"""Generate the pre-PR release-object fixture with the code at origin/main."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from base64 import b64encode
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from axiom_corpus.corpus.artifacts import CorpusArtifactStore
from axiom_corpus.corpus.models import ProvisionRecord, SourceInventoryItem
from axiom_corpus.corpus.releases import (
    COMPLETE_EXPRESSION_DATES_PROFILE,
    ReleaseManifest,
    resolve_release_manifest_path,
)
from axiom_corpus.release.manifest import (
    build_release_content,
    build_unsigned_release_object,
    selector_sha256,
    serialize_release_object,
    sign_release_object,
)

REPO = Path(__file__).resolve().parents[1]
KEY = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
PRIVATE = b64encode(
    KEY.private_bytes(
        serialization.Encoding.Raw,
        serialization.PrivateFormat.Raw,
        serialization.NoEncryption(),
    )
).decode()
GIT_ENV = {
    "GIT_AUTHOR_NAME": "Fixture",
    "GIT_AUTHOR_EMAIL": "fixture@example.com",
    "GIT_COMMITTER_NAME": "Fixture",
    "GIT_COMMITTER_EMAIL": "fixture@example.com",
    "GIT_AUTHOR_DATE": "2026-09-27T00:00:00+00:00",
    "GIT_COMMITTER_DATE": "2026-09-27T00:00:00+00:00",
}


def build_tree(root: Path) -> ReleaseManifest:
    store = CorpusArtifactStore(root / "data" / "corpus")
    name = "fx-rulespec-2026-09-27"
    scopes = []
    for jurisdiction, document_class, version, title in (
        ("fx", "statute", "2026-09-27-fx-statute", "1"),
        ("fx", "regulation", "2026-09-27-fx-regulation", "7"),
    ):
        source = store.source_path(jurisdiction, document_class, version, f"title-{title}.xml")
        source_sha = store.write_text(source, f"<title n='{title}'>Official text.</title>")
        source_rel = source.relative_to(store.root).as_posix()
        root_path = f"{jurisdiction}/{document_class}/{title}"
        section_path = f"{root_path}/1"
        store.write_inventory(
            store.inventory_path(jurisdiction, document_class, version),
            [
                SourceInventoryItem(citation_path=root_path, source_path=source_rel, sha256=source_sha),
                SourceInventoryItem(citation_path=section_path, source_path=source_rel, sha256=source_sha),
            ],
        )
        store.write_provisions(
            store.provisions_path(jurisdiction, document_class, version),
            [
                ProvisionRecord(
                    jurisdiction=jurisdiction,
                    document_class=document_class,
                    citation_path=root_path,
                    version=version,
                    heading=f"Title {title}",
                    kind="title",
                    source_path=source_rel,
                    expression_date="2026-09-01",
                ),
                ProvisionRecord(
                    jurisdiction=jurisdiction,
                    document_class=document_class,
                    citation_path=section_path,
                    parent_citation_path=root_path,
                    version=version,
                    heading="Section 1",
                    body="Official text — π.",
                    kind="section",
                    source_path=source_rel,
                    expression_date="2026-09-01",
                ),
            ],
        )
        store.write_json(
            store.coverage_path(jurisdiction, document_class, version),
            {
                "complete": True,
                "source_count": 2,
                "provision_count": 2,
                "matched_count": 2,
                "missing_from_provisions": [],
                "extra_provisions": [],
            },
        )
        scopes.append(
            {"jurisdiction": jurisdiction, "document_class": document_class, "version": version}
        )
    selector = root / "manifests" / "releases" / f"{name}.json"
    selector.parent.mkdir(parents=True)
    selector.write_text(
        json.dumps(
            {"name": name, "quality_profile": COMPLETE_EXPRESSION_DATES_PROFILE, "scopes": scopes},
            indent=2,
        )
        + "\n"
    )
    env = {**os.environ, **GIT_ENV}
    subprocess.run(["git", "init", "-q", str(root)], check=True, env=env)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True, env=env)
    subprocess.run(
        ["git", "-C", str(root), "-c", "commit.gpgsign=false", "commit", "-qm", "fixture"],
        check=True,
        env=env,
    )
    return ReleaseManifest.load(selector)


def main() -> int:
    out = Path(sys.argv[1])
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "repo"
        release = build_tree(root)
        content = build_release_content(
            root,
            release=release,
            validation={"passed": True},
            created_at="2026-09-27T00:00:00Z",
        )
    content["validation"] = {
        "passed": True,
        "quality_profile": COMPLETE_EXPRESSION_DATES_PROFILE,
        "deep_validation": {"error_count": 0, "warning_count": 0, "scope_count": len(content["scopes"])},
        "r2_readback": {
            "bucket": "axiom-corpus",
            "artifact_count": len(content["artifacts"]),
            "artifact_bytes": sum(entry["bytes"] for entry in content["artifacts"]),
            "verified_keys": [entry["r2_key"] for entry in content["artifacts"]],
        },
        "supabase_projection_evidence": [
            {
                "jurisdiction": scope["jurisdiction"],
                "document_class": scope["document_class"],
                "version": scope["version"],
                "expected": scope["provision_rows"],
                "actual": scope["provision_rows"],
                "expected_navigation": scope["navigation_rows"],
                "actual_navigation": scope["navigation_rows"],
                "expected_provision_projection_sha256": scope["provision_projection_sha256"],
                "actual_provision_projection_sha256": scope["provision_projection_sha256"],
                "expected_navigation_projection_sha256": scope["navigation_projection_sha256"],
                "actual_navigation_projection_sha256": scope["navigation_projection_sha256"],
            }
            for scope in sorted(
                content["scopes"],
                key=lambda s: (s["jurisdiction"], s["document_class"], s["version"]),
            )
        ],
    }
    signed = sign_release_object(build_unsigned_release_object(content), private_key=PRIVATE)
    tracked = subprocess.run(
        ["git", "-C", str(REPO), "ls-files", "manifests/releases/*.json"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split()
    selector_digests = {}
    for relative in sorted(tracked):
        manifest = ReleaseManifest.load(REPO / relative)
        selector_digests[relative] = selector_sha256(manifest)
    payload = {
        "generated_from": subprocess.run(
            ["git", "-C", str(REPO), "rev-parse", "HEAD"], check=True, capture_output=True, text=True
        ).stdout.strip(),
        "release_selector_sha256": selector_sha256(release),
        "content": content,
        "signed_release_object": serialize_release_object(signed).decode("ascii"),
        "tracked_selector_sha256": selector_digests,
    }
    out.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n")
    print(out, len(selector_digests), payload["release_selector_sha256"], content["git"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
