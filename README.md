# AOC 10W1D (RK3566 E-Ink, Android 11) — DSU 기반 Full ROM 백업, Magisk 루팅 및 시스템 제어

Rockchip RK3566 기반 Android 11 E-Ink 태블릿(AOC 10W1D)을 위한 DSU 기반 엔지니어링 툴킷 및 기술 문서입니다. 시스템 파티션 수정 없이 임시 DSU(Dynamic System Updates) 진단 GSI 환경에서 `adb root`를 활성화하여 eMMC 18개 파티션 전체(64MB boot 포함) 덤프, Magisk 30.7 시스템리스 루팅, E-Ink 화면 리소스 제어 및 MaskROM 비상 복구 절차를 다룹니다.

- **대상 기기**: `AOC_10W1D` (10.3" Carta E-Ink, Rockchip RK3566, 4GB RAM, 64GB eMMC, 와콤 EMR, 판매처 표기 `WT10S`, 펌웨어 `WT10S2CN20251225`, Android 11 `RQ2A.210505.003`, 커널 4.19.193)
- **검증 상태**: 검증 기기 1대에서 전 과정 실측 (2026-11-14 ~ 2026-11-15). 다른 AOC 기기에서 초보자 안내서를 따라 한 사용자 보고 1건(성공, 첫 부팅 때 Magisk 확인 단계에서 차이 → [안내서 5.3](./BEGINNER_GUIDE.md#53-루팅-확인과-셸-허용)에 반영)
- **공개 저장소**: <https://github.com/zlkiki/AOC-10W1D-DSU-Root> (MIT License)
- **릴리즈 배포**: [Releases v2026.11.14](https://github.com/zlkiki/AOC-10W1D-DSU-Root/releases/latest) (클린 진단 GSI, 전용 앱, 테마팩, 자동화 도구)
- **선례 참조**: [zhalps/Duokan-Pro2](https://github.com/zhalps/Duokan-Pro2) (샤오미 듀오칸 Pro 2 선례)

---

## 핵심 기능 및 기술 성과

1. **비침습 eMMC Full ROM 덤프**:
   - 하드웨어 분해 및 시스템 파티션 쓰기 없이, 1회성 DSU 진단 GSI를 통해 순정 eMMC 18개 파티션 전체(64MB `boot`, 3GB `super`, `logo`, `waveform` 등 약 4.2GB)를 SHA-256 무결성 검증과 함께 백업.
   - Rockchip U-Boot의 32MB LBA 읽기 제한(`0xCC` 더미 패딩) 및 fastbootd `fetch` 미지원 문제를 해결.
2. **Magisk 30.7 시스템리스 루팅**:
   - 덤프된 순정 `boot.img`에 Magisk 패치를 적용하여 플래시.
   - 시스템 파티션은 건드리지 않는 시스템리스 방식이며, 루팅 후에도 SELinux는 Enforcing 그대로입니다.
3. **온디바이스 화면 제어 도구 (`EinkScreens v1.2`)**:
   - 순수 Java/SDK 빌드 (57KB, 외부 종속성 배제).
   - DocumentsUI 부재 환경 대응 자체 파일 브라우저 내장.
   - 슬립, 종료, 부팅 로고, 부팅 애니메이션, 꺼진 상태 충전 등 5개 화면을 16단계 오차확산(디더링)으로 변환 및 적용. 순정 복원 기능 지원.
4. **E-Ink용 테마 그림 (Releases `EinkThemes.zip`, 9종 45장)**:
   - 1404x1872 해상도·16단계 그레이에 맞춘 글자 없는 테마 9종 × 5장. [`tools/aoc_make_eink_themes.py`](./tools/aoc_make_eink_themes.py)로 다시 만들 수 있습니다.
5. **하드웨어 비상 복구 절차 규명**:
   - fastbootd로 순정 boot 되돌리기, MaskROM + RKDevTool(`rk3566_loader.bin`) 주소 지정 쓰기를 이 기기에서 실측했습니다. Android가 켜지지 않는 상태에서 MaskROM으로 들어가는 방법은 아직 실측하지 않았습니다([RECOVERY.md](./RECOVERY.md)의 [미검증] 표시).

---

## 문서 안내

본 프로젝트는 목적과 작업 범위에 따라 역할을 분리한 문서 체계로 구성되어 있습니다.

| 문서명 | 주요 내용 | 대상 독자 / 권장 상황 | 링크 |
|:---|:---|:---|:---|
| **초보자 실전 안내서**<br>`BEGINNER_GUIDE.md` | Windows PowerShell 복사·붙여넣기 기반 순정 백업, Magisk 루팅, 화면 교체 앱 구동 매뉴얼 | 일반 사용자 | [BEGINNER_GUIDE.md](./BEGINNER_GUIDE.md) |
| **DSU 덤프 & 기술 가이드**<br>`DSU_DUMP_GUIDE.md` | DSU 진단 GSI 제작, USB 가젯 스크립트 메커니즘, 18개 파티션 덤프 및 무결성 검증 명세 | 개발자 | [DSU_DUMP_GUIDE.md](./DSU_DUMP_GUIDE.md) |
| **Magisk 루팅 & 화면 커스텀**<br>`MAGISK_AND_SCREENS.md` | Magisk 30.7 구조, `logo` 파티션 RKEL 헤더 분석, `/data/misc/eink` 및 부팅 애니메이션 수동 제어 규격 | 시스템 제어 분석가 | [MAGISK_AND_SCREENS.md](./MAGISK_AND_SCREENS.md) |
| **비상 복구 매뉴얼**<br>`RECOVERY.md` | 부팅 중단, ADB 미검출, 화면 오류 시 Fastbootd 및 MaskROM/RKDevTool 기반 순정 팩토리 롤백 절차 | 장애 복구 상황 | [RECOVERY.md](./RECOVERY.md) |
| **진단 GSI 고지 및 라이선스**<br>`GSI_NOTICE.md` | phh AOSP v313 원본 출처, 오픈소스 라이선스, 개인정보 완전 제거 검증 및 SHA-256 해시 고지 | 검증 및 라이선스 확인 | [GSI_NOTICE.md](./GSI_NOTICE.md) |
| **화면 제어 앱 소스코드**<br>`app/` | 순수 Java/SDK 기반 E-Ink 화면 변환 및 적용 앱 소스 (`EinkScreens v1.2`, 57KB) | 앱 빌더, 개발자 | [app/](./app/) |
| **자동화 스크립트 모음**<br>`tools/` | 진단 GSI 빌더, eMMC 덤프 도구, 온디바이스 Magisk 패처, 테마 생성기 | CLI 작업자 | [tools/](#저장소-파일-구조-repository-structure) |

---

## 어디서 시작할까

```text
                                 [기기 작업 시작]
                                         │
            ┌────────────────────────────┴───────────────────────────┐
            ▼                                                        ▼
   [빠른 루팅 및 화면 교체]                                  [DSU 원리 및 GSI 빌드]
            │                                                        │
            ▼                                                        ▼
    BEGINNER_GUIDE.md                                        DSU_DUMP_GUIDE.md
   (Windows CLI 스크립트)                                   (진단 GSI 빌드 및 덤프 분석)
            │                                                        │
            └────────────────────────────┬───────────────────────────┘
                                         │
                          ┌──────────────┴──────────────┐
                          ▼                             ▼
                 [화면 제어 규격 분석]                  [부팅 이상 복구]
                          │                             │
                          ▼                             ▼
                  MAGISK_AND_SCREENS.md             RECOVERY.md
              (logo/hwcomposer/bootanim)       (MaskROM / RKDevTool 복구)
```

---

## 작업 개요 (3단계 요약)

1. **사전 준비**: 태블릿 설정에서 USB 디버깅을 활성화합니다. (Settings ➔ About Device 제목 7~8회 탭 ➔ 비밀번호 `2204` ➔ Android 설정 ➔ 태블릿 정보 ➔ 빌드 번호 연타 ➔ `2204`).
2. **백업 및 루팅**: [Releases](https://github.com/zlkiki/AOC-10W1D-DSU-Root/releases/latest) 패키지를 다운로드한 뒤, PowerShell 스크립트를 통해 진단 GSI로 eMMC 전체 백업을 추출하고 Magisk 루팅을 적용합니다.
3. **화면 설정**: 설치된 **EinkScreens** 앱을 통해 슬립, 종료, 부팅 화면을 선택 및 적용합니다.

상세 절차는 [초보자 안내서 (`BEGINNER_GUIDE.md`)](./BEGINNER_GUIDE.md)를 참조하십시오.

---

## 저장소 파일 구조 (Repository Structure)

```text
AOC-10W1D-DSU-Root/
├── README.md                  ← [본 문서] 프로젝트 개요 및 문서 안내
├── BEGINNER_GUIDE.md          ← 초보자용 Windows 단계별 실전 가이드
├── DSU_DUMP_GUIDE.md          ← DSU 진단 GSI 제작 및 전체 파티션 덤프 엔지니어링 명세
├── MAGISK_AND_SCREENS.md      ← Magisk 루팅 및 화면 리소스 제어 기술 상세
├── RECOVERY.md                ← 장애 복구 매뉴얼 (fastboot, MaskROM + RKDevTool)
├── GSI_NOTICE.md              ← 릴리즈 진단 GSI 출처, 라이선스, 무결성 검증 고지
├── LICENSE                    ← MIT License
├── images/                    ← 가이드 참조용 스크린샷 (12장)
├── app/                       ← 온디바이스 앱 소스코드 (EinkScreens v1.2)
│   ├── AndroidManifest.xml
│   ├── build.py               ← Android SDK 기반 단독 빌드 스크립트 (Gradle 미사용)
│   └── src/io/github/zlkiki/einkscreens/ (MainActivity, Root, Img, Logo, BootAnim)
└── tools/                     ← 자동화 및 엔지니어링 스크립트
    ├── build_diag_gsi.sh      ← phh GSI 기반 진단 GSI 빌드 스크립트 (Linux/WSL)
    ├── zz_dsu_diag.rc         ← init 진단 서비스 설정 파일
    ├── dsudiag.sh             ← USB 강제 바인딩 셸 스크립트
    ├── aoc_full_rom_dump.py   ← eMMC 전체 파티션 SHA-256 무결성 검증 덤프 도구
    ├── aoc_backup_partitions.sh ← DSU root 셸 온디바이스 백업 스크립트
    ├── aoc_magisk_patch.sh    ← 온디바이스 boot.img Magisk 패치 스크립트
    ├── bootimg_check.py       ← boot 이미지 헤더 및 ramdisk 검증 도구
    ├── eink_logo.py           ← logo 파티션(RKEL/GR04) 언팩/팩 도구
    ├── make_bootanim_module.py ← bootanimation.zip 교체 Magisk 모듈 생성기
    └── aoc_make_eink_themes.py ← E-Ink 전용 테마 9종(45장) 생성기
```

---

## English Summary

### Overview & Documentation Matrix

**Project Scope**: An engineering toolkit and reference for Rockchip RK3566 Android 11 E-Ink tablets (AOC 10W1D). It provides a non-invasive Full ROM eMMC dump (including 64MB clean boot) via temporary DSU diagnostic GSI without writing to system partitions, followed by Magisk 30.7 rooting, 5-screen customization (sleep, power-off, boot logo, boot animation, off-state charging), and hardware MaskROM recovery procedures.

| Document | Purpose | Target Audience | Link |
|:---|:---|:---|:---|
| **[BEGINNER_GUIDE.md](./BEGINNER_GUIDE.md)** | Step-by-step PowerShell walk-through (Backup → Magisk Root → Screens App → Themes) | End Users | [BEGINNER_GUIDE.md](./BEGINNER_GUIDE.md) |
| **[DSU_DUMP_GUIDE.md](./DSU_DUMP_GUIDE.md)** | Core DSU engineering spec, USB gadget bug analysis, diagnostic GSI build, eMMC dump | Developers, Engineers | [DSU_DUMP_GUIDE.md](./DSU_DUMP_GUIDE.md) |
| **[MAGISK_AND_SCREENS.md](./MAGISK_AND_SCREENS.md)** | Magisk 30.7 structure, U-Boot logo (RKEL), hwcomposer `/data/misc/eink` analysis | System Customizers | [MAGISK_AND_SCREENS.md](./MAGISK_AND_SCREENS.md) |
| **[RECOVERY.md](./RECOVERY.md)** | Emergency recovery via Fastbootd and hardware MaskROM / RKDevTool | Troubleshooting | [RECOVERY.md](./RECOVERY.md) |
| **[GSI_NOTICE.md](./GSI_NOTICE.md)** | Upstream phh v313 source, open-source licenses, privacy verification, SHA-256 hashes | Reference | [GSI_NOTICE.md](./GSI_NOTICE.md) |
| **[`app/`](./app/)** | Pure Java/SDK on-device screen switcher source (`EinkScreens v1.2`, 57KB) | App Developers | [app/](./app/) |
| **[`tools/`](./tools/)** | Diagnostic GSI builder, dump tools, device patchers, theme image generator | CLI Users | [tools/](#저장소-파일-구조-repository-structure) |

- **Target Device**: `AOC_10W1D` (Rockchip RK3566, Android 11, A-only with dynamic partitions, factory unlocked bootloader, 10.3" Carta E-Ink).
- **Rationale for DSU**: The vendor does not provide factory firmware. RKDevTool fails past LBA 32MB (`0xCC` padding). Fastbootd lacks the `fetch` command. DSU provides an isolated `adb root` environment to safely read all raw block devices.
- **Core Engineering Solution**: Standard GSIs hang on the boot logo because `sys.usb.config=adb,mtp` does not match vendor USB gadget triggers, and the framework crash-loops on the E-Ink display HAL. The custom diagnostic GSI injects an init service that forces `setprop sys.usb.config adb` and starts `adbd` at 150 seconds, successfully bringing up `adb root`.

---

## 크레딧 및 라이선스 (Credits & License)

- [zhalps/Duokan-Pro2](https://github.com/zhalps/Duokan-Pro2): RK3566 E-Ink 환경에서 DSU 기반 boot 덤프 접근법 참조.
- [phhusson/treble_experimentations](https://github.com/phhusson/treble_experimentations): phh Treble GSI (AOSP 11 ARM64).
- AOSP [`external/avb`](https://android.googlesource.com/platform/external/avb/): `avbtool` 및 테스트 키.
- [topjohnwu/Magisk](https://github.com/topjohnwu/Magisk): 시스템리스 루팅 프레임워크 (`tools/aoc_magisk_patch.sh`에서 공식 키트 활용).

문서, `tools/` 스크립트, `app/` 소스코드, 테마 리소스는 [MIT License](./LICENSE)로 배포됩니다. Releases의 진단 GSI는 phh/AOSP 구성 요소의 각 라이선스를 따릅니다 ([GSI_NOTICE.md](./GSI_NOTICE.md)).
