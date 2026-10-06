from __future__ import annotations

import datetime as dt
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
    # An archived page belongs to the state of the page it archives.
    assert (
        bundle.url_state(
            "https://web.archive.org/web/2011/http://services.dpw.state.pa.us:80/manual.htm",
            STATE_HOSTS,
        )
        == "pa"
    )
    # A federal letter to one state, by the config's pattern.
    letter = (
        "https://www.fns.usda.gov/sites/default/files/resource-files/ca-abawd-response-fy2026-a.pdf"
    )
    assert bundle.url_state(letter, STATE_HOSTS) is None
    assert bundle.url_state(letter, STATE_HOSTS, ["/(?P<state>[a-z]{2})-abawd-response"]) == "ca"


def test_url_key_reads_alias_hosts_as_the_host_they_serve_for():
    aliases = {"fna.usda.gov": "fns.usda.gov", "fns-prod.azureedge.us": "fns.usda.gov"}
    assert bundle.url_key("https://www.fna.usda.gov/snap/x", aliases) == ("fns.usda.gov", "/snap/x")
    assert bundle.url_key("https://fns-prod.azureedge.us/a.pdf", aliases) == bundle.url_key(
        "https://www.fns.usda.gov/a.pdf", aliases
    )


def test_title_state_names_one_state_only():
    assert bundle.title_state(["Massachusetts DTA SNAP policy"]) == "ma"
    assert bundle.title_state(["New York and New Jersey letters"]) is None
    assert bundle.title_state(["7 CFR 273.9"]) is None


def test_normalize_url_reads_a_webworks_page_from_its_fragment():
    assert (
        bundle.normalize_url(
            "https://dbmefaapolicy.azdes.gov/index.html#page/FAA5/NA_Medical_Expenses_and_Deduction.html"
        )
        == "https://dbmefaapolicy.azdes.gov/FAA5/NA_Medical_Expenses_and_Deduction.html"
    )
    assert bundle.normalize_url("https://www.ecfr.gov/x#p-273.9(a)") == "https://www.ecfr.gov/x"
    assert (
        bundle.normalize_url("https://web.archive.org/web/2026id_/https://www.usda.gov/a.pdf")
        == "https://www.usda.gov/a.pdf"
    )


def test_fiscal_year_starts_in_october():
    assert bundle.fiscal_year(dt.date(2026, 9, 30)) == 2026
    assert bundle.fiscal_year(dt.date(2026, 10, 1)) == 2027


def test_back_year_compares_fiscal_years_and_poverty_guideline_years():
    day = dt.date(2026, 10, 6)  # FY2027
    assert bundle.back_year(
        "https://fns-prod.azureedge.us/FY19-Maximum-Allotments-Deductions.pdf", day
    )
    assert bundle.back_year("https://www.fns.usda.gov/snap/allotment/cola/fy26", day)
    assert bundle.back_year(
        "https://www.usda.gov/guidance-documents/fns.snap-COLAMemoFY23_0.pdf", day
    )
    assert not bundle.back_year("https://www.fns.usda.gov/snap/allotment/cola/fy27", day)
    assert not bundle.back_year("https://www.usda.gov/fna.snap-cola2027.pdf", day)
    # Poverty guidelines are by calendar year, from the URL or the title.
    assert bundle.back_year("https://aspe.hhs.gov/2025-poverty-guidelines", day)
    assert bundle.back_year("https://www.govinfo.gov/x 2025 Poverty Guidelines", day)
    assert not bundle.back_year("https://aspe.hhs.gov/2026-poverty-guidelines", day)
    # A year in a folder is a publication date.
    assert not bundle.back_year("https://www.cdss.ca.gov/ACLs/2025/25-79.pdf", day)


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
        "as_of": "2026-10-06",
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
                "enacting": "Enacting text",
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
    deductions = "parameters/gov/usda/snap/income/deductions/x.yaml"
    cfg = config(
        tmp_path,
        monkeypatch,
        {
            "fns.yaml": "documents:\n- citation_path: us/guidance/usda/fns/snap-fy2027-cola\n"
            "  source_url: https://www.fna.usda.gov/snap/allotment/cola/fy27\n"
        },
        [
            {
                "url": "https://law.cornell.edu/uscode/text/7/2014#e_6_A",
                "citation": "us/statute/7/2014/e/6/A",
                "files": [deductions],
            },
            {
                "url": "https://law.cornell.edu/uscode/text/7/2014#g",
                "citation": "us/statute/7/2014/g",
                "files": ["parameters/gov/usda/snap/income/sources/y.yaml"],
            },
            # A whole section PolicyEngine cites is a unit too.
            {
                "url": "https://law.cornell.edu/uscode/text/7/2015",
                "citation": "us/statute/7/2015",
                "files": [deductions],
            },
            {"url": "https://www.snapscreener.com/blog/x", "citation": None, "files": []},
            {"url": "https://hhs.iowa.gov/media/4001/download", "citation": None, "files": []},
            # Another state's rule in a file that lists every state's.
            {
                "url": "https://risos-apa.s3.amazonaws.com/DHS/7907.pdf",
                "titles": ["Rhode Island DHS SNAP rule 7907"],
                "citation": None,
                "files": [deductions],
            },
            # The public law, where the same file cites the codified section.
            {
                "url": "https://www.congress.gov/119/plaws/publ21/PLAW-119publ21.pdf",
                "citation": None,
                "files": [deductions],
            },
            # The corpus registers FNS pages at fna.usda.gov.
            {
                "url": "https://www.fns.usda.gov/snap/allotment/cola/fy27",
                "citation": None,
                "files": [deductions],
            },
        ],
    )
    cfg["screener"]["host_aliases"] = {"fna.usda.gov": "fns.usda.gov"}
    tier = bundle.screener_tier(cfg, json.loads((tmp_path / "refs.json").read_text()), None)
    docs = {d["key"]: d for d in tier["documents"]}
    assert docs["us/statute/7/2014"]["scope"] == "in"
    assert [(c["path"], c["part"]) for c in docs["us/statute/7/2014"]["cited"]] == [
        ("us/statute/7/2014/e/6/A", "Deductions"),
        ("us/statute/7/2014/g", "Income"),
    ]
    assert [c["path"] for c in docs["us/statute/7/2015"]["cited"]] == ["us/statute/7/2015"]
    assert docs["https://www.snapscreener.com/blog/x"]["reason"] == "Secondary"
    assert docs["https://hhs.iowa.gov/media/4001/download"]["reason"] == "Another state"
    assert docs["https://risos-apa.s3.amazonaws.com/DHS/7907.pdf"]["reason"] == "Another state"
    assert (
        docs["https://www.congress.gov/119/plaws/publ21/PLAW-119publ21.pdf"]["reason"]
        == "Enacting text"
    )
    assert docs["us/guidance/usda/fns/snap-fy2027-cola"]["scope"] == "in"
    assert tier["membership"]["fiscal_year"] == 2027


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
    tier = bundle.full_tier(cfg, {"documents": []})
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


def test_full_tier_holds_the_screener_tier_the_federal_law_and_known_state_sources(
    tmp_path, monkeypatch
):
    cfg = config(tmp_path, monkeypatch, {}, [])
    (tmp_path / "schema.yaml").write_text(
        yaml.safe_dump(
            {
                "elements": [
                    {"id": "a", "label": "7 USC 2014(a)", "citation_path": "us/statute/7/2014/a"},
                    {"id": "b", "label": "7 USC 2014(d)", "citation_path": "us/statute/7/2014/d"},
                    {"id": "c", "label": "7 CFR 275.1", "citation_path": "us/regulation/7/275/1"},
                    {
                        "id": "d",
                        "label": "FY 2026 COLA",
                        "citation_path": "us/guidance/fy2026-cola",
                    },
                    {"id": "e", "label": "State fact", "citation_path": None},
                ]
            }
        )
    )
    cfg["full"].update(
        {
            "federal": {
                "schema": "schema.yaml",
                "exclude": [{"pattern": "^us/regulation/7/275", "reason": "Administration"}],
                "parts": [{"pattern": "^us/statute/7/2014", "part": "Income"}],
            },
            "known_sources": [
                {
                    "citation_path": "us-az/statute/46",
                    "title": "ARS Title 46",
                    "part": "Deductions",
                    "note": "No manifest yet",
                }
            ],
        }
    )
    screener = {
        "documents": [
            {
                "key": "us/statute/7/2015",
                "name": "7 USC 2015",
                "layer": "federal",
                "citation_path": "us/statute/7/2015",
                "source_url": None,
                "scope": "in",
                "part": "Deductions",
            },
            {"key": "https://x/old", "scope": "excluded", "reason": "Back-year"},
        ]
    }
    tier = bundle.full_tier(cfg, screener)
    docs = {d["key"]: d for d in tier["documents"]}
    # The screener tier's in-scope documents are all here, and only those.
    assert docs["us/statute/7/2015"]["sources"] == ["screener"]
    assert "https://x/old" not in docs
    # Schema elements group into sections, each once.
    assert docs["us/statute/7/2014"]["sources"] == ["schema:a", "schema:b"]
    assert docs["us/statute/7/2014"]["part"] == "Income"
    assert docs["us/regulation/7/275/1"]["reason"] == "Administration"
    assert docs["us/guidance/fy2026-cola"]["reason"] == "Back-year"
    assert docs["us-az/statute/46"]["scope"] == "in"
    assert tier["membership"]["in_scope_by_layer"] == {"federal": 2, "state": 1}
