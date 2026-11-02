`validate-release` takes `--release` more than once (and `--workers`): one
pass validates every named selector, deep-checking each distinct scope once
and walking the local corpus tree once, and still prints each selector's own
full report and verdict (the same as validating it alone). CI's "Validate
named release selectors" job validates all selectors this way; it read and
checked every scope about nine times (18,783 scope entries, 2,116 distinct
scopes) and took over 40 minutes. The unused release-wide citation set no
longer reaches the per-scope checks: parent integrity is scope-local, and
citation uniqueness is the only release-wide provision check.
