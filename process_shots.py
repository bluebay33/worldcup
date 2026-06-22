# -*- coding: utf-8 -*-
"""把 shots/ 里的截图批量处理成 Google Play 合规的手机截图,输出到 shots/play_ready/。
规则:每边 320~3840px;长边 <= 2x 短边(超了补深色边、不裁内容);去 alpha 透明通道;
单张 <8MB(超了转 JPEG)。用法:python process_shots.py [图片文件夹]"""
import os
import sys
import glob
import math
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "shots")
OUT = os.path.join(SRC, "play_ready")
BG = (15, 20, 25)        # #0f1419 应用深色底,补边几乎看不出
MAXR = 2.0               # Play 硬上限:长边 <= 2x 短边
PAD_TO = 1.95            # 超限时补到这个比例(留点安全余量,不卡 2.0 边界)
MIN_SIDE, MAX_SIDE = 320, 3840
MAX_BYTES = 8 * 1024 * 1024

os.makedirs(OUT, exist_ok=True)
files = sorted(f for f in glob.glob(os.path.join(SRC, "*"))
               if f.lower().endswith((".png", ".jpg", ".jpeg")) and os.path.dirname(f) != OUT)
if not files:
    print("没找到图片。请把截图(.png/.jpg)放到:", SRC)
    sys.exit()

i = 0
for f in files:
    im = Image.open(f)
    w, h = im.size
    # 去 alpha:贴到深色背景上
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        base = Image.new("RGB", (w, h), BG)
        base.paste(im, mask=im.split()[-1])
        im = base
    else:
        im = im.convert("RGB")
    note = []
    lo, sh = max(w, h), min(w, h)
    # 比例超 PAD_TO(1.95)-> 补短边的深色边(不裁内容),统一留出到 2.0 上限的安全余量
    if lo > PAD_TO * sh:
        if h >= w:                       # 竖图,补宽到 h/PAD_TO
            nw = max(w, math.ceil(h / PAD_TO))
            canvas = Image.new("RGB", (nw, h), BG)
            canvas.paste(im, ((nw - w) // 2, 0))
        else:                            # 横图,补高
            nh = max(h, math.ceil(w / PAD_TO))
            canvas = Image.new("RGB", (w, nh), BG)
            canvas.paste(im, (0, (nh - h) // 2))
        im = canvas
        note.append("补边到<=2:1")
    # 任一边超 3840 -> 等比缩小
    if max(im.size) > MAX_SIDE:
        sc = MAX_SIDE / max(im.size)
        im = im.resize((int(im.size[0] * sc), int(im.size[1] * sc)), Image.LANCZOS)
        note.append("缩到<=3840")
    if min(im.size) < MIN_SIDE:
        note.append("⚠短边<320,Play会拒(原图太小)")
    i += 1
    outp = os.path.join(OUT, f"shot-{i:02d}.png")
    im.save(outp)
    sz = os.path.getsize(outp)
    if sz > MAX_BYTES:                    # 超 8MB 转 JPEG
        os.remove(outp)
        outp = os.path.join(OUT, f"shot-{i:02d}.jpg")
        im.save(outp, "JPEG", quality=90)
        sz = os.path.getsize(outp)
        note.append("转JPEG压到<8MB")
    ratio = max(im.size) / min(im.size)
    print(f"{os.path.basename(f)}  {w}x{h} -> {im.size[0]}x{im.size[1]}  "
          f"比例{ratio:.2f}  {sz // 1024}KB  {'; '.join(note) or '原样合规'}  => {os.path.basename(outp)}")

print("\n完成。合规截图在:", OUT)
print("可直接上传 Play。建议中文界面 >=2 张、英文界面 >=2 张分别命名好。")
