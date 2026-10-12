"""Extract the wave-7 Minnesota DHS manifest one document at a time, with a pause between requests.

www.dhs.state.mn.us sits behind a Radware bot manager. The run notes document the curl_cffi chrome120
profile for it (docs/ingest-runs/2026-09-14-msp-charts-snap-fy2026.md,
docs/ingest-runs/2026-09-14-liheap-matrix-ssi-standards.md); on 2026-10-12 that profile answered the first
four pages and then the Radware challenge page for every further request in a burst. This wrapper runs the
unchanged `extract_official_documents` with a pause before each publisher request and refuses any response
that is the Radware page, so a challenge is never stored as a document. It does not retry a challenged page.

    uv run python scripts/extract_w7_state_benefits_mn.py --base <corpus root> --pause 45
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from axiom_corpus.corpus import documents
from axiom_corpus.corpus.artifacts import CorpusArtifactStore

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "manifests/us-mn-state-benefits-w7-manual.yaml"
VERSION = "2026-10-12-w7-state-benefits-manual-mn"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--pause", type=float, default=45.0)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--version", default=VERSION)
    args = parser.parse_args()

    original = documents._download_document
    first = True

    def paced(source, *, session):  # type: ignore[no-untyped-def]
        nonlocal first
        if not first:
            time.sleep(args.pause)
        first = False
        downloaded = original(source, session=session)
        # The challenge page's <title> is "Radware Page" (offset 159 on 2026-10-12); real pages
        # also load a perfdrive script, so only the title marks a challenge.
        if b"<title>Radware Page</title>" in downloaded.content[:4000]:
            raise RuntimeError(f"Radware challenge page for {source.source_url}; not stored")
        print(f"fetched {source.source_id}: {len(downloaded.content)} bytes", flush=True)
        return downloaded

    documents._download_document = paced  # type: ignore[assignment]
    report = documents.extract_official_documents(
        CorpusArtifactStore(args.base),
        manifest_path=args.manifest,
        version=args.version,
        source_as_of="2026-10-12",
    )
    print(report.provisions_path, report.provisions_written, report.coverage.complete)


if __name__ == "__main__":
    main()
