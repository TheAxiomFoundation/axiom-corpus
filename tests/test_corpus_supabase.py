import hashlib
import io
import json
import urllib.error
from base64 import b64encode

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from axiom_corpus.corpus.models import ProvisionRecord
from axiom_corpus.corpus.releases import ReleaseManifest, ReleaseScope
from axiom_corpus.corpus.supabase import (
    StagedScopeEvidence,
    activate_corpus_release,
    delete_supabase_provisions_scope,
    deterministic_provision_id,
    fetch_provision_counts,
    fetch_release_provision_counts,
    fetch_released_scope_objects,
    fetch_staged_release_scope_evidence,
    iter_supabase_rows,
    load_provisions_to_supabase,
    provision_to_supabase_row,
    refresh_corpus_analytics,
    resolve_service_key,
    verify_release_coverage,
    write_supabase_rows_jsonl,
)
from axiom_corpus.release.manifest import (
    ReleaseManifestError,
    build_unsigned_release_object,
    content_addressed_r2_key,
    sign_release_object,
)


def _signed_release_object() -> tuple[dict, str]:
    private = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
    private_text = b64encode(
        private.private_bytes(
            serialization.Encoding.Raw,
            serialization.PrivateFormat.Raw,
            serialization.NoEncryption(),
        )
    ).decode()
    public_text = b64encode(
        private.public_key().public_bytes(
            serialization.Encoding.Raw,
            serialization.PublicFormat.Raw,
        )
    ).decode()
    provision_digest = "c" * 64
    navigation_digest = "d" * 64
    scope = {
        "jurisdiction": "nz",
        "document_class": "statute",
        "version": "v1",
        "provision_rows": 1,
        "navigation_rows": 1,
        "provision_projection_sha256": provision_digest,
        "navigation_projection_sha256": navigation_digest,
    }
    artifacts = []
    for artifact_class, path, rows in (
        ("coverage", "data/corpus/coverage/nz/statute/v1.json", None),
        ("inventory", "data/corpus/inventory/nz/statute/v1.json", None),
        ("provisions", "data/corpus/provisions/nz/statute/v1.jsonl", 1),
        ("sources", "data/corpus/sources/nz/statute/v1/source.txt", None),
    ):
        digest = hashlib.sha256(path.encode()).hexdigest()
        artifact = {
            "artifact_class": artifact_class,
            "path": path,
            "sha256": digest,
            "bytes": len(path.encode()),
            "r2_bucket": "axiom-corpus",
            "r2_key": content_addressed_r2_key(digest),
        }
        if rows is not None:
            artifact["rows"] = rows
        artifacts.append(artifact)
    artifacts.sort(key=lambda artifact: artifact["path"])
    selector = {
        "name": "nz-rulespec-v1",
        "scopes": [{key: scope[key] for key in ("jurisdiction", "document_class", "version")}],
    }
    selector_digest = hashlib.sha256(
        json.dumps(selector, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    content = {
        "release": "nz-rulespec-v1",
        "created_at": "2026-07-10T00:00:00Z",
        "selector_sha256": selector_digest,
        "corpus_base": "data/corpus",
        "git": {"commit": "a" * 40, "committed_at": "2026-07-10T00:00:00Z"},
        "r2": {"bucket": "axiom-corpus", "addressing": "sha256"},
        "scopes": [scope],
        "artifacts": artifacts,
        "validation": {
            "passed": True,
            "deep_validation": {"error_count": 0, "warning_count": 0, "scope_count": 1},
            "r2_readback": {
                "bucket": "axiom-corpus",
                "artifact_count": 4,
                "artifact_bytes": sum(artifact["bytes"] for artifact in artifacts),
                "verified_keys": [artifact["r2_key"] for artifact in artifacts],
            },
            "supabase_projection_evidence": [
                {
                    "jurisdiction": "nz",
                    "document_class": "statute",
                    "version": "v1",
                    "expected": 1,
                    "actual": 1,
                    "expected_navigation": 1,
                    "actual_navigation": 1,
                    "expected_provision_projection_sha256": provision_digest,
                    "actual_provision_projection_sha256": provision_digest,
                    "expected_navigation_projection_sha256": navigation_digest,
                    "actual_navigation_projection_sha256": navigation_digest,
                }
            ],
        },
    }
    return (
        sign_release_object(build_unsigned_release_object(content), private_key=private_text),
        public_text,
    )


def test_supabase_projection_derives_stable_ids_and_parent_ids():
    record = ProvisionRecord(
        jurisdiction="us",
        document_class="regulation",
        citation_path="us/regulation/7/273/1",
        parent_citation_path="us/regulation/7/273",
        heading="Household concept",
        body="Text.",
    )

    row = provision_to_supabase_row(record)

    assert row["id"] == deterministic_provision_id("us/regulation/7/273/1")
    assert row["parent_id"] == deterministic_provision_id("us/regulation/7/273")
    assert row["doc_type"] == "regulation"
    assert row["version"] is None
    assert row["has_rulespec"] is False
    assert row["identifiers"] == {}


def test_supabase_projection_uses_versioned_ids_for_release_rows():
    record = ProvisionRecord(
        jurisdiction="us",
        document_class="regulation",
        citation_path="us/regulation/7/273/1",
        parent_citation_path="us/regulation/7/273",
        id=deterministic_provision_id("us/regulation/7/273/1").upper(),
        parent_id=deterministic_provision_id("us/regulation/7/273").upper(),
        version="2026-05-13",
    )

    row = provision_to_supabase_row(record)

    assert row["id"] == deterministic_provision_id(
        "us/regulation/7/273/1",
        "2026-05-13",
    )
    assert row["parent_id"] == deterministic_provision_id(
        "us/regulation/7/273",
        "2026-05-13",
    )
    assert row["version"] == "2026-05-13"


def test_supabase_projection_canonicalizes_explicit_uuid_ids():
    record = ProvisionRecord(
        jurisdiction="us",
        document_class="regulation",
        citation_path="us/regulation/7/273/1",
        id="AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA",
        parent_id="BBBBBBBB-BBBB-4BBB-8BBB-BBBBBBBBBBBB",
    )

    row = provision_to_supabase_row(record)

    assert row["id"] == "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    assert row["parent_id"] == "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


def test_supabase_projection_rejects_non_uuid_database_ids():
    record = ProvisionRecord(
        jurisdiction="us",
        document_class="regulation",
        citation_path="us/regulation/7/273/1",
        id="not-a-uuid",
    )

    with pytest.raises(ValueError, match="id must be a UUID"):
        provision_to_supabase_row(record)


def test_supabase_projection_preserves_non_uuid_source_document_id_as_identifier():
    record = ProvisionRecord(
        jurisdiction="us-ny",
        document_class="regulation",
        citation_path="us-ny/regulation/title-1",
        source_document_id="I0dea9f40aab711ddae51f9dc2e7e68c4",
        identifiers={"nycrr:guid": "I0dea9f40aab711ddae51f9dc2e7e68c4"},
    )

    row = provision_to_supabase_row(record)

    assert row["source_document_id"] is None
    assert row["identifiers"] == {
        "nycrr:guid": "I0dea9f40aab711ddae51f9dc2e7e68c4",
        "source:document_id": "I0dea9f40aab711ddae51f9dc2e7e68c4",
    }


def test_supabase_projection_keeps_uuid_source_document_id_column():
    source_document_id = "11111111-1111-1111-1111-111111111111"
    record = ProvisionRecord(
        jurisdiction="us",
        document_class="policy",
        citation_path="us/policy/source-doc",
        source_document_id=source_document_id,
    )

    row = provision_to_supabase_row(record)

    assert row["source_document_id"] == source_document_id
    assert row["identifiers"] == {}


def test_supabase_projection_strips_postgres_invalid_nul_characters():
    record = ProvisionRecord(
        jurisdiction="us",
        document_class="rulemaking",
        citation_path="us/rulemaking/federal-register/2026-05-15/2026-09722",
        heading="Notice\x00",
        body="Federal Register\x00 text",
        identifiers={"federal-register:\x00document-number": "2026-09722\x00"},
    )

    row = provision_to_supabase_row(record)

    assert row["heading"] == "Notice"
    assert row["body"] == "Federal Register text"
    assert row["identifiers"] == {"federal-register:document-number": "2026-09722"}


def test_iter_supabase_rows_compacts_ordinal_that_exceeds_postgres_int4():
    rows = list(
        iter_supabase_rows(
            [
                ProvisionRecord(
                    jurisdiction="us",
                    document_class="statute",
                    citation_path="us/statute/20/1070a/a/1",
                    ordinal=10701001001,
                ),
                ProvisionRecord(
                    jurisdiction="us",
                    document_class="statute",
                    citation_path="us/statute/20/1070a/a/2",
                    ordinal=10701001002,
                ),
            ]
        )
    )

    assert [row["ordinal"] for row in rows] == [0, 1]
    assert rows[0]["identifiers"]["corpus:ordinal"] == 10701001001
    assert rows[1]["identifiers"]["corpus:ordinal"] == 10701001002


def test_write_supabase_rows_jsonl_uses_projection_contract(tmp_path):
    out = tmp_path / "rows.jsonl"
    count = write_supabase_rows_jsonl(
        out,
        [
            ProvisionRecord(
                jurisdiction="us",
                document_class="regulation",
                citation_path="us/regulation/7/273",
                heading="Certification of Eligible Households",
                level=0,
            )
        ],
    )

    row = json.loads(out.read_text())
    assert count == 1
    assert row["id"] == deterministic_provision_id("us/regulation/7/273")
    assert row["body"] is None


def test_fetch_provision_counts_reads_materialized_view(monkeypatch):
    import axiom_corpus.corpus.supabase as supabase

    calls = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return json.dumps(
                [
                    {
                        "jurisdiction": "us-wa",
                        "document_class": "statute",
                        "provision_count": 54631,
                        "body_count": 51768,
                        "top_level_count": 100,
                        "rulespec_count": 0,
                        "refreshed_at": "2026-05-04T17:00:00+00:00",
                    }
                ]
            ).encode()

    def fake_urlopen(req, timeout):
        calls.append((req.full_url, req.headers, timeout))
        return FakeResponse()

    monkeypatch.setattr(supabase.urllib.request, "urlopen", fake_urlopen)

    rows = fetch_provision_counts(
        service_key="service",
        supabase_url="https://example.supabase.co",
    )

    assert rows == (
        {
            "jurisdiction": "us-wa",
            "document_class": "statute",
            "provision_count": 54631,
            "body_count": 51768,
            "top_level_count": 100,
            "rulespec_count": 0,
            "refreshed_at": "2026-05-04T17:00:00+00:00",
        },
    )
    assert calls[0][0].startswith("https://example.supabase.co/rest/v1/current_provision_counts?")
    assert calls[0][1]["Accept-profile"] == "corpus"
    assert calls[0][2] == 180


def test_fetch_provision_counts_can_include_legacy(monkeypatch):
    import axiom_corpus.corpus.supabase as supabase

    calls = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return json.dumps(
                [
                    {
                        "jurisdiction": "us-wa",
                        "document_class": "statute",
                        "provision_count": 54631,
                    }
                ]
            ).encode()

    def fake_urlopen(req, timeout):
        calls.append(req.full_url)
        return FakeResponse()

    monkeypatch.setattr(supabase.urllib.request, "urlopen", fake_urlopen)

    fetch_provision_counts(
        service_key="service",
        supabase_url="https://example.supabase.co",
        include_legacy=True,
    )

    assert calls[0].startswith("https://example.supabase.co/rest/v1/provision_counts?")


def test_fetch_release_provision_counts_counts_manifest_scopes(monkeypatch):
    import axiom_corpus.corpus.supabase as supabase

    calls = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return json.dumps(
                [
                    {
                        "jurisdiction": "us",
                        "document_class": "guidance",
                        "provision_count": 13,
                        "body_count": 10,
                        "top_level_count": 2,
                        "rulespec_count": 2,
                        "refreshed_at": "2026-05-18T01:35:41+00:00",
                    }
                ]
            ).encode()

    def fake_urlopen(req, timeout):
        calls.append((req.full_url, req.get_method(), req.data, req.headers, timeout))
        return FakeResponse()

    monkeypatch.setattr(supabase.urllib.request, "urlopen", fake_urlopen)

    rows = fetch_release_provision_counts(
        ReleaseManifest(
            name="test-release",
            scopes=(
                ReleaseScope("us", "guidance", "2026-a"),
                ReleaseScope("us", "guidance", "2026-b"),
            ),
        ),
        service_key="service",
        supabase_url="https://example.supabase.co",
    )

    assert rows == (
        {
            "jurisdiction": "us",
            "document_class": "guidance",
            "provision_count": 13,
            "body_count": 10,
            "top_level_count": 2,
            "rulespec_count": 2,
            "refreshed_at": rows[0]["refreshed_at"],
        },
    )
    assert len(calls) == 1
    assert calls[0][0] == "https://example.supabase.co/rest/v1/rpc/get_release_provision_counts"
    assert calls[0][1] == "POST"
    assert calls[0][3]["Accept-profile"] == "corpus"
    assert calls[0][3]["Content-profile"] == "corpus"
    assert calls[0][4] == 180
    payload = json.loads(calls[0][2])
    assert payload == {
        "p_scopes": [
            {
                "jurisdiction": "us",
                "document_class": "guidance",
                "version": "2026-a",
            },
            {
                "jurisdiction": "us",
                "document_class": "guidance",
                "version": "2026-b",
            },
        ]
    }


def test_fetch_release_provision_counts_corrects_stale_zero_rows(monkeypatch):
    import axiom_corpus.corpus.supabase as supabase

    calls = []

    class FakeRpc:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return json.dumps(
                [
                    {
                        "jurisdiction": "us-md",
                        "document_class": "regulation",
                        "provision_count": 0,
                        "body_count": 0,
                        "top_level_count": 0,
                        "rulespec_count": 0,
                        "refreshed_at": "2026-05-18T01:35:41+00:00",
                    }
                ]
            ).encode()

    class FakeHead:
        def __init__(self, total):
            self.headers = {"Content-Range": f"0-0/{total}"}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

    def fake_urlopen(req, timeout):  # noqa: ARG001
        calls.append((req.full_url, req.get_method()))
        if req.get_method() == "POST":
            return FakeRpc()
        if "body=not.is.null" in req.full_url:
            return FakeHead(29637)
        if "parent_id=is.null" in req.full_url:
            return FakeHead(1)
        if "has_rulespec=eq.true" in req.full_url:
            return FakeHead(0)
        return FakeHead(34174)

    monkeypatch.setattr(supabase.urllib.request, "urlopen", fake_urlopen)

    rows = fetch_release_provision_counts(
        ReleaseManifest(
            name="test-release",
            scopes=(ReleaseScope("us-md", "regulation", "2026-05-18"),),
        ),
        service_key="service",
        supabase_url="https://example.supabase.co",
    )

    assert rows == (
        {
            "jurisdiction": "us-md",
            "document_class": "regulation",
            "provision_count": 34174,
            "body_count": 29637,
            "top_level_count": 1,
            "rulespec_count": 0,
            "refreshed_at": rows[0]["refreshed_at"],
        },
    )
    assert [call[1] for call in calls] == ["POST", "HEAD", "HEAD", "HEAD", "HEAD"]


def test_fetch_release_provision_counts_falls_back_when_exact_count_times_out(
    monkeypatch,
):
    import axiom_corpus.corpus.supabase as supabase

    calls = []

    class FakePage:
        def __init__(self, rows):
            self._rows = rows

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return json.dumps(self._rows).encode()

    class FakeHead:
        headers = {"Content-Range": "0-0/0"}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

    def fake_urlopen(req, timeout):  # noqa: ARG001
        calls.append((req.full_url, req.get_method()))
        if len(calls) == 1:
            raise urllib.error.HTTPError(
                req.full_url,
                400,
                "Bad Request",
                {},
                io.BytesIO(b'{"code":"PGRST202"}'),
            )
        if len(calls) == 2:
            raise urllib.error.HTTPError(
                req.full_url,
                500,
                "Internal Server Error",
                {},
                io.BytesIO(b'{"code":"57014"}'),
            )
        if req.get_method() == "GET":
            return FakePage([{"id": "a"}, {"id": "b"}])
        return FakeHead()

    monkeypatch.setattr(supabase.urllib.request, "urlopen", fake_urlopen)

    rows = fetch_release_provision_counts(
        ReleaseManifest(
            name="test-release",
            scopes=(ReleaseScope("us", "form", "2026-05-01"),),
        ),
        service_key="service",
        supabase_url="https://example.supabase.co",
    )

    assert rows[0]["provision_count"] == 2
    assert calls[0][1] == "POST"
    assert calls[1][1] == "HEAD"
    assert calls[2][1] == "GET"
    assert "order=id.asc" in calls[2][0]


def test_load_provisions_to_supabase_only_stages_versioned_chunks(monkeypatch):
    import axiom_corpus.corpus.supabase as supabase

    calls = []

    class FakeResponse:
        def __init__(self, body=b""):
            self.body = body

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return self.body

    def fake_urlopen(req, timeout):
        calls.append((req.full_url, req.data, timeout))
        return FakeResponse()

    monkeypatch.setattr(supabase.urllib.request, "urlopen", fake_urlopen)

    report = load_provisions_to_supabase(
        [
            ProvisionRecord(
                jurisdiction="us",
                document_class="regulation",
                citation_path="us/regulation/7/273",
                version="2026-05-13",
            ),
            ProvisionRecord(
                jurisdiction="us",
                document_class="regulation",
                citation_path="us/regulation/7/273/1",
                version="2026-05-13",
            ),
        ],
        service_key="service",
        supabase_url="https://example.supabase.co",
        chunk_size=1,
    )

    assert report.rows_total == 2
    assert report.rows_loaded == 2
    assert report.chunk_count == 2
    # Staging never refreshes or changes the active release boundary.
    assert [call[0] for call in calls] == [
        "https://example.supabase.co/rest/v1/provisions?on_conflict=id",
        "https://example.supabase.co/rest/v1/provisions?on_conflict=id",
    ]
    first_payload = json.loads(calls[0][1])
    assert first_payload[0]["citation_path"] == "us/regulation/7/273"
    assert first_payload[0]["version"] == "2026-05-13"
    assert first_payload[0]["id"] == deterministic_provision_id(
        "us/regulation/7/273",
        "2026-05-13",
    )


def test_load_provisions_to_supabase_dry_run_does_not_call_network(monkeypatch):
    import axiom_corpus.corpus.supabase as supabase

    def fake_urlopen(*args, **kwargs):
        raise AssertionError("dry-run should not call network")

    monkeypatch.setattr(supabase.urllib.request, "urlopen", fake_urlopen)

    report = load_provisions_to_supabase(
        [
            ProvisionRecord(
                jurisdiction="us",
                document_class="regulation",
                citation_path="us/regulation/7/273",
                version="2026-05-13",
            )
        ],
        service_key="",
        dry_run=True,
    )

    assert report.rows_total == 1
    assert report.rows_loaded == 0
    assert report.chunk_count == 1


def test_load_provisions_to_supabase_requires_version_for_staging(monkeypatch):
    import axiom_corpus.corpus.supabase as supabase

    def fake_urlopen(*args, **kwargs):
        raise AssertionError("validation should fail before network")

    monkeypatch.setattr(supabase.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(ValueError, match="version is required"):
        load_provisions_to_supabase(
            [
                ProvisionRecord(
                    jurisdiction="us",
                    document_class="regulation",
                    citation_path="us/regulation/7/273",
                )
            ],
            service_key="",
            dry_run=True,
        )


def test_fetch_staged_release_scope_evidence_requires_exact_rpc_surface(monkeypatch):
    import axiom_corpus.corpus.supabase as supabase

    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return json.dumps(
                [
                    {
                        "jurisdiction": "nz",
                        "document_class": "statute",
                        "version": "v1",
                        "provision_count": 11198,
                        "navigation_count": 11198,
                        "provision_projection_sha256": "a" * 64,
                        "navigation_projection_sha256": "b" * 64,
                    }
                ]
            ).encode()

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["payload"] = json.loads(req.data)
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(supabase.urllib.request, "urlopen", fake_urlopen)
    release = ReleaseManifest(
        name="nz-rulespec-v1",
        scopes=(ReleaseScope("nz", "statute", "v1"),),
    )

    assert fetch_staged_release_scope_evidence(
        release,
        service_key="service",
        supabase_url="https://example.supabase.co",
    ) == {
        ("nz", "statute", "v1"): StagedScopeEvidence(
            11198,
            11198,
            "a" * 64,
            "b" * 64,
        )
    }
    assert captured["url"].endswith("/rpc/get_staged_release_scope_evidence")
    assert captured["payload"]["p_scopes"][0]["version"] == "v1"
    assert captured["timeout"] == 600


def test_activate_corpus_release_uses_verified_management_query(monkeypatch):
    import axiom_corpus.corpus.supabase as supabase

    release_object, public_key = _signed_release_object()
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return json.dumps(
                [
                    {
                        "result": {
                            "active": True,
                            "release": "nz-rulespec-v1",
                            "content_sha256": release_object["content_sha256"],
                        }
                    }
                ]
            ).encode()

    def fake_urlopen(req, timeout):
        captured["method"] = req.get_method()
        captured["url"] = req.full_url
        captured["payload"] = json.loads(req.data)
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(supabase.urllib.request, "urlopen", fake_urlopen)

    result = activate_corpus_release(
        release_object,
        access_token="management",
        public_key=public_key,
        supabase_url="https://example.supabase.co",
    )

    assert result["active"] is True
    assert captured["method"] == "POST"
    assert captured["url"] == "https://api.supabase.com/v1/projects/example/database/query"
    assert captured["payload"] == {
        "query": "SELECT corpus.activate_corpus_release($1::jsonb) AS result",
        "parameters": [json.dumps(release_object, sort_keys=True)],
        "read_only": False,
    }
    assert captured["timeout"] == 600


def test_fetch_released_scope_objects_returns_exact_signed_rows(monkeypatch):
    import axiom_corpus.corpus.supabase as supabase

    release_object, _public_key = _signed_release_object()

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return json.dumps(
                [
                    {
                        "jurisdiction": "nz",
                        "document_class": "statute",
                        "version": "v1",
                        "release_name": "nz-rulespec-v1",
                        "content_sha256": release_object["content_sha256"],
                        "release_object": release_object,
                    }
                ]
            ).encode()

    monkeypatch.setattr(supabase.urllib.request, "urlopen", lambda *args, **kwargs: FakeResponse())
    release = ReleaseManifest(
        name="nz-rulespec-v2",
        scopes=(ReleaseScope("nz", "statute", "v1"),),
    )

    rows = fetch_released_scope_objects(
        release,
        service_key="service",
        supabase_url="https://example.supabase.co",
    )

    prior = rows[("nz", "statute", "v1")][0]
    assert prior.release_name == "nz-rulespec-v1"
    assert prior.release_object == release_object


def test_activate_rejects_invalid_signature_before_network(monkeypatch):
    import axiom_corpus.corpus.supabase as supabase

    release_object, public_key = _signed_release_object()
    release_object["signature"]["value"] = b64encode(b"invalid").decode()
    monkeypatch.setattr(
        supabase.urllib.request,
        "urlopen",
        lambda *args, **kwargs: pytest.fail("invalid object must not reach the network"),
    )

    with pytest.raises(ReleaseManifestError, match="signature is invalid"):
        activate_corpus_release(
            release_object,
            access_token="management",
            public_key=public_key,
            supabase_url="https://example.supabase.co",
        )


@pytest.mark.parametrize(
    ("response", "message"),
    [
        ({}, "unexpected staged release-evidence response"),
        ([None], "malformed row"),
        (
            [
                {
                    "jurisdiction": "",
                    "document_class": "statute",
                    "version": "v1",
                    "provision_count": 1,
                    "navigation_count": 1,
                    "provision_projection_sha256": "a" * 64,
                    "navigation_projection_sha256": "b" * 64,
                }
            ],
            "invalid staged release-evidence identity",
        ),
        (
            [
                {
                    "jurisdiction": "nz",
                    "document_class": "statute",
                    "version": "v1",
                    "provision_count": True,
                    "navigation_count": 1,
                    "provision_projection_sha256": "a" * 64,
                    "navigation_projection_sha256": "b" * 64,
                }
            ],
            "invalid staged release row count",
        ),
        (
            [
                {
                    "jurisdiction": "nz",
                    "document_class": "statute",
                    "version": "v1",
                    "provision_count": 1,
                    "navigation_count": 1,
                    "provision_projection_sha256": "invalid",
                    "navigation_projection_sha256": "b" * 64,
                }
            ],
            "invalid staged release projection digest",
        ),
        ([], "staged release-evidence scope mismatch"),
    ],
)
def test_fetch_staged_release_scope_evidence_rejects_malformed_rpc_rows(
    monkeypatch,
    response,
    message,
):
    import axiom_corpus.corpus.supabase as supabase

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return json.dumps(response).encode()

    monkeypatch.setattr(supabase.urllib.request, "urlopen", lambda *args, **kwargs: FakeResponse())
    release = ReleaseManifest(
        name="nz-rulespec-v1",
        scopes=(ReleaseScope("nz", "statute", "v1"),),
    )

    with pytest.raises(RuntimeError, match=message):
        fetch_staged_release_scope_evidence(
            release,
            service_key="service",
            supabase_url="https://example.supabase.co",
        )


@pytest.mark.parametrize(
    ("response", "message"),
    [
        ([], "unexpected corpus activation query response"),
        ([{"result": []}], "unexpected corpus activation response"),
        ([{"result": {"active": False}}], "unexpected corpus activation response"),
        (
            [
                {
                    "result": {
                        "active": True,
                        "release": "other",
                        "content_sha256": "a" * 64,
                    }
                }
            ],
            "release name does not match",
        ),
        (
            [
                {
                    "result": {
                        "active": True,
                        "release": "nz-rulespec-v1",
                        "content_sha256": "b" * 64,
                    }
                }
            ],
            "release digest does not match",
        ),
    ],
)
def test_activate_corpus_release_rejects_malformed_rpc_response(
    monkeypatch,
    response,
    message,
):
    import axiom_corpus.corpus.supabase as supabase

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return json.dumps(response).encode()

    monkeypatch.setattr(supabase.urllib.request, "urlopen", lambda *args, **kwargs: FakeResponse())
    release_object, public_key = _signed_release_object()

    with pytest.raises(RuntimeError, match=message):
        activate_corpus_release(
            release_object,
            access_token="management",
            public_key=public_key,
            supabase_url="https://example.supabase.co",
        )


def test_delete_supabase_provisions_scope_fetches_ids_then_deletes_chunks(monkeypatch):
    import axiom_corpus.corpus.supabase as supabase

    calls = []

    class FakeResponse:
        def __init__(self, body=b"{}"):
            self.body = body

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return self.body

    pages = [
        [
            {"id": "11111111-1111-1111-1111-111111111111"},
            {"id": "22222222-2222-2222-2222-222222222222"},
        ],
        [{"id": "33333333-3333-3333-3333-333333333333"}],
    ]

    def fake_urlopen(req, timeout):
        calls.append((req.full_url, req.get_method(), timeout))
        if req.get_method() == "GET":
            return FakeResponse(json.dumps(pages.pop(0)).encode())
        return FakeResponse()

    monkeypatch.setattr(supabase.urllib.request, "urlopen", fake_urlopen)

    report = delete_supabase_provisions_scope(
        jurisdiction="us-ga",
        document_class="statute",
        service_key="service",
        supabase_url="https://example.supabase.co",
        fetch_page_size=2,
        delete_chunk_size=2,
    )

    assert report.intended_rows_deleted == 3
    assert report.delete_chunk_count == 2
    assert calls[0][0].startswith("https://example.supabase.co/rest/v1/provisions?select=id")
    assert calls[0][1] == "GET"
    assert calls[2][1] == "DELETE"
    assert "id=in." in calls[2][0]


def test_resolve_service_key_prefers_service_role_env():
    key = resolve_service_key(
        "https://example.supabase.co",
        environ={"SUPABASE_SERVICE_ROLE_KEY": "service", "SUPABASE_ACCESS_TOKEN": "token"},
    )

    assert key == "service"


def test_resolve_service_key_fetches_service_role_from_management_api(monkeypatch):
    import axiom_corpus.corpus.supabase as supabase

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return b'[{"name": "service_role", "api_key": "service"}]'

    calls = []

    def fake_urlopen(req, timeout):
        calls.append((req.full_url, req.headers["Authorization"]))
        return FakeResponse()

    monkeypatch.setattr(supabase.urllib.request, "urlopen", fake_urlopen)

    key = resolve_service_key(
        "https://abc123.supabase.co",
        environ={"SUPABASE_ACCESS_TOKEN": "management"},
    )

    assert key == "service"
    assert calls == [("https://api.supabase.com/v1/projects/abc123/api-keys", "Bearer management")]


def test_refresh_corpus_analytics_calls_current_rpc(monkeypatch):
    import axiom_corpus.corpus.supabase as supabase

    calls = []

    class FakeResponse:
        def __init__(self, body=b"{}"):
            self.body = body

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return b"{}"

    def fake_urlopen(req, timeout):
        calls.append(req.full_url)
        return FakeResponse()

    monkeypatch.setattr(supabase.urllib.request, "urlopen", fake_urlopen)

    refresh_corpus_analytics(service_key="service", rest_url="https://example.supabase.co/rest/v1")

    assert calls == [
        "https://example.supabase.co/rest/v1/rpc/refresh_corpus_analytics",
    ]


def test_verify_release_coverage_flags_jurisdictions_missing_current_provisions(monkeypatch):
    """The historical UK regression: rows in navigation_nodes, zero in
    current_provisions. The check must catch this."""
    import axiom_corpus.corpus.supabase as supabase

    nav_count_rpc_rows = [
        {"jurisdiction": "us", "document_class": "statute", "node_count": 1000},
        {"jurisdiction": "uk", "document_class": "regulation", "node_count": 4705},
        {"jurisdiction": "us-ca", "document_class": "statute", "node_count": 7948},
    ]
    current_rows = [
        {"jurisdiction": "us", "document_class": "statute", "provision_count": 1000},
        {"jurisdiction": "us-ca", "document_class": "statute", "provision_count": 7948},
        # uk deliberately absent → should be flagged
    ]

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return json.dumps(self.payload).encode()

    def fake_urlopen(req, timeout):
        url = req.full_url
        if "/rpc/get_navigation_node_counts" in url:
            return FakeResponse(nav_count_rpc_rows)
        if "/current_provision_counts" in url:
            return FakeResponse(current_rows)
        raise AssertionError(f"unexpected URL {url}")

    monkeypatch.setattr(supabase.urllib.request, "urlopen", fake_urlopen)

    report = verify_release_coverage(
        service_key="service",
        supabase_url="https://example.supabase.co",
    )

    assert report.ok is False
    assert len(report.missing_current_provisions) == 1
    finding = report.missing_current_provisions[0]
    assert finding.jurisdiction == "uk"
    assert finding.document_class == "regulation"
    assert finding.navigation_node_count == 4705
    assert finding.current_provision_count == 0


def test_verify_release_coverage_clean_when_all_jurisdictions_covered(monkeypatch):
    import axiom_corpus.corpus.supabase as supabase

    nav_count_rpc_rows = [
        {"jurisdiction": "us", "document_class": "statute", "node_count": 1000},
        {"jurisdiction": "uk", "document_class": "regulation", "node_count": 4705},
    ]
    current_rows = [
        {"jurisdiction": "us", "document_class": "statute", "provision_count": 1000},
        {"jurisdiction": "uk", "document_class": "regulation", "provision_count": 4705},
    ]

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return json.dumps(self.payload).encode()

    def fake_urlopen(req, timeout):
        url = req.full_url
        if "/rpc/get_navigation_node_counts" in url:
            return FakeResponse(nav_count_rpc_rows)
        if "/current_provision_counts" in url:
            return FakeResponse(current_rows)
        raise AssertionError(f"unexpected URL {url}")

    monkeypatch.setattr(supabase.urllib.request, "urlopen", fake_urlopen)

    report = verify_release_coverage(
        service_key="service",
        supabase_url="https://example.supabase.co",
    )

    assert report.ok is True
    assert report.missing_current_provisions == ()


def test_delete_supabase_provisions_scope_limits_deletes_to_versions(monkeypatch):
    import axiom_corpus.corpus.supabase as supabase

    calls = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return b"[]"

    def fake_urlopen(req, timeout):
        calls.append(req.full_url)
        return FakeResponse()

    monkeypatch.setattr(supabase.urllib.request, "urlopen", fake_urlopen)

    delete_supabase_provisions_scope(
        jurisdiction="ca",
        document_class="policy",
        service_key="service",
        supabase_url="https://example.supabase.co",
        versions=["2026-07-01-cra-2025-alternative-minimum-tax"],
    )

    assert "version=in." in calls[0]
    assert "2026-07-01-cra-2025-alternative-minimum-tax" in calls[0]
