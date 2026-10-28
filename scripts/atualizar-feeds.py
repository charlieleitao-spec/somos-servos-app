"""Atualiza manchetes oficiais; preserva a última lista válida por fonte."""
import concurrent.futures
import datetime as dt
import html
import json
import os
from pathlib import Path
import urllib.request
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

SOURCES = {
    "vatican": ("Vatican News", "https://www.vaticannews.va/pt.rss.xml", "https://www.vaticannews.va/pt.html", "vaticannews.va"),
    "cnbb": ("CNBB", "https://www.cnbb.org.br/feed/", "https://www.cnbb.org.br/ultimas-noticias/", "cnbb.org.br"),
    "crb": ("CRB Nacional", "https://crbnacional.org.br/feed/", "https://crbnacional.org.br/noticias/", "crbnacional.org.br"),
}
OUTPUT = Path(__file__).resolve().parents[1] / "data/noticias-igreja.json"


def parse_feed(xml, host):
    root = ET.fromstring(xml)
    items, seen = [], set()
    for entry in root.iter():
        if entry.tag.rsplit("}", 1)[-1] not in {"item", "entry"}:
            continue
        title, link = "", ""
        for child in entry:
            tag = child.tag.rsplit("}", 1)[-1]
            if tag == "title":
                title = " ".join(html.unescape("".join(child.itertext())).split())
            elif tag == "link" and child.get("rel", "alternate") == "alternate":
                link = (child.get("href") or child.text or "").strip()
        parsed = urlparse(link)
        if (title and parsed.scheme in {"http", "https"}
                and (parsed.hostname or "").removeprefix("www.") == host
                and link not in seen):
            items.append({"title": title, "link": link})
            seen.add(link)
        if len(items) == 3:
            break
    if not items:
        raise ValueError("Feed sem manchetes válidas")
    return items


def fetch_source(key):
    name, feed, page, host = SOURCES[key]
    request = urllib.request.Request(feed, headers={
        "User-Agent": "Mozilla/5.0 (compatible; SomosServosFeedReader/1.0)",
        "Accept": "application/rss+xml,application/xml,text/xml,*/*",
    })
    with urllib.request.urlopen(request, timeout=30) as response:
        xml = response.read(2_000_001)
    if len(xml) > 2_000_000:
        raise ValueError("Feed maior que o limite de leitura")
    return {"name": name, "page": page, "feed": feed,
            "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "items": parse_feed(xml, host)}


def main():
    data = json.loads(OUTPUT.read_text()) if OUTPUT.exists() else {"version": 1, "sources": {}}
    failures = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures = {key: pool.submit(fetch_source, key) for key in SOURCES}
        for key, future in futures.items():
            try:
                source = future.result()
                # Não altera a data nem cria commit se a lista continua igual.
                if data["sources"].get(key, {}).get("items") != source["items"]:
                    data["sources"][key] = source
                print(f"{key}: {len(source['items'])} manchetes verificadas")
            except Exception as error:
                print(f"{key}: {error}; mantendo última lista válida")
                failures.append(key)
    missing = [key for key in SOURCES if not data["sources"].get(key, {}).get("items")]
    if missing:
        raise SystemExit("Fontes ainda sem lista válida: " + ", ".join(missing))
    OUTPUT.parent.mkdir(exist_ok=True)
    temporary = OUTPUT.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, OUTPUT)
    if len(failures) == len(SOURCES):
        raise SystemExit("Nenhuma fonte pôde ser consultada; listas preservadas")


if __name__ == "__main__":
    main()
