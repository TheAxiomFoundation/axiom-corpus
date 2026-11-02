"""Synthetic locked-scope checks for the assembled eCFR section-text successors."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import pytest
from hypothesis import HealthCheck, example, given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus import ecfr
from axiom_corpus.corpus.corpus_locks import CorpusLock, LockEntry, serialize_lock
from axiom_corpus.corpus.supabase import deterministic_provision_id
from scripts.repro import ecfr_section_text_successors as repro

OLD = "2026-07-01-synthetic"
NEW = f"{OLD}-r2026-10-29-ecfr-section-text"
PREFIX = f"sources/us/regulation/{OLD}/"
SOURCE = f"{PREFIX}official-documents/part.xml"
SIDE_SOURCE = f"{PREFIX}provenance/capture.bin"
DEFAULT_KINDS = ("changed", "stable", "drift", "placeholder", "document", "paragraph")


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _legacy_body(element: ET.Element) -> str:
    """Give a synthetic section its explicitly recorded pre-fix body."""
    return element.get("BASELINE", ecfr._section_body(element))


@dataclass
class LockedFixture:
    base: Path
    lock_dir: Path
    key: str
    records: list[dict[str, Any]]
    inventory: dict[str, Any]
    source_payloads: dict[str, bytes]

    def artifact(self, kind: str, version: str = OLD) -> Path:
        suffix = ".jsonl" if kind == "provisions" else ".json"
        return self.base / kind / "us/regulation" / f"{version}{suffix}"

    def save(self) -> None:
        """Update only the fixture's explicitly named files and their lock."""
        payloads = {
            **self.source_payloads,
            f"provisions/us/regulation/{OLD}.jsonl": "".join(
                json.dumps(row, sort_keys=True) + "\n" for row in self.records
            ).encode(),
            f"inventory/us/regulation/{OLD}.json": json.dumps(self.inventory).encode(),
            f"coverage/us/regulation/{OLD}.json": json.dumps(
                {"complete": True, "version": OLD, "provision_count": len(self.records)}
            ).encode(),
        }
        entries: list[LockEntry] = []
        for relative, payload in sorted(payloads.items()):
            path = self.base / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
            entries.append(LockEntry(f"data/corpus/{relative}", _sha(payload), len(payload)))
        lock = self.lock_dir / "us/regulation" / f"{OLD}.json"
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_bytes(serialize_lock(CorpusLock.from_entries(("us", "regulation", OLD), entries)))

    def run(self) -> dict[str, Any]:
        return repro.reconstruct(
            self.key,
            base=self.base,
            lock_dir=self.lock_dir,
            report_path=self.base.parent / "report.json",
        )

    def successor_rows(self) -> list[dict[str, Any]]:
        with self.artifact("provisions", NEW).open() as stream:
            return [json.loads(line) for line in stream if line.strip()]

    def assert_no_successor(self) -> None:
        assert not any(self.artifact(kind, NEW).exists() for kind in ("provisions", "inventory", "coverage"))
        assert not (self.base / f"sources/us/regulation/{NEW}").exists()


def _fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    key: str = "recovery",
    kinds: tuple[str, ...] = DEFAULT_KINDS,
    extras: list[dict[str, Any]] | None = None,
    version_ids: list[bool] | None = None,
) -> LockedFixture:
    root = ET.Element("ROOT")
    records: list[dict[str, Any]] = []
    delta: set[str] = set()
    inherited: set[str] = set()
    for index, kind in enumerate(kinds):
        citation = f"us/regulation/1/1/{index + 1}"
        body: str | None = "Retained official document text."
        heading = f"§ 1.{index + 1} Synthetic heading."
        metadata: dict[str, Any] = {
            "capture_version": OLD,
            "image": {"path": f"{PREFIX}images/{index}.png"},
            "references": [OLD, f"See {SOURCE} for the capture.", f"literal-{OLD}"],
            "extra": (extras or [{}] * len(kinds))[index],
        }
        if kind in {"changed", "stable", "drift"}:
            section = ET.SubElement(root, "DIV8", {"N": f"1.{index + 1}", "TYPE": "SECTION"})
            ET.SubElement(section, "HEAD").text = heading
            paragraph = ET.SubElement(section, "P")
            if kind == "changed":
                paragraph.text = "Before"
                ET.SubElement(paragraph, "br").tail = "after."
                section.set("BASELINE", "Beforeafter.")
                body = "Beforeafter."
                delta.add(citation)
            elif kind == "drift":
                section.insert(1, ET.Element("HED"))
                section[1].text = "Editorial Note:"
                paragraph.text = "Inherited text."
                body = "Inherited text."
                inherited.add(citation)
            else:
                paragraph.text = "Stable unchanged text."
                body = ecfr._section_body(section)
            heading = ecfr._section_heading(section, "1", str(index + 1))
        elif kind == "placeholder":
            metadata.update(structure_only=True, body_status="not_in_ecfr_full_xml")
            body = None
        elif kind == "paragraph":
            citation = f"us/regulation/1/1/unchanged/{index + 1}"
        record: dict[str, Any] = {
            "citation_path": citation,
            "heading": heading,
            "body": body,
            "kind": "paragraph" if kind == "paragraph" else "section",
            "source_format": "official-document" if kind in {"document", "paragraph"} else "ecfr-xml",
            "source_path": SOURCE,
            "source_as_of": "2026-07-01",
            "expression_date": "2026-07-01",
            "version": OLD,
            "metadata": metadata,
            "ordinal": index,
        }
        scoped = (version_ids or [bool(i % 2) for i in range(len(kinds))])[index]
        record["id"] = deterministic_provision_id(citation, OLD) if scoped else deterministic_provision_id(citation)
        stable_index = next((i for i, row_kind in enumerate(kinds) if row_kind == "stable"), None)
        parent = (
            f"us/regulation/1/1/{stable_index + 1}"
            if kind == "paragraph" and stable_index is not None
            else records[0]["citation_path"] if records and kind != "paragraph" else None
        )
        if parent:
            record["parent_citation_path"] = parent
            record["parent_id"] = deterministic_provision_id(parent, OLD) if scoped else deterministic_provision_id(parent)
        records.append(record)
    payload = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    inventory = {
        "version": OLD,
        "items": [
            {"citation_path": row["citation_path"], "source_path": SOURCE, "sha256": _sha(payload)}
            for row in records
        ],
    }
    fixture = LockedFixture(
        tmp_path / "data/corpus",
        tmp_path / "locks",
        key,
        records,
        inventory,
        {SOURCE: payload, SIDE_SOURCE: b"\x00unchanged capture metadata\xff\r\n"},
    )
    monkeypatch.setitem(repro.SCOPES, key, {"old": OLD, "new": NEW})
    monkeypatch.setitem(repro.EXPECTED, key, delta)
    monkeypatch.setattr(repro, "INHERITED_RECOVERY_DRIFT", inherited)
    monkeypatch.setattr(repro, "pre832_renderer", lambda: _legacy_body)
    fixture.save()
    return fixture


def test_delta_set_mismatch_refuses_before_writing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fixture = _fixture(tmp_path, monkeypatch)
    monkeypatch.setitem(repro.EXPECTED, "recovery", set())
    with pytest.raises(ValueError, match="unexpected #832 delta"):
        fixture.run()
    fixture.assert_no_successor()


def test_inherited_drift_set_mismatch_refuses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fixture = _fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(repro, "INHERITED_RECOVERY_DRIFT", set())
    with pytest.raises(ValueError, match="inherited recovery drift set changed"):
        fixture.run()
    fixture.assert_no_successor()


def test_inherited_drift_keeps_the_locked_body(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fixture = _fixture(tmp_path, monkeypatch)
    report = fixture.run()
    old, new = fixture.records[2], fixture.successor_rows()[2]
    assert new["body"] == old["body"] == "Inherited text."
    assert report["inherited_rendering_drift"] == [
        {
            "citation_path": old["citation_path"],
            "source_path": SOURCE,
            "locked_body_sha256": _sha(b"Inherited text."),
            "pre832_body_sha256": _sha(b"Editorial Note:\n\nInherited text."),
            "main_body_sha256": _sha(b"Editorial Note:\n\nInherited text."),
            "locked_chars": 15,
            "pre832_chars": 32,
            "main_chars": 32,
            "preserved": True,
            "pre832_equals_main": True,
        }
    ]


def test_only_delta_bodies_change_and_report_matches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fixture = _fixture(tmp_path, monkeypatch)
    report = fixture.run()
    rows = fixture.successor_rows()
    changed = {old["citation_path"] for old, new in zip(fixture.records, rows, strict=True) if old["body"] != new["body"]}
    assert changed == {"us/regulation/1/1/1"}
    assert rows[0]["body"] == "Before after."
    assert report["body_changed_paths"] == sorted(changed)
    assert report["row_count"] == len(rows)
    assert json.loads((fixture.base.parent / "report.json").read_text()) == report


def test_26_1_renders_all_sections_and_checks_changed_set(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fixture = _fixture(tmp_path, monkeypatch, key="26-1", kinds=("changed", "stable", "placeholder"))
    monkeypatch.setitem(repro.EXPECTED, "26-1", set())
    monkeypatch.setattr(repro, "pre832_renderer", lambda: pytest.fail("26-1 must use its own locked main-rendered snapshots"))
    with pytest.raises(ValueError, match="unexpected body changes"):
        fixture.run()
    fixture.assert_no_successor()


def test_version_scoped_ids_change_and_path_only_ids_stay(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fixture = _fixture(tmp_path, monkeypatch)
    fixture.run()
    for old, new in zip(fixture.records, fixture.successor_rows(), strict=True):
        for field, path in (("id", old["citation_path"]), ("parent_id", old.get("parent_citation_path"))):
            if not path:
                continue
            assert new[field] == (
                deterministic_provision_id(path, NEW)
                if old[field] == deterministic_provision_id(path, OLD)
                else old[field]
            )


@pytest.mark.parametrize("field", ("id", "parent_id"))
def test_unknown_id_scheme_refuses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str) -> None:
    fixture = _fixture(tmp_path, monkeypatch)
    fixture.records[1][field] = "unrecognized-id"
    fixture.save()
    with pytest.raises(ValueError, match=f"unknown {field} scheme"):
        fixture.run()
    fixture.assert_no_successor()


@pytest.mark.parametrize("kind", ("provisions", "inventory", "coverage", "sources"))
def test_existing_target_refuses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str) -> None:
    fixture = _fixture(tmp_path, monkeypatch)
    target = fixture.base / f"sources/us/regulation/{NEW}" if kind == "sources" else fixture.artifact(kind, NEW)
    target.parent.mkdir(parents=True, exist_ok=True)
    if kind == "sources":
        target.mkdir()
    else:
        target.write_bytes(b"existing target must survive")
    with pytest.raises(ValueError, match="successor output already exists"):
        fixture.run()
    if kind != "sources":
        assert target.read_bytes() == b"existing target must survive"


def test_sources_copy_byte_for_byte_including_non_xml_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fixture = _fixture(tmp_path, monkeypatch)
    fixture.run()
    for relative, payload in fixture.source_payloads.items():
        assert (fixture.base / relative).read_bytes() == payload
        copied = fixture.base / relative.replace(f"/{OLD}/", f"/{NEW}/")
        assert copied.read_bytes() == payload
        assert _sha(copied.read_bytes()) == _sha(payload)


def test_copied_sources_get_rehashed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fixture = _fixture(tmp_path, monkeypatch)
    copyfile = shutil.copyfile

    def corrupt_copy(source: Path, destination: Path, *args: Any, **kwargs: Any) -> Path:
        result = copyfile(source, destination, *args, **kwargs)
        if Path(source).name == "capture.bin":
            Path(destination).write_bytes(b"corrupt")
        return result

    monkeypatch.setattr(repro.shutil, "copyfile", corrupt_copy)
    with pytest.raises(ValueError, match="copied source byte drift"):
        fixture.run()


def test_placeholder_passes_through_without_rendering(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fixture = _fixture(tmp_path, monkeypatch)
    report = fixture.run()
    placeholder = fixture.successor_rows()[3]
    assert placeholder["body"] is None
    assert placeholder["metadata"]["structure_only"] is True
    assert placeholder["metadata"]["body_status"] == "not_in_ecfr_full_xml"
    assert report["preserved_structure_only_rows"] == [
        {"citation_path": placeholder["citation_path"], "body_status": "not_in_ecfr_full_xml", "source_path": SOURCE, "preserved": True}
    ]


@pytest.mark.parametrize(("field", "value", "message"), (("body", "Unexpected body", "structure-only row unexpectedly has body"), ("metadata", {"structure_only": True, "body_status": "unknown"}, "unknown structure-only status")), ids=("body", "status"))
def test_invalid_placeholder_refuses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str, value: Any, message: str) -> None:
    fixture = _fixture(tmp_path, monkeypatch)
    fixture.records[3][field] = value
    fixture.save()
    with pytest.raises(ValueError, match=message):
        fixture.run()
    fixture.assert_no_successor()


@pytest.mark.parametrize("same_size", (False, True))
def test_locked_file_hash_and_size_guard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, same_size: bool) -> None:
    fixture = _fixture(tmp_path, monkeypatch)
    path = fixture.base / SIDE_SOURCE
    payload = path.read_bytes()
    path.write_bytes(b"X" * len(payload) if same_size else payload + b"extra")
    with pytest.raises(ValueError, match="locked file differs"):
        fixture.run()
    fixture.assert_no_successor()


@pytest.mark.parametrize(("field", "value", "message"), (("source_path", f"{PREFIX}unlocked.xml", "inventory source is not locked"), ("sha256", "0" * 64, "inventory source hash differs")), ids=("source_path", "sha256"))
def test_inventory_sources_match_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str, value: str, message: str) -> None:
    fixture = _fixture(tmp_path, monkeypatch)
    fixture.inventory["items"][0][field] = value
    fixture.save()
    with pytest.raises(ValueError, match=message):
        fixture.run()
    fixture.assert_no_successor()


def test_inventory_and_provision_source_agree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fixture = _fixture(tmp_path, monkeypatch)
    fixture.records[0]["source_path"] = SIDE_SOURCE
    fixture.save()
    with pytest.raises(ValueError, match="provision/inventory source differs"):
        fixture.run()
    fixture.assert_no_successor()


def test_inventory_citations_agree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fixture = _fixture(tmp_path, monkeypatch)
    fixture.inventory["items"].pop()
    fixture.save()
    with pytest.raises(ValueError, match="inventory differs"):
        fixture.run()
    fixture.assert_no_successor()


def test_duplicate_citation_refuses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fixture = _fixture(tmp_path, monkeypatch)
    fixture.records.append(deepcopy(fixture.records[0]))
    fixture.save()
    with pytest.raises(ValueError, match="predecessor has duplicate citations"):
        fixture.run()
    fixture.assert_no_successor()


def test_paragraph_below_changed_section_refuses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fixture = _fixture(tmp_path, monkeypatch)
    paragraph = fixture.records[-1]
    paragraph["citation_path"] = fixture.records[0]["citation_path"] + "/a"
    paragraph["id"] = deterministic_provision_id(paragraph["citation_path"])
    fixture.inventory["items"][-1]["citation_path"] = paragraph["citation_path"]
    fixture.save()
    with pytest.raises(ValueError, match="paragraph must be regenerated with changed parent body"):
        fixture.run()
    fixture.assert_no_successor()


def test_paragraph_linked_to_changed_section_refuses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fixture = _fixture(tmp_path, monkeypatch)
    paragraph = fixture.records[-1]
    parent = fixture.records[0]["citation_path"]
    assert not paragraph["citation_path"].startswith(parent + "/")
    paragraph["parent_citation_path"] = parent
    paragraph["parent_id"] = deterministic_provision_id(parent, OLD)
    fixture.save()
    with pytest.raises(ValueError, match="paragraph must be regenerated with changed parent body"):
        fixture.run()
    fixture.assert_no_successor()


@pytest.mark.parametrize(("field", "value", "message"), (("body", "Prior unrelated body", "changed section is not pre832-equivalent"), ("heading", "Prior heading", "heading drift"), ("source_as_of", "2026-07-02", "mixed dates within one XML source")), ids=("body", "heading", "dates"))
def test_section_capture_guards(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str, value: str, message: str) -> None:
    fixture = _fixture(tmp_path, monkeypatch)
    fixture.records[0][field] = value
    fixture.save()
    with pytest.raises(ValueError, match=message):
        fixture.run()
    fixture.assert_no_successor()


def test_xml_must_contain_every_selected_section(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fixture = _fixture(tmp_path, monkeypatch)
    root = ET.fromstring(fixture.source_payloads[SOURCE])
    root.remove(root[0])
    payload = ET.tostring(root)
    fixture.source_payloads[SOURCE] = payload
    for item in fixture.inventory["items"]:
        item["sha256"] = _sha(payload)
    fixture.save()
    with pytest.raises(ValueError, match="XML identity mismatch"):
        fixture.run()
    fixture.assert_no_successor()


def test_xml_duplicate_section_refuses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fixture = _fixture(tmp_path, monkeypatch)
    root = ET.fromstring(fixture.source_payloads[SOURCE])
    root.append(deepcopy(root[0]))
    payload = ET.tostring(root)
    fixture.source_payloads[SOURCE] = payload
    for item in fixture.inventory["items"]:
        item["sha256"] = _sha(payload)
    fixture.save()
    with pytest.raises(ValueError, match="duplicate section in XML"):
        fixture.run()
    fixture.assert_no_successor()


def test_section_source_must_be_xml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fixture = _fixture(tmp_path, monkeypatch)
    fixture.records[0]["source_path"] = SIDE_SOURCE
    fixture.inventory["items"][0].update(source_path=SIDE_SOURCE, sha256=_sha(fixture.source_payloads[SIDE_SOURCE]))
    fixture.save()
    with pytest.raises(ValueError, match="row source is not XML"):
        fixture.run()
    fixture.assert_no_successor()


def test_extra_unlocked_local_sources_stay_out(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fixture = _fixture(tmp_path, monkeypatch)
    extra = fixture.base / PREFIX / "local-only.txt"
    extra.write_text("This local file has no predecessor lock entry.")
    fixture.run()
    assert not (fixture.base / f"sources/us/regulation/{NEW}/local-only.txt").exists()


def _mock_git_source(monkeypatch: pytest.MonkeyPatch, payload: bytes, *, pinned: bool = True) -> None:
    def read_source(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        assert command == ["git", "show", f"{repro.BASELINE_COMMIT}:{repro.BASELINE_SOURCE}"]
        assert kwargs == {"cwd": repro.REPO_ROOT, "capture_output": True, "check": True}
        return subprocess.CompletedProcess(command, 0, stdout=payload)

    monkeypatch.setattr(repro.subprocess, "run", read_source)
    if pinned:
        monkeypatch.setattr(repro, "BASELINE_SOURCE_SHA256", _sha(payload))


def test_pre832_source_hash_must_match(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_git_source(monkeypatch, b"# unrelated historical source", pinned=False)
    with pytest.raises(ValueError, match="pre832 renderer source digest differs"):
        repro.pre832_renderer()


def test_pre832_commit_must_exist(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing_commit(*args: Any, **kwargs: Any) -> None:
        raise subprocess.CalledProcessError(128, ["git", "show"])

    monkeypatch.setattr(repro.subprocess, "run", missing_commit)
    with pytest.raises(ValueError, match="cannot read pinned pre-#832 renderer from git"):
        repro.pre832_renderer()


def test_pre832_ast_runs_only_the_three_renderer_functions(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = b'''raise AssertionError("Do not execute historical top-level statements")
def unrelated():
    raise AssertionError("Do not call unrelated historical functions")
def _section_body(element):
    return _table_text(element)
def _table_text(element):
    return _element_text_with_breaks(element)
def _element_text_with_breaks(element):
    return "Pinned synthetic legacy body"
'''
    _mock_git_source(monkeypatch, payload)
    assert repro.pre832_renderer()(ET.Element("DIV8")) == "Pinned synthetic legacy body"


@pytest.mark.parametrize("duplicate", (False, True))
def test_pre832_ast_requires_exactly_one_of_each_function(monkeypatch: pytest.MonkeyPatch, duplicate: bool) -> None:
    payload = b'''def _section_body(element):
    return "legacy"
def _table_text(element):
    return "legacy"
'''
    if duplicate:
        payload += b'''def _element_text_with_breaks(element):
    return "legacy"
def _section_body(element):
    return "duplicate"
'''
    _mock_git_source(monkeypatch, payload)
    with pytest.raises(ValueError, match="baseline renderer functions missing or duplicated"):
        repro.pre832_renderer()


_json_value = st.recursive(
    st.none() | st.booleans() | st.integers() | st.text(max_size=20) | st.sampled_from([OLD, SOURCE, PREFIX, f"See {SOURCE} for the capture.", f"literal-{OLD}"]),
    lambda child: st.lists(child, max_size=3) | st.dictionaries(st.text(max_size=10), child, max_size=3),
    max_leaves=12,
)
_row_specs = st.lists(
    st.tuples(st.sampled_from(DEFAULT_KINDS), st.dictionaries(st.text(max_size=10), _json_value, max_size=3), st.booleans()),
    min_size=1,
    max_size=12,
)


def _expected_extra(value: Any) -> Any:
    """Apply the version and source-prefix contract independently to generated data."""
    if isinstance(value, dict):
        return {key: _expected_extra(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_expected_extra(item) for item in value]
    if isinstance(value, str):
        if value == OLD:
            return NEW
        return value.replace(PREFIX, f"sources/us/regulation/{NEW}/")
    return value


@settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(_row_specs)
@example([("changed", {"unicode": "\u0085\u2028\u2029"}, True)])
def test_every_non_body_field_survives_version_rewrite(tmp_path: Path, specs: list[tuple[str, dict[str, Any], bool]]) -> None:
    # Each generated example owns a clean scope; no predecessor bytes need a fetch.
    case = tmp_path / "property-case"
    if case.exists():
        shutil.rmtree(case)
    with pytest.MonkeyPatch.context() as monkeypatch:
        fixture = _fixture(case, monkeypatch, kinds=tuple(spec[0] for spec in specs), extras=[spec[1] for spec in specs], version_ids=[spec[2] for spec in specs])
        fixture.run()
        for index, (old, new) in enumerate(zip(fixture.records, fixture.successor_rows(), strict=True)):
            expected = deepcopy(old)
            expected.pop("body")
            expected["version"] = NEW
            expected["source_path"] = SOURCE.replace(f"/{OLD}/", f"/{NEW}/")
            expected["metadata"]["capture_version"] = NEW
            expected["metadata"]["image"]["path"] = f"sources/us/regulation/{NEW}/images/{index}.png"
            expected["metadata"]["references"] = [NEW, f"See {expected['source_path']} for the capture.", f"literal-{OLD}"]
            expected["metadata"]["extra"] = _expected_extra(old["metadata"]["extra"])
            for field, path in (("id", old["citation_path"]), ("parent_id", old.get("parent_citation_path"))):
                if path and specs[index][2]:
                    expected[field] = deterministic_provision_id(path, NEW)
            assert {field: value for field, value in new.items() if field != "body"} == expected
