"""Every section a locked scope wrote from an official page still reads as that section.

The Arizona and Illinois section parsers refuse a page that names no section,
and the New York crawler records a page behind a "SECTION ..." link that does
not parse as a section as a gap. These tests run those checks over every
official page that a locked Arizona, Illinois or New York statute scope wrote
as a section, so a check that would turn a real section into a gap fails here.
They take the pages from the locked provisions, not from a directory listing,
so a page that a partial checkout lacks fails the run instead of leaving
nothing to read.
"""

from functools import cache
from pathlib import Path

from axiom_corpus.corpus.corpus_locks import load_locks
from axiom_corpus.corpus.io import load_provisions
from axiom_corpus.corpus.models import ProvisionRecord
from axiom_corpus.corpus.state_adapters.arizona import (
    ARIZONA_SECTION_SOURCE_FORMAT,
    parse_arizona_section,
)
from axiom_corpus.corpus.state_adapters.illinois import (
    parse_illinois_ilcs_doc_name,
    parse_illinois_ilcs_section,
)
from axiom_corpus.corpus.state_adapters.new_york import (
    NEW_YORK_SENATE_SOURCE_FORMAT,
    parse_new_york_law_page,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS = REPO_ROOT / "data" / "corpus"


@cache
def _locked_paths() -> tuple[str, ...]:
    return tuple(sorted(load_locks(REPO_ROOT).by_path))


def _written_sections(jurisdiction: str, source_directory: str) -> list[ProvisionRecord]:
    """Sections that locked statute scopes wrote from pages under ``source_directory``."""
    prefix = f"data/corpus/provisions/{jurisdiction}/statute/"
    sections = [
        record
        for path in _locked_paths()
        if path.startswith(prefix)
        for record in load_provisions(REPO_ROOT / path)
        if record.kind == "section"
        and record.source_path is not None
        and f"/{source_directory}/" in record.source_path
    ]
    assert sections, (
        f"no locked {jurisdiction} statute scope wrote a section from {source_directory}"
    )
    return sections


def test_every_written_arizona_section_page_still_reads():
    unreadable = []
    for record in _written_sections("us-az", ARIZONA_SECTION_SOURCE_FORMAT):
        assert record.source_path is not None
        try:
            parse_arizona_section((CORPUS / record.source_path).read_bytes())
        except ValueError as exc:
            unreadable.append(f"{record.citation_path}: {exc}")
    assert unreadable == []


def test_every_written_illinois_section_page_still_reads_as_that_section():
    # A page that cited another section would be written under that section,
    # leaving its own document's section out of the inventory.
    wrong = []
    for record in _written_sections("us-il", "illinois-ilcs"):
        assert record.source_path is not None
        page = CORPUS / record.source_path
        document = parse_illinois_ilcs_doc_name(page.name)
        try:
            section = parse_illinois_ilcs_section(page.read_bytes(), document=document)
        except ValueError as exc:
            wrong.append(f"{record.citation_path}: {exc}")
            continue
        if {section.citation_path, document.citation_path} != {record.citation_path}:
            wrong.append(
                f"{record.citation_path}: page reads as {section.citation_path}, "
                f"document names {document.citation_path}"
            )
    assert wrong == []


def test_every_written_new_york_section_page_still_reads_as_that_section():
    # The crawler reaches these pages through "SECTION ..." links and records a
    # page there that does not parse as a section as a gap.
    wrong = []
    for record in _written_sections("us-ny", NEW_YORK_SENATE_SOURCE_FORMAT):
        assert record.source_path is not None
        assert record.source_url is not None
        parsed = parse_new_york_law_page(
            (CORPUS / record.source_path).read_bytes(),
            source_url=record.source_url,
        )
        if (parsed.kind, parsed.citation_path) != ("section", record.citation_path):
            wrong.append(
                f"{record.citation_path}: page reads as {parsed.kind} {parsed.citation_path}"
            )
    assert wrong == []
