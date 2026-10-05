"""The streaming artifact readers agree exactly with the whole-file readers.

Invariant: for every file, ``load_provisions`` / ``iter_provisions`` return the
records ``_reference_load_provisions`` returns, or raise the same exception type
with the same message, and ``load_source_inventory_references`` returns the
gate fields of the items ``_reference_load_source_inventory`` returns, or raises
what it raises. The generated files are mostly valid artifacts with unicode,
line-separator, blank-line and CRLF variation, plus malformed rows, non-object
rows, missing keys, non-canonical inventory shapes, truncation and bytes that
are not UTF-8.
"""

from __future__ import annotations

import json
import tempfile
from collections.abc import Callable
from pathlib import Path
from unittest import mock

import pytest
from hypothesis import HealthCheck, event, given, settings
from hypothesis import strategies as st

import axiom_corpus.corpus.io as corpus_io
from axiom_corpus.corpus.io import (
    SourceInventoryReference,
    iter_provisions,
    load_provisions,
    load_source_inventory_references,
)
from tests._reference_publication import (
    _reference_load_provisions,
    _reference_load_source_inventory,
)

_SETTINGS = settings(
    max_examples=200,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)

# Text that exercises every line-boundary rule str.splitlines applies,
# JSON escapes, surrogate escapes, and multi-byte UTF-8.
_TRICKY_TEXT = st.text(
    alphabet=st.sampled_from(
        list("abc /\\\"'{}[],:0123456789")
        + [
            "\u2028",
            "\u2029",
            "\x85",
            "\x0b",
            "\x0c",
            "\x1c",
            "\t",
            "\xe9",
            "\u4e2d",
            "\U0001f600",
            "\xa0",
        ]
    ),
    max_size=12,
)
_JSON_SCALAR = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-(2**40), max_value=2**40),
    st.floats(allow_nan=False, allow_infinity=False),
    _TRICKY_TEXT,
)
_JSON_VALUE = st.recursive(
    _JSON_SCALAR,
    lambda children: st.lists(children, max_size=3)
    | st.dictionaries(_TRICKY_TEXT, children, max_size=3),
    max_leaves=6,
)


_VALID_TEXT = st.text(
    alphabet=st.sampled_from(
        list("abc /-.:0123456789") + ["\u2028", "\x85", "\xe9", "\u4e2d", "\U0001f600", "\ud800"]
    ),
    max_size=12,
)


@st.composite
def _provision_mapping(draw: st.DrawFn, *, valid: bool) -> dict[str, object]:
    row: dict[str, object] = {}
    if valid:
        row["jurisdiction"] = draw(st.sampled_from(["us", "ca"]))
        row["document_class"] = draw(st.sampled_from(["statute", "regulation"]))
        row["citation_path"] = "us/statute/" + draw(_VALID_TEXT)
        optional = {
            "body": st.one_of(st.none(), _VALID_TEXT),
            "heading": st.one_of(st.none(), _VALID_TEXT),
            "id": st.one_of(st.none(), _VALID_TEXT),
            "version": st.sampled_from(["2026-05-01", "v1"]),
            "source_path": st.one_of(st.none(), _VALID_TEXT),
            "expression_date": st.sampled_from(["2026-05-01", "2026-5-1"]),
            "identifiers": st.dictionaries(_VALID_TEXT, _VALID_TEXT, max_size=2),
            "metadata": st.dictionaries(_VALID_TEXT, _VALID_TEXT, max_size=2),
            "ordinal": st.integers(min_value=-5, max_value=2**40),
        }
        for key, values in optional.items():
            if draw(st.booleans()):
                row[key] = draw(values)
        return row
    for key in ("jurisdiction", "document_class", "citation_path"):
        # Occasionally omit a required key so from_mapping raises KeyError.
        if draw(st.integers(min_value=0, max_value=30)) != 0:
            row[key] = draw(st.one_of(_TRICKY_TEXT, _JSON_SCALAR))
    for key in (
        "body",
        "heading",
        "id",
        "version",
        "source_path",
        "parent_citation_path",
        "expression_date",
        "identifiers",
        "metadata",
        "ordinal",
        "language",
    ):
        if draw(st.booleans()):
            row[key] = draw(_JSON_VALUE)
    return row


_BAD_LINES = st.sampled_from(
    [
        "{",
        "[1, 2]",
        "null",
        '"row"',
        "7",
        "{} {}",
        '{"jurisdiction": "us"',
        "\ufeff{}",
        '{"a": NaN}',
        "   ",
        "",
        "\x0c",
    ]
)
_LINE_ENDINGS = st.sampled_from(["\n", "\r\n", "\r", "\u2028", "\x85", "\n\n", " \n"])


@st.composite
def _provisions_bytes(draw: st.DrawFn) -> bytes:
    # Half the files are valid artifacts (escaped JSON rows, any line
    # boundary, blank lines); the rest carry malformed rows, raw separators
    # inside strings, and bytes that are not UTF-8.
    valid = draw(st.booleans())
    parts: list[str] = []
    for _ in range(draw(st.integers(min_value=0, max_value=6))):
        if not valid and draw(st.integers(min_value=0, max_value=5)) == 0:
            line = draw(_BAD_LINES)
        else:
            line = json.dumps(
                draw(_provision_mapping(valid=valid)),
                ensure_ascii=valid or draw(st.booleans()),
            )
        parts.append(line + draw(_LINE_ENDINGS))
    if parts and draw(st.booleans()):
        parts[-1] = parts[-1].rstrip("\n")
    data = "".join(parts).encode("utf-8", "surrogatepass")
    if not valid and data and draw(st.integers(min_value=0, max_value=4)) == 0:
        # Bytes that are not UTF-8, or a multi-byte sequence cut short.
        at = draw(st.integers(min_value=0, max_value=len(data)))
        data = (
            data[:at]
            + draw(st.sampled_from([b"\xff", b"\xc3", b"\xe4\xb8", b"\xed\xa0\x80"]))
            + data[at:]
        )
    return data


def _outcome(call: Callable[[], object]) -> tuple[str, object]:
    try:
        return ("ok", call())
    except Exception as exc:
        return ("raised", (type(exc), str(exc)))


def _labelled(outcome: tuple[str, object]) -> tuple[str, object]:
    # Recorded for --hypothesis-show-statistics: generated inputs must reach
    # both successful results and each kind of failure.
    if outcome[0] == "ok":
        event("ok")
    else:
        error_type, message = outcome[1]  # type: ignore[misc]
        event(f"raised {error_type.__name__}: {str(message)[:40]}")
    return outcome


def _write(directory: str, name: str, data: bytes) -> Path:
    path = Path(directory) / name
    path.write_bytes(data)
    return path


@_SETTINGS
@given(data=_provisions_bytes())
def test_load_provisions_matches_whole_file_reader(data: bytes) -> None:
    with tempfile.TemporaryDirectory() as directory:
        path = _write(directory, "provisions.jsonl", data)
        expected = _labelled(_outcome(lambda: _reference_load_provisions(path)))
        assert _outcome(lambda: load_provisions(path)) == expected
        assert _outcome(lambda: tuple(iter_provisions(path))) == expected


def test_iter_provisions_yields_lazily_and_reports_decode_errors_first(tmp_path: Path) -> None:
    # Enough valid rows that the malformed row and the undecodable byte sit
    # well past the first chunk the text layer decodes.
    good = json.dumps({"jurisdiction": "us", "document_class": "statute", "citation_path": "a"})
    path = tmp_path / "provisions.jsonl"
    path.write_bytes((good + "\n").encode() * 2000 + b"{not json}\n" + b"\xff\n")

    reference = _outcome(lambda: _reference_load_provisions(path))
    assert reference[0] == "raised" and reference[1][0] is UnicodeDecodeError
    stream = iter_provisions(path)
    assert next(stream).citation_path == "a"
    with pytest.raises(UnicodeDecodeError) as excinfo:
        for _ in stream:
            pass
    # The byte position is the whole file's, not a decode chunk's.
    assert str(excinfo.value) == reference[1][1]


def test_iter_provisions_of_a_missing_file_is_empty(tmp_path: Path) -> None:
    assert tuple(iter_provisions(tmp_path / "absent.jsonl")) == ()
    assert _reference_load_provisions(tmp_path / "absent.jsonl") == ()


def test_iter_provisions_raises_if_the_file_changes_to_decodable_mid_read(tmp_path: Path) -> None:
    path = tmp_path / "provisions.jsonl"
    path.write_bytes(b"\xff\n")
    real_read_text = Path.read_text

    def read_after_repair(self: Path, *args: object, **kwargs: object) -> str:
        self.write_bytes(b"")
        return real_read_text(self, *args, **kwargs)  # type: ignore[arg-type]

    with (
        mock.patch.object(Path, "read_text", read_after_repair),
        pytest.raises(OSError, match="changed while it was read"),
    ):
        tuple(iter_provisions(path))


_INVENTORY_ITEM = st.fixed_dictionaries(
    {},
    optional={
        "citation_path": st.one_of(_TRICKY_TEXT, _JSON_SCALAR),
        "source_path": _JSON_VALUE,
        "sha256": _JSON_VALUE,
        "source_url": _JSON_VALUE,
        "source_format": _JSON_VALUE,
        "metadata": _JSON_VALUE,
    },
)


_VALID_INVENTORY_ITEM = st.fixed_dictionaries(
    {"citation_path": _VALID_TEXT},
    optional={
        "source_path": _VALID_TEXT,
        "sha256": st.sampled_from(["a" * 64, "b" * 64]),
        "source_url": _VALID_TEXT,
        "source_format": st.sampled_from(["xml", "html"]),
        "metadata": st.dictionaries(_VALID_TEXT, _VALID_TEXT, max_size=2),
    },
)


@st.composite
def _inventory_bytes(draw: st.DrawFn) -> bytes:
    if draw(st.booleans()):
        # A valid inventory as the writer shapes it, with formatting variation.
        text = json.dumps(
            {"items": draw(st.lists(_VALID_INVENTORY_ITEM, max_size=6))},
            indent=draw(st.sampled_from([None, 0, 2, "\t"])),
            sort_keys=draw(st.booleans()),
            ensure_ascii=draw(st.booleans()),
        )
        text = draw(st.sampled_from(["", " ", "\n", "\r\n"])) + text
        return (text + draw(st.sampled_from(["", "\n", " \r\n"]))).encode("utf-8", "surrogatepass")
    items = draw(st.lists(st.one_of(_INVENTORY_ITEM, _INVENTORY_ITEM, _JSON_VALUE), max_size=5))
    shape = draw(
        st.sampled_from(
            [
                "canonical",
                "canonical",
                "list",
                "other-key-first",
                "other-key-last",
                "duplicate-items",
                "no-items",
                "items-not-list",
                "scalar",
            ]
        )
    )
    document: object
    if shape == "canonical":
        document = {"items": items}
    elif shape == "list":
        document = items
    elif shape == "other-key-first":
        document = {"a": draw(_JSON_VALUE), "items": items}
    elif shape == "other-key-last":
        document = {"items": items, "z": draw(_JSON_VALUE)}
    elif shape == "no-items":
        document = {"other": items}
    elif shape == "items-not-list":
        document = {"items": draw(_JSON_VALUE)}
    else:
        document = draw(_JSON_VALUE)
    text = json.dumps(
        document,
        indent=draw(st.sampled_from([None, 0, 1, 2, "\t"])),
        sort_keys=draw(st.booleans()),
        ensure_ascii=draw(st.booleans()),
    )
    if shape == "duplicate-items":
        text = '{"items": [], "items": ' + json.dumps(items) + "}"
    text = (
        draw(st.sampled_from(["", " ", "\n", "\r\n"]))
        + text
        + draw(st.sampled_from(["", "\n", " \r\n", "\n{}", ",", "]", "\ufeff"]))
    )
    if draw(st.integers(min_value=0, max_value=8)) == 0:
        text = "\ufeff" + text
    data = text.encode("utf-8", "surrogatepass")
    mutation = draw(st.integers(min_value=0, max_value=10))
    if data and mutation == 0:
        data = data[: draw(st.integers(min_value=0, max_value=len(data)))]
    elif data and mutation == 1:
        at = draw(st.integers(min_value=0, max_value=len(data)))
        data = data[:at] + draw(st.sampled_from([b"\xff", b"\xc3", b"}", b","])) + data[at:]
    return data


def _reference_inventory_references(path: Path) -> tuple[SourceInventoryReference, ...]:
    return tuple(
        SourceInventoryReference(item.citation_path, item.source_path, item.sha256)
        for item in _reference_load_source_inventory(path)
    )


@_SETTINGS
@given(data=_inventory_bytes(), read_chars=st.sampled_from([1, 2, 3, 7, 64, 1024 * 1024]))
def test_inventory_references_match_whole_file_reader(data: bytes, read_chars: int) -> None:
    with tempfile.TemporaryDirectory() as directory:
        path = _write(directory, "inventory.json", data)
        expected = _labelled(_outcome(lambda: _reference_inventory_references(path)))
        with mock.patch.object(corpus_io, "_INVENTORY_READ_CHARS", read_chars):
            assert _outcome(lambda: load_source_inventory_references(path)) == expected


@_SETTINGS
@given(
    items=st.lists(_INVENTORY_ITEM, max_size=8),
    read_chars=st.sampled_from([1, 5, 17, 1024 * 1024]),
)
def test_canonical_inventories_stream_without_the_whole_file_reader(
    items: list[dict[str, object]], read_chars: int
) -> None:
    # The writer's own shape must take the streaming path: the whole-file
    # reader is never called, yet the result or error is the reference's.
    with tempfile.TemporaryDirectory() as directory:
        path = _write(
            directory,
            "inventory.json",
            (json.dumps({"items": items}, indent=2, sort_keys=True) + "\n").encode(),
        )
        expected = _outcome(lambda: _reference_inventory_references(path))
        with (
            mock.patch.object(corpus_io, "_INVENTORY_READ_CHARS", read_chars),
            mock.patch.object(
                corpus_io,
                "load_source_inventory",
                side_effect=AssertionError("canonical inventory was read whole"),
            ),
        ):
            assert _outcome(lambda: load_source_inventory_references(path)) == expected


def test_inventory_references_share_repeated_source_strings(tmp_path: Path) -> None:
    path = tmp_path / "inventory.json"
    items = [
        {"citation_path": f"us/statute/1/{n}", "source_path": "sources/a.xml", "sha256": "f" * 64}
        for n in range(3)
    ]
    path.write_text(json.dumps({"items": items}, indent=2))

    references = load_source_inventory_references(path)

    assert [ref.citation_path for ref in references] == [item["citation_path"] for item in items]
    assert len({id(ref.source_path) for ref in references}) == 1
    assert len({id(ref.sha256) for ref in references}) == 1
