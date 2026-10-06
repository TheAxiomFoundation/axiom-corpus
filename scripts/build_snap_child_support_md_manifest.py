"""Build the complete SNAP COMAR manifest from DSD's retained chapter index."""

from __future__ import annotations

import argparse
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from bs4 import BeautifulSoup

INDEX_URL = "https://regs.maryland.gov/us/md/exec/comar/07.03.17"
ROOT = "us-md/regulation/title-07/subtitle-03/chapter-17"


def build_manifest(index_html: bytes) -> dict[str, Any]:
    """Preserve the publisher's complete section list and printed history dates."""
    soup = BeautifulSoup(index_html, "html.parser")
    article = soup.select_one("article.content")
    if article is None:
        raise ValueError("missing COMAR chapter article")
    links = article.select("nav.toc a")
    if not links:
        raise ValueError("missing COMAR chapter contents")
    history = [p.get_text(" ", strip=True) for p in article.select("section.annotations p")]
    chapter_history = [line for line in history if line.startswith("Chapter revised effective")]
    # A section's expression date is the last printed amendment affecting it,
    # or the chapter-wide revision. It is not an inferred original adoption date.
    date_pattern = r"[A-Z][a-z]+ \d{1,2}, \d{4}"

    def last_date(lines: list[str]) -> str:
        dates = [
            datetime.strptime(match, "%B %d, %Y").date().isoformat()
            for line in lines
            for match in re.findall(date_pattern, line)
        ]
        return max(dates)

    common = {
        "jurisdiction": "us-md",
        "document_class": "regulation",
        "source_format": "html",
        "source_as_of": "2026-09-27",
        "extraction": {"html_content_selector": "article.content"},
    }
    metadata = {
        "primary_source": True,
        "source_authority": "Maryland Department of Human Services",
        "official_publisher": "Maryland Division of State Documents",
        "program": "SNAP",
        "index_url": INDEX_URL,
        "index_document_count": len(links),
        "source_as_of_note": "live-text retrieval date",
        "expression_date_note": (
            "latest effective amendment date printed in the chapter administrative history "
            "for this regulation, including chapter-wide revisions; not original adoption"
        ),
        "discovered_via": "SNAP child support cited state sources; policyengine-us PR #9622",
    }
    documents = [{
        **common,
        "source_id": "md-comar-07-03-17-index",
        "title": "COMAR 07.03.17 Food Supplement Program: administrative history and authority",
        "source_url": INDEX_URL,
        "citation_path": ROOT,
        "expression_date": last_date(history),
        "metadata": {
            **metadata,
            "document_subtype": "administrative_code_chapter_history",
            "listed_regulations": [a.get_text(" ", strip=True) for a in links],
            "expression_date_note": "latest effective amendment date printed in chapter history",
        },
    }]
    for link in links:
        href = str(link["href"])
        number = href.rsplit(".", 1)[-1]
        matching = [line for line in history if re.match(rf"Regulation \.{re.escape(number)}(?=[A-Z ,]|$)", line)]
        documents.append({
            **common,
            "source_id": f"md-comar-07-03-17-{number}",
            "title": f"COMAR 07.03.17{link.get_text(' ', strip=True)}",
            "source_url": f"https://regs.maryland.gov{href}",
            "citation_path": f"{ROOT}/regulation-{number}",
            "expression_date": last_date(chapter_history + matching),
            "metadata": {
                **metadata,
                "document_subtype": "administrative_code_regulation",
                "regulation_number": f"07.03.17.{number}",
                "historical_notes": chapter_history + matching,
                "legacy_source_url": f"https://dsd.maryland.gov/regulations/Pages/07.03.17.{number}.aspx",
            },
        })
    return {"documents": documents}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(yaml.safe_dump(build_manifest(args.index.read_bytes()), sort_keys=False, allow_unicode=True))
