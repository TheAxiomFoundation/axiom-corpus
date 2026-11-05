"""Failure diagnostics follow evidence in FetchReport, without fetching bytes.

Invariants:
* the credentials hint appears exactly when a serialized authentication error
  is present (a symlink retains its own remedy);
* every failure kind is reported once with its file count, including several
  kinds in one file's source errors; the first 20 distinct unknown reasons
  survive verbatim, and the message counts the rest;
* the same report, including a different insertion order, gives the same text;
* an exception's own text adds no failure kind and hides none, unless it copies
  a shape the store or botocore writes: a configured source's name after '; ',
  the errno right after ': ', a trailing ': no source holds it', or botocore's
  authentication text;
* one summary checks each directory its paths share once.
"""

from __future__ import annotations

import errno
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError
from hypothesis import HealthCheck, example, given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus import resolver as resolver_module
from axiom_corpus.corpus.content_store import ContentCache, FetchReport
from axiom_corpus.corpus.corpus_locks import LockEntry
from axiom_corpus.corpus.resolver import CorpusNotMaterializedError, CorpusResolver

PREFIX = "data/corpus/provisions/nz/statute"
CREDENTIAL_HINT = (
    "Check R2 credentials (~/.config/axiom-foundation/r2-credentials.json) "
    "or run `axiom-corpus-ingest corpus fetch` with network access."
)
HINTS = {
    "ENOSPC": "The disk ran out of space. Free disk space",
    "No source holds it": "No configured source has the object.",
    "Authentication": CREDENTIAL_HINT,
    "Symlinks": "Corpus files are placed as regular files, never through symlinks: "
    "remove the symlink and fetch again.",
}
AUTH_CODES = (
    "AccessDenied",
    "InvalidAccessKeyId",
    "SignatureDoesNotMatch",
    "ExpiredToken",
    "InvalidToken",
    "TokenRefreshRequired",
    "RequestExpired",
    "401",
    "403",
)


def _client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": "request refused"}}, "GetObject")


AUTH_ERRORS = [
    *[_client_error(code) for code in AUTH_CODES],
    NoCredentialsError(),
    PartialCredentialsError(provider="explicit", cred_var="aws_secret_access_key"),
]
DISK_REASON = f"OSError: {OSError(errno.ENOSPC, 'No space left on device')}"
MISSING_REASON = "ContentStoreError: cannot obtain object (sha256 abc, 1 bytes): no source holds it"
UNKNOWN_REASON = "RuntimeError: unexpected checksum failure"
# ensure() takes source names from the resolver and never opens these stubs.
SOURCES = [SimpleNamespace(name=name) for name in ("r2", "git", "mirror", "local")]


def _source_failure(error: BaseException) -> str:
    # ensure_cached/_stream_to retain the source name and str(exc), then the
    # materialize worker adds the enclosing exception's type.
    return f"ContentStoreError: cannot obtain object (sha256 abc, 1 bytes): r2: {error}"


def _message(repo: Path, failed: dict[str, str]) -> str:
    report = FetchReport(failed=dict(failed))
    entries = [LockEntry(path=path, sha256="a" * 64, size=1) for path in failed]
    resolver = CorpusResolver(repo, cache=ContentCache(repo / "cache"), sources=SOURCES)
    with patch.object(resolver_module, "materialize_resilient", return_value=report):
        if not failed:
            assert resolver.ensure(entries).ok
            return ""
        with pytest.raises(CorpusNotMaterializedError) as raised:
            resolver.ensure(entries)
    return str(raised.value)


def _assert_hints(message: str, *expected: str) -> None:
    for kind, hint in HINTS.items():
        assert message.count(hint) == int(kind in expected), message


@pytest.mark.parametrize("wrapped", [False, True], ids=["filesystem", "source"])
def test_ensure_explains_enospc(tmp_path: Path, wrapped: bool) -> None:
    error = OSError(errno.ENOSPC, "No space left on device")
    reason = _source_failure(error) if wrapped else f"OSError: {error}"
    message = _message(tmp_path, {f"{PREFIX}/disk.jsonl": reason})
    _assert_hints(message, "ENOSPC")
    assert "ENOSPC (1 file(s))" in message
    assert "corpus worktree and cache" in message


def test_ensure_explains_missing_source(tmp_path: Path) -> None:
    message = _message(tmp_path, {f"{PREFIX}/missing.jsonl": MISSING_REASON})
    _assert_hints(message, "No source holds it")
    assert "No source holds it (1 file(s))" in message
    assert "Check which sources are configured and whether an earlier fetch failed." in message


@pytest.mark.parametrize(
    "error", AUTH_ERRORS, ids=[*AUTH_CODES, "no-credentials", "partial-credentials"]
)
def test_ensure_explains_authentication(tmp_path: Path, error: BaseException) -> None:
    message = _message(tmp_path, {f"{PREFIX}/auth.jsonl": _source_failure(error)})
    _assert_hints(message, "Authentication")
    assert "Authentication (1 file(s))" in message
    assert CREDENTIAL_HINT in message  # Pin the entire existing path and advice.


@pytest.mark.parametrize(
    "reason",
    [
        UNKNOWN_REASON,
        "unknown error",
        "RuntimeError: mentions AccessDenied, 401, 403 and authentication",
        "RuntimeError: expected 403 bytes in path AccessDenied.jsonl",
        _source_failure(
            ClientError(
                {"Error": {"Code": "ServiceUnavailable", "Message": "AccessDenied"}}, "GetObject"
            )
        ),
        _source_failure(_client_error("ServiceUnavailable")),
        _source_failure(_client_error("NoSuchKey")),
        "PermissionError: [Errno 13] Permission denied",
    ],
)
def test_ensure_keeps_unknown_reason_without_guessing(tmp_path: Path, reason: str) -> None:
    message = _message(tmp_path, {f"{PREFIX}/unknown.jsonl": reason})
    _assert_hints(message)
    assert f"Other errors (1 file(s)): {reason}" in message


@pytest.mark.parametrize(("files", "more"), [(20, None), (21, 1), (500, 480)])
def test_ensure_bounds_unknown_reasons_and_counts_the_rest(
    tmp_path: Path, files: int, more: int | None
) -> None:
    # The store's reasons name the file, so each one differs.
    failed = {
        f"{PREFIX}/{index:03}.jsonl": (
            f"ContentStoreError: cannot obtain {PREFIX}/{index:03}.jsonl "
            f"(sha256 {index:064x}, 1 bytes): r2: {UNKNOWN_REASON}"
        )
        for index in range(files)
    }
    message = _message(tmp_path, failed)
    assert f"{files} locked corpus file(s) could not be fetched" in message
    assert f"Other errors ({files} file(s)):" in message
    # The first failure opens the message, and the summary then repeats it.
    assert message.count("ContentStoreError:") == 21
    assert message.endswith(f"; and {more} more") == (more is not None)
    assert " more" not in message.replace(f"; and {more} more", "")
    assert message == _message(tmp_path, dict(reversed(list(failed.items()))))


def test_ensure_lists_a_repeated_unknown_reason_once(tmp_path: Path) -> None:
    failed = {f"{PREFIX}/{index}.jsonl": UNKNOWN_REASON for index in range(2)}
    message = _message(tmp_path, failed)
    assert f"Other errors (2 file(s)): {UNKNOWN_REASON}" in message
    # Once after the first failure's path, and once in the summary.
    assert message.count(UNKNOWN_REASON) == 2


def test_ensure_summarizes_all_failure_kinds_and_counts(tmp_path: Path) -> None:
    reasons = [
        DISK_REASON,
        DISK_REASON,
        MISSING_REASON,
        MISSING_REASON,
        MISSING_REASON,
        _source_failure(AUTH_ERRORS[0]),
        _source_failure(AUTH_ERRORS[1]),
        UNKNOWN_REASON,
        "RuntimeError: a second unknown reason",
    ]
    failed = {f"{PREFIX}/{index}.jsonl": reason for index, reason in enumerate(reasons)}
    message = _message(tmp_path, failed)
    _assert_hints(message, "ENOSPC", "No source holds it", "Authentication")
    for kind, count in [
        ("ENOSPC", 2),
        ("No source holds it", 3),
        ("Authentication", 2),
        ("Other errors", 2),
    ]:
        assert f"{kind} ({count} file(s))" in message
    assert UNKNOWN_REASON in message
    assert "RuntimeError: a second unknown reason" in message
    assert "9 locked corpus file(s) could not be fetched" in message
    assert message == _message(tmp_path, dict(reversed(list(failed.items()))))


def test_ensure_counts_multiple_source_failure_kinds_once_per_file(tmp_path: Path) -> None:
    reason = f"{_source_failure(AUTH_ERRORS[0])}; mirror: {AUTH_ERRORS[1]}; local: {DISK_REASON}"
    message = _message(tmp_path, {f"{PREFIX}/combined.jsonl": reason})
    _assert_hints(message, "ENOSPC", "Authentication")
    assert "Authentication (1 file(s))" in message
    assert "ENOSPC (1 file(s))" in message


def _kinds(message: str) -> set[str]:
    return {kind for kind in (*HINTS, "Other errors") if f"{kind} (" in message}


def _denied(text: str) -> ClientError:
    return ClientError({"Error": {"Code": "AccessDenied", "Message": text}}, "GetObject")


def _refused(filename: str) -> PermissionError:
    return PermissionError(errno.EACCES, "Permission denied", filename)


def _disk_full(filename: str) -> OSError:
    return OSError(errno.ENOSPC, "No space left on device", filename)


@pytest.mark.parametrize(
    ("error", "kind"),
    [
        (_denied("request refused; RequestId: abc"), "Authentication"),
        (
            PartialCredentialsError(
                provider="env; backend: metadata", cred_var="aws_secret_access_key"
            ),
            "Authentication",
        ),
        (_refused("/archive/[Errno 28].json"), "Other errors"),
        (_disk_full("/cache; tmp: object"), "ENOSPC"),
    ],
    ids=["message-separator", "provider-separator", "quoted-errno", "filename-separator"],
)
def test_ensure_reads_the_kind_past_an_exceptions_own_text(
    tmp_path: Path, error: BaseException, kind: str
) -> None:
    reason = _source_failure(error)
    message = _message(tmp_path, {f"{PREFIX}/text.jsonl": reason})
    assert _kinds(message) == {kind}, message
    assert f"{kind} (1 file(s))" in message


# An exception's text can still imitate the store in two ways, and these fragments
# leave both out: none names a configured source, and no ": " can directly precede the errno.
TEXT_FRAGMENTS = ["; ", ": ", "RequestId", "backend", "/[Errno 28].json", "a", " "]


@settings(
    max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(text=st.lists(st.sampled_from(TEXT_FRAGMENTS), max_size=8).map("".join))
def test_generated_exception_text_leaves_the_kind_alone(tmp_path: Path, text: str) -> None:
    for error, kind in [
        (_denied(text), "Authentication"),
        (_refused(text), "Other errors"),
        (_disk_full(text), "ENOSPC"),
    ]:
        message = _message(tmp_path, {f"{PREFIX}/text.jsonl": _source_failure(error)})
        assert _kinds(message) == {kind}, message


@pytest.mark.parametrize(
    ("reason", "kind"),
    [
        ("RuntimeError: request refused: no source holds it", "No source holds it"),
        (
            "ClientError: An error occurred (ServiceUnavailable) when calling the GetObject "
            "operation: An error occurred (AccessDenied) when calling the GetObject operation",
            "Authentication",
        ),
    ],
    ids=["no-source-suffix", "quoted-auth-error"],
)
def test_an_exception_that_copies_a_known_shape_reads_as_that_kind(
    tmp_path: Path, reason: str, kind: str
) -> None:
    # str(exc) is all the store keeps, so these two read as the shape they copy.
    message = _message(tmp_path, {f"{PREFIX}/text.jsonl": reason})
    assert _kinds(message) == {kind}, message


def test_only_a_configured_source_starts_a_new_source_failure(tmp_path: Path) -> None:
    failed = {f"{PREFIX}/text.jsonl": f"{_source_failure(AUTH_ERRORS[0])}; mirror: boom"}
    message = _message(tmp_path, failed)
    assert _kinds(message) == {"Authentication", "Other errors"}, message
    entries = [LockEntry(path=path, sha256="a" * 64, size=1) for path in failed]
    alone = CorpusResolver(
        tmp_path, cache=ContentCache(tmp_path / "cache"), sources=[SimpleNamespace(name="r2")]
    )
    with (
        patch.object(
            resolver_module, "materialize_resilient", return_value=FetchReport(failed=dict(failed))
        ),
        pytest.raises(CorpusNotMaterializedError) as raised,
    ):
        alone.ensure(entries)
    assert _kinds(str(raised.value)) == {"Authentication"}, raised.value


@pytest.mark.parametrize("name", ["r2+mirror.[x]", "mirror|backup", "mirror(1)", "x[y"])
def test_a_source_name_with_regex_syntax_still_starts_a_new_failure(
    tmp_path: Path, name: str
) -> None:
    reason = f"{_source_failure(AUTH_ERRORS[0])}; {name}: {UNKNOWN_REASON}"
    sources = [SimpleNamespace(name="r2"), SimpleNamespace(name=name)]
    message = resolver_module._fetch_failure_hints(
        tmp_path, {f"{PREFIX}/text.jsonl": reason}, sources
    )
    assert _kinds(message) == {"Authentication", "Other errors"}, message


def test_summary_checks_each_shared_directory_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    files = 50
    failed = {f"{PREFIX}/{index:02}.jsonl": UNKNOWN_REASON for index in range(files)}
    checks: Counter[Path] = Counter()
    is_symlink = Path.is_symlink

    def counted(path: Path) -> bool:
        checks[path] += 1
        return is_symlink(path)

    monkeypatch.setattr(Path, "is_symlink", counted)
    resolver_module._fetch_failure_hints(tmp_path, failed, SOURCES)
    assert set(checks.values()) == {1}
    assert len(checks) == files + len(PREFIX.split("/"))


def test_ensure_counts_every_file_under_a_symlinked_directory(tmp_path: Path) -> None:
    parent, leaf = PREFIX.rsplit("/", 1)
    (tmp_path / parent).mkdir(parents=True)
    (tmp_path / parent / leaf).symlink_to(tmp_path / "elsewhere")
    failed = {f"{PREFIX}/{index}.jsonl": UNKNOWN_REASON for index in range(3)}
    message = _message(tmp_path, failed)
    _assert_hints(message, "Symlinks")
    assert "Symlinks (3 file(s))" in message
    assert "Other errors" not in message


def test_ensure_retains_unknown_source_error_alongside_known_error(tmp_path: Path) -> None:
    reason = f"{_source_failure(AUTH_ERRORS[0])}; git: {UNKNOWN_REASON}"
    message = _message(tmp_path, {f"{PREFIX}/combined.jsonl": reason})
    _assert_hints(message, "Authentication")
    assert f"Other errors (1 file(s)): {reason}" in message


@pytest.mark.parametrize("mixed", [False, True])
def test_ensure_keeps_symlink_remedy(tmp_path: Path, mixed: bool) -> None:
    path = f"{PREFIX}/0-link.jsonl"
    target = tmp_path / path
    target.parent.mkdir(parents=True)
    target.symlink_to(tmp_path / "absent")
    failed = {path: "ContentStoreError: refusing to write through a symlink"}
    if mixed:
        failed[f"{PREFIX}/1-auth.jsonl"] = _source_failure(AUTH_ERRORS[0])
    message = _message(tmp_path, failed)
    _assert_hints(message, "Symlinks", *(["Authentication"] if mixed else []))
    assert "Symlinks (1 file(s))" in message


PROPERTY_CASES = [
    (("ENOSPC",), DISK_REASON),
    (("No source holds it",), MISSING_REASON),
    *[(("Authentication",), _source_failure(error)) for error in AUTH_ERRORS],
    (("Other errors",), UNKNOWN_REASON),
    (("Other errors",), "RuntimeError: mentions 403 and AccessDenied"),
    (("ENOSPC", "Authentication"), f"{_source_failure(AUTH_ERRORS[0])}; local: {DISK_REASON}"),
    (
        ("Authentication", "Other errors"),
        f"{_source_failure(AUTH_ERRORS[0])}; git: {UNKNOWN_REASON}",
    ),
]


@settings(
    max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@example(cases=[PROPERTY_CASES[0], PROPERTY_CASES[1], PROPERTY_CASES[2], PROPERTY_CASES[-1]])
@example(cases=[])
@given(cases=st.lists(st.sampled_from(PROPERTY_CASES), max_size=25))
def test_generated_fetch_reports_preserve_diagnostic_invariants(
    tmp_path: Path, cases: list[tuple[tuple[str, ...], str]]
) -> None:
    failed = {f"{PREFIX}/{index:02}.jsonl": reason for index, (_kind, reason) in enumerate(cases)}
    counts = Counter(kind for kinds, _reason in cases for kind in kinds)
    message = _message(tmp_path, failed)
    _assert_hints(message, *counts)
    for kind, count in counts.items():
        assert message.count(f"{kind} ({count} file(s)):") == 1
    for kinds, reason in cases:
        if "Other errors" in kinds:
            assert reason in message
    assert message == _message(tmp_path, failed)
    assert message == _message(tmp_path, dict(reversed(list(failed.items()))))
