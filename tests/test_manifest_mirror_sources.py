"""No new manifest may take regulation text from the Cornell LII mirror.

Six SNAP manifests from May 2026 capture state rules from
``law.cornell.edu/regulations``. The shared HTML extractor keeps that site's
page furniture ("State Regulations", "Compare", the quarterly-update notice)
and drops a rule's lists, so the rows hold part of a rule
(docs/ingest-runs/2026-11-11-snap-official-rules-al-fl-tn.md). The six are
frozen here; a rule's text comes from its official publisher.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

import yaml

MANIFESTS = Path(__file__).resolve().parents[1] / "manifests"
MIRROR_HOST = "law.cornell.edu"
# Legacy captures. Remove a name when its manifest is retired; never add one.
LEGACY_MIRROR_MANIFESTS = frozenset(
    {
        "us-al-snap-primary-policy.yaml",
        "us-fl-snap-primary-policy.yaml",
        "us-ma-snap-primary-policy.yaml",
        "us-nc-snap-primary-policy.yaml",
        "us-sc-snap-primary-policy.yaml",
        "us-tn-snap-primary-policy.yaml",
    }
)
OFFICIAL_SUCCESSORS = {
    "us-al-snap-admin-code-660-4.yaml": "admincode.legislature.state.al.us",
    "us-fl-snap-fac-65a-1-official.yaml": "www.flrules.org",
    "us-tn-snap-rules-1240-01-chapters.yaml": "publications.tnsosfiles.com",
}


def _documents(path: Path) -> list[dict]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return []
    if not isinstance(data, dict) or not isinstance(data.get("documents"), list):
        return []
    return [doc for doc in data["documents"] if isinstance(doc, dict)]


def _text_hosts(doc: dict) -> set[str]:
    return {
        urlparse(str(doc[key])).netloc.lower()
        for key in ("source_url", "download_url")
        if doc.get(key)
    }


def _takes_text_from_mirror(doc: dict) -> bool:
    return any(host == MIRROR_HOST or host.endswith("." + MIRROR_HOST) for host in _text_hosts(doc))


def test_only_the_legacy_manifests_take_text_from_the_mirror() -> None:
    mirror_manifests = {
        path.name
        for path in sorted(MANIFESTS.glob("*.yaml"))
        if any(_takes_text_from_mirror(doc) for doc in _documents(path))
    }

    assert mirror_manifests <= LEGACY_MIRROR_MANIFESTS, sorted(
        mirror_manifests - LEGACY_MIRROR_MANIFESTS
    )


def test_official_successors_read_only_their_publisher() -> None:
    for name, host in OFFICIAL_SUCCESSORS.items():
        documents = _documents(MANIFESTS / name)

        assert documents, name
        for doc in documents:
            assert _text_hosts(doc) == {host}, (name, doc["source_id"])
            assert doc["metadata"]["primary_source"] is True, (name, doc["source_id"])


def test_florida_successors_keep_the_mirror_rows_citation_paths() -> None:
    legacy_paths = {
        doc["citation_path"] for doc in _documents(MANIFESTS / "us-fl-snap-primary-policy.yaml")
    }
    successor_paths = [
        doc["citation_path"] for doc in _documents(MANIFESTS / "us-fl-snap-fac-65a-1-official.yaml")
    ]

    assert len(successor_paths) == len(set(successor_paths)) == 31
    assert set(successor_paths) <= legacy_paths
