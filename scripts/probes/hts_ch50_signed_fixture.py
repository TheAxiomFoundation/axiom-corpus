import argparse
import ast
import base64
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from axiom_corpus.corpus.releases import (
    COMPLETE_EXPRESSION_DATES_PROFILE,
    ReleaseManifest,
    ReleaseScope,
)
from axiom_corpus.release.manifest import (
    build_release_content,
    build_unsigned_release_object,
    sign_release_object,
)
from scripts.repro import us_hts_rev15_chapter50_edition as e

parser = argparse.ArgumentParser(
    description="Build an ephemeral signed TEST fixture; publication evidence is mocked."
)
parser.add_argument("--retained-source", type=Path, required=True)
parser.add_argument("--binding", type=Path, required=True)
parser.add_argument("--historical-artifact", type=Path, action="append", required=True)
args = parser.parse_args()
history = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in args.historical_artifact}
root = Path(tempfile.mkdtemp(prefix="axiom-ch50-test-")).resolve()
(root / "data").mkdir()
source = args.retained_source
e.build_scope(root / "data/corpus", source)
assert history == {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in args.historical_artifact}
print(json.dumps({"unchanged_historical_artifacts": history}))
name = "us-ch50-edition-test"
manifest = ReleaseManifest(
    name=name,
    scopes=(ReleaseScope("us", "statute", e.VERSION),),
    quality_profile=COMPLETE_EXPRESSION_DATES_PROFILE,
)
p = root / "manifests/releases" / f"{name}.json"
p.parent.mkdir(parents=True)
p.write_text(
    json.dumps(
        {
            "name": name,
            "quality_profile": COMPLETE_EXPRESSION_DATES_PROFILE,
            "scopes": [{"jurisdiction": "us", "document_class": "statute", "version": e.VERSION}],
        }
    )
)
subprocess.run(["git", "init", "-q", str(root)], check=True)
subprocess.run(["git", "-C", str(root), "add", "."], check=True)
subprocess.run(
    [
        "git",
        "-C",
        str(root),
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.org",
        "-c",
        "commit.gpgsign=false",
        "commit",
        "-qm",
        "ephemeral test fixture",
    ],
    check=True,
)
key = Ed25519PrivateKey.generate()
private = base64.b64encode(
    key.private_bytes(
        serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption()
    )
).decode()
public = base64.b64encode(
    key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
).decode()
content = build_release_content(
    root,
    release=manifest,
    validation={"passed": True, "test_fixture_only": True},
    created_at="2026-10-01T00:00:00Z",
)
# Ephemeral test fixture only: same mocked publication evidence as repository unit tests.
module = ast.parse(Path("tests/test_release_gate.py").read_text())
fn = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == "_validation")
ns = {"Any": object, "COMPLETE_EXPRESSION_DATES_PROFILE": COMPLETE_EXPRESSION_DATES_PROFILE}
exec(compile(ast.Module(body=[fn], type_ignores=[]), "<test fixture>", "exec"), ns)
content["validation"] = ns["_validation"](content)
signed = sign_release_object(build_unsigned_release_object(content), private_key=private)
sha = signed["content_sha256"]
f = root / "releases" / name / f"{sha}.json"
f.parent.mkdir(parents=True)
f.write_text(json.dumps(signed))
args.binding.write_text(
    json.dumps(
        {
            "root": str(root),
            "name": name,
            "sha": sha,
            "public": public,
            "version": e.VERSION,
            "citation": e.ROOT,
        }
    )
)
