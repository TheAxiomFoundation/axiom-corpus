"""Batched validation preserves selector policy and replays scope notices."""

import json
import tempfile
from dataclasses import replace
from pathlib import Path

import pytest
from hypothesis import example, given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus import cli, release_quality
from axiom_corpus.corpus.content_quality import CONTENT_CHECK_VERSION
from axiom_corpus.corpus.release_policy import (
    ContentBaseline,
    ReleaseGatePolicy,
    ReleasePolicyError,
    SelectorAllowance,
    scan_scope,
)
from axiom_corpus.corpus.releases import ReleaseManifest
from axiom_corpus.release.manifest import selector_sha256
from tests.test_release_policy import (
    CLEAN_ROWS,
    HOLLOW_ROWS,
    OTHER,
    SCOPE,
    _withdrawn,
    _write_scope,
)


@pytest.mark.parametrize("workers", [1, 2])
def test_batch_policy_is_selector_specific_and_content_notices_are_replayed(tmp_path, workers):
    _write_scope(tmp_path, SCOPE, CLEAN_ROWS)
    _write_scope(tmp_path, OTHER, HOLLOW_ROWS)
    allowed = ReleaseManifest("allowed", (SCOPE, OTHER))
    denied = ReleaseManifest("denied", (SCOPE, OTHER))
    edited = ReleaseManifest("allowed", (SCOPE,))
    policy = ReleaseGatePolicy(
        withdrawn=_withdrawn(SelectorAllowance(allowed.name, selector_sha256(allowed))),
        content_baseline=ContentBaseline(
            CONTENT_CHECK_VERSION, {OTHER.key: scan_scope(tmp_path, OTHER)}
        ),
    )
    releases = [allowed, denied, edited]
    for limit in (1, 200):
        reports = release_quality.validate_releases(
            tmp_path, releases, policy=policy, workers=workers, max_issues=limit,
            strict_warnings=True,
        )
        assert [report.to_mapping() for report in reports] == [
            release_quality.validate_release(
                tmp_path, release, policy=policy, max_issues=limit, strict_warnings=True
            ).to_mapping()
            for release in releases
        ]
        assert [report.ok for report in reports] == [True, False, False]
        assert [report.notice_count for report in reports] == [2, 1, 0]
        assert reports[0].to_mapping()["notices"][0]["code"] == "withdrawn_scope_grandfathered"
        assert [issue.code for issue in reports[1].issues] == ["withdrawn_scope_selected"]


@settings(max_examples=12, deadline=None)
@example(baseline_state="mismatched", copies=2, limit=1)
@example(baseline_state="stale", copies=2, limit=1)
@given(
    baseline_state=st.sampled_from(["absent", "recorded", "mismatched", "stale"]),
    copies=st.integers(1, 4), limit=st.integers(1, 3),
)
def test_cached_content_errors_and_notices_equal_independent_validation(baseline_state, copies, limit):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        _write_scope(root, OTHER, HOLLOW_ROWS)
        entry = scan_scope(root, OTHER)
        if baseline_state == "mismatched":
            entry = replace(entry, provisions_sha256="0" * 64)
        policy = ReleaseGatePolicy(
            content_baseline=ContentBaseline(
                "content-check-v0" if baseline_state == "stale" else CONTENT_CHECK_VERSION,
                {OTHER.key: entry} if baseline_state != "absent" else {},
            )
        )
        releases = [ReleaseManifest(f"cut-{n}", (OTHER,)) for n in range(copies)]
        reports = release_quality.validate_releases(root, releases, policy=policy, max_issues=limit)
        for release, report in zip(releases, reports, strict=True):
            assert report.to_mapping() == release_quality.validate_release(
                root, release, policy=policy, max_issues=limit
            ).to_mapping()
            assert (report.error_count, report.notice_count) == (
                (0, 1) if baseline_state == "recorded" else (2, 0)
            )
            assert report.warning_count == int(baseline_state in {"stale", "mismatched"})


def test_batch_cli_fails_closed_on_an_unreadable_policy(tmp_path, monkeypatch, capsys):
    paths = []
    for name in ("one", "two"):
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps({"name": name, "scopes": [
            {"jurisdiction": SCOPE.jurisdiction, "document_class": SCOPE.document_class,
             "version": SCOPE.version}
        ]}))
        paths.extend(["--release", str(path)])

    def unreadable(_root):
        raise ReleasePolicyError("unreadable policy")

    monkeypatch.setattr(ReleaseGatePolicy, "for_corpus", unreadable)
    assert cli.main(["validate-release", *paths, "--base", str(tmp_path)]) == 2
    output = capsys.readouterr()
    assert "validate-release: unreadable policy" in output.err
    assert not output.out


def test_batch_cli_reports_both_selectors_and_grandfathered_notices(tmp_path, monkeypatch, capsys):
    _write_scope(tmp_path, SCOPE, CLEAN_ROWS)
    allowed = ReleaseManifest("allowed", (SCOPE,))
    policy = ReleaseGatePolicy(
        withdrawn=_withdrawn(SelectorAllowance(allowed.name, selector_sha256(allowed)))
    )
    monkeypatch.setattr(ReleaseGatePolicy, "for_corpus", lambda _root: policy)
    paths = []
    for name in ("denied", "allowed"):
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps({"name": name, "scopes": [
            {"jurisdiction": SCOPE.jurisdiction, "document_class": SCOPE.document_class,
             "version": SCOPE.version}
        ]}))
        paths.extend(["--release", str(path)])
    assert cli.main(["validate-release", *paths, "--base", str(tmp_path)]) == 2
    output = capsys.readouterr()
    assert output.out.count('"release_path":') == 2
    assert '"code": "withdrawn_scope_grandfathered"' in output.out
    assert '"code": "withdrawn_scope_selected"' in output.out
    assert "2 selectors, 1 ok" in output.err


def test_content_check_runs_after_pytest_without_background_workers():
    workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/ci.yml").read_text()
    assert "Start the release content baseline check" not in workflow
    assert workflow.index("pytest -v") < workflow.index(
        "axiom-corpus-ingest content-check --all --check-baseline"
    )
    assert "content-check.rc" not in workflow
