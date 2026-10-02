#!/usr/bin/env python3
"""Publica uma postagem no blog Somos Servos via Blogger API v3."""
import json, os, sys, urllib.error, urllib.parse, urllib.request

TOKEN_URL="https://oauth2.googleapis.com/token"
BLOGS_URL="https://www.googleapis.com/blogger/v3/users/self/blogs"
TARGET_HOST="somosservos.blogspot.com"

def required(name):
    value=os.environ.get(name,"").strip()
    if not value: raise RuntimeError(f"Variável/secret ausente: {name}")
    return value

def request_json(url, method="GET", data=None, token=None, content_type=None):
    body=None if data is None else data
    req=urllib.request.Request(url,data=body,method=method)
    if token: req.add_header("Authorization",f"Bearer {token}")
    if content_type: req.add_header("Content-Type",content_type)
    with urllib.request.urlopen(req,timeout=30) as response:
        return json.load(response)

def main():
    form=urllib.parse.urlencode({
      "client_id":required("BLOGGER_CLIENT_ID"),
      "client_secret":required("BLOGGER_CLIENT_SECRET"),
      "refresh_token":required("BLOGGER_REFRESH_TOKEN"),
      "grant_type":"refresh_token"}).encode()
    token=request_json(TOKEN_URL,"POST",form,content_type="application/x-www-form-urlencoded").get("access_token")
    if not token: raise RuntimeError("Google não devolveu access token.")
    blogs=request_json(BLOGS_URL,token=token).get("items",[])
    blog=next((b for b in blogs if TARGET_HOST in (b.get("url") or "").lower()),None)
    if not blog: raise RuntimeError("Blog Somos Servos não localizado na conta autorizada.")
    payload={"kind":"blogger#post","title":required("POST_TITLE"),"content":required("POST_CONTENT")}
    labels=os.environ.get("POST_LABELS","").strip()
    if labels: payload["labels"]=[x.strip() for x in labels.split(",") if x.strip()]
    data=json.dumps(payload,ensure_ascii=False).encode("utf-8")
    result=request_json(f"https://www.googleapis.com/blogger/v3/blogs/{blog['id']}/posts/","POST",data,token,"application/json; charset=UTF-8")
    print(f"Publicado: {result.get('title')}")
    print(f"URL: {result.get('url')}")

if __name__=="__main__":
    try: main()
    except urllib.error.HTTPError as exc:
        print(f"Erro HTTP {exc.code}: {exc.read().decode('utf-8',errors='replace')}",file=sys.stderr); sys.exit(1)
    except Exception as exc:
        print(f"Falha: {exc}",file=sys.stderr); sys.exit(1)
