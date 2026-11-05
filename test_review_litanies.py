import copy
import unittest
from blogger_review_litanies import prepare, digest, verify


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.post = {'id': '1', 'title': 'Exemplo', 'status': 'LIVE', 'content': 'Antes.',
                     'url': 'https://somosservos.blogspot.com/2026/11/exemplo.html',
                     'published': '2026-10-01T12:00:00Z', 'labels': ['Ladainhas']}
        self.item = {**self.post, 'before': 'Antes.', 'after': 'Depois.',
                     'before_sha256': digest('Antes.'), 'after_sha256': digest('Depois.')}

    def test_exact_change_and_idempotent_resume(self):
        self.assertEqual(prepare(self.post, self.item), 'Depois.')
        self.post['content'] = 'Depois.'
        self.assertIsNone(prepare(self.post, self.item))

    def test_concurrent_edit_is_preserved(self):
        self.post['content'] = 'Antes. Outro editor acrescentou conteúdo.'
        with self.assertRaises(RuntimeError): prepare(self.post, self.item)

    def test_wrong_target_and_draft_rejected(self):
        for field, value in [('id', '2'), ('title', 'Outro'), ('status', 'DRAFT'), ('url', 'https://somosservos.blogspot.com/outro.html')]:
            post = {**self.post, field: value}
            with self.assertRaises(RuntimeError): prepare(post, self.item)

    def test_metadata_and_exact_readback(self):
        checked = {**self.post, 'content': 'Depois.'}
        verify(self.post, checked, 'Depois.')
        for field, value in [('published', '2026-11-05'), ('labels', []), ('content', 'Incompleto')]:
            with self.assertRaises(RuntimeError): verify(self.post, {**checked, field: value}, 'Depois.')


if __name__ == '__main__': unittest.main()
