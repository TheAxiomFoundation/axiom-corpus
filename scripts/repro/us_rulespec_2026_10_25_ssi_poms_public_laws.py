#!/usr/bin/env python3
"""Build the US RuleSpec pin release that adds the SSI POMS and W6 public-law scopes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BASE_RELEASE = "us-rulespec-2026-10-22-ca-concurrent-versions"
RELEASE = "us-rulespec-2026-10-25-ssi-poms-public-laws"
ADDITIONS = (
    {"document_class": "manual", "jurisdiction": "us", "version": "2026-09-10-ssi-poms-si"},
    {
        "document_class": "manual",
        "jurisdiction": "us",
        "version": "2026-09-13-ssi-poms-si-remainder",
    },
    {
        "document_class": "statute",
        "jurisdiction": "us",
        "version": "2026-10-06-w6-federal-public-laws",
    },
)
DESCRIPTION = (
    f"Successor to {BASE_RELEASE}, rulespec-us's corpus pin. It preserves every prior "
    "scope and adds three signed, locked scopes that the W6, W5 and W7 union releases already "
    "carry: the "
    "SSA POMS part SI sections (us/manual/2026-09-10-ssi-poms-si and its 2026-09-13 remainder, "
    "at us/manual/ssa/poms/si/<section>) and the W6 federal public laws "
    "(us/statute/2026-10-06-w6-federal-public-laws, at us/statute/public-law/<congress>-<number>, "
    "including Pub. L. 98-21 and Pub. L. 103-66). None of their paths is carried by a pin scope. "
    "It keeps the pin's three withdrawn ME, MI and MN 2026-07-13 recovery scopes under "
    "exceptions recorded for this selector. It is a publish-only pin release for rulespec-us; "
    "do not activate it."
)


def _key(scope: dict[str, str]) -> tuple[str, str, str]:
    return (scope["jurisdiction"], scope["document_class"], scope["version"])


def build_release(
    *, release_dir: Path = REPO_ROOT / "manifests/releases", output_dir: Path | None = None
) -> Path:
    """Add the three scopes to the pin without replacing any scope."""
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
