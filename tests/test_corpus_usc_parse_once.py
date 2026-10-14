"""US Code extraction parses each title once and writes what three parses wrote.

``extract_usc``, ``extract_usc_directory`` and the US recovery scripts used to parse
a USLM title three times: ``parse_uslm_title`` itself, then again inside
``build_usc_inventory_from_xml`` and ``iter_usc_title_provisions``. They now share
one parsed ``UscTitleDocument``. These tests pin the properties that make that safe:

- re-parsing with the parsed title, which is what the old extractors did, gives an
  equal document;
- each public wrapper equals parse-then-delegate, for any scope and limit;
- the extractors parse each title once and write the same bytes as the old
  re-parsing composition, for any scope, limit, title, date and source form.
"""

from __future__ import annotations

import hashlib
import tempfile
import zipfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from types import ModuleType
from typing import Any
from xml.etree import ElementTree as ET

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus import usc
from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from scripts import recover_ingest, recover_ingest_batch
from tests.test_corpus_usc import (
    SAMPLE_USLM,
    SAMPLE_USLM_42,
    SAMPLE_USLM_NESTED,
    SAMPLE_USLM_SUBSECTIONS,
)

SAMPLES = (SAMPLE_USLM, SAMPLE_USLM_42, SAMPLE_USLM_NESTED, SAMPLE_USLM_SUBSECTIONS)
TITLE_26_SAMPLES = (SAMPLE_USLM, SAMPLE_USLM_NESTED)
TITLE_42_SAMPLES = (SAMPLE_USLM_42, SAMPLE_USLM_SUBSECTIONS)
RELEASE_POINT_URL = "https://uscode.house.gov/download/releasepoints/us/pl/119/103/xml_usc.zip"


@contextmanager
def _counting_parses(*modules: ModuleType) -> Iterator[list[str]]:
    """Record a digest of the text of every ``parse_uslm_title`` call.

    ``usc`` is always patched, which covers the public wrappers; scripts that bind the
    name at import are passed in so their direct calls are counted too.
    """
    calls: list[str] = []
    real = usc.parse_uslm_title

    def counting(xml_content: str, title: str | int | None = None) -> usc.UscTitleDocument:
        calls.append(hashlib.sha256(xml_content.encode()).hexdigest())
        return real(xml_content, title=title)

    with pytest.MonkeyPatch.context() as patch:
        for module in (usc, *modules):
            patch.setattr(module, "parse_uslm_title", counting)
        yield calls


@contextmanager
def _reparsing_each_pass(
    text_for_title: Callable[[str], str], *modules: ModuleType
) -> Iterator[None]:
    """Restore the old composition: each inventory and provision pass re-parses its text.

    The old extractors called ``build_usc_inventory_from_xml(text, title=document.title)``
    and ``iter_usc_title_provisions(text, title=document.title)``, so this is the
    reference path the shared-document extractors must match byte for byte.
    """
    real_inventory = usc._build_usc_inventory
    real_provisions = usc._iter_usc_provisions

    def inventory(document: usc.UscTitleDocument, **kwargs: Any) -> usc.UscInventory:
        reparsed = usc.parse_uslm_title(text_for_title(document.title), title=document.title)
        return real_inventory(reparsed, **kwargs)

    def provisions(document: usc.UscTitleDocument, **kwargs: Any) -> Iterator[Any]:
        reparsed = usc.parse_uslm_title(text_for_title(document.title), title=document.title)
        return real_provisions(reparsed, **kwargs)

    with pytest.MonkeyPatch.context() as patch:
        for module in (usc, *modules):
            patch.setattr(module, "_build_usc_inventory", inventory)
            patch.setattr(module, "_iter_usc_provisions", provisions)
        yield


def _outcome(run: Callable[[CorpusArtifactStore], usc.UscExtractReport]) -> tuple[Any, ...]:
    """Run an extraction into a fresh store; return its report and every written byte."""
    with tempfile.TemporaryDirectory() as tmp:
        store = CorpusArtifactStore(Path(tmp) / "corpus")
        try:
            report = run(store)
        except ValueError as exc:
            return ("error", type(exc).__name__, str(exc))
        files = {
            path.relative_to(store.root).as_posix(): path.read_bytes()
            for path in sorted(store.root.rglob("*"))
            if path.is_file()
        }
        return (
            "ok",
            report.title,
            report.title_count,
            report.section_count,
            report.provisions_written,
            report.coverage.to_mapping(),
            tuple(path.relative_to(store.root).as_posix() for path in report.source_paths),
            files,
        )


def _title_forms(title: str) -> list[str | int | None]:
    """The ways a caller can name a title, plus one that does not match the text."""
    return [None, title, f" {title.upper()} ", int(title), "7"]


@st.composite
def _scopes(draw: st.DrawFn, text: str) -> set[str] | None:
    document = usc.parse_uslm_title(text)
    paths = [item.citation_path for item in usc.build_usc_inventory_from_xml(text).items]
    candidates = [*paths, f"us/statute/{document.title}/no-such-section", "us/statute/99/1"]
    return draw(st.none() | st.sets(st.sampled_from(candidates), max_size=len(candidates)))


@settings(max_examples=60, deadline=None)
@given(text=st.sampled_from(SAMPLES), data=st.data())
def test_reparsing_with_the_parsed_title_gives_an_equal_document(text: str, data: st.DataObject):
    title = data.draw(st.sampled_from(_title_forms(usc.parse_uslm_title(text).title)))

    document = usc.parse_uslm_title(text, title=title)

    assert usc.parse_uslm_title(text, title=document.title) == document
    assert usc.parse_uslm_title(text, title=title) == document


@settings(max_examples=150, deadline=None)
@given(text=st.sampled_from(SAMPLES), data=st.data())
def test_public_wrappers_equal_parse_then_delegate(text: str, data: st.DataObject):
    title = data.draw(st.sampled_from(_title_forms(usc.parse_uslm_title(text).title)))
    allowed = data.draw(_scopes(text))
    inventory_kwargs = {
        "run_id": data.draw(st.sampled_from([None, "2026-05-05-title-26"])),
        "source_sha256": data.draw(st.sampled_from([None, "0" * 64])),
        "source_download_url": data.draw(st.sampled_from([None, RELEASE_POINT_URL])),
        "limit": data.draw(st.none() | st.integers(min_value=0, max_value=12)),
        "allowed_citation_paths": allowed,
        "source_path": data.draw(st.sampled_from([None, "sources/us/statute/x/usc.xml"])),
    }
    provision_kwargs = {
        "version": "2026-05-05",
        "source_path": "sources/us/statute/2026-05-05/uslm/usc.xml",
        "source_as_of": data.draw(st.sampled_from([None, "2026-05-06"])),
        "expression_date": data.draw(st.sampled_from([None, "2026-05-07"])),
        "source_download_url": data.draw(st.sampled_from([None, RELEASE_POINT_URL])),
        "allowed_citation_paths": allowed,
    }

    document = usc.parse_uslm_title(text, title=title)

    assert usc.build_usc_inventory_from_xml(
        text, title=title, **inventory_kwargs
    ) == usc._build_usc_inventory(document, **inventory_kwargs)
    assert list(usc.iter_usc_title_provisions(text, title=title, **provision_kwargs)) == list(
        usc._iter_usc_provisions(document, **provision_kwargs)
    )


def test_iter_usc_title_provisions_still_parses_on_first_iteration():
    records = usc.iter_usc_title_provisions("<not-xml", version="v", source_path="p")

    with pytest.raises(ET.ParseError):
        next(records)


def _write_source(directory: Path, text: str, *, as_zip: bool) -> Path:
    title = usc.parse_uslm_title(text).title
    if not as_zip:
        path = directory / f"usc{title}.xml"
        path.write_text(text)
        return path
    path = directory / f"xml_usc{title}@119-103.zip"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f"usc{title}.xml", text)
    return path


@settings(max_examples=120, deadline=None)
@given(text=st.sampled_from(SAMPLES), as_zip=st.booleans(), data=st.data())
def test_extract_usc_parses_once_and_writes_what_reparsing_wrote(
    text: str, as_zip: bool, data: st.DataObject
):
    inventory_size = len(usc.build_usc_inventory_from_xml(text).items)
    download_url = data.draw(st.sampled_from([None, RELEASE_POINT_URL]))
    kwargs = {
        "title": data.draw(st.sampled_from(_title_forms(usc.parse_uslm_title(text).title))),
        "allowed_citation_paths": data.draw(_scopes(text)),
        "limit": data.draw(st.none() | st.integers(min_value=0, max_value=inventory_size + 2)),
        "source_as_of": data.draw(st.sampled_from([None, "2026-05-06"])),
        "expression_date": data.draw(st.sampled_from([None, "2026-05-07", date(2026, 5, 8)])),
        "source_download_url": download_url,
        "prior_release_point": download_url is not None and data.draw(st.booleans()),
    }
    with tempfile.TemporaryDirectory() as tmp:
        source = _write_source(Path(tmp), text, as_zip=as_zip)
        source_kwargs = {"source_zip": source} if as_zip else {"source_xml": source}

        def run(store: CorpusArtifactStore) -> usc.UscExtractReport:
            return usc.extract_usc(store, version="2026-05-05", **source_kwargs, **kwargs)

        with _counting_parses() as calls:
            shared = _outcome(run)
        with _reparsing_each_pass(lambda _title: text):
            reference = _outcome(run)

    assert shared == reference
    assert shared[0] == "ok"
    assert len(calls) == 1


@settings(max_examples=80, deadline=None)
@given(
    text_26=st.sampled_from(TITLE_26_SAMPLES),
    text_42=st.sampled_from(TITLE_42_SAMPLES),
    only_title=st.sampled_from([None, "26", 42, " 42 "]),
    limit=st.none() | st.integers(min_value=0, max_value=14),
    source_as_of=st.sampled_from([None, "2026-04-01"]),
    expression_date=st.sampled_from([None, "2026-04-02", date(2026, 4, 3)]),
    source_download_url=st.sampled_from([None, RELEASE_POINT_URL]),
)
def test_extract_usc_directory_parses_each_title_once_and_writes_what_reparsing_wrote(
    text_26: str,
    text_42: str,
    only_title: str | int | None,
    limit: int | None,
    source_as_of: str | None,
    expression_date: str | date | None,
    source_download_url: str | None,
):
    texts = {"26": text_26, "42": text_42}
    with tempfile.TemporaryDirectory() as tmp:
        source_dir = Path(tmp) / "uscode"
        source_dir.mkdir()
        for text in texts.values():
            _write_source(source_dir, text, as_zip=False)

        def run(store: CorpusArtifactStore) -> usc.UscExtractReport:
            return usc.extract_usc_directory(
                store,
                version="2026-04-29",
                source_dir=source_dir,
                only_title=only_title,
                source_as_of=source_as_of,
                expression_date=expression_date,
                source_download_url=source_download_url,
                limit=limit,
            )

        with _counting_parses() as calls:
            shared = _outcome(run)
        with _reparsing_each_pass(texts.__getitem__):
            reference = _outcome(run)

    assert shared == reference
    # ``limit=0`` stops before any row and raises in both paths; a run that writes
    # parses each title it reaches exactly once.
    assert len(calls) == len(set(calls)) >= 1
    if shared[0] == "ok":
        assert len(calls) == shared[2]


def test_recover_ingest_parses_each_uscode_row_once(tmp_path: Path):
    source = _write_source(tmp_path, SAMPLE_USLM_NESTED, as_zip=False)
    row = recover_ingest.FetchedFile(
        path=source,
        url="https://uscode.house.gov/download/usc26.xml",
        fetched_at="2026-07-13T12:00:00Z",
        sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        sidecar=source.with_suffix(".json"),
    )
    entry = {
        "jurisdiction": "us",
        "document_class": "statute",
        "version": "2026-07-13-recovery",
        "title": "26",
        "source_as_of": "2026-07-13",
        "expression_date": "2026-07-13",
    }
    source_keys = {source: "sources/us/statute/2026-07-13-recovery/official-documents/usc26.xml"}

    with _counting_parses(recover_ingest) as calls:
        shared = recover_ingest._uscode_records(entry, (row,), source_keys)
    with _reparsing_each_pass(lambda _title: SAMPLE_USLM_NESTED, recover_ingest):
        reference = recover_ingest._uscode_records(entry, (row,), source_keys)

    assert shared == reference
    items, records = shared
    assert [record.citation_path for record in records] == [
        "us/statute/26",
        "us/statute/26/1401",
        "us/statute/26/1401/b",
        "us/statute/26/1401/b/2",
        "us/statute/26/1401/b/2/A",
        "us/statute/26/1401/b/2/A/i",
        "us/statute/26/1401/b/2/A/ii",
        "us/statute/26/1401/b/2/B",
    ]
    assert [item.citation_path for item in items] == [record.citation_path for record in records]
    assert len(calls) == 1


def test_recover_ingest_batch_parses_each_uslm_title_once(tmp_path: Path):
    source = _write_source(tmp_path, SAMPLE_USLM, as_zip=False)
    data = source.read_bytes()
    entry = {
        "parser": "usc:uslm-xml",
        "document_id": "uscode-title-26",
        "proposed_version": "2026-07-13-recovery",
        "covers_citation_paths": ["us/statute/26/32"],
    }
    provenance = {"sha256": hashlib.sha256(data).hexdigest(), "url": "https://uscode.house.gov/"}
    source_key = "sources/us/statute/2026-07-13-recovery/official-documents/usc26.xml"

    with _counting_parses(recover_ingest_batch) as calls:
        shared = recover_ingest_batch._parse(entry, source, data, provenance, source_key)
    with _reparsing_each_pass(lambda _title: SAMPLE_USLM, recover_ingest_batch):
        reference = recover_ingest_batch._parse(entry, source, data, provenance, source_key)

    assert shared == reference
    assert [record.citation_path for record in shared[1]] == [
        "us/statute/26",
        "us/statute/26/32",
        "us/statute/26/151",
    ]
    assert len(calls) == 1
