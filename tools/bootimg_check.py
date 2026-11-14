#!/usr/bin/env python3
"""Android boot image(header v0~v2) 섹션 비교 도구 — Magisk 패치 전후 검증용 (AOC 10W1D에서 사용).

사용법:
  python bootimg_check.py info  boot.img
  python bootimg_check.py diff  stock_boot.img patched_boot.img [--max-size 67108864]

diff 합격 기준 (Magisk 패치 정상):
  - 헤더 버전·page size 동일
  - kernel, second(RSCE 리소스), recovery_dtbo, dtb 해시 동일
  - ramdisk만 변경
  - 전체 크기 <= 파티션 크기(기본 64MB)
.gz 입력 허용.
"""
from __future__ import annotations

import gzip
import hashlib
import struct
import sys
from pathlib import Path


def load(p: str) -> bytes:
    d = Path(p).read_bytes()
    return gzip.decompress(d) if p.endswith(".gz") else d


def align(n: int, page: int) -> int:
    return (n + page - 1) // page * page


def parse(d: bytes) -> dict:
    if d[:8] != b"ANDROID!":
        raise ValueError("ANDROID! 매직 아님")
    (k_size, _k_addr, r_size, _r_addr, s_size, _s_addr, _tags, page, ver, _osv) = struct.unpack_from("<10I", d, 8)
    cmdline = d[64:576].split(b"\0", 1)[0].decode(errors="replace")
    info = dict(version=ver, page=page, cmdline=cmdline)
    off = page
    secs = [("kernel", k_size), ("ramdisk", r_size), ("second", s_size)]
    if ver >= 1:
        rd_size, = struct.unpack_from("<I", d, 1632)
        secs.append(("recovery_dtbo", rd_size))
    if ver >= 2:
        dtb_size, = struct.unpack_from("<I", d, 1648)
        secs.append(("dtb", dtb_size))
    sections = {}
    for name, size in secs:
        sections[name] = dict(off=off, size=size, sha=hashlib.sha256(d[off:off + size]).hexdigest(), head=d[off:off + 4].hex())
        off += align(size, page)
    info["sections"] = sections
    info["used"] = off
    return info


def show(name: str, info: dict):
    print(f"{name}: header v{info['version']} page={info['page']} used={info['used']}B")
    for k, s in info["sections"].items():
        print(f"  {k:<14} off=0x{s['off']:08x} size={s['size']:>10} head={s['head']} sha256={s['sha'][:16]}")


def main(argv):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if len(argv) >= 2 and argv[0] == "info":
        show(argv[1], parse(load(argv[1])))
        return 0
    if len(argv) >= 3 and argv[0] == "diff":
        max_size = 64 * 1024 * 1024
        if "--max-size" in argv:
            max_size = int(argv[argv.index("--max-size") + 1])
        a, b = load(argv[1]), load(argv[2])
        ia, ib = parse(a), parse(b)
        show("stock", ia)
        show("patched", ib)
        ok = True
        checks = [("header version", ia["version"] == ib["version"]), ("page size", ia["page"] == ib["page"])]
        for k in ia["sections"]:
            same = ia["sections"][k]["sha"] == ib["sections"].get(k, {}).get("sha")
            if k == "ramdisk":
                checks.append(("ramdisk 변경됨(패치 적용)", not same))
            elif ia["sections"][k]["size"] == 0 and ib["sections"].get(k, {}).get("size", 0) == 0:
                continue
            else:
                checks.append((f"{k} 동일", same))
        checks.append((f"파일 크기 {len(b)} <= {max_size}", len(b) <= max_size))
        checks.append(("cmdline 동일", ia["cmdline"] == ib["cmdline"]))
        for label, res in checks:
            print(f"  [{'PASS' if res else 'FAIL'}] {label}")
            ok &= res
        print("판정:", "합격" if ok else "불합격")
        return 0 if ok else 1
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
