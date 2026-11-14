package io.github.zlkiki.einkscreens;

import android.graphics.Bitmap;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.util.zip.CRC32;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

/** /odm/media/bootanimation.zip 교체용 Magisk 모듈 파일 생성. */
final class BootAnim {
    static final String MODID = "eink_bootanim";
    static final String MODDIR = "/data/adb/modules/" + MODID;
    static final String TARGET = "/odm/media/bootanimation.zip";
    static final int FRAMES = 6;

    /** 같은 파일을 덮는 다른 모듈 폴더 목록 (앱 모듈 제외). 각 줄: 폴더 + " active|disabled|remove" */
    static final String FIND_OTHERS = "for m in /data/adb/modules/*; do"
            + " [ \"$m\" = \"" + MODDIR + "\" ] && continue;"
            + " grep -qs '" + TARGET + "' \"$m/post-fs-data.sh\" \"$m/service.sh\" || continue;"
            + " s=active; [ -f \"$m/disable\" ] && s=disabled; [ -f \"$m/remove\" ] && s=remove;"
            + " echo \"$m $s\"; done";

    /** 현재 걸린 bind mount를 모두 풂 (부팅 애니메이션은 부팅 때만 쓰이므로 안전). */
    static final String UNMOUNT = "n=0; while grep -q ' " + TARGET + " ' /proc/self/mounts && [ $n -lt 5 ]; do"
            + " umount " + TARGET + " 2>/dev/null || break; n=$((n+1)); done; true";

    static final String POST_FS_DATA = "#!/system/bin/sh\n"
            + "MODDIR=${0%/*}\n"
            + "SRC=$MODDIR/bootanimation.zip\n"
            + "DST=/odm/media/bootanimation.zip\n"
            + "[ -f \"$SRC\" ] && [ -f \"$DST\" ] || exit 0\n"
            + "# oemfs cannot be set on /data; vendor_file is not readable by bootanim; system_file works.\n"
            + "chcon u:object_r:system_file:s0 \"$SRC\"\n"
            + "chmod 0644 \"$SRC\"\n"
            + "mount -o bind \"$SRC\" \"$DST\"\n";

    static final String MODULE_PROP = "id=" + MODID + "\n"
            + "name=E-Ink boot animation\n"
            + "version=v2\nversionCode=2\n"
            + "author=E-Ink Screens app\n"
            + "description=Custom /odm/media/bootanimation.zip (made by E-Ink Screens app). Delete to restore stock.\n";

    private BootAnim() {}

    /** 세로 사진 + 진행 막대 프레임으로 무압축 zip 작성. */
    static void writeZip(Bitmap portrait, File out) throws Exception {
        try (ZipOutputStream z = new ZipOutputStream(new FileOutputStream(out))) {
            stored(z, "desc.txt", (Img.W + " " + Img.H + " 1\np 0 0 part0\n").getBytes("UTF-8"));
            Bitmap g = Img.grayBitmap(portrait);
            for (int i = 0; i < FRAMES; i++) {
                Bitmap f = Img.withProgress(g, (i + 1) / (float) FRAMES);
                ByteArrayOutputStream b = new ByteArrayOutputStream();
                f.compress(Bitmap.CompressFormat.PNG, 100, b);
                stored(z, String.format("part0/%03d.png", i + 1), b.toByteArray());
            }
        }
    }

    private static void stored(ZipOutputStream z, String name, byte[] d) throws Exception {
        ZipEntry e = new ZipEntry(name);
        e.setMethod(ZipEntry.STORED);
        e.setSize(d.length);
        e.setCompressedSize(d.length);
        CRC32 c = new CRC32();
        c.update(d);
        e.setCrc(c.getValue());
        z.putNextEntry(e);
        z.write(d);
        z.closeEntry();
    }
}
