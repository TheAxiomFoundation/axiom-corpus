"""Regression tests for the backlog-publish health fixes.

Covers the three failure classes seen in the June-30 workflow_dispatch backlog:
  * 23505 duplicate key on UNIQUE(citation_path)  -> preserve-existing-ids upsert
  * 22023 "time zone not recognized"              -> date-column coercion
  * 23503 parent_id foreign key not present       -> missing-ancestor synthesis
and the version-aware superseded skip that keeps a backlog safe on rerun.
"""

import axiom_corpus.corpus.supabase as supabase
from axiom_corpus.corpus.models import ProvisionRecord
from axiom_corpus.corpus.supabase import (
    _coerce_date_column_value,
    _version_date_prefix,
    deterministic_provision_id,
    load_provisions_to_supabase,
    provision_to_supabase_row,
    synthesize_missing_ancestor_records,
)


# --------------------------------------------------------------------------- #
# Class 2a — date-column coercion (the version-slug-as-date ingest bug)
# --------------------------------------------------------------------------- #
def test_coerce_date_truncates_version_slug_to_iso_prefix():
    value, original = _coerce_date_column_value(
        "2026-07-01-be-company-car-tax-benefit-guidance"
    )
    assert value == "2026-07-01"
    assert original == "2026-07-01-be-company-car-tax-benefit-guidance"


def test_coerce_date_passes_valid_dates_untouched():
    assert _coerce_date_column_value("2026-07-03") == ("2026-07-03", None)
    assert _coerce_date_column_value("2026-07-01T12:00:00") == (
        "2026-07-01T12:00:00",
        None,
    )
    assert _coerce_date_column_value(None) == (None, None)


def test_coerce_date_nulls_unparseable_values():
    assert _coerce_date_column_value("not-a-date") == (None, "not-a-date")
    # A leading token that looks date-shaped but is not a real calendar date.
    assert _coerce_date_column_value("2026-13-99-x") == (None, "2026-13-99-x")


def test_projection_coerces_bad_expression_date_and_stashes_original():
    record = ProvisionRecord(
        jurisdiction="be",
        document_class="guidance",
        citation_path="be/guidance/spf/company-car/2026-faq",
        version="2026-07-01-be-company-car-tax-benefit-guidance",
        expression_date="2026-07-01-be-company-car-tax-benefit-guidance",
        source_as_of="2026-06-30-be-tax-benefit",
    )

    row = provision_to_supabase_row(record)

    assert row["expression_date"] == "2026-07-01"
    assert row["source_as_of"] == "2026-06-30"
    assert (
        row["identifiers"]["corpus:raw_expression_date"]
        == "2026-07-01-be-company-car-tax-benefit-guidance"
    )
    assert row["identifiers"]["corpus:raw_source_as_of"] == "2026-06-30-be-tax-benefit"
    # The provision text is never touched by metadata coercion.
    assert row["version"] == "2026-07-01-be-company-car-tax-benefit-guidance"


# --------------------------------------------------------------------------- #
# Class 2b — missing-ancestor synthesis
# --------------------------------------------------------------------------- #
def _article(n: str) -> ProvisionRecord:
    return ProvisionRecord(
        jurisdiction="be",
        document_class="statute",
        citation_path=f"be/statute/loi/1978/07/03/1978070303/article/{n}",
        parent_citation_path="be/statute/loi/1978/07/03/1978070303",
        parent_id=deterministic_provision_id(
            "be/statute/loi/1978/07/03/1978070303", "2026-07-05-be-birth-leave"
        ),
        version="2026-07-05-be-birth-leave",
        level=2,
        body="Text.",
    )


def test_synthesize_creates_root_container_matching_child_parent_id():
    records = [_article("52"), _article("101")]

    ancestors = synthesize_missing_ancestor_records(records, known_paths=set())

    assert len(ancestors) == 1
    container = ancestors[0]
    assert container.citation_path == "be/statute/loi/1978/07/03/1978070303"
    assert container.parent_citation_path is None  # root
    assert container.level == 1
    assert container.id == records[0].parent_id
    assert container.identifiers == {
        "corpus:synthesized_container": "missing-parent-backfill"
    }


def test_synthesize_skips_parents_already_in_records_or_db():
    records = [
        _article("52"),
        ProvisionRecord(
            jurisdiction="be",
            document_class="statute",
            citation_path="be/statute/loi/1978/07/03/1978070303",
            version="2026-07-05-be-birth-leave",
            level=1,
        ),
    ]
    # Parent is defined in-file -> nothing to synthesize.
    assert synthesize_missing_ancestor_records(records, known_paths=set()) == []
    # Parent already live in the DB -> nothing to synthesize.
    assert (
        synthesize_missing_ancestor_records(
            [_article("52")],
            known_paths={"be/statute/loi/1978/07/03/1978070303"},
        )
        == []
    )


def test_synthesized_container_projects_to_child_parent_id_in_both_modes():
    child = _article("52")
    container = synthesize_missing_ancestor_records([child], known_paths=set())[0]
    # Versioned ids (default): both recompute from (path, version) -> identical.
    assert (
        provision_to_supabase_row(container, versioned_ids=True)["id"]
        == provision_to_supabase_row(child, versioned_ids=True)["parent_id"]
    )
    # Preserved ids: container keeps the copied uuid == child's parent_id.
    assert (
        provision_to_supabase_row(container, versioned_ids=False)["id"]
        == provision_to_supabase_row(child, versioned_ids=False)["parent_id"]
    )


# --------------------------------------------------------------------------- #
# Version prefix helper
# --------------------------------------------------------------------------- #
def test_version_date_prefix():
    assert _version_date_prefix("2026-07-06-ny-tax-article22-core") == "2026-07-06"
    assert _version_date_prefix("2026-05-06") == "2026-05-06"
    assert _version_date_prefix("no-date-here") is None
    assert _version_date_prefix(None) is None


# --------------------------------------------------------------------------- #
# load_provisions_to_supabase — end-to-end record preparation (HTTP mocked)
# --------------------------------------------------------------------------- #
def _capture_loader(monkeypatch, existing_rows):
    """Patch DB access; return a list that collects every upserted row."""
    captured: list[dict] = []
    monkeypatch.setattr(
        supabase,
        "fetch_existing_provision_rows",
        lambda paths, **kw: dict(existing_rows),
    )
    monkeypatch.setattr(
        supabase,
        "upsert_supabase_rows",
        lambda rows, **kw: captured.extend(rows),
    )
    return captured


def test_load_synthesizes_missing_parent_so_fk_resolves(monkeypatch):
    captured = _capture_loader(monkeypatch, existing_rows={})
    records = [_article("52"), _article("101")]

    report = load_provisions_to_supabase(
        records,
        service_key="k",
        refresh=False,
        auto_register_scopes=False,
        preserve_existing_ids=True,
        synthesize_missing_parents=True,
    )

    assert report.synthesized_parents == 1
    by_path = {r["citation_path"]: r for r in captured}
    container = by_path["be/statute/loi/1978/07/03/1978070303"]
    # Every child's parent_id points at a row that is now present in the batch.
    present_ids = {r["id"] for r in captured}
    for art in ("52", "101"):
        child = by_path[f"be/statute/loi/1978/07/03/1978070303/article/{art}"]
        assert child["parent_id"] == container["id"]
        assert child["parent_id"] in present_ids


def test_load_preserves_existing_id_for_reused_citation_path(monkeypatch):
    # A newer version reuses a citation_path already live under an older id.
    existing_id = "11111111-1111-5111-8111-111111111111"
    existing = {
        "be/statute/loi/1978/07/03/1978070303/article/52": {
            "id": existing_id,
            "version": "2026-05-01-old",
        }
    }
    captured = _capture_loader(monkeypatch, existing_rows=existing)

    load_provisions_to_supabase(
        [_article("52")],
        service_key="k",
        refresh=False,
        auto_register_scopes=False,
        preserve_existing_ids=True,
        synthesize_missing_parents=True,
    )

    by_path = {r["citation_path"]: r for r in captured}
    # The reused path upserts in place onto the existing row id (no new id ->
    # no UNIQUE(citation_path) collision).
    assert by_path["be/statute/loi/1978/07/03/1978070303/article/52"]["id"] == existing_id


def test_load_skips_records_superseded_by_a_newer_live_version(monkeypatch):
    existing = {
        "be/statute/loi/1978/07/03/1978070303/article/52": {
            "id": "22222222-2222-5222-8222-222222222222",
            "version": "2026-09-01-newer",  # strictly newer than the candidate
        }
    }
    captured = _capture_loader(monkeypatch, existing_rows=existing)

    report = load_provisions_to_supabase(
        [_article("52")],
        service_key="k",
        refresh=False,
        auto_register_scopes=False,
        preserve_existing_ids=True,
        skip_superseded=True,
    )

    assert report.superseded_skipped == 1
    # The superseded row is never written, so the newer live row is preserved.
    assert all(
        r["citation_path"] != "be/statute/loi/1978/07/03/1978070303/article/52"
        for r in captured
    )


def test_load_replaces_when_candidate_is_newer_than_live(monkeypatch):
    existing = {
        "be/statute/loi/1978/07/03/1978070303/article/52": {
            "id": "33333333-3333-5333-8333-333333333333",
            "version": "2026-05-01-old",  # older than the 2026-07-05 candidate
        }
    }
    captured = _capture_loader(monkeypatch, existing_rows=existing)

    report = load_provisions_to_supabase(
        [_article("52")],
        service_key="k",
        refresh=False,
        auto_register_scopes=False,
        preserve_existing_ids=True,
        skip_superseded=True,
    )

    assert report.superseded_skipped == 0
    assert any(
        r["citation_path"] == "be/statute/loi/1978/07/03/1978070303/article/52"
        for r in captured
    )
