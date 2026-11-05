# s21 — Integração de fontes de conteúdo

Verificação: 05/11/2026. Prioridade: baixa.

## Escopo implementado

Acessos externos à liturgia brasileira das Edições CNBB e à apresentação da Folhinha pela Editora Vozes, identificada como publicação de 2021. Os links exigem internet; nenhum conteúdo da Folhinha é importado, reproduzido ou armazenado offline. A página histórica não comprova a disponibilidade atual dos aplicativos da Folhinha.

As consultas já existentes à API comunitária Liturgia Diária v2 no Liturgia OSM e no Hoje na Família Servita são preservadas. Caminho Servita e Somos Servos oferecem acesso às fontes; não receberam consulta automática nem novo leitor de Missa.

Não foram alterados calendário OSM, decisões de datas, PDFs, ICS, dados pessoais, versões Android ou workflows. São Filipe Benizi permanece em 23 de agosto para o Brasil. Somente a identificação do cache dos arquivos da interface foi atualizada para distribuir os novos links em uma publicação futura.

## Verificação local

- Sintaxe JavaScript dos arquivos modificados conferida.
- Links presentes nos quatro projetos, com abertura externa e proteção noopener/noreferrer.
- Teste existente do Hoje: consulta sob demanda, data e ano exatos, cache apenas de referências, acesso sem rede, rejeição de resposta de outro ano, troca de data durante consulta e armazenamento bloqueado: passou.
- Auditoria geral do Liturgia OSM interrompida por divergência já existente: APP_VERSION 4.9.130 e package.json 4.9.131. Esta alteração não modifica nenhum dos dois números. A falha não foi corrigida neste registro.
- Nenhum teste no Samsung A56 ou compilação Android realizado nesta etapa.

## Limites e encaminhamento

API oficial da Folhinha, licença de reutilização, limites, procedência dos textos e autorização de armazenamento offline continuam sem comprovação. Confirmar diretamente com a Editora Vozes antes de qualquer importação automática. A leitura e a proposta não equivalem à homologação litúrgica completa de uma API independente.

Alteração preparada em branch separada. Publicação, release e workflows permanecem fora desta etapa; a autorização inicial para não disparar workflows foi preservada com commits [skip actions].

## Fontes

- https://liturgiadiaria.edicoescnbb.com.br/
- https://www.vozes.com.br/blog/folhinha-2022-publicacao-traz-curiosidades-e-evangelizacao-para-o-seu-dia-a-dia
- https://github.com/Dancrf/liturgia-diaria

Registro manual: s21. Situação: em andamento; integração dos acessos preparada, API Folhinha bloqueada até confirmação do fornecedor. O painel não foi atualizado automaticamente.
