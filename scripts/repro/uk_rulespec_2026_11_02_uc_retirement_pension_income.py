#!/usr/bin/env python3
"""Build the UK RuleSpec pin release that adds the UC retirement pension income scopes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BASE_RELEASE = "uk-rulespec-2026-10-25-pe-child-definitions"
RELEASE = "uk-rulespec-2026-11-02-uc-retirement-pension-income"
ADDITIONS = (
    {
        "document_class": "regulation",
        "jurisdiction": "uk",
        "version": "2026-11-02-uk-uc-retirement-pension-income",
    },
    {
        "document_class": "statute",
        "jurisdiction": "uk",
        "version": "2026-11-02-uk-uc-retirement-pension-income",
    },
)
DESCRIPTION = (
    f"Successor to {BASE_RELEASE}, rulespec-uk's corpus pin. It preserves every prior "
    "scope and adds the two signed, locked scopes that define the retirement pension "
    "income Universal Credit counts as unearned income: State Pension Credit Act 2002 "
    "s.16 (uk/statute/2026-11-02-uk-uc-retirement-pension-income, 1 provision) and "
    "Universal Credit Regulations 2013 regs 67 and 73 with State Pension Credit "
    "Regulations 2002 reg 16 (uk/regulation/2026-11-02-uk-uc-retirement-pension-income, "
    "3 provisions). No pin scope carries any of their paths. It is a publish-only pin "
    "release for rulespec-uk; do not activate it."
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
