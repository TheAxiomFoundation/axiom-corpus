"""Deterministic release-gate unit tests (no network or Supabase)."""

from __future__ import annotations

import copy
import importlib.util
import json
import re
import subprocess
import sys
from argparse import Namespace
from base64 import b64decode, b64encode
from pathlib import Path
from typing import Any

import pytest
import yaml
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.models import ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.releases import (
    COMPLETE_EXPRESSION_DATES_PROFILE,
    LAYER_BASE,
    ReleaseManifest,
    ReleaseScope,
)
from axiom_corpus.corpus.supabase import PREVIEW_ACTIVATION_QUERY
from axiom_corpus.release.manifest import (
    RELEASE_OBJECT_SCHEMA_V2,
    RELEASE_OBJECT_SCHEMA_V3,
    RELEASE_OBJECT_SCHEMA_V4,
    RELEASE_OBJECT_SIGNATURE_ALGORITHM,
    RELEASE_OBJECT_SIGNATURE_KEY_ID,
    build_release_content,
    build_unsigned_release_object,
    canonical_release_object_bytes,
    canonical_release_public_key,
    release_content_sha256,
    sign_release_object,
)

_SPEC = importlib.util.spec_from_file_location(
    "check_release_gate", Path(__file__).parents[1] / "scripts" / "check_release_gate.py"
)
assert _SPEC and _SPEC.loader
gate = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = gate
_SPEC.loader.exec_module(gate)

# A layered United States line: the May base of the Code under its primary cuts.
B = ReleaseScope("us", "statute", "2026-04-29", layer=LAYER_BASE)
B_PRIMARY = ReleaseScope("us", "statute", "2026-04-29")
B_NEW = ReleaseScope("us", "statute", "2026-11-01-us-code", layer=LAYER_BASE)
P1 = ReleaseScope("us", "statute", "2026-07-26-p1")
P2 = ReleaseScope("us", "statute", "2026-07-28-p2")
R1 = ReleaseScope("us", "regulation", "2026-07-26-r1")
BR = ReleaseScope("us", "regulation", "2026-05-01", layer=LAYER_BASE)
BR_NEW = ReleaseScope("us", "regulation", "2026-11-01-cfr", layer=LAYER_BASE)
P1_BASE = ReleaseScope("us", "statute", "2026-07-26-p1", layer=LAYER_BASE)


def _new_key_pair() -> tuple[str, str]:
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


def _public_pem(public_key: str) -> str:
    # As tests/test_publish_corpus.py spells a key as PEM.
    loaded = Ed25519PublicKey.from_public_bytes(b64decode(public_key))
    return loaded.public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()


@pytest.fixture
def signing_keys() -> tuple[str, str]:
    return _new_key_pair()


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
                "expected_provision_projection_sha256": scope["provision_projection_sha256"],
                "actual_provision_projection_sha256": scope["provision_projection_sha256"],
                "expected_navigation_projection_sha256": scope["navigation_projection_sha256"],
                "actual_navigation_projection_sha256": scope["navigation_projection_sha256"],
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
    subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.com"], check=True)
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
                    "scopes": [scope.to_selector_mapping() for scope in scopes],
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
        signed = sign_release_object(build_unsigned_release_object(content), private_key=private)
        path = root / f"{name}.json"
        path.write_text(json.dumps(signed, indent=2, sort_keys=True) + "\n")
        return signed, path

    return root, public, make


def _results(
    release_repo,
    name: str,
    scopes: list[ReleaseScope],
    active: list[dict],
    *,
    allow_regression: bool = False,
):
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
        allow_regression=allow_regression,
    )
    return obj, path, results


def _by_name(results) -> dict[str, Any]:
    return {result.name: result for result in results}


def _install_active_manifest(root: Path, name: str, *scopes: ReleaseScope) -> None:
    path = root / "manifests" / "releases" / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"name": name, "scopes": [scope.to_selector_mapping() for scope in scopes]})
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


def _rewrite_plan_scopes(root: Path, name: str, scopes: list[dict[str, str]]) -> None:
    plan = root / "manifests" / "releases" / f"{name}.json"
    payload = json.loads(plan.read_text())
    payload["scopes"] = scopes
    plan.write_text(json.dumps(payload))


def _activate_without_state(release_repo, name: str, obj: dict[str, Any], path: Path):
    root, public, _ = release_repo
    return gate.run_gate(
        release_object_path=path,
        release=name,
        content_sha=obj["content_sha256"],
        repo_root=root,
        mode="activate",
        public_key=public,
        active_state_provider=lambda _obj: [],
    )


def test_provenance_passes_with_matching_base_layers(release_repo) -> None:
    obj, _, results = _results(release_repo, "us-layered-plan", [B, P1], [])
    assert obj["schema_version"] == "axiom-corpus/release-object/v4"
    assert {scope["version"]: scope.get("layer") for scope in obj["content"]["scopes"]} == {
        B.version: LAYER_BASE,
        P1.version: None,
    }
    by_name = _by_name(results)
    assert by_name["object_identity"].passed, by_name["object_identity"].evidence
    assert by_name["cut_plan_provenance"].passed, by_name["cut_plan_provenance"].evidence


@pytest.mark.parametrize("variant", ["object_base_plan_primary", "object_primary_plan_base"])
def test_provenance_fails_on_a_layer_flip(release_repo, variant: str) -> None:
    # The triples match, so only the layer comparison can see the flip.
    signed, planned = (B, B_PRIMARY) if variant == "object_base_plan_primary" else (B_PRIMARY, B)
    name = f"us-flip-{variant.replace('_', '-')}"
    obj, path = release_repo[2](name, [signed, P1])
    _rewrite_plan_scopes(
        release_repo[0], name, [planned.to_selector_mapping(), P1.to_selector_mapping()]
    )
    by_name = _by_name(_activate_without_state(release_repo, name, obj, path))
    assert by_name["object_identity"].passed, by_name["object_identity"].evidence
    result = by_name["cut_plan_provenance"]
    assert not result.passed
    assert result.evidence == (
        f"cut-plan layer mismatch (us/statute/2026-04-29: plan {planned.layer}, "
        f"object {signed.layer})"
    )


def test_provenance_refuses_an_explicit_primary_layer(release_repo) -> None:
    obj, path = release_repo[2]("us-explicit-primary", [B, P1])
    _rewrite_plan_scopes(
        release_repo[0],
        "us-explicit-primary",
        [B.to_selector_mapping(), {**P1.to_selector_mapping(), "layer": "primary"}],
    )
    results = _activate_without_state(release_repo, "us-explicit-primary", obj, path)
    result = _by_name(results)["cut_plan_provenance"]
    assert not result.passed
    assert "cannot validate cut plan" in result.evidence
    assert "scope layer must be 'base' or absent (primary): 'primary'" in result.evidence


def test_provenance_still_refuses_duplicate_triples(release_repo) -> None:
    # A plan that names one triple twice, once as a base, is not two scopes.
    obj, path = release_repo[2]("us-duplicate-triple", [B, P1])
    _rewrite_plan_scopes(
        release_repo[0],
        "us-duplicate-triple",
        [B_PRIMARY.to_selector_mapping(), B.to_selector_mapping(), P1.to_selector_mapping()],
    )
    results = _activate_without_state(release_repo, "us-duplicate-triple", obj, path)
    result = _by_name(results)["cut_plan_provenance"]
    assert not result.passed
    assert "cannot validate cut plan" in result.evidence
    assert "duplicate scope triple: ('us', 'statute', '2026-04-29')" in result.evidence


def test_older_release_vs_active_fails_incident_replay(release_repo) -> None:
    scope = ReleaseScope("uk", "manual", "2026-07-24-council")
    root, public, make = release_repo
    obj, path = make("uk-older", [scope])
    _install_active_manifest(root, "uk-active", ReleaseScope("uk", "manual", "2026-07-26-council"))
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
        release="uk-older",
        content_sha=obj["content_sha256"],
        repo_root=root,
        mode="activate",
        public_key=public,
        active_state_provider=lambda _obj: active,
    )
    by_name = _by_name(results)
    assert not by_name["scope_monotonicity"].passed
    assert (
        "incoming frontier '2026-07-24-council' precedes active "
        "'2026-07-26-council' from 'uk-active'"
    ) in by_name["scope_monotonicity"].evidence
    assert by_name["no_orphan"].passed


def test_serving_state_rows_fail_preview_coverage(release_repo) -> None:
    scope = ReleaseScope("uk", "manual", "2026-07-24-council")
    serving_state = [
        {
            "jurisdiction": "uk",
            "document_class": "manual",
            "release_name": "uk-active",
            "version": "2026-07-26-council",
            "changes": False,
        }
    ]
    _, _, results = _results(release_repo, "uk-serving-state", [scope], serving_state)
    result = _by_name(results)["scope_monotonicity"]
    assert not result.passed
    assert "active-state preview schema violation" in result.evidence
    assert "missing incoming pair(s) [('uk', 'manual')]; refusing vacuous pass" in result.evidence


def test_empty_active_state_rows_fail_preview_coverage(release_repo) -> None:
    scope = ReleaseScope("uk", "manual", "2026-07-24-council")
    _, _, results = _results(release_repo, "uk-empty-preview", [scope], [])
    result = _by_name(results)["scope_monotonicity"]
    assert not result.passed
    assert result.evidence == (
        "active-state preview cannot support scope_monotonicity: "
        "missing incoming pair(s) [('uk', 'manual')]; refusing vacuous pass"
    )


@pytest.mark.parametrize(
    "row",
    [
        {
            "jurisdiction": "uk",
            "document_class": "manual",
        },
        {
            "jurisdiction": "uk",
            "document_class": "manual",
            "changes": "true",
        },
        {
            "jurisdiction": "uk",
            "document_class": "manual",
            "changes": True,
            "current_versions": ["2026-07-26-council"],
        },
        {
            "jurisdiction": "uk",
            "document_class": "manual",
            "changes": True,
            "current_release_name": "uk-active",
        },
    ],
)
@pytest.mark.parametrize("allow_regression", [False, True])
def test_malformed_preview_rows_fail_schema_validation(
    release_repo, row: dict[str, Any], allow_regression: bool
) -> None:
    scope = ReleaseScope("uk", "manual", "2026-07-24-council")
    _, _, results = _results(
        release_repo,
        "uk-malformed-preview",
        [scope],
        [row],
        allow_regression=allow_regression,
    )
    result = _by_name(results)["scope_monotonicity"]
    assert not result.passed
    assert not result.warning
    assert "active-state preview schema violation" in result.evidence
    assert "refusing vacuous pass" in result.evidence


def test_nonincoming_malformed_preview_rows_are_skipped(release_repo) -> None:
    scope = ReleaseScope("uk", "manual", "2026-07-24-council")
    active = [
        {
            "jurisdiction": "uk",
            "document_class": "manual",
            "changes": False,
            "current_release_name": "uk-skip-extra",
        },
        {
            "jurisdiction": "extra",
            "document_class": "manual",
        },
    ]
    _, _, results = _results(release_repo, "uk-skip-extra", [scope], active)
    assert _by_name(results)["scope_monotonicity"].passed


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
    assert "identical version evidence" in result.evidence


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
    root, public, make = release_repo
    shared = ReleaseScope("uk", "manual", "2026-07-26-council")
    scopes = [
        shared,
        ReleaseScope("uk-new", "manual", "2026-07-26-council"),
    ]
    obj, path = make("uk-superset", scopes, created_at="2026-07-26T01:00:00Z")
    _install_active_manifest(root, "uk-active", shared)
    active = [
        {
            "jurisdiction": "uk",
            "document_class": "manual",
            "changes": True,
            "current_release_name": "uk-active",
            "current_versions": [shared.version],
            "current_base_version": None,
            "incoming_published_at": "2026-07-26T01:00:00Z",
            "current_published_at": "2026-07-26T00:00:00Z",
        },
        {
            "jurisdiction": "uk-new",
            "document_class": "manual",
            "changes": True,
            "current_release_name": None,
            "current_versions": [],
        },
    ]
    results = gate.run_gate(
        release_object_path=path,
        release="uk-superset",
        content_sha=obj["content_sha256"],
        repo_root=root,
        mode="activate",
        public_key=public,
        active_state_provider=lambda _obj: active,
    )
    assert all(result.passed for result in results), [
        (result.name, result.evidence) for result in results
    ]


def test_identical_version_sets_pass_without_parsing(release_repo) -> None:
    # Grandfathered version keys (us-ky form 2026-740-es) do not parse as
    # YYYY-MM-DD-…; when the incoming release carries the identical
    # version evidence, monotonicity holds by identity and only the
    # publication-recency requirement applies.
    scope = ReleaseScope("us-ky", "form", "2026-740-es")
    active = [
        {
            "jurisdiction": "us-ky",
            "document_class": "form",
            "changes": True,
            "current_release_name": "us-active",
            "current_versions": ["2026-740-es"],
            "current_published_at": "2026-08-10T00:00:00Z",
            "incoming_published_at": "2026-08-23T00:00:00Z",
        }
    ]
    _, _, results = _results(release_repo, "us-identical", [scope], active, allow_regression=False)
    result = _by_name(results)["scope_monotonicity"]
    assert result.passed, result.evidence


def test_identical_version_sets_still_require_publication_recency(
    release_repo,
) -> None:
    scope = ReleaseScope("us-ky", "form", "2026-740-es")
    active = [
        {
            "jurisdiction": "us-ky",
            "document_class": "form",
            "changes": True,
            "current_release_name": "us-active",
            "current_versions": ["2026-740-es"],
            "current_published_at": "2026-08-23T00:00:00Z",
            "incoming_published_at": "2026-08-10T00:00:00Z",
        }
    ]
    _, _, results = _results(release_repo, "us-replay", [scope], active, allow_regression=False)
    result = _by_name(results)["scope_monotonicity"]
    assert not result.passed
    assert "identical version evidence" in result.evidence


def _kept_grandfathered_row(current_versions, *, incoming_at, current_at):
    return {
        "jurisdiction": "us-ky",
        "document_class": "form",
        "changes": True,
        "current_release_name": "us-active",
        "current_versions": current_versions,
        "current_published_at": current_at,
        "incoming_published_at": incoming_at,
    }


def test_kept_grandfathered_version_with_an_added_version_passes(release_repo) -> None:
    # The wave-6 union keeps us-ky form 2026-740-es and adds a dated forms
    # scope: the kept key needs no ordering proof, so nothing moves back.
    scopes = [
        ReleaseScope("us-ky", "form", "2026-740-es"),
        ReleaseScope("us-ky", "form", "2026-10-06-w6-income-tax-forms-ky"),
    ]
    active = [
        _kept_grandfathered_row(
            ["2026-740-es"],
            incoming_at="2026-10-07T23:22:00Z",
            current_at="2026-09-25T17:00:00Z",
        )
    ]
    _, _, results = _results(release_repo, "us-added", scopes, active, allow_regression=False)
    result = _by_name(results)["scope_monotonicity"]
    assert result.passed, result.evidence


def test_kept_grandfathered_version_still_requires_publication_recency(release_repo) -> None:
    scopes = [
        ReleaseScope("us-ky", "form", "2026-740-es"),
        ReleaseScope("us-ky", "form", "2026-10-06-w6-income-tax-forms-ky"),
    ]
    active = [
        _kept_grandfathered_row(
            ["2026-740-es"],
            incoming_at="2026-09-01T00:00:00Z",
            current_at="2026-09-25T17:00:00Z",
        )
    ]
    _, _, results = _results(release_repo, "us-replay-added", scopes, active)
    result = _by_name(results)["scope_monotonicity"]
    assert not result.passed
    assert "keeps the active versions ['2026-740-es'] and adds others" in result.evidence


def test_kept_grandfathered_version_orders_the_versions_that_differ(release_repo) -> None:
    kept = ReleaseScope("us-ky", "form", "2026-740-es")
    newer = ReleaseScope("us-ky", "form", "2026-10-06-w6-income-tax-forms-ky")
    older = ReleaseScope("us-ky", "form", "2026-08-01-income-tax-forms-ky")
    active = [
        _kept_grandfathered_row(
            ["2026-740-es", "2026-09-01-income-tax-forms-ky"],
            incoming_at="2026-10-07T23:22:00Z",
            current_at="2026-09-25T17:00:00Z",
        )
    ]
    _, _, ahead = _results(release_repo, "us-ahead", [kept, newer], active)
    assert _by_name(ahead)["scope_monotonicity"].passed
    _, _, behind = _results(release_repo, "us-behind", [kept, older], active)
    result = _by_name(behind)["scope_monotonicity"]
    assert not result.passed
    assert "incoming frontier '2026-08-01-income-tax-forms-ky' precedes" in result.evidence


def test_kept_grandfathered_version_alone_cannot_drop_ordered_versions(release_repo) -> None:
    active = [
        _kept_grandfathered_row(
            ["2026-740-es", "2026-09-01-income-tax-forms-ky"],
            incoming_at="2026-10-07T23:22:00Z",
            current_at="2026-09-25T17:00:00Z",
        )
    ]
    _, _, results = _results(
        release_repo,
        "us-dropped",
        [ReleaseScope("us-ky", "form", "2026-740-es")],
        active,
        allow_regression=True,
    )
    result = _by_name(results)["scope_monotonicity"]
    assert not result.passed
    assert not result.warning
    assert "no ordering proof is possible" in result.evidence


def test_new_malformed_version_beside_a_kept_one_fails(release_repo) -> None:
    scopes = [
        ReleaseScope("us-ky", "form", "2026-740-es"),
        ReleaseScope("us-ky", "form", "2026-740-es-revised"),
    ]
    active = [
        _kept_grandfathered_row(
            ["2026-740-es"],
            incoming_at="2026-10-07T23:22:00Z",
            current_at="2026-09-25T17:00:00Z",
        )
    ]
    _, _, results = _results(
        release_repo, "us-new-malformed", scopes, active, allow_regression=True
    )
    result = _by_name(results)["scope_monotonicity"]
    assert not result.passed
    assert "malformed version key '2026-740-es-revised'" in result.evidence


def test_allow_regression_malformed_version_still_fails(release_repo) -> None:
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
    _, _, results = _results(release_repo, "uk-malformed", [scope], active, allow_regression=True)
    result = _by_name(results)["scope_monotonicity"]
    assert not result.passed
    assert not result.warning
    assert "malformed version key" in result.evidence


def test_allow_regression_missing_timestamp_still_fails(release_repo) -> None:
    scope = ReleaseScope("uk", "manual", "2026-07-26-council")
    active = [
        {
            "jurisdiction": "uk",
            "document_class": "manual",
            "changes": True,
            "current_release_name": "uk-active",
            "current_versions": [scope.version],
            "current_published_at": "2026-07-26T00:00:00Z",
        }
    ]
    _, _, results = _results(
        release_repo, "uk-missing-timestamp", [scope], active, allow_regression=True
    )
    result = _by_name(results)["scope_monotonicity"]
    assert not result.passed
    assert not result.warning
    assert "incoming database publication timestamp is missing" in result.evidence


def test_proven_ordering_regression_with_flag_warns_and_acknowledges(
    release_repo, capsys, monkeypatch
) -> None:
    scope = ReleaseScope("uk", "manual", "2026-07-24-council")
    root, public, make = release_repo
    obj, path = make("uk-ack", [scope], created_at="2026-07-24T00:00:00Z")
    _install_active_manifest(root, "uk-active", ReleaseScope("uk", "manual", "2026-07-26-council"))
    active = [
        {
            "jurisdiction": "uk",
            "document_class": "manual",
            "changes": True,
            "current_release_name": "uk-active",
            "current_versions": ["2026-07-26-council"],
            "current_base_version": None,
            "current_published_at": "2026-07-26T00:00:00Z",
        }
    ]
    active_path = root / "active-state.json"
    active_path.write_text(json.dumps(active))
    monkeypatch.setenv("AXIOM_CORPUS_RELEASE_PUBLIC_KEY", public)
    exit_code = gate.main(
        [
            "--release-object",
            str(path),
            "--release",
            "uk-ack",
            "--content-sha",
            obj["content_sha256"],
            "--repo-root",
            str(root),
            "--mode",
            "activate",
            "--active-state-file",
            str(active_path),
            "--allow-regression",
        ]
    )
    output = capsys.readouterr().out
    assert exit_code == 0
    assert "| scope_monotonicity | WARN |" in output
    assert "RELEASE_GATE_REGRESSION_ACKNOWLEDGED=uk-ack" in output


def test_proven_ordering_regression_without_flag_fails(release_repo) -> None:
    scope = ReleaseScope("uk", "manual", "2026-07-24-council")
    active = [
        {
            "jurisdiction": "uk",
            "document_class": "manual",
            "changes": True,
            "current_release_name": "uk-active",
            "current_versions": ["2026-07-26-council"],
            "incoming_published_at": "2026-07-24T00:00:00Z",
            "current_published_at": "2026-07-26T00:00:00Z",
        }
    ]
    _, _, results = _results(release_repo, "uk-regression", [scope], active)
    result = _by_name(results)["scope_monotonicity"]
    assert not result.passed
    assert not result.warning
    assert "incoming frontier" in result.evidence


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


def test_mirror_provenance_compares_layers(release_repo) -> None:
    root, public, make = release_repo
    obj, path = make("us-layered-mirror", [B, P1])
    _rewrite_plan_scopes(
        root, "us-layered-mirror", [B_PRIMARY.to_selector_mapping(), P1.to_selector_mapping()]
    )
    artifact = root / "publish-artifact.json"
    artifact.write_bytes(path.read_bytes())
    results = gate.run_gate(
        release_object_path=path,
        release="us-layered-mirror",
        content_sha=obj["content_sha256"],
        repo_root=root,
        mode="mirror",
        public_key=public,
        published_artifact=artifact,
        destination_path=f"releases/us-layered-mirror/{obj['content_sha256']}.json",
    )
    assert [result.name for result in results] == [
        "object_identity",
        "cut_plan_provenance",
        "mirror_artifact_path",
    ]
    by_name = _by_name(results)
    assert by_name["object_identity"].passed, by_name["object_identity"].evidence
    assert by_name["mirror_artifact_path"].passed, by_name["mirror_artifact_path"].evidence
    result = by_name["cut_plan_provenance"]
    assert not result.passed
    assert result.evidence == (
        "cut-plan layer mismatch (us/statute/2026-04-29: plan primary, object base)"
    )


# The Supabase provider, fed as data: every test patches both network calls and
# the direct database preview before it builds the provider, with a dummy token.
_INCOMING = {"release": "us-incoming", "content_sha256": "a" * 64}


def _stored_scope(scope: ReleaseScope) -> dict[str, Any]:
    return {**scope.to_selector_mapping(), "provision_rows": 1, "navigation_rows": 1}


def _stored_detail(
    name: str,
    scopes: object,
    *,
    schema_version: str = RELEASE_OBJECT_SCHEMA_V4,
    content_sha256: str | None = None,
) -> dict[str, Any]:
    return {
        "release_name": name,
        "content_sha256": content_sha256 or f"{name}-sha",
        "published_at": "2026-07-26T00:00:00Z",
        "release_object": {
            "schema_version": schema_version,
            "release": name,
            "content": {"scopes": scopes},
        },
    }


def _incoming_detail() -> dict[str, Any]:
    # Its bases differ from every active object's, so a provider that read the
    # incoming release's base map would report the wrong current_base_version.
    return _stored_detail(
        "us-incoming",
        [_stored_scope(B_NEW), _stored_scope(P2), _stored_scope(BR)],
        content_sha256=_INCOMING["content_sha256"],
    )


def _changed_row(pair: tuple[str, str], release: str, sha: str | None = None) -> dict[str, Any]:
    return {
        "jurisdiction": pair[0],
        "document_class": pair[1],
        "changes": True,
        "current_release_name": release,
        "current_content_sha256": f"{release}-sha" if sha is None else sha,
    }


def _signed_detail(
    obj: dict[str, Any],
    *,
    published_at: str,
    release_name: str | None = None,
    content_sha256: str | None = None,
) -> dict[str, Any]:
    """A stored row for a release object, under the object's own name and digest."""
    return {
        "release_name": obj["release"] if release_name is None else release_name,
        "content_sha256": obj["content_sha256"] if content_sha256 is None else content_sha256,
        "published_at": published_at,
        "release_object": obj,
    }


def _fake_supabase_provider(
    monkeypatch,
    rows: list[dict[str, Any]],
    details: list[dict[str, Any]],
    queries: list[dict[str, Any]],
    *,
    public_key: str = "unused-public-key",
    legacy_public_keys: tuple[str, ...] = (),
):
    monkeypatch.setenv(gate.DEFAULT_ACCESS_TOKEN_ENV, "test-token")
    monkeypatch.delenv(gate.DEFAULT_DATABASE_URL_ENV, raising=False)

    def no_direct_preview(*_args: object, **_kwargs: object) -> list[dict[str, Any]]:
        raise AssertionError("the direct database preview must not run")

    def preview(_release_object: object, **_kwargs: object) -> list[dict[str, Any]]:
        return rows

    def post(_url: str, **kwargs: Any) -> list[dict[str, Any]]:
        queries.append(kwargs)
        return details

    monkeypatch.setattr(gate, "preview_corpus_release_activation_direct", no_direct_preview)
    monkeypatch.setattr(gate, "preview_corpus_release_activation", preview)
    monkeypatch.setattr(gate, "_management_api_post_json_with_curl", post)
    return gate._supabase_active_state_provider(
        Namespace(supabase_url="https://abcdefghijklmnop.supabase.co", expected_project_ref=None),
        public_key,
        legacy_public_keys=legacy_public_keys,
    )


def test_supabase_provider_records_current_base_version(release_repo, monkeypatch) -> None:
    _, public, make = release_repo
    layered, _ = make("us-layered", [B, P1])
    plain, _ = make("us-plain", [R1])
    # Its bases differ from every active object's, so a provider that read the
    # incoming release's base map would report the wrong current_base_version.
    incoming, _ = make("us-incoming", [B_NEW, P2, BR])
    assert layered["schema_version"] == RELEASE_OBJECT_SCHEMA_V4
    assert plain["schema_version"] == RELEASE_OBJECT_SCHEMA_V3
    rows = [
        _changed_row(("us", "statute"), "us-layered", layered["content_sha256"]),
        _changed_row(("us", "regulation"), "us-plain", plain["content_sha256"]),
        # The active object carries no version of this pair, so no base is recorded.
        _changed_row(("us", "rulings"), "us-layered", layered["content_sha256"]),
    ]
    details = [
        _signed_detail(incoming, published_at=_LATER),
        _signed_detail(layered, published_at=_EARLIER),
        _signed_detail(plain, published_at=_EARLIER),
    ]
    queries: list[dict[str, Any]] = []
    provide = _fake_supabase_provider(monkeypatch, rows, details, queries, public_key=public)

    by_pair = {(row["jurisdiction"], row["document_class"]): row for row in provide(incoming)}

    statute = by_pair["us", "statute"]
    assert statute["current_base_version"] == "2026-04-29"
    assert statute["current_versions"] == ["2026-04-29", "2026-07-26-p1"]
    regulation = by_pair["us", "regulation"]
    assert "current_base_version" in regulation
    assert regulation["current_base_version"] is None
    assert regulation["current_versions"] == ["2026-07-26-r1"]
    rulings = by_pair["us", "rulings"]
    assert "current_base_version" not in rulings
    assert rulings["current_versions"] == []
    assert len(queries) == 1
    assert queries[0]["access_token"] == "test-token"
    assert queries[0]["payload"]["read_only"] is True
    assert queries[0]["payload"]["parameters"][0] == [
        "us-incoming",
        "us-layered",
        "us-plain",
    ]


@pytest.mark.parametrize(
    ("release_object", "message"),
    [
        pytest.param(
            "not an object",
            "stored release object of 'us-active' is not a JSON object with a content object",
            id="non_object",
        ),
        pytest.param(
            {"schema_version": RELEASE_OBJECT_SCHEMA_V4, "content": ["not", "an", "object"]},
            "stored release object of 'us-active' is not a JSON object with a content object",
            id="non_object_content",
        ),
        pytest.param(
            {
                "schema_version": RELEASE_OBJECT_SCHEMA_V3,
                "content": {"scopes": [_stored_scope(B), _stored_scope(P1)]},
            },
            "only release-object/v4 may sign scope layers",
            id="layer_on_v3",
        ),
        pytest.param(
            {
                "schema_version": RELEASE_OBJECT_SCHEMA_V2,
                "content": {"scopes": [_stored_scope(B), _stored_scope(P1)]},
            },
            "only release-object/v4 may sign scope layers",
            id="layer_on_v2",
        ),
        pytest.param(
            {
                "schema_version": RELEASE_OBJECT_SCHEMA_V4,
                "content": {"scopes": [_stored_scope(B), _stored_scope(B_NEW)]},
            },
            "more than one base scope for us/statute",
            id="two_bases",
        ),
        pytest.param(
            {
                "schema_version": RELEASE_OBJECT_SCHEMA_V4,
                "content": {"scopes": [{**_stored_scope(P1), "layer": "overlay"}]},
            },
            "scope us/statute/2026-07-26-p1 has an unsupported layer: 'overlay'",
            id="unknown_layer",
        ),
        pytest.param(
            {
                "schema_version": RELEASE_OBJECT_SCHEMA_V4,
                "content": {"scopes": [{**_stored_scope(P1), "layer": "primary"}]},
            },
            "scope us/statute/2026-07-26-p1 has an unsupported layer: 'primary'",
            id="explicit_primary_layer",
        ),
        pytest.param(
            {"schema_version": RELEASE_OBJECT_SCHEMA_V4, "content": {"scopes": _stored_scope(P1)}},
            "scopes must be a JSON array",
            id="non_list_scopes",
        ),
        pytest.param(
            {
                "schema_version": RELEASE_OBJECT_SCHEMA_V4,
                "content": {"scopes": [_stored_scope(B), _stored_scope(B_PRIMARY)]},
            },
            "duplicate scope triple: ('us', 'statute', '2026-04-29')",
            id="duplicate_triple",
        ),
    ],
)
def test_supabase_provider_refuses_malformed_active_objects(
    monkeypatch, release_object: object, message: str
) -> None:
    active = _stored_detail("us-active", [])
    active["release_object"] = release_object
    provide = _fake_supabase_provider(
        monkeypatch,
        [_changed_row(("us", "statute"), "us-active")],
        [_incoming_detail(), active],
        [],
    )
    with pytest.raises(ValueError, match=re.escape(message)):
        provide(_INCOMING)


# Activation's base_carry_forward check, fed preview rows as data. A row carries
# current_base_version only where the provider read the active object.
_STATUTE = ("us", "statute")
_REGULATION = ("us", "regulation")
_UNSET: Any = object()
_EARLIER = "2026-07-27T00:00:00Z"
_LATER = "2026-07-29T00:00:00Z"
_LATEST = "2026-07-30T00:00:00Z"
_ACTIVATE_NAMES = [
    "object_identity",
    "cut_plan_provenance",
    "scope_monotonicity",
    "no_orphan",
    "base_carry_forward",
    "base_only_pair",
    "primary_frontier",
]


def _layered_row(
    pair: tuple[str, str],
    current_versions: list[Any],
    base: Any = _UNSET,
    *,
    release: str = "us-active",
    incoming_at: str = _LATER,
    current_at: str = _EARLIER,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "jurisdiction": pair[0],
        "document_class": pair[1],
        "changes": True,
        "current_release_name": release,
        "current_versions": current_versions,
        "incoming_published_at": incoming_at,
        "current_published_at": current_at,
    }
    if base is not _UNSET:
        row["current_base_version"] = base
    return row


def _write_lineage_baseline(
    root: Path,
    *,
    selector: str,
    predecessor: str,
    pair: tuple[str, str],
    replaced: str,
    replaced_by: ReleaseScope,
    digest: str,
) -> Path:
    # The gate reads only the incoming selector's pin; the loader still needs both.
    # Quoted, because YAML reads an all-digit digest as a number.
    digests = {selector: digest, predecessor: "f" * 64}
    lines = [
        "schema_version: axiom-corpus/selector-lineage-baseline/v1",
        "selector_digests:",
        *(f'  {name}: "{digests[name]}"' for name in sorted(digests)),
        "base_replacements:",
        f"  - selector: {selector}",
        f"    predecessor: {predecessor}",
        f"    pair: {'/'.join(pair)}",
        f'    replaced: "{replaced}"',
        f"    replaced_by: {'/'.join(replaced_by.key)}",
        "    listed_on: 2026-11-18",
        "    reason: A reviewed replacement of the May base.",
    ]
    path = root / "manifests" / "selector-lineage-baseline.yaml"
    path.write_text("\n".join(lines) + "\n")
    return path


def _activate(
    release_repo,
    name: str,
    obj: dict[str, Any],
    path: Path,
    rows: list[dict[str, Any]],
    *,
    allow_regression: bool = False,
):
    root, public, _ = release_repo
    return gate.run_gate(
        release_object_path=path,
        release=name,
        content_sha=obj["content_sha256"],
        repo_root=root,
        mode="activate",
        public_key=public,
        active_state_provider=lambda _obj: rows,
        allow_regression=allow_regression,
    )


def _evidence(results) -> list[tuple[str, bool, str]]:
    return [(result.name, result.passed, result.evidence) for result in results]


def _stop_serving(incoming: str, selects: str, current: str = "us-active") -> str:
    return (
        f"us/statute: activation would stop serving base us/statute/2026-04-29 of "
        f"{current!r}; {incoming} selects {selects} for us/statute. Carry the base "
        "unchanged, or record the replacement under base_replacements in "
        f"manifests/selector-lineage-baseline.yaml for {incoming}"
    )


def test_ordinary_later_cut_passes_every_check(release_repo) -> None:
    _install_active_manifest(release_repo[0], "us-restore", B, P1)
    rows = [_layered_row(_STATUTE, [B.version, P1.version], B.version, release="us-restore")]
    _, _, results = _results(release_repo, "us-later", [B, P1, P2], rows)
    assert [result.name for result in results] == _ACTIVATE_NAMES
    assert all(result.passed and not result.warning for result in results), _evidence(results)
    assert _by_name(results)["base_carry_forward"].evidence == (
        "1 incoming pair(s): 1 displace an active base; 1 carry it unchanged and 0 replace "
        "it under a recorded base_replacements entry"
    )


def _restore_rows(*, incoming_at: str, current_at: str) -> list[dict[str, Any]]:
    times = {"release": "us-head", "incoming_at": incoming_at, "current_at": current_at}
    return [
        _layered_row(_STATUTE, [P1.version, P2.version], None, **times),
        _layered_row(_REGULATION, [R1.version], None, **times),
    ]


def test_restore_composite_passes_every_check(release_repo) -> None:
    # The head serves primaries only; the restore adds both May bases beneath them.
    _install_active_manifest(release_repo[0], "us-head", P1, P2, R1)
    rows = _restore_rows(incoming_at=_LATER, current_at=_EARLIER)
    _, _, results = _results(release_repo, "us-restore", [P1, P2, B, R1, BR], rows)
    assert [result.name for result in results] == _ACTIVATE_NAMES
    assert all(result.passed and not result.warning for result in results), _evidence(results)
    by_name = _by_name(results)
    assert "2 displaced pair(s) are version/publication monotone" in (
        by_name["scope_monotonicity"].evidence
    )
    assert by_name["base_carry_forward"].evidence == (
        "2 incoming pair(s): 0 displace an active base; 0 carry it unchanged and 0 replace "
        "it under a recorded base_replacements entry"
    )


def test_restore_tie_branch_still_requires_publication_recency(release_repo) -> None:
    # The bases are older than every primary, so the frontiers tie and only the
    # publication order can prove the restore is not a replay.
    _install_active_manifest(release_repo[0], "us-head", P1, P2, R1)
    rows = _restore_rows(incoming_at=_EARLIER, current_at=_LATER)
    _, _, results = _results(release_repo, "us-restore", [P1, P2, B, R1, BR], rows)
    by_name = _by_name(results)
    monotonicity = by_name["scope_monotonicity"]
    assert not monotonicity.passed
    assert "('us', 'statute'): versions tie at '2026-07-28-p2'" in monotonicity.evidence
    assert "('us', 'regulation'): versions tie at '2026-07-26-r1'" in monotonicity.evidence
    assert by_name["base_carry_forward"].passed, by_name["base_carry_forward"].evidence


@pytest.mark.parametrize("allow_regression", [False, True])
def test_omitted_base_is_the_only_failure(release_repo, allow_regression: bool) -> None:
    _install_active_manifest(release_repo[0], "us-active", B, P1)
    rows = [_layered_row(_STATUTE, [B.version, P1.version], B.version)]
    _, _, results = _results(
        release_repo, "us-omitted", [P1, P2], rows, allow_regression=allow_regression
    )
    assert [result.name for result in results] == _ACTIVATE_NAMES
    result = _by_name(results)["base_carry_forward"]
    assert (result.passed, result.warning) == (False, False)
    # One exact string under both flag values: the flag does not reach this check.
    assert result.evidence == _stop_serving("us-omitted", "no base")
    assert "activation would stop serving base us/statute/2026-04-29" in result.evidence
    others = [item for item in results if item.name != "base_carry_forward"]
    assert all(item.passed and not item.warning for item in others), _evidence(others)


def test_base_carried_as_primary_fails(release_repo) -> None:
    _install_active_manifest(release_repo[0], "us-active", B, P1)
    rows = [_layered_row(_STATUTE, [B.version, P1.version], B.version)]
    _, _, results = _results(release_repo, "us-as-primary", [B_PRIMARY, P1], rows)
    by_name = _by_name(results)
    # The same versions on both sides take monotonicity's identical branch.
    assert by_name["scope_monotonicity"].passed, by_name["scope_monotonicity"].evidence
    result = by_name["base_carry_forward"]
    assert not result.passed
    assert result.evidence == _stop_serving("us-as-primary", "no base")


@pytest.mark.parametrize(
    "variant",
    ["none", "matching", "wrong_replaced", "wrong_replaced_by", "stale_pin", "no_incoming_base"],
)
def test_base_replacement_needs_a_recorded_entry(release_repo, variant: str) -> None:
    root, _, make = release_repo
    _install_active_manifest(root, "us-restore", B, P1)
    # no_incoming_base: the record names the active base and the pin, but the cut
    # selects no base, so the record cannot match what the cut serves.
    scopes = [P1, P2] if variant == "no_incoming_base" else [B_NEW, P1]
    obj, path = make("us-restore-next", scopes)
    signed = obj["content"]["selector_sha256"]
    other_base = ReleaseScope("us", "statute", "2026-11-02-us-code", layer=LAYER_BASE)
    if variant != "none":
        _write_lineage_baseline(
            root,
            selector="us-restore-next",
            predecessor="us-restore",
            pair=_STATUTE,
            replaced="2026-04-30" if variant == "wrong_replaced" else B.version,
            replaced_by=other_base if variant == "wrong_replaced_by" else B_NEW,
            digest="0" * 64 if variant == "stale_pin" else signed,
        )
    rows = [_layered_row(_STATUTE, [B.version, P1.version], B.version, release="us-restore")]
    results = _activate(release_repo, "us-restore-next", obj, path, rows)
    result = _by_name(results)["base_carry_forward"]
    if variant == "matching":
        assert result.passed, result.evidence
        assert result.evidence == (
            "1 incoming pair(s): 1 displace an active base; 0 carry it unchanged and 1 "
            "replace it under a recorded base_replacements entry"
        )
        return
    suffix = {
        "none": "",
        "wrong_replaced": " (the recorded replacement differs: replaced '2026-04-30' is not "
        "the active base '2026-04-29')",
        "wrong_replaced_by": " (the recorded replacement differs: replaced_by "
        "'us/statute/2026-11-02-us-code' is not the incoming base "
        "(us/statute/2026-11-01-us-code))",
        "stale_pin": " (the recorded replacement differs: the selector_digests pin "
        f"'{'0' * 64}' is not the signed selector_sha256 '{signed}')",
        "no_incoming_base": " (the recorded replacement differs: replaced_by "
        "'us/statute/2026-11-01-us-code' is not the incoming base (no base))",
    }[variant]
    selects = "no base" if variant == "no_incoming_base" else "base us/statute/2026-11-01-us-code"
    assert not result.passed
    assert result.evidence == (
        _stop_serving("us-restore-next", selects, current="us-restore") + suffix
    )


def test_a_replacement_recorded_for_another_cut_does_not_clear_this_one(release_repo) -> None:
    # The replacement sits on an intermediate cut that was never activated. The
    # incoming cut is pinned at its signed digest, but no record names it for the pair.
    root, _, make = release_repo
    _install_active_manifest(root, "us-restore", B, P1)
    obj, path = make("us-restore-next", [B_NEW, P1])
    (root / "manifests" / "selector-lineage-baseline.yaml").write_text(
        "schema_version: axiom-corpus/selector-lineage-baseline/v1\n"
        "selector_digests:\n"
        f'  us-restore: "{"f" * 64}"\n'
        f'  us-restore-mid: "{"e" * 64}"\n'
        f'  us-restore-next: "{obj["content"]["selector_sha256"]}"\n'
        "base_replacements:\n"
        "  - selector: us-restore-mid\n"
        "    predecessor: us-restore\n"
        "    pair: us/statute\n"
        '    replaced: "2026-04-29"\n'
        "    replaced_by: us/statute/2026-11-01-us-code\n"
        "    listed_on: 2026-11-18\n"
        "    reason: The intermediate cut replaces the May base.\n"
        "  - selector: us-restore-next\n"
        "    predecessor: us-restore-mid\n"
        "    pair: us/regulation\n"
        '    replaced: "2026-05-01"\n'
        "    replaced_by: us/regulation/2026-11-01-cfr\n"
        "    listed_on: 2026-11-18\n"
        "    reason: The later cut replaces the regulation base.\n"
    )
    rows = [_layered_row(_STATUTE, [B.version, P1.version], B.version, release="us-restore")]
    results = _activate(release_repo, "us-restore-next", obj, path, rows)
    result = _by_name(results)["base_carry_forward"]
    assert not result.passed
    assert result.evidence == _stop_serving(
        "us-restore-next", "base us/statute/2026-11-01-us-code", current="us-restore"
    )


def test_a_replacement_cannot_clear_a_replaced_base_kept_as_primary(release_repo) -> None:
    # The cut records the May base's replacement but still selects the May version,
    # as a primary scope. A record holds only while the cut no longer selects the
    # replaced version in either layer, as the lineage check's rule says.
    root, _, make = release_repo
    _install_active_manifest(root, "us-restore", B, P1)
    obj, path = make("us-restore-next", [B_PRIMARY, B_NEW, P1])
    _write_lineage_baseline(
        root,
        selector="us-restore-next",
        predecessor="us-restore",
        pair=_STATUTE,
        replaced=B.version,
        replaced_by=B_NEW,
        digest=obj["content"]["selector_sha256"],
    )
    rows = [_layered_row(_STATUTE, [B.version, P1.version], B.version, release="us-restore")]
    results = _activate(release_repo, "us-restore-next", obj, path, rows)
    assert [result.name for result in results] == _ACTIVATE_NAMES
    result = _by_name(results)["base_carry_forward"]
    assert (result.passed, result.warning) == (False, False)
    assert result.evidence == (
        _stop_serving("us-restore-next", "base us/statute/2026-11-01-us-code", current="us-restore")
        + " (the recorded replacement differs: us-restore-next still selects the replaced "
        "version us/statute/2026-04-29)"
    )
    # Monotonicity sees a superset whose frontier is the new base, and the cut keeps a
    # primary scope, so base_only_pair takes its early return.
    others = [item for item in results if item.name != "base_carry_forward"]
    assert all(item.passed and not item.warning for item in others), _evidence(others)


@pytest.mark.parametrize("allow_regression", [False, True])
def test_missing_current_base_version_fails_closed(release_repo, allow_regression: bool) -> None:
    _install_active_manifest(release_repo[0], "us-active", B, P1)
    rows = [_layered_row(_STATUTE, [B.version, P1.version])]
    _, _, results = _results(
        release_repo, "us-no-base-evidence", [B, P1, P2], rows, allow_regression=allow_regression
    )
    by_name = _by_name(results)
    assert by_name["scope_monotonicity"].passed, by_name["scope_monotonicity"].evidence
    result = by_name["base_carry_forward"]
    assert (result.passed, result.warning) == (False, False)
    assert result.evidence == "us/statute: active-state evidence lacks current_base_version"


_STATUTE_ROW = _layered_row(_STATUTE, [B.version, P1.version], B.version)


@pytest.mark.parametrize(
    ("rows", "message"),
    [
        pytest.param(
            [_layered_row(_STATUTE, [P1.version], B.version)],
            "us/statute: current_base_version '2026-04-29' is not among current_versions "
            "['2026-07-26-p1']",
            id="base_not_listed",
        ),
        pytest.param(
            [_layered_row(_STATUTE, [B.version, P1.version], 20260429)],
            "us/statute: current_base_version 20260429 is not among current_versions "
            "['2026-04-29', '2026-07-26-p1']",
            id="non_string_base",
        ),
        pytest.param(
            [_layered_row(_STATUTE, [], None)],
            "us/statute: active release 'us-active' has no version evidence",
            id="empty_versions",
        ),
        pytest.param(
            [_layered_row(_STATUTE, [B.version, 7], B.version)],
            "us/statute: active release 'us-active' has no version evidence",
            id="non_string_version",
        ),
        pytest.param(
            [{**_STATUTE_ROW, "changes": "true"}],
            "us/statute: changes must be present and boolean, not 'true'",
            id="non_bool_changes",
        ),
        pytest.param(
            [{key: value for key, value in _STATUTE_ROW.items() if key != "current_release_name"}],
            "us/statute: active-state evidence lacks current_release_name",
            id="missing_release_key",
        ),
        pytest.param(
            [{**_STATUTE_ROW, "current_release_name": ""}],
            "us/statute: current_release_name must be a non-empty string or null, not ''",
            id="empty_release_name",
        ),
        pytest.param(
            [{**_STATUTE_ROW, "current_release_name": 5}],
            "us/statute: current_release_name must be a non-empty string or null, not 5",
            id="non_string_release_name",
        ),
        pytest.param(
            [_STATUTE_ROW, _STATUTE_ROW],
            "us/statute: active-state preview has 2 row(s) for an incoming pair; "
            "refusing vacuous pass",
            id="duplicate_rows",
        ),
        pytest.param(
            [],
            "us/statute: active-state preview has 0 row(s) for an incoming pair; "
            "refusing vacuous pass",
            id="no_row",
        ),
    ],
)
def test_base_carry_forward_rejects_malformed_evidence(
    release_repo, rows: list[dict[str, Any]], message: str
) -> None:
    _, _, results = _results(release_repo, "us-malformed", [B, P1, P2], rows)
    result = _by_name(results)["base_carry_forward"]
    assert (result.passed, result.warning) == (False, False)
    assert result.evidence == message
    # primary_frontier reads the rows through the same rules.
    assert _by_name(results)["primary_frontier"].evidence == message


def test_unchanged_new_and_uncarried_pairs_are_not_checked(release_repo) -> None:
    # None of these rows carries current_base_version, and none needs it.
    rows = [
        {
            "jurisdiction": "us",
            "document_class": "statute",
            "changes": False,
            "current_release_name": "us-mixed",
        },
        {
            "jurisdiction": "us",
            "document_class": "regulation",
            "changes": True,
            "current_release_name": None,
            "current_versions": [],
        },
        {
            "jurisdiction": "us",
            "document_class": "guidance",
            "changes": True,
            "current_release_name": "us-other",
            "current_versions": ["2026-07-01-guidance"],
        },
    ]
    _, _, results = _results(release_repo, "us-mixed", [B, P1, R1], rows)
    result = _by_name(results)["base_carry_forward"]
    assert result.passed, result.evidence
    assert result.evidence == (
        "2 incoming pair(s): 0 displace an active base; 0 carry it unchanged and 0 replace "
        "it under a recorded base_replacements entry"
    )


@pytest.mark.parametrize("regulation", ["carried", "recorded", "no_active_base", "null_pointer"])
def test_a_later_pair_is_checked_after_an_earlier_pair_passes(
    release_repo, regulation: str
) -> None:
    # us/regulation sorts first and passes each way; us/statute still omits its base.
    root, _, make = release_repo
    obj, path = make("us-two-pairs", [BR_NEW if regulation == "recorded" else BR, R1, P1, P2])
    if regulation == "recorded":
        _write_lineage_baseline(
            root,
            selector="us-two-pairs",
            predecessor="us-active",
            pair=_REGULATION,
            replaced=BR.version,
            replaced_by=BR_NEW,
            digest=obj["content"]["selector_sha256"],
        )
    based_regulation = _layered_row(_REGULATION, [BR.version, R1.version], BR.version)
    regulation_row = {
        "carried": based_regulation,
        "recorded": based_regulation,
        "no_active_base": _layered_row(_REGULATION, [R1.version], None),
        "null_pointer": {
            "jurisdiction": "us",
            "document_class": "regulation",
            "changes": True,
            "current_release_name": None,
            "current_versions": [],
        },
    }[regulation]
    rows = [regulation_row, _layered_row(_STATUTE, [B.version, P1.version], B.version)]
    results = _activate(release_repo, "us-two-pairs", obj, path, rows)
    result = _by_name(results)["base_carry_forward"]
    assert (result.passed, result.warning) == (False, False)
    # The evidence names only us/statute, so us/regulation passed before it.
    assert result.evidence == _stop_serving("us-two-pairs", "no base")


def test_a_base_only_incoming_pair_is_checked(release_repo) -> None:
    # The cut selects only a fresh base for us/statute, whose active release serves
    # its base alone, and no record names the replacement.
    rows = [
        _layered_row(_REGULATION, [R1.version], None),
        _layered_row(_STATUTE, [B.version], B.version),
    ]
    _, _, results = _results(release_repo, "us-base-only", [B_NEW, R1], rows)
    result = _by_name(results)["base_carry_forward"]
    assert (result.passed, result.warning) == (False, False)
    assert result.evidence == _stop_serving("us-base-only", "base us/statute/2026-11-01-us-code")


def _primary_regression(
    label: str = "us/statute",
    incoming: str = P1.version,
    active: str = P2.version,
    current: str = "us-active",
) -> str:
    return (
        f"{label}: incoming primary frontier {incoming!r} precedes active primary frontier "
        f"{active!r} of {current!r}; neither side's base counts toward its frontier"
    )


def test_an_older_carried_base_cannot_hide_a_primary_regression(release_repo) -> None:
    _install_active_manifest(release_repo[0], "us-active", B, P2)
    rows = [_layered_row(_STATUTE, [B.version, P2.version], B.version)]
    _, _, results = _results(release_repo, "us-behind", [B, P1], rows)
    by_name = _by_name(results)
    monotonicity = by_name["scope_monotonicity"]
    assert not monotonicity.passed
    assert (
        "incoming frontier '2026-07-26-p1' precedes active '2026-07-28-p2'" in monotonicity.evidence
    )
    assert by_name["base_carry_forward"].passed, by_name["base_carry_forward"].evidence
    frontier = by_name["primary_frontier"]
    assert (frontier.passed, frontier.warning) == (False, False)
    assert frontier.evidence == _primary_regression()


def test_activate_results_are_named_once_in_order(release_repo) -> None:
    root, public, make = release_repo
    _install_active_manifest(root, "us-active", B, P1)
    obj, path = make("us-named", [B, P1, P2])
    rows = [_layered_row(_STATUTE, [B.version, P1.version], B.version)]
    results = _activate(release_repo, "us-named", obj, path, rows)
    assert [result.name for result in results] == _ACTIVATE_NAMES
    artifact = root / "publish-artifact.json"
    artifact.write_bytes(path.read_bytes())
    mirror = gate.run_gate(
        release_object_path=path,
        release="us-named",
        content_sha=obj["content_sha256"],
        repo_root=root,
        mode="mirror",
        public_key=public,
        published_artifact=artifact,
        destination_path=f"releases/us-named/{obj['content_sha256']}.json",
    )
    assert [result.name for result in mirror] == [
        "object_identity",
        "cut_plan_provenance",
        "mirror_artifact_path",
    ]


@pytest.mark.parametrize("failure", ["raises", "none"])
def test_provider_failure_fails_every_state_check(release_repo, failure: str) -> None:
    root, public, make = release_repo
    obj, path = make("us-no-state", [B, P1])

    def raising(_release_object: object) -> list[dict[str, Any]]:
        raise ValueError("boom")

    results = gate.run_gate(
        release_object_path=path,
        release="us-no-state",
        content_sha=obj["content_sha256"],
        repo_root=root,
        mode="activate",
        public_key=public,
        active_state_provider=raising if failure == "raises" else None,
    )
    assert [result.name for result in results] == _ACTIVATE_NAMES
    state = {result.name: result for result in results[2:]}
    assert not any(result.passed or result.warning for result in state.values())
    if failure == "raises":
        expected = {
            "scope_monotonicity": "active-state lookup failed: boom",
            "no_orphan": "active-state evidence unavailable",
            "base_carry_forward": "active-state evidence unavailable",
            "base_only_pair": "active-state evidence unavailable",
            "primary_frontier": "active-state evidence unavailable",
        }
    else:
        expected = dict.fromkeys(state, "active-state provider is missing")
    assert {name: result.evidence for name, result in state.items()} == expected


def _recorded_replacement(
    release_repo, shape: str
) -> tuple[dict[str, Any], Path, Path, list[dict[str, Any]]]:
    # Both shapes replace the May base under a recorded entry. primary_kept keeps P1
    # above the new base; base_only selects the new base alone over an active release
    # that serves its base alone, so base_only_pair reaches its per-pair loop.
    root, _, make = release_repo
    if shape == "primary_kept":
        _install_active_manifest(root, "us-restore", B, P1)
        obj, path = make("us-restore-next", [B_NEW, P1])
        current = [B.version, P1.version]
    else:
        _install_active_manifest(root, "us-restore", B)
        obj, path = make("us-restore-next", [B_NEW])
        current = [B.version]
    baseline = _write_lineage_baseline(
        root,
        selector="us-restore-next",
        predecessor="us-restore",
        pair=_STATUTE,
        replaced=B.version,
        replaced_by=B_NEW,
        digest=obj["content"]["selector_sha256"],
    )
    rows = [_layered_row(_STATUTE, current, B.version, release="us-restore")]
    return obj, path, baseline, rows


def _repeat_a_baseline_key(baseline: Path, variant: str, signed: str) -> str:
    """Repeat one key of the baseline, the copy that does not match the cut first.

    Read as its last copy, as YAML reads a repeated key, the baseline would still
    record the replacement. repeated_merge gives the recorded entry two empty merge
    keys, which PyYAML flattens away, so the entry reads as written. Returns the
    error the loader gives for the repeat.
    """
    text = baseline.read_text()
    pin = f'  us-restore-next: "{signed}"\n'
    replaced = f'    replaced: "{B.version}"\n'
    entries = text.split("base_replacements:\n", 1)[1]
    stale = "base_replacements:\n" + entries.replace(
        "us/statute/2026-11-01-us-code", "us/statute/2026-11-02-us-code"
    )
    schema, rest = text.split("\n", 1)
    key, edited = {
        "repeated_pin": (
            "us-restore-next",
            text.replace(pin, f'  us-restore-next: "{"0" * 64}"\n' + pin, 1),
        ),
        "repeated_section": ("base_replacements", f"{schema}\n{stale}{rest}"),
        "repeated_field": (
            "replaced",
            text.replace(replaced, '    replaced: "2026-04-30"\n' + replaced, 1),
        ),
        "repeated_merge": ("<<", text.replace(replaced, replaced + "    <<: {}\n    <<: {}\n", 1)),
    }[variant]
    copies = [
        number
        for number, line in enumerate(edited.splitlines(), 1)
        if re.match(rf"\s*{re.escape(key)}:", line)
    ]
    assert len(copies) == 2, copies
    baseline.write_text(edited)
    return (
        f"SelectorLineageError: {baseline}: line {copies[1]}: the key {key!r} repeats in one "
        "mapping"
    )


@pytest.mark.parametrize("shape", ["primary_kept", "base_only"])
@pytest.mark.parametrize(
    "variant",
    [
        "unknown_field",
        "yaml_syntax",
        "repeated_pin",
        "repeated_section",
        "repeated_field",
        "repeated_merge",
    ],
)
def test_malformed_lineage_baseline_fails_only_base_carry_forward(
    release_repo, variant: str, shape: str
) -> None:
    obj, path, baseline, rows = _recorded_replacement(release_repo, shape)
    if variant == "unknown_field":
        baseline.write_text(baseline.read_text() + "unreviewed_section: []\n")
        error = f"SelectorLineageError: {baseline}: unsupported fields ['unreviewed_section']"
    elif variant == "yaml_syntax":
        baseline.write_text(baseline.read_text() + "selector_digests: {unclosed\n")
        # A YAML error is not a ValueError, so only a broad guard contains it.
        with pytest.raises(yaml.YAMLError) as info:
            yaml.safe_load(baseline.read_text())
        assert not isinstance(info.value, ValueError)
        error = f"{type(info.value).__name__}: "
    else:
        error = _repeat_a_baseline_key(baseline, variant, obj["content"]["selector_sha256"])
    results = _activate(release_repo, "us-restore-next", obj, path, rows)
    assert [result.name for result in results] == _ACTIVATE_NAMES
    by_name = _by_name(results)
    result = by_name["base_carry_forward"]
    assert (result.passed, result.warning) == (False, False)
    assert result.evidence.startswith(f"base_carry_forward could not run: {error}")
    # The error fails base_carry_forward alone: base_only_pair reads no baseline.
    others = [item for item in results if item.name != "base_carry_forward"]
    assert all(item.passed and not item.warning for item in others), _evidence(others)
    if shape == "base_only":
        assert by_name["base_only_pair"].evidence == (
            "1 base-only incoming pair(s): 1 displace no active primary scope"
        )


def test_a_well_formed_baseline_clears_a_displaced_base_only_pair(release_repo) -> None:
    # The base_only shape with its baseline as written passes every check, so each
    # malformed-baseline case above fails for its baseline alone.
    obj, path, _, rows = _recorded_replacement(release_repo, "base_only")
    results = _activate(release_repo, "us-restore-next", obj, path, rows)
    assert [result.name for result in results] == _ACTIVATE_NAMES
    assert all(result.passed and not result.warning for result in results), _evidence(results)
    by_name = _by_name(results)
    assert by_name["base_carry_forward"].evidence == (
        "1 incoming pair(s): 1 displace an active base; 0 carry it unchanged and 1 "
        "replace it under a recorded base_replacements entry"
    )
    assert by_name["base_only_pair"].evidence == (
        "1 base-only incoming pair(s): 1 displace no active primary scope"
    )


@pytest.mark.parametrize("case", ["carried_base", "no_active_base"])
def test_carried_and_absent_bases_never_read_the_lineage_baseline(release_repo, case: str) -> None:
    # An unreadable baseline cannot fail a pair that needs no recorded replacement.
    root, _, make = release_repo
    if case == "carried_base":
        _install_active_manifest(root, "us-restore", B, P1)
        name, scopes = "us-later", [B, P1, P2]
        rows = [_layered_row(_STATUTE, [B.version, P1.version], B.version, release="us-restore")]
    else:
        _install_active_manifest(root, "us-head", P1, P2, R1)
        name, scopes = "us-restore", [P1, P2, B, R1, BR]
        rows = _restore_rows(incoming_at=_LATER, current_at=_EARLIER)
    obj, path = make(name, scopes)
    (root / "manifests" / "selector-lineage-baseline.yaml").write_text("selector_digests: {\n")
    results = _activate(release_repo, name, obj, path, rows)
    assert [result.name for result in results] == _ACTIVATE_NAMES
    assert all(result.passed for result in results), _evidence(results)


# Activation's base_only_pair check: a pair the incoming release selects only a
# base for must not displace an active release that serves primaries there.
def _base_alone(
    pair: tuple[str, str],
    incoming: str,
    base: str,
    primaries: list[str],
    current: str = "us-active",
) -> str:
    label = "/".join(pair)
    listed = ", ".join(f"{label}/{version}" for version in primaries)
    return (
        f"{label}: activation would serve {label} from base {label}/{base} alone and stop "
        f"serving primary scope(s) {listed} of {current!r}: {incoming} selects no primary "
        f"scope of {label}. Carry a primary scope of {label}; --allow-regression does not "
        "waive this check"
    )


@pytest.mark.parametrize("allow_regression", [False, True])
def test_base_only_successor_cannot_displace_active_primaries(
    release_repo, allow_regression: bool
) -> None:
    # The cut keeps the base, so lineage and base_carry_forward see nothing wrong;
    # only base_only_pair sees that it drops the primary above the base.
    _install_active_manifest(release_repo[0], "us-active", B, P1)
    rows = [_layered_row(_STATUTE, [B.version, P1.version], B.version)]
    _, _, results = _results(
        release_repo, "us-base-alone", [B], rows, allow_regression=allow_regression
    )
    assert [result.name for result in results] == _ACTIVATE_NAMES
    by_name = _by_name(results)
    result = by_name["base_only_pair"]
    assert (result.passed, result.warning) == (False, False)
    assert result.evidence == _base_alone(_STATUTE, "us-base-alone", B.version, [P1.version])
    assert by_name["base_carry_forward"].passed, by_name["base_carry_forward"].evidence
    monotonicity = by_name["scope_monotonicity"]
    assert (monotonicity.passed, monotonicity.warning) == (allow_regression, allow_regression)
    assert "incoming frontier '2026-04-29' precedes active '2026-07-26-p1'" in (
        monotonicity.evidence
    )
    for name in ("object_identity", "cut_plan_provenance", "no_orphan"):
        assert by_name[name].passed, by_name[name].evidence


def test_base_only_pair_fails_the_cli_under_allow_regression(
    release_repo, capsys, monkeypatch
) -> None:
    root, public, make = release_repo
    obj, path = make("us-base-alone", [B])
    _install_active_manifest(root, "us-active", B, P1)
    active_path = root / "active-state.json"
    active_path.write_text(json.dumps([_layered_row(_STATUTE, [B.version, P1.version], B.version)]))
    monkeypatch.setenv("AXIOM_CORPUS_RELEASE_PUBLIC_KEY", public)
    exit_code = gate.main(
        [
            "--release-object",
            str(path),
            "--release",
            "us-base-alone",
            "--content-sha",
            obj["content_sha256"],
            "--repo-root",
            str(root),
            "--mode",
            "activate",
            "--active-state-file",
            str(active_path),
            "--allow-regression",
        ]
    )
    output = capsys.readouterr().out
    assert exit_code == 1
    assert "| scope_monotonicity | WARN |" in output
    assert "| base_only_pair | FAIL |" in output
    # The flag turns the frontier regression into a warning; base_only_pair alone fails.
    assert re.findall(r"^\| (\w+) \| (PASS|FAIL|WARN) \|", output, re.MULTILINE) == [
        ("object_identity", "PASS"),
        ("cut_plan_provenance", "PASS"),
        ("scope_monotonicity", "WARN"),
        ("no_orphan", "PASS"),
        ("base_carry_forward", "PASS"),
        ("base_only_pair", "FAIL"),
        ("primary_frontier", "PASS"),
    ]


def test_separate_base_only_release_cannot_displace_primaries(release_repo) -> None:
    # The active release serves us/statute from primaries alone; the cut selects
    # only the May base, which no active base needs to carry forward.
    _install_active_manifest(release_repo[0], "us-active", P1)
    rows = [_layered_row(_STATUTE, [P1.version], None)]
    _, _, results = _results(release_repo, "us-base-release", [B], rows)
    by_name = _by_name(results)
    assert by_name["base_carry_forward"].passed, by_name["base_carry_forward"].evidence
    result = by_name["base_only_pair"]
    assert (result.passed, result.warning) == (False, False)
    assert result.evidence == _base_alone(_STATUTE, "us-base-release", B.version, [P1.version])


def test_fresh_base_alone_cannot_displace_primaries(release_repo) -> None:
    # A recorded replacement clears base_carry_forward, and the fresh base advances
    # the frontier, but the cut still drops the primary above the old base.
    root, _, make = release_repo
    _install_active_manifest(root, "us-active", B, P1)
    obj, path = make("us-fresh-base", [B_NEW])
    _write_lineage_baseline(
        root,
        selector="us-fresh-base",
        predecessor="us-active",
        pair=_STATUTE,
        replaced=B.version,
        replaced_by=B_NEW,
        digest=obj["content"]["selector_sha256"],
    )
    rows = [_layered_row(_STATUTE, [B.version, P1.version], B.version)]
    results = _activate(release_repo, "us-fresh-base", obj, path, rows)
    assert [result.name for result in results] == _ACTIVATE_NAMES
    assert [result.name for result in results if not result.passed] == ["base_only_pair"], (
        _evidence(results)
    )
    by_name = _by_name(results)
    assert by_name["base_carry_forward"].evidence == (
        "1 incoming pair(s): 1 displace an active base; 0 carry it unchanged and 1 replace "
        "it under a recorded base_replacements entry"
    )
    assert by_name["base_only_pair"].evidence == _base_alone(
        _STATUTE, "us-fresh-base", B_NEW.version, [P1.version]
    )


def test_base_only_pair_refuses_a_primary_relabelled_as_base(release_repo) -> None:
    # The cut serves the active primary version again, now as a base. Only the
    # active base is subtracted, so the version still counts as a displaced primary.
    _install_active_manifest(release_repo[0], "us-active", B_PRIMARY)
    rows = [_layered_row(_STATUTE, [B.version], None)]
    _, _, results = _results(release_repo, "us-relabelled", [B], rows)
    by_name = _by_name(results)
    assert by_name["scope_monotonicity"].passed, by_name["scope_monotonicity"].evidence
    assert by_name["base_carry_forward"].passed, by_name["base_carry_forward"].evidence
    result = by_name["base_only_pair"]
    assert (result.passed, result.warning) == (False, False)
    assert result.evidence == _base_alone(_STATUTE, "us-relabelled", B.version, [B.version])


@pytest.mark.parametrize("case", ["new_pair", "already_base_only", "reaffirm"])
def test_base_only_pair_passes_when_nothing_is_displaced(release_repo, case: str) -> None:
    row = {
        "new_pair": {
            "jurisdiction": "us",
            "document_class": "statute",
            "changes": True,
            "current_release_name": None,
            "current_versions": [],
        },
        "already_base_only": _layered_row(_STATUTE, [B.version], B.version),
        "reaffirm": {
            "jurisdiction": "us",
            "document_class": "statute",
            "changes": False,
            "current_release_name": "us-base-alone",
        },
    }[case]
    _, _, results = _results(release_repo, "us-base-alone", [B], [row])
    result = _by_name(results)["base_only_pair"]
    assert (result.passed, result.warning) == (True, False), result.evidence
    assert result.evidence == "1 base-only incoming pair(s): 1 displace no active primary scope"


@pytest.mark.parametrize(
    ("rows", "message"),
    [
        pytest.param(
            [_layered_row(_STATUTE, [B.version, P1.version])],
            "us/statute: active-state evidence lacks current_base_version",
            id="missing_key",
        ),
        pytest.param(
            # Empty versions and a null base would leave no primaries to subtract from.
            [_layered_row(_STATUTE, [], None)],
            "us/statute: active release 'us-active' has no version evidence",
            id="empty_versions",
        ),
        pytest.param(
            [_layered_row(_STATUTE, [P1.version], B.version)],
            "us/statute: current_base_version '2026-04-29' is not among current_versions "
            "['2026-07-26-p1']",
            id="base_not_listed",
        ),
        pytest.param(
            [],
            "us/statute: active-state preview has 0 row(s) for an incoming pair; "
            "refusing vacuous pass",
            id="no_row",
        ),
    ],
)
def test_base_only_pair_rejects_malformed_evidence(
    release_repo, rows: list[dict[str, Any]], message: str
) -> None:
    _, _, results = _results(release_repo, "us-base-alone", [B], rows)
    result = _by_name(results)["base_only_pair"]
    assert (result.passed, result.warning) == (False, False)
    assert result.evidence == message


@pytest.mark.parametrize("regulation", ["null_pointer", "already_base_only", "displaced"])
def test_a_later_base_only_pair_is_checked_after_an_earlier_one(
    release_repo, regulation: str
) -> None:
    # us/regulation sorts first; us/statute still displaces an active primary.
    regulation_row = {
        "null_pointer": {
            "jurisdiction": "us",
            "document_class": "regulation",
            "changes": True,
            "current_release_name": None,
            "current_versions": [],
        },
        "already_base_only": _layered_row(_REGULATION, [BR.version], BR.version),
        "displaced": _layered_row(_REGULATION, [BR.version, R1.version], BR.version),
    }[regulation]
    rows = [regulation_row, _layered_row(_STATUTE, [B.version, P1.version], B.version)]
    _, _, results = _results(release_repo, "us-bases-alone", [BR, B], rows)
    result = _by_name(results)["base_only_pair"]
    assert (result.passed, result.warning) == (False, False)
    expected = [_base_alone(_STATUTE, "us-bases-alone", B.version, [P1.version])]
    if regulation == "displaced":
        expected.insert(0, _base_alone(_REGULATION, "us-bases-alone", BR.version, [R1.version]))
    assert result.evidence == "; ".join(expected)


# Activation's primary_frontier check: a base dated after a pair's primary scopes
# must not hide a dropped newest primary scope from scope_monotonicity.
U = ReleaseScope("us", "statute", "2026-740-es")
U_R = ReleaseScope("us", "regulation", "2026-740-es")


def _newer_base_activation(
    release_repo, case: str
) -> tuple[str, dict[str, Any], Path, list[dict[str, Any]]]:
    """One newer-base cut: it drops P2, keeps P1 and selects the November base."""
    root, _, make = release_repo
    active, active_base = {
        "carried": ([B_NEW, P1, P2], B_NEW.version),
        "fresh": ([P1, P2], None),
        "replaced": ([B, P1, P2], B.version),
    }[case]
    _install_active_manifest(root, "us-active", *active)
    name = f"us-{case}"
    obj, path = make(name, [B_NEW, P1])
    if case == "replaced":
        _write_lineage_baseline(
            root,
            selector=name,
            predecessor="us-active",
            pair=_STATUTE,
            replaced=B.version,
            replaced_by=B_NEW,
            digest=obj["content"]["selector_sha256"],
        )
    rows = [_layered_row(_STATUTE, [scope.version for scope in active], active_base)]
    return name, obj, path, rows


def _malformed_key(label: str, version: str) -> str:
    with pytest.raises(ValueError) as malformed:
        gate._version_key(version)
    return f"{label}: {malformed.value}"


@pytest.mark.parametrize("allow_regression", [False, True])
@pytest.mark.parametrize("case", ["carried", "fresh", "replaced"])
def test_a_newer_base_cannot_hide_a_dropped_newest_primary(
    release_repo, case: str, allow_regression: bool
) -> None:
    # The November base is dated after both primary scopes, so it is the incoming
    # frontier of scope_monotonicity whether the active release carries it (carried),
    # serves no base (fresh) or serves the May base the cut records replacing.
    name, obj, path, rows = _newer_base_activation(release_repo, case)
    results = _activate(release_repo, name, obj, path, rows, allow_regression=allow_regression)
    others = [item for item in results if item.name != "primary_frontier"]
    assert all(item.passed and not item.warning for item in others), _evidence(others)
    assert [result.name for result in results] == _ACTIVATE_NAMES
    frontier = _by_name(results)["primary_frontier"]
    assert (frontier.passed, frontier.warning) == (allow_regression, allow_regression)
    assert frontier.evidence == _primary_regression()


@pytest.mark.parametrize("flag", [False, True])
def test_primary_frontier_regression_in_the_cli(
    release_repo, capsys, monkeypatch, flag: bool
) -> None:
    root, public, _ = release_repo
    name, obj, path, rows = _newer_base_activation(release_repo, "carried")
    active_path = root / "active-state.json"
    active_path.write_text(json.dumps(rows))
    monkeypatch.setenv("AXIOM_CORPUS_RELEASE_PUBLIC_KEY", public)
    argv = [
        "--release-object",
        str(path),
        "--release",
        name,
        "--content-sha",
        obj["content_sha256"],
        "--repo-root",
        str(root),
        "--mode",
        "activate",
        "--active-state-file",
        str(active_path),
    ]
    exit_code = gate.main(argv + (["--allow-regression"] if flag else []))
    output = capsys.readouterr().out
    status = "WARN" if flag else "FAIL"
    assert re.findall(r"^\| (\w+) \| (PASS|FAIL|WARN) \|", output, re.MULTILINE) == [
        ("object_identity", "PASS"),
        ("cut_plan_provenance", "PASS"),
        ("scope_monotonicity", "PASS"),
        ("no_orphan", "PASS"),
        ("base_carry_forward", "PASS"),
        ("base_only_pair", "PASS"),
        ("primary_frontier", status),
    ]
    assert f"| primary_frontier | {status} |" in output
    assert exit_code == (0 if flag else 1)
    acknowledged = f"RELEASE_GATE_REGRESSION_ACKNOWLEDGED={name}"
    assert (acknowledged in output.splitlines()) is flag


@pytest.mark.parametrize("case", ["later_cut", "older_primary_dropped"])
def test_primary_frontier_passes_kept_and_advanced_primaries(release_repo, case: str) -> None:
    # later_cut keeps every active primary scope; older_primary_dropped keeps the
    # newest, so the primary frontiers tie and the per-pair limit remains.
    active, incoming = {
        "later_cut": ([B_NEW, P1], [B_NEW, P1, P2]),
        "older_primary_dropped": ([B_NEW, P1, P2], [B_NEW, P2]),
    }[case]
    _install_active_manifest(release_repo[0], "us-active", *active)
    rows = [_layered_row(_STATUTE, [scope.version for scope in active], B_NEW.version)]
    _, _, results = _results(release_repo, "us-next", incoming, rows)
    assert [result.name for result in results] == _ACTIVATE_NAMES
    assert all(result.passed and not result.warning for result in results), _evidence(results)
    assert _by_name(results)["primary_frontier"].evidence == (
        "1 incoming pair(s): 1 displaced pair(s) have a base on either side; 1 keep or "
        "advance their newest primary scope and 0 select only a base, which base_only_pair "
        "checks"
    )


def test_an_omitted_base_with_a_primary_regression_fails_primary_frontier(release_repo) -> None:
    # The cut selects no base, so only the active side has a base to leave out.
    _install_active_manifest(release_repo[0], "us-active", B, P2)
    rows = [_layered_row(_STATUTE, [B.version, P2.version], B.version)]
    _, _, results = _results(release_repo, "us-omitted", [P1], rows)
    assert [result.name for result in results if not result.passed] == [
        "scope_monotonicity",
        "base_carry_forward",
        "primary_frontier",
    ], _evidence(results)
    frontier = _by_name(results)["primary_frontier"]
    assert (frontier.passed, frontier.warning) == (False, False)
    assert frontier.evidence == _primary_regression()


@pytest.mark.parametrize(
    ("case", "allow_regression"),
    [
        pytest.param("kept_unordered_regression", False, id="kept_unordered_regression"),
        pytest.param("only_unordered_kept", False, id="only_unordered_kept-False"),
        pytest.param("only_unordered_kept", True, id="only_unordered_kept-True"),
        pytest.param("unordered_only_active", False, id="unordered_only_active"),
        pytest.param("dropped_unordered", False, id="dropped_unordered"),
    ],
)
def test_primary_frontier_orders_unordered_primaries(
    release_repo, case: str, allow_regression: bool
) -> None:
    # U does not parse as a dated version key. A primary version both sides keep needs
    # no ordering proof; every other primary version must order.
    active, incoming = {
        "kept_unordered_regression": ([B_NEW, U, P2], [B_NEW, U, P1]),
        "only_unordered_kept": ([B_NEW, U, P1], [B_NEW, U]),
        "unordered_only_active": ([B_NEW, U], [B_NEW, U, P1]),
        "dropped_unordered": ([B_NEW, U, P1], [B_NEW, P1]),
    }[case]
    _install_active_manifest(release_repo[0], "us-active", *active)
    rows = [_layered_row(_STATUTE, [scope.version for scope in active], B_NEW.version)]
    _, _, results = _results(
        release_repo, "us-next", incoming, rows, allow_regression=allow_regression
    )
    assert not any(result.warning for result in results), _evidence(results)
    failed = [result.name for result in results if not result.passed]
    if case == "unordered_only_active":
        # Every active primary version is kept, so the pair needs no ordering proof.
        assert [result.name for result in results] == _ACTIVATE_NAMES
        assert failed == [], _evidence(results)
        assert _by_name(results)["primary_frontier"].evidence == (
            "1 incoming pair(s): 1 displaced pair(s) have a base on either side; 1 keep or "
            "advance their newest primary scope and 0 select only a base, which "
            "base_only_pair checks"
        )
        return
    # scope_monotonicity orders the versions that differ with the base among them, so
    # the frontiers tie at the base; it fails only when it cannot order U either.
    expected_failed = ["primary_frontier"]
    if case == "dropped_unordered":
        expected_failed.insert(0, "scope_monotonicity")
    assert failed == expected_failed, _evidence(results)
    frontier = _by_name(results)["primary_frontier"]
    assert (frontier.passed, frontier.warning) == (False, False)
    assert (
        frontier.evidence
        == {
            "kept_unordered_regression": _primary_regression(),
            "only_unordered_kept": "us/statute: incoming keeps only unordered primary versions "
            "['2026-740-es'] and drops active primary versions ['2026-07-26-p1']; no ordering "
            "proof is possible",
            "dropped_unordered": _malformed_key("us/statute", U.version),
        }[case]
    )


@pytest.mark.parametrize(
    "regulation",
    [
        "no_base",
        "base_only",
        "keeps_all",
        "null_pointer",
        "earlier_evidence_failure",
        "earlier_malformed_key",
    ],
)
def test_a_later_pair_is_checked_after_an_earlier_one_passes_primary_frontier(
    release_repo, regulation: str
) -> None:
    # us/regulation sorts first; us/statute is the carried newer-base regression.
    active, base, incoming = {
        "no_base": ([R1], None, [R1]),
        "base_only": ([BR], BR.version, [BR]),
        "keeps_all": ([BR, R1], BR.version, [BR, R1]),
        "null_pointer": ([], None, [R1]),
        "earlier_evidence_failure": ([BR, U_R, R1], BR.version, [BR, U_R]),
        "earlier_malformed_key": ([BR, U_R, R1], BR.version, [BR, R1]),
    }[regulation]
    regulation_row = (
        {
            "jurisdiction": "us",
            "document_class": "regulation",
            "changes": True,
            "current_release_name": None,
            "current_versions": [],
        }
        if regulation == "null_pointer"
        else _layered_row(_REGULATION, [scope.version for scope in active], base)
    )
    statute_row = _layered_row(_STATUTE, [B_NEW.version, P1.version, P2.version], B_NEW.version)
    _, _, results = _results(
        release_repo, "us-two-pairs", [*incoming, B_NEW, P1], [regulation_row, statute_row]
    )
    result = _by_name(results)["primary_frontier"]
    assert (result.passed, result.warning) == (False, False)
    # The evidence names us/statute, so the check went on past us/regulation.
    expected = [_primary_regression()]
    if regulation == "earlier_evidence_failure":
        expected.insert(
            0,
            "us/regulation: incoming keeps only unordered primary versions ['2026-740-es'] "
            "and drops active primary versions ['2026-07-26-r1']; no ordering proof is "
            "possible",
        )
    elif regulation == "earlier_malformed_key":
        expected.insert(0, _malformed_key("us/regulation", U_R.version))
    assert result.evidence == "; ".join(expected)


@pytest.mark.parametrize(
    ("regulation", "statute"),
    [
        pytest.param("unordered_kept", "newer_base", id="unordered_kept"),
        pytest.param("malformed_key", "newer_base", id="malformed_key"),
        pytest.param("missing_base_field", "newer_base", id="missing_base_field"),
        pytest.param("malformed_key", "older_base", id="malformed_key-older_base"),
    ],
)
def test_an_evidence_failure_keeps_a_waived_regression_on_another_pair_failing(
    release_repo, regulation: str, statute: str
) -> None:
    # us/regulation sorts first and fails on evidence; us/statute moves its newest
    # primary scope back, a proven regression that --allow-regression would turn into
    # a warning if it stood alone.
    regulation_active, regulation_incoming = {
        "unordered_kept": ([BR, U_R, R1], [BR, U_R]),
        "malformed_key": ([BR, U_R, R1], [BR, R1]),
        "missing_base_field": ([BR, R1], [BR, R1]),
    }[regulation]
    statute_base = {"newer_base": B_NEW, "older_base": B}[statute]
    statute_active = [statute_base, P1, P2]
    _install_active_manifest(release_repo[0], "us-active", *regulation_active, *statute_active)
    rows = [
        _layered_row(
            _REGULATION,
            [scope.version for scope in regulation_active],
            _UNSET if regulation == "missing_base_field" else BR.version,
        ),
        _layered_row(_STATUTE, [scope.version for scope in statute_active], statute_base.version),
    ]
    _, _, results = _results(
        release_repo,
        "us-two-pairs",
        [*regulation_incoming, statute_base, P1],
        rows,
        allow_regression=True,
    )
    assert [result.name for result in results] == _ACTIVATE_NAMES
    frontier = _by_name(results)["primary_frontier"]
    assert (frontier.passed, frontier.warning) == (False, False)
    evidence_failure = {
        "unordered_kept": "us/regulation: incoming keeps only unordered primary versions "
        "['2026-740-es'] and drops active primary versions ['2026-07-26-r1']; no ordering "
        "proof is possible",
        "malformed_key": _malformed_key("us/regulation", U_R.version),
        "missing_base_field": "us/regulation: active-state evidence lacks current_base_version",
    }[regulation]
    assert frontier.evidence == f"{evidence_failure}; {_primary_regression()}"
    failed = [result.name for result in results if not result.passed]
    warned = [result.name for result in results if result.warning]
    assert (failed, warned) == {
        ("unordered_kept", "newer_base"): (["primary_frontier"], ["scope_monotonicity"]),
        ("malformed_key", "newer_base"): (["scope_monotonicity", "primary_frontier"], []),
        ("missing_base_field", "newer_base"): (["base_carry_forward", "primary_frontier"], []),
        ("malformed_key", "older_base"): (["scope_monotonicity", "primary_frontier"], []),
    }[(regulation, statute)], _evidence(results)
    if statute == "older_base":
        # The older base leaves scope_monotonicity's statute frontier at the primary
        # scopes, so it too holds a proven regression beside an evidence failure.
        monotonicity = _by_name(results)["scope_monotonicity"]
        assert "malformed version key '2026-740-es'" in monotonicity.evidence
        assert "incoming frontier '2026-07-26-p1' precedes active '2026-07-28-p2'" in (
            monotonicity.evidence
        )


def test_an_unreadable_signed_layer_fails_each_layer_check_alone(release_repo) -> None:
    # A tampered object fails identity, and each layer check reports its own error
    # without a second result for the checks in the provider's shared try.
    root, _, make = release_repo
    _install_active_manifest(root, "us-active", B, P1)
    obj, path = make("us-tampered", [B, P1])
    for scope in obj["content"]["scopes"]:
        if scope.get("layer") == LAYER_BASE:
            scope["layer"] = "overlay"
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")
    rows = [_layered_row(_STATUTE, [B.version, P1.version], B.version)]
    results = _activate(release_repo, "us-tampered", obj, path, rows)
    assert [result.name for result in results] == _ACTIVATE_NAMES
    by_name = _by_name(results)
    assert not by_name["object_identity"].passed
    monotonicity = by_name["scope_monotonicity"]
    assert monotonicity.passed, monotonicity.evidence
    assert "active-state lookup failed" not in monotonicity.evidence
    error = "ValueError: scope us/statute/2026-04-29 has an unsupported layer: 'overlay'"
    for name in ("base_carry_forward", "base_only_pair", "primary_frontier"):
        assert (by_name[name].passed, by_name[name].evidence) == (
            False,
            f"{name} could not run: {error}",
        )


# The provider reads versions, bases and layers only from a stored release object
# that is the signed object of its own row: it names the row's release, hashes to
# the row's digest and verifies (schema, digests, signature).
def _unsigned(obj: dict[str, Any]) -> dict[str, Any]:
    unsigned = copy.deepcopy(obj)
    unsigned.pop("signature")
    return unsigned


def _without_base_marker(obj: dict[str, Any]) -> dict[str, Any]:
    relabelled = copy.deepcopy(obj)
    for scope in relabelled["content"]["scopes"]:
        scope.pop("layer", None)
    return relabelled


def _resign_unchecked(obj: dict[str, Any], private_text: str) -> dict[str, Any]:
    """Re-sign an object with a valid content digest, skipping sign_release_object's checks."""
    signed = copy.deepcopy(obj)
    signed.pop("signature", None)
    signed["content_sha256"] = release_content_sha256(signed["content"])
    private = Ed25519PrivateKey.from_private_bytes(b64decode(private_text))
    signed["signature"] = {
        "algorithm": RELEASE_OBJECT_SIGNATURE_ALGORITHM,
        "key_id": RELEASE_OBJECT_SIGNATURE_KEY_ID,
        "value": b64encode(private.sign(canonical_release_object_bytes(signed))).decode("ascii"),
    }
    return signed


def _provider_results(
    release_repo,
    monkeypatch,
    name: str,
    obj: dict[str, Any],
    path: Path,
    rows: list[dict[str, Any]],
    details: list[dict[str, Any]],
    *,
    legacy_public_keys: tuple[str, ...] = (),
):
    root, public, _ = release_repo
    provide = _fake_supabase_provider(
        monkeypatch,
        rows,
        details,
        [],
        public_key=public,
        legacy_public_keys=legacy_public_keys,
    )
    return gate.run_gate(
        release_object_path=path,
        release=name,
        content_sha=obj["content_sha256"],
        repo_root=root,
        mode="activate",
        public_key=public,
        active_state_provider=provide,
    )


def _forged_activation(variant: str, root: Path, make, private: str):
    """Set up one forgery: (incoming name, object, path, rows, details, refused, refusal)."""
    if variant == "null_identity":
        # A detail with no identity, keyed ('None', 'None'), meets the null row.
        active, _ = make("us-active", [B, P1])
        plain, _ = make("us-plain", [R1])
        obj, path = make("us-new-pair", [B, R1])
        rows = [
            {
                "jurisdiction": "us",
                "document_class": "statute",
                "changes": True,
                "current_release_name": None,
                "current_content_sha256": None,
            },
            _changed_row(_REGULATION, "us-plain", plain["content_sha256"]),
        ]
        details = [
            _signed_detail(obj, published_at=_LATER),
            _signed_detail(plain, published_at=_EARLIER),
            {
                "release_name": None,
                "content_sha256": None,
                "published_at": _EARLIER,
                "release_object": active,
            },
        ]
        return "us-new-pair", obj, path, rows, details, "None", "has no release identity"
    incoming_name, incoming_scopes = "us-next", [P1, P2]
    refused, refusal = "'us-active'", "is not the object of its row"
    stored_incoming = None
    if variant == "relabelled_unsigned":
        active, _ = make("us-active", [B, P1])
        stored, digest = _unsigned(_without_base_marker(active)), active["content_sha256"]
    elif variant in ("unsigned", "foreign_key"):
        active, _ = make("us-active", [B_PRIMARY, P1])
        digest = active["content_sha256"]
        if variant == "unsigned":
            stored = _unsigned(active)
            refusal = "does not verify: release object is missing its signature"
        else:
            stored = sign_release_object(active, private_key=_new_key_pair()[0])
            refusal = "does not verify: release object signature is invalid"
    elif variant == "unmarked_v4_base":
        active, _ = make("us-active", [B, P1])
        stored = _resign_unchecked(_without_base_marker(active), private)
        digest = stored["content_sha256"]
        refusal = (
            "does not verify: release-object/v4 is reserved for releases with at least one "
            "base scope"
        )
    elif variant == "other_release":
        stored, _ = make("us-other", [B_PRIMARY, P1])
        _install_active_manifest(root, "us-active", B, P1)
        digest = stored["content_sha256"]
    elif variant == "other_digest":
        active, _ = make("us-active", [B, P1])
        stored, _ = make("us-active", [B_PRIMARY, P1])
        digest = active["content_sha256"]
    elif variant == "unsigned_incoming":
        stored, _ = make("us-active", [B, P1])
        digest = stored["content_sha256"]
        incoming_scopes = [B, P1, P2]
        stored_incoming = _unsigned
        refused, refusal = "'us-next'", "does not verify: release object is missing its signature"
    elif variant == "base_only_forgery":
        active, _ = make("us-active", [B, P1])
        stored, _ = make("us-active", [P1_BASE])
        digest = active["content_sha256"]
        incoming_scopes = [P1_BASE]
    else:
        assert variant == "monotonicity_forgery"
        active, _ = make("us-active", [P2])
        stored, _ = make("us-active", [P1])
        digest = active["content_sha256"]
        incoming_scopes = [P1]
    obj, path = make(incoming_name, incoming_scopes)
    incoming_copy = obj if stored_incoming is None else stored_incoming(obj)
    rows = [_changed_row(_STATUTE, "us-active", digest)]
    details = [
        _signed_detail(incoming_copy, published_at=_LATER),
        _signed_detail(
            stored, published_at=_EARLIER, release_name="us-active", content_sha256=digest
        ),
    ]
    return incoming_name, obj, path, rows, details, refused, refusal


@pytest.mark.parametrize(
    "variant",
    [
        "relabelled_unsigned",
        "unsigned",
        "foreign_key",
        "unmarked_v4_base",
        "other_release",
        "other_digest",
        "unsigned_incoming",
        "base_only_forgery",
        "monotonicity_forgery",
        "null_identity",
    ],
)
def test_a_stored_object_that_is_not_its_rows_signed_object_fails_every_state_check(
    release_repo, signing_keys, monkeypatch, variant: str
) -> None:
    root, _, make = release_repo
    name, obj, path, rows, details, refused, refusal = _forged_activation(
        variant, root, make, signing_keys[0]
    )
    results = _provider_results(release_repo, monkeypatch, name, obj, path, rows, details)
    assert [result.name for result in results] == _ACTIVATE_NAMES
    by_name = _by_name(results)
    for check in ("object_identity", "cut_plan_provenance"):
        assert by_name[check].passed, by_name[check].evidence
    monotonicity = by_name["scope_monotonicity"]
    assert (monotonicity.passed, monotonicity.warning) == (False, False)
    assert monotonicity.evidence.startswith(
        f"active-state lookup failed: stored release object of {refused} "
    ), monotonicity.evidence
    assert refusal in monotonicity.evidence
    for result in results[3:]:
        assert (result.passed, result.warning, result.evidence) == (
            False,
            False,
            "active-state evidence unavailable",
        )


@pytest.mark.parametrize("case", ["base", "base_only", "monotonicity"])
def test_honest_stored_objects_show_what_the_forgeries_hide(
    release_repo, monkeypatch, case: str
) -> None:
    _, _, make = release_repo
    active_scopes, incoming_scopes = {
        "base": ([B, P1], [P1, P2]),
        "base_only": ([B, P1], [P1_BASE]),
        "monotonicity": ([P2], [P1]),
    }[case]
    active, _ = make("us-active", active_scopes)
    obj, path = make("us-next", incoming_scopes)
    rows = [_changed_row(_STATUTE, "us-active", active["content_sha256"])]
    details = [
        _signed_detail(obj, published_at=_LATER),
        _signed_detail(active, published_at=_EARLIER),
    ]
    results = _provider_results(release_repo, monkeypatch, "us-next", obj, path, rows, details)
    by_name = _by_name(results)
    failed = {result.name: result.evidence for result in results if not result.passed}
    if case == "base":
        assert failed == {"base_carry_forward": _stop_serving("us-next", "no base")}
    elif case == "base_only":
        assert failed == {
            "base_carry_forward": _stop_serving("us-next", "base us/statute/2026-07-26-p1"),
            "base_only_pair": _base_alone(_STATUTE, "us-next", P1.version, [P1.version]),
        }
    else:
        assert list(failed) == ["scope_monotonicity"]
        assert "incoming frontier '2026-07-26-p1' precedes active '2026-07-28-p2'" in (
            by_name["scope_monotonicity"].evidence
        )


def _assert_lookup_failed(results, message: str) -> None:
    """The provider raised: identity checks pass and every active-state check fails."""
    assert [result.name for result in results] == _ACTIVATE_NAMES
    by_name = _by_name(results)
    for check in ("object_identity", "cut_plan_provenance"):
        assert by_name[check].passed, by_name[check].evidence
    monotonicity = by_name["scope_monotonicity"]
    assert (monotonicity.passed, monotonicity.warning, monotonicity.evidence) == (
        False,
        False,
        f"active-state lookup failed: {message}",
    )
    for result in results[3:]:
        assert (result.passed, result.warning, result.evidence) == (
            False,
            False,
            "active-state evidence unavailable",
        )


def test_the_gate_holds_preview_rows_to_the_wrapper_querys_columns() -> None:
    # tests/test_atomic_release_postgres.py's
    # test_preview_wrapper_query_matches_the_function_contract runs this query
    # against the function and checks its five columns, so the gate's list cannot
    # drift from the function either.
    selected = PREVIEW_ACTIVATION_QUERY.split("SELECT ", 1)[1].split(" FROM ", 1)[0]
    assert tuple(column.strip() for column in selected.split(",")) == gate._PREVIEW_COLUMNS


_PREVIEW_VARIANTS = {
    "honest": (lambda row: row, None),
    "provider_versions": (
        lambda row: {**row, "current_versions": [P1.version]},
        "extra ['current_versions'], missing []",
    ),
    "provider_base": (
        lambda row: {**row, "current_base_version": None},
        "extra ['current_base_version'], missing []",
    ),
    "provider_active_time": (
        lambda row: {**row, "current_published_at": _EARLIER},
        "extra ['current_published_at'], missing []",
    ),
    "provider_incoming_time": (
        lambda row: {**row, "incoming_published_at": _LATER},
        "extra ['incoming_published_at'], missing []",
    ),
    "unknown_column": (
        lambda row: {**row, "note": "added on the way"},
        "extra ['note'], missing []",
    ),
    "missing_digest": (
        lambda row: {key: value for key, value in row.items() if key != "current_content_sha256"},
        "extra [], missing ['current_content_sha256']",
    ),
}


@pytest.mark.parametrize("variant", list(_PREVIEW_VARIANTS))
def test_a_preview_row_outside_the_function_contract_fails_every_state_check(
    release_repo, monkeypatch, variant: str
) -> None:
    # A reaffirming row (changes false) displaces nothing and needs no stored
    # object, so without the column rule every variant passes all seven checks.
    root, public, make = release_repo
    obj, path = make("us-next", [P1])
    edit, columns = _PREVIEW_VARIANTS[variant]
    row = edit(
        {
            "jurisdiction": "us",
            "document_class": "statute",
            "current_release_name": "us-next",
            "current_content_sha256": obj["content_sha256"],
            "changes": False,
        }
    )
    queries: list[dict[str, Any]] = []
    provide = _fake_supabase_provider(monkeypatch, [row], [], queries, public_key=public)
    results = gate.run_gate(
        release_object_path=path,
        release="us-next",
        content_sha=obj["content_sha256"],
        repo_root=root,
        mode="activate",
        public_key=public,
        active_state_provider=provide,
    )
    assert queries == []
    if columns is None:
        assert all(result.passed and not result.warning for result in results), _evidence(results)
        return
    _assert_lookup_failed(
        results,
        f"active-state preview row 0 does not have the preview function's columns: {columns}",
    )


def test_a_malformed_preview_cannot_supply_version_evidence(release_repo, monkeypatch) -> None:
    # Round 2 P2-2. The active release serves base B under P1, and the incoming
    # release drops B (test_honest_stored_objects_show_what_the_forgeries_hide
    # "base" fails it on base_carry_forward). Here the response row says the
    # active release has no base and the details response omits that release, so
    # without the column rule nothing corrects the row and all seven checks pass.
    _, _, make = release_repo
    active, _ = make("us-active", [B, P1])
    obj, path = make("us-next", [P1, P2])
    row = {
        **_changed_row(_STATUTE, "us-active", active["content_sha256"]),
        "current_versions": [B.version, P1.version],
        "current_base_version": None,
    }
    results = _provider_results(
        release_repo,
        monkeypatch,
        "us-next",
        obj,
        path,
        [row],
        [_signed_detail(obj, published_at=_LATER)],
    )
    _assert_lookup_failed(
        results,
        "active-state preview row 0 does not have the preview function's columns: "
        "extra ['current_base_version', 'current_versions'], missing []",
    )


@pytest.mark.parametrize("injected", [False, True])
def test_a_preview_row_cannot_supply_the_incoming_publication_time(
    release_repo, monkeypatch, injected: bool
) -> None:
    # Identical versions on both sides, so only publication recency decides. The
    # database returns the active object but not the incoming one, so the gate
    # has no incoming time and refuses; without the column rule a
    # response-supplied incoming_published_at survives (the provider sets it only
    # from a returned detail) and proves recency. The active detail is present,
    # so only the column rule can refuse the injected row.
    _, _, make = release_repo
    active, _ = make("us-active", [P1])
    obj, path = make("us-next", [P1])
    row = _changed_row(_STATUTE, "us-active", active["content_sha256"])
    if injected:
        row["incoming_published_at"] = _LATER
    results = _provider_results(
        release_repo,
        monkeypatch,
        "us-next",
        obj,
        path,
        [row],
        [_signed_detail(active, published_at=_EARLIER)],
    )
    if injected:
        _assert_lookup_failed(
            results,
            "active-state preview row 0 does not have the preview function's columns: "
            "extra ['incoming_published_at'], missing []",
        )
        return
    failed = {result.name: result.evidence for result in results if not result.passed}
    assert failed == {
        "scope_monotonicity": (
            "incoming database publication timestamp is missing; publication evidence: "
            "corpus.release_objects.created_at; scope_activation_history records activation "
            "time, not publication time"
        )
    }


def test_a_displaced_release_without_a_stored_object_fails_every_state_check(
    release_repo, monkeypatch
) -> None:
    # Moved here from test_supabase_provider_records_current_base_version's
    # us-missing row. corpus.active_scope_pointer references corpus.release_objects,
    # so an honest details response always holds the displaced release. Without
    # the missing-object rule scope_monotonicity, base_carry_forward and
    # primary_frontier already fail on the empty versions, but no_orphan passes,
    # because the manifest is on main, and base_only_pair passes, because the cut
    # has no base-only pair.
    root, _, make = release_repo
    _install_active_manifest(root, "us-missing", P1)
    obj, path = make("us-next", [P1, P2])
    results = _provider_results(
        release_repo,
        monkeypatch,
        "us-next",
        obj,
        path,
        [_changed_row(_STATUTE, "us-missing")],
        [_signed_detail(obj, published_at=_LATER)],
    )
    _assert_lookup_failed(
        results,
        "the database returned no stored release object for displaced release(s) "
        "'us-missing' at 'us-missing-sha'",
    )


_RESPONSE_VARIANTS = [
    "honest",
    "null",
    "object",
    "null_item",
    "number_item",
    "missing_column",
    "extra_column",
    "empty_name",
    "numeric_digest",
]


@pytest.mark.parametrize("variant", _RESPONSE_VARIANTS)
def test_a_malformed_stored_object_response_fails_every_state_check(
    release_repo, monkeypatch, variant: str
) -> None:
    # A strict advance over a plain active release: the honest response passes.
    _, _, make = release_repo
    active, _ = make("us-active", [P1])
    obj, path = make("us-next", [P1, P2])
    sha = active["content_sha256"]
    incoming = _signed_detail(obj, published_at=_LATER)
    stored = _signed_detail(active, published_at=_EARLIER)
    columns = "stored release object response item 1 does not have the query's columns"
    identity = "has no release identity: release_name and content_sha256 must be non-empty strings"
    response, message = {
        "honest": ([incoming, stored], None),
        "null": (None, "stored release object response is not a JSON array: NoneType"),
        "object": (
            {"rows": [incoming, stored]},
            "stored release object response is not a JSON array: dict",
        ),
        "null_item": (
            [incoming, None],
            "stored release object response item 1 is not an object: NoneType",
        ),
        "number_item": (
            [incoming, 42],
            "stored release object response item 1 is not an object: int",
        ),
        "missing_column": (
            [incoming, {key: value for key, value in stored.items() if key != "published_at"}],
            f"{columns}: extra [], missing ['published_at']",
        ),
        "extra_column": (
            [incoming, {**stored, "note": "added on the way"}],
            f"{columns}: extra ['note'], missing []",
        ),
        "empty_name": (
            [incoming, {**stored, "release_name": ""}],
            f"stored release object of '' {identity}, not '' and {sha!r}",
        ),
        "numeric_digest": (
            [incoming, {**stored, "content_sha256": 7}],
            f"stored release object of 'us-active' {identity}, not 'us-active' and 7",
        ),
    }[variant]
    rows = [_changed_row(_STATUTE, "us-active", sha)]
    results = _provider_results(release_repo, monkeypatch, "us-next", obj, path, rows, response)
    if message is None:
        assert all(result.passed and not result.warning for result in results), _evidence(results)
        return
    _assert_lookup_failed(results, message)


@pytest.mark.parametrize("copies", ["first_copy_only", "later_copy_differs", "identical"])
def test_a_repeated_stored_identity_fails_every_state_check(
    release_repo, monkeypatch, copies: str
) -> None:
    # Identical versions, so publication recency decides. The first stored copy of
    # the active release was published after the incoming release, so that copy
    # alone fails scope_monotonicity. Without the repeat rule a later copy with an
    # earlier time replaces it (the provider kept the last copy), and identical
    # copies both verify.
    _, _, make = release_repo
    active, _ = make("us-active", [P1])
    obj, path = make("us-next", [P1])
    first_at = _EARLIER if copies == "identical" else _LATEST
    details = [
        _signed_detail(obj, published_at=_LATER),
        _signed_detail(active, published_at=first_at),
    ]
    if copies != "first_copy_only":
        details.append(_signed_detail(active, published_at=_EARLIER))
    rows = [_changed_row(_STATUTE, "us-active", active["content_sha256"])]
    results = _provider_results(release_repo, monkeypatch, "us-next", obj, path, rows, details)
    if copies == "first_copy_only":
        failed = {result.name: result.evidence for result in results if not result.passed}
        assert list(failed) == ["scope_monotonicity"]
        evidence = failed["scope_monotonicity"]
        assert "identical version evidence, but incoming 'us-next' was published" in evidence
        return
    _assert_lookup_failed(
        results,
        f"stored release object of 'us-active' at {active['content_sha256']!r} "
        "appears more than once",
    )


def test_a_repeated_stored_release_name_fails_every_state_check(release_repo, monkeypatch) -> None:
    # release_name is corpus.release_objects' primary key, so one name never comes
    # back at two digests. Here the preview names us-active at two digests for two
    # pairs, and the response returns a genuine signed object at each. Without the
    # release_name rule both verify, each row reads its own object, and all seven
    # checks pass.
    _, _, make = release_repo
    statute_only, _ = make("us-active", [P1])
    both, _ = make("us-active", [P1, R1])
    obj, path = make("us-next", [P1, P2, R1])
    rows = [
        _changed_row(_STATUTE, "us-active", statute_only["content_sha256"]),
        _changed_row(_REGULATION, "us-active", both["content_sha256"]),
    ]
    details = [
        _signed_detail(obj, published_at=_LATER),
        _signed_detail(statute_only, published_at=_EARLIER),
        _signed_detail(both, published_at=_EARLIER),
    ]
    results = _provider_results(release_repo, monkeypatch, "us-next", obj, path, rows, details)
    _assert_lookup_failed(
        results,
        f"stored release object of 'us-active' at {both['content_sha256']!r} repeats the "
        f"release_name of the object at {statute_only['content_sha256']!r}",
    )


def test_a_repeated_stored_digest_fails_every_state_check(release_repo, monkeypatch) -> None:
    # content_sha256 is UNIQUE in corpus.release_objects, so one digest never comes
    # back under two names. The signed content names its release, so no genuine
    # object of another release shares the digest: without the content_sha256 rule
    # the relabelled copy fails the bind with other text.
    _, _, make = release_repo
    active, _ = make("us-active", [P1])
    obj, path = make("us-next", [P1, P2, R1])
    sha = active["content_sha256"]
    rows = [
        _changed_row(_STATUTE, "us-active", sha),
        _changed_row(_REGULATION, "us-alias", sha),
    ]
    details = [
        _signed_detail(obj, published_at=_LATER),
        _signed_detail(active, published_at=_EARLIER),
        _signed_detail(active, published_at=_EARLIER, release_name="us-alias"),
    ]
    results = _provider_results(release_repo, monkeypatch, "us-next", obj, path, rows, details)
    _assert_lookup_failed(
        results,
        f"stored release object of 'us-alias' at {sha!r} repeats the content_sha256 of 'us-active'",
    )


def test_an_unrequested_stored_identity_fails_every_state_check(release_repo, monkeypatch) -> None:
    # The query asks only for the incoming and displaced identities (WHERE ... IN).
    # Without the requested rule a genuine signed object of another release
    # verifies and is ignored.
    _, _, make = release_repo
    active, _ = make("us-active", [P1])
    other, _ = make("us-other", [R1])
    obj, path = make("us-next", [P1, P2])
    rows = [_changed_row(_STATUTE, "us-active", active["content_sha256"])]
    details = [
        _signed_detail(obj, published_at=_LATER),
        _signed_detail(active, published_at=_EARLIER),
        _signed_detail(other, published_at=_EARLIER),
    ]
    results = _provider_results(release_repo, monkeypatch, "us-next", obj, path, rows, details)
    _assert_lookup_failed(
        results,
        f"stored release object of 'us-other' at {other['content_sha256']!r} was not requested",
    )


@pytest.mark.parametrize("keys", ["none", "other", "signer"])
def test_a_displaced_object_signed_under_a_retired_key_needs_that_key(
    release_repo, monkeypatch, keys: str
) -> None:
    _, _, make = release_repo
    retired_private, retired_public = _new_key_pair()
    active, _ = make("us-active", [B, P1])
    # Re-signing leaves the content, and so its digest, unchanged.
    retired = sign_release_object(active, private_key=retired_private)
    assert retired["content_sha256"] == active["content_sha256"]
    obj, path = make("us-next", [B, P1, P2])
    rows = [_changed_row(_STATUTE, "us-active", active["content_sha256"])]
    details = [
        _signed_detail(obj, published_at=_LATER),
        _signed_detail(retired, published_at=_EARLIER),
    ]
    legacy = {"none": (), "other": (_new_key_pair()[1],), "signer": (retired_public,)}[keys]
    results = _provider_results(
        release_repo, monkeypatch, "us-next", obj, path, rows, details, legacy_public_keys=legacy
    )
    assert [result.name for result in results] == _ACTIVATE_NAMES
    by_name = _by_name(results)
    if keys == "signer":
        assert all(result.passed and not result.warning for result in results), _evidence(results)
        assert by_name["base_carry_forward"].evidence == (
            "1 incoming pair(s): 1 displace an active base; 1 carry it unchanged and 0 replace "
            "it under a recorded base_replacements entry"
        )
        return
    assert by_name["scope_monotonicity"].evidence == (
        "active-state lookup failed: stored release object of 'us-active' does not verify: "
        "release object signature is invalid"
    )
    for result in results[2:]:
        assert (result.passed, result.warning) == (False, False), result.evidence
    for result in results[3:]:
        assert result.evidence == "active-state evidence unavailable"


def test_an_incoming_stored_object_signed_under_a_retired_key_is_refused(
    release_repo, monkeypatch
) -> None:
    _, _, make = release_repo
    retired_private, retired_public = _new_key_pair()
    active, _ = make("us-active", [B, P1])
    # The incoming file verifies under the current key, so object_identity passes;
    # only its stored copy is signed under the retired key the provider lists.
    obj, path = make("us-next", [B, P1, P2])
    details = [
        _signed_detail(sign_release_object(obj, private_key=retired_private), published_at=_LATER),
        _signed_detail(active, published_at=_EARLIER),
    ]
    rows = [_changed_row(_STATUTE, "us-active", active["content_sha256"])]
    results = _provider_results(
        release_repo,
        monkeypatch,
        "us-next",
        obj,
        path,
        rows,
        details,
        legacy_public_keys=(retired_public,),
    )
    assert [result.name for result in results] == _ACTIVATE_NAMES
    by_name = _by_name(results)
    assert by_name["object_identity"].passed, by_name["object_identity"].evidence
    assert "of 'us-next' does not verify: release object signature is invalid" in (
        by_name["scope_monotonicity"].evidence
    )
    for result in results[2:]:
        assert (result.passed, result.warning) == (False, False), result.evidence


_REFUSED_KEYS = {
    "not_json": "AXIOM_CORPUS_RELEASE_LEGACY_PUBLIC_KEYS",
    "not_list": "AXIOM_CORPUS_RELEASE_LEGACY_PUBLIC_KEYS",
    "duplicate": "AXIOM_CORPUS_RELEASE_LEGACY_PUBLIC_KEYS",
    "bad_key": "AXIOM_CORPUS_RELEASE_LEGACY_PUBLIC_KEYS",
    "current_listed": "must not list the current release public key",
    "current_listed_as_pem": "must not list the current release public key",
    "current_pem_listed_raw": "must not list the current release public key",
    "two_spellings": "must list each public key once, in any spelling",
    "malformed_current": r"AXIOM_CORPUS_RELEASE_PUBLIC_KEY \(or RELEASE_TRUST_ROOT\) is not",
}


@pytest.mark.parametrize(
    "value",
    ["unset", "valid", "valid_pem", "malformed_current_empty", *_REFUSED_KEYS],
)
def test_the_gate_reads_retired_keys_as_the_publisher_does(
    release_repo, monkeypatch, value: str
) -> None:
    root, public, make = release_repo
    _install_active_manifest(root, "us-active", B, P1)
    obj, path = make("us-next", [B, P1, P2])
    rows = [_layered_row(_STATUTE, [B.version, P1.version], B.version)]
    retired = _new_key_pair()[1]
    recorded: list[tuple[str, ...]] = []

    def recorder(_args: Namespace, _public_key: str, legacy_public_keys: tuple[str, ...] = ()):
        recorded.append(tuple(legacy_public_keys))
        return lambda _release_object: rows

    monkeypatch.setattr(gate, "_supabase_active_state_provider", recorder)
    current = {
        "current_pem_listed_raw": _public_pem(public),
        "malformed_current": "not-a-key",
        "malformed_current_empty": "not-a-key",
    }.get(value, public)
    monkeypatch.setenv("AXIOM_CORPUS_RELEASE_PUBLIC_KEY", current)
    # The publisher's variable, named literally.
    env = "AXIOM_CORPUS_RELEASE_LEGACY_PUBLIC_KEYS"
    raw = {
        "unset": None,
        "malformed_current_empty": "[]",
        "valid": json.dumps([retired]),
        "valid_pem": json.dumps([_public_pem(retired)]),
        "not_json": "not json",
        "not_list": json.dumps("key"),
        "duplicate": json.dumps([retired, retired]),
        "bad_key": json.dumps(["not-a-key"]),
        "current_listed": json.dumps([retired, public]),
        "current_listed_as_pem": json.dumps([_public_pem(public)]),
        "current_pem_listed_raw": json.dumps([public]),
        "two_spellings": json.dumps([retired, _public_pem(retired)]),
        "malformed_current": json.dumps([retired]),
    }[value]
    if raw is None:
        monkeypatch.delenv(env, raising=False)
    else:
        monkeypatch.setenv(env, raw)
    argv = [
        "--release-object",
        str(path),
        "--release",
        "us-next",
        "--content-sha",
        obj["content_sha256"],
        "--repo-root",
        str(root),
        "--mode",
        "activate",
    ]
    if value in ("unset", "valid", "valid_pem"):
        assert gate.main(argv) == 0
        expected = () if value == "unset" else (canonical_release_public_key(retired),)
        assert recorded == [expected]
    elif value == "malformed_current_empty":
        # An empty list leaves nothing to compare, so the malformed current key
        # reaches object_identity and fails it, as it does with the variable unset.
        assert gate.main(argv) == 1
        assert recorded == [()]
    else:
        with pytest.raises(SystemExit, match=_REFUSED_KEYS[value]):
            gate.main(argv)
        assert recorded == []


# A null current_release_name means no active pointer serves the pair, so the row
# carries no evidence of an active release; a row that does contradicts itself.
_NULL_POINTER = {
    "jurisdiction": "us",
    "document_class": "statute",
    "changes": True,
    "current_release_name": None,
}
_NULL_POINTER_EVIDENCE = {
    "versions_and_base": (
        {"current_versions": [B.version, P1.version], "current_base_version": B.version},
        "current_versions ['2026-04-29', '2026-07-26-p1'], current_base_version '2026-04-29'",
    ),
    "versions_only": ({"current_versions": [P1.version]}, "current_versions ['2026-07-26-p1']"),
    "base_only": (
        {"current_versions": [], "current_base_version": B.version},
        "current_base_version '2026-04-29'",
    ),
    "digest_only": (
        {"current_versions": [], "current_content_sha256": "a" * 64},
        f"current_content_sha256 '{'a' * 64}'",
    ),
    "published_only": (
        {"current_versions": [], "current_published_at": _EARLIER},
        f"current_published_at '{_EARLIER}'",
    ),
    "falsy_base": ({"current_versions": [], "current_base_version": ""}, "current_base_version ''"),
    "null_versions": ({"current_versions": None}, "current_versions None"),
}


def _null_pointer_failure(stray: str) -> str:
    return (
        "us/statute: current_release_name is null, so no release serves the pair, but the "
        f"row carries active-release evidence: {stray}"
    )


@pytest.mark.parametrize("variant", list(_NULL_POINTER_EVIDENCE))
def test_a_null_pointer_with_active_evidence_fails_base_carry_forward(
    release_repo, variant: str
) -> None:
    _, _, make = release_repo
    fields, stray = _NULL_POINTER_EVIDENCE[variant]
    rows = [{**_NULL_POINTER, **fields}]
    obj, path = make("us-new", [P1, P2])
    for allow_regression in (False, True):
        results = _activate(
            release_repo, "us-new", obj, path, rows, allow_regression=allow_regression
        )
        result = _by_name(results)["base_carry_forward"]
        assert (result.passed, result.warning) == (False, False)
        assert result.evidence == _null_pointer_failure(stray)


def test_a_null_pointer_with_active_evidence_fails_base_only_pair(release_repo) -> None:
    fields, stray = _NULL_POINTER_EVIDENCE["versions_and_base"]
    _, _, results = _results(release_repo, "us-new", [B], [{**_NULL_POINTER, **fields}])
    by_name = _by_name(results)
    for name in ("base_only_pair", "base_carry_forward"):
        assert (by_name[name].passed, by_name[name].warning) == (False, False)
        assert by_name[name].evidence == _null_pointer_failure(stray)


def test_a_contradictory_offline_preview_fails_the_cli(release_repo, capsys, monkeypatch) -> None:
    root, public, make = release_repo
    obj, path = make("us-new", [P1, P2])
    fields, _ = _NULL_POINTER_EVIDENCE["versions_and_base"]
    active_path = root / "active-state.json"
    active_path.write_text(json.dumps([{**_NULL_POINTER, **fields}]))
    monkeypatch.setenv("AXIOM_CORPUS_RELEASE_PUBLIC_KEY", public)
    exit_code = gate.main(
        [
            "--release-object",
            str(path),
            "--release",
            "us-new",
            "--content-sha",
            obj["content_sha256"],
            "--repo-root",
            str(root),
            "--mode",
            "activate",
            "--active-state-file",
            str(active_path),
        ]
    )
    output = capsys.readouterr().out
    assert exit_code == 1
    assert re.findall(r"^\| (\w+) \| (PASS|FAIL|WARN) \|", output, re.MULTILINE) == [
        ("object_identity", "PASS"),
        ("cut_plan_provenance", "PASS"),
        ("scope_monotonicity", "PASS"),
        ("no_orphan", "PASS"),
        ("base_carry_forward", "FAIL"),
        ("base_only_pair", "PASS"),
        ("primary_frontier", "FAIL"),
    ]


def test_a_null_pointer_in_the_provider_shape_displaces_nothing(release_repo, monkeypatch) -> None:
    # The live provider's null row: a null digest, empty versions and the incoming
    # publication time. It displaces nothing, so every check passes.
    root, public, make = release_repo
    plain, _ = make("us-plain", [R1])
    obj, path = make("us-new-pair", [B, R1])
    rows = [
        {
            "jurisdiction": "us",
            "document_class": "statute",
            "changes": True,
            "current_release_name": None,
            "current_content_sha256": None,
        },
        _changed_row(_REGULATION, "us-plain", plain["content_sha256"]),
    ]
    details = [
        _signed_detail(plain, published_at=_EARLIER),
        _signed_detail(obj, published_at=_LATER),
    ]
    provide = _fake_supabase_provider(monkeypatch, rows, details, [], public_key=public)
    statute = next(row for row in provide(obj) if row["document_class"] == "statute")
    assert statute == {
        "jurisdiction": "us",
        "document_class": "statute",
        "changes": True,
        "current_release_name": None,
        "current_content_sha256": None,
        "current_versions": [],
        "incoming_published_at": _LATER,
    }
    results = gate.run_gate(
        release_object_path=path,
        release="us-new-pair",
        content_sha=obj["content_sha256"],
        repo_root=root,
        mode="activate",
        public_key=public,
        active_state_provider=provide,
    )
    assert [result.name for result in results] == _ACTIVATE_NAMES
    assert all(result.passed and not result.warning for result in results), _evidence(results)
    assert _by_name(results)["base_only_pair"].evidence == (
        "1 base-only incoming pair(s): 1 displace no active primary scope"
    )
