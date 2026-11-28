from __future__ import annotations

import datetime as dt
import json

import pytest
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
    assert bundle.url_key("https://www.fna.usda.gov/snap/x", aliases) == (
        "fns.usda.gov",
        "/snap/x",
        "",
    )
    assert bundle.url_key("https://fns-prod.azureedge.us/a.pdf", aliases) == bundle.url_key(
        "https://www.fns.usda.gov/a.pdf", aliases
    )


def test_url_key_keeps_the_query_that_names_a_query_routed_document():
    # Colorado's register serves every rule from one script; the query names the rule.
    snap = "https://www.sos.state.co.us/CCR/GenerateRulePdf.do?ruleVersionId=10492&fileName=10%20CCR%202506-1"
    chp = "https://www.sos.state.co.us/CCR/GenerateRulePdf.do?ruleVersionId=10779"
    assert bundle.url_key(snap) != bundle.url_key(chp)
    # Parameter order, case, encoding and tracking parameters do not change the key.
    assert bundle.url_key(snap) == bundle.url_key(
        "https://sos.state.co.us/ccr/GenerateRulePdf.do?filename=10+CCR+2506-1&ruleVersionId=10492&utm_source=x"
    )


def test_url_lookup_falls_back_to_the_page_named_without_a_query():
    index = {bundle.url_key("https://example.gov/manual.pdf"): "us-xx/manual"}
    assert (
        bundle.url_lookup(index, bundle.url_key("https://example.gov/manual.pdf?v=3"))
        == "us-xx/manual"
    )
    rules = {
        bundle.url_key(
            "https://www.sos.state.co.us/CCR/GenerateRulePdf.do?ruleVersionId=1"
        ): "us-co/a"
    }
    assert (
        bundle.url_lookup(
            rules,
            bundle.url_key("https://www.sos.state.co.us/CCR/GenerateRulePdf.do?ruleVersionId=2"),
        )
        is None
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


def test_normalize_url_reads_a_webworks_page_named_under_the_host_root():
    page = "https://dbmefaapolicy.azdes.gov/FAA5/NA_Utility_Expenses_and_Allowances.html"
    fragment = "#page/FAA5/NA_Utility_Expenses_and_Allowances.html"
    for reader in (
        "https://dbmefaapolicy.azdes.gov/index.html",
        "https://dbmefaapolicy.azdes.gov/",
        "https://dbmefaapolicy.azdes.gov",
    ):
        assert bundle.normalize_url(reader + fragment) == page
        assert bundle.normalize_url(reader + fragment + "/") == page
    assert (
        bundle.normalize_url(
            "https://dbmefaapolicy.azdes.gov/#page/FAA6/Utility_Allowance_Current_Amount.html"
        )
        == "https://dbmefaapolicy.azdes.gov/FAA6/Utility_Allowance_Current_Amount.html"
    )
    assert bundle.url_key(
        bundle.normalize_url("https://dbmefaapolicy.azdes.gov/#page/FAA5/A.html")
    ) == bundle.url_key("https://dbmefaapolicy.azdes.gov/FAA5/A.html")
    # A fragment that names no page, and a page-like fragment under another
    # path, stay the page before the fragment.
    assert (
        bundle.normalize_url("https://dbmefaapolicy.azdes.gov/#page/")
        == "https://dbmefaapolicy.azdes.gov/"
    )
    assert (
        bundle.normalize_url("https://example.gov/manual/#page/FAA5/A.html")
        == "https://example.gov/manual/"
    )


def test_normalize_url_webworks_page_edge_forms():
    page = "dbmefaapolicy.azdes.gov/FAA5/A.html"
    # Scheme: http and https both read; an uppercase scheme reads the same.
    assert (
        bundle.normalize_url("http://dbmefaapolicy.azdes.gov/#page/FAA5/A.html") == "http://" + page
    )
    assert (
        bundle.normalize_url("HTTPS://dbmefaapolicy.azdes.gov/#page/FAA5/A.html")
        == "HTTPS://" + page
    )
    assert bundle.url_key(
        bundle.normalize_url("HTTPS://DBMEFAAPOLICY.AZDES.GOV/#page/FAA5/A.html")
    ) == bundle.url_key("https://" + page)
    # A second fragment inside the page fragment is not part of the page.
    assert (
        bundle.normalize_url("https://dbmefaapolicy.azdes.gov/#page/FAA5/A.html#sec")
        == "https://" + page
    )
    # Archived and padded links read the page they archive.
    assert (
        bundle.normalize_url(
            "https://web.archive.org/web/2026id_/https://dbmefaapolicy.azdes.gov/#page/FAA5/A.html"
        )
        == "https://" + page
    )
    assert (
        bundle.normalize_url("  https://dbmefaapolicy.azdes.gov/#page/FAA5/A.html\n")
        == "https://" + page
    )
    # A query before the fragment, an empty fragment, a fragment that is not a
    # page, and a reader index under another path keep the page before the fragment.
    for url, expected in (
        (
            "https://dbmefaapolicy.azdes.gov/?x=1#page/FAA5/A.html",
            "https://dbmefaapolicy.azdes.gov/?x=1",
        ),
        ("https://dbmefaapolicy.azdes.gov/#", "https://dbmefaapolicy.azdes.gov/"),
        ("https://dbmefaapolicy.azdes.gov/#page", "https://dbmefaapolicy.azdes.gov/"),
        ("https://dbmefaapolicy.azdes.gov/#page//", "https://dbmefaapolicy.azdes.gov/"),
        ("https://example.gov/#top", "https://example.gov/"),
        ("https://example.gov/index.html#overview", "https://example.gov/index.html"),
        (
            "https://example.gov/manual/index.html#page/X/A.html",
            "https://example.gov/manual/index.html",
        ),
    ):
        assert bundle.normalize_url(url) == expected


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
    # A three-year state plan is current through its last fiscal year.
    assert not bundle.back_year(
        "us-ca/policy/acf/ccdf-plan/fy2025-2027 California CCDF Plan, FFY 2025-2027", day
    )
    assert not bundle.back_year("Idaho TANF State Plan Renewal FY2026-FY2028", day)
    assert bundle.back_year("Nebraska CCDF Plan For Nebraska FFY 2019-2021", day)
    assert bundle.back_year("Kansas TANF State Plan FFY 2024-2026", day)
    assert bundle.back_year("2024-09-30-SUA-Table-FY25-508-Update.xlsx", day)
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


def test_document_path_puts_a_section_cut_from_a_title_under_its_label():
    section = {
        "citation_path": "us/statute/26",
        "extraction": {"section_label": "85"},
    }
    assert bundle.document_path(section) == "us/statute/26/85"
    rule = {
        "citation_path": "us-ut/regulation/admin-rules/r986/200",
        "extraction": {"section_label": "239"},
    }
    assert bundle.document_path(rule) == "us-ut/regulation/admin-rules/r986/200/239"
    # A label that already ends the path, or one that names no section, changes nothing.
    assert bundle.document_path(
        {"citation_path": "us/statute/7/2014", "extraction": {"section_label": "2014"}}
    ) == ("us/statute/7/2014")
    assert bundle.document_path(
        {"citation_path": "us-sd/statute/10/43", "extraction": {"section_label": "chapter-index"}}
    ) == ("us-sd/statute/10/43")
    assert bundle.document_path({"citation_path": "us/statute/7/2015"}) == "us/statute/7/2015"


def test_rule_part_takes_the_first_matching_rule_and_flattens_shared_lists():
    shared = [{"pattern": "(?i)income", "part": "Income"}]
    rules = bundle._rules([{"pattern": "deductions", "part": "Deductions"}, shared])
    assert bundle.rule_part(rules, "gov/usda/snap/income/deductions/x.yaml") == "Deductions"
    assert bundle.rule_part(rules, None, "https://x/income") == "Income"
    assert bundle.rule_part(rules, "gov/usda/snap/asset_test") is None


def test_schema_sections_read_every_schema_shape():
    snap = {
        "elements": [
            {"id": "a", "level": "federal_statute", "citation_path": "us/statute/7/2014/a"}
        ]
    }
    tanf = {
        "federal_statute_elements": [{"id": "t1", "citation": "42 U.S.C. 601", "name": "Purpose"}],
        "federal_regulation_elements": [{"id": "t2", "citation": "45 CFR 260.20"}],
    }
    medicaid = {
        "elements": [
            {"id": "m1", "level": "federal_only", "federal_citation": "42 U.S.C. 1396a(a)(10)"},
            {"id": "m2", "level": "federal_only", "federal_citation": "42 CFR 431 subpart E"},
            {"id": "m3", "level": "state", "federal_citation": "42 U.S.C. 1396a(a)(3)"},
        ]
    }
    tax = {"elements": [{"id": "F1", "level": "federal", "sections": ["1", "32"]}]}
    assert [p for p, _, _ in bundle.schema_sections(snap)] == ["us/statute/7/2014/a"]
    assert [p for p, _, _ in bundle.schema_sections(tanf)] == [
        "us/statute/42/601",
        "us/regulation/45/260/20",
    ]
    assert [p for p, _, _ in bundle.schema_sections(medicaid)] == [
        "us/statute/42/1396a",
        "us/regulation/42/431",
    ]
    assert [p for p, _, _ in bundle.schema_sections(tax)] == ["us/statute/26/1", "us/statute/26/32"]
    # Every level: the federal law a state-level element cites too.
    assert [p for p, _, _ in bundle.schema_sections(medicaid, every_level=True)] == [
        "us/statute/42/1396a",
        "us/regulation/42/431",
        "us/statute/42/1396a",
    ]


def config(tmp_path, monkeypatch) -> dict:
    """A minimal programs config, with one program and two states, under tmp_path."""
    monkeypatch.setattr(bundle, "REPO", tmp_path)
    (tmp_path / "schema.yaml").write_text(
        yaml.safe_dump(
            {
                "elements": [
                    {
                        "id": "s1",
                        "level": "federal_statute",
                        "citation_path": "us/statute/7/2014/a",
                    },
                    {
                        "id": "s2",
                        "level": "federal_regulation",
                        "citation_path": "us/regulation/7/275/1",
                    },
                ]
            }
        )
    )
    return {
        "as_of": "2026-10-06",
        "jurisdictions": ["az", "ca"],
        "policyengine_us": {"references": "refs-{program}.json"},
        "tiers": {
            "screener": {"title": "Screener-level parity", "definition": "d"},
            "full": {"title": "Full document bundle", "definition": "d"},
        },
        "exclusions": {
            "back_year": "Back-year",
            "secondary": "Secondary",
            "data_series": "Data series",
            "enacting": "Enacting text",
        },
        "secondary_hosts": "(?i)snapscreener",
        "data_series_hosts": "(?i)snapqcdata",
        "federal_hosts": "(?i)(^|\\.)(usda|fns|fna)\\.gov$|law\\.cornell\\.edu$",
        "state_hosts": STATE_HOSTS,
        "host_aliases": {"fna.usda.gov": "fns.usda.gov"},
        "programs": {
            "snap": {
                "title": "SNAP",
                "plan_programs": ["snap"],
                "schema": "schema.yaml",
                "federal_exclude": [
                    {"pattern": "^us/regulation/7/275", "reason": "Administration"}
                ],
                "federal_manifests": "^us-snap",
                "state_manifests": "snap",
                "state_documents": "(?i)nutrition assistance",
                "parts": ["Income", "Deductions", "Benefit amount", "Other"],
                "part_rules": [
                    {"pattern": "deductions", "part": "Deductions"},
                    [{"pattern": "(?i)income", "part": "Income"}],
                ],
                "states": {
                    "az": {
                        "known_sources": [
                            {
                                "citation_path": "us-az/statute/46",
                                "title": "ARS 46",
                                "part": "Other",
                            }
                        ]
                    }
                },
            }
        },
    }


def test_build_program_puts_each_reference_in_the_layer_of_the_law_it_names(tmp_path, monkeypatch):
    cfg = config(tmp_path, monkeypatch)
    deductions = "parameters/gov/usda/snap/income/deductions/x.yaml"
    references = {
        "references": [
            # Federal law: the federal layer, a whole section a unit too.
            {
                "url": "https://law.cornell.edu/uscode/text/7/2014#e_6_A",
                "citation": "us/statute/7/2014/e/6/A",
                "files": [deductions],
            },
            {
                "url": "https://law.cornell.edu/uscode/text/7/2015",
                "citation": "us/statute/7/2015",
                "files": [deductions],
            },
            # A state's own source, from its state folder: that state's layer.
            {
                "url": "https://dbmefaapolicy.azdes.gov/FAA5/x.html",
                "citation": None,
                "states": ["az"],
                "files": ["parameters/gov/states/az/des/snap/x.yaml"],
            },
            # Another state's rule in a file that lists every state's: that state's layer.
            {
                "url": "https://www.cdss.ca.gov/acl-25-79.pdf",
                "citation": None,
                "titles": ["California ACL 25-79"],
                "files": [deductions],
            },
            # A federal page cited from a state folder stays federal.
            {
                "url": "https://www.fns.usda.gov/snap/work-requirements",
                "citation": None,
                "states": ["az"],
                "files": ["parameters/gov/states/az/des/snap/y.yaml"],
            },
            {"url": "https://www.snapscreener.com/blog/x", "citation": None, "files": [deductions]},
            {
                "url": "https://www.congress.gov/119/plaws/publ21/PLAW-119publ21.pdf",
                "citation": None,
                "files": [deductions],
            },
        ]
    }
    manifests = {
        "manifests/us-snap-guidance.yaml": [
            {
                "citation_path": "us/guidance/usda/fns/snap-fy2027-cola",
                "title": "FY 2027 COLA",
                "source_url": "https://www.fna.usda.gov/snap/allotment/cola/fy27",
            }
        ],
        "manifests/us-az-snap-primary-policy.yaml": [
            {
                "citation_path": "us-az/regulation/aac/6/14",
                "title": "AAC 6-14",
                "source_url": "https://apps.azsos.gov/6-14.pdf",
            }
        ],
        # A manual shared by programs: only the documents that name this one.
        "manifests/us-ca-manuals.yaml": [
            {
                "citation_path": "us-ca/manual/x/nutrition",
                "title": "Nutrition assistance budgeting",
            },
            {"citation_path": "us-ca/manual/x/child-care", "title": "Child care eligibility"},
        ],
    }
    index = bundle.index_manifests(manifests, cfg["host_aliases"])
    out = bundle.build_program(cfg, "snap", references, None, manifests, index)
    layers = {layer["jurisdiction"]: layer for layer in out["layers"]}
    assert list(layers) == ["us", "us-az", "us-ca"]
    federal = {d["key"]: d for d in layers["us"]["screener"]}
    assert [c["path"] for c in federal["us/statute/7/2014"]["cited"]] == ["us/statute/7/2014/e/6/A"]
    assert federal["us/statute/7/2014"]["part"] == "Deductions"
    assert [c["path"] for c in federal["us/statute/7/2015"]["cited"]] == ["us/statute/7/2015"]
    assert federal["https://www.fns.usda.gov/snap/work-requirements"]["scope"] == "in"
    assert federal["https://www.snapscreener.com/blog/x"]["reason"] == "Secondary"
    assert (
        federal["https://www.congress.gov/119/plaws/publ21/PLAW-119publ21.pdf"]["reason"]
        == "Enacting text"
    )
    assert [d["key"] for d in layers["us-az"]["screener"]] == [
        "https://dbmefaapolicy.azdes.gov/FAA5/x.html"
    ]
    assert [d["key"] for d in layers["us-ca"]["screener"]] == [
        "https://www.cdss.ca.gov/acl-25-79.pdf"
    ]
    # The full tier: the screener documents, then the federal law and guidance, then the state's sources.
    federal_full = {d["key"]: d for d in layers["us"]["full"]}
    assert federal_full["us/statute/7/2014"]["sources"] == ["screener", "schema:s1"]
    assert federal_full["us/regulation/7/275/1"]["reason"] == "Administration"
    assert federal_full["us/guidance/usda/fns/snap-fy2027-cola"]["scope"] == "in"
    az_full = [d["key"] for d in layers["us-az"]["full"] if d["scope"] == "in"]
    assert az_full == [
        "https://dbmefaapolicy.azdes.gov/FAA5/x.html",
        "us-az/regulation/aac/6/14",
        "us-az/statute/46",
    ]
    ca_full = [d["key"] for d in layers["us-ca"]["full"]]
    assert "us-ca/manual/x/nutrition" in ca_full and "us-ca/manual/x/child-care" not in ca_full
    # Every layer's full tier holds its screener tier.
    for layer in out["layers"]:
        screener = {d["key"] for d in layer["screener"] if d["scope"] == "in"}
        assert screener <= {d["key"] for d in layer["full"] if d["scope"] == "in"}
    assert out["tiers"][0]["membership"]["fiscal_year"] == 2027


def test_build_program_places_a_state_plan_document_in_its_state_and_never_repeats_a_federal_one(
    tmp_path, monkeypatch
):
    cfg = config(tmp_path, monkeypatch)
    exhibit = "https://www.macpac.gov/exhibit-36.pdf"
    references = {
        "references": [
            # The same page cited from the federal folder and from a state's folder.
            {"url": exhibit, "citation": None, "files": ["parameters/gov/usda/snap/x.yaml"]},
            {
                "url": exhibit,
                "citation": None,
                "states": ["az"],
                "files": ["parameters/gov/states/az/des/snap/x.yaml"],
            },
        ]
    }
    plan = {
        "documents": [
            {
                "id": "AZ-SPA-1",
                "jurisdiction": "US",
                "programs": ["snap"],
                "citation_paths": ["us-az/policy/cms/state-plan/spa-1"],
                "title": "Arizona state plan amendment",
            },
            {
                "id": "AZ-ABAWD-2025",
                "jurisdiction": "US",
                "programs": ["snap"],
                "urls": ["https://www.fns.usda.gov/files/az-abawd-response-fy2027.pdf"],
                "title": "USDA FNS Arizona ABAWD waiver response",
            },
        ]
    }
    cfg["state_url_patterns"] = ["/(?P<state>[a-z]{2})-abawd-response"]
    out = bundle.build_program(cfg, "snap", references, plan, {}, bundle.index_manifests({}, {}))
    layers = {layer["jurisdiction"]: layer for layer in out["layers"]}
    for tier in ("screener", "full"):
        federal = [d["key"] for d in layers["us"][tier]]
        arizona = [d["key"] for d in layers["us-az"][tier]]
        assert exhibit in federal and exhibit not in arizona
        assert "us-az/policy/cms/state-plan/spa-1" in arizona
        assert "us-az/policy/cms/state-plan/spa-1" not in federal
        letter = "https://www.fns.usda.gov/files/az-abawd-response-fy2027.pdf"
        assert letter in arizona and letter not in federal


def test_build_program_joins_an_address_to_the_path_that_holds_it_and_excludes_non_sources(
    tmp_path, monkeypatch
):
    cfg = config(tmp_path, monkeypatch)
    statute = "https://law.example-mirror.com/az/46-292"
    calculator = "https://www.fns.usda.gov/snap/eligibility-calculator"
    cfg["document_paths"] = {statute: "us-az/statute/46/292"}
    cfg["not_sources"] = {calculator: "Calculator: not a source of rules"}
    references = {
        "references": [
            {
                "url": statute,
                "citation": None,
                "states": ["az"],
                "files": ["parameters/gov/states/az/x.yaml"],
            },
            {"url": calculator, "citation": None, "files": ["parameters/gov/usda/snap/x.yaml"]},
        ]
    }
    out = bundle.build_program(cfg, "snap", references, None, {}, bundle.index_manifests({}, {}))
    layers = {layer["jurisdiction"]: layer for layer in out["layers"]}
    arizona = {d["key"]: d for d in layers["us-az"]["screener"]}
    assert arizona["us-az/statute/46/292"]["scope"] == "in"
    federal = {d["key"]: d for d in layers["us"]["screener"]}
    assert federal[calculator]["scope"] == "excluded"
    assert federal[calculator]["reason"] == "Calculator: not a source of rules"


def test_build_program_joins_a_query_routed_rule_only_to_its_own_manifest(tmp_path, monkeypatch):
    # Two Colorado rules from the same script: a SNAP reference to a third rule
    # joins neither (before, all three shared one key and the last manifest won).
    cfg = config(tmp_path, monkeypatch)
    pdf = "https://www.sos.state.co.us/CCR/GenerateRulePdf.do?ruleVersionId={}&fileName={}"
    manifests = {
        "manifests/co.yaml": [
            {
                "citation_path": "us-co/regulation/10-ccr-2505-3",
                "source_url": pdf.format(1, "10 CCR 2505-3"),
            },
            {
                "citation_path": "us-co/regulation/8-ccr-1403-1",
                "source_url": pdf.format(2, "8 CCR 1403-1"),
            },
        ]
    }
    snap = pdf.format(3, "10 CCR 2506-1")
    references = {
        "references": [
            {
                "url": snap,
                "citation": None,
                "states": ["co"],
                "files": ["parameters/gov/usda/snap/x.yaml"],
            },
            {
                "url": pdf.format(2, "8 CCR 1403-1") + "#page=17",
                "citation": None,
                "states": ["co"],
                "files": ["parameters/gov/usda/snap/y.yaml"],
            },
        ]
    }
    cfg["jurisdictions"] = ["az", "ca", "co"]
    cfg["not_sources"] = {pdf.format(9, "1 CCR 201-2"): "Not a source"}
    index = bundle.index_manifests(manifests, {})
    out = bundle.build_program(cfg, "snap", references, None, {}, index)
    layers = {layer["jurisdiction"]: layer for layer in out["layers"]}
    colorado = {d["key"]: d for d in layers["us-co"]["screener"]}
    assert set(colorado) == {bundle.normalize_url(snap), "us-co/regulation/8-ccr-1403-1"}
    assert colorado[bundle.normalize_url(snap)]["scope"] == "in"


def test_build_program_joins_a_manifest_entry_without_a_path_to_the_path_that_holds_it(
    tmp_path, monkeypatch
):
    # A state manifest lists a waiver by its address only; a wave decision says
    # a served path holds that address, so Tier 2 names the path.
    cfg = config(tmp_path, monkeypatch)
    waiver = "https://www.fns.usda.gov/sites/default/files/resource-files/az-snap-waiver.pdf"
    cfg["document_paths"] = {waiver: "us-az/policy/usda/fns/snap-waiver"}
    manifests = {
        "manifests/us-az-snap-primary-policy.yaml": [{"title": "SNAP waiver", "source_url": waiver}]
    }
    index = bundle.index_manifests(manifests, cfg["host_aliases"])
    out = bundle.build_program(cfg, "snap", {"references": []}, None, manifests, index)
    layers = {layer["jurisdiction"]: layer for layer in out["layers"]}
    full = {d["key"]: d for d in layers["us-az"]["full"]}
    assert "us-az/policy/usda/fns/snap-waiver" in full
    assert (
        full["us-az/policy/usda/fns/snap-waiver"]["citation_path"]
        == "us-az/policy/usda/fns/snap-waiver"
    )
    assert waiver not in full


def test_build_program_moves_a_known_source_to_the_path_a_wave_holds_it_at(tmp_path, monkeypatch):
    cfg = config(tmp_path, monkeypatch)
    cfg["path_moves"] = {"us-az/statute/46": "us-az/statute/title-46"}
    out = bundle.build_program(
        cfg, "snap", {"references": []}, None, {}, bundle.index_manifests({}, {})
    )
    layers = {layer["jurisdiction"]: layer for layer in out["layers"]}
    keys = {d["key"] for d in layers["us-az"]["full"]}
    assert "us-az/statute/title-46" in keys and "us-az/statute/46" not in keys


def test_build_program_expands_a_plan_row_that_names_parts_of_a_code(tmp_path, monkeypatch):
    # "USC 26 subtitle-A" names subparts of chapter 1, not the whole subtitle:
    # the config lists their sections, and the bundle names each of them.
    cfg = config(tmp_path, monkeypatch)
    cfg["plan_sections"] = {"USC 26 subtitle-A": ["us/statute/26/21", "us/statute/26/32"]}
    plan = {
        "documents": [
            {
                "id": "USC 26 subtitle-A",
                "jurisdiction": "US",
                "programs": ["snap"],
                "urls": [
                    "https://www.law.cornell.edu/uscode/text/26/subtitle-A/chapter-1/subchapter-A/part-IV/subpart-A"
                ],
                "title": "26 U.S. Code Subpart A - Nonrefundable Personal Credits",
            }
        ]
    }
    out = bundle.build_program(
        cfg, "snap", {"references": []}, plan, {}, bundle.index_manifests({}, {})
    )
    federal = {layer["jurisdiction"]: layer for layer in out["layers"]}["us"]
    keys = {d["key"] for d in federal["screener"]}
    assert {"us/statute/26/21", "us/statute/26/32"} <= keys
    assert not any("subtitle-A" in k for k in keys)


PLAN_ONLY = "Plan-only: not cited by the reference model"


def whole_part_plan(
    tmp_path, monkeypatch, reason: str | None, more_references: list[dict] | None = None
) -> dict:
    """A bundle whose plan names whole parts of a code (26 U.S.C. 21, 32, 36B
    and 42 U.S.C. 1397ll), one of those sections again on a row of its own, and
    a reference that cites another; the plan_sections reason set or not."""
    cfg = config(tmp_path, monkeypatch)
    if reason:
        cfg["exclusions"]["plan_sections"] = reason
    # The program's own law, at a state level: 42 U.S.C. 1397ll.
    (tmp_path / "schema.yaml").write_text(
        yaml.safe_dump(
            {
                "elements": [
                    {
                        "id": "s1",
                        "level": "federal_statute",
                        "citation_path": "us/statute/7/2014/a",
                    },
                    {"id": "c1", "level": "state", "federal_citation": "42 U.S.C. 1397ll"},
                ]
            }
        )
    )
    cfg["plan_sections"] = {
        "USC 26 subtitle-A": ["us/statute/26/21", "us/statute/26/32", "us/statute/26/36B"],
        "USC 42 chapter-7": ["us/statute/42/1397ll"],
    }
    plan = {
        "documents": [
            {
                "id": "USC 26 subtitle-A",
                "jurisdiction": "US",
                "programs": ["snap"],
                "title": "Credits",
            },
            {"id": "USC 42 chapter-7", "jurisdiction": "US", "programs": ["snap"], "title": "CHIP"},
            # A row of its own for 26 U.S.C. 21.
            {"id": "USC 26 21", "jurisdiction": "US", "programs": ["snap"], "title": "26 USC 21"},
        ]
    }
    references = {
        "references": [
            {
                "url": "https://www.law.cornell.edu/uscode/text/26/32#b",
                "citation": "us/statute/26/32/b",
                "files": ["parameters/gov/usda/snap/income/x.yaml"],
            },
            *(more_references or []),
        ]
    }
    return bundle.build_program(cfg, "snap", references, plan, {}, bundle.index_manifests({}, {}))


def test_build_program_moves_a_section_only_a_whole_part_plan_row_brings_in_to_the_full_bundle(
    tmp_path, monkeypatch
):
    # 26 U.S.C. 36B: only the whole-part row names it, and no reference cites
    # it. It leaves the screener tier with the configured reason and stays in
    # the full bundle. 26 U.S.C. 32 (cited), 26 U.S.C. 21 (a row of its own)
    # and 42 U.S.C. 1397ll (the program's own law) stay in the screener tier.
    out = whole_part_plan(tmp_path, monkeypatch, PLAN_ONLY)
    federal = {layer["jurisdiction"]: layer for layer in out["layers"]}["us"]
    screener = {d["key"]: d for d in federal["screener"]}
    assert screener["us/statute/26/36B"]["scope"] == "excluded"
    assert screener["us/statute/26/36B"]["reason"] == PLAN_ONLY
    for key in ("us/statute/26/21", "us/statute/26/32", "us/statute/42/1397ll"):
        assert screener[key]["scope"] == "in", key
        assert "reason" not in screener[key]
    full = {d["key"]: d for d in federal["full"]}
    assert full["us/statute/26/36B"]["scope"] == "in"
    assert full["us/statute/26/36B"]["sources"] == ["plan"]
    assert full["us/statute/26/32"]["sources"] == ["screener"]
    screener_tier, full_tier = out["tiers"]
    assert "whole parts of a code" in screener_tier["membership"]["rule"]
    assert "whole-part plan row" in full_tier["membership"]["rule"]


def test_build_program_keeps_a_whole_part_section_a_reference_cites_with_a_reason(
    tmp_path, monkeypatch
):
    # 26 U.S.C. 36B again, now cited by a reference that is excluded for its own
    # reason (a back-year link). The section is not "not cited by the reference
    # model", so the rule leaves it in the screener tier, as with the rule off.
    back_year = {
        "url": "https://www.law.cornell.edu/uscode/text/26/36B",
        "citation": "us/statute/26/36B",
        "titles": ["FY 2024 premium tax credit table"],
        "files": ["parameters/gov/usda/snap/income/y.yaml"],
    }
    for reason in (PLAN_ONLY, None):
        out = whole_part_plan(tmp_path, monkeypatch, reason, [back_year])
        federal = {layer["jurisdiction"]: layer for layer in out["layers"]}["us"]
        doc = {d["key"]: d for d in federal["screener"]}["us/statute/26/36B"]
        assert doc["scope"] == "in", reason
        assert doc["sources"] == ["policyengine-references", "plan"]
        assert "reason" not in doc
        full = {d["key"]: d for d in federal["full"]}
        assert full["us/statute/26/36B"]["sources"] == ["screener"]


def test_build_program_keeps_whole_part_sections_in_the_screener_tier_without_the_reason(
    tmp_path, monkeypatch
):
    # Without a plan_sections reason, every section of the row stays in the
    # screener tier, and both tiers hold the same sections as with it.
    off = whole_part_plan(tmp_path, monkeypatch, None)
    on = whole_part_plan(tmp_path, monkeypatch, PLAN_ONLY)
    federal_off = {layer["jurisdiction"]: layer for layer in off["layers"]}["us"]
    federal_on = {layer["jurisdiction"]: layer for layer in on["layers"]}["us"]
    screener = {d["key"]: d for d in federal_off["screener"]}
    assert screener["us/statute/26/36B"]["scope"] == "in"
    assert off["tiers"][0]["membership"]["in_scope_by_layer"]["federal"] == 4
    assert on["tiers"][0]["membership"]["in_scope_by_layer"]["federal"] == 3
    assert [d["key"] for d in federal_off["full"]] == [d["key"] for d in federal_on["full"]]
    assert off["tiers"][1]["membership"] == on["tiers"][1]["membership"] | {
        "rule": off["tiers"][1]["membership"]["rule"]
    }
    assert "whole parts" not in off["tiers"][0]["membership"]["rule"]


def test_build_program_excludes_a_plan_document_the_decisions_rule_out(tmp_path, monkeypatch):
    # A plan row whose URL is a not_source is excluded with its reason, as the
    # same URL is when PolicyEngine cites it (wave-6 OUT-OF-SCOPE rows such as
    # MACPAC publications reached the bundles through the plan).
    cfg = config(tmp_path, monkeypatch)
    macstats = "https://www.macpac.gov/publication/chip-spending-by-state/"
    cfg["not_sources"] = {macstats: "Not a source of rules: MACPAC statistics"}
    plan = {
        "documents": [
            {
                "id": "MACPAC-CHIP-SPENDING",
                "jurisdiction": "US",
                "programs": ["snap"],
                "urls": [macstats],
                "title": "MACPAC CHIP spending by state",
            }
        ]
    }
    out = bundle.build_program(
        cfg, "snap", {"references": []}, plan, {}, bundle.index_manifests({}, {})
    )
    federal = {layer["jurisdiction"]: layer for layer in out["layers"]}["us"]
    screener = {d["key"]: d for d in federal["screener"]}
    assert screener[macstats]["scope"] == "excluded"
    assert screener[macstats]["reason"] == "Not a source of rules: MACPAC statistics"
    assert macstats not in {d["key"] for d in federal["full"]}


def test_apply_wave_decisions_joins_held_addresses_and_excludes_non_sources():
    import scripts.apply_wave_decisions as apply

    orders = {
        "https://law.justia.com/az/46-292": {"bundle_url": "https://law.justia.com/az/46-292"},
        "https://example.gov/calculator": {"bundle_url": "https://example.gov/calculator"},
        "https://blocked.gov/x": {"bundle_url": "https://blocked.gov/x"},
        "us/statute/7/2015": {"bundle_url": ""},
        "us-ca/form/official_forms/temp-2250": {
            "bundle_url": "https://www.cdss.ca.gov/temp2250.pdf",
            "bundle_path": "us-ca/form/official_forms/temp-2250",
        },
    }
    decisions = [
        {
            "id": "https://law.justia.com/az/46-292",
            "new_status": "ALREADY-HELD",
            "citation_path": "us-az/statute/46-292",
        },
        {
            "id": "https://example.gov/calculator",
            "new_status": "OUT-OF-SCOPE",
            "note": "an eligibility calculator",
        },
        {"id": "https://blocked.gov/x", "new_status": "OUTREACH"},
        {"id": "us/statute/7/2015", "new_status": "PRESENT", "citation_path": "us/statute/7/2015"},
        {
            "id": "us-ca/form/official_forms/temp-2250",
            "new_status": "PRESENT",
            "citation_path": "us-ca/form/official-forms/temp-2250",
        },
    ]
    out, statuses = apply.joins(orders, decisions, {})
    assert out["document_paths"] == {"https://law.justia.com/az/46-292": "us-az/statute/46-292"}
    assert out["path_moves"] == {
        "us-ca/form/official_forms/temp-2250": "us-ca/form/official-forms/temp-2250"
    }
    assert out["not_sources"] == {
        "https://example.gov/calculator": "Not a source of rules: an eligibility calculator"
    }
    assert statuses == {"ALREADY-HELD": 1, "OUT-OF-SCOPE": 1, "OUTREACH": 1, "PRESENT": 2}


def test_build_program_follows_a_moved_path(tmp_path, monkeypatch):
    cfg = config(tmp_path, monkeypatch)
    cfg["path_moves"] = {"us/statute/7/2014": "us/statute/7/2014-moved"}
    references = {
        "references": [
            {
                "url": "https://law.cornell.edu/uscode/text/7/2014",
                "citation": "us/statute/7/2014",
                "files": ["x.yaml"],
            }
        ]
    }
    out = bundle.build_program(cfg, "snap", references, None, {}, bundle.index_manifests({}, {}))
    federal = [d["key"] for d in out["layers"][0]["screener"]]
    assert federal == ["us/statute/7/2014-moved"]


def _release(tmp_path, rows_by_scope: dict[tuple[str, str, str], list[dict]]) -> None:
    """A selector named `pin` and the provision file of each of its scopes."""
    scopes = [{"jurisdiction": j, "document_class": c, "version": v} for j, c, v in rows_by_scope]
    selectors = tmp_path / "manifests/releases"
    selectors.mkdir(parents=True)
    (selectors / "pin.json").write_text(json.dumps({"name": "pin", "scopes": scopes}))
    for (j, c, v), rows in rows_by_scope.items():
        provisions = tmp_path / "data/corpus/provisions" / j / c / f"{v}.jsonl"
        provisions.parent.mkdir(parents=True, exist_ok=True)
        provisions.write_text("".join(json.dumps(row) + "\n" for row in rows))


def test_release_text_paths_hold_each_path_with_a_body_and_every_path_above_it(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(bundle, "REPO", tmp_path)
    _release(
        tmp_path,
        {
            ("us", "statute", "v1"): [
                {"citation_path": "us/statute/26", "body": None},
                {"citation_path": "us/statute/26/101", "body": ""},
                {"citation_path": "us/statute/26/101/a", "body": "Gross income does not include"},
                {"citation_path": "us/statute/26/103", "body": "   "},
                {"citation_path": None, "body": "no path"},
            ],
            ("us-az", "manual", "v2"): [{"citation_path": "us-az/manual/faa/1", "body": "text"}],
        },
    )
    # An unselected scope's text is not served, although the corpus holds it.
    unselected = tmp_path / "data/corpus/provisions/us/statute/other.jsonl"
    unselected.write_text(json.dumps({"citation_path": "us/statute/26/105", "body": "text"}) + "\n")

    paths = bundle.release_text_paths("pin")

    assert paths == {
        "us",
        "us/statute",
        "us/statute/26",
        "us/statute/26/101",
        "us/statute/26/101/a",
        "us-az",
        "us-az/manual",
        "us-az/manual/faa",
        "us-az/manual/faa/1",
    }


def test_release_text_paths_follow_parent_rows_to_a_container_at_another_path(
    tmp_path, monkeypatch
):
    """42 CFR 435 subpart D holds 435.300 and on, at paths that are not under its own."""
    monkeypatch.setattr(bundle, "REPO", tmp_path)
    _release(
        tmp_path,
        {
            ("us", "regulation", "v1"): [
                {"id": "part", "citation_path": "us/regulation/42/435", "body": None},
                {
                    "id": "d",
                    "parent_id": "part",
                    "citation_path": "us/regulation/42/435/subpart-D",
                    "body": None,
                },
                {
                    "id": "e",
                    "parent_id": "part",
                    "citation_path": "us/regulation/42/435/subpart-E",
                    "body": None,
                },
                {
                    "id": "300",
                    "parent_id": "d",
                    "citation_path": "us/regulation/42/435/300",
                    "body": "This subpart specifies",
                },
                # A row that names itself as its parent does not loop.
                {
                    "id": "x",
                    "parent_id": "x",
                    "citation_path": "us/regulation/42/435/4",
                    "body": "t",
                },
            ]
        },
    )

    paths = bundle.release_text_paths("pin")

    assert "us/regulation/42/435/subpart-D" in paths
    assert "us/regulation/42/435/subpart-E" not in paths
    assert "us/regulation/42/435/4" in paths


def test_release_text_paths_name_the_fetch_for_a_scope_that_is_not_in_the_checkout(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(bundle, "REPO", tmp_path)
    _release(tmp_path, {("us", "statute", "v1"): []})
    (tmp_path / "data/corpus/provisions/us/statute/v1.jsonl").unlink()
    with pytest.raises(SystemExit, match="corpus fetch --release pin"):
        bundle.release_text_paths("pin")


def _doc(path: str | None, scope: str = "in") -> dict:
    return {"key": path or "https://example.gov/x", "citation_path": path, "scope": scope}


def test_stamp_release_text_marks_each_document_and_counts_in_scope_ones_by_layer():
    built = {
        "tiers": [{"membership": {}}, {"membership": {}}],
        "layers": [
            {
                "jurisdiction": "us",
                "screener": [_doc("us/statute/26/101"), _doc("us/statute/26/105")],
                "full": [_doc("us/statute/26/101"), _doc("us/statute/26/101", scope="out")],
            },
            {
                "jurisdiction": "us-az",
                "screener": [_doc("us-az/manual/faa/1"), _doc(None)],
                "full": [_doc("us-az/manual/faa/1")],
            },
        ],
    }
    paths = {"us/statute/26/101", "us-az/manual/faa/1"}

    bundle.stamp_release_text(built, "pin", paths)

    us, az = built["layers"]
    assert [d["release_text"] for d in us["screener"]] == [True, False]
    assert [d["release_text"] for d in us["full"]] == [True, True]
    assert [d["release_text"] for d in az["screener"]] == [True, False]
    assert built["encoder_release"]["name"] == "pin"
    assert [t["membership"]["release_text_by_layer"] for t in built["tiers"]] == [
        {"federal": 1, "state": 1},
        {"federal": 1, "state": 1},  # the out-of-scope document is marked but not counted
    ]


def _build_snap(tmp_path, monkeypatch, **extra) -> dict:
    cfg = {**config(tmp_path, monkeypatch), **extra}
    (tmp_path / "config.yaml").write_text(yaml.safe_dump(cfg))
    (tmp_path / "refs-snap.json").write_text(
        json.dumps(
            {
                "references": [
                    {
                        "url": "https://law.cornell.edu/uscode/text/7/2014#e_6_A",
                        "citation": "us/statute/7/2014/e/6/A",
                        "files": ["parameters/gov/usda/snap/income/deductions/x.yaml"],
                    },
                    {
                        "url": "https://law.cornell.edu/uscode/text/7/2015",
                        "citation": "us/statute/7/2015",
                        "files": ["parameters/gov/usda/snap/income/deductions/x.yaml"],
                    },
                ]
            }
        )
    )
    monkeypatch.setattr(bundle, "load_manifests", lambda: {})
    return bundle.build(tmp_path / "config.yaml")["snap"]


def test_build_records_release_text_only_when_the_config_names_a_release(tmp_path, monkeypatch):
    _release(
        tmp_path,
        {("us", "statute", "v1"): [{"citation_path": "us/statute/7/2014/e/6", "body": "text"}]},
    )

    plain = _build_snap(tmp_path, monkeypatch)
    stamped = _build_snap(tmp_path, monkeypatch, encoder_release="pin")

    assert "encoder_release" not in plain
    assert all(
        "release_text" not in doc
        for layer in plain["layers"]
        for tier in ("screener", "full")
        for doc in layer[tier]
    )
    federal = {d["key"]: d["release_text"] for d in stamped["layers"][0]["screener"]}
    assert federal == {"us/statute/7/2014": True, "us/statute/7/2015": False}
    assert stamped["tiers"][0]["membership"]["release_text_by_layer"] == {"federal": 1, "state": 0}
    # Nothing else moves: without the stamps, the two builds are the same bundle.
    for layer in stamped["layers"]:
        for tier in ("screener", "full"):
            for doc in layer[tier]:
                del doc["release_text"]
    del stamped["encoder_release"]
    for tier in stamped["tiers"]:
        del tier["membership"]["release_text_by_layer"]
    assert stamped == plain
