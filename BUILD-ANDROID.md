# Somos Servos — compilação e publicação Android

## Requisitos

- Node.js 22
- npm
- Android Studio e Android SDK atualizados
- JDK 21

O GitHub Actions usa essas versões.

## APK de teste

```bash
npm install
npm run android:init
npm run android:sync
npm run android:debug
```

O arquivo de depuração fica em `android/app/build/outputs/apk/debug/app-debug.apk`. O fluxo **Build APK Somos Servos** também o disponibiliza para teste. Ele é assinado pela chave de depuração do Android e serve somente para testes.

## Preparar a assinatura estável

O identificador do pacote é `br.com.somosservos.app`. O release usa uma chave privada permanente exclusiva do Somos Servos. Não reutilize a chave de outro app, não a envie por mensagem e não a coloque no repositório.

1. Em um computador sob seu controle, gere um keystore dedicado. O JDK inclui o comando `keytool`; ele pedirá as senhas sem incluí-las no comando:

   ```bash
   keytool -genkeypair -v -keystore somos-servos-release.jks -alias somos-servos -keyalg RSA -keysize 4096 -validity 10000
   ```

   Guarde o arquivo `somos-servos-release.jks`, a senha do keystore e a senha da chave em dois locais seguros. O alias sugerido é `somos-servos`.

2. Codifique uma cópia do arquivo para cadastrar no GitHub. No Linux:

   ```bash
   base64 -w 0 somos-servos-release.jks
   ```

   No macOS:

   ```bash
   base64 < somos-servos-release.jks | tr -d '\n'
   ```

   Copie a saída apenas para o segredo do GitHub; não a publique nem a envie aqui.

3. Abra [os segredos do GitHub Actions deste repositório](https://github.com/charlieleitao-spec/somos-servos-app/settings/secrets/actions) e crie estes quatro **Repository secrets**:

   | Nome | Valor |
   | --- | --- |
   | `SOMOS_SERVOS_KEYSTORE_BASE64` | Saída base64 do passo 2 |
   | `SOMOS_SERVOS_STORE_PASSWORD` | Senha do keystore |
   | `SOMOS_SERVOS_KEY_ALIAS` | `somos-servos` |
   | `SOMOS_SERVOS_KEY_PASSWORD` | Senha da chave |

   Esses nomes são exclusivos deste app. O fluxo decodifica o keystore apenas no diretório temporário do runner, assina o APK, verifica pacote, versão e assinatura, e apaga o arquivo temporário.

## Publicar uma versão

1. Abra **Actions > Release APK Somos Servos** e escolha **Run workflow** na branch `main`.
2. Informe a versão pública em formato `MAJOR.MINOR.PATCH`; a primeira pode ser `1.0.1`.
3. O fluxo calcula o `versionCode` a partir da versão, compila o APK release, verifica a assinatura e publica uma release estável com link direto para o APK.

Use uma versão pública maior em cada release. O `versionCode` é calculado como `MAJOR × 1.000.000 + MINOR × 1.000 + PATCH`; mantenha `MINOR` e `PATCH` abaixo de 1000. O APK de teste atual usa a chave de depuração, portanto não pode ser atualizado diretamente para o primeiro APK estável: será necessário desinstalar o APK de teste antes da primeira instalação assinada. Depois, todas as releases devem usar o mesmo keystore para permitir atualizações normais.

Nos pull requests, o mesmo fluxo compila e verifica um APK assinado com uma chave descartável de teste, sem usar os segredos permanentes nem publicar uma release. O arquivo `scripts/configure-android-release.py` configura somente o projeto Android temporário do runner. Senhas e keystore não são gravados no repositório.
