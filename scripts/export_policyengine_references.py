#!/usr/bin/env python3
"""Export the PolicyEngine-US references a program bundle's screener tier
draws on, from one pinned release.

Reads every parameter and variable file under the folders the bundle config
names (``screener.policyengine_us.folders``) at the pinned commit of a local
policyengine-us checkout, and records each reference URL once with every file
that cites it. A citation path is derived only where the URL's own structure
carries it (Cornell, eCFR, uscode.house.gov); the bundle builder joins the rest
to corpus manifests by URL and grades exclusions itself.

Usage::

    git -C ~/policyengine-us fetch origin main
    python scripts/export_policyengine_references.py \\
        manifests/program-bundles/us-az-snap.config.yaml --checkout ~/policyengine-us

The export is written to the config's ``screener.references`` path. It is
dated by the pinned commit, so the same pin always gives the same file.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
ROOT = "policyengine_us"
QUOTED_URL = re.compile(r"""["'](https?://[^"'\s]+)["']""")
PY_REFERENCE = re.compile(r"^(\s+)reference\s*=", re.M)


def git(checkout: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(checkout), *args], check=True, capture_output=True, text=True
    ).stdout


def yaml_references(node) -> list[tuple[str, str | None]]:
    """Every reference in a parameter file, as (URL, title): an href, or a
    string under a reference key. Multi-state files name the state in the title."""
    out: list[tuple[str, str | None]] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "reference":
                items = value if isinstance(value, list) else [value]
                for item in items:
                    href = item.get("href") if isinstance(item, dict) else item
                    title = item.get("title") if isinstance(item, dict) else None
                    if isinstance(href, str) and href.startswith("http"):
                        out.append((href.strip(), title if isinstance(title, str) else None))
            else:
                out.extend(yaml_references(value))
    elif isinstance(node, list):
        for item in node:
            out.extend(yaml_references(item))
    return out


def python_references(text: str) -> list[tuple[str, str | None]]:
    """Every URL in a variable's ``reference =`` assignment, up to the next attribute."""
    out: list[tuple[str, str | None]] = []
    for m in PY_REFERENCE.finditer(text):
        indent = m.group(1)
        block = []
        for line in text[m.start() :].splitlines()[1:]:
            if re.match(rf"^{indent}[A-Za-z_]\w*\s*=|^{indent}def |^\S", line):
                break
            block.append(line)
        first = text[m.start() :].splitlines()[0]
        out.extend((url, None) for url in QUOTED_URL.findall("\n".join([first, *block])))
    return out


def _frag_parts(frag: str) -> list[str]:
    return [x for x in re.split(r"[_\-/]", frag.replace("substep", "").replace("subst", "")) if x]


def citation_from_url(url: str) -> tuple[str, str] | None:
    """(kind, corpus citation path) where the URL's structure carries the citation."""
    m = re.search(r"law\.cornell\.edu/uscode/text/(\d+)/(\d+[a-z\-]*)(?:#(.*))?$", url)
    if m:
        tail = _frag_parts(m.group(3) or "")
        return "statute", "/".join(["us", "statute", m.group(1), m.group(2), *tail[:4]])
    m = re.search(r"law\.cornell\.edu/cfr/text/(\d+)/(\d+)\.(\d+)(?:#(.*))?", url)
    if m:
        tail = _frag_parts(m.group(4) or "")
        return "regulation", "/".join(
            ["us", "regulation", m.group(1), m.group(2), m.group(3), *tail[:3]]
        )
    m = re.search(
        r"ecfr\.gov/.*?title-(\d+).*?section-(\d+)\.(\d+)(?:#p-\d+\.\d+((?:\([^)]+\))+))?", url
    )
    if m:
        tail = re.findall(r"\(([^)]+)\)", m.group(4) or "")
        return "regulation", "/".join(
            ["us", "regulation", m.group(1), m.group(2), m.group(3), *tail[:3]]
        )
    m = re.search(
        r"uscode\.house\.gov/view\.xhtml\?.*?USC-prelim-title(\d+)-section(\d+[a-z\-]*)", url, re.I
    )
    if m:
        return "statute", f"us/statute/{m.group(1)}/{m.group(2)}"
    m = re.search(r"ecfr\.gov/.*?title-(\d+).*?part-(\d+)(?:/|$)", url)
    if m:
        return "regulation", f"us/regulation/{m.group(1)}/{m.group(2)}"
    # An edition of the US Code on govinfo: USCODE-2023-title7-chap51-sec2015.
    m = re.search(
        r"govinfo\.gov/.*USCODE-\d{4}-title(\d+)-[^/]*?sec(\d+[a-z\-]*?)\.(?:htm|pdf)", url
    )
    if m:
        return "statute", f"us/statute/{m.group(1)}/{m.group(2)}"
    # SSA POMS, SI series: poms.nsf/lnx/0501401001 is SI 01401.001.
    m = re.search(r"ssa\.gov/poms\.nsf/lnx/05(\d{5})(\d{3})", url)
    if m:
        return "manual", f"us/manual/ssa/poms/si/{m.group(1)}.{m.group(2)}"
    return None


def export(config_path: Path, checkout: Path) -> dict:
    cfg = yaml.safe_load(config_path.read_text())
    pin = cfg["screener"]["policyengine_us"]
    commit = pin["commit"]
    files = git(
        checkout,
        "ls-tree",
        "-r",
        "--name-only",
        commit,
        "--",
        *[
            f"{ROOT}/{kind}/{folder}"
            for folder in pin["folders"]
            for kind in ("parameters", "variables")
        ],
    ).split()
    cited: dict[str, list[str]] = {}
    titles: dict[str, list[str]] = {}
    for path in sorted(files):
        if not path.endswith((".yaml", ".py")):
            continue
        text = git(checkout, "show", f"{commit}:{path}")
        if path.endswith(".yaml"):
            # Every scalar as text: PolicyEngine dates some values 0000-01-01.
            try:
                urls = yaml_references(yaml.load(text, Loader=yaml.BaseLoader))
            except yaml.YAMLError:
                urls = []
        else:
            urls = python_references(text)
        short = path.removeprefix(f"{ROOT}/")
        for url, title in urls:
            if short not in cited.setdefault(url, []):
                cited[url].append(short)
            if title and title not in titles.setdefault(url, []):
                titles[url].append(title)
    references = []
    for url, citing in sorted(cited.items()):
        found = citation_from_url(url)
        references.append(
            {
                "url": url,
                "kind": found[0] if found else None,
                "citation": found[1] if found else None,
                "titles": titles.get(url, []),
                "files": citing,
            }
        )
    return {
        "policyengine_us_version": pin["version"],
        "policyengine_us_commit": commit,
        "policyengine_us_commit_date": git(checkout, "show", "-s", "--format=%cs", commit).strip(),
        "program": cfg["program"],
        "state": cfg["jurisdiction"],
        "folders": pin["folders"],
        "derived_by": "scripts/export_policyengine_references.py",
        "files_read": sum(p.endswith((".yaml", ".py")) for p in files),
        "references": references,
    }


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("config", type=Path, help="manifests/program-bundles/<id>.config.yaml")
    ap.add_argument("--checkout", type=Path, required=True, help="a policyengine-us git checkout")
    args = ap.parse_args()
    out = export(args.config, args.checkout.expanduser())
    cfg = yaml.safe_load(args.config.read_text())
    target = REPO / cfg["screener"]["references"]
    target.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(
        f"{len(out['references'])} references from {out['files_read']} files "
        f"at policyengine-us {out['policyengine_us_version']} ({out['policyengine_us_commit'][:10]})"
    )


if __name__ == "__main__":
    main()
