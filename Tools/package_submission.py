#!/usr/bin/env python3
"""Allowlist a judge package, with anonymized evidence and no private images or credentials."""
import csv
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    files = {}
    def add(path, name=None):
        files[name or str(path.relative_to(ROOT))] = path.read_bytes()
    for name in ['README.md', 'LICENSE', 'SECURITY.md', '.gitignore', 'experiments/README.md', 'experiments/requirements.txt',
                 'experiments/test_metrics.py', 'experiments/test_calibration.py', 'Config/Cloud.xcconfig.example',
                 'aws/Dockerfile', 'aws/.dockerignore', 'aws/README.md', 'aws/requirements.txt',
                 'aws/handler.py', 'aws/sharing.py', 'aws/test_handler.py', 'aws/test_sharing.py', 'aws/template.yaml']:
        add(ROOT / name)
    for dirname, suffixes in [('RecallLens', {'.swift','.mm','.h','.plist','.json','.strings','.png','.svg'}),
                              ('Tools', {'.py','.rb','.sh'}), ('Tests', {'.swift'}),
                              ('experiments/src', {'.py'}), ('experiments/notebooks', {'.ipynb'})]:
        for p in sorted((ROOT / dirname).rglob('*')):
            if p.is_file() and p.suffix in suffixes and '__pycache__' not in p.parts:
                add(p)
    for name in ['TECHNICAL_REPORT.md', 'PHOTO_BENCHMARK.md', 'DEVPOST_SUBMISSION.md',
                 'DIVERSE_PHOTO_STUDY.md', 'SHARING.md', 'JUDGE_README.md',
                 'architecture.svg', 'architecture.png', 'recalllens.svg', 'recalllens.png']:
        add(ROOT / 'docs' / name)
    for p in sorted((ROOT / 'docs/figures').glob('*')):
        if p.suffix in {'.png', '.pdf'}:
            add(p)
    add(ROOT / 'output/pdf/Recalllens-Technical-Report.pdf', 'Recalllens-Technical-Report.pdf')
    evidence = ROOT / 'docs/evidence'
    for p in evidence.rglob('*'):
        if p.is_file() and p.suffix in {'.json','.csv','.md'}:
            add(p)
    # A harmless local-only config makes generation/build work immediately.
    files['Config/Cloud.xcconfig'] = b'// Local mode. Set both values to enable the AWS demo.\nWB_CLOUD_VERIFICATION_URL =\nWB_CLOUD_VERIFICATION_TOKEN =\n'
    secret_config = (ROOT / 'Config/Cloud.xcconfig').read_text()
    token_match = re.search(r'^WB_CLOUD_VERIFICATION_TOKEN\s*=\s*(.+)$', secret_config, re.M)
    token = token_match.group(1).strip().strip('"').encode() if token_match else b''
    for name, content in files.items():
        if token and len(token) >= 24 and token in content:
            raise SystemExit('Private demo token detected; packaging aborted')
        if re.search(rb'AKIA[0-9A-Z]{16}|-----BEGIN (?:RSA |EC )?PRIVATE KEY-----', content):
            raise SystemExit('Credential pattern detected; packaging aborted')
        if any(part in name.split('/') for part in ['Captures','references','queries','private_manifest.csv','private_exclusions.csv']):
            raise SystemExit('Private data path detected; packaging aborted')
        if name.endswith(('.md','.py','.rb','.sh','.ipynb')):
            files[name] = content.replace(str(ROOT).encode(), b'/path/to/RecallLens')
    manifest = {name:hashlib.sha256(content).hexdigest() for name,content in sorted(files.items())}
    files['SHA256SUMS.json'] = (json.dumps(manifest, indent=2)+'\n').encode()
    output = ROOT / 'output/submission/Recalllens-Submission.zip'
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, content in sorted(files.items()):
            z.writestr('Recalllens/'+name, content)
    with zipfile.ZipFile(output) as z:
        assert z.testzip() is None
        for name, digest in manifest.items():
            assert hashlib.sha256(z.read('Recalllens/'+name)).hexdigest() == digest
    print(json.dumps({'archive':str(output),'files':len(files),'bytes':output.stat().st_size,'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'private_token_scan':'passed','archive_integrity':'passed'}))


if __name__ == '__main__':
    main()
