import json

import httpx
import pytest

from axiom_corpus.fetchers.nz_legislation_api import (
    NZLegislationAPIClient,
    NZLegislationAPIError,
    download_nz_legislation_api_sources,
)


def _work_row():
    return {
        "work_id": "act_public_1990_109",
        "legislation_type": "act",
        "legislation_status": "in_force",
        "publisher": "Parliamentary Counsel Office",
        "latest_matching_version": {
            "title": "New Zealand Bill of Rights Act 1990",
            "version_id": "act_public_1990_109_en_2022-08-30",
            "is_latest_version": True,
            "formats": [
                {
                    "type": "html",
                    "url": "https://www.legislation.govt.nz/act/public/1990/109/en/2022-08-30/",
                },
                {
                    "type": "xml",
                    "url": "https://www.legislation.govt.nz/act/public/1990/109/en/2022-08-30.xml/",
                },
            ],
        },
    }


def test_discover_latest_xml_sources_uses_api_key_and_filters_xml():
    seen = []

    def handler(request):
        seen.append(request)
        assert request.headers["x-api-key"] == "test-key"
        assert request.url.path == "/v0/works/"
        assert request.url.params["publisher"] == "Parliamentary Counsel Office"
        assert request.url.params["legislation_type"] == "act"
        return httpx.Response(
            200,
            json={
                "results": [_work_row()],
                "page": 1,
                "per_page": 100,
                "total": 1,
            },
        )

    client = NZLegislationAPIClient(
        "test-key",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    sources = client.discover_latest_xml_sources(legislation_types=("act",))

    assert len(seen) == 1
    assert len(sources) == 1
    source = sources[0]
    assert source.work_id == "act_public_1990_109"
    assert source.version_id == "act_public_1990_109_en_2022-08-30"
    assert source.xml_url.endswith("2022-08-30.xml/")
    assert source.relative_path == ("act/public/1990/109/act_public_1990_109_en_2022-08-30.xml")


def test_download_nz_legislation_api_sources_writes_xml_and_manifest(tmp_path):
    def handler(request):
        if request.url.host == "api.legislation.govt.nz":
            return httpx.Response(
                200,
                json={
                    "results": [_work_row()],
                    "page": 1,
                    "per_page": 100,
                    "total": 1,
                },
            )
        return httpx.Response(
            200,
            content=b'<?xml version="1.0"?><act id="DLM1" year="1990" act.no="109" />',
            headers={"content-type": "application/xml"},
        )

    client = NZLegislationAPIClient(
        "test-key",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    manifest_path = tmp_path / "manifest.json"

    report = download_nz_legislation_api_sources(
        tmp_path / "xml",
        api_key="test-key",
        legislation_types=("act",),
        manifest_path=manifest_path,
        client=client,
    )

    assert report.downloaded_count == 1
    assert report.failed_count == 0
    target = tmp_path / "xml/act/public/1990/109/act_public_1990_109_en_2022-08-30.xml"
    assert target.read_text().startswith("<?xml")
    payload = json.loads(manifest_path.read_text())
    assert payload["discovered_count"] == 1
    assert payload["sources"][0]["xml_url"].endswith("2022-08-30.xml/")


def test_download_nz_legislation_api_sources_reports_waf_failures(tmp_path):
    def handler(request):
        if request.url.host == "api.legislation.govt.nz":
            return httpx.Response(
                200,
                json={
                    "results": [_work_row()],
                    "page": 1,
                    "per_page": 100,
                    "total": 1,
                },
            )
        return httpx.Response(202, headers={"x-amzn-waf-action": "challenge"})

    client = NZLegislationAPIClient(
        "test-key",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    report = download_nz_legislation_api_sources(
        tmp_path / "xml",
        api_key="test-key",
        legislation_types=("act",),
        allow_failures=True,
        client=client,
    )

    assert report.downloaded_count == 0
    assert report.failed_count == 1
    assert "WAF challenge" in report.failures[0]["error"]


def test_download_nz_legislation_api_sources_raises_on_waf_by_default(tmp_path):
    def handler(request):
        if request.url.host == "api.legislation.govt.nz":
            return httpx.Response(
                200,
                json={
                    "results": [_work_row()],
                    "page": 1,
                    "per_page": 100,
                    "total": 1,
                },
            )
        return httpx.Response(202, headers={"x-amzn-waf-action": "challenge"})

    client = NZLegislationAPIClient(
        "test-key",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(NZLegislationAPIError, match="WAF challenge"):
        download_nz_legislation_api_sources(
            tmp_path / "xml",
            api_key="test-key",
            legislation_types=("act",),
            client=client,
        )
