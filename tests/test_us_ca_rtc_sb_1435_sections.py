"""Committed-artifact checks for the SB 1435 text of Cal. R&TC 17024.5 and 17052."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from axiom_corpus.corpus.release_quality import validate_release
from axiom_corpus.corpus.releases import ReleaseManifest, ReleaseScope

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = REPO_ROOT / "data/corpus"
VERSION = "2026-09-23-ca-rtc-sb-1435-us-ca-sections-rtc-17024.5-rtc-17052"
CHAPTER_VERSION = "2026-09-14-income-tax-chapter-us-ca-sections-4e26e6efabc3f0c7"
FTB_3514_VERSION = "2026-09-23-ca-2025-ftb-3514"
SECTIONS = ("17024.5", "17052")
LEGINFO_URL = (
    "https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml"
    "?lawCode=RTC&sectionNum={section}"
)
SB_1435_HISTORY = (
    "(Amended by Stats. 2026, Ch. 236, Sec. {sec}. (SB 1435) Effective September 14, "
    "2026. Applicable to taxable years beginning on or after January 1, 2025, provided "
    "in Section 46 of Stats. 2026, Ch. 236.)"
)
_PARAGRAPH_RE = re.compile(r"^\((\d+)\) ")


def _records(version: str) -> dict[str, dict[str, object]]:
    path = CORPUS_ROOT / f"provisions/us-ca/statute/{version}.jsonl"
    records = [json.loads(line) for line in path.read_text().splitlines()]
    return {str(record["citation_path"]): record for record in records}


def _body(version: str, section: str) -> str:
    body = _records(version)[f"us-ca/statute/rtc/{section}"]["body"]
    assert isinstance(body, str)
    return body


def test_sb_1435_sections_retain_official_leginfo_bytes() -> None:
    inventory = json.loads((CORPUS_ROOT / f"inventory/us-ca/statute/{VERSION}.json").read_text())
    items = {item["citation_path"]: item for item in inventory["items"]}
    assert sorted(items) == [f"us-ca/statute/rtc/{section}" for section in SECTIONS]
    for section in SECTIONS:
        item = items[f"us-ca/statute/rtc/{section}"]
        assert item["source_url"] == LEGINFO_URL.format(section=section)
        source = CORPUS_ROOT / item["source_path"]
        assert source.name == f"RTC-{section}.html"
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        assert digest == item["sha256"] == item["metadata"]["content_sha256"]


def test_sb_1435_sections_coverage_is_complete_and_self_contained() -> None:
    coverage = json.loads((CORPUS_ROOT / f"coverage/us-ca/statute/{VERSION}.json").read_text())
    assert coverage["complete"] is True
    assert coverage["matched_count"] == coverage["source_count"] == 2
    assert coverage["provision_count"] == 2
    for record in _records(VERSION).values():
        assert record["version"] == VERSION
        assert record["source_as_of"] == record["expression_date"] == "2026-09-23"
        assert record.get("parent_citation_path") is None
        assert record.get("parent_id") is None
        metadata = record["metadata"]
        assert isinstance(metadata, dict)
        assert metadata["detached_parent_citation_path"] == "us-ca/statute/rtc"
        assert metadata["self_contained_root"] is True


def test_sb_1435_sections_carry_the_amended_text() -> None:
    records = _records(VERSION)
    for sec, section in enumerate(SECTIONS, start=1):
        metadata = records[f"us-ca/statute/rtc/{section}"]["metadata"]
        assert isinstance(metadata, dict)
        assert metadata["history"] == SB_1435_HISTORY.format(sec=sec)
        assert _body(VERSION, section).endswith(SB_1435_HISTORY.format(sec=sec))

    eitc = _body(VERSION, "17052")
    assert (
        "(d) Section 32(i)(1) of the Internal Revenue Code is modified by substituting "
        "“$3,400” for the amount prescribed in that provision."
    ) in eitc
    assert "(j) (1) In accordance with Section 41, the purpose" in eitc
    assert "the Senate Committee on Revenue and Taxation, the Assembly Committee" in eitc

    conformity = _body(VERSION, "17024.5")
    assert "A foreign investment company" not in conformity
    assert (
        "(5) A foreign trust, as defined in Section 679 of the Internal Revenue Code."
    ) in conformity
    assert (
        "(11) Deduction for personal exemptions, as provided in Section 151 of the "
        "Internal Revenue Code."
    ) in conformity


def _paragraph_number(line: str) -> int:
    match = _PARAGRAPH_RE.match(line)
    assert match is not None, line
    return int(match.group(1))


def test_sb_1435_sections_differ_from_the_chapter_scope_only_as_amended() -> None:
    for sec, section in enumerate(SECTIONS, start=1):
        old = _body(CHAPTER_VERSION, section).splitlines()
        new = _body(VERSION, section).splitlines()
        assert "Stats. 2026, Ch. 236" not in old[-1]
        assert new[-1] == SB_1435_HISTORY.format(sec=sec)
        if section == "17052":
            # SB 1435 rewrites (d), (j)(1) and (j)(2) in place; the history
            # note is the only other changed line.
            assert len(new) == len(old)
            changed = [
                index
                for index, (before, after) in enumerate(zip(old, new, strict=True))
                if before != after
            ]
            assert changed[-1] == len(old) - 1
            rewrites = (
                ("for “$2,200.”", "for the amount prescribed in that provision."),
                ("Section 41 of the Revenue and Taxation Code,", "Section 41,"),
                (
                    "Senate Committee on Governance and Finance",
                    "Senate Committee on Revenue and Taxation",
                ),
            )
            assert len(changed) == len(rewrites) + 1
            for index, (before, after) in zip(changed[:-1], rewrites, strict=True):
                assert before in old[index]
                assert old[index].replace(before, after) == new[index]
        else:
            # SB 1435 deletes (b)(5) and renumbers (b)(6)-(14) as (b)(5)-(13);
            # every other line except the history note is unchanged.
            start = next(
                index
                for index, line in enumerate(old)
                if line.startswith("(5) A foreign investment company")
            )
            renumbered_old = old[start + 1 : start + 10]
            renumbered_new = new[start : start + 9]
            assert [_paragraph_number(line) for line in renumbered_old] == list(range(6, 15))
            assert [_paragraph_number(line) for line in renumbered_new] == list(range(5, 14))
            assert [_PARAGRAPH_RE.sub("", line) for line in renumbered_old] == [
                _PARAGRAPH_RE.sub("", line) for line in renumbered_new
            ]
            assert old[:start] == new[:start]
            assert old[start + 10 : -1] == new[start + 9 : -1]
            assert len(new) == len(old) - 1


def test_sb_1435_scope_passes_release_validation_with_the_ftb_3514_scope() -> None:
    release = ReleaseManifest(
        name="us-ca-2026-09-23-pb-ca-validation",
        quality_profile="complete-expression-dates-v1",
        scopes=(
            ReleaseScope("us-ca", "form", FTB_3514_VERSION),
            ReleaseScope("us-ca", "statute", VERSION),
        ),
    )
    report = validate_release(CORPUS_ROOT, release, strict_warnings=True, max_issues=50)
    assert report.to_mapping()["ok"] is True
    assert report.to_mapping()["issue_count"] == 0


def test_sb_1435_scope_collides_with_the_chapter_scope_in_one_release() -> None:
    release = ReleaseManifest(
        name="us-ca-2026-09-23-pb-ca-collision",
        quality_profile="complete-expression-dates-v1",
        scopes=(
            ReleaseScope("us-ca", "statute", CHAPTER_VERSION),
            ReleaseScope("us-ca", "statute", VERSION),
        ),
    )
    report = validate_release(CORPUS_ROOT, release, strict_warnings=True, max_issues=50)
    issues = report.to_mapping()["issues"]
    assert isinstance(issues, list)
    assert sorted((issue["code"], issue["message"].split()[1]) for issue in issues) == [
        ("duplicate_release_citation", f"us-ca/statute/rtc/{section}") for section in SECTIONS
    ]
