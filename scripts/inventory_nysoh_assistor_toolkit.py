#!/usr/bin/env python3
"""Inventory the NY State of Health Assistor Tool Kit index by document family.

The Assistor Tool Kit page is the publisher's own index for the 2026 Medicaid,
Child Health Plus and Essential Plan income-levels chart that the Medicaid
queue's `us-ny` wave-6 bundle-gap row names
(`manifests/us-ny-medicaid-income-levels-2026.yaml`,
scope `us-ny/guidance/2026-10-20-w8-ny-medicaid`). The marketplace's own
resources library (`/resources`) renders its items server-side but lists none of
these PDFs, its search form is JavaScript-only, and the Drupal sitemap holds no
resource nodes, so this page is the index that proves the row's primary source.

The host answers HTTP 403 (CloudFront, 919 bytes) to the extractor's own Axiom
User-Agent and HTTP 200 to the extractor's built-in browser User-Agent fallback,
which is what this script sends. TLS verification is never disabled.

Usage:
    uv run --extra dev python scripts/inventory_nysoh_assistor_toolkit.py [--json]
"""

from __future__ import annotations

import argparse
import html
import json
import re
from collections import Counter

import requests

from axiom_corpus.corpus.documents import OFFICIAL_DOCUMENT_BROWSER_USER_AGENT

INDEX_URL = "https://info.nystateofhealth.ny.gov/AssistorToolKit"
DOCUMENT_SUFFIX = re.compile(r"\.(pdf|docx?|xlsx?|pptx?)(\?|$)", re.IGNORECASE)
_MONTH_FIRST = re.compile(
    r"^(january|february|march|april|may|june|july|august|september|october|november|december)\b",
    re.IGNORECASE,
)


def family(label: str, href: str) -> str:
    """Name the index family of one document link, by its printed label and address."""
    text = f"{label} {href}".lower()
    if "newsletter" in href.lower() or _MONTH_FIRST.match(label):
        return "assistor_newsletter_pdf"
    if re.search(r"income level|fpl|desk aid", label, re.IGNORECASE):
        return "eligibility_income_chart_pdf"
    if re.search(r"doh ?50(88|90|91)|identity|attestation|fax cover", text):
        return "identity_form_or_instruction_pdf"
    if re.search(r"ny\.gov|registering your account", label, re.IGNORECASE):
        return "account_instruction_pdf"
    if re.search(r"essential health benefits", label, re.IGNORECASE):
        return "qhp_benefit_attachment_pdf"
    if re.search(r"hra|training memo", text):
        return "assistor_training_memo_pdf"
    return "other_document"


def main_region(page: str) -> str:
    """The index page's main region, without its site navigation."""
    start = page.find('id="main-content"')
    region = page[start:] if start >= 0 else page
    end = region.find("</main>")
    return region[:end] if end >= 0 else region


def inventory(page: str) -> dict[str, object]:
    region = main_region(page)
    links: list[dict[str, str]] = []
    for match in re.finditer(
        r'<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>', region, re.DOTALL | re.IGNORECASE
    ):
        href = html.unescape(match.group(1))
        label = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(match.group(2)))).strip()
        if label:
            links.append({"href": href, "label": label})
    documents = [link for link in links if DOCUMENT_SUFFIX.search(link["href"])]
    families = Counter(family(link["label"], link["href"]) for link in documents)
    return {
        "index_url": INDEX_URL,
        "link_count": len(links),
        "index_document_count": len(documents),
        "index_families": dict(sorted(families.items())),
        "eligibility_income_chart_pdf": [
            link
            for link in documents
            if family(link["label"], link["href"]) == "eligibility_income_chart_pdf"
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print the inventory as JSON.")
    args = parser.parse_args()
    response = requests.get(
        INDEX_URL,
        timeout=60,
        headers={"User-Agent": OFFICIAL_DOCUMENT_BROWSER_USER_AGENT},
    )
    response.raise_for_status()
    report = inventory(response.text)
    if args.json:
        print(json.dumps(report, indent=2))
        return 0
    print(f"{report['index_url']}: HTTP {response.status_code}, {len(response.content)} bytes")
    print(f"  links: {report['link_count']}, document links: {report['index_document_count']}")
    for name, count in report["index_families"].items():  # type: ignore[union-attr]
        print(f"    {name}: {count}")
    print("  eligibility_income_chart_pdf:")
    for link in report["eligibility_income_chart_pdf"]:  # type: ignore[union-attr]
        print(f"    {link['label']}\n      {link['href']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
