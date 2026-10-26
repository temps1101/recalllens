#!/usr/bin/env python3
"""Calibrate exclusively on confirmed tuning labels, freeze, then evaluate test data."""
import argparse
import csv
import hashlib
import json
import statistics
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DEFAULT=ROOT/'experiments/output/diverse-study-2026-10-26'


def read(path):
    with path.open(newline='') as f:return list(csv.DictReader(f))


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def metrics(rows,labels,threshold):
    positive=[r for r in rows if labels[r['pair_id']]['label']=='same_scene']
    negative=[r for r in rows if labels[r['pair_id']]['label']=='different_scene']
    tp=sum(float(r['score'])>=threshold for r in positive)
    fp=sum(float(r['score'])>=threshold for r in negative)
    return {'positive_directions':len(positive),'negative_directions':len(negative),'true_accepts':tp,'false_accepts':fp,
            'true_accept_rate':tp/len(positive) if positive else None,'false_accept_rate':fp/len(negative) if negative else None,
            'unique_pairs':len({r['pair_id'] for r in rows}),'blocks':len({r['block'] for r in rows}),
            'median_comparison_ms':statistics.median(float(r['compare_ms']) for r in rows) if rows else None}


def confirmed_labels(path):
    rows=read(path)
    if len({r['pair_id'] for r in rows})!=len(rows):raise ValueError('Duplicate label IDs')
    return {r['pair_id']:r for r in rows if r.get('review_status')=='confirmed' and r['label'] in {'same_scene','different_scene'}}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('phase',choices=['calibrate','evaluate'])
    parser.add_argument('--base',type=Path,default=DEFAULT)
    parser.add_argument('--labels',type=Path,required=True)
    args=parser.parse_args();base=args.base
    labels=confirmed_labels(args.labels)
    if not labels:raise SystemExit('No independently confirmed labels. Model suggestions cannot silently become ground truth.')
    selection=base/'frozen_selection.json'
    if args.phase=='calibrate':
        if selection.exists():raise SystemExit('Selection is already frozen; preserve the experiment.')
        scores=[r for r in read(base/'tune_scores.csv') if r['pair_id'] in labels]
        groups={}
        for r in scores:groups.setdefault(r['config'],[]).append(r)
        if not groups:raise SystemExit('No labeled tuning examples')
        first=next(iter(groups.values()))
        counts=metrics(first,labels,0)
        if counts['positive_directions']==0 or counts['negative_directions']==0:raise SystemExit('Tuning requires confirmed positive and negative pairs')
        candidates=[]
        for config,rows in groups.items():
            thresholds=sorted({0.,1.000001,*[float(r['score'])+0.0000001 for r in rows],*[float(r['score']) for r in rows]})
            admissible=[]
            for threshold in thresholds:
                m=metrics(rows,labels,threshold)
                if m['false_accept_rate']<=.05:
                    admissible.append(dict(m,threshold=threshold,config=config,family=rows[0]['family']))
            best=min(admissible,key=lambda r:(-r['true_accept_rate'],r['false_accept_rate'],r['median_comparison_ms'],r['config'],r['threshold']))
            candidates.append(best)
        winners={}
        for family in sorted({r['family'] for r in candidates}):
            winners[family]=min([r for r in candidates if r['family']==family],key=lambda r:(-r['true_accept_rate'],r['false_accept_rate'],r['median_comparison_ms'],r['config']))
        selection.write_text(json.dumps({'labels_sha256':digest(args.labels),'tune_scores_sha256':digest(base/'tune_scores.csv'),
                                         'sealed_test_sha256':digest(base/'test_scores.sealed.csv'),'selection_used_test_scores':False,
                                         'winners':winners,'tuning_sensitivity':candidates},indent=2)+'\n')
        print('Selection frozen using tuning labels only. Test scoring has not been opened by this command.')
    else:
        if not selection.exists():raise SystemExit('Freeze calibration first')
        frozen=json.loads(selection.read_text())
        if digest(args.labels)!=frozen['labels_sha256']:raise SystemExit('Labels changed after calibration; audit instead of silently reevaluating')
        if digest(base/'test_scores.sealed.csv')!=frozen['sealed_test_sha256']:raise SystemExit('Test score file changed')
        scores=[r for r in read(base/'test_scores.sealed.csv') if r['pair_id'] in labels]
        chosen={**frozen['winners'],'deployed_anchor':{'config':'orb1600_ratio0.75_ransac4','threshold':.62}}
        results={}
        for family,choice in chosen.items():
            subset=[r for r in scores if r['config']==choice['config']]
            results[family]={**choice,'test':metrics(subset,labels,choice['threshold']),
                             'by_block':{b:metrics([r for r in subset if r['block']==b],labels,choice['threshold']) for b in sorted({r['block'] for r in subset})}}
        output=base/'heldout_results.json'
        if output.exists():raise SystemExit('Evaluation already exists; do not overwrite the first look')
        output.write_text(json.dumps({'methods':results,'label_file_sha256':digest(args.labels),
                                     'limitation':'Directional comparisons share pairs; block counts and sample composition must accompany rates. Confirmed review does not imply objective scene identity.'},indent=2)+'\n')
        print(output)


if __name__=='__main__':main()
