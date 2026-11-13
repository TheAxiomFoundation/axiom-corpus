#!/usr/bin/env python3
"""Build the UK RuleSpec pin release that adds the PolicyEngine child-definition scopes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BASE_RELEASE = "uk-rulespec-2026-09-07"
RELEASE = "uk-rulespec-2026-10-25-pe-child-definitions"
ADDITIONS = (
    {
        "document_class": "regulation",
        "jurisdiction": "uk",
        "version": "2026-09-28-uk-pe-child-definitions",
    },
    {
        "document_class": "statute",
        "jurisdiction": "uk",
        "version": "2026-09-28-uk-pe-child-definitions",
    },
)
DESCRIPTION = (
    f"Successor to {BASE_RELEASE}, rulespec-uk's corpus pin. It preserves every prior "
    "scope and adds the two signed, locked scopes of the 2026-09-28 PolicyEngine parity "
    "ingest: the legal definitions of a child, qualifying or young person, couple, lone "
    "parent and claimant in UK statutes (uk/statute/2026-09-28-uk-pe-child-definitions, "
    "10 provisions) and regulations (uk/regulation/2026-09-28-uk-pe-child-definitions, "
    "27 provisions). None of their paths is carried by a pin scope. It is a publish-only "
    "pin release for rulespec-uk; do not activate it."
)


def _key(scope: dict[str, str]) -> tuple[str, str, str]:
    return (scope["jurisdiction"], scope["document_class"], scope["version"])


def build_release(
    *, release_dir: Path = REPO_ROOT / "manifests/releases", output_dir: Path | None = None
) -> Path:
    """Add the two scopes to the pin without replacing any scope."""
    payload = json.loads((release_dir / f"{BASE_RELEASE}.json").read_text(encoding="utf-8"))
    scopes = payload["scopes"]
    present = {_key(scope) for scope in scopes} & {_key(scope) for scope in ADDITIONS}
    if present:
        raise ValueError(f"base release already selects {sorted(present)}")
    final_scopes = sorted([*scopes, *map(dict, ADDITIONS)], key=_key)
    if len({_key(scope) for scope in final_scopes}) != len(final_scopes):
        raise ValueError("release selector would contain duplicate scopes")
    payload.update({"description": DESCRIPTION, "name": RELEASE, "scopes": final_scopes})
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
