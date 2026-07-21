"""Unit coverage for the activation wrapper guards (no database required)."""

from __future__ import annotations

import pytest

from axiom_corpus.corpus import supabase


def _release_object(scopes: list[dict[str, str]]) -> dict[str, object]:
    content = {"release": "r", "scopes": scopes}
    return {
        "schema_version": "axiom-corpus/release-object/v2",
        "release": "r",
        "content_sha256": "a" * 64,
        "content": content,
        "signature": {"algorithm": "ed25519", "key_id": "axiom-corpus-release-v2", "value": "x"},
    }


def test_scope_completeness_accepts_exact_pair_cover() -> None:
    release = _release_object(
        [
            {"jurisdiction": "us", "document_class": "statute", "version": "v1"},
            {"jurisdiction": "us", "document_class": "statute", "version": "v2"},
            {"jurisdiction": "nz", "document_class": "regulation", "version": "v1"},
        ]
    )
    result = {
        "scope_count": 3,
        "scopes": {
            "activated": [{"jurisdiction": "us", "document_class": "statute"}],
            "reaffirmed": [{"jurisdiction": "nz", "document_class": "regulation"}],
        },
    }
    supabase._require_complete_activation_scopes(result, release)


def test_scope_completeness_rejects_missing_pair() -> None:
    release = _release_object(
        [
            {"jurisdiction": "us", "document_class": "statute", "version": "v1"},
            {"jurisdiction": "nz", "document_class": "regulation", "version": "v1"},
        ]
    )
    result = {
        "scope_count": 2,
        "scopes": {
            "activated": [{"jurisdiction": "us", "document_class": "statute"}],
            "reaffirmed": [],
        },
    }
    with pytest.raises(RuntimeError, match="do not match the release's signed pairs"):
        supabase._require_complete_activation_scopes(result, release)


def test_scope_completeness_rejects_duplicate_pair() -> None:
    release = _release_object(
        [{"jurisdiction": "us", "document_class": "statute", "version": "v1"}]
    )
    result = {
        "scope_count": 1,
        "scopes": {
            "activated": [{"jurisdiction": "us", "document_class": "statute"}],
            "reaffirmed": [{"jurisdiction": "us", "document_class": "statute"}],
        },
    }
    with pytest.raises(RuntimeError, match="duplicate"):
        supabase._require_complete_activation_scopes(result, release)


def test_scope_completeness_rejects_wrong_count() -> None:
    release = _release_object(
        [{"jurisdiction": "us", "document_class": "statute", "version": "v1"}]
    )
    result = {
        "scope_count": 5,
        "scopes": {
            "activated": [{"jurisdiction": "us", "document_class": "statute"}],
            "reaffirmed": [],
        },
    }
    with pytest.raises(RuntimeError, match="scope_count"):
        supabase._require_complete_activation_scopes(result, release)


def test_project_ref_guard_blocks_mismatch(monkeypatch) -> None:
    called = False

    def _fail_post(*args, **kwargs):  # pragma: no cover - must not run
        nonlocal called
        called = True
        raise AssertionError("management API must not be called on ref mismatch")

    monkeypatch.setattr(supabase, "_management_api_post_json_with_curl", _fail_post)
    monkeypatch.setattr(supabase, "verify_release_object", lambda *a, **k: None)
    with pytest.raises(RuntimeError, match="expected 'other-project'"):
        supabase.activate_corpus_release(
            _release_object([{"jurisdiction": "us", "document_class": "statute", "version": "v1"}]),
            access_token="t",
            public_key="k",
            supabase_url="https://swocpijqqahhuwtuahwc.supabase.co",
            expected_project_ref="other-project",
        )
    assert called is False
