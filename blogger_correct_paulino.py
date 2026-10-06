#!/usr/bin/env python3
"""Corrige a grafia de Frei Paulino no Blogger; não altera datas nem status."""
from __future__ import annotations

import argparse
import json
import os
import re
import unicodedata
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Comment
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

DRY_RUN = True
SCOPE = "https://www.googleapis.com/auth/blogger"
TOKEN_URI = "https://oauth2.googleapis.com/token"
SKIP_URLS = {
    "https://somosservos.blogspot.com/2010/03/sonho-de-padre-paolino-reserva-do-medio.html"
}
PRAYER_HEADING = "ORAÇÃO PELA BEATIFICAÇÃO E CANONIZAÇÃO"
BACKUP_DIR = Path("backups/paulino")
REPORT_PATH = Path("paulino-correction-report.json")


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Variável obrigatória ausente: {name}")
    return value


def service():
    credentials = Credentials(
        token=None,
        refresh_token=required("BLOGGER_REFRESH_TOKEN"),
        token_uri=TOKEN_URI,
        client_id=required("BLOGGER_CLIENT_ID"),
        client_secret=required("BLOGGER_CLIENT_SECRET"),
        scopes=[SCOPE],
    )
    return build("blogger", "v3", credentials=credentials, cache_discovery=False)


def locate_blog(api) -> str:
    configured = os.environ.get("BLOGGER_BLOG_ID", "").strip()
    if configured:
        return configured
    blogs = api.blogs().listByUser(userId="self").execute().get("items", [])
    matches = [b for b in blogs if "somosservos.blogspot.com" in (b.get("url") or "").lower()]
    if len(matches) != 1:
        raise RuntimeError(f"Esperava um blog Somos Servos; encontrei {len(matches)}.")
    return str(matches[0]["id"])


def list_posts(api, blog_id: str) -> list[dict]:
    found: dict[str, dict] = {}
    for status in ("LIVE", "DRAFT", "SCHEDULED"):
        token = None
        while True:
            args = {"blogId": blog_id, "status": status, "fetchBodies": True,
                    "view": "ADMIN", "maxResults": 500}
            if token:
                args["pageToken"] = token
            page = api.posts().list(**args).execute()
            for item in page.get("items", []):
                found[str(item["id"])] = item
            token = page.get("nextPageToken")
            if not token:
                break
    return list(found.values())


def list_pages(api, blog_id: str) -> list[dict]:
    found: dict[str, dict] = {}
    token = None
    while True:
        args = {"blogId": blog_id, "fetchBodies": True, "view": "ADMIN", "maxResults": 500}
        if token:
            args["pageToken"] = token
        page = api.pages().list(**args).execute()
        for item in page.get("items", []):
            found[str(item["id"])] = item
        token = page.get("nextPageToken")
        if not token:
            break
    return list(found.values())


def preserve_case(word: str, replacement: str) -> str:
    if word.isupper():
        return replacement.upper()
    if word[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def replace_name(text: str) -> tuple[str, int]:
    count = 0
    def paolino(match):
        nonlocal count
        count += 1
        return preserve_case(match.group(0), "Paulino")
    text = re.sub(r"paolino", paolino, text, flags=re.IGNORECASE)
    def baldassari(match):
        nonlocal count
        count += 1
        return preserve_case(match.group(0), "Baldassarri")
    text = re.sub(r"baldassari(?!r)", baldassari, text, flags=re.IGNORECASE)
    return text, count


def protected_prayer_nodes(soup: BeautifulSoup) -> set:
    """Preserva o bloco da oração aprovada, quando estiver identificado no HTML."""
    protected = set()
    marker = re.sub(r"\s+", " ", PRAYER_HEADING).casefold()
    for node in soup.find_all(string=True):
        if isinstance(node, Comment):
            continue
        plain = re.sub(r"\s+", " ", str(node)).strip().casefold()
        if marker not in plain:
            continue
        block = node.find_parent(["p", "div", "section", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6"])
        if block is None:
            block = node.parent
        protected.update(block.find_all(string=True))
        sibling = block.find_next_sibling() if block else None
        if sibling and getattr(sibling, "name", None) not in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            protected.update(sibling.find_all(string=True))
    return protected


def change_content(content: str) -> tuple[str, int]:
    soup = BeautifulSoup(content or "", "html.parser")
    protected = protected_prayer_nodes(soup)
    count = 0
    for node in list(soup.find_all(string=True)):
        if isinstance(node, Comment) or node in protected:
            continue
        if node.parent and node.parent.name in {"script", "style"}:
            continue
        updated, hits = replace_name(str(node))
        if hits:
            node.replace_with(NavigableString(updated))
            count += hits
    return soup.decode(formatter="minimal"), count


def process_item(api, blog_id: str, kind: str, item: dict, apply: bool) -> dict | None:
    url = item.get("url", "")
    if kind == "post" and url.rstrip("/").lower() in {u.rstrip("/").lower() for u in SKIP_URLS}:
        return None
    title_before = item.get("title") or ""
    title_after, title_hits = replace_name(title_before)
    content_before = item.get("content") or ""
    content_after, content_hits = change_content(content_before)
    total = title_hits + content_hits
    if not total:
        return None
    record = {
        "type": kind, "id": str(item["id"]), "url": url,
        "title_before": title_before, "title_after": title_after,
        "title_occurrences": title_hits, "body_occurrences": content_hits,
        "content_before": content_before, "content_after": content_after,
        "updated": False,
    }
    if apply:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        backup = BACKUP_DIR / f"{stamp}-{kind}-{item['id']}.json"
        backup.write_text(json.dumps(item, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        record["backup"] = str(backup)
        body = {"title": title_after, "content": content_after}
        if kind == "post":
            api.posts().patch(blogId=blog_id, postId=str(item["id"]), body=body).execute()
            verify = api.posts().get(blogId=blog_id, postId=str(item["id"]), view="ADMIN").execute()
        else:
            api.pages().patch(blogId=blog_id, pageId=str(item["id"]), body=body).execute()
            verify = api.pages().get(blogId=blog_id, pageId=str(item["id"]), view="ADMIN").execute()
        if verify.get("title", "") != title_after or verify.get("content", "") != content_after:
            raise RuntimeError(f"A leitura de verificação divergiu para {kind} {item['id']}.")
        record["updated"] = True
    return record


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-apply", action="store_true")
    args = parser.parse_args()
    apply = args.apply and args.confirm_apply
    if args.apply and not args.confirm_apply:
        raise SystemExit("Para gravar, use --apply --confirm-apply.")
    if apply and DRY_RUN:
        # DRY_RUN remains the safe default; both explicit flags opt into writes.
        pass

    api = service()
    blog_id = locate_blog(api)
    posts = list_posts(api, blog_id)
    pages = list_pages(api, blog_id)
    all_items = [("post", x) for x in posts] + [("page", x) for x in pages]
    changes = []
    for kind, item in all_items:
        record = process_item(api, blog_id, kind, item, apply)
        if record:
            changes.append(record)
            print(f"{kind.upper()} | {item.get('title') or '(sem título)'} | {item.get('url','')} | título={record['title_occurrences']} corpo={record['body_occurrences']} | {'APLICADO' if apply else 'SIMULAÇÃO'}")

    REPORT_PATH.write_text(json.dumps({
        "mode": "apply" if apply else "dry-run",
        "blog_id": blog_id,
        "posts_scanned": len(posts),
        "pages_scanned": len(pages),
        "changed_items": len(changes),
        "changes": changes,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Resumo: {len(changes)} itens com ocorrências; modo={'aplicado' if apply else 'simulação'}. Relatório: {REPORT_PATH}")


if __name__ == "__main__":
    main()
