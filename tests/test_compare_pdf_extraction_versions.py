"""Tests for scripts/compare_pdf_extraction_versions.py.

Invariants:

* ``reproduced_rows`` returns committed citation paths only, never more than
  there are blocks (each block reproduces at most one row), every row when the
  blocks carry the committed bodies under any paths, and never fewer rows when
  a block is added at a new path.
* ``compare_documents``: the committed rows of the compared documents split
  into reproduced on both, on the locked snapshot only, on the candidate only
  and on neither, with nothing left over; two equal snapshots differ nowhere
  and reproduce the same rows; exchanging the snapshots exchanges the two
  ``only`` counts and leaves every difference count as it was.
* ``select_tasks``: ``--ocr skip`` and ``--ocr only`` split ``--ocr all``.
* End to end, two snapshots of the same environment compare equal, and a
  committed body the extractor does not produce counts as reproduced on neither.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import fitz
import pytest
import yaml
from hypothesis import given, settings
from hypothesis import strategies as st

from scripts.compare_pdf_extraction_versions import (
    BODY,
    build_plan,
    compare,
    compare_documents,
    compare_pdfs,
    digest,
    main,
    reproduced_rows,
    run_snapshot,
    select_tasks,
)

BODIES = st.sampled_from(["alpha", "beta", "gamma", "delta"]).map(digest)
PATHS = st.sampled_from([f"xx/policy/doc/page-{n}" for n in range(1, 7)])


def _block(path: str, body: str, heading: str = "h", metadata: str = "m") -> list[object]:
    return [path, heading, body, 10, body, 8, metadata]


def _blocks(entries: dict[str, str]) -> dict[str, list[object]]:
    return {path: _block(path, body) for path, body in entries.items()}


def test_reproduced_rows_matches_by_path_then_by_body() -> None:
    committed = {"a": digest("one"), "b": digest("two"), "c": digest("three")}
    blocks = _blocks({"a": digest("one"), "renamed": digest("two"), "c": digest("other")})
    assert reproduced_rows(blocks, committed) == {"a", "b"}


def test_a_block_reproduces_at_most_one_row() -> None:
    committed = {"a": digest("same"), "b": digest("same")}
    assert len(reproduced_rows(_blocks({"x": digest("same")}), committed)) == 1
    both = _blocks({"x": digest("same"), "y": digest("same")})
    assert reproduced_rows(both, committed) == {"a", "b"}


@settings(max_examples=200, deadline=None)
@given(
    committed=st.dictionaries(PATHS, BODIES, max_size=6),
    blocks=st.dictionaries(PATHS, BODIES, max_size=6),
)
def test_reproduced_rows_is_a_bounded_subset_of_the_committed_rows(
    committed: dict[str, str], blocks: dict[str, str]
) -> None:
    reproduced = reproduced_rows(_blocks(blocks), committed)
    assert reproduced <= committed.keys()
    assert len(reproduced) <= len(blocks)


@settings(max_examples=200, deadline=None)
@given(committed=st.dictionaries(PATHS, BODIES, max_size=6), data=st.data())
def test_the_committed_bodies_under_any_paths_reproduce_every_row(
    committed: dict[str, str], data: st.DataObject
) -> None:
    paths = data.draw(st.permutations([f"other-{n}" for n in range(len(committed))]))
    renamed = dict(zip(paths, committed.values(), strict=True))
    assert reproduced_rows(_blocks(renamed), committed) == committed.keys()
    assert reproduced_rows(_blocks(committed), committed) == committed.keys()


@settings(max_examples=200, deadline=None)
@given(
    committed=st.dictionaries(PATHS, BODIES, max_size=6),
    blocks=st.dictionaries(PATHS, BODIES, max_size=5),
    path=PATHS,
    body=BODIES,
)
def test_adding_a_block_never_reproduces_fewer_rows(
    committed: dict[str, str], blocks: dict[str, str], path: str, body: str
) -> None:
    if path in blocks:
        return
    before = reproduced_rows(_blocks(blocks), committed)
    after = reproduced_rows(_blocks({**blocks, path: body}), committed)
    assert len(after) >= len(before)


def _task(index: int) -> dict[str, object]:
    return {
        "kind": "document",
        "key": f"doc-{index}",
        "scope": f"xx/policy/v{index % 2}",
        "ocr": False,
        "candidates": [],
    }


def _record(key: str, blocks: dict[str, list[object]]) -> dict[str, object]:
    return {"key": key, "candidates": [{"blocks": list(blocks.values()), "warnings": 0}]}


BLOCK_SETS = st.dictionaries(PATHS, st.tuples(BODIES, st.sampled_from(["h", "h2"])), max_size=5)


def _rich_blocks(entries: dict[str, tuple[str, str]]) -> dict[str, list[object]]:
    return {path: _block(path, body, heading) for path, (body, heading) in entries.items()}


@settings(max_examples=150, deadline=None)
@given(
    documents=st.lists(
        st.tuples(BLOCK_SETS, BLOCK_SETS, st.dictionaries(PATHS, BODIES, max_size=5)),
        min_size=1,
        max_size=4,
    )
)
def test_compare_documents_conserves_rows_and_is_symmetric(
    documents: list[tuple[dict, dict, dict[str, str]]],
) -> None:
    plan = [_task(index) for index in range(len(documents))]
    locked = {
        f"doc-{i}": _record(f"doc-{i}", _rich_blocks(a)) for i, (a, _, _) in enumerate(documents)
    }
    candidate = {
        f"doc-{i}": _record(f"doc-{i}", _rich_blocks(b)) for i, (_, b, _) in enumerate(documents)
    }
    committed = {f"doc-{i}": rows for i, (_, _, rows) in enumerate(documents)}

    forward, _ = compare_documents(plan, locked, candidate, committed)
    backward, _ = compare_documents(plan, candidate, locked, committed)

    rows = forward["rows"]
    assert rows["committed_rows"] == sum(len(rows) for _, _, rows in documents)
    assert rows["committed_rows"] == (
        rows["committed_rows_reproduced_on_both"]
        + rows["committed_rows_reproduced_on_locked_only"]
        + rows["committed_rows_reproduced_on_candidate_only"]
        + rows["committed_rows_reproduced_on_neither"]
    )
    assert forward["documents"]["extracted_on_both"] == len(documents)
    swapped = dict(backward["rows"])
    (
        swapped["committed_rows_reproduced_on_locked_only"],
        swapped["committed_rows_reproduced_on_candidate_only"],
    ) = (
        swapped["committed_rows_reproduced_on_candidate_only"],
        swapped["committed_rows_reproduced_on_locked_only"],
    )
    assert swapped == rows
    differences = {
        key: value
        for key, value in forward["documents"].items()
        if not key.startswith("differing_with_every_committed_row")
    }
    assert differences == {
        key: value
        for key, value in backward["documents"].items()
        if not key.startswith("differing_with_every_committed_row")
    }


@settings(max_examples=100, deadline=None)
@given(
    documents=st.lists(
        st.tuples(BLOCK_SETS, st.dictionaries(PATHS, BODIES, max_size=5)), min_size=1, max_size=4
    )
)
def test_equal_snapshots_differ_nowhere(documents: list[tuple[dict, dict[str, str]]]) -> None:
    plan = [_task(index) for index in range(len(documents))]
    snapshot = {
        f"doc-{i}": _record(f"doc-{i}", _rich_blocks(blocks))
        for i, (blocks, _) in enumerate(documents)
    }
    committed = {f"doc-{i}": rows for i, (_, rows) in enumerate(documents)}
    summary, details = compare_documents(plan, snapshot, snapshot, committed)
    assert details == []
    assert summary["documents"]["identical"] == len(documents)
    assert summary["scopes_with_a_differing_document"] == 0
    assert summary["rows"]["committed_rows_reproduced_on_locked_only"] == 0
    assert summary["rows"]["committed_rows_reproduced_on_candidate_only"] == 0


def test_compare_documents_classifies_each_kind_of_difference() -> None:
    plan = [_task(index) for index in range(5)]
    base = _blocks({"p1": digest("one"), "p2": digest("two")})
    whitespace = {path: list(block) for path, block in base.items()}
    whitespace["p2"][BODY] = digest("t w o")  # same non-space digest
    characters = {path: list(block) for path, block in base.items()}
    characters["p2"][BODY] = digest("three")
    characters["p2"][4] = digest("three")
    extra = {**base, "p3": _block("p3", digest("new"))}
    heading = {path: list(block) for path, block in base.items()}
    heading["p1"][1] = "other heading"
    locked = {f"doc-{i}": _record(f"doc-{i}", base) for i in range(5)}
    candidate = {
        "doc-0": _record("doc-0", base),
        "doc-1": _record("doc-1", whitespace),
        "doc-2": _record("doc-2", characters),
        "doc-3": _record("doc-3", extra),
        "doc-4": _record("doc-4", heading),
    }
    committed = {f"doc-{i}": {"p1": digest("one"), "p2": digest("two")} for i in range(5)}
    summary, details = compare_documents(plan, locked, candidate, committed)
    assert summary["documents"]["identical"] == 1
    assert summary["documents"]["differ_in_whitespace_only"] == 1
    assert summary["documents"]["differ_in_characters_or_blocks"] == 2
    assert summary["documents"]["differ_in_heading_or_metadata_only"] == 1
    assert summary["rows"]["committed_rows_reproduced_on_locked_only"] == 2
    by_key = {item["key"]: item for item in details}
    assert by_key["doc-2"]["every_committed_row_reproduced_by"] == "locked"
    assert by_key["doc-3"]["every_committed_row_reproduced_by"] == "both"


def test_compare_documents_counts_errors_apart() -> None:
    plan = [_task(0), _task(1), _task(2)]
    failing = {"key": "doc-0", "candidates": [{"error": "FileDataError: Failed to open stream"}]}
    locked = {
        "doc-0": failing,
        "doc-1": {"key": "doc-1", "error": "read: FileNotFoundError()"},
        "doc-2": {"key": "doc-2", "candidates": [{"error": "ValueError: no section"}]},
    }
    candidate = {
        "doc-0": failing,
        "doc-1": {"key": "doc-1", "error": "read: FileNotFoundError()"},
        "doc-2": _record("doc-2", _blocks({"p1": digest("one")})),
    }
    summary, details = compare_documents(plan, locked, candidate, {})
    assert summary["documents"]["extraction_fails_on_both:FileDataError"] == 1
    assert summary["documents"]["source_file_unreadable"] == 1
    assert summary["documents"]["extraction_fails_on_one"] == 1
    assert [item["key"] for item in details] == ["doc-2"]
    assert summary["scopes_with_a_differing_document"] == 1


def _pdf_record(key: str, pages: list[list[object]]) -> dict[str, object]:
    return {"key": key, "path": f"{key}.pdf", "pages": pages}


def test_compare_pdfs_counts_the_pages_that_differ() -> None:
    plan = [{"kind": "pdf", "key": key, "path": f"{key}.pdf"} for key in ("same", "chars", "count")]
    page = ["t", "n", 10, "s", "sn", "w"]
    changed = ["t2", "n2", 12, "s2", "sn2", "w2"]
    locked = {
        "same": _pdf_record("same", [page, page]),
        "chars": _pdf_record("chars", [page, page]),
        "count": _pdf_record("count", [page]),
    }
    candidate = {
        "same": _pdf_record("same", [page, page]),
        "chars": _pdf_record("chars", [page, changed]),
        "count": _pdf_record("count", [page, page]),
    }
    counts, details = compare_pdfs(plan, locked, candidate)
    assert counts["pdfs_compared"] == 3
    assert counts["pages_compared"] == 4
    assert counts["pages_differing_in_get_text_characters"] == 1
    assert counts["pdfs_with_differing_page_count"] == 1
    assert counts["pdfs_with_a_differing_page"] == 1
    by_key = {item["key"]: item for item in details}
    assert by_key["chars"]["example_pages"] == [2]
    assert by_key["chars"]["nonspace_characters_candidate_minus_locked"] == 2


@settings(max_examples=100, deadline=None)
@given(flags=st.lists(st.booleans(), max_size=8))
def test_ocr_skip_and_only_split_all(flags: list[bool]) -> None:
    plan = [
        {"kind": "document", "key": f"doc-{index}", "ocr": flag} for index, flag in enumerate(flags)
    ] + [{"kind": "pdf", "key": "pdf-0"}]
    kinds = {"document", "pdf"}
    every = select_tasks(plan, done=set(), kinds=kinds, ocr="all")
    skip = select_tasks(plan, done=set(), kinds=kinds, ocr="skip")
    only = select_tasks(plan, done=set(), kinds=kinds, ocr="only")
    documents = [task["key"] for task in every if task["kind"] == "document"]
    assert sorted(t["key"] for t in skip + only if t["kind"] == "document") == sorted(documents)
    assert not {t["key"] for t in skip if t["kind"] == "document"} & {
        t["key"] for t in only if t["kind"] == "document"
    }
    assert select_tasks(plan, done={"pdf-0"}, kinds={"pdf"}, ocr="all") == []


# ------------------------------------------------------------------ end to end

SCOPE = ("xx", "policy", "2026-01-01-test")
SOURCE_PATH = "sources/xx/policy/2026-01-01-test/official-documents/test-doc.pdf"


def _corpus(root: Path) -> Path:
    """A one-document corpus whose committed rows the extractor reproduces."""
    from axiom_corpus.corpus import documents

    jurisdiction, document_class, version = SCOPE
    pdf = fitz.open()
    for text in ("Section 1. Eligibility\nA household qualifies.", "Section 2. Amounts"):
        page = pdf.new_page()
        page.insert_text((72, 72), text, fontsize=11)
    pdf_path = root / "data" / "corpus" / SOURCE_PATH
    pdf_path.parent.mkdir(parents=True)
    pdf.save(pdf_path)
    content = pdf_path.read_bytes()

    row = {
        "source_id": "test-doc",
        "jurisdiction": jurisdiction,
        "document_class": document_class,
        "title": "Test document",
        "source_url": "https://example.gov/test-doc.pdf",
    }
    (root / "manifests").mkdir()
    (root / "manifests" / "xx-test.yaml").write_text(yaml.safe_dump({"documents": [row]}))
    source = documents.OfficialDocumentSource.from_mapping(row)
    blocks = documents._extract_blocks(
        content, "pdf", source_url=source.source_url, title=source.title, extraction=None
    )
    provisions = root / "data" / "corpus" / "provisions" / jurisdiction / document_class
    provisions.mkdir(parents=True)
    rows = [
        {
            "citation_path": "xx/policy/test-doc",
            "source_format": "pdf",
            "source_path": SOURCE_PATH,
            "source_id": "test-doc",
            "body": None,
        }
    ]
    rows += [
        {
            "citation_path": documents._block_citation_path(source, block),
            "source_format": "pdf",
            "source_path": SOURCE_PATH,
            "source_id": "test-doc",
            "body": block.body,
        }
        for block in blocks
    ]
    provisions_path = provisions / f"{version}.jsonl"
    provisions_path.write_text("".join(json.dumps(item) + "\n" for item in rows))

    lock = root / ".axiom" / "corpus-locks" / jurisdiction / document_class / f"{version}.json"
    lock.parent.mkdir(parents=True)
    lock.write_text(
        json.dumps(
            {
                "jurisdiction": jurisdiction,
                "document_class": document_class,
                "version": version,
                "files": [
                    {"path": f"data/corpus/{SOURCE_PATH}", "sha256": "a" * 64},
                    {"path": provisions_path.relative_to(root).as_posix(), "sha256": "b" * 64},
                ],
            }
        )
    )
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "manifests"], check=True)
    return provisions_path


def test_end_to_end_equal_snapshots_reproduce_every_committed_row(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    provisions_path = _corpus(tmp_path)
    plan = build_plan(tmp_path)
    assert [task["kind"] for task in plan] == ["document", "pdf"]
    assert plan[0]["rows"] == 3  # the document row and two pages
    assert plan[0]["candidates"][0]["manifest"] == "manifests/xx-test.yaml"

    plan_path = tmp_path / "plan.jsonl"
    assert main(["--root", str(tmp_path), "plan", "--out", str(plan_path)]) == 0
    assert [json.loads(line) for line in plan_path.read_text().splitlines()] == plan
    for name in ("locked", "candidate"):
        snapshot = tmp_path / f"{name}.jsonl"
        assert run_snapshot(plan, snapshot, root=tmp_path, kinds={"document", "pdf"}) == 2
        # A rerun skips the finished tasks.
        assert run_snapshot(plan, snapshot, root=tmp_path, kinds={"document", "pdf"}) == 0

    capsys.readouterr()
    details_path = tmp_path / "details.jsonl"
    argv = ["--root", str(tmp_path), "compare", "--plan", str(plan_path)]
    argv += ["--locked", str(tmp_path / "locked.jsonl")]
    argv += ["--candidate", str(tmp_path / "candidate.jsonl"), "--details", str(details_path)]
    assert main(argv) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["documents"]["identical"] == 1
    assert report["rows"]["committed_rows"] == 2
    assert report["rows"]["committed_rows_reproduced_on_both"] == 2
    assert report["pdfs"]["pages_compared"] == 2
    assert "pdfs_with_a_differing_page" not in report["pdfs"]
    assert details_path.read_text() == ""

    # A committed body the extractor does not produce is reproduced by neither.
    rows = [json.loads(line) for line in provisions_path.read_text().splitlines()]
    rows[1]["body"] = "text no PyMuPDF release reads from this page"
    provisions_path.write_text("".join(json.dumps(item) + "\n" for item in rows))
    records = [json.loads(line) for line in (tmp_path / "locked.jsonl").read_text().splitlines()]
    report, _ = compare(tmp_path, plan, records, records)
    assert report["rows"]["committed_rows_reproduced_on_neither"] == 1
    assert report["rows"]["committed_rows_reproduced_on_both"] == 1
