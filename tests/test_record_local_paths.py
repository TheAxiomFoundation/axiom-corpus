"""No unsigned record holds a path on the machine that wrote it.

Run notes (``docs/ingest-runs/``), closure work (``docs/coverage/``), reasoning
logs (``.axiom/reasoning-logs/``) and source manifests (``manifests/``) are
public. ``/Users/<name>/...``, ``/private/tmp/...`` or ``~/...`` reaches no
reader and publishes the operator's directory layout.

Invariants:

1. Repository guard. Every record (tracked or untracked, never git-ignored)
   holds no local path, unless ``.axiom/record-local-paths.yaml`` grandfathers
   it. An entry holds only while its record keeps the bytes it pins (sha256),
   still holds a local path, and is attested at those bytes by exactly the
   signed ingest manifests it names; and an entry whose bytes are not in
   ``GRANDFATHERED_SHA256`` (the five attested records on ``main`` on
   2026-10-20) fails, so the allowlist only shrinks. A record that is not UTF-8
   text, an unreadable ingest manifest and a malformed allowlist fail closed.
2. Detection. ``find_record_local_paths`` returns a subset of
   ``find_local_paths``: it drops exactly the spellings that name no place
   (``~``, ``file://``, ``$HOME``, a root alone) and ``/media/`` web paths, and
   keeps every path below a home or temporary root. Messages name a path by its
   root only.
3. Functional manifest paths. Every ``local_path`` in a source manifest is
   relative and names a file a corpus lock records, so ``corpus fetch`` supplies
   it on any machine; every ``download_dir`` is relative and stays inside the
   checkout's ``data/``.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

import pytest
import yaml
from hypothesis import given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus.manifest_local_paths import LOCAL_PATH_ROOTS, find_local_paths
from axiom_corpus.corpus.record_local_paths import (
    RECORD_LOCAL_PATH_ALLOWLIST_PATH,
    RECORD_ROOTS,
    audit_record_local_paths,
    find_record_local_paths,
    load_record_local_path_allowlist,
    record_files,
)
from tests.test_ingest_manifest_provenance import _init_repo

REPO_ROOT = Path(__file__).resolve().parents[1]

# The bytes of the five records on main that held a local path when this guard
# landed (2026-10-20; axiom-corpus#896). Each is attested by a signed ingest
# manifest, so it cannot change without signing that manifest again. An
# allowlist entry must pin one of these, so the allowlist can only lose entries.
# This set only ever loses members: never add to it; scrub the record instead.
GRANDFATHERED_SHA256 = frozenset(
    {
        # .axiom/reasoning-logs/us-co-regulation-2026-06-19-co-oap-9-ccr-2503-5.md
        "a9640fa2f2f6c276e8fedb44b1dbef32842ab5f627370ebe4a2fe3fc230ceeb5",
        # docs/ingest-runs/2026-07-03-dc-code-title-4-refresh.md
        "a77162479d6c753d6836a0c3a60df92b4aed0acf938a3fd8a07955741f6d2b0b",
        # docs/ingest-runs/2026-07-04-be-wallonia-aviq-family-benefit-plafonds-2025.md
        "d12702294775e77329fe01c569c0180c4b92058c7ec6c928938560d6ed62dc4e",
        # docs/ingest-runs/2026-07-21-co-snap-policy.md
        "e2f804fd6b5bdd2ab2c812da9651d0ed146fdb6995dee49eef8cfdc8523149bb",
        # docs/ingest-runs/2026-07-21-wv-snap-manual.md
        "925ebb25d65477fbcedfa3f4d203de0216fe9e7336aac026d0e72aefb70b8746",
    }
)
ISSUE = "https://github.com/TheAxiomFoundation/axiom-corpus/issues/896"


# --- 1. Repository guard -----------------------------------------------------


def test_no_record_holds_a_local_path_unless_grandfathered() -> None:
    issues = audit_record_local_paths(REPO_ROOT, grandfathered_sha256=GRANDFATHERED_SHA256)

    assert issues == [], "\n".join(issues)


def test_the_allowlist_is_inside_the_grandfathered_set() -> None:
    allowances = load_record_local_path_allowlist(REPO_ROOT / RECORD_LOCAL_PATH_ALLOWLIST_PATH)

    assert {allowance.sha256 for allowance in allowances} <= GRANDFATHERED_SHA256
    assert len(allowances) <= len(GRANDFATHERED_SHA256)


LEAKY = "Ran `uv run x --base /Users/someone/secret-dir/data/corpus`.\n"
CLEAN = "Ran `uv run x --base data/corpus` from `<worktrees>/w7-federal`.\n"


def _repo(tmp_path: Path) -> Path:
    return _init_repo(tmp_path / "repo")


def _write(repo: Path, name: str, content: str | bytes) -> tuple[str, bytes]:
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    data = content.encode() if isinstance(content, str) else content
    path.write_bytes(data)
    return name, data


def _attest(repo: Path, manifest: str, records: dict[str, bytes]) -> str:
    name = f".axiom/ingest-manifests/{manifest}"
    payload = {
        "command": {"text": "extract"},
        "reasoning_logs": [
            {"path": path, "sha256": hashlib.sha256(data).hexdigest()}
            for path, data in records.items()
        ],
    }
    _write(repo, name, json.dumps(payload, indent=2) + "\n")
    return name


def _write_allowlist(repo: Path, entries: list[dict[str, object]], **overrides: object) -> None:
    document: dict[str, object] = {
        "schema_version": "axiom-corpus/record-local-paths/v1",
        "records": entries,
    }
    document.update(overrides)
    _write(repo, RECORD_LOCAL_PATH_ALLOWLIST_PATH.as_posix(), yaml.safe_dump(document))


def _entry(path: str, data: bytes, attested_by: list[str]) -> dict[str, object]:
    return {
        "path": path,
        "sha256": hashlib.sha256(data).hexdigest(),
        "attested_by": attested_by,
        "issue": ISSUE,
    }


def _audit(repo: Path, grandfathered: set[str] | frozenset[str] = frozenset()) -> list[str]:
    return audit_record_local_paths(repo, grandfathered_sha256=frozenset(grandfathered))


@pytest.mark.parametrize(
    "name",
    [
        "docs/ingest-runs/2026-10-20-x.md",
        "docs/coverage/wave9/brief.md",
        "docs/coverage/wave9/check.py",
        ".axiom/reasoning-logs/us-x.md",
        "manifests/us-x.yaml",
        "manifests/releases/us-x.json",
    ],
)
def test_a_record_with_a_local_path_fails_naming_line_and_root(tmp_path, name: str) -> None:
    repo = _repo(tmp_path)
    _write(repo, "docs/ingest-runs/clean.md", CLEAN)
    _write(repo, name, "title\n\n" + LEAKY)
    _write_allowlist(repo, [])

    [issue] = _audit(repo)

    assert issue.startswith(f"`{name}`: line 3 holds /Users/…")
    assert "never grandfathered" in issue
    assert "someone" not in issue and "secret-dir" not in issue


def test_a_new_record_is_caught_before_it_is_committed(tmp_path) -> None:
    repo = _repo(tmp_path)
    _write_allowlist(repo, [])
    name, _ = _write(repo, "docs/ingest-runs/draft.md", LEAKY)

    assert [issue.split(":")[0] for issue in _audit(repo)] == [f"`{name}`"]


@pytest.mark.parametrize(
    "name",
    [
        "docs/adapters/guide.md",  # a guide, not a record
        "scripts/build.py",
        "docs/coverage/wave9/__pycache__/check.cpython-314.pyc",  # git-ignored
        "manifests/downloads/x.html",  # git-ignored
    ],
)
def test_files_that_are_not_records_are_not_read(tmp_path, name: str) -> None:
    repo = _repo(tmp_path)
    _write(repo, ".gitignore", "__pycache__/\ndownloads/\n")
    _write(repo, name, b"\xff" + LEAKY.encode())
    _write_allowlist(repo, [])

    assert _audit(repo) == []
    assert name not in record_files(repo)


def test_a_grandfathered_attested_record_passes_while_its_bytes_hold(tmp_path) -> None:
    repo = _repo(tmp_path)
    name, data = _write(repo, "docs/ingest-runs/old.md", LEAKY)
    manifest = _attest(repo, "us/statute/old.json", {name: data})
    _write_allowlist(repo, [_entry(name, data, [manifest])])

    assert _audit(repo, {hashlib.sha256(data).hexdigest()}) == []


def test_a_changed_grandfathered_record_fails(tmp_path) -> None:
    repo = _repo(tmp_path)
    name, data = _write(repo, "docs/ingest-runs/old.md", LEAKY)
    manifest = _attest(repo, "us/statute/old.json", {name: data})
    _write_allowlist(repo, [_entry(name, data, [manifest])])
    _write(repo, name, LEAKY + "More.\n")

    [issue] = _audit(repo, {hashlib.sha256(data).hexdigest()})

    assert "changed since it was grandfathered" in issue and ISSUE in issue
    assert "line 1 holds /Users/…" in issue


def test_a_scrubbed_record_leaves_a_stale_entry_that_fails(tmp_path) -> None:
    repo = _repo(tmp_path)
    name, data = _write(repo, "docs/ingest-runs/old.md", LEAKY)
    manifest = _attest(repo, "us/statute/old.json", {name: data})
    _write_allowlist(repo, [_entry(name, data, [manifest])])
    _write(repo, name, CLEAN)

    [issue] = _audit(repo, {hashlib.sha256(data).hexdigest()})

    assert "no longer holds a local path; remove its entry" in issue


def test_an_entry_outside_the_grandfathered_set_fails_so_the_list_only_shrinks(tmp_path) -> None:
    repo = _repo(tmp_path)
    name, data = _write(repo, "docs/ingest-runs/old.md", LEAKY)
    manifest = _attest(repo, "us/statute/old.json", {name: data})
    _write_allowlist(repo, [_entry(name, data, [manifest])])

    [issue] = _audit(repo, {"0" * 64})

    assert "not grandfathered on 2026-10-20" in issue


def test_an_unattested_record_cannot_be_grandfathered(tmp_path) -> None:
    repo = _repo(tmp_path)
    name, data = _write(repo, "docs/ingest-runs/old.md", LEAKY)
    manifest = _attest(repo, "us/statute/old.json", {})
    _write_allowlist(repo, [_entry(name, data, [manifest])])

    [issue] = _audit(repo, {hashlib.sha256(data).hexdigest()})

    assert "attested at these bytes by no signed ingest manifest" in issue


def test_an_entry_must_name_every_attesting_manifest(tmp_path) -> None:
    repo = _repo(tmp_path)
    name, data = _write(repo, "docs/ingest-runs/old.md", LEAKY)
    first = _attest(repo, "us/statute/a.json", {name: data})
    second = _attest(repo, "us/statute/b.json", {name: data})
    _write_allowlist(repo, [_entry(name, data, [first])])

    [issue] = _audit(repo, {hashlib.sha256(data).hexdigest()})

    assert f"attested at these bytes by `{first}`, `{second}`" in issue


def test_an_attestation_of_other_bytes_does_not_count(tmp_path) -> None:
    repo = _repo(tmp_path)
    name, data = _write(repo, "docs/ingest-runs/old.md", LEAKY)
    manifest = _attest(repo, "us/statute/old.json", {name: b"earlier bytes"})
    _write_allowlist(repo, [_entry(name, data, [manifest])])

    [issue] = _audit(repo, {hashlib.sha256(data).hexdigest()})

    assert "by no signed ingest manifest" in issue


def test_an_entry_for_a_missing_record_fails(tmp_path) -> None:
    repo = _repo(tmp_path)
    gone = "docs/ingest-runs/gone.md"
    _write_allowlist(repo, [_entry(gone, b"x", [".axiom/ingest-manifests/a.json"])])

    [issue] = _audit(repo, {hashlib.sha256(b"x").hexdigest()})

    assert f"`{gone}`, which is not a record in the repository" in issue


def test_an_entry_listed_twice_fails(tmp_path) -> None:
    repo = _repo(tmp_path)
    name, data = _write(repo, "docs/ingest-runs/old.md", LEAKY)
    manifest = _attest(repo, "us/statute/old.json", {name: data})
    _write_allowlist(repo, [_entry(name, data, [manifest]), _entry(name, data, [manifest])])

    [issue] = _audit(repo, {hashlib.sha256(data).hexdigest()})

    assert "twice" in issue


def test_a_record_that_is_not_utf8_fails_closed(tmp_path) -> None:
    repo = _repo(tmp_path)
    name, _ = _write(repo, "docs/coverage/wave9/scan.csv", b"\xff\xfe/Users/someone/x\n")
    _write_allowlist(repo, [])

    [issue] = _audit(repo)

    assert issue == f"`{name}` is not UTF-8 text, so it cannot be checked for local paths."


def test_an_unreadable_ingest_manifest_fails_closed(tmp_path) -> None:
    repo = _repo(tmp_path)
    _write(repo, ".axiom/ingest-manifests/us/statute/bad.json", "{not json")
    _write_allowlist(repo, [])

    [issue] = _audit(repo)

    assert "cannot be read, so the records it attests are unknown" in issue


@pytest.mark.parametrize(
    ("overrides", "entries", "message"),
    [
        ({"schema_version": "v0"}, [], "schema_version"),
        ({"records": {}}, [], "`records` must be a list"),
        ({}, [{"path": "x"}], "exactly path, sha256, attested_by and issue"),
        (
            {},
            [{"path": "docs/guide.md", "sha256": "0" * 64, "attested_by": ["a"], "issue": ISSUE}],
            "path must name a file under",
        ),
        (
            {},
            [
                {
                    "path": "docs/ingest-runs/../guide.md",
                    "sha256": "0" * 64,
                    "attested_by": [".axiom/ingest-manifests/a.json"],
                    "issue": ISSUE,
                }
            ],
            "path must name a file under",
        ),
        (
            {},
            [
                {
                    "path": "docs/ingest-runs/a.md",
                    "sha256": "ABC",
                    "attested_by": [".axiom/ingest-manifests/a.json"],
                    "issue": ISSUE,
                }
            ],
            "64 lowercase hex",
        ),
        (
            {},
            [
                {
                    "path": "docs/ingest-runs/a.md",
                    "sha256": "0" * 64,
                    "attested_by": [],
                    "issue": ISSUE,
                }
            ],
            "attested_by must be a sorted list",
        ),
        (
            {},
            [
                {
                    "path": "docs/ingest-runs/a.md",
                    "sha256": "0" * 64,
                    "attested_by": [
                        ".axiom/ingest-manifests/b.json",
                        ".axiom/ingest-manifests/a.json",
                    ],
                    "issue": ISSUE,
                }
            ],
            "attested_by must be a sorted list",
        ),
        (
            {},
            [
                {
                    "path": "docs/ingest-runs/a.md",
                    "sha256": "0" * 64,
                    "attested_by": ["manifests/a.yaml"],
                    "issue": ISSUE,
                }
            ],
            "attested_by must be a sorted list",
        ),
        (
            {},
            [
                {
                    "path": "docs/ingest-runs/a.md",
                    "sha256": "0" * 64,
                    "attested_by": [".axiom/ingest-manifests/a.json"],
                    "issue": "#896",
                }
            ],
            "issue URL",
        ),
    ],
)
def test_a_malformed_allowlist_fails_closed(tmp_path, overrides, entries, message) -> None:
    repo = _repo(tmp_path)
    _write(repo, "docs/ingest-runs/clean.md", CLEAN)
    _write_allowlist(repo, entries, **overrides)

    [issue] = _audit(repo)

    assert issue.startswith(f"`{RECORD_LOCAL_PATH_ALLOWLIST_PATH.as_posix()}`")
    assert message in issue


def test_a_missing_allowlist_fails_closed_without_naming_the_checkout(tmp_path) -> None:
    repo = _repo(tmp_path)

    [issue] = _audit(repo)

    assert issue == (
        f"`{RECORD_LOCAL_PATH_ALLOWLIST_PATH.as_posix()}` cannot be read "
        "(No such file or directory)."
    )


def test_an_allowlist_that_is_not_yaml_fails_closed(tmp_path) -> None:
    repo = _repo(tmp_path)
    _write(repo, RECORD_LOCAL_PATH_ALLOWLIST_PATH.as_posix(), "records: [\n")

    [issue] = _audit(repo)

    assert issue == f"`{RECORD_LOCAL_PATH_ALLOWLIST_PATH.as_posix()}` is not YAML."


# --- 2. Detection ------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        # OCR of a state plan's checkboxes, and "approximately".
        "Optional State ~ Supplement ~ ~ ~ ~ ~ 0 NEW",
        "the higher of: ~ 133% FPL;",
        # URL text fragments and a CSS sibling combinator.
        "https://law.example.gov/statute/26/32/:~:text=In%20the%20case",
        "uksi_20180146_en.pdf#:~:text=Coming%20into%20force",
        "html_content_selector: 'p.SectBody:has(a[name=\"Art10Sec1\"]) ~ p.ConstSourceNote'",
        # Disk-space notes and prose about the scheme or the root.
        "Disk: `df -g ~` 32 GB free.",
        "official (non-`file://`) download URLs; records a `file://` download URL",
        "under `$HOME` or `/Users/` or `/private/`",
        # Web paths on content-managed sites.
        '{"href": "/media/file/ia-13-0022-mc5.pdf"}',
        "(`/media/<id>/download?inline`)",
        # Placeholders and repository-relative paths.
        CLEAN,
        "`<scratchpad>/tmp/replay.json`, `data/corpus/downloads/us-al-code`",
        "download_dir: ../data/corpus/downloads/us-al-code/2026-09-14-income-tax-chapter",
    ],
)
def test_spellings_that_name_no_machine_path_pass(text: str) -> None:
    assert find_record_local_paths(text) == []


@pytest.mark.parametrize(
    ("text", "root"),
    [
        ("--base /Users/someone/axiom-corpus/data/corpus", "/Users/…"),
        ("Worktree `~/axiom-corpus-worktrees/w6-health`", "~…"),
        ("UV_CACHE_DIR=/private/tmp/axiom-uv-cache uv run", "/private/…"),
        ("REQUESTS_CA_BUNDLE=/tmp/w6-ca.pem", "/tmp/…"),
        ("local_path: /tmp/ny-tanf-source/plan.pdf", "/tmp/…"),
        ('"download_url": "file:///tmp/ny-tanf-source/plan.pdf"', "file:…"),
        ("cache at `$HOME/.axiom/poms-si-cache`", "$HOME…"),
        ("cd /home/runner/work/axiom-corpus", "/home/…"),
        ("/var/folders/xy/T/tmp.abc", "/var/folders/…"),
        ("PATH=/Volumes/Data/bin:$PATH", "/Volumes/…"),
    ],
)
def test_paths_on_a_machine_fail(text: str, root: str) -> None:
    found = find_record_local_paths(text)

    assert found and found[0].describe() == root


_NAME = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789._-", min_size=1, max_size=12)
_WORDS = st.lists(
    st.one_of(
        st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789 ~/:.$<>`'\"=()-\n", max_size=20),
        st.sampled_from(
            [*LOCAL_PATH_ROOTS, "~", "~/", "~/x", "file://", "file:///x", "$HOME", "${HOME}/x"]
            + ["%USERPROFILE%", "C:\\Users\\", "C:/Users/x", "/media/file/a.pdf", "<scratchpad>"]
        ),
    ),
    max_size=6,
)


@settings(max_examples=300, deadline=None)
@given(text=st.text(max_size=120))
def test_detection_is_a_subset_of_find_local_paths(text: str) -> None:
    found = find_record_local_paths(text)

    assert set(found) <= set(find_local_paths(text))


_NO_PLACE_TOKEN = re.compile(
    r"(?i)~/?|file:/*|(?:\$HOME|\$\{HOME\}|%USERPROFILE%)/?"
    r"|[a-z]:[\\/](?:users|documents and settings)[\\/]?"
)


@settings(max_examples=300, deadline=None)
@given(words=_WORDS)
def test_it_drops_exactly_the_spellings_that_name_no_place(words: list[str]) -> None:
    text = " ".join(words)
    kept = set(find_record_local_paths(text))

    for path in find_local_paths(text):
        token = text[path.start : path.end]
        names_no_place = (
            token == path.root or path.root == "/media/"
            if path.kind == "absolute"
            else _NO_PLACE_TOKEN.fullmatch(token) is not None
        )
        assert (path in kept) is not names_no_place, token


@settings(max_examples=300, deadline=None)
@given(
    root=st.sampled_from([root for root in LOCAL_PATH_ROOTS if root != "/media/"] + ["~/"]),
    name=_NAME,
    before=_WORDS,
    after=_WORDS,
)
def test_every_path_below_a_machine_root_is_found(
    root: str, name: str, before: list[str], after: list[str]
) -> None:
    path = f"{root}{name}/x"
    text = " ".join(before) + f" `{path}` " + " ".join(after)

    found = find_record_local_paths(text)

    start = text.index(f"`{path}`") + 1
    assert any(item.start == start for item in found), text


# --- 3. Functional manifest paths --------------------------------------------


def _source_manifests(key: str) -> list[Path]:
    """The manifests whose text names ``key`` (parsing all 1,700 takes a minute)."""
    return sorted(
        path for path in (REPO_ROOT / "manifests").rglob("*.yaml") if f"{key}:" in path.read_text()
    )


def _locked_corpus_files() -> set[str]:
    locked: set[str] = set()
    for lock in (REPO_ROOT / ".axiom/corpus-locks").rglob("*.json"):
        locked.update(item["path"] for item in json.loads(lock.read_text())["files"])
    return locked


def _manifest_rows(manifest: Path, key: str) -> list[dict]:
    document = yaml.load(manifest.read_text(), Loader=getattr(yaml, "CSafeLoader", yaml.SafeLoader))
    rows = document.get(key) if isinstance(document, dict) else None
    return [row for row in rows or [] if isinstance(row, dict)]


def test_every_local_path_names_a_locked_corpus_file() -> None:
    locked = _locked_corpus_files()
    seen = 0
    for manifest in _source_manifests("local_path"):
        for row in _manifest_rows(manifest, "documents"):
            local_path = row.get("local_path")
            if local_path is None:
                continue
            seen += 1
            assert not Path(local_path).is_absolute(), f"{manifest.name}: {row['source_id']}"
            resolved = Path(os.path.normpath(manifest.parent / local_path))
            relative = resolved.relative_to(REPO_ROOT).as_posix()
            assert relative in locked, f"{manifest.name}: {row['source_id']}"
    # The bo, mz (three) and us-ny retained copies at least.
    assert seen >= 5


def test_every_download_dir_stays_inside_the_checkout_data_directory() -> None:
    seen = 0
    data = REPO_ROOT / "data"
    for manifest in _source_manifests("download_dir"):
        for row in _manifest_rows(manifest, "sources"):
            options = row.get("options")
            download_dir = options.get("download_dir") if isinstance(options, dict) else None
            if download_dir is None:
                continue
            seen += 1
            assert not Path(download_dir).is_absolute(), f"{manifest.name}: {row['source_id']}"
            resolved = Path(os.path.normpath(manifest.parent / download_dir))
            assert resolved.is_relative_to(data), manifest.name
    assert seen > 0


def test_the_record_roots_exist() -> None:
    for root in RECORD_ROOTS:
        assert (REPO_ROOT / root).is_dir(), root


def test_record_files_lists_the_repository_records() -> None:
    files = record_files(REPO_ROOT)
    tracked = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "--", *RECORD_ROOTS],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split("\n")

    assert {name for name in tracked if name and (REPO_ROOT / name).is_file()} <= set(files)
