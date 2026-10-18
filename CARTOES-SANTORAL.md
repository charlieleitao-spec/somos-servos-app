# Cartões do Santoral Servita

O gerador `gerar-cartao.py` utiliza o mesmo `santoral.json` do Liturgia OSM. Não mantenha uma cópia independente no repositório.

## Preparação

Baixe a versão atual de `www/data/santoral.json` do repositório `charlieleitao-spec/liturgia-osm` e coloque-a numa pasta local. Forneça o PNG original do emblema OSM enviado pelo responsável; **não substitua por emblema gerado por IA**.

```bash
python3 gerar-cartao.py --todos --dir /caminho/dados --emblema assets/emblema-osm-oficial.png --out cartoes
```

Para um cartão: `python3 gerar-cartao.py 10-25 --dir /caminho/dados --emblema assets/emblema-osm-oficial.png --out cartoes`.

Requer Python 3.9+ e Pillow. Os cartões são PNG 1080 × 1350, com legendas TXT.

O PNG original fornecido pelo responsável está em `assets/emblema-osm-oficial.png`, preservado sem alterações. Os 32 cartões foram gerados a partir da fonte canônica (SHA-256 `008871ac6dc24a25de92f3ec6a902b113e4a4f6a61a900578cd111794caa0d71`) e revisados em 18/10/2026.

Consulta e download: https://charlieleitao-spec.github.io/somos-servos-app/cartoes/
Nenhuma postagem automática no Blogger é realizada por este gerador.
