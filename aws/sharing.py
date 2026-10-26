"""Account-free, bearer-link photo delivery. Photos are deliberately prefetched."""
import base64
import binascii
import json
import os
import re
import secrets
import time
import uuid

import boto3
os.environ.setdefault("OPENCV_IO_MAX_IMAGE_PIXELS", "4000000")
import cv2
import numpy as np
from botocore.exceptions import ClientError

TOKEN = re.compile(r"^[A-Za-z0-9_-]{32}$")
MAX_BODY = 2_500_000
LIFETIME = 30 * 86400


def response(status, data):
    return {'statusCode': status, 'headers': {'content-type': 'application/json', 'cache-control': 'no-store'}, 'body': json.dumps(data)}


def storage():
    return boto3.client('s3'), os.environ['SHARE_BUCKET']


def handle(event, path, method, upload_authorized):
    if path.endswith('/shares') and method == 'POST':
        if not upload_authorized:
            return response(401, {'error': 'Unauthorized'})
        body = event.get('body') or '{}'
        if len(body) > MAX_BODY * 1.4:
            return response(413, {'error': 'Photo exceeds upload limit'})
        try:
            if event.get('isBase64Encoded'):
                body = base64.b64decode(body, validate=True).decode('utf-8')
            if len(body) > MAX_BODY:
                return response(413, {'error': 'Photo exceeds upload limit'})
            payload = json.loads(body)
            if not isinstance(payload, dict): raise ValueError('Invalid upload')
            encoded = payload.get('photo', '')
            if not isinstance(encoded, str) or len(encoded) > 2_000_000: raise ValueError('Invalid photo')
            raw = base64.b64decode(encoded, validate=True)
            # The app sends a bounded JPEG; reject other formats before decoding.
            if not raw.startswith(b'\xff\xd8'): raise ValueError('JPEG required')
            image = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
            if image is None or max(image.shape[:2]) > 2000: raise ValueError('Invalid image size')
            # Re-encoding removes EXIF/location metadata and normalizes the payload.
            ok, jpeg = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if not ok: raise ValueError('Invalid JPEG')
            photo = base64.b64encode(jpeg).decode('ascii')
            if len(photo) > 2_000_000: raise ValueError('Photo too large')
            feature_data = payload.get('featureData', '')
            feature_algorithm = payload.get('featureAlgorithm', '')
            if feature_algorithm != 'opencv-5-orb-v1': raise ValueError('Invalid feature algorithm')
            # Validate that the uploaded OpenCV signature and JPEG describe the same scene.
            # This is the only server-side vision operation in the sharing architecture.
            import handler
            feature_blob = handler._decode_feature_blob(feature_data)
            reference_points, reference_descriptors, _ = handler._unpack_features(feature_blob)
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            orb = cv2.ORB.create(nfeatures=1600, scaleFactor=1.2, nlevels=8, edgeThreshold=31,
                                 firstLevel=0, WTA_K=2, scoreType=cv2.ORB_HARRIS_SCORE,
                                 patchSize=31, fastThreshold=12)
            query_points, query_descriptors = orb.detectAndCompute(gray, None)
            binding = handler._match_features(query_points, query_descriptors, gray.shape,
                                              reference_points, reference_descriptors)
            if binding['similarity'] < 0.25: raise ValueError('Photo and feature signature do not match')
            captured = float(payload.get('capturedAt', time.time()))
            if not 0 <= captured <= time.time() + 86400: raise ValueError('Invalid capture date')
        except (ValueError, TypeError, binascii.Error, UnicodeError, cv2.error):
            return response(400, {'error': 'Invalid photo upload'})
        token = secrets.token_urlsafe(24)
        now = int(time.time())
        item = {'shareId': token, 'recordId': str(uuid.uuid4()), 'photo': photo,
                'featureData': feature_data, 'featureAlgorithm': feature_algorithm,
                'capturedAt': captured, 'expiresAt': now + LIFETIME}
        s3, bucket = storage()
        s3.put_object(Bucket=bucket, Key=f'shares/{token}.json', Body=json.dumps(item).encode(),
                      ContentType='application/json', ServerSideEncryption='AES256')
        context = event.get('requestContext', {})
        stage = context.get('stage', 'prod')
        base_url = os.environ.get('PUBLIC_BASE_URL') or ('https://' + context['domainName'] + ('' if stage == '$default' else '/' + stage))
        return response(201, {'shareId': token, 'expiresAt': item['expiresAt'],
                              'url': base_url.rstrip('/') + '/s/' + token,
                              'engine': f"OpenCV {cv2.__version__} ORB pair validation"})

    match = re.search(r'/(shares|s)/([^/]+)$', path)
    if not match or method != 'GET' or not TOKEN.fullmatch(match[2]):
        return response(404, {'error': 'Share not found'})
    token = match[2]
    if match[1] == 's':
        # Link previews never contain the shared photo or its retrieval endpoint.
        html = '''<!doctype html><html lang="ja"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><title>Recalllens — 写真を受け取る</title>
<style>body{background:#101c20;color:#eef6f4;font-family:system-ui;max-width:420px;margin:18vh auto;padding:28px;text-align:center}a{display:block;background:#80e2c3;color:#102721;padding:18px;border-radius:18px;text-decoration:none;font-weight:600}p{line-height:1.8;color:#bdd0cc}</style>
<h1>風景に、写真が届いています。</h1><p>Recalllensで受け取ると、その風景にカメラを向けたときに写真が現れます。</p>
<a href="recalllens://receive/TOKEN">Recalllensで受け取る</a>
<p>アプリがインストールされたiPhoneで開いてください。開かない場合は上のボタンを押してください。</p>
<script>if(/iPhone|iPad|iPod/.test(navigator.userAgent)){location.href='recalllens://receive/TOKEN';}</script></html>'''.replace('TOKEN', token)
        language = {str(k).lower(): str(v) for k, v in (event.get('headers') or {}).items()}.get('accept-language', '').split(',')[0].lower()
        if not language.startswith('ja'):
            for japanese, english in {
                'lang="ja"': 'lang="en"', '写真を受け取る': 'Receive a photo',
                '風景に、写真が届いています。': 'A photo is waiting in this scene.',
                'Recalllensで受け取ると、その風景にカメラを向けたときに写真が現れます。': 'Receive it in Recalllens, then point your camera at the matching scene to reveal it.',
                'Recalllensで受け取る': 'Receive in Recalllens',
                'アプリがインストールされたiPhoneで開いてください。開かない場合は上のボタンを押してください。': 'Open on an iPhone with Recalllens installed. If the app does not open automatically, tap the button above.'
            }.items(): html = html.replace(japanese, english)
        return {'statusCode': 200, 'headers': {'content-type': 'text/html; charset=utf-8',
            'cache-control': 'no-store', 'referrer-policy': 'no-referrer', 'x-content-type-options': 'nosniff',
            'content-security-policy': "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; frame-ancestors 'none'"}, 'body': html}
    s3, bucket = storage()
    try:
        obj = s3.get_object(Bucket=bucket, Key=f'shares/{token}.json')
    except ClientError as error:
        if error.response['Error']['Code'] in {'NoSuchKey', '404'}:
            return response(404, {'error': 'Share not found'})
        raise
    item = json.loads(obj['Body'].read(MAX_BODY + 1))
    if item['expiresAt'] <= time.time():
        return response(410, {'error': 'Share expired'})
    return response(200, item)
