# NZ Act 2026/54 amendment markers

The successor scope is `nz/statute/2026-10-23-rulespec-nz-pco`.
Its 26 provision rows retain every predecessor field except the scope-identity
fields `version` and `source_path`, and additive `metadata`. The document
row and all 21 body-bearing rows gain `document_type: amendment_act` and
`amends: [nz/statute/act/public/2018/0032]`; 22 amending rows gain XML-bound Part and
commencement metadata. Sections 5, 8 and 9 insert new provisions and have no
target. Preliminary sections 1–3 receive the document markers without target
or commencement fields. The encoder discards null-body rows, so each surviving
section and inserted Schedule clause carries its own amendment markers.
No RuleSpec content is produced.

The selector `nz-rulespec-2026-10-23-amendment-markers` replaces exactly the
2026-10-20 statute supplement in `nz-rulespec-2026-10-20`; its other eight
scope objects and order are unchanged. This is a **publish-only pin release
for rulespec-nz; never activate it**. No selected scope is withdrawn under
`manifests/withdrawn-scopes.yaml`. Nothing was signed, locked, uploaded or
published by the extraction itself. The hub signed the preceding output;
this regeneration needs re-signing as described under "Signing and publication".

## Retained official evidence

The source is copied from
`data/corpus/sources/nz/statute/2026-10-20-rulespec-nz-pco/act/public/2026/54/act_public_2026_54_en_2026-09-03.xml`.
It is 150,784 bytes, SHA-256
`aa6b16470e1302a80503a5a8fb44ea40159081cd234c731cad672652b5545f52`.
No publisher request or other capture was made. Capture provenance is in the
[predecessor run note](2026-10-20-nz-act-2026-54.md).

The XML root is public Act 2026/54, ID `LMS1607518`, assented and as at
3 September 2026. It has no explicit amendment-Act status attribute. Its 16
`amend` elements and section 3's operative statement, “This Act amends the
Social Security Act 2018”, establish amendment status. Section 3's
`leg-title/@href=DLM6783102` resolves to the principal document's official
identifier in an active row of the base release. Its title is checked against
both section 3's XML and its normalized body; the principal path is derived
from that resolved row, rather than asserted by the overlay.

Top-level `body/part` 1 (`LMS1607692`) contains sections 4–12; Part 2
(`LMS1607699`) contains sections 13–15. Section 2 states **2 November 2026**
for the Act and **1 April 2027** for Part 2. Its Part 2 internal reference
links to `LMS1607699`. The Part 2 and Schedule 2 `date.first.valid` attributes
say `2026-11-02`; the explicit operative exception in section 2 controls.

The schedules are outside the Act's Parts. Schedule 1 (`LMS1607718`) links
through `empowering-prov/intref` to section 10 (`LMS1607652`, Part 1);
Schedule 2 (`LMS1607726`) links to section 13 (`LMS1607693`, Part 2). Each
schedule family inherits its inserting section's Part, date and target.
Inserted Parts 16 and 18 are principal-Act structure: `metadata.part` is
respectively `"1"` and `"2"`, including on their descendant clause rows.
The spec omitted the two schedule wrapper rows; they receive the same
bindings as their descendants even though their bodies are null.

The reviewed overlay contains only nine section-target claims and the three
new-provision section labels. The code checks each amended heading, checks
each target exists and is active in the principal document selected by the
base release, and rejects incomplete or conflicting claims with the affected
row's citation. Dates, document identity, principal identity and Part
membership are derived from the source. The ordinary NZ extractor is unchanged;
enrichment requires invoking the separate module with `--overlay`.

## Section 15's table target

The active principal row
`nz/statute/act/public/2018/0032/schedule/4/part/7/clause/lms118453`
is the unlabelled XML provision `LMS118453` containing the Part 7 rate table.
Its body includes clauses 4, 5, 6 and 6A, which section 15 replaces. Validation
checks the heading's Schedule 4, the operative Part 7 and replacement range,
the target's official provision ID, and those table clause labels. It is the
single `amendment_target` today.

If a later extraction splits the table into clause rows, section 15 must list
the replaced clauses as `amendment_targets`. That split also requires the overlay
validator to check replacement coverage across the targets: `_check_target`
currently requires each target, on its own, to contain every replaced clause.
Discovery from a principal
citation reads every listed target; only the direct amending-section route
blocks on multiple targets, as specified by the encoder contract. This build
does not change the table extraction.

## Encoder application conditions

Clause 125 is cumulative: the relevant benefit must (a) be applied or
reapplied for on or after 2 November 2026, (b) not be reapplied for after MSD
gave a pre-commencement notice or advice of expiry, and (c) be granted or
regranted as a relevant benefit commencing on or after 2 November 2026.
Part 1 encoding therefore needs applicability conditions as well as a date.

Clause 132 applies from 1 April 2027 irrespective of when entitlement starts,
an application is made, or a grant decision is made. It also covers the
specified cases of payments not yet commenced, suspended, not payable, or not
received. The spec's summary omitted decision timing and these payment-status
cases. A plain dated Accommodation Supplement version requires no grandfathering.
No application-condition metadata is added. These clauses receive the same
four routing/Part fields as the rest of their schedule families, plus the two
document markers carried by all body-bearing rows.

The inherited `metadata.stage: in-force` is the existing extractor default,
not evidence of commencement; it is retained. Commencement is established by
the new explicit date and section 2 citation. The source observation and
expression dates remain 20 October 2026, preserving capture identity.

## Scope identity and content preservation

A new scope's identity fields name the new scope; the release gates require it, and
they are unchanged. These are the only fields that differ from the predecessor apart
from the added metadata:

- Every provision's `version` becomes `2026-10-23-rulespec-nz-pco`.
- Every serialized inventory item gains `version:
  2026-10-23-rulespec-nz-pco`. The inventory model has no version field, so this
  value is included when writing the successor inventory records.
- Every provision and inventory item's `source_path` becomes
  `sources/nz/statute/2026-10-23-rulespec-nz-pco/act/public/2026/54/act_public_2026_54_en_2026-09-03.xml`.
  This uses the predecessor's canonical relative-path layout with the new
  version; it resolves under `data/corpus/` to the byte-identical retained XML.
- The coverage report's existing scope-level `version` names the successor.

No other fields change except the added provision markers. Provision `id`,
`parent_id`, citation paths, bodies, headings, ordering, source URLs, identifiers,
source observation dates and expression dates are preserved. Inventory metadata,
source hashes, ordering and all other non-identity values are preserved. The
retained XML is unchanged, including its publisher identity and dates.

## Reproduction and verification

With the `nz/statute` scopes fetched (`axiom-corpus-ingest corpus fetch nz/statute`), on a GIL
CPython 3.14:

```bash
uv run --extra dev python -m axiom_corpus.corpus.nz_amendment_markers \
  --overlay manifests/nz-amendment-markers/act-2026-0054.yaml \
  --temp-root <scratch-dir>
uv run --extra dev python scripts/repro/nz_rulespec_2026_10_23_amendment_markers.py
```

Before writing, the reproducer re-extracts the 2026-10-20 scope with the
ordinary adapter into a temporary store and compares all four artifacts byte
for byte. Its output source copy has the same SHA-256, and all 26 new rows
are compared to the predecessor with only `metadata`, `version` and
`source_path` excluded. Metadata checks require all inherited keys and values
to survive and allow only the reviewed added markers. Inventory comparison
excludes only `version` and `source_path`; each remaining value and the item
order must match the predecessor. The new coverage report has 26 matched
entries, no missing, extra or duplicate entries, and `complete: true`.

Equality mutations change section 4's body, heading, ordinal, ID or source
observation date; each fails the preservation check. Dedicated identity tests
check every serialized provision and inventory record against the successor's
canonical values and reject a retained predecessor `version` or `source_path`.
The existing shared release gate independently rejects a stale provision
`version`, provision `source_path` or inventory `source_path`, producing exactly
one error for each isolated mutation. It ignores the inventory's optional
serialized `version`; the dedicated inventory identity assertion enforces that
additional requirement.

Other validator mutations cover source-byte drift, predecessor artifact-byte
drift, missing or inactive principal targets, incorrect amended headings,
missing table clauses, malformed or incomplete overlays, XML Part membership,
schedule empowering references and commencement statements. Failures identify
the affected row or artifact. Moving section 13 into XML Part 1 changes its
and Schedule 2's Part/date bindings, checking the structural dependency.

The selector reproducer follows the pattern in
`scripts/repro/us_rulespec_2026_10_20_fs_pilot_reg_e_f.py` on main. Its tests
independently derive the exact scope delta, reproduce the selector bytes and
reject duplicates or withdrawn selected scopes. The 300-example property
preserves sibling scope values and order while replacing only the named
predecessor, including bases with other versions of the same jurisdiction and
document class. The CA concurrent-version reproducer is on another open PR's
branch and is not required for this build.

Before the identity correction, isolated local validation reported 53 errors
and no warnings:
26 `provision_version_mismatch`, 26 `noncanonical_inventory_source_path` and
one deduplicated `noncanonical_provision_source_path`. The corrected scope
reports **zero errors and zero warnings** under the same existing
`validate_release` call, using `complete-expression-dates-v1` and
`ReleaseGatePolicy.empty()`. The isolated check exercises the existing scope
validators without signing or weakening their version/source boundaries.

Before this fix round, the focused marker, selector and locked-install suite
passed: **101 passed** (68 marker tests, 11 selector tests and 22 locked-install tests).
Ruff passes, mypy reports no issues in 105 corpus source files, and
`towncrier check` exits zero. The existing NZ converter/legislation quartet
reproduced round 1's result: **68 passed, one failed**. The
unchanged `test_nz_release_has_one_exact_row_for_every_current_pco_provision`
hits its 60-second timeout while parsing the full retained release. It also needs
the June regulation scope, which the partial checkout used here did not fetch. The selected release-policy/withdrawn checks
passed: **76 passed**, with the same four exclusions as round 1
(one git-writing test and three groups needing unrelated unfetched scopes).
CI runs the full suite.

Checks ran on GIL CPython 3.14.7 with at most four workers. The reproducer and
selector commands both exit zero.

Direct checks of the persisted output verify 26 identical bodies and 26
non-identity provision and inventory mappings, 26 additive metadata changes,
and all four unchanged predecessor lock hashes. Coverage
differs from the predecessor only in its scope version. No protected corpus
bytes are tracked in git.

## Fix-round verification

The corpus-side encoder contract checks both in-memory and persisted output:
all 21 body-bearing rows carry both document markers; all 19 rows declaring a
target point to an existing provision inside the principal document; and
insertion sections 5, 8 and 9 carry commencement evidence without a target.
The six new cases bring the focused marker, selector and locked-install suite
to **107 passed**. The bounded NZ adapter quartet reports **68 passed, one
deselected** (the previously timed-out full-release scan); the selected
release-policy tests report **76 passed, 55 deselected** with the exclusions
described above. Ruff, mypy (105 source files) and Towncrier pass.

The new contract assertions reject **94 deliberate output mutations**:
44 missing marker fields, 38 foreign or nonexistent principal targets, and
12 missing commencement fields or invented insertion targets. Baseline
contracts pass before and after these in-memory mutations.

The external integration probe AST-extracts the actual encoder functions at
`81ddc09ac1d5c9d55a262d25ae8f91064227dc61`; it is not a repository test.
Before regeneration, 0 of 21 body-bearing rows satisfy its amendment marker
predicate, and both principal requests attach no amendment evidence. At that
encoder head, direct sections 5 and 9 already classify by their text, while
section 8 bypasses amendment routing. After regeneration, all 21 rows satisfy
the marker predicate. Principal section 20 attaches section 4's exact body,
and the `clause/lms118453` table attaches section 15's exact body. Direct
sections 5, 8 and 9 all classify as amendments, and the actual routing function
rejects each for a missing `metadata.amendment_target`.

The regenerated selector validates all nine scopes with **zero errors and
zero warnings**, retaining one existing baselined guidance notice. All 26
bodies remain byte-identical, and only `metadata`, `version` and `source_path`
differ from the predecessor. The four successor artifacts total 304,895 bytes;
only the provisions file differs from the prior successor lock. Its SHA-256
is `d2bfab06f4f699010567547e4b47acc3e9d6eb9f9593d33b526ec3e9b4476d9a`
(128,580 bytes). Source, inventory, coverage and selector bytes remain unchanged.

## Signing and publication

The hub signed and locked the preceding generator output with
`sign-ingest-manifest --lock --push`, which records the generator commit and
pins the corpus bytes outside git. The regenerated provisions from this fix
round need a new hub signature and lock; this round performs no signing or upload. The release
selector is publish-only: dispatch `publish.yml`, then `mirror-release.yml`. Never
activate it.

The opt-in implementation and its tests are new files; the ordinary NZ adapter is
unchanged.
