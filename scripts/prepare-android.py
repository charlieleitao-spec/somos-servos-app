#!/usr/bin/env python3
"""Copy native sources and configure the generated Capacitor Android project."""

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
