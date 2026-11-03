"""Tests for scripts/sweep_pdf_amendment_markup.py, and a differential over fixture PDFs.

Invariants:

* ``read_marked_text`` (the sweep's reader, written apart from the extractor so
  that it reads the markup of any version) splits every markup the extractor
  accepts exactly as ``documents._amendment_markup_runs`` does, and gives back
  the normalized text (Hypothesis, on rendered markup).
* ``expand_signature(state_signature(runs))`` is one state per non-space
  character of the runs, in order.
* ``classify_page`` calls a page read alike on both sides ``identical``;
  exchanging the sides exchanges ``marks_removed`` and ``marks_added``, and
  ``fixed`` and ``newly_refused``; a default text that differs always fails.
* End to end, over fixture PDFs and two code trees, the sweep calls a page
  ``fixed`` exactly where the base refuses it and the working tree marks it,
  every other page ``identical``, and fails when the base marks less.
* Differential over the cited Maryland PDFs: on every page, the extractor's
  marked text reads back to the default page text, and main's strip (remove
  every occurrence of each delimiter) gives the same text back on every page but
  the struck-bracket pages ``_SWEPT_PAGES`` lists. So main, which checks that
  strip, extracts every other page of these PDFs exactly as this branch does.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import warnings
from pathlib import Path
from typing import Any

import fitz  # type: ignore[import-untyped]
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus import documents as documents_module
from axiom_corpus.corpus.documents import (
    PdfAmendmentMarkupWarning,
    _amendment_markup_runs,
    _normalize_text,
    _render_amendment_markup,
)
from scripts.sweep_pdf_amendment_markup import (
    DEFAULT,
    DETAIL,
    OUTCOME,
    STATES,
    classify_page,
    expand_signature,
    export_tree,
    main,
    read_marked_text,
    state_signature,
)
from tests.test_corpus_documents_pdf_amendment_markup_reading import (
    _SWEPT_PAGES,
    SOURCES,
    _marked_text,
    _naive_strip,
    _pdf_with_marked_parts,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
D, I = "deleted", "inserted"  # noqa: E741
LETTER = {None: "P", D: "D", I: "I"}


# --------------------------------------------------------------- the reader


@settings(max_examples=800, deadline=None)
@given(_marked_text())
def test_the_sweep_reads_accepted_markup_as_the_extractor_does(
    case: tuple[str, list[str | None]],
) -> None:
    raw, states = case
    rendered = _render_amendment_markup(raw, states)
    if rendered.delimiters_in_text or any(
        token in raw for token in documents_module._AMENDMENT_MARKUP_TOKENS
    ):
        return
    runs = read_marked_text(rendered.text)
    assert [(text, state) for text, state in runs] == [
        (text, LETTER[state]) for text, state in _amendment_markup_runs(rendered.text)
    ]
    assert "".join(text for text, _state in runs) == _normalize_text(raw)


def test_the_sweep_reads_a_struck_bracket_and_refuses_an_open_run() -> None:
    assert read_marked_text("the budget bill [-[-]shall[-] MAY-] specify") == [
        ("the budget bill ", "P"),
        ("[", "D"),
        ("shall", "P"),
        ("] MAY", "D"),
        (" specify", "P"),
    ]
    assert read_marked_text("keep {+{+}x") == [("keep ", "P"), ("{", "I"), ("x", "P")]
    with pytest.raises(ValueError, match="never closed"):
        read_marked_text("a [-b")


@settings(max_examples=300, deadline=None)
@given(
    st.lists(st.tuples(st.text(alphabet="ab \n", max_size=6), st.sampled_from("PDI")), max_size=8)
)
def test_a_state_signature_expands_to_one_state_per_non_space_character(
    runs: list[tuple[str, str]],
) -> None:
    expected = "".join(
        state for text, state in runs for character in text if not character.isspace()
    )
    assert expand_signature(state_signature(runs)) == expected


# ------------------------------------------------------------- classify_page


def _ok(states: str, text: str = "t", default: str = "d") -> list[Any]:
    return [default, 1, "ok", text, "m", states, "w", 0]


def _error(message: str, default: str = "d") -> list[Any]:
    return [default, 1, "error", message, "", "", "", 0]


PAGES = st.one_of(
    st.builds(
        _ok,
        st.sampled_from(["P3", "D1P2", "P1I2", "D3", "I1D1P1", "P2D1"]),
        st.sampled_from(["t", "u"]),
        st.sampled_from(["d", "e"]),
    ),
    st.builds(_error, st.sampled_from(["RuntimeError: x", "ValueError: y"]), st.sampled_from("de")),
)
SWAPPED = {
    "marks_removed": "marks_added",
    "marks_added": "marks_removed",
    "fixed": "newly_refused",
    "newly_refused": "fixed",
}


@settings(max_examples=500, deadline=None)
@given(PAGES, PAGES)
def test_exchanging_the_sides_exchanges_the_directed_outcomes(
    base: list[Any], head: list[Any]
) -> None:
    outcome = classify_page(base, head)
    assert classify_page(base, base) == "identical"
    assert classify_page(head, base) == SWAPPED.get(outcome, outcome)
    if base[DEFAULT] != head[DEFAULT]:
        assert outcome == "default_text_changed"
    if outcome == "identical":
        assert base[OUTCOME] == head[OUTCOME] and base[DETAIL] == head[DETAIL]


def test_classify_page_names_each_kind_of_change() -> None:
    assert classify_page(_ok("P1D2"), _ok("P3", text="u")) == "marks_removed"
    assert classify_page(_ok("P3"), _ok("P1D2", text="u")) == "marks_added"
    assert classify_page(_ok("P1D2"), _ok("P1I2", text="u")) == "marks_changed"
    assert classify_page(_ok("P1D2"), _ok("P1D2", text="u")) == "same_marks_other_output"
    assert classify_page(_error("RuntimeError: x"), _ok("P3")) == "fixed"
    assert (
        classify_page(_error("RuntimeError: x"), _error("ValueError: y")) == "refused_differently"
    )
    assert classify_page(_ok("P3"), _ok("mismatch", text="u")) == "read_back_mismatch"
    assert classify_page(_error("RuntimeError: x"), _ok("mismatch")) == "read_back_mismatch"
    assert classify_page(_ok("P3"), _ok("P3", default="e")) == "default_text_changed"
    assert classify_page(_ok("P3"), _error("ValueError: y")) == "newly_refused"
    page = _ok("P3")
    page[STATES] = "P3"
    assert classify_page(page, list(page)) == "identical"


# --------------------------------------------------------------- end to end


def _base_tree(tmp_path: Path, name: str, override: str) -> Path:
    """A copy of this checkout's src whose documents module ends with ``override``."""
    src = tmp_path / name / "src"
    shutil.copytree(
        REPO_ROOT / "src" / "axiom_corpus",
        src / "axiom_corpus",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    module = src / "axiom_corpus" / "corpus" / "documents.py"
    module.write_text(module.read_text(encoding="utf-8") + "\n\n" + override, encoding="utf-8")
    return src


# main's strip: remove every occurrence of each delimiter.
MAIN_STRIP = """
def _strip_amendment_markup(text: str) -> str:
    for token in _AMENDMENT_MARKUP_TOKENS:
        text = text.replace(token, "")
    return text
"""
# No rule is ever at a strike offset.
NO_STRIKES = "_PDF_STRIKE_OFFSET_RANGE = (50.0, 60.0)\n"


def _fixture_pdfs(directory: Path) -> list[Path]:
    """A PDF without rules, one with a strike and an underline, one with a struck "["."""
    plain = fitz.open()
    plain.new_page().insert_text((72, 100), "No markup on this page.", fontname="helv")
    pdfs = {
        "plain.pdf": plain.tobytes(),
        "marked.pdf": _pdf_with_marked_parts(
            [("keep ", None), ("old", D), (" and ", None), ("new", I), (" text", None)]
        ),
        "bracket.pdf": _pdf_with_marked_parts(
            [
                ("the budget bill ", None),
                ("[", D),
                ("shall", None),
                ("] MAY", D),
                (" specify", None),
            ]
        ),
    }
    plain.close()
    paths = []
    for name, content in pdfs.items():
        path = directory / name
        path.write_bytes(content)
        paths.append(path)
    return paths


def test_the_sweep_compares_two_trees_over_fixture_pdfs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pdfs = _fixture_pdfs(tmp_path)
    out = tmp_path / "sweep"
    listed = [argument for path in pdfs for argument in ("--pdf", str(path))]
    run = ["run", "--out-dir", str(out), "--workers", "1", "--timeout", "120", *listed]

    main_like = _base_tree(tmp_path, "main-like", MAIN_STRIP)
    assert main([*run, "--base-src", str(main_like)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["verdict"] == "pass"
    assert report["pages"] == {"fixed": 1, "identical": 2}
    details = [json.loads(line) for line in (out / "details.jsonl").read_text().splitlines()]
    assert [(Path(item["path"]).name, item["outcome"]) for item in details] == [
        ("bracket.pdf", "fixed")
    ]
    assert "amendment markup changed the text of PDF page 1" in details[0]["base"]

    # A base that strikes nothing: the working tree marks more, and the sweep fails.
    no_strikes = _base_tree(tmp_path, "no-strikes", NO_STRIKES)
    assert main([*run, "--base-src", str(no_strikes)]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["failing"] == {"marks_added": 2}
    assert report["pages"] == {"identical": 1, "marks_added": 2}
    # The working tree's snapshot is reused, and --allow accepts the outcome.
    assert len(list(out.glob("snapshot-*.jsonl"))) == 3
    snapshots = report["snapshots"]
    compare = ["compare", "--out-dir", str(out), "--allow", "marks_added"]
    compare += ["--base", str(out / snapshots["base"]), "--head", str(out / snapshots["head"])]
    assert main(compare) == 0
    assert json.loads(capsys.readouterr().out)["verdict"] == "pass"


def test_the_sweep_refuses_a_base_that_is_the_working_tree(tmp_path: Path) -> None:
    same = tmp_path / "same" / "src"
    shutil.copytree(
        REPO_ROOT / "src" / "axiom_corpus",
        same / "axiom_corpus",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    pdf = _fixture_pdfs(tmp_path)[0]
    with pytest.raises(SystemExit):
        main(["run", "--base-src", str(same), "--out-dir", str(tmp_path / "o"), "--pdf", str(pdf)])


def test_a_missing_pdf_leaves_the_sweep_incomplete(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    base = _base_tree(tmp_path, "main-like", MAIN_STRIP)
    missing = tmp_path / "missing.pdf"
    args = ["run", "--base-src", str(base), "--out-dir", str(tmp_path / "o"), "--workers", "1"]
    assert main([*args, "--pdf", str(missing)]) == 2
    report = json.loads(capsys.readouterr().out)
    assert report["verdict"] == "incomplete"
    assert report["incomplete"] == {"unreadable": 1}


def test_export_tree_writes_the_package_at_a_commit(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    package = repo / "src" / "axiom_corpus" / "corpus"
    package.mkdir(parents=True)
    (package / "documents.py").write_text("VALUE = 1\n")

    def git(*args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
        ).stdout

    git("init", "-q")
    git("add", ".")
    git("-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-qm", "base")
    (package / "documents.py").write_text("VALUE = 2\n")
    src, commit = export_tree(repo, "HEAD", tmp_path / "out")
    assert commit == git("rev-parse", "HEAD").strip()
    assert (src / "axiom_corpus" / "corpus" / "documents.py").read_text() == "VALUE = 1\n"
    # A second export reuses the first.
    assert export_tree(repo, "HEAD", tmp_path / "out") == (src, commit)


# ------------------------------------------- differential over the cited PDFs


_MARYLAND = [(relative, pages) for relative, pages in _SWEPT_PAGES if relative.startswith("us-md/")]


@pytest.mark.parametrize(("relative", "swept"), _MARYLAND, ids=[r for r, _p in _MARYLAND])
def test_main_extracts_every_other_page_of_the_cited_maryland_pdfs_alike(
    relative: str, swept: tuple[int, ...]
) -> None:
    extraction: dict[str, Any] = {"amendment_markup": True}
    markup = documents_module._pdf_amendment_markup_config(extraction)
    misread_by_main = []
    marked = 0
    with fitz.open(SOURCES / relative) as document:
        for number, page in enumerate(document, start=1):
            default_text = _normalize_text(documents_module._pdf_page_text(page, extraction={}))
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", PdfAmendmentMarkupWarning)
                    text, _metadata = documents_module._pdf_page_layered_text(
                        page, extraction=extraction, markup=markup, page_number=number
                    )
            except ValueError as error:
                # Refused before any markup is written (a character both struck and
                # underlined), by code main shares, so main refuses it the same way.
                assert "both struck through and underlined" in str(error), (number, error)
                continue
            marked += 1
            assert documents_module._strip_amendment_markup(text) == default_text, number
            if _naive_strip(text) != default_text:
                misread_by_main.append(number)
    assert tuple(misread_by_main) == swept
    assert marked > len(swept)
