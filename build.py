# -*- coding: utf-8 -*-
"""
世界杯战报生成器。
读 data.json，生成自包含的 report.html（CSS 内联，双击即可离线查看）。

设计要点：
- 比赛结果（matches）是唯一事实源，积分榜由代码自动推算，
  这样更新者（AI 或人）只要改/加比分，绝不会出现"积分和比分对不上"的 bug。
- 不依赖任何第三方库，python build.py 即可。

用法：python build.py
"""
import json
import os
import re
import html
from datetime import datetime, timezone, timedelta
from urllib.parse import quote_plus

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data.json")
OUT = os.path.join(HERE, "report.html")

# 央视集锦直链映射(key = 中文队名 sorted 后 "|" 拼;由 WebSearch / Google Custom Search 维护)。
# 命中则 CN 用户直达 sports.cctv.com 集锦页;缺失(没抓到/刚踢完没发集锦)则回退百度搜索。
try:
    with open(os.path.join(HERE, "cctv_links.json"), encoding="utf-8") as _f:
        CCTV_LINKS = json.load(_f)
except Exception:
    CCTV_LINKS = {}


def esc(s):
    return html.escape(str(s))


def bi(zh, en):
    """双语文本:输出一个 span,默认显示中文;页面 JS 按浏览器语言切到英文。
    zh/en 都存进 data-* 属性,支持来回切换。"""
    return (f'<span class="i18n" data-zh="{esc(zh)}" data-en="{esc(en)}">{esc(zh)}</span>')


def team_bi(name):
    """队名双语:中文用 TEAM_CN/占位规则,英文用 ESPN 原名(本就是英文)。"""
    return bi(cn(name), name)


def grp_label(g):
    """match 行左上角的分组小标签:字母组直接显示,'淘汰赛' 做双语。"""
    return bi("淘汰赛", "KO") if g == "淘汰赛" else esc(g)


# 淘汰赛轮次 slug(来自 ESPN season.slug)-> 双语标签。比泛标签"淘汰赛"更明确。
_KO_ROUND_BI = {
    "round-of-32": ("32强赛", "Round of 32"),
    "round-of-16": ("16强赛", "Round of 16"),
    "quarterfinals": ("1/4决赛", "Quarterfinal"),
    "semifinals": ("半决赛", "Semifinal"),
    "3rd-place-match": ("季军赛", "Third Place"),
    "final": ("决赛", "Final"),
}


def round_tag(m):
    """淘汰赛场的轮次标签(双语);非淘汰赛或无 round 字段返回空串。"""
    r = m.get("round")
    if r in _KO_ROUND_BI:
        zh, en = _KO_ROUND_BI[r]
        return bi(zh, en)
    return ""


def collap(title, body, *, open_=True, cls=""):
    """把一个板块包成可折叠的 <details>。title 已是 HTML，body 已是 HTML。"""
    op = " open" if open_ else ""
    return (f'<details class="sec {cls}"{op}><summary class="sec-h">{title}</summary>'
            f'<div class="sec-body">{body}</div></details>')


# ESPN 英文队名 -> 中文（含常见写法变体，缺失则回退英文）
TEAM_CN = {
    "South Africa": "南非", "Mexico": "墨西哥", "South Korea": "韩国", "Korea Republic": "韩国",
    "Czechia": "捷克", "Czech Republic": "捷克",
    "Switzerland": "瑞士", "Canada": "加拿大", "Qatar": "卡塔尔",
    "Bosnia and Herzegovina": "波黑", "Bosnia & Herzegovina": "波黑", "Bosnia-Herzegovina": "波黑",
    "Croatia": "克罗地亚", "Brazil": "巴西", "Morocco": "摩洛哥", "Scotland": "苏格兰", "Haiti": "海地",
    "United States": "美国", "USA": "美国", "Australia": "澳大利亚",
    "Türkiye": "土耳其", "Turkey": "土耳其", "Paraguay": "巴拉圭",
    "Germany": "德国", "Ecuador": "厄瓜多尔", "Curaçao": "库拉索",
    "Côte d'Ivoire": "科特迪瓦", "Ivory Coast": "科特迪瓦",
    "Netherlands": "荷兰", "Japan": "日本", "Tunisia": "突尼斯", "Sweden": "瑞典",
    "Belgium": "比利时", "New Zealand": "新西兰", "Egypt": "埃及", "Iran": "伊朗", "IR Iran": "伊朗",
    "Spain": "西班牙", "Uruguay": "乌拉圭", "Saudi Arabia": "沙特阿拉伯", "Cape Verde": "佛得角",
    "France": "法国", "Norway": "挪威", "Senegal": "塞内加尔", "Iraq": "伊拉克",
    "Argentina": "阿根廷", "Austria": "奥地利", "Algeria": "阿尔及利亚", "Jordan": "约旦",
    "Colombia": "哥伦比亚", "Uzbekistan": "乌兹别克斯坦", "DR Congo": "刚果(金)", "Congo DR": "刚果(金)", "Portugal": "葡萄牙",
    "England": "英格兰", "Panama": "巴拿马", "Ghana": "加纳",
}


_ROUND_CN = {"Round of 32": "32强", "Round of 16": "16强",
             "Quarterfinal": "1/4决赛", "Semifinal": "半决赛"}


def cn(name):
    """队名转中文；淘汰赛占位名(如 'Group A Winner')按模式翻译；都没命中则原样返回。"""
    if name in TEAM_CN:
        return TEAM_CN[name]
    m = re.fullmatch(r"Group ([A-L]) Winner", name)
    if m:
        return f"{m.group(1)}组第1"
    m = re.fullmatch(r"Group ([A-L]) 2nd Place", name)
    if m:
        return f"{m.group(1)}组第2"
    m = re.fullmatch(r"Third Place Group ([A-L/]+)", name)
    if m:
        return f"小组第3({m.group(1)})"
    m = re.fullmatch(r"(Round of 32|Round of 16|Quarterfinal|Semifinal) (\d+) (Winner|Loser)", name)
    if m:
        wl = "胜者" if m.group(3) == "Winner" else "负者"
        return f"{_ROUND_CN[m.group(1)]}第{m.group(2)}场{wl}"
    return name


# 队名 -> ISO 3166-1 alpha-2(用于生成 emoji 国旗;英/苏/威用特殊 emoji)
TEAM_ISO = {
    "South Africa": "ZA", "Mexico": "MX", "South Korea": "KR", "Korea Republic": "KR",
    "Czechia": "CZ", "Czech Republic": "CZ", "Switzerland": "CH", "Canada": "CA", "Qatar": "QA",
    "Bosnia and Herzegovina": "BA", "Bosnia & Herzegovina": "BA", "Bosnia-Herzegovina": "BA",
    "Croatia": "HR", "Brazil": "BR", "Morocco": "MA", "Haiti": "HT",
    "United States": "US", "USA": "US", "Australia": "AU", "Türkiye": "TR", "Turkey": "TR",
    "Paraguay": "PY", "Germany": "DE", "Ecuador": "EC", "Curaçao": "CW",
    "Côte d'Ivoire": "CI", "Ivory Coast": "CI", "Netherlands": "NL", "Japan": "JP", "Tunisia": "TN",
    "Sweden": "SE", "Belgium": "BE", "New Zealand": "NZ", "Egypt": "EG", "Iran": "IR", "IR Iran": "IR",
    "Spain": "ES", "Uruguay": "UY", "Saudi Arabia": "SA", "Cape Verde": "CV", "France": "FR",
    "Norway": "NO", "Senegal": "SN", "Iraq": "IQ", "Argentina": "AR", "Austria": "AT", "Algeria": "DZ",
    "Jordan": "JO", "Colombia": "CO", "Uzbekistan": "UZ", "DR Congo": "CD", "Congo DR": "CD",
    "Portugal": "PT", "Panama": "PA", "Ghana": "GH",
}

# 英格兰/苏格兰/威尔士不是 ISO 国家,用 emoji tag 序列(手机端能渲染,Windows 桌面可能退化)
_SPECIAL_FLAG = {
    "England": "\U0001F3F4\U000E0067\U000E0062\U000E0065\U000E006E\U000E0067\U000E007F",
    "Scotland": "\U0001F3F4\U000E0067\U000E0062\U000E0073\U000E0063\U000E0074\U000E007F",
    "Wales": "\U0001F3F4\U000E0067\U000E0062\U000E0077\U000E006C\U000E0073\U000E007F",
}


def flag(name):
    """队名 -> emoji 国旗;占位名/未知队返回空串。"""
    if name in _SPECIAL_FLAG:
        return _SPECIAL_FLAG[name]
    code = TEAM_ISO.get(name)
    if not code:
        return ""
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in code)


def team_flag_bi(name, flag_first=True):
    """国旗(语言无关) + 双语队名。flag_first=False 时旗放队名后(用于右对齐的主队)。"""
    f = flag(name)
    fh = f'<span class="flag">{f}</span>' if f else ""
    return (fh + team_bi(name)) if flag_first else (team_bi(name) + fh)


# ESPN 城市字符串 -> 中文主办城市（16 个主办城市；缺失则回退英文原文，不编造）
CITY_CN = {
    "Arlington, Texas": "达拉斯", "Atlanta, Georgia": "亚特兰大",
    "East Rutherford, New Jersey": "纽约", "Foxborough, Massachusetts": "波士顿",
    "Guadalajara": "瓜达拉哈拉", "Guadalupe": "蒙特雷",
    "Houston, Texas": "休斯顿", "Inglewood, California": "洛杉矶",
    "Kansas City, Missouri": "堪萨斯城", "Mexico City": "墨西哥城",
    "Miami Gardens, Florida": "迈阿密", "Philadelphia, Pennsylvania": "费城",
    "Santa Clara, California": "旧金山湾区", "Seattle, Washington": "西雅图",
    "Toronto": "多伦多", "Vancouver": "温哥华",
}


def city_cn(city):
    return CITY_CN.get(city, city)


def compute_table(group):
    """从该组 matches 推算积分榜。胜3平1负0。"""
    rows = {t: {"team": t, "p": 0, "w": 0, "d": 0, "l": 0,
                "gf": 0, "ga": 0, "pts": 0} for t in group["teams"]}
    for m in group.get("matches", []):
        if m.get("status") != "FT" or m.get("hs") is None or m.get("as") is None:
            continue  # 只计完场;进行中(LIVE)的当前比分不计入,等完场再算
        h, a = m["home"], m["away"]
        hs, as_ = m["hs"], m["as"]
        for t in (h, a):
            if t not in rows:  # 容错：matches 里出现了 teams 没声明的队
                rows[t] = {"team": t, "p": 0, "w": 0, "d": 0, "l": 0,
                           "gf": 0, "ga": 0, "pts": 0}
        rows[h]["p"] += 1; rows[a]["p"] += 1
        rows[h]["gf"] += hs; rows[h]["ga"] += as_
        rows[a]["gf"] += as_; rows[a]["ga"] += hs
        if hs > as_:
            rows[h]["w"] += 1; rows[h]["pts"] += 3; rows[a]["l"] += 1
        elif hs < as_:
            rows[a]["w"] += 1; rows[a]["pts"] += 3; rows[h]["l"] += 1
        else:
            rows[h]["d"] += 1; rows[a]["d"] += 1
            rows[h]["pts"] += 1; rows[a]["pts"] += 1
    table = list(rows.values())
    # 排序：积分 > 净胜球 > 进球 > 队名
    table.sort(key=lambda r: (-r["pts"], -(r["gf"] - r["ga"]), -r["gf"], r["team"]))
    return table


def score_cell(m):
    if m.get("hs") is None or m.get("as") is None:
        return '<span class="vs">vs</span>'
    base = f'<span class="score">{m["hs"]} : {m["as"]}</span>'
    # 淘汰赛决胜方式:点球场补「点球 4:3」,加时绝杀补「加时」。hs/as 已是常规+加时的比分。
    dec = m.get("decided")
    if dec == "pens":
        p = m.get("pens") or {}
        ph, pa = p.get("h"), p.get("a")
        if ph is not None and pa is not None:
            base += f'<span class="sdecide">{bi("点球", "pens")} {ph}:{pa}</span>'
        else:
            base += f'<span class="sdecide">{bi("点球决胜", "on pens")}</span>'
    elif dec == "aet":
        base += f'<span class="sdecide">{bi("加时", "AET")}</span>'
    return base


def match_row(m, show_group=False):
    _rt = round_tag(m)
    if _rt:  # 淘汰赛场:用具体轮次标签(32强赛/决赛…)替代泛"淘汰赛"
        grp = f'<span class="tag ko">{_rt}</span> '
    elif show_group and m.get("group"):
        grp = f'<span class="tag">{grp_label(m["group"])}</span> '
    else:
        grp = ""
    status = m.get("status", "")
    badge = ""
    if status == "FT":
        badge = f'<span class="badge ft">{bi("完场", "FT")}</span>'
    elif status == "LIVE":
        badge = f'<span class="badge live">{bi("进行中", "LIVE")}</span>'
    elif status == "sched":
        badge = f'<span class="badge sched">{bi("未开赛", "Sched")}</span>'
    _city = m.get("city", "")
    _vname = m.get("venue", "")
    _czh = city_cn(_city)
    _loc_zh = f"{_czh} · {_vname}" if (_czh and _vname) else (_czh or _vname)
    _loc_en = f"{_city} · {_vname}" if (_city and _vname) else (_city or _vname)
    venue = f'<span class="venue">{bi(_loc_zh, _loc_en)}</span>' if _loc_zh else ""
    _fb = esc(m.get("date", "")) + (" " + esc(m["time"]) if m.get("time") else "")
    ts = m.get("ts")
    dt = f'<span class="ltime" data-ts="{ts}">{_fb}</span>' if ts else _fb
    return f"""<div class="match" data-h="{esc(m['home'])}" data-a="{esc(m['away'])}">
      <div class="m-date">{grp}{dt}</div>
      <div class="m-home">{team_flag_bi(m["home"], flag_first=False)}</div>
      <div class="m-score">{score_cell(m)}</div>
      <div class="m-away">{team_flag_bi(m["away"], flag_first=True)}</div>
      <div class="m-meta">{badge}{venue}</div>
      {goals_html(m)}{videos_html(m)}
    </div>"""


def match_list_row(m):
    """HISTORY 用的紧凑列表行：常显一行(时间/组 + 主 比分 客)，点击用 JS 展开进球/集锦/场地。
    不用原生 <details>/<summary>——部分 Windows Chrome/Edge 不渲染 summary 内容、回退成默认"详情"
    标签。改用普通 <div> + JS 切换，渲染稳定。"""
    _rt = round_tag(m)
    if _rt:
        grp = f'<span class="tag ko">{_rt}</span>'
    elif m.get("group"):
        grp = f'<span class="tag">{grp_label(m["group"])}</span>'
    else:
        grp = ""
    _fb = esc(m.get("date", "")) + (" " + esc(m["time"]) if m.get("time") else "")
    ts = m.get("ts")
    dt = f'<span class="ltime" data-ts="{ts}">{_fb}</span>' if ts else f'<span>{_fb}</span>'
    line = ('<div class="ml-line" role="button" tabindex="0">'
            f'<span class="ml-when">{dt}{grp}</span>'
            f'<span class="ml-h">{team_flag_bi(m["home"], flag_first=False)}</span>'
            f'<span class="ml-sc">{score_cell(m)}</span>'
            f'<span class="ml-a">{team_flag_bi(m["away"], flag_first=True)}</span>'
            '<span class="ml-tog" aria-hidden="true">▸</span>'
            '</div>')
    _city = m.get("city", "")
    _vname = m.get("venue", "")
    _czh = city_cn(_city)
    _loc_zh = f"{_czh} · {_vname}" if (_czh and _vname) else (_czh or _vname)
    _loc_en = f"{_city} · {_vname}" if (_city and _vname) else (_city or _vname)
    venue = f'<div class="ml-venue">📍 {bi(_loc_zh, _loc_en)}</div>' if _loc_zh else ""
    detail = f"{venue}{goals_html(m)}{videos_html(m)}"
    if not detail:
        detail = f'<div class="ml-venue">{bi("暂无更多详情", "No further detail")}</div>'
    # 排序用 data：时间(ts)、主/客队名(英文，稳定 A-Z)、胜方进球(两队较大比分；平局即该比分)
    _hs, _as = m.get("hs"), m.get("as")
    _wg = max(_hs, _as) if (_hs is not None and _as is not None) else -1
    # 注意：排序时间属性叫 data-sts，不能叫 data-ts —— 全局 renderTimes() 会对所有 [data-ts]
    # 元素执行 textContent=日期，把整行内容(队名/比分/展开块)抹成一个日期字符串。
    attrs = f' data-sts="{ts or 0}" data-h="{esc(m["home"])}" data-a="{esc(m["away"])}" data-wg="{_wg}"'
    return f'<div class="ml-row"{attrs}>{line}<div class="ml-body" hidden>{detail}</div></div>'


def _goal_mark(t):
    t = t or ""
    if "Penalty" in t:
        return bi("(点球)", "(P)")
    if "Own" in t:
        return bi("(乌龙)", "(OG)")
    if "Header" in t:
        return bi("(头球)", "(H)")
    return ""


def goals_html(m):
    goals = m.get("goals") or []
    if not goals:
        return ""
    parts = []
    for g in goals:
        nm = g.get("scorer") or "?"
        parts.append(f'<span class="gitem">{esc(g.get("min", ""))} {esc(nm)}{_goal_mark(g.get("type"))}'
                     f'<span class="gteam">{team_bi(g.get("team", ""))}</span></span>')
    return '<div class="m-goals">⚽ ' + "".join(parts) + "</div>"


def fifa_highlight_link(m):
    """已结束比赛 -> 集锦链接。集锦按地区分槽(ca=TSN只在加拿大可播、us=FOX只在美国可播):
    链接里同时带 ca/us 直链 + 搜索兜底,前端 JS 按读者所在国(/cdn-cgi/trace)选 href。
    默认 href 用搜索链接(无 JS / 其它地区都安全可用)。兼容旧的单 highlight 结构。"""
    if m.get("status") != "FT" or m.get("hs") is None or m.get("as") is None:
        return ""
    hls = m.get("highlights")
    if not isinstance(hls, dict):                      # 旧单结构 -> 按频道归到对应槽
        old = m.get("highlight") or {}
        hls = {}
        if old.get("url"):
            ch = _norm_ch(old.get("channel") or "")
            reg = "ca" if ch.startswith("tsn") else ("us" if ch.startswith(("fox", "cbs", "telemundo")) else None)
            if reg:
                hls[reg] = old
    ca = (hls.get("ca") or {}).get("url") if hls else None
    us = (hls.get("us") or {}).get("url") if hls else None
    q = f'{m["home"]} vs {m["away"]} full highlights FIFA world cup 2026'
    search = "https://www.youtube.com/results?search_query=" + quote_plus(q)
    # 中国读者(loc=CN):YouTube/TSN/FOX 都用不了。
    # 优先用央视集锦直链(cctv_links.json,中文队名 sorted 做 key)→ CN 直达 sports.cctv.com 集锦页;
    # 未命中(没抓到/刚踢完没发集锦)则回退百度搜央视标题模板「[世界杯]X组 队1 队2 集锦」
    # (央视集锦页标题格式固定,百度对央视大站索引好、标题强匹配,基本第一条)。
    cn_link = CCTV_LINKS.get("|".join(sorted([cn(m["home"]), cn(m["away"])])))
    if not cn_link:
        grp = m.get("group", "")
        grp_tag = f"{grp}组" if (grp and grp != "淘汰赛" and len(grp) <= 2) else ""
        cn_q = f'[世界杯]{grp_tag} {cn(m["home"])} {cn(m["away"])} 集锦'
        cn_link = "https://www.baidu.com/s?wd=" + quote_plus(cn_q)
    data = (f' data-hl-search="{esc(search)}"'
            + (f' data-hl-ca="{esc(ca)}"' if ca else "")
            + (f' data-hl-us="{esc(us)}"' if us else "")
            + f' data-hl-cn="{esc(cn_link)}"')
    label = "🎬 " + bi("集锦", "Highlights")
    return (f'<a class="vlink yt" href="{esc(search)}"{data} '
            f'target="_blank" rel="noopener">{label}</a>')


def _norm_ch(s):
    import unicodedata as _u
    s = _u.normalize("NFKD", s or "")
    return "".join(c for c in s if not _u.combining(c)).lower()


def videos_html(m):
    links = []
    yt = fifa_highlight_link(m)
    if yt:
        links.append(yt)
    for v in (m.get("videos") or []):
        _t = v.get("title")
        _label = esc(_t[:26]) if _t else bi("视频", "Video")
        links.append(f'<a class="vlink" href="{esc(v.get("url", ""))}" target="_blank" rel="noopener">'
                     f'▶ {_label}</a>')
    if not links:
        return ""
    return f'<div class="m-videos">{"".join(links)}</div>'


def group_block(group, elim=frozenset()):
    table = compute_table(group)
    name = group["name"]
    trs = []
    for i, r in enumerate(table):
        cls = "qualify" if i < 2 else ""  # 前两名晋级高亮
        if r["team"] in elim:              # 已出局:整行置灰(国旗+队名)
            cls = (cls + " out").strip()
        gd = r["gf"] - r["ga"]
        gd_s = f"+{gd}" if gd > 0 else str(gd)
        trs.append(f"""<tr class="{cls}" data-team="{esc(r['team'])}">
          <td class="rank">{i+1}</td>
          <td class="tname">{team_flag_bi(r['team'])}</td>
          <td>{r['p']}</td><td>{r['w']}</td><td>{r['d']}</td><td>{r['l']}</td>
          <td>{r['gf']}</td><td>{r['ga']}</td><td class="gd">{gd_s}</td>
          <td class="pts">{r['pts']}</td>
        </tr>""")
    played = [m for m in group.get("matches", [])
              if m.get("hs") is not None]
    sched = [m for m in group.get("matches", [])
             if m.get("hs") is None]
    matches_html = ""
    for m in played + sched:
        matches_html += match_row(m)
    n = len(played) + len(sched)
    if matches_html:
        _sm = bi(f"比赛详情 · {n} 场", f"Matches · {n}")
        body = (f'<details class="g-details"><summary>{_sm}</summary>'
                f'<div class="g-matches">{matches_html}</div></details>')
    else:
        body = f'<div class="empty">{bi("暂无比赛", "No matches")}</div>'
    return f"""<section class="group">
      <h3>{bi("小组 " + name, "Group " + name)}</h3>
      <table class="standings">
        <thead><tr>
          <th>#</th><th class="tname">{bi("球队", "Team")}</th><th>{bi("赛", "P")}</th><th>{bi("胜", "W")}</th><th>{bi("平", "D")}</th>
          <th>{bi("负", "L")}</th><th>{bi("进", "GF")}</th><th>{bi("失", "GA")}</th><th>{bi("净", "GD")}</th><th>{bi("分", "Pts")}</th>
        </tr></thead>
        <tbody>{''.join(trs)}</tbody>
      </table>
      {body}
    </section>"""


def ko_winner(m):
    """完赛淘汰赛场的 (胜者队名, 负者队名);未完赛或无法判定返回 (None, None)。
    点球场比分是平的,靠 pens 判;常规/加时靠 hs/as 判。"""
    if m.get("status") != "FT" or m.get("hs") is None or m.get("as") is None:
        return (None, None)
    h, a = m["home"], m["away"]
    if m.get("decided") == "pens":
        p = m.get("pens") or {}
        ph, pa = p.get("h"), p.get("a")
        if ph is None or pa is None:
            return (None, None)
        return (h, a) if ph > pa else (a, h)
    hs, as_ = m["hs"], m["as"]
    if hs > as_:
        return (h, a)
    if as_ > hs:
        return (a, h)
    return (None, None)


def eliminated_teams(data):
    """已出局的队集合:没进 32 强的小组队 + 淘汰赛输掉的队。用于国旗置灰。"""
    all_group = set()
    for g in data.get("groups", []):
        for t in g.get("teams", []):
            all_group.add(t)
    ko = data.get("knockout", [])
    r32_real = set()
    for m in ko:
        if m.get("round") == "round-of-32":
            for t in (m["home"], m["away"]):
                if t in all_group:          # 真实队(占位名不在小组名单里)
                    r32_real.add(t)
    elim = set(t for t in all_group if t not in r32_real)  # 没进淘汰赛=出局
    for m in ko:
        _, loser = ko_winner(m)
        if loser:
            elim.add(loser)                 # 淘汰赛输掉=出局
    return elim


# ---- 淘汰赛对阵图(SVG 对称树,皇家蓝+金,缩放适配一屏)----
_PH_RE = re.compile(r"(Round of 32|Round of 16|Quarterfinal|Semifinal) (\d+) (Winner|Loser)")
_PREV = {"round-of-16": "round-of-32", "quarterfinals": "round-of-16",
         "semifinals": "quarterfinals", "final": "semifinals"}
_DEPTH = {"final": 0, "semifinals": 1, "quarterfinals": 2, "round-of-16": 3, "round-of-32": 4}
# SVG 版面常量(框加大、字号提高,让缩放到一屏后更清楚)
_COLW, _BOXW, _BOXH, _PITCH, _TOP, _CX = 156, 136, 48, 58, 48, 636


def _feeder_idx(label, prev_slug, prev_list):
    """某场一方队名 -> 它在上一轮(prev_list,按日期排序)里的下标;占位名按编号、真实队按参赛反查。"""
    m = _PH_RE.fullmatch((label or "").strip())
    if m:
        rmap = {"Round of 32": "round-of-32", "Round of 16": "round-of-16",
                "Quarterfinal": "quarterfinals", "Semifinal": "semifinals"}
        if rmap.get(m.group(1)) == prev_slug and m.group(3) == "Winner":
            i = int(m.group(2)) - 1
            return i if 0 <= i < len(prev_list) else None
        return None
    for i, pm in enumerate(prev_list):
        if label in (pm.get("home"), pm.get("away")):
            return i
    return None


def _bk_node(slug, idx, R):
    m = R[slug][idx]
    n = {"m": m, "slug": slug, "ch": []}
    ps = _PREV.get(slug)
    if ps and R.get(ps):
        a = _feeder_idx(m.get("home"), ps, R[ps])
        b = _feeder_idx(m.get("away"), ps, R[ps])
        if a is not None and b is not None:
            n["ch"] = [_bk_node(ps, a, R), _bk_node(ps, b, R)]
    return n


def _bk_box_svg(n, is_final=False):
    m = n["m"]
    x, cy = n["x"], n["cy"]
    y = cy - _BOXH / 2
    played = m.get("status") == "FT" and m.get("hs") is not None
    live = m.get("status") == "LIVE"
    w, l = ko_winner(m)
    stroke = "#e7c14b" if is_final else "#2a4a86"
    fill = "#173463" if is_final else "#13294d"
    out = [f'<g class="bk-node{" live" if live else ""}" data-h="{esc(m["home"])}" data-a="{esc(m["away"])}">',
           f'<rect class="bk-box" x="{x:.0f}" y="{y:.0f}" width="{_BOXW}" height="{_BOXH}" rx="6" fill="{fill}" stroke="{stroke}"/>']

    def row(name, score, wl, ry):
        ph = _PH_RE.fullmatch((name or "").strip())
        nm_zh = "—" if ph else cn(name)
        nm_en = "—" if ph else (name or "—")
        fl = "" if ph else flag(name)
        op = ' opacity="0.4"' if (played and wl == "l") else ""
        nfill = "#ffffff" if (played and wl == "w") else "#c8d4ec"
        fw = ' font-weight="700"' if (played and wl == "w") else ""
        scfill = "#f4c430" if (played and wl == "w") else "#c8d4ec"
        seg = [f'<g class="bk-row"{op}>']
        if fl:
            seg.append(f'<text class="bk-fl" x="{x+9:.0f}" y="{ry+4:.0f}" font-size="17">{fl}</text>')
        seg.append(f'<text class="i18n bk-nm" data-zh="{esc(nm_zh)}" data-en="{esc(nm_en)}" '
                   f'x="{x+31:.0f}" y="{ry+4:.0f}" font-size="16" fill="{nfill}"{fw}>{esc(nm_zh)}</text>')
        sc = "" if score is None else str(score)
        seg.append(f'<text class="bk-sc" x="{x+_BOXW-9:.0f}" y="{ry+4:.0f}" font-size="16" '
                   f'font-weight="700" fill="{scfill}" text-anchor="end">{esc(sc)}</text>')
        seg.append("</g>")
        return "".join(seg)

    out.append(row(m.get("home"), m.get("hs"), "w" if m.get("home") == w else ("l" if m.get("home") == l else ""), y + 16))
    out.append(row(m.get("away"), m.get("as"), "w" if m.get("away") == w else ("l" if m.get("away") == l else ""), y + 36))
    dec = m.get("decided")
    nz = ne = ""
    if dec == "pens":
        p = m.get("pens") or {}
        if p.get("h") is not None and p.get("a") is not None:
            nz, ne = f'点球{p["h"]}:{p["a"]}', f'pens {p["h"]}:{p["a"]}'
    elif dec == "aet":
        nz, ne = "加时", "AET"
    out.append(f'<text class="i18n bk-note-t" data-zh="{nz}" data-en="{ne}" x="{x+_BOXW-9:.0f}" '
               f'y="{y+_BOXH+11:.0f}" font-size="11" fill="#e0b53c" text-anchor="end">{nz}</text>')
    out.append("</g>")
    return "".join(out)


def _bk_conn_svg(n):
    out = []
    for c in n["ch"]:
        if c["x"] < n["x"]:                       # 子在左、父在右
            cxr, px = c["x"] + _BOXW, n["x"]
            mid = (cxr + px) / 2
            out.append(f'<path d="M{cxr:.0f} {c["cy"]:.0f} H{mid:.0f} V{n["cy"]:.0f} H{px:.0f}"/>')
        else:                                     # 子在右、父在左
            cxl, px = c["x"], n["x"] + _BOXW
            mid = (cxl + px) / 2
            out.append(f'<path d="M{cxl:.0f} {c["cy"]:.0f} H{mid:.0f} V{n["cy"]:.0f} H{px:.0f}"/>')
        out.append(_bk_conn_svg(c))
    return "".join(out)


def bracket_svg(knockout):
    R = {}
    for s in ["round-of-32", "round-of-16", "quarterfinals", "semifinals", "final", "3rd-place-match"]:
        R[s] = sorted([m for m in knockout if m.get("round") == s], key=lambda x: (x.get("ts") or 0))
    if len(R["round-of-32"]) < 16 or not R["final"]:
        return f'<div class="empty">{bi("淘汰赛对阵未产生", "Bracket not set yet")}</div>'

    root = _bk_node("final", 0, R)
    if len(root["ch"]) != 2:                       # 结构没建全,兜底
        return f'<div class="empty">{bi("对阵图数据待补全", "Bracket data incomplete")}</div>'

    # 布局:左右子树各收集叶子(32强)按序赋 y,父节点 y=子节点中点;x 按深度+左右
    def collect(n, bucket):
        if n["ch"]:
            for c in n["ch"]:
                collect(c, bucket)
        else:
            bucket.append(n)
    lefts, rights = [], []
    collect(root["ch"][0], lefts)
    collect(root["ch"][1], rights)
    for i, n in enumerate(lefts):
        n["cy"] = _TOP + _BOXH / 2 + i * _PITCH
    for i, n in enumerate(rights):
        n["cy"] = _TOP + _BOXH / 2 + i * _PITCH

    def setcy(n):
        if n["ch"]:
            for c in n["ch"]:
                setcy(c)
            n["cy"] = sum(c["cy"] for c in n["ch"]) / len(n["ch"])
    setcy(root["ch"][0])
    setcy(root["ch"][1])
    root["cy"] = (root["ch"][0]["cy"] + root["ch"][1]["cy"]) / 2

    def setx(n, side):
        d = _DEPTH[n["slug"]]
        n["x"] = _CX - d * _COLW if side == "L" else (_CX + d * _COLW if side == "R" else _CX)
        for c in n["ch"]:
            setx(c, side)
    root["x"] = _CX
    setx(root["ch"][0], "L")
    setx(root["ch"][1], "R")

    n_leaves = max(len(lefts), len(rights), 8)
    W = _CX + 4 * _COLW + _BOXW + 12
    H = _TOP + n_leaves * _PITCH + 66            # 底部给季军赛留位

    # 连线(先画,压在盒子下面)
    conns = _bk_conn_svg(root["ch"][0]) + _bk_conn_svg(root["ch"][1])
    # 决赛连两个半决赛
    for c in root["ch"]:
        if c["x"] < root["x"]:
            conns += f'<path d="M{c["x"]+_BOXW:.0f} {c["cy"]:.0f} H{(c["x"]+_BOXW+root["x"])/2:.0f} V{root["cy"]:.0f} H{root["x"]:.0f}"/>'
        else:
            conns += f'<path d="M{c["x"]:.0f} {c["cy"]:.0f} H{(c["x"]+root["x"]+_BOXW)/2:.0f} V{root["cy"]:.0f} H{root["x"]+_BOXW:.0f}"/>'

    # 所有盒子
    def allnodes(n, acc):
        acc.append(n)
        for c in n["ch"]:
            allnodes(c, acc)
    nodes = []
    allnodes(root, nodes)
    boxes = "".join(_bk_box_svg(n, is_final=(n is root)) for n in nodes)

    # 轮次标签(顶部)
    labels = [("round-of-32", "32强赛", "Round of 32", 4), ("round-of-16", "16强赛", "Round of 16", 3),
              ("quarterfinals", "1/4决赛", "QF", 2), ("semifinals", "半决赛", "SF", 1)]
    lbls = []
    for slug, zh, en, d in labels:
        for cxp in (_CX - d * _COLW + _BOXW / 2, _CX + d * _COLW + _BOXW / 2):
            lbls.append(f'<text class="i18n bk-lbl" data-zh="{zh}" data-en="{en}" x="{cxp:.0f}" y="30" '
                        f'text-anchor="middle">{zh}</text>')
    lbls.append(f'<text class="i18n bk-lbl" data-zh="决赛" data-en="Final" x="{_CX+_BOXW/2:.0f}" y="30" text-anchor="middle">决赛</text>')
    # 奖杯 + 决赛上方
    trophy = f'<text x="{_CX+_BOXW/2:.0f}" y="{root["cy"]-_BOXH/2-10:.0f}" font-size="26" text-anchor="middle">🏆</text>'

    # 季军赛(底部居中,独立)
    third = ""
    if R["3rd-place-match"]:
        t = dict()
        tn = {"m": R["3rd-place-match"][0], "slug": "final", "ch": [], "x": _CX, "cy": H - 34}
        third = (f'<text class="i18n bk-lbl" data-zh="季军赛" data-en="3rd Place" x="{_CX+_BOXW/2:.0f}" '
                 f'y="{H-58:.0f}" text-anchor="middle">季军赛</text>' + _bk_box_svg(tn))

    hint = f'<div class="bk-hint">{bi("双指放大看细节 · 胜者金色高亮、出局队淡化", "Pinch to zoom · winners gold, losers dimmed")}</div>'
    svg = (f'<div class="bk-wrap"><svg class="bk-svg" viewBox="0 0 {W:.0f} {H:.0f}" '
           f'xmlns="http://www.w3.org/2000/svg" role="img" aria-label="淘汰赛对阵图">'
           f'<rect x="0" y="0" width="{W:.0f}" height="{H:.0f}" rx="10" fill="#0b1e3f"/>'
           f'<g class="bk-lines" stroke="#e0b53c" stroke-width="1.4" fill="none" opacity="0.7">{conns}</g>'
           f'{"".join(lbls)}{trophy}{boxes}{third}</svg></div>{hint}')
    return svg


def group_flags_overview(groups, elim):
    """树下方的小组分组国旗总览:每组按积分排序,前两名高亮,出局队国旗置灰。"""
    if not groups:
        return ""
    cards = []
    for g in sorted(groups, key=lambda x: x.get("name", "")):
        rows = []
        for i, r in enumerate(compute_table(g)):
            t = r["team"]
            out = " out" if t in elim else ""
            qual = " qual" if (i < 2 and not out) else ""
            rows.append(f'<div class="gf-t{out}{qual}" data-team="{esc(t)}">'
                        f'<span class="gf-fl">{flag(t)}</span>'
                        f'<span class="i18n gf-nm" data-zh="{esc(cn(t))}" data-en="{esc(t)}">{esc(cn(t))}</span></div>')
        cards.append(f'<div class="gf-card"><div class="gf-h">{esc(g["name"])}</div>{"".join(rows)}</div>')
    title = f'<div class="i18n gf-title" data-zh="小组分组 · 前二晋级 · 出局队灰显" data-en="Groups · top 2 advance · eliminated dimmed">小组分组 · 前二晋级 · 出局队灰显</div>'
    return f'{title}<div class="gf-grid">{"".join(cards)}</div>'


def build():
    with open(DATA, "r", encoding="utf-8") as f:
        data = json.load(f)
    meta = data.get("meta", {})
    elim = eliminated_teams(data)

    groups_html = "".join(group_block(g, elim) for g in data.get("groups", []))
    if not groups_html:
        groups_html = '<div class="empty">小组数据待补全</div>'

    # 近期赛程：未来 48 小时内要踢的（北京时间）。候选含小组赛 sched + fixtures 数组 + 淘汰赛 sched。
    BJT = timezone(timedelta(hours=8))

    def _mdt(m):
        ts = m.get("ts")
        if ts:
            return datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
        try:
            return datetime.strptime(m.get("date", "") + " " + (m.get("time") or "00:00"),
                                     "%Y-%m-%d %H:%M").replace(tzinfo=BJT)
        except ValueError:
            return None

    pool = []
    for g in data.get("groups", []):
        for m in g.get("matches", []):
            if m.get("status") == "sched":
                mm = dict(m); mm["group"] = g["name"]; pool.append(mm)
    for m in data.get("fixtures", []):
        if m.get("hs") is None:
            pool.append(dict(m))
    for m in data.get("knockout", []):
        if m.get("status") == "sched" or m.get("hs") is None:
            mm = dict(m); mm.setdefault("group", "淘汰赛"); pool.append(mm)

    now = datetime.now(BJT)
    end48 = now + timedelta(hours=48)
    win = sorted((( _mdt(m), m) for m in pool), key=lambda x: (x[0] is None, x[0] or now))
    in48 = [m for dt, m in win if dt is not None and now <= dt <= end48]
    if in48:
        upcoming = in48
        fix_zh, fix_en = "未来 48 小时", "Next 48h"
    else:
        # 当前时段没有 48h 内的比赛，退而显示最近即将开赛的 8 场
        upcoming = [m for dt, m in win if dt is not None and dt >= now][:8]
        fix_zh, fix_en = "即将开赛", "Upcoming"
    fixtures_html = ""
    if upcoming:
        _t = "🔥 " + bi("近期赛程 · " + fix_zh, "Up Next · " + fix_en)
        _cnt = f'<span class="cnt">{bi(f"{len(upcoming)} 场", str(len(upcoming)))}</span>'
        _note = f'<span class="note">{bi("（本地时间）", "(local time)")}</span>'
        _title = f"{_t} {_cnt}{_note}"
        _body = '<div class="fix-grid">' + "".join(match_row(m, show_group=True) for m in upcoming) + '</div>'
        fixtures_html = collap(_title, _body, open_=True, cls="fixtures hero")

    # 最近战果：正在进行(LIVE)的场必须包含、且置顶；其后接「最近6场」与「最近24小时」中较多的一组。
    played_pool, live_pool = [], []

    def _push(m, grp):
        st = m.get("status")
        dt = _mdt(m)
        # 已到/过开球时间但数据仍停留在 sched（fetch 未及时刷成 LIVE）→ 视同进行中并置顶。
        # 否则这场会卡在「近期赛程(只收未来 sched)」与「最近战果(只收 LIVE/FT)」的夹缝中消失。
        if st == "LIVE" or (st == "sched" and dt is not None and dt <= now):
            mm = dict(m); mm["group"] = grp; mm["status"] = "LIVE"; live_pool.append(mm)
        elif st == "FT" and m.get("hs") is not None:
            mm = dict(m); mm["group"] = grp; played_pool.append(mm)

    for g in data.get("groups", []):
        for m in g.get("matches", []):
            _push(m, g["name"])
    for m in data.get("knockout", []):
        _push(m, "淘汰赛")
    _far = datetime.min.replace(tzinfo=BJT)
    played_desc = sorted(played_pool, key=lambda m: (_mdt(m) or _far), reverse=True)
    last6 = played_desc[:6]
    last24 = [m for m in played_desc if _mdt(m) and (now - timedelta(hours=24)) <= _mdt(m) <= now]
    base = last24 if len(last24) > len(last6) else last6
    _more24 = len(last24) > len(last6)
    base_zh = "最近 24 小时" if _more24 else "最近 6 场"
    base_en = "Last 24h" if _more24 else "Last 6"
    live_sorted = sorted(live_pool, key=lambda m: (_mdt(m) or _far), reverse=True)
    recent = live_sorted + base
    rec_zh = ("进行中 + " + base_zh) if live_sorted else base_zh
    rec_en = ("Live + " + base_en) if live_sorted else base_en
    recent_html = ""
    if recent:
        _t = "🏁 " + bi("赛果", "Results")
        _note = f'<span class="note">{bi("（本地时间）", "(local time)")}</span>'
        _title = f"{_t} {_note}"
        _recent_grid = '<div class="fix-grid">' + "".join(match_row(m, show_group=True) for m in recent) + '</div>'
        if played_desc:
            # 两个 tab：默认「最近」(进行中+最近6场/24h，卡片铺开)；
            # HISTORY 列全部已赛(最新在前)，用紧凑列表，点击单行再展开细节，免去到小组赛逐个翻找
            _sort_bar = ('<div class="mlsort">'
                         f'<span class="mlsort-l">{bi("排序", "Sort")}</span>'
                         f'<button type="button" class="sortb on" data-k="ts" data-dir="desc">{bi("时间", "Time")}</button>'
                         f'<button type="button" class="sortb" data-k="country" data-dir="asc">{bi("国家", "Country")}</button>'
                         f'<button type="button" class="sortb" data-k="wg" data-dir="desc">{bi("胜方进球", "Winner goals")}</button>'
                         '</div>')
            _hist_list = (_sort_bar + '<div class="ml-list">'
                          + "".join(match_list_row(m) for m in played_desc) + '</div>')
            _tabs = ('<div class="rtabs">'
                     f'<button type="button" class="rtab on" data-rp="recent">{bi(rec_zh, rec_en)} '
                     f'<span class="num">{len(recent)}</span></button>'
                     f'<button type="button" class="rtab" data-rp="hist">{bi("历史全部", "HISTORY")} '
                     f'<span class="num">{len(played_desc)}</span></button>'
                     '</div>')
            _body = (_tabs
                     + f'<div class="rpanel" data-rp="recent">{_recent_grid}</div>'
                     + f'<div class="rpanel" data-rp="hist" hidden>{_hist_list}</div>')
        else:
            _body = _recent_grid
        recent_html = collap(_title, _body, open_=True, cls="results hero")

    # 球员进球榜：汇总各场进球者（乌龙球不计个人）。
    scorers = {}

    def _collect_goals(matches):
        for mm in matches:
            if mm.get("status") != "FT":
                continue  # 只统计完场的进球;进行中的比赛等完场再计入射手榜
            for goal in mm.get("goals", []):
                t = goal.get("type", "") or ""
                if "Own" in t:
                    continue
                nm = goal.get("scorer")
                if not nm:
                    continue
                rec = scorers.setdefault(nm, {"name": nm, "team": goal.get("team", ""), "goals": 0, "pens": 0})
                rec["goals"] += 1
                if "Penalty" in t:
                    rec["pens"] += 1

    for g in data.get("groups", []):
        _collect_goals(g.get("matches", []))
    _collect_goals(data.get("knockout", []))
    top = sorted(scorers.values(), key=lambda r: (-r["goals"], r["name"]))
    scorers_html = ""
    if top:
        def _score_table(items, start):
            rs = []
            for j, r in enumerate(items):
                pen = ""
                if r["pens"]:
                    _pz = f'含{r["pens"]}点'
                    _pe = f'{r["pens"]} pen'
                    pen = f'<span class="pen">{bi(_pz, _pe)}</span>'
                rs.append(f'<tr><td class="rank">{start + j}</td>'
                          f'<td class="tname">{esc(r["name"])}{pen}</td>'
                          f'<td>{team_flag_bi(r["team"])}</td><td class="pts">{r["goals"]}</td></tr>')
            return ('<table class="scoretable"><thead><tr><th>#</th>'
                    f'<th class="tname">{bi("球员", "Player")}</th>'
                    f'<th>{bi("球队", "Team")}</th><th>{bi("进", "G")}</th></tr></thead><tbody>'
                    + "".join(rs) + '</tbody></table>')

        topn = top[:20]
        half = (len(topn) + 1) // 2
        cols = '<div class="scorer-cols">' + _score_table(topn[:half], 1)
        if topn[half:]:
            cols += _score_table(topn[half:], half + 1)
        cols += '</div>'
        more = (f'<div class="more">{bi(f"仅显示前 20 名，共 {len(top)} 名球员有进球", f"Top 20 of {len(top)} scorers")}</div>'
                if len(top) > 20 else "")
        scorers_html = collap("⚽ " + bi("球员进球榜", "Top Scorers"), cols + more, open_=False, cls="scorers")

    standings_html = collap(bi("小组积分榜", "Group Standings"), f'<div class="groups">{groups_html}</div>',
                            open_=False, cls="standings")

    knockout = data.get("knockout", [])
    knockout_html = collap(bi("淘汰赛对阵图", "Knockout Bracket"),
                           bracket_svg(knockout) + group_flags_overview(data.get("groups", []), elim),
                           open_=False, cls="knockout")

    sources = " · ".join(esc(s) for s in meta.get("sources", []))
    _built = datetime.now(timezone.utc)
    built_at = _built.astimezone(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M")
    built_ms = int(_built.timestamp() * 1000)

    # 实时比分：比赛进行中时每 45 秒直连 ESPN scoreboard（CORS: *，前端可直连），按队名
    # （displayName，与 data.json 同源）匹配页面比赛，局部更新比分/状态/时钟。不刷整页、不动
    # 积分榜（LIVE 不计分，只算完场）；也根治"已开球但仍 sched 显示 vs"——拉到实时比分即填上。
    live_js = r'''
(function(){
  var EP='https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard?dates=';
  var SM='https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/summary?event=';
  function ymd(d){return d.getUTCFullYear()+('0'+(d.getUTCMonth()+1)).slice(-2)+('0'+d.getUTCDate()).slice(-2);}
  function range(){var n=Date.now();return ymd(new Date(n-86400000))+'-'+ymd(new Date(n+86400000));}
  function key(h,a){return (h||'').toLowerCase()+'|'+(a||'').toLowerCase();}
  function en(){return document.documentElement.getAttribute('data-lang')==='en';}
  var idx={};
  var ms=document.querySelectorAll('.match');
  for(var i=0;i<ms.length;i++){
    var h=ms[i].getAttribute('data-h'),a=ms[i].getAttribute('data-a');
    if(h&&a){var k=key(h,a);(idx[k]=idx[k]||[]).push(ms[i]);}
  }
  // 对阵图 SVG 节点索引(与 .match 同键,实时更新比分/胜负/点球 + 输球置灰积分榜)
  var bidx={};
  var bms=document.querySelectorAll('.bk-node');
  for(var bi2=0;bi2<bms.length;bi2++){
    var bh=bms[bi2].getAttribute('data-h'),ba=bms[bi2].getAttribute('data-a');
    if(bh&&ba){var bk=key(bh,ba);(bidx[bk]=bidx[bk]||[]).push(bms[bi2]);}
  }
  if(!Object.keys(idx).length && !Object.keys(bidx).length) return;
  function dimTeam(name){
    var all=document.querySelectorAll('[data-team]');  // 积分榜行 + 小组国旗总览格,一起置灰
    for(var q=0;q<all.length;q++){ if(all[q].getAttribute('data-team')===name) all[q].classList.add('out'); }
  }
  function applyBK(gs,hs,as,state,sh,sa,stName){
    var winner=null;
    if(state==='post'){
      if(stName.indexOf('PEN')>=0&&sh!=null&&sa!=null) winner=(sh>sa)?'h':'a';
      else if(hs!=null&&as!=null){ if(hs>as)winner='h'; else if(as>hs)winner='a'; }
    }
    function setRow(row,score,role){ // role:'w'胜 'l'负 ''中性
      var sc=row.querySelector('.bk-sc'); if(sc) sc.textContent=(score==null?'':score);
      var nm=row.querySelector('.bk-nm');
      row.removeAttribute('opacity');
      if(nm){ nm.setAttribute('fill',role==='w'?'#ffffff':'#c8d4ec'); if(role==='w') nm.setAttribute('font-weight','700'); else nm.removeAttribute('font-weight'); }
      if(sc) sc.setAttribute('fill',role==='w'?'#f4c430':'#c8d4ec');
      if(role==='l') row.setAttribute('opacity','0.4');
    }
    for(var i=0;i<gs.length;i++){
      var g=gs[i],rows=g.querySelectorAll('.bk-row');
      if(rows.length<2) continue;
      setRow(rows[0],state==='pre'?null:hs,winner==='h'?'w':(winner==='a'?'l':''));
      setRow(rows[1],state==='pre'?null:as,winner==='a'?'w':(winner==='h'?'l':''));
      var note=g.querySelector('.bk-note-t'),nz='',ne='';
      if(state==='post'){
        if(stName.indexOf('PEN')>=0&&sh!=null&&sa!=null){ nz='点球'+sh+':'+sa; ne='pens '+sh+':'+sa; }
        else if(stName.indexOf('AET')>=0){ nz='加时'; ne='AET'; }
      }
      if(note){ note.setAttribute('data-zh',nz); note.setAttribute('data-en',ne); note.textContent=en()?ne:nz; }
      if(state==='in') g.classList.add('live'); else g.classList.remove('live');
      if(winner){ dimTeam(winner==='h'?g.getAttribute('data-a'):g.getAttribute('data-h')); }
    }
  }
  function setBadge(meta,state,clock){
    var b=meta.querySelector('.badge'); if(!b) return;
    var cls,z,e;
    if(state==='in'){cls='live';z='进行中';e='LIVE';}
    else if(state==='post'){cls='ft';z='完场';e='FT';}
    else{cls='sched';z='未开赛';e='Sched';}
    b.className='badge '+cls;
    var clk=(state==='in'&&clock)?(' '+String(clock).replace(/[^0-9'+:A-Za-z ]/g,'')):'';
    b.innerHTML='<span class="i18n" data-zh="'+z+'" data-en="'+e+'">'+(en()?e:z)+'</span>'+clk;
  }
  function mark(t){
    t=t||'';
    if(t.indexOf('Penalty')>=0) return en()?' (P)':'(点球)';
    if(t.indexOf('Own')>=0) return en()?' (OG)':'(乌龙)';
    if(t.indexOf('Header')>=0) return en()?' (H)':'(头球)';
    return '';
  }
  function gesc(s){var n=document.createElement('div');n.textContent=(s==null?'':String(s));return n.innerHTML;}
  function renderGoals(els,goals){
    if(!goals.length) return;
    var h='<div class="m-goals">⚽ ';
    for(var i=0;i<goals.length;i++){
      var g=goals[i];
      h+='<span class="gitem">'+gesc(g.min)+' '+gesc(g.scorer)+mark(g.type)+'<span class="gteam">'+gesc(g.team)+'</span></span>';
    }
    h+='</div>';
    for(var j=0;j<els.length;j++){
      var old=els[j].querySelector('.m-goals');
      if(old) old.outerHTML=h; else els[j].insertAdjacentHTML('beforeend',h);
    }
  }
  function fetchGoals(eid,els){
    fetch(SM+eid,{cache:'no-store'}).then(function(r){return r.json();}).then(function(s){
      var ke=s.keyEvents||[],goals=[];
      for(var i=0;i<ke.length;i++){
        var k=ke[i]; if(!k.scoringPlay) continue;
        var ps=k.participants||[];
        var sc=(ps[0]&&ps[0].athlete)?ps[0].athlete.displayName:'?';
        goals.push({min:(k.clock||{}).displayValue||'',scorer:sc,type:(k.type||{}).text||'',team:(k.team||{}).displayName||''});
      }
      renderGoals(els,goals);
    }).catch(function(){});
  }
  function apply(els,hs,as,state,clock,eid,sh,sa,stName){
    for(var i=0;i<els.length;i++){
      var el=els[i];
      var sc=el.querySelector('.m-score');
      if(sc&&state!=='pre'&&hs!=null&&as!=null){
        // 淘汰赛完场:点球场补「点球 4:3」、加时绝杀补「加时」,与服务端 score_cell 同口径
        var ex='';
        if(state==='post'&&stName){
          if(stName.indexOf('PEN')>=0&&sh!=null&&sa!=null) ex='<span class="sdecide">'+(en()?'pens ':'点球 ')+sh+':'+sa+'</span>';
          else if(stName.indexOf('AET')>=0) ex='<span class="sdecide">'+(en()?'AET':'加时')+'</span>';
        }
        sc.innerHTML='<span class="score">'+hs+' : '+as+'</span>'+ex;
      }
      var meta=el.querySelector('.m-meta');
      if(meta) setBadge(meta,state,clock);
    }
    // 进行中:每轮刷新进球。完场:若卡片还没进球就补拉一次——完赛瞬间服务端重建常拿不到
    // 进球数据,FT 卡片是空的,会把之前 live 渲染的进球人/进球时间覆盖掉,这里客户端兜底填回。
    if(eid&&(state==='in'||(state==='post'&&els[0]&&!els[0].querySelector('.m-goals')))) fetchGoals(eid,els);
  }
  var timer=null;
  function poll(){
    fetch(EP+range(),{cache:'no-store'}).then(function(r){return r.json();}).then(function(d){
      var evs=(d&&d.events)||[],live=false;
      for(var i=0;i<evs.length;i++){
        var c=(evs[i].competitions||[])[0];if(!c)continue;
        var cs=c.competitors||[];if(cs.length!==2)continue;
        var hc=cs[0].homeAway==='home'?cs[0]:cs[1];
        var ac=cs[0].homeAway==='home'?cs[1]:cs[0];
        var st=((c.status||{}).type)||{},state=st.state||'';
        var els=idx[key((hc.team||{}).displayName,(ac.team||{}).displayName)];
        if(els){apply(els,hc.score,ac.score,state,(c.status||{}).displayClock,evs[i].id,hc.shootoutScore,ac.shootoutScore,st.name||'');if(state==='in')live=true;}
        var bcards=bidx[key((hc.team||{}).displayName,(ac.team||{}).displayName)];
        if(bcards) applyBK(bcards,hc.score,ac.score,state,hc.shootoutScore,ac.shootoutScore,st.name||'');
      }
      if(timer)clearInterval(timer);
      timer=setInterval(poll,live?45000:300000);
    }).catch(function(){if(timer)clearInterval(timer);timer=setInterval(poll,300000);});
  }
  poll();
})();
'''

    page = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="renderer" content="webkit">
<meta name="force-rendering" content="webkit">
<meta name="HandheldFriendly" content="true">
<meta name="MobileOptimized" content="width">
<meta name="applicable-device" content="mobile">
<title>{esc(meta.get('tournament','世界杯'))} · 战报</title>
<link rel="manifest" href="manifest.webmanifest">
<meta name="theme-color" content="#0f1419">
<link rel="icon" href="icon-192.png">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="世界杯">
<meta name="application-name" content="世界杯">
<meta property="og:title" content="2026世界杯战报">
<meta property="og:description" content="积分榜·射手榜·每场官方集锦·赛程,每小时自动更新">
<meta property="og:type" content="website">
<meta property="og:url" content="https://worldcup-ata.pages.dev/">
<meta property="og:image" content="https://worldcup-ata.pages.dev/icon-512.png">
<meta property="og:image:width" content="512">
<meta property="og:image:height" content="512">
<meta name="description" content="2026世界杯实时战报:积分榜·射手榜·每场官方集锦·赛程,每小时自动更新,中英双语">
<style>
  :root {{
    --bg:#0f1419; --card:#1a212b; --line:#2a3441; --txt:#e6edf3;
    --muted:#8b98a5; --accent:#3fb950; --gold:#d4a017; --live:#f85149;
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--txt);
    font-family:-apple-system,"Segoe UI","Microsoft YaHei",sans-serif; line-height:1.5; }}
  .wrap {{ max-width:1100px; margin:0 auto;
    padding:calc(24px + env(safe-area-inset-top)) calc(16px + env(safe-area-inset-right))
            calc(60px + env(safe-area-inset-bottom)) calc(16px + env(safe-area-inset-left)); }}
  header.top {{ border-bottom:2px solid var(--line); padding-bottom:16px; margin-bottom:24px; }}
  header.top h1 {{ margin:0 0 6px; font-size:28px; }}
  .sub {{ color:var(--muted); font-size:13px; display:flex; flex-wrap:wrap; gap:6px 16px; }}
  .sub b {{ color:var(--txt); font-weight:600; }}
  .notes {{ background:#1c2733; border-left:3px solid var(--gold); padding:10px 14px;
    border-radius:0 6px 6px 0; margin-top:14px; font-size:13px; color:var(--muted); }}
  h2 {{ font-size:20px; margin:32px 0 14px; padding-left:10px; border-left:4px solid var(--accent); }}
  .sec {{ margin:0 0 12px; background:var(--card); border:1px solid var(--line);
    border-radius:12px; padding:14px 18px; }}
  .sec > .sec-h {{ list-style:none; cursor:pointer; user-select:none; font-size:20px; font-weight:600;
    margin:0; padding-left:10px; border-left:4px solid var(--accent);
    display:flex; align-items:center; gap:10px; flex-wrap:wrap; }}
  .sec[open] > .sec-h {{ margin-bottom:14px; }}
  .sec > .sec-h::-webkit-details-marker {{ display:none; }}
  .sec > .sec-h::after {{ content:"▸ 展开"; color:var(--muted); font-size:12px; font-weight:400; margin-left:auto; }}
  .sec[open] > .sec-h::after {{ content:"▾ 收起"; }}
  .sec > .sec-h:hover {{ color:var(--accent); }}
  .sec .note {{ font-size:12px; color:var(--muted); font-weight:400; }}
  .scorer-cols {{ display:grid; grid-template-columns:1fr; gap:14px; align-items:start; }}
  .groups {{ display:grid; grid-template-columns:1fr; gap:18px; }}
  .group {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:14px 16px; }}
  .group h3 {{ margin:0 0 10px; font-size:16px; color:var(--gold); }}
  table.standings {{ width:100%; border-collapse:collapse; font-size:13px; }}
  table.standings th {{ color:var(--muted); font-weight:500; text-align:center; padding:4px 3px; border-bottom:1px solid var(--line); }}
  table.standings td {{ text-align:center; padding:5px 3px; border-bottom:1px solid #222c38; }}
  td.tname, th.tname {{ text-align:left; }}
  td.rank {{ color:var(--muted); }}
  td.pts {{ font-weight:700; color:var(--txt); }}
  td.gd {{ color:var(--muted); }}
  tr.qualify td {{ background:rgba(63,185,80,0.10); }}
  tr.qualify td.rank {{ color:var(--accent); font-weight:700; box-shadow:inset 2px 0 0 var(--accent); }}
  /* 已出局的队:整行淡化、国旗去色(name 加删除线) */
  tr.out td {{ opacity:0.42; }}
  tr.out .flag {{ filter:grayscale(1); }}
  tr.out .tname {{ text-decoration:line-through; text-decoration-color:rgba(139,152,165,0.5); }}
  /* 淘汰赛对阵图:SVG 对称树,皇家蓝+金,宽度自适应(缩放看全貌,双指放大看细节) */
  .bk-wrap {{ width:100%; overflow-x:auto; -webkit-overflow-scrolling:touch;
    background:#0b1e3f; border-radius:10px; }}
  .bk-svg {{ display:block; width:100%; height:auto; }}
  .bk-lbl {{ font-size:13px; font-weight:700; fill:var(--gold); }}
  .bk-node.live .bk-box {{ stroke:var(--live); stroke-width:2; }}
  .bk-hint {{ color:var(--muted); font-size:11px; text-align:center; margin-top:8px; }}
  /* 树下方:小组分组国旗总览(出局队国旗置灰) */
  .gf-title {{ color:var(--gold); font-size:13px; font-weight:700; text-align:center; margin:18px 0 10px; }}
  .gf-grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(116px,1fr)); gap:8px; }}
  .gf-card {{ background:#0f151c; border:1px solid #21262d; border-radius:8px; padding:6px 9px; }}
  .gf-h {{ font-size:12px; font-weight:700; color:var(--gold); text-align:center;
    border-bottom:1px solid #21262d; padding-bottom:4px; margin-bottom:5px; }}
  .gf-t {{ display:flex; align-items:center; gap:7px; font-size:14px; color:var(--muted); padding:2.5px 0; }}
  .gf-fl {{ font-size:18px; line-height:1; }}
  .gf-t.qual {{ color:var(--txt); font-weight:600; }}
  .gf-t.out {{ opacity:0.4; }}
  .gf-t.out .gf-fl {{ filter:grayscale(1); }}
  .g-details {{ margin-top:10px; }}
  .g-details > summary {{ cursor:pointer; list-style:none; user-select:none; font-size:12.5px;
    color:var(--muted); padding:6px 10px; border-radius:6px; background:#161d27;
    border:1px solid var(--line); }}
  .g-details > summary::-webkit-details-marker {{ display:none; }}
  .g-details > summary::after {{ content:"▸ 点击展开"; float:right; color:var(--gold); font-size:11px; }}
  .g-details[open] > summary::after {{ content:"▾ 收起"; }}
  .g-details > summary:hover {{ color:var(--txt); border-color:var(--accent); }}
  .g-details[open] > summary {{ color:var(--txt); margin-bottom:6px; }}
  .g-matches {{ display:flex; flex-direction:column; gap:4px; }}
  .match {{ display:grid; grid-template-columns:72px 1fr auto 1fr; align-items:center;
    gap:6px; font-size:12.5px; padding:5px 4px; border-radius:6px; }}
  .match:hover {{ background:#222c38; }}
  .m-date {{ color:var(--muted); font-size:11px; }}
  .m-home {{ text-align:right; }}
  .m-away {{ text-align:left; }}
  .m-score {{ text-align:center; min-width:54px; }}
  .score {{ font-weight:700; }}
  .vs {{ color:var(--muted); font-size:11px; }}
  .sdecide {{ display:block; color:var(--gold); font-size:10px; line-height:1.2; margin-top:1px; white-space:nowrap; }}
  .m-meta {{ grid-column:2 / -1; display:flex; gap:8px; align-items:center; }}
  .badge {{ font-size:10px; padding:1px 6px; border-radius:10px; }}
  .badge.ft {{ background:#21262d; color:var(--muted); }}
  .badge.live {{ background:rgba(248,81,73,0.15); color:var(--live); }}
  .badge.sched {{ background:rgba(212,160,23,0.15); color:var(--gold); }}
  .venue {{ color:var(--muted); font-size:11px; }}
  .tag {{ background:#21262d; color:var(--muted); padding:0 5px; border-radius:4px; font-size:10px; }}
  .tag.ko {{ background:rgba(212,160,23,0.16); color:var(--gold); font-weight:600; }}
  .flag {{ margin:0 4px; font-size:1.15em; line-height:1; vertical-align:-1px; }}
  .m-goals {{ grid-column:1 / -1; font-size:12px; color:var(--txt); display:flex; flex-wrap:wrap;
    gap:6px 12px; padding:4px 2px 0; }}
  .gitem {{ color:#cdd6e0; }}
  .gteam {{ color:var(--muted); font-size:10.5px; margin-left:3px; }}
  .m-videos {{ grid-column:1 / -1; display:flex; flex-wrap:wrap; gap:6px 10px; padding:4px 2px 0; }}
  .vlink {{ color:var(--accent); font-size:11px; text-decoration:none; border:1px solid #2f4636;
    padding:1px 7px; border-radius:10px; }}
  .vlink:hover {{ background:rgba(63,185,80,0.12); }}
  .vlink.yt {{ color:#ff6b6b; border-color:#5a2f2f; }}
  .vlink.yt:hover {{ background:rgba(248,81,73,0.12); }}
  .scorers {{ margin-top:18px; }}
  /* 下方三个板块:与上面 hero 卡保持一致的卡片框(边框+柔和发光),但比 hero 略淡以维持层级 */
  .sec.standings, .sec.scorers, .sec.knockout {{
    border:1px solid #36434f; box-shadow:0 0 0 3px rgba(63,185,80,0.06); }}
  table.scoretable {{ width:100%; border-collapse:collapse; font-size:13px;
    background:var(--card); border:1px solid var(--line); border-radius:10px; overflow:hidden; }}
  table.scoretable th {{ color:var(--muted); font-weight:500; text-align:center; padding:8px 6px; border-bottom:1px solid var(--line); }}
  table.scoretable td {{ text-align:center; padding:7px 6px; border-bottom:1px solid #222c38; }}
  table.scoretable td.tname {{ text-align:left; }}
  table.scoretable td.pts {{ font-weight:700; color:var(--accent); }}
  .pen {{ color:var(--muted); font-size:10.5px; margin-left:6px; }}
  .more {{ color:var(--muted); font-size:12px; margin-top:8px; }}
  .fix-grid {{ display:grid; grid-template-columns:1fr; gap:8px; }}
  @media (min-width:901px) {{
    .groups {{ grid-template-columns:repeat(auto-fill,minmax(330px,1fr)); }}
    .fix-grid {{ grid-template-columns:repeat(auto-fill,minmax(300px,1fr)); }}
    .scorer-cols {{ grid-template-columns:1fr 1fr; }}
  }}
  .fix-grid .match {{ background:var(--card); border:1px solid var(--line); padding:10px 12px; }}
  .fixtures.hero {{ background:linear-gradient(180deg,#1c2a22,#161d27); border:1px solid var(--accent);
    border-radius:12px; padding:14px 18px 18px; margin-bottom:10px; box-shadow:0 0 0 3px rgba(63,185,80,0.08); }}
  .fixtures.hero > .sec-h {{ margin:2px 0 12px; border-left-color:var(--gold); }}
  .fixtures.hero .cnt {{ background:var(--accent); color:#06210f; font-size:13px; font-weight:700;
    padding:1px 9px; border-radius:10px; }}
  .fixtures.hero .fix-grid .match {{ background:#10171f; border-color:#2f4636; }}
  .results.hero {{ background:linear-gradient(180deg,#2a2418,#161d27); border:1px solid var(--gold);
    border-radius:12px; padding:14px 18px 18px; margin-bottom:10px; box-shadow:0 0 0 3px rgba(212,160,23,0.08); }}
  .results.hero > .sec-h {{ margin:2px 0 12px; border-left-color:var(--gold); }}
  .results.hero .cnt {{ background:var(--gold); color:#211900; font-size:13px; font-weight:700;
    padding:1px 9px; border-radius:10px; }}
  .results.hero .fix-grid .match {{ background:#10171f; border-color:#463a2f; }}
  /* 最近战果框内的 tab：最近 / HISTORY */
  .rtabs {{ display:flex; gap:8px; margin-bottom:14px; flex-wrap:wrap; }}
  .rtab {{ background:transparent; color:var(--muted); border:1px solid var(--line);
    border-radius:8px; padding:6px 14px; font-size:14px; font-weight:600; cursor:pointer;
    font-family:inherit; line-height:1.2; display:inline-flex; align-items:center; gap:7px; }}
  .rtab:hover {{ color:var(--txt); border-color:var(--gold); }}
  .rtab.on {{ color:#211900; background:var(--gold); border-color:var(--gold); }}
  .rtab .num {{ font-weight:700; opacity:.85; }}
  .rtab.on .num {{ opacity:1; }}
  .rpanel[hidden] {{ display:none; }}
  @media (max-width:900px) {{ .rtab {{ font-size:15px; padding:7px 15px; }} }}
  /* HISTORY 紧凑列表：一行一场，点击展开 */
  .ml-list {{ display:flex; flex-direction:column; gap:4px; }}
  .ml-row {{ background:#10171f; border:1px solid #2a3441; border-radius:8px; }}
  .ml-row[open] {{ border-color:var(--gold); }}
  .ml-line {{ display:flex; align-items:center; gap:10px; padding:8px 12px; font-size:14px;
    cursor:pointer; user-select:none; }}
  .ml-tog {{ flex:0 0 auto; color:var(--muted); font-size:11px; margin-left:2px; transition:transform .15s; }}
  .ml-row.open .ml-tog {{ transform:rotate(90deg); color:var(--gold); }}
  .ml-when {{ display:flex; align-items:center; gap:6px; flex:0 0 auto;
    min-width:92px; color:var(--muted); font-size:12px; }}
  .ml-h {{ flex:1 1 0; text-align:right; min-width:0; }}
  .ml-a {{ flex:1 1 0; text-align:left; min-width:0; }}
  .ml-sc {{ flex:0 0 auto; min-width:52px; text-align:center; color:var(--gold); }}
  .ml-line:hover {{ background:#141d27; }}
  .ml-line:hover .ml-h, .ml-line:hover .ml-a {{ color:var(--accent); }}
  .ml-body {{ padding:8px 12px 10px; border-top:1px solid #222c38; }}
  .ml-venue {{ color:var(--muted); font-size:12px; padding:2px 0 4px; }}
  /* HISTORY 排序工具栏 */
  .mlsort {{ display:flex; align-items:center; gap:7px; flex-wrap:wrap; margin-bottom:10px; }}
  .mlsort-l {{ color:var(--muted); font-size:12px; }}
  .sortb {{ background:transparent; color:var(--muted); border:1px solid var(--line);
    border-radius:7px; padding:4px 11px; font-size:13px; cursor:pointer; font-family:inherit;
    line-height:1.2; }}
  .sortb:hover {{ color:var(--txt); border-color:var(--gold); }}
  .sortb.on {{ color:#211900; background:var(--gold); border-color:var(--gold); font-weight:600; }}
  .sortb .ar {{ margin-left:4px; font-size:11px; }}
  @media (max-width:900px) {{
    .ml-line {{ font-size:15px; gap:8px; }}
    .ml-when {{ min-width:64px; }}
    .sortb {{ font-size:14px; padding:5px 12px; }}
  }}
  .empty {{ color:var(--muted); font-size:13px; padding:16px; text-align:center;
    background:var(--card); border:1px dashed var(--line); border-radius:8px; }}
  footer {{ margin-top:40px; padding-top:16px; border-top:1px solid var(--line);
    color:var(--muted); font-size:12px; text-align:center; }}
  /* 防止长英文(场馆/标题)撑破布局导致整页缩小 */
  html {{ -webkit-text-size-adjust:100%; text-size-adjust:100%; }}
  body {{ overflow-wrap:break-word; }}
  .venue, td.tname, .gitem {{ overflow-wrap:anywhere; }}
  /* 手机端:普通浏览器按原始 px 会偏小,这里整体放大字号 */
  @media (max-width:900px) {{
    .wrap {{ padding-left:calc(10px + env(safe-area-inset-left));
             padding-right:calc(10px + env(safe-area-inset-right)); }}
    header.top h1 {{ font-size:23px; }}
    .sub {{ font-size:13.5px; }}
    .sec {{ padding:13px 13px; }}
    .sec > .sec-h {{ font-size:18px; }}
    .cnt, .note {{ font-size:13px; }}
    .group h3 {{ font-size:17px; }}
    .match {{ font-size:15px; }}
    .m-date {{ font-size:13px; }}
    .score {{ font-size:17px; }}
    .m-goals {{ font-size:14px; }}
    .gteam {{ font-size:12px; }}
    .vlink {{ font-size:13px; padding:3px 10px; }}
    .badge {{ font-size:12px; }}
    .venue, .tag {{ font-size:12px; }}
    table.standings {{ font-size:15px; }}
    table.standings th, table.standings td {{ padding:7px 2px; }}
    table.scoretable {{ font-size:15px; }}
    table.scoretable th, table.scoretable td {{ padding:9px 4px; }}
    .more {{ font-size:13px; }}
  }}
  /* 标题行 + 右上角菜单 */
  .top-row {{ display:flex; align-items:flex-start; gap:10px; }}
  .top-row h1 {{ flex:1 1 auto; min-width:0; margin:0 0 6px; }}
  .menu-wrap {{ position:relative; flex:0 0 auto; }}
  .topbtn {{ background:var(--card); color:var(--muted); display:inline-flex; align-items:center;
    border:1px solid var(--line); border-radius:8px; padding:6px 10px; font-size:13px;
    cursor:pointer; font-family:inherit; line-height:1; }}
  .topbtn:hover {{ color:var(--txt); border-color:var(--accent); }}
  .menu {{ position:absolute; top:calc(100% + 6px); right:0; z-index:60; min-width:140px;
    background:var(--card); border:1px solid var(--line); border-radius:10px; padding:6px;
    box-shadow:0 8px 24px rgba(0,0,0,0.5); display:flex; flex-direction:column; gap:2px; }}
  .menu[hidden] {{ display:none; }}
  .menu-item {{ background:transparent; color:var(--txt); border:none; text-align:left;
    padding:9px 12px; font-size:14px; border-radius:7px; cursor:pointer; font-family:inherit; }}
  .menu-item:hover {{ background:#222c38; color:var(--accent); }}
  /* 有新数据时弹出的刷新小条(底部居中,不打断阅读) */
  .rfpill {{ position:fixed; left:50%; transform:translateX(-50%);
    bottom:calc(16px + env(safe-area-inset-bottom)); z-index:50;
    background:var(--gold); color:#211900; border:none; border-radius:20px;
    padding:10px 18px; font-size:14px; font-weight:600; font-family:inherit; cursor:pointer;
    box-shadow:0 4px 16px rgba(0,0,0,0.45); }}
  /* 英文模式下的折叠标记文案 */
  html[data-lang=en] .sec > .sec-h::after {{ content:"▸ Expand"; }}
  html[data-lang=en] .sec[open] > .sec-h::after {{ content:"▾ Collapse"; }}
  html[data-lang=en] .g-details > summary::after {{ content:"▸ Show"; }}
  html[data-lang=en] .g-details[open] > summary::after {{ content:"▾ Hide"; }}
</style>
</head>
<body>
<div class="wrap">
  <header class="top">
    <div class="top-row">
      <h1>⚽ {bi(esc(meta.get('tournament','世界杯')) + " 战报", "2026 World Cup · Match Report")}</h1>
      <div class="menu-wrap">
        <button id="menubtn" class="topbtn" type="button" aria-label="menu" aria-haspopup="true" aria-expanded="false">
          <svg width="20" height="20" viewBox="0 0 20 20" aria-hidden="true"><circle cx="6" cy="6" r="2" fill="currentColor"/><circle cx="14" cy="6" r="2" fill="currentColor"/><circle cx="6" cy="14" r="2" fill="currentColor"/><circle cx="14" cy="14" r="2" fill="currentColor"/></svg>
        </button>
        <div id="menu" class="menu" hidden role="menu">
          <button class="menu-item" type="button" data-act="refresh" role="menuitem"><span class="i18n" data-zh="刷新" data-en="Refresh">刷新</span></button>
          <button class="menu-item" type="button" data-act="share" role="menuitem"><span class="i18n" data-zh="分享" data-en="Share">分享</span></button>
          <button class="menu-item" type="button" data-act="notify" id="notifyitem" role="menuitem">🔔 开启提醒</button>
          <button class="menu-item" type="button" data-act="lang" id="langitem" role="menuitem">EN</button>
        </div>
      </div>
    </div>
    <div class="sub">
      <span>{bi("主办：", "Hosts: ")}<b>{bi(meta.get('host',''), "USA / Canada / Mexico")}</b></span>
      <span>{bi("数据更新：", "Updated: ")}<b data-ts="{meta.get('lastUpdatedTs','')}">{esc(meta.get('lastUpdated',''))}</b>{bi("（本地时间）", " (local time)")}</span>
    </div>
  </header>

  {recent_html}

  {fixtures_html}

  {scorers_html}

  {standings_html}

  {knockout_html}

  <footer>{bi("页面生成于", "Generated")} <span data-ts="{built_ms}">{built_at}</span> · {bi("时间按你的浏览器时区显示 · 积分榜自动推算", "Times shown in your browser timezone · standings auto-computed")}</footer>
</div>
<script>
(function(){{
  function p(n){{return String(n).padStart(2,'0');}}
  function abs(ms){{
    var d=new Date(Number(ms));
    if(isNaN(d.getTime()))return null;
    return d.getFullYear()+'-'+p(d.getMonth()+1)+'-'+p(d.getDate())+' '+p(d.getHours())+':'+p(d.getMinutes());
  }}
  // 比赛时间:今天/明天/昨天用词代替日期(按本地时区),其余日子显示完整日期
  function rel(ms,en){{
    var d=new Date(Number(ms));
    if(isNaN(d.getTime()))return null;
    var now=new Date();
    var a=new Date(d.getFullYear(),d.getMonth(),d.getDate());
    var b=new Date(now.getFullYear(),now.getMonth(),now.getDate());
    var diff=Math.round((a-b)/86400000);
    var hm=p(d.getHours())+':'+p(d.getMinutes());
    if(diff===0) return (en?'Today':'今天')+' '+hm;
    if(diff===1) return (en?'Tomorrow':'明天')+' '+hm;
    if(diff===-1) return (en?'Yesterday':'昨天')+' '+hm;
    return abs(ms);
  }}
  function renderTimes(en){{
    var els=document.querySelectorAll('[data-ts]');
    for(var i=0;i<els.length;i++){{
      var ms=els[i].getAttribute('data-ts');
      if(!ms) continue;
      var s=els[i].classList.contains('ltime') ? rel(ms,en) : abs(ms);
      if(s) els[i].textContent=s;
    }}
  }}
  // 双语:中文系统显示中文,其余显示英文;可点右上角按钮手动切换并记忆
  function applyLang(en){{
    document.documentElement.setAttribute('data-lang', en?'en':'zh');
    document.documentElement.setAttribute('lang', en?'en':'zh');
    var ns=document.querySelectorAll('.i18n');
    for(var k=0;k<ns.length;k++){{
      var v=ns[k].getAttribute(en?'data-en':'data-zh');
      if(v!=null) ns[k].textContent=v;
    }}
    document.title = en ? '2026 World Cup · Report' : '2026世界杯 · 战报';
    var b=document.getElementById('langitem');
    if(b) b.textContent = en ? '中文' : 'EN';
    renderTimes(en);  // 日期用词随语言切换(今天<->Today)
  }}
  var navl=(navigator.languages&&navigator.languages[0])||navigator.language||'';
  var saved=null; try{{saved=localStorage.getItem('wc_lang');}}catch(e){{}}
  var en0 = saved ? (saved==='en') : !/^zh/i.test(navl);
  applyLang(en0);
  // 右上角菜单:刷新 / 分享 / 中英切换
  function setLang(en){{ try{{localStorage.setItem('wc_lang', en?'en':'zh');}}catch(e){{}} applyLang(en); }}
  var SHARE_URL='https://worldcup-ata.pages.dev/';
  function doShare(item){{
    var isEn=document.documentElement.getAttribute('data-lang')==='en';
    var lab=item.querySelector('.i18n');
    function flash(msg){{ if(!lab) return; lab.textContent=msg;
      setTimeout(function(){{ var en=document.documentElement.getAttribute('data-lang')==='en';
        lab.textContent=lab.getAttribute(en?'data-en':'data-zh'); }},2400); }}
    var ok=isEn?'Copied — paste in WeChat':'已复制·去微信粘贴';
    if(navigator.clipboard&&navigator.clipboard.writeText){{
      navigator.clipboard.writeText(SHARE_URL).then(function(){{ flash(ok); }})
        .catch(function(){{ window.prompt(isEn?'Copy this link':'复制此链接', SHARE_URL); }});
    }} else {{ window.prompt(isEn?'Copy this link':'复制此链接', SHARE_URL); }}
  }}
  var menubtn=document.getElementById('menubtn'), menu=document.getElementById('menu');
  function closeMenu(){{ if(menu){{ menu.hidden=true; menubtn.setAttribute('aria-expanded','false'); }} }}
  // ——比赛结束提醒(本步:请求权限+弹本地测试通知验证;真·推送的订阅+发送是下一步)——
  function notifSupported(){{ return ('serviceWorker' in navigator)&&('Notification' in window)&&('PushManager' in window); }}
  function setNotifLabel(){{
    var it=document.getElementById('notifyitem'); if(!it) return;
    var en=document.documentElement.getAttribute('data-lang')==='en';
    if(!notifSupported()){{ it.textContent=en?'🔔 Alerts (unsupported)':'🔔 提醒·此设备不支持'; return; }}
    var p=Notification.permission;
    it.textContent = p==='granted' ? (en?'🔔 Alerts on ✓':'🔔 提醒已开启 ✓')
      : p==='denied' ? (en?'🔔 Alerts blocked':'🔔 提醒被拒·去设置开')
      : (en?'🔔 Enable alerts':'🔔 开启提醒');
  }}
  var VAPID_PUBLIC='BI85gnNmqaBPjzRpCqRl3_Q26imy4fT59ThO6izSt02L8gyyFQ3XKiyvjMtBG2BR6tXXFrix4-adtlIf4J9WZHA';
  var PUSH_API='https://worldcup-push.bluebay33.workers.dev';
  function urlB64ToU8(b){{
    var pad='='.repeat((4-b.length%4)%4);
    var s=(b+pad).replace(/-/g,'+').replace(/_/g,'/');
    var raw=atob(s), u=new Uint8Array(raw.length);
    for(var i=0;i<raw.length;i++) u[i]=raw.charCodeAt(i);
    return u;
  }}
  function enableNotify(){{
    var en=document.documentElement.getAttribute('data-lang')==='en';
    if(!notifSupported()){{ alert(en?'This device does not support push.':'此设备不支持通知'); return; }}
    if(Notification.permission==='denied'){{ alert(en?'Blocked — enable in settings.':'通知被拒,要去手机设置里手动允许'); return; }}
    Notification.requestPermission().then(function(perm){{
      setNotifLabel();
      if(perm!=='granted') return;
      navigator.serviceWorker.ready.then(function(reg){{
        return reg.pushManager.getSubscription().then(function(ex){{
          return ex || reg.pushManager.subscribe({{ userVisibleOnly:true, applicationServerKey: urlB64ToU8(VAPID_PUBLIC) }});
        }}).then(function(sub){{
          return fetch(PUSH_API+'/subscribe', {{ method:'POST', headers:{{'Content-Type':'application/json'}}, body: JSON.stringify(sub) }});
        }}).then(function(r){{
          if(r.ok){{ reg.showNotification(en?'✅ Alerts on':'✅ 提醒已开启', {{ body: en?'Match results will be pushed here.':'比赛结束时,赛果会推到这里', icon:'icon-192.png', tag:'wc-test' }}); }}
          else {{ alert((en?'Subscribe failed: ':'订阅失败: ')+r.status); }}
        }});
      }}).catch(function(err){{ alert((en?'Error: ':'出错: ')+(err&&err.message||err)); }});
    }});
  }}
  if(menubtn&&menu){{
    menubtn.addEventListener('click', function(e){{
      e.stopPropagation();
      var willOpen=menu.hidden; menu.hidden=!willOpen;
      menubtn.setAttribute('aria-expanded', willOpen?'true':'false');
      if(willOpen) setNotifLabel();
    }});
    menu.addEventListener('click', function(e){{
      var it=e.target.closest('.menu-item'); if(!it) return;
      var act=it.getAttribute('data-act');
      if(act==='refresh'){{ location.reload(); return; }}
      if(act==='share'){{ doShare(it); setTimeout(closeMenu,1600); return; }}
      if(act==='notify'){{ enableNotify(); closeMenu(); return; }}
      if(act==='lang'){{ setLang(document.documentElement.getAttribute('data-lang')!=='en'); closeMenu(); }}
    }});
    document.addEventListener('click', function(e){{
      if(!menu.hidden && !menubtn.contains(e.target) && !menu.contains(e.target)) closeMenu();
    }});
  }}
  // 注册极简 service worker,让本站可被「安装」为独立 APP(强制手机版渲染,无视桌面版开关)
  if('serviceWorker' in navigator){{
    navigator.serviceWorker.register('sw.js').catch(function(){{}});
  }}
}})();
</script>
<script>
/* 最近战果框内的 tab 切换:最近 <-> HISTORY(全部已赛) */
(function(){{
  var tabs=document.querySelectorAll('.rtab');
  for(var i=0;i<tabs.length;i++){{
    tabs[i].addEventListener('click', function(){{
      var box=this.closest('.sec-body'); if(!box) return;
      var key=this.getAttribute('data-rp');
      var bs=box.querySelectorAll('.rtab');
      for(var j=0;j<bs.length;j++) bs[j].classList.toggle('on', bs[j].getAttribute('data-rp')===key);
      var ps=box.querySelectorAll('.rpanel');
      for(var k=0;k<ps.length;k++) ps[k].hidden = (ps[k].getAttribute('data-rp')!==key);
    }});
  }}
}})();
</script>
<script>
/* HISTORY 列表行点击展开/收起(不依赖 <details>) */
(function(){{
  function toggle(line){{
    var row=line.parentNode; if(!row||row.className.indexOf('ml-row')<0) return;
    var body=row.querySelector('.ml-body'); if(!body) return;
    var open=!row.classList.contains('open');
    row.classList.toggle('open', open);
    body.hidden=!open;
  }}
  var lines=document.querySelectorAll('.ml-line');
  for(var i=0;i<lines.length;i++){{
    lines[i].addEventListener('click', function(){{ toggle(this); }});
    lines[i].addEventListener('keydown', function(e){{
      if(e.key==='Enter'||e.key===' '){{ e.preventDefault(); toggle(this); }}
    }});
  }}
}})();
</script>
<script>
/* HISTORY 排序:时间 / 国家(主队为主、客队为次, A-Z) / 胜方进球。再点同一项切换升降序。 */
(function(){{
  function cmp(a,b){{ return a<b?-1:a>b?1:0; }}
  function sortList(list, key, dir){{
    var rows=Array.prototype.slice.call(list.children);
    rows.sort(function(a,b){{
      var r;
      if(key==='ts') r=Number(a.dataset.sts||0)-Number(b.dataset.sts||0);
      else if(key==='wg') r=Number(a.dataset.wg||-1)-Number(b.dataset.wg||-1);
      else {{ // country：主队名，相同再比客队名(不分大小写)
        r=cmp((a.dataset.h||'').toLowerCase(),(b.dataset.h||'').toLowerCase());
        if(r===0) r=cmp((a.dataset.a||'').toLowerCase(),(b.dataset.a||'').toLowerCase());
      }}
      return dir==='desc'?-r:r;
    }});
    for(var i=0;i<rows.length;i++) list.appendChild(rows[i]);
  }}
  var bars=document.querySelectorAll('.mlsort');
  for(var i=0;i<bars.length;i++){{(function(bar){{
    var list=bar.parentNode.querySelector('.ml-list'); if(!list) return;
    var btns=bar.querySelectorAll('.sortb');
    function paint(){{
      for(var j=0;j<btns.length;j++){{
        var on=btns[j].classList.contains('on');
        var old=btns[j].querySelector('.ar'); if(old) old.remove();
        if(on){{ var s=document.createElement('span'); s.className='ar';
          s.textContent=btns[j].getAttribute('data-dir')==='desc'?'↓':'↑'; btns[j].appendChild(s); }}
      }}
    }}
    for(var j=0;j<btns.length;j++){{
      btns[j].addEventListener('click', function(){{
        var wasOn=this.classList.contains('on');
        if(wasOn){{ // 已激活 -> 切换升降序
          this.setAttribute('data-dir', this.getAttribute('data-dir')==='desc'?'asc':'desc');
        }} else {{
          for(var k=0;k<btns.length;k++) btns[k].classList.remove('on');
          this.classList.add('on');
        }}
        paint();
        sortList(list, this.getAttribute('data-k'), this.getAttribute('data-dir'));
      }});
    }}
    paint(); // 初始显示默认排序(时间↓)的箭头
  }})(bars[i]);}}
}})();
</script>
<script>
/* 自动/手动刷新:数据每小时由后台重建并部署。检测线上 data.json 的 lastUpdatedTs 是否更新,
   有新数据才刷(没变就不刷,不丢滚动位置)。切回前台/后台直接刷;正在看时弹"点击刷新"小条不打断。
   手动:右上角 ↻ 按钮 / 电脑 F5,直接重载。 */
(function(){{
  var SELF = {meta.get('lastUpdatedTs', 0) or 0};
  function check(cb){{
    fetch('data.json?_=' + (new Date()).getTime(), {{cache: 'no-store'}})
      .then(function(r){{ return r.json(); }})
      .then(function(d){{ var t = d && d.meta && d.meta.lastUpdatedTs; cb(!!(t && t > SELF)); }})
      .catch(function(){{ cb(false); }});
  }}
  function pill(){{
    if(document.getElementById('rfpill')) return;
    var en = document.documentElement.getAttribute('data-lang') === 'en';
    var b = document.createElement('button');
    b.id = 'rfpill'; b.className = 'rfpill';
    b.textContent = en ? '↻ New data — tap to refresh' : '↻ 有新数据 · 点击刷新';
    b.onclick = function(){{ location.reload(); }};
    document.body.appendChild(b);
  }}
  document.addEventListener('visibilitychange', function(){{
    if(!document.hidden) check(function(n){{ if(n) location.reload(); }});
  }});
  setInterval(function(){{
    check(function(n){{ if(n){{ if(document.hidden) location.reload(); else pill(); }} }});
  }}, 1800000);  // 30 分钟
  // 手动刷新已并入右上角菜单(菜单的"刷新"项 location.reload());电脑 F5 照常。
}})();
</script>
<script>
/* 集锦地区分发:按读者所在国(Cloudflare /cdn-cgi/trace)把链接换成 TSN(加拿大)/FOX(美国)/
   百度搜索(中国大陆,YouTube 用不了)。其它地区保持默认 href=YouTube 搜索链接。纯前端,无需 Worker。 */
(function(){{
  fetch('/cdn-cgi/trace').then(function(r){{return r.text();}}).then(function(t){{
    var m=t.match(/loc=([A-Za-z]+)/); var loc=m?m[1].toUpperCase():'';
    var ls=document.querySelectorAll('a[data-hl-search]');
    for(var i=0;i<ls.length;i++){{
      var a=ls[i], ca=a.getAttribute('data-hl-ca'), us=a.getAttribute('data-hl-us'),
          cn=a.getAttribute('data-hl-cn');
      if(loc==='CA'&&ca){{ a.href=ca; }}
      else if(loc==='US'&&us){{ a.href=us; }}
      else if(loc==='CN'&&cn){{ a.href=cn; }}
    }}
  }}).catch(function(){{}});
}})();
</script>
<script>{live_js}</script>
</body>
</html>"""

    with open(OUT, "w", encoding="utf-8") as f:
        f.write(page)
    # 同时写一份 index.html，方便静态服务/直接预览
    with open(os.path.join(HERE, "index.html"), "w", encoding="utf-8") as f:
        f.write(page)
    print(f"已生成 {OUT}")


if __name__ == "__main__":
    build()
