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

Two pre-convention writers left 23 such rows: a CFR ingest that hashed the
bare citation path, and a Canada grounding pass that used an
``axiom-corpus:`` prefix. Neither writer survives — every extractor now goes
through ``deterministic_provision_id`` — and none of the affected scopes had
been cut into a release, so all 23 rows are restamped and this check has no
exceptions. Any new offender is a bug in a writer, not something to
allowlist.

A row whose scope IS already published cannot be restamped in place: main
would diverge from the frozen release object. Fix that case by re-versioning
the scope and restamping as part of the rename.
"""

import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from axiom_corpus.corpus.supabase import deterministic_provision_id

PROVISIONS_ROOT = Path(__file__).resolve().parents[1] / "data" / "corpus" / "provisions"


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

    assert not offenders, (
        "Provision ids must be the legacy deterministic id "
        '(uuid5(NAMESPACE_URL, "axiom:" + citation_path)) so the Supabase loader can '
        "version-qualify them. A non-conforming id is written to Supabase verbatim, so the "
        "row keeps one primary key across versions and every publish after the first dies "
        "on rules_pkey — recoverable only by re-versioning the scope. Fix the writer, then "
        "restamp the rows (in place if the scope was never cut into a release; otherwise as "
        "part of re-versioning it). Offenders:\n"
        + "\n".join(f"  {name}: {count} row(s)" for name, count in sorted(offenders.items()))
    )


def test_prefixless_ids_are_not_the_convention():
    """The exact defect: a bare-path uuid5 differs from the legacy id."""
    citation_path = "us/regulation/42/435/550"

    assert _prefixless_id(citation_path) != deterministic_provision_id(citation_path)
