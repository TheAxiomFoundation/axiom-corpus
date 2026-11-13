"""Uganda NSSF Act ss. 10-12: the 2026-09-25 re-extraction and its release.

The 2026-07-08 capture carried Tesseract misreads and right-margin crop
damage into the rows that rulespec-ug cites ("ofa standard contributi of
five percent", "monthly wa payment", "fifly cents"). These tests pin the
corrected bodies, the shape of the manifest corrections, and the
ug-rulespec release that swaps the scope.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

from axiom_corpus.corpus.releases import ReleaseManifest

ROOT = Path(__file__).resolve().parents[1]
VERSION = "2026-09-25-ug-nssf-contributions"
SUPERSEDED_VERSION = "2026-07-08-ug-nssf-contributions"
PROVISIONS = ROOT / f"data/corpus/provisions/ug/statute/{VERSION}.jsonl"
MANIFEST = ROOT / "manifests/ug-nssf-contributions-official-documents.yaml"
RELEASE = ROOT / "manifests/releases/ug-rulespec-2026-09-25.json"
PREDECESSOR = ROOT / "manifests/releases/ug-rulespec-2026-07-12.json"

ACT = "ug/statute/cap-230/national-social-security-fund-act"
S10 = f"{ACT}/section-10-payment-of-standard-contribution-by-employers"
S11 = f"{ACT}/section-11-employees-share-of-standard-contribution"
S12 = f"{ACT}/section-12-special-contribution"

# Search keys in the manifest's text_replacements that complete a word cut
# at the right margin of the scan. A restoration keeps everything the print
# shows except the last glyph, which the crop may have cut through (the
# partial "n" in "on ar", the partial "b" in "section t"), and only adds after
# it.
MARGIN_RESTORATIONS = (
    "furnish to the Managing Director on ar",
    "regarding each eligible employee in his or he",
    "the contribution due on such wages, the total wage",
    "and the total contributions and such other information a",
    "may deduct from the monthly wa",
    "the employee’s share ofa standard contributi",
    "total wages paid during that month to t",
    "more than one wage payment is made during any mor",
    "a member of the Fund or not, tha",
    "the age of fifty-five years in respec",
    "has specifically applied this section t",
)

# Proof excerpts the rulespec-ug NSSF modules and the composed pipeline quote
# once they are re-pinned to this release. Each must be a verbatim substring
# of its row.
RULESPEC_EXCERPTS = {
    S10: (
        "a standard contribution of fifteen percent calculated on the total wages",
        "a standard contribution of fifteen percent calculated on the total wages paid",
        "within fifteen days next following the last day of the month",
        "fifteen percent",
        "during that month to that employee.",
    ),
    S11: (
        "five percent",
        "employee’s share of a standard contribution of five percent calculated on the total wages",
        "deduct from the monthly wage payment of his or her employee the employee’s share of a "
        "standard contribution of five percent calculated on the total wages",
        "not less than four equal instalments",
        "within six months of payment of wages",
        "five percent calculated on the total wages paid during that month",
        "deduct from the last wage payment during that month the difference between the "
        "employee’s share and the total sum already deducted",
        "if the total sum so deducted exceeds the employee’s share, the employer shall refund "
        "the amount in excess",
    ),
    S12: (
        "a special contribution of ten percent",
        "within fifteen days following the last day of the month",
        "an employee of or above the age of fifty-five years",
        "to the nearest multiple of a shilling",
        "non-resident employee who is not an eligible employee",
        "an employee of or above the age of fifty-five years in respect of whom the "
        "Minister has specifically applied this section",
        "an eligible employee",
        "total wages payable to such persons calculated from fifty cents or more to the "
        "nearest multiple of a shilling",
        "every contributing employer shall, for each month during which he or she employs a "
        "person of the following class or description, whether that person is a member of "
        "the Fund or not",
        "pay into the reserve account in such manner as may be prescribed by the Minister, "
        "within fifteen days following the last day of the month for which wages are paid, "
        "a special contribution of ten percent of the total wages payable to such persons",
        "which contribution shall not be payable on the same wages as standard contribution",
    ),
}

# OCR and crop damage present in the 2026-07-08 rows.
DAMAGE = (
    "employce",
    "employcc",
    "ofa standard",
    "contributi ",
    "monthly wa ",
    "to t employee",
    "any mor ",
    "on ar ",
    "his or he service",
    "information a the",
    "total wage to",
    "Ifancligible",
    "contribution duc",
    "docs not",
    "Forthe",
    "Onand",
    "anon-resident",
    "tha is to say",
    "in respec of",
    "section t statutory",
    "fifly",
    "retums",
)


def _bodies() -> dict[str, str]:
    rows = [
        json.loads(line)
        for line in PROVISIONS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return {row["citation_path"]: row.get("body") or "" for row in rows}


def _replacements() -> dict[str, str]:
    manifest = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    (document,) = manifest["documents"]
    return document["extraction"]["text_replacements"]


def test_rows_cover_the_act_and_three_sections() -> None:
    assert set(_bodies()) == {ACT, S10, S11, S12}


@pytest.mark.parametrize("fragment", DAMAGE)
def test_no_ocr_or_crop_damage_survives(fragment: str) -> None:
    for citation, body in _bodies().items():
        assert fragment not in body, (citation, fragment)


def test_running_heads_are_dropped() -> None:
    for citation, body in _bodies().items():
        assert "Cap. 230" not in body, citation
        assert re.search(r"\b82(1[4-9])\b", body) is None, citation


def test_section_12_ends_before_section_13() -> None:
    body = _bodies()[S12]
    assert "Voluntary contributions" not in body
    assert body.endswith(
        "apply different rates of contribution to different classes of employers and employees."
    )


@pytest.mark.parametrize(
    ("citation", "excerpt"),
    [
        (citation, excerpt)
        for citation, excerpts in RULESPEC_EXCERPTS.items()
        for excerpt in excerpts
    ],
)
def test_rulespec_excerpts_are_verbatim(citation: str, excerpt: str) -> None:
    assert excerpt in _bodies()[citation]


def test_statutory_numbers_are_the_printed_ones() -> None:
    bodies = _bodies()
    assert "fifteen percent" in bodies[S10]
    assert "five percent" in bodies[S11]
    assert "four equal instalments" in bodies[S11]
    assert "six months" in bodies[S11]
    assert "ten percent" in bodies[S12]
    assert "fifty-five years" in bodies[S12]
    assert "fifty cents" in bodies[S12]


def test_replacements_are_single_line_and_change_something() -> None:
    for search, replacement in _replacements().items():
        assert search and "\n" not in search and "\n" not in replacement
        assert search != replacement


def test_margin_restorations_only_append_to_the_printed_text() -> None:
    replacements = _replacements()
    assert set(MARGIN_RESTORATIONS) <= set(replacements)
    for search in MARGIN_RESTORATIONS:
        replacement = replacements[search]
        if search.endswith("ofa standard contributi"):
            # The one key that also fixes an interior misread ("ofa" -> "of a").
            assert replacement == "the employee’s share of a standard contribution"
            continue
        assert replacement.startswith(search[:-1]), search
        assert len(replacement) >= len(search), search


def test_release_swaps_only_the_nssf_scope() -> None:
    release = ReleaseManifest.load(RELEASE)
    predecessor = ReleaseManifest.load(PREDECESSOR)

    def keys(manifest: ReleaseManifest) -> set[tuple[str, str, str]]:
        return {
            (scope.jurisdiction, scope.document_class, scope.version) for scope in manifest.scopes
        }

    assert keys(predecessor) - keys(release) == {("ug", "statute", SUPERSEDED_VERSION)}
    assert keys(release) - keys(predecessor) == {("ug", "statute", VERSION)}


def test_release_scopes_resolve_to_committed_artifacts() -> None:
    release = ReleaseManifest.load(RELEASE)
    for scope in release.scopes:
        stem = f"{scope.jurisdiction}/{scope.document_class}/{scope.version}"
        assert (ROOT / f"data/corpus/provisions/{stem}.jsonl").is_file(), stem
        assert (ROOT / f"data/corpus/inventory/{stem}.json").is_file(), stem
        coverage = json.loads(
            (ROOT / f"data/corpus/coverage/{stem}.json").read_text(encoding="utf-8")
        )
        assert coverage["complete"] is True, stem


def test_superseded_capture_stays_for_its_published_releases() -> None:
    # ug-rulespec-2026-07-10 and -07-12 are published and every tracked
    # selector must deep-validate, so the July capture is kept, not deleted.
    for name in ("ug-rulespec-2026-07-10", "ug-rulespec-2026-07-12"):
        release = ReleaseManifest.load(ROOT / f"manifests/releases/{name}.json")
        assert ("ug", "statute", SUPERSEDED_VERSION) in {
            (scope.jurisdiction, scope.document_class, scope.version) for scope in release.scopes
        }
    for kind, suffix in (
        ("provisions", ".jsonl"),
        ("inventory", ".json"),
        ("coverage", ".json"),
    ):
        assert (ROOT / f"data/corpus/{kind}/ug/statute/{SUPERSEDED_VERSION}{suffix}").is_file()


def test_edition_dependent_restorations_carry_pinned_provenance() -> None:
    rows = [
        json.loads(line)
        for line in PROVISIONS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    for row in rows:
        note = row["metadata"]["transcription_note"]
        assert "editorial restorations" in note
        assert (
            "https://media.ulii.org/media/legislation/18538/source_file/"
            "e8d418f126b5c47a/1985-8.pdf" in note
        )
        assert "efeb3198e5fe7f4fb571a00facc8500190c1e49bb507f971eec3637cf1a42fa4" in note
        assert "Cap. 222 s.11(6)" in note and "Cap. 222 s.12(1)" in note
