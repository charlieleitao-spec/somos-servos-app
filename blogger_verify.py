#!/usr/bin/env python3
"""Verifica OAuth e localiza o blog Somos Servos sem publicar conteúdo."""
import json
import os
import sys
import urllib.parse
import urllib.request
import urllib.error

TOKEN_URL = "https://oauth2.googleapis.com/token"
BLOGS_URL = "https://www.googleapis.com/blogger/v3/users/self/blogs"
TARGET_HOST = "somosservos.blogspot.com"


def post_form(url, data):
    encoded = urllib.parse.urlencode(data).encode("utf-8")
    request = urllib.request.Request(url, data=encoded, method="POST")
    request.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def get_json(url, access_token):
    request = urllib.request.Request(url)
    request.add_header("Authorization", f"Bearer {access_token}")
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def required(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Secret ausente: {name}")
    return value


def main():
    client_id = required("BLOGGER_CLIENT_ID")
    client_secret = required("BLOGGER_CLIENT_SECRET")
    refresh_token = required("BLOGGER_REFRESH_TOKEN")

    token = post_form(TOKEN_URL, {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    })
    access_token = token.get("access_token")
    if not access_token:
        raise RuntimeError("O Google não devolveu um access token.")

    data = get_json(BLOGS_URL, access_token)
    blogs = data.get("items", [])
    if not blogs:
        raise RuntimeError("A conta autorizada não retornou nenhum blog.")

    target = None
    for blog in blogs:
        url = (blog.get("url") or "").lower()
        if TARGET_HOST in url:
            target = blog
            break

    if not target:
        nomes = ", ".join(blog.get("name", "(sem nome)") for blog in blogs)
        raise RuntimeError(f"Somos Servos não foi localizado. Blogs acessíveis: {nomes}")

    print("Conexão OAuth com o Blogger: OK")
    print(f"Blog localizado: {target.get('name')}")
    print(f"URL: {target.get('url')}")
    print(f"Blog ID: {target.get('id')}")
    print("Nenhuma postagem foi criada ou alterada.")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"Erro HTTP {exc.code} ao verificar Blogger: {body}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"Falha na verificação do Blogger: {exc}", file=sys.stderr)
        sys.exit(1)
