from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from axiom_corpus.corpus.documents import OfficialDocumentManifest, _extract_blocks

REPO_ROOT = Path(__file__).resolve().parents[1]
SPAIN_MANIFEST = REPO_ROOT / "manifests/es-wealth-tax-statutes-official-documents.yaml"
FAMILY_MANIFEST = REPO_ROOT / "manifests/ch-wealth-tax-family-statute-official-documents.yaml"
NORWAY_GUIDANCE_MANIFEST = REPO_ROOT / "manifests/no-wealth-tax-guidance-official-documents.yaml"
ZURICH_MANIFEST = REPO_ROOT / "manifests/ch-zh-wealth-tax-official-documents.yaml"
WEALTH_TAX_MANIFESTS = tuple(
    REPO_ROOT / "manifests" / name
    for name in (
        "ch-wealth-tax-family-statute-official-documents.yaml",
        "ch-zh-wealth-tax-factor-statute-official-documents.yaml",
        "ch-zh-wealth-tax-guidance-official-documents.yaml",
        "ch-zh-wealth-tax-official-documents.yaml",
        "es-an-wealth-tax-rebate-official-documents.yaml",
        "es-ga-wealth-tax-rebate-official-documents.yaml",
        "es-md-wealth-tax-rebate-official-documents.yaml",
        "es-wealth-tax-statutes-official-documents.yaml",
        "fr-ifi-2022-statute-official-documents.yaml",
        "no-wealth-tax-guidance-official-documents.yaml",
        "no-wealth-tax-statutes-official-documents.yaml",
    )
)


def _source(manifest_path: Path, source_id: str):
    manifest = OfficialDocumentManifest.load(manifest_path)
    return next(source for source in manifest.documents if source.source_id == source_id)


def test_wealth_tax_manifests_are_single_scope_and_complete() -> None:
    documents = [
        source
        for manifest_path in WEALTH_TAX_MANIFESTS
        for source in OfficialDocumentManifest.load(manifest_path).documents
    ]

    assert len(WEALTH_TAX_MANIFESTS) == 11
    assert len(documents) == 19
    assert len({source.source_id for source in documents}) == 19
    assert len({source.citation_path for source in documents}) == 19
    for manifest_path in WEALTH_TAX_MANIFESTS:
        manifest = OfficialDocumentManifest.load(manifest_path)
        assert (
            len({(source.jurisdiction, source.document_class) for source in manifest.documents})
            == 1
        ), manifest_path


def test_sthg_family_source_extracts_only_article_3() -> None:
    source = _source(FAMILY_MANIFEST, "ch-sthg-art-3-family-tax-unit")
    html = b"""
    <main>
      <h3>Art. 2 Prior provision</h3>
      <p>Prior body.</p>
      <h3>Art. 3 Family taxation</h3>
      <p>Article 3 family-unit body.</p>
      <h3>Art. 4 Following provision</h3>
      <p>Following body.</p>
    </main>
    """

    blocks = _extract_blocks(
        html,
        "html",
        source_url=source.source_url,
        title=source.title,
        extraction=source.extraction,
    )

    assert len(blocks) == 1
    assert blocks[0].metadata["citation_suffix"] == "art-3"
    assert blocks[0].body == "Article 3 family-unit body."


@pytest.mark.parametrize(
    "source_id",
    (
        "no-forskuddsmeldingen-2022-wealth-tax",
        "no-forskuddsmeldingen-2023-wealth-tax",
    ),
)
def test_norway_annual_guidance_stops_before_unrelated_property_sections(
    source_id: str,
) -> None:
    source = _source(NORWAY_GUIDANCE_MANIFEST, source_id)
    html = b"""
    <main>
      <h2>Formue</h2>
      <p>Allowance and rate body.</p>
      <h2>Boligeiendom</h2>
      <p>Housing body.</p>
      <h2>Formuesverdi av aksjer, egenkapitalbevis og verdipapirfondsandeler</h2>
      <p>Share body.</p>
      <h2>Formuesverdi for deltaker i selskap med deltakerfastsetting</h2>
      <p>Partnership body.</p>
      <h2>Formuesverdi n&#230;ringseiendom</h2>
      <p>Unrelated business-property body.</p>
      <h2>Utland</h2>
      <p>Unrelated foreign-property body.</p>
    </main>
    """

    blocks = _extract_blocks(
        html,
        "html",
        source_url=source.source_url,
        title=source.title,
        extraction=source.extraction,
    )

    assert [block.metadata["citation_suffix"] for block in blocks] == [
        "formue",
        "boligeiendom",
        "formuesverdi-aksjer",
        "formuesverdi-deltaker",
    ]
    assert blocks[-1].body == "Partnership body."
    assert all("business-property" not in block.body for block in blocks)


@pytest.mark.parametrize(
    ("manifest_name", "source_id", "prior", "target", "following"),
    (
        (
            "es-an-wealth-tax-rebate-official-documents.yaml",
            "es-an-decreto-ley-7-2022-wealth-tax-rebate",
            "preliminar",
            "primero",
            "segundo",
        ),
        (
            "es-ga-wealth-tax-rebate-official-documents.yaml",
            "es-ga-ley-18-2021-wealth-tax-rebate",
            "1",
            "2",
            "3",
        ),
        (
            "es-ga-wealth-tax-rebate-official-documents.yaml",
            "es-ga-ley-7-2022-wealth-tax-rebate-2023",
            "5",
            "6",
            "7",
        ),
        (
            "es-md-wealth-tax-rebate-official-documents.yaml",
            "es-md-decreto-legislativo-1-2010-wealth-tax-rebate",
            "19",
            "20",
            "21",
        ),
        (
            "es-wealth-tax-statutes-official-documents.yaml",
            "es-ley-38-2022-itsgf-consolidado",
            "2",
            "3",
            "4",
        ),
    ),
)
def test_scoped_spanish_sources_retain_only_the_cited_article(
    manifest_name: str,
    source_id: str,
    prior: str,
    target: str,
    following: str,
) -> None:
    source = _source(REPO_ROOT / "manifests" / manifest_name, source_id)
    html = f"""
    <main>
      <h3>Artículo {prior}. Prior provision</h3>
      <p>Prior body.</p>
      <h3>Artículo {target}. Target provision</h3>
      <p>Target article body.</p>
      <h3>Artículo {following}. Following provision</h3>
      <p>Following body.</p>
    </main>
    """.encode()

    blocks = _extract_blocks(
        html,
        "html",
        source_url=source.source_url,
        title=source.title,
        extraction=source.extraction,
    )

    assert len(blocks) == 1
    assert blocks[0].metadata["citation_suffix"] == f"articulo-{target}"
    assert blocks[0].body == "Target article body."


def test_rdl_8_2023_extracts_only_retroactive_article_17() -> None:
    source = _source(SPAIN_MANIFEST, "es-rdl-8-2023-itsgf-exemption-amendment")
    html = """
    <main>
      <h3>Artículo 16. Unrelated prior provision</h3>
      <p>Prior body.</p>
      <h3>Artículo 17. Modificación del impuesto</h3>
      <p>Article 17 amendment body.</p>
      <h3>Artículo 18. Unrelated following provision</h3>
      <p>Following body.</p>
    </main>
    """.encode()

    blocks = _extract_blocks(
        html,
        "html",
        source_url=source.source_url,
        title=source.title,
        extraction=source.extraction,
    )

    assert source.expression_date == "2022-12-29"
    assert len(blocks) == 1
    assert blocks[0].metadata["citation_suffix"] == "articulo-17"
    assert blocks[0].body == "Article 17 amendment body."
    assert "Prior" not in blocks[0].body
    assert "Following" not in blocks[0].body


def test_zurich_2022_uses_direct_pdf_and_retains_only_section_47() -> None:
    source = _source(ZURICH_MANIFEST, "ch-zh-stg-2022-section-47-wealth-tax")
    assert source.download_url is not None
    assert "/WebView/" in source.download_url
    assert "/%24File/631.1_8.6.97_115.pdf" in source.download_url

    document = fitz.open()
    for page_number in range(1, 26):
        page = document.new_page()
        if page_number == 24:
            page.insert_text((72, 72), "§ 46. Prior provision")
            page.insert_text((72, 96), "§ 47. Wealth-tax tariff")
            page.insert_text((72, 120), "Tariff body on page 24")
        elif page_number == 25:
            page.insert_text((72, 72), "§ 47 continuation")
            page.insert_text((72, 96), "D. Ausgleich der kalten Progression")
            page.insert_text((72, 120), "§ 48. Following provision")
            page.insert_text((72, 144), "Following body")
    pdf = document.tobytes()
    document.close()

    blocks = _extract_blocks(
        pdf,
        "pdf",
        source_url=source.source_url,
        title=source.title,
        extraction=source.extraction,
    )

    assert len(blocks) == 1
    assert "§ 47. Wealth-tax tariff" in blocks[0].body
    assert "§ 47 continuation" in blocks[0].body
    assert "§ 46" not in blocks[0].body
    assert "D. Ausgleich" not in blocks[0].body
    assert "§ 48" not in blocks[0].body
    assert "Following body" not in blocks[0].body
