"""The registration RPC that publication re-applies on every run accepts v4.

publish.yml and register-release-object.yml run
scripts/apply_release_object_staging_migration.py against production before
registering a signed release object, so the file it applies is the definition
production keeps. It must be the v4-aware one, or the next ordinary
publication reinstalls a function that rejects layered releases; and it must
register v2 and v3 objects exactly as 20260803175000 does.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = REPO_ROOT / "supabase" / "migrations"
V3_MIGRATION = MIGRATIONS / "20260803175000_stage_signed_release_object.sql"
V4_MIGRATION = MIGRATIONS / "20260927100000_stage_signed_release_object_v4.sql"
FUNCTION = "CREATE OR REPLACE FUNCTION corpus.stage_corpus_release_object"


def _script():
    spec = importlib.util.spec_from_file_location(
        "apply_release_object_staging_migration",
        REPO_ROOT / "scripts" / "apply_release_object_staging_migration.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_publication_applies_the_v4_registration_function() -> None:
    script = _script()
    assert script.MIGRATION == V4_MIGRATION
    text = V4_MIGRATION.read_text(encoding="utf-8")
    assert all(fragment in text for fragment in script.REQUIRED_FRAGMENTS)
    assert "'axiom-corpus/release-object/v4'" in script.REQUIRED_FRAGMENTS


def test_v4_registration_registers_v2_and_v3_exactly_as_before() -> None:
    """Undoing the three v4 edits must give back 20260803175000's function."""
    old = V3_MIGRATION.read_text(encoding="utf-8")
    new = V4_MIGRATION.read_text(encoding="utf-8")
    old_function = old[old.index(FUNCTION) :]
    new_function = new[new.index(FUNCTION) :]
    v4_block = new_function[
        new_function.index("  -- A v4 scope is primary without a layer key") : new_function.index(
            "  -- Serialize first publication"
        )
    ]
    reverted = (
        new_function.replace(v4_block, "")
        .replace(
            "  IF p_release_object ->> 'schema_version' IN (\n"
            "    'axiom-corpus/release-object/v3',\n"
            "    'axiom-corpus/release-object/v4'\n"
            "  ) THEN\n",
            "  IF p_release_object ->> 'schema_version' = 'axiom-corpus/release-object/v3' THEN\n",
        )
        .replace(
            "    'axiom-corpus/release-object/v3',\n    'axiom-corpus/release-object/v4'\n",
            "    'axiom-corpus/release-object/v3'\n",
        )
    )
    assert reverted == old_function
    # The insert trigger is not redefined: it stays as 20260803175000 installed it.
    assert "guard_corpus_release_object_insert" not in new.split(FUNCTION)[1]
    assert "CREATE TRIGGER" not in new
