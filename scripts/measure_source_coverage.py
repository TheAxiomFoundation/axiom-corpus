"""Measure the source coverage of locked HTML scopes, offline, and rank them.

Locked coverage reports cannot change, so the scopes that exist are measured here once
to rank successor work (docs/source-coverage-check.md, "Existing scopes"). For every
retained HTML source that a scope's rows cite, the script computes the figures the
official-document extractor now records at extraction time
(``axiom_corpus.corpus.source_coverage``): how many words of the source's region the
rows citing it keep, and the longest runs that are missing.

The region of a source is chosen in this order:

1. ``manifest``: the scope's signed ingest manifest names an official-document
   manifest (``--manifest manifests/x.yaml``) that still lists the source. The region is
   what the extractor reads from the retained page with that document's extraction
   settings as they are in the checkout now (``documents.html_source_region``).
2. ``source_id``: no manifest is named, but every official-document manifest in
   ``manifests/`` that lists this jurisdiction, document class and source id gives it
   the same extraction settings. The region is read with those.
3. ``whole_page``: otherwise. The region is the page's visible text (scripts, styles
   and templates removed) without the content check's navigation elements
   (``content_quality``: links, options, buttons, ``nav``, page headers and footers).
   Site chrome outside those elements is still counted, so a well-extracted page of a
   site with a lot of it scores low; read these scopes' missing runs before their
   shares.

A manifest read today is not the manifest the scope was built with. That is the
point: a scope whose manifest has since gained a selector scores low until a successor
is built with it.

    uv run python scripts/measure_source_coverage.py --all \\
        --output out/source-coverage.json --csv out/source-coverage-scopes.csv
    uv run python scripts/measure_source_coverage.py us-md/statute --output out/md.json

Bytes come from the checkout when a locked file is fetched there and from the local
corpus cache otherwise; nothing is fetched or written under ``data/corpus``. A scope
with a file in neither place is reported as ``absent``, never measured in part.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import sys
import warnings
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import lxml.html
import yaml
from bs4 import XMLParsedAsHTMLWarning
from lxml import etree

from axiom_corpus.corpus import content_quality, documents
from axiom_corpus.corpus.artifacts import safe_segment
from axiom_corpus.corpus.content_store import ContentCache
from axiom_corpus.corpus.corpus_locks import (
    CORPUS_BASE,
    CorpusLock,
    LockEntry,
    ScopeKey,
    load_locks,
    parse_scope_selector,
    scope_matches,
)
from axiom_corpus.corpus.io import iter_provisions
from axiom_corpus.corpus.release_policy import WITHDRAWN_SCOPES_PATH, load_withdrawn_scopes
from axiom_corpus.corpus.releases import ReleaseManifest
from axiom_corpus.corpus.source_coverage import (
    REVIEW_COVERAGE,
    REVIEW_MIN_REGION_WORDS,
    SOURCE_COVERAGE_VERSION,
    SourceCoverage,
    SourceRegion,
    needs_review,
    words,
)

DEFAULT_WORKERS = 4
REGION_WHOLE_PAGE = "html_whole_page"
MATCH_MANIFEST = "manifest"
MATCH_SOURCE_ID = "source_id"
MATCH_WHOLE_PAGE = "whole_page"
INGEST_MANIFEST_ROOT = Path(".axiom") / "ingest-manifests"
# Missing runs kept per source in the JSON report.
REPORT_RUNS = 5

_SELECTOR_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_MANIFEST_ARGUMENT = re.compile(r"--manifest[ =]+(\S+\.ya?ml)")
_OFFICIAL_DOCUMENTS_DIR = "official-documents"
_SOURCES_PREFIX = f"{CORPUS_BASE}/sources/"


def whole_page_region(raw: bytes) -> SourceRegion | None:
    """A page's visible text without the content check's navigation elements.

    The navigation elements' own text is recorded as dropped. Returns ``None`` when
    the bytes do not parse as HTML.
    """
    try:
        document = lxml.html.document_fromstring(raw)
    except (etree.LxmlError, ValueError):
        return None
    for element in document.xpath(content_quality._INVISIBLE_XPATH):
        element.drop_tree()
    for comment in document.xpath("//comment()|//processing-instruction()"):
        if comment.getparent() is not None:
            comment.drop_tree()
    region = SourceRegion()
    region.start(REGION_WHOLE_PAGE)
    navigation = document.xpath(content_quality._NAVIGATION_XPATH)
    inside = {id(element) for element in navigation}
    for element in navigation:
        if any(id(ancestor) in inside for ancestor in element.iterancestors()):
            continue  # counted with the navigation element that holds it
        region.drop(_element_text(element))
    for element in navigation:
        if element.getparent() is not None:
            element.drop_tree()
    body = document.find("body")
    region.read(_element_text(body if body is not None else document))
    return region


def _element_text(element: Any) -> str:
    """An element's text with a space wherever one of its elements starts or ends."""
    return " ".join(text.strip() for text in element.itertext() if text.strip())


def manifest_named_by_ingest(repo: Path, scope: ScopeKey) -> str | None:
    """The ``--manifest`` path in the command a scope's signed ingest manifest records."""
    path = repo / INGEST_MANIFEST_ROOT / scope[0] / scope[1] / f"{scope[2]}.json"
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    command = payload.get("command") if isinstance(payload, dict) else None
    text = command.get("text") if isinstance(command, dict) else None
    match = _MANIFEST_ARGUMENT.search(text) if isinstance(text, str) else None
    return match.group(1) if match else None


def manifest_documents(path: Path) -> list[dict[str, Any]]:
    """The document mappings of an official-document manifest ([] for any other YAML)."""
    try:
        data = yaml.load(path.read_text(), Loader=getattr(yaml, "CSafeLoader", yaml.SafeLoader))
    except (OSError, yaml.YAMLError, UnicodeDecodeError):
        return []
    documents_list = data.get("documents") if isinstance(data, dict) else None
    if not isinstance(documents_list, list):
        return []
    return [row for row in documents_list if isinstance(row, dict) and "source_id" in row]


def _extraction(row: Mapping[str, Any]) -> dict[str, Any] | None:
    extraction = row.get("extraction")
    return dict(extraction) if isinstance(extraction, dict) else None


def _source_stem(row: Mapping[str, Any]) -> str:
    return safe_segment(str(row["source_id"]))


class ManifestIndex:
    """The extraction settings the official-document manifests give each source id."""

    def __init__(self, repo: Path) -> None:
        self.repo = repo
        self._by_manifest: dict[str, dict[str, dict[str, Any] | None]] = {}
        self._by_source: dict[tuple[str, str, str], dict[str, dict[str, Any] | None]] | None = None

    def documents_of(self, manifest: str) -> dict[str, dict[str, Any] | None]:
        """Source file stem -> extraction settings, for one manifest."""
        if manifest not in self._by_manifest:
            self._by_manifest[manifest] = {
                _source_stem(row): _extraction(row)
                for row in manifest_documents(self.repo / manifest)
            }
        return self._by_manifest[manifest]

    def settings_by_source_id(
        self, jurisdiction: str, document_class: str, stem: str
    ) -> dict[str, Any] | None | bool:
        """The one extraction every manifest gives this source id, or ``False``.

        ``False`` means no manifest lists the source id or two of them disagree.
        """
        if self._by_source is None:
            index: dict[tuple[str, str, str], dict[str, dict[str, Any] | None]] = defaultdict(dict)
            for path in sorted((self.repo / "manifests").glob("*.yaml")):
                for row in manifest_documents(path):
                    key = (
                        str(row.get("jurisdiction")),
                        str(row.get("document_class", "policy")),
                        _source_stem(row),
                    )
                    extraction = _extraction(row)
                    index[key][json.dumps(extraction, sort_keys=True, default=str)] = extraction
            self._by_source = dict(index)
        candidates = self._by_source.get((jurisdiction, document_class, stem))
        if not candidates or len(candidates) != 1:
            return False
        return next(iter(candidates.values()))


class LockedFiles:
    """Where the bytes of locked corpus files are, without fetching any."""

    def __init__(self, repo: Path, cache: ContentCache | None = None) -> None:
        self.repo = repo
        self.cache = cache or ContentCache()

    def path(self, entry: LockEntry) -> Path | None:
        fetched = self.repo / entry.path
        if fetched.is_file():
            return fetched
        if self.cache.contains(entry.sha256, entry.size):
            return self.cache.object_path(entry.sha256)
        return None


def measure_scope(
    lock: CorpusLock,
    files: LockedFiles,
    *,
    manifest: str | None,
    manifest_settings: Mapping[str, dict[str, Any] | None],
    source_id_settings: Mapping[str, dict[str, Any] | None],
) -> dict[str, Any]:
    """Measure every retained HTML source the rows of one locked scope cite.

    ``manifest_settings`` maps a source file stem to the extraction settings of the
    manifest the scope's ingest named; ``source_id_settings`` does the same for stems
    matched by source id alone.
    """
    scope = "/".join(lock.scope)
    by_path = {entry.path: entry for entry in lock.files}
    provisions = by_path.get(
        f"{CORPUS_BASE}/provisions/{lock.jurisdiction}/{lock.document_class}/{lock.version}.jsonl"
    )
    result: dict[str, Any] = {"scope": scope, "manifest": manifest, "sources": []}
    if provisions is None:
        return {**result, "skipped": "no provisions file"}
    provisions_path = files.path(provisions)
    if provisions_path is None:
        return {**result, "absent": [provisions.path]}

    texts: dict[str, list[str]] = defaultdict(list)
    bodies: dict[str, list[str]] = defaultdict(list)
    first_row: dict[str, str] = {}
    row_counts: Counter[str] = Counter()
    rows = 0
    for record in iter_provisions(provisions_path):
        rows += 1
        source = record.source_path
        if not isinstance(source, str) or not source:
            continue
        row_counts[source] += 1
        first_row.setdefault(source, record.citation_path)
        for text in (record.heading, record.body):
            if isinstance(text, str) and text:
                texts[source].append(text)
        if isinstance(record.body, str) and record.body:
            bodies[source].append(record.body)

    absent: list[str] = []
    sources: list[dict[str, Any]] = []
    for source in sorted(row_counts):
        entry = by_path.get(f"{CORPUS_BASE}/{source.removeprefix(f'{CORPUS_BASE}/')}")
        if entry is None:
            continue  # the row cites a file outside this scope's lock
        path = files.path(entry)
        if path is None:
            absent.append(entry.path)
            continue
        with path.open("rb") as handle:
            if not content_quality.looks_like_html(handle.read(content_quality.HTML_SNIFF_BYTES)):
                continue
        raw = path.read_bytes()
        region, matched_by, error = _region(
            raw,
            stem=_stem(entry.path),
            manifest_settings=manifest_settings,
            source_id_settings=source_id_settings,
        )
        if region is None or region.kind is None:
            sources.append({"source_path": source, "error": error or "not parseable as HTML"})
            continue
        figures = region.measure(texts[source])
        row = _source_row(source, region.kind, matched_by, figures)
        row["rows"] = row_counts[source]
        # Rows with headings and no body are containers (a part's list of sections, an
        # index page): what they miss is not partial loss.
        row["row_body_words"] = sum(len(words(text)) for text in bodies[source])
        row["first_row"] = first_row[source]
        if error:
            row["region_error"] = error
        sources.append(row)
    if absent:
        return {**result, "absent": absent}
    cited = {f"{CORPUS_BASE}/{source.removeprefix(f'{CORPUS_BASE}/')}" for source in row_counts}
    result["rows"] = rows
    result["sources"] = sources
    result["uncited_sources"] = sum(
        1 for path in by_path if path.startswith(_SOURCES_PREFIX) and path not in cited
    )
    return result


def _stem(path: str) -> str | None:
    """The source file stem of an ``official-documents/<stem>[.ext]`` path, else ``None``."""
    parts = Path(path).parts
    if len(parts) < 2 or parts[-2] != _OFFICIAL_DOCUMENTS_DIR:
        return None
    return Path(parts[-1]).stem if Path(parts[-1]).suffix else parts[-1]


def _region(
    raw: bytes,
    *,
    stem: str | None,
    manifest_settings: Mapping[str, dict[str, Any] | None],
    source_id_settings: Mapping[str, dict[str, Any] | None],
) -> tuple[SourceRegion | None, str, str | None]:
    """The region of one page, how it was chosen, and why a manifest region failed."""
    error = None
    for matched_by, settings in (
        (MATCH_MANIFEST, manifest_settings),
        (MATCH_SOURCE_ID, source_id_settings),
    ):
        if stem is None or stem not in settings:
            continue
        try:
            with warnings.catch_warnings():
                # Retained XHTML pages are read as the extractor reads them.
                warnings.simplefilter("ignore", XMLParsedAsHTMLWarning)
                region = documents.html_source_region(raw, extraction=settings[stem])
            return region, matched_by, None
        except Exception as exc:
            # Today's manifest does not fit the retained page (a selector that no
            # longer matches, say): measure the whole page and say why. Whatever the
            # extraction raises, one page must not end a corpus-wide run.
            error = f"{matched_by} region failed: {type(exc).__name__}: {exc}"[:300]
            break
    return whole_page_region(raw), MATCH_WHOLE_PAGE, error


def _source_row(source: str, kind: str, matched_by: str, figures: SourceCoverage) -> dict[str, Any]:
    return {
        "source_path": source,
        "region": kind,
        "matched_by": matched_by,
        "region_words": figures.region_words,
        "kept_words": figures.kept_words,
        "deliberately_dropped_words": figures.deliberately_dropped_words,
        "coverage": round(figures.coverage, 4),
        "needs_review": needs_review(figures),
        "longest_missing_runs": [
            run.to_mapping() for run in figures.longest_missing_runs[:REPORT_RUNS]
        ],
    }


def summarize_scope(result: Mapping[str, Any]) -> dict[str, Any] | None:
    """One ranking row for a measured scope (``None`` when it has no measured source)."""
    measured = [row for row in result.get("sources", ()) if "region_words" in row]
    if not measured:
        return None
    coverages = sorted(row["coverage"] for row in measured)
    count = len(coverages)
    review = [row for row in measured if row["needs_review"]]
    regions = Counter(row["matched_by"] for row in measured)
    return {
        "scope": result["scope"],
        "region": "+".join(sorted(regions)),
        "manifest": result.get("manifest") or "",
        "sources": count,
        "median": round(statistics.median(coverages), 4),
        "p10": coverages[count // 10],
        "minimum": coverages[0],
        "needs_review": len(review),
        "needs_review_share": round(len(review) / count, 4),
        "needs_review_with_body": sum(1 for row in review if row.get("row_body_words", 0) > 0),
        "region_words": sum(row["region_words"] for row in measured),
        "missing_words": sum(row["region_words"] - row["kept_words"] for row in measured),
        "needs_review_missing_words": sum(
            row["region_words"] - row["kept_words"] for row in review
        ),
        "errors": sum(1 for row in result.get("sources", ()) if "error" in row),
    }


def rank(summaries: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Scopes with the most sources under the review bar first, lowest median breaking ties.

    ``needs_review_with_body`` counts the sources under the bar whose rows carry body
    text: those lost part of a text, where a source with heading-only rows is a
    container or an empty document.
    """
    return sorted(
        (dict(row) for row in summaries),
        key=lambda row: (-row["needs_review"], row["median"], row["scope"]),
    )


def release_context(repo: Path) -> dict[str, dict[str, Any]]:
    """Per scope: whether it is withdrawn, and the release selectors that select it.

    ``selectors`` counts the tracked selectors under ``manifests/releases``;
    ``newest_selector`` is the one with the latest date in its name. A scope no
    selector names and a withdrawn scope need no successor for a release's sake.
    """
    context: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"withdrawn": False, "selectors": 0, "newest_selector": ""}
    )
    withdrawn_path = repo / WITHDRAWN_SCOPES_PATH
    if withdrawn_path.is_file():
        for scope in load_withdrawn_scopes(withdrawn_path):
            context["/".join(scope)]["withdrawn"] = True
    newest: dict[str, tuple[str, str]] = {}
    for path in sorted((repo / "manifests" / "releases").glob("*.json")):
        release = ReleaseManifest.load(path)
        dates = _SELECTOR_DATE.findall(release.name)
        order = (max(dates) if dates else "", release.name)
        for scope in release.scope_keys:
            label = "/".join(scope)
            context[label]["selectors"] += 1
            if order > newest.get(label, ("", "")):
                newest[label] = order
                context[label]["newest_selector"] = release.name
    return context


_CSV_FIELDS = (
    "scope",
    "region",
    "sources",
    "median",
    "p10",
    "minimum",
    "needs_review",
    "needs_review_share",
    "needs_review_with_body",
    "region_words",
    "missing_words",
    "needs_review_missing_words",
    "errors",
    "withdrawn",
    "selectors",
    "newest_selector",
    "manifest",
)


def write_csv(path: Path, ranking: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=_CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in ranking:
            writer.writerow({field: row[field] for field in _CSV_FIELDS})


# --------------------------------------------------------------------------- CLI

_WORKER: dict[str, Any] = {}


def _job(
    arguments: tuple[str, ScopeKey, str | None, dict[str, Any], dict[str, Any]],
) -> dict[str, Any]:
    repo_text, scope, manifest, manifest_settings, source_id_settings = arguments
    if _WORKER.get("repo") != repo_text:
        repo = Path(repo_text)
        _WORKER.update(repo=repo_text, locks=load_locks(repo), files=LockedFiles(repo))
    lock = _WORKER["locks"].locks[scope]
    try:
        return measure_scope(
            lock,
            _WORKER["files"],
            manifest=manifest,
            manifest_settings=manifest_settings,
            source_id_settings=source_id_settings,
        )
    except Exception as exc:  # one unreadable scope must not end a corpus-wide run
        return {
            "scope": "/".join(scope),
            "manifest": manifest,
            "sources": [],
            "failed": f"{type(exc).__name__}: {exc}"[:300],
        }


def _html_stems(lock: CorpusLock) -> list[str]:
    """Stems of the scope's ``official-documents`` sources that may be HTML pages."""
    stems = []
    for entry in lock.files:
        if not entry.path.startswith(_SOURCES_PREFIX):
            continue
        if Path(entry.path).suffix.lower() not in {".html", ".htm", ""}:
            continue
        stem = _stem(entry.path)
        if stem is not None:
            stems.append(stem)
    return stems


def plan(
    repo: Path, scopes: Sequence[ScopeKey], locks: Mapping[ScopeKey, CorpusLock]
) -> list[tuple[str, ScopeKey, str | None, dict[str, Any], dict[str, Any]]]:
    """One job per scope with HTML-like sources, with the manifest settings it needs."""
    index = ManifestIndex(repo)
    jobs = []
    for scope in scopes:
        lock = locks[scope]
        if not any(
            entry.path.startswith(_SOURCES_PREFIX)
            and Path(entry.path).suffix.lower() in {".html", ".htm", ""}
            for entry in lock.files
        ):
            continue
        stems = _html_stems(lock)
        manifest = manifest_named_by_ingest(repo, scope)
        named = index.documents_of(manifest) if manifest else {}
        manifest_settings = {stem: named[stem] for stem in stems if stem in named}
        source_id_settings: dict[str, Any] = {}
        for stem in stems:
            if stem in manifest_settings:
                continue
            settings = index.settings_by_source_id(scope[0], scope[1], stem)
            if settings is not False:
                source_id_settings[stem] = settings
        jobs.append((str(repo), scope, manifest, manifest_settings, source_id_settings))
    return jobs


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "scopes", nargs="*", metavar="SCOPE", help="<jurisdiction>[/<class>[/<version>]]"
    )
    parser.add_argument("--all", action="store_true", help="Every locked scope.")
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="The checkout to measure.")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--output", type=Path, required=True, help="The JSON report.")
    parser.add_argument("--csv", type=Path, help="Also write the per-scope ranking as CSV.")
    args = parser.parse_args(argv)
    if not args.all and not args.scopes:
        parser.error("name one or more scopes, or pass --all")
    if args.workers < 1:
        parser.error("--workers must be positive")

    repo = args.repo.resolve()
    lock_set = load_locks(repo)
    if lock_set.errors:
        print("invalid corpus locks: " + "; ".join(lock_set.errors[:5]), file=sys.stderr)
        return 2
    selectors = [parse_scope_selector(text) for text in args.scopes]
    scopes = sorted(
        scope
        for scope in lock_set.locks
        if args.all or any(scope_matches(scope, selector) for selector in selectors)
    )
    jobs = plan(repo, scopes, lock_set.locks)
    print(
        f"{len(scopes)} locked scopes selected, {len(jobs)} with HTML-like sources", file=sys.stderr
    )
    if args.workers == 1 or len(jobs) < 2:
        results = [_job(job) for job in jobs]
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            results = list(pool.map(_job, jobs, chunksize=2))

    context = release_context(repo)
    summaries = [
        {**summary, **context[summary["scope"]]}
        for summary in map(summarize_scope, results)
        if summary is not None
    ]
    ranking = rank(summaries)
    report = {
        "measure": SOURCE_COVERAGE_VERSION,
        "review_bar": {"coverage": REVIEW_COVERAGE, "min_region_words": REVIEW_MIN_REGION_WORDS},
        "scopes_selected": len(scopes),
        "scopes_with_html_sources": len(jobs),
        "scopes_measured": len(summaries),
        "scopes_absent": sorted(row["scope"] for row in results if row.get("absent")),
        "scopes_failed": {row["scope"]: row["failed"] for row in results if row.get("failed")},
        "ranking": ranking,
        "scopes": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    if args.csv:
        write_csv(args.csv, ranking)
    for row in ranking[:25]:
        print(
            f"{row['scope']}: {row['sources']} sources ({row['region']}); median "
            f"{row['median']:.2f}, p10 {row['p10']:.2f}; {row['needs_review']} under "
            f"{REVIEW_COVERAGE} of {REVIEW_MIN_REGION_WORDS}+ words"
        )
    if report["scopes_absent"] or report["scopes_failed"]:
        print(
            f"{len(report['scopes_absent'])} scopes absent, "
            f"{len(report['scopes_failed'])} failed (see the report)",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
