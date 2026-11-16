# AOC 10W1D 비상 복구 매뉴얼

작업 중 기기 이상이나 부팅 장애가 발생했을 때 참조하는 복구 절차서입니다. 상위 절차부터 순서대로 진행하십시오.
모든 복구 절차는 사전 확보된 **기기 순정 백업(`aoc_backup` 디렉토리)**을 전제로 합니다. 타 기기의 덤프 파일(특히 `waveform.img`)은 절대 사용하지 마십시오.

| 구분 표기 | 정의 |
|:---:|:---|
| **[검증 완료]** | 본 기기(AOC 10W1D)에서 실측 및 복구 성공을 직접 확인한 절차 |
| **[미검증]** | 칩셋(RK3566) 구조상 유효하나 본 기기에서 직접 테스트하지 않은 절차 |

---

## 1. 증상별 조치 색인

| 증상 | 바로가기 |
|:---|:---|
| 임시 시스템(DSU) 부팅 후 로고에서 멈춤, PC ADB 미검출 | [2.1 DSU 부팅 중 멈춤](#21-dsu-부팅-중-멈춤) |
| 재부팅 후 PC `adb devices`에 기기 미검출 (기기는 정상 구동 중) | [2.2 PC에서 기기 미인식](#22-pc에서-기기-미인식) |
| 적용된 화면 복원 또는 비정상 출력 | [2.3 적용 화면 순정 복구](#23-적용-화면-순정-복구) |
| Magisk 루팅 후 Android 부팅은 되나 이상 동작 | [3. Android 부팅 가능 시: boot 원복 (fastboot)](#3-android-부팅-가능-시-boot-원복-fastboot) |
| **boot 변조 후 Android 부팅 불가 (블랙스크린 / 무한 루프)** | [4. Android 부팅 불가 시: MaskROM + RKDevTool 복구](#4-android-부팅-불가-시-maskrom--rkdevtool-복구) |

---

## 2. 일반 장애 조치

### 2.1. DSU 부팅 중 멈춤

- **조치**: 전원 버튼을 10초간 길게 눌러 전원을 완전 차단한 후 다시 켭니다. [검증 완료]
- DSU는 1회성 임시 부팅이므로 하드웨어 리셋 시 항상 순정 Android로 정상 부팅됩니다.

### 2.2. PC에서 기기 미인식

- **조치**: USB 케이블을 분리했다가 다시 연결합니다. [검증 완료]
- 이 기기는 재부팅 후 Windows 장치 관리자에는 표시되나 ADB 데몬과의 연결이 초기화되지 않는 현상이 빈번합니다. 케이블 재연결로 즉시 인식됩니다.

### 2.3. 적용 화면 순정 복구

- **조치**: **E-Ink 화면 바꾸기(`EinkScreens`)** 앱에서 **[순정 복원]** 버튼을 누릅니다. [검증 완료]
  - 부팅 로고 및 충전 화면은 앱 최초 실행 시 자동 생성된 백업(`/sdcard/EinkScreens/backup/logo_original.img`)으로 원복됩니다.
  - 부팅 애니메이션은 모듈 비활성화 후 재부팅 시 순정으로 자동 환원됩니다.
- 앱 백업 파일이 유실된 경우, 사전 덤프한 `logo.img`를 기기에 전송 후 복원할 수 있습니다:
  ```powershell
  .\adb push aoc_backup\logo.img /sdcard/EinkScreens/backup/logo_original.img
  ```
- 참고: `logo` 파티션 데이터가 손상되어도 U-Boot 레벨에서 경고만 발생하고 시스템 부팅 자체는 계속 진행됩니다. 부팅 애니메이션 파일이 손상되면 Android 프레임워크가 AOSP 기본 애니메이션으로 자동 대체합니다.

---

## 3. Android 부팅 가능 시: boot 원복 (fastboot)

순정 `boot.img`를 fastbootd 모드에서 직접 플래시합니다. [검증 완료]

```powershell
.\adb reboot fastboot
.\fastboot devices                                   # fastboot 기기 확인
.\fastboot flash boot aoc_backup\boot.img
.\fastboot reboot
```

> [!WARNING]
> - `fastboot`는 `logo` 파티션을 인식하지 못합니다 (`Partition not found`). `logo`는 앱을 이용하거나 4장의 MaskROM 절차로 복구하십시오.
> - `fastboot flash` 외의 기타 파괴적 명령(`erase`, `format`, `-w`, `flashall`)은 사용하지 마십시오.

---

## 4. Android 부팅 불가 시: MaskROM + RKDevTool 복구

`boot` 파티션 손상으로 Android, `adb reboot fastboot`, DSU가 모두 불가능한 경우, Rockchip 하드웨어 MaskROM 모드를 통해 PC에서 eMMC로 직접 이미지를 기록합니다.

### 4.1. 준비 도구

| 구분 | 내용 |
|:---|:---|
| **DriverAssistant** | Rockchip USB 드라이버 (실측: v5.14). 설치 파일 실행 후 [드라이버 설치] 완료. |
| **RKDevTool** | Rockchip 공식 Windows 펌웨어 도구 (실측: v3.37). |
| **RK3566 로더 파일**(`.bin`) | Rockchip `rkbin` 공식 `rk356x_spl_loader_v1.16.112.bin` (RK3566/RK3568 공용). |
| **순정 백업 이미지** | `aoc_backup\boot.img`, 필요 시 `aoc_backup\logo.img`. |
| **USB 포트** | PC 본체 후면 USB 2.0 포트 사용 권장 (허브 및 전면 포트 지양). |

### 4.2. MaskROM 모드 진입 경로

| 경로 | 필요 조건 | 상태 |
|:---|:---|:---:|
| **A. 소프트웨어 진입**<br>`adb reboot loader` ➔ RKDevTool `Found One LOADER Device` ➔ **[Go Maskrom]** 클릭 | ADB 통신 가능 상태 | **[검증 완료]** |
| **B. 하드웨어 키 진입**<br>USB 분리 ➔ 전원 10초(방전 차단) ➔ **전원 버튼을 누른 채 USB 연결** | Android 부팅 불가 상태 | [미검증] |
| **C. 테스트포인트 접지**<br>후면 커버 분해 후 eMMC CLK/D0 테스트 포인트를 접지한 채 USB 연결 | B 진입 불가 시 최후 수단 | [미검증] (분해 필요) |

- 기기 정상 연결 시 RKDevTool 하단 상태 표시에 `Found One MASKROM Device`가 출력됩니다. (장치 관리자: Rockchip VID `2207`).

### 4.3. boot 복구 절차 (Download Image 탭)

빈 `backup` 파티션 영역에 테스트 데이터를 지정 주소로 정확히 쓰고, 타 영역에 영향이 없음을 사전 실측 검증하였습니다. [검증 완료]

```text
┌ RKDevTool ─ [Download Image] [Upgrade Firmware] [Advanced Function] ─────────────┐
│  #   ☑   주소(Address)     이름(Name)   경로(Path)                                 │
│  1   ☑   0x00000000        Loader       ...\rk356x_spl_loader_*.bin   ← ① 체크    │
│  2   ☐   0x00009000        Misc                                       ← 체크 해제 │
│  3   ☑   0x0000D800        Boot         ...\aoc_backup\boot.img       ← ② 체크    │
│  4   ☐   0x0002F800        Recovery                                   ← 체크 해제 │
│  …   ☐   (나머지 전부)                                                ← 체크 해제 │
│                                                                                   │
│  ☑ Write by Address   ← ③ 필수 체크                      [ Run ]  ← ④             │
│  Found One MASKROM Device                                                         │
└───────────────────────────────────────────────────────────────────────────────────┘
```

1. **Download Image** 탭에서 **Loader** 행과 **Boot** 행만 체크하고, 나머지 모든 행은 **체크를 해제**합니다.
2. Loader 경로 칸에 로더 `.bin` 파일을, Boot 경로 칸에 `aoc_backup\boot.img`를 지정합니다.
3. Boot 행 주소가 **`0x0000D800`**인지 확인합니다 (eMMC 절대 섹터 LBA).
4. **Write by Address** 항목을 체크한 후 **[ Run ]** 버튼을 클릭합니다.
5. 로그 창에 `Download Boot Start` ➔ `Download image OK`가 출력되면 복구가 완료되며 기기가 재부팅됩니다.

`logo` 파티션을 복구할 경우 동일한 방식으로 **주소 `0x007FB800`**에 `aoc_backup\logo.img`를 지정하여 기록합니다.

### 4.4. 금지 사항

> [!CAUTION]
> - **Upgrade Firmware** 탭의 기능, **Erase Flash**, **EraseAll** 버튼은 eMMC 전체 영역을 포맷하므로 절대 클릭하지 마십시오.
> - `waveform`(주소 `0x00008000`)은 패널 고유 보정값이므로 기록하지 마십시오.
> - 주소가 불분명한 파티션에 임의로 기록하지 마십시오. 파티션 주소는 [DSU 덤프 가이드 §12](./DSU_DUMP_GUIDE.md#12-기기-정보-파티션-표-등)의 파티션 표를 준수해야 합니다.

### 4.5. 기술 참고 사항 (실측 기반)

- RKDevTool의 주소 단위는 **eMMC 절대 섹터(512바이트 LBA)**입니다. 기본 행 주소(Misc `0x9000`, Boot `0xD800`, Recovery `0x2F800`)는 GPT 파티션 시작 섹터와 1:1로 일치합니다.
- MaskROM 모드에서의 **쓰기(Write)** 동작에는 32MB LBA 제한이 없습니다. 읽기(`ExportImage`) 시에만 32MB 초과 구간이 `0xCC`로 채워집니다.
- RKDevTool 실행 시 `Download IDB`가 자동 수행되나, 동일 로더 사용 시 GPT 및 IDB 영역 바이너리는 변형되지 않습니다 (해시 일치 확인).
- 명령줄 `rkdeveloptool`(libusb)은 Windows의 `rockusb.sys` 드라이버와 통신 충돌이 발생하므로 RKDevTool GUI를 사용해야 합니다.

---

## English Summary

Recovery procedure hierarchy:

1. **DSU Stalled**: Hold power button for 10 seconds to force shutdown. Device boots back into stock OS upon power-on. [Verified]
2. **ADB Missing After Reboot**: Replug USB cable. [Verified]
3. **Screen Rollback**: Use [Stock] button inside the EinkScreens app, or push stock `logo.img` to `/sdcard/EinkScreens/backup/logo_original.img`.
4. **Android Bootable**: Run `adb reboot fastboot` → `fastboot flash boot aoc_backup\boot.img`. [Verified]
5. **Android Unbootable**: Enter MaskROM mode, open RKDevTool **Download Image** tab, configure Loader (`rk356x_spl_loader_*.bin`) and Boot (`aoc_backup\boot.img` at LBA `0x0000D800`), check **Write by Address**, and execute **Run**. Logo recovery is at LBA `0x007FB800`. [Verified]
