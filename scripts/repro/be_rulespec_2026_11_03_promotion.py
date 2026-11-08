#!/usr/bin/env python3
"""Build the 2026-11-03 Belgian statute source promotion and its release selector.

``be-rulespec-2026-08-29`` selects ``be/statute/2026-08-23-be-rulespec-source-promotion``,
and that scope holds 67 pages of the Code des impots sur les revenus 1992 (CIR 92) for income
2025. An encoding plan for rulespec-be's joint personal income tax pipeline asked for 16 more
pages that no release carries. This script promotes them, with the 20 pages that finish every
article on them, from the full export, ``be/statute/2026-06-30-be-income-tax-consolidated``,
the way axiom-corpus#626 promoted the 08-23 pages.

``promote`` (offline) writes ``be/statute/2026-11-03-be-rulespec-source-promotion``:

- every 08-23 row, changed only in ``version`` and ``source_path``;
- one row for each page in ``ADDED_PAGES``, copied from the full export with ``version``,
  ``expression_date`` and ``source_path`` set;
- the 08-23 inputs, byte for byte, except the CIR input: it takes the full export's raw line
  for each added page and keeps the full export's line order;
- the inventory and coverage those rows and inputs imply.

``release`` writes ``be-rulespec-2026-11-03``: ``be-rulespec-2026-08-29`` with its
``be/statute`` scope moved to the new version.

    uv run --extra dev python scripts/repro/be_rulespec_2026_11_03_promotion.py promote --base data/corpus
    uv run --extra dev python scripts/repro/be_rulespec_2026_11_03_promotion.py release
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from axiom_corpus.corpus.coverage import compare_provision_coverage
from axiom_corpus.corpus.models import ProvisionRecord

REPO_ROOT = Path(__file__).resolve().parents[2]
JURISDICTION = "be"
DOCUMENT_CLASS = "statute"
OLD_VERSION = "2026-08-23-be-rulespec-source-promotion"
NEW_VERSION = "2026-11-03-be-rulespec-source-promotion"
FULL_VERSION = "2026-06-30-be-income-tax-consolidated"
EXPRESSION_DATE = "2026-06-30"
BASE_RELEASE = "be-rulespec-2026-08-29"
RELEASE = "be-rulespec-2026-11-03"
CIR_PARENT = "be/statute/fisconetplus/cir92/revenus-2025"
# Named for the first 12 hex digits of the full export's provisions sha256.
CIR_INPUT_NAME = "axiom-corpus-9be12db7c693-2026-06-30-be-income-tax-consolidated.selected.jsonl"

# The pages the joint personal income tax plan asked for.
REQUESTED_PAGES = frozenset(
    {75, 77, 80, 91, 92, 93, 94, 98, 157, 158, 159, 175, 176, 191, 273, 274}
)
# The other pages of every article with text on a requested page, and of every article with
# text on those pages in turn: article_closure(REQUESTED_PAGES) less REQUESTED_PAGES.
COMPLETING_PAGES = frozenset(
    {74, 76, 78, 79, 81, 82, 97, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 155, 156}
)
ADDED_PAGES = REQUESTED_PAGES | COMPLETING_PAGES

DESCRIPTION = (
    f"Successor to {BASE_RELEASE}: it reuses that release's 12 other scopes and moves be/statute "
    f"to {NEW_VERSION}. That scope keeps every row of {OLD_VERSION} and adds 36 pages of the CIR 92 "
    "export for income 2025: 16 pages for rulespec-be's joint personal income tax pipeline and the "
    "20 pages that finish every article on them. The release then holds the whole text of every "
    "article on the added pages: articles 24 to 39 except 32/1 and 32/2, 75 to 80, 103 to 111, "
    "143 to 145 and 171. It is a publish-only pin release for rulespec-be; do not activate it."
)

ARTICLE_HEADING = re.compile(r"Articles? (?P<label>[0-9][^,]{0,40}?), CIR 92 \(revenus 2025\)")
# One section label, such as "C. - Profits", "Section 4/1.- Détermination de l'impôt étranger",
# "Sous-section 2vicies semel. - Réduction pour primes" or "1°bis. - Stage en entreprise": a
# marker, a period, a dash, then a title that holds no period, colon or semicolon. In the table
# of contents, dot leaders and a page number follow the title.
_SECTION_LABEL_ENTRY = (
    r"(?:(?:TITRE|CHAPITRE|Section|Sous-section) [0-9]+(?:/[0-9]+)?[a-z]*(?: semel)?"
    r"|[A-Z]|[0-9]+°[a-z]+)"
    r"\.\s*-\s+[^.;:]*?(?:\s*\.{3,}\s*[0-9]+)?"
)
# What a page can carry above its first heading when the article before it ended on the
# previous page: nothing, or a run of "(...)" and section labels, as in "C. - (...)". The
# export's bodies hold no line breaks, so labels and the text around them run together. A
# sentence of article text after a label holds a period, colon or semicolon, which no title
# holds, so that text does not match.
SECTION_LABEL = re.compile(rf"(?:\s*(?:\(\.\.\.\)|{_SECTION_LABEL_ENTRY}))*\s*")


def page_citation(page: int) -> str:
    return f"{CIR_PARENT}/page-{page}"


def _inputs_prefix(version: str) -> str:
    return f"sources/{JURISDICTION}/{DOCUMENT_CLASS}/{version}/inputs/"


def _provisions_path(base: Path, version: str) -> Path:
    return base / "provisions" / JURISDICTION / DOCUMENT_CLASS / f"{version}.jsonl"


def _inventory_path(base: Path, version: str) -> Path:
    return base / "inventory" / JURISDICTION / DOCUMENT_CLASS / f"{version}.json"


def _coverage_path(base: Path, version: str) -> Path:
    return base / "coverage" / JURISDICTION / DOCUMENT_CLASS / f"{version}.json"


def _inputs_dir(base: Path, version: str) -> Path:
    return base / _inputs_prefix(version)


def row_line(row: Mapping[str, Any]) -> str:
    """One provisions line in the encoding the 07-10 and 08-23 promotions use."""

    return json.dumps(row, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _citation(line: bytes) -> str:
    return str(json.loads(line)["citation_path"])


def promote_rows(
    old_rows: Iterable[Mapping[str, Any]],
    full_rows: Mapping[str, Mapping[str, Any]],
    pages: Iterable[int],
) -> list[dict[str, Any]]:
    """Old rows moved to the new version plus one full-export row per page, sorted."""

    old_prefix, new_prefix = _inputs_prefix(OLD_VERSION), _inputs_prefix(NEW_VERSION)
    rows: dict[str, dict[str, Any]] = {}
    for old in old_rows:
        row = dict(old)
        source_path = str(row["source_path"])
        if not source_path.startswith(old_prefix):
            raise ValueError(
                f"{row['citation_path']}: source_path {source_path!r} is outside {old_prefix}"
            )
        row["version"] = NEW_VERSION
        row["source_path"] = new_prefix + source_path[len(old_prefix) :]
        if row["citation_path"] in rows:
            raise ValueError(f"duplicate citation path {row['citation_path']}")
        rows[str(row["citation_path"])] = row
    parent = rows.get(CIR_PARENT)
    if parent is None:
        raise ValueError(f"the old promotion has no {CIR_PARENT} row")
    for page in sorted(set(pages)):
        citation = page_citation(page)
        if citation in rows:
            raise ValueError(f"{citation} is already in {OLD_VERSION}")
        source = full_rows.get(citation)
        if source is None:
            raise ValueError(f"{citation} is not in {FULL_VERSION}")
        if source.get("parent_citation_path") != CIR_PARENT or str(source.get("parent_id")) != str(
            parent["id"]
        ):
            raise ValueError(f"{citation} does not hang from the promotion's {CIR_PARENT} row")
        row = dict(source)
        row["version"] = NEW_VERSION
        row["expression_date"] = EXPRESSION_DATE
        row["source_path"] = new_prefix + CIR_INPUT_NAME
        rows[citation] = row
    return [rows[citation] for citation in sorted(rows)]


def select_input_lines(
    full_lines: Iterable[bytes], old_input_lines: Iterable[bytes], pages: Iterable[int]
) -> list[bytes]:
    """The full export's raw lines for the old input's citations and the pages, in file order."""

    full_lines = list(full_lines)
    by_citation: dict[str, bytes] = {}
    for line in full_lines:
        citation = _citation(line)
        if citation in by_citation:
            raise ValueError(f"{FULL_VERSION} repeats {citation}")
        by_citation[citation] = line
    old = {}
    for line in old_input_lines:
        citation = _citation(line)
        if by_citation.get(citation) != line:
            raise ValueError(f"the old CIR input line for {citation} is not the full export's line")
        old[citation] = line
    added = {page_citation(page) for page in pages}
    if added & old.keys():
        raise ValueError(f"the old CIR input already holds {sorted(added & old.keys())}")
    if not added <= by_citation.keys():
        raise ValueError(f"{FULL_VERSION} lacks {sorted(added - by_citation.keys())}")
    selected = old.keys() | added
    return [line for line in full_lines if _citation(line) in selected]


def inventory_items(
    rows: Iterable[Mapping[str, Any]], input_digests: Mapping[str, str]
) -> list[dict[str, Any]]:
    """One inventory item per row, naming its input file and that file's sha256.

    An item carries ``metadata`` only when its row does, as in the 08-23 inventory.
    """

    items = []
    for row in rows:
        name = str(row["source_path"]).rsplit("/", 1)[-1]
        item = {
            "citation_path": row["citation_path"],
            "sha256": input_digests[name],
            "source_format": row["source_format"],
            "source_path": row["source_path"],
            "source_url": row["source_url"],
        }
        if "metadata" in row:
            item["metadata"] = row["metadata"]
        items.append(item)
    return items


def _read_lines(path: Path) -> list[bytes]:
    return [line for line in path.read_bytes().splitlines() if line]


def _write(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def build_promotion(*, base: Path, output_base: Path | None = None) -> list[Path]:
    """Write the new scope's inputs, provisions, inventory and coverage under output_base."""

    output_base = output_base or base
    old_lines = _read_lines(_provisions_path(base, OLD_VERSION))
    full_lines = _read_lines(_provisions_path(base, FULL_VERSION))
    old_rows = [json.loads(line) for line in old_lines]
    if [row_line(row).encode() for row in old_rows] != old_lines:
        raise ValueError(f"{OLD_VERSION} provisions are not in the promotion encoding")
    full_rows = {_citation(line): json.loads(line) for line in full_lines}
    rows = promote_rows(old_rows, full_rows, ADDED_PAGES)

    written = []
    digests = {}
    old_inputs = _inputs_dir(base, OLD_VERSION)
    for source in sorted(old_inputs.iterdir()):
        if source.name == CIR_INPUT_NAME:
            lines = select_input_lines(full_lines, _read_lines(source), ADDED_PAGES)
            data = b"".join(line + b"\n" for line in lines)
        else:
            data = source.read_bytes()
        digests[source.name] = hashlib.sha256(data).hexdigest()
        written.append(_write(_inputs_dir(output_base, NEW_VERSION) / source.name, data))
    if CIR_INPUT_NAME not in digests:
        raise ValueError(f"{OLD_VERSION} has no {CIR_INPUT_NAME}")

    for row in rows:
        ProvisionRecord.from_mapping(row)
    provisions = "".join(row_line(row) + "\n" for row in rows).encode()
    written.append(_write(_provisions_path(output_base, NEW_VERSION), provisions))

    items = inventory_items(rows, digests)
    inventory = json.dumps({"items": items}, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    written.append(_write(_inventory_path(output_base, NEW_VERSION), inventory.encode()))

    report = compare_provision_coverage(
        [_Cited(item["citation_path"]) for item in items],
        [_Cited(row["citation_path"]) for row in rows],
        JURISDICTION,
        DOCUMENT_CLASS,
        NEW_VERSION,
    )
    if not report.complete:
        raise ValueError(f"coverage is incomplete: {report.to_mapping()}")
    coverage = json.dumps(report.to_mapping(), indent=2, sort_keys=True) + "\n"
    written.append(_write(_coverage_path(output_base, NEW_VERSION), coverage.encode()))
    return written


class _Cited:
    def __init__(self, citation_path: str) -> None:
        self.citation_path = citation_path


def article_spans(bodies: Mapping[int, str]) -> list[tuple[str, int, int]]:
    """Each article heading's label with the first and last page of its text."""

    headings = [
        (page, match.start(), match.group("label"))
        for page in sorted(bodies)
        for match in ARTICLE_HEADING.finditer(bodies[page])
    ]
    spans = []
    for index, (page, _, label) in enumerate(headings):
        if index + 1 == len(headings):
            last = max(bodies)
        else:
            next_page, next_offset, _ = headings[index + 1]
            above = bodies[next_page][:next_offset]
            if next_page > page and SECTION_LABEL.fullmatch(above):
                last = next_page - 1
            else:
                last = next_page
        spans.append((label, page, last))
    return spans


def article_closure(
    bodies: Mapping[int, str], pages: Iterable[int], present: Iterable[int] = ()
) -> frozenset[int]:
    """The pages plus every page of each article with text on them, repeated to a fixed point.

    Pages in ``present`` already sit in the scope: they never join the result, but an article
    that reaches one of them still pulls in its other pages.
    """

    spans = [range(first, last + 1) for _, first, last in article_spans(bodies)]
    present = frozenset(present)
    result = set(pages) - present
    while True:
        more = {
            page
            for span in spans
            if any(page in result for page in span)
            for page in span
            if page not in present
        }
        if more <= result:
            return frozenset(result)
        result |= more


def _scope_key(scope: Mapping[str, str]) -> tuple[str, str, str]:
    return (scope["jurisdiction"], scope["document_class"], scope["version"])


def build_release(
    *, release_dir: Path = REPO_ROOT / "manifests/releases", output_dir: Path | None = None
) -> Path:
    """Move the base release's be/statute scope to the new promotion and change nothing else."""

    payload = json.loads((release_dir / f"{BASE_RELEASE}.json").read_text(encoding="utf-8"))
    old_scope = {
        "document_class": DOCUMENT_CLASS,
        "jurisdiction": JURISDICTION,
        "version": OLD_VERSION,
    }
    matches = [
        index
        for index, scope in enumerate(payload["scopes"])
        if (scope["jurisdiction"], scope["document_class"]) == (JURISDICTION, DOCUMENT_CLASS)
    ]
    if len(matches) != 1 or payload["scopes"][matches[0]] != old_scope:
        raise ValueError(f"{BASE_RELEASE} must select be/statute exactly once, at {OLD_VERSION}")
    scopes = [dict(scope) for scope in payload["scopes"]]
    scopes[matches[0]] = {**old_scope, "version": NEW_VERSION}
    if len({_scope_key(scope) for scope in scopes}) != len(scopes):
        raise ValueError("release selector would contain duplicate scopes")
    payload.update({"name": RELEASE, "description": DESCRIPTION, "scopes": scopes})
    output = (output_dir or release_dir) / f"{RELEASE}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    promote = commands.add_parser("promote", help="write the new be/statute scope")
    promote.add_argument("--base", type=Path, default=REPO_ROOT / "data/corpus")
    promote.add_argument("--output-base", type=Path)
    release = commands.add_parser("release", help="write the release selector")
    release.add_argument("--release-dir", type=Path, default=REPO_ROOT / "manifests/releases")
    release.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    if args.command == "promote":
        for path in build_promotion(base=args.base, output_base=args.output_base):
            print(path)
    else:
        print(build_release(release_dir=args.release_dir, output_dir=args.output_dir))


if __name__ == "__main__":
    main()
