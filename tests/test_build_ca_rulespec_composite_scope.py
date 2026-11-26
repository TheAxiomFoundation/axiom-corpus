from __future__ import annotations

import json
import os
import re
import shutil
import sys
from collections.abc import Callable, Mapping
from dataclasses import replace
from pathlib import Path

import pytest

import scripts.build_ca_rulespec_composite_scope as ca_module
from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.models import ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.supabase import deterministic_provision_id
from scripts.build_ca_rulespec_composite_scope import (
    build_ca_rulespec_composite_scope,
    promote_program_roots,
)


def test_promotes_program_body_to_attested_primary_document(tmp_path) -> None:
    store = CorpusArtifactStore(tmp_path / "corpus")
    version = "ca-composite"
    root_path = "ca/policy/cra/example"
    source_path = store.source_path("ca", "policy", version, "example.txt")
    source_sha256 = store.write_text(source_path, "Primary text")
    relative_source_path = source_path.relative_to(store.root).as_posix()
    root = ProvisionRecord(
        jurisdiction="ca",
        document_class="policy",
        citation_path=root_path,
        body="Primary text",
        id=deterministic_provision_id(root_path, version),
        version=version,
        source_path=relative_source_path,
        level=1,
        ordinal=1,
        kind="document",
    )
    values = ProvisionRecord(
        jurisdiction="ca",
        document_class="policy",
        citation_path=f"{root_path}/values",
        body="Worksheet text",
        id=deterministic_provision_id(f"{root_path}/values", version),
        version=version,
        source_path=relative_source_path,
        parent_citation_path=root_path,
        parent_id=root.id,
        level=2,
        ordinal=2,
        kind="section",
    )
    inventory = (
        SourceInventoryItem(
            citation_path=root_path,
            source_path=relative_source_path,
            sha256=source_sha256,
        ),
        SourceInventoryItem(
            citation_path=values.citation_path,
            source_path=relative_source_path,
            sha256=source_sha256,
        ),
    )
    store.write_inventory(store.inventory_path("ca", "policy", version), inventory)
    store.write_provisions(store.provisions_path("ca", "policy", version), (root, values))

    promote_program_roots(base=store.root, version=version, citation_paths=(root_path,))

    records = {
        record.citation_path: record
        for record in load_provisions(store.provisions_path("ca", "policy", version))
    }
    primary_path = f"{root_path}/primary-document"
    assert records[root_path].body is None
    assert records[primary_path].body == "Primary text"
    assert records[primary_path].parent_citation_path == root_path
    assert records[primary_path].parent_id == deterministic_provision_id(root_path, version)
    assert records[f"{root_path}/values"] == values
    inventory_paths = {
        item.citation_path
        for item in load_source_inventory(store.inventory_path("ca", "policy", version))
    }
    assert inventory_paths == {root_path, primary_path, f"{root_path}/values"}


def test_preserves_existing_bodyless_composite_root(tmp_path) -> None:
    store = CorpusArtifactStore(tmp_path / "corpus")
    version = "ca-composite"
    root_path = "ca/policy/cra/example"
    source_path = store.source_path("ca", "policy", version, "example.txt")
    source_sha256 = store.write_text(source_path, "Document text")
    relative_source_path = source_path.relative_to(store.root).as_posix()
    root = ProvisionRecord(
        jurisdiction="ca",
        document_class="policy",
        citation_path=root_path,
        body=None,
        id=deterministic_provision_id(root_path, version),
        version=version,
        source_path=relative_source_path,
    )
    document = replace(
        root,
        citation_path=f"{root_path}/document-1",
        body="Document text",
        id=deterministic_provision_id(f"{root_path}/document-1", version),
        parent_citation_path=root_path,
        parent_id=root.id,
    )
    inventory = tuple(
        SourceInventoryItem(
            citation_path=record.citation_path,
            source_path=relative_source_path,
            sha256=source_sha256,
        )
        for record in (root, document)
    )
    store.write_inventory(store.inventory_path("ca", "policy", version), inventory)
    store.write_provisions(store.provisions_path("ca", "policy", version), (root, document))

    promote_program_roots(base=store.root, version=version, citation_paths=(root_path,))

    records = load_provisions(store.provisions_path("ca", "policy", version))
    assert records == (root, document)


def test_normalizes_empty_composite_root_and_removes_empty_primary_document(
    tmp_path,
) -> None:
    store = CorpusArtifactStore(tmp_path / "corpus")
    version = "ca-composite"
    root_path = "ca/policy/cra/example"
    source_path = store.source_path("ca", "policy", version, "example.txt")
    source_sha256 = store.write_text(source_path, "Document text")
    relative_source_path = source_path.relative_to(store.root).as_posix()
    root = ProvisionRecord(
        jurisdiction="ca",
        document_class="policy",
        citation_path=root_path,
        body="",
        id=deterministic_provision_id(root_path, version),
        version=version,
        source_path=relative_source_path,
    )
    document = replace(
        root,
        citation_path=f"{root_path}/document-1",
        body="Document text",
        id=deterministic_provision_id(f"{root_path}/document-1", version),
        parent_citation_path=root_path,
        parent_id=root.id,
    )
    empty_primary = replace(
        root,
        citation_path=f"{root_path}/primary-document",
        id=deterministic_provision_id(f"{root_path}/primary-document", version),
        parent_citation_path=root_path,
        parent_id=root.id,
    )
    inventory = tuple(
        SourceInventoryItem(
            citation_path=record.citation_path,
            source_path=relative_source_path,
            sha256=source_sha256,
        )
        for record in (root, document, empty_primary)
    )
    store.write_inventory(store.inventory_path("ca", "policy", version), inventory)
    store.write_provisions(
        store.provisions_path("ca", "policy", version),
        (root, document, empty_primary),
    )

    promote_program_roots(base=store.root, version=version, citation_paths=(root_path,))

    records = load_provisions(store.provisions_path("ca", "policy", version))
    assert records == (replace(root, body=None), document)
    assert all(not record.citation_path.endswith("/primary-document") for record in records)


def test_rejects_duplicate_supplemental_source_version(tmp_path) -> None:
    selector_path = tmp_path / "selector.json"
    selector_path.write_text(
        json.dumps(
            {
                "name": "ca-test",
                "scopes": [
                    {
                        "jurisdiction": "ca",
                        "document_class": "policy",
                        "version": "source-v1",
                    }
                ],
            }
        )
    )
    contract_path = tmp_path / "citations.json"
    contract_path.write_text(json.dumps({"citation_paths": ["ca/policy/example"]}))

    with pytest.raises(ValueError, match="source versions must be unique"):
        build_ca_rulespec_composite_scope(
            base=tmp_path / "corpus",
            selector_path=selector_path,
            citation_contract_path=contract_path,
            target_version="combined",
            supplemental_versions=("source-v1",),
        )


def test_rejects_additional_citation_already_in_contract(tmp_path) -> None:
    selector_path = tmp_path / "selector.json"
    selector_path.write_text(
        json.dumps(
            {
                "name": "ca-test",
                "scopes": [
                    {
                        "jurisdiction": "ca",
                        "document_class": "policy",
                        "version": "source-v1",
                    }
                ],
            }
        )
    )
    contract_path = tmp_path / "citations.json"
    contract_path.write_text(json.dumps({"citation_paths": ["ca/policy/example"]}))

    with pytest.raises(ValueError, match="citation paths must be unique"):
        build_ca_rulespec_composite_scope(
            base=tmp_path / "corpus",
            selector_path=selector_path,
            citation_contract_path=contract_path,
            target_version="combined",
            additional_citation_paths=("ca/policy/example",),
        )


class _ConsolidateCalledError(Exception):
    def __init__(self, kwargs: dict[str, object]) -> None:
        super().__init__("consolidate_release_scopes called")
        self.kwargs = kwargs


@pytest.mark.parametrize(
    "owner",
    [pytest.param("owner", id="base-checkout"), pytest.param(None, id="no-checkout")],
)
def test_cli_reads_the_selectors_of_the_checkout_holding_base(tmp_path, monkeypatch, owner) -> None:
    selector_path = tmp_path / "selector.json"
    selector_path.write_text(
        json.dumps(
            {
                "name": "ca-test",
                "scopes": [
                    {"jurisdiction": "ca", "document_class": "policy", "version": "source-v1"}
                ],
            }
        )
    )
    contract_path = tmp_path / "citations.json"
    contract_path.write_text(json.dumps({"citation_paths": ["ca/policy/example"]}))

    def stop_at_consolidate(**kwargs: object) -> tuple[()]:
        raise _ConsolidateCalledError(kwargs)

    monkeypatch.setattr(
        ca_module,
        "cli_repo",
        lambda args: None if owner is None else tmp_path / owner,
        raising=False,
    )
    monkeypatch.setattr(ca_module, "consolidate_release_scopes", stop_at_consolidate)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_ca_rulespec_composite_scope.py",
            "--base",
            str(tmp_path / "corpus"),
            "--selector",
            str(selector_path),
            "--citation-contract",
            str(contract_path),
            "--target-version",
            "combined",
        ],
    )

    if owner is None:
        with pytest.raises(SystemExit) as exited:
            ca_module.main()
        assert exited.value.code == 2
        return
    with pytest.raises(_ConsolidateCalledError) as called:
        ca_module.main()
    assert called.value.kwargs.get("releases_dir") == tmp_path / "owner" / "manifests" / "releases"
    # The working directory's checkout is read too, as composition and dedup read it.
    assert called.value.kwargs.get("holders_of") == (Path.cwd(),)


# Finding 6 of round 2: promotion and the builder leave bases alone.
MakeCheckout = Callable[[str, Mapping[str, Mapping[str, object]]], Path]
ROOT_PATH = "ca/policy/cra/example"
PROMOTION_REFUSAL = r"^base scopes are carried unchanged and cannot be promoted in place: "


def _write_program_scope(store: CorpusArtifactStore, version: str) -> None:
    """A ca/policy scope whose contracted root carries a body, so promotion rewrites it."""
    source_path = store.source_path("ca", "policy", version, "example.txt")
    source_sha256 = store.write_text(source_path, "Primary text")
    relative_source_path = source_path.relative_to(store.root).as_posix()
    root = ProvisionRecord(
        jurisdiction="ca",
        document_class="policy",
        citation_path=ROOT_PATH,
        body="Primary text",
        id=deterministic_provision_id(ROOT_PATH, version),
        version=version,
        source_path=relative_source_path,
        level=1,
        ordinal=1,
        kind="document",
    )
    store.write_inventory(
        store.inventory_path("ca", "policy", version),
        (
            SourceInventoryItem(
                citation_path=ROOT_PATH, source_path=relative_source_path, sha256=source_sha256
            ),
        ),
    )
    store.write_provisions(store.provisions_path("ca", "policy", version), (root,))


def _ca_scopes(*, base: str | None) -> list[dict[str, str]]:
    scopes = [{"jurisdiction": "ca", "document_class": "policy", "version": "src-v"}]
    if base is not None:
        scopes.append(
            {"jurisdiction": "ca", "document_class": "policy", "version": base, "layer": "base"}
        )
    return scopes


def _write_releases(directory: Path, *, base: str | None) -> Path:
    """A selectors directory whose one selector marks ``ca/policy/<base>`` as a base."""
    directory.mkdir(parents=True)
    payload = {"name": "ca-layered", "scopes": _ca_scopes(base=base)}
    (directory / "ca-layered.json").write_text(json.dumps(payload, indent=2) + "\n")
    return directory


def _tree(root: Path) -> dict[str, bytes | None]:
    """Every entry below ``root`` outside ``.git``: a file's bytes, else None."""
    found: dict[str, bytes | None] = {}
    for directory, directories, filenames in os.walk(root):
        directories[:] = [name for name in directories if name != ".git"]
        for name in (*directories, *filenames):
            path = Path(directory, name)
            if name != ".git":
                found[str(path.relative_to(root))] = path.read_bytes() if path.is_file() else None
    return found


@pytest.mark.parametrize("through", ["releases_dir", "default"])
def test_promotion_refuses_a_tracked_base(tmp_path, monkeypatch, through) -> None:
    store = CorpusArtifactStore(tmp_path / "corpus")
    _write_program_scope(store, "base-v")
    releases = _write_releases(tmp_path / "releases", base="base-v")
    before = _tree(tmp_path)

    with pytest.raises(ValueError, match=PROMOTION_REFUSAL + "ca/policy/base-v$"):
        if through == "releases_dir":
            promote_program_roots(
                base=store.root,
                version="base-v",
                citation_paths=(ROOT_PATH,),
                releases_dir=releases,
            )
        else:
            monkeypatch.setattr(ca_module, "DEFAULT_RELEASES_DIR", releases, raising=False)
            promote_program_roots(base=store.root, version="base-v", citation_paths=(ROOT_PATH,))

    assert _tree(tmp_path) == before


@pytest.mark.parametrize("version", ["base-v ", "base-v/", "BASE-V"])
def test_promotion_refuses_a_spelling_that_names_a_tracked_base(
    tmp_path, monkeypatch, version
) -> None:
    store = CorpusArtifactStore(tmp_path / "corpus")
    _write_program_scope(store, "base-v")
    releases = _write_releases(tmp_path / "releases", base="base-v")
    monkeypatch.setattr(ca_module, "DEFAULT_RELEASES_DIR", releases, raising=False)
    before = _tree(tmp_path)

    # Each spelling names base-v's files; a selector cannot hold it.
    with pytest.raises(ValueError, match=r"^not a canonical scope: "):
        promote_program_roots(base=store.root, version=version, citation_paths=(ROOT_PATH,))

    assert _tree(tmp_path) == before


def _ca_checkout(make_checkout: MakeCheckout, name: str, *, base: str | None = None) -> Path:
    selector = f"{name}-selector"
    return make_checkout(name, {selector: {"name": selector, "scopes": _ca_scopes(base=base)}})


def _swap_for_link(path: Path, target: Path) -> None:
    """Replace the directory ``path`` with a symlink to ``target``, then forget cached roots."""
    from axiom_corpus.corpus import resolver

    shutil.rmtree(path)
    path.symlink_to(target, target_is_directory=True)
    resolver._repo_root_for_dir.cache_clear()


@pytest.mark.parametrize(
    "case",
    [
        "corpus-link",
        "hard-link",
        "tracked-base-links-to-promoted",
        "linked-holders-base-links-to-promoted",
        "holder-selector-link",
        "file-chain",
    ],
)
def test_promotion_refuses_a_base_a_link_reaches(
    tmp_path, monkeypatch, make_checkout: MakeCheckout, case
) -> None:
    if case == "corpus-link":
        # Only B, which the corpus link leads into, marks base-v as a base.
        a = _ca_checkout(make_checkout, "a")
        b = _ca_checkout(make_checkout, "b", base="base-v")
        _write_program_scope(CorpusArtifactStore(b / "data" / "corpus"), "base-v")
        (a / "data").mkdir()
        (a / "data" / "corpus").symlink_to(b / "data" / "corpus")
        store = CorpusArtifactStore(a / "data" / "corpus")
        releases, version = a / "manifests" / "releases", "base-v"
        expected = PROMOTION_REFUSAL + "ca/policy/base-v$"
    elif case == "holder-selector-link":
        # B, which A's corpus link leads into, physically holds the promoted files
        # and commits base-v as a base; B's manifests leads to A's.
        a = _ca_checkout(make_checkout, "a")
        b = _ca_checkout(make_checkout, "b", base="base-v")
        _write_program_scope(CorpusArtifactStore(b / "data" / "corpus"), "base-v")
        (a / "data").mkdir()
        (a / "data" / "corpus").symlink_to(b / "data" / "corpus")
        _swap_for_link(b / "manifests", a / "manifests")
        store = CorpusArtifactStore(a / "data" / "corpus")
        releases, version = a / "manifests" / "releases", "base-v"
        expected = "^" + re.escape(
            f"selector directory leads through a link: {b / 'manifests'} -> "
        )
    elif case == "file-chain":
        # Only B marks base-v as a base. A's files of base-v link to B's, and
        # B's to C's, which C holds as regular files.
        a = _ca_checkout(make_checkout, "a")
        b = _ca_checkout(make_checkout, "b", base="base-v")
        c = _ca_checkout(make_checkout, "c")
        held = CorpusArtifactStore(c / "data" / "corpus")
        _write_program_scope(held, "base-v")
        stores = [CorpusArtifactStore(x / "data" / "corpus") for x in (a, b)]
        for here, there in zip(stores, [*stores[1:], held], strict=True):
            for path_of in (here.inventory_path, here.provisions_path):
                link = path_of("ca", "policy", "base-v")
                link.parent.mkdir(parents=True, exist_ok=True)
                link.symlink_to(Path(there.root, link.relative_to(here.root)))
        store = stores[0]
        releases, version = a / "manifests" / "releases", "base-v"
        inventory = store.inventory_path("ca", "policy", version)
        expected = (
            "^"
            + re.escape(
                "path leads through a symlinked file at or below a checkout's guarded place: "
                f"{inventory} (the link is {inventory}); corpus files are placed as regular "
                "files, never symlinks"
            )
            + "$"
        )
    elif case == "hard-link":
        store = CorpusArtifactStore(tmp_path / "corpus")
        _write_program_scope(store, "composite-v")
        releases, version = _write_releases(tmp_path / "releases", base=None), "composite-v"
        provisions = store.provisions_path("ca", "policy", version)
        os.link(provisions, tmp_path / "other.jsonl")
        expected = (
            r"^scope artifact shares its file with another path: "
            + re.escape(str(provisions))
            + r" \(2 links\)$"
        )
    elif case == "linked-holders-base-links-to-promoted":
        # A marks no base; only B, which A's corpus link leads into, marks
        # base-w, and B's base-w provisions link to composite-v's.
        a = _ca_checkout(make_checkout, "a")
        b = _ca_checkout(make_checkout, "b", base="base-w")
        shared = CorpusArtifactStore(b / "data" / "corpus")
        _write_program_scope(shared, "composite-v")
        shared.provisions_path("ca", "policy", "base-w").symlink_to(
            shared.provisions_path("ca", "policy", "composite-v")
        )
        (a / "data").mkdir()
        (a / "data" / "corpus").symlink_to(b / "data" / "corpus")
        store = CorpusArtifactStore(a / "data" / "corpus")
        releases, version = a / "manifests" / "releases", "composite-v"
        provisions = store.provisions_path("ca", "policy", version)
        expected = (
            "^"
            + re.escape(f"{provisions} is also ca/policy/base-w's provisions through a link")
            + "$"
        )
    else:
        store = CorpusArtifactStore(tmp_path / "corpus")
        _write_program_scope(store, "composite-v")
        releases, version = _write_releases(tmp_path / "releases", base="base-w"), "composite-v"
        provisions = store.provisions_path("ca", "policy", version)
        base_provisions = store.provisions_path("ca", "policy", "base-w")
        base_provisions.symlink_to(provisions)
        expected = (
            "^"
            + re.escape(f"{provisions} is also ca/policy/base-w's provisions through a link")
            + "$"
        )
    monkeypatch.setattr(ca_module, "DEFAULT_RELEASES_DIR", releases, raising=False)
    before = _tree(tmp_path)

    with pytest.raises(ValueError, match=expected):
        promote_program_roots(base=store.root, version=version, citation_paths=(ROOT_PATH,))

    assert _tree(tmp_path) == before


@pytest.mark.parametrize(
    "scopes",
    [
        pytest.param(
            [{"jurisdiction": "ca", "document_class": "policy", "version": "draft-base"}],
            id="alone",
        ),
        pytest.param(
            [
                {"jurisdiction": "ca", "document_class": "policy", "version": "a-primary"},
                {"jurisdiction": "ca", "document_class": "policy", "version": "draft-base"},
            ],
            id="after-a-primary",
        ),
    ],
)
def test_the_builder_refuses_a_base_in_its_selector(tmp_path, monkeypatch, scopes) -> None:
    scopes[-1]["layer"] = "base"
    selector_path = tmp_path / "draft.json"
    selector_path.write_text(json.dumps({"name": "ca-draft", "scopes": scopes}))
    contract_path = tmp_path / "citations.json"
    contract_path.write_text(json.dumps({"citation_paths": [ROOT_PATH]}))

    def stop_at_consolidate(**kwargs: object) -> tuple[()]:
        raise _ConsolidateCalledError(kwargs)

    monkeypatch.setattr(ca_module, "consolidate_release_scopes", stop_at_consolidate)

    # Refused before consolidation runs.
    with pytest.raises(
        ValueError,
        match=r"^base scopes are carried unchanged and cannot be consolidated: "
        r"ca/policy/draft-base$",
    ):
        build_ca_rulespec_composite_scope(
            base=tmp_path / "corpus",
            selector_path=selector_path,
            citation_contract_path=contract_path,
            target_version="composite",
            releases_dir=_write_releases(tmp_path / "releases", base=None),
        )


def test_the_builder_hands_its_releases_dir_to_promotion(tmp_path, monkeypatch) -> None:
    store = CorpusArtifactStore(tmp_path / "corpus")
    _write_program_scope(store, "base-v")
    releases = _write_releases(tmp_path / "releases", base="base-v")
    selector_path = tmp_path / "selector.json"
    selector_path.write_text(json.dumps({"name": "ca-s", "scopes": _ca_scopes(base=None)}))
    contract_path = tmp_path / "citations.json"
    contract_path.write_text(json.dumps({"citation_paths": [ROOT_PATH]}))
    # Consolidation writes nothing, so promotion runs on the existing base-v.
    monkeypatch.setattr(ca_module, "consolidate_release_scopes", lambda **kwargs: ())
    before = _tree(tmp_path)

    with pytest.raises(ValueError, match=PROMOTION_REFUSAL + "ca/policy/base-v$"):
        build_ca_rulespec_composite_scope(
            base=store.root,
            selector_path=selector_path,
            citation_contract_path=contract_path,
            target_version="base-v",
            releases_dir=releases,
        )

    assert _tree(tmp_path) == before


def test_the_builder_hands_its_holders_to_promotion(
    tmp_path, monkeypatch, make_checkout: MakeCheckout
) -> None:
    # Only C, a checkout the caller names in holders_of, marks base-w as a base,
    # and base-w's provisions link to the target's.
    c = _ca_checkout(make_checkout, "c", base="base-w")
    store = CorpusArtifactStore(tmp_path / "corpus")
    _write_program_scope(store, "composite-v")
    provisions = store.provisions_path("ca", "policy", "composite-v")
    store.provisions_path("ca", "policy", "base-w").symlink_to(provisions)
    releases = _write_releases(tmp_path / "releases", base=None)
    selector_path = tmp_path / "selector.json"
    selector_path.write_text(json.dumps({"name": "ca-s", "scopes": _ca_scopes(base=None)}))
    contract_path = tmp_path / "citations.json"
    contract_path.write_text(json.dumps({"citation_paths": [ROOT_PATH]}))
    # Consolidation writes nothing, so promotion runs on the existing composite-v.
    monkeypatch.setattr(ca_module, "consolidate_release_scopes", lambda **kwargs: ())
    promotions: list[dict[str, object]] = []
    promote = ca_module.promote_program_roots

    def recording_promote(**kwargs):
        promotions.append(kwargs)
        return promote(**kwargs)

    monkeypatch.setattr(ca_module, "promote_program_roots", recording_promote)
    before = _tree(tmp_path)

    with pytest.raises(
        ValueError,
        match="^"
        + re.escape(f"{provisions} is also ca/policy/base-w's provisions through a link")
        + "$",
    ):
        build_ca_rulespec_composite_scope(
            base=store.root,
            selector_path=selector_path,
            citation_contract_path=contract_path,
            target_version="composite-v",
            releases_dir=releases,
            holders_of=(c,),
        )

    assert [call.get("holders_of") for call in promotions] == [(c,)]
    assert _tree(tmp_path) == before
