import json
from pathlib import Path

from scripts.audit_release_scope_self_containment import find_scope_residuals


def test_cross_scope_parent_does_not_satisfy_staging_boundary(tmp_path: Path) -> None:
    base = tmp_path / "corpus"
    provisions = base / "provisions" / "us" / "regulation"
    provisions.mkdir(parents=True)
    parent_version = "42-435-complete"
    child_version = "community-engagement"
    (provisions / f"{parent_version}.jsonl").write_text(
        json.dumps({"citation_path": "us/regulation/42/435"}) + "\n"
    )
    (provisions / f"{child_version}.jsonl").write_text(
        json.dumps(
            {
                "citation_path": "us/regulation/42/435/550",
                "parent_citation_path": "us/regulation/42/435",
            }
        )
        + "\n"
    )
    release = {
        "scopes": [
            {"jurisdiction": "us", "document_class": "regulation", "version": parent_version},
            {"jurisdiction": "us", "document_class": "regulation", "version": child_version},
        ]
    }

    assert find_scope_residuals(release, base) == [
        {
            "jurisdiction": "us",
            "document_class": "regulation",
            "version": child_version,
            "citation_path": "us/regulation/42/435/550",
            "missing_parent_citation_path": "us/regulation/42/435",
        }
    ]
