"""Public-law extraction keeps amendment instructions and their quoted law together."""

import json
from pathlib import Path

import pytest
import yaml

from axiom_corpus.corpus.artifacts import CorpusArtifactStore, sha256_bytes
from axiom_corpus.corpus.documents import OfficialDocumentSource
from axiom_corpus.corpus.public_laws import extract_public_laws, parse_public_law

SOURCE_URL = "https://www.govinfo.gov/content/pkg/PLAW-119publ21/uslm/PLAW-119publ21.xml"
ROOT = "us/statute/pl/119/21"
XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<pLaw xmlns="http://schemas.gpo.gov/xml/uslm">
 <meta><congress>119</congress><docNumber>21</docNumber>
 <publicPrivate>public</publicPrivate><approvedDate>2025-07-04</approvedDate></meta>
 <main><title><section identifier="/us/pl/119/21/tVII/s70104" id="s70104">
 <num value="70104">SEC. 70104. </num><heading>CHILD TAX CREDIT.</heading>
 <subsection identifier="/us/pl/119/21/tVII/s70104/a" id="a">
 <num value="a">(a) </num><heading>Increase.</heading>
 <chapeau>Section 24(h) is amended-</chapeau>
 <paragraph identifier="/us/pl/119/21/tVII/s70104/a/2" id="a2">
 <num value="2">(2) </num><content>by striking <quotedText>"$2,000"</quotedText>
 and inserting <quotedText>"$2,200"</quotedText>.</content></paragraph></subsection>
 <subsection identifier="/us/pl/119/21/tVII/s70104/b" id="b">
 <num value="b">(b) </num><heading>Social Security Number Required.</heading>
 <content>Section 24(h)(7) is amended to read as follows:
 <quotedContent><paragraph><num value="7">"(7) </num><heading>Social security number.</heading>
 <content>The taxpayer's <page>139 STAT. 161</page>social security number
 <sidenote><p>Definition.</p></sidenote>and the child's number."</content></paragraph>
 <section><num value="999">SEC. 999.</num><content>A quoted section.</content></section>
 </quotedContent>.</content></subsection>
 <subsection identifier="/us/pl/119/21/tVII/s70104/f" id="f">
 <num value="f">(f) </num><heading>Effective Date.</heading>
 <content>The amendments made by this section shall apply to taxable years beginning
 after December 31, 2024.</content></subsection></section>
 <section><num value="70105">SEC. 70105.</num><content>Unrelated amendment.</content></section>
 </title></main></pLaw>"""


def source(**kwargs):
    return OfficialDocumentSource(
        source_id="PLAW-119publ21",
        jurisdiction="us",
        document_class="statute",
        title="Public Law 119-21",
        source_url=SOURCE_URL,
        **kwargs,
    )


def test_parse_public_law_preserves_amendments_and_quotes():
    records = parse_public_law(XML, source=source(), version="test", sections=("70104",))
    by_path = {record.citation_path: record for record in records}
    assert set(by_path) == {
        ROOT,
        f"{ROOT}/70104",
        f"{ROOT}/70104/a",
        f"{ROOT}/70104/a/2",
        f"{ROOT}/70104/b",
        f"{ROOT}/70104/f",
    }
    amendment = by_path[f"{ROOT}/70104/a/2"]
    assert amendment.body == 'by striking "$2,000" and inserting "$2,200".'
    assert amendment.parent_id == by_path[f"{ROOT}/70104/a"].id
    assert amendment.legal_identifier == "/us/pl/119/21/tVII/s70104/a/2"
    body = by_path[f"{ROOT}/70104/b"].body
    assert body is not None
    assert '"(7)' in body
    assert "The taxpayer's social security number and the child's number." in body
    assert "139 STAT." not in body
    assert "Definition." not in body
    assert "A quoted section." in body
    assert "Unrelated amendment" not in (by_path[f"{ROOT}/70104"].body or "")
    assert "after December 31, 2024" in (by_path[f"{ROOT}/70104/f"].body or "")
    assert all(record.expression_date == "2025-07-04" for record in records)
    assert all(record.source_url == SOURCE_URL for record in records)
    assert all(record.metadata["selected_sections"] == ["70104"] for record in records)


@pytest.mark.parametrize("section", ["999", "11022"])
def test_parse_public_law_fails_for_missing_or_quoted_section(section):
    with pytest.raises(ValueError, match="sections not found"):
        parse_public_law(XML, source=source(), version="test", sections=(section,))


@pytest.mark.parametrize(
    "kwargs,match",
    [
        ({"expression_date": "2024-12-31"}, "approvedDate"),
        ({"citation_path": "us/statute/26/24"}, "citation_path"),
        ({"download_url": SOURCE_URL.replace("119publ21", "115publ97")}, "law identity"),
    ],
)
def test_parse_public_law_fails_for_conflicting_provenance(kwargs, match):
    with pytest.raises(ValueError, match=match):
        parse_public_law(XML, source=source(**kwargs), version="test", sections=("70104",))


def test_extract_public_laws_writes_all_artifacts_without_network(tmp_path):
    download_dir = tmp_path / "downloads"
    download_dir.mkdir()
    (download_dir / "PLAW-119publ21.xml").write_bytes(XML)
    manifest = tmp_path / "public-laws.yaml"
    manifest.write_text(
        yaml.safe_dump(
            {
                "documents": [
                    {
                        "source_id": "PLAW-119publ21",
                        "jurisdiction": "us",
                        "document_class": "statute",
                        "title": "Public Law 119-21",
                        "source_url": SOURCE_URL,
                        "citation_path": ROOT,
                        "expression_date": "2025-07-04",
                        "source_as_of": "2025-07-04",
                        "extraction": {"sections": ["70104"]},
                    }
                ]
            }
        )
    )
    store = CorpusArtifactStore(tmp_path / "corpus")
    report = extract_public_laws(
        store,
        manifest_path=manifest,
        version="ctc-history",
        download_dir=download_dir,
    )
    assert report.coverage.complete
    assert report.provisions_written == 6
    assert report.block_count == 5
    assert report.source_paths[0].read_bytes() == XML
    inventory = json.loads(report.inventory_path.read_text())["items"]
    assert {item["sha256"] for item in inventory} == {sha256_bytes(XML)}
    provisions = [json.loads(line) for line in report.provisions_path.read_text().splitlines()]
    assert {item["source_path"] for item in inventory} == {row["source_path"] for row in provisions}
    assert len(json.loads(report.coverage_path.read_text())["missing_from_provisions"]) == 0
    assert all((store.root / row["source_path"]).is_file() for row in provisions)


@pytest.mark.parametrize("sections", [[], ["70104", "70104"], ["../70104"], "70104"])
def test_extract_public_laws_rejects_invalid_section_selection(tmp_path, sections):
    manifest = tmp_path / "public-laws.yaml"
    manifest.write_text(
        yaml.safe_dump(
            {
                "documents": [
                    {
                        "source_id": "PLAW-119publ21",
                        "jurisdiction": "us",
                        "document_class": "statute",
                        "title": "Public Law 119-21",
                        "source_url": SOURCE_URL,
                        "extraction": {"sections": sections},
                    }
                ]
            }
        )
    )
    with pytest.raises(ValueError):
        extract_public_laws(
            CorpusArtifactStore(tmp_path / "corpus"), manifest_path=manifest, version="v1"
        )


def test_extract_public_laws_cli(tmp_path, capsys):
    from axiom_corpus.corpus.cli import main

    source_path = tmp_path / "law.xml"
    source_path.write_bytes(XML)
    manifest = tmp_path / "public-laws.yaml"
    manifest.write_text(
        yaml.safe_dump(
            {
                "documents": [
                    {
                        "source_id": "PLAW-119publ21",
                        "jurisdiction": "us",
                        "document_class": "statute",
                        "title": "Public Law 119-21",
                        "source_url": SOURCE_URL,
                        "local_path": str(source_path),
                        "extraction": {"sections": ["70104"]},
                    }
                ]
            }
        )
    )
    assert (
        main(
            [
                "extract-public-laws",
                "--base",
                str(tmp_path / "corpus"),
                "--manifest",
                str(manifest),
                "--version",
                "test",
            ]
        )
        == 0
    )
    output = json.loads(capsys.readouterr().out)
    assert output["coverage_complete"] is True
    assert output["provisions_written"] == 6
    assert Path(output["provisions_path"]).is_file()


def test_retained_ctc_public_laws_ground_both_enacted_amendments():
    from axiom_corpus.corpus.documents import OfficialDocumentManifest

    repo = Path(__file__).resolve().parents[1]
    manifest = OfficialDocumentManifest.load(repo / "manifests/us-ctc-history-public-laws.yaml")
    snapshots = (
        repo / "data/corpus/sources/us/statute/2026-09-27-ctc-history-public-laws/public-laws"
    )
    by_path = {}
    for document in manifest.documents:
        selected = tuple(str(value) for value in document.extraction["sections"])
        records = parse_public_law(
            (snapshots / f"{document.source_id}.xml").read_bytes(),
            source=document,
            version="ctc-regression",
            sections=selected,
        )
        by_path.update({record.citation_path: record for record in records})
    assert len(by_path) == 15
    enhancement = f"{ROOT}/70104"
    amount = by_path[f"{enhancement}/a/2"].body
    assert "striking “$2,000” and inserting “$2,200”" in amount
    ssn = by_path[f"{enhancement}/b"].body
    assert "the taxpayer’s social security number" in ssn
    assert "the social security number of such qualifying child" in ssn
    inflation = by_path[f"{enhancement}/c"].body
    assert "Section 24(i) is amended to read as follows" in inflation
    assert "In the case of a taxable year beginning after 2024" in inflation
    assert "In the case of a taxable year beginning after 2025" in inflation
    refund = by_path[f"{enhancement}/d"].body
    assert "Section 24(h)(5) is amended" in refund
    assert "shall not exceed $1,400" in refund
    assert "taxable years beginning after December 31, 2024" in by_path[f"{enhancement}/f"].body
    tcja = "us/statute/pl/115/97/11022"
    original = by_path[f"{tcja}/a"].body
    assert "substituting ‘$2,000’ for ‘$1,000’" in original
    assert "In the case of a taxable year beginning after 2018, the $1,400 amount" in original
    assert "the social security number of such child on the return" in original
    assert "taxable years beginning after December 31, 2017" in by_path[f"{tcja}/b"].body
    assert by_path[enhancement].expression_date == "2025-07-04"
    assert by_path[tcja].expression_date == "2017-12-22"
