#!/usr/bin/env python3
"""Bounded deployed smoke test using only a new procedural reference; removes it afterward."""
import argparse
import json
import sys
import subprocess
import ssl
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import boto3
from botocore.httpsession import get_cert_path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "aws"))
from test_handler import encoded_test_image, encoded_features


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stack', default='weird-boots-verifier')
    parser.add_argument('--region', default='ap-northeast-1')
    args = parser.parse_args()
    # This pinned boto3 predates AWS CLI login credentials; import the active short-lived session in memory.
    credentials = json.loads(subprocess.run(['aws', 'configure', 'export-credentials', '--format', 'process', '--region', args.region], capture_output=True, text=True, check=True).stdout)
    session = boto3.Session(aws_access_key_id=credentials['AccessKeyId'], aws_secret_access_key=credentials['SecretAccessKey'], aws_session_token=credentials.get('SessionToken'), region_name=args.region)
    cf = session.client('cloudformation')
    stack = cf.describe_stacks(StackName=args.stack)['Stacks'][0]
    resources = cf.describe_stack_resources(StackName=args.stack)['StackResources']
    ids = {r['LogicalResourceId']: r['PhysicalResourceId'] for r in resources}
    outputs = {r['OutputKey']: r['OutputValue'] for r in stack['Outputs']}
    endpoint = outputs['VerificationEndpoint'].rstrip('/')
    function = session.client('lambda').get_function_configuration(FunctionName=ids['VerificationFunction'])
    token = function['Environment']['Variables']['API_TOKEN']
    table = session.resource('dynamodb').Table(ids['ReferenceTable'])
    ref = str(uuid.uuid4())
    image = encoded_test_image()
    findings = []
    def request(url, body, key=token):
        time.sleep(1.2)
        start = time.perf_counter()
        req = Request(url, data=json.dumps(body).encode(), headers={'Content-Type':'application/json','x-api-key':key}, method='POST')
        try:
            with urlopen(req, timeout=20, context=ssl.create_default_context(cafile=get_cert_path(True))) as response:
                return response.status, json.load(response), round((time.perf_counter()-start)*1000, 2)
        except HTTPError as error:
            return error.code, {}, round((time.perf_counter()-start)*1000, 2)
    try:
        status, body, ms = request(endpoint.rsplit('/', 1)[0]+'/references', {'referenceId':ref,'featureData':encoded_features(image)})
        findings.append({'check':'register_procedural_signature','passed':status==201,'http_status':status,'round_trip_ms':ms})
        assert status == 201
        status, body, ms = request(endpoint, {'referenceId':ref,'queryImage':image})
        findings.append({'check':'matching_image_authorized','passed':status==200 and body.get('authorized') is True,
                         'http_status':status,'round_trip_ms':ms,
                         'diagnostics':{k:body.get(k) for k in ['similarity','goodMatches','inliers','engine','imagesRetained','durationMs']}})
        status, _, ms = request(endpoint, {'referenceId':ref,'queryImage':image}, key='intentionally-invalid-smoke-token')
        findings.append({'check':'wrong_token_rejected','passed':status==401,'http_status':status,'round_trip_ms':ms})
        table.update_item(Key={'referenceId':ref}, UpdateExpression='SET expiresAt = :expiry', ExpressionAttributeValues={':expiry':int(time.time())-1})
        retained = 'Item' in table.get_item(Key={'referenceId':ref}, ConsistentRead=True)
        status, _, ms = request(endpoint, {'referenceId':ref,'queryImage':image})
        findings.append({'check':'expired_signature_rejected_before_ttl_cleanup','passed':retained and status==404,
                         'item_still_present_before_verify':retained,'http_status':status,'round_trip_ms':ms})
    finally:
        table.delete_item(Key={'referenceId':ref})
    result = {'checked_utc':datetime.now(timezone.utc).isoformat(),'stack_status':stack['StackStatus'],
              'function_last_modified':function['LastModified'],'fixture':'procedural image, not a user photograph',
              'checks':findings,'test_reference_deleted':True,'all_passed':len(findings)==4 and all(f['passed'] for f in findings)}
    output = ROOT / 'docs/evidence/deployed-checks.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))
    if not result['all_passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
