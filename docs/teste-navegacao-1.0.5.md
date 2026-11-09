# Teste da navegação — Somos Servos 1.0.5

Base: `3d10cce77d104d4b64f5389f127b7500cede1883`, versão 1.0.4. A proposta 1.0.5 já existia no documento de arquivos completos, mas o código da main ainda continha o import de módulo sem bundler e não oferecia o acesso inicial a Recursos. Os ajustes foram aplicados sobre a base atual, preservando o restante do projeto.

O botão Voltar é registrado por `window.Capacitor.Plugins.App`. O callback usa `canGoBack` fornecido pelo WebView; quando falso, chama `exitApp`. As falhas de registro e callback são tratadas. A navegação em páginas locais também conta com links explícitos de retorno.

O teste assinado usa versionName `1.0.5`, versionCode `1000005` e arquivo `Somos-Servos-1.0.5-teste.apk`. O workflow específico da branch compara o certificado com a versão oficial 1.0.4 e confere pacote, permissões finais e igualdade dos arquivos incluídos. Não publica release ou tag, não altera a galeria pública e não executa ações do Blogger. A chave permanece apenas no ambiente de compilação.

Verificações de código: `test_android_back.cjs`, `test_service_worker.cjs`, sintaxe e diff-check. A conferência em navegador usa um blog simulado e Service Worker real; verifica o botão Recursos em três larguras e, sem conexão, navegação para Recursos, galeria, retorno e percurso HTML. A contagem das 32 entradas da galeria no navegador não equivale a testar os PNGs offline na PWA. No APK, todos os arquivos locais são conferidos byte a byte.

## Conferência no A56

Instalar o APK de teste sobre a versão oficial, sem desinstalar. Navegar entre artigos reais do blog e usar o botão físico Voltar; na raiz, conferir o encerramento. Abrir Recursos, cartões e percurso com conexão e em modo avião. Usar os links de retorno e conferir a abertura externa dos feeds.

Os testes de código e navegador não substituem esta observação no WebView Android. A validação física permanece pendente até o relato do usuário. Não foi implementado o salvamento de artigos do blog para leitura offline nesta etapa.

## Compilação de teste entregue

Execução concluída com sucesso: https://github.com/charlieleitao-spec/somos-servos-app/actions/runs/42597110354

- Commit compilado: `69585268cc4f5e6245d043e7100f6a0ba91f8290`.
- Arquivo: `Somos-Servos-1.0.5-teste.apk`; tamanho: 6.212.803 bytes.
- SHA-256: `b6f17ba97136d656ac2cad4ce3fb19433dae35d3603f573bb34ccafb1c942970`.
- Certificado SHA-256: `b2cda5dccd59922dfef15d45ac8f61a34c99a44c5787902243b164b28f0f4553`, igual ao APK oficial 1.0.4.
- As permissões mescladas são idênticas às do APK oficial. INTERNET é a única permissão da plataforma Android; a permissão interna de receptor gerada pelo AndroidX já existia na versão anterior.
- Pacote `br.com.somosservos.app`, versionName `1.0.5`, versionCode `1000005` e 32 PNGs conferidos no APK baixado. A integridade do arquivo foi comparada ao SHA-256 gerado pelo pipeline.
- Testes de Voltar com ponte simulada, cache, cartões e navegação em navegador passaram. Capturas de 320 px online/offline foram inspecionadas. O blog no teste de navegador foi simulado.

A conferência no A56 e o aceite pelo usuário permanecem pendentes. Nenhuma integração à main, tag ou release foi feita nesta etapa; o Blogger não foi modificado.
