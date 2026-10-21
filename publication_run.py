#!/usr/bin/env python3
"""Executa o publicador com autenticação prévia e evidência, sem alterar conteúdo."""
import csv
import datetime as dt
import html
import importlib
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.request
from zoneinfo import ZoneInfo

OAUTH_ERRORS = {'invalid_grant', 'invalid_client', 'invalid_request', 'unauthorized_client',
                'unsupported_grant_type', 'invalid_scope', 'access_denied'}


def safe_request(url, method='GET', data=None, token=None, content_type=None, operation='API'):
    request = urllib.request.Request(url, data=data, method=method)
    if token:
        request.add_header('Authorization', f'Bearer {token}')
    if content_type:
        request.add_header('Content-Type', content_type)
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        code = ''
        if url == 'https://oauth2.googleapis.com/token':
            try:
                value = json.loads(exc.read()).get('error')
                if isinstance(value, str) and value in OAUTH_ERRORS:
                    code = value
            except (ValueError, AttributeError):
                pass
        advice = (' Renove BLOGGER_REFRESH_TOKEN usando o mesmo cliente OAuth; confira o modo Teste no Google Cloud.'
                  if code == 'invalid_grant' else '')
        raise RuntimeError(f'{operation}: HTTP {exc.code}' + (f' ({code})' if code else '') + '.' + advice) from None
    except (urllib.error.URLError, TimeoutError):
        raise RuntimeError(f'{operation}: falha de rede ou timeout.') from None


def check_public_url(url):
    if not url or not url.startswith(('https://', 'http://')):
        raise RuntimeError('API não devolveu URL pública válida; HTTP 200 não comprovado.')
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'SomosServosVerifier/1.0'}), timeout=45) as response:
            status = response.status
    except urllib.error.HTTPError as exc:
        status = exc.code
    except (urllib.error.URLError, TimeoutError):
        raise RuntimeError('URL pública: falha de rede ou timeout; HTTP 200 não comprovado.') from None
    if status != 200:
        raise RuntimeError(f'URL pública respondeu HTTP {status}; esperado 200.')


def record(result):
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a', encoding='utf-8') as stream:
            stream.write('\n### Publicação — ' + result['tipo'] + '\n\n')
            for key in ('data', 'tipo', 'titulo', 'id', 'url', 'status', 'erro'):
                value = html.escape(str(result.get(key) or '—')).replace('\n', ' ')
                stream.write(f'- **{key}:** {value}\n')
            stream.write('\nPrévia não cria post. Rascunho não comprova publicação pública.\n')
    # Uma linha por execução do publicador; inclui erro, prévia e duplicidade.
    path = Path('publicacoes.csv')
    header = not path.exists() or path.stat().st_size == 0
    with path.open('a', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream)
        if header:
            writer.writerow(['data', 'tipo', 'URL', 'status'])
        writer.writerow([result['data'], result['tipo'], result['url'], result['status']])
    # Somente as linhas desta execução serão aplicadas sobre a branch atualizada.
    with open('.publicacoes-pendentes.jsonl', 'a', encoding='utf-8') as stream:
        stream.write(json.dumps(result, ensure_ascii=False) + '\n')


def run(kind):
    result = dict(data=dt.datetime.now(ZoneInfo('America/Sao_Paulo')).isoformat(timespec='seconds'),
                  tipo=kind, titulo='', id='', url='', status='erro', erro='')
    module = importlib.import_module('blogger_daily_publish' if kind == 'diário' else 'weekly_servita')
    dry = os.getenv('DRY_RUN' if kind == 'diário' else 'WEEKLY_DRY_RUN', 'false').lower() == 'true'
    draft = kind == 'semanal' or os.getenv('DRAFT', 'false').lower() == 'true'
    created = False
    duplicate = False
    original_find = module.find_duplicate
    original_prepare = module.prepare_post if kind == 'diário' else module.title_for

    def request(*args, **kwargs):
        nonlocal created
        response = safe_request(*args, **kwargs)
        method = args[1] if len(args) > 1 else kwargs.get('method', 'GET')
        if method == 'POST' and '/posts/' in args[0]:
            created = True
            result.update(titulo=response.get('title', ''), id=response.get('id', ''), url=response.get('url', ''))
        return response

    def find(*args):
        nonlocal duplicate
        post = original_find(*args)
        if post:
            duplicate = True
            result.update(titulo=post.get('title', ''), id=post.get('id', ''), url=post.get('url', ''))
            result['status'] = 'duplicado_' + str(post.get('status', 'desconhecido')).lower()
            if not dry and str(post.get('status', '')).upper() == 'LIVE':
                check_public_url(result['url'])
                result['status'] = 'duplicado_live_http_200'
        return post

    def prepare(*args, **kwargs):
        value = original_prepare(*args, **kwargs)
        result['titulo'] = value[0] if kind == 'diário' else value
        return value

    try:
        module.json_request = request
        module.find_duplicate = find
        if kind == 'diário':
            module.prepare_post = prepare
        else:
            module.title_for = prepare
        # Executado antes de geração de conteúdo e de qualquer escrita no Blogger.
        token = module.access_token()
        module.locate_blog(token)
        module.access_token = lambda: token
        print('Verificação inicial OAuth e acesso ao blog: OK (sem escrita).')
        if os.getenv('GITHUB_REF') and os.getenv('GITHUB_REF') != 'refs/heads/main' and not dry:
            raise RuntimeError('Publicação/rascunho permitido somente na branch main.')
        module.main() if kind == 'diário' else module.main([])
        if created:
            if draft:
                result['status'] = 'rascunho_confirmado_api'
            else:
                check_public_url(result['url'])
                result['status'] = 'publicado_http_200'
        elif not duplicate:
            result['status'] = 'previa_sem_publicacao' if dry else 'sem_celebracao'
        return 0
    except Exception as exc:
        result['status'] = 'erro'
        result['erro'] = str(exc)
        print(f'Falha: {exc}', file=sys.stderr)
        return 1
    finally:
        record(result)


if __name__ == '__main__':
    if len(sys.argv) != 2 or sys.argv[1] not in ('diário', 'semanal'):
        sys.exit('Uso: publication_run.py diário|semanal')
    sys.exit(run(sys.argv[1]))
