#!/usr/bin/env python3
"""Gera o cartão compartilhável (PNG 1080x1350) do santo do dia.
Uso: python3 gerar-cartao.py [MM-DD|--todos] --dir <pasta-do-santoral> --emblema <arquivo.png> [--out saida] [--post-url URL]
Saídas: <out>/cartao-MM-DD.png; com --post-url, também .txt (legenda para colar).
Sem URL real, não produz legenda incompleta. --todos gera somente os PNGs.
Não reescreve o texto da fonte: usa apenas o começo da memória (bio), cortado em fim de frase."""
import argparse, json, os, re, sys
from datetime import datetime
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw, ImageFont

LINK = "charlieleitao-spec.github.io/hoje-familia-servita"
LIMITE_TRECHO = 140
MESES = ["janeiro","fevereiro","março","abril","maio","junho","julho","agosto","setembro","outubro","novembro","dezembro"]
W, H = 1080, 1350
FUNDO, CREME, OURO, SUAVE = (250, 247, 240), (23, 59, 103), (151, 115, 49), (104, 108, 112)
FONTES = ["/usr/share/fonts/truetype/dejavu/DejaVuSerif{}.ttf", "/usr/share/fonts/dejavu/DejaVuSerif{}.ttf"]

def fonte(tam, negrito=False):
    for modelo in FONTES:
        p = modelo.format("-Bold" if negrito else "")
        if os.path.exists(p):
            return ImageFont.truetype(p, tam)
    return ImageFont.load_default()

# ---- ADAPTADOR: esquema do santoral.json (lista com day, month, title, bio) ----
def achar(santoral, mes, dia):
    """Localiza a celebração na lista day/month/title/bio do santoral OSM."""
    if not isinstance(santoral, list):
        return None
    for item in santoral:
        if not isinstance(item, dict):
            continue
        try:
            if int(item.get("month", 0)) == mes and int(item.get("day", 0)) == dia:
                return item
        except (TypeError, ValueError):
            continue
    return None
# --------------------------------------------------------------------------------

def trecho(bio, limite=LIMITE_TRECHO):
    t = " ".join(str(bio).split())
    if t.startswith("*"):  # remove a linha de datas (* nascimento † morte, local, UF)
        t = re.sub(r"^\*.*?†.*?\b[A-Z]{2}\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕ])", "", t, count=1)
    t = t.strip()
    if len(t) <= limite:
        return t
    # Não confundir iniciais e abreviações com o fim de uma frase.
    finais = []
    for m in re.finditer(r'[.!?](?:[”"\u2019])?(?=\s|$)', t):
        palavra = t[:m.start()+1].split()[-1]
        if re.fullmatch(r'[A-Za-zÀ-ÿ]\.', palavra) or palavra.lower() in {'frei.', 'sr.', 'sra.', 'dr.', 'dra.', 'cf.', 'etc.'}:
            continue
        if m.end() <= limite:
            finais.append(m.end())
    if finais:
        return t[:finais[-1]].strip()
    # Se a primeira frase já exceder o limite, preservar palavras inteiras.
    palavras = t[:limite+1].rsplit(' ', 1)
    return palavras[0].rstrip(' ,;:') if len(palavras) > 1 else ''

def legenda(titulo, grau, data, post_url):
    from urllib.parse import urlparse
    if urlparse(post_url).scheme not in ('https', 'http') or not urlparse(post_url).netloc:
        raise ValueError('Informe a URL real do post do dia em --post-url')
    cabecalho = ' · '.join(x for x in (titulo, grau, data) if x)
    return (f'{cabecalho}\n\nConheça esta memória da família servita e reze conosco.\n\n'
            f'Post do dia: {post_url}\nHoje na Família Servita: https://{LINK}/\n')

def quebrar(draw, texto, fnt, largura):
    linhas, atual = [], ""
    for pal in texto.split():
        teste = (atual + " " + pal).strip()
        if draw.textlength(teste, font=fnt) <= largura:
            atual = teste
        else:
            if atual: linhas.append(atual)
            atual = pal
    return linhas + ([atual] if atual else [])

def centro(draw, y, texto, fnt, cor):
    w = draw.textlength(texto, font=fnt)
    draw.text(((W - w) / 2, y), texto, font=fnt, fill=cor)

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("chave", nargs="?", help="MM-DD ou --todos")
    ap.add_argument("--todos", action="store_true", help="Gera cartões para todas as celebrações")
    ap.add_argument("--emblema", required=True, help="PNG oficial do emblema OSM fornecido pelo usuário")
    ap.add_argument("--dir", default=".")
    ap.add_argument("--out", default="saida")
    ap.add_argument("--post-url", help="URL real do post do dia; sem ela, gera apenas o PNG, sem inventar link")
    a = ap.parse_args(argv)
    hoje = datetime.now(ZoneInfo("America/Sao_Paulo"))
    mes, dia = map(int, (a.chave or hoje.strftime("%m-%d")).split("-")) if not a.todos else (0, 0)
    chave = f"{mes:02d}-{dia:02d}"
    with open(os.path.join(a.dir, "santoral.json"), encoding="utf-8") as f:
        dados = json.load(f)
    if a.todos:
        if a.post_url:
            raise ValueError('--post-url é específico de um dia; não use com --todos')
        if not isinstance(dados, list):
            raise ValueError("santoral.json deve conter uma lista de celebrações")
        chaves = set()
        for item in dados:
            if not isinstance(item, dict):
                continue
            mm, dd = int(item["month"]), int(item["day"])
            if (mm, dd) in chaves:
                raise ValueError(f"Data duplicada no santoral: {mm:02d}-{dd:02d}")
            chaves.add((mm, dd))
            main([f"{mm:02d}-{dd:02d}", "--dir", a.dir, "--out", a.out, "--emblema", a.emblema])
        print(f"{len(chaves)} cartões gerados com o santoral oficial")
        return 0
    s = achar(dados, mes, dia)
    if not s:
        print(f"Sem celebração para {chave}; nenhum cartão gerado.")
        return 0

    titulo = s.get("title") or s.get("name")
    grau = str(s.get('grau') or '').strip()
    grau_exibido = {'comemoracao': 'Comemoração', 'memoria': 'Memória',
                    'memoria_facultativa': 'Memória facultativa',
                    'festa': 'Festa', 'solenidade': 'Solenidade'}.get(grau, grau)
    data = f"{dia} de {MESES[mes-1]}"
    texto_legenda = legenda(titulo, grau_exibido, data, a.post_url) if a.post_url else None
    if not os.path.isfile(a.emblema):
        raise FileNotFoundError("Emblema oficial OSM não encontrado: " + a.emblema)
    img = Image.new("RGB", (W, H), FUNDO)
    d = ImageDraw.Draw(img)
    d.rectangle([40, 40, W - 41, H - 41], outline=OURO, width=3)
    d.rectangle([56, 56, W - 57, H - 57], outline=(224, 214, 195), width=1)
    emblema = Image.open(a.emblema).convert("RGBA")
    emblema.thumbnail((110, 110), Image.Resampling.LANCZOS)
    img.paste(emblema, ((W - emblema.width)//2, 72), emblema)

    centro(d, 188, "SANTORAL SERVITA", fonte(30), OURO)
    centro(d, 238, f"{dia} de {MESES[mes-1]}", fonte(42), CREME)
    d.line([W/2 - 60, 306, W/2 + 60, 306], fill=OURO, width=3)

    tam = 84
    while tam > 44:  # reduz a fonte até o título caber em 4 linhas
        ft = fonte(tam, True)
        linhas = quebrar(d, titulo, ft, W - 200)
        if len(linhas) <= 3:
            break
        tam -= 4
    y = 350
    for l in linhas:
        centro(d, y, l, ft, CREME)
        y += int(tam * 1.3)

    y += 25
    if grau_exibido:
        fg = fonte(32)
        if d.textlength(grau_exibido, font=fg) > W - 200:
            raise ValueError('Grau excede a largura do cartão')
        centro(d, y, grau_exibido, fg, OURO)
        y += 65
    if y > 920:
        raise ValueError(f"Título muito longo para o cartão: {titulo}")
    d.line([W/2 - 40, y, W/2 + 40, y], fill=OURO, width=2)
    y += 50
    fc = fonte(36)
    resumo = trecho(s.get('bio', ''))
    linhas_resumo = quebrar(d, resumo, fc, W - 220)
    for limite in range(LIMITE_TRECHO - 1, 0, -1):
        if len(linhas_resumo) <= 3 and all(d.textlength(l, font=fc) <= W - 220 for l in linhas_resumo):
            break
        resumo = trecho(s.get('bio', ''), limite)
        linhas_resumo = quebrar(d, resumo, fc, W - 220)
    for l in linhas_resumo:
        if y + 56 > H - 245:
            raise ValueError(f"Biografia excede a área útil do cartão: {titulo}")
        centro(d, y, l, fc, (65, 76, 86))
        y += 56

    centro(d, H - 160, "ORDEM DOS SERVOS DE MARIA", fonte(30), SUAVE)

    os.makedirs(a.out, exist_ok=True)
    img.save(os.path.join(a.out, f"cartao-{chave}.png"), optimize=True)
    caminho_legenda = os.path.join(a.out, f"cartao-{chave}.txt")
    if texto_legenda:
        with open(caminho_legenda, 'w', encoding='utf-8') as f:
            f.write(texto_legenda)
    else:
        if os.path.exists(caminho_legenda):
            os.remove(caminho_legenda)
        print('Legenda pendente: informe --post-url com o endereço real do post do dia.')
    print(f"Gerado: cartao-{chave}.png ({titulo})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
