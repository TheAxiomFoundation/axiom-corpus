import json, re, sys, yaml
from axiom_corpus.corpus import documents as d
p='data/corpus/sources/us-co/regulation/2026-07-13-recovery-r2026-09-11-tanf-consolidated/2026-07-13-recovery/official-documents/us-co-8-ccr-1403-1'
b=open(p,'rb').read()
ext=yaml.safe_load(open(sys.argv[1]))['documents'][0]['extraction']
blocks=d._extract_pdf_blocks(b, extraction=ext)
print(len(blocks))
for bl in blocks:
    print(f"{bl.metadata['citation_suffix']:>14} p{bl.metadata['page_start']}-{bl.metadata['page_end']} {len(bl.body):6d} | {bl.heading[:80]} | {bl.body[:60]!r} ... {bl.body[-40:]!r}")
