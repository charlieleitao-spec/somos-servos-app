#!/usr/bin/env python3
"""Copy native sources and configure the generated Capacitor Android project."""

import json
import re
import shutil
from pathlib import Path


project = Path("android/app/src/main")
sources = Path("android-src")
shutil.copyfile(sources / "MainActivity.java", project / "java/br/com/somosservos/app/MainActivity.java")
drawable = project / "res/drawable"
drawable.mkdir(exist_ok=True)
shutil.copyfile(sources / "ic_notification.xml", drawable / "ic_notification.xml")

manifest = project / "AndroidManifest.xml"
source = manifest.read_text(encoding="utf-8")
if "xmlns:tools=" not in source:
    source = source.replace("<manifest ", '<manifest xmlns:tools="http://schemas.android.com/tools" ', 1)
for permission in ("WAKE_LOCK", "SCHEDULE_EXACT_ALARM"):
    marker = f'android:name="android.permission.{permission}"'
    if marker not in source:
        source = source.replace(
            "</manifest>", f'    <uses-permission {marker} tools:node="remove" />\n</manifest>', 1,
        )
manifest.write_text(source, encoding="utf-8")

# A variante de teste instala ao lado do APK estável.
version = json.loads(Path("package.json").read_text(encoding="utf-8"))["version"]
major, minor, patch = map(int, version.split("."))
gradle = project.parent.parent / "build.gradle"
source = gradle.read_text(encoding="utf-8")
source = re.sub(r'(?m)^(\s*versionName )"[^"]+"$', rf'\g<1>"{version}"', source)
source = re.sub(r"(?m)^(\s*versionCode )\d+$", rf"\g<1>{major * 1000000 + minor * 1000 + patch}", source)
if 'applicationIdSuffix ".teste"' not in source:
    source = source.replace(
        "    buildTypes {\n",
        '    buildTypes {\n        debug {\n            applicationIdSuffix ".teste"\n'
        '            versionNameSuffix "-teste"\n        }\n',
        1,
    )
gradle.write_text(source, encoding="utf-8")

debug = project.parent / "debug" / "AndroidManifest.xml"
debug.parent.mkdir(exist_ok=True)
debug.write_text(
    '''<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:tools="http://schemas.android.com/tools">
    <application android:label="Somos Servos Teste" tools:replace="android:label">
        <activity android:name="br.com.somosservos.app.MainActivity"
            android:label="Somos Servos Teste" tools:replace="android:label" />
    </application>
</manifest>
''', encoding="utf-8",
)
