#!/usr/bin/env python3
"""Build the US RuleSpec pin release that adds the signed Tier 1 program-bundle source text."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BASE_RELEASE = "us-rulespec-2026-11-11-cms-w6-federal-guidance"
RELEASE = "us-rulespec-2026-11-24-tier1-source-text"
# Signed scopes that us-rulespec-2026-10-13-w7-bundle-gaps-union selects and the pin line does
# not. Each carries the text of at least one Tier 1 document of the SNAP, Medicaid, CHIP or UI
# program bundle (docs/ingest-runs/2026-11-24-us-rulespec-tier1-source-text.md lists them).
ADDED: tuple[tuple[str, str, str], ...] = (
    ("us", "form", "2026-09-10-tax-irs-forms-ty2025"),
    ("us", "form", "2026-09-15-irs-forms-ty2025"),
    ("us", "guidance", "2026-08-03-snap-obbb-abawd-exceptions-implementation-memo"),
    ("us", "guidance", "2026-09-13-liheap-annual-figures-2026"),
    ("us", "guidance", "2026-10-06-w6-federal-agency-guidance"),
    ("us", "policy", "2026-10-06-w6-federal-cms-state-plans"),
    ("us", "regulation", "2026-07-24-1401-coordination-repair-title-26-part-1-r2026-09-13-closure-sections-consolidated-r2026-10-07-w6-1-414-consolidated"),
    ("us", "regulation", "2026-09-11-title-20-part-416"),
    ("us", "regulation", "2026-09-13-title-7-part-271"),
    ("us", "regulation", "2026-10-06-w6-federal-ecfr-closure-title-42-part-440"),
    ("us", "regulation", "2026-10-06-w6-federal-ecfr-closure-title-45-part-146"),
    ("us", "regulation", "2026-10-06-w6-federal-ecfr-closure-title-45-part-155"),
    ("us", "statute", "2026-09-13-tanf-statute-part-a-title-42"),
    ("us", "statute", "2026-09-13-tax-statute-closure-31-title-26"),
    ("us", "statute", "2026-10-06-w6-federal-usc-closure-title-26"),
    ("us", "statute", "2026-10-06-w6-federal-usc-closure-title-42"),
    ("us", "statute", "2026-10-12-w7-federal-usc-closure-title-25"),
    ("us", "statute", "2026-10-12-w7-federal-usc-closure-title-26"),
    ("us", "statute", "2026-10-12-w7-federal-usc-closure-title-29"),
    ("us", "statute", "2026-10-12-w7-federal-usc-closure-title-38"),
    ("us", "statute", "2026-10-12-w7-federal-usc-closure-title-8"),
    ("us-ak", "guidance", "2026-10-06-w6-benefits-guidance-ak"),
    ("us-al", "guidance", "2026-10-06-w6-benefits-guidance-al"),
    ("us-al", "guidance", "2026-10-06-w6-health-guidance-al"),
    ("us-al", "manual", "2026-09-10-chip-state-eligibility-manual"),
    ("us-al", "policy", "2026-09-13-medicaid-state-plan"),
    ("us-al", "regulation", "2026-10-06-w6-benefits-regulation-al"),
    ("us-al", "regulation", "2026-10-06-w6-health-regulation-al"),
    ("us-al", "statute", "2026-10-06-w6-benefits-ui-statute-us-al-title-25"),
    ("us-ar", "manual", "2026-09-10-medicaid-state-eligibility-manual"),
    ("us-ca", "form", "2026-10-06-w6-health-form-ca"),
    ("us-ca", "guidance", "2026-09-23-ca-cdss-acl-06-31"),
    ("us-ca", "guidance", "2026-10-06-w6-benefits-guidance-ca"),
    ("us-ca", "guidance", "2026-10-06-w6-health-guidance-ca"),
    ("us-ca", "manual", "2026-10-06-w6-health-manual-ca"),
    ("us-ca", "policy", "2026-09-13-chip-state-plan"),
    ("us-ca", "statute", "2026-10-06-w6-tanf-ccdf-statutes-ca-us-ca-title-wic-r2026-10-07-without-released-sections-consolidated"),
    ("us-co", "guidance", "2026-10-06-w6-health-guidance-co"),
    ("us-co", "manual", "2026-09-10-medicaid-state-eligibility-manual"),
    ("us-co", "statute", "2026-07-19-rulespec-us-co-title-39-consolidated-r2026-10-07-w6-title-10-consolidated"),
    ("us-ct", "guidance", "2026-10-06-w6-health-guidance-ct"),
    ("us-ct", "manual", "2026-09-10-chip-state-eligibility-manual"),
    ("us-dc", "guidance", "2026-10-06-w6-benefits-guidance-dc"),
    ("us-dc", "guidance", "2026-10-06-w6-health-guidance-dc"),
    ("us-de", "rulemaking", "2026-09-23-de-register-13-de-reg-1550"),
    ("us-de", "rulemaking", "2026-10-06-w6-benefits-rulemaking-de"),
    ("us-fl", "guidance", "2026-10-06-w6-health-guidance-fl"),
    ("us-fl", "policy", "2026-09-13-medicaid-state-plan"),
    ("us-ga", "guidance", "2026-10-06-w6-health-guidance-ga"),
    ("us-ga", "manual", "2026-09-10-chip-state-eligibility-manual"),
    ("us-ga", "manual", "2026-09-10-medicaid-state-eligibility-manual"),
    ("us-ga", "manual", "2026-10-06-w6-health-manual-ga"),
    ("us-ga", "policy", "2026-09-13-medicaid-state-plan"),
    ("us-hi", "guidance", "2026-10-06-w6-benefits-guidance-hi"),
    ("us-hi", "regulation", "2026-09-10-medicaid-state-eligibility-manual"),
    ("us-ia", "guidance", "2026-10-06-w6-health-guidance-ia"),
    ("us-ia", "regulation", "2026-10-06-w6-health-regulation-ia"),
    ("us-id", "policy", "2026-09-13-chip-state-plan"),
    ("us-id", "regulation", "2026-09-10-chip-state-eligibility-manual"),
    ("us-il", "guidance", "2026-10-06-w6-health-guidance-il"),
    ("us-il", "manual", "2026-09-23-il-dhs-mr-23-22"),
    ("us-il", "manual", "2026-10-12-w7-state-benefits-manual-il"),
    ("us-il", "regulation", "2026-09-14-income-tax-regulations-title-086-part-00100-r2026-10-07-w6-title-023-089-consolidated"),
    ("us-il", "statute", "2026-10-06-w6-health-statute-il-us-il-chapter-305-act-5"),
    ("us-in", "guidance", "2026-10-06-w6-health-guidance-in"),
    ("us-ks", "guidance", "2026-10-06-w6-health-guidance-ks"),
    ("us-ks", "manual", "2026-09-10-medicaid-state-eligibility-manual"),
    ("us-la", "guidance", "2026-10-06-w6-benefits-guidance-la"),
    ("us-la", "regulation", "2026-10-06-w6-health-regulation-la"),
    ("us-la", "regulation", "2026-10-06-w6-tanf-ccdf-rules-la"),
    ("us-la", "rulemaking", "2026-10-06-w6-benefits-rulemaking-la"),
    ("us-ma", "guidance", "2026-09-23-ma-dta-policy-online-snap-child-support"),
    ("us-ma", "guidance", "2026-10-06-w6-benefits-guidance-ma"),
    ("us-ma", "regulation", "2026-09-10-chip-state-eligibility-manual"),
    ("us-md", "guidance", "2026-10-06-w6-benefits-guidance-md"),
    ("us-md", "regulation", "2026-09-10-ssi-state-supplement-publication-2026-09-09-title-07-subtitle-03-chapters-06-07-r2026-10-07-chapters-03-17-title-03-subtitle-04-consolidated"),
    ("us-md", "statute", "2026-10-06-w6-benefits-statute-md"),
    ("us-me", "rulemaking", "2026-10-06-w6-benefits-rulemaking-me"),
    ("us-mi", "guidance", "2026-10-06-w6-benefits-guidance-mi"),
    ("us-mi", "guidance", "2026-10-06-w6-health-guidance-mi"),
    ("us-mn", "manual", "2026-09-10-chip-state-eligibility-manual"),
    ("us-mo", "guidance", "2026-10-06-w6-health-guidance-mo"),
    ("us-mo", "manual", "2026-09-10-chip-state-eligibility-manual"),
    ("us-mo", "manual", "2026-09-10-medicaid-state-eligibility-manual"),
    ("us-mo", "manual", "2026-10-12-w7-state-benefits-manual-mo"),
    ("us-mo", "statute", "2026-10-06-w6-health-statute-mo"),
    ("us-ms", "guidance", "2026-10-06-w6-health-guidance-ms"),
    ("us-ms", "manual", "2026-09-10-chip-state-eligibility-manual"),
    ("us-ms", "manual", "2026-10-06-w6-health-manual-ms"),
    ("us-ms", "policy", "2026-09-13-medicaid-state-plan"),
    ("us-ms", "policy", "2026-10-06-w6-health-policy-ms"),
    ("us-ms", "regulation", "2026-10-06-w6-health-regulation-ms"),
    ("us-mt", "manual", "2026-09-10-medicaid-state-eligibility-manual"),
    ("us-nc", "guidance", "2026-10-12-w7-state-benefits-guidance-nc"),
    ("us-nd", "guidance", "2026-10-06-w6-health-guidance-nd"),
    ("us-nd", "manual", "2026-09-10-chip-state-eligibility-manual"),
    ("us-nh", "manual", "2026-09-10-medicaid-state-eligibility-manual"),
    ("us-nh", "policy", "2026-09-13-medicaid-state-plan"),
    ("us-nj", "guidance", "2026-09-14-snap-fy2026-state-transmittal"),
    ("us-nj", "guidance", "2026-10-06-w6-benefits-guidance-nj"),
    ("us-nj", "rulemaking", "2026-10-12-w7-state-benefits-rulemaking-nj"),
    ("us-nj", "statute", "2026-10-12-w7-state-benefits-statute-nj"),
    ("us-nv", "guidance", "2026-10-06-w6-health-guidance-nv"),
    ("us-nv", "policy", "2026-09-13-medicaid-state-plan"),
    ("us-ny", "guidance", "2026-10-06-w6-benefits-guidance-ny"),
    ("us-ny", "manual", "2026-09-10-chip-state-eligibility-manual"),
    ("us-ny", "policy", "2026-09-13-chip-state-plan"),
    ("us-ny", "statute", "2026-10-06-w6-benefits-statute-ny"),
    ("us-ny", "statute", "2026-10-06-w6-income-tax-statute-ny-r2"),
    ("us-oh", "manual", "2026-09-10-medicaid-state-eligibility-manual"),
    ("us-ok", "guidance", "2026-10-06-w6-benefits-guidance-ok"),
    ("us-ok", "statute", "2026-10-06-w6-benefits-statute-ok"),
    ("us-or", "guidance", "2026-10-06-w6-health-guidance-or"),
    ("us-or", "regulation", "2026-09-10-tanf-state-policy-manual-chapter-461-r2026-09-14-150-316-consolidated-r2026-10-07-414-175-consolidated"),
    ("us-or", "regulation", "2026-10-06-w6-health-regulation-or"),
    ("us-or", "statute", "2026-10-06-w6-health-statute-or"),
    ("us-or", "statute", "2026-10-06-w6-health-statute-or-ors-us-or-chapter-414"),
    ("us-pa", "guidance", "2026-10-06-w6-benefits-guidance-pa"),
    ("us-pa", "regulation", "2026-10-12-w7-state-benefits-regulation-pa-title-34-chapter-65-r2026-10-13-without-shared-containers"),
    ("us-pa", "rulemaking", "2026-10-06-w6-benefits-rulemaking-pa"),
    ("us-ri", "policy", "2026-09-13-chip-state-plan"),
    ("us-sc", "guidance", "2026-09-14-msp-income-standards"),
    ("us-sc", "policy", "2026-09-13-medicaid-state-plan"),
    ("us-sc", "policy", "2026-10-06-w6-health-policy-sc"),
    ("us-tn", "policy", "2026-10-06-w6-health-policy-tn"),
    ("us-tx", "manual", "2026-09-10-medicaid-state-eligibility-manual"),
    ("us-tx", "manual", "2026-09-10-snap-state-manual-completion"),
    ("us-tx", "manual", "2026-10-06-w6-health-manual-tx"),
    ("us-tx", "statute", "2026-10-06-w6-benefits-statute-tx"),
    ("us-ut", "guidance", "2026-10-06-w6-benefits-guidance-ut"),
    ("us-ut", "regulation", "2026-10-06-w6-benefits-regulation-ut"),
    ("us-ut", "statute", "2026-10-06-w6-benefits-statute-ut"),
    ("us-va", "manual", "2026-09-10-medicaid-state-eligibility-manual"),
    ("us-va", "manual", "2026-10-06-w6-health-manual-va"),
    ("us-va", "regulation", "2026-09-23-va-22vac40-601-snap"),
    ("us-wa", "guidance", "2026-09-14-msp-income-standards"),
    ("us-wa", "guidance", "2026-10-06-w6-health-guidance-wa"),
    ("us-wa", "regulation", "2026-06-25-388-450-r2026-07-15-self-contained-r2026-10-07-388-400-424-470-w6-110-15-182-consolidated"),
    ("us-wa", "regulation", "2026-10-06-w6-benefits-regulation-wa"),
    ("us-wa", "rulemaking", "2026-10-12-w7-state-benefits-rulemaking-wa"),
    ("us-wa", "statute", "2026-10-06-w6-health-statute-wa"),
    ("us-wa", "statute", "2026-10-06-w6-tanf-ccdf-statute-wa"),
    ("us-wi", "guidance", "2026-10-06-w6-benefits-guidance-wi"),
    ("us-wi", "manual", "2026-10-06-w6-health-manual-wi"),
    ("us-wi", "policy", "2026-09-13-medicaid-state-plan"),
    ("us-wi", "statute", "2026-10-06-w6-tanf-ccdf-statute-wi-chapter-49"),
    ("us-wy", "guidance", "2026-10-06-w6-health-guidance-wy"),
    ("us-wy", "manual", "2026-09-15-medicaid-eligibility-manual-closure"),
    ("us-wy", "policy", "2026-09-13-medicaid-state-plan"),
)
# Base scopes that an added consolidated successor replaces: the successor holds every citation
# path of the scope it replaces, so keeping both would duplicate those paths.
REPLACED: tuple[tuple[str, str, str], ...] = (
    ("us-co", "statute", "2026-07-19-rulespec-us-co-title-39-consolidated"),
    ("us-wa", "regulation", "2026-06-25-388-450-r2026-07-15-self-contained"),
)
DESCRIPTION = (
    f"Successor to {BASE_RELEASE} on rulespec-us's corpus pin line, whose newest cut that "
    "selector is. This selector keeps 282 of its 284 scopes and adds 149 signed scopes that "
    "us-rulespec-2026-10-13-w7-bundle-gaps-union already selects and the pin line never did. "
    "They carry the source text of 347 Tier 1 documents of the SNAP, Medicaid, CHIP and UI "
    "program bundles that the encoder cannot read through the pin, including 80 U.S. Code "
    "sections in titles 8, 25, 26, 29, 38 and 42. Two added scopes are consolidated successors "
    "that hold every citation path of the base scope each one replaces: "
    "us-co/statute/2026-07-19-rulespec-us-co-title-39-consolidated and "
    "us-wa/regulation/2026-06-25-388-450-r2026-07-15-self-contained. Every other scope of the "
    "base stays, including the pin's three withdrawn ME, MI and MN 2026-07-13 recovery scopes; "
    "manifests/withdrawn-scopes.yaml records an exception for this selector on each. It ingests "
    "nothing. Publish it only as a pin release for rulespec-us; do not activate it."
)


def _key(scope: dict[str, str]) -> tuple[str, str, str]:
    return (scope["jurisdiction"], scope["document_class"], scope["version"])


def build_release(
    *, release_dir: Path = REPO_ROOT / "manifests/releases", output_dir: Path | None = None
) -> Path:
    """Drop the replaced scopes from the base release and add the signed scopes."""
    payload = json.loads((release_dir / f"{BASE_RELEASE}.json").read_text(encoding="utf-8"))
    scopes = payload["scopes"]
    keys = {_key(scope) for scope in scopes}
    if len(keys) != len(scopes):
        raise ValueError("base release contains duplicate scopes")
    if len(set(ADDED)) != len(ADDED):
        raise ValueError("ADDED repeats a scope")
    already = sorted(keys & set(ADDED))
    if already:
        raise ValueError(f"base release already selects {'/'.join(already[0])}")
    absent = sorted(set(REPLACED) - keys)
    if absent:
        raise ValueError(f"base release does not select {'/'.join(absent[0])}")
    final_scopes = [dict(scope) for scope in scopes if _key(scope) not in REPLACED]
    final_scopes.extend(
        {"document_class": document_class, "jurisdiction": jurisdiction, "version": version}
        for jurisdiction, document_class, version in ADDED
    )
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
