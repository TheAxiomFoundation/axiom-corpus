The locked-install check now splits each workflow step's shell text into commands
and words in one pass. Quotes and escapes no longer hide an install or fake one,
pathological text no longer slows the scan to seconds, and `uv run -w`,
`--with-editable`, `--with-requirements` and `python -mpip` now count as installs.
The order check reads a step's `shell` by its program, so
`bash --rcfile python.rc {0}` no longer counts as running Python.
