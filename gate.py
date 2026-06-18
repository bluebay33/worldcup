# -*- coding: utf-8 -*-
"""按比赛日程判断本次是否需要真正刷新(按需刷新,而非盲目定时)。

活跃(需要刷新)条件,任一满足即可:
- 有比赛正在进行(status=LIVE)
- 有比赛将在 90 分钟内开球(开赛前提前进入活跃,好及时显示)
- 有比赛在过去 6 小时内开球(收尾比分 + 抓 TSN 集锦)

结果写入 $GITHUB_OUTPUT 的 active=true|false,workflow 用它决定是否跑后续步骤。
非定时事件(push / 手动触发)一律强制刷新。
读不到 data.json 时保守刷新一次。
"""
import json
import os
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data.json")

PRE_MS = 90 * 60 * 1000     # 开球前 90 分钟起算活跃
POST_MS = 6 * 3600 * 1000   # 开球后 6 小时内仍活跃


def all_matches(data):
    for g in data.get("groups", []):
        for m in g.get("matches", []):
            yield m
    for m in data.get("fixtures", []):
        yield m
    for m in data.get("knockout", []):
        yield m


def decide():
    ev = os.environ.get("EVENT_NAME", "")
    if ev and ev != "schedule":
        return True, f"事件 {ev},强制刷新"
    try:
        with open(DATA, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return True, f"data.json 读取失败({e}),保守刷新"

    now = int(datetime.now(timezone.utc).timestamp() * 1000)
    lo, hi = now - POST_MS, now + PRE_MS
    for m in all_matches(data):
        if m.get("status") == "LIVE":
            return True, "有进行中比赛"
        ts = m.get("ts") or 0
        if ts and lo <= ts <= hi:
            mins = round((ts - now) / 60000)
            return True, f"有比赛在窗口内(距开球 {mins} 分钟)"
    return False, "无临近比赛,跳过本次刷新"


def main():
    active, reason = decide()
    print(f"[gate] active={active} | {reason}")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"active={'true' if active else 'false'}\n")


if __name__ == "__main__":
    main()
