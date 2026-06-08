/* ================================================================
 * JooPark Workspace — backup import guard helpers
 * Static non-module runtime loaded before app.js.
 * ================================================================ */

(function initJooParkImportGuards(global) {
  "use strict";

  const VERSION = "joopark-import-guards/v1";
  const MAX_IMPORT_BYTES = 2 * 1024 * 1024;
  const IMPORT_ARRAY_KEYS = [
    "events", "todos", "notes", "deletedItems", "reviewResults", "reviewIssueDraftOverrides", "habits", "projects", "issues",
    "team", "dbInstances", "schemas", "queries", "backups", "migrations",
  ];
  const IMPORT_RECORD_LIMITS = [
    { key: "events", label: "일정", max: 1000, count: (obj) => importArrayCount(obj, "events") },
    { key: "todos", label: "할 일", max: 1000, count: (obj) => importArrayCount(obj, "todos") },
    { key: "notes", label: "메모", max: 500, count: (obj) => importArrayCount(obj, "notes") },
    { key: "deletedItems", label: "최근 삭제", max: 40, count: (obj) => importArrayCount(obj, "deletedItems") },
    { key: "reviewResults", label: "검증 결과", max: 500, count: (obj) => importArrayCount(obj, "reviewResults") },
    { key: "reviewIssueDraftOverrides", label: "이슈 초안 담당 확인", max: 500, count: (obj) => importArrayCount(obj, "reviewIssueDraftOverrides") },
    { key: "habits", label: "습관", max: 200, count: (obj) => importArrayCount(obj, "habits") },
    { key: "projects", label: "프로젝트", max: 500, count: (obj) => importArrayCount(obj, "projects") },
    { key: "issues", label: "이슈", max: 2000, count: (obj) => importArrayCount(obj, "issues") },
    { key: "ganttTasks", label: "간트 작업", max: 1000, count: importGanttTaskCount },
    { key: "team", label: "팀", max: 500, count: (obj) => importArrayCount(obj, "team") },
    { key: "dbInstances", label: "DB 인스턴스", max: 200, count: (obj) => importArrayCount(obj, "dbInstances") },
    { key: "schemas", label: "스키마", max: 100, count: (obj) => importArrayCount(obj, "schemas") },
    { key: "schemaTables", label: "테이블", max: 5000, count: importSchemaTableCount },
    { key: "queries", label: "쿼리", max: 1000, count: (obj) => importArrayCount(obj, "queries") },
    { key: "backups", label: "백업", max: 1000, count: (obj) => importArrayCount(obj, "backups") },
    { key: "migrations", label: "마이그레이션", max: 500, count: (obj) => importArrayCount(obj, "migrations") },
  ];

  function importArrayCount(obj, key) {
    return Array.isArray(obj && obj[key]) ? obj[key].length : null;
  }

  function importGanttTaskCount(obj) {
    return obj && obj.gantt && typeof obj.gantt === "object" && !Array.isArray(obj.gantt) && Array.isArray(obj.gantt.tasks)
      ? obj.gantt.tasks.length
      : null;
  }

  function importDatabaseTableCount(db) {
    return Array.isArray(db && db.tables) ? db.tables.length : 0;
  }

  function importSchemaDatabaseTableCount(schema) {
    return Array.isArray(schema && schema.databases)
      ? schema.databases.reduce((sum, db) => sum + importDatabaseTableCount(db), 0)
      : 0;
  }

  function importSchemaTableCount(obj) {
    return Array.isArray(obj && obj.schemas)
      ? obj.schemas.reduce((sum, schema) => sum + importSchemaDatabaseTableCount(schema), 0)
      : null;
  }

  function isBackupShape(obj) {
    return Boolean(obj && typeof obj === "object" && !Array.isArray(obj) &&
      IMPORT_ARRAY_KEYS.some((key) => Array.isArray(obj[key])));
  }

  function publicRecordLimits() {
    return IMPORT_RECORD_LIMITS.map((entry) => ({
      key: entry.key,
      label: entry.label,
      max: entry.max,
    }));
  }

  function backupSummaryItems(obj) {
    return IMPORT_RECORD_LIMITS
      .filter((entry) => entry.key !== "schemas")
      .map((entry) => [entry.label, entry.count(obj)])
      .filter((entry) => entry[1] !== null);
  }

  function recordLimitViolations(obj) {
    return IMPORT_RECORD_LIMITS
      .map((entry) => {
        const count = entry.count(obj);
        return count !== null && count > entry.max
          ? { key: entry.key, label: entry.label, max: entry.max, count }
          : null;
      })
      .filter(Boolean);
  }

  function recordLimitMessage(violations) {
    const visible = violations.slice(0, 3).map((entry) => `${entry.label} ${entry.count}/${entry.max}`);
    const suffix = violations.length > visible.length ? ` 외 ${violations.length - visible.length}개` : "";
    return `가져오기 항목 수가 너무 많습니다: ${visible.join(", ")}${suffix}`;
  }

  global.JooParkImportGuards = Object.freeze({
    version: VERSION,
    maxImportBytes: MAX_IMPORT_BYTES,
    arrayKeys: Object.freeze(IMPORT_ARRAY_KEYS.slice()),
    recordLimits: Object.freeze(publicRecordLimits()),
    importArrayCount,
    importGanttTaskCount,
    importSchemaTableCount,
    isBackupShape,
    backupSummaryItems,
    recordLimitViolations,
    recordLimitMessage,
  });
})(typeof window !== "undefined" ? window : globalThis);
