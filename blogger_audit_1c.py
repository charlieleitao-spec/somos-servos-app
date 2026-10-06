#!/usr/bin/env python3
"""Auditoria somente de leitura do conteúdo público do Blogger (Etapa 1C)."""
import hashlib
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from difflib import SequenceMatcher
from html.parser import HTMLParser
from pathlib import Path

from blogger_inventory import access_token, locate_blog, list_resources

BLOG_HOST = "somosservos.blogspot.com"
YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtube-nocookie.com", "www.youtube-nocookie.com"}

class ContentParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text=[]; self.links=[]; self.iframes=[]; self.files=[]
        self.hidden=0
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if tag in {"script","style","noscript"}: self.hidden+=1
        if tag=="a" and a.get("href"): self.links.append(a["href"])
        if tag=="iframe" and a.get("src"): self.iframes.append(a["src"])
        if tag in {"object","embed"}:
            src=a.get("data") or a.get("src")
            if src: self.files.append(src)
        if tag in {"video","source"}:
            src=a.get("src")
            if src: self.files.append(src)
    def handle_endtag(self, tag):
        if tag in {"script","style","noscript"} and self.hidden: self.hidden-=1
    def handle_data(self, data):
        if not self.hidden: self.text.append(data)

def host(url):
    try: return (urllib.parse.urlsplit(url).hostname or "").lower()
    except Exception: return ""

def parse_body(item):
    p=ContentParser(); p.feed(item.get("content") or ""); p.close()
    text=re.sub(r"\s+"," ",html.unescape(" ".join(p.text))).strip()
    return p,text

def normalized_text(s):
    return re.sub(r"\s+"," ",s).strip().casefold()

def canonical_url(url):
    u=urllib.parse.urlsplit(html.unescape(url.strip()))
    if u.scheme not in {"http","https"} or not u.netloc: return None
    return urllib.parse.urlunsplit((u.scheme,u.netloc,u.path or "/",u.query,""))

def fetch_status(url):
    headers={"User-Agent":"Mozilla/5.0 (compatible; SomosServosReadOnlyAudit/1.0)","Range":"bytes=0-0"}
    for method in ("HEAD","GET"):
        req=urllib.request.Request(url,headers=headers,method=method)
        try:
            with urllib.request.urlopen(req,timeout=18) as resp:
                return {"status":resp.status,"final_url":resp.geturl(),"error":""}
        except urllib.error.HTTPError as e:
            if method=="HEAD" and e.code in {400,403,405,501}: continue
            return {"status":e.code,"final_url":e.geturl(),"error":""}
        except Exception as e:
            if method=="HEAD": continue
            return {"status":None,"final_url":"","error":type(e).__name__+": "+str(e)[:180]}
    return {"status":None,"final_url":"","error":"requisição inconclusiva"}

def video_oembed(url):
    endpoint="https://www.youtube.com/oembed?"+urllib.parse.urlencode({"url":url,"format":"json"})
    try:
        req=urllib.request.Request(endpoint,headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(req,timeout=18) as r:
            data=json.load(r)
            return {"available":True,"status":r.status,"title":data.get("title","")}
    except urllib.error.HTTPError as e:
        return {"available":False,"status":e.code,"title":""}
    except Exception as e:
        return {"available":None,"status":None,"title":"","error":type(e).__name__+": "+str(e)[:160]}

def classify_pair(a,b):
    if a["sha256"]==b["sha256"]: return "idênticos",100.0
    score=SequenceMatcher(None,a["normalized"],b["normalized"],autojunk=False).ratio()*100
    return ("parecidos" if score>=75 else "diferentes"),round(score,1)

def main():
    token=access_token(); blog_id=locate_blog(token)
    posts=list_resources(blog_id,token,"post",("live","draft","scheduled"))
    pages=list_resources(blog_id,token,"página",("live","draft"))
    parsed={str(x.get("id") or x.get("url")):parse_body(x) for x in posts+pages}
    videos={}; refs={}
    for item in posts:
        key=str(item.get("id") or item.get("url")); p,_=parsed[key]
        for src in p.iframes:
            h=host(src)
            if h in YOUTUBE_HOSTS:
                video=canonical_url(src)
                if video: videos.setdefault(video,[]).append(item)
        for href in p.links:
            link=canonical_url(href)
            h=host(link or "")
            if link and h and h!=BLOG_HOST and not h.endswith(".blogspot.com"):
                refs.setdefault(link,[]).append(item)
    video_results={}
    with ThreadPoolExecutor(max_workers=8) as pool:
        fut={pool.submit(video_oembed,u):u for u in videos}
        for f in as_completed(fut): video_results[fut[f]]=f.result()
    link_results={}
    with ThreadPoolExecutor(max_workers=16) as pool:
        fut={pool.submit(fetch_status,u):u for u in refs}
        for f in as_completed(fut): link_results[fut[f]]=f.result()
    youtube=[]
    for u,items in videos.items():
        r=video_results[u]
        youtube.append({"url":u,"available":r["available"],"status":r.get("status"),"title":r.get("title",""),"posts":[{"title":x.get("title",""),"url":x.get("url","")} for x in items],"error":r.get("error","")})
    broken=[]; inconclusive=[]
    for u,items in refs.items():
        r=link_results[u]; rec={"url":u,"status":r.get("status"),"final_url":r.get("final_url"),"error":r.get("error"),"posts":[{"title":x.get("title",""),"url":x.get("url","")} for x in items]}
        if r.get("status") is not None and r["status"]>=400: broken.append(rec)
        elif r.get("status") is None: inconclusive.append(rec)
    concepts={
      "Província/década de 1960":lambda t: "provincia" in t and ("1960" in t or "decada" in t),
      "Frei Paolino":lambda t: "paolino" in t or "baldassari" in t,
      "Frei Octávio":lambda t: "octavio" in t,
      "Frei Dionísio":lambda t: "dionisio" in t,
      "Oração à N. Sra. das Dores":lambda t: "oracao" in t and "dores" in t,
      "Não Violência":lambda t: "violencia" in t or "nao violencia" in t,
    }
    comparisons=[]
    for label,matcher in concepts.items():
        group=[]
        for x in posts:
            title=normalized_text(x.get("title") or "")
            if matcher(title):
                key=str(x.get("id") or x.get("url")); p,text=parsed[key]
                raw=x.get("content") or ""
                group.append({"title":x.get("title",""),"url":x.get("url",""),"published":x.get("published",""),"sha256":hashlib.sha256(raw.encode("utf-8")).hexdigest(),"normalized":normalized_text(text),"characters":len(text)})
        pairs=[]
        for i in range(len(group)):
            for j in range(i+1,len(group)):
                status,pct=classify_pair(group[i],group[j])
                pairs.append({"post_a":group[i]["url"],"title_a":group[i]["title"],"post_b":group[j]["url"],"title_b":group[j]["title"],"classification":status,"similarity_pct":pct})
        comparisons.append({"group":label,"posts":[{k:v for k,v in x.items() if k not in {"normalized","sha256"}} for x in group],"pairs":pairs})
    attachments=[]
    for item in posts+pages:
        key=str(item.get("id") or item.get("url")); p,text=parsed[key]
        source_candidates=[]
        for u in p.links+p.iframes+p.files:
            u=html.unescape(u)
            if re.search(r"\.pdf(?:$|[?#])|drive\.google\.com|docs\.google\.com/document|\.\w{2,5}(?:$|[?#])",u,re.I): source_candidates.append(u)
        title=(item.get("title") or "").strip()
        url=(item.get("url") or "").rstrip("/")
        is_home=not title and url in {"https://somosservos.blogspot.com","http://somosservos.blogspot.com"}
        likely_pdf=any(".pdf" in u.lower() for u in source_candidates) or "pdf" in (title+" "+text[:500]).casefold()
        if likely_pdf or is_home:
            attachments.append({"type":"página inicial sem título" if is_home else "post relacionado a PDF","title":title,"url":item.get("url",""),"text":text,"raw_html":item.get("content") or "","links":p.links,"iframes":p.iframes,"embedded_files":p.files,"candidate_attachments":list(dict.fromkeys(source_candidates))})
    result={"post_count":len(posts),"page_count":len(pages),"youtube_embed_count":len(videos),"youtube":youtube,"external_link_count":len(refs),"broken_external_links":broken,"inconclusive_external_links":inconclusive,"comparisons":comparisons,"pdf_and_home_items":attachments,"read_only":True,"generated_at_utc":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())}
    out=Path("auditoria-1c.json"); out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"post_count":len(posts),"page_count":len(pages),"youtube_embed_count":len(videos),"youtube_unavailable":[x for x in youtube if x["available"] is False],"youtube_inconclusive":[x for x in youtube if x["available"] is None],"external_unique_links":len(refs),"broken_external_links":broken,"inconclusive_external_links":inconclusive,"comparisons":comparisons,"pdf_and_home_items":[{k:v for k,v in x.items() if k!="raw_html"} for x in attachments],"artifact":"auditoria-1c.json"},ensure_ascii=False))

if __name__=="__main__":
    try: main()
    except Exception as e:
        print("Falha na auditoria 1C: "+str(e),file=sys.stderr); sys.exit(1)
