#!/usr/bin/env python3
"""E-Ink Screens APK build without Gradle (Android SDK build-tools + JDK).

Env:
  ANDROID_SDK   (default D:/Android/Sdk)        needs platforms;android-30 and build-tools;34.0.0
  JAVA_HOME     (default C:/tools/jdk-21)
  KEYSTORE      path to a .jks (created on first run if missing), KEYSTORE_PASS password
Usage: python build.py [OUT_DIR]   -> OUT_DIR/EinkScreens.apk
"""
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SDK = Path(os.environ.get("ANDROID_SDK", "D:/Android/Sdk"))
BT = SDK / "build-tools" / "34.0.0"
JAR = SDK / "platforms" / "android-30" / "android.jar"
JAVA_HOME = Path(os.environ.get("JAVA_HOME", "C:/tools/jdk-21"))
EXE = ".exe" if os.name == "nt" else ""
BAT = ".bat" if os.name == "nt" else ""


def run(*cmd):
    pw = os.environ.get("KEYSTORE_PASS")
    shown = " ".join(str(c) for c in cmd)
    print("+", shown.replace(pw, "***") if pw else shown, flush=True)
    subprocess.run([str(c) for c in cmd], check=True)


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "out"
    ks = Path(os.environ.get("KEYSTORE", "D:/Android/keys/einkscreens.jks"))
    pw = os.environ.get("KEYSTORE_PASS")
    if not pw:
        sys.exit("KEYSTORE_PASS not set")
    b = out / "build"
    shutil.rmtree(b, ignore_errors=True)
    (b / "gen").mkdir(parents=True)
    (b / "classes").mkdir()
    # 1) resources
    run(BT / f"aapt2{EXE}", "compile", "--dir", HERE / "res", "-o", b / "res.zip")
    run(BT / f"aapt2{EXE}", "link", "-I", JAR, "--manifest", HERE / "AndroidManifest.xml",
        "--java", b / "gen", "-o", b / "base.apk", b / "res.zip")
    # 2) java -> class (Java 8 target with android.jar as boot classpath)
    srcs = [str(p) for p in (HERE / "src").rglob("*.java")] + [str(p) for p in (b / "gen").rglob("*.java")]
    # android.jar 의 LambdaMetafactory 는 javac 와 맞지 않으므로 JDK 의 Java 8 API(--release 8)로 컴파일
    run(JAVA_HOME / "bin" / f"javac{EXE}", "-encoding", "UTF-8", "--release", "8",
        "-classpath", JAR, "-Xlint:-options", "-d", b / "classes", *srcs)
    # 3) class -> dex
    classes = [str(p) for p in (b / "classes").rglob("*.class")]
    run(BT / f"d8{BAT}", "--release", "--min-api", "30", "--lib", JAR, "--output", b, *classes)
    # 4) add dex, align, sign
    shutil.copy(b / "base.apk", b / "unsigned.apk")
    with zipfile.ZipFile(b / "unsigned.apk", "a") as z:
        z.write(b / "classes.dex", "classes.dex")
    run(BT / f"zipalign{EXE}", "-f", "-p", "4", b / "unsigned.apk", b / "aligned.apk")
    if not ks.exists():
        ks.parent.mkdir(parents=True, exist_ok=True)
        run(JAVA_HOME / "bin" / f"keytool{EXE}", "-genkeypair", "-keystore", ks, "-alias", "einkscreens",
            "-keyalg", "RSA", "-keysize", "3072", "-validity", "10000", "-storepass", pw, "-keypass", pw,
            "-dname", "CN=E-Ink Screens")
    apk = out / "EinkScreens.apk"
    run(BT / f"apksigner{BAT}", "sign", "--ks", ks, "--ks-key-alias", "einkscreens",
        "--ks-pass", "env:KEYSTORE_PASS", "--key-pass", "env:KEYSTORE_PASS", "--out", apk, b / "aligned.apk")
    run(BT / f"apksigner{BAT}", "verify", apk)
    print(f"OK: {apk} ({apk.stat().st_size} B)")


if __name__ == "__main__":
    main()
