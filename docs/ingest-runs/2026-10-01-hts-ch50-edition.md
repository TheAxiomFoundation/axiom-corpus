# Chapter 50 ingest handoff

Generator: axiom-corpus ba6a81ef5d0d3ed12cf7ade187a8a81ada88f821 (merged PR777).

The unsigned four-artifact output can be reproduced with the command below. Exact relative paths, byte lengths, hashes and coverage are in 2026-10-01-hts-ch50-edition-hashes.json. No signing, upload or activation has occurred.

Reasoning: use a disjoint edition-qualified chapter root because the old active release omits the Revision15 chapter50 leaves; substituting the full Revision15 schedule changes unrelated historical rates. The retained official snapshot SHA is 59a76c12e28d7a28975f31a8876bfb08e64927b922fe2b4f88801ff4459181e6. All41chapter leaf bodies use the existing renderer. Existing HTS scopes and selectors must remain unchanged. This source does not authorize ownership or migration of the tariff module.

First commit this reviewed reasoning record (and hash inventory) at repository-relative paths on a branch descended from the generator commit. Then sign from that clean descendant commit, recording the generator commit and signing commit separately. The --reasoning-log input must bind those durable committed bytes.

The established authorized ingest signer should independently verify the hashes, copy ONLY these four previously absent scope files beneath data/corpus in that clean descendant checkout, and use the existing sign-ingest-manifest --lock --push command for jurisdiction us, document-class statute, version 2026-10-01-usitc-hts-2026-rev15-chapter50-edition. Record the actual generation/copy command and this reasoning record. Commit the resulting signed ingest manifest and lock, not ignored corpus bytes. Verify the remote locked objects and guard-ingested checks before proposing merge.

Use the existing ingest signing identity and R2 upload environment. Do not substitute a release key or ephemeral test key. Publication of a new additive immutable release selector is a later reviewed step; activation is not part of this handoff.

## Reproduction

From the reviewed generator checkout, use the existing repository runtime:

```sh
PYTHONPATH=.:src python scripts/repro/us_hts_rev15_chapter50_edition.py \
  --output "$FRESH_OUTPUT" --retained-source "$RETAINED_REV15_JSON"
```

The output directory must not exist, its parent must exist, and its absolute path must contain no symlink ancestors. Verify the output hashes before copying only these four files into the same relative paths under data/corpus. Refuse existing destinations; do not overwrite another scope.

This record describes unsigned preparation. It is not a signed ingest manifest or production publication evidence.
