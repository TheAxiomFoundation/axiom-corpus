"""Tests for the gesetze-im-internet.de (juris XML) converter.

The fixture below is a hand-crafted miniature juris document (not a real law) that
reproduces every structural shape the extractor must handle: the law-level frame
norm, a table-of-contents (``Inhaltsübersicht``) norm, structural division
headings (one pair deliberately sharing a ``gliederungskennzahl`` to exercise
slug disambiguation), ordinary sections with ``<DL>`` enumerations, a lettered
section (``§ 32a``), an ``Anlage`` carrying a CALS table, and a repealed
``(weggefallen)`` range placeholder. Provenance and coverage are asserted against
it end-to-end.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from pathlib import Path

import pytest

import axiom_corpus.corpus.germany_gii as germany_gii
from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.germany_gii import (
    GermanLaw,
    extract_german_gii,
    load_german_gii_laws,
    parse_gii_law,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schema" / "citation-path.v1.json"

# A miniature juris XML document. Root doknr "BJNRTESTG00000000"; each norm has a
# unique doknr tail so collision disambiguation keys off it. Norms 2 and 9 share
# gliederungskennzahl "010" on purpose.
SAMPLE_JURIS_XML = """\
<?xml version="1.0" encoding="UTF-8" ?>
<!DOCTYPE dokumente SYSTEM "http://www.gesetze-im-internet.de/dtd/1.01/gii-norm.dtd">
<dokumente builddate="20260716000000" doknr="BJNRTESTG00000000">
<norm builddate="20260716000000" doknr="BJNRTESTG00000000">
<metadaten>
<jurabk>TestG 2020</jurabk>
<amtabk>TestG</amtabk>
<ausfertigung-datum manuell="ja">2020-01-15</ausfertigung-datum>
<fundstelle typ="amtlich"><periodikum>BGBl I</periodikum><zitstelle>2020, 1</zitstelle></fundstelle>
<langue>Gesetz über die Prüfung der Übermittlung (Testgesetz)</langue>
<standangabe checked="ja"><standtyp>Neuf</standtyp><standkommentar>Neugefasst durch Bek.</standkommentar></standangabe>
<standangabe checked="ja"><standtyp>Stand</standtyp><standkommentar>zuletzt geändert durch Art. 1 G v. 1.6.2026</standkommentar></standangabe>
</metadaten>
<textdaten><fussnoten><Content><P>(+++ Textnachweis ab: 1.1.2020 +++)</P></Content></fussnoten></textdaten>
</norm>
<norm builddate="20260716000000" doknr="BJNRTESTG00000000BJNE000100000">
<metadaten><jurabk>TestG 2020</jurabk><enbez>Inhaltsübersicht</enbez></metadaten>
<textdaten><text format="XML"><TOC><P>I. Allgemeines § 1 Anwendungsbereich</P></TOC></text></textdaten>
</norm>
<norm builddate="20260716000000" doknr="BJNRTESTG00000000BJNG000200000">
<metadaten><jurabk>TestG 2020</jurabk>
<gliederungseinheit><gliederungskennzahl>010</gliederungskennzahl><gliederungsbez>I.</gliederungsbez><gliederungstitel>Allgemeine Vorschriften</gliederungstitel></gliederungseinheit>
</metadaten>
<textdaten><text format="XML"><Content><P/></Content></text></textdaten>
</norm>
<norm builddate="20260716000000" doknr="BJNRTESTG00000000BJNE000300000">
<metadaten><jurabk>TestG 2020</jurabk><enbez>§ 1</enbez><titel format="XML">Anwendungsbereich</titel></metadaten>
<textdaten><text format="XML"><Content>
<P>(1) Dieses Gesetz gilt für<DL Font="normal" Type="arabic"><DT>1.</DT><DD Font="normal"><LA Size="normal">natürliche Personen,</LA></DD><DT>2.</DT><DD Font="normal"><LA Size="normal">juristische Personen.</LA></DD></DL></P>
<P>(2) Ausgenommen sind Körperschaften des öffentlichen Rechts.</P>
</Content></text></textdaten>
</norm>
<norm builddate="20260716000000" doknr="BJNRTESTG00000000BJNE000400000">
<metadaten><jurabk>TestG 2020</jurabk><enbez>§ 32a</enbez><titel format="XML">Einkommensteuertarif</titel></metadaten>
<textdaten><text format="XML"><Content><P>(1) <SUP class="Rec">1</SUP>Die tarifliche Einkommensteuer beträgt bis 12 348 Euro 0 Euro.</P></Content></text></textdaten>
</norm>
<norm builddate="20260716000000" doknr="BJNRTESTG00000000BJNE000500000">
<metadaten><jurabk>TestG 2020</jurabk><enbez>§ 66</enbez><titel format="XML">Höhe des Kindergeldes</titel></metadaten>
<textdaten><text format="XML"><Content><P><!-- Start: interner Umbruch -->Das Kindergeld beträgt <!-- SPLIT UMBAU -->255 Euro monatlich.</P><!-- Ende: interner Umbruch --></Content></text></textdaten>
</norm>
<norm builddate="20260716000000" doknr="BJNRTESTG00000000BJNE000700000">
<metadaten><jurabk>TestG 2020</jurabk><enbez>(XXXX) §§ 7c bis 7d</enbez><titel format="XML">(weggefallen)</titel></metadaten>
<textdaten><text format="XML"><Content><P/></Content></text></textdaten>
</norm>
<norm builddate="20260716000000" doknr="BJNRTESTG00000000BJNE000800000">
<metadaten><jurabk>TestG 2020</jurabk><enbez>Anlage 1</enbez><titel format="XML">(zu § 66)Kindergeldtabelle</titel></metadaten>
<textdaten><text format="XML"><Content><table><Title Align="auto">1. Kindergeldtabelle nach Ordnungsnummern</Title><tgroup cols="2"><tbody>
<row><entry>Kinder</entry><entry>Betrag</entry></row>
<row><entry>1</entry><entry>255 Euro</entry></row>
</tbody></tgroup></table></Content></text></textdaten>
</norm>
<norm builddate="20260716000000" doknr="BJNRTESTG00000000BJNG000900000">
<metadaten><jurabk>TestG 2020</jurabk>
<gliederungseinheit><gliederungskennzahl>010</gliederungskennzahl><gliederungsbez>II.</gliederungsbez><gliederungstitel>Besondere Vorschriften</gliederungstitel></gliederungseinheit>
</metadaten>
<textdaten><text format="XML"><Content><P/></Content></text></textdaten>
</norm>
</dokumente>
"""

SAMPLE_LAW = GermanLaw(
    slug="testg_2020",
    title="Testgesetz",
    source_as_of="2026-07-16",
    expression_date="2026-07-16",
)


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def _citation_pattern() -> re.Pattern[str]:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return re.compile(schema["$defs"]["citation_path"]["pattern"])


def _write_source(tmp_path: Path, name: str = "testg_2020.xml") -> Path:
    source = tmp_path / name
    source.write_text(SAMPLE_JURIS_XML, encoding="utf-8")
    return source


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------
def test_parse_gii_law_maps_every_norm_to_one_provision():
    norms = parse_gii_law(SAMPLE_JURIS_XML.encode("utf-8"), law=SAMPLE_LAW)
    # 9 <norm> elements in the fixture -> 9 parsed norms.
    assert len(norms) == 9
    kinds = [norm.kind for norm in norms]
    assert kinds[0] == "document"
    assert kinds.count("division") == 2
    assert kinds.count("anlage") == 1
    assert kinds.count("overview") == 1
    assert kinds.count("section") == 4  # § 1, § 32a, § 66, and the (weggefallen) range


def test_enbez_slugging_covers_sections_anlagen_overview_and_ranges():
    norms = parse_gii_law(SAMPLE_JURIS_XML.encode("utf-8"), law=SAMPLE_LAW)
    slugs = {norm.enbez: norm.norm_slug for norm in norms if norm.enbez}
    assert slugs["§ 1"] == "1"
    assert slugs["§ 32a"] == "32a"
    assert slugs["§ 66"] == "66"
    assert slugs["Anlage 1"] == "anlage-1"
    assert slugs["Inhaltsübersicht"] == "inhaltsuebersicht"
    assert slugs["(XXXX) §§ 7c bis 7d"] == "xxxx-7c-bis-7d"


def test_division_slugs_disambiguate_on_shared_gliederungskennzahl():
    norms = parse_gii_law(SAMPLE_JURIS_XML.encode("utf-8"), law=SAMPLE_LAW)
    division_slugs = sorted(n.norm_slug for n in norms if n.kind == "division")
    # Both divisions carry gliederungskennzahl "010"; the doknr tail disambiguates.
    assert division_slugs == [
        "gl-010-bjng000200000",
        "gl-010-bjng000900000",
    ]
    assert len(set(division_slugs)) == 2


def test_weggefallen_norm_is_flagged_and_keeps_placeholder_body():
    norms = parse_gii_law(SAMPLE_JURIS_XML.encode("utf-8"), law=SAMPLE_LAW)
    repealed = next(n for n in norms if n.enbez == "(XXXX) §§ 7c bis 7d")
    assert repealed.repealed is True
    assert repealed.body == "(weggefallen)"
    assert repealed.heading == "(weggefallen)"


def test_body_rendering_preserves_enumeration_markers_and_tables():
    norms = parse_gii_law(SAMPLE_JURIS_XML.encode("utf-8"), law=SAMPLE_LAW)
    by_enbez = {n.enbez: n for n in norms if n.enbez}
    section_1 = by_enbez["§ 1"]
    assert "1. natürliche Personen," in section_1.body
    assert "2. juristische Personen." in section_1.body
    assert "(2) Ausgenommen" in section_1.body
    # The Anlage table renders as pipe-delimited rows.
    assert "Kinder | Betrag" in by_enbez["Anlage 1"].body
    assert "1 | 255 Euro" in by_enbez["Anlage 1"].body
    # The Inhaltsübersicht body comes from <text><TOC>, not <Content>.
    assert "Allgemeines" in by_enbez["Inhaltsübersicht"].body


def test_law_frame_carries_act_metadata():
    norms = parse_gii_law(SAMPLE_JURIS_XML.encode("utf-8"), law=SAMPLE_LAW)
    frame = norms[0]
    assert frame.kind == "document"
    assert frame.norm_slug is None
    assert frame.law_metadata["ausfertigung_datum"] == "2020-01-15"
    assert frame.law_metadata["fundstelle"] == "BGBl I 2020, 1"
    assert "zuletzt geändert" in frame.law_metadata["stand"]
    # Umlauts survive verbatim in the rendered title body.
    assert "Übermittlung" in frame.body


# ---------------------------------------------------------------------------
# Extraction, provenance, coverage
# ---------------------------------------------------------------------------
def test_extract_requires_a_law_or_manifest(tmp_path):
    with pytest.raises(ValueError, match="at least one law or a manifest"):
        extract_german_gii(
            CorpusArtifactStore(tmp_path / "data" / "corpus"),
            version="2026-07-16-de",
        )


def test_extract_writes_inventory_provisions_and_complete_coverage(tmp_path):
    base = tmp_path / "data" / "corpus"
    source = _write_source(tmp_path)
    law = GermanLaw(slug="testg_2020", title="Testgesetz", local_source=source)

    report = extract_german_gii(
        CorpusArtifactStore(base),
        version="2026-07-16-de",
        laws=(law,),
        source_as_of="2026-07-16",
        expression_date="2026-07-16",
    )

    assert report.provisions_written == 9
    assert report.source_count == 9
    [scope] = report.scope_reports
    assert scope.jurisdiction == "de"
    assert scope.document_class == "statute"
    assert scope.law_count == 1
    assert scope.coverage.complete

    provisions = _read_jsonl(base / "provisions/de/statute/2026-07-16-de.jsonl")
    paths = {record["citation_path"] for record in provisions}
    assert "de/statute/testg-2020" in paths
    assert "de/statute/testg-2020/32a" in paths
    assert "de/statute/testg-2020/anlage-1" in paths
    assert "de/statute/testg-2020/inhaltsuebersicht" in paths
    assert "de/statute/testg-2020/xxxx-7c-bis-7d" in paths

    # Coverage file: source citation set == provision citation set.
    coverage = json.loads((base / "coverage/de/statute/2026-07-16-de.json").read_text())
    assert coverage["complete"] is True
    assert coverage["missing_from_provisions"] == []
    assert coverage["extra_provisions"] == []
    assert coverage["source_count"] == coverage["provision_count"] == 9


def test_extract_retains_source_bytes_with_matching_sha256(tmp_path):
    base = tmp_path / "data" / "corpus"
    source = _write_source(tmp_path)
    law = GermanLaw(slug="testg_2020", local_source=source)

    extract_german_gii(
        CorpusArtifactStore(base),
        version="2026-07-16-de",
        laws=(law,),
        source_as_of="2026-07-16",
    )

    retained = base / "sources/de/statute/2026-07-16-de/testg_2020/testg_2020.xml"
    assert retained.exists()
    expected_sha = hashlib.sha256(SAMPLE_JURIS_XML.encode("utf-8")).hexdigest()
    assert hashlib.sha256(retained.read_bytes()).hexdigest() == expected_sha

    inventory = json.loads((base / "inventory/de/statute/2026-07-16-de.json").read_text())
    for item in inventory["items"]:
        assert item["source_format"] == "gesetze-im-internet.de-juris-xml"
        assert item["sha256"] == expected_sha
        assert item["source_path"] == ("sources/de/statute/2026-07-16-de/testg_2020/testg_2020.xml")


def test_provision_records_carry_provenance_and_identity_fields(tmp_path):
    base = tmp_path / "data" / "corpus"
    source = _write_source(tmp_path)
    extract_german_gii(
        CorpusArtifactStore(base),
        version="2026-07-16-de",
        laws=(GermanLaw(slug="testg_2020", title="Testgesetz", local_source=source),),
        source_as_of="2026-07-16",
    )
    records = {
        r["citation_path"]: r
        for r in _read_jsonl(base / "provisions/de/statute/2026-07-16-de.jsonl")
    }

    section = records["de/statute/testg-2020/32a"]
    assert section["jurisdiction"] == "de"
    assert section["document_class"] == "statute"
    assert section["kind"] == "section"
    assert section["level"] == 1
    assert section["language"] == "de"
    assert section["parent_citation_path"] == "de/statute/testg-2020"
    assert section["citation_label"] == "TestG 2020 § 32a"
    assert section["source_url"].endswith("/testg_2020/xml.zip")
    assert section["identifiers"]["gesetze-im-internet.de:slug"] == "testg_2020"
    assert section["identifiers"]["gesetze-im-internet.de:enbez"] == "§ 32a"
    assert section["identifiers"]["gesetze-im-internet.de:doknr"].startswith("BJNRTESTG")

    parent = records["de/statute/testg-2020"]
    assert parent["kind"] == "document"
    assert parent["level"] == 0
    assert "parent_citation_path" not in parent  # top of the document tree


def test_extract_groups_statute_and_regulation_into_separate_scopes(tmp_path):
    base = tmp_path / "data" / "corpus"
    source = _write_source(tmp_path)
    laws = (
        GermanLaw(slug="testg_2020", local_source=source),
        GermanLaw(slug="testv_2020", document_class="regulation", local_source=source),
    )
    report = extract_german_gii(
        CorpusArtifactStore(base),
        version="2026-07-16-de",
        laws=laws,
        source_as_of="2026-07-16",
    )

    scopes = {(s.jurisdiction, s.document_class) for s in report.scope_reports}
    assert scopes == {("de", "statute"), ("de", "regulation")}
    assert (base / "provisions/de/statute/2026-07-16-de.jsonl").exists()
    assert (base / "provisions/de/regulation/2026-07-16-de.jsonl").exists()


def test_zip_source_is_unpacked(tmp_path):
    base = tmp_path / "data" / "corpus"
    zip_path = tmp_path / "testg_2020.zip"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("BJNRTESTG00000000.xml", SAMPLE_JURIS_XML)
    zip_path.write_bytes(buffer.getvalue())

    report = extract_german_gii(
        CorpusArtifactStore(base),
        version="2026-07-16-de",
        laws=(GermanLaw(slug="testg_2020", local_source=zip_path),),
        source_as_of="2026-07-16",
    )
    assert report.provisions_written == 9
    retained = base / "sources/de/statute/2026-07-16-de/testg_2020/BJNRTESTG00000000.xml"
    assert retained.exists()


def test_extract_rejects_two_slugs_that_map_to_the_same_citation_path(tmp_path):
    base = tmp_path / "data" / "corpus"
    source = _write_source(tmp_path)
    # "sgb_2" and "sgb-2" both slugify to de/statute/sgb-2 -> loud failure.
    laws = (
        GermanLaw(slug="sgb_2", local_source=source),
        GermanLaw(slug="sgb-2", local_source=source),
    )
    with pytest.raises(ValueError, match="map to the same citation path"):
        extract_german_gii(
            CorpusArtifactStore(base),
            version="2026-07-16-de",
            laws=laws,
            source_as_of="2026-07-16",
        )


# ---------------------------------------------------------------------------
# Citation-path grammar conformance
# ---------------------------------------------------------------------------
def test_every_citation_path_matches_the_grammar_and_avoids_irregular_families(tmp_path):
    base = tmp_path / "data" / "corpus"
    source = _write_source(tmp_path)
    # A law slug with an underscore must slugify to a hyphen (grammar excludes "_").
    extract_german_gii(
        CorpusArtifactStore(base),
        version="2026-07-16-de",
        laws=(GermanLaw(slug="testg_2020", local_source=source),),
        source_as_of="2026-07-16",
    )
    records = _read_jsonl(base / "provisions/de/statute/2026-07-16-de.jsonl")
    pattern = _citation_pattern()
    for record in records:
        path = record["citation_path"]
        assert pattern.match(path), f"grammar violation: {path}"
        # Segment 0/1 must equal the jurisdiction/document_class fields.
        segments = path.split("/")
        assert segments[0] == record["jurisdiction"]
        assert segments[1] == record["document_class"]
        # Irregular-family ratchets must not be bumped.
        assert not any(c.isupper() for c in path), path
        assert " " not in path
        assert "_" not in path
        assert "–" not in path  # en-dash
        assert not any(seg.endswith(("-", " ")) for seg in segments)
        assert not re.search(r"/(?:block|page)-\d+", path)
        assert len(segments) >= 3  # never a two-segment collection root


# ---------------------------------------------------------------------------
# Manifest loading
# ---------------------------------------------------------------------------
def test_load_german_gii_laws_reads_documents_and_cross_checks_citation_path(tmp_path):
    manifest = tmp_path / "de-test.yaml"
    manifest.write_text(
        """
version: 2026-07-16-de
documents:
  - source_id: de-estg
    jurisdiction: de
    document_class: statute
    slug: estg
    citation_path: de/statute/estg
    title: Einkommensteuergesetz
    source_url: https://www.gesetze-im-internet.de/estg/xml.zip
  - source_id: de-solzg
    jurisdiction: de
    document_class: statute
    slug: solzg_1995
    citation_path: de/statute/solzg-1995
    title: Solidaritätszuschlaggesetz 1995
""".lstrip()
    )
    laws = load_german_gii_laws(manifest)
    assert [law.slug for law in laws] == ["estg", "solzg_1995"]
    assert laws[0].parent_citation_path == "de/statute/estg"
    assert laws[1].parent_citation_path == "de/statute/solzg-1995"


def test_manifest_citation_path_mismatch_raises(tmp_path):
    manifest = tmp_path / "de-bad.yaml"
    manifest.write_text(
        """
documents:
  - slug: estg
    citation_path: de/statute/wrong-slug
""".lstrip()
    )
    with pytest.raises(ValueError, match="does not match the derived parent path"):
        load_german_gii_laws(manifest)


def test_manifest_duplicate_slug_raises(tmp_path):
    manifest = tmp_path / "de-dup.yaml"
    manifest.write_text(
        """
documents:
  - slug: estg
  - slug: estg
""".lstrip()
    )
    with pytest.raises(ValueError, match="duplicate law slug"):
        load_german_gii_laws(manifest)


# ---------------------------------------------------------------------------
# CLI wiring
# ---------------------------------------------------------------------------
def test_cli_extract_de_gii_writes_artifacts_and_returns_zero(tmp_path, capsys):
    from axiom_corpus.corpus.cli import main

    base = tmp_path / "data" / "corpus"
    source = _write_source(tmp_path)

    exit_code = main(
        [
            "extract-de-gii",
            "--base",
            str(base),
            "--version",
            "2026-07-16-de",
            "--source-xml",
            str(source),
            "--as-of",
            "2026-07-16",
        ]
    )

    assert exit_code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["provisions_written"] == 9
    assert report["scopes"][0]["complete"] is True
    assert (base / "provisions/de/statute/2026-07-16-de.jsonl").exists()


def test_cli_extract_de_gii_reads_a_source_directory(tmp_path, capsys):
    from axiom_corpus.corpus.cli import main

    base = tmp_path / "data" / "corpus"
    source_dir = tmp_path / "de-sources"
    source_dir.mkdir()
    (source_dir / "testg_2020.xml").write_text(SAMPLE_JURIS_XML, encoding="utf-8")
    (source_dir / "ignore.txt").write_text("not a law", encoding="utf-8")

    exit_code = main(
        [
            "extract-de-gii",
            "--base",
            str(base),
            "--version",
            "2026-07-16-de",
            "--source-dir",
            str(source_dir),
            "--source-as-of",
            "2026-07-16",
        ]
    )

    assert exit_code == 0
    report = json.loads(capsys.readouterr().out)
    # Only the .xml file is treated as a law; the .txt is ignored.
    assert report["scopes"][0]["law_count"] == 1
    assert report["provisions_written"] == 9


# ---------------------------------------------------------------------------
# Network fetch, manifest-driven extraction, and edge branches
# ---------------------------------------------------------------------------
def _zip_bytes(inner_name: str = "BJNRTESTG00000000.xml", xml: str = SAMPLE_JURIS_XML) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(inner_name, xml)
    return buffer.getvalue()


class _FakeResponse:
    def __init__(self, content: bytes):
        self.content = content

    def raise_for_status(self) -> None:
        return None


class _FakeSession:
    """Stand-in for requests.Session that returns a fixture zip for any URL."""

    def __init__(self, content: bytes):
        self._content = content
        self.headers: dict[str, str] = {}
        self.requested: list[str] = []

    def get(self, url: str, timeout: float) -> _FakeResponse:
        self.requested.append(url)
        return _FakeResponse(self._content)


def test_extract_fetches_via_requests_when_no_local_source(tmp_path, monkeypatch):
    import axiom_corpus.corpus.germany_gii as gii

    session = _FakeSession(_zip_bytes())
    monkeypatch.setattr(gii.requests, "Session", lambda: session)

    report = extract_german_gii(
        CorpusArtifactStore(tmp_path / "data" / "corpus"),
        version="2026-07-16-de",
        laws=(GermanLaw(slug="testg_2020"),),
        source_as_of="2026-07-16",
    )

    assert report.provisions_written == 9
    assert session.requested == ["https://www.gesetze-im-internet.de/testg_2020/xml.zip"]


def test_extract_from_manifest_applies_limit(tmp_path, monkeypatch):
    import axiom_corpus.corpus.germany_gii as gii

    monkeypatch.setattr(gii.requests, "Session", lambda: _FakeSession(_zip_bytes()))
    manifest = tmp_path / "de.yaml"
    manifest.write_text(
        """
documents:
  - slug: testg_2020
    citation_path: de/statute/testg-2020
  - slug: second_law
    citation_path: de/statute/second-law
""".lstrip()
    )

    report = extract_german_gii(
        CorpusArtifactStore(tmp_path / "data" / "corpus"),
        version="2026-07-16-de",
        manifest=manifest,
        limit=1,
        source_as_of="2026-07-16",
    )

    # limit=1 keeps only the first manifest law.
    assert report.provisions_written == 9
    assert report.scope_reports[0].law_count == 1


def test_extract_accepts_a_date_object_for_expression_date(tmp_path):
    from datetime import date

    base = tmp_path / "data" / "corpus"
    source = _write_source(tmp_path)
    extract_german_gii(
        CorpusArtifactStore(base),
        version="2026-07-16-de",
        laws=(GermanLaw(slug="testg_2020", local_source=source),),
        expression_date=date(2026, 7, 16),
        source_as_of="2026-07-16",
    )
    records = _read_jsonl(base / "provisions/de/statute/2026-07-16-de.jsonl")
    assert records[0]["expression_date"] == "2026-07-16"


def test_law_metadata_is_merged_and_primary_source_flag_is_honoured(tmp_path):
    base = tmp_path / "data" / "corpus"
    source = _write_source(tmp_path)
    law = GermanLaw(
        slug="testg_2020",
        local_source=source,
        metadata={"primary_source": False, "source_family": "test/family"},
    )
    extract_german_gii(
        CorpusArtifactStore(base),
        version="2026-07-16-de",
        laws=(law,),
        source_as_of="2026-07-16",
    )

    records = {
        r["citation_path"]: r
        for r in _read_jsonl(base / "provisions/de/statute/2026-07-16-de.jsonl")
    }
    section = records["de/statute/testg-2020/1"]
    assert section["metadata"]["primary_source"] is False
    assert section["metadata"]["source_family"] == "test/family"

    inventory = json.loads((base / "inventory/de/statute/2026-07-16-de.json").read_text())
    assert all(item["metadata"]["primary_source"] is False for item in inventory["items"])


# ---------------------------------------------------------------------------
# Structural edge cases and malformed input
# ---------------------------------------------------------------------------
FRAME_ONLY = (
    '<norm doknr="BJNRX00000000">'
    "<metadaten><jurabk>L</jurabk><langue>Beispielgesetz</langue></metadaten>"
    "</norm>"
)


def _doc(*norms: str, doknr: str = "BJNRX00000000") -> bytes:
    body = "".join(norms)
    return f'<dokumente doknr="{doknr}">{body}</dokumente>'.encode()


def test_parse_rejects_non_dokumente_root():
    with pytest.raises(ValueError, match="unexpected juris XML root"):
        parse_gii_law(b"<other><norm/></other>", law=SAMPLE_LAW)


def test_parse_rejects_norm_without_metadaten():
    xml = _doc(FRAME_ONLY, '<norm doknr="BJNRX00000000BJNE1"></norm>')
    with pytest.raises(ValueError, match="missing <metadaten>"):
        parse_gii_law(xml, law=SAMPLE_LAW)


def test_extract_errors_when_document_has_no_norms(tmp_path):
    law = GermanLaw(slug="empty", local_source=_write_empty_doc(tmp_path))
    with pytest.raises(ValueError, match="no <norm> elements parsed"):
        extract_german_gii(
            CorpusArtifactStore(tmp_path / "data" / "corpus"),
            version="2026-07-16-de",
            laws=(law,),
        )


def _write_empty_doc(tmp_path: Path) -> Path:
    path = tmp_path / "empty.xml"
    path.write_bytes(_doc())
    return path


def test_norm_without_enbez_or_division_falls_back_to_doknr_slug():
    section = (
        '<norm doknr="BJNRX00000000BJNE9">'
        "<metadaten><jurabk>L</jurabk></metadaten>"
        "<textdaten><text><Content><P>Freitext ohne Einzelnorm.</P></Content></text></textdaten>"
        "</norm>"
    )
    norms = parse_gii_law(_doc(FRAME_ONLY, section), law=SAMPLE_LAW)
    # Two norms, no slug collision -> the disambiguation early-returns unchanged.
    fallback = norms[1]
    assert fallback.kind == "norm"
    assert fallback.norm_slug == "n-bjne9"
    assert fallback.body == "Freitext ohne Einzelnorm."


def test_frame_without_footnotes_yields_metadata_only_body():
    norms = parse_gii_law(_doc(FRAME_ONLY), law=SAMPLE_LAW)
    frame = norms[0]
    assert frame.kind == "document"
    assert frame.body == "Beispielgesetz"


def test_content_rendering_handles_direct_br_dl_and_nested_tables():
    section = (
        '<norm doknr="BJNRX00000000BJNE5">'
        "<metadaten><jurabk>L</jurabk><enbez>§ 5</enbez><titel>Aufbau</titel></metadaten>"
        "<textdaten><text><Content>"
        "<BR/>"
        '<DL Type="arabic"><DT>1.</DT><DD><LA>erster Punkt</LA></DD></DL>'
        "<P>Einleitung<BR/>Fortsetzung"
        "<table><tgroup><tbody><row><entry>Zelle</entry></row></tbody></tgroup></table>"
        "</P>"
        "</Content></text></textdaten>"
        "</norm>"
    )
    norms = parse_gii_law(_doc(FRAME_ONLY, section), law=SAMPLE_LAW)
    body = norms[1].body
    assert "1. erster Punkt" in body
    assert "Einleitung\nFortsetzung" in body
    assert "Zelle" in body


@pytest.mark.parametrize(
    ("yaml_text", "match"),
    [
        ("- not-a-mapping\n", "must be a YAML mapping"),
        ("version: x\n", "must list at least one document"),
        ("documents:\n  - just-a-string\n", "each manifest document must be a mapping"),
        ("documents:\n  - slug: '  '\n", "slug must be non-empty"),
    ],
)
def test_manifest_structural_errors(tmp_path, yaml_text, match):
    manifest = tmp_path / "bad.yaml"
    manifest.write_text(yaml_text)
    with pytest.raises(ValueError, match=match):
        load_german_gii_laws(manifest)


def test_local_zip_without_xml_member_raises(tmp_path):
    zip_path = tmp_path / "testg_2020.zip"
    zip_path.write_bytes(_zip_bytes(inner_name="readme.txt", xml="not xml"))
    with pytest.raises(ValueError, match="contains no .xml document"):
        extract_german_gii(
            CorpusArtifactStore(tmp_path / "data" / "corpus"),
            version="2026-07-16-de",
            laws=(GermanLaw(slug="testg_2020", local_source=zip_path),),
        )


def test_enbez_without_section_marker_is_kind_norm():
    # "Eingangsformel" (enacting formula) is a real juris enbez with no § marker.
    section = (
        '<norm doknr="BJNRX00000000BJNE2">'
        "<metadaten><jurabk>L</jurabk><enbez>Eingangsformel</enbez></metadaten>"
        "<textdaten><text><Content><P>Der Bundestag hat das folgende Gesetz beschlossen:</P>"
        "</Content></text></textdaten></norm>"
    )
    norms = parse_gii_law(_doc(FRAME_ONLY, section), law=SAMPLE_LAW)
    formula = norms[1]
    assert formula.kind == "norm"
    assert formula.norm_slug == "eingangsformel"


def test_rendering_tolerates_comments_untitled_divisions_and_malformed_lists():
    # A stray XML comment (non-str tag), a division with only a kennzahl (no
    # heading), a body-only "(weggefallen)" marker, and a DL that opens on a
    # non-DT node with a trailing DT that has no DD -- all must render safely.
    division = (
        '<norm doknr="BJNRX00000000BJNG3">'
        "<metadaten><jurabk>L</jurabk>"
        "<gliederungseinheit><gliederungskennzahl>020</gliederungskennzahl></gliederungseinheit>"
        "</metadaten><textdaten><text><Content><P/></Content></text></textdaten></norm>"
    )
    repealed = (
        '<norm doknr="BJNRX00000000BJNE4">'
        "<metadaten><jurabk>L</jurabk><enbez>§ 4</enbez></metadaten>"
        "<textdaten><text><Content><P>(weggefallen)</P></Content></text></textdaten></norm>"
    )
    quirky = (
        '<norm doknr="BJNRX00000000BJNE6">'
        "<metadaten><jurabk>L</jurabk><enbez>§ 6</enbez></metadaten>"
        "<textdaten><text><Content><!-- editorial note -->"
        "<DL><LA>lose Angabe</LA><DT>1.</DT></DL>"
        "</Content></text></textdaten></norm>"
    )
    norms = parse_gii_law(_doc(FRAME_ONLY, division, repealed, quirky), law=SAMPLE_LAW)
    by_slug = {n.norm_slug: n for n in norms}

    assert by_slug["gl-020"].heading is None
    assert by_slug["4"].repealed is True
    assert by_slug["4"].body == "(weggefallen)"
    assert "lose Angabe" in by_slug["6"].body
    assert "1." in by_slug["6"].body


# ---------------------------------------------------------------------------
# Date-field integrity (the 2026-07-16 org-wide contamination class)
# ---------------------------------------------------------------------------
def test_live_fetch_stamps_actual_fetch_date(tmp_path, monkeypatch):
    monkeypatch.setattr(
        germany_gii,
        "_fetch_zip",
        lambda url, timeout: SAMPLE_JURIS_XML.encode("utf-8"),
    )
    base = tmp_path / "data" / "corpus"
    law = GermanLaw(slug="testg_2020", title="Testgesetz")

    extract_german_gii(
        CorpusArtifactStore(base),
        version="2026-07-16-de",
        laws=(law,),
        fetch_date="2026-07-16",
    )

    records = _read_jsonl(base / "provisions" / "de" / "statute" / "2026-07-16-de.jsonl")
    assert records
    assert {r["source_as_of"] for r in records} == {"2026-07-16"}


def test_live_fetch_rejects_conflicting_manifest_source_as_of(tmp_path, monkeypatch):
    monkeypatch.setattr(
        germany_gii,
        "_fetch_zip",
        lambda url, timeout: SAMPLE_JURIS_XML.encode("utf-8"),
    )
    law = GermanLaw(slug="testg_2020", title="Testgesetz", source_as_of="2026-01-01")

    with pytest.raises(ValueError, match="conflicts with the live fetch date"):
        extract_german_gii(
            CorpusArtifactStore(tmp_path / "data" / "corpus"),
            version="2026-07-16-de",
            laws=(law,),
            fetch_date="2026-07-16",
        )


def test_offline_source_requires_explicit_source_as_of(tmp_path):
    source = _write_source(tmp_path)
    law = GermanLaw(slug="testg_2020", title="Testgesetz", local_source=source)

    with pytest.raises(ValueError, match="offline sources require source_as_of"):
        extract_german_gii(
            CorpusArtifactStore(tmp_path / "data" / "corpus"),
            version="2026-07-16-de",
            laws=(law,),
        )


def test_version_slug_never_reaches_date_fields(tmp_path):
    source = _write_source(tmp_path)
    base = tmp_path / "data" / "corpus"
    law = GermanLaw(slug="testg_2020", title="Testgesetz", local_source=source)

    extract_german_gii(
        CorpusArtifactStore(base),
        version="2026-07-16-de",
        laws=(law,),
        source_as_of="2026-07-09",
    )

    iso = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    records = _read_jsonl(base / "provisions" / "de" / "statute" / "2026-07-16-de.jsonl")
    assert records
    for record in records:
        assert iso.match(record["source_as_of"]), record["source_as_of"]
        assert iso.match(record["expression_date"]), record["expression_date"]
        assert record["source_as_of"] != "2026-07-16-de"
        assert record["expression_date"] != "2026-07-16-de"


# ---------------------------------------------------------------------------
# Rendering fidelity regressions (gate findings on the first live ingest)
# ---------------------------------------------------------------------------
def test_table_titles_are_statutory_content():
    norms = parse_gii_law(SAMPLE_JURIS_XML.encode("utf-8"), law=SAMPLE_LAW)
    anlage = next(n for n in norms if n.norm_slug == "anlage-1")
    assert "1. Kindergeldtabelle nach Ordnungsnummern" in anlage.body


def test_internal_xml_comments_never_reach_bodies_but_their_tails_do():
    norms = parse_gii_law(SAMPLE_JURIS_XML.encode("utf-8"), law=SAMPLE_LAW)
    p66 = next(n for n in norms if n.norm_slug == "66")
    assert "Start:" not in p66.body
    assert "SPLIT UMBAU" not in p66.body
    assert "Ende:" not in p66.body
    # The text split across the comment must survive intact.
    assert "Das Kindergeld beträgt 255 Euro monatlich." in p66.body
