import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "feeds", Path(__file__).resolve().parents[1] / "scripts/atualizar-feeds.py"
)
feeds = importlib.util.module_from_spec(spec)
spec.loader.exec_module(feeds)


class FeedTests(unittest.TestCase):
    def test_rss_rejects_external_destinations_and_duplicates(self):
        xml = '''<rss><channel>
        <item><title>Falsa</title><link>https://cnbb.org.br.evil.test/a</link></item>
        <item><title>Notícia &amp; fé</title><link>https://www.cnbb.org.br/a/</link></item>
        <item><title>Duplicada</title><link>https://www.cnbb.org.br/a/</link></item>
        <item><title>Script</title><link>javascript:alert(1)</link></item>
        </channel></rss>'''
        self.assertEqual(feeds.parse_feed(xml, "cnbb.org.br"), [
            {"title": "Notícia & fé", "link": "https://www.cnbb.org.br/a/"}
        ])

    def test_atom_uses_alternate_link(self):
        xml = '''<feed xmlns="http://www.w3.org/2005/Atom"><entry>
        <title>Encontro</title><link rel="self" href="https://crbnacional.org.br/feed/1"/>
        <link rel="alternate" href="https://crbnacional.org.br/encontro/"/>
        </entry></feed>'''
        self.assertEqual(feeds.parse_feed(xml, "crbnacional.org.br")[0]["link"],
                         "https://crbnacional.org.br/encontro/")

    def test_unavailable_sources_preserve_last_lists(self):
        original = {"version": 1, "sources": {
            key: {"items": [{"title": "Anterior", "link": page}],
                  "updated_at": "2026-10-28T12:00:00+00:00"}
            for key, (_, _, page, _) in feeds.SOURCES.items()
        }}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "noticias.json"
            path.write_text(json.dumps(original))
            with patch.object(feeds, "OUTPUT", path), patch.object(
                feeds, "fetch_source", side_effect=TimeoutError("fonte indisponível")
            ):
                with self.assertRaises(SystemExit):
                    feeds.main()
            self.assertEqual(json.loads(path.read_text()), original)


if __name__ == "__main__":
    unittest.main()
