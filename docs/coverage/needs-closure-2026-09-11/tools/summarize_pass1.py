"""Roll-ups from a <program>-matrix.csv: status totals, per-jurisdiction table, top gap families, markdown out."""
import csv, sys, collections, yaml
prog, out = sys.argv[1], sys.argv[2]
rows = list(csv.DictReader(open(f'{out}/{prog}-matrix.csv')))
schema = {e['id']: e for e in yaml.safe_load(open(f'{out}/{prog}-schema.yaml'))['elements']}
ST = ['PRESENT','EXTRACTABLE','ABSENT','OUTREACH','REVIEW','INHERITED','NOT_APPLICABLE']
tot = collections.Counter(r['status'] for r in rows)
print('## Status totals (all cells)\n')
print('| Status | Cells |\n| --- | ---: |')
for s in ST: print(f'| {s} | {tot.get(s,0)} |')
print(f'| total | {len(rows)} |')
# state-level cells only (exclude us row, INHERITED, NOT_APPLICABLE)
sl = [r for r in rows if r['jurisdiction']!='us' and r['status'] not in ('INHERITED','NOT_APPLICABLE')]
tot2 = collections.Counter(r['status'] for r in sl)
print('\n## Status totals (state-level checked cells only)\n')
print('| Status | Cells | Share |\n| --- | ---: | ---: |')
for s in ST[:5]: print(f'| {s} | {tot2.get(s,0)} | {100*tot2.get(s,0)/max(1,len(sl)):.1f}% |')
print(f'| total | {len(sl)} | |')
# federal row
print('\n## Federal row (us)\n')
fed = [r for r in rows if r['jurisdiction']=='us']
c = collections.Counter(r['status'] for r in fed)
print('| Status | Elements |\n| --- | ---: |')
for s in ST: 
    if c.get(s): print(f'| {s} | {c[s]} |')
print('\nFederal elements not PRESENT:\n')
for r in fed:
    if r['status'] not in ('PRESENT',): print(f"- `{r['element']}` {r['status']}: {schema[r['element']]['title'][:110]} — {r['evidence_note'][:160]}")
# per jurisdiction
print('\n## Per-jurisdiction roll-up (state-level checked elements)\n')
print('| Jurisdiction | PRESENT | EXTRACTABLE | ABSENT | OUTREACH | REVIEW | checked |\n| --- | ---: | ---: | ---: | ---: | ---: | ---: |')
byj = collections.defaultdict(collections.Counter)
for r in sl: byj[r['jurisdiction']][r['status']] += 1
for j in sorted(byj):
    c = byj[j]; n = sum(c.values())
    print(f"| {j} | {c.get('PRESENT',0)} | {c.get('EXTRACTABLE',0)} | {c.get('ABSENT',0)} | {c.get('OUTREACH',0)} | {c.get('REVIEW',0)} | {n} |")
# top gaps by element (states not PRESENT)
print('\n## Top gaps: elements by number of states not PRESENT (state-level checked elements)\n')
bye = collections.defaultdict(collections.Counter)
for r in sl: bye[r['element']][r['status']] += 1
gaps = sorted(bye.items(), key=lambda kv: -(sum(v for k,v in kv[1].items() if k!='PRESENT')))
print('| Element | Title | not PRESENT | EXTRACTABLE | ABSENT | OUTREACH | REVIEW | family |\n| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |')
for e, c in gaps[:45]:
    np_ = sum(v for k,v in c.items() if k!='PRESENT')
    print(f"| `{e}` | {schema[e]['title'][:80]} | {np_} | {c.get('EXTRACTABLE',0)} | {c.get('ABSENT',0)} | {c.get('OUTREACH',0)} | {c.get('REVIEW',0)} | {schema[e]['carrying_family_state'][:60]} |")
# gap families: group not-PRESENT cells by carrying family
print('\n## Gap families (state-level cells not PRESENT, by carrying family)\n')
fam = collections.defaultdict(lambda: collections.Counter())
famstates = collections.defaultdict(set)
for r in sl:
    if r['status']!='PRESENT':
        fam[r['family']][r['status']] += 1; famstates[r['family']].add(r['jurisdiction'])
print('| Family | cells not PRESENT | states affected | EXTRACTABLE | ABSENT | OUTREACH | REVIEW |\n| --- | ---: | ---: | ---: | ---: | ---: | ---: |')
for f, c in sorted(fam.items(), key=lambda kv: -sum(kv[1].values())):
    print(f"| {f[:90]} | {sum(c.values())} | {len(famstates[f])} | {c.get('EXTRACTABLE',0)} | {c.get('ABSENT',0)} | {c.get('OUTREACH',0)} | {c.get('REVIEW',0)} |")
# PE cross-check: elements the law has that PE lacks
print('\n## PolicyEngine cross-check\n')
pe_no = [e for e in schema.values() if str(e['pe_modeled']).startswith('no')]
pe_yes = [e for e in schema.values() if not str(e['pe_modeled']).startswith('no')]
print(f'Elements modeled (fully or partially) by PolicyEngine: {len(pe_yes)} of {len(schema)}; not modeled: {len(pe_no)}.')
print('\nState-level elements the law has that PolicyEngine does not model:\n')
for e in schema.values():
    if e['level']!='federal_only' and str(e['pe_modeled']).startswith('no'): print(f"- `{e['id']}` {e['title'][:100]}")
