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
    "dashboardInsights", "dashboardResearchLoops", "dashboardImprovementCandidates", "dashboardDecisionReceipts", "dashboardEvidenceSnapshots", "dashboardHealthChecks",
    "team", "dbInstances", "schemas", "queries", "backups", "migrations",
  ];
  const IMPORT_RECORD_LIMITS = [
    { key: "events", label: "일정", max: 1000, count: (obj) => importArrayCount(obj, "events") },
    { key: "todos", label: "할 일", max: 1000, count: (obj) => importArrayCount(obj, "todos") },
    { key: "notes", label: "메모", max: 500, count: (obj) => importArrayCount(obj, "notes") },
    { key: "deletedItems", label: "최근 삭제", max: 40, count: (obj) => importArrayCount(obj, "deletedItems") },
    { key: "reviewResults", label: "검증 결과", max: 500, count: (obj) => importArrayCount(obj, "reviewResults") },
    { key: "reviewIssueDraftOverrides", label: "이슈 초안 담당 확인", max: 500, count: (obj) => importArrayCount(obj, "reviewIssueDraftOverrides") },
    { key: "dashboardInsights", label: "대시보드 인사이트", max: 500, count: (obj) => importArrayCount(obj, "dashboardInsights") },
    { key: "dashboardResearchLoops", label: "AutoResearch 루프", max: 200, count: (obj) => importArrayCount(obj, "dashboardResearchLoops") },
    { key: "dashboardImprovementCandidates", label: "개선 후보", max: 500, count: (obj) => importArrayCount(obj, "dashboardImprovementCandidates") },
    { key: "dashboardDecisionReceipts", label: "의사결정 영수증", max: 500, count: (obj) => importArrayCount(obj, "dashboardDecisionReceipts") },
    { key: "dashboardEvidenceSnapshots", label: "Evidence snapshot", max: 300, count: (obj) => importArrayCount(obj, "dashboardEvidenceSnapshots") },
    { key: "dashboardHealthChecks", label: "Dashboard health", max: 500, count: (obj) => importArrayCount(obj, "dashboardHealthChecks") },
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
  const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;
  const TIME_RE = /^\d{2}:\d{2}$/;
  const EXECUTION_CHECKLIST_FIELDS = new Set(["id", "text", "done"]);
  const DASHBOARD_SCORE_FIELDS = new Set(["userValue", "urgency", "difficulty", "regressionRisk", "performance", "accessibility", "security", "maintainability", "releaseReadiness", "localStorageStability", "mobileUX", "evidenceTraceability", "total", "weighted"]);
  const DASHBOARD_NEXT_ACTION_FIELDS = new Set(["label", "command", "view", "viewName", "status"]);
  const DASHBOARD_RECORD_FIELDS = {
    id: { type: "string", max: 80, nonEmpty: true },
    createdAt: { type: "string", max: 80 },
    sourceRefs: { type: "stringArray", maxItems: 30, max: 180 },
    summary: { type: "string", max: 500 },
    scoreBreakdown: { type: "dashboardScore" },
    confidence: { type: "number" },
    verificationStatus: { type: "string", max: 80 },
    riskFlags: { type: "stringArray", maxItems: 20, max: 120 },
    nextAction: { type: "dashboardNextAction" },
    receiptHash: { type: "string", max: 100 },
    loopSteps: { type: "stringArray", maxItems: 20, max: 120 },
    activeUntilUserStops: { type: "boolean" },
    cardCount: { type: "number" },
    candidateCount: { type: "number" },
    externalResearchSources: { type: "dashboardSourceArray", maxItems: 20 },
    needs_external_validation: { type: "boolean" },
    markdown: { type: "string", max: 6000 },
    loopId: { type: "string", max: 100 },
    evidenceSnapshotHash: { type: "string", max: 100 },
    healthCheckHash: { type: "string", max: 100 },
    insightHash: { type: "string", max: 100 },
    rankHint: { type: "number" },
  };
  const DASHBOARD_RECORD_SCHEMA = {
    label: "대시보드 intelligence",
    required: ["id", "createdAt", "sourceRefs", "summary", "scoreBreakdown", "confidence", "verificationStatus", "riskFlags", "nextAction", "receiptHash"],
    fields: DASHBOARD_RECORD_FIELDS,
  };
  const COLLECTION_SCHEMAS = {
    events: {
      label: "일정",
      required: ["id", "title", "date"],
      fields: {
        id: { type: "string", max: 80, nonEmpty: true },
        title: { type: "string", max: 120, nonEmpty: true },
        date: { type: "date" },
        allDay: { type: "boolean" },
        start: { type: "nullableTime" },
        end: { type: "nullableTime" },
        category: { type: "string", max: 40 },
        location: { type: "string", max: 120 },
        memo: { type: "string", max: 600 },
        repeat: { type: "enum", values: ["none", "daily", "weekly", "monthly"] },
        repeatUntil: { type: "nullableDate" },
        exceptions: { type: "dateArray", maxItems: 120 },
        createdAt: { type: "string", max: 80 },
      },
    },
    todos: {
      label: "할 일",
      required: ["id", "title"],
      fields: {
        id: { type: "string", max: 80, nonEmpty: true },
        title: { type: "string", max: 160, nonEmpty: true },
        due: { type: "nullableDate" },
        priority: { type: "enum", values: ["low", "med", "high"], default: "med" },
        done: { type: "boolean" },
        category: { type: "string", max: 40 },
        memo: { type: "string", max: 600 },
        createdAt: { type: "string", max: 80 },
      },
    },
    notes: {
      label: "메모",
      required: ["id"],
      fields: {
        id: { type: "string", max: 80, nonEmpty: true },
        title: { type: "string", max: 120 },
        body: { type: "string", max: 4000 },
        color: { type: "string", max: 32 },
        pinned: { type: "boolean" },
        updatedAt: { type: "string", max: 80 },
        sourceKind: { type: "string", max: 80 },
        sourceKey: { type: "string", max: 180 },
      },
    },
    dashboardInsights: DASHBOARD_RECORD_SCHEMA,
    dashboardResearchLoops: DASHBOARD_RECORD_SCHEMA,
    dashboardImprovementCandidates: DASHBOARD_RECORD_SCHEMA,
    dashboardDecisionReceipts: DASHBOARD_RECORD_SCHEMA,
    dashboardEvidenceSnapshots: DASHBOARD_RECORD_SCHEMA,
    dashboardHealthChecks: DASHBOARD_RECORD_SCHEMA,
    projects: {
      label: "프로젝트",
      required: ["id", "name"],
      fields: {
        id: { type: "string", max: 80, nonEmpty: true },
        name: { type: "string", max: 120, nonEmpty: true },
        owner: { type: "string", max: 80 },
        progress: { type: "number" },
        status: { type: "enum", values: ["on-track", "at-risk", "delayed"] },
        health: { type: "enum", values: ["green", "amber", "red"] },
        deadline: { type: "date" },
        burn: { type: "numberArray", maxItems: 60 },
        risks: { type: "number" },
        openIssues: { type: "number" },
        members: { type: "stringArray", maxItems: 50, max: 80 },
        description: { type: "string", max: 500 },
        category: { type: "string", max: 80 },
        sourceKind: { type: "string", max: 80 },
        adoptionStage: { type: "string", max: 80 },
        topics: { type: "stringArray", maxItems: 30, max: 80 },
        language: { type: "string", max: 80 },
        color: { type: "string", max: 32 },
        url: { type: "string", max: 300 },
        stars: { type: "number" },
        forks: { type: "number" },
        diskKb: { type: "number" },
        pushedAt: { type: "string", max: 80 },
        createdAt: { type: "string", max: 80 },
        lastCommit: { type: "string", max: 80 },
        openPRs: { type: "number" },
        mergedPRs: { type: "number" },
        closedIssues: { type: "number" },
      },
    },
    issues: {
      label: "이슈",
      required: ["id", "project", "title"],
      fields: {
        id: { type: "string", max: 80, nonEmpty: true },
        project: { type: "string", max: 80, nonEmpty: true },
        title: { type: "string", max: 120, nonEmpty: true },
        status: { type: "enum", values: ["todo", "in-progress", "review", "done"] },
        priority: { type: "enum", values: ["low", "med", "high", "crit"], default: "med" },
        assignee: { type: "string", max: 80 },
        labels: { type: "stringArray", maxItems: 12, max: 40 },
        due: { type: "nullableDate" },
        estimate: { type: "number" },
        order: { type: "number" },
        sourceKind: { type: "string", max: 80 },
        sourceKey: { type: "string", max: 180 },
        assigneeOverride: { type: "boolean" },
        assigneeOverrideSavedAt: { type: "string", max: 80 },
        assigneeConfidence: { type: "string", max: 20 },
        assigneeSource: { type: "string", max: 60 },
        assigneeReason: { type: "string", max: 240 },
        assigneeReviewRequired: { type: "boolean" },
        assigneeRequiredFollowUp: { type: "stringArray", maxItems: 6, max: 280 },
        assigneePromptExamples: { type: "stringArray", maxItems: 6, max: 260 },
        assigneeFollowUpReady: { type: "boolean" },
        executionOwner: { type: "string", max: 80 },
        executionFirstAction: { type: "string", max: 240 },
        executionDecisionGate: { type: "string", max: 300 },
        executionFallbackIfBlocked: { type: "string", max: 300 },
        executionChecklist: { type: "executionChecklist", maxItems: 12 },
        executionChecklistReady: { type: "boolean" },
      },
    },
  };

  function importArrayCount(obj, key) {
    return Array.isArray(obj && obj[key]) ? obj[key].length : null;
  }

  function importGanttTaskCount(obj) {
    const gantt = obj && obj.gantt;
    return isPlainObject(gantt) && Array.isArray(gantt.tasks)
      ? gantt.tasks.length
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
    return Boolean(isPlainObject(obj) &&
      IMPORT_ARRAY_KEYS.some((key) => Array.isArray(obj[key])));
  }

  function isPlainObject(value) {
    return Boolean(value && typeof value === "object" && !Array.isArray(value));
  }

  function violation(path, message, fatal = false) {
    return { path, message, fatal: !!fatal };
  }

  function addViolation(violations, path, message, fatal = false) {
    violations.push(violation(path, message, fatal));
  }

  function invalidImportPayload(message) {
    return { ok: false, normalized: null, violations: [violation("root", message)] };
  }

  function clonePlainValue(value) {
    if (Array.isArray(value)) return value.map((item) => clonePlainValue(item));
    if (isPlainObject(value)) {
      const out = {};
      Object.keys(value).forEach((key) => { out[key] = clonePlainValue(value[key]); });
      return out;
    }
    return value;
  }

  function validateString(value, rule, path, violations) {
    if (typeof value !== "string") {
      addViolation(violations, path, "문자열이어야 합니다", true);
      return "";
    }
    if (rule.nonEmpty && value.trim() === "") {
      addViolation(violations, path, "비어 있을 수 없습니다", true);
      return "";
    }
    if (Number.isFinite(rule.max) && value.length > rule.max) {
      addViolation(violations, path, `${rule.max}자 이하 문자열이어야 합니다`);
      return value.slice(0, rule.max);
    }
    return value;
  }

  function validateDateString(value, path, violations) {
    if (typeof value !== "string" || !DATE_RE.test(value)) {
      addViolation(violations, path, "YYYY-MM-DD 날짜 문자열이어야 합니다", true);
      return "";
    }
    return value;
  }

  function validateNullableDate(value, path, violations) {
    if (value === null || value === "") return null;
    if (typeof value !== "string") {
      addViolation(violations, path, "날짜 문자열 또는 null이어야 합니다");
      return null;
    }
    if (!DATE_RE.test(value)) {
      addViolation(violations, path, "YYYY-MM-DD 날짜 문자열 또는 null이어야 합니다");
      return null;
    }
    return value;
  }

  function validateNullableTime(value, path, violations) {
    if (value === null || value === "") return null;
    if (typeof value !== "string" || !TIME_RE.test(value)) {
      addViolation(violations, path, "HH:MM 시간 문자열 또는 null이어야 합니다");
      return null;
    }
    return value;
  }

  function validateBoolean(value, path, violations) {
    if (typeof value !== "boolean") {
      addViolation(violations, path, "boolean이어야 합니다", true);
      return false;
    }
    return value;
  }

  function validateNumber(value, path, violations) {
    if (typeof value !== "number" || !Number.isFinite(value)) {
      addViolation(violations, path, "유한한 숫자여야 합니다", true);
      return 0;
    }
    return value;
  }

  function validateEnum(value, rule, path, violations) {
    const fallback = rule.values.includes(rule.default) ? rule.default : rule.values[0];
    if (typeof value !== "string") {
      addViolation(violations, path, `문자열 허용값이어야 합니다: ${rule.values.join(", ")}`);
      return fallback;
    }
    if (!rule.values.includes(value)) {
      addViolation(violations, path, `허용값이어야 합니다: ${rule.values.join(", ")}`);
      return fallback;
    }
    return value;
  }

  function addMaxItemsViolation(value, rule, path, violations, noun) {
    if (Number.isFinite(rule.maxItems) && value.length > rule.maxItems) {
      addViolation(violations, path, `${rule.maxItems}개 이하 ${noun}이어야 합니다`);
    }
  }

  function validateStringArray(value, rule, path, violations) {
    if (!Array.isArray(value)) {
      addViolation(violations, path, "문자열 배열이어야 합니다", true);
      return [];
    }
    addMaxItemsViolation(value, rule, path, violations, "배열");
    return value.map((item, index) => validateString(item, { max: rule.max || 120 }, `${path}[${index}]`, violations));
  }

  function validateNumberArray(value, rule, path, violations) {
    if (!Array.isArray(value)) {
      addViolation(violations, path, "숫자 배열이어야 합니다", true);
      return [];
    }
    addMaxItemsViolation(value, rule, path, violations, "배열");
    return value.map((item, index) => validateNumber(item, `${path}[${index}]`, violations));
  }

  function validateDateArray(value, rule, path, violations) {
    if (!Array.isArray(value)) {
      addViolation(violations, path, "날짜 문자열 배열이어야 합니다", true);
      return [];
    }
    addMaxItemsViolation(value, rule, path, violations, "배열");
    return value.map((item, index) => validateDateString(item, `${path}[${index}]`, violations));
  }

  function validateExecutionChecklist(value, rule, path, violations) {
    if (!Array.isArray(value)) {
      addViolation(violations, path, "체크리스트 배열이어야 합니다", true);
      return [];
    }
    addMaxItemsViolation(value, rule, path, violations, "체크리스트");
    return value.map((item, index) => {
      const itemPath = `${path}[${index}]`;
      if (!isPlainObject(item)) {
        addViolation(violations, itemPath, "객체여야 합니다", true);
        return {};
      }
      Object.keys(item).forEach((key) => {
        if (!EXECUTION_CHECKLIST_FIELDS.has(key)) addViolation(violations, `${itemPath}.${key}`, "지원하지 않는 필드입니다", true);
      });
      return {
        id: validateString(item.id || `exec-${index + 1}`, { max: 40, nonEmpty: true }, `${itemPath}.id`, violations),
        text: validateString(item.text, { max: 240, nonEmpty: true }, `${itemPath}.text`, violations),
        done: validateBoolean(item.done, `${itemPath}.done`, violations),
      };
    });
  }

  function validateDashboardScore(value, rule, path, violations) {
    if (!isPlainObject(value)) {
      addViolation(violations, path, "점수 객체여야 합니다", true);
      return {};
    }
    const out = {};
    Object.keys(value).forEach((key) => {
      if (!DASHBOARD_SCORE_FIELDS.has(key)) {
        addViolation(violations, `${path}.${key}`, "지원하지 않는 점수 필드입니다", true);
        return;
      }
      out[key] = validateNumber(value[key], `${path}.${key}`, violations);
    });
    return out;
  }

  function validateDashboardNextAction(value, rule, path, violations) {
    if (!isPlainObject(value)) {
      addViolation(violations, path, "다음 액션 객체여야 합니다", true);
      return {};
    }
    const out = {};
    Object.keys(value).forEach((key) => {
      if (!DASHBOARD_NEXT_ACTION_FIELDS.has(key)) {
        addViolation(violations, `${path}.${key}`, "지원하지 않는 다음 액션 필드입니다", true);
        return;
      }
      out[key] = validateString(value[key], { max: key === "command" ? 260 : 120 }, `${path}.${key}`, violations);
    });
    return out;
  }

  function validateDashboardSourceArray(value, rule, path, violations) {
    if (!Array.isArray(value)) {
      addViolation(violations, path, "source 객체 배열이어야 합니다", true);
      return [];
    }
    addMaxItemsViolation(value, rule, path, violations, "source 배열");
    return value.slice(0, rule.maxItems || 20).map((item, index) => {
      const itemPath = `${path}[${index}]`;
      if (!isPlainObject(item)) {
        addViolation(violations, itemPath, "객체여야 합니다", true);
        return {};
      }
      return {
        id: validateString(item.id || "", { max: 100 }, `${itemPath}.id`, violations),
        title: validateString(item.title || "", { max: 160 }, `${itemPath}.title`, violations),
        url: validateString(item.url || "", { max: 300 }, `${itemPath}.url`, violations),
        checkedAt: validateString(item.checkedAt || "", { max: 80 }, `${itemPath}.checkedAt`, violations),
        confidence: validateNumber(Number(item.confidence || 0), `${itemPath}.confidence`, violations),
        note: validateString(item.note || "", { max: 360 }, `${itemPath}.note`, violations),
      };
    });
  }

  const FIELD_VALIDATORS = {
    string: validateString,
    date: (value, rule, path, violations) => validateDateString(value, path, violations),
    nullableDate: (value, rule, path, violations) => validateNullableDate(value, path, violations),
    nullableTime: (value, rule, path, violations) => validateNullableTime(value, path, violations),
    boolean: (value, rule, path, violations) => validateBoolean(value, path, violations),
    number: (value, rule, path, violations) => validateNumber(value, path, violations),
    enum: validateEnum,
    stringArray: validateStringArray,
    numberArray: validateNumberArray,
    dateArray: validateDateArray,
    executionChecklist: validateExecutionChecklist,
    dashboardScore: validateDashboardScore,
    dashboardNextAction: validateDashboardNextAction,
    dashboardSourceArray: validateDashboardSourceArray,
  };

  function validateField(value, rule, path, violations) {
    const validator = FIELD_VALIDATORS[rule.type];
    if (validator) return validator(value, rule, path, violations);
    addViolation(violations, path, "지원하지 않는 검증 규칙입니다");
    return value;
  }

  function hasRequiredValue(record, key) {
    const value = record[key];
    return value !== undefined && value !== null && !(typeof value === "string" && value.trim() === "");
  }

  function validateCollectionRecord(record, schema, path, violations) {
    if (!isPlainObject(record)) {
      addViolation(violations, path, "객체여야 합니다", true);
      return null;
    }
    const fieldKeys = Object.keys(schema.fields);
    const fieldNames = new Set(fieldKeys);
    Object.keys(record).forEach((key) => {
      if (!fieldNames.has(key)) addViolation(violations, `${path}.${key}`, "지원하지 않는 필드입니다", true);
    });
    schema.required.forEach((key) => {
      if (!hasRequiredValue(record, key)) {
        addViolation(violations, `${path}.${key}`, "필수 필드입니다", true);
      }
    });
    const normalized = {};
    fieldKeys.forEach((key) => {
      if (record[key] === undefined) return;
      normalized[key] = validateField(record[key], schema.fields[key], `${path}.${key}`, violations);
    });
    return normalized;
  }

  function validateImportPayload(obj) {
    const violations = [];
    if (!isPlainObject(obj)) {
      return invalidImportPayload("백업 객체여야 합니다");
    }
    if (!isBackupShape(obj)) {
      return invalidImportPayload("백업 형식이 아닙니다");
    }
    recordLimitViolations(obj).forEach((entry) => {
      addViolation(violations, entry.key, `${entry.max}개 이하만 가져올 수 있습니다`, true);
    });
    const normalized = clonePlainValue(obj);
    Object.keys(COLLECTION_SCHEMAS).forEach((key) => {
      if (obj[key] === undefined) return;
      if (!Array.isArray(obj[key])) {
        addViolation(violations, key, "배열이어야 합니다", true);
        return;
      }
      const schema = COLLECTION_SCHEMAS[key];
      normalized[key] = obj[key].map((record, index) =>
        validateCollectionRecord(record, schema, `${key}[${index}]`, violations)
      );
    });
    const fatalViolations = violations.filter((entry) => entry && entry.fatal);
    return {
      ok: fatalViolations.length === 0,
      normalized: fatalViolations.length === 0 ? normalized : null,
      violations,
    };
  }

  function importValidationMessage(violations) {
    const list = Array.isArray(violations) ? violations : [];
    if (list.length === 0) return "가져오기 데이터 검증 실패";
    const visible = list.slice(0, 3).map((entry) => `${entry.path}: ${entry.message}`);
    const suffix = list.length > visible.length ? ` 외 ${list.length - visible.length}개` : "";
    return `가져오기 데이터 검증 실패: ${visible.join(", ")}${suffix}`;
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
    validateImportPayload,
    importValidationMessage,
  });
})(typeof window !== "undefined" ? window : globalThis);
