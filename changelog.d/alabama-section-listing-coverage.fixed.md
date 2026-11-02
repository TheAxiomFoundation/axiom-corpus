Keep an Alabama run whose `codesOfAlabama` section listing ends before its reported `count` as incomplete. Before this, a listing that stopped on an empty or short page, repeated the same rows on every page, or reported no sections at all left out every title, chapter or article with no fetched section, and coverage still read complete.

Now, when the run holds fewer distinct sections than the listing's `count`, the listing reports no sections, or a sections page cannot be fetched or read:

- Every container the scaffold or titles name with no fetched section beneath it is an inventory gap with no provision, plus one error per gap. With `--only-title`, only that title's containers count.
- The gap's source is the sections page that ended the listing, or the titles source when that page could not be fetched.
- A container whose heading, or an ancestor's heading, reads "Repealed", "Reserved" or "Transferred" stays a record, because it holds no sections by law.
- When every container holds a fetched section, the container of the last section held is the gap.

A complete listing writes the same inventory, provisions and coverage as before. A run capped by `--limit` is unchanged.
