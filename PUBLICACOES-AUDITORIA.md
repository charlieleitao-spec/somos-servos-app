# Auditoria do publicador Blogger

Mudança limitada à execução e à auditoria. Os dois publicadores originais, seu HTML,
o calendário, os graus, as datas e as 32 páginas não foram alterados.
`publication_run.py` envolve os publicadores existentes e mantém suas funções de
busca de duplicatas, incluindo posts publicados, agendados e rascunhos.
O diário mantém a política existente; o semanal continua criando apenas rascunhos.
Nenhuma nova publicação direta foi habilitada. Os horários cron permanecem iguais.

## Evidência por execução de cada publicador

- Verificação OAuth e leitura do blog antes da geração e de qualquer escrita no Blogger.
- `GITHUB_STEP_SUMMARY`: data/hora em São Paulo, tipo, título, ID e URL efetivamente
  retornados pela API (quando disponíveis), status e erro. Não imprime tokens,
  segredos ou a descrição livre devolvida pelo servidor OAuth.
- Post público novo: GET da URL retornada, seguindo redirecionamentos, exige HTTP 200.
  HTTP diferente, URL ausente ou falha de rede retorna código 1. Não há nova tentativa
  de criação de post. Duplicata LIVE também é verificada sem recriar post.
- Rascunho: preserva a confirmação de ID/título/marcador/estado pela API;
  status `rascunho_confirmado_api`. Não exige URL pública para um rascunho privado.
  Prévia: `previa_sem_publicacao`, sem POST para o Blogger.
- `publicacoes.csv`: data,tipo,URL,status; uma linha por invocação diária/semanal,
  inclusive prévia, ausência de celebração, duplicata e falha OAuth.
- Etapas finais `always()` preservam artefato e fazem commit `[skip ci]` na branch
  executada. Reaplicam apenas as linhas novas sobre a versão remota mais recente,
  sem push forçado ou inclusão de cartões. Falha do commit também deixa job vermelho.
- Cancelamento forçado, falha anterior ao início do publicador ou indisponibilidade
  do GitHub podem impedir o registro; não existe garantia de persistência nesses casos.

## Como testar sem publicar

1. Actions → Publicação diária Somos Servos → Run workflow → selecionar a branch do PR.
2. Manter `create_draft=false`, `create_weekly_draft=false`, `inventory_only=false`.
   Para a prévia semanal, marcar `run_weekly=true`. Nenhuma data litúrgica é editada.
3. Conferir Summary, log da autenticação, artefato `auditoria-publicacoes-*` e
   commit `[skip ci]` de `publicacoes.csv` nessa branch.
4. Testes locais: `python -m unittest -v test_publication_run.py` (8 testes com mocks).
   Cobrem HTTP não-200, OAuth inválido, supressão de dados sensíveis, duplicata,
   rascunho, prévia semanal e preservação de ID após erro de verificação pública.

## Diagnóstico inicial comprovado

Última execução com falha antes deste trabalho: #44, 2026-10-20T02:22:02Z,
https://github.com/charlieleitao-spec/somos-servos-app/actions/runs/39358504897
Log: `Falha: Autenticação OAuth respondeu HTTP 400.`
O código anterior descartava o corpo do erro; esse log não comprova invalid_grant.
O novo código mostra somente o código OAuth reconhecido, sem expor credenciais.
Google Cloud não ficou acessível no navegador desta sessão (Site Unavailable);
modo Teste/Produção não verificado.

## Recuperação OAuth — somente se o diagnóstico confirmar invalid_grant

Faça uma etapa por vez. Não cole nenhuma chave ou token na conversa.

1. No projeto que contém o cliente OAuth usado pelo publicador, abra Google Auth
   Platform → Público-alvo (Audience). Confira o status. Se estiver Em teste, use
   Publicar app para passar a Em produção. Não é publicação de posts no Blogger.
   Não crie outro projeto nem troque cliente. Se a opção estiver bloqueada, registre
   a mensagem mostrada antes de fazer novas configurações.
2. No mesmo cliente OAuth do tipo Web, confira o redirecionamento autorizado
   `https://developers.google.com/oauthplayground` (adicione somente se ausente).
   Abra o OAuth Playground do Google, engrenagem → Use your own OAuth credentials,
   e informe ali o Client ID e Client Secret desse cliente. Use acesso Offline.
3. Autorize apenas `https://www.googleapis.com/auth/blogger` com a conta que administra
   Somos Servos; em Step 2, Exchange authorization code for tokens. Copie o refresh
   token diretamente para o Secret do GitHub, sem compartilhá-lo em chat.
4. Repositório → Settings → Secrets and variables → Actions → atualize
   `BLOGGER_REFRESH_TOKEN`. Mantenha `BLOGGER_CLIENT_ID` e `BLOGGER_CLIENT_SECRET`
   do MESMO cliente. O workflow aceita o nome legado `BLOGGER_REFFRESH_TOKEN`,
   mas prioriza o correto `BLOGGER_REFRESH_TOKEN`; atualize o correto.
   `BLOGGER_BLOG_ID` é usado pelo inventário e não corrige o OAuth diário/semanal.
5. Execute novamente apenas a prévia. Um token novo em Produção evita a expiração
   específica de sete dias de Teste, mas não impede revogação ou outras invalidações.

Fontes oficiais:
- https://developers.google.com/identity/protocols/oauth2
- https://developers.google.com/identity/protocols/oauth2/production-readiness/overview
- https://developers.google.com/oauthplayground/

A confirmação do status do projeto e, se necessária, a autorização/renovação pessoal
são pendências do titular. Não é necessário enviar credenciais ao assistente.

## Resultado real da prévia manual

Execução #45 em 20/10/2026, 07:27 (São Paulo):
https://github.com/charlieleitao-spec/somos-servos-app/actions/runs/39407997158

- `DRY_RUN=true`, `WEEKLY_DRY_RUN=true`, `DRAFT=false`.
- Falha inicial comprovada: `Autenticação OAuth: HTTP 400 (invalid_grant).`
- Exit code 1 e execução vermelha, antes de chamar o publicador.
- Summary exibiu data, tipo diário e erro; título/ID/URL vazios porque nenhum post foi criado.
- Artefato de auditoria salvo; etapa de commit confirmou `publicacoes.csv salvo com [skip ci]`.
- Leitura do CSV remoto confirmou: `2026-10-20T07:27:02-03:00,diário,,erro`.
- 8 testes locais passaram, com chamadas de API simuladas.

Não comprovados: modo Teste/Produção do projeto, motivo específico da invalidação,
renovação do token, publicação real com HTTP 200 e criação real de rascunho semanal.
O semanal foi testado localmente com mocks; não foi disparado nesta execução real.
Não houve merge nem alteração de Secrets. O próximo passo do titular é conferir
Público-alvo no projeto OAuth; em seguida, renovar o token seguindo as etapas acima.
