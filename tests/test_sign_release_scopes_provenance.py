"""Check the script's ownership predicate directly, without CLI imports or signing."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

SCRIPT = Path(__file__).parents[1] / "scripts/sign_release_scopes.sh"
JURISDICTION = "us-co"
DOCUMENT_CLASS = "policy"
VERSION = "2026-09-24-a"
EXTRACTION = (
    "axiom-corpus-ingest extract-official-documents --base data/corpus --version {version}"
    " (run note: docs/ingest-runs/2026-09-10-*.md)"
)
CONSOLIDATION = (
    "scripts/consolidate_release_scopes.py --base data/corpus --jurisdiction us-co"
    " --document-class policy --target-version {version}"
    " (run note: docs/ingest-runs/2026-09-11-release-consolidation.md)"
)
EXPECTED = EXTRACTION.format(version=VERSION)
FOREIGN_COMMANDS = {
    "custom-manifest-path": EXPECTED.replace(
        " (run note:", " --manifest custom/scope.yml (run note:"
    ),
    "consolidation-for-ordinary-version": CONSOLIDATION.format(version=VERSION),
}


def _owns(command: str, *, version: str = VERSION, expected: str = EXPECTED) -> bool:
    """Run the actual predicate with an otherwise reproducible whole-scope manifest."""
    source = re.search(
        r"^plan_signing\(\) \{.*?<<'PY'\n(.*?)^PY$", SCRIPT.read_text(), re.S | re.M
    )
    assert source, "plan_signing's Python is no longer where this test looks for it"
    function = next(
        node
        for node in ast.parse(source.group(1)).body
        if isinstance(node, ast.FunctionDef) and node.name == "this_scripts"
    )
    scope = f"{JURISDICTION}/{DOCUMENT_CLASS}/{version}"
    paths = {
        f"data/corpus/sources/{scope}/source.html",
        f"data/corpus/inventory/{scope}.json",
        f"data/corpus/provisions/{scope}.jsonl",
        f"data/corpus/coverage/{scope}.json",
    }
    namespace = {
        "re": re,
        "committed": lambda *_args: paths,
        "expected_commands": {(JURISDICTION, DOCUMENT_CLASS, version): expected},
    }
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(SCRIPT), "exec"), namespace)
    payload = {
        "jurisdiction": JURISDICTION,
        "document_class": DOCUMENT_CLASS,
        "version": version,
        "command": {"text": command},
        "reasoning_logs": [],
        "applied_files": [{"path": path, "sha256": "a" * 64} for path in sorted(paths)],
    }
    return namespace["this_scripts"](payload, "b" * 40, JURISDICTION, DOCUMENT_CLASS, version)


@pytest.mark.parametrize("foreign", FOREIGN_COMMANDS)
def test_foreign_commands_are_not_owned(foreign: str) -> None:
    assert _owns(FOREIGN_COMMANDS[foreign]) is False


@pytest.mark.parametrize(
    ("version", "command"),
    [
        pytest.param(VERSION, EXPECTED, id="plain-extraction"),
        pytest.param(
            VERSION,
            EXPECTED.replace(" (run note:", " --manifest manifests/test-scope.yaml (run note:"),
            id="manifest-extraction",
        ),
        *(
            pytest.param(version, CONSOLIDATION.format(version=version), id=version)
            for version in ("2026-09-24-c-consolidated", "2026-09-24-chapters-06-07")
        ),
    ],
)
def test_canonical_commands_are_owned(version: str, command: str) -> None:
    assert _owns(command, version=version, expected=command) is True


@settings(max_examples=40, deadline=None)
@given(
    command=st.one_of(
        st.sampled_from([EXPECTED, *FOREIGN_COMMANDS.values()]),
        st.text(max_size=180),
        st.text("abcdefghijklmnopqrstuvwxyz0123456789_-", min_size=1, max_size=12).map(
            lambda name: EXPECTED.replace(
                " (run note:", f" --manifest manifests/{name}.yaml (run note:"
            )
        ),
        st.text(min_size=1, max_size=8).map(lambda suffix: EXPECTED + suffix),
    )
)
def test_ownership_requires_exactly_the_expected_command(command: str) -> None:
    assert _owns(command) is (command == EXPECTED)
