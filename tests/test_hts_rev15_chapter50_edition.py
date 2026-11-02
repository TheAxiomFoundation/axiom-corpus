import hashlib
import json
from pathlib import Path

import pytest

from scripts.repro import us_hts_rev15_chapter50_edition as edition

SOURCE = (
    Path(__file__).resolve().parents[1]
    / "data/corpus"
    / edition.full._canonical_source_path(edition.SNAPSHOT)
)


def test_disjoint_scope_preserves_full_chapter_bodies_and_is_deterministic(tmp_path):
    outputs = [tmp_path / "first", tmp_path / "second"]
    manifests = [edition.build_scope(p, SOURCE) for p in outputs]
    assert manifests[0] == manifests[1]
    for relative in manifests[0]["artifacts"]:
        assert (outputs[0] / relative).read_bytes() == (outputs[1] / relative).read_bytes()
    provision = next(outputs[0].rglob("*.jsonl"))
    records = [json.loads(line) for line in provision.read_text().splitlines()]
    original = edition.full._target_blocks(json.loads(SOURCE.read_bytes()))
    expected = [b for b in original if edition.full._chapter_key(b.metadata["htsno"]) == "50"]
    inventory_file = next(outputs[0].glob("inventory/us/statute/*.json"))
    inventory = json.loads(inventory_file.read_text())["items"]
    assert len(inventory) == 42
    assert [r["citation_path"] for r in inventory] == [r["citation_path"] for r in records]
    assert all(
        r["metadata"]["normalization_scope"] == "chapter-50-source-edition-all-htsno-rows"
        for r in inventory
    )
    assert (outputs[0] / manifests[0]["artifacts"][0]).read_bytes() == SOURCE.read_bytes()
    assert records[0]["metadata"]["members"] == [
        {
            "htsno": b.metadata["htsno"],
            "source_row_index": b.metadata["row_index"],
            "body_sha256": hashlib.sha256(b.body.encode()).hexdigest(),
        }
        for b in expected
    ]
    assert inventory[0]["metadata"]["members"] == records[0]["metadata"]["members"]
    assert len(records) == 42
    assert all(
        r["metadata"]["normalization_scope"] == "chapter-50-source-edition-all-htsno-rows"
        for r in records
    )
    assert records[0]["citation_path"] == edition.ROOT
    assert not records[0].get("body")
    assert [r["body"] for r in records[1:]] == [b.body for b in expected]
    assert len({r["citation_path"] for r in records}) == 42
    assert all(not r["citation_path"].startswith("us/statute/hts/") for r in records)
    assert [r["citation_path"] for r in records[1:]] == [
        edition.ROOT + "/" + b.metadata["htsno"] for b in expected
    ]
    assert (
        records[0]["metadata"]["retained_snapshot_sha256"]
        == hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    )
    with pytest.raises(ValueError, match="overwrite"):
        edition.build_scope(outputs[0], SOURCE)


def test_wrong_source_fails_before_writing(tmp_path):
    source = tmp_path / "wrong.json"
    source.write_text("[]")
    destination = tmp_path / "output"
    with pytest.raises(ValueError, match="SHA mismatch"):
        edition.build_scope(destination, source)
    assert not destination.exists()


def test_symlink_parent_is_rejected_without_writing(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    link = tmp_path / "link"
    link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="symlinks"):
        edition.build_scope(link / "new", SOURCE)
    assert list(outside.iterdir()) == []


def test_existing_output_preserved(tmp_path):
    output = tmp_path / "output"
    output.mkdir()
    sentinel = output / "keep"
    sentinel.write_bytes(b"unchanged")
    with pytest.raises(ValueError, match="fresh"):
        edition.build_scope(output, SOURCE)
    assert sentinel.read_bytes() == b"unchanged"
    assert list(output.iterdir()) == [sentinel]


def test_missing_chapter_member_fails_before_writing(tmp_path, monkeypatch):
    original = edition.full._target_blocks

    def missing(rows):
        blocks = list(original(rows))
        target = next(i for i, b in enumerate(blocks) if b.metadata["htsno"].startswith("50"))
        blocks[target] = blocks[0]  # Preserve full census, remove one chapter member.
        return tuple(blocks)

    monkeypatch.setattr(edition.full, "_target_blocks", missing)
    with pytest.raises(ValueError, match="41 unique"):
        edition.build_scope(tmp_path / "output", SOURCE)
    assert not (tmp_path / "output").exists()
