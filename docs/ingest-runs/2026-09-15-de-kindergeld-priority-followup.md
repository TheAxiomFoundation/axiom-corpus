# Cross-border priority follow-up originals

The native official-document adapter captures three complete BFH originals
(III R 68/13 of 28 April 2016, III B 127/14 of 27 April 2015 and the III R 17/13
reference order of 8 May 2014), plus the German CURIA judgment C-378/14,
Trapkowski, of 22 October 2015. These correspond to pending discovery members
149–152. The 2014 reference order is distinct from the 2016 final judgment.

```bash
PYTHONPATH=src axiom-corpus-ingest extract-official-documents --base data/corpus --version 2026-09-15-de-kindergeld-priority-followup --manifest manifests/de-kindergeld-priority-followup.yaml
```

The recorded capture uses the same manifest with local_path entries pointing
to exact receipted official bytes. Three PDFs retain 13 pages; the HTML capture
selects the complete CURIA #document_content element, including both concluding
holdings and the procedural-language footnote. The legacy juris.curia.europa.eu
host provides the original German text; the current InfoCuria redirect supplies
an application shell and the attempted EUR-Lex PDF returned empty responses.
Neither shell nor empty response was ingested as judgment text.

All non-whitespace source text is conserved. Independent capture review found
no actionable findings; all PDF pages were rendered and representative first
and final pages inspected. The audit binds exact source, manifest and body
hashes. No generated body was manually edited. Decision dates are expression
dates; capture date is separate.

The release selector appends one scope to all 60 prior scopes. This capture
establishes neither current legal bearing nor BStBl II issue membership or
executable coverage. It does not activate serving or announce certification.
