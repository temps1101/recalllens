#!/usr/bin/env python3
"""Exercise sharing with a generated fixture, then remove only that fixture."""
import base64
import io
import json
import ssl
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request,urlopen
import boto3
from botocore.httpsession import get_cert_path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'aws'))
from test_handler import encoded_test_image, encoded_features

def main():
    creds=json.loads(subprocess.check_output(['aws','configure','export-credentials','--format','process','--region','ap-northeast-1']))
    session=boto3.Session(aws_access_key_id=creds['AccessKeyId'],aws_secret_access_key=creds['SecretAccessKey'],aws_session_token=creds['SessionToken'],region_name='ap-northeast-1')
    cf=session.client('cloudformation');stack=cf.describe_stacks(StackName='weird-boots-verifier')['Stacks'][0]
    resources={r['LogicalResourceId']:r['PhysicalResourceId'] for r in cf.describe_stack_resources(StackName='weird-boots-verifier')['StackResources']}
    base=next(o['OutputValue'] for o in stack['Outputs'] if o['OutputKey']=='VerificationEndpoint').rsplit('/',1)[0]
    token=session.client('lambda').get_function_configuration(FunctionName=resources['VerificationFunction'])['Environment']['Variables']['API_TOKEN']
    s3=session.client('s3');bucket=resources['SharedPhotos'];share_id=None
    def request(path,body=None,authenticated=False):
        headers={'content-type':'application/json'}
        if authenticated:headers['x-api-key']=token
        for attempt in range(4):
            time.sleep(1.5)
            req=Request(base+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
            try:
                with urlopen(req,timeout=30,context=ssl.create_default_context(cafile=get_cert_path(True))) as r:return r.status,r.read()
            except HTTPError as e:
                if e.code==429 and attempt<3:continue
                return e.code,e.read()
    checks=[]
    try:
        status,_=request('/shares',{},False);checks.append({'check':'unauthenticated_upload','status':status,'passed':status==401})
        image=encoded_test_image()
        status,body=request('/shares',{'photo':image,'featureData':encoded_features(image),
            'featureAlgorithm':'opencv-5-orb-v1','capturedAt':time.time()},True)
        checks.append({'check':'upload_generated_photo','status':status,'passed':status==201})
        if status!=201:raise RuntimeError('Fixture upload failed')
        share=json.loads(body);share_id=share['shareId']
        status,body=request('/s/'+share_id)
        checks.append({'check':'landing_has_deep_link_without_photo','status':status,'passed':status==200 and b'recalllens://receive/' in body and b'<img' not in body})
        status,body=request('/shares/'+share_id);item=json.loads(body)
        checks.append({'check':'account_free_pair_download','status':status,'passed':status==200 and item['shareId']==share_id and len(base64.b64decode(item['photo']))>0 and len(base64.b64decode(item['featureData']))>0 and item['featureAlgorithm']=='opencv-5-orb-v1'})
        status,again=request('/shares/'+share_id)
        checks.append({'check':'stable_identity_on_repeat','status':status,'passed':status==200 and json.loads(again)['recordId']==item['recordId']})
        item['expiresAt']=int(time.time())-1
        s3.put_object(Bucket=bucket,Key=f'shares/{share_id}.json',Body=json.dumps(item).encode(),ServerSideEncryption='AES256')
        status,_=request('/shares/'+share_id)
        checks.append({'check':'expired_object_not_delivered','status':status,'passed':status==410})
    finally:
        if share_id:s3.delete_object(Bucket=bucket,Key=f'shares/{share_id}.json')
    evidence={'date':'2026-10-27','architecture':'AWS validates and temporarily delivers explicitly shared image-signature pairs; live matching is local','stack_status':stack['StackStatus'],'checks':checks,'generated_fixture_deleted':bool(share_id),'all_passed':all(c['passed'] for c in checks)}
    (ROOT/'docs/evidence/sharing-checks.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print(json.dumps(evidence,indent=2))
    if not evidence['all_passed']:raise SystemExit(1)

if __name__=='__main__':main()
