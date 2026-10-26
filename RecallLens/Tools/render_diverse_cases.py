#!/usr/bin/env python3
"""Render two non-person-dominant examples, selected after evaluation for illustration."""
import csv
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image,ImageOps
import pillow_heif
pillow_heif.register_heif_opener()
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'experiments/output/diverse-study-2026-10-26'
with (BASE/'private_pairs.csv').open() as f:pairs={r['pair_id']:r for r in csv.DictReader(f)}
with (BASE/'test_scores.sealed.csv').open() as f:scores=list(csv.DictReader(f))
fig,axes=plt.subplots(2,2,figsize=(11,9),facecolor='white')
for i,pid in enumerate(['new_069','new_078']):
    values=[s for s in scores if s['pair_id']==pid and s['config']=='orb1600_ratio0.75_ransac4']
    title=f"{pid}: AI same-scene | deployed ORB scores "+' / '.join(f"{float(s['score']):.3f}" for s in values)+' | threshold 0.62'
    for j,k in enumerate(['path_a','path_b']):
        with Image.open(pairs[pid][k]) as im:
            im=ImageOps.exif_transpose(im).convert('RGB');im.thumbnail((1000,800));axes[i,j].imshow(im)
        axes[i,j].axis('off');axes[i,j].set_title('A' if j==0 else 'B',fontsize=10)
    fig.text(.5,.935-i*.455,title,ha='center',fontsize=11)
fig.subplots_adjust(top=.90,bottom=.045,hspace=.32,wspace=.04)
fig.text(.5,.012,'Illustrations selected after evaluation; all errors retained. Rendered without GPS/EXIF.',ha='center',fontsize=9)
fig.savefig(ROOT/'docs/figures/diverse-photo-cases.png',dpi=160);plt.close(fig)
