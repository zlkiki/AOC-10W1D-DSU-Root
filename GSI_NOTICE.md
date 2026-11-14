# 진단 GSI 출처·라이선스·변경 사항 (GSI notice)

Releases의 `aoc_dsu_diag_v2_phh-v313-vanilla.img.gz`에 대한 설명입니다.

> ⏳ **공개 준비 중**: 이 저장소의 `tools/`로 다시 빌드하고 DSU 부팅을 다시 확인한 뒤 Releases에 올립니다. 올릴 때 크기·SHA-256·`KEY_SYSTEM_SIZE`를 아래 표와 Releases 설명에 적습니다.

## 무엇인가

| 항목 | 내용 |
|:---|:---|
| 원본 | **phh Treble GSI v313**, `system-roar-arm64-ab-vanilla.img.xz` (AOSP Android 11, arm64, Google 앱 없음 "vanilla") |
| 원본 배포처 | <https://github.com/phhusson/treble_experimentations/releases/tag/v313> (Pierre-Hugues Husson, "phh") |
| 만든 방법 | 이 저장소의 [`tools/build_diag_gsi.sh`](./tools/build_diag_gsi.sh) |
| 크기 | gzip 약 930MB / 풀면 약 2.3GB (`KEY_SYSTEM_SIZE`는 Releases 설명 참고) |
| SHA-256 | Releases의 `SHA256SUMS.txt` |
| 용도 | AOC 10W1D에서 DSU로 **한 번만** 부팅해 root 셸을 얻고 순정 파티션을 백업하기 위함. 일상용 시스템이 아닙니다(화면이 그려지지 않음) |

**제조사 펌웨어는 들어 있지 않습니다.** AOC/제조사의 `boot`·`vendor`·`logo`·`waveform` 등은 올리지 않으며, 이 이미지는 phh GSI(=AOSP 기반 공개 소스 빌드)의 `system` 파티션 이미지일 뿐입니다.

## phh 원본에서 바꾼 점

[`tools/build_diag_gsi.sh`](./tools/build_diag_gsi.sh)가 하는 일 그대로입니다. 그 밖의 파일·바이너리는 phh 원본과 같습니다.

1. AVB 꼬리표(해시트리 + vbmeta) 제거 → ext4 본체만 사용
2. ext4를 키우고 `e2fsck -E unshare_blocks`로 블록 공유(dedup) 해제
3. **파일 3개 추가/변경** (`debugfs`, SELinux 레이블 `u:object_r:system_file:s0`)
   - `/system/etc/init/zz_dsu_diag.rc` — 부팅 단계를 커널 로그에 기록하고 진단 서비스를 시작하는 init 스크립트 ([`tools/zz_dsu_diag.rc`](./tools/zz_dsu_diag.rc))
   - `/system/bin/dsudiag.sh` — 150초에 USB ADB를 강제로 켜고, 8분 뒤 자동 재부팅(취소 가능) ([`tools/dsudiag.sh`](./tools/dsudiag.sh))
   - `/system/build.prop` — 끝에 `persist.sys.usb.config=adb` 한 줄 추가
4. 최소 크기로 줄인 뒤 `avbtool add_hashtree_footer`로 해시트리를 새로 만듦(sha1, **AOSP 공개 테스트 키** `testkey_rsa2048`). 부트로더가 언락(orange)인 기기에서만 의미가 있습니다.
5. gzip 압축

직접 만들고 싶다면 phh 원본을 내려받아 `tools/build_diag_gsi.sh`를 Linux/WSL에서 실행하세요([README §4](./README.md#4-1단계-진단-gsi-만들기)).

## 라이선스와 소스

이 이미지는 AOSP와 phh Treble 프로젝트의 구성 요소로 이루어져 있으며, 각 구성 요소는 **자기 라이선스**(대부분 Apache License 2.0, 일부 GPL·LGPL·BSD 등)를 따릅니다. 이 저장소의 MIT License는 이미지 안의 구성 요소에 적용되지 않습니다.

대응하는 소스:

- AOSP Android 11: <https://android.googlesource.com/> (각 구성 요소의 `NOTICE`·`LICENSE`는 이미지 안 `/system/etc/NOTICE.xml.gz`에도 있음)
- phh Treble 빌드 스크립트·릴리스: <https://github.com/phhusson/treble_experimentations>
- phh 기기 트리와 패치: <https://github.com/phhusson/device_phh_treble>, <https://github.com/phhusson> 아래 `platform_*` 저장소들
- 우리가 바꾼 부분: 이 저장소의 `tools/` (MIT)

phh 원본 바이너리는 변경 없이 다시 배포하는 것이며, 소스는 위 위치에서 받을 수 있습니다. 소스 위치를 찾기 어렵다면 [이슈](https://github.com/zlkiki/AOC-10W1D-DSU-Root/issues)로 알려 주세요.

## English

`aoc_dsu_diag_v2_phh-v313-vanilla.img.gz` is the **phh Treble GSI v313** `system-roar-arm64-ab-vanilla` (AOSP 11) system image, modified only by [`tools/build_diag_gsi.sh`](./tools/build_diag_gsi.sh): AVB footer stripped, ext4 unshared and grown, three files added/changed (`/system/etc/init/zz_dsu_diag.rc`, `/system/bin/dsudiag.sh`, one line `persist.sys.usb.config=adb` in `/system/build.prop`), shrunk, and a new hashtree footer added with the public AOSP test key. No vendor/OEM firmware is included. Components keep their own licenses (mostly Apache-2.0, some GPL/LGPL/BSD); sources: AOSP (android.googlesource.com), phhusson/treble_experimentations, phhusson/device_phh_treble and the phhusson `platform_*` repositories. The repository's MIT license covers only our scripts and documents. **Status: being rebuilt from this repository's `tools/` and re-tested before upload.**
