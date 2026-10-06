# PR #552 repair round 2 — defensive correctness and completeness audit

## Result

- Status: repaired content complete and committed locally; main-lane
  re-signing is intentionally still required.
- Branch: `ingest/ca-bbce-authority`
- Final HEAD: `256634f618f99cbf431b1e37b933aff5682aa50d`
- Repaired content commit:
  `c06ba01fc6e0a547bcafd6824249deae99e18a0b`
- Round-2 starting HEAD:
  `058cf9ff662161de6ea008e7d0098cb38e9571d8`
- Release selector: `us-ca-2026-07-28-calfresh-bbce-authority`
- Publication: none. No push, GitHub write, R2 upload, Supabase load,
  release activation, production-row deletion, or signing was performed.

The repaired corpus retains eight exact official source snapshots: six CDSS
All County Letter PDFs and current WIC §§18901.3 and 18901.5 HTML. It emits:

- guidance version
  `2026-07-28-ca-cdss-calfresh-bbce-authority`, with 47/47 rows; and
- statute version
  `2026-07-28-ca-cdss-calfresh-bbce-authority-us-ca-sections-wic-18901.3-wic-18901.5`,
  with 2/2 rows.

The total is 49 normalized rows. The prior 45 rows are semantically
conserved, and the two new sources add four rows: ACL 14-63 contributes one
document root plus two page rows; WIC §18901.3 contributes one section row.

## Exact retained sources and row counts

| Input | Official authority | Bytes | PDF pages | Rows | SHA-256 |
| --- | --- | ---: | ---: | ---: | --- |
| `WIC-18901.3.html` | Cal. WIC §18901.3 | 163,929 | — | 1 | `793afbd116aa7664fde4137f55d34ad659e80c10f37849d59bb4ea07b43fffdc` |
| `WIC-18901.5.html` | Cal. WIC §18901.5 | 164,166 | — | 1 | `97cae778729e0dd5d3c15797934690467876a14057e7d856d1500326e72d004e` |
| `14-56.pdf` | CDSS ACL 14-56 | 278,260 | 7 | 8 | `8677c1d3e5c2ec9ecef23206b24061999817a46fa469ccb68a000b8f2f570d5e` |
| `14-56e.pdf` | CDSS ACL 14-56E | 189,729 | 4 | 5 | `67e33a2613009abaef3759ebc2a583417fb852120f009848e3b1a1e3c3c11cbd` |
| `14-63.pdf` | CDSS ACL 14-63 | 120,344 | 2 | 3 | `4392ab0dedfcfb6f247bb7d3d913e90ff2a97a673ea01efac02ec9f3d6ee2841` |
| `15-42.pdf` | CDSS ACL 15-42 | 249,307 | 13 | 14 | `6aab92e4e2a2c9e0f234eba2b1c0eeb68d4d9d5dbc7ba752465a2358d9f2db33` |
| `14-100.pdf` | CDSS ACL 14-100 | 209,290 | 12 | 13 | `c981081163b361eea20aeeccec7934509dc5bf23d8d66c8035895586db60131e` |
| `13-32.pdf` | CDSS ACL 13-32 | 204,909 | 3 | 4 | `1a0bbfc2d6d69fd378aff3f1285d03d20b8b6abf2ff64c749b9897fd1cc55506` |
| **Total** | **8 sources** | **1,579,934** | **41** | **49** |  |

Each guidance PDF emits one root and one row per physical page. All 41 pages
have nonempty embedded text. No source snapshot was rewritten.

## Deterministic reproduction

The literal reproduction command remains:

```bash
uv run --extra dev python scripts/repro/us_ca_calfresh_bbce_authority.py --base data/corpus
```

The script verifies all eight source hashes and sizes, all six PDF page
counts, exact paths and row counts, complete coverage, official URLs, the
closed MCE-exclusion map, and retained authority excerpts before installing
the staged output.

PyMuPDF 1.28.0 exposed two unstable page rows in the round-1 artifacts:

- ACL 14-56 page 1 gained one accessibility-description string.
- ACL 13-32 page 1 gained two accessibility-description strings.

The other four PDFs, including ACL 14-63, were stable. `TEXT_IGNORE_ACTUALTEXT`
was rejected because it changed visible source text. A global PyMuPDF pin was
also unnecessary. The repair adds an opt-in, manifest-driven replacement
facility covering plain, segmented, styled, windowed, and OCR extraction;
only these three known accessibility strings are removed for the two affected
sources.

Actual full-scope dry runs under PyMuPDF 1.26.7 and 1.28.0 produced identical
hashes for all 14 generated artifacts:

| Generated artifact | SHA-256 under both versions |
| --- | --- |
| Guidance inventory | `5defe07565a11a8ac00874672bd85fe75406ace59a6c670ba7498d19e3e83c14` |
| Guidance provisions | `41f7997a9704cfa05b22a4e6873e2a6721e2e1d3f6822ac7d41ef72f4769675d` |
| Guidance coverage | `c0edbfcbf16dd12954dd2ea79b71a4cdd25cb5a639be0a95c810b034d74ab386` |
| Statute inventory | `74ade1657a6711d8d1d905ebcc77b714fda11f8dc3a224b701f877b6bbb3bd06` |
| Statute provisions | `b4ab85f9d45b56003fb6433d2799c5b4c33b473886b58519c54bd52380d28060` |
| Statute coverage | `a8950fdd0fa8752bef6ad381733e557785e4e41d93d3d62a561ea96633459b81` |

The final focused byte test regenerated all 14 files and compared each with
the committed artifact:

- PyMuPDF 1.26.7: 1 passed.
- PyMuPDF 1.28.0: 1 passed.

## Updated RuleSpec #1098 parameter-to-authority table

| Parameter or boundary | Current retained authority | Correct treatment |
| --- | --- | --- |
| California categorical-eligibility mandate | `us-ca/statute/wic/18901.5` | WIC §18901.5 establishes California's categorical-eligibility program, subject to federal authorization and other federal SNAP requirements. |
| Inclusive 200% FPL screen | `us-ca/guidance/cdss/acl-2015-15-42/page-2`; corroborated by ACL 14-56E page 2 | Use gross income at or below 200% FPL; the endpoint is included. |
| PUB 275 categorical trigger | ACL 15-42 page 2; qualification at ACL 14-56 page 3 | Issuance of or online access to PUB 275 participates in the trigger, but brochure access alone does not confer MCE; the gross screen and other eligibility conditions still apply. |
| Resource test waived | `us-ca/guidance/cdss/acl-2014-14-56/page-3` | Once the MCE conditions are met, resources are excluded from the eligibility determination. |
| Ordinary net-income eligibility ceiling waived | `us-ca/guidance/cdss/acl-2015-15-42/page-4` | Net income above the ordinary ceiling does not itself disqualify an MCE household; net income still determines the allotment. |
| Current MCE household exclusions | Current retained 7 CFR 273.2(j)(2)(vii) row `us/regulation/7/273/2`, with the WIC §18901.3 overlay described below | Use the exhaustive seven-gate map below. ACL 15-42 supplies two examples only and is not controlling for the omitted gates. |
| Former conviction-alone drug-felony exclusion | Current WIC §18901.3(a), `us-ca/statute/wic/18901.3`; ACL 14-100 page 2 is implementation context | California opted out. A qualifying drug-felony conviction alone is not a current California member-ineligibility gate. |
| Elderly/disabled neighboring route | `us-ca/guidance/cdss/acl-2013-13-32/page-1` | E/D households are not subject to a gross test for ordinary eligibility; the 200% line determines MCE conferment, not ordinary eligibility. |
| Zero-benefit neighboring rule | **Primary:** ACL 14-63 pages 1–2; **context:** ACL 14-56 page 6 | Outside the initial month, one- or two-person CE households receive at least the applicable minimum. For three-or-more-person CE/MCE households, California denies a zero-result application, discontinues a zero-result ongoing case, and denies a zero-result recertification. |

Historical dollar amounts in the letters are not asserted as current annual
figures.

## Exhaustive current MCE-exclusion gate map

Every federal gate maps to this exact retained row:

- file:
  `data/corpus/provisions/us/regulation/2026-07-15-title-7-part-273.jsonl`
- version: `2026-07-15-title-7-part-273`
- `source_as_of`: `2026-07-09`
- citation path: `us/regulation/7/273/2`

The referenced member rules in §273.11(m), (n), and (s) are retained in the
same file at `us/regulation/7/273/11`.

| Gate | 273.2(j)(2)(vii) clause and exact federal condition | State overlay | Current California result |
| --- | --- | --- | --- |
| Intentional Program Violation | (A): a member is disqualified for an IPV under §273.16. Federal row: `us/regulation/7/273/2`. | None. ACL 15-42 page 3 is non-exhaustive context. | Federal household gate controls. |
| Monthly-reporting disqualification | (A): a member is disqualified for failure to comply with monthly reporting under §273.21. Federal row: `us/regulation/7/273/2`. | None; no retained ACL covers this gate. | Federal household gate controls when the referenced disqualification applies. |
| Entire-household workfare disqualification | (B): the entire household is disqualified because one or more members failed workfare under §273.22. Federal row: `us/regulation/7/273/2`. | None; no retained ACL covers this gate. | Federal household gate controls; an individual issue alone is not enough without the household disqualification. |
| Head-of-household work disqualification | (C): the head is disqualified for failure to comply with §273.7 work requirements. Federal row: `us/regulation/7/273/2`. | None. ACL 15-42 page 3 is non-exhaustive context. | Federal household gate controls. |
| Drug-felony member ineligibility | (D): a member is ineligible under §273.11(m) by virtue of a drug-related felony conviction. Federal row: `us/regulation/7/273/2`; support row: `us/regulation/7/273/11`. | WIC §18901.3(a), retained at `us-ca/statute/wic/18901.3`, is California's legislative opt-out. | Conviction alone does not make the member ineligible in California, so this federal gate is not triggered on conviction alone. ACL 14-100 page 2 is context. |
| Fleeing felon or probation/parole violator | (D): a member is ineligible under §273.11(n). Federal row: `us/regulation/7/273/2`; support row: `us/regulation/7/273/11`. | WIC §18901.3(b) confirms probation/parole compliance and fleeing-felon treatment for the subdivision-(a) drug-felony cohort only. | The federal gate controls universally. WIC §18901.3(b) is not a replacement definition for everyone. ACL 14-100 pages 4–5 are context. |
| Serious crime plus sentence noncompliance | (D): a member has a specified serious-crime conviction **and** is not complying with the sentence under §273.11(s). Federal row: `us/regulation/7/273/2`; support row: `us/regulation/7/273/11`. | None; no retained ACL modifies this gate. | Both elements are required, and the federal household gate controls. |

The exact `(j)(2)(vii)` slice hashes to
`6f0365e2f9ead0833adcef7a3d5a9bd2859db43517811864a0715ff37b2c42ab`.
The map asserts the closed clause cardinality A=2, B=1, C=1, D=3.

Paragraph `(j)(2)(ix)` remains a separate member-exclusion category, not seven
additional household bars. Its five retained exclusions are ineligible
noncitizens, ineligible students, cash-out-State SSI recipients, persons
institutionalized in nonexempt facilities, and persons ineligible for §273.7
work noncompliance. The exact slice hashes to
`641740f072ea889906798769de510a6013d97d6b5c96293b34c9fe100cd44d25`.

## Prior-row conservation

All 45 round-1 rows remain unique and preserve the stable semantic projection
over citation path, body, heading, source identity and URL, source format and
dates, and metadata. The canonical sorted projection hashes to:

`6a79caf1945521a9d13aaf58248cd453a1d938b545d309d6b3f4b570fed68edd`

Fields that must change with the conventional two-section statute version
rename (`id`, `version`, `source_path`, and normalized parent fields) are
intentionally outside that conservation projection.

## Validation record

| Gate | Result |
| --- | --- |
| Source bytes | Pass: all eight retained files match pinned sizes and hashes. |
| Cross-version replay | Pass: all 14 hashes identical under actual PyMuPDF 1.26.7 and 1.28.0; exact byte test passes under both. |
| PDF replacement unit tests | Pass: 9 passed under both PyMuPDF versions. |
| Focused PR tests | Pass: 7 passed under both PyMuPDF versions. |
| Full pytest | Pass: 4,130 passed, 74 skipped, 208 deselected, 37 warnings in 110.17 seconds. |
| Ruff | Pass repository-wide. |
| Towncrier | Check and draft both pass. |
| Coverage | Pass and byte-stable after `--write`: guidance 47/47; statute 2/2. |
| Citation census | Pass: 143,779 records, 125,251 unique paths, `page_n` 31,399/31,399, no grammar failure, identity drift, or ratchet regression. |
| Tracked scope | Pass: 9 guidance references and 2 statute inventory references; all 14 generated artifacts independently confirmed tracked. |
| Strict release validation | Pass: exactly two scopes, zero errors, zero warnings. |
| Prior-45 conservation | Pass at the semantic hash above. |
| GitNexus | LOW risk, 23 changed files over round 2, zero affected execution processes. |
| `git diff --check` | Pass. |
| Broad prescribed MyPy command | Environment baseline limitation: exit 1 with 168 diagnostics in untouched legacy modules. The pinned round-1 review worktree has 177 under the same MyPy 1.19.0 installation; comparison finds zero branch-only diagnostics. Both changed Python files pass when checked directly with external imports skipped. |
| Signed-ingest guard | Intentionally pending. The required public key is unavailable in this lane, and both old manifests are known stale as detailed below. |

## Commit ledger

- `65f1dcf7` — start and correct the tracked round-2 ledger.
- `f5c28b0a` — add opt-in deterministic PDF text replacements and tests.
- `fb207f06` — correct the PDF stability count in the ledger.
- `c06ba01f` — ingest both sources, rebuild the two scopes and authority map,
  update tests, release selector, census, and run documentation.
- `256634f6` — finalize validation and handoff state in `PROGRESS.md`.

No tracked report was added. This report and `.ca-bbce-sources/` remain
untracked.

## Stale signatures and main-lane handoff

The two signed ingest manifests were left byte-for-byte unchanged, as
directed. They now describe the pre-repair scope:

- Guidance manifest: 3 of 8 applied entries have stale hashes (coverage,
  inventory, and provisions), and it does not include ACL 14-63.
- Old one-section statute manifest: all 4 applied paths are now absent after
  replacement by the combined two-section version.

Main lane must replace/re-sign:

- all 9 guidance artifacts: 6 source snapshots plus inventory, provisions,
  and coverage; and
- all 5 statute artifacts: 2 source snapshots plus inventory, provisions, and
  coverage.

It should then rerun the signed-ingest guard with
`AXIOM_CORPUS_INGEST_PUBLIC_KEY` configured. The existing signatures must not
be treated as validation of the repaired content.

## Sandbox and environment disclosures

- Plain `uv run` initially failed because the sandbox denied access to
  `/Users/maxghenis/.cache/uv`. All uv-based gates then ran through the same
  locked project environment using `UV_CACHE_DIR=/private/tmp/axiom-uv-cache`
  and `UV_NO_SYNC=1`.
- A fresh PyMuPDF 1.28.0 download was blocked by sandbox DNS/network access.
  An existing local uv archive was inspected as real PyMuPDF 1.28.0 and used
  for the required regeneration and test proof.
- GitNexus refreshed and saved the worktree-local graph, but registration in
  `/Users/maxghenis/.gitnexus/registry.json` failed with sandbox `EPERM`.
  Local context, impact, and change-detection queries still completed.
- Cryptographic ingest-guard verification stopped because
  `AXIOM_CORPUS_INGEST_PUBLIC_KEY` is not available in this lane.

No remote or production state was changed.
