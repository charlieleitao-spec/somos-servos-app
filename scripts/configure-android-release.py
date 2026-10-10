#!/usr/bin/env python3
"""Configure the generated Capacitor Android project for a signed release."""
import os
import re
from pathlib import Path

app_gradle = Path("android/app/build.gradle")
source = app_gradle.read_text(encoding="utf-8")

if not re.search(r'(?m)^\s*applicationId\s+"br\.com\.somosservos\.app"\s*$', source):
    raise SystemExit("Android applicationId is not the expected Somos Servos package.")

version_name = os.environ["SOMOS_SERVOS_VERSION_NAME"]
version_code = os.environ["SOMOS_SERVOS_VERSION_CODE"]
if not re.fullmatch(r"\d+\.\d+\.\d+", version_name):
    raise SystemExit("version_name must use MAJOR.MINOR.PATCH, for example 1.0.0.")
if not version_code.isdecimal() or not (1 <= int(version_code) <= 2_100_000_000):
    raise SystemExit("version_code must be a positive integer up to 2100000000.")

source, code_count = re.subn(
    r"(?m)^(\s*versionCode\s+)\d+\s*$",
    lambda match: f"{match.group(1)}{version_code}",
    source,
)
source, name_count = re.subn(
    r'(?m)^(\s*versionName\s+)"[^"]*"\s*$',
    lambda match: f'{match.group(1)}"{version_name}"',
    source,
)
if code_count != 1 or name_count != 1:
    raise SystemExit("Could not safely locate exactly one versionCode and versionName.")

build_types = re.search(r"(?m)^(\s*)buildTypes\s*\{\s*$", source)
if not build_types:
    raise SystemExit("Could not locate the generated Android buildTypes block.")
release_block = re.search(
    r"(?m)^(\s*)release\s*\{\s*$", source[build_types.end():]
)
if not release_block:
    raise SystemExit("Could not locate the generated release build type.")
release_indent = release_block.group(1)

if "signingConfigs.release" in source:
    raise SystemExit("A release signing configuration already exists; refusing to duplicate it.")

android_indent = build_types.group(1)
signing_config = (
    f"{android_indent}signingConfigs {{\n"
    f"{android_indent}    release {{\n"
    f"{android_indent}        storeFile file(System.getenv('SOMOS_SERVOS_KEYSTORE_PATH'))\n"
    f"{android_indent}        storePassword System.getenv('SOMOS_SERVOS_STORE_PASSWORD')\n"
    f"{android_indent}        keyAlias System.getenv('SOMOS_SERVOS_KEY_ALIAS')\n"
    f"{android_indent}        keyPassword System.getenv('SOMOS_SERVOS_KEY_PASSWORD')\n"
    f"{android_indent}    }}\n"
    f"{android_indent}}}\n"
)
source = source[:build_types.start()] + signing_config + source[build_types.start():]

release_open = re.search(
    r"(?m)^(\s*)release\s*\{\s*$",
    source[re.search(r"(?m)^\s*buildTypes\s*\{\s*$", source).end():],
)
if not release_open:
    raise SystemExit("Could not re-locate the release build type after configuration.")
absolute_release_start = re.search(r"(?m)^\s*buildTypes\s*\{\s*$", source).end() + release_open.start()
absolute_release_end = source.index("\n", absolute_release_start) + 1
signing_line = f"{release_indent}    signingConfig signingConfigs.release\n"
source = source[:absolute_release_end] + signing_line + source[absolute_release_end:]

app_gradle.write_text(source, encoding="utf-8")
print(f"Configured signed Somos Servos release {version_name} ({version_code}).")
