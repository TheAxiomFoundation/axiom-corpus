"""Keep the FY2026 SNAP memo release additive to the RuleSpec corpus pin."""

from pathlib import Path

from axiom_corpus.corpus.releases import ReleaseManifest

ROOT = Path(__file__).resolve().parents[1]
RELEASES = ROOT / "manifests" / "releases"
BASE = "us-rulespec-2026-08-08-obbb-alien-snap"
ADDITIVE = "us-rulespec-2026-10-13-snap-fy2026-memo-additive"
MEMO_SCOPE = ("us", "guidance", "2026-09-13-snap-fns-guidance")


def test_fy2026_memo_release_preserves_every_pinned_scope() -> None:
    base = ReleaseManifest.load(RELEASES / f"{BASE}.json")
    additive = ReleaseManifest.load(RELEASES / f"{ADDITIVE}.json")

    assert len(base.scope_keys) == 272
    assert len(additive.scope_keys) == 273
    assert set(additive.scope_keys) == set(base.scope_keys) | {MEMO_SCOPE}
    assert additive.quality_profile == base.quality_profile


def test_fy2026_memo_scope_has_manifest_and_lock() -> None:
    assert (ROOT / ".axiom/ingest-manifests/us/guidance/2026-09-13-snap-fns-guidance.json").is_file()
    assert (ROOT / ".axiom/corpus-locks/us/guidance/2026-09-13-snap-fns-guidance.json").is_file()
