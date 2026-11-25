Add a dispatched `Upload signed ingest corpus objects` workflow and the
`corpus ci-pack`, `corpus ci-select-asset` and `corpus ci-upload` commands, so
an ingest pull request's locked objects reach R2 without R2 write credentials
on the ingester's machine. The upload job accepts an object only when a signed
ingest manifest, the lock that equals it, and the uploaded bytes agree
(`docs/corpus-ci-upload.md`).
