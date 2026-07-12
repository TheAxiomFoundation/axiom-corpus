import json
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


def test_extract_lexdania_paragraph_sections() -> None:
    sections = extract_lexdania_sections((FIXTURES / "dk-lta-2025-603.lexdania.xml").read_bytes())
    assert len(sections) == 24
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


def test_extract_lexdania_rejects_non_lexdania_xml() -> None:
    with pytest.raises(ValueError, match="not a LexDania"):
        extract_lexdania_sections(b"<document><section>text</section></document>")


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

    with pytest.raises(ValueError, match="superseded"):
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

    with pytest.raises(ValueError, match="invalid LexDania XML"):
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
        match=r"requested URI .*2022/724.*found LegalResource URI\(s\).*2025/603",
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
        match=r"requested language 'da'; available languages: eng",
    ):
        extract_eli_documents(
            CorpusArtifactStore(corpus),
            manifest_path=manifest,
            version="audit",
            fetcher=payloads.__getitem__,
        )

    assert not any(corpus.rglob("*"))
