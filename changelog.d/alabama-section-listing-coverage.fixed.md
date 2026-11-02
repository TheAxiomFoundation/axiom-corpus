Keep an Alabama run whose `codesOfAlabama` section listing ends before its reported `count` as incomplete. Before this, a listing that stopped on an empty or short page, repeated the same rows on every page, or reported no sections at all left out every title, chapter or article with no fetched section, and coverage still read complete.

Now a listing ends early when the run holds fewer distinct sections than the listing's `count`, when it reports no sections, or when a sections page cannot be fetched or read. In such a run, a container with no section beneath it in the code's table of contents stays a record. Every other container or section the run didn't fetch becomes a gap, with one error each. With `--only-title`, only that title's nodes count. A gap's source is the sections page that ended the listing, or the titles source when that page could not be fetched.

When nothing the run didn't fetch can be named, the run can't place the missing sections. It marks the shortfall instead, as a gap at the container of the last section held, or at the title under `--only-title`, or at the code (`us-al/statute`), so a short listing never reads complete.

A failure to write a page's local snapshot aborts the run instead of becoming a gap. A complete listing writes the same inventory, provisions and coverage as before, and a run capped by `--limit` is unchanged.
