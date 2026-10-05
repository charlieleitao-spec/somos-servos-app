#!/usr/bin/env python3
"""Gera o cartão compartilhável (PNG 1080x1350) do santo do dia.
Uso: python3 scripts/gerar-cartao.py [MM-DD] [--dir www/data] [--out saida]
Saídas: <out>/cartao-MM-DD.png e <out>/cartao-MM-DD.txt (legenda para colar).
Não reescreve o texto da fonte: usa apenas o começo da memória (bio), cortado em fim de frase."""
import argparse, json, os, re, sys
from datetime import datetime
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw, ImageFont

LINK = "charlieleitao-spec.github.io/hoje-familia-servita"
MESES = ["janeiro","fevereiro","março","abril","maio","junho","julho","agosto","setembro","outubro","novembro","dezembro"]
W, H = 1080, 1350
FUNDO, CREME, OURO, SUAVE = (20, 17, 15), (244, 236, 222), (196, 160, 98), (170, 160, 146)
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

def trecho(bio, limite=230):
    t = " ".join(str(bio).split())
    if t.startswith("*"):  # remove a linha de datas (* nascimento † morte, local, UF)
        t = re.sub(r"^\*.*?†.*?\b[A-Z]{2}\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕ])", "", t, count=1)
    frases = re.split(r"(?<=[.!?])\s+", t)
    saida = ""
    for f in frases:
        if saida and len(saida) + len(f) + 1 > limite:
            break
        saida = (saida + " " + f).strip()
        if len(saida) >= limite * 0.55:
            break
    return saida

def quebrar(draw, texto, fnt, largura):
    linhas, atual = [], ""
    for pal in texto.split():
        teste = (atual + " " + pal).strip()
        if draw.textlength(teste, font=fnt) <= largura:
            atual = teste
        else:
            linhas.append(atual); atual = pal
    return linhas + ([atual] if atual else [])

def centro(draw, y, texto, fnt, cor):
    w = draw.textlength(texto, font=fnt)
    draw.text(((W - w) / 2, y), texto, font=fnt, fill=cor)

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("chave", nargs="?")
    ap.add_argument("--dir", default=".")
    ap.add_argument("--out", default="saida")
    a = ap.parse_args(argv)
    hoje = datetime.now(ZoneInfo("America/Sao_Paulo"))
    mes, dia = map(int, (a.chave or hoje.strftime("%m-%d")).split("-"))
    chave = f"{mes:02d}-{dia:02d}"
    with open(os.path.join(a.dir, "santoral.json"), encoding="utf-8") as f:
        s = achar(json.load(f), mes, dia)
    if not s:
        print(f"Sem celebração para {chave}; nenhum cartão gerado.")
        return 0

    titulo = s.get("title") or s.get("name")
    img = Image.new("RGB", (W, H), FUNDO)
    d = ImageDraw.Draw(img)
    d.rectangle([40, 40, W - 41, H - 41], outline=OURO, width=3)
    d.rectangle([56, 56, W - 57, H - 57], outline=(70, 58, 38), width=1)

    centro(d, 110, "HOJE NA FAMÍLIA SERVITA", fonte(30), OURO)
    centro(d, 175, f"{dia} de {MESES[mes-1]}", fonte(46), CREME)
    d.line([W/2 - 60, 250, W/2 + 60, 250], fill=OURO, width=3)

    tam = 84
    while tam > 44:  # reduz a fonte até o título caber em 4 linhas
        ft = fonte(tam, True)
        linhas = quebrar(d, titulo, ft, W - 200)
        if len(linhas) <= 4:
            break
        tam -= 4
    y = 310
    for l in linhas:
        centro(d, y, l, ft, CREME)
        y += int(tam * 1.3)

    y += 40
    d.line([W/2 - 40, y, W/2 + 40, y], fill=OURO, width=2)
    y += 50
    fc = fonte(36)
    for l in quebrar(d, trecho(s.get("bio", "")), fc, W - 220)[:9]:
        centro(d, y, l, fc, (214, 205, 190))
        y += 56

    centro(d, H - 190, "Leia a liturgia completa do dia", fonte(30), SUAVE)
    centro(d, H - 140, LINK, fonte(30, True), OURO)

    os.makedirs(a.out, exist_ok=True)
    img.save(os.path.join(a.out, f"cartao-{chave}.png"), optimize=True)
    with open(os.path.join(a.out, f"cartao-{chave}.txt"), "w", encoding="utf-8") as f:
        f.write(f"{titulo} — {dia} de {MESES[mes-1]}\n\n{trecho(s.get('bio',''))}\n\nLiturgia completa do dia: https://{LINK}/\n")
    print(f"Gerado: cartao-{chave}.png ({titulo})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
