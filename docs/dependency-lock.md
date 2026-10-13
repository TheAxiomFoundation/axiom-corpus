# Dependency versions: one lock for local runs and CI

`uv.lock` pins the version and file hashes of every dependency. Local runs use
it through `uv sync` and `uv run`. CI installs from it through
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
   installs them with `--require-hashes`.
3. The project in `DIR`, with `--no-deps`.

Every install step in `ci.yml` calls the script. On a pull request the corpus
guard still runs the base commit's code, now on the versions the base
commit's `uv.lock` pins, so a pull request changes neither the guard's code
nor its dependencies. (The workflow file and the script themselves run as the
pull request has them; review of workflow changes remains the trust root, as
`docs/corpus-storage.md` says of the guard.)

`tests/test_locked_install.py` holds this in place:

- every locked package that is installed is at its locked version. In CI this
  checks that the workflow installed the lock; it fails in an environment
  built any other way, for example by `pip install -e .`;
- `uv.lock` records the requirements `pyproject.toml` declares, so a
  dependency change without `uv lock` fails;
- every locked package has a wheel for CPython 3.14 on manylinux x86_64, so
  CI builds nothing from source except this project;
- no step in `ci.yml` runs `pip install` outside the script.

## Changing a dependency

```bash
# Add or change a requirement: edit pyproject.toml, then
uv lock

# Move one locked package to a newer release
uv lock --upgrade-package <name>
```

Commit `pyproject.toml` and `uv.lock` together. Both commands keep every other
pin where it is. Do not run `uv lock --upgrade`: it moves every package at
once, including the extraction libraries below.

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

## What the lock does not pin

- The release workflows (`publish.yml`, `activate-release.yml`,
  `register-release-object.yml`, `mirror-release.yml`) still install with
  `pip install -e .` (#866).
- The build backend `pyproject.toml` names (setuptools). pip fetches it to
  build this project in step 3.
- Programs outside Python, such as the Tesseract binary that OCR extraction
  calls.
