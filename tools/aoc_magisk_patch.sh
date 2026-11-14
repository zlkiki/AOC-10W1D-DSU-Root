#!/system/bin/sh
# AOC 10W1D: patch the stock boot.img with Magisk ON THE DEVICE, without the Magisk app's file picker.
# (This firmware has no DocumentsUI, so "Select and Patch a File" may have nothing to pick with.)
#
# Same steps and flags as MAGISK_AND_SCREENS.md §3.1. Runs as the normal adb shell user
# and writes only inside /data/local/tmp/mk. It never touches a partition.
#
#   adb shell mkdir -p /data/local/tmp/mk
#   adb push Magisk-v30.7.apk boot.img aoc_magisk_patch.sh /data/local/tmp/mk/
#   adb shell sh /data/local/tmp/mk/aoc_magisk_patch.sh
#   adb pull /data/local/tmp/mk/magisk_patched_boot.img
#
W=${MK_DIR:-/data/local/tmp/mk}
cd "$W" || exit 1
die() { echo "ERROR: $*"; exit 1; }

APK=$(ls Magisk*.apk 2>/dev/null | head -n 1)
[ -n "$APK" ] || die "Magisk*.apk not found in $W"
[ -f boot.img ] || die "boot.img not found in $W"
[ "$(getprop ro.product.cpu.abi)" = arm64-v8a ] || die "this script is for arm64-v8a devices"
[ "$(head -c 8 boot.img)" = "ANDROID!" ] || die "boot.img has no ANDROID! header (not a boot image?)"
SZ=$(stat -c %s boot.img)
[ "$SZ" = 67108864 ] || echo "WARN: boot.img is $SZ bytes (AOC 10W1D stock boot is 67108864)"
echo "[1/4] $APK, boot.img $SZ bytes, sha256 $(sha256sum boot.img | cut -d' ' -f1)"

rm -rf kit && mkdir kit && cd kit || exit 1
unzip -q -o "../$APK" assets/boot_patch.sh assets/util_functions.sh assets/stub.apk \
  lib/arm64-v8a/libmagiskinit.so lib/arm64-v8a/libmagiskboot.so lib/arm64-v8a/libmagisk.so \
  lib/arm64-v8a/libinit-ld.so lib/arm64-v8a/libbusybox.so || die "could not extract the Magisk kit from $APK"
mv assets/* . && rmdir assets
for f in magiskinit magiskboot magisk init-ld busybox; do
  mv "lib/arm64-v8a/lib$f.so" "$f" || die "lib$f.so missing"
done
rm -rf lib
chmod 755 ./*
echo "[2/4] Magisk kit ready"

# Values the Magisk app itself picks on this device (Android 11 system-as-root, no encryption, vbmeta partition)
export BOOTMODE=true KEEPVERITY=true KEEPFORCEENCRYPT=false PATCHVBMETAFLAG=false \
       RECOVERYMODE=false LEGACYSAR=false ASH_STANDALONE=1
./busybox sh boot_patch.sh "$W/boot.img" > "$W/patch.log" 2>&1
[ -f new-boot.img ] || { cat "$W/patch.log"; die "patch failed (log above)"; }
mv new-boot.img "$W/magisk_patched_boot.img"
echo "[3/4] patched (log: $W/patch.log)"

# Check: kernel, dtb and second/resource must be identical; only the ramdisk may change.
mkdir a b
(cd a && ../magiskboot unpack "$W/boot.img" >/dev/null 2>&1)
(cd b && ../magiskboot unpack "$W/magisk_patched_boot.img" >/dev/null 2>&1)
OK=1
for f in kernel dtb second; do
  if [ -f "a/$f" ]; then
    if cmp -s "a/$f" "b/$f"; then echo "      $f: same"; else echo "      $f: DIFFERENT"; OK=0; fi
  fi
done
cmp -s a/ramdisk.cpio b/ramdisk.cpio && { echo "      ramdisk: NOT changed"; OK=0; } || echo "      ramdisk: changed (Magisk added)"
[ "$(stat -c %s "$W/magisk_patched_boot.img")" -le 67108864 ] || { echo "      size: larger than the boot partition"; OK=0; }
cd "$W" && rm -rf kit
[ "$OK" = 1 ] || die "unexpected difference - do NOT flash this image"
echo "[4/4] OK  magisk_patched_boot.img sha256 $(sha256sum magisk_patched_boot.img | cut -d' ' -f1)"
