from pathlib import Path

import yaml


def test_named_release_publication_requires_explicit_dispatch() -> None:
    workflow = Path(".github/workflows/publish.yml").read_text(encoding="utf-8")
    triggers = workflow.split("on:\n", 1)[1].split("\nconcurrency:", 1)[0]
    assert "  workflow_dispatch:" in triggers
    assert "  push:" not in triggers
    assert 'printf \'%s\\n\' "$DISPATCH_RELEASE"' in workflow
    assert "git diff --name-only" not in workflow


def test_named_release_publication_uses_protected_environment() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/publish.yml").read_text(encoding="utf-8"))

    assert workflow["jobs"]["publish"]["environment"] == "release-publish"


def test_named_release_publication_is_main_only() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/publish.yml").read_text(encoding="utf-8"))

    assert workflow["jobs"]["publish"]["if"] == (
        "github.ref == 'refs/heads/main' && github.event_name == 'workflow_dispatch'"
    )


def test_release_signing_key_requires_protected_publication_environment() -> None:
    for path in sorted(Path(".github/workflows").glob("*.y*ml")):
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        shared_settings = {key: value for key, value in workflow.items() if key != "jobs"}
        for job_name, job in workflow["jobs"].items():
            if "AXIOM_CORPUS_RELEASE_SIGNING_KEY" not in str((shared_settings, job)):
                continue
            environment = job.get("environment")
            if isinstance(environment, dict):
                environment = environment.get("name")
            assert environment == "release-publish", f"{path}: {job_name} exposes release signing"
