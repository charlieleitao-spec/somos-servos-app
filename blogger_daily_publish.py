#!/usr/bin/env python3
"""Publica a celebração própria OSM do dia no Blogger, com deduplicação e leitura de volta."""
import datetime as dt
import html
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

TOKEN_URL = "https://oauth2.googleapis.com/token"
BLOGS_URL = "https://www.googleapis.com/blogger/v3/users/self/blogs"
DATA_BASE = "https://raw.githubusercontent.com/charlieleitao-spec/liturgia-osm/main/www/data/"
TARGET_HOST = "somosservos.blogspot.com"
TIMEZONE = ZoneInfo("America/Sao_Paulo")
LABELS = ["Ordem dos Servos de Maria", "Liturgia OSM", "Santos e Beatos"]


def required(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Configuração ausente: {name}")
    return value


def json_request(url, method="GET", data=None, token=None, content_type=None, operation="API"):
    request = urllib.request.Request(url, data=data, method=method)
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    if content_type:
        request.add_header("Content-Type", content_type)
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        # Não imprime o corpo da resposta: evita que erros de autenticação exponham dados.
        raise RuntimeError(f"{operation} respondeu HTTP {exc.code}.") from None


def get_public_json(name):
    request = urllib.request.Request(DATA_BASE + name, headers={"User-Agent": "SomosServosDailyPublisher/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            return json.load(response)
    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Não foi possível carregar {name} da fonte litúrgica.") from None


def access_token():
    form = urllib.parse.urlencode({
        "client_id": required("BLOGGER_CLIENT_ID"),
        "client_secret": required("BLOGGER_CLIENT_SECRET"),
        "refresh_token": required("BLOGGER_REFRESH_TOKEN"),
        "grant_type": "refresh_token",
    }).encode()
    result = json_request(TOKEN_URL, "POST", form, content_type="application/x-www-form-urlencoded",
                         operation="Autenticação OAuth")
    token = result.get("access_token")
    if not token:
        raise RuntimeError("Autenticação OAuth não devolveu token de acesso.")
    return token


def locate_blog(token):
    blogs = json_request(BLOGS_URL, token=token, operation="Consulta de blogs").get("items", [])
    blog = next((b for b in blogs if TARGET_HOST in (b.get("url") or "").lower()), None)
    if not blog:
        raise RuntimeError("O blog Somos Servos não foi localizado na conta autorizada.")
    return blog


def list_existing_posts(blog_id, token):
    url = f"https://www.googleapis.com/blogger/v3/blogs/{blog_id}/posts/?maxResults=500&fetchBodies=false"
    posts = []
    while url:
        page = json_request(url, token=token, operation="Consulta de postagens")
        posts.extend(page.get("items", []))
        next_token = page.get("nextPageToken")
        url = (f"https://www.googleapis.com/blogger/v3/blogs/{blog_id}/posts/"
               f"?maxResults=500&fetchBodies=false&pageToken={urllib.parse.quote(next_token)}") if next_token else None
    return posts


def paragraph_html(text):
    text = html.escape(text or "", quote=False).strip()
    if not text:
        return ""
    return "".join("<p>" + part.replace("\n", "<br>") + "</p>"
                   for part in text.split("\n\n") if part.strip())


def make_content(entry, office):
    title = entry.get("title") or entry.get("name")
    source_id = str(entry.get("id"))
    date_text = entry.get("date") or ""
    bio = paragraph_html(entry.get("bio", ""))
    prayer = paragraph_html(entry.get("prayer", ""))
    office_html = paragraph_html(office)
    return (
        f"<!-- somos-servos-source-id:{html.escape(source_id)} -->"
        f"<p><strong>{html.escape(date_text)} · {html.escape(entry.get('rank', ''))}</strong></p>"
        f"<h2>{html.escape(title)}</h2>"
        f"<h3>Memória</h3>{bio}"
        f"<h3>Oração</h3>{prayer}"
        f"<h3>Ofício próprio da Ordem</h3>{office_html}"
    )


def main():
    requested_date = os.environ.get("PUBLISH_DATE", "").strip()
    date = dt.date.fromisoformat(requested_date) if requested_date else dt.datetime.now(TIMEZONE).date()
    dry_run = os.environ.get("DRY_RUN", "false").strip().lower() == "true"

    santoral = get_public_json("santoral.json")
    offices = get_public_json("oficios-osm.json")
    entries = [item for item in santoral
               if int(item.get("day", 0)) == date.day and int(item.get("month", 0)) == date.month]
    if not entries:
        print(f"Sem celebração própria cadastrada para {date.isoformat()}; nenhuma postagem criada.")
        return
    if len(entries) > 1:
        raise RuntimeError(f"Há mais de uma celebração própria cadastrada para {date.isoformat()}; revisão necessária.")

    entry = entries[0]
    office = offices.get(str(entry.get("id")))
    if not isinstance(office, str) or not office.strip():
        print(f"Sem ofício próprio completo para o registro {entry.get('id')}; nenhuma postagem criada.")
        return

    title = f"{entry.get('title') or entry.get('name')} — Ofício próprio OSM"
    token = access_token()
    blog = locate_blog(token)
    posts = list_existing_posts(blog["id"], token)
    source_marker = f"somos-servos-source-id:{entry.get('id')}"
    duplicate = next((p for p in posts
                      if (p.get("title") or "").strip().casefold() == title.casefold()
                      or source_marker in (p.get("content") or "")), None)
    if duplicate:
        print(f"Já existe postagem correspondente (ID {duplicate.get('id')}); nenhuma duplicata criada.")
        return

    content = make_content(entry, office)
    if dry_run:
        print(f"Prévia sem publicação: {title}")
        print(f"Marcadores: {', '.join(LABELS)}")
        print(f"Conteúdo preparado; tamanho {len(content)} caracteres.")
        return

    payload = json.dumps({"kind": "blogger#post", "title": title, "content": content,
                          "labels": LABELS}, ensure_ascii=False).encode("utf-8")
    created = json_request(
        f"https://www.googleapis.com/blogger/v3/blogs/{blog['id']}/posts/",
        "POST", payload, token, "application/json; charset=UTF-8", "Criação da postagem")
    post_id = created.get("id")
    if not post_id:
        raise RuntimeError("A API não devolveu o identificador da postagem criada.")

    verified = json_request(
        f"https://www.googleapis.com/blogger/v3/blogs/{blog['id']}/posts/{post_id}?fetchBodies=true",
        token=token, operation="Verificação da postagem")
    if verified.get("id") != post_id or verified.get("title") != title:
        raise RuntimeError("A leitura de volta da API não confirmou título e identificador.")
    if source_marker not in (verified.get("content") or ""):
        raise RuntimeError("A leitura de volta da API não confirmou o marcador de origem.")
    print(f"Publicado e confirmado pela API: {verified.get('title')}")
    print(f"URL: {verified.get('url')}")
    print(f"ID da postagem confirmado: {post_id}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Falha: {exc}", file=sys.stderr)
        sys.exit(1)
