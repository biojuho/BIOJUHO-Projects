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
    const showToast = typeof options.showToast === "function"
      ? options.showToast
      : typeof rootWindow.showToast === "function"
        ? rootWindow.showToast
        : null;
    const watchedRegistrations = typeof WeakSet === "function" ? new WeakSet() : null;
    const watchedWorkers = typeof WeakSet === "function" ? new WeakSet() : null;
    let controllerObserved = !!(rootNavigator.serviceWorker && rootNavigator.serviceWorker.controller);
    let updateDetected = false;
    let updateToastShown = false;
    let updateReloadRequested = false;

    function localHostContext() {
      return rootLocation.hostname === "localhost" || rootLocation.hostname === "127.0.0.1";
    }

    function secureEnoughForServiceWorker() {
      return !!rootWindow.isSecureContext || localHostContext();
    }

    function serviceWorkerSupported() {
      return "serviceWorker" in rootNavigator;
    }

    function updateCallback(onUpdate) {
      return typeof onUpdate === "function" ? onUpdate : function () {};
    }

    function updateReload() {
      updateReloadRequested = true;
      const locationRef = rootLocation && typeof rootLocation.reload === "function"
        ? rootLocation
        : rootWindow.location;
      if (locationRef && typeof locationRef.reload === "function") {
        locationRef.reload();
        return true;
      }
      return false;
    }

    function showUpdateToast(message) {
      if (!showToast || updateToastShown) return false;
      updateToastShown = true;
      showToast(message, "info", {
        actionLabel: "새로고침",
        onAction: updateReload,
        timeoutMs: 12000,
      });
      return true;
    }

    function showUpdateReadyToast() {
      return showUpdateToast("새 버전이 준비되었습니다");
    }

    function showUpdateAppliedToast() {
      if (updateReloadRequested) return false;
      return showUpdateToast("새 버전이 적용되었습니다");
    }

    function registrationHasUpdate(registration, worker) {
      return !!(controllerObserved && registration && registration.active && worker && registration.active !== worker);
    }

    function watchWorker(worker, refresh, updateCandidate) {
      if (!worker || typeof worker.addEventListener !== "function") return false;
      if (watchedWorkers && watchedWorkers.has(worker)) return true;
      if (watchedWorkers) watchedWorkers.add(worker);
      const isUpdateCandidate = !!updateCandidate;
      worker.addEventListener("statechange", () => {
        refresh();
        if (!controllerObserved || (!isUpdateCandidate && !updateDetected)) return;
        if (worker.state === "installed") showUpdateReadyToast();
        if (worker.state === "activated") showUpdateAppliedToast();
      });
      return true;
    }

    function watchRegistration(registration, refresh) {
      if (!registration || typeof registration !== "object") return false;
      if (registrationHasUpdate(registration, registration.waiting)) {
        updateDetected = true;
        showUpdateReadyToast();
      }
      watchWorker(registration.installing, refresh, registrationHasUpdate(registration, registration.installing));
      if (typeof registration.addEventListener !== "function") return false;
      if (watchedRegistrations && watchedRegistrations.has(registration)) return true;
      if (watchedRegistrations) watchedRegistrations.add(registration);
      registration.addEventListener("updatefound", () => {
        const isUpdateCandidate = registrationHasUpdate(registration, registration.installing);
        if (isUpdateCandidate) updateDetected = true;
        watchWorker(registration.installing, refresh, isUpdateCandidate);
        refresh();
      });
      return true;
    }

    function statusLabel(runtime) {
      if (!runtime.checked) return "checking";
      if (!runtime.secureContext && !runtime.localHostContext) return "insecure";
      if (!runtime.serviceWorkerSupported) return "unsupported";
      if (runtime.serviceWorkerActive && runtime.cacheReady && runtime.manifestLinked) return "ready";
      if (runtime.serviceWorkerActive || runtime.cacheReady || runtime.manifestLinked) return "partial";
      return "waiting";
    }

    function resetServiceWorkerState(runtime) {
      runtime.serviceWorkerActive = false;
      runtime.scriptURL = "";
      runtime.scope = "";
    }

    function resetCacheState(runtime) {
      runtime.cacheReady = false;
      runtime.appShellCache = "";
      runtime.cachedAssetCount = 0;
    }

    async function inspect(previous) {
      const next = {
        ...(previous && typeof previous === "object" ? previous : {}),
        checked: true,
        secureContext: !!rootWindow.isSecureContext,
        localHostContext: localHostContext(),
        serviceWorkerSupported: serviceWorkerSupported(),
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
          resetServiceWorkerState(next);
          next.lastError = error && error.message ? error.message : "service worker registration unavailable";
        }
      } else {
        resetServiceWorkerState(next);
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
          resetCacheState(next);
          next.lastError = next.lastError || (error && error.message ? error.message : "cache storage unavailable");
        }
      } else {
        resetCacheState(next);
      }

      next.status = statusLabel(next);
      return next;
    }

    function setupObservers(onUpdate) {
      const refresh = updateCallback(onUpdate);
      rootWindow.addEventListener("online", refresh);
      rootWindow.addEventListener("offline", refresh);
      if (serviceWorkerSupported()) {
        rootNavigator.serviceWorker.addEventListener("controllerchange", () => {
          const hadController = controllerObserved;
          controllerObserved = !!rootNavigator.serviceWorker.controller;
          refresh();
          if (hadController && updateDetected) showUpdateAppliedToast();
        });
        rootNavigator.serviceWorker.ready
          .then((registration) => {
            watchRegistration(registration, refresh);
            refresh();
          })
          .catch(refresh);
      }
      refresh();
    }

    function register(onUpdate) {
      const refresh = updateCallback(onUpdate);
      if (!serviceWorkerSupported()) return false;
      if (!secureEnoughForServiceWorker()) return false;
      rootWindow.addEventListener("load", () => {
        rootNavigator.serviceWorker.register("./sw.js", { scope: "./" })
          .then((registration) => {
            watchRegistration(registration, refresh);
            refresh();
          })
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
