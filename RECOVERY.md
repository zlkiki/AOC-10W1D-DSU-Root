# AOC 10W1D 비상 복구

> [초보자 안내서](./BEGINNER_GUIDE.md)를 따라 하다 기기가 이상해졌을 때 보는 문서입니다. **위에서부터 순서대로**, 가장 쉬운 방법부터 시도하세요.
> 모든 방법에는 [초보자 안내서 4단계](./BEGINNER_GUIDE.md#4-진단-gsi로-임시-부팅하고-순정-백업-받기)에서 받은 **내 기기의 백업(`aoc_backup` 폴더)**이 필요합니다. 다른 사람의 백업, 특히 `waveform.img`는 절대 쓰지 마세요.

| 표시 | 뜻 |
|:-:|:---|
| 🟢 | 이 기기에서 실제로 해 본 방법 |
| 🟡 | 이론상 맞지만 이 기기에서 해 보지 않은 방법 |

---

## 1. 증상별 바로가기

| 증상 | 할 일 |
|:---|:---|
| 임시 시스템(DSU)으로 켠 뒤 로고에서 멈춤, PC에서도 안 보임 | [2.1](#21-dsu-중-멈춤) |
| 다시 시작한 뒤 PC `adb devices`에 안 보임 (기기는 켜져 있음) | [2.2](#22-pc에서-기기가-안-보임) |
| 바꾼 화면이 마음에 안 듦, 이상하게 나옴 | [2.3](#23-바꾼-화면-되돌리기) |
| Magisk 루팅 뒤 켜지지만 이상함 | [3](#3-android가-켜질-때-boot-되돌리기-fastboot) |
| **boot에 쓴 뒤 Android가 켜지지 않음** | [4](#4-android가-켜지지-않을-때-maskrom--rkdevtool) |

---

## 2. 가벼운 문제

### 2.1. DSU 중 멈춤

🟢 **전원 버튼을 10초 누르기** → 꺼지면 다시 눌러 켜기. DSU는 한 번만 켜는 기능이라 **항상 순정으로 돌아옵니다**(여러 차례 확인).

- 이 기기는 전원 버튼을 8~10초 누르면 전원이 끊깁니다. 다시 한 번 눌러야 켜집니다.

### 2.2. PC에서 기기가 안 보임

🟢 **USB 케이블을 뽑았다 다시 꽂기.** 이 기기는 다시 시작한 뒤 이런 일이 자주 생깁니다. Windows 장치 관리자에는 보이는데 `adb devices`만 비어 있는 경우가 대부분 이것입니다.

### 2.3. 바꾼 화면 되돌리기

🟢 **E-Ink 화면 바꾸기 앱의 [순정으로].** 부팅 로고·충전 화면은 앱이 처음 실행 때 만든 백업(`/sdcard/EinkScreens/backup/logo_original.img`)으로 되돌립니다. 부팅 애니메이션은 재부팅 후 순정이 됩니다.

앱 백업이 없어졌다면, 4단계 백업의 `logo.img`를 앱 백업 자리에 다시 넣고 [순정으로]를 누르면 됩니다.

```powershell
.\adb push aoc_backup\logo.img /sdcard/EinkScreens/backup/logo_original.img
```

> logo 파티션이 깨져도 부팅 자체는 막히지 않을 것으로 보입니다(U-Boot에 "logo 이상" 경고만 있음, 🟡). 부팅 애니메이션 파일이 잘못되면 Android가 기본 애니메이션으로 대신 보여 줍니다(🟢 실제로 겪음).

---

## 3. Android가 켜질 때: boot 되돌리기 (fastboot)

🟢 순정 boot를 그대로 다시 씁니다(이 기기에서 쓰기 확인).

```powershell
.\adb reboot fastboot
.\fastboot devices                                   # 영문숫자  fastboot
.\fastboot flash boot aoc_backup\boot.img
.\fastboot reboot
```

- `fastboot devices`가 비어 있으면 [초보자 안내서 5.2](./BEGINNER_GUIDE.md#52-boot에-쓰기-약-2분)의 Google USB 드라이버 설치를 하세요.
- ⚠️ `fastboot`는 `logo` 파티션을 모릅니다(`Partition not found`). logo는 2.3 또는 4의 방법으로 되돌립니다.
- ⚠️ `fastboot flash` 외의 명령(`erase`, `format`, `-w`, `flashall`)은 쓰지 마세요.

---

## 4. Android가 켜지지 않을 때: MaskROM + RKDevTool

boot가 깨지면 Android도, `adb reboot fastboot`도, DSU도 쓸 수 없습니다(DSU도 순정 boot로 처음 단계를 켜기 때문). 이때는 Rockchip 칩의 **MaskROM 모드**로 PC에서 eMMC에 직접 씁니다.

> 안내서의 `magisk_patched_boot.img`가 검증값(`4f8136e2…`)과 같았다면, 검증 기기에서 문제없이 켜진 것과 **바이트 단위로 같은 파일**입니다. 이 장까지 올 가능성은 낮습니다.

### 4.1. 준비물

| 항목 | 내용 |
|:---|:---|
| **DriverAssistant** (Rockchip USB 드라이버) | 실측: v5.14. 예: [Radxa 배포본](https://dl.radxa.com/tools/windows/DriverAssitant_v5.14.zip). 압축을 풀고 `DriverInstall.exe` → **드라이버 설치** |
| **RKDevTool** (Windows) | 실측: v3.37. Rockchip이 배포하는 Windows 도구입니다(Radxa·Pine64 등 RK35xx 보드 문서에 내려받기 링크가 있음) |
| **RK3566 로더 파일**(`.bin`) | RK3566·RK3568 공용 로더. 실측: Rockchip `rkbin`의 **`rk356x_spl_loader_v1.16.112.bin`**. rkbin 사본(예: [Radxa rkbin](https://github.com/radxa/rkbin/tree/develop-v2026.01/bin/rk35))의 `bin/rk35/`에 `rk356x_spl_loader_v*.bin`이 있습니다. 다른 버전은 이 기기에서 시험하지 않았습니다 |
| 내 백업 | `aoc_backup\boot.img`, 필요하면 `aoc_backup\logo.img` |
| USB 포트 | **PC 본체 뒤쪽 USB 2.0 포트** 권장(허브·전면 포트에서 불안정한 사례가 있음) |

### 4.2. MaskROM 모드 들어가기

| 방법 | 조건 | 상태 |
|:---|:---|:-:|
| A. `adb reboot loader` → RKDevTool 하단 `Found One LOADER Device` → **[Go Maskrom]** 버튼 → `Found One MASKROM Device` | Android(또는 adb)가 켜질 때 | 🟢 |
| B. USB 분리 → 전원 버튼 10초(전원 차단) → **전원 버튼을 누른 채 USB 연결** | Android가 안 켜질 때 | 🟡 |
| C. 기기를 열어 eMMC 클록 테스트 포인트를 접지한 채 연결 | B가 안 될 때 | 🟡 (분해 필요, 이 문서 범위 밖) |

- 이 기기에는 볼륨 버튼이 없습니다(전원 버튼 + 터치식 홈 버튼).
- RKDevTool 아래쪽 상태 줄 글자로 판단합니다. 장치 관리자에는 Rockchip(`VID 2207`) 장치로 보입니다.

### 4.3. boot 쓰기 (Download Image 탭)

🟢 이 기기에서 같은 방법으로 **빈 `backup` 파티션 한가운데에 시험 데이터를 정확한 주소에 쓰고**, 다른 곳이 바뀌지 않은 것을 확인했습니다.

```
┌ RKDevTool ─ [Download Image] [Upgrade Firmware] [Advanced Function] ─────────────┐
│  #   ☑   주소(Address)     이름(Name)   경로(Path)                                 │
│  1   ☑   0x00000000        Loader       ...\rk356x_spl_loader_*.bin   ← ① 체크    │
│  2   ☐   0x00009000        Misc                                       ← 체크 해제 │
│  3   ☑   0x0000D800        Boot         ...\aoc_backup\boot.img       ← ② 체크    │
│  4   ☐   0x0002F800        Recovery                                   ← 체크 해제 │
│  …   ☐   (나머지 전부)                                                ← 체크 해제 │
│                                                                                   │
│  ☑ Write by Address   ← ③ 꼭 체크                       [ Run ]  ← ④             │
│  Found One MASKROM Device                                                         │
└───────────────────────────────────────────────────────────────────────────────────┘
```

1. **Download Image** 탭에서 **Loader** 행과 **Boot** 행만 체크합니다. 나머지 행은 **모두 체크 해제**.
2. Loader 행의 경로 칸을 눌러 로더 `.bin`을, Boot 행의 경로 칸을 눌러 **내 `aoc_backup\boot.img`**를 고릅니다.
3. Boot 행 주소가 **`0x0000D800`**인지 확인합니다(이 기기의 boot 시작 섹터).
4. **Write by Address**를 체크하고 **Run**.
5. ✅ 정상: 오른쪽 기록 창에 `Download Boot Start` … `Download image OK`. 기기가 스스로 다시 켜집니다.

logo를 되돌릴 때는 같은 방법으로 **주소 `0x007FB800`**에 `aoc_backup\logo.img`를 씁니다(행을 하나 골라 주소와 이름을 바꿔서 사용).

### 4.4. 절대 하지 말 것

- **Upgrade Firmware** 탭, **Erase Flash**, **EraseAll** 버튼 — 전체를 지우거나 덮어씁니다.
- `waveform`(주소 `0x00008000`) 쓰기 — 패널 고유 보정값입니다. 내 백업이라도 꼭 필요할 때만.
- 다른 기기·다른 사람의 이미지 쓰기.
- 주소를 모르는 파티션 쓰기 — 주소는 기기마다 다를 수 있습니다. 내 백업의 `partitions.txt`와 [README §12](./README.md#12-기기-정보-파티션-표-등)의 파티션 표로 확인하세요.

### 4.5. 알아 두면 좋은 것 (실측)

- RKDevTool의 주소는 **eMMC 절대 섹터(512바이트 단위)**입니다. 기본 행 주소(Misc `0x9000`, Boot `0xD800`, Recovery `0x2F800`)가 이 기기의 파티션 시작 섹터와 같습니다.
- MaskROM에서 **쓰기**는 32MB 제한이 없습니다. 읽기(`ExportImage`)만 32MB 너머가 `0xCC`로 채워집니다. 그래서 백업은 DSU로 받았습니다.
- `Run` 때 `Download IDB`가 함께 실행되지만, 같은 로더라면 GPT·IDB 영역 내용은 바뀌지 않았습니다(덤프 해시 일치).
- 명령줄 `rkdeveloptool`은 DriverAssistant 드라이버(`rockusb.sys`)에 묶인 장치를 열지 못합니다(`creating comm object failed`). RKDevTool을 쓰세요.

---

## English summary

Try in this order. Everything needs **your own** backup from the DSU step; never flash someone else's images, especially `waveform`.

1. DSU stuck: hold power 10 s → power on → always back to stock (verified).
2. adb missing after reboot: replug the USB cable (common on this device).
3. Screens: tap **Stock** in the app; the logo backup lives in `/sdcard/EinkScreens/backup/logo_original.img` (you can push `aoc_backup\logo.img` there).
4. Android boots: `adb reboot fastboot` → `fastboot flash boot aoc_backup\boot.img` (verified). fastbootd does not know `logo`.
5. Android does not boot: MaskROM + RKDevTool **Download Image**, only the **Loader** row and the **Boot** row at `0x0000D800`, **Write by Address**, Run (writing at absolute eMMC sectors verified). `logo` is at `0x007FB800`. Loader used in the test: rkbin `rk356x_spl_loader_v1.16.112.bin`. Entering MaskROM via `adb reboot loader` → *Go Maskrom* is verified; entering it with a dead Android (holding power while plugging USB) is **not** verified. Never use Upgrade Firmware / Erase.
