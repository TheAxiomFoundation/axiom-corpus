# Unemployment insurance benefits, wave 1: federal layer and 19 state statutes

Date: 2026-11-24 (America/New_York). Branch `ingest/ui-benefits-tier1-wave1`, cut from `main` 085e7fe07.

Input: the roadmap's UI scope audit, `TheAxiomFoundation/axiom-roadmap-dashboard`
`tools/encoding-forecast/ui-scope-audit.json` (commit a9a977bc): 13 federal and 510 state documents for the amount of
and the basic eligibility for regular state unemployment benefits. No person reviewed the audit, so every citation was
treated as a lead and checked against the extracted official text.

Nothing was signed, locked, loaded, pushed to R2 or published. Every artifact is unsigned and outside git.

## What the corpus held before this run

Each audit document was matched against every locked `us*` provisions file (686,067 rows) by citation path and by
official address, against the signed ingest manifests, and against the newest rulespec-us pin-line selector
(`us-rulespec-2026-11-24-tier1-source-text`).

| jurisdiction | audit documents | held, signed, in the pin-line selector | held, signed, in no pin-line selector | new |
| --- | ---: | ---: | ---: | ---: |
| us | 13 | 4 | 0 | 9 |
| us-ak | 10 | 0 | 0 | 10 |
| us-al | 11 | 9 | 0 | 2 |
| us-ar | 9 | 0 | 0 | 9 |
| us-az | 11 | 0 | 0 | 11 |
| us-ca | 16 | 0 | 0 | 16 |
| us-co | 11 | 0 | 0 | 11 |
| us-ct | 15 | 0 | 0 | 15 |
| us-dc | 7 | 0 | 0 | 7 |
| us-de | 6 | 0 | 0 | 6 |
| us-fl | 7 | 0 | 0 | 7 |
| us-ga | 7 | 0 | 0 | 7 |
| us-hi | 9 | 0 | 0 | 9 |
| us-ia | 7 | 0 | 0 | 7 |
| us-id | 11 | 0 | 0 | 11 |
| us-il | 13 | 0 | 0 | 13 |
| us-in | 13 | 0 | 0 | 13 |
| us-ks | 7 | 0 | 0 | 7 |
| us-ky | 11 | 0 | 0 | 11 |
| us-la | 9 | 0 | 0 | 9 |
| us-ma | 8 | 0 | 0 | 8 |
| us-md | 10 | 0 | 0 | 10 |
| us-me | 9 | 0 | 0 | 9 |
| us-mi | 9 | 0 | 0 | 9 |
| us-mn | 6 | 0 | 0 | 6 |
| us-mo | 8 | 0 | 0 | 8 |
| us-ms | 10 | 0 | 0 | 10 |
| us-mt | 9 | 0 | 0 | 9 |
| us-nc | 11 | 0 | 0 | 11 |
| us-nd | 10 | 0 | 0 | 10 |
| us-ne | 11 | 0 | 0 | 11 |
| us-nh | 7 | 0 | 0 | 7 |
| us-nj | 12 | 4 | 4 | 4 |
| us-nm | 5 | 0 | 0 | 5 |
| us-nv | 11 | 0 | 0 | 11 |
| us-ny | 13 | 4 | 0 | 9 |
| us-oh | 8 | 0 | 0 | 8 |
| us-ok | 17 | 9 | 0 | 8 |
| us-or | 12 | 0 | 0 | 12 |
| us-pa | 8 | 4 | 0 | 4 |
| us-ri | 15 | 0 | 0 | 15 |
| us-sc | 14 | 0 | 0 | 14 |
| us-sd | 11 | 0 | 0 | 11 |
| us-tn | 9 | 0 | 0 | 9 |
| us-tx | 14 | 0 | 0 | 14 |
| us-ut | 9 | 6 | 0 | 3 |
| us-va | 10 | 0 | 0 | 10 |
| us-vt | 10 | 0 | 0 | 10 |
| us-wa | 12 | 0 | 0 | 12 |
| us-wi | 10 | 0 | 0 | 10 |
| us-wv | 6 | 0 | 0 | 6 |
| us-wy | 6 | 0 | 0 | 6 |
| total | 523 | 40 | 4 | 479 |

The four signed documents in no pin-line selector are N.J.S.A. 43:21-3, 43:21-4, 43:21-5a and 43:21-19 in
`us-nj/statute/2026-09-23-payroll-contributions-us-nj-title-43`. The corpus locks hold statute chapters, not whole state
codes, so the unemployment chapter of 45 states was new.

## Scopes of this run

28 scopes, 9,214 rows, 8,262 with text. Every scope reports coverage `complete: true` with 0 missing, 0 extra and 0
duplicate citation paths. `scripts/validate_citation_paths.py` over the 28 new provisions files: `RESULT: OK`.

| jurisdiction | class | version | rows | rows with text | characters | status |
| --- | --- | --- | ---: | ---: | ---: | --- |
| us-ak | statute | `2026-11-24-ui-benefits-statute-us-ak-title-23` | 551 | 466 | 685,491 | ready to sign |
| us-de | statute | `2026-11-24-ui-benefits-statute-us-de-title-19-chapter-33` | 81 | 70 | 301,635 | ready to sign |
| us-fl | statute | `2026-11-24-ui-benefits-statute-title-xxxi` | 341 | 322 | 1,307,317 | ready to sign |
| us-hi | statute | `2026-11-24-ui-benefits-statute-us-hi-chapter-383` | 137 | 118 | 281,133 | ready to sign |
| us-ia | statute | `2026-11-24-ui-benefits-statute-us-ia-chapter-96` | 55 | 38 | 241,625 | ready to sign |
| us-id | statute | `2026-11-24-ui-benefits-statute-us-id-title-72-chapter-13` | 115 | 113 | 290,955 | ready to sign |
| us-il | statute | `2026-11-24-ui-benefits-statute-us-il-chapter-820-act-405` | 225 | 223 | 558,248 | ready to sign |
| us-md | statute | `2026-11-24-ui-benefits-statute-us-md-article-gle` | 1,075 | 1,059 | 1,305,030 | ready to sign |
| us-me | statute | `2026-11-24-ui-benefits-statute-us-me-title-26-chapter-13` | 66 | 64 | 353,864 | ready to sign |
| us-mi | statute | `2026-11-24-ui-benefits-statute-us-mi-chapter-421` | 161 | 143 | 563,112 | ready to sign |
| us-mn | statute | `2026-11-24-ui-benefits-statute-us-mn-title-268` | 189 | 187 | 275,810 | ready to sign |
| us-ne | statute | `2026-11-24-ui-benefits-statute-us-ne-title-48` | 936 | 670 | 1,072,816 | ready to sign |
| us-or | statute | `2026-11-24-ui-benefits-statute-us-or-chapter-657` | 335 | 301 | 363,671 | ready to sign |
| us-ri | statute | `2026-11-24-ui-benefits-statute-us-ri-chapter-28-42` | 99 | 93 | 124,273 | ready to sign |
| us-ri | statute | `2026-11-24-ui-benefits-statute-us-ri-chapter-28-44` | 67 | 58 | 124,983 | ready to sign |
| us-sc | statute | `2026-11-24-ui-benefits-statute-us-sc-title-41-chapter-27` | 62 | 60 | 100,922 | ready to sign |
| us-sc | statute | `2026-11-24-ui-benefits-statute-us-sc-title-41-chapter-35` | 52 | 50 | 98,586 | ready to sign |
| us-sd | statute | `2026-11-24-ui-benefits-statute-title-61` | 375 | 286 | 197,637 | held (defect 2) |
| us-tx | statute | `2026-11-24-ui-benefits-statute-us-tx-title-LA` | 2,132 | 1,796 | 1,709,679 | held (defect 3) |
| us-wa | statute | `2026-11-24-ui-benefits-statute-us-wa-title-50.04` | 68 | 66 | 69,158 | ready to sign |
| us-wa | statute | `2026-11-24-ui-benefits-statute-us-wa-title-50.20` | 50 | 48 | 73,889 | ready to sign |
| us-wi | statute | `2026-11-24-ui-benefits-statute-chapter-108` | 1,729 | 1,728 | 1,455,776 | ready to sign |
| us | regulation | `2026-11-24-ui-benefits-ecfr-title-20-part-604` | 7 | 6 | 9,451 | ready to sign |
| us | regulation | `2026-11-24-ui-benefits-ecfr-title-20-part-609` | 28 | 24 | 44,120 | ready to sign |
| us | regulation | `2026-11-24-ui-benefits-ecfr-title-20-part-614` | 28 | 24 | 47,669 | ready to sign |
| us | regulation | `2026-11-24-ui-benefits-ecfr-title-20-part-616` | 11 | 10 | 14,765 | ready to sign |
| us | statute | `2026-11-24-ui-benefits-usc-title-42` | 125 | 125 | 102,697 | ready to sign |
| us | statute | `2026-11-24-ui-benefits-usc-title-5` | 114 | 114 | 51,739 | ready to sign |

Federal sources: OLRC release point 119-142 (`xml_usc05@119-142.zip`, `xml_usc42@119-142.zip`, current through Public
Law 119-142 of 2026-11-10), 5 U.S.C. 8501 to 8509, 8521 to 8523 and 8525 (8524 is repealed) and 42 U.S.C. 503; eCFR
title 20 at its latest issue date 2026-11-19, parts 604, 609, 614 and 616 (the appendices of part 614 are not taken).
26 U.S.C. 85, 3304, 3306 and 3402 were held and are in the pin-line selector.

State sources: the existing `extract-state-statutes` adapters, one manifest per state
(`manifests/us-<st>-ui-benefits-statute.yaml`, written by `scripts/build_ui_benefits_manifests.py`). An adapter that
filters at title grain takes the whole labor title (Alaska title 23, Florida title XXXI, Maryland Labor and Employment
Article, Nebraska chapter 48, Texas Labor Code).

## The audit against the official text

Every statute section the audit cites for the 19 states was found in the extracted text under the cited number, with
text, except:

1. **South Dakota, SDCL 61-6-1.** The citation is right: the Legislature serves "61-6-1. Requirements for eligibility
   for benefits during week". The extracted row at `us-sd/statute/61-6-1` is a transfer note ("61-6-1.2, 61-6-1.3.
   Transferred to §§ 61-6-24, 61-6-25") with no body. See defect 2.
2. **US DOL "Significant Provisions" and "Comparison of State UI Laws".** Not taken: wave 6 ruled these federal
   summaries of state law out (`docs/ingest-runs/2026-10-06-w6-benefits-decisions.csv`), and the audit itself marks
   them "reference only". The bundle excludes them with that reason.

The audit says 29 U.S.C. 206 is not needed for unemployment insurance. It stays in the bundle because the reference
model cites it; that is a membership decision for a person.

## Defects found (none worked around)

1. **Missouri, `missouri-revised-statutes`, chapter 288.** The extraction stops with "chapter 288 full text:
   full-chapter source omits section 288.036". No Missouri scope was kept. RSMo 288.060 also has two enactments (the
   2015 one is marked unconstitutional), which the adapter must keep as variants.
2. **South Dakota, `south-dakota-codified-laws`, title 61.** A combined transfer note takes the path of the live
   section 61-6-1 (and of 61-6-15), so the section's text is lost while coverage reads complete. The scope is held.
3. **Texas, `texas-tcas`.** The run id carries the code in upper case (`...-us-tx-title-LA`), which the lock rule
   (`^[a-z0-9][a-z0-9._-]*$`) rejects. Wave 6 met the same with `title-HR` and consolidated to a lower-case successor
   (`scripts/consolidate_release_scopes.py`). The scope is held until then.
4. **North Dakota, `north-dakota-code`.** The adapter accepts only chapter 57-38 (income tax). Title 52 was not run.
5. **Illinois, ilga.gov.** The server sends an incomplete TLS chain. The run used
   `REQUESTS_CA_BUNDLE=<certifi + data/certs/*.pem>` with full verification, as earlier runs did.
6. **Hawaii and Iowa.** One container row of each new scope (a volume or title root) has the path of a row in a scope
   the pin-line selector already selects. Check `validate-release` for a duplicate-path finding when the selector is cut.

## Not done in wave 1

- Regulations and agency documents of the wave 1 states (the audit lists 30 regulations and about 60 agency pages for
  them). They are in the bundle by address and count as not in the corpus.
- Kentucky (no statute adapter), California (leginfo answered HTTP 403 to the corpus client in October), the District
  of Columbia (the `dc-code` adapter needs the Council's law XML checkout), North Dakota, Missouri.
- The 21 states with audit confidence `medium` and the two with `low`. Georgia and Tennessee show a CAPTCHA on their
  official code sites and mass.gov blocked automated requests in the audit; nothing was tried against them.

## Human steps

1. Decide the membership rule (pull request for the bundle change).
2. Sign and lock the 26 ready scopes. This needs `AXIOM_CORPUS_INGEST_PRIVATE_KEY` and R2 write access:

   ```bash
   tail -n +2 docs/ingest-runs/2026-11-24-ui-benefits-wave1-unsigned-scopes.tsv |
   while IFS=$'\t' read -r j c v note; do
     uv run axiom-corpus-ingest sign-ingest-manifest --jurisdiction "$j" --document-class "$c" --version "$v" \
       --command "rebuild: see $note" --lock --push < /dev/null || break
   done
   git add .axiom/ingest-manifests .axiom/corpus-locks
   ```

   The artifacts are in this worktree's `data/corpus` and, as a copy, under
   `~/.axiom/workspace/ui-benefits-2026-11-24/data/corpus`. Run the loop from a checkout whose `data/corpus` holds them.
3. Run `uv run axiom-corpus-ingest content-check` on the 26 scopes (it reads locked scopes only) and record or fix
   its findings.
4. Cut the selector: copy `docs/ingest-runs/2026-11-24-us-rulespec-ui-benefits-wave1.selector.json` to
   `manifests/releases/us-rulespec-2026-11-24-ui-benefits-wave1.json`, remove the "DRAFT" sentence, add a reproducer and
   a test as for `us-rulespec-2026-11-24-tier1-source-text`, then run `validate-release` and the publish dry run. It is
   the base selector's 431 scopes plus 27: the 26 ready scopes and the signed New Jersey title 43 scope (458 scopes).
   Publish only; do not activate.
5. Re-pin rulespec-us (`.axiom/workflow-toolchain.toml`): the release name, the published `content_sha256`, and
   `axiom_corpus_ref` at or after the `main` commit that holds the selector.

## Rebuild

```bash
B=data/corpus
# U.S. Code, release point 119-142 (download each zip from uscode.house.gov first)
V=2026-11-24-ui-benefits-usc
for spec in "5 05 8501 8502 8503 8504 8505 8506 8507 8508 8509 8521 8522 8523 8525" "42 42 503"; do
  set -- $spec; T=$1; TT=$2; shift 2; A=(); for x in "$@"; do A+=(--section $x); done
  uv run axiom-corpus-ingest extract-usc --base $B --version $V --title $T --source-zip xml_usc$TT@119-142.zip \
    --source-as-of 2026-11-24 --expression-date 2026-11-10 \
    --source-url https://uscode.house.gov/download/releasepoints/us/pl/119/142/xml_usc$TT@119-142.zip "${A[@]}"
  uv run python scripts/self_contain_usc_scope.py --base $B --version $V-title-$T
done
for P in 604 609 614 616; do
  uv run axiom-corpus-ingest extract-ecfr --base $B --version 2026-11-24-ui-benefits-ecfr --as-of 2026-11-19 \
    --only-title 20 --only-part $P
done
uv run python scripts/build_ui_benefits_manifests.py
export REQUESTS_CA_BUNDLE=<certifi + data/certs/*.pem>   # Illinois only
for st in ak de fl hi ia id il md me mi mn ne or ri sc sd tx wa wi; do
  uv run axiom-corpus-ingest extract-state-statutes --base $B --manifest manifests/us-$st-ui-benefits-statute.yaml
done
```

Impact analysis: the GitNexus tools were not available in this session; no library code changed in this run.
