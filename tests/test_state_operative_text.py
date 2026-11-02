"""Operative text must survive source-first Maine and Ohio section parsing.

The source-token oracle deliberately excludes Maine section headings, revisor
notes, section histories, status blips, and amendment histories wherever they
occur. Substantive headnotes, paragraph labels, and inline references are
operative text. Ohio excludes navigation and its notice/metadata containers.
Both adapters exclude non-rendered subtrees, hidden elements, and every
BeautifulSoup special string type.
Equality means normalized token equality: both adapters collapse whitespace;
Maine also maps non-breaking hyphens and en dashes to ASCII hyphens, and em
dashes to two ASCII hyphens. Ohio preserves those punctuation characters.
"""

from pathlib import Path

import pytest
from bs4 import BeautifulSoup, NavigableString, Tag

from axiom_corpus.corpus.state_adapters.maine import parse_maine_section
from axiom_corpus.corpus.states import _ohio_laws_body_text

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "state_text"
SAMPLE_SECTION_HTML = (FIXTURE_DIR / "legacy-maine-subsection.html").read_text(encoding="utf-8")
SAMPLE_UNSUBDIVIDED_SECTION_HTML = (FIXTURE_DIR / "legacy-maine-unsubdivided.html").read_text(
    encoding="utf-8"
)
SAMPLE_OHIO_CHAPTER = (FIXTURE_DIR / "legacy-ohio-chapter.html").read_text(encoding="utf-8")


def _normalized_tokens(value: str, jurisdiction: str) -> list[str]:
    """Apply the documented normalization without calling an adapter cleaner."""
    if jurisdiction == "maine":
        value = value.translate({0x00A0: " ", 0x2011: "-", 0x2013: "-", 0x2014: "--"})
    return value.split()


def _operative_tokens(html: str, jurisdiction: str) -> list[str]:
    """Read the source DOM independently of either adapter's paragraph selection."""
    soup = BeautifulSoup(html, "lxml")
    root = soup.select_one(".MRSSection" if jurisdiction == "maine" else ".laws-body")
    assert isinstance(root, Tag)
    tokens: list[str] = []
    excluded = {"heading_section", "note", "qhistory", "headnote_blip", "bhistory"}
    nonrendered = {"template", "script", "style", "noscript", "head", "iframe", "object"}
    for node in root.descendants:
        if type(node) is not NavigableString:
            continue
        ancestors = [parent for parent in node.parents if isinstance(parent, Tag)]
        if any(
            parent.name in nonrendered
            or parent.has_attr("hidden")
            or str(parent.get("aria-hidden", "")).strip().lower() == "true"
            for parent in ancestors
        ):
            continue
        if jurisdiction == "maine":
            if any(excluded.intersection(parent.get("class", [])) for parent in ancestors):
                continue
        elif any(
            parent.name == "nav"
            or parent.get("role") == "navigation"
            or {
                "laws-notice",
                "laws-section-info",
                "laws-section-info-module",
                "content-head-text",
            }.intersection(parent.get("class", []))
            for parent in ancestors
        ):
            continue
        tokens.extend(_normalized_tokens(str(node), jurisdiction))
    return tokens


def _extracted_body(html: str, jurisdiction: str) -> str:
    if jurisdiction == "maine":
        body = parse_maine_section(html).body
    else:
        root = BeautifulSoup(html, "lxml").select_one(".laws-body")
        assert isinstance(root, Tag)
        body = _ohio_laws_body_text(root)
    assert body is not None
    return body


@pytest.mark.parametrize(
    ("jurisdiction", "dash", "normalized"),
    [
        ("maine", "\u2011", "-"),
        ("maine", "\u2013", "-"),
        ("maine", "\u2014", "--"),
        ("ohio", "\u2011", "\u2011"),
        ("ohio", "\u2013", "\u2013"),
        ("ohio", "\u2014", "\u2014"),
    ],
)
def test_operative_token_oracle_applies_each_adapter_normalization(
    jurisdiction: str, dash: str, normalized: str
):
    text = f"Tax\u00a0credit{dash}limit."
    if jurisdiction == "maine":
        html = f'<div class="MRSSection"><div class="mrs-text">{text}</div></div>'
    else:
        html = f'<section class="laws-body"><p>{text}</p></section>'
    expected = f"Tax credit{normalized}limit."

    assert _operative_tokens(html, jurisdiction) == expected.split()
    assert _extracted_body(html, jurisdiction) == expected


@pytest.mark.parametrize("section", ["5111", "5124-C", "5126-A", "5213-A"])
def test_maine_official_excerpt_keeps_every_operative_text_node_in_order(section: str):
    html = (FIXTURE_DIR / f"maine-{section}.html").read_text(encoding="utf-8")

    # Normalized token equality proves every operative token survives in source order,
    # including nested amounts, labels, introductory text, and inline references.
    assert _extracted_body(html, "maine").split() == _operative_tokens(html, "maine")


def test_ohio_official_rate_schedule_keeps_header_rows_and_every_sentence_in_order():
    html = (FIXTURE_DIR / "ohio-5747.02.html").read_text(encoding="utf-8")
    body = _extracted_body(html, "ohio")
    soup = BeautifulSoup(html, "lxml")
    expected_rows = [" ".join(row.get_text(" ", strip=True).split()) for row in soup.select("tr")]

    assert body.split() == _operative_tokens(html, "ohio")
    # A row stays on one line, including the header; cells retain source order.
    assert [line for line in body.splitlines() if line in expected_rows] == expected_rows
    assert "2024" in body and "2025" in body and "2026" in body
    assert "$360.69 plus 2.75%" in body
    assert "$342.00 plus 2.75%" in body
    assert "$2,394.32 plus 3.5%" in body
    assert "$2,394.32 plus 3.125%" in body


def test_maine_nested_subsections_direct_text_and_fallback_are_retained_once():
    html = """
    <div class="MRSSection">
      <h3 class="heading_section">§1. Example</h3>
      Opening operative sentence.
      <div class="MRSSubSection">
        <span class="headnote">1. Operative headnote.</span> Fallback sentence.
        <p>Nested fallback <a href="../36/title36sec5102.html">reference</a> sentence.</p>
      </div>
      Interleaved operative sentence.
      <div class="MRSSubSection">
        <div class="mrs-text">2. First paragraph.</div>
        <div class="MRSSubSection"><div class="mrs-text">Nested subsection sentence.</div></div>
        <div class="mrs-text">Final paragraph.</div>
      </div>
      Closing operative sentence.
    </div>
    """

    assert _extracted_body(html, "maine").split() == _operative_tokens(html, "maine")


def test_operative_headnotes_and_references_survive_editorial_exclusions():
    html = """
    <div class="MRSSection">
      <h3 class="heading_section">§1. Heading metadata</h3>
      <div class="mrs-text"><span class="headnote">1. Substantive headnote.</span>
        Tax is allowed under <a href="../36/title36sec5102.html">section 5102</a>.
        <span class="bhistory">Embedded legacy history.</span>
      </div>
      <span class="bhistory">External amendment metadata.</span>
      <div class="note">Revisor editorial metadata.</div>
      <div class="qhistory">SECTION HISTORY Historical metadata.</div>
      <div class="headnote_blip">Status metadata.</div>
      <script>Hidden script metadata.</script><style>Hidden style metadata.</style>
      <!-- Hidden comment metadata. -->
    </div>
    """
    body = _extracted_body(html, "maine")

    assert body.split() == _operative_tokens(html, "maine")
    assert "Substantive headnote." in body
    assert "section 5102" in body
    assert "Embedded legacy history." not in body
    assert "metadata" not in body
    assert parse_maine_section(html).source_history == (
        "Embedded legacy history.",
        "Historical metadata.",
    )


def test_ohio_mixed_wrappers_direct_text_and_notice_are_handled_in_order():
    html = """
    <section class="laws-body">
      Opening operative text.
      <span><p>First <a href="/ohio-revised-code/section-5747.025">inline reference</a>.</p></span>
      <span>Second sibling <em>inline text</em><br>following a break.</span>
      <div>Interleaved wrapper text.<table><tr><th>Income</th><th>Tax</th></tr>
        <tr><td><p>$100</p></td><td><span>2%</span><br>plus $1</td></tr>
      </table>Closing wrapper text.</div>
      <div class="laws-notice"><p>Last updated editorial metadata.</p></div>
      <script>Hidden script metadata.</script><style>Hidden style metadata.</style>
      <!-- Hidden comment metadata. -->
    </section>
    """
    body = _extracted_body(html, "ohio")

    assert body.split() == _operative_tokens(html, "ohio")
    assert "Income Tax" in body.splitlines()
    assert "$100 2% plus $1" in body.splitlines()
    assert "metadata" not in body


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        (
            SAMPLE_SECTION_HTML,
            "1. Resident taxpayer. A resident is allowed a credit under section 5102 .",
        ),
        (
            SAMPLE_UNSUBDIVIDED_SECTION_HTML,
            "The State Tax Assessor may establish procedures permitting payment of taxes "
            "by the use of credit cards.",
        ),
    ],
)
def test_maine_existing_simple_fixture_body_is_byte_identical(html: str, expected: str):
    assert _extracted_body(html, "maine").encode() == expected.encode()


def test_ohio_existing_simple_fixture_bodies_are_byte_identical():
    roots = BeautifulSoup(SAMPLE_OHIO_CHAPTER, "lxml").select(".laws-body")
    expected = [
        "As used in this chapter:\n"
        '(A) "Medicaid managed care organization" has the same meaning as in section '
        "5167.01 of the Revised Code.",
        "References are deemed to refer to the department of medicaid.",
    ]

    assert [_ohio_laws_body_text(root) for root in roots] == expected


def test_maine_complete_nested_paragraph_keeps_legacy_bytes():
    html = """
    <div class="MRSSection"><div class="MRSSubSection">
      <div class="mrs-text">Introduction.
        <div class="mrs-text"><span>A.</span> Nested operative sentence.</div>
        Closing sentence.
      </div>
    </div></div>
    """

    assert _extracted_body(html, "maine") == (
        "Introduction. A. Nested operative sentence. Closing sentence."
    )


def test_maine_fallback_subsection_keeps_embedded_legacy_history_bytes():
    html = """
    <div class="MRSSection"><div class="MRSSubSection">
      Fallback operative sentence.
      <span class="bhistory">[PL 2020, c. 1 (NEW).]</span>
    </div><span class="bhistory">External history metadata.</span></div>
    """
    parsed = parse_maine_section(html)

    assert parsed.body == "Fallback operative sentence."
    assert parsed.source_history == ("[PL 2020, c. 1 (NEW).]",)
    assert _extracted_body(html, "maine").split() == _operative_tokens(html, "maine")
