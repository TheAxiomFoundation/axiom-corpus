"""Discover encoded RuleSpec paths from local jurisdiction rules repos.

The navigation builder needs to know which provisions have RuleSpec encodings
so it can populate `corpus.navigation_nodes.has_rulespec` and the bottom-up
`encoded_descendant_count`. Today `corpus.provisions.has_rulespec` is mostly
unset because the corpus pipeline doesn't currently track RuleSpec coverage —
the canonical record is a YAML file in a jurisdiction's rules repo.

This module bridges that gap. Given the local checkout of a `rulespec-*` repo
(e.g. `rulespec-us`, `rulespec-us-co`), it walks the encoding directories, filters
out `.test.yaml` / `.meta.yaml` fixtures, and produces canonical corpus
citation paths (`us/statute/26/3111/a`).

Two on-disk layouts are supported, tried in this order:

1. Country monorepo: `<root>/rulespec-<country>/<prefix>/...` — one repo per
   country holding a directory per jurisdiction (`rulespec-us/us/` for federal,
   `rulespec-us/us-ca/`, `rulespec-uk/uk/`, ...), plus shared non-encoding
   directories such as `programs/`.
2. Legacy sibling checkouts: `<root>/rulespec-<prefix>/...` — one repo per
   jurisdiction with encoding buckets at the repo root.

The mapping mirrors the app's `repo-listing.ts` so that browser-side encoded
listings and the navigation index agree on which paths are "encoded".
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

# Canonical jurisdiction slug -> legacy rulespec-* repo directory name. The
# `rulespec-` suffix is also the jurisdiction's repo prefix, which doubles as
# its directory name inside a country monorepo (`rulespec-us/us-ca/`).
# Mirrors axiom-foundation.org/src/lib/axiom/repo-map.ts; keep in sync when
# new jurisdictions get rules repos.
JURISDICTION_REPO_MAP: dict[str, str] = {
    "us": "rulespec-us",
    "uk": "rulespec-uk",
    "canada": "rulespec-ca",
    "us-al": "rulespec-us-al",
    "us-ar": "rulespec-us-ar",
    "us-ca": "rulespec-us-ca",
    "us-co": "rulespec-us-co",
    "us-fl": "rulespec-us-fl",
    "us-ga": "rulespec-us-ga",
    "us-md": "rulespec-us-md",
    "us-nc": "rulespec-us-nc",
    "us-ny": "rulespec-us-ny",
    "us-sc": "rulespec-us-sc",
    "us-tn": "rulespec-us-tn",
    "us-tx": "rulespec-us-tx",
}

# Top-level bucket directory name -> citation_path bucket segment.
# Plural in the rules repo convention; singular in the corpus convention.
BUCKET_TO_CITATION_BUCKET: dict[str, str] = {
    "statutes": "statute",
    "regulations": "regulation",
    "policies": "policy",
}

# File suffixes that are RuleSpec source. Anything else (.test.yaml,
# .meta.yaml, README.md, scripts/, etc.) is skipped.
_EXCLUDED_SUFFIXES: tuple[str, ...] = (".test.yaml", ".meta.yaml")

# Repo suffixes (`rulespec-<prefix>`) for every known jurisdiction. In a
# country monorepo these double as the per-jurisdiction directory names.
_KNOWN_REPO_PREFIXES: frozenset[str] = frozenset(
    name.removeprefix("rulespec-") for name in JURISDICTION_REPO_MAP.values()
)

# Repo-root directories in a country monorepo that hold shared (non-encoding)
# content next to the per-jurisdiction directories.
_MONOREPO_SHARED_DIRS: frozenset[str] = frozenset({"programs"})


def repo_prefix_for_jurisdiction(jurisdiction: str) -> str | None:
    """Return the ``rulespec-*`` repo suffix for a jurisdiction slug.

    Most slugs are their own prefix (``us-ca`` -> ``us-ca``); ``canada``
    maps to ``rulespec-ca`` so its prefix is ``ca``. In a country monorepo
    the prefix is also the jurisdiction's directory name.
    """
    repo_dir_name = JURISDICTION_REPO_MAP.get(jurisdiction)
    if repo_dir_name is None:
        return None
    return repo_dir_name.removeprefix("rulespec-")


def monorepo_dir_name_for_jurisdiction(jurisdiction: str) -> str | None:
    """Return the country monorepo directory name for a jurisdiction slug.

    The country is the prefix up to the first ``-``: ``us-ca`` lives in
    ``rulespec-us``, ``canada`` (prefix ``ca``) lives in ``rulespec-ca``.
    """
    prefix = repo_prefix_for_jurisdiction(jurisdiction)
    if prefix is None:
        return None
    country = prefix.split("-", 1)[0]
    return f"rulespec-{country}"


def resolve_jurisdiction_dir(
    rulespec_root: str | Path,
    jurisdiction: str,
) -> Path | None:
    """Resolve the directory holding a jurisdiction's encodings under a root.

    ``rulespec_root`` is a directory containing ``rulespec-*`` checkouts.
    Candidates are tried in order:

    1. Country monorepo layout: ``<root>/rulespec-<country>/<prefix>/``
    2. Legacy sibling layout:   ``<root>/rulespec-<prefix>/``

    Returns ``None`` when the jurisdiction is unknown or neither layout is
    on disk.
    """
    root = Path(rulespec_root)
    prefix = repo_prefix_for_jurisdiction(jurisdiction)
    if prefix is None:
        return None
    candidates: list[Path] = []
    monorepo_dir_name = monorepo_dir_name_for_jurisdiction(jurisdiction)
    if monorepo_dir_name is not None:
        candidates.append(root / monorepo_dir_name / prefix)
    candidates.append(root / f"rulespec-{prefix}")
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return None


def discover_encoded_paths(
    repo_root: str | Path,
    jurisdiction: str,
) -> set[str]:
    """Walk ``repo_root`` and return canonical corpus citation paths.

    ``repo_root`` may be a legacy per-jurisdiction checkout (buckets at the
    repo root), a country monorepo checkout (the jurisdiction's content under
    ``<repo>/<prefix>/``), or a monorepo jurisdiction directory itself.

    A path qualifies when its file ends in ``.yaml`` and is not a test or
    meta overlay. Buckets outside `BUCKET_TO_CITATION_BUCKET` (e.g. an
    accidental ``scripts/`` checkin) pass through unchanged so callers can
    spot weird shapes in the data without crashing the build. Sibling
    jurisdiction directories and shared monorepo directories (``programs/``)
    are skipped so a partially migrated monorepo can't leak another
    jurisdiction's encodings into this jurisdiction's citation paths.

    Returns an empty set when the repo path doesn't exist — keeps the
    builder resilient to a missing optional checkout.
    """
    root = Path(repo_root)
    if not root.is_dir():
        return set()

    prefix = repo_prefix_for_jurisdiction(jurisdiction) or jurisdiction
    jurisdiction_dir = root / prefix
    if jurisdiction_dir.is_dir():
        # Country monorepo checkout: walk only this jurisdiction's directory.
        root = jurisdiction_dir

    encoded: set[str] = set()
    for yaml_path in root.rglob("*.yaml"):
        rel = yaml_path.relative_to(root).as_posix()
        if _is_excluded(rel):
            continue
        if _is_under_hidden_or_tests(rel):
            continue
        if _is_under_monorepo_sibling_dir(rel, prefix):
            continue
        citation = _repo_path_to_citation_path(rel, jurisdiction)
        if citation is not None:
            encoded.add(citation)
    return encoded


def discover_encoded_paths_for_jurisdictions(
    rulespec_root: str | Path,
    jurisdictions: Iterable[str],
) -> dict[str, set[str]]:
    """Discover encoded paths for several jurisdictions under one root dir.

    ``rulespec_root`` is the parent directory containing ``rulespec-*``
    checkouts — country monorepos (``rulespec-us/us-ca/...``), legacy sibling
    checkouts (``rulespec-us-ca/...``), or a mix during the transition; see
    ``resolve_jurisdiction_dir`` for the candidate order. Jurisdictions that
    don't have an entry in ``JURISDICTION_REPO_MAP`` (or whose repo isn't on
    disk in either layout) get an empty set.
    """
    root = Path(rulespec_root)
    out: dict[str, set[str]] = {}
    for jurisdiction in jurisdictions:
        candidate = resolve_jurisdiction_dir(root, jurisdiction)
        if candidate is None:
            out[jurisdiction] = set()
            continue
        out[jurisdiction] = discover_encoded_paths(candidate, jurisdiction)
    return out


def _is_excluded(relative_path: str) -> bool:
    return relative_path.endswith(_EXCLUDED_SUFFIXES)


def _is_under_hidden_or_tests(relative_path: str) -> bool:
    parts = relative_path.split("/")
    if not parts:
        return False
    # Skip dotfiles/dirs and the conventional ``tests/`` fixture root.
    return any(part.startswith(".") or part == "tests" for part in parts[:-1])


def _is_under_monorepo_sibling_dir(relative_path: str, prefix: str) -> bool:
    """Detect monorepo content that belongs to another jurisdiction.

    When a country monorepo is walked at its root (a partially migrated repo
    whose own content still sits at the top level), per-jurisdiction
    directories (``us-ca/``, ``uk-kingston-upon-thames/``) and shared
    directories (``programs/``) must not be misread as encoding buckets of
    the jurisdiction being walked.
    """
    head = relative_path.split("/", 1)[0]
    if head == prefix:
        return False
    if head in _MONOREPO_SHARED_DIRS or head in _KNOWN_REPO_PREFIXES:
        return True
    country = prefix.split("-", 1)[0]
    return head == country or head.startswith(f"{country}-")


def _repo_path_to_citation_path(relative_path: str, jurisdiction: str) -> str | None:
    """Translate ``statutes/7/2014/e/2.yaml`` into ``us/statute/7/2014/e/2``.

    Returns ``None`` for paths that don't have a leading bucket segment we
    recognise as containing RuleSpec encodings (e.g. a stray top-level
    ``CLAUDE.md`` ignored above, or a file directly at the repo root).
    """
    if not relative_path.endswith(".yaml"):
        return None
    stripped = relative_path[: -len(".yaml")]
    segments = stripped.split("/")
    if len(segments) < 2:
        return None
    repo_bucket = segments[0]
    citation_bucket = BUCKET_TO_CITATION_BUCKET.get(repo_bucket, repo_bucket)
    tail = list(segments[1:])
    tail = _normalize_tail(tail, jurisdiction=jurisdiction, repo_bucket=repo_bucket)
    if not tail:
        return f"{jurisdiction}/{citation_bucket}"
    return f"{jurisdiction}/{citation_bucket}/" + "/".join(tail)


def _normalize_tail(
    tail: list[str],
    *,
    jurisdiction: str,
    repo_bucket: str,
) -> list[str]:
    """Apply jurisdiction-specific tweaks so paths agree with the corpus.

    ``rulespec-us/regulations/7-cfr/...`` lands as ``us/regulation/7/...`` in the
    corpus — the publication-system suffix gets dropped on the title.
    Mirrors the app's ``normaliseTitleSegment``.
    """
    if not tail:
        return tail
    if jurisdiction == "us" and repo_bucket == "regulations":
        tail = list(tail)
        tail[0] = tail[0].removesuffix("-cfr")
    return tail
