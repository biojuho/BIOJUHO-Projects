(function attachRuntimeErrorBoundary(root) {
  "use strict";

  const VERSION = "joopark-runtime-error-boundary/v1";

  function debounceMsOption(value, fallback = 2500) {
    const parsed = Number(value);
    const fallbackNumber = Number(fallback);
    const safeFallback = Number.isFinite(fallbackNumber) && fallbackNumber > 0 ? fallbackNumber : 2500;
    const safeValue = Number.isFinite(parsed) && parsed > 0 ? parsed : safeFallback;
    return Math.max(250, Math.trunc(safeValue));
  }

  function createRuntimeErrorBoundary(options = {}) {
    const windowRef = options.window || root;
    const consoleRef = options.consoleRef || root.console || { error() {} };
    const locationRef = options.locationRef || windowRef.location || { hash: "" };
    const showToast = typeof options.showToast === "function" ? options.showToast : null;
    const fallback = typeof options.fallback === "function" ? options.fallback : null;
    const now = typeof options.now === "function" ? options.now : () => Date.now();
    const debounceMs = debounceMsOption(options.debounceMs);
    const toastMessage = options.toastMessage || "예상치 못한 오류가 발생했습니다. 화면을 안전하게 유지했습니다.";
    let installed = false;
    let handling = false;
    let lastToastAt = Number.NEGATIVE_INFINITY;

    function errorFromEvent(input) {
      if (!input) return null;
      if (input.error) return input.error;
      if (input.reason) return input.reason;
      return input;
    }

    function normalize(input, context = {}) {
      const error = errorFromEvent(input);
      const message = error && error.message ? String(error.message) : String(error || "unknown runtime error");
      const stack = error && error.stack ? String(error.stack) : "";
      return {
        version: VERSION,
        source: context.source || "runtime",
        message,
        stack,
        hash: String(locationRef.hash || ""),
        filename: context.filename || input?.filename || "",
        lineno: Number.isFinite(Number(context.lineno || input?.lineno)) ? Number(context.lineno || input?.lineno) : 0,
        colno: Number.isFinite(Number(context.colno || input?.colno)) ? Number(context.colno || input?.colno) : 0,
        view: context.view || "",
        at: typeof options.nowISO === "function" ? options.nowISO() : new Date(now()).toISOString(),
      };
    }

    function notify(payload) {
      const ts = now();
      if (!showToast || ts - lastToastAt < debounceMs) return false;
      lastToastAt = ts;
      showToast(toastMessage, "error", { timeoutMs: 5200 });
      return true;
    }

    function handle(input, context = {}) {
      const payload = normalize(input, context);
      if (handling) {
        consoleRef.error("[joopark-runtime-error]", payload);
        return payload;
      }
      handling = true;
      try {
        consoleRef.error("[joopark-runtime-error]", payload);
        try {
          notify(payload);
        } catch (toastError) {
          consoleRef.error("[joopark-runtime-error:toast]", normalize(toastError, { source: "runtime-toast" }));
        }
        if (fallback) {
          try {
            fallback(payload);
          } catch (fallbackError) {
            consoleRef.error("[joopark-runtime-error:fallback]", normalize(fallbackError, { source: "runtime-fallback" }));
          }
        }
      } finally {
        handling = false;
      }
      return payload;
    }

    function install() {
      if (installed || windowRef.__jooparkRuntimeErrorBoundaryInstalled) return false;
      if (!windowRef || typeof windowRef.addEventListener !== "function") return false;
      windowRef.__jooparkRuntimeErrorBoundaryInstalled = true;
      windowRef.addEventListener("error", (event) => {
        handle(event, {
          source: "error",
          filename: event?.filename,
          lineno: event?.lineno,
          colno: event?.colno,
        });
      });
      windowRef.addEventListener("unhandledrejection", (event) => {
        handle(event, { source: "unhandledrejection" });
      });
      installed = true;
      return true;
    }

    return {
      version: VERSION,
      install,
      handle,
      normalize,
      debounceMsOption,
    };
  }

  root.JooParkRuntimeErrorBoundary = {
    version: VERSION,
    create: createRuntimeErrorBoundary,
  };
})(typeof window !== "undefined" ? window : globalThis);
