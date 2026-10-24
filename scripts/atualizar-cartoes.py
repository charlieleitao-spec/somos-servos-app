"""Rebuild the published gallery from the pinned canonical santoral; never publish Blogger posts."""
import importlib.util,json,html,urllib.request,tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('cartao',root/'gerar-cartao.py')
cartao=importlib.util.module_from_spec(spec);spec.loader.exec_module(cartao)
url='https://raw.githubusercontent.com/charlieleitao-spec/liturgia-osm/ef6a874dffcc94cf9d1a9eb3bbdaafa99d77517b/www/data/santoral.json'
with urllib.request.urlopen(url,timeout=60) as response: data=json.load(response)
with tempfile.TemporaryDirectory() as folder:
    Path(folder,'santoral.json').write_text(json.dumps(data,ensure_ascii=False))
    cartao.main(['--todos','--dir',folder,'--out',str(root/'cartoes'),'--emblema',str(root/'assets/emblema-osm-oficial.png')])
cards=[]
for item in data:
    month,day=int(item['month']),int(item['day'])
    key=f'{month:02d}-{day:02d}'
    title=item.get('title') or item['name']
    grade={'comemoracao':'Comemoração','memoria':'Memória','memoria_facultativa':'Memória facultativa','festa':'Festa','solenidade':'Solenidade'}.get(item.get('grau'),item.get('grau') or '')
    date=f'{day} de {cartao.MESES[month-1]}'
    heading=' · '.join(x for x in [title,grade,date] if x)
    caption=f'{heading}\n\nConheça esta memória da família servita e reze conosco.\n\nSomos Servos: https://somosservos.blogspot.com/\nHoje na Família Servita: https://charlieleitao-spec.github.io/hoje-familia-servita/\n'
    (root/f'cartoes/cartao-{key}.txt').write_text(caption,encoding='utf-8')
    safe=html.escape(title)
    cards.append(f'<article><h2>{safe}</h2><p>{day:02d}/{month:02d}</p><img src="cartao-{key}.png?v=2" alt="Cartão de {safe}" loading="lazy" width="1080" height="1350"><p><a href="cartao-{key}.png" download>Baixar imagem</a> · <a href="cartao-{key}.txt" download>Baixar legenda</a></p></article>')
page='<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Cartões do Santoral Servita</title><style>:root{font-family:Georgia,serif;color:#173b67;background:#faf7f0}body{max-width:850px;margin:auto;padding:24px;line-height:1.6}article{background:white;border:1px solid #ddd5c6;border-radius:12px;padding:20px;margin:20px 0}img{max-width:100%;height:auto}a{display:inline-block;min-height:44px;color:#173b67}h1{font-size:1.8rem}</style><header><h1>Cartões do Santoral Servita</h1><p>Trechos curtos, emblema oficial e links nas legendas. As legendas desta coleção levam ao blog e ao aplicativo; as dos posts diários levam à postagem correspondente.</p><a href="../recursos.html">Recursos da família servita</a></header><main>'+''.join(cards)+'</main></html>'
(root/'cartoes/index.html').write_text(page,encoding='utf-8')
from PIL import Image
images=list((root/'cartoes').glob('cartao-*.png'))
assert len(images)==32
for path in images:
    with Image.open(path) as image: assert image.size==(1080,1350),path
print('32 cartões e legendas atualizados e dimensões verificadas.')
