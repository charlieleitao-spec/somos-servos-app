const BLOG_URL = 'https://somosservos.blogspot.com/?m=1';
const isNative = Boolean(window.Capacitor?.isNativePlatform?.());

const frame = document.querySelector('#blogFrame');
const fallback = document.querySelector('#fallback');
const retryButton = document.querySelector('#retryButton');
const installButton = document.querySelector('#installButton');
let installPrompt;
let connectionCheck = 0;

function showOffline() {
  connectionCheck += 1;
  frame.hidden = true;
  fallback.hidden = false;
}

function showBlog() {
  frame.hidden = false;
  fallback.hidden = true;
}

async function checkConnection() {
  const checkId = ++connectionCheck;
  if (!navigator.onLine) {
    showOffline();
    return;
  }

  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 10000);

  try {
    // A resposta opaca basta para confirmar que o Blogger está alcançável.
    await fetch(BLOG_URL, {
      mode: 'no-cors',
      cache: 'no-store',
      signal: controller.signal
    });
    if (checkId !== connectionCheck) return;

    showBlog();
    frame.src = BLOG_URL;
  } catch {
    if (checkId === connectionCheck) showOffline();
  } finally {
    window.clearTimeout(timeout);
  }
}

window.addEventListener('online', checkConnection);
window.addEventListener('offline', showOffline);
retryButton.addEventListener('click', checkConnection);

if (isNative) {
  window.addEventListener('DOMContentLoaded', async () => {
    try {
      const { App } = await import('@capacitor/app');
      await App.addListener('backButton', ({ canGoBack }) => {
        if (canGoBack || window.history.length > 1) {
          window.history.back();
        }
      });
    } catch (error) {
      console.warn('Não foi possível registrar o botão Voltar:', error);
    }
    await checkConnection();
  });
} else {
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
      try {
        const registration = await navigator.serviceWorker.register('./service-worker.js?v=22');
        await registration.update();
      } catch (error) {
        console.warn('Não foi possível atualizar o cache do aplicativo:', error);
      }
    });
  }

  checkConnection();
}
