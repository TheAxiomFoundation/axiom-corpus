"""eCFR section and appendix text for the element types the renderer dropped (#942).

Before #942, ``_section_body`` read only P, PSPACE, FP, FP-*, HED (and HD1-HD3 in
appendices), tables, formulas and appendix images; every other element's own text
was dropped. Each fixture under ``tests/fixtures/ecfr_section_text`` is a live eCFR
unit holding one such element type (see its README); each fixture test failed
before the fix.

Invariants checked here, for the fixtures and for generated units:

- Completeness and document order: every text node of a unit reaches the body
  exactly once, in document order, except text under HEAD (the heading field)
  and CITA (the source note), and an XREF's own text (the eCFR's link to a
  pending amendment, correction or delay; a block element inside it renders).
- Only gains: every block the previous renderer produced appears unchanged, in
  the same order, in the new body (a differential against a frozen copy of it).
- Model: the body's blocks equal those of an independent model of the rendering
  rules (paragraphs, headings, notes, worksheets, lists, captions, runs).
- Conservation: remove caption markers, ``|`` separators and whitespace, and a body
  equals the unit's source text in document order, less the same exclusions.
- Agreement: sections and appendices render the same body for content without
  images.
- Caption isolation: image captions never add, remove or change a paragraph anchor.
"""

from __future__ import annotations

import copy
import re
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import axiom_corpus.corpus.ecfr as ecfr
from axiom_corpus.corpus.anchors import generate_anchors_for_provision
from axiom_corpus.corpus.models import ProvisionRecord

FIXTURES = Path(__file__).parent / "fixtures" / "ecfr_section_text"
_EXCLUDED = frozenset({"HEAD", "CITA"})
_INLINE = frozenset({"E", "I", "B", "SU", "SUB", "SUP", "FR", "AC", "BR", "FTREF", "STRONG", "EM"})


def _walk_text(elem: ET.Element, emit) -> None:
    """Call ``emit(node, attribute, excluded)`` for each text and tail in document order.

    Excluded text is text under HEAD or CITA, and an XREF's own text: its text, its
    children's tails and the text of its inline markup. Block elements inside an
    XREF are section text.
    """

    def visit(node: ET.Element, excluded: bool) -> None:
        tag = ecfr._local_name(node.tag)
        excluded = excluded or tag in _EXCLUDED
        link = tag == "XREF"
        if node.text:
            emit(node, "text", excluded or link)
        for child in node:
            visit(child, excluded or (link and ecfr._local_name(child.tag) in _INLINE))
            if child.tail:
                emit(child, "tail", excluded or link)

    visit(elem, False)


# --------------------------------------------------------------------------- #
# The renderer before #942 (main at eeaaecd8f), frozen for the differential.   #
# It shares only helpers this change leaves alone.                             #
# --------------------------------------------------------------------------- #
def _legacy_text_with_breaks(elem: ET.Element) -> str:
    parts: list[str] = []

    def visit(node: ET.Element) -> None:
        if node.text:
            parts.append(node.text)
        for child in node:
            name = ecfr._local_name(child.tag)
            if name == "BR" and parts and parts[-1].endswith("-"):
                visit(child)
            elif name.startswith("FP-") or name in ecfr._WORD_BREAK_TAGS:
                parts.append(" ")
                visit(child)
                parts.append(" ")
            else:
                visit(child)
            if child.tail:
                parts.append(child.tail)

    visit(elem)
    return ecfr._clean_text("".join(parts))


def _legacy_table_text(elem: ET.Element) -> str:
    rows: list[str] = []
    for row in elem.iter():
        if ecfr._local_name(row.tag) != "TR":
            continue
        cells = [
            text
            for cell in row
            if ecfr._local_name(cell.tag) in {"TH", "TD"}
            for text in [_legacy_text_with_breaks(cell)]
            if text
        ]
        if cells:
            rows.append(" | ".join(cells))
    return "\n".join(rows)


def _legacy_table_caption_text(elem: ET.Element) -> str:
    return " ".join(
        text
        for caption in elem
        if ecfr._local_name(caption.tag) == "CAPTION"
        for text in [_legacy_text_with_breaks(caption)]
        if text
    )


def _legacy_section_body(
    elem: ET.Element,
    graphic_transcriptions: Mapping[str, str] | None = None,
    *,
    appendix: bool = False,
) -> str:
    blocks: list[str] = []
    transcriptions = graphic_transcriptions or {}

    def visit(node: ET.Element) -> None:
        for child in node:
            tag = ecfr._local_name(child.tag)
            if tag in {"HEAD", "CITA"}:
                continue
            if tag == "HED" or (appendix and tag in {"HD1", "HD2", "HD3"}):
                text = _legacy_text_with_breaks(child)
                if text:
                    blocks.append(text)
                for identifier in ecfr._non_math_graphic_identifiers(child) if appendix else ():
                    blocks.append(f"[Official source image: ecfr/graphics/{identifier}.png]")
                continue
            if tag in {"P", "PSPACE"} or tag == "FP" or tag.startswith("FP-"):
                text = _legacy_text_with_breaks(child)
                if text:
                    blocks.append(text)
                for identifier in ecfr._non_math_graphic_identifiers(child) if appendix else ():
                    blocks.append(f"[Official source image: ecfr/graphics/{identifier}.png]")
                continue
            if tag == "TABLE":
                caption = _legacy_table_caption_text(child)
                if caption:
                    blocks.append(f"[Table caption: {caption}]")
                text = _legacy_table_text(child)
                if text:
                    blocks.append(text)
                for identifier in ecfr._non_math_graphic_identifiers(child) if appendix else ():
                    blocks.append(f"[Official source image: ecfr/graphics/{identifier}.png]")
                continue
            if tag == "MATH":
                for identifier in ecfr._math_graphic_identifiers(child):
                    transcription = transcriptions.get(identifier)
                    if transcription:
                        blocks.append(
                            f"Formula ({identifier}, verified official image): {transcription}"
                        )
                    else:
                        blocks.append(f"[Official formula image: ecfr/graphics/{identifier}.png]")
                continue
            if appendix and tag == "IMG":
                graphic_identifier = ecfr._graphic_identifier(child.get("src"))
                if graphic_identifier:
                    blocks.append(
                        f"[Official source image: ecfr/graphics/{graphic_identifier}.png]"
                    )
                continue
            visit(child)

    visit(elem)
    return "\n\n".join(blocks)


# --------------------------------------------------------------------------- #
# Shared checks                                                                #
# --------------------------------------------------------------------------- #
_SENTINEL = re.compile("([0-9a-f]+)")


def _sentinel_copy(elem: ET.Element) -> tuple[ET.Element, list[int], set[int]]:
    """Copy ``elem`` with each non-blank text node replaced by a numbered token.

    Returns the copy, the token numbers the body must keep (in document order) and
    those it must leave out (see ``_walk_text``).
    """
    clone = copy.deepcopy(elem)
    kept: list[int] = []
    excluded: set[int] = set()

    def emit(node: ET.Element, attribute: str, excluded_here: bool) -> None:
        text = getattr(node, attribute)
        if not text.strip():
            return
        number = len(kept) + len(excluded)
        if excluded_here:
            excluded.add(number)
        else:
            kept.append(number)
        lead = text[: len(text) - len(text.lstrip())]
        trail = text[len(text.rstrip()):]
        setattr(node, attribute, f"{lead}{number:x}{trail}")

    _walk_text(clone, emit)
    return clone, kept, excluded


def _assert_complete(elem: ET.Element, *, appendix: bool) -> None:
    clone, kept, excluded = _sentinel_copy(elem)
    body = ecfr._section_body(clone, appendix=appendix)
    found = [int(match, 16) for match in _SENTINEL.findall(body)]
    assert not set(found) & excluded, "HEAD, CITA or XREF text reached the body"
    assert found == kept, "a text node is missing, repeated or out of document order"


def _is_subsequence(small: list[str], big: list[str]) -> bool:
    remaining = iter(big)
    return all(any(item == other for other in remaining) for item in small)


def _blocks(body: str) -> list[str]:
    return body.split("\n\n") if body else []


def _assert_only_gains(elem: ET.Element, *, appendix: bool) -> None:
    before = _blocks(_legacy_section_body(elem, appendix=appendix))
    after = _blocks(ecfr._section_body(elem, appendix=appendix))
    assert _is_subsequence(before, after), "a block of the previous body changed or moved"


def _unmark(body: str) -> str:
    return re.sub(r"(?m)^\[(?:Table|Image) caption: (.*)\]$", r"\1", body)


def _source_text(elem: ET.Element) -> str:
    """The unit's section text in document order (see ``_walk_text``)."""
    parts: list[str] = []

    def emit(node: ET.Element, attribute: str, excluded: bool) -> None:
        if not excluded:
            parts.append(getattr(node, attribute))

    _walk_text(elem, emit)
    return "".join(parts)


def _no_ws(text: str) -> str:
    return re.sub(r"\s+", "", text)


def _fixture(name: str) -> ET.Element:
    return ET.parse(FIXTURES / name).getroot()


# --------------------------------------------------------------------------- #
# Live fixtures                                                                #
# --------------------------------------------------------------------------- #
LIVE_UNITS = [
    # Leader-dot worksheets: one "label | figure" line per entry.
    pytest.param(
        "26-cfr-1-661-c-2.xml", False,
        [
            "Dividends | $10,000\nPartially tax-exempt interest | 10,000\n"
            "Fully tax-exempt interest | 10,000\nRents | 20,000\nRental expenses | 2,000\n"
            "Depreciation of rental property | 3,000\nTrustee's commissions | 5,000"
        ],
        id="LDRWK-26-1.661(c)-2",
    ),
    pytest.param(
        "37-cfr-2-7.xml", False,
        [
            "(a) Application fee for recordal of insignia | $20.00\n"
            "(b) Renewal of insignia recordal | $20.00\n"
            "(c) Surcharge for late renewal of insignia recordal | $20.00"
        ],
        id="LDRWK-37-2.7",
    ),
    # Lists: one item per line.
    pytest.param(
        "26-cfr-1-613-2.xml", False,
        [
            "Anorthosite. 2\nAsbestos.\nBauxite.\nBeryl. 3\nCelestite.\nChromite.\nCorundum.\n"
            "Fluorspar.\nGraphite.\nIlmenite.\nKyanite.\nMica.\nOlivine.\n"
            "Quartz crystals (radio grade).\nRutile.\nBlock Steatite talc.\nZircon."
        ],
        id="SCOL2-26-1.613-2",
    ),
    pytest.param(
        "10-cfr-110-28.xml", False, ["Cuba\nIran\nIraq\nNorth Korea\nSyria\nSudan"],
        id="SCOL2-10-110.28",
    ),
    # Paragraph variants.
    pytest.param(
        "26-cfr-1-861-10.xml", False,
        [
            "= $5,000 − [($15,000) multiplied by ($5,000)/($5,000 + $20,000)]",
            "= $2,000",
            "and",
            "= $20,000 − [($15,000) multiplied by ($20,000)/($5,000 + $20,000)]",
            "= $8,000.",
        ],
        id="FP1-2-26-1.861-10",
    ),
    pytest.param(
        "33-cfr-116-50.xml", False, ["Less salvage ____ $____", "____ $____"],
        id="P-2-33-116.50",
    ),
    pytest.param(
        "40-cfr-63-365-excerpt.xml", False,
        [
            "MSCV,n = Theoretical total mass of EtO vented to controls per charge, g (lb)",
            "Mcharge = total mass of sterilizer gas charge, g (lb)",
            "%E.O.w = weight percent of EtO",
        ],
        id="FP2-40-63.365",
    ),
    pytest.param(
        "16-cfr-436-5-excerpt.xml", False,
        [
            "We do not make any representations about a franchisee's future financial "
            "performance or the past financial performance of company-owned or franchised "
            "outlets. We also do not authorize our employees or representatives to make any "
            "such representations either orally or in writing. If you are purchasing an "
            "existing outlet, however, we may provide you with the actual records of that "
            "outlet. If you receive any other financial performance information or "
            "projections of your future income, you should report it to the franchisor's "
            "management by contacting [name, address, and telephone number], the Federal "
            "Trade Commission, and the appropriate state regulatory agencies."
        ],
        id="FP2-2-16-436.5",
    ),
    pytest.param(
        "49-cfr-179-400-9.xml", False,
        [
            "(1) A stiffening ring which meets the requirements of this paragraph, or",
            "(2) A circumferential line of a head at one-third the depth of the head from "
            "the tangent line);",
        ],
        id="FP2-3-49-179.400-9",
    ),
    pytest.param(
        "28-cfr-50-14-excerpt.xml", False,
        [
            "general principles",
            "A. Need for Uniformity—Issuing Agencies",
            "B. Purpose of Guidelines",
            "C. Relation to Prior Guidelines",
        ],
        id="P-3-28-50.14",
    ),
    pytest.param(
        "12-cfr-30-appendix-c.xml", True,
        ["A. Scope", "B. Preservation of Existing Authority"],
        id="P-1-12-30-appendix-C",
    ),
    pytest.param("49-cfr-1248-2.xml", False, ["Number of carloads."], id="P1-49-1248.2"),
    pytest.param(
        "21-cfr-1210-22.xml", False,
        [
            "Product",
            "(State whether raw milk, pasteurized milk, raw cream, or pasteurized cream.)",
            "Permit number",
            "Federal Import Milk Act, Department of Health and Human Services.",
            "Shipper",
            "Address of shipper",
        ],
        id="P2-P-DASH-21-1210.22",
    ),
    pytest.param(
        "29-cfr-301-9.xml", False, ["By Order of_____Division", "Attest:__________", "[Secretary]"],
        id="FRP-29-301.9",
    ),
    pytest.param(
        "46-cfr-42-50-10.xml", False,
        ["(Signature of official issuing the certificate)", "[Seal of issuing", "authority]"],
        id="FRP0-46-42.50-10",
    ),
    # Headings inside sections, as appendices already kept them.
    pytest.param("30-cfr-75-905.xml", False, ["[Statutory Provisions]"], id="HD1-30-75.905"),
    pytest.param("7-cfr-1051-2.xml", False, ["California"], id="HD2-7-1051.2"),
    pytest.param(
        "46-cfr-196-37-47.xml", False,
        ["PORTABLE MAGAZINE CHEST", "— FLAMMABLE —", "KEEP LIGHTS AND FIRE AWAY."],
        id="HD3-46-196.37-47",
    ),
    pytest.param(
        "14-cfr-241-section-18.xml", False,
        ["98 Cumulative Effect of Changes in Accounting Principles."],
        id="HD5-14-241-section-18",
    ),
    pytest.param("43-cfr-3287-4.xml", False, ["Group 3400—Coal Management"], id="HED1-43-3287.4"),
    pytest.param(
        "21-cfr-12-45.xml", False, ["Notice of Participation", "Docket No. ____"],
        id="DOCKETHD-21-12.45",
    ),
    pytest.param(
        "48-cfr-chapter-2-appendix-h.xml", True, ["H-100 Scope.", "H-101 Notification."],
        id="SECHD-48-chapter-2-appendix-H",
    ),
    pytest.param(
        "48-cfr-chapter-2-appendix-f-excerpt.xml", True, ["Part 1—Introduction", "F-101 General."],
        id="PARTHD-48-chapter-2-appendix-F",
    ),
    # Image captions, marked so the anchor scanner skips their labels.
    pytest.param(
        "46-cfr-11-505.xml", False,
        [
            "[Image caption: Figure 11.505(a)—Structure of National Engineer Officer "
            "Endorsements for Non-Seagoing Service]"
        ],
        id="TCAP-46-11.505",
    ),
    pytest.param(
        "29-cfr-2530-210-excerpt.xml", False, ["[Image caption: (i) Comprehensive diagram. (No. 6)]"],
        id="TCAP-29-2530.210",
    ),
    pytest.param(
        "46-cfr-42-13-25.xml", False,
        ["[Image caption: Figure 42.13-25(a)—Load line mark and lines to be used with this mark]"],
        id="BCAP-46-42.13-25",
    ),
    # Codified notes: authority citations, OMB approvals and signature names.
    pytest.param("27-cfr-19-661.xml", False, ["(26 U.S.C. 5181)"], id="SECAUTH-27-19.661"),
    pytest.param(
        "38-cfr-21-7614.xml", False,
        [
            "(Authority: 10 U.S.C. 16136(b), 38 U.S.C. 3691; Pub. L. 98-525, Pub. L. 101-366) "
            "(June 1, 1991)"
        ],
        id="PARAUTH-38-21.7614",
    ),
    pytest.param(
        "7-cfr-800-166.xml", False,
        ["(Approved by the Office of Management and Budget under control number 0580-0011)"],
        id="APPRO-7-800.166",
    ),
    pytest.param(
        "26-cfr-521-101-excerpt.xml", False, ["G. C. Marshall.", "Henrik Kauffman."],
        id="NAME-26-521.101",
    ),
]


@pytest.mark.parametrize("name,appendix,expected", LIVE_UNITS)
def test_live_unit_keeps_its_element_text(name, appendix, expected):
    elem = _fixture(name)

    blocks = _blocks(ecfr._section_body(elem, appendix=appendix))

    for block in expected:
        assert block in blocks
    _assert_complete(elem, appendix=appendix)
    _assert_only_gains(elem, appendix=appendix)


@pytest.mark.parametrize(
    "name,body",
    [
        ("37-cfr-2-7.xml", (
            "(a) Application fee for recordal of insignia | $20.00\n"
            "(b) Renewal of insignia recordal | $20.00\n"
            "(c) Surcharge for late renewal of insignia recordal | $20.00"
        )),
        ("10-cfr-110-28.xml", "Cuba\nIran\nIraq\nNorth Korea\nSyria\nSudan"),
        ("30-cfr-75-905.xml", "[Statutory Provisions]\n\nSingle-phase loads shall be connected phase-to-phase."),
        (
            "46-cfr-196-37-47.xml",
            "(a) Portable magazine chests shall be marked in letters at least 3 inches high:\n\n"
            "PORTABLE MAGAZINE CHEST\n\n— FLAMMABLE —\n\nKEEP LIGHTS AND FIRE AWAY.",
        ),
        (
            "27-cfr-19-661.xml",
            "This subpart covers the establishment and operation of alcohol fuel plants.\n\n"
            "(26 U.S.C. 5181)",
        ),
        (
            "7-cfr-800-166.xml",
            "Official certificates may be photo copied or similarly reproduced.\n\n"
            "(Approved by the Office of Management and Budget under control number 0580-0011)",
        ),
        (
            "46-cfr-11-505.xml",
            "Figure 11.505(a) illustrates the national engineering endorsement structure, "
            "including crossover points.\n\n"
            "[Image caption: Figure 11.505(a)—Structure of National Engineer Officer "
            "Endorsements for Non-Seagoing Service]",
        ),
        # XREF is the eCFR's link to a pending amendment, not section text.
        ("12-cfr-4-92.xml", ""),
    ],
)
def test_live_unit_body(name, body):
    elem = _fixture(name)

    assert ecfr._section_body(elem) == body
    if elem.find(".//img") is None:
        assert ecfr._section_body(elem, appendix=True) == body


def test_xref_amendment_link_stays_out_of_the_body():
    elem = _fixture("12-cfr-4-92.xml")

    assert "Link to an amendment" in "".join(elem.itertext())
    assert ecfr._section_body(elem) == ""
    _assert_complete(elem, appendix=False)


def test_appendix_keeps_image_markers_beside_captions():
    elem = _fixture("46-cfr-11-505.xml")

    assert _blocks(ecfr._section_body(elem, appendix=True))[-2:] == [
        "[Image caption: Figure 11.505(a)—Structure of National Engineer Officer "
        "Endorsements for Non-Seagoing Service]",
        "[Official source image: ecfr/graphics/ER24DE13.004.png]",
    ]


def _anchors(body: str, citation_path: str) -> list[tuple[str, str, str]]:
    provision = ProvisionRecord(
        jurisdiction="us",
        document_class="regulation",
        id="section-elements-fixture",
        citation_path=citation_path,
        body=body,
    )
    return [
        (anchor.citation_path, anchor.label, anchor.text)
        for anchor in generate_anchors_for_provision(provision)
    ]


def _without_caption_blocks(body: str) -> str:
    return "\n\n".join(
        block for block in _blocks(body)
        if not block.startswith(("[Image caption: ", "[Table caption: "))
    )


def _remove_image_captions(elem: ET.Element) -> None:
    for parent in list(elem.iter()):
        for child in list(parent):
            if child.tag in {"TCAP", "BCAP"}:
                parent.remove(child)


def test_labeled_image_caption_adds_no_paragraph_anchor():
    # 29 CFR 2530.210 captions diagram 6 "(i) Comprehensive diagram. (No. 6)" inside
    # paragraph (h)'s example, where a paragraph (i) could follow.
    elem = _fixture("29-cfr-2530-210-excerpt.xml")
    path = "us/regulation/29/2530/210"
    body = ecfr._section_body(elem)
    stripped = copy.deepcopy(elem)
    _remove_image_captions(stripped)

    anchors = _anchors(body, path)

    assert "[Image caption: (i) Comprehensive diagram. (No. 6)]" in _blocks(body)
    assert [anchor_path for anchor_path, _label, _text in anchors] == [f"{path}/h"]
    assert [
        (anchor_path, label, _without_caption_blocks(text))
        for anchor_path, label, text in anchors
    ] == _anchors(ecfr._section_body(stripped), path)


def test_new_block_elements_separate_words_inside_flattened_text():
    # No live section nests these elements inside a paragraph or cell, but a block
    # boundary still separates the words on either side.
    elem = ET.fromstring(
        "<DIV8><P>a<FP1-2>b</FP1-2>c<HD5>d</HD5>e<LDRFIG>f</LDRFIG>g</P>"
        "<TABLE><TR><TD>h<P-2>i</P-2>j</TD></TR></TABLE></DIV8>"
    )

    assert ecfr._section_body(elem) == "a b c d e f g\n\nh i j"


# --------------------------------------------------------------------------- #
# Generated units and a model of the rendering rules                           #
# --------------------------------------------------------------------------- #
_word = st.text(alphabet="abcxyzABC0189§$%.,—–'é-", min_size=1, max_size=6)
_words = st.lists(_word, min_size=1, max_size=3)
_IDS = ["ER01AP04.000", "EC21OC91.038", "ER05AP24.041"]

_PARAGRAPHS = [
    "P", "PSPACE", "FP", "FP-1", "FP-2", "FP-DASH", "FP1", "FP1-2", "FP2", "FP2-2", "FP2-3",
    "P-1", "P-2", "P-3", "P1", "P2", "P-DASH", "FRP", "FRP0",
]
_HEADINGS = ["HED", "HED1", "HD1", "HD2", "HD3", "HD5", "SECHD", "PARTHD", "DOCKETHD"]
_NOTES = ["SECAUTH", "PARAUTH", "APPRO", "NAME"]
_CONTAINERS = ["EXTRACT", "EXAMPLE", "NOTE", "DIV", "BOXTXT"]


def _leaf(images: bool):
    kinds = [
        st.tuples(st.just("text"), st.sampled_from(_PARAGRAPHS + _HEADINGS + _NOTES), _words),
        st.tuples(st.just("caption"), st.sampled_from(["TCAP", "BCAP"]), _words),
        st.tuples(
            st.just("worksheet"), st.none(),
            st.lists(st.tuples(st.sampled_from(["FL-2", "LDRFIG"]), _words), min_size=1, max_size=4),
        ),
        st.tuples(st.just("list"), st.none(), st.lists(_words, min_size=1, max_size=4)),
        st.tuples(
            st.just("table"), st.booleans(),
            st.lists(st.lists(_words, min_size=1, max_size=3), min_size=1, max_size=3),
        ),
        st.tuples(st.just("skip"), st.sampled_from(["CITA", "XREF"]), _words),
        # An XREF's own text stays out; a paragraph inside it renders.
        st.tuples(st.just("xref"), st.none(), st.tuples(_words, _words)),
        st.tuples(st.just("run"), st.sampled_from([None, "E", "SU", "I"]), _words),
        st.tuples(st.just("math"), st.none(), st.sampled_from(_IDS)),
    ]
    if images:
        kinds.append(st.tuples(st.just("img"), st.none(), st.sampled_from(_IDS)))
    return st.one_of(*kinds)


def _units(images: bool):
    return st.recursive(
        st.lists(_leaf(images), max_size=6),
        lambda inner: st.lists(
            st.one_of(_leaf(images), st.tuples(st.just("container"), st.sampled_from(_CONTAINERS), inner)),
            max_size=5,
        ),
        max_leaves=20,
    )


def _build(items, parent: ET.Element, last: ET.Element | None = None) -> None:
    """Append items to ``parent``; a run's text becomes the parent's text or a tail."""

    def add_text(text: str) -> None:
        if last is None:
            parent.text = (parent.text or "") + text
        else:
            last.tail = (last.tail or "") + text

    for kind, tag, content in items:
        if kind == "run":
            if tag is None:
                add_text(" " + " ".join(content) + " ")
                continue
            child = ET.SubElement(parent, tag)
            child.text = " ".join(content)
            child.tail = " "
            add_text(" ")
        elif kind in {"text", "caption", "skip"}:
            child = ET.SubElement(parent, tag)
            child.text = " ".join(content)
        elif kind == "xref":
            child = ET.SubElement(parent, "XREF")
            child.text = " ".join(content[0])
            ET.SubElement(child, "P").text = " ".join(content[1])
        elif kind == "worksheet":
            child = ET.SubElement(parent, "LDRWK")
            for item_tag, words in content:
                ET.SubElement(child, item_tag).text = " ".join(words)
        elif kind == "list":
            child = ET.SubElement(parent, "SCOL2")
            for words in content:
                ET.SubElement(child, "LI").text = " ".join(words)
        elif kind == "table":
            child = ET.SubElement(parent, "TABLE")
            if tag:
                ET.SubElement(ET.SubElement(child, "CAPTION"), "P").text = "caption"
            for row in content:
                tr = ET.SubElement(child, "TR")
                for words in row:
                    ET.SubElement(tr, "TD").text = " ".join(words)
        elif kind == "math":
            child = ET.SubElement(parent, "MATH")
            ET.SubElement(child, "img", src=f"/graphics/{content.lower()}.gif")
        elif kind == "img":
            child = ET.SubElement(parent, "img", src=f"/graphics/{content.lower()}.gif")
        else:  # container
            child = ET.SubElement(parent, tag)
            _build(content, child)
        last = child


def _unit_xml(items) -> ET.Element:
    root = ET.Element("DIV8", N="§ 1.1", TYPE="SECTION")
    head = ET.SubElement(root, "HEAD")
    head.text = "§ 1.1 HEADWORD heading."
    _build(items, root, last=head)
    return root


def _model_blocks(items, *, appendix: bool) -> list[str]:
    """The rendering rules, written independently of the renderer."""
    blocks: list[str] = []
    run: list[str] = []

    def flush() -> None:
        if run:
            blocks.append(" ".join(run))
            run.clear()

    def visit(entries) -> None:
        for kind, tag, content in entries:
            if kind == "run":
                run.extend(content)
                continue
            flush()
            if kind == "text":
                blocks.append(" ".join(content))
            elif kind == "caption":
                blocks.append(f"[Image caption: {' '.join(content)}]")
            elif kind == "xref":
                blocks.append(" ".join(content[1]))
            elif kind == "worksheet":
                lines: list[list[str]] = []
                for item_tag, words in content:
                    if item_tag == "LDRFIG" and lines:
                        lines[-1].append(" ".join(words))
                    else:
                        lines.append([" ".join(words)])
                blocks.append("\n".join(" | ".join(cells) for cells in lines))
            elif kind == "list":
                blocks.append("\n".join(" ".join(words) for words in content))
            elif kind == "table":
                if tag:
                    blocks.append("[Table caption: caption]")
                blocks.append("\n".join(" | ".join(" ".join(w) for w in row) for row in content))
            elif kind == "math":
                blocks.append(f"[Official formula image: ecfr/graphics/{content}.png]")
            elif kind == "img":
                if appendix:
                    blocks.append(f"[Official source image: ecfr/graphics/{content}.png]")
            elif kind == "container":
                visit(content)
                flush()
            # "skip": HEAD, CITA and XREF render nothing but still end a run.

    visit(items)
    flush()
    return blocks


@pytest.mark.parametrize("appendix", [False, True])
@settings(max_examples=300, deadline=None)
@given(items=_units(images=True))
def test_generated_units_follow_the_block_model(items, appendix):
    elem = _unit_xml(items)

    body = ecfr._section_body(elem, appendix=appendix)

    assert _blocks(body) == _model_blocks(items, appendix=appendix)
    assert "HEADWORD" not in body


@pytest.mark.parametrize("appendix", [False, True])
@settings(max_examples=300, deadline=None)
@given(items=_units(images=True))
def test_generated_units_keep_every_text_node_in_order(items, appendix):
    elem = _unit_xml(items)

    _assert_complete(elem, appendix=appendix)
    body = re.sub(
        r"(?m)^\[Official (?:formula|source) image: [^\]]*\]$",
        "",
        ecfr._section_body(elem, appendix=appendix),
    )
    assert _no_ws(_unmark(body)).replace("|", "") == _no_ws(_source_text(elem))


@pytest.mark.parametrize("appendix", [False, True])
@settings(max_examples=300, deadline=None)
@given(items=_units(images=True))
def test_generated_units_only_gain_text(items, appendix):
    elem = _unit_xml(items)

    _assert_only_gains(elem, appendix=appendix)


@settings(max_examples=300, deadline=None)
@given(items=_units(images=False))
def test_sections_and_appendices_agree_without_images(items):
    elem = _unit_xml(items)

    assert ecfr._section_body(elem) == ecfr._section_body(elem, appendix=True)


_label = st.sampled_from(["a", "b", "h", "i", "ii", "1", "2", "A", "B"])
_caption_text = st.tuples(
    _label,
    st.sampled_from([" Comprehensive diagram. (No. 6)", " Figure", " Text—(1) part", " Text: (A) part"]),
).map(lambda pair: f"({pair[0]}){pair[1]}")


@pytest.mark.parametrize("appendix", [False, True])
@settings(max_examples=150, deadline=None)
@given(
    captions=st.lists(st.tuples(st.sampled_from(["TCAP", "BCAP"]), _caption_text), min_size=1, max_size=4),
)
def test_labeled_image_captions_preserve_paragraph_anchors(captions, appendix):
    figures = "".join(
        (
            f'<TCAP>{caption}</TCAP><img src="/graphics/er01ap04.00{index}.gif"/>'
            if tag == "TCAP"
            else f'<img src="/graphics/er01ap04.00{index}.gif"/><BCAP>{caption}</BCAP>'
        )
        for index, (tag, caption) in enumerate(captions)
    )
    elem = ET.fromstring(
        "<DIV8><P>(a) Computation—(1) First paragraph.</P>"
        f"<P>(h) Example.</P>{figures}<P>(2) Second paragraph.</P><P>(b) Next paragraph.</P></DIV8>"
    )
    path = "us/regulation/29/2530/210"
    body = ecfr._section_body(elem, appendix=appendix)
    stripped = copy.deepcopy(elem)
    _remove_image_captions(stripped)

    assert [
        (anchor_path, label, _without_caption_blocks(text))
        for anchor_path, label, text in _anchors(body, path)
    ] == _anchors(ecfr._section_body(stripped, appendix=appendix), path)
