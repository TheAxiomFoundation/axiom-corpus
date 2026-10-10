"""Register a signed immutable corpus release without moving serving."""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Sequence
from contextlib import suppress
from pathlib import Path

from axiom_corpus.corpus.supabase import (
    DEFAULT_ACCESS_TOKEN_ENV,
    DEFAULT_AXIOM_SUPABASE_URL,
    _delete_release_activation_upload,
    _management_api_post_json_with_curl,
    _project_ref_from_url,
    _stage_release_activation_upload,
)
from axiom_corpus.release.manifest import (
    RELEASE_OBJECT_PUBLIC_KEY_ENV,
    verify_release_object,
)

STAGE_RELEASE_OBJECT_QUERY = (
    "SELECT corpus.stage_corpus_release_object("
    "corpus.load_release_activation_upload("
    "$1::text, $2::text, $3::text, $4::text"
    ")) AS result"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-object", type=Path, required=True)
    parser.add_argument("--release", required=True)
    parser.add_argument("--content-sha", required=True)
    parser.add_argument("--supabase-url", default=DEFAULT_AXIOM_SUPABASE_URL)
    parser.add_argument("--expected-project-ref", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    public_key = os.environ.get(RELEASE_OBJECT_PUBLIC_KEY_ENV)
    access_token = os.environ.get(DEFAULT_ACCESS_TOKEN_ENV)
    if not public_key:
        raise SystemExit(f"{RELEASE_OBJECT_PUBLIC_KEY_ENV} environment variable is required")
    if not access_token:
        raise SystemExit(f"{DEFAULT_ACCESS_TOKEN_ENV} environment variable is required")

    release_object = json.loads(args.release_object.read_bytes())
    verify_release_object(release_object, public_key=public_key)
    if release_object.get("release") != args.release:
        raise SystemExit("release object name does not match --release")
    if release_object.get("content_sha256") != args.content_sha:
        raise SystemExit("release object digest does not match --content-sha")

    project_ref = _project_ref_from_url(args.supabase_url)
    if project_ref != args.expected_project_ref:
        raise SystemExit(
            f"refusing to stage in Supabase project {project_ref!r}: "
            f"expected {args.expected_project_ref!r}"
        )
    endpoint = f"https://api.supabase.com/v1/projects/{project_ref}/database/query"
    upload_id, object_sha256 = _stage_release_activation_upload(
        release_object,
        endpoint=endpoint,
        access_token=access_token,
    )
    try:
        rows = _management_api_post_json_with_curl(
            endpoint,
            payload={
                "query": STAGE_RELEASE_OBJECT_QUERY,
                "parameters": [upload_id, args.release, args.content_sha, object_sha256],
                "read_only": False,
            },
            access_token=access_token,
            timeout=600,
        )
        if (
            not isinstance(rows, list)
            or len(rows) != 1
            or not isinstance(rows[0], dict)
            or set(rows[0]) != {"result"}
        ):
            raise RuntimeError(f"unexpected release object staging query response: {rows!r}")
        result = rows[0]["result"]
        if not isinstance(result, dict) or result.get("staged") is not True:
            raise RuntimeError(f"unexpected release object staging response: {result!r}")
        if result.get("release") != args.release:
            raise RuntimeError("staged release name does not match the requested object")
        if result.get("content_sha256") != args.content_sha:
            raise RuntimeError("staged release digest does not match the requested object")
    finally:
        with suppress(Exception):
            _delete_release_activation_upload(
                upload_id,
                endpoint=endpoint,
                access_token=access_token,
            )

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
