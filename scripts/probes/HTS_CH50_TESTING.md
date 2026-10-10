# Chapter 50 source-edition integration probe

These probes create an **ephemeral test key** and mock publication evidence using
this repository's release-gate unit fixture. They do not upload, activate, or
provide production publication authorization. The existing HTS scopes are not
replaced. The generated source root identifies an edition of retained evidence,
not an additional legal heading.

From the corpus repository, set `SOURCE` to the retained
`hts_2026_revision_15_json.json` (SHA-256
`59a76c12e28d7a28975f31a8876bfb08e64927b922fe2b4f88801ff4459181e6`).
Set `ENCODER_PYTHON` to a frozen environment from axiom-encode commit
`4e3cd9a27ca4d96389c9b8adbce0a76186631d52` (2079), installed with
`uv sync --frozen --python 3.14`. Set `POLICY` to the unchanged imported USITC
`us/policies/usitc/us-tariff-duty/lines/generated/ch50.yaml` from rulespec-us
commit `a924503cf3ad1d10c4a75ec892c1af37745223e3`.

```sh
PYTHONPATH=.:src uv run --extra dev python scripts/probes/hts_ch50_signed_fixture.py \
  --retained-source "$SOURCE" --binding /tmp/ch50-test-binding.json \
  --historical-artifact "$CURATED_HTS_JSONL" \
  --historical-artifact "$REV3_NOTES_JSONL" \
  --historical-artifact "$FULL_REV15_JSONL"
"$ENCODER_PYTHON" scripts/probes/hts_ch50_verify_fixture.py \
  --binding /tmp/ch50-test-binding.json --policy "$POLICY" \
  --result /tmp/ch50-test-result.json
```

The three historical paths are the retained curated HTS, Rev3 notes, and full
Rev15 provision artifacts. Their hashes must remain unchanged.

The verifier must resolve 41 exact leaf bodies, the composed chapter, and all
52 excerpts from 13 distinct table citations. A fresh subprocess must reject a
tampered provision artifact; the fixture is restored afterward. Binding and
result files are test artifacts; no private signing key is retained.

Focused adapter tests:

```sh
AXIOM_CORPUS_PARTIAL_TESTS=1 PYTHONPATH=.:src uv run --extra dev pytest -q \
  tests/test_hts_rev15_chapter50_edition.py
```

The partial-tree flag is for this explicitly scoped test only. It does not
establish that the required full repository suite passed. Full release checks,
authenticated production release publication, and native RuleSpec admission
remain separate requirements.
