import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path

from axiom_corpus.corpus.release_quality import validate_release
from axiom_corpus.corpus.releases import ReleaseManifest

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = REPO_ROOT / "data" / "corpus"
UK_RELEASE_PATH = REPO_ROOT / "manifests" / "releases" / "uk-rulespec-2026-07-12.json"
MIGRATION_PATH = REPO_ROOT / "manifests" / "migrations" / "rulespec-uk-source-promotion.json"
PROMOTION_VERSION = "2026-07-10-uk-rulespec-source-promotion"
RULESPEC_SOURCE_COMMIT = "64c6a9199239e1f364fb108534171372f87f6a2b"

EXPECTED_SCOPE_KEYS = (
    ("uk", "guidance", PROMOTION_VERSION),
    ("uk", "regulation", "2026-06-03-uk-universal-credit"),
    ("uk", "regulation", "2026-06-05-uk-pension-credit-reg6"),
    ("uk", "regulation", "2026-06-06-uk-national-insurance-final"),
    ("uk", "regulation", "2026-06-06-uk-uksi-2026-148-article14"),
    ("uk", "regulation", PROMOTION_VERSION),
    ("uk", "statute", "2026-06-03-uk-universal-credit"),
    ("uk", "statute", "2026-06-05-uk-child-benefit-sscba"),
    ("uk", "statute", "2026-06-06-uk-national-insurance-final"),
    ("uk", "statute", "2026-06-06-uk-state-pension-credit-section1"),
    ("uk", "statute", PROMOTION_VERSION),
    (
        "uk-kingston-upon-thames",
        "manual",
        "2026-06-07-kingston-council-tax-reduction-2026-2027",
    ),
)


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _scope_rows(scope: dict[str, str]) -> list[dict]:
    path = (
        CORPUS_ROOT
        / "provisions"
        / scope["jurisdiction"]
        / scope["document_class"]
        / f"{scope['version']}.jsonl"
    )
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def _active_row(entry: dict) -> dict:
    return next(
        row
        for row in _scope_rows(entry["active_scope"])
        if row["citation_path"] == entry["citation_path"]
    )


def test_uk_rulespec_named_release_is_the_exact_immutable_cut():
    release = ReleaseManifest.load(UK_RELEASE_PATH)

    assert release.name == "uk-rulespec-2026-07-12"
    assert release.scope_keys == EXPECTED_SCOPE_KEYS


def test_uk_rulespec_selector_passes_all_release_gates_strictly():
    report = validate_release(
        CORPUS_ROOT,
        ReleaseManifest.load(UK_RELEASE_PATH),
        strict_warnings=True,
        max_issues=500,
    )

    assert report.to_mapping() == {
        "release": "uk-rulespec-2026-07-12",
        "scope_count": 12,
        "ok": True,
        "error_count": 0,
        "warning_count": 0,
        "strict_warnings": True,
        "issue_count": 0,
        "issues_returned": 0,
        "issues_truncated": False,
        "issues": [],
    }


def test_rulespec_uk_migration_preserves_every_body_url_and_source_snapshot():
    migration = json.loads(MIGRATION_PATH.read_text())
    entries = migration["entries"]
    components = [component for entry in entries for component in entry["components"]]

    assert migration["source_commit"] == RULESPEC_SOURCE_COMMIT
    assert migration["active_release"] == (
        "manifests/releases/uk-rulespec-2026-07-12.json"
    )
    assert migration["expected_counts"] == {
        "entries": 167,
        "components": 177,
        "promotion_citations": 165,
        "guidance": 17,
        "regulation": 59,
        "statute": 89,
        "modified_existing_active_citations": 2,
        "kingston_provisions": 162,
        "original_official_source_artifacts": 37,
        "tracked_clml_gzip_containers": 2,
        "rulespec_source_snapshots": 52,
        "axiom_corpus_source_snapshots": 97,
        "official_source_ingests": 2,
    }
    assert len(entries) == 167
    assert len({entry["citation_path"] for entry in entries}) == 167
    assert len(components) == 177
    assert Counter(entry["resolution"] for entry in entries) == {
        "rulespec_only": 67,
        "newer_rulespec_snapshot": 1,
        "axiom_corpus_canonical_with_rulespec_variants": 7,
        "active_axiom_corpus_canonical_with_rulespec_variants": 2,
        "inactive_axiom_corpus_promoted": 88,
        "official_source_ingest": 2,
    }
    assert Counter(component["repository"] for component in components) == {
        "TheAxiomFoundation/rulespec-uk": 78,
        "TheAxiomFoundation/axiom-corpus": 97,
        "legislation.gov.uk": 2,
    }
    assert sum("original_source_sha256" in component for component in components) == 37
    assert migration["source_retention_policy"]["fallbacks"].startswith("None.")

    for entry in entries:
        component_urls = sorted(
            {
                component["source_url"]
                for component in entry["components"]
                if component["source_url"]
            }
        )
        assert entry["source_urls"] == component_urls
        assert entry["canonical_body_sha256"] == entry["canonical_component"]["body_sha256"]

        active_row = _active_row(entry)
        assert _sha256(active_row["body"].encode()) == entry["canonical_body_sha256"]
        assert active_row["metadata"]["source_urls"] == component_urls
        embedded_provenance = active_row["metadata"]["migration_provenance"]
        assert embedded_provenance["canonical_component"] == entry["canonical_component"]
        assert embedded_provenance["components"] == entry["components"]
        assert embedded_provenance["resolution"] == entry["resolution"]

        for component in entry["components"]:
            snapshot_path = CORPUS_ROOT / component["snapshot_path"]
            snapshot_bytes = snapshot_path.read_bytes()
            assert _sha256(snapshot_bytes) == component["snapshot_sha256"]
            raw_line = snapshot_bytes.splitlines()[component["snapshot_line"] - 1]
            assert _sha256(raw_line) == component["record_sha256"]
            snapshot_row = json.loads(raw_line)
            assert _sha256((snapshot_row.get("body") or "").encode()) == component["body_sha256"]
            assert snapshot_row.get("source_url") == component["source_url"]

            if "original_source_sha256" in component:
                storage = component["original_source_storage"]
                assert storage in {
                    "source_repository_git",
                    "axiom_corpus_git_gzip",
                }
                if storage == "source_repository_git":
                    assert component["original_source_artifact_path"].startswith(
                        "data/corpus/sources/"
                    )
                else:
                    assert component["original_source_container"] == "gzip"
                    assert component["original_source_path"].endswith(".xml.gz")
                    container_path = CORPUS_ROOT / component["original_source_path"]
                    container_bytes = container_path.read_bytes()
                    assert _sha256(container_bytes) == component["original_source_container_sha256"]
                    assert (
                        _sha256(gzip.decompress(container_bytes))
                        == component["original_source_sha256"]
                    )
                assert len(component["original_source_sha256"]) == 64


def test_official_clml_containers_are_inventory_sources_with_exact_raw_hashes():
    migration = json.loads(MIGRATION_PATH.read_text())
    inventory_path = (
        CORPUS_ROOT / "inventory/uk/statute/2026-07-10-uk-rulespec-source-promotion.json"
    )
    inventory = json.loads(inventory_path.read_text())
    inventory_by_citation = {item["citation_path"]: item for item in inventory["items"]}
    official_entries = [
        entry for entry in migration["entries"] if entry["resolution"] == "official_source_ingest"
    ]

    assert len(official_entries) == 2
    for entry in official_entries:
        component = entry["components"][0]
        item = inventory_by_citation[entry["citation_path"]]
        container_path = CORPUS_ROOT / item["source_path"]
        container_bytes = container_path.read_bytes()
        raw_clml = gzip.decompress(container_bytes)

        assert item["source_path"] == component["original_source_path"]
        assert item["source_format"] == "legislation.gov.uk-clml+gzip"
        assert item["sha256"] == _sha256(container_bytes)
        assert item["sha256"] == component["original_source_container_sha256"]
        assert item["metadata"]["original_source_sha256"] == _sha256(raw_clml)
        assert item["metadata"]["original_source_sha256"] == component["original_source_sha256"]
        normalized_snapshot = CORPUS_ROOT / item["metadata"]["normalized_snapshot_path"]
        assert item["metadata"]["normalized_snapshot_sha256"] == _sha256(
            normalized_snapshot.read_bytes()
        )


def test_rulespec_uk_duplicate_citation_resolves_to_the_newer_snapshot():
    migration = json.loads(MIGRATION_PATH.read_text())
    entry = next(
        entry
        for entry in migration["entries"]
        if entry["citation_path"] == "uk/guidance/govuk/carers-allowance/eligibility"
    )
    active_row = _active_row(entry)

    assert entry["resolution"] == "newer_rulespec_snapshot"
    assert len(entry["components"]) == 2
    assert entry["canonical_component"]["artifact_path"].endswith(
        "2026-06-10-uk-govuk-carers-allowance-eligibility.jsonl"
    )
    assert "Your earnings are \u00a3204 or less a week" in active_row["body"]
    assert "GBP 86.45" not in active_row["body"]


def test_kingston_artifacts_are_byte_preserved_and_release_backed():
    migration = json.loads(MIGRATION_PATH.read_text())
    kingston = migration["kingston"]

    assert kingston["source_commit"] == RULESPEC_SOURCE_COMMIT
    assert len(kingston["artifacts"]) == 4
    for artifact in kingston["artifacts"]:
        path = REPO_ROOT / artifact["artifact_path"]
        assert _sha256(path.read_bytes()) == artifact["sha256"]

    rows = _scope_rows(kingston["scope"])
    assert len(rows) == 162
    assert sum(row["kind"] == "document" for row in rows) == 1
    assert sum(row["kind"] == "page" for row in rows) == 161
