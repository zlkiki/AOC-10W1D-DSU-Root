#!/usr/bin/env python3
"""AOC 10W1D E-Ink 화면 테마 그림 생성기 (Pillow + numpy).

'E-Ink 화면 바꾸기' 앱의 [사진 고르기]에 쓸 세로 1404x1872, 16단계 그레이 그림을 테마 9종 x 5장 만든다.
글자·이름 없음. 아래쪽(y > 1450)은 흰색으로 비워 둠 → 앱이 진행 막대(부팅 애니메이션)·배터리 칸(충전)을 그 자리에 그림.

  1_슬립 · 2_종료 · 3_부팅로고 · 4_부팅애니 · 5_충전

사용법: python aoc_make_eink_themes.py OUT_DIR [테마id ...]
출력: OUT_DIR/<NN>_<테마>/<1..5>_*.png, OUT_DIR/<NN>_<테마>/_sheet.png(전 단계 확인용), OUT_DIR/_all_themes.png(한눈에 보기)
"""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

W, H = 1404, 1872
S = 2  # supersampling
K, D, M, L, P, WH = 0, 68, 136, 204, 238, 255
CX = W // 2

THEMES = [
    ("moon", "달의 위상", "Moon phases", "차오르는 달로 진행과 배터리를 보여 줌", "A waxing moon shows progress and battery"),
    ("ink", "종이와 잉크", "Paper & ink", "펼친 책, 덮인 책, 만년필 펜촉, 차오르는 잉크병", "Open book, closed book, pen nib, filling ink bottle"),
    ("geometry", "미니멀 기하", "Minimal geometry", "원·삼각형·사각형과 진행 고리", "Circle, triangle, square and a progress ring"),
    ("hourglass", "모래시계", "Hourglass", "모래가 아래로 쌓이며 진행", "Sand falls as progress"),
    ("sprout", "새싹", "Sprout", "화분의 새싹이 자라 꽃이 핌", "A sprout grows into a flower"),
    ("sunrise", "산과 해돋이", "Mountain sunrise", "산 너머로 해가 떠오름", "The sun rises over the mountains"),
    ("go", "바둑", "Go board", "바둑돌이 하나씩 놓임", "Stones are placed one by one"),
    ("dipper", "북두칠성", "Big Dipper", "별이 하나씩 이어짐", "Stars connect one by one"),
    ("coffee", "커피 한 잔", "Coffee", "잔에 커피가 차오름", "The cup fills with coffee"),
]


class Cv:
    def __init__(self):
        self.im = Image.new("L", (W * S, H * S), WH)
        self.d = ImageDraw.Draw(self.im)

    @staticmethod
    def s(v):
        return int(round(v * S))

    def pts(self, pts):
        return [(x * S, y * S) for x, y in pts]

    def circle(self, cx, cy, r, fill=None, outline=None, width=0):
        self.d.ellipse([(cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S], fill=fill, outline=outline, width=self.s(width))

    def ellipse(self, x0, y0, x1, y1, fill=None, outline=None, width=0):
        self.d.ellipse([x0 * S, y0 * S, x1 * S, y1 * S], fill=fill, outline=outline, width=self.s(width))

    def rect(self, x0, y0, x1, y1, fill=None, outline=None, width=0, radius=0):
        box = [x0 * S, y0 * S, x1 * S, y1 * S]
        if radius:
            self.d.rounded_rectangle(box, self.s(radius), fill=fill, outline=outline, width=self.s(width))
        else:
            self.d.rectangle(box, fill=fill, outline=outline, width=self.s(width))

    def line(self, pts, fill=K, width=6, caps=True):
        self.d.line(self.pts(pts), fill=fill, width=self.s(width), joint="curve")
        if caps:
            for x, y in (pts[0], pts[-1]):
                self.circle(x, y, width / 2, fill=fill)

    def poly(self, pts, fill=None, outline=None, width=0):
        self.d.polygon(self.pts(pts), fill=fill, outline=outline, width=self.s(width) if outline is not None else 0)

    def arc(self, cx, cy, r, start, end, fill=K, width=6):
        self.d.arc([(cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S], start, end, fill=fill, width=self.s(width))

    def dashed(self, a, b, fill=K, width=4, dash=18, gap=14):
        (x0, y0), (x1, y1) = a, b
        n = math.hypot(x1 - x0, y1 - y0)
        t = 0.0
        while t < n:
            e = min(n, t + dash)
            self.line([(x0 + (x1 - x0) * t / n, y0 + (y1 - y0) * t / n), (x0 + (x1 - x0) * e / n, y0 + (y1 - y0) * e / n)], fill, width)
            t = e + gap

    def done(self) -> Image.Image:
        im = self.im.resize((W, H), Image.LANCZOS)
        # bottom caption band stays white
        im.paste(WH, (0, 1450, W, H))
        return im.point(lambda v: min(15, int(round(v / 17))) * 17)


# ------------------------------------------------------------------ shared motifs

def sparkle(cv, cx, cy, r, fill=K):
    k = r * 0.22
    cv.poly([(cx, cy - r), (cx + k, cy - k), (cx + r, cy), (cx + k, cy + k), (cx, cy + r), (cx - k, cy + k), (cx - r, cy), (cx - k, cy - k)], fill=fill)


def stars(cv, seed, n, avoid=None, box=(80, 80, W - 80, 1400), rmin=8, rmax=26, fill=K):
    rnd = random.Random(seed)
    placed = 0
    while placed < n:
        x, y = rnd.uniform(box[0], box[2]), rnd.uniform(box[1], box[3])
        if avoid and math.hypot(x - avoid[0], y - avoid[1]) < avoid[2]:
            continue
        r = rnd.uniform(rmin, rmax)
        if r < 12:
            cv.circle(x, y, r * 0.45, fill=fill)
        else:
            sparkle(cv, x, y, r, fill)
        placed += 1


def crescent(cv, cx, cy, r, fill=K, bg=WH):
    cv.circle(cx, cy, r, fill=fill)
    cv.circle(cx + r * 0.42, cy - r * 0.22, r * 0.86, fill=bg)


def moon(cv, cx, cy, r, f, dark=D, craters=True):
    """Moon disk, lit fraction f (0 new .. 1 full), waxing (lit on the right)."""
    R = int(r * S)
    yy, xx = np.mgrid[-R:R, -R:R].astype(float) + 0.5
    nx, ny = xx / R, yy / R
    inside = nx ** 2 + ny ** 2 <= 1
    k = math.cos(math.pi * f)
    lit = inside & (nx > k * np.sqrt(np.clip(1 - ny ** 2, 0, 1)))
    cv.circle(cx, cy, r, fill=dark)
    layer = Image.new("L", (2 * R, 2 * R), WH)
    if craters:
        ld = ImageDraw.Draw(layer)
        for (u, v, q) in [(0.3, -0.35, 0.16), (-0.25, 0.2, 0.22), (0.45, 0.35, 0.12), (-0.5, -0.4, 0.1), (0.05, 0.6, 0.09)]:
            ld.ellipse([(u - q + 1) * R, (v - q + 1) * R, (u + q + 1) * R, (v + q + 1) * R], fill=P, outline=L, width=int(4 * S))
    cv.im.paste(layer, (int((cx - r) * S), int((cy - r) * S)), Image.fromarray((lit * 255).astype("uint8")))
    cv.circle(cx, cy, r, outline=K, width=10)


def leaf(cv, x, y, length, ang, fill=L):
    pts_u, pts_l = [], []
    ca, sa = math.cos(ang), math.sin(ang)
    for i in range(21):
        t = i / 20
        ax, hw = t * length, math.sin(math.pi * t) * length * 0.26
        pts_u.append((x + ax * ca - hw * sa, y + ax * sa + hw * ca))
        pts_l.append((x + ax * ca + hw * sa, y + ax * sa - hw * ca))
    cv.poly(pts_u + pts_l[::-1], fill=fill, outline=K, width=6)
    cv.line([(x, y), (x + length * 0.85 * ca, y + length * 0.85 * sa)], fill=K, width=4)


# ------------------------------------------------------------------ A. moon

def moon_lv(f):
    cv = Cv()
    stars(cv, 1, 14, avoid=(CX, 760, 520))
    moon(cv, CX, 760, 400, f)
    return cv.done()


def moon_sleep():
    cv = Cv()
    stars(cv, 2, 26, avoid=(CX + 40, 700, 470))
    moon(cv, CX + 40, 700, 340, 0.22)
    return cv.done()


def moon_off():
    cv = Cv()
    cv.circle(CX, 760, 400, outline=M, width=8)
    return cv.done()


def moon_logo1():
    cv = Cv()
    stars(cv, 3, 30, avoid=(CX, 740, 560))
    moon(cv, CX, 740, 460, 1)
    return cv.done()


def moon_logo2():
    cv = Cv()
    stars(cv, 4, 16, avoid=(CX, 560, 380), box=(80, 80, W - 80, 1000))
    moon(cv, CX, 560, 290, 1)
    cv.line([(120, 1060), (W - 120, 1060)], width=8)
    for i, w in enumerate([300, 220, 150, 90]):
        cv.line([(CX - w, 1130 + i * 60), (CX + w, 1130 + i * 60)], fill=M, width=10)
    return cv.done()


# ------------------------------------------------------------------ B. paper & ink

def ink_bottle(cv, f):
    x0, x1, y0, y1 = 432, 972, 620, 1260
    cv.rect(612, 440, 792, 560, fill=D, outline=K, width=8, radius=12)  # cap
    cv.rect(572, 540, 832, 640, fill=WH, outline=K, width=10, radius=10)  # neck
    cv.rect(x0, y0, x1, y1, fill=WH, outline=K, width=12, radius=70)
    if f > 0:
        top = y1 - 20 - (y1 - y0 - 60) * f
        cv.rect(x0 + 20, top, x1 - 20, y1 - 20, fill=D, radius=52 if f < 0.95 else 52)
        # wave on the ink surface
        pts = [(x0 + 20 + i * 25, top + 10 * math.sin(i * 0.8)) for i in range(int((x1 - x0 - 40) / 25) + 1)]
        cv.line(pts, fill=K, width=6)
    cv.line([(x0 + 60, y0 + 90), (x0 + 60, y0 + 320)], fill=L, width=14)  # glass highlight
    cv.rect(x0, y0, x1, y1, outline=K, width=12, radius=70)


def open_book(cv, cy=820, ribbon=True):
    l, r, t, b = 162, 1242, cy - 340, cy + 300
    cv.poly([(l, t + 40), (CX, t), (CX, b), (l, b + 40)], fill=WH, outline=K, width=10)
    cv.poly([(r, t + 40), (CX, t), (CX, b), (r, b + 40)], fill=WH, outline=K, width=10)
    cv.line([(l, b + 40), (CX, b + 70), (r, b + 40)], width=8)
    for i in range(8):
        y = t + 110 + i * 62
        cv.line([(l + 70, y + 30 * (1 - (i * 62 + 110) / (b - t))), (CX - 60, y - 6)], fill=M, width=8)
        cv.line([(CX + 60, y - 6), (r - 70, y + 30 * (1 - (i * 62 + 110) / (b - t)))], fill=M, width=8)
    if ribbon:
        cv.poly([(CX + 70, t + 10), (CX + 130, t + 10), (CX + 130, b + 180), (CX + 100, b + 140), (CX + 70, b + 180)], fill=D, outline=K, width=6)


def ink_lv(f):
    cv = Cv()
    ink_bottle(cv, f)
    return cv.done()


def ink_sleep():
    cv = Cv()
    open_book(cv)
    return cv.done()


def ink_off():
    cv = Cv()
    cv.rect(432, 360, 972, 1260, fill=WH, outline=K, width=12, radius=18)
    cv.rect(432, 360, 520, 1260, fill=D, outline=K, width=12, radius=18)
    cv.rect(600, 520, 900, 700, outline=K, width=6)
    cv.line([(640, 590), (860, 590)], fill=M, width=10)
    cv.line([(680, 640), (820, 640)], fill=M, width=8)
    for i in range(5):
        cv.line([(972, 400 + i * 4), (990, 410 + i * 4)], fill=M, width=4, caps=False)
    return cv.done()


def nib(cv, cx, top, h, fill=K):
    w = h * 0.36
    cv.poly([(cx - w, top), (cx + w, top), (cx + w, top + h * 0.45), (cx, top + h), (cx - w, top + h * 0.45)], fill=fill)
    cv.rect(cx - w - 20, top - 70, cx + w + 20, top + 10, fill=D, outline=K, width=8, radius=10)
    hole = top + h * 0.42
    cv.circle(cx, hole, h * 0.055, fill=WH)
    cv.line([(cx, hole), (cx, top + h - 6)], fill=WH, width=8, caps=False)


def ink_logo1():
    cv = Cv()
    nib(cv, CX, 360, 860)
    return cv.done()


def ink_logo2():
    cv = Cv()
    nib(cv, CX, 260, 620)
    cv.circle(CX, 1180, 110, fill=K)
    cv.poly([(CX - 98, 1130), (CX, 960), (CX + 98, 1130)], fill=K)
    cv.ellipse(CX - 300, 1300, CX + 300, 1360, fill=L)
    return cv.done()


# ------------------------------------------------------------------ C. geometry

def geo_lv(f):
    cv = Cv()
    cv.circle(CX, 760, 400, outline=L, width=10)
    if f > 0:
        if f >= 1:
            cv.circle(CX, 760, 400, outline=K, width=56)
        else:
            cv.arc(CX, 760, 400, -90, -90 + 360 * f, width=56)
    n = int(round(f * 6))
    for i in range(6):
        a = -math.pi / 2 + i * math.pi / 3
        cv.circle(CX + 160 * math.cos(a), 760 + 160 * math.sin(a), 34, fill=K if i < n else None, outline=K, width=6)
    return cv.done()


def geo_sleep():
    cv = Cv()
    cv.circle(560, 700, 300, fill=P, outline=K, width=8)
    cv.poly([(CX + 40, 380), (1080, 1080), (360, 1080)], outline=K, width=12)
    cv.rect(800, 840, 1060, 1100, fill=D)
    cv.line([(220, 1220), (1180, 1220)], width=10)
    cv.circle(1100, 420, 60, fill=K)
    return cv.done()


def geo_off():
    cv = Cv()
    cv.rect(CX - 250, 510, CX + 250, 1010, outline=K, width=14)
    cv.line([(CX - 120, 760), (CX + 120, 760)], fill=M, width=14)
    return cv.done()


def geo_logo1():
    cv = Cv()
    cv.circle(300, 760, 170, fill=K)
    cv.poly([(CX, 580), (CX + 180, 930), (CX - 180, 930)], outline=K, width=14)
    cv.rect(W - 470, 590, W - 130, 930, fill=M)
    return cv.done()


def geo_logo2():
    cv = Cv()
    for i, r in enumerate(range(460, 40, -60)):
        cv.circle(CX, 760, r, outline=K if i % 2 == 0 else M, width=14)
    cv.circle(CX, 760, 30, fill=K)
    return cv.done()


# ------------------------------------------------------------------ D. hourglass

def hourglass(cv, cx, cy, f, stream=True, sand=True, col=K):
    hh = 430  # half height of glass

    def hw(u):  # half width at u in [-1, 1]
        return 26 + 214 * abs(u) ** 0.7

    us = [i / 40 for i in range(-40, 41)]
    left = [(cx - hw(u), cy + u * hh) for u in us]
    right = [(cx + hw(u), cy + u * hh) for u in us]
    if sand:
        if f < 1:  # top sand sits above the neck
            ut = -(1 - f) * 0.82
            seg = [u for u in us if ut <= u <= -0.04]
            if seg:
                cv.poly([(cx - hw(u), cy + u * hh) for u in seg] + [(cx + hw(u), cy + u * hh) for u in seg[::-1]], fill=M)
        if f > 0:  # bottom pile
            ub = 1 - f * 0.82
            seg = [u for u in us if u >= ub]
            peak = cy + (ub - 0.12) * hh
            cv.poly([(cx - hw(ub), cy + ub * hh), (cx, peak), (cx + hw(ub), cy + ub * hh)] + [(cx + hw(u), cy + u * hh) for u in seg] + [(cx - hw(u), cy + u * hh) for u in seg[::-1]], fill=M)
        if stream and 0 < f < 1:
            cv.line([(cx, cy), (cx, cy + (1 - f * 0.82 - 0.12) * hh)], fill=D, width=6)
    cv.line(left, fill=col, width=10)
    cv.line(right, fill=col, width=10)
    for y in (cy - hh - 40, cy + hh + 40):
        cv.rect(cx - 300, y - 30, cx + 300, y + 30, fill=D if col == K else L, outline=col, width=8, radius=12)
    for x in (cx - 260, cx + 260):
        cv.line([(x, cy - hh - 10), (x, cy + hh + 10)], fill=col, width=14)


def hg_lv(f):
    cv = Cv()
    hourglass(cv, CX, 760, f)
    return cv.done()


def hg_sleep():
    cv = Cv()
    hourglass(cv, CX - 40, 800, 1, stream=False)
    crescent(cv, 1120, 300, 110)
    stars(cv, 5, 6, box=(900, 120, 1320, 600), avoid=(1120, 300, 150))
    return cv.done()


def hg_off():
    cv = Cv()
    hourglass(cv, CX, 760, 0, sand=False, col=M)
    return cv.done()


def hg_logo1():
    cv = Cv()
    hourglass(cv, CX, 760, 0, stream=False)
    return cv.done()


def hg_logo2():
    cv = Cv()
    hourglass(cv, CX, 760, 0.08)
    return cv.done()


# ------------------------------------------------------------------ E. sprout

def pot(cv, soil=True):
    cv.poly([(512, 1110), (892, 1110), (842, 1400), (562, 1400)], fill=D, outline=K, width=8)
    cv.rect(482, 1060, 922, 1130, fill=K, radius=10)
    if soil:
        cv.ellipse(530, 1040, 874, 1090, fill=M)


def plant(cv, f):
    pot(cv)
    if f <= 0:
        cv.ellipse(CX - 22, 1030, CX + 22, 1058, fill=K)
        return
    top = 1050 - (120 + 640 * f)
    pts = [(CX + 18 * math.sin((1050 - y) / 120), y) for y in range(1050, int(top) - 1, -10)]
    cv.line(pts, fill=K, width=12)
    n = max(1, int(round(f * 6)))
    for i in range(n):
        y = 1000 - (i + 0.5) * (1000 - top) / (n + 0.5)
        side = 1 if i % 2 == 0 else -1
        ang = -0.55 if side > 0 else math.pi + 0.55
        leaf(cv, CX + 18 * math.sin((1050 - y) / 120), y, 150 + 40 * (i < 2), ang)
    if f >= 1:
        fx, fy = CX + 18 * math.sin((1050 - top) / 120), top
        for k in range(8):
            a = k * math.pi / 4
            cv.circle(fx + 70 * math.cos(a), fy + 70 * math.sin(a), 48, fill=WH, outline=K, width=6)
        cv.circle(fx, fy, 46, fill=D, outline=K, width=6)


def sprout_lv(f):
    cv = Cv()
    plant(cv, f)
    return cv.done()


def sprout_sleep():
    cv = Cv()
    plant(cv, 0.66)
    crescent(cv, 1110, 300, 110)
    stars(cv, 6, 7, box=(860, 120, 1320, 640), avoid=(1110, 300, 150))
    return cv.done()


def sprout_off():
    cv = Cv()
    pot(cv)
    return cv.done()


def sprout_logo1():
    cv = Cv()
    cv.line([(220, 1150), (W - 220, 1150)], width=10)
    cv.line([(CX, 1150), (CX + 10, 960), (CX, 780)], fill=K, width=16)
    leaf(cv, CX, 790, 330, -0.45)
    leaf(cv, CX, 800, 300, math.pi + 0.45)
    return cv.done()


def sprout_logo2():
    cv = Cv()
    plant(cv, 1)
    return cv.done()


# ------------------------------------------------------------------ F. sunrise

def ranges(cv, filled=True):
    back = [(0, 1000), (180, 760), (330, 880), (520, 640), (720, 860), (900, 700), (1100, 900), (1260, 760), (W, 860), (W, 1420), (0, 1420)]
    front = [(0, 1150), (220, 960), (420, 1100), (640, 900), (860, 1120), (1060, 980), (1250, 1080), (W, 1000), (W, 1420), (0, 1420)]
    if filled:
        cv.poly(back, fill=L, outline=K, width=8)
        cv.poly(front, fill=D, outline=K, width=8)
    else:
        cv.poly(back, fill=WH, outline=M, width=8)
        cv.poly(front, fill=WH, outline=K, width=8)


def sun(cv, cx, cy, r, rays=True):
    if rays:
        for k in range(12):
            a = k * math.pi / 6
            cv.line([(cx + (r + 40) * math.cos(a), cy + (r + 40) * math.sin(a)), (cx + (r + 120) * math.cos(a), cy + (r + 120) * math.sin(a))], width=14)
    cv.circle(cx, cy, r, fill=WH, outline=K, width=12)


def sun_lv(f):
    cv = Cv()
    sun(cv, CX, 1080 - 640 * f, 170, rays=f >= 0.5)
    ranges(cv)
    return cv.done()


def sun_sleep():
    cv = Cv()
    crescent(cv, 960, 380, 150)
    stars(cv, 7, 16, box=(80, 100, W - 80, 640), avoid=(960, 380, 200))
    ranges(cv)
    return cv.done()


def sun_off():
    cv = Cv()
    ranges(cv, filled=False)
    return cv.done()


def sun_logo1():
    cv = Cv()
    sun(cv, CX, 940, 260)
    cv.rect(0, 940, W, 1440, fill=WH)
    cv.line([(100, 940), (W - 100, 940)], width=12)
    for i, w in enumerate([260, 190, 120]):
        cv.line([(CX - w, 1020 + i * 70), (CX + w, 1020 + i * 70)], fill=M, width=12)
    return cv.done()


def sun_logo2():
    return sun_lv(1)


# ------------------------------------------------------------------ G. go

GO_MOVES = [(2, 2), (6, 6), (6, 2), (2, 6), (4, 4), (5, 3), (3, 5), (4, 6), (6, 4), (3, 3), (5, 5), (4, 2),
            (2, 4), (7, 4), (4, 7), (1, 3), (3, 1), (7, 6), (6, 7), (5, 1), (1, 5), (7, 2), (2, 7), (4, 5)]


def board(cv, moves=0, last=True):
    x0, y0, step = 252, 310, 112.5
    cv.rect(x0 - 70, y0 - 70, x0 + 8 * step + 70, y0 + 8 * step + 70, fill=P, outline=K, width=8, radius=10)
    for i in range(9):
        cv.line([(x0, y0 + i * step), (x0 + 8 * step, y0 + i * step)], width=4, caps=False)
        cv.line([(x0 + i * step, y0), (x0 + i * step, y0 + 8 * step)], width=4, caps=False)
    for i, j in [(2, 2), (6, 2), (4, 4), (2, 6), (6, 6)]:
        cv.circle(x0 + i * step, y0 + j * step, 11, fill=K)
    for n, (i, j) in enumerate(GO_MOVES[:moves]):
        x, y = x0 + i * step, y0 + j * step
        if n % 2 == 0:
            cv.circle(x, y, 50, fill=K)
            cv.arc(x, y, 32, 200, 250, fill=M, width=6)
        else:
            cv.circle(x, y, 50, fill=WH, outline=K, width=5)
        if last and n == moves - 1:
            cv.circle(x, y, 16, outline=WH if n % 2 == 0 else K, width=5)


def go_lv(f):
    cv = Cv()
    board(cv, int(round(f * len(GO_MOVES))))
    return cv.done()


def go_sleep():
    cv = Cv()
    board(cv, 16, last=False)
    return cv.done()


def go_off():
    cv = Cv()
    board(cv, 0)
    return cv.done()


def go_logo1():
    cv = Cv()
    cv.circle(CX - 150, 740, 230, fill=K)
    cv.arc(CX - 150, 740, 150, 200, 250, fill=M, width=14)
    cv.circle(CX + 200, 820, 230, fill=WH, outline=K, width=10)
    return cv.done()


def go_logo2():
    cv = Cv()
    board(cv, 0)
    cv.circle(252 + 4 * 112.5, 310 + 4 * 112.5, 50, fill=K)
    return cv.done()


# ------------------------------------------------------------------ H. big dipper

DIPPER = [(230, 520), (420, 610), (570, 690), (740, 770), (790, 980), (1080, 1030), (1110, 780)]
POLARIS = (1180, 330)


def dipper(cv, n, polaris=False, faint=False):
    stars(cv, 8, 40, rmin=4, rmax=10, fill=M if faint else L)
    for i in range(n - 1):
        cv.line([DIPPER[i], DIPPER[i + 1]], fill=D, width=6)
    if n == 7:
        cv.line([DIPPER[6], DIPPER[3]], fill=D, width=6)
    for i, (x, y) in enumerate(DIPPER):
        if i < n:
            sparkle(cv, x, y, 54)
            cv.circle(x, y, 12, fill=K)
        else:
            cv.circle(x, y, 16 if faint else 10, fill=D if faint else M)
    if polaris:
        cv.dashed(DIPPER[6], POLARIS, fill=M, width=5)
        sparkle(cv, POLARIS[0], POLARIS[1], 70)


def dipper_lv(f):
    cv = Cv()
    dipper(cv, int(round(f * 7)))
    return cv.done()


def dipper_sleep():
    cv = Cv()
    dipper(cv, 7)
    crescent(cv, 300, 1200, 120)
    return cv.done()


def dipper_off():
    cv = Cv()
    dipper(cv, 0, faint=True)
    return cv.done()


def dipper_logo1():
    cv = Cv()
    stars(cv, 9, 24, avoid=(CX, 740, 420))
    sparkle(cv, CX, 740, 330)
    cv.circle(CX, 740, 40, fill=WH)
    return cv.done()


def dipper_logo2():
    cv = Cv()
    dipper(cv, 7, polaris=True)
    return cv.done()


# ------------------------------------------------------------------ I. coffee

def mug(cv, f, steam):
    cv.ellipse(332, 1180, 1072, 1290, fill=L, outline=K, width=8)  # saucer
    cv.ellipse(890, 760, 1100, 1040, outline=K, width=30)  # handle
    x0, x1, y0, y1 = 432, 952, 620, 1220
    cv.rect(x0, y0, x1, y1, fill=WH, outline=K, width=12, radius=50)
    if f > 0:
        top = y1 - 24 - (y1 - y0 - 70) * f
        cv.rect(x0 + 22, top, x1 - 22, y1 - 22, fill=D, radius=34)
        cv.line([(x0 + 22, top), (x1 - 22, top)], fill=K, width=8, caps=False)
    cv.line([(x0 + 60, y0 + 80), (x0 + 60, y0 + 300)], fill=L, width=14)
    cv.rect(x0, y0, x1, y1, outline=K, width=12, radius=50)
    if steam:
        for k, x in enumerate((582, CX, 822)):
            pts = [(x + 30 * math.sin(t / 30 + k), 560 - t) for t in range(0, 300, 10)]
            cv.line(pts, fill=M, width=12)


def coffee_lv(f):
    cv = Cv()
    mug(cv, f, steam=f >= 0.5)
    return cv.done()


def coffee_sleep():
    cv = Cv()
    mug(cv, 0.8, steam=True)
    crescent(cv, 1150, 300, 100)
    return cv.done()


def coffee_off():
    cv = Cv()
    mug(cv, 0, steam=False)
    return cv.done()


def bean(cv, cx, cy, rx, ry, ang):
    R = int(max(rx, ry) * S) + 20
    layer = Image.new("L", (2 * R, 2 * R), 0)
    ld = ImageDraw.Draw(layer)
    ld.ellipse([R - rx * S, R - ry * S, R + rx * S, R + ry * S], fill=255)
    mask = layer.rotate(ang, resample=Image.BICUBIC)
    cv.im.paste(D, (int(cx * S - R), int(cy * S - R)), mask)
    a = math.radians(-ang)
    pts = []
    for i in range(31):
        t = -1 + 2 * i / 30
        u, v = 30 * math.sin(t * math.pi), t * ry * 0.82
        pts.append((cx + u * math.cos(a) - v * math.sin(a), cy + u * math.sin(a) + v * math.cos(a)))
    cv.line(pts, fill=WH, width=18)


def coffee_logo1():
    cv = Cv()
    bean(cv, CX - 30, 760, 210, 330, 25)
    return cv.done()


def coffee_logo2():
    cv = Cv()
    mug(cv, 1, steam=True)
    return cv.done()


# ------------------------------------------------------------------ main

def render(tid):
    g = globals()
    pre = {"moon": "moon", "ink": "ink", "geometry": "geo", "hourglass": "hg", "sprout": "sprout",
           "sunrise": "sun", "go": "go", "dipper": "dipper", "coffee": "coffee"}[tid]
    imgs = {
        "sleep": g[pre + "_sleep"](),
        "off": g[pre + "_off"](),
        "logo1": g[pre + "_logo1"](),
        "logo2": g[pre + "_logo2"](),
    }
    for i in range(7):
        imgs[f"lv{i}"] = g[pre + "_lv"](i / 6)
    return imgs


# 앱 슬롯별 그림: (파일 이름, 사용할 그림)
SLOTS = [("1_슬립", "sleep"), ("2_종료", "off"), ("3_부팅로고", "logo1"), ("4_부팅애니", "logo2"), ("5_충전", "lv3")]


def strip(imgs, names, tw=234, th=312, gap=12):
    sheet = Image.new("L", (len(names) * tw + (len(names) - 1) * gap, th), WH)
    for i, n in enumerate(names):
        t = imgs[n].resize((tw, th), Image.LANCZOS)
        ImageDraw.Draw(t).rectangle([0, 0, tw - 1, th - 1], outline=M, width=2)
        sheet.paste(t, (i * (tw + gap), 0))
    return sheet


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    only = set(sys.argv[2:])
    rows = []
    for n, (tid, ko, en, dko, den) in enumerate(THEMES, 1):
        if only and tid not in only:
            continue
        d = out / f"{n:02d}_{ko.replace(' ', '')}"
        d.mkdir(exist_ok=True)
        imgs = render(tid)
        for fname, key in SLOTS:
            imgs[key].save(d / f"{fname}.png", optimize=True)
        strip(imgs, ["sleep", "off", "logo1", "logo2"] + [f"lv{i}" for i in range(7)], 117, 156, 6).save(d / "_sheet.png")
        rows.append(strip(imgs, [k for _, k in SLOTS]))
        print(f"{d.name}: {sum(p.stat().st_size for p in d.glob('[0-9]*.png')) // 1024} KB")
    if rows:
        sheet = Image.new("L", (rows[0].width, len(rows) * (rows[0].height + 16)), M)
        for i, r in enumerate(rows):
            sheet.paste(r, (0, i * (r.height + 16)))
        sheet.save(out / "_all_themes.png")


if __name__ == "__main__":
    main()
