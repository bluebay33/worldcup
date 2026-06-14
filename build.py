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
import html
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data.json")
OUT = os.path.join(HERE, "report.html")


def esc(s):
    return html.escape(str(s))


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
    venue = f'<span class="venue">{esc(m["venue"])}</span>' if m.get("venue") else ""
    return f"""<div class="match">
      <div class="m-date">{grp}{esc(m.get("date",""))}</div>
      <div class="m-home">{esc(m["home"])}</div>
      <div class="m-score">{score_cell(m)}</div>
      <div class="m-away">{esc(m["away"])}</div>
      <div class="m-meta">{badge}{venue}</div>
    </div>"""


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
          <td class="tname">{esc(r['team'])}</td>
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
    return f"""<section class="group">
      <h3>小组 {esc(name)}</h3>
      <table class="standings">
        <thead><tr>
          <th>#</th><th class="tname">球队</th><th>赛</th><th>胜</th><th>平</th>
          <th>负</th><th>进</th><th>失</th><th>净</th><th>分</th>
        </tr></thead>
        <tbody>{''.join(trs)}</tbody>
      </table>
      <div class="g-matches">{matches_html or '<div class="empty">暂无比赛</div>'}</div>
    </section>"""


def build():
    with open(DATA, "r", encoding="utf-8") as f:
        data = json.load(f)
    meta = data.get("meta", {})

    groups_html = "".join(group_block(g) for g in data.get("groups", []))
    if not groups_html:
        groups_html = '<div class="empty">小组数据待补全</div>'

    fixtures = data.get("fixtures", [])
    fixtures_html = ""
    if fixtures:
        fixtures_html = '<section class="fixtures"><h2>近期赛程 / 进行中</h2><div class="fix-grid">'
        fixtures_html += "".join(match_row(m, show_group=True) for m in fixtures)
        fixtures_html += "</div></section>"

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
  .g-matches {{ margin-top:10px; display:flex; flex-direction:column; gap:4px; }}
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
  .fix-grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(300px,1fr)); gap:8px; }}
  .fix-grid .match {{ background:var(--card); border:1px solid var(--line); padding:10px 12px; }}
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
      <span>数据更新：<b>{esc(meta.get('lastUpdated',''))}</b>（{esc(meta.get('updatedBy',''))}）</span>
      <span>来源：{sources}</span>
    </div>
    {'<div class="notes">' + esc(meta.get('notes','')) + '</div>' if meta.get('notes') else ''}
  </header>

  {fixtures_html}

  <h2>小组积分榜</h2>
  <div class="groups">{groups_html}</div>

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
