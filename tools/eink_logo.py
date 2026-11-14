#!/usr/bin/env python3
"""AOC 10W1D (Rockchip RK3566 E-Ink) logo 파티션(RKEL/GR04) 도구 — 부팅 로고·충전·저전력·종료 이미지 10종.

logo 파티션 구조 (2026-11-14 순정 덤프 실측):
  - 헤더 0x00: magic 'RKEL', u32 전체 크기, u32 width, u32 height, u32 엔트리 수, 버전 문자열 '1.00' (0x14)
  - 엔트리 표 0x40부터 0x20 바이트씩:
      magic 'GR04', u32 0, u16 width, u16 height, u32 type, u32 offset, u32 size, 8바이트 0
  - 이미지: 4bpp 그레이(픽셀 2개당 1바이트), width×height (가로 저장, 세로 화면을 시계방향 90° 회전)
  - type: 0x1 U-Boot 로고, 0x2 커널 로고, 0x4~0x80 충전 0~5, 0x100 저전력, 0x200 종료 (Rockchip rk_eink 규격, 렌더링으로 확인)

사용법:
  python eink_logo.py info   logo.img
  python eink_logo.py unpack logo.img OUTDIR           # 엔트리별 PNG(가로 원본 + 세로 보기용) 저장
  python eink_logo.py pack   logo.img OUT.img TYPE=PNG [TYPE=PNG ...]   # 지정 엔트리만 교체
  python eink_logo.py verify logo.img                  # unpack→pack 재조립이 원본과 바이트 동일한지 검사

PNG 입력은 세로 1404×1872(화면 보이는 방향) 또는 가로 1872×1404(저장 방향) 모두 허용.
"""
from __future__ import annotations

import gzip
import hashlib
import struct
import sys
from pathlib import Path

from PIL import Image

TYPE_NAMES = {
    0x1: "uboot",
    0x2: "kernel",
    0x4: "charge0",
    0x8: "charge1",
    0x10: "charge2",
    0x20: "charge3",
    0x40: "charge4",
    0x80: "charge5",
    0x100: "lowpower",
    0x200: "poweroff",
}
NAME_TYPES = {v: k for k, v in TYPE_NAMES.items()}
HDR_FMT = "<4sIIII"
ENT_FMT = "<4sIHHIII"
ENT_BASE, ENT_SIZE = 0x40, 0x20
# 니블 순서: 짝수 픽셀 = 하위 니블 (렌더링 실측으로 확정)
LOW_NIBBLE_FIRST = True


def load(path: str | Path) -> bytes:
    p = Path(path)
    data = p.read_bytes()
    return gzip.decompress(data) if p.suffix == ".gz" else data


def parse(data: bytes):
    magic, total, w, h, n = struct.unpack_from(HDR_FMT, data, 0)
    if magic != b"RKEL":
        raise ValueError(f"RKEL 매직 아님: {magic!r}")
    ents = []
    for i in range(n):
        m, z, ew, eh, typ, off, size = struct.unpack_from(ENT_FMT, data, ENT_BASE + i * ENT_SIZE)
        if m != b"GR04":
            raise ValueError(f"엔트리 {i} GR04 매직 아님: {m!r}")
        if size != ew * eh // 2:
            raise ValueError(f"엔트리 {i} 크기 불일치: {size} != {ew}*{eh}/2")
        ents.append(dict(idx=i, type=typ, name=TYPE_NAMES.get(typ, hex(typ)), w=ew, h=eh, off=off, size=size))
    return dict(total=total, w=w, h=h, n=n), ents


def gr04_to_image(raw: bytes, w: int, h: int) -> Image.Image:
    out = bytearray(w * h)
    for i, b in enumerate(raw):
        lo, hi = b & 0x0F, b >> 4
        a, c = (lo, hi) if LOW_NIBBLE_FIRST else (hi, lo)
        out[2 * i] = a * 17
        out[2 * i + 1] = c * 17
    return Image.frombytes("L", (w, h), bytes(out))


def image_to_gr04(im: Image.Image, w: int, h: int) -> bytes:
    im = im.convert("L")
    if im.size == (h, w):  # 세로(보이는 방향) 입력 → 저장 방향(시계 90°)으로 회전
        im = im.rotate(-90, expand=True)
    if im.size != (w, h):
        raise ValueError(f"이미지 크기 {im.size}: {w}x{h}(가로) 또는 {h}x{w}(세로)여야 함")
    px = im.tobytes()
    out = bytearray(w * h // 2)
    for i in range(len(out)):
        a = (px[2 * i] + 8) // 17
        c = (px[2 * i + 1] + 8) // 17
        out[i] = (a | (c << 4)) if LOW_NIBBLE_FIRST else ((a << 4) | c)
    return bytes(out)


def cmd_info(path):
    data = load(path)
    hdr, ents = parse(data)
    print(f"RKEL total=0x{hdr['total']:x} {hdr['w']}x{hdr['h']} entries={hdr['n']} file={len(data)}B sha256={hashlib.sha256(data).hexdigest()}")
    for e in ents:
        raw = data[e["off"]: e["off"] + e["size"]]
        print(f"  [{e['idx']}] type=0x{e['type']:03x} {e['name']:<9} off=0x{e['off']:06x} size={e['size']} sha256={hashlib.sha256(raw).hexdigest()[:16]}")


def cmd_unpack(path, outdir):
    data = load(path)
    _, ents = parse(data)
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    for e in ents:
        im = gr04_to_image(data[e["off"]: e["off"] + e["size"]], e["w"], e["h"])
        im.save(out / f"{e['idx']:02d}_{e['name']}_stored.png")
        im.rotate(90, expand=True).save(out / f"{e['idx']:02d}_{e['name']}_portrait.png")
    print(f"{len(ents)}개 저장: {out}")


def pack(data: bytes, replacements: dict[int, Image.Image]) -> bytes:
    _, ents = parse(data)
    buf = bytearray(data)
    for e in ents:
        if e["type"] in replacements:
            raw = image_to_gr04(replacements[e["type"]], e["w"], e["h"])
            buf[e["off"]: e["off"] + e["size"]] = raw
    assert len(buf) == len(data)
    return bytes(buf)


def cmd_pack(path, outpath, specs):
    data = load(path)
    reps = {}
    for s in specs:
        k, v = s.split("=", 1)
        typ = NAME_TYPES[k] if k in NAME_TYPES else int(k, 0)
        reps[typ] = Image.open(v)
    new = pack(data, reps)
    Path(outpath).write_bytes(new)
    _, ents = parse(new)
    changed = [e["name"] for e in ents if data[e["off"]: e["off"] + e["size"]] != new[e["off"]: e["off"] + e["size"]]]
    # 엔트리 영역 밖(헤더·패딩)은 원본과 같아야 함
    mask = bytearray(len(data))
    for e in ents:
        mask[e["off"]: e["off"] + e["size"]] = b"\x01" * e["size"]
    outside_same = all(data[i] == new[i] for i in range(len(data)) if not mask[i])
    print(f"저장: {outpath} ({len(new)}B) sha256={hashlib.sha256(new).hexdigest()}")
    print(f"  변경 엔트리: {changed}")
    print(f"  헤더·엔트리 외 영역 원본 동일: {outside_same}")
    if not outside_same:
        sys.exit(2)


def cmd_verify(path):
    data = load(path)
    _, ents = parse(data)
    reps = {e["type"]: gr04_to_image(data[e["off"]: e["off"] + e["size"]], e["w"], e["h"]) for e in ents}
    new = pack(data, reps)
    same = new == data
    print(f"재조립 바이트 동일: {same}")
    sys.exit(0 if same else 1)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv[1:]
    if not a:
        print(__doc__)
        sys.exit(1)
    {"info": lambda: cmd_info(a[1]),
     "unpack": lambda: cmd_unpack(a[1], a[2]),
     "pack": lambda: cmd_pack(a[1], a[2], a[3:]),
     "verify": lambda: cmd_verify(a[1])}[a[0]]()
