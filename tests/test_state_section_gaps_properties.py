"""Section failures leave coverage incomplete for every mix of failures.

For any set of sections and any assignment of failures to them, the run keeps
every listed section in the inventory, writes a provision only for the sections
it could read, logs one error per lost section, and reads complete exactly when
nothing failed. Every gap points at a file the run wrote, with a matching hash:
the listing when the page could not be fetched, otherwise the page itself. The
run writes the same artifacts whether one worker or several fetch the pages. A
run in which every section fails still raises, as it did before.
"""

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.state_adapters.maryland import extract_maryland_code
from tests.test_corpus_maryland import SAMPLE_SECTION_HTML as MD_SECTION_HTML
from tests.test_state_extraction_gaps import MAINTENANCE, _write_sources

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
