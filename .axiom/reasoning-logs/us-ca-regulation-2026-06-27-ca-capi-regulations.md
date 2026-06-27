# California CAPI Regulations Ingest

Run date: 2026-06-27

Source manifest: `manifests/us-ca-capi-regulations.yaml`

The manifest points to the California Department of Social Services CAPI/CVCB regulations PDF for EAS Chapter 49. The official-document extractor used labeled section segmentation on section labels matching `49-###`, starting at page 2 and dropping repeated manual headers/footers.

The run produced one source PDF artifact, 24 inventory entries, and 24 provision records. Coverage is complete with zero missing or extra provisions.

This source is needed for Axiom encoding of California CAPI / SSI state supplement parity work because the encoder could not resolve `us-ca:regulation/cdss/eas/49/49-005` before this source was materialized locally.
