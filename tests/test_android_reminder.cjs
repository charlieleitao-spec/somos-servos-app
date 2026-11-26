const assert = require('node:assert/strict');
const { upcomingReminders } = require('../android-src/web/android-reminder.js');
const calendar = require('../android-src/web/android-calendar.json');

const now = new Date(2027, 1, 16, 12);
const upcoming = upcomingReminders(calendar, now);
assert.equal(upcoming.length, 90);
assert.equal(upcoming[0].title, 'Sete Santos Fundadores');
assert.match(upcoming[0].body, /Solenidade/);
assert.equal(upcoming[1].title, 'Hoje na Família Servita');
assert.equal(new Set(upcoming.map(({ id }) => id)).size, upcoming.length);
assert.ok(upcoming.every(({ schedule, isExactNotification }) => {
  const date = new Date(schedule.at);
  return date > now && date.getHours() === 7 && date.getMinutes() === 0 && !isExactNotification;
}));

const beforeSeven = upcomingReminders(calendar, new Date(2027, 1, 17, 6, 59));
assert.equal(beforeSeven[0].id, upcoming[0].id);
const afterSeven = upcomingReminders(calendar, new Date(2027, 1, 17, 7));
assert.equal(afterSeven[0].id, upcoming[1].id);

const leapYear = upcomingReminders(calendar, new Date(2028, 1, 28, 12));
assert.equal(new Date(leapYear[0].schedule.at).getDate(), 29);
assert.equal(new Date(leapYear[1].schedule.at).getDate(), 1);
console.log('PASS: títulos do santoral, horário local, renovação sem duplicatas e ano bissexto.');
