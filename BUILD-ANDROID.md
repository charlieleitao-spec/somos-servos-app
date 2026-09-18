# Liturgia OSM 4.4.0 — compilação Android

## Requisitos
- Node.js 22 ou compatível
- npm
- Android Studio atualizado
- Android SDK instalado
- JDK 17

## Primeira preparação
```bash
npm install
npm run android:init
npm run android:sync
```

## Abrir no Android Studio
```bash
npm run android:open
```

No Android Studio, aguarde o Gradle sincronizar e teste primeiro em um aparelho/emulador Android 16.

## Gerar APK de teste
```bash
npm run android:debug
```
O APK normalmente será criado em `android/app/build/outputs/apk/debug/app-debug.apk`.

## Gerar versão de distribuição
Antes de uma versão release, configure uma chave própria e permanente no Android Studio/Gradle. Não use uma chave diferente a cada versão; o Android só aceita atualizações do mesmo pacote quando a assinatura é compatível.

O identificador oficial deste projeto é:
`com.liturgia_osm.app`

Nome exibido:
`Liturgia OSM`

## Observação sobre atualização de APK antigo
Se um APK anterior de `com.liturgia_osm.app` foi assinado com outra chave (por exemplo, uma chave criada por ferramenta de terceiros), a nova versão não poderá ser instalada por cima dele. Nesse caso, é necessário desinstalar a versão antiga ou assinar a nova versão com a mesma chave original.
