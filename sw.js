// 极简 service worker:满足 PWA「可安装」条件 + 网络抖动时不卡死在启动页。
// 不做内容缓存(数据永远走网络,杜绝过期);但网络请求失败时,「打开页面」的导航请求
// 返回一个 2 秒后自动重试的占位页,避免 TWA / 浏览器停在启动页或白屏。
self.addEventListener('install', function (e) { self.skipWaiting(); });
self.addEventListener('activate', function (e) {
  // 激活时清掉任何历史遗留缓存(防止旧版 SW 缓存的页面一直喂旧内容)
  e.waitUntil(
    caches.keys()
      .then(function (keys) { return Promise.all(keys.map(function (k) { return caches.delete(k); })); })
      .then(function () { return self.clients.claim(); })
  );
});
self.addEventListener('fetch', function (e) {
  e.respondWith(
    fetch(e.request).catch(function () {
      // 网络瞬断/连接重置:导航请求(打开页面)失败时返回自动重连页,而不是让壳卡在启动页;
      // 其它请求(数据/图片等)失败则交回页面自身的 JS 去处理(它们都有各自的 catch)。
      if (e.request.mode === 'navigate') {
        return new Response(
          '<!doctype html><html><head><meta charset="utf-8">' +
          '<meta name="viewport" content="width=device-width,initial-scale=1">' +
          '<meta http-equiv="refresh" content="2"></head>' +
          '<body style="margin:0;height:100vh;display:flex;align-items:center;justify-content:center;' +
          'background:#0d1117;color:#8b98a5;font:16px/1.7 system-ui,-apple-system,sans-serif">' +
          '<div style="text-align:center;font-size:32px">⚽' +
          '<div style="font-size:15px;margin-top:14px">网络波动，正在重连…</div>' +
          '</div></body></html>',
          { headers: { 'Content-Type': 'text/html; charset=utf-8' } }
        );
      }
      return Response.error();
    })
  );
});
