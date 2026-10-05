#!/usr/bin/env python3
"""Prepara o post semanal servita no fluxo Blogger já existente.

O post cobre sete dias a partir do domingo selecionado (domingo a sábado),
usa apenas título/data da fonte e cartões já disponíveis em cartoes/.
Posts automáticos ficam sempre em rascunho até autorização explícita.
"""
import datetime as dt
import hashlib
import html
import json
import os
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

from blogger_daily_publish import (
    TIMEZONE, access_token, find_duplicate, get_public_json,
    json_request, list_existing_posts, locate_blog,
)

MONTHS = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]
WEEKDAYS = [
    "segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
    "sexta-feira", "sábado", "domingo",
]
PAGES_BASE = "https://charlieleitao-spec.github.io/somos-servos-app"
HOJE_FAMILIA_SERVITA_URL = "https://charlieleitao-spec.github.io/hoje-familia-servita/"
LABELS = ["Ordem dos Servos de Maria", "Semana servita"]


def week_range(start):
    return start, start + dt.timedelta(days=6)


def date_label(date):
    return (
        f"{WEEKDAYS[date.weekday()]}, {date.day} de "
        f"{MONTHS[date.month - 1]} de {date.year}"
    )


def week_entries(santoral, start):
    events = []
    for offset in range(7):
        day = start + dt.timedelta(days=offset)
        for entry in santoral:
            try:
                matches = int(entry.get("month", 0)) == day.month and int(entry.get("day", 0)) == day.day
            except (TypeError, ValueError):
                matches = False
            if matches:
                events.append((day, entry))
    return events


def week_title(start):
    first, last = week_range(start)
    return f"A semana na Família Servita ({first:%d/%m} a {last:%d/%m})"


def card_public_url(date, cards_dir):
    filename = f"cartao-{date:%m-%d}.png"
    path = Path(cards_dir) / filename
    if not path.is_file():
        return None
    version = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    return f"{PAGES_BASE}/cartoes/{filename}?v={version}"


def make_week_content(santoral, start, cards_dir="cartoes"):
    marker = f"<!-- somos-servos-source-id:semana-{start.isoformat()} -->"
    parts = [marker]
    events = week_entries(santoral, start)
    for day, entry in events:
        title = html.escape(str(entry.get("title") or entry.get("name") or "Celebração servita"), quote=False)
        parts.append(f"<h3>{title}</h3>")
        parts.append(f"<p><strong>{html.escape(date_label(day), quote=False)}</strong></p>")
        image_url = card_public_url(day, cards_dir)
        if image_url:
            alt = html.escape(
                f"Cartão da celebração: {entry.get('title') or entry.get('name')} — {date_label(day)}",
                quote=True,
            )
            parts.append(
                '<figure style="margin:0 0 1.5em;text-align:center">'
                f'<img src="{html.escape(image_url, quote=True)}" alt="{alt}" '
                'width="1080" height="1350" style="max-width:100%;height:auto" />'
                '</figure>'
            )

    parts.append(
        '<p>O sábado é dedicado de modo especial à Virgem Maria na tradição da '
        'Ordem dos Servos de Maria. Conheça o Sábado Mariano no app '
        f'<a href="{HOJE_FAMILIA_SERVITA_URL}">Hoje na Família Servita</a>.</p>'
    )
    return "\n".join(parts)


def parse_start():
    raw = os.environ.get("WEEK_START", "").strip()
    if not raw:
        return dt.datetime.now(TIMEZONE).date()
    try:
        return dt.date.fromisoformat(raw)
    except ValueError:
        raise RuntimeError("WEEK_START deve estar no formato AAAA-MM-DD.") from None


def main():
    start = parse_start()
    if os.environ.get("GITHUB_EVENT_NAME") == "schedule" and start.weekday() != 6:
        print(f"Post semanal não executado: hoje não é domingo em {TIMEZONE.key}.")
        return
    if os.environ.get("GITHUB_EVENT_NAME") == "schedule":
        start = dt.datetime.now(TIMEZONE).date()

    santoral = get_public_json("santoral.json")
    title = week_title(start)
    content = make_week_content(santoral, start)
    dry_run = os.environ.get("DRY_RUN", "false").strip().lower() == "true"
    source_marker = f"somos-servos-source-id:semana-{start.isoformat()}"

    print(f"Título: {title}")
    print(f"Marcadores: {', '.join(LABELS)}")
    print("HTML da prévia:")
    print(content)
    if dry_run:
        print("Prévia concluída; nenhuma postagem criada.")
        return

    if os.environ.get("DRAFT", "true").strip().lower() != "true":
        raise RuntimeError("O post semanal deve permanecer em rascunho até autorização direta.")

    token = access_token()
    blog = locate_blog(token)
    duplicate = find_duplicate(list_existing_posts(blog["id"], token), title, source_marker)
    if duplicate:
        print(f"Já existe postagem semanal (ID {duplicate.get('id')}); nenhuma duplicata criada.")
        return

    payload = {
        "kind": "blogger#post",
        "title": title,
        "content": content,
        "labels": LABELS,
    }
    endpoint = f"https://www.googleapis.com/blogger/v3/blogs/{blog['id']}/posts/?isDraft=true"
    created = json_request(
        endpoint, "POST", json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        token, "application/json; charset=UTF-8", "Criação do rascunho semanal",
    )
    post_id = created.get("id")
    if not post_id:
        raise RuntimeError("A API não devolveu o identificador do rascunho semanal.")
    verified = json_request(
        f"https://www.googleapis.com/blogger/v3/blogs/{blog['id']}/posts/{post_id}?view=ADMIN",
        token=token, operation="Verificação do rascunho semanal",
    )
    if verified.get("id") != post_id or verified.get("title") != title:
        raise RuntimeError("A leitura de volta não confirmou título e identificador do rascunho.")
    if source_marker not in (verified.get("content") or ""):
        raise RuntimeError("A leitura de volta não confirmou o marcador de origem.")
    if "Semana servita" not in (verified.get("labels") or []):
        raise RuntimeError("A leitura de volta não confirmou o marcador Semana servita.")
    if str(verified.get("status", "")).upper() != "DRAFT":
        raise RuntimeError("A postagem semanal não foi confirmada como rascunho.")
    print(f"Rascunho semanal criado e confirmado: {verified.get('title')}")
    if verified.get("url"):
        print(f"URL de prévia: {verified.get('url')}")
    print(f"ID do rascunho confirmado: {post_id}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Falha: {exc}", file=sys.stderr)
        sys.exit(1)
