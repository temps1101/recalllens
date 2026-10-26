#!/usr/bin/env python3
"""Scientific comparison figures of existing natural photo pairs, without embedded EXIF.

Images are scaled for layout only. Scores come from the frozen audit, not the display renders.
"""
import csv
import json
from datetime import datetime
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image, ImageOps
from pillow_heif import register_heif_opener

ROOT = Path(__file__).resolve().parents[1]
register_heif_opener()


def rows(path):
    with path.open(newline='') as f:
        return list(csv.DictReader(f))


def main():
    labels = rows(ROOT / 'experiments/data/photo_library_pair_labels.csv')
    assets = {r['uuid']:r for r in rows(ROOT / 'experiments/output/photo_library_places_assets.csv')}
    scores = {(r['pair_id'],r['direction']):r for r in rows(ROOT / 'experiments/output/benchmark-2026-10-26/natural_pair_trials.csv')}
    originals = Path.home() / 'Pictures/Photos Library.photoslibrary/originals'
    output = ROOT / 'docs/figures'
    public_cases = []
    cases = [(43, 'Successful match: changed contents, shared counter structure'),
             (46, 'Successful match: changed angle and illumination'),
             (45, 'Missed match: close-up versus whole-object view'),
             (44, 'Correct rejection: same location group, different visible subjects')]
    for figure_index, group in enumerate([cases[:2],cases[2:]], 1):
        fig, axes = plt.subplots(2, 2, figsize=(11.8, 9.0), layout='constrained')
        for row_index, (number, title) in enumerate(group):
            label = labels[number-1]
            pair = f'pair_{number:03d}'
            forward, reverse = scores[(pair,'A_to_B')], scores[(pair,'B_to_A')]
            metadata = [assets[label[k]] for k in ['asset_a_uuid','asset_b_uuid']]
            for col, asset in enumerate(metadata):
                with Image.open(originals / asset['directory'] / asset['filename']) as source:
                    im = ImageOps.exif_transpose(source).convert('RGB')
                    im.thumbnail((1200,1200))
                    axes[row_index,col].imshow(im)
                axes[row_index,col].axis('off')
                if col == 1:
                    axes[row_index,col].set_title('Photo B', fontsize=10)
            try:
                gap = abs((datetime.fromisoformat(metadata[0]['captured_at'])-datetime.fromisoformat(metadata[1]['captured_at'])).total_seconds())
                elapsed = (f'{gap:.1f} seconds apart' if gap < 120 else
                           f'{gap/60:.1f} minutes apart' if gap < 86400 else f'{gap/86400:.1f} days apart')
            except ValueError:
                gap, elapsed = None, 'capture interval unavailable'
            details = (f"{pair} | Human label: {label['label']} | {elapsed}\n"
                       f"A to B: {float(forward['similarity']):.3f} ({forward['inliers']} inliers) | "
                       f"B to A: {float(reverse['similarity']):.3f} ({reverse['inliers']} inliers) | threshold 0.62")
            axes[row_index,0].set_title(title+'\n'+details+'\nPhoto A', fontsize=9, loc='left')
            public_cases.append({'pair_id':pair,'title':title,'label':label['label'],'capture_interval_seconds':gap,
                                 'forward_score':float(forward['similarity']),'reverse_score':float(reverse['similarity']),
                                 'selection':'Illustrative outcome categories, not a new accuracy sample'})
        fig.suptitle('Recall Lens | Actual archived photographs', fontsize=16, fontweight='bold')
        fig.supxlabel('Original photographs, scaled for display. No synthetic viewpoint changes. EXIF and GPS are not embedded in this figure.', fontsize=8)
        fig.savefig(output / f'natural-cases-{figure_index}.png',dpi=170,bbox_inches='tight')
        plt.close(fig)
    (ROOT/'docs/evidence/illustrated-cases.json').write_text(json.dumps(public_cases,indent=2)+'\n')
    print('Created two figures from four natural-photo pairs; source EXIF excluded.')


if __name__ == '__main__':
    main()
