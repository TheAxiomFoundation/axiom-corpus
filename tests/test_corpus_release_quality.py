from pathlib import Path

import pytest

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.models import ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.r2 import ArtifactReport, ArtifactScopeRow, ArtifactSupabaseGroup
from axiom_corpus.corpus.release_quality import validate_release
from axiom_corpus.corpus.releases import (
    COMPLETE_EXPRESSION_DATES_PROFILE,
    ReleaseManifest,
    ReleaseScope,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_source_scope(
    store: CorpusArtifactStore,
    *,
    jurisdiction: str = "us-co",
    document_class: str = "statute",
    version: str = "2026-04-29",
    inventory: list[SourceInventoryItem],
    provisions: list[ProvisionRecord],
) -> ReleaseManifest:
    store.write_inventory(
        store.inventory_path(jurisdiction, document_class, version),
        inventory,
    )
    store.write_provisions(
        store.provisions_path(jurisdiction, document_class, version),
        provisions,
    )
    store.write_json(
        store.coverage_path(jurisdiction, document_class, version),
        {
            "complete": True,
            "source_count": len(inventory),
            "provision_count": len(provisions),
            "matched_count": len(provisions),
            "missing_from_provisions": [],
            "extra_provisions": [],
        },
    )
    return ReleaseManifest(
        name="test-release",
        scopes=(ReleaseScope(jurisdiction, document_class, version),),
    )


def test_validate_release_reports_artifact_report_mismatches(tmp_path):
    store = CorpusArtifactStore(tmp_path / "corpus")
    artifact_report = ArtifactReport(
        local_root=store.root,
        prefixes=(),
        local_count=0,
        local_bytes=0,
        local_by_prefix={},
        remote_count=None,
        remote_bytes=None,
        remote_by_prefix=None,
        rows=(ArtifactScopeRow(jurisdiction="us-co", document_class="statute", version="v1"),),
        supabase_groups=(
            ArtifactSupabaseGroup(
                jurisdiction="us-co",
                document_class="statute",
                scope_count=1,
                versions=("v1",),
                provision_count=1,
                supabase_count=2,
            ),
        ),
    )

    report = validate_release(
        store.root,
        ReleaseManifest(name="test-release", scopes=()),
        artifact_report=artifact_report,
        max_issues=1,
    )
    payload = report.to_mapping()

    assert report.error_count == 2
    assert report.truncated is True
    assert payload["issues_truncated"] is True
    assert payload["issues"][0]["code"] == "artifact_report_mismatch"
    with pytest.raises(ValueError, match="max_issues"):
        validate_release(store.root, ReleaseManifest(name="test-release", scopes=()), max_issues=0)


def test_validate_release_accepts_r2_complete_remote_only_scope(tmp_path):
    store = CorpusArtifactStore(tmp_path / "corpus")
    artifact_report = ArtifactReport(
        local_root=store.root,
        prefixes=(),
        local_count=0,
        local_bytes=0,
        local_by_prefix={},
        remote_count=3,
        remote_bytes=3,
        remote_by_prefix=None,
        rows=(
            ArtifactScopeRow(
                jurisdiction="us-co",
                document_class="statute",
                version="v1",
                remote_inventory=True,
                remote_provisions=True,
                remote_coverage=True,
                coverage_complete=True,
                provision_count=10,
                supabase_count=10,
            ),
        ),
    )

    report = validate_release(
        store.root,
        ReleaseManifest(
            name="test-release",
            scopes=(ReleaseScope("us-co", "statute", "v1"),),
        ),
        artifact_report=artifact_report,
    )

    assert report.ok is True
    assert report.error_count == 0
    assert report.warning_count == 1
    assert report.issues[0].code == "remote_only_scope_not_deep_validated"


@pytest.mark.parametrize(
    ("local_versions", "remote_versions"),
    [
        (("local",), ("remote",)),
        ((), ("remote-one", "remote-two")),
    ],
)
def test_profiled_release_rejects_unverifiable_remote_uniqueness(
    tmp_path, local_versions, remote_versions
):
    store = CorpusArtifactStore(tmp_path / "corpus")
    scopes = []
    for version in local_versions:
        source = store.source_path("us-co", "statute", version, "source.html")
        source_sha256 = store.write_text(source, "<p>Official source.</p>")
        relative_source = source.relative_to(store.root).as_posix()
        _write_source_scope(
            store,
            version=version,
            inventory=[
                SourceInventoryItem(
                    citation_path="us-co/statute/39",
                    source_path=relative_source,
                    sha256=source_sha256,
                )
            ],
            provisions=[
                ProvisionRecord(
                    jurisdiction="us-co",
                    document_class="statute",
                    citation_path="us-co/statute/39",
                    body="Title 39.",
                    version=version,
                    source_path=relative_source,
                    source_as_of="2026-07-19",
                    expression_date="2026-07-19",
                )
            ],
        )
        scopes.append(ReleaseScope("us-co", "statute", version))
    rows = []
    for version in remote_versions:
        scopes.append(ReleaseScope("us-co", "statute", version))
        rows.append(
            ArtifactScopeRow(
                jurisdiction="us-co",
                document_class="statute",
                version=version,
                remote_inventory=True,
                remote_provisions=True,
                remote_coverage=True,
                coverage_complete=True,
                provision_count=1,
                supabase_count=1,
            )
        )
    report = validate_release(
        store.root,
        ReleaseManifest(
            name="profiled-release",
            scopes=tuple(scopes),
            quality_profile=COMPLETE_EXPRESSION_DATES_PROFILE,
        ),
        artifact_report=ArtifactReport(
            local_root=store.root,
            prefixes=(),
            local_count=0,
            local_bytes=0,
            local_by_prefix={},
            remote_count=len(rows) * 3,
            remote_bytes=len(rows) * 3,
            remote_by_prefix=None,
            rows=tuple(rows),
        ),
    )

    uniqueness_errors = [
        issue for issue in report.issues if issue.code == "release_citation_uniqueness_unverified"
    ]
    assert report.ok is False
    assert len(uniqueness_errors) == len(remote_versions)


def test_validate_release_rejects_cross_scope_citation_duplicates(tmp_path):
    store = CorpusArtifactStore(tmp_path / "corpus")
    citation_path = "us-co/statute/39"
    scopes = []
    for version in ("published-one", "published-two"):
        source = store.source_path("us-co", "statute", version, "source.html")
        source_sha256 = store.write_text(source, "<p>Official source.</p>")
        relative_source = source.relative_to(store.root).as_posix()
        _write_source_scope(
            store,
            version=version,
            inventory=[
                SourceInventoryItem(
                    citation_path=citation_path,
                    source_path=relative_source,
                    sha256=source_sha256,
                )
            ],
            provisions=[
                ProvisionRecord(
                    jurisdiction="us-co",
                    document_class="statute",
                    citation_path=citation_path,
                    body="Title 39.",
                    version=version,
                    source_path=relative_source,
                    source_as_of="2026-07-19",
                    expression_date="2026-07-19",
                )
            ],
        )
        scopes.append(ReleaseScope("us-co", "statute", version))

    report = validate_release(
        store.root,
        ReleaseManifest(
            name="test-release",
            scopes=tuple(scopes),
            quality_profile=COMPLETE_EXPRESSION_DATES_PROFILE,
        ),
    )

    assert report.ok is False
    duplicate = [issue for issue in report.issues if issue.code == "duplicate_release_citation"]
    assert len(duplicate) == 1
    assert duplicate[0].version == "published-two"
    assert "published-one" in duplicate[0].message


def test_known_historical_profiled_release_is_explicitly_grandfathered(tmp_path):
    store = CorpusArtifactStore(tmp_path / "corpus")
    citation_path = "us/statute/26"
    scopes = []
    for version in ("published-one", "published-two"):
        source = store.source_path("us", "statute", version, "source.xml")
        source_sha256 = store.write_text(source, "<title>26</title>")
        relative_source = source.relative_to(store.root).as_posix()
        _write_source_scope(
            store,
            jurisdiction="us",
            version=version,
            inventory=[
                SourceInventoryItem(
                    citation_path=citation_path,
                    source_path=relative_source,
                    sha256=source_sha256,
                )
            ],
            provisions=[
                ProvisionRecord(
                    jurisdiction="us",
                    document_class="statute",
                    citation_path=citation_path,
                    body=None,
                    version=version,
                    source_path=relative_source,
                    source_as_of="2026-07-19",
                    expression_date="2026-07-19",
                )
            ],
        )
        scopes.append(ReleaseScope("us", "statute", version))

    report = validate_release(
        store.root,
        ReleaseManifest(
            name="us-rulespec-2026-07-19",
            scopes=tuple(scopes),
            quality_profile=COMPLETE_EXPRESSION_DATES_PROFILE,
        ),
    )

    codes = {issue.code for issue in report.issues}
    assert report.ok is True
    assert "legacy_release_citation_uniqueness_grandfathered" in codes
    assert "duplicate_release_citation" not in codes


def test_validate_release_can_ignore_r2_only_mirror_gaps(tmp_path):
    store = CorpusArtifactStore(tmp_path / "corpus")
    artifact_report = ArtifactReport(
        local_root=store.root,
        prefixes=(),
        local_count=0,
        local_bytes=0,
        local_by_prefix={},
        remote_count=0,
        remote_bytes=0,
        remote_by_prefix=None,
        rows=(
            ArtifactScopeRow(
                jurisdiction="ca",
                document_class="policy",
                version="v1",
                local_inventory=True,
                local_provisions=True,
                local_coverage=True,
                local_source_files=1,
                remote_inventory=False,
                remote_provisions=False,
                remote_coverage=False,
                remote_source_files=0,
                coverage_complete=True,
                provision_count=10,
                supabase_count=9,
            ),
        ),
    )

    report = validate_release(
        store.root,
        ReleaseManifest(name="test-release", scopes=()),
        artifact_report=artifact_report,
        ignore_r2_missing=True,
    )

    assert report.ok is False
    assert report.error_count == 1
    assert report.issues[0].code == "artifact_report_mismatch"
    assert report.issues[0].message == (
        "artifact report has mismatch reasons: supabase_count_mismatch"
    )


def test_validate_release_requires_complete_source_references(tmp_path):
    store = CorpusArtifactStore(tmp_path / "corpus")
    version = "2026-04-29"
    source = store.source_path("us-co", "statute", version, "source.html")
    store.write_text(source, "Official source")
    release = _write_source_scope(
        store,
        version=version,
        inventory=[SourceInventoryItem(citation_path="us-co/statute/1")],
        provisions=[
            ProvisionRecord(
                jurisdiction="us-co",
                document_class="statute",
                citation_path="us-co/statute/1",
                body="Text.",
                version=version,
            )
        ],
    )

    report = validate_release(store.root, release)
    codes = {issue.code for issue in report.issues}

    assert report.ok is False
    assert {
        "missing_inventory_source_path",
        "missing_inventory_source_sha256",
        "missing_provision_source_path",
    }.issubset(codes)


def test_validate_release_rejects_missing_source_files(tmp_path):
    store = CorpusArtifactStore(tmp_path / "corpus")
    version = "2026-04-29"
    missing_path = f"sources/us-co/statute/{version}/missing.html"
    release = _write_source_scope(
        store,
        version=version,
        inventory=[
            SourceInventoryItem(
                citation_path="us-co/statute/1",
                source_path=missing_path,
                sha256="a" * 64,
            )
        ],
        provisions=[
            ProvisionRecord(
                jurisdiction="us-co",
                document_class="statute",
                citation_path="us-co/statute/1",
                body="Text.",
                version=version,
                source_path=missing_path,
            )
        ],
    )

    report = validate_release(store.root, release)
    codes = {issue.code for issue in report.issues}

    assert report.ok is False
    assert "missing_inventory_source_file" in codes
    assert "missing_provision_source_file" in codes


def test_validate_release_rejects_cross_scope_source_paths(tmp_path):
    store = CorpusArtifactStore(tmp_path / "corpus")
    version = "2026-04-29"
    source = store.source_path("us-ny", "statute", version, "source.html")
    digest = store.write_text(source, "Official source")
    cross_scope_path = source.relative_to(store.root).as_posix()
    release = _write_source_scope(
        store,
        version=version,
        inventory=[
            SourceInventoryItem(
                citation_path="us-co/statute/1",
                source_path=cross_scope_path,
                sha256=digest,
            )
        ],
        provisions=[
            ProvisionRecord(
                jurisdiction="us-co",
                document_class="statute",
                citation_path="us-co/statute/1",
                body="Text.",
                version=version,
                source_path=cross_scope_path,
            )
        ],
    )

    report = validate_release(store.root, release)
    codes = {issue.code for issue in report.issues}

    assert report.ok is False
    assert "noncanonical_inventory_source_path" in codes
    assert "noncanonical_provision_source_path" in codes


def test_validate_release_rejects_symlinked_source_files(tmp_path):
    store = CorpusArtifactStore(tmp_path / "corpus")
    version = "2026-04-29"
    target = store.source_path("us-co", "statute", version, "target.html")
    digest = store.write_text(target, "Official source")
    source = store.source_path("us-co", "statute", version, "source.html")
    source.symlink_to(target)
    source_path = source.relative_to(store.root).as_posix()
    release = _write_source_scope(
        store,
        version=version,
        inventory=[
            SourceInventoryItem(
                citation_path="us-co/statute/1",
                source_path=source_path,
                sha256=digest,
            )
        ],
        provisions=[
            ProvisionRecord(
                jurisdiction="us-co",
                document_class="statute",
                citation_path="us-co/statute/1",
                body="Text.",
                version=version,
                source_path=source_path,
            )
        ],
    )

    report = validate_release(store.root, release)
    codes = {issue.code for issue in report.issues}

    assert report.ok is False
    assert "symlinked_inventory_source_path" in codes
    assert "symlinked_provision_source_path" in codes


def test_validate_release_rejects_uninventoried_provision_source(tmp_path):
    store = CorpusArtifactStore(tmp_path / "corpus")
    version = "2026-04-29"
    inventory_source = store.source_path("us-co", "statute", version, "inventory.html")
    inventory_digest = store.write_text(inventory_source, "Inventory source")
    provision_source = store.source_path("us-co", "statute", version, "provision.html")
    store.write_text(provision_source, "Provision source")
    release = _write_source_scope(
        store,
        version=version,
        inventory=[
            SourceInventoryItem(
                citation_path="us-co/statute/1",
                source_path=inventory_source.relative_to(store.root).as_posix(),
                sha256=inventory_digest,
            )
        ],
        provisions=[
            ProvisionRecord(
                jurisdiction="us-co",
                document_class="statute",
                citation_path="us-co/statute/1",
                body="Text.",
                version=version,
                source_path=provision_source.relative_to(store.root).as_posix(),
            )
        ],
    )

    report = validate_release(store.root, release)

    assert report.ok is False
    assert "provision_source_not_in_inventory" in {issue.code for issue in report.issues}


def test_validate_release_reports_scope_invariant_errors(tmp_path):
    store = CorpusArtifactStore(tmp_path / "corpus")
    version = "2026-04-29"
    source = store.source_path("us-co", "statute", version, "source.html")
    store.write_text(source, "<p>Official source.</p>")
    store.write_inventory(
        store.inventory_path("us-co", "statute", version),
        [
            SourceInventoryItem(
                citation_path="",
                source_path=source.relative_to(store.root).as_posix(),
                sha256="wrong-sha",
            ),
            SourceInventoryItem(citation_path="us-co/statute/1"),
        ],
    )
    store.write_provisions(
        store.provisions_path("us-co", "statute", version),
        [
            ProvisionRecord(
                jurisdiction="us-ny",
                document_class="policy",
                citation_path="us-co/statute/1",
                id="duplicate-id",
                version="old",
                parent_citation_path="missing-parent",
                expression_date="not-a-date",
            ),
            ProvisionRecord(
                jurisdiction="us-co",
                document_class="statute",
                citation_path="us-co/statute/1",
                id="duplicate-id",
                body="Duplicate.",
                version=version,
                parent_citation_path="us-co/statute/1",
                parent_id="wrong-parent",
                source_as_of=version,
                expression_date=version,
            ),
        ],
    )
    store.write_json(
        store.coverage_path("us-co", "statute", version),
        {
            "complete": False,
            "source_count": 99,
            "provision_count": 99,
            "matched_count": 99,
            "missing_from_provisions": [""],
            "extra_provisions": [],
        },
    )
    release = ReleaseManifest(
        name="test-release",
        scopes=(ReleaseScope("us-co", "statute", version),),
    )

    report = validate_release(store.root, release, strict_warnings=True)
    codes = {issue.code for issue in report.issues}

    assert report.ok is False
    assert {
        "coverage_count_mismatch",
        "coverage_incomplete",
        "duplicate_provision_citation",
        "duplicate_provision_id",
        "empty_inventory_citation",
        "empty_provision_text",
        "invalid_expression_date",
        "missing_inventory_source_path",
        "missing_parent_citation",
        "missing_parent_id",
        "parent_id_mismatch",
        "persisted_coverage_incomplete",
        "provision_document_class_mismatch",
        "provision_jurisdiction_mismatch",
        "provision_version_mismatch",
        "source_sha256_mismatch",
    }.issubset(codes)


def test_validate_release_versions_expression_date_requirement(tmp_path):
    store = CorpusArtifactStore(tmp_path / "corpus")
    version = "2026-07-19"
    source = store.source_path("us", "statute", version, "source.xml")
    source_sha256 = store.write_text(source, "<section>Official source.</section>")
    source_path = source.relative_to(store.root).as_posix()
    release = _write_source_scope(
        store,
        jurisdiction="us",
        version=version,
        inventory=[
            SourceInventoryItem(
                citation_path="us/statute/1",
                source_path=source_path,
                sha256=source_sha256,
            )
        ],
        provisions=[
            ProvisionRecord(
                jurisdiction="us",
                document_class="statute",
                citation_path="us/statute/1",
                body="Official source.",
                version=version,
                source_path=source_path,
                source_as_of=version,
            )
        ],
    )

    legacy_report = validate_release(store.root, release)
    strict_release = ReleaseManifest(
        name=release.name,
        scopes=release.scopes,
        quality_profile=COMPLETE_EXPRESSION_DATES_PROFILE,
    )
    report = validate_release(store.root, strict_release)

    assert legacy_report.ok is True
    legacy_issue = next(
        item for item in legacy_report.issues if item.code == "missing_expression_date"
    )
    assert legacy_issue.severity == "warning"
    assert report.ok is False
    issue = next(item for item in report.issues if item.code == "missing_expression_date")
    assert issue.severity == "error"


def test_historical_us_selector_retains_legacy_expression_date_warnings():
    release = ReleaseManifest.load(REPO_ROOT / "manifests/releases/us-rulespec-2026-07-18.json")

    report = validate_release(
        REPO_ROOT / "data/corpus",
        release,
        max_issues=2000,
    )
    date_issues = [
        issue
        for issue in report.issues
        if issue.code in {"missing_expression_date", "invalid_expression_date"}
    ]

    assert report.ok is True
    assert len(date_issues) == 43
    assert {issue.severity for issue in date_issues} == {"warning"}


def test_validate_release_reports_missing_and_invalid_artifacts(tmp_path):
    store = CorpusArtifactStore(tmp_path / "corpus")
    version = "2026-04-29"
    store.inventory_path("us-bad-inventory", "statute", version).parent.mkdir(parents=True)
    store.inventory_path("us-bad-inventory", "statute", version).write_text("{")

    store.write_inventory(
        store.inventory_path("us-bad-provisions", "statute", version),
        [SourceInventoryItem(citation_path="us-bad-provisions/statute/1")],
    )
    store.provisions_path("us-bad-provisions", "statute", version).parent.mkdir(parents=True)
    store.provisions_path("us-bad-provisions", "statute", version).write_text("{")

    store.write_inventory(
        store.inventory_path("us-bad-coverage", "statute", version),
        [SourceInventoryItem(citation_path="us-bad-coverage/statute/1")],
    )
    store.write_provisions(
        store.provisions_path("us-bad-coverage", "statute", version),
        [
            ProvisionRecord(
                jurisdiction="us-bad-coverage",
                document_class="statute",
                citation_path="us-bad-coverage/statute/1",
                body="Text.",
                version=version,
                source_as_of=version,
                expression_date=version,
            )
        ],
    )
    store.coverage_path("us-bad-coverage", "statute", version).parent.mkdir(parents=True)
    store.coverage_path("us-bad-coverage", "statute", version).write_text("[]")

    store.write_inventory(
        store.inventory_path("us-json-coverage", "statute", version),
        [SourceInventoryItem(citation_path="us-json-coverage/statute/1")],
    )
    store.write_provisions(
        store.provisions_path("us-json-coverage", "statute", version),
        [
            ProvisionRecord(
                jurisdiction="us-json-coverage",
                document_class="statute",
                citation_path="us-json-coverage/statute/1",
                body="Text.",
                version=version,
                source_as_of=version,
                expression_date=version,
            )
        ],
    )
    store.coverage_path("us-json-coverage", "statute", version).parent.mkdir(parents=True)
    store.coverage_path("us-json-coverage", "statute", version).write_text("{")

    store.write_inventory(
        store.inventory_path("us-bogus-class", "bogus", version),
        [SourceInventoryItem(citation_path="us-bogus-class/bogus/1")],
    )
    store.write_provisions(
        store.provisions_path("us-bogus-class", "bogus", version),
        [
            ProvisionRecord(
                jurisdiction="us-bogus-class",
                document_class="bogus",
                citation_path="us-bogus-class/bogus/1",
                body="Text.",
                version=version,
                source_as_of=version,
                expression_date=version,
            )
        ],
    )
    store.write_json(
        store.coverage_path("us-bogus-class", "bogus", version),
        {
            "complete": True,
            "source_count": 1,
            "provision_count": 1,
            "matched_count": 1,
            "missing_from_provisions": [],
            "extra_provisions": [],
        },
    )

    # Bypass the constructor only to exercise validate_release's defensive
    # handling of an object supplied by an untyped caller. Normal construction
    # rejects this class before any artifact reads.
    invalid_scope = object.__new__(ReleaseScope)
    object.__setattr__(invalid_scope, "jurisdiction", "us-bogus-class")
    object.__setattr__(invalid_scope, "document_class", "bogus")
    object.__setattr__(invalid_scope, "version", version)

    release = ReleaseManifest(
        name="test-release",
        scopes=(
            ReleaseScope("us-missing", "statute", version),
            ReleaseScope("us-bad-inventory", "statute", version),
            ReleaseScope("us-bad-provisions", "statute", version),
            ReleaseScope("us-bad-coverage", "statute", version),
            ReleaseScope("us-json-coverage", "statute", version),
            invalid_scope,
        ),
    )

    report = validate_release(store.root, release)
    codes = {issue.code for issue in report.issues}

    assert {
        "invalid_coverage",
        "invalid_document_class",
        "invalid_inventory",
        "invalid_provisions",
        "missing_coverage",
        "missing_inventory",
        "missing_provisions",
    }.issubset(codes)
