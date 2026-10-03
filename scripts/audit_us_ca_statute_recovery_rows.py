#!/usr/bin/env python3
"""Classify every row of ``us-ca/statute/2026-07-13-recovery`` against its retained page.

The July 2026 recovery batch (``scripts/recover_ingest_batch.py``) staged eleven
LegInfo ``codes_displaySection`` pages through the shared document-block
extractor instead of the ``california-code-sections`` adapter. Each page became a
``document`` root with two ``block`` children. This script re-reads each retained
page, types it (a ``single_law_section`` page or a ``selectFromMultiples`` version
picker), and gives every row one verdict:

* ``empty_document_root``: the ``document`` root, whose body is empty.
* ``leginfo_page_chrome``: exactly LegInfo's navigation menu followed by the
  page's own ``#breadcrumbs`` entries, none of it section text.
* ``picker_history_notes_only``: the history notes of the versions a
  ``selectFromMultiples`` page offers, with no section text.
* ``section_text_without_history``: the section text. With the history note
  appended it equals, whitespace-normalized, the adapter's default body of the
  same page.
* ``unclassified``: none of the above.

For each page it also reads the rows that the two reference scopes, the
2026-09-14 R&TC income tax chapter and the 2026-06-25 CalWORKs sections, carry at
the page's section path (``us-ca/statute/<law>/<section>``). An R&TC row's body is
compared with the adapter's body of the recovery page. For WIC 11450 it records
which version the picker offers the CalWORKs row holds. The reference scopes are
named, not discovered, so later successors of them do not change the audit. It
writes only the audit JSON and changes no corpus artifact.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, Tag

from axiom_corpus.corpus.states import (
    _california_html_history,
    _california_html_section_body,
    _clean_text,
)

JURISDICTION = "us-ca"
DOCUMENT_CLASS = "statute"
VERSION = "2026-07-13-recovery"
SCOPE = f"{JURISDICTION}/{DOCUMENT_CLASS}/{VERSION}"
MANIFEST = Path(".axiom/ingest-manifests") / JURISDICTION / DOCUMENT_CLASS / f"{VERSION}.json"
DEFAULT_OUTPUT = Path("docs/ingest-runs/2026-09-25-us-ca-statute-recovery-audit.json")
REFERENCE_CARRIERS = (
    "2026-06-25-ca-wic-calworks-us-ca-sections-wic-11450-wic-11450.12-wic-11451.5-wic-11452-"
    "wic-11452.018",
    "2026-09-14-income-tax-chapter-us-ca-sections-4e26e6efabc3f0c7",
)

# LegInfo's page header as the shared block extractor flattens it: this menu,
# then the entries of the page's ``#breadcrumbs`` list (``California Law >>``,
# ``>>`` and the page title, e.g. ``Code Section``).
LEGINFO_MENU = (
    "skip to content",
    "home",
    "accessibility",
    "FAQ",
    "feedback",
    "sitemap",
    "login",
    "x",
    "Home",
    "Bill Information",
    "California Law",
    "Publications",
    "Other Resources",
    "My Subscriptions",
    "My Favorites",
)
NO_TEXT_VERDICTS = ("empty_document_root", "leginfo_page_chrome", "picker_history_notes_only")
_URL_SECTION = re.compile(r"lawCode=([A-Z]+)&sectionNum=([0-9.]+?)\.?$")
_ONCLICK_PARAM = re.compile(r"'([^']+)':'([^']*)'")


def _normalized(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _section_path(url: str) -> str:
    match = _URL_SECTION.search(url)
    if match is None:
        raise ValueError(f"not a LegInfo codes_displaySection URL: {url}")
    law_code, section = match.groups()
    return f"{JURISDICTION}/{DOCUMENT_CLASS}/{law_code.lower()}/{section}"


def _picker_versions(form: Tag) -> list[dict[str, str]]:
    """Versions a LegInfo ``selectFromMultiples`` form offers, in page order."""
    versions = []
    for link in form.find_all("a", onclick=re.compile("op_statues")):
        params = dict(_ONCLICK_PARAM.findall(str(link.get("onclick"))))
        row = link.find_parent("tr") or link.find_parent("div") or link
        versions.append(
            {
                "history": _clean_text(row.get_text(" ", strip=True)),
                "op_statues": params["op_statues"],
                "op_chapter": params["op_chapter"],
                "op_section": params["op_section"],
            }
        )
    return versions


def audit_page(html: bytes) -> dict[str, Any]:
    """Type one retained LegInfo page and extract what the adapter would."""
    soup = BeautifulSoup(html, "html.parser")
    title = soup.find("title")
    section_node = soup.find(id="single_law_section")
    picker = soup.find("form", id="selectFromMultiples")
    page: dict[str, Any] = {
        "title": _clean_text(title.get_text(" ", strip=True)) if isinstance(title, Tag) else None
    }
    # The page as a reader sees it outside the statute container (the section
    # div or the version-picker form): header, menus, footer.
    outside = BeautifulSoup(html, "html.parser")
    for container in (
        outside.find(id="single_law_section"),
        outside.find("form", id="selectFromMultiples"),
    ):
        if isinstance(container, Tag):
            container.decompose()
    for tag in outside.find_all(["script", "style", "title"]):
        tag.decompose()
    page["outside_text"] = _normalized(outside.get_text(" ", strip=True))
    breadcrumbs = soup.find(id="breadcrumbs")
    page["breadcrumbs"] = (
        [_normalized(item.get_text(" ", strip=True)) for item in breadcrumbs.find_all("li")]
        if isinstance(breadcrumbs, Tag)
        else []
    )
    if isinstance(section_node, Tag):
        page["page_type"] = "single_law_section"
        page["adapter_body"] = _california_html_section_body(section_node)
        page["history"] = _california_html_history(section_node)
        page["picker_versions"] = []
    elif isinstance(picker, Tag):
        page["page_type"] = "select_from_multiples"
        page["adapter_body"] = None
        page["history"] = None
        page["picker_versions"] = _picker_versions(picker)
    else:
        page["page_type"] = "other"
        page["adapter_body"] = None
        page["history"] = None
        page["picker_versions"] = []
    return page


def _opens(history: str, prefix: str) -> bool:
    """Whether ``history`` starts with ``prefix`` as a whole clause."""
    return history.startswith(prefix) and history[len(prefix) : len(prefix) + 1] in ("", " ", ")")


def classify_row(row: dict[str, Any], page: dict[str, Any]) -> str:
    body = row.get("body") or ""
    if row.get("kind") == "document" and not body.strip():
        return "empty_document_root"
    lines = [_normalized(line) for line in body.split("\n") if line.strip()]
    section_lines = {_normalized(line) for line in (page["adapter_body"] or "").split("\n")}
    if (
        page["breadcrumbs"]
        and lines == [*LEGINFO_MENU, *page["breadcrumbs"]]
        and not section_lines.intersection(lines)
        and all(line in page["outside_text"] for line in LEGINFO_MENU)
    ):
        return "leginfo_page_chrome"
    if (
        page["page_type"] == "select_from_multiples"
        and page["picker_versions"]
        and body.strip()
        and _normalized(body)
        == _normalized(" ".join(version["history"] for version in page["picker_versions"]))
    ):
        return "picker_history_notes_only"
    if (
        page["page_type"] == "single_law_section"
        and page["history"]
        and _normalized(f"{body} {page['history']}") == _normalized(page["adapter_body"])
    ):
        return "section_text_without_history"
    return "unclassified"


def _scope_rows(base: Path, version: str) -> list[dict[str, Any]]:
    path = base / "provisions" / JURISDICTION / DOCUMENT_CLASS / f"{version}.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _carriers(base: Path, section_paths: set[str]) -> dict[str, list[tuple[str, dict[str, Any]]]]:
    """Each reference scope's row at each section path."""
    found: dict[str, list[tuple[str, dict[str, Any]]]] = {path: [] for path in section_paths}
    directory = base / "provisions" / JURISDICTION / DOCUMENT_CLASS
    for version in REFERENCE_CARRIERS:
        with (directory / f"{version}.jsonl").open(encoding="utf-8") as handle:
            for line in handle:
                if not any(f'"{target}"' in line for target in section_paths):
                    continue
                row = json.loads(line)
                if row["citation_path"] in found:
                    found[row["citation_path"]].append((version, row))
    return found


def audit(base: Path, repo_root: Path) -> dict[str, Any]:
    rows = _scope_rows(base, VERSION)
    manifest = json.loads((repo_root / MANIFEST).read_text(encoding="utf-8"))
    manifest_sha = {entry["path"]: entry["sha256"] for entry in manifest["applied_files"]}

    documents = sorted({row["source_id"] for row in rows})
    pages: dict[str, dict[str, Any]] = {}
    files = []
    for document_id in documents:
        root = next(r for r in rows if r["source_id"] == document_id and r["kind"] == "document")
        source_rel = root["source_path"]
        data = (base / source_rel).read_bytes()
        provenance_path = (
            base / "sources" / JURISDICTION / DOCUMENT_CLASS / VERSION / "provenance"
        ) / f"{document_id}.json"
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        page = audit_page(data)
        pages[document_id] = page
        sha = _sha256(data)
        files.append(
            {
                "document_id": document_id,
                "source_path": source_rel,
                "url": provenance["url"],
                "fetched_at": provenance["fetched_at"],
                "sha256": sha,
                "sha256_matches_provenance": sha == provenance["sha256"],
                "sha256_matches_signed_manifest": sha
                == manifest_sha.get(f"data/corpus/{source_rel}"),
                "page_type": page["page_type"],
                "title": page["title"],
                "section_path": _section_path(provenance["url"]),
                "recovery_citation_path": root["citation_path"],
                "history": page["history"],
                "picker_versions": page["picker_versions"],
            }
        )

    audited_rows = []
    for line_number, row in enumerate(rows, start=1):
        page = pages[row["source_id"]]
        body = row.get("body") or ""
        audited_rows.append(
            {
                "line": line_number,
                "citation_path": row["citation_path"],
                "kind": row["kind"],
                "citation_label": row.get("citation_label"),
                "heading": row.get("heading"),
                "source_id": row["source_id"],
                "body_chars": len(body),
                "body_sha256": _sha256(body.encode("utf-8")),
                "verdict": classify_row(row, page),
            }
        )

    by_section = {file["section_path"]: file for file in files}
    carriers = _carriers(base, set(by_section))
    carriage = []
    for section_path, file in sorted(by_section.items()):
        page = pages[file["document_id"]]
        entries = []
        for version, row in carriers[section_path]:
            history = (row.get("metadata") or {}).get("history")
            entry: dict[str, Any] = {
                "version": version,
                "citation_path": row["citation_path"],
                "kind": row["kind"],
                "source_as_of": row.get("source_as_of"),
                "body_chars": len(row.get("body") or ""),
                "history": history,
            }
            if page["page_type"] == "single_law_section":
                entry["body_equals_recovery_page_text"] = _normalized(
                    row.get("body")
                ) == _normalized(page["adapter_body"])
            else:
                # The carried version is the offered one whose picker history line,
                # less its closing parenthesis, opens the carrier's LegInfo history.
                entry["picker_version_carried"] = [
                    index
                    for index, offered in enumerate(page["picker_versions"])
                    if history and _opens(history, offered["history"].removesuffix(")"))
                ]
            entries.append(entry)
        carriage.append(
            {
                "section_path": section_path,
                "recovery_citation_path": file["recovery_citation_path"],
                "recovery_page_type": file["page_type"],
                "carriers": entries,
            }
        )

    verdicts = Counter(row["verdict"] for row in audited_rows)
    return {
        "scope": SCOPE,
        "generated_by": "scripts/audit_us_ca_statute_recovery_rows.py",
        "summary": {
            "rows": len(audited_rows),
            "files": len(files),
            "verdicts": dict(sorted(verdicts.items())),
            "page_types": dict(sorted(Counter(f["page_type"] for f in files).items())),
            "rows_without_section_text": sum(verdicts[verdict] for verdict in NO_TEXT_VERDICTS),
        },
        "files": files,
        "rows": audited_rows,
        "carriage": carriage,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--base", type=Path, default=Path("data/corpus"))
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = audit(args.base, args.repo_root)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(report["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
