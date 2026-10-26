import json
import re
from pathlib import Path

import pytest
import yaml

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.eli import (
    EliInForce,
    extract_eli_documents,
    extract_lexdania_sections,
    parse_eli_graph,
    require_current_eli_act,
)
from axiom_corpus.corpus.io import load_provisions, load_source_inventory

FIXTURES = Path(__file__).parent / "fixtures" / "eli"


def _graph(name: str):
    return parse_eli_graph(json.loads((FIXTURES / name).read_text()))


def test_parse_current_denmark_eli_graph() -> None:
    metadata = _graph("dk-lta-2025-603.jsonld")
    assert metadata.eli_uri == "https://retsinformation.dk/eli/lta/2025/603"
    assert metadata.in_force is EliInForce.IN_FORCE
    assert metadata.changed_by == (
        "https://retsinformation.dk/eli/lta/2025/1642",
        "https://retsinformation.dk/eli/lta/2026/303",
    )
    assert metadata.consolidated_by == ()
    assert metadata.manifestation("pdf").legal_value == "definitive"  # type: ignore[union-attr]
    assert metadata.title_alternative == ("Børne- og ungeydelsesloven",)


def test_parse_superseded_denmark_eli_graph_and_manifestations() -> None:
    metadata = _graph("dk-lta-2022-724.jsonld")
    assert metadata.in_force is EliInForce.NOT_IN_FORCE
    assert metadata.consolidated_by == ("https://retsinformation.dk/eli/lta/2025/603",)
    assert len(metadata.changed_by) == 6
    assert {item.url for item in metadata.manifestations} == {
        "https://retsinformation.dk/eli/lta/2022/724/dan/xml",
        "https://retsinformation.dk/eli/lta/2022/724/dan/html",
        "https://retsinformation.dk/eli/lta/2022/724/dan/pdf",
    }


def test_parse_eli_graph_only_returns_formats_from_selected_expression() -> None:
    payload = json.loads((FIXTURES / "dk-lta-2025-603.jsonld").read_text())
    resource = payload[0]
    unrelated_expression_id = "https://retsinformation.dk/eli/lta/2025/603/eng"
    unrelated_format_id = f"{unrelated_expression_id}/xml"
    resource["http://data.europa.eu/eli/ontology#is_realized_by"].append(
        {"@id": unrelated_expression_id}
    )
    payload.extend(
        [
            {
                "@id": unrelated_expression_id,
                "@type": ["http://data.europa.eu/eli/ontology#LegalExpression"],
                "http://data.europa.eu/eli/ontology#language": [
                    {"@id": ("http://publications.europa.eu/resource/authority/language/eng")}
                ],
                "http://data.europa.eu/eli/ontology#is_embodied_by": [{"@id": unrelated_format_id}],
            },
            {
                "@id": unrelated_format_id,
                "@type": ["http://data.europa.eu/eli/ontology#Format"],
                "http://data.europa.eu/eli/ontology#format": [
                    {"@id": "http://www.iana.org/assignments/media-types/application/xml"}
                ],
            },
        ]
    )

    metadata = parse_eli_graph(payload, language="da")

    assert unrelated_format_id not in {item.url for item in metadata.manifestations}
    assert metadata.manifestation("xml").url.endswith("/dan/xml")  # type: ignore[union-attr]


def test_parse_eli_graph_selects_requested_legal_resource_when_it_is_second() -> None:
    other = json.loads((FIXTURES / "dk-lta-2022-724.jsonld").read_text())
    requested = json.loads((FIXTURES / "dk-lta-2025-603.jsonld").read_text())

    metadata = parse_eli_graph(
        [*other, *requested],
        language="da",
        expected_uri="http://retsinformation.dk/eli/lta/2025/603/",
    )

    assert metadata.eli_uri == "https://retsinformation.dk/eli/lta/2025/603"
    assert metadata.in_force is EliInForce.IN_FORCE


@pytest.mark.parametrize(
    ("actual", "expected"),
    [
        ("https://example.test/eli/act?value=/", "http://example.test/eli/act?value="),
        ("https://example.test/eli/act#part/", "http://example.test/eli/act#part"),
    ],
)
def test_parse_eli_graph_preserves_query_and_fragment_trailing_slashes_when_matching_uri(
    actual: str,
    expected: str,
) -> None:
    payload = json.loads((FIXTURES / "dk-lta-2025-603.jsonld").read_text())
    payload[0]["@id"] = actual

    with pytest.raises(ValueError, match="no LegalResource matching requested URI"):
        parse_eli_graph(payload, expected_uri=expected)


def test_parse_eli_graph_matches_http_and_https_with_path_trailing_slash_difference() -> None:
    payload = json.loads((FIXTURES / "dk-lta-2025-603.jsonld").read_text())

    metadata = parse_eli_graph(
        payload,
        expected_uri="http://retsinformation.dk/eli/lta/2025/603/",
    )

    assert metadata.eli_uri == "https://retsinformation.dk/eli/lta/2025/603"


def test_parse_eli_graph_without_language_selects_sole_expression() -> None:
    metadata = parse_eli_graph(
        json.loads((FIXTURES / "dk-lta-2025-603.jsonld").read_text())
    )

    assert metadata.title_alternative == ("Børne- og ungeydelsesloven",)


def test_currency_gate_refuses_superseded_and_allows_override() -> None:
    metadata = _graph("dk-lta-2022-724.jsonld")
    with pytest.raises(ValueError, match=r"superseded by .*2025/603.*allow-superseded"):
        require_current_eli_act(metadata)
    require_current_eli_act(metadata, allow_superseded=True)
    require_current_eli_act(_graph("dk-lta-2025-603.jsonld"))


def test_extract_lexdania_routes_consolidation_shape_to_paragraph_sections() -> None:
    sections = extract_lexdania_sections((FIXTURES / "dk-lta-2025-603.lexdania.xml").read_bytes())
    assert len(sections) == 24
    assert tuple(section.label for section in sections) == (
        "paragraf-1",
        "paragraf-1-a",
        "paragraf-2",
        "paragraf-3",
        "paragraf-4",
        "paragraf-4-a",
        "paragraf-4-b",
        "paragraf-4-c",
        "paragraf-4-d",
        "paragraf-4-e",
        "paragraf-5",
        "paragraf-6",
        "paragraf-6-a",
        "paragraf-7",
        "paragraf-8",
        "paragraf-8-a",
        "paragraf-8-b",
        "paragraf-9",
        "paragraf-10",
        "paragraf-11",
        "paragraf-12",
        "paragraf-13",
        "paragraf-14",
        "paragraf-15",
    )
    section_1 = next(section for section in sections if section.label == "paragraf-1")
    assert "16.992" in section_1.body
    assert "10.584" in section_1.body
    section_1a = next(section for section in sections if section.label == "paragraf-1-a")
    assert section_1a.metadata["paragraph_number"] == "1a"
    assert "700.000" in section_1a.body
    assert "børne- og ungeydelse" in section_1a.body
    assert "Stk. 2." in section_1a.body
    assert section_1.metadata["afsnit_number"] == "1"
    assert section_1.metadata["kapitel_number"] == "1"


def _extract_collision_fixture(
    tmp_path: Path, *, act_number: str, xml_fixture: str, act_year: str = "2025"
):
    eli_uri = f"https://retsinformation.dk/eli/lta/{act_year}/{act_number}"
    graph_url = f"https://example.test/{act_number}.json"
    xml_url = f"https://example.test/{act_number}.xml"
    source_id = f"dk-lta-{act_year}-{act_number}"
    manifest = tmp_path / f"eli-{act_number}.yaml"
    manifest.write_text(
        yaml.safe_dump(
            {
                "documents": [
                    {
                        "source_id": source_id,
                        "eli_uri": eli_uri,
                        "graph_url": graph_url,
                        "xml_url": xml_url,
                        "jurisdiction": "dk",
                        "document_class": "statute",
                        "citation_path": f"dk/statute/lta-{act_year}-{act_number}",
                        "title": source_id,
                        "language": "da",
                    }
                ]
            }
        )
    )
    graph_bytes = (FIXTURES / "dk-lta-2025-603.jsonld").read_bytes().replace(
        b"https://retsinformation.dk/eli/lta/2025/603", eli_uri.encode()
    )
    xml_bytes = (FIXTURES / xml_fixture).read_bytes()
    report = extract_eli_documents(
        CorpusArtifactStore(tmp_path / f"corpus-{act_number}"),
        manifest_path=manifest,
        version=f"ordered-{act_number}",
        fetcher={graph_url: graph_bytes, xml_url: xml_bytes}.__getitem__,
    )
    return (
        report,
        extract_lexdania_sections(xml_bytes),
        load_source_inventory(report.inventory_path),
        load_provisions(report.provisions_path),
    )


def test_extract_eli_documents_pins_ordered_collision_paths(tmp_path: Path) -> None:
    report, sections, inventory, provisions = _extract_collision_fixture(
        tmp_path,
        act_number="1004",
        xml_fixture="dk-lta-2025-1004-collisions.lexdania.xml",
    )
    expected_paths = (
        "dk/statute/lta-2025-1004",
        "dk/statute/lta-2025-1004/paragraf-28",
        "dk/statute/lta-2025-1004/afsnit-1-kapitel-4-paragraf-29",
        "dk/statute/lta-2025-1004/afsnit-1-kapitel-4-paragraf-30",
        "dk/statute/lta-2025-1004/afsnit-1-kapitel-4-paragraf-31",
        "dk/statute/lta-2025-1004/ikraft-paragraf-29",
        "dk/statute/lta-2025-1004/ikraft-paragraf-30",
        "dk/statute/lta-2025-1004/ikraft-paragraf-31",
    )
    expected_suffixes = (
        "paragraf-28",
        "afsnit-1-kapitel-4-paragraf-29",
        "afsnit-1-kapitel-4-paragraf-30",
        "afsnit-1-kapitel-4-paragraf-31",
        "ikraft-paragraf-29",
        "ikraft-paragraf-30",
        "ikraft-paragraf-31",
    )

    assert tuple(item.citation_path for item in inventory) == expected_paths
    assert tuple(record.citation_path for record in provisions) == expected_paths
    assert tuple(item.metadata["citation_suffix"] for item in inventory[1:]) == expected_suffixes
    assert (
        tuple(record.metadata["citation_suffix"] for record in provisions[1:])
        == expected_suffixes
    )
    assert len(inventory) == len(provisions) == len(sections) + 1 == 8
    assert report.block_count == len(sections) == 7
    assert report.provisions_written == 8
    assert report.coverage.complete
    persisted_coverage = json.loads(report.coverage_path.read_text())
    assert persisted_coverage["complete"] is True
    assert persisted_coverage["source_count"] == 8
    assert persisted_coverage["provision_count"] == 8
    assert persisted_coverage["matched_count"] == 8
    assert persisted_coverage["missing_from_provisions"] == []
    assert persisted_coverage["extra_provisions"] == []
    assert persisted_coverage["duplicate_source_citations"] == []
    assert persisted_coverage["duplicate_provision_citations"] == []


def test_extract_lexdania_pins_ordered_danish_letter_labels_to_grammar() -> None:
    sections = extract_lexdania_sections(
        (FIXTURES / "dk-lta-2025-1500-danish-letter-labels.lexdania.xml").read_bytes()
    )
    expected_labels = (
        "paragraf-7-ae",
        "paragraf-7-oe",
        "paragraf-7-aa",
    )

    assert tuple(section.label for section in sections) == expected_labels
    assert tuple(section.metadata["citation_suffix"] for section in sections) == expected_labels
    assert tuple(section.metadata["lexdania_local_id"] for section in sections) == (
        "7Æ",
        "7Ø",
        "7Å",
    )
    assert tuple(section.heading for section in sections) == (
        "§ 7 Æ.",
        "§ 7 Ø.",
        "§ 7 Å.",
    )

    schema_path = Path(__file__).resolve().parents[1] / "schema" / "citation-path.v1.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    citation_pattern = re.compile(schema["$defs"]["citation_path"]["pattern"])
    root_path = "dk/statute/lbk-1500-2025/ligningsloven"
    citation_paths = (root_path,) + tuple(f"{root_path}/{label}" for label in expected_labels)
    assert all(citation_pattern.fullmatch(path) for path in citation_paths)


def test_extract_lexdania_transliterates_structural_and_centered_local_ids() -> None:
    structural_xml = """\
        <Dokument id="structural-transliteration">
          <TitelGruppe>Artificial structural transliteration</TitelGruppe>
          <DokumentIndhold>
            <Afsnit localId="Æ"><Kapitel localId="É">
              <Paragraf localId="1"><Explicatus>§ 1.</Explicatus></Paragraf>
            </Kapitel></Afsnit>
            <Afsnit localId="Ø"><Kapitel localId="Å">
              <Paragraf localId="1"><Explicatus>§ 1.</Explicatus></Paragraf>
            </Kapitel></Afsnit>
          </DokumentIndhold>
        </Dokument>
    """.encode()
    structural_sections = extract_lexdania_sections(structural_xml)

    assert tuple(section.label for section in structural_sections) == (
        "afsnit-ae-kapitel-e-paragraf-1",
        "afsnit-oe-kapitel-aa-paragraf-1",
    )
    assert tuple(
        (section.metadata["afsnit_number"], section.metadata["kapitel_number"])
        for section in structural_sections
    ) == (("Æ", "É"), ("Ø", "Å"))

    centered_xml = """\
        <Dokument id="centered-transliteration">
          <TitelGruppe>Artificial centered transliteration</TitelGruppe>
          <DokumentIndhold>
            <AendringCentreretParagraf localId="7Æ">first</AendringCentreretParagraf>
            <AendringCentreretParagraf localId="7Ø">second</AendringCentreretParagraf>
            <AendringCentreretParagraf localId="7Å">third</AendringCentreretParagraf>
          </DokumentIndhold>
        </Dokument>
    """.encode()
    centered_sections = extract_lexdania_sections(centered_xml)

    assert tuple(section.label for section in centered_sections) == (
        "aendringcentreretparagraf-7-ae",
        "aendringcentreretparagraf-7-oe",
        "aendringcentreretparagraf-7-aa",
    )
    assert tuple(
        section.metadata["aendringcentreretparagraf_number"] for section in centered_sections
    ) == ("7Æ", "7Ø", "7Å")


@pytest.mark.parametrize(
    ("kind", "precomposed", "decomposed", "expected_label"),
    [
        ("Paragraf", "7Å", "7A\u030a", "paragraf-7-aa"),
        (
            "AendringCentreretParagraf",
            "7 Å",
            "7 A\u030a",
            "aendringcentreretparagraf-7-aa",
        ),
    ],
)
def test_extract_lexdania_nfc_normalizes_canonical_local_id_forms(
    kind: str,
    precomposed: str,
    decomposed: str,
    expected_label: str,
) -> None:
    def extract_label(local_id: str) -> str:
        xml = f"""\
            <Dokument id="canonical-local-id">
              <TitelGruppe>Artificial canonical localId</TitelGruppe>
              <DokumentIndhold>
                <{kind} localId="{local_id}">
                  <Explicatus>Identical unit content</Explicatus>
                </{kind}>
              </DokumentIndhold>
            </Dokument>
        """.encode()
        return extract_lexdania_sections(xml)[0].label

    precomposed_label = extract_label(precomposed)
    decomposed_label = extract_label(decomposed)

    assert precomposed_label.encode() == decomposed_label.encode()
    assert decomposed_label == expected_label


def test_extract_eli_documents_routes_amendment_wrappers_as_complete_units(
    tmp_path: Path,
) -> None:
    report, sections, inventory, provisions = _extract_collision_fixture(
        tmp_path,
        act_number="469",
        xml_fixture="dk-lta-2025-469-amendment-collisions.lexdania.xml",
    )
    expected_paths = (
        "dk/statute/lta-2025-469",
        "dk/statute/lta-2025-469/aendringcentreretparagraf-1",
        "dk/statute/lta-2025-469/aendringcentreretparagraf-2",
        "dk/statute/lta-2025-469/aendringcentreretparagraf-3",
    )
    expected_suffixes = (
        "aendringcentreretparagraf-1",
        "aendringcentreretparagraf-2",
        "aendringcentreretparagraf-3",
    )

    assert tuple(section.label for section in sections) == expected_suffixes
    assert "foretages følgende ændring:" in sections[0].body
    assert "Efter § 54 indsættes:" in sections[0].body
    assert "§ 54 a." in sections[0].body
    assert "Personer under 18 år må ikke anvendes som tolke" in sections[0].body
    assert not any(section.label.startswith("paragraf-") for section in sections)
    assert tuple(item.citation_path for item in inventory) == expected_paths
    assert tuple(record.citation_path for record in provisions) == expected_paths
    assert tuple(item.metadata["citation_suffix"] for item in inventory[1:]) == expected_suffixes
    assert (
        tuple(record.metadata["citation_suffix"] for record in provisions[1:])
        == expected_suffixes
    )
    assert len(inventory) == len(provisions) == len(sections) + 1 == 4
    assert report.block_count == len(sections) == 3
    assert report.provisions_written == 4
    assert report.coverage.complete


def test_extract_eli_documents_preserves_mixed_amendment_instructions(
    tmp_path: Path,
) -> None:
    report, sections, inventory, provisions = _extract_collision_fixture(
        tmp_path,
        act_number="1642",
        xml_fixture="dk-lta-2025-1642-mixed-amendment.lexdania.xml",
    )

    assert tuple(section.label for section in sections) == (
        "aendringcentreretparagraf-1",
        "aendringcentreretparagraf-7",
    )
    assert "ændres »12« til: »24«" in sections[0].body
    assert "Efter kapitel 7 a indsættes:" in sections[1].body
    assert "§ 44 b." in sections[1].body
    assert "Til brug for udbetaling af børne- og ungeydelse" in sections[1].body
    assert not any(section.label == "paragraf-44-b" for section in sections)
    assert tuple(item.metadata["citation_suffix"] for item in inventory[1:]) == (
        "aendringcentreretparagraf-1",
        "aendringcentreretparagraf-7",
    )
    assert tuple(record.metadata["citation_suffix"] for record in provisions[1:]) == (
        "aendringcentreretparagraf-1",
        "aendringcentreretparagraf-7",
    )
    assert report.block_count == 2
    assert report.provisions_written == 3
    assert report.coverage.complete


@pytest.mark.parametrize(
    ("act_year", "act_number", "xml_fixture", "expected_suffixes"),
    [
        (
            "2022",
            "252",
            "dk-lta-2022-252-amendment-only.lexdania.xml",
            (
                "aendringcentreretparagraf-1",
                "ikraftcentreretparagraf-2",
            ),
        ),
        (
            "2025",
            "198",
            "dk-lta-2025-198-amendment-only.lexdania.xml",
            (
                "aendringcentreretparagraf-1",
                "aendringcentreretparagraf-2",
                "aendringcentreretparagraf-3",
                "aendringcentreretparagraf-4",
                "aendringcentreretparagraf-5",
                "aendringcentreretparagraf-6",
                "aendringcentreretparagraf-7",
                "ikraftcentreretparagraf-8",
            ),
        ),
    ],
)
def test_extract_eli_documents_pins_centered_paths_and_coverage(
    tmp_path: Path,
    act_year: str,
    act_number: str,
    xml_fixture: str,
    expected_suffixes: tuple[str, ...],
) -> None:
    report, sections, inventory, provisions = _extract_collision_fixture(
        tmp_path,
        act_year=act_year,
        act_number=act_number,
        xml_fixture=xml_fixture,
    )
    root_path = f"dk/statute/lta-{act_year}-{act_number}"
    expected_paths = (root_path,) + tuple(
        f"{root_path}/{suffix}" for suffix in expected_suffixes
    )
    expected_count = len(expected_suffixes) + 1

    assert tuple(section.label for section in sections) == expected_suffixes
    assert all(section.body.strip() for section in sections)
    assert tuple(item.citation_path for item in inventory) == expected_paths
    assert tuple(record.citation_path for record in provisions) == expected_paths
    assert tuple(item.metadata["citation_suffix"] for item in inventory[1:]) == (
        expected_suffixes
    )
    assert tuple(record.metadata["citation_suffix"] for record in provisions[1:]) == (
        expected_suffixes
    )
    assert all(record.body and record.body.strip() for record in provisions[1:])
    assert len(inventory) == len(provisions) == expected_count
    assert report.block_count == len(expected_suffixes)
    assert report.provisions_written == expected_count
    assert report.coverage.complete
    assert json.loads(report.coverage_path.read_text()) == {
        "jurisdiction": "dk",
        "document_class": "statute",
        "version": f"ordered-{act_number}",
        "complete": True,
        "source_count": expected_count,
        "provision_count": expected_count,
        "matched_count": expected_count,
        "missing_from_provisions": [],
        "extra_provisions": [],
        "duplicate_source_citations": [],
        "duplicate_provision_citations": [],
    }


def test_extract_lexdania_centered_body_is_complete_normalized_itertext() -> None:
    sections = extract_lexdania_sections(
        (FIXTURES / "dk-lta-2022-252-amendment-only.lexdania.xml").read_bytes()
    )

    assert sections[1].label == "ikraftcentreretparagraf-2"
    assert sections[1].body == (
        "§ 2 Stk. 1. Loven træder i kraft den 1. marts 2022. "
        "Stk. 2. Loven har virkning fra og med indkomståret 2022."
    )


def test_extract_lexdania_fails_when_structure_cannot_disambiguate() -> None:
    xml = b"""\
        <Dokument id="same-afsnit-collision">
          <TitelGruppe>Artificial same-afsnit collision</TitelGruppe>
          <DokumentIndhold><Afsnit localId="2"><Kapitel localId="3">
            <Paragraf localId="29"><Explicatus>\xc2\xa7 29.</Explicatus></Paragraf>
            <Paragraf localId="29"><Explicatus>\xc2\xa7 29.</Explicatus></Paragraf>
          </Kapitel></Afsnit></DokumentIndhold>
        </Dokument>
    """

    with pytest.raises(
        ValueError,
        match="Artificial same-afsnit collision.*structurally disambiguate.*paragraph '29'",
    ):
        extract_lexdania_sections(xml)


def test_extract_lexdania_rejects_paragraph_transliteration_collision() -> None:
    xml = """\
        <Dokument id="paragraph-transliteration-collision">
          <TitelGruppe>Artificial paragraph transliteration collision</TitelGruppe>
          <DokumentIndhold>
            <Paragraf localId="7Æ"><Explicatus>§ 7 Æ.</Explicatus></Paragraf>
            <Paragraf localId="7AE"><Explicatus>§ 7 AE.</Explicatus></Paragraf>
          </DokumentIndhold>
        </Dokument>
    """.encode()

    with pytest.raises(ValueError) as caught:
        extract_lexdania_sections(xml)

    message = str(caught.value)
    assert "paragraph localIds '7Æ' and '7AE'" in message
    assert "collide after transliteration" in message
    assert "paragraf-7-ae" in message


def test_extract_lexdania_rejects_structural_transliteration_collision() -> None:
    xml = """\
        <Dokument id="structural-transliteration-collision">
          <TitelGruppe>Artificial structural transliteration collision</TitelGruppe>
          <DokumentIndhold>
            <Afsnit localId="Æ">
              <Paragraf localId="29"><Explicatus>§ 29.</Explicatus></Paragraf>
            </Afsnit>
            <Afsnit localId="AE">
              <Paragraf localId="29"><Explicatus>§ 29.</Explicatus></Paragraf>
            </Afsnit>
          </DokumentIndhold>
        </Dokument>
    """.encode()

    with pytest.raises(ValueError) as caught:
        extract_lexdania_sections(xml)

    message = str(caught.value)
    assert "cannot structurally disambiguate paragraph '29'" in message
    assert "Afsnit localId='Æ'" in message
    assert "Afsnit localId='AE'" in message
    assert "afsnit-ae-paragraf-29" in message


def test_extract_lexdania_allows_unique_labels_under_normalized_structural_ids() -> None:
    xml = """\
        <Dokument id="unique-final-labels">
          <TitelGruppe>Artificial unique final labels</TitelGruppe>
          <DokumentIndhold>
            <Afsnit localId="Æ">
              <Paragraf localId="1"><Explicatus>§ 1.</Explicatus></Paragraf>
            </Afsnit>
            <Afsnit localId="AE">
              <Paragraf localId="2"><Explicatus>§ 2.</Explicatus></Paragraf>
            </Afsnit>
          </DokumentIndhold>
        </Dokument>
    """.encode()

    assert tuple(section.label for section in extract_lexdania_sections(xml)) == (
        "paragraf-1",
        "paragraf-2",
    )


def test_extract_lexdania_collision_names_ancestor_without_local_id() -> None:
    xml = b"""\
        <Dokument id="ikraft-collision">
          <TitelGruppe>Artificial Ikraft collision</TitelGruppe>
          <DokumentIndhold>
            <Ikraft>
              <Paragraf localId="1"><Explicatus>first</Explicatus></Paragraf>
            </Ikraft>
            <Ikraft>
              <Paragraf localId="1"><Explicatus>second</Explicatus></Paragraf>
            </Ikraft>
          </DokumentIndhold>
        </Dokument>
    """

    with pytest.raises(ValueError) as caught:
        extract_lexdania_sections(xml)

    message = str(caught.value)
    assert "source chains Ikraft -> Paragraf localId='1'" in message
    assert "duplicate label 'ikraft-paragraf-1'" in message


def test_extract_lexdania_rejects_document_wide_final_label_collision(
    tmp_path: Path,
) -> None:
    pairs = (
        ("Æ", "Y PARAGRAF Z"),
        ("OTHER A", "Y PARAGRAF Z"),
        ("AE PARAGRAF Y", "Z"),
        ("OTHER B", "Z"),
    )
    units = "".join(
        f'<Afsnit localId="{afsnit}"><Paragraf localId="{paragraph}">'
        f"<Explicatus>{index}</Explicatus></Paragraf></Afsnit>"
        for index, (afsnit, paragraph) in enumerate(pairs)
    )
    xml = (
        f'<Dokument id="collision"><TitelGruppe>T</TitelGruppe>'
        f"<DokumentIndhold>{units}</DokumentIndhold></Dokument>"
    ).encode()

    with pytest.raises(ValueError) as caught:
        _extract_inline_eli_xml(tmp_path, xml)

    message = str(caught.value)
    assert "cannot structurally disambiguate paragraph 'Z'" in message
    assert (
        "Afsnit localId='Æ' -> Paragraf localId='Y PARAGRAF Z'" in message
    )
    assert "Afsnit localId='AE PARAGRAF Y' -> Paragraf localId='Z'" in message
    assert "duplicate label 'afsnit-ae-paragraf-y-paragraf-z'" in message
    artifact_root = tmp_path / "corpus-fail-closed"
    assert not tuple(path for path in artifact_root.rglob("*") if path.is_file())


def test_extract_lexdania_rejects_canonically_equivalent_local_ids() -> None:
    xml = """\
        <Dokument id="canonical-local-id-collision">
          <TitelGruppe>Artificial canonical localId collision</TitelGruppe>
          <DokumentIndhold>
            <Afsnit localId="1">
              <Paragraf localId="7Å"><Explicatus>A</Explicatus></Paragraf>
            </Afsnit>
            <Afsnit localId="2">
              <Paragraf localId="7A\u030a"><Explicatus>B</Explicatus></Paragraf>
            </Afsnit>
          </DokumentIndhold>
        </Dokument>
    """.encode()

    with pytest.raises(ValueError) as caught:
        extract_lexdania_sections(xml)

    message = str(caught.value)
    assert "paragraph localIds '7Å' and '7A\u030a'" in message
    assert "Afsnit localId='1' -> Paragraf localId='7Å'" in message
    assert "Afsnit localId='2' -> Paragraf localId='7A\u030a'" in message
    assert "duplicate label 'paragraf-7-aa'" in message


def test_extract_lexdania_rejects_non_lexdania_xml() -> None:
    with pytest.raises(ValueError, match="not a LexDania"):
        extract_lexdania_sections(b"<document><section>text</section></document>")


def _extract_inline_eli_xml(tmp_path: Path, xml_bytes: bytes) -> None:
    eli_uri = "https://retsinformation.dk/eli/lta/2025/9999"
    graph_url = "https://example.test/fail-closed.json"
    xml_url = "https://example.test/fail-closed.xml"
    manifest = tmp_path / "eli-fail-closed.yaml"
    manifest.write_text(
        yaml.safe_dump(
            {
                "documents": [
                    {
                        "source_id": "dk-lta-2025-9999-fail-closed",
                        "eli_uri": eli_uri,
                        "graph_url": graph_url,
                        "xml_url": xml_url,
                        "jurisdiction": "dk",
                        "document_class": "statute",
                        "citation_path": "dk/statute/lta-2025-9999",
                        "title": "Artificial manifest title",
                        "language": "da",
                    }
                ]
            }
        )
    )
    graph_bytes = (FIXTURES / "dk-lta-2025-603.jsonld").read_bytes().replace(
        b"https://retsinformation.dk/eli/lta/2025/603", eli_uri.encode()
    )
    extract_eli_documents(
        CorpusArtifactStore(tmp_path / "corpus-fail-closed"),
        manifest_path=manifest,
        version="fail-closed",
        fetcher={graph_url: graph_bytes, xml_url: xml_bytes}.__getitem__,
    )


@pytest.mark.parametrize(
    ("case_name", "content", "expected_tokens"),
    [
        (
            "empty-unit",
            '<AendringCentreretParagraf localId="1" />',
            ("AendringCentreretParagraf", "localId '1'", "yields empty text"),
        ),
        (
            "duplicate-label",
            (
                '<AendringCentreretParagraf localId="1-a">first</AendringCentreretParagraf>'
                '<AendringCentreretParagraf localId="1 a">second</AendringCentreretParagraf>'
            ),
            ("AendringCentreretParagraf", "duplicate label", "1-a"),
        ),
        (
            "transliteration-collision",
            (
                '<AendringCentreretParagraf localId="7Ø">first</AendringCentreretParagraf>'
                '<AendringCentreretParagraf localId="7OE">second</AendringCentreretParagraf>'
            ),
            (
                "AendringCentreretParagraf",
                "localIds '7Ø' and '7OE'",
                "duplicate label",
                "aendringcentreretparagraf-7-oe",
            ),
        ),
        (
            "missing-id",
            "<AendringCentreretParagraf>instruction</AendringCentreretParagraf>",
            ("AendringCentreretParagraf", "missing its localId"),
        ),
        (
            "unusable-id",
            (
                '<AendringCentreretParagraf localId="---">'
                "instruction</AendringCentreretParagraf>"
            ),
            ("AendringCentreretParagraf", "unusable localId '---'"),
        ),
        (
            "unknown-direct-element",
            (
                "<Hymne>preamble</Hymne>"
                '<AendringCentreretParagraf localId="1">instruction</AendringCentreretParagraf>'
                "<Ukendt>lost text</Ukendt>"
            ),
            ("DokumentIndhold", "unknown direct element(s): Ukendt"),
        ),
        (
            "content-text",
            (
                "leaked at content level"
                '<AendringCentreretParagraf localId="1">instruction</AendringCentreretParagraf>'
            ),
            ("DokumentIndhold.text", "leaked at content level"),
        ),
        (
            "child-tail",
            (
                '<AendringCentreretParagraf localId="1">instruction</AendringCentreretParagraf>'
                "leaked tail"
                '<IkraftCentreretParagraf localId="2">commencement</IkraftCentreretParagraf>'
            ),
            ("AendringCentreretParagraf localId='1'", "non-whitespace tail", "leaked tail"),
        ),
        (
            "mixed-direct-shapes",
            (
                '<Paragraf localId="1"><Explicatus>standard</Explicatus></Paragraf>'
                '<AendringCentreretParagraf localId="1">centered</AendringCentreretParagraf>'
            ),
            ("mixes direct standard", "Paragraf", "AendringCentreretParagraf"),
        ),
        (
            "no-operative-units",
            "<Hymne>preamble only</Hymne>",
            ("no supported operative units", "Hymne"),
        ),
        (
            "indledning-with-nested-paragraph",
            (
                '<Indledning><Paragraf localId="1">'
                "nested but not an operative direct root"
                "</Paragraf></Indledning>"
            ),
            ("no supported operative units", "Indledning"),
        ),
    ],
    ids=lambda value: value if isinstance(value, str) and "<" not in value else None,
)
def test_extract_eli_documents_fails_closed_with_document_and_unit_identity(
    tmp_path: Path,
    case_name: str,
    content: str,
    expected_tokens: tuple[str, ...],
) -> None:
    del case_name
    xml = f"""\
        <Dokument id="fail-closed-document">
          <TitelGruppe>Artificial fail-closed act</TitelGruppe>
          <DokumentIndhold>{content}</DokumentIndhold>
        </Dokument>
    """.encode()

    with pytest.raises(ValueError) as caught:
        _extract_inline_eli_xml(tmp_path, xml)

    message = str(caught.value)
    assert "source_id='dk-lta-2025-9999-fail-closed'" in message
    assert "eli='https://retsinformation.dk/eli/lta/2025/9999'" in message
    assert "title='Artificial manifest title'" in message
    assert "title='Artificial fail-closed act'" in message
    assert "root_id='fail-closed-document'" in message
    for token in expected_tokens:
        assert token in message


def test_extract_eli_documents_writes_standard_artifacts_with_injected_fetcher(
    tmp_path: Path,
) -> None:
    graph_url = "https://example.test/603.json"
    xml_url = "https://example.test/603.xml"
    manifest = tmp_path / "eli.yaml"
    manifest.write_text(
        yaml.safe_dump(
            {
                "documents": [
                    {
                        "source_id": "dk-lta-2025-603",
                        "eli_uri": "https://retsinformation.dk/eli/lta/2025/603",
                        "graph_url": graph_url,
                        "xml_url": xml_url,
                        "jurisdiction": "dk",
                        "document_class": "statute",
                        "citation_path": "dk/statute/lta-2025-603",
                        "title": "Børne- og ungeydelsesloven",
                        "language": "da",
                    }
                ]
            }
        )
    )
    payloads = {
        graph_url: (FIXTURES / "dk-lta-2025-603.jsonld").read_bytes(),
        xml_url: (FIXTURES / "dk-lta-2025-603.lexdania.xml").read_bytes(),
    }
    report = extract_eli_documents(
        CorpusArtifactStore(tmp_path / "corpus"),
        manifest_path=manifest,
        version="2025-06-03",
        fetcher=payloads.__getitem__,
    )
    assert report.coverage.complete
    assert report.block_count == 24
    assert report.provisions_written == 25
    assert len(report.source_paths) == 2
    assert report.inventory_path.exists()
    assert report.coverage_path.exists()
    inventory = load_source_inventory(report.inventory_path)
    provisions = load_provisions(report.provisions_path)
    assert len(inventory) == len(provisions) == 25
    section = next(row for row in provisions if row.citation_path.endswith("/paragraf-1-a"))
    assert section.level == 2
    assert section.language == "da"
    assert section.metadata["eli_changed_by"] == [
        "https://retsinformation.dk/eli/lta/2025/1642",
        "https://retsinformation.dk/eli/lta/2026/303",
    ]
    assert section.metadata["eli_consolidates"][0].endswith("/2022/724")
    assert section.expression_date == "2025-05-12"


def _two_document_manifest(tmp_path: Path) -> tuple[Path, dict[str, bytes]]:
    manifest = tmp_path / "eli-two.yaml"
    documents = []
    payloads: dict[str, bytes] = {}
    for source_id, fixture in (
        ("current", "dk-lta-2025-603.jsonld"),
        ("later", "dk-lta-2022-724.jsonld"),
    ):
        graph_url = f"https://example.test/{source_id}.json"
        xml_url = f"https://example.test/{source_id}.xml"
        documents.append(
            {
                "source_id": source_id,
                "eli_uri": {
                    "current": "https://retsinformation.dk/eli/lta/2025/603",
                    "later": "https://retsinformation.dk/eli/lta/2022/724",
                }[source_id],
                "graph_url": graph_url,
                "xml_url": xml_url,
                "jurisdiction": "dk",
                "document_class": "statute",
                "citation_path": f"dk/statute/{source_id}",
                "title": source_id,
                "language": "da",
            }
        )
        payloads[graph_url] = (FIXTURES / fixture).read_bytes()
        payloads[xml_url] = (FIXTURES / "dk-lta-2025-603.lexdania.xml").read_bytes()
    manifest.write_text(yaml.safe_dump({"documents": documents}))
    return manifest, payloads


def test_extract_eli_documents_superseded_later_document_leaves_store_untouched(
    tmp_path: Path,
) -> None:
    manifest, payloads = _two_document_manifest(tmp_path)
    corpus = tmp_path / "corpus"

    with pytest.raises(ValueError, match=r"source_id='later'.*superseded"):
        extract_eli_documents(
            CorpusArtifactStore(corpus),
            manifest_path=manifest,
            version="audit",
            fetcher=payloads.__getitem__,
        )

    assert not any(corpus.rglob("*"))


def test_extract_eli_documents_invalid_later_xml_leaves_store_untouched(
    tmp_path: Path,
) -> None:
    manifest, payloads = _two_document_manifest(tmp_path)
    payloads["https://example.test/later.xml"] = b"<broken"
    corpus = tmp_path / "corpus"

    with pytest.raises(
        ValueError,
        match=r"source_id='later'.*eli=.*2022/724.*invalid LexDania XML",
    ):
        extract_eli_documents(
            CorpusArtifactStore(corpus),
            manifest_path=manifest,
            version="audit",
            allow_superseded=True,
            fetcher=payloads.__getitem__,
        )

    assert not any(corpus.rglob("*"))


def test_extract_eli_documents_mismatched_later_graph_leaves_store_untouched(
    tmp_path: Path,
) -> None:
    manifest, payloads = _two_document_manifest(tmp_path)
    payloads["https://example.test/later.json"] = payloads[
        "https://example.test/current.json"
    ]
    corpus = tmp_path / "corpus"

    with pytest.raises(
        ValueError,
        match=(
            r"source_id='later'.*requested URI .*2022/724.*"
            r"found LegalResource URI\(s\).*2025/603"
        ),
    ):
        extract_eli_documents(
            CorpusArtifactStore(corpus),
            manifest_path=manifest,
            version="audit",
            fetcher=payloads.__getitem__,
        )

    assert not any(corpus.rglob("*"))


def test_extract_eli_documents_unavailable_language_leaves_store_untouched(
    tmp_path: Path,
) -> None:
    manifest, payloads = _two_document_manifest(tmp_path)
    graph = json.loads(payloads["https://example.test/later.json"])
    resource = graph[0]
    expression = next(
        node
        for node in graph
        if "http://data.europa.eu/eli/ontology#LegalExpression" in node.get("@type", [])
    )
    english_expression_id = expression["@id"].rsplit("/", 1)[0] + "/eng"
    resource["http://data.europa.eu/eli/ontology#is_realized_by"] = [
        {"@id": english_expression_id}
    ]
    expression["@id"] = english_expression_id
    expression["http://data.europa.eu/eli/ontology#language"] = [
        {"@id": "http://publications.europa.eu/resource/authority/language/eng"}
    ]
    payloads["https://example.test/later.json"] = json.dumps(graph).encode()
    corpus = tmp_path / "corpus"

    with pytest.raises(
        ValueError,
        match=r"source_id='later'.*requested language 'da'; available languages: eng",
    ):
        extract_eli_documents(
            CorpusArtifactStore(corpus),
            manifest_path=manifest,
            version="audit",
            fetcher=payloads.__getitem__,
        )

    assert not any(corpus.rglob("*"))
