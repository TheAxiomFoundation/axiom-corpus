from __future__ import annotations

import scripts.build_program_bundle as bundle


def test_url_state_names_state_publishers_and_leaves_federal_ones():
    assert bundle.url_state("https://dbmefaapolicy.azdes.gov/FAA5/x.html") == "az"
    assert bundle.url_state("https://www.cdss.ca.gov/Portals/9/ACLs/25-79.pdf") == "ca"
    assert bundle.url_state("https://mdhhs-pres-prod.michigan.gov/olmweb/BEM/554.pdf") == "mi"
    assert (
        bundle.url_state("https://www.law.cornell.edu/regulations/maine/10-144-C-M-R-ch-301")
        == "me"
    )
    assert bundle.url_state("https://www.fns.usda.gov/snap/work-requirements") is None


def test_normalize_url_reads_a_webworks_page_from_its_fragment():
    assert (
        bundle.normalize_url(
            "https://dbmefaapolicy.azdes.gov/index.html#page/FAA5/NA_Medical_Expenses_and_Deduction.html"
        )
        == "https://dbmefaapolicy.azdes.gov/FAA5/NA_Medical_Expenses_and_Deduction.html"
    )
    assert bundle.normalize_url("https://www.ecfr.gov/x#p-273.9(a)") == "https://www.ecfr.gov/x"


def test_back_year_compares_the_url_year_with_the_current_fiscal_year():
    assert bundle.back_year(
        "https://fns-prod.azureedge.us/FY19-Maximum-Allotments-Deductions.pdf", 2026
    )
    assert bundle.back_year("https://aspe.hhs.gov/2015-poverty-guidelines", 2026)
    assert not bundle.back_year("https://www.fns.usda.gov/snap/allotment/cola/fy26", 2026)


def test_document_key_takes_the_section_that_holds_a_cited_provision():
    assert bundle.document_key("us/statute/7/2014/e/6/A", []) == "us/statute/7/2014"
    assert bundle.document_key("us/regulation/7/273/9/a/1", []) == "us/regulation/7/273/9"
    assert (
        bundle.document_key("us/guidance/usda/fns/memo/page-2", ["us/guidance/usda/fns/memo"])
        == "us/guidance/usda/fns/memo"
    )


def test_screener_tier_groups_references_into_documents_and_records_exclusions(monkeypatch):
    monkeypatch.setattr(bundle, "manifest_index", lambda: ([], {}, {}))
    export = {
        "program": "snap",
        "policyengine_us_commit": "abc",
        "derived_by": "test",
        "references": [
            {
                "url": "https://www.law.cornell.edu/uscode/text/7/2014#e_6_A",
                "bucket": "covered",
                "citation": "us/statute/7/2014/e/6/A",
            },
            {
                "url": "https://www.law.cornell.edu/uscode/text/7/2014#g",
                "bucket": "covered",
                "citation": "us/statute/7/2014/g",
            },
            {"url": "https://www.snapscreener.com/blog/x", "bucket": "secondary", "citation": None},
            {
                "url": "https://hhs.iowa.gov/media/4001/download",
                "bucket": "not-registered",
                "citation": None,
            },
        ],
    }
    tier = bundle.screener_tier(export, None, None, "az", {}, 2026)
    docs = {d["key"]: d for d in tier["documents"]}
    assert docs["us/statute/7/2014"]["scope"] == "in"
    assert [c["path"] for c in docs["us/statute/7/2014"]["cited"]] == [
        "us/statute/7/2014/e/6/A",
        "us/statute/7/2014/g",
    ]
    assert docs["https://www.snapscreener.com/blog/x"]["reason"] == "Secondary source: not law"
    assert docs["https://hhs.iowa.gov/media/4001/download"]["reason"] == "Another state's source"


def test_toc_exclusions_take_manifest_pages_out_of_the_full_tier(tmp_path, monkeypatch):
    monkeypatch.setattr(bundle, "REPO", tmp_path)
    manifest = tmp_path / "manifests" / "x.yaml"
    manifest.parent.mkdir()
    manifest.write_text(
        "documents:\n"
        + "".join(
            f"- citation_path: us-az/manual/des/faa5/p{i}\n  title: Page {i}\n  source_url: https://x/{i}\n"
            f"  metadata: {{toc_sequence: {i}}}\n"
            for i in range(4)
        )
    )
    tier = bundle.full_tier(
        [manifest],
        bundle.parse_toc_exclusions(["manifests/x.yaml:2-3=Cash Assistance: not SNAP"]),
        [],
    )
    scopes = [(d["key"].rsplit("/", 1)[1], d["scope"], d.get("reason")) for d in tier["documents"]]
    assert scopes == [
        ("p0", "excluded", "Index or overview page: no rules of its own"),
        ("p1", "in", None),
        ("p2", "excluded", "Cash Assistance: not SNAP"),
        ("p3", "excluded", "Cash Assistance: not SNAP"),
    ]


def test_calculation_part_reads_the_policyengine_file_path():
    assert (
        bundle.calculation_part("parameters/gov/usda/snap/income/deductions/standard.yaml")
        == "Deductions"
    )
    assert (
        bundle.calculation_part("variables/gov/usda/snap/income/snap_gross_income.py") == "Income"
    )
    assert (
        bundle.calculation_part("parameters/gov/usda/snap/work_requirements/abawd/age.yaml")
        == "Work requirements"
    )
    assert bundle.calculation_part("parameters/gov/usda/snap/asset_test/limit.yaml") == "Assets"
    assert bundle.calculation_part("parameters/gov/irs/income/x.yaml") == "Other"
    assert bundle.plan_part("us/manual/ssa/poms/si/01140.200") == "Definitions from other programs"
    assert bundle.plan_part(None, "https://aspe.hhs.gov/poverty-guidelines") == "Income"


def test_full_tier_keeps_one_entry_per_source_and_gives_each_its_part(tmp_path, monkeypatch):
    monkeypatch.setattr(bundle, "REPO", tmp_path)
    (tmp_path / "manifests").mkdir()
    plan = tmp_path / "manifests" / "plan.yaml"
    plan.write_text(
        "documents:\n"
        "- title: E&T plan\n  source_url: https://fna.usda.gov/snap-et/stateplan/arizona\n"
    )
    own = tmp_path / "manifests" / "own.yaml"
    own.write_text(
        "documents:\n"
        "- title: E&T plan FFY 2026\n  citation_path: us-az/policy/snap-et-state-plan/ffy2026\n"
        "  source_url: https://fna.usda.gov/snap-et/stateplan/arizona\n"
    )
    tier = bundle.full_tier(
        [plan, own],
        [],
        bundle.parse_toc_parts(["manifests/own.yaml:all=Regulations, plans and waivers"]),
    )
    assert [(d["key"], d["part"]) for d in tier["documents"]] == [
        ("us-az/policy/snap-et-state-plan/ffy2026", "Regulations, plans and waivers")
    ]
