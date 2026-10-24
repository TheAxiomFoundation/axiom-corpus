# Title 52 election statute review addendum (2026-10-23)

This addendum supersedes the publication instructions in the historical
[2026-09-29 ingest run note](2026-09-29-election-statute-uocava-nvra.md).
Merging a release selector does not publish it. After review and green CI,
publication requires explicit dispatch of `publish.yml` with the immutable
selector on `main` through the `release-publish` environment. Activation remains
a separate operation through `activate-release.yml`. See
[Named Release Publication](../named-release-publication.md).

This repair adds no release selector and requests no publication or activation.
Uploading an ingest's content-addressed corpus objects does not publish a release
or change serving; see [Corpus storage outside git](../corpus-storage.md).

The provenance invariant is unchanged: the original signed ingest manifest,
scope lock, four artifact hashes, and historical run note retain their original
bytes. The signed clean source commit
`b325fcc4a320f92d6cd3ad0ed27f6fa60cc9d41e` must remain an ancestor of the repaired
branch head; integration must preserve that ancestry with a merge commit.
