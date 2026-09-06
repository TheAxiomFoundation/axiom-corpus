import hashlib
import json
from pathlib import Path

import pytest

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.israel_openlaw import (
    ISRAEL_OPENLAW_SOURCE_FORMAT,
    IsraelOpenLawManifest,
    IsraelOpenLawSource,
    extract_israel_openlaw,
    hebrew_suffix_slug,
    israeli_ident_slug,
    latin_ordinal_slug,
    parse_israel_openlaw_document,
    parse_israel_openlaw_html,
    schedule_heading_ident,
)
from axiom_corpus.corpus.supabase import deterministic_provision_id

REPO_ROOT = Path(__file__).resolve().parents[1]
IL_PILOT_VERSION = "2026-09-06-il-taxben-pilot"
IL_PILOT_MANIFEST = REPO_ROOT / "manifests" / "il-taxben-pilot-openlaw.yaml"
IL_PILOT_SOURCE_DIR = (
    REPO_ROOT / "data" / "corpus" / "sources" / "il" / "statute" / IL_PILOT_VERSION / "openlaw"
)
ITO = "il/statute/income-tax-ordinance"
NII = "il/statute/national-insurance-law-1995"

SAMPLE_TITLE = "פקודת דוגמה [נוסח חדש]"
SAMPLE_URL = "https://he.wikisource.org/wiki/%D7%A4%D7%A7%D7%95%D7%93%D7%AA_%D7%93%D7%95%D7%92%D7%9E%D7%94"

# A miniature OpenLaw page exercising every structural hazard the real snapshots
# contain: nested navigation, a suffixed section, a two-letter suffix whose
# gematria value differs from its letter position, a letter+digit tail, folded
# sub-item anchors, an editorial note, a note-introduced historical table, a
# repeal status line, and an in-text cross-reference that must not split.
SAMPLE_HTML = """\
<!doctype html>
<html lang="he" dir="rtl">
  <body>
    <div class="mw-parser-output">
      <div class="law" id="law-content">
        <h1 class="law-title mw-html-heading">פקודת דוגמה [נוסח חדש]</h1>
        <hr class="law-separator"/>
        <div>2000944 ס״ח תשכ״א, 47</div>
        <h2 class="law-section mw-html-heading">תוכן עניינים</h2>
        <div><div class="law-toc-2">חלק א׳</div></div>
        <h1 class="law-part mw-html-heading">חלק א׳: פרשנות</h1>
        <h2 class="law-section mw-html-heading">פרק ראשון: המקור</h2>
        <h3 class="law-subsection mw-html-heading">סימן א׳: פטור</h3>
        <div class="law-number tc_ selflink" id="סעיף_2"><a href="#סעיף_2">2.</a> </div>
        <div class="law-desc"><span class="law-float"></span>מקורות הכנסה <span
          class="law-note">[תיקון: תשס״ב־9]</span></div>
        <div class="law-main"><div>
        </div>
        <div class="law-content1"> מס הכנסה יהא משתלם לפי סעיף 121ב לפקודה.
        </div></div>
        <div class="law-cleaner"></div>
        <div class="law-number tc_ selflink" id="סעיף_2.1"><a href="#סעיף_2.1"></a> </div>
        <div class="law-desc"><span class="law-float"></span>עסק ומשלח־יד</div>
        <div class="law-main"><div>
        </div>
        <div class="law-number2 tc_">(1) </div><div class="law-content2"> השתכרות מכל עסק.
        </div></div>
        <div class="law-cleaner"></div>
        <div class="law-number tc_ selflink" id="סעיף_103כ"><a href="#סעיף_103כ">103כ.</a> </div>
        <div class="law-desc"><span class="law-float"></span>הוראות מעבר</div>
        <div class="law-main"><div>
        </div>
        <div class="law-number2 tc_">(א) </div><div class="law-content2"> הוראה ראשונה.
        </div>
        <div class="law-number2 tc_">(ב) </div><div class="law-content2"> הוראה שנייה <span
          class="law-note">(הערת עורך)</span>.
        </div></div>
        <div class="law-cleaner"></div>
        <div class="law-main"><div>
        </div>
        <div class="law-content1"> <span class="law-note">להלן מדרגות המס:</span>
        <div style="text-align: right;">
        <table><tbody><tr><td>2019</td><td>10%</td></tr></tbody></table>
        </div>
        </div></div>
        <div class="law-cleaner"></div>
        <div class="law-number tc_ selflink" id="סעיף_64א7ב"><a href="#סעיף_64א7ב">64א7ב.</a> </div>
        <div class="law-desc"><span class="law-float"></span> <span
          class="law-note">[תיקון: תשפ״ה־2]</span></div>
        <div class="law-main"><div>
        </div>
        <div class="law-content1"> <span class="law-note">(בוטל).</span>
        </div></div>
        <div class="law-cleaner"></div>
        <h2 class="law-section mw-html-heading">לוח ט״ז1</h2>
        <div class="law-number tc_ selflink" id="לוח_טז1_פרט_א"><a href="#לוח_טז1_פרט_א">(א)</a> </div>
        <div class="law-desc"><span class="law-float"></span>פרט ראשון</div>
        <div class="law-main"><div>
        </div>
        <div class="law-content1"> סכום הפרט.
        </div></div>
      </div>
    </div>
  </body>
</html>
"""


def _sample_mapping(**overrides: object) -> dict[str, object]:
    mapping: dict[str, object] = {
        "source_id": "sample-ordinance",
        "jurisdiction": "il",
        "document_class": "statute",
        "instrument_slug": "sample-ordinance",
        "israel_law_id": "2000944",
        "title": SAMPLE_TITLE,
        "title_en": "Sample Ordinance [New Version]",
        "source_url": SAMPLE_URL,
        "source_file": "sample.html",
        "sha256": "0" * 64,
        "source_as_of": "2026-09-06",
        "expression_date": "2026-06-08",
        "expression_date_basis": "Knesset OData KNS_IsraelLaw.LatestPublicationDate",
        "source_tier": "consolidation-knesset-linked",
        "language": "he",
        "expected_section_count": 3,
        "expected_schedule_item_count": 1,
        "expected_schedule_count": 1,
        "expected_part_count": 1,
        "expected_chapter_count": 1,
        "expected_sign_count": 1,
    }
    mapping.update(overrides)
    return mapping


def _sample_source(**overrides: object) -> IsraelOpenLawSource:
    return IsraelOpenLawSource.from_mapping(_sample_mapping(**overrides))


def _write_manifest(path: Path, source: dict[str, object]) -> None:
    path.write_text(json.dumps({"documents": [source]}, ensure_ascii=False), encoding="utf-8")


# --- transliteration -------------------------------------------------------


@pytest.mark.parametrize(
    ("suffix", "expected"),
    [
        ("א", "a"),
        ("ב", "b"),
        ("ט", "i"),
        ("י", "j"),
        ("יא", "k"),
        ("יב", "l"),
        ("טו", "o"),
        ("טז", "p"),
        ("יט", "s"),
        # כ is the 11th Hebrew letter but the 20th enumeration position; a
        # letter-position mapping would collide it with יא -> k.
        ("כ", "t"),
        ("כו", "z"),
        ("כז", "aa"),
        ("ל", "ad"),
        ("לד", "ah"),
    ],
)
def test_hebrew_suffix_slug_follows_enumeration_ordinal(suffix: str, expected: str) -> None:
    assert hebrew_suffix_slug(suffix) == expected


def test_enumeration_suffixes_never_collide() -> None:
    canonical = [
        "א", "ב", "ג", "ד", "ה", "ו", "ז", "ח", "ט", "י",
        "יא", "יב", "יג", "יד", "טו", "טז", "יז", "יח", "יט", "כ",
        "כא", "כב", "כג", "כד", "כה", "כו", "כז", "כח", "כט", "ל",
        "לא", "לב", "לג", "לד",
    ]
    slugs = [hebrew_suffix_slug(suffix) for suffix in canonical]
    assert slugs == [latin_ordinal_slug(index) for index in range(1, len(canonical) + 1)]
    assert len(set(slugs)) == len(slugs)


@pytest.mark.parametrize(
    ("ident", "expected"),
    [
        ("121", "121"),
        ("121ב", "121b"),
        ("120ב", "120b"),
        ("66א", "66a"),
        ("103יא", "103k"),
        ("103כ", "103t"),
        ("75טז1", "75p1"),
        ("64א7ב", "64a7b"),
        ("179לד", "179ah"),
        ("ט״ז1", "p1"),
    ],
)
def test_israeli_ident_slug(ident: str, expected: str) -> None:
    assert israeli_ident_slug(ident) == expected


@pytest.mark.parametrize("ident", ["", "121(א)", "121-ב", "121x"])
def test_israeli_ident_slug_rejects_unsupported_identifiers(ident: str) -> None:
    with pytest.raises(ValueError):
        israeli_ident_slug(ident)


def test_hebrew_suffix_slug_accepts_final_forms() -> None:
    assert hebrew_suffix_slug("ך") == hebrew_suffix_slug("כ")


# --- parser ----------------------------------------------------------------


def test_parse_folds_sub_items_and_keeps_editorial_apparatus_out_of_bodies() -> None:
    provisions = parse_israel_openlaw_html(SAMPLE_HTML, source=_sample_source())

    assert [item.kind for item in provisions] == [
        "document",
        "part",
        "chapter",
        "sign",
        "section",
        "section",
        "section",
        "schedule",
        "schedule-item",
    ]
    document, part, chapter, sign, section_2, section_103t, section_64a7b, schedule, item = (
        provisions
    )

    # Navigation nests; sections stay flat, per the Israel citation scheme.
    assert document.citation_path == "il/statute/sample-ordinance"
    assert part.citation_path == "il/statute/sample-ordinance/part-1"
    assert chapter.citation_path == "il/statute/sample-ordinance/part-1/chapter-1"
    assert sign.citation_path == "il/statute/sample-ordinance/part-1/chapter-1/sign-1"
    assert section_2.citation_path == "il/statute/sample-ordinance/section-2"
    assert section_2.parent_citation_path == sign.citation_path
    assert section_2.level == sign.level + 1

    # The table of contents is navigation chrome, never a provision.
    assert all((item.heading or "") != "תוכן עניינים" for item in provisions)

    # A dotted sub-item anchor folds into its section instead of splitting it,
    # and an in-text cross-reference to §121ב does not open a new section.
    assert section_2.body == "מס הכנסה יהא משתלם לפי סעיף 121ב לפקודה.\n(1) השתכרות מכל עסק."
    assert section_2.metadata["sub_item_headings"] == [
        {"identifier": "2.1", "heading": "עסק ומשלח־יד"}
    ]
    assert section_2.heading == "מקורות הכנסה"
    assert section_2.metadata["amendment_history"] == "[תיקון: תשס״ב־9]"
    assert "[תיקון" not in section_2.body


def test_parse_drops_note_only_blocks_but_records_them() -> None:
    provisions = parse_israel_openlaw_html(SAMPLE_HTML, source=_sample_source())
    section = next(item for item in provisions if item.citation_path.endswith("/section-103t"))

    assert section.body == "(א) הוראה ראשונה.\n(ב) הוראה שנייה."
    # The editorial parenthetical and the note-introduced historical table are
    # both gone from the body and both preserved in metadata.
    assert section.metadata["editorial_notes"] == ["(הערת עורך)", "להלן מדרגות המס:"]
    assert "2019" not in (section.body or "")
    assert "10%" not in (section.body or "")


def test_parse_keeps_a_repeal_status_line_as_the_body() -> None:
    provisions = parse_israel_openlaw_html(SAMPLE_HTML, source=_sample_source())
    section = next(item for item in provisions if item.citation_path.endswith("/section-64a7b"))

    assert section.body == "(בוטל)."
    assert section.metadata["status_marker"] == "בוטל"
    assert section.metadata["operative"] is False
    assert section.heading is None


def test_parse_binds_schedule_items_to_their_schedule() -> None:
    provisions = parse_israel_openlaw_html(SAMPLE_HTML, source=_sample_source())
    schedule = next(item for item in provisions if item.kind == "schedule")
    item = next(item for item in provisions if item.kind == "schedule-item")

    assert schedule.citation_path == "il/statute/sample-ordinance/schedule-p1"
    assert schedule.heading == "לוח ט״ז1"
    assert item.citation_path == "il/statute/sample-ordinance/schedule-p1/item-a"
    assert item.parent_citation_path == schedule.citation_path
    assert item.body == "סכום הפרט."


def test_parse_rejects_a_title_that_disagrees_with_the_manifest() -> None:
    with pytest.raises(ValueError, match="title mismatch"):
        parse_israel_openlaw_html(SAMPLE_HTML, source=_sample_source(title="פקודה אחרת"))


def test_parse_rejects_a_page_for_another_knesset_law_id() -> None:
    with pytest.raises(ValueError, match="IsraelLawID"):
        parse_israel_openlaw_html(SAMPLE_HTML, source=_sample_source(israel_law_id="2000198"))


def test_parse_rejects_an_undeclared_duplicate_section_anchor() -> None:
    duplicated = SAMPLE_HTML.replace(
        '<div class="law-number tc_ selflink" id="סעיף_64א7ב">'
        '<a href="#סעיף_64א7ב">64א7ב.</a> </div>',
        '<div class="law-number tc_ selflink" id="סעיף_103כ">'
        '<a href="#סעיף_103כ">103כ.</a> </div>',
    )
    with pytest.raises(ValueError, match="alternate_version_sections"):
        parse_israel_openlaw_html(duplicated, source=_sample_source())

    provisions = parse_israel_openlaw_html(
        duplicated,
        source=_sample_source(alternate_version_sections=["103כ"]),
    )
    paths = [item.citation_path for item in provisions]
    assert "il/statute/sample-ordinance/section-103t" in paths
    assert "il/statute/sample-ordinance/section-103t-alt2" in paths
    base = next(item for item in provisions if item.citation_path.endswith("/section-103t"))
    alternate = next(
        item for item in provisions if item.citation_path.endswith("/section-103t-alt2")
    )
    assert base.metadata["has_alternate_versions"] is True
    assert alternate.metadata["alternate_of"] == base.citation_path


# MediaWiki stops expanding templates once a page exceeds its post-expand
# budget; the marker below is exactly what it leaves behind. It lands after
# §64א7ב's anchor, so the cut takes that half-rendered section with it and the
# last whole section in the primary is §103כ.
SAMPLE_TRUNCATED_HTML = SAMPLE_HTML.replace(
    '''        <h2 class="law-section mw-html-heading">לוח ט״ז1</h2>''',
    '''        <div class="law-content1">שבר<!-- WARNING: template omitted, post-expand include size too large --></div>
        <h2 class="law-section mw-html-heading">לוח ט״ז1</h2>''',
)

SAMPLE_SUPPLEMENT_HTML = """\
<!doctype html>
<html lang="he" dir="rtl">
  <body>
    <div class="mw-content-rtl mw-parser-output" lang="he" dir="rtl">
      <div class="law" id="law-content">
        <p>פקודת דוגמה מתוך</p>
      </div>
      <div class="law-number tc_ selflink" id="סעיף_64א7ב"><a href="#סעיף_64א7ב">64א7ב.</a> </div>
      <div class="law-desc"><span class="law-float"></span>הוראה משלימה</div>
      <div class="law-main"><div>
      </div>
      <div class="law-content1"> הטקסט שנחתך בעמוד המלא.
      </div></div>
      <div class="law-cleaner"></div>
      <h2 class="law-section mw-html-heading">תוספת ראשונה א׳</h2>
      <h4 class="law-subsubsection mw-html-heading">( סעיף 75ג )</h4>
      <div class="law-number tc_ selflink" id="תוספת_1א_פרט_1"><a href="#תוספת_1א_פרט_1">(1)</a> </div>
      <div class="law-desc"><span class="law-float"></span>פרט ראשון</div>
      <div class="law-main"><div>
      </div>
      <div class="law-content1"> תוכן הפרט.
      </div></div>
      <h2 class="law-section mw-html-heading">מונחים המשמשים בפקודת דוגמה</h2>
      <div class="law-main"><div>
      </div>
      <div class="law-content1"> אָבוֹת Ascendants
      </div></div>
      <div class="graytext">אזהרה: המידע נועד להעשרה בלבד.</div>
    </div>
  </body>
</html>
"""


def _truncated_mapping(**overrides: object) -> dict[str, object]:
    mapping: dict[str, object] = {
        "expected_section_count": 3,
        "expected_schedule_item_count": 1,
        "expected_schedule_count": 1,
        "render_truncated_after_section": "103כ",
        "supplement_files": [
            {
                "source_file": "supplement.html",
                "sha256": hashlib.sha256(SAMPLE_SUPPLEMENT_HTML.encode("utf-8")).hexdigest(),
                "note": "the tail MediaWiki dropped",
            }
        ],
        "excluded_headings": ["תוכן עניינים", "מונחים המשמשים בפקודת דוגמה"],
    }
    mapping.update(overrides)
    return _sample_mapping(**mapping)


@pytest.mark.parametrize(
    ("heading_rest", "expected"),
    [
        ("ט״ז1", "טז1"),
        ("א׳", "א"),
        ("ב׳1", "ב1"),
        ("י״ד", "יד"),
        ("ראשונה (אינה חלה)", "1"),
        ("ראשונה א׳", "1א"),
        ("ראשונה א׳1", "1א1"),
        ("שניה", "2"),
        ("ח׳1א (פקע)", "ח1א"),
    ],
)
def test_schedule_heading_ident(heading_rest: str, expected: str) -> None:
    assert schedule_heading_ident(heading_rest) == expected


def test_a_truncated_render_is_refused_unless_the_manifest_declares_it() -> None:
    with pytest.raises(ValueError, match="render_truncated_after_section"):
        parse_israel_openlaw_html(SAMPLE_TRUNCATED_HTML, source=_sample_source())


def test_an_undamaged_render_may_not_claim_to_be_truncated() -> None:
    source = IsraelOpenLawSource.from_mapping(_truncated_mapping())
    with pytest.raises(ValueError, match="carries no truncation marker"):
        parse_israel_openlaw_document(
            source=source, primary_html=SAMPLE_HTML.encode("utf-8")
        )


def test_a_supplement_completes_a_truncated_render() -> None:
    source = IsraelOpenLawSource.from_mapping(_truncated_mapping())
    provisions = parse_israel_openlaw_document(
        source=source,
        primary_html=SAMPLE_TRUNCATED_HTML.encode("utf-8"),
        supplements=((source.supplement_files[0], SAMPLE_SUPPLEMENT_HTML.encode("utf-8")),),
    )
    paths = [item.citation_path for item in provisions]

    # The half-rendered section is cut from the primary and supplied whole.
    from_primary = [i.citation_path for i in provisions if i.source_file == "sample.html"]
    from_supplement = [i.citation_path for i in provisions if i.source_file == "supplement.html"]
    assert "il/statute/sample-ordinance/section-64a7b" not in from_primary
    assert "il/statute/sample-ordinance/section-64a7b" in from_supplement
    assert len(paths) == len(set(paths))

    repaired = next(i for i in provisions if i.citation_path.endswith("/section-64a7b"))
    assert repaired.body == "הטקסט שנחתך בעמוד המלא."
    assert repaired.heading == "הוראה משלימה"

    # Navigation context carries across fragments, and the h4 is a caption.
    schedule = next(i for i in provisions if i.kind == "schedule")
    assert schedule.citation_path == "il/statute/sample-ordinance/schedule-1a"
    assert schedule.metadata["caption"] == "( סעיף 75ג )"
    item = next(i for i in provisions if i.kind == "schedule-item")
    assert item.citation_path == "il/statute/sample-ordinance/schedule-1a/item-1"

    # The glossary and the project disclaimer are not law.
    bodies = " ".join(i.body or "" for i in provisions)
    assert "Ascendants" not in bodies
    assert "להעשרה בלבד" not in bodies

    document = provisions[0]
    assert document.metadata["render_truncated_after_section"] == "103כ"


def test_truncation_boundary_must_match_the_declaration() -> None:
    source = IsraelOpenLawSource.from_mapping(
        _truncated_mapping(render_truncated_after_section="2")
    )
    with pytest.raises(ValueError, match="truncates after section"):
        parse_israel_openlaw_document(
            source=source,
            primary_html=SAMPLE_TRUNCATED_HTML.encode("utf-8"),
            supplements=((source.supplement_files[0], SAMPLE_SUPPLEMENT_HTML.encode("utf-8")),),
        )


def test_a_truncated_source_must_supply_a_supplement() -> None:
    with pytest.raises(ValueError, match="no supplement_files"):
        IsraelOpenLawSource.from_mapping(
            _sample_mapping(render_truncated_after_section="103כ")
        )


# --- manifest --------------------------------------------------------------


@pytest.mark.parametrize(
    ("overrides", "error"),
    [
        ({"jurisdiction": "us"}, "jurisdiction must be il"),
        ({"document_class": "regulation"}, "document_class must be statute"),
        ({"language": "en"}, "language must be he"),
        ({"language": True}, "not a YAML boolean"),
        ({"source_url": "https://www.nevo.co.il/law_html/law01/255_001.htm"}, "he.wikisource.org"),
        ({"sha256": "abc"}, "SHA-256"),
        ({"source_file": "../escape.html"}, "plain file name"),
        ({"source_file": "sample.pdf"}, "must be HTML"),
        ({"israel_law_id": "2000944x"}, "only digits"),
        ({"expected_section_count": -1}, "expected_section_count"),
        ({"instrument_slug": "Income_Tax"}, "instrument_slug"),
        ({"source_tier": "primary-official"}, "unsupported source_tier"),
        ({"source_tier": "consolidation-nevo"}, "unsupported source_tier"),
    ],
)
def test_manifest_rejects_invalid_rows(overrides: dict[str, object], error: str) -> None:
    with pytest.raises(ValueError, match=error):
        IsraelOpenLawSource.from_mapping(_sample_mapping(**overrides))


def test_manifest_rejects_duplicate_instruments(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps(
            {"documents": [_sample_mapping(), _sample_mapping(source_id="other")]},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate Israel instrument_slug"):
        IsraelOpenLawManifest.load(path)


# --- extraction ------------------------------------------------------------


def test_extract_writes_versioned_complete_artifacts(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    payload = SAMPLE_HTML.encode("utf-8")
    (source_dir / "sample.html").write_bytes(payload)
    manifest_path = tmp_path / "manifest.json"
    _write_manifest(manifest_path, _sample_mapping(sha256=hashlib.sha256(payload).hexdigest()))
    store = CorpusArtifactStore(tmp_path / "corpus")

    report = extract_israel_openlaw(
        store,
        version="2026-09-06-sample",
        manifest_path=manifest_path,
        source_dir=source_dir,
    )

    assert report.jurisdiction == "il"
    assert report.document_class == "statute"
    assert report.section_count == 3
    assert report.schedule_item_count == 1
    assert report.provisions_written == 9
    assert report.coverage.complete

    provisions = load_provisions(report.provisions_path)
    inventory = load_source_inventory(report.inventory_path)
    assert len(provisions) == len(inventory) == 9
    assert {record.language for record in provisions} == {"he"}
    assert {record.source_format for record in provisions} == {ISRAEL_OPENLAW_SOURCE_FORMAT}
    assert {record.expression_date for record in provisions} == {"2026-06-08"}
    assert {record.source_as_of for record in provisions} == {"2026-09-06"}
    assert all(record.body for record in provisions)
    section = next(record for record in provisions if record.citation_path.endswith("/section-2"))
    assert section.id == deterministic_provision_id(section.citation_path, "2026-09-06-sample")
    assert section.source_path == (
        "sources/il/statute/2026-09-06-sample/openlaw/sample.html"
    )
    assert section.metadata is not None
    assert section.metadata["source_tier"] == "consolidation-knesset-linked"
    assert section.metadata["knesset_full_text_link_verified"] is True
    assert section.identifiers is not None
    assert section.identifiers["knesset.gov.il:israel_law_id"] == "2000944"


def test_extract_rejects_a_hash_mismatch_before_writing_artifacts(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "sample.html").write_bytes(SAMPLE_HTML.encode("utf-8"))
    manifest_path = tmp_path / "manifest.json"
    _write_manifest(manifest_path, _sample_mapping())
    corpus_root = tmp_path / "corpus"

    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        extract_israel_openlaw(
            CorpusArtifactStore(corpus_root),
            version="2026-09-06-sample",
            manifest_path=manifest_path,
            source_dir=source_dir,
        )
    assert not corpus_root.exists()


def test_extract_rejects_a_structural_count_drift_before_writing_artifacts(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    payload = SAMPLE_HTML.encode("utf-8")
    (source_dir / "sample.html").write_bytes(payload)
    manifest_path = tmp_path / "manifest.json"
    _write_manifest(
        manifest_path,
        _sample_mapping(sha256=hashlib.sha256(payload).hexdigest(), expected_section_count=4),
    )
    corpus_root = tmp_path / "corpus"

    with pytest.raises(ValueError, match="expected_section_count mismatch"):
        extract_israel_openlaw(
            CorpusArtifactStore(corpus_root),
            version="2026-09-06-sample",
            manifest_path=manifest_path,
            source_dir=source_dir,
        )
    assert not corpus_root.exists()


# --- checked-in pilot pack -------------------------------------------------


# --- statutory tables and their labels -------------------------------------

SCHEDULE_TITLE = "חוק דוגמה [נוסח משולב]"
SCHEDULE_URL = "https://he.wikisource.org/wiki/%D7%97%D7%95%D7%A7_%D7%93%D7%95%D7%92%D7%9E%D7%94"

# The four table shapes the real snapshots contain, each reduced to its
# structure: the two retirement ladders of NII לוח א׳1 that only their h4
# labels tell apart; לוח ח׳2, whose cells carry amendment notes; לוח י׳, whose
# two statutory versions are labelled by parenthesised notes outside the
# tables; לוח י״ז, definitions followed by an information table; and the
# one genuinely editorial block — the 2019-2027 comparison OpenLaw prints for
# itself under ITO §121, behind an unparenthesised lead-in.  Then the three note
# shapes that carry legal effect without a table and without a terminating colon:
# a sign headed by nothing but its applicability window (NII פרק ז׳ סימן ט׳), an
# inline rate substitution (NII §340א), and a re-reading instruction (ITO §14) —
# each printed next to one of the project's own value glosses, which must not move.
SCHEDULE_HTML = """\
<!doctype html>
<html lang="he" dir="rtl">
  <body>
    <div class="mw-parser-output">
      <div class="law" id="law-content">
        <h1 class="law-title mw-html-heading">חוק דוגמה [נוסח משולב]</h1>
        <hr class="law-separator"/>
        <div>2000198 ס״ח תשנ״ה, 210</div>
        <h2 class="law-section mw-html-heading">לוח א׳1</h2>
        <h4 class="law-subsubsection mw-html-heading">(סעיפים 1, 158, 403(ה) ו־406(א))</h4>
        <h3 class="law-subsection mw-html-heading">חלק א׳</h3>
        <h4 class="law-subsubsection mw-html-heading">(סעיפים 1 (ההגדרה ”גיל הפרישה“), 403(ה))</h4>
        <h4 class="law-subsubsection mw-html-heading">גיל הפרישה לגבר</h4>
        <div class="law-main"><div>
        </div>
        <div class="law-content1">
        <table><tbody>
        <tr><th>חודש הלידה</th><th>גיל הזכאות (בשנים)</th></tr>
        <tr><td>עד יוני 1939</td><td>65</td></tr>
        </tbody></table>
        </div></div>
        <div class="law-cleaner"></div>
        <h4 class="law-subsubsection mw-html-heading">גיל הפרישה לאישה</h4>
        <div class="law-main"><div>
        </div>
        <div class="law-content1">
        <table><tbody>
        <tr><th>חודש הלידה</th><th>גיל הזכאות (בשנים)</th></tr>
        <tr><td>עד יוני 1944</td><td>60</td></tr>
        </tbody></table>
        </div></div>
        <div class="law-cleaner"></div>
        <h2 class="law-section mw-html-heading">לוח ח׳2</h2>
        <h4 class="law-subsubsection mw-html-heading">(סעיף 223)</h4>
        <div class="law-desc"><span class="law-float"></span> <span
          class="law-note">[תיקון: תשע״ח־8]</span></div>
        <div class="law-main"><div>
        </div>
        <div class="law-content1">
        <table style="width: 100%; table-layout: fixed;"><tbody>
        <tr><th>טור א׳ שירותי הסיעוד</th><th>טור ב׳ שווי ביחידות שירות</th></tr>
        <tr><td>שעה אחת של טיפול אישי במבוטח בביתו</td><td><span
          class="law-note">(הוראת שעה בשנים 2026 עד 2029):</span> יחידה אחת</td></tr>
        </tbody></table>
        </div></div>
        <div class="law-cleaner"></div>
        <h2 class="law-section mw-html-heading">לוח י׳</h2>
        <h4 class="law-subsubsection mw-html-heading">(סעיפים 28, 32 ו־337 עד 342)</h4>
        <h3 class="law-subsection mw-html-heading">שיעור דמי ביטוח בעד אפריל שנת 2011 ואילך</h3>
        <div class="law-main"><div>
        </div>
        <div class="law-content1"> <span class="law-note">(הוראת שעה לשנים 2025–2026):</span>
        </div>
        <div class="law-content1">
        <table style="width: 100%; table-layout: fixed;"><tbody>
        <tr><th>אחוזים מההכנסה או מהשכר לפי סעיפים 337(א) ו־340(א)</th></tr>
        <tr><td>3.23</td></tr>
        </tbody></table>
        </div>
        <div class="law-content1"> <span class="law-note">(הנוסח הקבוע):</span>
        </div>
        <div class="law-content1">
        <table style="width: 100%; table-layout: fixed;"><tbody>
        <tr><th>אחוזים מההכנסה או מהשכר לפי סעיפים 337(א) ו־340(א)</th></tr>
        <tr><td>3.85</td></tr>
        </tbody></table>
        </div></div>
        <div class="law-cleaner"></div>
        <h2 class="law-section mw-html-heading">לוח י״ז</h2>
        <h4 class="law-subsubsection mw-html-heading">(סעיף 384א)</h4>
        <div class="law-main"><div>
        </div>
        <div class="law-content1"> בלוח זה – ”מידע על הכנסה מעבודה או משלח יד“.
        </div></div>
        <div class="law-cleaner"></div>
        <div class="law-main"><div>
        </div>
        <div class="law-content1">
        <table style="width: 100%; tabl-layout: fixed;"><tbody>
        <tr><th>טור א׳ סוג הגמלה</th><th>טור ב׳ מקור חוקי</th></tr>
        <tr><td>מענק אשפוז</td><td>סעיף 43 לחוק<span class="law-note">י</span></td></tr>
        </tbody></table>
        </div></div>
        <div class="law-cleaner"></div>
        <div class="law-number tc_ selflink" id="סעיף_121"><a href="#סעיף_121">121.</a> </div>
        <div class="law-desc"><span class="law-float"></span>שיעור המס ליחיד</div>
        <div class="law-main"><div>
        </div>
        <div class="law-content1"> על הכנסה חייבת של יחיד יוטל מס <span
          class="law-note">[תיקון: תשפ״ה־2]</span> <span class="law-note">(נקוב לשנת 2015;
          בשנת 2023, 141,840 ש״ח)</span>.
        </div></div>
        <div class="law-cleaner"></div>
        <div class="law-main"><div>
        </div>
        <div class="law-content1"> <span class="law-note">להלן מדרגות המס לשנים 2019 עד 2027:</span>
        <div style="text-align: right;">
        <table style="font-size: 75%; width: 100%;"><tbody>
        <tr><td>2019 עד 75,720</td><td>10%</td></tr>
        </tbody></table>
        </div>
        </div></div>
        <div class="law-cleaner"></div>
        <div class="law-number tc_ selflink" id="סעיף_348"><a href="#סעיף_348">348.</a> </div>
        <div class="law-desc"><span class="law-float"></span>הכנסה מזערית</div>
        <div class="law-main"><div>
        </div>
        <div class="law-number2 tc_">(א) </div>
        <div class="law-content2"> לא יבוא בחשבון סכום ההכנסה העולה על הסכום המרבי.
        </div>
        <div class="law-number2 tc_">(ב) </div>
        <div class="law-content2"> <span class="law-note">(הנוסח הקבוע):</span> מתנדב בשירות
        לאומי יראו כאילו הכנסתו היתה הסכום המזערי.
        </div>
        <div class="law-content2"> <span class="law-note">(הוראת שעה עד יום 31.8.2026):</span>
        מתנדב בשירות לאומי־אזרחי יראו כאילו הכנסתו היתה הסכום המזערי.
        </div>
        <div class="law-number2 tc_">(ג) </div>
        <div class="law-content2"> <span class="law-note">(נמחק).</span>
        </div>
        <div class="law-number2 tc_">(ד) </div>
        <div class="law-content2"> <span class="law-note">(פקע).</span>
        </div></div>
        <div class="law-cleaner"></div>
        <div class="law-number tc_ selflink" id="סעיף_11"><a href="#סעיף_11">11.</a> </div>
        <div class="law-desc"><span class="law-float"></span>יישוב מוטב</div>
        <div class="law-main"><div>
        </div>
        <div class="law-content1"> <span class="law-note">(הוראת שעה לשנים 2026 עד 2029):</span>
        תושב יישוב מוטב זכאי להנחה ממס.
        </div></div>
        <div class="law-cleaner"></div>
        <h2 class="law-section mw-html-heading">פרק ז׳: ביטוח אבטלה</h2>
        <h3 class="law-subsection mw-html-heading">סימן ט׳: הוראות מיוחדות</h3>
        <div class="law-main"><div>
        </div>
        <div class="law-content1"> <span
          class="law-note">(הוראת שעה מיום 31.3.2026 עד יום 31.3.2027):</span>
        </div></div>
        <div class="law-cleaner"></div>
        <div class="law-number tc_ selflink" id="סעיף_340א"><a href="#סעיף_340א">340א.</a> </div>
        <div class="law-desc"><span class="law-float"></span>דמי ביטוח לעובד במשק בית</div>
        <div class="law-main"><div>
        </div>
        <div class="law-number2 tc_">(א) </div>
        <div class="law-content2"> דמי הביטוח יהיו בשיעור של 6.25% <span
          class="law-note">(בשנים 2025–2026: 7.85%)</span> מהשכר.
        </div>
        <div class="law-content2"> ”השכר הממוצע“ – כמשמעותו בסעיף 2 <span
          class="law-note">(לעניין הגדרה זו, השכר הממוצע בשנת 2025: 12,536 ש״ח)</span>.
        </div>
        <div class="law-content2"> ”תושב חוזר ותיק“ – מי שהיה תושב חוץ עשר שנים רצופות <span
          class="law-note">(לגבי מי שהיה לתושב ישראל, יקראו ”חמש שנים“ במקום ”עשר שנים“)</span>.
        </div></div>
      </div>
    </div>
  </body>
</html>
"""


def _schedule_source() -> IsraelOpenLawSource:
    return IsraelOpenLawSource.from_mapping(
        {
            "source_id": "sample-insurance-law",
            "jurisdiction": "il",
            "document_class": "statute",
            "instrument_slug": "sample-insurance-law",
            "israel_law_id": "2000198",
            "title": SCHEDULE_TITLE,
            "title_en": "Sample Law [Consolidated Version]",
            "source_url": SCHEDULE_URL,
            "source_file": "sample-insurance-law.html",
            "sha256": "0" * 64,
            "source_as_of": "2026-09-06",
            "expression_date": "2026-06-15",
            "expression_date_basis": "Knesset OData KNS_IsraelLaw.LatestPublicationDate",
            "source_tier": "consolidation-wikisource",
            "language": "he",
            "expected_section_count": 4,
            "expected_schedule_item_count": 0,
            "expected_schedule_count": 4,
            "expected_part_count": 0,
            "expected_chapter_count": 1,
            "expected_sign_count": 3,
        }
    )


def _schedule_provisions() -> dict[str, object]:
    return {
        item.citation_path: item
        for item in parse_israel_openlaw_html(SCHEDULE_HTML, source=_schedule_source())
    }


SAMPLE_LAW = "il/statute/sample-insurance-law"


def test_removing_editorial_notes_keeps_the_statutory_table_it_annotates() -> None:
    """A note inside a table marks statutory text being amended, not apparatus.

    This is the לוח ח׳2 shape: before the repair the whole block was discarded
    because nothing but a table was left after note removal, and the schedule
    body fell back to its own heading.
    """
    provisions = _schedule_provisions()
    schedule = provisions[f"{SAMPLE_LAW}/schedule-h2"]

    assert schedule.body is not None
    assert "טור א׳ שירותי הסיעוד | טור ב׳ שווי ביחידות שירות" in schedule.body
    # The note is the statute's own temporary-order marker on that cell, so it stays
    # in the cell it qualifies rather than being lifted into a positionless list.
    assert (
        "שעה אחת של טיפול אישי במבוטח בביתו | (הוראת שעה בשנים 2026 עד 2029): יחידה אחת"
        in schedule.body
    )
    assert schedule.metadata is not None
    assert schedule.metadata["statutory_notes"] == ["(הוראת שעה בשנים 2026 עד 2029):"]


def test_parenthesised_version_labels_do_not_delete_their_tables() -> None:
    """The לוח י׳ shape: both contribution-rate tables are statutory.

    ``(הוראת שעה …)`` / ``(הנוסח הקבוע)`` are the statute's own version labels,
    printed in parentheses; only an unparenthesised lead-in introduces the
    project's apparatus.  Both tables must reach the body.
    """
    provisions = _schedule_provisions()
    sign = provisions[f"{SAMPLE_LAW}/schedule-j/sign-1"]

    assert sign.body is not None
    assert sign.body.count("אחוזים מההכנסה או מהשכר לפי סעיפים 337(א) ו־340(א)") == 2
    assert "3.23" in sign.body
    assert "3.85" in sign.body


def test_each_version_label_stays_above_the_table_it_labels() -> None:
    """Two identical-header rate tables are told apart only by their version label.

    Restoring the tables without their labels leaves the body printing them back to
    back with nothing between them — the same defect the h4 repair fixed for the two
    ladders of לוח א׳1.  The labels belong in the body, immediately above their own
    table, not in a flat positionless list.
    """
    provisions = _schedule_provisions()
    sign = provisions[f"{SAMPLE_LAW}/schedule-j/sign-1"]

    assert sign.body is not None
    lines = sign.body.split("\n")
    openings = [index for index, line in enumerate(lines) if line.startswith("אחוזים מההכנסה")]
    assert len(openings) == 2
    assert lines[openings[0] - 1] == "(הוראת שעה לשנים 2025–2026):"
    assert lines[openings[1] - 1] == "(הנוסח הקבוע):"
    # Recorded as statutory, not as apparatus that was removed.
    assert sign.metadata is not None
    assert sign.metadata["statutory_notes"] == [
        "(הוראת שעה לשנים 2025–2026):",
        "(הנוסח הקבוע):",
    ]
    assert "editorial_notes" not in sign.metadata


def test_a_repeal_or_expiry_marker_stays_on_the_entry_it_governs() -> None:
    """A schedule entry the statute repeals must not read as though in force."""
    provisions = _schedule_provisions()
    schedule = provisions[f"{SAMPLE_LAW}/schedule-h2"]

    assert schedule.body is not None
    assert "(הוראת שעה בשנים 2026 עד 2029):" in schedule.body


def test_a_repealed_subsection_of_a_live_section_keeps_its_marker() -> None:
    """(נמחק) / (פקע) on a limb of a section that is still in force.

    Dropping these left a bare enumerator behind — ITO §5 read
    ``(1) (2) (3) (4) (א) (ב) שר האוצר…``, five repealed limbs collapsed into a run
    of empty labels flowing into the text of the one that survives.
    """
    provisions = _schedule_provisions()
    section = provisions[f"{SAMPLE_LAW}/section-348"]

    assert section.body is not None
    assert "(ג) (נמחק)." in section.body
    assert "(ד) (פקע)." in section.body
    # The section itself is in force, so it is NOT given a section-level status marker.
    assert section.metadata is not None
    assert "status_marker" not in section.metadata
    assert "operative" not in section.metadata


def test_a_version_label_away_from_any_table_is_kept_too() -> None:
    """The NII §348(ה) shape: two competing versions printed consecutively.

    Neither is near a table, so a table-adjacency rule would miss them and the
    temporary-order version would read as a continuation of the permanent one.
    """
    provisions = _schedule_provisions()
    section = provisions[f"{SAMPLE_LAW}/section-348"]

    assert section.body is not None
    permanent = section.body.index("(הנוסח הקבוע):")
    temporary = section.body.index("(הוראת שעה עד יום 31.8.2026):")
    assert permanent < section.body.index("לאומי יראו כאילו") < temporary
    assert temporary < section.body.index("לאומי־אזרחי יראו כאילו")
    assert section.metadata is not None
    assert section.metadata["statutory_notes"] == [
        "(הנוסח הקבוע):",
        "(הוראת שעה עד יום 31.8.2026):",
        "(נמחק).",
        "(פקע).",
    ]


def test_a_sunset_window_on_a_whole_section_is_kept() -> None:
    """ITO §11's confrontation-line credits read as permanent without their window."""
    provisions = _schedule_provisions()
    section = provisions[f"{SAMPLE_LAW}/section-11"]

    assert section.body is not None
    assert section.body.startswith("(הוראת שעה לשנים 2026 עד 2029):")


def test_a_standalone_applicability_label_is_the_body_it_heads() -> None:
    """A block holding nothing but a window label is not a status line.

    NII פרק ז׳ סימן ט׳ — the wartime unemployment provisions — is headed by one note
    and nothing else: ``(הוראת שעה מיום 31.3.2026 עד יום 31.3.2027):``.  Treating every
    note-only block as a repeal/expiry line dropped that window into
    ``editorial_notes``, and the sign read as though it applied indefinitely.
    """
    provisions = _schedule_provisions()
    sign = provisions[f"{SAMPLE_LAW}/chapter-1/sign-1"]

    assert sign.body == "סימן ט׳: הוראות מיוחדות\n(הוראת שעה מיום 31.3.2026 עד יום 31.3.2027):"
    assert sign.metadata is not None
    assert sign.metadata["statutory_notes"] == ["(הוראת שעה מיום 31.3.2026 עד יום 31.3.2027):"]
    assert "editorial_notes" not in sign.metadata
    # It is a window, not a repeal: the sign stays in force and gets no status marker.
    assert "status_marker" not in sign.metadata
    assert "operative" not in sign.metadata


def test_a_note_only_status_line_still_becomes_the_section_status() -> None:
    """The negative control for the block above: a real status line is unchanged."""
    provisions = parse_israel_openlaw_html(SAMPLE_HTML, source=_sample_source())
    section = next(item for item in provisions if item.citation_path.endswith("/section-64a7b"))

    assert section.body == "(בוטל)."
    assert section.metadata["status_marker"] == "בוטל"
    assert section.metadata["operative"] is False


def test_an_inline_rate_substitution_stays_where_it_is_printed() -> None:
    """NII §340א's 6.25% is not the rate in force in 2025–2026; 7.85% is.

    The substitution is neither in a table cell nor colon-terminated, so the earlier
    rule deleted it and the body conveyed only the permanent rate for the pilot year.
    """
    provisions = _schedule_provisions()
    section = provisions[f"{SAMPLE_LAW}/section-340a"]

    assert section.body is not None
    assert "בשיעור של 6.25% (בשנים 2025–2026: 7.85%) מהשכר." in section.body
    assert section.metadata is not None
    assert "(בשנים 2025–2026: 7.85%)" in section.metadata["statutory_notes"]


def test_a_re_reading_instruction_stays_in_the_definition_it_amends() -> None:
    """``יקראו … במקום …`` replaces wording for the cohort it names."""
    provisions = _schedule_provisions()
    section = provisions[f"{SAMPLE_LAW}/section-340a"]

    assert section.body is not None
    assert (
        "”תושב חוזר ותיק“ – מי שהיה תושב חוץ עשר שנים רצופות "
        "(לגבי מי שהיה לתושב ישראל, יקראו ”חמש שנים“ במקום ”עשר שנים“)." in section.body
    )
    assert section.metadata is not None
    assert (
        "(לגבי מי שהיה לתושב ישראל, יקראו ”חמש שנים“ במקום ”עשר שנים“)"
        in section.metadata["statutory_notes"]
    )


def test_an_indexed_value_gloss_is_not_a_substitution() -> None:
    """The line between a substitution and one of the project's own figures.

    ``(לעניין הגדרה זו, השכר הממוצע בשנת 2025: 12,536 ש״ח)`` has the same
    ``(qualifier: value)`` shape as the rate substitution beside it, but it supplies a
    shekel figure the statute leaves to indexation rather than wording the statute
    replaces.  The citation scheme takes current-year regulated amounts only from
    official publications captured under ``il/policies/``, so it stays apparatus.
    """
    provisions = _schedule_provisions()
    section = provisions[f"{SAMPLE_LAW}/section-340a"]

    assert section.body is not None
    assert "12,536" not in section.body
    assert "”השכר הממוצע“ – כמשמעותו בסעיף 2." in section.body
    assert section.metadata is not None
    assert section.metadata["editorial_notes"] == [
        "(לעניין הגדרה זו, השכר הממוצע בשנת 2025: 12,536 ש״ח)"
    ]


def test_the_projects_own_glosses_still_never_reach_a_body() -> None:
    """Not every parenthesised note is the statute's.

    OpenLaw annotates indexed money amounts with its own parenthetical, and marks
    amendment history in brackets.  Neither is attached to a table, so neither is
    kept; only cell-level markers and table version labels are.
    """
    provisions = _schedule_provisions()
    section = provisions[f"{SAMPLE_LAW}/section-121"]

    assert section.body is not None
    assert "נקוב לשנת" not in section.body
    assert "תיקון:" not in section.body
    assert section.metadata is not None
    assert "(נקוב לשנת 2015; בשנת 2023, 141,840 ש״ח)" in section.metadata["editorial_notes"]
    assert "statutory_notes" not in section.metadata


def test_a_table_following_definitions_stays_with_them() -> None:
    """The לוח י״ז shape: the definitions survived, the table did not.

    Its notes are OpenLaw's bare footnote letters inside table cells, which is what
    made the pre-repair adapter discard the whole block; they are not parenthesised,
    so they stay out of the body while the table it annotated stays in.
    """
    provisions = _schedule_provisions()
    schedule = provisions[f"{SAMPLE_LAW}/schedule-q"]

    assert schedule.body is not None
    assert "בלוח זה – ”מידע על הכנסה מעבודה או משלח יד“." in schedule.body
    assert "טור א׳ סוג הגמלה | טור ב׳ מקור חוקי" in schedule.body
    assert "מענק אשפוז | סעיף 43 לחוק" in schedule.body
    assert schedule.metadata is not None
    assert schedule.metadata["editorial_notes"] == ["י"]


def test_the_projects_own_comparison_table_is_still_dropped() -> None:
    """The one genuinely editorial block: OpenLaw's 2019-2027 §121 comparison.

    This is the negative control, and it passes against the pre-repair adapter too —
    by design.  It does not prove the repair; it guards against over-correcting it
    later and letting the project's apparatus into a body.
    """
    provisions = _schedule_provisions()
    section = provisions[f"{SAMPLE_LAW}/section-121"]

    assert section.body == "על הכנסה חייבת של יחיד יוטל מס."
    assert "75,720" not in (section.body or "")
    assert section.metadata is not None
    assert section.metadata["editorial_notes"] == [
        "[תיקון: תשפ״ה־2]",
        "(נקוב לשנת 2015; בשנת 2023, 141,840 ש״ח)",
        "להלן מדרגות המס לשנים 2019 עד 2027:",
    ]


def test_statutory_subheadings_label_their_own_tables() -> None:
    """Two identically-headed retirement ladders, told apart only by their h4."""
    provisions = _schedule_provisions()
    sign = provisions[f"{SAMPLE_LAW}/schedule-a1/sign-1"]

    assert sign.body is not None
    male = sign.body.index("גיל הפרישה לגבר")
    female = sign.body.index("גיל הפרישה לאישה")
    assert male < sign.body.index("עד יוני 1939 | 65") < female
    assert female < sign.body.index("עד יוני 1944 | 60")
    # Every subheading is kept in printed order; none overwrites another, and the
    # caption the schedule prints under its own name stays first.
    assert sign.metadata is not None
    assert sign.metadata["captions"] == [
        "(סעיפים 1 (ההגדרה ”גיל הפרישה“), 403(ה))",
        "גיל הפרישה לגבר",
        "גיל הפרישה לאישה",
    ]
    assert sign.metadata["caption"] == "(סעיפים 1 (ההגדרה ”גיל הפרישה“), 403(ה))"
    # The schedule above it keeps its own caption; neither node steals the other's.
    schedule = provisions[f"{SAMPLE_LAW}/schedule-a1"]
    assert schedule.metadata is not None
    assert schedule.metadata["captions"] == ["(סעיפים 1, 158, 403(ה) ו־406(א))"]
    assert schedule.body == "לוח א׳1\n(סעיפים 1, 158, 403(ה) ו־406(א))"


def test_a_navigation_node_leads_with_its_own_name() -> None:
    """A content-bearing לוח must not read as a bare table."""
    provisions = _schedule_provisions()
    schedule = provisions[f"{SAMPLE_LAW}/schedule-h2"]

    assert schedule.heading == "לוח ח׳2"
    assert schedule.body is not None
    assert schedule.body.startswith("לוח ח׳2\n(סעיף 223)\n")


def test_pilot_manifest_pins_both_instruments() -> None:
    manifest = IsraelOpenLawManifest.load(IL_PILOT_MANIFEST)

    assert {source.instrument_slug for source in manifest.documents} == {
        "income-tax-ordinance",
        "national-insurance-law-1995",
    }
    assert {source.israel_law_id: source.expression_date for source in manifest.documents} == {
        "2000944": "2026-06-08",
        "2000198": "2026-06-15",
    }
    assert {source.source_as_of for source in manifest.documents} == {"2026-09-06"}
    assert {source.language for source in manifest.documents} == {"he"}
    counts = {source.instrument_slug: source.expected_section_count for source in manifest.documents}
    assert counts == {"income-tax-ordinance": 577, "national-insurance-law-1995": 561}
    # The Knesset "לחוק המלא" link was followed for the Ordinance only, so the
    # National Insurance Law claims the weaker tier until that check is done.
    assert {source.instrument_slug: source.source_tier for source in manifest.documents} == {
        "income-tax-ordinance": "consolidation-knesset-linked",
        "national-insurance-law-1995": "consolidation-wikisource",
    }
    for source in manifest.documents:
        snapshot = IL_PILOT_SOURCE_DIR / source.source_file
        assert hashlib.sha256(snapshot.read_bytes()).hexdigest() == source.sha256


def test_checked_in_pilot_pack_parses_to_exact_counts(tmp_path: Path) -> None:
    store = CorpusArtifactStore(tmp_path / "corpus")
    report = extract_israel_openlaw(
        store,
        version=IL_PILOT_VERSION,
        manifest_path=IL_PILOT_MANIFEST,
        source_dir=IL_PILOT_SOURCE_DIR,
    )

    assert report.document_count == 2
    assert report.section_count == 1138
    assert report.schedule_item_count == 46
    assert report.navigation_count == 228
    assert report.provisions_written == 1414
    assert report.coverage.complete

    provisions = {record.citation_path: record for record in load_provisions(report.provisions_path)}

    rate_schedule = provisions[f"{ITO}/section-121"]
    assert rate_schedule.heading == "שיעור המס ליחיד"
    assert rate_schedule.body is not None
    for percentage in ("10%", "14%", "20%", "31%", "35%", "47%"):
        assert percentage in rate_schedule.body
    for edge in ("84,120", "120,720", "228,000", "301,200", "560,280"):
        assert edge in rate_schedule.body
    # The 2019-2027 comparison table OpenLaw prints under §121 is editorial.
    assert "75,720" not in rate_schedule.body
    assert rate_schedule.metadata is not None
    assert any(
        note.startswith("(הסכומים מתואמים")
        for note in rate_schedule.metadata["editorial_notes"]
    )

    resident_credit = provisions[f"{ITO}/section-34"]
    assert resident_credit.body == (
        "בחישוב המס של יחיד שהיה תושב ישראל בשנת המס יובאו בחשבון שתי נקודות זיכוי."
    )
    travel_credit = provisions[f"{ITO}/section-36"]
    assert travel_credit.body is not None
    assert "1⁄4" in travel_credit.body

    surtax = provisions[f"{ITO}/section-121b"]
    assert surtax.heading == "מס נוסף על הכנסות גבוהות"

    child_allowance = provisions[f"{NII}/section-66"]
    assert child_allowance.heading is not None
    assert child_allowance.heading.startswith("זכות לקצבת ילדים")
    assert child_allowance.body is not None
    assert "סעיף 121ב לפקודת מס הכנסה" in child_allowance.body
    assert f"{NII}/section-65" in provisions
    assert f"{NII}/section-335" in provisions

    # The National Insurance Law prints §283 twice; both survive, distinctly.
    assert provisions[f"{NII}/section-283-alt2"].metadata is not None
    assert provisions[f"{NII}/section-283-alt2"].metadata["alternate_version"] is True

    # OpenLaw prints "57א" against the anchor for §57ג; the anchor wins and the
    # disagreement is recorded rather than silently resolved.
    assert {
        record.metadata["source_tier"]
        for record in provisions.values()
        if record.metadata and record.citation_path.startswith(NII)
    } == {"consolidation-wikisource"}

    mismatched = provisions[f"{NII}/section-57c"]
    assert mismatched.metadata is not None
    assert mismatched.metadata["printed_label_mismatch"] is True
    assert mismatched.metadata["printed_label"] == "57א"

    assert all(record.body for record in provisions.values())
    assert all(record.expression_date for record in provisions.values())
    assert all(record.language == "he" for record in provisions.values())


def test_checked_in_pilot_keeps_the_incorporated_statutory_tables() -> None:
    """The committed rows for the three schedules that lost their tables.

    NII לוח ח׳2, the §337(א)/§340(א) contribution-rate table under לוח י׳, and
    לוח י״ז each had their table deleted with the editorial notes around it and
    fell back to a heading-only body.  These are the rows as published.
    """
    provisions = {
        record.citation_path: record
        for record in load_provisions(
            REPO_ROOT
            / "data"
            / "corpus"
            / "provisions"
            / "il"
            / "statute"
            / f"{IL_PILOT_VERSION}.jsonl"
        )
    }

    nursing = provisions[f"{NII}/schedule-h2"]
    assert nursing.heading == "לוח ח׳2"
    assert nursing.body is not None
    assert "טור א׳\nשירותי הסיעוד | טור ב׳\nשווי ביחידות שירות" in nursing.body
    assert "בשעות הלילה – יחידה וחצי;" in nursing.body
    # The entry the statute repeals on 31.12.2026 must not read as though in force,
    # and the lapsed entry must not read as live.
    assert "(יבוטל ביום 31.12.2026): שירות כביסה של עד 5 ק״ג;" in nursing.body
    assert "(פקע)." in nursing.body

    contributions = provisions[f"{NII}/schedule-j/sign-1"]
    assert contributions.heading == "שיעור דמי ביטוח בעד אפריל שנת 2011 ואילך"
    assert contributions.body is not None
    # The rates NII §337(א) incorporates by reference to this לוח.
    assert (
        contributions.body.count("אחוזים מההכנסה או מהשכר לפי סעיפים 337(א) ו־340(א)") == 2
    )
    assert "עובד" in contributions.body
    # Two identical-header rate tables; each keeps the label saying which one it is.
    body_lines = contributions.body.split("\n")
    openings = [
        index for index, line in enumerate(body_lines) if line.startswith("טור א׳ | טור ב׳")
    ]
    assert len(openings) == 2
    assert body_lines[openings[0] - 1] == "(הוראת שעה לשנים 2025–2026):"
    assert body_lines[openings[1] - 1] == "(הנוסח הקבוע):"
    # The temporary-order substitution for the total rate reaches the body too.
    assert "(הוראת שעה בשנים 2024 עד 2027: 14.60)" in contributions.body

    information = provisions[f"{NII}/schedule-q"]
    assert information.heading == "לוח י״ז"
    assert information.body is not None
    assert "טור א׳\nסוג הגמלה | טור ב׳\nמקור חוקי | טור ג׳\nסוגי המידע" in information.body
    assert "מענק אשפוז | סעיף 43 לחוק" in information.body
    # The definitions that used to be the whole body are still there.
    assert "בלוח זה –" in information.body

    retirement = provisions[f"{NII}/schedule-a1/sign-1"]
    assert retirement.body is not None
    male = retirement.body.index("גיל הפרישה לגבר")
    female = retirement.body.index("גיל הפרישה לאישה")
    assert male < retirement.body.index("עד יוני 1939 | 65") < female
    assert female < retirement.body.index("עד יוני 1944 | 60")
    assert retirement.metadata is not None
    assert retirement.metadata["captions"][-2:] == ["גיל הפרישה לגבר", "גיל הפרישה לאישה"]

    # The one comparison table OpenLaw prints for itself is still not law.
    rate_schedule = provisions[f"{ITO}/section-121"]
    assert rate_schedule.body is not None
    assert "75,720" not in rate_schedule.body

    # A repealed limb of a live section keeps its marker instead of leaving a bare
    # enumerator behind. §5's five deleted limbs used to collapse into
    # "(1) (2) (3) (4) (א) (ב) שר האוצר…".
    exemptions = provisions[f"{ITO}/section-5"]
    assert exemptions.body is not None
    assert exemptions.body.startswith("(1) (נמחק).\n(2) (נמחק).\n(3) (נמחק).\n(4) (א) (נמחקה).")
    assert exemptions.metadata is not None
    # The section itself is in force; only its limbs are not.
    assert "operative" not in exemptions.metadata

    # A whole section that IS repealed still becomes its own status line.
    repealed = provisions[f"{ITO}/section-11a"]
    assert repealed.body == "(בוטל)."
    assert repealed.metadata is not None
    assert repealed.metadata["operative"] is False
    assert repealed.metadata["status_marker"] == "בוטל"

    # Two competing versions of NII §348 are told apart by their own labels.
    minimum_income = provisions[f"{NII}/section-348"]
    assert minimum_income.body is not None
    assert "(הנוסח הקבוע):" in minimum_income.body

    # OpenLaw's indexed-amount gloss is still not law, in the shipped rows.
    development = provisions[f"{ITO}/section-11"]
    assert development.body is not None
    assert "נקוב לשנת" not in development.body
    assert development.metadata is not None
    assert any(
        "נקוב לשנת" in note for note in (development.metadata.get("editorial_notes") or [])
    )


def test_checked_in_pilot_keeps_time_qualified_substitutions() -> None:
    """The committed rows for every note that states legal effect for a window.

    Three shapes, none of which sits in a table or ends with a colon, and all three of
    which change what the row conveys for the pilot year: a sign headed by nothing but
    its applicability window, an inline rate substitution, and an instruction to read
    one wording in place of another.
    """
    provisions = {
        record.citation_path: record
        for record in load_provisions(
            REPO_ROOT
            / "data"
            / "corpus"
            / "provisions"
            / "il"
            / "statute"
            / f"{IL_PILOT_VERSION}.jsonl"
        )
    }

    # The wartime unemployment sign applies only inside the window that heads it.
    wartime = provisions[f"{NII}/chapter-7/sign-9"]
    assert wartime.body is not None
    assert wartime.body.endswith("\n(הוראת שעה מיום 31.3.2026 עד יום 31.3.2027):")
    assert wartime.metadata is not None
    assert wartime.metadata["statutory_notes"] == ["(הוראת שעה מיום 31.3.2026 עד יום 31.3.2027):"]
    assert "editorial_notes" not in wartime.metadata

    # NII §340א: household-worker contributions. 6.25%/1%/2% are the permanent rates;
    # 7.85%/1.8%/3.6% are what is payable in 2025 and 2026.
    household = provisions[f"{NII}/section-340a"]
    assert household.body is not None
    assert "בשיעור של 6.25% (בשנים 2025–2026: 7.85%) מהשכר" in household.body
    assert "בפסקה (1), 1% (בשנים 2025–2026: 1.8%) מהשכר" in household.body
    assert "יהיו 2% (בשנים 2025–2026: 3.6%) מהשכר" in household.body
    assert household.metadata is not None
    assert household.metadata["statutory_notes"] == [
        "(בשנים 2025–2026: 7.85%)",
        "(בשנים 2025–2026: 1.8%)",
        "(בשנים 2025–2026: 3.6%)",
    ]

    # NII §340: work-injury and maternity contributions for trainees.
    trainees = provisions[f"{NII}/section-340"]
    assert trainees.body is not None
    assert "בשיעור 0.4% (בשנים 2025–2026: 0.53%) ממחצית השכר הממוצע" in trainees.body
    assert "בשיעור 0.1% (בשנים 2025–2026: 0.13%) ממחצית השכר הממוצע" in trainees.body
    assert trainees.metadata is not None
    assert trainees.metadata["statutory_notes"] == [
        "(בשנים 2025–2026: 0.53%)",
        "(בשנים 2025–2026: 0.13%)",
    ]

    # ITO §14: the ten-year residence test is read as five years for a 2007-2009 cohort.
    veteran_returnee = provisions[f"{ITO}/section-14"]
    assert veteran_returnee.body is not None
    assert (
        "תושב חוץ במשך עשר שנים רצופות לפחות (לגבי מי שהיה לתושב ישראל בשנות המס "
        "2007–2009, יקראו כאילו נאמר ”חמש שנים רצופות“ במקום ”עשר שנים רצופות“)."
        in veteran_returnee.body
    )

    # ITO §35: the new-immigrant credit runs 54 months, or 42 for a pre-2022 immigrant.
    immigrant_credit = provisions[f"{ITO}/section-35"]
    assert immigrant_credit.body is not None
    assert (
        "בתקופת 54 החודשים האמורים (עבור מי שעלה לפני שנת 2022: ארבעים ושנים החדשים "
        "האמורים)" in immigrant_credit.body
    )
    assert "במנין 54 החודשים (עבור מי שעלה לפני שנת 2022: 42 החדשים)" in immigrant_credit.body
    assert (
        "תחילת תקופת 54 החודשים (עבור מי שעלה לפני שנת 2022: תקופת 42 החדשים)"
        in immigrant_credit.body
    )


def test_checked_in_pilot_still_excludes_the_projects_value_glosses() -> None:
    """The negative control for the substitution rule, on the shipped rows.

    A gloss can carry the same ``(qualifier: value)`` shape as a substitution — the
    average wage OpenLaw supplies for a definition does — but it states a figure the
    statute leaves to indexation rather than wording the statute replaces, and the
    citation scheme takes those only from official publications under ``il/policies/``.
    """
    provisions = {
        record.citation_path: record
        for record in load_provisions(
            REPO_ROOT
            / "data"
            / "corpus"
            / "provisions"
            / "il"
            / "statute"
            / f"{IL_PILOT_VERSION}.jsonl"
        )
    }

    for citation_path, gloss in (
        (f"{ITO}/section-9a", "(לעניין הגדרה זו, השכר הממוצע בשנת 2025: 12,536 ש״ח)."),
        (f"{ITO}/section-47", "(השכר הממוצע במשק (חודשי): בשנת 2023, 11,870 ש״ח;"),
        (f"{ITO}/section-121", "(הסכומים מתואמים לשנים 2026–2027)"),
    ):
        record = provisions[citation_path]
        assert record.body is not None
        assert gloss not in record.body
        assert record.metadata is not None
        assert any(
            note.startswith(gloss) for note in (record.metadata.get("editorial_notes") or [])
        ), citation_path


def test_checked_in_pilot_artifacts_match_a_fresh_extraction(tmp_path: Path) -> None:
    committed = load_provisions(
        REPO_ROOT / "data" / "corpus" / "provisions" / "il" / "statute" / f"{IL_PILOT_VERSION}.jsonl"
    )
    report = extract_israel_openlaw(
        CorpusArtifactStore(tmp_path / "corpus"),
        version=IL_PILOT_VERSION,
        manifest_path=IL_PILOT_MANIFEST,
        source_dir=IL_PILOT_SOURCE_DIR,
    )
    assert load_provisions(report.provisions_path) == committed
