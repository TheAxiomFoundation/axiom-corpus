import json

import pytest

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.belgium_eli import (
    discover_belgian_moniteur_sources,
    extract_belgian_eli,
    parse_belgian_eli_source,
)

SAMPLE_BRUSSELS_LISTING_HTML = """\
<html>
  <body>
    <tr>
      <td align="left" width="80%">
        <font>
          25 AVRIL 2019. - Ordonnance réglant l'octroi des prestations familiales
          <br><br>
        </font>
      </td>
      <td align="center">
        <a href="http://www.ejustice.just.fgov.be/eli/ordonnance/2019/04/25/2019012118/moniteur">Moniteur</a>
        <br><br>
        <a href="http://www.ejustice.just.fgov.be/eli/ordonnance/2019/04/25/2019012118/justel">Justel</a>
      </td>
    </tr>
  </body>
</html>
"""

SAMPLE_BRUSSELS_JUSTEL_ARTICLES_HTML = """\
<html>
  <body>
    <p class="list-item--title">
      25 AVRIL 2019. - Ordonnance réglant l'octroi des prestations familiales
    </p>
    <div id="list-title-3" class="box plain-text">
      <h2 id="text">Texte</h2>
      <A NAME='Art.1er'></A>Article <A HREF='#Art.2'> 1er</A>.
      La présente ordonnance règle une matière visée à l'article 135 de la Constitution.<BR><BR>
      <A NAME='Art.2' HREF='#Art.1er'>Art.</A> <A HREF='#Art.3'> 2</A>.
      Les droits aux prestations familiales en région bilingue de Bruxelles-Capitale sont fixés par la présente ordonnance.<BR><BR>
      <A NAME='Art.7' HREF='#Art.6'>Art.</A> <A HREF='#Art.8'> 7</A>.
      Les allocations familiales de base s'élèvent à 150 euros.<BR>
    </div>
  </body>
</html>
"""

SAMPLE_FEDERAL_LISTING_HTML = """\
<html>
  <body>
    <tr>
      <td align="left" width="80%">
        03 JUILLET 1969. - Loi créant le Code de la taxe sur la valeur ajoutée
      </td>
      <td>
        <a href="http://www.ejustice.just.fgov.be/eli/loi/1969/07/03/1969070305/moniteur">Moniteur</a>
      </td>
    </tr>
    <tr><td colspan=3><hr></td></tr>
    <tr>
      <td align="left" width="80%">
        28 NOVEMBRE 1969. - Arrêté royal pris en exécution de la loi du 27 juin 1969
      </td>
      <td>
        <a href="http://www.ejustice.just.fgov.be/eli/arrete/1969/11/28/1969112813/moniteur">Moniteur</a>
      </td>
    </tr>
  </body>
</html>
"""

SAMPLE_MONITEUR_SUMMARY_EDITION_1_HTML = """\
<html>
  <body>
    <div class="editions">
      <span class="button__small active">1</span>
      <a href="summary.pl?language=fr&sum_date=2026-06-01&s_editie=2&view_numac=">2</a>
    </div>
    <div id="list-title-0">
      <h2 class="list-title">Lois, décrets, ordonnances et règlements</h2>
      <div class="list-item">
        <p class="list-item--subtitle">Service public fédéral Finances</p>
        <a href="article.pl?language=fr&sum_date=2026-06-01&lg_txt=f&caller=sum&s_editie=1&2026003831=1&numac_search=2026003831&view_numac=" class="list-item--title">
          25 mai 2026. - Arrêté royal déterminant le modèle de formulaire de déclaration en matière d'impôt national complémentaire, p. 29503.
        </a>
      </div>
    </div>
    <div id="list-title-1">
      <h2 class="list-title">Autres arrêtés</h2>
      <div class="list-item">
        <p class="list-item--subtitle">Région de Bruxelles-Capitale</p>
        <a href="article.pl?language=fr&sum_date=2026-06-01&lg_txt=f&caller=sum&s_editie=1&2026003900=2&numac_search=2026003900&view_numac=" class="list-item--title">
          21 mai 2026. - Arrêté du Gouvernement de la Région de Bruxelles-Capitale portant indexation, p. 29577.
        </a>
      </div>
      <div class="list-item">
        <a href="article.pl?language=fr&sum_date=2026-06-01&s_editie=1&2026003980=3&numac_search=2026003980&view_numac=" class="list-item--title">
          Ordre judiciaire, p. 29578.
        </a>
      </div>
    </div>
  </body>
</html>
"""

SAMPLE_MONITEUR_SUMMARY_EDITION_2_HTML = """\
<html>
  <body>
    <div class="editions">
      <a href="summary.pl?language=fr&sum_date=2026-06-01&s_editie=1&view_numac=">1</a>
      <span class="button__small active">2</span>
    </div>
    <div id="list-title-0">
      <h2 class="list-title">Lois, décrets, ordonnances et règlements</h2>
      <div class="list-item">
        <p class="list-item--subtitle">Service public fédéral Chancellerie du Premier Ministre</p>
        <a href="article.pl?language=fr&sum_date=2026-06-01&lg_txt=f&caller=sum&s_editie=2&2026003986=1&numac_search=2026003986&view_numac=" class="list-item--title">
          30 mai 2026. - Loi-programme, p. 29687.
        </a>
      </div>
    </div>
  </body>
</html>
"""

SAMPLE_MONITEUR_ARTICLE_HTML = """\
<html>
  <body>
    <div class="page__wrapper page__wrapper--top">
      <div class="page__section page__section--top">
        <span class="tag">2026003986</span>
        <h1 class="page__title">
          <span>Service public fédéral Chancellerie du Premier Ministre</span>
        </h1>
        <p class="intro-text">30 MAI 2026. - Loi-programme (1)</p>
      </div>
    </div>
    <main class="page__inner page__inner--content article-text">
      <p>
        PHILIPPE, Roi des Belges,<BR>
        Article 1<sup>er</sup>. La présente loi règle une matière visée à l'article 74 de la Constitution.<BR><BR>
        Art. 2. Dans l'article 162, 2°, du Code des droits et taxes divers, le nombre "5" est remplacé par le nombre "10".<BR><BR>
      </p>
    </main>
    <a href="https://www.ejustice.just.fgov.be/eli/loi/2026/05/30/2026003986/moniteur">https://www.ejustice.just.fgov.be/eli/loi/2026/05/30/2026003986/moniteur</a>
    <a href="https://www.ejustice.just.fgov.be/eli/loi/2026/05/30/2026003986/justel">JUSTEL - Législation consolidée</a>
  </body>
</html>
"""

SAMPLE_MONITEUR_ARTICLE_BODY_HTML = """\
<html>
  <body>
    <span class="tag">2018201006</span>
    <h1 class="page__title"><span>Service public de Wallonie</span></h1>
    <p class="intro-text">
      8 FEVRIER 2018. - Décret relatif à la gestion et au paiement des prestations familiales (1)
    </p>
    <main class="page__inner page__inner--content article-text" role="main">
      <p>
        Le Parlement wallon a adopté et Nous, Gouvernement wallon, sanctionnons ce qui suit :<BR>
        Article 1<sup>er</sup>. Le présent décret règle une matière visée à l'article 128 de la Constitution.<BR><BR>
        Art. 2. Pour l'application du présent décret, l'on entend par prestations familiales les avantages visés au Titre III.<BR><BR>
      </p>
    </main>
    <a id="link-text" class="links-link" href="https://www.ejustice.just.fgov.be/eli/decret/2018/02/08/2018201006/moniteur">
      https://www.ejustice.just.fgov.be/eli/decret/2018/02/08/2018201006/moniteur
    </a>
    <a class="links-link" href="https://www.ejustice.just.fgov.be/eli/decret/2018/02/08/2018201006/justel">
      JUSTEL - Législation consolidée
    </a>
  </body>
</html>
"""


def _read_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def test_extract_belgian_eli_requires_source(tmp_path):
    with pytest.raises(ValueError, match="at least one source HTML path"):
        extract_belgian_eli(
            CorpusArtifactStore(tmp_path / "data" / "corpus"),
            version="2026-06-30-be",
        )


def test_extract_belgian_eli_listing_writes_brussels_document_artifact(tmp_path):
    base = tmp_path / "data" / "corpus"
    source_html = tmp_path / "brussels-family-benefits.html"
    source_html.write_text(SAMPLE_BRUSSELS_LISTING_HTML)

    report = extract_belgian_eli(
        CorpusArtifactStore(base),
        version="2026-06-30-be",
        source_htmls=(source_html,),
        source_as_of="2026-06-30",
        expression_date="2026-01-01",
    )

    assert report.source_count == 1
    assert report.provisions_written == 1
    class_report = report.class_reports[0]
    assert class_report.jurisdiction == "be-bru"
    assert class_report.document_class == "statute"
    assert class_report.coverage.complete

    provisions_path = base / "provisions/be-bru/statute/2026-06-30-be.jsonl"
    [record] = _read_jsonl(provisions_path)
    assert record["citation_path"] == "be-bru/statute/ordonnance/2019/04/25/2019012118/document"
    assert (
        record["source_url"]
        == "https://www.ejustice.just.fgov.be/eli/ordonnance/2019/04/25/2019012118/moniteur"
    )
    assert (
        record["metadata"]["justel_url"]
        == "https://www.ejustice.just.fgov.be/eli/ordonnance/2019/04/25/2019012118/justel"
    )
    assert record["identifiers"]["ejustice.just.fgov.be:numac"] == "2019012118"
    assert (
        record["identifiers"]["ejustice.just.fgov.be:source_authority"]
        == "official_original_publication"
    )


def test_extract_belgian_eli_justel_article_page_writes_article_records(tmp_path):
    base = tmp_path / "data" / "corpus"
    source_dir = tmp_path / "eli"
    source_html = source_dir / "eli/ordonnance/2019/04/25/2019012118/justel.html"
    source_html.parent.mkdir(parents=True)
    source_html.write_text(SAMPLE_BRUSSELS_JUSTEL_ARTICLES_HTML)

    report = extract_belgian_eli(
        CorpusArtifactStore(base),
        version="2026-06-30-be",
        source_dir=source_dir,
    )

    assert report.source_count == 3
    assert report.provisions_written == 3
    class_report = report.class_reports[0]
    assert class_report.jurisdiction == "be-bru"
    assert class_report.document_class == "statute"
    assert class_report.coverage.complete

    records = _read_jsonl(base / "provisions/be-bru/statute/2026-06-30-be.jsonl")
    assert [record["citation_path"] for record in records] == [
        "be-bru/statute/ordonnance/2019/04/25/2019012118/article/1er",
        "be-bru/statute/ordonnance/2019/04/25/2019012118/article/2",
        "be-bru/statute/ordonnance/2019/04/25/2019012118/article/7",
    ]
    assert records[-1]["source_url"].endswith("/eli/ordonnance/2019/04/25/2019012118/justel#Art.7")
    assert (
        records[-1]["metadata"]["legal_authority_url"]
        == "https://www.ejustice.just.fgov.be/eli/ordonnance/2019/04/25/2019012118/moniteur"
    )
    assert records[-1]["metadata"]["source_authority"] == "non_authentic_consolidated_locator"
    assert "150 euros" in records[-1]["body"]
    assert records[-1]["source_path"] == (
        "sources/be-bru/statute/2026-06-30-be/eli/ordonnance/2019/04/25/2019012118/justel.html"
    )


def test_extract_belgian_eli_groups_federal_statute_and_regulation(tmp_path):
    base = tmp_path / "data" / "corpus"
    source_html = tmp_path / "federal-tax-and-social-security.html"
    source_html.write_text(SAMPLE_FEDERAL_LISTING_HTML)

    report = extract_belgian_eli(
        CorpusArtifactStore(base),
        version="2026-06-30-be",
        source_htmls=(source_html,),
    )

    assert {(r.jurisdiction, r.document_class) for r in report.class_reports} == {
        ("be", "regulation"),
        ("be", "statute"),
    }
    statute_records = _read_jsonl(base / "provisions/be/statute/2026-06-30-be.jsonl")
    regulation_records = _read_jsonl(base / "provisions/be/regulation/2026-06-30-be.jsonl")
    assert statute_records[0]["citation_path"] == ("be/statute/loi/1969/07/03/1969070305/document")
    assert regulation_records[0]["citation_path"] == (
        "be/regulation/arrete/1969/11/28/1969112813/document"
    )


def test_discover_belgian_moniteur_sources_follows_editions_and_policy_sections(
    monkeypatch,
):
    import axiom_corpus.corpus.belgium_eli as belgium_eli

    class FakeResponse:
        def __init__(self, url, text):
            self.url = url
            self.text = text

        def raise_for_status(self):
            return None

    class FakeSession:
        def __init__(self):
            self.headers = {}

        def get(self, url, timeout):
            assert timeout == 5
            if "s_editie=2" in url:
                return FakeResponse(url, SAMPLE_MONITEUR_SUMMARY_EDITION_2_HTML)
            return FakeResponse(url, SAMPLE_MONITEUR_SUMMARY_EDITION_1_HTML)

    monkeypatch.setattr(belgium_eli.requests, "Session", FakeSession)

    report = discover_belgian_moniteur_sources(
        start_date="2026-06-01",
        end_date="2026-06-01",
        request_timeout=5,
    )

    assert report.summary_pages_fetched == 2
    assert [source.numac for source in report.sources] == [
        "2026003831",
        "2026003900",
        "2026003986",
    ]
    assert [source.document_class for source in report.sources] == [
        "regulation",
        "regulation",
        "statute",
    ]
    assert report.sources[1].jurisdiction == "be-bru"
    assert report.sources[2].source_url == (
        "https://www.ejustice.just.fgov.be/cgi/article.pl?language=fr&sum_date="
        "2026-06-01&lg_txt=f&caller=sum&s_editie=2&2026003986=1&numac_search="
        "2026003986&view_numac="
    )


def test_extract_belgian_eli_moniteur_article_page_writes_article_records(tmp_path):
    base = tmp_path / "data" / "corpus"
    source_html = tmp_path / "moniteur-article.html"
    source_html.write_text(SAMPLE_MONITEUR_ARTICLE_HTML)

    report = extract_belgian_eli(
        CorpusArtifactStore(base),
        version="2026-06-30-be",
        source_htmls=(source_html,),
    )

    assert report.source_count == 2
    assert report.provisions_written == 2
    records = _read_jsonl(base / "provisions/be/statute/2026-06-30-be.jsonl")
    assert [record["citation_path"] for record in records] == [
        "be/statute/loi/2026/05/30/2026003986/article/1er",
        "be/statute/loi/2026/05/30/2026003986/article/2",
    ]
    assert records[0]["source_url"] == (
        "https://www.ejustice.just.fgov.be/eli/loi/2026/05/30/2026003986/moniteur"
    )
    assert records[0]["metadata"]["source_authority"] == ("official_original_publication")


def test_parse_belgian_eli_moniteur_article_body_url_writes_article_records():
    records = parse_belgian_eli_source(
        SAMPLE_MONITEUR_ARTICLE_BODY_HTML,
        source_name=(
            "https://www.ejustice.just.fgov.be/cgi/article_body.pl?"
            "language=fr&caller=summary&pub_date=2018-03-01&numac=2018201006"
        ),
    )

    assert [record.label for record in records] == ["1er", "2"]
    assert records[0].document.jurisdiction == "be-wal"
    assert records[0].document.document_type == "decret"
    assert records[0].document.moniteur_url == (
        "https://www.ejustice.just.fgov.be/cgi/article_body.pl?"
        "language=fr&caller=summary&pub_date=2018-03-01&numac=2018201006"
    )
    assert records[0].document.justel_url == (
        "https://www.ejustice.just.fgov.be/eli/decret/2018/02/08/2018201006/justel"
    )
    assert records[0].source_authority == "official_original_publication"
