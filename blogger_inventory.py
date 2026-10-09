#!/usr/bin/env python3
"""Inventário somente de leitura de posts e páginas do Blogger em CSV."""
import argparse
import csv
import html
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

TOKEN_URL = "https://oauth2.googleapis.com/token"
BLOGS_URL = "https://www.googleapis.com/blogger/v3/users/self/blogs"
API_BASE = "https://www.googleapis.com/blogger/v3"
TARGET_HOST = "somosservos.blogspot.com"
SHORT_POST_CHARS = 500
YOUTUBE_RE = re.compile(r"(?:youtube(?:-nocookie)?\.com|youtu\.be)", re.IGNORECASE)
VIDEO_HOST_RE = re.compile(r"(?:youtube(?:-nocookie)?\.com|youtu\.be|vimeo\.com)", re.IGNORECASE)
VIDEO_FILE_RE = re.compile(r"\.(?:mp4|m4v|mov|webm|ogv|avi|mpeg|mpg)(?:$|[?#])", re.IGNORECASE)
PDF_RE = re.compile(r"\.pdf(?:$|[?#])", re.IGNORECASE)
ATTACHMENT_RE = re.compile(
    r"\.(?:pdf|doc|docx|odt|rtf|xls|xlsx|ods|ppt|pptx|odp|txt|csv|zip|rar|7z|epub|ics)(?:$|[?#])",
    re.IGNORECASE,
)


class BodyParser(HTMLParser):
    """Extrai texto visível e conta links, imagens e mídias incorporadas."""
    HIDDEN = {"script", "style", "noscript", "template"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden_depth = 0
        self.parts = []
        self.links = 0
        self.images = 0
        self.iframes = 0
        self.embed_objects = 0
        self.youtube_embeds = 0
        self.pdf_embeds = 0
        self.video_present = False
        self.attachment_present = False

    def handle_starttag(self, tag, attrs):
        attributes = {key.lower(): (value or "") for key, value in attrs}
        if tag in self.HIDDEN:
            self.hidden_depth += 1
        if tag == "a":
            self.links += 1
        elif tag == "img":
            self.images += 1
        elif tag == "iframe":
            self.iframes += 1
        elif tag in {"embed", "object"}:
            self.embed_objects += 1

        references = " ".join(
            attributes.get(key, "") for key in ("href", "src", "data", "poster")
        )
        embed_tag = tag in {"iframe", "embed", "object"}
        if embed_tag and YOUTUBE_RE.search(references):
            self.youtube_embeds += 1
        if embed_tag and (
            PDF_RE.search(references)
            or attributes.get("type", "").lower().split(";")[0].strip() == "application/pdf"
        ):
            self.pdf_embeds += 1

        media_reference = VIDEO_HOST_RE.search(references) or VIDEO_FILE_RE.search(references)
        if tag == "video" or media_reference:
            self.video_present = True
        if tag == "source" and attributes.get("type", "").lower().startswith("video/"):
            self.video_present = True

        if (
            "download" in attributes
            or ATTACHMENT_RE.search(references)
            or re.search(r"(?:drive|docs)\.google\.com/(?:file/|uc\?|document/)", references, re.IGNORECASE)
        ):
            self.attachment_present = True

    def handle_endtag(self, tag):
        if tag in self.HIDDEN and self.hidden_depth:
            self.hidden_depth -= 1

    def handle_data(self, data):
        if not self.hidden_depth:
            self.parts.append(data)

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
    except urllib.error.URLError:
        raise RuntimeError(f"Falha de conexão durante {operation}.") from None


def access_token():
    form = urllib.parse.urlencode({
        "client_id": required("BLOGGER_CLIENT_ID"),
        "client_secret": required("BLOGGER_CLIENT_SECRET"),
        "refresh_token": required("BLOGGER_REFRESH_TOKEN"),
        "grant_type": "refresh_token",
    }).encode()
    result = json_request(TOKEN_URL, "POST", form,
                         content_type="application/x-www-form-urlencoded",
                         operation="Autenticação OAuth")
    token = result.get("access_token")
    if not token:
        raise RuntimeError("Autenticação OAuth não devolveu token de acesso.")
    return token


def locate_blog(token):
    requested_id = os.environ.get("BLOGGER_BLOG_ID", "").strip()
    if requested_id:
        return requested_id
    blogs = json_request(BLOGS_URL, token=token, operation="Consulta de blogs").get("items", [])
    blog = next((item for item in blogs
                 if TARGET_HOST in (item.get("url") or "").lower()), None)
    if not blog:
        raise RuntimeError("O blog Somos Servos não foi localizado na conta autorizada.")
    return str(blog["id"])


def list_resources(blog_id, token, kind, statuses):
    endpoint = "posts" if kind == "post" else "pages"
    base_url = f"{API_BASE}/blogs/{urllib.parse.quote(blog_id, safe='')}/{endpoint}"
    found = {}
    for status in statuses:
        page_token = None
        while True:
            params = {"fetchBodies": "true", "status": status, "view": "ADMIN"}
            params["maxResults"] = "500" if endpoint == "posts" else "100"
            if page_token:
                params["pageToken"] = page_token
            url = base_url + "?" + urllib.parse.urlencode(params)
            page = json_request(url, token=token,
                                operation=f"Listagem de {kind}s ({status})")
            for item in page.get("items", []):
                key = str(item.get("id") or item.get("url") or item.get("title"))
                found[key] = item
            page_token = page.get("nextPageToken")
            if not page_token:
                break
    return list(found.values())


def body_stats(content):
    parser = BodyParser()
    parser.feed(content or "")
    parser.close()
    visible_text = re.sub(r"\s+", " ", " ".join(parser.parts)).strip()
    embedded_count = parser.iframes + parser.embed_objects
    body_empty = not (
        visible_text or parser.links or parser.images or embedded_count
        or parser.video_present or parser.attachment_present
    )
    return {
        "visible_text": visible_text,
        "links": parser.links,
        "images": parser.images,
        "iframes": parser.iframes,
        "embed_objects": parser.embed_objects,
        "embedded_total": embedded_count,
        "youtube_embeds": parser.youtube_embeds,
        "pdf_embeds": parser.pdf_embeds,
        "video_present": parser.video_present,
        "attachment_present": parser.attachment_present,
        "body_empty": body_empty,
    }

def title_key(title):
    return re.sub(r"\s+", " ", (title or "").strip()).casefold()


def build_rows(posts, pages):
    entries = [("post", item) for item in posts] + [("página", item) for item in pages]
    title_counts = {}
    for _, item in entries:
        key = title_key(item.get("title", ""))
        if key:
            title_counts[key] = title_counts.get(key, 0) + 1

    rows = []
    for kind, item in entries:
        stats = body_stats(item.get("content") or "")
        visible_text = stats["visible_text"]
        chars = len(visible_text)
        title = item.get("title") or ""
        labels = item.get("labels") or []
        if not isinstance(labels, list):
            labels = [str(labels)]
        flags = []
        if stats["body_empty"]:
            flags.append("corpo vazio")
        if re.search(r"\bconferir\b", visible_text, flags=re.IGNORECASE) and stats["links"] == 0:
            flags.append("texto 'conferir' sem link")
        if not title.strip():
            flags.append("título vazio")
        if title and title_counts.get(title_key(title), 0) > 1:
            flags.append("título duplicado")
        if kind == "post" and chars <= SHORT_POST_CHARS:
            flags.append(f"post muito curto (≤{SHORT_POST_CHARS} caracteres)")
        rows.append({
            "tipo": kind,
            "título": title,
            "URL": item.get("url", ""),
            "data": item.get("published") or item.get("updated") or item.get("created") or "",
            "marcadores atuais": " | ".join(str(label) for label in labels),
            "número de caracteres": chars,
            "corpo vazio": "sim" if stats["body_empty"] else "não",
            "número de links": stats["links"],
            "número de imagens": stats["images"],
            "número de iframes/embeds": stats["embedded_total"],
            "número de iframes": stats["iframes"],
            "número de embeds/objetos": stats["embed_objects"],
            "número de embeds YouTube": stats["youtube_embeds"],
            "número de embeds PDF": stats["pdf_embeds"],
            "vídeo presente": "sim" if stats["video_present"] else "não",
            "arquivo anexo presente": "sim" if stats["attachment_present"] else "não",
            "título vazio": "sim" if not title.strip() else "não",
            "suspeitas": " | ".join(flags),
        })
    return rows

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="inventario-somos-servos.csv",
                        help="caminho do CSV de saída")
    args = parser.parse_args()

    token = access_token()
    blog_id = locate_blog(token)
    posts = list_resources(blog_id, token, "post", ("live", "draft", "scheduled"))
    pages = list_resources(blog_id, token, "página", ("live", "draft"))
    rows = build_rows(posts, pages)
    fields = ["tipo", "título", "URL", "data", "marcadores atuais",
              "número de caracteres", "corpo vazio", "número de links",
              "número de imagens", "número de iframes/embeds", "número de iframes",
              "número de embeds/objetos", "número de embeds YouTube", "número de embeds PDF",
              "vídeo presente", "arquivo anexo presente", "título vazio", "suspeitas"]
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"Inventário somente de leitura concluído: {len(posts)} posts, "
          f"{len(pages)} páginas; {len(rows)} linhas em {output}.")
    print(f"Critério de post muito curto: até {SHORT_POST_CHARS} caracteres de texto visível.")
    print("Nenhum post ou página foi criado, editado, publicado ou apagado.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Falha: {exc}", file=sys.stderr)
        sys.exit(1)
