#!/usr/bin/env python3
"""Build the US RuleSpec release with current D.C. Code title 47 and DC EITC sources.

The selector is the union of the two published successors of
us-rulespec-2026-08-08-obbb-alien-snap, so it rolls neither back:
us-rulespec-2026-08-23-canada-338-suspension-union and the SNAP FY 2027 COLA
scope of us-rulespec-2026-09-24-snap-fy2027-cola. It then replaces the stale
D.C. Code title 47 scope and adds the TY2022-TY2023 DC EITC sources.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

BASE_RELEASE = "us-rulespec-2026-08-23-canada-338-suspension-union"
SIBLING_RELEASE = "us-rulespec-2026-09-24-snap-fy2027-cola"
SIBLING_BASE_RELEASE = "us-rulespec-2026-08-08-obbb-alien-snap"
RELEASE = "us-rulespec-2026-09-26-dc-title-47-eitc-union"
REMOVALS = (
    {
        "document_class": "statute",
        "jurisdiction": "us-dc",
        "version": "2026-07-16-pit-east-title-47",
    },
)
ADDITIONS = (
    {
        "document_class": "statute",
        "jurisdiction": "us-dc",
        "version": "2026-09-26-codified-title-47",
    },
    {
        "document_class": "form",
        "jurisdiction": "us-dc",
        "version": "2026-09-26-dc-otr-d-40-booklets-ty2022-ty2023",
    },
    {
        "document_class": "guidance",
        "jurisdiction": "us",
        "version": "2026-09-26-irs-rev-procs-2021-45-2022-38",
    },
)


def _identity(scope: dict[str, str]) -> tuple[str, str, str]:
    return (scope["jurisdiction"], scope["document_class"], scope["version"])


def _scopes(release_dir: Path, name: str) -> list[dict[str, str]]:
    payload = json.loads((release_dir / f"{name}.json").read_text(encoding="utf-8"))
    return payload["scopes"]


def sibling_additions(release_dir: Path) -> list[dict[str, str]]:
    """Scopes the FY 2027 COLA release added to the common obbb predecessor."""
    common = {_identity(scope) for scope in _scopes(release_dir, SIBLING_BASE_RELEASE)}
    return [
        scope for scope in _scopes(release_dir, SIBLING_RELEASE) if _identity(scope) not in common
    ]


def build_release(*, release_dir: Path, output_dir: Path | None = None) -> Path:
    source = release_dir / f"{BASE_RELEASE}.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    scopes = list(payload["scopes"])
    identities = {_identity(scope) for scope in scopes}

    for scope in sibling_additions(release_dir):
        if _identity(scope) in identities:
            raise ValueError(f"sibling scope already in base release: {scope}")
        scopes.append(scope)
        identities.add(_identity(scope))
    for scope in REMOVALS:
        if _identity(scope) not in identities:
            raise ValueError(f"scope to replace is not in base release: {scope}")
    scopes = [scope for scope in scopes if scope not in REMOVALS]
    for scope in ADDITIONS:
        if _identity(scope) in identities:
            raise ValueError(f"addition already in base release: {scope}")
        scopes.append(scope)

    final_scopes = sorted(scopes, key=_identity)
    if len({_identity(scope) for scope in final_scopes}) != len(final_scopes):
        raise ValueError("release selector would contain duplicate scopes")

    payload.update(
        {
            "description": (
                f"Successor to {BASE_RELEASE} that also carries the SNAP FY 2027 COLA "
                f"scope of {SIBLING_RELEASE}. It replaces us-dc/statute "
                "2026-07-16-pit-east-title-47, extracted from a legacy tree whose "
                "title 47 history ends at D.C. Law 21-98, "
                "with 2026-09-26-codified-title-47 (DCCouncil/law-xml-codified "
                "publication of 2026-09-16), and adds the OTR 2022 and 2023 D-40 "
                "booklets and IRS Rev. Procs. 2021-45 and 2022-38 for the DC earned "
                "income tax credit (D.C. Code 47-1806.04(f))."
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
