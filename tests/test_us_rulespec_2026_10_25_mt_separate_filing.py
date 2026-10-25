from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus.release_policy import WITHDRAWN_SCOPES_PATH, load_withdrawn_scopes
from axiom_corpus.corpus.releases import ReleaseManifest
from scripts.repro.us_rulespec_2026_10_25_mt_separate_filing import (
    ADDITIONS,
    BASE_RELEASE,
    RELEASE,
    build_release,
)

ROOT = Path(__file__).resolve().parents[1]
RELEASE_DIR = ROOT / "manifests/releases"
DATED = "2026-10-25-mt-separate-filing-dated-authority"

# Literal, so a change to the reproducer's constants cannot also change what is checked.
EXPECTED_ADDITIONS = {
    ("us-mt", "form", "2026-10-06-w6-income-tax-forms-mt"),
    ("us-mt", "regulation", DATED),
    ("us-mt", "statute", "2026-10-06-w6-income-tax-statute-mt-r2"),
    ("us-mt", "statute", DATED),
}
ARM_PATH = "us-mt/regulation/title-42/chapter-42-15/subchapter-42-15-5/rule-42-15-524--effective-2010-04-30"
MCA_PATH = "us-mt/statute/15-30-2602--mca-2021"


def _key(scope: dict[str, str]) -> tuple[str, str, str]:
    return (scope["jurisdiction"], scope["document_class"], scope["version"])


def _keys(release: str) -> list[tuple[str, str, str]]:
    payload = json.loads((RELEASE_DIR / f"{release}.json").read_text(encoding="utf-8"))
    return [_key(scope) for scope in payload["scopes"]]


def _lock(scope: dict[str, str]) -> Path:
    return (
        ROOT
        / ".axiom/corpus-locks"
        / scope["jurisdiction"]
        / scope["document_class"]
        / f"{scope['version']}.json"
    )


def _rows(key: tuple[str, str, str]) -> list[dict]:
    jurisdiction, document_class, version = key
    path = ROOT / "data/corpus/provisions" / jurisdiction / document_class / f"{version}.jsonl"
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _row(key: tuple[str, str, str], citation_path: str) -> dict:
    (row,) = [row for row in _rows(key) if row["citation_path"] == citation_path]
    return row


def test_reproducer_constants_are_the_expected_delta() -> None:
    assert {_key(scope) for scope in ADDITIONS} == EXPECTED_ADDITIONS


def test_reproducer_matches_committed_selector(tmp_path: Path) -> None:
    generated = build_release(release_dir=RELEASE_DIR, output_dir=tmp_path)
    assert generated.read_bytes() == (RELEASE_DIR / f"{RELEASE}.json").read_bytes()


def test_selector_is_the_base_plus_the_montana_scopes() -> None:
    base, release = _keys(BASE_RELEASE), _keys(RELEASE)
    assert set(release) == set(base) | EXPECTED_ADDITIONS
    assert not set(base) & EXPECTED_ADDITIONS
    assert len(release) == len(base) + 4 == 276
    assert release == sorted(release)


@pytest.mark.parametrize("scope", ADDITIONS, ids=lambda scope: "/".join(_key(scope)[1:]))
def test_each_added_scope_is_locked_and_not_withdrawn(scope: dict[str, str]) -> None:
    assert _lock(scope).is_file(), f"{_key(scope)} must be signed and locked"
    assert _key(scope) not in load_withdrawn_scopes(ROOT / WITHDRAWN_SCOPES_PATH)


def test_it_selects_no_withdrawn_scope_the_base_does_not() -> None:
    withdrawn = load_withdrawn_scopes(ROOT / WITHDRAWN_SCOPES_PATH)
    assert not {key for key in _keys(RELEASE) if key in withdrawn} - set(_keys(BASE_RELEASE))


KEPT_WITHDRAWN = {"us-me", "us-mi", "us-mn"}  # 2026-07-13 recovery scopes, until rulespec-us#1365


def test_every_withdrawn_scope_it_keeps_has_its_own_exception() -> None:
    """Allowances don't carry forward: each kept withdrawn scope needs an exception for this selector."""
    withdrawn = load_withdrawn_scopes(ROOT / WITHDRAWN_SCOPES_PATH)
    release = ReleaseManifest.load(RELEASE_DIR / f"{RELEASE}.json")
    kept = [key for key in _keys(RELEASE) if key in withdrawn]
    assert {key[0] for key in kept} == KEPT_WITHDRAWN
    for key in kept:
        allowance = withdrawn[key].allowance_for(release)
        assert allowance is not None and allowance.is_exception, key


def test_selector_loads_and_keeps_the_quality_profile() -> None:
    release = ReleaseManifest.load(RELEASE_DIR / f"{RELEASE}.json")
    base = json.loads((RELEASE_DIR / f"{BASE_RELEASE}.json").read_text(encoding="utf-8"))
    ours = json.loads((RELEASE_DIR / f"{RELEASE}.json").read_text(encoding="utf-8"))
    assert release.name == RELEASE
    assert ours["quality_profile"] == base["quality_profile"]


def test_montana_scopes_share_no_citation_path() -> None:
    """One release cannot hold two rows at one path (duplicate_release_citation). A path
    starts with its jurisdiction and class, so only the selected us-mt scopes can collide."""
    seen: dict[str, tuple[str, str, str]] = {}
    for key in _keys(RELEASE):
        if key[0] != "us-mt":
            continue
        for row in _rows(key):
            assert row["citation_path"] not in seen, (
                row["citation_path"],
                seen.get(row["citation_path"]),
                key,
            )
            seen[row["citation_path"]] = key
    assert {ARM_PATH, MCA_PATH} <= set(seen)


@pytest.mark.parametrize(
    ("key", "document_path", "canonical", "variant"),
    [
        (
            ("us-mt", "regulation", DATED),
            ARM_PATH,
            "us-mt/regulation/title-42/chapter-42-15/subchapter-42-15-5/rule-42-15-524",
            "effective-2010-04-30",
        ),
        (("us-mt", "statute", DATED), MCA_PATH, "us-mt/statute/15-30-2602", "mca-2021"),
    ],
)
def test_dated_rows_are_variants_of_the_plain_path(
    key: tuple[str, str, str], document_path: str, canonical: str, variant: str
) -> None:
    rows = _rows(key)
    assert {row["citation_path"] for row in rows} == {document_path, f"{document_path}/block-1"}
    for row in rows:
        assert row["metadata"]["variant"] == variant
        assert row["metadata"]["canonical_citation_path"] == canonical
        assert row["citation_path"].startswith(f"{canonical}--{variant}")


def test_arm_source_is_the_archived_capture() -> None:
    row = _row(("us-mt", "regulation", DATED), f"{ARM_PATH}/block-1")
    source = (ROOT / "data/corpus" / row["source_path"]).read_bytes()
    metadata = row["metadata"]
    assert hashlib.sha256(source).hexdigest() == metadata["archive_payload_sha256"]
    assert row["expression_date"] == metadata["effective_start"] == "2010-04-30"
    assert row["source_as_of"] == "2023-10-03"
    assert f"/{metadata['archive_timestamp']}id_/" in metadata["download_url"]


def test_dated_rows_hold_the_separate_filing_texts() -> None:
    arm = _row(("us-mt", "regulation", DATED), f"{ARM_PATH}/block-1")["body"]
    assert "If one spouse files separately and itemizes deductions, then both must do so." in arm
    assert (
        "if the spouses file a separate return on the same form, an itemized deduction not "
        "clearly attributable to one spouse may be divided as provided on the form;"
    ) in arm
    mca = _row(("us-mt", "statute", DATED), f"{MCA_PATH}/block-1")["body"]
    assert mca.startswith("15-30-2602 . (Temporary)")
    assert "may, at the taxpayer's option, file a joint return with the husband or wife" in mca


_SCOPE = st.fixed_dictionaries(
    {
        "document_class": st.sampled_from(["form", "manual", "regulation", "statute"]),
        "jurisdiction": st.sampled_from(["us", "us-az", "us-mt", "us-ny"]),
        "version": st.from_regex(r"20[0-9]{2}-[01][0-9]-[0-3][0-9]-[a-z]{1,8}", fullmatch=True),
    }
)


@settings(max_examples=200, deadline=None)
@given(
    scopes=st.lists(_SCOPE, max_size=25, unique_by=_key),
    preselected=st.sets(st.integers(min_value=0, max_value=len(ADDITIONS) - 1), max_size=4),
)
def test_build_release_adds_on_any_base(
    tmp_path_factory: pytest.TempPathFactory,
    scopes: list[dict[str, str]],
    preselected: set[int],
) -> None:
    """For any duplicate-free base that holds no addition: output = base + ADDITIONS, sorted,
    nothing dropped. A base that already holds an addition is refused."""
    scopes = [*scopes, *(dict(ADDITIONS[i]) for i in sorted(preselected))]
    release_dir = tmp_path_factory.mktemp("releases")
    base = {"description": "base", "name": BASE_RELEASE, "quality_profile": "q", "scopes": scopes}
    (release_dir / f"{BASE_RELEASE}.json").write_text(json.dumps(base), encoding="utf-8")
    if preselected:
        with pytest.raises(ValueError, match="already selects"):
            build_release(release_dir=release_dir)
        return
    output = json.loads(build_release(release_dir=release_dir).read_text(encoding="utf-8"))
    identities = [_key(scope) for scope in output["scopes"]]
    assert identities == sorted(identities)
    assert sorted(identities) == sorted([*map(_key, scopes), *map(_key, ADDITIONS)])
    assert output["name"] == RELEASE
    assert output["quality_profile"] == "q"
