"""Offline tests for scripts/build_ccdf_state_plan_manifests.py: row identity on
manifests/ccdf-agent-queue.yaml, and the two things a full rebuild must not destroy.

The queue does not hold one row per jurisdiction. Three rows carry jurisdiction ``us`` (the ACF
plan directory, 45 CFR part 98, the CCDBG statute) and two carry ``us-in`` (the ACF-118 plan and
the FSSA CCDF Policy Manual), so a row's identity is its ``target_manifest``. Every test here
runs against a copy of the committed queue in tmp_path; no test fetches the ACF index.
"""

from __future__ import annotations

import copy
import importlib.util
import shutil
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "build_ccdf_state_plan_manifests.py"
QUEUE = REPO_ROOT / "manifests" / "ccdf-agent-queue.yaml"

_spec = importlib.util.spec_from_file_location("build_ccdf_state_plan_manifests", SCRIPT)
assert _spec and _spec.loader
ccdf = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = ccdf
_spec.loader.exec_module(ccdf)

IN_PLAN_ROW = "manifests/us-in-ccdf-state-plan-fy2025-2027.yaml"
IN_MANUAL_ROW = "manifests/us-in-ccdf-sources.yaml"
FEDERAL_ROW = "manifests/us-ccdf-sources.yaml"


def committed_queue() -> dict[str, Any]:
    payload = yaml.safe_load(QUEUE.read_text())
    assert isinstance(payload, dict) and isinstance(payload["states"], list)
    return payload


def queue_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, plans: bool = False) -> Path:
    """Point the script's ROOT at a tmp_path copy of the queue (and of the plan manifests)."""
    (tmp_path / "manifests").mkdir()
    shutil.copy(QUEUE, tmp_path / "manifests" / "ccdf-agent-queue.yaml")
    if plans:
        for path in (REPO_ROOT / "manifests").glob("us-*-ccdf-state-plan-fy2025-2027.yaml"):
            shutil.copy(path, tmp_path / "manifests" / path.name)
    monkeypatch.setattr(ccdf, "ROOT", tmp_path)
    return tmp_path / "manifests" / "ccdf-agent-queue.yaml"


def stub_index(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    """The 56 ACF index rows, read back from the index facts the committed queue records."""
    rows = [
        {"name": state["name"], "code": state["jurisdiction"].removeprefix("us-"),
         "plan_link": state.get("index_plan_link"), "appendix_url": state.get("index_appendix_url")}
        for state in committed_queue()["states"]
        if state.get("index_url") == ccdf.INDEX and state.get("name") in ccdf.CODES
    ]
    assert len(rows) == 56 and {r["code"] for r in rows} == set(ccdf.RESOLUTIONS)
    monkeypatch.setattr(ccdf, "fetch_index", lambda: copy.deepcopy(rows))
    monkeypatch.setattr(ccdf, "ca_bundle", lambda: Path("/dev/null"))
    return rows


# --------------------------------------------------------------------------------------
# Row identity: two rows share a jurisdiction, so rows are addressed by target manifest.
# --------------------------------------------------------------------------------------
def test_the_queue_really_does_hold_two_rows_per_jurisdiction_for_us_and_us_in() -> None:
    counts = Counter(state["jurisdiction"] for state in committed_queue()["states"])
    assert counts["us"] == 3
    assert counts["us-in"] == 2


def test_one_row_addresses_each_sibling_row_by_its_target_manifest() -> None:
    states = committed_queue()["states"]
    plan = ccdf.one_row(states, ccdf.plan_row_manifest("in"))
    manual = ccdf.one_row(states, ccdf.IN_MANUAL_ROW_MANIFEST)
    federal = ccdf.one_row(states, ccdf.FEDERAL_ROW_MANIFEST)
    assert ccdf.plan_row_manifest("in") == IN_PLAN_ROW
    assert plan["target_scope"]["document_class"] == "policy"
    assert manual["target_scope"]["document_class"] == "manual"
    assert federal["name"] == "Federal"
    # What keying by jurisdiction does instead: the last row of each jurisdiction wins.
    by_jurisdiction = {state["jurisdiction"]: state for state in states}
    assert by_jurisdiction["us-in"] is manual
    assert by_jurisdiction["us"] is not federal


@pytest.mark.parametrize("target", [IN_PLAN_ROW, IN_MANUAL_ROW, FEDERAL_ROW])
def test_one_row_refuses_an_ambiguous_or_missing_target_manifest(target: str) -> None:
    states = committed_queue()["states"]
    with pytest.raises(SystemExit, match=f"2 queue rows carry {target}"):
        ccdf.one_row([*states, dict(ccdf.one_row(states, target))], target)
    with pytest.raises(SystemExit, match=f"0 queue rows carry {target}"):
        ccdf.one_row([s for s in states if s.get("target_manifest") != target], target)


# --------------------------------------------------------------------------------------
# Defect 1: a narrow refresh of Indiana must reach the plan row, not the policy manual.
# --------------------------------------------------------------------------------------
def test_narrow_refresh_of_indiana_edits_the_plan_row_and_not_the_policy_manual_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    queue_path = queue_root(tmp_path, monkeypatch)
    before = committed_queue()["states"]
    ccdf.refresh_plan_rows(["in"])
    after = yaml.safe_load(queue_path.read_text())["states"]

    manual_before = ccdf.one_row(before, IN_MANUAL_ROW)
    manual_after = ccdf.one_row(after, IN_MANUAL_ROW)
    assert manual_after == manual_before, "the FSSA policy-manual row must not be reachable from --only in"
    assert manual_after["target_scope"]["document_class"] == "manual"

    plan_after = ccdf.one_row(after, IN_PLAN_ROW)
    assert plan_after["queue_status"] == ccdf.RESOLUTIONS["in"]["status"]
    assert plan_after["primary_source_url"] == ccdf.RESOLUTIONS["in"]["url"]
    assert plan_after["target_scope"]["document_class"] == "policy"


def test_narrow_refresh_leaves_every_untargeted_row_byte_identical(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    queue_path = queue_root(tmp_path, monkeypatch)
    codes = ["ak", "as", "az", "in", "md", "mo", "mp", "ny", "pr", "vi"]
    targeted = {ccdf.plan_row_manifest(code) for code in codes}
    before = {state.get("target_manifest") or state["name"]: state
              for state in committed_queue()["states"]}
    ccdf.refresh_plan_rows(codes)
    after = {state.get("target_manifest") or state["name"]: state
             for state in yaml.safe_load(queue_path.read_text())["states"]}
    assert set(before) == set(after)
    for key, row in before.items():
        if key not in targeted:
            assert after[key] == row, f"{key} changed but was not targeted"


def test_narrow_refresh_is_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    queue_path = queue_root(tmp_path, monkeypatch)
    ccdf.refresh_plan_rows(["in", "mo"])
    once = queue_path.read_bytes()
    ccdf.refresh_plan_rows(["in", "mo"])
    assert queue_path.read_bytes() == once


def test_narrow_refresh_refuses_when_two_rows_carry_the_plan_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    queue_path = queue_root(tmp_path, monkeypatch)
    payload = yaml.safe_load(queue_path.read_text())
    payload["states"].append({"jurisdiction": "us-in", "name": "a second Indiana plan row",
                              "queue_status": "needs_review", "target_manifest": IN_PLAN_ROW})
    queue_path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, width=120))
    unchanged = queue_path.read_bytes()
    with pytest.raises(SystemExit, match=f"2 queue rows carry {IN_PLAN_ROW}"):
        ccdf.refresh_plan_rows(["in"])
    assert queue_path.read_bytes() == unchanged


# --------------------------------------------------------------------------------------
# Defect 2: the full rebuild must not drop rows, families or committed scope versions.
# --------------------------------------------------------------------------------------
def test_a_bare_invocation_selects_no_pass_and_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    queue_path = queue_root(tmp_path, monkeypatch)
    stub_index(monkeypatch)
    monkeypatch.setattr(sys, "argv", ["build_ccdf_state_plan_manifests.py"])
    with pytest.raises(SystemExit) as caught:
        ccdf.main()
    assert caught.value.code == 2
    assert queue_path.read_bytes() == QUEUE.read_bytes()


def test_rebuild_keeps_every_additional_families_block(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    queue_path = queue_root(tmp_path, monkeypatch, plans=True)
    stub_index(monkeypatch)
    before = {state["target_manifest"]: state["additional_families"]
              for state in committed_queue()["states"]
              if "additional_families" in state and state.get("target_manifest")}
    assert len(before) == 51, "the appendix, amendment and rate-schedule families are the point of this test"
    assert ccdf.rebuild_all_rows() == 0
    after = {state.get("target_manifest"): state.get("additional_families")
             for state in yaml.safe_load(queue_path.read_text())["states"]}
    for target, families in before.items():
        assert after[target] == families, f"{target} lost its additional_families"


def test_rebuild_keeps_the_scope_version_each_row_already_carries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    queue_path = queue_root(tmp_path, monkeypatch, plans=True)
    stub_index(monkeypatch)
    before = {state.get("target_manifest") or state["name"]: (state.get("target_scope") or {}).get("version")
              for state in committed_queue()["states"]}
    # The committed versions are older than the run date, which is what the rebuild must not overwrite.
    assert ccdf.VERSION not in set(before.values())
    assert ccdf.rebuild_all_rows() == 0
    after = {state.get("target_manifest") or state["name"]: (state.get("target_scope") or {}).get("version")
             for state in yaml.safe_load(queue_path.read_text())["states"]}
    assert after == before


def test_rebuild_keeps_the_rows_the_index_does_not_supply(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    queue_path = queue_root(tmp_path, monkeypatch, plans=True)
    stub_index(monkeypatch)
    before = committed_queue()["states"]
    assert ccdf.rebuild_all_rows() == 0
    after = yaml.safe_load(queue_path.read_text())["states"]
    assert len(after) == len(before)
    assert [state["name"] for state in after if state["jurisdiction"] == "us"] == \
           [state["name"] for state in before if state["jurisdiction"] == "us"]
    for target in (FEDERAL_ROW, IN_MANUAL_ROW):
        assert ccdf.one_row(after, target) == ccdf.one_row(before, target)


def test_rebuild_does_not_restamp_the_manifests_it_did_not_re_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    queue_root(tmp_path, monkeypatch, plans=True)
    stub_index(monkeypatch)
    assert ccdf.rebuild_all_rows() == 0
    rebuilt = sorted((tmp_path / "manifests").glob("us-*-ccdf-state-plan-fy2025-2027.yaml"))
    assert len(rebuilt) == 47
    changed = [path.name for path in rebuilt
               if path.read_bytes() != (REPO_ROOT / "manifests" / path.name).read_bytes()]
    assert changed == [], "a rebuild of the committed resolutions must reproduce the committed manifests"


def test_rebuild_is_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    queue_path = queue_root(tmp_path, monkeypatch, plans=True)
    stub_index(monkeypatch)
    assert ccdf.rebuild_all_rows() == 0
    once = queue_path.read_bytes()
    assert ccdf.rebuild_all_rows() == 0
    assert queue_path.read_bytes() == once


def test_rebuild_refuses_to_write_a_queue_that_lost_a_row_or_a_family() -> None:
    kept = {"jurisdiction": "us", "name": "Federal", "target_manifest": FEDERAL_ROW}
    plan = {"jurisdiction": "us-in", "name": "Indiana", "target_manifest": IN_PLAN_ROW,
            "additional_families": [{"family": "ccdf_state_plan_appendix"}]}
    rebuilt_plan = {"jurisdiction": "us-in", "name": "Indiana", "target_manifest": IN_PLAN_ROW,
                    "additional_families": plan["additional_families"]}
    ccdf.refuse_if_rows_lost([kept, plan], [kept, rebuilt_plan])   # replaced in place: fine

    with pytest.raises(SystemExit, match=r"drop 1 queue rows: us \(manifests/us-ccdf-sources.yaml\)"):
        ccdf.refuse_if_rows_lost([kept, plan], [rebuilt_plan])
    stripped = {key: value for key, value in rebuilt_plan.items() if key != "additional_families"}
    with pytest.raises(SystemExit, match="drop additional_families from 1 rows: us-in"):
        ccdf.refuse_if_rows_lost([kept, plan], [kept, stripped])
