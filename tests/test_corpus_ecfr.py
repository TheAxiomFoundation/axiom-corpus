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
        include_appendices=True,
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


@pytest.mark.parametrize("entrypoint", ["lower", "public", "iterator", "extract", "inventory-cli", "extract-cli"])
def test_retained_416_default_scope_ignores_unsupported_appendix(
    tmp_path, monkeypatch, capsys, entrypoint
):
    import axiom_corpus.corpus.ecfr as ecfr
    from axiom_corpus.corpus.cli import main

    source = (
        Path(__file__).parents[1] / "data/corpus/sources/us/regulation"
        / "2026-07-23-title-20-part-416/ecfr"
    )
    structure = json.loads((source / "title-20.structure.json").read_text())
    xml = (source / "title-20-part-416.xml").read_text()
    assert "Appendix to Subpart K of Part 416" in xml
    monkeypatch.setattr(ecfr, "fetch_ecfr_structure", lambda title, as_of: structure)
    monkeypatch.setattr(ecfr, "fetch_ecfr_part_xml", lambda title, part, as_of: xml)
    monkeypatch.setattr(ecfr, "fetch_ecfr_graphic", lambda identifier: pytest.fail("unexpected graphic fetch"))
    kwargs = {"only_title": 20, "only_part": "416", "as_of": "2026-07-23"}
    store = CorpusArtifactStore(tmp_path / "corpus")

    def run(include_appendices=False):
        # Omit the keyword entirely on default calls to exercise public defaults.
        opt_in = {"include_appendices": True} if include_appendices else {}
        if entrypoint == "lower":
            return build_ecfr_inventory_from_structures((structure,), only_part="416", **opt_in)
        if entrypoint == "public":
            return build_ecfr_inventory(**kwargs, **opt_in)
        if entrypoint == "iterator":
            return tuple(iter_ecfr_title_provisions(
                xml, tuple(t for t in part_targets_from_structure(structure) if t.part == "416"),
                version="2026-07-23", source_path="official.xml", **opt_in,
            ))
        if entrypoint == "extract":
            return extract_ecfr(store, version="2026-07-23", **kwargs, **opt_in)
        command = "inventory-ecfr" if entrypoint == "inventory-cli" else "extract-ecfr"
        return main([
            command, "--base", str(store.root), "--version", "2026-07-23",
            "--as-of", "2026-07-23", "--only-title", "20", "--only-part", "416",
            *(["--include-appendices"] if include_appendices else []),
        ])

    result = run()
    if entrypoint in {"lower", "public"}:
        assert len(result.items) == 622
        assert not any(item.metadata["kind"] == "appendix" for item in result.items)
    elif entrypoint == "iterator":
        assert not any(record.kind == "appendix" for record in result)
        inventory_paths = {item.citation_path for item in build_ecfr_inventory(**kwargs).items}
        assert len(inventory_paths) == 622
        assert inventory_paths <= {record.citation_path for record in result}
    elif entrypoint == "extract":
        assert result.coverage.source_count == result.provisions_written == 622
        assert result.title_errors == ()
    else:
        assert result == 0
        output = json.loads(capsys.readouterr().out)
        key = "items_written" if entrypoint == "inventory-cli" else "provisions_written"
        assert output[key] == 622
    if entrypoint.endswith("-cli"):
        assert run(include_appendices=True) == 2
        error = capsys.readouterr()
        assert error.out == ""
        assert "unsupported nonreserved eCFR appendix" in error.err
        assert "Appendix to Subpart K of Part 416" in error.err
    else:
        with pytest.raises(ValueError, match="unsupported nonreserved eCFR appendix.*Appendix to Subpart K of Part 416"):
            run(include_appendices=True)


@pytest.mark.parametrize("container", ["title", "chapter", "subchapter"])
def test_part_scope_excludes_unrelated_uncontained_appendix(tmp_path, monkeypatch, container):
    import axiom_corpus.corpus.ecfr as ecfr

    structure = json.loads(json.dumps(SAMPLE_APPENDIX_STRUCTURE))
    outside = {"identifier": "Appendix A to Chapter VI", "type": "appendix"}
    if container == "title":
        structure["children"].append(outside)
    elif container == "chapter":
        structure["children"][0]["children"].append(outside)
    else:
        structure["children"][0]["children"].append({
            "identifier": "A", "type": "subchapter", "children": [outside],
        })
    monkeypatch.setattr(ecfr, "fetch_ecfr_structure", lambda title, as_of: structure)
    monkeypatch.setattr(ecfr, "fetch_ecfr_part_xml", lambda title, part, as_of: SAMPLE_APPENDIX_XML)
    monkeypatch.setattr(ecfr, "fetch_ecfr_graphic", lambda identifier: b"\x89PNG\r\n\x1a\n" + identifier.encode())

    inventory = build_ecfr_inventory_from_structures(
        (structure,), only_part="604", include_appendices=True,
    )
    expected = ["us/regulation/45/604", "us/regulation/45/604/100", "us/regulation/45/604/appendix-a", "us/regulation/45/604/appendix-b"]
    assert [item.citation_path for item in inventory.items] == expected
    report = extract_ecfr(
        CorpusArtifactStore(tmp_path / "corpus"), version="2026-08-30", as_of="2026-08-27",
        only_title=45, only_part="604", include_appendices=True,
    )
    assert report.title_errors == ()
    assert report.coverage.complete
    assert [record.citation_path for record in load_provisions(report.provisions_path)] == expected
    # Without a part selector the unsupported appendix is in scope and must fail.
    with pytest.raises(ValueError, match="unsupported nonreserved eCFR appendix without a part-scoped identifier"):
        build_ecfr_inventory_from_structures((structure,), include_appendices=True)


@pytest.mark.parametrize("identifier", ["Appendix II to Part 604", "Appendix A to Part 605"])
def test_extract_ecfr_validates_appendix_inventory_before_writing(tmp_path, monkeypatch, identifier):
    import axiom_corpus.corpus.ecfr as ecfr

    structure = json.loads(json.dumps(SAMPLE_APPENDIX_STRUCTURE))
    structure["children"][0]["children"][0]["children"][1]["identifier"] = identifier
    monkeypatch.setattr(ecfr, "fetch_ecfr_structure", lambda title, as_of: structure)
    monkeypatch.setattr(ecfr, "fetch_ecfr_part_xml", lambda *args: pytest.fail("invalid inventory fetched XML"))
    store = CorpusArtifactStore(tmp_path / "corpus")

    with pytest.raises(ValueError, match="unsupported.*appendix|appendix part.*conflicts"):
        extract_ecfr(
            store, version="2026-08-30", as_of="2026-08-27", only_title=45,
            only_part="604", include_appendices=True,
        )

    assert not store.root.exists()


def test_retained_source_inventory_failure_preserves_existing_run_bytes(tmp_path, monkeypatch):
    import axiom_corpus.corpus.ecfr as ecfr

    # A retained-source run must be section-scoped. Its unsupported appendix is
    # excluded, but the requested foreign-part section fails inventory validation
    # after the local XML was read and the scoped structure was constructed.
    xml = SAMPLE_APPENDIX_XML.replace("§ 604.100", "§ 605.100").replace(
        "Appendix A to Part 604", "Appendix II to Part 604"
    )
    source = tmp_path / "official.xml"
    source.write_bytes(xml.encode())
    store = CorpusArtifactStore(tmp_path / "corpus")
    retained = store.root / "sources/us/regulation/2026-08-30-title-45-part-604/ecfr/title-45-part-604.xml"
    retained.parent.mkdir(parents=True)
    retained.write_bytes(b"previous retained source")
    before = {path.relative_to(store.root): path.read_bytes() for path in store.root.rglob("*") if path.is_file()}
    monkeypatch.setattr(ecfr, "fetch_ecfr_structure", lambda *args: pytest.fail("local run fetched structure"))
    monkeypatch.setattr(ecfr, "fetch_ecfr_part_xml", lambda *args: pytest.fail("local run fetched XML"))

    with pytest.raises(ValueError, match=r"eCFR section selector\(s\) not found: 605\.100"):
        extract_ecfr(
            store, version="2026-08-30", as_of="2026-08-27", source_xml=source,
            only_title=45, only_part="604", only_sections=("605.100",), include_appendices=True,
        )

    assert source.read_bytes() == xml.encode()
    after = {path.relative_to(store.root): path.read_bytes() for path in store.root.rglob("*") if path.is_file()}
    assert after == before


@pytest.mark.parametrize("command", ["inventory-ecfr", "extract-ecfr"])
@pytest.mark.parametrize("identifier", ["Appendix II to Part 604", "Appendix A to Part 605"])
@pytest.mark.parametrize("existing_run", [False, True])
def test_ecfr_cli_reports_invalid_appendix_without_writes(
    tmp_path, monkeypatch, capsys, command, identifier, existing_run
):
    import axiom_corpus.corpus.ecfr as ecfr
    from axiom_corpus.corpus.cli import main

    structure = json.loads(json.dumps(SAMPLE_APPENDIX_STRUCTURE))
    structure["children"][0]["children"][0]["children"][1]["identifier"] = identifier
    monkeypatch.setattr(ecfr, "fetch_ecfr_structure", lambda title, as_of: structure)
    monkeypatch.setattr(ecfr, "fetch_ecfr_part_xml", lambda *args: pytest.fail("invalid inventory fetched XML"))
    output = tmp_path / "corpus"
    existing = output / "sources/us/regulation/2026-08-30-title-45-part-604/ecfr/title-45.structure.json"
    if existing_run:
        existing.parent.mkdir(parents=True)
        existing.write_bytes(b"previous run bytes")
    before = {path.relative_to(output): path.read_bytes() for path in output.rglob("*") if path.is_file()}

    result = main([
        command, "--base", str(output), "--version", "2026-08-30",
        "--as-of", "2026-08-27", "--only-title", "45", "--only-part", "604",
        "--include-appendices",
    ])

    assert result == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert identifier in captured.err
    assert "unsupported nonreserved eCFR appendix" in captured.err or "conflicts with enclosing part" in captured.err
    assert "Traceback" not in captured.err
    after = {path.relative_to(output): path.read_bytes() for path in output.rglob("*") if path.is_file()}
    assert after == before
    if not existing_run:
        assert not output.exists()


@pytest.mark.parametrize("include_appendices", [False, True])
def test_extract_ecfr_preserves_ordinary_section_body_and_formula_only_capture(
    tmp_path, monkeypatch, include_appendices
):
    import axiom_corpus.corpus.ecfr as ecfr

    section = """
      <HEAD>§ 604.100 Conditions on use of funds.</HEAD>
      <HED>Retained HED<IMG src="/graphics/SECTION.001.gif"/></HED>
      <HD1>Legacy omitted HD1<IMG src="/graphics/SECTION.002.gif"/><P>Nested paragraph</P></HD1>
      <HD2>Legacy omitted HD2</HD2><HD3>Legacy omitted HD3</HD3>
      <P>Paragraph text<IMG src="/graphics/SECTION.003.gif"/></P>
      <TABLE><TR><TD>Table text<IMG src="/graphics/SECTION.004.gif"/></TD></TR></TABLE>
      <IMG src="/graphics/SECTION.005.gif"/>
      <MATH><IMG src="/graphics/ER07OC94.022.gif"/></MATH>
    """
    xml = SAMPLE_APPENDIX_XML.replace(
        '<P>(a) No appropriated funds may be used for covered lobbying.</P>', section
    )
    assert section in xml
    fetched = []
    graphics = {
        identifier: b"\x89PNG\r\n\x1a\n" + identifier.encode()
        for identifier in ("ER07OC94.022", "EC01JA91.007", "EC01JA91.008", "EC01JA91.009")
    }

    def fetch_graphic(identifier):
        fetched.append(identifier)
        return graphics[identifier]

    monkeypatch.setattr(ecfr, "fetch_ecfr_structure", lambda title, as_of: SAMPLE_APPENDIX_STRUCTURE)
    monkeypatch.setattr(ecfr, "fetch_ecfr_part_xml", lambda title, part, as_of: xml)
    monkeypatch.setattr(ecfr, "fetch_ecfr_graphic", fetch_graphic)
    report = extract_ecfr(
        CorpusArtifactStore(tmp_path / "corpus"), version="2026-08-30", as_of="2026-08-27",
        only_title=45, only_part="604", include_appendices=include_appendices,
    )

    assert report.title_errors == ()
    assert report.coverage.complete
    records = load_provisions(report.provisions_path)
    assert records[1].body.split("\n\n") == [
        "Retained HED", "Nested paragraph", "Paragraph text", "Table text",
        "[Official formula image: ecfr/graphics/ER07OC94.022.png]",
    ]
    expected_ids = list(graphics) if include_appendices else ["ER07OC94.022"]
    assert fetched == expected_ids
    assert {path.stem: path.read_bytes() for path in report.source_paths if path.suffix == ".png"} == {
        identifier: graphics[identifier] for identifier in expected_ids
    }
    assert len(records) == (4 if include_appendices else 2)


def test_inventory_rejects_selected_appendix_part_conflict():
    structure = json.loads(json.dumps(SAMPLE_APPENDIX_STRUCTURE))
    structure["children"][0]["children"][0]["children"][1]["identifier"] = "Appendix A to Part 605"
    with pytest.raises(ValueError, match="appendix part '605' conflicts with enclosing part '604'"):
        build_ecfr_inventory_from_structures((structure,), only_part="604", include_appendices=True)
    assert len(build_ecfr_inventory_from_structures((structure,), only_part="604").items) == 2
    assert len(build_ecfr_inventory_from_structures(
        (structure,), only_part="604", only_sections=("604.100",), include_appendices=True,
    ).items) == 2


@pytest.mark.parametrize("allowed_paths", [None, {"us/regulation/45/604/appendix-a"}, {"us/regulation/45/605/appendix-a"}])
def test_iterator_rejects_selected_appendix_part_conflict(allowed_paths):
    xml = SAMPLE_APPENDIX_XML.replace("Appendix A to Part 604", "Appendix A to Part 605")
    kwargs = {
        "targets": (EcfrPartTarget(title=45, part="604"),),
        "version": "2026-08-30", "source_path": "official.xml",
    }
    with pytest.raises(ValueError, match="appendix part '605' conflicts with enclosing part '604'"):
        tuple(iter_ecfr_title_provisions(xml, **kwargs, allowed_citation_paths=allowed_paths, include_appendices=True))
    assert len(tuple(iter_ecfr_title_provisions(xml, **kwargs))) == 2
    scoped = tuple(iter_ecfr_title_provisions(
        xml, **kwargs, allowed_citation_paths={"us/regulation/45/604/100"}, include_appendices=True,
    ))
    assert [record.citation_path for record in scoped] == ["us/regulation/45/604/100"]


@pytest.mark.parametrize("appendix_id,ordinal", [("A", 1_000_065), ("12", 1_000_012)])
@pytest.mark.parametrize("include_appendices", [False, True])
def test_ecfr_cli_opt_in_retains_direct_appendix_image(
    tmp_path, monkeypatch, capsys, appendix_id, ordinal, include_appendices
):
    import axiom_corpus.corpus.ecfr as ecfr
    from axiom_corpus.corpus.cli import main

    identifier = f"Appendix {appendix_id} to Part 604"
    structure = {"identifier": "45", "type": "title", "children": [{
        "identifier": "604", "type": "part", "label": "Part 604-Forms",
        "children": [{"identifier": identifier, "type": "appendix", "label": f"{identifier}-Form"}],
    }]}
    xml = (
        '<ECFR><DIV5 N="604" TYPE="PART"><HEAD>Part 604-Forms</HEAD>'
        f'<DIV9 N="{identifier}" TYPE="APPENDIX"><HEAD>{identifier}-Form</HEAD>'
        '<IMG src="/graphics/EC01JA91.007.gif"/></DIV9></DIV5></ECFR>'
    )
    png = b"\x89PNG\r\n\x1a\nretained-form"
    fetched = []

    def fetch_graphic(graphic_id):
        fetched.append(graphic_id)
        assert graphic_id == "EC01JA91.007"
        return png

    monkeypatch.setattr(ecfr, "fetch_ecfr_structure", lambda title, as_of: structure)
    monkeypatch.setattr(ecfr, "fetch_ecfr_part_xml", lambda title, part, as_of: xml)
    monkeypatch.setattr(ecfr, "fetch_ecfr_graphic", fetch_graphic)
    store = CorpusArtifactStore(tmp_path / "corpus")
    for command in ("inventory-ecfr", "extract-ecfr"):
        assert main([
            command, "--base", str(store.root), "--version", "2026-08-30",
            "--as-of", "2026-08-27", "--only-title", "45", "--only-part", "604",
            *(["--include-appendices"] if include_appendices else []),
        ]) == 0
        output = json.loads(capsys.readouterr().out)
        count_key = "items_written" if command == "inventory-ecfr" else "provisions_written"
        assert output[count_key] == (2 if include_appendices else 1)
    records = load_provisions(Path(output["provisions_path"]))
    assert fetched == (["EC01JA91.007"] if include_appendices else [])
    if include_appendices:
        appendix = records[-1]
        assert appendix.citation_path == f"us/regulation/45/604/appendix-{appendix_id.lower()}"
        assert appendix.ordinal == ordinal
        assert appendix.heading == "Form"
        assert appendix.body == "[Official source image: ecfr/graphics/EC01JA91.007.png]"
        graphic_path = store.root / "sources/us/regulation/2026-08-30-title-45-part-604/ecfr/graphics/EC01JA91.007.png"
        assert graphic_path.read_bytes() == png


@pytest.mark.parametrize("appendix_id,ordinal", [("A", 1_000_065), ("12", 1_000_012)])
def test_extract_ecfr_retains_missing_xml_appendix_source_identity(
    tmp_path, monkeypatch, appendix_id, ordinal
):
    import axiom_corpus.corpus.ecfr as ecfr

    identifier = f"Appendix {appendix_id} to Part 604"
    structure = {"identifier": "45", "type": "title", "children": [{
        "identifier": "604", "type": "part", "label": "Part 604-Forms",
        "children": [{
            "identifier": identifier, "type": "appendix",
            "label_description": "Official retained form.",
        }],
    }]}
    xml = '<ECFR><DIV5 N="604" TYPE="PART"><HEAD>Part 604-Forms</HEAD></DIV5></ECFR>'
    monkeypatch.setattr(ecfr, "fetch_ecfr_structure", lambda title, as_of: structure)
    monkeypatch.setattr(ecfr, "fetch_ecfr_part_xml", lambda title, part, as_of: xml)
    monkeypatch.setattr(ecfr, "fetch_ecfr_graphic", lambda graphic_id: pytest.fail("missing XML has no image to fetch"))
    kwargs = {"version": "2026-08-30", "as_of": "2026-08-27", "only_title": 45, "only_part": "604", "include_appendices": True}
    report = extract_ecfr(CorpusArtifactStore(tmp_path / "missing"), **kwargs)

    assert report.title_errors == ()
    records = load_provisions(report.provisions_path)
    placeholder = records[-1]
    item = load_source_inventory(report.inventory_path)[-1]
    assert placeholder.citation_path == item.citation_path == f"us/regulation/45/604/appendix-{appendix_id.lower()}"
    assert placeholder.kind == "appendix"
    assert placeholder.body is None
    assert placeholder.heading == "Official retained form"
    assert placeholder.legal_identifier == f"45 CFR part 604, appendix {appendix_id}"
    assert placeholder.parent_citation_path == records[0].citation_path == "us/regulation/45/604"
    assert placeholder.parent_id == records[0].id
    assert placeholder.level == 1
    assert placeholder.ordinal == ordinal
    assert placeholder.source_path == item.source_path
    assert placeholder.source_url == item.source_url
    assert item.sha256 == sha256_bytes(xml.encode())
    assert placeholder.metadata["structure_only"] is True
    assert placeholder.metadata["body_status"] == "not_in_ecfr_full_xml"
    assert placeholder.identifiers == {"ecfr:title": "45", "ecfr:part": "604", "ecfr:appendix": appendix_id.lower()}

    # A later XML snapshot supplies text without changing the provision's identity.
    xml_with_appendix = xml.replace('</DIV5>', f'<DIV9 N="{identifier}" TYPE="APPENDIX"><P>Official form text</P></DIV9></DIV5>')
    monkeypatch.setattr(ecfr, "fetch_ecfr_part_xml", lambda title, part, as_of: xml_with_appendix)
    parsed_report = extract_ecfr(CorpusArtifactStore(tmp_path / "present"), **kwargs)
    parsed = load_provisions(parsed_report.provisions_path)[-1]
    assert parsed.id == placeholder.id
    assert parsed.body == "Official form text"
    assert not parsed.metadata.get("structure_only")


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
        build_ecfr_inventory_from_structures((unsupported,), only_part="604", include_appendices=True)


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
                include_appendices=True,
            )
        )


@pytest.mark.parametrize(
    "identifier",
    ["Appendix II to Part 604", "Appendix to Subpart A of Part 604", ""],
)
def test_build_ecfr_inventory_section_scope_excludes_unsupported_appendices(identifier):
    structure = json.loads(json.dumps(SAMPLE_APPENDIX_STRUCTURE))
    structure["children"][0]["children"][0]["children"][1]["identifier"] = identifier

    inventory = build_ecfr_inventory_from_structures(
        (structure,), only_part="604", only_sections=("604.100",),
        include_appendices=True,
    )

    assert [item.citation_path for item in inventory.items] == [
        "us/regulation/45/604",
        "us/regulation/45/604/100",
    ]
    with pytest.raises(ValueError, match="unsupported nonreserved eCFR appendix"):
        build_ecfr_inventory_from_structures((structure,), only_part="604", include_appendices=True)


@pytest.mark.parametrize("with_subpart", [False, True])
@pytest.mark.parametrize(
    "allowed_paths",
    [
        set(),
        {"us/regulation/45/604", "us/regulation/45/604/100"},
        {"us/regulation/45/604/appendix-b"},
    ],
)
def test_iter_ecfr_title_provisions_scope_excludes_unsupported_appendix(
    with_subpart, allowed_paths
):
    xml = SAMPLE_APPENDIX_XML.replace("Appendix A to Part 604", "Appendix II to Part 604")
    if with_subpart:
        xml = xml.replace(
            '<DIV8 N="§ 604.100"',
            '<DIV6 N="A" TYPE="SUBPART"><HEAD>Subpart A-General</HEAD><DIV8 N="§ 604.100"',
        ).replace("</DIV8>", "</DIV8></DIV6>")

    records = tuple(
        iter_ecfr_title_provisions(
            xml,
            (EcfrPartTarget(title=45, part="604", chapter="VI"),),
            version="2026-08-30-title-45-part-604",
            source_path="ecfr/title-45-part-604.xml",
            allowed_citation_paths=allowed_paths,
            include_appendices=True,
        )
    )

    assert {record.citation_path for record in records} == allowed_paths
    if "us/regulation/45/604/appendix-b" in allowed_paths:
        assert "[Official source image: ecfr/graphics/EC01JA91.007.png]" in records[0].body


@pytest.mark.parametrize("retained_xml", [False, True])
def test_extract_ecfr_section_scope_excludes_unsupported_appendix_and_its_graphics(
    tmp_path, monkeypatch, retained_xml
):
    import axiom_corpus.corpus.ecfr as ecfr

    structure = json.loads(json.dumps(SAMPLE_APPENDIX_STRUCTURE))
    structure["children"][0]["children"][0]["children"][2]["identifier"] = (
        "Appendix II to Part 604"
    )
    xml = SAMPLE_APPENDIX_XML.replace("Appendix B to Part 604", "Appendix II to Part 604")
    monkeypatch.setattr(ecfr, "fetch_ecfr_structure", lambda title, as_of: structure)
    monkeypatch.setattr(ecfr, "fetch_ecfr_part_xml", lambda title, part, as_of: xml)
    monkeypatch.setattr(
        ecfr, "fetch_ecfr_graphic", lambda identifier: pytest.fail("excluded graphic fetched")
    )
    source_xml = None
    if retained_xml:
        source_xml = tmp_path / "official-part-604.xml"
        source_xml.write_text(xml)
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_ecfr(
        store,
        version="2026-08-30",
        as_of="2026-08-27",
        only_title=45,
        only_part="604",
        only_sections=("604.100",),
        source_xml=source_xml,
        include_appendices=True,
    )

    assert report.title_errors == ()
    assert report.coverage.complete
    assert report.provisions_written == 2
    records = load_provisions(report.provisions_path)
    assert [record.citation_path for record in records] == [
        "us/regulation/45/604",
        "us/regulation/45/604/100",
    ]
    assert records[1].body == "(a) No appropriated funds may be used for covered lobbying."
    assert [item.citation_path for item in load_source_inventory(report.inventory_path)] == [
        record.citation_path for record in records
    ]
    retained_path = next(path for path in report.source_paths if path.suffix == ".xml")
    assert retained_path.read_bytes() == xml.encode()
    assert not any(path.suffix == ".png" for path in report.source_paths)


def test_iter_ecfr_title_provisions_rejects_requested_unsupported_appendix():
    xml = SAMPLE_APPENDIX_XML.replace("Appendix A to Part 604", "Appendix II to Part 604")

    with pytest.raises(ValueError, match="unsupported nonreserved eCFR appendix XML identifier"):
        tuple(
            iter_ecfr_title_provisions(
                xml,
                (EcfrPartTarget(title=45, part="604", chapter="VI"),),
                version="2026-08-30-title-45-part-604",
                source_path="ecfr/title-45-part-604.xml",
                allowed_citation_paths={"us/regulation/45/604/appendix-ii"},
                include_appendices=True,
            )
        )



def _nested_appendix_xml(wrapper, identifier="A"):
    xml = SAMPLE_APPENDIX_XML.replace("Appendix A to Part 604", f"Appendix {identifier} to Part 604")
    start = '<DIV7 TYPE="SUBJECT"><HEAD>Forms</HEAD>'
    end = '</DIV7>'
    if wrapper == "subpart":
        start = '<DIV6 N="A" TYPE="SUBPART"><HEAD>Subpart A-General</HEAD>' + start
        end += '</DIV6>'
    else:
        # A sibling subpart used to switch traversal into a direct-child-only
        # mode that also lost appendices under a part-level subject group.
        start = '<DIV6 N="A" TYPE="SUBPART"><HEAD>Subpart A-General</HEAD></DIV6>' + start
    return xml.replace(f'<DIV9 N="Appendix {identifier} to Part 604"', start + f'<DIV9 N="Appendix {identifier} to Part 604"', 1).replace(
        '</DIV5>', end + '<DIV8 N="§ 604.200" TYPE="SECTION"><HEAD>§ 604.200 After forms.</HEAD><P>Text after forms.</P></DIV8></DIV5>'
    )


@pytest.mark.parametrize("wrapper", ["part", "subpart"])
def test_iter_ecfr_nested_appendices_preserves_source_order_and_selection(wrapper):
    xml = _nested_appendix_xml(wrapper)
    kwargs = {
        "targets": (EcfrPartTarget(title=45, part="604", chapter="VI"),),
        "version": "2026-08-30-title-45-part-604",
        "source_path": "ecfr/title-45-part-604.xml",
    }
    records = tuple(iter_ecfr_title_provisions(xml, **kwargs, include_appendices=True))
    assert [record.citation_path for record in records] == [
        "us/regulation/45/604", "us/regulation/45/604/100",
        "us/regulation/45/604/subpart-A", "us/regulation/45/604/appendix-a",
        "us/regulation/45/604/appendix-b", "us/regulation/45/604/200",
    ]
    assert "included in all subcontracts" in records[3].body
    assert "ecfr/graphics/EC01JA91.007.png" in records[4].body
    assert records[3].parent_citation_path == "us/regulation/45/604"
    selected = tuple(iter_ecfr_title_provisions(
        xml, **kwargs, allowed_citation_paths={"us/regulation/45/604/appendix-a"},
        include_appendices=True,
    ))
    assert selected == (records[3],)


@pytest.mark.parametrize("wrapper", ["part", "subpart"])
@pytest.mark.parametrize("allowed_paths", [None, {"us/regulation/45/604/appendix-ii"}])
def test_iter_ecfr_nested_appendices_rejects_requested_unsupported(wrapper, allowed_paths):
    with pytest.raises(ValueError, match="unsupported nonreserved eCFR appendix XML identifier"):
        tuple(iter_ecfr_title_provisions(
            _nested_appendix_xml(wrapper, "II"),
            (EcfrPartTarget(title=45, part="604", chapter="VI"),),
            version="2026-08-30-title-45-part-604",
            source_path="ecfr/title-45-part-604.xml",
            allowed_citation_paths=allowed_paths,
            include_appendices=True,
        ))


@pytest.mark.parametrize("wrapper", ["part", "subpart"])
@pytest.mark.parametrize("allowed_paths", [set(), {"us/regulation/45/604/appendix-b"}])
def test_iter_ecfr_nested_appendices_skips_excluded_unsupported(wrapper, allowed_paths):
    records = tuple(iter_ecfr_title_provisions(
        _nested_appendix_xml(wrapper, "II"),
        (EcfrPartTarget(title=45, part="604", chapter="VI"),),
        version="2026-08-30-title-45-part-604",
        source_path="ecfr/title-45-part-604.xml",
        allowed_citation_paths=allowed_paths,
        include_appendices=True,
    ))
    assert {record.citation_path for record in records} == allowed_paths


@pytest.mark.parametrize("retained_xml", [False, True])
def test_extract_ecfr_nested_section_scope_does_not_fetch_excluded_graphics(
    tmp_path, monkeypatch, retained_xml
):
    import axiom_corpus.corpus.ecfr as ecfr

    xml = _nested_appendix_xml("subpart", "II")
    structure = json.loads(json.dumps(SAMPLE_APPENDIX_STRUCTURE))
    structure["children"][0]["children"][0]["children"][1]["identifier"] = "Appendix II to Part 604"
    monkeypatch.setattr(ecfr, "fetch_ecfr_structure", lambda title, as_of: structure)
    monkeypatch.setattr(ecfr, "fetch_ecfr_part_xml", lambda title, part, as_of: xml)
    monkeypatch.setattr(ecfr, "fetch_ecfr_graphic", lambda identifier: pytest.fail("excluded graphic fetched"))
    source_xml = None
    if retained_xml:
        source_xml = tmp_path / "official.xml"
        source_xml.write_text(xml)
    report = extract_ecfr(
        CorpusArtifactStore(tmp_path / "corpus"), version="2026-08-30", as_of="2026-08-27",
        only_title=45, only_part="604", only_sections=("604.100",), source_xml=source_xml,
        include_appendices=True,
    )
    assert report.coverage.complete
    assert report.title_errors == ()
    assert [record.citation_path for record in load_provisions(report.provisions_path)] == [
        "us/regulation/45/604", "us/regulation/45/604/100",
    ]
    assert not any(path.suffix == ".png" for path in report.source_paths)



@pytest.mark.parametrize("wrapper", ["part", "subpart"])
def test_extract_ecfr_archives_selected_nested_appendix_graphics(tmp_path, monkeypatch, wrapper):
    import axiom_corpus.corpus.ecfr as ecfr

    xml = _nested_appendix_xml(wrapper)
    structure = json.loads(json.dumps(SAMPLE_APPENDIX_STRUCTURE))
    part = structure["children"][0]["children"][0]
    section, *appendices = part["children"]
    subject = {"type": "subject", "children": appendices}
    subpart = {"identifier": "A", "label": "Subpart A-General", "type": "subpart", "children": [subject] if wrapper == "subpart" else []}
    part["children"] = [section, subpart] + ([subject] if wrapper == "part" else []) + [
        {"identifier": "604.200", "label": "§ 604.200 After forms.", "type": "section"}
    ]
    graphics = {f"EC01JA91.00{number}": b"\x89PNG\r\n\x1a\n" + bytes([number]) for number in (7, 8, 9)}
    monkeypatch.setattr(ecfr, "fetch_ecfr_structure", lambda title, as_of: structure)
    monkeypatch.setattr(ecfr, "fetch_ecfr_part_xml", lambda title, part, as_of: xml)
    monkeypatch.setattr(ecfr, "fetch_ecfr_graphic", lambda identifier: graphics[identifier])
    report = extract_ecfr(
        CorpusArtifactStore(tmp_path / "corpus"), version="2026-08-30", as_of="2026-08-27",
        only_title=45, only_part="604",
        include_appendices=True,
    )
    assert report.coverage.complete
    assert report.title_errors == ()
    records = load_provisions(report.provisions_path)
    assert [record.citation_path for record in records] == [
        "us/regulation/45/604", "us/regulation/45/604/100", "us/regulation/45/604/subpart-A",
        "us/regulation/45/604/appendix-a", "us/regulation/45/604/appendix-b", "us/regulation/45/604/200",
    ]
    assert [item.citation_path for item in load_source_inventory(report.inventory_path)] == [record.citation_path for record in records]
    retained_graphics = {path.stem: path.read_bytes() for path in report.source_paths if path.suffix == ".png"}
    assert retained_graphics == graphics
    assert "[Official source image: ecfr/graphics/EC01JA91.007.png]" in records[4].body


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
            include_appendices=True,
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


@pytest.mark.parametrize("container", ["TABLE", "HED", "HD1", "HD2", "HD3"])
@pytest.mark.parametrize("mixed_text", [False, True])
def test_extract_ecfr_preserves_appendix_graphics_in_consumed_containers(
    tmp_path, monkeypatch, container, mixed_text
):
    import axiom_corpus.corpus.ecfr as ecfr

    images = '<IMG src="/graphics/EC01JA91.007.gif"/><IMG src="/graphics/EC01JA91.008.gif"/>'
    content = "Form " + images + " caption" if mixed_text else images
    if container == "TABLE":
        content = f"<TR><TD>{content}</TD></TR>"
    xml = (
        '<ECFR><DIV5 N="604" TYPE="PART"><HEAD>Part 604</HEAD>'
        '<DIV9 N="Appendix A to Part 604" TYPE="APPENDIX"><HEAD>Form</HEAD>'
        f'<{container}>{content}</{container}>'
        '</DIV9></DIV5></ECFR>'
    )
    structure = {
        "identifier": "45", "type": "title", "children": [{
            "identifier": "604", "type": "part", "children": [{
                "identifier": "Appendix A to Part 604", "type": "appendix"
            }]
        }]
    }
    graphics = {
        identifier: b"\x89PNG\r\n\x1a\n" + identifier.encode()
        for identifier in ("EC01JA91.007", "EC01JA91.008")
    }
    monkeypatch.setattr(ecfr, "fetch_ecfr_structure", lambda title, as_of: structure)
    monkeypatch.setattr(ecfr, "fetch_ecfr_part_xml", lambda title, part, as_of: xml)
    monkeypatch.setattr(ecfr, "fetch_ecfr_graphic", lambda identifier: graphics[identifier])

    report = extract_ecfr(
        CorpusArtifactStore(tmp_path / "corpus"), version="2026-08-30", as_of="2026-08-27",
        only_title=45, only_part="604",
        include_appendices=True,
    )

    assert report.coverage.complete
    assert report.title_errors == ()
    appendix = load_provisions(report.provisions_path)[-1]
    assert appendix.citation_path == "us/regulation/45/604/appendix-a"
    expected = ["Form caption"] if mixed_text else []
    expected += [f"[Official source image: ecfr/graphics/{identifier}.png]" for identifier in graphics]
    assert appendix.body.split("\n\n") == expected
    assert {path.stem: path.read_bytes() for path in report.source_paths if path.suffix == ".png"} == graphics


@pytest.mark.parametrize("container", ["TABLE", "HD2"])
def test_appendix_container_graphics_do_not_relabel_math_images(container):
    formula = '<MATH><IMG src="/graphics/ER07OC94.022.gif"/></MATH>'
    content = '<IMG src="/graphics/EC01JA91.007.gif"/>' + formula
    if container == "TABLE":
        content = f"<TR><TD>{content}</TD></TR>"
    xml = (
        '<ECFR><DIV5 N="604" TYPE="PART"><HEAD>Part 604</HEAD>'
        '<DIV9 N="Appendix A to Part 604" TYPE="APPENDIX"><HEAD>Form</HEAD>'
        f'<{container}>{content}</{container}>{formula}'
        '</DIV9></DIV5></ECFR>'
    )

    records = tuple(iter_ecfr_title_provisions(
        xml, (EcfrPartTarget(title=45, part="604"),),
        version="2026-08-30", source_path="ecfr/title-45-part-604.xml",
        graphic_transcriptions={"ER07OC94.022": "X = (a * b) / c"},
        include_appendices=True,
    ))

    # Non-math discovery must not turn a formula into an ordinary image.
    # Standalone MATH keeps its existing transcription behavior.
    assert records[-1].body.split("\n\n") == [
        "[Official source image: ecfr/graphics/EC01JA91.007.png]",
        "Formula (ER07OC94.022, verified official image): X = (a * b) / c",
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
            include_appendices=True,
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
        include_appendices=True,
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
