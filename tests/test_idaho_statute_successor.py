import hashlib
import json
from pathlib import Path

from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from scripts.repro.idaho_title_63_chapter_30_successor import (
    BASE_RELEASE,
    RELEASE,
    SECTIONS,
    VERSION,
    build_scope,
    write_release,
)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_idaho_successor_uses_native_sections_and_is_deterministic(tmp_path):
    source_base = Path("data/corpus")
    first = tmp_path / "first"
    second = tmp_path / "second"
    first_paths = build_scope(base=first, source_base=source_base)
    second_paths = build_scope(base=second, source_base=source_base)

    assert [_digest(path) for path in first_paths] == [_digest(path) for path in second_paths]
    inventory = load_source_inventory(first_paths[0])
    records = load_provisions(first_paths[1])
    assert [record.citation_path for record in records] == [
        "us-id/statute/title-63",
        "us-id/statute/title-63/chapter-30",
        *(f"us-id/statute/{section}" for section in SECTIONS),
    ]
    assert len(inventory) == len(records) == 7
    assert not any("/block-" in record.citation_path for record in records)

    section = next(record for record in records if record.citation_path == "us-id/statute/63-3024")
    assert section.kind == "section"
    assert section.heading == "Individuals’ tax and tax on estates and trusts"
    assert "five and three-tenths percent (5.3%)" in (section.body or "")
    assert "$2,500" in (section.body or "")
    assert "$5,000" in (section.body or "")
    assert "consumer price index" in (section.body or "").lower()
    assert "How current is this law?" not in (section.body or "")
    assert section.metadata is not None
    assert section.metadata["references_to"] == ["us-id/statute/63-3031"]
    assert section.metadata["source_history"]

    for citation in ("63-3022E", "63-3025D"):
        rendition = next(
            record for record in records if record.citation_path == f"us-id/statute/{citation}"
        )
        assert "[effective until January 1, 2027]" in (rendition.body or "")
        assert "[effective January 1, 2027]" not in (rendition.body or "")
        assert f"{citation}." not in (rendition.body or "")
        assert "subsection (5) of section 66-402" in (rendition.body or "")
        assert "66-402 (4)" not in (rendition.body or "")


def test_idaho_successor_preserves_all_retained_source_hashes(tmp_path):
    build_scope(base=tmp_path, source_base=Path("data/corpus"))
    old = Path("data/corpus/sources/us-id/statute/2026-07-13-recovery")
    new = tmp_path / f"sources/us-id/statute/{VERSION}"
    for source in old.joinpath("official-documents").iterdir():
        assert _digest(source) == _digest(new / "official-documents" / source.name)
    for provenance in old.joinpath("provenance").iterdir():
        assert provenance.read_bytes() == (new / "provenance" / provenance.name).read_bytes()


def test_idaho_release_replaces_only_the_statute_scope(tmp_path):
    release_dir = Path("manifests/releases")
    old = json.loads((release_dir / f"{BASE_RELEASE}.json").read_text())
    generated = write_release(release_dir=release_dir, output_dir=tmp_path)
    new = json.loads(generated.read_text())
    expected_scopes = [dict(scope) for scope in old["scopes"]]
    target = next(
        scope
        for scope in expected_scopes
        if scope
        == {
            "document_class": "statute",
            "jurisdiction": "us-id",
            "version": "2026-07-13-recovery",
        }
    )
    target["version"] = VERSION

    assert new["name"] == RELEASE
    assert new["quality_profile"] == old["quality_profile"]
    assert new["scopes"] == expected_scopes
