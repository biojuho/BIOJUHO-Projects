(function (root) {
  "use strict";

  const VERSION = "joopark-workspace-storage/v1";
  const DEFAULT_ARTIFACT_STORAGE_KEY = "joopark-workspace:v3";

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
    const getArtifactStorage = typeof options.getArtifactStorage === "function" ? options.getArtifactStorage : function () { return root.storage; };
    const artifactStorageKey = options.artifactStorageKey || DEFAULT_ARTIFACT_STORAGE_KEY;
    const artifactStorageShared = options.artifactStorageShared === true;
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
    const finiteNumberOr = typeof options.finiteNumberOr === "function"
      ? options.finiteNumberOr
      : function (value, fallback) {
        const parsed = Number(value);
        return Number.isFinite(parsed) ? parsed : fallback;
      };
    const positiveFiniteNumberOrNull = typeof options.positiveFiniteNumberOrNull === "function"
      ? options.positiveFiniteNumberOrNull
      : function (value) {
        const parsed = Number(value);
        return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
      };

    if (!dashboard || !state || !storeKey || !storeKeyV3) {
      throw new Error("workspace storage requires dashboard, state, and storage keys");
    }

    let artifactHydrationEligible = false;
    let artifactSeedPersistPending = false;

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

    function artifactStorageKeyIsValid(key) {
      return typeof key === "string"
        && key.length > 0
        && key.length < 200
        && !/[\s\/\\'"]/.test(key);
    }

    function artifactStorageRef() {
      try {
        return getArtifactStorage();
      } catch (_) {
        return null;
      }
    }

    function artifactStorageUsable(methods = ["get", "set"]) {
      const storage = artifactStorageRef();
      return !!(
        storage
        && artifactStorageKeyIsValid(artifactStorageKey)
        && methods.every((method) => typeof storage[method] === "function")
      );
    }

    function artifactStorageState(patch = {}) {
      const current = state.storageHealth && state.storageHealth.artifactStorage && typeof state.storageHealth.artifactStorage === "object"
        ? state.storageHealth.artifactStorage
        : {};
      const available = artifactStorageUsable();
      return {
        key: artifactStorageKey,
        shared: artifactStorageShared,
        available,
        status: available ? (current.status || "ready") : "unavailable",
        lastMirroredAt: current.lastMirroredAt || "",
        lastHydratedAt: current.lastHydratedAt || "",
        lastBytes: Number.isFinite(current.lastBytes) ? current.lastBytes : 0,
        lastError: current.lastError || "",
        ...patch,
      };
    }

    function setArtifactStorageState(patch = {}) {
      const next = artifactStorageState(patch);
      state.storageHealth = {
        ...state.storageHealth,
        artifactStorage: next,
      };
      if (getCurrentView() === "settings") renderSettings();
      return next;
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
        dashboardInsights: dashboard.dashboardInsights,
        dashboardResearchLoops: dashboard.dashboardResearchLoops,
        dashboardImprovementCandidates: dashboard.dashboardImprovementCandidates,
        dashboardDecisionReceipts: dashboard.dashboardDecisionReceipts,
        dashboardEvidenceSnapshots: dashboard.dashboardEvidenceSnapshots,
        dashboardHealthChecks: dashboard.dashboardHealthChecks,
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

    function persistArtifactStorageMirror(serialized, savedAt) {
      if (!artifactStorageUsable(["set"])) {
        setArtifactStorageState({ available: false, status: "unavailable", lastError: "" });
        return Promise.resolve(false);
      }
      const storage = artifactStorageRef();
      const bytes = storageByteLength(serialized);
      setArtifactStorageState({
        available: true,
        status: "pending",
        lastBytes: bytes,
        lastError: "",
      });
      return Promise.resolve()
        .then(() => storage.set(artifactStorageKey, serialized, artifactStorageShared))
        .then((result) => {
          if (!result) throw new Error("window.storage.set returned empty result");
          setArtifactStorageState({
            available: true,
            status: "mirrored",
            lastMirroredAt: savedAt || nowISO(),
            lastBytes: bytes,
            lastError: "",
          });
          return true;
        })
        .catch((err) => {
          setArtifactStorageState({
            available: true,
            status: "error",
            lastBytes: bytes,
            lastError: err && err.message ? err.message : "window.storage mirror failed",
          });
          return false;
        });
    }

    function persistFailureRecovery(err, savedAt) {
      let recoveryJson = "";
      let recoveryBytes = 0;
      try {
        recoveryJson = JSON.stringify(persistPayload(savedAt), null, 2);
        recoveryBytes = storageByteLength(recoveryJson);
      } catch (serializeErr) {
        recoveryJson = "";
        recoveryBytes = 0;
      }
      return {
        ready: !!recoveryJson,
        generatedAt: savedAt,
        filename: `joopark-workspace-emergency-${savedAt.slice(0, 10)}.json`,
        bytes: recoveryBytes,
        reason: err && err.name ? err.name : "localStorage write failed",
        message: err && err.message ? err.message : "localStorage write failed",
        json: recoveryJson,
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
        artifactStorage: artifactStorageState(),
      };

      try {
        const nav = getNavigator();
        const manager = nav && nav.storage ? nav.storage : null;
        if (manager && typeof manager.estimate === "function") {
          next.estimateSupported = true;
          const estimate = await manager.estimate();
          next.usageBytes = finiteNumberOr(estimate && estimate.usage, next.localBytes);
          next.quotaBytes = positiveFiniteNumberOrNull(estimate && estimate.quota);
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
        persistArtifactStorageMirror(serialized, savedAt);
        dashboard.lastSavedAt = savedAt;
        state.storageHealth = {
          ...state.storageHealth,
          localBytes: storageByteLength(serialized),
          lastError: "",
          recovery: null,
          checkedAt: savedAt,
        };
        return true;
      } catch (err) {
        consoleRef.warn("[workspace] persist failed:", err && err.message);
        const checkedAt = nowISO();
        try {
          persistArtifactStorageMirror(JSON.stringify(persistPayload(checkedAt)), checkedAt);
        } catch (_) {}
        state.storageHealth = {
          ...state.storageHealth,
          status: "error",
          localBytes: storedPayloadBytes(),
          lastError: err && err.message ? err.message : "localStorage write failed",
          recovery: persistFailureRecovery(err, checkedAt),
          checkedAt,
        };
        showToast(`저장 실패: ${err && err.name ? err.name : "브라우저 저장공간"} 확인 · Settings에서 긴급 백업`, "error");
        return false;
      }
    }

    async function hydrateArtifactStorage(options = {}) {
      const force = options.force === true;
      if (!force && !artifactHydrationEligible) {
        setArtifactStorageState({ status: artifactStorageUsable() ? "skipped" : "unavailable" });
        return false;
      }
      if (!artifactStorageUsable(["get", "set"])) {
        setArtifactStorageState({ available: false, status: "unavailable", lastError: "" });
        return false;
      }
      const storage = artifactStorageRef();
      setArtifactStorageState({ available: true, status: "hydrating", lastError: "" });
      try {
        const result = await storage.get(artifactStorageKey, artifactStorageShared);
        const value = result && result.value;
        const raw = typeof value === "string" ? safeJsonParse(value) : value;
        if (!raw || typeof raw !== "object" || raw.v !== 3) {
          throw new Error("window.storage payload is missing or incompatible");
        }
        artifactHydrationEligible = false;
        artifactSeedPersistPending = false;
        applyV3Payload(raw);
        persist();
        setArtifactStorageState({
          available: true,
          status: "hydrated",
          lastHydratedAt: nowISO(),
          lastBytes: storageByteLength(typeof value === "string" ? value : JSON.stringify(raw)),
          lastError: "",
        });
        return true;
      } catch (err) {
        const missingOrEmpty = /not found|missing|does not exist|non.?existent/i.test(err && err.message ? err.message : "");
        if (artifactSeedPersistPending) {
          artifactSeedPersistPending = false;
          persist();
        }
        setArtifactStorageState({
          available: true,
          status: missingOrEmpty ? "empty" : "error",
          lastError: missingOrEmpty ? "" : (err && err.message ? err.message : "window.storage hydrate failed"),
        });
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

    function isObjectValue(value) {
      return Boolean(value && typeof value === "object");
    }

    function applyV3Payload(rawV3) {
      const hasPersonalSlices =
        Array.isArray(rawV3.events) || Array.isArray(rawV3.todos) || Array.isArray(rawV3.notes);
      ["events", "todos", "notes"].forEach((key) => applyArrayField(rawV3, key));
      if (Array.isArray(rawV3.deletedItems)) dashboard.deletedItems = rawV3.deletedItems;
      ["reviewResults", "reviewIssueDraftOverrides"].forEach((key) => applyArrayField(rawV3, key));
      ["dashboardInsights", "dashboardResearchLoops", "dashboardImprovementCandidates", "dashboardDecisionReceipts", "dashboardEvidenceSnapshots", "dashboardHealthChecks"].forEach((key) => applyArrayField(rawV3, key));
      if (isObjectValue(rawV3.settings)) dashboard.settings = { ...dashboard.settings, ...rawV3.settings };
      ["habits", "projects", "issues"].forEach((key) => applyArrayField(rawV3, key));
      if (isObjectValue(rawV3.gantt) && !Array.isArray(rawV3.gantt)) dashboard.gantt = rawV3.gantt;
      ["team", "dbInstances", "schemas", "queries"].forEach((key) => applyArrayField(rawV3, key));
      if (Array.isArray(rawV3.backups)) dashboard.backups = rawV3.backups;
      applyArrayField(rawV3, "migrations");
      if (isObjectValue(rawV3.ui)) dashboard.ui = rawV3.ui;
      if (isObjectValue(rawV3.imports)) dashboard.imports = rawV3.imports;
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
      if (isObjectValue(rawV2.settings)) dashboard.settings = { ...dashboard.settings, ...rawV2.settings };
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
      artifactHydrationEligible = artifactStorageUsable(["get", "set"]);
      artifactSeedPersistPending = artifactHydrationEligible;
      if (!artifactSeedPersistPending) persist();
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
      persistArtifactStorageMirror,
      persistFailureRecovery,
      hydrateArtifactStorage,
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
