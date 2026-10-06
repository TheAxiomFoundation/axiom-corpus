from __future__ import annotations

import yaml

import scripts.export_policyengine_references as export


def test_yaml_references_read_every_href_with_its_title():
    doc = yaml.load(
        """
description: SUA by state.
metadata:
  reference:
    - title: 7 CFR 273.9(d)(6)(iii)
      href: https://www.ecfr.gov/current/title-7/section-273.9#p-273.9(d)(6)(iii)
    - https://www.fns.usda.gov/snap/eligibility/deduction/standard-utility-allowances
AZ:
  metadata:
    reference:
      - title: Arizona FAA6
        href: https://dbmefaapolicy.azdes.gov/
  0000-01-01: 1
""",
        Loader=yaml.BaseLoader,
    )
    assert export.yaml_references(doc) == [
        (
            "https://www.ecfr.gov/current/title-7/section-273.9#p-273.9(d)(6)(iii)",
            "7 CFR 273.9(d)(6)(iii)",
        ),
        ("https://www.fns.usda.gov/snap/eligibility/deduction/standard-utility-allowances", None),
        ("https://dbmefaapolicy.azdes.gov/", "Arizona FAA6"),
    ]


def test_python_references_read_the_reference_assignment_only():
    text = """
class snap_gross_income(Variable):
    value_type = float
    reference = (
        "https://www.law.cornell.edu/uscode/text/7/2014#d",
        "https://www.ecfr.gov/current/title-7/section-273.9#p-273.9(b)",
    )
    documentation = "See https://example.org/not-a-reference"

    def formula(spm_unit, period, parameters):
        return 0
"""
    assert [url for url, _ in export.python_references(text)] == [
        "https://www.law.cornell.edu/uscode/text/7/2014#d",
        "https://www.ecfr.gov/current/title-7/section-273.9#p-273.9(b)",
    ]


def test_citation_from_url_reads_structured_urls():
    assert export.citation_from_url("https://www.law.cornell.edu/uscode/text/7/2014#e_6_A") == (
        "statute",
        "us/statute/7/2014/e/6/A",
    )
    assert export.citation_from_url(
        "https://www.ecfr.gov/current/title-7/section-273.9#p-273.9(d)(6)(iii)"
    ) == ("regulation", "us/regulation/7/273/9/d/6/iii")
    assert export.citation_from_url(
        "https://www.govinfo.gov/content/pkg/USCODE-2023-title7/pdf/USCODE-2023-title7-chap51-sec2015.pdf"
    ) == ("statute", "us/statute/7/2015")
    assert export.citation_from_url("https://secure.ssa.gov/poms.nsf/lnx/0501401001") == (
        "manual",
        "us/manual/ssa/poms/si/01401.001",
    )
    assert export.citation_from_url("https://www.fns.usda.gov/snap/work-requirements") is None
