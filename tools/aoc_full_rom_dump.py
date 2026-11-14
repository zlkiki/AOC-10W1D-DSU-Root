#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
aoc_full_rom_dump.py  (2026-11-14, AOC 10W1D 실기기 검증)

AOC 10W1D (RK3566 / Android 11 / A-only / eMMC=mmcblk2) DSU 기반 Full ROM 덤프 도구.
가이드: ../README.md

하위 명령 (실행 순서대로):
  preflight    순정 OS에서 DSU 사전 조건 점검               [읽기 전용]
  prepare-gsi  GSI .img.xz/.img -> 512B 패딩 -> .img.gz     [PC 로컬 작업]
  install-dsu  GSI 전송 + DSU 기능 플래그 + 설치 화면 호출  [기기 상태 변경: DSU 설치]
  reboot-dsu   설치 완료 확인 후 GSI로 재부팅, ADB 상태 대기 [기기 재부팅]
  dump         GSI(root)에서 전 파티션 덤프 -> PC 복사 -> 3중 해시 검증 -> 백업 교차검증
  crosscheck   PC에 받은 이미지를 기존 RKDevTool 백업과 다시 대조 [PC 로컬 작업]

안전 원칙:
  - 블록 디바이스는 읽기(if=)만 함. 모든 dd 출력(of=)은 DEVICE_TMP 아래로 강제됨.
  - userdata(개인 데이터)와 전체 디스크 노드(mmcblk2)는 덤프 대상에서 제외.
  - 기기 쪽 tmp는 DSU 임시 userdata 위에 있으므로 DSU를 지우면 함께 사라짐.
    PC 검증이 끝나기 전에는 DSU를 지우지 말 것.

사용 예:
  python aoc_full_rom_dump.py preflight
  # (진단 GSI는 tools/build_diag_gsi.sh 가 .img.gz와 .size까지 만들어 주므로 prepare-gsi 불필요)
  python aoc_full_rom_dump.py install-dsu aoc_dsu_diag_gsi.img.gz --userdata-gib 16
  python aoc_full_rom_dump.py reboot-dsu
  python aoc_full_rom_dump.py dump --out aoc_full_rom
"""

from __future__ import annotations

import argparse
import os
import gzip
import hashlib
import json
import lzma
import struct
import subprocess
import sys
import time
import zipfile
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

# --------------------------------------------------------------------------
# 상수 (2026-11-13 실측값)
# --------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
BACKUP_DIR = Path(os.environ.get("AOC_STOCK_BACKUP_DIR", "__none__"))  # 선택: 이전 부분 백업(boot.img.zip) 폴더

DEFAULT_ADB = "adb"
DEFAULT_SERIAL = os.environ.get("ANDROID_SERIAL")  # 미지정 시 연결된 기기 1대 자동 선택
DEFAULT_PC_OUT = "aoc_full_rom"
DEVICE_TMP = "/data/local/tmp/aoc_rom_dump"
DEVICE_DOWNLOAD = "/storage/emulated/0/Download"
DISK = "mmcblk2"

EXPECTED_PARTITIONS = [
    "uboot", "trust", "waveform", "misc", "dtbo", "vbmeta", "boot", "security",
    "recovery", "backup", "cache", "metadata", "super", "logo", "userdata",
]
EXCLUDED = {"userdata", DISK}

RESTORE_NOTES = {
    "metadata": "DSU 실행 중 상태(/metadata/gsi)가 기록된 이미지 - 순정 복원용으로 쓰지 말 것",
    "cache": "로그/임시 데이터 - 복원 불필요",
    "gpt_head": "GPT + idbloader(LBA 0 ~ uboot 직전) - 최후 수단 복원 전용",
    "gpt_tail": "백업 GPT(디스크 마지막 33섹터) - 참고용",
    "waveform": "E-Ink 패널 보정값 - 기기 고유, 쓰기 금지",
}

KNOWN_STOCK_SHA256: dict[str, str] = {
    # 선택: 자기 기기의 이전 RKDevTool 백업 SHA-256을 넣으면 덤프와 교차검증합니다.
    # 예) "waveform": "<sha256>", "dtbo": "<sha256>", "vbmeta": "<sha256>",
}
BOOT_PARTIAL_VALID = 5 * 1024 * 1024  # RKDevTool 덤프에서 유효한 boot 앞부분 (32MB 경계 - 27MB 시작)

SPARSE_MAGIC = b"\x3a\xff\x26\xed"
LP_GEOMETRY_MAGIC = b"gDla"  # 0x616c4467 little-endian, super 오프셋 4096

MB = 1024 * 1024


def info(msg: str) -> None:
    print(msg, flush=True)


def die(msg: str, code: int = 1) -> None:
    print(f"[중단] {msg}", flush=True)
    sys.exit(code)


def human(n: int) -> str:
    return f"{n / MB:,.1f} MB" if n < 1024 * MB else f"{n / (1024 * MB):,.2f} GB"


# --------------------------------------------------------------------------
# ADB 래퍼
# --------------------------------------------------------------------------
class Adb:
    def __init__(self, exe: str, serial: str):
        self.exe = exe
        self.serial = serial

    def _base(self) -> list[str]:
        return [self.exe, "-s", self.serial]

    def run(self, args: list[str], timeout: float = 30, check: bool = True) -> subprocess.CompletedProcess:
        try:
            res = subprocess.run(self._base() + args, capture_output=True, text=True,
                                 encoding="utf-8", errors="replace", timeout=timeout)
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"timeout({timeout:.0f}s): adb {' '.join(args)}")
        if check and res.returncode != 0:
            raise RuntimeError(f"adb {' '.join(args)} 실패 (rc={res.returncode}): {res.stderr.strip() or res.stdout.strip()}")
        return res

    def shell(self, cmd: str, timeout: float = 30, check: bool = True) -> str:
        return self.run(["shell", cmd], timeout=timeout, check=check).stdout.strip()

    def try_shell(self, cmd: str, timeout: float = 30) -> str | None:
        try:
            return self.shell(cmd, timeout=timeout)
        except RuntimeError:
            return None

    def state(self) -> str:
        res = subprocess.run([self.exe, "devices"], capture_output=True, text=True, timeout=15)
        for line in res.stdout.splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2 and parts[0] == self.serial:
                return parts[1]
        return "absent"

    def wait_state(self, want: str = "device", timeout: float = 120) -> str:
        end = time.time() + timeout
        last = None
        while time.time() < end:
            st = self.state()
            if st != last:
                info(f"  - ADB 상태: {st}")
                last = st
            if st == want:
                return st
            time.sleep(3)
        return last or "absent"

    def getprop(self, key: str) -> str:
        return self.try_shell(f"getprop {key}") or ""


def resolve_adb(path: str | None) -> str:
    if path:
        return path
    return DEFAULT_ADB if Path(DEFAULT_ADB).exists() else "adb"


# --------------------------------------------------------------------------
# preflight
# --------------------------------------------------------------------------
def cmd_preflight(a: argparse.Namespace) -> None:
    adb = Adb(resolve_adb(a.adb), a.serial)
    rows: list[tuple[str, str, str]] = []

    def add(level: str, item: str, detail: str) -> None:
        rows.append((level, item, detail))

    st = adb.state()
    if st != "device":
        die(f"기기 {a.serial} 상태가 '{st}' 입니다. USB 연결과 ADB 승인을 확인하세요.")

    model = adb.getprop("ro.product.model")
    add("PASS" if model == "AOC_10W1D" else "WARN", "모델", model)
    running = adb.getprop("ro.gsid.image_running")
    add("WARN" if running == "1" else "PASS", "현재 부팅", "DSU GSI 실행 중" if running == "1" else "순정 OS")

    pkgs = adb.try_shell("pm list packages com.android.dynsystem") or ""
    disabled = adb.try_shell("pm list packages -d com.android.dynsystem") or ""
    if "com.android.dynsystem" not in pkgs:
        add("FAIL", "DSU 서비스", "com.android.dynsystem 없음")
    else:
        add("FAIL" if disabled else "PASS", "DSU 서비스", "비활성화됨" if disabled else "있음")

    gsi = adb.try_shell("gsi_tool status")
    add("PASS" if gsi is not None else "FAIL", "gsi_tool status", gsi or "실행 불가")

    fflag = adb.getprop("persist.sys.fflag.override.settings_dynamic_system")
    add("PASS" if fflag in ("true", "1") else "INFO", "DSU 기능 플래그",
        fflag or "미설정 (install-dsu 단계에서 설정)")

    add("PASS" if adb.getprop("ro.boot.flash.locked") == "0" else "FAIL", "부트로더 언락",
        f"flash.locked={adb.getprop('ro.boot.flash.locked')}, vbstate={adb.getprop('ro.boot.verifiedbootstate')}")
    abi = adb.getprop("ro.product.cpu.abi")
    add("PASS" if abi == "arm64-v8a" else "FAIL", "ABI (arm64 GSI 사용)", abi)
    add("PASS" if adb.getprop("ro.boot.dynamic_partitions") == "true" else "FAIL", "동적 파티션",
        adb.getprop("ro.boot.dynamic_partitions"))

    df = adb.try_shell("df -k /data | tail -n 1") or ""
    try:
        avail_gb = int(df.split()[3]) / (1024 * 1024)
        need = a.userdata_gib + 4 + 10  # userdata + GSI(약 2~3GB) + AOSP 권장 여유 10GB
        add("PASS" if avail_gb >= need else "FAIL", "/data 가용 공간",
            f"{avail_gb:.1f} GB (필요 ≥ {need} GB: userdata {a.userdata_gib} + GSI 4 + 여유 10)")
    except (IndexError, ValueError):
        add("WARN", "/data 가용 공간", f"해석 실패: {df}")

    meta = adb.try_shell("mount | grep ' /metadata '") or ""
    add("PASS" if meta else "FAIL", "/metadata 마운트", meta.split(" type ")[0] if meta else "없음")

    names = (adb.try_shell("ls /dev/block/by-name/") or "").split()
    missing = [p for p in EXPECTED_PARTITIONS if p not in names]
    extra = [n for n in names if n not in EXPECTED_PARTITIONS and not n.startswith(DISK)]
    add("PASS" if not missing else "WARN", "파티션 테이블",
        f"{len(names)}개 노드" + (f", 누락 {missing}" if missing else "") + (f", 추가 {extra}" if extra else ""))

    sb = adb.try_shell("dumpsys statusbar | grep mDisabled1") or ""
    add("PASS" if "0x0" in sb else "WARN", "알림창(재부팅 버튼용)", sb.strip() or "확인 불가")

    info("\n=== DSU 사전 점검 (읽기 전용) ===")
    for level, item, detail in rows:
        info(f"[{level:4}] {item:<22} {detail}")
    fails = [r for r in rows if r[0] == "FAIL"]
    info(f"\n결과: FAIL {len(fails)}건 / WARN {sum(r[0] == 'WARN' for r in rows)}건")
    if fails:
        sys.exit(1)


# --------------------------------------------------------------------------
# prepare-gsi
# --------------------------------------------------------------------------
def cmd_prepare_gsi(a: argparse.Namespace) -> None:
    src = Path(a.image)
    if not src.exists():
        die(f"파일 없음: {src}")
    name = src.name
    for suf in (".xz", ".img"):
        if name.endswith(suf):
            name = name[: -len(suf)]
    out = Path(a.output) if a.output else src.with_name(name + ".img.gz")
    opener = lzma.open if src.suffix == ".xz" else open

    info(f"입력: {src}\n출력: {out}")
    total = 0
    t0 = time.time()
    with opener(src, "rb") as fin, gzip.open(out, "wb", compresslevel=a.level) as fout:
        head = fin.read(4096)
        if head[:4] == SPARSE_MAGIC:
            fout.close()
            out.unlink(missing_ok=True)
            die("Android sparse 이미지입니다. simg2img로 raw 변환 후 다시 실행하세요.")
        if head[1080:1082] != b"\x53\xef":
            info("  [경고] ext4 매직(0xEF53)이 보이지 않습니다. 올바른 system 이미지인지 확인하세요.")
        fout.write(head)
        total += len(head)
        while chunk := fin.read(8 * MB):
            fout.write(chunk)
            total += len(chunk)
            if total % (256 * MB) < 8 * MB:
                info(f"  ... {human(total)}")
        pad = (-total) % 512
        if pad:
            fout.write(b"\0" * pad)
            total += pad
    size_file = out.with_name(out.name + ".size")
    size_file.write_text(str(total), encoding="ascii")
    info(f"\n완료 ({time.time() - t0:.0f}초). 패딩 {pad}바이트 추가")
    info(f"KEY_SYSTEM_SIZE = {total}  (저장: {size_file.name})")
    info(f"gz 크기 = {human(out.stat().st_size)}")


# --------------------------------------------------------------------------
# install-dsu
# --------------------------------------------------------------------------
def cmd_install_dsu(a: argparse.Namespace) -> None:
    adb = Adb(resolve_adb(a.adb), a.serial)
    gz = Path(a.image_gz)
    if not gz.exists() or not gz.name.endswith(".gz"):
        die(f".img.gz 파일이 필요합니다: {gz}")
    size_file = gz.with_name(gz.name + ".size")
    sys_size = a.system_size or (int(size_file.read_text()) if size_file.exists() else 0)
    if sys_size <= 0 or sys_size % 512:
        die("KEY_SYSTEM_SIZE를 알 수 없거나 512의 배수가 아닙니다. prepare-gsi를 먼저 실행하세요.")
    if adb.state() != "device":
        die("ADB 연결 상태가 device가 아닙니다.")
    if adb.getprop("ro.gsid.image_running") == "1":
        die("이미 DSU GSI로 부팅되어 있습니다. 순정 OS에서 실행하세요.")
    status = adb.try_shell("gsi_tool status") or ""
    if status and status != "normal":
        info(f"  [주의] gsi_tool status = '{status}' (이미 설치된 DSU가 있을 수 있음)")
        if not a.force:
            die("기존 DSU가 있으면 reboot-dsu를 쓰거나, --force로 재설치하세요.")

    remote = f"{DEVICE_DOWNLOAD}/{gz.name}"
    info(f"[1/3] GSI 전송: {gz.name} ({human(gz.stat().st_size)}) -> {remote}")
    adb.run(["push", str(gz), remote], timeout=3600)
    rsize = adb.shell(f"stat -c %s {remote}")
    if int(rsize) != gz.stat().st_size:
        die(f"전송 크기 불일치: 기기 {rsize} != PC {gz.stat().st_size}")

    info("[2/3] DSU 기능 플래그 설정")
    adb.shell("setprop persist.sys.fflag.override.settings_dynamic_system true")

    userdata = a.userdata_gib * 1024 ** 3
    info(f"[3/3] DSU 설치 화면 호출 (system={sys_size}, userdata={userdata} = {a.userdata_gib}GiB)")
    out = adb.shell(
        "am start-activity -n com.android.dynsystem/com.android.dynsystem.VerificationActivity "
        f"-a android.os.image.action.START_INSTALL -d file://{remote} "
        f"--el KEY_SYSTEM_SIZE {sys_size} --el KEY_USERDATA_SIZE {userdata}")
    info(f"  {out}")
    info("\n다음 작업:")
    info("  1) 태블릿 화면에 뜬 확인 대화상자에서 [확인/OK]를 누르세요.")
    info("  2) 설치에 10~20분 걸립니다. 진행 확인:  adb shell gsi_tool status")
    info("  3) 설치가 끝나면:  python aoc_full_rom_dump.py reboot-dsu")
    info("  ※ gsi_tool enable 등 다른 활성화 방법을 섞지 마세요 (설치가 롤백될 수 있음).")


# --------------------------------------------------------------------------
# reboot-dsu
# --------------------------------------------------------------------------
def cmd_reboot_dsu(a: argparse.Namespace) -> None:
    adb = Adb(resolve_adb(a.adb), a.serial)
    if adb.state() != "device":
        die("ADB 연결 상태가 device가 아닙니다.")
    status = adb.try_shell("gsi_tool status") or ""
    info(f"gsi_tool status = '{status}'")
    notif = adb.try_shell("dumpsys notification --noredact | grep -E '(동적 시스템|Dynamic System|dynsystem)'") or ""
    has_ready_notif = ("동적 시스템이 준비되었습니다" in notif) or ("ready" in notif.lower()) or ("다시 시작" in notif)
    if status == "normal" and not has_ready_notif:
        die("설치된 DSU가 없습니다. install-dsu 완료 여부를 확인하세요.")

    if a.method == "shade":
        adb.shell("cmd statusbar expand-notifications")
        info("태블릿 알림창을 열었습니다. DSU 알림의 [다시 시작/Restart]를 누르세요.")
    else:
        info("DSU 서비스에 GSI 재부팅을 직접 요청합니다 (보조 경로).")
        adb.shell("am start-foreground-service -n com.android.dynsystem/.DynamicSystemInstallationService "
                  "-a com.android.dynsystem.ACTION_REBOOT_TO_DYN_SYSTEM")

    info("\n재부팅 감지 대기 (최대 5분)...")
    end = time.time() + 300
    while time.time() < end and adb.state() == "device":
        time.sleep(3)
    if adb.state() == "device":
        die("재부팅이 감지되지 않았습니다. 화면의 Restart를 눌렀는지 확인하거나 --method service로 다시 실행하세요.")
    info("GSI 부팅 후 ADB 대기 (최대 8분). E-Ink 화면이 멈춰 있어도 정상입니다.")
    st = adb.wait_state("device", timeout=480)
    if st == "unauthorized":
        die("GSI의 ADB가 'unauthorized'입니다. 진단 GSI가 맞는지 확인하세요. 전원 버튼 8~10초로 끄고 다시 켜면 순정으로 돌아옵니다.")
    if st != "device":
        die(f"GSI ADB 미응답 (상태 {st}). USB 케이블을 다시 꽂아 보고, 그래도 안 되면 진단 GSI가 8분 뒤 스스로 순정으로 재부팅합니다.")
    running = adb.getprop("ro.gsid.image_running")
    info(f"ro.gsid.image_running = {running}  /  ro.build.type = {adb.getprop('ro.build.type')}")
    if running == "1":
        info("\nGSI 진입 성공. 다음 순서:")
        info("  adb root")
        info("  adb shell touch /data/local/tmp/dsudiag_stop   # 8분 자동 재부팅 취소")
        info("  adb shell stop                                  # 프레임워크 재시작 루프 정지")
        info("  python aoc_full_rom_dump.py dump")
    else:
        info("\n순정 OS로 다시 부팅된 것 같습니다. 다른 --method로 다시 시도하세요.")


# --------------------------------------------------------------------------
# dump
# --------------------------------------------------------------------------
class Target:
    def __init__(self, name: str, src: str, size: int, skip_sectors: int | None = None):
        self.name = name
        self.src = src
        self.size = size
        self.skip = skip_sectors  # None = 파티션 전체, 아니면 512B 섹터 구간
        self.count = None if skip_sectors is None else size // 512

    def dd_args(self) -> str:
        if self.skip is None:
            return f"if={self.src} bs=4M"
        return f"if={self.src} bs=512 skip={self.skip} count={self.count}"


def io_timeout(size: int, mbps: float) -> float:
    return 300 + size / (mbps * MB)


def build_targets(adb: Adb) -> list[Target]:
    names = adb.shell("ls /dev/block/by-name/").split()
    targets: list[Target] = []
    for n in names:
        if n in EXCLUDED:
            continue
        src = f"/dev/block/by-name/{n}"
        size = int(adb.shell(f"blockdev --getsize64 {src}"))
        targets.append(Target(n, src, size))
    # super를 맨 마지막으로 (작은 것부터 빠르게 확보)
    targets.sort(key=lambda t: (t.name == "super", t.name))

    disk_sectors = int(adb.shell(f"cat /sys/class/block/{DISK}/size"))
    p1_start = adb.try_shell(f"cat /sys/class/block/{DISK}p1/start")
    head_sectors = int(p1_start) if p1_start and p1_start.isdigit() else 0x4000
    disk = f"/dev/block/{DISK}"
    targets.insert(0, Target("gpt_head", disk, head_sectors * 512, 0))
    targets.insert(1, Target("gpt_tail", disk, 33 * 512, disk_sectors - 33))
    return targets


def device_sha_of_source(adb: Adb, t: Target) -> str:
    out = adb.shell(f"dd {t.dd_args()} 2>/dev/null | sha256sum", timeout=io_timeout(t.size, 15))
    return out.split()[0]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8 * MB):
            h.update(chunk)
    return h.hexdigest()


def dump_local(adb: Adb, t: Target, pc_file: Path, retries: int) -> tuple[str, str]:
    dev_file = f"{DEVICE_TMP}/{t.name}.img"
    assert dev_file.startswith(DEVICE_TMP + "/")
    for attempt in range(1, retries + 1):
        if attempt > 1:
            info(f"   재시도 {attempt}/{retries}")
        try:
            src_sha = device_sha_of_source(adb, t)
            adb.shell(f"dd {t.dd_args()} of={dev_file} 2>/dev/null && sync", timeout=io_timeout(t.size, 8))
            dev_size = int(adb.shell(f"stat -c %s {dev_file}"))
            if dev_size != t.size:
                info(f"   [실패] 기기 파일 크기 {dev_size} != {t.size}")
                continue
            file_sha = adb.shell(f"sha256sum {dev_file}", timeout=io_timeout(t.size, 15)).split()[0]
            if file_sha != src_sha:
                info("   [실패] 블록 디바이스 해시와 기기 파일 해시가 다름 (읽기 불안정)")
                continue
        except (RuntimeError, ValueError, IndexError) as e:
            info(f"   [실패] 기기 덤프: {e}")
            continue
        for p in range(1, retries + 1):
            tmp = pc_file.with_suffix(".part")
            try:
                adb.run(["pull", dev_file, str(tmp)], timeout=io_timeout(t.size, 3))
            except RuntimeError as e:
                info(f"   [실패] pull {p}/{retries}: {e}")
                continue
            pc_sha = sha256_file(tmp)
            if pc_sha == src_sha and tmp.stat().st_size == t.size:
                tmp.replace(pc_file)
                return src_sha, "ok"
            info(f"   [실패] PC 해시 불일치 (pull {p}/{retries})")
        return src_sha, "pull_failed"
    return "", "dump_failed"


def dump_stream(adb: Adb, t: Target, pc_file: Path, retries: int) -> tuple[str, str]:
    for attempt in range(1, retries + 1):
        if attempt > 1:
            info(f"   재시도 {attempt}/{retries}")
        try:
            src_sha = device_sha_of_source(adb, t)
        except (RuntimeError, IndexError) as e:
            info(f"   [실패] 원본 해시: {e}")
            continue
        tmp = pc_file.with_suffix(".part")
        h = hashlib.sha256()
        n = 0
        cmd = [adb.exe, "-s", adb.serial, "exec-out", f"dd {t.dd_args()} 2>/dev/null"]
        deadline = time.time() + io_timeout(t.size, 3)
        with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as proc, open(tmp, "wb") as f:
            while chunk := proc.stdout.read(4 * MB):
                f.write(chunk)
                h.update(chunk)
                n += len(chunk)
                if time.time() > deadline:
                    proc.kill()
                    break
        if n == t.size and h.hexdigest() == src_sha:
            tmp.replace(pc_file)
            return src_sha, "ok"
        info(f"   [실패] 스트림 {n}/{t.size} 바이트, 해시 {'일치' if h.hexdigest() == src_sha else '불일치'}")
    return "", "stream_failed"


def collect_device_info(adb: Adb, out: Path) -> None:
    d = out / "device_info"
    d.mkdir(exist_ok=True)
    script = (
        f"for b in /sys/class/block/{DISK}*; do n=${{b##*/}}; "
        "printf '%s %s %s %s\\n' $n $(cat $b/start 2>/dev/null || echo -) $(cat $b/size) "
        "$(grep PARTNAME $b/uevent 2>/dev/null | cut -d= -f2 || echo -); done"
    )
    items = {
        "partition_table.txt": script,
        "proc_cmdline.txt": "cat /proc/cmdline",
        "lpdump_super.txt": "lpdump /dev/block/by-name/super 2>&1 || lpdump 2>&1",
        "getprop_gsi.txt": "getprop",
        "by-name.txt": "ls -l /dev/block/by-name/",
    }
    for fname, cmd in items.items():
        txt = adb.try_shell(cmd, timeout=60)
        if txt:
            (d / fname).write_text(txt + "\n", encoding="utf-8")
    try:
        cfg = subprocess.run([adb.exe, "-s", adb.serial, "exec-out", "cat /proc/config.gz"],
                             capture_output=True, timeout=60).stdout
        if cfg[:2] == b"\x1f\x8b":
            (d / "kernel_config.gz").write_bytes(cfg)
    except subprocess.TimeoutExpired:
        pass
    # RKDevTool parameter 형식 참고본 (섹터 단위, 절대 LBA)
    pt = d / "partition_table.txt"
    if pt.exists():
        parts = []
        for line in pt.read_text(encoding="utf-8").splitlines():
            f = line.split()
            if len(f) == 4 and f[1].isdigit() and f[3] != "-":
                parts.append((int(f[1]), int(f[2]), f[3]))
        parts.sort()
        spec = ",".join(
            (f"-@0x{s:08x}({nm}:grow)" if nm == "userdata" else f"0x{sz:08x}@0x{s:08x}({nm})")
            for s, sz, nm in parts)
        (d / "parameter_reconstructed.txt").write_text(
            "# 참고용 재구성 (실측 sysfs 기준). 그대로 플래시하기 전에 원본 parameter와 대조할 것\n"
            f"CMDLINE: mtdparts=rk29xxnand:{spec}\n", encoding="utf-8")


def crosscheck(out: Path) -> list[str]:
    lines: list[str] = []
    for name, sha in KNOWN_STOCK_SHA256.items():
        f = out / f"{name}.img"
        if not f.exists():
            lines.append(f"[----] {name}: 덤프 파일 없음")
            continue
        ok = sha256_file(f) == sha
        lines.append(f"[{'PASS' if ok else 'FAIL'}] {name}: 기존 RKDevTool 백업과 SHA-256 {'일치' if ok else '불일치'}")

    boot = out / "boot.img"
    zpath = BACKUP_DIR / "boot.img.zip"
    if boot.exists():
        data = boot.read_bytes()
        lines.append(f"[{'PASS' if data[:8] == b'ANDROID!' else 'FAIL'}] boot: 헤더 매직 {data[:8]!r}")
        if data[:8] != b"ANDROID!":
            return lines
        if zpath.exists():
            old = zipfile.ZipFile(zpath).read("boot.img")
            same = data[:BOOT_PARTIAL_VALID] == old[:BOOT_PARTIAL_VALID]
            lines.append(f"[{'PASS' if same else 'FAIL'}] boot: 앞 5MB가 기존 부분 백업과 {'일치' if same else '불일치'}")
        ks, _, rs, _, ss, _, _, ps, hv = struct.unpack_from("<9I", data, 8)
        rd_off = ps * (1 + -(-ks // ps))
        rd = data[rd_off:rd_off + rs]
        cc = rd.count(0xCC) == len(rd)
        magic = rd[:4].hex()
        known = magic.startswith("1f8b") or magic in ("02214c18", "04224d18") or rd[:6] == b"070701"
        lines.append(f"[{'PASS' if (known and not cc) else 'FAIL'}] boot: header v{hv}, kernel {ks:,}B, "
                     f"ramdisk {rs:,}B @0x{rd_off:x} 매직 {magic} {'(0xCC 패딩!)' if cc else ''}")
    super_img = out / "super.img"
    if super_img.exists():
        with open(super_img, "rb") as f:
            f.seek(4096)
            ok = f.read(4) == LP_GEOMETRY_MAGIC
        lines.append(f"[{'PASS' if ok else 'FAIL'}] super: LP 메타데이터 geometry 매직 {'확인' if ok else '없음'}")
    return lines


def cmd_dump(a: argparse.Namespace) -> None:
    adb = Adb(resolve_adb(a.adb), a.serial)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    state_file = out / "state.json"
    state: dict = json.loads(state_file.read_text(encoding="utf-8")) if state_file.exists() else {}

    info("[1/6] ADB root 확인")
    if adb.state() != "device":
        die(f"ADB 상태가 '{adb.state()}' 입니다.")
    if adb.getprop("ro.gsid.image_running") != "1" and not a.force:
        die("DSU GSI로 부팅된 상태가 아닙니다 (ro.gsid.image_running != 1). reboot-dsu 먼저.")
    adb.run(["root"], timeout=30, check=False)
    time.sleep(2)
    adb.run(["wait-for-device"], timeout=90)
    if adb.shell("id -u") != "0":
        die("root를 얻지 못했습니다. userdebug GSI인지 확인하세요.")
    info("  root (uid=0) 확인")

    info("[2/6] 덤프 대상 조회")
    targets = build_targets(adb)
    total = sum(t.size for t in targets)
    for t in targets:
        info(f"  - {t.name:<14} {human(t.size):>12}  {t.src}" + (f" (skip={t.skip}, count={t.count})" if t.skip is not None else ""))
    info(f"  합계 {human(total)} ({len(targets)}개, userdata 제외)")

    info("[3/6] 공간 확인")
    adb.shell(f"mkdir -p {DEVICE_TMP}")
    avail = int(adb.shell(f"df -k {DEVICE_TMP} | tail -n 1").split()[3]) * 1024
    info(f"  기기 {DEVICE_TMP} 가용 {human(avail)} (DSU 임시 userdata)")
    if a.mode == "local" and total + 512 * MB > avail:
        die(f"기기 공간 부족: 필요 {human(total + 512 * MB)} > 가용 {human(avail)}. "
            "--mode stream 으로 PC 직결 스트리밍을 쓰거나 userdata를 키워 DSU를 재설치하세요.")

    info("[4/6] 기기 정보 수집 (파티션 테이블, cmdline, lpdump, kernel config)")
    collect_device_info(adb, out)

    info(f"[5/6] 덤프 ({a.mode} 모드)")
    for i, t in enumerate(targets, 1):
        pc_file = out / f"{t.name}.img"
        prev = state.get(t.name, {})
        if (not a.redo and prev.get("status") == "ok" and pc_file.exists()
                and pc_file.stat().st_size == t.size):
            info(f"\n({i}/{len(targets)}) {t.name}: 이전 실행에서 검증 완료 - 건너뜀")
            continue
        info(f"\n({i}/{len(targets)}) {t.name} {human(t.size)}")
        t0 = time.time()
        fn = dump_local if a.mode == "local" else dump_stream
        sha, status = fn(adb, t, pc_file, a.retries)
        info(f"   -> {status} ({time.time() - t0:.0f}초) {sha}")
        state[t.name] = {"src": t.src, "skip_sectors": t.skip, "size": t.size, "sha256": sha,
                         "status": status, "note": RESTORE_NOTES.get(t.name, ""),
                         "time": time.strftime("%Y-%m-%d %H:%M:%S")}
        state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    info("\n[6/6] 기존 백업 교차검증")
    checks = crosscheck(out)
    for line in checks:
        info("  " + line)
    write_manifest(out, state, checks)

    failed = [k for k, v in state.items() if v["status"] != "ok"]
    bad_checks = [c for c in checks if c.startswith("[FAIL]")]
    info("\n==================================================")
    if failed or bad_checks:
        info(f"미완료: 실패 {failed or '-'} / 교차검증 실패 {len(bad_checks)}건")
        info("같은 명령을 다시 실행하면 완료된 항목은 건너뛰고 실패분만 재시도합니다.")
        info("※ DSU를 지우거나 해제하지 마세요. 기기 쪽 사본이 사라집니다.")
        sys.exit(2)
    info(f"전체 완료: {out / 'MANIFEST.txt'}")
    info("다음: 덤프를 두 곳 이상에 보관하고 해시 확인 -> adb reboot -> gsi_tool wipe (가이드 8장)")


def write_manifest(out: Path, state: dict, checks: list[str]) -> None:
    with open(out / "MANIFEST.txt", "w", encoding="utf-8") as f:
        f.write("# AOC_10W1D (WT10S2CN20251225) DSU Full ROM 덤프 매니페스트\n")
        f.write(f"# 작성: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("# 검증: 블록 디바이스 SHA-256 == 기기 파일 SHA-256 == PC 파일 SHA-256\n")
        f.write("# 가이드: ../README.md\n\n")
        f.write(f"{'이름':<14} {'상태':<13} {'크기(B)':>14}  {'SHA-256':<64}  소스 / 비고\n")
        f.write("-" * 150 + "\n")
        for name, v in state.items():
            src = v["src"] + (f" skip={v['skip_sectors']}" if v.get("skip_sectors") is not None else "")
            note = f" / {v['note']}" if v.get("note") else ""
            f.write(f"{name:<14} {v['status']:<13} {v['size']:>14}  {v['sha256'] or '-':<64}  {src}{note}\n")
        f.write("\n# 교차검증\n")
        for c in checks:
            f.write(c + "\n")
    (out / "manifest.json").write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def cmd_crosscheck(a: argparse.Namespace) -> None:
    out = Path(a.out)
    for line in crosscheck(out):
        info(line)


# --------------------------------------------------------------------------
def main() -> None:
    p = argparse.ArgumentParser(description="AOC 10W1D DSU 기반 Full ROM 덤프 도구")
    p.add_argument("--adb", help=f"adb 경로 (기본: {DEFAULT_ADB} 또는 PATH)")
    p.add_argument("--serial", default=DEFAULT_SERIAL, help=f"기기 시리얼 (기본 {DEFAULT_SERIAL}, USB)")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("preflight", help="순정 OS 사전 점검 (읽기 전용)")
    s.add_argument("--userdata-gib", type=int, default=16)
    s.set_defaults(func=cmd_preflight)

    s = sub.add_parser("prepare-gsi", help="GSI .img.xz -> 512B 패딩 .img.gz")
    s.add_argument("image")
    s.add_argument("--output")
    s.add_argument("--level", type=int, default=6, help="gzip 압축 레벨")
    s.set_defaults(func=cmd_prepare_gsi)

    s = sub.add_parser("install-dsu", help="GSI 전송 + DSU 설치 화면 호출")
    s.add_argument("image_gz")
    s.add_argument("--userdata-gib", type=int, default=16)
    s.add_argument("--system-size", type=int, help="미지정 시 <image>.gz.size 파일 사용")
    s.add_argument("--force", action="store_true", help="기존 DSU가 있어도 진행")
    s.set_defaults(func=cmd_install_dsu)

    s = sub.add_parser("reboot-dsu", help="설치된 DSU GSI로 재부팅")
    s.add_argument("--method", choices=["shade", "service"], default="shade",
                   help="shade: 알림창을 열고 Restart 터치(기본) / service: DSU 서비스 직접 호출(보조)")
    s.set_defaults(func=cmd_reboot_dsu)

    s = sub.add_parser("dump", help="GSI(root)에서 전 파티션 덤프 + 검증")
    s.add_argument("--out", default=DEFAULT_PC_OUT)
    s.add_argument("--mode", choices=["local", "stream"], default="local",
                   help="local: 기기 tmp에 먼저 덤프 후 pull(기본) / stream: PC로 직접 스트리밍")
    s.add_argument("--retries", type=int, default=3)
    s.add_argument("--redo", action="store_true", help="이전에 완료된 항목도 다시 덤프")
    s.add_argument("--force", action="store_true", help="GSI 실행 여부 확인 생략")
    s.set_defaults(func=cmd_dump)

    s = sub.add_parser("crosscheck", help="PC 덤프를 기존 백업과 재대조")
    s.add_argument("--out", default=DEFAULT_PC_OUT)
    s.set_defaults(func=cmd_crosscheck)

    a = p.parse_args()
    if not a.serial:
        res = subprocess.run([resolve_adb(a.adb), "devices"], capture_output=True, text=True, timeout=15).stdout
        devs = [x.split()[0] for x in res.splitlines()[1:] if len(x.split()) >= 2]
        if len(devs) != 1:
            die(f"연결된 기기가 {len(devs)}대입니다. --serial 또는 ANDROID_SERIAL로 지정하세요: {devs}")
        a.serial = devs[0]
    try:
        a.func(a)
    except RuntimeError as e:
        die(str(e))
    except KeyboardInterrupt:
        die("사용자 중단. 같은 명령을 다시 실행하면 이어서 진행합니다.", 130)


if __name__ == "__main__":
    main()
