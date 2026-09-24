import hashlib
import re
from pathlib import Path

from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from scripts.repro.us_ny_tax_article_22_line_structure import (
    SOURCE_VERSION,
    VERSION,
    build_scope,
)

CORPUS_ROOT = Path("data/corpus")
RELEASED_PROVISIONS = CORPUS_ROOT / f"provisions/us-ny/statute/{SOURCE_VERSION}.jsonl"
RELEASED_INVENTORY = CORPUS_ROOT / f"inventory/us-ny/statute/{SOURCE_VERSION}.json"


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _span(body: str, label: str, following: tuple[str, ...], start: int = 0, end: int | None = None):
    """First line-start ``(label)`` in ``body[start:end]`` up to the next sibling."""
    window = body[start:end]
    heads = [m.start() for m in re.finditer(rf"(?m)^\({re.escape(label)}\) ", window)]
    assert heads, label
    head = heads[0]
    stops = [
        m.start()
        for sibling in following
        for m in re.finditer(rf"(?m)^\({re.escape(sibling)}\) ", window)
        if m.start() > head
    ]
    stop = min(stops) if stops else len(window)
    return start + head, start + len(window[:stop].rstrip())


def test_successor_is_deterministic_and_section_shaped(tmp_path):
    first = build_scope(base=tmp_path / "first", source_base=CORPUS_ROOT)
    second = build_scope(base=tmp_path / "second", source_base=CORPUS_ROOT)

    for left, right in (
        (first.inventory_path, second.inventory_path),
        (first.provisions_path, second.provisions_path),
        (first.coverage_path, second.coverage_path),
    ):
        assert _digest(left) == _digest(right)

    records = load_provisions(first.provisions_path)
    released = load_provisions(RELEASED_PROVISIONS)
    released_roots = [record for record in released if record.kind == "document"]
    assert first.section_count == len(records) == len(released_roots) == 93
    assert [record.citation_path for record in records] == [
        record.citation_path for record in released_roots
    ]
    assert {record.kind for record in records} == {"section"}
    assert all(record.version == VERSION for record in records)
    assert all(record.parent_citation_path is None for record in records)
    assert not any("/block-" in record.citation_path for record in records)


def test_successor_keeps_released_words_and_source_bytes(tmp_path):
    scope = build_scope(base=tmp_path, source_base=CORPUS_ROOT)
    records = {record.citation_path: record for record in load_provisions(scope.provisions_path)}
    released_blocks = {
        record.parent_citation_path: record.body or ""
        for record in load_provisions(RELEASED_PROVISIONS)
        if record.kind == "block"
    }
    for citation_path, record in records.items():
        assert (record.body or "").split() == released_blocks[citation_path].split()

    released_hashes = {
        item.citation_path: item.sha256
        for item in load_source_inventory(RELEASED_INVENTORY)
        if (item.metadata or {}).get("kind") == "document"
    }
    for item in load_source_inventory(scope.inventory_path):
        assert item.sha256 == released_hashes[item.citation_path]
        assert _digest(tmp_path / item.source_path) == item.sha256
        assert item.source_format == "new-york-senate-html"


def test_successor_606_resolves_real_property_tax_credit_paths(tmp_path):
    scope = build_scope(base=tmp_path, source_base=CORPUS_ROOT)
    section = next(
        record
        for record in load_provisions(scope.provisions_path)
        if record.citation_path == "us-ny/statute/TAX/606"
    )
    body = section.body or ""
    assert section.heading == "Credits against tax"
    assert section.legal_identifier == "N.Y. TAX Law § 606"
    assert section.metadata is not None
    assert section.metadata["revision_date"] == "2026-09-04"
    assert "\\n" not in body

    e_start, e_end = _span(body, "e", ("e-1", "f"))
    assert body[e_start:].startswith("(e) Real property tax circuit breaker credit.")
    seven_start, seven_end = _span(body, "7", ("8",), e_start, e_end)
    assert body[seven_start:seven_end].startswith(
        "(7) No credit shall be granted under this subsection:"
    )
    d_start, d_end = _span(body, "D", ("E",), seven_start, seven_end)
    assert body[d_start:d_end] == (
        "(D) To a tenant if the adjusted rent for the residence exceeds four hundred "
        "fifty dollars per month on average."
    )

    # The 2025 flat credit tables of subsection (e)(3)(B) keep their header and
    # one row per line.
    subsection = body[e_start:e_end]
    header = (
        "\nIf the taxpayer's federal adjusted gross\n"
        "income for the taxable year is:      The credit amount is:\n"
    )
    assert subsection.count(header) == 2
    assert (
        "(ii) for all other taxpayers the amount of the credit allowable under this "
        "subsection shall be:" + header + "$5,000 or less"
    ) in subsection
    assert "\n$3,000 or less                                      $375\n" in subsection
    assert "\nOver $14,000 but not over $18,000                   $150\n" in subsection
    assert "\n$5,000 or less                                      $75\n" in subsection
    assert "\nOver $14,000 but not over $18,000                   $50\n" in subsection
