#!/usr/bin/env python3
"""Build the US RuleSpec release containing the Title 52 election statutes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

BASE_RELEASE = "us-rulespec-2026-09-24-snap-fy2027-cola"
RELEASE = "us-rulespec-2026-09-29-election-uocava-nvra"
ADDITION = {
    "document_class": "statute",
    "jurisdiction": "us",
    "version": "2026-09-29-election-statute-uocava-nvra-title-52",
}


def build_release(*, release_dir: Path, output_dir: Path | None = None) -> Path:
    """Add the Title 52 scope to the reviewed predecessor without replacing scopes."""
    source = release_dir / f"{BASE_RELEASE}.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    scopes = payload["scopes"]
    if ADDITION in scopes:
        raise ValueError("Title 52 election statute scope already exists in base release")

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
                "adds 52 U.S.C. 20302, 20310 and 20507 (OLRC release point 119-111), "
                "required to encode the UOCAVA 45-day absentee ballot transmission "
                "rule, the UOCAVA definitions of absent uniformed services and "
                "overseas voters, and the NVRA voter registration deadline."
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
