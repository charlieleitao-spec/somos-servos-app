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

    def test_duplicate_without_explicit_status_uses_the_list_filter(self):
        for status, public_checks in (('live', 1), ('draft', 0), ('scheduled', 0)):
            with self.subTest(status=status):
                self.module = importlib.reload(self.module)
                post = {'id': '123', 'title': 'Celebração', 'url': 'https://somosservos.blogspot.com/post.html', 'content': 'marker'}

                def request(url, **kwargs):
                    return {'items': [post.copy()]} if url.endswith(f'&status={status}') else {}

                def main():
                    posts = self.module.list_existing_posts('1', 'token')
                    self.module.find_duplicate(posts, 'marker')

                with patch.object(self.module, 'access_token', return_value='token'), \
                     patch.object(self.module, 'locate_blog', return_value={'id': '1'}), \
                     patch.object(self.module, 'main', side_effect=main), \
                     patch.object(audit, 'safe_request', side_effect=request) as api, \
                     patch.object(audit, 'check_public_url') as check:
                    self.assertEqual(audit.run('diário'), 0)
                    self.assertEqual(api.call_count, 3)
                    self.assertEqual(check.call_count, public_checks)
                result = json.loads(Path('.publicacoes-pendentes.jsonl').read_text().splitlines()[-1])
                suffix = '_http_200' if public_checks else ''
                self.assertEqual(result['status'], f'duplicado_{status}{suffix}')
                self.assertEqual(result['id'], '123')

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

    def test_rate_limit_preserves_new_and_existing_publication_evidence(self):
        for duplicate, expected in (
            (False, 'publicado_link_pendente'),
            (True, 'duplicado_live_link_pendente'),
        ):
            with self.subTest(duplicate=duplicate):
                self.module = importlib.reload(self.module)
                error = audit.PublicVerificationPending('URL pública respondeu HTTP 429.')
                self.assertEqual(self.run_case(public_error=error, duplicate=duplicate), (0, 1, 1))
                result = json.loads(Path('.publicacoes-pendentes.jsonl').read_text().splitlines()[-1])
                self.assertEqual(result['status'], expected)
                self.assertEqual(result['id'], '123')
                self.assertEqual(result['titulo'], 'Título, com vírgula')
                self.assertEqual(result['url'], 'https://somosservos.blogspot.com/post.html')
                self.assertIn('429', result['erro'])

    def test_rate_limit_retries_only_the_public_get(self):
        url = 'https://somosservos.blogspot.com/test'
        for delays, retry_succeeds, expected_sleep in (
            (('2',), True, [2]),
            (('2', '2'), False, [2]),
            (('120',), False, []),
        ):
            with self.subTest(delays=delays):
                errors = [urllib.error.HTTPError(url, 429, 'limited', {'Retry-After': delay}, None)
                          for delay in delays]
                with patch('urllib.request.urlopen') as urlopen, patch.object(audit.time, 'sleep') as sleep:
                    if retry_succeeds:
                        success = urlopen.return_value
                        success.__enter__.return_value.status = 200
                        urlopen.side_effect = [*errors, success]
                        audit.check_public_url(url)
                    else:
                        urlopen.side_effect = errors
                        with self.assertRaises(audit.PublicVerificationPending):
                            audit.check_public_url(url)
                    self.assertEqual(urlopen.call_count, 1 + len(expected_sleep))
                    self.assertTrue(all(call.args[0].get_method() == 'GET' for call in urlopen.call_args_list))
                    self.assertEqual([call.args[0] for call in sleep.call_args_list], expected_sleep)

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
