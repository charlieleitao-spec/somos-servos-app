#!/usr/bin/env python3
"""Finaliza a série mariana no Blogger com leitura de volta pela API."""
import base64, html, json, os, re, sys, urllib.error, urllib.parse, urllib.request
from pathlib import Path

M=json.loads(Path("data/ladainhas-series.json").read_text(encoding="utf-8"))
HOST="somosservos.blogspot.com"
EDITORIAL="Contemplar Maria — Aprender de Maria — Servir com Maria"
LABELS=["Ladainhas de Nossa Senhora","Espiritualidade Mariana","Servos de Maria"]

def req(url, method="GET", data=None, token=None, ctype=None, op="Blogger API"):
    r=urllib.request.Request(url,data=data,method=method)
    if token:r.add_header("Authorization","Bearer "+token)
    if ctype:r.add_header("Content-Type",ctype)
    try:
        with urllib.request.urlopen(r,timeout=60) as x:return json.load(x)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{op} respondeu HTTP {e.code}.") from None

def env(n):
    v=os.environ.get(n,"").strip()
    if not v:raise RuntimeError(f"Configuração ausente: {n}")
    return v

def auth():
    form=urllib.parse.urlencode({"client_id":env("BLOGGER_CLIENT_ID"),"client_secret":env("BLOGGER_CLIENT_SECRET"),"refresh_token":env("BLOGGER_REFRESH_TOKEN"),"grant_type":"refresh_token"}).encode()
    t=req("https://oauth2.googleapis.com/token","POST",form,ctype="application/x-www-form-urlencoded",op="Autenticação OAuth").get("access_token")
    if not t:raise RuntimeError("Autenticação OAuth não devolveu token.")
    print("Autenticação OAuth concluída.")
    blogs=req("https://www.googleapis.com/blogger/v3/users/self/blogs",token=t,op="Consulta de blogs").get("items",[])
    b=next((x for x in blogs if HOST in (x.get("url") or "").lower()),None)
    if not b:raise RuntimeError("Blog Somos Servos não localizado.")
    return t,b["id"]

def list_all(blog,resource,token):
    out=[]; page=None
    while True:
        q={"maxResults":"500","fetchBodies":"false"}
        if page:q["pageToken"]=page
        x=req(f"https://www.googleapis.com/blogger/v3/blogs/{blog}/{resource}/?{urllib.parse.urlencode(q)}",token=token,op=f"Consulta de {resource}")
        out.extend(x.get("items",[]));page=x.get("nextPageToken")
        if not page:return out

def read(blog,resource,item,token):
    return req(f"https://www.googleapis.com/blogger/v3/blogs/{blog}/{resource}/{item['id']}?fetchBodies=true",token=token,op=f"Leitura de {resource[:-1]}")

def save(blog,resource,token,title,content,current=None,labels=None):
    payload={"kind":"blogger#post" if resource=="posts" else "blogger#page","title":title,"content":content}
    if current:
        payload["id"]=current["id"]
        if current.get("published"):payload["published"]=current["published"]
        if resource=="posts":payload["labels"]=current.get("labels",labels or [])
        method="PUT";url=f"https://www.googleapis.com/blogger/v3/blogs/{blog}/{resource}/{current['id']}"
    else:
        if resource=="posts" and labels:payload["labels"]=labels
        method="POST";url=f"https://www.googleapis.com/blogger/v3/blogs/{blog}/{resource}/"
    result=req(url,method,json.dumps(payload,ensure_ascii=False).encode(),token,"application/json; charset=UTF-8",f"Gravação de {resource[:-1]}")
    rid=result.get("id") or (current or {}).get("id")
    if not rid:raise RuntimeError(f"A API não devolveu ID de {resource[:-1]}.")
    check=req(f"https://www.googleapis.com/blogger/v3/blogs/{blog}/{resource}/{rid}?fetchBodies=true",token=token,op=f"Verificação de {resource[:-1]}")
    if check.get("id")!=rid or check.get("title")!=title or not check.get("url") or check.get("content","")!=content:
        raise RuntimeError(f"A API não confirmou conteúdo, título, ID e URL de {resource[:-1]}.")
    return check

def inl(s):
    s=html.escape(s,quote=False)
    s=re.sub(r"\[([^\]]+)\]\((https?://[^ )]+)\)",r'<a href="\2">\1</a>',s)
    s=re.sub(r"\x60([^\x60]+)\x60",r"<code>\1</code>",s)
    s=re.sub(r"\*\*(.+?)\*\*",r"<strong>\1</strong>",s,flags=re.S)
    s=re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)",r"<em>\1</em>",s,flags=re.S)
    return s.replace("\uE000","<br>")
def markdown_html(md):
    lines=md.replace("\r\n","\n").replace("\r","\n").split("\n");out=[];i=0
    while i<len(lines):
        line=lines[i]
        if not line.strip():i+=1;continue
        h=re.match(r"^(#{1,6})\s+(.*)$",line)
        if h:
            n=len(h.group(1))
            if n>1:out.append(f"<h{n}>{inl(h.group(2).strip())}</h{n}>")
            i+=1;continue
        if re.match(r"^\s*(---+|\*\*\*+|___+)\s*$",line):out.append("<hr>");i+=1;continue
        if line.lstrip().startswith(">"):
            q=[]
            while i<len(lines) and lines[i].lstrip().startswith(">"):q.append(lines[i].lstrip()[1:].lstrip());i+=1
            out.append("<blockquote><p>"+inl(" ".join(q))+"</p></blockquote>");continue
        p=[]
        while i<len(lines) and lines[i].strip() and not re.match(r"^#{1,6}\s+|^\s*(---+|\*\*\*+|___+)\s*$|^\s*>",lines[i]):
            hard=lines[i].endswith("  ")
            p.append(lines[i].rstrip()+("\uE000" if hard else " "))
            i+=1
        if p:
            s="".join(p).rstrip(" ")
            out.append("<p>"+inl(s)+"</p>")
    return "\n".join(out)

def nav(prev,index_url,nxt):
    def item(label,x):
        return f'<a href="{html.escape(x["url"],quote=True)}">{label}</a>' if x else f'<span aria-disabled="true">{label}</span>'
    return '<nav class="ladainhas-navigation" aria-label="Navegação da série">'+item("← Anterior",prev)+' | <a href="'+html.escape(index_url,quote=True)+'">Índice das Ladainhas</a> | '+item("Próxima →",nxt)+'</nav>'

def with_nav(content,block):
    pat=re.compile(r'<nav\b[^>]*class=["\'][^"\']*ladainhas-navigation[^"\']*["\'][^>]*>.*?</nav>',re.I|re.S)
    return pat.sub(block,content,count=1) if pat.search(content) else content.rstrip()+"\n\n"+block

def index_html(posts,conclusion_url):
    groups=[("Invocações iniciais",posts[0:3]),("Maria, Mãe de Cristo e da Igreja",posts[3:17]),("Virgem e modelo de vida cristã",posts[17:23]),("Imagens e símbolos marianos",posts[23:36]),("Maria junto aos que sofrem",posts[36:41]),("Maria, Rainha",posts[41:])]
    out=["<h2>As Ladainhas de Nossa Senhora</h2>",f"<p><em>{EDITORIAL}</em></p>","<p>Uma escola de contemplação mariana. Percorra as invocações da Ladainha Lauretana e os textos preparados para o Somos Servos.</p>",f'<p><a href="{html.escape(M["opening"]["url"],quote=True)}">Apresentação — Uma escola de contemplação mariana</a></p>']
    for name,items in groups:
        if not items:continue
        out.append("<h3>"+html.escape(name)+"</h3><ol>")
        for x in items:out.append('<li><a href="'+html.escape(x["url"],quote=True)+'">'+html.escape(x["title"])+"</a></li>")
        out.append("</ol>")
    out.append('<h3>Conclusão</h3><p><a href="'+html.escape(conclusion_url,quote=True)+'">'+html.escape(M["conclusion_title"])+"</a></p>")
    return "\n".join(out)

def main():
    md=base64.b64decode(env("CONCLUSION_MARKDOWN_B64")).decode("utf-8")
    if not md.lstrip().startswith("# As Ladainhas de Nossa Senhora") or "## Um caminho com Maria até Cristo" not in md:
        raise RuntimeError("O texto integral da conclusão não corresponde ao título final esperado.")
    conclusion_body=markdown_html(md)
    token,blog=auth()
    posts=list_all(blog,"posts",token);pages=list_all(blog,"pages",token)
    def match(items,title):return next((x for x in items if (x.get("title") or "").strip().casefold()==title.casefold()),None)
    c=match(posts,M["conclusion_title"])
    if c:c=read(blog,"posts",c,token)
    c=save(blog,"posts",token,M["conclusion_title"],conclusion_body,c,LABELS)
    print("Conclusão confirmada pela API: "+c["title"]);print("URL: "+c["url"])
    items=[M["opening"],*M["invocation_posts"],{"title":M["conclusion_title"],"url":c["url"]}]
    page=match(pages,M["index_title"])
    if page:page=read(blog,"pages",page,token)
    page=save(blog,"pages",token,M["index_title"],index_html(M["invocation_posts"],c["url"]),page)
    print("Índice confirmado pela API: "+page["title"]);print("URL: "+page["url"])
    changed=0
    for i,item in enumerate(items):
        current=match(posts,item["title"])
        if not current:raise RuntimeError("Artigo da série não localizado: "+item["title"])
        current=read(blog,"posts",current,token)
        if current.get("url")!=item["url"]:raise RuntimeError("A URL da API diverge da URL confirmada: "+item["title"])
        body=with_nav(current.get("content",""),nav(items[i-1] if i else None,page["url"],items[i+1] if i+1<len(items) else None))
        if body!=current.get("content",""):
            verified=save(blog,"posts",token,item["title"],body,current)
            changed+=1
            print("Navegação confirmada: "+verified["title"]+" | "+verified["url"])
        else:print("Navegação já confirmada: "+current["title"]+" | "+current["url"])
    print(f"Concluído: 1 conclusão, 1 página-índice e {len(items)} artigos verificados; {changed} navegações aplicadas.")
if __name__=="__main__":
    try:main()
    except Exception as e:
        print("Falha: "+str(e),file=sys.stderr);sys.exit(1)
