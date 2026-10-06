#!/usr/bin/env python3
"""
Plano de correção de posts do Somos Servos via Blogger API v3.

Padrão seguro: DRY_RUN = True. Para gravar:
  python corrigir_posts_somos_servos.py --apply --confirm-apply

Dependências:
  python -m pip install google-api-python-client google-auth beautifulsoup4

Variáveis de ambiente obrigatórias:
  BLOGGER_CLIENT_ID
  BLOGGER_CLIENT_SECRET
  BLOGGER_REFRESH_TOKEN

BLOGGER_BLOG_ID é opcional; sem ele, o script localiza o blog autorizado
por BLOGGER_PUBLIC_URL (padrão: https://somosservos.blogspot.com).

O script nunca apaga posts. Para posts live/agendados, usa posts.revert,
o endpoint oficial que os torna rascunhos. Só altera o campo content nos
posts em que precisa limpar links ou remover o vídeo. Título e data são
preservados.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from bs4 import BeautifulSoup, NavigableString
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


# Trava principal: o padrão é simular e não gravar no Blogger.
DRY_RUN = True

BLOGGER_SCOPE = "https://www.googleapis.com/auth/blogger"
TOKEN_URI = "https://oauth2.googleapis.com/token"

PROVINCE_TITLE = "A criação da Província e a década de 1960"
PDF_EMPTY_TITLE = "Tejer historias_comunicar esperanza(1).pdf"
MOTHER_VIDEO_TITLE = "EU AMO A MINHA MÃE"
MOTHER_VIDEO_ID = "bCqlwnSIV3U"

# URLs confirmadas como 404 na auditoria. Mantemos as variantes exatas para
# não retirar links parecidos que não foram verificados.
BROKEN_LINKS = {
    "https://paroquiasenhoradahora.pt/index.php/component/k2/item/2244-liturgia-e-homilia-na-quarta-feira-de-cinzas-2025",
    "https://www.rs21.com.br/wp-content/themes/rs21_2/images/wallpaper/celular_wallpaper3b.jpg",
    "http://www.fao.org/wsfs/forum2050/wsfs-forum/en/",
    "http://www.fao.org/wsfs/forum2050/wsfs-forum/es/",
    "http://picasaweb.google.com.br/frcharlieosm/LancamentoLivro14Agosto2009?feat=embedwebsite",
    "https://online.flippingbook.com/view/544907/12/",
}
INVALID_HREF_MARKERS = ("/null", "/goog_1811811076")


def env_required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Variável de ambiente obrigatória ausente: {name}")
    return value


def make_service():
    credentials = Credentials(
        token=None,
        refresh_token=env_required("BLOGGER_REFRESH_TOKEN"),
        token_uri=TOKEN_URI,
        client_id=env_required("BLOGGER_CLIENT_ID"),
        client_secret=env_required("BLOGGER_CLIENT_SECRET"),
        scopes=[BLOGGER_SCOPE],
    )
    return build(
        "blogger",
        "v3",
        credentials=credentials,
        cache_discovery=False,
    )


def locate_blog_id(service) -> str:
    """Usa o ID configurado ou localiza Somos Servos na conta OAuth autorizada."""
    requested_id = os.environ.get("BLOGGER_BLOG_ID", "").strip()
    if requested_id:
        return requested_id

    target_host = (urlsplit(
        os.environ.get("BLOGGER_PUBLIC_URL", "https://somosservos.blogspot.com")
    ).hostname or "").casefold()
    blogs = service.blogs().listByUser(userId="self").execute().get("items", [])
    matches = [
        blog for blog in blogs
        if (urlsplit(blog.get("url", "")).hostname or "").casefold() == target_host
    ]
    if len(matches) != 1:
        raise RuntimeError(
            "Esperava localizar exatamente um blog Somos Servos na conta OAuth; "
            f"encontrei {len(matches)}. Configure BLOGGER_BLOG_ID para especificá-lo."
        )
    return str(matches[0]["id"])


def list_all_posts(service, blog_id: str) -> list[dict]:
    """Lê posts live, draft e scheduled com corpo completo e view ADMIN."""
    posts: dict[str, dict] = {}
    for status in ("live", "draft", "scheduled"):
        page_token = None
        while True:
            params = {
                "blogId": blog_id,
                "status": status,
                "fetchBodies": True,
                "view": "ADMIN",
                "maxResults": 500,
            }
            if page_token:
                params["pageToken"] = page_token
            page = service.posts().list(**params).execute()
            for post in page.get("items", []):
                post_id = str(post.get("id", ""))
                if post_id:
                    post["_listed_status"] = status
                    posts[post_id] = post
            page_token = page.get("nextPageToken")
            if not page_token:
                break
    return list(posts.values())


def normalized_title(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", (value or "").strip().casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text)


def normalized_href(href: str) -> str:
    return href.strip().replace("&amp;", "&")


def has_invalid_blogger_href(href: str) -> bool:
    path = urlsplit(normalized_href(href)).path.casefold()
    return any(marker in path for marker in INVALID_HREF_MARKERS)


def parse_html(content: str) -> BeautifulSoup:
    return BeautifulSoup(content or "", "html.parser")


def body_hash(content: str) -> str:
    return hashlib.sha256((content or "").encode("utf-8")).hexdigest()


def image_only_homepage_candidate(post: dict) -> bool:
    """Confirma título vazio, URL raiz e corpo composto só por uma imagem."""
    if (post.get("title") or "").strip():
        return False
    url = (post.get("url") or "").rstrip("/")
    blog_id = os.environ.get("BLOGGER_PUBLIC_URL", "https://somosservos.blogspot.com").rstrip("/")
    if url != blog_id:
        return False

    soup = parse_html(post.get("content", ""))
    if soup.get_text(" ", strip=True):
        return False
    if len(soup.find_all("img")) != 1:
        return False
    if soup.find(["iframe", "video", "object", "embed", "audio"]):
        return False
    # A imagem pode estar dentro de um link que abre a própria imagem.
    return True


def current_status(post: dict) -> str:
    status = (post.get("status") or post.get("_listed_status") or "").upper()
    if status not in {"LIVE", "DRAFT", "SCHEDULED"}:
        raise RuntimeError(
            f"Status não reconhecido para post {post.get('id')}: {status or '(ausente)'}"
        )
    return status


def add_action(actions: dict[str, dict], post: dict) -> dict:
    post_id = str(post["id"])
    if post_id not in actions:
        actions[post_id] = {
            "post": post,
            "draft_reasons": [],
            "content_reasons": [],
            "new_content": post.get("content") or "",
            "changes": [],
        }
    return actions[post_id]


def plain_text_or_unwrap(anchor) -> None:
    """
    Remove a ligação sem perder o conteúdo visível.
    Texto simples vira texto; âncoras com imagem preservam a imagem e o alt.
    """
    if anchor.find("img"):
        anchor.unwrap()
        return
    visible = anchor.get_text("", strip=False)
    anchor.replace_with(NavigableString(visible))


def clean_broken_links(content: str) -> tuple[str, list[str]]:
    soup = parse_html(content)
    changed = []
    # Copiamos a lista porque a substituição altera a árvore.
    for anchor in list(soup.find_all("a", href=True)):
        href = normalized_href(anchor.get("href", ""))
        if href in BROKEN_LINKS:
            plain_text_or_unwrap(anchor)
            changed.append(f"link 404 convertido em texto: {href}")
        elif has_invalid_blogger_href(href):
            # A diretriz específica pede manter a tag e seu texto interno.
            del anchor["href"]
            changed.append(f"atributo href inválido removido: {href}")
    return str(soup), changed


def remove_unavailable_mother_video(content: str, title: str) -> tuple[str, list[str]]:
    if not normalized_title(title).startswith(normalized_title(MOTHER_VIDEO_TITLE)):
        return content, []

    soup = parse_html(content)
    removed = []
    for frame in list(soup.find_all("iframe")):
        src = frame.get("src", "")
        host = (urlsplit(src).hostname or "").casefold()
        if MOTHER_VIDEO_ID in src and (
            host.endswith("youtube.com") or host.endswith("youtube-nocookie.com")
        ):
            parent = frame.parent
            frame.decompose()
            removed.append(f"iframe YouTube indisponível removido ({MOTHER_VIDEO_ID})")
            # Retira somente um wrapper que ficou vazio; preserva textos e outros
            # elementos do post.
            while (
                parent
                and getattr(parent, "name", None) in {"p", "div"}
                and not parent.get_text(" ", strip=True)
                and not parent.find(["img", "iframe", "video", "object", "embed", "a"])
            ):
                next_parent = parent.parent
                parent.decompose()
                parent = next_parent
    return str(soup), removed


def source_fingerprint(post: dict) -> str:
    fields = {
        key: post.get(key)
        for key in ("id", "title", "content", "published", "updated", "status", "url", "labels")
    }
    return hashlib.sha256(
        json.dumps(fields, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def build_plan(posts: list[dict]) -> dict[str, dict]:
    actions: dict[str, dict] = {}

    # Duplicata: exige exatamente duas instâncias e igualdade de hash antes
    # de escolher a cópia mais recente pela data original de publicação.
    province_matches = [
        p for p in posts
        if normalized_title(p.get("title")) == normalized_title(PROVINCE_TITLE)
    ]
    if len(province_matches) != 2:
        raise RuntimeError(
            "Esperava exatamente duas instâncias do post da Província; "
            f"encontrei {len(province_matches)}. Nenhuma mudança foi planejada."
        )
    if body_hash(province_matches[0].get("content", "")) != body_hash(
        province_matches[1].get("content", "")
    ):
        raise RuntimeError(
            "Os corpos atuais dos dois posts da Província não têm o mesmo SHA-256. "
            "O diagnóstico mudou; não vou escolher uma cópia automaticamente."
        )
    newest = max(
        province_matches,
        key=lambda p: p.get("published") or p.get("updated") or "",
    )
    entry = add_action(actions, newest)
    entry["draft_reasons"].append("cópia mais recente do post 100% duplicado da Província")

    pdf_matches = [
        p for p in posts
        if normalized_title(p.get("title")) == normalized_title(PDF_EMPTY_TITLE)
    ]
    if len(pdf_matches) != 1:
        raise RuntimeError(
            "Esperava um único post com título PDF vazio; "
            f"encontrei {len(pdf_matches)}."
        )
    add_action(actions, pdf_matches[0])["draft_reasons"].append(
        "post com título PDF e corpo vazio"
    )

    homepage_matches = [p for p in posts if image_only_homepage_candidate(p)]
    if len(homepage_matches) != 1:
        raise RuntimeError(
            "Esperava um único post sem título na URL raiz com somente uma imagem; "
            f"encontrei {len(homepage_matches)}."
        )
    add_action(actions, homepage_matches[0])["draft_reasons"].append(
        "entrada sem título na URL raiz, contendo somente uma imagem"
    )

    # Reprocessa o corpo em memória, unindo várias operações por post.
    for post in posts:
        content = post.get("content") or ""
        new_content, link_changes = clean_broken_links(content)
        new_content, video_changes = remove_unavailable_mother_video(
            new_content, post.get("title") or ""
        )
        if link_changes or video_changes:
            entry = add_action(actions, post)
            entry["new_content"] = new_content
            entry["content_reasons"].extend(link_changes + video_changes)
            entry["changes"].append(
                {
                    "before": content,
                    "after": new_content,
                }
            )
    return actions


def print_plan(actions: dict[str, dict], dry_run: bool) -> None:
    mode = "DRY-RUN — nenhuma alteração será gravada" if dry_run else "APLICAÇÃO"
    print(f"\n{mode}")
    print(f"Posts afetados: {len(actions)}")
    for post_id, item in actions.items():
        post = item["post"]
        title = post.get("title") or "(sem título)"
        print("\n" + "=" * 88)
        print(f"ID: {post_id}")
        print(f"Título: {title}")
        print(f"URL: {post.get('url', '')}")
        print(f"Status atual: {current_status(post)}")
        if item["draft_reasons"]:
            print("Status planejado: DRAFT — " + "; ".join(item["draft_reasons"]))
        for reason in item["content_reasons"]:
            print(f"HTML: {reason}")
        for change in item["changes"]:
            before_lines = change["before"].splitlines(keepends=True)
            after_lines = change["after"].splitlines(keepends=True)
            diff = difflib.unified_diff(
                before_lines,
                after_lines,
                fromfile="antes",
                tofile="depois",
            )
            rendered = "".join(diff)
            if rendered:
                print(rendered, end="" if rendered.endswith("\n") else "\n")
            else:
                print("HTML sem diferença.")


def backup_path(directory: Path, post: dict, now: str) -> Path:
    post_id = re.sub(r"[^A-Za-z0-9_-]", "_", str(post["id"]))
    return directory / f"{now}_post_{post_id}.json"


def write_backup(path: Path, post: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(post, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(path)


def apply_plan(service, blog_id: str, actions: dict[str, dict], backup_dir: Path) -> None:
    # Antes de qualquer escrita: relê cada post, verifica que continua igual ao
    # plano e salva o JSON completo de todos os originais.
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    prepared = []
    for post_id, item in actions.items():
        current = service.posts().get(
            blogId=blog_id,
            postId=post_id,
            view="ADMIN",
            fetchBody=True,
        ).execute()
        if source_fingerprint(current) != source_fingerprint(item["post"]):
            raise RuntimeError(
                f"Post {post_id} mudou após a leitura inicial. "
                "Abortei antes de fazer qualquer gravação."
            )
        path = backup_path(backup_dir, current, now)
        if path.exists():
            raise RuntimeError(f"Backup já existe; não vou sobrescrever: {path}")
        write_backup(path, current)
        prepared.append((post_id, item, current, path))

    print(f"\nBackups JSON originais gravados: {len(prepared)} em {backup_dir}")
    for post_id, item, current, path in prepared:
        print(f"Backup: {path}")
        status = current_status(current)
        # Primeiro tira do ar os posts que devem virar rascunho.
        if item["draft_reasons"] and status in {"LIVE", "SCHEDULED"}:
            response = service.posts().revert(
                blogId=blog_id,
                postId=post_id,
            ).execute()
            print(f"Revertido para rascunho: {post_id} ({response.get('status', 'status não retornado')})")
        elif item["draft_reasons"] and status == "DRAFT":
            print(f"Já estava em rascunho: {post_id}")

        # PATCH altera somente o corpo. Título, data e rótulos não são enviados.
        if item["content_reasons"] and item["new_content"] != (current.get("content") or ""):
            response = service.posts().patch(
                blogId=blog_id,
                postId=post_id,
                body={"content": item["new_content"]},
                fetchBody=True,
            ).execute()
            print(f"Corpo atualizado: {post_id}")

        verified = service.posts().get(
            blogId=blog_id,
            postId=post_id,
            view="ADMIN",
            fetchBody=True,
        ).execute()
        if item["draft_reasons"] and current_status(verified) != "DRAFT":
            raise RuntimeError(f"Verificação falhou: post {post_id} não ficou DRAFT.")
        if item["content_reasons"] and verified.get("content") != item["new_content"]:
            raise RuntimeError(f"Verificação falhou: corpo do post {post_id} não corresponde ao plano.")
        print(f"Verificado: {post_id}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="autoriza a execução das alterações; sem isso o script só simula",
    )
    parser.add_argument(
        "--confirm-apply",
        action="store_true",
        help="confirma a execução real junto com --apply (também funciona em GitHub Actions)",
    )
    parser.add_argument(
        "--backup-dir",
        default="backups/blogger-posts",
        help="diretório dos JSON originais (padrão: backups/blogger-posts)",
    )
    args = parser.parse_args()

    if args.confirm_apply and not args.apply:
        parser.error("--confirm-apply só pode ser usado junto com --apply")
    if args.apply and not args.confirm_apply:
        parser.error("Para gravar, informe as duas opções: --apply --confirm-apply")

    dry_run = DRY_RUN and not args.apply
    service = make_service()
    blog_id = locate_blog_id(service)
    posts = list_all_posts(service, blog_id)
    actions = build_plan(posts)
    print_plan(actions, dry_run)

    if dry_run:
        print("\nPara aplicar após revisar o diff e os backups planejados:")
        print("  python corrigir_posts_somos_servos.py --apply --confirm-apply")
        print(f"  Backup JSON: {Path(args.backup_dir).resolve()}")
        return 0

    apply_plan(service, blog_id, actions, Path(args.backup_dir))
    print("\nConcluído. Nenhum post foi apagado.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        raise SystemExit(1)
