# Somos Servos — compilação Android

## Requisitos

- Node.js 22
- npm
- Android Studio e Android SDK atualizados
- JDK 21

O fluxo automático do GitHub Actions usa essas versões.

## Preparar e sincronizar

Na primeira preparação:

```bash
npm install
npm run android:init
npm run android:sync
```

Para abrir o projeto no Android Studio:

```bash
npm run android:open
```

## APK de teste

```bash
npm run android:debug
```

O arquivo será gerado em `android/app/build/outputs/apk/debug/app-debug.apk`. O fluxo **Build APK Somos Servos** também disponibiliza esse APK como artefato temporário do GitHub Actions. Essa compilação de depuração serve para testes e não é uma versão assinada para distribuição geral.

## Versão de distribuição

O identificador Android deste projeto é `br.com.somosservos.app`, e o nome exibido é **Somos Servos**.

Antes de distribuir uma versão release, configure no Gradle uma chave de assinatura própria e permanente. Guarde a chave e as senhas em local seguro, fora do repositório. Todas as versões futuras precisam usar uma assinatura compatível para que possam atualizar a instalação existente. Se a assinatura mudar, o Android exigirá a remoção da versão anterior antes da instalação.

O projeto inclui o comando `npm run android:release`, mas a distribuição só deve ocorrer depois da configuração e verificação da assinatura release.
