(function (root) {
  "use strict";

  const VERSION = "joopark-event-reminders/v1";

  function createEventReminders(deps = {}) {
    const windowRef = deps.window || root;
    const NotificationRef = deps.Notification || windowRef.Notification;
    const eventsOn = typeof deps.eventsOn === "function" ? deps.eventsOn : () => [];
    const todayISO = typeof deps.todayISO === "function" ? deps.todayISO : () => new Date().toISOString().slice(0, 10);
    const setIntervalRef = typeof deps.setInterval === "function"
      ? deps.setInterval
      : windowRef.setInterval.bind(windowRef);
    const clearIntervalRef = typeof deps.clearInterval === "function"
      ? deps.clearInterval
      : (windowRef.clearInterval ? windowRef.clearInterval.bind(windowRef) : () => {});
    const lastFired = new Set();
    let pollTimer = null;

    function notificationsGranted() {
      return typeof NotificationRef === "function" && NotificationRef.permission === "granted";
    }

    function tryBrowserNotification(title, body) {
      try {
        if (!notificationsGranted()) return false;
        new NotificationRef(title, { body, icon: "" });
        return true;
      } catch (_) {
        return false;
      }
    }

    function remindUpcomingEvents(now = new Date()) {
      if (!notificationsGranted()) return 0;
      const todayStr = todayISO();
      // Prune stale day-keys so the dedupe Set doesn't grow one entry per
      // reminded event per day for the life of the session.
      lastFired.forEach((key) => { if (!key.endsWith(`-${todayStr}`)) lastFired.delete(key); });
      let sent = 0;
      eventsOn(todayStr).forEach((event) => {
        if (!event || event.allDay || !event.start) return;
        const [hh, mm] = String(event.start).split(":").map(Number);
        const eventTime = new Date(now.getFullYear(), now.getMonth(), now.getDate(), hh, mm, 0);
        const diffMin = (eventTime - now) / 60000;
        if (diffMin < 0 || diffMin > 10) return;
        const key = `${event._masterId || event.id}-${todayStr}`;
        if (lastFired.has(key)) return;
        lastFired.add(key);
        if (tryBrowserNotification(`일정 알림: ${event.title}`, `${event.start} 시작 (약 ${Math.round(diffMin)}분 후)`)) sent += 1;
      });
      return sent;
    }

    function start() {
      // Idempotent: init and the permission-grant handler both call start(),
      // which previously leaked a second 60s interval each time.
      if (pollTimer !== null) return pollTimer;
      try {
        pollTimer = setIntervalRef(() => {
          try {
            remindUpcomingEvents();
          } catch (_) {
            /* best-effort notification poll */
          }
        }, 60000);
      } catch (_) {
        pollTimer = null;
      }
      return pollTimer;
    }

    function stop() {
      if (pollTimer === null) return;
      try { clearIntervalRef(pollTimer); } catch (_) { /* best-effort */ }
      pollTimer = null;
    }

    return {
      version: VERSION,
      start,
      stop,
      tryBrowserNotification,
      remindUpcomingEvents,
    };
  }

  root.JooParkEventReminders = {
    version: VERSION,
    create: createEventReminders,
  };
})(window);
