"""Audit the held Wyoming EOM scope against what ecom.wyo.gov serves now."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import sys
from pathlib import Path

import requests
import yaml
from bs4 import BeautifulSoup

from axiom_corpus.corpus.documents import _extract_html_blocks

WS = re.compile(r"\s+")
PURPOSE = re.compile(r"^\s*Purpose\s*:", re.IGNORECASE)
LABEL = re.compile(r"^\s*[A-Z][A-Za-z /\-]{2,60}\s*:")


def norm(text: str) -> str:
    return WS.sub(" ", (text or "").replace(" ", " ")).strip()


def held_text(rows: list[dict]) -> str:
    parts: list[str] = []
    for row in sorted(rows, key=lambda r: (r["kind"] != "document", int(r["ordinal"]))):
        for field in ("heading", "body"):
            value = row.get(field)
            if value:
                parts.append(norm(value))
    return " ".join(parts)


def live_blocks(content: bytes, url: str, extraction: dict):
    blocks = _extract_html_blocks(
        content, source_url=url, fallback_title=None, extraction=extraction
    )
    return blocks


def root_text(content: bytes, selector: str) -> str:
    soup = BeautifulSoup(content, "html.parser")
    root = soup.select_one(selector)
    return norm(root.get_text(" ", strip=True)) if root else ""


def one(doc: dict, provisions: dict[str, list[dict]], session: requests.Session, base: Path):
    cp = doc["citation_path"]
    url = doc["source_url"]
    extraction = doc.get("extraction") or {}
    out: dict[str, object] = {"citation_path": cp, "source_url": url}

    rows = provisions.get(cp, [])
    out["held_rows"] = len(rows)
    held = held_text(rows)
    out["held_chars"] = len(held)

    try:
        resp = session.get(url, timeout=60)
        body = resp.content
    except Exception as exc:  # noqa: BLE001
        out["reachable"] = False
        out["error"] = str(exc)[:200]
        return out
    out["http_status"] = resp.status_code
    out["live_bytes"] = len(body)
    # Reachability is judged by the response body, not the status line.
    out["reachable"] = bool(root_text(body, extraction.get("html_content_selector", "body")))
    if not out["reachable"]:
        return out

    try:
        blocks = live_blocks(body, url, extraction)
    except Exception as exc:  # noqa: BLE001
        out["extract_error"] = str(exc)[:200]
        return out

    live_headings = [norm(b.heading or "") for b in blocks]
    live_bodies = [norm(b.body or "") for b in blocks]
    out["live_blocks"] = len(blocks)
    out["live_chars"] = len(" ".join(h + " " + b for h, b in zip(live_headings, live_bodies, strict=True)))

    purposes = [h for h in live_headings if PURPOSE.match(h)]
    out["live_purpose"] = purposes[0] if purposes else None
    out["purpose_in_corpus"] = (
        all(norm(p) in held for p in purposes) if purposes else None
    )

    labels = [h for h in live_headings if h and LABEL.match(h)]
    out["live_labels"] = len(labels)
    out["labels_missing"] = [h for h in labels if norm(h) not in held]

    # Full-text fidelity: every live text node must appear in the held text.
    live_root = root_text(body, extraction.get("html_content_selector", "body"))
    missing_words = 0
    for chunk in live_headings + live_bodies:
        if chunk and chunk not in held:
            missing_words += len(chunk.split())
    out["missing_chunk_words"] = missing_words
    out["text_faithful"] = missing_words == 0
    out["live_root_chars"] = len(live_root)

    retained = base / "sources" / doc["_scope"] / "official-documents" / f"{doc['source_id']}.html"
    out["retained_exists"] = retained.exists()
    if retained.exists():
        held_bytes = retained.read_bytes()
        out["retained_bytes"] = len(held_bytes)
        out["byte_identical"] = held_bytes == body
        try:
            held_blocks = live_blocks(held_bytes, url, extraction)
            out["retained_blocks"] = len(held_blocks)
            retained_text = " ".join(
                norm(b.heading or "") + " " + norm(b.body or "") for b in held_blocks
            )
            out["retained_vs_live_text_identical"] = norm(retained_text) == norm(
                " ".join(h + " " + b for h, b in zip(live_headings, live_bodies, strict=True))
            )
        except Exception as exc:  # noqa: BLE001
            out["retained_extract_error"] = str(exc)[:200]
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--base", required=True)
    ap.add_argument("--scope", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    manifest = yaml.safe_load(Path(args.manifest).read_text())
    docs = manifest["documents"]
    for doc in docs:
        doc["_scope"] = args.scope

    base = Path(args.base)
    prov_path = base / "provisions" / f"{args.scope}.jsonl"
    provisions: dict[str, list[dict]] = {}
    for line in prov_path.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        root = row["citation_path"].split("/block-")[0]
        provisions.setdefault(root, []).append(row)

    session = requests.Session()
    session.headers["User-Agent"] = "axiom-corpus-ingest/audit"
    results: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(one, d, provisions, session, base) for d in docs]
        for fut in concurrent.futures.as_completed(futures):
            results.append(fut.result())

    results.sort(key=lambda r: r["citation_path"])
    Path(args.out).write_text(json.dumps(results, indent=2) + "\n")

    reachable = [r for r in results if r.get("reachable")]
    faithful = [r for r in reachable if r.get("text_faithful")]
    lost_purpose = [r for r in reachable if r.get("purpose_in_corpus") is False]
    no_purpose = [r for r in reachable if r.get("live_purpose") is None]
    lost_labels = [r for r in reachable if r.get("labels_missing")]
    byte_same = [r for r in reachable if r.get("byte_identical")]
    retained_same_text = [r for r in reachable if r.get("retained_vs_live_text_identical")]
    print(f"documents          {len(results)}")
    print(f"reachable          {len(reachable)}")
    print(f"text faithful      {len(faithful)}")
    print(f"lose Purpose       {len(lost_purpose)}")
    print(f"no live Purpose    {len(no_purpose)}")
    print(f"lose field labels  {len(lost_labels)}")
    print(f"byte-identical     {len(byte_same)}")
    print(f"retained==live txt {len(retained_same_text)}")
    for r in lost_purpose[:5]:
        print("  PURPOSE LOST", r["citation_path"], r["live_purpose"])
    for r in lost_labels[:5]:
        print("  LABELS LOST", r["citation_path"], r["labels_missing"][:3])
    return 0


if __name__ == "__main__":
    sys.exit(main())
