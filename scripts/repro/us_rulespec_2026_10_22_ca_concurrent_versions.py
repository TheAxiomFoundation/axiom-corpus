#!/usr/bin/env python3
"""Build the US RuleSpec pin release that adds California's concurrent LegInfo versions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BASE_RELEASE = "us-rulespec-2026-10-20-fs-pilot-reg-e-f"
RELEASE = "us-rulespec-2026-10-22-ca-concurrent-versions"
ADDITION = {
    "document_class": "statute",
    "jurisdiction": "us-ca",
    "version": (
        "2026-09-26-ca-leginfo-concurrent-versions-us-ca-sections-"
        "wic-11450--all-wic-11451.5--all-rtc-17552.3--all-rtc-17563.5--all"
    ),
}
DESCRIPTION = (
    f"Successor to {BASE_RELEASE}, rulespec-us's corpus pin. It preserves every prior "
    "scope and adds the California LegInfo concurrent-versions scope from axiom-corpus#752: "
    "each current version of WIC 11450, WIC 11451.5, R&TC 17552.3 and R&TC 17563.5 at its own "
    "<section>--<slug> variant path, including WIC 11450's later version "
    "(us-ca/statute/wic/11450--operative-2024-07-01), which governs CalWORKs maximum aid "
    "payments. Plain section paths keep their existing carriers. It is a publish-only pin "
    "release for rulespec-us; do not activate it."
)


def _key(scope: dict[str, str]) -> tuple[str, str, str]:
    return (scope["jurisdiction"], scope["document_class"], scope["version"])


def build_release(
    *, release_dir: Path = REPO_ROOT / "manifests/releases", output_dir: Path | None = None
) -> Path:
    """Add the concurrent-versions scope to the pin without replacing any scope."""
    payload = json.loads((release_dir / f"{BASE_RELEASE}.json").read_text(encoding="utf-8"))
    scopes = payload["scopes"]
    if any(_key(scope) == _key(ADDITION) for scope in scopes):
        raise ValueError("California concurrent-versions scope already exists in the base release")
    final_scopes = sorted([*scopes, dict(ADDITION)], key=_key)
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
