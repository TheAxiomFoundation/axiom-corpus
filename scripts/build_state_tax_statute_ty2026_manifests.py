"""Build the 2026-09-14 state income-tax statute and TY2026 indexed-amount manifests and
update ``manifests/tax-agent-queue.yaml`` (run note
``docs/ingest-runs/2026-09-14-state-tax-statute-ty2026.md``).

Two families:

* ``statute`` (``--family statute``): the whole income-tax chapter for the partial-chapter
  states of the closure check that have no chapter-capable source-first adapter. The
  legislature's own index is read live and one official-documents entry is written per
  section: Kentucky (KRS chapter 141, one PDF per section from the LRC statute service),
  Virginia (Code of Virginia title 58.1 chapter 3, one HTML page per section from LIS),
  New York (Tax Law article 22, one HTML page per section from the Senate OpenLegislation
  site) and California (RTC parts 10 and 10.2, the section list the California section
  extractor is run with). The adapter-driven states are in
  ``manifests/state-income-tax-chapters-2026-09-14.yaml`` and need no generator.
* ``amounts`` (``--family amounts``): the revenue department's TY2026 indexed-amount
  publication per state (or the latest published year where the department has posted no
  2026 product), one static table per jurisdiction confirmed by the agent on 2026-09-13
  from the publisher's own index (recorded as ``index_url``).

``--family queue`` rewrites the queue rows for both families from the manifests and the
coverage artifacts on disk (``AXIOM_CORPUS_BASE``); it never invents counts.

    uv run python scripts/build_state_tax_statute_ty2026_manifests.py --family statute
    uv run python scripts/build_state_tax_statute_ty2026_manifests.py --family amounts
    uv run python scripts/build_state_tax_statute_ty2026_manifests.py --family queue
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
MANIFESTS = ROOT / "manifests"
CORPUS_BASE = Path(os.environ.get("AXIOM_CORPUS_BASE", str(ROOT / "data" / "corpus")))
SOURCE_AS_OF = "2026-09-14"
STATUTE_VERSION = "2026-09-14-income-tax-chapter"
AMOUNTS_VERSION = "2026-09-14-ty2026-indexed-amounts"
USER_AGENT = (
    "Axiom/1.0 (Legal Archive; contact@axiom-foundation.org) "
    "https://github.com/TheAxiomFoundation/axiom-corpus"
)
SINGLE_BLOCK = {"segmentation": "single_block"}
# nysenate.gov answers HTTP 403 to the plain corpus client and serves the page to a
# Chrome TLS fingerprint (probed 2026-09-13); the extractor's curl_cffi path honours this.
NY_REQUEST = {
    "browser_user_agent": True,
    "browser_impersonation": "chrome120",
    "browser_impersonation_direct": True,
}

KY_CHAPTER_INDEX = "https://apps.legislature.ky.gov/law/statutes/chapter.aspx?id=37674"
KY_STATUTE_URL = "https://apps.legislature.ky.gov/law/statutes/statute.aspx?id={id}"
VA_CHAPTER_INDEX = "https://law.lis.virginia.gov/vacode/title58.1/chapter3/"
VA_SECTION_URL = "https://law.lis.virginia.gov/vacode/title58.1/chapter3/section{section}/"
NY_ARTICLE_INDEX = "https://www.nysenate.gov/legislation/laws/TAX/A22"
NY_PART_URL = "https://www.nysenate.gov/legislation/laws/TAX/A22P{part}"
NY_SECTION_URL = "https://www.nysenate.gov/legislation/laws/TAX/{section}"
CA_TOC_URL = (
    "https://leginfo.legislature.ca.gov/faces/codes_displayexpandedbranch.xhtml"
    "?tocCode=RTC&division=2.&title=&part={part}&chapter=&article="
)
CA_TEXT_URL = "https://leginfo.legislature.ca.gov/faces/codes_displayText.xhtml?"
CA_PARTS = ("10.", "10.2.")


def _session() -> requests.Session:
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    return session


def _get(session: requests.Session, url: str, *, timeout: int = 90) -> str:
    response = session.get(url, timeout=timeout)
    response.raise_for_status()
    return response.text


def _impersonated_get(url: str) -> str:
    from curl_cffi import requests as curl_requests

    response = curl_requests.get(url, impersonate="chrome120", timeout=90)
    if response.status_code != 200:
        raise RuntimeError(f"{url}: HTTP {response.status_code}")
    return response.text


def _write_manifest(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, width=120))


# --------------------------------------------------------------------------- statute


def _statute_document(
    *,
    jurisdiction: str,
    source_id: str,
    title: str,
    source_url: str,
    source_format: str,
    citation_path: str,
    extraction: dict[str, Any],
    authority: str,
    index_url: str,
    metadata: dict[str, Any],
    request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "source_id": source_id,
        "jurisdiction": jurisdiction,
        "document_class": "statute",
        "title": title,
        "source_url": source_url,
        "source_format": source_format,
        "source_as_of": SOURCE_AS_OF,
        "expression_date": SOURCE_AS_OF,
        "citation_path": citation_path,
        "extraction": extraction,
        "metadata": {
            "primary_source": True,
            "source_authority": authority,
            "document_subtype": "codified_statute_section",
            "program": "individual_income_tax",
            "source_status": f"current_official_codified_text_as_of_{SOURCE_AS_OF}",
            "source_family": "state-income-tax-chapter-2026-09-14",
            "index_url": index_url,
            "discovered_via": f"manual-review:tax-agent-queue; index {index_url}",
            **metadata,
        },
    }
    if request:
        doc["request"] = dict(request)
    return doc


def build_kentucky(session: requests.Session) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """KRS chapter 141: one PDF per section from the LRC statute service."""
    html = _get(session, KY_CHAPTER_INDEX)
    rows: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for match in re.finditer(
        r'href="statute\.aspx\?id=(?P<id>\d+)"[^>]*>\s*\.(?P<suffix>[0-9]+)\s+(?P<heading>[^<]*)<',
        html,
    ):
        statute_id = match.group("id")
        if statute_id in seen:
            continue
        seen.add(statute_id)
        section = f"141.{match.group('suffix')}"
        heading = re.sub(r"\s+", " ", match.group("heading")).strip()
        rows.append((statute_id, section, heading))
    if len(rows) < 150:
        raise RuntimeError(f"KRS chapter 141 index parsed only {len(rows)} sections")
    documents = [
        _statute_document(
            jurisdiction="us-ky",
            source_id=f"us-ky-krs-{section.replace('.', '-')}",
            title=f"KRS {section} {heading}".strip(),
            source_url=KY_STATUTE_URL.format(id=statute_id),
            source_format="pdf",
            citation_path=f"us-ky/statute/krs/{section}",
            extraction=SINGLE_BLOCK,
            authority="Kentucky Legislative Research Commission",
            index_url=KY_CHAPTER_INDEX,
            metadata={
                "chapter": "141",
                "section": section,
                "lrc_statute_id": statute_id,
                "repealed_or_renumbered": bool(re.match(r"(?i)^(repealed|renumbered)", heading)),
            },
        )
        for statute_id, section, heading in rows
    ]
    inventory = {
        "index_url": KY_CHAPTER_INDEX,
        "index_document_count": len(rows),
        "index_count_method": "statute.aspx section links on the LRC chapter 141 page",
        "taken_count": len(documents),
        "repealed_or_renumbered_stubs": sum(1 for d in documents if d["metadata"]["repealed_or_renumbered"]),
    }
    return documents, inventory


def build_virginia(session: requests.Session) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Code of Virginia title 58.1 chapter 3: one LIS HTML page per section."""
    html = _get(session, VA_CHAPTER_INDEX)
    rows: list[tuple[str, str]] = []
    seen: set[str] = set()
    for match in re.finditer(
        r"href=[\"']/vacode/title58\.1/chapter3/section(?P<section>58\.1-[0-9A-Z.:-]+)/[\"'][^>]*>(?P<text>.*?)</a>",
        html,
        flags=re.S,
    ):
        section = match.group("section")
        if section in seen:
            continue
        seen.add(section)
        text = re.sub(r"<[^>]+>", " ", match.group("text"))
        text = re.sub(r"\s+", " ", text).strip()
        heading = re.sub(rf"^§\s*{re.escape(section)}\.?\s*", "", text).strip()
        rows.append((section, heading))
    if len(rows) < 250:
        raise RuntimeError(f"Virginia chapter 3 index parsed only {len(rows)} sections")
    documents = [
        _statute_document(
            jurisdiction="us-va",
            source_id=f"us-va-code-{section.replace('.', '-').replace(':', '-')}",
            title=f"Va. Code § {section}. {heading}".strip(),
            source_url=VA_SECTION_URL.format(section=section),
            source_format="html",
            citation_path=f"us-va/statute/58.1/{section}",
            extraction={"html_content_selector": "article#vacode section.body"},
            authority="Virginia General Assembly (Legislative Information System)",
            index_url=VA_CHAPTER_INDEX,
            metadata={"title": "58.1", "chapter": "3", "section": section},
        )
        for section, heading in rows
    ]
    inventory = {
        "index_url": VA_CHAPTER_INDEX,
        "index_document_count": len(rows),
        "index_count_method": "section links on the LIS chapter 3 table of contents",
        "taken_count": len(documents),
    }
    return documents, inventory


def build_new_york() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Tax Law article 22: one nysenate.gov page per section, listed on the six part pages."""
    rows: list[tuple[int, str, str, str]] = []
    part_titles: dict[int, str] = {}
    for part in range(1, 7):
        html = _impersonated_get(NY_PART_URL.format(part=part))
        title = re.search(r'nys-openleg-result-title-short">([^<]+)<', html)
        part_titles[part] = title.group(1).strip() if title else ""
        for match in re.finditer(
            r'href="https://www\.nysenate\.gov/legislation/laws/TAX/(?P<section>[0-9][0-9A-Z.-]*)"[^>]*>(?P<text>.*?)</a>',
            html,
            flags=re.S,
        ):
            section = match.group("section")
            if any(section == row[1] for row in rows):
                continue
            text = re.sub(r"<[^>]+>", " ", match.group("text"))
            text = re.sub(r"\s+", " ", text).strip()
            heading = re.sub(rf"^SECTION\s+{re.escape(section)}\s*", "", text).strip()
            rows.append((part, section, heading, part_titles[part]))
    if len(rows) < 80:
        raise RuntimeError(f"Tax Law article 22 parts listed only {len(rows)} sections")
    documents = [
        _statute_document(
            jurisdiction="us-ny",
            source_id=f"us-ny-tax-{section.lower()}",
            title=f"N.Y. Tax Law § {section}. {heading}".strip(),
            source_url=NY_SECTION_URL.format(section=section),
            source_format="html",
            citation_path=f"us-ny/statute/TAX/{section}",
            extraction={"html_content_selector": "div.nys-openleg-result-text"},
            authority="New York State Senate (OpenLegislation)",
            index_url=NY_ARTICLE_INDEX,
            metadata={
                "law_id": "TAX",
                "article": "22",
                "part": str(part),
                "part_heading": part_title,
                "section": section,
                "part_index_url": NY_PART_URL.format(part=part),
            },
            request=NY_REQUEST,
        )
        for part, section, heading, part_title in rows
    ]
    inventory = {
        "index_url": NY_ARTICLE_INDEX,
        "index_document_count": len(rows),
        "index_count_method": "section links on the six article 22 part pages (A22P1-A22P6)",
        "taken_count": len(documents),
        "parts": {str(p): sum(1 for r in rows if r[0] == p) for p in range(1, 7)},
    }
    return documents, inventory


def build_california(session: requests.Session) -> dict[str, Any]:
    """RTC parts 10 and 10.2: the section list for extract-california-code-sections."""
    parts: dict[str, list[dict[str, Any]]] = {}
    for part in CA_PARTS:
        toc = _get(session, CA_TOC_URL.format(part=part))
        queries: list[str] = []
        for match in re.finditer(
            r"codes_displayText\.xhtml\?(lawCode=RTC&amp;division=2\.&amp;title=&amp;part="
            rf"{re.escape(part)}&amp;chapter=[0-9.]*&amp;article=[0-9.]*)",
            toc,
        ):
            query = match.group(1).replace("&amp;", "&")
            if query not in queries:
                queries.append(query)
        if not queries:
            raise RuntimeError(f"RTC part {part}: no chapter/article pages on the table of contents")
        pages: list[dict[str, Any]] = []
        for query in queries:
            html = _get(session, CA_TEXT_URL + query)
            sections = re.findall(r"<h6[^>]*>\s*<a href=\"javascript:submitCodesValues\('([0-9.]+)'", html)
            if not sections:
                raise RuntimeError(f"RTC page {query}: no section headings")
            pages.append({"query": query, "sections": [s.rstrip(".") for s in sections]})
        parts[part] = pages
    payload = {
        "version": STATUTE_VERSION,
        "jurisdiction": "us-ca",
        "document_class": "statute",
        "law_code": "RTC",
        "index_urls": [CA_TOC_URL.format(part=part) for part in CA_PARTS],
        "source_authority": "California Legislative Counsel (leginfo.legislature.ca.gov)",
        "note": (
            "Section list for `axiom-corpus-ingest extract-california-code-sections` (one "
            "--section RTC:<n> per entry): Revenue and Taxation Code Division 2, Part 10 "
            "(Personal Income Tax, sections 17001-18181) and Part 10.2 (Administration of "
            "Franchise and Income Tax Laws, sections 18401-19802), read from the official "
            "expanded-branch tables of contents and each chapter/article text page."
        ),
        "parts": {
            part: {
                "chapter_article_pages": len(pages),
                "section_count": sum(len(p["sections"]) for p in pages),
                "pages": pages,
            }
            for part, pages in parts.items()
        },
    }
    return payload


def build_statute(*, verify_only: bool = False) -> None:
    session = _session()
    ky_docs, ky_inv = build_kentucky(session)
    va_docs, va_inv = build_virginia(session)
    ny_docs, ny_inv = build_new_york()
    ca = build_california(session)
    ca_inv = {
        "index_url": ca["index_urls"],
        "index_document_count": sum(p["section_count"] for p in ca["parts"].values()),
        "taken_count": sum(p["section_count"] for p in ca["parts"].values()),
    }
    print(json.dumps({"us-ky": ky_inv, "us-va": va_inv, "us-ny": ny_inv, "us-ca": ca_inv}, indent=1))
    if verify_only:
        return
    _write_manifest(
        MANIFESTS / "us-ky-krs-chapter-141-income-taxes.yaml",
        {"version": STATUTE_VERSION, "documents": ky_docs},
    )
    _write_manifest(
        MANIFESTS / "us-va-code-title-58.1-chapter-3-income-tax.yaml",
        {"version": STATUTE_VERSION, "documents": va_docs},
    )
    _write_manifest(
        MANIFESTS / "us-ny-tax-law-article-22-personal-income-tax.yaml",
        {"version": STATUTE_VERSION, "documents": ny_docs},
    )
    _write_manifest(MANIFESTS / "us-ca-rtc-part-10-10.2-sections.yaml", ca)
    (MANIFESTS / "us-ca-rtc-part-10-10.2-sections.args").write_text(
        "".join(
            f"--section RTC:{section}\n"
            for part in ca["parts"].values()
            for page in part["pages"]
            for section in page["sections"]
        )
    )


# --------------------------------------------------------------------- wave 5: North Carolina

NC_ARTICLE_URL = "https://www.ncleg.gov/EnactedLegislation/Statutes/HTML/ByArticle/Chapter_105/Article_{article}.html"
NC_SECTION_URL = "https://www.ncleg.gov/EnactedLegislation/Statutes/HTML/BySection/Chapter_105/GS_105-{section}.html"
NC_ARTICLES = ("4", "4A")
# Sections whose heading the by-article page lists but for which the General Assembly
# publishes no per-section page (HTTP 404 on 2026-09-14): repealed placeholders.
NC_NO_SECTION_PAGE = {"163"}
W5_SOURCE_AS_OF = "2026-09-15"
W5_STATUTE_VERSION = "2026-09-15-income-tax-chapter"


def build_north_carolina(session: requests.Session) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """G.S. Chapter 105 Articles 4 (Income Tax) and 4A (Withholding; Estimated Income Tax
    for Individuals): one official per-section HTML page each, the section list read from
    the General Assembly's by-article HTML (section headings ``§ 105-N.``)."""
    rows: list[tuple[str, str, str, str]] = []
    seen: set[str] = set()
    part = ""
    for article in NC_ARTICLES:
        html = _get(session, NC_ARTICLE_URL.format(article=article))
        pattern = re.compile(
            r"(?:Part (?P<part>\d+)\.\s*(?P<part_heading>[^<]{0,80}))"
            r"|(?:(?:&sect;|&#167;|§)(?:&nbsp;|\s)*105-(?P<section>1[3-6][0-9](?:\.[0-9]+)?[A-Z]?)\.(?:&nbsp;|\s)*(?P<heading>[^<]{0,200}))"
        )
        count = 0
        for match in pattern.finditer(html):
            if match.group("part"):
                part = f"Part {match.group('part')}. {match.group('part_heading').strip()}"
                continue
            section = match.group("section")
            if section in seen or section in NC_NO_SECTION_PAGE:
                continue
            seen.add(section)
            heading = re.sub(r"\s+", " ", match.group("heading")).strip()
            rows.append((article, section, heading, part))
            count += 1
        if count < 10:
            raise RuntimeError(f"G.S. 105 Article {article} page listed only {count} sections")
    documents = [
        _statute_document(
            jurisdiction="us-nc",
            source_id=f"us-nc-gs-105-{section.replace('.', '-')}",
            title=f"G.S. 105-{section}. {heading}".strip(),
            source_url=NC_SECTION_URL.format(section=section),
            source_format="html",
            citation_path=f"us-nc/statute/105/105-{section}",
            extraction={"html_content_selector": "body"},
            authority="North Carolina General Assembly",
            index_url=NC_ARTICLE_URL.format(article=article),
            metadata={"chapter": "105", "article": article, "part": part_heading, "section": f"105-{section}",
                      "repealed_or_renumbered": bool(re.match(r"(?i)^(repealed|recodified|transferred|reserved)", heading))},
        )
        for article, section, heading, part_heading in rows
    ]
    for doc in documents:
        doc["source_as_of"] = W5_SOURCE_AS_OF
        doc["expression_date"] = W5_SOURCE_AS_OF
        doc["metadata"]["source_status"] = f"current_official_codified_text_as_of_{W5_SOURCE_AS_OF}"
        doc["metadata"]["source_family"] = "state-income-tax-chapter-2026-09-15"
    inventory = {
        "index_url": [NC_ARTICLE_URL.format(article=a) for a in NC_ARTICLES],
        "index_document_count": len(rows),
        "index_count_method": "section headings on the General Assembly by-article HTML pages for Articles 4 and 4A",
        "taken_count": len(documents),
        "repealed_or_renumbered_stubs": sum(1 for d in documents if d["metadata"]["repealed_or_renumbered"]),
        "no_section_page": sorted(NC_NO_SECTION_PAGE),
        "articles": {a: sum(1 for r in rows if r[0] == a) for a in NC_ARTICLES},
    }
    return documents, inventory


def build_north_carolina_statute(*, verify_only: bool = False) -> None:
    session = _session()
    docs, inv = build_north_carolina(session)
    print(json.dumps({"us-nc": inv}, indent=1))
    if verify_only:
        return
    _write_manifest(
        MANIFESTS / "us-nc-gs-chapter-105-article-4-income-tax.yaml",
        {"version": W5_STATUTE_VERSION, "documents": docs},
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--family",
        choices=("statute", "amounts", "queue", "forms", "forms-queue", "nc-statute"),
        required=True,
        help="wave 5 (2026-09-15): forms = TY2025 state resident-return manifests from "
        "state_tax_ty2025_forms.py; forms-queue = their queue rows; nc-statute = the North "
        "Carolina G.S. Chapter 105 Article 4 section manifest",
    )
    parser.add_argument("--verify", action="store_true", help="read the indexes and print counts without writing")
    args = parser.parse_args()
    if args.family == "statute":
        build_statute(verify_only=args.verify)
        return 0
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from state_tax_ty2026_amounts import build_amounts, update_queue

    if args.family == "amounts":
        build_amounts(verify_only=args.verify)
        return 0
    if args.family == "forms":
        from state_tax_ty2025_forms import build_forms

        build_forms(verify_only=args.verify)
        return 0
    if args.family == "forms-queue":
        from state_tax_ty2025_forms import update_queue as update_forms_queue

        update_forms_queue()
        return 0
    if args.family == "nc-statute":
        build_north_carolina_statute(verify_only=args.verify)
        return 0
    update_queue()
    return 0


if __name__ == "__main__":
    sys.exit(main())
