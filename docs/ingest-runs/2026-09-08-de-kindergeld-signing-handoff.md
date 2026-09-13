# Kindergeld capture signing record

The signing blocker below was resolved on 8 September 2026: the dedicated
local Axiom ingest key was located, matched against the repository public
trust key, and used to sign all twelve scopes. No key was transmitted.
The instructions below record the signing procedure. The data commit is
`e6039721` on `de-kindergeld-frontier-2026-09-08`. Its named-release dry-run
passed with 107 artifacts, 4,483 rows and fourteen scopes (including the two
preserved July scopes). The capture audit's 935 new row hashes were also
independently rechecked against the committed JSONL bytes.

A key-holder must run the following in the reviewed branch checkout, in the
authorized environment that already supplies `AXIOM_CORPUS_INGEST_PRIVATE_KEY`.
Do not substitute the release signing key, transmit a private key through a
PR/chat, or change the authentication guard. Review the outstanding capture
and historical-applicability limitations in the companion frontier report
before signing; a signature does not declare the release complete for closure.

```bash
uv run --extra dev python - <<'PY'
import json
import subprocess
from pathlib import Path

if subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no']):
    raise SystemExit('Sign only from a clean reviewed commit')
audit = json.loads(Path('docs/ingest-runs/2026-09-08-de-kindergeld-capture-audit.json').read_text())
for item in audit['provision_files']:
    path = Path(item['path'])
    subprocess.run([
        'axiom-corpus-ingest', 'sign-ingest-manifest',
        '--jurisdiction', 'de', '--document-class', path.parent.name,
        '--version', path.stem,
        '--command', 'DE Kindergeld primary-source capture tranche (PR #647); existing extract-de-gii and extract-official-documents; exact inputs and source receipts in manifests/de-kindergeld-*.yaml and docs/ingest-runs/2026-09-08-de-kindergeld-capture-audit.json',
        '--reasoning-log', 'docs/ingest-runs/2026-09-08-de-kindergeld-frontier.md',
    ], check=True)
PY
```

Review and commit only the resulting `.axiom/ingest-manifests/de/` entries.
Push to the same branch and require green CI before promotion. Preserve the
attested data commit using a merge commit. Publication remains a separate
main-only step through the existing named-release workflow; retain its signed
release object, full commit and `content_sha256` before repinning consumers.
The selector SHA is not the release identity.
