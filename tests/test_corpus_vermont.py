import json
from pathlib import Path

import fitz

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.state_adapters.vermont import (
    extract_vermont_statutes,
    parse_vermont_2026_chapter_151_act_registry,
    parse_vermont_act_text,
    parse_vermont_chapter_index,
    parse_vermont_full_chapter,
)

SECTION_ROWS = (
    ("5811", "Definitions"),
    ("5822", "Tax on income of individuals, estates, and trusts"),
    ("5823", "Vermont income of individuals, estates, and trusts"),
    ("5824", "Adoption of federal income tax laws"),
    ("5916", "Denial of tax credits for S corporations"),
    ("5930u", "Tax credit for affordable housing"),
    ("5930bb", "Eligibility and administration"),
    ("5930ee", "Limitations"),
    ("5930ii", "Research and development tax credit"),
    ("5930ll", "Machinery and equipment tax credit [Applicable through 2030]"),
    ("5930ll", "Repealed effective July 1, 2030"),
)


def _index_html() -> str:
    links = "".join(
        f'<li><a href="/statutes/section/32/151/{section.zfill(5)}">§ {section}. {heading}</a></li>'
        for section, heading in SECTION_ROWS
    )
    return f"""<!doctype html><html><body>
    <ul class="statutes-list">
      <li><strong>Subchapter <span class="dirty">001</span>:
      <span class="caps">INCOME TAX AUTHORITY</span></strong></li>
      {links}
    </ul></body></html>"""


def _full_html() -> str:
    sections = "".join(
        f"<li><p><b>§ {section}. {heading}</b></p><p>Operative body for {section}.</p></li>"
        for section, heading in SECTION_ROWS
    )
    return f"""<!doctype html><html><body>
    <div class="alert">The Statutes below include the actions of the 2025 session.</div>
    <ul class="statutes-list">
      <li><i><strong>Subchapter <span class="dirty">001</span>:
      <span class="caps">INCOME TAX AUTHORITY</span></strong></i></li>
      {sections}
    </ul></body></html>"""


def _registry_json() -> bytes:
    rows = []
    for act, section in (
        ("164", "5811"),
        ("164", "5811"),
        ("164", "5822"),
        ("164", "5823"),
        ("164", "5824"),
        ("164", "5916"),
        ("164", "5930ee"),
        ("164", "5930ii"),
        ("164", "5930u"),
        ("152", "5930bb"),
    ):
        rows.append(
            {
                "TitleNumber": "32",
                "Chapter": "(Ch. 151)",
                "Year": "2026",
                "Citation": f"32 VSA &sect; {section}",
                "ActNo": act,
            }
        )
    return json.dumps({"data": rows}).encode()


ACT_164_TEXT = """No. 164 2026
Sec. 1. REPEAL
32 V.S.A. § 5916 (denial of tax credits for S corporations) is repealed.
Sec. 2. Other law.
Sec. 17. 32 V.S.A. § 5930u(h) is amended to read:
§ 5930u. TAX CREDIT FOR AFFORDABLE HOUSING
Current allocation amendment.
Sec. 18. Other law.
Sec. 55. 32 V.S.A. § 5811 is amended to read:
§ 5811. DEFINITIONS
Federal decoupling text.
Sec. 55a. 32 V.S.A. § 5811 is amended to read:
§ 5811. DEFINITIONS
Qualified small business stock text.
Sec. 56. 32 V.S.A. § 5822 is amended to read:
§ 5822. TAX ON INCOME OF INDIVIDUALS, TRUSTS, AND ESTATES
Adjusted gross income text.
Sec. 57. 32 V.S.A. § 5823 is amended to read:
§ 5823. VERMONT INCOME
Nonresident computation text.
Sec. 58. 32 V.S.A. § 5930ii is amended to read:
§ 5930ii. RESEARCH AND DEVELOPMENT TAX CREDIT
Future 2027 credit text.
Sec. 59. 32 V.S.A. § 5930ee is amended to read:
§ 5930ee. LIMITATIONS
Award limit text.
Sec. 60. 32 V.S.A. § 5824 is amended to read:
§ 5824. ADOPTION OF FEDERAL INCOME TAX LAWS
December 31, 2025 link-up text.
Sec. 61. Other law.
Sec. 64. EFFECTIVE DATES
"""

ACT_152_TEXT = """No. 152 2026
Sec. 19. 32 V.S.A. § 5930bb is amended to read:
§ 5930bb. ELIGIBILITY AND ADMINISTRATION
State-designated centers text.
Sec. 20. Other law.
Sec. 23. EFFECTIVE DATE
"""


def _pdf(text: str) -> bytes:
    document = fitz.open()
    page = document.new_page(width=612, height=2000)
    page.insert_textbox(fitz.Rect(36, 36, 576, 1964), text, fontsize=8)
    return document.tobytes()


def _write_sources(root: Path) -> Path:
    source = root / "source" / "vermont-legislature"
    source.mkdir(parents=True)
    (source / "title-32-chapter-151-index.html").write_text(_index_html())
    (source / "title-32-chapter-151-full.html").write_text(_full_html())
    (source / "2026-acts-affecting-statutes.json").write_bytes(_registry_json())
    (source / "2026-act-152-s325.pdf").write_bytes(_pdf(ACT_152_TEXT))
    (source / "2026-act-164-h933.pdf").write_bytes(_pdf(ACT_164_TEXT))
    return root / "source"


def test_vermont_chapter_parsers_close_index_to_full_text_and_future_variant():
    subchapters, indexed = parse_vermont_chapter_index(_index_html())
    full_subchapters, sections = parse_vermont_full_chapter(_full_html())

    assert subchapters == full_subchapters
    assert len(indexed) == len(sections) == 11
    assert [row.section for row in indexed] == [row.section for row in sections]
    assert indexed[-2].citation_path == "us-vt/statute/32-5930ll"
    assert indexed[-1].citation_path == "us-vt/statute/32-5930ll--effective-2030-07-01"
    assert indexed[-2].status == "operative"
    assert indexed[-1].status == "future_repeal"
    assert sections[-2].status == "operative"
    assert sections[-1].status == "future_repeal"
    assert sections[0].body == "Operative body for 5811."


def test_vermont_2026_registry_and_enacted_text_have_exact_overlay_closure():
    registry = parse_vermont_2026_chapter_151_act_registry(_registry_json())
    overlays = (
        *parse_vermont_act_text(ACT_152_TEXT, act_number="152"),
        *parse_vermont_act_text(ACT_164_TEXT, act_number="164"),
    )

    assert len(registry) == 9
    assert len(overlays) == 10
    assert {(row.act_number, row.statute_section) for row in overlays} == set(registry)
    section_5811 = [row for row in overlays if row.statute_section == "5811"]
    assert [row.act_section for row in section_5811] == ["55", "55a"]


def test_extract_vermont_statutes_writes_complete_source_first_artifacts(tmp_path):
    source_dir = _write_sources(tmp_path)
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_vermont_statutes(
        store,
        version="2026-07-16-pit-central",
        source_dir=source_dir,
        source_as_of="2026-07-16",
        expression_date="2026-07-16",
        only_title="32",
        only_chapter="151",
    )

    assert report.coverage.complete
    assert report.section_count == 11
    assert report.container_count == 3
    assert report.provisions_written == 14
    assert len(report.source_paths) == 5
    assert report.provisions_path.name == (
        "2026-07-16-pit-central-us-vt-title-32-chapter-151.jsonl"
    )

    inventory = load_source_inventory(report.inventory_path)
    records = load_provisions(report.provisions_path)
    assert len(inventory) == len(records) == 14
    chapter = next(row for row in records if row.citation_path == "us-vt/statute/chapter-151")
    section_5811 = next(row for row in records if row.citation_path == "us-vt/statute/32-5811")
    section_5916 = next(row for row in records if row.citation_path == "us-vt/statute/32-5916")
    section_5930ii = next(row for row in records if row.citation_path == "us-vt/statute/32-5930ii")
    section_5930ll = next(row for row in records if row.citation_path == "us-vt/statute/32-5930ll")
    section_5930ll_future = next(
        row
        for row in records
        if row.citation_path == "us-vt/statute/32-5930ll--effective-2030-07-01"
    )
    assert chapter.metadata["indexed_section_units"] == 11
    assert chapter.metadata["unique_section_urls"] == 10
    assert len(section_5811.metadata["2026_enacted_overlays"]) == 2
    assert section_5916.metadata["status"] == "repealed"
    assert section_5916.body.startswith("[Repealed by 2026 Act No. 164")
    assert section_5930ii.metadata["2026_enacted_overlays"][0]["status"] == "future"
    assert section_5930ll.metadata["status"] == "operative"
    assert section_5930ll.metadata["future_repeal_effective_date"] == "2030-07-01"
    assert section_5930ll_future.metadata["status"] == "future_repeal"
    assert section_5930ll_future.metadata["effective_date"] == "2030-07-01"
