# Dependency versions: one lock for local runs and CI

`uv.lock` pins the version and file hashes of every dependency. Local runs use
it through `uv sync` and `uv run`. CI and the authenticated release-artifact
exporter (`export-release-artifact.yml`) install from it through
`.github/scripts/install-locked.sh`. A test therefore runs on the same versions
on a laptop and in CI, and an extraction run under
`uv run axiom-corpus-ingest ...` uses the versions the tests ran on.

`pyproject.toml` still declares lower bounds (`pymupdf>=1.25.0`). They say what
the code needs. The lock says what runs.

## What CI did before

Until 2026-10-13 `ci.yml` installed with `pip install -e ".[dev]"`, so each run
resolved the lower bounds to whatever PyPI served that day. Measured on the
`test (3.14)` job of run 38428564153 (job 115404368787, 2026-10-13) against the
`uv.lock` of the same day:

| | packages |
|---|---|
| installed by the job | 122 |
| the project itself | 1 |
| at the locked version | 28 |
| at another version | 82 |
| not in the lock at all | 11 |

Among the 82 were libraries that turn source files into provision text, and
the tools that judge a change:

| package | CI | lock |
|---|---|---|
| pymupdf | 1.28.2 | 1.26.7 |
| lxml | 6.1.3 | 6.0.2 |
| beautifulsoup4 | 4.15.0 | 4.14.3 |
| soupsieve | 3.0.3 | 2.8.1 |
| striprtf | 0.0.33 | 0.0.32 |
| pytest | 9.1.1 | 8.4.2 |
| ruff | 0.17.0 | 0.14.8 |
| mypy | 2.4.0 | 1.19.0 |

The 11 packages outside the lock included the three pytest plugins the test
step installed by name (`pytest-cov`, `pytest-timeout`, `pytest-xdist`) and
`httpx2`, which `anthropic` 1.13.0 uses where the locked 0.75.0 uses `httpx`.

The difference had already cost work:

- PyMuPDF 1.26.7 and 1.28.2 read the same PDF differently. In run
  38428564153 ten cases of a test on CMS state plan pages (#862) failed on
  CI's 1.28.2.
- Two tests re-extract committed sources and compare them with the committed
  provisions (`tests/test_us_ca_2025_ftb_3514_booklet.py`,
  `tests/test_us_irs_optional_sales_tax_tables.py`). They are written for
  PyMuPDF 1.26.7 and skip on any other version, so CI never ran them.
- `tests/test_encoder.py` picks its HTTP mock by inspecting the installed
  `anthropic` SDK, because the locked and the CI-resolved SDK used different
  HTTP packages.

## How CI installs

`.github/scripts/install-locked.sh [--project DIR] [--editable] [--extra NAME]...`
installs into the job's Python:

1. `uv`, at the version and hashes in `.github/scripts/uv-requirements.txt`.
2. Every dependency `DIR/uv.lock` pins for the project and the named extras.
   `uv export --frozen` writes them as pip requirements with hashes, and pip
   installs them with `--require-hashes`, from wheels only
   (`--only-binary :all:`): pip does not hash-check the tools it would fetch
   to build a source distribution.
3. The project in `DIR`, with `--no-deps`.

Every install step in `ci.yml` calls the script, and so does the exporter: it
installs in a step that has no credentials, and only the next step, which
receives the read-only storage credentials, runs
`scripts/export_release_artifact.py` with that Python. (#892 brought the
installer, its uv pin, the lock changes and `tests/test_locked_install.py` to
`main` with the exporter.) On a pull request the corpus
guard still runs the base commit's code, on the versions the base commit's
`uv.lock` pins, installed by the base commit's own copy of the script. The
pull request changes none of these, but `ci.yml` itself runs as the pull
request has it, so review of changes to `.github/workflows` and
`.github/scripts` remains the trust root, as `docs/corpus-storage.md` says of
the guard. A pull request whose base predates the script installs the guard
with the pull request's copy and `--allow-source-builds`, since that base's
lock may pin a package with no wheel: on this change's own pull request the
guard step built pyiceberg 0.10.0 from source.

The guard is installed into the same Python before the pull request's own
install, so a package the base lock has and the pull request's lock drops
stays installed for the pull request's tests.

`tests/test_locked_install.py` holds this in place:

- every locked package that is installed is at its locked version, and every
  package the lock pins for the `dev` extra on the running platform is
  installed. In CI this checks that the workflow installed the lock; it fails
  in an environment built any other way, for example by `pip install -e .`;
- `uv lock --check`: `uv.lock` is up to date with `pyproject.toml`, so a
  dependency change without `uv lock` fails;
- every locked package has a wheel for CPython 3.14 on manylinux x86_64,
  which the wheels-only install needs;
- every job in `ci.yml` that runs this project's code installs it through
  the script, and no step there installs packages another way (pip, pipx or
  uv in a `run:` block). This reads the commands; it catches mistakes, not a
  workflow written to get around it.

## Changing a dependency

```bash
# Add or change a requirement: edit pyproject.toml, then
uv lock

# Move one locked package to a newer release
uv lock --upgrade-package <name>
```

Commit `pyproject.toml` and `uv.lock` together. Both commands keep the other
pins where they are as long as the new requirements allow them and PyPI still
lists them (the `verify` extra moved when PyPI dropped its locked
policyengine-us; see
`changelog.d/verify-extra-policyengine-us-relock.changed.md`). Check the lock
diff before committing. Do not run `uv lock --upgrade`: it moves every package
at once, including the extraction libraries below.

## Extraction libraries

These turn source bytes into provision text, so a version move can change the
text extracted from a source the corpus already holds:

| library | used by |
|---|---|
| pymupdf | PDF text, in `corpus/documents.py` and nine other modules |
| beautifulsoup4, soupsieve, lxml | HTML and XML, in over 100 modules |
| striprtf | Oklahoma statutes (RTF) |
| openpyxl, xlrd | spreadsheets in `corpus/documents.py` |

Before moving one of them in the lock, measure what the move changes across
the corpus and get a decision on the result: which version is authoritative
for published extraction is a methodology choice, not a dependency bump.
`scripts/compare_pdf_extraction_versions.py` measures a PyMuPDF move; its
docstring gives the commands.

## PyMuPDF 1.26.7 against 1.28.2

Measured on 2026-10-13 with `scripts/compare_pdf_extraction_versions.py` on
the corpus at `origin/main` 460549782 (2,431 lock files, every locked file
fetched), CPython 3.14.7 on macOS arm64. The locked environment had PyMuPDF
1.26.7 (MuPDF 1.26.12); the other was the same lock with PyMuPDF 1.28.2
(MuPDF 1.28.2), and `pip freeze` differed in that one line.

The snapshots were taken with an earlier version of the script whose records
have the same format. On 183 sampled tasks (123 documents, 60 PDFs) the
committed script extracts the same blocks and pages; the records differ only
in elapsed time and in the input hash the committed script adds to PDF
records. The document snapshots hashed the
bytes they read: all 11,645 readable sources equal the lock's SHA-256. The
page-by-page snapshots did not hash their input. After the runs every one of
the 10,746 PDFs hashed to the lock's SHA-256, and the latest inode change
time among them (17:51 UTC) is earlier than the start of the runs (17:56
UTC), so none changed while the runs read them.

### Committed PDF documents

Committed provision rows with `source_format: pdf` name 11,656 source
documents. Each was re-extracted with `documents._extract_blocks` under each
extraction configuration the manifests give its `source_id`:

| documents | count |
|---|---|
| extracted on both versions | 11,630 |
| identical on both | 11,018 |
| differing in characters or blocks | 445 |
| differing in whitespace only | 167 |
| not extracted: the source path is a JSON Lines file, not a PDF | 15 |
| not extracted: the source file is not in the corpus | 11 |

The 612 differing documents are in 153 of the 1,443 scopes compared. Of
241,256 blocks compared, 3,312 differ: 2,052 in non-space characters and
1,260 in whitespace only. No block exists on one version and not the other.

The 11,630 documents have 245,329 committed rows with a body. A row counts
as reproduced when an extracted block has its exact body:

| committed rows | count |
|---|---|
| reproduced on both versions | 234,145 |
| reproduced on 1.26.7 only | 3,135 |
| reproduced on 1.28.2 only | 0 |
| reproduced on neither | 8,049 |

"Neither" are rows that today's manifests and extractor do not produce on
either version, so they say nothing about PyMuPDF. In 525 of the 612
differing documents 1.26.7 reproduces every committed row; in the other 87
neither version does; in none does 1.28.2 alone. Where the two versions
differ, the committed rows are 1.26.7's.

### Every PDF page

Each of the 10,746 distinct PDFs in the corpus was also read page by page
with the calls the statute adapters make, on both versions. (Four North
Dakota and Ohio tax booklets first hit the 900-second limit on one version
while the host had the run's processes stopped, and were rerun with
`--retry-errors`.)

| pages | count |
|---|---|
| compared | 288,622 |
| `get_text()` differs | 28,563 |
| `get_text()` differs in non-space characters | 2,080 |
| `get_text("text", sort=True)` differs | 4,738 |
| `get_text("words")` differs | 2,587 |

1,813 PDFs have a differing page, 379 a page that differs in non-space
characters. Most `get_text()` differences are in whitespace, which the
official-document extractor normalizes away.

### What differs

Neither version is uniformly better. From the bodies of sampled differing
documents:

- 1.28.2 keeps combining marks attached where 1.26.7 separates them:
  `sx̌ʷýʔłpx` against `sx ̌ʷy ́ʔłpx`
  (`us-or/manual/odhs/open/page-336`).
- 1.28.2 inserts spaces inside words and numbers: `45` becomes `4 5` and
  `follows:` becomes `follows :` (Georgia IT-511,
  `us-ga/form/dor/ty2024/it-511/document-1`), `TAXABLE` becomes `TAX` /
  `ABLE` (FTB 3514), `table` becomes `tabl e`
  (`us-ca/policy/cdss/tanf/acl-15-52/page-3`).
- 1.28.2 drops characters: a dot leader after each telephone number on Form
  760ES (`us-va/form/tax/ty2026/760es/document-1`, whose body is 272
  characters shorter), and on the Georgia IT-511 repeated title text and
  `Phone:` (its body is 2,857 characters shorter).
- 1.28.2 adds text that comes from the PDF's ActualText (it is gone when
  extracted with `TEXT_IGNORE_ACTUALTEXT`): image descriptions such as "This
  image shows a sample of the front of the new HHS ORR Verification of
  Release Card." (`us-or/manual/odhs/open/page-974`), and the line
  "Tennessee Department of Human Services" from a zero-width box near the
  top of the page (`us-tn/manual/dhs/snap/24-14/page-1`).
- 1.28.2 keeps bullet glyphs as the private-use character U+F0B7 where
  1.26.7 leaves them out (`us-md/manual/mdh/medicaid/section-1500/page-3`).
- In whitespace, 1.28.2 sometimes joins lines 1.26.7 separates by a blank
  line (`us-la/manual/dcfs/economic-independence/o-390-dsnap-regular-snap-households-394419/page-1`).

478 of the differing blocks are pages whose committed body is mostly control
characters (glyph codes with no Unicode mapping): CMS Medicaid and CHIP
state-plan pages such as `us-az/policy/cms/chip-state-plan/spa/az-22-0007/approval-package/page-110`.
On the two such pages examined (pages 4 and 110 of that approval package)
both versions return control characters, 1.28.2 more of them. Those pages
are unreadable whichever version is used, a corpus defect of its own: 673
committed rows in 44 scopes have a body that is at least half control
characters.

### Decision

CI now installs the lock, so tests and extraction run on PyMuPDF 1.26.7, the
version the committed corpus was extracted with. Moving the lock to 1.28.2
would change the text a re-extraction gives for 612 documents (5.3%) and
lose the exact reproduction of 3,135 committed rows, for changes that are
improvements in some documents and regressions in others. Which version is
authoritative for published extraction is a methodology call, queued for a
decision; until it is made, the lock stays on 1.26.7.

## What the lock does not pin

- The release workflows (`publish.yml`, `activate-release.yml`,
  `register-release-object.yml`, `mirror-release.yml`) still install with
  `pip install -e .` (#866).
- The build backend `pyproject.toml` names (setuptools). pip fetches it to
  build this project in step 3.
- Programs outside Python, such as the Tesseract binary that OCR extraction
  calls.
