#!/usr/bin/env python3
"""Build the US RuleSpec release that adds Regulation E and Regulation F for the FS pilot."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path

from axiom_corpus.corpus.release_policy import (
    WITHDRAWN_SCOPES_PATH,
    WithdrawnScope,
    load_withdrawn_scopes,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

BASE_RELEASE = "us-rulespec-2026-10-09-az-des-ece-dated"
RELEASE = "us-rulespec-2026-10-20-fs-pilot-reg-e-f"
ADDITIONS = (
    {
        "document_class": "regulation",
        "jurisdiction": "us",
        "version": "2026-10-19-title-12-part-1005",
    },
    {
        "document_class": "regulation",
        "jurisdiction": "us",
        "version": "2026-10-19-title-12-part-1006",
    },
)
# Withdrawn scopes this release keeps as recorded exceptions (release decision on
# axiom-corpus#911): rulespec-us modules cite paths only these carry until
# rulespec-us#1365 re-points them. Their replacements are not selected, because
# they would duplicate citation paths.
KEPT = (
    ("us-me", "statute", "2026-07-13-recovery"),
    ("us-mi", "statute", "2026-07-13-recovery"),
    ("us-mn", "statute", "2026-07-13-recovery"),
)
DESCRIPTION = (
    f"Successor to {BASE_RELEASE}. It applies manifests/withdrawn-scopes.yaml to the 16 "
    "withdrawn scopes that selector carries (release decisions of 2026-10-03 on "
    "axiom-corpus#757 and 2026-10-11 on #760). 13 leave, and four listed replacement "
    "scopes are selected in their place. The us-me, us-mi and us-mn 2026-07-13-recovery "
    "statute scopes stay as recorded exceptions (axiom-corpus#911), without their five "
    "2026-09-14 replacements, which would duplicate 12 citation paths. They stay until "
    "rulespec-us re-points the modules that cite them (rulespec-us#1365). It adds 12 CFR "
    "part 1005 (Regulation E, Electronic Fund Transfers) and part 1006 (Regulation F, Debt "
    "Collection) from the eCFR as of 2026-10-16, ingested and signed in axiom-corpus#894, "
    "for the financial-services pilot encodes of 12 CFR 1005.6, 1005.11 and 1006.14. It is "
    "a publish-only pin release for rulespec-us; do not activate it."
)

Key = tuple[str, str, str]


def _key(scope: Mapping[str, str]) -> Key:
    return (scope["jurisdiction"], scope["document_class"], scope["version"])


def _scope(key: Key) -> dict[str, str]:
    jurisdiction, document_class, version = key
    return {"document_class": document_class, "jurisdiction": jurisdiction, "version": version}


def select_scopes(
    base: list[Mapping[str, str]],
    withdrawn: Mapping[Key, WithdrawnScope],
    *,
    additions: tuple[Mapping[str, str], ...] = ADDITIONS,
    kept: tuple[Key, ...] = KEPT,
) -> list[dict[str, str]]:
    """The base's scopes with the registry applied, the kept exceptions and the additions.

    A withdrawn scope in ``kept`` stays and none of its replacements are added. Every
    other withdrawn scope leaves, and its ``replace_with`` scopes are selected once.
    Refuses an addition the base already holds, a replacement that is itself
    withdrawn, and a duplicate in the result.
    """
    base_keys = [_key(scope) for scope in base]
    if len(set(base_keys)) != len(base_keys):
        raise ValueError("base release selector has duplicate scopes")
    for addition in additions:
        if _key(addition) in base_keys:
            raise ValueError(f"{'/'.join(_key(addition))} already exists in the base release")
    selected: list[Key] = []
    replacements: list[Key] = []
    for key in base_keys:
        entry = withdrawn.get(key)
        if entry is None or key in kept:
            selected.append(key)
            continue
        for replacement in entry.replace_with:
            if replacement.key in withdrawn:
                raise ValueError(f"replacement {'/'.join(replacement.key)} is itself withdrawn")
            replacements.append(replacement.key)
    for key in replacements:
        if key not in selected:
            selected.append(key)
    selected.extend(_key(addition) for addition in additions)
    if len(set(selected)) != len(selected):
        raise ValueError("release selector would contain duplicate scopes")
    return [_scope(key) for key in sorted(selected)]


def build_release(
    *,
    release_dir: Path,
    output_dir: Path | None = None,
    registry: Path = REPO_ROOT / WITHDRAWN_SCOPES_PATH,
) -> Path:
    """Write the release selector built from the base selector and the registry."""
    source = release_dir / f"{BASE_RELEASE}.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    scopes = select_scopes(payload["scopes"], load_withdrawn_scopes(registry))
    payload.update({"description": DESCRIPTION, "name": RELEASE, "scopes": scopes})
    output = (output_dir or release_dir) / f"{RELEASE}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-dir", type=Path, default=REPO_ROOT / "manifests/releases")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    print(build_release(release_dir=args.release_dir, output_dir=args.output_dir))


if __name__ == "__main__":
    main()
