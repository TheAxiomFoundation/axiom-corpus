"""Committed provision ids must follow the deterministic identity convention.

On-disk rows carry the *legacy* deterministic id — ``uuid5(NAMESPACE_URL,
"axiom:" + citation_path)`` — and ``provision_to_supabase_row`` converges
that to a version-qualified id at load time so one citation can exist in
several published versions.

An id that is neither absent, nor the legacy form, nor the version-qualified
form is passed through to Supabase verbatim, which silently defeats
version-qualification: the row then carries the SAME primary key in every
version it appears in. The first publish wins and every later one dies with
``duplicate key value violates unique constraint "rules_pkey"`` — and because
published scope keys are immutable, the scope can only be recovered by
re-versioning it.

A pre-convention CFR ingest stamped ``uuid5(NAMESPACE_URL, citation_path)``
(no ``axiom:`` prefix) on 21 rows. The 14 in the re-versioned CMS 2454 scope
are fixed here; the remaining 7 sit in already-published scopes whose
artifacts are frozen, so they are pinned as a shrinking allowlist and tracked
in the linked issue — they must be restamped as part of re-versioning those
scopes, never in place.
"""

import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from axiom_corpus.corpus.supabase import deterministic_provision_id

PROVISIONS_ROOT = Path(__file__).resolve().parents[1] / "data" / "corpus" / "provisions"

# Rows whose ids predate the convention and live in published (frozen) scopes.
# Restamp each one when its scope is next re-versioned, then drop it here.
# Tracked in TheAxiomFoundation/axiom-corpus#374.
KNOWN_PRE_CONVENTION_ROWS = {
    # Pre-convention CFR ingest: uuid5 of the bare citation path.
    ("us-ny/policy/2026-06-05-ny-tanf.jsonl", 4),
    ("us-ma/guidance/2025-11-17-dta-policy-online-snap-cola-sua-heating-cooling.jsonl", 1),
    ("us-ma/guidance/2025-11-17-dta-policy-online-snap-cola.jsonl", 1),
    ("us-ma/regulation/2026-05-28-365-180-children.jsonl", 1),
    # Opaque ids from an unidentified writer — same publish-time hazard.
    ("ca/policy/2026-07-05-cra-2025-child-care-expenses-deduction.jsonl", 1),
    ("ca/policy/2026-07-05-cra-2025-moving-expenses-deduction.jsonl", 1),
}


def _prefixless_id(citation_path: str) -> str:
    """The pre-convention id: the citation path without the `axiom:` prefix."""
    return str(uuid5(NAMESPACE_URL, citation_path))


def test_committed_provision_ids_follow_the_identity_convention():
    offenders: dict[str, int] = {}
    for path in sorted(PROVISIONS_ROOT.rglob("*.jsonl")):
        for line in path.open():
            row = json.loads(line)
            row_id = row.get("id")
            if not row_id:
                continue
            citation_path = row.get("citation_path")
            version = row.get("version")
            if row_id in (
                deterministic_provision_id(citation_path),
                deterministic_provision_id(citation_path, version),
            ):
                continue
            key = str(path.relative_to(PROVISIONS_ROOT))
            offenders[key] = offenders.get(key, 0) + 1

    assert set(offenders.items()) == KNOWN_PRE_CONVENTION_ROWS, (
        "Provision ids must be the legacy deterministic id "
        '(uuid5(NAMESPACE_URL, "axiom:" + citation_path)) so the Supabase loader can '
        "version-qualify them. A non-conforming id is written to Supabase verbatim and "
        "collides across versions (rules_pkey), which is only recoverable by re-versioning "
        "the scope. Unexpected offenders:\n"
        + "\n".join(
            f"  {name}: {count} row(s)"
            for name, count in sorted(set(offenders.items()) - KNOWN_PRE_CONVENTION_ROWS)
        )
        + "\nAllowlisted rows that are now fixed (drop them from "
        "KNOWN_PRE_CONVENTION_ROWS):\n"
        + "\n".join(
            f"  {name}: {count} row(s)"
            for name, count in sorted(KNOWN_PRE_CONVENTION_ROWS - set(offenders.items()))
        )
    )


def test_prefixless_ids_are_not_the_convention():
    """The exact defect: a bare-path uuid5 differs from the legacy id."""
    citation_path = "us/regulation/42/435/550"

    assert _prefixless_id(citation_path) != deterministic_provision_id(citation_path)
