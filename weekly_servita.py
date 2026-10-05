#!/usr/bin/env python3
"""Prepara o resumo semanal servita para o Blogger, sempre como rascunho."""
import argparse
import datetime as dt
import html
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

DATA_URL = "https://raw.githubusercontent.com/charlieleitao-spec/liturgia-osm/main/www/data/santoral.json"
BLOGS_URL = "https://www.googleapis.com/blogger/v3/users/self/blogs"
TARGET_HOST = "somosservos.blogspot.com"
TIMEZONE = ZoneInfo("America/Sao_Paulo")
APP_URL = "https://charlieleitao-spec.github.io/hoje-familia-servita/"
PAGES_URL = "https://charlieleitao-spec.github.io/somos-servos-app/"
WEEKDAYS = ("segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
            "sexta-feira", "sábado", "domingo")
LABELS = ["Semana servita"]


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
        raise RuntimeError(f"{operation} respondeu HTTP {exc.code}.") from None


def load_santoral(path=None):
    if path:
        with Path(path).open(encoding="utf-8") as source:
            return json.load(source)
    request = urllib.request.Request(DATA_URL, headers={"User-Agent": "SomosServosWeekly/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            return json.load(response)
    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError):
        raise RuntimeError("Não foi possível carregar santoral.json da fonte litúrgica.") from None


def access_token():
    form = urllib.parse.urlencode({
        "client_id": required("BLOGGER_CLIENT_ID"),
        "client_secret": required("BLOGGER_CLIENT_SECRET"),
        "refresh_token": required("BLOGGER_REFRESH_TOKEN"),
        "grant_type": "refresh_token",
    }).encode()
    result = json_request("https://oauth2.googleapis.com/token", "POST", form,
                          content_type="application/x-www-form-urlencoded", operation="Autenticação OAuth")
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
    base = f"https://www.googleapis.com/blogger/v3/blogs/{blog_id}/posts/"
    posts = {}
    for status in ("live", "draft", "scheduled"):
        url = f"{base}?maxResults=500&fetchBodies=true&status={status}"
        while url:
            page = json_request(url, token=token, operation="Consulta de postagens")
            for post in page.get("items", []):
                posts[post.get("id") or (post.get("title"), post.get("url"))] = post
            page_token = page.get("nextPageToken")
            url = (f"{base}?maxResults=500&fetchBodies=true&status={status}"
                   f"&pageToken={urllib.parse.quote(page_token)}") if page_token else None
    return list(posts.values())


def week_entries(santoral, start):
    if not isinstance(santoral, list):
        raise RuntimeError("O formato de santoral.json não é uma lista.")
    by_date = {}
    for item in santoral:
        if not isinstance(item, dict):
            continue
        try:
            month, day = int(item["month"]), int(item["day"])
        except (KeyError, TypeError, ValueError):
            continue
        for year in (start.year, start.year + 1):
            try:
                date = dt.date(year, month, day)
            except ValueError:
                continue
            if start <= date <= start + dt.timedelta(days=6):
                by_date.setdefault(date, []).append(item)
    return [(date, item) for date in sorted(by_date) for item in by_date[date]]


def title_for(start):
    end = start + dt.timedelta(days=6)
    return f"A semana na Família Servita ({start:%d/%m} a {end:%d/%m})"


def source_marker(start):
    return f"somos-servos-weekly-origin:{start.isoformat()}"


def make_content(santoral, start, cards_dir):
    marker = source_marker(start)
    parts = [f"<!-- {marker} -->"]
    events = week_entries(santoral, start)
    if events:
        parts.append("<ul>")
        for date, item in events:
            name = item.get("title") or item.get("name") or ""
            if not name:
                continue
            label = f"{WEEKDAYS[date.weekday()]}, {date:%d/%m/%Y}"
            parts.append(f"<li><strong>{html.escape(label)}</strong> — {html.escape(str(name))}")
            card = Path(cards_dir) / f"cartao-{date:%m-%d}.png" if cards_dir else None
            if card and card.is_file():
                image_url = PAGES_URL + "cartoes/" + card.name
                parts.append(
                    '<br><img src="' + html.escape(image_url, quote=True) + '" alt="Cartão: '
                    + html.escape(str(name), quote=True)
                    + '" width="1080" height="1350" style="max-width:100%;height:auto">'
                )
            parts.append("</li>")
        parts.append("</ul>")
    parts.append("<p>No Sábado Mariano, a Família Servita honra de modo especial a Bem-aventurada Virgem Maria, recordando sua presença materna e confiando à sua intercessão as necessidades da Igreja e do mundo.</p>")
    parts.append(f'<p><a href="{APP_URL}">Hoje na Família Servita</a></p>')
    return "\n".join(parts)


def find_duplicate(posts, title, marker):
    normalized_title = title.strip().casefold()
    return next((post for post in posts
                 if (post.get("title") or "").strip().casefold() == normalized_title
                 or marker in (post.get("content") or "")), None)


def create_draft(title, content, marker, token, blog_id):
    payload = json.dumps({"kind": "blogger#post", "title": title, "content": content,
                          "labels": LABELS}, ensure_ascii=False).encode("utf-8")
    url = f"https://www.googleapis.com/blogger/v3/blogs/{blog_id}/posts/?isDraft=true"
    created = json_request(url, "POST", payload, token, "application/json; charset=UTF-8", "Criação do rascunho")
    post_id = created.get("id")
    if not post_id:
        raise RuntimeError("A API não devolveu o identificador do rascunho.")
    verified = json_request(
        f"https://www.googleapis.com/blogger/v3/blogs/{blog_id}/posts/{post_id}?view=ADMIN",
        token=token, operation="Verificação do rascunho")
    if verified.get("id") != post_id or verified.get("title") != title:
        raise RuntimeError("A leitura de volta não confirmou título e identificador.")
    if marker not in (verified.get("content") or ""):
        raise RuntimeError("A leitura de volta não confirmou o marcador de origem.")
    if str(verified.get("status", "")).upper() != "DRAFT":
        raise RuntimeError("A leitura de volta não confirmou o estado de rascunho.")
    print(f"Rascunho criado e confirmado pela API: {verified.get('title')} (ID {post_id})")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", help="Primeiro dia da semana (AAAA-MM-DD)")
    parser.add_argument("--santoral", help="Arquivo local para testes de prévia")
    parser.add_argument("--cards-dir", default="cartoes")
    args = parser.parse_args(argv)
    date_text = args.start_date or os.environ.get("WEEKLY_START_DATE", "").strip()
    start = dt.date.fromisoformat(date_text) if date_text else dt.datetime.now(TIMEZONE).date()
    santoral = load_santoral(args.santoral)
    title = title_for(start)
    content = make_content(santoral, start, args.cards_dir)
    dry_run = os.environ.get("WEEKLY_DRY_RUN", "false").strip().lower() == "true"
    if dry_run:
        print(f"Prévia semanal: {title}")
        print(f"Marcador: Semana servita")
        print("HTML:")
        print(content)
        return

    token = access_token()
    blog = locate_blog(token)
    duplicate = find_duplicate(list_existing_posts(blog["id"], token), title, source_marker(start))
    if duplicate:
        print(f"Já existe postagem correspondente (ID {duplicate.get('id')}); nenhuma duplicata criada.")
        return
    create_draft(title, content, source_marker(start), token, blog["id"])


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Falha: {exc}", file=sys.stderr)
        sys.exit(1)
