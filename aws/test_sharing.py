import io
import json
import os
import unittest
from unittest.mock import MagicMock, patch
from botocore.exceptions import ClientError
import sharing
import handler
from test_handler import encoded_test_image, encoded_features

class SharingTests(unittest.TestCase):
    def setUp(self):
        self.objects = {}
        self.s3 = MagicMock()
        self.s3.put_object.side_effect = lambda **kw: self.objects.__setitem__(kw['Key'], kw['Body'])
        def get(**kw):
            if kw['Key'] not in self.objects:
                raise ClientError({'Error': {'Code': 'NoSuchKey'}}, 'GetObject')
            return {'Body': io.BytesIO(self.objects[kw['Key']])}
        self.s3.get_object.side_effect = get
        self.env = patch.dict(os.environ, {'API_TOKEN': 'demo-key', 'PUBLIC_BASE_URL': 'https://example.com/prod'})
        self.env.start()
        self.store = patch.object(sharing, 'storage', return_value=(self.s3, 'private-bucket')); self.store.start()

    def tearDown(self):
        self.store.stop(); self.env.stop()

    def request(self, path, method='GET', payload=None, token=None):
        return handler.lambda_handler({'rawPath': '/prod'+path, 'requestContext': {'http': {'method': method}},
            'headers': {'x-api-key': token} if token else {}, 'body': json.dumps(payload or {})}, None)

    def create(self):
        image = encoded_test_image()
        r = self.request('/shares', 'POST', {'photo': image, 'featureData': encoded_features(image),
            'featureAlgorithm': 'opencv-5-orb-v1', 'capturedAt': 1000}, 'demo-key')
        self.assertEqual(r['statusCode'], 201)
        return json.loads(r['body'])

    def test_upload_requires_token_but_link_holder_can_receive_without_account(self):
        self.assertEqual(self.request('/shares', 'POST', {})['statusCode'], 401)
        created = self.create()
        result = self.request('/shares/'+created['shareId'])
        self.assertEqual(result['statusCode'], 200)
        photo = json.loads(result['body'])
        self.assertEqual(photo['shareId'], created['shareId'])
        self.assertTrue(photo['photo'])
        self.assertTrue(photo['featureData'])
        self.assertEqual(photo['featureAlgorithm'], 'opencv-5-orb-v1')
        self.assertEqual(self.request('/shares/'+created['shareId'])['body'], result['body'])

    def test_landing_never_embeds_photo_even_for_link_preview(self):
        created = self.create()
        result = self.request('/s/'+created['shareId'])
        self.assertEqual(result['statusCode'], 200)
        self.assertIn('recalllens://receive/'+created['shareId'], result['body'])
        self.assertNotIn('data:image', result['body'])
        self.assertNotIn('<img', result['body'])
        self.s3.get_object.assert_not_called()

    def test_expiry_is_enforced_before_s3_lifecycle_removal(self):
        created = self.create()
        with patch.object(sharing.time, 'time', return_value=created['expiresAt']):
            self.assertEqual(self.request('/shares/'+created['shareId'])['statusCode'], 410)
        self.assertEqual(len(self.objects), 1)

    def test_landing_follows_japanese_or_english_language_preference(self):
        created = self.create()
        for language, text in [('ja-JP, en;q=0.8', '写真を受け取る'), ('en-US, ja;q=0.8', 'Receive a photo')]:
            event = {'rawPath': '/prod/s/'+created['shareId'], 'requestContext': {'http': {'method': 'GET'}}, 'headers': {'accept-language': language}}
            self.assertIn(text, handler.lambda_handler(event, None)['body'])

    def test_invalid_missing_and_oversized_requests(self):
        self.assertEqual(self.request('/shares/'+'x'*32)['statusCode'], 404)
        self.assertEqual(self.request('/shares/../secret')['statusCode'], 404)
        self.assertEqual(self.request('/shares', 'POST', {'photo':'not-jpeg'}, 'demo-key')['statusCode'], 400)
        self.assertEqual(self.request('/shares', 'POST', {'photo':encoded_test_image(), 'featureData':'bad',
            'featureAlgorithm':'opencv-5-orb-v1'}, 'demo-key')['statusCode'], 400)
        self.assertEqual(self.request('/shares', 'POST', {'photo':'x'*3_000_000}, 'demo-key')['statusCode'], 413)
        self.assertEqual(self.request('/shares', 'POST', [], 'demo-key')['statusCode'], 400)

if __name__=='__main__': unittest.main()
