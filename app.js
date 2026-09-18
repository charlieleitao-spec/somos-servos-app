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

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => navigator.serviceWorker.register('./service-worker.js'));
}
updateConnection();
