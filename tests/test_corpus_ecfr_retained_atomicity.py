"""Unreadable existing artifacts must leave a retained-XML rebuild unchanged."""

import json
import tempfile
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.ecfr import extract_ecfr


def _assert_unreadable_artifact_preserves_run(root, artifact, corrupt_bytes, part, body):
    source = root / "official.xml"
    xml = (
        f'<ECFR><DIV5 N="{part}" TYPE="PART"><HEAD>Part {part}</HEAD>'
        '<DIV8 N="3809.1" TYPE="SECTION"><HEAD>Section one</HEAD>'
        '<P>Saved body.</P></DIV8></DIV5></ECFR>'
    )
    source.write_text(xml)
    store = CorpusArtifactStore(root / "corpus")
    kwargs = {
        "version": "retained-review", "as_of": "2026-10-08", "source_xml": source,
        "only_title": 43, "only_part": part, "only_sections": ("3809.1",), "workers": 1,
    }
    report = extract_ecfr(store, **kwargs)
    assert report.coverage.complete and not report.title_errors
    artifact_path = report.inventory_path if artifact == "inventory" else report.provisions_path
    artifact_path.write_bytes(corrupt_bytes)
    before = {
        path.relative_to(store.root): path.read_bytes()
        for path in store.root.rglob("*") if path.is_file()
    }
    assert {path.parts[0] for path in before} == {
        "sources", "inventory", "provisions", "coverage",
    }
    snapshot = next(path for path in report.source_paths if path.suffix == ".xml")
    source.write_text(xml.replace("Saved body.", f"Changed {body}."))
    assert source.read_bytes() != before[snapshot.relative_to(store.root)]

    with pytest.raises((json.JSONDecodeError, UnicodeDecodeError)):
        extract_ecfr(store, **kwargs)

    # The failed read must precede every write, including the replacement XML.
    assert snapshot.read_bytes() == before[snapshot.relative_to(store.root)]
    assert {
        path.relative_to(store.root): path.read_bytes()
        for path in store.root.rglob("*") if path.is_file()
    } == before


@pytest.mark.parametrize("artifact", ["inventory", "provisions"])
def test_retained_rebuild_with_corrupt_artifact_preserves_run(tmp_path, monkeypatch, artifact):
    monkeypatch.chdir(tmp_path)
    _assert_unreadable_artifact_preserves_run(tmp_path, artifact, b"{", "3800", "body")


@settings(
    max_examples=32, deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    artifact=st.sampled_from(["inventory", "provisions"]),
    corrupt_bytes=st.sampled_from([b"{", b'{"items": [', b"\xff"]),
    part=st.sampled_from(["3800", "3809"]),
    body=st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789 ", max_size=40),
)
def test_property_unreadable_artifact_rebuild_preserves_run(
    tmp_path, monkeypatch, artifact, corrupt_bytes, part, body
):
    monkeypatch.chdir(tmp_path)
    with tempfile.TemporaryDirectory(dir=tmp_path) as tmp:
        _assert_unreadable_artifact_preserves_run(
            Path(tmp), artifact, corrupt_bytes, part, body,
        )
