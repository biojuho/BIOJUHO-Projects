const CACHE_VERSION = "joopark-workspace-v3-offline-2026-06-09-github-discovery";
const CACHE_VERSION_LINEAGE = ["joopark-workspace-v3-offline-2026-06-09-ops-runtime-loader", "joopark-workspace-v3-offline-2026-06-09-home-view-module", "joopark-workspace-v3-offline-2026-06-09-runtime-error-boundary-module", "joopark-workspace-v3-offline-2026-06-08-review-issue-payload-module", "joopark-workspace-v3-offline-2026-06-08-review-execution-checklist-module"];
const APP_SHELL_CACHE = `joopark-app-shell-${CACHE_VERSION}`;

const APP_SHELL_ASSETS = [
  "./",
  "./index.html",
  "./styles.css",
  "./favicon.svg",
  "./site.webmanifest",
  "./social-preview.png",
  "./icons/icon-192.svg",
  "./icons/icon-512.svg",
  "./vendor/fuse.min.js",
  "./vendor/marked.umd.js",
  "./vendor/purify.min.js",
  "./search-empty-state.js",
  "./home-execution-view.js",
  "./calendar-view.js",
  "./todo-view.js",
  "./notes-view.js",
  "./habits-view.js",
  "./stats-view.js",
  "./llm-wiki-view.js",
  "./portfolio-view.js",
  "./kanban-view.js",
  "./gantt-view.js",
  "./team-view.js",
  "./workspace-storage.js",
  "./dashboard-storage.js",
  "./dashboard-prioritization.js",
  "./dashboard-evidence-receipts.js",
  "./dashboard-insights-engine.js",
  "./dashboard-autoresearch-loop.js",
  "./dashboard-view.js",
  "./storage-status-view.js",
  "./settings-view.js",
  "./system-status-view.js",
  "./backup-import-guards.js",
  "./backup-import-ui.js",
  "./release-status.js",
  "./operations-copy-actions.js",
  "./verify-workspace-summary.js",
  "./dialog-shell.js",
  "./project-picker.js",
  "./global-search.js",
  "./command-palette.js",
  "./keyboard-shortcuts.js",
  "./interaction-setup.js",
  "./event-reminders.js",
  "./footer-clock.js",
  "./db-catalog.js",
  "./review-handoff.js",
  "./review-result-view.js",
  "./review-execution-checklist.js",
  "./review-issue-payload.js",
  "./review-result-state.js",
  "./review-result-draft-state.js",
  "./review-creation-actions.js",
  "./review-package-view.js",
  "./review-artifact-view.js",
  "./review-artifact-state.js",
  "./review-copy-actions.js",
  "./review-submission-copy.js",
  "./review-recommendation-export.js",
  "./runtime-error-boundary.js",
  "./pwa-runtime.js",
  "./workspace-seed-data.js",
  "./home-view.js",
  "./ops-runtime-loader.js",
  "./app.js",
  "./data/repos.json",
  "./data/adoption-candidates.json",
  "./data/github-project-discovery.json",
  "./data/publish-evidence.json",
  "./data/pages-attestation-proof.json",
  "./data/launch-readiness-refresh.json",
  "./data/output-quality-audit.json",
  "./autoresearch-results/release-readiness-summary.json",
  "./autoresearch-results/verify-workspace-summary.json",
];
const OPTIONAL_APP_SHELL_ASSETS = [
  "./release-provenance.json",
];

function sameOrigin(request) {
  try {
    return new URL(request.url).origin === self.location.origin;
  } catch {
    return false;
  }
}

async function cacheAppShell() {
  const cache = await caches.open(APP_SHELL_CACHE);
  await cache.addAll(APP_SHELL_ASSETS);
  await Promise.all(OPTIONAL_APP_SHELL_ASSETS.map(async (asset) => {
    try {
      const response = await fetch(asset);
      if (response && response.ok) await cache.put(asset, response);
    } catch {
      // Optional release metadata is only present in packaged builds.
    }
  }));
}

async function clearOldCaches() {
  const names = await caches.keys();
  await Promise.all(
    names
      .filter((name) => name.startsWith("joopark-app-shell-") && name !== APP_SHELL_CACHE)
      .map((name) => caches.delete(name)),
  );
}

async function networkFirst(request) {
  const cache = await caches.open(APP_SHELL_CACHE);
  try {
    const response = await fetch(request);
    if (response && response.ok) {
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    return (await cache.match(request)) || (await cache.match("./index.html"));
  }
}

self.addEventListener("install", (event) => {
  event.waitUntil(cacheAppShell().then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(clearOldCaches().then(() => self.clients.claim()));
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET" || !sameOrigin(event.request)) return;
  event.respondWith(networkFirst(event.request));
});
