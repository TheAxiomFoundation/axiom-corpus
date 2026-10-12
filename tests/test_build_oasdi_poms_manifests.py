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


def _index(part: str, layout: dict[str, list[str]]) -> dict[str, dict]:
    return {
        chapter: {
            "title": chapter,
            "code": chapter,
            "subchapters": {sub: {"title": sub, "sections": []} for sub in subs},
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
