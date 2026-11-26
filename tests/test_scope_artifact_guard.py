"""The scope artifact guard: the checkouts that hold a path, and aliased artifacts.

``successors.checkouts_holding`` finds the checkouts holding a path: those
whose guarded place it stands at below a symlink (the resolver's rules) and
the one it physically resolves into (by HEAD). ``guard_scope_artifacts``
refuses an artifact path that resolves to another artifact's path, a guarded
link into no checkout, and a rewritten file with more than one link, and it
returns the inventories of the holders it finds, other than the caller's own.
``refuse_links_into_bases`` refuses a file the caller rewrites, moves or
unlinks that a base's provisions, inventory, coverage, ingest manifest or
sources lead to through a link.

Each checkout is built with ``make_checkout`` under ``tmp_path``. New names
are reached through the module, so this file still loads on a tree without
them.
"""

from __future__ import annotations

import json
import os
import re
import shutil
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
        "unguarded-file-link",
        "directory-chain",
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
    elif layout == "unguarded-file-link":
        # A pointer at no guarded place, reached by no guarded link, is followed.
        path = tmp_path / "pointer.jsonl"
        path.symlink_to(b_file)
        expected = (frozenset(), b)
    elif layout == "directory-chain":
        # Directory links at two checkouts' guarded places are both link holders.
        c = _checkout(make_checkout, "c")
        _write(_artifact(c / "data" / "corpus", "provisions", B))
        shutil.rmtree(b / "data" / "corpus" / "provisions")
        (b / "data" / "corpus" / "provisions").symlink_to(c / "data" / "corpus" / "provisions")
        a_corpus.parent.mkdir()
        a_corpus.symlink_to(b / "data" / "corpus")
        expected = (frozenset({a, b}), c)

    assert successors.checkouts_holding(path) == expected


FILE_LINK_REFUSAL = "path leads through a symlinked file at or below a checkout's guarded place: "


def _file_link_refusal(path: Path, link: Path) -> str:
    return (
        "^"
        + re.escape(
            f"{FILE_LINK_REFUSAL}{path} (the link is {link}); corpus files are placed as "
            "regular files, never symlinks"
        )
        + "$"
    )


def _relink_file(path: Path, target: Path | str) -> None:
    """Make ``path`` a symlink to ``target``, replacing whatever stands there."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or path.exists():
        path.unlink()
    path.symlink_to(target)


@pytest.mark.parametrize(
    "layout",
    [
        "direct-file-link",
        "file-chain",
        "three-hop",
        "relative-file-link",
        "file-into-linked-corpus",
        "directory-then-file",
        "pointer-between",
        "dangling-file-link",
        "file-link-cycle",
    ],
)
def test_checkouts_holding_refuses_a_path_through_a_symlinked_file(
    make_checkout: MakeCheckout, tmp_path: Path, layout: str
) -> None:
    a, b, c, d = (_checkout(make_checkout, name) for name in "abcd")
    a_file, b_file, c_file, d_file = (
        _artifact(checkout / "data" / "corpus", "provisions", B) for checkout in (a, b, c, d)
    )
    # The link the walk stops at: A's own file unless the row says otherwise.
    link = a_file
    if layout == "direct-file-link":
        _write(b_file)
        _relink_file(a_file, b_file)
    elif layout == "file-chain":
        _write(c_file)
        _relink_file(b_file, c_file)
        _relink_file(a_file, b_file)
    elif layout == "three-hop":
        _write(d_file)
        _relink_file(c_file, d_file)
        _relink_file(b_file, c_file)
        _relink_file(a_file, b_file)
    elif layout == "relative-file-link":
        _write(b_file)
        _relink_file(a_file, os.path.relpath(b_file, a_file.parent))
    elif layout == "file-into-linked-corpus":
        # A's file names B's spelled path, and B's corpus leads into C's.
        _write(c_file)
        (b / "data").mkdir()
        (b / "data" / "corpus").symlink_to(c / "data" / "corpus")
        _relink_file(a_file, b_file)
    elif layout == "directory-then-file":
        _write(c_file)
        _relink_file(b_file, c_file)
        (a / "data").mkdir()
        (a / "data" / "corpus").symlink_to(b / "data" / "corpus")
        link = b_file
    elif layout == "pointer-between":
        # A's corpus leads to a plain directory, whose file is a pointer into B.
        shared = tmp_path / "shared"
        _write(c_file)
        _relink_file(b_file, c_file)
        pointer = _artifact(shared, "provisions", B)
        _relink_file(pointer, b_file)
        (a / "data").mkdir()
        (a / "data" / "corpus").symlink_to(shared)
        link = pointer
    elif layout == "dangling-file-link":
        b_file.parent.mkdir(parents=True)
        _relink_file(a_file, b_file)
    elif layout == "file-link-cycle":
        _relink_file(a_file, b_file)
        _relink_file(b_file, a_file)
    _clear_resolver_cache()

    with pytest.raises(ValueError, match=_file_link_refusal(a_file, link)):
        successors.checkouts_holding(a_file)


def test_guard_refuses_a_holders_of_path_through_a_symlinked_file(
    make_checkout: MakeCheckout,
) -> None:
    a = _checkout(make_checkout, "a")
    b = _checkout(make_checkout, "b")
    plain = _write(_artifact(a / "data" / "corpus", "provisions", P))
    b_file = _write(_artifact(b / "data" / "corpus", "provisions", B))
    a_file = _artifact(a / "data" / "corpus", "provisions", B)
    _relink_file(a_file, b_file)
    _clear_resolver_cache()

    with pytest.raises(ValueError, match=_file_link_refusal(a_file, a_file)):
        successors.guard_scope_artifacts([plain], releases_dir=_releases(a), holders_of=(a_file,))


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


# A holder's selector directory, or the caller's, that a link or another git
# repository answers for is refused, not dropped as a duplicate or read at
# another repository's HEAD.

LINK_REFUSAL = "^selector directory leads through a link: "
GIT_ENTRY_REFUSAL = "^selector directory sits at a git entry: "


def _swap_for_link(path: Path, target: Path) -> None:
    """Replace the directory ``path`` with a symlink to ``target``."""
    shutil.rmtree(path)
    path.symlink_to(target, target_is_directory=True)


def _marking_checkout(make_checkout: MakeCheckout, name: str) -> Path:
    """A checkout whose committed selector marks ``B`` as a base."""
    selector = f"{name}-sel"
    payload = {
        "name": selector,
        "scopes": [
            {"jurisdiction": P[0], "document_class": P[1], "version": P[2]},
            {"jurisdiction": B[0], "document_class": B[1], "version": B[2], "layer": "base"},
        ],
    }
    return make_checkout(name, {selector: payload})


@pytest.mark.parametrize(
    "layout", ["holder-releases-link", "holder-manifests-link", "releases-dir-link"]
)
def test_guard_refuses_a_selector_directory_reached_through_a_link(
    make_checkout: MakeCheckout, tmp_path: Path, layout: str
) -> None:
    a = _checkout(make_checkout, "a")
    path = _write(_artifact(a / "data" / "corpus", "provisions", B))
    c = _checkout(make_checkout, "c")
    if layout == "holder-releases-link":
        # Without the refusal, A's inventory has C's realpath and is dropped as C's.
        link = _releases(a)
        _swap_for_link(link, _releases(c))
        releases_dir = _releases(c)
    elif layout == "holder-manifests-link":
        b = _checkout(make_checkout, "b")
        link = a / "manifests"
        _swap_for_link(link, b / "manifests")
        releases_dir = _releases(c)
    else:
        link = tmp_path / "sel"
        link.symlink_to(_releases(c), target_is_directory=True)
        releases_dir = link
    _clear_resolver_cache()

    with pytest.raises(ValueError, match=LINK_REFUSAL + re.escape(f"{link} -> ")):
        successors.guard_scope_artifacts([path], releases_dir=releases_dir)


@pytest.mark.parametrize(
    "layout",
    [
        "holder-nested-repo-at-manifests",
        "holder-nested-repo-at-releases",
        "holder-gitfile-at-manifests",
        "releases-dir-core-worktree-redirect",
        "holder-ceiling-at-manifests",
        "holder-ceiling-at-checkout",
    ],
)
def test_guard_refuses_a_holder_that_another_git_repository_answers_for(
    make_checkout: MakeCheckout, monkeypatch: pytest.MonkeyPatch, layout: str
) -> None:
    a = _marking_checkout(make_checkout, "a")
    other = _checkout(make_checkout, "other")
    third = _checkout(make_checkout, "third")
    path = _write(_artifact(a / "data" / "corpus", "provisions", B))
    releases = _releases(a)
    releases_dir = _releases(third)
    holders_of: tuple[Path, ...] = ()
    ceiling: Path | None = None
    refusal: tuple[type[Exception], str] | None = None
    plain = {
        "name": "plain",
        "scopes": [{"jurisdiction": P[0], "document_class": P[1], "version": P[2]}],
    }

    def hide_the_selector_beside_a_plain_one(*, whole_manifests: bool) -> None:
        if whole_manifests:
            fixture_git(a, "sparse-checkout", "set", "--no-cone", "/*", "!/manifests/")
        else:
            fixture_git(a, "update-index", "--skip-worktree", "manifests/releases/a-sel.json")
            (releases / "a-sel.json").unlink()
        _write(releases / "plain.json", json.dumps(plain) + "\n")

    if layout == "holder-nested-repo-at-manifests":
        hide_the_selector_beside_a_plain_one(whole_manifests=True)
        fixture_git(a / "manifests", "init", "-q")
        entry = a / "manifests" / ".git"
        refusal = (ValueError, GIT_ENTRY_REFUSAL + re.escape(str(entry)))
    elif layout == "holder-nested-repo-at-releases":
        hide_the_selector_beside_a_plain_one(whole_manifests=False)
        fixture_git(releases, "init", "-q")
        entry = releases / ".git"
        refusal = (ValueError, GIT_ENTRY_REFUSAL + re.escape(str(entry)))
    elif layout == "holder-gitfile-at-manifests":
        hide_the_selector_beside_a_plain_one(whole_manifests=True)
        entry = a / "manifests" / ".git"
        entry.write_text(f"gitdir: {other / '.git'}\n", encoding="utf-8")
        refusal = (ValueError, GIT_ENTRY_REFUSAL + re.escape(str(entry)))
    elif layout == "releases-dir-core-worktree-redirect":
        hide_the_selector_beside_a_plain_one(whole_manifests=False)
        fixture_git(a, "config", "core.worktree", str(other))
        releases_dir, holders_of = releases, (a,)
        refusal = (
            FileNotFoundError,
            r"^selector directory is not the manifests/releases of the toplevel git names \("
            + re.escape(str(other))
            + r"\), while a \.git entry sits two levels up at "
            + re.escape(str(a / ".git")),
        )
    elif layout == "holder-ceiling-at-manifests":
        ceiling = a / "manifests"
    else:
        assert layout == "holder-ceiling-at-checkout"
        ceiling = a
    _clear_resolver_cache()
    if ceiling is not None:
        # Exported after every fixture git command; git would stop its search there.
        monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(ceiling))

    def run() -> tuple[frozenset[Any], tuple[Path, ...], list[frozenset[Any]]]:
        # As each tool does: read releases_dir, guard, then read each inventory.
        own = successors.tracked_base_scopes(releases_dir)
        inventories = successors.guard_scope_artifacts(
            [path], releases_dir=releases_dir, holders_of=holders_of
        )
        return own, inventories, [successors.tracked_base_scopes(i) for i in inventories]

    if refusal is None:
        assert run() == (frozenset(), (releases,), [frozenset({B})])
        return
    error, pattern = refusal
    with pytest.raises(error, match=pattern):
        run()


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
        "hard-link",
        "ingest-manifest-symlink",
        "sources-dir-link",
        "sources-parent-link",
        "sources-entry-link",
        "file-into-moved",
        "sources-entry-to-rewritten",
        "sources-dir-into-moved",
        "sources-case-alias",
        "sources-without-moved",
        "plain",
        "base-absent",
        "base-links-to-another-base",
        "sources-entry-to-moved-parent",
        "sources-entry-to-rewritten-parent",
        "sources-entry-case-alias-of-rewritten",
        "sources-entry-to-hard-link-of-rewritten",
        "sources-entry-case-alias-of-moved-parent",
        "file-into-moved-case-alias",
        "sources-dir-to-case-alias-of-moved-parent",
        "sources-dir-to-rewritten-parent",
        "sources-entry-link-loop",
        "sources-entry-link-through-a-file",
        "sources-entry-to-sibling",
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
    elif layout == "hard-link":
        os.link(_artifact(corpus, "provisions", Q), _artifact(corpus, "provisions", B))
        expected = r"q\.jsonl is also us/statute/b's provisions through a link"
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
    elif layout == "file-into-moved":
        _artifact(corpus, "provisions", B).symlink_to(q_sources / "x" / "source.html")
        arguments = {"moved": [q_sources]}
        expected = "/q is also us/statute/b's provisions through a link"
    elif layout == "sources-entry-to-rewritten":
        entry = corpus / "sources" / "us" / "statute" / "b" / "x" / "source.html"
        entry.parent.mkdir(parents=True)
        entry.symlink_to(_artifact(corpus, "provisions", Q))
        arguments = {"rewritten": q_files, "moved": [q_sources]}
        expected = r"q\.jsonl is also us/statute/b's sources through a link"
    elif layout == "sources-dir-into-moved":
        (corpus / "sources" / "us" / "statute" / "b").symlink_to(Path("q") / "x")
        arguments = {"moved": [q_sources]}
        expected = "/q is also us/statute/b's sources through a link"
    elif layout == "sources-case-alias":
        (corpus / "sources" / "us" / "statute" / "b").symlink_to("Q")
        if not (corpus / "sources" / "us" / "statute" / "Q").exists():
            pytest.skip("the filesystem keeps q and Q apart, so there is no case alias")
        arguments = {"moved": [q_sources]}
        expected = "/q is also us/statute/b's sources through a link"
    elif layout == "plain":
        for kind in ("provisions", "inventory", "coverage"):
            _write(_artifact(corpus, kind, B))
    elif layout == "base-links-to-another-base":
        _write(_artifact(corpus, "provisions", C))
        _artifact(corpus, "provisions", B).symlink_to(_artifact(corpus, "provisions", C))
        bases = {B, C}
    elif layout.startswith("sources-entry-"):
        # A link below b's sources, compared with q's files and q's sources.
        statute_sources = corpus / "sources" / "us" / "statute"
        b_sources = statute_sources / "b"
        b_sources.mkdir()
        alias = b_sources / "alias"
        arguments = {"rewritten": q_files, "moved": [q_sources]}
        moved_refusal = "/q is also us/statute/b's sources through a link"
        rewritten_refusal = r"q\.jsonl is also us/statute/b's sources through a link"
        if layout == "sources-entry-to-moved-parent":
            alias.symlink_to(statute_sources)
            expected = moved_refusal
        elif layout == "sources-entry-to-rewritten-parent":
            alias.symlink_to(corpus / "provisions" / "us" / "statute")
            expected = rewritten_refusal
        elif layout == "sources-entry-case-alias-of-rewritten":
            alias.symlink_to(corpus / "provisions" / "us" / "statute" / "Q.jsonl")
            if not alias.exists():
                pytest.skip("the filesystem keeps q and Q apart, so there is no case alias")
            expected = rewritten_refusal
        elif layout == "sources-entry-to-hard-link-of-rewritten":
            hard = tmp_path / "h.jsonl"
            os.link(q_files[0], hard)
            alias.symlink_to(hard)
            expected = rewritten_refusal
        elif layout == "sources-entry-case-alias-of-moved-parent":
            alias.symlink_to(corpus / "SOURCES" / "us" / "statute")
            if not alias.exists():
                pytest.skip("the filesystem keeps sources and SOURCES apart")
            arguments = {"moved": [q_sources]}
            expected = moved_refusal
        elif layout == "sources-entry-link-loop":
            loop = b_sources / "loop"
            loop.symlink_to("loop")
            arguments = {"moved": [q_sources]}
            expected = "loop is a link below us/statute/b's sources that cannot be followed \\("
        elif layout == "sources-entry-link-through-a-file":
            _write(b_sources / "plainfile.html", "<p>b</p>\n")
            (b_sources / "through-file").symlink_to(Path("plainfile.html") / "x")
            arguments = {"moved": [q_sources]}
            expected = (
                "through-file is a link below us/statute/b's sources that cannot be followed \\("
            )
        elif layout == "sources-entry-to-sibling":
            _write(statute_sources / "c" / "c.html", "<p>c</p>\n")
            alias.symlink_to(statute_sources / "c")
        else:
            raise AssertionError(layout)
    elif layout == "file-into-moved-case-alias":
        _artifact(corpus, "provisions", B).symlink_to(
            corpus / "sources" / "us" / "statute" / "Q" / "x" / "source.html"
        )
        if not _artifact(corpus, "provisions", B).exists():
            pytest.skip("the filesystem keeps q and Q apart, so there is no case alias")
        arguments = {"moved": [q_sources]}
        expected = "/q is also us/statute/b's provisions through a link"
    elif layout == "sources-dir-to-case-alias-of-moved-parent":
        regulation_sources = corpus / "sources" / "us" / "regulation"
        regulation_sources.mkdir(parents=True)
        (regulation_sources / "b").symlink_to(corpus / "SOURCES" / "us" / "statute")
        if not (regulation_sources / "b").exists():
            pytest.skip("the filesystem keeps sources and SOURCES apart")
        bases = {("us", "regulation", "b")}
        arguments = {"moved": [q_sources]}
        expected = "/q is also us/regulation/b's sources through a link"
    elif layout == "sources-dir-to-rewritten-parent":
        (corpus / "sources" / "us" / "statute" / "b").symlink_to(
            Path("..") / ".." / ".." / "provisions" / "us" / "statute"
        )
        arguments = {"rewritten": q_files, "moved": [q_sources]}
        expected = r"q\.jsonl is also us/statute/b's sources through a link"

    if expected is None:
        assert successors.refuse_links_into_bases(corpus=corpus, bases=bases, **arguments) is None
        return
    with pytest.raises(ValueError, match=expected):
        successors.refuse_links_into_bases(corpus=corpus, bases=bases, **arguments)
