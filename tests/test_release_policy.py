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
- A row on the reviewed-empty list is never a ``hollow_document_root`` finding,
  by fresh scan or by baseline alike, and both paths report the same
  reviewed-empty notice; a listed row that is not a hollow root fails the
  baseline comparison.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.content_quality import (
    CONTENT_CHECK_VERSION,
    FINDING_CODES,
    ContentFinding,
)
from axiom_corpus.corpus.corpus_locks import LOCK_ROOT
from axiom_corpus.corpus.models import ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.release_policy import (
    REVIEWED_EMPTY_PATH,
    ContentBaseline,
    ContentBaselineEntry,
    ReleaseGatePolicy,
    ReleasePolicyError,
    ReviewedEmptyNode,
    ReviewedEmptyScope,
    SelectorAllowance,
    WithdrawnScope,
    compare_content_baseline,
    content_baseline_text,
    load_content_baseline,
    load_reviewed_empty,
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


def _reviewed(scope: ReleaseScope, *paths: str) -> dict:
    return {
        scope.key: ReviewedEmptyScope(
            scope=scope,
            run_note="docs/ingest-runs/x.md",
            nodes=tuple(
                ReviewedEmptyNode(path, "table_of_contents", "Contents.") for path in paths
            ),
        )
    }


def test_a_reviewed_empty_root_is_a_notice_by_scan_and_by_baseline(tmp_path: Path) -> None:
    _write_scope(tmp_path, OTHER, HOLLOW_ROWS)
    release = _release("cut", OTHER)
    policy = ReleaseGatePolicy(reviewed_empty=_reviewed(OTHER, "us-xx/statute/17014"))
    scanned = validate_release(tmp_path, release, policy=policy)
    # The menu block is still navigation; the root it leaves hollow was reviewed.
    assert [(issue.code, issue.message.split(":", 1)[0]) for issue in scanned.issues] == [
        ("navigation_body", "us-xx/statute/17014/block-1")
    ]
    [scan_notice] = scanned.notices
    assert scan_notice.code == "reviewed_empty_document_roots"
    assert scan_notice.path == str(REVIEWED_EMPTY_PATH)
    assert "has 1 document rows that review found correctly empty" in scan_notice.message
    entry = scan_scope(tmp_path, OTHER, reviewed_empty=policy.reviewed_empty_paths(OTHER))
    assert [(f.code, f.path) for f in entry.findings] == [
        ("navigation_body", "us-xx/statute/17014/block-1")
    ]
    assert entry.reviewed_empty == ("us-xx/statute/17014",)
    recorded = validate_release(
        tmp_path,
        release,
        policy=ReleaseGatePolicy(
            content_baseline=ContentBaseline(CONTENT_CHECK_VERSION, {OTHER.key: entry}),
            reviewed_empty=policy.reviewed_empty,
        ),
        strict_warnings=True,
    )
    assert (recorded.ok, recorded.error_count, recorded.warning_count) == (True, 0, 0)
    assert [notice.code for notice in recorded.notices] == [
        "baselined_content_findings",
        "reviewed_empty_document_roots",
    ]
    assert recorded.notices[1].message == scan_notice.message
    # Without the list the root is a finding again.
    plain = validate_release(tmp_path, release, policy=ReleaseGatePolicy())
    assert "hollow_document_root" in {issue.code for issue in plain.issues}


def test_a_reviewed_row_with_text_below_it_exempts_nothing(tmp_path: Path) -> None:
    _write_scope(tmp_path, OTHER, [*HOLLOW_ROWS, ("us-xx/statute/17014/block-2", LAW, "block")])
    policy = ReleaseGatePolicy(reviewed_empty=_reviewed(OTHER, "us-xx/statute/17014"))
    report = validate_release(tmp_path, _release("cut", OTHER), policy=policy)
    assert [issue.code for issue in report.issues] == ["navigation_body"]
    assert report.notices == ()


def test_comparison_names_stale_and_unlocked_reviewed_rows(tmp_path: Path) -> None:
    _write_scope(tmp_path, OTHER, HOLLOW_ROWS)
    gone = ReleaseScope("us-xx", "statute", "gone")
    reviewed = {
        **_reviewed(OTHER, "us-xx/statute/17014", "us-xx/statute/17014/block-1"),
        **_reviewed(gone, "us-xx/statute/1"),
    }
    fresh = scan_scope(tmp_path, OTHER, reviewed_empty=reviewed[OTHER.key].paths)
    baseline = ContentBaseline(CONTENT_CHECK_VERSION, {OTHER.key: fresh})
    problems = {
        difference.scope: difference.problem
        for difference in compare_content_baseline(
            baseline, {OTHER.key: fresh}, locked_scopes=[OTHER.key], reviewed_empty=reviewed
        )
    }
    assert problems == {
        "us-xx/statute/gone": f"listed in {REVIEWED_EMPTY_PATH} but not locked",
        "us-xx/statute/2026-09-14-chapter": (
            f"1 rows in {REVIEWED_EMPTY_PATH} are not hollow document roots: "
            "us-xx/statute/17014/block-1"
        ),
    }
    exact = _reviewed(OTHER, "us-xx/statute/17014")
    fresh = scan_scope(tmp_path, OTHER, reviewed_empty=exact[OTHER.key].paths)
    baseline = ContentBaseline(CONTENT_CHECK_VERSION, {OTHER.key: fresh})
    assert (
        compare_content_baseline(
            baseline, {OTHER.key: fresh}, locked_scopes=[OTHER.key], reviewed_empty=exact
        )
        == []
    )
    # A baseline made before the row was reviewed still records it: the list
    # and the baseline must change together.
    before = ContentBaseline(CONTENT_CHECK_VERSION, {OTHER.key: scan_scope(tmp_path, OTHER)})
    assert [
        difference.problem
        for difference in compare_content_baseline(
            before, {OTHER.key: fresh}, locked_scopes=[OTHER.key], reviewed_empty=exact
        )
    ] == ["findings differ: 0 new, 1 no longer found"]


def _reviewed_text(**overrides: object) -> str:
    node = {
        "path": "us-xx/statute/toc",
        "reason": "table_of_contents",
        "note": "The code's table of contents.",
    }
    node.update(overrides.pop("node", {}))  # type: ignore[arg-type]
    entry: dict[str, object] = {
        "scope": "us-xx/statute/2026-09-14-chapter",
        "run_note": "docs/ingest-runs/x.md",
        "nodes": [node],
    }
    entry.update(overrides)
    return json.dumps({"schema_version": "axiom-corpus/reviewed-empty-nodes/v1", "scopes": [entry]})


def test_the_reviewed_empty_list_parses(tmp_path: Path) -> None:
    path = tmp_path / "reviewed.yaml"
    path.write_text(_reviewed_text(node={"note": "The code's\n   table of contents."}))
    loaded = load_reviewed_empty(path)
    assert loaded == {
        OTHER.key: ReviewedEmptyScope(
            OTHER,
            "docs/ingest-runs/x.md",
            (
                ReviewedEmptyNode(
                    "us-xx/statute/toc", "table_of_contents", "The code's table of contents."
                ),
            ),
        )
    }
    assert ReleaseGatePolicy(reviewed_empty=loaded).reviewed_empty_paths(OTHER) == {
        "us-xx/statute/toc"
    }
    assert ReleaseGatePolicy(reviewed_empty=loaded).reviewed_empty_paths(SCOPE) == frozenset()


@pytest.mark.parametrize(
    ("text", "message"),
    [
        (_reviewed_text(node={"reason": "boring"}), "reason must be one of"),
        (_reviewed_text(node={"path": "us-yy/statute/toc"}), "citation path under us-xx/statute/"),
        (_reviewed_text(node={"note": " "}), "note must be a non-empty string"),
        (_reviewed_text(node={"extra": 1}), "fields must be"),
        (_reviewed_text(nodes=[]), "nodes must be a non-empty list"),
        (_reviewed_text(run_note=None), "run_note must be a non-empty string"),
        (_reviewed_text(scope="us-xx/statute"), "scope must be"),
        (
            _reviewed_text(
                nodes=[
                    {"path": "us-xx/statute/b", "reason": "index", "note": "x"},
                    {"path": "us-xx/statute/a", "reason": "index", "note": "x"},
                ]
            ),
            "sorted and free of duplicates",
        ),
        (
            _reviewed_text(
                nodes=[
                    {"path": "us-xx/statute/a", "reason": "index", "note": "x"},
                    {"path": "us-xx/statute/a", "reason": "reserved", "note": "y"},
                ]
            ),
            "sorted and free of duplicates",
        ),
        (
            _reviewed_text().replace("reviewed-empty-nodes/v1", "reviewed-empty-nodes/v0"),
            "schema_version",
        ),
        (json.dumps({"schema_version": "axiom-corpus/reviewed-empty-nodes/v1"}), "fields must be"),
    ],
)
def test_the_reviewed_empty_list_rejects_malformed_entries(
    tmp_path: Path, text: str, message: str
) -> None:
    path = tmp_path / "reviewed.yaml"
    path.write_text(text)
    with pytest.raises(ReleasePolicyError, match=message):
        load_reviewed_empty(path)


def test_the_reviewed_empty_list_keeps_scopes_sorted_and_unique(tmp_path: Path) -> None:
    document = json.loads(_reviewed_text())
    entry = document["scopes"][0]
    earlier = {**entry, "scope": "us-xx/statute/2026-07-13-recovery"}
    path = tmp_path / "reviewed.yaml"
    for scopes in ([entry, earlier], [entry, entry]):
        path.write_text(json.dumps({**document, "scopes": scopes}))
        with pytest.raises(ReleasePolicyError, match="sorted by jurisdiction"):
            load_reviewed_empty(path)
    path.write_text(json.dumps({**document, "scopes": [earlier, entry]}))
    assert list(load_reviewed_empty(path)) == [SCOPE.key, OTHER.key]


def test_the_reviewed_empty_list_is_read_but_never_required(tmp_path: Path) -> None:
    (tmp_path / "manifests").mkdir()
    write_content_baseline(tmp_path / "manifests/release-content-baseline.json", [])
    (tmp_path / "manifests/withdrawn-scopes.yaml").write_text(_registry_text())
    assert ReleaseGatePolicy.load(tmp_path, required=True).reviewed_empty == {}
    (tmp_path / REVIEWED_EMPTY_PATH).write_text(_reviewed_text())
    assert ReleaseGatePolicy.load(tmp_path, required=True).reviewed_empty_paths(OTHER) == {
        "us-xx/statute/toc"
    }
