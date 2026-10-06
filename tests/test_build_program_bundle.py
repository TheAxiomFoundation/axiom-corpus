from __future__ import annotations

import datetime as dt

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
