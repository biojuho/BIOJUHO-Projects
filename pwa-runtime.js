(function (root) {
  "use strict";

  const VERSION = "joopark-pwa-runtime/v1";

  function createPwaRuntime(deps) {
    const options = deps || {};
    const rootWindow = options.window || root;
    const rootDocument = options.document || rootWindow.document;
    const rootNavigator = options.navigator || rootWindow.navigator || {};
    const rootLocation = options.location || rootWindow.location || {};
    const rootCaches = options.caches || rootWindow.caches;

    function localHostContext() {
      return rootLocation.hostname === "localhost" || rootLocation.hostname === "127.0.0.1";
    }

    function secureEnoughForServiceWorker() {
      return !!rootWindow.isSecureContext || localHostContext();
    }

    function statusLabel(runtime) {
      if (!runtime.checked) return "checking";
      if (!runtime.secureContext && !runtime.localHostContext) return "insecure";
      if (!runtime.serviceWorkerSupported) return "unsupported";
      if (runtime.serviceWorkerActive && runtime.cacheReady && runtime.manifestLinked) return "ready";
      if (runtime.serviceWorkerActive || runtime.cacheReady || runtime.manifestLinked) return "partial";
      return "waiting";
    }

    async function inspect(previous) {
      const next = {
        ...(previous && typeof previous === "object" ? previous : {}),
        checked: true,
        secureContext: !!rootWindow.isSecureContext,
        localHostContext: localHostContext(),
        serviceWorkerSupported: "serviceWorker" in rootNavigator,
        controller: !!(rootNavigator.serviceWorker && rootNavigator.serviceWorker.controller),
        cachesSupported: !!rootCaches,
        manifestLinked: !!(rootDocument && rootDocument.querySelector('link[rel="manifest"][href$="site.webmanifest"]')),
        standalone: !!(rootWindow.matchMedia && rootWindow.matchMedia("(display-mode: standalone)").matches) || rootNavigator.standalone === true,
        online: rootNavigator.onLine !== false,
        checkedAt: new Date().toISOString(),
        lastError: "",
      };

      if (next.serviceWorkerSupported && secureEnoughForServiceWorker()) {
        try {
          const registration = await rootNavigator.serviceWorker.getRegistration("./");
          const worker = registration && (registration.active || registration.installing || registration.waiting);
          next.serviceWorkerActive = !!(registration && registration.active);
          next.scriptURL = worker ? worker.scriptURL || "" : "";
          next.scope = registration ? registration.scope || "" : "";
        } catch (error) {
          next.serviceWorkerActive = false;
          next.scriptURL = "";
          next.scope = "";
          next.lastError = error && error.message ? error.message : "service worker registration unavailable";
        }
      } else {
        next.serviceWorkerActive = false;
        next.scriptURL = "";
        next.scope = "";
      }

      if (next.cachesSupported) {
        try {
          const cacheNames = await rootCaches.keys();
          const appShellCaches = cacheNames.filter((name) => name.includes("joopark-app-shell")).sort();
          const appShellCache = appShellCaches[appShellCaches.length - 1] || "";
          next.appShellCache = appShellCache;
          next.cacheReady = !!appShellCache;
          next.cachedAssetCount = 0;
          if (appShellCache) {
            const cache = await rootCaches.open(appShellCache);
            const requests = await cache.keys();
            next.cachedAssetCount = requests.length;
          }
        } catch (error) {
          next.cacheReady = false;
          next.appShellCache = "";
          next.cachedAssetCount = 0;
          next.lastError = next.lastError || (error && error.message ? error.message : "cache storage unavailable");
        }
      } else {
        next.cacheReady = false;
        next.appShellCache = "";
        next.cachedAssetCount = 0;
      }

      next.status = statusLabel(next);
      return next;
    }

    function setupObservers(onUpdate) {
      const refresh = typeof onUpdate === "function" ? onUpdate : function () {};
      rootWindow.addEventListener("online", refresh);
      rootWindow.addEventListener("offline", refresh);
      if ("serviceWorker" in rootNavigator) {
        rootNavigator.serviceWorker.addEventListener("controllerchange", refresh);
        rootNavigator.serviceWorker.ready.then(refresh).catch(refresh);
      }
      refresh();
    }

    function register(onUpdate) {
      const refresh = typeof onUpdate === "function" ? onUpdate : function () {};
      if (!("serviceWorker" in rootNavigator)) return false;
      if (!secureEnoughForServiceWorker()) return false;
      rootWindow.addEventListener("load", () => {
        rootNavigator.serviceWorker.register("./sw.js", { scope: "./" })
          .then(refresh)
          .catch(() => {
            // Registration is an enhancement; static hosting still works without it.
          })
          .finally(refresh);
      }, { once: true });
      return true;
    }

    return {
      version: VERSION,
      statusLabel,
      inspect,
      setupObservers,
      register,
    };
  }

  root.JooParkPwaRuntime = {
    version: VERSION,
    create: createPwaRuntime,
  };
})(window);
