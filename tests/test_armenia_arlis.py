import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from axiom_corpus.corpus.armenia_arlis import (
    ARMENIA_ARLIS_SOURCE_FORMAT,
    ArmeniaARLISManifest,
    ArmeniaARLISSource,
    extract_armenia_arlis,
    parse_armenia_arlis_html,
)
from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.supabase import deterministic_provision_id

REPO_ROOT = Path(__file__).resolve().parents[1]
AM_TAXBEN_CORE_VERSION = "2026-08-29-am-taxben-core"
AM_RULESPEC_SOURCE_PACK_VERSION = "2026-08-30-am-rulespec-source-pack"
AM_TAX_CODE_2024_CONTINUITY_VERSION = "2026-08-30-am-tax-code-2024-continuity"

SAMPLE_ARLIS_HTML = """\
<!doctype html>
<html lang="hy">
  <head><title>ՓՈՐՁՆԱԿԱՆ ՕՐԵՆՔ</title></head>
  <body>
    <div class="act-info__item">
      <div class="act-info__label">Համար</div>
      <div class="act-info__value">ՀՕ-1-Ն</div>
    </div>
    <div class="act-info__item">
      <div class="act-info__label">Տիպ</div>
      <div class="act-info__value">Օրենք</div>
    </div>
    <div class="act-info__item">
      <div class="act-info__label">Ընդունման ամսաթիվ</div>
      <div class="act-info__value">01.01.2026</div>
    </div>
    <div class="act-info__item">
      <div class="act-info__label">Փաստաթղթի տեսակ</div>
      <div class="act-info__value">
        Պաշտոնական Ինկորպորացիա (01.09.2026-մինչ օրս)
      </div>
    </div>
    <a class="act-changes-primary" href="/hy/acts/109017">Primary act</a>
    <div class="act-changes-history__couple current-act">
      <div class="act-changes-history__item">
        <a class="act-link" href="/hy/acts/999999">Amendment</a>
      </div>
      <div class="act-changes-history__item">
        <a class="act-link" href="/hy/acts/230171">Current act</a>
      </div>
      <div class="act-changes-history__couple-compare"
           data-request-url="/hy/acts/230171/compare/230171"></div>
    </div>
    <div id="act_body">
      <div class="act-block__section">
        <p>ՀԱՅԱՍՏԱՆԻ ՀԱՆՐԱՊԵՏՈՒԹՅԱՆ ՕՐԵՆՔԸ</p>
        <p>Մ Ա Ս 1</p>
        <p>ԸՆԴՀԱՆՈՒՐ ՄԱՍ</p>
        <p>Բ Ա Ժ Ի Ն 2</p>
        <p>ՀԱՐԿԵՐ</p>
        <p>Գ Լ ՈՒ Խ 3.1(գլուխը լրաց. 01.09.26 ՀՕ-1-Ն)</p>
        <p>ՍՈՑԻԱԼԱԿԱՆ ԾԱԽՍԵՐ</p>
        <p><strong>
          <table><tr>
            <td>&nbsp;<a href="/acts/files/court"><b>⚖</b></a><strong>Հ<a name="split"></a>ոդված 293․1.</strong></td>
            <td><strong>Սոցիալական<b> ծախսերը</b></strong></td>
          </tr></table>
        </strong></p>
        <p>1. Շահառուն վճարում է 10 տոկոս։</p>
        <p>(293․1-ին հոդվածը լրաց. 01.09.26 ՀՕ-1-Ն)</p>
        <table><tr>
          <td><strong>Հոդված294.</strong></td>
          <td><strong>Հաջորդ դրույթը</strong></td>
        </tr></table>
        <p>1. Պահպանվում են «մեջբերումը», շեշտը՝ և հարցականը՞</p>
        <table><tr><td>&nbsp;Հավելված 1</td></tr></table>
        <p>ՀԱՎԵԼՎԱԾԻ ՎԵՐՆԱԳԻՐԸ</p>
        <p>Հավելվածի դրույթը։</p>
        <table><tr>
          <td>Հայաստանի Հանրապետության Նախագահ</td>
          <td>Ա. Անուն</td>
        </tr></table>
      </div>
    </div>
  </body>
</html>
"""

HISTORICAL_ARLIS_HTML = SAMPLE_ARLIS_HTML.replace(
    "Պաշտոնական Ինկորպորացիա (01.09.2026-մինչ օրս)",
    "Պաշտոնական Ինկորպորացիա (01.01.2024-24.03.2024)",
)

# Verbatim metadata and legal-text excerpts from the official ARLIS pages,
# retrieved 2026-08-30. The reduced DOM keeps only elements the adapter reads.
MAIN_ACT_179204_URL = "https://www.arlis.am/hy/acts/179204"
MAIN_ACT_179204_TITLE = (
    "ՀՀ ԿԱՌԱՎԱՐՈՒԹՅԱՆ ՈՐՈՇՈՒՄԸ ՀԱՐԿԱՅԻՆ ՏԱՐՎԱ ԸՆԹԱՑՔՈՒՄ ՖԻԶԻԿԱԿԱՆ "
    "ԱՆՁԱՆՑ ՍՈՑԻԱԼԱԿԱՆ ԾԱԽՍԵՐԻ ԳՈՒՄԱՐՆԵՐԸ՝ ՀԱՇՎԱՐԿՎԱԾ ԵՎ (ԿԱՄ) "
    "ՎՃԱՐՎԱԾ (ԱՅԴ ԹՎՈՒՄ՝ ՀԱՐԿԱՅԻՆ ԳՈՐԾԱԿԱԼԻ ԿՈՂՄԻՑ) ԵԿԱՄՏԱՅԻՆ "
    "ՀԱՐԿԻ ԳՈՒՄԱՐՆԵՐԻՑ ՓՈԽՀԱՏՈՒՑՄԱՆ (ՎԵՐԱԴԱՐՁՄԱՆ) ԿԱՐԳԸ ՍԱՀՄԱՆԵԼՈՒ ՄԱՍԻՆ"
)
MAIN_ACT_179204_HTML = f"""\
<!doctype html>
<html lang="hy">
  <head><title>{MAIN_ACT_179204_TITLE}</title></head>
  <body>
    <div class="act-info__item">
      <div class="act-info__label">Համար</div>
      <div class="act-info__value">N 956-Ն</div>
    </div>
    <div class="act-info__item">
      <div class="act-info__label">Տիպ</div>
      <div class="act-info__value">Որոշում</div>
    </div>
    <div class="act-info__item">
      <div class="act-info__label">Ընդունող մարմին</div>
      <div class="act-info__value">ՀՀ կառավարություն</div>
    </div>
    <div class="act-info__item">
      <div class="act-info__label">Փաստաթղթի տեսակ</div>
      <div class="act-info__value">Հիմնական ակտ (17.06.2023-15.02.2025)</div>
    </div>
    <div class="act-info__item">
      <div class="act-info__label">Ընդունման ամսաթիվ</div>
      <div class="act-info__value">16.06.2023</div>
    </div>
    <a class="act-changes-primary" href="/hy/acts/179204">Հիմնական ակտ</a>
    <div id="act_body">
      <div class="act-block__section">
        <p>Հիմք ընդունելով Հայաստանի Հանրապետության հարկային օրենսգրքի 158-րդ հոդվածի 3-րդ մասը՝ Հայաստանի Հանրապետության կառավարությունը որոշում է.</p>
        <p>1. Սահմանել հարկային տարվա ընթացքում ֆիզիկական անձանց սոցիալական ծախսերի գումարները՝ հաշվարկված և (կամ) վճարված (այդ թվում՝ հարկային գործակալի կողմից) եկամտային հարկի գումարներից փոխհատուցման (վերադարձման) կարգը՝ համաձայն հավելվածի:</p>
        <table><tr><td>Հայաստանի Հանրապետության<br/>վարչապետ</td><td>Ն. Փաշինյան</td></tr></table>
        <table><tr><td>Հավելված ՀՀ կառավարության 2023 թվականի հունիսի 16-ի N 956-Ն որոշման</td></tr></table>
        <strong>Կ Ա Ր Գ</strong>
        <p>1․ Սույն կարգով կարգավորվում են հարկային տարվա ընթացքում ֆիզիկական անձանց՝ Հայաստանի Հանրապետության հարկային օրենսգրքի (այսուհետ՝ օրենսգիրք) 147.1-ին հոդվածով սահմանված սոցիալական ծախսերը, բայց ոչ ավելի, քան դրանց համար Հայաստանի Հանրապետության կառավարության սահմանած առավելագույն չափերով, եկամտային հարկով հարկման բազայի նկատմամբ օրենսգրքի 150-րդ հոդվածով սահմանված դրույքաչափերով հաշվարկված և (կամ) վճարված (այդ թվում՝ հարկային գործակալի կողմից) եկամտային հարկի գումարներից փոխհատուցման (վերադարձման) հետ կապված հարաբերությունները:</p>
        <table><tr><td>Հայաստանի Հանրապետության վարչապետի աշխատակազմի ղեկավար</td><td>Ա. Հարությունյան</td></tr></table>
      </div>
    </div>
  </body>
</html>
"""

INCORPORATION_162079_URL = "https://www.arlis.am/hy/acts/162079"
INCORPORATION_162079_TITLE = (
    "ՀՀ ԿԱՌԱՎԱՐՈՒԹՅԱՆ ՈՐՈՇՈՒՄԸ ՀԻՓՈԹԵՔԱՅԻՆ ՎԱՐԿԻ ՍՊԱՍԱՐԿՄԱՆ ՀԱՄԱՐ "
    "ՎՃԱՐՎԱԾ ՏՈԿՈՍՆԵՐԻ ԳՈՒՄԱՐՆԵՐԻ ՉԱՓՈՎ ՖԻԶԻԿԱԿԱՆ ԱՆՁԱՆՑ ԿՈՂՄԻՑ "
    "ՎՃԱՐՎԱԾ ԵԿԱՄՏԱՅԻՆ ՀԱՐԿԻ ԳՈՒՄԱՐՆԵՐԻ ՎԵՐԱԴԱՐՁՄԱՆ ԿԱՐԳԸ ՍԱՀՄԱՆԵԼՈՒ ՄԱՍԻՆ"
)
INCORPORATION_162079_HTML = f"""\
<!doctype html>
<html lang="hy">
  <head><title>{INCORPORATION_162079_TITLE}</title></head>
  <body>
    <div class="act-info__item">
      <div class="act-info__label">Համար</div>
      <div class="act-info__value">N 1321-Ն</div>
    </div>
    <div class="act-info__item">
      <div class="act-info__label">Տիպ</div>
      <div class="act-info__value">Որոշում</div>
    </div>
    <div class="act-info__item">
      <div class="act-info__label">Ընդունող մարմին</div>
      <div class="act-info__value">ՀՀ կառավարություն</div>
    </div>
    <div class="act-info__item">
      <div class="act-info__label">Փաստաթղթի տեսակ</div>
      <div class="act-info__value">Պաշտոնական Ինկորպորացիա (16.04.2022-01.08.2024)</div>
    </div>
    <div class="act-info__item">
      <div class="act-info__label">Ընդունման ամսաթիվ</div>
      <div class="act-info__value">05.10.2017</div>
    </div>
    <a class="act-changes-primary" href="/hy/acts/116657">Հիմնական ակտ</a>
    <div class="act-changes-history__couple current-act">
      <div class="act-changes-history__item">
        <a class="act-link" href="/hy/acts/162025">15.04.2022, N 509-Ն</a>
      </div>
      <div class="act-changes-history__item">
        <a class="act-link" href="/hy/acts/162079">05.10.2017, N 1321-Ն</a>
      </div>
      <div class="act-changes-history__couple-compare"
           data-request-url="/hy/acts/162079/compare/162079"></div>
    </div>
    <div id="act_body">
      <div class="act-block__section">
        <p>Հիմք ընդունելով Հայաստանի Հանրապետության հարկային օրենսգրքի 160-րդ հոդվածի 6-րդ մասը և 2021 թվականի նոյեմբերի 17-ի «Հայաստանի Հանրապետության հարկային օրենսգրքում փոփոխություններ և լրացումներ կատարելու մասին» ՀՕ-360-Ն Հայաստանի Հանրապետության օրենքի 5-րդ հոդվածի 3-րդ մասը` Հայաստանի Հանրապետության կառավարությունը որոշում է.</p>
        <table><tr><td>Հավելված ՀՀ կառավարության 2017 թվականի հոկտեմբերի 5-ի N 1321 -Ն որոշման</td></tr></table>
        <strong>Կ Ա Ր Գ</strong>
        <p>1. Սույն կարգով կարգավորվում են, Հայաստանի Հանրապետության հարկային օրենսգրքի 160-րդ հոդվածի համաձայն, Հայաստանի Հանրապետության ռեզիդենտ ֆինանսական կազմակերպությունից ստացված և փաստացի բնակարանի կամ անհատական բնակելի տան ձեռքբերմանը կամ անհատական բնակելի տան կառուցմանն ուղղված հիփոթեքային վարկի (այսուհետ՝ հիփոթեքային վարկ) սպասարկման համար վճարվող տոկոսների (այսուհետ՝ տոկոս) գումարների չափով ֆիզիկական անձանց (բացառությամբ վարձու աշխատող չհամարվող անհատ ձեռնարկատիրոջ և նոտարի) օրենքով սահմանված կարգով վճարված (այդ թվում` հարկային գործակալի միջոցով գանձված) եկամտային հարկը վերադարձնելու հետ կապված հարաբերությունները:</p>
      </div>
    </div>
  </body>
</html>
"""

NUMBERED_APPENDICES_66111_URL = "https://www.arlis.am/hy/acts/66111"
NUMBERED_APPENDICES_66111_TITLE = (
    "ՀՀ ԿԱՌԱՎԱՐՈՒԹՅԱՆ ՈՐՈՇՈՒՄԸ ԻՆՏԵՐՆԵՏՈՎ ՀՐԱՊԱՐԱԿԱՅԻՆ ԾԱՆՈՒՑՄԱՆ "
    "ԵՆԹԱԿԱ ՀԱՅՏԱՐԱՐՈՒԹՅԱՆ ԸՆԴՈՒՆՄԱՆ, ԿԱՅՔԸ ՎԱՐՈՂ ԱՆՁԻՆ ՓՈԽԱՆՑՄԱՆ, "
    "ԿԱՅՔՈՒՄ ՀԱՅՏԱՐԱՐՈՒԹՅՈՒՆՆԵՐԻ ՏԵՂԱԴՐՄԱՆ ԵՎ ԱՐԽԻՎԱՑՄԱՆ ԺԱՄԿԵՏՆԵՐԻ "
    "ՍԱՀՄԱՆՄԱՆ ԿԱՐԳԸ ԵՎ ՀԱՅՏԱՐԱՐՈՒԹՅԱՆ ՏԵՔՍՏԸ ՆԵՐԿԱՅԱՑՆԵԼՈՒ "
    "ԷԼԵԿՏՐՈՆԱՅԻՆ ՁԵՎԱՉԱՓԸ ՀԱՍՏԱՏԵԼՈՒ ՄԱՍԻՆ"
)
NUMBERED_APPENDICES_66111_HTML = f"""\
<!doctype html>
<html lang="hy">
  <head><title>{NUMBERED_APPENDICES_66111_TITLE}</title></head>
  <body>
    <div class="act-info__item">
      <div class="act-info__label">Համար</div>
      <div class="act-info__value">N 174-Ն</div>
    </div>
    <div class="act-info__item">
      <div class="act-info__label">Տիպ</div>
      <div class="act-info__value">Որոշում</div>
    </div>
    <div class="act-info__item">
      <div class="act-info__label">Ընդունող մարմին</div>
      <div class="act-info__value">ՀՀ կառավարություն</div>
    </div>
    <div class="act-info__item">
      <div class="act-info__label">Փաստաթղթի տեսակ</div>
      <div class="act-info__value">Հիմնական ակտ (19.03.2011-15.09.2012)</div>
    </div>
    <div class="act-info__item">
      <div class="act-info__label">Ընդունման ամսաթիվ</div>
      <div class="act-info__value">17.02.2011</div>
    </div>
    <a class="act-changes-primary" href="/hy/acts/66111">Հիմնական ակտ</a>
    <div id="act_body">
      <div class="act-block__section">
        <p>Հիմք ընդունելով «Ինտերնետով հրապարակային ծանուցման մասին» Հայաստանի Հանրապետության օրենքի 4-րդ, 5-րդ և 6-րդ հոդվածները` Հայաստանի Հանրապետության կառավարությունը որոշում է.</p>
        <p>1. Հաստատել`</p>
        <p>1) ինտերնետով հրապարակային ծանուցման ենթակա հայտարարության ընդունման, կայքը վարող անձին փոխանցման, կայքում հայտարարությունների տեղադրման և արխիվացման ժամկետների սահմանման կարգը՝ համաձայն N 1 հավելվածի.</p>
        <table><tr><td>Հավելված N 1 ՀՀ կառավարության 2011 թվականի փետրվարի 17-ի N 174-Ն որոշման</td></tr></table>
        <p>Կ Ա Ր Գ</p>
        <p>ԻՆՏԵՐՆԵՏՈՎ ՀՐԱՊԱՐԱԿԱՅԻՆ ԾԱՆՈՒՑՄԱՆ ԵՆԹԱԿԱ ՀԱՅՏԱՐԱՐՈՒԹՅԱՆ ԸՆԴՈՒՆՄԱՆ, ԿԱՅՔԸ ՎԱՐՈՂ ԱՆՁԻՆ ՓՈԽԱՆՑՄԱՆ, ԿԱՅՔՈՒՄ ՀԱՅՏԱՐԱՐՈՒԹՅՈՒՆՆԵՐԻ ՏԵՂԱԴՐՄԱՆ ԵՎ ԱՐԽԻՎԱՑՄԱՆ ԺԱՄԿԵՏՆԵՐԻ ՍԱՀՄԱՆՄԱՆ</p>
        <table><tr><td>Հայաստանի Հանրապետության կառավարության աշխատակազմի ղեկավար</td><td>Դ. Սարգսյան</td></tr></table>
        <p>Հավելված N 2 ՀՀ կառավարության 2011 թվականի փետրվարի 17-ի N 174-Ն որոշման</p>
        <p>Է Լ Ե Կ Տ Ր Ո Ն Ա Յ Ի Ն Ձ ԵՎ Ա Չ Ա Փ</p>
        <p>ԻՆՏԵՐՆԵՏՈՎ ՀՐԱՊԱՐԱԿԱՅԻՆ ԾԱՆՈՒՑՄԱՆ ԵՆԹԱԿԱ ՀԱՅՏԱՐԱՐՈՒԹՅԱՆ</p>
      </div>
    </div>
  </body>
</html>
"""


def _source_mapping(*, sha256: str, expected_article_count: int = 2) -> dict[str, object]:
    return {
        "source_id": "sample-statute",
        "jurisdiction": "am",
        "document_class": "statute",
        "act_id": "230171",
        "base_act_id": "109017",
        "official_number": "ՀՕ-1-Ն",
        "adopted": "2026-01-01",
        "title": "ՓՈՐՁՆԱԿԱՆ ՕՐԵՆՔ",
        "source_url": "https://www.arlis.am/hy/acts/230171/latest",
        "source_file": "sample.html",
        "sha256": sha256,
        "source_as_of": "2026-08-29",
        "expression_date": "2026-09-01",
        "language": "hy",
        "expected_article_count": expected_article_count,
    }


def _sample_source() -> ArmeniaARLISSource:
    content = SAMPLE_ARLIS_HTML.encode()
    return ArmeniaARLISSource.from_mapping(
        _source_mapping(sha256=hashlib.sha256(content).hexdigest())
    )


def _main_act_regulation_mapping(*, sha256: str) -> dict[str, object]:
    return {
        "source_id": "government-decision-956-n",
        "jurisdiction": "am",
        "document_class": "regulation",
        "act_id": "179204",
        "official_number": "N 956-Ն",
        "adopted": "2023-06-16",
        "title": MAIN_ACT_179204_TITLE,
        "source_url": MAIN_ACT_179204_URL,
        "source_file": "act-179204.html",
        "sha256": sha256,
        "source_as_of": "2026-08-30",
        "expression_date": "2023-06-17",
        "expression_end_date": "2025-02-15",
        "language": "hy",
        "expected_article_count": 0,
        "expected_appendix_count": 1,
    }


def _incorporation_regulation_mapping(*, sha256: str) -> dict[str, object]:
    return {
        "source_id": "government-decision-1321-n-2022",
        "jurisdiction": "am",
        "document_class": "regulation",
        "act_id": "162079",
        "base_act_id": "116657",
        "official_number": "N 1321-Ն",
        "adopted": "2017-10-05",
        "title": INCORPORATION_162079_TITLE,
        "source_url": INCORPORATION_162079_URL,
        "source_file": "act-162079.html",
        "sha256": sha256,
        "source_as_of": "2026-08-30",
        "expression_date": "2022-04-16",
        "expression_end_date": "2024-08-01",
        "language": "hy",
        "expected_article_count": 0,
        "expected_appendix_count": 1,
    }


def _numbered_appendices_regulation_mapping(*, sha256: str) -> dict[str, object]:
    return {
        "source_id": "government-decision-174-n",
        "jurisdiction": "am",
        "document_class": "regulation",
        "act_id": "66111",
        "official_number": "N 174-Ն",
        "adopted": "2011-02-17",
        "title": NUMBERED_APPENDICES_66111_TITLE,
        "source_url": NUMBERED_APPENDICES_66111_URL,
        "source_file": "act-66111.html",
        "sha256": sha256,
        "source_as_of": "2026-08-30",
        "expression_date": "2011-03-19",
        "expression_end_date": "2012-09-15",
        "language": "hy",
        "expected_article_count": 0,
        "expected_appendix_count": 2,
    }


def _write_manifest(path: Path, source: dict[str, object]) -> None:
    path.write_text(
        json.dumps({"documents": [source]}, ensure_ascii=False),
        encoding="utf-8",
    )


def test_campaign_manifest_pins_all_six_corrected_article_counts_and_dates():
    manifest = ArmeniaARLISManifest.load(REPO_ROOT / "manifests" / "am-taxben-core-arlis.yaml")

    counts = {source.source_id: source.expected_article_count for source in manifest.documents}
    assert counts == {
        "tax-code": 474,
        "funded-pensions": 81,
        "universal-health-insurance": 46,
        "servicemen-compensation": 32,
        "state-benefits": 44,
        "state-pensions": 58,
    }
    assert sum(counts.values()) == 735
    assert {source.source_id: source.expression_date for source in manifest.documents} == {
        "tax-code": "2026-09-01",
        "funded-pensions": "2026-05-18",
        "universal-health-insurance": "2026-05-08",
        "servicemen-compensation": "2026-09-01",
        "state-benefits": "2026-09-01",
        "state-pensions": "2026-09-01",
    }
    assert {source.source_as_of for source in manifest.documents} == {"2026-08-29"}
    assert {source.language for source in manifest.documents} == {"hy"}


def test_parse_armenia_arlis_preserves_split_headers_hierarchy_and_punctuation():
    provisions = parse_armenia_arlis_html(
        SAMPLE_ARLIS_HTML,
        source=_sample_source(),
    )

    assert [item.kind for item in provisions] == [
        "document",
        "part",
        "section",
        "chapter",
        "article",
        "article",
        "appendix",
    ]
    document, part, section, chapter, article, next_article, appendix = provisions
    assert document.citation_path == "am/statute/act-230171"
    assert part.citation_path == "am/statute/act-230171/part-1"
    assert section.citation_path == "am/statute/act-230171/part-1/section-2"
    assert chapter.citation_path.endswith("/part-1/section-2/chapter-3.1")
    assert chapter.heading == "ՍՈՑԻԱԼԱԿԱՆ ԾԱԽՍԵՐ"
    assert chapter.body is not None
    assert chapter.body.startswith("(գլուխը լրաց. 01.09.26 ՀՕ-1-Ն)")

    assert article.citation_path == "am/statute/act-230171/article-293.1"
    assert article.parent_citation_path == chapter.citation_path
    assert article.heading == "Սոցիալական ծախսերը"
    assert article.body == (
        "1. Շահառուն վճարում է 10 տոկոս։\n(293․1-ին հոդվածը լրաց. 01.09.26 ՀՕ-1-Ն)"
    )
    assert article.metadata["raw_article_marker"].endswith("Հոդված 293․1.")
    assert article.metadata["court_decision_urls"] == ["https://www.arlis.am/acts/files/court"]
    assert next_article.label == "294"
    assert next_article.body == "1. Պահպանվում են «մեջբերումը», շեշտը՝ և հարցականը՞"
    assert appendix.citation_path == "am/statute/act-230171/appendix-1"
    assert appendix.heading == "ՀԱՎԵԼՎԱԾԻ ՎԵՐՆԱԳԻՐԸ"
    assert document.body is not None
    assert "Հայաստանի Հանրապետության Նախագահ" in document.body


def test_extract_armenia_arlis_writes_versioned_complete_artifacts(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    content = SAMPLE_ARLIS_HTML.encode()
    (source_dir / "sample.html").write_bytes(content)
    source_mapping = _source_mapping(sha256=hashlib.sha256(content).hexdigest())
    manifest_path = tmp_path / "manifest.yaml"
    _write_manifest(manifest_path, source_mapping)
    base = tmp_path / "corpus"

    report = extract_armenia_arlis(
        CorpusArtifactStore(base),
        version=AM_TAXBEN_CORE_VERSION,
        manifest_path=manifest_path,
        source_dir=source_dir,
    )

    assert report.jurisdiction == "am"
    assert report.document_class == "statute"
    assert report.document_count == 1
    assert report.article_count == 2
    assert report.structural_count == 4
    assert report.provisions_written == 7
    assert report.coverage.complete
    assert len(report.source_paths) == 1
    assert report.source_paths[0].read_bytes() == content

    records = load_provisions(report.provisions_path)
    inventory = load_source_inventory(report.inventory_path)
    article = next(record for record in records if record.kind == "article")
    assert article.id == deterministic_provision_id(
        article.citation_path,
        AM_TAXBEN_CORE_VERSION,
    )
    assert article.parent_citation_path is not None
    assert article.parent_id == deterministic_provision_id(
        article.parent_citation_path,
        AM_TAXBEN_CORE_VERSION,
    )
    assert article.source_as_of == "2026-08-29"
    assert article.expression_date == "2026-09-01"
    assert article.language == "hy"
    assert article.source_path is not None
    assert article.source_path.endswith(f"/am/statute/{AM_TAXBEN_CORE_VERSION}/arlis/sample.html")
    assert inventory[0].source_format == ARMENIA_ARLIS_SOURCE_FORMAT
    assert inventory[0].sha256 == hashlib.sha256(content).hexdigest()


def test_extract_main_act_regulation_writes_regulation_scope(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    content = MAIN_ACT_179204_HTML.encode()
    (source_dir / "act-179204.html").write_bytes(content)
    source_mapping = _main_act_regulation_mapping(sha256=hashlib.sha256(content).hexdigest())
    manifest_path = tmp_path / "manifest.yaml"
    _write_manifest(manifest_path, source_mapping)

    report = extract_armenia_arlis(
        CorpusArtifactStore(tmp_path / "corpus"),
        version="2026-08-30-am-regulation-adapter-test",
        manifest_path=manifest_path,
        source_dir=source_dir,
    )

    assert report.document_class == "regulation"
    assert report.article_count == 0
    assert report.structural_count == 1
    assert report.provisions_written == 2
    assert "/am/regulation/" in str(report.inventory_path)
    assert "/am/regulation/" in str(report.provisions_path)
    assert report.source_paths[0].read_bytes() == content

    records = load_provisions(report.provisions_path)
    records_by_path = {record.citation_path: record for record in records}
    document = records_by_path["am/regulation/act-179204"]
    appendix = records_by_path["am/regulation/act-179204/appendix-1"]
    assert {record.document_class for record in records} == {"regulation"}
    assert document.body is not None
    assert "Հայաստանի Հանրապետության կառավարությունը որոշում է" in document.body
    assert "վարչապետ | Ն. Փաշինյան" in document.body
    assert "վարչապետի աշխատակազմի ղեկավար | Ա. Հարությունյան" in document.body
    assert appendix.body is not None
    assert "147.1-ին հոդվածով սահմանված սոցիալական ծախսերը" in appendix.body
    assert "վարչապետ" not in appendix.body
    assert "document_class" not in appendix.metadata
    assert appendix.metadata["expression_end_date"] == "2025-02-15"
    assert appendix.metadata["expected_appendix_count"] == 1
    assert appendix.identifiers["arlis.am:expression_end_exclusive"] == "2025-02-15"
    assert appendix.source_path is not None
    assert appendix.source_path.endswith(
        "/am/regulation/2026-08-30-am-regulation-adapter-test/arlis/act-179204.html"
    )


def test_parse_official_incorporation_regulation_uses_regulation_citations():
    content = INCORPORATION_162079_HTML.encode()
    source = ArmeniaARLISSource.from_mapping(
        _incorporation_regulation_mapping(sha256=hashlib.sha256(content).hexdigest())
    )

    provisions = parse_armenia_arlis_html(content, source=source)

    assert [item.citation_path for item in provisions] == [
        "am/regulation/act-162079",
        "am/regulation/act-162079/appendix-1",
    ]
    assert provisions[1].body is not None
    assert "եկամտային հարկը վերադարձնելու" in provisions[1].body


def test_parse_numbered_official_appendices_preserves_two_appendix_scopes():
    content = NUMBERED_APPENDICES_66111_HTML.encode()
    source = ArmeniaARLISSource.from_mapping(
        _numbered_appendices_regulation_mapping(sha256=hashlib.sha256(content).hexdigest())
    )

    provisions = parse_armenia_arlis_html(content, source=source)

    assert [item.citation_path for item in provisions] == [
        "am/regulation/act-66111",
        "am/regulation/act-66111/appendix-1",
        "am/regulation/act-66111/appendix-2",
    ]
    document, appendix_1, appendix_2 = provisions
    assert document.body is not None
    assert "կառավարության աշխատակազմի ղեկավար | Դ. Սարգսյան" in document.body
    assert appendix_1.body is not None
    assert "Կ Ա Ր Գ" in appendix_1.body
    assert "աշխատակազմի ղեկավար" not in appendix_1.body
    assert appendix_2.body is not None
    assert "Է Լ Ե Կ Տ Ր Ո Ն Ա Յ Ի Ն Ձ ԵՎ Ա Չ Ա Փ" in appendix_2.body


def test_manifest_defaults_to_statute_for_existing_callers():
    mapping = _source_mapping(sha256="0" * 64)
    mapping.pop("document_class")

    source = ArmeniaARLISSource.from_mapping(mapping)

    assert source.document_class == "statute"
    assert source.document_citation_path == "am/statute/act-230171"


def test_manifest_rejects_unsupported_and_mixed_document_classes(tmp_path):
    statute = _source_mapping(sha256="0" * 64)
    with pytest.raises(ValueError, match="must be statute or regulation"):
        ArmeniaARLISSource.from_mapping({**statute, "document_class": "guidance"})

    regulation = _main_act_regulation_mapping(sha256="1" * 64)
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text(
        json.dumps({"documents": [statute, regulation]}, ensure_ascii=False),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="exactly one document_class"):
        ArmeniaARLISManifest.load(manifest_path)


@pytest.mark.parametrize(
    ("html", "mapping"),
    [
        (
            MAIN_ACT_179204_HTML,
            {
                **_main_act_regulation_mapping(
                    sha256=hashlib.sha256(MAIN_ACT_179204_HTML.encode()).hexdigest()
                ),
                "document_class": "statute",
            },
        ),
        (
            SAMPLE_ARLIS_HTML,
            {
                **_source_mapping(sha256=hashlib.sha256(SAMPLE_ARLIS_HTML.encode()).hexdigest()),
                "document_class": "regulation",
                "expected_appendix_count": 1,
            },
        ),
    ],
)
def test_parse_rejects_manifest_class_that_disagrees_with_arlis_type(html, mapping):
    source = ArmeniaARLISSource.from_mapping(mapping)

    with pytest.raises(ValueError, match="document_class mismatch"):
        parse_armenia_arlis_html(html, source=source)


def test_manifest_allows_zero_but_rejects_negative_expected_article_count():
    mapping = _main_act_regulation_mapping(sha256="0" * 64)
    assert ArmeniaARLISSource.from_mapping(mapping).expected_article_count == 0
    with pytest.raises(ValueError, match="non-negative expected_article_count"):
        ArmeniaARLISSource.from_mapping({**mapping, "expected_article_count": -1})


def test_regulation_manifest_requires_non_negative_expected_appendix_count():
    mapping = _main_act_regulation_mapping(sha256="0" * 64)
    without_count = {
        key: value for key, value in mapping.items() if key != "expected_appendix_count"
    }
    with pytest.raises(ValueError, match="requires a non-negative expected_appendix_count"):
        ArmeniaARLISSource.from_mapping(without_count)
    with pytest.raises(ValueError, match="requires a non-negative expected_appendix_count"):
        ArmeniaARLISSource.from_mapping({**mapping, "expected_appendix_count": -1})


@pytest.mark.parametrize(
    ("html", "error"),
    [
        (
            MAIN_ACT_179204_HTML.replace("ՀՀ կառավարություն</div>", "ՀՀ կենտրոնական բանկ</div>"),
            "enactment-body mismatch",
        ),
        (
            MAIN_ACT_179204_HTML.replace(
                """    <div class="act-info__item">
      <div class="act-info__label">Ընդունող մարմին</div>
      <div class="act-info__value">ՀՀ կառավարություն</div>
    </div>
""",
                "",
            ),
            "missing act-info field",
        ),
    ],
)
def test_parse_regulation_requires_armenian_government_enactment_body(html, error):
    source = ArmeniaARLISSource.from_mapping(
        _main_act_regulation_mapping(sha256=hashlib.sha256(html.encode()).hexdigest())
    )

    with pytest.raises(ValueError, match=error):
        parse_armenia_arlis_html(html, source=source)


@pytest.mark.parametrize(
    ("html", "error"),
    [
        (
            MAIN_ACT_179204_HTML.replace("Հիմնական ակտ (", "Փոփոխող ակտ ("),
            "unrecognized validity value",
        ),
        (
            MAIN_ACT_179204_HTML.replace(
                'href="/hy/acts/179204"',
                'href="/hy/acts/179767"',
            ),
            "act_id mismatch for main act",
        ),
        (
            MAIN_ACT_179204_HTML.replace(
                '<a class="act-changes-primary" href="/hy/acts/179204">Հիմնական ակտ</a>',
                "",
            ),
            "exactly one primary-act link",
        ),
        (
            MAIN_ACT_179204_HTML.replace(
                '<a class="act-changes-primary" href="/hy/acts/179204">Հիմնական ակտ</a>',
                '<a class="act-changes-primary" href="/hy/acts/179204">Հիմնական ակտ</a>'
                '<a class="act-changes-primary" href="/hy/acts/179204">Հիմնական ակտ</a>',
            ),
            "exactly one primary-act link",
        ),
        (
            MAIN_ACT_179204_HTML.replace(
                '<div id="act_body">',
                '<div class="act-changes-history__couple current-act"></div><div id="act_body">',
            ),
            "must not contain a current-act history row",
        ),
    ],
)
def test_parse_main_act_regulation_rejects_unbound_metadata(html, error):
    source = ArmeniaARLISSource.from_mapping(
        _main_act_regulation_mapping(sha256=hashlib.sha256(html.encode()).hexdigest())
    )

    with pytest.raises(ValueError, match=error):
        parse_armenia_arlis_html(html, source=source)


def test_parse_main_act_rejects_manifest_base_act_id():
    source = ArmeniaARLISSource.from_mapping(
        {
            **_main_act_regulation_mapping(
                sha256=hashlib.sha256(MAIN_ACT_179204_HTML.encode()).hexdigest()
            ),
            "base_act_id": "179204",
        }
    )

    with pytest.raises(ValueError, match="must not declare base_act_id"):
        parse_armenia_arlis_html(MAIN_ACT_179204_HTML, source=source)


def test_parse_incorporation_rejects_missing_primary_link():
    html = INCORPORATION_162079_HTML.replace(
        '<a class="act-changes-primary" href="/hy/acts/116657">Հիմնական ակտ</a>',
        "",
    )
    source = ArmeniaARLISSource.from_mapping(
        _incorporation_regulation_mapping(sha256=hashlib.sha256(html.encode()).hexdigest())
    )

    with pytest.raises(ValueError, match="exactly one primary-act link"):
        parse_armenia_arlis_html(html, source=source)


def test_parse_regulation_incorporation_requires_base_act_id():
    mapping = _incorporation_regulation_mapping(
        sha256=hashlib.sha256(INCORPORATION_162079_HTML.encode()).hexdigest()
    )
    mapping.pop("base_act_id")
    source = ArmeniaARLISSource.from_mapping(mapping)

    with pytest.raises(ValueError, match="regulation incorporation.*requires base_act_id"):
        parse_armenia_arlis_html(INCORPORATION_162079_HTML, source=source)


def test_parse_rejects_unrecognized_standalone_appendix_marker():
    html = MAIN_ACT_179204_HTML.replace(
        "Հավելված ՀՀ կառավարության 2023 թվականի հունիսի 16-ի N 956-Ն որոշման",
        "Հավելված անհայտ ձևաչափ",
    )
    source = ArmeniaARLISSource.from_mapping(
        _main_act_regulation_mapping(sha256=hashlib.sha256(html.encode()).hexdigest())
    )

    with pytest.raises(ValueError, match="unrecognized appendix marker"):
        parse_armenia_arlis_html(html, source=source)


def test_signature_shape_does_not_hoist_substantive_role_table():
    html = MAIN_ACT_179204_HTML.replace(
        "Հայաստանի Հանրապետության վարչապետի աշխատակազմի ղեկավար</td>",
        "Հայաստանի Հանրապետության վարչապետի աշխատակազմի ղեկավարի պարտականությունները</td>",
    )
    source = ArmeniaARLISSource.from_mapping(
        _main_act_regulation_mapping(sha256=hashlib.sha256(html.encode()).hexdigest())
    )

    document, appendix = parse_armenia_arlis_html(html, source=source)

    assert document.body is not None
    assert "ղեկավարի պարտականությունները" not in document.body
    assert appendix.body is not None
    assert "ղեկավարի պարտականությունները | Ա. Հարությունյան" in appendix.body


def test_checked_in_six_document_pack_parses_to_exact_counts(tmp_path):
    source_dir = (
        REPO_ROOT
        / "data"
        / "corpus"
        / "sources"
        / "am"
        / "statute"
        / AM_TAXBEN_CORE_VERSION
        / "arlis"
    )

    report = extract_armenia_arlis(
        CorpusArtifactStore(tmp_path / "corpus"),
        version=AM_TAXBEN_CORE_VERSION,
        manifest_path=REPO_ROOT / "manifests" / "am-taxben-core-arlis.yaml",
        source_dir=source_dir,
    )

    assert {
        item.source_id: (item.article_count, item.structural_count)
        for item in report.document_reports
    } == {
        "tax-code": (474, 114),
        "funded-pensions": (81, 15),
        "universal-health-insurance": (46, 9),
        "servicemen-compensation": (32, 5),
        "state-benefits": (44, 14),
        "state-pensions": (58, 10),
    }
    assert report.article_count == 735
    assert report.structural_count == 167
    assert report.provisions_written == 908
    assert report.coverage.complete
    records = load_provisions(report.provisions_path)
    assert {record.expression_date for record in records} == {
        "2026-05-08",
        "2026-05-18",
        "2026-09-01",
    }
    assert {record.source_as_of for record in records} == {"2026-08-29"}
    records_by_path = {record.citation_path: record for record in records}
    assert len(records_by_path) == len(records)
    children_by_parent = {}
    for record in records:
        if record.parent_citation_path is None:
            continue
        parent = records_by_path[record.parent_citation_path]
        assert record.level == parent.level + 1
        children_by_parent.setdefault(record.parent_citation_path, []).append(record)
    for siblings in children_by_parent.values():
        ordinals = [record.ordinal for record in siblings]
        assert None not in ordinals
        assert ordinals == sorted(ordinals)
        assert len(ordinals) == len(set(ordinals))

    tax_document_path = "am/statute/act-230171"
    assert records_by_path[f"{tax_document_path}/article-1"].parent_citation_path == (
        f"{tax_document_path}/part-1/section-1/chapter-1"
    )
    assert records_by_path[f"{tax_document_path}/article-458"].parent_citation_path == (
        f"{tax_document_path}/part-4/section-22/chapter-82"
    )
    tax_appendices = [
        record
        for record in records
        if record.citation_path.startswith(f"{tax_document_path}/appendix-")
    ]
    assert len(tax_appendices) == 3
    assert {record.parent_citation_path for record in tax_appendices} == {tax_document_path}
    for label, heading_start, body_start in (
        (
            "78",
            "Ավելացված արժեքի հարկի գումարի վճարումը",
            "1. ԱԱՀ վճարողները",
        ),
        ("147.1", "Սոցիալական ծախսերը", "1. Սոցիալական ծախսեր են համարվում"),
    ):
        matches = [
            record
            for record in records
            if record.citation_path == f"am/statute/act-230171/article-{label}"
        ]
        assert len(matches) == 1
        assert matches[0].heading == heading_start
        assert matches[0].body is not None
        assert matches[0].body.startswith(body_start)
        assert matches[0].parent_citation_path is not None
        assert matches[0].parent_citation_path.startswith("am/statute/act-230171/")
    assert all("\xa0" not in (record.heading or "") for record in records)
    assert all("\xa0" not in (record.body or "") for record in records)
    servicemen_article_1 = next(
        record for record in records if record.citation_path == "am/statute/act-230046/article-1"
    )
    assert servicemen_article_1.heading == "Օրենքի կարգավորման առարկան"


def test_rulespec_pack_is_a_bounded_2024_evidence_slice():
    manifest = ArmeniaARLISManifest.load(
        REPO_ROOT / "manifests" / "am-rulespec-source-pack-arlis.yaml"
    )
    assert all(source.base_act_id is not None for source in manifest.documents)
    assert [
        (source.source_id, source.act_id, source.expression_date, source.expression_end_date)
        for source in manifest.documents
    ] == [
        ("tax-code-2024-q1", "187950", "2024-01-01", "2024-03-24"),
        ("tax-code-2024-year-end", "201213", "2024-12-23", "2025-01-01"),
        ("funded-pensions-2024-q1", "183145", "2023-10-13", "2024-03-27"),
        ("funded-pensions-2024-q2", "191184", "2024-03-27", "2024-07-09"),
        ("funded-pensions-2024-h2", "194995", "2024-07-09", "2025-01-01"),
        ("minimum-wage-2024", "172160", "2022-12-23", None),
    ]


def test_tax_code_2024_continuity_manifest_closes_the_endpoint_gap():
    continuity = ArmeniaARLISManifest.load(
        REPO_ROOT / "manifests" / "am-tax-code-2024-continuity-arlis.yaml"
    )
    assert [
        (
            source.act_id,
            source.expression_date,
            source.expression_end_date,
            source.expected_article_count,
        )
        for source in continuity.documents
    ] == [
        ("190955", "2024-03-24", "2024-04-05", 462),
        ("191399", "2024-04-05", "2024-04-07", 464),
        ("191449", "2024-04-07", "2024-05-04", 464),
        ("192465", "2024-05-04", "2024-06-01", 464),
        ("193378", "2024-06-01", "2024-07-18", 464),
        ("195238", "2024-07-18", "2024-09-01", 464),
        ("196879", "2024-09-01", "2024-10-21", 465),
        ("198522", "2024-10-21", "2024-10-24", 469),
        ("198723", "2024-10-24", "2024-11-14", 469),
        ("199704", "2024-11-14", "2024-11-18", 469),
        ("199763", "2024-11-18", "2024-11-29", 470),
        ("200343", "2024-11-29", "2024-12-23", 470),
    ]

    endpoint_pack = ArmeniaARLISManifest.load(
        REPO_ROOT / "manifests" / "am-rulespec-source-pack-arlis.yaml"
    )
    intervals = sorted(
        (source.expression_date, source.expression_end_date)
        for source in (*endpoint_pack.documents, *continuity.documents)
        if source.base_act_id == "109017"
    )
    assert intervals[0] == ("2024-01-01", "2024-03-24")
    assert intervals[-1] == ("2024-12-23", "2025-01-01")
    assert all(
        left[1] == right[0]
        for left, right in zip(intervals[:-1], intervals[1:], strict=True)
    )


def test_checked_in_tax_code_2024_continuity_sources_match_manifest():
    manifest = ArmeniaARLISManifest.load(
        REPO_ROOT / "manifests" / "am-tax-code-2024-continuity-arlis.yaml"
    )
    source_dir = (
        REPO_ROOT
        / "data"
        / "corpus"
        / "sources"
        / "am"
        / "statute"
        / AM_TAX_CODE_2024_CONTINUITY_VERSION
        / "arlis"
    )

    for source in manifest.documents:
        content = (source_dir / source.source_file).read_bytes()
        assert hashlib.sha256(content).hexdigest() == source.sha256
        provisions = parse_armenia_arlis_html(content, source=source)
        assert sum(item.kind == "article" for item in provisions) == (
            source.expected_article_count
        )


def test_checked_in_rulespec_pack_binds_2024_evidence_expressions(tmp_path):
    source_dir = (
        REPO_ROOT
        / "data"
        / "corpus"
        / "sources"
        / "am"
        / "statute"
        / AM_RULESPEC_SOURCE_PACK_VERSION
        / "arlis"
    )

    report = extract_armenia_arlis(
        CorpusArtifactStore(tmp_path / "corpus"),
        version=AM_RULESPEC_SOURCE_PACK_VERSION,
        manifest_path=REPO_ROOT / "manifests" / "am-rulespec-source-pack-arlis.yaml",
        source_dir=source_dir,
    )

    assert {
        item.source_id: (item.article_count, item.structural_count)
        for item in report.document_reports
    } == {
        "tax-code-2024-q1": (461, 113),
        "tax-code-2024-year-end": (470, 114),
        "funded-pensions-2024-q1": (81, 15),
        "funded-pensions-2024-q2": (81, 15),
        "funded-pensions-2024-h2": (81, 15),
        "minimum-wage-2024": (7, 0),
    }
    assert report.document_count == 6
    assert report.article_count == 1181
    assert report.structural_count == 272
    assert report.provisions_written == 1459
    assert report.coverage.complete

    records = load_provisions(report.provisions_path)
    records_by_path = {record.citation_path: record for record in records}
    assert len(records_by_path) == 1459
    assert records_by_path["am/statute/act-187950/article-150"].expression_date == ("2024-01-01")
    assert (
        records_by_path["am/statute/act-187950/article-150"].metadata["expression_end_date"]
        == "2024-03-24"
    )
    assert (
        records_by_path["am/statute/act-187950/article-150"].identifiers[
            "arlis.am:expression_end_exclusive"
        ]
        == "2024-03-24"
    )
    assert (
        records_by_path["am/statute/act-187950/article-150"].identifiers["arlis.am:base_act_id"]
        == "109017"
    )
    assert (
        records_by_path["am/statute/act-194995/article-6"].metadata["expression_end_date"]
        == "2025-01-01"
    )
    minimum_wage = records_by_path["am/statute/act-172160/article-1"]
    assert minimum_wage.heading is None
    assert minimum_wage.body is not None
    assert "75000 դրամ" in minimum_wage.body


def test_extract_armenia_arlis_rejects_hash_before_writing_artifacts(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "sample.html").write_text(SAMPLE_ARLIS_HTML, encoding="utf-8")
    manifest_path = tmp_path / "manifest.yaml"
    _write_manifest(manifest_path, _source_mapping(sha256="0" * 64))
    base = tmp_path / "corpus"

    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        extract_armenia_arlis(
            CorpusArtifactStore(base),
            version=AM_TAXBEN_CORE_VERSION,
            manifest_path=manifest_path,
            source_dir=source_dir,
        )

    assert not base.exists()


def test_extract_armenia_arlis_rejects_article_count_before_writing_artifacts(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    content = SAMPLE_ARLIS_HTML.encode()
    (source_dir / "sample.html").write_bytes(content)
    manifest_path = tmp_path / "manifest.yaml"
    _write_manifest(
        manifest_path,
        _source_mapping(
            sha256=hashlib.sha256(content).hexdigest(),
            expected_article_count=3,
        ),
    )
    base = tmp_path / "corpus"

    with pytest.raises(ValueError, match="article count mismatch"):
        extract_armenia_arlis(
            CorpusArtifactStore(base),
            version=AM_TAXBEN_CORE_VERSION,
            manifest_path=manifest_path,
            source_dir=source_dir,
        )

    assert not base.exists()


def test_extract_armenia_arlis_rejects_zero_expected_count_when_articles_exist(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    content = SAMPLE_ARLIS_HTML.encode()
    (source_dir / "sample.html").write_bytes(content)
    manifest_path = tmp_path / "manifest.yaml"
    _write_manifest(
        manifest_path,
        _source_mapping(
            sha256=hashlib.sha256(content).hexdigest(),
            expected_article_count=0,
        ),
    )
    base = tmp_path / "corpus"

    with pytest.raises(ValueError, match="expected 0, got 2"):
        extract_armenia_arlis(
            CorpusArtifactStore(base),
            version=AM_TAXBEN_CORE_VERSION,
            manifest_path=manifest_path,
            source_dir=source_dir,
        )

    assert not base.exists()


def test_extract_regulation_rejects_appendix_count_before_writing_artifacts(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    content = MAIN_ACT_179204_HTML.encode()
    (source_dir / "act-179204.html").write_bytes(content)
    mapping = {
        **_main_act_regulation_mapping(sha256=hashlib.sha256(content).hexdigest()),
        "expected_appendix_count": 2,
    }
    manifest_path = tmp_path / "manifest.yaml"
    _write_manifest(manifest_path, mapping)
    base = tmp_path / "corpus"

    with pytest.raises(ValueError, match="appendix count mismatch.*expected 2, got 1"):
        extract_armenia_arlis(
            CorpusArtifactStore(base),
            version="2026-08-30-am-regulation-adapter-test",
            manifest_path=manifest_path,
            source_dir=source_dir,
        )

    assert not base.exists()


def test_parse_zero_article_source_rejects_empty_legal_body():
    prefix, remainder = MAIN_ACT_179204_HTML.split(
        '<div class="act-block__section">',
        maxsplit=1,
    )
    _body, suffix = remainder.split("</div>", maxsplit=1)
    html = f'{prefix}<div class="act-block__section"></div>{suffix}'
    source = ArmeniaARLISSource.from_mapping(
        _main_act_regulation_mapping(sha256=hashlib.sha256(html.encode()).hexdigest())
    )

    with pytest.raises(ValueError, match="no extractable legal content"):
        parse_armenia_arlis_html(html, source=source)


def test_parse_armenia_arlis_rejects_unbound_article_marker():
    malformed = SAMPLE_ARLIS_HTML.replace(
        "<p>1. Շահառուն վճարում է 10 տոկոս։</p>",
        "<p><span>Հոդված 999.</span> Չկապված վերնագիր</p>",
    )

    with pytest.raises(ValueError, match="unrecognized article marker"):
        parse_armenia_arlis_html(malformed, source=_sample_source())


def test_parse_armenia_arlis_does_not_treat_appendix_reference_as_header():
    reference = SAMPLE_ARLIS_HTML.replace(
        "        <p>1. Շահառուն վճարում է 10 տոկոս։</p>",
        "        <p>Հավելված 1-ում նշված կարգը կիրառվում է։</p>\n"
        "        <p>1. Շահառուն վճարում է 10 տոկոս։</p>",
    )
    source = ArmeniaARLISSource.from_mapping(
        {
            **_source_mapping(sha256=hashlib.sha256(reference.encode()).hexdigest()),
        }
    )

    provisions = parse_armenia_arlis_html(reference, source=source)

    appendices = [item for item in provisions if item.kind == "appendix"]
    assert [item.citation_path for item in appendices] == ["am/statute/act-230171/appendix-1"]
    article = next(item for item in provisions if item.citation_path.endswith("/article-293.1"))
    assert article.body is not None
    assert "Հավելված 1-ում նշված կարգը կիրառվում է։" in article.body


def test_parse_armenia_arlis_preserves_inline_article_body_without_heading():
    inline = SAMPLE_ARLIS_HTML.replace(
        """<table><tr>
          <td><strong>Հոդված294.</strong></td>
          <td><strong>Հաջորդ դրույթը</strong></td>
        </tr></table>
        <p>1. Պահպանվում են «մեջբերումը», շեշտը՝ և հարցականը՞</p>""",
        """<p><strong>Հոդված 294.</strong> Պահպանվում են «մեջբերումը», շեշտը՝ և հարցականը՞</p>""",
    )

    provisions = parse_armenia_arlis_html(inline, source=_sample_source())

    article = next(item for item in provisions if item.citation_path.endswith("article-294"))
    assert article.heading is None
    assert article.body == "Պահպանվում են «մեջբերումը», շեշտը՝ և հարցականը՞"


def test_parse_armenia_arlis_rejects_expression_date_drift():
    source = ArmeniaARLISSource.from_mapping(
        {
            **_source_mapping(sha256=hashlib.sha256(SAMPLE_ARLIS_HTML.encode()).hexdigest()),
            "expression_date": "2026-08-29",
        }
    )

    with pytest.raises(ValueError, match="expression period mismatch"):
        parse_armenia_arlis_html(SAMPLE_ARLIS_HTML, source=source)


def test_parse_armenia_arlis_accepts_finite_historical_expression_period():
    source = ArmeniaARLISSource.from_mapping(
        {
            **_source_mapping(sha256=hashlib.sha256(HISTORICAL_ARLIS_HTML.encode()).hexdigest()),
            "source_url": "https://www.arlis.am/hy/acts/230171",
            "expression_date": "2024-01-01",
            "expression_end_date": "2024-03-24",
        }
    )

    provisions = parse_armenia_arlis_html(HISTORICAL_ARLIS_HTML, source=source)

    assert provisions[0].metadata == {"article_count": 2, "structural_count": 4}
    assert source.expression_end_date == "2024-03-24"


def test_parse_armenia_arlis_rejects_historical_expression_end_drift():
    source = ArmeniaARLISSource.from_mapping(
        {
            **_source_mapping(sha256=hashlib.sha256(HISTORICAL_ARLIS_HTML.encode()).hexdigest()),
            "source_url": "https://www.arlis.am/hy/acts/230171",
            "expression_date": "2024-01-01",
            "expression_end_date": "2024-03-25",
        }
    )

    with pytest.raises(ValueError, match="expression period mismatch"):
        parse_armenia_arlis_html(HISTORICAL_ARLIS_HTML, source=source)


@pytest.mark.parametrize(
    ("changes", "error"),
    [
        ({"title": "ԱՅԼ ՕՐԵՆՔ"}, "title mismatch"),
        ({"official_number": "ՀՕ-999-Ն"}, "official_number mismatch"),
        ({"adopted": "2026-01-02"}, "adopted mismatch"),
        ({"base_act_id": "999999"}, "base_act_id mismatch"),
        (
            {
                "act_id": "999999",
                "source_url": "https://www.arlis.am/hy/acts/999999/latest",
            },
            "act_id mismatch",
        ),
    ],
)
def test_parse_armenia_arlis_rejects_cross_labeled_source_identity(changes, error):
    source = replace(_sample_source(), **changes)

    with pytest.raises(ValueError, match=error):
        parse_armenia_arlis_html(SAMPLE_ARLIS_HTML, source=source)


def test_extract_armenia_arlis_rejects_cross_label_before_writing_artifacts(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    content = SAMPLE_ARLIS_HTML.encode()
    (source_dir / "sample.html").write_bytes(content)
    manifest_path = tmp_path / "manifest.yaml"
    source_mapping = _source_mapping(sha256=hashlib.sha256(content).hexdigest())
    source_mapping["official_number"] = "ՀՕ-999-Ն"
    _write_manifest(manifest_path, source_mapping)
    base = tmp_path / "corpus"

    with pytest.raises(ValueError, match="official_number mismatch"):
        extract_armenia_arlis(
            CorpusArtifactStore(base),
            version=AM_TAXBEN_CORE_VERSION,
            manifest_path=manifest_path,
            source_dir=source_dir,
        )

    assert not base.exists()


def test_extract_armenia_arlis_rejects_cross_labeled_act_id_before_writing_artifacts(
    tmp_path,
):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    content = SAMPLE_ARLIS_HTML.encode()
    (source_dir / "sample.html").write_bytes(content)
    manifest_path = tmp_path / "manifest.yaml"
    source_mapping = _source_mapping(sha256=hashlib.sha256(content).hexdigest())
    source_mapping["act_id"] = "999999"
    source_mapping["source_url"] = "https://www.arlis.am/hy/acts/999999/latest"
    _write_manifest(manifest_path, source_mapping)
    base = tmp_path / "corpus"

    with pytest.raises(ValueError, match="act_id mismatch"):
        extract_armenia_arlis(
            CorpusArtifactStore(base),
            version=AM_TAXBEN_CORE_VERSION,
            manifest_path=manifest_path,
            source_dir=source_dir,
        )

    assert not base.exists()


def test_parse_armenia_arlis_rejects_duplicate_article_label_across_chapters():
    duplicate = SAMPLE_ARLIS_HTML.replace(
        "        <table><tr><td>&nbsp;Հավելված 1</td></tr></table>",
        """\
        <p>Գ Լ ՈՒ Խ 4</p>
        <p>ԱՅԼ ԳԼՈՒԽ</p>
        <table><tr>
          <td><strong>Հոդված 293․1.</strong></td>
          <td><strong>Կրկնվող դրույթ</strong></td>
        </tr></table>
        <p>1. Կրկնվող հոդվածի տեքստը։</p>
        <table><tr><td>&nbsp;Հավելված 1</td></tr></table>""",
    )

    with pytest.raises(ValueError, match=r"duplicate article labels: 293\.1"):
        parse_armenia_arlis_html(duplicate, source=_sample_source())


def test_manifest_requires_quoted_dates_and_armenian_language():
    valid = _source_mapping(sha256="0" * 64)
    with pytest.raises(ValueError, match="explicitly quoted ISO date"):
        ArmeniaARLISSource.from_mapping({**valid, "source_as_of": object()})
    with pytest.raises(ValueError, match="language must be hy"):
        ArmeniaARLISSource.from_mapping({**valid, "language": "en"})
    with pytest.raises(ValueError, match="explicitly quoted ISO date"):
        ArmeniaARLISSource.from_mapping({**valid, "expression_end_date": 20240324})
    with pytest.raises(ValueError, match="must follow expression_date"):
        ArmeniaARLISSource.from_mapping({**valid, "expression_end_date": valid["expression_date"]})


@pytest.mark.parametrize(
    "source_url",
    [
        "https://www.arlis.am/hy/acts/230171/latest/",
        "https://arlis.am/hy/acts/230171/latest",
        "https://www.arlis.am/hy/acts/230171/latest?download=1",
    ],
)
def test_manifest_rejects_noncanonical_arlis_urls(source_url):
    valid = _source_mapping(sha256="0" * 64)

    with pytest.raises(ValueError, match="official Armenian act URL"):
        ArmeniaARLISSource.from_mapping({**valid, "source_url": source_url})


def test_manifest_rejects_latest_url_for_finite_historical_expression():
    valid = _source_mapping(sha256="0" * 64)

    with pytest.raises(ValueError, match="finite ARLIS historical expressions"):
        ArmeniaARLISSource.from_mapping(
            {
                **valid,
                "expression_date": "2024-01-01",
                "expression_end_date": "2024-03-24",
            }
        )
