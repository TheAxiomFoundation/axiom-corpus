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
# expected. If any unreleased scope has no signed ingest manifest yet, export
# AXIOM_CORPUS_INGEST_PRIVATE_KEY in this shell only (never written to a file); the
# script checks for it before it stages anything.
#
# The unreleased scopes are the draft selector's scopes minus the predecessor's.
# Order matters: the signer records HEAD and requires a clean tracked tree, and the
# signed manifest must describe committed artifact bytes. So: (1) force-add and commit
# the artifacts, (2) sign every unreleased scope against that commit, (3) commit the
# manifests, (4) copy the draft to manifests/releases/<name>.json, deep-validate it
# against the committed artifacts and commit it.
#
# Re-running. Steps 1-3 skip what is already done, so a draft whose scopes were all
# committed and signed in their ingest PR goes on to the self-check and step 4 without
# committing anything first. A run can stop before the selector commit because a step
# failed or because it was interrupted. The interrupt can be Ctrl-C, which signals the
# whole foreground process group, or a SIGTERM or SIGHUP. The run acts on it once the
# running command has finished, and further signals cannot cut its cleanup short.
# Either way it unstages what it staged and deletes its copy of
# manifests/releases/<name>.json. It keeps its commits and the manifests it signed,
# which the next run reuses. Step 1 checks every scope's coverage and artifacts before
# it stages any. So after a failure, fix the cause and run the same command again, with
# nothing to clean up by hand.
#
# There is one exception: a fix that changes, adds or removes any artifact of a scope
# that already has a manifest. The manifest no longer matches, so guard-ingested
# rejects the branch. With the public key set, the self-check stops every re-run;
# without it, CI fails the PR. So commit the fix and delete the scope's manifest
# (.axiom/ingest-manifests/<jurisdiction>/<class>/<version>.json), committing the
# deletion if the manifest was committed. Step 2 then signs the scope again. A manifest
# from the scope's ingest PR may carry reasoning-log attestations this script cannot
# reproduce, so re-sign such a scope the way its ingest PR did instead.
#
# Only a crash, or a signal the script does not handle, can leave <name>.json behind or
# leave files staged without saying so. Such signals are SIGKILL, Ctrl-\ (SIGQUIT) and
# the rarely sent USR1, USR2 and ALRM. Ctrl-\ is therefore the way to stop a run whose
# cleanup hangs.
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
STARTED="" COPIED="" CUT=""
on_exit() {
  status=$?
  set +e
  # A second signal must not cut the cleanup short (two SIGHUPs from a closing terminal,
  # Ctrl-C after a failed step), and nor may a closed output pipe (output piped through
  # `head`) at its first message. The children inherit the ignored signals, except git
  # while it holds index.lock: it then handles them itself, drops the lock and fails. So
  # the unstage below is tried twice.
  trap '' INT TERM HUP PIPE
  rm -f "$SCOPE_LIST"
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
    if [ -n "$COPIED" ]; then
      rm -f "$TARGET"
      echo "deleted $TARGET, this run's copy of the draft: the selector was not cut" >&2
    fi
    echo "stopped before cutting $TARGET; fix the cause and run the same command again" >&2
    echo "(if the fix touches an artifact of a scope that has a manifest, see the header of $0 first)" >&2
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
SCOPES=()
while IFS= read -r line; do SCOPES+=("$line"); done < "$SCOPE_LIST"
echo "unreleased scopes: ${#SCOPES[@]} (draft $NAME)"
[ "${#SCOPES[@]}" -gt 0 ] || { echo "nothing to sign" >&2; exit 1; }

# Signing needs the private key. Check for it now, before step 1 stages anything, and
# only when some scope has no manifest for step 2 to keep.
signed() { [ -f ".axiom/ingest-manifests/$1/$2/$3.json" ]; }
UNSIGNED=0
for line in "${SCOPES[@]}"; do
  read -r jur cls ver <<<"$line"
  signed "$jur" "$cls" "$ver" || UNSIGNED=$((UNSIGNED + 1))
done
if [ "$UNSIGNED" -gt 0 ] && [ -z "${AXIOM_CORPUS_INGEST_PRIVATE_KEY:-}" ]; then
  echo "$UNSIGNED of ${#SCOPES[@]} unreleased scopes need signing; export AXIOM_CORPUS_INGEST_PRIVATE_KEY in this shell first" >&2
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

# 2. sign each scope against the clean data commit. The command text is the rebuild
#    command: the manifest that carries the scope's version when one exists, otherwise
#    the run note that records the adapter or consolidation command.
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
for line in "${SCOPES[@]}"; do
  read -r jur cls ver <<<"$line"
  if signed "$jur" "$cls" "$ver"; then
    # Already signed, by an earlier run or in the scope's ingest PR (its manifest may carry
    # reasoning-log attestations this script cannot reproduce). guard-ingested checks it
    # against the artifacts in whichever PR commits them: this branch's, or the ingest PR's.
    echo "already signed, keeping existing manifest: $jur/$cls/$ver"
    continue
  fi
  m=$(manifest_for "$jur" "$cls" "$ver")
  case "$ver" in
    *-consolidated|*chapters-06-07)
      cmd="scripts/consolidate_release_scopes.py --base data/corpus --jurisdiction $jur --document-class $cls --target-version $ver (run note: docs/ingest-runs/2026-09-11-release-consolidation.md)" ;;
    *)
      cmd="axiom-corpus-ingest extract-official-documents --base data/corpus --version $ver"
      [ -n "$m" ] && cmd="$cmd --manifest $m"
      cmd="$cmd (run note: docs/ingest-runs/2026-09-10-*.md)" ;;
  esac
  uv run axiom-corpus-ingest sign-ingest-manifest \
    --jurisdiction "$jur" --document-class "$cls" --version "$ver" \
    --command "$cmd"
done

# 3. commit the signed manifests and self-check with the public key if available. Nothing
#    is staged when every scope kept a manifest that was committed before this run.
git add .axiom/ingest-manifests
if git diff --cached --quiet; then
  echo "signed manifests already committed; skipping sign commit"
else
  git commit -q -m "$(printf 'Sign %s scopes\n\nCo-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>' "$NAME")"
  echo "sign commit: $(git rev-parse --short HEAD)"
fi
# guard-ingested diffs base...head from their merge base, so with origin/main (or main) as
# the base it checks every commit this branch adds, as CI does for the PR: this run's zero,
# one or two commits and any that an earlier, stopped run made.
GUARD_BASE=""
for ref in origin/main main; do
  if git merge-base "$ref" HEAD >/dev/null 2>&1; then GUARD_BASE=$ref; break; fi
done
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
