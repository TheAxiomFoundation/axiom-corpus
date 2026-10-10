# New York SNAP regulations ingest (2026-07-17)

## Official source boundary

The New York Department of State publishes the online NYCRR through Thomson
Reuters Westlaw and identifies that online edition as unofficial and not for
evidentiary use. This scope retains the two complete SNAP regulation parts:
Part 385, covering public-assistance and SNAP employment requirements, and Part
387, covering the Supplemental Nutrition Assistance Program. Their two browse
pages enumerate 42 documents: 39 codified sections, two notes documents, and one
references document. All 44 HTML pages are retained exactly as served.

The Westlaw text layer reports that the base compilation is current through
September 15, 2021. It therefore contains superseded standard utility allowances
in section 387.12(f)(3)(v). The current text is restored from two retained
official Department of State Register PDFs. The October 15, 2025 issue supplies
the complete amended clauses and the February 25, 2026 Notice of Adoption states
that the final rule made no changes to that published text. The final notice is
the expression-date authority for the four overlaid rows.

## Generated scope

No corpus row or retained source is authored or edited manually. The scoped
NYCRR extractor retains each browse page and child document, reconstructs the
nested subdivision hierarchy, verifies the adopted amendment, removes only its
bracketed superseded language, and applies the current clauses:

```text
env -u UV_FROZEN uv run --extra dev axiom-corpus extract-nycrr-parts --base data/corpus --version 2026-07-17-ny-snap-regulations --manifest manifests/us-ny-snap-regulations.yaml --source-as-of 2026-07-17 --expression-date 2026-07-17
```

The generated scope contains 1,678 rows with complete 1,678-of-1,678 coverage:
two part roots, three supporting documents, 39 sections, and 1,634 nested
subdivisions. Every non-root citation has its parent, and no generated nested row
is empty; the source's repealed section 387.13 remains an empty section root. The
adopted allowances are $1,062/$988/$877 for heating and cooling,
$419/$388/$355 for utilities, and $32 for telephone.

The retained October 15 rule-text PDF is 1,022,894 bytes with SHA-256
`4dbfc93a066b640da53f0a0817bccd65d37f850e065ed3b707330fa6d582a993`.
The retained February 25 adoption PDF is 7,555,813 bytes with SHA-256
`0b613beba5abed601f7fb879a05a9a8802975776fabc3274e1b8d1954b5ec25e`.

A second live extraction into a clean corpus root reproduced the provisions and
coverage artifacts byte for byte. Both State Register PDFs and the two NYCRR
browse pages were also byte-identical. Westlaw randomized only Cloudflare's
`data-cfemail` anti-scraping token in the child-document HTML; after normalizing
that non-content attribute, the sorted 44-file HTML checksum manifest matched at
SHA-256 `f183b57220c15f27621e737703c732f6defcb1ac699f84360d14e2056c6be6a6`.
Inventory structure was identical after excluding the raw hashes affected by
those randomized tokens.

The source-less `2025-10-01-otda-snap-sua` scope and the secondary-source
`2026-05-09-ny-snap-eligibility` scope are removed only after this replacement is
committed and signed, with each removal recorded in a signed tombstone.
