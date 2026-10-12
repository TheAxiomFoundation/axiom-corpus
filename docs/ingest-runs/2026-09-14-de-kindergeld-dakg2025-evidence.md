# DA-KG 2025 A 19.2 retained-source capture

This native capture normalizes the complete A 19.2 (Nachweis der Behinderung)
from page 54 of the BZSt-authored DA-KG Stand 2025. Both paragraphs, all three
numbered proof routes, the alternative medical-proof route, and the distinction
between a limited proof period and expiry of an SGB IX card are retained.
The complete 173-page original PDF is preserved as the source snapshot.

The download is from Tacheles, a non-government mirror. Its SHA-256 is exactly
33e1a8c4f6bd65034febc9d0c45850e64e982f665f519f08eaeceb80ac02dedd,
which axiom-oracles already binds in de-subject-003 and its DA-KG 2025 frontier.
The document identifies BZSt as publisher and Stand 2025 on its cover and preface.
The primary_source flag describes original government-authored content; it does
not identify Tacheles as an official host or imply independent cryptographic
attestation by BZSt. The live legacy BZSt URL was also downloaded and inspected:
it now returns Stand 2026, SHA-256 29cf1e1b24708f0bb1680c031bad97e79d87cab805c9a74b6379caa4d5196e9c.
No current official-host capture of the 2025 bytes is claimed.

The manifest's expression_date records capture on 14 September 2026; edition_year
is 2025. Neither field establishes an inferred commencement or issuance date.
This does not substitute the 2026 guidance for the 2025 ledger.

Extraction uses the existing extract-official-documents adapter, single_block,
and a page window bounded by the separate A 19.2 and A 19.3 label lines. The
initial combined label/title anchor yielded an empty block and was rejected
before signing despite the inventory coverage flag. The corrected extraction
requires one substantive block and two rows; the entire normalized body was
compared to the original PDF page with whitespace normalization only. Page 54
was rendered and visually inspected, including section boundaries and all lists.

Reproduce with the public manifest and a temporary copy whose local_path points
to the retained snapshot identified by the audit:

```bash
axiom-corpus-ingest extract-official-documents --base data/corpus \
  --version 2026-09-14-de-kindergeld-dakg2025-evidence \
  --manifest /path/to/runtime-manifest.json
```

No generated body or receipt was manually edited. The cumulative release selector
preserves all 56 preceding DE scopes and adds only this guidance scope. Other
DA-KG sections, the substantive disability definition and eligibility conditions
remain independent work. Capture and signing do not close the frontier.
