#!/usr/bin/env python3
"""Score frozen pairs without labels; keep tuning and test observations separate."""
import csv
import hashlib
import itertools
import json
import sys
import time
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageOps

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'experiments/src'))
from recall_lens_eval import read_gray, coverage, write_csv
BASE=ROOT/'experiments/output/diverse-study-2026-10-26'
RATIOS=[.65,.75,.85]
PIXELS=[2.,4.,8.]


def main():
    if (BASE/'scoring_complete.json').exists():raise SystemExit('Completed scoring exists; preserve it.')
    with (BASE/'private_pairs.csv').open() as f:pairs=list(csv.DictReader(f))
    protocol={'algorithms':['hsv_histogram','orb_descriptor_support','orb_ransac','sift_ransac'],
              'orb_feature_counts':[800,1600],'sift_feature_counts':[1600],'ratio_tests':RATIOS,'ransac_pixels':PIXELS,
              'geometry_score':'0.52*inlier_ratio + 0.33*min(inliers/36,1) + 0.15*min(query_coverage/.22,1)',
              'descriptor_score':'min(ratio-test matches/36,1)',
              'histogram_score':'1 - Bhattacharyya distance; HSV bins 24x16x8, normalized',
              'deployment_anchor':'ORB1600, ratio .75, RANSAC4, threshold .62; frozen before evaluation',
              'calibration_rule':'For each family choose maximum positive acceptance subject to <=5% observed false acceptance on tune labels, then fewer false accepts, lower comparison latency, then stable config ID. Select thresholds using tune scores only. No guarantee about population error rates.',
              'labeling':'No labels or model suggestions are inputs to scoring. Test scores are not inspected before calibration is frozen.'}
    (BASE/'comparison_protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')
    paths=sorted({r[k] for r in pairs for k in ['path_a','path_b']})
    cache={};feature_rows=[]
    for i,path in enumerate(paths):
        gray=read_gray(Path(path))
        with Image.open(path) as src:
            rgb=np.asarray(ImageOps.exif_transpose(src).convert('RGB'))
        rgb=cv2.resize(rgb,(gray.shape[1],gray.shape[0]))
        hsv=cv2.cvtColor(rgb,cv2.COLOR_RGB2HSV)
        hist=cv2.calcHist([hsv],[0,1,2],None,[24,16,8],[0,180,0,256,0,256])
        cv2.normalize(hist,hist,alpha=1,norm_type=cv2.NORM_L1)
        item={'shape':gray.shape,'hist':hist,'features':{}}
        for kind,count in [('orb',800),('orb',1600),('sift',1600)]:
            detector=(cv2.ORB.create(nfeatures=count,fastThreshold=12) if kind=='orb' else cv2.SIFT.create(nfeatures=count))
            start=time.perf_counter();kp,desc=detector.detectAndCompute(gray,None);ms=(time.perf_counter()-start)*1000
            item['features'][(kind,count)]=(kp or [],desc)
            feature_rows.append({'image_id':f'image_{i+1:03d}','method':kind,'features_requested':count,'features_detected':len(kp or []),'extraction_ms':round(ms,4)})
        cache[path]=item
        if (i+1)%24==0:print(f'Extracted {i+1}/{len(paths)} photographs',flush=True)
    results={'tune':[],'test':[]}
    for index,row in enumerate(pairs):
        for direction,qa,rb in [('A_to_B','path_a','path_b'),('B_to_A','path_b','path_a')]:
            q,r=cache[row[qa]],cache[row[rb]]
            common={'pair_id':row['pair_id'],'block':row['block'],'split':row['split'],'direction':direction}
            start=time.perf_counter();sim=1-cv2.compareHist(q['hist'],r['hist'],cv2.HISTCMP_BHATTACHARYYA)
            results[row['split']].append(dict(common,config='hsv_histogram',family='hsv_histogram',score=round(float(sim),6),good_matches=0,inliers=0,compare_ms=round((time.perf_counter()-start)*1000,4)))
            for kind,count in [('orb',800),('orb',1600),('sift',1600)]:
                qp,qd=q['features'][(kind,count)];rp,rd=r['features'][(kind,count)]
                start=time.perf_counter()
                matches=(cv2.BFMatcher(cv2.NORM_HAMMING if kind=='orb' else cv2.NORM_L2).knnMatch(qd,rd,k=2) if qd is not None and rd is not None else [])
                matching_ms=(time.perf_counter()-start)*1000
                for ratio in RATIOS:
                    good=[p[0] for p in matches if len(p)==2 and p[0].distance<ratio*p[1].distance]
                    prefix=f'{kind}{count}_ratio{ratio:.2f}'
                    if kind=='orb':
                        results[row['split']].append(dict(common,config=prefix+'_descriptor',family='orb_descriptor_support',score=round(min(1,len(good)/36),6),good_matches=len(good),inliers=0,compare_ms=round(matching_ms,4)))
                    qxy=np.float32([qp[m.queryIdx].pt for m in good]);rxy=np.float32([rp[m.trainIdx].pt for m in good])
                    for tolerance in PIXELS:
                        start=time.perf_counter();inliers=0
                        if len(good)<8:sim=.18*min(1,len(good)/24)
                        else:
                            cv2.setRNGSeed(20261026)
                            _,mask=cv2.findHomography(qxy,rxy,cv2.RANSAC,tolerance)
                            valid=mask.ravel().astype(bool) if mask is not None else np.zeros(len(good),dtype=bool)
                            inliers=int(valid.sum())
                            sim=.52*inliers/len(good)+.33*min(1,inliers/36)+.15*min(1,coverage(qxy[valid],q['shape'])/.22)
                        results[row['split']].append(dict(common,config=prefix+f'_ransac{tolerance:.0f}',family=kind+'_ransac',score=round(float(sim),6),good_matches=len(good),inliers=inliers,compare_ms=round(matching_ms+(time.perf_counter()-start)*1000,4)))
        if (index+1)%16==0:print(f'Scored {index+1}/{len(pairs)} pairs',flush=True)
    write_csv(BASE/'tune_scores.csv',results['tune'])
    write_csv(BASE/'test_scores.sealed.csv',results['test'])
    write_csv(BASE/'feature_costs.csv',feature_rows)
    summary={'unique_images':len(paths),'pairs':len(pairs),'configs':len({r['config'] for r in results['tune']}),'tune_rows':len(results['tune']),'sealed_test_rows':len(results['test']),'opencv_version':cv2.__version__,'scoring_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (BASE/'scoring_complete.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary),flush=True)


if __name__=='__main__':main()
