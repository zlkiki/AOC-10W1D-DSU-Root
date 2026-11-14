#!/system/bin/sh
# AOC 10W1D: back up every partition except userdata, from the DSU GSI root shell. No Python needed.
# It only READS block devices. Output: /data/local/tmp/aoc_backup/*.img + SHA256SUMS.txt
#
#   adb root
#   adb push aoc_backup_partitions.sh /data/local/tmp/
#   adb shell sh /data/local/tmp/aoc_backup_partitions.sh          # all partitions (~4.2 GB, ~4 min)
#   adb shell sh /data/local/tmp/aoc_backup_partitions.sh boot logo  # only these
#   adb pull /data/local/tmp/aoc_backup
#
# Each image is checked twice: SHA-256 of the block device == SHA-256 of the copied file.
# SHA256SUMS.txt uses the "<hash> *<file>" format, so the PC copy can be checked the same way.
O=${OUT:-/data/local/tmp/aoc_backup}
B=/dev/block/by-name
die() { echo "ERROR: $*"; exit 1; }

[ "$(id -u)" = 0 ] || die "needs root. In the DSU GSI run 'adb root' first."
[ "$(getprop ro.gsid.image_running)" = 1 ] || echo "WARN: not running the DSU GSI (ro.gsid.image_running != 1)"
[ -d "$B" ] || die "$B not found"

PARTS="$*"
if [ -z "$PARTS" ]; then
  for p in $(ls "$B"); do
    case "$p" in userdata|mmcblk[0-9]) continue ;; esac   # user data and the whole-disk node
    PARTS="$PARTS $p"
  done
  GPT=1
fi

need=0
for p in $PARTS; do
  [ -e "$B/$p" ] || die "no partition named $p"
  need=$((need + $(blockdev --getsz "$B/$p") / 2048))   # 512-byte sectors -> MB (stays within 32-bit shell math)
done
free=$(df -k /data | tail -n 1 | awk '{print int($4/1024)}')
echo "partitions:$PARTS"
echo "need ${need} MB, free ${free} MB on /data"
[ "$free" -gt $((need + 512)) ] || die "not enough space on /data"

mkdir -p "$O" && cd "$O" || exit 1
: > SHA256SUMS.txt
fail=0
n=0
total=$(echo $PARTS | wc -w)
for p in $PARTS; do
  n=$((n + 1))
  printf '(%d/%d) %-14s ' "$n" "$total" "$p"
  dd if="$B/$p" of="$p.img" bs=4M 2>/dev/null || { echo "dd FAILED"; fail=1; continue; }
  h1=$(sha256sum "$B/$p" | cut -d' ' -f1)
  h2=$(sha256sum "$p.img" | cut -d' ' -f1)
  if [ "$h1" = "$h2" ]; then
    echo "$h2 *$p.img" >> SHA256SUMS.txt
    echo "ok  $(ls -l "$p.img" | awk '{printf "%d", $5 / 1048576}') MB"
  else
    echo "HASH MISMATCH"; fail=1
  fi
done

# GPT + idbloader area in front of the first partition (only for a full backup)
if [ "$GPT" = 1 ] && [ -r /sys/class/block/mmcblk2p1/start ]; then
  start=$(cat /sys/class/block/mmcblk2p1/start)
  dd if=/dev/block/mmcblk2 of=gpt_head.img bs=512 count="$start" 2>/dev/null
  h1=$(dd if=/dev/block/mmcblk2 bs=512 count="$start" 2>/dev/null | sha256sum | cut -d' ' -f1)
  h2=$(sha256sum gpt_head.img | cut -d' ' -f1)
  [ "$h1" = "$h2" ] && { echo "$h2 *gpt_head.img" >> SHA256SUMS.txt; echo "gpt_head       ok"; } || { echo "gpt_head HASH MISMATCH"; fail=1; }
fi

getprop > getprop.txt
ls -l "$B" > partitions.txt
[ "$fail" = 0 ] || die "some images failed - see above"
echo "DONE: $O ($(du -sm "$O" | cut -f1) MB). Now on the PC: adb pull $O"
