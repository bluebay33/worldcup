# -*- coding: utf-8 -*-
"""
从 ESPN 公开 JSON 端点拉取 2026 世界杯真实数据，生成 data.json。

为什么用 ESPN：结构化字段、机器可读、带 UTC 开球时间，不会像 AI 检索摘要那样幻觉。
- 比分/赛程：scoreboard?dates=YYYYMMDD-YYYYMMDD（含 status、UTC date）
- 分组名单：standings?season=2026（12 组，每组 4 队）

输出 data.json 结构与 build.py 对齐：
  meta / groups[{name,teams,matches[{date,time,home,away,hs,as,status,venue}]}] / knockout[]
时间统一转北京时间（UTC+8）。同组两队 -> 小组赛；跨组 -> 淘汰赛。

用法：python fetch_espn.py
"""
import json
import os
import time
import urllib.request
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data.json")
GROUPS_CACHE = os.path.join(HERE, "groups_cache.json")

SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard?dates={}"
STANDINGS = "https://site.web.api.espn.com/apis/v2/sports/soccer/fifa.world/standings?season=2026"

START = datetime(2026, 6, 11).date()
END = datetime(2026, 7, 19).date()
BJT = timezone(timedelta(hours=8))
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def get_json(url, retries=5):
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as ex:
            last = ex
            time.sleep(1.5 * (i + 1))
    raise last


def to_bjt(iso):
    """ESPN UTC ISO（如 2026-06-11T19:00Z）-> (北京日期, 北京HH:MM)。"""
    s = (iso or "").replace("Z", "+00:00")
    dt = None
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M%z"):
        try:
            dt = datetime.strptime(s, fmt)
            break
        except ValueError:
            continue
    if dt is None:
        return "", ""
    b = dt.astimezone(BJT)
    return b.strftime("%Y-%m-%d"), b.strftime("%H:%M")


def map_status(ev):
    name = (ev.get("status", {}).get("type", {}) or {}).get("name", "")
    state = (ev.get("status", {}).get("type", {}) or {}).get("state", "")
    if name in ("STATUS_FULL_TIME", "STATUS_FINAL") or state == "post":
        return "FT"
    if name == "STATUS_SCHEDULED" or state == "pre":
        return "sched"
    return "LIVE"


def fetch_groups():
    """返回 (groups_order, team2group)。失败则回退缓存。"""
    try:
        st = get_json(STANDINGS)
        children = st.get("children", [])
        groups_order = []
        team2group = {}
        for ch in children:
            name = ch.get("name", "")  # "Group A"
            short = name.replace("Group ", "").strip() or name
            entries = (ch.get("standings") or {}).get("entries", [])
            teams = []
            for en in entries:
                tn = en.get("team", {}).get("displayName")
                if tn:
                    teams.append(tn)
                    team2group[tn] = short
            if teams:
                groups_order.append({"name": short, "teams": teams})
        if groups_order:
            with open(GROUPS_CACHE, "w", encoding="utf-8") as f:
                json.dump({"groups_order": groups_order, "team2group": team2group},
                          f, ensure_ascii=False, indent=2)
            return groups_order, team2group
    except Exception as ex:
        print("[warn] standings 拉取失败，尝试缓存：", repr(ex))
    if os.path.exists(GROUPS_CACHE):
        with open(GROUPS_CACHE, "r", encoding="utf-8") as f:
            c = json.load(f)
        return c["groups_order"], c["team2group"]
    raise RuntimeError("standings 拉取失败且无缓存")


def fetch_events():
    """按周分段拉 scoreboard，按 event id 去重。"""
    seen = {}
    d = START
    while d <= END:
        d2 = min(d + timedelta(days=6), END)
        rng = d.strftime("%Y%m%d") + "-" + d2.strftime("%Y%m%d")
        try:
            sb = get_json(SCOREBOARD.format(rng))
            for e in sb.get("events", []):
                seen[e.get("id", e.get("uid", str(len(seen))))] = e
        except Exception as ex:
            print(f"[warn] scoreboard {rng} 失败：", repr(ex))
        d = d2 + timedelta(days=1)
    return list(seen.values())


def parse_event(e):
    comp = (e.get("competitions") or [{}])[0]
    cs = comp.get("competitors", [])
    home = away = None
    for c in cs:
        side = c.get("homeAway")
        name = c.get("team", {}).get("displayName")
        score = c.get("score")
        if side == "home":
            home = (name, score)
        elif side == "away":
            away = (name, score)
    if not home or not away:
        # 兜底：按列表顺序
        if len(cs) == 2:
            home = (cs[0].get("team", {}).get("displayName"), cs[0].get("score"))
            away = (cs[1].get("team", {}).get("displayName"), cs[1].get("score"))
        else:
            return None
    status = map_status(e)
    date, t = to_bjt(e.get("date", ""))
    vobj = comp.get("venue") or {}
    venue = vobj.get("fullName") or ""
    city = (vobj.get("address") or {}).get("city") or ""

    def to_int(s):
        try:
            return int(s)
        except (TypeError, ValueError):
            return None
    hs = to_int(home[1]) if status != "sched" else None
    as_ = to_int(away[1]) if status != "sched" else None
    return {
        "date": date, "time": t,
        "home": home[0], "away": away[0],
        "hs": hs, "as": as_,
        "status": status, "venue": venue, "city": city,
    }


def main():
    groups_order, team2group = fetch_groups()
    events = fetch_events()
    print(f"[info] 拉到 {len(events)} 场比赛、{len(groups_order)} 个组")

    # 按组装配 matches；跨组进 knockout
    gmatches = {g["name"]: [] for g in groups_order}
    knockout = []
    for e in events:
        m = parse_event(e)
        if not m:
            continue
        gh = team2group.get(m["home"])
        ga = team2group.get(m["away"])
        if gh and ga and gh == ga:
            gmatches[gh].append(m)
        else:
            knockout.append(m)

    for name in gmatches:
        gmatches[name].sort(key=lambda x: (x.get("date", ""), x.get("time", "")))
    knockout.sort(key=lambda x: (x.get("date", ""), x.get("time", "")))

    groups = [{"name": g["name"], "teams": g["teams"],
               "matches": gmatches[g["name"]]} for g in groups_order]

    now_bjt = datetime.now(BJT).strftime("%Y-%m-%d %H:%M") + " (北京时间)"
    data = {
        "meta": {
            "tournament": "2026世界杯",
            "host": "美国 / 加拿大 / 墨西哥",
            "lastUpdated": now_bjt,
            "updatedBy": "ESPN 自动拉取",
            "sources": ["ESPN"],
            "notes": "数据来自 ESPN 公开结构化端点，开球时间已转北京时间。比赛结果是唯一事实源，积分榜由 build.py 自动推算（胜3平1负0）。同组两队记小组赛，跨组记淘汰赛。",
        },
        "groups": groups,
        "knockout": knockout,
    }
    with open(DATA, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    played = sum(1 for g in groups for m in g["matches"] if m["status"] == "FT")
    sched = sum(1 for g in groups for m in g["matches"] if m["status"] == "sched")
    print(f"[ok] 已写 data.json：已赛 {played} 场、未赛 {sched} 场、淘汰赛 {len(knockout)} 场")


if __name__ == "__main__":
    main()
