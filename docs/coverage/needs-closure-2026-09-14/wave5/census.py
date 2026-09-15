import json, csv, re, glob, pathlib, collections, statistics
BASE=pathlib.Path("/Users/pavelmakarchuk/axiom-corpus/data/corpus/provisions")
sel={(s["jurisdiction"],s["document_class"],s["version"]) for s in json.load(open("manifests/releases/us-rulespec-2026-09-14-wave4-r2-union.json"))["scopes"]}
for p in BASE.glob("*/*/2026-09-15-*.jsonl"): sel.add((p.parts[-3],p.parts[-2],p.stem))
def rows(key):
    p=BASE/key[0]/key[1]/(key[2]+".jsonl")
    if not p.exists(): return []
    out=[]
    for l in p.open():
        try: r=json.loads(l)
        except Exception: continue
        out.append(r)
    return out
def norm(cp): return cp.replace("–","-").replace("—","-")
# ---- federal: dedupe body-bearing paths across all selected us/statute + us/regulation scopes
fed=set(); fed_other=collections.Counter(); fedmark={}
PM=re.compile(r"(?m)^\s*\((?:[a-z]{1,2}|\d{1,2}|[ivx]{1,4})\)")
for key in sorted(sel):
    if key[0]!="us": continue
    if key[1] in ("statute","regulation"):
        for r in rows(key):
            b=r.get("body") or ""
            if b.strip():
                cp=norm(r["citation_path"]); fed.add(cp); fedmark[cp]=max(fedmark.get(cp,0), len(PM.findall(b)))
    else:
        n=sum(1 for r in rows(key) if (r.get("body") or "").strip()); fed_other[key[1]]+=n
def secnum(s):
    m=re.match(r"(\d+)([A-Za-z]*)(?:-(\d+))?$", s); return (int(m.group(1)), m.group(2), int(m.group(3) or 0)) if m else None
def in_range(s, lo, hi, prefixes=()):
    n=secnum(s)
    if prefixes and any(re.match(p+"$", s) for p in prefixes): return True
    return bool(n) and lo<=n[0]<=hi
PROG={
 "SNAP":     dict(st=[("7",2011,2036,())], reg=[("7",set(range(271,286)))]),
 "Medicaid": dict(st=[("42",1396,1396,(r"1396[a-z0-9-]*",))], reg=[("42",set(range(430,457)))]),
 "CHIP":     dict(st=[("42",1397,1397,(r"1397[a-m][a-m]",))], reg=[("42",{457})]),
 "TANF":     dict(st=[("42",601,619,())], reg=[("45",set(range(260,266)))]),
 "CCDF":     dict(st=[("42",9857,9858,(r"985[78][a-z0-9-]*",))], reg=[("45",{98})]),
 "LIHEAP":   dict(st=[("42",8621,8630,())], reg=[("45",{96})]),
 "WIC":      dict(st=[("42",1786,1786,())], reg=[("7",{246})]),
 "SSI":      dict(st=[("42",1381,1383,(r"138[123][a-z0-9-]*",))], reg=[("20",{416})]),
 "Medicare": dict(st=[("42",426,426,(r"426[a-z0-9-]*",r"1395[a-z0-9-]*",))], reg=[("42",set(range(400,430)))]),
 "UI":       dict(st=[("26",3301,3311,()),("42",501,504,()),("42",1101,1110,())], reg=[("20",set(range(601,700)))]),
 "Income tax": dict(st=[("26",1,1400,(r"1400[A-Z]*(-\d+)?",))], reg=[("26",{1,31})]),
 "EITC":     dict(st=[("26",32,32,())], reg=[("26",{1})], regsec=r"32-\d"),
 "CTC":      dict(st=[("26",24,24,())], reg=[("26",{1})], regsec=r"24-\d"),
}
def count_fed(cfg):
    st_secs=set(); reg_secs=set(); paras=0; marks=0
    for cp in fed:
        seg=cp.split("/")
        if seg[1]=="statute" and len(seg)>=4:
            for t,lo,hi,pre in cfg["st"]:
                if seg[2]==t and in_range(seg[3],lo,hi,pre):
                    st_secs.add(seg[3]); paras+=1; marks+=fedmark.get(cp,0); break
        elif seg[1]=="regulation" and len(seg)>=5:
            for t,parts in cfg["reg"]:
                if seg[2]==t and seg[3].isdigit() and int(seg[3]) in parts:
                    if cfg.get("regsec") and not re.match(cfg["regsec"], seg[4]): continue
                    reg_secs.add((seg[3],seg[4])); paras+=1; marks+=fedmark.get(cp,0); break
    return len(st_secs), len(reg_secs), paras, marks
# ---- state: scopes cited by each program's matrix (folded), body rows per jurisdiction
MAT={"SNAP":"snap","Medicaid":"medicaid","CHIP":"chip","TANF":"tanf","CCDF":"ccdf","LIHEAP":"liheap","WIC":"wic","SSI":"ssi","Medicare":"medicare","Income tax":"tax"}
scope_rows_cache={}
def body_rows(key):
    if key not in scope_rows_cache: scope_rows_cache[key]=[r for r in rows(key) if (r.get("body") or "").strip()]
    return scope_rows_cache[key]
state_stats={}; tax_scopes_by_jur=collections.defaultdict(set)
for prog,m in MAT.items():
    cited=collections.defaultdict(set); citedpaths=collections.defaultdict(set)
    for r in csv.DictReader(open(f"docs/coverage/needs-closure-2026-09-14/{m}-matrix.csv")):
        if r["jurisdiction"]=="us" or r["status"]!="PRESENT" or not r["scope_version"]: continue
        sv=r["scope_version"]; parts=sv.split("/"); cp=r["citation_path"].split("/")
        key=tuple(parts) if len(parts)==3 else ((cp[0],cp[1],sv) if len(cp)>2 else None)
        if key and key[0]!="us": cited[key[0]].add(key); citedpaths[key[0]].add(norm(r["citation_path"]))
    per={}; rel={}
    for jur,keys in cited.items():
        paths=set()
        for k in keys:
            for r in body_rows(k): paths.add(norm(r["citation_path"]))
        per[jur]=len(paths)
        cps=citedpaths[jur]; rel[jur]=sum(1 for p in paths if p in cps or any(p.startswith(c+"/") for c in cps))
        if prog=="Income tax": tax_scopes_by_jur[jur]|=keys
    vals=list(per.values()); rv=list(rel.values())
    state_stats[prog]=(len(per), round(statistics.mean(vals)) if vals else 0, round(statistics.median(vals)) if vals else 0, sum(vals), round(statistics.mean(rv)) if rv else 0)
# EITC / CTC state rows: tax scopes' rows mentioning the credit
for prog,rx in (("EITC", r"earned[- ]income (tax )?credit"),("CTC", r"child (and dependent care )?tax credit|child tax credit|credit for (each )?(qualifying|dependent) child")):
    per={}
    for jur,keys in tax_scopes_by_jur.items():
        n=0
        for k in keys:
            n+=sum(1 for r in body_rows(k) if re.search(rx, r["body"], re.I))
        if n: per[jur]=n
    vals=list(per.values()); state_stats[prog]=(len(per), round(statistics.mean(vals)) if vals else 0, round(statistics.median(vals)) if vals else 0, sum(vals), round(statistics.mean(vals)) if vals else 0)
state_stats["UI"]=(0,0,0,0,0)
print("| Program | Fed statute sections | Fed reg sections | Fed body rows | Fed paragraph markers | Jurisdictions | State rows/jur: cited sections+descendants (mean) | State rows/jur: whole cited scopes (mean) | (median) |")
print("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
for prog,cfg in PROG.items():
    a,b,c,m=count_fed(cfg); j,mean,med,tot,relm=state_stats.get(prog,(0,0,0,0,0))
    print(f"| {prog} | {a:,} | {b:,} | {c:,} | {m:,} | {j} | {relm:,} | {mean:,} | {med:,} |")
print("\nOther federal body rows held (all programs, by class):", dict(fed_other))
