// 极简 service worker:仅用于让本站满足 PWA「可安装」条件(生成 WebAPK)。
// 不做任何缓存,所有请求永远走网络 —— 杜绝数据过期问题。
self.addEventListener('install', function (e) { self.skipWaiting(); });
self.addEventListener('activate', function (e) {
  // 激活时清掉任何历史遗留的缓存(防止旧版 SW 缓存的页面一直喂旧内容)
  e.waitUntil(
    caches.keys()
      .then(function (keys) { return Promise.all(keys.map(function (k) { return caches.delete(k); })); })
      .then(function () { return self.clients.claim(); })
  );
});
self.addEventListener('fetch', function (e) {
  // 网络直通,不读写缓存
  e.respondWith(fetch(e.request));
});
