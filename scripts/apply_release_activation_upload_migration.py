"""Install the private chunk transport required for large release activation."""

from __future__ import annotations

import os
from pathlib import Path

from axiom_corpus.corpus.supabase import (
    DEFAULT_ACCESS_TOKEN_ENV,
    DEFAULT_AXIOM_SUPABASE_URL,
    apply_release_activation_upload_migration,
)

MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "supabase/migrations/20260722021000_chunked_release_activation_upload.sql"
)


def main() -> int:
    access_token = os.environ.get(DEFAULT_ACCESS_TOKEN_ENV)
    if not access_token:
        raise SystemExit(f"{DEFAULT_ACCESS_TOKEN_ENV} environment variable is required")
    apply_release_activation_upload_migration(
        MIGRATION.read_text(encoding="utf-8"),
        access_token=access_token,
        supabase_url=DEFAULT_AXIOM_SUPABASE_URL,
        expected_project_ref="swocpijqqahhuwtuahwc",
    )
    print("Release activation upload schema is ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
