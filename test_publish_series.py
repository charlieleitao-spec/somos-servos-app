import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import blogger_publish_series as s


class PublishTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads(s.MANIFEST.read_text())
        self.rows = s.validate(self.manifest)

    def post(self, a, status='LIVE'):
        return dict(id=str(a['number']), title=a['title'], content=a['content'],
                    status=status, url='https://somosservos.blogspot.com/2026/11/artigo-'+str(a['number'])+'.html')

    def test_corrupt_last_article_rejected_before_authentication(self):
        m = copy.deepcopy(self.manifest)
        m['articles'][-1]['content'] += 'alteração'
        with self.assertRaises(RuntimeError):
            s.validate(m)

    def test_draft_collision_prevents_all_creations(self):
        with patch.object(s, 'all_posts', return_value=[self.post(self.rows[-1], 'DRAFT')]), patch.object(s.api, 'request_json') as req:
            with self.assertRaises(RuntimeError):
                s.publish(self.rows, 'blog', 'token')
            req.assert_not_called()

    def test_restart_preserves_first_live_post_and_creates_remaining_seven(self):
        writes = []
        def req(url, method='GET', data=None, *args, **kwargs):
            if method == 'POST':
                payload = json.loads(data)
                n = next(a['number'] for a in self.rows if a['title'] == payload['title'])
                writes.append(n)
                return {'id': str(n)}
            n = int(url.split('/posts/')[1].split('?')[0])
            return self.post(self.rows[n-1])
        with tempfile.TemporaryDirectory() as d, patch.object(s, 'all_posts', return_value=[self.post(self.rows[0])]), patch.object(s.api, 'request_json', side_effect=req), patch.object(s.Path, 'write_text'):
            result = s.publish(self.rows, 'blog', 'token')
        self.assertEqual(writes, list(range(2, 9)))
        self.assertEqual(len(result), 8)

    def test_content_readback_mismatch_stops_after_first_creation(self):
        writes = []
        def req(url, method='GET', data=None, *args, **kwargs):
            if method == 'POST':
                writes.append(1)
                return {'id': '1'}
            p = self.post(self.rows[0]);p['content'] = 'diferente';return p
        with patch.object(s, 'all_posts', return_value=[]), patch.object(s.api, 'request_json', side_effect=req):
            with self.assertRaises(RuntimeError):
                s.publish(self.rows, 'blog', 'token')
        self.assertEqual(writes, [1])


if __name__ == '__main__':
    unittest.main()
