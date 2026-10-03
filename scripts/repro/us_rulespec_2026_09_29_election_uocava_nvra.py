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
# docs/ingest-runs/2026-09-25-us-ca-statute-recovery-audit.md, "How later cuts
# supersede the scope": the next cut in this line drops the us-ca recovery and
# PIT core scopes and selects the chapter scope that carries all of their R&TC
# sections (#742, which would supply successors, is not merged).
US_CA_REMOVALS = (
    {
        "document_class": "statute",
        "jurisdiction": "us-ca",
        "version": "2026-07-13-recovery",
    },
    {
        "document_class": "statute",
        "jurisdiction": "us-ca",
        "version": (
            "2026-07-06-ca-rtc-pit-core-us-ca-sections-rtc-17041-rtc-17043-rtc-17045-"
            "rtc-17052-rtc-17054-rtc-17073.5"
        ),
    },
)
US_CA_ADDITION = {
    "document_class": "statute",
    "jurisdiction": "us-ca",
    "version": "2026-09-14-income-tax-chapter-us-ca-sections-4e26e6efabc3f0c7",
}


def build_release(*, release_dir: Path, output_dir: Path | None = None) -> Path:
    """Add the Title 52 scope to the reviewed predecessor and apply the us-ca swap."""
    source = release_dir / f"{BASE_RELEASE}.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    scopes = payload["scopes"]
    for scope in (ADDITION, US_CA_ADDITION):
        if scope in scopes:
            raise ValueError(f"scope already exists in base release: {scope}")
    for scope in US_CA_REMOVALS:
        if scope not in scopes:
            raise ValueError(f"scope to replace is missing from base release: {scope}")

    final_scopes = sorted(
        [
            *(scope for scope in scopes if scope not in US_CA_REMOVALS),
            ADDITION,
            US_CA_ADDITION,
        ],
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
                f"Successor to {BASE_RELEASE}. It adds 52 U.S.C. 20302, 20310 and "
                "20507 (OLRC release point 119-111), required to encode the UOCAVA "
                "45-day absentee ballot transmission rule, the UOCAVA definitions of "
                "absent uniformed services and overseas voters, and the NVRA voter "
                "registration deadline. It keeps every other prior scope except that, "
                "as the 2026-09-25 us-ca statute recovery audit requires of the next "
                "cut in this line, the California 2026-07-13 recovery and PIT core "
                "statute scopes are replaced by the 2026-09-14 income tax chapter "
                "scope, which carries all of their Revenue and Taxation Code sections."
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
