"""Extract the wave-7 Minnesota DHS manifest, pacing requests and refusing Radware challenge pages.

www.dhs.state.mn.us sits behind a Radware bot manager. The run notes document the curl_cffi chrome120
profile for it (docs/ingest-runs/2026-09-14-msp-charts-snap-fy2026.md,
docs/ingest-runs/2026-09-14-liheap-matrix-ssi-standards.md); on 2026-10-12 that profile answered the first
four pages of the probe and then the Radware challenge page for every further request. This wrapper runs the
unchanged `extract_official_documents` with a pause before each publisher request and refuses any response
that is the Radware page, so a challenge is never stored as a document. It does not retry a challenged page.

`--retained SOURCE_ID=PATH` replays bytes the probe already took from the official address with the same
documented profile (the supported `local_path` field, set on an untracked copy of the committed manifest,
as in docs/ingest-runs/2026-09-09-de-kindergeld-adult-services.md); the run note lists their SHA-256.

    uv run python scripts/extract_w7_state_benefits_mn.py --base <corpus root> --pause 60 \
        [--retained <source_id>=<file> ...] [--work-dir <scratch dir>]
"""

from __future__ import annotations

import argparse
import tempfile
import time
from pathlib import Path

import yaml

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
    parser.add_argument("--retained", action="append", default=[], metavar="SOURCE_ID=PATH")
    parser.add_argument("--work-dir", type=Path)
    args = parser.parse_args()

    manifest_path = args.manifest
    if args.retained:
        retained = dict(item.split("=", 1) for item in args.retained)
        data = yaml.safe_load(args.manifest.read_text())
        unknown = set(retained) - {d["source_id"] for d in data["documents"]}
        if unknown:
            raise SystemExit(f"unknown source ids: {sorted(unknown)}")
        for entry in data["documents"]:
            if entry["source_id"] in retained:
                entry["local_path"] = str(Path(retained[entry["source_id"]]).resolve())
        work_dir = args.work_dir or Path(tempfile.mkdtemp())
        manifest_path = work_dir / f"{args.manifest.stem}.retained.yaml"
        manifest_path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))

    original = documents._download_document
    first = True

    def paced(source, *, session):  # type: ignore[no-untyped-def]
        nonlocal first
        if not source.local_path:
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
        manifest_path=manifest_path,
        version=args.version,
        source_as_of="2026-10-12",
    )
    print(report.provisions_path, report.provisions_written, report.coverage.complete)


if __name__ == "__main__":
    main()
