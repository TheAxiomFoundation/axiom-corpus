from pathlib import Path


def test_named_release_publication_requires_explicit_dispatch() -> None:
    workflow = Path(".github/workflows/publish.yml").read_text(encoding="utf-8")
    triggers = workflow.split("on:\n", 1)[1].split("\nconcurrency:", 1)[0]
    assert "  workflow_dispatch:" in triggers
    assert "  push:" not in triggers
    assert 'printf \'%s\\n\' "$DISPATCH_RELEASE"' in workflow
    assert "git diff --name-only" not in workflow
