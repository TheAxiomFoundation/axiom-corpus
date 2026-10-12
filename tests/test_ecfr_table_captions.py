"""eCFR table captions reach provision bodies as each table's leading line(s).

A ``<CAPTION>`` names the table it heads ("Table 1—For Employees"). Before
this behaviour the adapter read only ``TR`` rows, so 20 CFR 404.1592 kept the
rows of its two tables but lost which one applies to employees and which to the
self-employed. docs/validation/ecfr-table-captions-2026-10-12.md records the
impact analysis and the replay over every retained eCFR source.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from hypothesis import given
from hypothesis import strategies as st

from axiom_corpus.corpus.ecfr import (
    EcfrPartTarget,
    _table_text,
    iter_ecfr_title_provisions,
)
from tests.corpus_scan import corpus_scan_timeout

REPO_ROOT = Path(__file__).resolve().parents[1]

# 20 CFR 404.1592(d)(2)-(3) as eCFR served it on 2026-10-12, with the
# paragraph prose shortened. Each table keeps its real markup shape:
# DIV/DIV/TABLE, a CAPTION holding one P class="title", then THEAD and TBODY.
SECTION_404_1592_XML = """
<ECFR>
  <DIV5 N="404" TYPE="PART">
    <HEAD>PART 404—FEDERAL OLD-AGE, SURVIVORS AND DISABILITY INSURANCE (1950- )</HEAD>
    <DIV8 N="404.1592" TYPE="SECTION">
      <HEAD>§ 404.1592 The trial work period.</HEAD>
      <P>(i) Before January 1, 2002, your earnings in a month were more than the amount(s) indicated in Table 1 for the year(s) in which you worked.</P>
      <DIV width="100%"><DIV class="gpotbl_div">
        <TABLE border="1" class="gpo_table" frame="void" width="100%">
          <CAPTION><P class="title">Table 1&#x2014;For Employees</P></CAPTION>
          <THEAD>
            <TR><TH>For months</TH><TH>You earn more than</TH></TR>
          </THEAD>
          <TBODY>
            <TR><TD>In calendar years before 1979</TD><TD>$50</TD></TR>
            <TR><TD>In calendar year 2001</TD><TD>530</TD></TR>
          </TBODY>
        </TABLE>
      </DIV></DIV>
      <DIV width="100%"><DIV class="gpotbl_div">
        <TABLE border="1" class="gpo_table" frame="void" width="100%">
          <CAPTION><P class="title">Table 2&#x2014;For the Self-Employed</P></CAPTION>
          <THEAD>
            <TR>
              <TH>For months</TH>
              <TH>Your net earnings are more than</TH>
              <TH>Or you work in the business more than</TH>
            </TR>
          </THEAD>
          <TBODY>
            <TR><TD>In calendar years before 1979</TD><TD>$50</TD><TD>15 hours.</TD></TR>
            <TR><TD>In calendar year 2001</TD><TD>530</TD><TD>80 hours.</TD></TR>
          </TBODY>
        </TABLE>
      </DIV></DIV>
      <P>(e) Limitations on the number of trial work periods.</P>
    </DIV8>
  </DIV5>
</ECFR>
"""

EMPLOYEES = "Table 1—For Employees"
SELF_EMPLOYED = "Table 2—For the Self-Employed"


def _last_body(xml: str, *, title: int, part: str, include_appendices: bool = False) -> str:
    records = tuple(
        iter_ecfr_title_provisions(
            xml,
            (EcfrPartTarget(title=title, part=part),),
            version="2026-10-12-test",
            source_path="sources/test/ecfr.xml",
            include_appendices=include_appendices,
        )
    )
    body = records[-1].body
    assert body is not None
    return body


def _table(markup: str) -> ET.Element:
    return ET.fromstring(f"<TABLE>{markup}</TABLE>")


def test_section_tables_open_with_their_captions():
    body = _last_body(SECTION_404_1592_XML, title=20, part="404")

    assert body.split("\n\n") == [
        "(i) Before January 1, 2002, your earnings in a month were more than the "
        "amount(s) indicated in Table 1 for the year(s) in which you worked.",
        "\n".join([
            EMPLOYEES,
            "For months | You earn more than",
            "In calendar years before 1979 | $50",
            "In calendar year 2001 | 530",
        ]),
        "\n".join([
            SELF_EMPLOYED,
            "For months | Your net earnings are more than | "
            "Or you work in the business more than",
            "In calendar years before 1979 | $50 | 15 hours.",
            "In calendar year 2001 | 530 | 80 hours.",
        ]),
        "(e) Limitations on the number of trial work periods.",
    ]


def test_caption_text_reaches_the_body_only_through_the_caption():
    """Anti-vacuous: the assertions above cannot pass without CAPTION handling.

    Each caption string occurs once in the fixture, inside its CAPTION, so no
    other element can supply it. Stripping the CAPTION elements must remove
    exactly those lines and nothing else; under the old rows-only behaviour the
    two bodies were identical and this test fails.
    """
    for caption in ("Table 1&#x2014;For Employees", "Table 2&#x2014;For the Self-Employed"):
        assert SECTION_404_1592_XML.count(caption) == 1
        assert f'<CAPTION><P class="title">{caption}</P></CAPTION>' in SECTION_404_1592_XML
    stripped_xml = re.sub(r"<CAPTION>.*?</CAPTION>", "", SECTION_404_1592_XML)
    assert stripped_xml.count("<CAPTION>") == 0

    with_captions = _last_body(SECTION_404_1592_XML, title=20, part="404")
    without_captions = _last_body(stripped_xml, title=20, part="404")

    assert with_captions != without_captions
    assert EMPLOYEES not in without_captions
    assert SELF_EMPLOYED not in without_captions
    lines = with_captions.split("\n")
    for caption in (EMPLOYEES, SELF_EMPLOYED):
        assert lines.count(caption) == 1
        assert lines[lines.index(caption) + 1].startswith("For months | ")
    assert [line for line in lines if line not in {EMPLOYEES, SELF_EMPLOYED}] == (
        without_captions.split("\n")
    )


@pytest.mark.parametrize(
    ("caption", "expected"),
    [
        pytest.param(
            # 26 CFR 1.72-9 Table VIII: title, then two headnotes; <sup> joins inline.
            '<CAPTION><P class="title">Table VIII&#x2014;Temporary Life Annuities; '
            "<sup>1</sup> One Life&#x2014;Expected Return Multiples</P>"
            '<P class="headnote">[See footnote at end of tables]</P>'
            '<P class="headnote">Temporary Period&#x2014;Maximum Duration of Annuity</P>'
            "</CAPTION>",
            [
                "Table VIII—Temporary Life Annuities; 1 One Life—Expected Return Multiples",
                "[See footnote at end of tables]",
                "Temporary Period—Maximum Duration of Annuity",
            ],
            id="title-and-headnotes",
        ),
        pytest.param(
            '<CAPTION><P class="headnote">[In thousands of dollars]</P></CAPTION>',
            ["[In thousands of dollars]"],
            id="headnote-only",
        ),
        pytest.param(
            # 47 CFR 54.621: inline emphasis stays inside one line.
            '<CAPTION><P class="title">Table 1 to Paragraph (<E T="01">b</E>)(2)'
            "&#x2014;Prioritization Schedule</P></CAPTION>",
            ["Table 1 to Paragraph (b)(2)—Prioritization Schedule"],
            id="inline-emphasis",
        ),
        pytest.param(
            '<CAPTION><P class="title">Table E</P><P class="headnote"><strong>'
            "Table E&#x2014;Single Life, Unisex</strong></P></CAPTION>",
            ["Table E", "Table E—Single Life, Unisex"],
            id="strong-headnote",
        ),
        pytest.param("<CAPTION>Table 9</CAPTION>", ["Table 9"], id="loose-text"),
        pytest.param(
            '<CAPTION>Table <E T="01">9</E> rates</CAPTION>',
            ["Table 9 rates"],
            id="loose-inline-markup-is-one-line",
        ),
        pytest.param(
            "<CAPTION>Schedule <P>A</P> rates</CAPTION>",
            ["Schedule A rates"],
            id="mixed-text-and-paragraph-is-one-line",
        ),
        pytest.param("<CAPTION/>", [], id="empty"),
        pytest.param(
            '<CAPTION><P class="title">  </P></CAPTION>', [], id="blank-paragraph"
        ),
    ],
)
def test_caption_shapes(caption, expected):
    rows = "<THEAD><TR><TH>Year</TH><TH>Amount</TH></TR></THEAD><TBODY><TR><TD>2001</TD><TD>530</TD></TR></TBODY>"

    assert _table_text(_table(caption + rows)).split("\n") == [
        *expected,
        "Year | Amount",
        "2001 | 530",
    ]


def test_caption_only_table_is_kept_as_its_own_block():
    xml = (
        '<ECFR><DIV5 N="999" TYPE="PART"><HEAD>Part 999</HEAD>'
        '<DIV8 N="§ 999.1" TYPE="SECTION"><HEAD>§ 999.1 Rates.</HEAD>'
        "<P>(a) The rates are:</P>"
        '<DIV class="gpotbl_div"><TABLE><CAPTION><P class="title">Table 1 to Paragraph (a)'
        "</P></CAPTION></TABLE></DIV>"
        "<P>(b) Reserved.</P>"
        "</DIV8></DIV5></ECFR>"
    )

    assert _last_body(xml, title=45, part="999").split("\n\n") == [
        "(a) The rates are:",
        "Table 1 to Paragraph (a)",
        "(b) Reserved.",
    ]


def test_appendix_table_caption_precedes_rows_and_image_placeholders():
    xml = (
        '<ECFR><DIV5 N="604" TYPE="PART"><HEAD>Part 604</HEAD>'
        '<DIV9 N="Appendix A to Part 604" TYPE="APPENDIX"><HEAD>Appendix A</HEAD>'
        '<DIV class="gpotbl_div"><TABLE><CAPTION><P class="title">Table A&#x2014;Form'
        "</P></CAPTION>"
        '<TR><TD>Signature</TD><TD><IMG src="/graphics/EC01JA91.007.gif"/></TD></TR>'
        "</TABLE></DIV>"
        "</DIV9></DIV5></ECFR>"
    )

    assert _last_body(xml, title=45, part="604", include_appendices=True).split("\n\n") == [
        "Table A—Form\nSignature",
        "[Official source image: ecfr/graphics/EC01JA91.007.png]",
    ]


def test_retained_part_416_source_emits_the_captions_its_release_lacks():
    """Real bytes: 20 CFR 416.974 and 416.1112 each open a table with "Table 1".

    The released 2026-09-11 scope was extracted before captions were emitted,
    so its stored bodies lack the line; re-extracting the retained XML adds it
    directly above each table's first row and changes nothing else. Those two
    records are successor candidates (see the validation note).
    """
    version = "2026-09-11-title-20-part-416"
    xml = (
        REPO_ROOT
        / f"data/corpus/sources/us/regulation/{version}/ecfr/title-20-part-416.xml"
    ).read_text()
    stored = {
        record["citation_path"]: record["body"]
        for line in (
            REPO_ROOT / f"data/corpus/provisions/us/regulation/{version}.jsonl"
        ).read_text().splitlines()
        for record in [json.loads(line)]
    }
    extracted = {
        record.citation_path: record.body
        for record in iter_ecfr_title_provisions(
            xml,
            (EcfrPartTarget(title=20, part="416"),),
            version=version,
            source_path="sources/test/ecfr.xml",
        )
    }

    for section in ("974", "1112"):
        path = f"us/regulation/20/416/{section}"
        new_lines = extracted[path].split("\n")
        old_lines = stored[path].split("\n")
        caption_index = next(
            index
            for index, line in enumerate(new_lines)
            if line == "Table 1" and " | " in new_lines[index + 1]
        )
        assert new_lines[: caption_index] + new_lines[caption_index + 1 :] == old_lines
        assert old_lines[caption_index] == new_lines[caption_index + 1]


_TEXT = st.text(
    alphabet=st.characters(categories=("L", "N", "P", "S", "Zs")), max_size=24
)


@st.composite
def _captioned_tables(draw):
    paragraphs = []
    for _ in range(draw(st.integers(min_value=0, max_value=3))):
        text = draw(_TEXT)
        cut_a = draw(st.integers(min_value=0, max_value=len(text)))
        cut_b = draw(st.integers(min_value=cut_a, max_value=len(text)))
        paragraphs.append((draw(st.sampled_from(["title", "headnote"])), text, cut_a, cut_b))
    rows = draw(st.lists(st.lists(_TEXT, max_size=3), max_size=4))
    return paragraphs, rows


def _build_table(paragraphs, rows, *, with_caption: bool) -> ET.Element:
    table = ET.Element("TABLE")
    if with_caption:
        caption = ET.SubElement(table, "CAPTION")
        for css_class, text, cut_a, cut_b in paragraphs:
            paragraph = ET.SubElement(caption, "P", {"class": css_class})
            paragraph.text = text[:cut_a]
            if cut_b > cut_a:
                emphasis = ET.SubElement(paragraph, "E", {"T": "01"})
                emphasis.text = text[cut_a:cut_b]
                emphasis.tail = text[cut_b:]
            else:
                paragraph.text = text
    body = ET.SubElement(table, "TBODY")
    for cells in rows:
        row = ET.SubElement(body, "TR")
        for cell in cells:
            ET.SubElement(row, "TD").text = cell
    return table


@given(_captioned_tables())
def test_caption_lines_lead_in_order_and_rows_are_unchanged(case):
    """Invariants for every caption of P paragraphs and every row set.

    1. The output opens with one line per non-blank caption paragraph, in
       source order, each the paragraph's whitespace-normalized text (inline
       markup never splits a paragraph across lines).
    2. Everything after those lines is byte-identical to the same table
       without its caption: a caption never alters, drops, or reorders rows.
    """
    paragraphs, rows = case
    expected = [
        line
        for _, text, _, _ in paragraphs
        if (line := re.sub(r"\s+", " ", text).strip())
    ]

    with_caption = _table_text(_build_table(paragraphs, rows, with_caption=True))
    without_caption = _table_text(_build_table(paragraphs, rows, with_caption=False))

    lines = with_caption.split("\n") if with_caption else []
    assert lines[: len(expected)] == expected
    assert "\n".join(lines[len(expected) :]) == without_caption


AUDIT_REPORT = REPO_ROOT / "docs/validation/ecfr-table-captions-2026-10-12.audit.json"
CORPUS_ROOT = REPO_ROOT / "data/corpus"


def _audit_input_bytes() -> int:
    # The audit's cost tracks the us/regulation provisions it reads and the
    # eCFR XML they name, so its budget follows tests/corpus_scan.py.
    return sum(
        path.stat().st_size
        for root in (
            CORPUS_ROOT / "provisions/us/regulation",
            CORPUS_ROOT / "sources/us/regulation",
        )
        if root.is_dir()
        for path in root.rglob("*")
        if path.suffix in {".jsonl", ".xml"} and path.is_file()
    )


def _released_findings(report: dict) -> dict[tuple[str, str], tuple[str, ...]]:
    # Only what a stored body lacks is compared. Release names are left out
    # (every new union selector re-lists these scopes), and so is
    # caption_only_change, which holds for the adapter that wrote the report
    # but would drift with any later change to how other text is rendered.
    return {
        (scope["scope"], record["citation_path"]): tuple(record["missing_caption_lines"])
        for scope in report["scopes"]
        if scope["released_in"]
        for record in scope["records"]
    }


@pytest.mark.timeout(corpus_scan_timeout(_audit_input_bytes()))
def test_released_scopes_missing_captions_match_the_recorded_successor_candidates():
    """The recorded successor list stays complete for released eCFR scopes.

    If this fails because a release selector now names another eCFR scope
    extracted before captions were emitted, release a successor extracted with
    this adapter instead, or rerun scripts/audit_ecfr_table_captions.py
    --output docs/validation/ecfr-table-captions-2026-10-12.audit.json and add
    the scope to the validation note's successor list.
    """
    from scripts.audit_ecfr_table_captions import audit

    actual = _released_findings(audit(CORPUS_ROOT, REPO_ROOT / "manifests/releases"))
    recorded = _released_findings(json.loads(AUDIT_REPORT.read_text()))

    assert recorded
    assert actual == recorded


def test_missing_caption_lines_counts_caption_lines_only():
    from scripts.audit_ecfr_table_captions import missing_caption_lines

    rows = "Adjusted basis per books | Market value\nCash | 3,000"
    without = f"(b) Partnership AB has these assets:\n\nAssets\n\n{rows}"
    rendered = f"(b) Partnership AB has these assets:\n\nAssets\n\nAssets\n{rows}"

    # 26 CFR 1.751-1 shape: the caption repeats a line already in the body.
    assert missing_caption_lines(without, rendered, ["Assets"]) == ["Assets"]
    assert missing_caption_lines(rendered, rendered, ["Assets"]) == []
    # A body that carries its captions is not flagged when a later adapter
    # renders some unrelated text differently.
    drifted = rendered.replace("(b) Partnership AB", "(b) Partnership AB (as amended)")
    assert missing_caption_lines(rendered, drifted + "\n\nNew note.", ["Assets"]) == []


def _write_scope(base: Path, version: str, xml: str, records: list[dict]) -> None:
    source_path = f"sources/us/regulation/{version}/ecfr/title-20-part-416.xml"
    (base / source_path).parent.mkdir(parents=True, exist_ok=True)
    (base / source_path).write_text(xml)
    provisions = base / "provisions/us/regulation" / f"{version}.jsonl"
    provisions.parent.mkdir(parents=True, exist_ok=True)
    provisions.write_text(
        "".join(
            json.dumps({"source_format": "ecfr-xml", "source_path": source_path, **record}) + "\n"
            for record in records
        )
    )


def test_audit_follows_materialized_subparts_and_spares_captioned_successors(tmp_path):
    """Sections sit under subpart paths that do not prefix their own paths.

    us/regulation/20/416/1112 has parent us/regulation/20/416/subpart-K. A
    subpart body materialized from that section inherits its missing caption;
    a successor extracted with captions is not reported.
    """
    from scripts.audit_ecfr_table_captions import audit

    xml = (
        '<DIV5 N="416" TYPE="PART"><HEAD>PART 416</HEAD>'
        '<DIV6 N="K" TYPE="SUBPART"><HEAD>Subpart K—Income</HEAD>'
        '<DIV8 N="416.1112" TYPE="SECTION"><HEAD>§ 416.1112 Earned income we do not count.</HEAD>'
        "<P>(c)(4) See Table 1.</P>"
        '<DIV class="gpotbl_div"><TABLE><CAPTION><P class="title">Table 1</P></CAPTION>'
        "<TR><TH>Age</TH><TH>Amount</TH></TR><TR><TD>Under 22</TD><TD>$2,350</TD></TR>"
        "</TABLE></DIV></DIV8></DIV6></DIV5>"
    )
    section_path = "us/regulation/20/416/1112"
    subpart_path = "us/regulation/20/416/subpart-K"
    captioned = _last_body(f"<ECFR>{xml}</ECFR>", title=20, part="416")
    uncaptioned = _last_body(
        re.sub(r"<CAPTION>.*?</CAPTION>", "", f"<ECFR>{xml}</ECFR>"), title=20, part="416"
    )
    assert captioned != uncaptioned

    def records(section_body: str) -> list[dict]:
        return [
            {"citation_path": subpart_path, "kind": "subpart",
             "parent_citation_path": "us/regulation/20/416",
             "body": f"Earned income we do not count\n\n{section_body}"},
            {"citation_path": section_path, "kind": "section",
             "parent_citation_path": subpart_path, "body": section_body},
        ]

    base = tmp_path / "corpus"
    _write_scope(base, "old", xml, records(uncaptioned))
    _write_scope(base, "successor", xml, records(captioned))
    releases = tmp_path / "releases"
    releases.mkdir()
    (releases / "r.json").write_text(json.dumps({"name": "r", "scopes": [
        {"jurisdiction": "us", "document_class": "regulation", "version": version}
        for version in ("old", "successor")
    ]}))

    report = audit(base, releases)

    assert [scope["scope"] for scope in report["scopes"]] == ["us/regulation/old"]
    findings = {
        record["citation_path"]: record for record in report["scopes"][0]["records"]
    }
    assert findings[section_path]["missing_caption_lines"] == ["Table 1"]
    assert findings[section_path]["caption_only_change"] is True
    assert findings[subpart_path]["missing_caption_lines"] == ["Table 1"]
    assert findings[subpart_path]["materialized_from"] == [section_path]


def test_deeming_slice_replay_holds_no_captioned_table():
    """Why the pinned part 416 replay baseline needs no versioned behaviour.

    tests/test_repro_us_cfr_416_deeming_slice.py regenerates the 14-path slice
    with the current adapter and checks its hashes. The retained July XML has
    two captions, both outside the slice (416.974 and 416.1112), and container
    bodies join only the slice's own children, so emitting captions leaves
    every replayed byte unchanged.
    """
    from scripts.audit_ecfr_table_captions import captioned_provisions
    from scripts.repro_us_cfr_416_deeming_slice import (
        APPROVED_CITATION_PATHS,
        XML_RELATIVE_PATH,
    )

    root = ET.fromstring((CORPUS_ROOT / XML_RELATIVE_PATH).read_bytes())
    captioned = sorted(captioned_provisions(root, 20))

    assert captioned == ["us/regulation/20/416/1112", "us/regulation/20/416/974"]
    assert not set(captioned) & set(APPROVED_CITATION_PATHS)
