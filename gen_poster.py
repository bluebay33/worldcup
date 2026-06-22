# -*- coding: utf-8 -*-
"""生成微信分享海报 poster.png(竖版 1080x1440)。

为什么要这张图:微信对站外链接(尤其 *.pages.dev 这种免费共享域名)
的卡片抓取不稳定 —— 国内爬虫到 Cloudflare 链路时好时坏,抓不到 og 就没卡片。
海报图绕开爬虫:用户分享时发「海报图 + 粘贴链接文字」,图在微信永远显示。

精简版:标题 + 足球图标 + 站点主题 + 网址 + 指向门户的二维码 + 更新时间。
动态亮点(积分榜/射手榜)待确认效果后再加。

用法:python gen_poster.py   (改完重跑即可)
依赖:Pillow、qrcode[pil]
"""
import os
import math
import json
import qrcode
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data.json")
OUT = os.path.join(HERE, "poster.png")

W, H = 1080, 1440
PORTAL = "https://sports-aeg.pages.dev/worldcup/"
URL_TEXT = "sports-aeg.pages.dev/worldcup"

# 字体:本地用微软雅黑。注意——GitHub Actions(Ubuntu)没有此字体,
# 云端自动生成前需把开源中文字体(Noto Sans SC 等)入库并改这里的路径。
FONT_BD = "C:/Windows/Fonts/msyhbd.ttc"
FONT_RG = "C:/Windows/Fonts/msyh.ttc"


def font(path, size):
    return ImageFont.truetype(path, size)


def pentagon(cx, cy, r, rot=0.0):
    pts = []
    for k in range(5):
        a = math.radians(rot + k * 72 - 90)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def draw_ball(d, cx, cy, br):
    """复用 gen_icons.py 的白球+黑五边形画法。"""
    d.ellipse([cx - br - 5, cy - br - 5, cx + br + 5, cy + br + 5], fill=(0, 0, 0))
    d.ellipse([cx - br, cy - br, cx + br, cy + br], fill=(247, 247, 247))
    d.polygon(pentagon(cx, cy, br * 0.34), fill=(22, 22, 24))
    for k in range(5):
        a = math.radians(k * 72 - 90)
        px, py = cx + br * 0.66 * math.cos(a), cy + br * 0.66 * math.sin(a)
        d.polygon(pentagon(px, py, br * 0.2, rot=k * 72 + 36), fill=(22, 22, 24))


def center_text(d, cy, text, fnt, fill):
    bb = d.textbbox((0, 0), text, font=fnt)
    w = bb[2] - bb[0]
    d.text(((W - w) / 2, cy), text, font=fnt, fill=fill)
    return bb[3] - bb[1]


def make_qr(url, px):
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M,
                       box_size=10, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0f1419", back_color="white").convert("RGB")
    return img.resize((px, px), Image.NEAREST)


def main():
    try:
        meta = json.load(open(DATA, encoding="utf-8")).get("meta", {})
    except Exception:
        meta = {}
    tournament = meta.get("tournament", "2026世界杯")
    host = meta.get("host", "")
    updated = meta.get("lastUpdated", "")

    img = Image.new("RGB", (W, H), (15, 20, 25))
    d = ImageDraw.Draw(img)

    # 背景竖向渐变:深绿 -> 深蓝灰(同站点主题)
    top, bot = (20, 110, 60), (12, 22, 30)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)))

    # 足球图标
    draw_ball(d, W / 2, 300, 150)

    # 主标题
    center_text(d, 510, f"{tournament}战报", font(FONT_BD, 104), (255, 255, 255))
    # 副标题
    center_text(d, 660, "积分榜 · 射手榜 · 每场官方集锦 · 赛程", font(FONT_RG, 42), (159, 176, 189))
    if host:
        center_text(d, 730, f"主办:{host}", font(FONT_RG, 36), (120, 138, 150))

    # 分隔线
    d.line([(140, 850), (W - 140, 850)], fill=(60, 80, 90), width=2)

    # 底部:二维码(右) + 网址/提示(左)
    qpx = 300
    qx, qy = W - 140 - qpx, 950
    qr = make_qr(PORTAL, qpx)
    # 二维码白底加一圈留白框
    d.rectangle([qx - 16, qy - 16, qx + qpx + 16, qy + qpx + 16], fill=(255, 255, 255))
    img.paste(qr, (qx, qy))

    d.text((140, 985), "扫码看实时战报", font=font(FONT_BD, 52), fill=(255, 255, 255))
    d.text((140, 1075), "或访问", font=font(FONT_RG, 34), fill=(159, 176, 189))
    d.text((140, 1130), URL_TEXT, font=font(FONT_RG, 30), fill=(80, 200, 130))

    if updated:
        center_text(d, 1360, f"更新:{updated}", font(FONT_RG, 32), (110, 128, 140))

    img.save(OUT)
    print("poster generated:", OUT)


if __name__ == "__main__":
    main()
