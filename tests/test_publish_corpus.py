"""Hermetic tests for the named-release publication controller."""

from __future__ import annotations

import importlib.util
import json
import sys
from base64 import b64encode
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.models import ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.navigation_supabase import NavigationSupabaseWriteReport
from axiom_corpus.corpus.r2 import R2Config
from axiom_corpus.corpus.supabase import StagedScopeCounts, SupabaseLoadReport
from axiom_corpus.release.manifest import ReleaseManifestError
from axiom_corpus.release.publication import R2ReadbackReport

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_publish_script():
    path = REPO_ROOT / "scripts" / "publish_corpus.py"
    spec = importlib.util.spec_from_file_location("publish_corpus", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["publish_corpus"] = module
    spec.loader.exec_module(module)
    return module


publish = _load_publish_script()


def _keys() -> tuple[str, str]:
    private = Ed25519PrivateKey.generate()
    return (
        b64encode(
            private.private_bytes(
                serialization.Encoding.Raw,
                serialization.PrivateFormat.Raw,
                serialization.NoEncryption(),
            )
        ).decode(),
        b64encode(
            private.public_key().public_bytes(
                serialization.Encoding.Raw,
                serialization.PublicFormat.Raw,
            )
        ).decode(),
    )


def _tree(tmp_path: Path) -> tuple[Path, Path, Path, tuple[str, str, str]]:
    root = tmp_path / "repo"
    base = root / "data" / "corpus"
    store = CorpusArtifactStore(base)
    scope = ("nz", "statute", "2026-07-10-nz-rulespec")
    source = store.source_path(*scope, "act.html")
    source_sha = store.write_text(source, "<p>Official text.</p>")
    source_rel = source.relative_to(base).as_posix()
    store.write_inventory(
        store.inventory_path(*scope),
        [
            SourceInventoryItem(
                citation_path="nz/statute/act/1",
                source_path=source_rel,
                sha256=source_sha,
            )
        ],
    )
    store.write_provisions(
        store.provisions_path(*scope),
        [
            ProvisionRecord(
                jurisdiction=scope[0],
                document_class=scope[1],
                version=scope[2],
                citation_path="nz/statute/act/1",
                body="Official text.",
                source_path=source_rel,
                source_as_of="2026-07-10",
                expression_date="2026-07-10",
            )
        ],
    )
    store.write_json(
        store.coverage_path(*scope),
        {
            "complete": True,
            "source_count": 1,
            "provision_count": 1,
            "matched_count": 1,
            "missing_from_provisions": [],
            "extra_provisions": [],
        },
    )
    selector = root / "manifests" / "releases" / "nz-rulespec-2026-07-10.json"
    selector.parent.mkdir(parents=True)
    selector.write_text(
        json.dumps(
            {
                "name": "nz-rulespec-2026-07-10",
                "scopes": [
                    {
                        "jurisdiction": scope[0],
                        "document_class": scope[1],
                        "version": scope[2],
                    }
                ],
            }
        )
    )
    return root, base, selector, scope


def _config() -> R2Config:
    return R2Config(
        bucket="axiom-corpus",
        endpoint_url="https://example.r2.cloudflarestorage.com",
        access_key_id="key",
        secret_access_key="secret",
    )


def _fixed_git(monkeypatch) -> None:
    import axiom_corpus.release.manifest as manifest

    monkeypatch.setattr(
        manifest,
        "_git_provenance",
        lambda root: {"commit": "a" * 40, "committed_at": "2026-07-10T00:00:00Z"},
    )


def _readback_for(content: dict, *, uploaded: int | None = None) -> R2ReadbackReport:
    artifacts = content["artifacts"]
    uploaded_count = len(artifacts) if uploaded is None else uploaded
    return R2ReadbackReport(
        "axiom-corpus",
        len(artifacts),
        sum(entry["bytes"] for entry in artifacts),
        uploaded_count,
        len(artifacts) - uploaded_count,
        tuple(entry["r2_key"] for entry in artifacts),
    )


def test_dry_run_is_local_and_explicit(tmp_path: Path, monkeypatch) -> None:
    root, base, selector, _ = _tree(tmp_path)
    _fixed_git(monkeypatch)

    plan = publish.plan_named_release(
        repo_root=root,
        base=base,
        selector_path=selector,
        r2_bucket="axiom-corpus",
    )

    assert plan == {
        "dry_run": True,
        "release": "nz-rulespec-2026-07-10",
        "selector": str(selector),
        "scope_count": 1,
        "artifact_count": 4,
        "provision_rows": 1,
    }


def test_publication_orders_all_validation_before_activation(tmp_path: Path, monkeypatch) -> None:
    root, base, selector, scope = _tree(tmp_path)
    _fixed_git(monkeypatch)
    private, public = _keys()
    calls: list[str] = []
    real_validate = publish.validate_release

    def validated(*args, **kwargs):
        calls.append("deep-validate")
        return real_validate(*args, **kwargs)

    monkeypatch.setattr(publish, "validate_release", validated)

    def stage_artifacts(*args, **kwargs):
        calls.append("r2-readback")
        return _readback_for(kwargs["release_content"])

    monkeypatch.setattr(publish, "stage_release_artifacts", stage_artifacts)
    monkeypatch.setattr(
        publish,
        "load_provisions_to_supabase",
        lambda *args, **kwargs: calls.append("stage-provisions")
        or SupabaseLoadReport(rows_total=1, rows_loaded=1, chunk_count=1),
    )
    monkeypatch.setattr(
        publish,
        "write_navigation_nodes_to_supabase",
        lambda *args, **kwargs: calls.append("stage-navigation")
        or NavigationSupabaseWriteReport(1, 1, 1, (scope,), 0, 0),
    )
    monkeypatch.setattr(
        publish,
        "fetch_staged_release_scope_counts",
        lambda *args, **kwargs: calls.append("exact-counts") or {scope: StagedScopeCounts(1, 1)},
    )

    def stage_object(release_object, **kwargs):
        calls.append("signed-object-readback")
        assert release_object["signature"]["algorithm"] == "ed25519"
        return f"releases/{release_object['release']}/{release_object['content_sha256']}.json"

    monkeypatch.setattr(publish, "stage_signed_release_object", stage_object)
    monkeypatch.setattr(
        publish,
        "activate_corpus_release",
        lambda release_object, **kwargs: calls.append("atomic-activate")
        or {
            "active": True,
            "release": release_object["release"],
            "content_sha256": release_object["content_sha256"],
        },
    )

    report = publish.publish_named_release(
        repo_root=root,
        base=base,
        selector_path=selector,
        supabase_url="https://example.supabase.co",
        service_key="service",
        r2_config=_config(),
        private_key=private,
        public_key=public,
    )

    assert calls == [
        "deep-validate",
        "r2-readback",
        "stage-provisions",
        "stage-navigation",
        "exact-counts",
        "deep-validate",
        "signed-object-readback",
        "atomic-activate",
    ]
    assert report.activation["active"] is True
    assert report.release_object["content"]["validation"]["passed"] is True


def test_count_mismatch_never_signs_or_activates(tmp_path: Path, monkeypatch) -> None:
    root, base, selector, scope = _tree(tmp_path)
    _fixed_git(monkeypatch)
    private, public = _keys()
    activated = False
    monkeypatch.setattr(
        publish,
        "stage_release_artifacts",
        lambda *args, **kwargs: _readback_for(kwargs["release_content"]),
    )
    monkeypatch.setattr(
        publish,
        "load_provisions_to_supabase",
        lambda *args, **kwargs: SupabaseLoadReport(1, 1, 1),
    )
    monkeypatch.setattr(
        publish,
        "write_navigation_nodes_to_supabase",
        lambda *args, **kwargs: NavigationSupabaseWriteReport(1, 1, 1, (scope,), 0, 0),
    )
    monkeypatch.setattr(
        publish,
        "fetch_staged_release_scope_counts",
        lambda *args, **kwargs: {scope: StagedScopeCounts(0, 0)},
    )

    def activate(*args, **kwargs):
        nonlocal activated
        activated = True
        return {}

    monkeypatch.setattr(publish, "activate_corpus_release", activate)
    with pytest.raises(ReleaseManifestError, match="exact staged provision/navigation counts"):
        publish.publish_named_release(
            repo_root=root,
            base=base,
            selector_path=selector,
            supabase_url="https://example.supabase.co",
            service_key="service",
            r2_config=_config(),
            private_key=private,
            public_key=public,
        )
    assert activated is False


def test_private_public_key_mismatch_never_activates(tmp_path: Path, monkeypatch) -> None:
    root, base, selector, scope = _tree(tmp_path)
    _fixed_git(monkeypatch)
    private, _ = _keys()
    _, wrong_public = _keys()
    monkeypatch.setattr(
        publish,
        "stage_release_artifacts",
        lambda *args, **kwargs: _readback_for(kwargs["release_content"]),
    )
    monkeypatch.setattr(
        publish,
        "load_provisions_to_supabase",
        lambda *args, **kwargs: SupabaseLoadReport(1, 1, 1),
    )
    monkeypatch.setattr(
        publish,
        "write_navigation_nodes_to_supabase",
        lambda *args, **kwargs: NavigationSupabaseWriteReport(1, 1, 1, (scope,), 0, 0),
    )
    monkeypatch.setattr(
        publish,
        "fetch_staged_release_scope_counts",
        lambda *args, **kwargs: {scope: StagedScopeCounts(1, 1)},
    )
    monkeypatch.setattr(
        publish,
        "activate_corpus_release",
        lambda *args, **kwargs: pytest.fail("activation must not run"),
    )

    with pytest.raises(ReleaseManifestError, match="signature is invalid"):
        publish.publish_named_release(
            repo_root=root,
            base=base,
            selector_path=selector,
            supabase_url="https://example.supabase.co",
            service_key="service",
            r2_config=_config(),
            private_key=private,
            public_key=wrong_public,
        )


def test_publisher_contains_no_legacy_escape_hatches() -> None:
    source = (REPO_ROOT / "scripts" / "publish_corpus.py").read_text()
    for forbidden in (
        "--synthesize-missing-parents",
        "--no-auto-register",
        "--stage",
        "allow_refresh_failure=True",
        'release_name="current"',
        "--all",
        "--range",
        "--since",
    ):
        assert forbidden not in source


def test_signed_validation_evidence_is_retry_stable(tmp_path: Path) -> None:
    _root, base, selector, scope = _tree(tmp_path)
    release = publish.ReleaseManifest.load(selector)
    report = publish.validate_release(base, release)
    counts = {scope: 1}
    actual_counts = {scope: StagedScopeCounts(1, 1)}
    first = publish._validation_attestation(
        report,
        r2_report=R2ReadbackReport("axiom-corpus", 4, 100, 4, 0, ("a", "b")),
        expected_counts=counts,
        actual_counts=actual_counts,
    )
    retry = publish._validation_attestation(
        report,
        r2_report=R2ReadbackReport("axiom-corpus", 4, 100, 0, 4, ("a", "b")),
        expected_counts=counts,
        actual_counts=actual_counts,
    )

    assert first == retry
