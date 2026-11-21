from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable, Mapping
from pathlib import Path

import pytest

import scripts.compose_scope_versions as compose_module
from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.models import ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.supabase import deterministic_provision_id
from scripts.compose_scope_versions import compose_scope_versions
from tests.conftest import fixture_git


def _write_scope(
    store: CorpusArtifactStore,
    version: str,
    citation_paths: list[str],
    *,
    parent: dict[str, str] | None = None,
    jurisdiction: str = "de",
) -> tuple[tuple[SourceInventoryItem, ...], tuple[ProvisionRecord, ...]]:
    source = store.source_path(jurisdiction, "statute", version, f"{version}-source.xml")
    source_sha256 = store.write_text(source, f"<doc>{version}</doc>")
    source_path = source.relative_to(store.root).as_posix()
    parent = parent or {}
    inventory = tuple(
        SourceInventoryItem(
            citation_path=citation_path,
            source_path=source_path,
            sha256=source_sha256,
        )
        for citation_path in citation_paths
    )
    records = tuple(
        ProvisionRecord(
            jurisdiction=jurisdiction,
            document_class="statute",
            citation_path=citation_path,
            body=f"Body of {citation_path}.",
            id=deterministic_provision_id(citation_path, version),
            version=version,
            source_path=source_path,
            source_as_of="2026-07-21",
            expression_date="2026-07-21",
            parent_citation_path=parent.get(citation_path),
            parent_id=(
                deterministic_provision_id(parent[citation_path], version)
                if citation_path in parent
                else None
            ),
        )
        for citation_path in citation_paths
    )
    store.write_inventory(store.inventory_path(jurisdiction, "statute", version), inventory)
    store.write_provisions(store.provisions_path(jurisdiction, "statute", version), records)
    return inventory, records


def test_compose_concatenates_and_rewrites_versions(tmp_path):
    store = CorpusArtifactStore(tmp_path / "corpus")
    _, base_records = _write_scope(
        store,
        "wave-1",
        ["de/statute/estg", "de/statute/estg/66"],
        parent={"de/statute/estg/66": "de/statute/estg"},
    )
    _write_scope(store, "wave-2", ["de/statute/act-449/stefeg"])

    generated = compose_scope_versions(
        base=store.root,
        jurisdiction="de",
        document_class="statute",
        source_versions=["wave-1", "wave-2"],
        target_version="composed",
    )

    assert len(generated) == 4
    # Constituent artifacts stay untouched.
    assert (
        load_provisions(store.provisions_path("de", "statute", "wave-1"))
        == base_records
    )
    target_inventory = load_source_inventory(
        store.inventory_path("de", "statute", "composed")
    )
    target_records = load_provisions(store.provisions_path("de", "statute", "composed"))
    assert [item.citation_path for item in target_inventory] == [
        "de/statute/estg",
        "de/statute/estg/66",
        "de/statute/act-449/stefeg",
    ]
    assert all(item.source_path.startswith("sources/de/statute/composed/") for item in target_inventory)
    assert {record.version for record in target_records} == {"composed"}
    assert target_records[0].id == deterministic_provision_id(
        "de/statute/estg", "composed"
    )
    assert target_records[1].parent_id == target_records[0].id
    assert target_records[2].id == deterministic_provision_id(
        "de/statute/act-449/stefeg", "composed"
    )
    # Source files from every constituent are present under the composed tree.
    composed_sources = sorted(
        path.name
        for path in (store.root / "sources" / "de" / "statute" / "composed").rglob("*")
        if path.is_file()
    )
    assert composed_sources == ["wave-1-source.xml", "wave-2-source.xml"]


def test_compose_rejects_duplicate_citation_paths(tmp_path):
    store = CorpusArtifactStore(tmp_path / "corpus")
    _write_scope(store, "wave-1", ["de/statute/estg"])
    _write_scope(store, "wave-2", ["de/statute/estg"])

    with pytest.raises(ValueError, match="duplicate inventory citation_path"):
        compose_scope_versions(
            base=store.root,
            jurisdiction="de",
            document_class="statute",
            source_versions=["wave-1", "wave-2"],
            target_version="composed",
        )


def test_compose_rejects_existing_target_and_reused_version(tmp_path):
    store = CorpusArtifactStore(tmp_path / "corpus")
    _write_scope(store, "wave-1", ["de/statute/estg"])
    _write_scope(store, "wave-2", ["de/statute/solzg-1995"])

    with pytest.raises(ValueError, match="target version must differ"):
        compose_scope_versions(
            base=store.root,
            jurisdiction="de",
            document_class="statute",
            source_versions=["wave-1", "wave-2"],
            target_version="wave-2",
        )
    with pytest.raises(ValueError, match="at least two source versions"):
        compose_scope_versions(
            base=store.root,
            jurisdiction="de",
            document_class="statute",
            source_versions=["wave-1"],
            target_version="composed",
        )
    compose_scope_versions(
        base=store.root,
        jurisdiction="de",
        document_class="statute",
        source_versions=["wave-1", "wave-2"],
        target_version="composed",
    )
    with pytest.raises(ValueError, match="target artifact already exists"):
        compose_scope_versions(
            base=store.root,
            jurisdiction="de",
            document_class="statute",
            source_versions=["wave-1", "wave-2"],
            target_version="composed",
        )


def _target_artifacts(store: CorpusArtifactStore, version: str):
    return (
        store.root / "sources" / "de" / "statute" / version,
        store.inventory_path("de", "statute", version),
        store.provisions_path("de", "statute", version),
        store.coverage_path("de", "statute", version),
    )


def _write_single_doc_scope(
    store: CorpusArtifactStore,
    version: str,
    citation_path: str,
    *,
    source_name: str,
) -> None:
    source = store.source_path("de", "statute", version, source_name)
    source_sha256 = store.write_text(source, f"<doc>{version}</doc>")
    source_path = source.relative_to(store.root).as_posix()
    store.write_inventory(
        store.inventory_path("de", "statute", version),
        [
            SourceInventoryItem(
                citation_path=citation_path,
                source_path=source_path,
                sha256=source_sha256,
            )
        ],
    )
    store.write_provisions(
        store.provisions_path("de", "statute", version),
        [
            ProvisionRecord(
                jurisdiction="de",
                document_class="statute",
                citation_path=citation_path,
                body="Body.",
                id=deterministic_provision_id(citation_path, version),
                version=version,
                source_path=source_path,
                source_as_of="2026-07-21",
                expression_date="2026-07-21",
            )
        ],
    )


def test_compose_rejects_colliding_source_files_without_debris(tmp_path):
    store = CorpusArtifactStore(tmp_path / "corpus")
    _write_single_doc_scope(store, "wave-1", "de/statute/estg", source_name="same-name.xml")
    _write_single_doc_scope(
        store, "wave-2", "de/statute/solzg-1995", source_name="same-name.xml"
    )

    with pytest.raises(ValueError, match="source file collides"):
        compose_scope_versions(
            base=store.root,
            jurisdiction="de",
            document_class="statute",
            source_versions=["wave-1", "wave-2"],
            target_version="composed",
        )
    # The refusal happens before any target artifact is created, so a
    # corrected retry is not blocked by the existing-target guard.
    for path in _target_artifacts(store, "composed"):
        assert not path.exists()

    _write_single_doc_scope(
        store, "wave-3", "de/statute/bkgg-1996", source_name="other-name.xml"
    )
    compose_scope_versions(
        base=store.root,
        jurisdiction="de",
        document_class="statute",
        source_versions=["wave-1", "wave-3"],
        target_version="composed",
    )
    for path in _target_artifacts(store, "composed"):
        assert path.exists()


def test_compose_rejects_file_versus_directory_collisions(tmp_path):
    store = CorpusArtifactStore(tmp_path / "corpus")
    # The dangerous shape is directory-first, file-second: copy2 would
    # silently write the later constituent's file INTO the already-copied
    # directory ("target/node/node"). File-first merely crashes on mkdir.
    # The preflight must refuse both orders before anything is created.
    _write_single_doc_scope(
        store, "wave-1", "de/statute/estg", source_name="node/inside.xml"
    )
    _write_single_doc_scope(store, "wave-2", "de/statute/solzg-1995", source_name="node")

    with pytest.raises(ValueError, match="source file collides"):
        compose_scope_versions(
            base=store.root,
            jurisdiction="de",
            document_class="statute",
            source_versions=["wave-1", "wave-2"],
            target_version="composed",
        )
    with pytest.raises(ValueError, match="source file collides"):
        compose_scope_versions(
            base=store.root,
            jurisdiction="de",
            document_class="statute",
            source_versions=["wave-2", "wave-1"],
            target_version="composed",
        )
    for path in _target_artifacts(store, "composed"):
        assert not path.exists()


def test_compose_rejects_filesystem_equivalent_name_collisions(tmp_path):
    store = CorpusArtifactStore(tmp_path / "corpus")
    # Case-insensitive or normalizing filesystems (APFS) resolve "A.xml" /
    # "a.xml" and NFC/NFD spellings of "ä.xml" to the same entry, so the
    # second copy would silently replace the first despite lexically
    # distinct relative paths.
    _write_single_doc_scope(store, "wave-1", "de/statute/estg", source_name="A.xml")
    _write_single_doc_scope(
        store, "wave-2", "de/statute/solzg-1995", source_name="a.xml"
    )
    with pytest.raises(ValueError, match="source file collides"):
        compose_scope_versions(
            base=store.root,
            jurisdiction="de",
            document_class="statute",
            source_versions=["wave-1", "wave-2"],
            target_version="composed",
        )

    _write_single_doc_scope(
        store, "wave-3", "de/statute/bkgg-1996", source_name="bä.xml"
    )
    _write_single_doc_scope(
        store, "wave-4", "de/statute/wogg", source_name="bä.xml"
    )
    with pytest.raises(ValueError, match="source file collides"):
        compose_scope_versions(
            base=store.root,
            jurisdiction="de",
            document_class="statute",
            source_versions=["wave-3", "wave-4"],
            target_version="composed",
        )

    # Full canonical caseless matching, not just NFC+casefold: U+015A
    # (precomposed S-acute) casefolds to precomposed ś while U+017F U+0301
    # (long s + combining acute) casefolds to a decomposed spelling — only
    # NFD(casefold(NFD(s))) equates them, and APFS treats them as one entry.
    _write_single_doc_scope(
        store, "wave-5", "de/statute/sgb-2", source_name="Ś.xml"
    )
    _write_single_doc_scope(
        store, "wave-6", "de/statute/sgb-12", source_name="ſ́.xml"
    )
    with pytest.raises(ValueError, match="source file collides"):
        compose_scope_versions(
            base=store.root,
            jurisdiction="de",
            document_class="statute",
            source_versions=["wave-5", "wave-6"],
            target_version="composed",
        )
    for path in _target_artifacts(store, "composed"):
        assert not path.exists()


def test_compose_rejects_incomplete_constituents_even_when_aggregate_cancels(tmp_path):
    store = CorpusArtifactStore(tmp_path / "corpus")
    # wave-1 inventories "a" but provides "b"; wave-2 the reverse. The
    # aggregate citation sets match, so only a per-constituent check refuses.
    for version, inventoried, provided in (
        ("wave-1", "de/statute/a", "de/statute/b"),
        ("wave-2", "de/statute/b", "de/statute/a"),
    ):
        source = store.source_path("de", "statute", version, f"{version}.xml")
        source_sha256 = store.write_text(source, f"<doc>{version}</doc>")
        source_path = source.relative_to(store.root).as_posix()
        store.write_inventory(
            store.inventory_path("de", "statute", version),
            [
                SourceInventoryItem(
                    citation_path=inventoried,
                    source_path=source_path,
                    sha256=source_sha256,
                )
            ],
        )
        store.write_provisions(
            store.provisions_path("de", "statute", version),
            [
                ProvisionRecord(
                    jurisdiction="de",
                    document_class="statute",
                    citation_path=provided,
                    body="Body.",
                    id=deterministic_provision_id(provided, version),
                    version=version,
                    source_path=source_path,
                    source_as_of="2026-07-21",
                    expression_date="2026-07-21",
                )
            ],
        )

    with pytest.raises(ValueError, match="constituent scope does not have complete"):
        compose_scope_versions(
            base=store.root,
            jurisdiction="de",
            document_class="statute",
            source_versions=["wave-1", "wave-2"],
            target_version="composed",
        )
    for path in _target_artifacts(store, "composed"):
        assert not path.exists()


def test_compose_rejects_symlinked_source_files(tmp_path):
    store = CorpusArtifactStore(tmp_path / "corpus")
    _write_single_doc_scope(store, "wave-1", "de/statute/estg", source_name="one.xml")
    _write_single_doc_scope(store, "wave-2", "de/statute/solzg-1995", source_name="two.xml")
    linked = store.source_path("de", "statute", "wave-2", "sneaky-link.xml")
    linked.symlink_to(store.source_path("de", "statute", "wave-2", "two.xml"))

    with pytest.raises(ValueError, match="contains a symlink"):
        compose_scope_versions(
            base=store.root,
            jurisdiction="de",
            document_class="statute",
            source_versions=["wave-1", "wave-2"],
            target_version="composed",
        )


def test_compose_cleans_up_when_a_target_write_fails(tmp_path, monkeypatch):
    store = CorpusArtifactStore(tmp_path / "corpus")
    _write_single_doc_scope(store, "wave-1", "de/statute/estg", source_name="one.xml")
    _write_single_doc_scope(store, "wave-2", "de/statute/solzg-1995", source_name="two.xml")

    original = CorpusArtifactStore.write_provisions

    def broken_write_provisions(self, path, records):
        if "composed" in str(path):
            raise OSError("disk full")
        return original(self, path, records)

    monkeypatch.setattr(CorpusArtifactStore, "write_provisions", broken_write_provisions)
    with pytest.raises(OSError, match="disk full"):
        compose_scope_versions(
            base=store.root,
            jurisdiction="de",
            document_class="statute",
            source_versions=["wave-1", "wave-2"],
            target_version="composed",
        )
    for path in _target_artifacts(store, "composed"):
        assert not path.exists()

    monkeypatch.setattr(CorpusArtifactStore, "write_provisions", original)
    compose_scope_versions(
        base=store.root,
        jurisdiction="de",
        document_class="statute",
        source_versions=["wave-1", "wave-2"],
        target_version="composed",
    )
    for path in _target_artifacts(store, "composed"):
        assert path.exists()


def _write_layered_selector(releases_dir: Path) -> Path:
    """Write a tracked selector that marks us-example/statute/tracked-base as a base."""
    releases_dir.mkdir(parents=True)
    selector = {
        "name": "us-example-layered",
        "scopes": [
            {
                "document_class": "statute",
                "jurisdiction": "us-example",
                "layer": "base",
                "version": "tracked-base",
            },
            {
                "document_class": "statute",
                "jurisdiction": "us-example",
                "version": "primary-one",
            },
        ],
    }
    (releases_dir / "us-example-layered.json").write_text(
        json.dumps(selector, indent=2, sort_keys=True) + "\n"
    )
    return releases_dir


def _write_example_scope(
    store: CorpusArtifactStore, version: str, *, jurisdiction: str = "us-example"
) -> None:
    _write_scope(
        store,
        version,
        [f"{jurisdiction}/statute/{version}"],
        jurisdiction=jurisdiction,
    )


def _tree(root: Path) -> dict[str, bytes | None]:
    """Every path under ``root``, with a file's bytes and None for a directory."""
    return {
        path.relative_to(root).as_posix(): path.read_bytes() if path.is_file() else None
        for path in sorted(root.rglob("*"))
    }


def _refuse_fetch(*_args, **_kwargs):
    raise AssertionError("require_materialized ran for a refused base scope")


@pytest.mark.parametrize(
    ("source_versions", "target_version"),
    [
        pytest.param(["tracked-base", "primary-one"], "composed", id="base-source"),
        pytest.param(["primary-one", "primary-two"], "tracked-base", id="base-target"),
    ],
)
def test_compose_refuses_a_tracked_base_scope_before_fetching(
    tmp_path, monkeypatch, source_versions, target_version
):
    store = CorpusArtifactStore(tmp_path / "corpus")
    for version in source_versions:
        _write_example_scope(store, version)
    releases_dir = _write_layered_selector(tmp_path / "releases")
    before = _tree(store.root)
    monkeypatch.setattr(compose_module, "require_materialized", _refuse_fetch)

    with pytest.raises(
        ValueError,
        match=(
            r"^base scopes are carried unchanged and cannot be composed: "
            r"us-example/statute/tracked-base$"
        ),
    ):
        compose_scope_versions(
            base=store.root,
            jurisdiction="us-example",
            document_class="statute",
            source_versions=source_versions,
            target_version=target_version,
            releases_dir=releases_dir,
        )

    # Nothing was created, moved or rewritten.
    assert _tree(store.root) == before
    assert not (store.root / "sources/us-example/statute" / target_version).exists()
    assert not store.inventory_path("us-example", "statute", target_version).exists()
    assert not store.provisions_path("us-example", "statute", target_version).exists()
    assert not store.coverage_path("us-example", "statute", target_version).exists()


def test_compose_composes_primary_scopes_beside_a_tracked_base(tmp_path):
    store = CorpusArtifactStore(tmp_path / "corpus")
    releases_dir = _write_layered_selector(tmp_path / "releases")
    # Primary scopes of the pair whose base the selector marks.
    _write_example_scope(store, "primary-one")
    _write_example_scope(store, "primary-two")
    # The base's version string under another pair names a primary scope.
    _write_example_scope(store, "tracked-base", jurisdiction="de")
    _write_example_scope(store, "primary-one", jurisdiction="de")

    compose_scope_versions(
        base=store.root,
        jurisdiction="us-example",
        document_class="statute",
        source_versions=["primary-one", "primary-two"],
        target_version="composed",
        releases_dir=releases_dir,
    )
    compose_scope_versions(
        base=store.root,
        jurisdiction="de",
        document_class="statute",
        source_versions=["tracked-base", "primary-one"],
        target_version="composed",
        releases_dir=releases_dir,
    )

    assert [
        record.citation_path
        for record in load_provisions(store.provisions_path("us-example", "statute", "composed"))
    ] == ["us-example/statute/primary-one", "us-example/statute/primary-two"]
    assert [
        record.citation_path
        for record in load_provisions(store.provisions_path("de", "statute", "composed"))
    ] == ["de/statute/tracked-base", "de/statute/primary-one"]


def test_compose_reads_the_repository_selectors_by_default(tmp_path, monkeypatch):
    store = CorpusArtifactStore(tmp_path / "corpus")
    _write_example_scope(store, "primary-one")
    _write_example_scope(store, "primary-two")
    seen: list[Path] = []

    def recording_tracked_base_scopes(releases_dir: Path) -> frozenset[tuple[str, str, str]]:
        seen.append(releases_dir)
        return frozenset({("us-example", "statute", "primary-two")})

    monkeypatch.setattr(compose_module, "tracked_base_scopes", recording_tracked_base_scopes)
    monkeypatch.setattr(compose_module, "require_materialized", _refuse_fetch)

    with pytest.raises(ValueError, match=r"cannot be composed: us-example/statute/primary-two$"):
        compose_scope_versions(
            base=store.root,
            jurisdiction="us-example",
            document_class="statute",
            source_versions=["primary-one", "primary-two"],
            target_version="composed",
        )

    repository_releases = Path(__file__).resolve().parents[1] / "manifests" / "releases"
    assert seen == [repository_releases]
    assert repository_releases.is_dir()


@pytest.mark.parametrize(
    "checkout",
    [
        pytest.param("other-checkout", id="base-checkout"),
        pytest.param(None, id="no-checkout"),
    ],
)
def test_compose_cli_reads_the_selectors_of_the_checkout_holding_base(
    tmp_path, monkeypatch, checkout
):
    store = CorpusArtifactStore(tmp_path / "corpus")
    _write_example_scope(store, "primary-one")
    _write_example_scope(store, "primary-two")
    asked: list[Path] = []
    seen: list[Path] = []

    def fake_cli_repo(args) -> Path | None:
        asked.append(Path(args.base))
        return None if checkout is None else tmp_path / checkout

    def recording_tracked_base_scopes(releases_dir: Path) -> frozenset[tuple[str, str, str]]:
        seen.append(releases_dir)
        return frozenset({("us-example", "statute", "primary-two")})

    monkeypatch.setattr(compose_module, "cli_repo", fake_cli_repo, raising=False)
    monkeypatch.setattr(compose_module, "tracked_base_scopes", recording_tracked_base_scopes)
    monkeypatch.setattr(compose_module, "require_materialized", _refuse_fetch)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "compose_scope_versions.py",
            "--base",
            str(store.root),
            "--jurisdiction",
            "us-example",
            "--document-class",
            "statute",
            "--source-version",
            "primary-one",
            "--source-version",
            "primary-two",
            "--target-version",
            "composed",
        ],
    )

    if checkout is None:
        # No checkout holds --base or the working directory, so no selector
        # says which scopes are bases: the command line refuses to guess.
        with pytest.raises(SystemExit) as exited:
            compose_module.main()
        assert exited.value.code == 2
        assert seen == []
        return
    with pytest.raises(ValueError, match=r"cannot be composed: us-example/statute/primary-two$"):
        compose_module.main()
    assert seen == [tmp_path / "other-checkout" / "manifests" / "releases"]
    assert asked == [store.root]


# Spellings a selector cannot hold that name the files of us-example/statute/tracked-base:
# artifacts.safe_segment strips whitespace and "/" and rewrites "\\" and ":",
# and APFS folds case.
BASE_ALIASES = [
    pytest.param(("us-example", "statute", "tracked-base "), id="trailing-space"),
    pytest.param(("us-example", "statute", " tracked-base"), id="leading-space"),
    pytest.param(("us-example", "statute", "tracked-base\t"), id="trailing-tab"),
    pytest.param(("us-example", "statute", "tracked-base\n"), id="trailing-newline"),
    pytest.param(("us-example", "statute", "tracked-base/"), id="trailing-slash"),
    pytest.param(("us-example", "statute", "tracked:base"), id="colon"),
    pytest.param(("us-example", "statute", "tracked\\base"), id="backslash"),
    pytest.param(("us-example", "statute", "Tracked-Base"), id="upper-case"),
    pytest.param(("us-example ", "statute", "tracked-base"), id="jurisdiction-alias"),
    pytest.param(("us-example", "statute/", "tracked-base"), id="document-class-alias"),
]


@pytest.mark.parametrize("role", ["source", "target"])
@pytest.mark.parametrize("alias", BASE_ALIASES)
def test_compose_refuses_a_spelling_that_names_a_tracked_base(tmp_path, monkeypatch, alias, role):
    jurisdiction, document_class, version = alias
    store = CorpusArtifactStore(tmp_path / "corpus")
    _write_example_scope(store, "primary-one")
    _write_example_scope(store, "primary-two")
    releases_dir = _write_layered_selector(tmp_path / "releases")
    before = _tree(store.root)
    monkeypatch.setattr(compose_module, "require_materialized", _refuse_fetch)
    if role == "source":
        source_versions = [version, "primary-one"]
        target_version = "composed"
    else:
        source_versions = ["primary-one", "primary-two"]
        target_version = version

    # The name is refused before any path is built or anything is fetched.
    with pytest.raises(ValueError, match=r"^not a canonical scope: "):
        compose_scope_versions(
            base=store.root,
            jurisdiction=jurisdiction,
            document_class=document_class,
            source_versions=source_versions,
            target_version=target_version,
            releases_dir=releases_dir,
        )

    assert _tree(store.root) == before
    assert not (store.root / "sources/us-example/statute/tracked-base").exists()
    assert not store.inventory_path("us-example", "statute", "tracked-base").exists()
    assert not store.provisions_path("us-example", "statute", "tracked-base").exists()
    assert not store.coverage_path("us-example", "statute", "tracked-base").exists()


@pytest.mark.parametrize("target_version", ["tracked-base ", "tracked-base/"])
def test_compose_writes_nothing_at_a_tracked_base_path_through_an_alias(tmp_path, target_version):
    store = CorpusArtifactStore(tmp_path / "corpus")
    _write_example_scope(store, "primary-one")
    _write_example_scope(store, "primary-two")
    releases_dir = _write_layered_selector(tmp_path / "releases")

    # With the real fetch step: the alias would otherwise write the base's files.
    with pytest.raises(ValueError, match=r"^not a canonical scope: "):
        compose_scope_versions(
            base=store.root,
            jurisdiction="us-example",
            document_class="statute",
            source_versions=["primary-one", "primary-two"],
            target_version=target_version,
            releases_dir=releases_dir,
        )

    assert not store.provisions_path("us-example", "statute", "tracked-base").exists()
    assert not store.inventory_path("us-example", "statute", "tracked-base").exists()
    assert not store.coverage_path("us-example", "statute", "tracked-base").exists()
    assert not (store.root / "sources/us-example/statute/tracked-base").exists()


@pytest.mark.parametrize("role", ["source", "target"])
def test_compose_refuses_a_spelling_before_reading_the_tracked_selectors(
    tmp_path, monkeypatch, role
):
    store = CorpusArtifactStore(tmp_path / "corpus")
    _write_example_scope(store, "primary-one")
    _write_example_scope(store, "primary-two")
    monkeypatch.setattr(compose_module, "require_materialized", _refuse_fetch)
    if role == "source":
        source_versions = ["tracked-base ", "primary-one"]
        target_version = "composed"
    else:
        source_versions = ["primary-one", "primary-two"]
        target_version = "tracked-base "

    # No selector directory exists, so the spelling refusal can win only if
    # the check runs before tracked_base_scopes reads the directory.
    with pytest.raises(
        ValueError, match=r"^not a canonical scope: 'us-example'/'statute'/'tracked-base ' "
    ):
        compose_scope_versions(
            base=store.root,
            jurisdiction="us-example",
            document_class="statute",
            source_versions=source_versions,
            target_version=target_version,
            releases_dir=tmp_path / "missing",
        )


# Finding 1 of round 2: the checkouts that hold the paths composition uses. Each
# checkout is built with ``make_checkout`` and commits one selector.
MakeCheckout = Callable[[str, Mapping[str, Mapping[str, object]]], Path]
VERSIONS = ["primary-one", "primary-two"]


def _checkout(make_checkout: MakeCheckout, name: str, *, base: str | None = None) -> Path:
    """A checkout whose committed selector marks ``us-example/statute/<base>`` as a base."""
    selector = f"{name}-selector"
    scopes: list[dict[str, str]] = [
        {"document_class": "statute", "jurisdiction": "us-example", "version": "primary-one"}
    ]
    if base is not None:
        scopes.append(
            {
                "document_class": "statute",
                "jurisdiction": "us-example",
                "layer": "base",
                "version": base,
            }
        )
    return make_checkout(name, {selector: {"name": selector, "scopes": scopes}})


def _releases(checkout: Path) -> Path:
    return checkout / "manifests" / "releases"


def _link(link: Path, target: Path) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(target)


def _bytes_under(root: Path) -> dict[str, bytes | None]:
    """Every entry below ``root`` outside ``.git``: a file's bytes, else None."""
    found: dict[str, bytes | None] = {}
    for directory, directories, filenames in os.walk(root):
        directories[:] = [name for name in directories if name != ".git"]
        for name in (*directories, *filenames):
            path = Path(directory, name)
            if name != ".git":
                found[str(path.relative_to(root))] = path.read_bytes() if path.is_file() else None
    return found


def _sources(checkout: Path) -> CorpusArtifactStore:
    store = CorpusArtifactStore(checkout / "data" / "corpus")
    _write_example_scope(store, "primary-one")
    _write_example_scope(store, "primary-two")
    return store


@pytest.mark.parametrize(
    "case",
    [
        "target-named-after-another-checkouts-base",
        "source-is-another-checkouts-base",
        "coverage-link-target",
        "link-outside-checkouts",
        "directory-alias",
    ],
)
def test_compose_refuses_a_base_or_an_alias_another_path_holds(
    tmp_path, monkeypatch, make_checkout, case
):
    document_class = "statute"
    target_version = "composed"
    if case == "target-named-after-another-checkouts-base":
        a = _checkout(make_checkout, "a")
        b = _checkout(make_checkout, "b", base="composed-base")
        _link(a / "data" / "corpus", _sources(b).root)
        target_version = "composed-base"
        refused = "us-example/statute/composed-base"
    elif case == "source-is-another-checkouts-base":
        a = _checkout(make_checkout, "a")
        b = _checkout(make_checkout, "b", base="primary-two")
        _link(a / "data" / "corpus", _sources(b).root)
        refused = "us-example/statute/primary-two"
    elif case == "coverage-link-target":
        a = _checkout(make_checkout, "a")
        b = _checkout(make_checkout, "b", base="composed")
        _sources(a)
        (b / "data" / "corpus" / "coverage").mkdir(parents=True)
        _link(a / "data" / "corpus" / "coverage", b / "data" / "corpus" / "coverage")
        refused = "us-example/statute/composed"
    elif case == "link-outside-checkouts":
        a = _checkout(make_checkout, "a")
        shared = CorpusArtifactStore(tmp_path / "shared")
        _write_example_scope(shared, "primary-one")
        _write_example_scope(shared, "primary-two")
        _link(a / "data" / "corpus", shared.root)
        refused = ""
        expected = r"^scope artifact leads through a link outside every axiom-corpus checkout: "
    else:
        a = _checkout(make_checkout, "a", base="primary-two")
        store = _sources(a)
        for kind in ("inventory", "provisions", "sources"):
            _link(
                store.root / kind / "us-example" / "regulation",
                store.root / kind / "us-example" / "statute",
            )
        document_class = "regulation"
        refused = ""
        expected = r"^scope artifact resolves to another path: "
    if refused:
        expected = rf"^base scopes are carried unchanged and cannot be composed: {refused}$"
    before = _bytes_under(tmp_path)
    monkeypatch.setattr(compose_module, "require_materialized", _refuse_fetch)

    with pytest.raises(ValueError, match=expected):
        compose_scope_versions(
            base=a / "data" / "corpus",
            jurisdiction="us-example",
            document_class=document_class,
            source_versions=VERSIONS,
            target_version=target_version,
            releases_dir=_releases(a),
        )

    # Refused before the fetch, and nothing was written in any checkout.
    assert _bytes_under(tmp_path) == before


def test_compose_cli_reads_the_working_directorys_checkout(tmp_path, monkeypatch, make_checkout):
    m = _checkout(make_checkout, "m")
    wt = tmp_path / "wt"
    fixture_git(m, "worktree", "add", "-q", "-b", "feat", str(wt))
    # The worktree's branch commits a selector that marks primary-two as a base.
    payload = {
        "name": "wt-layered",
        "scopes": [
            {
                "document_class": "statute",
                "jurisdiction": "us-example",
                "layer": "base",
                "version": "primary-two",
            }
        ],
    }
    (_releases(wt) / "wt-layered.json").write_text(json.dumps(payload, indent=2) + "\n")
    fixture_git(wt, "add", "--", "manifests")
    fixture_git(wt, "commit", "-q", "-m", "Mark primary-two as a base")
    store = _sources(m)
    before = _bytes_under(tmp_path)
    monkeypatch.setattr(compose_module, "require_materialized", _refuse_fetch)
    monkeypatch.chdir(wt)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "compose_scope_versions.py",
            "--base",
            str(store.root),
            "--jurisdiction",
            "us-example",
            "--document-class",
            "statute",
            "--source-version",
            "primary-one",
            "--source-version",
            "primary-two",
            "--target-version",
            "composed",
        ],
    )

    # --base binds to m, whose HEAD marks nothing; the working directory's does.
    with pytest.raises(
        ValueError,
        match=r"^base scopes are carried unchanged and cannot be composed: "
        r"us-example/statute/primary-two$",
    ):
        compose_module.main()

    assert _bytes_under(tmp_path) == before


def test_compose_runs_through_a_link_into_a_checkout_that_marks_no_base(tmp_path, make_checkout):
    a = _checkout(make_checkout, "a")
    b = _checkout(make_checkout, "b")
    shared = _sources(b)
    _link(a / "data" / "corpus", shared.root)

    compose_scope_versions(
        base=a / "data" / "corpus",
        jurisdiction="us-example",
        document_class="statute",
        source_versions=VERSIONS,
        target_version="composed",
        releases_dir=_releases(a),
    )

    assert [
        record.citation_path
        for record in load_provisions(shared.provisions_path("us-example", "statute", "composed"))
    ] == ["us-example/statute/primary-one", "us-example/statute/primary-two"]
