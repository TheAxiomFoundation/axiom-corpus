"""Hermetic tests for the named-release publication controller."""

from __future__ import annotations

import importlib.util
import json
import sys
from base64 import b64decode, b64encode
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.models import ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.navigation import build_navigation_nodes
from axiom_corpus.corpus.navigation_supabase import NavigationSupabaseWriteReport
from axiom_corpus.corpus.projection_digest import (
    navigation_projection_sha256,
    provision_projection_sha256,
)
from axiom_corpus.corpus.r2 import R2Config
from axiom_corpus.corpus.supabase import (
    ReleasedScopeObject,
    StagedScopeEvidence,
    SupabaseLoadReport,
    iter_supabase_rows,
)
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


@pytest.fixture(autouse=True)
def _no_prior_released_scopes(monkeypatch):
    monkeypatch.setattr(
        publish,
        "fetch_released_scope_objects",
        lambda release, **kwargs: dict.fromkeys(release.scope_keys, ()),
    )


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


def _public_pem(public_key: str) -> str:
    loaded = Ed25519PublicKey.from_public_bytes(b64decode(public_key))
    return loaded.public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()


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
                "quality_profile": "complete-expression-dates-v1",
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
    monkeypatch.setattr(manifest, "_require_tracked_release_inputs", lambda *args, **kwargs: None)


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


def _scope_evidence(base: Path, scope: tuple[str, str, str]) -> StagedScopeEvidence:
    records = tuple(
        ProvisionRecord.from_mapping(json.loads(line))
        for line in (base / "provisions" / scope[0] / scope[1] / f"{scope[2]}.jsonl")
        .read_text()
        .splitlines()
        if line.strip()
    )
    navigation = build_navigation_nodes(records)
    return StagedScopeEvidence(
        provision_rows=len(records),
        navigation_rows=len(navigation),
        provision_projection_sha256=provision_projection_sha256(iter_supabase_rows(records)),
        navigation_projection_sha256=navigation_projection_sha256(
            node.to_supabase_row() for node in navigation
        ),
    )


def _signed_prior_object(
    root: Path,
    base: Path,
    selector: Path,
    scope: tuple[str, str, str],
    private_key: str,
) -> dict:
    release = publish.ReleaseManifest.load(selector)
    provisional = publish.build_release_content(
        root,
        release=release,
        validation={"passed": True, "phase": "preflight"},
    )
    evidence = {scope: _scope_evidence(base, scope)}
    validation = publish._validation_attestation(
        publish.validate_release(base, release),
        quality_profile="complete-expression-dates-v1",
        r2_report=_readback_for(provisional),
        expected_evidence=evidence,
        actual_evidence=evidence,
    )
    content = publish.build_release_content(root, release=release, validation=validation)
    return publish.sign_release_object(
        publish.build_unsigned_release_object(content),
        private_key=private_key,
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


def test_dry_run_rejects_legacy_quality_profile(tmp_path: Path, monkeypatch) -> None:
    root, base, selector, _ = _tree(tmp_path)
    _fixed_git(monkeypatch)
    payload = json.loads(selector.read_text())
    payload.pop("quality_profile")
    selector.write_text(json.dumps(payload))

    with pytest.raises(ReleaseManifestError, match="requires quality_profile"):
        publish.plan_named_release(
            repo_root=root,
            base=base,
            selector_path=selector,
            r2_bucket="axiom-corpus",
        )


def test_publication_rejects_legacy_profile_before_external_writes(
    tmp_path: Path, monkeypatch
) -> None:
    root, base, selector, _ = _tree(tmp_path)
    payload = json.loads(selector.read_text())
    payload.pop("quality_profile")
    selector.write_text(json.dumps(payload))
    monkeypatch.setattr(
        publish,
        "validate_release",
        lambda *args, **kwargs: pytest.fail("legacy selector must fail before validation"),
    )
    monkeypatch.setattr(
        publish,
        "stage_release_artifacts",
        lambda *args, **kwargs: pytest.fail("legacy selector must not write to R2"),
    )
    private, public = _keys()

    with pytest.raises(ReleaseManifestError, match="requires quality_profile"):
        publish.publish_named_release(
            repo_root=root,
            base=base,
            selector_path=selector,
            supabase_url="https://example.supabase.co",
            service_key="service",
            access_token="management",
            r2_config=_config(),
            private_key=private,
            public_key=public,
        )


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
        "fetch_staged_release_scope_evidence",
        lambda *args, **kwargs: calls.append("exact-evidence")
        or {scope: _scope_evidence(base, scope)},
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
        access_token="management",
        r2_config=_config(),
        private_key=private,
        public_key=public,
        activate=True,
    )

    assert calls == [
        "deep-validate",
        "r2-readback",
        "stage-provisions",
        "stage-navigation",
        "exact-evidence",
        "deep-validate",
        "signed-object-readback",
        "atomic-activate",
    ]
    assert report.activation["active"] is True
    assert report.release_object["content"]["validation"]["passed"] is True


def test_publish_does_not_activate_by_default(tmp_path: Path, monkeypatch) -> None:
    # A routine publish must not move serving: activation repoints the per-scope
    # serving map and can displace another jurisdiction (axiom-corpus#408). It is
    # opt-in via activate=True / the --activate flag.
    root, base, selector, scope = _tree(tmp_path)
    _fixed_git(monkeypatch)
    private, public = _keys()
    monkeypatch.setattr(
        publish,
        "stage_release_artifacts",
        lambda *args, **kwargs: _readback_for(kwargs["release_content"]),
    )
    monkeypatch.setattr(
        publish,
        "load_provisions_to_supabase",
        lambda *args, **kwargs: SupabaseLoadReport(rows_total=1, rows_loaded=1, chunk_count=1),
    )
    monkeypatch.setattr(
        publish,
        "write_navigation_nodes_to_supabase",
        lambda *args, **kwargs: NavigationSupabaseWriteReport(1, 1, 1, (scope,), 0, 0),
    )
    monkeypatch.setattr(
        publish,
        "fetch_staged_release_scope_evidence",
        lambda *args, **kwargs: {scope: _scope_evidence(base, scope)},
    )
    monkeypatch.setattr(
        publish,
        "stage_signed_release_object",
        lambda release_object, **kwargs: (
            f"releases/{release_object['release']}/{release_object['content_sha256']}.json"
        ),
    )
    monkeypatch.setattr(
        publish,
        "activate_corpus_release",
        lambda *args, **kwargs: pytest.fail("publish must not activate without activate=True"),
    )

    report = publish.publish_named_release(
        repo_root=root,
        base=base,
        selector_path=selector,
        supabase_url="https://example.supabase.co",
        service_key="service",
        access_token="management",
        r2_config=_config(),
        private_key=private,
        public_key=public,
    )

    assert report.activation is None
    assert report.to_mapping()["activation"] is None
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
        "fetch_staged_release_scope_evidence",
        lambda *args, **kwargs: {
            scope: StagedScopeEvidence(
                0,
                0,
                _scope_evidence(base, scope).provision_projection_sha256,
                _scope_evidence(base, scope).navigation_projection_sha256,
            )
        },
    )

    def activate(*args, **kwargs):
        nonlocal activated
        activated = True
        return {}

    monkeypatch.setattr(publish, "activate_corpus_release", activate)
    with pytest.raises(ReleaseManifestError, match="exact staged provision/navigation projection"):
        publish.publish_named_release(
            repo_root=root,
            base=base,
            selector_path=selector,
            supabase_url="https://example.supabase.co",
            service_key="service",
            access_token="management",
            r2_config=_config(),
            private_key=private,
            public_key=public,
            activate=True,
        )
    assert activated is False


def test_private_public_key_mismatch_never_activates(tmp_path: Path, monkeypatch) -> None:
    root, base, selector, scope = _tree(tmp_path)
    _fixed_git(monkeypatch)
    private, matching_public = _keys()
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
        "fetch_staged_release_scope_evidence",
        lambda *args, **kwargs: {scope: _scope_evidence(base, scope)},
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
            access_token="management",
            r2_config=_config(),
            private_key=private,
            public_key=wrong_public,
            legacy_public_keys=(matching_public,),
            activate=True,
        )


@pytest.mark.parametrize("successor", [False, True])
@pytest.mark.parametrize("rotated_key", [False, True])
def test_released_scope_retry_or_successor_reuses_exact_immutable_rows(
    tmp_path: Path,
    monkeypatch,
    successor: bool,
    rotated_key: bool,
) -> None:
    root, base, selector, scope = _tree(tmp_path)
    _fixed_git(monkeypatch)
    private, public = _keys()
    prior_private, prior_public = _keys() if rotated_key else (private, public)
    prior_object = _signed_prior_object(root, base, selector, scope, prior_private)
    target_selector = selector
    if successor:
        target_selector = selector.with_name("nz-rulespec-2026-07-11.json")
        target_selector.write_text(
            json.dumps(
                    {
                        "name": "nz-rulespec-2026-07-11",
                        "quality_profile": "complete-expression-dates-v1",
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
    monkeypatch.setattr(
        publish,
        "fetch_released_scope_objects",
        lambda *args, **kwargs: {
            scope: (
                ReleasedScopeObject(
                    scope_key=scope,
                    release_name=str(prior_object["release"]),
                    content_sha256=str(prior_object["content_sha256"]),
                    release_object=prior_object,
                ),
            )
        },
    )
    monkeypatch.setattr(
        publish,
        "stage_release_artifacts",
        lambda *args, **kwargs: _readback_for(kwargs["release_content"], uploaded=0),
    )
    monkeypatch.setattr(
        publish,
        "load_provisions_to_supabase",
        lambda *args, **kwargs: pytest.fail("released provision rows must not be rewritten"),
    )
    monkeypatch.setattr(
        publish,
        "write_navigation_nodes_to_supabase",
        lambda *args, **kwargs: pytest.fail("released navigation rows must not be rewritten"),
    )
    monkeypatch.setattr(
        publish,
        "fetch_staged_release_scope_evidence",
        lambda *args, **kwargs: {scope: _scope_evidence(base, scope)},
    )
    monkeypatch.setattr(
        publish,
        "stage_signed_release_object",
        lambda release_object, **kwargs: (
            f"releases/{release_object['release']}/{release_object['content_sha256']}.json"
        ),
    )
    monkeypatch.setattr(
        publish,
        "activate_corpus_release",
        lambda release_object, **kwargs: {
            "active": True,
            "release": release_object["release"],
            "content_sha256": release_object["content_sha256"],
        },
    )

    report = publish.publish_named_release(
        repo_root=root,
        base=base,
        selector_path=target_selector,
        supabase_url="https://example.supabase.co",
        service_key="service",
        access_token="management",
        r2_config=_config(),
        private_key=private,
        public_key=public,
        legacy_public_keys=(prior_public,) if rotated_key else (),
        activate=True,
    )

    assert report.provision_rows == 1
    assert report.activation["active"] is True


def test_released_scope_signed_by_untrusted_legacy_key_is_rejected(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root, base, selector, scope = _tree(tmp_path)
    _fixed_git(monkeypatch)
    prior_private, _prior_public = _keys()
    _current_private, current_public = _keys()
    prior_object = _signed_prior_object(root, base, selector, scope, prior_private)
    release = publish.ReleaseManifest.load(selector)
    content = publish.build_release_content(
        root,
        release=release,
        validation={"passed": True, "phase": "preflight"},
    )
    released = {
        scope: (
            ReleasedScopeObject(
                scope_key=scope,
                release_name=str(prior_object["release"]),
                content_sha256=str(prior_object["content_sha256"]),
                release_object=prior_object,
            ),
        )
    }

    with pytest.raises(ReleaseManifestError, match="untrusted prior release object"):
        publish._require_safe_released_scope_reuse(
            content,
            released,
            public_keys=(current_public,),
        )


def test_invalid_prior_object_is_not_treated_as_a_key_mismatch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root, base, selector, scope = _tree(tmp_path)
    _fixed_git(monkeypatch)
    private, public = _keys()
    prior_object = _signed_prior_object(root, base, selector, scope, private)
    prior_object["signature"]["value"] = "not-base64"

    with pytest.raises(ReleaseManifestError, match="signature encoding is invalid"):
        publish._verifies_with_any_key(prior_object, (public,))


@pytest.mark.parametrize(
    "raw",
    ["not-json", "{}", '[""]', '["duplicate", "duplicate"]', '["key", 1]'],
)
def test_legacy_public_key_environment_is_strict_json(monkeypatch, raw: str) -> None:
    monkeypatch.setenv(publish.RELEASE_OBJECT_LEGACY_PUBLIC_KEYS_ENV, raw)

    with pytest.raises(ReleaseManifestError, match="JSON array|unique JSON array"):
        publish._legacy_public_keys_from_env()


def test_legacy_public_key_environment_accepts_unique_keys(monkeypatch) -> None:
    _first_private, first = _keys()
    _second_private, second = _keys()
    monkeypatch.setenv(
        publish.RELEASE_OBJECT_LEGACY_PUBLIC_KEYS_ENV,
        json.dumps([first, second]),
    )

    assert publish._legacy_public_keys_from_env() == (first, second)


def test_publication_rejects_malformed_legacy_key_before_external_writes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root, base, selector, _scope = _tree(tmp_path)
    private, public = _keys()
    monkeypatch.setattr(
        publish,
        "validate_release",
        lambda *args, **kwargs: pytest.fail("invalid trust configuration must fail first"),
    )

    with pytest.raises(ReleaseManifestError, match="public key must be raw base64 or PEM"):
        publish.publish_named_release(
            repo_root=root,
            base=base,
            selector_path=selector,
            supabase_url="https://example.supabase.co",
            service_key="service",
            access_token="management",
            r2_config=_config(),
            private_key=private,
            public_key=public,
            legacy_public_keys=("not-a-key",),
        )


def test_trusted_release_keys_reject_canonical_duplicates() -> None:
    _current_private, current = _keys()
    _legacy_private, legacy = _keys()

    with pytest.raises(ReleaseManifestError, match="canonically unique"):
        publish._trusted_release_public_keys(current, (legacy, _public_pem(legacy)))

    with pytest.raises(ReleaseManifestError, match="must not be a legacy key"):
        publish._trusted_release_public_keys(current, (_public_pem(current),))


def test_released_scope_with_different_signed_projection_aborts_before_dml(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root, base, selector, scope = _tree(tmp_path)
    _fixed_git(monkeypatch)
    private, public = _keys()
    prior_object = _signed_prior_object(root, base, selector, scope, private)
    prior_object["content"]["scopes"][0]["provision_projection_sha256"] = "f" * 64
    prior_evidence = prior_object["content"]["validation"]["supabase_projection_evidence"][0]
    prior_evidence["expected_provision_projection_sha256"] = "f" * 64
    prior_evidence["actual_provision_projection_sha256"] = "f" * 64
    prior_content = prior_object["content"]
    prior_object = publish.sign_release_object(
        publish.build_unsigned_release_object(prior_content),
        private_key=private,
    )
    monkeypatch.setattr(
        publish,
        "stage_release_artifacts",
        lambda *args, **kwargs: _readback_for(kwargs["release_content"]),
    )
    monkeypatch.setattr(
        publish,
        "fetch_released_scope_objects",
        lambda *args, **kwargs: {
            scope: (
                ReleasedScopeObject(
                    scope,
                    str(prior_object["release"]),
                    str(prior_object["content_sha256"]),
                    prior_object,
                ),
            )
        },
    )
    monkeypatch.setattr(
        publish,
        "load_provisions_to_supabase",
        lambda *args, **kwargs: pytest.fail("mismatch must abort before DML"),
    )

    with pytest.raises(ReleaseManifestError, match="immutable released scope differs"):
        publish.publish_named_release(
            repo_root=root,
            base=base,
            selector_path=selector,
            supabase_url="https://example.supabase.co",
            service_key="service",
            access_token="management",
            r2_config=_config(),
            private_key=private,
            public_key=public,
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
    actual_evidence = {scope: _scope_evidence(base, scope)}
    first = publish._validation_attestation(
        report,
        quality_profile="complete-expression-dates-v1",
        r2_report=R2ReadbackReport("axiom-corpus", 4, 100, 4, 0, ("a", "b")),
        expected_evidence=actual_evidence,
        actual_evidence=actual_evidence,
    )
    retry = publish._validation_attestation(
        report,
        quality_profile="complete-expression-dates-v1",
        r2_report=R2ReadbackReport("axiom-corpus", 4, 100, 0, 4, ("a", "b")),
        expected_evidence=actual_evidence,
        actual_evidence=actual_evidence,
    )

    assert first == retry
