import json
import os
from collections.abc import Iterator, Mapping
from functools import cache
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

from axiom_corpus.corpus.ingest_manifests import sha256_file, verify_ingest_manifest

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = REPO_ROOT / "data" / "corpus"
EXPECTED_TARGET_MANIFEST_PATHS = {
    "us-co": "us-co/regulation/10-ccr-2506-1",
    "us-oh": "us-oh/regulation/agency-5101-4",
}
PUBLISHED_CURRENT = "published_current"
SOURCE_REFETCH_REQUIRED = "source_refetch_required"
COMPREHENSIVE_RELEASE = REPO_ROOT / "manifests/releases/us-rulespec-snap-2026-07-21.json"
CONSOLIDATED_MASSACHUSETTS_VERSION = "2026-07-21-ma-dta-regulations-consolidated"
CONSOLIDATED_MASSACHUSETTS_SCOPE = (
    "us-ma",
    "regulation",
    CONSOLIDATED_MASSACHUSETTS_VERSION,
)
RELEASE_SCOPE_SUBSTITUTIONS = {
    (
        "us-ma",
        "regulation",
        "2026-07-17-ma-dta-snap-regulations",
    ): CONSOLIDATED_MASSACHUSETTS_SCOPE,
}
SUPERSEDED_RELEASE_SCOPES = {
    ("us-co", "regulation", "2026-04-29-10-ccr-2506-1-r2026-07-15-self-contained"),
    ("us-la", "manual", "2026-07-13-recovery"),
    ("us-ma", "regulation", "2026-05-28"),
    ("us-mi", "manual", "2026-07-13-recovery"),
}


@cache
def _sha256_file_cached(path: Path) -> str:
    """Hash each retained source once even when many inventory rows share it."""
    return sha256_file(path)


def _queue() -> list[dict[str, Any]]:
    queue_path = REPO_ROOT / "manifests" / "state-snap-manual-agent-queue.yaml"
    payload = yaml.safe_load(queue_path.read_text())
    assert isinstance(payload, dict)
    states = payload.get("states")
    assert isinstance(states, list) and all(isinstance(state, dict) for state in states)
    return cast(list[dict[str, Any]], states)


def _scope_paths(scope: Mapping[str, Any]) -> dict[str, Path]:
    jurisdiction = str(scope["jurisdiction"])
    document_class = str(scope["document_class"])
    version = str(scope["version"])
    return {
        "source_root": CORPUS_ROOT / "sources" / jurisdiction / document_class / version,
        "inventory": CORPUS_ROOT
        / "inventory"
        / jurisdiction
        / document_class
        / f"{version}.json",
        "provisions": CORPUS_ROOT
        / "provisions"
        / jurisdiction
        / document_class
        / f"{version}.jsonl",
        "coverage": CORPUS_ROOT
        / "coverage"
        / jurisdiction
        / document_class
        / f"{version}.json",
        "ingest_manifest": REPO_ROOT
        / ".axiom"
        / "ingest-manifests"
        / jurisdiction
        / document_class
        / f"{version}.json",
    }


def _nested_source_paths(value: object) -> Iterator[str]:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if isinstance(key, str) and key.endswith("source_path") and isinstance(nested, str):
                yield nested
            else:
                yield from _nested_source_paths(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _nested_source_paths(nested)


def _scope_entries(
    state: dict[str, Any],
) -> list[tuple[str, str, str, Mapping[str, Any]]]:
    entries = [
        (
            "target",
            str(state["queue_status"]),
            str(state["target_manifest"]),
            cast(Mapping[str, Any], state["target_scope"]),
        )
    ]
    supporting_values = {
        "status": state.get("supporting_queue_status"),
        "manifest": state.get("supporting_manifest"),
        "scope": state.get("supporting_scope"),
    }
    if any(value is not None for value in supporting_values.values()):
        assert all(supporting_values.values()), state["jurisdiction"]
        entries.append(
            (
                "supporting",
                str(supporting_values["status"]),
                str(supporting_values["manifest"]),
                cast(Mapping[str, Any], supporting_values["scope"]),
            )
        )
    return entries


def _assert_scope_matches_retained_sources(
    *,
    state: dict[str, Any],
    role: str,
    status: str,
    manifest_path: str,
    scope: Mapping[str, Any],
) -> None:
    label = f"{state['jurisdiction']}:{role}"
    assert status in {PUBLISHED_CURRENT, SOURCE_REFETCH_REQUIRED}
    assert (REPO_ROOT / manifest_path).is_file(), label
    assert all(scope.get(key) for key in ("jurisdiction", "document_class", "version")), label

    paths = _scope_paths(scope)
    source_files = (
        sorted(path for path in paths["source_root"].rglob("*") if path.is_file())
        if paths["source_root"].is_dir()
        else []
    )
    if status == SOURCE_REFETCH_REQUIRED:
        assert source_files == [], label
        return

    assert source_files, label
    assert all(paths[name].is_file() for name in paths if name != "source_root"), label

    coverage = json.loads(paths["coverage"].read_text())
    inventory = json.loads(paths["inventory"].read_text())
    ingest_manifest = json.loads(paths["ingest_manifest"].read_text())
    jurisdiction = str(scope["jurisdiction"])
    document_class = str(scope["document_class"])
    version = str(scope["version"])
    assert coverage["complete"] is True
    assert coverage["jurisdiction"] == jurisdiction
    assert coverage["document_class"] == document_class
    assert str(coverage["version"]) == version
    assert ingest_manifest["jurisdiction"] == jurisdiction
    assert ingest_manifest["document_class"] == document_class
    assert str(ingest_manifest["version"]) == version

    applied = {
        item["path"]: item
        for item in ingest_manifest["applied_files"]
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }
    expected_paths = {
        path.relative_to(REPO_ROOT).as_posix()
        for path in [*source_files, paths["inventory"], paths["provisions"], paths["coverage"]]
    }
    assert expected_paths <= applied.keys(), label
    assert all(applied[path].get("deleted") is not True for path in expected_paths), label
    for relative_path, item in applied.items():
        if item.get("deleted") is True:
            continue
        artifact = REPO_ROOT / relative_path
        assert artifact.is_file(), relative_path
        assert item.get("sha256") == _sha256_file_cached(artifact), relative_path

    for inventory_item in inventory["items"]:
        source_path = inventory_item.get("source_path")
        assert isinstance(source_path, str) and source_path, inventory_item["citation_path"]
        source = CORPUS_ROOT / source_path
        assert source.is_file(), source_path
        assert inventory_item.get("sha256") == _sha256_file_cached(source), source_path
        for metadata_path in _nested_source_paths(inventory_item.get("metadata", {})):
            assert (CORPUS_ROOT / metadata_path).is_file(), metadata_path

    expected_citation_path = EXPECTED_TARGET_MANIFEST_PATHS.get(state["jurisdiction"])
    if role == "target" and expected_citation_path:
        manifest_payload = yaml.safe_load((REPO_ROOT / manifest_path).read_text())
        citation_paths = {
            document.get("citation_path") for document in manifest_payload.get("documents", [])
        }
        assert expected_citation_path in citation_paths


def test_state_snap_queue_statuses_match_retained_sources() -> None:
    queue = _queue()
    assert len(queue) == 51

    for state in queue:
        for role, status, manifest_path, scope in _scope_entries(state):
            _assert_scope_matches_retained_sources(
                state=state,
                role=role,
                status=status,
                manifest_path=manifest_path,
                scope=scope,
            )


def test_published_state_snap_ingest_manifests_are_authenticated() -> None:
    public_key = os.environ.get("AXIOM_CORPUS_INGEST_PUBLIC_KEY")
    if not public_key:
        if os.environ.get("CI"):
            pytest.fail("AXIOM_CORPUS_INGEST_PUBLIC_KEY is required in CI")
        pytest.skip("AXIOM_CORPUS_INGEST_PUBLIC_KEY is required for signature verification")

    issues: dict[str, list[str]] = {}
    for state in _queue():
        for role, status, _manifest_path, scope in _scope_entries(state):
            if status != PUBLISHED_CURRENT:
                continue
            manifest_path = _scope_paths(scope)["ingest_manifest"]
            manifest = json.loads(manifest_path.read_text())
            manifest_issues = verify_ingest_manifest(
                manifest,
                public_key=public_key,
                repo=REPO_ROOT,
                head_ref="HEAD",
            )
            if manifest_issues:
                issues[f"{state['jurisdiction']}:{role}"] = manifest_issues

    assert issues == {}


def test_comprehensive_release_tracks_the_state_snap_queue() -> None:
    payload = json.loads(COMPREHENSIVE_RELEASE.read_text())
    release_scopes = {
        (scope["jurisdiction"], scope["document_class"], scope["version"])
        for scope in payload["scopes"]
    }

    published_scopes = set()
    refetch_scopes = set()
    for state in _queue():
        scope = state["target_scope"]
        identity = (scope["jurisdiction"], scope["document_class"], scope["version"])
        if state["queue_status"] == PUBLISHED_CURRENT:
            published_scopes.add(RELEASE_SCOPE_SUBSTITUTIONS.get(identity, identity))
        else:
            refetch_scopes.add(identity)

    assert published_scopes <= release_scopes
    assert refetch_scopes.isdisjoint(release_scopes)
    assert SUPERSEDED_RELEASE_SCOPES.isdisjoint(release_scopes)


def test_massachusetts_consolidation_drops_shadowed_legacy_blocks() -> None:
    paths = _scope_paths(
        {
            "jurisdiction": CONSOLIDATED_MASSACHUSETTS_SCOPE[0],
            "document_class": CONSOLIDATED_MASSACHUSETTS_SCOPE[1],
            "version": CONSOLIDATED_MASSACHUSETTS_SCOPE[2],
        }
    )
    rows = [json.loads(line) for line in paths["provisions"].read_text().splitlines()]
    inventory = json.loads(paths["inventory"].read_text())
    current_source_fragment = "/2026-07-17-ma-dta-snap-regulations/"
    legacy_source_fragment = "/2026-05-28/"
    current_citations = {
        row["citation_path"]
        for row in rows
        if current_source_fragment in (row.get("source_path") or "")
    }
    legacy_rows = [
        row for row in rows if legacy_source_fragment in (row.get("source_path") or "")
    ]

    assert len(rows) == len(inventory["items"]) == 332
    assert {row["citation_path"] for row in legacy_rows} == {
        "us-ma/regulation/106-cmr/364/990",
        "us-ma/regulation/106-cmr/364/990/block-1",
    }
    assert not any(
        row.get("kind") == "block" and row.get("parent_citation_path") in current_citations
        for row in legacy_rows
    )
    assert "file://" not in json.dumps(rows)
    assert "file://" not in json.dumps(inventory)


def test_massachusetts_consolidation_manifest_is_authenticated() -> None:
    public_key = os.environ.get("AXIOM_CORPUS_INGEST_PUBLIC_KEY")
    if not public_key:
        if os.environ.get("CI"):
            pytest.fail("AXIOM_CORPUS_INGEST_PUBLIC_KEY is required in CI")
        pytest.skip("AXIOM_CORPUS_INGEST_PUBLIC_KEY is required for signature verification")

    manifest_path = _scope_paths(
        {
            "jurisdiction": CONSOLIDATED_MASSACHUSETTS_SCOPE[0],
            "document_class": CONSOLIDATED_MASSACHUSETTS_SCOPE[1],
            "version": CONSOLIDATED_MASSACHUSETTS_SCOPE[2],
        }
    )["ingest_manifest"]
    manifest = json.loads(manifest_path.read_text())

    assert (
        verify_ingest_manifest(
            manifest,
            public_key=public_key,
            repo=REPO_ROOT,
            head_ref="HEAD",
        )
        == []
    )
