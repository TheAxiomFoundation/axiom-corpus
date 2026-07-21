from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.bind_inventory_source_hashes import bind_inventory_source_hashes

VERSION = "2026-test"
SOURCE_RELATIVE = f"sources/ca/policy/{VERSION}/official/source.txt"


def _fixture(tmp_path: Path, *, sha256: str | None = None) -> tuple[Path, Path, Path]:
    source = tmp_path / "data" / "corpus" / SOURCE_RELATIVE
    source.parent.mkdir(parents=True)
    source.write_text("official source\n", encoding="utf-8")
    inventory = tmp_path / "data" / "corpus" / "inventory" / "ca" / "policy" / f"{VERSION}.json"
    inventory.parent.mkdir(parents=True)
    item = {
        "citation_path": "ca/policy/test",
        "source_path": SOURCE_RELATIVE,
        "metadata": {"primary_source": True},
    }
    if sha256 is not None:
        item["sha256"] = sha256
    inventory.write_text(
        json.dumps(
            {
                "document_class": "policy",
                "items": [item],
                "jurisdiction": "ca",
                "source_count": 1,
                "version": VERSION,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    release = tmp_path / "release.json"
    release.write_text(
        json.dumps(
            {
                "name": "ca-test-release",
                "scopes": [
                    {
                        "document_class": "policy",
                        "jurisdiction": "ca",
                        "version": VERSION,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return release, inventory, source


def test_dry_run_then_write_binds_source_hash_and_preserves_inventory(tmp_path: Path) -> None:
    release, inventory, source = _fixture(tmp_path)
    original = inventory.read_bytes()

    preview = bind_inventory_source_hashes(tmp_path, release)
    assert preview["bound_items"] == 1
    assert inventory.read_bytes() == original

    applied = bind_inventory_source_hashes(tmp_path, release, write=True)
    payload = json.loads(inventory.read_text(encoding="utf-8"))
    assert applied["changed_scopes"] == [f"ca/policy/{VERSION}"]
    assert payload["source_count"] == 1
    assert payload["items"][0]["sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()


def test_existing_mismatched_hash_fails_closed(tmp_path: Path) -> None:
    release, _, _ = _fixture(tmp_path, sha256="0" * 64)

    with pytest.raises(ValueError, match="source sha256 mismatch"):
        bind_inventory_source_hashes(tmp_path, release, write=True)


def test_source_path_must_stay_inside_release_scope(tmp_path: Path) -> None:
    release, inventory, _ = _fixture(tmp_path)
    payload = json.loads(inventory.read_text(encoding="utf-8"))
    payload["items"][0]["source_path"] = "sources/ca/policy/another/official/source.txt"
    inventory.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="outside its release scope"):
        bind_inventory_source_hashes(tmp_path, release)


def test_write_does_not_partially_apply_before_all_scopes_validate(tmp_path: Path) -> None:
    release, first_inventory, _ = _fixture(tmp_path)
    first_original = first_inventory.read_bytes()
    second_version = "2026-test-later"
    second_source_relative = f"sources/ca/policy/{second_version}/official/source.txt"
    second_source = tmp_path / "data" / "corpus" / second_source_relative
    second_source.parent.mkdir(parents=True)
    second_source.write_text("later official source\n", encoding="utf-8")
    second_inventory = (
        tmp_path
        / "data"
        / "corpus"
        / "inventory"
        / "ca"
        / "policy"
        / f"{second_version}.json"
    )
    second_inventory.write_text(
        json.dumps(
            {
                "document_class": "policy",
                "items": [
                    {
                        "citation_path": "ca/policy/test-later",
                        "source_path": second_source_relative,
                        "sha256": "0" * 64,
                    }
                ],
                "jurisdiction": "ca",
                "source_count": 1,
                "version": second_version,
            }
        ),
        encoding="utf-8",
    )
    release_payload = json.loads(release.read_text(encoding="utf-8"))
    release_payload["scopes"].append(
        {
            "document_class": "policy",
            "jurisdiction": "ca",
            "version": second_version,
        }
    )
    release.write_text(json.dumps(release_payload), encoding="utf-8")

    with pytest.raises(ValueError, match="source sha256 mismatch"):
        bind_inventory_source_hashes(tmp_path, release, write=True)

    assert first_inventory.read_bytes() == first_original
