"""Confere o código e promove o APK 1.0.5 aceito no A56 sem recompilá-lo."""
import argparse
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

APPROVED = '69585268cc4f5e6245d043e7100f6a0ba91f8290'
SHA256 = 'b6f17ba97136d656ac2cad4ce3fb19433dae35d3603f573bb34ccafb1c942970'
WEB_FILES = 'index.html recursos.html pesquisa-bibliografica.html pesquisa-imagens.html pesquisa-historica.html referencias-salvas.html referencias-salvas.js percurso-servita.html aprofundamento-servita.html comunidades-servitas.html percurso-servita.pdf recursos-offline.js app.js styles.css manifest.webmanifest service-worker.js icon-192.png icon-512.png icon.svg'.split()
ROOTS = ['cartoes', 'assets', 'data']
# O feed é atualizado automaticamente; o APK conserva a cópia já aceita.
MUTABLE_FEEDS = {'data/noticias-igreja.json'}

def approved(path):
    return subprocess.check_output(['git', 'show', f'{APPROVED}:{path}'])

def source_paths():
    dirs = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', APPROVED, *ROOTS], text=True).splitlines()
    return WEB_FILES + dirs

def verify_source():
    paths = source_paths()
    for p in paths + ['android-src/MainActivity.java', 'capacitor.config.json', 'scripts/configure-android-release.py', 'package.json', 'package-lock.json']:
        assert Path(p).is_file(), f'Arquivo aprovado ausente: {p}'
        if p not in MUTABLE_FEEDS:
            assert Path(p).read_bytes() == approved(p), f'Código diferente do APK aceito: {p}'
    for root in ROOTS:
        expected = {p for p in paths if p.startswith(root+'/')}
        actual = {p.as_posix() for p in Path(root).rglob('*') if p.is_file()}
        assert actual == expected, f'Arquivos adicionados ou removidos: {root}'
    assert json.loads(Path('package.json').read_text())['version'] == '1.0.5'
    print('PASS: código, dependências, identidade e materiais do APK aprovado preservados; feed automático da main mantido.')

def verify_apk(path):
    assert hashlib.sha256(path.read_bytes()).hexdigest() == SHA256, 'APK diferente do arquivo aceito no A56'
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None
        for p in source_paths():
            assert z.read('assets/public/'+p) == approved(p), f'Arquivo empacotado diferente do aprovado: {p}'
        assert len([n for n in z.namelist() if n.startswith('assets/public/cartoes/cartao-') and n.endswith('.png')]) == 32
    print('PASS: APK idêntico ao aceito no A56; arquivos web e 32 cartões conferidos.')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--apk', type=Path)
    args = parser.parse_args()
    verify_source()
    if args.apk:
        verify_apk(args.apk)
