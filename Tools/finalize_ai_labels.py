#!/usr/bin/env python3
"""Freeze conservative agreement labels; AI review is not human ground truth."""
import csv
import io
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'experiments/output/diverse-study-2026-10-26'

def main():
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--response',type=Path,required=True);a=p.parse_args()
    out=BASE/'reviewed_labels.csv'
    if out.exists():raise SystemExit('Labels already frozen')
    response=a.response.read_text()
    start=response.index('pair_id,label,scene_category,confidence,visual_evidence,nuisance_factors')
    content=response[start:].split('```')[0].strip()
    worker=list(csv.DictReader(io.StringIO(content)))
    own=json.loads((BASE/'independent_ai_review.json').read_text())['rows']
    own={f'new_{r[0]:03d}':r for r in own}
    assert len(worker)==96 and {r['pair_id'] for r in worker}==set(own)
    rows=[];disagreements=[]
    for w in worker:
        r=own[w['pair_id']]
        agree=w['label']==r[1] and r[1]!='uncertain'
        rows.append(dict(pair_id=w['pair_id'],label=r[1] if agree else 'uncertain',
            review_status='confirmed' if agree else 'unresolved',reviewer='two_AI_visual_passes_not_human',
            scene_category=r[2],notes=r[3],primary_label=r[1],worker_label=w['label']))
        if w['label']!=r[1]:disagreements.append(dict(pair_id=w['pair_id'],primary=r[1],worker=w['label']))
    with out.open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    (BASE/'worker_proposals.csv').write_text(content+'\n')
    audit={'provenance':'Two AI visual passes on contact sheets; no human validation. Primary assistant saw a summary of worker uncertainties before completing its last 24 pairs, but not worker row labels or algorithm scores. Passes are not statistically independent.',
           'inclusion_rule':'Only agreement on same_scene/different_scene; either uncertain or disagreement excluded. Frozen before tuning/test score interpretation.',
           'pairs':96,'included':sum(r['review_status']=='confirmed' for r in rows),'excluded':sum(r['review_status']!='confirmed' for r in rows),
           'disagreements':disagreements,'counts':{label:sum(r['label']==label for r in rows) for label in ['same_scene','different_scene','uncertain']}}
    (BASE/'label_audit.json').write_text(json.dumps(audit,indent=2)+'\n')
    print(json.dumps(audit,indent=2))

if __name__=='__main__':main()
