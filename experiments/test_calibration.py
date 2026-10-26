import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT=Path(__file__).resolve().parents[1]/'Tools/calibrate_vision_methods.py'


def write(path,rows):
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


class CalibrationTests(unittest.TestCase):
    def test_test_set_cannot_choose_the_winning_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory)
            labels=[]
            for split in ['tune','test']:
                samples=[]
                for suffix,label in [('p','same_scene'),('n','different_scene')]:
                    pair=split+suffix
                    labels.append(dict(pair_id=pair,label=label,review_status='confirmed'))
                    for config in ['A','B']:
                        good=(split=='tune' and config=='A') or (split=='test' and config=='B')
                        score=.9 if (suffix=='p')==good else .1
                        samples.append(dict(pair_id=pair,block=split,split=split,direction='A_to_B',config=config,family='orb_ransac',score=score,compare_ms=1))
                write(base/('tune_scores.csv' if split=='tune' else 'test_scores.sealed.csv'),samples)
            write(base/'labels.csv',labels)
            def run(phase):
                return subprocess.run([sys.executable,str(SCRIPT),phase,'--base',str(base),'--labels',str(base/'labels.csv')],capture_output=True,text=True)
            self.assertEqual(run('calibrate').returncode,0)
            frozen=json.loads((base/'frozen_selection.json').read_text())
            self.assertEqual(frozen['winners']['orb_ransac']['config'],'A')
            self.assertFalse((base/'heldout_results.json').exists())
            self.assertEqual(run('evaluate').returncode,0)
            results=json.loads((base/'heldout_results.json').read_text())
            self.assertEqual(results['methods']['orb_ransac']['config'],'A')
            self.assertEqual(results['methods']['orb_ransac']['test']['false_accepts'],1)
            self.assertNotEqual(run('calibrate').returncode,0)

    def test_unreviewed_model_labels_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory)
            write(base/'labels.csv',[dict(pair_id='p',label='same_scene',review_status='model_proposed')])
            r=subprocess.run([sys.executable,str(SCRIPT),'calibrate','--base',str(base),'--labels',str(base/'labels.csv')],capture_output=True,text=True)
            self.assertNotEqual(r.returncode,0)
            self.assertIn('No independently confirmed',r.stderr)


if __name__=='__main__':unittest.main()
