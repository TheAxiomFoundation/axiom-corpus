import re, yaml
from axiom_corpus.corpus import documents as d
p='data/corpus/sources/us-co/regulation/2026-07-13-recovery-r2026-09-11-tanf-consolidated/2026-07-13-recovery/official-documents/us-co-8-ccr-1403-1'
b=open(p,'rb').read()
ext=yaml.safe_load(open('manifests/us-co-ccap-8-ccr-1403-1.yaml'))['documents'][0]['extraction']
blocks=d._extract_pdf_blocks(b, extraction=ext)
raw=d._filtered_pdf_lines(b, extraction={})
filt=d._filtered_pdf_lines(b, extraction=ext)
print('raw lines',len(raw),'filtered',len(filt),'dropped',len(raw)-len(filt))
# what was dropped, grouped
from collections import Counter
fs=Counter(filt); rs=Counter(raw)
dropped=rs-fs
print(sorted(Counter(l for (l,p),n in dropped.items() for _ in range(n)).items(), key=lambda x:-x[1])[:12])
nonheader_numbers=[(l,p) for (l,p) in filt if re.fullmatch(r'\d{1,3}',l)]
print('standalone numbers kept', nonheader_numbers)
start=[i for i,(l,p) in enumerate(filt) if l=='3.100'][0]
src_tokens=' '.join(l for l,p in filt[start:]).replace('Editor’s Notes','editors-notes').split()
out_tokens=' '.join(f'{bl.heading} {bl.body}' for bl in blocks).split()
print('tokens src',len(src_tokens),'out',len(out_tokens),'equal',src_tokens==out_tokens)
if src_tokens!=out_tokens:
    for i,(a,c) in enumerate(zip(src_tokens,out_tokens)):
        if a!=c: print(i, src_tokens[i-5:i+5], out_tokens[i-5:i+5]); break
b3116=[bl for bl in blocks if bl.metadata['citation_suffix']=='3.116.3'][0]; print(b3116.heading)
h=[bl for bl in blocks if bl.metadata['citation_suffix']=='3.105.1'][0].body
i=h.find('Family Size'); print(h[i-200:i+420])
