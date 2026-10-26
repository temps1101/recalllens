#!/usr/bin/env python3
"""Freeze score-independent, geographically separated natural-photo pairs for blind review."""
import csv
import hashlib
import itertools
import json
import math
from pathlib import Path
from PIL import Image, ImageOps, ImageDraw
from pillow_heif import register_heif_opener

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'experiments/output/diverse-study-2026-10-26'
register_heif_opener()


def read(path):
    with path.open(newline='') as f:
        return list(csv.DictReader(f))


def distance(a,b):
    x,y=map(math.radians,a);u,v=map(math.radians,b)
    return 12742000*math.asin(min(1,math.sqrt(math.sin((u-x)/2)**2+math.cos(x)*math.cos(u)*math.sin((v-y)/2)**2)))


def main():
    if (OUT/'private_pairs.csv').exists():
        raise SystemExit('Frozen selection exists; do not overwrite it.')
    OUT.mkdir(parents=True,exist_ok=True)
    originals=Path.home()/'Pictures/Photos Library.photoslibrary/originals'
    previous=read(ROOT/'experiments/output/benchmark-2026-10-26/private_manifest.csv')
    excluded_paths={r['path'] for r in previous}
    excluded_hashes={r['sha256'] for r in previous}
    labels=read(ROOT/'experiments/data/photo_library_pair_labels.csv')
    excluded_ids={r[k] for r in labels for k in ['asset_a_uuid','asset_b_uuid']}
    groups={}
    for r in read(ROOT/'experiments/output/photo_library_places_assets.csv'):
        try:lat,lon=float(r['latitude']),float(r['longitude'])
        except ValueError:continue
        p=originals/r['directory']/r['filename']
        if not(-90<=lat<=90 and -180<=lon<=180) or r['uuid'] in excluded_ids or str(p) in excluded_paths or not p.is_file():continue
        key=(round(lat,3),round(lon,3))
        groups.setdefault(key,[]).append(dict(r,path=str(p)))
    eligible=[k for k,v in groups.items() if len(v)>=6]
    eligible.sort(key=lambda k:hashlib.sha256(repr(k).encode()).hexdigest())
    selected=[]; used_hashes=set(); manifest=[]
    for key in eligible:
        if any(distance(key,k)<500 for k in selected):continue
        ordered=sorted(groups[key],key=lambda r:(r['captured_at'],r['uuid']))
        # Six time-spaced photos chosen before any vision score is calculated.
        chosen=[ordered[round(i*(len(ordered)-1)/5)] for i in range(6)]
        valid=[]
        for r in chosen:
            digest=hashlib.sha256(Path(r['path']).read_bytes()).hexdigest()
            if digest in excluded_hashes or digest in used_hashes:continue
            try:
                with Image.open(r['path']) as im:im.load()
            except Exception:continue
            valid.append(dict(r,sha256=digest))
        if len(valid)<6:continue
        selected.append(key);used_hashes.update(r['sha256'] for r in valid)
        group=f'block_{len(selected):02d}'
        split='tune' if len(selected)%2 else 'test'
        # Adjacent capture intervals and one longer-interval pair; labels remain unknown.
        for a,b in [(0,1),(2,3),(4,5),(0,5)]:
            pair=f'new_{len(manifest)+1:03d}'
            manifest.append(dict(pair_id=pair,block=group,split=split,path_a=valid[a]['path'],path_b=valid[b]['path'],sha256_a=valid[a]['sha256'],sha256_b=valid[b]['sha256'],captured_a=valid[a]['captured_at'],captured_b=valid[b]['captured_at'],latitude_block=key[0],longitude_block=key[1]))
        if len(selected)==24:break
    with (OUT/'private_pairs.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(manifest[0]));w.writeheader();w.writerows(manifest)
    contact=OUT/'review_sheets';contact.mkdir()
    for start in range(0,len(manifest),8):
        sheet=Image.new('RGB',(1600,1400),'white');draw=ImageDraw.Draw(sheet)
        for i,r in enumerate(manifest[start:start+8]):
            x=(i%2)*800;y=(i//2)*350
            draw.text((x+12,y+8),r['pair_id']+'     A                                          B',fill='black')
            for j,k in enumerate(['path_a','path_b']):
                with Image.open(r[k]) as im:
                    thumb=ImageOps.exif_transpose(im).convert('RGB');thumb.thumbnail((385,310))
                    sheet.paste(thumb,(x+j*400+(400-thumb.width)//2,y+30+(310-thumb.height)//2))
            draw.rectangle((x,y,x+799,y+349),outline='#888888')
        sheet.save(contact/f'pairs_{start+1:03d}_{min(start+8,len(manifest)):03d}.jpg',quality=90)
    protocol={'version':1,'pair_count':len(manifest),'spatial_blocks':len(selected),'block_center_separation_m':500,'pair_selection':'Six time-spaced photos per 0.001-degree coordinate cell, three adjacent pairs plus endpoints; selected before vision scoring.','split':'Alternating blocks in frozen hash order; 12 tune and 12 test blocks. Images never cross splits.','prior_data':'Excludes previous 641-image file hashes and all previously human-labeled asset IDs.','label_status':'Unlabeled. Any vision-model judgments remain provisional until independently checked.','limitations':'GPS cells select candidates, not ground truth. Local availability and valid GPS bias the source pool. Nearby cell edges can be closer than block centers.','manifest_sha256':hashlib.sha256((OUT/'private_pairs.csv').read_bytes()).hexdigest()}
    (OUT/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')
    print(json.dumps(protocol,indent=2))


if __name__=='__main__':main()
