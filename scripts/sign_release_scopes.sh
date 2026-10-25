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
# Two cases need a scope signed by hand, after which the same command keeps that
# manifest. (1) A manifest this script cannot show it signed is never replaced: one
# committed on main, or one that records reasoning logs, deleted files, a command of its
# own or a hand-picked file list, as an ingest PR's may. If a fix touches an artifact of
# such a scope, guard-ingested rejects the branch until the scope is signed again the
# way it was first signed. With the public key set, the self-check stops every re-run;
# without it, CI fails the PR. (2) This script cannot mark an artifact deleted. When the
# branch removes an artifact that main has, from a scope the script would sign, the run
# stops before step 1 and names the artifacts; sign that scope with --deleted-file.
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
    echo "(if the fix touches an artifact of a scope whose manifest this script cannot show it signed, see the header of $0 first)" >&2
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
# one or two commits and any that an earlier, stopped run made. Step 2's plan reads
# deletions against that merge base (MERGE_BASE), and it takes a manifest at the merge
# base with either ref (MAIN_BASES) for main's, in case origin/main is behind main.
GUARD_BASE="" MERGE_BASE="" MAIN_BASES=""
for ref in origin/main main; do
  base=$(git merge-base "$ref" HEAD 2>/dev/null) || continue
  [ -n "$GUARD_BASE" ] || { GUARD_BASE=$ref; MERGE_BASE=$base; }
  MAIN_BASES="$MAIN_BASES $base"
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
# - on this branch: untracked, or absent at the merge base with origin/main and with
#   main, whichever share history with HEAD. A manifest committed on main is never
#   replaced. With no main to compare, every committed manifest counts as main's.
# - this script's: it records the command command_for writes for its scope and no
#   reasoning logs, every entry has a sha256 (a deleted file's has none), and its files
#   are exactly the scope's artifacts in the commit it records: the whole scope, as the
#   signer infers it, not a hand-picked --file list. The signer derives everything else
#   in it from the repository, so signing it again loses nothing. Any other manifest,
#   such as an ingest PR's, may attest what this script cannot reproduce (reasoning logs,
#   say), so it is never replaced; if a fix changes its scope's artifacts, sign that
#   scope again the way it was signed.
# - stale: its files or their sha256s are not the scope's artifacts as the signer finds
#   them now, or the commit it was signed against is not in HEAD's history (after a
#   rebase, say). guard-ingested rejects either.
# An untracked manifest that is not readable JSON, such as one a signer interrupted
# mid-write leaves behind, is signed again too: it attests nothing.
# This script signs only the files a scope has, so it cannot mark an artifact deleted,
# which guard-ingested requires when the branch removes one that MERGE_BASE has. The
# plan stops the run before step 1 when a scope it would sign does that, and says how
# to sign the scope by hand. A manifest signed that way is kept.
# The plan is one "<action>\t<reason>" line per scope; the action is sign, resign or keep.
plan_signing() {  # guard-ref merge-base main-bases scope-list manifest... command...
  python3 - "$@" <<'PY'
import functools, hashlib, json, re, subprocess, sys
from pathlib import Path

guard_ref, merge_base, main_bases, scope_list, *manifest_commands = sys.argv[1:]
scopes = [line.split() for line in Path(scope_list).read_text().splitlines()]
if len(manifest_commands) != 2 * len(scopes):
    sys.exit("plan_signing: one manifest path and command per scope expected")
manifests = manifest_commands[:len(scopes)]
expected_commands = {
    tuple(scope): command for scope, command in zip(scopes, manifest_commands[len(scopes):])
}
ROOT = ".axiom/ingest-manifests"


def git(*args):
    return subprocess.run(["git", "--literal-pathspecs", *args], capture_output=True, check=False)


def names(result):
    return {p for p in result.stdout.decode("utf-8", "surrogateescape").split("\0") if p}


def listed(*args):
    result = git(*args)
    if result.returncode != 0:
        sys.exit(f"git {' '.join(args)}: {result.stderr.decode(errors='replace').strip()}")
    return names(result)


tracked = listed("ls-files", "-z", "--", ROOT)
on_main = (
    set().union(*(listed("ls-tree", "-r", "-z", "--name-only", b, "--", ROOT) for b in main_bases.split()))
    if main_bases.split()
    else tracked
)


def scope_paths(jur, cls, ver):
    return [
        f"data/corpus/sources/{jur}/{cls}/{ver}",
        f"data/corpus/inventory/{jur}/{cls}/{ver}.json",
        f"data/corpus/provisions/{jur}/{cls}/{ver}.jsonl",
        f"data/corpus/coverage/{jur}/{cls}/{ver}.json",
    ]


def committed(commit, jur, cls, ver):
    """The scope's artifact files in a commit, or None when the commit cannot be read."""
    result = git("ls-tree", "-r", "-z", "--name-only", commit, "--", *scope_paths(jur, cls, ver))
    return names(result) if result.returncode == 0 else None


def current(jur, cls, ver):
    """The files sign-ingest-manifest signs for the scope now (_infer_scope_artifacts)."""
    sources, *files = (Path(p) for p in scope_paths(jur, cls, ver))
    return [p for p in sources.rglob("*") if p.is_file()] + [p for p in files if p.exists()]


@functools.lru_cache(maxsize=None)
def in_history(commit):
    return git("merge-base", "--is-ancestor", commit, "HEAD").returncode == 0


def signing_commit(payload):
    git_metadata = payload.get("axiom_corpus_git")
    commit = git_metadata.get("commit") if isinstance(git_metadata, dict) else None
    return commit if isinstance(commit, str) and re.fullmatch(r"[0-9a-f]{40}", commit) else None


def this_scripts(payload, commit, jur, cls, ver):
    command = payload.get("command")
    text = command.get("text") if isinstance(command, dict) else None
    entries = payload.get("applied_files")
    if not (
        (payload.get("jurisdiction"), payload.get("document_class"), payload.get("version"))
        == (jur, cls, ver)
        and isinstance(text, str)
        and text == expected_commands[(jur, cls, ver)]
        and payload.get("reasoning_logs") == []
        and isinstance(entries, list)
        and all(
            isinstance(entry, dict)
            and isinstance(entry.get("path"), str)
            # A deleted file's entry has no sha256, and matches_artifacts reads one.
            and isinstance(entry.get("sha256"), str)
            for entry in entries
        )
    ):
        return False
    paths = {entry["path"] for entry in entries}
    return len(paths) == len(entries) and paths == committed(commit, jur, cls, ver)


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def matches_artifacts(entries, jur, cls, ver):
    """Whether the entries are what sign-ingest-manifest would sign for the scope now."""
    files = current(jur, cls, ver)
    signed = {entry["path"]: entry["sha256"] for entry in entries}
    if set(signed) != {p.as_posix() for p in files}:
        return False
    try:
        return all(sha256(p) == signed[p.as_posix()] for p in sorted(files))
    except OSError:
        return False


def classify(jur, cls, ver, path):
    if not Path(path).is_file():
        return "sign", ""
    if path in on_main:
        return "keep", ""
    try:
        payload = json.loads(Path(path).read_bytes())
    except (OSError, ValueError):
        payload = None
    if not isinstance(payload, dict):
        if path in tracked:
            return "keep", ""
        return "resign", "its untracked manifest is not readable JSON"
    commit = signing_commit(payload)
    if commit is None or not this_scripts(payload, commit, jur, cls, ver):
        return "keep", ""
    if not in_history(commit):
        return "resign", "the commit it was signed against is not in HEAD's history"
    if not matches_artifacts(payload["applied_files"], jur, cls, ver):
        return "resign", "its artifacts changed after it was signed"
    return "keep", ""


plan, removals = [], []
for (jur, cls, ver), path in zip(scopes, manifests):
    action, reason = classify(jur, cls, ver, path)
    plan.append(f"{action}\t{reason}")
    # Step 1 reports a missing artifact; only a scope that has all four can remove one.
    if action != "keep" and merge_base and all(Path(p).exists() for p in scope_paths(jur, cls, ver)):
        now = {p.as_posix() for p in current(jur, cls, ver)}
        removed = sorted((committed(merge_base, jur, cls, ver) or set()) - now)
        removals += [f"  {jur}/{cls}/{ver}: {p}" for p in removed]
if removals:
    print(
        f"nothing staged; these scopes remove artifacts that {guard_ref} has:",
        *removals,
        "guard-ingested needs each such scope's manifest to mark them deleted, which this",
        "script cannot sign. Sign each such scope by hand with axiom-corpus-ingest",
        "sign-ingest-manifest, passing --file for each of its artifacts and --deleted-file for",
        "each removed one, then run this command again: it keeps that manifest.",
        sep="\n",
        file=sys.stderr,
    )
    sys.exit(1)
print(*plan, sep="\n")
PY
}
# Resolve each rebuild command once, for both recognition and signing. Main-owned
# manifests are kept before command comparison; spare them the YAML lookup.
COMMANDS=()
for i in "${!SCOPES[@]}"; do
  read -r jur cls ver <<<"${SCOPES[$i]}"
  main_owned=""
  if [ -f "${MANIFESTS[$i]}" ]; then
    for base in $MAIN_BASES; do
      if git cat-file -e "$base:${MANIFESTS[$i]}" 2>/dev/null; then
        main_owned=1
        break
      fi
    done
    if [ -z "$MAIN_BASES" ] && git --literal-pathspecs ls-files --error-unmatch \
      -- "${MANIFESTS[$i]}" >/dev/null 2>&1; then
      main_owned=1
    fi
  fi
  if [ -n "$main_owned" ]; then
    COMMANDS+=("")
  else
    COMMANDS+=("$(command_for "$jur" "$cls" "$ver")")
  fi
done
PLAN=$(plan_signing "$GUARD_BASE" "$MERGE_BASE" "$MAIN_BASES" "$SCOPE_LIST" "${MANIFESTS[@]}" "${COMMANDS[@]}")
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
        # sign-ingest-manifest records the file a link points to, never the link's own
        # path, which is what guard-ingested looks up.
        if os.path.islink(path):
            problems.append(f"symlink {path}")
        elif not os.path.exists(path):
            problems.append(f"missing {path}")
        elif os.path.isdir(path):
            if not any(files for _, _, files in os.walk(path)):
                problems.append(f"empty {path}")  # git cannot commit an empty directory
            problems += [
                f"symlink {os.path.join(root, name)}"
                for root, dirs, files in os.walk(path)
                for name in sorted(dirs + files)
                if os.path.islink(os.path.join(root, name))
            ]
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
  uv run axiom-corpus-ingest sign-ingest-manifest \
    --jurisdiction "$jur" --document-class "$cls" --version "$ver" \
    --command "${COMMANDS[$i]}" ${output:+--output "$output"}
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
