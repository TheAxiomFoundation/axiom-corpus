#!/usr/bin/env python3
"""Extract 305 ILCS 5 (Illinois Public Aid Code) from the ILGA file repository host.

Wave 6 health, work-order rows 68-70 (305 ILCS 5/5-2). On 2026-10-06 www.ilga.gov answered
the corpus client HTTP 403 "Access Denied" for every path, including the /ftp/ILCS/ tree that
the `illinois-ilcs` adapter reads by default. The same Illinois General Assembly file
repository is served at https://ftp.ilga.gov/ILCS/ (HTTP 200, directory dates 11/24/2025, the
same snapshot the 2026-05-04 statewide scope records as source_as_of 2025-11-24); the JCAR
admin-code adapter already reads that host. This driver calls the unchanged library adapter
with that base URL. No library code is modified.

Usage:
    REQUESTS_CA_BUNDLE=<certifi + data/certs> uv run python scripts/extract_w6_health_illinois_ilcs.py \
        --base /Users/pavelmakarchuk/axiom-corpus/data/corpus
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import date

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.cli import _state_statute_report_payload
from axiom_corpus.corpus.state_adapters.illinois import extract_illinois_ilcs

VERSION = "2026-10-06-w6-health-statute-il"
BASE_URL = "https://ftp.ilga.gov/ILCS/"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--chapter", default="305")
    parser.add_argument("--act", default="5")
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    started = time.time()
    report = extract_illinois_ilcs(
        CorpusArtifactStore(args.base),
        version=VERSION,
        source_as_of="2026-10-06",
        expression_date=date(2025, 11, 24),
        only_chapter=args.chapter,
        only_act=args.act,
        workers=args.workers,
        base_url=BASE_URL,
    )
    payload = _state_statute_report_payload(
        report, source_id="us-il-ilcs-305-5", adapter="illinois-ilcs", version=VERSION
    )
    payload["seconds"] = round(time.time() - started, 1)
    payload["base_url"] = BASE_URL
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0 if report.coverage.complete else 2


if __name__ == "__main__":
    raise SystemExit(main())
