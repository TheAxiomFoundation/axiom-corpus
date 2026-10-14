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


def test_resolve_release_takes_the_newest_published_version_and_its_release_commit(
    monkeypatch, tmp_path
):
    calls = []

    def fake_git(checkout, *args):
        calls.append(args)
        if args[0] == "log":
            # The release commit is the oldest commit that set the version.
            return {"2.29.10": "f47ba56\n4c900b6\n", "2.29.11": "4c900b6\n"}[args[4].split('"')[1]]
        if args[0] == "show":
            return 'name = "policyengine-us"\nversion = "2.29.11"\n'
        return ""

    monkeypatch.setattr(export, "git", fake_git)
    # PyPI's newest can trail main by a release that is still publishing.
    monkeypatch.setattr(export, "newest_published", lambda: "2.29.10")
    assert export.resolve_release(tmp_path, "latest") == ("2.29.10", "f47ba56")
    assert calls[0] == ("fetch", "--quiet", "origin", "main")
    # A version number holds that release.
    assert export.resolve_release(tmp_path, "2.29.11") == ("2.29.11", "4c900b6")
    # Without PyPI, main's own version.
    monkeypatch.setattr(export, "newest_published", lambda: None)
    assert export.resolve_release(tmp_path, "latest") == ("2.29.11", "4c900b6")


def test_programs_of_reads_federal_folders_and_each_state_s_program_folder():
    programs = {
        "snap": {"policyengine_folders": ["gov/usda/snap", "gov/hhs/fpg"], "state_folders": "snap"},
        "ccdf": {"policyengine_folders": ["gov/hhs/ccdf"], "state_folders": "ccap|ccdf"},
        "income_tax": {"policyengine_folders": ["gov/irs"], "state_folders": "^tax/income"},
    }
    assert export.programs_of("policyengine_us/parameters/gov/usda/snap/x.yaml", programs) == [
        ("snap", None)
    ]
    assert export.programs_of("policyengine_us/parameters/gov/hhs/fpg/x.yaml", programs) == [
        ("snap", None)
    ]
    # An agency, then the program; or the program directly.
    assert export.programs_of(
        "policyengine_us/parameters/gov/states/az/des/ccap/x.yaml", programs
    ) == [("ccdf", "az")]
    assert export.programs_of("policyengine_us/variables/gov/states/nj/snap/x.py", programs) == [
        ("snap", "nj")
    ]
    assert export.programs_of(
        "policyengine_us/parameters/gov/states/ca/tax/income/x.yaml", programs
    ) == [("income_tax", "ca")]
    assert (
        export.programs_of("policyengine_us/parameters/gov/states/ca/cdss/tanf/x.yaml", programs)
        == []
    )
