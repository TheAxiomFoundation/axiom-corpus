# Unemployment insurance benefits, wave 3: thirteen states with medium audit confidence

Date: 2026-11-24 (America/New_York). Branch `ingest/ui-benefits-tier1-wave3`, stacked on
`ingest/ui-benefits-tier1-wave1b`. Earlier notes: `2026-11-24-ui-benefits-wave1.md`, `2026-11-24-ui-benefits-wave1b.md`.

Input: the roadmap's UI scope audit (`axiom-roadmap-dashboard` a9a977bc; no person reviewed it). Each citation was
checked against the fetched official text. Nothing was signed, locked, loaded, pushed to R2 or published. No adapter
was changed. No CAPTCHA or challenge page was worked around.

States: Arizona, Colorado, Connecticut, Indiana, Kansas, Louisiana, Massachusetts, Montana, New Hampshire, New Mexico,
Nevada, Ohio, Vermont, and West Virginia (audit confidence low; it has an adapter, so it was tried).

## Scopes

28 scopes, 6,665 rows, 5,862 with text. Every scope reports coverage `complete: true`.
`scripts/validate_citation_paths.py` over the new files: `RESULT: OK`. No path of these scopes is in a scope of the
pin-line selector. All are ready to sign.

| jurisdiction | class | version | rows | rows with text | characters |
| --- | --- | --- | ---: | ---: | ---: |
| us-az | statute | `2026-11-24-ui-benefits-statute-us-az-title-23` | 589 | 530 | 947,802 |
| us-co | guidance | `2026-11-24-ui-benefits-guidance-co` | 17 | 15 | 7,542 |
| us-ct | guidance | `2026-11-24-ui-benefits-guidance-ct` | 30 | 28 | 42,408 |
| us-ct | statute | `2026-11-24-ui-benefits-statute-title-31-chapter-567` | 113 | 111 | 330,086 |
| us-in | guidance | `2026-11-24-ui-benefits-guidance-in` | 33 | 32 | 82,713 |
| us-in | statute | `2026-11-24-ui-benefits-statute-us-in-title-22` | 2,184 | 1,888 | 1,918,875 |
| us-ks | guidance | `2026-11-24-ui-benefits-guidance-ks` | 3 | 2 | 3,364 |
| us-ks | statute | `2026-11-24-ui-benefits-statute-us-ks-chapter-44-article-7` | 85 | 57 | 383,756 |
| us-la | guidance | `2026-11-24-ui-benefits-guidance-la` | 9 | 8 | 16,532 |
| us-la | statute | `2026-11-24-ui-benefits-statute-us-la-title-23` | 873 | 721 | 1,305,238 |
| us-ma | guidance | `2026-11-24-ui-benefits-guidance-ma` | 17 | 15 | 5,753 |
| us-ma | statute | `2026-11-24-ui-benefits-statute-us-ma-chapter-151a` | 177 | 118 | 380,160 |
| us-mt | guidance | `2026-11-24-ui-benefits-guidance-mt` | 37 | 35 | 72,220 |
| us-mt | statute | `2026-11-24-ui-benefits-statute-us-mt-title-39` | 1,185 | 1,053 | 919,395 |
| us-nh | regulation | `2026-11-24-ui-benefits-regulation-nh` | 4 | 3 | 369,364 |
| us-nh | statute | `2026-11-24-ui-benefits-statute-us-nh-title-xxiii-chapter-282-a` | 208 | 201 | 283,123 |
| us-nm | guidance | `2026-11-24-ui-benefits-guidance-nm` | 31 | 30 | 65,581 |
| us-nm | regulation | `2026-11-24-ui-benefits-regulation-nm` | 2 | 1 | 92,100 |
| us-nm | statute | `2026-11-24-ui-benefits-statute` | 68 | 60 | 233,586 |
| us-nv | guidance | `2026-11-24-ui-benefits-guidance-nv` | 3 | 2 | 1,742 |
| us-nv | regulation | `2026-11-24-ui-benefits-regulation-nv` | 2 | 1 | 121,747 |
| us-nv | statute | `2026-11-24-ui-benefits-statute-us-nv-chapter-612` | 215 | 213 | 264,144 |
| us-oh | guidance | `2026-11-24-ui-benefits-guidance-oh` | 8 | 6 | 12,054 |
| us-oh | regulation | `2026-11-24-ui-benefits-regulation-oh` | 2 | 1 | 959 |
| us-oh | statute | `2026-11-24-ui-benefits-statute-us-oh-title-41` | 697 | 669 | 1,796,646 |
| us-vt | guidance | `2026-11-24-ui-benefits-guidance-vt` | 32 | 30 | 56,552 |
| us-vt | statute | `2026-11-24-ui-benefits-statute-vt` | 14 | 7 | 81,721 |
| us-wv | guidance | `2026-11-24-ui-benefits-guidance-wv` | 27 | 25 | 45,057 |

Statutes come from the existing `extract-state-statutes` adapters (`scripts/build_ui_benefits_manifests.py`); an
adapter that filters at title grain takes the whole title (Arizona 23, Indiana 22, Louisiana 23, Montana 39, Ohio 41).
Regulations and agency documents come from `extract-official-documents`
(`scripts/build_ui_benefits_document_manifests.py`).

## The audit against the official text

Every statute section the audit cites for Arizona, Connecticut, Indiana, Kansas, Louisiana, Massachusetts, Montana,
New Hampshire, New Mexico, Nevada, Ohio and Vermont is in the extracted text under the cited number, with text. The
schedule of RSA 282-A:25 is complete (annual earnings 2,800 to 41,500; the audit read only its first and last rows).

- **Kansas, KDOL "Unemployment Insurance Benefits Information Guide"**: the cited address
  (`showpublisheddocument/308/...`) serves K-WC 107, a table of maximum workers compensation benefits. Not kept.
- **Vermont**: the `vermont-statutes` adapter accepts only title 32, so 21 V.S.A. 1301, 1338, 1338a, 1339, 1340, 1343
  and 1344 are taken as official documents from the Legislature's section pages (content selector
  `ul.statutes-detail`, which leaves the site notice out).

## Not taken

| item | reason |
| --- | --- |
| Colorado statutes (C.R.S. 8-70, 8-73) | adapter defect: the OLLS file is `crs2025-title-08.htm`, the adapter asks for `title-8` (HTTP 404), and with `title: "08"` it matches no section. Fix: zero-pad the title in the file name only |
| Colorado 7 CCR 1101-2 | `extract-colorado-ccr --only-series 1101-2`: "no Colorado CCR documents discovered" |
| West Virginia statutes (ch. 21A) | code.wvlegislature.gov did not answer (connection timeout, 15 s, 2026-11-24); the audit met the same |
| Arizona DES handbook and eligibility page | des.az.gov answered HTTP 403 (challenge page); nothing tried against it |
| Arizona A.A.C. title 6 chapter 3 | apps.azsos.gov: Cloudflare challenge in October and in the audit; not tried again |
| Connecticut RCSA 31-230, 31-235, 31-236 | the eRegulations portal page has no text without scripts |
| Indiana 646 IAC 5 | the Administrative Code viewer has no text without scripts |
| Kansas Register notice | the site banner in the body; needs a content selector |
| Louisiana LAC title 40 | one file, all of title 40 (3.5 million characters, workers compensation included) in three rows; the unemployment part needs a splitter |
| Massachusetts DUA form P2594 | the PDF text layer reads garbled (interleaved letters) |
| Vermont Employment Security Board rules | image-only PDF, no text layer; needs OCR |
| New York Labor Law 520, 522, 523, 591, 600 | nysenate.gov answers HTTP 403 (Cloudflare) to the plain client; earlier runs used browser impersonation there, which this run does not do |

Each held document is in the generator's `HELD` list with its reason.

## Human steps

1. Sign and lock, after the scopes of waves 1 and 1b, with `AXIOM_CORPUS_INGEST_PRIVATE_KEY` and R2 write access:

   ```bash
   tail -n +2 docs/ingest-runs/2026-11-24-ui-benefits-wave3-unsigned-scopes.tsv |
   while IFS=$'\t' read -r j c v note; do
     uv run axiom-corpus-ingest sign-ingest-manifest --jurisdiction "$j" --document-class "$c" --version "$v" \
       --command "rebuild: see $note" --lock --push < /dev/null || break
   done
   git add .axiom/ingest-manifests .axiom/corpus-locks
   ```

2. Run `content-check` on the locked scopes.
3. Add the scopes to the draft successor selector before it is cut. Publish only; do not activate.

The artifacts are in the worktree's `data/corpus` and in a copy under `~/.axiom/workspace/ui-benefits-2026-11-24`.

## Rebuild

```bash
B=data/corpus; export REQUESTS_CA_BUNDLE=<certifi + data/certs/*.pem>
uv run python scripts/build_ui_benefits_manifests.py && uv run python scripts/build_ui_benefits_document_manifests.py
for st in az ct in ks la ma mt nh nm nv oh; do
  uv run axiom-corpus-ingest extract-state-statutes --base $B --manifest manifests/us-$st-ui-benefits-statute.yaml
done
for m in manifests/us-{co,ct,in,ks,la,ma,mt,nm,nv,oh,vt,wv}-ui-benefits-guidance.yaml \
         manifests/us-{nh,nm,nv,oh}-ui-benefits-regulation.yaml manifests/us-vt-ui-benefits-statute.yaml; do
  uv run axiom-corpus-ingest extract-official-documents --base $B --manifest $m \
    --version "$(grep -m1 '^version:' $m | awk '{print $2}')"
done
```

Impact analysis: the GitNexus tools were not available in this session; no library code changed in this run.
