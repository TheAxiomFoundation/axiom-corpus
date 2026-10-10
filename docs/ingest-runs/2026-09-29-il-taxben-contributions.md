# Israel tax-benefit pilot, contributions increment: the National Health Insurance Law

Date: 2026-09-29. Branch `ingest/il-health-insurance-law`. Scope
`il/statute/2026-09-29-il-taxben-contributions`, release selector
`manifests/releases/il-rulespec-2026-09-29.json`. Manifest:
`manifests/il-taxben-contributions-openlaw.yaml`.

Purpose: rulespec-il encodes an employee's two payroll deductions together,
National Insurance (National Insurance Law §§334, 337, 342, 348, לוח י׳ and
לוח י״א) and health insurance (National Health Insurance Law §14). The pilot
scope `il/statute/2026-09-06-il-taxben-pilot` does not carry the health law.
This scope adds it and repeats the pilot's three instruments unchanged.

No publication, registration or activation step was run from this branch. See
"What merging does".

## Sources

The scope has five source files. Four are the pilot's captures; their sha256
and size equal the entries in
`.axiom/corpus-locks/il/statute/2026-09-06-il-taxben-pilot.json`. One is new.

| File under `sources/il/statute/2026-09-29-il-taxben-contributions/openlaw/` | Bytes | sha256 | Status |
|---|---|---|---|
| `ito-wikisource.html` | 2,457,177 | `87535c2b8cd8aa50b27d32301dc2ddd768390ef64e9fb4f391c3e65fe99dc228` | pilot capture |
| `ito-wikisource-tail-235-247.html` | 102,308 | `6cc14dd6bdd6caf14d1f0d63a6f9f74bc83706aefae46b000933d82d84abb9e8` | pilot capture |
| `nii-law-wikisource.html` | 1,941,686 | `7dbaaa757912c71b361381640d2578bf2c6ab52f2002817b85d677c2267f0715` | pilot capture |
| `economic-efficiency-law-2026-wikisource.html` | 82,593 | `c4632b9f2d50e63cdd4bd0ab517ec5aa1a0f1488448e6151d0eb6a7aedbb6c4c` | pilot capture |
| `health-insurance-law-wikisource.html` | 829,188 | `61c3879b1f1e3cd048bc28b1e62ff9beed79f16b7158ec49d663a39f00f93570` | new |

The bytes are content-addressed lock entries in
`.axiom/corpus-locks/il/statute/2026-09-29-il-taxben-contributions.json`;
`axiom-corpus-ingest corpus fetch` places them.

### Paths under `ops/il-lane/sources/`

Both Israel manifests cite files under `ops/il-lane/sources/`. That folder is
the Israel lane's working folder on the ingesting machine. It is not part of
this repository. The captured pages it holds are the lock entries above, byte
for byte. Its provenance records for the health law are reproduced below, so
this note is the accessible copy of what
`ops/il-lane/sources/health-insurance-law-wikisource.html.provenance.json`
says. The pilot's records are described in
`manifests/il-taxben-pilot-openlaw.yaml`.

The manifest's `expression_date_basis` string names that path. It is copied
into `metadata.expression_date_basis` on every health-law row, so changing it
would change the signed artifacts. It stays as written.

## The health law capture

The capture's provenance record, verbatim:

```json
{
  "url": "https://he.wikisource.org/wiki/%D7%97%D7%95%D7%A7_%D7%91%D7%99%D7%98%D7%95%D7%97_%D7%91%D7%A8%D7%99%D7%90%D7%95%D7%AA_%D7%9E%D7%9E%D7%9C%D7%9B%D7%AA%D7%99",
  "retrieved_at": "2026-09-06T13:07:55Z",
  "sha256": "61c3879b1f1e3cd048bc28b1e62ff9beed79f16b7158ec49d663a39f00f93570",
  "tier": "consolidation-wikisource",
  "publisher": "he.wikisource.org (ספר החוקים הפתוח)",
  "file": "health-insurance-law-wikisource.html",
  "instrument": "חוק ביטוח בריאות ממלכתי, התשנ\"ד-1994",
  "israel_law_id": "2000111",
  "source_as_of": "2026-05-24",
  "source_as_of_basis": "Knesset OData KNS_IsraelLaw.LatestPublicationDate for IsraelLawID 2000111, retrieved 2026-09-06 (query: substringof('ביטוח בריאות ממלכתי',Name))",
  "tier_note": "Same tier as the National Insurance Law capture. The Knesset National Legislation Database's 'לחוק המלא' link has NOT been verified for this act, so it claims the lower tier.",
  "note": "Captured by the il-rules lane session 2 to make the health half of the employee contribution encodable. Statutory text carries no copyright (Israeli Copyright Act 2007 §6); the Wikisource editorial layer is CC BY-SA and is stripped from provision bodies. §14(ב)(1) states 5.17% and §14(ו1) states 3.23% on the part of income not exceeding the reduced amount fixed under NII §341."
}
```

The record's `source_as_of` field holds the Knesset publication date. The
manifest names the same date `expression_date` (2026-05-24) and sets
`source_as_of` to the capture date (2026-09-06).

### Page revision

The captured page prints `"wgRevisionId":3073760`. The MediaWiki API
(`action=query&prop=revisions` for the page `חוק ביטוח בריאות ממלכתי`) lists
that revision as OpenLawBot's of 2026-08-14.

| Checked | Latest revision | Finding |
|---|---|---|
| 2026-09-29 | 3081417 (2026-09-09, OpenLawBot, "[3081404] כניסה לתוקף") | One revision later than the capture. Its only change deletes eight "(החל מיום 17.8.2026):" commencement notes in תוספת שנייה, at part 1 item 28 and part 2 item 3. §14 is unchanged. |
| 2026-10-04 | 3081417 | No revision since. |

Rows `schedule-2/sign-1/item-28` and `schedule-2/sign-2/item-3` therefore
still print that qualifier.

### Expression date

The 2026-09-06 session queried the Knesset OData service by name and recorded
the value in the provenance record. It did not save the response. The same
record was fetched again by ID on 2026-10-04T23:09:18Z:

`https://knesset.gov.il/Odata/ParliamentInfo.svc/KNS_IsraelLaw()?$filter=IsraelLawID eq 2000111&$format=json`

The response (694 bytes, sha256
`44524af631be17a8d38261785a72504a99a182ac16de64194a6b34fa10dcd82c`) gives, for
`IsraelLawID` 2000111, `LatestPublicationDate` `2026-05-24T17:04:00`,
`PublicationDate` `1994-06-26T00:00:00` and `LawValidityDesc` `תקף`. That
matches the manifest's `expression_date`.

## Extraction

The signed ingest manifest records the command:

```
uv run --extra dev axiom-corpus-ingest extract-il-openlaw --base data/corpus --version 2026-09-29-il-taxben-contributions --manifest manifests/il-taxben-contributions-openlaw.yaml --source-dir data/corpus/sources/il/statute/2026-09-29-il-taxben-contributions/openlaw
```

It wrote 1,633 provision rows against 1,633 inventory entries, with none
missing and none extra.

| Instrument | Rows |
|---|---|
| `income-tax-ordinance` | 686 |
| `national-insurance-law-1995` | 728 |
| `economic-efficiency-law-2026` | 21 |
| `national-health-insurance-law-1994` | 198 |

The health law's 198 rows are 1 document, 15 chapters, 103 sections,
8 schedules, 3 signs and 68 schedule items, the counts the manifest declares.
`tests/test_israel_openlaw.py` checks that every pilot row is unchanged apart
from its version-bound ids and paths, and that §14 carries both rates.

The adapter changed in two places for this act. Schedule items hang under their
part where a schedule's parts restart item numbering. §1 is read where it
follows the table of contents with no chapter heading before it.

## Signing

`.axiom/ingest-manifests/il/statute/2026-09-29-il-taxben-contributions.json`
was generated at 2026-09-29T14:33:57Z, at commit `6897adb9b`, with a clean
tree. It attests the eight artifact files by sha256 and is signed with key
`axiom-corpus-ingest-v1` (ed25519). Two earlier signatures in this branch's
history were replaced after review rounds changed the adapter.

## Migration to lock files

On 2026-10-03 the branch was merged with `main` after the corpus bytes moved
out of git (#774), and `axiom-corpus-ingest corpus migrate` moved its eight
corpus files into the lock file (commits `69c8d3c19` and `8a9f84b91`). Each
lock entry has the sha256 and size the signed manifest attests. The migration
checked that R2 `objects/sha256/` holds every object the lock names before it
pushed the branch.

## What merging does

`.github/workflows/publish.yml` runs on a push to `main` that changes
`manifests/releases/*.json`. This branch adds
`manifests/releases/il-rulespec-2026-09-29.json`, so merging it runs that
workflow. Its step "Validate, sign, and register the named release (activation
is separate)" registers `il-rulespec-2026-09-29`, which holds this one scope.
The workflow does not activate the release: `scripts/publish_corpus.py`
defaults to `activate=False`, and serving changes only through
`scripts/activate_release.py`.
