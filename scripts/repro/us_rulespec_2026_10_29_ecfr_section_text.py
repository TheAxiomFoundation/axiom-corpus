#!/usr/bin/env python3
"""Build the US RuleSpec pin release with the eCFR section-text successor scopes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BASE_RELEASE = "us-rulespec-2026-10-25-mt-separate-filing"
RELEASE = "us-rulespec-2026-10-29-ecfr-section-text"
# Predecessor version -> successor version, all us/regulation. The successors carry #832's
# table captions and word breaks (#943, #944); each pair holds the same citation paths.
REPLACEMENTS = {
    "2026-06-18-title-47-part-54-r2026-07-15-self-contained": (
        "2026-06-18-r2026-10-29-ecfr-section-text-title-47-part-54"
    ),
    "2026-06-24-title-45-part-1302": "2026-06-24-r2026-10-29-ecfr-section-text-title-45-part-1302",
    "2026-07-13-recovery-r2026-07-17-dedup": (
        "2026-07-13-recovery-r2026-07-17-dedup-r2026-10-29-ecfr-section-text"
    ),
}
JURISDICTION = "us"
DOCUMENT_CLASS = "regulation"
DESCRIPTION = (
    f"Successor to {BASE_RELEASE} on rulespec-us's corpus pin line. It replaces three us/regulation "
    "scopes with successors that keep eCFR table captions as marked caption blocks and separate "
    "words at line breaks (axiom-corpus#832), at the same citation paths: 47 CFR part 54 "
    "(2026-06-18-title-47-part-54-r2026-07-15-self-contained -> "
    "2026-06-18-r2026-10-29-ecfr-section-text-title-47-part-54), 45 CFR part 1302 "
    "(2026-06-24-title-45-part-1302 -> 2026-06-24-r2026-10-29-ecfr-section-text-title-45-part-1302) "
    "and the July 13 recovery scope (2026-07-13-recovery-r2026-07-17-dedup -> "
    "2026-07-13-recovery-r2026-07-17-dedup-r2026-10-29-ecfr-section-text). The 47 CFR 54 and "
    "45 CFR 1302 successors also carry earlier source-backed extractor repairs (note headings and "
    "formula blocks in part 54, the 1302.1 Overview text). Every other scope is kept, "
    "including the pin's three withdrawn ME, MI and MN 2026-07-13 recovery scopes under exceptions "
    "recorded for this selector. It is a publish-only pin release for rulespec-us; do not activate it."
)


def _key(scope: dict[str, str]) -> tuple[str, str, str]:
    return (scope["jurisdiction"], scope["document_class"], scope["version"])


def build_release(
    *, release_dir: Path = REPO_ROOT / "manifests/releases", output_dir: Path | None = None
) -> Path:
    """Swap each predecessor in the base release for its successor; keep every other scope."""
    payload = json.loads((release_dir / f"{BASE_RELEASE}.json").read_text(encoding="utf-8"))
    scopes = payload["scopes"]
    keys = {_key(scope) for scope in scopes}
    if len(keys) != len(scopes):
        raise ValueError("base release contains duplicate scopes")
    missing = sorted(old for old in REPLACEMENTS if (JURISDICTION, DOCUMENT_CLASS, old) not in keys)
    if missing:
        raise ValueError(f"base release does not select {missing}")
    present = sorted(
        new for new in REPLACEMENTS.values() if (JURISDICTION, DOCUMENT_CLASS, new) in keys
    )
    if present:
        raise ValueError(f"base release already selects {present}")
    final_scopes = []
    for scope in scopes:
        scope = dict(scope)
        if (scope["jurisdiction"], scope["document_class"]) == (JURISDICTION, DOCUMENT_CLASS):
            scope["version"] = REPLACEMENTS.get(scope["version"], scope["version"])
        final_scopes.append(scope)
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
