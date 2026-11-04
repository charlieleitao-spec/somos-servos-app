#!/usr/bin/env python3
"""Publicação autorizada, retomável e sem sobrescrita dos oito originais."""
import hashlib
import json
from pathlib import Path
import urllib.parse

import blogger_publish as api

MANIFEST = Path('editorial/serie-maria-20261104.json')
SERIES = 'Com Maria, no caminho da Vida Religiosa Consagrada'
ROOT = 'https://www.googleapis.com/blogger/v3/blogs/'


def validate(manifest):
    rows = manifest.get('articles', [])
    if manifest.get('series') != SERIES or [a.get('number') for a in rows] != list(range(1, 9)):
        raise RuntimeError('Manifesto não contém exatamente os oito artigos em ordem.')
    titles = set()
    for a in rows:
        title = a.get('title', '').strip().casefold()
        content = a.get('content', '')
        marker = 'somosservos-serie-maria-vrc-20261102-' + str(a['number']).zfill(2)
        if not title or title in titles:
            raise RuntimeError('Título vazio ou repetido no manifesto.')
        titles.add(title)
        if a.get('marker') != marker or content.count(marker) != 1:
            raise RuntimeError('Identificador estável inválido.')
        if hashlib.sha256(content.encode()).hexdigest() != a.get('sha256'):
            raise RuntimeError('Conteúdo diverge do manifesto aprovado.')
        if f'— {a["number"]}/8' not in content or 'Referências bíblicas:' not in content or 'Oração' not in content:
            raise RuntimeError('Artigo incompleto.')
    return rows


def all_posts(blog_id, token):
    posts = []
    page_token = None
    while True:
        query = [('maxResults', '500'), ('fetchBodies', 'true'),
                 ('status', 'live'), ('status', 'draft'), ('status', 'scheduled')]
        if page_token:
            query.append(('pageToken', page_token))
        page = api.request_json(ROOT + blog_id + '/posts?' + urllib.parse.urlencode(query),
                                token=token, operation='Inventário completo pré-publicação')
        posts.extend(page.get('items', []))
        page_token = page.get('nextPageToken')
        if not page_token:
            return posts


def matches(a, posts):
    return [p for p in posts if p.get('title', '').strip().casefold() == a['title'].strip().casefold()
            or a['marker'] in p.get('content', '')]


def verify(a, post):
    if not post.get('id') or post.get('title') != a['title']:
        raise RuntimeError('Identidade do artigo não confirmada na API.')
    if post.get('content') != a['content']:
        raise RuntimeError('Conteúdo da leitura de volta diverge do original enviado.')
    url = urllib.parse.urlsplit(post.get('url', ''))
    if url.scheme != 'https' or url.hostname != api.TARGET_HOST:
        raise RuntimeError('URL de publicação não confirmada.')


def publish(rows, blog_id, token):
    posts = all_posts(blog_id, token)
    # Toda colisão é examinada ANTES da primeira criação. Nunca altera um existente.
    existing = {}
    for a in rows:
        found = matches(a, posts)
        if len(found) > 1:
            raise RuntimeError(f'Múltiplos candidatos para artigo {a["number"]}; nenhuma nova criação.')
        if found:
            p = found[0]
            verify(a, p)
            if p.get('status') != 'LIVE':
                raise RuntimeError('Artigo já existe como rascunho/agendado; criação interrompida.')
            existing[a['number']] = p
    results = []
    for a in rows:
        p = existing.get(a['number'])
        action = 'existente preservado'
        if p is None:
            payload = {'kind': 'blogger#post', 'title': a['title'],
                       'content': a['content'], 'labels': a['labels']}
            created = api.request_json(ROOT + blog_id + '/posts/?isDraft=false', 'POST',
                json.dumps(payload, ensure_ascii=False).encode(), token,
                'application/json; charset=UTF-8', 'Publicação autorizada')
            if not created.get('id'):
                raise RuntimeError('Criação não devolveu ID; conferir inventário antes de retomar.')
            p = api.request_json(ROOT + blog_id + '/posts/' + created['id'] + '?fetchBodies=true',
                                 token=token, operation='Leitura de confirmação')
            verify(a, p)
            if p.get('status') != 'LIVE':
                # A API pode omitir status no recurso individual. A listagem live deve conter o ID.
                live = api.request_json(ROOT + blog_id + '/posts?' + urllib.parse.urlencode({
                    'status': 'live', 'maxResults': '500', 'fetchBodies': 'false'}),
                    token=token, operation='Confirmação do estado publicado')
                if not any(x.get('id') == p['id'] for x in live.get('items', [])):
                    raise RuntimeError('Estado LIVE não confirmado; interrompendo novas criações.')
            action = 'publicado e verificado'
        result = {'number': a['number'], 'title': a['title'], 'id': p['id'],
                  'url': p['url'], 'action': action, 'content_sha256': a['sha256']}
        results.append(result)
        Path('resultado-serie-maria.json').write_text(json.dumps(results, ensure_ascii=False, indent=2))
        print(json.dumps(result, ensure_ascii=False), flush=True)
    return results


def main():
    rows = validate(json.loads(MANIFEST.read_text()))
    token = api.get_access_token()
    blog = api.find_blog(token)
    publish(rows, str(blog['id']), token)


if __name__ == '__main__':
    main()
