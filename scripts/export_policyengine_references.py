#!/usr/bin/env python3
"""Export the PolicyEngine-US references every program bundle's screener tier
draws on, from one release: the newest one by default.

``policyengine_us.release`` in the programs config is ``latest`` (the newest
version published on PyPI) or a version number. The script finds the release
commit on policyengine-us main (the commit that set that version), reads every
parameter and variable file at that commit once, and gives each program the
references of its files:

- its federal folders (``policyengine_folders``), which apply to every state;
- each state's folders for the program (``state_folders``: a segment after
  ``gov/states/<st>/`` that names the program, or a pattern on the path
  there). A reference from a state folder records that state.

A citation path is derived only where the URL's own structure carries it
(Cornell, eCFR, uscode.house.gov, govinfo, SSA POMS); the bundle builder joins
the rest to corpus manifests by URL and grades exclusions itself.

Usage::

    python scripts/export_policyengine_references.py \\
        manifests/program-bundles/programs.config.yaml --checkout ~/policyengine-us

One export per program, at the config's ``policyengine_us.references`` path.
Each records the version and commit it read, so a rebuild from the same
export is exact; re-running it moves the bundles to the newest release.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import urllib.request
from collections import defaultdict
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
ROOT = "policyengine_us"
PYPI = "https://pypi.org/pypi/policyengine-us/json"
QUOTED_URL = re.compile(r"""["'](https?://[^"'\s]+)["']""")
PY_REFERENCE = re.compile(r"^(\s+)reference\s*=", re.M)
STATE_FILE = re.compile(r"^(?:parameters|variables)/gov/states/([a-z]{2})/(.+)$")


def git(checkout: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(checkout), *args], check=True, capture_output=True, text=True
    ).stdout


def read_files(checkout: Path, commit: str, paths: list[str]) -> dict[str, str]:
    """Every file's text at a commit, through one ``git cat-file --batch``."""
    proc = subprocess.run(
        ["git", "-C", str(checkout), "cat-file", "--batch"],
        input="".join(f"{commit}:{p}\n" for p in paths).encode(),
        check=True,
        capture_output=True,
    )
    out, data, pos = {}, proc.stdout, 0
    for path in paths:
        end = data.index(b"\n", pos)
        header = data[pos:end].decode().split()
        pos = end + 1
        if len(header) < 3 or header[1] != "blob":
            continue
        size = int(header[2])
        out[path] = data[pos : pos + size].decode("utf-8", errors="replace")
        pos += size + 1
    return out


def newest_published() -> str | None:
    """The newest policyengine-us version on PyPI, or None when PyPI is unreachable."""
    try:
        with urllib.request.urlopen(PYPI, timeout=20) as res:
            return json.load(res)["info"]["version"]
    except (OSError, ValueError, KeyError):
        return None


def release_commit(checkout: Path, version: str) -> str | None:
    """The commit on main that set the package version: the release commit."""
    found = git(
        checkout,
        "log",
        "origin/main",
        "--reverse",
        "--format=%H",
        f'-Sversion = "{version}"',
        "--",
        "pyproject.toml",
    ).split()
    return found[0] if found else None


def resolve_release(checkout: Path, release: str) -> tuple[str, str]:
    """(version, commit) of the configured release: ``latest`` or a version number.

    ``latest`` is the newest version published on PyPI; main can be a version
    ahead while its release publishes. Without PyPI, main's own version."""
    git(checkout, "fetch", "--quiet", "origin", "main")
    version = newest_published() if release == "latest" else release
    if version is None:
        m = re.search(
            r'^version = "([^"]+)"', git(checkout, "show", "origin/main:pyproject.toml"), re.M
        )
        version = m.group(1) if m else None
    commit = release_commit(checkout, version) if version else None
    if not version or not commit:
        raise SystemExit(f"policyengine-us release {release!r}: no release commit on main")
    return version, commit


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


def file_references(path: str, text: str) -> list[tuple[str, str | None]]:
    if path.endswith(".yaml"):
        # Every scalar as text: PolicyEngine dates some values 0000-01-01.
        try:
            return yaml_references(yaml.load(text, Loader=yaml.BaseLoader))
        except yaml.YAMLError:
            return []
    return python_references(text)


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


def state_program_match(pattern: str, rel: str) -> bool:
    """Whether a path under gov/states/<st>/ is the program's: a pattern that
    starts with ^ matches the path; otherwise one of the first two segments
    (an agency, then a program, or the program alone) must be the program."""
    if pattern.startswith("^"):
        return re.search(pattern, rel) is not None
    return any(re.fullmatch(pattern, seg) for seg in rel.split("/")[:2])


def programs_of(path: str, programs: dict) -> list[tuple[str, str | None]]:
    """(program, state) pairs a PolicyEngine file belongs to; state None for a federal folder."""
    short = path.removeprefix(f"{ROOT}/")
    rel = short.split("/", 1)[1] if "/" in short else short
    out: list[tuple[str, str | None]] = []
    m = STATE_FILE.match(short)
    for pid, prog in programs.items():
        if (
            m
            and prog.get("state_folders")
            and state_program_match(prog["state_folders"], m.group(2))
        ):
            out.append((pid, m.group(1)))
            continue
        for folder in prog.get("policyengine_folders") or []:
            if rel == folder or rel.startswith(folder + "/"):
                out.append((pid, None))
                break
    return out


def export(config_path: Path, checkout: Path) -> dict[str, dict]:
    cfg = yaml.safe_load(config_path.read_text())
    pin = cfg["policyengine_us"]
    version, commit = resolve_release(checkout, str(pin.get("release", "latest")))
    programs = cfg["programs"]
    files = [
        p
        for p in git(
            checkout,
            "ls-tree",
            "-r",
            "--name-only",
            commit,
            "--",
            f"{ROOT}/parameters/gov",
            f"{ROOT}/variables/gov",
        ).split()
        if p.endswith((".yaml", ".py"))
    ]
    owners = {p: programs_of(p, programs) for p in files}
    texts = read_files(checkout, commit, [p for p, o in owners.items() if o])
    cited: dict[str, dict[str, dict]] = defaultdict(dict)
    files_read: dict[str, int] = defaultdict(int)
    for path, text in texts.items():
        short = path.removeprefix(f"{ROOT}/")
        for pid, state in owners[path]:
            files_read[pid] += 1
            for url, title in file_references(path, text):
                ref = cited[pid].setdefault(url, {"files": [], "titles": [], "states": []})
                if short not in ref["files"]:
                    ref["files"].append(short)
                if title and title not in ref["titles"]:
                    ref["titles"].append(title)
                if state and state not in ref["states"]:
                    ref["states"].append(state)
    date = git(checkout, "show", "-s", "--format=%cs", commit).strip()
    out = {}
    for pid, prog in programs.items():
        references = []
        for url, ref in sorted(cited[pid].items()):
            found = citation_from_url(url)
            references.append(
                {
                    "url": url,
                    "kind": found[0] if found else None,
                    "citation": found[1] if found else None,
                    "titles": ref["titles"],
                    "states": sorted(ref["states"]),
                    "files": ref["files"],
                }
            )
        out[pid] = {
            "policyengine_us_release": str(pin.get("release", "latest")),
            "policyengine_us_version": version,
            "policyengine_us_commit": commit,
            "policyengine_us_commit_date": date,
            "program": pid,
            "folders": prog.get("policyengine_folders") or [],
            "state_folders": prog.get("state_folders"),
            "derived_by": "scripts/export_policyengine_references.py",
            "files_read": files_read[pid],
            "references": references,
        }
    return out


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("config", type=Path, help="manifests/program-bundles/programs.config.yaml")
    ap.add_argument("--checkout", type=Path, required=True, help="a policyengine-us git checkout")
    args = ap.parse_args()
    cfg = yaml.safe_load(args.config.read_text())
    for pid, data in export(args.config, args.checkout.expanduser()).items():
        target = REPO / cfg["policyengine_us"]["references"].format(program=pid)
        target.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
        states = len({s for r in data["references"] for s in r["states"]})
        print(
            f"{pid}: {len(data['references'])} references from {data['files_read']} files "
            f"({states} states) at policyengine-us {data['policyengine_us_version']}"
        )


if __name__ == "__main__":
    main()
