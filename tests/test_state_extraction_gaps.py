"""Every selected statute target is extracted or remains a visible coverage gap."""

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
import requests
from bs4 import BeautifulSoup
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus import states
from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.r2 import build_artifact_report
from axiom_corpus.corpus.release_quality import validate_release
from axiom_corpus.corpus.releases import ReleaseManifest, ReleaseScope
from axiom_corpus.corpus.state_adapters.maine import (
    MAINE_REVISED_STATUTES_INDEX,
    extract_maine_revised_statutes,
)
from axiom_corpus.corpus.state_statute_completion import (
    _best_complete_unpromoted_row,
    _source_first_complete,
)
from axiom_corpus.corpus.states import StateStatuteExtractReport, extract_ohio_revised_code
from tests.test_corpus_maine import (
    SAMPLE_CHAPTER_HTML,
    SAMPLE_SECTION_HTML,
    SAMPLE_TITLE_HTML,
    SAMPLE_TITLE_INDEX_HTML,
)
from tests.test_corpus_states import (
    SAMPLE_OHIO_CHAPTER,
    SAMPLE_OHIO_INDEX,
    SAMPLE_OHIO_TITLE,
)

MAINTENANCE = "<html><body><h1>Scheduled maintenance</h1></body></html>"
MAINE_CONTAINERS = {
    "us-me/statute/title-36",
    "us-me/statute/title-36/part-8",
    "us-me/statute/title-36/chapter-822",
}
OHIO_CONTAINERS = {"us-oh/statute/title-51", "us-oh/statute/chapter-5160"}


def _write_sources(root: Path, sources: dict[str, str]) -> None:
    for relative, html in sources.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")


def _assert_visible_gaps(
    store: CorpusArtifactStore,
    report: StateStatuteExtractReport,
    *,
    expected: set[str],
    missing: set[str],
    gap_source: str,
) -> None:
    inventory = load_source_inventory(report.inventory_path)
    provisions = load_provisions(report.provisions_path)
    inventory_paths = {item.citation_path for item in inventory}
    provision_paths = {record.citation_path for record in provisions}
    assert inventory_paths == expected
    assert provision_paths == expected - missing
    assert len(inventory) == len(inventory_paths)
    assert len(provisions) == len(provision_paths)
    assert len(report.errors) == len(missing)
    assert report.coverage.complete is False
    assert report.coverage.missing_from_provisions == tuple(sorted(missing))
    persisted = json.loads(report.coverage_path.read_text())
    assert persisted["complete"] is False
    assert persisted["missing_from_provisions"] == sorted(missing)
    assert persisted["source_count"] == len(expected)
    assert persisted["provision_count"] == len(expected - missing)
    for item in inventory:
        if item.citation_path in missing:
            assert item.source_path is not None
            assert item.source_path.endswith(gap_source)
            source_path = store.root / item.source_path
            assert source_path.is_file()
            assert item.sha256 == hashlib.sha256(source_path.read_bytes()).hexdigest()

    release = ReleaseManifest(
        name="test-release",
        scopes=(ReleaseScope(report.jurisdiction, "statute", report.coverage.version),),
    )
    validation = validate_release(store.root, release, strict_warnings=True)
    codes = {issue.code for issue in validation.issues}
    assert validation.ok is False
    assert {"coverage_incomplete", "persisted_coverage_incomplete"} <= codes
    assert not {"missing_inventory_source_path", "source_sha256_mismatch"} & codes
    rows = build_artifact_report(store.root, jurisdiction=report.jurisdiction).rows
    assert len(rows) == 1
    assert rows[0].coverage_complete is False
    assert _source_first_complete(rows[0]) is False
    assert _best_complete_unpromoted_row(rows) is None


@pytest.mark.parametrize("failed_section", ["5219-S", "5219-T"])
@pytest.mark.parametrize("failure", ["maintenance", "missing-file"])
def test_maine_mixed_rejected_targets_remain_inventory_gaps(
    tmp_path, failed_section, failure
):
    source = tmp_path / "source"
    pages = {
        MAINE_REVISED_STATUTES_INDEX: SAMPLE_TITLE_INDEX_HTML,
        "36/title36ch0sec0.html": SAMPLE_TITLE_HTML,
        "36/title36ch822sec0.html": SAMPLE_CHAPTER_HTML,
        "36/title36sec5219-S.html": SAMPLE_SECTION_HTML,
        "36/title36sec5219-T.html": SAMPLE_SECTION_HTML.replace("5219-S", "5219-T"),
    }
    failed_path = f"36/title36sec{failed_section}.html"
    if failure == "maintenance":
        pages[failed_path] = MAINTENANCE
    else:
        del pages[failed_path]
    _write_sources(source, pages)
    store = CorpusArtifactStore(tmp_path / "corpus")
    report = extract_maine_revised_statutes(
        store, version="2026-05-09", source_dir=source, only_title="36", workers=1
    )
    assert report.section_count == 1
    assert report.errors
    assert failed_path in report.errors[0]
    _assert_visible_gaps(
        store,
        report,
        expected=MAINE_CONTAINERS | {f"us-me/statute/36/{s}" for s in ("5219-S", "5219-T")},
        missing={f"us-me/statute/36/{failed_section}"},
        gap_source="36/title36ch822sec0.html",
    )


@pytest.mark.parametrize("failed_index", [0, 1])
def test_ohio_mixed_section_without_body_remains_inventory_gap(tmp_path, failed_index):
    source = tmp_path / "source"
    chapter = BeautifulSoup(SAMPLE_OHIO_CHAPTER, "html.parser")
    chapter.select("section.laws-body")[failed_index].decompose()
    _write_sources(
        source,
        {
            "ohio-revised-code/index.html": SAMPLE_OHIO_INDEX,
            "ohio-revised-code/titles/title-51.html": SAMPLE_OHIO_TITLE,
            "ohio-revised-code/chapters/chapter-5160.html": str(chapter),
        },
    )
    store = CorpusArtifactStore(tmp_path / "corpus")
    report = extract_ohio_revised_code(
        store, version="2026-05-09", source_dir=source, only_title="51"
    )
    failed_section = ("5160.01", "5160.011")[failed_index]
    assert report.section_count == 1
    assert report.errors
    assert failed_section in report.errors[0]
    _assert_visible_gaps(
        store,
        report,
        expected=OHIO_CONTAINERS | {"us-oh/statute/5160.01", "us-oh/statute/5160.011"},
        missing={f"us-oh/statute/{failed_section}"},
        gap_source="ohio-revised-code/chapters/chapter-5160.html",
    )


@pytest.mark.parametrize("failure", ["maintenance", "request-error"])
def test_ohio_mixed_rejected_chapters_remain_inventory_gaps(tmp_path, monkeypatch, failure):
    source = tmp_path / "source"
    extra_chapter = '<a href="/ohio-revised-code/chapter-5161">Chapter 5161 | Other law</a>'
    _write_sources(
        source,
        {
            "ohio-revised-code/index.html": SAMPLE_OHIO_INDEX,
            "ohio-revised-code/titles/title-51.html": SAMPLE_OHIO_TITLE.replace(
                "</main>", extra_chapter + "</main>"
            ),
            "ohio-revised-code/chapters/chapter-5160.html": SAMPLE_OHIO_CHAPTER,
            "ohio-revised-code/chapters/chapter-5161.html": MAINTENANCE,
        },
    )
    if failure == "request-error":
        load_html = states._load_ohio_html

        def reject_chapter(*args, **kwargs):
            if kwargs["relative_name"].endswith("chapter-5161.html"):
                raise requests.RequestException("source unavailable")
            return load_html(*args, **kwargs)

        monkeypatch.setattr(states, "_load_ohio_html", reject_chapter)
    store = CorpusArtifactStore(tmp_path / "corpus")
    report = extract_ohio_revised_code(
        store, version="2026-05-09", source_dir=source, only_title="51"
    )
    assert report.section_count == 2
    assert report.errors
    assert "5161" in report.errors[0]
    _assert_visible_gaps(
        store,
        report,
        expected=OHIO_CONTAINERS
        | {"us-oh/statute/chapter-5161", "us-oh/statute/5160.01", "us-oh/statute/5160.011"},
        missing={"us-oh/statute/chapter-5161"},
        gap_source=(
            "ohio-revised-code/titles/title-51.html"
            if failure == "request-error"
            else "ohio-revised-code/chapters/chapter-5161.html"
        ),
    )


@st.composite
def _mixed_targets(draw):
    count = draw(st.integers(min_value=2, max_value=5))
    failures = draw(
        st.sets(st.integers(min_value=0, max_value=count - 1), min_size=1, max_size=count - 1)
    )
    order = draw(st.permutations(tuple(range(count))))
    return order, failures


@settings(
    max_examples=20,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(case=_mixed_targets())
def test_maine_selected_targets_are_extracted_or_covered_as_gaps(tmp_path, case):
    order, failures = case
    with TemporaryDirectory(dir=tmp_path) as directory:
        root = Path(directory)
        pages = {
            MAINE_REVISED_STATUTES_INDEX: SAMPLE_TITLE_INDEX_HTML,
            "36/title36ch0sec0.html": SAMPLE_TITLE_HTML,
        }
        links = []
        for index in order:
            section = f"5219-{chr(65 + index)}"
            links.append(
                '<div class="MRSSection_toclist">'
                f'<a href="./title36sec{section}.html">36 §{section}. Credit</a></div>'
            )
            pages[f"36/title36sec{section}.html"] = (
                MAINTENANCE
                if index in failures
                else SAMPLE_SECTION_HTML.replace("5219-S", section)
            )
        pages["36/title36ch822sec0.html"] = "<html><body>" + "".join(links) + "</body></html>"
        _write_sources(root / "source", pages)
        store = CorpusArtifactStore(root / "corpus")
        report = extract_maine_revised_statutes(
            store, version="2026-05-09", source_dir=root / "source", only_title="36", workers=1
        )
        assert report.section_count == len(order) - len(failures)
        _assert_visible_gaps(
            store,
            report,
            expected=MAINE_CONTAINERS | {f"us-me/statute/36/5219-{chr(65 + i)}" for i in order},
            missing={f"us-me/statute/36/5219-{chr(65 + i)}" for i in failures},
            gap_source="36/title36ch822sec0.html",
        )


@settings(
    max_examples=20,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(case=_mixed_targets())
def test_ohio_selected_targets_are_extracted_or_covered_as_gaps(tmp_path, case):
    order, failures = case
    with TemporaryDirectory(dir=tmp_path) as directory:
        root = Path(directory)
        sections = []
        for index in order:
            section = f"5160.{index + 1:02}"
            content = BeautifulSoup(SAMPLE_OHIO_CHAPTER, "html.parser").select(
                "div.list-content"
            )[0]
            if index in failures:
                content.select_one("section.laws-body").decompose()
            sections.append(str(content).replace("5160.01", section))
        _write_sources(
            root / "source",
            {
                "ohio-revised-code/index.html": SAMPLE_OHIO_INDEX,
                "ohio-revised-code/titles/title-51.html": SAMPLE_OHIO_TITLE,
                "ohio-revised-code/chapters/chapter-5160.html": "".join(sections),
            },
        )
        store = CorpusArtifactStore(root / "corpus")
        report = extract_ohio_revised_code(
            store, version="2026-05-09", source_dir=root / "source", only_title="51"
        )
        assert report.section_count == len(order) - len(failures)
        _assert_visible_gaps(
            store,
            report,
            expected=OHIO_CONTAINERS | {f"us-oh/statute/5160.{i + 1:02}" for i in order},
            missing={f"us-oh/statute/5160.{i + 1:02}" for i in failures},
            gap_source="ohio-revised-code/chapters/chapter-5160.html",
        )
