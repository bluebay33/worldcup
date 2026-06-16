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

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data.json")
OUT = os.path.join(HERE, "report.html")


def esc(s):
    return html.escape(str(s))


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
        if m.get("hs") is None or m.get("as") is None:
            continue  # 未赛，不计入
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
        t = m.get("time", "")
        return f'<span class="vs">{esc(t)} vs</span>' if t else '<span class="vs">vs</span>'
    return f'<span class="score">{m["hs"]} : {m["as"]}</span>'


def match_row(m, show_group=False):
    grp = f'<span class="tag">{esc(m["group"])}</span> ' if show_group and m.get("group") else ""
    status = m.get("status", "")
    badge = ""
    if status == "FT":
        badge = '<span class="badge ft">完场</span>'
    elif status == "LIVE":
        badge = '<span class="badge live">进行中</span>'
    elif status == "sched":
        badge = '<span class="badge sched">未开赛</span>'
    _city = city_cn(m.get("city", ""))
    _vname = m.get("venue", "")
    _loc = f"{_city} · {_vname}" if (_city and _vname) else (_city or _vname)
    venue = f'<span class="venue">{esc(_loc)}</span>' if _loc else ""
    dt = esc(m.get("date", "")) + (" " + esc(m["time"]) if m.get("time") else "")
    return f"""<div class="match">
      <div class="m-date">{grp}{dt}</div>
      <div class="m-home">{esc(cn(m["home"]))}</div>
      <div class="m-score">{score_cell(m)}</div>
      <div class="m-away">{esc(cn(m["away"]))}</div>
      <div class="m-meta">{badge}{venue}</div>
      {goals_html(m)}{videos_html(m)}
    </div>"""


def _goal_mark(t):
    t = t or ""
    if "Penalty" in t:
        return "(点球)"
    if "Own" in t:
        return "(乌龙)"
    if "Header" in t:
        return "(头球)"
    return ""


def goals_html(m):
    goals = m.get("goals") or []
    if not goals:
        return ""
    parts = []
    for g in goals:
        nm = g.get("scorer") or "?"
        team = cn(g.get("team", ""))
        parts.append(f'<span class="gitem">{esc(g.get("min", ""))} {esc(nm)}{_goal_mark(g.get("type"))}'
                     f'<span class="gteam">{esc(team)}</span></span>')
    return '<div class="m-goals">⚽ ' + "".join(parts) + "</div>"


def videos_html(m):
    vids = m.get("videos") or []
    if not vids:
        return ""
    links = "".join(
        f'<a class="vlink" href="{esc(v.get("url", ""))}" target="_blank" rel="noopener">▶ {esc((v.get("title") or "视频")[:26])}</a>'
        for v in vids)
    return f'<div class="m-videos">{links}</div>'


def group_block(group):
    table = compute_table(group)
    name = group["name"]
    trs = []
    for i, r in enumerate(table):
        cls = "qualify" if i < 2 else ""  # 前两名晋级高亮
        gd = r["gf"] - r["ga"]
        gd_s = f"+{gd}" if gd > 0 else str(gd)
        trs.append(f"""<tr class="{cls}">
          <td class="rank">{i+1}</td>
          <td class="tname">{esc(cn(r['team']))}</td>
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
        body = (f'<details class="g-details"><summary>比赛详情 · {n} 场</summary>'
                f'<div class="g-matches">{matches_html}</div></details>')
    else:
        body = '<div class="empty">暂无比赛</div>'
    return f"""<section class="group">
      <h3>小组 {esc(name)}</h3>
      <table class="standings">
        <thead><tr>
          <th>#</th><th class="tname">球队</th><th>赛</th><th>胜</th><th>平</th>
          <th>负</th><th>进</th><th>失</th><th>净</th><th>分</th>
        </tr></thead>
        <tbody>{''.join(trs)}</tbody>
      </table>
      {body}
    </section>"""


def build():
    with open(DATA, "r", encoding="utf-8") as f:
        data = json.load(f)
    meta = data.get("meta", {})

    groups_html = "".join(group_block(g) for g in data.get("groups", []))
    if not groups_html:
        groups_html = '<div class="empty">小组数据待补全</div>'

    # 近期赛程：未来 48 小时内要踢的（北京时间）。候选含小组赛 sched + fixtures 数组 + 淘汰赛 sched。
    BJT = timezone(timedelta(hours=8))

    def _mdt(m):
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
        fix_label = "未来 48 小时"
    else:
        # 当前时段没有 48h 内的比赛，退而显示最近即将开赛的 8 场
        upcoming = [m for dt, m in win if dt is not None and dt >= now][:8]
        fix_label = "即将开赛"
    fixtures_html = ""
    if upcoming:
        fixtures_html = ('<section class="fixtures hero">'
                         f'<h2>🔥 近期赛程 · {fix_label} <span class="cnt">{len(upcoming)} 场</span>'
                         '<span style="font-size:13px;color:var(--muted);font-weight:400;">（时间为北京时间）</span>'
                         '</h2><div class="fix-grid">')
        fixtures_html += "".join(match_row(m, show_group=True) for m in upcoming)
        fixtures_html += "</div></section>"

    # 最近战果（已赛）：取「最近 6 场」与「最近 24 小时内」中数量更多的一组，时间倒序展示。
    played_pool = []
    for g in data.get("groups", []):
        for m in g.get("matches", []):
            if m.get("status") == "FT" and m.get("hs") is not None:
                mm = dict(m); mm["group"] = g["name"]; played_pool.append(mm)
    for m in data.get("knockout", []):
        if m.get("status") == "FT" and m.get("hs") is not None:
            mm = dict(m); mm.setdefault("group", "淘汰赛"); played_pool.append(mm)
    _far = datetime.min.replace(tzinfo=BJT)
    played_desc = sorted(played_pool, key=lambda m: (_mdt(m) or _far), reverse=True)
    last6 = played_desc[:6]
    last24 = [m for m in played_desc if _mdt(m) and (now - timedelta(hours=24)) <= _mdt(m) <= now]
    if len(last24) > len(last6):
        recent, recent_label = last24, "最近 24 小时"
    else:
        recent, recent_label = last6, "最近 6 场"
    recent_html = ""
    if recent:
        recent_html = ('<section class="results hero">'
                       f'<h2>🏁 最近战果 · {recent_label} <span class="cnt">{len(recent)} 场</span>'
                       '<span style="font-size:13px;color:var(--muted);font-weight:400;">（时间为北京时间）</span>'
                       '</h2><div class="fix-grid">')
        recent_html += "".join(match_row(m, show_group=True) for m in recent)
        recent_html += "</div></section>"

    # 球员进球榜：汇总各场进球者（乌龙球不计个人）。
    scorers = {}

    def _collect_goals(matches):
        for mm in matches:
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
        rows = []
        for i, r in enumerate(top[:20]):
            pen = f'<span class="pen">含{r["pens"]}点</span>' if r["pens"] else ""
            rows.append(f'<tr><td class="rank">{i+1}</td>'
                        f'<td class="tname">{esc(r["name"])}{pen}</td>'
                        f'<td>{esc(cn(r["team"]))}</td><td class="pts">{r["goals"]}</td></tr>')
        more = (f'<div class="more">仅显示前 20 名，共 {len(top)} 名球员有进球</div>'
                if len(top) > 20 else "")
        scorers_html = ('<section class="scorers"><h2>⚽ 球员进球榜</h2>'
                        '<table class="scoretable"><thead><tr><th>#</th>'
                        '<th class="tname">球员</th><th>球队</th><th>进球</th></tr></thead>'
                        '<tbody>' + "".join(rows) + '</tbody></table>' + more + '</section>')

    knockout = data.get("knockout", [])
    knockout_html = ""
    if knockout:
        knockout_html = '<section class="knockout"><h2>淘汰赛</h2><div class="fix-grid">'
        knockout_html += "".join(match_row(m, show_group=True) for m in knockout)
        knockout_html += "</div></section>"
    else:
        knockout_html = '<section class="knockout"><h2>淘汰赛</h2><div class="empty">小组赛进行中，淘汰赛对阵未产生</div></section>'

    sources = " · ".join(esc(s) for s in meta.get("sources", []))
    built_at = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")

    page = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(meta.get('tournament','世界杯'))} · 战报</title>
<style>
  :root {{
    --bg:#0f1419; --card:#1a212b; --line:#2a3441; --txt:#e6edf3;
    --muted:#8b98a5; --accent:#3fb950; --gold:#d4a017; --live:#f85149;
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--txt);
    font-family:-apple-system,"Segoe UI","Microsoft YaHei",sans-serif; line-height:1.5; }}
  .wrap {{ max-width:1100px; margin:0 auto; padding:24px 16px 60px; }}
  header.top {{ border-bottom:2px solid var(--line); padding-bottom:16px; margin-bottom:24px; }}
  header.top h1 {{ margin:0 0 6px; font-size:28px; }}
  .sub {{ color:var(--muted); font-size:13px; display:flex; flex-wrap:wrap; gap:6px 16px; }}
  .sub b {{ color:var(--txt); font-weight:600; }}
  .notes {{ background:#1c2733; border-left:3px solid var(--gold); padding:10px 14px;
    border-radius:0 6px 6px 0; margin-top:14px; font-size:13px; color:var(--muted); }}
  h2 {{ font-size:20px; margin:32px 0 14px; padding-left:10px; border-left:4px solid var(--accent); }}
  .groups {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(330px,1fr)); gap:18px; }}
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
  .m-meta {{ grid-column:2 / -1; display:flex; gap:8px; align-items:center; }}
  .badge {{ font-size:10px; padding:1px 6px; border-radius:10px; }}
  .badge.ft {{ background:#21262d; color:var(--muted); }}
  .badge.live {{ background:rgba(248,81,73,0.15); color:var(--live); }}
  .badge.sched {{ background:rgba(212,160,23,0.15); color:var(--gold); }}
  .venue {{ color:var(--muted); font-size:11px; }}
  .tag {{ background:#21262d; color:var(--muted); padding:0 5px; border-radius:4px; font-size:10px; }}
  .m-goals {{ grid-column:1 / -1; font-size:12px; color:var(--txt); display:flex; flex-wrap:wrap;
    gap:6px 12px; padding:4px 2px 0; }}
  .gitem {{ color:#cdd6e0; }}
  .gteam {{ color:var(--muted); font-size:10.5px; margin-left:3px; }}
  .m-videos {{ grid-column:1 / -1; display:flex; flex-wrap:wrap; gap:6px 10px; padding:4px 2px 0; }}
  .vlink {{ color:var(--accent); font-size:11px; text-decoration:none; border:1px solid #2f4636;
    padding:1px 7px; border-radius:10px; }}
  .vlink:hover {{ background:rgba(63,185,80,0.12); }}
  .scorers {{ margin-top:18px; }}
  table.scoretable {{ width:100%; max-width:560px; border-collapse:collapse; font-size:13px;
    background:var(--card); border:1px solid var(--line); border-radius:10px; overflow:hidden; }}
  table.scoretable th {{ color:var(--muted); font-weight:500; text-align:center; padding:8px 6px; border-bottom:1px solid var(--line); }}
  table.scoretable td {{ text-align:center; padding:7px 6px; border-bottom:1px solid #222c38; }}
  table.scoretable td.tname {{ text-align:left; }}
  table.scoretable td.pts {{ font-weight:700; color:var(--accent); }}
  .pen {{ color:var(--muted); font-size:10.5px; margin-left:6px; }}
  .more {{ color:var(--muted); font-size:12px; margin-top:8px; }}
  .fix-grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(300px,1fr)); gap:8px; }}
  .fix-grid .match {{ background:var(--card); border:1px solid var(--line); padding:10px 12px; }}
  .fixtures.hero {{ background:linear-gradient(180deg,#1c2a22,#161d27); border:1px solid var(--accent);
    border-radius:12px; padding:14px 18px 18px; margin-bottom:10px; box-shadow:0 0 0 3px rgba(63,185,80,0.08); }}
  .fixtures.hero h2 {{ margin:4px 0 14px; border-left-color:var(--gold); display:flex; align-items:center; gap:10px; flex-wrap:wrap; }}
  .fixtures.hero .cnt {{ background:var(--accent); color:#06210f; font-size:13px; font-weight:700;
    padding:1px 9px; border-radius:10px; }}
  .fixtures.hero .fix-grid .match {{ background:#10171f; border-color:#2f4636; }}
  .results.hero {{ background:linear-gradient(180deg,#2a2418,#161d27); border:1px solid var(--gold);
    border-radius:12px; padding:14px 18px 18px; margin-bottom:10px; box-shadow:0 0 0 3px rgba(212,160,23,0.08); }}
  .results.hero h2 {{ margin:4px 0 14px; border-left-color:var(--gold); display:flex; align-items:center; gap:10px; flex-wrap:wrap; }}
  .results.hero .cnt {{ background:var(--gold); color:#211900; font-size:13px; font-weight:700;
    padding:1px 9px; border-radius:10px; }}
  .results.hero .fix-grid .match {{ background:#10171f; border-color:#463a2f; }}
  .empty {{ color:var(--muted); font-size:13px; padding:16px; text-align:center;
    background:var(--card); border:1px dashed var(--line); border-radius:8px; }}
  footer {{ margin-top:40px; padding-top:16px; border-top:1px solid var(--line);
    color:var(--muted); font-size:12px; text-align:center; }}
</style>
</head>
<body>
<div class="wrap">
  <header class="top">
    <h1>⚽ {esc(meta.get('tournament','世界杯'))} 战报</h1>
    <div class="sub">
      <span>主办：<b>{esc(meta.get('host',''))}</b></span>
      <span>数据更新：<b>{esc(meta.get('lastUpdated',''))}</b></span>
    </div>
  </header>

  {recent_html}

  {fixtures_html}

  <h2>小组积分榜</h2>
  <div class="groups">{groups_html}</div>

  {scorers_html}

  {knockout_html}

  <footer>页面生成于 {built_at} · 绿色行为小组前两名（晋级区）· 数据自动推算自比赛结果</footer>
</div>
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
