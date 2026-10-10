#!/usr/bin/env python3
"""Configure the generated Capacitor Android project for a signed release."""
import os
import re
from pathlib import Path

app_gradle = Path("android/app/build.gradle")
lines = app_gradle.read_text(encoding="utf-8").splitlines(keepends=True)

source = "".join(lines)
if not re.search(r'(?m)^[ \t]*applicationId[ \t]+"br\.com\.somosservos\.app"[ \t]*$', source):
    raise SystemExit("Android applicationId is not the expected Somos Servos package.")

version_name = os.environ["SOMOS_SERVOS_VERSION_NAME"]
version_code = os.environ["SOMOS_SERVOS_VERSION_CODE"]
if not re.fullmatch(r"\d+\.\d+\.\d+", version_name):
    raise SystemExit("version_name must use MAJOR.MINOR.PATCH, for example 1.0.0.")
if not version_code.isdecimal() or not (1 <= int(version_code) <= 2_100_000_000):
    raise SystemExit("version_code must be a positive integer up to 2100000000.")

source, code_count = re.subn(
    r"(?m)^([ \t]*versionCode[ \t]+)\d+[ \t]*$",
    lambda match: f"{match.group(1)}{version_code}",
    source,
)
source, name_count = re.subn(
    r'(?m)^([ \t]*versionName[ \t]+)"[^"]*"[ \t]*$',
    lambda match: f'{match.group(1)}"{version_name}"',
    source,
)
if code_count != 1 or name_count != 1:
    raise SystemExit("Could not safely locate exactly one versionCode and versionName.")

lines = source.splitlines(keepends=True)
build_types_index = next(
    (index for index, line in enumerate(lines)
     if re.match(r"^[ \t]*buildTypes[ \t]*\{[ \t]*$", line.rstrip("\r\n"))),
    None,
)
if build_types_index is None:
    raise SystemExit("Could not locate the generated Android buildTypes block.")

release_index = next(
    (index for index in range(build_types_index + 1, len(lines))
     if re.match(r"^[ \t]*release[ \t]*\{[ \t]*$", lines[index].rstrip("\r\n"))),
    None,
)
if release_index is None:
    raise SystemExit("Could not locate the generated release build type.")
if "signingConfigs.release" in source:
    raise SystemExit("A release signing configuration already exists; refusing to duplicate it.")

build_types_indent = re.match(r"^[ \t]*", lines[build_types_index]).group(0)
release_indent = re.match(r"^[ \t]*", lines[release_index]).group(0)
signing_config = [
    f"{build_types_indent}signingConfigs {{\n",
    f"{build_types_indent}    release {{\n",
    f"{build_types_indent}        storeFile file(System.getenv('SOMOS_SERVOS_KEYSTORE_PATH'))\n",
    f"{build_types_indent}        storePassword System.getenv('SOMOS_SERVOS_STORE_PASSWORD')\n",
    f"{build_types_indent}        keyAlias System.getenv('SOMOS_SERVOS_KEY_ALIAS')\n",
    f"{build_types_indent}        keyPassword System.getenv('SOMOS_SERVOS_KEY_PASSWORD')\n",
    f"{build_types_indent}    }}\n",
    f"{build_types_indent}}}\n",
]
lines[build_types_index:build_types_index] = signing_config
release_index += len(signing_config)
lines.insert(
    release_index + 1,
    f"{release_indent}    signingConfig signingConfigs.release\n",
)

app_gradle.write_text("".join(lines), encoding="utf-8")
print(f"Configured signed Somos Servos release {version_name} ({version_code}).")
