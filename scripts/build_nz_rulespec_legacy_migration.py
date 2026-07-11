"""Build the auditable RuleSpec-NZ legacy-corpus migration ledger."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from axiom_corpus.corpus.releases import ReleaseManifest
from axiom_corpus.release.manifest import selector_sha256

SCHEMA_VERSION = "axiom-corpus/nz-rulespec-legacy-migration/v2"
RELEASE_NAME = "nz-rulespec-2026-07-10"
SELECTOR_RELATIVE_PATH = Path("manifests/releases") / f"{RELEASE_NAME}.json"
VERSION = "2026-06-16-rulespec-nz-pco"
SOURCE_REPOSITORY = "TheAxiomFoundation/rulespec-nz"
SOURCE_COMMIT = "c9e0c069a8f9ec9aacb41f8f0bb1b5d56c148e38"

AGENCY_SUPERSESSIONS: dict[str, tuple[tuple[str, ...], str]] = {
    "nz/agency/ird/acc-earners-levy-rates": (
        (
            "nz/regulation/regulation/public/2025/0018/regulation/4",
            "nz/regulation/regulation/public/2025/0018/regulation/5",
        ),
        "The IRD summary remains a supplemental reference URL in RuleSpec-NZ; "
        "the active corpus cites the official levy-rate and earnings-cap regulations.",
    ),
    "nz/agency/ird/working-for-families-family-tax-credit": (
        (
            "nz/statute/act/public/2007/0097/section/md-3",
            "nz/statute/act/public/2007/0097/section/md-13",
        ),
        "The IRD summary remains a supplemental reference URL in RuleSpec-NZ; "
        "the active corpus cites the official family-credit amount and abatement sections.",
    ),
    "nz/agency/ird/working-for-families-in-work-tax-credit": (
        (
            "nz/statute/act/public/2007/0097/section/md-10",
            "nz/statute/act/public/2026/0008/section/105",
        ),
        "The IRD summary remains a supplemental reference URL in RuleSpec-NZ; "
        "the active corpus cites the official in-work credit section and 2026 amendment.",
    ),
    "nz/agency/ird/working-for-families-best-start": (
        (
            "nz/statute/act/public/2007/0097/section/mg-1",
            "nz/statute/act/public/2007/0097/section/mg-2",
            "nz/statute/act/public/2007/0097/section/mg-3",
        ),
        "The IRD summary remains a supplemental reference URL in RuleSpec-NZ; "
        "the active corpus cites the official Best Start calculation sections.",
    ),
    "nz/agency/ird/working-for-families-minimum-family-tax-credit": (
        (
            "nz/statute/act/public/2007/0097/section/me-1",
            "nz/statute/act/public/2007/0097/section/me-3",
        ),
        "The IRD summary remains a supplemental reference URL in RuleSpec-NZ; "
        "the active corpus cites the official minimum-family-credit sections.",
    ),
}

RULESPEC_PCO_HIERARCHY_SUPERSESSIONS: dict[str, tuple[str, str]] = {
    "nz/regulation/regulation/public/1998/0277/regulation/4-lms1588497": (
        "nz/regulation/regulation/public/1998/0277/schedule/2/part/2/clause/4",
        "LMS1588497",
    ),
    "nz/statute/act/public/2001/0049/section/32-dlm104829": (
        "nz/statute/act/public/2001/0049/schedule/1/part/2/clause/32",
        "DLM104829",
    ),
    "nz/statute/act/public/2001/0049/section/47-dlm104891": (
        "nz/statute/act/public/2001/0049/schedule/1/part/2/clause/47",
        "DLM104891",
    ),
    "nz/statute/act/public/2007/0097/section/1-dlm1523194": (
        "nz/statute/act/public/2007/0097/schedule/1/part/a/clause/1",
        "DLM1523194",
    ),
    "nz/statute/act/public/2018/0032/section/19-dlm6784845": (
        "nz/statute/act/public/2018/0032/schedule/3/part/5/clause/19",
        "DLM6784845",
    ),
    "nz/statute/act/public/2018/0032/schedule/4/part/1": (
        "nz/statute/act/public/2018/0032/schedule/4/part/1/clause/lms118447",
        "LMS118447",
    ),
    "nz/statute/act/public/2018/0032/schedule/4/part/2": (
        "nz/statute/act/public/2018/0032/schedule/4/part/2/clause/lms118467",
        "LMS118467",
    ),
    "nz/statute/act/public/2018/0032/schedule/4/part/3": (
        "nz/statute/act/public/2018/0032/schedule/4/part/3/clause/lms118466",
        "LMS118466",
    ),
    "nz/statute/act/public/2018/0032/schedule/4/part/7": (
        "nz/statute/act/public/2018/0032/schedule/4/part/7/clause/lms118453",
        "LMS118453",
    ),
    "nz/statute/act/public/2018/0032/schedule/4/part/8": (
        "nz/statute/act/public/2018/0032/schedule/4/part/8/clause/lms118454",
        "LMS118454",
    ),
    "nz/statute/act/public/2018/0032/schedule/4/part/9": (
        "nz/statute/act/public/2018/0032/schedule/4/part/9/clause/lms118455",
        "LMS118455",
    ),
}

LEGACY_PCO_HIERARCHY_SUPERSESSIONS: dict[str, tuple[str, str]] = {
    "nz/statute/act/public/2018/0032/schedule/3/clause/19": (
        "nz/statute/act/public/2018/0032/schedule/3/part/5/clause/19",
        "DLM6784845",
    ),
    "nz/statute/act/public/2018/0032/schedule/4/part/9/clause/2": (
        "nz/statute/act/public/2018/0032/schedule/4/part/9/clause/lms118455",
        "LMS118455",
    ),
}

PCO_HIERARCHY_SUPERSESSIONS = {
    **RULESPEC_PCO_HIERARCHY_SUPERSESSIONS,
    **LEGACY_PCO_HIERARCHY_SUPERSESSIONS,
}

_OFFICIAL_PCO_NETLOC = "www.legislation.govt.nz"
_PCO_ELEMENT_LEAF_RE = re.compile(r"(?P<element_id>(?:DLM|LMS)[0-9]+)\.html")
_PCO_COLLISION_SUFFIX_RE = re.compile(
    r"-(?P<element_id>(?:DLM|LMS)[0-9]+)$",
    re.IGNORECASE,
)
_PCO_DOCUMENT_FAMILY_RE = re.compile(r"[a-z][a-z0-9-]*")


def _sha256_text(value: str | None) -> str | None:
    if value is None:
        return None
    return hashlib.sha256(value.encode()).hexdigest()


def _url_element_id(value: str | None) -> str | None:
    """Return an element ID only from one canonical official PCO page URL."""

    if not isinstance(value, str):
        return None
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None
    if (
        parsed.scheme != "https"
        or parsed.netloc != _OFFICIAL_PCO_NETLOC
        or parsed.query
        or parsed.fragment
    ):
        return None

    parts = parsed.path.strip("/").split("/")
    if len(parts) != 6:
        return None
    document_type, family, year, number, expression, leaf = parts
    if document_type in {"act", "regulation"}:
        if _PCO_DOCUMENT_FAMILY_RE.fullmatch(family) is None:
            return None
    elif document_type == "secondary-legislation":
        if family != "pco-drafted":
            return None
    else:
        return None
    if (
        re.fullmatch(r"[0-9]{4}", year) is None
        or re.fullmatch(r"[0-9]+", number) is None
        or expression != "latest"
    ):
        return None
    match = _PCO_ELEMENT_LEAF_RE.fullmatch(leaf)
    return match.group("element_id").lower() if match else None


CanonicalIndexes = tuple[
    dict[str, dict[str, Any]],
    dict[str, list[dict[str, Any]]],
    dict[str, list[dict[str, Any]]],
    dict[str, list[dict[str, Any]]],
]


def _canonical_indexes(rows: list[dict[str, Any]]) -> CanonicalIndexes:
    by_path: dict[str, dict[str, Any]] = {}
    by_lower_path: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_url: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_element_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        citation_path = row["citation_path"]
        if citation_path in by_path:
            raise ValueError(f"Duplicate canonical citation path: {citation_path}")
        by_path[citation_path] = row
        by_lower_path[citation_path.lower()].append(row)
        source_url = row.get("source_url")
        if source_url:
            by_url[source_url].append(row)
        element_id = _url_element_id(source_url)
        if element_id:
            by_element_id[element_id].append(row)
    return by_path, by_lower_path, by_url, by_element_id


def _resolve_canonical_matches(
    legacy: dict[str, Any], indexes: CanonicalIndexes
) -> tuple[list[dict[str, Any]], str | None]:
    """Resolve a legacy row only through canonical source identity."""
    by_path, by_lower_path, by_url, by_element_id = indexes
    citation_path = legacy["citation_path"]
    exact = by_path.get(citation_path)
    if exact is not None:
        return [exact], "exact-citation"

    lowercase_candidates = by_lower_path.get(citation_path.lower(), [])
    if len(lowercase_candidates) == 1:
        return lowercase_candidates, "canonical-lowercase-citation"

    # The old converter added a PCO element ID to every colliding token before
    # routing provisions into their final namespaces.  After routing first,
    # most of those tokens are unique and the canonical path is the exact
    # legacy path with that suffix removed.  Accept that migration only when
    # the row at the resulting path carries the same official PCO identifier.
    collision_suffix = _PCO_COLLISION_SUFFIX_RE.search(citation_path)
    if collision_suffix is not None:
        unsuffixed_path = citation_path[: collision_suffix.start()]
        unsuffixed_candidates = by_lower_path.get(unsuffixed_path.lower(), [])
        if len(unsuffixed_candidates) == 1:
            candidate = unsuffixed_candidates[0]
            identifiers = candidate.get("identifiers") or {}
            canonical_element_ids = {
                str(identifiers[key]).lower()
                for key in (
                    "legislation.govt.nz:provision",
                    "legislation.govt.nz:element",
                )
                if identifiers.get(key)
            }
            if collision_suffix.group("element_id").lower() in canonical_element_ids:
                return [candidate], "official-pco-element-id-citation-suffix"

    source_url = legacy.get("source_url")
    source_url_candidates = by_url.get(source_url, []) if isinstance(source_url, str) else []
    if len(source_url_candidates) == 1:
        return source_url_candidates, "official-source-url"

    element_id = _url_element_id(legacy.get("source_url"))
    element_candidates = by_element_id.get(element_id or "", [])
    if len(element_candidates) == 1:
        return element_candidates, "official-pco-element-id"

    return [], None


def _git_output(repo: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), *args],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError(
            f"Cannot verify RuleSpec-NZ legacy checkout at {repo}: git {' '.join(args)} failed"
        ) from exc
    return result.stdout.strip()


def _verified_legacy_checkout_root(legacy_root: Path) -> Path:
    """Require the immutable, clean RuleSpec-NZ checkout used by the ledger."""
    try:
        legacy_root = legacy_root.resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"RuleSpec-NZ legacy corpus root does not exist: {legacy_root}") from exc

    checkout_root = Path(_git_output(legacy_root, "rev-parse", "--show-toplevel")).resolve()
    expected_legacy_root = checkout_root / "data/corpus/provisions/nz"
    if legacy_root != expected_legacy_root:
        raise ValueError(
            "RuleSpec-NZ legacy corpus root must be the checkout's exact "
            f"data/corpus/provisions/nz directory: {expected_legacy_root}"
        )

    head = _git_output(checkout_root, "rev-parse", "HEAD")
    if head != SOURCE_COMMIT:
        raise ValueError(
            f"RuleSpec-NZ legacy checkout must be exactly {SOURCE_COMMIT}; found {head}"
        )

    status = _git_output(
        checkout_root,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
    )
    if status:
        raise ValueError(
            "RuleSpec-NZ legacy checkout must be clean; found uncommitted or untracked files"
        )
    return checkout_root


def _load_active_rows(
    repo: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any], ReleaseManifest]:
    selector_path = repo / SELECTOR_RELATIVE_PATH
    selector = json.loads(selector_path.read_text())
    release = ReleaseManifest.load(selector_path)
    if release.name != RELEASE_NAME:
        raise ValueError(f"Release selector {SELECTOR_RELATIVE_PATH} must name {RELEASE_NAME!r}")
    rows: list[dict[str, Any]] = []
    for scope in selector["scopes"]:
        artifact = (
            repo
            / "data/corpus/provisions"
            / scope["jurisdiction"]
            / scope["document_class"]
            / f"{scope['version']}.jsonl"
        )
        rows.extend(json.loads(line) for line in artifact.read_text().splitlines())
    return rows, selector, release


def _canonical_target(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "body_sha256": _sha256_text(row.get("body")),
        "citation_path": row["citation_path"],
        "id": row["id"],
        "source_url_sha256": _sha256_text(row.get("source_url")),
        "version": row["version"],
    }


def _pco_hierarchy_supersession(
    citation_path: str, by_path: dict[str, dict[str, Any]]
) -> tuple[dict[str, Any], str] | None:
    supersession = PCO_HIERARCHY_SUPERSESSIONS.get(citation_path.lower())
    if supersession is None:
        return None

    target_path, expected_pco_id = supersession
    target = by_path.get(target_path)
    if target is None:
        raise ValueError(f"Explicit PCO hierarchy supersession target is absent: {target_path}")
    identifiers = target.get("identifiers") or {}
    actual_pco_id = identifiers.get("legislation.govt.nz:provision")
    if actual_pco_id != expected_pco_id:
        raise ValueError(
            f"Explicit PCO hierarchy supersession target {target_path} must identify "
            f"{expected_pco_id}; found {actual_pco_id!r}"
        )
    rationale = (
        f"The legacy citation flattened PCO provision {expected_pco_id}; the canonical "
        f"parser preserves its official schedule hierarchy at {target_path}."
    )
    return target, rationale


def _rulespec_pco_hierarchy_supersessions(
    by_path: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for legacy_path in sorted(RULESPEC_PCO_HIERARCHY_SUPERSESSIONS):
        resolved = _pco_hierarchy_supersession(legacy_path, by_path)
        if resolved is None:  # pragma: no cover - constant and lookup share the same key set
            raise AssertionError(legacy_path)
        target, _ = resolved
        _, pco_id = RULESPEC_PCO_HIERARCHY_SUPERSESSIONS[legacy_path]
        records.append(
            {
                "canonical": _canonical_target(target),
                "legacy_citation_path": legacy_path,
                "mapping_basis": "explicit-pco-hierarchy-supersession",
                "pco_provision_id": pco_id,
            }
        )
    return records


def build_migration(repo: Path, legacy_root: Path) -> dict[str, Any]:
    """Return the complete migration ledger for every legacy local row."""
    legacy_checkout_root = _verified_legacy_checkout_root(legacy_root)
    legacy_root = legacy_checkout_root / "data/corpus/provisions/nz"
    active_rows, selector, release = _load_active_rows(repo)
    body_rows = [row for row in active_rows if row.get("body") is not None]
    indexes = _canonical_indexes(body_rows)
    by_path = indexes[0]

    prior_rows = {
        row["citation_path"]: row
        for row in (
            json.loads(line)
            for line in (repo / "data/corpus/provisions/nz/statute/2026-07-08.jsonl")
            .read_text()
            .splitlines()
        )
    }
    entries: list[dict[str, Any]] = []
    for artifact in sorted(legacy_root.glob("*/*.jsonl")):
        relative_artifact = artifact.relative_to(legacy_checkout_root)
        for line_number, raw_line in enumerate(artifact.read_text().splitlines(), 1):
            legacy = json.loads(raw_line)
            citation_path = legacy["citation_path"]
            matches, basis = _resolve_canonical_matches(legacy, indexes)

            disposition = "canonical"
            rationale = (
                f"Official PCO XML re-extraction supersedes the curated legacy row; "
                f"source identity is preserved by {basis}."
            )
            pco_supersession = _pco_hierarchy_supersession(citation_path, by_path)
            if pco_supersession is not None:
                target, rationale = pco_supersession
                matches = [target]
                disposition = "superseded"
                basis = "explicit-pco-hierarchy-supersession"
            elif not matches:
                supersession = AGENCY_SUPERSESSIONS.get(citation_path)
                if supersession is None:
                    msg = f"No canonical or explicit supersession mapping for {citation_path}"
                    raise ValueError(msg)
                target_paths, rationale = supersession
                matches = [by_path[path] for path in target_paths]
                disposition = "superseded"
                basis = "explicit-agency-summary-supersession"

            prior = prior_rows.get(citation_path)
            prior_status = "absent"
            if prior is not None:
                prior_status = (
                    "shared-identical"
                    if prior.get("body") == legacy.get("body")
                    else "shared-divergent"
                )
            entries.append(
                {
                    "body_relation": (
                        "byte-identical"
                        if len(matches) == 1 and matches[0].get("body") == legacy.get("body")
                        else "official-source-reextraction"
                    ),
                    "canonical": [_canonical_target(row) for row in matches],
                    "disposition": disposition,
                    "legacy": {
                        "artifact": relative_artifact.as_posix(),
                        "body_sha256": _sha256_text(legacy.get("body")),
                        "citation_path": citation_path,
                        "line": line_number,
                        "row_sha256": hashlib.sha256(raw_line.encode()).hexdigest(),
                        "source_url_sha256": _sha256_text(legacy.get("source_url")),
                    },
                    "mapping_basis": basis,
                    "prior_external_body_sha256": (
                        _sha256_text(prior.get("body")) if prior is not None else None
                    ),
                    "prior_external_status": prior_status,
                    "rationale": rationale,
                }
            )

    status_counts = Counter(entry["prior_external_status"] for entry in entries)
    disposition_counts = Counter(entry["disposition"] for entry in entries)
    return {
        "canonical_release": RELEASE_NAME,
        "canonical_release_cut_plan": {
            "path": SELECTOR_RELATIVE_PATH.as_posix(),
            "selector_sha256": selector_sha256(release),
        },
        "canonical_scopes": selector["scopes"],
        "disposition_counts": dict(sorted(disposition_counts.items())),
        "entries": entries,
        "legacy_row_count": len(entries),
        "legacy_unique_citation_count": len(
            {entry["legacy"]["citation_path"] for entry in entries}
        ),
        "prior_external_status_counts": dict(sorted(status_counts.items())),
        "rulespec_citation_supersessions": _rulespec_pco_hierarchy_supersessions(by_path),
        "schema_version": SCHEMA_VERSION,
        "source_commit": SOURCE_COMMIT,
        "source_repository": SOURCE_REPOSITORY,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--legacy-root", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/corpus/migrations/nz/rulespec-nz-legacy-2026-06-17.json"),
    )
    args = parser.parse_args()
    payload = build_migration(args.repo.resolve(), args.legacy_root.resolve())
    output = args.output if args.output.is_absolute() else args.repo / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
