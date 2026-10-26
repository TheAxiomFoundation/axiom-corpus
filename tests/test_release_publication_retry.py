"""Publication must recover from transient reads without accepting different bytes."""

import threading
import time
from collections import Counter
from io import BytesIO

import pytest
from botocore.exceptions import ClientError, SSLError

from axiom_corpus.corpus.content_store import R2UnavailableError, RetryPolicy
from axiom_corpus.release import publication
from axiom_corpus.release.manifest import (
    ReleaseManifestError,
    build_unsigned_release_object,
    serialize_release_object,
    sign_release_object,
)
from tests.test_release_publication import FakeR2, _config, _content, _keys, _many_artifact_content


def _error(code="ServiceUnavailable", status=503):
    return ClientError(
        {"Error": {"Code": code}, "ResponseMetadata": {"HTTPStatusCode": status}}, "GetObject"
    )


def _retry(sleeps, attempts=3):
    return RetryPolicy(attempts=attempts, sleep=sleeps.append, jitter=lambda: 0)


class ScriptedR2(FakeR2):
    def __init__(self, objects, answers):
        super().__init__(objects)
        self.answers = list(answers)
        self.reads = 0

    def get_object(self, **kwargs):
        self.reads += 1
        if self.answers:
            answer = self.answers.pop(0)
            if isinstance(answer, BaseException):
                raise answer
            if answer != "stored":
                return {"Body": answer}
        return super().get_object(**kwargs)


def _one_artifact(tmp_path):
    content = _content(tmp_path)
    content["artifacts"] = content["artifacts"][:1]
    entry = content["artifacts"][0]
    return content, entry["r2_key"], (tmp_path / entry["path"]).read_bytes()


@pytest.mark.parametrize("phase", ["existing", "readback", "after-upload"])
@pytest.mark.parametrize("code,status", [("ServiceUnavailable", 503), ("429", 429)])
def test_artifact_transient_reads_retry_both_verification_reads(tmp_path, phase, code, status):
    content, key, raw = _one_artifact(tmp_path)
    answers = [_error(code, status)] if phase == "existing" else ["stored", _error(code, status)]
    client = ScriptedR2({} if phase == "after-upload" else {key: raw}, answers)
    sleeps = []
    report = publication.stage_release_artifacts(
        tmp_path,
        release_content=content,
        config=_config(),
        client=client,
        read_retry=_retry(sleeps),
    )
    assert report.verified_keys == (key,)
    assert report.uploaded_count == (phase == "after-upload")
    assert client.reads == 3
    assert sleeps == [0.5]


def test_persistent_transient_read_exhausts_its_budget_without_uploading(tmp_path):
    content, key, raw = _one_artifact(tmp_path)
    client = ScriptedR2({key: raw}, [_error()] * 4)
    sleeps = []
    with pytest.raises(R2UnavailableError, match="gave up after 3 attempts"):
        publication.stage_release_artifacts(
            tmp_path,
            release_content=content,
            config=_config(),
            client=client,
            read_retry=_retry(sleeps),
        )
    assert client.reads == 3
    assert sleeps == [0.5, 1]
    assert not client.uploads


@pytest.mark.parametrize(
    "error",
    [
        _error("AccessDenied", 403),
        _error("NotImplemented", 501),
        SSLError(endpoint_url="https://r2.invalid", error="TLS"),
    ],
)
def test_nontransient_read_errors_do_not_retry(tmp_path, error):
    content, key, raw = _one_artifact(tmp_path)
    client = ScriptedR2({key: raw}, [error])
    sleeps = []
    with pytest.raises(type(error)):
        publication.stage_release_artifacts(
            tmp_path,
            release_content=content,
            config=_config(),
            client=client,
            read_retry=_retry(sleeps),
        )
    assert client.reads == 1
    assert not sleeps and not client.uploads


def test_absence_is_not_retried_and_still_requires_post_upload_verification(tmp_path):
    content, key, _ = _one_artifact(tmp_path)
    client = ScriptedR2({}, [_error("NoSuchKey", 404)])
    sleeps = []
    report = publication.stage_release_artifacts(
        tmp_path,
        release_content=content,
        config=_config(),
        client=client,
        read_retry=_retry(sleeps),
    )
    assert client.reads == 2 and not sleeps
    assert client.uploads == [key] and report.uploaded_count == 1


@pytest.mark.parametrize("malformed", [None, 7, b"xxx"])
def test_malformed_or_corrupt_readbacks_do_not_retry_or_write(tmp_path, malformed):
    content, key, raw = _one_artifact(tmp_path)

    class BadBody(BytesIO):
        def read(self, *args):
            return malformed

    body = None if malformed is None else BadBody()
    client = ScriptedR2({key: raw}, [body])
    sleeps = []
    # A corrupt byte stream must terminate, unlike the malformed non-byte body.
    if isinstance(malformed, bytes):
        client.answers = [BytesIO(malformed)]
    with pytest.raises(ReleaseManifestError):
        publication.stage_release_artifacts(
            tmp_path,
            release_content=content,
            config=_config(),
            client=client,
            read_retry=_retry(sleeps),
        )
    assert client.reads == 1 and not sleeps and not client.uploads


def test_midstream_failure_closes_body_and_restarts_hash_and_length(tmp_path):
    content, key, raw = _one_artifact(tmp_path)

    class BrokenBody(BytesIO):
        reads = 0

        def read(self, size=-1):
            self.reads += 1
            if self.reads == 1:
                return super().read(1)
            raise TimeoutError("connection lost mid-body")

    broken = BrokenBody(raw)

    class CheckedR2(ScriptedR2):
        def get_object(self, **kwargs):
            if self.reads:
                assert broken.closed, "retry started before failed body closed"
            return super().get_object(**kwargs)

    client = CheckedR2({key: raw}, [broken])
    report = publication.stage_release_artifacts(
        tmp_path, release_content=content, config=_config(), client=client, read_retry=_retry([])
    )
    assert report.verified_keys == (key,) and client.reads == 3


def test_integrity_failure_after_transient_read_still_fails_closed(tmp_path):
    content, key, raw = _one_artifact(tmp_path)
    client = ScriptedR2({key: raw}, ["stored", _error(), BytesIO(b"x" * len(raw))])
    sleeps = []
    with pytest.raises(ReleaseManifestError, match="sha256 mismatch"):
        publication.stage_release_artifacts(
            tmp_path,
            release_content=content,
            config=_config(),
            client=client,
            read_retry=_retry(sleeps),
        )
    assert client.reads == 3 and sleeps == [0.5] and not client.uploads


def test_duplicate_keys_serialize_through_body_close_and_distinct_keys_overlap(tmp_path):
    content = _many_artifact_content(tmp_path)
    original = content["artifacts"][0]
    for index in range(8):
        path = f"data/corpus/sources/nz/statute/v1/duplicate-{index}.html"
        (tmp_path / path).write_bytes((tmp_path / original["path"]).read_bytes())
        content["artifacts"].append({**original, "path": path, "artifact_class": "sources"})
    objects = {
        entry["r2_key"]: (tmp_path / entry["path"]).read_bytes() for entry in content["artifacts"]
    }
    active, maximum = Counter(), Counter()
    state = {"max_total": 0}
    lock = threading.Lock()

    class HeldBody(BytesIO):
        def __init__(self, raw, key):
            super().__init__(raw)
            self.key = key

        def read(self, size=-1):
            time.sleep(0.005)
            return super().read(size)

        def close(self):
            if not self.closed:
                with lock:
                    active[self.key] -= 1
            super().close()

    class ConcurrentR2(FakeR2):
        def get_object(self, **kwargs):
            key = kwargs["Key"]
            with lock:
                active[key] += 1
                maximum[key] = max(maximum[key], active[key])
                state["max_total"] = max(state["max_total"], sum(active.values()))
            return {"Body": HeldBody(self.objects[key], key)}

    client = ConcurrentR2(objects)
    report = publication.stage_release_artifacts(
        tmp_path, release_content=content, config=_config(), client=client, workers=8
    )
    assert max(maximum.values()) == 1 and state["max_total"] > 1
    assert not any(active.values())
    assert report.verified_keys == tuple(entry["r2_key"] for entry in content["artifacts"])
    assert report.artifact_count == len(content["artifacts"]) and not client.uploads


@pytest.mark.parametrize("phase", ["existing", "readback", "after-upload"])
def test_signed_object_reads_retry_without_changing_signed_bytes(tmp_path, phase):
    private, public = _keys()
    signed = sign_release_object(
        build_unsigned_release_object(_content(tmp_path)), private_key=private
    )
    key = f"releases/{signed['release']}/{signed['content_sha256']}.json"
    raw = serialize_release_object(signed)
    answers = [_error()] if phase == "existing" else ["stored", _error()]
    client = ScriptedR2({} if phase == "after-upload" else {key: raw}, answers)
    sleeps = []
    assert (
        publication.stage_signed_release_object(
            signed, public_key=public, config=_config(), client=client, read_retry=_retry(sleeps)
        )
        == key
    )
    assert client.objects[key] == raw and client.reads == 3 and sleeps == [0.5]


def test_signed_object_read_exhaustion_does_not_report_success(tmp_path):
    private, public = _keys()
    signed = sign_release_object(
        build_unsigned_release_object(_content(tmp_path)), private_key=private
    )
    client = ScriptedR2({}, [_error()] * 4)
    with pytest.raises(R2UnavailableError, match="gave up after 3 attempts"):
        publication.stage_signed_release_object(
            signed, public_key=public, config=_config(), client=client, read_retry=_retry([])
        )
    assert client.reads == 3 and not client.uploads


@pytest.mark.parametrize("signed_object", [False, True])
@pytest.mark.parametrize(
    "code,status", [("ConditionalRequestConflict", 409), ("PreconditionFailed", 412)]
)
def test_conditional_conflict_readback_retries_and_still_verifies_exact_bytes(
    tmp_path, signed_object, code, status
):
    class RacingR2(ScriptedR2):
        def put_object(self, **kwargs):
            body = kwargs["Body"]
            self.objects[kwargs["Key"]] = body.read() if hasattr(body, "read") else bytes(body)
            raise _error(code, status)

    client = RacingR2({}, ["stored", _error()])
    sleeps = []
    if signed_object:
        private, public = _keys()
        signed = sign_release_object(
            build_unsigned_release_object(_content(tmp_path)), private_key=private
        )
        key = publication.stage_signed_release_object(
            signed, public_key=public, config=_config(), client=client, read_retry=_retry(sleeps)
        )
        assert client.objects[key] == serialize_release_object(signed)
    else:
        content, key, raw = _one_artifact(tmp_path)
        report = publication.stage_release_artifacts(
            tmp_path,
            release_content=content,
            config=_config(),
            client=client,
            read_retry=_retry(sleeps),
        )
        assert client.objects[key] == raw and report.reused_count == 1
    assert client.reads == 4 and sleeps == [0.5]


@pytest.mark.parametrize("signed_object", [False, True])
def test_publication_uses_separate_single_attempt_reader_and_standard_writer(
    tmp_path, monkeypatch, signed_object
):
    calls = []
    writer, reader = FakeR2(), FakeR2()
    reader.objects = writer.objects

    def client_factory(config, **kwargs):
        calls.append(kwargs)
        return reader if kwargs.get("sdk_retries") is False else writer

    monkeypatch.setattr(publication, "make_r2_client", client_factory)
    if signed_object:
        private, public = _keys()
        signed = sign_release_object(
            build_unsigned_release_object(_content(tmp_path)), private_key=private
        )
        publication.stage_signed_release_object(signed, public_key=public, config=_config())
    else:
        publication.stage_release_artifacts(
            tmp_path, release_content=_content(tmp_path), config=_config(), workers=3
        )
    assert len(calls) == 2
    assert "sdk_retries" not in calls[0] and calls[1]["sdk_retries"] is False
    assert writer.uploads and not reader.uploads
