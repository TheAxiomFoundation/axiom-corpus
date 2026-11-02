"""A kept eCFR snapshot never sits beside provisions parsed from other bytes.

axiom-corpus#934: a resume refetches the XML of a title whose provisions are
cached (its snapshot was removed), and graphics capture then fails. The run
must not store the replacement XML while the old provisions stay in place.
It fails before writing anything, and a later resume reparses the title.
"""

import urllib.error
from hashlib import sha256

import pytest

import axiom_corpus.corpus.ecfr as ecfr
from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from tests.test_corpus_ecfr_multi_title_atomicity import (
    AS_OF,
    VERSION,
    _extract,
    _patch_sources,
    _snapshot,
    _source_paths,
    _unused_transcriptions,
    _xml,
)

PNG = b"\x89PNG\r\n\x1a\nvalid graphic fixture"


@pytest.fixture(autouse=True)
def _isolate_synthetic_corpus(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def _with_graphic(xml):
    return xml.replace("</P>", '</P><MATH><IMG src="/graphics/er07oc94.023.gif"/></MATH>')


def _graphic_fetcher(monkeypatch, failure):
    state = {"failure": failure}

    def fetch(identifier):
        if state["failure"] == "download":
            raise urllib.error.URLError("graphic unavailable")
        if state["failure"] == "not-png":
            return b"<html>not a graphic</html>"
        return PNG

    monkeypatch.setattr(ecfr, "fetch_ecfr_graphic", fetch)
    monkeypatch.setattr(ecfr.time, "sleep", lambda _: None)
    return state


def _assert_rows_from_stored_bytes(store, run_id, expected_bodies):
    """Each section row starts with its expected text, found in the bytes its
    inventory item pins. Rows with a graphic also carry the image reference."""
    inventory = {
        item.citation_path: item
        for item in load_source_inventory(store.inventory_path("us", "regulation", run_id))
    }
    records = {
        record.citation_path: record
        for record in load_provisions(store.provisions_path("us", "regulation", run_id))
        if record.kind == "section"
    }
    assert set(records) == {f"us/regulation/{title}/{title * 10}/1" for title in expected_bodies}
    for title, body in expected_bodies.items():
        path = f"us/regulation/{title}/{title * 10}/1"
        item = inventory[path]
        source_bytes = (store.root / item.source_path).read_bytes()
        assert item.sha256 == sha256(source_bytes).hexdigest()
        assert records[path].body.startswith(body)
        assert body.encode() in source_bytes


def _section_run(store, **kwargs):
    return ecfr.extract_ecfr(
        store,
        version=VERSION,
        as_of=AS_OF,
        only_title=1,
        only_sections=("10.1",),
        workers=1,
        **kwargs,
    )


@pytest.mark.parametrize("failure", ["download", "not-png"])
def test_section_resume_graphic_failure_keeps_no_stale_provisions(tmp_path, monkeypatch, failure):
    # A section-filtered resume never took the cached-title shortcut, so the
    # missing snapshot was refetched and the graphic error kept the old rows.
    xml_by_title, _ = _patch_sources(monkeypatch, (1,))
    store = CorpusArtifactStore(tmp_path / "corpus")
    initial = _section_run(store)
    assert initial.coverage.complete and initial.title_error_count == 0
    source_path = store.source_path(
        "us", "regulation", ecfr.ecfr_run_id(VERSION, 1, None, None), "ecfr/title-1.xml"
    )
    source_path.unlink()
    before = _snapshot(store.root)
    xml_by_title[1] = _with_graphic(_xml(1, "Replacement title 1 body."))
    graphics = _graphic_fetcher(monkeypatch, failure)

    with pytest.raises(ValueError, match="cannot revalidate cached eCFR provisions"):
        _section_run(store)
    assert _snapshot(store.root) == before

    graphics["failure"] = None
    resumed = _section_run(store)
    assert resumed.coverage.complete and resumed.title_error_count == 0
    assert source_path.read_text() == xml_by_title[1]
    _assert_rows_from_stored_bytes(
        store, ecfr.ecfr_run_id(VERSION, 1, None, None), {1: "Replacement title 1 body."}
    )


@pytest.mark.parametrize("failure", ["download", "not-png"])
def test_transcription_refresh_graphic_failure_keeps_no_stale_provisions(
    tmp_path, monkeypatch, failure
):
    xml_by_title, _ = _patch_sources(monkeypatch, (1, 2))
    store = CorpusArtifactStore(tmp_path / "corpus")
    initial = _extract(store)
    assert initial.coverage.complete and initial.title_error_count == 0
    _source_paths(store, (1, 2))[1].unlink()
    before = _snapshot(store.root)
    xml_by_title[1] = _with_graphic(_xml(1, "Replacement title 1 body."))
    graphics = _graphic_fetcher(monkeypatch, failure)
    transcriptions = _unused_transcriptions(tmp_path)

    with pytest.raises(ValueError, match="cannot revalidate cached eCFR provisions"):
        _extract(store, graphic_transcriptions=transcriptions)
    assert _snapshot(store.root) == before

    graphics["failure"] = None
    resumed = _extract(store, graphic_transcriptions=transcriptions)
    assert resumed.coverage.complete and resumed.title_error_count == 0
    _assert_rows_from_stored_bytes(
        store, VERSION, {1: "Replacement title 1 body.", 2: "Saved title 2 body."}
    )


@pytest.mark.parametrize("workers", [1, 2])
@pytest.mark.parametrize("failure", ["download", "not-png"])
def test_other_title_graphic_failure_does_not_strand_a_refetched_title(
    tmp_path, monkeypatch, workers, failure
):
    # Title 1 refetches cleanly, but title 2's graphic failure stops the
    # transcription run from committing any title's provisions. Title 1's
    # replacement XML must not be stored beside its old rows.
    xml_by_title, _ = _patch_sources(monkeypatch, (1,))
    store = CorpusArtifactStore(tmp_path / "corpus")
    initial = _extract(store, workers=workers)
    assert initial.coverage.complete and initial.title_error_count == 0
    _source_paths(store, (1,))[1].unlink()
    before = _snapshot(store.root)
    xml_by_title, _ = _patch_sources(monkeypatch, (1, 2))
    xml_by_title[1] = _xml(1, "Replacement title 1 body.")
    xml_by_title[2] = _with_graphic(_xml(2, "New title 2 body."))
    graphics = _graphic_fetcher(monkeypatch, failure)
    transcriptions = _unused_transcriptions(tmp_path)

    with pytest.raises(ValueError, match="cannot revalidate cached eCFR provisions"):
        _extract(store, workers=workers, graphic_transcriptions=transcriptions)
    assert _snapshot(store.root) == before

    graphics["failure"] = None
    resumed = _extract(store, workers=workers, graphic_transcriptions=transcriptions)
    assert resumed.coverage.complete and resumed.title_error_count == 0
    _assert_rows_from_stored_bytes(
        store, VERSION, {1: "Replacement title 1 body.", 2: "New title 2 body."}
    )


def _retained_run(store, source_xml, **kwargs):
    return ecfr.extract_ecfr(
        store,
        version=VERSION,
        as_of=AS_OF,
        only_title=1,
        only_part="10",
        only_sections=("10.1",),
        source_xml=source_xml,
        workers=1,
        **kwargs,
    )


def _retained_snapshot_path(store):
    run_id = ecfr.ecfr_run_id(VERSION, 1, "10", None)
    return run_id, store.source_path("us", "regulation", run_id, "ecfr/title-1-part-10.xml")


@pytest.mark.parametrize("include_appendices", [False, True])
@pytest.mark.parametrize("failure", ["download", "not-png"])
def test_retained_xml_resume_graphic_failure_writes_nothing(
    tmp_path, monkeypatch, failure, include_appendices
):
    # A --source-xml run once wrote the replacement snapshot before it knew
    # whether the title would be reparsed, so the raise below came too late.
    store = CorpusArtifactStore(tmp_path / "corpus")
    source_xml = tmp_path / "title-1-part-10.xml"
    source_xml.write_text(_xml(1, "Saved title 1 body."))
    initial = _retained_run(store, source_xml, include_appendices=include_appendices)
    assert initial.coverage.complete and initial.title_error_count == 0
    run_id, snapshot_path = _retained_snapshot_path(store)
    saved_snapshot = snapshot_path.read_bytes()
    before = _snapshot(store.root)
    replacement = _with_graphic(_xml(1, "Replacement title 1 body."))
    source_xml.write_text(replacement)
    graphics = _graphic_fetcher(monkeypatch, failure)

    with pytest.raises(ValueError, match="cannot revalidate cached eCFR provisions"):
        _retained_run(store, source_xml, include_appendices=include_appendices)
    assert _snapshot(store.root) == before
    assert snapshot_path.read_bytes() == saved_snapshot

    graphics["failure"] = None
    resumed = _retained_run(store, source_xml, include_appendices=include_appendices)
    assert resumed.coverage.complete and resumed.title_error_count == 0
    assert snapshot_path.read_text() == replacement
    _assert_rows_from_stored_bytes(store, run_id, {1: "Replacement title 1 body."})


def test_fresh_retained_xml_graphic_failure_stays_resumable(tmp_path, monkeypatch):
    # With no cached rows nothing can go stale: the retained snapshot is kept
    # for the resume and the title is reported as a title error, as before.
    store = CorpusArtifactStore(tmp_path / "corpus")
    source_xml = tmp_path / "title-1-part-10.xml"
    replacement = _with_graphic(_xml(1, "Fresh title 1 body."))
    source_xml.write_text(replacement)
    graphics = _graphic_fetcher(monkeypatch, "download")

    report = _retained_run(store, source_xml)
    _, snapshot_path = _retained_snapshot_path(store)
    assert report.title_error_count == 1
    assert snapshot_path.read_text() == replacement
    assert "Fresh title 1 body." not in report.provisions_path.read_text()

    graphics["failure"] = None
    resumed = _retained_run(store, source_xml)
    assert resumed.coverage.complete and resumed.title_error_count == 0


@pytest.mark.parametrize("retained", ["valid", "repeated-path", "missing-section"])
def test_retained_xml_with_no_title_result_is_stored_only_after_validation(
    tmp_path, monkeypatch, retained
):
    # When no title result covers the retained title, no result stages its
    # bytes, so extract_ecfr writes them itself after every check has passed.
    # No real input reaches that branch: source_xml requires section
    # selectors, and each one selects its part and section under the retained
    # title. Keying every selected path under another title makes the retained
    # title select none, while the checks on the retained bytes still run.
    title_from_citation_path = ecfr._title_from_citation_path
    monkeypatch.setattr(
        ecfr, "_title_from_citation_path", lambda path: title_from_citation_path(path) + 1000
    )
    store = CorpusArtifactStore(tmp_path / "corpus")
    source_xml = tmp_path / "title-1-part-10.xml"
    xml = _xml(1, "Retained title 1 body.")
    if retained == "repeated-path":
        # A second N that folds to the selected section's citation path.
        xml = xml.replace(
            "</DIV5>",
            '<DIV8 N="10.1()" TYPE="SECTION" NODE="other-1">'
            "<HEAD>Other section</HEAD><P>Conflicting body.</P></DIV8></DIV5>",
        )
    elif retained == "missing-section":
        xml = xml.replace('N="10.1"', 'N="10.2"')
    source_xml.write_text(xml)
    run_id, snapshot_path = _retained_snapshot_path(store)

    if retained != "valid":
        expected_error = "holds citation path" if retained == "repeated-path" else "not found"
        with pytest.raises(ValueError, match=expected_error):
            _retained_run(store, source_xml)
        assert not snapshot_path.exists()
        assert not store.root.exists() or _snapshot(store.root) == {}
        return

    report = _retained_run(store, source_xml)
    assert report.title_error_count == 0
    assert snapshot_path.read_bytes() == source_xml.read_bytes()
    digest = sha256(source_xml.read_bytes()).hexdigest()
    inventory = load_source_inventory(store.inventory_path("us", "regulation", run_id))
    assert {item.citation_path for item in inventory} == {
        "us/regulation/1/10",
        "us/regulation/1/10/1",
    }
    for item in inventory:
        # The inventory pins the stored snapshot, which holds the checked bytes.
        assert item.source_path == str(snapshot_path.relative_to(store.root))
        assert item.sha256 == digest
    assert report.coverage.complete
