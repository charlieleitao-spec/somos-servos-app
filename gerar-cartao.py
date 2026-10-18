#!/usr/bin/env python3
"""Gera o cartão compartilhável (PNG 1080x1350) do santo do dia.
Uso: python3 gerar-cartao.py [MM-DD|--todos] --dir <pasta-do-santoral> --emblema <arquivo.png> [--out saida]
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
    a = ap.parse_args(argv)
    hoje = datetime.now(ZoneInfo("America/Sao_Paulo"))
    mes, dia = map(int, (a.chave or hoje.strftime("%m-%d")).split("-")) if not a.todos else (0, 0)
    chave = f"{mes:02d}-{dia:02d}"
    with open(os.path.join(a.dir, "santoral.json"), encoding="utf-8") as f:
        dados = json.load(f)
    if a.todos:
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
    if not os.path.isfile(a.emblema):
        raise FileNotFoundError("Emblema oficial OSM não encontrado: " + a.emblema)
    img = Image.new("RGB", (W, H), FUNDO)
    d = ImageDraw.Draw(img)
    d.rectangle([40, 40, W - 41, H - 41], outline=OURO, width=3)
    d.rectangle([56, 56, W - 57, H - 57], outline=(70, 58, 38), width=1)
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
    if y > 920:
        raise ValueError(f"Título muito longo para o cartão: {titulo}")
    d.line([W/2 - 40, y, W/2 + 40, y], fill=OURO, width=2)
    y += 50
    fc = fonte(36)
    for l in quebrar(d, trecho(s.get("bio", "")), fc, W - 220):
        if y + 56 > H - 245:
            raise ValueError(f"Biografia excede a área útil do cartão: {titulo}")
        centro(d, y, l, fc, (214, 205, 190))
        y += 56

    centro(d, H - 190, "ORDEM DOS SERVOS DE MARIA", fonte(30), SUAVE)
    centro(d, H - 140, LINK, fonte(30, True), OURO)

    os.makedirs(a.out, exist_ok=True)
    img.save(os.path.join(a.out, f"cartao-{chave}.png"), optimize=True)
    with open(os.path.join(a.out, f"cartao-{chave}.txt"), "w", encoding="utf-8") as f:
        f.write(f"{titulo} — {dia} de {MESES[mes-1]}\n\n{trecho(s.get('bio',''))}\n\nLiturgia completa do dia: https://{LINK}/\n")
    print(f"Gerado: cartao-{chave}.png ({titulo})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
