"""Move corpus serving to a signed release, per scope.

Publication (``scripts/publish_corpus.py``) stages content and signs the release
object but does NOT move serving. Activation is a separate, explicit step
because it repoints the per-scope serving map — one active release+version per
(jurisdiction, document_class) — and can displace another jurisdiction's
release. Overlapping scopes resolve last-activation-wins, and every takeover is
recorded in ``corpus.scope_activation_history``.

The signed release object is read from a local file (e.g. the ``--output`` of a
publish run) or fetched from the canonical R2 bucket by name + content sha.

    # Preview the takeover without moving serving:
    uv run --extra dev python scripts/activate_release.py \
      --release nz-rulespec-2026-07-18 \
      --content-sha <sha> \
      --credentials-file ~/.config/axiom-foundation/r2-credentials.json \
      --dry-run

    # Activate:
    uv run --extra dev python scripts/activate_release.py \
      --release-object out/nz-release-object.json

Environment: ``AXIOM_CORPUS_RELEASE_PUBLIC_KEY`` (Ed25519 verify key) and
``SUPABASE_ACCESS_TOKEN`` (Management API credential for the activation RPC).
"""

from __future__ import annotations

import argparse
import json
import os
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from axiom_corpus.corpus.r2 import load_r2_config, make_r2_client
from axiom_corpus.corpus.supabase import (
    DEFAULT_ACCESS_TOKEN_ENV,
    DEFAULT_AXIOM_SUPABASE_URL,
    activate_corpus_release,
    preview_corpus_release_activation,
)
from axiom_corpus.release.manifest import (
    RELEASE_OBJECT_PUBLIC_KEY_ENV,
    release_object_r2_key,
)

# Serving-moving activation only ever targets a bare Supabase project URL. A
# stricter shape than the shared _project_ref_from_url helper keeps a mistyped
# or credential-bearing --supabase-url from silently activating elsewhere.
_SUPABASE_PROJECT_URL = re.compile(r"^https://(?P<ref>[a-z0-9]{16,40})\.supabase\.co/?$")


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"{name} environment variable is required")
    return value


def _load_release_object(args: argparse.Namespace) -> dict[str, Any]:
    if args.release_object is not None:
        return json.loads(Path(args.release_object).read_bytes())
    if not args.release or not args.content_sha:
        raise SystemExit(
            "provide --release-object PATH, or both --release and --content-sha "
            "to fetch the signed object from the canonical R2 bucket"
        )
    config = load_r2_config(
        credential_path=args.credentials_file,
        bucket=args.r2_bucket,
        endpoint_url=args.r2_endpoint,
    )
    client = make_r2_client(config)
    key = release_object_r2_key(args.release, args.content_sha)
    body = client.get_object(Bucket=config.bucket, Key=key)["Body"].read()
    return json.loads(body)


def _print_preview(rows: list[dict[str, object]]) -> None:
    changing = [row for row in rows if row.get("changes")]
    print(f"activation preview: {len(rows)} pair(s), {len(changing)} would change")
    for row in rows:
        marker = "CHANGE" if row.get("changes") else "same  "
        current = row.get("current_release_name") or "(none)"
        print(
            f"  {marker}  {row.get('jurisdiction')}/{row.get('document_class')} "
            f"(currently {current})"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--release-object",
        type=Path,
        help="Path to a signed release object JSON (e.g. publish --output).",
    )
    parser.add_argument("--release", help="Release name (with --content-sha).")
    parser.add_argument("--content-sha", help="Release content sha256 (with --release).")
    parser.add_argument("--credentials-file", type=Path)
    parser.add_argument("--r2-bucket")
    parser.add_argument("--r2-endpoint")
    parser.add_argument("--supabase-url", default=DEFAULT_AXIOM_SUPABASE_URL)
    parser.add_argument("--access-token-env", default=DEFAULT_ACCESS_TOKEN_ENV)
    parser.add_argument(
        "--expected-project-ref",
        help=(
            "Required acknowledgement when --supabase-url is not the default "
            "production project: must equal the ref in the URL."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the per-scope takeover without moving serving.",
    )
    parser.add_argument("--output", type=Path)
    return parser


def _resolve_project_ref(args: argparse.Namespace) -> str:
    match = _SUPABASE_PROJECT_URL.match(args.supabase_url)
    if not match:
        raise SystemExit(
            f"--supabase-url must be a bare https://<ref>.supabase.co URL, got {args.supabase_url!r}"
        )
    ref = match.group("ref")
    # A non-default target must be acknowledged explicitly so a mistyped URL
    # cannot silently move serving in the wrong project.
    is_default = args.supabase_url.rstrip("/") == DEFAULT_AXIOM_SUPABASE_URL.rstrip("/")
    if not is_default and not args.expected_project_ref:
        raise SystemExit(
            "--expected-project-ref is required when --supabase-url is not the "
            "default production project"
        )
    if args.expected_project_ref and args.expected_project_ref != ref:
        raise SystemExit(
            f"--expected-project-ref {args.expected_project_ref!r} does not match "
            f"the URL project ref {ref!r}"
        )
    return ref


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    expected_ref = _resolve_project_ref(args)
    release_object = _load_release_object(args)
    public_key = _required_env(RELEASE_OBJECT_PUBLIC_KEY_ENV)
    access_token = _required_env(args.access_token_env)

    if args.dry_run:
        rows = preview_corpus_release_activation(
            release_object,
            access_token=access_token,
            public_key=public_key,
            supabase_url=args.supabase_url,
            expected_project_ref=expected_ref,
        )
        _print_preview(rows)
        payload: dict[str, Any] = {
            "dry_run": True,
            "release": release_object.get("release"),
            "content_sha256": release_object.get("content_sha256"),
            "scopes": rows,
        }
    else:
        result = activate_corpus_release(
            release_object,
            access_token=access_token,
            public_key=public_key,
            supabase_url=args.supabase_url,
            expected_project_ref=expected_ref,
        )
        payload = dict(result)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(
            (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
        )
        payload["written_to"] = str(args.output)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
