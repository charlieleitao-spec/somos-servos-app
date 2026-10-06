#!/usr/bin/env python3
"""Publica a celebração própria OSM do dia no Blogger, com deduplicação e leitura de volta."""
import datetime as dt
import hashlib
import html
import json
import os
import re
import sys
import subprocess
import tempfile
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

TOKEN_URL = "https://oauth2.googleapis.com/token"
BLOGS_URL = "https://www.googleapis.com/blogger/v3/users/self/blogs"
DATA_BASE = "https://raw.githubusercontent.com/charlieleitao-spec/liturgia-osm/main/www/data/"
TARGET_HOST = "somosservos.blogspot.com"
TIMEZONE = ZoneInfo("America/Sao_Paulo")
LABELS = ["Santos e Beatos"]


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
    base_url = f"https://www.googleapis.com/blogger/v3/blogs/{blog_id}/posts/"
    posts_by_id = {}
    for status in ("live", "draft", "scheduled"):
        url = f"{base_url}?maxResults=500&fetchBodies=true&status={status}"
        while url:
            page = json_request(url, token=token, operation="Consulta de postagens")
            for post in page.get("items", []):
                posts_by_id[post.get("id") or (post.get("title"), post.get("url"))] = post
            next_token = page.get("nextPageToken")
            url = (f"{base_url}?maxResults=500&fetchBodies=true&status={status}"
                   f"&pageToken={urllib.parse.quote(next_token)}") if next_token else None
    return list(posts_by_id.values())


def paragraph_html(text):
    text = str(text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return ""
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    return "\n".join(
        "<p>" + html.escape(part, quote=False).replace("\n", "<br>") + "</p>"
        for part in paragraphs
    )


def strip_section_title(title, text):
    original = str(text or "")
    first_line = re.match(r"^\s*([^\r\n]*)\r?\n", original)
    if first_line and first_line.group(1).strip() == str(title).strip():
        return original[first_line.end():]
    return original


def split_memorial_date_line(text):
    original = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    date_line = re.match(
        r"^(\*\s*[^†\r\n]*†[^\r\n]*?,\s*[A-Z]{2})([ \t]+)(?=[A-ZÀ-ÖØ-Þ])",
        original,
    )
    if not date_line:
        return None, original
    return date_line.group(1), original[date_line.end():]


def split_uppercase_heading(text):
    original = str(text or "").replace("\r\n", "\n").replace("\r", "\n").lstrip()
    tokens = list(re.finditer(r"\S+", original))
    heading_end = 0
    heading_words = 0
    for token in tokens:
        letters = [char for char in token.group() if char.isalpha()]
        if not letters or not all(char.isupper() for char in letters):
            break
        heading_end = token.end()
        heading_words += 1
    if heading_words < 2 or not original[heading_end:].strip():
        return None, original
    return original[:heading_end].strip(), original[heading_end:].lstrip()


def sections_from(celebration):
    if not isinstance(celebration, dict) or celebration.get("tipo_material") == "sem_material_proprio":
        return []
    hours = (celebration.get("material") or {}).get("horas")
    if not isinstance(hours, dict):
        return []

    sections = []
    for hour_key, hour in hours.items():
        if not isinstance(hour, dict):
            continue
        text = hour.get("texto")
        if isinstance(text, str) and text:
            sections.append({
                "title": hour.get("titulo") or ("Textos próprios" if hour_key == "textos_proprios" else hour_key),
                "text": text,
            })
            prayer = hour.get("oracao")
            if isinstance(prayer, str) and prayer:
                sections.append({"title": "Oração", "text": prayer})
            continue

        rubric = hour.get("rubrica")
        if isinstance(rubric, str) and rubric:
            sections.append({"title": hour.get("titulo") or "Textos próprios", "text": rubric})

        alternatives = hour.get("alternativas")
        if isinstance(alternatives, list):
            for alternative in alternatives:
                if not isinstance(alternative, dict):
                    continue
                text = alternative.get("texto")
                if isinstance(text, str) and text:
                    sections.append({
                        "title": alternative.get("titulo") or hour.get("titulo") or "Textos próprios",
                        "text": text,
                    })

        prayer = hour.get("oracao")
        if isinstance(prayer, str) and prayer:
            sections.append({"title": "Oração", "text": prayer})

    return sections


def celebration_for(offices, date):
    date_key = date.strftime("%m-%d")
    celebrations = offices.get("celebracoes") if isinstance(offices, dict) else None
    celebration = celebrations.get(date_key) if isinstance(celebrations, dict) else None
    if not isinstance(celebration, dict) or celebration.get("tipo_material") == "sem_material_proprio":
        return None
    return celebration


def make_content(entry, sections=None, card_url=None, card_alt=None):
    title = entry.get("title") or entry.get("name")
    source_id = str(entry.get("id"))
    date_text = entry.get("date") or ""
    date_line, bio_text = split_memorial_date_line(entry.get("bio", ""))
    bio_parts = []
    if date_line:
        bio_parts.append(paragraph_html(date_line))
    bio_parts.append(paragraph_html(bio_text))
    bio = "\n".join(part for part in bio_parts if part)

    prayer_title, prayer_text = split_uppercase_heading(entry.get("prayer", ""))
    prayer_heading = (f"<h4>{html.escape(prayer_title, quote=False)}</h4>\n"
                      if prayer_title else "")
    prayer = prayer_heading + paragraph_html(prayer_text)

    section_html = ""
    if sections:
        rendered = []
        for section in sections:
            section_title = section.get("title") or "Textos próprios"
            section_text = strip_section_title(section_title, section.get("text", ""))
            rendered.append(
                f"<h4>{html.escape(str(section_title), quote=False)}</h4>\n"
                f"{paragraph_html(section_text)}"
            )
        section_html = "<h3>Ofício próprio da Ordem</h3>\n" + "\n".join(rendered)
    card_html = ""
    if card_url:
        card_html = (
            '<figure style="margin:0 0 1.5em;text-align:center">'
            f'<img src="{html.escape(card_url, quote=True)}" '
            f'alt="{html.escape(card_alt or title, quote=True)}" '
            'width="1080" height="1350" style="max-width:100%;height:auto" />'
            '</figure>'
        )
    return (
        f"<!-- somos-servos-source-id:{html.escape(source_id)} -->"
        f"{card_html}"
        f"<p><strong>{html.escape(date_text)} · {html.escape(entry.get('rank', ''))}</strong></p>"
        f"<h2>{html.escape(title, quote=False)}</h2>"
        f"<h3>Memória</h3>{bio}"
        f"<h3>Oração</h3>{prayer}"
        f"{section_html}"
    )


def prepare_post(entry, offices, date, card_url=None, card_alt=None):
    celebration = celebration_for(offices, date)
    sections = sections_from(celebration)
    title = (f"{entry.get('title') or entry.get('name')} — Ofício próprio OSM"
             if sections else f"{entry.get('title') or entry.get('name')} — Memória OSM")
    return title, make_content(entry, sections, card_url, card_alt)


def find_duplicate(posts, source_marker):
    """Deduplica somente pelo identificador estável gravado no corpo do post."""
    return next((post for post in posts
                 if source_marker in (post.get("content") or "")), None)


def entry_for_date(santoral, date):
    entries = [item for item in santoral
               if int(item.get("day", 0)) == date.day and int(item.get("month", 0)) == date.month]
    if len(entries) > 1:
        raise RuntimeError(f"Há mais de uma celebração própria cadastrada para {date.isoformat()}; revisão necessária.")
    return entries[0] if entries else None


def generate_card(santoral, date):
    generator = Path(__file__).with_name("gerar-cartao.py")
    if not generator.is_file():
        raise RuntimeError("O gerador gerar-cartao.py não está disponível no repositório.")

    output_dir = Path(__file__).with_name("cartoes")
    output_dir.mkdir(parents=True, exist_ok=True)
    key = date.strftime("%m-%d")
    with tempfile.TemporaryDirectory(prefix="somos-servos-santoral-") as temp_dir:
        data_dir = Path(temp_dir)
        with (data_dir / "santoral.json").open("w", encoding="utf-8") as data_file:
            json.dump(santoral, data_file, ensure_ascii=False)
        result = subprocess.run(
            [sys.executable, str(generator), key, "--dir", str(data_dir), "--out", str(output_dir)],
            check=False, capture_output=True, text=True,
        )
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.returncode != 0:
        detail = result.stderr.strip()
        raise RuntimeError("Não foi possível gerar o cartão." + (f" {detail}" if detail else ""))

    png_path = output_dir / f"cartao-{key}.png"
    caption_path = output_dir / f"cartao-{key}.txt"
    if not png_path.is_file() or not caption_path.is_file():
        raise RuntimeError("O gerador não produziu o PNG e a legenda esperados.")
    return png_path, caption_path


def set_github_env(name, value):
    github_env = os.environ.get("GITHUB_ENV")
    if github_env:
        with open(github_env, "a", encoding="utf-8") as env_file:
            env_file.write(f"{name}={value}\n")


def main():
    requested_date = os.environ.get("PUBLISH_DATE", "").strip()
    date = dt.date.fromisoformat(requested_date) if requested_date else dt.datetime.now(TIMEZONE).date()
    dry_run = os.environ.get("DRY_RUN", "false").strip().lower() == "true"

    santoral = get_public_json("santoral.json")
    offices = get_public_json("oficios-osm.json")
    entry = entry_for_date(santoral, date)
    if not entry:
        print(f"Sem celebração própria cadastrada para {date.isoformat()}; nenhuma postagem criada.")
        return

    png_path, caption_path = generate_card(santoral, date)
    card_version = hashlib.sha256(png_path.read_bytes()).hexdigest()[:16]
    card_url = (
        "https://charlieleitao-spec.github.io/somos-servos-app/"
        f"cartoes/{png_path.name}?v={urllib.parse.quote(card_version)}"
    )
    card_alt = f"Cartão: {entry.get('title') or entry.get('name')} — {entry.get('date', date.isoformat())}"
    title, content = prepare_post(entry, offices, date, card_url, card_alt)
    celebration = celebration_for(offices, date)
    labels = LABELS + (["Ofícios"] if sections_from(celebration) else [])
    is_draft = os.environ.get("DRAFT", "false").strip().lower() == "true"
    token = access_token()
    blog = locate_blog(token)
    posts = list_existing_posts(blog["id"], token)
    source_marker = f"somos-servos-source-id:{entry.get('id')}"
    duplicate = find_duplicate(posts, source_marker)
    if duplicate:
        existing_content = duplicate.get("content") or ""
        card_path = f"cartoes/{png_path.name}"
        if card_path in existing_content:
            set_github_env("CARD_COMMIT", "true")
            set_github_env("CARD_PUBLIC_URL", card_url)
            print(f"Já existe postagem correspondente (ID {duplicate.get('id')}); o cartão será garantido no Pages.")
        else:
            print(f"Já existe postagem correspondente (ID {duplicate.get('id')}); nenhuma duplicata criada.")
        return

    if dry_run:
        print(f"Prévia sem publicação: {title}")
        print(f"Marcadores: {', '.join(labels)}")
        print(f"Conteúdo preparado; tamanho {len(content)} caracteres.")
        print(f"PNG da prévia: {png_path}")
        print("Legenda do cartão:")
        print(caption_path.read_text(encoding="utf-8").strip())
        return

    payload = json.dumps({"kind": "blogger#post", "title": title, "content": content,
                          "labels": labels}, ensure_ascii=False).encode("utf-8")
    insert_url = f"https://www.googleapis.com/blogger/v3/blogs/{blog['id']}/posts/"
    if is_draft:
        insert_url += "?isDraft=true"
    created = json_request(
        insert_url, "POST", payload, token, "application/json; charset=UTF-8", "Criação da postagem")
    post_id = created.get("id")
    if not post_id:
        raise RuntimeError("A API não devolveu o identificador da postagem criada.")

    verified = json_request(
        f"https://www.googleapis.com/blogger/v3/blogs/{blog['id']}/posts/{post_id}?view=ADMIN",
        token=token, operation="Verificação da postagem")
    if verified.get("id") != post_id or verified.get("title") != title:
        raise RuntimeError("A leitura de volta da API não confirmou título e identificador.")
    if source_marker not in (verified.get("content") or ""):
        raise RuntimeError("A leitura de volta da API não confirmou o marcador de origem.")
    if is_draft and str(verified.get("status", "")).upper() != "DRAFT":
        raise RuntimeError("A leitura de volta da API não confirmou o estado de rascunho.")
    result_label = "Rascunho criado e confirmado" if is_draft else "Publicado e confirmado"
    set_github_env("CARD_COMMIT", "true")
    set_github_env("CARD_PUBLIC_URL", card_url)
    print(f"{result_label} pela API: {verified.get('title')}")
    print(f"Cartão e legenda preparados: {png_path.name}, {caption_path.name}")
    print(f"URL: {verified.get('url')}")
    print(f"ID da postagem confirmado: {post_id}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Falha: {exc}", file=sys.stderr)
        sys.exit(1)

