import json,re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CATALOG=json.loads((ROOT/'data'/'exams.json').read_text(encoding='utf-8'))

def norm(text:str)->str:
    text=text.lower().replace('&',' and ')
    return re.sub(r'[^a-z0-9]+',' ',text).strip()

def find_exam(text:str):
    n=norm(text)
    exact=[]
    for key,e in CATALOG.items():
        vals=[key,e['name'],*e.get('aliases',[])]
        for v in vals:
            nv=norm(v)
            if n==nv:
                exact.append((len(nv),key))
    if exact: return max(exact)[1]
    candidates=[]
    for key,e in CATALOG.items():
        for v in [e['name'],*e.get('aliases',[])]:
            nv=norm(v)
            if nv and re.search(r'\b'+re.escape(nv)+r'\b',n):
                candidates.append((len(nv),key))
    return max(candidates)[1] if candidates else None

def get_stage(key,stage): return CATALOG[key]['stages'][stage]
def get_paper(key,stage,paper): return CATALOG[key]['stages'][stage]['papers'][paper]

def detect_stage(key,text):
    n=norm(text)
    stages=CATALOG[key]['stages']
    if key=='reet':
        if 'level 2' in n or 'class 6' in n or 'class 6 8' in n: return 'l2'
        return 'l1'
    if key=='ras':
        return 'mains' if 'main' in n else 'pre'
    return next(iter(stages))

def detect_paper(key,stage,text):
    n=norm(text)
    papers=CATALOG[key]['stages'][stage]['papers']
    if key=='ras' and stage=='mains':
        for p in ('p4','p3','p2','p1'):
            if re.search(r'paper\s*'+p[-1],n) or ('paper '+str(int(p[-1])) in n): return p
    if key=='si':
        if 'paper 2' in n or 'paper ii' in n: return 'p2'
        if 'paper 1' in n or 'paper i' in n: return 'p1'
    return next(iter(papers))
