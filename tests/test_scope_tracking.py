import json
import subprocess

from axiom_corpus.corpus.scope_tracking import _git_indexed_json_batch


def test_git_indexed_json_batch_reads_multiple_files_and_skips_missing(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    paths = ["first.json", "nested/second.json"]
    for path, payload in zip(paths, ({"first": 1}, {"second": [2]}), strict=True):
        target = repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload) + "\n")
    subprocess.run(["git", "add", *paths], cwd=repo, check=True)

    payloads = _git_indexed_json_batch(repo, [*paths, "missing.json"])

    assert payloads == {"first.json": {"first": 1}, "nested/second.json": {"second": [2]}}
