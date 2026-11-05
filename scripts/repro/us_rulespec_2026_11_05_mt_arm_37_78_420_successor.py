#!/usr/bin/env python3
"""Build the US RuleSpec pin release with the Montana ARM 37.78.420 successor scope."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BASE_RELEASE = "us-rulespec-2026-10-29-ecfr-section-text"
RELEASE = "us-rulespec-2026-11-05-mt-arm-37-78-420-successor"
# Forty other pairs in the base also select a version named 2026-07-13-recovery, us-mt/statute
# among them, so the swap matches the whole scope.
PREDECESSOR = ("us-mt", "regulation", "2026-07-13-recovery")
SUCCESSOR = ("us-mt", "regulation", "2026-07-13-recovery-r2026-09-27-chrome-free")
DESCRIPTION = (
    f"Successor to {BASE_RELEASE} on rulespec-us's corpus pin line. It replaces "
    "us-mt/regulation/2026-07-13-recovery with its signed successor, "
    "us-mt/regulation/2026-07-13-recovery-r2026-09-27-chrome-free, which carries ARM 37.78.420 "
    "at the same citation path without the rules.mt.gov page chrome (axiom-corpus#761). Every "
    "other scope stays, including the pin's three withdrawn ME, MI and MN 2026-07-13 recovery "
    "scopes; manifests/withdrawn-scopes.yaml records an exception for this selector on each. "
    "Publish it only as a pin release for rulespec-us; do not activate it."
)


def _key(scope: dict[str, str]) -> tuple[str, str, str]:
    return (scope["jurisdiction"], scope["document_class"], scope["version"])


def build_release(
    *, release_dir: Path = REPO_ROOT / "manifests/releases", output_dir: Path | None = None
) -> Path:
    """Swap the predecessor scope in the base release for its successor; keep every other scope."""
    payload = json.loads((release_dir / f"{BASE_RELEASE}.json").read_text(encoding="utf-8"))
    scopes = payload["scopes"]
    keys = {_key(scope) for scope in scopes}
    if len(keys) != len(scopes):
        raise ValueError("base release contains duplicate scopes")
    if PREDECESSOR not in keys:
        raise ValueError(f"base release does not select {'/'.join(PREDECESSOR)}")
    if SUCCESSOR in keys:
        raise ValueError(f"base release already selects {'/'.join(SUCCESSOR)}")
    final_scopes = [dict(scope) for scope in scopes]
    for scope in final_scopes:
        if _key(scope) == PREDECESSOR:
            scope["version"] = SUCCESSOR[2]
    final_scopes.sort(key=_key)
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
