from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from scripts.repro.us_rulespec_2026_10_09_az_des_ece_dated import (
    ADDITION,
    BASE_RELEASE,
    RELEASE,
    build_release,
)

ROOT = Path(__file__).resolve().parents[1]
RELEASE_DIR = ROOT / "manifests/releases"
PROVISIONS = ROOT / "data/corpus/provisions"
# rulespec-us pins this release today (.axiom/toolchain.toml); the new release
# must keep every scope it selects so a re-pin changes nothing else.
RULESPEC_US_PIN = "us-rulespec-2026-08-08-obbb-alien-snap"
FAA5_SCOPE = {
    "document_class": "manual",
    "jurisdiction": "us-az",
    "version": "2026-07-17-faa5-recovery",
}
NOTICE = "us-az/manual/des/archived-policy/2026-03-23-whats-changed"
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _identities(release: str) -> set[tuple[str, str, str]]:
    payload = json.loads((RELEASE_DIR / f"{release}.json").read_text(encoding="utf-8"))
    return {
        (scope["jurisdiction"], scope["document_class"], scope["version"])
        for scope in payload["scopes"]
    }


def _identity(scope: dict[str, str]) -> tuple[str, str, str]:
    return (scope["jurisdiction"], scope["document_class"], scope["version"])


def _rows(scope: dict[str, str]) -> list[dict[str, Any]]:
    path = (
        PROVISIONS / scope["jurisdiction"] / scope["document_class"] / f"{scope['version']}.jsonl"
    )
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_reproducer_matches_committed_selector(tmp_path: Path) -> None:
    generated = build_release(release_dir=RELEASE_DIR, output_dir=tmp_path)
    assert generated.read_bytes() == (RELEASE_DIR / f"{RELEASE}.json").read_bytes()


def test_selector_preserves_base_and_adds_only_the_notice_scope() -> None:
    base = _identities(BASE_RELEASE)
    release = _identities(RELEASE)

    assert release == base | {_identity(ADDITION)}
    assert len(release) == len(base) + 1


def test_selector_is_a_strict_superset_of_the_rulespec_us_pin() -> None:
    pin = _identities(RULESPEC_US_PIN)
    release = _identities(RELEASE)

    assert pin < release
    assert release - pin == {
        ("us", "guidance", "2026-09-24-snap-fy2027-cola"),
        _identity(ADDITION),
    }


def test_notice_scope_has_unique_noncolliding_citation_paths() -> None:
    paths = [row["citation_path"] for row in _rows(ADDITION)]

    assert paths == [NOTICE, f"{NOTICE}/document-1"]

    base = json.loads((RELEASE_DIR / f"{BASE_RELEASE}.json").read_text(encoding="utf-8"))
    predecessor_paths: set[str] = set()
    for scope in base["scopes"]:
        predecessor_paths.update(row["citation_path"] for row in _rows(scope))

    assert predecessor_paths.isdisjoint(paths)


def test_notice_rows_amend_faa5_pages_that_the_release_carries() -> None:
    """Every amendment target names a document the release actually serves.

    axiom-encode attaches an amendment row to a target when a bare-path value
    under ``amends``/``amendment_targets`` starts with the target's document path,
    and only within the pinned release's same (jurisdiction, document_class).
    """
    faa5_paths = {row["citation_path"] for row in _rows(FAA5_SCOPE)}
    rows = _rows(ADDITION)

    for row in rows:
        assert (row["jurisdiction"], row["document_class"]) == ("us-az", "manual")
        metadata = row["metadata"]
        assert metadata["document_type"] == "policy change notice (amendment)"
        assert metadata["amends"] == [
            "us-az/manual/des/faa5/na-categorical-eligibility",
            "us-az/manual/des/faa5/na-eligibility-and-benefit-determination",
        ]
        targets = [*metadata["amends"], *metadata["amendment_targets"]]
        assert targets
        for target in targets:
            assert " " not in target
            assert target in faa5_paths
        assert row["expression_date"] == "2026-03-23"
        assert metadata["effective_start"] == "2026-03-01"
        assert ISO_DATE.match(row["source_as_of"])

    (body_row,) = [row for row in rows if row.get("body")]
    body = body_row["body"]
    assert len(body) <= 12_000, "axiom-encode omits amendment bodies over 12,000 characters"
    assert "EFFECTIVE DATE: For the benefit month of 03/2026 and ongoing" in body
    assert "has changed from 185% of the FPL to 200% of the FPL" in body


_SCOPE = st.fixed_dictionaries(
    {
        "document_class": st.sampled_from(["guidance", "manual", "statute", "regulation"]),
        "jurisdiction": st.sampled_from(["us", "us-az", "us-ca", "us-ny"]),
        "version": st.from_regex(r"20[0-9]{2}-[01][0-9]-[0-3][0-9]-[a-z]{1,8}", fullmatch=True),
    }
)


# Each example writes a selector to disk; I/O time under load is not a property.
@settings(max_examples=200, deadline=None)
@given(
    scopes=st.lists(_SCOPE, max_size=25, unique_by=_identity),
    with_addition=st.booleans(),
)
def test_build_release_adds_exactly_the_notice_scope_to_any_base(
    tmp_path_factory: pytest.TempPathFactory,
    scopes: list[dict[str, str]],
    with_addition: bool,
) -> None:
    """For every duplicate-free base: output = base + ADDITION, sorted, nothing dropped.

    A base that already holds the notice scope is refused rather than silently kept.
    """
    if with_addition:
        scopes = [*scopes, dict(ADDITION)]
    release_dir = tmp_path_factory.mktemp("releases")
    base = {"description": "base", "name": BASE_RELEASE, "quality_profile": "q", "scopes": scopes}
    (release_dir / f"{BASE_RELEASE}.json").write_text(json.dumps(base), encoding="utf-8")

    if ADDITION in scopes:
        with pytest.raises(ValueError):
            build_release(release_dir=release_dir)
        return

    output = json.loads(build_release(release_dir=release_dir).read_text(encoding="utf-8"))
    identities = [_identity(scope) for scope in output["scopes"]]

    assert identities == sorted(identities)
    assert sorted(identities) == sorted([*map(_identity, scopes), _identity(ADDITION)])
    assert output["name"] == RELEASE
    assert output["quality_profile"] == "q"
