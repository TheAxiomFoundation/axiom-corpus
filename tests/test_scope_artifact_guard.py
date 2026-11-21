"""The scope artifact guard: the checkouts that hold a path, and aliased artifacts.

``successors.checkouts_holding`` finds the checkouts holding a path: those
whose guarded place it stands at below a symlink (the resolver's rules) and
the one it physically resolves into (by HEAD). ``guard_scope_artifacts``
refuses an artifact path that resolves to another artifact's path, a guarded
link into no checkout, and a rewritten file with more than one link, and it
returns the inventories of every holder other than the caller's own.
``refuse_links_into_bases`` refuses a file the caller rewrites, moves or
unlinks that a base's provisions, inventory, coverage, ingest manifest or
sources lead to through a link.

Each checkout is built with ``make_checkout`` under ``tmp_path``. New names
are reached through the module, so this file still loads on a tree without
them.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import pytest

from axiom_corpus.corpus import successors
from tests.conftest import fixture_git

MakeCheckout = Callable[[str, Mapping[str, Mapping[str, object]]], Path]

P = ("us", "statute", "p")
B = ("us", "statute", "b")
Q = ("us", "statute", "q")
_SUFFIX = {"provisions": ".jsonl", "inventory": ".json", "coverage": ".json"}


def _checkout(make_checkout: MakeCheckout, name: str) -> Path:
    selector = f"{name}-sel"
    payload = {
        "name": selector,
        "scopes": [{"jurisdiction": P[0], "document_class": P[1], "version": P[2]}],
    }
    return make_checkout(name, {selector: payload})


def _artifact(corpus: Path, kind: str, key: tuple[str, str, str]) -> Path:
    return corpus / kind / key[0] / key[1] / f"{key[2]}{_SUFFIX[kind]}"


def _write(path: Path, text: str = "{}\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _releases(root: Path) -> Path:
    return root / "manifests" / "releases"


def _clear_resolver_cache() -> None:
    from axiom_corpus.corpus import resolver

    resolver._repo_root_for_dir.cache_clear()


def _plain_repository(tmp_path: Path) -> Path:
    """A committed git repository whose HEAD holds no selector."""
    repository = tmp_path / "plain-repo"
    _write(repository / "README.md", "Not a checkout.\n")
    fixture_git(repository, "init", "-q", "-b", "main")
    fixture_git(repository, "add", "--", "README.md")
    fixture_git(repository, "commit", "-q", "-m", "Plain repository")
    return repository


@pytest.mark.parametrize(
    "layout",
    [
        "plain-path",
        "corpus-link",
        "class-link",
        "unguarded-link",
        "link-into-no-checkout",
        "no-checkout",
        "sparse-without-markers",
        "git-repo-without-selectors",
        "git-env",
    ],
)
def test_checkouts_holding(
    make_checkout: MakeCheckout,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    layout: str,
) -> None:
    a = _checkout(make_checkout, "a")
    b = _checkout(make_checkout, "b")
    b_file = _write(_artifact(b / "data" / "corpus", "provisions", B))
    a_corpus = a / "data" / "corpus"
    path = _artifact(a_corpus, "provisions", B)
    expected: tuple[frozenset[Path], Path | None]
    if layout == "plain-path":
        _write(path)
        expected = (frozenset(), a)
    elif layout == "corpus-link":
        a_corpus.parent.mkdir()
        a_corpus.symlink_to(b / "data" / "corpus")
        expected = (frozenset({a}), b)
    elif layout == "class-link":
        a_corpus.mkdir(parents=True)
        (a_corpus / "provisions").symlink_to(b / "data" / "corpus" / "provisions")
        expected = (frozenset({a}), b)
    elif layout == "unguarded-link":
        (a / "plain-link").symlink_to(b / "data" / "corpus")
        path = _artifact(a / "plain-link", "provisions", B)
        expected = (frozenset(), b)
    elif layout == "link-into-no-checkout":
        shared = tmp_path / "shared"
        _write(_artifact(shared, "provisions", B))
        a_corpus.parent.mkdir()
        a_corpus.symlink_to(shared)
        expected = (frozenset({a}), None)
    elif layout == "no-checkout":
        path = _write(_artifact(tmp_path / "loose" / "data" / "corpus", "provisions", B))
        expected = (frozenset(), None)
    elif layout == "sparse-without-markers":
        fixture_git(b, "sparse-checkout", "set", "--no-cone", "/*", "!/src/", "!/.axiom/")
        _clear_resolver_cache()
        assert not (b / "src").exists() and not (b / ".axiom").exists()
        from axiom_corpus.corpus import resolver

        # The resolver's markers find no checkout here; HEAD still lists selectors.
        assert resolver.find_repo_root(b_file) is None
        path = b_file
        expected = (frozenset(), b)
    elif layout == "git-repo-without-selectors":
        repository = _plain_repository(tmp_path)
        path = _write(_artifact(repository / "data" / "corpus", "provisions", B))
        expected = (frozenset(), None)
    elif layout == "git-env":
        repository = _plain_repository(tmp_path)
        path = b_file
        # Exported after every fixture git command; git would name the other repository.
        monkeypatch.setenv("GIT_DIR", str(repository / ".git"))
        monkeypatch.setenv("GIT_WORK_TREE", str(repository))
        expected = (frozenset(), b)

    assert successors.checkouts_holding(path) == expected


@pytest.mark.parametrize("layout", ["file-symlink", "directory-alias", "class-alias"])
def test_guard_refuses_an_aliased_artifact(make_checkout: MakeCheckout, layout: str) -> None:
    a = _checkout(make_checkout, "a")
    corpus = a / "data" / "corpus"
    if layout == "file-symlink":
        _write(_artifact(corpus, "provisions", B))
        guarded = _artifact(corpus, "provisions", Q)
        guarded.symlink_to(_artifact(corpus, "provisions", B))
    elif layout == "directory-alias":
        _write(_artifact(corpus, "provisions", B))
        (corpus / "provisions" / "us" / "regulation").symlink_to("statute")
        guarded = _artifact(corpus, "provisions", ("us", "regulation", "b"))
    else:
        _write(_artifact(corpus, "inventory", Q))
        guarded = _artifact(corpus, "coverage", Q)
        guarded.parent.mkdir(parents=True)
        guarded.symlink_to(_artifact(corpus, "inventory", Q))

    with pytest.raises(ValueError, match="scope artifact resolves to another path: "):
        successors.guard_scope_artifacts([guarded], releases_dir=_releases(a))


def test_guard_refuses_a_shared_file_only_when_rewritten(make_checkout: MakeCheckout) -> None:
    a = _checkout(make_checkout, "a")
    corpus = a / "data" / "corpus"
    b_file = _write(_artifact(corpus, "provisions", B))
    q_file = _artifact(corpus, "provisions", Q)
    os.link(b_file, q_file)

    with pytest.raises(
        ValueError,
        match=r"scope artifact shares its file with another path: .*q\.jsonl \(2 links\)",
    ):
        successors.guard_scope_artifacts([q_file], releases_dir=_releases(a), rewritten=[q_file])
    assert successors.guard_scope_artifacts([q_file], releases_dir=_releases(a)) == ()


def test_guard_refuses_a_guarded_link_into_no_checkout(
    make_checkout: MakeCheckout, tmp_path: Path
) -> None:
    a = _checkout(make_checkout, "a")
    shared = tmp_path / "shared"
    _write(_artifact(shared, "provisions", B))
    (a / "data").mkdir()
    (a / "data" / "corpus").symlink_to(shared)
    path = _artifact(a / "data" / "corpus", "provisions", B)

    with pytest.raises(
        ValueError,
        match="scope artifact leads through a link outside every axiom-corpus checkout: ",
    ):
        successors.guard_scope_artifacts([path], releases_dir=_releases(a))

    # The same link into a sparse checkout without markers leads into a checkout.
    b = _checkout(make_checkout, "b")
    _write(_artifact(b / "data" / "corpus", "provisions", B))
    fixture_git(b, "sparse-checkout", "set", "--no-cone", "/*", "!/src/")
    _clear_resolver_cache()
    (a / "data" / "corpus").unlink()
    (a / "data" / "corpus").symlink_to(b / "data" / "corpus")
    assert successors.guard_scope_artifacts([path], releases_dir=_releases(a)) == (_releases(b),)


def test_guard_returns_the_inventories_of_every_holder(
    make_checkout: MakeCheckout, tmp_path: Path
) -> None:
    a = _checkout(make_checkout, "a")
    b = _checkout(make_checkout, "b")
    c = _checkout(make_checkout, "c")
    d = _checkout(make_checkout, "d")
    _write(_artifact(b / "data" / "corpus", "provisions", B))
    (a / "data").mkdir()
    (a / "data" / "corpus").symlink_to(b / "data" / "corpus")
    path = _artifact(a / "data" / "corpus", "provisions", B)
    guard: Any = successors.guard_scope_artifacts

    assert guard([path], releases_dir=_releases(a)) == (_releases(b),)
    assert guard([path], releases_dir=_releases(c)) == (_releases(a), _releases(b))
    assert guard([path], releases_dir=_releases(a), holders_of=(_releases(d) / "x.json",)) == (
        _releases(b),
        _releases(d),
    )
    assert guard([path], releases_dir=_releases(b)) == (_releases(a),)

    real = tmp_path / "real"
    _write(_artifact(real, "provisions", B))
    (tmp_path / "alias").symlink_to(real)
    alias_path = _artifact(tmp_path / "alias", "provisions", B)
    assert guard([alias_path], releases_dir=_releases(c)) == ()


# A base's file that leads, through a link, to a file the tool rewrites, moves or unlinks.

C = ("us", "statute", "c")
REGULATION_Q = ("us", "regulation", "q")


def _base_corpus(tmp_path: Path) -> tuple[Path, list[Path], Path]:
    """A corpus where ``q`` holds real provisions, inventory, coverage and one source."""
    corpus = tmp_path / "corpus"
    q_files = [
        _write(_artifact(corpus, kind, Q)) for kind in ("provisions", "inventory", "coverage")
    ]
    q_sources = corpus / "sources" / "us" / "statute" / "q"
    _write(q_sources / "x" / "source.html", "<html></html>\n")
    return corpus, q_files, q_sources


@pytest.mark.parametrize(
    "layout",
    [
        "file-symlink",
        "coverage-symlink",
        "directory-alias",
        "case-alias",
        "ingest-manifest-symlink",
        "sources-dir-link",
        "sources-parent-link",
        "sources-entry-link",
        "sources-without-moved",
        "plain",
        "base-absent",
        "base-links-to-another-base",
    ],
)
def test_refuse_links_into_bases(tmp_path: Path, layout: str) -> None:
    corpus, q_files, q_sources = _base_corpus(tmp_path)
    bases: set[tuple[str, str, str]] = {B}
    arguments: dict[str, Any] = {"rewritten": q_files}
    expected: str | None = None
    if layout == "file-symlink":
        _artifact(corpus, "provisions", B).symlink_to(_artifact(corpus, "provisions", Q))
        expected = r"q\.jsonl is also us/statute/b's provisions through a link"
    elif layout == "coverage-symlink":
        _artifact(corpus, "coverage", B).symlink_to(_artifact(corpus, "coverage", Q))
        expected = r"q\.json is also us/statute/b's coverage through a link"
    elif layout == "directory-alias":
        (corpus / "provisions" / "us" / "regulation").symlink_to("statute")
        bases = {REGULATION_Q}
        expected = r"q\.jsonl is also us/regulation/q's provisions through a link"
    elif layout == "case-alias":
        (corpus / "provisions" / "us" / "regulation").symlink_to(Path("..") / "US" / "statute")
        if not (corpus / "provisions" / "US").exists():
            pytest.skip("the filesystem keeps us and US apart, so there is no case alias")
        bases = {REGULATION_Q}
        expected = r"q\.jsonl is also us/regulation/q's provisions through a link"
    elif layout == "ingest-manifest-symlink":
        ingest = tmp_path / "ingest"
        q_manifest = _write(ingest / "us" / "statute" / "q.json")
        (ingest / "us" / "statute" / "b.json").symlink_to("q.json")
        arguments = {"rewritten": [*q_files, q_manifest], "ingest_manifests": ingest}
        expected = r"q\.json is also us/statute/b's ingest manifest through a link"
    elif layout in {"sources-dir-link", "sources-without-moved"}:
        (corpus / "sources" / "us" / "statute" / "b").symlink_to("q")
        if layout == "sources-dir-link":
            arguments = {"moved": [q_sources]}
            expected = "/q is also us/statute/b's sources through a link"
    elif layout == "sources-parent-link":
        (corpus / "sources" / "us" / "statute" / "b").symlink_to(".")
        arguments = {"moved": [q_sources]}
        expected = "/q is also us/statute/b's sources through a link"
    elif layout == "sources-entry-link":
        entry = corpus / "sources" / "us" / "statute" / "b" / "x" / "source.html"
        entry.parent.mkdir(parents=True)
        entry.symlink_to(q_sources / "x" / "source.html")
        arguments = {"moved": [q_sources]}
        expected = "/q is also us/statute/b's sources through a link"
    elif layout == "plain":
        for kind in ("provisions", "inventory", "coverage"):
            _write(_artifact(corpus, kind, B))
    elif layout == "base-links-to-another-base":
        _write(_artifact(corpus, "provisions", C))
        _artifact(corpus, "provisions", B).symlink_to(_artifact(corpus, "provisions", C))
        bases = {B, C}

    if expected is None:
        assert successors.refuse_links_into_bases(corpus=corpus, bases=bases, **arguments) is None
        return
    with pytest.raises(ValueError, match=expected):
        successors.refuse_links_into_bases(corpus=corpus, bases=bases, **arguments)
