"""Section failures leave coverage incomplete for every mix of failures.

For any set of sections and any assignment of failures to them, the run keeps
every listed section in the inventory, writes a provision only for the sections
it could read, logs one error per lost section, and reads complete exactly when
nothing failed. Every gap points at a file the run wrote, with a matching hash:
the listing when the page could not be fetched, otherwise the page itself. The
run writes the same artifacts whether one worker or several fetch the pages. A
Maryland run in which every section fails, and an Illinois run that fetches no
section document, still raise, as they did before.

Arizona, Illinois and New York runs keep these properties when a fetched page
names no section: a maintenance, empty or wrong-shape page, or in New York a
page for another node behind a "SECTION ..." link. A section whose page names
it but holds no text, or marks it repealed, is still written. The Arizona and
Illinois parsers read a page exactly when it names a section.
"""

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from hypothesis import HealthCheck, example, given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.state_adapters import illinois
from axiom_corpus.corpus.state_adapters.arizona import (
    ARIZONA_SECTION_SOURCE_FORMAT,
    ARIZONA_TITLE_DETAIL_SOURCE_FORMAT,
    ARIZONA_TITLE_INDEX_SOURCE_FORMAT,
    extract_arizona_revised_statutes,
    parse_arizona_section,
)
from axiom_corpus.corpus.state_adapters.illinois import (
    ILLINOIS_ILCS_BASE_URL,
    ILLINOIS_ILCS_FULLTEXT_URL,
    extract_illinois_ilcs,
    parse_illinois_ilcs_doc_name,
    parse_illinois_ilcs_section,
)
from axiom_corpus.corpus.state_adapters.maryland import extract_maryland_code
from axiom_corpus.corpus.state_adapters.new_york import extract_new_york_consolidated_laws
from tests.test_corpus_arizona import SAMPLE_EMPTY_SECTION_HTML as AZ_EMPTY_SECTION_HTML
from tests.test_corpus_arizona import SAMPLE_SECTION_HTML as AZ_SECTION_HTML
from tests.test_corpus_arizona import SAMPLE_TITLE_DETAIL_HTML as AZ_TITLE_DETAIL_HTML
from tests.test_corpus_arizona import SAMPLE_TITLE_INDEX_HTML as AZ_TITLE_INDEX_HTML
from tests.test_corpus_maryland import SAMPLE_SECTION_HTML as MD_SECTION_HTML
from tests.test_corpus_new_york import SAMPLE_ARTICLE as NY_ARTICLE_HTML
from tests.test_corpus_new_york import SAMPLE_EMPTY_SECTION_602 as NY_EMPTY_SECTION_602
from tests.test_corpus_new_york import SAMPLE_INDEX as NY_INDEX_HTML
from tests.test_corpus_new_york import SAMPLE_PART as NY_PART_HTML
from tests.test_corpus_new_york import SAMPLE_SECTION_602 as NY_SECTION_602_HTML
from tests.test_corpus_new_york import SAMPLE_TAX as NY_TAX_HTML
from tests.test_state_extraction_gaps import MAINTENANCE, _write_sources
from tests.test_state_section_gaps import _IllinoisRemote

_PAGES = {
    "good": None,
    "maintenance": MAINTENANCE,
    "empty": "",
    "wrong-shape": "<html><body><main><h1>Search results</h1></main></body></html>",
}
_SECTION_LIST = "maryland-code-json/sections/gag.json"
_CONTAINERS = {"us-md/statute/gag", "us-md/statute/gag/title-1"}


def _maryland_pages(outcomes: list[str]) -> dict[str, str]:
    sections = [
        {"DisplayText": f"1-1{index:02d}", "Value": str(100 * index)}
        for index in range(1, len(outcomes) + 1)
    ]
    pages = {
        "maryland-code-json/articles.json": json.dumps(
            [{"DisplayText": "Agriculture - (gag)", "Value": "gag"}]
        ),
        _SECTION_LIST: json.dumps(sections),
    }
    for index, outcome in enumerate(outcomes, start=1):
        if outcome == "missing-file":
            continue
        page = _PAGES[outcome]
        if page is None:
            page = MD_SECTION_HTML.replace("1&ndash;101", f"1&ndash;1{index:02d}")
        pages[f"maryland-code-html/gag/1-1{index:02d}.html"] = page
    return pages


def _artifacts(report) -> tuple[str, str, str]:
    return (
        report.inventory_path.read_text(),
        report.provisions_path.read_text(),
        report.coverage_path.read_text(),
    )


@settings(
    max_examples=40,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
@given(
    outcomes=st.lists(
        st.sampled_from(["good", "missing-file", "maintenance", "empty", "wrong-shape"]),
        min_size=1,
        max_size=6,
    )
)
def test_maryland_section_failures_keep_coverage_incomplete(outcomes):
    sections = {f"us-md/statute/gag/1-1{i:02d}": o for i, o in enumerate(outcomes, start=1)}
    failed = {path for path, outcome in sections.items() if outcome != "good"}
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_sources(root / "source", _maryland_pages(outcomes))
        if failed == set(sections):
            # Intended: a run that reads no section still fails outright.
            with pytest.raises(ValueError, match="no Maryland sections extracted"):
                extract_maryland_code(
                    CorpusArtifactStore(root / "corpus"),
                    version="2026-05-09",
                    source_dir=root / "source",
                    workers=1,
                )
            return
        runs = []
        for workers in (1, 3):
            store = CorpusArtifactStore(root / f"corpus-{workers}")
            report = extract_maryland_code(
                store, version="2026-05-09", source_dir=root / "source", workers=workers
            )
            runs.append((store, report))

        # Differential: the parallel fetch path writes the same artifacts.
        assert _artifacts(runs[0][1]) == _artifacts(runs[1][1])
        store, report = runs[0]
        inventory = load_source_inventory(report.inventory_path)
        provisions = load_provisions(report.provisions_path)
        assert {item.citation_path for item in inventory} == _CONTAINERS | set(sections)
        assert {record.citation_path for record in provisions} == (
            _CONTAINERS | set(sections)
        ) - failed
        assert len(report.errors) == len(failed)
        assert report.coverage.complete is (not failed)
        assert set(report.coverage.missing_from_provisions) == failed
        assert json.loads(report.coverage_path.read_text())["complete"] is (not failed)
        for item in inventory:
            if item.citation_path not in failed:
                continue
            outcome = sections[item.citation_path]
            expected_source = (
                _SECTION_LIST
                if outcome == "missing-file"
                else f"maryland-code-html/gag/{item.citation_path.rsplit('/', 1)[1]}.html"
            )
            assert item.source_path is not None
            assert item.source_path.endswith(expected_source)
            source_file = store.root / item.source_path
            assert item.sha256 == hashlib.sha256(source_file.read_bytes()).hexdigest()


# --- Arizona, Illinois and New York: pages that name no section ---

_JUNK = {
    "maintenance": MAINTENANCE,
    "empty": "",
    "wrong-shape": "<html><body><main><h1>Search results</h1></main></body></html>",
}
# Outcomes a run must still write as a section, so coverage stays complete.
_WRITTEN = {"good", "no-text", "repealed"}


def _run_twice(extract, root: Path, workers: int):
    """Run ``extract`` with one worker and with ``workers``; return both reports."""
    reports = []
    for count in (1, workers):
        store = CorpusArtifactStore(root / f"corpus-{count}")
        reports.append((store, extract(store, count)))
    # Differential: the parallel fetch path writes the same artifacts.
    assert _artifacts(reports[0][1]) == _artifacts(reports[1][1])
    return reports[0]


def _assert_gaps(store, report, *, containers, sections, gap_sources) -> None:
    """Every section is inventoried; only written outcomes have provisions."""
    failed = {path for path, outcome in sections.items() if outcome not in _WRITTEN}
    inventory = load_source_inventory(report.inventory_path)
    provisions = load_provisions(report.provisions_path)
    assert {item.citation_path for item in inventory} == containers | set(sections)
    assert len(inventory) == len(containers) + len(sections)
    assert {record.citation_path for record in provisions} == (containers | set(sections)) - failed
    assert len(report.errors) == len(failed)
    assert report.coverage.complete is (not failed)
    assert set(report.coverage.missing_from_provisions) == failed
    assert json.loads(report.coverage_path.read_text())["complete"] is (not failed)
    for item in inventory:
        if item.citation_path not in failed:
            continue
        assert item.source_path is not None
        assert item.source_path.endswith(gap_sources[item.citation_path])
        source_file = store.root / item.source_path
        assert item.sha256 == hashlib.sha256(source_file.read_bytes()).hexdigest()


_AZ_ROW = """        <ul>
          <li class="colleft">
            <a class="stat" href="/viewdocument/?docName=https://www.azleg.gov/ars/1/002{index:02d}.htm">1-2{index:02d}</a>
          </li>
          <li class="colright">Heading {index}</li>
        </ul>
"""
_AZ_DETAIL = f"{ARIZONA_TITLE_DETAIL_SOURCE_FORMAT}/title-1.html"
_AZ_CONTAINERS = {
    "us-az/statute/title-1",
    "us-az/statute/title-1/chapter-2",
    "us-az/statute/title-1/chapter-2/article-1",
}


def _arizona_pages(outcomes: list[str]) -> dict[str, str]:
    rows = "".join(_AZ_ROW.format(index=index) for index in range(2, len(outcomes) + 1))
    pages = {
        f"{ARIZONA_TITLE_INDEX_SOURCE_FORMAT}/index.html": AZ_TITLE_INDEX_HTML,
        _AZ_DETAIL: AZ_TITLE_DETAIL_HTML.replace(
            "      </div>\n    </div>", rows + "      </div>\n    </div>", 1
        ),
    }
    for index, outcome in enumerate(outcomes, start=1):
        if outcome == "missing-file":
            continue
        section = f"1-2{index:02d}"
        page = {
            "good": AZ_SECTION_HTML.replace("1-201", section),
            "no-text": AZ_EMPTY_SECTION_HTML.replace("1-201", section),
        }.get(outcome) or _JUNK[outcome]
        pages[f"{ARIZONA_SECTION_SOURCE_FORMAT}/title-1/{section}.html"] = page
    return pages


@settings(
    max_examples=40,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(
    outcomes=st.lists(
        st.sampled_from(["good", "no-text", "missing-file", *_JUNK]),
        min_size=1,
        max_size=6,
    )
)
def test_arizona_section_failures_keep_coverage_incomplete(outcomes):
    sections = {f"us-az/statute/1-2{i:02d}": o for i, o in enumerate(outcomes, start=1)}
    gap_sources = {
        path: _AZ_DETAIL
        if outcome == "missing-file"
        else f"{ARIZONA_SECTION_SOURCE_FORMAT}/title-1/{path.rsplit('/', 1)[1]}.html"
        for path, outcome in sections.items()
    }
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_sources(root / "source", _arizona_pages(outcomes))
        store, report = _run_twice(
            lambda store, workers: extract_arizona_revised_statutes(
                store,
                version="2026-05-09",
                source_dir=root / "source",
                only_title="1",
                workers=workers,
            ),
            root,
            workers=3,
        )
        _assert_gaps(
            store, report, containers=_AZ_CONTAINERS, sections=sections, gap_sources=gap_sources
        )


_IL_ACT_DIR = "Ch 0005/Act 0070"
_IL_CONTAINERS = {"us-il/statute/5", "us-il/statute/5/70"}


def _illinois_pages(outcomes: list[str]) -> dict[str, str]:
    links = "".join(
        f'<a href="/ftp/ILCS/Ch%200005/Act%200070/000500700K{index}.html">Sec. {index}</a>\n'
        for index in range(1, len(outcomes) + 1)
    )
    pages = {ILLINOIS_ILCS_BASE_URL: links}
    for index, outcome in enumerate(outcomes, start=1):
        if outcome == "missing-file":
            continue
        text = {
            "good": f"<p>Sec. {index}. Heading {index}.</p><p>Text of Section {index}.</p>",
            "repealed": f"<p>Sec. {index}.</p><p>(Repealed).</p>",
        }.get(outcome)
        page = (
            f"<html><body><p>(5 ILCS 70/{index}) (from Ch. 1, par. 10{index:02d})</p>"
            f"{text}</body></html>"
            if text is not None
            else _JUNK[outcome]
        )
        pages[f"{ILLINOIS_ILCS_FULLTEXT_URL}?DocName=000500700K{index}"] = page
    return pages


@settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    outcomes=st.lists(
        st.sampled_from(["good", "repealed", "missing-file", *_JUNK]),
        min_size=1,
        max_size=6,
    )
)
def test_illinois_section_failures_keep_coverage_incomplete(outcomes):
    sections = {f"us-il/statute/5/70/{i}": o for i, o in enumerate(outcomes, start=1)}
    gap_sources = {
        path: "illinois-ilcs/index.html"
        if outcome == "missing-file"
        else f"illinois-ilcs/{_IL_ACT_DIR}/000500700K{path.rsplit('/', 1)[1]}.html"
        for path, outcome in sections.items()
    }
    remote = _IllinoisRemote(_illinois_pages(outcomes))

    def extract(store, workers):
        return extract_illinois_ilcs(
            store, version="2026-05-01", only_chapter=5, only_act=70, workers=workers
        )

    with TemporaryDirectory() as tmp, pytest.MonkeyPatch.context() as patch:
        patch.setattr(illinois.requests, "Session", lambda: remote)
        patch.setattr(illinois.requests, "get", remote.get)
        root = Path(tmp)
        if set(outcomes) == {"missing-file"}:
            # Intended: a run that fetches no section document still fails
            # outright. One that fetches only unreadable pages writes the
            # chapter and act from them, so it does not.
            with pytest.raises(ValueError, match="no Illinois ILCS provisions extracted"):
                extract(CorpusArtifactStore(root / "corpus"), 1)
            return
        store, report = _run_twice(extract, root, workers=4)
        _assert_gaps(
            store, report, containers=_IL_CONTAINERS, sections=sections, gap_sources=gap_sources
        )


_NY_PART = "TAX/A22P1.html"
_NY_CONTAINERS = {"us-ny/statute/TAX", "us-ny/statute/TAX/A22", "us-ny/statute/TAX/A22P1"}


def _new_york_pages(outcomes: list[str]) -> dict[str, str]:
    links = "".join(
        '<a class="nys-openleg-result-item-link" '
        f'href="https://www.nysenate.gov/legislation/laws/TAX/60{index}">'
        f"SECTION 60{index} Heading {index}</a>\n"
        for index in range(1, len(outcomes) + 1)
    )
    pages = {
        "CONSOLIDATED.html": NY_INDEX_HTML,
        "TAX/index.html": NY_TAX_HTML,
        "TAX/A22.html": NY_ARTICLE_HTML,
        _NY_PART: NY_PART_HTML.split('<div class="nys-openleg-items-container">', 1)[0]
        + f'<div class="nys-openleg-items-container">{links}</div></body></html>',
    }
    for index, outcome in enumerate(outcomes, start=1):
        if outcome == "missing-file":
            continue
        page = {
            "good": NY_SECTION_602_HTML.replace("602", f"60{index}"),
            "no-text": NY_EMPTY_SECTION_602.replace("602", f"60{index}"),
            # A page for another node, here the article that holds the part.
            "other-node": NY_ARTICLE_HTML,
        }.get(outcome) or _JUNK[outcome]
        pages[f"TAX/60{index}.html"] = page
    return pages


@settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    outcomes=st.lists(
        st.sampled_from(["good", "no-text", "missing-file", "other-node", *_JUNK]),
        min_size=1,
        max_size=6,
    )
)
def test_new_york_section_failures_keep_coverage_incomplete(outcomes):
    sections = {f"us-ny/statute/TAX/60{i}": o for i, o in enumerate(outcomes, start=1)}
    gap_sources = {
        path: f"new-york-senate-html/{_NY_PART}"
        if outcome == "missing-file"
        else f"new-york-senate-html/TAX/{path.rsplit('/', 1)[1]}.html"
        for path, outcome in sections.items()
    }
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_sources(root / "source" / "new-york-senate-html", _new_york_pages(outcomes))
        store, report = _run_twice(
            lambda store, workers: extract_new_york_consolidated_laws(
                store,
                version="2026-test",
                source_dir=root / "source",
                only_title="TAX",
                workers=workers,
                source_as_of="2026-01-30",
                expression_date="2026-01-30",
            ),
            root,
            workers=4,
        )
        _assert_gaps(
            store, report, containers=_NY_CONTAINERS, sections=sections, gap_sources=gap_sources
        )


# Words with no digits, so generated text never names a section by accident.
_WORDS = st.text(alphabet="abcdefghij klmnopqrstuvwxyz", max_size=24)


@settings(max_examples=100, deadline=None)
@given(
    section=st.from_regex(r"[1-9][0-9]?-[1-9][0-9]{2,3}(\.[0-9]{1,2})?", fullmatch=True),
    heading=_WORDS,
    paragraphs=st.lists(_WORDS, max_size=3),
    named_in=st.sampled_from(["title", "paragraph", "both", "neither"]),
)
# A title with an empty heading cleans to "1-100 -" (found by this test).
@example(section="1-100", heading="", paragraphs=[], named_in="title")
def test_arizona_page_reads_exactly_when_it_names_a_section(section, heading, paragraphs, named_in):
    title = f"{section} - {heading}" if named_in in {"title", "both"} else heading
    first = f"<p>{section}. <u>{heading}</u></p>" if named_in in {"paragraph", "both"} else ""
    rest = "".join(f"<p>{paragraph}</p>" for paragraph in paragraphs)
    html = f"<html><head><title>{title}</title></head><body>{first}{rest}</body></html>"
    if named_in == "neither":
        with pytest.raises(ValueError, match="no section number"):
            parse_arizona_section(html)
    else:
        parse_arizona_section(html)


@settings(max_examples=100, deadline=None)
@given(
    expected=st.from_regex(r"[1-9][0-9]{0,2}(-[0-9]{1,3})?(\.[0-9]{1,2})?[a-c]?", fullmatch=True),
    named=st.from_regex(r"[1-9][0-9]{0,2}(-[0-9]{1,3})?(\.[0-9]{1,2})?[a-c]?", fullmatch=True),
    heading=_WORDS,
    text=_WORDS,
)
def test_illinois_uncited_page_reads_exactly_when_it_names_its_own_section(
    expected, named, heading, text
):
    # A page without an ILCS citation reads under its document's section only
    # when a line opens with that section's heading, never another's.
    document = parse_illinois_ilcs_doc_name(f"000500700K{expected}.html")
    html = f"<html><body><p>Sec. {named}. {heading}</p><p>{text}</p></body></html>"
    if named == expected:
        section = parse_illinois_ilcs_section(html, document=document)
        assert section.citation_path == document.citation_path
    else:
        with pytest.raises(ValueError, match="names no section"):
            parse_illinois_ilcs_section(html, document=document)
