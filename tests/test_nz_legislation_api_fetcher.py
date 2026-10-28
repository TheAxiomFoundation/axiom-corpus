import json
import logging
import re
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor

import h11
import httpx
import pytest
from hypothesis import example, given, settings
from hypothesis import strategies as st

from axiom_corpus.fetchers.nz_legislation_api import (
    _API_KEY_EXTENSION,
    NZ_LEGISLATION_HOSTS,
    NZLegislationAPIClient,
    NZLegislationAPIError,
    _PCOKeyClient,
    _PCOKeyTransport,
    download_nz_legislation_api_sources,
    is_nz_legislation_url,
    nz_legislation_api_key_client,
    nz_legislation_api_key_extensions,
    scope_nz_legislation_api_key,
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
        transport=httpx.MockTransport(handler),
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
        transport=httpx.MockTransport(handler),
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
        transport=httpx.MockTransport(handler),
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
        transport=httpx.MockTransport(handler),
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
        transport=httpx.MockTransport(handler),
    )

    assert client.download_xml(_PCO_XML_URL) == _XML


def _recording_handler(seen, redirects=None):
    """Record (url, key) per hop; redirect each URL in `redirects` to its location."""
    redirects = redirects or {}
    lock = threading.Lock()

    def handler(request):
        with lock:
            seen.append((str(request.url), request.headers.get("x-api-key")))
        location = redirects.get(str(request.url))
        if location:
            return httpx.Response(302, headers={"location": location})
        return httpx.Response(200, content=_XML)

    return handler


_REDIRECT_URL = "https://www.legislation.govt.nz/redirect"


def test_owned_client_sends_its_key_only_on_its_own_requests():
    seen = []

    with NZLegislationAPIClient(
        "test-key", transport=httpx.MockTransport(_recording_handler(seen))
    ) as client:
        owned = client.client
        assert owned.follow_redirects is True
        assert client.download_xml(_PCO_XML_URL) == _XML
        owned.get(_PCO_XML_URL)
        owned.get(_PCO_XML_URL, headers={"X-Api-Key": "caller-key"})
        owned.get("https://example.org/own.xml", headers={"X-Api-Key": "caller-key"})

    assert seen == [
        (_PCO_XML_URL, "test-key"),
        (_PCO_XML_URL, None),
        (_PCO_XML_URL, "caller-key"),
        ("https://example.org/own.xml", "caller-key"),
    ]
    assert owned.is_closed


def test_client_created_after_close_is_owned_and_closed():
    client = NZLegislationAPIClient(
        "test-key", transport=httpx.MockTransport(lambda request: httpx.Response(200, content=_XML))
    )
    first = client.client
    client.close()
    assert first.is_closed

    assert client.download_xml(_PCO_XML_URL) == _XML
    second = client.client
    assert second is not first
    client.close()
    assert second.is_closed


def test_wrappers_sharing_a_transport_send_their_own_keys():
    seen = []
    transport = httpx.MockTransport(_recording_handler(seen))
    first = NZLegislationAPIClient("first-key", transport=transport)
    second = NZLegislationAPIClient("second-key", transport=transport)
    url = "https://www.legislation.govt.nz/act/public/1990/{}/en/latest.xml"

    first.download_xml(url.format(1))
    second.download_xml(url.format(2))
    first.download_xml(url.format(3))
    second.close()
    first.download_xml(url.format(4))
    first.close()

    assert [key for _, key in seen] == ["first-key", "second-key", "first-key", "first-key"]


def test_every_transport_the_client_can_pick_adds_the_key(monkeypatch):
    # httpx 0.28 picks each hop's transport in Client._transport_for_url, from
    # the default transport or a mount (proxy mounts from the environment
    # included); the key client wraps whichever it picks.
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.invalid:3128")
    monkeypatch.delenv("NO_PROXY", raising=False)
    monkeypatch.delenv("no_proxy", raising=False)
    proxied = NZLegislationAPIClient("test-key").client
    picked = proxied._transport_for_url(httpx.URL(_PCO_XML_URL))
    assert isinstance(picked, _PCOKeyTransport)
    assert any(picked._transport is mount for mount in proxied._mounts.values())
    proxied.close()

    seen_default = []
    seen_mounted = []
    client = _PCOKeyClient(
        api_key="test-key",
        transport=httpx.MockTransport(_recording_handler(seen_default)),
        mounts={
            "https://www.legislation.govt.nz": httpx.MockTransport(_recording_handler(seen_mounted))
        },
    )
    extensions = nz_legislation_api_key_extensions()
    client.get(_PCO_XML_URL, extensions=extensions)
    client.get("https://legislation.govt.nz/act.xml", extensions=extensions)

    assert seen_mounted == [(_PCO_XML_URL, "test-key")]
    assert seen_default == [("https://legislation.govt.nz/act.xml", "test-key")]
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
    handler = _recording_handler(seen, {_PCO_XML_URL: location})
    client = NZLegislationAPIClient("test-key", transport=httpx.MockTransport(handler))

    assert client.download_xml(_PCO_XML_URL) == _XML
    assert seen == [(_PCO_XML_URL, "test-key"), (location, None)]


def test_redirect_between_pco_hosts_keeps_api_key():
    seen = []
    target = "https://legislation.govt.nz/act/public/1990/109/en/2022-08-30.xml"
    handler = _recording_handler(seen, {_PCO_XML_URL: target})
    client = NZLegislationAPIClient("test-key", transport=httpx.MockTransport(handler))

    assert client.download_xml(_PCO_XML_URL) == _XML
    assert seen == [(_PCO_XML_URL, "test-key"), (target, "test-key")]


def test_the_key_leaves_the_request_once_sent():
    # Invariant: the key is on a request only while its hop is being sent, so
    # response hooks, response.request, next_request and redirect history
    # never hold it; a tagged next_request sent later is scoped again.
    seen = []
    hook_keys = []
    handler = _recording_handler(
        seen,
        {
            _REDIRECT_URL: "https://legislation.govt.nz/end",
            "https://legislation.govt.nz/end": "https://example.org/x",
        },
    )
    wrapper = NZLegislationAPIClient("test-key", transport=httpx.MockTransport(handler))
    client = wrapper.client
    client.follow_redirects = False
    client.event_hooks = {
        "response": [lambda response: hook_keys.append(response.request.headers.get("x-api-key"))]
    }

    first = wrapper._get(_REDIRECT_URL, headers={})
    second = client.send(first.next_request)
    third = client.send(second.next_request)

    assert seen == [
        (_REDIRECT_URL, "test-key"),
        ("https://legislation.govt.nz/end", "test-key"),
        ("https://example.org/x", None),
    ]
    assert hook_keys == [None, None, None]
    for response in (first, second, third):
        assert "x-api-key" not in response.request.headers
    assert "x-api-key" not in first.next_request.headers
    assert "x-api-key" not in second.next_request.headers
    wrapper.close()


def test_the_key_leaves_the_request_when_the_send_fails():
    seen = []

    def handler(request):
        seen.append(request.headers.get("x-api-key"))
        raise httpx.ConnectError("refused", request=request)

    wrapper = NZLegislationAPIClient("test-key", transport=httpx.MockTransport(handler))

    with pytest.raises(httpx.ConnectError) as raised:
        wrapper._get(_PCO_XML_URL, headers={})

    assert seen == ["test-key"]
    assert "x-api-key" not in raised.value.request.headers
    wrapper.close()


_OFF_PCO_LOCATIONS = ["https://example.org/end", "http://www.legislation.govt.nz/end"]


@pytest.mark.parametrize("location", _OFF_PCO_LOCATIONS)
@pytest.mark.parametrize("action", ["close wrapper", "replace hooks", "empty hooks in place"])
def test_closing_or_rehooking_mid_redirect_never_forwards_the_key(action, location):
    # Invariant: whatever a caller's response hook does to the wrapper or to
    # the client's hooks between hops, a hop that is not https to a PCO host
    # carries no key.
    seen = []
    wrapper = NZLegislationAPIClient(
        "owner-key",
        transport=httpx.MockTransport(_recording_handler(seen, {_REDIRECT_URL: location})),
    )
    client = wrapper.client

    def caller_response_hook(response):
        if response.url.path != "/redirect":
            return
        if action == "close wrapper":
            wrapper.close()
        elif action == "replace hooks":
            client.event_hooks = {"request": [], "response": []}
        else:
            client.event_hooks["request"].clear()
            client.event_hooks["response"].clear()

    client.event_hooks = {"response": [caller_response_hook]}

    response = client.get(_REDIRECT_URL, extensions=nz_legislation_api_key_extensions())

    assert response.status_code == 200
    assert seen == [(_REDIRECT_URL, "owner-key"), (location, None)]
    client.close()


@pytest.mark.parametrize("location", _OFF_PCO_LOCATIONS)
def test_rehooking_during_one_request_never_exposes_another_requests_key(location):
    # Round 4's case: request B has been sent with its key when a caller
    # response hook on request A replaces the client's hooks; B's redirect
    # off https PCO hosts still carries no key.
    seen = []
    b_sent = threading.Event()
    hooks_replaced = threading.Event()
    record = _recording_handler(seen)

    def handler(request):
        response = record(request)
        if request.url.path == "/a":
            assert b_sent.wait(5)
            return httpx.Response(302, headers={"location": "https://example.org/a-end"})
        if request.url.path == "/b":
            b_sent.set()
            assert hooks_replaced.wait(5)
            return httpx.Response(302, headers={"location": location})
        return response

    wrapper = NZLegislationAPIClient("owner-key", transport=httpx.MockTransport(handler))
    client = wrapper.client

    def caller_response_hook(response):
        if response.url.path == "/a":
            client.event_hooks = {}
            hooks_replaced.set()

    client.event_hooks = {"response": [caller_response_hook]}
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(wrapper._get, f"https://www.legislation.govt.nz/{path}", headers={})
            for path in ("a", "b")
        ]
        statuses = [future.result(timeout=10).status_code for future in futures]

    assert statuses == [200, 200]
    assert sorted(seen) == sorted(
        [
            ("https://www.legislation.govt.nz/a", "owner-key"),
            ("https://www.legislation.govt.nz/b", "owner-key"),
            ("https://example.org/a-end", None),
            (location, None),
        ]
    )
    wrapper.close()


def test_a_nested_caller_request_that_rehooks_never_exposes_the_outer_key():
    # A caller request hook on the outer request sends a nested request whose
    # response hook replaces the client's hooks; the outer redirect off PCO
    # still carries no key.
    seen = []
    wrapper = NZLegislationAPIClient(
        "owner-key",
        transport=httpx.MockTransport(
            _recording_handler(
                seen, {"https://www.legislation.govt.nz/outer": "https://example.org/outer-end"}
            )
        ),
    )
    client = wrapper.client

    def caller_request_hook(request):
        if request.url.path == "/outer":
            client.get("https://www.legislation.govt.nz/nested")

    def caller_response_hook(response):
        if response.url.path == "/nested":
            client.event_hooks = {}

    client.event_hooks = {"request": [caller_request_hook], "response": [caller_response_hook]}

    assert wrapper._get("https://www.legislation.govt.nz/outer", headers={}).status_code == 200
    assert seen == [
        ("https://www.legislation.govt.nz/nested", None),
        ("https://www.legislation.govt.nz/outer", "owner-key"),
        ("https://example.org/outer-end", None),
    ]
    wrapper.close()


def test_no_request_holds_the_key_once_its_hop_is_sent():
    # Invariant: the key is on a request only while its hop is being sent.
    # The tag httpx copies onto redirects, history and next_request is a
    # marker, so no request a caller can reach afterwards holds the key.
    def handler(request):
        if request.url.path == "/redirect":
            return httpx.Response(302, headers={"location": "https://example.org/end"})
        if request.url.path == "/fail":
            return httpx.Response(500)
        return httpx.Response(200, content=_XML)

    wrapper = NZLegislationAPIClient(_SECRET, transport=httpx.MockTransport(handler))
    hooked = []
    wrapper.client.event_hooks = {"response": [lambda response: hooked.append(response.request)]}

    followed = wrapper._get(_REDIRECT_URL, headers={})
    wrapper.client.follow_redirects = False
    stopped = wrapper._get(_REDIRECT_URL, headers={})
    failed = wrapper._get("https://www.legislation.govt.nz/fail", headers={})
    with pytest.raises(httpx.HTTPStatusError) as raised:
        failed.raise_for_status()

    requests = [
        followed.request,
        *(response.request for response in followed.history),
        stopped.request,
        stopped.next_request,
        raised.value.request,
        *hooked,
    ]
    assert len(requests) == 9
    for request in requests:
        assert request.extensions[_API_KEY_EXTENSION] is True
        assert _SECRET not in repr(vars(request))
    wrapper.close()


def test_the_key_is_redacted_where_the_client_holds_it():
    # The key lives on the wrapper and its httpx client, and on each hop's
    # transport; none of them shows it in a repr of its attributes.
    wrapper = NZLegislationAPIClient(
        _SECRET, transport=httpx.MockTransport(lambda request: httpx.Response(200))
    )
    client = wrapper.client
    transport = client._transport_for_url(httpx.URL(_PCO_XML_URL))

    assert wrapper.api_key == _SECRET
    for holder in (wrapper, client, transport):
        assert _SECRET not in repr(holder)
        assert _SECRET not in repr(vars(holder))
    wrapper.close()


def test_the_key_is_fixed_when_the_wrapper_is_built():
    # The client holds the key it was built with, so the wrapper offers no way
    # to change it afterwards.
    seen = []
    wrapper = NZLegislationAPIClient(
        "test-key", transport=httpx.MockTransport(_recording_handler(seen))
    )

    with pytest.raises(AttributeError):
        wrapper.api_key = "other-key"  # type: ignore[misc]
    wrapper.client.get(_PCO_XML_URL, extensions=nz_legislation_api_key_extensions())

    assert seen == [(_PCO_XML_URL, "test-key")]
    wrapper.close()


def test_only_a_key_tag_from_the_helper_adds_the_key():
    seen = []
    wrapper = NZLegislationAPIClient(
        "test-key", transport=httpx.MockTransport(_recording_handler(seen))
    )

    wrapper.client.get(_PCO_XML_URL, extensions={_API_KEY_EXTENSION: "raw-key"})

    assert seen == [(_PCO_XML_URL, None)]
    wrapper.close()


_INVALID_KEY_MESSAGE = "NZ Legislation API key must be printable ASCII with no whitespace"


@given(
    key=st.one_of(
        st.text(max_size=12),
        st.text(alphabet=st.characters(min_codepoint=0x21, max_codepoint=0x7E), min_size=1),
        st.from_regex(r"[!-~]{1,8}[ \t\r\n\x00\x7f\x80][!-~]{0,8}", fullmatch=True),
    )
)
@example(key="test-key\n")
@example(key=" test-key")
@example(key="")
def test_keys_are_validated_without_echoing_them(key):
    # Invariants: a key is accepted exactly when it is printable ASCII with no
    # whitespace; a rejected key raises one fixed message, never the key; and
    # every accepted key is a header value h11 sends without error.
    valid = re.fullmatch(r"[!-~]+", key) is not None

    if valid:
        nz_legislation_api_key_client(api_key=key, timeout=1).close()
        NZLegislationAPIClient(key).close()
        h11.Request(method="GET", target="/", headers=[("Host", "x"), ("X-Api-Key", key)])
    else:
        with pytest.raises(ValueError) as raised:
            nz_legislation_api_key_client(api_key=key, timeout=1)
        assert str(raised.value) == _INVALID_KEY_MESSAGE
        with pytest.raises(ValueError) as raised:
            NZLegislationAPIClient(key)
        assert str(raised.value) in (_INVALID_KEY_MESSAGE, "NZ Legislation API key is required")


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
def test_scoping_sets_key_iff_https_pco_host(scheme, host, path, preset):
    # Invariant: after scoping, a request carries the key exactly when it is
    # https to a PCO host, whatever headers it started with.
    headers = {"X-Api-Key": "stale-key"} if preset else {}
    request = httpx.Request("GET", f"{scheme}://{host}{path}", headers=headers)

    scope_nz_legislation_api_key(request, "test-key")

    allowed = scheme == "https" and host in NZ_LEGISLATION_HOSTS
    assert is_nz_legislation_url(request.url) is allowed
    assert request.headers.get("x-api-key") == ("test-key" if allowed else None)


def _follow_chain(chain, *, wrapped, follow, max_redirects, auth):
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

    transport = httpx.MockTransport(handler)
    if wrapped:
        wrapper = NZLegislationAPIClient("test-key", transport=transport)
        client = wrapper.client
        client.follow_redirects = follow
        client.max_redirects = max_redirects
        client.auth = auth

        def send():
            return wrapper._get(chain[0], headers={})
    else:
        client = httpx.Client(
            transport=transport, follow_redirects=follow, max_redirects=max_redirects, auth=auth
        )

        def send():
            return client.get(chain[0])

    try:
        response = send()
    except httpx.TooManyRedirects:
        outcome = "too many redirects"
        next_key = None
    else:
        next_request = response.next_request
        outcome = (response.status_code, len(response.history), next_request and next_request.url)
        next_key = next_request and next_request.headers.get("x-api-key")
    client.close()
    return seen, outcome, next_key


@settings(deadline=None)
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
    # Invariants: with the caller's redirect, limit and auth settings on the
    # wrapper's client, the wrapper transmits exactly the hops plain httpx
    # would, with the same Authorization on each hop and the same outcome;
    # each transmitted hop carries the key exactly when it is https to a PCO
    # host; and next_request never holds the key.
    chain = [f"{scheme}://{host}/hop/{index}" for index, (scheme, host) in enumerate(hops)]
    options = {"follow": follow, "max_redirects": max_redirects, "auth": auth}

    wrapper_seen, wrapper_outcome, next_key = _follow_chain(chain, wrapped=True, **options)
    httpx_seen, httpx_outcome, _ = _follow_chain(chain, wrapped=False, **options)

    assert [hop[:2] for hop in wrapper_seen] == [hop[:2] for hop in httpx_seen]
    assert wrapper_outcome == httpx_outcome
    assert next_key is None
    for url, _, key in wrapper_seen:
        assert key == ("test-key" if is_nz_legislation_url(url) else None)


_TARGETS = {
    "pco": "https://www.legislation.govt.nz/act/1.xml",
    "pco to other host": "https://www.legislation.govt.nz/redirect?to=https://example.org/end",
    "pco to http": "https://www.legislation.govt.nz/redirect?to=http://www.legislation.govt.nz/end",
    "pco to pco": "https://www.legislation.govt.nz/redirect?to=https://legislation.govt.nz/end",
    "other host": "https://example.org/own.xml",
}
_OPERATIONS = st.lists(
    st.one_of(
        st.tuples(st.just("new"), st.integers(0, 2)),
        st.tuples(st.just("close"), st.integers(0, 5)),
        st.tuples(st.just("wrapper get"), st.integers(0, 5), st.sampled_from(sorted(_TARGETS))),
        st.tuples(
            st.just("caller get"),
            st.integers(0, 5),
            st.sampled_from(sorted(_TARGETS)),
            st.sampled_from([None, "caller-key"]),
        ),
        st.tuples(st.just("replace hooks"), st.integers(0, 5)),
    ),
    max_size=12,
)


@settings(deadline=None)
@given(operations=_OPERATIONS)
def test_any_interleaving_scopes_each_wrappers_key_and_leaves_caller_requests_alone(operations):
    # Invariants, for any interleaving of wrappers created on one transport and
    # closed, caller requests on their clients and caller hook replacements: a
    # wrapper's hop carries that wrapper's key exactly when it is https to a
    # PCO host; a caller's hops carry exactly the headers plain httpx would.
    seen = []

    def handler(request):
        seen.append((str(request.url), request.headers.get("x-api-key")))
        target = request.url.params.get("to")
        if target:
            return httpx.Response(302, headers={"location": target})
        return httpx.Response(200, content=_XML)

    def hops(url):
        target = httpx.URL(url).params.get("to")
        return [str(httpx.URL(hop)) for hop in ([url, target] if target else [url])]

    transport = httpx.MockTransport(handler)
    wrappers = []
    open_wrappers = []
    expected = []
    for operation in operations:
        kind = operation[0]
        if kind == "new":
            wrapper = NZLegislationAPIClient(f"key-{len(wrappers)}", transport=transport)
            wrappers.append(wrapper)
            open_wrappers.append(wrapper)
        elif kind == "close" and operation[1] < len(wrappers):
            wrapper = wrappers[operation[1]]
            wrapper.close()
            if wrapper in open_wrappers:
                open_wrappers.remove(wrapper)
        elif not open_wrappers:
            continue
        elif kind == "wrapper get":
            wrapper = open_wrappers[operation[1] % len(open_wrappers)]
            url = _TARGETS[operation[2]]
            wrapper._get(url, headers={})
            expected += [
                (hop, wrapper.api_key if is_nz_legislation_url(hop) else None) for hop in hops(url)
            ]
        elif kind == "caller get":
            client = open_wrappers[operation[1] % len(open_wrappers)].client
            url = _TARGETS[operation[2]]
            headers = {"X-Api-Key": operation[3]} if operation[3] else {}
            client.get(url, headers=headers)
            expected += [(hop, operation[3]) for hop in hops(url)]
        elif kind == "replace hooks":
            open_wrappers[operation[1] % len(open_wrappers)].client.event_hooks = {}

    assert seen == expected
    for wrapper in open_wrappers:
        wrapper.close()


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
        transport=httpx.MockTransport(_leak_handler(seen_urls)),
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
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises((NZLegislationAPIError, httpx.HTTPStatusError)) as excinfo:
        download_nz_legislation_api_sources(
            tmp_path / "xml", api_key=_SECRET, legislation_types=("act",), client=client
        )

    rendered = "".join(traceback.format_exception(excinfo.value))
    assert _SECRET not in rendered
    assert _SECRET not in repr(excinfo.value)
