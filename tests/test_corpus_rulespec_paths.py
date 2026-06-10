"""Tests for rulespec-* repo path discovery and citation-path mapping."""

from __future__ import annotations

from pathlib import Path

from axiom_corpus.corpus.rulespec_paths import (
    discover_encoded_paths,
    discover_encoded_paths_for_jurisdictions,
    monorepo_dir_name_for_jurisdiction,
    repo_prefix_for_jurisdiction,
    resolve_jurisdiction_dir,
)


def _touch(path: Path, body: str = "rule: {}\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)


def test_us_statute_yaml_maps_to_canonical_citation_path(tmp_path: Path) -> None:
    repo = tmp_path / "rulespec-us"
    _touch(repo / "statutes" / "7" / "2014" / "e" / "2.yaml")

    encoded = discover_encoded_paths(repo, "us")

    assert encoded == {"us/statute/7/2014/e/2"}


def test_us_statute_top_section_yaml_maps_to_path(tmp_path: Path) -> None:
    repo = tmp_path / "rulespec-us"
    _touch(repo / "statutes" / "26" / "3111" / "a.yaml")

    encoded = discover_encoded_paths(repo, "us")

    assert encoded == {"us/statute/26/3111/a"}


def test_us_regulations_strip_cfr_suffix(tmp_path: Path) -> None:
    repo = tmp_path / "rulespec-us"
    _touch(repo / "regulations" / "7-cfr" / "273" / "7.yaml")

    encoded = discover_encoded_paths(repo, "us")

    # 7-cfr collapses to bare title 7 to align with corpus citation_path.
    assert encoded == {"us/regulation/7/273/7"}


def test_state_regulations_keep_cfr_style_title(tmp_path: Path) -> None:
    repo = tmp_path / "rulespec-us-co"
    _touch(repo / "regulations" / "10-ccr-2506-1" / "4.306.1.yaml")

    encoded = discover_encoded_paths(repo, "us-co")

    # Non-federal jurisdictions don't strip the publication-system suffix.
    assert encoded == {"us-co/regulation/10-ccr-2506-1/4.306.1"}


def test_test_yaml_files_are_excluded(tmp_path: Path) -> None:
    repo = tmp_path / "rulespec-us"
    _touch(repo / "statutes" / "26" / "3111" / "a.yaml")
    _touch(repo / "statutes" / "26" / "3111" / "a.test.yaml")

    encoded = discover_encoded_paths(repo, "us")

    assert encoded == {"us/statute/26/3111/a"}


def test_meta_yaml_files_are_excluded(tmp_path: Path) -> None:
    repo = tmp_path / "rulespec-us"
    _touch(repo / "statutes" / "26" / "3111" / "a.yaml")
    _touch(repo / "statutes" / "26" / "3111" / "a.meta.yaml")

    encoded = discover_encoded_paths(repo, "us")

    assert encoded == {"us/statute/26/3111/a"}


def test_files_under_tests_directory_are_skipped(tmp_path: Path) -> None:
    repo = tmp_path / "rulespec-us"
    _touch(repo / "tests" / "fixture.yaml")
    _touch(repo / "statutes" / "26" / "3111" / "a.yaml")

    encoded = discover_encoded_paths(repo, "us")

    assert encoded == {"us/statute/26/3111/a"}


def test_hidden_directories_are_skipped(tmp_path: Path) -> None:
    repo = tmp_path / "rulespec-us"
    _touch(repo / ".github" / "workflows" / "ci.yaml")
    _touch(repo / "statutes" / "26" / "3111" / "a.yaml")

    encoded = discover_encoded_paths(repo, "us")

    assert encoded == {"us/statute/26/3111/a"}


def test_policies_bucket_maps_to_policy(tmp_path: Path) -> None:
    repo = tmp_path / "rulespec-us"
    _touch(repo / "policies" / "irs" / "rev-proc-2025-32" / "standard-deduction.yaml")

    encoded = discover_encoded_paths(repo, "us")

    assert encoded == {"us/policy/irs/rev-proc-2025-32/standard-deduction"}


def test_missing_repo_returns_empty_set(tmp_path: Path) -> None:
    assert discover_encoded_paths(tmp_path / "does-not-exist", "us") == set()


def test_root_discovery_for_multiple_jurisdictions(tmp_path: Path) -> None:
    _touch(tmp_path / "rulespec-us" / "statutes" / "26" / "3111" / "a.yaml")
    _touch(tmp_path / "rulespec-us-co" / "regulations" / "10-ccr-2506-1" / "4.306.1.yaml")

    discovered = discover_encoded_paths_for_jurisdictions(tmp_path, ["us", "us-co", "uk"])

    assert discovered["us"] == {"us/statute/26/3111/a"}
    assert discovered["us-co"] == {"us-co/regulation/10-ccr-2506-1/4.306.1"}
    assert discovered["uk"] == set()


def test_unknown_bucket_passes_through(tmp_path: Path) -> None:
    repo = tmp_path / "rulespec-us"
    _touch(repo / "manuals" / "irs" / "irm-1.yaml")

    encoded = discover_encoded_paths(repo, "us")

    # No collapse for unmapped buckets — they reach the citation path
    # verbatim so unknown shapes surface in the data instead of crashing.
    assert encoded == {"us/manuals/irs/irm-1"}


def test_files_at_repo_root_are_skipped(tmp_path: Path) -> None:
    repo = tmp_path / "rulespec-us"
    _touch(repo / "config.yaml")
    _touch(repo / "statutes" / "26" / "3111" / "a.yaml")

    encoded = discover_encoded_paths(repo, "us")

    assert encoded == {"us/statute/26/3111/a"}


# ---------------------------------------------------------------------------
# Country monorepo layout (`rulespec-<country>/<prefix>/...`)
# ---------------------------------------------------------------------------


def _build_us_monorepo(root: Path) -> Path:
    """A consolidated rulespec-us holding federal + state jurisdiction dirs."""
    repo = root / "rulespec-us"
    _touch(repo / "us" / "statutes" / "26" / "3111" / "a.yaml")
    _touch(repo / "us" / "regulations" / "7-cfr" / "273" / "7.yaml")
    _touch(repo / "us-ca" / "regulations" / "mpp" / "63-300" / "1.yaml")
    _touch(repo / "us-co" / "regulations" / "10-ccr-2506-1" / "4.306.1.yaml")
    _touch(repo / "programs" / "us" / "snap" / "2026.yaml")
    return repo


def test_jurisdiction_prefix_and_monorepo_name_helpers() -> None:
    assert repo_prefix_for_jurisdiction("us") == "us"
    assert repo_prefix_for_jurisdiction("us-ca") == "us-ca"
    # `canada` is the one slug whose repo prefix differs from the slug.
    assert repo_prefix_for_jurisdiction("canada") == "ca"
    assert repo_prefix_for_jurisdiction("not-a-jurisdiction") is None

    assert monorepo_dir_name_for_jurisdiction("us") == "rulespec-us"
    assert monorepo_dir_name_for_jurisdiction("us-ca") == "rulespec-us"
    assert monorepo_dir_name_for_jurisdiction("uk") == "rulespec-uk"
    assert monorepo_dir_name_for_jurisdiction("canada") == "rulespec-ca"
    assert monorepo_dir_name_for_jurisdiction("not-a-jurisdiction") is None


def test_resolve_jurisdiction_dir_prefers_monorepo_layout(tmp_path: Path) -> None:
    repo = _build_us_monorepo(tmp_path)
    # A stale legacy sibling checkout must lose to the monorepo directory.
    _touch(tmp_path / "rulespec-us-ca" / "regulations" / "mpp" / "63-300" / "1.yaml")

    assert resolve_jurisdiction_dir(tmp_path, "us") == repo / "us"
    assert resolve_jurisdiction_dir(tmp_path, "us-ca") == repo / "us-ca"


def test_resolve_jurisdiction_dir_falls_back_to_legacy_layout(tmp_path: Path) -> None:
    _touch(tmp_path / "rulespec-us" / "statutes" / "26" / "3111" / "a.yaml")
    _touch(tmp_path / "rulespec-us-ca" / "regulations" / "mpp" / "63-300" / "1.yaml")

    # No `us/` dir inside rulespec-us -> the legacy checkout root resolves.
    assert resolve_jurisdiction_dir(tmp_path, "us") == tmp_path / "rulespec-us"
    # No `us-ca/` dir inside rulespec-us -> the legacy sibling resolves.
    assert resolve_jurisdiction_dir(tmp_path, "us-ca") == tmp_path / "rulespec-us-ca"


def test_resolve_jurisdiction_dir_unknown_or_missing(tmp_path: Path) -> None:
    assert resolve_jurisdiction_dir(tmp_path, "not-a-jurisdiction") is None
    assert resolve_jurisdiction_dir(tmp_path, "us-ny") is None


def test_monorepo_discovery_for_federal_and_state_jurisdictions(tmp_path: Path) -> None:
    _build_us_monorepo(tmp_path)

    discovered = discover_encoded_paths_for_jurisdictions(
        tmp_path, ["us", "us-ca", "us-co", "uk"]
    )

    assert discovered["us"] == {
        "us/statute/26/3111/a",
        "us/regulation/7/273/7",
    }
    # Durable IDs are unchanged: us-ca:regulations/mpp/63-300/1 resolves to
    # <rulespec-us>/us-ca/regulations/mpp/63-300/1.yaml.
    assert discovered["us-ca"] == {"us-ca/regulation/mpp/63-300/1"}
    assert discovered["us-co"] == {"us-co/regulation/10-ccr-2506-1/4.306.1"}
    assert discovered["uk"] == set()


def test_monorepo_and_legacy_layouts_mix_under_one_root(tmp_path: Path) -> None:
    _build_us_monorepo(tmp_path)
    # us-ny has not been consolidated yet and still lives in a sibling repo.
    _touch(tmp_path / "rulespec-us-ny" / "regulations" / "18-nycrr" / "387.1.yaml")
    _touch(tmp_path / "rulespec-uk" / "uk" / "statutes" / "sscba-1992" / "141.yaml")
    _touch(tmp_path / "rulespec-ca" / "ca" / "statutes" / "ita" / "118.yaml")

    discovered = discover_encoded_paths_for_jurisdictions(
        tmp_path, ["us", "us-ca", "us-ny", "uk", "canada"]
    )

    assert discovered["us"] == {
        "us/statute/26/3111/a",
        "us/regulation/7/273/7",
    }
    assert discovered["us-ca"] == {"us-ca/regulation/mpp/63-300/1"}
    assert discovered["us-ny"] == {"us-ny/regulation/18-nycrr/387.1"}
    assert discovered["uk"] == {"uk/statute/sscba-1992/141"}
    assert discovered["canada"] == {"canada/statute/ita/118"}


def test_discover_encoded_paths_accepts_monorepo_checkout_root(tmp_path: Path) -> None:
    repo = _build_us_monorepo(tmp_path)

    # Pointing straight at the monorepo checkout resolves the jurisdiction dir.
    assert discover_encoded_paths(repo, "us") == {
        "us/statute/26/3111/a",
        "us/regulation/7/273/7",
    }
    assert discover_encoded_paths(repo, "us-ca") == {"us-ca/regulation/mpp/63-300/1"}
    # Pointing at the jurisdiction directory itself also works.
    assert discover_encoded_paths(repo / "us-ca", "us-ca") == {
        "us-ca/regulation/mpp/63-300/1"
    }


def test_partially_migrated_monorepo_does_not_leak_sibling_jurisdictions(
    tmp_path: Path,
) -> None:
    # Transitional shape: federal content still at the repo root, but state
    # directories and programs/ already merged in.
    repo = tmp_path / "rulespec-us"
    _touch(repo / "statutes" / "26" / "3111" / "a.yaml")
    _touch(repo / "us-ca" / "regulations" / "mpp" / "63-300" / "1.yaml")
    _touch(repo / "programs" / "us" / "snap" / "2026.yaml")

    discovered = discover_encoded_paths_for_jurisdictions(tmp_path, ["us", "us-ca"])

    assert discovered["us"] == {"us/statute/26/3111/a"}
    assert discovered["us-ca"] == {"us-ca/regulation/mpp/63-300/1"}


def test_monorepo_programs_dir_is_not_an_encoding_bucket(tmp_path: Path) -> None:
    repo = _build_us_monorepo(tmp_path)

    encoded = discover_encoded_paths(repo, "us")

    assert not any(path.startswith("us/programs") for path in encoded)


def test_uk_monorepo_local_authority_jurisdiction_dirs_do_not_leak(
    tmp_path: Path,
) -> None:
    # Jurisdiction dirs that are not in JURISDICTION_REPO_MAP yet (e.g. a new
    # local authority) still match the `<country>-` shape and are skipped when
    # walking a transitional repo root.
    repo = tmp_path / "rulespec-uk"
    _touch(repo / "statutes" / "sscba-1992" / "141.yaml")
    _touch(repo / "uk-kingston-upon-thames" / "policies" / "council-tax" / "2026.yaml")

    assert discover_encoded_paths(repo, "uk") == {"uk/statute/sscba-1992/141"}
