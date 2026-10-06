from __future__ import annotations

import json

import yaml

import scripts.build_program_bundle as bundle

STATE_HOSTS = {"azdes.gov": "az"}


def test_url_state_names_state_publishers_and_leaves_federal_ones():
    assert bundle.url_state("https://dbmefaapolicy.azdes.gov/FAA5/x.html", STATE_HOSTS) == "az"
    assert bundle.url_state("https://www.cdss.ca.gov/Portals/9/ACLs/25-79.pdf", STATE_HOSTS) == "ca"
    assert (
        bundle.url_state("https://mdhhs-pres-prod.michigan.gov/olmweb/BEM/554.pdf", STATE_HOSTS)
        == "mi"
    )
    assert (
        bundle.url_state(
            "https://www.law.cornell.edu/regulations/maine/10-144-C-M-R-ch-301", STATE_HOSTS
        )
        == "me"
    )
    assert bundle.url_state("https://www.fns.usda.gov/snap/work-requirements", STATE_HOSTS) is None


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


def test_folder_and_plan_parts_come_from_the_config():
    folders = {
        "income": "Income",
        "income/deductions": "Deductions",
        "work_requirements": "Work requirements",
    }
    assert (
        bundle.folder_part("parameters/gov/usda/snap/income/deductions/standard.yaml", folders)
        == "Deductions"
    )
    assert (
        bundle.folder_part("variables/gov/usda/snap/income/snap_gross_income.py", folders)
        == "Income"
    )
    assert (
        bundle.folder_part("parameters/gov/usda/snap/work_requirements/abawd/age.yaml", folders)
        == "Work requirements"
    )
    assert bundle.folder_part("parameters/gov/irs/income/x.yaml", folders) is None
    patterns = [
        {"pattern": "^us/manual/ssa/", "part": "Definitions from other programs"},
        {"pattern": "(?i)poverty", "part": "Income"},
    ]
    assert (
        bundle.plan_part(patterns, "us/manual/ssa/poms/si/01140.200")
        == "Definitions from other programs"
    )
    assert bundle.plan_part(patterns, None, "https://aspe.hhs.gov/poverty-guidelines") == "Income"
    assert bundle.plan_part(patterns, "us/statute/7/2014") is None


def config(tmp_path, monkeypatch, manifests: dict[str, str], references: list[dict]) -> dict:
    """A minimal bundle config over manifests and references written under tmp_path."""
    monkeypatch.setattr(bundle, "REPO", tmp_path)
    (tmp_path / "manifests").mkdir()
    for name, text in manifests.items():
        (tmp_path / "manifests" / name).write_text(text)
    (tmp_path / "refs.json").write_text(json.dumps({"program": "snap", "references": references}))
    return {
        "id": "us-az/snap",
        "title": "Arizona SNAP",
        "program": "snap",
        "jurisdiction": "us-az",
        "current_fiscal_year": 2026,
        "parts": ["Income", "Deductions", "Benefit amount", "Other"],
        "screener": {
            "title": "Screener-level parity",
            "definition": "d",
            "references": "refs.json",
            "folder_parts": {"income": "Income", "income/deductions": "Deductions"},
            "plan_parts": [],
            "exclusions": {
                "back_year": "Back-year",
                "secondary": "Secondary",
                "data_series": "Data series",
                "other_state": "Another state",
            },
            "secondary_hosts": "(?i)snapscreener",
            "data_series_hosts": "(?i)snapqcdata",
            "state_hosts": STATE_HOSTS,
        },
        "full": {
            "title": "Full document bundle",
            "definition": "d",
            "manifests": [],
            "exclude": [],
            "parts": [],
        },
    }


def test_screener_tier_groups_references_into_documents_with_parts_and_exclusions(
    tmp_path, monkeypatch
):
    cfg = config(
        tmp_path,
        monkeypatch,
        {},
        [
            {
                "url": "https://law.cornell.edu/uscode/text/7/2014#e_6_A",
                "bucket": "covered",
                "citation": "us/statute/7/2014/e/6/A",
                "files": ["parameters/gov/usda/snap/income/deductions/x.yaml"],
            },
            {
                "url": "https://law.cornell.edu/uscode/text/7/2014#g",
                "bucket": "covered",
                "citation": "us/statute/7/2014/g",
                "files": ["parameters/gov/usda/snap/income/sources/y.yaml"],
            },
            {
                "url": "https://www.snapscreener.com/blog/x",
                "bucket": "secondary",
                "citation": None,
                "files": [],
            },
            {
                "url": "https://hhs.iowa.gov/media/4001/download",
                "bucket": "not-registered",
                "citation": None,
                "files": [],
            },
        ],
    )
    tier = bundle.screener_tier(cfg, json.loads((tmp_path / "refs.json").read_text()), None)
    docs = {d["key"]: d for d in tier["documents"]}
    assert docs["us/statute/7/2014"]["scope"] == "in"
    assert [(c["path"], c["part"]) for c in docs["us/statute/7/2014"]["cited"]] == [
        ("us/statute/7/2014/e/6/A", "Deductions"),
        ("us/statute/7/2014/g", "Income"),
    ]
    assert docs["https://www.snapscreener.com/blog/x"]["reason"] == "Secondary"
    assert docs["https://hhs.iowa.gov/media/4001/download"]["reason"] == "Another state"


def test_full_tier_applies_exclusions_parts_and_one_entry_per_source(tmp_path, monkeypatch):
    pages = "documents:\n" + "".join(
        f"- citation_path: us-az/manual/des/faa5/p{i}\n  title: Page {i}\n  source_url: https://x/{i}\n  metadata: {{toc_sequence: {i}}}\n"
        for i in range(4)
    )
    cfg = config(
        tmp_path,
        monkeypatch,
        {
            "faa5.yaml": pages,
            "plan.yaml": "documents:\n- title: E&T plan\n  source_url: https://fna.usda.gov/snap-et/az\n",
            "own.yaml": "documents:\n- title: E&T plan FFY 2026\n  citation_path: us-az/policy/et/ffy2026\n  source_url: https://fna.usda.gov/snap-et/az\n",
        },
        [],
    )
    cfg["full"].update(
        {
            "manifests": ["manifests/faa5.yaml", "manifests/plan.yaml", "manifests/own.yaml"],
            "exclude": [
                {
                    "manifest": "manifests/faa5.yaml",
                    "toc": [2, 3],
                    "reason": "Cash Assistance: not SNAP",
                }
            ],
            "parts": [
                {"manifest": "manifests/faa5.yaml", "toc": [1, 1], "part": "Benefit amount"},
                {"key": "us-az/policy/et/ffy2026", "part": "Income"},
            ],
        }
    )
    tier = bundle.full_tier(cfg)
    assert [
        (d["key"].rsplit("/", 1)[1], d["scope"], d.get("reason"), d["part"])
        for d in tier["documents"]
    ] == [
        ("p0", "excluded", "Index or overview page: no rules of its own", "Other"),
        ("p1", "in", None, "Benefit amount"),
        ("p2", "excluded", "Cash Assistance: not SNAP", "Other"),
        ("p3", "excluded", "Cash Assistance: not SNAP", "Other"),
        ("ffy2026", "in", None, "Income"),
    ]


def test_build_refuses_a_part_the_config_does_not_list(tmp_path, monkeypatch):
    cfg = config(
        tmp_path, monkeypatch, {"faa5.yaml": "documents:\n- citation_path: a/b\n  title: A\n"}, []
    )
    cfg["full"].update(
        {
            "manifests": ["manifests/faa5.yaml"],
            "parts": [{"manifest": "manifests/faa5.yaml", "part": "Assets"}],
        }
    )
    path = tmp_path / "manifests" / "x.config.yaml"
    path.write_text(yaml.safe_dump(cfg))
    try:
        bundle.build(path)
    except SystemExit as error:
        assert "Assets" in str(error)
    else:
        raise AssertionError("build accepted a part the config does not list")
