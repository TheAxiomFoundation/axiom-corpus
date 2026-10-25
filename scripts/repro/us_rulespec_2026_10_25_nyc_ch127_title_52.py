#!/usr/bin/env python3
"""Build the US RuleSpec pin release with the NYC ch. 127 text and the Title 52 election scope."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BASE_RELEASE = "us-rulespec-2026-10-25-ssi-poms-public-laws"
RELEASE = "us-rulespec-2026-10-25-nyc-ch127-title-52"
ADDITIONS = (
    {
        "document_class": "statute",
        "jurisdiction": "us",
        "version": "2026-09-29-election-statute-uocava-nvra-title-52",
    },
    {"document_class": "statute", "jurisdiction": "us-ny", "version": "2026-09-28-nyc-admin-code"},
)
REPLACED = (
    {"document_class": "statute", "jurisdiction": "us-ny", "version": "2026-06-05-nyc-admin-code"},
)
DESCRIPTION = (
    f"Successor to {BASE_RELEASE}, rulespec-us's corpus pin. It replaces the NYC "
    "Administrative Code scope us-ny/statute/2026-06-05-nyc-admin-code with "
    "us-ny/statute/2026-09-28-nyc-admin-code, which carries the same three sections "
    "(11-1701, 11-1704.1 and 11-1706) at the same paths with the text as amended by "
    "chapter 127 of 2026 (A.11561 Part D) and Local Law 133 of 2026. It adds the signed, "
    "locked Title 52 election scope us/statute/2026-09-29-election-statute-uocava-nvra-title-52 "
    "(52 U.S.C. 20302, 20310 and 20507, at us/statute/52/...). Every other scope is kept, "
    "including the pin's three withdrawn ME, MI and MN 2026-07-13 recovery scopes under "
    "exceptions recorded for this selector. It is a publish-only pin release for rulespec-us; "
    "do not activate it."
)


def _key(scope: dict[str, str]) -> tuple[str, str, str]:
    return (scope["jurisdiction"], scope["document_class"], scope["version"])


def build_release(
    *, release_dir: Path = REPO_ROOT / "manifests/releases", output_dir: Path | None = None
) -> Path:
    """Drop the replaced scope from the pin and add the two scopes; keep every other scope."""
    payload = json.loads((release_dir / f"{BASE_RELEASE}.json").read_text(encoding="utf-8"))
    scopes = payload["scopes"]
    base_keys = {_key(scope) for scope in scopes}
    present = base_keys & {_key(scope) for scope in ADDITIONS}
    if present:
        raise ValueError(f"base release already selects {sorted(present)}")
    missing = {_key(scope) for scope in REPLACED} - base_keys
    if missing:
        raise ValueError(f"base release does not select {sorted(missing)}")
    replaced = {_key(scope) for scope in REPLACED}
    kept = [scope for scope in scopes if _key(scope) not in replaced]
    final_scopes = sorted([*kept, *map(dict, ADDITIONS)], key=_key)
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
