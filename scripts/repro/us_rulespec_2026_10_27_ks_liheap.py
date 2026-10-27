#!/usr/bin/env python3
"""Build the US RuleSpec pin release with the Kansas LIHEAP sources on the current pin line."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BASE_RELEASE = "us-rulespec-2026-10-25-mt-separate-filing"
RELEASE = "us-rulespec-2026-10-27-ks-liheap"
# The seven scopes us-rulespec-2026-10-23-ks-liheap added to its own, older base.
ADDITIONS = (
    {
        "document_class": "guidance",
        "jurisdiction": "us",
        "version": "2026-10-02-hhs-poverty-2024-2025",
    },
    {
        "document_class": "statute",
        "jurisdiction": "us",
        "version": "2026-09-13-liheap-statute-chapter-94-title-42",
    },
    {
        "document_class": "manual",
        "jurisdiction": "us-ks",
        "version": "2026-10-02-ks-lieap-historical",
    },
    {
        "document_class": "policy",
        "jurisdiction": "us-ks",
        "version": "2026-09-10",
    },
    {
        "document_class": "policy",
        "jurisdiction": "us-ks",
        "version": "2026-09-14-liheap-benefit-matrix",
    },
    {
        "document_class": "policy",
        "jurisdiction": "us-ks",
        "version": "2026-10-02-ks-liheap-matrix-fy2025",
    },
    {
        "document_class": "policy",
        "jurisdiction": "us-ks",
        "version": "2026-10-02-ks-liheap-plan-fy2025",
    },
)
DESCRIPTION = (
    f"Successor to {BASE_RELEASE} on rulespec-us's corpus pin line. It keeps all 276 scopes "
    "of that pin and adds the seven signed, locked Kansas LIHEAP scopes of "
    "us-rulespec-2026-10-23-ks-liheap: the dated KEESM LIEAP manual pages "
    "(us-ks/manual/2026-10-02-ks-lieap-historical), the FY2025 Kansas LIHEAP plan and benefit "
    "matrix (us-ks/policy/2026-10-02-ks-liheap-plan-fy2025, "
    "us-ks/policy/2026-10-02-ks-liheap-matrix-fy2025), the FY2026 Kansas plan and benefit matrix "
    "(us-ks/policy/2026-09-10, us-ks/policy/2026-09-14-liheap-benefit-matrix), the 2024 and 2025 "
    "HHS poverty notices (us/guidance/2026-10-02-hhs-poverty-2024-2025) and the federal LIHEAP "
    "statute (us/statute/2026-09-13-liheap-statute-chapter-94-title-42). It replaces "
    "us-rulespec-2026-10-23-ks-liheap, which was cut from "
    "us-rulespec-2026-10-22-ca-concurrent-versions and so lacks the pin line's later scopes. "
    "Every other scope is kept, including the pin's three withdrawn ME, MI and MN 2026-07-13 "
    "recovery scopes under exceptions recorded for this selector. It is a publish-only pin "
    "release for rulespec-us; do not activate it."
)


def _key(scope: dict[str, str]) -> tuple[str, str, str]:
    return (scope["jurisdiction"], scope["document_class"], scope["version"])


def build_release(
    *, release_dir: Path = REPO_ROOT / "manifests/releases", output_dir: Path | None = None
) -> Path:
    """Add the seven Kansas LIHEAP scopes to the base release; keep every other scope."""
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
