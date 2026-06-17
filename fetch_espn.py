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
import re
import time
import unicodedata
import urllib.request
from urllib.parse import quote_plus
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data.json")
GROUPS_CACHE = os.path.join(HERE, "groups_cache.json")

SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard?dates={}"
STANDINGS = "https://site.web.api.espn.com/apis/v2/sports/soccer/fifa.world/standings?season=2026"
SUMMARY = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/summary?event={}"

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


def to_ms(iso):
    """ESPN UTC ISO -> epoch 毫秒(UTC)；供浏览器按读者本地时区显示。无法解析返回 None。"""
    s = (iso or "").replace("Z", "+00:00")
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M%z"):
        try:
            return int(datetime.strptime(s, fmt).timestamp() * 1000)
        except ValueError:
            continue
    return None


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
    ts = to_ms(e.get("date", ""))
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
        "date": date, "time": t, "ts": ts,
        "home": home[0], "away": away[0],
        "hs": hs, "as": as_,
        "status": status, "venue": venue, "city": city,
    }


def fetch_match_detail(event_id):
    """对已结束比赛，抓进球者名单(participants)和 ESPN 赛事视频。返回 (goals, videos)。"""
    goals, vids = [], []
    if not event_id:
        return goals, vids
    try:
        s = get_json(SUMMARY.format(event_id), retries=3)
    except Exception as ex:
        print(f"[warn] summary {event_id} 失败：", repr(ex))
        return goals, vids
    for k in s.get("keyEvents", []):
        if not k.get("scoringPlay"):
            continue
        parts = k.get("participants") or []
        scorer = (parts[0].get("athlete") or {}).get("displayName") if parts else None
        assist = (parts[1].get("athlete") or {}).get("displayName") if len(parts) > 1 else None
        goals.append({
            "min": (k.get("clock") or {}).get("displayValue", ""),
            "scorer": scorer,
            "assist": assist,
            "type": (k.get("type") or {}).get("text", ""),
            "team": (k.get("team") or {}).get("displayName", ""),
        })
    for v in (s.get("videos") or [])[:3]:
        href = ((v.get("links") or {}).get("source") or {}).get("href")
        if href:
            vids.append({"title": v.get("headline", ""), "url": href})
    return goals, vids


def _norm(s):
    """小写 + 去音标(Curaçao->curacao, Türkiye->turkiye),便于匹配。"""
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).lower()

# ESPN 数据队名 与 FIFA 标题队名 无词重叠的，给别名(其余靠去音标/共同词即可)
_TEAM_ALIAS = {
    "united states": ["usa", "united states"],
    "ivory coast": ["cote", "ivoire", "ivory coast"],
}
_STOP = {"and", "the", "of", "dr", "fc", "ir", "republic"}


def _team_tokens(name):
    al = _TEAM_ALIAS.get(_norm(name))
    if al:
        return al
    words = [w for w in re.split(r"[\s'\-]+", _norm(name)) if len(w) >= 3 and w not in _STOP]
    return words or [_norm(name)]


def _relevant(title, home, away):
    """标题是否同时提到主、客两队(去音标后子串匹配)。"""
    t = _norm(title)
    h = any(tok in t for tok in _team_tokens(home))
    a = any(tok in t for tok in _team_tokens(away))
    return h and a


# 发布者可信度(越靠前越优先):FIFA 官方 > 官方转播商 > 其它
_TRUSTED = ["fifa", "tsn", "fox soccer", "fox sports", "cbs sports", "telemundo", "itv", "bbc sport"]


def _pub_rank(channel):
    c = _norm(channel)
    for i, name in enumerate(_TRUSTED):
        if name in c:
            return i
    return len(_TRUSTED)   # 非可信发布者排最后(仍保留,作兜底)


def fetch_youtube_highlight(home, away):
    """搜 '队名A 队名B highlights world cup 2026'（不带比分——带比分会搜到蹭标题的二次上传），
    取官方集锦：优先 FIFA 官方频道，否则取首条。返回 {'url','title'} 或 None。"""
    q = f"{home} {away} highlights world cup 2026"
    url = "https://www.youtube.com/results?search_query=" + quote_plus(q) + "&hl=en&gl=US"
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
            "Accept-Language": "en-US,en;q=0.9",
            "Cookie": "CONSENT=YES+1",
        })
        with urllib.request.urlopen(req, timeout=20) as r:
            h = r.read().decode("utf-8", "ignore")
    except Exception as ex:
        print(f"[warn] youtube 搜索失败 {home}-{away}:", repr(ex))
        return None
    items = re.findall(
        r'"videoRenderer":\{"videoId":"([\w-]{11})".*?"title":\{"runs":\[\{"text":"([^"]+)"'
        r'.*?(?:"ownerText"|"longBylineText"):\{"runs":\[\{"text":"([^"]+)"', h)
    if not items:
        return None

    def clean(t):
        return t.replace("\\u0026", "&").replace("\\u003d", "=").replace("\\/", "/")

    def watch(vid, title, ch):
        c = clean(ch).split("•")[0].split("\\n")[0].strip()   # 去掉 "• 1.1M views • ..." 等附加
        return {"url": f"https://www.youtube.com/watch?v={vid}",
                "title": clean(title), "channel": c}

    # 候选必须含「完整关键字」:主客两队 + fifa + world cup + 2026 + highlight,且非 shorts。
    # 挡掉:蹭队名的动画/预测、直播/预告、资格赛、单球、老世界杯重传、某队的另一场等。
    def _ok(title):
        t = _norm(title)
        return (_relevant(title, home, away)
                and "fifa" in t
                and ("world cup" in t or "worldcup" in t)
                and "2026" in t
                and "highlight" in t
                and "shorts" not in t)

    cands = [(vid, title, ch) for vid, title, ch in items if _ok(title)]
    if not cands:
        return None                                    # 没有合格的 -> build.py 退回搜索链接
    # 按发布者可信度排序(稳定排序:同级保持原相关性顺序);FIFA>TSN等官方转播>其它
    cands.sort(key=lambda c: _pub_rank(c[2]))
    return watch(*cands[0])


def main():
    groups_order, team2group = fetch_groups()
    events = fetch_events()
    print(f"[info] 拉到 {len(events)} 场比赛、{len(groups_order)} 个组")

    # 复用上次已找到的 YouTube 集锦链接（避免每次重抓、云端被拦时仍有上次结果）
    prev_hl = {}
    if os.path.exists(DATA):
        try:
            old = json.load(open(DATA, encoding="utf-8"))
            allm = [mm for g in old.get("groups", []) for mm in g.get("matches", [])] + old.get("knockout", [])
            for mm in allm:
                if mm.get("highlight"):
                    prev_hl[(mm.get("home"), mm.get("away"), mm.get("date"))] = mm["highlight"]
        except Exception:
            pass

    # 按组装配 matches；跨组进 knockout。已结束比赛额外抓进球者名单+视频+集锦。
    gmatches = {g["name"]: [] for g in groups_order}
    knockout = []
    detail_n = 0
    hl_hit = hl_new = 0
    for e in events:
        m = parse_event(e)
        if not m:
            continue
        if m["status"] == "FT":
            goals, vids = fetch_match_detail(e.get("id"))
            if goals:
                m["goals"] = goals
            if vids:
                m["videos"] = vids
            key = (m["home"], m["away"], m["date"])
            if key in prev_hl:
                m["highlight"] = prev_hl[key]; hl_hit += 1
            else:
                hl = fetch_youtube_highlight(m["home"], m["away"])
                if hl:
                    m["highlight"] = hl; hl_new += 1
            detail_n += 1
        gh = team2group.get(m["home"])
        ga = team2group.get(m["away"])
        if gh and ga and gh == ga:
            gmatches[gh].append(m)
        else:
            knockout.append(m)
    print(f"[info] 已为 {detail_n} 场抓进球/视频；集锦链接：复用 {hl_hit}、新抓 {hl_new}")

    for name in gmatches:
        gmatches[name].sort(key=lambda x: (x.get("date", ""), x.get("time", "")))
    knockout.sort(key=lambda x: (x.get("date", ""), x.get("time", "")))

    groups = [{"name": g["name"], "teams": g["teams"],
               "matches": gmatches[g["name"]]} for g in groups_order]

    now_utc = datetime.now(timezone.utc)
    now_bjt = now_utc.astimezone(BJT).strftime("%Y-%m-%d %H:%M") + " (北京时间)"
    data = {
        "meta": {
            "tournament": "2026世界杯",
            "host": "美国 / 加拿大 / 墨西哥",
            "lastUpdated": now_bjt,
            "lastUpdatedTs": int(now_utc.timestamp() * 1000),
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
