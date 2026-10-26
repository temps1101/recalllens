#!/usr/bin/env python3
"""Publish anonymized AI-reviewed exploratory results and reproducible figures."""
import csv
import json
import statistics
from collections import Counter
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'experiments/output/diverse-study-2026-10-26'
OUT=ROOT/'docs/evidence/diverse-study'
FIG=ROOT/'docs/figures'
NAMES={'hsv_histogram':'HSV color','orb_descriptor_support':'ORB support (tuned)',
       'orb_ransac':'ORB geometry (tuned)','sift_ransac':'SIFT geometry (tuned)','deployed_anchor':'ORB deployed (0.62)'}

def read(path):
    with path.open(newline='') as f:return list(csv.DictReader(f))

def write(path,rows):
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def main():
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--from-evidence',action='store_true');args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    if not args.from_evidence:
        for name in ['reviewed_labels.csv','worker_proposals.csv','label_audit.json','frozen_selection.json',
                     'heldout_results.json','feature_costs.csv','comparison_protocol.json','scoring_complete.json','tune_scores.csv']:
            (OUT/name).write_bytes((BASE/name).read_bytes())
        (OUT/'test_scores.csv').write_bytes((BASE/'test_scores.sealed.csv').read_bytes())
        pairs=read(BASE/'private_pairs.csv')
        write(OUT/'pair_splits.csv',[{k:r[k] for k in ['pair_id','block','split']} for r in pairs])
    pairs=read(OUT/'pair_splits.csv')
    labels={r['pair_id']:r for r in read(OUT/'reviewed_labels.csv')}
    scores=read(OUT/'test_scores.csv');tune=read(OUT/'tune_scores.csv')
    frozen=json.loads((OUT/'frozen_selection.json').read_text())
    result=json.loads((OUT/'heldout_results.json').read_text())['methods']
    valid={k:v for k,v in labels.items() if v['review_status']=='confirmed'}
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'figure.dpi':140})
    keys=list(result);x=np.arange(len(keys))
    fig,axes=plt.subplots(1,2,figsize=(12,4.8))
    for ax,key,den,title,color in [(axes[0],'true_accepts','positive_directions','Same-scene directions accepted','#168475'),(axes[1],'false_accepts','negative_directions','Different-scene directions accepted','#c46245')]:
        vals=[result[k]['test'][key]/result[k]['test'][den]*100 for k in keys]
        ax.barh(x,vals,color=color);ax.set_yticks(x,[NAMES[k] for k in keys]);ax.invert_yaxis();ax.set_xlim(0,105);ax.set_title(title);ax.set_xlabel('Percent of directional comparisons')
        for i,k in enumerate(keys):
            m=result[k]['test'];ax.text(vals[i]+1,i,f"{m[key]}/{m[den]}",va='center',fontsize=9)
    fig.suptitle('Held-out photos: 39 pairs in 12 spatial blocks | AI agreement labels',fontsize=13)
    fig.text(.5,.015,'Directions share photographs; 9 of 48 held-out pairs excluded as uncertain. No human validation.',ha='center',fontsize=9)
    fig.tight_layout(rect=[0,.04,1,.94]);fig.savefig(FIG/'diverse-method-comparison.png');plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(12,4.6))
    for family,choice in frozen['winners'].items():
        subset=[r for r in tune if r['pair_id'] in valid and r['config']==choice['config']]
        pos=[float(r['score']) for r in subset if valid[r['pair_id']]['label']=='same_scene']
        neg=[float(r['score']) for r in subset if valid[r['pair_id']]['label']=='different_scene']
        thresholds=sorted({0,1.000001,*pos,*neg})
        axes[0].plot([100*sum(v>=t for v in neg)/len(neg) for t in thresholds],[100*sum(v>=t for v in pos)/len(pos) for t in thresholds],label=NAMES[family])
    axes[0].axvline(5,color='gray',linestyle='--');axes[0].set(xlabel='Observed false acceptance (%)',ylabel='Positive acceptance (%)',title='Tuning-only threshold curves',xlim=(-2,102),ylim=(-2,102));axes[0].legend(fontsize=7)
    for family in frozen['winners']:
        c=[r for r in frozen['tuning_sensitivity'] if r['family']==family]
        axes[1].scatter([r['false_accept_rate']*100 for r in c],[r['true_accept_rate']*100 for r in c],label=f'{NAMES[family]} (n={len(c)})',s=45,alpha=.65)
    axes[1].set(xlabel='Observed false acceptance (%)',ylabel='Positive acceptance (%)',title='34 configurations at tuned thresholds',xlim=(-.5,5.5),ylim=(-2,102));axes[1].legend(fontsize=7)
    fig.suptitle('Tuning: 35 pairs (10 positive / 25 negative); test scores not used')
    fig.tight_layout();fig.savefig(FIG/'diverse-tuning.png');plt.close(fig)
    feature=read(OUT/'feature_costs.csv')
    extraction={f'{kind}{count}':statistics.median(float(r['extraction_ms']) for r in feature if r['method']==kind and r['features_requested']==count) for kind,count in [('orb','800'),('orb','1600'),('sift','1600')]}
    fig,axes=plt.subplots(1,2,figsize=(11,4))
    axes[0].bar(list(extraction),list(extraction.values()),color='#168475');axes[0].set(title='Feature extraction / image',ylabel='Median milliseconds')
    timingkeys=[k for k in keys if k!='hsv_histogram']
    axes[1].barh([NAMES[k] for k in timingkeys],[result[k]['test']['median_comparison_ms'] for k in timingkeys],color='#377bb3');axes[1].set(title='Comparison with cached features',xlabel='Median milliseconds')
    fig.suptitle('Local computer timings; not iPhone or AWS latency')
    fig.tight_layout();fig.savefig(FIG/'diverse-timing.png');plt.close(fig)
    failure=[];fallback=[]
    for family,choice in result.items():
        for s in scores:
            if s['pair_id'] not in valid or s['config']!=choice['config']:continue
            accept=float(s['score'])>=choice['threshold'];positive=valid[s['pair_id']]['label']=='same_scene'
            if accept and int(s['good_matches'])<8 and family in {'orb_ransac','sift_ransac'}:fallback.append(dict(method=family,**s))
            if accept!=positive:failure.append(dict(method=family,pair_id=s['pair_id'],direction=s['direction'],error='false_accept' if accept else 'miss',score=s['score'],threshold=choice['threshold'],scene_category=valid[s['pair_id']]['scene_category'],visual_observation=valid[s['pair_id']]['notes']))
    write(OUT/'failures.csv',failure)
    category=[]
    for cat in sorted({r['scene_category'] for r in valid.values()}):
        sub=[s for s in scores if s['pair_id'] in valid and valid[s['pair_id']]['scene_category']==cat and s['config']==result['deployed_anchor']['config']]
        if not sub:continue
        pos=[s for s in sub if valid[s['pair_id']]['label']=='same_scene'];neg=[s for s in sub if valid[s['pair_id']]['label']=='different_scene']
        category.append(dict(category=cat,positive_directions=len(pos),accepted=sum(float(s['score'])>=.62 for s in pos),negative_directions=len(neg),false_accepts=sum(float(s['score'])>=.62 for s in neg)))
    write(OUT/'category_results.csv',category)
    composition=Counter((r['split'],labels[r['pair_id']]['label']) for r in pairs)
    details={'composition':{f'{k[0]}/{k[1]}':v for k,v in composition.items()},'feature_extraction_median_ms':extraction,
             'tuned_geometry_acceptances_with_fewer_than_eight_matches':Counter(r['method'] for r in fallback),
             'positive_blocks':{split:len({r['block'] for r in pairs if r['split']==split and labels[r['pair_id']]['label']=='same_scene'}) for split in ['tune','test']}}
    (OUT/'summary.json').write_text(json.dumps(details,indent=2)+'\n')
    table=['| Method | Frozen threshold | Same accepted | Different accepted | Comparison ms |','|---|---:|---:|---:|---:|']
    for k,c in result.items():
        m=c['test'];table.append(f"| {NAMES[k]} | {c['threshold']:.6f} | {m['true_accepts']}/{m['positive_directions']} | {m['false_accepts']}/{m['negative_directions']} | {m['median_comparison_ms']:.3f} |")
    report='''# Diverse archived-photo study: exploratory AI-reviewed comparison

## Scope and provenance

144 archived photographs form 96 pairs from 24 GPS blocks. Existing 641-photo and human-labeled pools were excluded. Blocks were separated into 12 tuning and 12 held-out groups before scoring. GPS/time selected candidates, not visual labels. There is no image/hash overlap across the split. This is a retrospective photo study, not new field capture or a user study.

The user authorized ChatGPT image uploads. A worker and the primary assistant reviewed contact sheets without algorithm scores. Only agreement on same/different was retained: 74 pairs (24 positive, 50 negative); 22/96 were excluded. Ten pair labels disagreed and twelve were jointly uncertain. These are two AI passes, not human ground truth or statistically independent annotation. The primary assistant saw the worker's uncertainty summary before completing its last 24 reviews. No uncertain label was resolved using scores. Excluding ambiguous views can make the task easier.

Tuning contains 35 retained pairs (10 positive, 25 negative), with 13 exclusions. Held-out evaluation contains 39 retained pairs (14 positive, 25 negative), with nine exclusions. Both directions share images and must not be counted as independent trials. Near-duplicate bursts and a single person's archive limit diversity. Full scene-level independence is not established by GPS separation.

## Frozen comparison

Four method families and 34 configurations were scored. Each family selected parameters/threshold on tuning data alone, maximizing positive acceptance under observed false acceptance <=5%, then fewer false accepts and lower comparison time. Selection and label hashes were frozen before the test file was opened. No held-out retuning was performed. The deployed ORB threshold 0.62 remained a separate unchanged anchor.

'''+ '\n'.join(table)+'''

![Held-out method comparison](figures/diverse-method-comparison.png)

## Interpretation and deployment decision

SIFT recovered more positives but produced three false acceptances; color similarity produced eight. The current ORB setting missed sixteen of twenty-eight positive directions. Thus the expanded test exposes substantial viewpoint/visible-area limitations, rather than establishing broad robustness.

The tuned ORB geometry threshold is only 0.0225001. It can accept the production scoring fallback for fewer than eight correspondences, before any homography exists. Its result equals tuned descriptor support on this set; it is not evidence that geometric verification improved. A future calibration should require a valid homography and a minimum inlier count as hard constraints, then be assessed on a new held-out set. We preserve this failed selection outcome and do not deploy it.

![Tuning curves and parameter comparison](figures/diverse-tuning.png)

## Observed failures and application implications

- The railway views new_037/038 and oblique temple views new_085/088 were missed in both directions by every feature-based selected method. Shared structure is visible to the AI reviewers, but framing, scale and foreground occlusion differ. These observations suggest conditions to investigate; they do not isolate a causal mechanism.
- SIFT false acceptances occur in new_045 A-to-B, new_055 A-to-B and new_072 B-to-A. The pairs depict different subjects or views. Geometric estimation alone does not guarantee meaningful scene correspondence at this permissive threshold.
- Strongly related views of distinctive objects and stable surroundings remain useful candidates. The deployed model's category counts are supplied in category_results.csv; categories are small and confounded, so no category ranking is claimed.
- Product guidance should ask users to include stable distinctive background structure and return to similar framing. A future registration quality check, multi-view capture and hard geometry gate need separate evaluation. No user benefit or improvement from these unimplemented changes is claimed.

All errors, including low-scoring positives, remain in failures.csv. Existing human-labeled evidence and actual-photo illustrations remain separate in PHOTO_BENCHMARK.md.

## Runtime and reproducibility

![Extraction and comparison timings](figures/diverse-timing.png)

Times are local computer observations with cached features. They exclude photo decoding, full archive retrieval, network and display. Median feature extraction over 144 photos is about 12.2 ms for ORB800, 12.9 ms for ORB1600 and 43.6 ms for SIFT1600. No histogram extraction timing was recorded; its comparison-only time cannot establish full-pipeline superiority. These are not iPhone or AWS performance estimates.

Anonymized score rows, splits, labels, label provenance, selection hashes and all failure records are in docs/evidence/diverse-study. Private paths, GPS coordinates, timestamps and originals are excluded. Aggregate results and plots are reproducible from these rows using Tools/report_diverse_study.py; feature extraction from private originals is not reproducible from the public package. Full regeneration uses prepare_diverse_pairs.py, compare_vision_methods.py, finalize_ai_labels.py and calibrate_vision_methods.py in that order. Frozen outputs prevent silently replacing the first evaluation.

## Rubric contribution and remaining priorities

This study supports technical execution and documentation by showing a separate tuning/test protocol, algorithm/parameter comparisons, speed tradeoffs and measured failures. It does not replace a working demonstration or evidence of user benefit. The remaining submission priorities are the actual app/AWS demo video, judge access and final submission. Official criteria: https://opencv26.devpost.com/rules .
'''
    report=report.replace('using Tools/report_diverse_study.py;', 'using Tools/report_diverse_study.py --from-evidence;')
    (ROOT/'docs/DIVERSE_PHOTO_STUDY.md').write_text(report)
    print(json.dumps(details,indent=2))

if __name__=='__main__':main()
