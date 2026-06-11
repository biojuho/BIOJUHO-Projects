/* ================================================================
 * JooPark Workspace — lazy operations/review runtime loader.
 * Static non-module runtime loaded before app.js.
 * ================================================================ */

(function initJooParkOpsRuntime(global) {
  "use strict";

  const VERSION = "joopark-ops-runtime-loader/v1";
  const GROUPS = Object.freeze({
    release: Object.freeze([
      "release-status.js",
      "operations-copy-actions.js",
      "verify-workspace-summary.js",
    ]),
    operations: Object.freeze([
      "operations-copy-actions.js",
    ]),
    review: Object.freeze([
      "review-recommendation-export.js",
      "review-execution-checklist.js",
      "review-issue-payload.js",
      "review-result-view.js",
      "review-handoff.js",
      "review-artifact-view.js",
      "review-package-view.js",
      "review-artifact-state.js",
      "review-result-draft-state.js",
      "review-creation-actions.js",
      "review-copy-actions.js",
      "review-submission-copy.js",
      "review-result-state.js",
    ]),
  });

  const loaded = new Set();
  const pending = new Map();
  const lastErrors = new Map();
  const loadEvents = [];
  const groupLoads = new Map();

  function nowIso() {
    return new Date().toISOString();
  }

  function pushEvent(event) {
    loadEvents.push({ at: nowIso(), ...event });
    if (loadEvents.length > 40) loadEvents.splice(0, loadEvents.length - 40);
  }

  function normalizePath(path) {
    return String(path || "").replace(/^\.\//, "").replace(/[?#].*$/, "");
  }

  function rememberExistingScripts() {
    if (!global.document) return;
    global.document.querySelectorAll("script[src]").forEach((script) => {
      loaded.add(normalizePath(script.getAttribute("src")));
    });
  }

  function srcFor(path) {
    return `./${normalizePath(path)}`;
  }

  function loadScript(path) {
    const normalized = normalizePath(path);
    if (!normalized) return Promise.resolve({ path: normalized, status: "skipped" });
    if (loaded.has(normalized)) return Promise.resolve({ path: normalized, status: "loaded" });
    if (pending.has(normalized)) return pending.get(normalized);

    const promise = new Promise((resolve, reject) => {
      const script = global.document.createElement("script");
      script.src = srcFor(normalized);
      script.async = false;
      script.dataset.opsRuntime = "lazy";
      pushEvent({ type: "file_start", path: normalized, status: "loading" });
      script.onload = () => {
        loaded.add(normalized);
        lastErrors.delete(normalized);
        pending.delete(normalized);
        pushEvent({ type: "file_loaded", path: normalized, status: "loaded" });
        resolve({ path: normalized, status: "loaded" });
      };
      script.onerror = () => {
        const message = `Failed to load operations runtime: ${normalized}`;
        lastErrors.set(normalized, message);
        pending.delete(normalized);
        pushEvent({ type: "file_failed", path: normalized, status: "failed", error: message });
        reject(new Error(message));
      };
      global.document.head.appendChild(script);
    });
    pending.set(normalized, promise);
    return promise;
  }

  async function load(groupName) {
    rememberExistingScripts();
    const group = GROUPS[groupName] || [];
    const results = [];
    const startedAt = nowIso();
    const groupResult = {
      version: VERSION,
      group: groupName,
      status: "pass",
      files: group.slice(),
      loaded: [],
      results,
      startedAt,
      finishedAt: "",
      durationMs: 0,
      error: "",
    };
    const started = Date.now();
    pushEvent({ type: "group_start", group: groupName, status: "loading", total: group.length });
    try {
      for (const path of group) {
        results.push(await loadScript(path));
      }
      return groupResult;
    } catch (error) {
      groupResult.status = "fail";
      groupResult.error = error && error.message ? error.message : String(error);
      throw error;
    } finally {
      groupResult.loaded = Array.from(loaded).sort();
      groupResult.finishedAt = nowIso();
      groupResult.durationMs = Date.now() - started;
      groupLoads.set(groupName, { ...groupResult, results: results.slice() });
      pushEvent({
        type: "group_done",
        group: groupName,
        status: groupResult.status,
        loadedCount: group.filter((path) => loaded.has(path)).length,
        total: group.length,
        error: groupResult.error,
      });
    }
  }

  function statusByPath(path) {
    const normalized = normalizePath(path);
    if (loaded.has(normalized)) return "loaded";
    if (pending.has(normalized)) return "loading";
    if (lastErrors.has(normalized)) return "failed";
    return "idle";
  }

  function stats() {
    rememberExistingScripts();
    const lazyFiles = new Set(Object.values(GROUPS).flat());
    const fileStats = Array.from(lazyFiles).sort().map((path) => ({
      path,
      status: statusByPath(path),
      error: lastErrors.get(path) || "",
    }));
    const groupStats = Object.entries(GROUPS).map(([key, files]) => {
      const loadedCount = files.filter((path) => loaded.has(path)).length;
      const failed = files.filter((path) => lastErrors.has(path));
      const pendingFiles = files.filter((path) => pending.has(path));
      const lastLoad = groupLoads.get(key) || null;
      return {
        group: key,
        total: files.length,
        loadedCount,
        pendingCount: pendingFiles.length,
        failedCount: failed.length,
        ready: files.length > 0 && loadedCount === files.length && failed.length === 0,
        status: failed.length ? "failed" : pendingFiles.length ? "loading" : loadedCount === files.length ? "loaded" : "idle",
        lastStatus: lastLoad ? lastLoad.status : "none",
        lastDurationMs: lastLoad ? lastLoad.durationMs : 0,
        lastError: lastLoad ? lastLoad.error : "",
      };
    });
    return {
      version: VERSION,
      groups: Object.fromEntries(Object.entries(GROUPS).map(([key, files]) => [key, files.slice()])),
      lazyFileCount: lazyFiles.size,
      loadedLazyFileCount: Array.from(lazyFiles).filter((path) => loaded.has(path)).length,
      pending: Array.from(pending.keys()).sort(),
      failed: Array.from(lastErrors.entries()).map(([path, error]) => ({ path, error })),
      fileStats,
      groupStats,
      lastLoads: Object.fromEntries(Array.from(groupLoads.entries()).map(([key, value]) => [key, { ...value, results: value.results.slice() }])),
      events: loadEvents.slice(),
      loaded: Array.from(loaded).sort(),
    };
  }

  rememberExistingScripts();

  global.JooParkOpsRuntime = Object.freeze({
    version: VERSION,
    load,
    stats,
  });
})(typeof window !== "undefined" ? window : globalThis);
