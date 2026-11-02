"""Keep the dated Arizona ECE authority when adding the ABAWD memo source."""

from pathlib import Path

import yaml

from axiom_corpus.corpus.releases import ReleaseManifest

ROOT = Path(__file__).resolve().parents[1]
RELEASES = ROOT / "manifests" / "releases"
PREDECESSOR = "us-rulespec-2026-10-09-az-des-ece-dated"
SUCCESSOR = "us-rulespec-2026-10-16-snap-abawd-memo-source-corrected"
MEMO_SCOPE = ("us", "guidance", "2026-08-03-snap-obbb-abawd-exceptions-implementation-memo")
ECE_SCOPE = ("us-az", "manual", "2026-10-09-az-des-snap-ece-dated-authority")


def test_abawd_memo_release_preserves_ece_and_replaces_withdrawn_scopes() -> None:
    predecessor = ReleaseManifest.load(RELEASES / f"{PREDECESSOR}.json")
    successor = ReleaseManifest.load(RELEASES / f"{SUCCESSOR}.json")
    policy = yaml.safe_load((ROOT / "manifests/withdrawn-scopes.yaml").read_text())
    withdrawn = {
        tuple(entry["scope"].split("/", 2)): entry
        for entry in policy["scopes"]
    }
    inherited_withdrawn = set(predecessor.scope_keys) & withdrawn.keys()
    replacements = {
        tuple(replacement.split("/", 2))
        for scope in inherited_withdrawn
        for replacement in withdrawn[scope].get("replace_with", [])
    }

    assert len(predecessor.scope_keys) == 274
    assert len(inherited_withdrawn) == 16
    assert len(successor.scope_keys) == 268
    assert ECE_SCOPE in predecessor.scope_keys
    assert ECE_SCOPE in successor.scope_keys
    assert set(successor.scope_keys) == (
        set(predecessor.scope_keys) - inherited_withdrawn
    ) | replacements | {MEMO_SCOPE}
    assert not set(successor.scope_keys) & withdrawn.keys()
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
