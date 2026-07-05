#!/usr/bin/env python3
"""Regenerate the typed concept registry from local ``rulespec-*`` checkouts.

Deterministic and re-runnable: given the same input checkouts, this writes
byte-identical ``src/axiom_corpus/concepts/data/<jurisdiction>.yaml`` files. It embeds the
scanned ``rulespec`` commit SHA and the imported PolicyEngine-mappings commit
SHA into each file's ``generated_from`` block so the checked-in registry can be
validated for internal consistency without a live checkout (see
``tests/test_concept_registry.py``).

What it extracts, per jurisdiction directory (``us``, ``us-nc``, ``uk``, ...)
inside a ``rulespec-*`` repo:

* **outputs** — every ``rules[].name`` in every module (non-test) ``.yaml``.
  The concept id is ``<jurisdiction>:<module-path>#<name>``. Type fields
  (``entity``, ``dtype``, ``unit``, ``period``) are copied from the defining
  rule where present. When the same output name is defined by more than one
  rule version with conflicting types, the field is dropped and
  ``type_ambiguous: true`` is set (never guessed).
* **inputs** — every ``#input.<name>`` key in companion ``.test.yaml`` files,
  plus bare variable references in rule formulas that are not themselves rule
  names, imported outputs, or language keywords. Inputs carry no declared type
  in the source, so dtype/unit/period are left unset; ``entity`` is set only
  when every consuming rule in the same module agrees on one entity
  (unambiguous), else left unset.

Cross-engine edges: PolicyEngine mappings (``axiom-encode``
``oracles/policyengine/mappings/<country>.yaml``) are joined onto matching
output concept ids, one file and engine key per country — US mappings as
``mappings.policyengine_us`` and UK mappings as ``mappings.policyengine_uk``
(see ``PE_MAPPING_SOURCES``).

Usage::

    uv run python scripts/build_concept_registry.py \
        --rulespec-root ~/TheAxiomFoundation \
        --write

Without ``--write`` it prints a summary and exits (dry run). ``--check``
regenerates in memory and fails if the checked-in files differ.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

REGISTRY_SCHEMA_VERSION = "axiom-corpus/concept-registry/v1"
REGISTRY_VERSION = "0.1.0"

_REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_ROOT = _REPO_ROOT / "src" / "axiom_corpus" / "concepts" / "data"

# Bucket directories that hold RuleSpec encodings inside a jurisdiction dir.
ENCODING_BUCKETS = frozenset({"statutes", "regulations", "policies"})
EXCLUDED_SUFFIXES = (".test.yaml", ".meta.yaml")

# ``rulespec-<country>`` repos hold a directory per jurisdiction (``us``,
# ``us-ca``, ``uk``, ``uk-kingston-upon-thames``) plus shared non-encoding
# dirs. A jurisdiction dir is the country slug or ``<country>-<sub>``.
COUNTRY_REPOS: dict[str, str] = {
    "us": "rulespec-us",
    "uk": "rulespec-uk",
}

# PolicyEngine cross-engine mappings, one ``axiom-encode`` file per country,
# joined onto matching output concept ids. ``engine`` is the mappings key the
# edge is emitted under, matching the PolicyEngine package for that country.
PE_MAPPING_SOURCES: dict[str, tuple[str, str]] = {
    "us": ("src/axiom_encode/oracles/policyengine/mappings/us.yaml", "policyengine_us"),
    "uk": ("src/axiom_encode/oracles/policyengine/mappings/uk.yaml", "policyengine_uk"),
}


def default_rulespec_root() -> Path:
    """Find the directory holding ``rulespec-*`` checkouts.

    This repo may be a plain clone (siblings at ``../``) or a git worktree
    under ``<org>/_worktrees/<name>`` (siblings two levels up). Walk ancestors
    and return the first that contains ``rulespec-us``; fall back to the repo's
    parent so ``--rulespec-root`` can always override.
    """
    for ancestor in _REPO_ROOT.parents:
        if (ancestor / "rulespec-us").is_dir():
            return ancestor
    return _REPO_ROOT.parent

# Identifiers that appear in formula text but are never input slots.
FORMULA_KEYWORDS = frozenset(
    {
        "if", "else", "elif", "and", "or", "not", "in", "is", "true", "false",
        "none", "for", "while", "return", "def", "lambda", "min", "max", "sum",
        "abs", "round", "any", "all", "len", "int", "float", "str", "bool",
        "then", "otherwise", "and_", "or_",
    }
)
_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_INPUT_KEY_RE = re.compile(r"^(?P<mod>.+?)#input\.(?P<name>.+)$")


@dataclass
class ConceptAcc:
    """Mutable accumulator for one concept while scanning."""

    id: str
    kind: str
    name: str
    entities: set[str] = field(default_factory=set)
    dtypes: set[str] = field(default_factory=set)
    units: set[str] = field(default_factory=set)
    periods: set[str] = field(default_factory=set)
    modules: set[str] = field(default_factory=set)
    occurrences: int = 0


# ---------------------------------------------------------------------------
# Git / provenance
# ---------------------------------------------------------------------------


def git_head_sha(repo: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return out.stdout.strip() or None


def git_file_sha(repo: Path, relpath: str) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "log", "-1", "--format=%H", "--", relpath],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return out.stdout.strip() or None


# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------


def jurisdiction_dirs(country_repo: Path, country: str) -> Iterator[Path]:
    """Yield jurisdiction directories inside a ``rulespec-<country>`` repo."""
    for d in sorted(country_repo.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        if d.name == country or d.name.startswith(f"{country}-"):
            yield d


def iter_module_files(jur_dir: Path) -> Iterator[Path]:
    for p in sorted(jur_dir.rglob("*.yaml")):
        rel = p.relative_to(jur_dir).as_posix()
        if rel.endswith(EXCLUDED_SUFFIXES):
            continue
        if any(part.startswith(".") for part in rel.split("/")[:-1]):
            continue
        if rel.split("/")[0] not in ENCODING_BUCKETS:
            continue
        yield p


def module_prefix(jur_dir: Path, module_path: Path) -> str:
    rel = module_path.relative_to(jur_dir).as_posix()
    return f"{jur_dir.name}:{rel[: -len('.yaml')]}"


def test_path_for(module_path: Path) -> Path:
    return Path(str(module_path)[: -len(".yaml")] + ".test.yaml")


def _safe_load(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text())
    except yaml.YAMLError:
        return None


def scan_jurisdiction(jur_dir: Path) -> tuple[dict[str, ConceptAcc], int]:
    """Return ``{concept_id: ConceptAcc}`` and the module count for one dir."""
    concepts: dict[str, ConceptAcc] = {}
    module_count = 0

    for module_path in iter_module_files(jur_dir):
        doc = _safe_load(module_path)
        if not isinstance(doc, dict):
            continue
        module_count += 1
        prefix = module_prefix(jur_dir, module_path)
        rules = doc.get("rules") or []
        rule_names: set[str] = set()
        imported_outputs: set[str] = set()
        module_entities: set[str] = set()
        formula_idents: set[str] = set()

        for rule in rules:
            if not isinstance(rule, dict) or "name" not in rule:
                continue
            name = str(rule["name"])
            rule_names.add(name)
            cid = f"{prefix}#{name}"
            acc = concepts.setdefault(cid, ConceptAcc(id=cid, kind="output", name=name))
            acc.occurrences += 1
            acc.modules.add(prefix)
            _absorb_rule_types(acc, rule, module_entities)
            _collect_formula_and_imports(rule, formula_idents, imported_outputs)

        # Inputs from the companion test file (authoritative, explicit).
        test_inputs = _collect_test_inputs(test_path_for(module_path))
        # Inputs from formula bare-vars (secondary, filtered).
        formula_inputs = _formula_input_names(
            formula_idents, rule_names, imported_outputs
        )

        _register_inputs(
            concepts,
            prefix=prefix,
            test_inputs=test_inputs,
            formula_inputs=formula_inputs,
            module_entity=(next(iter(module_entities)) if len(module_entities) == 1 else None),
        )

    return concepts, module_count


def _absorb_rule_types(
    acc: ConceptAcc, rule: dict[str, Any], module_entities: set[str]
) -> None:
    for field_name, bucket in (
        ("entity", acc.entities),
        ("dtype", acc.dtypes),
        ("unit", acc.units),
        ("period", acc.periods),
    ):
        value = rule.get(field_name)
        if value is not None:
            bucket.add(str(value))
            if field_name == "entity":
                module_entities.add(str(value))


def _collect_formula_and_imports(
    rule: dict[str, Any],
    formula_idents: set[str],
    imported_outputs: set[str],
) -> None:
    for version in rule.get("versions") or []:
        if not isinstance(version, dict):
            continue
        formula = version.get("formula")
        if isinstance(formula, str):
            formula_idents.update(_IDENT_RE.findall(formula))
    metadata = rule.get("metadata") or {}
    proof = metadata.get("proof") if isinstance(metadata, dict) else None
    if isinstance(proof, dict):
        for atom in proof.get("atoms") or []:
            if not isinstance(atom, dict):
                continue
            imp = atom.get("import")
            if isinstance(imp, dict) and imp.get("output"):
                imported_outputs.add(str(imp["output"]))


def _collect_test_inputs(test_path: Path) -> set[str]:
    names: set[str] = set()
    if not test_path.exists():
        return names
    tdoc = _safe_load(test_path)
    if not isinstance(tdoc, list):
        return names
    for case in tdoc:
        if not isinstance(case, dict):
            continue
        for key in case.get("input") or {}:
            match = _INPUT_KEY_RE.match(str(key))
            if match:
                names.add(match.group("name"))
    return names


def _formula_input_names(
    formula_idents: set[str],
    rule_names: set[str],
    imported_outputs: set[str],
) -> set[str]:
    imported_names = {oid.split("#", 1)[-1] for oid in imported_outputs}
    imported_names |= {n.split(".", 1)[-1] for n in imported_names}
    candidates = formula_idents - rule_names - imported_names - FORMULA_KEYWORDS
    return {c for c in candidates if not c.isupper()}


def _register_inputs(
    concepts: dict[str, ConceptAcc],
    *,
    prefix: str,
    test_inputs: set[str],
    formula_inputs: set[str],
    module_entity: str | None,
) -> None:
    for name in sorted(test_inputs | formula_inputs):
        cid = f"{prefix}#input.{name}"
        acc = concepts.setdefault(cid, ConceptAcc(id=cid, kind="input", name=name))
        acc.occurrences += 1
        acc.modules.add(prefix)
        # Only inherit entity when the whole module agrees on one entity — the
        # single unambiguous signal. dtype/unit/period are never derivable for
        # an input from the consuming rule, so they stay unset.
        if module_entity is not None:
            acc.entities.add(module_entity)


# ---------------------------------------------------------------------------
# PolicyEngine mapping import
# ---------------------------------------------------------------------------


def load_pe_mappings(mappings_path: Path) -> dict[str, dict[str, Any]]:
    """Return ``{legal_id: mapping_edge}`` for exact-id PolicyEngine mappings.

    Reads one ``axiom-encode`` PolicyEngine mappings file
    (``oracles/policyengine/mappings/<country>.yaml``). Only exact ``legal_id``
    entries produce edges; ``legal_id_prefix`` catch-alls are coverage-level
    classifications, not concept edges, so they are ignored here — a fresh exact
    ``parameter_value`` entry therefore joins onto its concept even when a
    ``not_comparable`` prefix covers the same module.
    """
    if not mappings_path.exists():
        return {}
    doc = _safe_load(mappings_path)
    if not isinstance(doc, dict):
        return {}
    edges: dict[str, dict[str, Any]] = {}
    for entry in doc.get("mappings") or []:
        if not isinstance(entry, dict):
            continue
        legal_id = entry.get("legal_id")
        if not legal_id:
            continue
        edge = _pe_edge_from_entry(entry)
        if edge:
            edges[str(legal_id)] = edge
    return edges


# Back-compat alias: the loader was US-only before per-country mappings landed.
load_pe_us_mappings = load_pe_mappings


def _pe_edge_from_entry(entry: dict[str, Any]) -> dict[str, Any]:
    edge: dict[str, Any] = {}
    for src, dst in (
        ("mapping_type", "mapping_type"),
        ("policyengine_variable", "variable"),
        ("policyengine_parameter", "parameter"),
        ("parameter_key", "parameter_key"),
        ("comparison", "comparison"),
        ("program", "program"),
    ):
        value = entry.get(src)
        if value is not None:
            edge[dst] = str(value)
    return edge


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def _resolve_field(values: set[str]) -> tuple[str | None, bool]:
    """Return (value, ambiguous). Exactly one value -> that value; >1 -> None+ambiguous."""
    if len(values) == 1:
        return next(iter(values)), False
    if len(values) > 1:
        return None, True
    return None, False


def concept_to_payload(
    acc: ConceptAcc,
    pe_edges: dict[str, dict[str, Any]],
    engine: str = "policyengine_us",
) -> dict[str, Any]:
    entity, entity_amb = _resolve_field(acc.entities)
    dtype, dtype_amb = _resolve_field(acc.dtypes)
    unit, unit_amb = _resolve_field(acc.units)
    period, period_amb = _resolve_field(acc.periods)

    payload: dict[str, Any] = {
        "id": acc.id,
        "kind": acc.kind,
        "name": acc.name,
    }
    if entity is not None:
        payload["entity"] = entity
    if dtype is not None:
        payload["dtype"] = dtype
    if unit is not None:
        payload["unit"] = unit
    if period is not None:
        payload["period"] = period
    if any((entity_amb, dtype_amb, unit_amb, period_amb)):
        payload["type_ambiguous"] = True
    payload["modules"] = sorted(acc.modules)
    payload["occurrences"] = acc.occurrences

    edge = pe_edges.get(acc.id)
    if edge:
        payload["mappings"] = {engine: edge}
    return payload


def build_jurisdiction_payload(
    jurisdiction: str,
    concepts: dict[str, ConceptAcc],
    pe_edges: dict[str, dict[str, Any]],
    generated_from: dict[str, Any],
    engine: str = "policyengine_us",
) -> dict[str, Any]:
    ordered = sorted(concepts.values(), key=lambda a: (a.kind, a.id))
    concept_payloads = [concept_to_payload(a, pe_edges, engine) for a in ordered]
    n_inputs = sum(1 for a in ordered if a.kind == "input")
    n_outputs = sum(1 for a in ordered if a.kind == "output")
    return {
        "schema_version": REGISTRY_SCHEMA_VERSION,
        "registry_version": REGISTRY_VERSION,
        "jurisdiction": jurisdiction,
        "generated_from": generated_from,
        "concept_count": len(concept_payloads),
        "input_count": n_inputs,
        "output_count": n_outputs,
        "concepts": concept_payloads,
    }


def dump_yaml(payload: dict[str, Any]) -> str:
    header = (
        "# Typed concept registry — GENERATED, do not edit by hand.\n"
        "# Regenerate with: uv run python scripts/build_concept_registry.py --write\n"
        "# One concept per input slot or rule output; see docs/concept-registry.md.\n"
    )
    body = yaml.safe_dump(
        payload,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
        width=100,
    )
    return header + body


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


@dataclass
class BuildResult:
    files: dict[str, str]  # filename -> content
    summary: dict[str, Any]


def build(
    rulespec_root: Path,
    encode_repo: Path,
    countries: Iterable[str],
) -> BuildResult:
    # Load PolicyEngine mappings once per country from ``axiom-encode``. Each
    # country has its own mappings file and its own engine key, so UK concepts
    # gain ``policyengine_uk`` edges just as US concepts gain ``policyengine_us``.
    pe_by_country: dict[str, dict[str, Any]] = {}
    for country, (rel, engine) in PE_MAPPING_SOURCES.items():
        path = encode_repo / rel
        pe_by_country[country] = {
            "edges": load_pe_mappings(path),
            "engine": engine,
            "path": rel,
            "sha": git_file_sha(encode_repo, rel) or git_head_sha(encode_repo),
        }

    files: dict[str, str] = {}
    per_jurisdiction: dict[str, dict[str, int]] = {}
    total_concepts = 0
    total_pe_mapped = 0

    for country in countries:
        repo_name = COUNTRY_REPOS.get(country)
        if repo_name is None:
            continue
        country_repo = rulespec_root / repo_name
        if not country_repo.is_dir():
            continue
        rulespec_sha = git_head_sha(country_repo)
        pe = pe_by_country.get(country)
        # Mappings are keyed on the country slug; a sub-jurisdiction (``us-nc``,
        # ``uk-...``) shares its country's mapping file (edges join by exact id).
        edges = pe["edges"] if pe else {}
        engine = pe["engine"] if pe else "policyengine_us"

        for jur_dir in jurisdiction_dirs(country_repo, country):
            concepts, module_count = scan_jurisdiction(jur_dir)
            if not concepts:
                continue
            jurisdiction = jur_dir.name
            generated_from: dict[str, Any] = {
                "rulespec_repo": repo_name,
                "rulespec_sha": rulespec_sha,
                "module_count": module_count,
            }
            # Record the mappings provenance whenever a country-level mappings
            # file contributed edges — matching the prior US behaviour (the
            # block was attached to every US jurisdiction), now generalised so
            # UK jurisdictions carry the same provenance.
            if edges:
                generated_from["policyengine_mappings_repo"] = "axiom-encode"
                generated_from["policyengine_mappings_path"] = pe["path"]
                generated_from["policyengine_mappings_sha"] = pe["sha"]
            payload = build_jurisdiction_payload(
                jurisdiction, concepts, edges, generated_from, engine
            )
            files[f"{jurisdiction}.yaml"] = dump_yaml(payload)

            n_mapped = sum(1 for a in concepts.values() if a.id in edges)
            per_jurisdiction[jurisdiction] = {
                "concepts": payload["concept_count"],
                "inputs": payload["input_count"],
                "outputs": payload["output_count"],
                "pe_mapped": n_mapped,
                "modules": module_count,
            }
            total_concepts += payload["concept_count"]
            total_pe_mapped += n_mapped

    summary = {
        "jurisdictions": len(files),
        "total_concepts": total_concepts,
        "total_pe_mapped": total_pe_mapped,
        "per_jurisdiction": per_jurisdiction,
    }
    return BuildResult(files=files, summary=summary)


def write_files(result: BuildResult, data_root: Path) -> None:
    data_root.mkdir(parents=True, exist_ok=True)
    written = set(result.files)
    for name, content in result.files.items():
        (data_root / name).write_text(content)
    # Remove stale generated files for jurisdictions that no longer produce
    # concepts, so the directory always reflects the current scan.
    for existing in data_root.glob("*.yaml"):
        if existing.name not in written:
            existing.unlink()


def check_files(result: BuildResult, data_root: Path) -> list[str]:
    diffs: list[str] = []
    for name, content in result.files.items():
        target = data_root / name
        if not target.exists():
            diffs.append(f"missing: {name}")
        elif target.read_text() != content:
            diffs.append(f"stale: {name}")
    for existing in data_root.glob("*.yaml"):
        if existing.name not in result.files:
            diffs.append(f"orphan: {existing.name}")
    return diffs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    root_default = default_rulespec_root()
    parser.add_argument(
        "--rulespec-root",
        type=Path,
        default=root_default,
        help="Directory containing rulespec-* checkouts (default: nearest ancestor with rulespec-us)",
    )
    parser.add_argument(
        "--encode-repo",
        type=Path,
        default=root_default / "axiom-encode",
        help="Path to the axiom-encode checkout (source of PE mappings)",
    )
    parser.add_argument(
        "--countries",
        nargs="+",
        default=["us", "uk"],
        help="Country repos to scan (default: us uk)",
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=DEFAULT_DATA_ROOT,
        help="Output directory for the registry YAML files",
    )
    parser.add_argument("--write", action="store_true", help="Write files to disk")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if checked-in files differ from a fresh build",
    )
    args = parser.parse_args(argv)

    result = build(args.rulespec_root, args.encode_repo, args.countries)

    if args.check:
        diffs = check_files(result, args.data_root)
        if diffs:
            print("Concept registry is stale:", file=sys.stderr)
            for d in diffs:
                print(f"  {d}", file=sys.stderr)
            print(
                "Run: uv run python scripts/build_concept_registry.py --write",
                file=sys.stderr,
            )
            return 1
        print("Concept registry is up to date.")
        return 0

    if args.write:
        write_files(result, args.data_root)
        print(f"Wrote {len(result.files)} jurisdiction file(s) to {args.data_root}")

    s = result.summary
    print(
        f"jurisdictions={s['jurisdictions']} "
        f"concepts={s['total_concepts']} pe_mapped={s['total_pe_mapped']}"
    )
    for jur, stats in sorted(s["per_jurisdiction"].items()):
        print(
            f"  {jur:8s} concepts={stats['concepts']:6d} "
            f"in={stats['inputs']:6d} out={stats['outputs']:6d} "
            f"pe={stats['pe_mapped']:4d} modules={stats['modules']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
