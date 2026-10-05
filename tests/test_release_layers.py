"""Signed scope layers: selectors, release objects, validation, and reuse.

A base scope is served underneath the primary scopes of its release. These
tests pin the one canonical encoding of each layer, the v3/v4 split, and the
differential property that a release without a base scope is byte-identical to
what the publisher produced before layers existed (the committed fixture was
generated from origin/main at the commit recorded in it).
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from base64 import b64encode
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from hypothesis import given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.corpus_locks import CorpusLock, LockEntry, write_lock
from axiom_corpus.corpus.models import ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.navigation import (
    build_navigation_nodes,
    merge_layered_parent_paths,
    scope_parent_paths,
)
from axiom_corpus.corpus.release_quality import (
    ReleaseValidationReport,
    _LayeredCitationOwners,
    validate_release,
)
from axiom_corpus.corpus.releases import (
    COMPLETE_EXPRESSION_DATES_PROFILE,
    LAYER_BASE,
    LAYER_PRIMARY,
    ReleaseManifest,
    ReleaseScope,
    _parse_scope,
)
from axiom_corpus.release.manifest import (
    RELEASE_OBJECT_SCHEMA_V3,
    RELEASE_OBJECT_SCHEMA_V4,
    ReleaseManifestError,
    build_release_content,
    build_unsigned_release_object,
    canonical_json_bytes,
    canonical_release_object_bytes,
    release_content_sha256,
    selector_sha256,
    serialize_release_object,
    sign_release_object,
    verify_release_object,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "release_layers" / "pre_layer_v3_release.json"
SIGNING_KEY = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
PRIVATE_KEY = b64encode(
    SIGNING_KEY.private_bytes(
        serialization.Encoding.Raw,
        serialization.PrivateFormat.Raw,
        serialization.NoEncryption(),
    )
).decode()
PUBLIC_KEY = b64encode(
    SIGNING_KEY.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
).decode()
GIT_ENV = {
    "GIT_AUTHOR_NAME": "Fixture",
    "GIT_AUTHOR_EMAIL": "fixture@example.com",
    "GIT_COMMITTER_NAME": "Fixture",
    "GIT_COMMITTER_EMAIL": "fixture@example.com",
    "GIT_AUTHOR_DATE": "2026-09-27T00:00:00+00:00",
    "GIT_COMMITTER_DATE": "2026-09-27T00:00:00+00:00",
}
FIXTURE_RELEASE = "fx-rulespec-2026-09-27"
FIXTURE_SCOPES = (
    ("fx", "statute", "2026-09-27-fx-statute", "1"),
    ("fx", "regulation", "2026-09-27-fx-regulation", "7"),
)


def _load_publish_script() -> Any:
    path = REPO_ROOT / "scripts" / "publish_corpus.py"
    spec = importlib.util.spec_from_file_location("publish_corpus_layers", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["publish_corpus_layers"] = module
    spec.loader.exec_module(module)
    return module


publish = _load_publish_script()


def _write_scope(
    store: CorpusArtifactStore,
    jurisdiction: str,
    document_class: str,
    version: str,
    title: str,
    sections: Sequence[str] = ("1",),
) -> None:
    """Write one complete scope: a title row and its sections, one XML source."""
    source = store.source_path(jurisdiction, document_class, version, f"title-{title}.xml")
    source_sha = store.write_text(source, f"<title n='{title}'>Official text.</title>")
    source_rel = source.relative_to(store.root).as_posix()
    root_path = f"{jurisdiction}/{document_class}/{title}"
    section_paths = [f"{root_path}/{section}" for section in sections]
    store.write_inventory(
        store.inventory_path(jurisdiction, document_class, version),
        [
            SourceInventoryItem(citation_path=path, source_path=source_rel, sha256=source_sha)
            for path in (root_path, *section_paths)
        ],
    )
    records = [
        ProvisionRecord(
            jurisdiction=jurisdiction,
            document_class=document_class,
            citation_path=root_path,
            version=version,
            heading=f"Title {title}",
            kind="title",
            source_path=source_rel,
            expression_date="2026-09-01",
        )
    ]
    for section, path in zip(sections, section_paths, strict=True):
        records.append(
            ProvisionRecord(
                jurisdiction=jurisdiction,
                document_class=document_class,
                citation_path=path,
                parent_citation_path=root_path,
                version=version,
                heading=f"Section {section}",
                body="Official text — π." if section == "1" else f"Section {section} text.",
                kind="section",
                source_path=source_rel,
                expression_date="2026-09-01",
            )
        )
    store.write_provisions(store.provisions_path(jurisdiction, document_class, version), records)
    store.write_json(
        store.coverage_path(jurisdiction, document_class, version),
        {
            "complete": True,
            "source_count": len(records),
            "provision_count": len(records),
            "matched_count": len(records),
            "missing_from_provisions": [],
            "extra_provisions": [],
        },
    )


def _commit(root: Path, selector: dict[str, Any]) -> ReleaseManifest:
    path = root / "manifests" / "releases" / f"{selector['name']}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(selector, indent=2) + "\n")
    env = {**os.environ, **GIT_ENV}
    if not (root / ".git").exists():
        subprocess.run(["git", "init", "-q", str(root)], check=True, env=env)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True, env=env)
    subprocess.run(
        ["git", "-C", str(root), "-c", "commit.gpgsign=false", "commit", "-qm", "fixture"],
        check=True,
        env=env,
    )
    return ReleaseManifest.load(path)


def _fixture_tree(root: Path) -> ReleaseManifest:
    """Rebuild exactly the tree the committed pre-layer fixture was generated from."""
    store = CorpusArtifactStore(root / "data" / "corpus")
    for jurisdiction, document_class, version, title in FIXTURE_SCOPES:
        _write_scope(store, jurisdiction, document_class, version, title)
    return _commit(
        root,
        {
            "name": FIXTURE_RELEASE,
            "quality_profile": COMPLETE_EXPRESSION_DATES_PROFILE,
            "scopes": [
                {"jurisdiction": j, "document_class": dc, "version": v}
                for j, dc, v, _title in FIXTURE_SCOPES
            ],
        },
    )


def _layered_tree(root: Path, *, name: str = "fx-rulespec-2026-09-28") -> ReleaseManifest:
    """The fixture's two primary scopes plus a base scope under fx/statute.

    The base scope carries the primary title and section 1 (the overlap the
    serving view resolves) and base-only sections 2 and 3.
    """
    store = CorpusArtifactStore(root / "data" / "corpus")
    for jurisdiction, document_class, version, title in FIXTURE_SCOPES:
        _write_scope(store, jurisdiction, document_class, version, title)
    _write_scope(store, "fx", "statute", "2026-04-29-fx-base", "1", ("1", "2", "3"))
    return _commit(
        root,
        {
            "name": name,
            "quality_profile": COMPLETE_EXPRESSION_DATES_PROFILE,
            "scopes": [
                {"jurisdiction": j, "document_class": dc, "version": v}
                for j, dc, v, _title in FIXTURE_SCOPES
            ]
            + [
                {
                    "jurisdiction": "fx",
                    "document_class": "statute",
                    "version": "2026-04-29-fx-base",
                    "layer": "base",
                }
            ],
        },
    )


def _validation_for(content: dict[str, Any]) -> dict[str, Any]:
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
            for scope in sorted(
                content["scopes"],
                key=lambda s: (s["jurisdiction"], s["document_class"], s["version"]),
            )
        ],
    }


def _content(root: Path, release: ReleaseManifest) -> dict[str, Any]:
    content = build_release_content(
        root,
        release=release,
        validation={"passed": True},
        created_at="2026-09-27T00:00:00Z",
    )
    content["validation"] = _validation_for(content)
    return content


def _sign_without_validation(unsigned: dict[str, Any]) -> dict[str, Any]:
    """Sign arbitrary bytes, so verification (not signing) is what rejects them."""
    signature = SIGNING_KEY.sign(canonical_release_object_bytes(unsigned))
    return {
        **unsigned,
        "signature": {
            "algorithm": "ed25519",
            "key_id": "axiom-corpus-release-v2",
            "value": b64encode(signature).decode(),
        },
    }


def _reseal(payload: dict[str, Any], *, schema_version: str | None = None) -> dict[str, Any]:
    unsigned = {key: value for key, value in payload.items() if key != "signature"}
    if schema_version is not None:
        unsigned["schema_version"] = schema_version
    unsigned["content_sha256"] = release_content_sha256(unsigned["content"])
    return _sign_without_validation(unsigned)


# ---------------------------------------------------------------------------
# Selectors: one canonical encoding per layer.
# ---------------------------------------------------------------------------


def test_scope_layer_defaults_to_primary_with_a_three_field_encoding() -> None:
    primary = ReleaseScope("us", "statute", "2026-08-03")
    base = ReleaseScope("us", "statute", "2026-04-29", layer=LAYER_BASE)

    assert primary.layer == LAYER_PRIMARY
    assert primary.to_selector_mapping() == {
        "jurisdiction": "us",
        "document_class": "statute",
        "version": "2026-08-03",
    }
    assert base.to_selector_mapping()["layer"] == "base"
    assert base.key == ("us", "statute", "2026-04-29")
    with pytest.raises(ValueError, match="invalid layer"):
        ReleaseScope("us", "statute", "v1", layer="secondary")


@pytest.mark.parametrize("layer", ["primary", "Base", "", None, 1, ["base"]])
def test_selector_accepts_only_the_base_layer_spelling(tmp_path: Path, layer: object) -> None:
    path = tmp_path / "us-rulespec-layered.json"
    path.write_text(
        json.dumps(
            {
                "name": "us-rulespec-layered",
                "scopes": [
                    {
                        "jurisdiction": "us",
                        "document_class": "statute",
                        "version": "2026-04-29",
                        "layer": layer,
                    }
                ],
            }
        )
    )

    with pytest.raises(ValueError, match="layer must be 'base' or absent"):
        ReleaseManifest.load(path)


def test_selector_loads_a_base_scope(tmp_path: Path) -> None:
    path = tmp_path / "us-rulespec-layered.json"
    path.write_text(
        json.dumps(
            {
                "name": "us-rulespec-layered",
                "scopes": [
                    {"jurisdiction": "us", "document_class": "statute", "version": "2026-08-03"},
                    {
                        "jurisdiction": "us",
                        "document_class": "statute",
                        "version": "2026-04-29",
                        "layer": "base",
                    },
                ],
            }
        )
    )

    manifest = ReleaseManifest.load(path)

    assert [scope.layer for scope in manifest.scopes] == ["primary", "base"]
    assert manifest.has_base_scope is True
    assert manifest.scope_keys == (
        ("us", "statute", "2026-08-03"),
        ("us", "statute", "2026-04-29"),
    )


def test_selector_allows_one_base_scope_per_pair(tmp_path: Path) -> None:
    scopes = (
        ReleaseScope("us", "statute", "2026-04-29", layer=LAYER_BASE),
        ReleaseScope("us", "statute", "2026-05-01", layer=LAYER_BASE),
    )
    with pytest.raises(ValueError, match="more than one base scope for us/statute"):
        ReleaseManifest(name="us-two-bases", scopes=scopes)

    path = tmp_path / "us-two-bases.json"
    path.write_text(
        json.dumps(
            {
                "name": "us-two-bases",
                "scopes": [scope.to_selector_mapping() for scope in scopes],
            }
        )
    )
    with pytest.raises(ValueError, match="more than one base scope"):
        ReleaseManifest.load(path)

    # One base per pair: a base scope in another pair is fine.
    ReleaseManifest(
        name="us-bases",
        scopes=(scopes[0], ReleaseScope("us", "regulation", "2026-05-01", layer=LAYER_BASE)),
    )


def test_one_version_cannot_be_both_base_and_primary() -> None:
    with pytest.raises(ValueError, match="duplicate scope"):
        ReleaseManifest(
            name="us-same-version",
            scopes=(
                ReleaseScope("us", "statute", "2026-04-29"),
                ReleaseScope("us", "statute", "2026-04-29", layer=LAYER_BASE),
            ),
        )


_JURISDICTIONS = st.sampled_from(["us", "us-ca", "nz"])
_DOCUMENT_CLASSES = st.sampled_from(["statute", "regulation", "guidance"])
_VERSIONS = st.sampled_from(["2026-04-29", "2026-05-01", "2026-08-03", "v1", "v2"])


@st.composite
def _manifests(draw: st.DrawFn, *, allow_base: bool = True) -> ReleaseManifest:
    keys = draw(
        st.lists(
            st.tuples(_JURISDICTIONS, _DOCUMENT_CLASSES, _VERSIONS),
            min_size=1,
            max_size=8,
            unique=True,
        )
    )
    scopes = []
    base_pairs: set[tuple[str, str]] = set()
    for jurisdiction, document_class, version in keys:
        base = (
            allow_base and (jurisdiction, document_class) not in base_pairs and draw(st.booleans())
        )
        if base:
            base_pairs.add((jurisdiction, document_class))
        scopes.append(
            ReleaseScope(
                jurisdiction,
                document_class,
                version,
                layer=LAYER_BASE if base else LAYER_PRIMARY,
            )
        )
    profile = draw(st.sampled_from([None, COMPLETE_EXPRESSION_DATES_PROFILE]))
    return ReleaseManifest(name="hypothesis-release", scopes=tuple(scopes), quality_profile=profile)


def _reference_selector_sha256(release: ReleaseManifest) -> str:
    """selector_sha256 as it was before layers existed (origin/main f1916d73)."""
    selector: dict[str, Any] = {
        "name": release.name,
        "scopes": [
            {
                "jurisdiction": scope.jurisdiction,
                "document_class": scope.document_class,
                "version": scope.version,
            }
            for scope in release.scopes
        ],
    }
    if release.quality_profile is not None:
        selector["quality_profile"] = release.quality_profile
    return hashlib.sha256(canonical_json_bytes(selector)).hexdigest()


@settings(max_examples=150, deadline=None)
@given(_manifests())
def test_selector_encoding_round_trips_every_layer(release: ReleaseManifest) -> None:
    payload = {
        "name": release.name,
        "scopes": [scope.to_selector_mapping() for scope in release.scopes],
    }
    if release.quality_profile is not None:
        payload["quality_profile"] = release.quality_profile
    for raw, scope in zip(payload["scopes"], release.scopes, strict=True):
        assert ("layer" in raw) is scope.is_base

    loaded = ReleaseManifest(
        name=release.name,
        scopes=tuple(
            _parse_scope(raw, manifest_path=Path("<generated>")) for raw in payload["scopes"]
        ),
        quality_profile=release.quality_profile,
    )

    assert loaded == release
    assert selector_sha256(loaded) == selector_sha256(release)


@settings(max_examples=150, deadline=None)
@given(_manifests(allow_base=False))
def test_selector_sha256_without_base_scopes_equals_pre_layer_reference(
    release: ReleaseManifest,
) -> None:
    assert selector_sha256(release) == _reference_selector_sha256(release)


@settings(max_examples=150, deadline=None)
@given(_manifests(), st.data())
def test_selector_sha256_covers_every_scope_layer(
    release: ReleaseManifest,
    data: st.DataObject,
) -> None:
    index = data.draw(st.integers(min_value=0, max_value=len(release.scopes) - 1))
    flipped = list(release.scopes)
    scope = flipped[index]
    flipped[index] = ReleaseScope(
        scope.jurisdiction,
        scope.document_class,
        scope.version,
        layer=LAYER_PRIMARY if scope.is_base else LAYER_BASE,
    )
    try:
        other = ReleaseManifest(
            name=release.name,
            scopes=tuple(flipped),
            quality_profile=release.quality_profile,
        )
    except ValueError:
        return  # flipping to base would give the pair a second base scope
    assert selector_sha256(other) != selector_sha256(release)


# ---------------------------------------------------------------------------
# Differential: releases without a base scope are byte-identical to pre-PR.
# ---------------------------------------------------------------------------


def _fixture() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text())


def test_tracked_release_selectors_hash_exactly_as_before_layers() -> None:
    expected = _fixture()["tracked_selector_sha256"]
    assert len(expected) >= 100
    checked = 0
    for relative, digest in expected.items():
        path = REPO_ROOT / relative
        if not path.exists():
            continue
        release = ReleaseManifest.load(path)
        assert release.has_base_scope is False
        assert selector_sha256(release) == digest, relative
        checked += 1
    assert checked == len(expected)


def test_release_without_base_scope_is_byte_identical_to_pre_layer_v3(tmp_path: Path) -> None:
    fixture = _fixture()
    release = _fixture_tree(tmp_path / "repo")

    content = _content(tmp_path / "repo", release)
    unsigned = build_unsigned_release_object(content)
    signed = sign_release_object(unsigned, private_key=PRIVATE_KEY)

    assert selector_sha256(release) == fixture["release_selector_sha256"]
    assert content == fixture["content"]
    assert unsigned["schema_version"] == RELEASE_OBJECT_SCHEMA_V3
    assert serialize_release_object(signed).decode("ascii") == fixture["signed_release_object"]
    verify_release_object(signed, public_key=PUBLIC_KEY)


def test_pre_layer_v3_object_still_verifies() -> None:
    signed = json.loads(_fixture()["signed_release_object"])

    verify_release_object(signed, public_key=PUBLIC_KEY)
    assert signed["schema_version"] == RELEASE_OBJECT_SCHEMA_V3


# ---------------------------------------------------------------------------
# Release-object v4: signed layers.
# ---------------------------------------------------------------------------


def _layered_signed(tmp_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    _release, content, signed = _layered_release(tmp_path)
    return content, signed


def _layered_release(
    tmp_path: Path,
) -> tuple[ReleaseManifest, dict[str, Any], dict[str, Any]]:
    release = _layered_tree(tmp_path / "repo")
    content = _content(tmp_path / "repo", release)
    signed = sign_release_object(build_unsigned_release_object(content), private_key=PRIVATE_KEY)
    return release, content, signed


def test_layered_release_emits_v4_with_base_layer_only_on_base_scope(tmp_path: Path) -> None:
    release, _content_value, signed = _layered_release(tmp_path)

    assert signed["schema_version"] == RELEASE_OBJECT_SCHEMA_V4
    layers = {scope["version"]: scope.get("layer") for scope in signed["content"]["scopes"]}
    assert layers == {
        "2026-09-27-fx-statute": None,
        "2026-09-27-fx-regulation": None,
        "2026-04-29-fx-base": "base",
    }
    assert signed["content"]["selector_sha256"] == selector_sha256(release)
    assert selector_sha256(release) != _reference_selector_sha256(release)
    verify_release_object(signed, public_key=PUBLIC_KEY)


def test_layered_successor_keeps_historical_primary_scope_identity(tmp_path: Path) -> None:
    """A primary scope released in v3 is reusable byte-for-byte by a v4 successor."""
    historical = _fixture()["content"]
    content, _signed = _layered_signed(tmp_path)

    for jurisdiction, document_class, version, _title in FIXTURE_SCOPES:
        key = (jurisdiction, document_class, version)
        assert publish._scope_publication_identity(
            content, key
        ) == publish._scope_publication_identity(historical, key)


BASE_KEY = ("fx", "statute", "2026-04-29-fx-base")


def _locked_base_tree(root: Path, *, tamper: bool = False) -> ReleaseManifest:
    """The layered tree with the base scope's bytes outside git.

    Corpus bytes may live outside git, pinned by committed lock files
    (docs/corpus-storage.md); a restored base scope's artifacts will. The
    primary scopes stay tracked. With ``tamper`` the lock pins other bytes for
    the base provisions file.
    """
    store = CorpusArtifactStore(root / "data" / "corpus")
    for jurisdiction, document_class, version, title in FIXTURE_SCOPES:
        _write_scope(store, jurisdiction, document_class, version, title)
    _write_scope(store, *BASE_KEY, "1", ("1", "2", "3"))
    stem = "/".join(BASE_KEY)
    base_files = sorted(
        path
        for prefix in ("sources", "inventory", "provisions", "coverage")
        for path in (root / "data" / "corpus" / prefix).rglob("*")
        if path.is_file()
        and path.relative_to(root / "data" / "corpus" / prefix).as_posix().startswith(stem)
    )
    entries = []
    for path in base_files:
        data = path.read_bytes()
        if tamper and path.suffix == ".jsonl":
            data += b"\n"
        entries.append(
            LockEntry(
                path.relative_to(root).as_posix(), hashlib.sha256(data).hexdigest(), len(data)
            )
        )
    write_lock(root, CorpusLock.from_entries(BASE_KEY, entries))
    (root / ".gitignore").write_text(f"data/corpus/*/{stem}*\n")
    return _commit(
        root,
        {
            "name": "fx-rulespec-2026-09-28",
            "quality_profile": COMPLETE_EXPRESSION_DATES_PROFILE,
            "scopes": [
                {"jurisdiction": j, "document_class": dc, "version": v}
                for j, dc, v, _title in FIXTURE_SCOPES
            ]
            + [
                dict(zip(("jurisdiction", "document_class", "version"), BASE_KEY, strict=True))
                | {"layer": "base"}
            ],
        },
    )


@pytest.fixture
def no_corpus_fetch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Keep corpus resolution off R2 and the developer's shared cache."""
    from axiom_corpus.corpus import content_store
    from axiom_corpus.corpus import resolver as resolver_module

    def refuse(cls: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("R2 is disabled in tests")

    monkeypatch.setattr(content_store.R2ObjectStore, "from_environment", classmethod(refuse))
    monkeypatch.setenv("AXIOM_CORPUS_CACHE", str(tmp_path / "cache"))
    monkeypatch.setattr(resolver_module, "_RESOLVERS", {})


@pytest.mark.usefixtures("no_corpus_fetch")
def test_lock_pinned_base_scope_builds_and_signs_v4_content(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    release = _locked_base_tree(repo)
    tracked = subprocess.run(
        ["git", "-C", str(repo), "ls-files"], check=True, capture_output=True, text=True
    ).stdout.split()
    assert not any("2026-04-29-fx-base" in path for path in tracked if path.startswith("data/"))
    assert ".axiom/corpus-locks/fx/statute/2026-04-29-fx-base.json" in tracked

    content = _content(repo, release)
    signed = sign_release_object(build_unsigned_release_object(content), private_key=PRIVATE_KEY)

    assert signed["schema_version"] == RELEASE_OBJECT_SCHEMA_V4
    base = [scope for scope in signed["content"]["scopes"] if scope.get("layer") == "base"]
    assert [(s["jurisdiction"], s["document_class"], s["version"]) for s in base] == [BASE_KEY]
    assert base[0]["provision_rows"] == 4
    assert any(
        entry["path"] == "data/corpus/provisions/fx/statute/2026-04-29-fx-base.jsonl"
        for entry in signed["content"]["artifacts"]
    )
    verify_release_object(signed, public_key=PUBLIC_KEY)


@pytest.mark.usefixtures("no_corpus_fetch")
def test_lock_pinned_base_scope_must_match_its_lock(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    release = _locked_base_tree(repo, tamper=True)

    with pytest.raises(ReleaseManifestError, match="pinned by a committed corpus lock"):
        _content(repo, release)


def test_v4_without_a_base_scope_fails_verification(tmp_path: Path) -> None:
    release = _fixture_tree(tmp_path / "repo")
    content = _content(tmp_path / "repo", release)
    v3 = build_unsigned_release_object(content)

    forged = _reseal(v3, schema_version=RELEASE_OBJECT_SCHEMA_V4)

    with pytest.raises(ReleaseManifestError, match="reserved for releases with at least one base"):
        verify_release_object(forged, public_key=PUBLIC_KEY)
    with pytest.raises(ReleaseManifestError, match="reserved for releases with at least one base"):
        sign_release_object(
            {**v3, "schema_version": RELEASE_OBJECT_SCHEMA_V4}, private_key=PRIVATE_KEY
        )


@pytest.mark.parametrize(
    "where",
    ["scope", "validation", "deep_validation", "artifact", "evidence", "content"],
)
def test_v3_object_with_a_layer_key_anywhere_fails_verification(
    tmp_path: Path,
    where: str,
) -> None:
    content, signed = _layered_signed(tmp_path)
    forged_content = copy.deepcopy(signed["content"])
    if where != "scope":
        for scope in forged_content["scopes"]:
            scope.pop("layer", None)
        forged_content["selector_sha256"] = _reference_selector_sha256(
            _fixture_like_manifest(forged_content)
        )
    target = {
        "scope": lambda c: c["scopes"][-1],
        "validation": lambda c: c["validation"],
        "deep_validation": lambda c: c["validation"]["deep_validation"],
        "artifact": lambda c: c["artifacts"][0],
        "evidence": lambda c: c["validation"]["supabase_projection_evidence"][0],
        "content": lambda c: c,
    }[where](forged_content)
    target["layer"] = "base"

    forged = _reseal({**signed, "content": forged_content}, schema_version=RELEASE_OBJECT_SCHEMA_V3)

    with pytest.raises(ReleaseManifestError):
        verify_release_object(forged, public_key=PUBLIC_KEY)


def _fixture_like_manifest(content: dict[str, Any]) -> ReleaseManifest:
    return ReleaseManifest(
        name=content["release"],
        scopes=tuple(
            ReleaseScope(
                scope["jurisdiction"],
                scope["document_class"],
                scope["version"],
                layer=scope.get("layer", LAYER_PRIMARY),
            )
            for scope in content["scopes"]
        ),
        quality_profile=content["quality_profile"],
    )


@pytest.mark.parametrize("layer", ["primary", "BASE", None, 0])
def test_v4_accepts_only_the_base_layer_spelling(tmp_path: Path, layer: object) -> None:
    _content_value, signed = _layered_signed(tmp_path)
    forged = copy.deepcopy(signed)
    forged["content"]["scopes"][0]["layer"] = layer

    with pytest.raises(ReleaseManifestError, match="unsupported layer"):
        verify_release_object(_reseal(forged), public_key=PUBLIC_KEY)


def test_v4_rejects_two_base_scopes_for_one_pair(tmp_path: Path) -> None:
    _content_value, signed = _layered_signed(tmp_path)
    forged = copy.deepcopy(signed)
    statute_primary = next(
        scope
        for scope in forged["content"]["scopes"]
        if scope["version"] == "2026-09-27-fx-statute"
    )
    statute_primary["layer"] = "base"

    with pytest.raises(ReleaseManifestError, match="more than one base scope for fx/statute"):
        verify_release_object(_reseal(forged), public_key=PUBLIC_KEY)


def test_signed_selector_covers_the_layer(tmp_path: Path) -> None:
    _content_value, signed = _layered_signed(tmp_path)
    tampered = copy.deepcopy(signed)
    tampered["content"]["scopes"][0]["layer"] = "base"
    for scope in tampered["content"]["scopes"][1:]:
        scope.pop("layer", None)

    # The content digest is recomputed, so only the signed selector digest can
    # notice that the base scope moved.
    with pytest.raises(ReleaseManifestError, match="selector sha256 does not match"):
        verify_release_object(_reseal(tampered), public_key=PUBLIC_KEY)
    with pytest.raises(ReleaseManifestError, match="content sha256 does not match"):
        verify_release_object(
            {**tampered, "content_sha256": signed["content_sha256"]},
            public_key=PUBLIC_KEY,
        )


# ---------------------------------------------------------------------------
# Scope reuse: the layer is part of an immutable scope's signed identity.
# ---------------------------------------------------------------------------


def test_released_scope_layer_cannot_change_on_reuse(tmp_path: Path) -> None:
    content, signed = _layered_signed(tmp_path)
    base_key = ("fx", "statute", "2026-04-29-fx-base")
    as_primary = copy.deepcopy(content)
    for scope in as_primary["scopes"]:
        if (scope["jurisdiction"], scope["document_class"], scope["version"]) == base_key:
            scope.pop("layer")

    released = {
        key: (
            publish.ReleasedScopeObject(
                scope_key=key,
                release_name=str(signed["release"]),
                content_sha256=str(signed["content_sha256"]),
                release_object=signed,
            ),
        )
        for key in (
            tuple(scope[field] for field in ("jurisdiction", "document_class", "version"))
            for scope in content["scopes"]
        )
    }

    publish._require_safe_released_scope_reuse(content, released, public_keys=(PUBLIC_KEY,))
    with pytest.raises(ReleaseManifestError, match="immutable released scope differs"):
        publish._require_safe_released_scope_reuse(
            as_primary,
            released,
            public_keys=(PUBLIC_KEY,),
        )


# ---------------------------------------------------------------------------
# Validation: citation uniqueness per layer.
# ---------------------------------------------------------------------------


def test_layered_release_validates_with_a_base_primary_overlap(tmp_path: Path) -> None:
    release = _layered_tree(tmp_path / "repo")

    report = validate_release(tmp_path / "repo" / "data" / "corpus", release)

    assert report.ok, report.to_mapping()
    assert report.error_count == 0


def _write_section_only_scope(
    store: CorpusArtifactStore, version: str, *, declared_parent: str | None
) -> None:
    """A primary scope with section 1/5 of title 1 and not the title itself."""
    source = store.source_path("fx", "statute", version, "title-1.xml")
    source_sha = store.write_text(source, "<title n='1'>Amended text.</title>")
    source_rel = source.relative_to(store.root).as_posix()
    path = "fx/statute/1/5"
    store.write_inventory(
        store.inventory_path("fx", "statute", version),
        [SourceInventoryItem(citation_path=path, source_path=source_rel, sha256=source_sha)],
    )
    store.write_provisions(
        store.provisions_path("fx", "statute", version),
        [
            ProvisionRecord(
                jurisdiction="fx",
                document_class="statute",
                citation_path=path,
                parent_citation_path=declared_parent,
                version=version,
                heading="Section 5",
                body="Section 5 text.",
                kind="section",
                source_path=source_rel,
                expression_date="2026-09-01",
            )
        ],
    )
    store.write_json(
        store.coverage_path("fx", "statute", version),
        {
            "complete": True,
            "source_count": 1,
            "provision_count": 1,
            "matched_count": 1,
            "missing_from_provisions": [],
            "extra_provisions": [],
        },
    )


@pytest.mark.parametrize(("declared_parent", "ok"), [("fx/statute/1", False), (None, True)])
def test_parent_closure_stays_per_scope_across_layers(
    tmp_path: Path, declared_parent: str | None, ok: bool
) -> None:
    """A row's parent id is versioned by the row's own scope, so a declared
    parent must be in that scope even when the base carries it. A section that
    leaves its title to the base declares no parent; serving places it."""
    store = CorpusArtifactStore(tmp_path / "data" / "corpus")
    _write_scope(store, "fx", "statute", "v-base", "1", ("1", "2"))
    _write_section_only_scope(store, "v-sections", declared_parent=declared_parent)
    release = ReleaseManifest(
        name="fx-section-over-base",
        scopes=(
            ReleaseScope("fx", "statute", "v-base", layer=LAYER_BASE),
            ReleaseScope("fx", "statute", "v-sections"),
        ),
        quality_profile=COMPLETE_EXPRESSION_DATES_PROFILE,
    )

    report = validate_release(store.root, release)

    assert report.ok is ok, report.to_mapping()
    codes = {(issue.code, issue.version) for issue in report.issues if issue.severity == "error"}
    assert codes == (set() if ok else {("missing_parent_citation", "v-sections")})


# ---------------------------------------------------------------------------
# Validation: how serving merges a layered pair's trees.
# ---------------------------------------------------------------------------

Rows = Sequence[tuple[str, str | None]]


def _write_tree_scope(store: CorpusArtifactStore, version: str, rows: Rows) -> None:
    """A complete fx/statute scope of (citation path, declared parent) rows."""
    source = store.source_path("fx", "statute", version, "statute.xml")
    source_sha = store.write_text(source, "<statute>Official text.</statute>")
    source_rel = source.relative_to(store.root).as_posix()
    store.write_inventory(
        store.inventory_path("fx", "statute", version),
        [
            SourceInventoryItem(citation_path=path, source_path=source_rel, sha256=source_sha)
            for path, _parent in rows
        ],
    )
    store.write_provisions(
        store.provisions_path("fx", "statute", version),
        [
            ProvisionRecord(
                jurisdiction="fx",
                document_class="statute",
                citation_path=path,
                parent_citation_path=parent,
                version=version,
                heading=f"Heading {path}",
                body=f"Text of {path}.",
                kind="section",
                source_path=source_rel,
                expression_date="2026-09-01",
            )
            for path, parent in rows
        ],
    )
    store.write_json(
        store.coverage_path("fx", "statute", version),
        {
            "complete": True,
            "source_count": len(rows),
            "provision_count": len(rows),
            "matched_count": len(rows),
            "missing_from_provisions": [],
            "extra_provisions": [],
        },
    )


def _validate_layered(
    tmp_path: Path, base: Rows | None, *primaries: Rows
) -> ReleaseValidationReport:
    store = CorpusArtifactStore(tmp_path / "data" / "corpus")
    scopes = []
    if base is not None:
        _write_tree_scope(store, "v-base", base)
        scopes.append(ReleaseScope("fx", "statute", "v-base", layer=LAYER_BASE))
    for index, rows in enumerate(primaries):
        _write_tree_scope(store, f"v-primary-{index}", rows)
        scopes.append(ReleaseScope("fx", "statute", f"v-primary-{index}"))
    return validate_release(
        store.root,
        ReleaseManifest(
            name="fx-layered",
            scopes=tuple(scopes),
            quality_profile=COMPLETE_EXPRESSION_DATES_PROFILE,
        ),
    )


def _layered_warnings(report: ReleaseValidationReport) -> list[tuple[str, str, str | None]]:
    assert report.ok and report.error_count == 0, report.to_mapping()
    return [
        (issue.code, issue.message, issue.version)
        for issue in report.issues
        if issue.code.startswith("layered_")
    ]


_BASE_TITLE_1 = (
    ("fx/statute/1", None),
    ("fx/statute/1/1", "fx/statute/1"),
    ("fx/statute/1/2", "fx/statute/1"),
)


def test_a_primary_root_under_no_served_ancestor_is_a_warning(tmp_path: Path) -> None:
    """A mistyped path (l for 1) would otherwise become a top-level document silently."""
    report = _validate_layered(tmp_path, _BASE_TITLE_1, (("fx/statute/l/5", None),))

    assert _layered_warnings(report) == [
        (
            "layered_primary_root_unattached",
            "fx/statute/l/5 is a root of its primary scope, and fx/statute serves neither "
            "it nor any ancestor path, so serving lists it as a new top-level document; "
            "check its citation path",
            "v-primary-0",
        )
    ]


def test_primary_roots_the_merge_attaches_raise_no_warning(tmp_path: Path) -> None:
    report = _validate_layered(
        tmp_path,
        _BASE_TITLE_1,
        # Under a base title, and a base twin's place.
        (("fx/statute/1/5", None), ("fx/statute/1/1", None)),
        # A primary title of its own, re-encoding the base title.
        (("fx/statute/1", None), ("fx/statute/1/2", "fx/statute/1")),
    )

    assert _layered_warnings(report) == []


def test_a_new_title_warns_once_and_its_sections_attach_to_it(tmp_path: Path) -> None:
    report = _validate_layered(
        tmp_path,
        _BASE_TITLE_1,
        (("fx/statute/9", None), ("fx/statute/9/1", "fx/statute/9")),
        (("fx/statute/9/2", None),),
    )

    assert [(code, version) for code, _message, version in _layered_warnings(report)] == [
        ("layered_primary_root_unattached", "v-primary-0")
    ]


def test_a_parent_cycle_between_the_layers_is_a_warning(tmp_path: Path) -> None:
    """The base puts b under a; the primary scope puts a under b."""
    report = _validate_layered(
        tmp_path,
        (
            ("fx/statute/1", None),
            ("fx/statute/1/a", "fx/statute/1"),
            ("fx/statute/1/b", "fx/statute/1/a"),
        ),
        (("fx/statute/1/a", "fx/statute/1/b"), ("fx/statute/1/b", None)),
    )

    assert _layered_warnings(report) == [
        (
            "layered_parent_cycle_broken",
            "the base and primary scopes of fx/statute disagree about parents, forming the "
            "cycle fx/statute/1/a -> fx/statute/1/b -> fx/statute/1/a; serving makes "
            "fx/statute/1/a a top-level document",
            "v-primary-0",
        )
    ]


def test_releases_without_a_base_scope_get_no_layered_warning(tmp_path: Path) -> None:
    report = _validate_layered(tmp_path, None, (("fx/statute/9", None),), _BASE_TITLE_1)

    assert _layered_warnings(report) == []


_TREE_PATHS = st.sampled_from(
    [
        "fx/statute/1",
        "fx/statute/1/a",
        "fx/statute/1/b",
        "fx/statute/1/a/i",
        "fx/statute/2",
        "fx/statute/2/a",
    ]
)
_TREE = st.lists(
    st.tuples(_TREE_PATHS, st.one_of(st.none(), _TREE_PATHS)),
    min_size=1,
    max_size=6,
    unique_by=lambda row: row[0],
)


@settings(max_examples=300, deadline=None)
@given(base=_TREE, primaries=st.lists(_TREE, max_size=3))
def test_the_merged_tree_is_a_forest_of_the_served_paths(
    base: list[tuple[str, str | None]], primaries: list[list[tuple[str, str | None]]]
) -> None:
    merged = merge_layered_parent_paths(
        scope_parent_paths(base), [scope_parent_paths(rows) for rows in primaries]
    )
    served = {path for path, _parent in base} | {path for rows in primaries for path, _ in rows}
    assert set(merged.parent_paths) == served
    for path in served:
        seen = set()
        cursor: str | None = path
        while cursor is not None:
            assert cursor not in seen, "parent cycle left in the merged tree"
            seen.add(cursor)
            cursor = merged.parent_paths[cursor]
    for cycle in merged.broken_cycles:
        assert cycle[0] == min(cycle)
        assert merged.parent_paths[cycle[0]] is None
    first_owner = {}
    for index, rows in enumerate(primaries):
        for path, _parent in rows:
            first_owner.setdefault(path, index)
    base_paths = {path for path, _parent in base}
    for index, path in merged.new_roots:
        assert first_owner[path] == index
        assert path not in base_paths
        assert not any(path.startswith(other + "/") for other in served)


@settings(max_examples=300, deadline=None)
@given(data=st.data())
def test_the_merge_equals_building_navigation_over_the_winning_records(
    data: st.DataObject,
) -> None:
    """Every declared parent the immediate path prefix, the base closed under
    ancestors, no primary scope skipping a level between two of its own paths:
    merging equals build_navigation_nodes over what is served. (A scope that
    skips one keeps its own parent, as serving does.)"""
    universe = [
        "fx/statute/1",
        "fx/statute/1/a",
        "fx/statute/1/b",
        "fx/statute/1/a/i",
        "fx/statute/2",
        "fx/statute/2/a",
    ]
    base_paths = set(data.draw(st.lists(st.sampled_from(universe), min_size=1)))
    base_paths |= {path.rsplit("/", 1)[0] for path in base_paths if path.count("/") > 2}
    base_paths |= {"/".join(path.split("/")[:3]) for path in base_paths}
    taken: set[str] = set()
    primaries: list[list[str]] = []
    for _index in range(data.draw(st.integers(0, 2))):
        chosen = set(data.draw(st.lists(st.sampled_from(universe)))) - taken
        for path in sorted(chosen, key=lambda path: path.count("/")):
            parts = path.split("/")
            ancestors = {"/".join(parts[:size]) for size in range(3, len(parts))}
            if ancestors & chosen and "/".join(parts[:-1]) not in chosen:
                chosen.discard(path)
        taken.update(chosen)
        primaries.append(sorted(chosen))

    def rows(paths: Sequence[str]) -> list[tuple[str, str | None]]:
        within = set(paths)
        return [
            (path, path.rsplit("/", 1)[0] if path.rsplit("/", 1)[0] in within else None)
            for path in sorted(paths)
        ]

    merged = merge_layered_parent_paths(
        scope_parent_paths(rows(sorted(base_paths))),
        [scope_parent_paths(rows(paths)) for paths in primaries],
    )
    winners = [
        ProvisionRecord(
            jurisdiction="fx",
            document_class="statute",
            citation_path=path,
            parent_citation_path=parent,
            version="v",
        )
        for path, parent in rows(sorted(base_paths | taken))
    ]
    built = {node.path: node.parent_path for node in build_navigation_nodes(winners)}
    assert merged.parent_paths == built
    assert merged.broken_cycles == ()


def test_same_path_in_two_primary_scopes_still_fails(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    store = CorpusArtifactStore(root / "data" / "corpus")
    _write_scope(store, "fx", "statute", "v-one", "1")
    _write_scope(store, "fx", "statute", "v-two", "1")
    release = ReleaseManifest(
        name="fx-two-primaries",
        scopes=(ReleaseScope("fx", "statute", "v-one"), ReleaseScope("fx", "statute", "v-two")),
        quality_profile=COMPLETE_EXPRESSION_DATES_PROFILE,
    )

    report = validate_release(store.root, release)

    codes = [issue.code for issue in report.issues]
    assert codes.count("duplicate_release_citation") == 2  # title and section 1


def test_base_primary_overlap_across_pairs_fails(tmp_path: Path) -> None:
    owners = _LayeredCitationOwners()
    base = ReleaseScope("us", "statute", "2026-04-29", layer=LAYER_BASE)
    primary = ReleaseScope("us", "regulation", "2026-08-03")

    assert owners.claim("us/statute/7/2011", base) is None
    conflict = owners.claim("us/statute/7/2011", primary)

    assert conflict is not None
    assert conflict[0] == "layered_citation_outside_pair"


_SCOPE_POOL = (
    ReleaseScope("us", "statute", "p1"),
    ReleaseScope("us", "statute", "p2"),
    ReleaseScope("us", "statute", "b1", layer=LAYER_BASE),
    ReleaseScope("us", "regulation", "p3"),
    ReleaseScope("us", "regulation", "b2", layer=LAYER_BASE),
)
_CLAIMS = st.lists(
    st.tuples(st.sampled_from(_SCOPE_POOL), st.sampled_from(["a", "b", "c"])),
    max_size=14,
)


def _declaratively_unambiguous(claims: Sequence[tuple[ReleaseScope, str]]) -> bool:
    """For every path: one scope per layer, and a base/primary overlap in one pair."""
    owners: dict[tuple[str, str], set[ReleaseScope]] = {}
    for scope, path in claims:
        owners.setdefault((scope.layer, path), set()).add(scope)
    for (layer, path), scopes in owners.items():
        if len(scopes) > 1:
            return False
        other = owners.get((LAYER_PRIMARY if layer == LAYER_BASE else LAYER_BASE, path))
        if other and {s.pair for s in scopes} != {s.pair for s in other}:
            return False
    return True


@settings(max_examples=300, deadline=None)
@given(_CLAIMS)
def test_layered_citation_owners_accept_exactly_the_unambiguous_releases(
    claims: list[tuple[ReleaseScope, str]],
) -> None:
    owners = _LayeredCitationOwners()
    conflicts = [owners.claim(path, scope) for scope, path in claims]

    assert (not any(conflicts)) is _declaratively_unambiguous(claims)


def _reference_primary_conflicts(
    claims: Sequence[tuple[ReleaseScope, str]],
) -> list[str | None]:
    """The single-layer uniqueness rule as it was before layers (origin/main)."""
    owners: dict[str, ReleaseScope] = {}
    messages: list[str | None] = []
    for scope, path in claims:
        owner = owners.get(path)
        if owner is not None and owner != scope:
            messages.append(
                f"citation_path {path} is also present in "
                f"{owner.jurisdiction}/{owner.document_class}/{owner.version}"
            )
        else:
            owners[path] = scope
            messages.append(None)
    return messages


@settings(max_examples=300, deadline=None)
@given(
    st.lists(
        st.tuples(
            st.sampled_from([scope for scope in _SCOPE_POOL if not scope.is_base]),
            st.sampled_from(["a", "b", "c"]),
        ),
        max_size=14,
    )
)
def test_primary_only_uniqueness_matches_pre_layer_rule(
    claims: list[tuple[ReleaseScope, str]],
) -> None:
    owners = _LayeredCitationOwners()
    actual = []
    for scope, path in claims:
        conflict = owners.claim(path, scope)
        if conflict is not None:
            assert conflict[0] == "duplicate_release_citation"
        actual.append(None if conflict is None else conflict[1])

    assert actual == _reference_primary_conflicts(claims)
