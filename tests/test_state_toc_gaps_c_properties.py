"""Container failures leave coverage incomplete for every mix of failures.

For any set of containers and any assignment of outcomes to them, the run keeps
every container it selected in the inventory, writes a provision only for what
it could read, logs one error per lost container, and reads complete exactly
when nothing failed. Every gap points at a file the run wrote, with a matching
hash: the parent listing when the run could not fetch the page, otherwise the
page itself. A container empty by law stays complete. Indiana writes the same
artifacts from a source directory as from the Code ZIP, and Oregon the same
whether one worker or several discover its chapters. A run that writes no
provision at all still raises, as it did before.
"""

import hashlib
import json
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.state_adapters import oregon
from axiom_corpus.corpus.state_adapters.indiana import (
    INDIANA_CODE_SOURCE_FORMAT,
    extract_indiana_code,
)
from axiom_corpus.corpus.state_adapters.oregon import (
    OREGON_ORS_SOURCE_FORMAT,
    extract_oregon_ors,
)
from axiom_corpus.corpus.state_adapters.south_carolina import (
    SOUTH_CAROLINA_SOURCE_FORMAT,
    extract_south_carolina_code,
)
from tests.test_corpus_oregon import SAMPLE_OREGON_LANDING as OR_LANDING
from tests.test_state_extraction_gaps import MAINTENANCE, _write_sources

VERSION = "2026-05-09"
_UNUSABLE = {
    "maintenance": MAINTENANCE,
    "empty": "",
    "wrong-shape": "<html><body><main><h1>Search results</h1><p>No entries.</p></main></body></html>",
}
_SETTINGS = settings(
    max_examples=40,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)


def _artifacts(report) -> tuple[str, str, str]:
    return (
        report.inventory_path.read_text(),
        report.provisions_path.read_text(),
        report.coverage_path.read_text(),
    )


def _assert_gaps(store, report, *, expected: set[str], failed: dict[str, str]) -> None:
    """Coverage lists exactly the failed containers, each sourced from the given page."""
    inventory = load_source_inventory(report.inventory_path)
    provisions = load_provisions(report.provisions_path)
    assert {item.citation_path for item in inventory} == expected
    assert {record.citation_path for record in provisions} == expected - set(failed)
    assert len(inventory) == len(expected)
    assert len(report.errors) == len(failed)
    assert report.coverage.complete is (not failed)
    assert set(report.coverage.missing_from_provisions) == set(failed)
    assert json.loads(report.coverage_path.read_text())["complete"] is (not failed)
    for item in inventory:
        if item.citation_path not in failed:
            continue
        assert item.source_path is not None
        assert item.source_path.endswith(failed[item.citation_path])
        source_file = store.root / item.source_path
        assert item.sha256 == hashlib.sha256(source_file.read_bytes()).hexdigest()


# --- Indiana ----------------------------------------------------------------

_IN_OUTCOMES = ["good", "repealed", "maintenance", "empty", "wrong-shape", "no-children"]


def _indiana_title_page(title: int, outcome: str) -> str:
    def heading(kind: str, source_id: str, description: str) -> str:
        return (
            f'<div class="{kind}" id="{source_id}"><span id="ic_number">IC {source_id}</span>'
            f'<span id="shortdescription">{description}</span></div>'
        )

    if outcome in _UNUSABLE:
        return _UNUSABLE[outcome]
    if outcome == "repealed":
        body = heading("title", str(title), f"TITLE {title}. REPEALED")
        body += "<p><i>Repealed by Acts 1982, P.L.127, SEC.2(a).</i></p>"
    elif outcome == "no-children":
        body = heading("title", str(title), f"TITLE {title}. TEST")
    else:
        body = (
            heading("title", str(title), f"TITLE {title}. TEST")
            + heading("article", f"{title}-1", "ARTICLE 1. TEST")
            + heading("chapter", f"{title}-1-1", "Chapter 1. Test")
            + heading("section", f"{title}-1-1-1", "Applicability")
            + "<p>Sec. 1. This chapter applies to every test.</p>"
        )
    return f"<html><body>{body}</body></html>"


@_SETTINGS
@given(outcomes=st.lists(st.sampled_from(_IN_OUTCOMES), min_size=1, max_size=6))
def test_indiana_title_failures_keep_coverage_incomplete(outcomes):
    titles = dict(enumerate(outcomes, start=1))
    pages = {f"{title}.html": _indiana_title_page(title, o) for title, o in titles.items()}
    expected: set[str] = set()
    failed: dict[str, str] = {}
    for title, outcome in titles.items():
        path = f"us-in/statute/{title}"
        expected.add(path)
        if outcome == "good":
            expected |= {f"{path}-1", f"{path}-1-1", f"{path}-1-1-1"}
        elif outcome != "repealed":
            failed[path] = f"{INDIANA_CODE_SOURCE_FORMAT}/2025_Indiana_Code_HTML/{title}.html"
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_sources(root / "source", pages)
        zip_path = root / "2025-Indiana-Code-html.zip"
        with zipfile.ZipFile(zip_path, "w") as archive:
            for name, html in pages.items():
                archive.writestr(f"2025-Indiana-Code-html/2025_Indiana_Code_HTML/{name}", html)
        inputs = {"source_dir": root / "source", "source_zip": zip_path}
        if len(failed) == len(titles):
            # Intended: a run that writes no provision at all fails outright.
            for name, value in inputs.items():
                with pytest.raises(ValueError, match="no Indiana Code provisions extracted"):
                    extract_indiana_code(
                        CorpusArtifactStore(root / f"corpus-{name}"),
                        version=VERSION,
                        **{name: value},
                    )
            return
        runs = {}
        for name, value in inputs.items():
            store = CorpusArtifactStore(root / f"corpus-{name}")
            runs[name] = (store, extract_indiana_code(store, version=VERSION, **{name: value}))
        # Differential: the source directory and the Code ZIP write the same artifacts.
        assert _artifacts(runs["source_dir"][1]) == _artifacts(runs["source_zip"][1])
        _assert_gaps(*runs["source_dir"], expected=expected, failed=failed)


# --- Oregon -----------------------------------------------------------------

_OR_OUTCOMES = [
    "good",
    "former",
    "missing-file",
    "maintenance",
    "empty",
    "wrong-shape",
    "no-children",
]
_OR_LANDING_PAGE = f"{OREGON_ORS_SOURCE_FORMAT}/ORS.aspx"


def _oregon_chapter_page(chapter: int, outcome: str) -> str:
    if outcome in _UNUSABLE:
        return _UNUSABLE[outcome]
    if outcome == "former":
        lines = [f"Chapter {chapter} (Former Provisions)", "Test", f"Note: {chapter}.010 repealed."]
    elif outcome == "no-children":
        lines = [f"Chapter {chapter} — Test Chapter", "2025 EDITION"]
    else:
        lines = [
            f"Chapter {chapter} — Test Chapter",
            "2025 EDITION",
            f"{chapter}.010     Definitions",
            f"{chapter}.010 Definitions. As used in this chapter, words mean what they say.",
        ]
    return "<html><body>" + "".join(f"<p>{line}</p>" for line in lines) + "</body></html>"


@_SETTINGS
@given(outcomes=st.lists(st.sampled_from(_OR_OUTCOMES), min_size=1, max_size=6))
def test_oregon_chapter_failures_keep_coverage_incomplete(outcomes):
    # Chapters 90 on lie inside the landing page's title 10 range (90-105).
    chapters = {90 + index: outcome for index, outcome in enumerate(outcomes)}
    pages = {"ORS.aspx": OR_LANDING}
    pages |= {f"ors{c:03d}.html": _oregon_chapter_page(c, o) for c, o in chapters.items()}
    expected: set[str] = set()
    failed: dict[str, str] = {}
    for chapter, outcome in chapters.items():
        path = f"us-or/statute/chapter-{chapter:03d}"
        expected.add(path)
        if outcome == "good":
            expected.add(f"us-or/statute/{chapter}.010")
        elif outcome == "missing-file":
            failed[path] = _OR_LANDING_PAGE
        elif outcome != "former":
            failed[path] = f"{OREGON_ORS_SOURCE_FORMAT}/ors{chapter:03d}.html"
    if len(failed) < len(chapters):
        expected.add("us-or/statute/title-10")
    with TemporaryDirectory() as tmp, pytest.MonkeyPatch.context() as patch:
        root = Path(tmp)
        fetches: dict[str, int] = {}

        def fake_download(url: str) -> bytes:
            name = url.rsplit("/", 1)[1]
            fetches[name] = fetches.get(name, 0) + 1
            if name not in pages:
                raise ValueError(f"failed to fetch Oregon source page {url}: 404 Client Error")
            missing = name != "ORS.aspx" and chapters[int(name[3:6])] == "missing-file"
            if missing and fetches[name] > 1:
                # Discovery saw the chapter; the extraction fetch then fails.
                raise ValueError(f"failed to fetch Oregon source page {url}: 503 Server Error")
            return pages[name].encode()

        patch.setattr(oregon, "_download_oregon_page", fake_download)
        if len(failed) == len(chapters):
            # Intended: a run that writes no provision at all fails outright.
            with pytest.raises(ValueError, match="no Oregon ORS provisions extracted"):
                extract_oregon_ors(CorpusArtifactStore(root / "corpus"), version=VERSION, workers=1)
            return
        runs = []
        for workers in (1, 4):
            fetches.clear()
            store = CorpusArtifactStore(root / f"corpus-{workers}")
            runs.append((store, extract_oregon_ors(store, version=VERSION, workers=workers)))
        # Differential: parallel chapter discovery writes the same artifacts.
        assert _artifacts(runs[0][1]) == _artifacts(runs[1][1])
        _assert_gaps(*runs[0], expected=expected, failed=failed)


# --- South Carolina ---------------------------------------------------------

_SC_TITLE_OUTCOMES = ["good", "missing-file", "maintenance", "empty", "wrong-shape", "no-children"]
_SC_CHAPTER_OUTCOMES = [
    "good",
    "repealed",
    "reserved",
    "missing-file",
    "maintenance",
    "empty",
    "wrong-shape",
    "no-children",
]
_SC_ROOT = SOUTH_CAROLINA_SOURCE_FORMAT


def _sc_pages(titles: dict[int, tuple[str, dict[int, str]]]) -> dict[str, str]:
    master = "".join(
        f'<a href="/code/title{title}.php">Title {title}</a> - Test Title {title}<br />'
        for title in titles
    )
    pages = {f"{_SC_ROOT}/statmast.html": f"<html><body>{master}</body></html>"}
    for title, (title_outcome, chapters) in titles.items():
        title_page = f"{_SC_ROOT}/title-{title}.html"
        if title_outcome == "missing-file":
            continue
        if title_outcome in _UNUSABLE:
            pages[title_page] = _UNUSABLE[title_outcome]
            continue
        if title_outcome == "no-children":
            pages[title_page] = f"<html><body><div>Title {title} - Test Title</div></body></html>"
            continue
        rows = "".join(
            f"<tr><td>CHAPTER {chapter} - TEST CHAPTER {chapter}"
            f"{' [REPEALED]' if outcome == 'repealed' else ''}</td>"
            f'<td><a href="/code/t{title:02d}c{chapter:03d}.php">HTML</a></td></tr>'
            for chapter, outcome in chapters.items()
        )
        pages[title_page] = f"<html><body><table>{rows}</table></body></html>"
        for chapter, outcome in chapters.items():
            if outcome == "missing-file":
                continue
            head = (
                f'<html><body><div style="text-align: center;">CHAPTER {chapter}</div>'
                f'<div style="text-align: center;">Test Chapter {chapter}</div><br />'
            )
            body = {
                "good": f'<span style="font-weight: bold;"> SECTION {title}-{chapter}-10.</span>'
                " Test.<br /><br />Every test applies.<br /><br />HISTORY: 1995 Act No. 76.",
                "repealed": "Editor's Note<br /><br />This Chapter was repealed.",
                "reserved": "(Reserved for Future Use)",
                "no-children": "",
            }
            pages[f"{_SC_ROOT}/title-{title}/chapter-{chapter}.html"] = (
                _UNUSABLE[outcome]
                if outcome in _UNUSABLE
                else head + body[outcome] + "</body></html>"
            )
    return pages


@_SETTINGS
@given(
    plan=st.lists(
        st.tuples(
            st.sampled_from(_SC_TITLE_OUTCOMES),
            st.lists(st.sampled_from(_SC_CHAPTER_OUTCOMES), min_size=1, max_size=4),
        ),
        min_size=1,
        max_size=3,
    )
)
def test_south_carolina_title_and_chapter_failures_keep_coverage_incomplete(plan):
    titles = {
        title: (title_outcome, dict(enumerate(chapter_outcomes, start=1)))
        for title, (title_outcome, chapter_outcomes) in enumerate(plan, start=1)
    }
    expected: set[str] = set()
    failed: dict[str, str] = {}
    for title, (title_outcome, chapters) in titles.items():
        title_path = f"us-sc/statute/title-{title}"
        expected.add(title_path)
        if title_outcome != "good":
            failed[title_path] = (
                f"{_SC_ROOT}/statmast.html"
                if title_outcome == "missing-file"
                else f"{_SC_ROOT}/title-{title}.html"
            )
            continue
        for chapter, outcome in chapters.items():
            chapter_path = f"{title_path}/chapter-{chapter}"
            expected.add(chapter_path)
            if outcome == "good":
                expected.add(f"us-sc/statute/{title}-{chapter}-10")
            elif outcome == "missing-file":
                failed[chapter_path] = f"{_SC_ROOT}/title-{title}.html"
            elif outcome not in ("repealed", "reserved"):
                failed[chapter_path] = f"{_SC_ROOT}/title-{title}/chapter-{chapter}.html"
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_sources(root / "source", _sc_pages(titles))
        store = CorpusArtifactStore(root / "corpus")
        if all(title_outcome != "good" for title_outcome, _chapters in titles.values()):
            # Intended: a run that writes no provision at all fails outright.
            with pytest.raises(ValueError, match="no South Carolina provisions extracted"):
                extract_south_carolina_code(store, version=VERSION, source_dir=root / "source")
            return
        report = extract_south_carolina_code(store, version=VERSION, source_dir=root / "source")
        _assert_gaps(store, report, expected=expected, failed=failed)
