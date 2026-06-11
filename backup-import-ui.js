(function attachBackupImportUi(global) {
  "use strict";

  const VERSION = "joopark-backup-import-ui/v1";
  const DEFAULT_MAX_IMPORT_BYTES = 2 * 1024 * 1024;

  function fallbackRaw(value) {
    return { __raw: true, value: value == null ? "" : String(value) };
  }

  function fallbackEscape(value) {
    if (value === null || value === undefined) return "";
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function fallbackHtml(strings, ...values) {
    let output = "";
    for (let index = 0; index < strings.length; index += 1) {
      output += strings[index];
      if (index >= values.length) continue;
      const value = values[index];
      if (value === null || value === undefined || value === false) continue;
      if (value && value.__raw) output += value.value;
      else if (Array.isArray(value)) output += value.map((item) => (item && item.__raw ? item.value : fallbackEscape(item))).join("");
      else output += fallbackEscape(value);
    }
    return output;
  }

  function createBackupImportUi(deps = {}) {
    const html = typeof deps.html === "function" ? deps.html : fallbackHtml;
    const raw = typeof deps.raw === "function" ? deps.raw : fallbackRaw;
    const dashboard = isObjectValue(deps.dashboard) ? deps.dashboard : {};
    const guards = isObjectValue(deps.importGuards) ? deps.importGuards : {};
    const showToast = typeof deps.showToast === "function" ? deps.showToast : (() => {});
    const openModal = typeof deps.openModal === "function" ? deps.openModal : (() => {});
    const formatBytes = typeof deps.formatBytes === "function" ? deps.formatBytes : ((value) => `${value} bytes`);
    const normalizeAllData = typeof deps.normalizeAllData === "function" ? deps.normalizeAllData : (() => {});
    const rebuildIndexes = typeof deps.rebuildIndexes === "function" ? deps.rebuildIndexes : (() => {});
    const commit = typeof deps.commit === "function" ? deps.commit : (() => {});
    const fileReaderFactory = typeof deps.fileReaderFactory === "function"
      ? deps.fileReaderFactory
      : () => new global.FileReader();

    function isObjectValue(value) {
      return Boolean(value && typeof value === "object");
    }

    function isPlainObject(value) {
      return Boolean(isObjectValue(value) && !Array.isArray(value));
    }

    function isImportBackupShape(obj) {
      return typeof guards.isBackupShape === "function" ? guards.isBackupShape(obj) : false;
    }

    function importBackupSummaryItems(obj) {
      return typeof guards.backupSummaryItems === "function" ? guards.backupSummaryItems(obj) : [];
    }

    function importRecordLimitViolations(obj) {
      return typeof guards.recordLimitViolations === "function" ? guards.recordLimitViolations(obj) : [];
    }

    function importRecordLimitMessage(violations) {
      return typeof guards.recordLimitMessage === "function" ? guards.recordLimitMessage(violations) : "가져오기 항목 수가 너무 많습니다";
    }

    function validateImportPayload(obj) {
      return typeof guards.validateImportPayload === "function"
        ? guards.validateImportPayload(obj)
        : { ok: true, normalized: obj, violations: [] };
    }

    function importValidationMessage(violations) {
      return typeof guards.importValidationMessage === "function"
        ? guards.importValidationMessage(violations)
        : "가져오기 데이터 검증 실패";
    }

    function rejectImportFile(input, message) {
      showToast(message, "error");
      if (input) input.value = "";
    }

    function maxImportBytesOption(value, fallback = DEFAULT_MAX_IMPORT_BYTES) {
      const parsed = Number(value);
      if (Number.isFinite(parsed) && parsed > 0) return parsed;
      const fallbackNumber = Number(fallback);
      return Number.isFinite(fallbackNumber) && fallbackNumber > 0 ? fallbackNumber : 0;
    }

    function importBackupSummaryHTML(obj) {
      return importBackupSummaryItems(obj)
        .map(([label, count]) => html`<span>${label} <strong>${count}</strong></span>`)
        .join(" · ");
    }

    function importArrayField(obj, key) {
      if (Array.isArray(obj[key])) dashboard[key] = obj[key];
    }

    function importObjectField(obj, key) {
      if (isObjectValue(obj[key])) dashboard[key] = obj[key];
    }

    function applyImported(obj) {
      if (!isImportBackupShape(obj)) {
        showToast("백업 형식이 아닙니다", "error");
        return;
      }
      const validation = validateImportPayload(obj);
      if (!validation.ok) {
        showToast(importValidationMessage(validation.violations), "error");
        return;
      }
      const source = validation.normalized || obj;
      ["events", "todos", "notes"].forEach((key) => importArrayField(source, key));
      importArrayField(source, "deletedItems");
      ["reviewResults", "reviewIssueDraftOverrides"].forEach((key) => importArrayField(source, key));
      ["dashboardInsights", "dashboardResearchLoops", "dashboardImprovementCandidates", "dashboardDecisionReceipts", "dashboardEvidenceSnapshots", "dashboardHealthChecks"].forEach((key) => importArrayField(source, key));
      if (isObjectValue(source.settings)) {
        dashboard.settings = { ...dashboard.settings, ...source.settings };
      }
      ["habits", "projects", "issues"].forEach((key) => importArrayField(source, key));
      if (isPlainObject(source.gantt)) dashboard.gantt = source.gantt;
      ["team", "dbInstances", "schemas", "queries"].forEach((key) => importArrayField(source, key));
      importArrayField(source, "backups");
      importArrayField(source, "migrations");
      ["ui", "imports"].forEach((key) => importObjectField(source, key));
      normalizeAllData();
      rebuildIndexes();
      commit();
      showToast("백업을 가져왔습니다 (기존 데이터 대체)", "info");
    }

    function handleImportFile(event) {
      const input = event.target;
      const file = input.files && input.files[0];
      const maxImportBytes = maxImportBytesOption(guards.maxImportBytes);
      if (!file) return;
      if (Number.isFinite(file.size) && maxImportBytes > 0 && file.size > maxImportBytes) {
        rejectImportFile(input, `가져오기 파일은 ${formatBytes(maxImportBytes)} 이하만 지원합니다`);
        return;
      }
      const reader = fileReaderFactory();
      reader.onload = () => {
        let obj = null;
        try {
          obj = JSON.parse(reader.result);
        } catch (_) {
          rejectImportFile(input, "JSON 파싱 실패");
          return;
        }
        if (!isImportBackupShape(obj)) {
          rejectImportFile(input, "백업 형식이 아닙니다");
          return;
        }
        const recordViolations = importRecordLimitViolations(obj);
        if (recordViolations.length > 0) {
          rejectImportFile(input, importRecordLimitMessage(recordViolations));
          return;
        }
        const validation = validateImportPayload(obj);
        if (!validation.ok) {
          rejectImportFile(input, importValidationMessage(validation.violations));
          return;
        }
        const source = validation.normalized || obj;
        openModal("백업 가져오기", html`
          <div class="modal-confirm-body">
            <p data-import-summary>가져올 데이터 — ${raw(importBackupSummaryHTML(source))}</p>
            <p class="muted-note">현재 저장된 워크스페이스 데이터가 가져온 항목으로 <strong>대체</strong>됩니다. 되돌릴 수 없으니, 필요하면 먼저 내보내기로 백업하세요.</p>
          </div>
        `, () => {
          applyImported(source);
          return true;
        });
        input.value = "";
      };
      reader.onerror = () => {
        rejectImportFile(input, "파일 읽기 실패");
      };
      reader.readAsText(file);
    }

    return Object.freeze({
      rejectImportFile,
      importBackupSummaryHTML,
      applyImported,
      handleImportFile,
      maxImportBytesOption,
    });
  }

  global.JooParkBackupImportUi = Object.freeze({
    version: VERSION,
    create: createBackupImportUi,
  });
})(typeof window !== "undefined" ? window : globalThis);
