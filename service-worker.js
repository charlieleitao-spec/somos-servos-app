const CACHE_PREFIX = 'somos-servos-shell-';
const CACHE = CACHE_PREFIX + 'v57';
const APP_SHELL = [
  './',
  './index.html',
  './recursos.html',
  './pesquisa-bibliografica.html',
  './pesquisa-imagens.html',
  './pesquisa-historica.html',
  './referencias-salvas.html',
  './referencias-salvas.js',
  './recursos-offline.js',
  './data/biblioteca-servita-catalogo.json',
  './cartoes/index.html',
  './percurso-servita.html',
  './aprofundamento-servita.html',
  './comunidades-servitas.html',
  './percurso-servita.pdf',
  './styles.css?v=5',
  './app.js?v=23',
  './manifest.webmanifest',
  './icon-192.png',
  './icon-512.png'
];

self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(APP_SHELL.map(path => new Request(path, { cache: 'reload' })))));
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(keys.filter(key => key.startsWith(CACHE_PREFIX) && key !== CACHE).map(key => caches.delete(key))))
  );
  self.clients.claim();
});

async function saveResponse(cache, request, response) {
  if (response.ok) {
    try { await cache.put(request, response.clone()); } catch { /* A leitura continua se o armazenamento estiver cheio. */ }
  }
  return response;
}

async function loadPage(request) {
  const cache = await caches.open(CACHE);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 5000);
  try {
    const response = await fetch(request, { signal: controller.signal, cache: 'no-cache' });
    if (response.status >= 500) {
      const cached = await cache.match(request);
      if (cached) return cached;
    }
    return await saveResponse(cache, request, response);
  } catch (error) {
    const cached = await cache.match(request);
    if (cached) return cached;
    throw error;
  } finally { clearTimeout(timer); }
}

self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin || event.request.method !== 'GET') return;
  if (event.request.mode === 'navigate') {
    event.respondWith(loadPage(event.request));
    return;
  }
  event.respondWith(caches.open(CACHE).then(async cache => {
    const cached = await cache.match(event.request);
    return cached || saveResponse(cache, event.request, await fetch(event.request));
  }));
});
