"""Keep the approved section-only slice reproducible as appendix support grows."""

import json
from pathlib import Path

from axiom_corpus.corpus.artifacts import sha256_bytes
from scripts.repro_us_cfr_416_deeming_slice import (
    EXPECTED_SOURCE_SHA256,
    GENERATED_RELATIVE_PATHS,
    PROVISIONS_RELATIVE_PATH,
    reproduce,
)


def test_deeming_reproduction_preserves_pinned_section_scope(tmp_path):
    repo_root = Path(__file__).parents[1]
    source_base = repo_root / "data" / "corpus"
    manifest = json.loads(
        (repo_root / "docs/validation/us-cfr-416-deeming-baseline.json").read_text()
    )
    assert manifest["source_sha256"] == {
        str(path): digest for path, digest in EXPECTED_SOURCE_SHA256.items()
    }
    for relative_path, expected_digest in manifest["source_sha256"].items():
        assert sha256_bytes((source_base / relative_path).read_bytes()) == expected_digest
    assert set(manifest["output_sha256"]) == {str(path) for path in GENERATED_RELATIVE_PATHS}

    report = reproduce(tmp_path, source_base)

    assert report["full_source_count"] == 622
    assert report["selected_count"] == 14
    assert report["coverage_complete"]
    for key, expected in manifest["expected_report"].items():
        assert report[key] == expected
    assert report["files"] == manifest["output_sha256"]
    for relative_path in GENERATED_RELATIVE_PATHS:
        actual = (tmp_path / relative_path).read_bytes()
        actual_digest = sha256_bytes(actual)
        assert actual_digest == manifest["output_sha256"][str(relative_path)]
        if relative_path == PROVISIONS_RELATIVE_PATH:
            # The historical replay and the published July artifact are distinct;
            # docs/validation/us-cfr-416-deeming-baseline.md documents both.
            published = manifest["published_provisions"]
            assert published["relative_path"] == str(relative_path)
            assert sha256_bytes((source_base / relative_path).read_bytes()) == published["sha256"]
            assert actual_digest != published["sha256"]
        else:
            assert actual == (source_base / relative_path).read_bytes()
