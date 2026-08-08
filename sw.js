'use strict';

// Remove o cache legado do tema para que novas versões do portfólio
// sejam carregadas diretamente do GitHub Pages.
self.addEventListener('install', function() {
  self.skipWaiting();
});

self.addEventListener('activate', function(event) {
  event.waitUntil(
    caches.keys()
      .then(function(keys) {
        return Promise.all(keys.map(function(key) {
          return caches.delete(key);
        }));
      })
      .then(function() {
        return self.registration.unregister();
      })
  );
});
