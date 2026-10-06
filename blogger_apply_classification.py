#!/usr/bin/env python3
"""Apply the approved Blogger marker classification, preserving body/title/date."""
import csv
import json
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://www.googleapis.com/blogger/v3"
TOKEN_URL = "https://oauth2.googleapis.com/token"
BLOGS_URL = f"{API}/users/self/blogs"
TARGET_HOST = "somosservos.blogspot.com"
OFFICIAL = {
    "Santos e Beatos", "Ofícios", "Liturgia", "Espiritualidade servita",
    "Devoções", "Igreja e Ordem", "Documentos", "Histórico", "App e blog",
}
SERIES = {
    "Espiritualidade Mariana", "Ladainhas de Nossa Senhora", "Aprender de Maria",
    "Contemplar Maria", "Servir com Maria",
}
BATCH_SIZE = 25


def required(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Configuração ausente: {name}")
    return value


def request_json(url, method="GET", payload=None, token=None, content_type="application/json"):
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    if data is not None:
        req.add_header("Content-Type", content_type)
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Blogger API retornou HTTP {exc.code} em {method} {urllib.parse.urlsplit(url).path}.") from None
    except urllib.error.URLError:
        raise RuntimeError(f"Falha de conexão com a Blogger API em {method}.") from None


def access_token():
    form = urllib.parse.urlencode({
        "client_id": required("BLOGGER_CLIENT_ID"),
        "client_secret": required("BLOGGER_CLIENT_SECRET"),
        "refresh_token": required("BLOGGER_REFRESH_TOKEN"),
        "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request(TOKEN_URL, data=form, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            result = json.load(response)
    except (urllib.error.HTTPError, urllib.error.URLError):
        raise RuntimeError("Autenticação OAuth do Blogger falhou.") from None
    token = result.get("access_token")
    if not token:
        raise RuntimeError("Autenticação OAuth não devolveu token de acesso.")
    return token


def blog_id(token):
    configured = os.environ.get("BLOGGER_BLOG_ID", "").strip()
    if configured:
        return configured
    result = request_json(BLOGS_URL, token=token)
    for blog in result.get("items", []):
        if TARGET_HOST in (blog.get("url") or "").lower():
            return str(blog["id"])
    raise RuntimeError("O blog Somos Servos não foi encontrado na conta autorizada.")


def list_posts(blog, token):
    base = f"{API}/blogs/{urllib.parse.quote(blog, safe='')}/posts"
    found = {}
    for status in ("live", "draft", "scheduled"):
        next_page = None
        while True:
            params = {"maxResults": "500", "fetchBodies": "true", "view": "ADMIN", "status": status}
            if next_page:
                params["pageToken"] = next_page
            page = request_json(base + "?" + urllib.parse.urlencode(params), token=token)
            for post in page.get("items", []):
                if post.get("id"):
                    found[str(post["id"])] = post
            next_page = page.get("nextPageToken")
            if not next_page:
                break
    return list(found.values())


def url_key(url):
    parts = urllib.parse.urlsplit((url or "").strip())
    return (parts.hostname or "").lower(), parts.path.rstrip("/")


def parse_list(value):
    return [part.strip() for part in (value or "").replace("\n", "|").split("|") if part.strip()]


def ordered_unique(items):
    return list(dict.fromkeys(items))


def csv_rows(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        yield from csv.DictReader(stream)


def validate_assignment(row):
    main = (row.get("marcador_principal") or "").strip()
    action = (row.get("acao_sugerida") or "").strip().casefold()
    if (row.get("tipo") or "").strip().casefold() != "post":
        return None, "ignorado: página"
    if not main:
        return None, "ignorado: marcador_principal vazio"
    if "revisar" in action or "apagar" in action:
        return None, f"ignorado: ação {row.get('acao_sugerida', '').strip()}"
    extras = parse_list(row.get("marcadores_extras"))
    if main not in OFFICIAL or any(label not in OFFICIAL for label in extras):
        return None, "revisar: marcador fora da lista oficial"
    if len(extras) > 2 or main in extras or len(set(extras)) != len(extras):
        return None, "revisar: limite ou duplicidade de marcadores inválido"
    if main == "Histórico" and extras:
        return None, "revisar: Histórico não pode ter marcadores extras"
    return (main, extras), ""


def write_log(writer, stream, **fields):
    writer.writerow(fields)
    stream.flush()


def main():
    apply = os.environ.get("APPLY_CHANGES", "false").strip().lower() == "true"
    source = Path(os.environ.get("CLASSIFICATION_CSV", "classification.csv"))
    backup_dir = Path("backups/blogger-labels")
    backup_dir.mkdir(parents=True, exist_ok=True)
    log_path = Path("blogger-labels-audit.csv")
    fields = ["titulo", "URL", "post_id", "status", "resultado", "marcadores_antes", "marcadores_depois", "detalhe"]
    token = access_token()
    blog = blog_id(token)
    posts = list_posts(blog, token)
    by_url = {}
    for post in posts:
        by_url.setdefault(url_key(post.get("url")), []).append(post)

    inputs = list(csv_rows(source))
    print(f"Posts e rascunhos carregados: {len(posts)}; linhas da classificação: {len(inputs)}.")
    print(f"Modo: {'APLICAÇÃO' if apply else 'SIMULAÇÃO'}; lote de {BATCH_SIZE} posts.")
    changes = 0
    skipped = 0
    already = 0
    review = 0

    with log_path.open("w", encoding="utf-8-sig", newline="") as log_stream:
        writer = csv.DictWriter(log_stream, fieldnames=fields)
        writer.writeheader()
        sequence = 0
        for row in inputs:
            assignment, reason = validate_assignment(row)
            title = (row.get("titulo") or "").strip()
            url = (row.get("URL") or "").strip()
            if assignment is None:
                skipped += 1
                write_log(writer, log_stream, titulo=title, URL=url, post_id="", status="", resultado="IGNORADO", marcadores_antes="", marcadores_depois="", detalhe=reason)
                continue

            candidates = by_url.get(url_key(url), [])
            candidates = [p for p in candidates if (p.get("title") or "").strip() == title]
            if len(candidates) != 1:
                skipped += 1
                status = "não encontrado" if not candidates else "ambíguo"
                write_log(writer, log_stream, titulo=title, URL=url, post_id="", status=status, resultado="REVISAR", marcadores_antes="", marcadores_depois="", detalhe="URL/título não identificam exatamente um post publicável/rascunho; sem alteração.")
                review += 1
                continue

            post = candidates[0]
            post_id = str(post["id"])
            before = ordered_unique(post.get("labels") or [])
            main, extras = assignment
            preserved_series = [label for label in before if label in SERIES]
            if main == "Histórico" and preserved_series:
                skipped += 1
                review += 1
                write_log(writer, log_stream, titulo=title, URL=url, post_id=post_id, status=post.get("status", ""), resultado="REVISAR", marcadores_antes=" | ".join(before), marcadores_depois="", detalhe="Histórico conflita com marcador de série que deve ser preservado; sem alteração.")
                continue
            desired = ordered_unique([main, *extras, *preserved_series])
            if len(desired) != len([main, *extras, *preserved_series]):
                skipped += 1
                review += 1
                write_log(writer, log_stream, titulo=title, URL=url, post_id=post_id, status=post.get("status", ""), resultado="REVISAR", marcadores_antes=" | ".join(before), marcadores_depois="", detalhe="Marcador repetido após preservar série; sem alteração.")
                continue
            if set(before) == set(desired):
                already += 1
                write_log(writer, log_stream, titulo=title, URL=url, post_id=post_id, status=post.get("status", ""), resultado="JÁ CORRETO", marcadores_antes=" | ".join(before), marcadores_depois=" | ".join(desired), detalhe="Nenhuma gravação necessária.")
                continue

            sequence += 1
            batch_number = (sequence - 1) // BATCH_SIZE + 1
            print(f"Lote {batch_number} — {sequence}: {title}\n  antes: {' | '.join(before) or '(sem marcadores)'}\n  depois: {' | '.join(desired)}")
            if not apply:
                write_log(writer, log_stream, titulo=title, URL=url, post_id=post_id, status=post.get("status", ""), resultado="DRY-RUN", marcadores_antes=" | ".join(before), marcadores_depois=" | ".join(desired), detalhe="Simulação; nenhuma alteração enviada.")
                continue

            backup_path = backup_dir / f"{post_id}.json"
            if not backup_path.exists():
                backup_path.write_text(json.dumps(post, ensure_ascii=False, indent=2), encoding="utf-8")
            resource = f"{API}/blogs/{urllib.parse.quote(blog, safe='')}/posts/{urllib.parse.quote(post_id, safe='')}"
            updated = request_json(resource, method="PATCH", payload={"labels": desired}, token=token)
            check = request_json(resource + "?" + urllib.parse.urlencode({"view": "ADMIN"}), token=token)
            if set(check.get("labels") or []) != set(desired):
                raise RuntimeError(f"Leitura de volta não confirmou os marcadores do post {post_id}.")
            if (check.get("title") or "") != (post.get("title") or "") or (check.get("content") or "") != (post.get("content") or "") or check.get("published") != post.get("published"):
                raise RuntimeError(f"Título, corpo ou data mudou inesperadamente no post {post_id}; backup JSON foi salvo.")
            changes += 1
            by_url[url_key(url)] = [check]
            write_log(writer, log_stream, titulo=title, URL=url, post_id=post_id, status=post.get("status", ""), resultado="APLICADO E CONFERIDO", marcadores_antes=" | ".join(before), marcadores_depois=" | ".join(check.get("labels") or []), detalhe=f"Backup: {backup_path.as_posix()}; patch + leitura de volta confirmados.")
            if sequence % BATCH_SIZE == 0:
                print(f"Lote {batch_number} conferido ({BATCH_SIZE} posts); iniciando o próximo.")
                time.sleep(0.25)

    print(f"Concluído: {changes} alterados e conferidos; {already} já corretos; {skipped} ignorados/revisão ({review} requerem revisão).")
    print(f"Log: {log_path}; backups JSON: {backup_dir}.")
    print("Títulos, corpo e data de publicação verificados sem alteração nos posts atualizados.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Falha: {exc}", file=sys.stderr)
        sys.exit(1)
