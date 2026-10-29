#!/usr/bin/env python3
"""Build the US RuleSpec pin release with Montana's 2021-2023 separate-filing authority."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BASE_RELEASE = "us-rulespec-2026-10-25-nyc-ch127-title-52"
RELEASE = "us-rulespec-2026-10-25-mt-separate-filing"
ADDITIONS = (
    {
        "document_class": "form",
        "jurisdiction": "us-mt",
        "version": "2026-10-06-w6-income-tax-forms-mt",
    },
    {
        "document_class": "regulation",
        "jurisdiction": "us-mt",
        "version": "2026-10-25-mt-separate-filing-dated-authority",
    },
    {
        "document_class": "statute",
        "jurisdiction": "us-mt",
        "version": "2026-10-06-w6-income-tax-statute-mt-r2",
    },
    {
        "document_class": "statute",
        "jurisdiction": "us-mt",
        "version": "2026-10-25-mt-separate-filing-dated-authority",
    },
)
DESCRIPTION = (
    f"Successor to {BASE_RELEASE} on rulespec-us's corpus pin line. It adds the Montana "
    "texts for married taxpayers filing separately in tax years 2021-2023: ARM 42.15.524 as "
    "in effect from 4/30/2010 (us-mt/regulation/2026-10-25-mt-separate-filing-dated-authority) "
    "and the Montana Code Annotated 2021 text of 15-30-2602 "
    "(us-mt/statute/2026-10-25-mt-separate-filing-dated-authority), each at a variant path, and "
    "two signed, locked scopes already on main: us-mt/statute/2026-10-06-w6-income-tax-statute-mt-r2 "
    "(the MCA 2019 and 2021 texts of 15-30-2131, 2021 SB 399, and 2023 HB 192 and HB 222) and "
    "us-mt/form/2026-10-06-w6-income-tax-forms-mt (Form 2 and its instructions for tax years "
    "2021-2024, and two related forms). "
    "Every other scope is kept, including the pin's three withdrawn ME, MI and MN 2026-07-13 "
    "recovery scopes under exceptions recorded for this selector. It is a publish-only pin "
    "release for rulespec-us; do not activate it."
)


def _key(scope: dict[str, str]) -> tuple[str, str, str]:
    return (scope["jurisdiction"], scope["document_class"], scope["version"])


def build_release(
    *, release_dir: Path = REPO_ROOT / "manifests/releases", output_dir: Path | None = None
) -> Path:
    """Add the four Montana scopes to the base release; keep every other scope."""
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
