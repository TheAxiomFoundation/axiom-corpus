import json
from pathlib import Path

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.cli import main
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.virginia_vac import (
    _section_detail_parts,
    extract_virginia_vac,
)


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _write_vac_sources(source_dir: Path) -> None:
    _write_json(
        source_dir / "virginia-vac-json/titles.json",
        [
            {
                "TitleNumber": "1",
                "TitleName": "Administration",
                "AgencyList": None,
            }
        ],
    )
    _write_json(
        source_dir / "virginia-vac-json/title-1/agencies.json",
        {
            "TitleNumber": "1",
            "TitleName": "Administration",
            "AgencyList": [
                {
                    "AgencyNumber": "7",
                    "AgencyName": "Virginia Code Commission",
                    "ChapterList": None,
                }
            ],
        },
    )
    _write_json(
        source_dir / "virginia-vac-json/title-1/agency-7/preface.json",
        {
            "TitleNumber": "1",
            "TitleName": "Administration",
            "AgencyNumber": "7",
            "AgencyName": "Virginia Code Commission",
            "Preface": "Agency Summary",
            "PrefaceSummary": "<p>The commission publishes the Virginia Administrative Code.</p>",
        },
    )
    _write_json(
        source_dir / "virginia-vac-json/title-1/agency-7/chapters.json",
        {
            "TitleNumber": "1",
            "TitleName": "Administration",
            "AgencyList": [
                {
                    "AgencyNumber": "7",
                    "AgencyName": "Virginia Code Commission",
                    "ChapterList": [
                        {
                            "ChapterNumber": "Preface",
                            "ChapterName": "Agency Summary",
                            "Sections": None,
                        },
                        {
                            "ChapterNumber": "10",
                            "ChapterName": "Regulations for Filing and Publishing Agency Regulations",
                            "Sections": None,
                        },
                    ],
                }
            ],
        },
    )
    sections = [
        {
            "PartNumber": "I",
            "PartName": "General Provisions",
            "ArticleNumber": "",
            "ArticleName": "",
            "SectionNumber": "10",
            "SectionTitle": "Definitions",
            "Body": None,
            "Authority": None,
            "HistoricalNote": None,
        },
        {
            "PartNumber": "I",
            "PartName": "General Provisions",
            "ArticleNumber": "",
            "ArticleName": "",
            "SectionNumber": "20",
            "SectionTitle": "Computation of time",
            "Body": None,
            "Authority": None,
            "HistoricalNote": None,
        },
    ]
    _write_json(
        source_dir / "virginia-vac-json/title-1/agency-7/chapter-10/sections.json",
        {
            "TitleNumber": "1",
            "TitleName": "Administration",
            "AgencyList": [
                {
                    "AgencyNumber": "7",
                    "AgencyName": "Virginia Code Commission",
                    "ChapterList": [
                        {
                            "ChapterNumber": "10",
                            "ChapterName": "Regulations for Filing and Publishing Agency Regulations",
                            "Sections": sections,
                        }
                    ],
                }
            ],
        },
    )
    _write_json(
        source_dir / "virginia-vac-json/title-1/agency-7/chapter-10/section-10.json",
        {
            "TitleNumber": "1",
            "TitleName": "Administration",
            "AgencyList": [
                {
                    "AgencyNumber": "7",
                    "AgencyName": "Virginia Code Commission",
                    "ChapterList": [
                        {
                            "ChapterNumber": "10",
                            "ChapterName": "Regulations for Filing and Publishing Agency Regulations",
                            "Sections": [
                                {
                                    **sections[0],
                                    "Body": (
                                        "<p>The following words and terms apply.</p>"
                                        "<table><tr><th>Term</th><th>Meaning</th></tr>"
                                        "<tr><td>VAC</td><td>Virginia Administrative Code</td></tr></table>"
                                    ),
                                    "Authority": "§ <a href='/vacode/2.2-4104/'>2.2-4104</a> of the Code of Virginia.",
                                    "HistoricalNote": "Derived from Virginia Register Volume 32, Issue 9.",
                                }
                            ],
                        }
                    ],
                }
            ],
        },
    )


def test_extract_virginia_vac_local_sources_writes_records(tmp_path):
    source_dir = tmp_path / "vac-source"
    _write_vac_sources(source_dir)
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_virginia_vac(
        store,
        version="2026-05-18",
        source_dir=source_dir,
        only_title="1",
        only_agency="7",
        only_chapter="10",
        limit=1,
        workers=1,
    )

    assert report.coverage.complete
    assert report.title_count == 1
    assert report.agency_count == 1
    assert report.chapter_count == 1
    assert report.section_count == 1
    assert report.provisions_written == 5

    records = load_provisions(report.provisions_path)
    assert [record.citation_path for record in records] == [
        "us-va/regulation",
        "us-va/regulation/title-1",
        "us-va/regulation/title-1/agency-7",
        "us-va/regulation/title-1/agency-7/chapter-10",
        "us-va/regulation/title-1/agency-7/chapter-10/section-10",
    ]
    assert records[2].body == "The commission publishes the Virginia Administrative Code."
    section = records[-1]
    assert section.heading == "1VAC7-10-10. Definitions"
    assert section.citation_label == "1VAC7-10-10"
    assert section.body is not None
    assert "The following words and terms apply." in section.body
    assert "Term | Meaning" in section.body
    assert section.metadata is not None
    assert section.metadata["authority"] == "§ 2.2-4104 of the Code of Virginia."
    assert section.metadata["historical_note"] == (
        "Derived from Virginia Register Volume 32, Issue 9."
    )

    inventory = load_source_inventory(report.inventory_path)
    assert [item.citation_path for item in inventory] == [
        record.citation_path for record in records
    ]
    assert inventory[-1].source_format == "virginia-vac-json"


def test_extract_virginia_vac_cli_local_sources(tmp_path, capsys):
    source_dir = tmp_path / "vac-source"
    _write_vac_sources(source_dir)
    base = tmp_path / "corpus"

    exit_code = main(
        [
            "extract-virginia-vac",
            "--base",
            str(base),
            "--version",
            "2026-05-18",
            "--source-dir",
            str(source_dir),
            "--only-title",
            "1",
            "--only-agency",
            "7",
            "--only-chapter",
            "10",
            "--limit",
            "1",
            "--workers",
            "1",
        ]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert '"jurisdiction": "us-va"' in output
    assert '"document_class": "regulation"' in output
    assert '"section_count": 1' in output


def test_extract_virginia_vac_preserves_nonnumeric_section_rows(tmp_path):
    source_dir = tmp_path / "vac-source"
    _write_vac_sources(source_dir)
    _write_json(
        source_dir / "virginia-vac-json/title-1/agency-7/chapter-10/sections.json",
        {
            "TitleNumber": "1",
            "TitleName": "Administration",
            "AgencyList": [
                {
                    "AgencyNumber": "7",
                    "AgencyName": "Virginia Code Commission",
                    "ChapterList": [
                        {
                            "ChapterNumber": "10",
                            "ChapterName": "Regulations for Filing and Publishing Agency Regulations",
                            "Sections": [
                                {
                                    "PartNumber": "",
                                    "PartName": "",
                                    "ArticleNumber": "",
                                    "ArticleName": "",
                                    "SectionNumber": "FORMS",
                                    "SectionTitle": "FORMS (1VAC7-10)",
                                    "Body": None,
                                    "Authority": None,
                                    "HistoricalNote": None,
                                },
                                {
                                    "PartNumber": "",
                                    "PartName": "",
                                    "ArticleNumber": "",
                                    "ArticleName": "",
                                    "SectionNumber": "FORMS",
                                    "SectionTitle": "FORMS (1VAC7-10)",
                                    "Body": None,
                                    "Authority": None,
                                    "HistoricalNote": None,
                                }
                            ],
                        }
                    ],
                }
            ],
        },
    )
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_virginia_vac(
        store,
        version="2026-05-18",
        source_dir=source_dir,
        only_title="1",
        only_agency="7",
        only_chapter="10",
        workers=1,
    )

    assert report.coverage.complete
    assert report.section_count == 1
    records = load_provisions(report.provisions_path)
    assert records[-1].citation_path == (
        "us-va/regulation/title-1/agency-7/chapter-10/section-forms"
    )
    assert records[-1].heading == "1VAC7-10-FORMS. FORMS (1VAC7-10)"
    assert records[-1].body is None
    assert records[-1].source_path.endswith("/chapter-10/sections.json")


def test_virginia_section_detail_parts_handles_point_and_colon():
    assert _section_detail_parts("155") == ("155", "0", "0")
    assert _section_detail_parts("155.1") == ("155", "1", "0")
    assert _section_detail_parts("155.1:2") == ("155", "1", "2")
