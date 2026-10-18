"""Keep the dated Arizona ECE authority when adding the ABAWD memo source."""

from pathlib import Path

from axiom_corpus.corpus.releases import ReleaseManifest

ROOT = Path(__file__).resolve().parents[1]
RELEASES = ROOT / "manifests" / "releases"
PREDECESSOR = "us-rulespec-2026-10-09-az-des-ece-dated"
SUCCESSOR = "us-rulespec-2026-10-16-snap-abawd-memo-source-corrected"
MEMO_SCOPE = ("us", "guidance", "2026-08-03-snap-obbb-abawd-exceptions-implementation-memo")
ECE_SCOPE = ("us-az", "manual", "2026-10-09-az-des-snap-ece-dated-authority")


def test_abawd_memo_release_preserves_the_dated_ece_predecessor() -> None:
    predecessor = ReleaseManifest.load(RELEASES / f"{PREDECESSOR}.json")
    successor = ReleaseManifest.load(RELEASES / f"{SUCCESSOR}.json")

    assert len(predecessor.scope_keys) == 274
    assert len(successor.scope_keys) == 275
    assert ECE_SCOPE in predecessor.scope_keys
    assert set(successor.scope_keys) == set(predecessor.scope_keys) | {MEMO_SCOPE}
    assert successor.quality_profile == predecessor.quality_profile


def test_abawd_memo_scope_is_signed_and_locked() -> None:
    assert (
        ROOT
        / ".axiom/ingest-manifests/us/guidance/2026-08-03-snap-obbb-abawd-exceptions-implementation-memo.json"
    ).is_file()
    assert (
        ROOT
        / ".axiom/corpus-locks/us/guidance/2026-08-03-snap-obbb-abawd-exceptions-implementation-memo.json"
    ).is_file()
