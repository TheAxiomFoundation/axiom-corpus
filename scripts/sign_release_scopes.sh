#!/usr/bin/env bash
# Commit, sign and select the unreleased scopes of a draft release selector.
#
# Usage:
#   scripts/sign_release_scopes.sh <draft-selector.json> <predecessor-selector.json>
#
# Example (2026-09-11 program ingestion):
#   scripts/sign_release_scopes.sh \
#     docs/ingest-runs/2026-09-11-us-rulespec-program-ingestion-union.selector.json \
#     manifests/releases/us-rulespec-2026-08-23-canada-338-suspension-union.json
#
# Run from the repository root on a release branch cut from main AFTER the program
# PRs are merged. Tracked files must be clean; untracked data/corpus artifacts are
# expected. If any unreleased scope needs signing (it has no signed ingest manifest yet,
# or step 2 will sign it again), export AXIOM_CORPUS_INGEST_PRIVATE_KEY in this shell
# only (never written to a file); the script checks for it before it stages anything.
#
# The unreleased scopes are the draft selector's scopes minus the predecessor's.
# Order matters: the signer records HEAD and requires a clean tracked tree, and the
# signed manifest must describe committed artifact bytes. So: (1) force-add and commit
# the artifacts, (2) sign every unreleased scope against that commit, (3) commit those
# scopes' manifests and no others, (4) copy the draft to manifests/releases/<name>.json,
# deep-validate it against the committed artifacts and commit it.
#
# Re-running. Steps 1-3 skip what is already done, so a draft whose scopes were all
# committed and signed in their ingest PR goes on to the self-check and step 4 without
# committing anything first. A run can stop before the selector commit because a step
# failed or because it was interrupted. The interrupt can be Ctrl-C, which signals the
# whole foreground process group, or a SIGTERM or SIGHUP. The run acts on it once the
# running command has finished, and further signals cannot cut its cleanup short.
# Either way it unstages what it staged, puts back any committed manifest it had
# replaced, and deletes its copy of manifests/releases/<name>.json. It keeps its commits
# and the manifests it signed, which the next run reuses. Step 1 checks every scope's
# coverage and artifacts before it stages any. So after a failure, fix the cause and run
# the same command again, with nothing to clean up by hand. That holds when the fix
# changes, adds or removes an artifact of a scope whose manifest this script signed on
# this branch: step 2 signs that scope again (see "Plan step 2" below).
#
# A manifest this script did not sign is never replaced: one committed on main, or one
# from the scope's ingest PR, which may carry reasoning-log attestations this script
# cannot reproduce. If a fix touches an artifact of such a scope, guard-ingested rejects
# the branch until the scope is signed again the way its ingest PR signed it. With the
# public key set, the self-check stops every re-run; without it, CI fails the PR.
#
# Only a crash, or a signal the script does not handle, can leave <name>.json behind or
# leave files staged or a committed manifest replaced without saying so. Such signals
# include SIGKILL, Ctrl-\ (SIGQUIT) and the rarely sent USR1, USR2 and ALRM. Ctrl-\ is
# therefore the way to stop a run whose cleanup hangs.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
DRAFT="${1:?draft selector path}"
PREDECESSOR="${2:?predecessor selector path}"
[ -z "$(git status --porcelain --untracked-files=no)" ] || { echo "tracked tree is dirty; commit or stash first" >&2; exit 1; }
# On main itself the guard-ingested self-check below would diff an empty main...HEAD range.
[ "$(git symbolic-ref -q --short HEAD || true)" != main ] || { echo "on main; cut a release branch from main first" >&2; exit 1; }

NAME=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["name"])' "$DRAFT")
TARGET="manifests/releases/$NAME.json"
[ ! -e "$TARGET" ] || { echo "$TARGET already exists; selectors are immutable" >&2; exit 1; }

# Unreleased scopes: draft minus predecessor, as "jurisdiction document_class version" lines.
# (macOS ships bash 3.2: no mapfile, and no heredoc inside a process substitution.)
SCOPE_LIST=$(mktemp)
# From step 1 on, a run that stops before the selector commit undoes what it has not
# committed (see the header). The tracked tree was clean at the start, so the index
# differs from HEAD only by what this run staged. Bash 3.2 can show $? as 0 here after an
# expansion error or an untrapped signal, so a run that did not finish never exits 0.
STARTED="" COPIED="" CUT="" RESIGN_DIR=""
on_exit() {
  status=$?
  set +e
  # A second signal must not cut the cleanup short (two SIGHUPs from a closing terminal,
  # Ctrl-C after a failed step), and nor may a closed output pipe (output piped through
  # `head`) at its first message. The children inherit the ignored signals, except git
  # while it holds index.lock: it then handles them itself, drops the lock and fails. So
  # the unstage and the put-back below are each tried twice.
  trap '' INT TERM HUP PIPE
  rm -f "$SCOPE_LIST"
  [ -z "$RESIGN_DIR" ] || rm -rf "$RESIGN_DIR"
  [ -z "$CUT" ] || return 0
  # HEAD is checked too: an interrupt can land between the selector commit and CUT=1.
  if [ -n "$STARTED" ] && ! git cat-file -e "HEAD:$TARGET" 2>/dev/null; then
    if ! git diff --cached --quiet; then
      if git reset -q -- data/corpus .axiom/ingest-manifests "$TARGET" \
        || git reset -q -- data/corpus .axiom/ingest-manifests "$TARGET"; then
        echo "unstaged what this run staged but did not commit" >&2
      else
        echo "could not unstage this run's changes; unstage them before re-running" >&2
      fi
    fi
    # Step 3 moves each manifest signed again over the old one just before the sign commit.
    # An old one that was committed is put back here, and the next run signs it again.
    if ! git diff --quiet -- .axiom/ingest-manifests; then
      if git checkout -q -- .axiom/ingest-manifests \
        || git checkout -q -- .axiom/ingest-manifests; then
        echo "put back the committed manifests this run had replaced but not committed" >&2
      else
        echo "could not put back the committed manifests this run replaced; restore them before re-running" >&2
      fi
    fi
    if [ -n "$COPIED" ]; then
      rm -f "$TARGET"
      echo "deleted $TARGET, this run's copy of the draft: the selector was not cut" >&2
    fi
    echo "stopped before cutting $TARGET; fix the cause and run the same command again" >&2
    echo "(if the fix touches an artifact of a scope whose manifest this script did not sign, see the header of $0 first)" >&2
  fi
  [ "$status" -ne 0 ] || status=1
  exit "$status"
}
trap on_exit EXIT
# Bash runs a trapped signal's handler only once the foreground command has finished, so
# on_exit never races a commit that is still landing. Left untrapped, a SIGTERM or SIGHUP
# sent to this script alone would run on_exit at once, while git kept running.
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP
python3 - "$DRAFT" "$PREDECESSOR" > "$SCOPE_LIST" <<'PY'
import json, sys
draft, predecessor = (json.load(open(p))["scopes"] for p in sys.argv[1:3])
released = {(s["jurisdiction"], s["document_class"], s["version"]) for s in predecessor}
for s in sorted(draft, key=lambda s: (s["jurisdiction"], s["document_class"], s["version"])):
    key = (s["jurisdiction"], s["document_class"], s["version"])
    if key not in released:
        print(*key)
PY
# MANIFESTS holds each scope's signed ingest manifest, where sign-ingest-manifest writes it.
SCOPES=() MANIFESTS=()
while IFS= read -r line; do
  read -r jur cls ver <<<"$line"
  SCOPES+=("$line")
  MANIFESTS+=(".axiom/ingest-manifests/$jur/$cls/$ver.json")
done < "$SCOPE_LIST"
echo "unreleased scopes: ${#SCOPES[@]} (draft $NAME)"
[ "${#SCOPES[@]}" -gt 0 ] || { echo "nothing to sign" >&2; exit 1; }

# guard-ingested diffs base...head from their merge base, so with origin/main (or main) as
# the base it checks every commit this branch adds, as CI does for the PR: this run's zero,
# one or two commits and any that an earlier, stopped run made. That merge base also
# tells step 2 which manifests main already has.
GUARD_BASE="" MERGE_BASE=""
for ref in origin/main main; do
  if MERGE_BASE=$(git merge-base "$ref" HEAD 2>/dev/null); then GUARD_BASE=$ref; break; fi
done

# The command text step 2 signs a scope with is the rebuild command: the manifest that
# carries the scope's version when one exists, otherwise the run note that records the
# adapter or consolidation command.
manifest_for() {  # best-effort lookup of the manifest that produced a scope
  python3 - "$1" "$2" "$3" <<'PY'
import sys, yaml, glob
jur, cls, ver = sys.argv[1:4]
for m in sorted(glob.glob("manifests/*.yaml")):
    try:
        d = yaml.safe_load(open(m))
    except Exception:
        continue
    if not isinstance(d, dict) or d.get("version") != ver:
        continue
    docs = d.get("documents") or []
    if docs and docs[0].get("jurisdiction") == jur and docs[0].get("document_class") == cls:
        print(m); break
else:
    print("")
PY
}
command_for() {  # jurisdiction document_class version; plan_signing recognises the result
  case "$3" in
    *-consolidated|*chapters-06-07)
      echo "scripts/consolidate_release_scopes.py --base data/corpus --jurisdiction $1 --document-class $2 --target-version $3 (run note: docs/ingest-runs/2026-09-11-release-consolidation.md)" ;;
    *)
      m=$(manifest_for "$1" "$2" "$3") || return
      echo "axiom-corpus-ingest extract-official-documents --base data/corpus --version $3${m:+ --manifest $m} (run note: docs/ingest-runs/2026-09-10-*.md)" ;;
  esac
}

# Plan step 2 now, before step 1 stages anything, so the key check knows what it will
# sign. A scope with no manifest is signed. A scope with a manifest keeps it, unless
# this script signed that manifest on this branch and it no longer matches; then step 2
# signs the scope again. Such a manifest must be:
# - on this branch: untracked, or committed after the merge base with main. A manifest
#   committed on main is never replaced. With no main to compare, every committed
#   manifest counts as main's.
# - this script's: it records the command command_for writes for its scope, and no
#   reasoning logs or deleted files. The signer derives everything else in it from the
#   repository, so signing it again loses nothing. An ingest PR's manifest may attest
#   reasoning logs this script cannot reproduce, so it is never replaced; if a fix
#   changes its scope's artifacts, sign that scope again the way the ingest PR did.
# - stale: its files or their sha256s are not the scope's artifacts as the signer finds
#   them now, or the commit it was signed against is not in HEAD's history (after a
#   rebase, say). guard-ingested rejects either.
# An untracked manifest that is not readable JSON, such as one a signer interrupted
# mid-write leaves behind, is signed again too: it attests nothing.
# The plan is one "<action>\t<reason>" line per scope; the action is sign, resign or keep.
plan_signing() {  # merge-base-or-empty scope-list manifest...
  python3 - "$@" <<'PY'
import hashlib, json, re, subprocess, sys
from pathlib import Path

merge_base, scope_list, *manifests = sys.argv[1:]
scopes = [line.split() for line in Path(scope_list).read_text().splitlines()]
if len(scopes) != len(manifests):
    sys.exit("plan_signing: one manifest path per scope expected")
ROOT = ".axiom/ingest-manifests"


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, check=False)


def listed(*args):
    result = git(*args)
    if result.returncode != 0:
        sys.exit(f"git {' '.join(args)}: {result.stderr.decode(errors='replace').strip()}")
    return {p for p in result.stdout.decode("utf-8", "surrogateescape").split("\0") if p}


tracked = listed("ls-files", "-z", "--", ROOT)
on_main = listed("ls-tree", "-r", "-z", "--name-only", merge_base, "--", ROOT) if merge_base else tracked
in_history = {}


def signed_in_history(payload):
    git_metadata = payload.get("axiom_corpus_git")
    commit = git_metadata.get("commit") if isinstance(git_metadata, dict) else None
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        return False
    if commit not in in_history:
        in_history[commit] = git("merge-base", "--is-ancestor", commit, "HEAD").returncode == 0
    return in_history[commit]


def this_scripts(payload, jur, cls, ver):
    # The two forms command_for writes, whichever manifests/*.yaml it found.
    j, c, v = (re.escape(part) for part in (jur, cls, ver))
    script_command = re.compile(
        rf"scripts/consolidate_release_scopes\.py --base data/corpus --jurisdiction {j}"
        rf" --document-class {c} --target-version {v}"
        r" \(run note: docs/ingest-runs/2026-09-11-release-consolidation\.md\)"
        rf"|axiom-corpus-ingest extract-official-documents --base data/corpus --version {v}"
        r"( --manifest \S+)? \(run note: docs/ingest-runs/2026-09-10-\*\.md\)"
    )
    command = payload.get("command")
    text = command.get("text") if isinstance(command, dict) else None
    entries = payload.get("applied_files")
    return (
        (payload.get("jurisdiction"), payload.get("document_class"), payload.get("version"))
        == (jur, cls, ver)
        and isinstance(text, str)
        and script_command.fullmatch(text) is not None
        and payload.get("reasoning_logs") == []
        and isinstance(entries, list)
        and all(
            isinstance(entry, dict)
            and isinstance(entry.get("path"), str)
            and isinstance(entry.get("sha256"), str)
            and entry.get("deleted") is not True
            for entry in entries
        )
    )


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def matches_artifacts(entries, jur, cls, ver):
    """Whether the entries are what sign-ingest-manifest would sign for the scope now."""
    base = Path("data/corpus")
    files = [p for p in (base / "sources" / jur / cls / ver).rglob("*") if p.is_file()]
    files += [
        p
        for p in (
            base / "inventory" / jur / cls / f"{ver}.json",
            base / "provisions" / jur / cls / f"{ver}.jsonl",
            base / "coverage" / jur / cls / f"{ver}.json",
        )
        if p.exists()
    ]
    signed = {entry["path"]: entry["sha256"] for entry in entries}
    if len(signed) != len(entries) or set(signed) != {p.as_posix() for p in files}:
        return False
    try:
        return all(sha256(p) == signed[p.as_posix()] for p in sorted(files))
    except OSError:
        return False


for (jur, cls, ver), path in zip(scopes, manifests):
    if not Path(path).is_file():
        print("sign\t")
        continue
    if path in on_main:
        print("keep\t")
        continue
    try:
        payload = json.loads(Path(path).read_bytes())
    except (OSError, ValueError):
        payload = None
    if not isinstance(payload, dict):
        print("keep\t" if path in tracked else "resign\tits untracked manifest is not readable JSON")
    elif not this_scripts(payload, jur, cls, ver):
        print("keep\t")
    elif not signed_in_history(payload):
        print("resign\tthe commit it was signed against is not in HEAD's history")
    elif not matches_artifacts(payload["applied_files"], jur, cls, ver):
        print("resign\tits artifacts changed after it was signed")
    else:
        print("keep\t")
PY
}
PLAN=$(plan_signing "$MERGE_BASE" "$SCOPE_LIST" "${MANIFESTS[@]}")
ACTIONS=() REASONS=()
while IFS=$'\t' read -r action reason; do
  ACTIONS+=("$action")
  REASONS+=("$reason")
done <<<"$PLAN"

# Signing needs the private key. Check for it now, before step 1 stages anything, and
# only when step 2 will sign some scope.
TO_SIGN=0
for i in "${!SCOPES[@]}"; do
  [ "${ACTIONS[$i]}" = keep ] || TO_SIGN=$((TO_SIGN + 1))
done
if [ "$TO_SIGN" -gt 0 ] && [ -z "${AXIOM_CORPUS_INGEST_PRIVATE_KEY:-}" ]; then
  echo "$TO_SIGN of ${#SCOPES[@]} unreleased scopes need signing; export AXIOM_CORPUS_INGEST_PRIVATE_KEY in this shell first" >&2
  for i in "${!SCOPES[@]}"; do
    [ "${ACTIONS[$i]}" != resign ] || echo "  ${MANIFESTS[$i]} will be signed again: ${REASONS[$i]}" >&2
  done
  exit 1
fi

# 1. force-add artifacts (data/ is gitignored) and commit them. Every scope's artifacts
#    are checked before any is staged, and one `git add` stages them all (git leaves the
#    index untouched when a path is missing), so a failure here leaves nothing staged.
STARTED=1
ARTIFACTS=()
for line in "${SCOPES[@]}"; do
  read -r jur cls ver <<<"$line"
  ARTIFACTS+=("data/corpus/coverage/$jur/$cls/$ver.json"
              "data/corpus/inventory/$jur/$cls/$ver.json"
              "data/corpus/provisions/$jur/$cls/$ver.jsonl"
              "data/corpus/sources/$jur/$cls/$ver")
done
python3 - "${ARTIFACTS[@]}" <<'PY'
import json, os, sys
paths, problems = sys.argv[1:], []
for coverage, *rest in (paths[i:i + 4] for i in range(0, len(paths), 4)):
    for path in (coverage, *rest):
        if not os.path.exists(path):
            problems.append(f"missing {path}")
        elif os.path.isdir(path) and not any(files for _, _, files in os.walk(path)):
            problems.append(f"empty {path}")  # git cannot commit an empty directory
    if not os.path.exists(coverage):
        continue
    try:
        with open(coverage) as f:
            complete = json.load(f)["complete"] is True
    except (OSError, ValueError, LookupError, TypeError) as error:
        problems.append(f"unreadable {coverage}: {error}")
        continue
    if not complete:
        problems.append(f"coverage not complete: {coverage}")
if problems:
    print("nothing staged; fix these first:", *problems, sep="\n  ", file=sys.stderr)
    sys.exit(1)
PY
git add -f -- "${ARTIFACTS[@]}"
if git diff --cached --quiet; then
  echo "artifacts already committed; skipping data commit"
else
git commit -q -m "$(printf 'Add %s artifacts (unsigned data commit)\n\nSources, inventory, provisions and coverage for the %d unreleased scopes selected by\n%s. Signed ingest manifests follow in the next commit.\n\nCo-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>' "$NAME" "${#SCOPES[@]}" "$NAME")"
fi
echo "data commit: $(git rev-parse --short HEAD)"

# 2. sign each scope against the clean data commit, as planned above. The signer needs a
#    clean tracked tree, so a manifest signed again goes aside, to RESIGN_DIR, until
#    step 3: writing it over a committed copy now would stop every later signing.
for i in "${!SCOPES[@]}"; do
  read -r jur cls ver <<<"${SCOPES[$i]}"
  output=""
  case "${ACTIONS[$i]}" in
    keep)
      # Already signed, by an earlier run or in the scope's ingest PR (its manifest may carry
      # reasoning-log attestations this script cannot reproduce). guard-ingested checks it
      # against the artifacts in whichever PR commits them: this branch's, or the ingest PR's.
      echo "already signed, keeping existing manifest: $jur/$cls/$ver"
      continue ;;
    resign)
      echo "signing again: $jur/$cls/$ver (${REASONS[$i]})"
      [ -n "$RESIGN_DIR" ] || RESIGN_DIR=$(mktemp -d .sign-release-scopes.XXXXXX)
      output="$RESIGN_DIR/$jur/$cls/$ver.json" ;;
  esac
  cmd=$(command_for "$jur" "$cls" "$ver")
  uv run axiom-corpus-ingest sign-ingest-manifest \
    --jurisdiction "$jur" --document-class "$cls" --version "$ver" \
    --command "$cmd" ${output:+--output "$output"}
done

# 3. move each manifest signed again into place, then commit the unreleased scopes'
#    manifests and self-check with the public key if available. Only those manifests are
#    staged: an untracked manifest of any other scope stays out of the commit. Nothing is
#    staged when every scope kept a manifest that was committed before this run.
for i in "${!SCOPES[@]}"; do
  [ "${ACTIONS[$i]}" = resign ] || continue
  read -r jur cls ver <<<"${SCOPES[$i]}"
  mv -f "$RESIGN_DIR/$jur/$cls/$ver.json" "${MANIFESTS[$i]}"
done
git add -- "${MANIFESTS[@]}"
if git diff --cached --quiet; then
  echo "signed manifests already committed; skipping sign commit"
else
  git commit -q -m "$(printf 'Sign %s scopes\n\nCo-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>' "$NAME")"
  echo "sign commit: $(git rev-parse --short HEAD)"
fi
if [ -z "${AXIOM_CORPUS_INGEST_PUBLIC_KEY:-}" ]; then
  echo "AXIOM_CORPUS_INGEST_PUBLIC_KEY not set; CI will run guard-ingested on the PR"
elif [ -z "$GUARD_BASE" ]; then
  echo "neither origin/main nor main shares history with HEAD; CI will run guard-ingested on the PR"
else
  echo "guard-ingested: checking $GUARD_BASE...HEAD"
  uv run axiom-corpus-ingest guard-ingested --base-ref "$GUARD_BASE" --head-ref HEAD \
    || { echo "guard-ingested failed; not cutting $TARGET" >&2; exit 1; }
  echo "guard-ingested: ok"
fi

# 4. track the immutable selector, deep-validate it against the committed artifacts and
#    commit it. If any of that fails, on_exit deletes the copy, so the next run does not
#    take it for a cut selector.
COPIED=1
cp "$DRAFT" "$TARGET"
uv run axiom-corpus-ingest validate-release --base data/corpus --release "$TARGET" --ignore-r2-missing --max-issues 20 \
  || { echo "validate-release failed; not cutting $TARGET" >&2; exit 1; }
git add "$TARGET"
git commit -q -m "$(printf 'Cut %s\n\nCo-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>' "$NAME")"
CUT=1
echo "selector commit: $(git rev-parse --short HEAD)"
echo "next: open a PR (CI runs guard-ingested and validates the selector), then"
echo "      uv run --extra dev python scripts/publish_corpus.py --release $TARGET --dry-run"
