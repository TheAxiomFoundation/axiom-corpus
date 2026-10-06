import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from axiom_corpus.corpus import documents as documents_module
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.supabase import deterministic_provision_id
from scripts.repro.us_co_8_ccr_1403_1_sections import (
    MANIFEST,
    REPLACED_ROOT,
    RETAINED_SHA256,
    RETAINED_SOURCE,
    ROOT_CITATION_PATH,
    SCOPE_FIELDS,
    SOURCE_VERSION,
    VERSION,
    build_scope,
)

CORPUS_ROOT = Path("data/corpus")
SCOPE = "us-co/regulation"
SOURCE_PROVISIONS = CORPUS_ROOT / f"provisions/{SCOPE}/{SOURCE_VERSION}.jsonl"
SOURCE_INVENTORY = CORPUS_ROOT / f"inventory/{SCOPE}/{SOURCE_VERSION}.json"
SOURCE_DIRECTORY = CORPUS_ROOT / f"sources/{SCOPE}/{SOURCE_VERSION}"
COMMITTED_PROVISIONS = CORPUS_ROOT / f"provisions/{SCOPE}/{VERSION}.jsonl"
COMMITTED_INVENTORY = CORPUS_ROOT / f"inventory/{SCOPE}/{VERSION}.json"
COMMITTED_COVERAGE = CORPUS_ROOT / f"coverage/{SCOPE}/{VERSION}.json"
COMMITTED_DIRECTORY = CORPUS_ROOT / f"sources/{SCOPE}/{VERSION}"

SECTION_LABELS = [
    "3.100", "3.101", "3.102", "3.103",
    "3.104", "3.104.1", "3.104.2", "3.104.3", "3.104.4",
    "3.105", "3.105.1", "3.105.2", "3.105.3", "3.105.4",
    "3.106", "3.106.1", "3.106.2", "3.107", "3.107.1", "3.108", "3.109",
    "3.110", "3.110.1", "3.110.2", "3.111", "3.112", "3.113",
    "3.114", "3.114.1", "3.114.2", "3.114.3",
    "3.115", "3.115.1", "3.115.2", "3.115.3", "3.115.4", "3.115.5",
    "3.116", "3.116.1", "3.116.2", "3.116.3", "3.116.4", "3.116.5", "3.116.6",
    "3.116.7", "3.116.8", "3.116.9",
    "3.116.91", "3.116.92", "3.116.93", "3.116.94", "3.116.95",
    "editors-notes",
]  # fmt: skip


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tree(directory: Path) -> dict[str, str]:
    return {
        str(path.relative_to(directory)): _digest(path)
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory):
    base = tmp_path_factory.mktemp("successor")
    return base, build_scope(base=base, source_base=CORPUS_ROOT)


def _new_rows(scope) -> list:
    return [
        record
        for record in load_provisions(scope.provisions_path)
        if record.citation_path == ROOT_CITATION_PATH
        or record.citation_path.startswith(f"{ROOT_CITATION_PATH}/")
    ]


def test_build_reproduces_the_committed_successor_byte_for_byte(built) -> None:
    base, scope = built
    assert _digest(scope.provisions_path) == _digest(COMMITTED_PROVISIONS)
    assert _digest(scope.inventory_path) == _digest(COMMITTED_INVENTORY)
    assert _digest(scope.coverage_path) == _digest(COMMITTED_COVERAGE)
    assert _tree(scope.source_directory) == _tree(COMMITTED_DIRECTORY)


def test_source_tree_is_the_consolidated_tree_file_for_file(built) -> None:
    _base, scope = built
    assert _tree(scope.source_directory) == _tree(SOURCE_DIRECTORY)
    assert _digest(scope.source_directory / RETAINED_SOURCE) == RETAINED_SHA256


def test_carried_rows_change_only_the_fields_that_name_the_scope(built) -> None:
    _base, scope = built
    source = load_provisions(SOURCE_PROVISIONS)
    successor = load_provisions(scope.provisions_path)
    kept = [r for r in source if not r.citation_path.startswith(f"{ROOT_CITATION_PATH}/")]
    carried = [r for r in successor if not r.citation_path.startswith(f"{ROOT_CITATION_PATH}/")]
    carried = [r for r in carried if r.citation_path != ROOT_CITATION_PATH]
    assert len(kept) == len(carried) == 174
    source_lines = SOURCE_PROVISIONS.read_text().splitlines()
    source_line = {json.loads(line)["citation_path"]: line for line in source_lines}
    successor_lines = {
        json.loads(line)["citation_path"]: line
        for line in scope.provisions_path.read_text().splitlines()
    }
    for old, new in zip(kept, carried, strict=True):
        assert new.citation_path == old.citation_path
        assert replace(new, **{field: getattr(old, field) for field in SCOPE_FIELDS}) == old
        assert new.version == VERSION
        assert new.id == deterministic_provision_id(new.citation_path, VERSION)
        assert new.source_path == (old.source_path or "").replace(
            f"/{SOURCE_VERSION}/", f"/{VERSION}/", 1
        )
        # Byte level: the JSON line differs only by the version string and the two ids.
        line = successor_lines[new.citation_path].replace(VERSION, SOURCE_VERSION)
        line = line.replace(new.id, old.id)
        if new.parent_id:
            line = line.replace(new.parent_id, str(old.parent_id))
        assert line == source_line[old.citation_path]

    source_items = load_source_inventory(SOURCE_INVENTORY)
    successor_items = load_source_inventory(scope.inventory_path)
    old_items = [i for i in source_items if not i.citation_path.startswith(ROOT_CITATION_PATH)]
    new_items = [i for i in successor_items if not i.citation_path.startswith(ROOT_CITATION_PATH)]
    assert len(old_items) == len(new_items) == 174
    for old_item, new_item in zip(old_items, new_items, strict=True):
        assert replace(new_item, source_path=old_item.source_path) == old_item


def test_section_rows_replace_the_recovery_rows_in_place(built) -> None:
    _base, scope = built
    source_paths = [r.citation_path for r in load_provisions(SOURCE_PROVISIONS)]
    successor = load_provisions(scope.provisions_path)
    successor_paths = [r.citation_path for r in successor]
    start = source_paths.index(REPLACED_ROOT)
    assert source_paths[start : start + 76] == [
        REPLACED_ROOT,
        *(f"{REPLACED_ROOT}/page-{n}" for n in range(1, 76)),
    ]
    assert successor_paths[:start] == source_paths[:start]
    assert successor_paths[start : start + 54] == [
        ROOT_CITATION_PATH,
        *(f"{ROOT_CITATION_PATH}/{label}" for label in SECTION_LABELS),
    ]
    assert successor_paths[start + 54 :] == source_paths[start + 76 :]
    assert len(successor_paths) == len(set(successor_paths)) == 228
    assert not any("/page-" in path for path in successor_paths if "8-ccr-1403-1" in path)
    assert json.loads(COMMITTED_COVERAGE.read_text())["complete"] is True


def test_rulebook_rows_are_a_bodyless_root_over_flat_sections(built) -> None:
    _base, scope = built
    rows = _new_rows(scope)
    root, sections = rows[0], rows[1:]
    assert root.kind == "document" and root.body is None and root.level == 1
    assert root.id == deterministic_provision_id(ROOT_CITATION_PATH, VERSION)
    for row in rows:
        # The retained PDF is ruleVersionId 11042, effective 2023-08-14; it was
        # fetched on 2026-07-13.
        assert (row.expression_date, row.source_as_of) == ("2023-08-14", "2026-07-13")
        assert row.metadata["rule_version_id"] == "11042"
    for section in sections:
        assert section.kind == "section" and section.level == 2
        assert section.parent_citation_path == ROOT_CITATION_PATH
        assert section.parent_id == root.id
        assert section.version == VERSION
        assert section.source_path == f"sources/{SCOPE}/{VERSION}/{RETAINED_SOURCE}"
        assert section.metadata["successor_of_version"] == SOURCE_VERSION
        assert section.metadata["successor_of_citation_path"] == REPLACED_ROOT
        assert section.metadata["download_url"].startswith("https://www.sos.state.co.us/")
        assert "CODE OF COLORADO REGULATIONS" not in (section.body or "")
        assert "Secretary of State State of Colorado" not in (section.body or "")
    # Container sections print only a heading before their first subsection.
    empty = {s.citation_path.rsplit("/", 1)[1] for s in sections if not s.body}
    assert empty == {"3.100", "3.104", "3.110", "3.114", "3.115", "3.116"}


def test_3_111_is_parent_fees_and_3_105_1_keeps_the_income_table(built) -> None:
    _base, scope = built
    rows = {r.citation_path: r for r in _new_rows(scope)}
    fees = rows[f"{ROOT_CITATION_PATH}/3.111"]
    assert fees.heading == "3.111 PARENT FEES"
    assert (fees.body or "").startswith("A. Parent fees are based on gross countable income")
    assert (fees.body or "").endswith("reviewed during each subsequent re-determination.")
    assert fees.metadata["page_start"] == 40 and fees.metadata["page_end"] == 43
    eligibility = rows[f"{ROOT_CITATION_PATH}/3.105.1"].body or ""
    assert (
        "Family Size 100% Federal Poverty Guideline (FPG) 85% State Median Income (SMI) "
        "(State and Federal Maximum Income Limit) 1 $1,132.50 $4,080.62 2 $1,525.83 $5,336.19 "
        "3 $1,919.17 $6,591.77 4 $2,312.50 $7,847.34 5 $2,705.83 $9,102.92 "
        "6 $3,099.17 $10,358.49 7 $3,492.50 $10,593.91 8 $3,885.83 $10,829.33 "
        "Each Additional person $393.33 $235.42"
    ) in eligibility
    hearings = rows[f"{ROOT_CITATION_PATH}/3.116.3"]
    assert hearings.heading == (
        "3.116.3 INTENTIONAL PROGRAM VIOLATION/ADMINISTRATIVE DISQUALIFICATION HEARINGS (IPV/ADH)"
    )
    notes = rows[f"{ROOT_CITATION_PATH}/editors-notes"]
    assert (notes.body or "").startswith("New rule emer. rule eff. 10/01/2022.")
    last = rows[f"{ROOT_CITATION_PATH}/3.116.95"]
    assert (last.body or "").endswith("has been discharged through bankruptcy.")


def test_sections_partition_the_rulebook_text(built) -> None:
    """Every word from the first rule label on lands in exactly one row, in order."""
    _base, scope = built
    content = (SOURCE_DIRECTORY / RETAINED_SOURCE).read_bytes()
    extraction = yaml.safe_load(MANIFEST.read_text())["documents"][0]["extraction"]
    raw = documents_module._filtered_pdf_lines(content, extraction={})
    kept = documents_module._filtered_pdf_lines(content, extraction=extraction)
    # The only lines the configuration removes are the 74 running headers
    # (three title lines and the page number), two rules and page 1's footer.
    removed = len(raw) - len(kept)
    assert removed == 74 * 4 + 2 + 3
    start = [line for line, _page in kept].index("3.100")
    words = " ".join(line for line, _page in kept[start:]).split()
    words = [("editors-notes" if w == "Editor’s" else w) for w in words]
    words = [
        w for i, w in enumerate(words) if not (w == "Notes" and words[i - 1] == "editors-notes")
    ]
    rows = _new_rows(scope)[1:]
    assert " ".join(f"{r.heading} {r.body or ''}" for r in rows).split() == words
