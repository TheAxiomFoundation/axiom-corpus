`extract-official-documents` no longer publishes the extracting machine's path for a manifest
`local_path` copy. Rows recorded `metadata.download_url = file:///<local path>` and a null
`content_type`; they now record the entry's `download_url` (else the Google Drive direct link,
else `source_url`) and the source format's media type, and a relative `local_path` resolves
against the manifest file. `guard-ingested` rejects new inventory and provisions artifacts whose
URL fields hold a `file:` URL. `scripts/audit_local_file_urls.py` lists the 43 locked scopes that
already do, and `scripts/repair_local_file_download_urls.py` writes verified successor scopes for
them.
