"""Repository release policy the release gate reads: withdrawn scopes and the content baseline.

Tracked files decide what ``validate_release`` accepts beyond a scope's own
artifacts (docs/release-gate-policy.md):

``manifests/withdrawn-scopes.yaml``
    Scopes no new release may select, each with its reason, the decision that
    withdrew it (``withdrawn_on``), the day the entry was written
    (``listed_on``), its run note, and what a cut puts in its place. Tracked
    selectors are immutable, so every selector that reached ``main`` before the
    entry did and selects the scope keeps it: it is listed under
    ``grandfathered_selectors`` and pinned by its selector digest, so the
    allowance cannot follow a selector that is edited later. Some of these were
    cut after the decision but before the gate existed. A selector that reaches
    ``main`` later may keep the scope only as a named ``exception`` that gives a
    reason.
``manifests/release-content-baseline.json``
    The content findings (``axiom_corpus.corpus.content_quality``) of every
    locked scope when the content gate began, findings or none, each pinned to
    the sha256 of the scope's provisions and inventory files under one check
    version. The inventory pins every source file's sha256, and validation
    checks the sources against it, so the two digests pin all the bytes the
    checks read. A release may carry a scope's recorded findings; a scope the
    baseline does not list, or whose bytes differ from its entry, is checked
    again, and then every finding fails the release, recorded or not. Listing clean scopes lets validation skip
    re-reading them; a new scope with no findings needs no entry.
``manifests/reviewed-empty-nodes.yaml``
    Bodyless ``document`` rows that review found correctly empty (a table of
    contents, an index of separate documents, a cross-reference stub, a
    reserved, deleted or repealed item, a page whose content area is empty),
    each with its reason and the run note that records the review. Such a row
    is not a ``hollow_document_root`` finding, so the baseline does not pin it;
    validation reports the scope's reviewed rows as a notice. An entry that no
    longer names a hollow root fails ``content-check --check-baseline``. The
    file is optional: without it every hollow root is a finding.

No file lists a scope it does not need to. A checkout without them validates
as before, with an empty policy.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from axiom_corpus.corpus.content_quality import (
    CONTENT_CHECK_VERSION,
    FINDING_CODES,
    ContentFinding,
)
from axiom_corpus.corpus.releases import ReleaseManifest, ReleaseScope, ScopeKey
from axiom_corpus.release.manifest import selector_sha256

WITHDRAWN_SCOPES_PATH = Path("manifests") / "withdrawn-scopes.yaml"
CONTENT_BASELINE_PATH = Path("manifests") / "release-content-baseline.json"
WITHDRAWN_SCOPES_SCHEMA = "axiom-corpus/withdrawn-scopes/v1"
CONTENT_BASELINE_SCHEMA = "axiom-corpus/release-content-baseline/v1"
REVIEWED_EMPTY_PATH = Path("manifests") / "reviewed-empty-nodes.yaml"
REVIEWED_EMPTY_SCHEMA = "axiom-corpus/reviewed-empty-nodes/v1"
# Why review found a bodyless document row correctly empty: the official node
# has no operative text of its own.
REVIEWED_EMPTY_REASONS = frozenset(
    {
        "table_of_contents",  # the source's table of contents
        "index",  # a heading or page that only links to separate documents
        "cross_reference",  # a "see" or relocation stub whose target is elsewhere
        "reserved",  # a reserved item
        "deleted",  # a deleted item: only a deletion marker is left
        "repealed",  # a repealed part: only its repeal notice and history
        "empty_in_source",  # the official page's content area is empty
    }
)

_WITHDRAWN_FIELDS = {"schema_version", "selector_digests", "scopes"}
_ENTRY_FIELDS = {
    "scope",
    "withdrawn_on",
    "listed_on",
    "decision",
    "reason",
    "run_note",
    "replace_with",
    "carried_by",
    "grandfathered_selectors",
    "exceptions",
}
_ENTRY_REQUIRED = {"scope", "withdrawn_on", "listed_on", "decision", "reason", "run_note"}
_EXCEPTION_FIELDS = {"selector", "reason"}


class ReleasePolicyError(ValueError):
    """A release policy file is malformed."""


def parse_scope(value: object, *, where: str) -> ReleaseScope:
    """Parse ``<jurisdiction>/<document_class>/<version>``."""
    if not isinstance(value, str) or value.count("/") < 2:
        raise ReleasePolicyError(f"{where}: scope must be jurisdiction/document_class/version")
    jurisdiction, document_class, version = value.split("/", 2)
    try:
        return ReleaseScope(jurisdiction, document_class, version)
    except ValueError as exc:
        raise ReleasePolicyError(f"{where}: {exc}") from exc


def scope_label(scope: ReleaseScope | ScopeKey) -> str:
    key = scope.key if isinstance(scope, ReleaseScope) else scope
    return "/".join(key)


@dataclass(frozen=True)
class SelectorAllowance:
    """A tracked selector that may keep a withdrawn scope."""

    name: str
    selector_sha256: str
    reason: str | None = None

    @property
    def is_exception(self) -> bool:
        return self.reason is not None


@dataclass(frozen=True)
class WithdrawnScope:
    """One scope no new release may select."""

    scope: ReleaseScope
    withdrawn_on: str
    listed_on: str
    decision: str
    reason: str
    run_note: str
    replace_with: tuple[ReleaseScope, ...] = ()
    carried_by: tuple[ReleaseScope, ...] = ()
    allowances: Mapping[str, SelectorAllowance] = field(default_factory=dict)

    def allowance_for(self, release: ReleaseManifest) -> SelectorAllowance | None:
        """The allowance that lets ``release`` keep this scope, if it has one.

        An allowance holds only for the exact selector it names: same name and
        same selector digest.
        """
        allowance = self.allowances.get(release.name)
        if allowance is None or allowance.selector_sha256 != selector_sha256(release):
            return None
        return allowance

    def remedy(self) -> str:
        """How a new cut replaces this scope, for the gate's error message."""
        parts = []
        if self.replace_with:
            parts.append(
                "select "
                + ", ".join(scope_label(scope) for scope in self.replace_with)
                + " in its place"
            )
        else:
            parts.append("drop it; nothing replaces it")
        if self.carried_by:
            parts.append(
                "its text is carried by "
                + ", ".join(scope_label(scope) for scope in self.carried_by)
            )
        return "; ".join(parts)


@dataclass(frozen=True)
class ContentBaselineEntry:
    """The known content findings of one locked scope, possibly none.

    ``reviewed_empty`` is set only on a fresh scan (``scan_scope``): the hollow
    roots the reviewed-empty list exempted from ``findings``. The baseline file
    does not record it, and it takes no part in comparing entries.
    """

    scope: ReleaseScope
    provisions_sha256: str
    inventory_sha256: str
    findings: tuple[ContentFinding, ...] = ()
    reviewed_empty: tuple[str, ...] = field(default=(), compare=False)

    def pins(self, provisions_sha256: str, inventory_sha256: str) -> bool:
        return (self.provisions_sha256, self.inventory_sha256) == (
            provisions_sha256,
            inventory_sha256,
        )


@dataclass(frozen=True)
class ContentBaseline:
    check_version: str
    entries: Mapping[ScopeKey, ContentBaselineEntry]

    def entry_for(self, scope: ReleaseScope) -> ContentBaselineEntry | None:
        return self.entries.get(scope.key)


@dataclass(frozen=True)
class ReviewedEmptyNode:
    """A bodyless document row that review found correctly empty."""

    path: str
    reason: str
    note: str


@dataclass(frozen=True)
class ReviewedEmptyScope:
    """The reviewed-empty rows of one scope, and the run note that records the review."""

    scope: ReleaseScope
    run_note: str
    nodes: tuple[ReviewedEmptyNode, ...]

    @property
    def paths(self) -> frozenset[str]:
        return frozenset(node.path for node in self.nodes)


@dataclass(frozen=True)
class ReleaseGatePolicy:
    """Everything the release gate reads from the repository besides scope artifacts."""

    withdrawn: Mapping[ScopeKey, WithdrawnScope] = field(default_factory=dict)
    content_baseline: ContentBaseline = field(
        default_factory=lambda: ContentBaseline(CONTENT_CHECK_VERSION, {})
    )
    source: str | None = None
    reviewed_empty: Mapping[ScopeKey, ReviewedEmptyScope] = field(default_factory=dict)

    def reviewed_empty_paths(self, scope: ReleaseScope | ScopeKey) -> frozenset[str]:
        """Citation paths of ``scope``'s rows reviewed as correctly empty."""
        key = scope.key if isinstance(scope, ReleaseScope) else scope
        entry = self.reviewed_empty.get(key)
        return entry.paths if entry is not None else frozenset()

    @classmethod
    def empty(cls) -> ReleaseGatePolicy:
        return cls()

    @classmethod
    def load(cls, repo_root: str | Path, *, required: bool = False) -> ReleaseGatePolicy:
        """Read the policy files of a checkout; an absent file is an empty policy.

        With ``required``, an absent withdrawn-scope list or content baseline is
        an error instead: publication from a checkout that holds corpus locks
        must not silently skip the policy. The reviewed-empty list is never
        required: without it no hollow root is exempt, which only adds findings.
        """
        root = Path(repo_root)
        withdrawn_path = root / WITHDRAWN_SCOPES_PATH
        baseline_path = root / CONTENT_BASELINE_PATH
        if required:
            missing = [str(path) for path in (withdrawn_path, baseline_path) if not path.is_file()]
            if missing:
                raise ReleasePolicyError(f"release policy files are missing: {missing}")
        withdrawn = load_withdrawn_scopes(withdrawn_path) if withdrawn_path.exists() else {}
        baseline = (
            load_content_baseline(baseline_path)
            if baseline_path.exists()
            else ContentBaseline(CONTENT_CHECK_VERSION, {})
        )
        reviewed_path = root / REVIEWED_EMPTY_PATH
        reviewed = load_reviewed_empty(reviewed_path) if reviewed_path.exists() else {}
        return cls(
            withdrawn=withdrawn,
            content_baseline=baseline,
            source=str(root),
            reviewed_empty=reviewed,
        )

    @classmethod
    def for_checkout(cls, repo_root: str | Path) -> ReleaseGatePolicy:
        """The policy of a checkout, required wherever it keeps corpus locks.

        A checkout whose corpus bytes are pinned by lock files is a real corpus
        checkout: validating or publishing from one that lacks the
        withdrawn-scope list or the content baseline must fail, not run
        against an empty policy.
        """
        from axiom_corpus.corpus.corpus_locks import LOCK_ROOT

        root = Path(repo_root)
        return cls.load(root, required=(root / LOCK_ROOT).is_dir())

    @classmethod
    def for_corpus(cls, corpus_root: str | Path) -> ReleaseGatePolicy:
        """The policy of the axiom-corpus checkout holding ``corpus_root``, if any."""
        from axiom_corpus.corpus.resolver import find_repo_root

        root = Path(corpus_root)
        repo = find_repo_root(root) if root.exists() else None
        return cls.for_checkout(repo) if repo is not None else cls.empty()


def _require_mapping(value: object, where: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ReleasePolicyError(f"{where} must be a mapping")
    return value


def _require_string(value: object, where: str) -> str:
    if isinstance(value, date):
        return value.isoformat()
    if not isinstance(value, str) or not value.strip():
        raise ReleasePolicyError(f"{where} must be a non-empty string")
    return value


def _iso_date(value: object, where: str) -> str:
    """A date as YYYY-MM-DD, so dates compare correctly as text."""
    text = _require_string(value, where)
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise ReleasePolicyError(f"{where} must be an ISO date") from exc


def _string_list(value: object, where: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ReleasePolicyError(f"{where} must be a list of strings")
    return list(value)


def _sorted_unique(values: list[str], where: str) -> None:
    if values != sorted(values) or len(set(values)) != len(values):
        raise ReleasePolicyError(f"{where} must be sorted and free of duplicates")


def _scope_order(label: str) -> tuple[str, ...]:
    return tuple(label.split("/", 2))


def _sorted_unique_scopes(labels: list[str], where: str) -> None:
    """Scope labels sorted as (jurisdiction, document_class, version), each once."""
    if labels != sorted(labels, key=_scope_order) or len(set(labels)) != len(labels):
        raise ReleasePolicyError(
            f"{where} must be sorted by jurisdiction, document class and version, "
            "and free of duplicates"
        )


def load_withdrawn_scopes(path: str | Path) -> dict[ScopeKey, WithdrawnScope]:
    """Parse ``manifests/withdrawn-scopes.yaml``; reject anything malformed."""
    where = str(path)
    data = _require_mapping(yaml.safe_load(Path(path).read_text(encoding="utf-8")), where)
    if set(data) - _WITHDRAWN_FIELDS:
        raise ReleasePolicyError(
            f"{where}: unsupported fields {sorted(set(data) - _WITHDRAWN_FIELDS)}"
        )
    if data.get("schema_version") != WITHDRAWN_SCOPES_SCHEMA:
        raise ReleasePolicyError(f"{where}: schema_version must be {WITHDRAWN_SCOPES_SCHEMA}")
    digests_raw = _require_mapping(data.get("selector_digests") or {}, f"{where}: selector_digests")
    digests = {
        _require_string(name, f"{where}: selector name"): _require_string(
            value, f"{where}: selector_digests.{name}"
        )
        for name, value in digests_raw.items()
    }
    _sorted_unique(list(digests), f"{where}: selector_digests")
    used: set[str] = set()
    raw_entries = data.get("scopes")
    if not isinstance(raw_entries, list) or not raw_entries:
        raise ReleasePolicyError(f"{where}: scopes must be a non-empty list")
    entries: dict[ScopeKey, WithdrawnScope] = {}
    labels: list[str] = []
    for index, raw in enumerate(raw_entries):
        entry_where = f"{where}: scopes[{index}]"
        item = _require_mapping(raw, entry_where)
        if set(item) - _ENTRY_FIELDS:
            raise ReleasePolicyError(
                f"{entry_where}: unsupported fields {sorted(set(item) - _ENTRY_FIELDS)}"
            )
        missing = _ENTRY_REQUIRED - set(item)
        if missing:
            raise ReleasePolicyError(f"{entry_where}: missing {sorted(missing)}")
        scope = parse_scope(item["scope"], where=entry_where)
        labels.append(scope_label(scope))
        withdrawn_on = _iso_date(item["withdrawn_on"], f"{entry_where}.withdrawn_on")
        listed_on = _iso_date(item["listed_on"], f"{entry_where}.listed_on")
        if listed_on < withdrawn_on:
            raise ReleasePolicyError(f"{entry_where}: listed_on precedes withdrawn_on")
        allowances: dict[str, SelectorAllowance] = {}
        grandfathered = _string_list(
            item.get("grandfathered_selectors"), f"{entry_where}.grandfathered_selectors"
        )
        _sorted_unique(grandfathered, f"{entry_where}.grandfathered_selectors")
        for name in grandfathered:
            if name not in digests:
                raise ReleasePolicyError(
                    f"{entry_where}: selector {name} has no selector_digests entry"
                )
            allowances[name] = SelectorAllowance(name, digests[name])
            used.add(name)
        raw_exceptions = item.get("exceptions") or []
        if not isinstance(raw_exceptions, list):
            raise ReleasePolicyError(f"{entry_where}.exceptions must be a list")
        for exception_index, raw_exception in enumerate(raw_exceptions):
            exception_where = f"{entry_where}.exceptions[{exception_index}]"
            exception = _require_mapping(raw_exception, exception_where)
            if set(exception) != _EXCEPTION_FIELDS:
                raise ReleasePolicyError(
                    f"{exception_where} must have exactly {sorted(_EXCEPTION_FIELDS)}"
                )
            name = _require_string(exception["selector"], f"{exception_where}.selector")
            if name in allowances:
                raise ReleasePolicyError(f"{exception_where}: {name} is listed twice")
            if name not in digests:
                raise ReleasePolicyError(
                    f"{exception_where}: selector {name} has no selector_digests entry"
                )
            allowances[name] = SelectorAllowance(
                name,
                digests[name],
                _require_string(exception["reason"], f"{exception_where}.reason"),
            )
            used.add(name)
        entry = WithdrawnScope(
            scope=scope,
            withdrawn_on=withdrawn_on,
            listed_on=listed_on,
            decision=_require_string(item["decision"], f"{entry_where}.decision"),
            reason=" ".join(_require_string(item["reason"], f"{entry_where}.reason").split()),
            run_note=_require_string(item["run_note"], f"{entry_where}.run_note"),
            replace_with=tuple(
                parse_scope(value, where=f"{entry_where}.replace_with")
                for value in _string_list(item.get("replace_with"), f"{entry_where}.replace_with")
            ),
            carried_by=tuple(
                parse_scope(value, where=f"{entry_where}.carried_by")
                for value in _string_list(item.get("carried_by"), f"{entry_where}.carried_by")
            ),
            allowances=allowances,
        )
        entries[scope.key] = entry
    _sorted_unique_scopes(labels, f"{where}: scopes")
    for scope_key, entry in entries.items():
        for other in (*entry.replace_with, *entry.carried_by):
            if other.key in entries:
                raise ReleasePolicyError(
                    f"{where}: {scope_label(scope_key)} points at {scope_label(other)}, "
                    "which is itself withdrawn"
                )
    unused = sorted(set(digests) - used)
    if unused:
        raise ReleasePolicyError(f"{where}: selector_digests lists unused selectors {unused}")
    return entries


_REVIEWED_FIELDS = {"schema_version", "scopes"}
_REVIEWED_SCOPE_FIELDS = {"scope", "run_note", "nodes"}
_REVIEWED_NODE_FIELDS = {"path", "reason", "note"}


def load_reviewed_empty(path: str | Path) -> dict[ScopeKey, ReviewedEmptyScope]:
    """Parse ``manifests/reviewed-empty-nodes.yaml``; reject anything malformed.

    Scopes are sorted by jurisdiction, document class and version, each listed
    once; a scope's nodes are sorted by path, each once, each under the scope's
    jurisdiction and document class, with a known reason and a note.
    """
    where = str(path)
    data = _require_mapping(yaml.safe_load(Path(path).read_text(encoding="utf-8")), where)
    if set(data) != _REVIEWED_FIELDS:
        raise ReleasePolicyError(f"{where}: fields must be {sorted(_REVIEWED_FIELDS)}")
    if data["schema_version"] != REVIEWED_EMPTY_SCHEMA:
        raise ReleasePolicyError(f"{where}: schema_version must be {REVIEWED_EMPTY_SCHEMA}")
    raw_scopes = data["scopes"]
    if not isinstance(raw_scopes, list):
        raise ReleasePolicyError(f"{where}: scopes must be a list")
    entries: dict[ScopeKey, ReviewedEmptyScope] = {}
    labels: list[str] = []
    for index, raw in enumerate(raw_scopes):
        entry_where = f"{where}: scopes[{index}]"
        item = _require_mapping(raw, entry_where)
        if set(item) != _REVIEWED_SCOPE_FIELDS:
            raise ReleasePolicyError(
                f"{entry_where}: fields must be {sorted(_REVIEWED_SCOPE_FIELDS)}"
            )
        scope = parse_scope(item["scope"], where=entry_where)
        labels.append(scope_label(scope))
        raw_nodes = item["nodes"]
        if not isinstance(raw_nodes, list) or not raw_nodes:
            raise ReleasePolicyError(f"{entry_where}.nodes must be a non-empty list")
        prefix = f"{scope.jurisdiction}/{scope.document_class}/"
        nodes = []
        for node_index, raw_node in enumerate(raw_nodes):
            node_where = f"{entry_where}.nodes[{node_index}]"
            node = _require_mapping(raw_node, node_where)
            if set(node) != _REVIEWED_NODE_FIELDS:
                raise ReleasePolicyError(
                    f"{node_where}: fields must be {sorted(_REVIEWED_NODE_FIELDS)}"
                )
            node_path = _require_string(node["path"], f"{node_where}.path")
            if not node_path.startswith(prefix) or node_path != node_path.strip():
                raise ReleasePolicyError(
                    f"{node_where}.path must be a citation path under {prefix}"
                )
            reason = _require_string(node["reason"], f"{node_where}.reason")
            if reason not in REVIEWED_EMPTY_REASONS:
                raise ReleasePolicyError(
                    f"{node_where}.reason must be one of {sorted(REVIEWED_EMPTY_REASONS)}"
                )
            nodes.append(
                ReviewedEmptyNode(
                    path=node_path,
                    reason=reason,
                    note=" ".join(_require_string(node["note"], f"{node_where}.note").split()),
                )
            )
        _sorted_unique([node.path for node in nodes], f"{entry_where}.nodes paths")
        entries[scope.key] = ReviewedEmptyScope(
            scope=scope,
            run_note=_require_string(item["run_note"], f"{entry_where}.run_note"),
            nodes=tuple(nodes),
        )
    _sorted_unique_scopes(labels, f"{where}: scopes")
    return entries


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_content_baseline(path: str | Path) -> ContentBaseline:
    """Parse ``manifests/release-content-baseline.json``; reject anything malformed."""
    where = str(path)
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ReleasePolicyError(f"{where}: {exc}") from exc
    data = _require_mapping(data, where)
    if set(data) != {"schema_version", "check_version", "scopes"}:
        raise ReleasePolicyError(f"{where}: fields must be schema_version, check_version, scopes")
    if data["schema_version"] != CONTENT_BASELINE_SCHEMA:
        raise ReleasePolicyError(f"{where}: schema_version must be {CONTENT_BASELINE_SCHEMA}")
    check_version = _require_string(data["check_version"], f"{where}: check_version")
    scopes = _require_mapping(data["scopes"], f"{where}: scopes")
    _sorted_unique_scopes(list(scopes), f"{where}: scopes")
    entries: dict[ScopeKey, ContentBaselineEntry] = {}
    for label, raw in scopes.items():
        entry_where = f"{where}: scopes.{label}"
        item = _require_mapping(raw, entry_where)
        if set(item) != _BASELINE_ENTRY_FIELDS:
            raise ReleasePolicyError(
                f"{entry_where}: fields must be {sorted(_BASELINE_ENTRY_FIELDS)}"
            )
        scope = parse_scope(label, where=entry_where)
        raw_findings = item["findings"]
        if not isinstance(raw_findings, list):
            raise ReleasePolicyError(f"{entry_where}.findings must be a list")
        findings = []
        for raw_finding in raw_findings:
            if (
                not isinstance(raw_finding, list)
                or len(raw_finding) != 2
                or raw_finding[0] not in FINDING_CODES
                or not isinstance(raw_finding[1], str)
            ):
                raise ReleasePolicyError(f"{entry_where}: each finding must be [code, path]")
            findings.append(ContentFinding(raw_finding[0], raw_finding[1]))
        if findings != sorted(set(findings)):
            raise ReleasePolicyError(f"{entry_where}: findings must be sorted and unique")
        entries[scope.key] = ContentBaselineEntry(
            scope=scope,
            provisions_sha256=_require_digest(
                item["provisions_sha256"], f"{entry_where}.provisions_sha256"
            ),
            inventory_sha256=_require_digest(
                item["inventory_sha256"], f"{entry_where}.inventory_sha256"
            ),
            findings=tuple(findings),
        )
    return ContentBaseline(check_version=check_version, entries=entries)


_BASELINE_ENTRY_FIELDS = {"provisions_sha256", "inventory_sha256", "findings"}


def _require_digest(value: object, where: str) -> str:
    text = _require_string(value, where)
    if len(text) != 64 or any(char not in "0123456789abcdef" for char in text):
        raise ReleasePolicyError(f"{where} must be a lowercase sha256 hex digest")
    return text


def content_baseline_text(
    entries: Iterable[ContentBaselineEntry], *, check_version: str = CONTENT_CHECK_VERSION
) -> str:
    """The canonical text of a baseline: one scope per line, sorted, so diffs stay small."""
    lines = []
    for entry in sorted(entries, key=lambda item: item.scope.key):
        record = {
            "provisions_sha256": entry.provisions_sha256,
            "inventory_sha256": entry.inventory_sha256,
            "findings": [[finding.code, finding.path] for finding in sorted(set(entry.findings))],
        }
        lines.append(
            f"  {json.dumps(scope_label(entry.scope))}: "
            f"{json.dumps(record, ensure_ascii=False, separators=(', ', ': '))}"
        )
    header = (
        "{\n"
        f'"schema_version": {json.dumps(CONTENT_BASELINE_SCHEMA)},\n'
        f'"check_version": {json.dumps(check_version)},\n'
        '"scopes": {\n'
    )
    return header + ",\n".join(lines) + ("\n" if lines else "") + "}\n}\n"


def write_content_baseline(path: str | Path, entries: Iterable[ContentBaselineEntry]) -> None:
    Path(path).write_text(content_baseline_text(entries), encoding="utf-8")


def scan_scope(
    corpus_root: str | Path,
    scope: ReleaseScope | ScopeKey,
    *,
    reviewed_empty: Iterable[str] = (),
) -> ContentBaselineEntry:
    """Run the content checks over one scope and pin the result to its bytes.

    ``reviewed_empty`` is the scope's reviewed-empty rows
    (``ReleaseGatePolicy.reviewed_empty_paths``); the hollow roots among them
    are left out of ``findings`` and reported in ``reviewed_empty``.
    """
    from axiom_corpus.corpus.artifacts import CorpusArtifactStore
    from axiom_corpus.corpus.content_quality import ScopeContentScanner
    from axiom_corpus.corpus.io import iter_provisions

    release_scope = scope if isinstance(scope, ReleaseScope) else ReleaseScope(*scope)
    store = CorpusArtifactStore(corpus_root)
    key = release_scope.key
    provisions_path = store.provisions_path(*key)
    inventory_path = store.inventory_path(*key)
    scanner = ScopeContentScanner(store.root, reviewed_empty=reviewed_empty)
    for record in iter_provisions(provisions_path):
        scanner.add(record)
    return ContentBaselineEntry(
        scope=release_scope,
        provisions_sha256=sha256_file(provisions_path),
        inventory_sha256=sha256_file(inventory_path),
        findings=scanner.findings(),
        reviewed_empty=scanner.reviewed_empty_roots(),
    )


@dataclass(frozen=True)
class BaselineDifference:
    """One way the content baseline disagrees with the corpus."""

    scope: str
    problem: str


def compare_content_baseline(
    baseline: ContentBaseline,
    scanned: Mapping[ScopeKey, ContentBaselineEntry],
    *,
    locked_scopes: Iterable[ScopeKey],
    reviewed_empty: Mapping[ScopeKey, ReviewedEmptyScope] | None = None,
) -> list[BaselineDifference]:
    """Every disagreement between ``baseline`` and fresh scans of the locked scopes.

    The baseline holds when its check version is current, every entry names a
    locked scope and matches that scope's scan exactly (digests and findings),
    and every locked scope it does not list scans clean. The reviewed-empty
    list holds when every scope it names is locked and every row it lists is
    a hollow root the scan exempted (``scanned`` comes from ``scan_scope`` with
    the same list), so a row that gains text below it, or a mistyped path,
    cannot stay exempt.
    """
    differences: list[BaselineDifference] = []
    if baseline.check_version != CONTENT_CHECK_VERSION:
        differences.append(
            BaselineDifference(
                "*",
                f"check_version is {baseline.check_version}, but the checks are "
                f"{CONTENT_CHECK_VERSION}; rebuild the baseline",
            )
        )
    locked = set(locked_scopes)
    reviewed = reviewed_empty or {}
    for key in sorted(set(baseline.entries) - locked):
        differences.append(BaselineDifference(scope_label(key), "listed but not locked"))
    for key in sorted(set(reviewed) - locked):
        differences.append(
            BaselineDifference(scope_label(key), f"listed in {REVIEWED_EMPTY_PATH} but not locked")
        )
    for key in sorted(set(reviewed) & locked):
        entry = scanned.get(key)
        if entry is None:
            continue
        stale = sorted(reviewed[key].paths - set(entry.reviewed_empty))
        if stale:
            differences.append(
                BaselineDifference(
                    scope_label(key),
                    f"{len(stale)} rows in {REVIEWED_EMPTY_PATH} are not hollow document "
                    f"roots: {', '.join(stale)}",
                )
            )
    for key in sorted(locked):
        entry = scanned.get(key)
        if entry is None:
            continue
        recorded = baseline.entries.get(key)
        if recorded is None:
            if entry.findings:
                counts = ", ".join(
                    f"{count} {code}"
                    for code, count in sorted(_count_codes(entry.findings).items())
                )
                differences.append(
                    BaselineDifference(scope_label(key), f"unrecorded content findings: {counts}")
                )
            continue
        if not recorded.pins(entry.provisions_sha256, entry.inventory_sha256):
            differences.append(
                BaselineDifference(scope_label(key), "provisions or inventory bytes changed")
            )
        elif recorded.findings != entry.findings:
            added = sorted(set(entry.findings) - set(recorded.findings))
            removed = sorted(set(recorded.findings) - set(entry.findings))
            differences.append(
                BaselineDifference(
                    scope_label(key),
                    f"findings differ: {len(added)} new, {len(removed)} no longer found",
                )
            )
    return differences


def _count_codes(findings: Iterable[ContentFinding]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding.code] = counts.get(finding.code, 0) + 1
    return counts


def selectors_selecting(releases_dir: str | Path, scope: ReleaseScope) -> dict[str, str]:
    """Tracked selectors under ``releases_dir`` that select ``scope``, with their digests."""
    found: dict[str, str] = {}
    for path in sorted(Path(releases_dir).glob("*.json")):
        release = ReleaseManifest.load(path)
        if scope.key in release.scope_keys:
            found[release.name] = selector_sha256(release)
    return found
