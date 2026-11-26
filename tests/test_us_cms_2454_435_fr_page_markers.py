"""The page-marker successor of the CMS-2454 42 CFR 435.550-435.563 scope."""

from __future__ import annotations

import difflib
import hashlib
import json
import re
import shutil
from functools import cache
from pathlib import Path

import pytest

from axiom_corpus.corpus.federal_register import (
    FEDERAL_REGISTER_PAGE_MARKER,
    _federal_register_cfr_section_body,
    check_federal_register_cfr_paragraphs,
    comparison_text,
    normalize_federal_register_cfr_section_body,
)
from axiom_corpus.corpus.io import load_provisions, load_source_inventory
from axiom_corpus.corpus.models import ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.release_quality import validate_release
from axiom_corpus.corpus.releases import ReleaseManifest, ReleaseScope
from axiom_corpus.corpus.supabase import deterministic_provision_id
from scripts.repro.us_cms_2454_435_fr_page_markers import (
    CORRECTION_LEAF,
    ECFR_DATE,
    ECFR_URL,
    RETAINED_SOURCES,
    SECTIONS,
    SOURCE_VERSION,
    VERIFICATION_LEAVES,
    VERSION,
    build_scope,
    citation_path,
    ecfr_leaf,
    ecfr_paragraphs,
    ecfr_provenance_leaf,
    non_space_text,
)

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data/corpus"
SCOPE = ("us", "regulation")
OLD_SOURCES = CORPUS / "sources/us/regulation" / SOURCE_VERSION
NEW_SOURCES = CORPUS / "sources/us/regulation" / VERSION
LINEAGE_KEYS = ("successor_of_version", "successor_of_source_path", "verification_source_paths")
CHANGED_FIELDS = {"version", "id", "body", "source_path", "metadata"}
# "[[Page N]]" markers in the base rows: nine in eight rows.
PAGE_MARKERS = {
    "552": ["[[Page 33471]]"],
    "554": ["[[Page 33472]]"],
    "555": ["[[Page 33473]]"],
    "556": ["[[Page 33474]]"],
    "557": ["[[Page 39029]]", "[[Page 39030]]"],
    "558": ["[[Page 39031]]"],
    "561": ["[[Page 33479]]"],
    "563": ["[[Page 33480]]"],
}
# Markers that split a sentence; each becomes one space. The others (554 and
# 555, before a paragraph; 563, at the end) leave no space behind.
MID_SENTENCE_MARKERS = {"552": 1, "556": 1, "557": 2, "558": 1, "561": 1}
# Lines that wrap inside a hyphenated word, which the successor rejoins.
HYPHEN_WRAPS = {
    "555": ["short-term"],
    "557": ["short-term", "unemployment-based"],
    "558": ["short-term"],
}
# Column-0 continuation lines of the base that start with "(", which a
# line-initial label reader takes for paragraph starts.
CROSS_REFERENCE_WRAPS = {
    "552": ["(d)(1)(i) of this section by 4.33 weeks", "(4) of this section for a total"],
    "554": ["(c)(1)(i)(A) through (C) of this section."],
    "556": ["(b) of this subchapter"],
    "558": ["(c)(1)(i) or (ii) of this section", "(PTC) used", "(a)(2) of this section ends"],
    "561": ["(a) of this section must be provided", "(PTC) used"],
}


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _artifact(kind: str, version: str = VERSION, base: Path = CORPUS) -> Path:
    suffix = "jsonl" if kind == "provisions" else "json"
    return base / kind / "us/regulation" / f"{version}.{suffix}"


def _number(record: ProvisionRecord | SourceInventoryItem) -> str:
    return record.citation_path.rsplit("/", 1)[1]


@cache
def _base_records() -> tuple[ProvisionRecord, ...]:
    return tuple(load_provisions(_artifact("provisions", SOURCE_VERSION)))


@cache
def _records() -> tuple[ProvisionRecord, ...]:
    return tuple(load_provisions(_artifact("provisions")))


@cache
def _pairs() -> tuple[tuple[ProvisionRecord, ProvisionRecord], ...]:
    return tuple(zip(_base_records(), _records(), strict=True))


def _files(root: Path) -> list[Path]:
    return sorted(path.relative_to(root) for path in root.rglob("*") if path.is_file())


def test_build_reproduces_the_scope_byte_for_byte(tmp_path: Path) -> None:
    first = build_scope(base=tmp_path / "first", source_base=CORPUS)
    second = build_scope(base=tmp_path / "second", source_base=CORPUS)
    for kind in ("inventory", "provisions", "coverage"):
        built = _artifact(kind, base=tmp_path / "first")
        assert _digest(built) == _digest(_artifact(kind, base=tmp_path / "second")), kind
        assert built.read_bytes() == _artifact(kind).read_bytes(), kind
    assert first.section_count == second.section_count == 14
    assert _files(first.source_root) == _files(NEW_SOURCES)
    assert sorted(str(leaf) for leaf in _files(NEW_SOURCES)) == sorted(
        [*RETAINED_SOURCES, *VERIFICATION_LEAVES]
    )
    for leaf in _files(NEW_SOURCES):
        assert (first.source_root / leaf).read_bytes() == (NEW_SOURCES / leaf).read_bytes(), leaf


def test_successor_keeps_the_base_citation_set() -> None:
    expected = [citation_path(section) for section in SECTIONS]
    assert [record.citation_path for record in _base_records()] == expected
    assert [record.citation_path for record in _records()] == expected
    assert len(set(expected)) == 14


def test_rows_change_only_body_version_id_source_path_and_lineage() -> None:
    for base, row in _pairs():
        base_fields, fields = base.to_mapping(), row.to_mapping()
        assert {
            key
            for key in base_fields.keys() | fields.keys()
            if base_fields.get(key) != fields.get(key)
        } <= CHANGED_FIELDS
        assert row.version == VERSION
        assert row.id == deterministic_provision_id(row.citation_path, VERSION)
        assert row.parent_citation_path is None and row.parent_id is None
        assert (base.source_as_of, base.expression_date) == (row.source_as_of, row.expression_date)
        assert row.source_path == base.source_path.replace(SOURCE_VERSION, VERSION, 1)
        metadata = dict(row.metadata or {})
        lineage = {key: metadata.pop(key) for key in LINEAGE_KEYS}
        assert metadata == base.metadata
        assert lineage == {
            "successor_of_version": SOURCE_VERSION,
            "successor_of_source_path": base.source_path,
            "verification_source_paths": [
                f"sources/us/regulation/{VERSION}/{ecfr_leaf('435.' + _number(row))}"
            ],
        }


def test_inventory_keeps_each_items_source_bytes() -> None:
    base_items = load_source_inventory(_artifact("inventory", SOURCE_VERSION))
    items = load_source_inventory(_artifact("inventory"))
    assert [item.citation_path for item in items] == [item.citation_path for item in base_items]
    for base, item in zip(base_items, items, strict=True):
        assert item.sha256 == base.sha256
        assert item.source_format == base.source_format == "federal-register-raw-text-slice"
        assert item.source_url == base.source_url
        assert item.source_path == base.source_path.replace(SOURCE_VERSION, VERSION, 1)
        assert _digest(CORPUS / item.source_path) == item.sha256
        metadata = dict(item.metadata or {})
        for key in LINEAGE_KEYS:
            metadata.pop(key)
        assert metadata == base.metadata


def test_retained_sources_are_copied_unchanged() -> None:
    for leaf, sha256 in RETAINED_SOURCES.items():
        assert _digest(NEW_SOURCES / leaf) == _digest(OLD_SOURCES / leaf) == sha256


def test_corrected_rows_are_slices_of_the_retained_correction() -> None:
    correction = (NEW_SOURCES / CORRECTION_LEAF).read_text("utf-8")
    for base, row in _pairs():
        if _number(row) in ("557", "558"):
            assert base.source_document_id == row.source_document_id == "C1-2026-11094"
            assert (
                _federal_register_cfr_section_body(correction, "435." + _number(row)) == base.body
            )


def test_every_page_marker_is_dropped() -> None:
    found = {
        _number(base): FEDERAL_REGISTER_PAGE_MARKER.findall(base.body or "")
        for base in _base_records()
        if FEDERAL_REGISTER_PAGE_MARKER.search(base.body or "")
    }
    assert found == PAGE_MARKERS
    assert sum(map(len, found.values())) == 9
    for row in _records():
        assert "[[Page" not in (row.body or "")


def test_only_line_breaks_move() -> None:
    for base, row in _pairs():
        number, before, after = _number(row), base.body or "", row.body or ""
        # Every non-space character is kept, less the page markers.
        assert non_space_text(after) == non_space_text(FEDERAL_REGISTER_PAGE_MARKER.sub("", before))
        # Without line breaks, the texts differ only by the spaces that replace
        # mid-sentence page markers.
        flat_before = re.sub(r"\n\n\[\[Page \d+\]\](?:\n\n)?", "", before).replace("\n", "")
        flat_after = after.replace("\n", "")
        opcodes = [
            (tag, flat_before[i1:i2], flat_after[j1:j2])
            for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(
                None, flat_before, flat_after, autojunk=False
            ).get_opcodes()
            if tag != "equal"
        ]
        assert opcodes == [("insert", "", " ")] * MID_SENTENCE_MARKERS.get(number, 0), number
        # The words are the base's, less the markers, with hyphen wraps rejoined.
        # A marker is two whitespace-separated tokens ("[[Page", "39031]]").
        words = FEDERAL_REGISTER_PAGE_MARKER.sub(" ", before).split()
        assert len(before.split()) - len(words) == 2 * len(PAGE_MARKERS.get(number, []))
        rejoined: list[str] = []
        merges: list[str] = []
        for word in words:
            hyphen = bool(rejoined) and re.search(r"[^-]-\Z", rejoined[-1]) is not None
            if hyphen and f"{rejoined[-1]}\n{word}" in before:
                rejoined[-1] += word
                merges.append(rejoined[-1])
            else:
                rejoined.append(word)
        assert merges == HYPHEN_WRAPS.get(number, []), number
        assert after.split() == rejoined, number


def test_each_line_is_the_heading_or_one_paragraph() -> None:
    for base, row in _pairs():
        lines = (row.body or "").split("\n")
        assert lines[0].startswith(f"Sec.  435.{_number(row)} ")
        assert lines[1] == ""
        for line in lines[2:]:
            assert re.fullmatch(r"    \S.*\S", line), line[:60]
        assert not [line for line in lines if line.startswith("(")]
        base_lines = (base.body or "").split("\n")
        wrapped = [line for line in base_lines if line.startswith("(")]
        assert len(wrapped) == len(CROSS_REFERENCE_WRAPS.get(_number(row), []))
        for start in CROSS_REFERENCE_WRAPS.get(_number(row), []):
            assert any(line.startswith(start) for line in wrapped), start
            assert not any(line.lstrip().startswith(start) for line in lines), start


@pytest.mark.parametrize("section", SECTIONS)
def test_body_reads_as_the_ecfr_section_paragraph_for_line(section: str) -> None:
    row = next(record for record in _records() if record.citation_path == citation_path(section))
    content = (NEW_SOURCES / ecfr_leaf(section)).read_bytes()
    paragraphs = ecfr_paragraphs(content, section)
    check_federal_register_cfr_paragraphs(row.body or "", paragraphs)
    assert comparison_text(row.body or "") == comparison_text("\n".join(paragraphs))
    base = next(record for record in _base_records() if record.citation_path == row.citation_path)
    # The base already has the eCFR words (the d2932 comparison: markers out,
    # hyphen wraps joined); only its lines differ.
    unwrapped = FEDERAL_REGISTER_PAGE_MARKER.sub("", base.body or "").replace("-\n", "-")
    assert comparison_text(unwrapped) == comparison_text(row.body or "")
    with pytest.raises(ValueError, match="body differs from eCFR"):
        check_federal_register_cfr_paragraphs(base.body or "", paragraphs)


def test_ecfr_check_catches_a_changed_word() -> None:
    row = next(record for record in _records() if record.citation_path.endswith("/558"))
    content = (NEW_SOURCES / ecfr_leaf("435.558")).read_bytes()
    changed = content.replace(b"provided by the individual", b"provided by the applicant", 1)
    assert changed != content
    with pytest.raises(ValueError, match="body differs from eCFR"):
        normalize_federal_register_cfr_section_body(
            row.body or "", ecfr_paragraphs(changed, "435.558")
        )


def test_verification_sources_are_the_ecfr_sections_with_provenance() -> None:
    for section in SECTIONS:
        content = (NEW_SOURCES / ecfr_leaf(section)).read_bytes()
        provenance = json.loads((NEW_SOURCES / ecfr_provenance_leaf(section)).read_text("utf-8"))
        assert provenance["sha256"] == hashlib.sha256(content).hexdigest()
        assert provenance["url"] == ECFR_URL.format(date=ECFR_DATE, section=section)
        assert (provenance["http"], provenance["fetch_method"]) == (200, "http-get")
        assert ecfr_paragraphs(content, section)[0].startswith(f"§ {section} ")


def test_build_refuses_a_changed_base_row(tmp_path: Path) -> None:
    source_base = tmp_path / "source"
    for kind in ("inventory", "provisions"):
        target = _artifact(kind, SOURCE_VERSION, base=source_base)
        target.parent.mkdir(parents=True)
        shutil.copyfile(_artifact(kind, SOURCE_VERSION), target)
    provisions = _artifact("provisions", SOURCE_VERSION, base=source_base)
    provisions.write_text(
        provisions.read_text("utf-8").replace("provided by", "provided  by", 1), "utf-8"
    )
    with pytest.raises(ValueError, match="not the locked base artifact"):
        build_scope(base=tmp_path / "out", source_base=source_base)


def test_successor_validates_alone() -> None:
    release = ReleaseManifest(
        name="cms-435-fr-page-markers-alone",
        quality_profile="complete-expression-dates-v1",
        scopes=(ReleaseScope(*SCOPE, VERSION),),
    )
    report = validate_release(CORPUS, release, strict_warnings=True).to_mapping()
    assert (report["ok"], report["issue_count"]) == (True, 0), report["issues"][:3]


def test_selecting_the_base_with_its_successor_is_rejected() -> None:
    release = ReleaseManifest(
        name="cms-435-fr-page-markers-both",
        quality_profile="complete-expression-dates-v1",
        scopes=(ReleaseScope(*SCOPE, SOURCE_VERSION), ReleaseScope(*SCOPE, VERSION)),
    )
    report = validate_release(CORPUS, release, strict_warnings=True).to_mapping()
    assert not report["ok"]
    assert {issue["code"] for issue in report["issues"]} == {"duplicate_release_citation"}
    assert report["issue_count"] == 14


def test_build_fetches_the_locked_inputs_it_reads_and_not_its_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from axiom_corpus.corpus import resolver as corpus_resolver
    from axiom_corpus.corpus.content_store import ContentCache, content_key
    from axiom_corpus.corpus.corpus_locks import scope_for_path, write_lock
    from axiom_corpus.corpus.resolver import CorpusResolver
    from scripts.repro import us_cms_2454_435_fr_page_markers as repro
    from tests.test_corpus_storage import _init_repo, _remote, _scope_lock

    base, successor = f"us/regulation/{SOURCE_VERSION}", f"us/regulation/{VERSION}"
    # The build reads the base scope's sources, inventory and provisions, and the
    # eCFR checks kept under the successor's source directory. The resolver
    # places a scope's source directory whole, so the successor's copies of the
    # retained sources (which the build rewrites with the same bytes) come too.
    inputs = {
        **{f"data/corpus/sources/{base}/{leaf}": leaf.encode() for leaf in RETAINED_SOURCES},
        f"data/corpus/inventory/{base}.json": b'{"items": []}\n',
        f"data/corpus/provisions/{base}.jsonl": b'{"citation_path": "a"}\n',
        **{
            f"data/corpus/sources/{successor}/{leaf}": leaf.encode() for leaf in VERIFICATION_LEAVES
        },
        **{
            f"data/corpus/sources/{successor}/{leaf}": b"copy " + leaf.encode()
            for leaf in RETAINED_SOURCES
        },
    }
    # It never reads the base coverage or the successor's inventory, provisions
    # and coverage, which it writes.
    others = {
        f"data/corpus/coverage/{base}.json": b'{"complete": true}\n',
        f"data/corpus/inventory/{successor}.json": b'{"items": [1]}\n',
        f"data/corpus/provisions/{successor}.jsonl": b'{"citation_path": "b"}\n',
        f"data/corpus/coverage/{successor}.json": b'{"complete": false}\n',
    }
    files = {**inputs, **others}
    repo = _init_repo(tmp_path / "repo")
    remote, _fake = _remote({content_key(hashlib.sha256(d).hexdigest()): d for d in files.values()})
    monkeypatch.delenv("AXIOM_CORPUS_NO_FETCH", raising=False)
    for scope in {scope_for_path(path) for path in files}:
        write_lock(
            repo, _scope_lock({p: d for p, d in files.items() if scope_for_path(p) == scope}, scope)
        )
    resolver = CorpusResolver(repo, cache=ContentCache(tmp_path / "cache"), sources=[remote])
    monkeypatch.setitem(corpus_resolver._RESOLVERS, repo.resolve(), resolver)

    repro.ensure_corpus_inputs(repo=repo, source_base=repo / "data" / "corpus")
    root = repo / "data" / "corpus"
    present = {p.relative_to(repo).as_posix() for p in root.rglob("*") if p.is_file()}
    assert present == set(inputs)
    assert all((repo / path).read_bytes() == data for path, data in inputs.items())
