import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

from axiom_corpus.corpus.documents import OfficialDocumentManifest

REPO_ROOT = Path(__file__).parents[1]
MANIFEST = REPO_ROOT / "manifests/us-federal-proposal-security-2026.yaml"

MATERIALIZED_SCOPES = {
    ("guidance", "2026-08-30-federal-proposal-security-guidance"): 25,
    ("regulation", "2026-08-30-proposal-security-title-2-part-25"): 16,
    ("regulation", "2026-08-30-proposal-security-title-45-part-604"): 22,
    ("statute", "2026-08-30-proposal-security-title-31"): 73,
    ("statute", "2026-08-30-proposal-security-title-42"): 133,
}


def test_federal_proposal_security_manifest_has_stable_scoped_sources():
    manifest = OfficialDocumentManifest.load(MANIFEST)
    manifest.require_unique_sources()

    assert len(manifest.documents) == 6
    by_id = {document.source_id: document for document in manifest.documents}

    chapter_i = by_id["nsf-pappg-24-1-chapter-i-submission-security"]
    assert chapter_i.extraction is not None
    assert [
        row["section_label"] for row in chapter_i.extraction["anchor_ranges"]
    ] == ["submission-instructions", "uei-and-sam"]

    supplement_2 = by_id["nsf-pappg-24-1-supplement-2-dmsp"]
    assert supplement_2.extraction is not None
    assert "s" in supplement_2.extraction["html_drop_selectors"]
    assert supplement_2.extraction["section_label"] == "dmsp"

    notice = by_id["nsf-important-notice-149-proposal-security"]
    assert notice.extraction is not None
    assert notice.extraction["stop_text_pattern"] == r"^5\."

    faq = by_id["nsf-important-notice-149-implementation-faq"]
    assert faq.extraction is not None
    assert len(faq.extraction["anchor_ranges"]) == 9

    tip = by_id["nsf-tip-person-entity-of-concern-prohibition"]
    assert tip.extraction is not None
    assert tip.extraction["section_label"] == "implementation"
    assert tip.metadata is not None
    assert tip.metadata["dynamic_external_lists"] is True
    assert tip.metadata["prohibited_entity_names_must_not_be_encoded"] is True


def test_materialized_federal_proposal_security_scopes_are_self_contained():
    verified_archive_members: dict[Path, tuple[str, str]] = {}
    for (document_class, version), expected_count in MATERIALIZED_SCOPES.items():
        inventory_path = (
            REPO_ROOT / f"data/corpus/inventory/us/{document_class}/{version}.json"
        )
        provisions_path = (
            REPO_ROOT / f"data/corpus/provisions/us/{document_class}/{version}.jsonl"
        )
        coverage_path = (
            REPO_ROOT / f"data/corpus/coverage/us/{document_class}/{version}.json"
        )

        inventory = json.loads(inventory_path.read_text())["items"]
        provisions = [
            json.loads(line) for line in provisions_path.read_text().splitlines()
        ]
        coverage = json.loads(coverage_path.read_text())

        inventory_paths = {item["citation_path"] for item in inventory}
        provision_paths = {item["citation_path"] for item in provisions}
        assert len(inventory) == expected_count
        assert len(inventory_paths) == expected_count
        assert len(provisions) == expected_count
        assert provision_paths == inventory_paths
        assert coverage["complete"] is True
        assert coverage["missing_from_provisions"] == []
        assert coverage["extra_provisions"] == []

        for item in inventory:
            source_path = REPO_ROOT / "data/corpus" / item["source_path"]
            assert source_path.is_file(), source_path
            assert hashlib.sha256(source_path.read_bytes()).hexdigest() == item["sha256"]
            if document_class == "statute":
                assert source_path.suffix == ".zip"
                assert item["source_format"] == "uslm-xml+zip"
                metadata = item["metadata"]
                assert metadata["archive_sha256"] == item["sha256"]
                assert metadata["archive_member"].endswith(".xml")
                assert len(metadata["archive_member_sha256"]) == 64
                if source_path not in verified_archive_members:
                    member_digest = hashlib.sha256()
                    with ZipFile(source_path) as archive:
                        with archive.open(metadata["archive_member"]) as member:
                            while chunk := member.read(1024 * 1024):
                                member_digest.update(chunk)
                    verified_archive_members[source_path] = (
                        metadata["archive_member"],
                        member_digest.hexdigest(),
                    )
                assert verified_archive_members[source_path] == (
                    metadata["archive_member"],
                    metadata["archive_member_sha256"],
                )
