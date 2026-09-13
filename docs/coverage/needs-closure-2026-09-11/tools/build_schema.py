"""Emit the law-derived needs schemas for Medicaid and CHIP.

Element = one rule element an end-to-end encoding needs. Primary source of elements: the
program's own legal structure (42 U.S.C. 1396a and the sections it invokes; 42 U.S.C.
1397aa-1397mm; every section of 42 CFR 435, 436, 447 subpart A and 457; the structure of the
state rulebooks held in the corpus). PolicyEngine and rulespec-us are recorded per element as a
cross-check only (`pe_modeled`, `rulespec`).

level: F  = federal_only (federal text sets it; states inherit; state rows are INHERITED)
       FS = federal_with_state_option (federal text sets the rule; a state elects or implements;
            the state row is checked against the state's held documents)
       S  = state (a state-set value or state-authored rule; state row checked)
conf:  high = the search pattern is specific enough that a body match counts as PRESENT;
       low  = a match is only a candidate and is reported as REVIEW.
"""
from __future__ import annotations
import sys, yaml

def E(id, title, cite, level, fam, pe, rs, pats, conf='high', notes='', **flags):
    d = dict(id=id, title=title, federal_citation=cite, level={'F':'federal_only','FS':'federal_with_state_option','S':'state'}[level],
             carrying_family_state=fam, pe_modeled=pe, rulespec=rs, search_patterns=pats, search_confidence=conf, notes=notes)
    d.update(flags)
    return d

MAN = 'state eligibility manual or codified eligibility regulation'
MAN_TAB = 'state eligibility manual appendix / annual income-level table or notice'
PLAN = 'approved Medicaid state plan (attachments 2.2-A, 2.6-A, supplements) on medicaid.gov'
CPLAN = 'approved CHIP state plan (CMS template) on medicaid.gov'
NOFAM = 'n/a (federal text only)'

# ---------------------------------------------------------------- Medicaid: statute
M = []
M += [
 E('M-ST-1396a-a10','1902(a)(10): mandatory and optional categorically needy groups, medically needy option, MSP (A)(i)-(ii), (C), (E)','42 U.S.C. 1396a(a)(10)','F',NOFAM,'partial (gov/hhs/medicaid/eligibility/categories/*)','us:statutes/42 (a/10 held; cited by state cms wrappers)',[],'high','Held as us/statute/42/1396a/a/10. Per-group elements are the 42 CFR 435 subparts B-D sections below.'),
 E('M-ST-1396a-a17','1902(a)(17): reasonable income and resource standards and methodologies; 1902(r)(2) less-restrictive methodologies','42 U.S.C. 1396a(a)(17), 1396a(r)(2)','S',MAN,'no','no',[r'less restrictive (methodolog|income|resource)|more liberal (methodolog|income|resource)|1902\(r\)\(2\)'],'high','Statute subsection not held (only 1396a(a)(10), (e), (f), (l), (m), (xx) are in the corpus). State-level: which disregards/methodologies the state elected.'),
 E('M-ST-1396a-a34','1902(a)(34): retroactive eligibility (three months before application)','42 U.S.C. 1396a(a)(34); 42 CFR 435.915','S',MAN,'no','no',[r'retroactive (medicaid|coverage|eligibility|period|month)|three months? (prior|before|preceding)|3 months? (prior|before|preceding)'],'high','Statute subsection not held. Several states limit retroactive coverage under 1115 demonstrations.'),
 E('M-ST-1396a-a47','1902(a)(47), 1920, 1920A, 1920B, 1920C: presumptive eligibility authority','42 U.S.C. 1396a(a)(47), 1396r-1, 1396r-1a, 1396r-1b, 1396r-1c','F',NOFAM,'no','no',[],'high','Not held. State elections are elements 435.1102, 435.1103, 435.1110.'),
 E('M-ST-1396a-e12','1902(e)(12): 12-month continuous eligibility for children (mandatory from 2024-01-01)','42 U.S.C. 1396a(e)(12); 42 CFR 435.926','F',NOFAM,'no','no',[],'high','Held (us/statute/42/1396a/e/12). State implementation is element 435.926.'),
 E('M-ST-1396a-e14','1902(e)(14): MAGI income determination, 5-percentage-point disregard','42 U.S.C. 1396a(e)(14); 42 CFR 435.603','F',NOFAM,'yes (gov/hhs/medicaid/income/*, household/*)','us:policies/medicaid/magi_household_income_pipeline',[],'high','Held (us/statute/42/1396a/e/14).'),
 E('M-ST-1396a-e16','1902(e)(16): 12-month postpartum coverage option','42 U.S.C. 1396a(e)(16); 42 CFR 435.170','F',NOFAM,'yes (categories/pregnant/postpartum_coverage)','no',[],'high','Held. State election is element 435.170.'),
 E('M-ST-1396a-k','1902(k) and 1902(a)(10)(A)(i)(VIII): adult group (expansion) and benchmark benefits','42 U.S.C. 1396a(k); 42 CFR 435.119','F',NOFAM,'yes (categories/adult/*)','us-xx cms eligibility-levels wrappers (expansion flag)',[],'high','1396a(k) not held (a(10) is). State election is element 435.119.'),
 E('M-ST-1396a-l','1902(l): poverty-level pregnant women, infants and children; income levels','42 U.S.C. 1396a(l); 42 CFR 435.116, 435.118','F',NOFAM,'yes','yes',[],'high','Held (us/statute/42/1396a/l).'),
 E('M-ST-1396a-m','1902(m): optional poverty-level aged and disabled group (100% FPL)','42 U.S.C. 1396a(m)','S',MAN,'partial (categories/senior_or_disabled/*)','no',[r'poverty.level (aged|disabled|elderly)|100 ?(%|percent) (of the )?(FPL|federal poverty).{0,80}(aged|disabled|65)|(aged|disabled).{0,80}100 ?(%|percent) (of the )?(FPL|federal poverty)'],'low','Held (us/statute/42/1396a/m). No 42 CFR 435 section implements it; the state election appears only in the state plan and manual.'),
 E('M-ST-1396a-xx','1902(xx): community engagement requirement (P.L. 119-21 sec. 71119)','42 U.S.C. 1396a(xx); 42 CFR 435.550-435.563','F',NOFAM,'yes (eligibility/work_requirements/*, variables *community_engagement*)','no',[],'high','Held (us/statute/42/1396a/xx and the CMS-2454-IFC scope). State implementation is elements 435.551-435.561.'),
 E('M-ST-1396a-f','1902(f): states using more restrictive standards than SSI (209(b))','42 U.S.C. 1396a(f); 42 CFR 435.121','F',NOFAM,'yes (ssi_recipient/classification/section_209b)','no',[],'high','Held (us/statute/42/1396a/f).'),
 E('M-ST-1396b-v','1903(v): emergency medical assistance for noncitizens not lawfully admitted','42 U.S.C. 1396b(v); 42 CFR 435.139, 435.406','S',MAN,'yes (emergency_medicaid/*)','no',[r'emergency medical (assistance|services|condition)|emergency medicaid|emergency (services )?(for|to) (non-?citizens|aliens|undocumented)|\bEMA\b|alien emergency'],'high','Held (us/statute/42/1396b/v).'),
 E('M-ST-1396d-a','1905(a): medical assistance (benefit) definition','42 U.S.C. 1396d(a)','F',NOFAM,'no','no',[],'high','Held. The state benefit package is element M-SS-BENEFITS.'),
 E('M-ST-1396d-n','1905(n): qualified pregnant woman or child','42 U.S.C. 1396d(n)','F',NOFAM,'no','no',[],'high','Held.'),
 E('M-ST-1396d-p','1905(p): qualified Medicare beneficiary; Medicare cost-sharing; MSP resource standards','42 U.S.C. 1396d(p); 42 CFR 435.123-435.126','F',NOFAM,'no','no',[],'high','Held. State implementation is elements 435.123-435.126.'),
 E('M-ST-1396d-b-y','1905(b), (y), (z): FMAP, expansion FMAP','42 U.S.C. 1396d(b), (y), (z)','F',NOFAM,'yes (cost_share/fmap, expansion_fmap)','no',[],'high','Not held (only 1396d(a), (n), (p), (q) are). Financing, not eligibility.'),
 E('M-ST-1396o','1916, 1916A: premiums and cost sharing','42 U.S.C. 1396o, 1396o-1; 42 CFR 447.50-447.57','F',NOFAM,'no','no',[],'high','Not held. State elections are elements 447.52-447.57.'),
 E('M-ST-1396p-c','1917(c): transfers of assets for less than fair market value; look-back period; penalty period','42 U.S.C. 1396p(c)','S',MAN,'no','no',[r'transfer of (assets|resources|property)|look-?back period|penalty period|uncompensated (transfer|value)'],'high','Not held (only 1396p(f)). State-set: penalty divisor, hardship waiver.'),
 E('M-ST-1396p-b','1917(b): estate recovery','42 U.S.C. 1396p(b)','S',MAN,'no','no',[r'estate recovery|recover(y|ed) from the estate|estate claim'],'high','Not held.'),
 E('M-ST-1396p-d','1917(d): treatment of trusts (including special needs and pooled trusts; qualified income trusts)','42 U.S.C. 1396p(d)','S',MAN,'no','no',[r'special needs trust|pooled trust|qualified income trust|miller trust|treatment of trusts|trust(s)? (established|created).{0,60}(medicaid|assets)'],'high','Not held.'),
 E('M-ST-1396p-f','1917(f): home equity limit for long-term care eligibility','42 U.S.C. 1396p(f)','S',MAN,'yes (long_term_care/home_equity/*)','no',[r'home equity'],'high','Held (us/statute/42/1396p/f). State-set: the elected limit between the federal floor and ceiling.'),
 E('M-ST-1396r-5','1924: spousal impoverishment (community spouse resource and income allowances)','42 U.S.C. 1396r-5','S',MAN,'no','no',[r'spousal impoverishment|community spouse|spousal (resource|income) (allowance|standard)|\bCSRA\b|\bMMMNA\b|minimum monthly maintenance'],'high','Not held. State-set: CSRA within the federal range, MMMNA, excess shelter standard.'),
 E('M-ST-1396r-6','1925: transitional medical assistance','42 U.S.C. 1396r-6; 42 CFR 435.112','S',MAN,'no','no',[r'transitional medical assistance|transitional medicaid|\bTMA\b|extended medicaid|extension of medicaid.{0,60}(earn|employment)|medical extension'],'high','Not held.'),
 E('M-ST-1396u-1','1931: low-income families (AFDC-related) group','42 U.S.C. 1396u-1; 42 CFR 435.110','F',NOFAM,'yes (categories/parent/*)','no',[],'high','Held (us/statute/42/1396u-1).'),
 E('M-ST-1396a-a10Aii-buyin','1902(a)(10)(A)(ii)(XIII), (XV), (XVI): working disabled buy-in groups (Ticket to Work)','42 U.S.C. 1396a(a)(10)(A)(ii)(XIII),(XV),(XVI)','S',MAN,'yes (variables is_working_disabled_buy_in_for_medicaid, medicaid_working_disabled_buy_in_premium)','no',[r'working disabled|medicaid buy-?in|ticket to work|workers with disabilities|working people with disabilities|employed (individuals|persons) with disabilities|\bMAWD\b|\bMWD\b|health coverage for workers'],'high','Held inside us/statute/42/1396a/a/10. No 42 CFR 435 section implements these groups.'),
 E('M-ST-1320b-7','1137: income and eligibility verification system (IEVS)','42 U.S.C. 1320b-7; 42 CFR 435.940-435.965','F',NOFAM,'no','no',[],'high','Not held. State implementation is elements 435.945-435.956.'),
 E('M-ST-1382','Title XVI SSI eligibility criteria referenced by 1902(a)(10)(A)(i)(II) and 1902(f)','42 U.S.C. 1382, 1382a, 1382b, 1382c','F',NOFAM,'partial (gov/ssa)','no',[],'high','Held (us/statute 2026-06-20 SSI Title XVI scope).'),
 E('M-ST-8usc-1611','PRWORA noncitizen eligibility: 8 U.S.C. 1611, 1612, 1613 (five-year bar), 1641 (qualified alien)','8 U.S.C. 1611, 1612, 1613, 1641; invoked by 42 U.S.C. 1396b(v) and 42 CFR 435.406','F',NOFAM,'yes (eligibility/eligible_immigration_statuses, five_year_bar_years, bar_exempt_immigration_statuses)','no',[],'high','Not held: no title-8 statute scope exists in the corpus. State election (CHIPRA 214 lawfully residing children and pregnant women) is element 435.406.'),
 E('M-ST-1315','1115 demonstration: state-specific eligibility terms (special terms and conditions)','42 U.S.C. 1315','S','CMS-approved 1115 demonstration special terms and conditions (medicaid.gov)','partial (variables is_medicaid_1115_mec_adult; states/ar work requirements)','no',[r'1115 (demonstration|waiver)|section 1115|demonstration (waiver|project|program)'],'high','1315 not held. Which states run 1115 eligibility demonstrations cannot be settled from the corpus; the pattern only finds mentions.'),
 E('M-ST-1396a-a3','1902(a)(3): fair hearings (42 CFR 431 subpart E is outside the regulation set requested for this check)','42 U.S.C. 1396a(a)(3); 42 CFR 431.200-431.250','S',MAN,'no','no',[r'fair hearing|administrative hearing|appeal(s)? (process|rights|procedure)|right to (a )?(hearing|appeal)'],'high','Statute subsection not held; 42 CFR 431 not in the corpus. Every held state manual has a hearings chapter, so the element is listed at the state level.'),
 E('M-ST-1396a-a25','1902(a)(25): third party liability and assignment of rights','42 U.S.C. 1396a(a)(25); 42 CFR 433 subpart D; 435.610','S',MAN,'no','no',[r'third.party liability|\bTPL\b|third.party (resource|payer|coverage)|assignment of rights'],'high','Statute subsection not held; 42 CFR 433 not in the corpus.'),
]

# ---------------------------------------------------------------- Medicaid: 42 CFR 435 by section
def R(sec, title, level, pats=None, conf='high', pe='no', rs='no', fam=MAN, notes='', **flags):
    flags.setdefault('cfr_path', f'us/regulation/42/435/{sec}')
    return E(f'M-435-{sec}', f'42 CFR 435.{sec}: {title}', f'42 CFR 435.{sec}', level, fam if level!='F' else NOFAM, pe, rs, pats or [], conf, notes, **flags)

M += [
 R('2','Purpose and applicability','F'), R('3','Basis','F'),
 R('4','Definitions and use of terms (state option: caretaker relative, dependent child age)','FS',[r'caretaker relative|specified relative|degree of relationship'],pe='partial (household/child_age_limit, parent/dependent_child/*)'),
 R('10','State plan requirements (the approved state plan)','S',[],fam=PLAN,notes='The state plan itself; medicaid.gov posts every state plan.',state_plan=True),
 R('100','Scope (subpart B mandatory coverage)','F'),
 R('110','Parents and other caretaker relatives (state income standard)','S',[r'parents? (and|or|&) (other )?caretaker relatives?|caretaker relatives?|low.income famil(y|ies) with (dependent )?children|section 1931|1931 (group|families)'],pe='yes (categories/parent/income_limit)',rs='us-xx cms eligibility-levels wrappers (parent/caretaker level)',fallback='us/form/cms/medicaid-chip-bhp-eligibility-levels/block-1'),
 R('112','Families terminated from AFDC because of increased earnings or hours (extended coverage)','FS',[r'increased earnings|increase in earnings|transitional medical assistance|extended medicaid|medical extension'],),
 R('115','Families with eligibility extended because of increased spousal support','FS',[r'(spousal|child) support.{0,120}(four|4).month|(four|4).month.{0,120}(spousal|child) support'],conf='low'),
 R('116','Pregnant women (state income standard, 133-185% FPL or higher)','S',[r'pregnan'],pe='yes (categories/pregnant/income_limit)',rs='us-xx cms eligibility-levels wrappers',fallback='us/form/cms/medicaid-chip-bhp-eligibility-levels/block-1'),
 R('117','Deemed newborn children','S',[r'deemed newborn|newborn.{0,80}(deemed|automatically|eligible)|continuously eligible newborn'],),
 R('118','Infants and children under age 19 (state income standards by age band)','S',[r'(infants?|children).{0,60}under (age )?19|under (age )?19|age[sd]? (0|1|6).{0,20}(to|through|-).{0,10}(1|5|18|19)|children.{0,40}(1 through 5|6 through 18|ages? 1-5|ages? 6-18)'],pe='yes (categories/infant, young_child, older_child income_limit + age_range)',rs='us-xx cms eligibility-levels wrappers',fallback='us/form/cms/medicaid-chip-bhp-eligibility-levels/block-1'),
 R('119','Coverage for individuals age 19 or older and under 65 at or below 133% FPL (adult group; state election)','S',[r'adult group|expansion (adult|group|population)|new adult group|MAGI adult|(133|138) ?(%|percent).{0,60}(FPL|poverty)|group VIII|VIII group'],pe='yes (categories/adult/*)',rs='us-xx cms eligibility-levels wrappers (expansion flag)',fallback='us/form/cms/medicaid-chip-bhp-eligibility-levels/block-1'),
 R('120','Individuals receiving SSI (1634 states)','S',[r'SSI recipient|receiv(e|es|ing) SSI|supplemental security income.{0,60}(eligib|automatic|categorically)|1634'],pe='yes (ssi_recipient/*)',rs='us-ga:policies/dfcs/medicaid/2578'),
 R('121','Individuals in states using more restrictive requirements than SSI (209(b))','FS',[r'209\(b\)|more restrictive.{0,60}(SSI|than)'],pe='yes (ssi_recipient/classification/section_209b)'),
 R('122','Individuals ineligible for SSI or optional state supplements because of requirements that do not apply under Medicaid','FS',[r'ineligible for SSI (solely|only|because)|not eligible for SSI (solely|only|because)'],conf='low'),
 R('123','Qualified Medicare beneficiaries (QMB)','S',[r'qualified medicare beneficiar|\bQMB\b'],),
 R('124','Specified low-income Medicare beneficiaries (SLMB)','S',[r'specified low.income medicare|\bSLMB\b|\bSLIMB\b'],),
 R('125','Qualifying individuals (QI)','S',[r'qualifying individual|\bQI-?1\b|\bQI\b program|\bQMB-?E\b|\bMQB-?E\b'],),
 R('126','Qualified disabled and working individuals (QDWI)','S',[r'qualified disabled (and|&) working|\bQDWI\b'],),
 R('130','Individuals receiving mandatory state supplements','FS',[r'mandatory state supplement'],conf='low'),
 R('131','Essential spouses in December 1973','FS',[r'essential spouse'],),
 R('132','Institutionalized individuals eligible in December 1973','FS',[r'december 1973|(institutionalized|in an institution).{0,60}1973'],conf='low'),
 R('133','Blind and disabled individuals eligible in December 1973','FS',[r'(blind|disabled).{0,60}(december )?1973|1973.{0,60}(blind|disabled)'],conf='low'),
 R('134','Individuals who would be eligible except for the 1972 OASDI increase','FS',[r'pub(lic)? ?(law|l\.) ?92-336|1972.{0,60}(OASDI|social security) (increase|benefit)'],conf='low'),
 R('135','Individuals ineligible for cash assistance because of OASDI cost-of-living increases (Pickle)','FS',[r'pickle|cost.of.living.{0,80}(OASDI|social security|RSDI).{0,80}(disregard|ineligible|lost)|503 (group|eligib)'],),
 R('136','State agency one-time notice and annual review requirements (Pickle)','F'),
 R('137','Disabled widows and widowers ineligible for SSI because of the 1983 benefit increase','FS',[r'disabled widow'],),
 R('138','Disabled widows and widowers aged 60 through 64','FS',[r'disabled widow.{0,80}(60|sixty)'],conf='low'),
 R('139','Coverage for certain aliens (emergency services)','FS',[r'emergency medical (assistance|services|condition)|emergency medicaid|alien emergency'],),
 R('145','Children with title IV-E adoption assistance, foster care or guardianship care','S',[r'IV-E|title 4-?E|foster care.{0,80}(medicaid|eligib)|adoption assistance.{0,80}(medicaid|eligib)|guardianship assistance'],),
 R('150','Former foster care children (to age 26)','S',[r'former foster care|aged out of foster care|foster care.{0,60}(age 26|under 26|26)'],),
 R('170','Pregnant women eligible for extended or continuous eligibility (postpartum; state 12-month option)','S',[r'postpartum'],pe='yes (categories/pregnant/postpartum_coverage)'),
 R('172','Continuous eligibility for hospitalized children (inpatient at age 19)','FS',[r'(inpatient|hospitalized).{0,120}(19th birthday|turns 19|age 19|attains age 19)|(19th birthday|turns 19).{0,120}(inpatient|hospital)'],conf='low'),
 R('200','Scope (subpart C options for coverage)','F'), R('201','Individuals included in optional groups','F'),
 R('210','Optional eligibility for individuals meeting the income and resource requirements of the cash assistance programs','FS',[r'optional.{0,60}(aged|blind|disabled).{0,120}(SSI|cash assistance) (income|standard|requirement)|meet(s)? the (income and resource|financial) requirements (of|for) SSI'],conf='low',pe='yes (variables is_optional_senior_or_disabled_*)'),
 R('211','Optional eligibility for individuals who would be eligible for cash assistance if not institutionalized','FS',[r'would be eligible for (SSI|cash assistance).{0,80}(not )?(in|institution)'],conf='low'),
 R('212','Individuals who would be ineligible if not enrolled in an MCO or PCCM (guaranteed eligibility)','F'),
 R('213','Optional eligibility for individuals needing treatment for breast or cervical cancer','S',[r'breast (and|or|&) cervical cancer|\bBCC(P|T|CP)\b|\bBCCPT\b'],),
 R('214','Eligibility limited to family planning and related services','S',[r'family planning (program|only|benefit|group|coverage|services)'],),
 R('215','Individuals infected with tuberculosis','S',[r'tuberculosis|\bTB\b (infected|program|group|related)'],),
 R('217','Individuals receiving home and community-based waiver services (special income level)','S',[r'home and community.based (services )?waiver|\bHCBS\b waiver|1915\(c\)|waiver (services|group|program)'],),
 R('218','Individuals with MAGI-based income above 133% FPL (state option)','S',[r'(above|over|exceed(s|ing)?|more than|greater than) 133 ?(%|percent)|1902\(hh\)'],conf='low'),
 R('219','Individuals receiving state plan home and community-based services (1915(i))','FS',[r'1915\(i\)|state plan home and community.based'],),
 R('220','Optional eligibility for parents and other caretaker relatives above the 1931 standard','FS',[r'optional.{0,60}(parent|caretaker)|caretaker relative.{0,120}(optional|above|higher income)'],conf='low'),
 R('222','Optional eligibility for reasonable classifications of individuals under age 21 (income)','FS',[r'reasonable classification|under (age )?21.{0,120}(optional|reasonable)'],conf='low'),
 R('223','Other optional eligibility for reasonable classifications of individuals under age 21','FS',[r'reasonable classification'],conf='low'),
 R('225','Individuals under age 19 who would be eligible if in a medical institution (Katie Beckett/TEFRA)','S',[r'katie beckett|\bTEFRA\b|(disabled )?child(ren)? (living )?at home.{0,120}(institution|would be eligible)|would (otherwise )?be eligible.{0,60}(institution|hospital|nursing).{0,120}(home|child)'],),
 R('226','Optional eligibility for independent foster care adolescents','FS',[r'independent foster care adolescent'],),
 R('227','Optional eligibility for individuals under 21 under state adoption assistance agreements','FS',[r'(state|non-?IV-?E) adoption assistance|adoption (assistance|subsidy).{0,80}(state|non-?IV-?E)'],conf='low'),
 R('229','Optional targeted low-income children (Medicaid-expansion CHIP)','S',[r'targeted low.income child|title XXI|medicaid expansion (CHIP|program)|M-?CHIP|CHIP.{0,60}medicaid expansion|expansion CHIP'],),
 R('230','Aged, blind and disabled individuals in 209(b) states (optional)','FS',[r'209\(b\)'],conf='low',pe='yes (categories/senior_or_disabled/*)'),
 R('232','Individuals receiving only optional state supplements (1634 states)','S',[r'optional state supplement|state supplement(ary|al) (payment|program)|\bSSP\b|\bOSS\b|state supplementation'],),
 R('234','Individuals receiving only optional state supplements in 209(b) states','FS',[r'optional state supplement.{0,120}209\(b\)|209\(b\).{0,120}optional state supplement'],conf='low'),
 R('236','Individuals in institutions eligible under a special income level (300% of SSI)','S',[r'special income (level|limit|standard|group)|300 ?(%|percent).{0,60}(SSI|federal benefit rate|FBR)|institutional(ized)? (income )?(cap|limit|standard)'],),
 R('300','Scope (subpart D medically needy)','F'),
 R('301','General rules for medically needy coverage (state election)','S',[r'medically needy'],pe='yes (categories/medically_needy/*)'),
 R('308','Medically needy coverage of individuals under age 21','S',[r'medically needy.{0,120}(under (age )?21|child)|(child|under (age )?21).{0,120}medically needy'],conf='low'),
 R('310','Medically needy coverage of parents and other caretaker relatives','S',[r'medically needy.{0,120}(parent|caretaker)|(parent|caretaker).{0,120}medically needy'],conf='low'),
 R('320','Medically needy coverage of the aged (SSI states)','FS',[r'medically needy.{0,120}(aged|elderly|65)|(aged|elderly|65).{0,120}medically needy'],conf='low'),
 R('322','Medically needy coverage of the blind (SSI states)','FS',[r'medically needy.{0,120}blind|blind.{0,120}medically needy'],conf='low'),
 R('324','Medically needy coverage of the disabled (SSI states)','FS',[r'medically needy.{0,120}disab|disab.{0,120}medically needy'],conf='low'),
 R('326','Medically needy individuals who would be ineligible if not enrolled in an MCO or PCCM','F'),
 R('330','Medically needy coverage of the aged, blind and disabled in 209(b) states','FS',[r'medically needy.{0,200}209\(b\)|209\(b\).{0,200}medically needy'],conf='low'),
 R('340','Protected medically needy coverage for blind and disabled individuals eligible in December 1973','F'),
 R('350','Medically needy coverage for certain aliens','F'),
 R('400','Scope (subpart E general eligibility requirements)','F'), R('401','General rules','F'),
 R('403','State residence','S',[r'state residen|residency requirement|resident of (the state|this state|\w+)'],),
 R('404',"Applicant's choice of category",'F'),
 R('406','Citizenship and noncitizen eligibility (state option: lawfully residing children and pregnant women)','S',[r'qualified (alien|non-?citizen|immigrant)|lawfully (present|residing)|citizenship (and|or|&) (alien|immigra|non-?citizen)|immigration status|non-?citizen eligib|five.year bar|5.year bar'],pe='yes (eligibility/eligible_immigration_statuses, five_year_bar_years, undocumented_immigrant)',rs='no'),
 R('407','Types of acceptable documentary evidence of citizenship','FS',[r'(documentary )?evidence of citizenship|(proof|verification|documentation) of (U\.?S\.? )?citizenship|citizenship (documentation|verification)'],),
 R('500','Scope (subpart F categorical requirements)','F'),
 R('520','Age requirements for the aged','FS',[r'age(d)? 65|65 years (of age|or older)|sixty.five'],conf='low'),
 R('530','Definition of blindness','FS',[r'blind(ness)?.{0,80}(defin|20/200|central visual acuity)'],),
 R('531','Determinations of blindness','FS',[r'(determination|determining) of blindness|blindness.{0,60}(determin|review)'],conf='low'),
 R('540','Definition of disability','FS',[r'defin(ition|ed).{0,40}disab|disab(ility|led).{0,60}(defin|means|as defined)'],conf='low'),
 R('541','Determinations of disability (state determination or SSA)','FS',[r'disability determination|(determination|determining) of disability|\bMRT\b|medical review team|disability (review|examin)'],),
 R('550','Community engagement: basis and scope (CMS-2454-IFC)','F',absent_note='IFC compliance date 2027-01-01 (states may implement earlier); state manuals held on 2026-09-10 predate implementation'),
 R('551','Community engagement: applicable individual','S',[r'community engagement|work requirement'],notes='Held in the CMS-2454-IFC corrected scope.',absent_note='IFC compliance date 2027-01-01; state manuals held predate implementation',pe='yes (work_requirements/*)'),
 R('552','Community engagement: demonstrating community engagement (80 hours)','S',[r'community engagement|(80|eighty) hours'],absent_note='IFC compliance date 2027-01-01',pe='yes (work_requirements/monthly_hours_threshold)'),
 R('553','Community engagement: mandatory exceptions','S',[r'community engagement.{0,300}exception|exception.{0,300}community engagement'],absent_note='IFC compliance date 2027-01-01',pe='partial (variables *_for_medicaid_ce)'),
 R('554','Community engagement: specified excluded individuals','S',[r'community engagement.{0,300}exclu|exclu.{0,300}community engagement'],absent_note='IFC compliance date 2027-01-01',pe='partial'),
 R('555','Community engagement: optional exception for short-term hardship events','S',[r'short.term hardship'],absent_note='IFC compliance date 2027-01-01'),
 R('556','Community engagement: assessing compliance','S',[r'community engagement.{0,300}(assess|compliance)'],absent_note='IFC compliance date 2027-01-01'),
 R('557','Community engagement: verifying compliance or exception','S',[r'community engagement.{0,300}verif'],absent_note='IFC compliance date 2027-01-01'),
 R('558','Community engagement: noncompliance procedures','S',[r'community engagement.{0,300}(noncompliance|non-compliance|disenroll)'],absent_note='IFC compliance date 2027-01-01'),
 R('559','Community engagement: implementation timing','S',[r'community engagement.{0,300}(implement|effective)'],absent_note='IFC compliance date 2027-01-01'),
 R('560','Community engagement: good faith effort exemption','F'),
 R('561','Community engagement: state requirements for outreach','S',[r'community engagement.{0,300}outreach'],absent_note='IFC compliance date 2027-01-01'),
 R('562','Community engagement: state data submission for monitoring','F'),
 R('563','Community engagement: prohibition of waivers','F'),
 R('600','Scope (subpart G financial eligibility requirements)','F'),
 R('601','Application of financial eligibility methodologies (less restrictive methodologies)','S',[r'less restrictive|more liberal|1902\(r\)\(2\)|income disregard|resource disregard'],pe='partial (senior_or_disabled/income/disregard)'),
 R('602','Financial responsibility of relatives and other individuals (spousal and parental deeming)','S',[r'deem(ed|ing) (income|resources)|financial responsibility of relatives|spouse.{0,80}(deem|financially responsible)|parent.{0,80}deem'],pe='partial (income/deemed/*)'),
 R('603','Application of modified adjusted gross income (MAGI): household, income, budget period, 5% disregard','S',[r'modified adjusted gross income|\bMAGI\b'],pe='yes (income/*, household/*)',rs='us:policies/medicaid/magi_household_income_pipeline'),
 R('610','Assignment of rights to benefits (third party liability)','S',[r'assignment of rights|third.party liability|\bTPL\b'],),
 R('622','Individuals in institutions eligible under a special income level (financial rules)','S',[r'special income (level|limit|standard)'],),
 R('631','General requirements for determining income eligibility in 209(b) states','FS',[r'209\(b\)'],conf='low'),
 R('640','Protected Medicaid eligibility for individuals eligible in December 1973','F'),
 R('700','Scope (subpart H post-eligibility)','F'),
 R('725','Post-eligibility treatment of income of institutionalized individuals in SSI states (patient liability, personal needs allowance)','S',[r'post.eligibility|patient liability|personal needs allowance|patient pay(ment)?|share of cost|cost of care contribution|\bPNA\b'],),
 R('726','Post-eligibility treatment of income of individuals receiving HCBS waiver services (maintenance needs allowance)','S',[r'(post.eligibility|maintenance needs|personal needs).{0,200}(waiver|home and community|HCBS)|(waiver|HCBS).{0,200}(post.eligibility|maintenance needs allowance)'],),
 R('733','Post-eligibility treatment of income in 209(b) states','FS',[r'post.eligibility.{0,200}209\(b\)'],conf='low'),
 R('735','Post-eligibility treatment of income and resources for HCBS in 209(b) states','FS',[r'209\(b\)'],conf='low'),
 R('800','Scope (subpart I medically needy financial requirements)','F'),
 R('811','Medically needy income standard: general requirements (state-set MNIL)','S',[r'medically needy income (level|standard|limit)|\bMNIL\b|protected income level|\bPIL\b|medically needy (standard|level)'],pe='yes (medically_needy/limit/income/*)',fam=MAN_TAB),
 R('814','Medically needy income standard: state plan requirements','S',[],fam=PLAN,state_plan=True),
 R('831','Income eligibility (spend-down, budget period)','S',[r'spend.?down|excess income|incurred medical expenses.{0,120}(deduct|excess|spend)'],pe='yes (variables medicaid_medically_needy_medical_expenses)'),
 R('832','Post-eligibility treatment of income of institutionalized medically needy individuals','FS',[r'medically needy.{0,200}(post.eligibility|patient liability|institution)'],conf='low'),
 R('840','Medically needy resource standard: general requirements (state-set)','S',[r'medically needy resource (standard|limit|level)|resource (limit|standard|level).{0,120}medically needy'],pe='yes (medically_needy/limit/assets/*)',fam=MAN_TAB),
 R('843','Medically needy resource standard: state plan requirements','S',[],fam=PLAN,state_plan=True),
 R('845','Medically needy resource eligibility','FS',[r'medically needy.{0,200}resource'],conf='low'),
 R('900','Scope (subpart J eligibility in the states and DC)','F'), R('901','Consistency with objectives and statutes','F'), R('902','Simplicity of administration','F'), R('903','Adherence of local agencies to state plan requirements','F'),
 R('904','Establishment of outstation locations','FS',[r'outstation'],conf='low'),
 R('905','Availability and accessibility of program information','F'), R('906','Opportunity to apply','F'),
 R('907','Application (single streamlined application; state options)','S',[r'application (form|process|procedures?|requirements?)|single streamlined application|apply(ing)? for (medicaid|medical assistance|benefits|coverage)|how to apply'],),
 R('908','Assistance with application and renewal (application assisters, certified counselors)','FS',[r'application assist|assist(ance)? (with|in) (completing|the) (an )?application|certified application counselor|navigator'],conf='low'),
 R('909','Automatic entitlement following eligibility determination under other programs','F'),
 R('910','Use of social security number','S',[r'social security number|\bSSN\b'],),
 R('911','Determination of eligibility (highest applicable group, MAGI and non-MAGI)','S',[r'determination of eligibility|eligibility determination|determin(e|ing) eligibility'],),
 R('912','Timely determination and redetermination of eligibility (45/90-day standards)','S',[r'(45|forty.five) (calendar )?days|(90|ninety) (calendar )?days|timel(y|iness) (standard|determination)|reasonable promptness|standard of promptness'],),
 R('914','Case documentation','F'),
 R('915','Effective date of eligibility (retroactive months)','S',[r'effective date of (eligibility|coverage)|begin(ning)? date of (eligibility|coverage)|retroactive'],),
 R('916','Regularly scheduled renewals (12-month; ex parte)','S',[r'renewal|redetermination|recertification|ex parte|annual review|passive renewal'],),
 R('917',"Notice of agency's decision (adequate notice, adverse action)",'S',[r'notice of (adverse )?action|adequate notice|written notice|timely notice|advance notice|notice requirements'],),
 R('918','Use of electronic notices','FS',[r'electronic notice|electronic(ally)? (delivered )?notic'],conf='low'),
 R('919','Changes in circumstances (reporting and acting on changes)','S',[r'change(s)? in circumstance|report(ing)? (a )?change|reported change|change report'],),
 R('920','Verification of SSNs','FS',[r'(verif|validat).{0,60}(SSN|social security number)|(SSN|social security number).{0,60}(verif|validat)'],),
 R('923','Authorized representatives','S',[r'authorized representative'],),
 R('926','Continuous eligibility for children (12 months, mandatory 2024)','S',[r'continuous eligibility|(12|twelve).month continuous|continuous coverage (for|of) children|continuous(ly)? eligib'],),
 R('927','Requirements for states to submit data on redeterminations','F'), R('928','Reduction in FMAP for failure to submit data','F'), R('930','Furnishing Medicaid','F'),
 R('940','Basis and scope (verification of eligibility)','F'),
 R('945','General requirements (verification plan)','S',[r'verification plan|verif(y|ication) of (income|eligibility|information)|verification (requirement|standard|procedure)'],),
 R('948','Verifying financial information (electronic data sources, reasonable compatibility)','S',[r'electronic (data )?source|reasonabl(e|y) compatib|federal data services hub|\bIEVS\b|data (match|exchange)|the hub\b'],),
 R('949','Verification through an electronic service','FS',[r'electronic (verification )?service|federal data services hub|the hub\b'],conf='low'),
 R('952','Use of information and requests for additional information (reasonable compatibility standard)','S',[r'reasonabl(e|y) compatib'],),
 R('956','Verification of other non-financial information (citizenship, immigration, residency, SSN)','S',[r'verif.{0,80}(citizenship|immigration|residency|residence|age|identity)|(citizenship|immigration|residency).{0,80}verif'],),
 R('960','Standardized formats for furnishing and obtaining information','F'), R('965','Delay of effective date','F'),
 R('1000','Scope (subpart K FFP)','F'), R('1001','FFP for administration','F'), R('1002','FFP for services','F'), R('1003','FFP for redeterminations','F'), R('1004','Beneficiaries overcoming certain conditions of eligibility','F'), R('1005','Beneficiaries in institutions under a special income standard','F'), R('1006','Beneficiaries of optional state supplements only','F'), R('1007','Categorically needy, medically needy and QMB (FFP limits)','F'), R('1008','FFP for individuals who declared citizenship pending verification','F'), R('1009','Institutionalized individuals (IMD exclusion)','F'), R('1010','Definitions relating to institutional status','F'), R('1011','Requirement for mandatory state supplements','F'), R('1012','Requirement for maintenance of optional state supplement expenditures','F'), R('1015','FFP for premium assistance for plans in the individual market','F'),
 R('1100','Basis for presumptive eligibility','F'), R('1101','Definitions related to presumptive eligibility','F'),
 R('1102','Children covered under presumptive eligibility (state option)','S',[r'presumptive eligibility.{0,200}child|child(ren)?.{0,200}presumptive eligibility|presumptive(ly)? eligib.{0,60}(child|kids)'],),
 R('1103','Presumptive eligibility for other individuals (pregnant women, adults, BCCP; state option)','S',[r'presumptive eligibility.{0,200}(pregnan|adult|parent|caretaker|family planning|breast)|(pregnan|adult).{0,200}presumptive eligibility'],),
 R('1110','Presumptive eligibility determined by hospitals (mandatory)','S',[r'hospital presumptive|presumptive eligibility.{0,120}hospital|qualified hospital|\bHPE\b'],),
 R('1200','Medicaid agency responsibilities for coordinated eligibility and enrollment with CHIP, Exchange and BHP','S',[r'insurance affordability program|(exchange|marketplace).{0,120}(coordinat|transfer|refer)|(coordinat|transfer|refer).{0,120}(exchange|marketplace)|account transfer|healthplanfinder|federally.facilitated'],),
 R('1205','Alignment with Exchange initial open enrollment period','F'),
]

# ---------------------------------------------------------------- Medicaid: 42 CFR 436 (Guam, PR, VI) by section
S436 = [('1','Purpose and applicability'),('2','Basis'),('3','Definitions and use of terms'),('10','State plan requirements'),('100','Scope'),('110','Individuals receiving cash assistance'),('111','Individuals not eligible for cash assistance because of a requirement not applicable under Medicaid'),('112','Individuals who would be eligible for cash assistance except for increased OASDI'),('114','Individuals deemed to be receiving AFDC'),('116','Families terminated from AFDC because of increased earnings or hours'),('118','Children with adoption assistance or foster care maintenance payments'),('120','Qualified pregnant women and children who are not qualified family members'),('121','Qualified family members'),('122','Pregnant women eligible for extended coverage'),('124','Newborn children'),('128','Coverage for certain qualified aliens'),('200','Scope'),('201','Individuals included in optional groups'),('210','Individuals who meet the income and resource requirements of the cash assistance programs'),('211','Individuals who would be eligible for cash assistance if not in medical institutions'),('212','Individuals who would be eligible for cash assistance if the state plan were as broad as allowed'),('217','Individuals receiving home and community-based services'),('219','Individuals receiving state plan home and community-based services'),('220','Individuals who would meet AFDC requirements if child care costs were paid from earnings'),('222','Individuals under age 21 who meet AFDC income and resource requirements'),('224','Individuals under age 21 under state adoption assistance agreements'),('229','Optional targeted low-income children'),('230','Essential spouses of aged, blind or disabled individuals receiving cash assistance'),('300','Scope'),('301','General rules (medically needy)'),('308','Medically needy coverage of individuals under age 21'),('310','Medically needy coverage of specified relatives'),('320','Medically needy coverage of the aged'),('321','Medically needy coverage of the blind'),('322','Medically needy coverage of the disabled'),('330','Coverage for certain aliens'),('400','Scope'),('401','General rules'),('403','State residence'),('404',"Applicant's choice of category"),('406','Citizenship and alienage'),('407','Types of acceptable documentary evidence of citizenship'),('500','Scope'),('510','Determination of dependency'),('520','Age requirements for the aged'),('522','Determination of age'),('530','Definition of blindness'),('531','Determination of blindness'),('540','Definition of disability'),('541','Determination of disability'),('600','Scope'),('601','Application of financial eligibility methodologies'),('602','Financial responsibility of relatives and other individuals'),('610','Assignment of rights to benefits'),('800','Scope'),('811','Medically needy income standard: general requirements'),('814','Medically needy income standard: state plan requirements'),('831','Income eligibility'),('832','Post-eligibility treatment of income of institutionalized individuals'),('840','Medically needy resource standard: general requirements'),('843','Medically needy resource standard: state plan requirements'),('845','Medically needy resource eligibility'),('900','Scope'),('901','General requirements'),('909','Automatic entitlement following eligibility under other programs'),('1000','Scope'),('1001','FFP for administration'),('1002','FFP for services'),('1003','Beneficiaries overcoming certain conditions of eligibility'),('1004','FFP for individuals who declared citizenship'),('1005','Institutionalized individuals'),('1006','Definitions relating to institutional status'),('1100','Basis and scope (presumptive eligibility)'),('1101','Definitions related to presumptive eligibility period for children'),('1102','General rules')]
for sec, t in S436:
    M.append(E(f'M-436-{sec}', f'42 CFR 436.{sec}: {t}', f'42 CFR 436.{sec}', 'F', NOFAM, 'no', 'no', [], 'high',
               'Part 436 governs eligibility in Guam, Puerto Rico and the Virgin Islands; not applicable to the 50 states and DC (state rows NOT_APPLICABLE).', cfr_path=f'us/regulation/42/436/{sec}', territories_only=True))

# ---------------------------------------------------------------- Medicaid: 42 CFR 447 subpart A
S447 = [('1','Purpose','F'),('10','Prohibition against reassignment of provider claims','F'),('15','Acceptance of state payment as payment in full','F'),('20','Provider restrictions: state plan requirements','F'),('21','Reduction of payments to providers','F'),('25',"Direct payments to certain beneficiaries for physicians' or dentists' services",'F'),('26','Prohibition on payment for provider-preventable conditions','F'),('30','Withholding the federal share to recover Medicare overpayments','F'),('31','Withholding Medicare payments to recover Medicaid overpayments','F'),('40','Payments for reserving beds in institutions','F'),('45','Timely claims payment','F'),('46','Timely claims payment by MCOs','F'),('50','Premiums and cost sharing: basis and purpose','F'),('51','Definitions (cost sharing)','F'),('88','Options for claiming FFP for section 1920A presumptive eligibility payments','F'),('90','FFP: conditions related to pending investigations of credible allegations of fraud','F')]
for sec, t, lv in S447:
    M.append(E(f'M-447-{sec}', f'42 CFR 447.{sec}: {t}', f'42 CFR 447.{sec}', lv, NOFAM, 'no', 'no', [], 'high', 'Part 447 is not in the corpus (eCFR structure 2026-09-09 lists subpart A sections 447.1-447.90).', cfr_path=f'us/regulation/42/447/{sec}', ecfr_missing=True))
M += [
 E('M-447-52','42 CFR 447.52: Cost sharing (copayments; state election and amounts)','42 CFR 447.52','S',MAN+' / state plan attachment 4.18','no','no',[r'co-?pay(ment)?s?\b|cost.sharing|coinsurance|deductible'],'high','Part 447 not held.',cfr_path='us/regulation/42/447/52',ecfr_missing=True),
 E('M-447-53','42 CFR 447.53: Cost sharing for drugs (preferred/non-preferred)','42 CFR 447.53','S',MAN,'no','no',[r'(co-?pay(ment)?|cost.sharing).{0,120}(drug|prescription|pharmacy)|(drug|prescription|pharmacy).{0,120}(co-?pay(ment)?|cost.sharing)'],'high','Part 447 not held.',cfr_path='us/regulation/42/447/53',ecfr_missing=True),
 E('M-447-54','42 CFR 447.54: Cost sharing for non-emergency use of the emergency department','42 CFR 447.54','S',MAN,'no','no',[r'(non-?emergenc(y|ies)|emergency (department|room)).{0,120}(co-?pay(ment)?|cost.sharing)|(co-?pay(ment)?|cost.sharing).{0,120}emergency (department|room)'],'high','Part 447 not held.',cfr_path='us/regulation/42/447/54',ecfr_missing=True),
 E('M-447-55','42 CFR 447.55: Premiums (state election, amounts, groups)','42 CFR 447.55','S',MAN,'yes (variables medicaid_premium, medicaid_working_disabled_buy_in_premium)','no',[r'premium'],'high','Part 447 not held.',cfr_path='us/regulation/42/447/55',ecfr_missing=True),
 E('M-447-56','42 CFR 447.56: Limitations on premiums and cost sharing (exempt groups, 5% aggregate cap)','42 CFR 447.56','S',MAN,'no','no',[r'(cost.sharing|co-?pay(ment)?|premium).{0,200}(exempt|5 ?(%|percent)|five percent|aggregate|maximum)|(exempt|5 ?(%|percent) of.{0,40}income|aggregate).{0,120}(cost.sharing|co-?pay|premium)'],'high','Part 447 not held.',cfr_path='us/regulation/42/447/56',ecfr_missing=True),
 E('M-447-57','42 CFR 447.57: Beneficiary and public notice requirements for cost sharing','42 CFR 447.57','FS',MAN,'no','no',[r'public (schedule|notice).{0,120}(cost.sharing|co-?pay|premium)'],'low','Part 447 not held.',cfr_path='us/regulation/42/447/57',ecfr_missing=True),
]

# ---------------------------------------------------------------- Medicaid: state rulebook structure elements
M += [
 E('M-SS-STATE-PLAN','Approved Medicaid state plan (current compiled plan with eligibility attachments)','42 U.S.C. 1396a(a); 42 CFR 435.10, 430.10','S',PLAN,'no','no',[],'high','No state plan document is held for any state; medicaid.gov posts every approved plan (https://www.medicaid.gov/medicaid/medicaid-state-plan-amendments).',state_plan=True),
 E('M-SS-SPA','Medicaid state plan amendments (eligibility SPAs on record)','42 CFR 430.12','S','CMS Medicaid SPA index (medicaid.gov)','no','no',[],'high','No Medicaid SPA document is held for any state (the corpus CHIP SPA scope holds CHIP SPAs only).',state_plan=True),
 E('M-SS-INCOME-TABLE','Current-year MAGI income standards table (children by age band, pregnant, parents, adults) as a percentage of FPL','42 CFR 435.110, 435.116, 435.118, 435.119; state plan supplement to attachment 2.6-A','S',MAN_TAB,'yes (categories/*/income_limit)','us-xx:policies/cms/<state>-medicaid-chip-bhp-eligibility-levels',[r'income (limit|standard|level|guideline|chart|table)s?.{0,160}(%|percent).{0,40}(FPL|poverty)|(%|percent) (of (the )?)?(FPL|federal poverty).{0,160}income (limit|standard|level)|poverty (level|guideline)s? (chart|table)'],'high','Federal fallback: the CMS Medicaid/CHIP/BHP eligibility-levels table (state decisions as of 2023-12-01) carries every state.',fallback='us/form/cms/medicaid-chip-bhp-eligibility-levels/block-1'),
 E('M-SS-RESOURCE-TABLE','Non-MAGI (aged, blind, disabled) income and resource limits table','42 CFR 435.121, 435.230, 435.601, 435.840; state plan','S',MAN_TAB,'yes (categories/senior_or_disabled/assets/limit/*, income/limit/*)','no',[r'resource (limit|standard|level|maximum)s?.{0,120}\$\s?\d|\$\s?2,?000|\$\s?3,?000|asset (limit|test).{0,120}\$\s?\d|countable (resources|assets).{0,120}(limit|exceed).{0,60}\$'],'high',''),
 E('M-SS-BENEFITS','Covered services / benefit package (state plan attachment 3.1-A, alternative benefit plan)','42 U.S.C. 1396d(a), 1396u-7; 42 CFR 440','S','state plan attachment 3.1 / provider or member handbook','no','no',[r'covered services|benefit package|scope of (covered )?(services|benefits)|alternative benefit plan|\bABP\b|EPSDT'],'low','42 CFR 440 not in the corpus; benefit rules mostly live outside eligibility manuals.'),
 E('M-SS-HEARINGS','Fair hearings and appeals chapter of the state rulebook','42 CFR 431 subpart E (not in the corpus); 42 U.S.C. 1396a(a)(3)','S',MAN,'no','no',[r'fair hearing|administrative hearing|appeal(s)? (process|rights|procedure)|right to (a )?(hearing|appeal)|request(ing)? a hearing'],'high','Duplicate view of M-ST-1396a-a3 from the state-structure side; kept because every held manual carries the chapter.'),
]

# ================================================================ CHIP
C = []
C += [
 E('C-ST-1397aa','2101: purpose; state child health plans','42 U.S.C. 1397aa','F',NOFAM,'no','no',[],'high','Held (us/statute/42/1397aa, consolidated title-42 scope).'),
 E('C-ST-1397bb','2102: general contents of the state child health plan; eligibility standards and methodology; outreach; coordination','42 U.S.C. 1397bb','F',NOFAM,'no','no',[],'high','Held. State plan content is element 457.50 / C-SS-STATE-PLAN.'),
 E('C-ST-1397cc','2103: coverage requirements (benchmark options); 2103(e) cost-sharing limits','42 U.S.C. 1397cc','F',NOFAM,'partial (cost_sharing/cap/rate)','no',[],'high','Held. State elections are elements 457.410-457.450 and 457.505-457.570.'),
 E('C-ST-1397dd','2104: allotments','42 U.S.C. 1397dd','F',NOFAM,'no','no',[],'high','Held.'),
 E('C-ST-1397ee','2105: payments to states (enhanced FMAP; 10% administrative cap; conditions)','42 U.S.C. 1397ee','F',NOFAM,'yes (variables chip_federal_share, chip_federal_cost)','no',[],'high','Held.'),
 E('C-ST-1397ff','2106: submission, approval and amendment of state child health plans','42 U.S.C. 1397ff','F',NOFAM,'no','no',[],'high','Held.'),
 E('C-ST-1397gg','2107: strategic objectives and performance goals; plan administration','42 U.S.C. 1397gg','F',NOFAM,'no','no',[],'high','Held.'),
 E('C-ST-1397hh','2108: annual reports; evaluations','42 U.S.C. 1397hh','F',NOFAM,'no','no',[],'high','Held.'),
 E('C-ST-1397ii','2109: miscellaneous provisions (relation to other laws; adult coverage limits)','42 U.S.C. 1397ii','F',NOFAM,'no','no',[],'high','Held.'),
 E('C-ST-1397jj-b','2110(b): targeted low-income child (state income standard; uncovered child; group health plan exclusion; substitution)','42 U.S.C. 1397jj(b); 42 CFR 457.310','S',CPLAN+' / '+MAN,'yes (child/income_limit, child/max_age, disqualifying_health_coverage)','us-xx:policies/cms/<state>-chip-eligibility',[r'targeted low.income child|uninsured child|(no|without) (other )?(creditable |health )?(insurance|coverage).{0,80}child|child.{0,80}(no|without) (other )?(creditable |health )?(insurance|coverage)'],'high','Held (us/statute/42/1397jj).',fallback='us/form/cms/medicaid-chip-bhp-eligibility-levels/block-1'),
 E('C-ST-1397jj-c','2110(c): definitions (child, creditable coverage, etc.)','42 U.S.C. 1397jj(c)','F',NOFAM,'yes (child/max_age)','us:statutes/42/1397jj/c/1#child',[],'high','Held.'),
 E('C-ST-1397kk','2111: phase-out of coverage for nonpregnant childless adults; parent coverage conditions','42 U.S.C. 1397kk','F',NOFAM,'no','no',[],'high','Held.'),
 E('C-ST-1397ll','2112: optional coverage of targeted low-income pregnant women (state election and income standard)','42 U.S.C. 1397ll','S',CPLAN+' / '+MAN,'yes (pregnant/income_limit)','us-xx:policies/cms/<state>-chip-eligibility (pregnant CHIP availability)',[r'pregnan'],'high','Held (us/statute/42/1397ll). Fallback: CMS table "Pregnant Women CHIP" column.',fallback='us/form/cms/medicaid-chip-bhp-eligibility-levels/block-1',chip_context=True),
 E('C-ST-1397mm','2113: grants to improve outreach and enrollment','42 U.S.C. 1397mm','F',NOFAM,'no','no',[],'high','Held.'),
 E('C-ST-FCEP','Unborn child option (coverage from conception to birth, 42 CFR 457.10 definition of child; CHIP SPA CS9)','42 CFR 457.10 ("child"); state CHIP SPA template CS9','S','CMS CHIP SPA (medicaid.gov) / '+MAN,'yes (fcep/*)','us-xx:policies/cms/<state>-chip-eligibility (FCEP)',[r'unborn child|conception to birth|from conception|prenatal (coverage|program|care).{0,60}(CHIP|title XXI)|CHIP perinatal|unborn'],'high','The CMS CHIP children-coverage map (us/form) records which states elect the FCEP option; the CHIP SPA scope holds the FCEP SPAs for some states.',fallback='us/form/cms/chip-children-coverage-map',coverage_map=True,chip_context=True),
]
def Q(sec, title, level, pats=None, conf='high', pe='no', rs='no', fam=MAN, notes='', **flags):
    flags.setdefault('cfr_path', f'us/regulation/42/457/{sec}')
    return E(f'C-457-{sec}', f'42 CFR 457.{sec}: {title}', f'42 CFR 457.{sec}', level, fam if level!='F' else NOFAM, pe, rs, pats or [], conf, notes, chip_context=True, **flags)
C += [
 Q('1','Program description','F'), Q('2','Basis and scope of subchapter D','F'), Q('10','Definitions and use of terms (child, targeted low-income child, etc.)','F'), Q('30','Basis, scope and applicability of subpart A','F'),
 Q('40','State program administration (designated agency)','F'),
 Q('50','State plan (the approved CHIP state plan)','S',[],fam=CPLAN,state_plan=True,notes='medicaid.gov posts every CHIP state plan; the PA CHIP index also lists its state plan PDF (not taken).'),
 Q('60','Amendments (CHIP SPAs on record)','S',[],fam='CMS CHIP SPA index (medicaid.gov)',spa=True,notes='The corpus CHIP SPA scope (us/policy 2026-07-05-cms-chip-fcep-spa) holds SPAs for 20 states.'),
 Q('65','Effective date and duration of state plans and amendments','F'),
 Q('70','Program options (Medicaid expansion, separate program, combination)','S',[r'medicaid expansion (CHIP|program)|separate (CHIP|child health|children.s health) (program|insurance)|combination (program|CHIP)|title XXI'],fam='CMS CHIP children coverage map (us/form) / '+CPLAN,coverage_map=True,fallback='us/form/cms/chip-children-coverage-map',notes='The CMS coverage map (us/form/cms/chip-children-coverage-map/<state>) records each state\'s program type.'),
 Q('80','Current state child health insurance coverage and coordination','FS',[r'coordinat.{0,120}(medicaid|exchange|marketplace)'],conf='low'),
 Q('90','Outreach','FS',[r'outreach'],conf='low'),
 Q('110','Enrollment assistance and information requirements','FS',[r'(enrollment|application) assist'],conf='low'),
 Q('120','Public involvement in program development','F'),
 Q('125','Provision of child health assistance to American Indian and Alaska Native children','FS',[r'american indian|alaska native|\bAI/AN\b|tribal member|indian health'],),
 Q('130','Civil rights assurance','F'), Q('135','Assurance of compliance with other provisions','F'), Q('140','Budget','F'), Q('150','CMS review of state plan material','F'), Q('160','Notice and timing of CMS action','F'), Q('170','Withdrawal process','F'),
 Q('200','Program reviews','F'), Q('202','Audits','F'), Q('203','Administrative and judicial review of action on state plan material','F'), Q('204','Withholding of payment for failure to comply','F'), Q('206','Administrative appeals under CHIP','F'), Q('208','Judicial review','F'), Q('216','Treatment of uncashed or canceled CHIP checks','F'), Q('220','Funds from units of government as state share','F'), Q('222','FFP for equipment','F'), Q('224','FFP: conditions relating to cost sharing','F'), Q('226','Fiscal policies and accountability','F'), Q('228','Cost allocation','F'), Q('230','FFP for state ADP expenditures','F'), Q('232','Refunding of federal share of overpayments','F'), Q('236','Audits','F'), Q('238','Documentation of payment rates','F'),
 Q('300','Basis, scope and applicability (subpart C eligibility)','F'), Q('301','Definitions and use of terms','F'),
 Q('305','State plan provisions (eligibility standards in the plan)','S',[],fam=CPLAN,state_plan=True),
 Q('310','Targeted low-income child (state income standard; uninsured; not eligible for Medicaid; group health plan exclusions)','S',[r'targeted low.income child|(200|250|300|3\d\d|2\d\d) ?(%|percent).{0,60}(FPL|poverty).{0,200}(CHIP|child)|uninsured.{0,80}child|child.{0,80}uninsured'],pe='yes (child/income_limit, disqualifying_health_coverage)',rs='us-xx:policies/cms/<state>-chip-eligibility',fallback='us/form/cms/medicaid-chip-bhp-eligibility-levels/block-1',fam=MAN_TAB),
 Q('315','Application of MAGI and household definition','S',[r'modified adjusted gross income|\bMAGI\b'],pe='yes (via gov/hhs/medicaid/income)'),
 Q('320-a','Other eligibility standards: residency, citizenship, age, SSN (457.320(a)-(c))','S',[r'(state )?residen|citizen|immigra|lawfully|social security number'],conf='low',cfr_path='us/regulation/42/457/320'),
 Q('320-b','Other eligibility standards: waiting period / period of uninsurance (457.320(a)(9), 457.805)','S',[r'waiting period|period of uninsurance|uninsured for (at least )?(30|60|90|ninety|three|3|6|six)|(30|60|90|ninety) days?.{0,80}(uninsured|without (health )?(insurance|coverage))'],cfr_path='us/regulation/42/457/320'),
 Q('330','Application (single streamlined; state options)','S',[r'application (form|process|procedure)|apply(ing)? for|single streamlined application'],),
 Q('340','Application for and enrollment in CHIP (effective dates, notices)','S',[r'enroll(ment|ed).{0,120}(effective|begin|date)|effective date|begin date'],conf='low'),
 Q('342','Continuous eligibility for children (12 months; mandatory 2024)','S',[r'continuous eligibility|(12|twelve).month continuous|continuous coverage'],),
 Q('343','Periodic renewal of CHIP eligibility','S',[r'renewal|redetermination|recertification|annual review|ex parte'],),
 Q('348','Determinations of CHIP eligibility by other insurance affordability programs','FS',[r'(exchange|marketplace|medicaid).{0,120}(determin|refer|transfer).{0,80}CHIP|CHIP.{0,120}(exchange|marketplace).{0,80}(determin|refer|transfer)'],conf='low'),
 Q('350','Eligibility screening and enrollment in other insurance affordability programs (Medicaid screen)','S',[r'screen(ed|ing)? for medicaid|medicaid.{0,60}screen|not eligible for medicaid|ineligible for medicaid|insurance affordability program'],),
 Q('351','Coordination involving appeals entities','F'), Q('353','Monitoring and evaluation of screening process','F'),
 Q('355','Presumptive eligibility for children (state option)','S',[r'presumptive'],),
 Q('360','Deemed newborn children','S',[r'newborn'],),
 Q('370','Alignment with Exchange initial open enrollment period','F'),
 Q('380','Eligibility verification','S',[r'verif'],),
 Q('401','Basis, scope and applicability (subpart D benefits)','F'), Q('402','Definition of child health assistance','F'),
 Q('410','Health benefits coverage options (benchmark, benchmark-equivalent, existing, Secretary-approved)','S',[r'benchmark|benefit package|covered (services|benefits)|schedule of benefits|scope of (services|benefits)'],conf='low',fam=CPLAN+' / member handbook'),
 Q('420','Benchmark health benefits coverage','F'), Q('430','Benchmark-equivalent coverage','F'), Q('431','Actuarial report for benchmark-equivalent coverage','F'), Q('440','Existing comprehensive state-based coverage','F'), Q('450','Secretary-approved coverage','F'), Q('470','Prohibited coverage','F'), Q('475','Limitations on coverage: abortions','F'), Q('480','Prohibited coverage limitations; preexisting conditions','F'), Q('490','Delivery and utilization control systems','F'), Q('495','State assurance of access to care and quality','F'), Q('496','Parity in mental health and substance use disorder benefits','F'),
 Q('500','Basis, scope and applicability (subpart E cost sharing)','F'),
 Q('505','General state plan requirements for cost sharing (whether the state imposes any)','S',[r'cost.sharing|co-?pay(ment)?|premium|enrollment fee'],),
 Q('510','Premiums, enrollment fees or similar fees (state schedule)','S',[r'premium|enrollment fee|annual fee'],pe='yes for 17 states (states/<xx>/hhs/chip/premium*, enrollment_fee*)',fam=MAN_TAB),
 Q('515','Co-payments, coinsurance, deductibles (state schedule)','S',[r'co-?pay(ment)?s?\b|coinsurance|deductible'],),
 Q('520','Cost sharing for well-baby and well-child care (prohibited)','S',[r'well.?(baby|child)|preventive (services|care).{0,120}(no|without|exempt|free)|(no|without|exempt).{0,60}(co-?pay|cost.sharing).{0,120}(preventive|well)'],conf='low'),
 Q('525','Public schedule of cost sharing','FS',[r'public schedule|schedule of (cost.sharing|co-?pay|premium)'],conf='low'),
 Q('530','General cost-sharing protection for lower-income children','F'),
 Q('535','Cost-sharing protection for American Indians and Alaska Natives','S',[r'american indian|alaska native|\bAI/AN\b|tribal'],),
 Q('540','Cost-sharing charges for children at or below 150% FPL (nominal)','S',[r'150 ?(%|percent).{0,200}(co-?pay|cost.sharing|premium|nominal)|(co-?pay|cost.sharing|premium).{0,200}150 ?(%|percent)'],conf='low'),
 Q('555','Maximum allowable cost-sharing charges for children 101-150% FPL','F'),
 Q('560','Cumulative cost-sharing maximum (5% of family income)','S',[r'5 ?(%|percent).{0,120}(family |household |annual |gross )?income|cumulative (cost.sharing )?maximum|(cost.sharing|co-?pay|premium).{0,160}(cap|maximum|limit).{0,80}(5|five) ?(%|percent)'],pe='yes (cost_sharing/cap/rate)'),
 Q('570','Disenrollment protections (premium nonpayment, grace period, lock-out)','S',[r'disenroll|non-?payment (of premium)?|failure to pay|grace period|lock-?out'],),
 Q('600','Purpose and basis (subpart F payments)','F'), Q('602','Applicability','F'), Q('606','Conditions for state allotments and federal payments','F'), Q('608','State allotments prior to FY 2009','F'), Q('609','State allotments after FY 2008','F'), Q('610','Availability of allotments prior to FY 2009','F'), Q('611','Availability of allotments after FY 2008','F'), Q('614','General payment process','F'), Q('616','Application and tracking of payments','F'), Q('618','Ten percent limit on certain expenditures','F'), Q('622','Rate of FFP (enhanced FMAP)','F',pe='yes (variables chip_federal_share)'), Q('626','Prevention of duplicate payments','F'), Q('628','Other applicable federal regulations','F'), Q('630','Grants procedures','F'),
 Q('700','Basis, scope and applicability (subpart G)','F'), Q('710','Strategic objectives and performance goals (state plan)','F'), Q('720','Data collection, records and reports assurance','F'), Q('730','Beneficiary access to and exchange of data','F'), Q('731','Provider and payer access to health data','F'), Q('732','Prior authorization requirements','F'), Q('740','State expenditures and statistical reports','F'), Q('750','Annual report','F'), Q('760','Provider directory information','F'), Q('770','Reporting on health care quality measures','F'),
 Q('800','Basis, scope and applicability (subpart H substitution)','F'),
 Q('805','Procedures to address substitution under group health plans (crowd-out; waiting periods)','S',[r'substitution|crowd.?out|(employer.sponsored|group health).{0,120}(drop|waiting|substitut)|(drop|dropped|voluntarily terminat).{0,80}(coverage|insurance)'],),
 Q('810','Premium assistance programs: protections against substitution','FS',[r'premium assistance'],),
 Q('900','Basis, scope and applicability (subpart I program integrity)','F'), Q('910','State program administration','F'), Q('915','Fraud detection and investigation','F'), Q('925','Preliminary investigation','F'), Q('930','Full investigation, resolution and reporting','F'), Q('935','Sanctions and related penalties','F'), Q('940','Procurement standards','F'), Q('945','Certification for contracts and proposals','F'), Q('950','Contract and payment requirements','F'),
 Q('960','Reporting changes in eligibility and redetermining eligibility','S',[r'change(s)? in (circumstance|income|eligibility)|report(ing)? (a )?change'],),
 Q('965','Documentation','F'), Q('980','Verification of enrollment and provider services received','F'), Q('985','Integrity of professional advice to enrollees','F'), Q('990','Provider and supplier screening','F'),
 Q('1000','Basis, scope and applicability (subpart J waivers)','F'), Q('1003','CMS review of waiver requests','F'),
 Q('1005','Cost-effective coverage through a community-based health delivery system (waiver option)','FS',[r'community.based health (delivery|plan)'],conf='low'),
 Q('1010','Purchase of family coverage (waiver option)','FS',[r'purchase of family coverage|family coverage.{0,80}(waiver|purchase)'],conf='low'),
 Q('1015','Cost-effectiveness','F'),
 Q('1100','Basis, scope and applicability (subpart K protections)','F'),
 Q('1110','Privacy protections','FS',[r'privacy|confidential'],conf='low'),
 Q('1120','Description of the review process (appeals/grievances) in the state plan','S',[r'review process|appeal|fair hearing|grievance|request(ing)? a (review|hearing)'],),
 Q('1130','Matters subject to review','F'), Q('1140','Core elements of review','F'), Q('1150','Impartial review','F'), Q('1160','Time frames for review','F'), Q('1170','Continuation of enrollment pending review','F'), Q('1180','Notice','F'), Q('1190','Review procedures with premium assistance','F'),
 Q('1200','Basis, scope and applicability (subpart L managed care)','F'), Q('1201','Standard contract requirements','F'), Q('1203','Rate development standards and MLR','F'), Q('1206','NEMT PAHPs','F'), Q('1207','Information requirements','F'), Q('1208','Provider discrimination prohibited','F'), Q('1209','Contracts involving Indians and IHCPs','F'), Q('1210','Enrollment process','F'), Q('1212','Disenrollment','F'), Q('1214','Conflict of interest safeguards','F'), Q('1216','Continued services to enrollees','F'), Q('1218','Network adequacy standards','F'), Q('1220','Enrollee rights','F'), Q('1222','Provider-enrollee communication','F'), Q('1224','Marketing activities','F'), Q('1226','Liability for payment','F'), Q('1228','Emergency and poststabilization services','F'), Q('1230','Access standards','F'), Q('1233','Structure and operation standards','F'), Q('1240','Quality measurement and improvement','F'), Q('1250','External quality review','F'), Q('1260','Grievance system','F'), Q('1270','Sanctions','F'), Q('1280','Conditions necessary to contract as an MCO, PAHP or PIHP','F'), Q('1285','Program integrity safeguards','F'),
]
# CHIP: Medicaid rules that govern Medicaid-expansion CHIP children (cross-references)
C += [
 E('C-435-229','42 CFR 435.229 (via 457.70): optional targeted low-income children under the Medicaid state plan (M-CHIP group; state income standard)','42 CFR 435.229; 42 U.S.C. 1396a(a)(10)(A)(ii)(XIV)','S',MAN,'yes (via gov/hhs/medicaid child income limits)','us-xx cms eligibility-levels wrappers',[r'targeted low.income child|title XXI|medicaid expansion (CHIP|program)|M-?CHIP|CHIP.{0,60}medicaid expansion|expansion CHIP|(CHIP|title XXI).{0,80}funded'],'high','',cfr_path='us/regulation/42/435/229',chip_context=True,fallback='us/form/cms/medicaid-chip-bhp-eligibility-levels/block-1'),
 E('C-435-118','42 CFR 435.118 (via 457.70): Medicaid children income standards by age band that define the M-CHIP band','42 CFR 435.118','S',MAN_TAB,'yes','us-xx cms eligibility-levels wrappers',[r'(infants?|children).{0,60}under (age )?19|under (age )?19|age[sd]? (0|1|6).{0,20}(to|through|-).{0,10}(1|5|18|19)'],'high','',cfr_path='us/regulation/42/435/118',fallback='us/form/cms/medicaid-chip-bhp-eligibility-levels/block-1'),
 E('C-435-603','42 CFR 435.603 (via 457.315): MAGI household and income rules applied to CHIP','42 CFR 435.603','S',MAN,'yes','us:policies/medicaid/magi_household_income_pipeline',[r'modified adjusted gross income|\bMAGI\b'],'high','',cfr_path='us/regulation/42/435/603'),
 E('C-435-926','42 CFR 435.926 (via 457.342): continuous eligibility for M-CHIP children','42 CFR 435.926','S',MAN,'no','no',[r'continuous eligibility|(12|twelve).month continuous|continuous coverage'],'high','',cfr_path='us/regulation/42/435/926'),
 E('C-435-1102','42 CFR 435.1102 (via 457.355): presumptive eligibility for M-CHIP children','42 CFR 435.1102','S',MAN,'no','no',[r'presumptive'],'high','',cfr_path='us/regulation/42/435/1102',chip_context=True),
 E('C-435-117','42 CFR 435.117 (via 457.360): deemed newborns','42 CFR 435.117','S',MAN,'no','no',[r'newborn'],'high','',cfr_path='us/regulation/42/435/117',chip_context=True),
 E('C-SS-STATE-PLAN','Approved CHIP state plan (current compiled CMS template)','42 U.S.C. 1397ff; 42 CFR 457.50','S',CPLAN,'no','no',[],'high','No CHIP state plan is held for any state; medicaid.gov posts every approved plan (https://www.medicaid.gov/chip/state-program-information).',state_plan=True),
 E('C-SS-INCOME-PREMIUM-TABLE','Current-year CHIP income bands and premium/enrollment-fee schedule (agency table or notice)','42 CFR 457.310, 457.510; state plan','S',MAN_TAB,'yes (child/income_limit; states/<xx>/hhs/chip/premium*)','us-xx:policies/cms/<state>-chip-eligibility',[r'(income (limit|standard|level|guideline|chart|table)s?|premium).{0,200}(%|percent).{0,40}(FPL|poverty)|(%|percent) (of (the )?)?(FPL|federal poverty).{0,200}(premium|income (limit|standard|level))'],'high','Federal fallback: the CMS eligibility-levels table (2023-12-01) carries the separate-CHIP upper income limit for every state but no premium amounts.',fallback='us/form/cms/medicaid-chip-bhp-eligibility-levels/block-1',chip_context=True),
 E('C-SS-DISQUALIFYING-COVERAGE','Disqualifying (creditable / group health / employer-sponsored) coverage rule as applied by the state','42 U.S.C. 1397jj(b)(1)(C), (b)(2); 42 CFR 457.310(b)(2)','S',MAN,'yes (disqualifying_health_coverage; variable has_chip_disqualifying_health_coverage)','no',[r'(other|creditable|group|employer.sponsored|private) health (insurance|coverage|plan)|creditable coverage|employer.sponsored (insurance|coverage)|\bESI\b|state employee (health )?(benefit|plan|coverage)'],'high','',chip_context=True),
]

# ================================================================ pass 2 overrides (2026-09-12)
# The first pass marked cells PRESENT on single-word patterns ('pregnan', 'premium', 'newborn',
# 'verif') and on hits in SNAP/TANF/CalFresh scopes with Medicaid words nearby. This pass:
#  - search_patterns  = strong patterns: a hit in the state's Medicaid/CHIP scopes (or the pointer
#                       scopes for done-by-pointer states) is PRESENT;
#  - weak_patterns    = candidate patterns: a hit is REVIEW with the candidate cited;
#  - needs_number     = a strong hit also needs a value signal in the provision body
#                       (percent of FPL, dollar amount) because the element is a state-set value;
#  - neg_context      = a hit whose +-120-char window matches this (and not the program) is
#                       rejected (Medicare premiums, ACA individual-responsibility exemptions);
#  - plan_family      = the CMS-posted state plan section that carries the election when the
#                       state's own text does not (no hit -> EXTRACTABLE naming that family).
MPLAN = {'groups': 'Medicaid state plan attachment 2.2-A (groups covered) on medicaid.gov',
         'financial': 'Medicaid state plan attachment 2.6-A and supplements (financial eligibility, income and resource standards) on medicaid.gov',
         'mn': 'Medicaid state plan attachment 2.6-A supplement (medically needy income and resource levels) on medicaid.gov',
         'cost': 'Medicaid state plan attachment 4.18-A to 4.18-F (premiums and cost sharing) on medicaid.gov',
         'nonfin': 'Medicaid state plan sections 2.1-2.5 (application, residency, blindness, disability) on medicaid.gov',
         'verif': 'MAGI-based verification plan (state-submitted, posted by CMS on medicaid.gov)',
         'pe': 'Medicaid state plan presumptive-eligibility pages (S-series eligibility SPAs) on medicaid.gov',
         'ce': 'community-engagement implementation SPA or 1115 terms (not yet posted for any state; IFC compliance date 2027-01-01)',
         'ltc': 'Medicaid state plan attachment 2.6-A supplements 8a-8c and 9-12 (post-eligibility, transfers, trusts, estate recovery, spousal impoverishment) on medicaid.gov'}
CPLANF = {'elig': 'CHIP state plan sections 4.1-4.4 (eligibility standards and methodology) on medicaid.gov',
          'cost': 'CHIP state plan section 8 (cost sharing and payment) on medicaid.gov',
          'benefits': 'CHIP state plan section 6 (coverage requirements) on medicaid.gov',
          'crowd': 'CHIP state plan section 4.4 (substitution of coverage) on medicaid.gov',
          'review': 'CHIP state plan section 9 (strategic objectives) and CS-series eligibility SPAs on medicaid.gov',
          'proc': 'CHIP state plan sections 4 and 5 (eligibility procedures, outreach, coordination) on medicaid.gov'}
NUM = r'\d{1,3}\s?(%|percent)|\$\s?\d|federal poverty|\bFPL\b|\bFPIG\b|\bFPG\b|poverty (level|guideline|line)'
MEDICARE_NEG = r'medicare|part [abd]\b|\bQMB\b|\bSLMB\b|\bQI\b|buy-?in for medicare'
ACA_NEG = r'individual (shared )?responsibility|marketplace|exchange|qualified health plan|\bAPTC\b|premium tax credit|premium assistance'
CE_NEG = r'waiver|day support|supported employment|employment services|community coaching|residential|habilitation|\bDD\b|developmental'

OVR = {
 # ---- Medicaid statute
 'M-ST-1396a-a34': dict(search_patterns=[r'retroactive (medicaid|medical assistance|coverage|eligibility|period|months?|assistance|benefits?)|(three|3) (calendar )?months? (prior to|before|preceding|immediately preceding) the (month of |date of )?(application|filing)'], plan_family=MPLAN['nonfin']),
 'M-ST-1396a-m': dict(search_patterns=[], weak_patterns=[r'poverty.level (aged|disabled|elderly)|100 ?(%|percent) (of the )?(FPL|federal poverty).{0,80}(aged|disabled|65)|(aged|disabled).{0,80}100 ?(%|percent) (of the )?(FPL|federal poverty)'], plan_family=MPLAN['groups']),
 'M-ST-1396b-v': dict(plan_family=MPLAN['groups']),
 'M-ST-1396p-c': dict(plan_family=MPLAN['ltc']),
 'M-ST-1396p-b': dict(plan_family=MPLAN['ltc']),
 'M-ST-1396p-d': dict(plan_family=MPLAN['ltc']),
 'M-ST-1396p-f': dict(search_patterns=[r'home equity (limit|interest|value|cap|standard|threshold)|equity (interest |value )?in (the |their |his or her |a )?home.{0,120}(exceed|limit|\$|more than|greater than)'], weak_patterns=[r'home equity'], plan_family=MPLAN['ltc']),
 'M-ST-1396r-5': dict(plan_family=MPLAN['ltc']),
 'M-ST-1396r-6': dict(search_patterns=[r'transitional medical assistance|transitional medicaid|\bTMA\b|extended medicaid|(4|four|6|six|12|twelve).month (extended|extension|transitional)|medical extension'], plan_family=MPLAN['groups']),
 'M-ST-1396a-a10Aii-buyin': dict(plan_family=MPLAN['groups']),
 'M-ST-1315': dict(search_patterns=[], weak_patterns=[r'1115 (demonstration|waiver)|section 1115|demonstration (waiver|project|program)'], notes_add='A mention of a section 1115 demonstration is only a candidate; the terms live in the CMS special terms and conditions, not in the manual.'),
 'M-ST-1396a-a3': dict(plan_family='Medicaid state plan section 4.2 (fair hearings) on medicaid.gov'),
 'M-ST-1396a-a25': dict(plan_family='Medicaid state plan section 4.22 (third party liability) on medicaid.gov'),
 'M-ST-1396a-a17': dict(plan_family=MPLAN['financial']),
 # ---- 42 CFR 435 subpart B-D groups (state elects / sets the standard)
 'M-435-4': dict(plan_family=MPLAN['groups']),
 'M-435-110': dict(needs_number=True, plan_family=MPLAN['financial']),
 'M-435-112': dict(plan_family=MPLAN['groups']),
 'M-435-115': dict(plan_family=MPLAN['groups']),
 'M-435-116': dict(search_patterns=[r'pregnan\w*'], needs_number=True, plan_family=MPLAN['financial']),
 'M-435-117': dict(search_patterns=[r'deemed newborn|newborn.{0,150}(deemed|automatically|continuous(ly)? eligib|eligible (until|through|for (the )?(first )?(year|12 months|twelve months))|remains eligible)|continuously eligible newborn|child born to a (woman|mother|pregnant).{0,120}(medicaid|medical assistance|eligible)'], weak_patterns=[r'newborn'], plan_family=MPLAN['groups']),
 'M-435-118': dict(needs_number=True, plan_family=MPLAN['financial']),
 'M-435-119': dict(needs_number=True, plan_family=MPLAN['groups']),
 'M-435-120': dict(plan_family=MPLAN['groups']),
 'M-435-121': dict(plan_family=MPLAN['groups']),
 'M-435-122': dict(plan_family=MPLAN['groups']),
 'M-435-123': dict(plan_family=MPLAN['groups']), 'M-435-124': dict(plan_family=MPLAN['groups']), 'M-435-125': dict(plan_family=MPLAN['groups']), 'M-435-126': dict(plan_family=MPLAN['groups']),
 'M-435-130': dict(plan_family=MPLAN['groups']), 'M-435-131': dict(plan_family=MPLAN['groups']), 'M-435-132': dict(plan_family=MPLAN['groups']), 'M-435-133': dict(plan_family=MPLAN['groups']), 'M-435-134': dict(plan_family=MPLAN['groups']), 'M-435-135': dict(plan_family=MPLAN['groups']), 'M-435-137': dict(plan_family=MPLAN['groups']), 'M-435-138': dict(plan_family=MPLAN['groups']), 'M-435-139': dict(plan_family=MPLAN['groups']),
 'M-435-145': dict(search_patterns=[r'(title )?IV-?E\b|foster care (maintenance )?payments?.{0,150}(medicaid|medical assistance|eligib|automatically)|(adoption assistance|guardianship assistance).{0,150}(medicaid|medical assistance|eligib|automatically)|(medicaid|medical assistance).{0,120}(foster care|adoption assistance)'], plan_family=MPLAN['groups']),
 'M-435-150': dict(search_patterns=[r'former foster care|aged out of foster care|(in|receiving) foster care.{0,120}(18th birthday|age 18|turned 18|attain(ed|ing) (age )?18).{0,160}(26|twenty-six)|(under (age )?26|age 26|26th birthday).{0,160}foster care'], weak_patterns=[r'foster care'], plan_family=MPLAN['groups']),
 'M-435-170': dict(search_patterns=[r'postpartum (period|coverage|care|eligibility)|(12|twelve|60|sixty).(month|day)s? (postpartum|after (the )?(end of )?pregnancy)|postpartum.{0,80}(12|twelve|60|sixty).(month|day)'], weak_patterns=[r'postpartum'], plan_family=MPLAN['groups']),
 'M-435-172': dict(plan_family=MPLAN['groups']),
 'M-435-210': dict(plan_family=MPLAN['groups']), 'M-435-211': dict(plan_family=MPLAN['groups']), 'M-435-213': dict(plan_family=MPLAN['groups']), 'M-435-214': dict(plan_family=MPLAN['groups']), 'M-435-215': dict(plan_family=MPLAN['groups']), 'M-435-217': dict(plan_family=MPLAN['groups']), 'M-435-218': dict(plan_family=MPLAN['groups']), 'M-435-219': dict(plan_family=MPLAN['groups']), 'M-435-220': dict(plan_family=MPLAN['groups']), 'M-435-222': dict(plan_family=MPLAN['groups']), 'M-435-223': dict(plan_family=MPLAN['groups']), 'M-435-225': dict(plan_family=MPLAN['groups']), 'M-435-226': dict(plan_family=MPLAN['groups']), 'M-435-227': dict(plan_family=MPLAN['groups']), 'M-435-229': dict(plan_family=MPLAN['groups']), 'M-435-230': dict(plan_family=MPLAN['groups']), 'M-435-232': dict(plan_family=MPLAN['groups']), 'M-435-234': dict(plan_family=MPLAN['groups']),
 'M-435-236': dict(search_patterns=[r'special income (level|limit|standard|group)|300 ?(%|percent) (of )?(the )?(SSI|federal benefit rate|FBR|maximum SSI)|institutional(ized)? (income )?(cap|limit|standard)'], plan_family=MPLAN['groups']),
 'M-435-301': dict(plan_family=MPLAN['groups']), 'M-435-308': dict(plan_family=MPLAN['groups']), 'M-435-310': dict(plan_family=MPLAN['groups']), 'M-435-320': dict(plan_family=MPLAN['groups']), 'M-435-322': dict(plan_family=MPLAN['groups']), 'M-435-324': dict(plan_family=MPLAN['groups']), 'M-435-330': dict(plan_family=MPLAN['groups']),
 # ---- subpart E-F non-financial
 'M-435-403': dict(plan_family=MPLAN['nonfin']), 'M-435-406': dict(plan_family=MPLAN['groups']), 'M-435-407': dict(plan_family=MPLAN['nonfin']),
 'M-435-520': dict(plan_family=MPLAN['nonfin']), 'M-435-530': dict(plan_family=MPLAN['nonfin']), 'M-435-531': dict(plan_family=MPLAN['nonfin']), 'M-435-540': dict(plan_family=MPLAN['nonfin']), 'M-435-541': dict(plan_family=MPLAN['nonfin']),
 # ---- community engagement: strong = 'community engagement'; 'work requirement' alone is a candidate
 'M-435-551': dict(search_patterns=[r'community engagement'], weak_patterns=[r'work requirement'], neg_context=CE_NEG, plan_family=MPLAN['ce']),
 'M-435-552': dict(search_patterns=[r'community engagement.{0,300}(80|eighty) hours|(80|eighty) hours.{0,300}community engagement'], weak_patterns=[r'(80|eighty) hours'], neg_context=CE_NEG, plan_family=MPLAN['ce']),
 'M-435-553': dict(neg_context=CE_NEG, plan_family=MPLAN['ce']), 'M-435-554': dict(neg_context=CE_NEG, plan_family=MPLAN['ce']), 'M-435-555': dict(neg_context=CE_NEG, plan_family=MPLAN['ce']), 'M-435-556': dict(neg_context=CE_NEG, plan_family=MPLAN['ce']), 'M-435-557': dict(neg_context=CE_NEG, plan_family=MPLAN['ce']), 'M-435-558': dict(neg_context=CE_NEG, plan_family=MPLAN['ce']), 'M-435-559': dict(neg_context=CE_NEG, plan_family=MPLAN['ce']), 'M-435-561': dict(neg_context=CE_NEG, plan_family=MPLAN['ce']),
 # ---- subpart G-I financial
 'M-435-601': dict(plan_family=MPLAN['financial']), 'M-435-602': dict(plan_family=MPLAN['financial']), 'M-435-603': dict(plan_family=MPLAN['financial']), 'M-435-610': dict(plan_family='Medicaid state plan section 4.22 on medicaid.gov'),
 'M-435-622': dict(plan_family=MPLAN['financial']), 'M-435-631': dict(plan_family=MPLAN['financial']),
 'M-435-725': dict(plan_family=MPLAN['ltc']), 'M-435-726': dict(plan_family=MPLAN['ltc']), 'M-435-733': dict(plan_family=MPLAN['ltc']), 'M-435-735': dict(plan_family=MPLAN['ltc']),
 'M-435-811': dict(needs_number=True, plan_family=MPLAN['mn']), 'M-435-831': dict(plan_family=MPLAN['mn']), 'M-435-832': dict(plan_family=MPLAN['mn']), 'M-435-840': dict(needs_number=True, plan_family=MPLAN['mn']), 'M-435-845': dict(plan_family=MPLAN['mn']),
 # ---- subpart J process
 'M-435-907': dict(plan_family=MPLAN['nonfin']), 'M-435-910': dict(plan_family=MPLAN['nonfin']),
 'M-435-915': dict(search_patterns=[r'effective date of (eligibility|coverage|medicaid|medical assistance)|(begin(ning)?|start) date of (eligibility|coverage|medicaid)|eligibility (begins|shall begin|will begin|may begin)|retroactive (coverage|eligibility|period|months?|medicaid|medical assistance)'], plan_family=MPLAN['nonfin']),
 'M-435-916': dict(search_patterns=[r'\brenewals?\b|redetermination|recertification|ex parte|annual (review|redetermination)|passive renewal'], plan_family=MPLAN['nonfin']),
 'M-435-945': dict(plan_family=MPLAN['verif']), 'M-435-948': dict(plan_family=MPLAN['verif']), 'M-435-949': dict(plan_family=MPLAN['verif']), 'M-435-952': dict(plan_family=MPLAN['verif']), 'M-435-956': dict(plan_family=MPLAN['verif']), 'M-435-920': dict(plan_family=MPLAN['verif']),
 'M-435-926': dict(plan_family=MPLAN['groups']),
 'M-435-1102': dict(search_patterns=[r'presumptive(ly)? eligib.{0,200}(child|kids)|(child|kids).{0,200}presumptive(ly)? eligib'], weak_patterns=[r'presumptive(ly)? eligib'], plan_family=MPLAN['pe']),
 'M-435-1103': dict(search_patterns=[r'presumptive(ly)? eligib.{0,200}(pregnan|adult|parent|caretaker|family planning|breast)|(pregnan|adult).{0,200}presumptive(ly)? eligib'], weak_patterns=[r'presumptive(ly)? eligib'], plan_family=MPLAN['pe']),
 'M-435-1110': dict(search_patterns=[r'hospital presumptive|presumptive(ly)? eligib.{0,150}hospital|qualified hospital|\bHPE\b'], weak_patterns=[r'presumptive(ly)? eligib'], plan_family=MPLAN['pe']),
 # ---- 447 cost sharing
 'M-447-52': dict(search_patterns=[r'\bco-?pay(ment)?s?\b|cost.sharing|\bcoinsurance\b'], neg_context=MEDICARE_NEG, plan_family=MPLAN['cost']),
 'M-447-53': dict(neg_context=MEDICARE_NEG, plan_family=MPLAN['cost']),
 'M-447-54': dict(plan_family=MPLAN['cost']),
 'M-447-55': dict(search_patterns=[r'(medicaid|medical assistance|program|buy-?in|enrollment|monthly|sliding.scale|premium.based) premiums?\b|premiums? (amounts?|schedule|payments?|are|is|shall|will|must) (be )?(charged|required|paid|due|\$|based)|\$\s?\d[\d,.]*\s?(per|a|/) ?month.{0,80}premium|premiums?.{0,100}\$\s?\d'], weak_patterns=[r'premium'], neg_context=MEDICARE_NEG, plan_family=MPLAN['cost']),
 'M-447-56': dict(search_patterns=[r'(cost.sharing|co-?pay(ment)?s?|premiums?).{0,200}(exempt|5 ?(%|percent)|five percent|aggregate (limit|cap|maximum)|out.of.pocket (maximum|limit))|(exempt|5 ?(%|percent) of.{0,40}income|aggregate (limit|cap)).{0,150}(cost.sharing|co-?pay|premium)'], neg_context=ACA_NEG+'|'+MEDICARE_NEG, plan_family=MPLAN['cost']),
 'M-447-57': dict(plan_family=MPLAN['cost']),
 # ---- state structure
 'M-SS-INCOME-TABLE': dict(needs_number=True, no_fallback=True, notes_add='Pass 2: the CMS 2023-12-01 compilation does not satisfy a current-year table; it is cited in the evidence note but the cell stays a gap.'),
 'M-SS-RESOURCE-TABLE': dict(needs_number=True, plan_family=MPLAN['financial']),
 'M-SS-BENEFITS': dict(plan_family='Medicaid state plan attachment 3.1-A/B (amount, duration and scope) on medicaid.gov'),
 'M-SS-HEARINGS': dict(plan_family='Medicaid state plan section 4.2 (fair hearings) on medicaid.gov'),
 # ================ CHIP
 'C-ST-1397jj-b': dict(plan_family=CPLANF['elig']),
 'C-ST-1397ll': dict(search_patterns=[r'pregnan\w*'], needs_number=True, plan_family=CPLANF['elig']),
 'C-ST-FCEP': dict(plan_family=CPLANF['elig']),
 'C-457-70': dict(plan_family=CPLANF['elig']),
 'C-457-80': dict(plan_family=CPLANF['proc']), 'C-457-90': dict(plan_family=CPLANF['proc']), 'C-457-110': dict(plan_family=CPLANF['proc']), 'C-457-125': dict(plan_family=CPLANF['elig']),
 'C-457-310': dict(needs_number=True, plan_family=CPLANF['elig']),
 'C-457-315': dict(plan_family=CPLANF['elig']),
 'C-457-320-a': dict(plan_family=CPLANF['elig']), 'C-457-320-b': dict(plan_family=CPLANF['crowd']),
 'C-457-330': dict(plan_family=CPLANF['proc']),
 'C-457-340': dict(plan_family=CPLANF['proc']),
 'C-457-342': dict(plan_family=CPLANF['elig']),
 'C-457-343': dict(search_patterns=[r'\brenewals?\b|redetermination|recertification|annual (review|redetermination)|ex parte'], plan_family=CPLANF['proc']),
 'C-457-348': dict(plan_family=CPLANF['proc']), 'C-457-350': dict(plan_family=CPLANF['proc']),
 'C-457-355': dict(search_patterns=[r'presumptive(ly)? eligib'], plan_family=CPLANF['elig']),
 'C-457-360': dict(search_patterns=[r'deemed newborn|newborn.{0,150}(deemed|automatically|continuous(ly)? eligib|eligible (until|through|for (the )?(first )?(year|12 months|twelve months))|remains eligible)|child born to a (woman|mother|pregnant).{0,120}(chip|medicaid|eligible)'], weak_patterns=[r'newborn'], plan_family=CPLANF['elig']),
 'C-457-380': dict(search_patterns=[r'verif(y|ied|ication) (of )?(income|eligibility|citizenship|immigration|information|household|residency|insurance|the information)|verification (plan|requirements?|procedures?|standards?|sources?)|electronic (data )?(sources?|verification)|self.attestation'], weak_patterns=[r'verif'], plan_family=CPLANF['proc']),
 'C-457-410': dict(plan_family=CPLANF['benefits']),
 'C-457-505': dict(search_patterns=[r'cost.sharing|\bco-?pay(ment)?s?\b|\bpremiums?\b|enrollment fee'], neg_context=MEDICARE_NEG+'|'+ACA_NEG, plan_family=CPLANF['cost']),
 'C-457-510': dict(search_patterns=[r'(chip|program|monthly|annual|family|sliding.scale|premium.based) premiums?\b|premiums? (amounts?|schedule|payments?|are|is|shall|will|must) (be )?(charged|required|paid|due|\$|based)|enrollment fee|\$\s?\d[\d,.]*\s?(per|a|/) ?(month|year|child|family).{0,80}(premium|fee)|(premium|fee)s?.{0,100}\$\s?\d'], weak_patterns=[r'premium'], needs_number=True, neg_context=MEDICARE_NEG+'|'+ACA_NEG, plan_family=CPLANF['cost']),
 'C-457-515': dict(search_patterns=[r'\bco-?pay(ment)?s?\b|\bcoinsurance\b|\bdeductibles?\b'], neg_context=MEDICARE_NEG+'|'+ACA_NEG, plan_family=CPLANF['cost']),
 'C-457-520': dict(plan_family=CPLANF['cost']), 'C-457-525': dict(plan_family=CPLANF['cost']), 'C-457-535': dict(plan_family=CPLANF['cost']), 'C-457-540': dict(plan_family=CPLANF['cost']),
 'C-457-560': dict(neg_context=ACA_NEG, plan_family=CPLANF['cost']),
 'C-457-570': dict(search_patterns=[r'disenroll|non-?payment of (the )?premium|failure to pay (the |a )?premium|grace period|lock-?out'], plan_family=CPLANF['cost']),
 'C-457-805': dict(plan_family=CPLANF['crowd']), 'C-457-810': dict(plan_family=CPLANF['crowd']),
 'C-457-960': dict(plan_family=CPLANF['proc']),
 'C-457-1005': dict(plan_family=CPLANF['benefits']), 'C-457-1010': dict(plan_family=CPLANF['benefits']),
 'C-457-1110': dict(plan_family=CPLANF['review']), 'C-457-1120': dict(plan_family=CPLANF['review']),
 'C-435-229': dict(plan_family=MPLAN['groups']), 'C-435-118': dict(needs_number=True, plan_family=MPLAN['financial']), 'C-435-603': dict(plan_family=MPLAN['financial']), 'C-435-926': dict(plan_family=MPLAN['groups']),
 'C-435-1102': dict(search_patterns=[r'presumptive(ly)? eligib'], plan_family=MPLAN['pe']),
 'C-435-117': dict(search_patterns=[r'deemed newborn|newborn.{0,150}(deemed|automatically|continuous(ly)? eligib|eligible (until|through|for (the )?(first )?(year|12 months|twelve months))|remains eligible)|child born to a (woman|mother|pregnant).{0,120}(chip|medicaid|eligible)'], weak_patterns=[r'newborn'], plan_family=MPLAN['groups']),
 'C-SS-INCOME-PREMIUM-TABLE': dict(needs_number=True, no_fallback=True, notes_add='Pass 2: the CMS 2023-12-01 compilation does not satisfy a current-year table; it is cited in the evidence note but the cell stays a gap.'),
 'C-SS-DISQUALIFYING-COVERAGE': dict(plan_family=CPLANF['crowd']),
}

# Corrections to first-pass notes established by reading the corpus on 2026-09-12
NOTE_FIX = {
 'M-ST-8usc-1611': 'Corrected 2026-09-12: 8 U.S.C. 1612, 1613 and 1641 are held (us/statute/8/1612, 1613, 1641 in the released 2026-07-13-recovery statute scope); 8 U.S.C. 1611 is not. State election (CHIPRA 214 lawfully residing children and pregnant women) is element 435.406.',
 'M-ST-1396u-1': 'Held (us/statute/42/1396u–1, en-dash in the citation path; a, b, c, d, e, f, g, h, i).',
 'M-ST-1396a-a17': 'Statute subsection not held (the Medicaid statute scope holds 1396a(a)(10) only under (a), plus (e)(1)-(16), (f), (l)(1)-(4), (m)(1)-(4)). State-level: which disregards/methodologies the state elected.',
}

def apply_overrides(elems):
    for e in elems:
        e.setdefault('weak_patterns', [])
        o = OVR.get(e['id'])
        if o:
            for k, v in o.items():
                if k == 'notes_add': e['notes'] = (e['notes'] + ' ' + v).strip()
                else: e[k] = v
        if e['id'] in NOTE_FIX: e['notes'] = NOTE_FIX[e['id']]
        # first-pass low-confidence patterns become weak (candidate) patterns
        if e.get('search_confidence') == 'low' and e.get('search_patterns') and not e['weak_patterns']:
            e['weak_patterns'] = e['search_patterns']; e['search_patterns'] = []
        e['search_confidence'] = 'high' if e['search_patterns'] else ('low' if e['weak_patterns'] else 'n/a')
    return elems

def dump(prog, elems, extra):
    doc = {'program': prog, 'date': '2026-09-11', 'schema_version': 2}
    doc.update(extra)
    doc['element_count'] = len(elems)
    doc['elements'] = elems
    return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=140)

if __name__ == '__main__':
    out = sys.argv[1]
    common = {
      'method': 'Elements are derived from the program\'s legal structure, not from a model. (1) 42 U.S.C. 1396a and the sections it invokes (1396b(v), 1396d, 1396o, 1396p, 1396r-5, 1396r-6, 1396u-1, 1320b-7, 1382-1382c, 8 U.S.C. 1611-1641, 1315) / 42 U.S.C. 1397aa-1397mm. (2) Every section of 42 CFR 435 (as held in us/regulation/2026-06-25-title-42-part-435 plus the CMS-2454-IFC 435.550-563 scope), 436 (us/regulation/2026-09-11-title-42-part-436), 447 subpart A (eCFR structure 2026-09-09; not held) and 457 (us/regulation/2026-07-13-recovery-r2026-07-17-dedup). (3) The structure of the state rulebooks held in the corpus (tables of contents of the 2026-09-10 Medicaid and CHIP state scopes: definitions, application, coverage groups, non-financial, household/assistance unit, income, resources, MAGI and non-MAGI budgeting, LTC/HCBS post-eligibility, transfers and trusts, spousal impoverishment, medically needy/spend-down, MSP, presumptive and continuous eligibility, renewals and changes, notices and hearings, appendix income/resource tables), the approved state plan and SPAs, and annual income-level tables. PolicyEngine (policyengine-us 84253b6, 2026-08-17: parameters gov/hhs/medicaid, gov/hhs/chip, gov/aca, gov/states/*/hhs/chip, gov/states/{ar,va}/*/medicaid and the matching variables) and rulespec-us (c8951033, 2026-08-08: us-xx/policies/cms/*-chip-eligibility and *-medicaid-chip-bhp-eligibility-levels wrappers, us/policies/medicaid/magi_household_income_pipeline, us-ga dfcs/medicaid/2578, oracle-coverage-pending entries) are recorded per element as a cross-check in pe_modeled / rulespec.',
      'levels': {'federal_only': 'federal text sets the element; every state inherits it (state matrix rows: INHERITED, or NOT_APPLICABLE for part 436 which governs only GU/PR/VI)', 'federal_with_state_option': 'federal text sets the rule; the state elects or implements; the state row is checked against the state\'s held documents', 'state': 'a state-set value or state-authored rule; the state row is checked; the federal row records the federal authority'},
      'search_confidence': {'high': 'search_patterns (strong) exist: a body match in the state\'s program or pointer scopes is PRESENT with the matched provision (subject to needs_number and neg_context)', 'low': 'only weak_patterns exist: a match is a candidate and is reported REVIEW with the candidate cited', 'n/a': 'no text search; the cell is settled by the federal row, a CMS compilation, the state plan family or the queue row'},
      'pass_2_note': 'Schema version 2 (2026-09-12). Pass 1 (2026-09-11) marked PRESENT on single-word patterns and on hits in SNAP, TANF and CalFresh scopes; pass 2 restricts the search universe to the state\'s Medicaid and CHIP scopes plus the pointer scopes of done-by-pointer states, splits patterns into strong and weak, requires a value signal for state-set standards, rejects Medicare and ACA contexts for cost-sharing elements, and names the CMS-posted state plan family that carries an election when the state text does not. 42 CFR 457.344 is held only as a removal notice in the CMS-2454-IFC conforming-amendments scope and is not an element.',
    }
    open(f'{out}/medicaid-schema.yaml','w').write(dump('medicaid', apply_overrides(M), dict(common, title='Medicaid needs schema (law-derived)', labels=['medicaid'], aliases={'medicaid_chip_bhp':'us manifest tag'}, pe_cross_check_summary='PolicyEngine models: MAGI groups and income limits (children by age band, pregnant + postpartum, parents/caretakers incl. deprivation and student options, adult group), SSI-recipient and 209(b) classification, optional aged/blind/disabled income and asset limits and disregards, medically needy categories and income/asset limits, MAGI household and income counting, immigration eligibility and five-year bar, emergency Medicaid, LTC home equity limit, community engagement (age range, hours, dependent and foster-care limits), working-disabled buy-in premium, 1115 MEC adult, FMAP. PolicyEngine does not model: presumptive eligibility, continuous eligibility, retroactive eligibility, MSP (QMB/SLMB/QI/QDWI), spousal impoverishment, transfers/look-back, trusts, estate recovery, post-eligibility treatment of income, TMA, Medicaid premiums and copayments (447), BCCP/TB/family-planning/HCBS/Katie Beckett groups, 1902(r)(2) methodologies, deeming, verification, renewals, notices, hearings, state plan content.')))
    open(f'{out}/chip-schema.yaml','w').write(dump('chip', apply_overrides(C), dict(common, title='CHIP needs schema (law-derived)', labels=['chip'], pe_cross_check_summary='PolicyEngine models: separate-CHIP child income limit and max age, pregnant-woman CHIP income limit, FCEP (unborn child) income limit and Alabama county/statewide flags, disqualifying health coverage, the 5% cumulative cost-sharing cap, and state premium/enrollment-fee schedules for 17 states (AL, CT, DE, FL, GA, IA, ID, IL, IN, KS, LA, MA, MI, MO, NY, TX, WI), plus federal share. PolicyEngine does not model: waiting periods/substitution, continuous eligibility, presumptive eligibility, renewals, verification, benefit package, copayment schedules, disenrollment protections, AI/AN exemptions, M-CHIP vs S-CHIP program type, state plan content.')))
    print(len(M), len(C))
