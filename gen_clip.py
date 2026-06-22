# -*- coding: utf-8 -*-
"""
赛后数据可视化短视频生成器
读 data.json 里某场比赛的进球时间轴 + 比分,渲染成竖屏 MP4。
全程用自绘数据图,不含任何赛事转播画面 —— 规避版权,可投 B 站。

用法:
  python gen_clip.py                # 默认自动选进球最多的一场
  python gen_clip.py Germany        # 按球队名(子串)选
  python gen_clip.py --index 0 0    # 按 分组序号 比赛序号 选
"""
import sys, json, math, os, wave, struct, subprocess, tempfile
from PIL import Image, ImageDraw, ImageFont
import imageio.v2 as imageio
import numpy as np

# ---------- 基本参数 ----------
W, H = 1080, 1920
FPS = 30
OUT = "clip.mp4"

# 配色(深场地绿底 + 双队强调色)
BG_TOP    = (8, 26, 20)
BG_BOT    = (4, 14, 12)
GOLD      = (245, 197, 66)    # 主队
BLUE      = (74, 163, 255)    # 客队
WHITE     = (240, 244, 242)
GREY      = (150, 162, 158)
LINE      = (40, 60, 52)

FONT_DIR = r"C:\Windows\Fonts"
def font(name, size):
    return ImageFont.truetype(f"{FONT_DIR}\\{name}", size)

# 拉丁(含重音)用 Arial Unicode,中文粗体用等线
F_HUGE   = font("ARIALUNI.TTF", 200)   # 比分
F_TEAM   = font("ARIALUNI.TTF", 66)    # 队名
F_MIN    = font("arialbd.ttf",  40)    # 分钟徽标
F_SCORER = font("ARIALUNI.TTF", 40)    # 射手名
F_TAG_CN = font("Dengb.ttf",    30)    # 中文小标签
F_LBL    = font("Dengb.ttf",    34)    # 顶部标题
F_SUB    = font("ARIALUNI.TTF", 30)    # 副信息
F_FOOT   = font("Dengb.ttf",    26)    # 页脚

# ---------- 选比赛 ----------
def pick_match(argv):
    d = json.load(open("data.json", encoding="utf-8"))
    flat = [(g["name"], m) for g in d["groups"] for m in g["matches"]
            if m.get("status") == "FT" and m.get("goals")]
    if len(argv) >= 3 and argv[0] == "--index":
        gi, mi = int(argv[1]), int(argv[2])
        g = d["groups"][gi]
        return g["name"], g["matches"][mi], d["meta"]
    if argv:
        key = argv[0].lower()
        for gn, m in flat:
            if key in m["home"].lower() or key in m["away"].lower():
                return gn, m, d["meta"]
    # 默认:进球最多 + 双方都进球优先
    best = max(flat, key=lambda x: len(x[1]["goals"])
               + (2 if len({g["team"] for g in x[1]["goals"]}) > 1 else 0))
    return best[0], best[1], d["meta"]

# ---------- 进球类型 → 中文标签 ----------
def goal_tag(t):
    t = (t or "").lower()
    if "header" in t:  return "头球"
    if "penalty" in t: return "点球"
    if "volley" in t:  return "凌空"
    if "free" in t:    return "任意球"
    if "own" in t:     return "乌龙"
    return "进球"

# ---------- 缓动 ----------
def ease(t):  # easeOutCubic, t∈[0,1]
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3

def clamp01(x): return max(0.0, min(1.0, x))

# ---------- 绘图工具 ----------
def vgrad(draw):
    for y in range(H):
        f = y / H
        r = int(BG_TOP[0] + (BG_BOT[0]-BG_TOP[0])*f)
        g = int(BG_TOP[1] + (BG_BOT[1]-BG_TOP[1])*f)
        b = int(BG_TOP[2] + (BG_BOT[2]-BG_TOP[2])*f)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

def text_c(draw, xy, s, fnt, fill, anchor="mm"):
    draw.text(xy, s, font=fnt, fill=fill, anchor=anchor)

def rounded(draw, box, r, fill):
    draw.rounded_rectangle(box, radius=r, fill=fill)

# ---------- 单帧渲染 ----------
def render(frame, total, gname, m, meta):
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    vgrad(d)

    goals = m["goals"]
    hs, as_ = m["hs"], m["as"]
    home, away = m["home"], m["away"]

    # —— 时间线规划(帧)——
    f_head  = 24            # 标题淡入
    f_team  = 30            # 队名滑入
    f_score = 28            # 比分跳动
    g_each  = 13            # 每个进球出现间隔
    start_goals = f_head + f_team + f_score
    # 全局透明度起点
    head_a  = ease(frame / f_head)

    # —— 顶部标题 ——
    a = int(220 * head_a)
    text_c(d, (W//2, 95),  meta.get("tournament", "World Cup 2026") + " · 赛后数据",
           F_LBL, (GOLD[0], GOLD[1], GOLD[2]))
    text_c(d, (W//2, 145), f"Group {gname} · {m.get('date','')}", F_SUB, GREY)
    d.line([(120, 185), (W-120, 185)], fill=LINE, width=2)

    # —— 队名滑入 ——
    tp = ease((frame - f_head) / f_team)
    dx = int((1 - tp) * 260)
    text_c(d, (W//2 - 300 + dx, 360), home, F_TEAM, WHITE)
    text_c(d, (W//2 + 300 - dx, 360), away, F_TEAM, WHITE)
    # 队色条
    rounded(d, (W//2-470, 405, W//2-130, 417), 6, GOLD)
    rounded(d, (W//2+130, 405, W//2+470, 417), 6, BLUE)

    # —— 比分跳动 ——
    sp = ease((frame - f_head - f_team) / f_score)
    ch = int(round(hs * sp)); ca = int(round(as_ * sp))
    text_c(d, (W//2 - 200, 560), str(ch), F_HUGE, GOLD)
    text_c(d, (W//2 + 200, 560), str(ca), F_HUGE, BLUE)
    # 手绘冒号(避免大号字形渲染成方块)
    for cy in (525, 595):
        d.ellipse([W//2-13, cy-13, W//2+13, cy+13], fill=GREY)

    # —— 进球时间轴 ——
    top = 760
    row_h = (H - top - 130) / max(len(goals), 1)
    row_h = min(row_h, 130)
    d.line([(W//2, top), (W//2, top + row_h*len(goals))], fill=LINE, width=3)
    for i, gl in enumerate(goals):
        appear = start_goals + i * g_each
        ap = ease((frame - appear) / 16)
        if ap <= 0:
            continue
        y = top + row_h * i + row_h/2
        is_home = gl.get("team") == home
        col = GOLD if is_home else BLUE
        side = -1 if is_home else 1
        slide = int((1 - ap) * 80) * side
        bx = W//2 + side * 90 + slide

        # 时间轴节点
        d.ellipse([W//2-12, y-12, W//2+12, y+12], fill=col)

        # 卡片(内容统一单列左对齐,避免双锚点对撞)
        card_w, card_h = 420, 96
        if is_home:
            box = (bx - card_w, y - card_h/2, bx, y + card_h/2)
        else:
            box = (bx, y - card_h/2, bx + card_w, y + card_h/2)
        pad_x = box[0] + 20
        # 半透明卡底
        ov = Image.new("RGBA", (W, H), (0,0,0,0))
        od = ImageDraw.Draw(ov)
        od.rounded_rectangle(box, radius=16,
                             fill=(col[0], col[1], col[2], int(38*ap)),
                             outline=(col[0], col[1], col[2], int(160*ap)), width=2)
        img.paste(Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB"), (0,0))
        d = ImageDraw.Draw(img)

        # 第一行:分钟(队色) + 射手(白)
        mn = gl["min"]
        d.text((pad_x, y - 16), mn, font=F_MIN, fill=col, anchor="lm")
        mw = d.textlength(mn, font=F_MIN)
        d.text((pad_x + mw + 14, y - 16), gl.get("scorer", ""),
               font=F_SCORER, fill=WHITE, anchor="lm")
        # 第二行:类型标签 + 助攻
        sub = goal_tag(gl.get("type"))
        ast = gl.get("assist")
        if ast:
            sub += "  ·  助攻 " + ast
        d.text((pad_x, y + 24), sub, font=F_TAG_CN, fill=GREY, anchor="lm")

    # —— 页脚水印 ——
    text_c(d, (W//2, H-70), "数据源 ESPN · 本视频为数据可视化,不含赛事画面",
           F_FOOT, GREY)
    return img

# ---------- 配乐:合成无版权占位 BGM ----------
def synth_bgm(path, dur):
    """numpy 合成 I-V-vi-IV 大调进行 + 软底鼓,写 16bit WAV。无版权。"""
    sr = 44100
    beat = 0.5                       # 120 BPM
    chord_len = beat * 4             # 每和弦 2s
    # C 大调 I-V-vi-IV,每个和弦 (根, 三, 五) Hz
    prog = [
        (261.63, 329.63, 392.00),   # C
        (196.00, 246.94, 293.66),   # G
        (220.00, 261.63, 329.63),   # Am
        (174.61, 220.00, 261.63),   # F
    ]
    n = int(sr * dur)
    t = np.arange(n) / sr
    out = np.zeros(n)

    # 和弦 pad(轻微失谐 + 八度叠加)
    for i in range(int(math.ceil(dur / chord_len))):
        notes = prog[i % len(prog)]
        s0 = int(i * chord_len * sr)
        s1 = min(int((i + 1) * chord_len * sr), n)
        if s0 >= n:
            break
        seg = t[s0:s1] - t[s0]
        # 该和弦内的柔和包络
        env = np.minimum(seg / 0.08, 1.0) * np.exp(-seg * 0.25)
        wav = np.zeros(s1 - s0)
        for f in notes:
            wav += np.sin(2*np.pi*f*seg)
            wav += 0.5*np.sin(2*np.pi*f*1.003*seg)   # 失谐加厚
            wav += 0.25*np.sin(2*np.pi*f*2*seg)       # 高八度
        out[s0:s1] += 0.10 * env * wav

    # 软底鼓:每拍一下 55Hz 快衰减
    for k in range(int(dur / beat)):
        s0 = int(k * beat * sr)
        s1 = min(s0 + int(0.18 * sr), n)
        if s0 >= n:
            break
        seg = (np.arange(s1 - s0)) / sr
        kick = np.sin(2*np.pi*55*seg) * np.exp(-seg * 22)
        out[s0:s1] += 0.35 * kick

    # 主控:归一化 + 整体淡入淡出
    out /= max(np.max(np.abs(out)), 1e-6)
    out *= 0.85
    fi = int(0.6 * sr)
    out[:fi] *= np.linspace(0, 1, fi)
    fo = int(1.4 * sr)
    out[-fo:] *= np.linspace(1, 0, fo)

    pcm = (out * 32767).astype(np.int16)
    with wave.open(path, "w") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(pcm.tobytes())

def mux_audio(video, audio, out, dur):
    """用自带 ffmpeg 把音频合进视频,结尾淡出,以视频长度为准。"""
    import imageio_ffmpeg
    exe = imageio_ffmpeg.get_ffmpeg_exe()
    fade_st = max(dur - 1.2, 0.1)
    subprocess.run([
        exe, "-y", "-i", video, "-i", audio,
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-af", f"afade=t=out:st={fade_st:.2f}:d=1.2",
        "-shortest", out
    ], check=True, capture_output=True)

# ---------- 主流程 ----------
def main():
    argv = sys.argv[1:]
    # 取出 --bgm FILE / --no-bgm 选项,剩下的交给 pick_match
    bgm_file, use_bgm = None, True
    if "--no-bgm" in argv:
        use_bgm = False; argv.remove("--no-bgm")
    if "--bgm" in argv:
        i = argv.index("--bgm"); bgm_file = argv[i+1]; del argv[i:i+2]

    gname, m, meta = pick_match(argv)
    ng = len(m["goals"])
    total = 24 + 30 + 28 + ng * 13 + 16 + 45   # 末尾留停顿
    dur = total / FPS
    print(f"渲染: Group {gname}  {m['home']} {m['hs']}-{m['as']} {m['away']}  "
          f"({ng}球, {total}帧 ≈ {dur:.1f}s)")

    silent = "_silent.mp4" if use_bgm else OUT
    writer = imageio.get_writer(silent, fps=FPS, codec="libx264",
                                quality=8, macro_block_size=8)
    for f in range(total):
        writer.append_data(np.asarray(render(f, total, gname, m, meta)))
        if f % 30 == 0:
            print(f"  {f}/{total}")
    writer.close()

    if not use_bgm:
        print(f"完成(无声) -> {OUT}"); return

    # 配乐:优先用户提供,否则合成占位
    if bgm_file and os.path.exists(bgm_file):
        audio = bgm_file
        print(f"配乐: {bgm_file}")
    else:
        audio = "_bgm.wav"
        synth_bgm(audio, dur + 0.3)
        print("配乐: 合成占位 BGM(无版权)。用 --bgm xxx.mp3 换成你自己的")
    mux_audio(silent, audio, OUT, dur)
    os.remove(silent)
    if audio == "_bgm.wav":
        os.remove(audio)               # 清理合成的临时音轨
    print(f"完成 -> {OUT}")

if __name__ == "__main__":
    main()
