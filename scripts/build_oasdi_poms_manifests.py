"""Build SSA POMS official-document manifests for Social Security (OASDI) from parts
RS (Retirement and Survivors Insurance) and GN (General), reusing the part SI/HI
generator's index reader and document builder (``build_ssi_poms_si_manifests.py``).

Primary official source: SSA Program Operations Manual System (POMS), public site
https://secure.ssa.gov/poms.nsf/. Part RS is chapter-list category 03 and part GN
category 02; each chapter links to a subchapter list that enumerates every section
(national and regional) with its ``lnx`` URL. One manifest document per section,
citation path ``us/manual/ssa/poms/<part>/<section number>``.

Families (``--family``), one scope each:

* ``oasdi-rs``: whole chapters RS 002 (Benefits and Payments), RS 006 (Determination
  of PIAs and Benefit Amounts) and RS 025 (Annual Earnings Test), version
  ``2026-10-12-oasdi-poms-rs``.
* ``oasdi-gn``: subchapter GN 02603 (Readjustment Procedures), version
  ``2026-10-12-oasdi-poms-gn``.

The selection is every chapter (RS) or subchapter (GN) that holds a POMS section
cited by ``TheAxiomFoundation/rulespec-us`` ``known-source-conflicts.yaml``
(``pending_texts``) or by the Social Security source snapshots that register's
entries pin; see ``docs/ingest-runs/2026-10-12-oasdi-ssa-sources.md``. Every section
the subchapter list enumerates for a taken subchapter is taken, including the
``.000`` table-of-contents sections, so taken_count equals the index count.

There is no OASDI agent queue, so unlike the SI/HI families this script writes only
the manifest. Section pages are cached under ``--cache-dir`` (default
``~/.axiom/poms-<part>-cache``); the corpus extractor re-fetches every page itself
when it snapshots the source.

    uv run python scripts/build_oasdi_poms_manifests.py --family oasdi-rs|oasdi-gn [--print-index]
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]


def _load_poms_generator() -> ModuleType:
    path = Path(__file__).with_name("build_ssi_poms_si_manifests.py")
    spec = importlib.util.spec_from_file_location("build_ssi_poms_si_manifests", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolve the module's string annotations through sys.modules
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


poms = _load_poms_generator()
# POMS part -> (chapter-list category, program); the shared reader looks parts up here.
poms.PARTS.setdefault("RS", ("03", "OASDI"))
poms.PARTS.setdefault("GN", ("02", "OASDI"))

SOURCE_AS_OF = "2026-10-12"
DISCOVERED_VIA = (
    "source-conflict register: TheAxiomFoundation/rulespec-us known-source-conflicts.yaml "
    "pending_texts (rulespec-us#1710) and the Social Security source snapshots its entries pin; "
    "SSA POMS {part} table of contents"
)


@dataclasses.dataclass(frozen=True)
class Selection:
    """A family plus the chapters it takes whole (``chapters``) or the single
    subchapters it takes (``subchapters``)."""

    family: object
    chapters: tuple[str, ...] = ()
    subchapters: tuple[str, ...] = ()

    def subchapters_taken(self, chapters: dict[str, dict]) -> tuple[str, ...]:
        """Expand whole chapters into their subchapters from the publisher's index
        and fail closed when a named chapter or subchapter is not listed."""
        taken: list[str] = []
        for chapter in self.chapters:
            if chapter not in chapters:
                raise SystemExit(f"chapter {chapter} is not in the {self.family.part} chapter list")
            taken.extend(chapters[chapter]["subchapters"])
        listed = {sub for info in chapters.values() for sub in info["subchapters"]}
        for sub in self.subchapters:
            if sub not in listed:
                raise SystemExit(f"subchapter {sub} is not in the {self.family.part} subchapter lists")
            taken.append(sub)
        if len(set(taken)) != len(taken):
            raise SystemExit("a subchapter is selected twice")
        return tuple(taken)


SELECTIONS = {
    "oasdi-rs": Selection(
        family=poms.Family(
            name="oasdi-rs", part="RS", version="2026-10-12-oasdi-poms-rs", source_as_of=SOURCE_AS_OF,
            manifest="us-ssa-poms-rs-2026-10-12.yaml", discovered_via=DISCOVERED_VIA.format(part="RS"),
        ),
        # RS 002: RS 00209 (parent's benefits); RS 006: RS 00605, RS 00615, RS 00630;
        # RS 025: RS 02501, RS 02505, RS 02510.
        chapters=("RS 002", "RS 006", "RS 025"),
    ),
    "oasdi-gn": Selection(
        family=poms.Family(
            name="oasdi-gn", part="GN", version="2026-10-12-oasdi-poms-gn", source_as_of=SOURCE_AS_OF,
            manifest="us-ssa-poms-gn-2026-10-12.yaml", discovered_via=DISCOVERED_VIA.format(part="GN"),
        ),
        subchapters=("GN 02603",),
    ),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--family", choices=sorted(SELECTIONS), required=True, help="POMS scope to build")
    parser.add_argument("--cache-dir", type=Path, default=None,
                        help="section-page cache (default ~/.axiom/poms-<part>-cache)")
    parser.add_argument("--print-index", action="store_true", help="print the part's index inventory as markdown")
    args = parser.parse_args()
    selection = SELECTIONS[args.family]
    cache_dir = args.cache_dir or Path.home() / ".axiom" / f"poms-{selection.family.part.lower()}-cache"
    session = requests.Session()
    session.headers.update({"User-Agent": poms.USER_AGENT})
    chapters = poms.read_index(session, cache_dir, selection.family.part)
    family = dataclasses.replace(selection.family, include=selection.subchapters_taken(chapters))
    index_count = sum(len(s["sections"]) for c in chapters.values() for s in c["subchapters"].values())
    if args.print_index:
        print(poms.index_markdown(chapters, family))
    docs = poms.build_documents(chapters, session, cache_dir, family)
    expected = sum(
        len(s["sections"]) for c in chapters.values() for k, s in c["subchapters"].items() if family.takes(k)
    )
    if len(docs) != expected:
        raise SystemExit(f"took {len(docs)} sections, the index lists {expected} for the selection")
    manifest = {"version": family.version, "documents": docs}
    family.manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True, width=120))
    missing_dates = [d["metadata"]["poms_section"] for d in docs if "effective_date_printed" not in d["metadata"]]
    print(
        json.dumps(
            {
                "family": family.name,
                "manifest": str(family.manifest_path.relative_to(ROOT)),
                "index_section_count": index_count,
                "subchapters_taken": list(family.include or ()),
                "taken_count": len(docs),
                "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
                "sections_without_printed_effective_date": missing_dates,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
