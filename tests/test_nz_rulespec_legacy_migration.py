"""Audit the one-way migration from RuleSpec-NZ's repo-local corpus."""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from axiom_corpus.corpus.releases import ReleaseManifest
from axiom_corpus.release.manifest import selector_sha256
from scripts import build_nz_rulespec_legacy_migration as migration_builder

REPO_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = REPO_ROOT / "data/corpus/migrations/nz/rulespec-nz-legacy-2026-06-17.json"
RELEASE_NAME = "nz-rulespec-2026-07-10"
SELECTOR_RELATIVE_PATH = Path("manifests/releases") / f"{RELEASE_NAME}.json"
SELECTOR_PATH = REPO_ROOT / SELECTOR_RELATIVE_PATH
VERSION = "2026-06-16-rulespec-nz-pco"
SOURCE_COMMIT = "c9e0c069a8f9ec9aacb41f8f0bb1b5d56c148e38"
SELECTOR_SHA256 = "7e2a7a92e038bb0b1e5cef8d8e5e7830d8bfaceda71cc74ac561b4cab122eff2"


def _sha256_text(value: str | None) -> str | None:
    if value is None:
        return None
    return hashlib.sha256(value.encode()).hexdigest()


def _active_rows(selector: dict) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    for scope in selector["scopes"]:
        path = (
            REPO_ROOT
            / "data/corpus/provisions"
            / scope["jurisdiction"]
            / scope["document_class"]
            / f"{scope['version']}.jsonl"
        )
        for line in path.read_text().splitlines():
            row = json.loads(line)
            assert row["citation_path"] not in rows
            rows[row["citation_path"]] = row
    return rows


def _inventory_source_names(scope: dict) -> tuple[set[str], set[str]]:
    document_class = scope["document_class"]
    inventory_path = (
        REPO_ROOT
        / "data/corpus/inventory"
        / scope["jurisdiction"]
        / document_class
        / f"{scope['version']}.json"
    )
    inventory = json.loads(inventory_path.read_text())
    source_root = (
        REPO_ROOT
        / "data/corpus/sources"
        / scope["jurisdiction"]
        / document_class
        / scope["version"]
    )
    expected = {
        path.relative_to(source_root).as_posix()
        for path in source_root.rglob("*")
        if path.is_file()
    }
    actual = {item["metadata"]["source_name"] for item in inventory["items"]}
    return actual, expected


def _inactive_source_elements(selector: dict) -> tuple[set[str], set[str]]:
    inactive_ids: set[str] = set()
    deletion_statuses: set[str] = set()
    for scope in selector["scopes"]:
        source_root = (
            REPO_ROOT
            / "data/corpus/sources"
            / scope["jurisdiction"]
            / scope["document_class"]
            / scope["version"]
        )
        for source_path in source_root.rglob("*.xml"):
            root = ET.fromstring(source_path.read_bytes())
            parents = {child: parent for parent in root.iter() for child in parent}
            for element in root.iter():
                own_status = (element.get("deletion-status") or "").strip()
                if own_status:
                    deletion_statuses.add(own_status.lower())
                element_id = element.get("id")
                if not element_id:
                    continue
                current: ET.Element | None = element
                while current is not None:
                    if (current.get("deletion-status") or "").strip():
                        inactive_ids.add(element_id)
                        break
                    current = parents.get(current)
    return inactive_ids, deletion_statuses


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "https://www.legislation.govt.nz/act/public/2007/0097/latest/DLM1512320.html",
            "dlm1512320",
        ),
        (
            "https://www.legislation.govt.nz/secondary-legislation/pco-drafted/2018/202/latest/LMS96256.html",
            "lms96256",
        ),
        ("https://attacker.example/LMS96256.html", None),
        (
            "https://www.legislation.govt.nz.attacker.example/act/public/2007/0097/latest/DLM1512320.html",
            None,
        ),
        (
            "https://www.legislation.govt.nz@attacker.example/act/public/2007/0097/latest/DLM1512320.html",
            None,
        ),
        (
            "https://www.legislation.govt.nz:443/act/public/2007/0097/latest/DLM1512320.html",
            None,
        ),
        (
            "http://www.legislation.govt.nz/act/public/2007/0097/latest/DLM1512320.html",
            None,
        ),
        (
            "https://www.legislation.govt.nz/act/public/2007/0097/latest/DLM1512320.html?redirect=1",
            None,
        ),
        (
            "https://www.legislation.govt.nz/act/public/2007/0097/latest/DLM1512320.html#fragment",
            None,
        ),
        (
            "https://www.legislation.govt.nz/not-legislation/latest/DLM1512320.html",
            None,
        ),
    ],
)
def test_pco_element_id_requires_canonical_official_page_url(url, expected):
    assert migration_builder._url_element_id(url) == expected


def test_attacker_url_cannot_authorize_official_pco_element_id_mapping():
    canonical = {
        "citation_path": "nz/statute/act/public/2007/0097/section/md-3",
        "source_url": (
            "https://www.legislation.govt.nz/act/public/2007/0097/latest/DLM1512320.html"
        ),
    }
    indexes = migration_builder._canonical_indexes([canonical])

    matches, basis = migration_builder._resolve_canonical_matches(
        {
            "citation_path": "nz/statute/attacker-controlled",
            "source_url": "https://attacker.example/DLM1512320.html",
        },
        indexes,
    )

    assert matches == []
    assert basis is None


def test_legacy_collision_suffix_maps_only_to_matching_canonical_pco_identity():
    canonical = {
        "citation_path": "nz/statute/act/public/1985/0141/section/8",
        "identifiers": {"legislation.govt.nz:provision": "DLM82299"},
        "source_url": ("https://www.legislation.govt.nz/act/public/1985/0141/latest/DLM82299.html"),
    }
    indexes = migration_builder._canonical_indexes([canonical])

    matches, basis = migration_builder._resolve_canonical_matches(
        {"citation_path": ("nz/statute/act/public/1985/0141/section/8-DLM82299")},
        indexes,
    )

    assert matches == [canonical]
    assert basis == "official-pco-element-id-citation-suffix"


@pytest.mark.parametrize(
    "legacy_path",
    [
        "nz/statute/act/public/1985/0141/section/8-DLM00000",
        "nz/statute/attacker-controlled-DLM82299",
        "nz/statute/act/public/1985/0141/section/8-DLM82299-extra",
    ],
)
def test_legacy_collision_suffix_rejects_wrong_identity_or_path(legacy_path):
    canonical = {
        "citation_path": "nz/statute/act/public/1985/0141/section/8",
        "identifiers": {"legislation.govt.nz:provision": "DLM82299"},
        "source_url": ("https://www.legislation.govt.nz/act/public/1985/0141/latest/DLM82299.html"),
    }
    indexes = migration_builder._canonical_indexes([canonical])

    matches, basis = migration_builder._resolve_canonical_matches(
        {"citation_path": legacy_path},
        indexes,
    )

    assert matches == []
    assert basis is None


def test_nz_legacy_migration_accounts_for_every_row_without_silent_loss():
    migration = json.loads(MIGRATION_PATH.read_text())
    selector = json.loads(SELECTOR_PATH.read_text())
    release = ReleaseManifest.load(SELECTOR_PATH)

    assert selector == {
        "description": "Immutable official New Zealand legislation scopes used by RuleSpec-NZ.",
        "name": RELEASE_NAME,
        "scopes": [
            {
                "document_class": "regulation",
                "jurisdiction": "nz",
                "version": VERSION,
            },
            {
                "document_class": "statute",
                "jurisdiction": "nz",
                "version": VERSION,
            },
        ],
    }
    assert migration["canonical_release"] == selector["name"]
    assert migration["canonical_scopes"] == selector["scopes"]
    assert selector_sha256(release) == SELECTOR_SHA256
    assert migration["canonical_release_cut_plan"] == {
        "path": SELECTOR_RELATIVE_PATH.as_posix(),
        "selector_sha256": SELECTOR_SHA256,
    }
    assert "canonical_release_selector_sha256" not in migration
    assert migration["schema_version"] == ("axiom-corpus/nz-rulespec-legacy-migration/v2")
    assert not (REPO_ROOT / "manifests/releases/current.json").exists()
    assert not (REPO_ROOT / "manifests/releases/nz-rulespec-current.json").exists()
    assert migration["source_repository"] == "TheAxiomFoundation/rulespec-nz"
    assert migration["source_commit"] == SOURCE_COMMIT
    assert migration["legacy_row_count"] == 199
    assert migration["legacy_unique_citation_count"] == 195
    assert migration["disposition_counts"] == {
        "canonical": 185,
        "superseded": 14,
    }
    assert migration["prior_external_status_counts"] == {
        "absent": 130,
        "shared-divergent": 69,
    }

    entries = migration["entries"]
    assert len(entries) == 199
    assert len({(entry["legacy"]["artifact"], entry["legacy"]["line"]) for entry in entries}) == 199
    assert len({entry["legacy"]["citation_path"] for entry in entries}) == 195
    assert Counter(entry["prior_external_status"] for entry in entries) == {
        "absent": 130,
        "shared-divergent": 69,
    }
    assert all(entry["body_relation"] == "official-source-reextraction" for entry in entries)

    active = _active_rows(selector)
    assert len(active) == 10_171
    assert Counter(row["document_class"] for row in active.values()) == {
        "regulation": 652,
        "statute": 9_519,
    }
    schedule_clauses = [
        row
        for row in active.values()
        if row["kind"] == "clause" and "/schedule/" in row["citation_path"]
    ]
    assert len(schedule_clauses) == 1_283
    assert Counter(row["document_class"] for row in schedule_clauses) == {
        "regulation": 114,
        "statute": 1_169,
    }
    assert not any(
        path == "nz/statute/act/public/2011/0067"
        or path.startswith("nz/statute/act/public/2011/0067/")
        for path in active
    )
    for entry in entries:
        legacy = entry["legacy"]
        assert legacy["artifact"].startswith("data/corpus/provisions/nz/")
        assert len(legacy["row_sha256"]) == 64
        assert len(legacy["body_sha256"]) == 64
        assert legacy["source_url_sha256"] is None or len(legacy["source_url_sha256"]) == 64
        assert entry["canonical"]
        assert entry["rationale"]
        if entry["prior_external_status"] == "shared-divergent":
            assert len(entry["prior_external_body_sha256"]) == 64
            assert entry["prior_external_body_sha256"] != legacy["body_sha256"]
        else:
            assert entry["prior_external_body_sha256"] is None

        for target in entry["canonical"]:
            row = active[target["citation_path"]]
            assert row["body"] is not None
            assert target["id"] == row["id"]
            assert target["version"] == VERSION
            assert target["body_sha256"] == _sha256_text(row["body"])
            assert target["source_url_sha256"] == _sha256_text(row["source_url"])
            for required in (
                "id",
                "source_path",
                "source_as_of",
                "expression_date",
            ):
                assert row[required]

    schedule_21 = active["nz/statute/act/public/2007/0097/schedule/21"]
    schedule_39 = active["nz/statute/act/public/2007/0097/schedule/39"]
    assert schedule_21["identifiers"]["legislation.govt.nz:element"] == "LMS199577"
    assert schedule_39["identifiers"]["legislation.govt.nz:element"] == "LMS960776"

    inactive_ids, deletion_statuses = _inactive_source_elements(selector)
    emitted_element_ids = {
        row.get("identifiers", {}).get("legislation.govt.nz:provision")
        or row.get("identifiers", {}).get("legislation.govt.nz:element")
        for row in active.values()
    }
    assert {"expired", "repealed", "revoked"} <= deletion_statuses
    assert emitted_element_ids.isdisjoint(inactive_ids)

    superseded = [entry for entry in entries if entry["disposition"] == "superseded"]
    assert Counter(entry["mapping_basis"] for entry in superseded) == {
        "explicit-agency-summary-supersession": 5,
        "explicit-pco-hierarchy-supersession": 9,
    }


def test_rulespec_pco_citations_have_only_explicit_hierarchy_supersessions():
    migration = json.loads(MIGRATION_PATH.read_text())
    expected = {
        "nz/regulation/regulation/public/1998/0277/regulation/4-lms1588497": (
            "nz/regulation/regulation/public/1998/0277/schedule/2/part/2/clause/4",
            "LMS1588497",
        ),
        "nz/statute/act/public/2001/0049/section/32-dlm104829": (
            "nz/statute/act/public/2001/0049/schedule/1/part/2/clause/32",
            "DLM104829",
        ),
        "nz/statute/act/public/2001/0049/section/47-dlm104891": (
            "nz/statute/act/public/2001/0049/schedule/1/part/2/clause/47",
            "DLM104891",
        ),
        "nz/statute/act/public/2007/0097/section/1-dlm1523194": (
            "nz/statute/act/public/2007/0097/schedule/1/part/a/clause/1",
            "DLM1523194",
        ),
        "nz/statute/act/public/2018/0032/section/19-dlm6784845": (
            "nz/statute/act/public/2018/0032/schedule/3/part/5/clause/19",
            "DLM6784845",
        ),
        "nz/statute/act/public/2018/0032/schedule/4/part/1": (
            "nz/statute/act/public/2018/0032/schedule/4/part/1/clause/lms118447",
            "LMS118447",
        ),
        "nz/statute/act/public/2018/0032/schedule/4/part/2": (
            "nz/statute/act/public/2018/0032/schedule/4/part/2/clause/lms118467",
            "LMS118467",
        ),
        "nz/statute/act/public/2018/0032/schedule/4/part/3": (
            "nz/statute/act/public/2018/0032/schedule/4/part/3/clause/lms118466",
            "LMS118466",
        ),
        "nz/statute/act/public/2018/0032/schedule/4/part/7": (
            "nz/statute/act/public/2018/0032/schedule/4/part/7/clause/lms118453",
            "LMS118453",
        ),
        "nz/statute/act/public/2018/0032/schedule/4/part/8": (
            "nz/statute/act/public/2018/0032/schedule/4/part/8/clause/lms118454",
            "LMS118454",
        ),
        "nz/statute/act/public/2018/0032/schedule/4/part/9": (
            "nz/statute/act/public/2018/0032/schedule/4/part/9/clause/lms118455",
            "LMS118455",
        ),
    }
    records = migration["rulespec_citation_supersessions"]

    assert len(records) == 11
    assert {
        record["legacy_citation_path"]: (
            record["canonical"]["citation_path"],
            record["pco_provision_id"],
        )
        for record in records
    } == expected
    assert all(
        record["mapping_basis"] == "explicit-pco-hierarchy-supersession" for record in records
    )


def test_bodyless_schedule_parts_map_only_to_their_explicit_table_clause():
    migration = json.loads(MIGRATION_PATH.read_text())
    selector = json.loads(SELECTOR_PATH.read_text())
    active = _active_rows(selector)
    entries = {entry["legacy"]["citation_path"].lower(): entry for entry in migration["entries"]}
    expected = {
        "nz/statute/act/public/2018/0032/schedule/4/part/1": (
            "nz/statute/act/public/2018/0032/schedule/4/part/1/clause/lms118447",
            "LMS118447",
        ),
        "nz/statute/act/public/2018/0032/schedule/4/part/2": (
            "nz/statute/act/public/2018/0032/schedule/4/part/2/clause/lms118467",
            "LMS118467",
        ),
        "nz/statute/act/public/2018/0032/schedule/4/part/3": (
            "nz/statute/act/public/2018/0032/schedule/4/part/3/clause/lms118466",
            "LMS118466",
        ),
        "nz/statute/act/public/2018/0032/schedule/4/part/7": (
            "nz/statute/act/public/2018/0032/schedule/4/part/7/clause/lms118453",
            "LMS118453",
        ),
        "nz/statute/act/public/2018/0032/schedule/4/part/8": (
            "nz/statute/act/public/2018/0032/schedule/4/part/8/clause/lms118454",
            "LMS118454",
        ),
        "nz/statute/act/public/2018/0032/schedule/4/part/9": (
            "nz/statute/act/public/2018/0032/schedule/4/part/9/clause/lms118455",
            "LMS118455",
        ),
    }
    body_indexes = migration_builder._canonical_indexes(
        [row for row in active.values() if row.get("body") is not None]
    )

    for old_path, (target_path, pco_id) in expected.items():
        assert active[old_path].get("body") is None
        body_descendants = [
            row["citation_path"]
            for row in active.values()
            if row["citation_path"].startswith(f"{old_path}/") and row.get("body") is not None
        ]
        assert body_descendants == [target_path]
        assert active[target_path]["identifiers"]["legislation.govt.nz:provision"] == pco_id
        assert active[target_path]["body"]
        entry = entries[old_path]
        assert entry["mapping_basis"] == "explicit-pco-hierarchy-supersession"
        assert [target["citation_path"] for target in entry["canonical"]] == [target_path]
        assert migration_builder._resolve_canonical_matches(
            {
                "citation_path": old_path,
                "source_url": active[old_path]["source_url"],
            },
            body_indexes,
        ) == ([], None)


def test_legacy_schedule_aliases_resolve_to_the_preserved_pco_hierarchy():
    migration = json.loads(MIGRATION_PATH.read_text())
    entries = {entry["legacy"]["citation_path"].lower(): entry for entry in migration["entries"]}
    expected = {
        "nz/statute/act/public/2007/0097/section/1-dlm1523194": (
            "nz/statute/act/public/2007/0097/schedule/1/part/a/clause/1",
            "DLM1523194",
        ),
        "nz/statute/act/public/2018/0032/schedule/3/clause/19": (
            "nz/statute/act/public/2018/0032/schedule/3/part/5/clause/19",
            "DLM6784845",
        ),
        "nz/statute/act/public/2018/0032/schedule/4/part/9/clause/2": (
            "nz/statute/act/public/2018/0032/schedule/4/part/9/clause/lms118455",
            "LMS118455",
        ),
    }
    active = _active_rows(json.loads(SELECTOR_PATH.read_text()))

    for legacy_path, (target_path, pco_id) in expected.items():
        entry = entries[legacy_path]
        assert entry["mapping_basis"] == "explicit-pco-hierarchy-supersession"
        assert [target["citation_path"] for target in entry["canonical"]] == [target_path]
        assert active[target_path]["identifiers"]["legislation.govt.nz:provision"] == pco_id


def test_nz_release_inventory_uses_canonical_identifying_source_names():
    selector = json.loads(SELECTOR_PATH.read_text())
    source_counts: dict[str, int] = {}

    for scope in selector["scopes"]:
        actual, expected = _inventory_source_names(scope)
        assert actual == expected
        assert all("/" in source_name for source_name in actual)
        source_counts[scope["document_class"]] = len(actual)

    assert source_counts == {"regulation": 9, "statute": 20}


def test_regulation_8_subclauses_map_to_the_official_regulation_8_source():
    migration = json.loads(MIGRATION_PATH.read_text())
    prefix = "nz/regulation/regulation/public/1993/0169/regulation/8/subclause/"
    expected_subclauses = {"1", "3", "4", "5", "5A", "6", "7", "8"}
    entries = {
        entry["legacy"]["citation_path"].removeprefix(prefix): entry
        for entry in migration["entries"]
        if entry["legacy"]["citation_path"].startswith(prefix)
    }

    assert set(entries) == expected_subclauses
    for entry in entries.values():
        assert entry["mapping_basis"] == "official-source-url"
        assert [target["citation_path"] for target in entry["canonical"]] == [
            "nz/regulation/regulation/public/1993/0169/regulation/8"
        ]


def test_canonical_resolution_does_not_guess_from_a_subclause_last_label():
    regulation_1 = {
        "citation_path": "nz/regulation/regulation/public/1993/0169/regulation/1",
        "source_url": "https://www.legislation.govt.nz/id/regulation-1.html",
    }
    regulation_8 = {
        "citation_path": "nz/regulation/regulation/public/1993/0169/regulation/8",
        "source_url": "https://www.legislation.govt.nz/id/regulation-8.html",
    }
    indexes = migration_builder._canonical_indexes([regulation_1, regulation_8])
    legacy = {
        "citation_path": ("nz/regulation/regulation/public/1993/0169/regulation/8/subclause/1"),
        "source_url": "https://www.legislation.govt.nz/id/unrelated.html",
    }

    assert migration_builder._resolve_canonical_matches(legacy, indexes) == ([], None)


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _make_legacy_checkout(tmp_path: Path) -> tuple[Path, Path, str]:
    checkout = tmp_path / "rulespec-nz"
    legacy_root = checkout / "data/corpus/provisions/nz"
    legacy_root.mkdir(parents=True)
    (legacy_root / "README").write_text("immutable fixture\n")
    subprocess.run(["git", "init", "-q", str(checkout)], check=True)
    _git(checkout, "config", "user.name", "Test")
    _git(checkout, "config", "user.email", "test@example.com")
    _git(checkout, "add", ".")
    _git(checkout, "commit", "-qm", "fixture")
    return checkout, legacy_root, _git(checkout, "rev-parse", "HEAD")


def test_legacy_checkout_verifier_requires_the_exact_source_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _, legacy_root, commit = _make_legacy_checkout(tmp_path)
    monkeypatch.setattr(migration_builder, "SOURCE_COMMIT", commit)
    assert migration_builder._verified_legacy_checkout_root(legacy_root) == (
        legacy_root.parents[3].resolve()
    )

    with pytest.raises(ValueError, match="exact data/corpus/provisions/nz"):
        migration_builder._verified_legacy_checkout_root(legacy_root.parent)

    monkeypatch.setattr(migration_builder, "SOURCE_COMMIT", "0" * 40)
    with pytest.raises(ValueError, match="must be exactly"):
        migration_builder._verified_legacy_checkout_root(legacy_root)


def test_legacy_checkout_verifier_rejects_a_dirty_source_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _, legacy_root, commit = _make_legacy_checkout(tmp_path)
    monkeypatch.setattr(migration_builder, "SOURCE_COMMIT", commit)
    (legacy_root / "untracked.jsonl").write_text("{}\n")

    with pytest.raises(ValueError, match="must be clean"):
        migration_builder._verified_legacy_checkout_root(legacy_root)
