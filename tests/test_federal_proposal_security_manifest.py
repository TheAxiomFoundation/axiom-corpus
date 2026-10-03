import hashlib
import json
import os
from pathlib import Path
from zipfile import ZipFile

import pytest
import yaml

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.cli import main as corpus_cli
from axiom_corpus.corpus.documents import OfficialDocumentManifest, extract_official_documents
from axiom_corpus.corpus.ingest_manifests import (
    INGEST_MANIFEST_KEY_ID,
    INGEST_MANIFEST_SCHEMA_VERSION,
    INGEST_MANIFEST_SIGNATURE_ALGORITHM,
    default_ingest_manifest_path,
    sha256_file,
    verify_ingest_manifest,
)
from scripts.self_contain_usc_scope import self_contain_scope

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = REPO_ROOT / "data" / "corpus"
MANIFEST = REPO_ROOT / "manifests/us-federal-proposal-security-2026.yaml"
RUN_NOTE = "docs/ingest-runs/2026-08-30-federal-proposal-security.md"
USC_VERSION = "2026-08-30-proposal-security"
GUIDANCE_VERSION = "2026-09-28-federal-proposal-security-guidance"
RELEASE_POINT_URL = "https://uscode.house.gov/download/releasepoints/us/pl/119/102"

MATERIALIZED_SCOPES = {
    ("guidance", GUIDANCE_VERSION): 25,
    ("regulation", f"{USC_VERSION}-title-2-part-25"): 16,
    ("regulation", f"{USC_VERSION}-title-45-part-604"): 22,
    ("statute", f"{USC_VERSION}-title-31"): 72,
    ("statute", f"{USC_VERSION}-title-42"): 174,
}

# Official OLRC release point Online@119-102 downloads retained byte-for-byte, and
# the extract-usc selectors each scope was built with (recorded in its signed manifest).
USC_ARCHIVES = {
    f"{USC_VERSION}-title-31": {
        "title": "31",
        "archive": "olrc/xml_usc31@119-102.zip",
        "archive_sha256": "1cccbcc7e0fe4bc548b970e866dced83a728bca2f3d305f477405f0426735b78",
        "member": "usc31.xml",
        "member_sha256": "254572a738146d41174b64232c98f630e892b8d368d7a1841d3750d8cb102185",
        "selectors": ["--section", "1352"],
        "sections": {"1352"},
    },
    f"{USC_VERSION}-title-42": {
        "title": "42",
        "archive": "olrc/xml_usc42@119-102.zip",
        "archive_sha256": "31929c28f117362ac8788607242795769b05ed7726f07e4ed3b1786f39655ce7",
        "member": "usc42.xml",
        "member_sha256": "b72955590abe55bdbd1ce5d13c5293955a82add9c84fad92c1674ec469e86624",
        "selectors": [
            "--section", "1862o",
            "--citation-path", "us/statute/42/1862o–1",
            "--section", "6605",
            "--section", "18901",
            "--section", "19036",
            "--section", "19231",
            "--section", "19232",
            "--section", "19233",
            "--section", "19234",
            "--section", "19235",
            "--section", "19236",
            "--section", "19237",
        ],
        "sections": {
            "1862o",
            "1862o–1",
            "6605",
            "18901",
            "19036",
            "19231",
            "19232",
            "19233",
            "19234",
            "19235",
            "19236",
            "19237",
        },
    },
}

# The rebuild command each signed manifest must record, by document class.
EXPECTED_COMMAND_FRAGMENTS = {
    "guidance": (
        "axiom-corpus-ingest extract-official-documents",
        f"--version {GUIDANCE_VERSION}",
        "--manifest manifests/us-federal-proposal-security-2026.yaml",
        RUN_NOTE,
    ),
    "regulation": (
        "axiom-corpus-ingest extract-ecfr",
        "--as-of 2026-08-27",
        "--include-appendices",
        RUN_NOTE,
    ),
    "statute": (
        "axiom-corpus-ingest extract-usc",
        "--source-zip",
        "scripts/self_contain_usc_scope.py",
        RUN_NOTE,
    ),
}

# Fields a local_path replay records differently from the live capture.
REPLAY_ONLY_METADATA = ("download_url", "content_type")


def _scope_path(kind: str, document_class: str, version: str) -> Path:
    suffix = ".jsonl" if kind == "provisions" else ".json"
    return CORPUS_ROOT / kind / "us" / document_class / f"{version}{suffix}"


def _load_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def _scope_artifacts(document_class: str, version: str) -> set[str]:
    source_root = CORPUS_ROOT / "sources" / "us" / document_class / version
    paths = {path for path in source_root.rglob("*") if path.is_file()}
    paths |= {
        _scope_path(kind, document_class, version)
        for kind in ("inventory", "provisions", "coverage")
    }
    return {path.relative_to(REPO_ROOT).as_posix() for path in paths}


def _ingest_manifest(document_class: str, version: str) -> dict:
    path = REPO_ROOT / default_ingest_manifest_path(
        jurisdiction="us",
        document_class=document_class,
        version=version,
    )
    return json.loads(path.read_text())


def _rebuild_usc_scope(tmp_path: Path, version: str) -> Path:
    expected = USC_ARCHIVES[version]
    title = expected["title"]
    base = tmp_path / "corpus"
    archive = CORPUS_ROOT / "sources/us/statute" / version / expected["archive"]
    argv = [
        "extract-usc",
        "--base", str(base),
        "--version", USC_VERSION,
        "--source-zip", str(archive),
        "--title", title,
        "--source-as-of", "2026-07-12",
        "--expression-date", "2026-07-12",
        "--source-url", f"{RELEASE_POINT_URL}/xml_usc{title}@119-102.zip",
        *expected["selectors"],
    ]
    assert corpus_cli(argv) == 0
    self_contain_scope(base, jurisdiction="us", document_class="statute", version=version)
    return base


def _assert_rebuilt_usc_scope_matches(base: Path, version: str) -> None:
    expected = USC_ARCHIVES[version]
    rebuilt_archive = base / "sources/us/statute" / version / expected["archive"]
    assert sha256_file(rebuilt_archive) == expected["archive_sha256"]
    for kind in ("inventory", "provisions", "coverage"):
        committed = _scope_path(kind, "statute", version)
        rebuilt = base / committed.relative_to(CORPUS_ROOT)
        assert rebuilt.read_bytes() == committed.read_bytes(), kind


def test_federal_proposal_security_manifest_has_stable_scoped_sources():
    manifest = OfficialDocumentManifest.load(MANIFEST)
    manifest.require_unique_sources()

    assert len(manifest.documents) == 6
    by_id = {document.source_id: document for document in manifest.documents}
    assert {document.source_as_of for document in manifest.documents} == {"2026-09-28"}

    chapter_i = by_id["nsf-pappg-24-1-chapter-i-submission-security"]
    assert chapter_i.extraction is not None
    assert [
        row["section_label"] for row in chapter_i.extraction["anchor_ranges"]
    ] == ["submission-instructions", "uei-and-sam"]

    supplement_2 = by_id["nsf-pappg-24-1-supplement-2-dmsp"]
    assert supplement_2.extraction is not None
    assert supplement_2.extraction["html_drop_selectors"] == [
        ".print",
        "s",
        'h2:-soup-contains("Contact information") ~ p',
        'h2:-soup-contains("Contact information")',
    ]
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
    for (document_class, version), expected_count in MATERIALIZED_SCOPES.items():
        inventory = json.loads(_scope_path("inventory", document_class, version).read_text())[
            "items"
        ]
        provisions = _load_rows(_scope_path("provisions", document_class, version))
        coverage = json.loads(_scope_path("coverage", document_class, version).read_text())

        inventory_paths = {item["citation_path"] for item in inventory}
        provision_ids = {row["citation_path"]: row["id"] for row in provisions}
        assert len(inventory) == expected_count
        assert len(inventory_paths) == expected_count
        assert len(provisions) == expected_count
        assert set(provision_ids) == inventory_paths
        assert coverage["complete"] is True
        assert coverage["missing_from_provisions"] == []
        assert coverage["extra_provisions"] == []

        # Every parent link resolves inside the scope, by path and by id.
        for row in provisions:
            parent = row.get("parent_citation_path")
            if parent is None:
                assert row.get("parent_id") is None, row["citation_path"]
                continue
            assert parent in provision_ids, row["citation_path"]
            assert row["parent_id"] == provision_ids[parent], row["citation_path"]
            if document_class == "statute":
                assert row["metadata"]["parent_citation_path"] == parent, row["citation_path"]

        for item in inventory:
            source_path = CORPUS_ROOT / item["source_path"]
            assert source_path.is_file(), source_path
            assert hashlib.sha256(source_path.read_bytes()).hexdigest() == item["sha256"]


def test_supplement_2_dmsp_row_stops_before_the_page_contact_section():
    rows = {
        row["citation_path"]: row
        for row in _load_rows(_scope_path("provisions", "guidance", GUIDANCE_VERSION))
    }
    body = rows["us/guidance/nsf/pappg/24-1/supplement-2/dmsp"]["body"]
    assert body.endswith("must be accompanied by a clear justification.")
    assert "Contact information" not in body
    assert "policy@nsf.gov" not in body


def test_us_code_scopes_retain_the_official_release_point_zip():
    for version, expected in USC_ARCHIVES.items():
        title = expected["title"]
        source_root = CORPUS_ROOT / "sources/us/statute" / version
        assert sorted(
            path.relative_to(source_root).as_posix()
            for path in source_root.rglob("*")
            if path.is_file()
        ) == [expected["archive"]]
        archive = source_root / expected["archive"]
        assert sha256_file(archive) == expected["archive_sha256"]
        with ZipFile(archive) as zipped:
            assert [info.filename for info in zipped.infolist()] == [expected["member"]]
            member_digest = hashlib.sha256()
            with zipped.open(expected["member"]) as member:
                while chunk := member.read(1024 * 1024):
                    member_digest.update(chunk)
        assert member_digest.hexdigest() == expected["member_sha256"]

        inventory = json.loads(_scope_path("inventory", "statute", version).read_text())["items"]
        provisions = _load_rows(_scope_path("provisions", "statute", version))
        source_key = f"sources/us/statute/{version}/{expected['archive']}"
        for record in [*inventory, *provisions]:
            assert record["source_path"] == source_key
            assert record["source_format"] == "uslm-xml"
            assert record["metadata"]["source_archive_member"] == expected["member"]
            assert record["metadata"]["publication_name"] == "Online@119-102"
        for item in inventory:
            assert item["sha256"] == expected["archive_sha256"]

        # Section rows are detached roots; the released title row is not duplicated.
        paths = {row["citation_path"] for row in provisions}
        assert f"us/statute/{title}" not in paths
        roots = [row for row in provisions if row.get("parent_citation_path") is None]
        assert {row["citation_path"] for row in roots} == {
            f"us/statute/{title}/{section}" for section in expected["sections"]
        }
        for row in roots:
            assert row["kind"] == "section"
            assert row["metadata"]["self_contained_root"] is True
            assert row["metadata"]["detached_parent_citation_path"] == f"us/statute/{title}"
            assert row["metadata"]["parent_citation_path"] == f"us/statute/{title}"


def test_title_31_scope_rebuilds_byte_identically_from_the_retained_zip(tmp_path):
    version = f"{USC_VERSION}-title-31"
    base = _rebuild_usc_scope(tmp_path, version)
    _assert_rebuilt_usc_scope_matches(base, version)


@pytest.mark.slow
@pytest.mark.timeout(300)
def test_title_42_scope_rebuilds_byte_identically_from_the_retained_zip(tmp_path):
    version = f"{USC_VERSION}-title-42"
    base = _rebuild_usc_scope(tmp_path, version)
    _assert_rebuilt_usc_scope_matches(base, version)


def test_guidance_scope_replays_from_the_retained_captures(tmp_path):
    source_root = (
        CORPUS_ROOT / "sources/us/guidance" / GUIDANCE_VERSION / "official-documents"
    )
    payload = yaml.safe_load(MANIFEST.read_text())
    for document in payload["documents"]:
        document["local_path"] = str(source_root / f"{document['source_id']}.html")
    replay_manifest = tmp_path / "replay.yaml"
    replay_manifest.write_text(yaml.safe_dump(payload, sort_keys=False))
    base = tmp_path / "corpus"
    report = extract_official_documents(
        CorpusArtifactStore(base),
        manifest_path=replay_manifest,
        version=GUIDANCE_VERSION,
    )
    assert report.coverage.complete

    replay_sources = base / "sources/us/guidance" / GUIDANCE_VERSION / "official-documents"
    assert sorted(path.name for path in replay_sources.iterdir()) == sorted(
        path.name for path in source_root.iterdir()
    )
    for path in source_root.iterdir():
        assert (replay_sources / path.name).read_bytes() == path.read_bytes(), path.name
    committed_coverage = _scope_path("coverage", "guidance", GUIDANCE_VERSION)
    assert (base / committed_coverage.relative_to(CORPUS_ROOT)).read_bytes() == (
        committed_coverage.read_bytes()
    )

    source_urls = {document["source_id"]: document["source_url"] for document in payload["documents"]}

    def comparable(record: dict) -> dict:
        record = json.loads(json.dumps(record))
        for field in REPLAY_ONLY_METADATA:
            record["metadata"].pop(field, None)
        return record

    for kind in ("inventory", "provisions"):
        committed_path = _scope_path(kind, "guidance", GUIDANCE_VERSION)
        replay_path = base / committed_path.relative_to(CORPUS_ROOT)
        if kind == "inventory":
            committed = json.loads(committed_path.read_text())["items"]
            replayed = json.loads(replay_path.read_text())["items"]
        else:
            committed = _load_rows(committed_path)
            replayed = _load_rows(replay_path)
        assert [comparable(record) for record in replayed] == [
            comparable(record) for record in committed
        ], kind
        # The live capture records the official URL, never a local file.
        for record in committed:
            source_id = Path(record["source_path"]).stem
            assert record["metadata"]["download_url"] == source_urls[source_id]
            assert record["metadata"]["content_type"].startswith("text/html")


def test_federal_proposal_security_scopes_carry_signed_ingest_manifests():
    for (document_class, version), expected_count in MATERIALIZED_SCOPES.items():
        manifest = _ingest_manifest(document_class, version)

        assert manifest["schema_version"] == INGEST_MANIFEST_SCHEMA_VERSION
        assert manifest["jurisdiction"] == "us"
        assert manifest["document_class"] == document_class
        assert manifest["version"] == version
        assert manifest["reasoning_logs"] == []
        coverage = json.loads(_scope_path("coverage", document_class, version).read_text())
        assert manifest["coverage"] == {
            "complete": True,
            "source_count": expected_count,
            "provision_count": expected_count,
            "matched_count": expected_count,
            "missing_count": 0,
            "extra_count": 0,
        }
        assert manifest["coverage"]["source_count"] == coverage["source_count"]
        assert manifest["coverage"]["provision_count"] == coverage["provision_count"]
        command = manifest["command"]["text"]
        for fragment in EXPECTED_COMMAND_FRAGMENTS[document_class]:
            assert fragment in command, (version, fragment)
        if version in USC_ARCHIVES:
            assert " ".join(USC_ARCHIVES[version]["selectors"]) in command, version

        git = manifest["axiom_corpus_git"]
        assert git["root"] == "."
        assert git["dirty_tracked"] is False
        assert len(git["commit"]) == 40

        signature = manifest["signature"]
        assert signature["algorithm"] == INGEST_MANIFEST_SIGNATURE_ALGORITHM
        assert signature["key_id"] == INGEST_MANIFEST_KEY_ID
        assert signature["value"]

        # The manifest attests exactly the scope's artifacts, at their committed bytes.
        applied = {entry["path"]: entry for entry in manifest["applied_files"]}
        assert set(applied) == _scope_artifacts(document_class, version)
        for path, entry in applied.items():
            assert "deleted" not in entry, path
            assert entry["sha256"] == sha256_file(REPO_ROOT / path), path


def test_federal_proposal_security_ingest_manifests_are_authenticated():
    public_key = os.environ.get("AXIOM_CORPUS_INGEST_PUBLIC_KEY")
    if not public_key:
        if os.environ.get("CI"):
            pytest.fail("AXIOM_CORPUS_INGEST_PUBLIC_KEY is required in CI")
        pytest.skip("AXIOM_CORPUS_INGEST_PUBLIC_KEY is required for signature verification")

    issues = {
        version: verify_ingest_manifest(
            _ingest_manifest(document_class, version),
            public_key=public_key,
            repo=REPO_ROOT,
            head_ref="HEAD",
        )
        for document_class, version in MATERIALIZED_SCOPES
    }
    assert issues == {version: [] for _document_class, version in MATERIALIZED_SCOPES}
