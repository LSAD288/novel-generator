/* 烽火南境 PWA Service Worker
   策略：网络优先，失败回退缓存 —— 保证更新立即可见，断网时至少能打开外壳。
   只在 https 或 localhost 下会注册成功（局域网 http 下浏览器会跳过）。 */
const CACHE = 'fj-shell-v1';
const SHELL = [
  '/',
  '/index.html',
  '/app.css',
  '/theme.css',
  '/app.js',
  '/studio.js',
  '/manifest.webmanifest',
  '/assets/logo.png',
  '/assets/icons/icon-192.png',
];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(SHELL)).catch(() => {}).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;
  if (url.pathname.startsWith('/api/')) return;

  e.respondWith(
    fetch(req)
      .then((res) => {
        if (res && res.ok) {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
        }
        return res;
      })
      .catch(() => caches.match(req).then((hit) => hit || caches.match('/index.html')))
  );
});
