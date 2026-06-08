(function attachBackupImportUi(global) {
  "use strict";

  const VERSION = "joopark-backup-import-ui/v1";

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
    const dashboard = deps.dashboard && typeof deps.dashboard === "object" ? deps.dashboard : {};
    const guards = deps.importGuards && typeof deps.importGuards === "object" ? deps.importGuards : {};
    const showToast = typeof deps.showToast === "function" ? deps.showToast : (() => {});
    const openModal = typeof deps.openModal === "function" ? deps.openModal : (() => {});
    const formatBytes = typeof deps.formatBytes === "function" ? deps.formatBytes : ((value) => `${value} bytes`);
    const normalizeAllData = typeof deps.normalizeAllData === "function" ? deps.normalizeAllData : (() => {});
    const rebuildIndexes = typeof deps.rebuildIndexes === "function" ? deps.rebuildIndexes : (() => {});
    const commit = typeof deps.commit === "function" ? deps.commit : (() => {});
    const fileReaderFactory = typeof deps.fileReaderFactory === "function"
      ? deps.fileReaderFactory
      : () => new global.FileReader();

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

    function rejectImportFile(input, message) {
      showToast(message, "error");
      if (input) input.value = "";
    }

    function importBackupSummaryHTML(obj) {
      return importBackupSummaryItems(obj)
        .map(([label, count]) => html`<span>${label} <strong>${count}</strong></span>`)
        .join(" · ");
    }

    function importArrayField(obj, key) {
      if (Array.isArray(obj[key])) dashboard[key] = obj[key];
    }

    function applyImported(obj) {
      if (!isImportBackupShape(obj)) {
        showToast("백업 형식이 아닙니다", "error");
        return;
      }
      ["events", "todos", "notes"].forEach((key) => importArrayField(obj, key));
      if (Array.isArray(obj.deletedItems)) dashboard.deletedItems = obj.deletedItems;
      ["reviewResults", "reviewIssueDraftOverrides"].forEach((key) => importArrayField(obj, key));
      if (obj.settings && typeof obj.settings === "object") {
        dashboard.settings = { ...dashboard.settings, ...obj.settings };
      }
      ["habits", "projects", "issues"].forEach((key) => importArrayField(obj, key));
      if (obj.gantt && typeof obj.gantt === "object" && !Array.isArray(obj.gantt)) dashboard.gantt = obj.gantt;
      ["team", "dbInstances", "schemas", "queries"].forEach((key) => importArrayField(obj, key));
      if (Array.isArray(obj.backups)) dashboard.backups = obj.backups;
      importArrayField(obj, "migrations");
      if (obj.ui && typeof obj.ui === "object") dashboard.ui = obj.ui;
      if (obj.imports && typeof obj.imports === "object") dashboard.imports = obj.imports;
      normalizeAllData();
      rebuildIndexes();
      commit();
      showToast("백업을 가져왔습니다 (기존 데이터 대체)", "info");
    }

    function handleImportFile(event) {
      const input = event.target;
      const file = input.files && input.files[0];
      const maxImportBytes = Number(guards.maxImportBytes || 0);
      if (!file) return;
      if (Number.isFinite(file.size) && maxImportBytes > 0 && file.size > maxImportBytes) {
        showToast(`가져오기 파일은 ${formatBytes(maxImportBytes)} 이하만 지원합니다`, "error");
        input.value = "";
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
        openModal("백업 가져오기", html`
          <div class="modal-confirm-body">
            <p data-import-summary>가져올 데이터 — ${raw(importBackupSummaryHTML(obj))}</p>
            <p class="muted-note">현재 저장된 워크스페이스 데이터가 가져온 항목으로 <strong>대체</strong>됩니다. 되돌릴 수 없으니, 필요하면 먼저 내보내기로 백업하세요.</p>
          </div>
        `, () => {
          applyImported(obj);
          return true;
        });
        input.value = "";
      };
      reader.onerror = () => {
        showToast("파일 읽기 실패", "error");
        input.value = "";
      };
      reader.readAsText(file);
    }

    return Object.freeze({
      rejectImportFile,
      importBackupSummaryHTML,
      applyImported,
      handleImportFile,
    });
  }

  global.JooParkBackupImportUi = Object.freeze({
    version: VERSION,
    create: createBackupImportUi,
  });
})(typeof window !== "undefined" ? window : globalThis);
