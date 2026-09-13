"""Needs-closure check: one CSV row per (jurisdiction, element) for Medicaid and CHIP.

Read-only over data/corpus. Usage:
  python3 build_matrix.py --corpus /path/to/axiom-corpus --out docs/coverage/needs-closure-2026-09-11 [--program medicaid|chip]

Statuses:
  PRESENT        a specific provision in a selected scope carries the element (cited)
  EXTRACTABLE    publisher lists the carrying family; not taken (family and index URL named)
  ABSENT         publisher posts nothing carrying it (what was checked is in evidence_note)
  OUTREACH       the queue row records a publisher block
  REVIEW         cannot tell from the corpus (candidate cited when a low-confidence match exists)
  INHERITED      federal-only element; carried once at the federal row and inherited by the state
  NOT_APPLICABLE part 436 (GU/PR/VI only) at the state level; state-only structure elements at the federal level
"""
from __future__ import annotations
import argparse, csv, json, os, re, sys, time, collections
import yaml

STATES = ['us-'+s for s in 'ak al ar az ca co ct dc de fl ga hi ia id il in ks ky la ma md me mi mn mo ms mt nc nd ne nh nj nm nv ny oh ok or pa ri sc sd tn tx ut va vt wa wi wv wy'.split()]
STATE_NAMES = {}
CTX = re.compile(r'medicaid|medical assistance|\bchip\b|children.s health|kidcare|husky|medi-cal|masshealth|badgercare|apple health|soonercare|tenncare|healthnet|ahcccs|denali|hawk-i|peachcare|famis|healthy steps|dynasaur|all kids|child health plus|medquest|\bquest\b|mainecare|healthy connections|health first colorado|medi-?cal|ohp\b|oregon health plan|husky|nj familycare|hoosier healthwise|healthy montana|coverkids|arkids|michild|mchp|chp\+|nevada check up|wvchip|kchip|lachip|cubcare|kid care|title xix|title xxi|1902|435\.', re.I)
CHIPCTX = re.compile(r'\bchip\b|\bs-?chip\b|\bm-?chip\b|title xxi|children.s health (insurance|plan)|kidcare|kid care|husky b|child health plus|peachcare|famis|all kids|hawk-i|denali kidcare|healthy steps|dynasaur|nevada check up|coverkids|cub ?care|healthy montana kids|arkids (first-?)?b|michild|mchp|maryland children.s health|chp\+|child health plan plus|florida kidcare|healthy kids|badgercare plus|wvchip|kchip|lachip|hoosier healthwise|package c|mo healthnet for kids|nj familycare|apple health for kids|partners for healthy children|health first colorado|sooner ?care|kancare|alabama.s health|delaware healthy children|dr\. dynasaur|1397|457\.|targeted low.income', re.I)
SKIP_VER = re.compile(r'(tax|pit|income-tax|hts|tariff|usitc|irs|1040|estimate|surtax|rate-notice|rate-determination|k40es|it-511|n11|540|it-540|1-es|form1|740-es|hb96|snap-fy|abawd|alien-eligibility|cola|wic|ccdf|liheap|medicare|ssi-poms|kindergeld|canada|hr6644|title-19|title-26|title-7|title-45|title-20|title-47|oasdi|doe-rebates|title-12|title-15|title-38|usc-26)', re.I)

def norm(p): return p.replace('–','-').replace('—','-')

def load_index(corpus, selector):
    sel = json.load(open(selector))['scopes'] + [{'jurisdiction':'us','document_class':'regulation','version':'2026-09-11-title-42-part-436'}]
    idx = collections.defaultdict(list); fed = {}
    for s in sel:
        j, v, dc = s['jurisdiction'], s['version'], s['document_class']
        if j != 'us' and j not in STATES: continue
        if SKIP_VER.search(v) and not re.search(r'medicaid|chip|435|436|457|1397|title-42', v, re.I): continue
        f = f'{corpus}/data/corpus/provisions/{j}/{dc}/{v}.jsonl'
        if not os.path.exists(f): print('missing scope file', f, file=sys.stderr); continue
        for line in open(f):
            r = json.loads(line); b = r.get('body') or ''
            cp = r['citation_path']
            if j == 'us':
                if b.strip(): fed.setdefault(norm(cp), (v, cp))
                continue
            if b.strip(): idx[j].append((v, dc, cp, r.get('heading') or '', b))
    return idx, fed

def load_queue(path):
    d = yaml.safe_load(open(path)); rows = {}
    for r in d['states']:
        fams = r.get('index_families') or {}
        untaken = []
        for k, v in fams.items():
            if isinstance(v, dict):
                if v.get('found', 0) > v.get('taken', 0): untaken.append(f"{k} ({v['found']-v['taken']} of {v['found']} not taken)")
            else: untaken.append(f'{k} ({v} listed)')
        rows[r['jurisdiction']] = dict(status=r.get('queue_status'), index_url=r.get('index_url'), primary=r.get('primary_source_url'),
            version=(r.get('target_scope') or {}).get('version'), dc=(r.get('target_scope') or {}).get('document_class'),
            untaken=untaken, idx=r.get('index_document_count'), taken=r.get('taken_count'), notes=(r.get('notes') or '')[:300], pointer=r.get('pointer'), name=r.get('name'))
    return rows

STATUTE_PATHS = {
 'M-ST-1396a-a10':['us/statute/42/1396a/a/10'], 'M-ST-1396a-a17':['us/statute/42/1396a/a/17'], 'M-ST-1396a-a34':['us/statute/42/1396a/a/34'],
 'M-ST-1396a-a47':['us/statute/42/1396a/a/47','us/statute/42/1396r-1'], 'M-ST-1396a-e12':['us/statute/42/1396a/e/12'], 'M-ST-1396a-e14':['us/statute/42/1396a/e/14'],
 'M-ST-1396a-e16':['us/statute/42/1396a/e/16'], 'M-ST-1396a-k':['us/statute/42/1396a/k'], 'M-ST-1396a-l':['us/statute/42/1396a/l'], 'M-ST-1396a-m':['us/statute/42/1396a/m'],
 'M-ST-1396a-xx':['us/statute/42/1396a/xx'], 'M-ST-1396a-f':['us/statute/42/1396a/f'], 'M-ST-1396b-v':['us/statute/42/1396b/v'], 'M-ST-1396d-a':['us/statute/42/1396d/a'],
 'M-ST-1396d-n':['us/statute/42/1396d/n'], 'M-ST-1396d-p':['us/statute/42/1396d/p'], 'M-ST-1396d-b-y':['us/statute/42/1396d/b','us/statute/42/1396d/y'], 'M-ST-1396o':['us/statute/42/1396o','us/statute/42/1396o-1'],
 'M-ST-1396p-c':['us/statute/42/1396p/c'], 'M-ST-1396p-b':['us/statute/42/1396p/b'], 'M-ST-1396p-d':['us/statute/42/1396p/d'], 'M-ST-1396p-f':['us/statute/42/1396p/f'],
 'M-ST-1396r-5':['us/statute/42/1396r-5'], 'M-ST-1396r-6':['us/statute/42/1396r-6'], 'M-ST-1396u-1':['us/statute/42/1396u-1'], 'M-ST-1396a-a10Aii-buyin':['us/statute/42/1396a/a/10'],
 'M-ST-1320b-7':['us/statute/42/1320b-7'], 'M-ST-1382':['us/statute/42/1382','us/statute/42/1382c'], 'M-ST-8usc-1611':['us/statute/8/1641','us/statute/8/1611'], 'M-ST-1315':['us/statute/42/1315'],
 'M-ST-1396a-a3':['us/statute/42/1396a/a/3'], 'M-ST-1396a-a25':['us/statute/42/1396a/a/25'],
 'C-ST-1397aa':['us/statute/42/1397aa'], 'C-ST-1397bb':['us/statute/42/1397bb'], 'C-ST-1397cc':['us/statute/42/1397cc'], 'C-ST-1397dd':['us/statute/42/1397dd'], 'C-ST-1397ee':['us/statute/42/1397ee'],
 'C-ST-1397ff':['us/statute/42/1397ff'], 'C-ST-1397gg':['us/statute/42/1397gg'], 'C-ST-1397hh':['us/statute/42/1397hh'], 'C-ST-1397ii':['us/statute/42/1397ii'], 'C-ST-1397jj-b':['us/statute/42/1397jj/b'],
 'C-ST-1397jj-c':['us/statute/42/1397jj/c'], 'C-ST-1397kk':['us/statute/42/1397kk'], 'C-ST-1397ll':['us/statute/42/1397ll'], 'C-ST-1397mm':['us/statute/42/1397mm'], 'C-ST-FCEP':['us/regulation/42/457/10'],
}
ECFR_INDEX = 'https://www.ecfr.gov/api/versioner/v1/structure/2026-09-09/title-42.json'
USC_INDEX = 'https://uscode.house.gov/view.xhtml?path=/prelim@title42/chapter7/subchapter19&edition=prelim'
USC8_INDEX = 'https://uscode.house.gov/view.xhtml?path=/prelim@title8/chapter14&edition=prelim'
MSPA_INDEX = 'https://www.medicaid.gov/medicaid/medicaid-state-plan-amendments'
CSPA_INDEX = 'https://www.medicaid.gov/chip/state-program-information/chip-state-plan-amendments'
CPLAN_INDEX = 'https://www.medicaid.gov/chip/state-program-information'
MAP_NAMES = {'us-dc':'district-of-columbia'}

def snippet(b, m, n=150):
    s = max(0, m.start()-60); t = b[s:s+n].replace('\n',' ').replace('\r',' ')
    return re.sub(r'\s+',' ',t).strip()

def federal_row(e, fed, fed_versions):
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
                v, cp = fed[sorted(hit, key=len)[0]]; return ('PRESENT', v, cp, f'federal statute text held ({cite})', 'federal statute (uscode.house.gov)')
        if cid == 'M-ST-8usc-1611':
            return ('EXTRACTABLE', '', '', f'no title-8 statute scope in the corpus; {cite}; publisher index {USC8_INDEX}', 'federal statute (uscode.house.gov title 8)')
        return ('EXTRACTABLE', '', '', f'{cite} not held (the Medicaid statute scope holds only 1396a(a)(10),(e),(f),(l),(m),(xx), 1396b(f),(v), 1396d(a),(n),(p),(q), 1396p(f), 1396u-1); publisher index {USC_INDEX}', 'federal statute (uscode.house.gov)')
    if e.get('fallback'):
        p = e['fallback']
        if p in fed:
            v, cp = fed[p]; return ('PRESENT', v, cp, 'CMS compilation carries every state (state decisions as of 2023-12-01)', 'CMS compilation (medicaid.gov)')
    return ('NOT_APPLICABLE', '', '', 'state-level element; no federal document carries it', 'n/a')

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--corpus', required=True); ap.add_argument('--out', required=True); ap.add_argument('--program', default='both'); a = ap.parse_args()
    t0 = time.time()
    selector = f'{a.corpus}/docs/ingest-runs/2026-09-11-us-rulespec-program-ingestion-union.selector.json'
    idx, fed = load_index(a.corpus, selector)
    fedv = None
    mq = load_queue(f'{a.corpus}/manifests/medicaid-agent-queue.yaml'); cq = load_queue(f'{a.corpus}/manifests/chip-agent-queue.yaml')
    for j in STATES: STATE_NAMES[j] = (mq.get(j) or cq.get(j) or {}).get('name', j)
    # CHIP SPA docs per state
    spa = collections.defaultdict(list)
    for line in open(f'{a.corpus}/data/corpus/provisions/us/policy/2026-07-05-cms-chip-fcep-spa.jsonl'):
        r = json.loads(line); p = r['citation_path'].split('/')
        if len(p) >= 7 and p[6] == 'summary': spa['us-'+p[4]].append(r['citation_path'])
    covmap = {}
    for line in open(f'{a.corpus}/data/corpus/provisions/us/form/2026-07-05-cms-chip-children-coverage-map.jsonl'):
        r = json.loads(line)
        if r['kind'] == 'record': covmap[r['citation_path'].split('/')[-1]] = (r['citation_path'], r.get('body') or '')
    print('index loaded', sum(len(v) for v in idx.values()), 'state rows;', len(fed), 'federal paths;', round(time.time()-t0,1), 's', file=sys.stderr)
    programs = ['medicaid','chip'] if a.program == 'both' else [a.program]
    for prog in programs:
        schema = yaml.safe_load(open(f'{a.out}/{prog}-schema.yaml'))
        rows = []; log = collections.Counter()
        for e in schema['elements']:
            pats = [re.compile(p, re.I) for p in e.get('search_patterns') or []]
            st, v, cp, note, fam = federal_row(e, fed, fedv)
            rows.append(['us', e['id'], e['level'], fam, st, v, cp, note, e['pe_modeled']])
            log[('us', st)] += 1
            for j in STATES:
                r = state_row(prog, e, pats, j, idx.get(j, []), mq.get(j, {}), cq.get(j, {}), spa, covmap, fed)
                rows.append([j, e['id'], e['level'], e['carrying_family_state'], *r, e['pe_modeled']])
                log[(prog, r[0])] += 1
        with open(f'{a.out}/{prog}-matrix.csv', 'w', newline='') as f:
            w = csv.writer(f); w.writerow(['jurisdiction','element','level','family','status','scope_version','citation_path','evidence_note','pe_modeled']); w.writerows(rows)
        print(prog, len(rows), 'rows', dict(log), round(time.time()-t0,1), 's', file=sys.stderr)

def program_versions(j, mq, cq):
    vs = set()
    for q in (mq, cq):
        if q.get('version'): vs.add(q['version'])
    if j == 'us-id': vs |= {'2026-07-04-id-aabd-rules','2026-09-10-chip-state-eligibility-manual'}
    if j == 'us-or': vs.add('2026-09-10-chip-state-eligibility-manual')
    return vs

def state_row(prog, e, pats, j, rows, mq, cq, spa, covmap, fed):
    level = e['level']
    if e.get('territories_only'): return ('NOT_APPLICABLE', '', e['cfr_path'], 'part 436 governs GU/PR/VI only; not applicable to the 50 states and DC')
    if level == 'federal_only':
        cp = e.get('cfr_path') or (STATUTE_PATHS.get(e['id']) or [''])[0]
        return ('INHERITED', '', cp, f"federal-only element ({e['federal_citation']}); carried at the us row and inherited")
    q = mq if prog == 'medicaid' else cq
    if prog == 'chip' and (cq.get('status') == 'done' or not cq.get('version')) and mq: q = mq if cq.get('status') == 'done' else cq
    blocked = (cq.get('status') == 'blocked_primary_source') if prog == 'chip' else (mq.get('status') == 'blocked_primary_source')
    if prog == 'chip' and cq.get('status') == 'done': blocked = mq.get('status') == 'blocked_primary_source'
    pv = program_versions(j, mq, cq)
    # special families
    if e.get('state_plan'):
        if e['id'].startswith('C-') or 'CHIP' in e['carrying_family_state']:
            return ('EXTRACTABLE', '', '', f"family: {e['carrying_family_state']}; not held for any state; index {CPLAN_INDEX}")
        return ('EXTRACTABLE', '', '', f"family: {e['carrying_family_state']}; not held for any state; index {MSPA_INDEX}")
    if e.get('spa'):
        if spa.get(j):
            ids = sorted({p.split('/')[5] for p in spa[j]})
            return ('PRESENT', '2026-07-05-cms-chip-fcep-spa', spa[j][0], f"CHIP SPA documents held: {', '.join(ids)} (SPAs on record, not the compiled plan)")
        return ('EXTRACTABLE', '', '', f'no CHIP SPA held for this state; CMS CHIP SPA index {CSPA_INDEX} lists every state\'s SPAs')
    # keyword search
    best = None
    chipctx = e.get('chip_context') and prog == 'chip'
    for v, dc, cp, h, b in rows:
        inprog = v in pv
        for p in pats:
            m = p.search(h) or p.search(b)
            if not m: continue
            text = h + ' ' + b
            if not inprog:
                if not CTX.search(h):
                    src = h if p.search(h) else b
                    win = src[max(0, m.start()-400): m.end()+400]
                    if not CTX.search(win): continue
            if chipctx and not ('chip' in v):
                if not (CHIPCTX.search(h) or CHIPCTX.search(b[max(0, m.start()-600): m.end()+600])): continue
            score = (4 if inprog else 0) + (2 if p.search(h) else 0) + (1 if re.search('medicaid|chip', v) else 0) + (1 if 200 <= len(b) <= 40000 else 0)
            if best is None or score > best[0]:
                best = (score, v, cp, p.pattern, snippet(h if p.search(h) else b, m))
    if best:
        _, v, cp, pat, snip = best
        if e['search_confidence'] == 'high':
            return ('PRESENT', v, cp, f"pattern /{pat[:60]}/ matched: '{snip}'")
        return ('REVIEW', v, cp, f"low-confidence pattern /{pat[:60]}/ matched (candidate, needs reading): '{snip}'")
    # coverage map / fallbacks
    if e.get('coverage_map'):
        name = MAP_NAMES.get(j, STATE_NAMES.get(j, '').lower().replace(' ', '-'))
        if name in covmap:
            cp, body = covmap[name]
            return ('PRESENT', '2026-07-05-cms-chip-children-coverage-map', cp, f"state text not found; CMS coverage map record carries the state's election: '{body[:100]}'")
    if e.get('fallback') and e['fallback'] in fed:
        v, cp = fed[e['fallback']]
        return ('PRESENT', v, cp, "state's own document not found by keyword; carried only by the CMS Medicaid/CHIP/BHP eligibility-levels compilation (state decisions as of 2023-12-01; stale for 2026)")
    # gap classification
    if blocked:
        return ('OUTREACH', '', '', f"publisher block recorded in the {prog} queue row ({q.get('status')}): {q.get('notes','')[:160]}")
    if e.get('absent_note'):
        return ('ABSENT', '', '', f"no community-engagement text in the held {STATE_NAMES.get(j)} documents; {e['absent_note']}")
    if q.get('status') == 'needs_review' or (q.get('taken') in (0, None) and q.get('status') != 'done'):
        return ('EXTRACTABLE', '', '', f"no {prog} document taken for this state; publisher lists: {'; '.join(q.get('untaken') or ['(index not inventoried)'])}; index {q.get('index_url')}")
    untaken = q.get('untaken') or []
    if untaken:
        return ('EXTRACTABLE', '', '', f"not found in held text; publisher index lists untaken families: {'; '.join(untaken)[:300]}; index {q.get('index_url')}")
    return ('REVIEW', '', '', f"no keyword hit in the held text; every inventoried family on {q.get('index_url')} was taken, so the state either does not elect this element or its text uses other terms")

if __name__ == '__main__':
    main()
