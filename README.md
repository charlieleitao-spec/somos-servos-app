# Somos Servos

Aplicativo instalável do blog [Somos Servos da Virgem Gloriosa](https://somosservos.blogspot.com/).

## GitHub Pages

1. Em **Settings > Pages**, escolha **Deploy from a branch**.
2. Selecione a branch **main** e a pasta **/(root)**.
3. Abra [o aplicativo](https://charlieleitao-spec.github.io/somos-servos-app/) no Chrome e toque em **Instalar**.

O aplicativo mantém em cache os arquivos necessários para abrir sua interface. As postagens são carregadas do Blogger e exigem conexão com a internet. Quando não houver conexão, uma tela informa a situação e permite tentar novamente.

## APK Android

O fluxo [Build APK Somos Servos](https://github.com/charlieleitao-spec/somos-servos-app/actions/workflows/main.yml) compila automaticamente um APK de depuração para testes. O artefato fica disponível por tempo limitado na execução do Actions; ele não equivale a uma versão assinada para distribuição geral.

O fluxo [Release APK Somos Servos](https://github.com/charlieleitao-spec/somos-servos-app/actions/workflows/release-apk.yml) gera e publica uma versão estável, assinada com uma chave dedicada ao app. Configure os segredos e siga o procedimento em [BUILD-ANDROID.md](BUILD-ANDROID.md) antes de executar esse fluxo.
