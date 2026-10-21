#!/usr/bin/env python3
"""Persiste só a auditoria, sem incluir cartões ou sobrescrever commits concorrentes."""
import csv
import json
import os
from pathlib import Path
import subprocess
import tempfile


def git(*args, cwd=None):
    return subprocess.run(['git', *args], cwd=cwd, check=True, capture_output=True, text=True)


def main():
    pending = Path('.publicacoes-pendentes.jsonl')
    if not pending.exists():
        return
    rows = [json.loads(line) for line in pending.read_text(encoding='utf-8').splitlines()]
    branch = os.environ['GITHUB_REF_NAME']
    git('check-ref-format', '--branch', branch)
    with tempfile.TemporaryDirectory(prefix='publicacoes-') as temp:
        git('init', temp)
        git('remote', 'add', 'origin', git('remote', 'get-url', 'origin').stdout.strip(), cwd=temp)
        # Reutiliza a autenticação configurada por checkout sem imprimir seu valor.
        auth = subprocess.run(['git', 'config', '--get', 'http.https://github.com/.extraheader'], capture_output=True, text=True)
        if auth.returncode == 0:
            git('config', 'http.https://github.com/.extraheader', auth.stdout.strip(), cwd=temp)
        git('config', 'user.name', 'github-actions[bot]', cwd=temp)
        git('config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com', cwd=temp)
        for attempt in range(3):
            git('fetch', '--depth=1', 'origin', branch, cwd=temp)
            git('checkout', '-B', 'audit-log', 'FETCH_HEAD', cwd=temp)
            path = Path(temp) / 'publicacoes.csv'
            header = not path.exists() or path.stat().st_size == 0
            with path.open('a', encoding='utf-8', newline='') as stream:
                writer = csv.writer(stream)
                if header:
                    writer.writerow(['data', 'tipo', 'URL', 'status'])
                for row in rows:
                    writer.writerow([row['data'], row['tipo'], row['url'], row['status']])
            git('add', '--', 'publicacoes.csv', cwd=temp)
            git('commit', '-m', f'Registrar publicação {os.getenv("GITHUB_RUN_ID", "manual")} [skip ci]', cwd=temp)
            try:
                git('push', 'origin', f'HEAD:refs/heads/{branch}', cwd=temp)
                print('publicacoes.csv salvo com [skip ci].')
                return
            except subprocess.CalledProcessError:
                if attempt == 2:
                    raise RuntimeError('Não foi possível salvar publicacoes.csv após 3 tentativas; consulte o artefato de auditoria.') from None


if __name__ == '__main__':
    main()
