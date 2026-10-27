# Biblioteca e Formação Servita — implantação no Blogger

Publicada em 27/10/2026:
https://somosservos.blogspot.com/p/biblioteca-e-formacao-servita.html

## Arquivos e implantação

- `biblioteca-formacao-servita.html`: corpo publicado, com as cinco seções preservadas. O Blogger fornece o título, evitando duplicação.
- `menu-biblioteca-formacao-servita.html`: gadget publicado. Mantém os dez destinos principais; Maria e Documentos e História usam `details`/`summary` nativos, com a página principal como primeiro destino.
- Biblioteca em Documentos e História; Escola de Mariologia Servita também em Maria. Demais destinos preservados.
- Georgia e cores do tema preservadas. CSS restrito às novas classes do gadget, com links separados e altura mínima de 44 px. Nenhuma substituição do XML do tema.
- Sem links diretos de PDF externos. Acesso orientado ao acervo offline Liturgia OSM 4.9.120 pela página Aplicativos Servitas.

## Verificações concluídas

- Os cinco destinos retornaram HTTP 200 e títulos correspondentes: Constituições e Regra, Escola de Mariologia, Ladainhas, Linha do Tempo e Aplicativos Servitas.
- Página pública inspecionada no navegador de computador: cinco seções, índice e tipografia.
- Submenus Maria e Documentos e História abertos e destinos conferidos. Uma regra antiga do tema juntava links; corrigida exclusivamente nas novas classes e confirmada visualmente.
- Prévia Smartphone do próprio Blogger utilizada: conteúdo, índice, quebra de linhas, abertura do menu e ambos os submenus conferidos visualmente. Escola de Mariologia e Biblioteca visíveis nos grupos corretos; links separados, sem sobreposição na prévia.

A verificação móvel foi realizada na prévia do Blogger, sem declarar teste novo em aparelho físico ou no Samsung A56.

Nenhuma alteração no aplicativo, workflows ou APK; nenhum teste de aplicativo repetido; nenhum outro projeto modificado. A publicação no Blogger independe do merge desta PR.

## Revisão dos três percursos — 27/10/2026

Publicados: Conhecer os Servos de Maria; Viver o carisma servita; Aprofundar a formação. Atalhos disponíveis no início da Biblioteca; cinco seções originais preservadas.

Revisão final: 14 destinos distintos de leitura com HTTP 200; âncoras internas resolvidas; nenhum identificador duplicado. Na prévia Smartphone do Blogger, os três percursos foram inspecionados visualmente. Largura útil de 397 px, sem transbordamento horizontal; títulos, parágrafos e links dentro da área de leitura. Não foi realizado novo teste em aparelho físico.

## Roteiro de encontros — 27/10/2026

Publicado: https://somosservos.blogspot.com/p/roteiro-de-encontros-da-familia-servita.html

Fonte: `roteiro-encontros-familia-servita.html`. Seis encontros, dois por percurso, com leituras, oração, partilha e compromissos. Acesso acrescentado no início da Biblioteca; retorno à Biblioteca presente no roteiro. Ambos os links percorridos na página pública.

Verificação desta publicação: uma única seção de conteúdo; seis encontros e seis âncoras válidas; Georgia; nenhuma rolagem horizontal no computador (1363 px) nem na prévia Smartphone do Blogger (397 px úteis). Primeiro atalho do índice acionado na prévia móvel. Versão editável em DOCX entregue separadamente. Testes anteriormente aprovados do menu e do aplicativo não repetidos.
