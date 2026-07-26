"""Deterministic release-gate unit tests (no network or Supabase)."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from base64 import b64encode
from pathlib import Path
from typing import Any

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.models import ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.releases import (
    COMPLETE_EXPRESSION_DATES_PROFILE,
    ReleaseManifest,
    ReleaseScope,
)
from axiom_corpus.release.manifest import (
    build_release_content,
    build_unsigned_release_object,
    sign_release_object,
)

_SPEC = importlib.util.spec_from_file_location(
    "check_release_gate", Path(__file__).parents[1] / "scripts" / "check_release_gate.py"
)
assert _SPEC and _SPEC.loader
gate = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = gate
_SPEC.loader.exec_module(gate)


@pytest.fixture
def signing_keys() -> tuple[str, str]:
    private = Ed25519PrivateKey.generate()
    private_text = b64encode(
        private.private_bytes(
            serialization.Encoding.Raw,
            serialization.PrivateFormat.Raw,
            serialization.NoEncryption(),
        )
    ).decode()
    public_text = b64encode(
        private.public_key().public_bytes(
            serialization.Encoding.Raw,
            serialization.PublicFormat.Raw,
        )
    ).decode()
    return private_text, public_text


def _write_scope(store: CorpusArtifactStore, scope: ReleaseScope) -> None:
    source = store.source_path(
        scope.jurisdiction, scope.document_class, scope.version, "source.txt"
    )
    digest = store.write_text(source, "Official text.\n")
    source_rel = source.relative_to(store.root).as_posix()
    store.write_inventory(
        store.inventory_path(scope.jurisdiction, scope.document_class, scope.version),
        [
            SourceInventoryItem(
                citation_path=f"{scope.jurisdiction}/{scope.document_class}/1",
                source_path=source_rel,
                sha256=digest,
            )
        ],
    )
    store.write_provisions(
        store.provisions_path(scope.jurisdiction, scope.document_class, scope.version),
        [
            ProvisionRecord(
                jurisdiction=scope.jurisdiction,
                document_class=scope.document_class,
                citation_path=f"{scope.jurisdiction}/{scope.document_class}/1",
                version=scope.version,
                body="Official text.",
                source_path=source_rel,
            )
        ],
    )
    store.write_json(
        store.coverage_path(scope.jurisdiction, scope.document_class, scope.version),
        {
            "complete": True,
            "source_count": 1,
            "provision_count": 1,
            "matched_count": 1,
            "missing_from_provisions": [],
            "extra_provisions": [],
        },
    )


def _validation(content: dict[str, Any]) -> dict[str, Any]:
    return {
        "passed": True,
        "quality_profile": COMPLETE_EXPRESSION_DATES_PROFILE,
        "deep_validation": {
            "error_count": 0,
            "warning_count": 0,
            "scope_count": len(content["scopes"]),
        },
        "r2_readback": {
            "bucket": "axiom-corpus",
            "artifact_count": len(content["artifacts"]),
            "artifact_bytes": sum(entry["bytes"] for entry in content["artifacts"]),
            "verified_keys": [entry["r2_key"] for entry in content["artifacts"]],
        },
        "supabase_projection_evidence": [
            {
                "jurisdiction": scope["jurisdiction"],
                "document_class": scope["document_class"],
                "version": scope["version"],
                "expected": scope["provision_rows"],
                "actual": scope["provision_rows"],
                "expected_navigation": scope["navigation_rows"],
                "actual_navigation": scope["navigation_rows"],
                "expected_provision_projection_sha256": scope[
                    "provision_projection_sha256"
                ],
                "actual_provision_projection_sha256": scope[
                    "provision_projection_sha256"
                ],
                "expected_navigation_projection_sha256": scope[
                    "navigation_projection_sha256"
                ],
                "actual_navigation_projection_sha256": scope[
                    "navigation_projection_sha256"
                ],
            }
            for scope in content["scopes"]
        ],
    }


@pytest.fixture
def release_repo(tmp_path: Path, signing_keys: tuple[str, str]):
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "test@example.com"], check=True
    )
    private, public = signing_keys

    def make(
        name: str,
        scopes: list[ReleaseScope],
        *,
        created_at: str = "2026-07-26T00:00:00Z",
    ) -> tuple[dict[str, Any], Path]:
        store = CorpusArtifactStore(root / "data" / "corpus")
        for scope in scopes:
            _write_scope(store, scope)
        manifest = ReleaseManifest(
            name=name,
            scopes=tuple(scopes),
            quality_profile=COMPLETE_EXPRESSION_DATES_PROFILE,
        )
        plan_path = root / "manifests" / "releases" / f"{name}.json"
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_path.write_text(
            json.dumps(
                {
                    "name": name,
                    "quality_profile": COMPLETE_EXPRESSION_DATES_PROFILE,
                    "scopes": [
                        {
                            "jurisdiction": scope.jurisdiction,
                            "document_class": scope.document_class,
                            "version": scope.version,
                        }
                        for scope in scopes
                    ],
                }
            )
        )
        subprocess.run(["git", "-C", str(root), "add", "."], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "-c",
                "commit.gpgsign=false",
                "commit",
                "-qm",
                name,
            ],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(root), "update-ref", "refs/remotes/origin/main", "HEAD"],
            check=True,
        )
        content = build_release_content(
            root, release=manifest, validation={"passed": True}, created_at=created_at
        )
        content["validation"] = _validation(content)
        signed = sign_release_object(
            build_unsigned_release_object(content), private_key=private
        )
        path = root / f"{name}.json"
        path.write_text(json.dumps(signed, indent=2, sort_keys=True) + "\n")
        return signed, path

    return root, public, make


def _results(release_repo, name: str, scopes: list[ReleaseScope], active: list[dict]):
    root, public, make = release_repo
    obj, path = make(name, scopes)
    results = gate.run_gate(
        release_object_path=path,
        release=name,
        content_sha=obj["content_sha256"],
        repo_root=root,
        mode="activate",
        public_key=public,
        active_state_provider=lambda _obj: active,
    )
    return obj, path, results


def _by_name(results) -> dict[str, Any]:
    return {result.name: result for result in results}


def _install_active_manifest(root: Path, name: str, scope: ReleaseScope) -> None:
    path = root / "manifests" / "releases" / f"{name}.json"
    path.write_text(
        json.dumps(
            {
                "name": name,
                "scopes": [
                    {
                        "jurisdiction": scope.jurisdiction,
                        "document_class": scope.document_class,
                        "version": scope.version,
                    }
                ],
            }
        )
    )
    subprocess.run(["git", "-C", str(root), "add", str(path)], check=True)
    subprocess.run(
        ["git", "-C", str(root), "-c", "commit.gpgsign=false", "commit", "-qm", name],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(root), "update-ref", "refs/remotes/origin/main", "HEAD"],
        check=True,
    )


def test_object_identity_mismatch(release_repo) -> None:
    scope = ReleaseScope("uk", "manual", "2026-07-26-current")
    obj, path, _ = _results(release_repo, "uk-current", [scope], [])
    results = gate.run_gate(
        release_object_path=path,
        release="uk-wrong",
        content_sha=obj["content_sha256"],
        repo_root=release_repo[0],
        mode="activate",
        public_key=release_repo[1],
        active_state_provider=lambda _obj: [],
    )
    assert not _by_name(results)["object_identity"].passed


def test_tampered_signature(release_repo) -> None:
    scope = ReleaseScope("uk", "manual", "2026-07-26-current")
    obj, path, _ = _results(release_repo, "uk-tampered", [scope], [])
    obj["signature"]["value"] = "A" * len(obj["signature"]["value"])
    path.write_text(json.dumps(obj))
    results = gate.run_gate(
        release_object_path=path,
        release="uk-tampered",
        content_sha=obj["content_sha256"],
        repo_root=release_repo[0],
        mode="activate",
        public_key=release_repo[1],
        active_state_provider=lambda _obj: [],
    )
    assert "signature" in _by_name(results)["object_identity"].evidence
    assert not _by_name(results)["object_identity"].passed


@pytest.mark.parametrize("variant", ["missing", "mismatched"])
def test_missing_or_mismatched_cut_plan(release_repo, variant: str) -> None:
    scope = ReleaseScope("uk", "manual", "2026-07-26-current")
    obj, path, _ = _results(release_repo, f"uk-plan-{variant}", [scope], [])
    plan = release_repo[0] / "manifests" / "releases" / f"uk-plan-{variant}.json"
    if variant == "missing":
        plan.unlink()
    else:
        payload = json.loads(plan.read_text())
        payload["scopes"][0]["version"] = "2026-07-25-older"
        plan.write_text(json.dumps(payload))
    results = gate.run_gate(
        release_object_path=path,
        release=f"uk-plan-{variant}",
        content_sha=obj["content_sha256"],
        repo_root=release_repo[0],
        mode="activate",
        public_key=release_repo[1],
        active_state_provider=lambda _obj: [],
    )
    assert not _by_name(results)["cut_plan_provenance"].passed


def test_non_ancestor_commit(release_repo) -> None:
    scope = ReleaseScope("uk", "manual", "2026-07-26-current")
    obj, path, _ = _results(release_repo, "uk-nonancestor", [scope], [])
    root = release_repo[0]
    subprocess.run(["git", "-C", str(root), "checkout", "--orphan", "other"], check=True)
    subprocess.run(["git", "-C", str(root), "rm", "-rf", "."], check=True)
    (root / "other").write_text("x")
    subprocess.run(["git", "-C", str(root), "add", "other"], check=True)
    subprocess.run(
        ["git", "-C", str(root), "-c", "commit.gpgsign=false", "commit", "-qm", "other"],
        check=True,
    )
    bad = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    obj["content"]["git"]["commit"] = bad
    private = release_repo[2].__closure__  # keep fixture callable alive; key is not exposed
    del private
    # Provenance is independently evaluated even though mutating signed content also
    # makes identity fail.
    path.write_text(json.dumps(obj))
    results = gate.run_gate(
        release_object_path=path,
        release="uk-nonancestor",
        content_sha=obj["content_sha256"],
        repo_root=root,
        mode="activate",
        public_key=release_repo[1],
        active_state_provider=lambda _obj: [],
    )
    assert "not proven ancestor" in _by_name(results)["cut_plan_provenance"].evidence


def test_older_release_vs_active_fails_incident_replay(release_repo) -> None:
    scope = ReleaseScope("uk", "manual", "2026-07-24-council")
    active = [
        {
            "jurisdiction": "uk",
            "document_class": "manual",
            "changes": True,
            "current_release_name": "uk-active",
            "current_versions": ["2026-07-26-council"],
            "current_published_at": "2026-07-26T00:00:00Z",
        }
    ]
    _, _, results = _results(release_repo, "uk-older", [scope], active)
    assert not _by_name(results)["scope_monotonicity"].passed


def test_older_publication_with_equal_versions_fails_incident_replay(release_repo) -> None:
    scope = ReleaseScope("uk", "manual", "2026-07-24-council")
    root, public, make = release_repo
    obj, path = make("uk-2026-07-24", [scope], created_at="2026-07-24T00:00:00Z")
    _install_active_manifest(root, "uk-2026-07-26", scope)
    active = [
        {
            "jurisdiction": "uk",
            "document_class": "manual",
            "changes": True,
            "current_release_name": "uk-2026-07-26",
            "current_versions": [scope.version],
            "incoming_published_at": "2026-07-24T00:00:00Z",
            "current_published_at": "2026-07-26T00:00:00Z",
        }
    ]
    results = gate.run_gate(
        release_object_path=path,
        release="uk-2026-07-24",
        content_sha=obj["content_sha256"],
        repo_root=root,
        mode="activate",
        public_key=public,
        active_state_provider=lambda _obj: active,
    )
    result = _by_name(results)["scope_monotonicity"]
    assert not result.passed
    assert "versions tie" in result.evidence


def test_equal_release_reaffirm_passes(release_repo) -> None:
    scope = ReleaseScope("uk", "manual", "2026-07-26-council")
    active = [
        {
            "jurisdiction": "uk",
            "document_class": "manual",
            "changes": False,
            "current_release_name": "uk-equal",
        }
    ]
    _, _, results = _results(release_repo, "uk-equal", [scope], active)
    assert _by_name(results)["scope_monotonicity"].passed


def test_strict_superset_passes(release_repo) -> None:
    scopes = [
        ReleaseScope("uk", "manual", "2026-07-26-council"),
        ReleaseScope("uk-new", "manual", "2026-07-26-council"),
    ]
    active = [
        {
            "jurisdiction": "uk",
            "document_class": "manual",
            "changes": False,
            "current_release_name": "uk-superset",
        },
        {
            "jurisdiction": "uk-new",
            "document_class": "manual",
            "changes": True,
            "current_release_name": None,
        },
    ]
    _, _, results = _results(release_repo, "uk-superset", scopes, active)
    assert all(result.passed for result in results), [
        (result.name, result.evidence) for result in results
    ]


def test_malformed_version_key_fails_loudly(release_repo) -> None:
    scope = ReleaseScope("uk", "manual", "not-a-date")
    active = [
        {
            "jurisdiction": "uk",
            "document_class": "manual",
            "changes": True,
            "current_release_name": "uk-active",
            "current_versions": ["2026-07-26-council"],
            "current_published_at": "2026-07-26T00:00:00Z",
        }
    ]
    _, _, results = _results(release_repo, "uk-malformed", [scope], active)
    result = _by_name(results)["scope_monotonicity"]
    assert not result.passed
    assert "malformed version key" in result.evidence


def test_allow_regression_only_acknowledges_monotonicity(release_repo, capsys) -> None:
    scope = ReleaseScope("uk", "manual", "2026-07-24-council")
    root, public, make = release_repo
    obj, path = make("uk-ack", [scope], created_at="2026-07-24T00:00:00Z")
    _install_active_manifest(
        root, "uk-active", ReleaseScope("uk", "manual", "2026-07-26-council")
    )
    active = [
        {
            "jurisdiction": "uk",
            "document_class": "manual",
            "changes": True,
            "current_release_name": "uk-active",
            "current_versions": ["2026-07-26-council"],
            "current_published_at": "2026-07-26T00:00:00Z",
        }
    ]
    results = gate.run_gate(
        release_object_path=path,
        release="uk-ack",
        content_sha=obj["content_sha256"],
        repo_root=root,
        mode="activate",
        public_key=public,
        active_state_provider=lambda _obj: active,
        allow_regression=True,
    )
    monotonicity = _by_name(results)["scope_monotonicity"]
    assert monotonicity.passed and monotonicity.warning
    assert all(result.passed for result in results)
    gate._print_results(results)
    if monotonicity.warning:
        print("RELEASE_GATE_REGRESSION_ACKNOWLEDGED=uk-ack")
    assert "RELEASE_GATE_REGRESSION_ACKNOWLEDGED=uk-ack" in capsys.readouterr().out


@pytest.mark.parametrize("mismatch", ["path", "artifact"])
def test_mirror_path_or_artifact_mismatch(release_repo, mismatch: str) -> None:
    scope = ReleaseScope("uk", "manual", "2026-07-26-council")
    root, public, make = release_repo
    obj, path = make("uk-mirror", [scope])
    artifact = root / "publish-artifact.json"
    artifact.write_bytes(path.read_bytes())
    destination = f"releases/uk-mirror/{obj['content_sha256']}.json"
    if mismatch == "path":
        destination = "releases/wrong/path.json"
    else:
        artifact.write_bytes(path.read_bytes() + b" ")
    results = gate.run_gate(
        release_object_path=path,
        release="uk-mirror",
        content_sha=obj["content_sha256"],
        repo_root=root,
        mode="mirror",
        public_key=public,
        published_artifact=artifact,
        destination_path=destination,
    )
    assert not _by_name(results)["mirror_artifact_path"].passed
