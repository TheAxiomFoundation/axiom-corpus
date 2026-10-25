# Parentage source recovery for the Kindergeld frontier

This adds 537 corpus rows in two scopes while preserving all seventeen scopes
of the published civil release. It does not declare any module encoded or
assert dependency closure.

The original KindRG was retrieved through the public BGBl Xaver archive:
`https://www.bgbl.de/xaver/bgbl/start.xav?start=%2F%2F*%5B%40attr_id%3D%27bgbl197s2942.pdf%27%5D`.
The site's ordinary session bootstrap and text response identify the PDF as
`bgbl/Bundesgesetzblatt Teil I/1997/Nr. 84 vom 19.12.1997/bgbl197s2942.pdf`.
The retained 2,893,647-byte PDF has SHA-256
`bd58391268f7d4103670967f86ab7642fe9bae34faf56ec36415b2dadc1e2c7b`.
Transient public-session/CSRF values are not committed.

The document is image-only. Existing official-document extraction used German
Tesseract 5.5.3 OCR at 300 DPI. German model SHA-256 is
`19d219bbb6672c869d20a9636c6816a81eb9a71796cb93ebe0cb1530e2cdb22d`
(from the tesseract-ocr/tessdata_fast project). The full 26-page artifact is
retained, with an empty parent row and one extracted body row. The OCR text
contains recognition errors, notably section signs rendered as 8; no claim
of a fully exact transcription is made. Printed page 2942's introduction of
BGB §1591 and page 2967's Article 17 §1 commencement sentence were rendered
and visually verified. Both quoted sentences in the audit are exact body
substrings. Any additional excerpt must be checked against the PDF before
encoding. No OCR body was manually patched.

Because the archive returns a dynamically generated PDF through a temporary
session URL, replay uses the retained canonical snapshot as the CLI's
`local_path`. Construct an untracked copy of the committed manifest adding
an absolute local_path to that PDF, then run:

```sh
TESSDATA_PREFIX=/path/to/deu-model-directory PYTHONPATH=src python -m axiom_corpus.corpus.cli extract-official-documents --base data/corpus --version 2026-09-08-de-kindergeld-parentage-history --manifest /absolute/path/to/replay-manifest.json --source-as-of 2026-09-08 --expression-date 1997-12-16
PYTHONPATH=src python -m axiom_corpus.corpus.cli extract-de-gii --base data/corpus --version 2026-09-08-de-kindergeld-parentage-transition --manifest manifests/de-kindergeld-parentage-transition-gii.yaml --source-as-of 2026-09-08 --expression-date 2026-09-08
```

The second scope captures the full EGBGB and SBGG using the existing GII XML
adapter. EGBGB Article 224 §1 is
`de/statute/bgbeg/1-bjne030901377`, distinguished from other §1 provisions by
the official document ID; its metadata binds `gliederungsbez: Art 224`.
Its first paragraph concerns **Vaterschaft**, not an automatic exclusion of
all maternity relationships involving births before July 1998.

SBGG §11 states that the register sex entry is irrelevant to the parent-child
relationship under BGB §1591 and §1592 no.3. A current sex-marker Boolean
must not be made a conclusive motherhood condition. SBGG §15(2) extends the
specified provisions to earlier changes under TSG and PStG §45b. The SBGG act
row also preserves the GII commencement note: all except §4 entered force
on 1 November 2024; §4 on 1 August 2024. Capture date is not commencement.

These sources address review findings in rulespec-de PR #46: its signed
candidate has an unsupported year-0001 effective date and a current-woman
input, and its tests do not establish temporal persistence or the 2025
consumer scope. Supervised repair is required; no manual RuleSpec edit or
signature reuse is permitted. No serving pointer is changed by this capture.
