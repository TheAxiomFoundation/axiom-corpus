#!/usr/bin/env python3
"""Classify every row of the July 2026 recovery scopes flagged after the us-ca audit.

``docs/ingest-runs/2026-09-25-us-ca-statute-recovery-audit.md`` (follow-up 5) lists
sibling scopes of ``us-ca/statute/2026-07-13-recovery`` whose rows hold page chrome,
empty roots or landing pages. This script re-reads every retained source file of
those scopes and gives every row one verdict:

* ``empty_document_root``: a ``document`` row whose body is empty.

A block row of an HTML page must equal, byte for byte, one block the shared
extractor makes of the retained page (``documents._extract_html_blocks``: the
text nodes of ``_main_content`` after its drop list, joined between headings).
Which verdict it gets depends on where that block's nodes sit:

* ``site_chrome``: every node lies outside the page's legal-text container (on a
  South Carolina chapter page, before the first ``SECTION`` marker).
* ``legal_text``: every node lies inside the container, outside its history note.
* ``history_note``: every node lies in the container's history note.
* ``history_note_and_site_chrome``: the history note (on some pages followed by a
  revisor's note inside the container), then page footer nodes.
* ``tables_from_other_sections``: on a chapter page, every node is a table printed
  under a section other than the one the row's path names.
* ``landing_page_text``: a block of a page that holds no legal text of its own (an
  index, table of contents or welcome page), or that page's whole content root
  when the extractor found no text node in it.
* ``document_page_text`` (HTML): a block of an official document page that has no
  site container.

Other rows:

* ``page_text_with_chrome``: the page's whole visible text, as
  ``recover_ingest_batch._targeted_state_html`` flattens it, with the legal-text
  container's text a proper part of it.
* ``document_page_text`` (PDF): the shared PDF extractor's text of the page the
  row's path names.
* ``document_section_text``: a PDF section row equal to the section of the same
  label that the shared PDF extractor makes with the ``extraction`` block of the
  tracked source manifest (``heading_only`` when both are empty).
* ``alias_copy``: a row ``_materialize_planned_targets`` made by copying the whole
  body of another row of the same document to a planned citation path. The row
  records which row it copies and whether the copy opens with the target label.
* ``unclassified``: none of the above.

For every scope it also records the retained files' hashes against their
provenance sidecars and the signed ingest manifest, the tracked selectors that
select the scope, and what the named carrier scopes hold at the scope's paths.
Carriers are named, not discovered, so later successors do not change the audit.
It writes only the audit JSON and changes no corpus artifact.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, Tag

DEFAULT_OUTPUT = Path("docs/ingest-runs/2026-09-27-recovery-sibling-scopes-audit.json")
TEXT_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "table", "blockquote")
NO_TEXT_VERDICTS = (
    "empty_document_root",
    "site_chrome",
    "tables_from_other_sections",
    "landing_page_text",
)
KEY_SELECTORS = (
    "us-rulespec-2026-08-08-obbb-alien-snap",
    "us-rulespec-2026-09-24-snap-fy2027-cola",
    "us-rulespec-2026-08-23-canada-338-suspension-union",
    "us-rulespec-2026-09-14-wave4-union",
    "us-rulespec-2026-09-14-wave4-r2-union",
)
_SC_SECTION = re.compile(r"^\s*SECTION\s+(\d+-\d+-\d+[A-Z]?)\.\s*$")


@dataclass(frozen=True)
class ScopeAudit:
    """How to read one scope's retained pages."""

    jurisdiction: str
    document_class: str
    version: str
    # CSS selector of the element that holds a page's legal text.
    container: str | None = None
    # CSS selector of the history note inside the container, where it has one.
    history: str | None = None
    # Documents whose page holds no legal text of its own.
    landing: frozenset[str] = frozenset()
    # Documents that are a chapter page read by South Carolina SECTION markers.
    section_marker_pages: frozenset[str] = frozenset()
    # PDF documents extracted with a tracked manifest's ``extraction`` block:
    # document id -> (manifest, the document's citation path there).
    pdf_extraction: dict[str, tuple[str, str]] = field(default_factory=dict)
    carriers: tuple[str, ...] = ()

    @property
    def key(self) -> str:
        return f"{self.jurisdiction}/{self.document_class}/{self.version}"


RECOVERY = "2026-07-13-recovery"
SCOPES: tuple[ScopeAudit, ...] = (
    ScopeAudit(
        "us-ny",
        "statute",
        RECOVERY,
        container="div.nys-openleg-result-text",
        carriers=(
            "2026-09-14-income-tax-chapter",
            "2026-09-14-income-tax-chapter-r2026-09-23-line-structure",
        ),
    ),
    ScopeAudit(
        "us-id",
        "statute",
        RECOVERY,
        container="div.pgbrk",
        carriers=(
            "2026-07-31-id-title-63-chapter-30-successor",
            "2026-09-14-income-tax-chapter-us-id-title-63-chapter-30",
        ),
    ),
    ScopeAudit(
        "us-me",
        "statute",
        RECOVERY,
        container="div.MRSSection",
        carriers=("2026-09-14-income-tax-chapter-us-me-title-36",),
    ),
    ScopeAudit(
        "us-mn",
        "statute",
        RECOVERY,
        container="div#xtend",
        history="div.history",
        carriers=("2026-09-14-income-tax-chapter-us-mn-title-290",),
    ),
    ScopeAudit(
        "us-ut",
        "statute",
        RECOVERY,
        container="div#secdiv",
        carriers=("2026-09-14-income-tax-chapter-title-59",),
    ),
    ScopeAudit(
        "us-sc",
        "statute",
        RECOVERY,
        section_marker_pages=frozenset({"us-sc-code-12-6-520"}),
        carriers=(
            "2026-07-16-pit-central-us-sc-title-12-chapter-6",
            "2026-07-24-sc-act110-us-sc-title-12-chapter-6",
        ),
    ),
    ScopeAudit(
        "us-mi",
        "statute",
        RECOVERY,
        container="div.sectionWrapper",
        carriers=("2026-09-14-income-tax-chapter-us-mi-chapter-206",),
    ),
    ScopeAudit(
        "us-mt",
        "regulation",
        RECOVERY,
        container="div.react-pdf__Page__textContent",
        carriers=("2026-09-14-income-tax-regulations-title-42-section-42-15",),
    ),
    ScopeAudit(
        "us-co",
        "regulation",
        RECOVERY,
        landing=frozenset({"release-scope-us-co-regulation-2026-04-29-10-ccr-2506-1"}),
        carriers=("2026-07-13-recovery-r2026-09-11-tanf-consolidated",),
    ),
    ScopeAudit(
        "us-co",
        "regulation",
        "2026-07-13-recovery-r2026-09-11-tanf-consolidated",
        landing=frozenset({"release-scope-us-co-regulation-2026-04-29-10-ccr-2506-1"}),
        pdf_extraction={
            "us-co-ccr-9-2503-6-colorado-works": (
                "manifests/us-co-tanf-state-policy-manual.yaml",
                "us-co/regulation/9-ccr-2503-6",
            )
        },
        carriers=(RECOVERY,),
    ),
    ScopeAudit(
        "us-fl",
        "regulation",
        RECOVERY,
        landing=frozenset({"release-scope-us-fl-regulation-2026-05-29"}),
        carriers=("2026-05-29-r2026-07-15-self-contained",),
    ),
    ScopeAudit(
        "us-sc",
        "regulation",
        RECOVERY,
        landing=frozenset({"release-scope-us-sc-regulation-2026-05-29"}),
        carriers=("2026-05-29-r2026-07-15-self-contained",),
    ),
    ScopeAudit(
        "us-tn",
        "regulation",
        RECOVERY,
        landing=frozenset({"release-scope-us-tn-regulation-2026-05-29"}),
        carriers=("2026-05-29-r2026-07-15-self-contained",),
    ),
    ScopeAudit(
        "us-il",
        "manual",
        "2026-07-13-recovery-r2026-07-17-dedup",
        landing=frozenset({"release-scope-us-il-manual-2026-05-27-il-cash-snap-medical-manual"}),
        carriers=("2026-05-27-il-cash-snap-medical-manual-r2026-07-15-self-contained",),
    ),
    ScopeAudit(
        "us-in",
        "manual",
        RECOVERY,
        landing=frozenset({"release-scope-us-in-manual-2026-05-27-in-snap-manual"}),
        carriers=("2026-05-27-in-snap-manual-r2026-07-15-self-contained",),
    ),
    ScopeAudit(
        "us-sc",
        "manual",
        RECOVERY,
        landing=frozenset({"release-scope-us-sc-manual-2026-05-27-sc-snap-manual"}),
        carriers=("2026-05-27-sc-snap-manual",),
    ),
    ScopeAudit(
        "us-ut",
        "manual",
        RECOVERY,
        landing=frozenset({"release-scope-us-ut-manual-2026-05-27-ut-manuals"}),
        carriers=("2026-05-27-ut-manuals-r2026-07-15-self-contained",),
    ),
    ScopeAudit(
        "us",
        "guidance",
        RECOVERY,
        landing=frozenset(
            {
                "release-scope-us-guidance-2026-05-01-snap-fy2026-cola",
                "release-scope-us-guidance-2026-05-02-snap-fy2026-income-eligibility-standards",
                "release-scope-us-guidance-2026-07-08-snap-fy2024-cola",
            }
        ),
        carriers=(
            "2026-05-01-snap-fy2026-cola-r2026-07-15-self-contained",
            "2026-05-02-snap-fy2026-income-eligibility-standards-r2026-07-15-self-contained",
            "2026-07-08-snap-fy2024-cola",
            "2026-05-02-irs-rev-proc-2025-32-r2026-07-15-self-contained",
            "2026-06-01-irs-rev-proc-2025-25-irs-rev-proc-2025-25",
        ),
    ),
)


def normalized(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _words(text: str) -> list[str]:
    """Lower-case words, without parenthesized paragraph markers.

    Carriers print markers differently (Utah's chapter scope repeats the parent,
    ``(2)(a)``), so markers are left out of the word comparison.
    """
    return re.findall(r"[a-z0-9]+", re.sub(r"\([0-9a-z]{1,6}\)", " ", text.lower()))


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _element_text(element: Tag) -> str:
    return normalized(element.get_text(" ", strip=True))


def _is_in(element: Tag, containers: list[Tag]) -> bool:
    return any(element is container or container in element.parents for container in containers)


# ``documents._extract_html_blocks`` drops these before it reads a page (the
# ``drop_selectors`` list in src/axiom_corpus/corpus/documents.py).
EXTRACTOR_DROP_SELECTORS = (
    "script",
    "style",
    "noscript",
    "svg",
    "button",
    "input",
    "nav",
    "select",
    "header",
    "footer",
    "textarea",
    "aside",
    ".breadcrumb",
    ".breadcrumbs",
    "[aria-label='breadcrumb']",
)


@dataclass
class Node:
    """One text node the shared block extractor reads, and where it sits."""

    text: str
    heading: bool
    region: str  # "text" or "history" inside the legal-text container, else "outside"
    section: str | None = None


@dataclass
class Page:
    """One retained HTML page as the shared block extractor walks it."""

    title: str | None
    nodes: list[Node]
    root_text: str
    container_text: str
    visible_text: str
    has_container: bool

    def runs(self) -> list[list[Node]]:
        """The non-heading nodes between headings: the extractor's block bodies."""
        runs: list[list[Node]] = [[]]
        for node in self.nodes:
            if node.heading:
                runs.append([])
            else:
                runs[-1].append(node)
        return [run for run in runs if run]


def _targeted_visible_text(html: bytes) -> str:
    """The page text ``recover_ingest_batch._targeted_state_html`` stores."""
    soup = BeautifulSoup(html.decode("utf-8-sig", errors="replace"), "lxml")
    for tag in soup.find_all(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    return normalized(soup.get_text(" ", strip=True))


def read_page(
    html: bytes,
    container: str | None,
    *,
    history: str | None = None,
    section_markers: bool = False,
) -> Page:
    """Walk a page the way ``documents._extract_html_blocks`` does.

    The nodes are the extractor's own (``_main_content`` and ``_html_text_nodes``
    after its drop list); only their place relative to the legal-text container
    is decided here.
    """
    from axiom_corpus.corpus.documents import (
        _HEADING_TAGS,
        _html_soup,
        _html_text_nodes,
        _main_content,
        _normalize_text,
    )

    plain = BeautifulSoup(html.decode("utf-8-sig", errors="replace"), "lxml")
    title_tag = plain.find("title")
    title = _element_text(title_tag) if isinstance(title_tag, Tag) else None
    for tag in plain.find_all(["script", "style", "noscript"]):
        tag.decompose()
    container_nodes = plain.select(container) if container else []

    soup = _html_soup(html)
    for selector in EXTRACTOR_DROP_SELECTORS:
        for dropped in soup.select(selector):
            dropped.decompose()
    containers = soup.select(container) if container else []
    histories = soup.select(history) if history else []
    root = _main_content(soup)
    nodes = []
    for element in _html_text_nodes(root, extraction=None):
        text = _normalize_text(element.get_text(" ", strip=True))
        if not text:
            continue
        if _is_in(element, histories):
            region = "history"
        elif _is_in(element, containers):
            region = "text"
        else:
            region = "outside"
        section = None
        if section_markers:
            marker = element.find_previous(string=_SC_SECTION)
            match = _SC_SECTION.match(str(marker)) if marker is not None else None
            section = match.group(1) if match else None
        nodes.append(Node(text, element.name in _HEADING_TAGS, region, section))
    return Page(
        title=title,
        nodes=nodes,
        root_text=_normalize_text(root.get_text(" ", strip=True)),
        container_text=normalized(" ".join(_element_text(node) for node in container_nodes)),
        visible_text=_targeted_visible_text(html),
        has_container=bool(container_nodes),
    )


def _matching_run(body: str, page: Page) -> list[Node] | None:
    """The extractor block whose body is exactly ``body``.

    ``_extract_html_blocks`` stores ``_normalize_text("\n\n".join(parts))`` for each
    run of non-heading nodes; a row matches a run only when it is that string.
    """
    from axiom_corpus.corpus.documents import _normalize_text

    for run in page.runs():
        if _normalize_text("\n\n".join(node.text for node in run)) == body:
            return run
    return None


@dataclass(frozen=True)
class PdfText:
    """What the shared PDF extractor reads from one retained PDF."""

    pages: dict[int, str]
    sections: dict[str, str]


def _pdf_extraction(repo_root: Path, manifest: str, citation_path: str) -> dict[str, Any]:
    """The ``extraction`` block a tracked source manifest gives one document."""
    import yaml

    payload = yaml.safe_load((repo_root / manifest).read_text(encoding="utf-8"))
    for document in payload.get("documents") or payload.get("sources") or []:
        if document.get("citation_path") == citation_path:
            return dict(document.get("extraction") or {})
    raise ValueError(f"{manifest} names no document at {citation_path}")


@cache
def _pdf_text(path: Path, extraction_json: str) -> PdfText:
    from axiom_corpus.corpus.documents import _extract_pdf_blocks

    extraction = json.loads(extraction_json) or None
    blocks = _extract_pdf_blocks(path.read_bytes(), extraction=extraction)
    return PdfText(
        pages={block.ordinal: block.body for block in blocks if block.kind == "page"},
        sections={
            str(block.metadata["section_label"]): block.body
            for block in blocks
            if block.kind == "section" and "section_label" in block.metadata
        },
    )


def _label(path: str) -> str:
    return path.rsplit("/", 1)[-1]


def classify_row(
    row: dict[str, Any],
    *,
    scope: ScopeAudit,
    page: Page | None,
    pdf: PdfText | None,
    document_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """One verdict for one row, with the facts the verdict rests on."""
    body = row.get("body") or ""
    kind = row.get("kind")
    metadata = row.get("metadata") or {}
    if kind == "document" and not body.strip():
        return {"verdict": "empty_document_root"}
    if metadata.get("recovery_target_alias"):
        copied = [
            other["citation_path"]
            for other in document_rows
            if other is not row
            and not (other.get("metadata") or {}).get("recovery_target_alias")
            and other.get("body") == body
        ]
        if len(copied) != 1:
            return {"verdict": "unclassified"}
        label = _label(row["citation_path"])
        opening = normalized(body)[:500]
        printed = label.replace("-", "[:-]")
        opens = bool(re.search(rf"(?<![\w.])(?:§\s*)?{printed}(?![\w.])", opening[:120], re.I))
        if label.startswith("page-"):
            opens = _label(copied[0]) == label
        return {"verdict": "alias_copy", "copies": copied[0], "opens_with_target": opens}
    source_format = row.get("source_format")
    if source_format == "pdf":
        match = re.search(r"page-(\d+)$", row["citation_path"])
        if pdf is not None and match and pdf.pages.get(int(match.group(1))) == body:
            return {"verdict": "document_page_text"}
        label = _label(row["citation_path"])
        if pdf is not None and kind == "section" and pdf.sections.get(label) == body:
            return {"verdict": "document_section_text", "heading_only": not body.strip()}
        return {"verdict": "unclassified"}
    if page is None:
        return {"verdict": "unclassified"}
    source_id = row.get("source_id")
    if kind == "section" and "\n" not in body:
        if (
            body == page.visible_text
            and page.container_text
            and page.container_text in body
            and page.container_text != body
        ):
            return {"verdict": "page_text_with_chrome"}
        return {"verdict": "unclassified"}
    run = _matching_run(body, page) if body.strip() else None
    if run is None:
        if source_id in scope.landing and normalized(body) == normalized(page.root_text):
            # The extractor's fallback: its content root held no text node, so the
            # block is the root's whole text.
            return {"verdict": "landing_page_text", "extractor_fallback": True}
        return {"verdict": "unclassified"}
    regions = [node.region for node in run]
    if source_id in scope.landing:
        return {"verdict": "landing_page_text"}
    if source_id in scope.section_marker_pages:
        target = _label(row["citation_path"].rsplit("/block-", 1)[0])
        sections = sorted({node.section or "" for node in run})
        if sections == [""]:
            return {"verdict": "site_chrome", "sections": []}
        if "" not in sections and target not in sections:
            return {"verdict": "tables_from_other_sections", "sections": sections}
        return {"verdict": "unclassified"}
    if not page.has_container:
        return {"verdict": "document_page_text"}
    if set(regions) == {"outside"}:
        return {"verdict": "site_chrome"}
    if set(regions) == {"text"}:
        return {"verdict": "legal_text"}
    if set(regions) == {"history"}:
        return {"verdict": "history_note"}
    first_outside = regions.index("outside") if "outside" in regions else len(regions)
    leading, trailing = regions[:first_outside], regions[first_outside:]
    if (
        leading
        and "history" in leading
        and set(leading) <= {"history", "text"}
        and set(trailing) == {"outside"}
    ):
        # The history note (and, on some pages, a revisor's note printed after it),
        # then the page footer.
        return {"verdict": "history_note_and_site_chrome", "includes_note": "text" in leading}
    return {"verdict": "unclassified"}


def _scope_rows(base: Path, scope: ScopeAudit, version: str | None = None) -> list[dict[str, Any]]:
    path = (
        base
        / "provisions"
        / scope.jurisdiction
        / scope.document_class
        / f"{version or scope.version}.jsonl"
    )
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _provenance(base: Path, source_path: str, document_id: str) -> dict[str, Any] | None:
    directory = (base / source_path).parent.parent / "provenance"
    for candidate in (
        directory / f"{document_id}.json",
        directory / f"{Path(source_path).name}.json",
    ):
        if candidate.is_file():
            return dict(json.loads(candidate.read_text(encoding="utf-8")))
    return None


def selectors_selecting(repo_root: Path, scope: ScopeAudit) -> list[str]:
    selecting = []
    for path in sorted((repo_root / "manifests" / "releases").glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if any(
            (entry["jurisdiction"], entry["document_class"], entry["version"])
            == (scope.jurisdiction, scope.document_class, scope.version)
            for entry in payload["scopes"]
        ):
            selecting.append(path.stem)
    return selecting


TEXT_VERDICTS = ("legal_text", "history_note", "document_page_text", "document_section_text")


def _carriage(
    base: Path,
    scope: ScopeAudit,
    rows: list[dict[str, Any]],
    verdicts: dict[str, str],
    pages: dict[str, Page],
) -> list[dict[str, Any]]:
    """What each named carrier holds at each path of the scope.

    A carrier row with an empty body is read the way axiom-encode composes one:
    from the bodies of its descendants in the same scope, in file order. For
    each carried path the entry also counts how many lines of the scope's own
    text-bearing rows at or under that path occur in the carrier's text.
    """
    by_path = {row["citation_path"]: row for row in rows}
    entries = []
    for version in scope.carriers:
        path = base / "provisions" / scope.jurisdiction / scope.document_class / f"{version}.jsonl"
        carrier_rows = [
            json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line
        ]
        for carrier in carrier_rows:
            citation_path = carrier["citation_path"]
            if citation_path not in by_path:
                continue
            composed = not (carrier.get("body") or "").strip()
            if composed:
                parts = [
                    other.get("body") or ""
                    for other in carrier_rows
                    if other["citation_path"].startswith(citation_path + "/")
                ]
                carrier_text = normalized(" ".join(parts))
            else:
                carrier_text = normalized(carrier.get("body"))
            mine = by_path[citation_path]
            entry: dict[str, Any] = {
                "citation_path": citation_path,
                "carrier_version": version,
                "carrier_kind": carrier.get("kind"),
                "carrier_source_as_of": carrier.get("source_as_of"),
                "carrier_text_composed_from_descendants": composed,
                "carrier_text_chars": len(carrier_text),
                "row_body_equals_carrier_text": normalized(mine.get("body")) == carrier_text,
            }
            page = pages.get(mine.get("source_id") or "")
            if page is not None and page.container_text and carrier_text:
                entry["container_text_equals_carrier_text"] = page.container_text == carrier_text
                entry["carrier_text_in_container_text"] = carrier_text in page.container_text
                entry["container_text_in_carrier_text"] = page.container_text in carrier_text
                # Word counts each side has that the other lacks: formatting-blind, so
                # a moved heading or history note shows up as a few words, a dropped
                # paragraph as many.
                container_words = Counter(_words(page.container_text))
                carrier_words = Counter(_words(carrier_text))
                entry["container_words_not_in_carrier"] = sum(
                    (container_words - carrier_words).values()
                )
                entry["carrier_words_not_in_container"] = sum(
                    (carrier_words - container_words).values()
                )
                container_lines = [
                    node.text for node in page.nodes if node.region == "text" and not node.heading
                ]
                entry["container_lines"] = len(container_lines)
                entry["container_lines_in_carrier_text"] = sum(
                    normalized(line) in carrier_text for line in container_lines
                )
            lines = [
                normalized(part)
                for row in rows
                if (
                    row["citation_path"] == citation_path
                    or row["citation_path"].startswith(citation_path + "/")
                )
                and verdicts[row["citation_path"]] in TEXT_VERDICTS
                for part in (row.get("body") or "").split("\n\n")
                if part.strip()
            ]
            if lines and carrier_text:
                entry["text_lines"] = len(lines)
                entry["text_lines_in_carrier_text"] = sum(line in carrier_text for line in lines)
            entries.append(entry)
    return entries


@dataclass
class ScopeSources:
    """One scope's rows and its retained sources, read once."""

    rows: list[dict[str, Any]]
    by_document: dict[str, list[dict[str, Any]]]
    files: list[dict[str, Any]]
    pages: dict[str, Page]
    pdfs: dict[str, PdfText]

    def classify(self, row: dict[str, Any], scope: ScopeAudit) -> dict[str, Any]:
        document_id = row["source_id"]
        return classify_row(
            row,
            scope=scope,
            page=self.pages.get(document_id),
            pdf=self.pdfs.get(document_id),
            document_rows=self.by_document[document_id],
        )


def load_sources(base: Path, repo_root: Path, scope: ScopeAudit) -> ScopeSources:
    rows = _scope_rows(base, scope)
    manifest_path = (
        repo_root
        / ".axiom"
        / "ingest-manifests"
        / scope.jurisdiction
        / scope.document_class
        / f"{scope.version}.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    signed = {entry["path"]: entry["sha256"] for entry in manifest["applied_files"]}
    by_document: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_document.setdefault(row["source_id"], []).append(row)
    files = []
    pages: dict[str, Page] = {}
    pdfs: dict[str, PdfText] = {}
    for document_id, document_rows in sorted(by_document.items()):
        source_path = document_rows[0]["source_path"]
        data = (base / source_path).read_bytes()
        provenance = _provenance(base, source_path, document_id)
        digest = sha256(data)
        record: dict[str, Any] = {
            "document_id": document_id,
            "source_path": source_path,
            "url": (provenance or {}).get("url"),
            "fetched_at": (provenance or {}).get("fetched_at"),
            "sha256": digest,
            # Adapter-made sources carried into a consolidated scope have no sidecar.
            "sha256_matches_provenance": (
                digest == provenance.get("sha256") if provenance else None
            ),
            "sha256_matches_signed_manifest": digest == signed.get(f"data/corpus/{source_path}"),
            "rows": len(document_rows),
        }
        if data.startswith(b"%PDF"):
            record["format"] = "pdf"
            extraction: dict[str, Any] = {}
            if document_id in scope.pdf_extraction:
                manifest_name, citation = scope.pdf_extraction[document_id]
                extraction = _pdf_extraction(repo_root, manifest_name, citation)
                record["extraction_from"] = manifest_name
            pdfs[document_id] = _pdf_text(
                base / source_path, json.dumps(extraction, sort_keys=True)
            )
        else:
            record["format"] = "html"
            page = read_page(
                data,
                scope.container,
                history=scope.history,
                section_markers=document_id in scope.section_marker_pages,
            )
            pages[document_id] = page
            record["title"] = page.title
            record["page_type"] = (
                "landing"
                if document_id in scope.landing
                else "chapter_page"
                if document_id in scope.section_marker_pages
                else "legal_text_container"
                if page.has_container
                else "document_without_container"
            )
        files.append(record)
    return ScopeSources(rows, by_document, files, pages, pdfs)


def audit_scope(base: Path, repo_root: Path, scope: ScopeAudit) -> dict[str, Any]:
    sources = load_sources(base, repo_root, scope)
    rows, files, pages = sources.rows, sources.files, sources.pages
    audited_rows = []
    for line_number, row in enumerate(rows, start=1):
        document_id = row["source_id"]
        result = sources.classify(row, scope)
        body = row.get("body") or ""
        audited_rows.append(
            {
                "line": line_number,
                "citation_path": row["citation_path"],
                "kind": row.get("kind"),
                "source_id": document_id,
                "heading": row.get("heading"),
                "body_chars": len(body),
                "body_sha256": sha256(body.encode("utf-8")),
                **result,
            }
        )
    verdicts = Counter(row["verdict"] for row in audited_rows)
    selecting = selectors_selecting(repo_root, scope)
    return {
        "scope": scope.key,
        "summary": {
            "rows": len(audited_rows),
            "files": len(files),
            "verdicts": dict(sorted(verdicts.items())),
            "rows_without_legal_text": sum(verdicts[verdict] for verdict in NO_TEXT_VERDICTS),
        },
        "files": files,
        "rows": audited_rows,
        "carriage": _carriage(
            base,
            scope,
            rows,
            {row["citation_path"]: row["verdict"] for row in audited_rows},
            pages,
        ),
        "selectors": {
            "count": len(selecting),
            "names": selecting,
            "key_lines": {name: name in selecting for name in KEY_SELECTORS},
        },
    }


def audit(base: Path, repo_root: Path) -> dict[str, Any]:
    return {
        "generated_by": "scripts/audit_recovery_sibling_scopes.py",
        "scopes": {scope.key: audit_scope(base, repo_root, scope) for scope in SCOPES},
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
    for key, scope in report["scopes"].items():
        print(key, json.dumps(scope["summary"]["verdicts"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
