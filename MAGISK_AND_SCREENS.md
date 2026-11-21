# AOC 10W1D — Magisk 루팅과 부팅·충전·슬립·종료 화면 바꾸기

> [DSU 덤프 가이드](./DSU_DUMP_GUIDE.md)의 DSU 절차로 **순정 `boot.img`(64MB 전체)와 eMMC 전체 백업을 확보한 뒤** 진행하는 후속 가이드입니다. (전체 프로젝트 허브: [README](./README.md))
> 순서: ① boot를 되돌리는 복구 경로를 먼저 실측 → ② Magisk 루팅 → ③ 화면 교체.
>
> 이 문서는 **원리와 실측 기록**입니다. 따라 하기만 하려면 [초보자 안내서](./BEGINNER_GUIDE.md)를 보세요. 화면 교체는 이제 기기용 앱 **E-Ink 화면 바꾸기**(소스 [`app/`](./app/), APK는 Releases)로 사진을 골라 할 수 있고, 아래 §4~§6은 그 앱이 내부에서 하는 일입니다.

- 검증 기기·펌웨어: README와 같음 (AOC_10W1D, `WT10S2CN20251225`, Android 11)
- 검증일: 2026-11-14
- 결과: Magisk 30.7 루팅(SELinux Enforcing 유지), 부팅 로고·Android 부팅 애니메이션·꺼진 상태 충전·슬립·종료 화면 교체를 실기기에서 확인

> [!CAUTION]
> 본 문서의 작업은 `boot` 및 `logo` 파티션에 실제 쓰기(Write)를 수행합니다. 사전 백업 없이 진행하지 마십시오. **`waveform` 파티션은 기기 패널 고유의 튜닝 데이터이므로 절대 임의로 덮어쓰지 마십시오.**

---

## 목차

1. [먼저: 화면별로 담당하는 곳](#1-먼저-화면별로-담당하는-곳)
2. [복구 경로 실측 (boot에 쓰기 전에)](#2-복구-경로-실측-boot에-쓰기-전에)
3. [Magisk 루팅](#3-magisk-루팅)
4. [부팅 로고·충전·저전력 화면: logo 파티션](#4-부팅-로고충전저전력-화면-logo-파티션)
5. [슬립·종료 화면: /data/misc/eink](#5-슬립종료-화면-datamisceink)
6. [Android 부팅 애니메이션: Magisk 모듈](#6-android-부팅-애니메이션-magisk-모듈)
7. [되돌리기](#7-되돌리기)
8. [알려진 한계와 함정](#8-알려진-한계와-함정)
9. [English summary](#9-english-summary)

---

## 1. 먼저: 화면별로 담당하는 곳

전원을 켜서 쓰다가 끌 때까지 보이는 화면은 세 군데에서 나옵니다. 한 군데만 바꾸면 나머지는 순정 그대로입니다.

| 순서 | 화면 | 담당 | 바꾸는 법 | 확인 |
|:-:|:---|:---|:---|:-:|
| 1 | U-Boot 로고 | `logo` 파티션 type `0x1` | [§4](#4-부팅-로고충전저전력-화면-logo-파티션) | 확인 |
| 2 | 커널 로고 ("System booting…") | `logo` 파티션 type `0x2` | §4 | 확인 |
| 3 | **Android 부팅 애니메이션** (진행 막대, 가장 오래 보임) | `/odm/media/bootanimation.zip` | [§6](#6-android-부팅-애니메이션-magisk-모듈) | 확인 |
| — | 꺼진 상태 충전 (배터리 0~5단계) | `logo` 파티션 `0x4~0x80` | §4 | 확인 |
| — | 부팅 시 저전력 | `logo` 파티션 `0x100` | §4 | 미재현 |
| — | U-Boot/커널 쪽 종료 | `logo` 파티션 `0x200` | §4 | 미재현 |
| — | **슬립(대기)** | vendor hwcomposer → `/data/misc/eink/standby.png` | [§5](#5-슬립종료-화면-datamisceink) | 확인 |
| — | **종료** (Android에서 끌 때) | hwcomposer → `/data/misc/eink/poweroff.png` | §5 | 확인 |
| — | 충전 중·완충·저전력 슬립, 방전 종료 | hwcomposer → `standby_charge.png` 등 | §5 | 쓰이지 않는 것으로 보임 ([§8](#8-알려진-한계와-함정)) |

> 순정 `WeGallery`(갤러리)의 "대기 화면으로 지정" 기능은 메뉴 배열 누락 버그로 화면에 나오지 않습니다. 그 기능이 쓰는 `/data/misc/standby.png`는 이 펌웨어의 화면 표시에 쓰이지 않습니다.

---

## 2. 복구 경로 실측 (boot에 쓰기 전에)

boot가 깨지면 `adb reboot fastboot`도, DSU도 쓸 수 없습니다. **DSU도 순정 boot의 커널·ramdisk로 첫 단계를 부팅하기 때문입니다.** 그래서 Android 없이 boot를 되돌리는 방법을 먼저 실측했습니다. 아래 표의 시험은 모두 **순정과 같은 내용**을 쓰거나 **미사용 파티션**에 써서 위험을 없앴습니다.

| 경로 | Android 필요 | 실측 방법 | 결과 |
|:---|:-:|:---|:---|
| A. fastbootd `fastboot flash boot` | 진입 시 필요 | 순정 `boot.img`를 그대로 씀 | 성공 (Writing OKAY) |
| B. DSU root 셸 `dd` | DSU 설치 시 필요 | 순정 `boot.img`를 `dd` → 캐시 비우고 블록 SHA-256 비교 | 성공 (해시 일치) |
| **C. MaskROM + RKDevTool `Write by Address`** | **불필요** | 전부 0인 `backup` 파티션 한가운데(LBA `0x000BF800`)에 1MB 표식 → DSU root에서 읽어 확인 → 0으로 복원 | 성공 (정확한 주소 기록, 타 영역 무변경) |

알게 된 것:
- **RKDevTool의 주소는 eMMC 절대 섹터입니다.** 기본 행 주소(Misc `0x9000`, Boot `0xD800`, Recovery `0x2F800`)가 GPT 시작 섹터와 같습니다.
- **MaskROM(로더 usbplug)에서 쓰기는 32MB 제한이 없습니다.** README의 `0xCC` 제한은 읽기에만 해당합니다.
- RKDevTool `Run` 때 `Download IDB`가 실행되지만, 같은 로더라면 GPT·IDB 영역 내용은 바뀌지 않았습니다(덤프 해시 일치).
- `fastboot reboot bootloader`로 들어가는 U-Boot fastboot(`18D1:D00D`)는 Windows 드라이버가 따로 필요합니다. Google USB 드라이버의 inf에는 `4EE0`(fastbootd)만 있습니다. 그래서 `fastboot boot`(쓰기 없이 한 번만 부팅하는 시험)는 해 보지 못했습니다.
- `rkdeveloptool`(libusb)은 Rockchip 드라이버(`rockusb.sys`)에 묶인 장치를 열지 못합니다(`creating comm object failed`). RKDevTool GUI를 쓰세요.

### 2.1. 비상 복구 (boot가 깨져 Android가 안 뜰 때)

1. USB 분리 → 전원 버튼 10초(전원 차단) → **전원 버튼을 누른 채 USB 연결** → RKDevTool 하단에 `Found One MASKROM Device`
2. `Download Image` 탭: **Loader** 행 ☑ (RK3566 로더 `.bin`), **Boot** 행 ☑ 주소 `0x0000D800` + 순정 `boot.img`. **다른 행은 전부 체크 해제**
3. `Write by Address` ☑ → `Run` → `Download image OK`

`logo`는 같은 방법으로 주소 `0x007FB800`에 씁니다. 주소는 이 기기의 파티션 표 기준이므로, 다른 기기는 [DSU 덤프 가이드 §12](./DSU_DUMP_GUIDE.md#12-기기-정보-파티션-표-등)처럼 직접 확인하세요.

---

## 3. Magisk 루팅

### 3.1. 패치 (기기 화면 조작 없이, CLI)

Magisk APK(zip)에서 아래 파일을 꺼내 이름을 바꿉니다. 이 기기는 **arm64-v8a**입니다(`ro.product.cpu.abilist`, zygote64_32). 듀오칸 Pro 2는 32비트 유저스페이스라 armeabi-v7a를 썼지만, 여기서는 그대로 따라 하면 안 됩니다.

| APK 안 | 기기에서 이름 |
|:---|:---|
| `assets/boot_patch.sh`, `assets/util_functions.sh`, `assets/stub.apk` | 그대로 |
| `lib/arm64-v8a/libmagiskinit.so` | `magiskinit` |
| `lib/arm64-v8a/libmagiskboot.so` | `magiskboot` |
| `lib/arm64-v8a/libmagisk.so` | `magisk` |
| `lib/arm64-v8a/libinit-ld.so` | `init-ld` |
| `lib/arm64-v8a/libbusybox.so` | `busybox` |

```bash
adb shell mkdir -p /data/local/tmp/mk
adb push kit/. /data/local/tmp/mk/
adb push boot.img /data/local/tmp/mk/boot.img          # 순정 64MB
adb shell 'cd /data/local/tmp/mk && chmod 755 * && \
  export BOOTMODE=true KEEPVERITY=true KEEPFORCEENCRYPT=false PATCHVBMETAFLAG=false RECOVERYMODE=false LEGACYSAR=false ASH_STANDALONE=1 && \
  ./busybox sh boot_patch.sh /data/local/tmp/mk/boot.img'
adb pull /data/local/tmp/mk/new-boot.img magisk_patched_boot.img
```

- 일반 셸 권한으로 실행됩니다. 아무것도 쓰지 않습니다.
- 위 추출·이름 바꾸기·패치·결과 검사를 기기 안에서 한 번에 하는 스크립트: [`tools/aoc_magisk_patch.sh`](./tools/aoc_magisk_patch.sh) (기기의 `unzip` 사용, PC에 Python 불필요). 순정 boot `190133…`에서 위 실측과 **같은 결과**(`4f8136e2…`)가 나오는 것을 확인했습니다. 이 펌웨어에는 DocumentsUI가 없어 Magisk 앱의 "파일 선택 후 패치"는 쓸 수 없습니다.
- 플래그는 Magisk 앱이 이 기기에서 고르는 값과 같습니다: Android 11 system-as-root → `KEEPVERITY=true`, 암호화 없음 → `KEEPFORCEENCRYPT=false`, vbmeta 파티션 있음 → `PATCHVBMETAFLAG=false`.
- `Failed to patch`가 3번 나오는 것은 삼성 전용 커널 패턴이 없다는 뜻이라 정상입니다.

### 3.2. 패치 결과 검사

```bash
python tools/bootimg_check.py diff boot.img magisk_patched_boot.img
```

실측: kernel(31,682,568B)·second(RSCE 리소스)·dtb·cmdline·header v2가 모두 같고, **ramdisk만** 761,811B에서 917,439B로 바뀌었습니다. 파일은 64MB 안에 들어가고, 커널 영역의 바이트 차이는 0입니다.

vbmeta 플래그가 `2`(검증 비활성)이고 부트로더가 언락(orange) 상태라 vbmeta를 따로 고칠 필요가 없었습니다.

### 3.3. 플래시

```bash
adb install Magisk-v30.7.apk
adb reboot fastboot
fastboot flash boot magisk_patched_boot.img
fastboot reboot
```

- 부팅 후 PC에서 adb가 안 보이면 **USB 케이블을 다시 꽂으세요.** 이 기기에서 재부팅 뒤 자주 생기는 현상이고, Windows 장치 관리자에는 ADB 인터페이스가 정상으로 보입니다.
- `adb shell magisk -v` → `30.7:MAGISK:R`이고, su 링크는 `/vendor/bin/su`에 생깁니다.
- 다른 기기 사용자 보고: 첫 부팅에서 `magisk -v`가 `inaccessible or not found`였지만 `df`에 `magisk` tmpfs(`/debug_ramdisk`, `/debug_ramdisk/.magisk/worker`)가 있었습니다. Magisk 앱에서 설정하자 기기가 재시작됐고, 그 뒤로는 정상이었습니다. 검증 기기에서는 재현되지 않았고(첫 부팅부터 정상, "추가 설정" 안내 없음) 원인은 확인하지 못했습니다. PC에서 boot를 썼기 때문에 앱이 평소 채워 두는 `/data/adb/magisk`가 비어 있었고, 앱의 추가 설정이 그것을 채운 것으로 추정합니다. **이때 boot를 다시 쓸 필요는 없습니다.**

### 3.4. 첫 su 권한 요청 처리 시 주의점

E-Ink는 화면 갱신이 느립니다. 그래서 `adb shell su`를 처음 실행하면 허용 팝업이 10초 시간 초과로 거부되어 Magisk가 Shell을 '거부'로 자동 저장하기 쉽습니다. 그 뒤로는 팝업 없이 바로 `Permission denied`가 발생합니다.

- 대안: Magisk 앱 실행 ➔ **[슈퍼유저] 탭 ➔ "[SharedUID] 셸" 스위치 켜기** (사전에 셸 권한을 허용해 두는 것을 권장합니다).

---

## 4. 부팅 로고·충전·저전력 화면: logo 파티션

### 4.1. 형식 (`RKEL` / `GR04`)

| 위치 | 내용 |
|:---|:---|
| 0x00 | `RKEL`, u32 전체 크기, u32 width(1872), u32 height(1404), u32 엔트리 수(10), 버전 `1.00`(0x14) |
| 0x40부터 0x20바이트씩 | `GR04`, u32 0, u16 w, u16 h, u32 **type**, u32 offset, u32 size |
| 이미지 | **4bpp 그레이**, 픽셀 2개당 1바이트, **짝수 픽셀 = 하위 니블**. 가로 1872×1404로 저장 = 세로 화면 내용을 **시계방향 90°** 회전한 것 |

type: `0x1` U-Boot 로고, `0x2` 커널 로고, `0x4`·`0x8`·`0x10`·`0x20`·`0x40`·`0x80` 충전 0~5단계, `0x100` 저전력, `0x200` 종료. 모두 렌더링해서 확인했습니다.

### 4.2. 교체

```bash
python tools/eink_logo.py unpack logo.img logo_png/          # 순정 10장 보기 (세로/가로 PNG)
python tools/eink_logo.py verify logo.img                    # 풀었다 다시 조립 → 바이트 동일 확인
python tools/eink_logo.py pack logo.img logo_custom.img uboot=a.png kernel=b.png charge0=c0.png poweroff=p.png
adb push logo_custom.img /data/local/tmp/
adb shell su -c 'dd if=/data/local/tmp/logo_custom.img of=/dev/block/by-name/logo bs=1M conv=fsync; echo 3 > /proc/sys/vm/drop_caches; sha256sum /dev/block/by-name/logo'
```

- 입력 PNG는 세로 1404×1872(보이는 방향)이면 됩니다. 도구가 회전하고 16단계 그레이로 바꿉니다.
- `pack`은 지정한 엔트리의 픽셀만 바꾸고, 헤더와 엔트리 밖 영역이 원본과 같은지 검사합니다.
- **fastbootd는 `logo` 파티션을 모릅니다**(`Partition not found`). 쓰기와 원복은 `su dd` 또는 MaskROM(주소 `0x007FB800`)으로 합니다.
- U-Boot에는 `No invalid kernel logo in logo.img` 경고 처리가 있어, logo가 깨져도 부팅이 막히지는 않을 것으로 보입니다(시험하지 않음).

---

## 5. 슬립·종료 화면: /data/misc/eink

이 화면들은 앱이 아니라 vendor **`hwcomposer.rk30board.so`**가 그립니다. 화면 전원 모드가 바뀔 때 PNG를 읽어 E-Ink에 표시하며, 읽는 순서는 다음과 같습니다.

```
/data/misc/eink/standby.png            → 없으면 /vendor/media/standby.png
/data/misc/eink/poweroff.png           → 없으면 /vendor/media/poweroff.png
(standby_charge, standby_charge_full, standby_lowpower, poweroff_nopower 도 같은 방식)
```

실측 로그: `hwcomposer-drm: Open /data/misc/eink/standby.png success` → `in drawLogoPic begin`

- SELinux: `/data/misc/eink(/.*)?` → `rk_eink_data_file`(hwcomposer 읽기, system_app 쓰기 허용). 폴더는 이미 있습니다(system:system 0770).
- 규격: 순정 `/vendor/media/*.png`와 같은 **가로 1872×1404 PNG**(세로 내용을 시계방향 90° 회전).

```bash
# 세로로 만든 이미지를 가로로 저장: PIL 기준 im.rotate(-90, expand=True)
adb push eink/ /data/local/tmp/eink
adb shell su -c 'cp /data/local/tmp/eink/*.png /data/misc/eink/ && chown system:system /data/misc/eink/*.png && chmod 0644 /data/misc/eink/*.png && chcon u:object_r:rk_eink_data_file:s0 /data/misc/eink/*.png'
```

파티션에 쓰지 않고, 루팅만 필요합니다. 파일을 지우면 순정으로 돌아갑니다.

---

## 6. Android 부팅 애니메이션: Magisk 모듈

커널 로고 다음, Android가 뜰 때까지 가장 오래 보이는 "System booting, please wait…" + 진행 막대 화면은 **`/odm/media/bootanimation.zip`**입니다. logo 파티션만 바꾸면 "부팅 로고가 안 바뀌었다"고 느끼게 되는 이유가 이것입니다.

- 순정 규격: 1404×1872 **세로 그대로**(회전하지 않음), `desc.txt` = `1404 1872 1` / `p 0 0 part0`, PNG 6장, 1fps, **무압축 zip**
- `/odm`은 super 안의 읽기 전용 파티션이고, Magisk magic mount 대상이 아닙니다 → 모듈의 `post-fs-data.sh`에서 **bind mount**로 덮어씁니다.

```bash
python tools/make_bootanim_module.py Magisk-v30.7.apk out/                 # 예시 프레임
python tools/make_bootanim_module.py Magisk-v30.7.apk out/ --frames my/    # 내 PNG(1404x1872)
adb push out/eink_bootanim.zip /data/local/tmp/
adb shell su -c 'magisk --install-module /data/local/tmp/eink_bootanim.zip'
adb reboot
```

### 6.1. SELinux 레이블 지정 주의점 (실측)

| 시도 | 결과 |
|:---|:---|
| 원본과 같은 `oemfs` 레이블 지정 | `avc: denied { associate } … tcontext=labeledfs` — `/data`(f2fs)에는 적용 불가 |
| `vendor_file` | 적용 가능하나 `avc: denied { read } … scontext=u:r:bootanim:s0` 발생 ➔ AOSP 기본(안드로이드 로고) 애니메이션으로 대체됨 |
| **`system_file`** | 적용 가능 및 bootanim 정상 읽기 확인 ➔ 교체 성공 |

> 실기기에서 검증한 것은 같은 로직의 개인용 모듈(v2)입니다. 공개용 `make_bootanim_module.py`는 기본 프레임과 이름만 다릅니다.

---

## 7. 되돌리기

| 변경 | 되돌리는 법 |
|:---|:---|
| Magisk boot | Magisk 앱 [Magisk 제거 → 순정 이미지 복원], 또는 `fastboot flash boot boot.img`(순정), 또는 MaskROM 주소 `0x0000D800` |
| logo | `su dd`로 순정 `logo.img`, 또는 MaskROM 주소 `0x007FB800` |
| 슬립·종료 PNG | `su -c 'rm /data/misc/eink/*.png'` |
| 부팅 애니메이션 | Magisk [모듈]에서 삭제 → 재부팅 |

E-Ink 화면 바꾸기 앱을 썼다면 각 화면의 [순정으로]가 위 일을 대신합니다. boot가 깨졌을 때의 절차는 [RECOVERY.md](./RECOVERY.md)에 정리했습니다.

---

## 8. 알려진 한계와 함정

- **충전 중·완충·저전력 슬립(`standby_charge*.png`, `standby_lowpower.png`)과 방전 종료(`poweroff_nopower.png`)는 표시 조건을 재현하지 못했습니다.** 기기 사용자 관찰로는 이 펌웨어에서 배터리·충전 상태 화면은 **전원이 꺼진 상태에서 충전할 때(logo 파티션 `0x4~0x80`)만** 나타나며, 슬립 중에는 충전 여부와 관계없이 `standby.png`가 쓰입니다.
  - hwcomposer가 참조하는 속성은 `sys.power.connected`, `sys.power.status`, `sys.power.shutdown`, `ro.wetao.custom_standby`, `ro.need.white.with.standby`입니다.
  - 실제 기기에서는 USB 충전·100% 상태에서도 `sys.power.*`가 비어 있었습니다.
  - `setprop`/`resetprop`으로 11가지 조합을 넣어 슬립에 들어가 봤지만 항상 `standby.png`만 열렸습니다. 이 펌웨어에서 실제로 쓰이는지는 hwcomposer 역어셈블이 필요합니다(기여 환영).
  - 시험할 때는 `svc power stayon usb`로 CPU 절전을 막으세요. 화면이 꺼질 때 USB가 끊길 수 있습니다.
- `logo` 파티션의 저전력(`0x100`)·종료(`0x200`) 이미지는 기록했지만, 표시되는 상황은 확인하지 못했습니다.
- 재부팅 후 PC adb가 기기를 못 찾는 일이 잦습니다 → 케이블 재연결.
- 화면 잠금이 없으면 DSU 설치는 확인 창 없이 바로 시작됩니다([DSU 덤프 가이드 §5](./DSU_DUMP_GUIDE.md#5-2단계-dsu-설치) 참고).

---

## 9. English summary

**Prerequisite**: full stock backup via the DSU method in [DSU_DUMP_GUIDE.md](./DSU_DUMP_GUIDE.md) (stock `boot.img` 64 MB). Project overview: [README.md](./README.md).

**Recovery paths, verified before touching `boot`** (DSU also boots the stock boot's kernel/ramdisk, so a broken boot kills DSU too):
- fastbootd `fastboot flash boot` works (tested with the identical stock image).
- DSU root `dd` to `/dev/block/by-name/boot` works (block SHA-256 matched after `drop_caches`).
- **MaskROM + RKDevTool "Write by Address" writes past 32 MB fine** (the `0xCC` limit is read-only). Addresses are absolute eMMC sectors: boot `0x0000D800`, logo `0x007FB800`. A 1 MB marker written to the empty `backup` partition was found at the exact LBA from the DSU shell, and nothing else changed.

**Magisk (30.7)**: patch on-device with the CLI kit from the APK (arm64-v8a; `KEEPVERITY=true KEEPFORCEENCRYPT=false PATCHVBMETAFLAG=false`). Only the ramdisk changes (`tools/bootimg_check.py diff`). Flash with fastbootd. vbmeta flags are already `2` (verification disabled). On E-Ink the first `su` prompt easily times out and Magisk stores a *deny* for Shell, so enable Shell in the Superuser tab.

**Screens**:
- `logo` partition = `RKEL` header + 10 `GR04` 4bpp images (1872×1404 stored, i.e. portrait rotated 90° clockwise, low nibble first). Types: `0x1` U-Boot logo, `0x2` kernel logo, `0x4…0x80` off-charging 0–5, `0x100` low power, `0x200` power-off. Edit with `tools/eink_logo.py` and write with `su dd` (fastbootd does not know `logo`).
- Battery/charging screens only appear while charging with the device powered off (logo `0x4…0x80`); during sleep `standby.png` is used whether charging or not.
- Sleep / power-off screens are drawn by `hwcomposer.rk30board.so`, which reads `/data/misc/eink/{standby,poweroff,…}.png` before `/vendor/media/`. Copy 1872×1404 PNGs there (`system:system 0644`, `u:object_r:rk_eink_data_file:s0`). No partition write.
- The long "System booting…" progress-bar screen is `/odm/media/bootanimation.zip` (1404×1872 portrait, 1 fps, stored zip). Replace it with a Magisk module that bind-mounts its own zip in `post-fs-data` (`tools/make_bootanim_module.py`). **The file must be labeled `system_file`**: `oemfs` cannot be set on `/data`, and `vendor_file` is not readable by `bootanim`, which then falls back to the AOSP animation.

**Not reproduced**: charging, full and low-battery sleep variants and the dead-battery power-off image. Setting `sys.power.*` / `ro.wetao.custom_standby` at runtime always selected `standby.png`.
