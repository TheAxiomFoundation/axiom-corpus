#!/usr/bin/env python3
"""Build the US RuleSpec release that adds the dated Arizona DES ECE notice."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

BASE_RELEASE = "us-rulespec-2026-09-24-snap-fy2027-cola"
RELEASE = "us-rulespec-2026-10-09-az-des-ece-dated"
ADDITION = {
    "document_class": "manual",
    "jurisdiction": "us-az",
    "version": "2026-10-09-az-des-snap-ece-dated-authority",
}


def build_release(*, release_dir: Path, output_dir: Path | None = None) -> Path:
    """Add the notice scope to the reviewed predecessor without replacing scopes."""
    source = release_dir / f"{BASE_RELEASE}.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    scopes = payload["scopes"]
    if ADDITION in scopes:
        raise ValueError("Arizona DES ECE notice scope already exists in base release")

    final_scopes = sorted(
        [*scopes, ADDITION],
        key=lambda scope: (
            scope["jurisdiction"],
            scope["document_class"],
            scope["version"],
        ),
    )
    identities = {
        (scope["jurisdiction"], scope["document_class"], scope["version"]) for scope in final_scopes
    }
    if len(identities) != len(final_scopes):
        raise ValueError("release selector would contain duplicate scopes")

    payload.update(
        {
            "description": (
                f"Successor to {BASE_RELEASE}. It preserves every prior scope and "
                "adds the Arizona DES Cash and Nutrition Assistance Policy Manual "
                "notice What's Changed on 03/23/2026, which moves the Nutrition "
                "Assistance expanded categorical eligibility gross income limit from "
                "185% to 200% of the federal poverty level for benefit month 03/2026 "
                "onward, required to encode that limit with its effective dates. It is "
                "a publish-only pin release for rulespec-us; do not activate it."
            ),
            "name": RELEASE,
            "scopes": final_scopes,
        }
    )
    output = (output_dir or release_dir) / f"{RELEASE}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-dir", type=Path, default=Path("manifests/releases"))
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    print(build_release(release_dir=args.release_dir, output_dir=args.output_dir))


if __name__ == "__main__":
    main()
