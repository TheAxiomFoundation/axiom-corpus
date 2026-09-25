"""Streaming release validation reports exactly what full-record validation did.

Invariants, checked against the pre-streaming implementations on generated
corpus trees:

- ``validate_release`` returns an identical report (every issue, in order,
  with the same counts, truncation and ``ok``), or raises the same exception
  type and message, for any mix of valid and faulty scopes: missing, invalid
  and non-canonical inventories; malformed, duplicate, parentless and
  misattributed provisions; unreadable, uninventoried and tampered sources;
  missing and invalid dates; incomplete or miscounted coverage; unsectioned
  document bodies; and citation paths shared across scopes.
- ``_validate_signed_source_references`` accepts exactly the scopes the
  whole-file check accepted and otherwise raises the same first error.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from collections.abc import Callable
from pathlib import Path

from hypothesis import HealthCheck, event, given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus.release_quality import validate_release
from axiom_corpus.corpus.releases import (
    COMPLETE_EXPRESSION_DATES_PROFILE,
    ReleaseManifest,
    ReleaseScope,
)
from axiom_corpus.release.manifest import _validate_signed_source_references
from tests._reference_publication import (
    _reference_validate_release,
    _reference_validate_signed_source_references,
)

_SETTINGS = settings(
    max_examples=150,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)

_FILLER = "Taxable income from line 26000 of your return. " * 10
_SECTIONED_BODY = f"intro\nStep 1 - Income\n{_FILLER}\nStep 2 - Tax\n{_FILLER}\n"
_VERSIONS = ("2026-05-01", "2026-06-01")


def _outcome(call: Callable[[], object]) -> tuple[str, object]:
    try:
        return ("ok", call())
    except Exception as exc:
        return ("raised", (type(exc), str(exc)))


def _source_name(index: int) -> str:
    return f"title-{index}.xml"


@st.composite
def _scope_tree(draw: st.DrawFn, scope: tuple[str, str, str], *, valid: bool) -> dict:
    """Describe one scope's artifacts; ``valid`` keeps every check passing."""
    jurisdiction, document_class, version = scope
    prefix = f"sources/{jurisdiction}/{document_class}/{version}"
    sources = {
        _source_name(index): f"<title n='{index}'/>".encode() * draw(st.integers(1, 3))
        for index in range(draw(st.integers(min_value=1, max_value=3)))
    }
    paths = sorted(
        set(
            draw(
                st.lists(
                    st.sampled_from(["1", "1/a", "1/b", "2", "2/a", "3", "3/x/y"]),
                    min_size=1,
                    max_size=6,
                )
            )
        )
    )
    citation_root = f"{jurisdiction}/{document_class}"
    records: list[dict[str, object]] = []
    items: list[dict[str, object]] = []
    for relative in paths:
        citation_path = f"{citation_root}/{relative}"
        parent = citation_path.rsplit("/", 1)[0] if "/" in relative else None
        source = draw(st.sampled_from(sorted(sources)))
        record: dict[str, object] = {
            "jurisdiction": jurisdiction,
            "document_class": document_class,
            "citation_path": citation_path,
            "version": version,
            "body": draw(st.sampled_from(["Text.", "  Text with padding ", "\u2014 dash"])),
            "heading": draw(st.sampled_from([None, "Heading"])),
            "source_path": f"{prefix}/{source}",
            "source_as_of": version,
            "expression_date": version,
        }
        if parent is not None and parent.split("/", 2)[-1] in paths:
            record["parent_citation_path"] = parent
        item: dict[str, object] = {
            "citation_path": citation_path,
            "source_path": f"{prefix}/{source}",
            "sha256": hashlib.sha256(sources[source]).hexdigest(),
        }
        if not valid:
            fault = draw(st.integers(min_value=0, max_value=24))
            if fault == 0:
                record["parent_citation_path"] = f"{citation_root}/missing"
            elif fault == 1:
                record["jurisdiction"] = "zz"
            elif fault == 2:
                record["version"] = "other"
            elif fault == 3:
                record["body"] = "   "
                record["heading"] = draw(st.sampled_from([None, "", "  ", ["list"]]))
            elif fault == 4:
                record["expression_date"] = draw(st.sampled_from([None, "", "2026-13-40", 20260501]))
            elif fault == 5:
                record["source_as_of"] = draw(st.sampled_from([None, "yesterday"]))
            elif fault == 6:
                record["source_path"] = draw(
                    st.sampled_from(
                        [None, "", f"{prefix}/absent.xml", "/etc/passwd", f"{prefix}/../x", 7]
                    )
                )
            elif fault == 7:
                item["sha256"] = draw(st.sampled_from([None, "", "0" * 64]))
            elif fault == 8:
                item["source_path"] = draw(st.sampled_from([None, f"{prefix}/absent.xml", "x/y"]))
            elif fault == 9:
                record["kind"] = "document"
                record["body"] = _SECTIONED_BODY
            elif fault == 10:
                record["id"] = draw(st.sampled_from(["dup-id", ["unhashable"]]))
            elif fault == 11:
                record["parent_id"] = "not-the-parent"
                record["id"] = "explicit"
            elif fault == 12:
                items.append(dict(item))  # duplicate inventory citation
            elif fault == 13:
                continue  # provision without inventory item: coverage extra
            elif fault == 14:
                records.append(record)
                continue  # inventory item without provision: coverage missing
            elif fault == 15:
                records.append(dict(record))  # duplicate provision citation
        records.append(record)
        items.append(item)
    coverage = {
        "complete": True,
        "source_count": len(items),
        "provision_count": len(records),
        "matched_count": len({r["citation_path"] for r in records} & {i["citation_path"] for i in items}),
        "missing_from_provisions": [],
        "extra_provisions": [],
    }
    inventory_text = json.dumps({"items": items}, indent=2, sort_keys=True) + "\n"
    provisions_text = "".join(json.dumps(record, sort_keys=True) + "\n" for record in records)
    coverage_text = json.dumps(coverage, indent=2, sort_keys=True) + "\n"
    if not valid:
        artifact_fault = draw(st.integers(min_value=0, max_value=14))
        if artifact_fault == 0:
            inventory_text = None
        elif artifact_fault == 1:
            provisions_text = None
        elif artifact_fault == 2:
            coverage_text = None
        elif artifact_fault == 3:
            inventory_text = inventory_text[: len(inventory_text) // 2]
        elif artifact_fault == 4:
            provisions_text = provisions_text + "{broken\n"
        elif artifact_fault == 5:
            coverage_text = "[1, 2]"
        elif artifact_fault == 6:
            coverage_text = "{not json"
        elif artifact_fault == 7:
            coverage = {**coverage, "complete": False, "source_count": 99}
            coverage_text = json.dumps(coverage)
        elif artifact_fault == 8:
            inventory_text = json.dumps([{"citation_path": "x"}])
        elif artifact_fault == 9:
            provisions_text = "[1]\n" + provisions_text
    return {
        "sources": sources,
        "inventory": inventory_text,
        "provisions": provisions_text,
        "coverage": coverage_text,
    }


def _write_scope(root: Path, scope: tuple[str, str, str], tree: dict) -> None:
    jurisdiction, document_class, version = scope
    for name, payload in tree["sources"].items():
        path = root / "sources" / jurisdiction / document_class / version / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    for kind, suffix in (("inventory", "json"), ("provisions", "jsonl"), ("coverage", "json")):
        text = tree[kind]
        if text is None:
            continue
        path = root / kind / jurisdiction / document_class / f"{version}.{suffix}"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


@st.composite
def _release(draw: st.DrawFn) -> tuple[ReleaseManifest, dict]:
    valid = draw(st.booleans())
    scope_keys = draw(
        st.lists(
            st.tuples(
                st.sampled_from(["us", "ca"]),
                st.sampled_from(["statute", "regulation"]),
                st.sampled_from(_VERSIONS),
            ),
            min_size=1,
            max_size=3,
            unique=True,
        )
    )
    trees = {scope: draw(_scope_tree(scope, valid=valid)) for scope in scope_keys}
    release = ReleaseManifest(
        name="us-streaming-2026-09-25",
        scopes=tuple(ReleaseScope(*scope) for scope in scope_keys),
        quality_profile=draw(st.sampled_from([None, COMPLETE_EXPRESSION_DATES_PROFILE])),
    )
    return release, trees


@_SETTINGS
@given(
    release_trees=_release(),
    max_issues=st.sampled_from([1, 3, 200]),
    strict_warnings=st.booleans(),
)
def test_validate_release_matches_full_record_validation(
    release_trees: tuple[ReleaseManifest, dict],
    max_issues: int,
    strict_warnings: bool,
) -> None:
    release, trees = release_trees
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        for scope, tree in trees.items():
            _write_scope(root, scope, tree)

        def run(validator: Callable[..., object]) -> tuple[str, object]:
            outcome = _outcome(
                lambda: validator(
                    root, release, max_issues=max_issues, strict_warnings=strict_warnings
                )
            )
            if outcome[0] == "ok":
                return ("ok", outcome[1].to_mapping())  # type: ignore[attr-defined]
            return outcome

        expected = run(_reference_validate_release)
        actual = run(validate_release)
    if expected[0] == "ok":
        mapping = expected[1]
        event("report ok" if mapping["ok"] else "report errors")  # type: ignore[index]
        for issue in mapping["issues"]:  # type: ignore[index]
            event(f"issue {issue['code']}")
    else:
        event(f"raised {expected[1][0].__name__}")  # type: ignore[index]
    assert actual == expected


@_SETTINGS
@given(data=st.data())
def test_signed_source_references_match_whole_file_check(data: st.DataObject) -> None:
    scope = ("us", "statute", "2026-05-01")
    tree = data.draw(_scope_tree(scope, valid=data.draw(st.booleans())))
    with tempfile.TemporaryDirectory() as directory:
        repo_root = Path(directory)
        base = repo_root / "data" / "corpus"
        _write_scope(base, scope, tree)
        entries: list[dict[str, object]] = []
        for kind, suffix in (("inventory", "json"), ("provisions", "jsonl")):
            if tree[kind] is not None:
                entries.append(
                    {
                        "artifact_class": kind,
                        "path": f"data/corpus/{kind}/us/statute/2026-05-01.{suffix}",
                    }
                )
        for name, payload in tree["sources"].items():
            if data.draw(st.integers(min_value=0, max_value=6)) == 0:
                continue  # an unsigned source
            digest = hashlib.sha256(payload).hexdigest()
            if data.draw(st.integers(min_value=0, max_value=6)) == 0:
                digest = "0" * 64
            entries.append(
                {
                    "artifact_class": "sources",
                    "path": f"data/corpus/sources/us/statute/2026-05-01/{name}",
                    "sha256": digest,
                }
            )

        def run(check: Callable[..., None]) -> tuple[str, object]:
            return _outcome(
                lambda: check(repo_root, base="data/corpus", scope_key=scope, entries=entries)
            )

        expected = run(_reference_validate_signed_source_references)
        actual = run(_validate_signed_source_references)
    event("accepted" if expected[0] == "ok" else f"raised {str(expected[1][1])[:48]}")  # type: ignore[index]
    assert actual == expected
