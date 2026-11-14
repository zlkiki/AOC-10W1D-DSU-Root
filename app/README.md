# E-Ink Screens (E-Ink 화면 바꾸기)

Rooted (Magisk) AOC 10W1D app: pick a photo for the sleep, power-off, boot logo, boot animation and off-charging screens, or restore stock. 루팅(Magisk)된 AOC 10W1D에서 사진을 골라 슬립·종료·부팅 로고·부팅 애니메이션·꺼진 상태 충전 화면을 바꾸거나 순정으로 되돌리는 앱입니다.

| 화면 | 기록 위치 |
|:---|:---|
| 슬립 | `/data/misc/eink/standby*.png` (4종 같은 그림) |
| 종료 | `/data/misc/eink/poweroff*.png` + logo `0x200` |
| 부팅 로고 | logo `0x1`, `0x2` |
| 꺼진 상태 충전 | logo `0x4~0x80`(배터리 칸 자동), `0x100`(저전력) |
| 부팅 애니메이션 | Magisk 모듈 `/data/adb/modules/eink_bootanim` (bind mount) |

- 첫 실행 때 logo 파티션을 `/sdcard/EinkScreens/backup/logo_original.img`에 백업하고, [순정으로]는 이 백업에서 해당 엔트리만 되돌립니다. 이미 logo를 바꾼 기기라면 이 파일을 순정 logo로 교체하세요.
- logo 기록은 `/dev/block/by-name/logo`(16MB, RKEL 헤더 확인)로만 하며, 기록 후 다시 읽어 SHA-256을 비교합니다.
- 빌드: `python build.py OUTDIR` (Android SDK build-tools 34 + platforms;android-30, JDK, Gradle 불필요). 환경변수 `KEYSTORE_PASS` 필요.
