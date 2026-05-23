"""Offline PolicyEngine reference extraction for source discovery.

PolicyEngine references are discovery provenance only. This module scans a
checked-out PolicyEngine repository and emits records that can seed Axiom
source-discovery reports without making PolicyEngine a corpus input.
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
from collections import Counter
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any


class PolicyEngineReferenceScope(StrEnum):
    """File scopes available to the offline PolicyEngine reference scanner."""

    POLICY = "policy"
    ALL = "all"


@dataclass(frozen=True)
class PolicyEngineReference:
    """One URL or bare textual source reference found in a PolicyEngine file."""

    project: str
    upstream_commit: str | None
    file_path: str
    line: int
    source_type: str
    symbol_path: str | None
    reference_kind: str
    reference_text: str
    reference_url: str | None
    citation_text: str | None

    def to_mapping(self) -> dict[str, Any]:
        return {
            "project": self.project,
            "upstream_commit": self.upstream_commit,
            "file_path": self.file_path,
            "line": self.line,
            "source_type": self.source_type,
            "symbol_path": self.symbol_path,
            "reference_kind": self.reference_kind,
            "reference_text": self.reference_text,
            "reference_url": self.reference_url,
            "citation_text": self.citation_text,
        }


URL_RE = re.compile(r"https?://[^\s'\"<>)\]}]+")
YAML_REFERENCE_RE = re.compile(r"^(\s*)(?:-\s*)?reference\s*:\s*(.*)$", re.I)
REFERENCE_COMMENT_RE = re.compile(r"#\s*(?:Reference|Source|Citation)\s*:\s*(.+)$", re.I)
SKIP_DIR_NAMES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
}
POLICYENGINE_PACKAGE_PROJECTS = {
    "policyengine_us": "policyengine-us",
    "policyengine_uk": "policyengine-uk",
}


def scan_policyengine_references(
    repo_path: str | Path,
    *,
    project: str | None = None,
    upstream_commit: str | None = None,
    scope: PolicyEngineReferenceScope | str = PolicyEngineReferenceScope.POLICY,
) -> tuple[PolicyEngineReference, ...]:
    """Scan a PolicyEngine checkout for URL and textual source references.

    The default ``policy`` scope walks ``parameters`` and ``variables`` only.
    ``all`` additionally scans supported source/documentation files throughout
    the checkout, which is useful for rebuilding broad URL inventories.
    """

    repo = Path(repo_path)
    package_dir, inferred_project = _discover_policyengine_package(repo)
    resolved_project = project or inferred_project
    resolved_commit = upstream_commit if upstream_commit is not None else _git_commit(repo)
    resolved_scope = PolicyEngineReferenceScope(scope)

    records: list[PolicyEngineReference] = []
    for path in _iter_reference_files(repo, package_dir, resolved_scope):
        records.extend(
            _scan_reference_file(
                repo=repo,
                package_dir=package_dir,
                path=path,
                project=resolved_project,
                upstream_commit=resolved_commit,
            )
        )
    return _dedupe_references(records)


def write_policyengine_references_jsonl(
    references: tuple[PolicyEngineReference, ...],
    output_path: str | Path,
) -> None:
    """Write reference records as JSON Lines."""

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(record.to_mapping(), sort_keys=True) for record in references]
    output.write_text("\n".join(lines) + ("\n" if lines else ""))


def write_policyengine_url_inventory(
    references: tuple[PolicyEngineReference, ...],
    output_path: str | Path,
) -> None:
    """Write a static URL-list inventory consumable by source-discovery."""

    urls = sorted({record.reference_url for record in references if record.reference_url})
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(urls) + ("\n" if urls else ""))


def summarize_policyengine_references(
    references: tuple[PolicyEngineReference, ...],
) -> dict[str, Any]:
    """Return stable counts for CLI output and tests."""

    return {
        "reference_count": len(references),
        "url_reference_count": sum(1 for record in references if record.reference_url),
        "citation_reference_count": sum(
            1 for record in references if record.citation_text is not None
        ),
        "unique_url_count": len(
            {record.reference_url for record in references if record.reference_url}
        ),
        "project_counts": _counter_mapping(Counter(record.project for record in references)),
        "source_type_counts": _counter_mapping(
            Counter(record.source_type for record in references)
        ),
        "reference_kind_counts": _counter_mapping(
            Counter(record.reference_kind for record in references)
        ),
    }


def _discover_policyengine_package(repo: Path) -> tuple[Path, str]:
    for package_name, project in POLICYENGINE_PACKAGE_PROJECTS.items():
        package_dir = repo / package_name
        if package_dir.exists():
            return package_dir, project
    raise ValueError(f"PolicyEngine package directory not found in {repo}")


def _git_commit(repo: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    commit = result.stdout.strip()
    return commit or None


def _iter_reference_files(
    repo: Path,
    package_dir: Path,
    scope: PolicyEngineReferenceScope,
) -> tuple[Path, ...]:
    roots: tuple[Path, ...]
    if scope is PolicyEngineReferenceScope.POLICY:
        roots = (package_dir / "parameters", package_dir / "variables")
    else:
        roots = (repo,)

    paths: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_dir() or _has_skipped_part(path, repo):
                continue
            if path.suffix.lower() in {".yaml", ".yml", ".py", ".md"}:
                paths.append(path)
    return tuple(sorted(paths))


def _has_skipped_part(path: Path, repo: Path) -> bool:
    try:
        relative = path.relative_to(repo)
    except ValueError:
        relative = path
    return any(part in SKIP_DIR_NAMES for part in relative.parts)


def _scan_reference_file(
    *,
    repo: Path,
    package_dir: Path,
    path: Path,
    project: str,
    upstream_commit: str | None,
) -> tuple[PolicyEngineReference, ...]:
    suffix = path.suffix.lower()
    if suffix == ".py":
        records = list(
            _scan_python_file(
                repo=repo,
                package_dir=package_dir,
                path=path,
                project=project,
                upstream_commit=upstream_commit,
            )
        )
    else:
        records = list(
            _scan_text_file(
                repo=repo,
                package_dir=package_dir,
                path=path,
                project=project,
                upstream_commit=upstream_commit,
            )
        )
    return _dedupe_references(records)


def _scan_python_file(
    *,
    repo: Path,
    package_dir: Path,
    path: Path,
    project: str,
    upstream_commit: str | None,
) -> tuple[PolicyEngineReference, ...]:
    text = path.read_text(errors="ignore")
    relative_path = _relative_posix(repo, path)
    source_type = _source_type(package_dir, path)
    fallback_symbol_path = _symbol_path(package_dir, path)
    records: list[PolicyEngineReference] = []

    try:
        tree = ast.parse(text)
    except SyntaxError:
        tree = None

    if tree is not None:
        records.extend(
            _python_reference_assignments(
                tree=tree,
                project=project,
                upstream_commit=upstream_commit,
                file_path=relative_path,
                source_type=source_type,
                fallback_symbol_path=fallback_symbol_path,
            )
        )

    ast_url_line_keys = {
        (record.line, record.reference_url)
        for record in records
        if record.reference_url is not None
    }
    for line_number, line in enumerate(text.splitlines(), start=1):
        for url in _extract_urls(line):
            if (line_number, url) in ast_url_line_keys:
                continue
            records.append(
                _url_record(
                    project=project,
                    upstream_commit=upstream_commit,
                    file_path=relative_path,
                    line=line_number,
                    source_type=source_type,
                    symbol_path=fallback_symbol_path,
                    url=url,
                )
            )
        citation = _reference_comment_text(line)
        if citation is None or _extract_urls(citation):
            continue
        records.append(
            _citation_record(
                project=project,
                upstream_commit=upstream_commit,
                file_path=relative_path,
                line=line_number,
                source_type=source_type,
                symbol_path=fallback_symbol_path,
                citation_text=citation,
            )
        )
    return tuple(records)


def _python_reference_assignments(
    *,
    tree: ast.AST,
    project: str,
    upstream_commit: str | None,
    file_path: str,
    source_type: str,
    fallback_symbol_path: str | None,
) -> tuple[PolicyEngineReference, ...]:
    records: list[PolicyEngineReference] = []
    for node in getattr(tree, "body", ()):
        if isinstance(node, ast.ClassDef):
            for assignment in node.body:
                value = _reference_assignment_value(assignment)
                if value is None:
                    continue
                records.extend(
                    _records_from_python_reference_value(
                        value=value,
                        symbol_path=node.name,
                        project=project,
                        upstream_commit=upstream_commit,
                        file_path=file_path,
                        source_type=source_type,
                    )
                )
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = _reference_assignment_value(node)
            if value is None:
                continue
            records.extend(
                _records_from_python_reference_value(
                    value=value,
                    symbol_path=fallback_symbol_path,
                    project=project,
                    upstream_commit=upstream_commit,
                    file_path=file_path,
                    source_type=source_type,
                )
            )
    return tuple(records)


def _reference_assignment_value(node: ast.AST) -> ast.AST | None:
    if isinstance(node, ast.Assign):
        if any(_is_reference_target(target) for target in node.targets):
            return node.value
        return None
    if isinstance(node, ast.AnnAssign) and _is_reference_target(node.target):
        return node.value
    return None


def _is_reference_target(target: ast.AST) -> bool:
    return isinstance(target, ast.Name) and target.id == "reference"


def _records_from_python_reference_value(
    *,
    value: ast.AST,
    symbol_path: str | None,
    project: str,
    upstream_commit: str | None,
    file_path: str,
    source_type: str,
) -> tuple[PolicyEngineReference, ...]:
    records: list[PolicyEngineReference] = []
    for text, line in _iter_string_literals(value):
        text = _clean_reference_text(text)
        if not text:
            continue
        urls = tuple(_extract_urls(text))
        if urls:
            for url in urls:
                records.append(
                    _url_record(
                        project=project,
                        upstream_commit=upstream_commit,
                        file_path=file_path,
                        line=line,
                        source_type=source_type,
                        symbol_path=symbol_path,
                        url=url,
                    )
                )
        else:
            records.append(
                _citation_record(
                    project=project,
                    upstream_commit=upstream_commit,
                    file_path=file_path,
                    line=line,
                    source_type=source_type,
                    symbol_path=symbol_path,
                    citation_text=text,
                )
            )
    return tuple(records)


def _iter_string_literals(node: ast.AST) -> tuple[tuple[str, int], ...]:
    strings: list[tuple[str, int]] = []
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        strings.append((node.value, node.lineno))
    elif isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        for element in node.elts:
            strings.extend(_iter_string_literals(element))
    elif isinstance(node, ast.Dict):
        for key in node.keys:
            if key is not None:
                strings.extend(_iter_string_literals(key))
        for value in node.values:
            strings.extend(_iter_string_literals(value))
    elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        strings.extend(_iter_string_literals(node.left))
        strings.extend(_iter_string_literals(node.right))
    return tuple(strings)


def _scan_text_file(
    *,
    repo: Path,
    package_dir: Path,
    path: Path,
    project: str,
    upstream_commit: str | None,
) -> tuple[PolicyEngineReference, ...]:
    lines = path.read_text(errors="ignore").splitlines()
    relative_path = _relative_posix(repo, path)
    source_type = _source_type(package_dir, path)
    symbol_path = _symbol_path(package_dir, path)
    records: list[PolicyEngineReference] = []

    reference_block_indent: int | None = None
    for line_number, line in enumerate(lines, start=1):
        for url in _extract_urls(line):
            records.append(
                _url_record(
                    project=project,
                    upstream_commit=upstream_commit,
                    file_path=relative_path,
                    line=line_number,
                    source_type=source_type,
                    symbol_path=symbol_path,
                    url=url,
                )
            )

        reference_match = YAML_REFERENCE_RE.match(line)
        if reference_match is not None:
            reference_block_indent = len(reference_match.group(1))
            inline_text = _yaml_reference_text(reference_match.group(2))
            if inline_text is not None and not _extract_urls(inline_text):
                records.append(
                    _citation_record(
                        project=project,
                        upstream_commit=upstream_commit,
                        file_path=relative_path,
                        line=line_number,
                        source_type=source_type,
                        symbol_path=symbol_path,
                        citation_text=inline_text,
                    )
                )
            continue

        comment_text = _reference_comment_text(line)
        if comment_text is not None and not _extract_urls(comment_text):
            records.append(
                _citation_record(
                    project=project,
                    upstream_commit=upstream_commit,
                    file_path=relative_path,
                    line=line_number,
                    source_type=source_type,
                    symbol_path=symbol_path,
                    citation_text=comment_text,
                )
            )

        if reference_block_indent is None:
            continue
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent <= reference_block_indent and not line.lstrip().startswith("-"):
            reference_block_indent = None
            continue
        reference_text = _yaml_reference_text(line)
        if reference_text is None or _extract_urls(reference_text):
            continue
        records.append(
            _citation_record(
                project=project,
                upstream_commit=upstream_commit,
                file_path=relative_path,
                line=line_number,
                source_type=source_type,
                symbol_path=symbol_path,
                citation_text=reference_text,
            )
        )
    return tuple(records)


def _extract_urls(text: str) -> tuple[str, ...]:
    urls: list[str] = []
    for match in URL_RE.finditer(text):
        url = match.group(0).rstrip(".,;:")
        if url:
            urls.append(url)
    return tuple(urls)


def _reference_comment_text(line: str) -> str | None:
    match = REFERENCE_COMMENT_RE.search(line)
    if match is None:
        return None
    return _clean_reference_text(match.group(1))


def _yaml_reference_text(text: str) -> str | None:
    stripped = text.strip()
    if not stripped:
        return None
    if stripped.startswith("#"):
        return _reference_comment_text(stripped)
    if stripped.startswith("- "):
        stripped = stripped[2:].strip()
    if stripped.startswith("-"):
        stripped = stripped[1:].strip()
    if not stripped:
        return None
    if ":" in stripped:
        key, value = stripped.split(":", 1)
        normalized_key = key.strip().lower()
        if normalized_key in {"href", "url"}:
            return None
        if normalized_key in {"citation", "reference", "source", "title"}:
            stripped = value.strip()
        else:
            return None
    return _clean_reference_text(stripped)


def _clean_reference_text(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return ""
    if " #" in stripped:
        stripped = stripped.split(" #", 1)[0].rstrip()
    stripped = stripped.strip("'\"")
    return stripped.strip()


def _url_record(
    *,
    project: str,
    upstream_commit: str | None,
    file_path: str,
    line: int,
    source_type: str,
    symbol_path: str | None,
    url: str,
) -> PolicyEngineReference:
    return PolicyEngineReference(
        project=project,
        upstream_commit=upstream_commit,
        file_path=file_path,
        line=line,
        source_type=source_type,
        symbol_path=symbol_path,
        reference_kind="url",
        reference_text=url,
        reference_url=url,
        citation_text=None,
    )


def _citation_record(
    *,
    project: str,
    upstream_commit: str | None,
    file_path: str,
    line: int,
    source_type: str,
    symbol_path: str | None,
    citation_text: str,
) -> PolicyEngineReference:
    return PolicyEngineReference(
        project=project,
        upstream_commit=upstream_commit,
        file_path=file_path,
        line=line,
        source_type=source_type,
        symbol_path=symbol_path,
        reference_kind="citation",
        reference_text=citation_text,
        reference_url=None,
        citation_text=citation_text,
    )


def _source_type(package_dir: Path, path: Path) -> str:
    parameters_dir = package_dir / "parameters"
    variables_dir = package_dir / "variables"
    if _is_relative_to(path, parameters_dir):
        return "parameter"
    if _is_relative_to(path, variables_dir):
        return "variable"
    if path.suffix.lower() in {".yaml", ".yml"}:
        return "yaml"
    if path.suffix.lower() == ".py":
        return "python"
    if path.suffix.lower() == ".md":
        return "markdown"
    return "other"


def _symbol_path(package_dir: Path, path: Path) -> str | None:
    parameters_dir = package_dir / "parameters"
    variables_dir = package_dir / "variables"
    if _is_relative_to(path, parameters_dir):
        return _dotted_path(path.relative_to(parameters_dir))
    if _is_relative_to(path, variables_dir):
        return path.stem
    return None


def _dotted_path(relative_path: Path) -> str | None:
    parts = list(relative_path.with_suffix("").parts)
    if parts and parts[-1] == "index":
        parts = parts[:-1]
    if not parts:
        return None
    return ".".join(parts)


def _relative_posix(repo: Path, path: Path) -> str:
    return path.relative_to(repo).as_posix()


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _dedupe_references(
    records: list[PolicyEngineReference] | tuple[PolicyEngineReference, ...],
) -> tuple[PolicyEngineReference, ...]:
    by_key: dict[tuple[str, str, int, str, str, str | None], PolicyEngineReference] = {}
    for record in records:
        key = (
            record.project,
            record.file_path,
            record.line,
            record.reference_kind,
            record.reference_text,
            record.symbol_path,
        )
        by_key.setdefault(key, record)
    return tuple(
        by_key[key]
        for key in sorted(
            by_key,
            key=lambda item: (item[0], item[1], item[2], item[3], item[4], item[5] or ""),
        )
    )


def _counter_mapping(counter: Counter[str]) -> dict[str, int]:
    return {key: counter[key] for key in sorted(counter)}
