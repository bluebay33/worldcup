# -*- coding: utf-8 -*-
"""按比赛日程 + 集锦状态判断本次是否需要真正刷新(按需刷新,而非盲目定时)。

活跃(需要刷新)条件,任一满足即可:
- 有比赛正在进行(status=LIVE)
- 有比赛将在 90 分钟内开球(开赛前提前进入活跃)
- 有比赛在过去 6 小时内开球(收尾比分)
- 近 30 小时内完赛、但还没抓到 TSN 集锦的比赛(TSN 赛后几小时才发,要持续去抓;抓到就不再算活跃)

数据源:优先拉**线上已部署的 data.json**(含真实状态+集锦),拉不到再回退本地 committed 版。
  这点很重要:仓库里 committed 的 data.json 是旧的(workflow 不回写),只有线上那份反映真实状态。

结果写入 $GITHUB_OUTPUT 的 active=true|false。非定时事件(push/手动)一律强制刷新。
"""
import json
import os
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data.json")
LIVE_URL = "https://worldcup-ata.pages.dev/data.json"

PRE_MS = 90 * 60 * 1000          # 开球前 90 分钟起算活跃
POST_MS = 6 * 3600 * 1000        # 开球后 6 小时内仍活跃(比分收尾)
HILITE_MS = 30 * 3600 * 1000     # 完赛后 30 小时内若仍缺集锦,继续抓(抓到即停;上限防空转)


def all_matches(data):
    for g in data.get("groups", []):
        for m in g.get("matches", []):
            yield m
    for m in data.get("fixtures", []):
        yield m
    for m in data.get("knockout", []):
        yield m


def load_data():
    """优先线上已部署 data.json(真实状态+集锦),失败回退本地 committed。"""
    try:
        req = urllib.request.Request(
            LIVE_URL, headers={"User-Agent": "gate/1.0", "Cache-Control": "no-cache"})
        raw = urllib.request.urlopen(req, timeout=15).read().decode("utf-8")
        return json.loads(raw), "线上"
    except Exception:
        try:
            with open(DATA, "r", encoding="utf-8") as f:
                return json.load(f), "本地committed"
        except Exception:
            return None, "无"


def decide():
    ev = os.environ.get("EVENT_NAME", "")
    if ev and ev != "schedule":
        return True, f"事件 {ev},强制刷新"

    data, src = load_data()
    if data is None:
        return True, "无法读取数据,保守刷新"

    now = int(datetime.now(timezone.utc).timestamp() * 1000)
    near_lo, near_hi = now - POST_MS, now + PRE_MS
    hl_lo = now - HILITE_MS
    for m in all_matches(data):
        if m.get("status") == "LIVE":
            return True, f"有进行中比赛(源={src})"
        ts = m.get("ts") or 0
        if not ts:
            continue
        if near_lo <= ts <= near_hi:
            return True, f"有比赛在比分窗口内(源={src})"
        if hl_lo <= ts <= now and m.get("status") == "FT":
            if not (m.get("highlight") or {}).get("url"):
                return True, f"近期完赛比赛缺集锦,继续抓(源={src})"
    return False, f"无临近比赛、近期完赛均已有集锦(源={src})"


def main():
    active, reason = decide()
    print(f"[gate] active={active} | {reason}")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"active={'true' if active else 'false'}\n")


if __name__ == "__main__":
    main()
