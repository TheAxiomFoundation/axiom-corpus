#!/usr/bin/env python3
"""Build the publish-only NZ RuleSpec pin with amendment routing metadata."""

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
BASE_RELEASE = "nz-rulespec-2026-10-20"
RELEASE = "nz-rulespec-2026-10-23-amendment-markers"
OLD_SCOPE = ("nz", "statute", "2026-10-20-rulespec-nz-pco")
NEW_SCOPE = ("nz", "statute", "2026-10-23-rulespec-nz-pco")
DESCRIPTION = (
    f"Successor to {BASE_RELEASE}, replacing only nz/statute/{OLD_SCOPE[2]} with "
    f"nz/statute/{NEW_SCOPE[2]}. The retained official XML and all provision bodies of "
    "the Social Security (Jobseeker Support and Accommodation Supplement) Amendment "
    "Act 2026 are unchanged; the successor adds reviewed amendment targets and "
    "commencement metadata derived from the XML Parts for encoding dated principal-Act "
    "rules. Every other scope is unchanged. It is a publish-only pin release for "
    "rulespec-nz; do not activate it."
)

Key = tuple[str, str, str]


def _key(scope: Mapping[str, str]) -> Key:
    return (scope["jurisdiction"], scope["document_class"], scope["version"])


def select_scopes(
    base: list[Mapping[str, str]],
    withdrawn: Mapping[Key, WithdrawnScope],
) -> list[dict[str, str]]:
    """Replace exactly the predecessor scope, preserving order and all other values.

    Fail rather than alter this pin's scope delta if a selected scope is withdrawn.
    A later policy change then requires a separately reviewed release decision.
    """
    keys = [_key(scope) for scope in base]
    if len(set(keys)) != len(keys):
        raise ValueError("base release selector has duplicate scopes")
    if OLD_SCOPE not in keys:
        raise ValueError(f"base release must select {'/'.join(OLD_SCOPE)}")
    if NEW_SCOPE in keys:
        raise ValueError(f"{'/'.join(NEW_SCOPE)} already exists in the base release")
    selected = [
        {**scope, "version": NEW_SCOPE[2]} if _key(scope) == OLD_SCOPE else dict(scope)
        for scope in base
    ]
    for scope in selected:
        key = _key(scope)
        if key in withdrawn:
            raise ValueError(f"new pin release selects withdrawn scope {'/'.join(key)}")
    return selected


def build_release(
    *,
    release_dir: Path,
    output_dir: Path | None = None,
    registry: Path = REPO_ROOT / WITHDRAWN_SCOPES_PATH,
) -> Path:
    """Write the exact one-scope successor; do not publish or activate it."""
    source = release_dir / f"{BASE_RELEASE}.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    scopes = select_scopes(payload["scopes"], load_withdrawn_scopes(registry))
    payload.update({"description": DESCRIPTION, "name": RELEASE, "scopes": scopes})
    output = (output_dir or release_dir) / f"{RELEASE}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-dir", type=Path, default=REPO_ROOT / "manifests/releases")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    print(build_release(release_dir=args.release_dir, output_dir=args.output_dir))


if __name__ == "__main__":
    main()
