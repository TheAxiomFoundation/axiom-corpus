import json

import pytest
import yaml

from axiom_corpus.corpus.cli import main
from axiom_corpus.corpus.policyengine_references import (
    PolicyEngineReferenceScope,
    scan_policyengine_references,
)
from axiom_corpus.corpus.releases import ReleaseManifest, ReleaseScope
from axiom_corpus.corpus.source_discovery import (
    DiscoveryDisposition,
    SourceStatus,
    build_source_discovery_report,
)
from axiom_corpus.corpus.source_promotion import promote_source_discovery_group


def test_source_discovery_classifies_static_external_urls(tmp_path):
    urls = tmp_path / "policyengine_urls.txt"
    urls.write_text(
        "\n".join(
            [
                "https://www.irs.gov/instructions/i1040gi?utm_source=test",
                "https://aspe.hhs.gov/topics/poverty-economic-mobility/poverty-guidelines",
                "https://ftb.ca.gov/forms/misc/1001.pdf#page=2",
                "https://law.cornell.edu/cfr/text/26/1.402(g)-1#old",
                "https://law.cornell.edu/cfr/text/26/1.402(g)-1#new",
                "https://advance.lexis.com/documentpage/?crid=abc",
                "https://docs.google.com/spreadsheets/d/example/edit",
                "not a url",
            ]
        )
    )
    release = ReleaseManifest(
        name="current",
        scopes=(ReleaseScope("us-ca", "form", "2026-05-11"),),
    )

    report = build_source_discovery_report(
        (urls,),
        release=release,
        generated_at="2026-05-11T12:00:00+00:00",
    )
    rows = {row.host: row for row in report.rows}

    assert report.raw_url_count == 8
    assert report.invalid_url_count == 1
    assert report.unique_url_count == 6
    assert rows["irs.gov"].source_status is SourceStatus.PRIMARY_OFFICIAL
    assert rows["irs.gov"].disposition is DiscoveryDisposition.READY_FOR_MANIFEST
    assert rows["irs.gov"].document_class == "form"
    assert rows["irs.gov"].jurisdiction == "us"
    assert rows["aspe.hhs.gov"].source_status is SourceStatus.PRIMARY_OFFICIAL
    assert rows["aspe.hhs.gov"].disposition is DiscoveryDisposition.READY_FOR_MANIFEST
    assert rows["aspe.hhs.gov"].document_class == "guidance"
    assert rows["aspe.hhs.gov"].jurisdiction == "us"
    assert rows["ftb.ca.gov"].release_scope_present is True
    assert rows["law.cornell.edu"].source_status is SourceStatus.SECONDARY_MIRROR
    assert rows["law.cornell.edu"].disposition is DiscoveryDisposition.EXCLUDED_SECONDARY
    assert rows["law.cornell.edu"].input_count == 2
    assert rows["advance.lexis.com"].disposition is DiscoveryDisposition.BLOCKED_VENDOR_ONLY
    assert rows["docs.google.com"].disposition is DiscoveryDisposition.NEEDS_REVIEW

    payload = report.to_mapping()
    assert payload["ready_for_manifest_count"] == 3
    assert payload["needs_review_count"] == 1
    assert payload["blocked_or_excluded_count"] == 2
    assert payload["release_scope_present_count"] == 1
    assert payload["source_status_counts"]["primary_official"] == 3
    assert payload["ready_group_count"] == 2
    assert [row["group_key"] for row in payload["group_rows"]] == [
        "us/form/individual_income_tax_forms",
        "us/guidance/poverty_guidelines",
    ]
    assert payload["group_rows"][0]["suggested_manifest_stem"] == (
        "us-individual-income-tax-forms"
    )


def test_source_discovery_classifies_uk_official_policy_sources(tmp_path):
    urls = tmp_path / "policyengine_uk_urls.txt"
    urls.write_text(
        "\n".join(
            [
                "https://www.legislation.gov.uk/ukpga/2003/1/section/1",
                "https://www.legislation.gov.uk/uksi/2013/376/regulation/36",
                "https://www.gov.uk/government/publications/benefit-and-pension-rates-2024-to-2025",
                "https://obr.uk/docs/dlm_uploads/NICS-Cut-Impact-on-Labour-Supply-Note.pdf",
                "https://www.lexisnexis.co.uk/example",
            ]
        )
    )

    report = build_source_discovery_report(
        (urls,),
        release=ReleaseManifest(name="current", scopes=()),
        generated_at="2026-05-23T12:00:00+00:00",
        source_name="policyengine",
    )
    rows = {row.canonical_url: row for row in report.rows}

    act = rows["https://legislation.gov.uk/ukpga/2003/1/section/1"]
    instrument = rows["https://legislation.gov.uk/uksi/2013/376/regulation/36"]
    govuk = rows[
        "https://gov.uk/government/publications/benefit-and-pension-rates-2024-to-2025"
    ]
    obr = rows[
        "https://obr.uk/docs/dlm_uploads/NICS-Cut-Impact-on-Labour-Supply-Note.pdf"
    ]
    vendor = rows["https://lexisnexis.co.uk/example"]

    assert act.source_status is SourceStatus.PRIMARY_OFFICIAL
    assert act.jurisdiction == "uk"
    assert act.document_class == "statute"
    assert instrument.document_class == "regulation"
    assert govuk.jurisdiction == "uk"
    assert govuk.disposition is DiscoveryDisposition.READY_FOR_MANIFEST
    assert obr.source_status is SourceStatus.PRIMARY_OFFICIAL
    assert vendor.disposition is DiscoveryDisposition.BLOCKED_VENDOR_ONLY


def test_source_discovery_cli_writes_report(tmp_path, capsys):
    source = tmp_path / "state_references.txt"
    source.write_text("https://leg.colorado.gov/colorado-revised-statutes\n")
    output = tmp_path / "analytics" / "source-discovery-current.json"

    exit_code = main(
        [
            "source-discovery",
            "--base",
            str(tmp_path),
            "--input",
            str(source),
            "--release",
            "",
            "--output",
            str(output),
        ]
    )
    printed = json.loads(capsys.readouterr().out)
    written = json.loads(output.read_text())

    assert exit_code == 0
    assert printed["written_to"] == str(output)
    assert written["unique_url_count"] == 1
    assert written["ready_group_count"] == 1
    assert written["group_rows"][0]["group_key"] == "us-co/statute/statute"
    assert written["rows"][0]["jurisdiction"] == "us-co"
    assert written["rows"][0]["disposition"] == "ready_for_manifest"


def test_source_discovery_cli_uses_inventory_urls_for_release_coverage(tmp_path, capsys):
    source = tmp_path / "federal_references.txt"
    medicaid_url = (
        "https://www.medicaid.gov/medicaid/national-medicaid-chip-program-information/"
        "medicaid-childrens-health-insurance-program-basic-health-program-eligibility-levels"
    )
    source.write_text(
        "\n".join(
            [
                f"{medicaid_url}/index.html",
                "https://www.cbo.gov/system/files/2025-01/53724-2025-01-Tax-Parameters.xlsx",
            ]
        )
    )
    release_path = tmp_path / "releases" / "current.json"
    release_path.parent.mkdir(parents=True)
    release_path.write_text(
        json.dumps(
            {
                "name": "current",
                "scopes": [
                    {
                        "jurisdiction": "us",
                        "document_class": "form",
                        "version": "covered-form",
                    }
                ],
            }
        )
    )
    inventory_path = tmp_path / "inventory" / "us" / "form" / "covered-form.json"
    inventory_path.parent.mkdir(parents=True)
    inventory_path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "citation_path": "us/form/cms/medicaid-chip-bhp-eligibility-levels",
                        "source_url": medicaid_url,
                    }
                ]
            }
        )
    )
    output = tmp_path / "analytics" / "source-discovery-current.json"

    exit_code = main(
        [
            "source-discovery",
            "--base",
            str(tmp_path),
            "--input",
            str(source),
            "--output",
            str(output),
        ]
    )
    capsys.readouterr()
    written = json.loads(output.read_text())
    rows = {row["host"]: row for row in written["rows"]}
    group_keys = {row["group_key"] for row in written["group_rows"]}

    assert exit_code == 0
    assert rows["medicaid.gov"]["release_scope_present"] is True
    assert rows["cbo.gov"]["release_scope_present"] is False
    assert "us/form/federal_tax_parameters" in group_keys
    assert "us/form/medicaid_chip_eligibility_levels" not in group_keys


def test_promote_source_discovery_group_cli_writes_official_document_manifest(
    tmp_path,
    capsys,
):
    report_path = tmp_path / "source-discovery.json"
    output_path = tmp_path / "manifests" / "us-snap-guidance.yaml"
    report_path.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "raw_url": "https://fns.usda.gov/snap/current-guidance.pdf#page=3",
                        "canonical_url": "https://fns.usda.gov/snap/current-guidance.pdf",
                        "host": "fns.usda.gov",
                        "source_list": "policyengine-us",
                        "input_count": 4,
                        "source_status": "primary_official",
                        "disposition": "ready_for_manifest",
                        "document_class": "guidance",
                        "jurisdiction": "us",
                        "release_scope_present": False,
                        "fragment": "page=3",
                        "reason": "ready",
                        "reference_count": 2,
                        "sample_reference_paths": [
                            "policyengine-us#policyengine_us/parameters/snap.yaml:5#snap"
                        ],
                    },
                    {
                        "raw_url": "https://fns.usda.gov/snap/html-guidance",
                        "canonical_url": "https://fns.usda.gov/snap/html-guidance",
                        "host": "fns.usda.gov",
                        "source_list": "policyengine-us",
                        "input_count": 1,
                        "source_status": "primary_official",
                        "disposition": "ready_for_manifest",
                        "document_class": "guidance",
                        "jurisdiction": "us",
                        "release_scope_present": False,
                        "fragment": None,
                        "reason": "ready",
                    },
                    {
                        "raw_url": "https://example.com/snap-summary",
                        "canonical_url": "https://example.com/snap-summary",
                        "host": "example.com",
                        "source_list": "policyengine-us",
                        "input_count": 5,
                        "source_status": "unknown",
                        "disposition": "needs_review",
                        "document_class": "guidance",
                        "jurisdiction": "us",
                        "release_scope_present": False,
                        "fragment": None,
                        "reason": "review",
                    },
                ]
            }
        )
    )

    exit_code = main(
        [
            "promote-source-discovery-group",
            "--report",
            str(report_path),
            "--group-key",
            "us/guidance/snap_guidance",
            "--output",
            str(output_path),
            "--source-as-of",
            "2026-05-23",
            "--rewrite-url",
            (
                "https://fns.usda.gov/snap/html-guidance="
                "https://fns.usda.gov/snap/html-guidance-current"
            ),
        ]
    )
    printed = json.loads(capsys.readouterr().out)
    manifest = yaml.safe_load(output_path.read_text())

    assert exit_code == 0
    assert printed["document_count"] == 2
    assert [doc["source_format"] for doc in manifest["documents"]] == ["pdf", "html"]
    assert manifest["documents"][0]["source_as_of"] == "2026-05-23"
    assert manifest["documents"][0]["citation_path"].startswith(
        "us/guidance/snap_guidance/fns.usda.gov/"
    )
    assert manifest["documents"][0]["metadata"]["discovered_via"] == [
        "policyengine-us#policyengine_us/parameters/snap.yaml:5#snap"
    ]
    assert (
        manifest["documents"][1]["source_url"]
        == "https://fns.usda.gov/snap/html-guidance-current"
    )
    assert (
        manifest["documents"][1]["metadata"]["source_discovery_canonical_url"]
        == "https://fns.usda.gov/snap/html-guidance"
    )
    assert manifest["documents"][1]["metadata"]["source_url_rewritten"] is True


def test_promote_source_discovery_group_requires_adapter_for_unsupported_formats(
    tmp_path,
):
    report_path = tmp_path / "source-discovery.json"
    report_path.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "raw_url": "https://irs.gov/pub/irs-soi/tax-parameters.xlsx",
                        "canonical_url": "https://irs.gov/pub/irs-soi/tax-parameters.xlsx",
                        "host": "irs.gov",
                        "source_list": "policyengine-us",
                        "input_count": 1,
                        "source_status": "primary_official",
                        "disposition": "ready_for_manifest",
                        "document_class": "form",
                        "jurisdiction": "us",
                        "release_scope_present": False,
                        "fragment": None,
                        "reason": "ready",
                    }
                ]
            }
        )
    )

    with pytest.raises(ValueError, match="need a non-HTML/PDF adapter"):
        promote_source_discovery_group(
            report_path=report_path,
            group_key="us/form/federal_tax_parameters",
            output_path=tmp_path / "manifest.yaml",
        )


def test_promote_source_discovery_group_disambiguates_duplicate_citation_paths(
    tmp_path,
):
    report_path = tmp_path / "source-discovery.json"
    output_path = tmp_path / "manifest.yaml"
    report_path.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "raw_url": "https://revenue.wi.gov/TaxForms2021/FormA.pdf",
                        "canonical_url": "https://revenue.wi.gov/TaxForms2021/FormA.pdf",
                        "host": "revenue.wi.gov",
                        "source_list": "policyengine-us",
                        "input_count": 1,
                        "source_status": "primary_official",
                        "disposition": "ready_for_manifest",
                        "document_class": "form",
                        "jurisdiction": "us-wi",
                        "release_scope_present": False,
                        "fragment": None,
                        "reason": "ready",
                    },
                    {
                        "raw_url": "https://revenue.wi.gov/TaxForms2021/forma.pdf",
                        "canonical_url": "https://revenue.wi.gov/TaxForms2021/forma.pdf",
                        "host": "revenue.wi.gov",
                        "source_list": "policyengine-us",
                        "input_count": 1,
                        "source_status": "primary_official",
                        "disposition": "ready_for_manifest",
                        "document_class": "form",
                        "jurisdiction": "us-wi",
                        "release_scope_present": False,
                        "fragment": None,
                        "reason": "ready",
                    },
                ]
            }
        )
    )

    promote_source_discovery_group(
        report_path=report_path,
        group_key="us-wi/form/tax_forms",
        output_path=output_path,
    )
    documents = yaml.safe_load(output_path.read_text())["documents"]
    citation_paths = [document["citation_path"] for document in documents]

    assert len(citation_paths) == len(set(citation_paths))
    assert all("source_discovery_base_citation_path" in doc["metadata"] for doc in documents)


def test_policyengine_reference_scanner_preserves_policy_provenance(tmp_path):
    repo = tmp_path / "policyengine-us"
    parameter = (
        repo
        / "policyengine_us"
        / "parameters"
        / "gov"
        / "irs"
        / "standard_deduction.yaml"
    )
    variable = (
        repo
        / "policyengine_us"
        / "variables"
        / "gov"
        / "irs"
        / "income_tax.py"
    )
    on_demand_parameter = (
        repo
        / "policyengine_us"
        / "params_on_demand"
        / "gov"
        / "hhs"
        / "medicaid"
        / "geography"
        / "medicaid_rating_area.yaml"
    )
    readme = repo / "README.md"
    parameter.parent.mkdir(parents=True)
    variable.parent.mkdir(parents=True)
    on_demand_parameter.parent.mkdir(parents=True)
    parameter.write_text(
        "\n".join(
            [
                "description: Standard deduction.",
                "metadata:",
                "  reference:",
                "  - title: 26 U.S.C. § 63(c)",
                "    href: https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title26-section63",
                "CO:",
                "  # https://www.sos.state.co.us/CCR/GenerateRulePdf.do?ruleVersionId=10492",
                "  2026-01-01: 1",
            ]
        )
    )
    variable.write_text(
        "\n".join(
            [
                "class income_tax:",
                "    reference = {",
                '        "title": "26 U.S.C. § 1",',
                '        "href": "https://www.law.cornell.edu/uscode/text/26/1",',
                "    }",
                "",
                "class income_tax_pre_charges:",
                "    reference = dict(",
                '        title="Income Tax Act 2007 s. 23",',
                '        href="https://www.legislation.gov.uk/ukpga/2007/3/section/23",',
                "    )",
                "",
                "class adjacent_literal_urls:",
                "    reference = (",
                '        "https://first.example/statute"',
                '        "https://second.example/regulation"',
                "    )",
                "",
                "class adjacent_slash_literal_urls:",
                "    reference = (",
                '        "https://slash-first.example/"',
                '        "https://slash-second.example/"',
                "    )",
                "",
                "class adjacent_prefix_suffix_url:",
                "    reference = (",
                '        "https://prefix.example/"',
                '        "source"',
                "    )",
                "",
                "class nested_url_wrappers:",
                "    reference = [",
                '        "https://web.archive.org/web/20250324135334/https://example.gov/source",',
                '        "https://www.azleg.gov/viewdocument/?docName=https://example.gov/source",',
                "    ]",
            ]
        )
    )
    on_demand_parameter.write_text(
        "\n".join(
            [
                "metadata:",
                "  reference:",
                "    - title: CMS rating area data",
                "      href: https://www.cms.gov/cciio/programs-and-initiatives/health-insurance-market-reforms/state-gra",
            ]
        )
    )
    readme.write_text("https://policyengine.org/us\n")

    records = scan_policyengine_references(
        repo,
        project="policyengine-us",
        upstream_commit="abc123",
        scope=PolicyEngineReferenceScope.POLICY,
    )
    mappings = [record.to_mapping() for record in records]
    urls = {record.reference_url for record in records if record.reference_url}
    citations = {record.citation_text for record in records if record.citation_text}

    assert "https://policyengine.org/us" not in urls
    assert "https://www.law.cornell.edu/uscode/text/26/1" in urls
    assert (
        "https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title26-section63"
        in urls
    )
    assert "https://www.sos.state.co.us/CCR/GenerateRulePdf.do?ruleVersionId=10492" in urls
    assert "https://www.legislation.gov.uk/ukpga/2007/3/section/23" in urls
    assert (
        "https://www.cms.gov/cciio/programs-and-initiatives/health-insurance-market-reforms/state-gra"
        in urls
    )
    assert "https://first.example/statute" in urls
    assert "https://second.example/regulation" in urls
    assert "https://slash-first.example/" in urls
    assert "https://slash-second.example/" in urls
    assert "https://prefix.example/" in urls
    assert (
        "https://web.archive.org/web/20250324135334/https://example.gov/source"
        in urls
    )
    assert "https://www.azleg.gov/viewdocument/?docName=https://example.gov/source" in urls
    assert "https://web.archive.org/web/20250324135334/" not in urls
    assert "https://www.azleg.gov/viewdocument/?docName=" not in urls
    assert (
        "https://first.example/statutehttps://second.example/regulation"
        not in urls
    )
    assert "https://slash-first.example/https://slash-second.example/" not in urls
    assert "https://prefix.example/source" not in urls
    assert "26 U.S.C. § 63(c)" in citations
    assert "26 U.S.C. § 1" in citations
    assert "Income Tax Act 2007 s. 23" in citations
    assert "CMS rating area data" in citations
    assert "title" not in citations
    assert "href" not in citations
    assert {
        (row["file_path"], row["source_type"], row["symbol_path"])
        for row in mappings
        if row["reference_url"] == "https://www.law.cornell.edu/uscode/text/26/1"
    } == {
        (
            "policyengine_us/variables/gov/irs/income_tax.py",
            "variable",
            "income_tax",
        )
    }
    assert {
        row["symbol_path"]
        for row in mappings
        if row["reference_url"]
        == "https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title26-section63"
    } == {"gov.irs.standard_deduction"}
    assert {
        (row["source_type"], row["symbol_path"])
        for row in mappings
        if row["reference_url"]
        == "https://www.cms.gov/cciio/programs-and-initiatives/health-insurance-market-reforms/state-gra"
    } == {("parameter", "gov.hhs.medicaid.geography.medicaid_rating_area")}
    assert {
        (row["symbol_path"], row["line"])
        for row in mappings
        if row["reference_url"] == "https://second.example/regulation"
    } == {("adjacent_literal_urls", 16)}
    assert {
        (row["symbol_path"], row["line"])
        for row in mappings
        if row["reference_url"] == "https://slash-second.example/"
    } == {("adjacent_slash_literal_urls", 22)}
    assert {
        (row["symbol_path"], row["line"])
        for row in mappings
        if row["reference_url"] == "https://prefix.example/"
    } == {("adjacent_prefix_suffix_url", 27)}


def test_policyengine_references_cli_writes_jsonl_and_url_inventory(tmp_path, capsys):
    repo = tmp_path / "policyengine-uk"
    parameter = (
        repo
        / "policyengine_uk"
        / "parameters"
        / "gov"
        / "hmrc"
        / "personal_allowance.yaml"
    )
    readme = repo / "docs" / "notes.md"
    parameter.parent.mkdir(parents=True)
    readme.parent.mkdir(parents=True)
    parameter.write_text(
        "\n".join(
            [
                "metadata:",
                "  reference:",
                "  - href: https://www.legislation.gov.uk/ukpga/2007/3/section/35",
                "  - Income Tax Act 2007 s. 35",
            ]
        )
    )
    readme.write_text("https://policyengine.org/uk/research/example\n")
    output = tmp_path / "references.jsonl"
    url_output = tmp_path / "urls.txt"

    exit_code = main(
        [
            "policyengine-references",
            "--repo",
            str(repo),
            "--scope",
            "policy",
            "--output",
            str(output),
            "--url-output",
            str(url_output),
        ]
    )
    printed = json.loads(capsys.readouterr().out)
    rows = [json.loads(line) for line in output.read_text().splitlines()]
    urls = url_output.read_text().splitlines()

    assert exit_code == 0
    assert printed["reference_count"] == 2
    assert printed["url_reference_count"] == 1
    assert printed["citation_reference_count"] == 1
    assert printed["project_counts"] == {"policyengine-uk": 2}
    assert urls == ["https://www.legislation.gov.uk/ukpga/2007/3/section/35"]
    assert rows[0]["file_path"] == (
        "policyengine_uk/parameters/gov/hmrc/personal_allowance.yaml"
    )
    assert rows[0]["symbol_path"] == "gov.hmrc.personal_allowance"

    discovery_output = tmp_path / "source-discovery.json"
    discovery_exit_code = main(
        [
            "source-discovery",
            "--base",
            str(tmp_path),
            "--release",
            "",
            "--reference-input",
            str(output),
            "--output",
            str(discovery_output),
        ]
    )
    capsys.readouterr()
    discovery = json.loads(discovery_output.read_text())

    assert discovery_exit_code == 0
    assert discovery["unique_url_count"] == 1
    assert discovery["rows"][0]["source_list"] == "policyengine-uk"
    assert discovery["rows"][0]["reference_count"] == 1
    assert discovery["rows"][0]["sample_reference_paths"] == [
        (
            "policyengine-uk#"
            "policyengine_uk/parameters/gov/hmrc/personal_allowance.yaml:3#"
            "gov.hmrc.personal_allowance"
        )
    ]
