"""Hermetic unit tests for the corpus publication driver and staleness guard.

These cover the pure decision logic — scope derivation from provisions files,
the git-vs-DB publish plan split, and the staleness classification — using tiny
fixture JSONL trees in ``tmp_path``. Network-touching steps (sync-r2,
load-supabase, Supabase reads) are not exercised here; they are thin wrappers
over already-tested corpus CLI commands.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_script(name: str):
    path = REPO_ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


publish = _load_script("publish_corpus")
staleness = _load_script("check_publication_staleness")


def _write_provisions(root: Path, rel: str, records: list[dict]) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    return path


def _rec(jurisdiction: str, document_class: str, version: str, cite: str) -> dict:
    return {
        "jurisdiction": jurisdiction,
        "document_class": document_class,
        "version": version,
        "citation_path": cite,
        "body": "text",
    }


# --------------------------------------------------------------------------- #
# file_scopes
# --------------------------------------------------------------------------- #
def test_file_scopes_derives_scope_from_records(tmp_path, monkeypatch):
    root = tmp_path / "provisions"
    monkeypatch.setattr(publish, "PROVISIONS_ROOT", root)
    p = _write_provisions(
        root,
        "us-al/statute/2026-07-02-us-al-title-38.jsonl",
        [_rec("us-al", "statute", "2026-07-02-us-al-title-38", "us-al/statute/title-38")],
    )
    scopes, skipped = publish.file_scopes([p])
    assert skipped == []
    assert len(scopes) == 1
    fs = scopes[0]
    assert fs.db_scope == ("us-al", "statute", "2026-07-02-us-al-title-38")
    # Artifact stem is the filename stem, used for the R2 --version filter.
    assert fs.artifact_stem == "2026-07-02-us-al-title-38"


def test_file_scopes_uses_record_version_not_path_stem(tmp_path, monkeypatch):
    """When a file's record version differs from its filename stem, the DB
    scope must follow the record version while the R2 stem follows the path."""
    root = tmp_path / "provisions"
    monkeypatch.setattr(publish, "PROVISIONS_ROOT", root)
    p = _write_provisions(
        root,
        "us/statute/2026-05-10-snap-sections.jsonl",
        [_rec("us", "statute", "2026-04-29", "us/statute/snap/1")],
    )
    scopes, skipped = publish.file_scopes([p])
    assert skipped == []
    assert scopes[0].db_scope == ("us", "statute", "2026-04-29")
    assert scopes[0].artifact_stem == "2026-05-10-snap-sections"


def test_file_scopes_skips_unparseable_and_empty(tmp_path, monkeypatch):
    root = tmp_path / "provisions"
    monkeypatch.setattr(publish, "PROVISIONS_ROOT", root)
    # Legacy shape without jurisdiction/document_class — cannot be loaded.
    legacy = root / "us/guidance/2026-05-17-ssa.jsonl"
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text(json.dumps({"body": "x", "citation_path": "us/guidance/ssa/1"}) + "\n")
    empty = root / "us/guidance/empty.jsonl"
    empty.write_text("\n")
    scopes, skipped = publish.file_scopes([legacy, empty])
    assert scopes == []
    assert len(skipped) == 2
    reasons = {r for _, r in skipped}
    assert any("unparseable" in r for r in reasons)
    assert "empty" in reasons


def test_file_scopes_multiple_versions_in_one_file(tmp_path, monkeypatch):
    root = tmp_path / "provisions"
    monkeypatch.setattr(publish, "PROVISIONS_ROOT", root)
    p = _write_provisions(
        root,
        "be/statute/2026-06-30-be-tax-benefit.jsonl",
        [
            _rec("be", "statute", "2026-06-30-be-tax-benefit", "be/statute/a"),
            _rec("be-vlg", "statute", "2026-06-30-be-tax-benefit", "be-vlg/statute/a"),
        ],
    )
    scopes, _ = publish.file_scopes([p])
    got = {s.db_scope for s in scopes}
    assert got == {
        ("be", "statute", "2026-06-30-be-tax-benefit"),
        ("be-vlg", "statute", "2026-06-30-be-tax-benefit"),
    }


# --------------------------------------------------------------------------- #
# build_publish_plan
# --------------------------------------------------------------------------- #
def _fs(j: str, dc: str, v: str, path: str = "x.jsonl") -> publish.FileScope:
    return publish.FileScope(
        path=Path(path), jurisdiction=j, document_class=dc, version=v, artifact_stem=v
    )


def test_plan_publishes_only_absent_scopes():
    new = _fs("ng", "statute", "2026-07-06-ng-core")
    active = _fs("us", "statute", "2026-04-29")
    staged = _fs("us-ny", "regulation", "2026-05-09")
    to_pub, already, held = publish.build_publish_plan(
        [new, active, staged],
        active_scopes={("us", "statute", "2026-04-29")},
        all_scope_versions={
            ("us", "statute", "2026-04-29"),
            ("us-ny", "regulation", "2026-05-09"),  # inactive row present
        },
    )
    assert [s.db_scope for s in to_pub] == [("ng", "statute", "2026-07-06-ng-core")]
    assert [s.db_scope for s in already] == [("us", "statute", "2026-04-29")]
    # An inactive release_scopes row means "deliberately staged/superseded":
    # the automation must not implicitly publish it.
    assert [s.db_scope for s in held] == [("us-ny", "regulation", "2026-05-09")]


def test_plan_dedupes_same_scope_across_files():
    a = _fs("be", "statute", "2026-06-30-be-tax-benefit", "file-a.jsonl")
    b = _fs("be", "statute", "2026-06-30-be-tax-benefit", "file-b.jsonl")
    to_pub, _, _ = publish.build_publish_plan(
        [a, b], active_scopes=set(), all_scope_versions=set()
    )
    assert len(to_pub) == 1


def test_plan_is_order_stable():
    scopes = [
        _fs("us", "statute", "v2"),
        _fs("be", "statute", "v1"),
        _fs("us", "guidance", "v1"),
    ]
    to_pub, _, _ = publish.build_publish_plan(
        scopes, active_scopes=set(), all_scope_versions=set()
    )
    assert [s.db_scope for s in to_pub] == [
        ("be", "statute", "v1"),
        ("us", "guidance", "v1"),
        ("us", "statute", "v2"),
    ]


# --------------------------------------------------------------------------- #
# _is_provisions_jsonl
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "rel,expected",
    [
        ("data/corpus/provisions/us-al/statute/2026-07-02-x.jsonl", True),
        ("data/corpus/provisions/us-al/statute/x.json", False),  # not jsonl
        ("data/corpus/snapshots/provision-counts-2026-07-06.json", False),
        ("data/corpus/provisions/us-al/2026-07-02.jsonl", False),  # wrong depth
        ("data/corpus/sources/us-al/statute/2026/raw.jsonl", False),  # not provisions
    ],
)
def test_is_provisions_jsonl(rel, expected):
    assert publish._is_provisions_jsonl(rel) is expected


# --------------------------------------------------------------------------- #
# staleness guard classification
# --------------------------------------------------------------------------- #
def test_staleness_collects_scopes_with_commit_time(tmp_path, monkeypatch):
    root = tmp_path / "provisions"
    monkeypatch.setattr(staleness, "PROVISIONS_ROOT", root)
    _write_provisions(
        root,
        "ng/statute/2026-07-06-ng-core.jsonl",
        [_rec("ng", "statute", "2026-07-06-ng-core", "ng/statute/a")],
    )
    old = datetime(2026, 7, 6, tzinfo=UTC)
    monkeypatch.setattr(
        staleness, "_git_commit_epoch", lambda path: int(old.timestamp())
    )
    got = staleness.collect_git_scopes(cutoff=None)
    assert len(got) == 1
    assert got[0].scope == ("ng", "statute", "2026-07-06-ng-core")
    assert got[0].committed_at == old


def test_staleness_cutoff_excludes_pre_automation_files(tmp_path, monkeypatch):
    root = tmp_path / "provisions"
    monkeypatch.setattr(staleness, "PROVISIONS_ROOT", root)
    _write_provisions(
        root, "old/statute/v.jsonl", [_rec("old", "statute", "v", "old/statute/a")]
    )
    # File committed well before the cutoff.
    monkeypatch.setattr(
        staleness,
        "_git_commit_epoch",
        lambda path: int(datetime(2026, 1, 1, tzinfo=UTC).timestamp()),
    )
    cutoff = datetime(2026, 7, 4, tzinfo=UTC)
    assert staleness.collect_git_scopes(cutoff=cutoff) == []


def test_staleness_lag_math(tmp_path, monkeypatch):
    """A scope committed >max_lag ago and not active is lagging; a fresh one
    inside the grace window is not."""
    now = datetime.now(UTC)
    stale_gs = staleness.GitScope(
        scope=("us", "statute", "stale"),
        path="us/statute/stale.jsonl",
        committed_at=now - timedelta(hours=48),
    )
    fresh_gs = staleness.GitScope(
        scope=("us", "statute", "fresh"),
        path="us/statute/fresh.jsonl",
        committed_at=now - timedelta(hours=2),
    )
    active_gs = staleness.GitScope(
        scope=("us", "statute", "live"),
        path="us/statute/live.jsonl",
        committed_at=now - timedelta(hours=48),
    )
    monkeypatch.setattr(
        staleness, "collect_git_scopes", lambda cutoff: [stale_gs, fresh_gs, active_gs]
    )
    monkeypatch.setattr(
        staleness,
        "fetch_scopes",
        lambda **kw: {("us", "statute", "live")} if kw["active"] else set(),
    )
    monkeypatch.setattr(staleness, "resolve_service_key", lambda *a, **k: "key")
    rc = staleness.main(["--max-lag-hours", "24"])
    assert rc == 1  # the 48h-old unpublished scope trips the guard


def test_staleness_all_published_is_green(tmp_path, monkeypatch):
    now = datetime.now(UTC)
    gs = staleness.GitScope(
        scope=("us", "statute", "live"),
        path="us/statute/live.jsonl",
        committed_at=now - timedelta(hours=48),
    )
    monkeypatch.setattr(staleness, "collect_git_scopes", lambda cutoff: [gs])
    monkeypatch.setattr(
        staleness, "fetch_scopes", lambda **kw: {("us", "statute", "live")}
    )
    monkeypatch.setattr(staleness, "resolve_service_key", lambda *a, **k: "key")
    assert staleness.main(["--max-lag-hours", "24"]) == 0


# --------------------------------------------------------------------------- #
# refresh_analytics resilience (gateway timeout is normal on this DB)
# --------------------------------------------------------------------------- #
def _http_error(code: int):
    import urllib.error

    return urllib.error.HTTPError(
        url="http://x", code=code, msg="timeout", hdrs=None, fp=None
    )


def test_refresh_swallows_gateway_504_then_polls_to_success(monkeypatch):
    """A 504 from the refresh RPC means the DB is still working; the driver
    polls the count view until the expected scope appears."""
    calls = {"refresh": 0, "verify": 0}

    def fake_refresh(**kwargs):
        calls["refresh"] += 1
        raise _http_error(504)

    poll_results = [
        {},  # first poll: not yet visible
        {("ng", "statute"): 4},  # second poll: landed
    ]

    def fake_verify(**kwargs):
        calls["verify"] += 1
        return poll_results.pop(0) if poll_results else {("ng", "statute"): 4}

    # refresh_analytics imports refresh_corpus_analytics locally from the
    # source module, so patch it there.
    import axiom_corpus.corpus.supabase as sb

    monkeypatch.setattr(sb, "refresh_corpus_analytics", fake_refresh)
    monkeypatch.setattr(publish, "verify_scope_counts", fake_verify)

    publish.refresh_analytics(
        supabase_url="http://x",
        service_key="k",
        expected_pairs={("ng", "statute")},
        poll_deadline_s=10,
        poll_interval_s=0,
    )
    assert calls["refresh"] == 1
    assert calls["verify"] >= 2  # polled until visible


def test_refresh_reraises_non_gateway_http_error(monkeypatch):
    import axiom_corpus.corpus.supabase as sb

    def fake_refresh(**kwargs):
        raise _http_error(400)

    monkeypatch.setattr(sb, "refresh_corpus_analytics", fake_refresh)
    with pytest.raises(Exception) as excinfo:
        publish.refresh_analytics(
            supabase_url="http://x", service_key="k", expected_pairs={("ng", "statute")}
        )
    assert "400" in str(excinfo.value)


def test_is_transient_classification():
    assert publish._is_transient("HTTP Error 500: Internal Server Error")
    assert publish._is_transient("HTTP Error 502: Bad Gateway")
    assert publish._is_transient("urllib.error.HTTPError: HTTP Error 504: Gateway Timeout")
    assert publish._is_transient("connection timed out")
    # Deterministic data errors are NOT transient.
    assert not publish._is_transient(
        'upsert failed 409: violates foreign key constraint "rules_parent_id_fkey"'
    )
    assert not publish._is_transient('upsert failed 400: time zone "x" not recognized')
    # Regression: the chunk-size "500 rows" in load progress must not read as a
    # transient HTTP 500.
    assert not publish._is_transient(
        "processed Supabase chunk 1 (500 rows)\n"
        'RuntimeError: upsert failed 409: {"code":"23503",'
        '"message":"violates foreign key constraint rules_parent_id_fkey"}'
    )


def _fake_proc(returncode: int, stderr: str = ""):
    import subprocess

    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout="", stderr=stderr)


def test_load_retries_on_transient_then_succeeds(monkeypatch):
    calls = {"n": 0}

    def fake_ingest(cmd):
        calls["n"] += 1
        if calls["n"] == 1:
            return _fake_proc(1, "HTTP Error 503: Service Unavailable")
        return _fake_proc(0)

    monkeypatch.setattr(publish, "_ingest", fake_ingest)
    import time as _t

    monkeypatch.setattr(_t, "sleep", lambda s: None)
    fs = _fs("ng", "statute", "v1", "ng/statute/v1.jsonl")
    publish._load_supabase(fs, 500, retries=2, backoff_s=0)
    assert calls["n"] == 2  # retried once, then succeeded


def test_load_fails_fast_on_data_error(monkeypatch):
    calls = {"n": 0}

    def fake_ingest(cmd):
        calls["n"] += 1
        return _fake_proc(1, 'upsert failed 409: violates foreign key constraint')

    monkeypatch.setattr(publish, "_ingest", fake_ingest)
    fs = _fs("be", "regulation", "v1", "be/regulation/v1.jsonl")
    with pytest.raises(RuntimeError):
        publish._load_supabase(fs, 500, retries=3, backoff_s=0)
    assert calls["n"] == 1  # no retries on a deterministic 409


def test_refresh_success_no_poll(monkeypatch):
    import axiom_corpus.corpus.supabase as sb

    monkeypatch.setattr(sb, "refresh_corpus_analytics", lambda **kw: None)
    called = {"verify": 0}
    monkeypatch.setattr(
        publish,
        "verify_scope_counts",
        lambda **kw: called.__setitem__("verify", called["verify"] + 1) or {},
    )
    publish.refresh_analytics(
        supabase_url="http://x", service_key="k", expected_pairs={("ng", "statute")}
    )
    # Clean refresh returns immediately; no polling needed.
    assert called["verify"] == 0
