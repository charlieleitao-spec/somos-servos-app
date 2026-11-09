# Teste da navegação — Somos Servos 1.0.5

Base: `3d10cce77d104d4b64f5389f127b7500cede1883`, versão 1.0.4. A proposta 1.0.5 já existia no documento de arquivos completos, mas o código da main ainda continha o import de módulo sem bundler e não oferecia o acesso inicial a Recursos. Os ajustes foram aplicados sobre a base atual, preservando o restante do projeto.

O botão Voltar é registrado por `window.Capacitor.Plugins.App`. O callback usa `canGoBack` fornecido pelo WebView; quando falso, chama `exitApp`. As falhas de registro e callback são tratadas. A navegação em páginas locais também conta com links explícitos de retorno.

O teste assinado usa versionName `1.0.5`, versionCode `1000005` e arquivo `Somos-Servos-1.0.5-teste.apk`. O workflow específico da branch compara o certificado com a versão oficial 1.0.4 e confere pacote, permissões finais e igualdade dos arquivos incluídos. Não publica release ou tag, não altera a galeria pública e não executa ações do Blogger. A chave permanece apenas no ambiente de compilação.

Verificações de código: `test_android_back.cjs`, `test_service_worker.cjs`, sintaxe e diff-check. A conferência em navegador usa um blog simulado e Service Worker real; verifica o botão Recursos em três larguras e, sem conexão, navegação para Recursos, galeria, retorno e percurso HTML. A contagem das 32 entradas da galeria no navegador não equivale a testar os PNGs offline na PWA. No APK, todos os arquivos locais são conferidos byte a byte.

## Conferência no A56

Instalar o APK de teste sobre a versão oficial, sem desinstalar. Navegar entre artigos reais do blog e usar o botão físico Voltar; na raiz, conferir o encerramento. Abrir Recursos, cartões e percurso com conexão e em modo avião. Usar os links de retorno e conferir a abertura externa dos feeds.

Os testes de código e navegador não substituem esta observação no WebView Android. A validação física permanece pendente até o relato do usuário. Não foi implementado o salvamento de artigos do blog para leitura offline nesta etapa.
