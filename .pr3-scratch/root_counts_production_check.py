"""Read-only check of production's get_root_document_counts() (anon key, GET only).

For every (jurisdiction, doc_type) pair the RPC returns:
  rpc     - the RPC's document_count
  served  - count=exact of current_navigation_nodes roots (parent_path IS NULL)
  unserved_released - versions of the pair that some activated release signed
            (release in scope_activation_history; its signed scopes from
            release_objects) and that the pair does not serve now. Released rows
            are immutable (guard_released_scope_row_immutable), activation
            required navigation_rows > 0, and every non-empty navigation scope
            has at least one root, so each such version holds >= 1 stored root
            that 20260910120000's table-wide count includes and a served-only
            count does not.
Writes JSON to stdout.
"""

from __future__ import annotations

import json
import sys
import time
from collections import defaultdict

import httpx

from axiom_corpus.query.supabase import (
    DEFAULT_AXIOM_SUPABASE_ANON_KEY as KEY,
)
from axiom_corpus.query.supabase import (
    DEFAULT_AXIOM_SUPABASE_URL as URL,
)

HEADERS = {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Accept-Profile": "corpus"}
client = httpx.Client(timeout=60, headers=HEADERS)


def _get(path: str, params: dict | list, headers: dict | None = None) -> httpx.Response:
    # A transient 5xx (seen once on the first RPC call) is retried; anything
    # else raises.
    for attempt in range(4):
        response = client.get(f"{URL}/rest/v1/{path}", params=params, headers=headers)
        if response.status_code < 500:
            break
        time.sleep(2 * (attempt + 1))
    response.raise_for_status()
    return response


def get(path: str, params: dict | list) -> list[dict]:
    return _get(path, params).json()


def get_all(path: str, params: dict, order: str) -> list[dict]:
    rows: list[dict] = []
    while True:
        page = get(path, {**params, "order": order, "limit": "1000", "offset": str(len(rows))})
        if not page:
            return rows
        rows.extend(page)


def exact_count(path: str, params: list[tuple[str, str]]) -> int:
    response = _get(
        path, params, headers={"Prefer": "count=exact", "Range-Unit": "items", "Range": "0-0"}
    )
    return int(response.headers["content-range"].rsplit("/", 1)[1])


rpc = get("rpc/get_root_document_counts", {})
served_scopes = get_all(
    "current_release_scopes", {"select": "jurisdiction,document_class,version"}, "jurisdiction,document_class,version"
)
served_versions: dict[tuple[str, str], set[str]] = defaultdict(set)
for row in served_scopes:
    served_versions[(row["jurisdiction"], row["document_class"])].add(row["version"])

history = get_all("scope_activation_history", {"select": "release_name"}, "id")
activated = sorted({row["release_name"] for row in history})
signed_versions: dict[tuple[str, str], set[str]] = defaultdict(set)
for start in range(0, len(activated), 20):
    batch = activated[start : start + 20]
    for row in get(
        "release_objects",
        {
            "select": "release_name,scopes:release_object->content->scopes",
            "release_name": f"in.({','.join(batch)})",
        },
    ):
        for scope in row["scopes"] or []:
            signed_versions[(scope["jurisdiction"], scope["document_class"])].add(scope["version"])

pairs = []
for row in rpc:
    jurisdiction, doc_type = row["jurisdiction"], row["doc_type"]
    params = [("select", "id"), ("jurisdiction", f"eq.{jurisdiction}"), ("parent_path", "is.null")]
    if doc_type == "unknown":
        params.append(("or", "(doc_type.is.null,doc_type.eq.,doc_type.eq.unknown)"))
    else:
        params.append(("doc_type", f"eq.{doc_type}"))
    served = exact_count("current_navigation_nodes", params)
    pair = (jurisdiction, doc_type)
    unserved = sorted(signed_versions.get(pair, set()) - served_versions.get(pair, set()))
    pairs.append(
        {
            "jurisdiction": jurisdiction,
            "doc_type": doc_type,
            "rpc": int(row["document_count"]),
            "served": served,
            "unserved_released_versions": len(unserved),
        }
    )

summary = {
    "pairs": len(pairs),
    "rpc_equals_served": sum(p["rpc"] == p["served"] for p in pairs),
    "rpc_total": sum(p["rpc"] for p in pairs),
    "served_total": sum(p["served"] for p in pairs),
    "pairs_with_unserved_released_versions": sum(p["unserved_released_versions"] > 0 for p in pairs),
    "unserved_released_versions_total": sum(p["unserved_released_versions"] for p in pairs),
    "activated_releases": len(activated),
    "us": [p for p in pairs if p["jurisdiction"] == "us"],
    "mismatches": [p for p in pairs if p["rpc"] != p["served"]],
}
json.dump({"summary": summary, "pairs": pairs}, sys.stdout, indent=2)
