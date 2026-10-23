"""Pin the FY2026 memo without retaining audited defective California scopes."""

from pathlib import Path

from axiom_corpus.corpus.releases import ReleaseManifest

ROOT = Path(__file__).resolve().parents[1]
RELEASES = ROOT / "manifests" / "releases"
BASE = "us-rulespec-2026-08-08-obbb-alien-snap"
SUCCESSOR = "us-rulespec-2026-10-13-snap-fy2026-memo-source-corrected"
MEMO_SCOPE = ("us", "guidance", "2026-09-13-snap-fns-guidance")
DEFECTIVE_RECOVERY = ("us-ca", "statute", "2026-07-13-recovery")
PIT_CORE = (
    "us-ca",
    "statute",
    "2026-07-06-ca-rtc-pit-core-us-ca-sections-rtc-17041-rtc-17043-rtc-17045-rtc-17052-rtc-17054-rtc-17073.5",
)
CHAPTER = (
    "us-ca",
    "statute",
    "2026-09-14-income-tax-chapter-us-ca-sections-4e26e6efabc3f0c7-r2026-09-24-preserve-tables",
)
CALWORKS = (
    "us-ca",
    "statute",
    "2026-06-25-ca-wic-calworks-us-ca-sections-wic-11450-wic-11450.12-wic-11451.5-wic-11452-wic-11452.018",
)
CALWORKS_TABLES = (
    "us-ca",
    "statute",
    "2026-06-25-ca-wic-calworks-us-ca-sections-wic-11450-wic-11450.12-wic-11451.5-wic-11452-wic-11452.018-r2026-09-24-preserve-tables",
)


def test_fy2026_memo_release_makes_only_the_audited_source_swap() -> None:
    base = ReleaseManifest.load(RELEASES / f"{BASE}.json")
    successor = ReleaseManifest.load(RELEASES / f"{SUCCESSOR}.json")

    assert len(base.scope_keys) == 272
    assert len(successor.scope_keys) == 272
    assert set(successor.scope_keys) == (
        set(base.scope_keys) - {DEFECTIVE_RECOVERY, PIT_CORE, CALWORKS}
    ) | {CHAPTER, CALWORKS_TABLES, MEMO_SCOPE}
    assert successor.quality_profile == base.quality_profile


def test_fy2026_memo_scope_has_manifest_and_lock() -> None:
    assert (ROOT / ".axiom/ingest-manifests/us/guidance/2026-09-13-snap-fns-guidance.json").is_file()
    assert (ROOT / ".axiom/corpus-locks/us/guidance/2026-09-13-snap-fns-guidance.json").is_file()
