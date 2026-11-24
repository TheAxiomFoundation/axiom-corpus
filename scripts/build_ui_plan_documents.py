#!/usr/bin/env python3
"""Write the unemployment insurance plan documents from the roadmap's UI scope audit.

The audit (axiom-roadmap-dashboard, ``tools/encoding-forecast/ui-scope-audit.json``)
lists, for the federal layer and each state, the statutes, regulations and agency
documents that decide the amount of and the basic eligibility for regular state
unemployment benefits. No person reviewed it, so a citation is a lead: this script
keeps a citation's corpus path only when the path is in a provisions file under
``--base`` and holds text at or under it. A document with no such path keeps its
official address alone, and the bundle joins it by that address or lists it as not
in the corpus.

Rows are written only for the jurisdictions in ``--jurisdictions``: the ones an
ingest run has taken, so the bundle does not list documents nobody has read.

Usage::

    python scripts/build_ui_plan_documents.py --audit <ui-scope-audit.json> \\
        --audit-source <repo>@<commit>:<path> --base data/corpus --jurisdictions us us-ak ...
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit

REPO = Path(__file__).resolve().parent.parent
OUTPUT = REPO / "sources/plans/ui-scope-audit-documents.json"
CLASSES = {"statute": "statute", "regulation": "regulation"}
COMPOUND = re.compile(r"\d+[A-Za-z]?(?:[.:\-–]\d+[A-Za-z]?)+(?:-[A-Z]\b)?")
SINGLE = re.compile(r"§+\s*(\d+[A-Za-z]?(?:-[A-Z])?)\b|/(\d+[A-Za-z]?)\b")
USC = re.compile(r"(\d+) U\.S\.C\. §+\s*(\d+[A-Za-z]?)(?:-(\d+))?")
CFR = re.compile(r"(\d+) C\.F\.R\. part (\d+)")


# Citations whose corpus path does not carry the cited number in its last segment.
OVERRIDES = {
    ("us-ak", "8 AAC 85"): ["us-ak/regulation/aac/8/85"],
    ("us-or", "OAR chapter 471, division 30"): ["us-or/regulation/chapter-471/division-30"],
    ("us-md", "COMAR 09.32.02"): ["us-md/regulation/title-09/subtitle-32/chapter-02"],
    ("us-il", "56 Ill. Adm. Code Part 2920"): [
        "us-il/regulation/title-056/chapter-iv/subchapter-g/part-2920"
    ],
    ("us-il", "56 Ill. Adm. Code Part 2865"): [
        "us-il/regulation/title-056/chapter-iv/subchapter-f/part-2865"
    ],
}
# A state code a bare section number belongs to.
CODE_PREFIX = {"us-ca": "us-ca/statute/uic/"}


def address(url: str) -> str:
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").removeprefix("www.")
    return (host + parts.path.rstrip("/") + ("?" + parts.query if parts.query else "")).lower()


def norm(text: str) -> str:
    return re.sub(r"[^0-9a-z]+", "-", text.lower()).strip("-")


def tokens(citation: str) -> list[str]:
    """The section numbers a citation names, without parenthetical notes."""
    text = re.sub(r"\(.*?\)", "", citation)
    found = [m.group(0) for m in COMPOUND.finditer(text)]
    return found or [m.group(1) or m.group(2) for m in SINGLE.finditer(text)]


def load_rows(base: Path, jurisdiction: str) -> dict[str, dict]:
    """citation_path -> {"text": chars at the path, "parent": parent path} over every
    provisions file of the jurisdiction under the base."""
    rows: dict[str, dict] = {}
    for path in sorted((base / "provisions" / jurisdiction).glob("*/*.jsonl")):
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                row = json.loads(line)
                held = rows.setdefault(
                    row["citation_path"], {"text": 0, "parent": None, "url": None}
                )
                held["url"] = held["url"] or row.get("source_url")
                held["text"] = max(held["text"], len((row.get("body") or "").strip()))
                held["parent"] = held["parent"] or row.get("parent_citation_path")
    return rows


def with_text(rows: dict[str, dict]) -> set[str]:
    """Paths that hold text themselves or through a descendant (by path or by parent)."""
    out = set()
    for path, row in rows.items():
        if not row["text"]:
            continue
        seen = set()
        while path and path not in seen:
            seen.add(path)
            out.add(path)
            parts = path.split("/")
            for depth in range(3, len(parts)):
                out.add("/".join(parts[:depth]))
            path = (rows.get(path) or {}).get("parent")
    return out


def paths_of(
    document: dict, jurisdiction: str, rows: dict[str, dict], readable: set[str]
) -> list[str]:
    citation = document["citation"]
    for (state, start), paths in OVERRIDES.items():
        if state == jurisdiction and citation.startswith(start):
            return [p for p in paths if p in readable]
    # The document whose rows name the audit's address: its shortest path with text.
    wanted_address = address(document["official_url"])
    by_address = sorted(
        (
            p
            for p, row in rows.items()
            if row["url"] and address(row["url"]) == wanted_address and p in readable
        ),
        key=lambda p: (len(p.split("/")), p),
    )
    document_class = CLASSES.get(document["class"])
    if not document_class:
        return by_address[:1]
    prefix = f"{jurisdiction}/{document_class}/"
    usc, cfr = USC.search(citation), CFR.search(citation)
    if jurisdiction == "us" and usc:
        title, first, last = usc.group(1), usc.group(2), usc.group(3)
        if last and first.isdigit():
            candidates = [f"us/statute/{title}/{n}" for n in range(int(first), int(last) + 1)]
        else:
            candidates = [f"us/statute/{title}/{first}"]
        return [p for p in candidates if p in readable]
    if jurisdiction == "us" and cfr:
        path = f"us/regulation/{cfr.group(1)}/{cfr.group(2)}"
        return [path] if path in readable else []
    found: list[str] = []
    code = CODE_PREFIX.get(jurisdiction)
    if code and document_class == "statute":
        found = [code + t for t in tokens(citation) if code + t in readable]
        if found:
            return found
    for token in tokens(citation):
        wanted = norm(token)
        match = sorted(
            p
            for p in rows
            if p.startswith(prefix)
            and p in readable
            and (norm(p.split("/")[-1]) == wanted or norm(p[len(prefix) :]) == wanted)
            and ("-" in wanted or len(p.split("/")) > 3)
        )
        # A bare section number: the path whose earlier segments the citation also names
        # (820 ILCS 405/402 is .../820/405/402), else the only path that ends in it.
        if "-" not in wanted and len(match) > 1:
            words = set(re.findall(r"[0-9a-z]+", citation.lower()))
            match = [p for p in match if set(p[len(prefix) :].lower().split("/")[:-1]) <= words]
        if match and ("-" in wanted or len(match) == 1) and match[0] not in found:
            found.append(match[0])
    return found or by_address[:1]


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--audit-source", required=True)
    parser.add_argument("--base", type=Path, default=REPO / "data/corpus")
    parser.add_argument("--jurisdictions", nargs="+", required=True)
    args = parser.parse_args()

    audit = json.loads(args.audit.read_text(encoding="utf-8"))
    documents: list[dict] = []
    unresolved: dict[str, list[str]] = defaultdict(list)
    for entry in audit["jurisdictions"]:
        jurisdiction = entry["jurisdiction"]
        if jurisdiction not in args.jurisdictions:
            continue
        rows = load_rows(args.base, jurisdiction)
        readable = with_text(rows)
        for document in entry["documents"]:
            paths = paths_of(document, jurisdiction, rows, readable)
            if document["class"] in CLASSES and not paths:
                unresolved[jurisdiction].append(document["citation"])
            base_row = {
                "jurisdiction": jurisdiction.upper(),
                "programs": ["ui"],
                "title": f"{document['citation']}: {document['title']}",
                "document_class": document["class"],
                "urls": [document["official_url"]],
            }
            if not paths:
                documents.append(
                    {
                        "id": f"{jurisdiction} {document['citation']}",
                        **base_row,
                        "citation_paths": [],
                    }
                )
            # A document with a path is named by the path alone: its address can be a
            # code's landing page, which says nothing about the section.
            for path in paths:
                suffix = f" [{path.rsplit('/', 1)[-1]}]" if len(paths) > 1 else ""
                documents.append(
                    {
                        "id": f"{jurisdiction} {document['citation']}{suffix}",
                        **base_row,
                        "urls": [],
                        "official_url": document["official_url"],
                        "citation_paths": [path],
                    }
                )
    ids = [d["id"] for d in documents]
    repeated = sorted({i for i in ids if ids.count(i) > 1})
    for document in documents:
        if document["id"] in repeated:
            document["id"] = (
                f"{document['id']} ({(document['urls'] or [document.get('official_url')])[0]})"
            )
    payload = {
        "source": args.audit_source,
        "as_of": "2026-11-24",
        "status": "AUDIT, NOT REVIEWED BY A PERSON",
        "programs": ["ui"],
        "note": (
            "The UI scope audit's documents (amount of and basic eligibility for regular state unemployment "
            "benefits) for the jurisdictions an ingest run has taken. A citation path is kept only where a "
            "provisions file held it with text when scripts/build_ui_plan_documents.py ran; every other document "
            "is named by its official address."
        ),
        "jurisdictions": sorted(args.jurisdictions),
        "documents": documents,
    }
    OUTPUT.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    with_path = sum(1 for d in documents if d["citation_paths"])
    print(
        f"{len(documents)} documents, {with_path} with a corpus path, {len(documents) - with_path} by address"
    )
    for jurisdiction, citations in sorted(unresolved.items()):
        print(f"  {jurisdiction}: no path for {citations}")


if __name__ == "__main__":
    main()
