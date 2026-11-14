package io.github.zlkiki.einkscreens;

import android.graphics.Bitmap;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.security.MessageDigest;

/**
 * Rockchip E-Ink logo 파티션 (RKEL 헤더 + GR04 4bpp 엔트리).
 * 엔트리: 0x1 U-Boot, 0x2 커널, 0x4..0x80 충전 0~5, 0x100 저전력, 0x200 종료.
 * 픽셀: 짝수 픽셀 = 하위 니블, 가로 저장(세로 내용을 시계방향 90° 회전).
 */
final class Logo {
    static final int PART_SIZE = 16 * 1024 * 1024;
    static final int T_UBOOT = 0x1, T_KERNEL = 0x2, T_LOWPOWER = 0x100, T_POWEROFF = 0x200;
    static final int[] T_CHARGE = {0x4, 0x8, 0x10, 0x20, 0x40, 0x80};

    static final class Entry {
        int type, w, h, off, size;
    }

    final byte[] data;
    final Entry[] entries;

    Logo(byte[] data) {
        if (data.length != PART_SIZE) throw new IllegalArgumentException("logo size " + data.length);
        ByteBuffer b = ByteBuffer.wrap(data).order(ByteOrder.LITTLE_ENDIAN);
        if (data[0] != 'R' || data[1] != 'K' || data[2] != 'E' || data[3] != 'L')
            throw new IllegalArgumentException("RKEL header not found");
        int n = b.getInt(16);
        if (n < 1 || n > 32) throw new IllegalArgumentException("entry count " + n);
        entries = new Entry[n];
        for (int i = 0; i < n; i++) {
            int o = 0x40 + i * 0x20;
            if (data[o] != 'G' || data[o + 1] != 'R' || data[o + 2] != '0' || data[o + 3] != '4')
                throw new IllegalArgumentException("GR04 entry " + i);
            Entry e = new Entry();
            e.w = b.getShort(o + 8) & 0xffff;
            e.h = b.getShort(o + 10) & 0xffff;
            e.type = b.getInt(o + 12);
            e.off = b.getInt(o + 16);
            e.size = b.getInt(o + 20);
            if (e.size != e.w * e.h / 2 || e.off < 0x40 || (long) e.off + e.size > data.length)
                throw new IllegalArgumentException("entry " + i + " bounds");
            entries[i] = e;
        }
        this.data = data;
    }

    Entry find(int type) {
        for (Entry e : entries) if (e.type == type) return e;
        return null;
    }

    /** 세로 비트맵(1404x1872)을 해당 엔트리에 기록. 없는 type이면 false. */
    boolean put(int type, Bitmap portrait) {
        Entry e = find(type);
        if (e == null) return false;
        Bitmap stored = Img.rotateCw(portrait);
        if (stored.getWidth() != e.w || stored.getHeight() != e.h)
            stored = Bitmap.createScaledBitmap(stored, e.w, e.h, true);
        int[] q = Img.dither16(Img.gray(stored), e.w, e.h);
        for (int i = 0; i < e.size; i++) {
            int a = q[2 * i], c = q[2 * i + 1];
            data[e.off + i] = (byte) (a | (c << 4));
        }
        return true;
    }

    /** 다른 logo 이미지에서 해당 엔트리 바이트를 그대로 복사(순정 되돌리기). */
    boolean copyFrom(Logo src, int type) {
        Entry d = find(type), s = src.find(type);
        if (d == null || s == null || d.size != s.size) return false;
        System.arraycopy(src.data, s.off, data, d.off, d.size);
        return true;
    }

    /** 미리보기용 세로 비트맵. */
    Bitmap render(int type) {
        Entry e = find(type);
        if (e == null) return null;
        int[] g = new int[e.w * e.h];
        for (int i = 0; i < e.size; i++) {
            int v = data[e.off + i] & 0xff;
            g[2 * i] = (v & 0x0f) * 17;
            g[2 * i + 1] = (v >> 4) * 17;
        }
        return Img.rotateCcw(Img.fromGray(g, e.w, e.h));
    }

    static String sha256(byte[] d) throws Exception {
        MessageDigest md = MessageDigest.getInstance("SHA-256");
        byte[] h = md.digest(d);
        StringBuilder sb = new StringBuilder();
        for (byte x : h) sb.append(String.format("%02x", x));
        return sb.toString();
    }
}
