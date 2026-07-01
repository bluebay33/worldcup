// 极简 service worker:满足 PWA「可安装」条件 + 不卡死在启动页。
// 不做内容缓存(数据永远走网络,杜绝过期)。
// v2 (2026-07-01):偶发"停在足球启动页"根因是首个导航请求「挂起」(连上了但响应不来,
//   既不 resolve 也不 reject)——旧版只 .catch() 失败、接不住挂起,壳就永久等。现改为:
//   ① 非导航请求一律放行,SW 不插手;② 导航请求「网络优先 + 4.5 秒超时」,挂起也回退重连页。
self.addEventListener('install', function (e) { self.skipWaiting(); });
self.addEventListener('activate', function (e) {
  // 激活时清掉任何历史遗留缓存(防止旧版 SW 缓存的页面一直喂旧内容)
  e.waitUntil(
    caches.keys()
      .then(function (keys) { return Promise.all(keys.map(function (k) { return caches.delete(k); })); })
      .then(function () { return self.clients.claim(); })
  );
});
// 2 秒后自动重试的占位页——导航请求失败/挂起时的兜底,避免壳停在启动页或白屏。
function reconnectPage() {
  return new Response(
    '<!doctype html><html><head><meta charset="utf-8">' +
    '<meta name="viewport" content="width=device-width,initial-scale=1">' +
    '<meta http-equiv="refresh" content="2"></head>' +
    '<body style="margin:0;height:100vh;display:flex;align-items:center;justify-content:center;' +
    'background:#0d1117;color:#8b98a5;font:16px/1.7 system-ui,-apple-system,sans-serif">' +
    '<div style="text-align:center;font-size:32px">⚽' +
    '<div style="font-size:15px;margin-top:14px">正在加载，请稍候…</div>' +
    '</div></body></html>',
    { headers: { 'Content-Type': 'text/html; charset=utf-8' } }
  );
}
self.addEventListener('fetch', function (e) {
  // 非导航请求(数据/图片/脚本)一律放行走浏览器默认,SW 不拦截——减少 SW 层卡死面。
  if (e.request.mode !== 'navigate') return;
  // 导航请求:网络优先,但最多等 4.5 秒。fetch 成功→用真页面;失败或超时(挂起)→回退重连页。
  // 关键:setTimeout 兜住"挂起"这一档(旧版只 .catch 失败,接不住挂起→永久卡启动页)。
  e.respondWith(new Promise(function (resolve) {
    var settled = false;
    var timer = setTimeout(function () {
      if (!settled) { settled = true; resolve(reconnectPage()); }
    }, 4500);
    fetch(e.request).then(function (resp) {
      if (!settled) { settled = true; clearTimeout(timer); resolve(resp); }
    }).catch(function () {
      if (!settled) { settled = true; clearTimeout(timer); resolve(reconnectPage()); }
    });
  }));
});
// 收到 Web Push → 弹系统通知。payload 约定 JSON: {title, body, url, tag}
self.addEventListener('push', function (e) {
  var d = {};
  try { d = e.data ? e.data.json() : {}; } catch (err) { d = { body: e.data ? e.data.text() : '' }; }
  e.waitUntil(self.registration.showNotification(d.title || '2026 世界杯', {
    body: d.body || '',
    icon: 'icon-192.png',
    badge: 'icon-192.png',
    tag: d.tag || 'wc-push',
    data: { url: d.url || '/' }
  }));
});
// 点击通知 → 聚焦已开窗口,否则打开 app
self.addEventListener('notificationclick', function (e) {
  e.notification.close();
  var url = (e.notification.data && e.notification.data.url) || '/';
  e.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function (cs) {
      for (var i = 0; i < cs.length; i++) { if ('focus' in cs[i]) return cs[i].focus(); }
      if (self.clients.openWindow) return self.clients.openWindow(url);
    })
  );
});
