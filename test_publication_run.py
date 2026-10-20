import contextlib
import csv
import importlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
import publication_run as audit


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.cwd = os.getcwd()
        os.chdir(self.temp.name)
        self.env = patch.dict(os.environ, {'GITHUB_STEP_SUMMARY': 'summary.md', 'DRY_RUN': 'false', 'DRAFT': 'false', 'WEEKLY_DRY_RUN': 'false', 'GITHUB_REF': 'refs/heads/main'}, clear=True)
        self.env.start()
        self.module = importlib.reload(importlib.import_module('blogger_daily_publish'))

    def tearDown(self):
        self.env.stop()
        os.chdir(self.cwd)
        self.temp.cleanup()

    def run_case(self, post=None, public_error=None, auth_error=None, duplicate=False):
        post = post or {'title': 'Título, com vírgula', 'id': '123', 'url': 'https://somosservos.blogspot.com/post.html', 'status': 'LIVE'}
        def main():
            if duplicate:
                self.module.find_duplicate([dict(post, content='marker')], 'marker')
            else:
                self.module.json_request('https://www.googleapis.com/blogger/v3/blogs/1/posts/', 'POST')
        with patch.object(self.module, 'access_token', side_effect=auth_error, return_value='secret-token'), patch.object(self.module, 'locate_blog', return_value={'id':'1'}), patch.object(self.module, 'main', side_effect=main) as work, patch.object(audit, 'safe_request', return_value=post), patch.object(audit, 'check_public_url', side_effect=public_error) as check:
            status = audit.run('diário')
            return status, work.call_count, check.call_count

    def test_public_success_records_api_fields(self):
        self.assertEqual(self.run_case(), (0,1,1))
        summary = Path('summary.md').read_text()
        self.assertIn('123', summary)
        self.assertIn('publicado_http_200', summary)
        self.assertEqual(len(list(csv.reader(io.StringIO(Path('publicacoes.csv').read_text())))), 2)

    def test_http_failure_exits_one_preserving_created_id(self):
        self.assertEqual(self.run_case(public_error=RuntimeError('URL pública respondeu HTTP 404; esperado 200.'))[0], 1)
        summary = Path('summary.md').read_text()
        self.assertIn('123', summary)
        self.assertIn('404', summary)

    def test_preflight_failure_stops_before_publisher(self):
        self.assertEqual(self.run_case(auth_error=RuntimeError('Autenticação OAuth: HTTP 400 (invalid_grant).')), (1,0,0))
        self.assertIn('invalid_grant', Path('summary.md').read_text())

    def test_duplicate_kept_and_verified(self):
        self.assertEqual(self.run_case(duplicate=True), (0,1,1))
        self.assertIn('duplicado_live_http_200', Path('summary.md').read_text())

    def test_draft_never_claims_public_http(self):
        os.environ['DRAFT'] = 'true'
        self.assertEqual(self.run_case(), (0,1,0))
        self.assertIn('rascunho_confirmado_api', Path('summary.md').read_text())

    def test_oauth_only_emits_allowed_error_code(self):
        body = io.BytesIO(json.dumps({'error':'invalid_grant','error_description':'SECRET-VALUE'}).encode())
        error = urllib.error.HTTPError('url',400,'bad',{},body)
        with patch('urllib.request.urlopen', side_effect=error):
            with self.assertRaises(RuntimeError) as caught:
                audit.safe_request('https://oauth2.googleapis.com/token','POST')
        self.assertIn('invalid_grant', str(caught.exception))
        self.assertNotIn('SECRET-VALUE', str(caught.exception))

    def test_get_requires_exact_200(self):
        for code in (201,204,404,500):
            with self.subTest(code=code), patch('urllib.request.urlopen') as urlopen:
                urlopen.return_value.__enter__.return_value.status = code
                with self.assertRaises(RuntimeError):
                    audit.check_public_url('https://somosservos.blogspot.com/test')

    def test_weekly_preview_does_not_create_post(self):
        os.environ['WEEKLY_DRY_RUN']='true'
        module=importlib.reload(importlib.import_module('weekly_servita'))
        with patch.object(module,'access_token',return_value='token'), patch.object(module,'locate_blog',return_value={'id':'1'}), patch.object(module,'load_santoral',return_value=[]), patch.object(module,'create_post') as create:
            self.assertEqual(audit.run('semanal'),0)
            create.assert_not_called()
        self.assertIn('previa_sem_publicacao',Path('summary.md').read_text())

if __name__ == '__main__':
    unittest.main()
