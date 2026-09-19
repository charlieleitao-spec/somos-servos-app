const frame = document.querySelector('#blogFrame');
const fallback = document.querySelector('#fallback');
const retryButton = document.querySelector('#retryButton');
const installButton = document.querySelector('#installButton');
const isNative = Boolean(window.Capacitor?.isNativePlatform?.());
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
  frame.src = 'https://somosservos.blogspot.com/?m=1';
});
window.addEventListener('offline', updateConnection);
retryButton.addEventListener('click', () => {
  updateConnection();
  if (navigator.onLine) frame.src = 'https://somosservos.blogspot.com/?m=1';
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

async function resetOldCache() {
  if (isNative && 'serviceWorker' in navigator) {
    const registrations = await navigator.serviceWorker.getRegistrations();
    await Promise.all(registrations.map(registration => registration.unregister()));
  }
  if (isNative && 'caches' in window) {
    const keys = await caches.keys();
    await Promise.all(keys.map(key => caches.delete(key)));
  }
}

if (!isNative && 'serviceWorker' in navigator) {
  window.addEventListener('load', async () => {
    const registration = await navigator.serviceWorker.register('./service-worker.js?v=18');
    await registration.update();
  });
}

resetOldCache();
updateConnection();
