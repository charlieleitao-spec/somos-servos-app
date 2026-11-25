"""Atualização pontual autorizada: link e rótulo de Liturgia OSM em uma página existente."""
import json
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from blogger_inventory import access_token, json_request, API_BASE

BLOG = '7202450909909295362'
TARGET = '/p/aplicativos-servitas.html'
OLD = 'https://github.com/charlieleitao-spec/liturgia-osm/releases/download/v4.9.137/Liturgia-OSM-4.9.137.apk'
NEW = 'https://github.com/charlieleitao-spec/liturgia-osm/releases/download/v4.9.138/Liturgia-OSM-4.9.138.apk'
OLD_LABEL = 'Baixar Liturgia OSM 4.9.137 (Android)'
NEW_LABEL = 'Baixar Liturgia OSM 4.9.138 (Android)'

def replace(content):
    if OLD not in content and OLD_LABEL not in content and content.count(NEW) == 1 and content.count(NEW_LABEL) == 1:
        return content
    assert content.count(OLD) == 1, 'Link anterior ausente ou ambíguo: nenhuma alteração.'
    assert content.count(OLD_LABEL) == 1, 'Rótulo anterior ausente ou ambíguo: nenhuma alteração.'
    assert NEW not in content, 'Novo link já existe em contexto conflitante: nenhuma alteração.'
    return content.replace(OLD, NEW).replace(OLD_LABEL, NEW_LABEL)

def main():
    with urlopen(Request(NEW, method='HEAD'), timeout=45) as response:
        assert response.status == 200, 'APK estável ainda não disponível.'
    token = access_token()
    candidates = []
    page_token = ''
    while True:
        url = f'{API_BASE}/blogs/{BLOG}/pages?maxResults=100&fetchBodies=true'
        if page_token:
            from urllib.parse import quote
            url += '&pageToken=' + quote(page_token, safe='')
        result = json_request(url, token=token, operation='Leitura de páginas')
        for page in result.get('items', []):
            u = urlsplit(page.get('url', ''))
            if u.hostname == 'somosservos.blogspot.com' and u.path == TARGET:
                candidates.append(page)
        page_token = result.get('nextPageToken', '')
        if not page_token:
            break
    assert len(candidates) == 1, 'Página de instalação ausente ou ambígua: nenhuma alteração.'
    page = candidates[0]
    assert str(page['id']).isdigit()
    endpoint = f'{API_BASE}/blogs/{BLOG}/pages/{page["id"]}'
    before = json_request(endpoint, token=token, operation='Leitura da página existente')
    original = before['content']
    patched = replace(original)
    audit = Path('auditoria-link-4.9.138')
    audit.mkdir(exist_ok=True)
    (audit/'anterior.html').write_text(original)
    if patched != original:
        fresh = json_request(endpoint, token=token, operation='Conferência antes da alteração')
        assert fresh.get('updated') == before.get('updated') and fresh['content'] == original, 'Página alterada simultaneamente: nenhuma escrita.'
        json_request(endpoint, method='PATCH', data=json.dumps({'content':patched}).encode(), token=token,
                     content_type='application/json; charset=utf-8', operation='Atualização pontual do link autorizado')
    after = json_request(endpoint, token=token, operation='Conferência após atualização')
    assert after['content'] == patched, 'Conteúdo retornado diverge da alteração pontual.'
    (audit/'atual.html').write_text(after['content'])
    evidence = {'blog_id': BLOG, 'page_id':str(page['id']), 'url':'https://somosservos.blogspot.com'+TARGET,
                'novo_link':NEW, 'alterado':patched != original, 'resultado':'link e rótulo confirmados na API; demais conteúdos preservados'}
    (audit/'resultado.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2))
    print(json.dumps(evidence, ensure_ascii=False))

if __name__ == '__main__':
    main()
