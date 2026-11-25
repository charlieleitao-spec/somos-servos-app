'use strict';

const reminderPreference = 'daily-reminder-enabled';
const scheduleVersion = 'daily-reminder-schedule';
const channelId = 'celebracao-servita';
const dailyIdBase = 2750000;
const horizon = 90;

function upcomingReminders(entries, now) {
  const celebrations = new Map(entries.map(([month, day, title, rank]) => [
    month * 100 + day,
    { title, rank },
  ]));
  const notifications = [];
  for (let offset = 0; offset <= horizon; offset++) {
    const date = new Date(now.getFullYear(), now.getMonth(), now.getDate() + offset, 7);
    if (date <= now) continue;
    const monthDay = (date.getMonth() + 1) * 100 + date.getDate();
    const utcDay = Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()) / 86400000;
    const celebration = celebrations.get(monthDay);
    notifications.push({
      id: dailyIdBase + utcDay,
      title: celebration?.title || 'Hoje na Família Servita',
      body: celebration
        ? celebration.rank + ' no calendário servita. Toque para abrir a página Hoje.'
        : 'Sem celebração própria no calendário servita. Consulte o ofício do tempo litúrgico.',
      channelId,
      isExactNotification: false,
      schedule: { at: date.toISOString(), allowWhileIdle: true },
    });
  }
  return notifications;
}

async function setUpReminder() {
  const plugin = window.Capacitor?.Plugins?.LocalNotifications;
  if (!plugin) return;

  const button = document.getElementById('reminder');
  const status = document.getElementById('status');
  const isEnabled = () => localStorage.getItem(reminderPreference) === 'true';

  async function cancelPending() {
    const { notifications } = await plugin.getPending();
    const own = notifications.filter(({ id }) => id >= dailyIdBase && id < dailyIdBase + 100000);
    if (own.length) await plugin.cancel({ notifications: own.map(({ id }) => ({ id })) });
  }

  async function renewSchedule() {
    const now = new Date();
    const stamp = [now.toDateString(), Intl.DateTimeFormat().resolvedOptions().timeZone].join('|');
    if (localStorage.getItem(scheduleVersion) === stamp) return;

    const response = await fetch('./android-calendar.json');
    if (!response.ok) throw new Error('Calendário indisponível');
    const entries = await response.json();
    const upcoming = upcomingReminders(entries, now);
    await plugin.createChannel({ id: channelId, name: 'Celebração servita do dia', importance: 3 });
    // IDs por dia substituem agendamentos existentes, inclusive após mudança de fuso.
    await plugin.schedule({ notifications: upcoming });
    localStorage.setItem(scheduleVersion, stamp);
  }

  async function update(toggle) {
    button.disabled = true;
    try {
      if (toggle && isEnabled()) {
        await cancelPending();
        localStorage.removeItem(reminderPreference);
        localStorage.removeItem(scheduleVersion);
      } else if (toggle || isEnabled()) {
        let permission = await plugin.checkPermissions();
        if (toggle && permission.display !== 'granted') permission = await plugin.requestPermissions();
        if (permission.display === 'granted') {
          await renewSchedule();
          localStorage.setItem(reminderPreference, 'true');
        } else {
          await cancelPending();
          localStorage.removeItem(reminderPreference);
          localStorage.removeItem(scheduleVersion);
          status.textContent = 'Autorize as notificações do Somos Servos nas configurações do Android.';
          return;
        }
      }
      status.textContent = isEnabled() ? 'Lembrete ativado.' : 'Lembrete desativado.';
    } catch (error) {
      console.warn('Não foi possível atualizar o lembrete diário.', error);
      localStorage.removeItem(scheduleVersion);
      status.textContent = 'Não foi possível atualizar o lembrete. Tente novamente.';
    } finally {
      button.textContent = isEnabled() ? 'Desativar lembrete' : 'Ativar lembrete';
      button.disabled = false;
    }
  }

  button.addEventListener('click', () => update(true));
  window.addEventListener('somos-servos-resume', () => {
    if (!button.disabled) update(false);
  });
  await update(false);
}

if (typeof window !== 'undefined') setUpReminder();
if (typeof module !== 'undefined') module.exports = { upcomingReminders };
