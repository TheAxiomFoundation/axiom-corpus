"""The release policy the gate reads: withdrawn scopes and the content baseline.

Invariants, for every input:

- Withdrawn scopes: a release that selects one fails unless it is that exact
  tracked selector (same name and selector digest) listed for the scope.
- Notices never change ``ok``, the error count or the warning count, and a
  report with none has exactly the mapping it had before notices existed.
- The content baseline round-trips through its canonical text, and the text
  does not depend on entry order.
- Differential: validating a scope by fresh scan and validating it against a
  baseline entry made from that scan report the same findings, as errors in
  the first case and as one notice in the second.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

import pytest
from hypothesis import HealthCheck, example, given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.content_quality import (
    CONTENT_CHECK_VERSION,
    FINDING_CODES,
    MAX_BODY_TOKENS,
    ContentFinding,
)
from axiom_corpus.corpus.corpus_locks import LOCK_ROOT
from axiom_corpus.corpus.models import ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.release_policy import (
    ContentBaseline,
    ContentBaselineEntry,
    ReleaseGatePolicy,
    ReleasePolicyError,
    SelectorAllowance,
    WithdrawnScope,
    compare_content_baseline,
    content_baseline_text,
    load_content_baseline,
    load_withdrawn_scopes,
    scan_scope,
    write_content_baseline,
)
from axiom_corpus.corpus.release_quality import validate_release
from axiom_corpus.corpus.releases import ReleaseManifest, ReleaseScope
from axiom_corpus.corpus.supabase import deterministic_provision_id
from axiom_corpus.release.manifest import selector_sha256

SCOPE = ReleaseScope("us-xx", "statute", "2026-07-13-recovery")
OTHER = ReleaseScope("us-xx", "statute", "2026-09-14-chapter")
MENU_PAGE = (
    "<!doctype html><html><body><nav><ul>"
    "<li><a href='/'>Home</a></li><li><a href='/s'>Advanced Search</a></li>"
    "<li><a href='/c'>Contact Us</a></li></ul></nav>"
    "<div><p>Every individual domiciled in this state is a resident.</p></div>"
    "</body></html>"
)
LAW = "Every individual domiciled in this state is a resident."


def _parent(path: str) -> str | None:
    return path.rsplit("/", 1)[0] if path.count("/") > 2 else None


def _write_scope(root: Path, scope: ReleaseScope, rows: list[tuple[str, str | None, str]]) -> None:
    """Write a scope whose rows all cite one retained HTML page; it passes every other check."""
    store = CorpusArtifactStore(root)
    key = scope.key
    source = f"sources/{'/'.join(key)}/official-documents/page.html"
    source_path = root / source
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text(MENU_PAGE, encoding="utf-8")
    digest = hashlib.sha256(source_path.read_bytes()).hexdigest()
    records = [
        ProvisionRecord(
            jurisdiction=key[0],
            document_class=key[1],
            citation_path=path,
            body=body,
            heading=path.rsplit("/", 1)[-1],
            kind=kind,
            version=key[2],
            source_path=source,
            source_as_of="2026-07-14",
            expression_date="2026-07-14",
            id=deterministic_provision_id(path),
            parent_citation_path=_parent(path),
            parent_id=deterministic_provision_id(_parent(path)) if _parent(path) else None,
        )
        for path, body, kind in rows
    ]
    inventory = [
        SourceInventoryItem(citation_path=record.citation_path, source_path=source, sha256=digest)
        for record in records
    ]
    store.write_inventory(store.inventory_path(*key), inventory)
    store.write_provisions(store.provisions_path(*key), records)
    store.write_json(
        store.coverage_path(*key),
        {
            "complete": True,
            "source_count": len(inventory),
            "provision_count": len(records),
            "matched_count": len(records),
            "missing_from_provisions": [],
            "extra_provisions": [],
        },
    )


HOLLOW_ROWS = [
    ("us-xx/statute/17014", None, "document"),
    ("us-xx/statute/17014/block-1", "Home\n\nAdvanced Search\n\nContact Us", "block"),
]
CLEAN_ROWS = [("us-xx/statute/17014", LAW, "section")]


def _release(name: str, *scopes: ReleaseScope) -> ReleaseManifest:
    return ReleaseManifest(name=name, scopes=scopes)


def _withdrawn(*allowances: SelectorAllowance) -> dict:
    entry = WithdrawnScope(
        scope=SCOPE,
        withdrawn_on="2026-09-27",
        listed_on="2026-10-13",
        decision="release decision of 2026-09-27 on axiom-corpus#748",
        reason="Its roots are empty and its blocks are menus.",
        run_note="docs/ingest-runs/2026-09-25-us-ca-statute-recovery-audit.md",
        replace_with=(OTHER,),
        allowances={allowance.name: allowance for allowance in allowances},
    )
    return {SCOPE.key: entry}


def test_a_new_cut_that_selects_a_withdrawn_scope_fails_with_the_remedy(tmp_path: Path) -> None:
    _write_scope(tmp_path, SCOPE, CLEAN_ROWS)
    policy = ReleaseGatePolicy(withdrawn=_withdrawn())
    report = validate_release(tmp_path, _release("new-cut", SCOPE), policy=policy)
    assert (report.ok, report.error_count, report.warning_count) == (False, 1, 0)
    [issue] = report.issues
    assert issue.code == "withdrawn_scope_selected"
    assert "us-xx/statute/2026-09-14-chapter" in issue.message
    assert "docs/ingest-runs/2026-09-25-us-ca-statute-recovery-audit.md" in issue.message
    assert issue.path == "manifests/withdrawn-scopes.yaml"


def test_the_grandfathered_selector_keeps_the_scope_with_a_notice(tmp_path: Path) -> None:
    _write_scope(tmp_path, SCOPE, CLEAN_ROWS)
    release = _release("old-cut", SCOPE)
    policy = ReleaseGatePolicy(
        withdrawn=_withdrawn(SelectorAllowance("old-cut", selector_sha256(release)))
    )
    report = validate_release(tmp_path, release, policy=policy, strict_warnings=True)
    assert (report.ok, report.error_count, report.warning_count) == (True, 0, 0)
    [notice] = report.notices
    assert notice.code == "withdrawn_scope_grandfathered"
    assert "selected it before the gate listed it, and keeps it" in notice.message
    payload = report.to_mapping()
    assert payload["notice_count"] == 1 and payload["issue_count"] == 0
    assert payload["notices"] == [notice.to_mapping()]


def test_an_allowance_does_not_follow_an_edited_selector(tmp_path: Path) -> None:
    _write_scope(tmp_path, SCOPE, CLEAN_ROWS)
    _write_scope(tmp_path, OTHER, [("us-xx/statute/17041", LAW, "section")])
    original = _release("old-cut", SCOPE)
    policy = ReleaseGatePolicy(
        withdrawn=_withdrawn(SelectorAllowance("old-cut", selector_sha256(original)))
    )
    edited = _release("old-cut", SCOPE, OTHER)
    report = validate_release(tmp_path, edited, policy=policy)
    assert [issue.code for issue in report.issues] == ["withdrawn_scope_selected"]


def test_an_exception_names_its_reason(tmp_path: Path) -> None:
    _write_scope(tmp_path, SCOPE, CLEAN_ROWS)
    release = _release("pin-successor", SCOPE)
    policy = ReleaseGatePolicy(
        withdrawn=_withdrawn(
            SelectorAllowance(
                "pin-successor", selector_sha256(release), "strict superset of the pinned cut"
            )
        )
    )
    report = validate_release(tmp_path, release, policy=policy)
    assert report.ok
    assert "strict superset of the pinned cut" in report.notices[0].message


def test_new_content_findings_fail_and_recorded_ones_are_notices(tmp_path: Path) -> None:
    _write_scope(tmp_path, OTHER, HOLLOW_ROWS)
    release = _release("cut", OTHER)
    scanned = validate_release(tmp_path, release, policy=ReleaseGatePolicy())
    assert not scanned.ok
    assert sorted((issue.code, issue.message.split(":", 1)[0]) for issue in scanned.issues) == [
        ("hollow_document_root", "us-xx/statute/17014"),
        ("navigation_body", "us-xx/statute/17014/block-1"),
    ]
    entry = scan_scope(tmp_path, OTHER)
    # The two paths agree: the scan's errors are exactly the recorded findings.
    assert {(issue.code, issue.message.split(":", 1)[0]) for issue in scanned.issues} == {
        (finding.code, finding.path) for finding in entry.findings
    }
    baseline = ContentBaseline(CONTENT_CHECK_VERSION, {OTHER.key: entry})
    recorded = validate_release(
        tmp_path, release, policy=ReleaseGatePolicy(content_baseline=baseline), strict_warnings=True
    )
    assert (recorded.ok, recorded.error_count, recorded.warning_count) == (True, 0, 0)
    [notice] = recorded.notices
    assert notice.code == "baselined_content_findings"
    assert "1 hollow_document_root, 1 navigation_body" in notice.message


def test_a_new_scope_with_text_after_the_navigation_sample_passes_release_validation(
    tmp_path: Path,
) -> None:
    citation = "us-xx/statute/17014"
    numbers = [str(number) for number in range(1, MAX_BODY_TOKENS + 1)]
    body = " ".join(numbers) + " Tax liability."
    _write_scope(
        tmp_path,
        OTHER,
        [(citation, None, "document"), (citation + "/block-1", body, "block")],
    )
    # The source contains the same table and text, and the inventory pins it.
    source = tmp_path / f"sources/{'/'.join(OTHER.key)}/official-documents/page.html"
    source.write_text(
        "<html><body><table>"
        + "".join(f"<tr><td>{number}</td></tr>" for number in numbers)
        + "</table><p>Tax liability.</p></body></html>",
        encoding="utf-8",
    )
    store = CorpusArtifactStore(tmp_path)
    inventory = store.inventory_path(*OTHER.key)
    payload = json.loads(inventory.read_text(encoding="utf-8"))
    for item in payload["items"]:
        item["sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    store.write_json(inventory, payload)
    report = validate_release(
        tmp_path, _release("numeric-tail", OTHER), policy=ReleaseGatePolicy.empty()
    )
    assert (report.ok, report.error_count, report.warning_count) == (True, 0, 0)
    assert report.issues == ()
    assert report.notices == ()


def test_a_baseline_entry_for_other_bytes_is_checked_again(tmp_path: Path) -> None:
    _write_scope(tmp_path, OTHER, HOLLOW_ROWS)
    stale = ContentBaselineEntry(OTHER, "0" * 64, "1" * 64, ())
    policy = ReleaseGatePolicy(
        content_baseline=ContentBaseline(CONTENT_CHECK_VERSION, {OTHER.key: stale})
    )
    report = validate_release(tmp_path, _release("cut", OTHER), policy=policy)
    codes = sorted(issue.code for issue in report.issues)
    assert codes == ["content_baseline_mismatch", "hollow_document_root", "navigation_body"]


def test_a_baseline_from_other_check_rules_is_ignored(tmp_path: Path) -> None:
    _write_scope(tmp_path, OTHER, HOLLOW_ROWS)
    entry = scan_scope(tmp_path, OTHER)
    policy = ReleaseGatePolicy(
        content_baseline=ContentBaseline("content-check-v0", {OTHER.key: entry})
    )
    report = validate_release(tmp_path, _release("cut", OTHER), policy=policy)
    assert report.error_count == 2
    # One warning says why every finding is new.
    assert [issue.code for issue in report.issues if issue.severity == "warning"] == [
        "content_baseline_stale"
    ]


def test_an_unreadable_artifact_is_not_called_a_baseline_mismatch(tmp_path: Path) -> None:
    _write_scope(tmp_path, OTHER, HOLLOW_ROWS)
    entry = scan_scope(tmp_path, OTHER)
    (tmp_path / "inventory/us-xx/statute/2026-09-14-chapter.json").unlink()
    policy = ReleaseGatePolicy(
        content_baseline=ContentBaseline(CONTENT_CHECK_VERSION, {OTHER.key: entry})
    )
    report = validate_release(tmp_path, _release("cut", OTHER), policy=policy)
    codes = {issue.code for issue in report.issues}
    assert "missing_inventory" in codes
    assert "content_baseline_mismatch" not in codes


def test_a_withdrawn_scope_is_not_content_checked(tmp_path: Path) -> None:
    _write_scope(tmp_path, SCOPE, HOLLOW_ROWS)
    report = validate_release(
        tmp_path, _release("cut", SCOPE), policy=ReleaseGatePolicy(withdrawn=_withdrawn())
    )
    assert [issue.code for issue in report.issues] == ["withdrawn_scope_selected"]


def test_a_clean_report_has_no_notice_keys(tmp_path: Path) -> None:
    _write_scope(tmp_path, OTHER, CLEAN_ROWS)
    payload = validate_release(
        tmp_path, _release("cut", OTHER), policy=ReleaseGatePolicy()
    ).to_mapping()
    assert "notices" not in payload and "notice_count" not in payload
    assert payload["ok"] is True


def test_a_corpus_outside_any_checkout_gets_the_empty_policy(tmp_path: Path) -> None:
    assert ReleaseGatePolicy.for_corpus(tmp_path) == ReleaseGatePolicy.empty()


def _registry_text(**overrides: object) -> str:
    entry = {
        "scope": "us-xx/statute/2026-07-13-recovery",
        "withdrawn_on": "2026-09-27",
        "listed_on": "2026-10-13",
        "decision": "release decision of 2026-09-27 on axiom-corpus#748",
        "run_note": "docs/ingest-runs/x.md",
        "reason": "Empty roots and menus.",
        "replace_with": ["us-xx/statute/2026-09-14-chapter"],
        "carried_by": [],
        "grandfathered_selectors": ["a-cut"],
        "exceptions": [],
    }
    entry.update(overrides)
    document = {
        "schema_version": "axiom-corpus/withdrawn-scopes/v1",
        "selector_digests": {"a-cut": "a" * 64},
        "scopes": [entry],
    }
    return json.dumps(document)  # JSON is YAML


def test_the_registry_parses(tmp_path: Path) -> None:
    path = tmp_path / "w.yaml"
    path.write_text(_registry_text())
    [entry] = load_withdrawn_scopes(path).values()
    assert entry.scope == SCOPE
    assert entry.allowances["a-cut"] == SelectorAllowance("a-cut", "a" * 64)
    assert entry.replace_with == (OTHER,)


def test_registry_dates_are_read_as_dates(tmp_path: Path) -> None:
    """Dates compare as dates: a basic-format date is normalized, not compared as text.

    As text "20261012" sorts after "2026-10-13"; as a date it is the day before.
    """
    path = tmp_path / "w.yaml"
    path.write_text(_registry_text(withdrawn_on="20261012"))
    [entry] = load_withdrawn_scopes(path).values()
    assert (entry.withdrawn_on, entry.listed_on) == ("2026-10-12", "2026-10-13")


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"grandfathered_selectors": ["b-cut"]}, "no selector_digests entry"),
        ({"grandfathered_selectors": ["a-cut", "a-cut"]}, "sorted and free of duplicates"),
        ({"withdrawn_on": "27 September"}, "ISO date"),
        ({"withdrawn_on": "20261014"}, "listed_on precedes withdrawn_on"),
        ({"listed_on": "2026-09-01"}, "listed_on precedes withdrawn_on"),
        ({"replace_with": ["us-xx/statute/2026-07-13-recovery"]}, "itself withdrawn"),
        ({"surprise": 1}, "unsupported fields"),
        ({"exceptions": [{"selector": "a-cut"}]}, "must have exactly"),
        ({"grandfathered_selectors": [], "exceptions": []}, "unused selectors"),
        ({"scope": "us-xx/statute"}, "jurisdiction/document_class/version"),
    ],
)
def test_the_registry_rejects_malformed_entries(
    tmp_path: Path, overrides: dict, message: str
) -> None:
    path = tmp_path / "w.yaml"
    path.write_text(_registry_text(**overrides))
    with pytest.raises(ReleasePolicyError, match=message):
        load_withdrawn_scopes(path)


_DIGEST = st.text(alphabet="0123456789abcdef", min_size=64, max_size=64)
_FINDING = st.builds(
    ContentFinding,
    st.sampled_from(FINDING_CODES),
    st.text(alphabet="abcdefghij/-.", min_size=1, max_size=20),
)
_SCOPE = st.builds(
    ReleaseScope,
    st.sampled_from(["us", "us-ca", "us-ny", "uk"]),
    st.sampled_from(["statute", "regulation", "manual"]),
    st.text(alphabet="0123456789-abcdef", min_size=1, max_size=12).filter(
        lambda value: value[0].isalnum()
    ),
)


@settings(max_examples=100, deadline=None)
@example(scopes=[SCOPE, SCOPE])
@example(scopes=[OTHER, SCOPE])
@given(scopes=st.lists(_SCOPE, min_size=2, max_size=6))
def test_registry_scope_entries_must_be_sorted_and_unique(scopes: list[ReleaseScope]) -> None:
    """A later entry cannot replace an earlier entry's withdrawal and allowances."""
    document = json.loads(_registry_text())
    template = document["scopes"][0]
    document["scopes"] = [
        {**template, "scope": "/".join(scope.key), "replace_with": []} for scope in scopes
    ]
    keys = [scope.key for scope in scopes]
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "withdrawn.yaml"
        path.write_text(json.dumps(document))
        if keys == sorted(set(keys)):
            assert list(load_withdrawn_scopes(path)) == keys
        else:
            with pytest.raises(ReleasePolicyError, match="free of duplicates"):
                load_withdrawn_scopes(path)


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    entries=st.lists(
        st.builds(
            ContentBaselineEntry,
            _SCOPE,
            _DIGEST,
            _DIGEST,
            st.lists(_FINDING, max_size=4).map(lambda f: tuple(sorted(set(f)))),
        ),
        max_size=6,
        unique_by=lambda entry: entry.scope.key,
    ),
    order=st.randoms(use_true_random=False),
)
def test_the_baseline_round_trips_in_any_order(entries, order) -> None:  # type: ignore[no-untyped-def]
    shuffled = list(entries)
    order.shuffle(shuffled)
    text = content_baseline_text(entries)
    assert text == content_baseline_text(shuffled)
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "baseline.json"
        write_content_baseline(path, shuffled)
        loaded = load_content_baseline(path)
    assert loaded.check_version == CONTENT_CHECK_VERSION
    assert loaded.entries == {entry.scope.key: entry for entry in entries}


def test_comparison_names_every_kind_of_difference(tmp_path: Path) -> None:
    _write_scope(tmp_path, OTHER, HOLLOW_ROWS)
    fresh = scan_scope(tmp_path, OTHER)
    gone = ReleaseScope("us-xx", "statute", "gone")
    stale = ContentBaseline(
        CONTENT_CHECK_VERSION,
        {
            OTHER.key: ContentBaselineEntry(
                OTHER, fresh.provisions_sha256, fresh.inventory_sha256, ()
            ),
            gone.key: ContentBaselineEntry(gone, "0" * 64, "0" * 64, ()),
        },
    )
    problems = {
        difference.scope: difference.problem
        for difference in compare_content_baseline(
            stale, {OTHER.key: fresh}, locked_scopes=[OTHER.key]
        )
    }
    assert problems == {
        "us-xx/statute/gone": "listed but not locked",
        "us-xx/statute/2026-09-14-chapter": "findings differ: 2 new, 0 no longer found",
    }
    unlisted = compare_content_baseline(
        ContentBaseline(CONTENT_CHECK_VERSION, {}), {OTHER.key: fresh}, locked_scopes=[OTHER.key]
    )
    assert [d.problem for d in unlisted] == [
        "unrecorded content findings: 1 hollow_document_root, 1 navigation_body"
    ]
    exact = ContentBaseline(CONTENT_CHECK_VERSION, {OTHER.key: fresh})
    assert compare_content_baseline(exact, {OTHER.key: fresh}, locked_scopes=[OTHER.key]) == []


def test_a_required_policy_must_have_both_files(tmp_path: Path) -> None:
    assert ReleaseGatePolicy.load(tmp_path) == ReleaseGatePolicy(source=str(tmp_path))
    with pytest.raises(ReleasePolicyError, match="release policy files are missing"):
        ReleaseGatePolicy.load(tmp_path, required=True)


def test_a_checkout_with_corpus_locks_requires_its_policy(tmp_path: Path) -> None:
    """Validation and publication fail closed in a locked checkout without the policy files."""
    repo = tmp_path / "checkout"
    (repo / "src" / "axiom_corpus").mkdir(parents=True)
    (repo / "data" / "corpus").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    assert ReleaseGatePolicy.for_checkout(repo) == ReleaseGatePolicy(source=str(repo))
    assert ReleaseGatePolicy.for_corpus(repo / "data" / "corpus").source == str(repo.resolve())
    (repo / LOCK_ROOT).mkdir(parents=True)
    with pytest.raises(ReleasePolicyError, match="release policy files are missing"):
        ReleaseGatePolicy.for_checkout(repo)
    with pytest.raises(ReleasePolicyError, match="release policy files are missing"):
        ReleaseGatePolicy.for_corpus(repo / "data" / "corpus")
