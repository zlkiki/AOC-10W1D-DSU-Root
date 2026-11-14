#!/usr/bin/env python3
"""AOC 10W1D: replace the Android boot animation (/odm/media/bootanimation.zip) with a Magisk module.

Stock animation on this device: /odm/media/bootanimation.zip, 1404x1872 portrait (NOT rotated),
desc.txt "1404 1872 1" / "p 0 0 part0", 6 PNG frames, 1 fps, loops until boot completes, stored (no compression).

Magisk magic mount does not cover /odm, so the module bind-mounts its own zip in post-fs-data.
The file MUST be labeled u:object_r:system_file:s0 (verified 2026-11-14):
  - the original label (oemfs) cannot be set on /data (f2fs): avc denied { associate }
  - vendor_file can be set but bootanim cannot read it: avc denied { read } -> AOSP default animation is shown

Usage:
  python make_bootanim_module.py Magisk.apk OUTDIR                       # generic sample frames
  python make_bootanim_module.py Magisk.apk OUTDIR --frames DIR           # your own PNGs (sorted by name), 1404x1872
  python make_bootanim_module.py Magisk.apk OUTDIR --text "Starting..."   # sample frames with your text
Install: adb push OUTDIR/eink_bootanim.zip /data/local/tmp/ && adb shell su -c magisk --install-module /data/local/tmp/eink_bootanim.zip  -> reboot
Remove : Magisk app > Modules > delete -> reboot (stock animation comes back)
"""
from __future__ import annotations

import argparse
import io
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1404, 1872
MODID = "eink_bootanim"

POST_FS_DATA = """#!/system/bin/sh
MODDIR=${0%/*}
SRC=$MODDIR/bootanimation.zip
DST=/odm/media/bootanimation.zip
[ -f "$SRC" ] && [ -f "$DST" ] || exit 0
# oemfs cannot be set on /data; vendor_file is not readable by bootanim; system_file works.
chcon u:object_r:system_file:s0 "$SRC"
chmod 0644 "$SRC"
mount -o bind "$SRC" "$DST"
"""

MODULE_PROP = f"""id={MODID}
name=E-Ink boot animation (AOC 10W1D)
version=v2
versionCode=2
author=AOC-10W1D-DSU-Root
description=Bind-mounts a custom bootanimation.zip over /odm/media/bootanimation.zip. Delete the module to restore stock.
"""


def sample_frames(text: str, n: int = 6) -> list[Image.Image]:
    try:
        big, small = ImageFont.load_default(size=96), ImageFont.load_default(size=44)
    except TypeError:  # Pillow < 10.1
        big = small = ImageFont.load_default()
    out = []
    for i in range(n):
        im = Image.new("L", (W, H), 255)
        d = ImageDraw.Draw(im)
        tw = d.textlength(text, font=big)
        d.text(((W - tw) / 2, 760), text, font=big, fill=0)
        x0, x1, y0, y1 = 252, W - 252, 1000, 1050
        d.rectangle([x0, y0, x1, y1], outline=0, width=6)
        d.rectangle([x0 + 6, y0 + 6, x0 + 6 + int((x1 - x0 - 12) * (i + 1) / n), y1 - 6], fill=0)
        label = f"frame {i + 1}/{n}"
        d.text(((W - d.textlength(label, font=small)) / 2, H - 200), label, font=small, fill=136)
        out.append(im)
    return out


def load_frames(folder: Path) -> list[Image.Image]:
    frames = []
    for p in sorted(folder.glob("*.png")):
        im = Image.open(p).convert("L")
        if im.size != (W, H):
            raise SystemExit(f"{p.name}: {im.size}, expected {W}x{H} portrait")
        frames.append(im)
    if not frames:
        raise SystemExit(f"no PNG in {folder}")
    return frames


def build(apk: Path, out: Path, frames: list[Image.Image], fps: int) -> tuple[Path, Path]:
    out.mkdir(parents=True, exist_ok=True)
    anim = out / "bootanimation.zip"
    with zipfile.ZipFile(anim, "w", compression=zipfile.ZIP_STORED) as z:
        z.writestr("desc.txt", f"{W} {H} {fps}\np 0 0 part0\n")
        for i, im in enumerate(frames):
            buf = io.BytesIO()
            im.save(buf, "PNG")
            z.writestr(f"part0/{i + 1:03d}.png", buf.getvalue())
    with zipfile.ZipFile(apk) as a:
        installer = a.read("assets/module_installer.sh")
    mod = out / f"{MODID}.zip"
    with zipfile.ZipFile(mod, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("META-INF/com/google/android/update-binary", installer)
        z.writestr("META-INF/com/google/android/updater-script", "#MAGISK\n")
        z.writestr("module.prop", MODULE_PROP)
        z.writestr("post-fs-data.sh", POST_FS_DATA)
        z.write(anim, "bootanimation.zip", compress_type=zipfile.ZIP_STORED)
    return anim, mod


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("magisk_apk", type=Path)
    ap.add_argument("outdir", type=Path)
    ap.add_argument("--frames", type=Path, help="folder of 1404x1872 PNG frames")
    ap.add_argument("--text", default="Starting Android", help="text for sample frames")
    ap.add_argument("--fps", type=int, default=1)
    a = ap.parse_args()
    frames = load_frames(a.frames) if a.frames else sample_frames(a.text)
    anim, mod = build(a.magisk_apk, a.outdir, frames, a.fps)
    print(f"animation: {anim} ({anim.stat().st_size} B, {len(frames)} frames)\nmodule:    {mod}")


if __name__ == "__main__":
    main()
