#!/usr/bin/env python3
"""Build the collision-free US RuleSpec ECPS release selector."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

BASE_RELEASE = "us-rulespec-2026-07-31-idaho-statutes-current"
RELEASE = "us-rulespec-2026-08-03-ecps-pit-tariff-union"


@dataclass(frozen=True, order=True)
class Scope:
    jurisdiction: str
    document_class: str
    version: str

    @classmethod
    def from_mapping(cls, payload: dict[str, str]) -> Scope:
        return cls(
            jurisdiction=payload["jurisdiction"],
            document_class=payload["document_class"],
            version=payload["version"],
        )

    def to_mapping(self) -> dict[str, str]:
        return {
            "document_class": self.document_class,
            "jurisdiction": self.jurisdiction,
            "version": self.version,
        }


REPLACEMENTS = {
    Scope("us", "statute", "2026-07-19-rulespec-title-26-consolidated"): Scope(
        "us", "statute", "2026-08-03-rulespec-title-26-current-union"
    ),
    Scope("us-nc", "statute", "2026-07-13-recovery"): Scope(
        "us-nc", "statute", "2026-08-03-nc-income-tax-current-union"
    ),
}

ADDITIONS = (
    Scope("us", "guidance", "2026-07-23-irs-notice-2025-67"),
    Scope("us", "rulemaking", "2026-08-03-rulespec-tariff-rulemaking-union"),
    Scope("us", "statute", "2026-08-03-tariff-title-19-spine-with-root-title-19"),
    Scope("us", "statute", "2026-08-01-usitc-hts-2026-rev3-notes"),
    Scope("us", "statute", "2026-08-03-rulespec-hts-current-with-legacy-aluminum"),
    Scope("us-ak", "statute", "2026-07-24-ak-individual-income-tax"),
    Scope("us-ca", "form", "2026-07-23-ca-2025-tax-materials-for-2026-estimates"),
    Scope("us-ca", "form", "2026-07-23-ca-2026-form-540-es"),
    Scope("us-ca", "guidance", "2026-07-28-ca-cdss-calfresh-bbce-authority"),
    Scope(
        "us-ca",
        "statute",
        "2026-07-28-ca-cdss-calfresh-bbce-authority-us-ca-sections-wic-18901.3-wic-18901.5",
    ),
    Scope("us-ct", "statute", "2026-07-24-ct-income-tax-supplement"),
    Scope("us-ct", "statute", "2026-07-26-ct-12-700-a-10"),
    Scope("us-fl", "statute", "2026-07-24-fl-individual-income-tax-zero-liability"),
    Scope("us-hi", "form", "2026-07-22-hi-2025-n11-capital-gain-worksheet"),
    Scope("us-il", "guidance", "2026-07-24-il-personal-exemption-guidance"),
    Scope("us-il", "statute", "2026-07-24-il-individual-income-tax-resident-core"),
    Scope("us-in", "guidance", "2026-07-24-in-2026-individual-income-tax-source-hold"),
    Scope("us-ks", "guidance", "2026-07-24-ks-2026-income-tax-rate-determination"),
    Scope("us-ks", "statute", "2026-07-24-ks-resident-income-tax-core"),
    Scope("us-ky", "form", "2026-740-es"),
    Scope("us-ky", "statute", "2026-07-22-individual-income-tax"),
    Scope("us-la", "form", "2026-07-23-la-2026-it-540es-instructions"),
    Scope("us-ma", "form", "2026-07-22-ma-2026-form-1-es"),
    Scope(
        "us-ma",
        "guidance",
        "2026-08-03-ma-dta-snap-cola-official-source-recovery",
    ),
    Scope("us-ma", "guidance", "2026-07-22-ma-2026-surtax-guidance"),
    Scope("us-me", "guidance", "2026-07-23-me-individual-income-tax-rates-2026"),
    Scope(
        "us-mn",
        "guidance",
        "2026-07-22-mn-income-tax-inflation-adjusted-amounts-2026",
    ),
    Scope("us-ne", "form", "2026-07-22-ne-1040n-es-2026"),
    Scope("us-nv", "statute", "2026-07-24-nv-individual-income-tax-zero-liability"),
    Scope("us-ny", "form", "2026-06-05-ny-tax-current-forms"),
    Scope("us-ny", "policy", "2026-08-03-ny-tanf-official-source-recovery"),
    Scope("us-ny", "statute", "2026-06-05-nyc-admin-code"),
    Scope(
        "us-ny",
        "statute",
        "2026-07-06-ny-tax-article22-core-us-ny-sections-tax-601-tax-606-tax-614-tax-615-tax-616",
    ),
    Scope("us-ny", "statute", "2026-07-13-recovery"),
    Scope("us-oh", "guidance", "2026-07-21-oh-hb96-final-analysis"),
    Scope("us-or", "form", "2026-07-22-or-estimate-2026"),
    Scope("us-or", "statute", "2026-07-24-or-pit-session-laws"),
    Scope("us-ri", "guidance", "2026-07-23-ri-pit-adv-2025-22"),
    Scope("us-sd", "guidance", "2026-07-24-sd-personal-income-tax-zero-liability"),
    Scope("us-sd", "statute", "2026-07-24-sd-bank-income-tax-boundary"),
    Scope(
        "us-tn",
        "guidance",
        "2026-07-24-tn-individual-income-tax-zero-liability-guidance",
    ),
    Scope("us-tn", "statute", "2026-07-24-tn-hall-income-tax-zero-rate-statute"),
    Scope("us-wi", "form", "2026-07-22-wi-form1-es-2026"),
)


def build_release(*, release_dir: Path, output_dir: Path | None = None) -> Path:
    """Write the immutable selector from its reviewed predecessor."""
    source = release_dir / f"{BASE_RELEASE}.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    scopes = [Scope.from_mapping(scope) for scope in payload["scopes"]]
    replacement_counts = dict.fromkeys(REPLACEMENTS, 0)
    replaced: list[Scope] = []
    for scope in scopes:
        if scope in REPLACEMENTS:
            replacement_counts[scope] += 1
            replaced.append(REPLACEMENTS[scope])
        else:
            replaced.append(scope)
    invalid_counts = {scope: count for scope, count in replacement_counts.items() if count != 1}
    if invalid_counts:
        raise ValueError(f"release replacements must each match once: {invalid_counts}")

    final_scopes = tuple(sorted((*replaced, *ADDITIONS)))
    if len(final_scopes) != len(set(final_scopes)):
        raise ValueError("release selector would contain duplicate scopes")
    payload.update(
        {
            "description": (
                f"Successor to {BASE_RELEASE}. It preserves the signed SNAP, CMS, and "
                "personal-income-tax union; replaces federal Title 26 and North "
                "Carolina with collision-free current successors; and adds the "
                "current state PIT, IRS, and tariff authorities required by the "
                "RuleSpec ECPS hard cut."
            ),
            "name": RELEASE,
            "scopes": [scope.to_mapping() for scope in final_scopes],
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
