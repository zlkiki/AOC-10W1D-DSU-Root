# AOC 10W1D (RK3566 E-Ink, Android 11) — DSU로 무분해·무플래시 root 셸 얻기와 순정 ROM 전체 백업

> 부트로더 언락 상태의 RK3566 Android 11 E-Ink 태블릿에서, **시스템 파티션에 한 바이트도 쓰지 않고** 임시 GSI(DSU)로 부팅해 `adb root` 셸을 얻고, eMMC 전체(boot 64MB 포함)를 백업하는 방법입니다.
>
> 이 기기에서 그대로 따라 하면 **"화면이 로고에서 멈추고 USB/ADB가 영영 안 잡히는"** 문제가 생깁니다. 이 가이드는 그 원인을 로그로 밝혀내고 해결한 과정과, 바로 쓸 수 있는 도구를 담고 있습니다.

- 검증 기기: **AOC_10W1D** (10.3" Carta E-Ink, Rockchip RK3566, 4GB/64GB, 와콤 EMR, 판매처 표기 `WT10S`, 펌웨어 `WT10S2CN20251225`, Android 11 `RQ2A.210505.003`, 커널 4.19.193)
- 검증일: 2026-11-14
- 결과: DSU 부팅 → GSI root ADB 확보 → 전 파티션 18개 덤프(블록 디바이스·기기 파일·PC 파일 SHA-256 3중 일치) → 순정 복귀까지 실측 완료
- **후속 가이드: [Magisk 루팅과 부팅·충전·슬립·종료 화면 바꾸기](./MAGISK_AND_SCREENS.md)** (2026-11-14 검증)
- 참고한 선례: [zhalps/Duokan-Pro2](https://github.com/zhalps/Duokan-Pro2) (샤오미 듀오칸 Pro 2, 같은 RK3566 + Android 11)

---

## 목차

1. [이 가이드가 필요한 이유](#1-이-가이드가-필요한-이유)
2. [먼저 읽기: 무엇을 하고 무엇을 하지 않는가](#2-먼저-읽기-무엇을-하고-무엇을-하지-않는가)
3. [준비물과 사전 조건 확인](#3-준비물과-사전-조건-확인)
4. [1단계: 진단 GSI 만들기](#4-1단계-진단-gsi-만들기)
5. [2단계: DSU 설치](#5-2단계-dsu-설치)
6. [3단계: GSI로 부팅하고 root 셸 얻기](#6-3단계-gsi로-부팅하고-root-셸-얻기)
7. [4단계: 전체 파티션 덤프](#7-4단계-전체-파티션-덤프)
8. [5단계: 순정으로 복귀하고 정리](#8-5단계-순정으로-복귀하고-정리)
9. [문제 해결](#9-문제-해결)
10. [원인 분석: 왜 그냥 DSU로는 안 되는가](#10-원인-분석-왜-그냥-dsu로는-안-되는가)
11. [진단 방법론: 화면도 ADB도 없는 부팅을 들여다보는 법](#11-진단-방법론-화면도-adb도-없는-부팅을-들여다보는-법)
12. [기기 정보 (파티션 표 등)](#12-기기-정보-파티션-표-등)
13. [다음 단계 아이디어 (미검증)](#13-다음-단계-아이디어-미검증)
14. [파일 목록](#14-파일-목록)
15. [English summary](#15-english-summary)
16. [감사와 라이선스](#16-감사와-라이선스)

---

## 1. 이 가이드가 필요한 이유

이 계열 기기에는 몇 가지 불편한 사정이 있습니다.

- 제조사가 **공식 펌웨어(복구 ROM)를 배포하지 않습니다.** 망가지면 되돌릴 이미지가 없습니다.
- Rockchip LOADER/MaskROM 모드에서 RKDevTool로 읽으면, 이 기기의 U-Boot는 **LBA 32MB 너머를 읽지 못하고 `0xCC`로 채워** 돌려줍니다. `boot`(64MB)는 앞부분만 유효하고, `super`(3GB)는 아예 읽을 수 없습니다.
- `fastbootd`는 `fetch` 명령을 지원하지 않습니다(`Device does not support fetch command`).
- U-Boot를 패치해 32MB 제한을 풀면, SPL이 FIT 이미지 해시 불일치로 로드를 거부합니다(실측).

남은 방법이 **DSU(Dynamic System Updates)** 입니다. 안드로이드 10부터 있는 공식 기능으로, `/data` 안의 파일에 임시 시스템(GSI)을 깔고 **한 번만** 그걸로 부팅합니다. phh Treble GSI는 `userdebug` 빌드라 `adb root`가 되고, root 셸에서는 `/dev/block/by-name/*`를 통째로 읽을 수 있습니다. 듀오칸 Pro 2 선례가 바로 이 방법입니다.

그런데 AOC 10W1D에서 선례를 그대로 따라 하면 이렇게 됩니다.

- `[다시 시작]`을 누르면 화면이 **부팅 로고("System booting, please wait...")에서 멈춥니다.**
- **USB 장치가 아예 잡히지 않습니다.** ADB도, fastboot도, Rockchip loader도 없습니다.
- 26분을 기다려도 그대로이고, 전원 버튼을 길게 눌러 끄면 순정으로 돌아옵니다.

처음에는 "A-only 기기 + 구형 4.19 커널이라 DSU가 안 된다"고 결론 내렸지만, **틀린 결론이었습니다.** 커널도 init도 DSU도 정상이었고, 문제는 **GSI가 부팅된 뒤 USB(adbd)가 켜지지 않는 것** 하나였습니다. 자세한 내용은 [10장](#10-원인-분석-왜-그냥-dsu로는-안-되는가)에 있습니다.

---

## 2. 먼저 읽기: 무엇을 하고 무엇을 하지 않는가

**하는 것**
- `/data` 안에 DSU 이미지 파일(약 2.3GB)과 임시 userdata(16GiB)를 만듭니다.
- `/metadata`에 DSU 상태 파일을 씁니다(안드로이드가 원래 하는 일).
- GSI로 **1회만** 부팅합니다. 그다음 부팅은 자동으로 순정입니다.
- GSI root 셸에서 블록 디바이스를 **읽기만** 합니다.

**하지 않는 것**
- `boot`, `recovery`, `super`, `uboot`, `waveform` 등 시스템·부트 파티션에 **쓰지 않습니다.**
- 부트로더를 언락하지 않습니다(이 기기는 **출고 시 이미 언락** 상태여야 합니다. [3장](#3-준비물과-사전-조건-확인) 확인).
- 사용자 데이터(`userdata`)는 덤프하지 않습니다.

**위험도**
- 이 절차의 실측 기준 위험은 낮습니다. DSU 부팅이 어떻게 되든 **전원 버튼 8~10초로 끄고 다시 켜면 순정으로 돌아왔습니다**(여러 차례 실측).
- 단, 모든 책임은 본인에게 있습니다. 기기·펌웨어가 다르면 결과가 다를 수 있습니다.

> ⚠️ 덤프한 `waveform`은 **패널마다 고유한 E-Ink 보정값**입니다. 다른 기기에 쓰지 마세요. 다른 사람의 덤프를 내 기기에 쓰는 것도 금지입니다.

---

## 3. 준비물과 사전 조건 확인

### 3.1. 준비물

| 항목 | 내용 |
|:---|:---|
| PC | Windows / Linux / macOS, [Android platform-tools](https://developer.android.com/tools/releases/platform-tools)(`adb`), Python 3.10+ |
| 이미지 빌드 환경 | **Linux 또는 WSL** (`e2fsprogs` 1.45+, `python3`, `curl`, `xz-utils`, `gzip`, `android-sdk-libsparse-utils`) |
| GSI | phh Treble **v313** `system-roar-arm64-ab-vanilla.img.xz` (AOSP 11, arm64, vanilla) — [phhusson/treble_experimentations releases](https://github.com/phhusson/treble_experimentations/releases) |
| 기기 저장 공간 | `/data` 여유 **30GB 이상** (임시 userdata 16GiB + GSI 2.3GB + 여유) |
| USB 케이블 | 데이터 전송 가능한 C 타입 케이블 |
| 배터리 | 60% 이상 권장 |

> GSI 선택: AOC는 64비트 유저랜드(`ro.zygote=zygote64_32`)이므로 **arm64** 이미지를 씁니다. 듀오칸 Pro 2는 32비트 유저랜드라 `arm32_binder64`를 썼습니다. 이 부분은 기기마다 다릅니다.

### 3.2. 기기 설정

1. 개발자 옵션 → **USB 디버깅 켜기**, PC 연결 후 RSA 키 허용.
2. `adb devices`에 `device`로 보이는지 확인.

### 3.3. 사전 조건 확인 (읽기 전용)

```bash
adb shell getprop ro.boot.flash.locked          # 0 이어야 함 (부트로더 언락)
adb shell getprop ro.boot.verifiedbootstate     # orange
adb shell getprop ro.boot.dynamic_partitions    # true
adb shell getprop ro.product.cpu.abi            # arm64-v8a
adb shell getprop ro.boot.slot_suffix           # (빈 값) = A-only. 그래도 DSU는 됩니다
adb shell gsi_tool status                       # normal
adb shell df -h /data                           # 여유 30GB 이상
adb shell mount | grep ' /metadata '            # /metadata 마운트 확인
```

또는 동봉 스크립트로 한 번에 확인합니다(읽기 전용).

```bash
python tools/aoc_full_rom_dump.py preflight
```

```
[PASS] 모델                     AOC_10W1D
[PASS] 부트로더 언락                flash.locked=0, vbstate=orange
[PASS] ABI (arm64 GSI 사용)     arm64-v8a
[PASS] 동적 파티션                 true
[PASS] /data 가용 공간            46.7 GB (필요 ≥ 30 GB: userdata 16 + GSI 4 + 여유 10)
[PASS] /metadata 마운트          /dev/block/mmcblk2p12 on /metadata
...
결과: FAIL 0건 / WARN 0건
```

`flash.locked`가 `1`이면 이 가이드는 그대로는 쓸 수 없습니다(서명되지 않은 GSI는 잠긴 부트로더에서 거부됩니다).

---

## 4. 1단계: 진단 GSI 만들기

phh 원본 GSI에 **파일 3개를 추가한 "진단 GSI"** 를 만듭니다. 이게 이 가이드의 핵심입니다.

| 추가 파일 | 역할 |
|:---|:---|
| `/system/etc/init/zz_dsu_diag.rc` | 부팅 단계(`early-init`·`init`·`late-init`·`post-fs-data`·`boot`)와 USB/adbd/zygote 상태 변화를 커널 로그에 기록. `late-init`에서 진단 서비스 시작 |
| `/system/bin/dsudiag.sh` | 30초마다 상태 기록. **150초에 adbd가 안 떠 있으면 `setprop sys.usb.config adb` + `start adbd`로 USB ADB를 강제로 켬.** 8분 뒤 자동 웜 재부팅(취소 가능) |
| `/system/build.prop` | `persist.sys.usb.config=adb` 한 줄 추가 |

> 진단 서비스는 SELinux `su` 도메인(phh userdebug 정책에서 permissive)으로 실행됩니다. init이 `su`로 전환하는 규칙(`allow init su (process (transition))`)이 phh 정책에 있는 것을 확인했습니다.

### 4.1. 빌드 (Linux/WSL)

```bash
sudo apt install e2fsprogs python3 curl xz-utils gzip android-sdk-libsparse-utils
cd tools
chmod +x build_diag_gsi.sh
./build_diag_gsi.sh ~/Downloads/system-roar-arm64-ab-vanilla.img.xz ./out
```

스크립트가 하는 일:

1. `.xz` 해제, sparse면 `simg2img`로 raw 변환
2. **AVB 꼬리표 제거**: phh 이미지 끝에는 dm-verity 해시트리 + vbmeta(`AVBf`)가 붙어 있습니다. `avbtool info_image`로 원래 파일시스템 크기를 읽어 그만큼만 잘라냅니다.
3. **`shared_blocks` 해제**: phh 이미지는 블록 중복 제거(`shared_blocks`) ext4라서 그대로는 파일을 추가할 수 없습니다. 4000MB로 늘린 뒤 `e2fsck -E unshare_blocks`로 풉니다(실사용 약 2.2GB, 2000MB로는 공간 부족).
4. `debugfs -w`로 파일 3개 주입, SELinux 라벨 `u:object_r:system_file:s0` 지정
5. `resize2fs -M`으로 최소 크기 축소
6. `avbtool add_hashtree_footer`로 **해시트리 재생성**(sha1, AOSP 테스트 키, FEC 생략) → `verify_image`로 검증
7. gzip 압축 + `KEY_SYSTEM_SIZE` 값을 `.size` 파일로 저장

실행 예(약 3~4분):

```
== 2. AVB 꼬리표 제거 (ext4 본체만 분리)
ext4 크기: 1585721344
== 3. 4000MB 확장 + shared_blocks 해제
/: 6396/17408 files (12.2% non-contiguous), 562931/1024000 blocks
== 4. 진단 파일 주입 (debugfs)
주입 및 SELinux 라벨 확인 완료
== 5. 축소 + AVB 해시트리 재생성 + 검증
system: Successfully verified sha1 hashtree of system.img for image of 2307375104 bytes
== 6. gzip + KEY_SYSTEM_SIZE
완료: ./out/aoc_dsu_diag_gsi.img.gz
KEY_SYSTEM_SIZE = 2325557248
```

결과물: `out/aoc_dsu_diag_gsi.img.gz`(약 930MB)와 `out/aoc_dsu_diag_gsi.img.gz.size`.

> 해시트리 서명은 AOSP 공개 테스트 키입니다. 부트로더가 언락(orange)이면 서명 키 불일치는 허용되고, 해시트리 자체는 수정된 내용과 일치하므로 dm-verity가 정상 동작합니다.

---

## 5. 2단계: DSU 설치

### 5.1. 이미지 전송

```bash
adb push out/aoc_dsu_diag_gsi.img.gz /storage/emulated/0/Download/
```

### 5.2. DSU 기능 플래그 켜기 (중요)

이걸 안 하면 설치 화면에서 버튼을 눌러도 아무 반응이 없습니다.

```bash
adb shell setprop persist.sys.fflag.override.settings_dynamic_system true
```

### 5.3. 설치 시작

`KEY_SYSTEM_SIZE`는 `.size` 파일 값(위 예시는 `2325557248`)을 그대로 씁니다. 임시 userdata는 16GiB(`17179869184`)로 잡습니다. 덤프 중 `super`(3GB)를 임시로 담아야 하기 때문입니다.

```bash
adb shell am start-activity \
  -n com.android.dynsystem/com.android.dynsystem.VerificationActivity \
  -a android.os.image.action.START_INSTALL \
  -d file:///storage/emulated/0/Download/aoc_dsu_diag_gsi.img.gz \
  --el KEY_SYSTEM_SIZE 2325557248 \
  --el KEY_USERDATA_SIZE 17179869184
```

또는 동봉 스크립트:

```bash
python tools/aoc_full_rom_dump.py install-dsu out/aoc_dsu_diag_gsi.img.gz --userdata-gib 16
```

태블릿에 확인 창이 뜨면 **[확인]**을 누릅니다. 설치는 약 **6~8분** 걸립니다. 진행률은 알림창에 표시되고, 끝나면 이런 알림이 뜹니다.

> **"동적 시스템이 준비되었습니다. 사용을 시작하려면 기기를 다시 시작하세요."** `[삭제]` `[다시 시작]`

> 참고: 설치 완료 직후에도 `gsi_tool status`는 `normal`로 보입니다. 정상입니다.

---

## 6. 3단계: GSI로 부팅하고 root 셸 얻기

### 6.1. 재부팅

알림의 **[다시 시작]**을 누릅니다.

> ⚠️ **전원 메뉴의 재시작을 쓰지 마세요.** DSU는 알림 버튼(1회성 부팅 활성화)으로만 진입합니다. 다른 방법을 섞으면 설치가 롤백될 수 있습니다(선례 경고).

PC에서 알림창을 열어 둘 수도 있습니다: `adb shell cmd statusbar expand-notifications`

### 6.2. 기다리기: 화면은 바뀌지 않습니다

- 화면은 부팅 로고에서 **그대로 멈춘 것처럼 보입니다.** 정상입니다. GSI에는 이 기기의 E-Ink 디스플레이 경로가 맞지 않아 화면을 갱신하지 못하고, E-Ink는 마지막 화면을 그대로 유지합니다.
- 진단 스크립트가 **150초 시점에 USB ADB를 강제로 켭니다.** 실측에서는 `[다시 시작]` 후 **약 2분 40초** 뒤 `adb devices`에 나타났습니다.

```bash
# 3분쯤 뒤
adb devices
# List of devices attached
# XXXXXXXXXXXX    device
```

### 6.3. root 전환과 자동 재부팅 취소 (8분 안에)

진단 GSI는 **8분 뒤 스스로 재부팅해서 순정으로 돌아가도록** 되어 있습니다(안전장치). 작업하려면 반드시 취소하세요.

```bash
adb root                 # restarting adbd as root
adb wait-for-device
adb shell id             # uid=0(root) ... context=u:r:su:s0
adb shell getprop ro.gsid.image_running    # 1  (DSU GSI로 부팅 중)
adb shell getprop ro.build.type            # userdebug
adb shell touch /data/local/tmp/dsudiag_stop   # ← 자동 재부팅 취소
```

### 6.4. 프레임워크 재시작 루프 멈추기

GSI 프레임워크(zygote/system_server/surfaceflinger)가 이 기기의 디스플레이 HAL과 맞지 않아 **약 5초마다 재시작을 반복**합니다. 덤프에는 필요 없으니 멈춥니다.

```bash
adb shell stop
adb shell getprop init.svc.zygote    # stopped
```

이제 커널과 기본 서비스만 도는 **root 셸**이 있습니다.

---

## 7. 4단계: 전체 파티션 덤프

### 7.1. 동봉 스크립트로 (권장, 실측에 쓴 방법)

```bash
python tools/aoc_full_rom_dump.py dump --out aoc_full_rom
```

동작:
- `/dev/block/by-name/` 전체를 자동 순회(`userdata`와 전체 디스크 노드 `mmcblk2` 제외) + GPT 앞부분(LBA 0 ~ uboot 직전, idbloader 포함)과 백업 GPT
- 각 항목마다 **블록 디바이스 SHA-256 = 기기 tmp 파일 SHA-256 = PC 파일 SHA-256** 3중 검증
- `MANIFEST.txt`, `manifest.json`, `device_info/`(파티션 표, RKDevTool parameter 재구성본, `lpdump`, `/proc/cmdline`, 커널 config, getprop) 생성
- 중단되면 같은 명령으로 이어서 진행(`state.json`)
- `boot` 헤더·ramdisk 매직, `super` LP 메타데이터 매직 자동 점검

실측(약 4분, 총 4.2GB):

```
(4/18) boot 64.0 MB      -> ok (4초)
(12/18) recovery 96.0 MB -> ok (6초)
(18/18) super 3.04 GB    -> ok (203초)
[PASS] boot: 헤더 매직 b'ANDROID!'
[PASS] boot: header v2, kernel 31,682,568B, ramdisk 761,811B @0x1e38000 매직 1f8b0800
[PASS] super: LP 메타데이터 geometry 매직 확인
```

**`boot`가 64MB 전체 유효**합니다. RKDevTool 덤프에서 `0xCC`로 채워지던 ramdisk 영역(0x1e38000 근처)까지 정상입니다.

### 7.2. 수동으로 (스크립트 없이)

```bash
adb shell 'mkdir -p /data/local/tmp/d && ls /dev/block/by-name'
for p in boot recovery dtbo vbmeta uboot trust misc security waveform logo backup metadata super; do
  adb shell "dd if=/dev/block/by-name/$p of=/data/local/tmp/d/$p.img bs=4M && sha256sum /dev/block/by-name/$p /data/local/tmp/d/$p.img"
  adb pull /data/local/tmp/d/$p.img
  sha256sum $p.img      # 위 두 값과 같아야 함
  adb shell rm /data/local/tmp/d/$p.img
done
```

> Windows Git Bash에서는 `/data/...` 경로가 변환되지 않도록 `export MSYS_NO_PATHCONV=1`을 먼저 실행하세요.

### 7.3. 보관 시 주의

| 파일 | 주의 |
|:---|:---|
| `waveform.img` | 기기 고유 E-Ink 보정값. 다른 기기에 절대 쓰지 말 것 |
| `metadata.img` | DSU 실행 중 상태(`/metadata/gsi`)가 들어 있음. 순정 복원에 쓰지 말 것 |
| `cache.img` | 로그/임시 데이터. 복원 불필요 |
| `gpt_head.img` | GPT + idbloader. 최후 수단 복원 전용 |
| `super.img` | system/system_ext/vendor/odm/product 묶음(3GB). 압축 보관 권장 |

**최소 두 곳**에 보관하고 해시를 다시 확인하세요.

---

## 8. 5단계: 순정으로 복귀하고 정리

```bash
adb reboot              # GSI에서 재부팅 → 1회성 부팅이므로 순정으로 돌아옴
# 순정 부팅 후 (PC에서 기기가 안 보이면 USB 케이블을 뽑았다 다시 꽂기)
adb shell getprop ro.build.type     # user
adb shell gsi_tool status           # installed / disabled
adb shell gsi_tool wipe             # Live image install successfully removed.
adb shell gsi_tool status           # normal
adb shell setprop persist.sys.fflag.override.settings_dynamic_system false
adb shell am force-stop com.android.dynsystem    # 남은 DSU 알림 제거
adb shell rm /storage/emulated/0/Download/aoc_dsu_diag_gsi.img.gz
```

`gsi_tool wipe`로 DSU 영역(약 18GB)이 회수되고 기기는 완전히 원래 상태가 됩니다.

다시 root 셸이 필요하면 [5단계](#5-2단계-dsu-설치)부터 반복하면 됩니다(이미지는 재사용 가능).

---

## 9. 문제 해결

| 증상 | 원인 / 조치 |
|:---|:---|
| 설치 화면에서 버튼을 눌러도 반응 없음 | DSU 기능 플래그 누락 → `setprop persist.sys.fflag.override.settings_dynamic_system true` |
| `[다시 시작]` 후 화면이 로고에서 멈춤 | **정상.** GSI가 E-Ink 화면을 갱신하지 못함. 화면으로 판단하지 말고 ADB로 판단 |
| 3~4분이 지나도 `adb devices`가 비어 있음 | ① USB 케이블을 뽑았다 다시 꽂기 ② 장치 관리자에 VID `2207`(Rockchip) 장치가 보이는지 확인 ③ 원본 phh GSI를 쓴 경우 → **진단 GSI를 써야 함**(10장) |
| 순정으로 재부팅한 뒤 PC `adb devices`에 기기가 안 보임(장치 관리자에는 보임) | 이 기기에서 자주 재현됨. **USB 케이블을 뽑았다 다시 꽂으면** 해결 |
| `adb devices`에 `unauthorized` | GSI 쪽 ADB 키 문제. phh 이미지는 `ro.adb.secure=0`이라 원래 안 생겨야 함. 진단 GSI가 맞는지 확인 |
| 8분 뒤 저절로 재부팅됨 | 진단 GSI의 안전장치. `adb shell touch /data/local/tmp/dsudiag_stop`으로 취소 |
| 순정으로 돌아가고 싶음 | `adb reboot`(GSI에서) 또는 전원 버튼 8~10초 → 다시 켜기. 1회성 부팅이라 항상 순정으로 돌아옴 |
| 전원 버튼을 길게 눌렀더니 다시 켜지지 않음 | 이 기기의 PMIC는 길게 누르기(약 8~9초) = **전원 차단**. 다시 눌러 켜면 됨 |
| 설치 중 공간 부족 | `/data` 여유 30GB 이상 필요. 임시 userdata를 줄이면 `super` 덤프 시 공간 부족 가능 → 7.1 스크립트의 `--mode stream`(PC로 직접 스트리밍) 사용 |

---

## 10. 원인 분석: 왜 그냥 DSU로는 안 되는가

### 10.1. 처음의 오판

처음 두 번(phh vanilla, vndklite) 실패한 뒤 이렇게 결론 냈습니다: *"듀오칸은 A/B 기기라서 됐고, AOC는 A-only + Rockchip 4.19 커널이라 DSU 루프백을 지원하지 않아 커널 패닉이 난다."*

**근거가 없었습니다.**
- AOSP DSU는 부트로더 슬롯 전환으로 동작하지 않습니다. **1단계 init**(`first_stage_mount`)이 `/metadata/gsi/dsu/`를 읽고 `system`을 DSU 이미지로 바꿔 끼웁니다. 필수 조건은 **동적 파티션 + `/metadata`** 이고, AOC는 둘 다 충족합니다.
- 듀오칸 선례 자체가 "Rockchip + Android 11 + 커널 4.19" 조합입니다.
- "로고에서 멈춤"은 선례 문서에도 **정상 증상**이라고 적혀 있습니다(GSI에 E-Ink 드라이버 없음).

### 10.2. 실제로 일어난 일 (커널 로그 실측)

진단 GSI v2의 커널 로그(GSI root 셸에서 `dmesg`로 회수. 1차 진단에서는 11장의 ramoops 방법으로 같은 단계까지 확인):

```
[    1.542853] init: init first stage started!
[    1.602616] init: Failed to copy /avb into /metadata/gsi/dsu/avb/: No such file or directory   ← 무해
[    1.605639] init: [libfs_mgr]Created logical partition system on device /dev/block/dm-0
[    2.070509] init: Loading SELinux policy
[    5.085635] init: init second stage started!
[    5.620314] DSUDIAG: stage early-init
[    6.230959] DSUDIAG: stage late-init
[   11.986349] DSUDIAG: stage post-fs-data
[   12.824057] DSUDIAG: stage boot
[   12.914795] DSUDIAG: sys.usb.config=adb,mtp          ← 여기가 문제
[   12.915918] DSUDIAG: init.svc.zygote=restarting
[   17.913099] DSUDIAG: init.svc.zygote=restarting       ← 약 5초마다 반복
[   36.433408] DSUDIAG: t=30s usb.config=adb,mtp usb.state= adbd= zygote=running ...
[   36.501542] DSUDIAG: t=30s udc_g1=[] udc_list=[fcc00000.dwc3 ] udc_state=[not attached ]
   ... (150초까지 동일: adbd는 한 번도 시작되지 않음)
[  157.352075] DSUDIAG: forcing USB adb: setprop sys.usb.config adb + start adbd
[  157.371513] DSUDIAG: sys.usb.config=adb
[  157.372791] DSUDIAG: init.svc.adbd=running
[  157.405188] DSUDIAG: sys.usb.state=adb
[  165.469323] DSUDIAG: after force: usb.config=adb usb.state=adb adbd=running udc_g1=[fcc00000.dwc3]
```

커널, 1·2단계 init, `post-fs-data`, `boot`까지 **모두 정상**이었습니다.

### 10.3. 근본 원인

1. **USB 설정 트리거 불일치**
   - `init.usb.rc`의 `on boot && property:persist.sys.usb.config=*` → `setprop sys.usb.config ${persist.sys.usb.config}` 로 `sys.usb.config=adb,mtp`가 됩니다.
   - 그런데 USB 가젯을 실제로 구성하는 트리거는 GSI의 `/system/etc/init/hw/init.usb.configfs.rc`와 순정 vendor의 `/vendor/etc/init/hw/init.rk30board.usb.rc` 모두 **`sys.usb.config=mtp,adb`와 `=adb` 등만** 정의되어 있고, **`adb,mtp` 순서는 없습니다.**
   - 결과: 가젯 구성 없음, `adbd` 미시작, UDC(`fcc00000.dwc3`) 미연결 → **PC에서 USB 장치가 아예 안 보임.** 순정 OS는 `persist.sys.usb.config=mtp,adb`라 문제가 없습니다.
   - (`adb,mtp` 값이 정확히 어디서 만들어지는지는 추적하지 못했습니다.)
2. **프레임워크 재시작 루프**
   - zygote가 약 5초마다 재시작합니다(`surfaceflinger`, `vendor.hwcomposer-2-1`, `audioserver`도 `restarting`). Rockchip E-Ink 디스플레이 HAL과 순수 AOSP 프레임워크가 맞지 않는 것으로 보입니다.
   - 정상이라면 system_server의 UsbDeviceManager가 USB 설정을 다시 맞추지만, system_server가 끝내 안정화되지 않아 그 기회도 없습니다. `sys.boot_completed`도 설정되지 않습니다.
3. **E-Ink 화면 유지**: 화면이 부트로더 로고 그대로라 "멈춤"처럼 보입니다.

→ 해결: `sys.usb.config`를 **`adb`** 로 바꾸면 기존 트리거(`=adb`)가 걸려 가젯이 구성되고 adbd가 뜹니다. 진단 GSI는 이걸 150초 시점에 자동으로 합니다.

### 10.4. 확인된 부수 사실

- phh v313 vanilla의 `build.prop`에는 이미 `ro.adb.secure=0`이 있습니다 → ADB 인증 문제는 아님.
- GSI에서 SELinux는 **Permissive**로 동작했습니다.
- phh의 `phhsu_daemon`이 부팅 중 DSU system을 재마운트하고 `resize2fs`로 확장합니다(무해).
- DSU 1회성 부팅에서는 1단계 init이 DSU로 가기로 결정하는 순간 `/metadata/gsi/dsu/install_status`를 `disabled`로 바꿉니다. 그래서 GSI가 어떻게 되든 다음 부팅은 순정입니다. 순정으로 돌아온 뒤 `gsi_tool status`가 `installed / disabled`이면 **DSU 부팅이 실제로 시도되었다는 증거**입니다.

---

## 11. 진단 방법론: 화면도 ADB도 없는 부팅을 들여다보는 법

비슷한 문제를 다른 기기에서 겪는 분을 위해, 이번에 쓴 방법을 정리합니다. 분해(UART)는 쓰지 않았습니다.

### 11.1. ramoops(pstore)로 직전 부팅의 커널 로그 회수

- Rockchip 커널은 보통 ramoops가 켜져 있습니다(`ramoops: attached 0xf0000@0x110000`). **웜 재부팅**이면 직전 부팅의 커널 로그가 RAM에 남습니다.
- user 빌드의 shell은 `/sys/fs/pstore`를 못 읽지만, **`adb bugreport`는 dumpstate가 root로 돌기 때문에** `------ LAST KMSG (/sys/fs/pstore/console-ramoops-0) ------` 섹션에 그 로그를 담아 줍니다.

```bash
adb bugreport after.zip
unzip after.zip -d after
grep -n "^------ LAST KMSG" after/bugreport-*.txt
```

- 확인 방법: 순정에서 `adb reboot` 한 번 → bugreport에 `LAST KMSG`가 있고 직전 세션 로그가 들어 있으면 사용 가능합니다.

### 11.2. 함정 1: 전원 버튼 길게 누르기는 로그를 지운다

- 이 기기의 RK817 PMIC는 전원 버튼 약 8~9초 = **전원 차단**입니다(재시작 아님). RAM이 지워져 `LAST KMSG`가 사라집니다(`*** Error dumping /proc/last_kmsg ... No such file or directory`).
- 그래서 **GSI가 스스로 소프트웨어 재부팅**하게 만들었습니다: 진단 서비스가 일정 시간 뒤 `setprop sys.powerctl reboot`를 실행합니다.

### 11.3. 함정 2: vendor가 콘솔 로그 레벨을 낮춘다

- 첫 진단에서는 6초 이후 메시지가 ramoops에 하나도 없었습니다. vendor init이 `/proc/sys/kernel/printk`를 낮춰, 그 이후 메시지가 콘솔(=ramoops)로 가지 않았기 때문입니다.
- 해결: 매 기록마다 `echo 8 > /proc/sys/kernel/printk`를 하고, `/dev/kmsg`에 `<2>` 우선순위로 씁니다.

### 11.4. 함정 3: E-Ink 화면은 증거가 아니다

전원이 끊겨도 마지막 화면이 남습니다. "로고에서 멈춤"은 커널이 죽었는지 살았는지 전혀 알려주지 않습니다. 판단은 USB 열거, `gsi_tool status`, 커널 로그로 하세요.

### 11.5. 그 밖의 판별 신호

| 신호 | 의미 |
|:---|:---|
| 복귀 후 `gsi_tool status` = `installed / disabled` | 1단계 init이 DSU 부팅을 결정했음 (커널 단계 실패 아님) |
| 오래 기다려도 스스로 재부팅하지 않음 | 커널 패닉(보통 자동 재부팅)이나 init 치명 오류(부트로더로 재부팅 → USB에 loader 장치 등장)가 아님 |
| PC 장치 관리자에 VID `2207:350A`(Rockusb) / `18D1`(fastboot) 등장 | init 치명 오류로 부트로더 진입 |
| 재부팅 직전 `sysrq: Show Blocked State` 목록 | init이 `sys.powerctl`로 재부팅할 때 남는 D 상태 태스크 목록. 어디서 막혔는지 단서 |

---

## 12. 기기 정보 (파티션 표 등)

eMMC는 `mmcblk2`, 섹터 512B, 총 122,142,720 섹터(약 58.2GiB).

| # | 이름 | 시작 섹터 | 크기(섹터) | 크기 | 비고 |
|---:|:---|---:|---:|---:|:---|
| — | (GPT + idbloader) | 0 | 16,384 | 8MB | `gpt_head` |
| p1 | uboot | 16,384 | 8,192 | 4MB | FIT 이미지 |
| p2 | trust | 24,576 | 8,192 | 4MB | |
| p3 | waveform | 32,768 | 4,096 | 2MB | **기기 고유** |
| p4 | misc | 36,864 | 8,192 | 4MB | |
| p5 | dtbo | 45,056 | 8,192 | 4MB | |
| p6 | vbmeta | 53,248 | 2,048 | 1MB | |
| p7 | boot | 55,296 | 131,072 | 64MB | header v2, ramdisk @0x1e38000 |
| p8 | security | 186,368 | 8,192 | 4MB | |
| p9 | recovery | 194,560 | 196,608 | 96MB | fastbootd |
| p10 | backup | 391,168 | 786,432 | 384MB | |
| p11 | cache | 1,177,600 | 786,432 | 384MB | |
| p12 | metadata | 1,964,032 | 32,768 | 16MB | ext4, first_stage_mount |
| p13 | super | 1,996,800 | 6,373,376 | 3.04GB | 동적 파티션 그룹 `rockchip_dynamic_partitions` |
| p14 | logo | 8,370,176 | 32,768 | 16MB | |
| p15 | userdata | 8,402,944 | 113,739,712 | 54.2GB | f2fs, 암호화 없음(`ro.crypto.state=unsupported`) |

`super` 안: `system`, `system_ext`, `vendor`, `odm`, `product` (A-only, 슬롯 접미사 없음). `mmcblk2boot0/1`(각 4MB)도 덤프 대상에 포함됩니다.

기타 실측값: `ro.boot.flash.locked=0`, `verifiedbootstate=orange`, `ro.zygote=zygote64_32`, `ro.product.first_api_level=30`, `ro.vndk.version=30`, `ro.treble.enabled=true`, `ro.vendor.eink=true`, ramoops `0xf0000@0x110000`.

---

## 13. 다음 단계 아이디어 (미검증)

이 문서는 **백업까지** 다룹니다. Magisk 루팅과 화면 교체는 [MAGISK_AND_SCREENS.md](./MAGISK_AND_SCREENS.md)에서 검증했습니다. 아래는 아직 시도하지 않은 내용입니다.

- **더 단순한 진단 GSI**: `build.prop`에 `persist.sys.usb.config=mtp,adb`를 넣거나, `.rc`에 `on boot` → `setprop sys.usb.config adb` 한 줄만 넣어도 될 것으로 보입니다(150초 대기 없이 바로 ADB).
- ~~Magisk 루팅~~ → 검증 완료: [MAGISK_AND_SCREENS.md](./MAGISK_AND_SCREENS.md) (복구 경로 실측 후 fastbootd로 플래시)
- **Google 공식 GSI**(`aosp_arm64-exp-RP1A.200720.009`)는 다운로드와 변환까지만 해 두고 부팅은 하지 않았습니다.

---

## 14. 파일 목록

```
AOC-10W1D-DSU-Root/
├── README.md                  ← 이 문서 (DSU root 셸·전체 백업)
├── MAGISK_AND_SCREENS.md      ← 후속: Magisk 루팅, 부팅·충전·슬립·종료 화면 교체
├── LICENSE                 ← MIT
└── tools/
    ├── build_diag_gsi.sh      ← phh GSI → 진단 GSI 빌드 (Linux/WSL)
    ├── zz_dsu_diag.rc         ← GSI에 주입되는 init 스크립트
    ├── dsudiag.sh             ← GSI에 주입되는 진단/USB 강제 스크립트
    ├── aoc_full_rom_dump.py   ← preflight / install-dsu / reboot-dsu / dump / crosscheck
    ├── bootimg_check.py       ← boot 이미지 섹션 비교 (Magisk 패치 검증)
    ├── eink_logo.py           ← logo 파티션(RKEL/GR04) 풀기·조립·검증
    └── make_bootanim_module.py ← /odm/media/bootanimation.zip 교체 Magisk 모듈 생성
```

`aoc_full_rom_dump.py`는 `adb`가 PATH에 있어야 하고, 기기가 1대만 연결되어 있으면 자동으로 선택합니다(여러 대면 `--serial` 또는 `ANDROID_SERIAL`).

---

## 15. English summary

**Target**: AOC_10W1D (Rockchip RK3566, Android 11, A-only + dynamic partitions, bootloader unlocked from factory, 10.3" E-Ink). Probably applicable to similar Rockchip RK3566 Android 11 e-ink readers.

**Goal**: get a temporary root shell via DSU (no flashing) and dump the whole eMMC, because the vendor ships no firmware and RKDevTool/U-Boot can't read past LBA 32MB (`0xCC` filler).

**Problem**: following the Duokan Pro 2 method, the device "hangs" on the boot logo and no USB device ever appears. It is **not** an A-only/kernel limitation. Kernel, first/second stage init, `post-fs-data` and `boot` all run fine. The real causes:
1. `sys.usb.config` becomes `adb,mtp`, but both GSI `init.usb.configfs.rc` and the vendor `init.rk30board.usb.rc` only have triggers for `mtp,adb` / `adb`. So the USB gadget is never configured and adbd never starts.
2. The GSI framework (zygote/surfaceflinger/hwcomposer) crash-loops every ~5 s on the Rockchip E-Ink display HAL, so system_server never fixes the USB config.
3. E-Ink keeps the last frame, so it looks frozen.

**Fix**: inject a small init script into the phh GSI that runs `setprop sys.usb.config adb` + `start adbd` (at 150 s). `adb root` then works (~2:40 after tapping Restart).

**Steps**: `tools/build_diag_gsi.sh` (strip AVB footer → grow + `e2fsck -E unshare_blocks` → inject files with `debugfs` → shrink → `avbtool add_hashtree_footer`) → push → `setprop persist.sys.fflag.override.settings_dynamic_system true` → `am start-activity ... START_INSTALL --el KEY_SYSTEM_SIZE <size> --el KEY_USERDATA_SIZE 17179869184` → tap **Restart** in the notification → `adb root` → `touch /data/local/tmp/dsudiag_stop` (cancels the 8-min auto reboot) → `stop` → `python tools/aoc_full_rom_dump.py dump` → `adb reboot` → `gsi_tool wipe`.

**Follow-up**: Magisk root and boot/charging/sleep/power-off screen replacement are verified in [MAGISK_AND_SCREENS.md](./MAGISK_AND_SCREENS.md).

**Debug tips**: `adb bugreport` includes `LAST KMSG` (ramoops) of the previous boot even on user builds, but only after a *warm* reboot. Long-pressing power on this PMIC cuts power and erases it, so make the GSI reboot itself (`setprop sys.powerctl reboot`). Vendor init lowers the console loglevel, so write `8` to `/proc/sys/kernel/printk` and log with `<2>` priority.

---

## 16. 감사와 라이선스

- [zhalps/Duokan-Pro2](https://github.com/zhalps/Duokan-Pro2): RK3566 E-Ink 기기에서 DSU로 boot를 덤프하는 아이디어와 절차(기능 플래그, `am start-activity`, 512B 정렬 + gzip).
- [phhusson/treble_experimentations](https://github.com/phhusson/treble_experimentations): phh Treble GSI.
- AOSP [`external/avb`](https://android.googlesource.com/platform/external/avb/): `avbtool`, 테스트 키.

이 문서와 `tools/`의 스크립트는 [MIT License](./LICENSE)로 배포합니다. 자유롭게 사용·수정·배포할 수 있으며, 기기 손상에 대한 책임은 사용자에게 있습니다.

공개 저장소: <https://github.com/zlkiki/AOC-10W1D-DSU-Root>
