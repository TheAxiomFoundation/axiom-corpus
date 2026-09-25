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
# PRs are merged, with AXIOM_CORPUS_INGEST_PRIVATE_KEY exported in this shell only
# (never written to a file). Tracked files must be clean; untracked data/corpus
# artifacts are expected.
#
# The unreleased scopes are the draft selector's scopes minus the predecessor's.
# Order matters: the signer records HEAD and requires a clean tracked tree, and the
# signed manifest must describe committed artifact bytes. So: (1) force-add and commit
# the artifacts, (2) sign every unreleased scope against that commit, (3) commit the
# manifests, (4) copy the draft to manifests/releases/<name>.json, deep-validate it
# against the committed artifacts and commit it.
#
# Steps 1-3 skip what is already done: a run that stopped while signing can be re-run
# as is, and a draft whose scopes were all committed and signed in their ingest PR goes
# on to the self-check and step 4 without committing anything first.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
DRAFT="${1:?draft selector path}"
PREDECESSOR="${2:?predecessor selector path}"
: "${AXIOM_CORPUS_INGEST_PRIVATE_KEY:?export AXIOM_CORPUS_INGEST_PRIVATE_KEY in this shell first}"
[ -z "$(git status --porcelain --untracked-files=no)" ] || { echo "tracked tree is dirty; commit or stash first" >&2; exit 1; }

NAME=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["name"])' "$DRAFT")
TARGET="manifests/releases/$NAME.json"
[ ! -e "$TARGET" ] || { echo "$TARGET already exists; selectors are immutable" >&2; exit 1; }

# Unreleased scopes: draft minus predecessor, as "jurisdiction document_class version" lines.
# (macOS ships bash 3.2: no mapfile, and no heredoc inside a process substitution.)
SCOPE_LIST=$(mktemp)
trap 'rm -f "$SCOPE_LIST"' EXIT
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

# 1. force-add artifacts (data/ is gitignored) and commit them.
for line in "${SCOPES[@]}"; do
  read -r jur cls ver <<<"$line"
  cov="data/corpus/coverage/$jur/$cls/$ver.json"
  python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); assert d["complete"] is True, sys.argv[1]' "$cov"
  git add -f "$cov" \
             "data/corpus/inventory/$jur/$cls/$ver.json" \
             "data/corpus/provisions/$jur/$cls/$ver.jsonl" \
             "data/corpus/sources/$jur/$cls/$ver"
done
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
  if [ -f ".axiom/ingest-manifests/$jur/$cls/$ver.json" ]; then
    # Already signed by an earlier run (its manifest may carry reasoning-log attestations
    # this script cannot reproduce); guard-ingested, below or in CI, still verifies it.
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

# 4. track the immutable selector and deep-validate it against the committed artifacts.
cp "$DRAFT" "$TARGET"
uv run axiom-corpus-ingest validate-release --base data/corpus --release "$TARGET" --ignore-r2-missing --max-issues 20
git add "$TARGET"
git commit -q -m "$(printf 'Cut %s\n\nCo-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>' "$NAME")"
echo "selector commit: $(git rev-parse --short HEAD)"
echo "next: open a PR (CI runs guard-ingested and validates the selector), then"
echo "      uv run --extra dev python scripts/publish_corpus.py --release $TARGET --dry-run"
