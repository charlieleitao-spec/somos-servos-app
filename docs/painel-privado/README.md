# Implantação privada — Painel Somos Servos

Este diretório contém apenas instruções de preparação, **sem dados administrativos**.

## Segurança e arquitetura

- Este repositório é público. Branches, commits e arquivos nele também são públicos.
- NÃO publicar aqui o painel administrativo completo, arquivos JSON exportados, diagnósticos internos, rascunhos não publicados, tokens, credenciais ou dados pessoais.
- Hospedar a interface administrativa em **repositório privado separado** e ambiente com autenticação real e autorização por usuário (por exemplo, provedor de identidade com controle de acesso no servidor).
- A autenticação deve proteger também APIs, dados e arquivos, não apenas esconder a interface no navegador.
- Desabilitar indexação, usar HTTPS e proteger segredos no servidor.
- Não usar GitHub Pages público como mecanismo de proteção.
- Antes de migrar registros locais, revisar o conteúdo e confirmar destino privado e política de backup.

## Regras editoriais

- Rascunho, revisão, autorização, publicação e confirmação são estados distintos.
- Nunca publicar automaticamente sem autorização explícita registrada.
- Verificar URL e identificador do post antes de criar nova publicação; atualizar o registro existente para evitar duplicações.
- Não alterar workflows de produção nem a branch main durante esta preparação.

## Etapas pendentes

1. Criar repositório privado dedicado ao painel, separado deste repositório público.
2. Configurar autenticação e controle de acesso de ponta a ponta.
3. Migrar o HTML do painel e validar suas dependências sem inserir dados sensíveis no histórico Git.
4. Implementar persistência segura e backup (armazenamento local isolado é apenas provisório).
5. Validar em ambiente de teste; publicar somente após aprovação explícita.

Status: **preparação técnica; implantação privada ainda não realizada**.
