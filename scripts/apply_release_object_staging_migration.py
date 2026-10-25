"""Install the private signed-release registration RPC."""

from __future__ import annotations

import os
from pathlib import Path

from axiom_corpus.corpus.supabase import (
    DEFAULT_ACCESS_TOKEN_ENV,
    DEFAULT_AXIOM_SUPABASE_URL,
    _management_api_post_json_with_curl,
    _project_ref_from_url,
)

MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "supabase/migrations/20260803175000_stage_signed_release_object.sql"
)
EXPECTED_PROJECT_REF = "swocpijqqahhuwtuahwc"
REQUIRED_FRAGMENTS = (
    "CREATE OR REPLACE FUNCTION corpus.stage_corpus_release_object",
    "INSERT INTO corpus.release_objects",
    "REVOKE EXECUTE ON FUNCTION corpus.stage_corpus_release_object(jsonb)",
)


def main() -> int:
    access_token = os.environ.get(DEFAULT_ACCESS_TOKEN_ENV)
    if not access_token:
        raise SystemExit(f"{DEFAULT_ACCESS_TOKEN_ENV} environment variable is required")
    project_ref = _project_ref_from_url(DEFAULT_AXIOM_SUPABASE_URL)
    if project_ref != EXPECTED_PROJECT_REF:
        raise SystemExit(
            f"refusing to migrate Supabase project {project_ref!r}: "
            f"expected {EXPECTED_PROJECT_REF!r}"
        )
    migration = MIGRATION.read_text(encoding="utf-8")
    if any(fragment not in migration for fragment in REQUIRED_FRAGMENTS):
        raise SystemExit("signed release object staging migration is incomplete")
    rows = _management_api_post_json_with_curl(
        f"https://api.supabase.com/v1/projects/{project_ref}/database/query",
        payload={"query": migration, "read_only": False},
        access_token=access_token,
        timeout=120,
    )
    if rows != []:
        raise SystemExit(f"unexpected release object staging migration response: {rows!r}")
    print("Signed release object staging schema is ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
