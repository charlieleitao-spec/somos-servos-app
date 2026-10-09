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


def audit_live_pages(pages: list[dict], posts: list[dict]) -> None:
    """Audita grafias nas páginas publicadas e localiza a oração aprovada."""
    patterns = [
        ("Paolino", re.compile(r"paolino", re.IGNORECASE)),
        ("Baldassari", re.compile(r"baldassari(?!r)", re.IGNORECASE)),
        ("Paulino Maria", re.compile(r"\bpaulino\s+maria\b", re.IGNORECASE)),
    ]
    live_pages = [page for page in pages
                  if str(page.get("status") or "LIVE").upper() == "LIVE"]
    matches = []
    prayer_items = []
    prayer_candidates = []

    for page in live_pages:
        title = page.get("title") or "(sem título)"
        url = page.get("url") or ""
        date = page.get("published") or page.get("updated") or page.get("created") or ""
        soup = BeautifulSoup(page.get("content") or "", "html.parser")
        protected = protected_prayer_nodes(soup)
        sources = [("título", title, False)]
        for node in soup.find_all(string=True):
            if isinstance(node, Comment) or (node.parent and node.parent.name in {"script", "style"}):
                continue
            text = re.sub(r"\s+", " ", str(node)).strip()
            if text:
                sources.append(("oração aprovada" if node in protected else "conteúdo",
                                text, node in protected))
        for location, text, is_prayer in sources:
            for form, pattern in patterns:
                for match in pattern.finditer(text):
                    start = max(0, match.start() - 70)
                    end = min(len(text), match.end() + 70)
                    matches.append((title, date, url, form, location, text[start:end], is_prayer))

    outside_matches = [row for row in matches if not row[6]]
    print(f"Auditoria de grafia: {len(live_pages)} páginas LIVE verificadas.")
    print("Ocorrências: forma | página | data | localização | trecho")
    if not outside_matches:
        print("Nenhuma ocorrência das formas solicitadas fora da oração aprovada.")
    for title, date, url, form, location, excerpt, is_prayer in matches:
        marker = " — preservar" if is_prayer else ""
        print(f"- {form} | {title} | {date} | {location}{marker} | …{excerpt}… | {url}")

    for kind, items in (("página", pages), ("post", posts)):
        for item in items:
            soup = BeautifulSoup(item.get("content") or "", "html.parser")
            visible = re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).casefold()
            title = item.get("title") or "(sem título)"
            date = item.get("published") or item.get("updated") or item.get("created") or ""
            status = str(item.get("status") or "LIVE").upper()
            url = item.get("url") or ""
            if PRAYER_HEADING.casefold() in visible:
                prayer_items.append((kind, title, date, status, url))
            elif ("oraç" in visible or "orac" in visible) and any(
                    term in visible for term in ("paulino", "paolino", "baldassari", "beatificação", "canonização")):
                excerpt = next((visible[max(0, m.start()-80):m.end()+160]
                                for pattern in (r"oraç\w*", r"orac\w*")
                                for m in re.finditer(pattern, visible)), visible[:220])
                prayer_candidates.append((kind, title, date, status, excerpt, url))

    print("Oração aprovada (localização em páginas e posts):")
    if prayer_items:
        for kind, title, date, status, url in prayer_items:
            print(f"- {kind} | {title} | {date} | {status} | {PRAYER_HEADING} | {url}")
    else:
        print("- Cabeçalho exato da oração aprovada não encontrado nas páginas nem nos posts consultados.")
        if prayer_candidates:
            print("Referências de oração ligadas a Frei Paulino para conferência:")
            for kind, title, date, status, excerpt, url in prayer_candidates:
                print(f"- {kind} | {title} | {date} | {status} | …{excerpt}… | {url}")
        else:
            print("- Nenhum bloco com oração e referência a Frei Paulino foi localizado.")


def audit_live_posts(posts: list[dict]) -> int:
    """Conta e busca somente nos posts LIVE, sem gravar no Blogger."""
    patterns = [
        ("Paolino", re.compile(r"paolino", re.IGNORECASE)),
        ("Baldassari (um r)", re.compile(r"baldassari(?!r)", re.IGNORECASE)),
        ("Paulino Maria", re.compile(r"\bpaulino\s+maria\b", re.IGNORECASE)),
    ]
    live_posts = [post for post in posts
                  if str(post.get("status") or "").upper() == "LIVE"]
    matches = []
    prayer_locations = set()
    for post in live_posts:
        title = post.get("title") or "(sem título)"
        url = post.get("url") or ""
        soup = BeautifulSoup(post.get("content") or "", "html.parser")
        protected = protected_prayer_nodes(soup)
        sources = [("título", title, False)]
        for node in soup.find_all(string=True):
            if isinstance(node, Comment) or (node.parent and node.parent.name in {"script", "style"}):
                continue
            text = re.sub(r"\s+", " ", str(node)).strip()
            if text:
                sources.append(("oração aprovada" if node in protected else "conteúdo",
                                text, node in protected))
        for location, text, is_prayer in sources:
            for form, pattern in patterns:
                if pattern.search(text):
                    matches.append((form, title, url, location, is_prayer))
                    if is_prayer:
                        prayer_locations.add((title, url))
    print(f"Posts LIVE verificados: {len(live_posts)}.")
    print("Ocorrências fora da oração aprovada (forma | título | URL):")
    outside = [item for item in matches if not item[4]]
    if outside:
        for form, title, url, _, _ in outside:
            print(f"- {form} | {title} | {url}")
    else:
        print("Nenhuma.")
    if prayer_locations:
        print("Oração aprovada preservada; ocorrência encontrada em:")
        for title, url in sorted(prayer_locations):
            print(f"- {title} | {url}")
    return len(live_posts)


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
    live_count = audit_live_posts(posts)
    REPORT_PATH.write_text(json.dumps({
        "mode": "dry-run",
        "posts_live_scanned": live_count,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Modo=simulação; nenhuma alteração enviada ao Blogger.")
    return

    pages = list_pages(api, blog_id)
    audit_live_pages(pages, posts)
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
