"""Grouped top-level help must stay complete and non-breaking (#471)."""

from __future__ import annotations

import argparse
import re

import pytest

from axiom_corpus.corpus.cli import (
    _COMMAND_GROUPS,
    _EPILOG_WIDTH,
    _cmd_validate_manifest,
    build_parser,
)


def _subparsers_action(parser: argparse.ArgumentParser) -> argparse._SubParsersAction:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action
    raise AssertionError("no subparsers action on the corpus CLI parser")


def _canonical_and_alias_names(
    parser: argparse.ArgumentParser,
) -> tuple[set[str], dict[str, str]]:
    """Canonical command names, plus alias -> canonical for the rest."""

    index = parser._axiom_command_index  # type: ignore[attr-defined]
    canonical = set(index.canonical)
    aliases = dict(index.aliases)
    registered = set(_subparsers_action(parser).choices)
    assert canonical | set(aliases) == registered, (
        "command index no longer covers the registered choices "
        f"(uncovered: {sorted(registered - canonical - set(aliases))})"
    )
    # Summaries survived the argparse-internals harvest.
    assert all(index.helps.get(name) for name in canonical), (
        "a canonical command lost its help summary"
    )
    return canonical, aliases


def _parse_epilog_sections(epilog: str) -> dict[str, list[str]]:
    """Section title -> command tokens, exactly as the epilog renders them."""

    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in epilog.splitlines():
        if line and not line.startswith(" ") and line.endswith(":"):
            if line != "commands by pipeline stage:":
                current = line[:-1]
                sections[current] = []
        elif current is not None and re.match(r"^  \S", line):
            sections[current].append(line[2:].split()[0])
    return sections


def test_every_canonical_command_grouped_exactly_once() -> None:
    grouped = [name for _, names in _COMMAND_GROUPS for name in names]
    assert len(grouped) == len(set(grouped)), "a command appears in two groups"

    canonical, aliases = _canonical_and_alias_names(build_parser())
    assert set(grouped) == canonical, (
        "command groups and registered canonical subcommands diverged; update "
        "_COMMAND_GROUPS in the same change that adds or removes a command "
        f"(missing from groups: {sorted(canonical - set(grouped))}; "
        f"stale in groups: {sorted(set(grouped) - canonical)})"
    )
    # Aliases must resolve to a grouped canonical, never render as their own row.
    assert set(aliases.values()) <= canonical


def test_epilog_sections_match_the_table_exactly() -> None:
    parser = build_parser()
    assert parser.epilog is not None
    sections = _parse_epilog_sections(parser.epilog)

    assert list(sections) == [title for title, _ in _COMMAND_GROUPS], (
        "rendered sections diverge from _COMMAND_GROUPS (an Ungrouped section "
        "here means a command is missing from the table)"
    )
    for title, names in _COMMAND_GROUPS:
        assert sections[title] == list(names), f"section {title!r} diverged"

    rendered = [name for names in sections.values() for name in names]
    assert len(rendered) == len(set(rendered)), "a command renders twice"


def test_aliases_render_beside_their_canonical_command() -> None:
    parser = build_parser()
    canonical, aliases = _canonical_and_alias_names(parser)
    assert parser.epilog is not None
    for alias, canonical_name in aliases.items():
        assert f"{canonical_name} ({alias})" in parser.epilog, (
            f"alias {alias!r} lost its canonical linkage in the epilog"
        )


def test_epilog_summaries_and_width() -> None:
    parser = build_parser()
    assert parser.epilog is not None
    # Summaries are pulled from add_parser(help=...) via argparse internals; if
    # those internals change shape, fail loudly rather than render bare names.
    assert "Validate a corpus manifest." in parser.epilog
    assert "Build a source inventory from eCFR structure JSON." in parser.epilog
    long_lines = [line for line in parser.epilog.splitlines() if len(line) > _EPILOG_WIDTH]
    assert not long_lines, f"epilog lines exceed {_EPILOG_WIDTH} columns: {long_lines[:3]}"


def test_top_level_help_renders_grouped_index_once(capsys: pytest.CaptureFixture[str]) -> None:
    parser = build_parser()
    with pytest.raises(SystemExit) as excinfo:
        parser.parse_args(["--help"])
    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    assert "commands by pipeline stage:" in out
    assert "same CLI under two names" in out
    wide = [line for line in out.splitlines() if len(line) > _EPILOG_WIDTH]
    assert not wide, f"--help lines exceed {_EPILOG_WIDTH} columns: {wide[:3]}"
    # The flat alphabetical block is replaced, not duplicated: each canonical
    # command starts exactly one line in the whole help output.
    canonical, _ = _canonical_and_alias_names(build_parser())
    for name in canonical:
        starts = re.findall(rf"^  {re.escape(name)}(?=[ (]|$)", out, flags=re.MULTILINE)
        assert len(starts) == 1, f"{name} rendered {len(starts)} times"


def test_parsing_still_routes_commands() -> None:
    args = build_parser().parse_args(["validate-manifest", "some/path.yaml"])
    assert args.command == "validate-manifest"
    assert args.func is _cmd_validate_manifest
