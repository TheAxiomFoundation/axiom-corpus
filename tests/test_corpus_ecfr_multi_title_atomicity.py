"""A rejected title must not commit another title's replacement source bytes."""

import json
import tempfile
from hashlib import sha256
from pathlib import Path
from threading import Event

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import axiom_corpus.corpus.ecfr as ecfr
from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.io import load_provisions, load_source_inventory

VERSION = "multi-title-review"
AS_OF = "2026-10-08"


@pytest.fixture(autouse=True)
def _isolate_synthetic_corpus(tmp_path, monkeypatch):
    # These synthetic artifacts have no repository locks. Keep missing-file
    # resolution in their temporary directory, as in the single-title tests.
    monkeypatch.chdir(tmp_path)


def _structure(title):
    part = title * 10
    return {
        "type": "title",
        "identifier": str(title),
        "label": f"Title {title}",
        "children": [
            {
                "type": "part",
                "identifier": str(part),
                "label": f"Part {part}",
                "children": [
                    {
                        "type": "section",
                        "identifier": f"{part}.1",
                        "label": "Section one",
                    }
                ],
            }
        ],
    }


def _xml(title, body, *, duplicate=False):
    part = title * 10
    section = (
        f'<DIV8 N="{part}.1" TYPE="SECTION" NODE="selected-{title}">'
        f"<HEAD>Section one</HEAD><P>{body}</P></DIV8>"
    )
    if duplicate:
        # Distinct publisher identifiers fold to the same selected citation path.
        section += (
            f'<DIV8 N="{part - 1}-{part}.1" TYPE="SECTION" NODE="other-{title}">'
            "<HEAD>Other section</HEAD><P>Conflicting body.</P></DIV8>"
        )
    return f'<ECFR><DIV5 N="{part}" TYPE="PART"><HEAD>Part {part}</HEAD>{section}</DIV5></ECFR>'


def _snapshot(root):
    return {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def _extract(store, *, workers=1, graphic_transcriptions=None):
    return ecfr.extract_ecfr(
        store,
        version=VERSION,
        as_of=AS_OF,
        workers=workers,
        graphic_transcriptions=graphic_transcriptions,
    )


def _patch_sources(monkeypatch, titles):
    xml_by_title = {title: _xml(title, f"Saved title {title} body.") for title in titles}
    fetched = []

    def fetch(title, as_of):
        fetched.append(title)
        return xml_by_title[title]

    monkeypatch.setattr(ecfr, "DEFAULT_CFR_TITLES", titles)
    monkeypatch.setattr(ecfr, "fetch_ecfr_structure", lambda title, as_of: _structure(title))
    monkeypatch.setattr(ecfr, "fetch_ecfr_title_xml", fetch)
    return xml_by_title, fetched


def _source_paths(store, titles):
    return {
        title: store.source_path("us", "regulation", VERSION, f"ecfr/title-{title}.xml")
        for title in titles
    }


def _assert_supported_sources(store, expected_bodies):
    """Compare literal test bodies and source digests, without production selectors."""
    inventory = {
        item.citation_path: item
        for item in load_source_inventory(store.inventory_path("us", "regulation", VERSION))
    }
    records = {
        record.citation_path: record
        for record in load_provisions(store.provisions_path("us", "regulation", VERSION))
        if record.kind == "section"
    }
    assert set(records) == {f"us/regulation/{title}/{title * 10}/1" for title in expected_bodies}
    for title, body in expected_bodies.items():
        path = f"us/regulation/{title}/{title * 10}/1"
        item = inventory[path]
        assert item.source_path is not None
        source_bytes = (store.root / item.source_path).read_bytes()
        assert item.sha256 == sha256(source_bytes).hexdigest()
        assert records[path].body == body
        assert body.encode() in source_bytes


def _unused_transcriptions(root):
    # The supported manifest loader accepts entries unused by this run; any
    # nonempty manifest requests the same complete-cache refresh as the CLI.
    manifest = root / "unused-transcriptions.json"
    manifest.write_text(
        json.dumps(
            {
                "graphics": {"ER07OC94.022": {"sha256": "a" * 64, "text": "Unused formula"}},
            }
        )
    )
    return ecfr.load_ecfr_graphic_transcriptions(manifest)


def _gate_failing_titles(monkeypatch, valid_titles, failing_titles):
    """Make every valid task finish first, including with multiple worker threads."""
    completed = {title: Event() for title in valid_titles}
    original = ecfr._extract_one_title

    def extract_one_title(*args, **kwargs):
        title = args[1]
        if title in failing_titles:
            for event in completed.values():
                assert event.wait(5), "a valid title did not finish before the failure"
        result = original(*args, **kwargs)
        if title in completed:
            completed[title].set()
        return result

    monkeypatch.setattr(ecfr, "_extract_one_title", extract_one_title)


def _assert_failed_refresh_and_resume(
    root,
    monkeypatch,
    titles,
    failing_titles,
    workers,
    *,
    kept_titles=frozenset(),
):
    # Schedule valid titles first so a single worker exercises the same ordering
    # as the explicit event gate used with several workers.
    ordered_titles = tuple(title for title in titles if title not in failing_titles) + tuple(
        title for title in titles if title in failing_titles
    )
    xml_by_title, fetched = _patch_sources(monkeypatch, ordered_titles)
    store = CorpusArtifactStore(root / "corpus")
    initial = _extract(store, workers=workers)
    assert initial.coverage.complete and initial.title_error_count == 0
    _assert_supported_sources(store, {title: f"Saved title {title} body." for title in titles})
    for title, path in _source_paths(store, titles).items():
        if title not in kept_titles:
            path.unlink()
    before = _snapshot(store.root)
    replacement_bodies = {title: f"Replacement title {title} body." for title in titles}
    for title in titles:
        xml_by_title[title] = _xml(
            title,
            replacement_bodies[title],
            duplicate=title in failing_titles,
        )
    transcriptions = _unused_transcriptions(root)
    fetched.clear()
    with monkeypatch.context() as patch:
        _gate_failing_titles(
            patch,
            set(titles) - failing_titles,
            failing_titles,
        )
        if failing_titles:
            with pytest.raises(ValueError, match="twice"):
                _extract(store, workers=workers, graphic_transcriptions=transcriptions)
            # A fatal identity error rolls back the whole run, including source
            # writes by a different title whose validation already succeeded.
            assert _snapshot(store.root) == before
            # An ordinary resume sees the same ambiguous replacement inputs.
            # Complete cached rows must not hide them or certify stale text.
            with pytest.raises(ValueError, match="twice"):
                _extract(store, workers=workers)
            assert _snapshot(store.root) == before
        else:
            report = _extract(store, workers=workers, graphic_transcriptions=transcriptions)
            assert report.coverage.complete and report.title_error_count == 0

    # Remove the ambiguity and resume normally, with no transcription request.
    # Complete cached rows cannot hide missing sources or certify stale bodies.
    for title in titles:
        xml_by_title[title] = _xml(title, replacement_bodies[title])
    resumed = _extract(store, workers=workers)
    assert resumed.coverage.complete and resumed.title_error_count == 0
    expected_bodies = {
        title: f"Saved title {title} body." if title in kept_titles else replacement_bodies[title]
        for title in titles
    }
    _assert_supported_sources(store, expected_bodies)


@pytest.mark.parametrize("workers", [1, 2])
def test_later_title_duplicate_preserves_all_artifacts_then_ordinary_resume_reparses(
    tmp_path,
    monkeypatch,
    workers,
):
    _assert_failed_refresh_and_resume(tmp_path, monkeypatch, (1, 2), {2}, workers)


@pytest.mark.parametrize("workers", [1, 2])
def test_later_title_duplicate_preserves_other_titles_new_graphic_and_source(
    tmp_path,
    monkeypatch,
    workers,
):
    xml_by_title, _ = _patch_sources(monkeypatch, (1, 2))
    store = CorpusArtifactStore(tmp_path / "corpus")
    initial = _extract(store, workers=workers)
    assert initial.coverage.complete and initial.title_error_count == 0
    for path in _source_paths(store, (1, 2)).values():
        path.unlink()
    before = _snapshot(store.root)
    xml_by_title[1] = _xml(1, "Replacement title 1 body.").replace(
        "</P>",
        '</P><MATH><IMG src="/graphics/er07oc94.023.gif"/></MATH>',
    )
    xml_by_title[2] = _xml(2, "Replacement title 2 body.", duplicate=True)
    fetched_graphics = []

    def fetch_graphic(identifier):
        fetched_graphics.append(identifier)
        return b"\x89PNG\r\n\x1a\nvalid graphic fixture"

    monkeypatch.setattr(ecfr, "fetch_ecfr_graphic", fetch_graphic)
    _gate_failing_titles(monkeypatch, {1}, {2})

    with pytest.raises(ValueError, match="twice"):
        _extract(
            store,
            workers=workers,
            graphic_transcriptions=_unused_transcriptions(tmp_path),
        )

    assert fetched_graphics == ["ER07OC94.023"]
    assert _snapshot(store.root) == before


@settings(
    max_examples=32,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    failures=st.lists(st.booleans(), min_size=2, max_size=4),
    workers=st.sampled_from([1, 2]),
    keep_sources=st.sets(st.integers(min_value=1, max_value=4), max_size=4),
)
def test_property_any_failed_title_preserves_sources_and_resumed_text_is_supported(
    tmp_path,
    monkeypatch,
    failures,
    workers,
    keep_sources,
):
    """Independent oracle: literal bodies occur in bytes matching inventory hashes.

    Every subset of titles may fail, including none and all. A failed refresh
    preserves every artifact; a normal retry must establish coherent provenance.
    """
    titles = tuple(range(1, len(failures) + 1))
    failing_titles = {title for title, fails in zip(titles, failures, strict=True) if fails}
    # Failed titles need refetching to encounter their malformed replacement.
    # Other titles independently retain or remove their source snapshots.
    kept_titles = (set(titles) & keep_sources) - failing_titles
    with tempfile.TemporaryDirectory(dir=tmp_path) as tmp, monkeypatch.context() as patch:
        _assert_failed_refresh_and_resume(
            Path(tmp),
            patch,
            titles,
            failing_titles,
            workers,
            kept_titles=kept_titles,
        )


@pytest.mark.parametrize("workers", [1, 2])
@pytest.mark.parametrize("source_state", ["missing", "changed"])
def test_ordinary_resume_reextracts_complete_title_with_unpinned_source(
    tmp_path,
    monkeypatch,
    workers,
    source_state,
):
    titles = (1, 2)
    xml_by_title, fetched = _patch_sources(monkeypatch, titles)
    store = CorpusArtifactStore(tmp_path / "corpus")
    initial = _extract(store, workers=workers)
    assert initial.coverage.complete and initial.title_error_count == 0
    source_path = _source_paths(store, titles)[1]
    xml_by_title[1] = _xml(1, "Replacement title 1 body.")
    if source_state == "missing":
        source_path.unlink()
    else:
        source_path.write_text(xml_by_title[1])
    fetched.clear()

    resumed = _extract(store, workers=workers)

    assert resumed.coverage.complete and resumed.title_error_count == 0
    assert 2 not in fetched, "a source whose pinned hash still matches can stay cached"
    if source_state == "missing":
        assert fetched == [1]
    _assert_supported_sources(
        store,
        {
            1: "Replacement title 1 body.",
            2: "Saved title 2 body.",
        },
    )


@pytest.mark.parametrize("workers", [1, 2])
def test_changed_source_missing_selected_section_removes_old_cached_body(
    tmp_path,
    monkeypatch,
    workers,
):
    _, fetched = _patch_sources(monkeypatch, (1, 2))
    store = CorpusArtifactStore(tmp_path / "corpus")
    initial = _extract(store, workers=workers)
    assert initial.coverage.complete and initial.title_error_count == 0
    source_path = _source_paths(store, (1, 2))[1]
    changed_xml = _xml(1, "Replacement unselected body.").replace('N="10.1"', 'N="10.2"')
    source_path.write_text(changed_xml)
    fetched.clear()

    resumed = _extract(store, workers=workers)

    assert resumed.coverage.complete and resumed.title_error_count == 0
    assert fetched == []
    records = {record.citation_path: record for record in load_provisions(resumed.provisions_path)}
    placeholder = records["us/regulation/1/10/1"]
    assert placeholder.body is None
    assert placeholder.metadata is not None
    assert placeholder.metadata["structure_only"] is True
    assert placeholder.metadata["body_status"] == "not_in_ecfr_full_xml"
    assert records["us/regulation/2/20/1"].body == "Saved title 2 body."
    inventory = {item.citation_path: item for item in load_source_inventory(resumed.inventory_path)}
    assert inventory["us/regulation/1/10/1"].sha256 == sha256(changed_xml.encode()).hexdigest()
    assert "Saved title 1 body." not in resumed.provisions_path.read_text()


@pytest.mark.parametrize("workers", [1, 2])
def test_changed_malformed_source_fails_closed_without_rehashing_cached_inventory(
    tmp_path,
    monkeypatch,
    workers,
):
    _patch_sources(monkeypatch, (1, 2))
    store = CorpusArtifactStore(tmp_path / "corpus")
    initial = _extract(store, workers=workers)
    assert initial.coverage.complete and initial.title_error_count == 0
    _source_paths(store, (1, 2))[1].write_text("<ECFR>")
    before = _snapshot(store.root)

    with pytest.raises(ValueError):
        _extract(store, workers=workers)

    assert _snapshot(store.root) == before


@pytest.mark.parametrize("workers", [1, 2])
def test_partially_cached_title_with_changed_malformed_source_fails_closed(
    tmp_path,
    monkeypatch,
    workers,
):
    xml_by_title, _ = _patch_sources(monkeypatch, (1, 2))
    first_structure = _structure(1)
    first_structure["children"][0]["children"].append(
        {
            "type": "section",
            "identifier": "10.2",
            "label": "Section two",
        }
    )
    monkeypatch.setattr(
        ecfr,
        "fetch_ecfr_structure",
        lambda title, as_of: first_structure if title == 1 else _structure(title),
    )
    xml_by_title[1] = _xml(1, "Saved title 1 body.").replace(
        "</DIV5>",
        '<DIV8 N="10.2" TYPE="SECTION" NODE="selected-1-second">'
        "<HEAD>Section two</HEAD><P>Saved second section body.</P></DIV8></DIV5>",
    )
    store = CorpusArtifactStore(tmp_path / "corpus")
    initial = _extract(store, workers=workers)
    assert initial.coverage.complete and initial.title_error_count == 0
    records = load_provisions(initial.provisions_path)
    assert {"us/regulation/1/10/1", "us/regulation/1/10/2"} <= {
        record.citation_path for record in records
    }
    store.write_provisions(
        initial.provisions_path,
        (record for record in records if record.citation_path != "us/regulation/1/10/2"),
    )
    _source_paths(store, (1, 2))[1].write_text("<ECFR>")
    before = _snapshot(store.root)

    with pytest.raises(ValueError):
        _extract(store, workers=workers)

    assert _snapshot(store.root) == before
