# 2026-07-21 US SNAP Chapter 51

This ingest captures the complete current US Code Chapter 51, Supplemental
Nutrition Assistance Program, from the Office of the Law Revision Counsel's
official USLM XML release point for Public Law 119-100. The downloaded Title 7
source reports `Online@119-100` and a creation date of 2026-04-17.

The source archive was downloaded from:

`https://uscode.house.gov/download/releasepoints/us/pl/119/100/xml_usc07@119-100.zip`

The corpus extractor was run against `usc07.xml` with Title 7 and all 34
sections in Chapter 51 selected explicitly:

```text
axiom-corpus-ingest extract-usc --title 7 --include-title \
  --version 2026-07-21-snap-chapter-51-title-7 \
  --source-as-of 2026-06-26 --expression-date 2026-06-26 \
  --section 2011 --section 2012 --section 2012a --section 2013 \
  --section 2014 --section 2014a --section 2015 --section 2016 \
  --section 2016a --section 2017 --section 2018 --section 2019 \
  --section 2020 --section 2021 --section 2022 --section 2023 \
  --section 2024 --section 2025 --section 2026 --section 2026a \
  --section 2027 --section 2028 --section 2029 --section 2030 \
  --section 2031 --section 2032 --section 2033 --section 2034 \
  --section 2035 --section 2036 --section 2036a --section 2036b \
  --section 2036c --section 2036d usc07.xml
```

The extractor's canonical scope version is
`2026-07-21-snap-chapter-51-title-7-title-7`. Coverage is complete: 827 source
rows match 827 provision rows, with no missing provisions, extra provisions,
or duplicate source or provision citations. The count includes the Title 7
container and the selected chapter's structured descendants.

No corpus source or provision row was written by hand. The signed ingest
manifest authenticates the official source XML, inventory, provisions,
coverage report, and this run record.
