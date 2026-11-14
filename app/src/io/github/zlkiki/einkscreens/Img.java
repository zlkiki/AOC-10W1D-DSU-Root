package io.github.zlkiki.einkscreens;

import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Matrix;
import android.graphics.Paint;
import android.graphics.Rect;
import android.graphics.RectF;

/** E-Ink 화면용 이미지 변환. 패널 1404x1872(세로). 저장 형식에 따라 시계방향 90° 회전. */
final class Img {
    static final int W = 1404, H = 1872;

    private Img() {}

    /** 사진을 세로 1404x1872에 맞춤. crop=true면 가운데 잘라 채우기, false면 흰 여백으로 전체 보이기. */
    static Bitmap fitPortrait(Bitmap src, boolean crop) {
        Bitmap out = Bitmap.createBitmap(W, H, Bitmap.Config.ARGB_8888);
        Canvas c = new Canvas(out);
        c.drawColor(Color.WHITE);
        float sw = src.getWidth(), sh = src.getHeight();
        float scale = crop ? Math.max(W / sw, H / sh) : Math.min(W / sw, H / sh);
        float dw = sw * scale, dh = sh * scale;
        RectF dst = new RectF((W - dw) / 2f, (H - dh) / 2f, (W + dw) / 2f, (H + dh) / 2f);
        Paint p = new Paint(Paint.FILTER_BITMAP_FLAG | Paint.ANTI_ALIAS_FLAG);
        c.drawBitmap(src, null, dst, p);
        return out;
    }

    /** 0~255 그레이 배열(행 우선). */
    static int[] gray(Bitmap b) {
        int w = b.getWidth(), h = b.getHeight();
        int[] px = new int[w * h];
        b.getPixels(px, 0, w, 0, 0, w, h);
        for (int i = 0; i < px.length; i++) {
            int c = px[i];
            int r = (c >> 16) & 0xff, g = (c >> 8) & 0xff, bl = c & 0xff;
            px[i] = (r * 299 + g * 587 + bl * 114) / 1000;
        }
        return px;
    }

    static Bitmap fromGray(int[] g, int w, int h) {
        int[] px = new int[w * h];
        for (int i = 0; i < px.length; i++) {
            int v = Math.max(0, Math.min(255, g[i]));
            px[i] = 0xff000000 | (v << 16) | (v << 8) | v;
        }
        Bitmap b = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888);
        b.setPixels(px, 0, w, 0, 0, w, h);
        return b;
    }

    /** Floyd-Steinberg 오차 확산으로 16단계(0~15) 양자화. */
    static int[] dither16(int[] g, int w, int h) {
        float[] e = new float[g.length];
        for (int i = 0; i < g.length; i++) e[i] = g[i];
        int[] q = new int[g.length];
        for (int y = 0; y < h; y++) {
            for (int x = 0; x < w; x++) {
                int i = y * w + x;
                float v = Math.max(0f, Math.min(255f, e[i]));
                int lv = Math.round(v / 17f);
                q[i] = lv;
                float err = v - lv * 17f;
                if (x + 1 < w) e[i + 1] += err * 7 / 16f;
                if (y + 1 < h) {
                    if (x > 0) e[i + w - 1] += err * 3 / 16f;
                    e[i + w] += err * 5 / 16f;
                    if (x + 1 < w) e[i + w + 1] += err / 16f;
                }
            }
        }
        return q;
    }

    static Bitmap rotateCw(Bitmap b) {
        Matrix m = new Matrix();
        m.postRotate(90);
        return Bitmap.createBitmap(b, 0, 0, b.getWidth(), b.getHeight(), m, true);
    }

    static Bitmap rotateCcw(Bitmap b) {
        Matrix m = new Matrix();
        m.postRotate(-90);
        return Bitmap.createBitmap(b, 0, 0, b.getWidth(), b.getHeight(), m, true);
    }

    static Bitmap grayBitmap(Bitmap b) {
        return fromGray(gray(b), b.getWidth(), b.getHeight());
    }

    static Bitmap copy(Bitmap b) {
        return b.copy(Bitmap.Config.ARGB_8888, true);
    }

    /** 아래쪽 흰 띠 위에 진행 막대(0..1). 부팅 애니메이션 프레임용. */
    static Bitmap withProgress(Bitmap portrait, float frac) {
        Bitmap b = copy(portrait);
        Canvas c = new Canvas(b);
        Paint p = new Paint(Paint.ANTI_ALIAS_FLAG);
        p.setColor(Color.WHITE);
        c.drawRect(0, H - 230, W, H, p);
        int x0 = 252, x1 = W - 252, y0 = H - 150, y1 = H - 100;
        p.setColor(Color.BLACK);
        p.setStyle(Paint.Style.STROKE);
        p.setStrokeWidth(6);
        c.drawRect(x0, y0, x1, y1, p);
        p.setStyle(Paint.Style.FILL);
        c.drawRect(x0 + 6, y0 + 6, x0 + 6 + (x1 - x0 - 12) * frac, y1 - 6, p);
        return b;
    }

    /** 아래쪽 흰 띠 위에 배터리 아이콘. level 0..5 칸, warn이면 느낌표. 충전 화면용. */
    static Bitmap withBattery(Bitmap portrait, int level, boolean warn) {
        Bitmap b = copy(portrait);
        Canvas c = new Canvas(b);
        Paint p = new Paint(Paint.ANTI_ALIAS_FLAG);
        p.setColor(Color.WHITE);
        c.drawRect(0, H - 330, W, H, p);
        int bw = 420, bh = 170, x0 = (W - bw) / 2, y0 = H - 260;
        p.setColor(Color.BLACK);
        p.setStyle(Paint.Style.STROKE);
        p.setStrokeWidth(12);
        c.drawRoundRect(new RectF(x0, y0, x0 + bw, y0 + bh), 20, 20, p);
        p.setStyle(Paint.Style.FILL);
        c.drawRect(x0 + bw, y0 + 50, x0 + bw + 28, y0 + bh - 50, p);
        int pad = 22, gap = 12, cell = (bw - 2 * pad - 4 * gap) / 5;
        for (int i = 0; i < 5; i++) {
            int cx = x0 + pad + i * (cell + gap);
            p.setColor(i < level ? Color.rgb(40, 40, 40) : Color.rgb(210, 210, 210));
            c.drawRect(cx, y0 + pad, cx + cell, y0 + bh - pad, p);
        }
        if (warn) {
            p.setColor(Color.WHITE);
            c.drawRect(x0 + 14, y0 + 14, x0 + bw - 14, y0 + bh - 14, p);
            p.setColor(Color.BLACK);
            p.setTextSize(140);
            p.setFakeBoldText(true);
            p.setTextAlign(Paint.Align.CENTER);
            Rect tb = new Rect();
            p.getTextBounds("!", 0, 1, tb);
            c.drawText("!", x0 + bw / 2f, y0 + bh / 2f + tb.height() / 2f, p);
        }
        return b;
    }

    /** 미리보기용 축소. */
    static Bitmap thumb(Bitmap b, int maxH) {
        float s = (float) maxH / b.getHeight();
        return Bitmap.createScaledBitmap(b, Math.max(1, Math.round(b.getWidth() * s)), maxH, true);
    }
}
