// worldcup-push —— 每分钟轮询 ESPN,检测"刚结束"的比赛,状态存 KV。
// 这是推送系统的「检测引擎」:Cron 每分钟跑一次(云端常驻),发现某场从「进行中」变「完场」,
// 就记下最终比分。后续 Web Push 发送逻辑挂在 justFinished 处(见 TODO)。
const ESPN = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard?dates=";

function ymd(d) {
  return d.getUTCFullYear() +
    ("0" + (d.getUTCMonth() + 1)).slice(-2) +
    ("0" + d.getUTCDate()).slice(-2);
}
function range() {
  const n = Date.now();
  return ymd(new Date(n - 86400000)) + "-" + ymd(new Date(n + 86400000));
}

async function poll(env) {
  const res = await fetch(ESPN + range(), { cf: { cacheTtl: 0 } });
  if (!res.ok) throw new Error("espn " + res.status);
  const data = await res.json();
  const events = data.events || [];

  const prevRaw = await env.WC_KV.get("match_status");
  const prev = prevRaw ? JSON.parse(prevRaw) : null;   // 首次部署 prev=null,只播种不判定
  const now = {};
  const justFinished = [];

  for (const e of events) {
    const comp = (e.competitions || [])[0];
    if (!comp) continue;
    const state = (((comp.status || {}).type) || {}).state || ""; // pre / in / post
    now[e.id] = state;
    // 只有上一轮已知该场、且从「非 post」变「post」才算刚结束
    // (避免首轮/重启把历史完场全当成"刚结束"误报)
    if (prev && state === "post" && prev[e.id] && prev[e.id] !== "post") {
      const cs = comp.competitors || [];
      const h = cs.find(c => c.homeAway === "home") || cs[0];
      const a = cs.find(c => c.homeAway === "away") || cs[1];
      justFinished.push({
        id: e.id,
        home: (h.team || {}).displayName, hs: h.score,
        away: (a.team || {}).displayName, as: a.score
      });
    }
  }

  // 只在状态真的变化时才写 KV——KV 免费额度每天 1000 写,每分钟无脑写(1440/天)会超额。
  // 绝大多数分钟无比赛状态变化,跳过写入;只有 pre→in→post 等变化时才写,一天几十次以内。
  const nowStr = JSON.stringify(now);
  if (nowStr !== prevRaw) await env.WC_KV.put("match_status", nowStr);

  if (justFinished.length) {
    // 记录最近一批刚结束的(供 /recent 验证 + 后续推送层取用)
    await env.WC_KV.put("recent_finishes",
      JSON.stringify({ ts: Date.now(), matches: justFinished }));
    for (const m of justFinished) console.log("FINISHED:", m.home, m.hs, ":", m.as, m.away);
    // TODO(推送层): 这里遍历 KV 里的订阅,发 Web Push「X hs:as Y 完场」
  }
  return { checked: events.length, justFinished };
}

export default {
  // Cron Trigger 每分钟触发
  async scheduled(event, env, ctx) {
    ctx.waitUntil(poll(env).catch(err => console.log("poll error:", err.message)));
  },
  // HTTP 端点:调试/验证用
  async fetch(req, env) {
    const url = new URL(req.url);
    if (url.pathname === "/recent") {        // 看最近检测到的"刚结束"
      const r = await env.WC_KV.get("recent_finishes");
      return new Response(r || "{}", { headers: { "content-type": "application/json; charset=utf-8" } });
    }
    if (url.pathname === "/run") {           // 手动触发一次轮询(不等 cron)
      try {
        const r = await poll(env);
        return new Response(JSON.stringify(r, null, 2), { headers: { "content-type": "application/json; charset=utf-8" } });
      } catch (e) {
        return new Response("error: " + e.message, { status: 500 });
      }
    }
    return new Response("worldcup-push: ESPN match-end watcher (cron 1min)\n");
  }
};
