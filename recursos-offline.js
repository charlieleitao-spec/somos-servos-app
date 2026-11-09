(() => {
  if (!('serviceWorker' in navigator)) return;

  async function prepareOfflineResources() {
    try {
      await import('./sw-version.js');
      const registration = await navigator.serviceWorker.register('./service-worker.js?v=' + globalThis.SOMOS_SERVOS_SW_VERSION, { updateViaCache: 'none' });
      await registration.update();
    } catch (error) {
      console.warn('Não foi possível preparar os recursos para acesso offline:', error);
    }
  }

  if (document.readyState === 'complete') {
    prepareOfflineResources();
  } else {
    window.addEventListener('load', prepareOfflineResources, { once: true });
  }
})();
