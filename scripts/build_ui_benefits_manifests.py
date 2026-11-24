#!/usr/bin/env python3
"""Write the state statute manifests of the unemployment insurance benefits run.

One manifest per state, ``manifests/us-<st>-ui-benefits-statute.yaml``, each naming the
part of the state's code that holds its unemployment insurance law, for the existing
``extract-state-statutes`` adapters. The audit that lists the sections is
``sources/plans/ui-scope-audit-documents.json``; the run note is
``docs/ingest-runs/2026-11-24-ui-benefits-wave1.md``.

Usage::

    python scripts/build_ui_benefits_manifests.py
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
VERSION = "2026-11-24-ui-benefits-statute"
AS_OF = "2026-11-24"
RUN_NOTE = "docs/ingest-runs/2026-11-24-ui-benefits-wave1.md"

# state: (wave, law, [(source id suffix, adapter, source_url, options)])
STATES: dict[str, tuple[int, str, list[tuple[str, str, str, dict]]]] = {
    "ak": (
        1,
        "Alaska Employment Security Act, AS 23.20",
        [
            (
                "title-23",
                "alaska-statutes",
                "https://www.akleg.gov/basis/statutes.asp",
                {"only_title": "23", "workers": 4},
            ),
        ],
    ),
    "de": (
        1,
        "19 Del. C. chapter 33, Unemployment Compensation",
        [
            (
                "title-19-chapter-33",
                "delaware-code",
                "https://www.delcode.delaware.gov/title19/c033/index.html",
                {"only_title": "19", "only_chapter": "33", "workers": 1},
            ),
        ],
    ),
    "fl": (
        1,
        "Reemployment Assistance Program Law, Fla. Stat. chapter 443 (Title XXXI)",
        [
            (
                "title-xxxi",
                "florida-statutes",
                "https://www.leg.state.fl.us/statutes/",
                {
                    "only_title": "XXXI",
                    "source_year": 2025,
                    "request_delay_seconds": 0.05,
                    "timeout_seconds": 60,
                },
            ),
        ],
    ),
    "hi": (
        1,
        "Hawaii Employment Security Law, HRS chapter 383",
        [
            (
                "chapter-383",
                "hawaii-revised-statutes",
                "https://data.capitol.hawaii.gov/hrscurrent/",
                {
                    "only_chapter": "383",
                    "base_url": "https://data.capitol.hawaii.gov/hrscurrent/",
                    "workers": 4,
                },
            ),
        ],
    ),
    "ia": (
        1,
        "Iowa Employment Security Law, Iowa Code chapter 96",
        [
            (
                "chapter-96",
                "iowa-code",
                "https://www.legis.iowa.gov/law/iowaCode?year=2026",
                {"only_chapter": "96", "source_year": 2026, "workers": 4},
            ),
        ],
    ),
    "id": (
        1,
        "Idaho Employment Security Law, Idaho Code title 72 chapter 13",
        [
            (
                "title-72-chapter-13",
                "idaho-statutes",
                "https://legislature.idaho.gov/statutesrules/idstat/Title72/T72CH13/",
                {
                    "only_title": "72",
                    "only_chapter": "13",
                    "request_delay_seconds": 0.2,
                    "request_attempts": 10,
                    "workers": 1,
                },
            ),
        ],
    ),
    "il": (
        1,
        "Unemployment Insurance Act, 820 ILCS 405",
        [
            (
                "chapter-820-act-405",
                "illinois-ilcs",
                "https://www.ilga.gov/ftp/ILCS/",
                {"only_title": "820", "only_act": "405", "workers": 4},
            ),
        ],
    ),
    "me": (
        1,
        "Maine Employment Security Law, 26 M.R.S. chapter 13",
        [
            (
                "title-26-chapter-13",
                "maine-revised-statutes",
                "https://legislature.maine.gov/statutes/26/title26ch13sec0.html",
                {"only_title": "26", "only_chapter": "13", "workers": 4},
            ),
        ],
    ),
    "md": (
        1,
        "Maryland Unemployment Insurance Law, Labor and Employment Article title 8",
        [
            (
                "article-gle",
                "maryland-code",
                "https://mgaleg.maryland.gov/mgawebsite/Laws/Statutes",
                {
                    "only_article": "gle",
                    "enactments": False,
                    "include_constitution": False,
                    "workers": 4,
                },
            ),
        ],
    ),
    "mi": (
        1,
        "Michigan Employment Security Act, MCL 421.1 et seq.",
        [
            (
                "chapter-421",
                "michigan-compiled-laws",
                "https://www.legislature.mi.gov/documents/mcl/",
                {
                    "only_title": "421",
                    "request_delay_seconds": 0.1,
                    "timeout_seconds": 120,
                    "workers": 4,
                },
            ),
        ],
    ),
    "mn": (
        1,
        "Minnesota Unemployment Insurance Law, Minn. Stat. chapter 268",
        [
            (
                "chapter-268",
                "minnesota-statutes",
                "https://www.revisor.mn.gov/statutes/cite/268",
                {"only_title": "268", "workers": 4},
            ),
        ],
    ),
    "mo": (
        1,
        "Missouri Employment Security Law, RSMo chapter 288",
        [
            (
                "chapter-288",
                "missouri-revised-statutes",
                "https://revisor.mo.gov/main/OneChapter.aspx?chapter=288",
                {
                    "only_title": "288",
                    "base_url": "https://revisor.mo.gov/main/",
                    "workers": 1,
                    "request_delay_seconds": 0.25,
                    "timeout_seconds": 90,
                },
            ),
        ],
    ),
    "ne": (
        1,
        "Nebraska Employment Security Law, Neb. Rev. Stat. 48-601 to 48-683",
        [
            (
                "chapter-48",
                "nebraska-revised-statutes",
                "https://nebraskalegislature.gov/laws/browse-chapters.php?chapter=48",
                {"only_title": "48"},
            ),
        ],
    ),
    "or": (
        1,
        "Oregon unemployment insurance law, ORS chapter 657",
        [
            (
                "chapter-657",
                "oregon-ors",
                "https://www.oregonlegislature.gov/bills_laws/ors/ors657.html",
                {"only_chapter": "657", "source_year": 2025, "workers": 2},
            ),
        ],
    ),
    "ri": (
        1,
        "Rhode Island Employment Security Act, R.I. Gen. Laws chapters 28-42 and 28-44",
        [
            (
                "chapter-28-42",
                "rhode-island-general-laws",
                "https://webserver.rilegislature.gov/Statutes/TITLE28/28-42/INDEX.htm",
                {"only_title": "28", "only_chapter": "28-42", "workers": 1},
            ),
            (
                "chapter-28-44",
                "rhode-island-general-laws",
                "https://webserver.rilegislature.gov/Statutes/TITLE28/28-44/INDEX.htm",
                {"only_title": "28", "only_chapter": "28-44", "workers": 1},
            ),
        ],
    ),
    "sc": (
        1,
        "South Carolina Employment and Workforce Law, S.C. Code title 41 chapters 27 and 35",
        [
            (
                "title-41-chapter-27",
                "south-carolina-code",
                "https://www.scstatehouse.gov/code/t41c027.php",
                {"only_title": "41", "only_chapter": "27", "request_delay_seconds": 0.3},
            ),
            (
                "title-41-chapter-35",
                "south-carolina-code",
                "https://www.scstatehouse.gov/code/t41c035.php",
                {"only_title": "41", "only_chapter": "35", "request_delay_seconds": 0.3},
            ),
        ],
    ),
    "sd": (
        1,
        "South Dakota Reemployment Assistance law, SDCL title 61",
        [
            (
                "title-61",
                "south-dakota-codified-laws",
                "https://sdlegislature.gov/Statutes/61",
                {
                    "only_title": "61",
                    "base_url": "https://sdlegislature.gov",
                    "request_delay_seconds": 0.25,
                    "request_attempts": 6,
                    "workers": 1,
                },
            ),
        ],
    ),
    "tx": (
        1,
        "Texas Unemployment Compensation Act, Labor Code title 4 subtitle A",
        [
            (
                "code-la",
                "texas-tcas",
                "https://statutes.capitol.texas.gov/",
                {"only_title": "la", "workers": 4},
            ),
        ],
    ),
    "wa": (
        1,
        "Employment Security Act, RCW title 50 (chapters 50.04 and 50.20)",
        [
            (
                "chapter-50-04",
                "washington-rcw",
                "https://app.leg.wa.gov/RCW/default.aspx?cite=50.04",
                {"only_title": "50.04", "workers": 4},
            ),
            (
                "chapter-50-20",
                "washington-rcw",
                "https://app.leg.wa.gov/RCW/default.aspx?cite=50.20",
                {"only_title": "50.20", "workers": 4},
            ),
        ],
    ),
    "wi": (
        1,
        "Wisconsin unemployment insurance law, Wis. Stat. chapter 108",
        [
            (
                "chapter-108",
                "wisconsin-statutes",
                "https://docs.legis.wisconsin.gov/statutes/prefaces/toc",
                {
                    "only_title": "108",
                    "base_url": "https://docs.legis.wisconsin.gov",
                    "include_subunits": True,
                    "request_delay_seconds": 0.05,
                    "timeout_seconds": 90,
                    "workers": 2,
                },
            ),
        ],
    ),
}


def manifest(st: str) -> dict:
    _wave, law, sources = STATES[st]
    return {
        "version": VERSION,
        "sources": [
            {
                "source_id": f"us-{st}-ui-benefits-{suffix}",
                "jurisdiction": f"us-{st}",
                "document_class": "statute",
                "adapter": adapter,
                "source_url": url,
                "version": VERSION,
                "options": {"source_as_of": AS_OF, "expression_date": AS_OF, **options},
                "metadata": {"program": "Unemployment insurance", "law": law, "run_note": RUN_NOTE},
            }
            for suffix, adapter, url, options in sources
        ],
    }


def main() -> None:
    for st in sorted(STATES):
        path = REPO / "manifests" / f"us-{st}-ui-benefits-statute.yaml"
        header = (
            f"# Unemployment insurance benefits, {STATES[st][1]}.\n"
            f"# Written by scripts/build_ui_benefits_manifests.py; run note {RUN_NOTE}.\n"
        )
        path.write_text(
            header + yaml.safe_dump(manifest(st), sort_keys=False, width=110), encoding="utf-8"
        )
        print(path.relative_to(REPO))


if __name__ == "__main__":
    main()
