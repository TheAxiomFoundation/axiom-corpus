"""Offline tests for scripts/build_oasdi_poms_manifests.py and the two POMS
manifests it wrote (parts RS and GN, Social Security)."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "build_oasdi_poms_manifests.py"

_spec = importlib.util.spec_from_file_location("build_oasdi_poms_manifests", SCRIPT)
assert _spec and _spec.loader
oasdi = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = oasdi
_spec.loader.exec_module(oasdi)

# The POMS sections TheAxiomFoundation/rulespec-us known-source-conflicts.yaml
# cites in pending_texts (rulespec-us#1710).
REGISTER_SECTIONS = {
    "RS 02501.030", "RS 02501.080", "RS 02501.140",
    "RS 00615.003", "RS 00615.201", "RS 00615.482", "RS 00615.491",
    "RS 00630.400", "RS 00209.001", "RS 00209.015",
    "GN 02603.045", "GN 02603.050",
}


# Sections per taken subchapter in SSA's own subchapter lists on 2026-10-12
# (docs/ingest-runs/2026-10-12-oasdi-ssa-sources.md), including the .000
# table-of-contents sections and regional sections.
EXPECTED_SECTIONS = {
    "oasdi-rs": {
        "RS 00200": 1, "RS 00201": 4, "RS 00202": 22, "RS 00203": 16, "RS 00204": 18,
        "RS 00205": 36, "RS 00207": 17, "RS 00208": 26, "RS 00209": 7, "RS 00210": 11,
        "RS 00600": 1, "RS 00601": 10, "RS 00605": 96, "RS 00615": 95, "RS 00620": 11,
        "RS 00630": 6, "RS 00640": 3,
        "RS 02500": 1, "RS 02501": 20, "RS 02505": 42, "RS 02510": 15,
    },
    "oasdi-gn": {"GN 02603": 12},
}


def _index(part: str, layout: dict[str, list[str]], *, empty: tuple[str, ...] = ()) -> dict[str, dict]:
    return {
        chapter: {
            "title": chapter,
            "code": chapter,
            "subchapters": {
                sub: {"title": sub, "sections": [] if sub in empty else [{"section": f"{sub}.001"}]}
                for sub in subs
            },
        }
        for chapter, subs in layout.items()
    }


def test_parts_registered_without_touching_si_and_hi() -> None:
    assert oasdi.poms.PARTS["RS"] == ("03", "OASDI")
    assert oasdi.poms.PARTS["GN"] == ("02", "OASDI")
    assert oasdi.poms.PARTS["SI"] == ("05", "SSI")
    assert oasdi.poms.PARTS["HI"] == ("06", "MEDICARE")


def test_whole_chapters_expand_to_every_listed_subchapter() -> None:
    chapters = _index(
        "RS",
        {
            "RS 002": ["RS 00200", "RS 00209"],
            "RS 003": ["RS 00301"],
            "RS 006": ["RS 00605", "RS 00615"],
            "RS 025": ["RS 02501"],
        },
    )
    taken = oasdi.SELECTIONS["oasdi-rs"].subchapters_taken(chapters)
    assert taken == ("RS 00200", "RS 00209", "RS 00605", "RS 00615", "RS 02501")


def test_single_subchapter_selection() -> None:
    chapters = _index("GN", {"GN 026": ["GN 02602", "GN 02603", "GN 02608"]})
    assert oasdi.SELECTIONS["oasdi-gn"].subchapters_taken(chapters) == ("GN 02603",)


@pytest.mark.parametrize(
    ("family", "layout", "message"),
    [
        ("oasdi-rs", {"RS 002": ["RS 00209"], "RS 006": ["RS 00615"]}, "chapter RS 025"),
        ("oasdi-gn", {"GN 026": ["GN 02602"]}, "subchapter GN 02603"),
    ],
)
def test_selection_fails_closed_when_the_index_lacks_it(family: str, layout: dict, message: str) -> None:
    with pytest.raises(SystemExit, match=message):
        oasdi.SELECTIONS[family].subchapters_taken(_index(family, layout))


def test_selection_rejects_a_subchapter_taken_twice() -> None:
    selection = oasdi.Selection(
        family=oasdi.SELECTIONS["oasdi-gn"].family,
        chapters=("GN 026",),
        subchapters=("GN 02603",),
    )
    with pytest.raises(SystemExit, match="selected twice"):
        selection.subchapters_taken(_index("GN", {"GN 026": ["GN 02603"]}))


@pytest.mark.parametrize(
    ("family", "layout", "empty", "message"),
    [
        # SSA keeps a subchapter heading but the parser finds no section under it
        ("oasdi-rs", {"RS 002": ["RS 00201", "RS 00209"], "RS 006": ["RS 00615"], "RS 025": ["RS 02501"]},
         ("RS 00201",), "no sections parsed for selected subchapter.*RS 00201"),
        ("oasdi-gn", {"GN 026": ["GN 02602", "GN 02603"]}, ("GN 02603",), "GN 02603"),
        # a chapter heading survives with no subchapters under it
        ("oasdi-rs", {"RS 002": [], "RS 006": ["RS 00615"], "RS 025": ["RS 02501"]}, (), "chapter RS 002 lists no"),
    ],
)
def test_selection_rejects_empty_parsed_selections(family: str, layout: dict, empty: tuple, message: str) -> None:
    with pytest.raises(SystemExit, match=message):
        oasdi.SELECTIONS[family].subchapters_taken(_index(family, layout, empty=empty))


def test_unselected_empty_subchapter_is_ignored() -> None:
    chapters = _index("GN", {"GN 026": ["GN 02602", "GN 02603"]}, empty=("GN 02602",))
    assert oasdi.SELECTIONS["oasdi-gn"].subchapters_taken(chapters) == ("GN 02603",)


@pytest.mark.parametrize("family", sorted(oasdi.SELECTIONS))
def test_committed_manifest_has_every_expected_section(family: str) -> None:
    fam = oasdi.SELECTIONS[family].family
    docs = yaml.safe_load(fam.manifest_path.read_text(encoding="utf-8"))["documents"]
    counts: dict[str, int] = {}
    for doc in docs:
        sub = doc["metadata"]["poms_subchapter"]
        counts[sub] = counts.get(sub, 0) + 1
    assert counts == EXPECTED_SECTIONS[family]
    # every subchapter's table-of-contents section is taken
    sections = {doc["metadata"]["poms_section"] for doc in docs}
    assert {f"{sub}.000" for sub in EXPECTED_SECTIONS[family]} <= sections


@pytest.mark.parametrize("family", sorted(oasdi.SELECTIONS))
def test_committed_manifest_uses_the_poms_extraction(family: str) -> None:
    fam = oasdi.SELECTIONS[family].family
    docs = yaml.safe_load(fam.manifest_path.read_text(encoding="utf-8"))["documents"]
    expected = {
        "html_content_selector": "div.poms",
        "html_drop_selectors": ["p.tninfo", "div.poms-citation"],
    }
    assert expected == oasdi.poms.EXTRACTION
    for doc in docs:
        assert doc["extraction"] == expected
        assert doc["request"] == {"browser_impersonation": True}
        assert doc["source_format"] == "html"


@pytest.mark.parametrize("family", sorted(oasdi.SELECTIONS))
def test_committed_manifest_matches_its_family(family: str) -> None:
    fam = oasdi.SELECTIONS[family].family
    part = fam.part.lower()
    manifest = yaml.safe_load(fam.manifest_path.read_text(encoding="utf-8"))
    assert manifest["version"] == fam.version
    docs = manifest["documents"]
    paths = [doc["citation_path"] for doc in docs]
    assert len(paths) == len(set(paths))
    selection = oasdi.SELECTIONS[family]
    for doc in docs:
        meta = doc["metadata"]
        number = meta["poms_section"].split(" ", 1)[1].lower()
        assert doc["citation_path"] == f"us/manual/ssa/poms/{part}/{number}"
        assert doc["source_id"] == f"ssa-poms-{part}-{number.replace('.', '-')}"
        assert doc["jurisdiction"] == "us" and doc["document_class"] == "manual"
        assert doc["source_as_of"] == fam.source_as_of
        assert re.fullmatch(r"https://secure\.ssa\.gov/apps10/poms\.nsf/lnx/\d{10}[A-Z]*", doc["source_url"])
        assert meta["program"] == "OASDI" and meta["poms_part"] == fam.part
        assert doc["expression_date"] == meta["effective_date_printed"]
        assert meta["poms_chapter"] in selection.chapters or meta["poms_subchapter"] in selection.subchapters


def test_manifests_hold_every_register_section() -> None:
    held = set()
    for selection in oasdi.SELECTIONS.values():
        manifest = yaml.safe_load(selection.family.manifest_path.read_text(encoding="utf-8"))
        held |= {doc["metadata"]["poms_section"] for doc in manifest["documents"]}
    assert held >= REGISTER_SECTIONS
