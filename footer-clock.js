(function (root) {
  "use strict";

  const VERSION = "joopark-footer-clock/v1";

  function pad2(value) {
    return String(value).padStart(2, "0");
  }

  function formatFooterNow(date) {
    const d = date instanceof Date ? date : new Date();
    const yyyy = d.getFullYear();
    const mm = pad2(d.getMonth() + 1);
    const dd = pad2(d.getDate());
    const hh = pad2(d.getHours());
    const mi = pad2(d.getMinutes());
    return `현재 시각: ${yyyy}-${mm}-${dd} ${hh}:${mi}`;
  }

  function createFooterClock(deps = {}) {
    const documentRef = deps.document || root.document;
    const getNow = typeof deps.getNow === "function" ? deps.getNow : () => new Date();
    const getFooterNow = typeof deps.getFooterNow === "function"
      ? deps.getFooterNow
      : () => (documentRef && documentRef.getElementById ? documentRef.getElementById("footerNow") : null);
    const setTimeoutRef = typeof deps.setTimeout === "function"
      ? deps.setTimeout
      : root.setTimeout.bind(root);
    const clearTimeoutRef = typeof deps.clearTimeout === "function"
      ? deps.clearTimeout
      : root.clearTimeout.bind(root);

    let footerTimerId = null;
    let visibilityBound = false;

    function update() {
      const node = getFooterNow();
      if (!node) return false;
      node.textContent = formatFooterNow(getNow());
      return true;
    }

    function schedule() {
      if (footerTimerId !== null) return footerTimerId;
      const now = getNow();
      const msToNextMinute = (60 - now.getSeconds()) * 1000 - now.getMilliseconds();
      footerTimerId = setTimeoutRef(function tick() {
        update();
        footerTimerId = setTimeoutRef(tick, 60 * 1000);
      }, msToNextMinute);
      return footerTimerId;
    }

    function pause() {
      if (footerTimerId === null) return false;
      clearTimeoutRef(footerTimerId);
      footerTimerId = null;
      return true;
    }

    function setupVisibility() {
      if (!documentRef || typeof documentRef.addEventListener !== "function" || visibilityBound) return false;
      visibilityBound = true;
      documentRef.addEventListener("visibilitychange", () => {
        if (documentRef.hidden) pause();
        else {
          update();
          schedule();
        }
      });
      return true;
    }

    return {
      version: VERSION,
      formatFooterNow,
      update,
      schedule,
      pause,
      setupVisibility,
    };
  }

  root.JooParkFooterClock = {
    version: VERSION,
    create: createFooterClock,
  };
})(window);
