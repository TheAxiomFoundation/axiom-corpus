import json
from pathlib import Path

import pytest

from axiom_corpus.corpus.releases import (
    COMPLETE_EXPRESSION_DATES_PROFILE,
    ReleaseManifest,
    ReleaseScope,
    resolve_release_manifest_path,
)


def test_release_manifest_loads_scope_keys(tmp_path):
    path = tmp_path / "nz-rulespec-v1.json"
    path.write_text(
        json.dumps(
            {
                "name": "nz-rulespec-v1",
                "scopes": [
                    {
                        "jurisdiction": "us-co",
                        "document_class": "policy",
                        "version": "2026-04-30",
                    }
                ],
            }
        )
    )

    manifest = ReleaseManifest.load(path)

    assert manifest.name == "nz-rulespec-v1"
    assert manifest.scope_keys == (("us-co", "policy", "2026-04-30"),)
    assert manifest.quality_profile is None
    assert manifest.requires_complete_expression_dates is False


def test_release_manifest_loads_supported_quality_profile(tmp_path):
    path = tmp_path / "nz-rulespec-v2.json"
    path.write_text(
        json.dumps(
            {
                "name": "nz-rulespec-v2",
                "quality_profile": COMPLETE_EXPRESSION_DATES_PROFILE,
                "scopes": [
                    {
                        "jurisdiction": "nz",
                        "document_class": "statute",
                        "version": "v2",
                    }
                ],
            }
        )
    )

    manifest = ReleaseManifest.load(path)

    assert manifest.quality_profile == COMPLETE_EXPRESSION_DATES_PROFILE
    assert manifest.requires_complete_expression_dates is True


def test_release_manifest_rejects_unsupported_quality_profile(tmp_path):
    path = tmp_path / "nz-rulespec-v2.json"
    path.write_text(
        json.dumps(
            {
                "name": "nz-rulespec-v2",
                "quality_profile": "unknown-profile",
                "scopes": [
                    {
                        "jurisdiction": "nz",
                        "document_class": "statute",
                        "version": "v2",
                    }
                ],
            }
        )
    )

    with pytest.raises(ValueError, match="unsupported quality_profile"):
        ReleaseManifest.load(path)


def test_release_manifest_rejects_duplicate_scopes(tmp_path):
    path = tmp_path / "nz-rulespec-v1.json"
    scope = {
        "jurisdiction": "us-co",
        "document_class": "policy",
        "version": "2026-04-30",
    }
    path.write_text(json.dumps({"name": "nz-rulespec-v1", "scopes": [scope, scope]}))

    with pytest.raises(ValueError, match="duplicate scope"):
        ReleaseManifest.load(path)


def test_resolve_release_manifest_path_uses_only_tracked_selector_directory():
    assert resolve_release_manifest_path("nz-rulespec-v1") == Path(
        "manifests/releases/nz-rulespec-v1.json"
    )


def test_release_manifest_rejects_mutable_current_name(tmp_path):
    path = tmp_path / "current.json"
    path.write_text(json.dumps({"name": "current", "scopes": []}))

    with pytest.raises(ValueError, match="reserved"):
        ReleaseManifest.load(path)


def test_release_manifest_requires_explicit_name(tmp_path):
    path = tmp_path / "nz-rulespec-v1.json"
    path.write_text(json.dumps({"scopes": []}))

    with pytest.raises(ValueError, match="explicit name"):
        ReleaseManifest.load(path)


def test_release_manifest_requires_non_empty_exact_scope_schema(tmp_path):
    empty = tmp_path / "empty.json"
    empty.write_text(json.dumps({"name": "nz-v1", "scopes": []}))
    with pytest.raises(ValueError, match="non-empty scopes"):
        ReleaseManifest.load(empty)

    extra = tmp_path / "extra.json"
    extra.write_text(
        json.dumps(
            {
                "name": "nz-v1",
                "scopes": [
                    {
                        "jurisdiction": "nz",
                        "document_class": "statute",
                        "version": "v1",
                        "active": True,
                    }
                ],
            }
        )
    )
    with pytest.raises(ValueError, match="unsupported fields"):
        ReleaseManifest.load(extra)


def test_release_manifest_rejects_scope_path_traversal(tmp_path):
    path = tmp_path / "nz-v1.json"
    path.write_text(
        json.dumps(
            {
                "name": "nz-v1",
                "scopes": [
                    {
                        "jurisdiction": "../nz",
                        "document_class": "statute",
                        "version": "v1",
                    }
                ],
            }
        )
    )

    with pytest.raises(ValueError, match="invalid jurisdiction"):
        ReleaseManifest.load(path)


def test_release_scope_constructor_rejects_invalid_identity() -> None:
    with pytest.raises(ValueError, match="invalid jurisdiction"):
        ReleaseScope("../nz", "statute", "v1")
    with pytest.raises(ValueError, match="invalid document_class"):
        ReleaseScope("nz", "bogus", "v1")


def test_release_selector_rejects_invalid_top_level_and_name(tmp_path):
    top_extra = tmp_path / "top-extra.json"
    top_extra.write_text(json.dumps({"name": "nz-v1", "scopes": [], "active": True}))
    with pytest.raises(ValueError, match="unsupported fields"):
        ReleaseManifest.load(top_extra)

    with pytest.raises(ValueError, match="Release names must"):
        ReleaseManifest(name="NZ V1", scopes=())
    with pytest.raises(ValueError, match="Release names must"):
        ReleaseManifest(name="nz.rulespec", scopes=())
    with pytest.raises(ValueError, match="Release names must"):
        ReleaseManifest(name="nz_rulespec", scopes=())
    with pytest.raises(ValueError, match="Release names must"):
        ReleaseManifest(name="nz--rulespec", scopes=())


def test_release_selector_loader_rejects_missing_non_object_and_bad_scopes(tmp_path):
    with pytest.raises(FileNotFoundError, match="not found"):
        ReleaseManifest.load(tmp_path / "missing.json")

    non_object = tmp_path / "non-object.json"
    non_object.write_text("[]")
    with pytest.raises(ValueError, match="must be a JSON object"):
        ReleaseManifest.load(non_object)

    non_object_scope = tmp_path / "non-object-scope.json"
    non_object_scope.write_text(json.dumps({"name": "nz-v1", "scopes": [None]}))
    with pytest.raises(ValueError, match="non-object scope"):
        ReleaseManifest.load(non_object_scope)

    bad_class = tmp_path / "bad-class.json"
    bad_class.write_text(
        json.dumps(
            {
                "name": "nz-v1",
                "scopes": [{"jurisdiction": "nz", "document_class": "bogus", "version": "v1"}],
            }
        )
    )
    with pytest.raises(ValueError, match="invalid document_class"):
        ReleaseManifest.load(bad_class)

    missing_field = tmp_path / "missing-field.json"
    missing_field.write_text(
        json.dumps(
            {
                "name": "nz-v1",
                "scopes": [{"jurisdiction": "nz", "document_class": "statute", "version": ""}],
            }
        )
    )
    with pytest.raises(ValueError, match="missing version"):
        ReleaseManifest.load(missing_field)


def test_release_selector_resolver_accepts_explicit_json_path(tmp_path):
    path = tmp_path / "selector.json"
    assert resolve_release_manifest_path(path) == path
