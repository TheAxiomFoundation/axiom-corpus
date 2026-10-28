import json
import logging
import traceback

import httpx
import pytest
from hypothesis import example, given
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


def test_owned_client_sends_its_key_only_on_its_own_requests(monkeypatch):
    seen = []

    def handler(request):
        seen.append(request.headers.get("x-api-key"))
        return httpx.Response(200, content=_XML)

    real_client = httpx.Client
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
    )

    with NZLegislationAPIClient("test-key") as client:
        owned = client.client
        assert owned.follow_redirects is True
        assert client.download_xml(_PCO_XML_URL) == _XML
        owned.get(_PCO_XML_URL)

    assert seen == ["test-key", None]
    assert owned.is_closed


def test_client_created_after_close_is_owned_and_closed(monkeypatch):
    real_client = httpx.Client
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: real_client(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, content=_XML)),
            **kwargs,
        ),
    )
    borrowed = real_client(transport=httpx.MockTransport(lambda request: httpx.Response(200)))
    client = NZLegislationAPIClient("test-key", client=borrowed)
    client.close()

    assert client.download_xml(_PCO_XML_URL) == _XML
    created = client.client
    assert created is not borrowed
    client.close()

    assert created.is_closed
    assert not borrowed.is_closed
    borrowed.close()


def test_wrappers_sharing_a_client_send_their_own_keys():
    # Invariants: each wrapper's requests carry its own key; the caller's own
    # requests on the shared client are never changed; once the last wrapper
    # closes, the client has exactly the hooks its caller gave it.
    seen = []
    caller_hook_urls = []

    def handler(request):
        seen.append((str(request.url), request.headers.get("x-api-key")))
        return httpx.Response(200, content=_XML)

    def caller_hook(request):
        caller_hook_urls.append(str(request.url))

    shared = httpx.Client(
        transport=httpx.MockTransport(handler),
        event_hooks={"request": [caller_hook]},
    )
    hooks_before = {name: list(hooks) for name, hooks in shared.event_hooks.items()}
    first = NZLegislationAPIClient("first-key", client=shared)
    second = NZLegislationAPIClient("second-key", client=shared)
    url = "https://www.legislation.govt.nz/act/public/1990/{}/en/latest.xml"

    first.download_xml(url.format(1))
    second.download_xml(url.format(2))
    shared.get(url.format(3))
    shared.get(url.format(4), headers={"X-Api-Key": "caller-key"})
    shared.get("https://example.org/own.xml", headers={"X-Api-Key": "caller-key"})
    first.download_xml(url.format(6))
    second.close()
    first.download_xml(url.format(7))
    first.close()
    shared.get(url.format(8))

    assert [key for _, key in seen] == [
        "first-key",
        "second-key",
        None,
        "caller-key",
        "caller-key",
        "first-key",
        "first-key",
        None,
    ]
    assert shared.event_hooks == hooks_before
    assert len(caller_hook_urls) == 8
    assert not shared.is_closed
    shared.close()


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


def _follow_chain(chain, *, follow, max_redirects, auth, send):
    """Serve a redirect chain and record each transmitted hop and the outcome."""
    seen = []

    def handler(request):
        seen.append(
            (request.url, request.headers.get("authorization"), request.headers.get("x-api-key"))
        )
        index = int(request.url.path.rsplit("/", 1)[1])
        if index + 1 < len(chain):
            return httpx.Response(302, headers={"location": chain[index + 1]})
        return httpx.Response(200, content=_XML)

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        follow_redirects=follow,
        max_redirects=max_redirects,
        auth=auth,
    )
    try:
        response = send(client, chain[0])
    except httpx.TooManyRedirects:
        outcome = "too many redirects"
    else:
        next_url = response.next_request.url if response.next_request else None
        outcome = (response.status_code, len(response.history), next_url)
    client.close()
    return seen, outcome


@given(
    hops=st.lists(st.tuples(st.sampled_from(["https", "http"]), _HOSTS), min_size=1, max_size=5),
    follow=st.booleans(),
    max_redirects=st.integers(min_value=0, max_value=4),
    auth=st.sampled_from([None, ("caller-user", "caller-password")]),
)
@example(
    hops=[("https", "www.legislation.govt.nz")] * 4,
    follow=True,
    max_redirects=1,
    auth=None,
)
@example(
    hops=[("https", "www.legislation.govt.nz"), ("https", "example.org")],
    follow=True,
    max_redirects=20,
    auth=("caller-user", "caller-password"),
)
@example(
    hops=[("https", "www.legislation.govt.nz"), ("http", "api.legislation.govt.nz")],
    follow=True,
    max_redirects=20,
    auth=("caller-user", "caller-password"),
)
@example(
    hops=[
        ("https", "www.legislation.govt.nz"),
        ("https", "example.org"),
        ("https", "legislation.govt.nz"),
    ],
    follow=True,
    max_redirects=20,
    auth=None,
)
def test_redirect_chains_match_httpx_and_scope_the_key_per_hop(hops, follow, max_redirects, auth):
    # Invariants: the wrapper transmits exactly the hops plain httpx would,
    # with the same caller Authorization on each hop and the same outcome, and
    # each transmitted hop carries the key exactly when it is https to a PCO
    # host.
    chain = [f"{scheme}://{host}/hop/{index}" for index, (scheme, host) in enumerate(hops)]

    wrapper_seen, wrapper_outcome = _follow_chain(
        chain,
        follow=follow,
        max_redirects=max_redirects,
        auth=auth,
        send=lambda client, url: NZLegislationAPIClient("test-key", client=client)._get(
            url, headers={}
        ),
    )
    httpx_seen, httpx_outcome = _follow_chain(
        chain,
        follow=follow,
        max_redirects=max_redirects,
        auth=auth,
        send=lambda client, url: client.get(url),
    )

    assert [hop[:2] for hop in wrapper_seen] == [hop[:2] for hop in httpx_seen]
    assert wrapper_outcome == httpx_outcome
    for url, _, key in wrapper_seen:
        assert key == ("test-key" if is_nz_legislation_url(url) else None)


_SECRET = "pco-secret-value-7f3a9c"


def _rows(*suffixes):
    rows = []
    for suffix in suffixes:
        row = json.loads(json.dumps(_work_row()))
        row["work_id"] = f"act_public_1990_{suffix}"
        version = row["latest_matching_version"]
        version["version_id"] = f"act_public_1990_{suffix}_en_2022-08-30"
        for item in version["formats"]:
            item["url"] = item["url"].replace("/109/", f"/{suffix}/")
        rows.append(row)
    return rows


def _leak_handler(seen_urls):
    def handler(request):
        seen_urls.append(str(request.url))
        if request.url.host == "api.legislation.govt.nz":
            return httpx.Response(
                200,
                json={"results": _rows("1", "2", "3"), "page": 1, "per_page": 100, "total": 3},
            )
        if "/1/" in request.url.path:
            return httpx.Response(200, content=_XML)
        if "/2/" in request.url.path:
            return httpx.Response(202, headers={"x-amzn-waf-action": "challenge"})
        return httpx.Response(500, text="upstream error")

    return handler


def test_api_key_never_reaches_logs_errors_urls_or_manifest(tmp_path, caplog):
    caplog.set_level(logging.DEBUG)
    seen_urls = []
    client = NZLegislationAPIClient(
        _SECRET,
        client=httpx.Client(transport=httpx.MockTransport(_leak_handler(seen_urls))),
    )
    manifest_path = tmp_path / "manifest.json"

    report = download_nz_legislation_api_sources(
        tmp_path / "xml",
        api_key=_SECRET,
        legislation_types=("act",),
        allow_failures=True,
        manifest_path=manifest_path,
        client=client,
    )

    assert (report.downloaded_count, report.failed_count) == (1, 2)
    errors = [failure["error"] for failure in report.failures]
    assert any("WAF challenge" in error for error in errors)
    assert any("500" in error for error in errors)
    assert len(seen_urls) == 4
    surfaces = {
        "manifest": manifest_path.read_text(),
        "report": json.dumps(report.to_mapping()),
        "errors": "\n".join(errors),
        "request urls": "\n".join(seen_urls),
        "logs": caplog.text,
        "client repr": repr(client),
    }
    for name, text in surfaces.items():
        assert _SECRET not in text, name


@pytest.mark.parametrize("suffix", ["2", "3"])
def test_api_key_never_reaches_raised_exceptions(tmp_path, suffix):
    def handler(request):
        if request.url.host == "api.legislation.govt.nz":
            return httpx.Response(
                200, json={"results": _rows(suffix), "page": 1, "per_page": 100, "total": 1}
            )
        return _leak_handler([])(request)

    client = NZLegislationAPIClient(
        _SECRET,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises((NZLegislationAPIError, httpx.HTTPStatusError)) as excinfo:
        download_nz_legislation_api_sources(
            tmp_path / "xml", api_key=_SECRET, legislation_types=("act",), client=client
        )

    rendered = "".join(traceback.format_exception(excinfo.value))
    assert _SECRET not in rendered
    assert _SECRET not in repr(excinfo.value)
