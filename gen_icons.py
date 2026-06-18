# -*- coding: utf-8 -*-
"""生成 PWA 图标:绿色渐变背景 + 白色足球(黑色五边形)。
输出 icon-512.png / icon-192.png / apple-touch-icon.png(180)。
改图标只需改这里再 python gen_icons.py。"""
import os
import math
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
S = 512


def pentagon(cx, cy, r, rot=0.0):
    pts = []
    for k in range(5):
        a = math.radians(rot + k * 72 - 90)  # -90:一个顶点朝上
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


img = Image.new("RGB", (S, S), (15, 20, 25))
d = ImageDraw.Draw(img)

# 背景竖向渐变:深绿 -> 深蓝灰
top, bot = (20, 110, 60), (12, 22, 30)
for y in range(S):
    t = y / S
    d.line([(0, y), (S, y)], fill=tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)))

cx = cy = S / 2
BR = S * 0.34
# 球体阴影 + 白球
d.ellipse([cx - BR - 6, cy - BR - 6, cx + BR + 6, cy + BR + 6], fill=(0, 0, 0))
d.ellipse([cx - BR, cy - BR, cx + BR, cy + BR], fill=(247, 247, 247))
# 中心黑五边形
d.polygon(pentagon(cx, cy, BR * 0.34), fill=(22, 22, 24))
# 外围 5 个黑五边形
for k in range(5):
    a = math.radians(k * 72 - 90)
    px, py = cx + BR * 0.66 * math.cos(a), cy + BR * 0.66 * math.sin(a)
    d.polygon(pentagon(px, py, BR * 0.2, rot=k * 72 + 36), fill=(22, 22, 24))

img.save(os.path.join(HERE, "icon-512.png"))
img.resize((192, 192), Image.LANCZOS).save(os.path.join(HERE, "icon-192.png"))
img.resize((180, 180), Image.LANCZOS).save(os.path.join(HERE, "apple-touch-icon.png"))
print("icons generated: 512/192/180")
