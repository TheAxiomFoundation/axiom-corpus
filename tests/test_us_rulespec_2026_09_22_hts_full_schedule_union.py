from __future__ import annotations

import json
import os
import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

from axiom_corpus.corpus.release_quality import validate_release
from axiom_corpus.corpus.releases import ReleaseManifest, ReleaseScope
from scripts.repro.us_rulespec_2026_09_22_hts_full_schedule_union import (
    BASE_RELEASE,
    DOCUMENT_CLASS,
    FULL_SCHEDULE_VERSION,
    JURISDICTION,
    LEGACY_CITATIONS,
    LEGACY_SOURCE_VERSION,
    LEGACY_VERSION,
    RELEASE,
    REPLACED_VERSION,
    WITNESS_CITATIONS,
    build_release,
    build_scope,
    verify_scope,
)

ROOT = Path(__file__).resolve().parents[1]
RELEASE_DIR = ROOT / "manifests/releases"
CORPUS = ROOT / "data/corpus"
HTS_ROOT = "us/statute/hts"
NOTES_VERSION = "2026-08-04-usitc-hts-2026-rev15-notes"
PREFIX = Path(JURISDICTION) / DOCUMENT_CLASS


def _keys(selector: Path) -> set[tuple[str, str, str]]:
    payload = json.loads(selector.read_text(encoding="utf-8"))
    return {
        (scope["jurisdiction"], scope["document_class"], scope["version"])
        for scope in payload["scopes"]
    }


def _provisions(base: Path, version: str) -> Path:
    return base / "provisions" / PREFIX / f"{version}.jsonl"


def _inventory(base: Path, version: str) -> Path:
    return base / "inventory" / PREFIX / f"{version}.json"


def _coverage(base: Path, version: str) -> Path:
    return base / "coverage" / PREFIX / f"{version}.json"


def _sources(base: Path, version: str) -> Path:
    return base / "sources" / PREFIX / version


def _copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, target)
    else:
        shutil.copyfile(source, target)


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _write_rows(path: Path, rows: list[dict]) -> None:
    path.unlink()
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def test_reproducer_matches_committed_selector(tmp_path: Path) -> None:
    generated = build_release(release_dir=RELEASE_DIR, output_dir=tmp_path)
    assert generated.read_bytes() == (RELEASE_DIR / f"{RELEASE}.json").read_bytes()


def test_selector_swaps_only_the_hts_scopes() -> None:
    base = _keys(RELEASE_DIR / f"{BASE_RELEASE}.json")
    release = _keys(RELEASE_DIR / f"{RELEASE}.json")

    assert base - release == {(JURISDICTION, DOCUMENT_CLASS, REPLACED_VERSION)}
    assert release - base == {
        (JURISDICTION, DOCUMENT_CLASS, FULL_SCHEDULE_VERSION),
        (JURISDICTION, DOCUMENT_CLASS, LEGACY_VERSION),
    }


def test_committed_legacy_scope_passes_reproducer_gates() -> None:
    assert verify_scope(CORPUS) == {
        "full_schedule": 29846,
        "legacy": 3,
        "replaced": 1714,
        "shared_with_replaced": 1711,
    }


def test_hts_citations_have_one_carrier_in_release() -> None:
    carriers: dict[str, str] = {}
    for jurisdiction, document_class, version in sorted(_keys(RELEASE_DIR / f"{RELEASE}.json")):
        if (jurisdiction, document_class) != (JURISDICTION, DOCUMENT_CLASS):
            continue
        provisions = CORPUS / "provisions" / jurisdiction / document_class / f"{version}.jsonl"
        for line in provisions.read_text(encoding="utf-8").splitlines():
            citation_path = json.loads(line)["citation_path"]
            if citation_path != HTS_ROOT and not citation_path.startswith(HTS_ROOT + "/"):
                continue
            assert citation_path not in carriers, (citation_path, carriers.get(citation_path))
            carriers[citation_path] = version

    assert set(carriers.values()) == {FULL_SCHEDULE_VERSION, LEGACY_VERSION, NOTES_VERSION}
    assert carriers[HTS_ROOT] == FULL_SCHEDULE_VERSION


def test_hts_scopes_validate_strictly_as_a_release() -> None:
    release = ReleaseManifest(
        name="hts-full-schedule-union-hts-scopes",
        scopes=tuple(
            ReleaseScope(JURISDICTION, DOCUMENT_CLASS, version)
            for version in (FULL_SCHEDULE_VERSION, LEGACY_VERSION, NOTES_VERSION)
        ),
        quality_profile="complete-expression-dates-v1",
    )

    report = validate_release(CORPUS, release, strict_warnings=True)

    assert report.ok, [issue.to_mapping() for issue in report.issues]
    assert (report.error_count, report.warning_count) == (0, 0)


def test_legacy_scope_rebuilds_byte_for_byte(tmp_path: Path) -> None:
    base = tmp_path / "corpus"
    for source in (
        _provisions(CORPUS, LEGACY_SOURCE_VERSION),
        _inventory(CORPUS, LEGACY_SOURCE_VERSION),
        _sources(CORPUS, LEGACY_SOURCE_VERSION),
    ):
        _copy(source, base / source.relative_to(CORPUS))
    # verify_scope only reads the full-schedule and replaced provisions.
    for version in (FULL_SCHEDULE_VERSION, REPLACED_VERSION):
        target = _provisions(base, version)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to(_provisions(CORPUS, version))

    build_scope(base)

    for committed, rebuilt in (
        (_coverage(CORPUS, LEGACY_VERSION), _coverage(base, LEGACY_VERSION)),
        (_inventory(CORPUS, LEGACY_VERSION), _inventory(base, LEGACY_VERSION)),
        (_provisions(CORPUS, LEGACY_VERSION), _provisions(base, LEGACY_VERSION)),
    ):
        assert committed.read_bytes() == rebuilt.read_bytes()
    committed_sources = _sources(CORPUS, LEGACY_VERSION)
    rebuilt_sources = _sources(base, LEGACY_VERSION)
    committed_files = sorted(p.relative_to(committed_sources) for p in committed_sources.rglob("*"))
    assert committed_files == sorted(
        p.relative_to(rebuilt_sources) for p in rebuilt_sources.rglob("*")
    )
    for relative in committed_files:
        if (committed_sources / relative).is_file():
            assert (committed_sources / relative).read_bytes() == (
                rebuilt_sources / relative
            ).read_bytes()


@pytest.fixture(scope="module")
def pristine(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A small corpus base that verify_scope accepts, built once per module.

    The full schedule is trimmed to the paths the replaced scope carries, which is
    all verify_scope reads from it.
    """
    base = tmp_path_factory.mktemp("pristine") / "corpus"
    for source in (
        _provisions(CORPUS, LEGACY_SOURCE_VERSION),
        _inventory(CORPUS, LEGACY_SOURCE_VERSION),
        _sources(CORPUS, LEGACY_SOURCE_VERSION),
        _provisions(CORPUS, REPLACED_VERSION),
        _provisions(CORPUS, LEGACY_VERSION),
        _inventory(CORPUS, LEGACY_VERSION),
        _coverage(CORPUS, LEGACY_VERSION),
        _sources(CORPUS, LEGACY_VERSION),
    ):
        _copy(source, base / source.relative_to(CORPUS))
    replaced = {row["citation_path"] for row in _rows(_provisions(CORPUS, REPLACED_VERSION))}
    trimmed = [
        row
        for row in _rows(_provisions(CORPUS, FULL_SCHEDULE_VERSION))
        if row["citation_path"] in replaced
    ]
    target = _provisions(base, FULL_SCHEDULE_VERSION)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in trimmed))
    return base


@pytest.fixture
def corpus_copy(pristine: Path, tmp_path: Path) -> Path:
    """Hard-link the pristine base; each mutation replaces a file rather than editing it."""
    base = tmp_path / "corpus"
    shutil.copytree(pristine, base, copy_function=os.link)
    return base


def test_verify_scope_accepts_the_pristine_copy(corpus_copy: Path) -> None:
    assert verify_scope(corpus_copy) == {
        "full_schedule": 1711,
        "legacy": 3,
        "replaced": 1714,
        "shared_with_replaced": 1711,
    }


def _edit_legacy(edit: Callable[[list[dict]], None]) -> Callable[[Path], None]:
    def mutate(base: Path) -> None:
        rows = _rows(_provisions(base, LEGACY_VERSION))
        edit(rows)
        _write_rows(_provisions(base, LEGACY_VERSION), rows)

    return mutate


def _edit_full_schedule(edit: Callable[[list[dict]], list[dict]]) -> Callable[[Path], None]:
    def mutate(base: Path) -> None:
        path = _provisions(base, FULL_SCHEDULE_VERSION)
        _write_rows(path, edit(_rows(path)))

    return mutate


def _shared_line(rows: list[dict]) -> dict:
    """A shared full-schedule line that is not a Revision 14 witness line."""
    return next(
        row
        for row in rows
        if row["citation_path"] != HTS_ROOT and row["citation_path"] not in WITNESS_CITATIONS
    )


def _set(row: dict, **fields: object) -> list[dict]:
    row.update(fields)
    return []


def _noncanonical_legacy(base: Path) -> None:
    path = _provisions(base, LEGACY_VERSION)
    text = path.read_text(encoding="utf-8")
    path.unlink()
    path.write_text(text.replace("\n", "\n\n", 1))


def _inventory_digest(base: Path) -> None:
    path = _inventory(base, LEGACY_VERSION)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["items"][0]["sha256"] = "0" * 64
    path.unlink()
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _retained_file(base: Path) -> Path:
    return next(p for p in _sources(base, LEGACY_VERSION).rglob("*") if p.is_file())


def _retained_source_byte(base: Path) -> None:
    path = _retained_file(base)
    data = path.read_bytes()
    path.unlink()
    path.write_bytes(data + b" ")


def _retained_source_symlink(base: Path) -> None:
    path = _retained_file(base)
    relative = path.relative_to(_sources(base, LEGACY_VERSION) / LEGACY_SOURCE_VERSION)
    path.unlink()
    path.symlink_to(_sources(base, LEGACY_SOURCE_VERSION) / relative)


def _stale_coverage(base: Path) -> None:
    path = _coverage(base, LEGACY_VERSION)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["matched_count"] = 2
    path.unlink()
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _full_schedule_carries_legacy(rows: list[dict]) -> list[dict]:
    legacy = next(
        row
        for row in _rows(_provisions(CORPUS, LEGACY_SOURCE_VERSION))
        if row["citation_path"] == LEGACY_CITATIONS[0]
    )
    return [*rows, legacy]


MUTATIONS: dict[str, Callable[[Path], None]] = {
    "legacy body": _edit_legacy(lambda rows: rows[0].update(body=rows[0]["body"] + " ")),
    "legacy parent restored": _edit_legacy(
        lambda rows: rows[1].update(parent_citation_path=HTS_ROOT)
    ),
    "legacy id": _edit_legacy(
        lambda rows: rows[2].update(id="0" * 8 + "-0000-0000-0000-" + "0" * 12)
    ),
    "legacy detach metadata": _edit_legacy(
        lambda rows: rows[0]["metadata"].pop("detached_parent_citation_path")
    ),
    "legacy serialization": _noncanonical_legacy,
    "inventory digest": _inventory_digest,
    "retained source byte": _retained_source_byte,
    "retained source symlink": _retained_source_symlink,
    "stale coverage": _stale_coverage,
    "full schedule drops a shared line": _edit_full_schedule(
        lambda rows: [row for row in rows if row is not _shared_line(rows)]
    ),
    "full schedule body": _edit_full_schedule(
        lambda rows: [*rows, *_set(_shared_line(rows), body="changed")]
    ),
    "full schedule kind": _edit_full_schedule(
        lambda rows: [*rows, *_set(_shared_line(rows), kind="changed")]
    ),
    "full schedule date outside the witness lines": _edit_full_schedule(
        lambda rows: [*rows, *_set(_shared_line(rows), expression_date="1999-01-01")]
    ),
    "full schedule carries a legacy line": _edit_full_schedule(_full_schedule_carries_legacy),
}


@pytest.mark.parametrize("mutation", sorted(MUTATIONS))
def test_verify_scope_rejects_corruption(corpus_copy: Path, mutation: str) -> None:
    MUTATIONS[mutation](corpus_copy)

    with pytest.raises(ValueError):
        verify_scope(corpus_copy)
