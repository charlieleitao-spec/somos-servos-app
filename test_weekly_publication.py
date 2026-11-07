"""Exercita o fluxo semanal real; somente HTTP e fontes externas são simulados."""
import datetime as dt
import importlib
import json
import os
import re
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import publication_run as audit
import weekly_servita as weekly

WORKFLOW = Path(__file__).parent / '.github/workflows/publicacao-diaria-blogger.yml'


class WeeklyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = os.getcwd()
        os.chdir(self.tmp.name)
        self.env = patch.dict(os.environ, {
            'GITHUB_REF': 'refs/heads/main',
            'WEEKLY_START_DATE': '2026-11-08',
            'WEEKLY_DRY_RUN': 'false', 'WEEKLY_DRAFT': 'false',
            'GITHUB_STEP_SUMMARY': 'summary.md',
        }, clear=True)
        self.env.start()
        importlib.reload(weekly)
        self.posts = []
        self.requests = []
        self.readback_status = None
        self.saved = None

    def tearDown(self):
        self.env.stop()
        os.chdir(self.cwd)
        self.tmp.cleanup()
        importlib.reload(weekly)

    def request(self, url, method='GET', data=None, *args, **kwargs):
        self.requests.append((url, method))
        if method == 'POST':
            state = 'DRAFT' if parse_qs(urlparse(url).query)['isDraft'] == ['true'] else 'LIVE'
            self.saved = dict(json.loads(data), id='123', status=state,
                              url='https://somosservos.blogspot.com/weekly.html')
            return self.saved
        return dict(self.saved, status=self.readback_status or self.saved['status'])

    def run_week(self):
        with patch.object(weekly, 'access_token', return_value='token'), \
             patch.object(weekly, 'locate_blog', return_value={'id': '1'}), \
             patch.object(weekly, 'load_santoral', return_value=[]), \
             patch.object(weekly, 'list_existing_posts', return_value=self.posts), \
             patch.object(audit, 'safe_request', side_effect=self.request), \
             patch.object(audit, 'check_public_url') as public:
            result = audit.run('semanal')
            return result, public.call_count

    def test_scheduled_publication_requires_live_and_public_url(self):
        self.assertEqual(self.run_week(), (0, 1))
        self.assertEqual(self.saved['status'], 'LIVE')
        self.assertIn('publicado_http_200', Path('publicacoes.csv').read_text())
        self.assertIn('isDraft=false', self.requests[0][0])

    def test_workflow_modes_resolve_to_string_booleans(self):
        workflow = WORKFLOW.read_text()
        self.assertIn('cron: "0 11 * * 0"', workflow)
        for event, schedule, manual_draft, expected in (
            ('schedule', '0 11 * * 0', False, ('false', 'false')),
            ('schedule', '5 9 * * *', False, ('true', 'true')),
            ('workflow_dispatch', '', False, ('true', 'true')),
            ('workflow_dispatch', '', True, ('false', 'true')),
        ):
            with self.subTest(event=event, schedule=schedule, draft=manual_draft):
                resolved = []
                for key in ('WEEKLY_DRY_RUN', 'WEEKLY_DRAFT'):
                    expression = re.search(r'^      ' + key + r': \$\{\{ (.+) \}\}$', workflow, re.M)[1]
                    for name, value in (
                        ('github.event_name', event), ('github.event.schedule', schedule),
                        ('inputs.create_weekly_draft', manual_draft),
                    ):
                        expression = expression.replace(name, repr(value))
                    resolved.append(eval(expression.replace('&&', 'and').replace('||', 'or'),
                                         {'__builtins__': {}}, {}))
                self.assertEqual(tuple(resolved), expected)

    def test_manual_preview_creates_nothing(self):
        os.environ.update(WEEKLY_DRY_RUN='true', WEEKLY_DRAFT='true')
        self.assertEqual(self.run_week(), (0, 0))
        self.assertEqual(self.requests, [])
        self.assertIn('previa_sem_publicacao', Path('publicacoes.csv').read_text())

    def test_explicit_manual_draft_is_not_publication(self):
        os.environ['WEEKLY_DRAFT'] = 'true'
        self.assertEqual(self.run_week(), (0, 0))
        self.assertEqual(self.saved['status'], 'DRAFT')
        self.assertIn('rascunho_confirmado_api', Path('publicacoes.csv').read_text())

    def test_existing_live_draft_or_scheduled_never_creates_duplicate(self):
        for state in ('LIVE', 'DRAFT', 'SCHEDULED'):
            with self.subTest(state=state):
                importlib.reload(weekly)
                self.posts = [dict(id='existing', status=state,
                    content=weekly.source_marker(dt.date(2026, 11, 8)),
                    url='https://somosservos.blogspot.com/existing.html')]
                self.requests.clear()
                self.assertEqual(self.run_week(), (0, int(state == 'LIVE')))
                self.assertEqual(self.requests, [])
                self.assertIn('duplicado_', Path('publicacoes.csv').read_text())

    def test_readback_wrong_state_fails_without_recreating(self):
        self.readback_status = 'DRAFT'
        self.assertEqual(self.run_week(), (1, 0))
        self.assertEqual(sum(method == 'POST' for _, method in self.requests), 1)
        self.assertIn('erro', Path('publicacoes.csv').read_text())

    def test_local_invocation_defaults_to_preview(self):
        os.environ.pop('WEEKLY_DRY_RUN')
        os.environ.pop('WEEKLY_DRAFT')
        self.assertEqual(self.run_week(), (0, 0))
        self.assertEqual(self.requests, [])

    def test_content_keeps_santoral_cards_saturday_and_app(self):
        card = Path('cartao-11-09.png')
        card.touch()
        text = weekly.make_content([{'month': 11, 'day': 9, 'title': 'Memória & teste'}],
                                    dt.date(2026, 11, 8), '.')
        for expected in ('Memória &amp; teste', 'cartao-11-09.png',
                         weekly.SABADO_MARIANO, weekly.APP_URL, '2026-11-08'):
            self.assertIn(expected, text)
        card.unlink()
        self.assertNotIn('<img', weekly.make_content([], dt.date(2026, 11, 8), '.'))


if __name__ == '__main__':
    unittest.main()
