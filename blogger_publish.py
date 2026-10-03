#!/usr/bin/env python3
"""Publica uma postagem no Blogger sem duplicar título e confirma a leitura de volta."""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

TOKEN_URL = "https://oauth2.googleapis.com/token"
BLOGS_URL = "https://www.googleapis.com/blogger/v3/users/self/blogs"
TARGET_HOST = "somosservos.blogspot.com"


def required(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Configuração ausente: {name}")
    return value


def request_json(url, method="GET", data=None, token=None, content_type=None, operation="Blogger API"):
    req = urllib.request.Request(url, data=data, method=method)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    if content_type:
        req.add_header("Content-Type", content_type)
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        # Não registra corpos de erro que possam conter dados sensíveis.
        raise RuntimeError(f"{operation} respondeu HTTP {exc.code}.") from None


def get_access_token():
    form = urllib.parse.urlencode({
        "client_id": required("BLOGGER_CLIENT_ID"),
        "client_secret": required("BLOGGER_CLIENT_SECRET"),
        "refresh_token": required("BLOGGER_REFRESH_TOKEN"),
        "grant_type": "refresh_token",
    }).encode()
    token = request_json(TOKEN_URL, "POST", form,
                         content_type="application/x-www-form-urlencoded",
                         operation="Autenticação OAuth").get("access_token")
    if not token:
        raise RuntimeError("Autenticação OAuth não devolveu token de acesso.")
    print("Autenticação OAuth concluída.")
    return token


def find_blog(token):
    blogs = request_json(BLOGS_URL, token=token, operation="Consulta de blogs").get("items", [])
    blog = next((b for b in blogs if TARGET_HOST in (b.get("url") or "").lower()), None)
    if not blog:
        raise RuntimeError("Blog Somos Servos não localizado na conta autorizada.")
    print("Blog Somos Servos localizado.")
    return blog


def existing_title(blog_id, token, title):
    next_token = None
    while True:
        query = {"maxResults": "500", "fetchBodies": "false"}
        if next_token:
            query["pageToken"] = next_token
        url = (f"https://www.googleapis.com/blogger/v3/blogs/{blog_id}/posts/?"
               f"{urllib.parse.urlencode(query)}")
        page = request_json(url, token=token, operation="Consulta de postagens")
        found = next((p for p in page.get("items", [])
                      if (p.get("title") or "").strip().casefold() == title.strip().casefold()), None)
        if found:
            return found
        next_token = page.get("nextPageToken")
        if not next_token:
            return None


def main():
    title = required("POST_TITLE").strip()
    content = required("POST_CONTENT")
    labels = [x.strip() for x in os.environ.get("POST_LABELS", "").split(",") if x.strip()]
    token = get_access_token()
    blog = find_blog(token)

    duplicate = existing_title(blog["id"], token, title)
    if duplicate:
        print(f"Já existe postagem com esse título (ID {duplicate.get('id')}); nenhuma duplicata criada.")
        print(f"URL: {duplicate.get('url')}")
        return

    payload = {"kind": "blogger#post", "title": title, "content": content}
    if labels:
        payload["labels"] = labels
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    created = request_json(
        f"https://www.googleapis.com/blogger/v3/blogs/{blog['id']}/posts/",
        "POST", data, token, "application/json; charset=UTF-8", "Criação da postagem")
    post_id = created.get("id")
    if not post_id:
        raise RuntimeError("A API não devolveu o identificador da postagem criada.")

    verified = request_json(
        f"https://www.googleapis.com/blogger/v3/blogs/{blog['id']}/posts/{post_id}?fetchBodies=true",
        token=token, operation="Verificação da postagem")
    if verified.get("id") != post_id or verified.get("title") != title or not verified.get("url"):
        raise RuntimeError("A leitura de volta da API não confirmou ID, título e URL.")
    print(f"Publicado e confirmado pela API: {verified.get('title')}")
    print(f"URL: {verified.get('url')}")
    print(f"ID da postagem confirmado: {post_id}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Falha: {exc}", file=sys.stderr)
        sys.exit(1)
