from __future__ import annotations

from pathlib import Path

from scripts.build_nc_ty2026_statutes import build_records

REPO = Path(__file__).parents[1]


def test_nc_ty2026_successor_applies_enacted_temporal_overlays() -> None:
    manifest, inventory, records = build_records(
        REPO / "data/corpus",
        REPO / "manifests/us-nc-ty2026-income-tax-core.yaml",
    )

    assert manifest["liability_status"] == "deferred_pending_final_d_400"
    assert len(inventory) == len(records) == 4
    by_path = {record.citation_path: record for record in records}

    deductions = by_path["us-nc/statute/105/105-153.5"]
    assert "adjusted gross income, as modified in G.S. 105-153.5" in deductions.body
    assert "The Business Recovery Grant Program" not in deductions.body
    assert "deduction for wagering losses under section 165(d)" in deductions.body
    assert "January 1, 2031 - see note) Certain Real Property Donations" in deductions.body

    rate = by_path["us-nc/statute/105/105-153.7"]
    assert "In 2026 3.99%" in rate.body
    assert "In 2027, 2028, and 2029 3.49%" in rate.body
    assert "one-fourth percentage point (0.25%)" in rate.body
    assert "FY 2025-2026" not in rate.body
    assert "FY 2033-2034 $40,258,000,000 In 2035" in rate.body

    credit = by_path["us-nc/statute/105/105-153.9"]
    assert "on or after January 1, 2023" in credit.body
    assert "beginning before January 1, 2023" not in credit.body
    selection = (credit.metadata or {})["version_selection"]
    assert len(selection["renditions"]) == 2
    assert sum(row["selected"] for row in selection["renditions"]) == 1

    donation = by_path["us-nc/statute/105/105-153.11"]
    assert donation.body.count("January 1, 2031") == 3
    assert "G.S. 105-130.34A(i)." in donation.body
    assert "or pass-through entity. individual." not in donation.body
    assert "in accordance with subsection ( l ) of this section." in donation.body
    donation_components = (donation.metadata or {})["component_sources"]
    assert next(
        component
        for component in donation_components
        if component["source_id"] == "sl-2026-11"
    )["sections"] == ["24(a)", "24(b)"]

    for record in records:
        assert record.id is not None
        assert record.version == manifest["version"]
        assert (record.metadata or {})["liability_status"] == (
            "deferred_pending_final_d_400"
        )
        assert (record.metadata or {})["component_sources"]
        for component in (record.metadata or {})["component_sources"][1:]:
            assert component["effective"]
