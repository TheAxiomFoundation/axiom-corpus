import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import yaml
from axiom_encode.corpus_resolver import LocalCorpusRelease, resolve_local_corpus_source

parser = argparse.ArgumentParser(
    description="Resolve an ephemeral chapter fixture and reject artifact tampering."
)
parser.add_argument("--binding", type=Path, required=True)
parser.add_argument("--policy", type=Path, required=True)
parser.add_argument("--result", type=Path, required=True)
parser.add_argument("--negative-child", action="store_true")
args = parser.parse_args()
b = json.loads(args.binding.read_text())
root = Path(b["root"])
name = b["name"]
sha = b["sha"]
public = b["public"]
e = SimpleNamespace(ROOT=b["citation"], VERSION=b["version"])
release = LocalCorpusRelease(root, name, sha, public)
chapter = resolve_local_corpus_source(e.ROOT, release)
rows = list(
    map(
        json.loads,
        (root / "data/corpus/provisions/us/statute" / f"{e.VERSION}.jsonl")
        .read_text()
        .splitlines(),
    )
)
for row in rows[1:]:
    assert resolve_local_corpus_source(row["citation_path"], release).body == row["body"]
result = {
    "ephemeral_test_only": True,
    "root": str(root),
    "release_sha": sha,
    "leaf_matches": len(rows) - 1,
    "chapter_body_length": len(chapter.body),
    "chapter_sha": hashlib.sha256(chapter.body.encode()).hexdigest(),
}
print(json.dumps(result))
args.result.write_text(json.dumps(result, indent=2) + "\n")

policy = yaml.safe_load(args.policy.read_text())
checked = set()
atoms = 0
for rule in policy["rules"]:
    for atom in rule.get("metadata", {}).get("proof", {}).get("atoms", []):
        src = atom.get("source", {})
        old = src.get("corpus_citation_path")
        excerpt = src.get("excerpt")
        if old and excerpt:
            target = old.replace("us/statute/hts/", e.ROOT + "/")
            body = resolve_local_corpus_source(target, release).body
            assert excerpt in body, (old, excerpt)
            checked.add(old)
            atoms += 1
result.update(proof_citations=len(checked), proof_atoms=atoms, mocked_publication_evidence=True)
args.result.write_text(json.dumps(result, indent=2) + "\n")
print("Proofs", len(checked), atoms)

assert len(checked) == 13 and atoms == 52
if not args.negative_child:
    provision = root / "data/corpus/provisions/us/statute" / f"{e.VERSION}.jsonl"
    original = provision.read_bytes()
    try:
        provision.write_bytes(original + b"\n")
        child = subprocess.run(
            [
                sys.executable,
                __file__,
                "--binding",
                str(args.binding),
                "--policy",
                str(args.policy),
                "--result",
                str(args.result),
                "--negative-child",
            ],
            capture_output=True,
            text=True,
        )
        assert child.returncode != 0
        assert "Corpus provision bytes do not match the verified release" in child.stderr
    finally:
        provision.write_bytes(original)
    result["tamper_rejected"] = True
    args.result.write_text(json.dumps(result, indent=2) + "\n")
