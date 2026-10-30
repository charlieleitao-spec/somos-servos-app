# Integração do Caminho Servita 1.0.4

## Escopo

Atualizar o cartão existente do Caminho Servita em Recursos da Família Servita, sem compilar outro APK, alterar o aplicativo Caminho ou criar uma nova versão. Reutiliza o arquivo 1.0.4 publicado e aprovado no A56.

## Estado examinado em 30/10/2026

| Projeto | Revisão examinada | Resultado no código |
| --- | --- | --- |
| Caminho Servita | `9b73f07855d08735d804042a7ed5f8f2971e21d1` | Fontes inclui Liturgia OSM, Hoje na Família Servita, Somos Servos e Biblioteca Servita; informa que páginas externas precisam de conexão. |
| Liturgia OSM | `3c94a4447bc66e2e9a9a4a1f00863f478b37afb4` | Menu aponta para a página Aplicativos Servitas do Blogger, na âncora `caminho-servita-app`, e para Recursos da Família Servita. |
| Hoje na Família Servita | `02eafe90ace815894177f9892f1ddb646ff45765` | Rodapé aponta para a mesma página do Blogger e para Recursos da Família Servita. |
| Somos Servos | `62f28448268b2678945171716a3b4519262bba75` | Recursos ainda oferece APK 1.0.0 e o endereço web anterior; ambos são atualizados nesta branch. |

A inspeção dos repositórios confirma o destino dos links no código; não confirma, por si só, o conteúdo de todas as instalações anteriores. A página publicada do Blogger não foi recuperada nesta revisão. A conferência de seu cartão e da âncora permanece pendente; seu conteúdo não foi alterado.

## Correção preparada

- Download público de Recursos aponta para `downloads/Caminho-Servita-1.0.4.apk`, junto com o arquivo de checksum.
- Endereço web canônico: https://caminho-servita.frcharlieosm.chatgpt.site . A indicação de acesso restrito permanece.
- Apresentação informa sete encontros iniciais e quatro de aprofundamento, além de orientar a atualização sem desinstalar.
- O arquivo público anterior 1.0.0 permanece, preservando links antigos.
- Cache interno do Somos Servos passa de v58 a v59 para atualizar a página offline; o APK não é pré-carregado. Isso não altera a numeração nem publica uma versão Android do Somos Servos.
- Estrutura visual, seções, catálogo da Biblioteca e demais cartões permanecem iguais.

APK: 1.151.469 bytes, SHA-256 `3fd67fd4e9c708fe2f7cd280a325fed597ec12c8a3e49e2ffc6a2f8e12589ca6`. Certificado original do Caminho preservado. É o mesmo arquivo da release v1.0.4 e do teste no A56.

## Validação

- Sintaxe do service worker aprovada.
- Teste existente `node tests/test_service_worker.cjs` aprovado: atualização online, fallback offline, timeout, erros e preservação de caches de outros projetos.
- Confirmado que a alteração HTML está restrita ao cartão Caminho Servita.
- Hash e tamanho do APK conferidos com a release 1.0.4.
- Validações da PR devem ser registradas na descrição antes da integração.

## Próximo conjunto, sem versões pequenas sucessivas

Conferir o cartão público do Blogger e sua âncora, padronizar os acessos entre os aplicativos e concluir a avaliação específica com TalkBack no A56. Agrupar esses ajustes antes de propor outra atualização Android. Os onze encontros existentes não são reescritos nesta etapa.
