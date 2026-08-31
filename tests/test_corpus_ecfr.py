import json
from datetime import date
from hashlib import sha256
from pathlib import Path
from urllib.error import HTTPError

import pytest

from axiom_corpus.corpus.artifacts import CorpusArtifactStore, sha256_bytes
from axiom_corpus.corpus.cli import build_parser
from axiom_corpus.corpus.ecfr import (
    EcfrGraphicTranscription,
    EcfrPartTarget,
    build_ecfr_inventory,
    build_ecfr_inventory_from_structures,
    extract_ecfr,
    iter_ecfr_title_provisions,
    load_ecfr_graphic_transcriptions,
    part_targets_from_structure,
)
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.models import ProvisionRecord

SAMPLE_STRUCTURE = {
    "identifier": "7",
    "label": "Title 7-Agriculture",
    "type": "title",
    "children": [
        {
            "identifier": "II",
            "label": "Chapter II-Food and Nutrition Service",
            "type": "chapter",
            "children": [
                {
                    "identifier": "C",
                    "label": "Subchapter C-Food Stamp Program",
                    "type": "subchapter",
                    "children": [
                        {
                            "identifier": "273",
                            "label": "Part 273-Certification of Eligible Households",
                            "type": "part",
                            "children": [
                                {
                                    "identifier": "273.1",
                                    "label": "§ 273.1 Household concept.",
                                    "label_description": "Household concept.",
                                    "type": "section",
                                },
                                {
                                    "identifier": "273.2",
                                    "label": "§ 273.2 Application processing.",
                                    "label_description": "Application processing.",
                                    "type": "section",
                                },
                            ],
                        }
                    ],
                }
            ],
        }
    ],
}

SAMPLE_SUBPART_STRUCTURE = {
    "identifier": "7",
    "label": "Title 7-Agriculture",
    "type": "title",
    "children": [
        {
            "identifier": "273",
            "label": "Part 273-Certification of Eligible Households",
            "type": "part",
            "children": [
                {
                    "identifier": "A",
                    "label": "Subpart A-General",
                    "type": "subpart",
                    "children": [
                        {
                            "identifier": "273.1",
                            "label": "§ 273.1 Household concept.",
                            "label_description": "Household concept.",
                            "type": "section",
                        }
                    ],
                }
            ],
        }
    ],
}

SAMPLE_APPENDIX_STRUCTURE = {
    "identifier": "45",
    "label": "Title 45-Public Welfare",
    "type": "title",
    "children": [
        {
            "identifier": "VI",
            "label": "Chapter VI-National Science Foundation",
            "type": "chapter",
            "children": [
                {
                    "identifier": "604",
                    "label": "Part 604-New Restrictions on Lobbying",
                    "type": "part",
                    "children": [
                        {
                            "identifier": "604.100",
                            "label": "§ 604.100 Conditions on use of funds.",
                            "label_description": "Conditions on use of funds.",
                            "type": "section",
                        },
                        {
                            "identifier": "Appendix A to Part 604",
                            "label": (
                                "Appendix A to Part 604-Certification Regarding "
                                "Lobbying"
                            ),
                            "type": "appendix",
                        },
                        {
                            "identifier": "Appendix B to Part 604",
                            "label": "Appendix B to Part 604-Disclosure Form",
                            "type": "appendix",
                        },
                    ],
                }
            ],
        }
    ],
}

SAMPLE_TITLE_XML = """
<ECFR>
  <DIV5 N="273" TYPE="PART">
    <HEAD>PART 273-CERTIFICATION OF ELIGIBLE HOUSEHOLDS</HEAD>
    <DIV8 N="§ 273.1" TYPE="SECTION" NODE="7:4.1.1.2.1.1.1.1">
      <HEAD>§ 273.1 Household concept.</HEAD>
      <P>(a) General household definition.</P>
      <P>(b) Special households.</P>
    </DIV8>
    <DIV8 N="§ 273.2" TYPE="SECTION" NODE="7:4.1.1.2.1.1.1.2">
      <HEAD>§ 273.2 Application processing.</HEAD>
      <P>(a) Application filing.</P>
    </DIV8>
  </DIV5>
</ECFR>
"""

SAMPLE_TITLE_WITH_TABLE_XML = """
<ECFR>
  <DIV5 N="275" TYPE="PART">
    <HEAD>PART 275-PERFORMANCE REPORTING SYSTEM</HEAD>
    <DIV8 N="§ 275.3" TYPE="SECTION" NODE="7:4.1.1.2.3.1.1.3">
      <HEAD>§ 275.3 Federal monitoring.</HEAD>
      <P>(A) The Federal review sample is determined as follows:</P>
      <DIV width="100%">
        <DIV class="gpotbl_div">
          <TABLE class="gpo_table">
            <THEAD>
              <TR>
                <TH>Average monthly reviewable caseload (N)</TH>
                <TH>Federal subsample target (n′)</TH>
              </TR>
            </THEAD>
            <TBODY>
              <TR>
                <TD>31,489 and over</TD>
                <TD>n′ = 400</TD>
              </TR>
              <TR>
                <TD>10,001 to 31,488</TD>
                <TD>n′ = .011634 N + 33.66</TD>
              </TR>
            </TBODY>
          </TABLE>
        </DIV>
      </DIV>
      <P>(B) The next paragraph remains after the table.</P>
    </DIV8>
  </DIV5>
</ECFR>
"""

SAMPLE_TITLE_WITH_GRAPHICS_XML = """
<ECFR>
  <DIV5 N="273" TYPE="PART">
    <HEAD>PART 273-CERTIFICATION OF ELIGIBLE HOUSEHOLDS</HEAD>
    <DIV8 N="§ 273.1" TYPE="SECTION" NODE="7:4.1.1.2.1.1.1.1">
      <HEAD>§ 273.1 Household concept.</HEAD>
      <P>(a) The formula follows.</P>
      <MATH><img src="/graphics/ER07OC94.022.gif"/></MATH>
      <FP>This flush paragraph remains operative.</FP>
      <FP-1>This numbered flush paragraph also remains operative.</FP-1>
    </DIV8>
    <DIV8 N="§ 273.2" TYPE="SECTION" NODE="7:4.1.1.2.1.1.1.2">
      <HEAD>§ 273.2 Application processing.</HEAD>
      <P>(a) Application filing.</P>
    </DIV8>
  </DIV5>
</ECFR>
"""

SAMPLE_TITLE_WITH_HED_XML = """
<ECFR>
  <DIV5 N="273" TYPE="PART">
    <HEAD>PART 273-CERTIFICATION OF ELIGIBLE HOUSEHOLDS</HEAD>
    <DIV8 N="§ 273.1" TYPE="SECTION" NODE="7:4.1.1.2.1.1.1.1">
      <HEAD>§ 273.1 Household concept.</HEAD>
      <P>(a) Operative paragraph.</P>
      <NOTE>
        <HED>Note:</HED>
        <P>This is the official note.</P>
      </NOTE>
      <EXAMPLE>
        <HED>Example 1.</HED>
        <P>First official example.</P>
      </EXAMPLE>
      <EXAMPLE>
        <HED>Example 2.</HED>
        <P>Second official example.</P>
      </EXAMPLE>
    </DIV8>
    <DIV8 N="§ 273.2" TYPE="SECTION" NODE="7:4.1.1.2.1.1.1.2">
      <HEAD>§ 273.2 Application processing.</HEAD>
      <P>(a) An unselected section.</P>
      <MATH><img src="/graphics/ER07OC94.022.gif"/></MATH>
    </DIV8>
  </DIV5>
</ECFR>
"""

SAMPLE_SUBPART_XML = """
<ECFR>
  <DIV5 N="273" TYPE="PART">
    <HEAD>PART 273-CERTIFICATION OF ELIGIBLE HOUSEHOLDS</HEAD>
    <DIV6 N="A" TYPE="SUBPART">
      <HEAD>Subpart A-General</HEAD>
      <DIV8 N="§ 273.1" TYPE="SECTION" NODE="7:4.1.1.2.1.1.1.1">
        <HEAD>§ 273.1 Household concept.</HEAD>
        <P>(a) General household definition.</P>
      </DIV8>
    </DIV6>
  </DIV5>
</ECFR>
"""

SAMPLE_INTERLEAVED_PART_XML = """
<ECFR>
  <DIV5 N="273" TYPE="PART">
    <HEAD>PART 273-CERTIFICATION OF ELIGIBLE HOUSEHOLDS</HEAD>
    <DIV8 N="§ 273.1" TYPE="SECTION" NODE="7:4.1.1.2.1.0.1.1">
      <HEAD>§ 273.1 Household concept.</HEAD>
      <P>(a) General household definition.</P>
    </DIV8>
    <DIV6 N="A" TYPE="SUBPART">
      <HEAD>Subpart A-General</HEAD>
      <DIV8 N="§ 273.2" TYPE="SECTION" NODE="7:4.1.1.2.1.1.1.2">
        <HEAD>§ 273.2 Office operations.</HEAD>
        <P>(a) Application processing.</P>
      </DIV8>
    </DIV6>
    <DIV8 N="§ 273.90" TYPE="SECTION" NODE="7:4.1.1.2.1.0.1.90">
      <HEAD>§ 273.90 Trailing direct section.</HEAD>
      <P>(a) Direct section that follows a formal subpart.</P>
    </DIV8>
  </DIV5>
</ECFR>
"""

SAMPLE_APPENDIX_XML = """
<ECFR>
  <DIV5 N="604" TYPE="PART">
    <HEAD>PART 604-NEW RESTRICTIONS ON LOBBYING</HEAD>
    <DIV8 N="§ 604.100" TYPE="SECTION" NODE="45:3.1.1.2.40.1.1.1">
      <HEAD>§ 604.100 Conditions on use of funds.</HEAD>
      <P>(a) No appropriated funds may be used for covered lobbying.</P>
    </DIV8>
    <DIV9 N="Appendix A to Part 604" TYPE="APPENDIX" NODE="45:3.1.1.2.40.1.3">
      <HEAD>Appendix A to Part 604-Certification Regarding Lobbying</HEAD>
      <HD2>Certification for Contracts, Grants, Loans, and Cooperative Agreements</HD2>
      <P>The undersigned certifies, to the best of his or her knowledge and belief.</P>
      <FP>(3) The undersigned shall require that the language of this certification be included in all subcontracts.</FP>
    </DIV9>
    <DIV9 N="Appendix B to Part 604" TYPE="APPENDIX" NODE="45:3.1.1.2.40.1.4">
      <HEAD>Appendix B to Part 604-Disclosure Form</HEAD>
      <FP><IMG src="/graphics/EC01JA91.007.gif"/></FP>
      <FP><IMG src="/graphics/EC01JA91.008.gif"/></FP>
      <FP><IMG src="/graphics/EC01JA91.009.gif"/></FP>
    </DIV9>
  </DIV5>
</ECFR>
"""

OFFICIAL_TITLE_45_PART_1302_XML = (
    Path(__file__).parents[1]
    / "data/corpus/sources/us/regulation/"
    "2026-06-24-title-45-part-1302/ecfr/title-45-part-1302.xml"
)
OFFICIAL_TITLE_45_PART_1302_SHA256 = (
    "1dc1b061cbb4b7ebb342b374ad58fdf6c66f118a39299b0e08b3bdb0e225e4b2"
)


def test_part_targets_from_structure_preserve_ancestry():
    targets = part_targets_from_structure(SAMPLE_STRUCTURE)

    assert targets == (
        EcfrPartTarget(
            title=7,
            part="273",
            chapter="II",
            subchapter="C",
            label="Part 273-Certification of Eligible Households",
        ),
    )


def test_build_ecfr_inventory_from_structure_sections():
    inventory = build_ecfr_inventory_from_structures((SAMPLE_STRUCTURE,))

    assert inventory.title_count == 1
    assert inventory.part_count == 1
    assert [item.citation_path for item in inventory.items] == [
        "us/regulation/7/273",
        "us/regulation/7/273/1",
        "us/regulation/7/273/2",
    ]
    assert inventory.items[0].source_format == "ecfr-xml"
    assert inventory.items[0].metadata["kind"] == "part"


def test_build_ecfr_inventory_from_structure_includes_subparts():
    inventory = build_ecfr_inventory_from_structures(
        (SAMPLE_SUBPART_STRUCTURE,),
        run_id="2026-04-29-title-7-part-273",
        only_part="273",
        source_sha256_by_title={7: "abc123"},
    )

    assert [item.citation_path for item in inventory.items] == [
        "us/regulation/7/273",
        "us/regulation/7/273/subpart-A",
        "us/regulation/7/273/1",
    ]
    assert inventory.items[0].source_path == (
        "sources/us/regulation/2026-04-29-title-7-part-273/ecfr/title-7-part-273.xml"
    )
    assert inventory.items[0].sha256 == "abc123"


def test_build_ecfr_inventory_from_structure_includes_appendices():
    inventory = build_ecfr_inventory_from_structures(
        (SAMPLE_APPENDIX_STRUCTURE,),
        run_id="2026-08-30-title-45-part-604",
        only_part="604",
    )

    assert [item.citation_path for item in inventory.items] == [
        "us/regulation/45/604",
        "us/regulation/45/604/100",
        "us/regulation/45/604/appendix-a",
        "us/regulation/45/604/appendix-b",
    ]
    appendix = inventory.items[2]
    assert appendix.metadata["kind"] == "appendix"
    assert appendix.metadata["parent_citation_path"] == "us/regulation/45/604"
    assert appendix.metadata["heading"] == "Certification Regarding Lobbying"
    assert appendix.source_url.endswith(
        "/appendix-Appendix%20A%20to%20Part%20604"
    )


def test_build_ecfr_inventory_fails_closed_for_unsupported_appendix_shape():
    unsupported = {
        **SAMPLE_APPENDIX_STRUCTURE,
        "children": [
            {
                **SAMPLE_APPENDIX_STRUCTURE["children"][0],
                "children": [
                    {
                        **SAMPLE_APPENDIX_STRUCTURE["children"][0]["children"][0],
                        "children": [
                            {
                                "identifier": "Appendix to Subpart A of Part 604",
                                "label": "Appendix to Subpart A of Part 604",
                                "type": "appendix",
                            }
                        ],
                    }
                ],
            }
        ],
    }

    with pytest.raises(
        ValueError,
        match="unsupported nonreserved eCFR appendix identifier",
    ):
        build_ecfr_inventory_from_structures((unsupported,), only_part="604")


def test_iter_ecfr_title_provisions_fails_closed_for_unsupported_appendix_xml():
    unsupported_xml = SAMPLE_APPENDIX_XML.replace(
        "Appendix A to Part 604",
        "Appendix II to Part 604",
    )

    with pytest.raises(
        ValueError,
        match="unsupported nonreserved eCFR appendix XML identifier",
    ):
        tuple(
            iter_ecfr_title_provisions(
                unsupported_xml,
                (EcfrPartTarget(title=45, part="604", chapter="VI"),),
                version="2026-08-30-title-45-part-604",
                source_path="ecfr/title-45-part-604.xml",
            )
        )


def test_build_ecfr_inventory_filters_exact_section_with_ancestors():
    inventory = build_ecfr_inventory_from_structures(
        (SAMPLE_STRUCTURE,),
        only_part="273",
        only_sections=("273.2",),
    )

    assert inventory.part_count == 1
    assert [item.citation_path for item in inventory.items] == [
        "us/regulation/7/273",
        "us/regulation/7/273/2",
    ]


def test_build_ecfr_inventory_section_filter_preserves_subpart_ancestor():
    inventory = build_ecfr_inventory_from_structures(
        (SAMPLE_SUBPART_STRUCTURE,),
        only_sections=("273.1",),
    )

    assert [item.citation_path for item in inventory.items] == [
        "us/regulation/7/273",
        "us/regulation/7/273/subpart-A",
        "us/regulation/7/273/1",
    ]


@pytest.mark.parametrize("selector", ["273", "273.", "not a section"])
def test_build_ecfr_inventory_rejects_invalid_section_selector(selector):
    with pytest.raises(ValueError, match="invalid eCFR section selector"):
        build_ecfr_inventory_from_structures(
            (SAMPLE_STRUCTURE,),
            only_sections=(selector,),
        )


def test_build_ecfr_inventory_rejects_unmatched_section_selector():
    with pytest.raises(ValueError, match="not found: 273.999"):
        build_ecfr_inventory_from_structures(
            (SAMPLE_STRUCTURE,),
            only_sections=("273.999",),
        )


def test_build_ecfr_inventory_rejects_section_filter_with_limit():
    with pytest.raises(ValueError, match="cannot be combined with limit"):
        build_ecfr_inventory_from_structures(
            (SAMPLE_STRUCTURE,),
            only_sections=("273.1",),
            limit=2,
        )


def test_build_ecfr_inventory_requires_title_for_section_filter():
    with pytest.raises(ValueError, match="requires only_title"):
        build_ecfr_inventory(
            as_of="2024-04-16",
            only_sections=("273.1",),
        )


def test_iter_ecfr_title_provisions_builds_normalized_records():
    records = tuple(
        iter_ecfr_title_provisions(
            SAMPLE_TITLE_XML,
            (EcfrPartTarget(title=7, part="273", chapter="II", subchapter="C"),),
            version="2026-04-29",
            source_path="ecfr/title-7.xml",
        )
    )

    assert [record.citation_path for record in records] == [
        "us/regulation/7/273",
        "us/regulation/7/273/1",
        "us/regulation/7/273/2",
    ]
    assert records[0].kind == "part"
    assert records[0].body is None
    assert records[1].document_class == "regulation"
    assert records[1].heading == "Household concept"
    assert records[1].parent_citation_path == "us/regulation/7/273"
    assert records[1].level == 1
    assert "General household" in records[1].body


def test_iter_ecfr_title_provisions_preserves_table_rows():
    records = tuple(
        iter_ecfr_title_provisions(
            SAMPLE_TITLE_WITH_TABLE_XML,
            (EcfrPartTarget(title=7, part="275", chapter="II", subchapter="C"),),
            version="2026-06-15-title-7-part-275",
            source_path="sources/us/regulation/2026-06-15-title-7-part-275/ecfr/title-7-part-275.xml",
        )
    )

    assert [record.citation_path for record in records] == [
        "us/regulation/7/275",
        "us/regulation/7/275/3",
    ]
    body = records[1].body
    assert body is not None
    assert "(A) The Federal review sample is determined as follows:" in body
    assert "Average monthly reviewable caseload (N) | Federal subsample target (n′)" in body
    assert "10,001 to 31,488 | n′ = .011634 N + 33.66" in body
    assert body.index("(A) The Federal review sample") < body.index(
        "Average monthly reviewable caseload"
    )
    assert body.index("10,001 to 31,488") < body.index(
        "(B) The next paragraph remains after the table."
    )


def test_iter_ecfr_title_provisions_preserves_flush_paragraphs_and_formulas():
    records = tuple(
        iter_ecfr_title_provisions(
            SAMPLE_TITLE_WITH_GRAPHICS_XML,
            (EcfrPartTarget(title=7, part="273"),),
            version="2026-07-15-title-7-part-273",
            source_path="sources/us/regulation/v/ecfr/title-7-part-273.xml",
            graphic_transcriptions={"ER07OC94.022": "X = (a * b) / c"},
        )
    )

    body = records[1].body
    assert body is not None
    assert "Formula (ER07OC94.022, verified official image): X = (a * b) / c" in body
    assert "This flush paragraph remains operative." in body
    assert "This numbered flush paragraph also remains operative." in body
    assert body.index("The formula follows") < body.index("Formula (ER07OC94.022")
    assert body.index("Formula (ER07OC94.022") < body.index("This flush paragraph")


def test_iter_ecfr_title_provisions_preserves_nested_hed_labels():
    records = tuple(
        iter_ecfr_title_provisions(
            SAMPLE_TITLE_WITH_HED_XML,
            (EcfrPartTarget(title=7, part="273"),),
            version="2026-07-24-title-7-part-273",
            source_path="sources/us/regulation/v/ecfr/title-7-part-273.xml",
        )
    )

    body = records[1].body
    assert body is not None
    assert body.split("\n\n") == [
        "(a) Operative paragraph.",
        "Note:",
        "This is the official note.",
        "Example 1.",
        "First official example.",
        "Example 2.",
        "Second official example.",
    ]
    assert "§ 273.1 Household concept." not in body


def test_load_ecfr_graphic_transcriptions_validates_digest_bound_entries(tmp_path):
    manifest = tmp_path / "graphics.json"
    manifest.write_text(
        '{"graphics":{"ER07OC94.022":{"sha256":"'
        + "a" * 64
        + '","text":" X = (a * b) / c "}}}'
    )

    assert load_ecfr_graphic_transcriptions(manifest) == {
        "ER07OC94.022": EcfrGraphicTranscription(
            sha256="a" * 64,
            text="X = (a * b) / c",
        )
    }


def test_iter_ecfr_title_provisions_builds_subpart_hierarchy():
    records = tuple(
        iter_ecfr_title_provisions(
            SAMPLE_SUBPART_XML,
            (EcfrPartTarget(title=7, part="273"),),
            version="2026-04-29",
            source_path="sources/us/regulation/2026-04-29/ecfr/title-7.xml",
        )
    )

    assert [record.citation_path for record in records] == [
        "us/regulation/7/273",
        "us/regulation/7/273/subpart-A",
        "us/regulation/7/273/1",
    ]
    assert records[2].parent_citation_path == "us/regulation/7/273/subpart-A"
    assert records[2].level == 2


def test_iter_ecfr_title_provisions_preserves_mixed_part_parentage_and_bodies():
    source_bytes = OFFICIAL_TITLE_45_PART_1302_XML.read_bytes()
    assert sha256(source_bytes).hexdigest() == OFFICIAL_TITLE_45_PART_1302_SHA256
    selected_paths = {
        "us/regulation/45/1302",
        "us/regulation/45/1302/1",
        "us/regulation/45/1302/subpart-A",
        "us/regulation/45/1302/10",
    }

    records = tuple(
        iter_ecfr_title_provisions(
            source_bytes.decode(),
            (EcfrPartTarget(title=45, part="1302"),),
            version="2026-06-24-title-45-part-1302",
            source_path=str(OFFICIAL_TITLE_45_PART_1302_XML),
            allowed_citation_paths=selected_paths,
        )
    )

    assert [record.citation_path for record in records] == [
        "us/regulation/45/1302",
        "us/regulation/45/1302/1",
        "us/regulation/45/1302/subpart-A",
        "us/regulation/45/1302/10",
    ]
    direct_section = records[1]
    assert direct_section.parent_citation_path == "us/regulation/45/1302"
    assert direct_section.level == 1
    assert direct_section.body is not None
    assert "This part implements the statutory requirements" in direct_section.body
    subpart_section = records[3]
    assert subpart_section.parent_citation_path == "us/regulation/45/1302/subpart-A"
    assert subpart_section.level == 2
    assert subpart_section.body is not None
    assert "This subpart describes requirements" in subpart_section.body


def test_iter_ecfr_title_provisions_keeps_document_order_for_interleaved_parts():
    records = tuple(
        iter_ecfr_title_provisions(
            SAMPLE_INTERLEAVED_PART_XML,
            (EcfrPartTarget(title=7, part="273"),),
            version="2026-04-29",
            source_path="sources/us/regulation/2026-04-29/ecfr/title-7.xml",
        )
    )

    assert [record.citation_path for record in records] == [
        "us/regulation/7/273",
        "us/regulation/7/273/1",
        "us/regulation/7/273/subpart-A",
        "us/regulation/7/273/2",
        "us/regulation/7/273/90",
    ]
    leading_direct = records[1]
    assert leading_direct.parent_citation_path == "us/regulation/7/273"
    assert leading_direct.level == 1
    trailing_direct = records[4]
    assert trailing_direct.parent_citation_path == "us/regulation/7/273"
    assert trailing_direct.level == 1
    assert trailing_direct.body is not None
    assert "follows a formal subpart" in trailing_direct.body
    subpart_section = records[3]
    assert subpart_section.parent_citation_path == "us/regulation/7/273/subpart-A"
    assert subpart_section.level == 2


def test_iter_ecfr_title_provisions_preserves_appendix_text_and_images():
    records = tuple(
        iter_ecfr_title_provisions(
            SAMPLE_APPENDIX_XML,
            (EcfrPartTarget(title=45, part="604", chapter="VI"),),
            version="2026-08-30-title-45-part-604",
            source_path=(
                "sources/us/regulation/2026-08-30-title-45-part-604/"
                "ecfr/title-45-part-604.xml"
            ),
        )
    )

    assert [record.citation_path for record in records] == [
        "us/regulation/45/604",
        "us/regulation/45/604/100",
        "us/regulation/45/604/appendix-a",
        "us/regulation/45/604/appendix-b",
    ]
    appendix_a = records[2]
    assert appendix_a.kind == "appendix"
    assert appendix_a.parent_citation_path == "us/regulation/45/604"
    assert appendix_a.identifiers["ecfr:appendix"] == "a"
    assert appendix_a.ordinal is not None
    assert records[1].ordinal is not None
    assert appendix_a.ordinal > records[1].ordinal
    assert appendix_a.body is not None
    assert "Certification for Contracts" in appendix_a.body
    assert "included in all subcontracts" in appendix_a.body
    appendix_b = records[3]
    assert appendix_b.ordinal is not None
    assert appendix_b.ordinal > appendix_a.ordinal
    assert appendix_b.body is not None
    assert appendix_b.body.split("\n\n") == [
        "[Official source image: ecfr/graphics/EC01JA91.007.png]",
        "[Official source image: ecfr/graphics/EC01JA91.008.png]",
        "[Official source image: ecfr/graphics/EC01JA91.009.png]",
    ]


def test_iter_ecfr_title_provisions_applies_appendix_formula_transcriptions():
    appendix_formula_xml = SAMPLE_APPENDIX_XML.replace(
        "<P>The undersigned certifies, to the best of his or her knowledge and belief.</P>",
        (
            "<P>The undersigned certifies, to the best of his or her knowledge "
            "and belief.</P><MATH><IMG src=\"/graphics/ER07OC94.022.gif\"/></MATH>"
        ),
    )
    records = tuple(
        iter_ecfr_title_provisions(
            appendix_formula_xml,
            (EcfrPartTarget(title=45, part="604", chapter="VI"),),
            version="2026-08-30-title-45-part-604",
            source_path="ecfr/title-45-part-604.xml",
            graphic_transcriptions={"ER07OC94.022": "X = (a * b) / c"},
        )
    )

    assert records[2].body is not None
    assert (
        "Formula (ER07OC94.022, verified official image): X = (a * b) / c"
        in records[2].body
    )


def test_extract_ecfr_writes_source_inventory_provisions_and_coverage(tmp_path, monkeypatch):
    import axiom_corpus.corpus.ecfr as ecfr

    monkeypatch.setattr(ecfr, "fetch_ecfr_structure", lambda title, as_of: SAMPLE_STRUCTURE)
    monkeypatch.setattr(
        ecfr,
        "fetch_ecfr_title_xml",
        lambda title, as_of: pytest.fail("part-scoped extract fetched a full title"),
    )
    monkeypatch.setattr(ecfr, "fetch_ecfr_part_xml", lambda title, part, as_of: SAMPLE_TITLE_XML)
    store = CorpusArtifactStore(tmp_path / "corpus")
    run_id = "2026-04-29-title-7-part-273"
    store.write_provisions(
        store.provisions_path("us", "regulation", run_id),
        [
            ProvisionRecord(
                jurisdiction="us",
                document_class="regulation",
                citation_path="us/regulation/7/999",
                body="stale",
            )
        ],
    )

    report = extract_ecfr(
        store,
        version="2026-04-29",
        as_of="2024-04-16",
        expression_date=date(2024, 4, 16),
        only_title=7,
        only_part="273",
    )

    assert report.coverage.complete
    assert report.provisions_written == 3
    assert (store.root / f"sources/us/regulation/{run_id}/ecfr/title-7-part-273.xml").exists()
    assert (store.root / f"inventory/us/regulation/{run_id}.json").exists()
    assert (store.root / f"provisions/us/regulation/{run_id}.jsonl").exists()
    records = load_provisions(report.provisions_path)
    assert [record.citation_path for record in records] == [
        "us/regulation/7/273",
        "us/regulation/7/273/1",
        "us/regulation/7/273/2",
    ]
    assert records[1].source_path == (
        "sources/us/regulation/2026-04-29-title-7-part-273/ecfr/title-7-part-273.xml"
    )
    assert records[1].source_as_of == "2024-04-16"
    assert records[1].expression_date == "2024-04-16"


def test_extract_ecfr_section_scope_preserves_formal_subpart(tmp_path):
    source_xml = tmp_path / "official-title-7-part-273.xml"
    source_xml.write_text(SAMPLE_SUBPART_XML)
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_ecfr(
        store,
        version="2026-07-24",
        as_of="2026-07-22",
        expression_date=date(2026, 7, 22),
        source_xml=source_xml,
        only_title=7,
        only_part="273",
        only_sections=("273.1",),
        workers=1,
    )

    expected_paths = [
        "us/regulation/7/273",
        "us/regulation/7/273/subpart-A",
        "us/regulation/7/273/1",
    ]
    inventory = load_source_inventory(report.inventory_path)
    records = load_provisions(report.provisions_path)

    assert report.coverage.complete
    assert report.coverage.source_count == 3
    assert report.coverage.provision_count == 3
    assert [item.citation_path for item in inventory] == expected_paths
    assert [record.citation_path for record in records] == expected_paths
    assert records[1].parent_citation_path == "us/regulation/7/273"
    assert records[1].level == 1
    assert records[2].parent_citation_path == "us/regulation/7/273/subpart-A"
    assert records[2].level == 2
    assert records[2].identifiers["ecfr:subpart"] == "A"


def test_extract_ecfr_section_scope_reprocesses_complete_cached_scope(
    tmp_path, monkeypatch
):
    import axiom_corpus.corpus.ecfr as ecfr

    monkeypatch.setattr(
        ecfr,
        "fetch_ecfr_structure",
        lambda title, as_of: pytest.fail("local source fetched structure JSON"),
    )
    monkeypatch.setattr(
        ecfr,
        "fetch_ecfr_part_xml",
        lambda title, part, as_of: pytest.fail("retained part XML was not reused"),
    )
    monkeypatch.setattr(
        ecfr,
        "fetch_ecfr_graphic",
        lambda identifier: pytest.fail("unselected section graphic was fetched"),
    )
    store = CorpusArtifactStore(tmp_path / "corpus")
    run_id = "2026-07-24-title-7-part-273"
    source_xml = tmp_path / "official-title-7-part-273.xml"
    source_bytes = SAMPLE_TITLE_WITH_HED_XML.replace("\n", "\r\n").encode()
    source_xml.write_bytes(source_bytes)
    retained_xml = store.source_path(
        "us",
        "regulation",
        run_id,
        "ecfr/title-7-part-273.xml",
    )
    store.write_provisions(
        store.provisions_path("us", "regulation", run_id),
        [
            ProvisionRecord(
                jurisdiction="us",
                document_class="regulation",
                citation_path="us/regulation/7/273",
                body=None,
            ),
            ProvisionRecord(
                jurisdiction="us",
                document_class="regulation",
                citation_path="us/regulation/7/273/1",
                body="stale cached body",
            ),
        ],
    )

    report = extract_ecfr(
        store,
        version="2026-07-24",
        as_of="2026-07-22",
        expression_date=date(2026, 7, 22),
        source_xml=source_xml,
        only_title=7,
        only_part="273",
        only_sections=("273.1",),
        workers=1,
    )

    assert report.coverage.complete
    assert report.coverage.source_count == 2
    assert report.coverage.provision_count == 2
    records = load_provisions(report.provisions_path)
    assert [record.citation_path for record in records] == [
        "us/regulation/7/273",
        "us/regulation/7/273/1",
    ]
    assert "Note:" in (records[1].body or "")
    assert "Example 2." in (records[1].body or "")
    assert retained_xml.read_bytes() == source_bytes
    structure_path = retained_xml.with_name("title-7.structure.json")
    assert not structure_path.exists()
    assert report.source_paths == (retained_xml,)


def test_ecfr_cli_accepts_repeatable_section_filter():
    parser = build_parser()

    inventory_args = parser.parse_args(
        [
            "inventory-ecfr",
            "--base",
            "data/corpus",
            "--version",
            "v",
            "--as-of",
            "2026-07-22",
            "--only-title",
            "26",
            "--section",
            "1.1401-1",
            "--section",
            "1.1402",
        ]
    )
    extract_args = parser.parse_args(
        [
            "extract-ecfr",
            "--base",
            "data/corpus",
            "--version",
            "v",
            "--as-of",
            "2026-07-22",
            "--source-xml",
            "official-title-26-part-1.xml",
            "--only-title",
            "26",
            "--section",
            "1.1401-1",
        ]
    )

    assert inventory_args.section == ["1.1401-1", "1.1402"]
    assert extract_args.section == ["1.1401-1"]
    assert extract_args.source_xml.name == "official-title-26-part-1.xml"


def test_extract_ecfr_archives_sha_bound_formula_graphics(tmp_path, monkeypatch):
    import axiom_corpus.corpus.ecfr as ecfr

    graphic = b"\x89PNG\r\n\x1a\nformula"
    monkeypatch.setattr(ecfr, "fetch_ecfr_structure", lambda title, as_of: SAMPLE_STRUCTURE)
    monkeypatch.setattr(
        ecfr,
        "fetch_ecfr_part_xml",
        lambda title, part, as_of: SAMPLE_TITLE_WITH_GRAPHICS_XML,
    )
    monkeypatch.setattr(ecfr, "fetch_ecfr_graphic", lambda identifier: graphic)
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_ecfr(
        store,
        version="2026-07-15",
        as_of="2026-07-09",
        expression_date=date(2026, 7, 9),
        only_title=7,
        only_part="273",
        graphic_transcriptions={
            "ER07OC94.022": EcfrGraphicTranscription(
                sha256=sha256_bytes(graphic),
                text="X = (a * b) / c",
            )
        },
    )

    assert report.coverage.complete
    graphic_path = (
        store.root
        / "sources/us/regulation/2026-07-15-title-7-part-273/ecfr/graphics/ER07OC94.022.png"
    )
    evidence_path = graphic_path.with_name("transcriptions.json")
    assert graphic_path.read_bytes() == graphic
    assert '"sha256"' in evidence_path.read_text()
    records = load_provisions(report.provisions_path)
    assert "verified official image" in (records[1].body or "")


def test_extract_ecfr_archives_appendix_graphics_and_reports_complete_coverage(
    tmp_path, monkeypatch
):
    import axiom_corpus.corpus.ecfr as ecfr

    graphics = {
        identifier: b"\x89PNG\r\n\x1a\n" + identifier.encode()
        for identifier in (
            "EC01JA91.007",
            "EC01JA91.008",
            "EC01JA91.009",
        )
    }
    monkeypatch.setattr(
        ecfr,
        "fetch_ecfr_structure",
        lambda title, as_of: SAMPLE_APPENDIX_STRUCTURE,
    )
    monkeypatch.setattr(
        ecfr,
        "fetch_ecfr_part_xml",
        lambda title, part, as_of: SAMPLE_APPENDIX_XML,
    )
    monkeypatch.setattr(
        ecfr,
        "fetch_ecfr_graphic",
        lambda identifier: graphics[identifier],
    )
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_ecfr(
        store,
        version="2026-08-30",
        as_of="2026-08-27",
        expression_date=date(2026, 8, 27),
        only_title=45,
        only_part="604",
    )

    assert report.coverage.complete
    assert report.provisions_written == 4
    records = load_provisions(report.provisions_path)
    assert [record.citation_path for record in records] == [
        "us/regulation/45/604",
        "us/regulation/45/604/100",
        "us/regulation/45/604/appendix-a",
        "us/regulation/45/604/appendix-b",
    ]
    for identifier, graphic in graphics.items():
        graphic_path = (
            store.root
            / "sources/us/regulation/2026-08-30-title-45-part-604/"
            / f"ecfr/graphics/{identifier}.png"
        )
        assert graphic_path.read_bytes() == graphic


def test_extract_ecfr_reprocesses_complete_scope_for_graphic_transcriptions(
    tmp_path, monkeypatch
):
    import axiom_corpus.corpus.ecfr as ecfr

    graphic = b"\x89PNG\r\n\x1a\nformula"
    monkeypatch.setattr(ecfr, "fetch_ecfr_structure", lambda title, as_of: SAMPLE_STRUCTURE)
    monkeypatch.setattr(
        ecfr,
        "fetch_ecfr_part_xml",
        lambda title, part, as_of: SAMPLE_TITLE_WITH_GRAPHICS_XML,
    )
    monkeypatch.setattr(ecfr, "fetch_ecfr_graphic", lambda identifier: graphic)
    store = CorpusArtifactStore(tmp_path / "corpus")
    kwargs = {
        "version": "2026-07-15",
        "as_of": "2026-07-09",
        "expression_date": date(2026, 7, 9),
        "only_title": 7,
        "only_part": "273",
    }

    first_report = extract_ecfr(store, **kwargs)
    first_records = load_provisions(first_report.provisions_path)
    assert "verified official image" not in (first_records[1].body or "")

    second_report = extract_ecfr(
        store,
        **kwargs,
        graphic_transcriptions={
            "ER07OC94.022": EcfrGraphicTranscription(
                sha256=sha256_bytes(graphic),
                text="X = (a * b) / c",
            )
        },
    )

    second_records = load_provisions(second_report.provisions_path)
    assert "verified official image" in (second_records[1].body or "")
    assert any(path.name == "transcriptions.json" for path in second_report.source_paths)


def test_extract_ecfr_rolls_back_failed_transcription_rebuild(tmp_path, monkeypatch):
    import axiom_corpus.corpus.ecfr as ecfr

    graphic = b"\x89PNG\r\n\x1a\nformula"
    monkeypatch.setattr(ecfr, "fetch_ecfr_structure", lambda title, as_of: SAMPLE_STRUCTURE)
    monkeypatch.setattr(
        ecfr,
        "fetch_ecfr_part_xml",
        lambda title, part, as_of: SAMPLE_TITLE_WITH_GRAPHICS_XML,
    )
    monkeypatch.setattr(ecfr, "fetch_ecfr_graphic", lambda identifier: graphic)
    store = CorpusArtifactStore(tmp_path / "corpus")
    kwargs = {
        "version": "2026-07-15",
        "as_of": "2026-07-09",
        "expression_date": date(2026, 7, 9),
        "only_title": 7,
        "only_part": "273",
    }
    successful = extract_ecfr(
        store,
        **kwargs,
        graphic_transcriptions={
            "ER07OC94.022": EcfrGraphicTranscription(
                sha256=sha256_bytes(graphic),
                text="original transcription",
            )
        },
    )
    records_before = successful.provisions_path.read_bytes()
    evidence_path = next(
        path for path in successful.source_paths if path.name == "transcriptions.json"
    )
    evidence_before = evidence_path.read_bytes()

    failed = extract_ecfr(
        store,
        **kwargs,
        graphic_transcriptions={
            "ER07OC94.022": EcfrGraphicTranscription(
                sha256="0" * 64,
                text="rejected transcription",
            )
        },
    )

    assert failed.title_error_count == 1
    assert failed.provisions_path.read_bytes() == records_before
    assert evidence_path.read_bytes() == evidence_before


def test_extract_ecfr_aggregates_graphic_evidence_across_titles(tmp_path, monkeypatch):
    import axiom_corpus.corpus.ecfr as ecfr

    identifiers = {1: "ER07OC94.022", 2: "ER25SE06.014"}
    graphics = {
        identifier: b"\x89PNG\r\n\x1a\n" + identifier.encode()
        for identifier in identifiers.values()
    }

    def structure(title, as_of):
        return {**SAMPLE_STRUCTURE, "identifier": str(title)}

    def title_xml(title, as_of):
        return SAMPLE_TITLE_WITH_GRAPHICS_XML.replace(
            "ER07OC94.022", identifiers[title]
        )

    monkeypatch.setattr(ecfr, "DEFAULT_CFR_TITLES", (1, 2))
    monkeypatch.setattr(ecfr, "fetch_ecfr_structure", structure)
    monkeypatch.setattr(ecfr, "fetch_ecfr_title_xml", title_xml)
    monkeypatch.setattr(ecfr, "fetch_ecfr_graphic", lambda identifier: graphics[identifier])
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_ecfr(
        store,
        version="2026-07-15",
        as_of="2026-07-09",
        expression_date=date(2026, 7, 9),
        workers=2,
        graphic_transcriptions={
            identifier: EcfrGraphicTranscription(
                sha256=sha256_bytes(graphic),
                text=f"formula for {identifier}",
            )
            for identifier, graphic in graphics.items()
        },
    )

    evidence_path = next(
        path for path in report.source_paths if path.name == "transcriptions.json"
    )
    assert set(json.loads(evidence_path.read_text())["graphics"]) == set(graphics)

    failed_store = CorpusArtifactStore(tmp_path / "failed-corpus")
    failed = extract_ecfr(
        failed_store,
        version="2026-07-15",
        as_of="2026-07-09",
        expression_date=date(2026, 7, 9),
        workers=2,
        graphic_transcriptions={
            identifiers[1]: EcfrGraphicTranscription(
                sha256=sha256_bytes(graphics[identifiers[1]]),
                text="valid transcription",
            ),
            identifiers[2]: EcfrGraphicTranscription(
                sha256="0" * 64,
                text="rejected transcription",
            ),
        },
    )

    assert failed.title_error_count == 1
    assert load_provisions(failed.provisions_path) == ()


def test_extract_ecfr_writes_structure_only_placeholders(tmp_path, monkeypatch):
    import axiom_corpus.corpus.ecfr as ecfr

    structure = {
        **SAMPLE_STRUCTURE,
        "children": [
            {
                **SAMPLE_STRUCTURE["children"][0],
                "children": [
                    {
                        **SAMPLE_STRUCTURE["children"][0]["children"][0],
                        "children": [
                            {
                                **SAMPLE_STRUCTURE["children"][0]["children"][0]["children"][0],
                                "children": [
                                    *SAMPLE_STRUCTURE["children"][0]["children"][0]["children"][0][
                                        "children"
                                    ],
                                    {
                                        "identifier": "273.3",
                                        "label": "§ 273.3 Missing from XML.",
                                        "label_description": "Missing from XML.",
                                        "type": "section",
                                    },
                                ],
                            }
                        ],
                    }
                ],
            }
        ],
    }

    monkeypatch.setattr(ecfr, "fetch_ecfr_structure", lambda title, as_of: structure)
    monkeypatch.setattr(ecfr, "fetch_ecfr_part_xml", lambda title, part, as_of: SAMPLE_TITLE_XML)

    store = CorpusArtifactStore(tmp_path / "corpus")
    report = extract_ecfr(
        store,
        version="2026-04-29",
        as_of="2024-04-16",
        expression_date=date(2024, 4, 16),
        only_title=7,
        only_part="273",
    )

    records = load_provisions(report.provisions_path)
    assert report.coverage.complete
    assert report.provisions_written == 4
    assert [record.citation_path for record in records] == [
        "us/regulation/7/273",
        "us/regulation/7/273/1",
        "us/regulation/7/273/2",
        "us/regulation/7/273/3",
    ]
    placeholder = records[-1]
    assert placeholder.body is None
    assert placeholder.heading == "Missing from XML"
    assert placeholder.parent_citation_path == "us/regulation/7/273"
    assert placeholder.legal_identifier == "7 CFR 273.3"
    assert placeholder.identifiers == {
        "ecfr:title": "7",
        "ecfr:part": "273",
        "ecfr:section": "3",
    }
    assert placeholder.metadata is not None
    assert placeholder.metadata["structure_only"] is True
    assert placeholder.metadata["body_status"] == "not_in_ecfr_full_xml"


def test_extract_ecfr_keeps_failed_titles_missing_from_coverage(tmp_path, monkeypatch):
    import axiom_corpus.corpus.ecfr as ecfr

    def fail_part_xml(title, part, as_of):
        raise HTTPError("https://example.test", 404, "Not Found", {}, None)

    monkeypatch.setattr(ecfr, "fetch_ecfr_structure", lambda title, as_of: SAMPLE_STRUCTURE)
    monkeypatch.setattr(ecfr, "fetch_ecfr_part_xml", fail_part_xml)

    store = CorpusArtifactStore(tmp_path / "corpus")
    report = extract_ecfr(
        store,
        version="2026-04-29",
        as_of="2024-04-16",
        expression_date=date(2024, 4, 16),
        only_title=7,
        only_part="273",
    )

    assert not report.coverage.complete
    assert report.title_error_count == 1
    assert report.provisions_written == 0
    assert report.coverage.missing_from_provisions == (
        "us/regulation/7/273",
        "us/regulation/7/273/1",
        "us/regulation/7/273/2",
    )


def test_build_ecfr_inventory_skips_missing_titles_in_full_mode(monkeypatch):
    import axiom_corpus.corpus.ecfr as ecfr

    def fake_fetch(title, as_of):
        if title == 2:
            raise HTTPError("https://example.test", 404, "Not Found", {}, None)
        return {**SAMPLE_STRUCTURE, "identifier": str(title)}

    monkeypatch.setattr(ecfr, "DEFAULT_CFR_TITLES", (1, 2))
    monkeypatch.setattr(ecfr, "fetch_ecfr_structure", fake_fetch)

    inventory = build_ecfr_inventory(as_of="2024-04-16")

    assert inventory.title_count == 1
    assert len(inventory.items) == 3
