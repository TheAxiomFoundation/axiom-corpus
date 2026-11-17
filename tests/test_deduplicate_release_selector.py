from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from scripts.deduplicate_release_selector import deduplicate


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _write_scope(corpus: Path, version: str, paths: list[str]) -> None:
    scope_root = ("us-example", "statute")
    provisions = corpus.joinpath("provisions", *scope_root, f"{version}.jsonl")
    inventory = corpus.joinpath("inventory", *scope_root, f"{version}.json")
    coverage = corpus.joinpath("coverage", *scope_root, f"{version}.json")
    provisions.parent.mkdir(parents=True, exist_ok=True)
    provisions.write_text(
        "".join(
            json.dumps(
                {
                    "citation_path": path,
                    "document_class": "statute",
                    "jurisdiction": "us-example",
                    "version": version,
                },
                sort_keys=True,
            )
            + "\n"
            for path in paths
        )
    )
    _write_json(inventory, {"items": [{"citation_path": path} for path in paths]})
    _write_json(
        coverage,
        {
            "complete": True,
            "document_class": "statute",
            "duplicate_provision_citations": [],
            "duplicate_source_citations": [],
            "extra_provisions": [],
            "jurisdiction": "us-example",
            "matched_count": len(paths),
            "missing_from_provisions": [],
            "provision_count": len(paths),
            "source_count": len(paths),
            "version": version,
        },
    )


def _write_selector(path: Path, versions: list[str], *, bases: tuple[str, ...] = ()) -> None:
    _write_json(
        path,
        {
            "scopes": [
                {
                    "document_class": "statute",
                    "jurisdiction": "us-example",
                    "version": version,
                    **({"layer": "base"} if version in bases else {}),
                }
                for version in versions
            ]
        },
    )


def _scope_files(corpus: Path, version: str) -> list[Path]:
    return [
        corpus.joinpath("provisions", "us-example", "statute", f"{version}.jsonl"),
        corpus.joinpath("inventory", "us-example", "statute", f"{version}.json"),
        corpus.joinpath("coverage", "us-example", "statute", f"{version}.json"),
    ]


def _digests(paths: list[Path]) -> dict[Path, str]:
    return {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def _provision_paths(corpus: Path, version: str) -> list[str]:
    provisions = corpus.joinpath("provisions", "us-example", "statute", f"{version}.jsonl")
    return [json.loads(line)["citation_path"] for line in provisions.read_text().splitlines()]


def _base_mapping(version: str) -> dict[str, str]:
    return {
        "document_class": "statute",
        "jurisdiction": "us-example",
        "layer": "base",
        "version": version,
    }


def test_deduplicate_retains_canonical_carrier_and_refreshes_added_scope(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    canonical = tmp_path / "canonical.json"
    target = tmp_path / "target.json"
    _write_scope(corpus, "canonical", ["us-example/statute/1"])
    _write_scope(corpus, "added", ["us-example/statute/1", "us-example/statute/2"])
    _write_selector(canonical, ["canonical"])
    _write_selector(target, ["canonical", "added"])

    dry_run = deduplicate(corpus, canonical, target, apply=False)
    assert dry_run["collision_count"] == 1
    assert "us-example/statute/1" in (
        corpus / "provisions/us-example/statute/added.jsonl"
    ).read_text()

    applied = deduplicate(corpus, canonical, target, apply=True)
    assert applied["collision_count"] == 1
    assert [
        json.loads(line)["citation_path"]
        for line in (corpus / "provisions/us-example/statute/added.jsonl").read_text().splitlines()
    ] == ["us-example/statute/2"]
    inventory = json.loads((corpus / "inventory/us-example/statute/added.json").read_text())
    coverage = json.loads((corpus / "coverage/us-example/statute/added.json").read_text())
    assert inventory["items"] == [{"citation_path": "us-example/statute/2"}]
    assert coverage["complete"] is True
    assert coverage["matched_count"] == coverage["provision_count"] == 1


def test_deduplicate_rejects_ambiguous_added_carriers(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    canonical = tmp_path / "canonical.json"
    target = tmp_path / "target.json"
    for version in ("canonical", "added-one", "added-two"):
        _write_scope(corpus, version, ["us-example/statute/1"])
    _write_selector(canonical, ["canonical"])
    _write_selector(target, ["canonical", "added-one", "added-two"])

    with pytest.raises(ValueError, match="ambiguous citation carrier"):
        deduplicate(corpus, canonical, target, apply=False)


def test_deduplicate_reports_inherited_canonical_collisions(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    canonical = tmp_path / "canonical.json"
    target = tmp_path / "target.json"
    _write_scope(corpus, "canonical-one", ["us-example/statute/1"])
    _write_scope(corpus, "canonical-two", ["us-example/statute/1"])
    _write_scope(corpus, "added", ["us-example/statute/2"])
    _write_selector(canonical, ["canonical-one", "canonical-two"])
    _write_selector(target, ["canonical-one", "canonical-two", "added"])

    report = deduplicate(corpus, canonical, target, apply=False)
    assert report["collision_count"] == 0
    assert report["inherited_collision_count"] == 1
    assert report["inherited_collision_paths"] == ["us-example/statute/1"]


def test_deduplicate_preflights_every_scope_before_writing(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    canonical = tmp_path / "canonical.json"
    target = tmp_path / "target.json"
    _write_scope(
        corpus,
        "canonical",
        ["us-example/statute/1", "us-example/statute/2"],
    )
    _write_scope(
        corpus,
        "added-a-good",
        ["us-example/statute/1", "us-example/statute/3"],
    )
    _write_scope(
        corpus,
        "added-z-bad",
        ["us-example/statute/2", "us-example/statute/4"],
    )
    _write_selector(canonical, ["canonical"])
    _write_selector(target, ["canonical", "added-a-good", "added-z-bad"])
    bad_inventory = corpus / "inventory/us-example/statute/added-z-bad.json"
    _write_json(bad_inventory, {"items": [{"citation_path": "us-example/statute/4"}]})
    good_provisions = corpus / "provisions/us-example/statute/added-a-good.jsonl"
    before = good_provisions.read_text()

    with pytest.raises(ValueError, match="expected one inventory item"):
        deduplicate(corpus, canonical, target, apply=True)

    assert good_provisions.read_text() == before


def test_deduplicate_never_opens_or_cuts_an_added_base(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    corpus = tmp_path / "corpus"
    canonical = tmp_path / "canonical.json"
    target = tmp_path / "target.json"
    _write_scope(
        corpus,
        "canonical",
        ["us-example/statute/1", "us-example/statute/2", "us-example/statute/5"],
    )
    _write_scope(
        corpus,
        "base",
        ["us-example/statute/1", "us-example/statute/2", "us-example/statute/3"],
    )
    _write_scope(corpus, "added", ["us-example/statute/4", "us-example/statute/5"])
    _write_selector(canonical, ["canonical"])
    _write_selector(target, ["canonical", "base", "added"], bases=("base",))
    base_files = _scope_files(corpus, "base")
    before = _digests(base_files)
    opened: list[Path] = []
    read_text = Path.read_text

    def recording_read_text(self: Path, *args: Any, **kwargs: Any) -> str:
        opened.append(self)
        return read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", recording_read_text)
    report = deduplicate(corpus, canonical, target, apply=True)
    monkeypatch.undo()

    assert set(_scope_files(corpus, "added")) <= set(opened)
    assert set(opened).isdisjoint(base_files)
    assert _digests(base_files) == before
    assert _provision_paths(corpus, "base") == [
        "us-example/statute/1",
        "us-example/statute/2",
        "us-example/statute/3",
    ]
    assert _provision_paths(corpus, "added") == ["us-example/statute/4"]
    assert report["collision_count"] == 1
    assert report["untouched_base_scopes"] == [_base_mapping("base")]


def test_deduplicate_lets_an_added_primary_shadow_a_canonical_base(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    canonical = tmp_path / "canonical.json"
    target = tmp_path / "target.json"
    _write_scope(corpus, "canonical", ["us-example/statute/5"])
    _write_scope(corpus, "base", ["us-example/statute/1", "us-example/statute/2"])
    _write_scope(corpus, "added", ["us-example/statute/1", "us-example/statute/3"])
    _write_selector(canonical, ["canonical", "base"], bases=("base",))
    _write_selector(target, ["canonical", "base", "added"], bases=("base",))
    before = _digests(_scope_files(corpus, "base") + _scope_files(corpus, "added"))

    report = deduplicate(corpus, canonical, target, apply=True)

    assert report["collision_count"] == 0
    assert report["scopes"] == []
    assert report["untouched_base_scopes"] == [_base_mapping("base")]
    assert _provision_paths(corpus, "added") == ["us-example/statute/1", "us-example/statute/3"]
    assert _digests(_scope_files(corpus, "base") + _scope_files(corpus, "added")) == before


def test_deduplicate_resolves_a_primary_collision_over_a_canonical_base(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    canonical = tmp_path / "canonical.json"
    target = tmp_path / "target.json"
    _write_scope(corpus, "canonical", ["us-example/statute/1"])
    _write_scope(corpus, "base", ["us-example/statute/1", "us-example/statute/2"])
    _write_scope(corpus, "added", ["us-example/statute/1", "us-example/statute/3"])
    _write_selector(canonical, ["canonical", "base"], bases=("base",))
    _write_selector(target, ["canonical", "base", "added"], bases=("base",))
    base_files = _scope_files(corpus, "base")
    before = _digests(base_files)

    report = deduplicate(corpus, canonical, target, apply=True)

    assert report["collision_count"] == 1
    assert report["inherited_collision_count"] == 0
    assert [(scope["version"], scope["removed_paths"]) for scope in report["scopes"]] == [
        ("added", ["us-example/statute/1"])
    ]
    assert _provision_paths(corpus, "added") == ["us-example/statute/3"]
    assert _provision_paths(corpus, "canonical") == ["us-example/statute/1"]
    assert _digests(base_files) == before
    assert report["untouched_base_scopes"] == [_base_mapping("base")]


@pytest.mark.parametrize(
    ("canonical_bases", "target_bases", "omitted"),
    [
        (("base",), (), "us-example/statute/base (base)"),
        ((), ("canonical",), "us-example/statute/canonical"),
    ],
    ids=["canonical-base-carried-as-primary", "canonical-primary-carried-as-base"],
)
def test_deduplicate_refuses_a_canonical_scope_carried_in_the_other_layer(
    tmp_path: Path,
    canonical_bases: tuple[str, ...],
    target_bases: tuple[str, ...],
    omitted: str,
) -> None:
    corpus = tmp_path / "corpus"
    canonical = tmp_path / "canonical.json"
    target = tmp_path / "target.json"
    _write_scope(corpus, "canonical", ["us-example/statute/1"])
    _write_scope(corpus, "base", ["us-example/statute/1", "us-example/statute/2"])
    _write_scope(corpus, "added", ["us-example/statute/3"])
    _write_selector(canonical, ["canonical", "base"], bases=canonical_bases)
    _write_selector(target, ["canonical", "base", "added"], bases=target_bases)

    with pytest.raises(ValueError) as excinfo:
        deduplicate(corpus, canonical, target, apply=False)

    assert str(excinfo.value) == f"target selector omits canonical scopes: {omitted}"


def test_deduplicate_refuses_a_scope_selected_in_both_layers(tmp_path: Path) -> None:
    canonical = tmp_path / "canonical.json"
    target = tmp_path / "target.json"
    _write_selector(canonical, ["canonical"])
    _write_json(
        target,
        {
            "scopes": [
                {"document_class": "statute", "jurisdiction": "us-example", "version": "canonical"},
                {
                    "document_class": "statute",
                    "jurisdiction": "us-example",
                    "layer": "base",
                    "version": "canonical",
                },
            ]
        },
    )

    with pytest.raises(ValueError, match="selector contains duplicate scopes"):
        deduplicate(tmp_path / "corpus", canonical, target, apply=False)
