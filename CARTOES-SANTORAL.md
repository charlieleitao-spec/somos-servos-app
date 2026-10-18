# Cartões do Santoral Servita

O gerador `gerar-cartao.py` utiliza o mesmo `santoral.json` do Liturgia OSM. Não mantenha uma cópia independente no repositório.

## Preparação

Baixe a versão atual de `www/data/santoral.json` do repositório `charlieleitao-spec/liturgia-osm` e coloque-a numa pasta local. Forneça o PNG original do emblema OSM enviado pelo responsável; **não substitua por emblema gerado por IA**.

```bash
python3 gerar-cartao.py --todos --dir /caminho/dados --emblema /caminho/emblema-osm-oficial.png --out cartoes
```

Para um cartão: `python3 gerar-cartao.py 10-25 --dir /caminho/dados --emblema /caminho/emblema-osm-oficial.png --out cartoes`.

Requer Python 3.9+ e Pillow. Os cartões são PNG 1080 × 1350, com legendas TXT. Revise os resultados antes de publicar. O PNG oficial não foi incluído neste PR porque o conector GitHub disponível não transportou o anexo binário; até sua inclusão, o gerador exige o arquivo local e falha claramente se ele estiver ausente. Nenhuma publicação automática é realizada.
