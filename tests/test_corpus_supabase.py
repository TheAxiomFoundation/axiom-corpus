import hashlib
import io
import json
import urllib.error
import urllib.parse
from base64 import b64encode

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from axiom_corpus.corpus.models import ProvisionRecord
from axiom_corpus.corpus.releases import (
    COMPLETE_EXPRESSION_DATES_PROFILE,
    ReleaseManifest,
    ReleaseScope,
)
from axiom_corpus.corpus.supabase import (
    ACTIVATE_RELEASE_QUERY,
    PREVIEW_ACTIVATION_QUERY,
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
    preview_corpus_release_activation,
    provision_to_supabase_row,
    refresh_corpus_analytics,
    resolve_service_key,
    verify_release_coverage,
    write_supabase_rows_jsonl,
)
from axiom_corpus.release.manifest import (
    ReleaseManifestError,
    build_unsigned_release_object,
    canonical_json_bytes,
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
        "quality_profile": COMPLETE_EXPRESSION_DATES_PROFILE,
        "scopes": [{key: scope[key] for key in ("jurisdiction", "document_class", "version")}],
    }
    selector_digest = hashlib.sha256(
        json.dumps(selector, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    content = {
        "release": "nz-rulespec-v1",
        "quality_profile": COMPLETE_EXPRESSION_DATES_PROFILE,
        "created_at": "2026-07-10T00:00:00Z",
        "selector_sha256": selector_digest,
        "corpus_base": "data/corpus",
        "git": {"commit": "a" * 40, "committed_at": "2026-07-10T00:00:00Z"},
        "r2": {"bucket": "axiom-corpus", "addressing": "sha256"},
        "scopes": [scope],
        "artifacts": artifacts,
        "validation": {
            "passed": True,
            "quality_profile": COMPLETE_EXPRESSION_DATES_PROFILE,
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


class FakeSupabaseProvisions:
    """Stateful PostgREST double for ``corpus.provisions`` staging.

    Simulates the constraints the live table enforces — the ``rules_pkey``
    primary key, the ``idx_provisions_citation_path_version`` unique index,
    the ``parent_id`` foreign key, and its ON DELETE CASCADE — so staging
    tests observe realistic failure modes instead of a permissive stub.
    """

    def __init__(self, rows=()):
        self.rows: dict[str, dict] = {}
        for row in rows:
            self.rows[str(row["id"])] = dict(row)
        self.calls: list[tuple[str, str]] = []

    def seed_record(self, record, *, row_id=None, parent_id=None):
        row = provision_to_supabase_row(record, versioned_ids=True)
        if row_id is not None:
            row["id"] = row_id
        if parent_id is not None:
            row["parent_id"] = parent_id
        self.rows[str(row["id"])] = row
        return row

    def urlopen(self, req, timeout):  # noqa: ARG002 - signature matches urllib
        method = req.get_method()
        parsed = urllib.parse.urlparse(req.full_url)
        params = dict(urllib.parse.parse_qsl(parsed.query))
        self.calls.append((method, req.full_url))
        if method == "GET":
            return self._get(params)
        if method == "POST":
            return self._insert(json.loads(req.data))
        if method == "DELETE":
            return self._delete(params)
        if method == "PATCH":
            return self._update(params, json.loads(req.data))
        raise AssertionError(f"unexpected method {method}")

    @staticmethod
    def _response(payload=b""):
        class _Resp:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return None

            def read(self):
                return payload

        return _Resp()

    @staticmethod
    def _conflict(code, message):
        body = json.dumps({"code": code, "message": message}).encode()
        return urllib.error.HTTPError("url", 409, "Conflict", {}, io.BytesIO(body))

    @staticmethod
    def _parse_in(value):
        inner = value.removeprefix("in.(").removesuffix(")")
        return [item.strip().strip('"') for item in inner.split(",") if item.strip()]

    def _get(self, params):
        matches = list(self.rows.values())
        for column in ("jurisdiction", "doc_type", "version"):
            if column in params:
                expected = params[column].removeprefix("eq.")
                matches = [row for row in matches if str(row.get(column) or "") == expected]
        if "parent_id" in params:
            wanted = set(self._parse_in(params["parent_id"]))
            matches = [row for row in matches if str(row.get("parent_id")) in wanted]
        matches.sort(key=lambda row: str(row["id"]))
        if "id" in params and params["id"].startswith("gt."):
            cursor = params["id"].removeprefix("gt.")
            matches = [row for row in matches if str(row["id"]) > cursor]
        if "limit" in params:
            matches = matches[: int(params["limit"])]
        return self._response(json.dumps(matches).encode())

    def _insert(self, payload):
        # One POST is one atomic statement: validate every row against the
        # current state and the rest of the payload before mutating anything.
        staged_keys = {
            (row["citation_path"], row["version"]): row_id for row_id, row in self.rows.items()
        }
        visible_ids = set(self.rows)
        for row in payload:
            if str(row["id"]) in visible_ids:
                raise self._conflict("23505", "duplicate key value violates rules_pkey")
            if (row["citation_path"], row["version"]) in staged_keys:
                raise self._conflict(
                    "23505",
                    "duplicate key value violates unique constraint "
                    '"idx_provisions_citation_path_version"',
                )
            visible_ids.add(str(row["id"]))
            staged_keys[(row["citation_path"], row["version"])] = str(row["id"])
        for row in payload:
            parent_id = row.get("parent_id")
            if parent_id is not None and str(parent_id) not in visible_ids:
                raise self._conflict("23503", f"parent_id {parent_id} is not present")
        for row in payload:
            self.rows[str(row["id"])] = dict(row)
        return self._response()

    def _delete(self, params):
        # parent_id is ON DELETE CASCADE on the live table: deletion reaches
        # exactly the descendants of the deleted ids, nothing else.
        doomed = set(self._parse_in(params["id"])) & set(self.rows)
        frontier = set(doomed)
        while frontier:
            frontier = {
                row_id
                for row_id, row in self.rows.items()
                if row_id not in doomed
                and row.get("parent_id") is not None
                and str(row["parent_id"]) in frontier
            }
            doomed |= frontier
        for row_id in doomed:
            self.rows.pop(row_id, None)
        return self._response()

    def _update(self, params, payload):
        row_id = params["id"].removeprefix("eq.")
        row = self.rows.get(row_id)
        if row is None:
            return self._response(b"[]")
        if "parent_id" in params:
            condition = params["parent_id"]
            if condition == "is.null":
                if row.get("parent_id") is not None:
                    return self._response(b"[]")
            elif str(row.get("parent_id")) != condition.removeprefix("eq."):
                return self._response(b"[]")
        updated = {**row, **payload}
        new_parent = updated.get("parent_id")
        if new_parent is not None and str(new_parent) not in self.rows:
            raise self._conflict("23503", f"parent_id {new_parent} is not present")
        for other_id, other in self.rows.items():
            if other_id != row_id and (other["citation_path"], other["version"]) == (
                updated["citation_path"],
                updated["version"],
            ):
                raise self._conflict(
                    "23505",
                    "duplicate key value violates unique constraint "
                    '"idx_provisions_citation_path_version"',
                )
        self.rows[row_id] = updated
        return self._response(json.dumps([updated]).encode())

    def write_calls(self):
        return [call for call in self.calls if call[0] != "GET"]


def _record(citation_path, *, version="2026-05-13", parent=None, body=None, level=0, ordinal=0):
    return ProvisionRecord(
        jurisdiction="us",
        document_class="regulation",
        citation_path=citation_path,
        version=version,
        parent_citation_path=parent,
        body=body,
        level=level,
        ordinal=ordinal,
    )


def test_load_provisions_to_supabase_stages_fresh_scope_with_plain_inserts(monkeypatch):
    import axiom_corpus.corpus.supabase as supabase

    fake = FakeSupabaseProvisions()
    monkeypatch.setattr(supabase.urllib.request, "urlopen", fake.urlopen)

    report = load_provisions_to_supabase(
        [
            _record("us/regulation/7/273"),
            _record("us/regulation/7/273/1", parent="us/regulation/7/273", level=1),
        ],
        service_key="service",
        supabase_url="https://example.supabase.co",
        chunk_size=1,
    )

    assert report.rows_total == 2
    assert report.rows_loaded == 2
    assert report.chunk_count == 2
    assert report.rows_inserted == 2
    assert report.rows_replaced == 0
    assert report.rows_already_staged == 0
    inserts = [call for call in fake.calls if call[0] == "POST"]
    # Plain inserts: verified staging never asks PostgREST to resolve
    # conflicts, so the URL carries no on_conflict clause.
    assert [url for _, url in inserts] == [
        "https://example.supabase.co/rest/v1/provisions",
        "https://example.supabase.co/rest/v1/provisions",
    ]
    root_id = deterministic_provision_id("us/regulation/7/273", "2026-05-13")
    assert fake.rows[root_id]["citation_path"] == "us/regulation/7/273"
    child_id = deterministic_provision_id("us/regulation/7/273/1", "2026-05-13")
    assert fake.rows[child_id]["parent_id"] == root_id


def test_load_provisions_to_supabase_is_noop_for_identically_staged_rows(monkeypatch):
    import axiom_corpus.corpus.supabase as supabase

    records = [
        _record("us/regulation/7/273"),
        _record("us/regulation/7/273/1", parent="us/regulation/7/273", level=1),
    ]
    fake = FakeSupabaseProvisions()
    for record in records:
        fake.seed_record(record)
    monkeypatch.setattr(supabase.urllib.request, "urlopen", fake.urlopen)
    before = {row_id: dict(row) for row_id, row in fake.rows.items()}

    report = load_provisions_to_supabase(
        records,
        service_key="service",
        supabase_url="https://example.supabase.co",
    )

    assert report.rows_total == 2
    assert report.rows_loaded == 2
    assert report.rows_already_staged == 2
    assert report.rows_inserted == 0
    assert report.rows_replaced == 0
    assert fake.write_calls() == []
    assert fake.rows == before


def test_load_provisions_to_supabase_converges_superseded_id_scheme(monkeypatch):
    """The SOUTHMOD publish regression: an earlier ingest staged identical
    content under unversioned legacy ids, which made the historical
    ``on_conflict=id`` upsert die on the (citation_path, version) unique
    index. The load must converge identity without touching content."""
    import axiom_corpus.corpus.supabase as supabase

    records = [
        _record("us/regulation/7/273", body="root text"),
        _record("us/regulation/7/273/1", parent="us/regulation/7/273", body="child", level=1),
    ]
    fake = FakeSupabaseProvisions()
    legacy_root = deterministic_provision_id("us/regulation/7/273")
    fake.seed_record(records[0], row_id=legacy_root)
    fake.seed_record(
        records[1],
        row_id=deterministic_provision_id("us/regulation/7/273/1"),
        parent_id=legacy_root,
    )
    monkeypatch.setattr(supabase.urllib.request, "urlopen", fake.urlopen)

    report = load_provisions_to_supabase(
        records,
        service_key="service",
        supabase_url="https://example.supabase.co",
    )

    assert report.rows_loaded == 2
    assert report.rows_replaced == 2
    assert report.rows_inserted == 0
    root_id = deterministic_provision_id("us/regulation/7/273", "2026-05-13")
    child_id = deterministic_provision_id("us/regulation/7/273/1", "2026-05-13")
    assert set(fake.rows) == {root_id, child_id}
    assert fake.rows[root_id]["body"] == "root text"
    assert fake.rows[child_id]["parent_id"] == root_id

    # A second identical load reaches the fixpoint: nothing is written.
    fake.calls.clear()
    rerun = load_provisions_to_supabase(
        records,
        service_key="service",
        supabase_url="https://example.supabase.co",
    )
    assert rerun.rows_already_staged == 2
    assert fake.write_calls() == []


def test_load_provisions_to_supabase_fails_loud_on_content_mismatch(monkeypatch):
    import axiom_corpus.corpus.supabase as supabase
    from axiom_corpus.corpus.supabase import ProvisionStagingConflictError

    fake = FakeSupabaseProvisions()
    fake.seed_record(_record("us/regulation/7/273", body="staged text"))
    monkeypatch.setattr(supabase.urllib.request, "urlopen", fake.urlopen)
    before = {row_id: dict(row) for row_id, row in fake.rows.items()}

    with pytest.raises(ProvisionStagingConflictError) as excinfo:
        load_provisions_to_supabase(
            [_record("us/regulation/7/273", body="different text")],
            service_key="service",
            supabase_url="https://example.supabase.co",
        )

    assert excinfo.value.conflicts == (
        {
            "kind": "content-mismatch",
            "citation_path": "us/regulation/7/273",
            "version": "2026-05-13",
            "fields": ["body"],
            "staged_id": deterministic_provision_id("us/regulation/7/273", "2026-05-13"),
        },
    )
    assert fake.write_calls() == []
    assert fake.rows == before


def test_load_provisions_to_supabase_fails_loud_on_unexpected_staged_rows(monkeypatch):
    import axiom_corpus.corpus.supabase as supabase
    from axiom_corpus.corpus.supabase import ProvisionStagingConflictError

    fake = FakeSupabaseProvisions()
    fake.seed_record(_record("us/regulation/7/273"))
    fake.seed_record(_record("us/regulation/7/999"))
    monkeypatch.setattr(supabase.urllib.request, "urlopen", fake.urlopen)

    with pytest.raises(ProvisionStagingConflictError) as excinfo:
        load_provisions_to_supabase(
            [_record("us/regulation/7/273")],
            service_key="service",
            supabase_url="https://example.supabase.co",
        )

    kinds = {conflict["kind"] for conflict in excinfo.value.conflicts}
    assert kinds == {"unexpected-staged-row"}
    assert excinfo.value.conflicts[0]["citation_path"] == "us/regulation/7/999"
    assert fake.write_calls() == []


def test_load_provisions_to_supabase_refuses_cascade_outside_load(monkeypatch):
    import axiom_corpus.corpus.supabase as supabase
    from axiom_corpus.corpus.supabase import ProvisionStagingConflictError

    fake = FakeSupabaseProvisions()
    legacy_root = deterministic_provision_id("us/regulation/7/273")
    fake.seed_record(_record("us/regulation/7/273"), row_id=legacy_root)
    # A different, unloaded scope staged a child under the legacy root id;
    # deleting the root would cascade into that scope.
    fake.seed_record(
        _record("us/regulation/7/273/1", version="2026-04-01", level=1),
        parent_id=legacy_root,
    )
    monkeypatch.setattr(supabase.urllib.request, "urlopen", fake.urlopen)
    before = {row_id: dict(row) for row_id, row in fake.rows.items()}

    with pytest.raises(ProvisionStagingConflictError) as excinfo:
        load_provisions_to_supabase(
            [_record("us/regulation/7/273")],
            service_key="service",
            supabase_url="https://example.supabase.co",
        )

    assert {conflict["kind"] for conflict in excinfo.value.conflicts} == {"cascade-outside-load"}
    assert excinfo.value.conflicts[0]["version"] == "2026-04-01"
    assert fake.write_calls() == []
    assert fake.rows == before


def test_load_provisions_to_supabase_converges_stale_parent_pointer_in_place(monkeypatch):
    import axiom_corpus.corpus.supabase as supabase

    records = [
        _record("us/regulation/7/273", body="root"),
        _record("us/regulation/7/274", body="other root", ordinal=1),
        _record("us/regulation/7/273/1", parent="us/regulation/7/273", body="child", level=1),
    ]
    fake = FakeSupabaseProvisions()
    fake.seed_record(records[0])
    other_root = fake.seed_record(records[1])
    # The child was staged with the canonical id but attached to the wrong,
    # still-surviving parent row.
    fake.seed_record(records[2], parent_id=other_root["id"])
    monkeypatch.setattr(supabase.urllib.request, "urlopen", fake.urlopen)

    report = load_provisions_to_supabase(
        records,
        service_key="service",
        supabase_url="https://example.supabase.co",
    )

    assert report.rows_replaced == 1
    assert report.rows_already_staged == 2
    patches = [call for call in fake.calls if call[0] == "PATCH"]
    assert len(patches) == 1
    child_id = deterministic_provision_id("us/regulation/7/273/1", "2026-05-13")
    assert fake.rows[child_id]["parent_id"] == deterministic_provision_id(
        "us/regulation/7/273", "2026-05-13"
    )


def test_load_provisions_to_supabase_converges_cross_scope_stale_parent_edges(monkeypatch):
    """The Ghana ingest staged one statute tree across several scope
    versions, with children in one version pointing at a stale parent id
    staged under another version. Loading every scope in one call must
    converge the whole edge set; the cascade guard only fires when the
    dependent scope is left out of the load (covered separately)."""
    import axiom_corpus.corpus.supabase as supabase

    parent_a = _record("us/statute/act-896", version="2026-05-13", body="act")
    child_b = _record(
        "us/statute/act-896/second-schedule",
        version="2026-06-01",
        parent="us/statute/act-896",
        body="schedule",
        level=1,
    )
    parent_b = _record("us/statute/act-896", version="2026-06-01", body="act")

    fake = FakeSupabaseProvisions()
    # Scope A's parent was staged under a superseded id scheme...
    stale_parent = fake.seed_record(parent_a, row_id="99999999-9999-5999-8999-999999999999")
    # ...and scope B's child hangs off that stale id; B's own parent row was
    # never staged at all.
    fake.seed_record(
        child_b,
        row_id=deterministic_provision_id("us/statute/act-896/second-schedule"),
        parent_id=stale_parent["id"],
    )
    monkeypatch.setattr(supabase.urllib.request, "urlopen", fake.urlopen)

    report = load_provisions_to_supabase(
        [parent_a, parent_b, child_b],
        service_key="service",
        supabase_url="https://example.supabase.co",
    )

    assert report.rows_loaded == 3
    assert report.rows_replaced == 2
    assert report.rows_inserted == 1
    parent_a_id = deterministic_provision_id("us/statute/act-896", "2026-05-13")
    parent_b_id = deterministic_provision_id("us/statute/act-896", "2026-06-01")
    child_b_id = deterministic_provision_id("us/statute/act-896/second-schedule", "2026-06-01")
    assert set(fake.rows) == {parent_a_id, parent_b_id, child_b_id}
    assert fake.rows[child_b_id]["parent_id"] == parent_b_id


def test_load_provisions_to_supabase_escalates_cascade_closure_through_kept_rows(monkeypatch):
    """A replaced ancestor cascade-deletes staged descendants even when their
    own rows are already canonical. The closure must escalate those
    descendants to replacements (and un-count them as already staged) so the
    load re-creates everything the delete takes down."""
    import axiom_corpus.corpus.supabase as supabase

    grandparent = _record("us/regulation/7", body="g")
    parent = _record("us/regulation/7/273", parent="us/regulation/7", body="p", level=1)
    child = _record("us/regulation/7/273/1", parent="us/regulation/7/273", body="c", level=2)

    fake = FakeSupabaseProvisions()
    legacy_grandparent = deterministic_provision_id("us/regulation/7")
    fake.seed_record(grandparent, row_id=legacy_grandparent)
    # The parent already carries its canonical id but still points at the
    # legacy grandparent; the child is fully canonical.
    fake.seed_record(parent, parent_id=legacy_grandparent)
    fake.seed_record(child)
    monkeypatch.setattr(supabase.urllib.request, "urlopen", fake.urlopen)

    report = load_provisions_to_supabase(
        [grandparent, parent, child],
        service_key="service",
        supabase_url="https://example.supabase.co",
    )

    assert report.rows_loaded == 3
    assert report.rows_replaced == 3
    assert report.rows_already_staged == 0
    grandparent_id = deterministic_provision_id("us/regulation/7", "2026-05-13")
    parent_id = deterministic_provision_id("us/regulation/7/273", "2026-05-13")
    child_id = deterministic_provision_id("us/regulation/7/273/1", "2026-05-13")
    assert set(fake.rows) == {grandparent_id, parent_id, child_id}
    assert fake.rows[parent_id]["parent_id"] == grandparent_id
    assert fake.rows[child_id]["parent_id"] == parent_id


def test_load_provisions_to_supabase_rejects_duplicate_incoming_keys(monkeypatch):
    import axiom_corpus.corpus.supabase as supabase

    def fail_urlopen(*args, **kwargs):
        raise AssertionError("duplicate keys must fail before network")

    monkeypatch.setattr(supabase.urllib.request, "urlopen", fail_urlopen)

    with pytest.raises(ValueError, match="repeats an immutable provision key"):
        load_provisions_to_supabase(
            [
                _record("us/regulation/7/273"),
                _record("us/regulation/7/273"),
            ],
            service_key="service",
            supabase_url="https://example.supabase.co",
        )


def test_update_supabase_provision_parent_requires_exactly_one_affected_row(monkeypatch):
    import axiom_corpus.corpus.supabase as supabase

    fake = FakeSupabaseProvisions()
    monkeypatch.setattr(supabase.urllib.request, "urlopen", fake.urlopen)

    with pytest.raises(RuntimeError, match="expected exactly 1"):
        supabase.update_supabase_provision_parent(
            row_id="00000000-0000-0000-0000-000000000000",
            new_parent_id=None,
            verified_parent_id=None,
            service_key="service",
            rest_url="https://example.supabase.co/rest/v1",
        )


def test_load_provisions_to_supabase_flags_jsonb_value_type_drift(monkeypatch):
    """Python's ``True == 1`` must not mask a jsonb value-type change in
    ``identifiers``: boolean true and numeric 1 are distinct stored values."""
    import axiom_corpus.corpus.supabase as supabase
    from axiom_corpus.corpus.supabase import ProvisionStagingConflictError

    record = ProvisionRecord(
        jurisdiction="us",
        document_class="regulation",
        citation_path="us/regulation/7/273",
        version="2026-05-13",
        identifiers={"source:flag": True},
    )
    fake = FakeSupabaseProvisions()
    staged = fake.seed_record(record)
    staged["identifiers"] = {"source:flag": 1}
    monkeypatch.setattr(supabase.urllib.request, "urlopen", fake.urlopen)

    with pytest.raises(ProvisionStagingConflictError) as excinfo:
        load_provisions_to_supabase(
            [record],
            service_key="service",
            supabase_url="https://example.supabase.co",
        )

    assert excinfo.value.conflicts[0]["kind"] == "content-mismatch"
    assert excinfo.value.conflicts[0]["fields"] == ["identifiers"]
    assert fake.write_calls() == []


def test_provision_column_equal_matches_projection_digest_semantics():
    from axiom_corpus.corpus.supabase import _provision_column_equal

    # Digest-contract values: bool and int stay distinct, exact values equal.
    assert _provision_column_equal("identifiers", {"k": 1}, {"k": 1})
    assert not _provision_column_equal("identifiers", {"k": True}, {"k": 1})
    # The signed digest contract renders int 1 and str "1" identically (both
    # hash as text "1", matching SQL jsonb_each_text), so staging must treat
    # them as interchangeable or it would conflict on states the release
    # evidence gate accepts.
    assert _provision_column_equal("identifiers", {"k": "1"}, {"k": 1})
    # Out-of-contract values (floats) fall back to canonical JSON, so
    # numerically-equal-but-differently-spelled values stay a loud conflict —
    # publication rejects floats at digest time regardless.
    assert _provision_column_equal("identifiers", {"k": 1.5}, {"k": 1.5})
    assert not _provision_column_equal("identifiers", {"k": 1}, {"k": 1.0})


def test_load_provisions_to_supabase_orders_inserts_by_dependency_not_input(monkeypatch):
    """A child listed before its parent, with equal levels and chunk_size=1,
    must still insert parent-first: order comes from the actual parent links,
    not from input order or an assumed level invariant."""
    import axiom_corpus.corpus.supabase as supabase

    child = _record("us/regulation/7/273/1", parent="us/regulation/7/273", level=0)
    parent = _record("us/regulation/7/273", level=0)
    fake = FakeSupabaseProvisions()
    monkeypatch.setattr(supabase.urllib.request, "urlopen", fake.urlopen)
    inserted_paths = []
    original_insert = supabase.insert_supabase_rows

    def recording_insert(rows, **kwargs):
        inserted_paths.extend(str(row["citation_path"]) for row in rows)
        original_insert(rows, **kwargs)

    monkeypatch.setattr(supabase, "insert_supabase_rows", recording_insert)

    report = load_provisions_to_supabase(
        [child, parent],
        service_key="service",
        supabase_url="https://example.supabase.co",
        chunk_size=1,
    )

    assert report.rows_inserted == 2
    child_id = deterministic_provision_id("us/regulation/7/273/1", "2026-05-13")
    parent_id = deterministic_provision_id("us/regulation/7/273", "2026-05-13")
    assert inserted_paths == ["us/regulation/7/273", "us/regulation/7/273/1"]
    assert fake.rows[child_id]["parent_id"] == parent_id


def test_load_provisions_to_supabase_rejects_cyclic_parent_linkage(monkeypatch):
    import axiom_corpus.corpus.supabase as supabase
    from axiom_corpus.corpus.supabase import ProvisionStagingConflictError

    first = ProvisionRecord(
        jurisdiction="us",
        document_class="regulation",
        citation_path="us/regulation/7/a",
        version="2026-05-13",
        id=deterministic_provision_id("us/regulation/7/a", "2026-05-13"),
        parent_id=deterministic_provision_id("us/regulation/7/b", "2026-05-13"),
    )
    second = ProvisionRecord(
        jurisdiction="us",
        document_class="regulation",
        citation_path="us/regulation/7/b",
        version="2026-05-13",
        id=deterministic_provision_id("us/regulation/7/b", "2026-05-13"),
        parent_id=deterministic_provision_id("us/regulation/7/a", "2026-05-13"),
    )
    fake = FakeSupabaseProvisions()
    monkeypatch.setattr(supabase.urllib.request, "urlopen", fake.urlopen)

    with pytest.raises(ProvisionStagingConflictError) as excinfo:
        load_provisions_to_supabase(
            [first, second],
            service_key="service",
            supabase_url="https://example.supabase.co",
        )

    assert {conflict["kind"] for conflict in excinfo.value.conflicts} == {"cyclic-parent-linkage"}
    assert fake.write_calls() == []


def test_load_provisions_to_supabase_recheck_catches_concurrent_dependent(monkeypatch):
    """A child staged by a concurrent writer between planning and deletion
    must abort the load before any delete, not be cascade-deleted."""
    import axiom_corpus.corpus.supabase as supabase
    from axiom_corpus.corpus.supabase import ProvisionStagingConflictError

    record = _record("us/regulation/7/273", body="root")
    fake = FakeSupabaseProvisions()
    legacy_root = deterministic_provision_id("us/regulation/7/273")
    fake.seed_record(record, row_id=legacy_root)
    monkeypatch.setattr(supabase.urllib.request, "urlopen", fake.urlopen)

    real_plan = supabase._plan_provision_staging

    def plan_then_race(*args, **kwargs):
        plan = real_plan(*args, **kwargs)
        fake.seed_record(
            _record(
                "us/regulation/7/273/raced",
                version="2026-06-01",
                body="late child",
                level=1,
            ),
            parent_id=legacy_root,
        )
        return plan

    monkeypatch.setattr(supabase, "_plan_provision_staging", plan_then_race)

    with pytest.raises(ProvisionStagingConflictError) as excinfo:
        load_provisions_to_supabase(
            [record],
            service_key="service",
            supabase_url="https://example.supabase.co",
        )

    assert excinfo.value.conflicts[0]["kind"] == "cascade-outside-load"
    assert excinfo.value.conflicts[0]["citation_path"] == "us/regulation/7/273/raced"
    # Nothing was deleted: both the stale root and the raced child survive.
    assert legacy_root in fake.rows
    assert not [call for call in fake.calls if call[0] == "DELETE"]


def test_load_provisions_to_supabase_conditional_patch_fails_on_concurrent_repoint(monkeypatch):
    """An in-place converge whose row was re-pointed by a concurrent writer
    after planning must fail loudly, not overwrite the newer state."""
    import axiom_corpus.corpus.supabase as supabase

    records = [
        _record("us/regulation/7/273", body="root"),
        _record("us/regulation/7/274", body="other root", ordinal=1),
        _record("us/regulation/7/273/1", parent="us/regulation/7/273", body="child", level=1),
    ]
    fake = FakeSupabaseProvisions()
    fake.seed_record(records[0])
    other_root = fake.seed_record(records[1])
    child_staged = fake.seed_record(records[2], parent_id=other_root["id"])
    monkeypatch.setattr(supabase.urllib.request, "urlopen", fake.urlopen)

    real_plan = supabase._plan_provision_staging

    def plan_then_race(*args, **kwargs):
        plan = real_plan(*args, **kwargs)
        fake.rows[str(child_staged["id"])]["parent_id"] = deterministic_provision_id(
            "us/regulation/7/273", "2026-05-13"
        )
        return plan

    monkeypatch.setattr(supabase, "_plan_provision_staging", plan_then_race)

    with pytest.raises(RuntimeError, match="changed or vanished after verification"):
        load_provisions_to_supabase(
            records,
            service_key="service",
            supabase_url="https://example.supabase.co",
        )


def test_iter_supabase_rows_ordinal_shim_indexes_within_each_scope():
    """A multi-scope iterable (the release-level publish load) must shim
    out-of-range ordinals to the row's position within its own scope, exactly
    matching the per-scope signed evidence digests."""
    records = [
        ProvisionRecord(
            jurisdiction="us",
            document_class="statute",
            citation_path="us/statute/20/1",
            version="2026-05-13",
            ordinal=10701001001,
        ),
        ProvisionRecord(
            jurisdiction="us",
            document_class="statute",
            citation_path="us/statute/21/1",
            version="2026-06-01",
            ordinal=10701001002,
        ),
        ProvisionRecord(
            jurisdiction="us",
            document_class="statute",
            citation_path="us/statute/21/2",
            version="2026-06-01",
            ordinal=10701001003,
        ),
    ]

    combined = list(iter_supabase_rows(records))
    per_scope = list(iter_supabase_rows(records[:1])) + list(iter_supabase_rows(records[1:]))

    assert [row["ordinal"] for row in combined] == [0, 0, 1]
    assert [row["ordinal"] for row in combined] == [row["ordinal"] for row in per_scope]


def test_insert_supabase_rows_surfaces_constraint_violations(monkeypatch):
    import axiom_corpus.corpus.supabase as supabase

    record = _record("us/regulation/7/273")
    fake = FakeSupabaseProvisions()
    staged = fake.seed_record(record)
    monkeypatch.setattr(supabase.urllib.request, "urlopen", fake.urlopen)

    with pytest.raises(RuntimeError, match="insert failed 409"):
        supabase.insert_supabase_rows(
            [dict(staged, id="11111111-1111-5111-8111-111111111111")],
            service_key="service",
            rest_url="https://example.supabase.co/rest/v1",
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
    captured = []

    def fake_run(command, *, input, capture_output, check, timeout):
        payload = json.loads(input)
        captured.append((command, payload, capture_output, check, timeout))
        query = payload["query"]
        if query == supabase.STAGE_RELEASE_ACTIVATION_CHUNK_QUERY:
            response = [{"chunk_index": payload["parameters"][3]}]
        elif query == ACTIVATE_RELEASE_QUERY:
            response = [
                {
                    "result": {
                        "active": True,
                        "release": "nz-rulespec-v1",
                        "content_sha256": release_object["content_sha256"],
                        "scope_count": 1,
                        "scopes": {
                            "activated": [
                                {"jurisdiction": "nz", "document_class": "statute"}
                            ],
                            "reaffirmed": [],
                        },
                    }
                }
            ]
        else:
            response = []
        return supabase.subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(response).encode(),
            stderr=b"",
        )

    monkeypatch.setattr(supabase.subprocess, "run", fake_run)

    result = activate_corpus_release(
        release_object,
        access_token="management",
        public_key=public_key,
        supabase_url="https://example.supabase.co",
    )

    assert result["active"] is True
    assert len(captured) == 4
    for command, _payload, capture_output, check, _timeout in captured:
        assert command[0] == "curl"
        assert "--fail-with-body" in command
        assert "--data-binary" in command
        assert command[-1] == "https://api.supabase.com/v1/projects/example/database/query"
        assert "Authorization: Bearer management" in command
        assert "User-Agent: axiom-corpus/0.1" in command
        assert capture_output is True
        assert check is False

    staged = [
        payload
        for _command, payload, _capture, _check, _timeout in captured
        if payload["query"] == supabase.STAGE_RELEASE_ACTIVATION_CHUNK_QUERY
    ]
    assert len(staged) == 1
    assert staged[0]["parameters"][1:3] == [
        "nz-rulespec-v1",
        release_object["content_sha256"],
    ]
    assert staged[0]["parameters"][3:5] == [0, 1]
    assert staged[0]["parameters"][5] == canonical_json_bytes(release_object).decode("ascii")

    activation = next(
        payload
        for _command, payload, _capture, _check, _timeout in captured
        if payload["query"] == ACTIVATE_RELEASE_QUERY
    )
    assert activation["parameters"][1:3] == [
        "nz-rulespec-v1",
        release_object["content_sha256"],
    ]
    assert activation["read_only"] is False


def test_preview_corpus_release_activation_sends_compact_verified_identity(monkeypatch):
    import axiom_corpus.corpus.supabase as supabase

    release_object, public_key = _signed_release_object()
    captured = {}

    def fake_post(url, *, payload, access_token, timeout):
        captured.update(
            url=url,
            payload=payload,
            access_token=access_token,
            timeout=timeout,
        )
        return []

    monkeypatch.setattr(supabase, "_management_api_post_json_with_curl", fake_post)

    assert preview_corpus_release_activation(
        release_object,
        access_token="management",
        public_key=public_key,
        supabase_url="https://example.supabase.co",
    ) == []

    assert captured["payload"]["query"] == PREVIEW_ACTIVATION_QUERY
    assert captured["payload"]["read_only"] is True
    preview_object = json.loads(captured["payload"]["parameters"][0])
    assert preview_object == {
        "release": "nz-rulespec-v1",
        "content": {"scopes": release_object["content"]["scopes"]},
    }
    assert len(json.dumps(captured["payload"])) < 2_000
    assert captured["access_token"] == "management"
    assert captured["timeout"] == 120


def test_stage_release_activation_upload_bounds_every_management_request(monkeypatch):
    import axiom_corpus.corpus.supabase as supabase

    release_object = {
        "release": "large-release",
        "content_sha256": "a" * 64,
        "content": {"artifacts": ["x" * 400_000]},
    }
    calls = []

    def fake_post(url, *, payload, access_token, timeout):
        calls.append(payload)
        if payload["query"] == supabase.STAGE_RELEASE_ACTIVATION_CHUNK_QUERY:
            return [{"chunk_index": payload["parameters"][3]}]
        return []

    monkeypatch.setattr(supabase, "_management_api_post_json_with_curl", fake_post)
    monkeypatch.setattr(supabase.secrets, "token_hex", lambda _size: "b" * 64)

    upload_id, object_sha256 = supabase._stage_release_activation_upload(
        release_object,
        endpoint="https://api.supabase.test/query",
        access_token="management",
    )

    staged = [
        payload
        for payload in calls
        if payload["query"] == supabase.STAGE_RELEASE_ACTIVATION_CHUNK_QUERY
    ]
    assert upload_id == "b" * 64
    assert object_sha256 == hashlib.sha256(canonical_json_bytes(release_object)).hexdigest()
    assert len(staged) == 4
    assert all(len(json.dumps(payload)) < 140_000 for payload in staged)
    assert "".join(payload["parameters"][5] for payload in staged) == canonical_json_bytes(
        release_object
    ).decode("ascii")


def test_apply_release_activation_upload_migration_uses_expected_project(monkeypatch):
    import axiom_corpus.corpus.supabase as supabase

    captured = {}
    migration = "\n".join(
        (
            "CREATE TABLE IF NOT EXISTS corpus.release_activation_upload_chunks",
            "CREATE OR REPLACE FUNCTION corpus.load_release_activation_upload",
            "REVOKE ALL ON corpus.release_activation_upload_chunks",
        )
    )

    def fake_post(url, *, payload, access_token, timeout):
        captured.update(
            url=url,
            payload=payload,
            access_token=access_token,
            timeout=timeout,
        )
        return []

    monkeypatch.setattr(supabase, "_management_api_post_json_with_curl", fake_post)
    supabase.apply_release_activation_upload_migration(
        migration,
        access_token="management",
        supabase_url="https://example.supabase.co",
        expected_project_ref="example",
    )

    assert captured == {
        "url": "https://api.supabase.com/v1/projects/example/database/query",
        "payload": {"query": migration, "read_only": False},
        "access_token": "management",
        "timeout": 120,
    }


def test_apply_release_activation_upload_migration_rejects_incomplete_sql(monkeypatch):
    import axiom_corpus.corpus.supabase as supabase

    monkeypatch.setattr(
        supabase,
        "_management_api_post_json_with_curl",
        lambda *args, **kwargs: pytest.fail("incomplete migration must not reach the network"),
    )
    with pytest.raises(RuntimeError, match="migration is incomplete"):
        supabase.apply_release_activation_upload_migration(
            "SELECT 1",
            access_token="management",
            supabase_url="https://example.supabase.co",
        )


def test_activate_corpus_release_reports_curl_http_body(monkeypatch):
    import axiom_corpus.corpus.supabase as supabase

    release_object, public_key = _signed_release_object()
    monkeypatch.setattr(
        supabase.subprocess,
        "run",
        lambda *args, **kwargs: supabase.subprocess.CompletedProcess(
            args[0], 22, stdout=b'{"message":"invalid query"}', stderr=b"curl: (22) 400"
        ),
    )

    with pytest.raises(RuntimeError, match="invalid query"):
        activate_corpus_release(
            release_object,
            access_token="management",
            public_key=public_key,
            supabase_url="https://example.supabase.co",
        )


class _ReleasedRowsResponse:
    def __init__(self, rows):
        self._rows = rows

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self):
        return json.dumps(self._rows).encode()


def _membership(scope: ReleaseScope) -> dict[str, str]:
    return {
        "jurisdiction": scope.jurisdiction,
        "document_class": scope.document_class,
        "version": scope.version,
    }


def _object_set(
    release_object: dict, release_name: str, scopes: tuple[ReleaseScope, ...]
) -> dict[str, object]:
    return {
        "release_name": release_name,
        "content_sha256": release_object["content_sha256"],
        "release_object": {**release_object, "release": release_name},
        "scopes": [_membership(scope) for scope in scopes],
    }


def _requested_scopes(req) -> list[dict[str, str]]:
    return json.loads(req.data)["p_scopes"]


def test_fetch_released_scope_objects_fetches_each_signed_object_once(monkeypatch):
    import axiom_corpus.corpus.supabase as supabase

    release_object, _public_key = _signed_release_object()
    scopes = tuple(ReleaseScope("nz", "statute", f"v{index}") for index in range(55))
    calls = []

    def fake_urlopen(req, **kwargs):
        calls.append(req)
        return _ReleasedRowsResponse([_object_set(release_object, "nz-rulespec-v1", scopes)])

    monkeypatch.setattr(supabase.urllib.request, "urlopen", fake_urlopen)
    rows = fetch_released_scope_objects(
        ReleaseManifest(name="nz-rulespec-v2", scopes=scopes),
        service_key="service",
        supabase_url="https://example.supabase.co",
    )

    assert len(calls) == 1
    assert calls[0].method == "POST"
    assert calls[0].full_url.endswith("/rpc/get_released_scope_object_sets")
    assert len(_requested_scopes(calls[0])) == len(scopes)
    assert set(rows) == {scope.key for scope in scopes}
    assert all(rows[scope.key][0].release_object == release_object for scope in scopes)


def test_fetch_released_scope_objects_splits_rejected_server_batches(monkeypatch):
    import axiom_corpus.corpus.supabase as supabase

    scopes = tuple(ReleaseScope("nz", "statute", f"v{index}") for index in range(5))
    requested_sizes = []

    def fake_urlopen(req, **kwargs):
        size = len(_requested_scopes(req))
        requested_sizes.append(size)
        if size > 2:
            raise urllib.error.HTTPError(req.full_url, 520, "origin error", {}, io.BytesIO())
        return _ReleasedRowsResponse([])

    monkeypatch.setattr(supabase.urllib.request, "urlopen", fake_urlopen)
    rows = fetch_released_scope_objects(
        ReleaseManifest(name="nz-rulespec-v2", scopes=scopes),
        service_key="service",
        supabase_url="https://example.supabase.co",
    )

    assert requested_sizes == [5, 2, 3, 1, 2]
    assert all(rows[scope.key] == () for scope in scopes)


def test_fetch_released_scope_objects_retries_single_scope_server_error(monkeypatch):
    import axiom_corpus.corpus.supabase as supabase

    release_object, _public_key = _signed_release_object()
    scope = ReleaseScope("nz", "statute", "v1")
    calls = 0
    sleeps = []

    def fake_urlopen(req, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise urllib.error.HTTPError(req.full_url, 520, "origin error", {}, io.BytesIO())
        return _ReleasedRowsResponse(
            [_object_set(release_object, "nz-rulespec-v1", (scope,))]
        )

    monkeypatch.setattr(supabase.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(supabase.time, "sleep", sleeps.append)
    rows = fetch_released_scope_objects(
        ReleaseManifest(name="nz-rulespec-v2", scopes=(scope,)),
        service_key="service",
        supabase_url="https://example.supabase.co",
    )

    assert calls == 2
    assert sleeps == [supabase._RELEASED_SCOPE_FETCH_BASE_BACKOFF_SECONDS]
    assert rows[scope.key][0].release_name == "nz-rulespec-v1"


@pytest.mark.parametrize(
    "error",
    [
        urllib.error.URLError("temporary network failure"),
        ConnectionResetError("connection reset by peer"),
    ],
)
def test_fetch_released_scope_objects_retries_network_errors(monkeypatch, error):
    import axiom_corpus.corpus.supabase as supabase

    scope = ReleaseScope("nz", "statute", "v1")
    calls = 0
    sleeps = []

    def fake_urlopen(req, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise error
        return _ReleasedRowsResponse([])

    monkeypatch.setattr(supabase.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(supabase.time, "sleep", sleeps.append)
    rows = fetch_released_scope_objects(
        ReleaseManifest(name="nz-rulespec-v2", scopes=(scope,)),
        service_key="service",
        supabase_url="https://example.supabase.co",
    )

    assert calls == 2
    assert sleeps == [supabase._RELEASED_SCOPE_FETCH_BASE_BACKOFF_SECONDS]
    assert rows[scope.key] == ()


def test_fetch_released_scope_objects_splits_after_network_retries(monkeypatch):
    import axiom_corpus.corpus.supabase as supabase

    scopes = tuple(ReleaseScope("nz", "statute", f"v{index}") for index in range(4))
    requested_sizes = []
    sleeps = []

    def fake_urlopen(req, **kwargs):
        size = len(_requested_scopes(req))
        requested_sizes.append(size)
        if size == len(scopes):
            raise ConnectionResetError("connection reset by peer")
        return _ReleasedRowsResponse([])

    monkeypatch.setattr(supabase.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(supabase.time, "sleep", sleeps.append)
    rows = fetch_released_scope_objects(
        ReleaseManifest(name="nz-rulespec-v2", scopes=scopes),
        service_key="service",
        supabase_url="https://example.supabase.co",
    )

    assert requested_sizes == [4, 4, 4, 2, 2]
    assert sleeps == [
        supabase._RELEASED_SCOPE_FETCH_BASE_BACKOFF_SECONDS,
        supabase._RELEASED_SCOPE_FETCH_BASE_BACKOFF_SECONDS * 2,
    ]
    assert all(rows[scope.key] == () for scope in scopes)


@pytest.mark.parametrize("status", [413, 414])
def test_fetch_released_scope_objects_splits_oversized_requests(monkeypatch, status):
    import axiom_corpus.corpus.supabase as supabase

    scopes = tuple(ReleaseScope("nz", "statute", f"v{index}") for index in range(5))
    requested_sizes = []

    def fake_urlopen(req, **kwargs):
        size = len(_requested_scopes(req))
        requested_sizes.append(size)
        if size > 2:
            raise urllib.error.HTTPError(req.full_url, status, "too large", {}, io.BytesIO())
        return _ReleasedRowsResponse([])

    monkeypatch.setattr(supabase.urllib.request, "urlopen", fake_urlopen)
    rows = fetch_released_scope_objects(
        ReleaseManifest(name="nz-rulespec-v2", scopes=scopes),
        service_key="service",
        supabase_url="https://example.supabase.co",
    )

    assert requested_sizes == [5, 2, 3, 1, 2]
    assert all(rows[scope.key] == () for scope in scopes)


def test_fetch_released_scope_objects_exhausts_network_retries(monkeypatch):
    import axiom_corpus.corpus.supabase as supabase

    scope = ReleaseScope("nz", "statute", "v1")
    calls = 0
    sleeps = []

    def fake_urlopen(req, **kwargs):
        nonlocal calls
        calls += 1
        raise TimeoutError("network timeout")

    monkeypatch.setattr(supabase.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(supabase.time, "sleep", sleeps.append)
    with pytest.raises(TimeoutError, match="network timeout"):
        fetch_released_scope_objects(
            ReleaseManifest(name="nz-rulespec-v2", scopes=(scope,)),
            service_key="service",
            supabase_url="https://example.supabase.co",
        )

    assert calls == supabase._RELEASED_SCOPE_FETCH_MAX_ATTEMPTS
    assert sleeps == [
        supabase._RELEASED_SCOPE_FETCH_BASE_BACKOFF_SECONDS,
        supabase._RELEASED_SCOPE_FETCH_BASE_BACKOFF_SECONDS * 2,
    ]


def test_fetch_released_scope_objects_mixed_released_and_unreleased(monkeypatch):
    import axiom_corpus.corpus.supabase as supabase

    release_object, _public_key = _signed_release_object()
    scopes = tuple(ReleaseScope("nz", "statute", f"v{index}") for index in range(3))
    object_sets = [
        _object_set(release_object, "nz-rulespec-v1a", (scopes[0], scopes[2])),
        _object_set(release_object, "nz-rulespec-v1b", (scopes[0],)),
    ]

    def fake_urlopen(req, **kwargs):
        return _ReleasedRowsResponse(object_sets)

    monkeypatch.setattr(supabase.urllib.request, "urlopen", fake_urlopen)
    rows = fetch_released_scope_objects(
        ReleaseManifest(name="nz-rulespec-v2", scopes=scopes),
        service_key="service",
        supabase_url="https://example.supabase.co",
    )

    assert [item.release_name for item in rows[scopes[0].key]] == [
        "nz-rulespec-v1a",
        "nz-rulespec-v1b",
    ]
    assert rows[scopes[1].key] == ()
    assert [item.release_name for item in rows[scopes[2].key]] == ["nz-rulespec-v1a"]


def test_fetch_released_scope_objects_rejects_rows_outside_their_batch(monkeypatch):
    import axiom_corpus.corpus.supabase as supabase

    scopes = tuple(ReleaseScope("nz", "statute", f"v{index}") for index in range(2))
    outside = ReleaseScope("nz", "statute", "outside")
    release_object, _public_key = _signed_release_object()

    def fake_urlopen(req, **kwargs):
        return _ReleasedRowsResponse(
            [_object_set(release_object, "nz-rulespec-v1", (outside,))]
        )

    monkeypatch.setattr(supabase.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(RuntimeError, match="unknown scope"):
        fetch_released_scope_objects(
            ReleaseManifest(name="nz-rulespec-v2", scopes=scopes),
            service_key="service",
            supabase_url="https://example.supabase.co",
        )


@pytest.mark.parametrize("fault", ["duplicate", "conflict", "identity", "empty_scopes"])
def test_fetch_released_scope_objects_rejects_invalid_object_rows(monkeypatch, fault):
    import axiom_corpus.corpus.supabase as supabase

    release_object, _public_key = _signed_release_object()
    scope = ReleaseScope("nz", "statute", "v1")
    valid = _object_set(release_object, "nz-rulespec-v1", (scope,))
    if fault == "duplicate":
        object_rows = [valid, valid]
        message = "duplicate"
    elif fault == "conflict":
        conflicting = {
            **valid,
            "content_sha256": "f" * 64,
            "release_object": {
                **valid["release_object"],
                "content_sha256": "f" * 64,
            },
            "scopes": [_membership(scope)],
        }
        object_rows = [valid, conflicting]
        message = "conflicting objects"
    elif fault == "identity":
        object_rows = [{**valid, "content_sha256": "f" * 64}]
        message = "inconsistent object identity"
    else:
        object_rows = [{**valid, "scopes": []}]
        message = "malformed memberships"

    def fake_urlopen(req, **kwargs):
        return _ReleasedRowsResponse(object_rows)

    monkeypatch.setattr(supabase.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(RuntimeError, match=message):
        fetch_released_scope_objects(
            ReleaseManifest(name="nz-rulespec-v2", scopes=(scope,)),
            service_key="service",
            supabase_url="https://example.supabase.co",
        )


def test_activate_rejects_invalid_signature_before_network(monkeypatch):
    import axiom_corpus.corpus.supabase as supabase

    release_object, public_key = _signed_release_object()
    release_object["signature"]["value"] = b64encode(b"invalid").decode()
    monkeypatch.setattr(
        supabase.subprocess,
        "run",
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

    queries = []

    def fake_post(_url, *, payload, **_kwargs):
        queries.append(payload["query"])
        if payload["query"] == supabase.STAGE_RELEASE_ACTIVATION_CHUNK_QUERY:
            return [{"chunk_index": payload["parameters"][3]}]
        if payload["query"] == ACTIVATE_RELEASE_QUERY:
            return response
        return []

    monkeypatch.setattr(supabase, "_management_api_post_json_with_curl", fake_post)
    release_object, public_key = _signed_release_object()

    with pytest.raises(RuntimeError, match=message):
        activate_corpus_release(
            release_object,
            access_token="management",
            public_key=public_key,
            supabase_url="https://example.supabase.co",
        )
    assert supabase.DELETE_RELEASE_ACTIVATION_UPLOAD_QUERY in queries


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
