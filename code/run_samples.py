import sys,csv,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
import solve, evaluate
D=Path(__file__).parent.parent/'dataset'
w=solve.load_world(D)
req=list(csv.DictReader(open(D/'sample_deletion_requests.csv')))
allc=req+list(csv.DictReader(open(D/'deletion_requests.csv')))
S=solve.Solver(w,allc)
gold={r['case_id']:r for r in csv.DictReader(open(D/'sample_output.csv'))}
pred={}
for q in req:
    st,steps=S.solve(q)
    pred[q['case_id']]={'deletion_status':st,'steps_json':json.dumps(steps)}
print(evaluate.score(pred,gold))
verbose=len(sys.argv)>1
for q in req:
    c=q['case_id']
    g=json.loads(gold[c]['steps_json']); p=json.loads(pred[c]['steps_json'])
    k=lambda s:(s['operation'],s['resource_id'],s['evidence_id'])
    gs={k(s) for s in g}; ps={k(s) for s in p}
    if gs!=ps or gold[c]['deletion_status']!=pred[c]['deletion_status']:
        print(c,gold[c]['deletion_status'][:4],pred[c]['deletion_status'][:4],'MISSING',sorted(gs-ps),'EXTRA',sorted(ps-gs))
