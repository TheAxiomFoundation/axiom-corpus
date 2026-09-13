"""Needs-closure check: one CSV row per (jurisdiction, element) for Medicaid and CHIP.

Read-only over data/corpus. Usage:
  python3 build_matrix.py --corpus /path/to/axiom-corpus --out docs/coverage/needs-closure-2026-09-11 [--program medicaid|chip]

Statuses:
  PRESENT        a specific provision in a selected scope carries the element (cited)
  EXTRACTABLE    an official publisher lists the carrying family; not taken (family and index URL named)
  ABSENT         the publisher posts nothing carrying it (what was checked is in evidence_note)
  OUTREACH       the queue row records a publisher block
  REVIEW         cannot tell from the corpus (candidate cited when a weak-pattern match exists)
  INHERITED      federal-only element; carried once at the federal row and inherited by the state
  NOT_APPLICABLE part 436 (GU/PR/VI only) at the state level; state-only structure elements at the federal level

Pass 2 (2026-09-12) search rules, see build_schema.py:
  - universe per state = the state's 2026-09-10 Medicaid and CHIP scopes, plus the pointer scopes named in
    the queue rows for done-by-pointer states (FL ESS manual, IL CSMM, MI Bridges, WV IMM, ID IDAPA 16.03.05,
    IN IHCPPM chapter 5000 in us-in-ssp-sapn, TX tx-manuals); no SNAP, TANF, WIC, CCDF, SSI or tax scope is searched;
  - strong pattern hit -> PRESENT; weak pattern hit -> REVIEW (candidate); needs_number requires a value
    signal in the body; neg_context rejects Medicare / ACA windows; a hit only in a table-of-contents
    provision is a candidate, not PRESENT;
  - no hit: OUTREACH if the program queue row is blocked; ABSENT for community-engagement elements (IFC
    compliance 2027-01-01) and for the CHIP agency-page states whose publisher posts no manual; EXTRACTABLE
    when a CMS-posted state plan family or an untaken publisher family carries the element; else REVIEW.
"""
from __future__ import annotations
import argparse, csv, json, os, re, sys, time, collections
import yaml

STATES = ['us-'+s for s in 'ak al ar az ca co ct dc de fl ga hi ia id il in ks ky la ma md me mi mn mo ms mt nc nd ne nh nj nm nv ny oh ok or pa ri sc sd tn tx ut va vt wa wi wv wy'.split()]
STATE_NAMES = {}
# pointer scopes: queue rows say the program text is already held in these released scopes
POINTER = {
 'us-fl': ['2026-05-27-fl-ess-manual-r2026-07-15-self-contained'],
 'us-il': ['2026-05-27-il-cash-snap-medical-manual-r2026-07-15-self-contained'],
 'us-mi': ['2026-07-17-mi-bridges-manual'],
 'us-wv': ['2026-07-21-wv-income-maintenance-manual'],
 'us-id': ['2026-07-04-id-aabd-rules'],
 'us-in': ['2026-07-04-in-ssp-sapn'],
 'us-tx': ['2026-05-27-tx-manuals-r2026-07-15-self-contained'],
}
PROG_VER = re.compile(r'2026-09-10-(medicaid|chip)-state-eligibility-manual')
CHIPCTX = re.compile(r'\bchip\b|\bs-?chip\b|\bm-?chip\b|title xxi|children.s health (insurance|plan)|kidcare|kid care|husky b|child health plus|peachcare|famis|all kids|hawk-i|denali kidcare|healthy steps|dynasaur|nevada check up|coverkids|cub ?care|healthy montana kids|arkids (first-?)?b|michild|mchp|maryland children.s health|chp\+|child health plan plus|florida kidcare|healthy kids|badgercare plus|wvchip|kchip|lachip|hoosier healthwise|package c|mo healthnet for kids|nj familycare|apple health for kids|partners for healthy children|sooner ?care|delaware healthy children|dr\. dynasaur|1397|457\.|targeted low.income', re.I)
TOC = re.compile(r'table of contents|^contents$|table-of-contents|/toc\b', re.I)
NUM = re.compile(r'\d{1,3}\s?(%|percent)|\$\s?\d|federal poverty|\bFPL\b|\bFPIG\b|\bFPG\b|poverty (level|guideline|line)', re.I)
PROGCTX = re.compile(r'medicaid|medical assistance|\bchip\b|title xix|title xxi|buy-?in', re.I)
# CHIP agency-page states: the queue row records that the agency publishes no CHIP eligibility manual
CHIP_NO_MANUAL = {'us-al': 'ADPH publishes no ALL Kids eligibility manual and the Alabama Administrative Code chapter could not be located (queue row); only the Income Guidelines and Premiums/Copays pages are held',
                  'us-ct': 'the DSS Uniform Policy Manual has no HUSKY B chapter and DSS publishes no HUSKY B manual (queue row); only the HUSKY B knowledge-base article and the 2026-03-01 income chart are held',
                  'us-ny': 'NYSDOH publishes no Child Health Plus eligibility manual and 10 NYCRR is vendor-hosted (queue row); only the Eligibility and Cost page is held'}

ECFR_INDEX = 'https://www.ecfr.gov/api/versioner/v1/structure/2026-09-09/title-42.json'
USC_INDEX = 'https://uscode.house.gov/view.xhtml?path=/prelim@title42/chapter7/subchapter19&edition=prelim'
MSPA_INDEX = 'https://www.medicaid.gov/medicaid/medicaid-state-plan-amendments'
CSPA_INDEX = 'https://www.medicaid.gov/chip/state-program-information/chip-state-plan-amendments'
CPLAN_INDEX = 'https://www.medicaid.gov/chip/state-program-information'
MAP_NAMES = {'us-dc': 'district-of-columbia'}

def norm(p): return p.replace('–', '-').replace('—', '-')

def load_index(corpus, selector):
    sel = json.load(open(selector))['scopes'] + [{'jurisdiction': 'us', 'document_class': 'regulation', 'version': '2026-09-11-title-42-part-436'}]
    idx = collections.defaultdict(list); fed = {}; loaded = collections.defaultdict(list)
    for s in sel:
        j, v, dc = s['jurisdiction'], s['version'], s['document_class']
        if j == 'us':
            if not re.search(r'medicaid|chip|435|436|457|1397|title-42|42-cfr|cms-2454|recovery|ssi-title-xvi', v, re.I): continue
        elif j in STATES:
            if not (PROG_VER.search(v) or v in POINTER.get(j, [])): continue
        else:
            continue
        f = f'{corpus}/data/corpus/provisions/{j}/{dc}/{v}.jsonl'
        if not os.path.exists(f): print('missing scope file', f, file=sys.stderr); continue
        n = 0
        for line in open(f):
            r = json.loads(line); b = r.get('body') or ''
            if not b.strip(): continue
            cp = r['citation_path']; n += 1
            if j == 'us': fed.setdefault(norm(cp), (v, cp)); continue
            idx[j].append((v, dc, cp, r.get('heading') or '', b))
        loaded[j].append((dc, v, n))
    return idx, fed, loaded

def load_queue(path):
    d = yaml.safe_load(open(path)); rows = {}
    for r in d['states']:
        fams = r.get('index_families') or {}
        untaken = []
        for k, v in fams.items():
            if isinstance(v, dict):
                if v.get('found', 0) > v.get('taken', 0): untaken.append(f"{k} ({v['found']-v['taken']} of {v['found']} not taken)")
            elif isinstance(v, int) and not k.startswith(('obsolete', 'repealed', 'faq', 'glossary', 'welcome', 'archive', 'privacy', 'program_web_page')):
                untaken.append(f'{k} ({v} listed in the index; the run took {r.get("taken_count")} documents in all)')
        rows[r['jurisdiction']] = dict(status=r.get('queue_status'), index_url=r.get('index_url'), primary=r.get('primary_source_url'),
            version=(r.get('target_scope') or {}).get('version'), dc=(r.get('target_scope') or {}).get('document_class'),
            untaken=untaken, idx=r.get('index_document_count'), taken=r.get('taken_count'), notes=(r.get('notes') or ''), pointer=r.get('pointer'), name=r.get('name'))
    return rows

STATUTE_PATHS = {
 'M-ST-1396a-a10':['us/statute/42/1396a/a/10'], 'M-ST-1396a-a17':['us/statute/42/1396a/a/17'], 'M-ST-1396a-a34':['us/statute/42/1396a/a/34'],
 'M-ST-1396a-a47':['us/statute/42/1396a/a/47','us/statute/42/1396r-1'], 'M-ST-1396a-e12':['us/statute/42/1396a/e/12'], 'M-ST-1396a-e14':['us/statute/42/1396a/e/14'],
 'M-ST-1396a-e16':['us/statute/42/1396a/e/16'], 'M-ST-1396a-k':['us/statute/42/1396a/k'], 'M-ST-1396a-l':['us/statute/42/1396a/l'], 'M-ST-1396a-m':['us/statute/42/1396a/m'],
 'M-ST-1396a-xx':['us/statute/42/1396a/xx'], 'M-ST-1396a-f':['us/statute/42/1396a/f'], 'M-ST-1396b-v':['us/statute/42/1396b/v'], 'M-ST-1396d-a':['us/statute/42/1396d/a'],
 'M-ST-1396d-n':['us/statute/42/1396d/n'], 'M-ST-1396d-p':['us/statute/42/1396d/p'], 'M-ST-1396d-b-y':['us/statute/42/1396d/b','us/statute/42/1396d/y'], 'M-ST-1396o':['us/statute/42/1396o','us/statute/42/1396o-1'],
 'M-ST-1396p-c':['us/statute/42/1396p/c'], 'M-ST-1396p-b':['us/statute/42/1396p/b'], 'M-ST-1396p-d':['us/statute/42/1396p/d'], 'M-ST-1396p-f':['us/statute/42/1396p/f'],
 'M-ST-1396r-5':['us/statute/42/1396r-5'], 'M-ST-1396r-6':['us/statute/42/1396r-6'], 'M-ST-1396u-1':['us/statute/42/1396u-1'], 'M-ST-1396a-a10Aii-buyin':['us/statute/42/1396a/a/10'],
 'M-ST-1320b-7':['us/statute/42/1320b-7'], 'M-ST-1382':['us/statute/42/1382','us/statute/42/1382c'], 'M-ST-8usc-1611':['us/statute/8/1641','us/statute/8/1612','us/statute/8/1613','us/statute/8/1611'], 'M-ST-1315':['us/statute/42/1315'],
 'M-ST-1396a-a3':['us/statute/42/1396a/a/3'], 'M-ST-1396a-a25':['us/statute/42/1396a/a/25'],
 'C-ST-1397aa':['us/statute/42/1397aa'], 'C-ST-1397bb':['us/statute/42/1397bb'], 'C-ST-1397cc':['us/statute/42/1397cc'], 'C-ST-1397dd':['us/statute/42/1397dd'], 'C-ST-1397ee':['us/statute/42/1397ee'],
 'C-ST-1397ff':['us/statute/42/1397ff'], 'C-ST-1397gg':['us/statute/42/1397gg'], 'C-ST-1397hh':['us/statute/42/1397hh'], 'C-ST-1397ii':['us/statute/42/1397ii'], 'C-ST-1397jj-b':['us/statute/42/1397jj/b'],
 'C-ST-1397jj-c':['us/statute/42/1397jj/c'], 'C-ST-1397kk':['us/statute/42/1397kk'], 'C-ST-1397ll':['us/statute/42/1397ll'], 'C-ST-1397mm':['us/statute/42/1397mm'], 'C-ST-FCEP':['us/regulation/42/457/10'],
}

def snippet(b, m, n=150):
    s = max(0, m.start()-60); t = b[s:s+n].replace('\n', ' ').replace('\r', ' ')
    return re.sub(r'\s+', ' ', t).strip()

def federal_row(e, fed):
    cid = e['id']; cite = e['federal_citation']
    if e.get('cfr_path'):
        p = e['cfr_path']
        if p in fed:
            v, cp = fed[p]; return ('PRESENT', v, cp, f'federal regulation text held ({cite})', 'federal regulation (eCFR)')
        if e.get('ecfr_missing'):
            return ('EXTRACTABLE', '', '', f'42 CFR part 447 is not in the corpus; eCFR structure 2026-09-09 lists {cite}; index {ECFR_INDEX}; take with extract-ecfr --only-title 42 --only-part 447', 'federal regulation (eCFR)')
        return ('REVIEW', '', '', f'{cite} not found in the selected federal scopes', 'federal regulation (eCFR)')
    if cid in STATUTE_PATHS:
        for p in STATUTE_PATHS[cid]:
            hit = [k for k in fed if k == p or k.startswith(p+'/')]
            if hit:
                v, cp = fed[sorted(hit, key=len)[0]]
                extra = ' (8 U.S.C. 1612, 1613, 1641 held; 1611 not held)' if cid == 'M-ST-8usc-1611' else ''
                return ('PRESENT', v, cp, f'federal statute text held ({cite}){extra}', 'federal statute (uscode.house.gov)')
        return ('EXTRACTABLE', '', '', f'{cite} not held (the Medicaid statute scope holds only 1396a(a)(10), (e), (f), (l), (m); 1396b(f), (v); 1396d(a), (n), (p), (q); 1396p(f); 1396u-1; the PL 119-21 scope holds 1396a(xx)); publisher index {USC_INDEX}', 'federal statute (uscode.house.gov)')
    if e.get('fallback') and not e.get('no_fallback'):
        p = e['fallback']
        if p in fed:
            v, cp = fed[p]; return ('PRESENT', v, cp, 'CMS compilation carries every state (state decisions as of 2023-12-01)', 'CMS compilation (medicaid.gov)')
    return ('NOT_APPLICABLE', '', '', 'state-level element; no federal document carries it', 'n/a')

def search(pats, rows, chipctx, needs_number, neg):
    """Best hit: (score, tier, version, citation_path, pattern, snippet, toc, numok); tier in {strong, weak}."""
    best = None
    for tier, plist in (('strong', pats['strong']), ('weak', pats['weak'])):
        for v, dc, cp, h, b in rows:
            for p in plist:
                m = p.search(h) or p.search(b)
                if not m: continue
                inhead = bool(p.search(h))
                src = h if inhead else b
                win = src[max(0, m.start()-120): m.end()+120]
                if neg and neg.search(win) and not PROGCTX.search(win): continue
                if chipctx and 'chip' not in v:
                    if not (CHIPCTX.search(h) or CHIPCTX.search(b[max(0, m.start()-600): m.end()+600])): continue
                toc = bool(TOC.search(h) or TOC.search(cp) or b.count('.....') >= 3)
                numok = (not needs_number) or bool(NUM.search(b))
                score = (3 if tier == 'strong' else 0) + (2 if numok else 0) + (2 if not toc else 0) + (1 if inhead else 0) + (1 if 200 <= len(b) <= 40000 else 0)
                if best is None or score > best[0]:
                    best = (score, tier, v, cp, p.pattern, snippet(src, m), toc, numok)
        if best and best[1] == 'strong' and not best[6] and best[7]: break
    return best

def state_row(prog, e, pats, j, rows, mq, cq, spa, covmap, fed):
    level = e['level']
    if e.get('territories_only'): return ('NOT_APPLICABLE', '', e['cfr_path'], 'part 436 governs GU/PR/VI only; not applicable to the 50 states and DC')
    if level == 'federal_only':
        cp = e.get('cfr_path') or (STATUTE_PATHS.get(e['id']) or [''])[0]
        return ('INHERITED', '', cp, f"federal-only element ({e['federal_citation']}); carried at the us row and inherited")
    q = cq if prog == 'chip' else mq
    # a CHIP row done by pointer into the Medicaid scope follows the Medicaid row's block state and untaken families
    if prog == 'chip' and cq.get('status') == 'done' and mq:
        q = dict(cq, untaken=mq.get('untaken') or [], index_url=mq.get('index_url') or cq.get('index_url'), status=mq.get('status') if mq.get('status') == 'blocked_primary_source' else cq.get('status'))
    blocked = q.get('status') == 'blocked_primary_source'
    if e.get('state_plan'):
        if e['id'].startswith('C-') or 'CHIP' in e['carrying_family_state']:
            return ('EXTRACTABLE', '', '', f"family: {e['carrying_family_state']}; not held for any state; index {CPLAN_INDEX}")
        return ('EXTRACTABLE', '', '', f"family: {e['carrying_family_state']}; not held for any state; index {MSPA_INDEX}")
    if e.get('spa'):
        if spa.get(j):
            ids = sorted({p.split('/')[5] for p in spa[j]})
            return ('PRESENT', '2026-07-05-cms-chip-fcep-spa', spa[j][0], f"CHIP SPA documents held: {', '.join(ids)} (SPAs on record, not the compiled plan)")
        return ('EXTRACTABLE', '', '', f"no CHIP SPA held for this state; CMS CHIP SPA index {CSPA_INDEX} lists every state's SPAs")
    chipctx = bool(e.get('chip_context') and prog == 'chip')
    neg = re.compile(e['neg_context'], re.I) if e.get('neg_context') else None
    best = search(pats, rows, chipctx, bool(e.get('needs_number')), neg)
    searched = f"searched {len(rows)} provisions in {STATE_NAMES.get(j, j)}'s program and pointer scopes"
    if best:
        score, tier, v, cp, pat, snip, toc, numok = best
        if tier == 'strong' and not toc and numok:
            return ('PRESENT', v, cp, f"strong pattern /{pat[:50]}/ matched: '{snip}'")
        why = 'only a table-of-contents provision matched' if toc else ('no value signal (percent of FPL or dollar amount) in the matched provision' if not numok else 'weak (candidate) pattern matched')
        return ('REVIEW', v, cp, f"{why}; /{pat[:50]}/: '{snip}' (candidate, needs reading)")
    if e.get('coverage_map'):
        name = MAP_NAMES.get(j, STATE_NAMES.get(j, '').lower().replace(' ', '-'))
        if name in covmap:
            cp, body = covmap[name]
            if e['id'] == 'C-ST-FCEP':
                elect = 'elects the FCEP option' if re.search(r'FCEP|unborn|conception', body, re.I) else 'records no FCEP election'
                return ('PRESENT', '2026-07-05-cms-chip-children-coverage-map', cp, f"state text not found ({searched}); CMS CHIP children-coverage map record {elect}: '{body[:100]}'")
            return ('PRESENT', '2026-07-05-cms-chip-children-coverage-map', cp, f"state text not found ({searched}); CMS coverage map record carries the state's program type: '{body[:100]}'")
    fb = ''
    if e.get('fallback') and e['fallback'] in fed:
        v, cp = fed[e['fallback']]
        if not e.get('no_fallback'):
            return ('PRESENT', v, cp, f"state's own text not found ({searched}); carried only by the CMS Medicaid/CHIP/BHP eligibility-levels compilation (state decisions as of 2023-12-01; stale for 2026)")
        fb = f'; the CMS eligibility-levels compilation ({cp}, 2023-12-01 values) is the only held source and does not satisfy a current-year table'
    if blocked:
        return ('OUTREACH', '', '', f"publisher block recorded in the {prog} queue row ({q.get('status')}); {searched}{fb}: {q.get('notes','')[:200]}")
    if e.get('absent_note'):
        return ('ABSENT', '', '', f"no community-engagement text in the held {STATE_NAMES.get(j)} documents ({searched}); {e['absent_note']}; no state has posted implementing rules")
    untaken = q.get('untaken') or []
    plan = e.get('plan_family')
    if q.get('status') == 'needs_review' or (q.get('taken') in (0, None) and q.get('status') != 'done'):
        return ('EXTRACTABLE', '', '', f"no {prog} document taken for this state ({searched}); publisher lists: {'; '.join(untaken or ['(index inventoried, not extractable through the generic path)'])}; index {q.get('index_url')}" + (f'; also carried by {plan}' if plan else '') + fb)
    if prog == 'chip' and j in CHIP_NO_MANUAL and not plan:
        return ('ABSENT', '', '', f"{CHIP_NO_MANUAL[j]}; {searched}{fb}")
    if plan:
        return ('EXTRACTABLE', '', '', f"not found in held text ({searched}); carried by {plan}" + (f"; untaken publisher families: {'; '.join(untaken)[:200]}; index {q.get('index_url')}" if untaken else '') + fb)
    if untaken:
        return ('EXTRACTABLE', '', '', f"not found in held text ({searched}); publisher index lists untaken families: {'; '.join(untaken)[:300]}; index {q.get('index_url')}{fb}")
    where = f"every inventoried family on {q.get('index_url')} was taken" if q.get('index_url') else 'the program text is a done-by-pointer scope with no separate index inventory'
    return ('REVIEW', '', '', f"no keyword hit ({searched}); {where}, so the state either does not elect this element or its text uses other terms{fb}")

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--corpus', required=True); ap.add_argument('--out', required=True); ap.add_argument('--program', default='both'); a = ap.parse_args()
    t0 = time.time()
    selector = f'{a.corpus}/docs/ingest-runs/2026-09-11-us-rulespec-program-ingestion-union.selector.json'
    idx, fed, loaded = load_index(a.corpus, selector)
    mq = load_queue(f'{a.corpus}/manifests/medicaid-agent-queue.yaml'); cq = load_queue(f'{a.corpus}/manifests/chip-agent-queue.yaml')
    for j in STATES: STATE_NAMES[j] = (mq.get(j) or cq.get(j) or {}).get('name', j)
    spa = collections.defaultdict(list)
    for line in open(f'{a.corpus}/data/corpus/provisions/us/policy/2026-07-05-cms-chip-fcep-spa.jsonl'):
        r = json.loads(line); p = r['citation_path'].split('/')
        if len(p) >= 7 and p[6] == 'summary': spa['us-'+p[4]].append(r['citation_path'])
    covmap = {}
    for line in open(f'{a.corpus}/data/corpus/provisions/us/form/2026-07-05-cms-chip-children-coverage-map.jsonl'):
        r = json.loads(line)
        if r['kind'] == 'record': covmap[r['citation_path'].split('/')[-1]] = (r['citation_path'], r.get('body') or '')
    print('index loaded', sum(len(v) for v in idx.values()), 'state rows;', len(fed), 'federal paths;', round(time.time()-t0, 1), 's', file=sys.stderr)
    with open(f'{a.out}/tools/search-universe.json', 'w') as f: json.dump({j: loaded[j] for j in STATES}, f, indent=1)
    programs = ['medicaid', 'chip'] if a.program == 'both' else [a.program]
    for prog in programs:
        t1 = time.time()
        schema = yaml.safe_load(open(f'{a.out}/{prog}-schema.yaml'))
        rows = []; log = collections.Counter()
        for e in schema['elements']:
            pats = {'strong': [re.compile(p, re.I) for p in e.get('search_patterns') or []], 'weak': [re.compile(p, re.I) for p in e.get('weak_patterns') or []]}
            st, v, cp, note, fam = federal_row(e, fed)
            rows.append(['us', e['id'], e['level'], fam, st, v, cp, e['pe_modeled'], note]); log[('us', st)] += 1
            for j in STATES:
                r = state_row(prog, e, pats, j, idx.get(j, []), mq.get(j, {}), cq.get(j, {}), spa, covmap, fed)
                rows.append([j, e['id'], e['level'], e['carrying_family_state'], r[0], r[1], r[2], e['pe_modeled'], r[3]]); log[(prog, r[0])] += 1
        with open(f'{a.out}/{prog}-matrix.csv', 'w', newline='') as f:
            w = csv.writer(f); w.writerow(['jurisdiction', 'element', 'level', 'family', 'status', 'scope_version', 'citation_path', 'pe_modeled', 'evidence_note']); w.writerows(rows)
        print(prog, len(rows), 'rows', dict(log), round(time.time()-t1, 1), 's', file=sys.stderr)
    print('total', round(time.time()-t0, 1), 's', file=sys.stderr)

if __name__ == '__main__':
    main()
