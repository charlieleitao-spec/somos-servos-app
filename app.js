const BLOG_URL = 'https://somosservos.blogspot.com/?m=1';
const isNative = Boolean(window.Capacitor?.isNativePlatform?.());

// No Android, navega o blog diretamente no WebView. Assim, as postagens
// entram no histórico nativo e o botão Voltar retorna à página anterior.
// replace() evita deixar esta tela intermediária no histórico inicial.
if (isNative) {
  window.location.replace(BLOG_URL);
} else {
  const frame = document.querySelector('#blogFrame');
  const fallback = document.querySelector('#fallback');
  const retryButton = document.querySelector('#retryButton');
  const installButton = document.querySelector('#installButton');
  let installPrompt;

  function updateConnection() {
    if (!navigator.onLine) {
      frame.hidden = true;
      fallback.hidden = false;
    } else {
      frame.hidden = false;
      fallback.hidden = true;
    }
  }

  window.addEventListener('online', () => {
    updateConnection();
    frame.src = BLOG_URL;
  });
  window.addEventListener('offline', updateConnection);
  retryButton.addEventListener('click', () => {
    updateConnection();
    if (navigator.onLine) frame.src = BLOG_URL;
  });

  window.addEventListener('beforeinstallprompt', event => {
    event.preventDefault();
    installPrompt = event;
    installButton.hidden = false;
  });
  installButton.addEventListener('click', async () => {
    if (!installPrompt) return;
    await installPrompt.prompt();
    await installPrompt.userChoice;
    installPrompt = undefined;
    installButton.hidden = true;
  });
  window.addEventListener('appinstalled', () => {
    installPrompt = undefined;
    installButton.hidden = true;
  });

  if ('serviceWorker' in navigator) {
    window.addEventListener('load', async () => {
      const registration = await navigator.serviceWorker.register('./service-worker.js?v=20');
      await registration.update();
    });
  }

  updateConnection();
}
