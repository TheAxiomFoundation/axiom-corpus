"""Build one official-document manifest per state and program for the approved Medicaid and
CHIP state plan material that CMS posts on medicaid.gov, and add a state-plan row to the
Medicaid and CHIP agent queues.

What CMS actually hosts (discovery 2026-09-13, see docs/ingest-runs/2026-09-13-cms-state-plans.md):
medicaid.gov does not post a compiled Medicaid state plan per state. The "Medicaid State Plan
Amendments" search (/medicaid/medicaid-state-plan-amendments, 16,727 records) and the "CHIP State
Plan Amendments" search (/chip/state-program-information/chip-spa, 1,007 records) list every
approved SPA with its approval package PDF (approval letter, CMS-179, the approved state plan
pages); the CHIP search additionally carries one CMS-compiled "Current State Plan" PDF plus a
factsheet per state (topic "State Plan Factsheet", compiled 2010-2011). Both searches tag records
with topics. This generator takes, per state:

* every page of the state's SPA index (all topics) as an HTML document (`spa-index/pNN`), which
  is the SPA record the closure schema's M-SS-SPA / 435.10 / C-SS-STATE-PLAN elements need;
* the PDFs of every record tagged with an eligibility-bearing topic (TAKE_TOPICS), which carry
  the approved attachment 2.2-A, 2.6-A supplement, 4.18 and MACPro S-series pages (Medicaid) and
  the CHIP plan sections 4, 5, 6 and 8 pages;
* for CHIP, the compiled Current State Plan and factsheet PDFs.

Records tagged only with other topics (reimbursement, drugs, managed care, ...) and untagged
records are inventoried per state in the queue row's `index_families` and not taken.

medicaid.gov answers plain clients HTTP 403 (Akamai "Access Denied") and answers curl_cffi
browser impersonation; every document therefore carries `request: browser_impersonation_direct`.
Nothing is worked around: medicaid.gov is the publisher, no mirror is used.

    uv run python scripts/build_cms_state_plan_manifests.py --program medicaid --only us-wy
    uv run python scripts/build_cms_state_plan_manifests.py --program all --cache /path/to/listing-cache
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
SOURCE_AS_OF = "2026-09-13"
PUBLISHER = "https://www.medicaid.gov"
PROGRAMS: dict[str, dict[str, Any]] = {
    "medicaid": {
        "version": "2026-09-13-medicaid-state-plan",
        "queue": ROOT / "manifests" / "medicaid-agent-queue.yaml",
        "index": f"{PUBLISHER}/medicaid/medicaid-state-plan-amendments",
        "path_root": "medicaid-state-plan",
        "stem": "medicaid-state-plan",
        "program": "MEDICAID",
        "label": "Medicaid",
        # Topics whose approval packages carry approved eligibility, cost-sharing or plan-structure
        # pages (Medicaid state plan attachment 2.2-A, 2.6-A and supplements, 4.18-A to 4.18-F,
        # sections 2.1-2.6, 4.22 and the MACPro S-series pages).
        "take_topics": {
            "Eligibility", "Cost Sharing", "Premiums", "Current State Plan", "Blind Disabled",
            "Medicaid Expansion", "Affordable Care Act", "Individual CoPayments or Insurance Payments",
            "Outreach & Enrollment", "State Plan Factsheet", "Third Party Liability",
            "Children's Health Insurance Program",
        },
    },
    "chip": {
        "version": "2026-09-13-chip-state-plan",
        "queue": ROOT / "manifests" / "chip-agent-queue.yaml",
        "index": f"{PUBLISHER}/chip/state-program-information/chip-spa",
        "path_root": "chip-state-plan",
        "stem": "chip-state-plan",
        "program": "CHIP",
        "label": "CHIP",
        # CHIP state plan sections 4 (eligibility), 5 (outreach and coordination), 6 (coverage) and
        # 8 (cost sharing), plus the compiled plan records ("State Plan Factsheet").
        "take_topics": {
            "Eligibility", "Cost Sharing", "Premiums", "Current State Plan", "State Plan Factsheet",
            "Enrollment", "Outreach & Enrollment", "Expansion", "MCHIP Program", "Benefits", "Dental",
        },
    },
}
STATES = {
    "us-al": "Alabama", "us-ak": "Alaska", "us-az": "Arizona", "us-ar": "Arkansas", "us-ca": "California",
    "us-co": "Colorado", "us-ct": "Connecticut", "us-de": "Delaware", "us-dc": "District of Columbia",
    "us-fl": "Florida", "us-ga": "Georgia", "us-hi": "Hawaii", "us-id": "Idaho", "us-il": "Illinois",
    "us-in": "Indiana", "us-ia": "Iowa", "us-ks": "Kansas", "us-ky": "Kentucky", "us-la": "Louisiana",
    "us-me": "Maine", "us-md": "Maryland", "us-ma": "Massachusetts", "us-mi": "Michigan", "us-mn": "Minnesota",
    "us-ms": "Mississippi", "us-mo": "Missouri", "us-mt": "Montana", "us-ne": "Nebraska", "us-nv": "Nevada",
    "us-nh": "New Hampshire", "us-nj": "New Jersey", "us-nm": "New Mexico", "us-ny": "New York",
    "us-nc": "North Carolina", "us-nd": "North Dakota", "us-oh": "Ohio", "us-ok": "Oklahoma", "us-or": "Oregon",
    "us-pa": "Pennsylvania", "us-ri": "Rhode Island", "us-sc": "South Carolina", "us-sd": "South Dakota",
    "us-tn": "Tennessee", "us-tx": "Texas", "us-ut": "Utah", "us-vt": "Vermont", "us-va": "Virginia",
    "us-wa": "Washington", "us-wv": "West Virginia", "us-wi": "Wisconsin", "us-wy": "Wyoming",
}
IMPERSONATE = "chrome120"
PAGE_SIZE = 100
INVENTORY = ROOT / "docs" / "ingest-runs" / "2026-09-13-cms-state-plans-inventory.json"

_RECORD_RE = re.compile(
    r'aria-controls="node-(\d+)"\s*>\s*Transmittal Number:\s*([^<]+?)\s*</button>.*?'
    r'<div\s+id="node-\1".*?<div class="usa-accordion-content-wrapper">(.*?)'
    r"</div>\s*</div>\s*</div>\s*</div>\s*</div>\s*</div>",
    re.S,
)
_TOTAL_RE = re.compile(r"Displaying\s*<strong>\s*(\d+)\s*-\s*(\d+)\s*</strong>\s*of\s*<strong>(\d+)</strong>")
_SELECT_RE = re.compile(r"<select[^>]*>.*?</select>", re.S)
_OPTION_RE = re.compile(r'<option[^>]*value="([^"]*)"[^>]*>([^<]*)')
_LINK_RE = re.compile(r'<li>\s*<a href="([^"]+)">\s*(.*?)\s*</a>\s*</li>', re.S)
_TOPIC_RE = re.compile(r'<span class="usa-chip">([^<]+)</span>')
_ROW_RE = re.compile(r'<div class="grid-row">(.*?)</div>\s*</div>', re.S)


class FetchError(RuntimeError):
    def __init__(self, url: str, status: int | None, size: int, seconds: float, detail: str):
        super().__init__(f"{url}: HTTP {status} ({size} bytes, {seconds:.1f}s) {detail}")
        self.url, self.status, self.size, self.seconds, self.detail = url, status, size, seconds, detail


def fetch(url: str) -> tuple[str, float]:
    """GET through curl_cffi browser impersonation (plain clients get Akamai 403). TLS verified."""
    from curl_cffi import requests as curl_requests

    start = time.time()
    last: tuple[int | None, int, str] = (None, 0, "")
    for attempt in range(4):
        try:
            resp = curl_requests.get(url, impersonate=IMPERSONATE, timeout=120, allow_redirects=True)
        except Exception as exc:  # noqa: BLE001 - transient network errors are retried, then reported
            last = (None, 0, repr(exc)[:200])
        else:
            if resp.status_code == 200:
                return resp.text, time.time() - start
            last = (resp.status_code, len(resp.content), (resp.text or "")[:120].replace("\n", " "))
            if resp.status_code not in (429, 500, 502, 503, 504):
                break
        time.sleep(5 * (attempt + 1))
    raise FetchError(url, last[0], last[1], time.time() - start, last[2])


def clean(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def slug(value: str, limit: int = 80) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:limit].strip("-")


def iso_date(text: str | None) -> str | None:
    if not text:
        return None
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%m/%d/%Y", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(text.strip(), fmt).date().isoformat()
        except ValueError:
            continue
    return None


def parse_filters(page: str) -> tuple[dict[str, str], dict[str, str]]:
    states: dict[str, str] = {}
    topics: dict[str, str] = {}
    for select in _SELECT_RE.findall(page):
        name = re.search(r'name="([^"]+)"', select)
        options = {html.unescape(label).strip(): value for value, label in _OPTION_RE.findall(select)}
        if name and "field_state" in name.group(1):
            states = options
        elif name and "field_topics" in name.group(1):
            topics = options
    return states, topics


def parse_records(page: str) -> list[dict[str, Any]]:
    records = []
    for nid, transmittal, inner in _RECORD_RE.findall(page):
        rows = _ROW_RE.findall(inner)
        approval = re.search(r"Approval Date:</b>\s*([^<]+)", inner)
        effective = re.search(r"Effective Date:</b>\s*([^<]+)", inner)
        records.append({
            "nid": nid,
            "transmittal": transmittal.strip(),
            "state": clean(rows[0]) if rows else None,
            "summary": clean(rows[1]) if len(rows) > 1 else "",
            "approval_date": approval.group(1).strip() if approval else None,
            "effective_date": effective.group(1).strip() if effective else None,
            "links": [(html.unescape(href), clean(label)) for href, label in _LINK_RE.findall(inner)],
            "topics": [html.unescape(topic).strip() for topic in _TOPIC_RE.findall(inner)],
        })
    return records


def listing_url(program: str, state_id: str, page: int, sort: str = "field_approval_date:desc") -> str:
    return (f"{PROGRAMS[program]['index']}?filter%5Bfield_state%5D%5Bin%5D%5B%5D={state_id}"
            f"&limit={PAGE_SIZE}&sort={sort.replace(':', '%3A')}&page={page}")


def crawl_listing(program: str, jur: str, state_id: str, cache: Path | None) -> dict[str, Any]:
    """All SPA records of one state, page by page (cached as JSON when --cache is given)."""
    cache_file = cache / f"{program}-{jur}.json" if cache else None
    if cache_file and cache_file.exists():
        return json.loads(cache_file.read_text())
    # The index is paged by a Solr sort; ties on the sort key can move a record across page boundaries
    # between requests, so records are de-duplicated by node id and a shortfall is filled from a second
    # pass with the alternate sort (title, unique per record) before the count is checked.
    by_nid: dict[str, dict[str, Any]] = {}
    pages: list[dict[str, Any]] = []
    seconds = 0.0
    total = 0
    for sort in ("field_approval_date:desc", "title_sort:asc"):
        page = 0
        while True:
            url = listing_url(program, state_id, page, sort=sort)
            text, secs = fetch(url)
            seconds += secs
            match = _TOTAL_RE.search(text)
            total = int(match.group(3)) if match else 0
            found = parse_records(text)
            if sort == "field_approval_date:desc":
                pages.append({"page": page, "url": url, "records": len(found), "bytes": len(text), "seconds": round(secs, 2)})
            for record in found:
                by_nid.setdefault(record["nid"], record)
            page += 1
            if not found or page * PAGE_SIZE >= total:
                break
        if len(by_nid) == total:
            break
    records = list(by_nid.values())
    if len(records) != total:
        raise RuntimeError(f"{program} {jur}: parsed {len(records)} distinct records but the index says {total}")
    result = {"program": program, "jurisdiction": jur, "state_id": state_id, "total": total, "pages": pages,
              "records": records, "listing_seconds": round(seconds, 2), "fetched_at": dt.datetime.now(dt.UTC).isoformat()}
    if cache_file:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(result, indent=1))
    return result


LABEL_SUBTYPES = {
    "approval-document": "spa_approval_package",
    "approval-package": "spa_approval_package",
    "form-cms-179": "spa_cms_179_form",
    "attachment": "spa_attachment",
    "current-state-plan": "cms_compiled_state_plan",
    "factsheet": "cms_state_plan_factsheet",
    "final-approved-state-plan": "cms_compiled_state_plan",
}


def is_compiled_plan(record: dict[str, Any]) -> bool:
    return "State Plan Factsheet" in record["topics"] and re.fullmatch(r"[A-Z]{2}", record["transmittal"]) is not None


def build_documents(program: str, jur: str, listing: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    spec = PROGRAMS[program]
    name = STATES[jur]
    root = f"{jur}/policy/cms/{spec['path_root']}"
    request = {"browser_impersonation_direct": True}
    common_meta = {
        "primary_source": True,
        "source_authority": "Centers for Medicare & Medicaid Services (medicaid.gov)",
        "program": spec["program"],
        "state": name,
        "source_discovery_group": f"{jur}/policy/cms-{spec['stem']}",
        "discovered_via": f"manual-review:{program}-agent-queue state-plan row; CMS SPA index {spec['index']}",
        "publisher_note": "medicaid.gov answers plain clients HTTP 403 (Akamai); fetched with curl_cffi browser impersonation, TLS verified",
    }
    docs: list[dict[str, Any]] = []
    n_pages = len(listing["pages"])
    for page in listing["pages"]:
        number = page["page"] + 1
        docs.append({
            "source_id": f"{jur}-cms-{spec['stem']}-spa-index-p{number:02d}",
            "jurisdiction": jur,
            "document_class": "policy",
            "title": f"{name} {spec['label']} state plan amendments on medicaid.gov: SPA index page {number} of {n_pages}",
            "source_url": page["url"],
            "source_format": "html",
            "source_as_of": SOURCE_AS_OF,
            "expression_date": SOURCE_AS_OF,
            "citation_path": f"{root}/spa-index/p{number:02d}",
            "request": request,
            "extraction": {"html_content_selector": ".medicaid-solr-searches-results",
                           "html_drop_selectors": [".mailto", "a.mailto"]},
            "metadata": {**common_meta, "document_subtype": "cms_spa_index_page", "index_page": number,
                         "index_pages": n_pages, "index_records_on_page": page["records"],
                         "index_records_total": listing["total"]},
        })
    families: dict[str, dict[str, int]] = {}
    taken_records: list[dict[str, Any]] = []
    used_paths: set[str] = set()
    for record in listing["records"]:
        topics = record["topics"] or ["(untagged)"]
        take = is_compiled_plan(record) or bool(set(record["topics"]) & spec["take_topics"])
        for topic in topics:
            fam = families.setdefault(f"spa_topic:{topic}", {"found": 0, "taken": 0})
            fam["found"] += 1
            if take:
                fam["taken"] += 1
        if not take:
            continue
        taken_records.append({k: record[k] for k in ("nid", "transmittal", "approval_date", "effective_date", "topics", "links")})
        expression = iso_date(record["effective_date"]) or iso_date(record["approval_date"]) or SOURCE_AS_OF
        tn_slug = slug(record["transmittal"])
        base = f"{root}/compiled" if is_compiled_plan(record) else f"{root}/spa/{tn_slug}"
        for href, label in record["links"]:
            label_slug = slug(label) or "document"
            path = f"{base}/{label_slug}"
            k = 2
            while path in used_paths:
                path = f"{base}/{label_slug}-{k}"
                k += 1
            used_paths.add(path)
            url = href if href.startswith("http") else PUBLISHER + href
            fmt = "pdf" if url.lower().endswith(".pdf") else "html"
            kind = "compiled state plan" if is_compiled_plan(record) else f"SPA {record['transmittal']}"
            docs.append({
                "source_id": f"{jur}-cms-{spec['stem']}-" + slug(path.removeprefix(root + "/").replace("/", "-")),
                "jurisdiction": jur,
                "document_class": "policy",
                "title": f"{name} {spec['label']} {kind}: {label} (approved {record['approval_date'] or 'n/a'}, effective {record['effective_date'] or 'n/a'})",
                "source_url": url,
                "source_format": fmt,
                "source_as_of": SOURCE_AS_OF,
                "expression_date": expression,
                "citation_path": path,
                "request": request,
                "extraction": {"ocr": True} if fmt == "pdf" else {},
                "metadata": {
                    **common_meta,
                    "document_subtype": LABEL_SUBTYPES.get(label_slug, "spa_document"),
                    "transmittal_number": record["transmittal"],
                    "cms_node_id": record["nid"],
                    "cms_record_url": f"{spec['index']}?filter%5Bnid%5D%5Beq%5D={record['nid']}",
                    "approval_date": iso_date(record["approval_date"]),
                    "effective_date": iso_date(record["effective_date"]),
                    "summary": record["summary"],
                    "topics": record["topics"],
                    "link_label": label,
                },
            })
    paths = [d["citation_path"] for d in docs]
    assert len(set(paths)) == len(paths), f"{jur}: duplicate citation paths"
    info = {
        "index_url": listing_url(program, listing["state_id"], 0),
        "records": listing["total"],
        "index_pages": n_pages,
        "taken_records": len(taken_records),
        "documents": len(docs),
        "pdf_documents": sum(1 for d in docs if d["source_format"] == "pdf"),
        "families": {"spa_index_page": {"found": n_pages, "taken": n_pages}, **dict(sorted(families.items()))},
        "listing_seconds": listing["listing_seconds"],
        "taken": taken_records,
    }
    return docs, info


def queue_note(program: str, info: dict[str, Any]) -> str:
    spec = PROGRAMS[program]
    topics = sorted(spec["take_topics"])
    return (f"CMS state plan row (2026-09-13): medicaid.gov posts no compiled {spec['label']} state plan; the CMS SPA index "
            f"lists {info['records']} approved {spec['label']} SPAs for the state. Taken: all {info['index_pages']} index page(s) "
            f"(every SPA record with transmittal number, summary, approval and effective dates, topics, links) and the "
            f"{info['pdf_documents']} PDF(s) of the {info['taken_records']} records tagged with an eligibility-bearing topic "
            f"({', '.join(topics)}); records tagged only with other topics and untagged records are inventoried in index_families "
            f"and not taken. Approval packages carry the approved state plan pages (attachment 2.2-A, 2.6-A supplements, "
            f"4.18, MACPro S-series pages for Medicaid; sections 4-9 pages for CHIP). medicaid.gov answers plain clients HTTP 403 "
            f"(Akamai) and answers curl_cffi browser impersonation (request: browser_impersonation_direct); TLS verified, no mirror. "
            f"Generator: scripts/build_cms_state_plan_manifests.py --program {program}.")


def blocked_note(program: str, exc: FetchError) -> str:
    return (f"CMS state plan row (2026-09-13): blocked at the publisher: {exc.url} answered HTTP {exc.status} "
            f"({exc.size} bytes, {exc.seconds:.1f} s) {exc.detail!r} to curl_cffi {IMPERSONATE} impersonation after retries; "
            f"no workaround attempted. Generator: scripts/build_cms_state_plan_manifests.py --program {program}.")


def update_queue(program: str, new_rows: dict[str, dict[str, Any]]) -> dict[str, int]:
    """Insert or replace the jurisdiction's CMS state-plan row right after its first row."""
    spec = PROGRAMS[program]
    queue = yaml.safe_load(spec["queue"].read_text())
    states: list[dict[str, Any]] = []
    seen_first: set[str] = set()
    for row in queue["states"]:
        if row.get("family") == "cms_state_plan" and row["jurisdiction"] in new_rows:
            continue  # replaced below
        states.append(row)
    # place each new row after the last existing row of its jurisdiction (or at the end)
    for jur, row in new_rows.items():
        idx = max((i for i, r in enumerate(states) if r["jurisdiction"] == jur), default=None)
        if idx is None:
            states.append(row)
        else:
            states.insert(idx + 1, row)
        seen_first.add(jur)
    queue["states"] = states
    queue["status_counts"] = {}
    for row in states:
        queue["status_counts"][row["queue_status"]] = queue["status_counts"].get(row["queue_status"], 0) + 1
    note = (f"CMS state plan family (2026-09-13): one `family: cms_state_plan` row per state for the medicaid.gov SPA index and "
            f"eligibility-bearing approval packages, version {spec['version']}, document_class policy, citation root "
            f"us-xx/policy/cms/{spec['path_root']}. Generator: scripts/build_cms_state_plan_manifests.py --program {program}.")
    notes = queue.setdefault("policy", {}).setdefault("notes", [])
    if note not in notes:
        notes.append(note)
    queue["queue_status"] = "in_progress"
    spec["queue"].write_text(yaml.safe_dump(queue, sort_keys=False, allow_unicode=True, width=120))
    return queue["status_counts"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--program", choices=["medicaid", "chip", "all"], default="all")
    parser.add_argument("--only", action="append", default=[], metavar="JURISDICTION")
    parser.add_argument("--cache", type=Path, default=None, help="directory of cached listing JSON (reused when present)")
    args = parser.parse_args()
    programs = ["medicaid", "chip"] if args.program == "all" else [args.program]
    jurisdictions = args.only or sorted(STATES)
    inventory = json.loads(INVENTORY.read_text()) if INVENTORY.exists() else {}
    for program in programs:
        spec = PROGRAMS[program]
        landing, _ = fetch(spec["index"])
        state_ids, _topics = parse_filters(landing)
        rows: dict[str, dict[str, Any]] = {}
        for jur in jurisdictions:
            name = STATES[jur]
            state_id = state_ids.get(name)
            if state_id is None:
                print(f"{program} {jur}: {name!r} not in the CMS state filter", file=sys.stderr)
                return 1
            stem = f"{jur}-{spec['stem']}"
            row: dict[str, Any] = {
                "jurisdiction": jur, "name": name, "family": "cms_state_plan", "lead_counts": {}, "candidate_sources": [],
                "target_manifest": f"manifests/{stem}.yaml",
                "target_scope": {"jurisdiction": jur, "document_class": "policy", "version": spec["version"]},
            }
            try:
                listing = crawl_listing(program, jur, state_id, args.cache)
                docs, info = build_documents(program, jur, listing)
            except FetchError as exc:
                print(f"{program} {jur}: BLOCKED {exc}", file=sys.stderr)
                row.update({"queue_status": "blocked_primary_source", "source_kind": "official_publisher_blocked",
                            "primary_source_url": listing_url(program, state_id, 0), "index_url": listing_url(program, state_id, 0),
                            "index_document_count": None, "taken_count": 0, "notes": blocked_note(program, exc)})
                rows[jur] = row
                inventory[f"{program}/{jur}"] = {"blocked": str(exc)}
                continue
            (ROOT / "manifests" / f"{stem}.yaml").write_text(
                yaml.safe_dump({"version": spec["version"], "documents": docs}, sort_keys=False, allow_unicode=True, width=120))
            row.update({
                "queue_status": "agent_ready", "source_kind": "cms_posted_state_plan_amendments",
                "primary_source_url": info["index_url"], "index_url": info["index_url"],
                "index_document_count": info["records"] + info["index_pages"], "taken_count": info["documents"],
                "index_families": info["families"], "notes": queue_note(program, info),
            })
            rows[jur] = row
            inventory[f"{program}/{jur}"] = dict(info)
            print(f"{program} {jur}: {info['records']} SPA records on {info['index_pages']} page(s); "
                  f"{info['taken_records']} eligibility-bearing records; {info['documents']} documents "
                  f"({info['pdf_documents']} PDFs); listing {info['listing_seconds']} s")
        counts = update_queue(program, rows)
        print(f"{program}: queue {counts}")
    INVENTORY.write_text(json.dumps(dict(sorted(inventory.items())), indent=1, sort_keys=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
