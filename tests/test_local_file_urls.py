"""A local_path copy never publishes the extracting machine's path.

Invariants:

1. Extraction from a manifest ``local_path`` copy records the manifest's
   official URL (``download_url``, else the Drive direct link, else
   ``source_url``) as ``metadata.download_url`` on every inventory item and
   provision row, never a ``file:`` URL, and records the media type of the
   declared or detected source format.
2. A relative ``local_path`` resolves against the manifest file, not the
   working directory.
3. ``local_file_url_fields`` reports exactly the URL fields (``url``, ``urls``,
   ``*_url``, ``*_urls`` at any depth) whose decoded value starts with
   ``file:`` (any case, after surrounding whitespace), however the JSON spells
   them; body text is never reported. Its prefilter agrees with a brute-force
   reference that parses every row, and it fails closed: an artifact it cannot
   decode or parse where a ``file:`` URL could sit raises instead of passing.
"""

from __future__ import annotations

import json
from pathlib import Path

import fitz  # type: ignore[import-untyped]
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.documents import (
    _SOURCE_FORMAT_CONTENT_TYPES,
    OfficialDocumentManifest,
    OfficialDocumentSource,
    _download_document,
    extract_official_documents,
)
from axiom_corpus.corpus.ingest_manifests import (
    LocalFileUrlScanError,
    _content_issues,
    local_file_url_fields,
)

INVENTORY = "data/corpus/inventory/de/guidance/2026-10-14-example.json"
PROVISIONS = "data/corpus/provisions/de/guidance/2026-10-14-example.jsonl"


def _pdf(path: Path, text: str) -> Path:
    document = fitz.open()
    document.new_page().insert_text((72, 72), text)
    document.save(path)
    document.close()
    return path


def _extract(tmp_path: Path, manifest_text: str) -> tuple[dict, list[dict], str]:
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text(manifest_text)
    report = extract_official_documents(
        CorpusArtifactStore(tmp_path / "corpus"),
        manifest_path=manifest_path,
        version="2026-10-14",
        source_as_of="2026-10-14",
    )
    inventory_text = report.inventory_path.read_text()
    provisions_text = report.provisions_path.read_text()
    rows = [json.loads(line) for line in provisions_text.splitlines() if line]
    return json.loads(inventory_text), rows, inventory_text + provisions_text


def test_local_path_extraction_records_official_urls_not_file_paths(tmp_path: Path) -> None:
    retained = tmp_path / "retained"
    retained.mkdir()
    html_path = retained / "page.html"
    html_path.write_text("<html><body><h1>Kindergeld</h1><p>Anspruch.</p></body></html>")
    pdf_path = _pdf(retained / "letter.pdf", "BMF letter text")
    drive_pdf = _pdf(retained / "drive.pdf", "Drive copy text")
    inventory, provisions, serialized = _extract(
        tmp_path,
        f"""
documents:
  - source_id: de-page
    jurisdiction: de
    document_class: guidance
    title: Page
    source_url: https://www.example.de/page
    source_format: html
    local_path: {json.dumps(str(html_path))}
  - source_id: de-letter
    jurisdiction: de
    document_class: guidance
    title: Letter
    source_url: https://www.example.de/letter
    download_url: https://www.example.de/letter.pdf?__blob=publicationFile
    local_path: {json.dumps(str(pdf_path))}
  - source_id: de-drive
    jurisdiction: de
    document_class: guidance
    title: Drive copy
    source_url: https://drive.google.com/file/d/abc123/view
    source_format: pdf
    local_path: {json.dumps(str(drive_pdf))}
""",
    )

    assert "file:" not in serialized
    assert str(tmp_path) not in serialized
    expected = {
        "de-page": ("https://www.example.de/page", "text/html"),
        "de-letter": (
            "https://www.example.de/letter.pdf?__blob=publicationFile",
            "application/pdf",
        ),
        "de-drive": (
            "https://drive.google.com/uc?export=download&id=abc123",
            "application/pdf",
        ),
    }
    for row in provisions:
        url, content_type = expected[row["source_id"]]
        assert row["metadata"]["download_url"] == url
        assert row["metadata"]["content_type"] == content_type
    by_source = {
        item["source_path"].rsplit("/", 1)[-1].split(".", 1)[0]: item for item in inventory["items"]
    }
    for source_id, (url, content_type) in expected.items():
        assert by_source[source_id]["metadata"]["download_url"] == url
        assert by_source[source_id]["metadata"]["content_type"] == content_type
    assert all("file:" not in json.dumps(item) for item in inventory["items"])
    assert _content_issues(INVENTORY, json.dumps(inventory).encode()) == []


def test_relative_local_path_resolves_against_the_manifest(tmp_path, monkeypatch) -> None:
    manifest_dir = tmp_path / "manifests"
    (manifest_dir / "retained").mkdir(parents=True)
    _pdf(manifest_dir / "retained" / "act.pdf", "Relative copy text")
    manifest_path = manifest_dir / "act.yaml"
    manifest_path.write_text(
        """
documents:
  - source_id: act
    jurisdiction: de
    document_class: statute
    title: Act
    source_url: https://www.example.de/act.pdf
    local_path: retained/act.pdf
"""
    )
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    (source,) = OfficialDocumentManifest.load(manifest_path).documents
    assert source.local_path == str(manifest_dir / "retained" / "act.pdf")
    report = extract_official_documents(
        CorpusArtifactStore(tmp_path / "corpus"),
        manifest_path=manifest_path,
        version="2026-10-14",
    )
    (root, page) = [json.loads(line) for line in report.provisions_path.read_text().splitlines()]
    assert "Relative copy text" in page["body"]
    assert root["metadata"]["download_url"] == "https://www.example.de/act.pdf"


def test_absolute_local_path_is_left_as_written(tmp_path: Path) -> None:
    pdf_path = _pdf(tmp_path / "act.pdf", "Absolute copy")
    manifest_path = tmp_path / "nested" / "act.yaml"
    manifest_path.parent.mkdir()
    manifest_path.write_text(
        f"""
documents:
  - source_id: act
    jurisdiction: de
    document_class: statute
    title: Act
    source_url: https://www.example.de/act.pdf
    local_path: {json.dumps(str(pdf_path))}
"""
    )
    (source,) = OfficialDocumentManifest.load(manifest_path).documents
    assert source.local_path == str(pdf_path)


_FORMAT_BYTES = {
    "pdf": b"%PDF-1.7\n",
    "html": b"<!doctype html><p>x</p>",
    "json": b"{}",
    "javascript": b"const toc = [];",
    "csv": b"a,b\n1,2\n",
    "doc": b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",
    "docx": b"PK\x03\x04",
    "xlsx": b"PK\x03\x04",
    "xls": b"\xd0\xcf\x11\xe0",
}
_URL = st.from_regex(r"https://[a-z]{1,12}\.example/[a-z0-9/]{0,20}", fullmatch=True)


class _NoNetwork:
    def get(self, *args, **kwargs):  # pragma: no cover - the property fails if reached
        raise AssertionError("a local_path copy must not touch the network")


@settings(max_examples=200, deadline=None)
@given(
    source_format=st.sampled_from(sorted(_SOURCE_FORMAT_CONTENT_TYPES)),
    source_url=_URL,
    download_url=st.none() | _URL,
    case=st.sampled_from([str.lower, str.upper]),
)
def test_local_copy_records_the_official_url_and_format_media_type(
    tmp_path_factory, source_format, source_url, download_url, case
) -> None:
    path = tmp_path_factory.mktemp("copy") / f"retained.{source_format}"
    path.write_bytes(_FORMAT_BYTES[source_format])
    source = OfficialDocumentSource(
        source_id="doc",
        jurisdiction="de",
        document_class="guidance",
        title="Doc",
        source_url=source_url,
        download_url=download_url,
        source_format=case(source_format),
        local_path=str(path),
    )
    downloaded = _download_document(source, session=_NoNetwork())  # type: ignore[arg-type]
    assert downloaded.final_url == (download_url or source_url)
    assert not downloaded.final_url.lower().startswith("file:")
    assert downloaded.content_type == _SOURCE_FORMAT_CONTENT_TYPES[source_format]
    assert downloaded.content == _FORMAT_BYTES[source_format]


def test_local_copy_without_declared_format_uses_the_detected_one(tmp_path: Path) -> None:
    pdf_path = _pdf(tmp_path / "copy.bin", "Detected")
    source = OfficialDocumentSource(
        source_id="doc",
        jurisdiction="de",
        document_class="guidance",
        title="Doc",
        source_url="https://www.example.de/doc",
        local_path=str(pdf_path),
    )
    downloaded = _download_document(source, session=_NoNetwork())  # type: ignore[arg-type]
    assert downloaded.content_type == "application/pdf"
    assert downloaded.final_url == "https://www.example.de/doc"


def _row(citation: str, **fields) -> dict:
    metadata = fields.pop("metadata", {})
    return {"citation_path": citation, "metadata": metadata, **fields}


def test_guard_reports_file_urls_in_url_fields_only() -> None:
    leaky = [
        _row(
            f"de/guidance/x/{index}",
            source_url="https://www.example.de/x",
            metadata={"download_url": "file:///Users/someone/retained.pdf"},
        )
        for index in range(5)
    ]
    body_only = _row(
        "us-nj/policy/plan/page-1",
        source_url="https://www.medicaid.gov/plan.pdf",
        body="printed link file:///C/Users/Gbb9/Desktop/plan.htm",
        metadata={"download_url": "https://www.medicaid.gov/plan.pdf"},
    )
    provisions = "\n".join(json.dumps(row) for row in [body_only, *leaky]) + "\n"
    (issue,) = _content_issues(PROVISIONS, provisions.encode())
    assert "5 row field(s)" in issue
    assert "`de/guidance/x/0` metadata.download_url" in issue
    assert "and 2 more" in issue
    assert "/Users/someone" not in issue  # the message never republishes the path
    assert _content_issues(PROVISIONS, (json.dumps(body_only) + "\n").encode()) == []

    inventory = {"items": [_row("de/guidance/y", source_url="FILE:///tmp/y.html")]}
    (issue,) = _content_issues(INVENTORY, json.dumps(inventory).encode())
    assert "`de/guidance/y` source_url" in issue

    other_field = {"items": [_row("de/guidance/z", metadata={"legal_authority_url": "file:///z"})]}
    assert local_file_url_fields(INVENTORY, json.dumps(other_field).encode()) == [
        ("de/guidance/z", "metadata.legal_authority_url")
    ]
    # Coverage and source files are not row artifacts.
    assert _content_issues("data/corpus/coverage/de/guidance/v.json", provisions.encode()) == []


def _reference(path: str, payload: bytes) -> list[tuple[str, str]]:
    """Parse every row with no prefilter and visit every key, depth first."""
    text = payload.decode("utf-8-sig")
    if path.endswith(".jsonl"):
        rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    else:
        rows = json.loads(text).get("items", [])
    found = []

    def visit(value, dotted):
        if isinstance(value, list):
            for child in value:
                visit(child, dotted)
            return
        if not isinstance(value, dict):
            return
        for key, child in value.items():
            here = f"{dotted}.{key}" if dotted else key
            url_key = key in ("url", "urls") or key.endswith(("_url", "_urls"))
            values = child if isinstance(child, list) else [child]
            if url_key and any(
                isinstance(v, str) and v.strip().lower().startswith("file:") for v in values
            ):
                found.append(here)
            visit(child, here)

    result = []
    for row in rows:
        found.clear()
        visit(row, "")
        result.extend((row["citation_path"], field) for field in found)
    return result


def _escape_some(serialized: str, data: st.DataObject) -> str:
    """Spell some ASCII letters of the serialized JSON as \\uXXXX escapes."""
    out = []
    in_string = False
    escaped = False
    for char in serialized:
        if in_string and not escaped and char.isalpha() and data.draw(st.booleans()):
            out.append(f"\\u{ord(char):04x}")
        else:
            out.append(char)
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == '"':
            in_string = not in_string
    return "".join(out)


_URLISH = st.sampled_from(
    [
        "https://www.example.de/a.pdf",
        "file:///Users/someone/a.pdf",
        "FILE:///tmp/a.html",
        "  file:///private/tmp/a",
        "files.example/a",
        "http://file:8080/a",
        "",
    ]
)


@settings(max_examples=300, deadline=None)
@given(
    rows=st.lists(
        st.fixed_dictionaries(
            {
                "source_url": _URLISH,
                "body": st.sampled_from(["", "see file:///C/x.htm", "plain"]),
                "metadata": st.dictionaries(
                    st.sampled_from(["download_url", "url", "legal_authority_url", "note"]),
                    _URLISH,
                    max_size=3,
                ),
                "extra": st.dictionaries(
                    st.sampled_from(["provenance", "source_urls", "mirror_url"]),
                    _URLISH
                    | st.lists(_URLISH, max_size=2)
                    | st.fixed_dictionaries({"download_url": _URLISH, "label": _URLISH}),
                    max_size=2,
                ),
            }
        ),
        max_size=6,
    ),
    jsonl=st.booleans(),
    ensure_ascii=st.booleans(),
    data=st.data(),
)
def test_prefiltered_scan_agrees_with_the_brute_force_reference(
    rows, jsonl, ensure_ascii, data
) -> None:
    rows = [
        {"citation_path": f"de/guidance/r/{i}", **row, "metadata": {**row["metadata"], **row.pop("extra")}}
        for i, row in enumerate(rows)
    ]
    if jsonl:
        path = PROVISIONS
        text = "\n".join(
            _escape_some(json.dumps(row, ensure_ascii=ensure_ascii), data) for row in rows
        )
    else:
        path = INVENTORY
        text = _escape_some(json.dumps({"items": rows}, ensure_ascii=ensure_ascii), data)
    payload = text.encode("utf-8")
    assert local_file_url_fields(path, payload) == _reference(path, payload)


def test_an_unparseable_candidate_line_fails_closed() -> None:
    """Review finding: one malformed line used to clear every leak in its artifact."""
    leaky = json.dumps(_row("de/guidance/a", metadata={"download_url": "file:///Users/x/a.pdf"}))
    payload = (leaky + "\n" + '{"citation_path": "de/guidance/b", "note": "file:' + "\n").encode()
    with pytest.raises(LocalFileUrlScanError, match="line 2 is not JSON"):
        local_file_url_fields(PROVISIONS, payload)
    (issue,) = _content_issues(PROVISIONS, payload)
    assert "cannot be checked for file: URLs" in issue
    assert "/Users/x" not in issue
    # A malformed line that could not hold a file: URL is left to other checks.
    assert local_file_url_fields(PROVISIONS, (leaky + "\n{not json\n").encode()) == [
        ("de/guidance/a", "metadata.download_url")
    ]


@pytest.mark.parametrize(
    ("path", "payload", "message"),
    [
        (INVENTORY, b"\xff\xfe not utf-8", "is not UTF-8"),
        (PROVISIONS, b"\xff\xfe not utf-8", "is not UTF-8"),
        (INVENTORY, b'{"items": [ file:', "is not JSON"),
        (INVENTORY, b'{"items": {"a": "file:///x"}}', "no list of inventory items"),
    ],
)
def test_unreadable_artifacts_fail_closed(path: str, payload: bytes, message: str) -> None:
    with pytest.raises(LocalFileUrlScanError, match=message):
        local_file_url_fields(path, payload)
    assert len(_content_issues(path, payload)) == 1


def test_nested_and_listed_url_fields_are_checked() -> None:
    row = _row(
        "de/guidance/n",
        metadata={
            "provenance": {"retrieved": {"download_url": "file:///tmp/a"}},
            "source_urls": ["https://ok.example/a", "file:///tmp/b"],
            "notes": ["file:///not/a/url/field"],
        },
    )
    payload = json.dumps({"items": [row]}).encode()
    assert local_file_url_fields(INVENTORY, payload) == [
        ("de/guidance/n", "metadata.provenance.retrieved.download_url"),
        ("de/guidance/n", "metadata.source_urls"),
    ]


def _locked_scope(repo: Path, scope: tuple[str, str, str], rows: list[dict]) -> None:
    from axiom_corpus.corpus.corpus_locks import lock_from_worktree, write_lock

    jurisdiction, document_class, version = scope
    base = repo / "data/corpus"
    files = {
        base / f"inventory/{jurisdiction}/{document_class}/{version}.json": json.dumps(
            {"items": rows}
        ),
        base / f"provisions/{jurisdiction}/{document_class}/{version}.jsonl": "\n".join(
            json.dumps(row) for row in rows
        )
        + "\n",
        base / f"coverage/{jurisdiction}/{document_class}/{version}.json": '{"complete": true}',
    }
    for path, text in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    write_lock(repo, lock_from_worktree(repo, scope))


def test_audit_lists_locked_scopes_with_local_file_urls(tmp_path: Path) -> None:
    from scripts.audit_local_file_urls import audit, main

    repo = tmp_path / "repo"
    leaky_scope = ("de", "guidance", "2026-09-14-leaky")
    _locked_scope(
        repo,
        leaky_scope,
        [
            _row("de/guidance/a", metadata={"download_url": "file:///Users/someone/a.pdf"}),
            _row("de/guidance/a/1", metadata={"download_url": "file:///Users/someone/a.pdf"}),
        ],
    )
    _locked_scope(
        repo,
        ("us-nj", "policy", "2026-09-13-body-only"),
        [_row("us-nj/policy/p", body="file:///C/Users/x.htm", source_url="https://x.gov/p")],
    )
    selectors = repo / "manifests/releases"
    selectors.mkdir(parents=True)
    (selectors / "de-rulespec-x.json").write_text(
        json.dumps(
            {
                "name": "de-rulespec-x",
                "scopes": [
                    dict(zip(("jurisdiction", "document_class", "version"), leaky_scope, strict=True))
                ],
            }
        )
    )

    report = audit(repo)
    assert report["scanned"] == 4
    assert report["unreadable"] == []
    (record,) = report["scopes"]
    assert record["scope"] == "de/guidance/2026-09-14-leaky"
    assert record["selectors"] == ["de-rulespec-x"]
    assert {path.split("/")[2]: d["rows"] for path, d in record["artifacts"].items()} == {
        "inventory": 2,
        "provisions": 2,
    }
    assert audit(repo, scope_prefixes=["us-nj"])["scopes"] == []
    assert main(["--repo", str(repo), "--scope", "us-nj"]) == 0
    assert main(["--repo", str(repo), "--release", str(selectors / "de-rulespec-x.json")]) == 1
    unreadable = audit(repo, reader=lambda entry: None)
    assert len(unreadable["unreadable"]) == 4


def _zip(member: str) -> bytes:
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(member, "<x/>")
    return buffer.getvalue()


# Content and file name from which each format is detected with no declared
# source_format and no HTTP content type (json is never detected).
_DETECTABLE = {
    "pdf": (b"%PDF-1.7\n", "doc"),
    "html": (b"<!doctype html><p>x</p>", "doc"),
    "javascript": (b"const toc = [];", "toc.js"),
    "csv": (b"a,b\n1,2\n", "table.csv"),
    "xls": (b"not a workbook", "table.xls"),
    "doc": (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1rest", "doc"),
    "docx": (_zip("word/document.xml"), "doc"),
    "xlsx": (_zip("xl/workbook.xml"), "doc"),
}


@pytest.mark.parametrize("source_format", sorted(_DETECTABLE))
def test_detected_format_is_stable_under_its_own_media_type(tmp_path, source_format) -> None:
    """The extract loop infers the format again after the copy is given a media type."""
    from axiom_corpus.corpus.documents import _infer_source_format

    content, name = _DETECTABLE[source_format]
    path = tmp_path / "copy.bin"
    path.write_bytes(content)
    source = OfficialDocumentSource(
        source_id="doc",
        jurisdiction="de",
        document_class="guidance",
        title="Doc",
        source_url=f"https://www.example.de/{name}",
        local_path=str(path),
    )
    downloaded = _download_document(source, session=_NoNetwork())  # type: ignore[arg-type]
    assert downloaded.content_type == _SOURCE_FORMAT_CONTENT_TYPES[source_format]
    assert _infer_source_format(source, downloaded) == source_format
