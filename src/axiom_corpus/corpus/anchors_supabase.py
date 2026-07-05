"""Supabase loader for the derived ``corpus.provision_anchors`` table.

Mirrors ``load_provisions_to_supabase`` but for the annotation layer. The table
is DERIVED and rebuildable, so this is a batch upsert keyed on the anchor's
``citation_path`` primary key. Applying to Supabase is *optional* — the
committed DDL + JSONL + tests are the deliverable — but the loader exists so the
layer can be published the same way provisions are.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import TextIO

from axiom_corpus.corpus.anchors import ProvisionAnchor, anchor_to_supabase_row
from axiom_corpus.corpus.supabase import (
    DEFAULT_AXIOM_SUPABASE_URL,
    USER_AGENT,
    _rest_url,
)

_ANCHORS_ENDPOINT = "provision_anchors"


@dataclass
class AnchorLoadReport:
    rows_total: int
    rows_loaded: int
    chunk_count: int
    dry_run: bool

    def to_mapping(self) -> dict[str, object]:
        return {
            "rows_total": self.rows_total,
            "rows_loaded": self.rows_loaded,
            "chunk_count": self.chunk_count,
            "dry_run": self.dry_run,
        }


def _chunked(
    rows: Iterable[dict[str, object]], size: int
) -> Iterator[list[dict[str, object]]]:
    chunk: list[dict[str, object]] = []
    for row in rows:
        chunk.append(row)
        if len(chunk) >= size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


def upsert_anchor_rows(
    rows: list[dict[str, object]],
    *,
    service_key: str,
    rest_url: str,
) -> None:
    """Upsert anchor rows on the ``citation_path`` primary key."""
    if not rows:
        return
    req = urllib.request.Request(
        f"{rest_url}/{_ANCHORS_ENDPOINT}?on_conflict=citation_path",
        data=json.dumps(rows).encode("utf-8"),
        headers={
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal",
            "Content-Profile": "corpus",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            resp.read()
    except urllib.error.HTTPError as exc:  # pragma: no cover - network path
        body = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"anchor upsert failed {exc.code}: {body}") from exc


def load_anchors_to_supabase(
    anchors: Iterable[ProvisionAnchor],
    *,
    service_key: str,
    supabase_url: str = DEFAULT_AXIOM_SUPABASE_URL,
    chunk_size: int = 500,
    dry_run: bool = False,
    progress_stream: TextIO | None = None,
) -> AnchorLoadReport:
    """Upsert derived anchor rows into ``corpus.provision_anchors``."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    rest_url = _rest_url(supabase_url)
    rows_loaded = 0
    chunk_count = 0
    row_iter = (anchor_to_supabase_row(anchor) for anchor in anchors)
    for chunk in _chunked(row_iter, chunk_size):
        chunk_count += 1
        if not dry_run:
            upsert_anchor_rows(chunk, service_key=service_key, rest_url=rest_url)
        rows_loaded += len(chunk)
        if progress_stream is not None:
            print(
                f"processed anchor chunk {chunk_count} ({rows_loaded} rows)",
                file=progress_stream,
                flush=True,
            )
    return AnchorLoadReport(
        rows_total=rows_loaded,
        rows_loaded=0 if dry_run else rows_loaded,
        chunk_count=chunk_count,
        dry_run=dry_run,
    )
