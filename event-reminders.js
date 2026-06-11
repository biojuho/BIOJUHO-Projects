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
    const lastFired = new Set();

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
      try {
        return setIntervalRef(() => {
          try {
            remindUpcomingEvents();
          } catch (_) {
            /* best-effort notification poll */
          }
        }, 60000);
      } catch (_) {
        return null;
      }
    }

    return {
      version: VERSION,
      start,
      tryBrowserNotification,
      remindUpcomingEvents,
    };
  }

  root.JooParkEventReminders = {
    version: VERSION,
    create: createEventReminders,
  };
})(window);
