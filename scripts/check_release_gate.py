"""Deterministic preflight for release activation and mirroring."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, cast

from axiom_corpus.corpus.supabase import (
    DEFAULT_ACCESS_TOKEN_ENV,
    DEFAULT_AXIOM_SUPABASE_URL,
    DEFAULT_DATABASE_URL_ENV,
    _management_api_post_json_with_curl,
    preview_corpus_release_activation,
    preview_corpus_release_activation_direct,
)
from axiom_corpus.release.manifest import (
    RELEASE_OBJECT_PUBLIC_KEY_ENV,
    ReleaseManifestError,
    verify_release_object,
)

Scope = tuple[str, str, str]
Pair = tuple[str, str]
ActiveStateProvider = Callable[[Mapping[str, Any]], list[dict[str, Any]]]
_VERSION_RE = re.compile(r"^(?P<day>\d{4}-\d{2}-\d{2})(?:-.+)?$")
_PROJECT_URL_RE = re.compile(r"^https://(?P<ref>[a-z0-9]{16,40})\.supabase\.co/?$")


@dataclass
class CheckResult:
    name: str
    passed: bool
    evidence: str
    warning: bool = False


def _canonical_content_sha(content: object) -> str:
    encoded = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "ascii"
    )
    return hashlib.sha256(encoded).hexdigest()


def _scope_triples(scopes: object) -> set[Scope]:
    if not isinstance(scopes, list):
        raise ValueError("scopes must be a JSON array")
    triples: set[Scope] = set()
    for index, scope in enumerate(scopes):
        if not isinstance(scope, dict):
            raise ValueError(f"scope {index} is not an object")
        values = tuple(scope.get(field) for field in ("jurisdiction", "document_class", "version"))
        if not all(isinstance(value, str) and value for value in values):
            raise ValueError(f"scope {index} lacks a non-empty jurisdiction/class/version")
        triple = cast(Scope, values)
        if triple in triples:
            raise ValueError(f"duplicate scope triple: {triple!r}")
        triples.add(triple)
    return triples


def _version_key(value: str) -> tuple[date, str]:
    match = _VERSION_RE.fullmatch(value)
    if match is None:
        raise ValueError(f"malformed version key {value!r}: expected YYYY-MM-DD-…")
    try:
        day = date.fromisoformat(match.group("day"))
    except ValueError as exc:
        raise ValueError(f"malformed version key {value!r}: invalid ISO date") from exc
    return day, value


def _timestamp(value: object, *, label: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} is missing")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{label} is malformed: {value!r}") from exc


def _is_ancestor(repo_root: Path, commit: str) -> tuple[bool, str]:
    completed = subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit, "origin/main"],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode == 0:
        return True, f"{commit} is an ancestor of origin/main"
    detail = completed.stderr.strip() or f"git exited {completed.returncode}"
    return False, f"{commit} is not proven ancestor of origin/main ({detail})"


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_bytes())
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _manifest_scopes_on_main(repo_root: Path, release: str) -> set[Scope]:
    relative = f"manifests/releases/{release}.json"
    completed = subprocess.run(
        ["git", "show", f"origin/main:{relative}"],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise ValueError(completed.stderr.strip() or f"{relative} is absent from origin/main")
    payload = json.loads(completed.stdout)
    if not isinstance(payload, dict):
        raise ValueError(f"{relative} on origin/main is not a JSON object")
    return _scope_triples(payload.get("scopes"))


def _identity_check(
    release_object: Mapping[str, Any],
    *,
    release: str,
    content_sha: str,
    public_key: str,
) -> CheckResult:
    failures: list[str] = []
    if release_object.get("release") != release:
        failures.append(f"release field is {release_object.get('release')!r}, expected {release!r}")
    actual_sha = _canonical_content_sha(release_object.get("content"))
    object_sha = release_object.get("content_sha256")
    if actual_sha != object_sha:
        failures.append(f"recomputed content sha {actual_sha} != object field {object_sha!r}")
    if actual_sha != content_sha:
        failures.append(f"recomputed content sha {actual_sha} != argument {content_sha}")
    try:
        verify_release_object(release_object, public_key=public_key)
    except (ReleaseManifestError, TypeError, ValueError) as exc:
        failures.append(f"signature/schema verification failed: {exc}")
    return CheckResult(
        "object_identity",
        not failures,
        "; ".join(failures)
        if failures
        else f"release and signed content sha {actual_sha} verified",
    )


def _provenance_check(
    release_object: Mapping[str, Any], *, release: str, repo_root: Path
) -> CheckResult:
    failures: list[str] = []
    plan_path = repo_root / "manifests" / "releases" / f"{release}.json"
    try:
        plan = _load_json(plan_path)
        plan_scopes = _scope_triples(plan.get("scopes"))
        object_scopes = _scope_triples(release_object.get("content", {}).get("scopes"))
        if plan_scopes != object_scopes:
            missing = sorted(object_scopes - plan_scopes)
            extra = sorted(plan_scopes - object_scopes)
            failures.append(f"cut-plan scope mismatch (missing={missing!r}, extra={extra!r})")
    except (OSError, json.JSONDecodeError, ValueError, AttributeError) as exc:
        failures.append(f"cannot validate cut plan {plan_path}: {exc}")

    commit = release_object.get("content", {}).get("git", {}).get("commit")
    if not isinstance(commit, str):
        failures.append("signed git commit is missing")
    else:
        ancestor, evidence = _is_ancestor(repo_root, commit)
        if not ancestor:
            failures.append(evidence)
    return CheckResult(
        "cut_plan_provenance",
        not failures,
        "; ".join(failures)
        if failures
        else f"{plan_path.relative_to(repo_root)} exactly matches; {evidence}",
    )


def _pair_versions(scopes: set[Scope]) -> dict[Pair, list[str]]:
    grouped: dict[Pair, list[str]] = defaultdict(list)
    for jurisdiction, document_class, version in scopes:
        grouped[(jurisdiction, document_class)].append(version)
    return grouped


def _monotonicity_check(
    release_object: Mapping[str, Any],
    active_rows: list[dict[str, Any]],
    *,
    allow_regression: bool,
) -> CheckResult:
    evidence_schema_failures: list[str] = []
    ordering_regressions: list[str] = []
    ordering_evidence_failed = False
    incoming = _pair_versions(_scope_triples(release_object["content"]["scopes"]))
    incoming_release = release_object["release"]
    covered_pairs: set[Pair] = set()
    checked = 0
    for index, row in enumerate(active_rows):
        jurisdiction = row.get("jurisdiction")
        document_class = row.get("document_class")
        if not (
            isinstance(jurisdiction, str)
            and jurisdiction
            and isinstance(document_class, str)
            and document_class
        ):
            evidence_schema_failures.append(
                f"active-state preview schema violation at row {index}: "
                "jurisdiction and document_class must be non-empty strings"
            )
            continue
        pair = (jurisdiction, document_class)
        if pair not in incoming:
            # Non-incoming rows are outside this check's scope and may be skipped even
            # when malformed; no monotonicity decision uses evidence from those rows.
            continue

        changes = row.get("changes")
        if "changes" not in row or not isinstance(changes, bool):
            evidence_schema_failures.append(
                f"active-state preview schema violation at row {index} for {pair!r}: "
                "changes must be present and boolean"
            )
            continue
        if not changes:
            if row.get("current_release_name") != incoming_release:
                evidence_schema_failures.append(
                    f"active-state preview schema violation at row {index} for {pair!r}: "
                    f"changes=false must identify incoming release {incoming_release!r} "
                    "in current_release_name"
                )
                continue
            covered_pairs.add(pair)
            continue

        required = ("current_release_name", "current_versions")
        missing_fields = [field for field in required if field not in row]
        if missing_fields:
            evidence_schema_failures.append(
                f"active-state preview schema violation at row {index} for {pair!r}: "
                f"changes=true requires fields {missing_fields!r}"
            )
            continue
        current_release = row["current_release_name"]
        current_versions = row["current_versions"]
        if current_release is not None and not (
            isinstance(current_release, str) and current_release
        ):
            evidence_schema_failures.append(
                f"active-state preview schema violation at row {index} for {pair!r}: "
                "current_release_name must be a non-empty string or null"
            )
            continue
        if not isinstance(current_versions, list):
            evidence_schema_failures.append(
                f"active-state preview schema violation at row {index} for {pair!r}: "
                "current_versions must be a list"
            )
            continue
        covered_pairs.add(pair)
        if current_release is None:
            continue

        checked += 1
        if not current_versions:
            evidence_schema_failures.append(
                f"{pair}: active release {current_release!r} has no version evidence"
            )
            continue
        if set(incoming[pair]) == {str(value) for value in current_versions}:
            # Identical version evidence on both sides is monotone by
            # identity — no version-key ordering proof is needed (some
            # grandfathered versions, e.g. us-ky form 2026-740-es, do
            # not parse as YYYY-MM-DD-…). Ordering reduces to the same
            # publication-recency requirement the frontier-tie branch
            # enforces below.
            try:
                incoming_published = _timestamp(
                    row.get("incoming_published_at"),
                    label="incoming database publication timestamp",
                )
                current_published = _timestamp(
                    row.get("current_published_at"),
                    label=f"{pair} active publication timestamp",
                )
            except ValueError as exc:
                evidence_schema_failures.append(str(exc))
                ordering_evidence_failed = True
                continue
            if incoming_published < current_published:
                ordering_regressions.append(
                    f"{pair}: identical version evidence, but incoming "
                    f"{incoming_release!r} was published "
                    f"{incoming_published.isoformat()} before active "
                    f"{current_release!r} at {current_published.isoformat()}"
                )
            continue
        try:
            incoming_frontier = max(_version_key(value) for value in incoming[pair])
            active_frontier = max(_version_key(str(value)) for value in current_versions)
        except ValueError as exc:
            evidence_schema_failures.append(f"{pair}: {exc}")
            ordering_evidence_failed = True
            continue
        if incoming_frontier < active_frontier:
            ordering_regressions.append(
                f"{pair}: incoming frontier {incoming_frontier[1]!r} precedes "
                f"active {active_frontier[1]!r} from {current_release!r}"
            )
            continue
        if incoming_frontier == active_frontier:
            try:
                incoming_published = _timestamp(
                    row.get("incoming_published_at"),
                    label="incoming database publication timestamp",
                )
                current_published = _timestamp(
                    row.get("current_published_at"),
                    label=f"{pair} active publication timestamp",
                )
            except ValueError as exc:
                evidence_schema_failures.append(str(exc))
                ordering_evidence_failed = True
                continue
            if incoming_published < current_published:
                ordering_regressions.append(
                    f"{pair}: versions tie at {incoming_frontier[1]!r}, but incoming "
                    f"{incoming_release!r} was published {incoming_published.isoformat()} "
                    f"before active {current_release!r} at {current_published.isoformat()}"
                )
    missing_pairs = sorted(set(incoming) - covered_pairs)
    if missing_pairs:
        evidence_schema_failures.append(
            "active-state preview cannot support scope_monotonicity: "
            f"missing incoming pair(s) {missing_pairs!r}; refusing vacuous pass"
        )

    failures = evidence_schema_failures + ordering_regressions
    warning = bool(ordering_regressions and allow_regression and not evidence_schema_failures)
    timestamp_source = (
        "publication evidence: corpus.release_objects.created_at; "
        "scope_activation_history records activation time, not publication time"
    )
    if failures:
        evidence = "; ".join(failures)
        if ordering_evidence_failed or ordering_regressions:
            evidence = f"{evidence}; {timestamp_source}"
    else:
        evidence = (
            f"all {len(incoming)} incoming pair(s) have preview evidence; "
            f"{checked} displaced pair(s) are version/publication monotone; {timestamp_source}"
        )
    return CheckResult(
        "scope_monotonicity",
        not failures or warning,
        evidence,
        warning=warning,
    )


def _no_orphan_check(active_rows: list[dict[str, Any]], *, repo_root: Path) -> CheckResult:
    failures: list[str] = []
    checked = 0
    cache: dict[str, set[Scope]] = {}
    for row in active_rows:
        if not row.get("changes") or not row.get("current_release_name"):
            continue
        checked += 1
        release = str(row["current_release_name"])
        pair = (str(row.get("jurisdiction")), str(row.get("document_class")))
        if release not in cache:
            try:
                cache[release] = _manifest_scopes_on_main(repo_root, release)
            except (json.JSONDecodeError, ValueError) as exc:
                failures.append(
                    f"{pair}: active release {release!r} has no valid main manifest ({exc})"
                )
                cache[release] = set()
        if not any(scope[:2] == pair for scope in cache[release]):
            failures.append(f"{pair}: manifest for displaced {release!r} does not cover the pair")
    return CheckResult(
        "no_orphan",
        not failures,
        "; ".join(failures)
        if failures
        else f"{checked} displaced pair attribution(s) remain on main",
    )


def _mirror_check(
    release_object_path: Path,
    *,
    published_artifact: Path | None,
    destination_path: str | None,
    release: str,
    content_sha: str,
) -> CheckResult:
    failures: list[str] = []
    expected = f"releases/{release}/{content_sha}.json"
    if destination_path != expected:
        failures.append(f"destination is {destination_path!r}, expected {expected!r}")
    if published_artifact is None:
        failures.append("--published-artifact is required in mirror mode")
    else:
        try:
            if release_object_path.read_bytes() != published_artifact.read_bytes():
                failures.append("release object bytes differ from the named publish-run artifact")
        except OSError as exc:
            failures.append(f"cannot compare publish artifact bytes: {exc}")
    return CheckResult(
        "mirror_artifact_path",
        not failures,
        "; ".join(failures)
        if failures
        else f"publish artifact is byte-identical; destination {expected}",
    )


def _active_state_from_file(path: Path) -> ActiveStateProvider:
    rows = json.loads(path.read_bytes())
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError("active-state fixture must be a JSON array of objects")
    return lambda _release_object: rows


def _supabase_active_state_provider(
    args: argparse.Namespace, public_key: str
) -> ActiveStateProvider:
    match = _PROJECT_URL_RE.fullmatch(args.supabase_url)
    if match is None:
        raise ValueError("--supabase-url must be a bare https://<ref>.supabase.co URL")
    project_ref = match.group("ref")
    if args.expected_project_ref and args.expected_project_ref != project_ref:
        raise ValueError("--expected-project-ref does not match --supabase-url")
    access_token = os.environ.get(DEFAULT_ACCESS_TOKEN_ENV)
    database_url = os.environ.get(DEFAULT_DATABASE_URL_ENV) or None
    if not access_token:
        raise ValueError(f"{DEFAULT_ACCESS_TOKEN_ENV} is required without --active-state-file")

    def provide(release_object: Mapping[str, Any]) -> list[dict[str, Any]]:
        if database_url:
            # The preview recomputes per-scope evidence; over the Management
            # API's 120 s HTTP proxy that stops fitting around 800 scopes.
            rows = preview_corpus_release_activation_direct(
                release_object,
                database_url=database_url,
                public_key=public_key,
                expected_project_ref=args.expected_project_ref or project_ref,
            )
        else:
            rows = preview_corpus_release_activation(
                release_object,
                access_token=access_token,
                public_key=public_key,
                supabase_url=args.supabase_url,
                expected_project_ref=args.expected_project_ref or project_ref,
            )
        for row in rows:
            if row.get("changes") is True:
                row.setdefault("current_versions", [])
        changing = [row for row in rows if row.get("changes") and row.get("current_release_name")]
        if not changing:
            return cast(list[dict[str, Any]], rows)
        identities = sorted(
            {
                (str(row["current_release_name"]), str(row["current_content_sha256"]))
                for row in changing
            }
            | {
                (
                    str(release_object["release"]),
                    str(release_object["content_sha256"]),
                )
            }
        )
        details = cast(
            list[dict[str, Any]],
            _management_api_post_json_with_curl(
                f"https://api.supabase.com/v1/projects/{project_ref}/database/query",
                payload={
                    "query": (
                        "SELECT release_name, content_sha256, created_at AS published_at, "
                        "release_object FROM corpus.release_objects "
                        "WHERE (release_name, content_sha256) IN "
                        "(SELECT * FROM unnest($1::text[], $2::text[]))"
                    ),
                    "parameters": [
                        [identity[0] for identity in identities],
                        [identity[1] for identity in identities],
                    ],
                    "read_only": True,
                },
                access_token=access_token,
                timeout=120,
            ),
        )
        by_identity: dict[tuple[str, str], dict[str, Any]] = {}
        for detail in details:
            obj = detail.get("release_object", {})
            scopes = _scope_triples(obj.get("content", {}).get("scopes"))
            detail["scopes"] = scopes
            by_identity[(str(detail["release_name"]), str(detail["content_sha256"]))] = detail
        for row in rows:
            incoming_detail = by_identity.get(
                (
                    str(release_object["release"]),
                    str(release_object["content_sha256"]),
                )
            )
            if incoming_detail is not None:
                row["incoming_published_at"] = incoming_detail["published_at"]
            identity = (
                str(row.get("current_release_name")),
                str(row.get("current_content_sha256")),
            )
            active_detail = by_identity.get(identity)
            if active_detail is None:
                continue
            pair = (str(row["jurisdiction"]), str(row["document_class"]))
            row["current_versions"] = sorted(
                scope[2] for scope in active_detail["scopes"] if scope[:2] == pair
            )
            row["current_published_at"] = active_detail["published_at"]
        return cast(list[dict[str, Any]], rows)

    return provide


def run_gate(
    *,
    release_object_path: Path,
    release: str,
    content_sha: str,
    repo_root: Path,
    mode: str,
    public_key: str,
    active_state_provider: ActiveStateProvider | None = None,
    allow_regression: bool = False,
    published_artifact: Path | None = None,
    destination_path: str | None = None,
) -> list[CheckResult]:
    try:
        release_object = _load_json(release_object_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return [CheckResult("object_identity", False, f"cannot load signed object: {exc}")]
    results = [
        _identity_check(
            release_object, release=release, content_sha=content_sha, public_key=public_key
        ),
        _provenance_check(release_object, release=release, repo_root=repo_root),
    ]
    if mode == "activate":
        if active_state_provider is None:
            results.extend(
                [
                    CheckResult("scope_monotonicity", False, "active-state provider is missing"),
                    CheckResult("no_orphan", False, "active-state provider is missing"),
                ]
            )
        else:
            try:
                active_rows = active_state_provider(release_object)
                results.append(
                    _monotonicity_check(
                        release_object, active_rows, allow_regression=allow_regression
                    )
                )
                results.append(_no_orphan_check(active_rows, repo_root=repo_root))
            except (KeyError, TypeError, ValueError, RuntimeError) as exc:
                results.extend(
                    [
                        CheckResult(
                            "scope_monotonicity", False, f"active-state lookup failed: {exc}"
                        ),
                        CheckResult("no_orphan", False, "active-state evidence unavailable"),
                    ]
                )
    else:
        results.append(
            _mirror_check(
                release_object_path,
                published_artifact=published_artifact,
                destination_path=destination_path,
                release=release,
                content_sha=content_sha,
            )
        )
    return results


def _print_results(results: list[CheckResult]) -> None:
    print("| check | result | evidence |")
    print("|---|---|---|")
    for result in results:
        status = "WARN" if result.warning else ("PASS" if result.passed else "FAIL")
        evidence = result.evidence.replace("|", "\\|").replace("\n", " ")
        print(f"| {result.name} | {status} | {evidence} |")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-object", type=Path, required=True)
    parser.add_argument("--release", required=True)
    parser.add_argument("--content-sha", required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--mode", choices=("activate", "mirror"), required=True)
    parser.add_argument("--supabase-url", default=DEFAULT_AXIOM_SUPABASE_URL)
    parser.add_argument("--expected-project-ref")
    parser.add_argument("--allow-regression", action="store_true")
    parser.add_argument("--active-state-file", type=Path)
    parser.add_argument("--active-state-output", type=Path)
    parser.add_argument("--published-artifact", type=Path)
    parser.add_argument("--destination-path")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    public_key = os.environ.get(RELEASE_OBJECT_PUBLIC_KEY_ENV) or os.environ.get(
        "RELEASE_TRUST_ROOT"
    )
    if not public_key:
        raise SystemExit(f"{RELEASE_OBJECT_PUBLIC_KEY_ENV} (or RELEASE_TRUST_ROOT) is required")
    provider: ActiveStateProvider | None = None
    if args.mode == "activate":
        provider = (
            _active_state_from_file(args.active_state_file)
            if args.active_state_file
            else _supabase_active_state_provider(args, public_key)
        )
        if args.active_state_output is not None:
            base_provider = provider

            def recording_provider(
                release_object: Mapping[str, Any],
            ) -> list[dict[str, Any]]:
                rows = base_provider(release_object)
                args.active_state_output.parent.mkdir(parents=True, exist_ok=True)
                args.active_state_output.write_text(
                    json.dumps(rows, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                return rows

            provider = recording_provider
    results = run_gate(
        release_object_path=args.release_object,
        release=args.release,
        content_sha=args.content_sha,
        repo_root=args.repo_root.resolve(),
        mode=args.mode,
        public_key=public_key,
        active_state_provider=provider,
        allow_regression=args.allow_regression,
        published_artifact=args.published_artifact,
        destination_path=args.destination_path,
    )
    _print_results(results)
    acknowledged = any(result.warning for result in results)
    if acknowledged:
        print(f"RELEASE_GATE_REGRESSION_ACKNOWLEDGED={args.release}")
    return 0 if all(result.passed for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
