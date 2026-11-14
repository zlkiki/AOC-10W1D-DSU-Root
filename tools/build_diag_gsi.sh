#!/usr/bin/env bash
# build_diag_gsi.sh — phh Treble GSI(AOSP 11, arm64 vanilla)를 AOC 10W1D DSU용 "진단 GSI"로 변환
#
# 하는 일
#   1) 입력 이미지 해제(.xz) / sparse → raw 변환
#   2) AVB 꼬리표를 떼고 ext4 본체만 분리
#   3) 4000MB로 확장 후 shared_blocks 해제 (phh 이미지는 블록 중복 제거 ext4라 그대로는 쓰기 불가)
#   4) debugfs로 파일 3개 주입
#        /system/etc/init/zz_dsu_diag.rc   (부팅 단계 기록, dsudiag 서비스 시작)
#        /system/bin/dsudiag.sh            (150초에 USB adb 강제, 8분 뒤 자동 웜 재부팅)
#        /system/build.prop                (persist.sys.usb.config=adb 추가)
#   5) 최소 크기로 축소 → AVB 해시트리 꼬리표 재생성(avbtool, AOSP 테스트 키) → 검증
#   6) gzip 압축 + KEY_SYSTEM_SIZE 값 파일(.size) 생성
#
# 사용법 (Linux 또는 WSL, root 불필요)
#   ./build_diag_gsi.sh <system-roar-arm64-ab-vanilla.img.xz | .img> [출력폴더]
#
# 필요 패키지 (Debian/Ubuntu)
#   sudo apt install e2fsprogs python3 curl xz-utils gzip android-sdk-libsparse-utils
#   e2fsprogs 1.45 이상 필요 (e2fsck -E unshare_blocks)
set -euo pipefail

IN="${1:?사용법: $0 <phh GSI .img.xz|.img> [출력폴더]}"
OUT="${2:-$PWD/diag_gsi_out}"
HERE="$(cd "$(dirname "$0")" && pwd)"
RC="$HERE/zz_dsu_diag.rc"
SH="$HERE/dsudiag.sh"
WORK="$OUT/work"
DEBUGFS="$(command -v debugfs || echo /usr/sbin/debugfs)"
E2FSCK="$(command -v e2fsck || echo /usr/sbin/e2fsck)"
RESIZE2FS="$(command -v resize2fs || echo /usr/sbin/resize2fs)"
DUMPE2FS="$(command -v dumpe2fs || echo /usr/sbin/dumpe2fs)"
AVB_URL="https://android.googlesource.com/platform/external/avb/+/refs/heads/main"

log() { printf '\n== %s\n' "$*"; }
[ -f "$RC" ] && [ -f "$SH" ] || { echo "zz_dsu_diag.rc / dsudiag.sh 가 스크립트와 같은 폴더에 있어야 합니다"; exit 1; }
mkdir -p "$WORK"

log "0. 도구 준비 (avbtool, AOSP 테스트 키)"
cd "$WORK"
[ -s avbtool.py ] || curl -fsS --max-time 60 "$AVB_URL/avbtool.py?format=TEXT" | base64 -d > avbtool.py
[ -s testkey_rsa2048.pem ] || curl -fsS --max-time 60 "$AVB_URL/test/data/testkey_rsa2048.pem?format=TEXT" | base64 -d > testkey_rsa2048.pem
head -1 avbtool.py | grep -q python3 || { echo "avbtool.py 다운로드 실패"; exit 1; }

log "1. 입력 해제 / raw 변환"
case "$IN" in
  *.xz) xz -dc "$IN" > input.img ;;
  *)    cp "$IN" input.img ;;
esac
if [ "$(head -c4 input.img | od -An -tx1 | tr -d ' ')" = "3aff26ed" ]; then
  echo "sparse 이미지 → simg2img"
  simg2img input.img input.raw && mv input.raw input.img
fi
[ "$(dd if=input.img bs=1 skip=1080 count=2 2>/dev/null | od -An -tx1 | tr -d ' ')" = "53ef" ] || { echo "ext4 이미지가 아닙니다"; exit 1; }

log "2. AVB 꼬리표 제거 (ext4 본체만 분리)"
ORIG=$(python3 avbtool.py info_image --image input.img 2>/dev/null | awk '/^Original image size:/{print $4}' || true)
if [ -z "${ORIG:-}" ]; then
  BC=$("$DUMPE2FS" -h input.img 2>/dev/null | awk '/^Block count:/{print $3}')
  ORIG=$((BC*4096)); echo "AVB 꼬리표 없음 → 파일시스템 크기 사용"
fi
echo "ext4 크기: $ORIG"
head -c "$ORIG" input.img > fs.img
rm -f input.img

log "3. 4000MB 확장 + shared_blocks 해제"
truncate -s 4000M fs.img
"$RESIZE2FS" fs.img
"$E2FSCK" -fy -E unshare_blocks fs.img > unshare.log 2>&1 || true
"$E2FSCK" -fn fs.img | tail -1
if "$DUMPE2FS" -h fs.img 2>/dev/null | grep -q shared_blocks; then
  echo "shared_blocks 해제 실패 (unshare.log 확인)"; exit 1
fi

log "4. 진단 파일 주입 (debugfs)"
cp "$RC" zz_dsu_diag.rc; cp "$SH" dsudiag.sh
sed -i 's/\r$//' zz_dsu_diag.rc dsudiag.sh
printf 'u:object_r:system_file:s0\0' > label.bin
"$DEBUGFS" -R "cat /system/build.prop" fs.img > build.prop 2>/dev/null
grep -q '^persist.sys.usb.config=' build.prop || printf '\n# AOC DSU diag\npersist.sys.usb.config=adb\n' >> build.prop
cat > cmds.txt <<'EOF'
cd /system/etc/init
write zz_dsu_diag.rc zz_dsu_diag.rc
sif zz_dsu_diag.rc mode 0100644
sif zz_dsu_diag.rc uid 0
sif zz_dsu_diag.rc gid 0
ea_set -f label.bin zz_dsu_diag.rc security.selinux
cd /system/bin
write dsudiag.sh dsudiag.sh
sif dsudiag.sh mode 0100755
sif dsudiag.sh uid 0
sif dsudiag.sh gid 2000
ea_set -f label.bin dsudiag.sh security.selinux
cd /system
rm build.prop
write build.prop build.prop
sif build.prop mode 0100644
sif build.prop uid 0
sif build.prop gid 0
ea_set -f label.bin build.prop security.selinux
EOF
"$DEBUGFS" -w -f cmds.txt fs.img > debugfs.log 2>&1
for f in /system/etc/init/zz_dsu_diag.rc /system/bin/dsudiag.sh /system/build.prop; do
  "$DEBUGFS" -R "ea_list $f" fs.img 2>/dev/null | grep -q 'system_file' || { echo "라벨 확인 실패: $f"; exit 1; }
done
echo "주입 및 SELinux 라벨 확인 완료"

log "5. 축소 + AVB 해시트리 재생성 + 검증"
"$E2FSCK" -fy fs.img > /dev/null 2>&1 || true
"$RESIZE2FS" -M fs.img
BC=$("$DUMPE2FS" -h fs.img 2>/dev/null | awk '/^Block count:/{print $3}')
truncate -s $((BC*4096)) fs.img
python3 avbtool.py add_hashtree_footer --image fs.img \
  --partition_name system --hash_algorithm sha1 \
  --algorithm SHA256_RSA2048 --key testkey_rsa2048.pem \
  --do_not_generate_fec
ln -sf fs.img system.img
python3 avbtool.py verify_image --image fs.img --key testkey_rsa2048.pem | tail -1
rm -f system.img

log "6. gzip + KEY_SYSTEM_SIZE"
SIZE=$(stat -c %s fs.img)
[ $((SIZE % 512)) -eq 0 ] || { echo "크기가 512의 배수가 아님"; exit 1; }
gzip -c -6 fs.img > "$OUT/aoc_dsu_diag_gsi.img.gz"
echo "$SIZE" > "$OUT/aoc_dsu_diag_gsi.img.gz.size"
( cd "$OUT" && sha256sum aoc_dsu_diag_gsi.img.gz > aoc_dsu_diag_gsi.img.gz.sha256 )
echo
echo "완료: $OUT/aoc_dsu_diag_gsi.img.gz"
echo "KEY_SYSTEM_SIZE = $SIZE"
echo "작업 폴더 삭제: rm -rf '$WORK'"
