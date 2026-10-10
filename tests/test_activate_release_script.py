from __future__ import annotations

import argparse
import json
from types import SimpleNamespace

import pytest

import scripts.activate_release as activate_release
from scripts.activate_release import _load_release_object


def _args(tmp_path, payload, *, release="release-one", content_sha="a" * 64):
    path = tmp_path / "release-object.json"
    path.write_text(json.dumps(payload))
    return argparse.Namespace(
        release_object=path,
        release=release,
        content_sha=content_sha,
        credentials_file=None,
        r2_bucket=None,
        r2_endpoint=None,
    )


def test_local_release_object_matches_requested_identity(tmp_path):
    payload = {"release": "release-one", "content_sha256": "a" * 64}

    assert _load_release_object(_args(tmp_path, payload)) == payload


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (
            {"release": "release-two", "content_sha256": "a" * 64},
            "expected release 'release-one'",
        ),
        (
            {"release": "release-one", "content_sha256": "b" * 64},
            "expected content_sha256",
        ),
    ],
)
def test_local_release_object_rejects_requested_identity_mismatch(
    tmp_path, payload, message
):
    with pytest.raises(SystemExit, match=message):
        _load_release_object(_args(tmp_path, payload))


def test_fetched_release_object_rejects_requested_key_identity_mismatch(monkeypatch):
    payload = {"release": "release-two", "content_sha256": "a" * 64}

    class Client:
        def get_object(self, **_kwargs):
            return {"Body": SimpleNamespace(read=lambda: json.dumps(payload).encode())}

    monkeypatch.setattr(
        activate_release,
        "load_r2_config",
        lambda **_kwargs: SimpleNamespace(bucket="corpus"),
    )
    monkeypatch.setattr(activate_release, "make_r2_client", lambda _config: Client())
    args = argparse.Namespace(
        release_object=None,
        release="release-one",
        content_sha="a" * 64,
        credentials_file=None,
        r2_bucket=None,
        r2_endpoint=None,
    )

    with pytest.raises(SystemExit, match="expected release 'release-one'"):
        _load_release_object(args)
