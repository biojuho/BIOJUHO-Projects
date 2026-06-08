(function (root) {
  "use strict";

  const VERSION = "joopark-workspace-storage/v1";

  function byteLength(value) {
    const text = value == null ? "" : String(value);
    try { return new Blob([text]).size; } catch (_) { return text.length; }
  }

  function safeJsonParse(text) {
    try { return JSON.parse(text || "null"); } catch (_) { return null; }
  }

  function createWorkspaceStorage(deps) {
    const options = deps || {};
    const dashboard = options.dashboard;
    const state = options.state;
    const storeKey = options.storeKey;
    const storeKeyV3 = options.storeKeyV3;
    const getStorage = typeof options.getStorage === "function" ? options.getStorage : function () { return root.localStorage; };
    const getNavigator = typeof options.getNavigator === "function" ? options.getNavigator : function () { return root.navigator; };
    const nowISO = typeof options.nowISO === "function" ? options.nowISO : function () { return new Date().toISOString(); };
    const normalizeAllData = typeof options.normalizeAllData === "function" ? options.normalizeAllData : function () {};
    const rebuildIndexes = typeof options.rebuildIndexes === "function" ? options.rebuildIndexes : function () {};
    const seedPersonalData = typeof options.seedPersonalData === "function" ? options.seedPersonalData : function () {};
    const setPmWasPersisted = typeof options.setPmWasPersisted === "function" ? options.setPmWasPersisted : function () {};
    const getCurrentView = typeof options.getCurrentView === "function" ? options.getCurrentView : function () { return dashboard && dashboard.currentView; };
    const renderSettings = typeof options.renderSettings === "function" ? options.renderSettings : function () {};
    const showToast = typeof options.showToast === "function" ? options.showToast : function () {};
    const consoleRef = options.consoleRef || root.console || { warn: function () {} };

    if (!dashboard || !state || !storeKey || !storeKeyV3) {
      throw new Error("workspace storage requires dashboard, state, and storage keys");
    }

    function storageByteLength(value) {
      return byteLength(value);
    }

    function storedPayloadBytes() {
      try {
        const storage = getStorage();
        return storageByteLength(storage.getItem(storeKeyV3) || "");
      } catch (_) {
        return 0;
      }
    }

    function formatBytes(bytes) {
      if (!Number.isFinite(bytes) || bytes < 0) return "확인 중";
      if (bytes < 1024) return `${bytes} B`;
      if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
      return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
    }

    function storagePercent(usageBytes, quotaBytes) {
      if (!Number.isFinite(usageBytes) || !Number.isFinite(quotaBytes) || quotaBytes <= 0) return null;
      return Math.max(0, Math.min(100, (usageBytes / quotaBytes) * 100));
    }

    function storageTone(health) {
      if (health && health.lastError) return "error";
      const pct = storagePercent(health && health.usageBytes, health && health.quotaBytes);
      if (pct !== null && pct >= 90) return "error";
      if (pct !== null && pct >= 75) return "warn";
      if (health && health.estimateSupported === false) return "warn";
      return "ok";
    }

    function storageStatusLabel(health) {
      if (health && health.lastError) return "저장 실패";
      const pct = storagePercent(health && health.usageBytes, health && health.quotaBytes);
      if (pct !== null && pct >= 90) return "위험";
      if (pct !== null && pct >= 75) return "주의";
      if (health && health.status === "checking") return "확인 중";
      if (health && health.estimateSupported === false) return "기본 저장";
      return "정상";
    }

    function storagePersistentLabel(health) {
      if (!health || health.persistedSupported === false) return "미지원";
      if (health.persisted === true) return "영속";
      if (health.persisted === false) return "일반";
      return "확인 중";
    }

    function persistPayload(savedAt) {
      return {
        v: 3,
        events: dashboard.events,
        todos: dashboard.todos,
        notes: dashboard.notes,
        deletedItems: dashboard.deletedItems,
        reviewResults: dashboard.reviewResults,
        reviewIssueDraftOverrides: dashboard.reviewIssueDraftOverrides,
        settings: dashboard.settings,
        habits: dashboard.habits,
        projects: dashboard.projects,
        issues: dashboard.issues,
        gantt: dashboard.gantt,
        team: dashboard.team,
        dbInstances: dashboard.dbInstances,
        schemas: dashboard.schemas,
        queries: dashboard.queries,
        backups: dashboard.backups,
        migrations: dashboard.migrations,
        ui: dashboard.ui,
        imports: dashboard.imports,
        savedAt,
      };
    }

    async function refreshStorageHealth(options = {}) {
      const next = {
        ...state.storageHealth,
        status: "checking",
        localBytes: storedPayloadBytes(),
        usageBytes: null,
        quotaBytes: null,
        persisted: null,
        estimateSupported: false,
        persistedSupported: false,
        checkedAt: nowISO(),
        lastError: "",
      };

      try {
        const nav = getNavigator();
        const manager = nav && nav.storage ? nav.storage : null;
        if (manager && typeof manager.estimate === "function") {
          next.estimateSupported = true;
          const estimate = await manager.estimate();
          next.usageBytes = Number(estimate && estimate.usage) || next.localBytes;
          next.quotaBytes = Number(estimate && estimate.quota) || null;
        } else {
          next.usageBytes = next.localBytes;
        }
        if (manager && typeof manager.persisted === "function") {
          next.persistedSupported = true;
          next.persisted = await manager.persisted();
        }
        next.status = "ready";
      } catch (err) {
        next.status = "error";
        next.usageBytes = next.localBytes;
        next.lastError = err && err.message ? err.message : "storage estimate failed";
      }

      state.storageHealth = next;
      if (options.render && getCurrentView() === "settings") renderSettings();
      return next;
    }

    async function requestStoragePersistence() {
      try {
        const nav = getNavigator();
        const manager = nav && nav.storage ? nav.storage : null;
        if (!manager || typeof manager.persist !== "function") {
          showToast("이 브라우저는 영속 저장 요청을 지원하지 않습니다", "warn");
          await refreshStorageHealth({ render: true });
          return;
        }
        const granted = await manager.persist();
        await refreshStorageHealth({ render: true });
        showToast(granted ? "영속 저장이 활성화되었습니다" : "영속 저장 요청이 허용되지 않았습니다", granted ? "info" : "warn");
      } catch (err) {
        state.storageHealth = {
          ...state.storageHealth,
          status: "error",
          lastError: err && err.message ? err.message : "persistent storage request failed",
          checkedAt: nowISO(),
        };
        if (getCurrentView() === "settings") renderSettings();
        showToast("영속 저장 요청에 실패했습니다", "error");
      }
    }

    function persist() {
      try {
        const savedAt = nowISO();
        const serialized = JSON.stringify(persistPayload(savedAt));
        getStorage().setItem(storeKeyV3, serialized);
        dashboard.lastSavedAt = savedAt;
        state.storageHealth = {
          ...state.storageHealth,
          localBytes: storageByteLength(serialized),
          lastError: "",
          checkedAt: savedAt,
        };
        return true;
      } catch (err) {
        consoleRef.warn("[workspace] persist failed:", err && err.message);
        state.storageHealth = {
          ...state.storageHealth,
          status: "error",
          localBytes: storedPayloadBytes(),
          lastError: err && err.message ? err.message : "localStorage write failed",
          checkedAt: nowISO(),
        };
        showToast(`저장 실패: ${err && err.name ? err.name : "브라우저 저장공간"} 확인`, "error");
        return false;
      }
    }

    function readStoredJson(key) {
      try {
        return safeJsonParse(getStorage().getItem(key) || "null");
      } catch (_) {
        return null;
      }
    }

    function applyArrayField(source, key) {
      if (Array.isArray(source[key])) dashboard[key] = source[key];
    }

    function applyV3Payload(rawV3) {
      const hasPersonalSlices =
        Array.isArray(rawV3.events) || Array.isArray(rawV3.todos) || Array.isArray(rawV3.notes);
      ["events", "todos", "notes"].forEach((key) => applyArrayField(rawV3, key));
      if (Array.isArray(rawV3.deletedItems)) dashboard.deletedItems = rawV3.deletedItems;
      ["reviewResults", "reviewIssueDraftOverrides"].forEach((key) => applyArrayField(rawV3, key));
      if (rawV3.settings && typeof rawV3.settings === "object") dashboard.settings = { ...dashboard.settings, ...rawV3.settings };
      ["habits", "projects", "issues"].forEach((key) => applyArrayField(rawV3, key));
      if (rawV3.gantt && typeof rawV3.gantt === "object" && !Array.isArray(rawV3.gantt)) dashboard.gantt = rawV3.gantt;
      ["team", "dbInstances", "schemas", "queries"].forEach((key) => applyArrayField(rawV3, key));
      if (Array.isArray(rawV3.backups)) dashboard.backups = rawV3.backups;
      applyArrayField(rawV3, "migrations");
      if (rawV3.ui && typeof rawV3.ui === "object") dashboard.ui = rawV3.ui;
      if (rawV3.imports && typeof rawV3.imports === "object") dashboard.imports = rawV3.imports;
      dashboard.lastSavedAt = rawV3.savedAt || null;
      setPmWasPersisted(true);
      normalizeAllData();
      rebuildIndexes();
      if (!hasPersonalSlices && !dashboard.events.length && !dashboard.todos.length && !dashboard.notes.length) {
        seedPersonalData();
        persist();
      }
      return true;
    }

    function applyV2Payload(rawV2) {
      ["events", "todos", "notes"].forEach((key) => applyArrayField(rawV2, key));
      if (rawV2.settings && typeof rawV2.settings === "object") dashboard.settings = { ...dashboard.settings, ...rawV2.settings };
      dashboard.lastSavedAt = rawV2.savedAt || null;
      setPmWasPersisted(false);
      normalizeAllData();
      rebuildIndexes();
      persist();
      return true;
    }

    function loadPersisted() {
      const rawV3 = readStoredJson(storeKeyV3);
      if (rawV3 && typeof rawV3 === "object" && rawV3.v === 3) {
        return applyV3Payload(rawV3);
      }

      const rawV2 = readStoredJson(storeKey);
      if (rawV2 && typeof rawV2 === "object" && (rawV2.events || rawV2.todos || rawV2.notes)) {
        return applyV2Payload(rawV2);
      }

      seedPersonalData();
      setPmWasPersisted(false);
      normalizeAllData();
      rebuildIndexes();
      persist();
      return false;
    }

    return {
      version: VERSION,
      storageByteLength,
      storedPayloadBytes,
      formatBytes,
      storagePercent,
      storageTone,
      storageStatusLabel,
      storagePersistentLabel,
      persistPayload,
      refreshStorageHealth,
      requestStoragePersistence,
      persist,
      loadPersisted,
    };
  }

  root.JooParkWorkspaceStorage = {
    version: VERSION,
    create: createWorkspaceStorage,
  };
})(window);
