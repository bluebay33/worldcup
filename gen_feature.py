# -*- coding: utf-8 -*-
"""生成 Google Play 功能图 feature-graphic.png(1024x500)。
沿用图标的绿色渐变 + 白色足球,右侧大标题 + 小标语,右下角小字 Unofficial。
改文案/配色只需改这里再 python gen_feature.py。"""
import os
import math
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = 1024, 500


def font(paths, size):
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


BOLD = ["C:/Windows/Fonts/msyhbd.ttc", "C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf"]
REG = ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simsun.ttc"]


def fit_font(draw, text, paths, max_w, start_size):
    """从 start_size 往下缩,直到文字宽度 <= max_w,避免裁切。"""
    size = start_size
    while size > 12:
        f = font(paths, size)
        bb = draw.textbbox((0, 0), text, font=f)
        if (bb[2] - bb[0]) <= max_w:
            return f
        size -= 2
    return font(paths, 12)


def pentagon(cx, cy, r, rot=0.0):
    pts = []
    for k in range(5):
        a = math.radians(rot + k * 72 - 90)  # -90:一个顶点朝上
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


img = Image.new("RGB", (W, H), (15, 20, 25))
d = ImageDraw.Draw(img)

# 背景竖向渐变:深绿 -> 深蓝灰(同图标)
top, bot = (20, 110, 60), (12, 22, 30)
for y in range(H):
    t = y / H
    d.line([(0, y), (W, y)], fill=tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)))

# 左侧足球
cx, cy = 250, H / 2
BR = 165
d.ellipse([cx - BR - 6, cy - BR - 6, cx + BR + 6, cy + BR + 6], fill=(0, 0, 0))
d.ellipse([cx - BR, cy - BR, cx + BR, cy + BR], fill=(247, 247, 247))
d.polygon(pentagon(cx, cy, BR * 0.34), fill=(22, 22, 24))
for k in range(5):
    a = math.radians(k * 72 - 90)
    px, py = cx + BR * 0.66 * math.cos(a), cy + BR * 0.66 * math.sin(a)
    d.polygon(pentagon(px, py, BR * 0.2, rot=k * 72 + 36), fill=(22, 22, 24))

# 右侧文字(自动缩放到不超出右边距)
tx = 470
maxw = W - tx - 36
d.text((tx, 110), "2026", font=font(BOLD, 60), fill=(212, 160, 23))
d.text((tx, 180), "世界杯战报", font=fit_font(d, "世界杯战报", BOLD, maxw, 104), fill=(240, 245, 250))
tag = "实时比分 · 积分榜 · 射手榜 · 官方集锦"
d.text((tx, 322), tag, font=fit_font(d, tag, REG, maxw, 34), fill=(150, 205, 170))

# 右下角小字(审核保险,不抢眼)
small = font(REG, 22)
txt = "Unofficial · 非官方"
bbox = d.textbbox((0, 0), txt, font=small)
d.text((W - (bbox[2] - bbox[0]) - 24, H - 40), txt, font=small, fill=(120, 140, 130))

out = os.path.join(HERE, "feature-graphic.png")
img.save(out)
print("生成:", out, img.size)
