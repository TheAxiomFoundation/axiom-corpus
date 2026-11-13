#!/usr/bin/env python3
"""Build the US RuleSpec pin release that adds the wave-6 federal CMS guidance scope."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BASE_RELEASE = "us-rulespec-2026-10-27-ks-liheap"
RELEASE = "us-rulespec-2026-11-11-cms-w6-federal-guidance"
# The base selects 15 other us/guidance versions, so the refusals match the whole scope.
ADDED = ("us", "guidance", "2026-10-06-w6-federal-cms-guidance")
DESCRIPTION = (
    f"Successor to {BASE_RELEASE} on rulespec-us's corpus pin line, whose newest cut that "
    "selector is: it holds all 276 scopes of rulespec-us's pin, "
    "us-rulespec-2026-10-29-ecfr-section-text, and seven Kansas LIHEAP scopes. This selector "
    "keeps all 283 and adds one signed scope, "
    "us/guidance/2026-10-06-w6-federal-cms-guidance (axiom-corpus#786, "
    "docs/ingest-runs/2026-10-06-w6-federal.md), which carries the CMCS Informational Bulletin "
    "of 2025-12-08 on Medicaid community engagement requirements at "
    "us/guidance/cms/cib/2025-12-08 with the scope's other CMS documents. Every scope of the "
    "base stays, including the pin's three withdrawn ME, MI and MN 2026-07-13 recovery scopes; "
    "manifests/withdrawn-scopes.yaml records an exception for this selector on each. Publish it "
    "only as a pin release for rulespec-us; do not activate it."
)


def _key(scope: dict[str, str]) -> tuple[str, str, str]:
    return (scope["jurisdiction"], scope["document_class"], scope["version"])


def build_release(
    *, release_dir: Path = REPO_ROOT / "manifests/releases", output_dir: Path | None = None
) -> Path:
    """Add the one scope to the base release; keep every other scope."""
    payload = json.loads((release_dir / f"{BASE_RELEASE}.json").read_text(encoding="utf-8"))
    scopes = payload["scopes"]
    keys = {_key(scope) for scope in scopes}
    if len(keys) != len(scopes):
        raise ValueError("base release contains duplicate scopes")
    if ADDED in keys:
        raise ValueError(f"base release already selects {'/'.join(ADDED)}")
    final_scopes = [dict(scope) for scope in scopes]
    final_scopes.append({"document_class": ADDED[1], "jurisdiction": ADDED[0], "version": ADDED[2]})
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
