# Edition-specific DA-KG capture

The BZSt endpoint whose filename mentions 2024 now returns **DA-KG Stand 2026**. The native official-document pipeline retained and extracted the complete 173-page PDF, yielding one parent and one complete body row with zero missing or extra rows. No legal body was edited manually.

The capture uses `manifests/de-kindergeld-dakg-2026.yaml`, version `2026-09-09-de-kindergeld-dakg`, and the actual capture expression date 2026-09-09. The edition year is separate metadata; neither the legacy filename nor PDF creation metadata establishes an issuance date. An unpublished attempt used only the edition year as expression date; the final capture was rerun and signed from a clean committed generator after correcting that declaration.

The preface concerns rules since 1 January 2026 and non-final cases subject to explicit temporal restrictions. This is not a replacement for DA-KG 2025. The consumer enrolls the separate 2026 edition as pending for text-bound applicability review. The complete body's SHA256 is `2e6bda7e7fa84cbf696959e70920cc0577c995b3c5aa8dfafde0feea70b3ed58`.

The additive named-release selector retains all 36 previous scopes unchanged and adds this guidance scope. Publication does not activate serving. Capture does not establish dependency closure or certification.
