"""No signed ingest manifest records a path on the machine that built it.

A signed manifest is public and its ``command.text`` records how anyone can
rebuild the scope. ``/Users/<name>/...``, ``/private/tmp/...`` or ``~/...``
reaches no one else and publishes the operator's directory layout.

Invariants:

1. Repository guard. Every manifest under ``.axiom/ingest-manifests/`` records
   no local path in any string field, unless
   ``.axiom/ingest-manifest-local-paths.yaml`` grandfathers it. An entry holds
   only while its manifest keeps the bytes it pins (sha256) and records paths in
   exactly the fields it lists; a stale entry fails; and an entry whose
   ``(path, sha256)`` is not in ``GRANDFATHERED`` (the fourteen on ``main`` on
   2026-10-20) fails, so the allowlist only shrinks. A manifest or allowlist
   that cannot be read fails closed.
2. Write time. ``build_ingest_manifest`` records an absolute path inside the
   checkout repository-relative (through ``~``, ``$HOME``, short-option and
   ``@`` leads, symbolic links, and a checkout path holding a space) and
   refuses any other local path; ``sign_ingest_manifest`` refuses a manifest
   with one in any field, the signature's key id included, so
   ``sign-ingest-manifest`` exits 2 and writes nothing.
3. Detection (``find_local_paths``) is sound for every root at a token start,
   never flags a root inside a URL or relative path or after a placeholder,
   is additive over whitespace-joined text, and agrees with a brute-force
   tokenizing reference. ``local_path_fields`` reports exactly the fields that
   hold one, and messages name a path by its root only.
4. ``relativize_repo_paths`` maps ``<checkout>/<rel>`` to ``<rel>``, rewrites a
   path only to one naming the same file, and is idempotent;
   ``recordable_command`` either refuses or returns a command with no local
   path that it returns unchanged.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest
import yaml
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus.cli import main
from axiom_corpus.corpus.ingest_manifests import (
    LOCAL_PATH_ALLOWLIST_PATH,
    ManifestLocalPathError,
    audit_manifest_local_paths,
    build_ingest_manifest,
    load_local_path_allowlist,
    manifest_local_path_issues,
    recordable_command,
    sign_ingest_manifest,
    write_signed_ingest_manifest,
)
from axiom_corpus.corpus.manifest_local_paths import (
    LOCAL_PATH_ROOTS,
    ManifestReadError,
    find_local_paths,
    local_path_fields,
    manifest_local_path_fields,
    redact_local_paths,
    relativize_repo_paths,
    repo_rewrites,
)
from scripts.recover_ingest import recorded_fetched_dir
from tests.test_ingest_manifest_provenance import _artifact, _init_repo, _keys

REPO_ROOT = Path(__file__).resolve().parents[1]

# The fourteen manifests on main that recorded a local path when this guard
# landed (2026-10-20; axiom-corpus#896), each at the bytes it had. An allowlist
# entry must be one of these pairs, so the allowlist can only lose entries.
# This set only ever loses members: never add to it; sign the manifest again
# without the path.
_MANIFESTS = ".axiom/ingest-manifests/"
GRANDFATHERED = frozenset(
    {
        (
            _MANIFESTS + "be/statute/2026-07-05-be-birth-leave.json",
            "313df68cdd3b91d50498b27cdca087f804b0e8a856138883f8511aa21f0533ee",
        ),
        (
            _MANIFESTS + "ca/rulemaking/2026-09-04-us-surtax-orders.json",
            "030b4a0621490d98f564c0a12597fd9d34d0629134b6d0f1cab8e181daf21b48",
        ),
        (
            _MANIFESTS + "de/guidance/2026-09-09-de-kindergeld-adult-services.json",
            "8e6263bf3cb260fbbca491c7a0c3572c1ac594ca66789f341b8a7825b34e1ff0",
        ),
        (
            _MANIFESTS + "de/guidance/2026-09-09-de-kindergeld-allowance-explanation.json",
            "9b5fc16dda2dc6da4a72aeead6b40b2eb117d114e97f14ee6fb129c419581112",
        ),
        (
            _MANIFESTS + "de/guidance/2026-09-09-de-kindergeld-bmf-letter-context.json",
            "6ef51002cf47f4b9391ec13dfb7f3d55d3656ba8327ef561aeeb980f79d8ff53",
        ),
        (
            _MANIFESTS + "de/statute/2026-09-09-de-kindergeld-adult-service-history.json",
            "177f547e33c8be690108f936b12ec94453fd3db243c7f96bcb27305965edcd64",
        ),
        (
            _MANIFESTS + "us-ca/regulation/2026-07-17-ca-cdss-mpp-calfresh.json",
            "b02cab0d9c7e05d633c73570b2b54a58e1a57bb5397783a338dfd9096fe7d018",
        ),
        (
            _MANIFESTS + "us-co/policy/2026-07-21-co-snap-policy.json",
            "c26cbc4250b352b0af8ef5fd408711337f53e6b7b6c492ef1b8c616233de42bc",
        ),
        (
            _MANIFESTS + "us-co/regulation/2026-06-19-co-oap-9-ccr-2503-5.json",
            "9e31c8ab4e6c8e7a58cd0f82c702f66f8ef3209be08a4d9717486fde07065220",
        ),
        (
            _MANIFESTS + "us-dc/statute/2026-05-19-title-4.json",
            "0e639195ec4bac231e913ed9d32c17f1ff7ff002315a21cbf8e09c161814e8fa",
        ),
        (
            _MANIFESTS + "us-wv/manual/2026-07-21-wv-income-maintenance-manual.json",
            "60e8d243f29ae7bf58a0939cc6f71d7394551aeefce1f5367c23bf0e4a905369",
        ),
        (
            _MANIFESTS + "us-wv/manual/2026-07-21-wv-snap-healthy-choices-overlay.json",
            "dc417f56481d4de2fd47ab3f483cb97d0efac2fa5cdead3e14daca08a6cd8365",
        ),
        (
            _MANIFESTS + "us/statute/2026-06-26-chip-title-xxi-title-42.json",
            "e8e0120ed3b74ed4b6cc9d8e541fc445d435a0e367ff150cb5d8444ede308e2f",
        ),
        (
            _MANIFESTS + "us/statute/2026-08-01-tariff-title-19-spine-title-19.json",
            "fc42d4dc1a8d4250ffebe1f81495ad2a61502b8668a2274a143640668e345c06",
        ),
    }
)
ISSUE = "https://github.com/TheAxiomFoundation/axiom-corpus/issues/896"


# --- 1. Repository guard -----------------------------------------------------


def test_no_ingest_manifest_records_a_local_path_unless_grandfathered() -> None:
    issues = audit_manifest_local_paths(REPO_ROOT, grandfathered=GRANDFATHERED)

    assert issues == [], "\n".join(issues)


def test_the_allowlist_is_inside_the_grandfathered_set() -> None:
    allowances = load_local_path_allowlist(REPO_ROOT / LOCAL_PATH_ALLOWLIST_PATH)

    assert {(allowance.path, allowance.sha256) for allowance in allowances} <= GRANDFATHERED


def _write_manifest(repo: Path, name: str, payload: object) -> tuple[str, bytes]:
    path = repo / ".axiom/ingest-manifests" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()
    path.write_bytes(data)
    return path.relative_to(repo).as_posix(), data


def _write_allowlist(repo: Path, entries: list[dict[str, object]], **overrides: object) -> None:
    document: dict[str, object] = {
        "schema_version": "axiom-corpus/ingest-manifest-local-paths/v1",
        "manifests": entries,
    }
    document.update(overrides)
    path = repo / LOCAL_PATH_ALLOWLIST_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(document, sort_keys=False))


def _entry(path: str, data: bytes, fields: list[str] | None = None) -> dict[str, object]:
    return {
        "path": path,
        "sha256": hashlib.sha256(data).hexdigest(),
        "fields": fields or ["command.text"],
        "issue": ISSUE,
    }


def _pair(path: str, data: bytes) -> tuple[str, str]:
    return path, hashlib.sha256(data).hexdigest()


LEAKY = {"command": {"text": "uv run x --manifest /Users/someone/secret-dir/replay.json"}}
CLEAN = {"command": {"text": "uv run x --manifest <scratchpad>/replay.json"}}


def _audit(repo: Path, grandfathered: set[tuple[str, str]] | None = None) -> list[str]:
    return audit_manifest_local_paths(repo, grandfathered=frozenset(grandfathered or ()))


def test_an_unlisted_manifest_with_a_local_path_fails_naming_field_and_root(tmp_path) -> None:
    _write_manifest(tmp_path, "us/statute/v.json", CLEAN)
    path, _ = _write_manifest(tmp_path, "us/statute/w.json", LEAKY)
    _write_allowlist(tmp_path, [])

    [issue] = _audit(tmp_path)

    assert issue.startswith(f"`{path}`")
    assert "`command.text` holds /Users/…" in issue
    assert "never grandfathered" in issue
    assert "someone" not in issue and "secret-dir" not in issue


def test_a_grandfathered_manifest_passes_while_its_bytes_and_fields_hold(tmp_path) -> None:
    path, data = _write_manifest(tmp_path, "us/statute/w.json", LEAKY)
    _write_allowlist(tmp_path, [_entry(path, data)])

    assert _audit(tmp_path, {_pair(path, data)}) == []


def test_a_changed_grandfathered_manifest_fails(tmp_path) -> None:
    path, data = _write_manifest(tmp_path, "us/statute/w.json", LEAKY)
    _write_allowlist(tmp_path, [_entry(path, data)])
    _write_manifest(tmp_path, "us/statute/w.json", {**LEAKY, "generated_at": "later"})

    [issue] = _audit(tmp_path, {_pair(path, data)})

    assert "changed since it was grandfathered" in issue and ISSUE in issue


def test_a_scrubbed_manifest_leaves_a_stale_entry_that_fails(tmp_path) -> None:
    path, data = _write_manifest(tmp_path, "us/statute/w.json", LEAKY)
    _write_allowlist(tmp_path, [_entry(path, data)])
    _write_manifest(tmp_path, "us/statute/w.json", CLEAN)

    [issue] = _audit(tmp_path, {_pair(path, data)})

    assert "no longer records a local path; remove its entry" in issue


def test_an_entry_outside_the_grandfathered_set_fails_so_the_list_only_shrinks(tmp_path) -> None:
    path, data = _write_manifest(tmp_path, "us/statute/w.json", LEAKY)
    _write_allowlist(tmp_path, [_entry(path, data)])

    [issue] = _audit(tmp_path, {(path, "0" * 64)})

    assert "not grandfathered on 2026-10-20" in issue


def test_grandfathered_bytes_copied_to_a_new_path_cannot_be_listed(tmp_path) -> None:
    """Once one grandfathered manifest is scrubbed, its slot is not reusable."""
    old, data = _write_manifest(tmp_path, "us/statute/w.json", LEAKY)
    new, _ = _write_manifest(tmp_path, "us/statute/copy.json", LEAKY)
    _write_allowlist(tmp_path, [_entry(new, data)])
    (tmp_path / old).unlink()

    [issue] = _audit(tmp_path, {_pair(old, data)})

    assert f"lists `{new}` at a path and bytes that were not grandfathered" in issue


def test_an_entry_for_a_missing_manifest_fails(tmp_path) -> None:
    path, data = _write_manifest(tmp_path, "us/statute/w.json", LEAKY)
    gone = ".axiom/ingest-manifests/us/statute/gone.json"
    _write_allowlist(tmp_path, [_entry(path, data), _entry(gone, data)])

    [issue] = _audit(tmp_path, {_pair(path, data), _pair(gone, data)})

    assert f"`{gone}`, which does not exist" in issue


def test_an_entry_listed_twice_fails(tmp_path) -> None:
    path, data = _write_manifest(tmp_path, "us/statute/w.json", LEAKY)
    _write_allowlist(tmp_path, [_entry(path, data), _entry(path, data)])

    [issue] = _audit(tmp_path, {_pair(path, data)})

    assert "twice" in issue


def test_an_entry_whose_fields_differ_fails(tmp_path) -> None:
    payload = {**LEAKY, "coverage": {"note": "see ~/notes"}}
    path, data = _write_manifest(tmp_path, "us/statute/w.json", payload)
    _write_allowlist(tmp_path, [_entry(path, data)])

    [issue] = _audit(tmp_path, {_pair(path, data)})

    assert "command.text, coverage.note" in issue


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (b"\xff\xfe{}", "is not UTF-8 text"),
        (b"{not json", "is not JSON"),
        (b'{"command": {"text": "/Users/a/b"}, "command": {"text": "ok"}}', "repeats the key"),
    ],
)
def test_an_unreadable_manifest_fails_closed(tmp_path, payload: bytes, message: str) -> None:
    path = tmp_path / ".axiom/ingest-manifests/us/statute/w.json"
    path.parent.mkdir(parents=True)
    path.write_bytes(payload)
    _write_allowlist(tmp_path, [])

    [issue] = _audit(tmp_path)

    assert message in issue and "cannot be checked for local paths" in issue


def _bad(**fields: object) -> dict[str, object]:
    entry: dict[str, object] = {
        "path": ".axiom/ingest-manifests/a.json",
        "sha256": "0" * 64,
        "fields": ["a"],
        "issue": ISSUE,
    }
    entry.update(fields)
    return entry


@pytest.mark.parametrize(
    ("overrides", "entries", "message"),
    [
        ({"schema_version": "v0"}, [], "schema_version"),
        ({"manifests": {}}, [], "`manifests` must be a list"),
        ({}, [{"path": "x"}], "exactly path, sha256, fields and issue"),
        ({}, [_bad(path="data/x.json")], "must name a .json file"),
        ({}, [_bad(path=".axiom/ingest-manifests/../x.json")], "must name a .json file"),
        ({}, [_bad(sha256="ABC")], "64 lowercase hex"),
        ({}, [_bad(fields=["b", "a"])], "sorted list"),
        ({}, [_bad(fields=[])], "sorted list"),
        ({}, [_bad(issue="#896")], "issue URL"),
    ],
)
def test_a_malformed_allowlist_fails_closed(tmp_path, overrides, entries, message) -> None:
    _write_manifest(tmp_path, "us/statute/w.json", CLEAN)
    _write_allowlist(tmp_path, entries, **overrides)

    [issue] = _audit(tmp_path)

    assert issue.startswith(f"`{LOCAL_PATH_ALLOWLIST_PATH.as_posix()}`") and message in issue


def test_a_missing_allowlist_fails_closed(tmp_path) -> None:
    _write_manifest(tmp_path, "us/statute/w.json", CLEAN)

    [issue] = _audit(tmp_path)

    assert issue.startswith(f"`{LOCAL_PATH_ALLOWLIST_PATH.as_posix()}`")


def test_paths_are_found_in_every_string_field_but_signature_value() -> None:
    payload = {
        "applied_files": [{"path": "data/x", "sha256": "a"}, {"path": "/tmp/x", "sha256": "b"}],
        "command": {"text": "ok"},
        "coverage": {"nested": [{"deep": "$HOME/x"}]},
        "/Users/someone/key": 1,
        # base64 may hold "/Users/" by chance; it records bytes, not a path.
        "signature": {"algorithm": "ed25519", "key_id": "~/k", "value": "/Users/cd+tmp/ef=="},
    }

    fields = [field for field, _ in local_path_fields(payload)]

    assert fields == [
        "applied_files[1].path",
        "coverage.nested[0].deep",
        "/Users/… (key)",
        "signature.key_id",
    ]
    assert "someone" not in " ".join(manifest_local_path_issues(payload))
    # Read as decoded: a JSON escape cannot hide a path.
    escaped = b'{"a": "\\u002fhome\\u002fsomeone", "b": "\\u007e/x"}'
    assert [field for field, _ in manifest_local_path_fields(escaped)] == ["a", "b"]


def test_manifest_local_path_fields_refuses_repeated_keys_without_echoing_a_path() -> None:
    with pytest.raises(ManifestReadError) as raised:
        manifest_local_path_fields(b'{"/Users/someone/x": 1, "/Users/someone/x": 2}')

    assert "someone" not in str(raised.value)


# --- 2. Write time ----------------------------------------------------------


def _spellings(path: Path) -> list[str]:
    """The checkout as an operator might type it: as resolved, and on macOS without /private."""
    resolved = str(path.resolve())
    spellings = [resolved]
    if resolved.startswith("/private/"):
        spellings.append(resolved[len("/private") :])
    return spellings


def test_build_records_checkout_paths_repository_relative(tmp_path, monkeypatch) -> None:
    repo = _init_repo(tmp_path / "repo")
    monkeypatch.setenv("HOME", str(tmp_path))
    for checkout in _spellings(repo):
        command = (
            f"UV_PROJECT_ENVIRONMENT={checkout}/.venv {checkout}/.venv/bin/python -m x "
            f"--base {checkout}/data/corpus --manifest ~/repo/manifests/m.yaml "
            f"--out $HOME/repo/data/ -o{checkout}/out.pdf -d @{checkout}/q.json "
            f"&& cd {checkout} && echo done"
        )

        manifest = build_ingest_manifest(
            repo=repo,
            base=Path("data/corpus"),
            jurisdiction="nz",
            document_class="statute",
            version="2026-07-10",
            command=command,
            applied_files=[_artifact(repo)],
        )

        assert manifest["command"]["text"] == (
            "UV_PROJECT_ENVIRONMENT=.venv .venv/bin/python -m x --base data/corpus "
            "--manifest manifests/m.yaml --out data/ -o./out.pdf -d @q.json "
            "&& cd . && echo done"
        )


@pytest.mark.parametrize(
    "outside",
    [
        "/Users/someone/axiom-corpus-uc/.venv",
        "/users/someone/x",
        "/private/tmp/de-kindergeld-closure/replay.json",
        "/tmp/usc19.xml",
        "/tmp",
        "/home/runner/x",
        "~/elsewhere/x",
        "file:///Users/someone/x",
    ],
)
def test_build_refuses_a_path_outside_the_checkout(tmp_path, outside: str) -> None:
    repo = _init_repo(tmp_path / "repo")

    with pytest.raises(ManifestLocalPathError) as raised:
        build_ingest_manifest(
            repo=repo,
            base=Path("data/corpus"),
            jurisdiction="nz",
            document_class="statute",
            version="2026-07-10",
            command=f"uv run x --flag={outside} --base data/corpus",
            applied_files=[_artifact(repo)],
        )

    message = str(raised.value)
    assert f"`{outside}`" in message
    assert "<scratchpad>" in message and "docs/ingest-runs/" in message


def test_build_keeps_placeholders_urls_and_run_notes(tmp_path) -> None:
    repo = _init_repo(tmp_path / "repo")
    command = (
        "TMPDIR=<scratchpad> uv run --extra dev axiom-corpus-ingest extract-official-documents "
        "--base data/corpus --manifest <scratchpad>/tmp/replay.json --source-url "
        "https://example.gov/home/tmp/x.pdf?file=/home/statutes/t4.htm#:~:text=Users "
        "(about ~ 2 hours; $HOME-independent; run note: docs/ingest-runs/2026-10-20-x.md)"
    )

    manifest = build_ingest_manifest(
        repo=repo,
        base=Path("data/corpus"),
        jurisdiction="nz",
        document_class="statute",
        version="2026-07-10",
        command=command,
        applied_files=[_artifact(repo)],
    )

    assert manifest["command"]["text"] == command


def _signable(repo: Path) -> dict[str, object]:
    manifest = build_ingest_manifest(
        repo=repo,
        base=Path("data/corpus"),
        jurisdiction="nz",
        document_class="statute",
        version="2026-07-10",
        command="axiom-corpus-ingest extract-nz-legislation",
        applied_files=[_artifact(repo)],
    )
    if not isinstance(manifest.get("coverage"), dict):
        manifest["coverage"] = {}
    return manifest


@pytest.mark.parametrize(
    ("field", "edit"),
    [
        ("command.text", lambda m: m["command"].update(text="x --dir /private/var/folders/ab/T")),
        ("coverage.note", lambda m: m["coverage"].update(note="from ~/Downloads")),
        ("applied_files[0].path", lambda m: m["applied_files"][0].update(path="/tmp/a.jsonl")),
    ],
)
def test_sign_refuses_a_manifest_with_a_local_path_in_any_field(tmp_path, field, edit) -> None:
    repo = _init_repo(tmp_path / "repo")
    manifest = _signable(repo)
    edit(manifest)
    _, private, _ = _keys()

    with pytest.raises(ManifestLocalPathError) as raised:
        sign_ingest_manifest(manifest, private_key=private)
    with pytest.raises(ManifestLocalPathError):
        write_signed_ingest_manifest(repo=repo, manifest=manifest, private_key=private)

    assert f"`{field}` holds" in str(raised.value)
    assert not (repo / ".axiom").exists()


def test_sign_refuses_a_local_path_as_the_key_id(tmp_path) -> None:
    repo = _init_repo(tmp_path / "repo")
    _, private, _ = _keys()

    with pytest.raises(ManifestLocalPathError) as raised:
        sign_ingest_manifest(_signable(repo), private_key=private, key_id="~/keys/ingest-v1")

    assert "`signature.key_id` holds ~/…" in str(raised.value)
    assert sign_ingest_manifest(_signable(repo), private_key=private, key_id="test-v1")


def test_cli_refuses_a_local_path_and_signs_nothing(tmp_path, capsys, monkeypatch) -> None:
    repo = _init_repo(tmp_path / "repo")
    _artifact(repo)
    _, private, _ = _keys()
    monkeypatch.setenv("AXIOM_CORPUS_INGEST_PRIVATE_KEY", private)

    exit_code = main(
        [
            "sign-ingest-manifest",
            "--repo",
            str(repo),
            "--jurisdiction",
            "nz",
            "--document-class",
            "statute",
            "--version",
            "2026-07-10",
            "--command",
            "axiom-corpus-ingest extract-x --manifest /private/tmp/closure/replay.json",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "`/private/tmp/closure/replay.json`" in captured.err
    assert "(nothing was signed)" in captured.err
    assert not (repo / ".axiom").exists()


def test_cli_refuses_a_local_key_id_and_signs_nothing(tmp_path, capsys, monkeypatch) -> None:
    repo = _init_repo(tmp_path / "repo")
    _artifact(repo)
    _, private, _ = _keys()
    monkeypatch.setenv("AXIOM_CORPUS_INGEST_PRIVATE_KEY", private)

    exit_code = main(
        [
            "sign-ingest-manifest",
            "--repo",
            str(repo),
            "--jurisdiction",
            "nz",
            "--document-class",
            "statute",
            "--version",
            "2026-07-10",
            "--command",
            "axiom-corpus-ingest extract-x",
            "--key-id",
            "~/keys/ingest-v1",
        ]
    )

    assert exit_code == 2
    assert "`signature.key_id` holds ~/…" in capsys.readouterr().err
    assert not (repo / ".axiom").exists()


def test_recover_ingest_records_an_outside_fetched_dir_as_a_placeholder(tmp_path) -> None:
    repo = tmp_path / "repo"
    (repo / "fetched").mkdir(parents=True)

    assert recorded_fetched_dir(repo / "fetched", repo) == "fetched"
    assert recorded_fetched_dir(tmp_path / "elsewhere", repo) == "<fetched-dir>"


def test_signing_flow_commands_record_no_local_path() -> None:
    """The fixed commands the repository's signing scripts record."""
    script = (REPO_ROOT / "scripts/sign_release_scopes.sh").read_text()
    batch = (REPO_ROOT / "scripts/recover_ingest_batch.py").read_text()
    commands = re.findall(r'cmd="([^"]*)"', script) + re.findall(r'command="([^"]*)"', batch)

    assert commands
    assert [command for command in commands if find_local_paths(command)] == []


# --- 3. Detection -----------------------------------------------------------

DELIMITERS = " \t\n\"'`=:,;|&()<>[]{}"
_SEGMENT = st.text(alphabet="abcXYZ019._-", min_size=1, max_size=8)
_REST = st.lists(_SEGMENT, max_size=4).map("/".join)
# Arbitrary text that holds no placeholder and no URL, so hides no path.
_PREFIX = st.text(max_size=20).filter(lambda text: "<" not in text and "://" not in text)


@pytest.mark.parametrize(
    ("text", "found"),
    [
        # A placeholder ends at its ">": a newline after it ends the token.
        ("<x>\n/tmp/y", ["/tmp/y"]),
        ("<x>/tmp/y", []),
        # A name with a dot is a redirect, not a placeholder.
        ("python x.py <in.json>/tmp/out.json", ["/tmp/out.json"]),
        # Every kind ends at the same delimiters, so a file: URL cannot swallow
        # the path after it.
        ("file:/a=/Users/x", ["file:/a", "/Users/x"]),
        # A file: URL is not a URL whose query is its own: the path after it is read.
        ("file:///a=/Users/x", ["file:///a", "/Users/x"]),
        ("FILE:///Users/x", ["FILE:///Users/x"]),
        ("PATH=/tmp/t/bin:$PATH", ["/tmp/t/bin"]),
        ("PYTHONPATH=src:/home/u/lib", ["/home/u/lib"]),
        ("2>/tmp/err.log", ["/tmp/err.log"]),
        # A value attached to a short option, and curl's @file.
        ("curl -sLo/Users/u/a.pdf -I/home/u/inc", ["/Users/u/a.pdf", "/home/u/inc"]),
        ("curl -d @/Users/u/q.json --data-binary=@~/b.json", ["/Users/u/q.json", "~/b.json"]),
        # Any case: macOS file systems ignore it.
        (
            "ls /users/u /USERS/u /Private/tmp/x /tmp",
            ["/users/u", "/USERS/u", "/Private/tmp/x", "/tmp"],
        ),
        ("~u/x ~/y", ["~u/x", "~/y"]),
        (
            "${HOME}/a $HOME/b %userprofile%\\c %TEMP%\\d",
            ["${HOME}/a", "$HOME/b", "%userprofile%\\c", "%TEMP%\\d"],
        ),
        ("C:\\Users\\u\\x D:/Users/u", ["C:\\Users\\u\\x", "D:/Users/u"]),
        ("/private/var/folders/ab/T/x", ["/private/var/folders/ab/T/x"]),
        # A path after a colon is read as one, whatever the colon means.
        ("docker -v data:/home/app rsync host:/home/x", ["/home/app", "/home/x"]),
        # Not paths on this machine.
        ("$HOMEBREW_PREFIX/bin ~2 hours ~ 2 hours profile:/x /usr/bin/env /opt/x /tmpfoo", []),
        ("cd ~ && cd $HOME && $HOME-independent", []),
        ("https://example.gov/Users/tmp/ data/home/x ./tmp/y s3://bucket/tmp/x", []),
        ("https://x.gov/?file=/home/statutes/t4.htm#:~:text=a https://x.gov/a,/Users/b", []),
    ],
)
def test_detection_examples(text: str, found: list[str]) -> None:
    assert [text[path.start : path.end] for path in find_local_paths(text)] == found


@settings(max_examples=300, deadline=None)
@given(
    prefix=_PREFIX,
    delimiter=st.sampled_from(DELIMITERS),
    lead=st.sampled_from(["", "-o", "-sLo", "@", "-d@"]),
    root=st.sampled_from(LOCAL_PATH_ROOTS),
    case=st.sampled_from([str, str.lower, str.upper]),
    rest=_REST,
)
def test_every_root_at_a_token_start_is_found(prefix, delimiter, lead, root, case, rest) -> None:
    text = prefix + delimiter + lead + case(root) + "/" + rest
    start = len(prefix) + len(delimiter) + len(lead)

    found = find_local_paths(text)

    # Reported as the path it starts, or inside one that holds it (``C:/Users/...``).
    assert any(path.start <= start < path.end for path in found)


@settings(max_examples=300, deadline=None)
@given(
    prefix=_PREFIX,
    root=st.sampled_from(LOCAL_PATH_ROOTS),
    secret=st.text(alphabet="qwrtpsdfghjkQWRTP", min_size=6, max_size=12),
)
def test_redaction_and_messages_name_only_the_root(prefix, root, secret) -> None:
    assume(secret not in prefix)
    text = f"{prefix} {root}/{secret}/more ~{secret}/x"

    assert secret not in redact_local_paths(text)
    assert secret not in " ".join(manifest_local_path_issues({"command": {"text": text}}))


_URL_SEGMENT = (
    st.sampled_from(
        ["home", "tmp", "Users", "private", "var", "folders", "root", "Volumes", "mnt", "media"]
    )
    | _SEGMENT
)


@settings(max_examples=300, deadline=None)
@given(
    scheme=st.sampled_from(["https://", "http://", "s3://", "gs://"]),
    host=st.sampled_from(["example.gov", "uscode.house.gov", "home", "tmp", "a.b:8080"]),
    segments=st.lists(_URL_SEGMENT, min_size=1, max_size=6),
    query=st.sampled_from(["", "?f=/home/x", "?a=/Users/b&c=/tmp/d", "#:~:text=~/x"]),
)
def test_a_root_inside_a_url_is_never_a_local_path(scheme, host, segments, query) -> None:
    url = f"{scheme}{host}/" + "/".join(segments) + query

    assert find_local_paths(url) == []
    assert find_local_paths(f"--source-url {url}") == []
    assert find_local_paths(f'--source-url="{url}"') == []


@settings(max_examples=300, deadline=None)
@given(segments=st.lists(_URL_SEGMENT, min_size=1, max_size=6))
def test_a_root_inside_a_relative_path_is_never_a_local_path(segments) -> None:
    relative = "data/" + "/".join(segments) + "/"

    assert find_local_paths(relative) == []
    assert find_local_paths(f"./{relative}") == []
    assert find_local_paths(f"<scratchpad>/{relative}") == []


# Command-like text: every kind of path, placeholders, URLs, leads and
# delimiters, so properties see paths in most examples rather than few.
_COMMAND_TOKENS = [
    *LOCAL_PATH_ROOTS,
    "/USERS",
    "/",
    "~/",
    "~u/",
    "~",
    "$HOME/",
    "$HOME",
    "%TEMP%\\",
    "file:/",
    "C:\\Users\\",
    "-o",
    "@",
    "data",
    "x.json",
    "..",
    "<s1>",
    "<a.b>",
    "https://x.gov/?a=",
    *DELIMITERS,
]
_COMMAND = st.lists(st.sampled_from(_COMMAND_TOKENS), max_size=12).map("".join)


@settings(max_examples=500, deadline=None)
@given(a=_COMMAND | st.text(), b=_COMMAND | st.text())
def test_detection_is_additive_over_whitespace(a, b) -> None:
    assert len(find_local_paths(f"{a} {b}")) == len(find_local_paths(a)) + len(find_local_paths(b))


_REFERENCE_TOKENS = [
    *LOCAL_PATH_ROOTS,
    "/USERS",
    "/users",
    "/Tmp",
    "/var/",
    "/opt/",
    "/",
    "Users",
    "tmp",
    "home",
    "data",
    "x1",
    "ab.json",
    "-o",
    "-xy",
    "@",
    "https://x.gov/?a=",
    "s3://b",
    ".",
    "<s1>",
    "<a.b>",
    "<",
    ">",
    *DELIMITERS,
]


def _reference_absolute_starts(text: str) -> set[int]:
    """Where an absolute local path starts, read token by token.

    A root (any case) followed by ``/``, a delimiter or the end, whose token
    begins with nothing or a short-option cluster and ``@``; not after a
    ``<name>`` placeholder, and not later in a word than a URL's ``scheme://``.
    """
    starts = set()
    lowered = text.lower()
    for index in range(len(text)):
        root = next(
            (
                root
                for root in LOCAL_PATH_ROOTS
                if lowered.startswith(root.lower(), index)
                and (
                    index + len(root) == len(text)
                    or text[index + len(root)] == "/"
                    or text[index + len(root)] in DELIMITERS
                )
            ),
            None,
        )
        if root is None:
            continue
        token_start = max((text.rfind(char, 0, index) for char in DELIMITERS), default=-1) + 1
        lead = text[token_start:index]
        if lead.startswith("-") and len(lead) > 1 and lead[1].isascii() and lead[1].isalpha():
            lead = lead[1:].lstrip("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")
        if lead not in ("", "@"):
            continue
        if index == token_start and index and text[index - 1] == ">":
            opening = text.rfind("<", 0, index - 1)
            name = text[opening + 1 : index - 1] if opening >= 0 else ""
            if name and all(char.isascii() and (char.isalnum() or char in "_-") for char in name):
                continue
        word_start = max((text.rfind(char, 0, index) for char in " \t\n\"'`"), default=-1) + 1
        if _reference_has_url_scheme(text[word_start:index]):
            continue
        starts.add(index)
    return starts


_SCHEME_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789+.-")


def _reference_has_url_scheme(word: str) -> bool:
    """Whether ``word`` holds ``scheme://`` for a scheme other than ``file``.

    The scheme is the whole run of scheme characters before ``://``, and starts
    with a letter.
    """
    at = word.find("://")
    while at >= 0:
        begin = at
        while begin > 0 and word[begin - 1] in _SCHEME_CHARS:
            begin -= 1
        scheme = word[begin:at]
        if scheme and scheme[0].isalpha() and scheme.lower() != "file":
            return True
        at = word.find("://", at + 1)
    return False


@settings(max_examples=1000, deadline=None)
@given(st.lists(st.sampled_from(_REFERENCE_TOKENS), max_size=14).map("".join))
def test_detection_agrees_with_a_brute_force_reference(text) -> None:
    found = find_local_paths(text)

    assert all(path.kind == "absolute" for path in found)
    assert {path.start for path in found} == _reference_absolute_starts(text)


_JSON_KEY = st.text(alphabet="abcdefgh_", min_size=1, max_size=6)
_SAFE_STRING = st.text(alphabet="abcXYZ 019._-=,", max_size=12)
_CLEAN_JSON = st.recursive(
    st.none() | st.booleans() | st.integers() | _SAFE_STRING,
    lambda children: st.lists(children, max_size=3)
    | st.dictionaries(_JSON_KEY, children, max_size=3),
    max_leaves=12,
)


@settings(max_examples=300, deadline=None)
@given(
    clean=_CLEAN_JSON,
    outer=_JSON_KEY,
    inner=_JSON_KEY,
    siblings=st.lists(_CLEAN_JSON, max_size=3),
    planted=st.sampled_from(["/Users/a/b", "x ~/b", "PATH=/tmp/t:$PATH", "file:///c", "$HOME/x"]),
)
def test_local_path_fields_reports_exactly_the_planted_field(
    clean, outer, inner, siblings, planted
) -> None:
    assume(outer != "clean")
    payload = {"clean": clean, outer: {inner: [*siblings, planted]}}

    found = {field for field, _ in local_path_fields(payload)}

    assert found == {f"{outer}.{inner}[{len(siblings)}]"}
    assert local_path_fields({"clean": clean}) == []


# --- 4. Relativizing --------------------------------------------------------


@pytest.fixture(scope="module")
def checkout(tmp_path_factory) -> Path:
    """A checkout under a home directory, with a symbolic link that leaves it."""
    home = tmp_path_factory.mktemp("home").resolve()
    path = home / "axiom-corpus"
    (path / "data").mkdir(parents=True)
    (home / "outside").mkdir()
    (path / "link").symlink_to(home / "outside", target_is_directory=True)
    return path


_RELATIVE = st.lists(_SEGMENT.filter(lambda s: s not in {".", ".."}), min_size=1, max_size=5).map(
    "/".join
)


@settings(max_examples=300, deadline=None)
@given(
    relative=_RELATIVE, delimiter=st.sampled_from(" =:\"'"), lead=st.sampled_from(["", "-o", "@"])
)
def test_a_checkout_path_becomes_its_relative_path(checkout, relative, delimiter, lead) -> None:
    for spelling in _spellings(checkout):
        text = f"--x{delimiter}{lead}{spelling}/{relative}"

        expected = os.path.normpath(relative)
        if expected.startswith(("-", "@")) or (lead == "-o" and not expected.startswith(".")):
            expected = "./" + expected
        assert relativize_repo_paths(text, repo=checkout) == f"--x{delimiter}{lead}{expected}"


@contextlib.contextmanager
def _home_above(checkout: Path) -> Iterator[None]:
    """``~`` and ``$HOME`` are the checkout's parent: ``~/axiom-corpus`` is the checkout."""
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("HOME", str(checkout.parent))
        yield


def _relativizing_tokens(checkout: Path) -> list[str]:
    return [
        *_spellings(checkout),
        f"~/{checkout.name}",
        f"$HOME/{checkout.name}",
        "/~",
        "/~cache",
        "/$HOME",
        "/link",
        "/data",
        "/..",
        "/.",
        "/x",
        "/tmp",
        "<s1>",
        "-o",
        "@",
        "file:",
        "https://x/?a=",
        " ",
        "=",
        ":",
        '"',
    ]


@settings(max_examples=1000, deadline=None)
@given(data=st.data())
def test_relativizing_is_idempotent_and_recording_is_a_fixed_point(checkout, data) -> None:
    tokens = _relativizing_tokens(checkout)
    text = data.draw(st.lists(st.sampled_from(tokens), max_size=10).map("".join) | st.text())
    with _home_above(checkout):
        once = relativize_repo_paths(text, repo=checkout)

        assert relativize_repo_paths(once, repo=checkout) == once
        try:
            recorded = recordable_command(text, repo=checkout)
        except ManifestLocalPathError:
            return
        assert find_local_paths(recorded) == []
        assert recordable_command(recorded, repo=checkout) == recorded


@settings(max_examples=500, deadline=None)
@given(segments=st.lists(st.sampled_from(["data", "link", "..", ".", "x", "~", "-o"]), max_size=5))
def test_a_rewrite_names_the_same_file(checkout, segments) -> None:
    original = "/".join([str(checkout), *segments])
    with _home_above(checkout):
        rewrites = repo_rewrites(f"--in {original}", repo=checkout)

    for rewrite in rewrites:
        assert os.path.realpath(checkout / rewrite.relative) == os.path.realpath(original)


@settings(max_examples=300, deadline=None)
@given(
    words=st.lists(st.sampled_from(["uv", "run", "--base", "data/corpus", "x.yaml"]), max_size=4),
    relative=_RELATIVE,
    root=st.sampled_from(LOCAL_PATH_ROOTS),
)
def test_recording_refuses_exactly_when_a_path_leaves_the_checkout(
    checkout, words, relative, root
) -> None:
    inside = f"{checkout}/{relative}"
    outside = f"{root}/elsewhere/{relative}"
    assume(not os.path.realpath(outside).startswith(str(checkout) + "/"))
    base = " ".join(words)
    expected = os.path.normpath(relative)
    if expected.startswith(("-", "@")):
        expected = "./" + expected

    assert recordable_command(f"{base} {inside}", repo=checkout) == f"{base} {expected}"
    with pytest.raises(ManifestLocalPathError):
        recordable_command(f"{base} {inside} {outside}", repo=checkout)


def test_a_rewrite_cannot_turn_a_later_path_into_a_placeholder_path(checkout) -> None:
    command = f"x <{checkout}/a>/tmp/y"

    assert relativize_repo_paths(command, repo=checkout) == "x <a>/tmp/y"
    assert find_local_paths("x <a>/tmp/y") == []
    with pytest.raises(ManifestLocalPathError) as raised:
        recordable_command(command, repo=checkout)
    assert "`/tmp/y`" in str(raised.value)


def test_a_relative_path_that_would_read_as_local_is_written_dot_slash(checkout) -> None:
    """A checkout directory named ``~cache`` or ``~`` is recorded ``./~cache``."""
    with _home_above(checkout):
        command = f"x --dir {checkout}/~cache/y ~/{checkout.name}/~/d -o{checkout}/-v"

        recorded = recordable_command(command, repo=checkout)

    assert recorded == "x --dir ./~cache/y ./~/d -o./-v"
    assert relativize_repo_paths(recorded, repo=checkout) == recorded


def test_a_relative_path_a_shell_would_expand_is_refused(checkout) -> None:
    """``./$HOME/z`` still names the home directory to a shell, so it is not recorded."""
    with pytest.raises(ManifestLocalPathError) as raised:
        recordable_command(f"x --env {checkout}/$HOME/z", repo=checkout)

    assert "`$HOME/z`" in str(raised.value)


def test_a_dot_dot_after_a_symbolic_link_is_judged_where_the_link_points(checkout) -> None:
    """``link`` leaves the checkout, so ``link/../secret.json`` is outside it."""
    assert relativize_repo_paths(f"{checkout}/link/x.json", repo=checkout) == "link/x.json"
    with pytest.raises(ManifestLocalPathError):
        recordable_command(f"--in {checkout}/link/../secret.json", repo=checkout)
    assert recordable_command(f"--in {checkout}/data/../x.json", repo=checkout) == "--in x.json"


def test_a_checkout_path_holding_a_space_is_relativized(tmp_path) -> None:
    """Matched as written; spelled through a symbolic link it is refused, never misread."""
    repo = (tmp_path / "My Repo").resolve()
    (repo / "data").mkdir(parents=True)
    command = f'--base "{repo}/data/corpus" --out={repo}/ -o{repo} --x {repo}'

    assert recordable_command(command, repo=repo) == '--base "data/corpus" --out=./ -o. --x .'
    with pytest.raises(ManifestLocalPathError):
        recordable_command(f"--in {repo}/../elsewhere", repo=repo)


@pytest.mark.parametrize("scheme", ["file:", "FILE:", "file://"])
def test_a_file_url_into_the_checkout_is_refused_not_rewritten(checkout, scheme) -> None:
    command = f"x --url {scheme}{checkout}/data/a.pdf"

    assert relativize_repo_paths(command, repo=checkout) == command
    with pytest.raises(ManifestLocalPathError):
        recordable_command(command, repo=checkout)


def test_a_checkout_path_after_a_placeholder_is_left_relative_to_it(checkout) -> None:
    """``<scratchpad>/...`` names a place in the scratchpad, whatever it looks like."""
    command = f"--in <scratchpad>{checkout}/data"

    assert relativize_repo_paths(command, repo=checkout) == command
    assert recordable_command(command, repo=checkout) == command


def test_a_checkout_path_inside_a_url_is_left_as_the_url_wrote_it(checkout) -> None:
    command = f"--source-url https://x.gov/?a={checkout}/data"

    assert relativize_repo_paths(command, repo=checkout) == command


def test_relativizing_a_nul_byte_does_not_raise(checkout) -> None:
    assert relativize_repo_paths("x /tmp/a\x00b", repo=checkout) == "x /tmp/a\x00b"


def test_a_checkout_reached_through_a_symbolic_link_is_relativized(tmp_path) -> None:
    repo = tmp_path / "axiom-corpus"
    repo.mkdir()
    link = tmp_path / "axiom-corpus-old-name"
    link.symlink_to(repo, target_is_directory=True)

    assert relativize_repo_paths(f"--base {link}/data/corpus", repo=repo) == "--base data/corpus"
    assert relativize_repo_paths(f"--base {repo}/data", repo=link) == "--base data"


def test_git_tracks_no_ingest_manifest_the_scan_cannot_see() -> None:
    """The audit walks the filesystem; every tracked manifest is a .json file it walks."""
    tracked = subprocess.run(
        ["git", "ls-files", "--", ".axiom/ingest-manifests"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()

    assert tracked
    assert [path for path in tracked if not path.endswith(".json")] == []
