import json

import httpx
import pytest
from hypothesis import given
from hypothesis import strategies as st

from axiom_corpus.fetchers.nz_legislation_api import (
    NZ_LEGISLATION_HOSTS,
    NZLegislationAPIClient,
    NZLegislationAPIError,
    download_nz_legislation_api_sources,
    is_nz_legislation_url,
    nz_legislation_api_key_hook,
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
    xml_requests = []

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
        xml_requests.append(request)
        assert request.headers["x-api-key"] == "test-key"
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
        workers=2,
        client=client,
    )

    assert report.downloaded_count == 1
    assert report.failed_count == 0
    assert len(xml_requests) == 1
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


_XML = b'<?xml version="1.0"?><act id="DLM1" year="1990" act.no="109" />'
_PCO_XML_URL = "https://www.legislation.govt.nz/act/public/1990/109/en/2022-08-30.xml"


def test_download_xml_sends_api_key_to_legislation_govt_nz():
    def handler(request):
        assert request.url.host == "www.legislation.govt.nz"
        assert request.headers["x-api-key"] == "test-key"
        return httpx.Response(200, content=_XML)

    client = NZLegislationAPIClient(
        "test-key",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert client.download_xml(_PCO_XML_URL) == _XML


def test_owned_client_installs_api_key_hook():
    client = NZLegislationAPIClient("test-key")
    request = httpx.Request("GET", _PCO_XML_URL)

    for hook in client.client.event_hooks["request"]:
        hook(request)

    assert request.headers["x-api-key"] == "test-key"
    client.close()


@pytest.mark.parametrize(
    "location",
    [
        "https://example.org/act.xml",
        "http://www.legislation.govt.nz/act/public/1990/109/en/2022-08-30.xml",
        "https://legislation.govt.nz.example.org/act.xml",
    ],
)
def test_redirect_off_https_pco_hosts_drops_api_key(location):
    seen = []

    def handler(request):
        seen.append((str(request.url), request.headers.get("x-api-key")))
        if request.url.host == "www.legislation.govt.nz" and request.url.scheme == "https":
            return httpx.Response(302, headers={"location": location})
        return httpx.Response(200, content=_XML)

    client = NZLegislationAPIClient(
        "test-key",
        client=httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True),
    )

    assert client.download_xml(_PCO_XML_URL) == _XML
    assert seen == [(_PCO_XML_URL, "test-key"), (location, None)]


def test_redirect_between_pco_hosts_keeps_api_key():
    seen = []
    target = "https://legislation.govt.nz/act/public/1990/109/en/2022-08-30.xml"

    def handler(request):
        seen.append((request.url.host, request.headers.get("x-api-key")))
        if request.url.host == "www.legislation.govt.nz":
            return httpx.Response(301, headers={"location": target})
        return httpx.Response(200, content=_XML)

    client = NZLegislationAPIClient(
        "test-key",
        client=httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True),
    )

    assert client.download_xml(_PCO_XML_URL) == _XML
    assert seen == [
        ("www.legislation.govt.nz", "test-key"),
        ("legislation.govt.nz", "test-key"),
    ]


_HOSTS = st.one_of(
    st.sampled_from(sorted(NZ_LEGISLATION_HOSTS)),
    st.sampled_from(
        [
            "legislation.govt.nz.example.org",
            "evillegislation.govt.nz",
            "pco.govt.nz",
            "example.org",
            "api.legislation.govt.nz.attacker.test",
        ]
    ),
    st.from_regex(r"[a-z]{1,12}(\.[a-z]{2,8}){1,3}", fullmatch=True),
)


@given(
    scheme=st.sampled_from(["https", "http"]),
    host=_HOSTS,
    path=st.from_regex(r"(/[a-z0-9._-]{0,12}){0,4}", fullmatch=True),
    preset=st.booleans(),
)
def test_api_key_hook_sets_key_iff_https_pco_host(scheme, host, path, preset):
    # Invariant: after the hook, a request carries the key exactly when it is
    # https to a PCO host, whatever headers it started with.
    headers = {"X-Api-Key": "stale-key"} if preset else {}
    request = httpx.Request("GET", f"{scheme}://{host}{path}", headers=headers)

    nz_legislation_api_key_hook("test-key")(request)

    allowed = scheme == "https" and host in NZ_LEGISLATION_HOSTS
    assert is_nz_legislation_url(request.url) is allowed
    assert request.headers.get("x-api-key") == ("test-key" if allowed else None)
