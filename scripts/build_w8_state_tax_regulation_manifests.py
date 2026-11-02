#!/usr/bin/env python3
"""Build the 2026-10-20 income-tax regulation manifests for AR, DC and UT.

These are three of the five rows that the 2026-09-14 state income-tax regulation run
(``docs/ingest-runs/2026-09-14-state-tax-regulations.md``, needs-closure gap R01) could
not extract. Their publishers changed:

* ``codeofarrules.arkansas.gov`` now renders section text server-side under a new query
  shape (``?levelType=section&titleID=&chapterID=&subChapterID=&partID=&subPartID=&sectionID=``);
  the recorded ``?levelType=PART&id=`` shape answers with a null-reference error page.
* ``dcregs.dc.gov`` now prints a stable ``RuleList.aspx?DownloadFile=`` address and a
  ``SectionList.aspx?SectionNumber=`` address beside every ``__doPostBack`` control.
* ``adminrules.utah.gov`` relaunched as eRules v1.0.0 on 2026-10-16; every
  ``/public/rule/...`` and ``/api/public/getfile/...`` address answers 404 and the rule
  now lives at ``/Rule/{ruleId}/{ruleTypeId}/{ruleVersionId}/undefined``.

Each jurisdiction's manifest is written to ``manifests/us-<st>-income-tax-regulations.yaml``
with the family's scope version ``2026-10-20-income-tax-regulations``. Every enumeration
reads the official publisher's own index; ``--cache-dir`` keeps the index responses so a
rebuild is reproducible offline. The script prints a JSON summary per jurisdiction
(index URL, index document count, taken count, index families) for the queue rows.

Run: ``uv run python scripts/build_w8_state_tax_regulation_manifests.py [--only us-xx]``
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

import requests
import yaml

USER_AGENT = (
    "Axiom/1.0 (Legal Archive; contact@axiom-foundation.org) "
    "https://github.com/TheAxiomFoundation/axiom-corpus"
)
SOURCE_AS_OF = "2026-10-20"
SCOPE_VERSION = "2026-10-20-income-tax-regulations"
RUN_NOTE = "docs/ingest-runs/2026-10-20-w8-state-tax-regulations.md"
DISCOVERED_VIA = "manual-review:tax-agent-queue 2026-10-20 (needs-closure R01 re-probe, wave 8)"
REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_DIR = REPO_ROOT / "manifests"
HOST_DELAY_SECONDS = 1.5

_cache_dir: Path | None = None
_last_request: dict[str, float] = {}


def fetch(
    url: str,
    *,
    method: str = "GET",
    body: str | None = None,
    content_type: str | None = None,
) -> bytes:
    """Fetch ``url`` from the official publisher, one host at a time, TLS verified."""

    key = hashlib.sha1(f"{method} {url} {body or ''}".encode()).hexdigest()
    if _cache_dir is not None:
        cached = _cache_dir / f"{key}.bin"
        if cached.exists():
            return cached.read_bytes()
    host = requests.utils.urlparse(url).netloc
    waited = time.monotonic() - _last_request.get(host, 0.0)
    if waited < HOST_DELAY_SECONDS:
        time.sleep(HOST_DELAY_SECONDS - waited)
    headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    if content_type:
        headers["Content-Type"] = content_type
    response = requests.request(method, url, headers=headers, data=body, timeout=120)
    _last_request[host] = time.monotonic()
    if response.status_code != 200:
        raise RuntimeError(f"{url}: HTTP {response.status_code}")
    content = response.content
    if _cache_dir is not None:
        _cache_dir.mkdir(parents=True, exist_ok=True)
        (_cache_dir / f"{key}.bin").write_bytes(content)
    return content


def document(
    *,
    jurisdiction: str,
    source_id: str,
    citation_path: str,
    title: str,
    source_url: str,
    source_format: str,
    expression_date: str,
    authority: str,
    publisher: str,
    subtype: str,
    index_url: str,
    extraction: dict[str, Any] | None = None,
    request: dict[str, Any] | None = None,
    download_url: str | None = None,
    extra_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "source_id": source_id,
        "jurisdiction": jurisdiction,
        "document_class": "regulation",
        "citation_path": citation_path,
        "title": title,
        "source_url": source_url,
        "source_format": source_format,
        "source_as_of": SOURCE_AS_OF,
        "expression_date": expression_date,
    }
    if download_url:
        entry["download_url"] = download_url
    if request:
        entry["request"] = request
    if extraction:
        entry["extraction"] = extraction
    metadata: dict[str, Any] = {
        "primary_source": True,
        "source_authority": authority,
        "official_publisher": publisher,
        "document_subtype": subtype,
        "program": "individual_income_tax",
        "source_discovery_group": f"{jurisdiction}/regulation/income-tax",
        "discovered_via": f"{DISCOVERED_VIA}; index {index_url}",
        "run_note": RUN_NOTE,
    }
    if extra_metadata:
        metadata.update(extra_metadata)
    entry["metadata"] = metadata
    return entry


class Builder:
    def __init__(self) -> None:
        self.summary: dict[str, dict[str, Any]] = {}

    def write(
        self,
        jurisdiction: str,
        documents: list[dict[str, Any]],
        *,
        index_url: str,
        index_document_count: int,
        index_families: dict[str, int],
        note: str,
        header: str,
    ) -> None:
        path = MANIFEST_DIR / f"{jurisdiction}-income-tax-regulations.yaml"
        payload = {"version": SCOPE_VERSION, "documents": documents}
        body = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, width=110)
        path.write_text(
            f"# {header}\n# Generated by scripts/{Path(__file__).name}; edit the generator.\n{body}"
        )
        self.summary[jurisdiction] = {
            "manifest": str(path.relative_to(REPO_ROOT)),
            "scope_version": SCOPE_VERSION,
            "index_url": index_url,
            "index_document_count": index_document_count,
            "taken_count": len(documents),
            "index_families": index_families,
            "note": note,
        }
        print(f"{jurisdiction}: {len(documents)} documents -> {path.name}", file=sys.stderr)


# --------------------------------------------------------------------------------------
# Arkansas: Code of Arkansas Rules, Title 26 Taxation, Parts 100-104
# --------------------------------------------------------------------------------------

AR_RULE = "https://codeofarrules.arkansas.gov/Rules/Rule"
AR_PART_INDEX = (
    "https://codeofarrules.arkansas.gov/Home/GetRulesSearchPartDropdown?levelType=PART&titleID=26"
)
AR_INCOME_TAX_PART_IDS = ("941", "942", "943", "944", "945")
AR_FAMILY_PATTERNS: tuple[tuple[str, str], ...] = (
    (
        "individual income tax",
        r"individual income tax|comprehensive individual|standard mileage|substitute and reproduced|employee contributions to employment",
    ),
    (
        "income tax credits and incentives",
        r"income tax credit|tax credit|recycling|apprenticeship|waterways|geotourism|historic rehabilitation|railroad modernization|donations or sales",
    ),
    (
        "income tax withholding and administration",
        r"withholding|electronic filing|electronic return originator|electronic funds transfer",
    ),
    (
        "corporate and pass-through income tax",
        r"corporation income tax|pass-through|intragroup intangible|small business tax accounting",
    ),
    (
        "sales, use and excise tax",
        r"gross receipts|compensating use|sales tax|use tax|food and food ingredients|vending|veterinarian|natural gas or electricity|water used|car wash",
    ),
    (
        "tobacco, beverage and other excise",
        r"beer excise|soft drink|cigarette|tobacco|alternative fuels",
    ),
    (
        "property, severance and transfer tax",
        r"real property tax credit|real estate transfer|severance|market valuation|nonresidential construction",
    ),
    (
        "tax administration and appeals",
        r"disclosable tax information|freedom of information|browsing|settlement or compromise|advisory council|bill of rights|surety bond|record keeping|practice and procedure|general provisions|general rules of practice|implementation|uniform reporting|import/export|tax appeals|commissioner of state lands|waste reduction|law enforcement family|check-off",
    ),
)


def _ar_family(title: str) -> str:
    lowered = title.lower()
    for name, pattern in AR_FAMILY_PATTERNS:
        if re.search(pattern, lowered):
            return name
    return "other taxation rules"


def _ar_query(level: str, part_id: str, subpart_id: str, section_id: str) -> str:
    return (
        f"{AR_RULE}?levelType={level}&titleID=26&chapterID=33&subChapterID=261"
        f"&partID={part_id}&subPartID={subpart_id}&sectionID={section_id}"
    )


def _ar_walk() -> list[dict[str, str]]:
    """Follow the publisher's own NEXT chain across Parts 100-104."""

    nodes: list[dict[str, str]] = []
    query = _ar_query("part", AR_INCOME_TAX_PART_IDS[0], "", "")
    seen: set[str] = set()
    while query and query not in seen:
        seen.add(query)
        page = fetch(query).decode("utf-8", "replace")
        params = dict(re.findall(r"(\w+)=([^&]*)", query.split("?", 1)[1]))
        heading_match = re.search(r"<h1>(.*?)</h1>", page, re.S)
        heading = (
            " ".join(html.unescape(re.sub(r"<[^>]+>", "", heading_match.group(1))).split())
            if heading_match
            else ""
        )
        appendix = re.search(r'href="(/Rules/AppendixDocument\?[^"]+)"', page)
        nodes.append(
            {
                "url": query,
                "level": params.get("levelType", ""),
                "part_id": params.get("partID", ""),
                "subpart_id": params.get("subPartID", ""),
                "section_id": params.get("sectionID", ""),
                "heading": heading,
                "appendix_href": html.unescape(appendix.group(1)) if appendix else "",
            }
        )
        next_link = re.search(r'<a style="float:right;" href="\?([^"]+)"', page)
        if not next_link:
            break
        next_query = f"{AR_RULE}?{next_link.group(1).replace('&amp;', '&')}"
        next_params = dict(re.findall(r"(\w+)=([^&]*)", next_query.split("?", 1)[1]))
        if next_params.get("partID") not in AR_INCOME_TAX_PART_IDS:
            break
        query = next_query
    return nodes


def build_ar(b: Builder) -> None:
    listing = json.loads(fetch(AR_PART_INDEX))
    families: dict[str, int] = {}
    part_titles: dict[str, str] = {}
    for part in listing:
        families[_ar_family(part["nodeTextFull"])] = (
            families.get(_ar_family(part["nodeTextFull"]), 0) + 1
        )
        part_titles[str(part["nodeID"])] = part["nodeTextFull"]

    nodes = _ar_walk()
    documents: list[dict[str, Any]] = []
    for node in nodes:
        part_number = part_titles[node["part_id"]].split(".")[0].replace("Part ", "").strip()
        if node["level"] == "section":
            label_match = re.search(r"26 CAR §\s*([0-9A-Za-z.\-]+)", node["heading"])
            if not label_match:
                raise RuntimeError(f"no section label in {node['heading']!r}")
            label = label_match.group(1).rstrip(".")
            documents.append(
                document(
                    jurisdiction="us-ar",
                    source_id=f"ar-car-26-{label.lower()}",
                    citation_path=(
                        f"us-ar/regulation/car/title-26/part-{part_number}/section-{label.lower()}"
                    ),
                    title=node["heading"],
                    source_url=node["url"],
                    source_format="html",
                    expression_date="2026-10-19",
                    authority="Arkansas Department of Finance and Administration",
                    publisher="Arkansas Secretary of State, Code of Arkansas Rules",
                    subtype="administrative_code_section",
                    index_url=AR_PART_INDEX,
                    extraction={"html_content_selector": "#docxContent"},
                    extra_metadata={
                        "code_citation": f"26 CAR § {label}",
                        "part_title": part_titles[node["part_id"]],
                        "expression_date_note": (
                            "Last Updated date the Code of Arkansas Rules prints on every page"
                        ),
                        "publisher_currency_note": (
                            "the online database is the official version of the Code of Arkansas"
                            " Rules and became effective 2025-01-01 (Ark. Code § 25-15-218);"
                            " updated weekly"
                        ),
                    },
                )
            )
        elif node["level"] == "appendix" and node["appendix_href"]:
            documents.append(
                document(
                    jurisdiction="us-ar",
                    source_id=f"ar-car-26-part-{part_number}-appendix-a",
                    citation_path=(f"us-ar/regulation/car/title-26/part-{part_number}/appendix-a"),
                    title=f"26 CAR pt. {part_number} {node['heading']}",
                    source_url=node["url"],
                    download_url=f"https://codeofarrules.arkansas.gov{node['appendix_href']}",
                    source_format="pdf",
                    expression_date="2026-10-19",
                    authority="Arkansas Department of Finance and Administration",
                    publisher="Arkansas Secretary of State, Code of Arkansas Rules",
                    subtype="administrative_code_appendix",
                    index_url=AR_PART_INDEX,
                    extraction={"page_citation_prefix": "page"},
                    extra_metadata={
                        "part_title": part_titles[node["part_id"]],
                        "source_url_note": (
                            "source_url is the appendix page; download_url is the appendix PDF"
                            " the page links"
                        ),
                    },
                )
            )

    b.write(
        "us-ar",
        documents,
        index_url=AR_PART_INDEX,
        index_document_count=len(listing),
        index_families=families,
        note=(
            "Code of Arkansas Rules Title 26 Taxation part index (67 parts); Parts 100-104"
            " (Subchapter D, individual income tax) taken as 71 section pages and 2 appendix"
            " PDFs. The 5 part pages and 5 'Subpart 1. Generally' pages carry no rule text."
        ),
        header=(
            "Wave 8 state-tax regulations: Code of Arkansas Rules Title 26 Parts 100-104"
            " (individual income tax)."
        ),
    )


# --------------------------------------------------------------------------------------
# District of Columbia: DCMR Title 9 Chapter 1 (Income and Franchise Taxes)
# --------------------------------------------------------------------------------------

DC_INDEX = "https://dcregs.dc.gov/Common/DCMR/RuleList.aspx?ChapterNum=9-1"
DC_ROW_RE = re.compile(
    r'lnkFile_(\d+)"\s+title="([^"]+)"[^>]*>([^<]+)</a>.*?'
    r'lblRegCat_\1">(.*?)</span>.*?'
    r'Label1_\1"\s+title="([^"]*)"[^>]*>[^<]*</a>.*?'
    r'Label2_\1">([^<]*)</span>',
    re.S,
)
DC_FAMILIES: tuple[tuple[str, int, int], ...] = (
    ("general provisions and exempt organizations", 100, 104),
    ("returns and filing requirements", 105, 111),
    ("individual income tax computation, credits and modifications", 112, 115),
    ("franchise tax on corporations and unincorporated businesses", 116, 121),
    ("allocation and apportionment", 122, 129),
    ("withholding", 130, 143),
    ("estimated tax", 144, 149),
    ("refunds, penalties and licenses", 150, 152),
    ("modifications, federal adjustments and college savings", 153, 155),
    ("combined reporting and investment entities", 156, 175),
    ("returns and filing requirements", 176, 176),
    ("reserved", 177, 185),
)


def _dc_family(section_number: int) -> str:
    for name, low, high in DC_FAMILIES:
        if low <= section_number <= high:
            return name
    return "other"


def build_dc(b: Builder) -> None:
    page = fetch(DC_INDEX).decode("utf-8", "replace")
    rows = DC_ROW_RE.findall(page)
    if not rows:
        raise RuntimeError(f"{DC_INDEX}: no section rows parsed")
    families: dict[str, int] = {}
    documents: list[dict[str, Any]] = []
    for _, section_url, number, category, download_url, effective in rows:
        number = html.unescape(number).strip()
        heading = " ".join(html.unescape(category).split())
        download_url = html.unescape(download_url)
        effective = html.unescape(effective).strip()
        if "DownloadFile" not in download_url:
            raise RuntimeError(f"{number}: no DownloadFile address on the chapter page")
        section_digits = int(number.split("-", 1)[1])
        family = _dc_family(section_digits)
        families[family] = families.get(family, 0) + 1
        month, day, year = (int(part) for part in effective.split("/"))
        printed_is_sentinel = (year, month, day) == (1900, 1, 1)
        extra: dict[str, Any] = {
            "code_citation": f"{number} DCMR",
            "chapter": "9-1 Income and Franchise Taxes",
            "index_family": family,
            "effective_date_printed": effective,
        }
        if printed_is_sentinel:
            extra["expression_date_note"] = (
                "the chapter page prints the 1/1/1900 placeholder for this section, so the"
                " expression date is the source-as-of date"
            )
            expression_date = SOURCE_AS_OF
        else:
            extra["expression_date_note"] = (
                "effective date the chapter page prints for the latest version"
            )
            expression_date = f"{year:04d}-{month:02d}-{day:02d}"
        documents.append(
            document(
                jurisdiction="us-dc",
                source_id=f"dc-dcmr-{number}",
                citation_path=f"us-dc/regulation/dcmr/{number}",
                title=f"DCMR {number} {heading}",
                source_url=html.unescape(section_url),
                download_url=download_url,
                source_format="doc",
                expression_date=expression_date,
                authority="District of Columbia Office of Tax and Revenue",
                publisher=("DC Office of Documents and Administrative Issuances (DCMR)"),
                subtype="municipal_regulation_section",
                index_url=DC_INDEX,
                extraction={"segmentation": "single_block"},
                extra_metadata=extra,
            )
        )
    b.write(
        "us-dc",
        documents,
        index_url=DC_INDEX,
        index_document_count=len(rows),
        index_families=families,
        note=(
            "DCMR Title 9 Chapter 1 (Income and Franchise Taxes). Every one of the 85 listed"
            " sections now carries a stable RuleList.aspx?DownloadFile= address beside its"
            " __doPostBack control; all 85 taken, including the 9 RESERVED sections the"
            " publisher prints as rule text."
        ),
        header="Wave 8 state-tax regulations: DCMR Title 9 Chapter 1 (Income and Franchise Taxes).",
    )


# --------------------------------------------------------------------------------------
# Utah: Utah Administrative Code R865-9I (Tax Commission, Auditing)
# --------------------------------------------------------------------------------------

UT_SEARCH = "https://adminrules.utah.gov/api/search"
UT_RULE_VERSION = "https://adminrules.utah.gov/api/ruleVersion"
UT_CURRENT_RULE_TYPE_ID = 51
UT_INDEX = f"{UT_SEARCH} (POST searchTerm=R865 ruleTypeId=51)"
UT_FAMILY_BY_RULE: dict[str, str] = {
    "R865-9i": "individual income tax",
    "R865-3c": "corporate and franchise income tax",
    "R865-6f": "corporate and franchise income tax",
    "R865-19s": "sales and use tax",
    "R865-21u": "sales and use tax",
    "R865-12l": "sales and use tax",
    "R865-13g": "fuel tax",
    "R865-4d": "fuel tax",
    "R865-16r": "severance and mineral tax",
    "R865-15o": "severance and mineral tax",
    "R865-14w": "severance and mineral tax",
    "R865-20t": "tobacco tax",
    "R865-11q": "assessments and fees",
    "R865-7h": "assessments and fees",
}


def _ut_search(term: str) -> list[dict[str, Any]]:
    body = json.dumps({"searchTerm": term, "ruleTypeId": UT_CURRENT_RULE_TYPE_ID})
    return json.loads(fetch(UT_SEARCH, method="POST", body=body, content_type="application/json"))


def _ut_rule_versions(version_ids: list[int]) -> list[dict[str, Any]]:
    body = json.dumps({"ruleTypeId": UT_CURRENT_RULE_TYPE_ID, "versionIds": version_ids})
    return json.loads(
        fetch(UT_RULE_VERSION, method="POST", body=body, content_type="application/json")
    )


def build_ut(b: Builder) -> None:
    version_ids: list[int] = []
    for agency in _ut_search("R865"):
        for title in agency["titleResults"]:
            version_ids += [rule["ruleVersionId"] for rule in title["ruleResults"]]
    versions = _ut_rule_versions(version_ids)
    families: dict[str, int] = {}
    for version in versions:
        family = UT_FAMILY_BY_RULE.get(version["ruleReference"], "other tax rules")
        families[family] = families.get(family, 0) + 1

    income_tax = [v for v in versions if v["ruleReference"].lower() == "r865-9i"]
    if len(income_tax) != 1:
        raise RuntimeError(f"expected one R865-9I current rule, got {len(income_tax)}")
    rule = income_tax[0]
    month, day, year = (int(part) for part in rule["effectiveDateString"].split("/"))
    rule_url = (
        f"https://adminrules.utah.gov/Rule/{rule['ruleId']}/{rule['ruleTypeId']}"
        f"/{rule['ruleVersionId']}/undefined"
    )
    documents = [
        document(
            jurisdiction="us-ut",
            source_id="ut-admin-rules-r865-9i-current",
            citation_path="us-ut/regulation/admin-rules/r865/9i",
            title=("Utah Administrative Code R865-9I: Income Tax (Tax Commission, Auditing)"),
            source_url=rule_url,
            source_format="html",
            expression_date=f"{year:04d}-{month:02d}-{day:02d}",
            authority="Utah State Tax Commission",
            publisher="Utah Office of Administrative Rules (eRules)",
            subtype="administrative_code_rule",
            index_url=UT_INDEX,
            extraction={"html_content_selector": "div[class$='_ruleHtml']"},
            extra_metadata={
                "code_citation": "R865-9I",
                "rule_id": rule["ruleId"],
                "rule_version_id": rule["ruleVersionId"],
                "rule_type_id": rule["ruleTypeId"],
                "title_number": rule["titleNumber"],
                "agency": rule["agencyName"],
                "effective_date": rule["effectiveDateString"],
                "expression_date_note": ("effective date the eRules rule-version record prints"),
                "source_url_note": (
                    "eRules relaunched 2026-10-16; the recorded"
                    " /public/rule/R865-9I/Current%20Rules address and the"
                    " /api/public/getfile/uac-html/ file route both answer 404. The rule page"
                    " server-renders the publisher's own converted rule HTML"
                    " (div.awdiv / span.awtext1) into the DOM."
                ),
                "publisher_file_route_note": (
                    "the new /api/storage/{file} download route answers HTTP 500 for every"
                    " file name, so the rule page is the only working official address"
                ),
            },
        )
    ]
    b.write(
        "us-ut",
        documents,
        index_url=UT_INDEX,
        index_document_count=len(versions),
        index_families=families,
        note=(
            "Utah Administrative Code Title R865 (Tax Commission, Auditing): 14 current"
            " rules; R865-9I Income Tax taken as one whole-rule document. Corporate and"
            " franchise (R865-3c, R865-6f) and the other tax families are out of scope for"
            " the income-tax row, as in the 2026-09-14 run."
        ),
        header="Wave 8 state-tax regulations: Utah Administrative Code R865-9I (Income Tax).",
    )


BUILDERS = {"us-ar": build_ar, "us-dc": build_dc, "us-ut": build_ut}


def main() -> int:
    global _cache_dir
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", action="append", choices=sorted(BUILDERS))
    parser.add_argument("--cache-dir", type=Path)
    args = parser.parse_args()
    if args.cache_dir:
        _cache_dir = args.cache_dir
    builder = Builder()
    for jurisdiction in args.only or sorted(BUILDERS):
        BUILDERS[jurisdiction](builder)
    print(json.dumps(builder.summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
