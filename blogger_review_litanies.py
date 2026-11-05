#!/usr/bin/env python3
"""Aplica somente cinco correções pontuais a posts LIVE existentes, sem criar posts."""
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urlparse
from blogger_publish import get_access_token, find_blog, request_json

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / 'editorial' / 'ladainhas-correcoes-20261104.json'


def digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def prepare(current, item):
    if str(current.get('id')) != item['id'] or current.get('title') != item['title']:
        raise RuntimeError('ID ou título divergente; nenhuma correção aplicada.')
    if urlparse(current.get('url', '')).path != urlparse(item['url']).path:
        raise RuntimeError('URL divergente; nenhuma correção aplicada.')
    if current.get('status') != 'LIVE':
        raise RuntimeError('Post não está LIVE; nenhuma correção aplicada.')
    body = current.get('content', '')
    if digest(body) == item['after_sha256']:
        return None
    if digest(body) != item['before_sha256']:
        raise RuntimeError('Conteúdo mudou desde a revisão; preservar edição concorrente.')
    if body.count(item['before']) != 1:
        raise RuntimeError('Trecho não é único; nenhuma correção aplicada.')
    updated = body.replace(item['before'], item['after'], 1)
    if digest(updated) != item['after_sha256']:
        raise RuntimeError('Resultado diverge do conteúdo revisado.')
    return updated


def verify(current, checked, expected):
    for key in ('id', 'title', 'published', 'labels', 'status'):
        if checked.get(key) != current.get(key):
            raise RuntimeError('Metadado não preservado: ' + key)
    if checked.get('content') != expected:
        raise RuntimeError('Leitura de volta não confirmou HTML exato.')
    if urlparse(checked.get('url', '')).path != urlparse(current.get('url', '')).path:
        raise RuntimeError('Permalink não preservado.')


def main():
    if os.environ.get('POST_CONTENT') != 'CORRIGIR_CINCO_TRECHOS_EXISTENTES':
        raise RuntimeError('Confirmação do manifesto ausente.')
    manifest = json.loads(MANIFEST.read_text())
    if len(manifest) != 5 or len({x['id'] for x in manifest}) != 5:
        raise RuntimeError('Manifesto deve conter cinco IDs distintos.')
    token = get_access_token()
    blog = find_blog(token)
    if urlparse(blog['url']).hostname != 'somosservos.blogspot.com':
        raise RuntimeError('Host do blog divergente.')
    prefix = f"https://www.googleapis.com/blogger/v3/blogs/{blog['id']}/posts/"
    pending = []
    # Toda a pré-validação ocorre antes da primeira mutação.
    for item in manifest:
        url = prefix + item['id']
        current = request_json(url + '?fetchBodies=true&view=ADMIN', token=token)
        pending.append((item, current, prepare(current, item), url))
    result = []
    for item, current, updated, url in pending:
        if updated is not None:
            # Releitura imediatamente anterior à escrita e precondição ETag.
            fresh = request_json(url + '?fetchBodies=true&view=ADMIN', token=token)
            updated = prepare(fresh, item)
            current = fresh
            if updated is not None:
                # PATCH somente content: título, data, rótulos e permalink preservados.
                payload = json.dumps({'content': updated}, ensure_ascii=False).encode()
                import urllib.request, urllib.error
                req = urllib.request.Request(url, data=payload, method='PATCH')
                req.add_header('Authorization', 'Bearer ' + token)
                req.add_header('Content-Type', 'application/json; charset=UTF-8')
                if fresh.get('etag'):
                    req.add_header('If-Match', fresh['etag'])
                try:
                    with urllib.request.urlopen(req, timeout=45) as response:
                        json.load(response)
                except urllib.error.HTTPError as exc:
                    raise RuntimeError(f'Correção respondeu HTTP {exc.code}; sem repetição automática.') from None
        expected = updated if updated is not None else current['content']
        checked = request_json(url + '?fetchBodies=true&view=ADMIN', token=token)
        verify(current, checked, expected)
        record = {'id': item['id'], 'title': item['title'], 'url': checked['url'],
                  'sha256': digest(expected), 'result': 'corrigido' if updated is not None else 'já conferido'}
        result.append(record)
        print(json.dumps(record, ensure_ascii=False))
    print('Confirmado: cinco posts existentes; nenhum post criado; metadados preservados.')
    Path('ladainhas-correcoes-result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        raise SystemExit('Falha segura: ' + str(exc))
