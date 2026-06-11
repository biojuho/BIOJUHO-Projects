#!/usr/bin/env node

import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");

function loadRuntime(relPath, extra = {}) {
  const sandbox = {
    console,
    Blob,
    setTimeout,
    clearTimeout,
    ...extra,
  };
  sandbox.window = sandbox;
  sandbox.self = sandbox;
  sandbox.globalThis = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(readFileSync(join(root, relPath), "utf8"), sandbox, { filename: relPath });
  return sandbox;
}

function escapeHtml(value) {
  if (value === null || value === undefined) return "";
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function raw(value) {
  return { __raw: true, value: value == null ? "" : String(value) };
}

function html(strings, ...values) {
  let out = "";
  for (let index = 0; index < strings.length; index += 1) {
    out += strings[index];
    if (index >= values.length) continue;
    const value = values[index];
    if (value === null || value === undefined || value === false) continue;
    if (value && value.__raw) out += value.value;
    else if (Array.isArray(value)) out += value.map((item) => item && item.__raw ? item.value : escapeHtml(item)).join("");
    else out += escapeHtml(value);
  }
  return out;
}

function storageMock({ failSet = false } = {}) {
  const map = new Map();
  return {
    getItem(key) {
      return map.has(key) ? map.get(key) : null;
    },
    setItem(key, value) {
      if (failSet) {
        const error = new Error("quota reached");
        error.name = "QuotaExceededError";
        throw error;
      }
      map.set(key, String(value));
    },
    removeItem(key) {
      map.delete(key);
    },
  };
}

function artifactStorageMock(options = {}) {
  const initial = options.initial && typeof options.initial === "object" ? options.initial : options;
  const map = new Map(Object.entries(initial).map(([key, value]) => [key, String(value)]));
  const calls = [];
  return {
    calls,
    getRaw(key) {
      return map.get(key);
    },
    async get(key, shared = false) {
      calls.push({ op: "get", key, shared });
      if (!map.has(key)) throw new Error("not found");
      return { key, value: map.get(key), shared };
    },
    async set(key, value, shared = false) {
      calls.push({ op: "set", key, value: String(value), shared });
      map.set(key, String(value));
      return { key, value: String(value), shared };
    },
    async delete(key, shared = false) {
      calls.push({ op: "delete", key, shared });
      const deleted = map.delete(key);
      return { key, deleted, shared };
    },
    async list(prefix = "", shared = false) {
      calls.push({ op: "list", prefix, shared });
      return { keys: [...map.keys()].filter((key) => key.startsWith(prefix)), prefix, shared };
    },
  };
}

function eventTargetMock(extra = {}) {
  const listeners = new Map();
  return {
    ...extra,
    addEventListener(type, callback) {
      if (!listeners.has(type)) listeners.set(type, []);
      listeners.get(type).push(callback);
    },
    dispatchEventType(type, event = {}) {
      (listeners.get(type) || []).forEach((callback) => callback(event));
    },
    listenerCount(type) {
      return (listeners.get(type) || []).length;
    },
  };
}

function matches(value, query) {
  if (!query) return true;
  return String(value || "").toLowerCase().includes(String(query || "").toLowerCase());
}

function ymd(date) {
  return [
    date.getFullYear(),
    String(date.getMonth() + 1).padStart(2, "0"),
    String(date.getDate()).padStart(2, "0"),
  ].join("-");
}

function addDaysISO(value, amount) {
  const [year, month, day] = String(value || "").split("-").map(Number);
  const date = new Date(year, month - 1, day);
  date.setDate(date.getDate() + amount);
  return ymd(date);
}

function dateFromISO(value) {
  const [year, month, day] = String(value || "").split("-").map(Number);
  return new Date(year, month - 1, day);
}

function weekDatesFor(today) {
  const date = dateFromISO(today);
  date.setDate(date.getDate() - date.getDay());
  return Array.from({ length: 7 }, (_, index) => {
    const next = new Date(date);
    next.setDate(date.getDate() + index);
    return ymd(next);
  });
}

function kpiCard(item) {
  return html`<article class="kpi">${item.title}:${item.value}${item.unit || ""}</article>`;
}

function panelHead(title, _link, controls) {
  return html`<header class="panel-head"><h2>${title}</h2>${raw(controls || "")}</header>`;
}

function searchEmptyState(kind, title, message = "") {
  return html`<article data-search-empty="${kind}"><strong>${title}</strong><span>${message}</span></article>`;
}

function createStorage(options = {}) {
  const dashboard = {
    events: [{ id: "ev1", title: "event" }],
    todos: [{ id: "td1", title: "todo" }],
    notes: [],
    deletedItems: [],
    reviewResults: [],
    reviewIssueDraftOverrides: [],
    settings: { displayName: "테스터" },
    habits: [],
    projects: [],
    issues: [],
    gantt: { tasks: [] },
    team: [],
    dbInstances: [],
    schemas: [],
    queries: [],
    backups: [],
    migrations: [],
    ui: {},
    imports: {},
  };
  const state = { storageHealth: {} };
  const toasts = [];
  const storage = storageMock(options);
  const runtime = loadRuntime("workspace-storage.js", {
    localStorage: storage,
    storage: options.artifactStorage || null,
    navigator: { storage: {} },
  });
  const api = runtime.JooParkWorkspaceStorage.create({
    dashboard,
    state,
    storeKey: "legacy",
    storeKeyV3: "current",
    getStorage: () => storage,
    getArtifactStorage: () => options.artifactStorage || null,
    artifactStorageKey: "joopark-workspace:v3",
    nowISO: () => "2026-06-09T00:00:00.000Z",
    normalizeAllData() {},
    rebuildIndexes() {},
    seedPersonalData() {},
    setPmWasPersisted() {},
    showToast(message, tone) {
      toasts.push({ message, tone });
    },
    consoleRef: { warn() {} },
  });
  return { api, dashboard, state, storage, toasts };
}

function testWorkspaceStorage() {
  const { api, dashboard, state, storage, toasts } = createStorage();
  assert.equal(api.version, "joopark-workspace-storage/v1");
  assert.equal(api.formatBytes(512), "512 B");
  assert.equal(api.formatBytes(1536), "1.5 KB");
  assert.equal(api.storagePercent(90, 100), 90);
  assert.equal(api.storageTone({ lastError: "no space" }), "error");
  assert.equal(api.storageStatusLabel({ lastError: "no space" }), "저장 실패");
  assert.equal(api.persist(), true);
  const saved = JSON.parse(storage.getItem("current"));
  assert.equal(saved.v, 3);
  assert.equal(saved.events.length, 1);
  assert.equal(dashboard.lastSavedAt, "2026-06-09T00:00:00.000Z");
  assert.equal(state.storageHealth.lastError, "");
  assert.equal(toasts.length, 0);

  const failed = createStorage({ failSet: true });
  assert.equal(failed.api.persist(), false);
  assert.equal(failed.state.storageHealth.status, "error");
  assert.equal(failed.state.storageHealth.lastError, "quota reached");
  assert.equal(failed.toasts.at(-1).tone, "error");
  assert.match(failed.toasts.at(-1).message, /저장 실패/);
}

async function testWorkspaceStorageArtifactMirrorAndHydration() {
  const artifact = artifactStorageMock();
  const mirrored = createStorage({ artifactStorage: artifact });
  const payload = JSON.stringify(mirrored.api.persistPayload("2026-06-09T00:00:00.000Z"));
  assert.equal(await mirrored.api.persistArtifactStorageMirror(payload, "2026-06-09T00:00:00.000Z"), true);
  const mirrorCall = artifact.calls.find((call) => call.op === "set");
  assert.equal(mirrorCall.key, "joopark-workspace:v3");
  assert.equal(mirrorCall.shared, false);
  assert.equal(JSON.parse(artifact.getRaw("joopark-workspace:v3")).v, 3);
  assert.equal(mirrored.state.storageHealth.artifactStorage.status, "mirrored");
  assert.equal(mirrored.state.storageHealth.artifactStorage.lastBytes > 0, true);

  const artifactPayload = {
    v: 3,
    events: [{ id: "ev-artifact", title: "artifact event" }],
    todos: [],
    notes: [],
    deletedItems: [],
    reviewResults: [],
    reviewIssueDraftOverrides: [],
    settings: { displayName: "Artifact User" },
    habits: [],
    projects: [],
    issues: [],
    gantt: { tasks: [] },
    team: [],
    dbInstances: [],
    schemas: [],
    queries: [],
    backups: [],
    migrations: [],
    ui: { theme: "light" },
    imports: {},
    savedAt: "2026-06-08T12:00:00.000Z",
  };
  const hydratedArtifact = artifactStorageMock({
    "joopark-workspace:v3": JSON.stringify(artifactPayload),
  });
  const hydrated = createStorage({ artifactStorage: hydratedArtifact });
  assert.equal(hydrated.api.loadPersisted(), false);
  assert.equal(hydrated.storage.getItem("current"), null);
  assert.equal(await hydrated.api.hydrateArtifactStorage(), true);
  assert.equal(hydrated.dashboard.events[0].title, "artifact event");
  assert.equal(hydrated.dashboard.settings.displayName, "Artifact User");
  assert.equal(JSON.parse(hydrated.storage.getItem("current")).events[0].title, "artifact event");
  assert.equal(["hydrated", "mirrored"].includes(hydrated.state.storageHealth.artifactStorage.status), true);
  assert.equal(hydratedArtifact.calls.some((call) => call.op === "get" && call.shared === false), true);
}

function testDashboardStorageConfidenceBounds() {
  const runtime = loadRuntime("dashboard-storage.js");
  const storage = runtime.JooParkDashboardStorage.create();
  assert.equal(storage.boundedConfidence("bad", 0.65), 0.65);
  assert.equal(storage.boundedConfidence(Infinity, 0.65), 0.65);
  assert.equal(storage.boundedConfidence(2, 0.65), 1);
  assert.equal(storage.boundedConfidence(-1, 0.65), 0);
  const bad = storage.normalizeDashboardRecord({ id: "bad", confidence: "bad", summary: "Summary" }, { confidence: 0.65 });
  assert.equal(bad.confidence, 0.65);
  assert.equal(Number.isFinite(bad.confidence), true);
  assert.match(JSON.stringify(bad), /"confidence":0\.65/);
}

function testStorageStatusRecoveryView() {
  const runtime = loadRuntime("storage-status-view.js");
  const view = runtime.JooParkStorageStatusView.create({
    html,
    raw,
    formatBytes: (bytes) => `${bytes} B`,
    storagePercent: () => 1.2,
    storageTone: (health) => health.status === "error" ? "error" : "ok",
    storageStatusLabel: (health) => health.status === "error" ? "오류" : "정상",
    storagePersistentLabel: () => "확인 중",
    formatLocalDateTime: (value) => value || "",
  });
  const output = view.settingsStorageHealthHTML({
    status: "error",
    lastError: "quota reached",
    localBytes: 11,
    usageBytes: 11,
    quotaBytes: 1000,
    recovery: {
      ready: true,
      generatedAt: "2026-06-09T00:00:00.000Z",
      filename: "joopark-emergency.json",
      bytes: 11,
      reason: "quota reached",
      json: "{\"ok\":true}",
    },
  });
  assert.match(output, /data-storage-failure-recovery/);
  assert.match(output, /role="alert"/);
  assert.match(output, /긴급 백업 다운로드/);
  assert.match(output, /download="joopark-emergency\.json"/);
  assert.match(output, /data-storage-failure-normal-export/);
  assert.match(output, /%7B%22ok%22%3Atrue%7D/);
}

function testKanbanHelpers() {
  const runtime = loadRuntime("kanban-view.js");
  const kanbanDeps = {
    html,
    raw,
    matches: (value, query) => String(value).toLowerCase().includes(String(query).toLowerCase()),
    kpiCard: (item) => html`<article data-kpi="${item.title}">${item.value}</article>`,
    panelHead: (title, _link, controls) => html`<header><h2>${title}</h2>${raw(controls || "")}</header>`,
    searchEmptyState: (kind, title) => html`<p data-empty="${kind}">${title}</p>`,
    memberName: (id) => id || "미지정",
    projectName: (id) => id || "프로젝트",
    issueExecutionChecklistItems: () => [],
    issueExecutionChecklistProgress: () => ({ done: 0, total: 0, percent: 0 }),
  };
  const kanban = runtime.JooParkKanbanView.create(kanbanDeps);
  const issues = [
    { id: "B", project: "p1", title: "Beta", status: "todo", priority: "low", assignee: "m1", labels: [{ name: "Ops" }], order: 2000 },
    { id: "A", project: "p1", title: "Alpha <script>", status: "todo", priority: "crit", assignee: "m1", labels: [{ name: "Ops" }, { label: "Risk" }, "Ops"], order: 1000 },
    { id: "C", project: "p2", title: "Other", status: "done", priority: "med", assignee: "", labels: [], order: 1000 },
  ];
  const model = kanban.kanbanViewModel({ issues, currentProjectId: "p1", sourceFilter: "all", density: "compact" });
  assert.deepEqual(model.all.map((issue) => issue.id), ["A", "B"]);
  assert.equal(model.counts.todo, 2);
  const card = kanban.issueCard(issues[1], model);
  assert.match(card, /#Ops/);
  assert.match(card, /#Risk/);
  assert.doesNotMatch(card, /\[object Object\]/);
  assert.match(card, /Alpha &lt;script&gt;/);
  assert.match(card, /data-kanban-card-density="compact"/);

  const largeIssues = Array.from({ length: 420 }, (_, index) => ({
    id: `L-${index}`,
    project: "p1",
    title: `Large issue ${index}`,
    status: ["todo", "in-progress", "review", "done"][index % 4],
    priority: "med",
    assignee: "",
    labels: [],
    order: index * 1000,
  }));
  const largeBoard = kanban.renderKanbanHTML({ issues: largeIssues, currentProjectId: "p1", sourceFilter: "all", density: "compact" });
  const renderedCards = (largeBoard.match(/class="kanban-card-wrap"/g) || []).length;
  assert.equal(renderedCards, 320);
  assert.match(largeBoard, /data-kanban-virtualized="true"/);

  const invalidLimitKanban = runtime.JooParkKanbanView.create({ ...kanbanDeps, columnRenderLimit: "bad" });
  const invalidLimitBoard = invalidLimitKanban.renderKanbanHTML({ issues: largeIssues, currentProjectId: "p1", sourceFilter: "all", density: "compact" });
  const invalidLimitCards = (invalidLimitBoard.match(/class="kanban-card-wrap"/g) || []).length;
  assert.equal(invalidLimitCards, 320);
  assert.match(invalidLimitBoard, /data-kanban-virtualized="true"/);
  assert.equal(invalidLimitKanban.renderLimitOption("Infinity"), 80);
  assert.equal(invalidLimitKanban.renderLimitOption("-1"), 20);
}

function testImportGuards() {
  const runtime = loadRuntime("backup-import-guards.js");
  assert.equal(runtime.JooParkImportGuards.version, "joopark-import-guards/v1");
  assert.equal(runtime.JooParkImportGuards.maxImportBytes, 2 * 1024 * 1024);
  assert.equal(runtime.JooParkImportGuards.isBackupShape({ todos: [] }), true);
  assert.equal(runtime.JooParkImportGuards.isBackupShape({ data: { todos: [] } }), false);
  const summaryItems = Array.from(runtime.JooParkImportGuards.backupSummaryItems({
    events: [{}],
    todos: [{}, {}],
    notes: [],
  }), (item) => Array.from(item));
  assert.equal(JSON.stringify(summaryItems), JSON.stringify([["일정", 1], ["할 일", 2], ["메모", 0]]));
  const violations = runtime.JooParkImportGuards.recordLimitViolations({
    todos: Array.from({ length: 1001 }, () => ({})),
  });
  assert.equal(violations.length, 1);
  assert.equal(violations[0].key, "todos");
  assert.match(runtime.JooParkImportGuards.recordLimitMessage(violations), /할 일 1001\/1000/);

  const validPayload = {
    events: [{
      id: "ev-1",
      title: "Demo event",
      date: "2026-06-09",
      allDay: false,
      start: "09:30",
      end: "10:00",
      category: "meeting",
      location: "HQ",
      memo: "",
      repeat: "none",
      repeatUntil: null,
      exceptions: [],
      createdAt: "2026-06-09T00:00:00.000Z",
    }],
    todos: [{
      id: "td-1",
      title: "Ship guard",
      due: null,
      priority: "high",
      done: false,
      category: "work",
      memo: "",
      createdAt: "2026-06-09T00:00:00.000Z",
    }],
    notes: [{
      id: "nt-1",
      title: "Note",
      body: "Body",
      color: "#22d3ee",
      pinned: true,
      updatedAt: "2026-06-09T00:00:00.000Z",
    }],
    projects: [{
      id: "proj-1",
      name: "Project",
      owner: "owner",
      progress: 25,
      status: "on-track",
      health: "green",
      deadline: "2026-07-01",
      burn: [0, 10, 25],
      risks: 1,
      openIssues: 2,
      members: ["jp"],
    }],
    issues: [{
      id: "PM-1",
      project: "proj-1",
      title: "Issue",
      status: "todo",
      priority: "med",
      assignee: "jp",
      labels: ["ops"],
      due: "2026-06-30",
      estimate: 3,
      order: 1000,
      executionChecklist: [{ id: "exec-1", text: "Check", done: false }],
    }],
  };
  const validValidation = runtime.JooParkImportGuards.validateImportPayload(validPayload);
  assert.equal(validValidation.ok, true);
  assert.equal(JSON.stringify(validValidation.normalized), JSON.stringify(validPayload));

  const invalidPayload = {
    todos: [{
      id: "td-1",
      title: { nested: "object title should be rejected" },
      done: "yes",
      unexpectedKey: "reject this",
    }],
  };
  const invalidValidation = runtime.JooParkImportGuards.validateImportPayload(invalidPayload);
  assert.equal(invalidValidation.ok, false);
  assert.equal(invalidValidation.normalized, null);
  assert.match(runtime.JooParkImportGuards.importValidationMessage(invalidValidation.violations), /todos\[0\]\.unexpectedKey/);
  assert.match(runtime.JooParkImportGuards.importValidationMessage(invalidValidation.violations), /문자열이어야 합니다/);

  const softDriftPayload = {
    projects: [{
      id: "proj-soft",
      name: "x".repeat(500),
      progress: 200,
      status: "unknown",
      health: "unknown",
      members: Array.from({ length: 75 }, (_, index) => `member-${index}`),
      burn: Array.from({ length: 90 }, (_, index) => index),
    }],
    issues: [{
      id: "ISS-soft",
      project: "proj-soft",
      title: "x".repeat(500),
      status: "bad-status",
      priority: "bad-priority",
      due: "bad-date",
      labels: Array.from({ length: 30 }, (_, index) => `label-${index}`),
      estimate: 2000,
    }],
  };
  const softDriftValidation = runtime.JooParkImportGuards.validateImportPayload(softDriftPayload);
  assert.equal(softDriftValidation.ok, true);
  assert.ok(softDriftValidation.normalized);
  assert.equal(softDriftValidation.normalized.projects[0].name.length, 120);
  assert.equal(softDriftValidation.normalized.projects[0].status, "on-track");
  assert.equal(softDriftValidation.normalized.issues[0].priority, "med");
  assert.equal(softDriftValidation.normalized.issues[0].due, null);
  const softDriftMessages = softDriftValidation.violations.map((entry) => `${entry.path}: ${entry.message}`).join("\n");
  assert.match(softDriftMessages, /projects\[0\]\.name: 120자 이하 문자열이어야 합니다/);
  assert.match(softDriftMessages, /projects\[0\]\.status: 허용값이어야 합니다/);
  assert.match(softDriftMessages, /projects\[0\]\.members: 50개 이하 배열이어야 합니다/);
  assert.match(softDriftMessages, /issues\[0\]\.due: YYYY-MM-DD 날짜 문자열 또는 null이어야 합니다/);
  assert.equal(softDriftValidation.violations.some((entry) => entry.fatal), false);

  const uiRuntime = loadRuntime("backup-import-ui.js", { FileReader: class {} });
  const opened = [];
  const toasts = [];
  let reader = null;
  class FakeReader {
    constructor() { reader = this; }
    readAsText() {}
  }
  const ui = uiRuntime.JooParkBackupImportUi.create({
    dashboard: { todos: [] },
    importGuards: runtime.JooParkImportGuards,
    showToast(message, tone) {
      toasts.push({ message, tone });
    },
    openModal(title, body) {
      opened.push({ title, body });
    },
    fileReaderFactory: () => new FakeReader(),
  });
  const input = { value: "bad.json", files: [{ size: 512 }] };
  ui.handleImportFile({ target: input });
  reader.result = JSON.stringify(invalidPayload);
  reader.onload();
  assert.equal(opened.length, 0);
  assert.equal(input.value, "");
  assert.equal(toasts.length, 1);
  assert.equal(toasts[0].tone, "error");
  assert.match(toasts[0].message, /가져오기 데이터 검증 실패/);

  const invalidLimitToasts = [];
  let invalidLimitReaderCalled = false;
  const invalidLimitUi = uiRuntime.JooParkBackupImportUi.create({
    importGuards: { ...runtime.JooParkImportGuards, maxImportBytes: "Infinity" },
    showToast(message, tone) {
      invalidLimitToasts.push({ message, tone });
    },
    formatBytes: (value) => `${value} bytes`,
    fileReaderFactory: () => ({
      readAsText() {
        invalidLimitReaderCalled = true;
      },
    }),
  });
  assert.equal(invalidLimitUi.maxImportBytesOption("Infinity"), runtime.JooParkImportGuards.maxImportBytes);
  assert.equal(invalidLimitUi.maxImportBytesOption("bad", 1024), 1024);
  const invalidLimitInput = { value: "huge.json", files: [{ size: runtime.JooParkImportGuards.maxImportBytes + 1 }] };
  invalidLimitUi.handleImportFile({ target: invalidLimitInput });
  assert.equal(invalidLimitReaderCalled, false);
  assert.equal(invalidLimitInput.value, "");
  assert.equal(invalidLimitToasts.length, 1);
  assert.equal(invalidLimitToasts[0].tone, "error");
  assert.match(invalidLimitToasts[0].message, /2097152 bytes 이하/);
}

function testRuntimeErrorBoundary() {
  const listeners = new Map();
  const toasts = [];
  const logs = [];
  let now = 1000;
  const fakeWindow = {
    location: { hash: "#pm-kanban" },
    addEventListener(type, callback) {
      listeners.set(type, callback);
    },
  };
  const runtime = loadRuntime("runtime-error-boundary.js", {
    window: fakeWindow,
    console: {
      error(label, payload) {
        logs.push({ label, payload });
      },
    },
  });
  const fallbacks = [];
  const boundary = runtime.JooParkRuntimeErrorBoundary.create({
    window: fakeWindow,
    consoleRef: {
      error(label, payload) {
        logs.push({ label, payload });
      },
    },
    locationRef: fakeWindow.location,
    now: () => now,
    nowISO: () => `t-${now}`,
    debounceMs: 2500,
    showToast(message, tone, options) {
      toasts.push({ message, tone, timeoutMs: options.timeoutMs });
    },
    fallback(payload) {
      fallbacks.push(payload);
    },
  });

  assert.equal(boundary.version, "joopark-runtime-error-boundary/v1");
  assert.equal(boundary.debounceMsOption("bad"), 2500);
  assert.equal(boundary.debounceMsOption(Infinity), 2500);
  assert.equal(boundary.debounceMsOption(100), 250);
  assert.equal(boundary.install(), true);
  assert.equal(boundary.install(), false);
  assert.equal(typeof listeners.get("error"), "function");
  assert.equal(typeof listeners.get("unhandledrejection"), "function");

  const first = boundary.handle(new Error("first boom"), { source: "unit" });
  const second = boundary.handle(new Error("second boom"), { source: "unit" });
  assert.equal(first.hash, "#pm-kanban");
  assert.equal(first.message, "first boom");
  assert.equal(second.message, "second boom");
  assert.equal(toasts.length, 1);
  assert.equal(toasts[0].tone, "error");
  assert.match(toasts[0].message, /예상치 못한 오류/);
  assert.equal(logs.filter((entry) => entry.label === "[joopark-runtime-error]").length, 2);
  assert.equal(fallbacks.length, 2);

  now += 3000;
  listeners.get("unhandledrejection")({ reason: new Error("promise boom") });
  assert.equal(toasts.length, 2);
  assert.equal(fallbacks.at(-1).source, "unhandledrejection");
  assert.equal(fallbacks.at(-1).message, "promise boom");

  const invalidDebounceToasts = [];
  const invalidDebounceBoundary = runtime.JooParkRuntimeErrorBoundary.create({
    window: { location: { hash: "" }, addEventListener() {} },
    consoleRef: { error() {} },
    now: () => 1000,
    debounceMs: "bad",
    showToast(message) {
      invalidDebounceToasts.push(message);
    },
  });
  invalidDebounceBoundary.handle(new Error("first invalid debounce"));
  invalidDebounceBoundary.handle(new Error("second invalid debounce"));
  assert.equal(invalidDebounceToasts.length, 1);
}

async function testPwaRuntimeUpdateReadyToast() {
  const runtime = loadRuntime("pwa-runtime.js");
  const toasts = [];
  const reloads = [];
  const loadCallbacks = [];
  const worker = eventTargetMock({ state: "installing", scriptURL: "http://127.0.0.1:5178/sw.js" });
  const registration = eventTargetMock({
    active: { scriptURL: "http://127.0.0.1:5178/sw.js" },
    installing: worker,
    waiting: null,
    scope: "http://127.0.0.1:5178/",
  });
  const serviceWorker = eventTargetMock({
    controller: { scriptURL: "http://127.0.0.1:5178/sw.js" },
    ready: Promise.resolve(registration),
    async register() {
      return registration;
    },
    async getRegistration() {
      return registration;
    },
  });
  const rootWindow = {
    isSecureContext: true,
    addEventListener(type, callback) {
      if (type === "load") loadCallbacks.push(callback);
    },
    location: { reload: () => reloads.push("window") },
  };
  const api = runtime.JooParkPwaRuntime.create({
    window: rootWindow,
    document: { querySelector: () => ({ href: "./site.webmanifest" }) },
    navigator: { serviceWorker, onLine: true },
    location: { hostname: "127.0.0.1", reload: () => reloads.push("location") },
    showToast(message, tone, options) {
      toasts.push({ message, tone, options });
    },
  });

  assert.equal(api.register(() => {}), true);
  assert.equal(loadCallbacks.length, 1);
  loadCallbacks[0]();
  await Promise.resolve();
  await Promise.resolve();
  registration.dispatchEventType("updatefound");
  assert.equal(worker.listenerCount("statechange"), 1);
  worker.state = "installed";
  worker.dispatchEventType("statechange");

  assert.equal(toasts.length, 1);
  assert.equal(toasts[0].tone, "info");
  assert.match(toasts[0].message, /새 버전이 준비되었습니다/);
  assert.equal(toasts[0].options.actionLabel, "새로고침");
  assert.equal(toasts[0].options.timeoutMs, 12000);
  toasts[0].options.onAction();
  assert.deepEqual(reloads, ["location"]);
}

async function testPwaRuntimeControllerChangeAppliedToast() {
  const runtime = loadRuntime("pwa-runtime.js");
  const toasts = [];
  const refreshes = [];
  const worker = eventTargetMock({ state: "installing", scriptURL: "http://127.0.0.1:5178/sw.js?v=2" });
  const activeWorker = { scriptURL: "http://127.0.0.1:5178/sw.js?v=1" };
  const registration = eventTargetMock({
    active: activeWorker,
    installing: worker,
    waiting: null,
    scope: "http://127.0.0.1:5178/",
  });
  const serviceWorker = eventTargetMock({
    controller: activeWorker,
    ready: Promise.resolve(registration),
    async getRegistration() {
      return registration;
    },
  });
  const api = runtime.JooParkPwaRuntime.create({
    window: { isSecureContext: true, addEventListener() {}, location: { reload() {} } },
    document: { querySelector: () => ({ href: "./site.webmanifest" }) },
    navigator: { serviceWorker, onLine: true },
    location: { hostname: "127.0.0.1" },
    showToast(message, tone, options) {
      toasts.push({ message, tone, options });
    },
  });

  api.setupObservers(() => refreshes.push("refresh"));
  await Promise.resolve();
  registration.dispatchEventType("updatefound");
  serviceWorker.controller = worker;
  serviceWorker.dispatchEventType("controllerchange");

  assert(refreshes.length >= 2);
  assert.equal(toasts.length, 1);
  assert.equal(toasts[0].tone, "info");
  assert.match(toasts[0].message, /새 버전이 적용되었습니다/);
  assert.equal(toasts[0].options.actionLabel, "새로고침");
}

async function testPwaRuntimeFirstInstallStaysQuiet() {
  const runtime = loadRuntime("pwa-runtime.js");
  const toasts = [];
  const refreshes = [];
  const worker = eventTargetMock({ state: "installing", scriptURL: "http://127.0.0.1:5178/sw.js" });
  const registration = eventTargetMock({
    active: null,
    installing: worker,
    waiting: null,
    scope: "http://127.0.0.1:5178/",
  });
  const serviceWorker = eventTargetMock({
    controller: null,
    ready: Promise.resolve(registration),
    async getRegistration() {
      return registration;
    },
  });
  const api = runtime.JooParkPwaRuntime.create({
    window: { isSecureContext: true, addEventListener() {}, location: { reload() {} } },
    document: { querySelector: () => ({ href: "./site.webmanifest" }) },
    navigator: { serviceWorker, onLine: true },
    location: { hostname: "127.0.0.1" },
    showToast(message, tone, options) {
      toasts.push({ message, tone, options });
    },
  });

  api.setupObservers(() => refreshes.push("refresh"));
  await Promise.resolve();
  registration.dispatchEventType("updatefound");
  serviceWorker.controller = worker;
  serviceWorker.dispatchEventType("controllerchange");
  worker.state = "activated";
  worker.dispatchEventType("statechange");

  assert(refreshes.length >= 3);
  assert.equal(toasts.length, 0);
}

function testCalendarViewModelAndEscapes() {
  const runtime = loadRuntime("calendar-view.js");
  const events = [
    { id: "evt-alpha", title: "Alpha <script>", memo: "memo <b>", location: "HQ <img>", category: "meeting", date: "2026-06-09", start: "09:00" },
    { id: "evt-beta", title: "Beta", memo: "plain", location: "Remote", category: "deadline", date: "2026-06-12", allDay: true },
  ];
  const occurrences = events.map((event) => ({ ...event, _masterId: event.id }));
  const calendar = runtime.JooParkCalendarView.create({
    html,
    raw,
    eventCats: {
      meeting: { label: "미팅", color: "var(--blue)" },
      deadline: { label: "마감", color: "var(--red)" },
      etc: { label: "기타", color: "var(--cyan)" },
    },
    eventCatOrder: ["meeting", "deadline", "etc"],
    weekdaysKo: ["일", "월", "화", "수", "목", "금", "토"],
    todayISO: () => "2026-06-09",
    ymToDate: (ym) => dateFromISO(`${ym}-01`),
    ymd,
    matches,
    expandOccurrences: (start, end) => occurrences.filter((event) => event.date >= start && event.date <= end),
    eventsOn: (date) => occurrences.filter((event) => event.date === date),
    addDaysISO,
    isTodayISO: (date) => date === "2026-06-09",
    formatKoreanShort: (value) => value,
    formatKoreanFull: (value) => value,
    eventTimeLabel: (event) => event.allDay ? "종일" : event.start || "",
    kpiCard,
    searchEmptyState,
  });

  const model = calendar.calendarViewModel({
    events,
    todos: [],
    query: "Alpha",
    month: "2026-06",
    selected: "2026-06-09",
    mode: "week",
  });
  assert.deepEqual(model.visibleRangeOccurrences.map((event) => event.id), ["evt-alpha"]);
  assert.equal(model.calendarSearchEmpty, false);
  assert.equal(model.rangeStart, "2026-06-07");
  assert.equal(model.rangeEnd, "2026-06-13");

  const row = calendar.eventRow(events[0], {});
  assert.match(row, /Alpha &lt;script&gt;/);
  assert.match(row, /HQ &lt;img&gt;/);
  assert.doesNotMatch(row, /<script>/);

  const empty = calendar.renderCalendarHTML({
    events,
    todos: [],
    query: "Missing <script>",
    month: "2026-06",
    selected: "2026-06-09",
    mode: "month",
  });
  assert.match(empty, /data-search-empty="calendar"/);
  assert.match(empty, /Missing &lt;script&gt;/);
}

function testTodoViewModelAndEscapes() {
  const runtime = loadRuntime("todo-view.js");
  const todoDeps = {
    html,
    raw,
    todoPriority: {
      high: { label: "높음", color: "var(--red)" },
      med: { label: "보통", color: "var(--cyan)" },
      low: { label: "낮음", color: "var(--green)" },
    },
    todoPrioRank: { high: 0, med: 1, low: 2 },
    todoFilters: [{ key: "active", label: "미완료" }, { key: "done", label: "완료" }],
    todoSourceFilters: [{ key: "all", label: "전체" }, { key: "wiki", label: "LLM Wiki" }],
    dueLabel: (value) => ({ cls: value ? "has-due" : "", text: value || "마감 없음" }),
    todayISO: () => "2026-06-09",
    matches,
    formatKoreanShort: (value) => value,
    kpiCard,
    searchEmptyState,
  };
  const todo = runtime.JooParkTodoView.create(todoDeps);
  const todos = [
    { id: "low", title: "Beta", category: "Ops", priority: "low", due: "2026-06-10", done: false },
    { id: "high", title: "Alpha <script>", category: "Ops <b>", priority: "high", due: "2026-06-10", done: false, memo: "ship", sourceKey: "llm-wiki:todo:alpha" },
    { id: "done", title: "Done", category: "Ops", priority: "med", due: "2026-06-08", done: true },
  ];

  const model = todo.todoViewModel(todos, "", "active", "all");
  assert.deepEqual(model.filtered.map((item) => item.id), ["high", "low"]);
  assert.equal(model.sourceCounts.wiki, 1);
  assert.equal(model.kpis[0].value, "2");

  const wikiModel = todo.todoViewModel(todos, "", "active", "wiki");
  assert.deepEqual(wikiModel.filtered.map((item) => item.id), ["high"]);

  const row = todo.todoRow(todos[1]);
  assert.match(row, /Alpha &lt;script&gt;/);
  assert.match(row, /Ops &lt;b&gt;/);
  assert.doesNotMatch(row, /<script>/);

  const empty = todo.todoListHTML(todo.todoViewModel(todos, "Missing <script>", "all", "all"));
  assert.match(empty, /data-search-empty="todo"/);
  assert.match(empty, /Missing &lt;script&gt;/);

  const manyTodos = Array.from({ length: 220 }, (_, index) => ({
    id: `many-${index}`,
    title: `Todo ${index}`,
    category: "Ops",
    priority: "med",
    due: "2026-06-10",
    done: false,
  }));
  const manyList = todo.todoListHTML(todo.todoViewModel(manyTodos, "", "all", "all"));
  const renderedTodos = (manyList.match(/class="todo-row /g) || []).length;
  assert.equal(renderedTodos, 160);
  assert.match(manyList, /data-todo-virtualized="true"/);

  const invalidLimitTodo = runtime.JooParkTodoView.create({
    ...todoDeps,
    todoRenderLimit: "bad-limit",
    todoBucketRenderLimit: "bad-limit",
  });
  const invalidLimitList = invalidLimitTodo.todoListHTML(invalidLimitTodo.todoViewModel(manyTodos, "", "all", "all"));
  const invalidLimitRenderedTodos = (invalidLimitList.match(/class="todo-row /g) || []).length;
  assert.equal(invalidLimitRenderedTodos, 160);
  assert.match(invalidLimitList, /data-todo-virtualized="true"/);
  const invalidBucketList = invalidLimitTodo.todoListHTML(invalidLimitTodo.todoViewModel(manyTodos, "", "active", "all"));
  const invalidBucketRenderedTodos = (invalidBucketList.match(/class="todo-row /g) || []).length;
  assert.equal(invalidBucketRenderedTodos, 80);
  assert.match(invalidBucketList, /data-todo-virtualized="true"/);
}

function testNotesViewModelAndEscapes() {
  const runtime = loadRuntime("notes-view.js");
  const notesView = runtime.JooParkNotesView.create({
    html,
    raw,
    matches,
    safeNoteColor: (value) => value || "var(--cyan)",
    renderMarkdown: () => null,
    formatKoreanShort: (value) => value,
    localYmd: (value) => String(value || "").slice(0, 10),
    searchEmptyState,
    noteSourceFilters: [
      { key: "all", label: "전체" },
      { key: "wiki", label: "LLM Wiki" },
      { key: "review", label: "Review" },
    ],
  });
  const notes = [
    { id: "new", title: "Beta", body: "body", updatedAt: "2026-06-09T10:00:00", pinned: false },
    { id: "pin", title: "Alpha <script>", body: "Body <b>", updatedAt: "2026-06-01T10:00:00", pinned: true, sourceKey: "llm-wiki:note:alpha" },
    { id: "review", title: "Review", body: "body", updatedAt: "2026-06-08T10:00:00", pinned: false, sourceKey: "workspace-review:item" },
  ];

  const model = notesView.notesViewModel({ notes, query: "", sourceFilter: "all" });
  assert.deepEqual(model.list.map((note) => note.id), ["pin", "new", "review"]);
  assert.equal(model.pinnedCount, 1);
  assert.equal(model.sourceCounts.wiki, 1);
  assert.equal(model.sourceCounts.review, 1);

  const wikiModel = notesView.notesViewModel({ notes, query: "", sourceFilter: "wiki" });
  assert.deepEqual(wikiModel.list.map((note) => note.id), ["pin"]);

  const card = notesView.noteCard(notes[1]);
  assert.match(card, /Alpha &lt;script&gt;/);
  assert.match(card, /Body &lt;b&gt;/);
  assert.doesNotMatch(card, /<script>/);

  const empty = notesView.notesGridHTML(notesView.notesViewModel({ notes, query: "Missing <script>", sourceFilter: "all" }));
  assert.match(empty, /data-search-empty="notes"/);
  assert.doesNotMatch(empty, /<script>/);
}

function testHabitsViewModelAndEscapes() {
  const runtime = loadRuntime("habits-view.js");
  const habitsView = runtime.JooParkHabitsView.create({
    html,
    raw,
    matches,
    todayISO: () => "2026-06-09",
    weekDatesFor,
    habitStreak: (habit) => ({ current: habit.current || 0, longest: habit.longest || 0 }),
    formatKoreanShort: (value) => value,
    kpiCard,
    panelHead,
    searchEmptyState,
    weekdaysKo: ["일", "월", "화", "수", "목", "금", "토"],
    noteColors: ["#2387ff"],
  });
  const habits = [
    { id: "alpha", name: "Alpha <script>", emoji: "A", target: 3, log: { "2026-06-08": true, "2026-06-09": true }, current: 2, longest: 4 },
    { id: "archived", name: "Archived", archived: true, log: { "2026-06-09": true }, longest: 8 },
  ];

  const model = habitsView.habitsViewModel({ habits, query: "Alpha" });
  assert.deepEqual(model.active.map((habit) => habit.id), ["alpha"]);
  assert.deepEqual(model.list.map((habit) => habit.id), ["alpha"]);
  assert.equal(model.kpis[0].value, "1");
  assert.equal(model.kpis[1].value, "1");
  assert.equal(model.kpis[3].value, "4");

  const card = habitsView.habitCard(habits[0], model);
  assert.match(card, /Alpha &lt;script&gt;/);
  assert.doesNotMatch(card, /<script>/);

  const empty = habitsView.habitsGridHTML(habitsView.habitsViewModel({ habits, query: "Missing <script>" }));
  assert.match(empty, /data-search-empty="habits"/);
  assert.match(empty, /Missing &lt;script&gt;/);
}

function testStatsViewModelAndEscapes() {
  const runtime = loadRuntime("stats-view.js");
  const statsView = runtime.JooParkStatsView.create({
    html,
    raw,
    todayISO: () => "2026-06-09",
    localYmd: (value) => String(value || "").slice(0, 10),
    addDaysISO,
    dateFromISO,
    weekDatesFor,
    habitStreak: (habit) => ({ current: habit.current || 0, longest: habit.longest || 0 }),
    spark: (points) => points.join(","),
    kpiCard,
    panelHead,
    eventCats: {
      deadline: { label: "마감 <script>", color: "var(--red)" },
      etc: { label: "기타", color: "var(--cyan)" },
    },
    eventCatOrder: ["deadline", "etc"],
    weekdaysKo: ["일", "월", "화", "수", "목", "금", "토"],
  });
  const model = statsView.statsViewModel({
    todos: [
      { id: "created", createdAt: "2026-06-09T08:00:00", done: false, due: "2026-06-10" },
      { id: "done", createdAt: "2026-06-01T08:00:00", done: true, completedAt: "2026-06-09T09:00:00" },
    ],
    habits: [{ id: "habit", name: "Alpha <script>", log: { "2026-06-09": true }, current: 1 }],
    events: [{ id: "event", category: "deadline", date: "2026-06-11" }],
  });

  assert.equal(model.kpis[0].value, "1");
  assert.equal(model.kpis[1].value, "50");
  assert.equal(model.kpis[3].value, "2");
  assert.equal(model.createdByDay.at(-1), 1);
  assert.equal(model.completedByDay.at(-1), 1);
  assert.equal(model.categoryItems[0].label, "마감 <script>");

  const chart = statsView.barChart([{ label: "Alpha <script>", value: 2, color: "var(--cyan)" }]);
  assert.match(chart, /Alpha &lt;script&gt;/);
  assert.doesNotMatch(chart, /<script>/);

  const habitSummary = statsView.habitSummarySection(model);
  assert.match(habitSummary, /Alpha &lt;script&gt;/);
}

function testDashboardConfidenceBounds() {
  const viewRuntime = loadRuntime("dashboard-view.js");
  const dashboardView = viewRuntime.JooParkDashboardView.create({ html, raw });
  assert.equal(dashboardView.confidenceText(Infinity), "0.00");
  assert.equal(dashboardView.confidenceText(2), "1.00");
  assert.equal(dashboardView.confidenceText(-1), "0.00");
  const rendered = dashboardView.renderDashboardIntelligenceHTML({
    cards: [],
    loops: [],
    latestReceipt: null,
    candidates: [
      { summary: "Candidate", confidence: Infinity, scoreBreakdown: { weighted: 1 }, verificationStatus: "pass", nextAction: { label: "Go" } },
    ],
    externalResearchSources: [
      { id: "s1", title: "Source", confidence: Infinity, checkedAt: "today" },
    ],
  });
  assert.doesNotMatch(rendered, /Infinity/);
  assert.match(rendered, /confidence 0\.00/);
  assert.match(rendered, /data-dashboard-external-source-confidence="0\.00"/);

  const receiptRuntime = loadRuntime("dashboard-evidence-receipts.js");
  const receipts = receiptRuntime.JooParkDashboardEvidenceReceipts.create();
  assert.equal(receipts.confidenceText(Infinity), "0.00");
  const markdown = receipts.receiptMarkdown({ id: "r1", createdAt: "now", verificationStatus: "pass", confidence: Infinity, receiptHash: "hash", summary: "Summary" });
  assert.doesNotMatch(markdown, /Infinity/);
  assert.match(markdown, /- confidence: 0\.00/);
}

function testDashboardAutoresearchConfidenceBounds() {
  const runtime = loadRuntime("dashboard-autoresearch-loop.js");
  const loop = runtime.JooParkDashboardAutoresearchLoop.create();
  assert.equal(loop.boundedConfidence(Infinity), 0.72);
  assert.equal(loop.boundedConfidence("bad", 0.64), 0.64);
  assert.equal(loop.boundedConfidence(2), 1);
  assert.equal(loop.boundedConfidence(0), 0);

  const appended = [];
  const storage = {
    ensureCollections() {},
    appendRecord(_dashboard, collection, record) {
      appended.push({ collection, record });
      return record;
    },
    collectionSummary() {
      return [{ key: "dashboardResearchLoops", count: 1, retention: 40 }];
    },
  };
  const prioritization = { rankCandidates: (items) => items };
  const receipts = { createReceipt: (record) => record };
  const insightsEngine = {
    dashboardInsightsModel: () => ({
      candidates: [
        { id: "c1", summary: "Candidate", confidence: Infinity, scoreBreakdown: { weighted: 10 }, verificationStatus: "pass" },
      ],
      cards: [],
      externalResearchSources: [],
      sourceSummary: {},
    }),
  };
  const result = loop.runLoop({ dashboard: {}, storage, prioritization, receipts, insightsEngine, createdAt: "2026-06-10T00:00:00.000Z" });
  assert.equal(Number.isFinite(result.loopRecord.confidence), true);
  assert.equal(Number.isFinite(result.rankedCandidates[0].confidence), true);
  assert.equal(Number.isFinite(result.decisionReceipt.confidence), true);
  assert.equal(result.loopRecord.confidence, 0.72);
  assert.equal(result.rankedCandidates[0].confidence, 0.72);
  assert.equal(result.decisionReceipt.confidence, 0.72);
  assert.equal(JSON.stringify(result.loopRecord).includes("null"), false);
  assert.equal(appended.find((item) => item.collection === "dashboardImprovementCandidates").record.confidence, 0.72);
}

function fakeClassList() {
  const classes = new Set();
  return {
    add(value) {
      classes.add(value);
    },
    remove(value) {
      classes.delete(value);
    },
    toggle(value, force) {
      if (force === undefined ? !classes.has(value) : force) classes.add(value);
      else classes.delete(value);
    },
    contains(value) {
      return classes.has(value);
    },
  };
}

function fakeElement(extra = {}) {
  return {
    attributes: {},
    classList: fakeClassList(),
    dataset: {},
    hidden: false,
    innerHTML: "",
    listeners: {},
    readOnly: false,
    textContent: "",
    value: "",
    addEventListener(type, callback) {
      if (!this.listeners[type]) this.listeners[type] = [];
      this.listeners[type].push(callback);
    },
    closest() {
      return this.closestTarget || null;
    },
    focus() {
      this.focused = true;
    },
    getBoundingClientRect() {
      return { top: 0 };
    },
    querySelector() {
      return null;
    },
    querySelectorAll() {
      return [];
    },
    removeAttribute(name) {
      delete this.attributes[name];
    },
    scrollIntoView() {},
    setAttribute(name, value) {
      this.attributes[name] = String(value);
    },
    ...extra,
  };
}

function testCommandPaletteBuildRenderAndEscapes() {
  const runtime = loadRuntime("command-palette.js");
  let openedTodoId = "";
  const elements = {
    palette: fakeElement(),
    paletteInput: fakeElement(),
    paletteResults: fakeElement(),
    paletteStatus: fakeElement(),
  };
  const documentRef = {
    activeElement: null,
    body: fakeElement(),
    getElementById(id) {
      return elements[id] || null;
    },
  };
  const palette = runtime.JooParkCommandPalette.create({
    document: documentRef,
    matches,
    maxHits: 5,
    getDashboard: () => ({
      todos: [
        { id: "todo-alpha", title: "Alpha <script>", category: "Ops", memo: "Beta", sourceKey: "llm-wiki:todo:alpha" },
      ],
      deletedItems: [{ id: "deleted" }],
    }),
    openTodoRecord: (todo) => { openedTodoId = todo.id; },
    formatKoreanShort: (value) => value,
  });

  const items = palette.buildItems("Alpha <script>");
  assert.equal(items.some((item) => item.label === "Alpha <script>"), true);

  palette.render("Alpha <script>");
  assert.match(elements.paletteResults.innerHTML, /Alpha &lt;script&gt;/);
  assert.doesNotMatch(elements.paletteResults.innerHTML, /<script>/);
  assert.equal(elements.paletteInput.attributes["aria-activedescendant"], "pal-option-0");

  palette.render("no-such-command");
  assert.equal(elements.paletteResults.innerHTML, "");
  assert.match(elements.paletteStatus.textContent, /검색 결과가 없습니다/);
  assert.equal(elements.paletteStatus.classList.contains("is-visible"), true);

  palette.render("Alpha");
  palette.runIndex("not-a-number");
  assert.equal(openedTodoId, "");
  palette.runIndex(0);
  assert.equal(openedTodoId, "todo-alpha");
}

function testCommandPaletteUnusedAppWrappersRemoved() {
  const appSource = readFileSync(join(root, "app.js"), "utf8");
  const structureSource = readFileSync(join(root, "scripts/check-app-structure.mjs"), "utf8");
  const auditSource = readFileSync(join(root, "scripts/audit-release-readiness.mjs"), "utf8");
  const removedWrappers = [
    "function _palStatusEl",
    "function setPaletteStatus",
    "function _buildPaletteItems",
    "function renderPaletteResults",
    "function _palRunIndex",
  ];
  for (const wrapper of removedWrappers) {
    assert.equal(appSource.includes(wrapper), false);
  }
  assert.match(appSource, /function commandPaletteCall\(name, \.\.\.args\)/);
  assert.equal(appSource.includes("function openPalette"), false);
  assert.equal(appSource.includes("function closePalette"), false);
  assert.match(appSource, /\["open-palette", \(\) => commandPaletteCall\("open"\)\]/);
  assert.match(appSource, /\["close-palette", \(\) => commandPaletteCall\("close"\)\]/);
  assert.match(appSource, /openPalette: \(\) => commandPaletteCall\("open"\)/);
  assert.match(appSource, /closePalette: \(\) => commandPaletteCall\("close"\)/);
  assert.match(appSource, /commandPaletteCall\("setup"\)/);
  assert.match(structureSource, /function commandPaletteCall/);
  assert.equal(structureSource.includes("function openPalette"), false);
  assert.equal(structureSource.includes("function closePalette"), false);
  assert.equal(auditSource.includes("function openPalette"), false);
  assert.equal(auditSource.includes("function closePalette"), false);
  assert.equal(structureSource.includes("commandPaletteCall(\\\"open\\\"") || structureSource.includes("commandPaletteCall(\"open\""), true);
  assert.equal(auditSource.includes("commandPaletteCall(\\\"open\\\"") || auditSource.includes("commandPaletteCall(\"open\""), true);
  assert.equal(structureSource.includes("commandPaletteCall(\\\"close\\\"") || structureSource.includes("commandPaletteCall(\"close\""), true);
  assert.equal(auditSource.includes("commandPaletteCall(\\\"close\\\"") || auditSource.includes("commandPaletteCall(\"close\""), true);
  assert.equal(structureSource.includes("commandPaletteCall(\"setup\"") || structureSource.includes("commandPaletteCall(\\\"setup\\\""), true);
  assert.match(auditSource, /function commandPaletteCall/);
  assert.equal(auditSource.includes("commandPaletteCall(\"setup\"") || auditSource.includes("commandPaletteCall(\\\"setup\\\""), true);
}

function testImportGuardUnusedAppWrappersRemoved() {
  const appSource = readFileSync(join(root, "app.js"), "utf8");
  const auditSource = readFileSync(join(root, "scripts/audit-release-readiness.mjs"), "utf8");
  const smokeSource = readFileSync(join(root, "scripts/smoke-delete-undo.mjs"), "utf8");
  const removedWrappers = [
    "const IMPORT_ARRAY_KEYS",
    "const IMPORT_RECORD_LIMITS",
    "function isImportBackupShape",
    "function importArrayCount",
    "function importGanttTaskCount",
    "function importSchemaTableCount",
    "function importBackupSummaryItems",
    "function importRecordLimitViolations",
    "function importRecordLimitMessage",
  ];
  for (const wrapper of removedWrappers) {
    assert.equal(appSource.includes(wrapper), false);
  }
  assert.equal(auditSource.includes('{ file: "app.js", terms: ["const IMPORT_ARRAY_KEYS = IMPORT_GUARDS.arrayKeys"'), false);
  assert.equal(auditSource.includes('{ file: "app.js", terms: ["function importBackupSummaryItems"'), false);
  assert.equal(auditSource.includes('{ file: "app.js", terms: ["const IMPORT_RECORD_LIMITS = IMPORT_GUARDS.recordLimits"'), false);
  assert.match(appSource, /const IMPORT_GUARDS = window\.JooParkImportGuards/);
  assert.match(appSource, /importGuards: IMPORT_GUARDS/);
  assert.match(appSource, /function importBackupSummaryHTML\(obj\) \{\s*return backupImportUiCall\("importBackupSummaryHTML", obj\);\s*\}/);
  assert.match(auditSource, /importGuards: IMPORT_GUARDS/);
  assert.match(smokeSource, /const importGuards = window\.JooParkImportGuards/);
  assert.match(smokeSource, /importGuards\.isBackupShape\(deletedImportShape\)/);
  assert.match(smokeSource, /importGuards\.backupSummaryItems\(deletedImportShape\)/);
  assert.match(smokeSource, /importGuards\.recordLimitViolations\(/);
}

function testGlobalSearchUnusedAppWrappersRemoved() {
  const appSource = readFileSync(join(root, "app.js"), "utf8");
  const globalSearchSource = readFileSync(join(root, "global-search.js"), "utf8");
  const structureSource = readFileSync(join(root, "scripts/check-app-structure.mjs"), "utf8");
  const auditSource = readFileSync(join(root, "scripts/audit-release-readiness.mjs"), "utf8");
  const removedWrappers = [
    "function announceInertSearch",
    "function currentSearchStatus",
    "function revealSearchEmptyIfNeeded",
    "function clearGlobalSearch",
    "function setupGlobalSearch",
  ];
  const hasTerm = (source, term) => source.includes(term) || source.includes(term.replaceAll("\"", "\\\""));
  for (const wrapper of removedWrappers) {
    assert.equal(appSource.includes(wrapper), false);
    assert.equal(structureSource.includes(wrapper), false);
    assert.equal(auditSource.includes(wrapper), false);
  }
  assert.match(appSource, /function isSearchInertView\(view = dashboard\.currentView\) \{ return globalSearchCall\("isInertView", view\); \}/);
  assert.match(appSource, /function syncSearchClearControl\(\) \{ return globalSearchCall\("clearControl"\); \}/);
  assert.match(appSource, /function syncSearchAffordance\(\{ announce = false \} = \{\}\) \{ return globalSearchCall\("syncAffordance", \{ announce \}\); \}/);
  assert.match(appSource, /\["clear-search", \(\) => globalSearchCall\("clear"\)\]/);
  assert.match(appSource, /globalSearchCall\("setup"\)/);
  assert.match(globalSearchSource, /function announceInert\(\)/);
  assert.match(globalSearchSource, /function status\(\)/);
  assert.match(globalSearchSource, /function revealEmptyIfNeeded\(\)/);
  assert.equal(hasTerm(structureSource, "globalSearchCall(\"clearControl\""), true);
  assert.equal(hasTerm(structureSource, "globalSearchCall(\"syncAffordance\""), true);
  assert.equal(hasTerm(structureSource, "globalSearchCall(\"clear\""), true);
  assert.equal(hasTerm(structureSource, "globalSearchCall(\"setup\""), true);
  assert.equal(hasTerm(auditSource, "globalSearchCall(\"clearControl\""), true);
  assert.equal(hasTerm(auditSource, "globalSearchCall(\"syncAffordance\""), true);
  assert.equal(hasTerm(auditSource, "globalSearchCall(\"clear\""), true);
  assert.equal(hasTerm(auditSource, "globalSearchCall(\"setup\""), true);
}

function testReviewStateUnusedAppWrappersRemoved() {
  const appSource = readFileSync(join(root, "app.js"), "utf8");
  const reviewResultStateSource = readFileSync(join(root, "review-result-state.js"), "utf8");
  const reviewArtifactStateSource = readFileSync(join(root, "review-artifact-state.js"), "utf8");
  const structureSource = readFileSync(join(root, "scripts/check-app-structure.mjs"), "utf8");
  const auditSource = readFileSync(join(root, "scripts/audit-release-readiness.mjs"), "utf8");
  const removedWrappers = [
    "function applyReviewArtifactRepairBody",
    "function reviewResultRecordRepairSnapshot",
    "function reviewResultPostRepairReceiptModel",
  ];
  const hasTerm = (source, term) => source.includes(term) || source.includes(term.replaceAll("\"", "\\\""));
  for (const wrapper of removedWrappers) {
    assert.equal(appSource.includes(wrapper), false);
    assert.equal(structureSource.includes(wrapper), false);
    assert.equal(auditSource.includes(wrapper), false);
  }
  assert.match(appSource, /function reviewArtifactRepairPreview\(target\) \{\s*return reviewArtifactStateCall\("repairPreview", target\);\s*\}/);
  assert.match(appSource, /function undoReviewArtifactRepair\(target\) \{\s*return reviewArtifactStateCall\("undoRepair", target\);\s*\}/);
  assert.match(appSource, /function attachReviewResultRepairReceipt\(validator, saved, result, warnings\) \{\s*return reviewResultStateCall\("attachRepairReceipt", validator, saved, result, warnings\);\s*\}/);
  assert.match(reviewArtifactStateSource, /function applyRepairBody\(repair\)/);
  assert.match(reviewResultStateSource, /function recordRepairSnapshot\(validator, state, message, details\)/);
  assert.match(reviewResultStateSource, /function postRepairReceiptModel\(validator, result, warnings, saved\)/);
  assert.equal(hasTerm(structureSource, "reviewArtifactStateCall(\"undoRepair\""), true);
  assert.equal(hasTerm(auditSource, "reviewArtifactStateCall(\"undoRepair\""), true);
  assert.equal(hasTerm(auditSource, "reviewResultStateCall(\"attachRepairReceipt\""), true);
}

function testReviewIssuePayloadUnusedAppWrappersRemoved() {
  const appSource = readFileSync(join(root, "app.js"), "utf8");
  const payloadSource = readFileSync(join(root, "review-issue-payload.js"), "utf8");
  const auditSource = readFileSync(join(root, "scripts/audit-release-readiness.mjs"), "utf8");
  const hasTerm = (source, term) => source.includes(term) || source.includes(term.replaceAll("\"", "\\\""));
  assert.equal(appSource.includes("function reviewOwnerToAssignee"), false);
  assert.equal(auditSource.includes("function reviewOwnerToAssignee"), false);
  assert.match(appSource, /function reviewOwnerAssignment\(owner, project\)/);
  assert.match(appSource, /function reviewSavedResultTrackerFields\(saved, draft\) \{\s*return reviewIssuePayloadCall\("reviewSavedResultTrackerFields", saved, draft\);\s*\}/);
  assert.match(payloadSource, /const reviewOwnerAssignment = options\.reviewOwnerAssignment/);
  assert.match(payloadSource, /const assignment = reviewOwnerAssignment\(owner, project\)/);
  assert.match(auditSource, /function reviewOwnerAssignment/);
  assert.equal(hasTerm(auditSource, 'reviewIssuePayloadCall("reviewSavedResultTrackerFields"'), true);
}

function testHomeExecutionUnusedAppWrappersRemoved() {
  const appSource = readFileSync(join(root, "app.js"), "utf8");
  const homeExecutionSource = readFileSync(join(root, "home-execution-view.js"), "utf8");
  const auditSource = readFileSync(join(root, "scripts/audit-release-readiness.mjs"), "utf8");
  const removedWrappers = [
    "function homeExecutionReasonChipsHTML",
    "function homeExecutionBucketSummaryHTML",
  ];
  for (const wrapper of removedWrappers) {
    assert.equal(appSource.includes(wrapper), false);
  }
  assert.equal(auditSource.includes('{ file: "app.js", terms: ["HOME_EXECUTION_DUE_REASON_LABEL", "function homeExecutionReasonChipsHTML"'), false);
  assert.equal(auditSource.includes('{ file: "app.js", terms: ["HOME_EXECUTION_BUCKET_LABEL", "function homeExecutionBucketSummary", "function homeExecutionBucketSummaryHTML"'), false);
  assert.match(appSource, /function homeExecutionReasonKey\(chips\)/);
  assert.match(appSource, /function homeExecutionBucketSummary\(items\)/);
  assert.match(appSource, /function homeExecutionBucketKey\(buckets\)/);
  assert.match(homeExecutionSource, /function homeExecutionReasonChipsHTML\(item\)/);
  assert.match(homeExecutionSource, /function homeExecutionBucketSummaryHTML\(model\)/);
  assert.match(auditSource, /function homeExecutionReasonKey/);
  assert.match(auditSource, /function homeExecutionBucketKey/);
}

function testCalendarUnusedAppWrapperRemoved() {
  const appSource = readFileSync(join(root, "app.js"), "utf8");
  const calendarSource = readFileSync(join(root, "calendar-view.js"), "utf8");
  const structureSource = readFileSync(join(root, "scripts/check-app-structure.mjs"), "utf8");
  const auditSource = readFileSync(join(root, "scripts/audit-release-readiness.mjs"), "utf8");
  assert.equal(appSource.includes("function calLegend"), false);
  assert.match(appSource, /function calendarViewCall\(name, \.\.\.args\)/);
  assert.match(appSource, /calendarViewCall\("renderCalendarHTML"/);
  assert.match(calendarSource, /function calLegend\(\)/);
  assert.match(structureSource, /function calLegend/);
  assert.match(auditSource, /function calLegend/);
}

function testTodoUnusedAppWrappersRemoved() {
  const appSource = readFileSync(join(root, "app.js"), "utf8");
  const todoSource = readFileSync(join(root, "todo-view.js"), "utf8");
  const structureSource = readFileSync(join(root, "scripts/check-app-structure.mjs"), "utf8");
  const auditSource = readFileSync(join(root, "scripts/audit-release-readiness.mjs"), "utf8");
  assert.equal(appSource.includes("function todoMatchesFilter"), false);
  assert.equal(appSource.includes("function todoRow"), false);
  assert.match(appSource, /function todoViewCall\(name, \.\.\.args\)/);
  assert.match(appSource, /todoViewCall\("renderTodosHTML"/);
  assert.match(todoSource, /function todoMatchesFilter\(todo, filter\)/);
  assert.match(todoSource, /function todoRow\(todo\)/);
  assert.match(structureSource, /function todoMatchesFilter/);
  assert.match(structureSource, /function todoRow/);
  assert.match(auditSource, /function todoMatchesFilter/);
  assert.match(auditSource, /function todoRow/);
}

function testDialogShellUnusedAppWrapperRemoved() {
  const appSource = readFileSync(join(root, "app.js"), "utf8");
  const dialogShellSource = readFileSync(join(root, "dialog-shell.js"), "utf8");
  const structureSource = readFileSync(join(root, "scripts/check-app-structure.mjs"), "utf8");
  const auditSource = readFileSync(join(root, "scripts/audit-release-readiness.mjs"), "utf8");
  assert.equal(appSource.includes("function setNotificationTriggerExpanded"), false);
  assert.match(appSource, /function dialogShellCall\(name, \.\.\.args\)/);
  assert.match(appSource, /dialogShellCall\("openSheet"/);
  assert.match(appSource, /dialogShellCall\("closeSheet"/);
  assert.match(appSource, /dialogShellCall\("openModal"/);
  assert.match(appSource, /dialogShellCall\("trapTab"/);
  assert.match(dialogShellSource, /function setNotificationTriggerExpanded\(expanded\)/);
  assert.match(dialogShellSource, /setNotificationTriggerExpanded\(openOptions\.notificationExpanded === true\)/);
  assert.match(dialogShellSource, /setNotificationTriggerExpanded\(false\)/);
  assert.equal(structureSource.includes("dialogShellCall(\\\"openSheet\\\""), true);
  assert.match(auditSource, /function setNotificationTriggerExpanded/);
}

function testProjectPickerThinAppWrappersRemoved() {
  const appSource = readFileSync(join(root, "app.js"), "utf8");
  const projectPickerSource = readFileSync(join(root, "project-picker.js"), "utf8");
  const structureSource = readFileSync(join(root, "scripts/check-app-structure.mjs"), "utf8");
  const auditSource = readFileSync(join(root, "scripts/audit-release-readiness.mjs"), "utf8");
  const hasTerm = (source, term) => source.includes(term) || source.includes(term.replaceAll("\"", "\\\""));
  assert.equal(appSource.includes("function setProjectPickerOpen"), false);
  assert.equal(appSource.includes("function projectPickerIsOpen"), false);
  assert.equal(structureSource.includes("function setProjectPickerOpen"), false);
  assert.equal(structureSource.includes("function projectPickerIsOpen"), false);
  assert.equal(auditSource.includes("function setProjectPickerOpen"), false);
  assert.equal(auditSource.includes("function projectPickerIsOpen"), false);
  assert.match(appSource, /function projectPickerCall\(name, \.\.\.args\)/);
  assert.match(appSource, /projectPickerCall\("setOpen", false\)/);
  assert.match(appSource, /projectPickerIsOpen: \(\) => projectPickerCall\("isOpen"\)/);
  assert.match(appSource, /setProjectPickerOpen: \(open\) => projectPickerCall\("setOpen", open\)/);
  assert.match(appSource, /if \(projectPickerCall\("isOpen"\)\) projectPickerCall\("renderOptions"\);/);
  assert.match(projectPickerSource, /function setOpen\(open\)/);
  assert.match(projectPickerSource, /function isOpen\(\)/);
  assert.equal(hasTerm(structureSource, "projectPickerCall(\"setOpen\""), true);
  assert.equal(hasTerm(structureSource, "projectPickerCall(\"isOpen\""), true);
  assert.equal(hasTerm(structureSource, "projectPickerCall(\"renderOptions\""), true);
  assert.equal(hasTerm(auditSource, "projectPickerCall(\"setOpen\""), true);
  assert.equal(hasTerm(auditSource, "projectPickerCall(\"isOpen\""), true);
  assert.equal(hasTerm(auditSource, "projectPickerCall(\"renderOptions\""), true);
}

function testInteractionSetupSingleUseAppWrapperRemoved() {
  const appSource = readFileSync(join(root, "app.js"), "utf8");
  const structureSource = readFileSync(join(root, "scripts/check-app-structure.mjs"), "utf8");
  assert.equal(appSource.includes("function setupDelegatedInteractions"), false);
  assert.equal(structureSource.includes("function setupDelegatedInteractions"), false);
  assert.match(appSource, /function interactionSetupCall\(name, \.\.\.args\)/);
  assert.match(appSource, /function setupInteractions\(\) \{\s*keyboardShortcutCall\("setup"\);\s*interactionSetupCall\("setup"\);/);
  assert.equal(structureSource.includes("interactionSetupCall(\\\"setup\\\""), true);
}

function testFooterClockSingleUseAppWrapperRemoved() {
  const appSource = readFileSync(join(root, "app.js"), "utf8");
  const footerClockSource = readFileSync(join(root, "footer-clock.js"), "utf8");
  const structureSource = readFileSync(join(root, "scripts/check-app-structure.mjs"), "utf8");
  assert.equal(appSource.includes("function setupFooterClockVisibility"), false);
  assert.equal(structureSource.includes("function setupFooterClockVisibility"), false);
  assert.match(appSource, /function footerClockCall\(name, \.\.\.args\)/);
  assert.match(appSource, /footerClockCall\("update"\)/);
  assert.match(appSource, /footerClockCall\("schedule"\)/);
  assert.match(appSource, /footerClockCall\("setupVisibility"\)/);
  assert.match(footerClockSource, /function setupVisibility\(\)/);
  assert.match(footerClockSource, /documentRef\.addEventListener\("visibilitychange"/);
  assert.equal(structureSource.includes("footerClockCall(\\\"setupVisibility\\\""), true);
}

function testEventReminderSingleUseAppWrapperRemoved() {
  const appSource = readFileSync(join(root, "app.js"), "utf8");
  const eventReminderSource = readFileSync(join(root, "event-reminders.js"), "utf8");
  const structureSource = readFileSync(join(root, "scripts/check-app-structure.mjs"), "utf8");
  assert.equal(appSource.includes("function startEventReminders"), false);
  assert.equal(appSource.includes("startEventReminders()"), false);
  assert.equal(structureSource.includes("function startEventReminders"), false);
  assert.match(appSource, /function eventReminderCall\(name, \.\.\.args\)/);
  assert.match(appSource, /eventReminderCall\("start"\)/);
  assert.match(eventReminderSource, /function start\(\)/);
  assert.match(eventReminderSource, /function remindUpcomingEvents\(now = new Date\(\)\)/);
  assert.equal(structureSource.includes("eventReminderCall(\\\"start\\\""), true);
}

function testGlobalSearchStateAndEscapes() {
  const runtime = loadRuntime("global-search.js");
  let currentView = "todo";
  let rendered = 0;
  let paletteOpened = 0;
  const shell = fakeElement();
  const query = fakeElement({
    closest() {
      return shell;
    },
  });
  const searchCount = fakeElement();
  const clearButton = fakeElement();
  const viewNode = fakeElement({
    querySelector() {
      return null;
    },
    querySelectorAll(selector) {
      return selector === "[data-search-result]" ? [{}, {}] : [];
    },
  });
  const state = { query: "Alpha <script>" };
  const globalSearch = runtime.JooParkGlobalSearch.create({
    refs: {
      query,
      searchCount,
      searchClear: clearButton,
      views: { todo: viewNode, home: viewNode },
    },
    state,
    getCurrentView: () => currentView,
    renderCurrentView: () => { rendered += 1; },
    openPalette: () => { paletteOpened += 1; },
    debounce: (fn) => fn,
    window: {
      innerHeight: 900,
      requestAnimationFrame: (fn) => fn(),
      scrollTo() {},
    },
    document: {
      querySelector() {
        return null;
      },
    },
  });

  assert.equal(globalSearch.status(), "2개 결과");
  globalSearch.syncAffordance();
  assert.equal(searchCount.textContent, "2개 결과");
  assert.doesNotMatch(searchCount.textContent, /<script>/);
  assert.equal(clearButton.hidden, false);
  assert.equal(shell.dataset.searchScope, "view");

  globalSearch.setup();
  query.listeners.input[0]({ target: { value: "Alpha <script>" } });
  assert.equal(state.query, "Alpha <script>");
  assert.equal(rendered, 1);
  assert.equal(searchCount.textContent, "2개 결과");

  currentView = "home";
  query.value = "Alpha <script>";
  globalSearch.syncAffordance({ announce: true });
  assert.equal(state.query, "");
  assert.equal(query.value, "");
  assert.equal(query.readOnly, true);
  assert.equal(query.attributes["aria-label"], "이 화면은 현재 뷰 검색을 지원하지 않음. 명령 팔레트로 이동 또는 통합 검색");
  assert.doesNotMatch(searchCount.textContent, /<script>/);

  const inertKeyEvent = {
    key: "a",
    metaKey: false,
    ctrlKey: false,
    altKey: false,
    defaultPrevented: false,
    preventDefault() {
      this.defaultPrevented = true;
    },
  };
  query.listeners.keydown.forEach((listener) => listener(inertKeyEvent));
  assert.equal(inertKeyEvent.defaultPrevented, true);
  assert.equal(paletteOpened, 1);
}

function testReviewExecutionChecklistHelpers() {
  const runtime = loadRuntime("review-execution-checklist.js");
  const factory = runtime.JooParkReviewExecutionChecklist;
  assert.equal(typeof factory.create, "function");

  // Missing required deps must be rejected, not silently degraded.
  assert.throws(() => factory.create({}), /requires saved result parser/);

  const checklist = factory.create({
    parseSavedReviewResult: (saved) => (saved && saved.result ? saved.result : null),
    reviewPrimaryDecision: (decisions) => decisions[0] || {},
  });

  // String and object items normalize to a common shape; blank text is dropped.
  const items = checklist.issueExecutionChecklistItems({
    executionChecklist: ["First task", { id: "x", text: "Second", done: true }, { text: "   " }, "  "],
  });
  // Objects/arrays cross the vm realm boundary, so compare fields, not references.
  assert.equal(items.length, 2);
  assert.equal(items[0].id, "exec-1");
  assert.equal(items[0].text, "First task");
  assert.equal(items[0].done, false);
  assert.equal(items[1].id, "x");
  assert.equal(items[1].text, "Second");
  assert.equal(items[1].done, true);

  // Progress arithmetic + Korean label boundaries.
  const progress = checklist.issueExecutionChecklistProgress({
    executionChecklist: [{ text: "a", done: true }, { text: "b", done: false }],
  });
  assert.equal(progress.total, 2);
  assert.equal(progress.done, 1);
  assert.equal(progress.remaining, 1);
  assert.equal(progress.percent, 50);
  assert.equal(progress.label, "1/2 완료");
  const emptyProgress = checklist.issueExecutionChecklistProgress({ executionChecklist: [] });
  assert.equal(emptyProgress.percent, 0);
  assert.equal(emptyProgress.label, "체크리스트 없음");

  // Markdown rendering uses GitHub task-list syntax; empty falls back to a notice line.
  assert.equal(checklist.reviewExecutionChecklistLines([{ text: "Do", done: true }]).join("\n"), "- [x] Do");
  assert.equal(checklist.reviewExecutionChecklistLines([]).join("\n"), "- [ ] No execution checklist supplied.");
  assert.equal(checklist.reviewExecutionChecklistCountLabel([{ text: "a" }, { text: "b" }]), "2개");
  assert.equal(checklist.reviewExecutionChecklistCountLabel([]), "없음");

  // firstPositiveTimeboxHours skips zero/negative/non-finite entries.
  assert.equal(checklist.firstPositiveTimeboxHours([{ timeboxHours: 0 }, { timeboxHours: -3 }, { timeboxHours: 6 }]), 6);
  assert.equal(checklist.firstPositiveTimeboxHours([]), undefined);

  // Saved-result derivation: dedups across primary decision + execution plan, caps at 8.
  const derived = checklist.reviewExecutionChecklistItemsFromSavedResult({
    key: "k",
    result: {
      decisions: [{ acceptanceCriteria: ["AC1"], validationPlan: ["VP1"] }],
      executionPlan: [{ firstAction: "Ship it", acceptanceCriteria: ["AC2"], validationPlan: ["VP2"] }],
    },
  });
  assert.equal(
    derived.map((item) => item.text).join("|"),
    "First action: Ship it|Acceptance: AC1|Acceptance: AC2|Validation: VP1|Validation: VP2",
  );
  assert.equal(derived[0].id, "exec-1");
  // Unparseable saved result yields an empty checklist rather than throwing.
  assert.equal(checklist.reviewExecutionChecklistItemsFromSavedResult({ key: "k" }).length, 0);
}

function testReviewIssuePayloadHelpers() {
  const runtime = loadRuntime("review-issue-payload.js");
  const factory = runtime.JooParkReviewIssuePayload;
  const noop = () => {};
  const deps = {
    shortCommit: (commit) => (commit ? String(commit).slice(0, 7) : ""),
    metricValue: (value) => (value == null ? "0" : String(value)),
    parseSavedReviewResult: (saved) => (saved && saved.result ? saved.result : null),
    projectByIdOrName: noop,
    reviewExecutionChecklistItemsFromSavedResult: () => [],
    reviewOwnerAssignment: () => ({}),
    reviewOwnerFollowUpItems: () => [],
    reviewOwnerPromptExamples: () => [],
    todayISO: () => "2026-06-09",
    addDays: (iso, days) => `${iso}+${days}d`,
  };

  // Every declared dependency is mandatory.
  assert.throws(() => factory.create({}), /review issue payload helper requires/);

  const payload = factory.create(deps);

  // Markdown section extraction is pure: it isolates the named heading's body and trims.
  const doc = "## Decision Summary\n- one\n- two\n\n## Decision\n- three";
  assert.equal(payload.reviewMarkdownSection(doc, "Decision Summary"), "- one\n- two");
  assert.equal(payload.reviewMarkdownSection(doc, "Decision"), "- three");
  assert.equal(payload.reviewMarkdownSection(doc, "Nope"), "");
  assert.equal(payload.reviewMarkdownSection("", "Decision"), "");

  // Operational readiness lines fill defaults when fields are absent.
  const opLines = payload.reviewOperationalReadinessLines({});
  assert.equal(opLines[0], "## Operational Readiness");
  assert.ok(opLines.some((line) => line === "- Owner: PM reviewer"));
  assert.ok(opLines.some((line) => line === "- Timebox hours: 4"));
  assert.equal(payload.reviewOperationalReadinessLines({ timeboxHours: "Infinity" }).find((line) => line.includes("Timebox hours")), "- Timebox hours: 4");

  // Due-date math: ceil(hours/8)-1 day offset, with non-positive/non-finite rejected.
  assert.equal(payload.reviewExecutionDueDate(0), "");
  assert.equal(payload.reviewExecutionDueDate("oops"), "");
  assert.equal(payload.reviewExecutionDueDate(4), "2026-06-09+0d");
  assert.equal(payload.reviewExecutionDueDate(16), "2026-06-09+1d");

  // Full body assembles the expected sections and echoes the decision.
  const body = payload.reviewIssueBodyLines({
    project: { name: "Proj", url: "http://x", lastCommit: "abcdef1234567", pushedAt: "2026-06-01", stars: 3, forks: 1, openIssues: 2, risks: 0, language: "JS" },
    decision: { status: "adopt", label: "score", score: 9, persistKey: "pk", reason: "solid" },
    secondary: null,
    scope: "all",
    timeboxHours: 4,
  });
  assert.match(body, /## Decision Summary/);
  assert.match(body, /Recommendation: Proj -> adopt \(score 9\)/);
  assert.match(body, /## Acceptance Criteria/);
  assert.match(body, /## Timebox: 4 hours/);
  assert.match(body, /Last commit: abcdef1/); // shortCommit applied

  const invalidTimeboxBody = payload.reviewIssueBodyLines({
    project: { name: "Proj", url: "http://x", lastCommit: "abcdef1234567", pushedAt: "2026-06-01", stars: 3, forks: 1, openIssues: 2, risks: 0, language: "JS" },
    decision: { status: "adopt", label: "score", score: 9, persistKey: "pk", reason: "solid" },
    secondary: null,
    scope: "all",
    timeboxHours: Infinity,
  });
  assert.doesNotMatch(invalidTimeboxBody, /Infinity/);
  assert.match(invalidTimeboxBody, /Timebox: 4 hours/);

  const invalidTracker = payload.reviewSavedResultTrackerFields({ result: { executionPlan: [{ owner: "PM", timeboxHours: Infinity }] } }, { estimate: 3 });
  assert.equal(invalidTracker.trackerReady, false);
  assert.equal(invalidTracker.estimate, 3);
  assert.equal(invalidTracker.due, "");
}

function testReviewCreationActionsFiniteEstimate() {
  const runtime = loadRuntime("review-creation-actions.js");
  const dashboard = { issues: [], notes: [] };
  let currentEstimate = "Infinity";
  let uidCount = 0;
  const handoff = { closest: () => null };
  const actions = runtime.JooParkReviewCreationActions.create({
    dashboard,
    reviewHandoffNode: () => handoff,
    issueBySourceKey: (key) => dashboard.issues.find((issue) => issue.sourceKey === key) || null,
    noteBySourceKey: () => null,
    openIssueInKanban: () => {},
    openNoteInNotesView: () => {},
    reviewIssueDraftNode: () => ({
      dataset: {
        issueDraftTitle: "Review issue",
        issueDraftProject: "Project A",
        issueDraftPriority: "med",
        issueDraftEstimate: currentEstimate,
        issueDraftLabels: "review,benchmark",
      },
    }),
    projectByName: () => ({ id: "proj-a" }),
    nodeText: () => "body",
    reviewDraftWithSavedResult: (input) => input,
    issueExecutionChecklistItems: () => [],
    savedReviewResultByKey: () => null,
    reviewSavedResultNoteBody: () => "",
    uid: () => `issue-${uidCount += 1}`,
    nowISO: () => "2026-06-10T00:00:00.000Z",
    rebuildIndexes: () => {},
    commit: () => {},
    showToast: () => {},
  });

  function createIssue(key, estimate) {
    currentEstimate = estimate;
    actions.createBenchmarkReviewIssue({ dataset: { reviewIssueKey: key } });
    return dashboard.issues.find((issue) => issue.sourceKey === key);
  }

  assert.equal(createIssue("review:infinity", "Infinity").estimate, 4);
  assert.equal(createIssue("review:huge", "5000").estimate, 999);
  assert.equal(createIssue("review:valid", "2.5").estimate, 2.5);
  assert.equal(dashboard.issues.every((issue) => Number.isFinite(issue.estimate)), true);
}

function testReviewResultStateHelpers() {
  const runtime = loadRuntime("review-result-state.js");
  const factory = runtime.JooParkReviewResultState;
  const noop = () => {};
  const deps = {
    nodeQuery: noop,
    nodeText: noop,
    setHTML: noop,
    copyTextWithStatus: noop,
    nowISO: () => "2026-06-09T00:00:00.000Z",
    clampText: (value) => value,
    clampTextArray: (value) => value,
    normalizeAllData: noop,
    persist: noop,
    renderSavedReviewResult: noop,
    refreshReviewIssueDraftFromSavedResult: noop,
    repairReceiptMarkdown: () => "md",
    validationOutputHTML: () => "",
  };

  // All DOM/persistence deps are required.
  assert.throws(() => factory.create({ nodeQuery: noop }), /review result state helper requires/);

  const state = factory.create(deps);
  const validator = { dataset: { reviewResultPrimaryKey: "pk-1", reviewResultType: "compare" } };

  // No snapshot recorded yet → no repair receipt model.
  assert.equal(state.postRepairReceiptModel(validator, {}, [], {}), null);

  // A "fail" snapshot is captured with normalized failure/warning arrays.
  state.recordRepairSnapshot(validator, "fail", "boom", { failures: ["F1"], warnings: ["W1"] });
  const model = state.postRepairReceiptModel(validator, { ok: true }, ["W1"], { key: "pk-1" });
  assert.equal(model.previous.message, "boom");
  assert.equal(model.previous.failures.join("|"), "F1");
  assert.equal(model.expectedKey, "pk-1");
  assert.equal(model.reviewType, "compare");
  assert.equal(model.repairedAt, "2026-06-09T00:00:00.000Z");

  // "empty" clears the snapshot.
  state.recordRepairSnapshot(validator, "empty");
  assert.equal(state.postRepairReceiptModel(validator, {}, [], {}), null);

  // Non-fail/non-empty states are no-ops (no snapshot stored).
  state.recordRepairSnapshot(validator, "pass", "ok", {});
  assert.equal(state.postRepairReceiptModel(validator, {}, [], {}), null);
}

function scriptArrayStrings(relPath, constName) {
  const source = readFileSync(join(root, relPath), "utf8");
  const pattern = new RegExp(`const\\s+${constName}\\s*=\\s*\\[([\\s\\S]*?)\\];`);
  const match = source.match(pattern);
  assert.ok(match, `${relPath} missing ${constName}`);
  return [...match[1].matchAll(/"([^"]+)"/g)].map((item) => item[1]);
}

function scriptSetStrings(relPath, constName) {
  const source = readFileSync(join(root, relPath), "utf8");
  const pattern = new RegExp(`const\\s+${constName}\\s*=\\s*new Set\\(\\[([\\s\\S]*?)\\]\\);`);
  const match = source.match(pattern);
  assert.ok(match, `${relPath} missing ${constName}`);
  return [...match[1].matchAll(/"([^"]+)"/g)].map((item) => item[1]);
}

function scriptFunctionSource(relPath, functionName) {
  const source = readFileSync(join(root, relPath), "utf8");
  const marker = `function ${functionName}(`;
  const start = source.indexOf(marker);
  assert.notEqual(start, -1, `${relPath} missing ${functionName}`);
  const paramsStart = source.indexOf("(", start);
  assert.notEqual(paramsStart, -1, `${relPath} missing ${functionName} params`);
  let paramsDepth = 0;
  let paramsEnd = -1;
  for (let index = paramsStart; index < source.length; index += 1) {
    if (source[index] === "(") paramsDepth += 1;
    else if (source[index] === ")") paramsDepth -= 1;
    if (paramsDepth === 0) {
      paramsEnd = index;
      break;
    }
  }
  assert.notEqual(paramsEnd, -1, `${relPath} ${functionName} params did not close`);
  const bodyStart = source.indexOf("{", paramsEnd);
  assert.notEqual(bodyStart, -1, `${relPath} missing ${functionName} body`);
  let depth = 0;
  for (let index = bodyStart; index < source.length; index += 1) {
    if (source[index] === "{") depth += 1;
    else if (source[index] === "}") depth -= 1;
    if (depth === 0) return source.slice(start, index + 1);
  }
  assert.fail(`${relPath} ${functionName} body did not close`);
}

function scriptFunction(relPath, functionName) {
  return vm.runInNewContext(`${scriptFunctionSource(relPath, functionName)}; ${functionName};`);
}

function packagedBrowserContextFiles({ relPath, runtimeConst, scriptsConst, excludeConst }) {
  const excluded = new Set(scriptSetStrings(relPath, excludeConst));
  return [...new Set([
    ...scriptArrayStrings(relPath, runtimeConst),
    ...scriptArrayStrings(relPath, scriptsConst),
    "package.json",
    "scripts/audit-release-readiness.mjs",
  ])]
    .filter((file) => !excluded.has(file))
    .sort();
}

function testPackagedBrowserGateContextParity() {
  const smokeReleaseFiles = packagedBrowserContextFiles({
    relPath: "scripts/smoke-release.mjs",
    runtimeConst: "packagedBrowserGateRuntimeFiles",
    scriptsConst: "packagedBrowserGateReleaseScripts",
    excludeConst: "packagedBrowserGateContextExcludedFiles",
  });
  const auditFiles = packagedBrowserContextFiles({
    relPath: "scripts/audit-release-readiness.mjs",
    runtimeConst: "runtimeFiles",
    scriptsConst: "releaseScripts",
    excludeConst: "packagedBrowserGateContextExcludedFiles",
  });
  assert.deepEqual(smokeReleaseFiles, auditFiles);
}

function testLlmWikiSmokeReadinessGuards() {
  const source = readFileSync(join(root, "scripts/smoke-llm-wiki.mjs"), "utf8");
  assert.match(source, /function assertAppServerReady/);
  assert.match(source, /LLM wiki smoke target is not reachable/);
  assert.match(source, /const routeReady = await evalRetry/);
  assert.match(source, /LLM wiki route did not become ready/);
  assert.match(source, /LLM wiki view container not found/);
}

function testDesktopSmokeNavigationLoadGuard() {
  const source = readFileSync(join(root, "scripts/smoke-chrome.mjs"), "utf8");
  assert.match(source, /async function waitForDocumentComplete/);
  assert.match(source, /lastState\?\.href === url && lastState\.readyState !== "loading"/);
  assert.match(source, /const isReady = document\.readyState !== "loading" &&/);
  assert.match(source, /async function navigateAndWaitForLoad/);
  assert.match(source, /Navigation failed for \$\{url\}/);
  assert.match(source, /await navigateAndWaitForLoad\(pageClient, url\)/);
}

function testProductSmokeUsesLock() {
  const source = readFileSync(join(root, "scripts/verify-product-smoke.mjs"), "utf8");
  assert.match(source, /import \{ withProductSmokeLock \} from "\.\/product-smoke-lock\.mjs"/);
  assert.match(source, /withProductSmokeLock\(\{ root, label: "verify:product", progress \}, main\)/);
}

function testProductSmokeLockHeartbeatStaleness() {
  const source = readFileSync(join(root, "scripts/product-smoke-lock.mjs"), "utf8");
  const productSmokeLockHeartbeatMs = scriptFunction("scripts/product-smoke-lock.mjs", "productSmokeLockHeartbeatMs");
  const staleDirMs = Date.now() - 120000;
  const freshOwnerMs = Date.now() - 1000;
  assert.equal(productSmokeLockHeartbeatMs({ heartbeatAt: new Date(freshOwnerMs).toISOString() }, 0, staleDirMs), freshOwnerMs);
  assert.equal(productSmokeLockHeartbeatMs({ acquiredAt: new Date(freshOwnerMs).toISOString() }, 0, staleDirMs), freshOwnerMs);
  assert.equal(productSmokeLockHeartbeatMs({}, freshOwnerMs, staleDirMs), freshOwnerMs);
  assert.equal(productSmokeLockHeartbeatMs({}, 0, staleDirMs), staleDirMs);
  assert.match(source, /const heartbeatMs = productSmokeLockHeartbeatMs\(owner, ownerStatMs, lockStatMs\)/);
  assert.match(source, /return heartbeatMs <= 0 \|\| Date\.now\(\) - heartbeatMs > staleMs/);
  assert.equal(source.includes("Date.now() - statSync(lockDir).mtimeMs > staleMs"), false);
}

function testProductSmokePortOptionFallbacks() {
  for (const relPath of ["scripts/verify-product-smoke.mjs", "scripts/smoke-release.mjs"]) {
    const source = readFileSync(join(root, relPath), "utf8");
    const portOption = scriptFunction(relPath, "portOption");
    assert.equal(portOption("5178", 0), 5178);
    assert.equal(portOption(0, 9999), 0);
    assert.equal(portOption("bad", 0), 0);
    assert.equal(portOption("Infinity", 0), 0);
    assert.equal(portOption("-1", 0), 0);
    assert.equal(portOption("65536", 0), 0);
    assert.equal(portOption("123.5", 0), 0);
    assert.match(source, /const requestedPort = portOption\(process\.env\.[A-Z_]+ \|\| process\.env\.PORT, 0\)/);
  }
}

function testAuditReleaseSmokeLockWaitDoesNotConsumeAttemptBudget() {
  const source = readFileSync(join(root, "scripts/audit-release-readiness.mjs"), "utf8");
  assert.match(source, /const smokeReleaseChildLockWaitMs = positiveMsOption\(/);
  assert.match(source, /const smokeReleaseChildLockPollMs = positiveMsOption\(/);
  assert.match(source, /process\.env\.JOOPARK_AUDIT_PRODUCT_SMOKE_CHILD_LOCK_WAIT_MS/);
  assert.match(source, /process\.env\.JOOPARK_AUDIT_PRODUCT_SMOKE_CHILD_LOCK_POLL_MS/);
  assert.match(source, /Math\.min\(60 \* 1000, Math\.max\(250, Math\.floor\(smokeReleaseAttemptTimeoutMs \/ 6\)\)\)/);
  assert.match(source, /Math\.min\(1000, Math\.max\(50, Math\.floor\(smokeReleaseChildLockWaitMs \/ 4\)\)\)/);
  assert.match(source, /PRODUCT_SMOKE_LOCK_WAIT_MS: String\(smokeReleaseChildLockWaitMs\)/);
  assert.match(source, /PRODUCT_SMOKE_LOCK_POLL_MS: String\(smokeReleaseChildLockPollMs\)/);
  assert.match(source, /function parseJsonFromOutputText\(text\)/);
  assert.match(source, /const firstBrace = value\.indexOf\("\{"\)/);
  assert.match(source, /const lastBrace = value\.lastIndexOf\("\}"\)/);
  assert.match(source, /const payload = parseJsonFromOutputText\(output\)/);
  assert.equal(source.includes("env: { RELEASE_OUT_DIR: releaseOutDir }"), false);
}

function testAuditIncompletePackagedGateDoesNotCascadeBrowserSubchecks() {
  const source = readFileSync(join(root, "scripts/audit-release-readiness.mjs"), "utf8");
  assert.match(source, /const releaseHeaderGateOk = !gateEvidence \|\| !gateEvidence\.result\?\.headers \|\| gateEvidence\.result\.headers\.status === "pass"/);
  assert.match(source, /const releaseFallbackGateOk = !gateEvidence \|\| !gateEvidence\.result\?\.fallbacks \|\| gateEvidence\.result\.fallbacks\.status === "pass"/);
  assert.match(source, /const desktopOverflowGateOk = !gateEvidence \|\| !gateEvidence\.result\?\.smoke \|\| \(/);
  assert.equal(source.includes("const releaseHeaderGateOk = !gateEvidence || gateEvidence.result?.headers?.status === \"pass\""), false);
  assert.equal(source.includes("const releaseFallbackGateOk = !gateEvidence || gateEvidence.result?.fallbacks?.status === \"pass\""), false);
}

function completePackagedGateEvidenceFixture() {
  return {
    status: "pass",
    command: "node scripts/smoke-release.mjs",
    cache: {
      source: "autoresearch-results/release-readiness-gates.json",
      generatedAt: "2026-06-10T00:00:00.000Z",
      maxAgeHours: 6,
      inputFiles: 89,
      written: true,
    },
    result: {
      status: "pass",
      package: { status: "pass" },
      verify: { status: "pass" },
      headers: { status: "pass" },
      fallbacks: { status: "pass" },
      routeParity: { status: "pass" },
      smoke: { status: "pass" },
      mobile: {
        status: "pass",
        searchEmpty: {
          status: "pass",
          expectedRouteCount: 13,
          expectedRoutes: ["llm-wiki"],
          issueCount: 0,
        },
        uiSurfaces: {
          palette: "pass",
          projectPicker: "pass",
          notificationSheet: "pass",
          sheetActions: "pass",
          modalTouch: "pass",
        },
      },
      interactions: {
        status: "pass",
        persistedChecks: {
          homeExecutionViewModule: true,
          homeExecutionQueue: true,
          homeExecutionQueueExplainability: true,
          homeExecutionQueueBuckets: true,
          homeExecutionQueueBucketFilter: true,
          homeExecutionQueueFilterSummary: true,
          homeExecutionQueueFilterComposition: true,
          homeExecutionQueueFilterWindow: true,
          homeExecutionQueueFilterRankWindow: true,
          homeExecutionQueueScoreWindow: true,
          homeExecutionQueueScoreDriver: true,
          homeExecutionQueueLeadDriver: true,
          homeExecutionQueueLeadDriverCount: true,
          homeExecutionQueueLeadDriverTie: true,
          homeExecutionQueueReceiptCompact: true,
          homeExecutionQueueReceiptDetail: true,
          homeExecutionQueueReceiptDescription: true,
          homeExecutionQueueQuickActions: true,
          homeExecutionQueueQuickUndo: true,
          homeReleaseGateEvidence: true,
          releaseGateEvidence: true,
          releaseGateEvidenceHandoff: true,
        },
      },
      deleteUndo: {
        status: "pass",
        checkedTypes: ["event", "todo", "note", "habit", "issue", "task", "query", "migration"],
        persisted: true,
      },
      accessibility: { status: "pass" },
    },
  };
}

function cloneJson(value) {
  return JSON.parse(JSON.stringify(value));
}

function testReleaseReadinessSummaryPrefersFreshGateEvidenceCache() {
  const source = readFileSync(join(root, "scripts/audit-release-readiness.mjs"), "utf8");
  const releaseReadinessSummaryFreshGateCache = vm.runInNewContext([
    scriptFunctionSource("scripts/audit-release-readiness.mjs", "completePackagedBrowserGateEvidence"),
    scriptFunctionSource("scripts/audit-release-readiness.mjs", "releaseReadinessSummaryFreshGateCache"),
    "releaseReadinessSummaryFreshGateCache;",
  ].join("\n"));
  const completeEvidence = completePackagedGateEvidenceFixture();
  const cache = releaseReadinessSummaryFreshGateCache({ evidence: completeEvidence });
  assert.equal(cache.status, "valid");
  assert.equal(cache.contextMatched, true);
  assert.equal(cache.cachedEvidenceStatus, "pass");
  assert.equal(cache.cachedResultStatus, "pass");
  assert.equal(cache.issues.length, 0);
  assert.equal(cache.contextMismatches.length, 0);
  assert.equal(cache.inputFiles, 89);
  const unwrittenEvidence = cloneJson(completeEvidence);
  unwrittenEvidence.cache.written = false;
  assert.equal(releaseReadinessSummaryFreshGateCache({ evidence: unwrittenEvidence }), null);
  const incompleteEvidence = cloneJson(completeEvidence);
  incompleteEvidence.result.accessibility.status = "fail";
  assert.equal(releaseReadinessSummaryFreshGateCache({ evidence: incompleteEvidence }), null);
  assert.match(source, /function releaseReadinessSummaryFreshGateCache\(gate\)/);
  assert.match(source, /cache\.written !== true/);
  assert.match(source, /completePackagedBrowserGateEvidence\(evidence\)/);
  assert.match(source, /const freshGateCache = releaseReadinessSummaryFreshGateCache\(gate\)/);
  assert.match(source, /if \(freshGateCache\) return freshGateCache/);
}

function testReleaseLockTimeoutFallbacks() {
  const contracts = [
    {
      relPath: "scripts/package-release.mjs",
      patterns: [
        /const packageLockTimeoutMs = positiveMsOption\(process\.env\.RELEASE_PACKAGE_LOCK_TIMEOUT_MS, 60000\)/,
        /const packageLockStaleMs = positiveMsOption\(process\.env\.RELEASE_PACKAGE_LOCK_STALE_MS, 10 \* 60 \* 1000\)/,
        /function readPackageLockOwner\(path\)/,
        /function packageLockOwnerProcess\(owner\)/,
        /if \(ownerProcess\.alive && ownerProcess\.commandMatches\) return false/,
      ],
    },
    {
      relPath: "scripts/verify-release.mjs",
      patterns: [
        /const packageLockTimeoutMs = positiveMsOption\(process\.env\.RELEASE_PACKAGE_LOCK_TIMEOUT_MS, 60000\)/,
        /const packageLockOwnerGraceMs = Math\.min\(packageLockTimeoutMs, 1000\)/,
        /function readPackageLockOwner\(path\)/,
        /function packageLockOwnerProcess\(owner\)/,
        /throw releasePackageLockError\(ownerProcess\)/,
      ],
    },
    {
      relPath: "scripts/audit-release-readiness.mjs",
      patterns: [
        /const auditGateLockTimeoutMs = positiveMsOption\(process\.env\.RELEASE_AUDIT_LOCK_TIMEOUT_MS, 10 \* 60 \* 1000\)/,
        /const auditGateLockStaleMs = positiveMsOption\(process\.env\.RELEASE_AUDIT_LOCK_STALE_MS, 30 \* 60 \* 1000\)/,
        /if \(ownerProcess\.alive && ownerProcess\.commandMatches\) return false/,
      ],
    },
  ];

  for (const contract of contracts) {
    const source = readFileSync(join(root, contract.relPath), "utf8");
    const positiveMsOption = scriptFunction(contract.relPath, "positiveMsOption");
    assert.equal(positiveMsOption("1500", 60000), 1500);
    assert.equal(positiveMsOption("bad", 60000), 60000);
    assert.equal(positiveMsOption("Infinity", 60000), 60000);
    assert.equal(positiveMsOption("-1", 60000), 60000);
    assert.equal(positiveMsOption("0", 60000), 60000);
    for (const pattern of contract.patterns) assert.match(source, pattern);
  }
  const packageLockOwnerProcess = scriptFunction("scripts/package-release.mjs", "packageLockOwnerProcess");
  const invalidPackageOwner = packageLockOwnerProcess({ pid: "bad" });
  assert.equal(invalidPackageOwner.alive, false);
  assert.equal(invalidPackageOwner.commandMatches, false);
  assert.equal(invalidPackageOwner.reason, "invalid_owner_pid");
  const packageReleaseSource = readFileSync(join(root, "scripts/package-release.mjs"), "utf8");
  assert.equal(packageReleaseSource.includes("Date.now() - statSync(path).mtimeMs > packageLockStaleMs"), false);
  const verifyReleaseOwnerProcess = scriptFunction("scripts/verify-release.mjs", "packageLockOwnerProcess");
  const invalidVerifyOwner = verifyReleaseOwnerProcess({ pid: "bad" });
  assert.equal(invalidVerifyOwner.alive, false);
  assert.equal(invalidVerifyOwner.commandMatches, false);
  assert.equal(invalidVerifyOwner.reason, "invalid_owner_pid");
}

function testReleaseReadinessFormatOption() {
  const source = readFileSync(join(root, "scripts/audit-release-readiness.mjs"), "utf8");
  const formatOption = scriptFunction("scripts/audit-release-readiness.mjs", "formatOption");
  assert.equal(formatOption(["--format=summary"]), "summary");
  assert.equal(formatOption(["--format", "summary"]), "summary");
  assert.equal(formatOption(["--summary"]), "summary");
  assert.equal(formatOption(["--format=markdown"]), "markdown");
  assert.equal(formatOption(["--format", "markdown"]), "markdown");
  assert.equal(formatOption(["--markdown"]), "markdown");
  assert.equal(formatOption(["--format=json-pretty"]), "json-pretty");
  assert.equal(formatOption(["--format", "json-pretty"]), "json-pretty");
  assert.equal(formatOption(["--pretty"]), "json-pretty");
  assert.equal(formatOption(["--format", "json"]), "json");
  assert.equal(formatOption(["--format", "--run-gates"]), "json");
  assert.equal(formatOption(["--format", "--summary"]), "summary");
  assert.equal(formatOption(["--format", "--markdown"]), "markdown");
  assert.equal(formatOption(["--format", "--pretty"]), "json-pretty");
  assert.match(source, /const rawArgs = process\.argv\.slice\(2\)/);
  assert.match(source, /const format = formatOption\(rawArgs\)/);
  assert.match(source, /nextValue\.startsWith\("--"\) \? "" : nextValue/);
}

function testRemoteWorkflowFileCheckFallbackAuditGuard() {
  const source = readFileSync(join(root, "scripts/audit-release-readiness.mjs"), "utf8");
  const fallbackReady = scriptFunction("scripts/audit-release-readiness.mjs", "remoteWorkflowFileCheckFallbackReady");
  assert.equal(fallbackReady("If browser approval cannot be completed, use each workflow row's installAction to choose the GitHub create or edit page before rerunning verification."), true);
  assert.equal(fallbackReady("If browser approval cannot be completed, use each workflow row's installAction: open GitHub edit-file pages for existing mismatched files; do not use new-file links for replace_existing_remote_file rows."), true);
  assert.equal(fallbackReady("GitHub UI new-file links"), false);
  assert.equal(fallbackReady(""), true);
  assert.match(source, /function remoteWorkflowFileCheckFallbackReady\(fallback\)/);
  assert.match(source, /remoteWorkflowFileCheckFallbackReady\(approvalHandoff\.fallback\)/);
}

function testLaunchReadinessOptionValueGuard() {
  const source = readFileSync(join(root, "scripts/refresh-launch-readiness.mjs"), "utf8");
  const optionValue = scriptFunction("scripts/refresh-launch-readiness.mjs", "optionValue");
  const finiteNumberOr = scriptFunction("scripts/refresh-launch-readiness.mjs", "finiteNumberOr");
  const markdownLines = vm.runInNewContext([
    scriptFunctionSource("scripts/refresh-launch-readiness.mjs", "yesNo"),
    scriptFunctionSource("scripts/refresh-launch-readiness.mjs", "finiteNumberOr"),
    scriptFunctionSource("scripts/refresh-launch-readiness.mjs", "markdownLines"),
    "markdownLines;",
  ].join("\n"));
  assert.equal(optionValue(["--repo=biojuho/BIOJUHO-Projects"], "--repo"), "biojuho/BIOJUHO-Projects");
  assert.equal(optionValue(["--repo", "biojuho/BIOJUHO-Projects", "--write"], "--repo"), "biojuho/BIOJUHO-Projects");
  assert.equal(optionValue(["--repo", "--write"], "--repo"), "");
  assert.equal(optionValue(["--out-json", "--write"], "--out-json"), "");
  assert.equal(finiteNumberOr(0, 7), 0);
  assert.equal(finiteNumberOr("0", 7), 0);
  assert.equal(finiteNumberOr("", 7), 7);
  const markdown = markdownLines({
    status: "pass",
    repo: "biojuho/BIOJUHO-Projects",
    generatedAt: "2026-06-10T00:00:00.000Z",
    evidenceFreshnessStatus: "fresh",
    evidenceExpiresAt: "2026-06-11T00:00:00.000Z",
    evidenceFreshness: { refreshRequired: false, sourceArtifactCount: 0 },
    commandCoverage: 6,
    decision: "keep_b",
    abComparison: {
      baseline: "manual_multi_command_refresh",
      baselineCommandCount: 6,
      candidate: "single_launch_readiness_refresh_runner",
      candidateCommandCount: 1,
      decision: "keep_b",
    },
    sourceArtifactSync: { status: "pass" },
    outputQualityGeneratedAt: "",
    outputQualitySourceInputCount: 0,
    latestGate: {},
    latestGateSummary: "",
    workflowScopeAvailable: false,
    workflowScopeInstallBlocked: false,
    remoteWorkflowFilesReady: false,
    remoteWorkflowVisibilityReady: true,
    allDispatchReady: false,
    safeToDispatch: false,
    readyForExternalClaim: false,
    dispatchCommandDisposition: "withheld",
    activeDispatchCommandCount: 0,
    dispatchCommandReferenceCount: 0,
    suggestedDispatchCommandCount: 9,
    guard: "guard",
    outputQualityGateTraceability: {},
    refreshChecklist: [],
    remoteWorkflowRepairAction: {},
    commandRuns: [],
    nextAction: { key: "install_workflows", status: "action_required", detail: "install workflows", command: "" },
    blockers: [],
  }).join("\n");
  assert.match(markdown, /activeDispatchCommandCount: 0/);
  assert.match(markdown, /dispatchCommandReferenceCount: 0/);
  assert.doesNotMatch(markdown, /dispatchCommandReferenceCount: 9/);
  assert.match(source, /function optionValue\(argsList, name\)/);
  assert.match(source, /return value\.startsWith\("--"\) \? "" : value/);
  assert.match(source, /function finiteNumberOr\(value, fallback = 0\)/);
  assert.equal(source.includes("dispatchCommandReferenceCount: ${data.dispatchCommandReferenceCount || data.suggestedDispatchCommandCount || 0}"), false);
}

function testOutputQualityOptionValueGuard() {
  const source = readFileSync(join(root, "scripts/capture-output-quality-audit.mjs"), "utf8");
  const optionValue = scriptFunction("scripts/capture-output-quality-audit.mjs", "optionValue");
  const finiteNumberOr = scriptFunction("scripts/capture-output-quality-audit.mjs", "finiteNumberOr");
  const countFromArrayOr = vm.runInNewContext([
    scriptFunctionSource("scripts/capture-output-quality-audit.mjs", "finiteNumberOr"),
    scriptFunctionSource("scripts/capture-output-quality-audit.mjs", "countFromArrayOr"),
    "countFromArrayOr;",
  ].join("\n"));
  assert.equal(optionValue(["--out=data/output-quality-audit.json"], "--out"), "data/output-quality-audit.json");
  assert.equal(optionValue(["--out", "tmp/output.json", "--write"], "--out"), "tmp/output.json");
  assert.equal(optionValue(["--out", "--write"], "--out"), "");
  assert.equal(optionValue(["--product-loop", "--markdown"], "--product-loop"), "");
  assert.equal(optionValue(["--release-gate-cache", "--write"], "--release-gate-cache"), "");
  assert.equal(optionValue(["--release-readiness-summary", "--markdown"], "--release-readiness-summary"), "");
  assert.equal(optionValue(["--previous-output-quality", "--write"], "--previous-output-quality"), "");
  assert.equal(optionValue(["--launch-handoff-verification", "--markdown"], "--launch-handoff-verification"), "");
  assert.equal(optionValue(["--main-bridge-plan", "--write"], "--main-bridge-plan"), "");
  assert.equal(finiteNumberOr(0, 7), 0);
  assert.equal(finiteNumberOr("", 7), 7);
  assert.equal(countFromArrayOr([], 9), 0);
  assert.equal(countFromArrayOr(["dispatch"], 9), 1);
  assert.equal(countFromArrayOr(null, "2"), 2);
  assert.match(source, /function optionValue\(argsList, name\)/);
  assert.match(source, /return value\.startsWith\("--"\) \? "" : value/);
  assert.match(source, /function countFromArrayOr\(value, fallback = 0\)/);
  assert.equal(source.includes("publishDispatchPlan?.suggestedDispatchCommands?.length || publishEvidence?.suggestedDispatchCommandCount || 0"), false);
  assert.equal(source.includes("publishEvidence?.withheldDispatchCommandCount || outputSnapshot?.publishEvidenceCommandGuard?.withheldDispatchCommands || 0"), false);
}

function testOutputQualityAcceptanceLedgerCountsPreserveExplicitZero() {
  const source = readFileSync(join(root, "scripts/capture-output-quality-audit.mjs"), "utf8");
  const remoteWorkflowFileAcceptanceLedgerSnapshot = vm.runInNewContext([
    scriptFunctionSource("scripts/capture-output-quality-audit.mjs", "finiteNumberOr"),
    scriptFunctionSource("scripts/capture-output-quality-audit.mjs", "remoteWorkflowFileAcceptanceLedgerSnapshot"),
    "remoteWorkflowFileAcceptanceLedgerSnapshot;",
  ].join("\n"));
  const launchProofAcceptanceLedgerSnapshot = vm.runInNewContext([
    scriptFunctionSource("scripts/capture-output-quality-audit.mjs", "finiteNumberOr"),
    scriptFunctionSource("scripts/capture-output-quality-audit.mjs", "launchProofAcceptanceLedgerSnapshot"),
    "launchProofAcceptanceLedgerSnapshot;",
  ].join("\n"));
  const explicitZeroRemote = remoteWorkflowFileAcceptanceLedgerSnapshot({
    remoteWorkflowFileAcceptanceLedger: {
      source: "generated_from_remote_workflow_file_check",
      status: "remote_file_install_required",
      fileCount: 0,
      readyCount: 0,
      missingCount: 0,
      mismatchCount: 0,
      notCheckedCount: 0,
      verifyCommand: "node scripts/check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write",
      files: [
        { key: "pages", status: "missing_on_default_branch" },
        { key: "drift-watch", status: "missing_on_default_branch" },
      ],
    },
  });
  assert.equal(explicitZeroRemote.ready, false);
  assert.equal(explicitZeroRemote.fileCount, 0);
  assert.equal(explicitZeroRemote.readyCount, 0);
  assert.equal(explicitZeroRemote.missingCount, 0);
  assert.equal(explicitZeroRemote.mismatchCount, 0);
  const derivedRemote = remoteWorkflowFileAcceptanceLedgerSnapshot({
    remoteWorkflowFileAcceptanceLedger: {
      source: "generated_from_remote_workflow_file_check",
      status: "remote_files_ready",
      readyCount: 2,
      missingCount: 0,
      mismatchCount: 0,
      files: [
        { key: "pages", remoteExists: true, remoteMatchesTemplate: true },
        { key: "drift-watch", remoteExists: true, remoteMatchesTemplate: true },
      ],
    },
  });
  assert.equal(derivedRemote.ready, true);
  assert.equal(derivedRemote.fileCount, 2);
  assert.equal(derivedRemote.readyCount, 2);
  const explicitZeroProof = launchProofAcceptanceLedgerSnapshot({
    launchProofAcceptanceLedger: {
      source: "generated_from_launch_execution_packet",
      status: "proof_blocked_until_dispatch",
      currentGate: "capture_launch_proof",
      requiredProofCount: 0,
      readyProofCount: 0,
      pendingProofCount: 0,
      captureWriteCommand: "node scripts/capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --write",
      requiredProofs: [
        { key: "pages_site_url", status: "blocked_until_dispatch" },
        { key: "pages_workflow_run", command: "gh workflow run joopark-pages.yml" },
        { key: "drift_workflow_run", command: "gh workflow run joopark-drift-watch.yml" },
        { key: "evidence_freshness" },
        { key: "release_receipt" },
        { key: "public_claim_guard", status: "guarded" },
      ],
    },
  });
  assert.equal(explicitZeroProof.ready, false);
  assert.equal(explicitZeroProof.requiredProofCount, 0);
  assert.equal(explicitZeroProof.readyProofCount, 0);
  assert.equal(explicitZeroProof.pendingProofCount, 0);
  const derivedProof = launchProofAcceptanceLedgerSnapshot({
    launchProofAcceptanceLedger: {
      source: "generated_from_launch_execution_packet",
      status: "proof_ready",
      currentGate: "capture_launch_proof",
      readyProofCount: 6,
      pendingProofCount: 0,
      captureWriteCommand: "node scripts/capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --write",
      requiredProofs: Array.from({ length: 6 }, (_, index) => ({ key: `proof_${index}`, status: "ready" })),
    },
  });
  assert.equal(derivedProof.ready, true);
  assert.equal(derivedProof.requiredProofCount, 6);
  assert.equal(derivedProof.readyProofCount, 6);
  assert.equal(derivedProof.pendingProofCount, 0);
  assert.match(source, /const fileCount = finiteNumberOr\(ledger\.fileCount, files\.length\)/);
  assert.match(source, /const requiredProofCount = finiteNumberOr\(ledger\.requiredProofCount, proofs\.length\)/);
  assert.equal(source.includes("Number(ledger.fileCount || files.length)"), false);
  assert.equal(source.includes("Number(ledger.requiredProofCount || proofs.length)"), false);
  assert.equal(source.includes("Number(ledger.pendingProofCount || 0)"), false);
}

function testOutputQualityWorkflowUiReceiptCountsPreserveExplicitZero() {
  const source = readFileSync(join(root, "scripts/capture-output-quality-audit.mjs"), "utf8");
  const workflowUiInstallReceiptSnapshot = vm.runInNewContext([
    scriptFunctionSource("scripts/capture-output-quality-audit.mjs", "finiteNumberOr"),
    scriptFunctionSource("scripts/capture-output-quality-audit.mjs", "workflowUiInstallReceiptSnapshot"),
    "workflowUiInstallReceiptSnapshot;",
  ].join("\n"));
  const receiptText = [
    "JooPark GitHub UI Workflow Install Receipt",
    "JooPark GitHub UI Workflow Paste Packet",
    "Paste exact template content",
    "Post-install evidence fields to fill:",
    "Parser-ready proof block:",
    "pages_workflow_commit:",
    "The parser ignores bracketed [paste ...] placeholders",
    "Handoff verifier proof",
    "dispatchReady=true",
    "driftDispatchReady=true",
    "safeToDispatch=true before gh workflow run",
    "every post-install evidence field has been filled",
    "verify-launch-handoff reports safeToDispatch=true",
  ].join("\n");
  const explicitZero = workflowUiInstallReceiptSnapshot({
    latestGate: {
      browserEvidence: {
        workflowUiInstallPastePacketCoverage: 1,
        workflowUiInstallReceiptCoverage: 1,
        workflowUiInstallReceiptCommandCount: 6,
        workflowUiInstallReceiptChecklistCount: 6,
      },
    },
    workflowUiInstallPlan: {
      workflowUiInstallPastePacketCoverage: 0,
      workflowUiInstallPastePacketReady: true,
      installReceipt: {
        ready: true,
        commandCount: 0,
        checklistCount: 0,
        expectedSignalCount: 0,
        text: receiptText,
      },
    },
  });
  assert.equal(explicitZero.ready, false);
  assert.equal(explicitZero.pastePacketCoverage, 0);
  assert.equal(explicitZero.commandCount, 0);
  assert.equal(explicitZero.checklistCount, 0);
  assert.equal(explicitZero.expectedSignalCount, 0);
  const readyReceipt = workflowUiInstallReceiptSnapshot({
    latestGate: { browserEvidence: {} },
    workflowUiInstallPlan: {
      workflowUiInstallPastePacketCoverage: 1,
      workflowUiInstallPastePacketReady: true,
      installReceipt: {
        ready: true,
        commandCount: 6,
        checklistCount: 6,
        expectedSignalCount: 8,
        text: receiptText,
      },
    },
  });
  assert.equal(readyReceipt.ready, true);
  assert.equal(readyReceipt.commandCount, 6);
  assert.equal(readyReceipt.checklistCount, 6);
  assert.equal(readyReceipt.expectedSignalCount, 8);
  assert.match(source, /const packetCoverage = finiteNumberOr\(/);
  assert.match(source, /const commandCount = finiteNumberOr\(receipt\.commandCount, evidence\.workflowUiInstallReceiptCommandCount\)/);
  assert.match(source, /const checklistCount = finiteNumberOr\(receipt\.checklistCount, evidence\.workflowUiInstallReceiptChecklistCount\)/);
  assert.match(source, /workflowUiInstallPastePacketCoverage: finiteNumberOr\(/);
  assert.equal(source.includes("workflowUiInstallPlan?.workflowUiInstallPastePacketCoverage || evidence.workflowUiInstallPastePacketCoverage"), false);
  assert.equal(source.includes("workflowUiInstallPlan?.workflowUiInstallPastePacketCoverage || latestGateCompact.browserEvidence.workflowUiInstallPastePacketCoverage"), false);
  assert.equal(source.includes("Number(receipt.commandCount || evidence.workflowUiInstallReceiptCommandCount || 0)"), false);
  assert.equal(source.includes("Number(receipt.checklistCount || evidence.workflowUiInstallReceiptChecklistCount || 0)"), false);
}

function testOutputQualityPostAuthCheckpointCountsPreserveExplicitZero() {
  const source = readFileSync(join(root, "scripts/capture-output-quality-audit.mjs"), "utf8");
  const launchPostAuthCheckpointSnapshot = vm.runInNewContext([
    scriptFunctionSource("scripts/capture-output-quality-audit.mjs", "finiteNumberOr"),
    scriptFunctionSource("scripts/capture-output-quality-audit.mjs", "launchPostAuthCheckpointSnapshot"),
    "launchPostAuthCheckpointSnapshot;",
  ].join("\n"));
  const requiredRecheckSequence = [
    { key: "confirm_scope" },
    { key: "install_workflows" },
    { key: "verify_remote_parity" },
    { key: "verify_actions_visibility" },
    { key: "verify_handoff_guard" },
  ];
  const requiredSourceArtifacts = [
    "gh auth status -h github.com",
    "data/remote-workflow-file-check.json",
    "data/publish-dispatch-plan.json",
    "data/launch-handoff-verification.json",
  ];
  const requiredExpectedSignals = [
    "Token scopes include workflow",
    "workflowScopeAvailable=true",
    "workflowScopeInstallBlocked=false",
    "remoteWorkflowFilesReady=true after installer or GitHub UI commit",
    "remoteWorkflowVisibilityReady=true before dispatch",
    "safeToDispatch=true before gh workflow run",
  ];
  const requiredBlockedSignals = [
    "workflowScopeInstallBlocked=true",
    "remoteWorkflowFilesReady=false",
    "remoteWorkflowVisibilityReady=false",
    "allDispatchReady=false",
  ];
  const baseCheckpoint = {
    key: "post_auth_checkpoint",
    status: "pass",
    authStatusCommand: "gh auth status -h github.com",
    verifyCommand: "node scripts/verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown",
    installCommand: "node scripts/install-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write --verify",
    verificationOnly: true,
    dispatchApproval: false,
    recheckSequence: requiredRecheckSequence,
    sourceArtifacts: requiredSourceArtifacts,
    expectedSignals: requiredExpectedSignals,
    blockedSignals: requiredBlockedSignals,
    guard: "Do not run gh workflow run until every action_required post-auth checkpoint item has passed and verify-launch-handoff reports safeToDispatch=true.",
  };
  const explicitZero = launchPostAuthCheckpointSnapshot({
    postAuthCheckpoint: {
      ...baseCheckpoint,
      commandCount: 0,
      recheckSequenceCount: 0,
      sourceArtifactCount: 0,
      expectedSignalCount: 0,
      blockedSignalCount: 0,
    },
  });
  assert.equal(explicitZero.commandCount, 0);
  assert.equal(explicitZero.recheckSequenceCount, 0);
  assert.equal(explicitZero.sourceArtifactCount, 0);
  assert.equal(explicitZero.expectedSignalCount, 0);
  assert.equal(explicitZero.blockedSignalCount, 0);
  const derivedCounts = launchPostAuthCheckpointSnapshot({
    postAuthCheckpoint: {
      ...baseCheckpoint,
      commandCount: 5,
    },
  });
  assert.equal(derivedCounts.ready, true);
  assert.equal(derivedCounts.commandCount, 5);
  assert.equal(derivedCounts.recheckSequenceCount, 5);
  assert.equal(derivedCounts.sourceArtifactCount, 4);
  assert.equal(derivedCounts.expectedSignalCount, 6);
  assert.equal(derivedCounts.blockedSignalCount, 4);
  assert.match(source, /const checkpointCommandCount = finiteNumberOr\(checkpoint\.commandCount, 0\)/);
  assert.match(source, /const checkpointRecheckSequenceCount = finiteNumberOr\(checkpoint\.recheckSequenceCount, recheckSequence\.length\)/);
  assert.match(source, /const checkpointSourceArtifactCount = finiteNumberOr\(checkpoint\.sourceArtifactCount, sourceArtifacts\.length\)/);
  assert.match(source, /const checkpointExpectedSignalCount = finiteNumberOr\(checkpoint\.expectedSignalCount, expectedSignals\.length\)/);
  assert.match(source, /const checkpointBlockedSignalCount = finiteNumberOr\(checkpoint\.blockedSignalCount, blockedSignals\.length\)/);
  assert.equal(source.includes("commandCount: Number(checkpoint.commandCount || 0)"), false);
  assert.equal(source.includes("recheckSequenceCount: recheckSequence.length"), false);
  assert.equal(source.includes("sourceArtifactCount: sourceArtifacts.length"), false);
  assert.equal(source.includes("expectedSignalCount: expectedSignals.length"), false);
  assert.equal(source.includes("blockedSignalCount: blockedSignals.length"), false);
}

function testOutputQualityReleaseGateBrowserEvidenceCountsPreserveExplicitZero() {
  const source = readFileSync(join(root, "scripts/capture-output-quality-audit.mjs"), "utf8");
  const releaseGateBrowserEvidence = vm.runInNewContext([
    scriptFunctionSource("scripts/capture-output-quality-audit.mjs", "finiteNumberOr"),
    scriptFunctionSource("scripts/capture-output-quality-audit.mjs", "countIssues"),
    "function reviewCommentNoteDecisionSummarySourceReady() { return false; }",
    "function reviewResultRepairActionPlanSourceReady() { return false; }",
    "function reviewPackageSubmissionCloseoutSummarySourceReady() { return false; }",
    "function postInstallEvidenceIntakeSourceReady() { return false; }",
    "function launchProofEvidenceReceiptSourceReady() { return false; }",
    "function outputQualityExternalClaimGuardSourceReady() { return false; }",
    "function homeFirstRunGuidedStartSourceReady() { return false; }",
    "function globalHelpAccessSourceReady() { return false; }",
    "function topbarDataSafetySourceReady() { return false; }",
    "function routeDeepLinkSourceReady() { return false; }",
    "function postInstallProofParserSourceReady() { return false; }",
    "function launchPacketReadyForExternalClaim() { return false; }",
    scriptFunctionSource("scripts/capture-output-quality-audit.mjs", "releaseGateBrowserEvidence"),
    "releaseGateBrowserEvidence;",
  ].join("\n"));
  const explicitZero = releaseGateBrowserEvidence(
    {
      evidence: {
        result: {
          interactions: {
            persistedChecks: {
              workflowUiInstallReceiptCopy: true,
              workflowUiInstallReceiptCoverage: 0,
              workflowUiInstallReceiptCommandCount: 6,
              workflowUiInstallReceiptChecklistCount: 6,
              postInstallProofParser: true,
              postInstallProofParserFields: 0,
              postInstallProofParserCoverage: 0,
              postInstallProofParserDetectedFields: 0,
              publishDispatchAuthPreflight: true,
              systemStatusWorkflowAuthPreflightFields: 0,
              outputQualityAuditReceipt: true,
              outputQualityExternalComparisonSources: 0,
              reviewPackageArtifactQualityRubricVisible: true,
              reviewPackageArtifactQualityItems: 0,
              reviewPackageDecisionBriefVisible: true,
              reviewPackageDecisionBriefFields: 0,
              reviewPackageDecisionBriefCoverage: 0,
              reviewIssueDecisionSummaryVisible: true,
              reviewIssueDecisionSummaryFields: 0,
              reviewIssueDecisionSummaryCoverage: 0,
              reviewCommentNoteDecisionSummaryVisible: true,
              reviewCommentNoteDecisionSummaryFields: 0,
              reviewCommentNoteDecisionSummaryCoverage: 0,
              reviewResultRepairActionPlanVisible: true,
              reviewResultRepairActionPlanFields: 0,
              reviewResultRepairActionPlanCoverage: 0,
              reviewPackageSubmissionCloseoutSummaryVisible: true,
              reviewPackageSubmissionCloseoutSummaryFields: 0,
              reviewPackageSubmissionCloseoutSummaryCoverage: 0,
              reviewPackageOperatorQuickStartVisible: true,
              reviewPackageOperatorQuickStartSteps: 0,
              reviewPackageOperatorQuickStartCoverage: 0,
              reviewPackageTrackerFormCopy: true,
              reviewPackageExternalReceiptIntegrity: true,
              reviewPackageFinalQualityGateVisible: true,
              reviewPackageTrackerFormPayloadCount: 0,
              reviewPackageTrackerFormPayloadCoverage: 0,
            },
          },
          verify: { status: "pass", sourceParityFiles: 38 },
          smoke: {},
          mobile: {},
        },
      },
    },
    {
      launchProofEvidenceReceipt: "JooPark Launch Proof Evidence Receipt",
      launchProofEvidenceFieldCount: 0,
      launchProofEvidenceFieldCoverage: 0,
      launchProofEvidenceFields: Array.from({ length: 6 }, (_, index) => ({ key: `proof_${index}` })),
    },
    {
      packet: true,
      stageCount: 0,
      commandCount: 0,
      externalComparisonSourceCount: 0,
      externalComparison: [{ key: "github_actions" }, { key: "github_pages" }],
      postAuthCheckpoint: {
        coverage: 0,
        commandCount: 0,
        expectedSignalCount: 0,
        recheckSequenceCount: 0,
        sourceArtifactCount: 0,
        expectedSignals: Array.from({ length: 6 }, (_, index) => `signal_${index}`),
        recheckSequence: Array.from({ length: 5 }, (_, index) => ({ key: `step_${index}` })),
        sourceArtifacts: Array.from({ length: 4 }, (_, index) => `artifact_${index}`),
      },
      postInstallEvidenceIntake: {
        ready: true,
        fieldCount: 0,
        fieldCoverage: 0,
        fields: Array.from({ length: 6 }, (_, index) => ({ key: `field_${index}` })),
      },
    },
    { installReceipt: { ready: true, coverage: 0, commandCount: 0, checklistCount: 0 } },
  );
  assert.equal(explicitZero.workflowUiInstallReceiptCoverage, 0);
  assert.equal(explicitZero.workflowUiInstallReceiptCommandCount, 0);
  assert.equal(explicitZero.workflowUiInstallReceiptChecklistCount, 0);
  assert.equal(explicitZero.postInstallProofParser, true);
  assert.equal(explicitZero.postInstallProofParserFields, 0);
  assert.equal(explicitZero.postInstallProofParserCoverage, 0);
  assert.equal(explicitZero.postInstallProofParserDetectedFields, 0);
  assert.equal(explicitZero.publishDispatchAuthPreflight, true);
  assert.equal(explicitZero.systemStatusWorkflowAuthPreflightFields, 0);
  assert.equal(explicitZero.launchExecutionPacket, true);
  assert.equal(explicitZero.launchExecutionPacketStages, 0);
  assert.equal(explicitZero.launchExecutionPacketCommands, 0);
  assert.equal(explicitZero.launchExecutionPacketExternalComparisonSources, 0);
  assert.equal(explicitZero.launchPostAuthCheckpointCoverage, 0);
  assert.equal(explicitZero.launchPostAuthCheckpointCommandCount, 0);
  assert.equal(explicitZero.launchPostAuthCheckpointExpectedSignals, 0);
  assert.equal(explicitZero.launchPostAuthCheckpointRecheckCount, 0);
  assert.equal(explicitZero.launchPostAuthCheckpointSourceArtifactCount, 0);
  assert.equal(explicitZero.postInstallEvidenceIntake, true);
  assert.equal(explicitZero.postInstallEvidenceIntakeFields, 0);
  assert.equal(explicitZero.postInstallEvidenceIntakeFieldCoverage, 0);
  assert.equal(explicitZero.launchProofEvidenceReceipt, true);
  assert.equal(explicitZero.launchProofEvidenceFields, 0);
  assert.equal(explicitZero.launchProofEvidenceFieldCoverage, 0);
  assert.equal(explicitZero.outputQualityExternalComparison, true);
  assert.equal(explicitZero.outputQualityExternalComparisonSources, 0);
  assert.equal(explicitZero.reviewPackageArtifactQualityRubric, true);
  assert.equal(explicitZero.reviewPackageArtifactQualityItems, 0);
  assert.equal(explicitZero.reviewPackageDecisionBrief, true);
  assert.equal(explicitZero.reviewPackageDecisionBriefFields, 0);
  assert.equal(explicitZero.reviewPackageDecisionBriefCoverage, 0);
  assert.equal(explicitZero.reviewIssueDecisionSummary, true);
  assert.equal(explicitZero.reviewIssueDecisionSummaryFields, 0);
  assert.equal(explicitZero.reviewIssueDecisionSummaryCoverage, 0);
  assert.equal(explicitZero.reviewCommentNoteDecisionSummary, true);
  assert.equal(explicitZero.reviewCommentNoteDecisionSummaryFields, 0);
  assert.equal(explicitZero.reviewCommentNoteDecisionSummaryCoverage, 0);
  assert.equal(explicitZero.reviewResultRepairActionPlan, true);
  assert.equal(explicitZero.reviewResultRepairActionPlanFields, 0);
  assert.equal(explicitZero.reviewResultRepairActionPlanCoverage, 0);
  assert.equal(explicitZero.reviewPackageSubmissionCloseoutSummary, true);
  assert.equal(explicitZero.reviewPackageSubmissionCloseoutSummaryFields, 0);
  assert.equal(explicitZero.reviewPackageSubmissionCloseoutSummaryCoverage, 0);
  assert.equal(explicitZero.reviewPackageOperatorQuickStart, true);
  assert.equal(explicitZero.reviewPackageOperatorQuickStartSteps, 0);
  assert.equal(explicitZero.reviewPackageOperatorQuickStartCoverage, 0);
  assert.equal(explicitZero.reviewPackageTrackerFormPayloads, true);
  assert.equal(explicitZero.reviewPackageTrackerFormPayloadCount, 0);
  assert.equal(explicitZero.reviewPackageTrackerFormPayloadCoverage, 0);
  const derived = releaseGateBrowserEvidence(
    {
      evidence: {
        result: {
          interactions: {
            persistedChecks: {
              workflowUiInstallReceiptCopy: true,
              workflowUiInstallReceiptCommandCount: 6,
              workflowUiInstallReceiptChecklistCount: 6,
            },
          },
          verify: { status: "pass", sourceParityFiles: 38 },
          smoke: {},
          mobile: {},
        },
      },
    },
    {},
    {},
    { installReceipt: { ready: true } },
  );
  assert.equal(derived.workflowUiInstallReceiptCoverage, 1);
  assert.equal(derived.workflowUiInstallReceiptCommandCount, 6);
  assert.equal(derived.workflowUiInstallReceiptChecklistCount, 6);
  const derivedReviewPackageCounts = releaseGateBrowserEvidence(
    {
      evidence: {
        result: {
          interactions: {
            persistedChecks: {
              reviewPackageArtifactQualityRubricVisible: true,
              reviewPackageDecisionBriefVisible: true,
              reviewIssueDecisionSummaryVisible: true,
              reviewCommentNoteDecisionSummaryVisible: true,
              reviewResultRepairActionPlanVisible: true,
              reviewPackageSubmissionCloseoutSummaryVisible: true,
              reviewPackageOperatorQuickStartVisible: true,
              reviewPackageTrackerFormCopy: true,
              reviewPackageExternalReceiptIntegrity: true,
              reviewPackageFinalQualityGateVisible: true,
            },
          },
          verify: { status: "pass", sourceParityFiles: 38 },
          smoke: {},
          mobile: {},
        },
      },
    },
  );
  assert.equal(derivedReviewPackageCounts.reviewPackageArtifactQualityItems, 5);
  assert.equal(derivedReviewPackageCounts.reviewPackageDecisionBriefFields, 6);
  assert.equal(derivedReviewPackageCounts.reviewPackageDecisionBriefCoverage, 1);
  assert.equal(derivedReviewPackageCounts.reviewIssueDecisionSummaryFields, 6);
  assert.equal(derivedReviewPackageCounts.reviewIssueDecisionSummaryCoverage, 1);
  assert.equal(derivedReviewPackageCounts.reviewCommentNoteDecisionSummaryFields, 6);
  assert.equal(derivedReviewPackageCounts.reviewCommentNoteDecisionSummaryCoverage, 1);
  assert.equal(derivedReviewPackageCounts.reviewResultRepairActionPlanFields, 6);
  assert.equal(derivedReviewPackageCounts.reviewResultRepairActionPlanCoverage, 1);
  assert.equal(derivedReviewPackageCounts.reviewPackageSubmissionCloseoutSummaryFields, 6);
  assert.equal(derivedReviewPackageCounts.reviewPackageSubmissionCloseoutSummaryCoverage, 1);
  assert.equal(derivedReviewPackageCounts.reviewPackageOperatorQuickStartSteps, 5);
  assert.equal(derivedReviewPackageCounts.reviewPackageOperatorQuickStartCoverage, 1);
  assert.equal(derivedReviewPackageCounts.reviewPackageTrackerFormPayloadCount, 11);
  assert.equal(derivedReviewPackageCounts.reviewPackageTrackerFormPayloadCoverage, 1);
  const derivedParser = releaseGateBrowserEvidence(
    {
      evidence: {
        result: {
          interactions: {
            persistedChecks: {
              postInstallProofParser: true,
              publishDispatchAuthPreflight: true,
              outputQualityAuditReceipt: true,
            },
          },
          verify: { status: "pass", sourceParityFiles: 38 },
          smoke: {},
          mobile: {},
        },
      },
    },
  );
  assert.equal(derivedParser.postInstallProofParserFields, 6);
  assert.equal(derivedParser.postInstallProofParserCoverage, 1);
  assert.equal(derivedParser.postInstallProofParserDetectedFields, 6);
  assert.equal(derivedParser.systemStatusWorkflowAuthPreflightFields, 1);
  assert.equal(derivedParser.outputQualityExternalComparisonSources, 4);
  const sourceBackedParserEvidence = vm.runInNewContext([
    scriptFunctionSource("scripts/capture-output-quality-audit.mjs", "finiteNumberOr"),
    scriptFunctionSource("scripts/capture-output-quality-audit.mjs", "countIssues"),
    "function reviewCommentNoteDecisionSummarySourceReady() { return false; }",
    "function reviewResultRepairActionPlanSourceReady() { return false; }",
    "function reviewPackageSubmissionCloseoutSummarySourceReady() { return false; }",
    "function postInstallEvidenceIntakeSourceReady() { return false; }",
    "function launchProofEvidenceReceiptSourceReady() { return false; }",
    "function outputQualityExternalClaimGuardSourceReady() { return false; }",
    "function homeFirstRunGuidedStartSourceReady() { return false; }",
    "function globalHelpAccessSourceReady() { return false; }",
    "function topbarDataSafetySourceReady() { return false; }",
    "function routeDeepLinkSourceReady() { return false; }",
    "function postInstallProofParserSourceReady() { return true; }",
    "function launchPacketReadyForExternalClaim() { return false; }",
    scriptFunctionSource("scripts/capture-output-quality-audit.mjs", "releaseGateBrowserEvidence"),
    "releaseGateBrowserEvidence;",
  ].join("\n"))(
    {
      evidence: {
        result: {
          interactions: {
            persistedChecks: {},
          },
          verify: { status: "pass", sourceParityFiles: 38 },
          smoke: {},
          mobile: {},
        },
      },
    },
  );
  assert.equal(sourceBackedParserEvidence.postInstallProofParser, true);
  assert.equal(sourceBackedParserEvidence.postInstallProofParserFields, 6);
  assert.equal(sourceBackedParserEvidence.postInstallProofParserCoverage, 1);
  assert.equal(sourceBackedParserEvidence.postInstallProofParserDetectedFields, 0);
  assert.equal(sourceBackedParserEvidence.postInstallProofParserFalsePositiveGuard, true);
  const derivedPostAuthCheckpoint = releaseGateBrowserEvidence(
    {
      evidence: {
        result: {
          interactions: {
            persistedChecks: {},
          },
          verify: { status: "pass", sourceParityFiles: 38 },
          smoke: {},
          mobile: {},
        },
      },
    },
    {},
    {
      packet: true,
      postAuthCheckpoint: {
        expectedSignals: Array.from({ length: 7 }, (_, index) => `signal_${index}`),
        recheckSequence: Array.from({ length: 6 }, (_, index) => ({ key: `step_${index}` })),
        sourceArtifacts: Array.from({ length: 5 }, (_, index) => `artifact_${index}`),
      },
    },
  );
  assert.equal(derivedPostAuthCheckpoint.launchExecutionPacket, true);
  assert.equal(derivedPostAuthCheckpoint.launchExecutionPacketStages, 5);
  assert.equal(derivedPostAuthCheckpoint.launchExecutionPacketCommands, 16);
  assert.equal(derivedPostAuthCheckpoint.launchExecutionPacketExternalComparisonSources, 3);
  assert.equal(derivedPostAuthCheckpoint.launchPostAuthCheckpointCoverage, 1);
  assert.equal(derivedPostAuthCheckpoint.launchPostAuthCheckpointCommandCount, 5);
  assert.equal(derivedPostAuthCheckpoint.launchPostAuthCheckpointExpectedSignals, 7);
  assert.equal(derivedPostAuthCheckpoint.launchPostAuthCheckpointRecheckCount, 6);
  assert.equal(derivedPostAuthCheckpoint.launchPostAuthCheckpointSourceArtifactCount, 5);
  const sourceBackedPostInstallIntake = releaseGateBrowserEvidence(
    {
      evidence: {
        result: {
          interactions: {
            persistedChecks: {},
          },
          verify: { status: "pass", sourceParityFiles: 38 },
          smoke: {},
          mobile: {},
        },
      },
    },
    {},
    {
      postInstallEvidenceIntake: {
        ready: true,
        fieldCount: 6,
        fieldCoverage: 1,
      },
    },
  );
  assert.equal(sourceBackedPostInstallIntake.postInstallEvidenceIntake, true);
  assert.equal(sourceBackedPostInstallIntake.postInstallEvidenceIntakeFields, 6);
  assert.equal(sourceBackedPostInstallIntake.postInstallEvidenceIntakeFieldCoverage, 1);
  const sourceBackedLaunchProofEvidence = releaseGateBrowserEvidence(
    {
      evidence: {
        result: {
          interactions: {
            persistedChecks: {},
          },
          verify: { status: "pass", sourceParityFiles: 38 },
          smoke: {},
          mobile: {},
        },
      },
    },
    {
      launchProofEvidenceReceipt: "JooPark Launch Proof Evidence Receipt",
      launchProofEvidenceFields: Array.from({ length: 6 }, (_, index) => ({ key: `proof_${index}` })),
    },
  );
  assert.equal(sourceBackedLaunchProofEvidence.launchProofEvidenceReceipt, true);
  assert.equal(sourceBackedLaunchProofEvidence.launchProofEvidenceFields, 6);
  assert.equal(sourceBackedLaunchProofEvidence.launchProofEvidenceFieldCoverage, 1);
  const sourceReadyText = [
    "JooPark GitHub UI Workflow Paste Packet",
    "Post-install evidence fields to fill:",
    "safeToDispatch=true before gh workflow run",
  ].join("\n");
  const sourceBackedPastePacket = releaseGateBrowserEvidence(
    {
      evidence: {
        result: {
          interactions: {
            persistedChecks: {
              workflowUiInstallPastePacketCopy: false,
              workflowUiInstallReceiptCopy: false,
            },
          },
          verify: { status: "pass", sourceParityFiles: 38 },
          smoke: {},
          mobile: {},
        },
      },
    },
    {},
    {},
    {
      workflowUiInstallPastePacketReady: true,
      workflowUiInstallPastePacketCoverage: 1,
      installReceipt: { ready: true, commandCount: 6, checklistCount: 6, text: sourceReadyText },
    },
  );
  assert.equal(sourceBackedPastePacket.workflowUiInstallPastePacketCopy, true);
  assert.equal(sourceBackedPastePacket.workflowUiInstallPastePacketCoverage, 1);
  const explicitZeroPastePacket = releaseGateBrowserEvidence(
    {
      evidence: {
        result: {
          interactions: {
            persistedChecks: {
              workflowUiInstallPastePacketCopy: false,
              workflowUiInstallReceiptCopy: false,
            },
          },
          verify: { status: "pass", sourceParityFiles: 38 },
          smoke: {},
          mobile: {},
        },
      },
    },
    {},
    {},
    {
      workflowUiInstallPastePacketReady: true,
      workflowUiInstallPastePacketCoverage: 0,
      installReceipt: { ready: true, commandCount: 6, checklistCount: 6, text: sourceReadyText },
    },
  );
  assert.equal(explicitZeroPastePacket.workflowUiInstallPastePacketCopy, false);
  assert.equal(explicitZeroPastePacket.workflowUiInstallPastePacketCoverage, 0);
  const explicitZeroPersistedPastePacket = releaseGateBrowserEvidence(
    {
      evidence: {
        result: {
          interactions: {
            persistedChecks: {
              workflowUiInstallPastePacketCopy: true,
              workflowUiInstallPastePacketCoverage: 0,
            },
          },
          verify: { status: "pass", sourceParityFiles: 38 },
          smoke: {},
          mobile: {},
        },
      },
    },
  );
  assert.equal(explicitZeroPersistedPastePacket.workflowUiInstallPastePacketCopy, true);
  assert.equal(explicitZeroPersistedPastePacket.workflowUiInstallPastePacketCoverage, 0);
  const derivedPersistedPastePacket = releaseGateBrowserEvidence(
    {
      evidence: {
        result: {
          interactions: {
            persistedChecks: {
              workflowUiInstallPastePacketCopy: true,
            },
          },
          verify: { status: "pass", sourceParityFiles: 38 },
          smoke: {},
          mobile: {},
        },
      },
    },
  );
  assert.equal(derivedPersistedPastePacket.workflowUiInstallPastePacketCopy, true);
  assert.equal(derivedPersistedPastePacket.workflowUiInstallPastePacketCoverage, 1);
  assert.match(source, /const workflowUiInstallPastePacketText = String\(/);
  assert.match(source, /const workflowUiInstallPastePacketSourceReady = !!\(/);
  assert.match(source, /const workflowUiInstallPastePacketEvidenceReady = !!\(/);
  assert.equal(source.includes("workflowUiInstallPastePacketCopy: !!(persistedChecks.workflowUiInstallPastePacketCopy || persistedChecks.workflowUiInstallReceiptCopy)"), false);
  assert.match(source, /const workflowUiInstallReceiptCoverage = finiteNumberOr\(\s+workflowUiInstallReceipt\.coverage,/);
  assert.match(source, /const workflowUiInstallReceiptCommandCount = finiteNumberOr\(workflowUiInstallReceipt\.commandCount, persistedChecks\.workflowUiInstallReceiptCommandCount\)/);
  assert.match(source, /const workflowUiInstallReceiptChecklistCount = finiteNumberOr\(workflowUiInstallReceipt\.checklistCount, persistedChecks\.workflowUiInstallReceiptChecklistCount\)/);
  assert.match(source, /workflowUiInstallPastePacketCoverage,\n    globalHelpAccess:/);
  assert.match(source, /const postInstallProofParserDetectedFields = finiteNumberOr\(\s+persistedChecks\.postInstallProofParserDetectedFields,\s+persistedChecks\.postInstallProofParser \? 6 : 0,/);
  assert.match(source, /const postInstallProofParserSourceReadyFlag = postInstallProofParserSourceReady\(\)/);
  assert.match(source, /const postInstallProofParserFields = finiteNumberOr\(\s+persistedChecks\.postInstallProofParserFields,\s+postInstallProofParserReady \? 6 : 0,/);
  assert.match(source, /const postInstallProofParserCoverage = finiteNumberOr\(\s+persistedChecks\.postInstallProofParserCoverage,\s+postInstallProofParserReady \? 1 : 0,/);
  assert.match(source, /const postInstallProofParserFalsePositiveGuard = !!\(/);
  assert.match(source, /postInstallProofParserFalsePositiveGuard,\n    postInstallProofParserFields,/);
  assert.match(source, /const systemStatusWorkflowAuthPreflightFields = finiteNumberOr\(\s+persistedChecks\.systemStatusWorkflowAuthPreflightFields,\s+persistedChecks\.publishDispatchAuthPreflight \? 1 : 0,/);
  assert.match(source, /const launchExecutionPacketStageCount = finiteNumberOr\(\s+launchExecutionPacket\?\.stageCount,\s+launchExecutionPacketReady \? 5 : 0,/);
  assert.match(source, /const launchExecutionPacketCommandCount = finiteNumberOr\(\s+launchExecutionPacket\?\.commandCount,\s+launchExecutionPacketReady \? 16 : 0,/);
  assert.match(source, /const launchExecutionPacketExternalComparisonSourceCount = finiteNumberOr\(\s+launchExecutionPacket\?\.externalComparisonSourceCount,\s+launchExecutionPacketExternalComparisons\.length \|\| \(launchExecutionPacketReady \? 3 : 0\),/);
  assert.match(source, /const launchPostAuthCheckpointCoverage = finiteNumberOr\(\s+launchPostAuthCheckpoint\.coverage,\s+launchExecutionPacketReady \? 1 : 0,/);
  assert.match(source, /const launchPostAuthCheckpointCommandCount = finiteNumberOr\(\s+launchPostAuthCheckpoint\.commandCount,\s+launchExecutionPacketReady \? 5 : 0,/);
  assert.match(source, /const launchPostAuthCheckpointExpectedSignalCount = finiteNumberOr\(\s+launchPostAuthCheckpoint\.expectedSignalCount,\s+launchPostAuthCheckpointExpectedSignalItems\.length \|\| \(launchExecutionPacketReady \? 6 : 0\),/);
  assert.match(source, /const launchPostAuthCheckpointRecheckCount = finiteNumberOr\(\s+launchPostAuthCheckpoint\.recheckSequenceCount,\s+launchPostAuthCheckpointRecheckItems\.length \|\| \(launchExecutionPacketReady \? 5 : 0\),/);
  assert.match(source, /const launchPostAuthCheckpointSourceArtifactCount = finiteNumberOr\(\s+launchPostAuthCheckpoint\.sourceArtifactCount,\s+launchPostAuthCheckpointSourceArtifacts\.length \|\| \(launchExecutionPacketReady \? 4 : 0\),/);
  assert.match(source, /const launchPostInstallEvidenceIntake = launchExecutionPacket\?\.postInstallEvidenceIntake/);
  assert.match(source, /const postInstallEvidenceIntakeFields = finiteNumberOr\(\s+launchPostInstallEvidenceIntake\.fieldCount,/);
  assert.match(source, /const postInstallEvidenceIntakeFieldCoverage = finiteNumberOr\(\s+launchPostInstallEvidenceIntake\.fieldCoverage,/);
  assert.match(source, /const launchProofEvidenceFields = finiteNumberOr\(\s+publishEvidence\?\.launchProofEvidenceFieldCount,/);
  assert.match(source, /const launchProofEvidenceFieldCoverage = finiteNumberOr\(\s+publishEvidence\?\.launchProofEvidenceFieldCoverage,/);
  assert.match(source, /const outputQualityExternalComparisonSources = finiteNumberOr\(\s+persistedChecks\.outputQualityExternalComparisonSources,/);
  assert.match(source, /const reviewPackageArtifactQualityItems = finiteNumberOr\(\s+persistedChecks\.reviewPackageArtifactQualityItems,/);
  assert.match(source, /const reviewPackageDecisionBriefFields = finiteNumberOr\(\s+persistedChecks\.reviewPackageDecisionBriefFields,/);
  assert.match(source, /const reviewPackageDecisionBriefCoverage = finiteNumberOr\(\s+persistedChecks\.reviewPackageDecisionBriefCoverage,/);
  assert.match(source, /const reviewIssueDecisionSummaryFields = finiteNumberOr\(\s+persistedChecks\.reviewIssueDecisionSummaryFields,/);
  assert.match(source, /const reviewIssueDecisionSummaryCoverage = finiteNumberOr\(\s+persistedChecks\.reviewIssueDecisionSummaryCoverage,/);
  assert.match(source, /const reviewCommentNoteDecisionSummaryFields = finiteNumberOr\(\s+persistedChecks\.reviewCommentNoteDecisionSummaryFields,/);
  assert.match(source, /const reviewCommentNoteDecisionSummaryCoverage = finiteNumberOr\(\s+persistedChecks\.reviewCommentNoteDecisionSummaryCoverage,/);
  assert.match(source, /const reviewResultRepairActionPlanFields = finiteNumberOr\(\s+persistedChecks\.reviewResultRepairActionPlanFields,/);
  assert.match(source, /const reviewResultRepairActionPlanCoverage = finiteNumberOr\(\s+persistedChecks\.reviewResultRepairActionPlanCoverage,/);
  assert.match(source, /const reviewPackageSubmissionCloseoutSummaryFields = finiteNumberOr\(\s+persistedChecks\.reviewPackageSubmissionCloseoutSummaryFields,/);
  assert.match(source, /const reviewPackageSubmissionCloseoutSummaryCoverage = finiteNumberOr\(\s+persistedChecks\.reviewPackageSubmissionCloseoutSummaryCoverage,/);
  assert.match(source, /const reviewPackageOperatorQuickStartSteps = finiteNumberOr\(\s+persistedChecks\.reviewPackageOperatorQuickStartSteps,/);
  assert.match(source, /const reviewPackageOperatorQuickStartCoverage = finiteNumberOr\(\s+persistedChecks\.reviewPackageOperatorQuickStartCoverage,/);
  assert.match(source, /const reviewPackageTrackerFormPayloadCount = finiteNumberOr\(\s+persistedChecks\.reviewPackageTrackerFormPayloadCount,/);
  assert.match(source, /const reviewPackageTrackerFormPayloadCoverage = finiteNumberOr\(\s+persistedChecks\.reviewPackageTrackerFormPayloadCoverage,/);
  assert.equal(source.includes("Number(workflowUiInstallReceipt.commandCount || persistedChecks.workflowUiInstallReceiptCommandCount || 0)"), false);
  assert.equal(source.includes("Number(workflowUiInstallReceipt.checklistCount || persistedChecks.workflowUiInstallReceiptChecklistCount || 0)"), false);
  assert.equal(source.includes("workflowUiInstallReceiptCoverage: workflowUiInstallReceiptReady ? 1 : 0"), false);
  assert.equal(source.includes("workflowUiInstallPastePacketEvidenceReady ? Math.max(1, workflowUiInstallPastePacketCoverage) : workflowUiInstallPastePacketCoverage"), false);
  assert.equal(source.includes("postInstallProofParserFields: postInstallProofParserReady ? 6 : 0"), false);
  assert.equal(source.includes("postInstallProofParserCoverage: postInstallProofParserReady ? 1 : 0"), false);
  assert.equal(source.includes("postInstallProofParserFalsePositiveGuard: !!persistedChecks.postInstallProofParserFalsePositiveGuard"), false);
  assert.equal(source.includes("Number(persistedChecks.postInstallProofParserDetectedFields || (persistedChecks.postInstallProofParser ? 6 : 0))"), false);
  assert.equal(source.includes("systemStatusWorkflowAuthPreflightFields: persistedChecks.publishDispatchAuthPreflight ? 1 : 0"), false);
  assert.equal(source.includes("launchExecutionPacketStages: 5"), false);
  assert.equal(source.includes("launchExecutionPacketCommands: 16"), false);
  assert.equal(source.includes("launchExecutionPacketExternalComparisonSources: 3"), false);
  assert.equal(source.includes("launchPostAuthCheckpointCoverage: launchExecutionPacketReady ? 1 : 0"), false);
  assert.equal(source.includes("launchPostAuthCheckpointCommandCount: launchExecutionPacketReady ? 5 : 0"), false);
  assert.equal(source.includes("launchPostAuthCheckpointExpectedSignals: launchExecutionPacketReady ? 6 : 0"), false);
  assert.equal(source.includes("launchPostAuthCheckpointRecheckCount: launchExecutionPacketReady ? 5 : 0"), false);
  assert.equal(source.includes("launchPostAuthCheckpointSourceArtifactCount: launchExecutionPacketReady ? 4 : 0"), false);
  assert.equal(source.includes("postInstallEvidenceIntakeFields: postInstallEvidenceIntakeReady ? 6 : 0"), false);
  assert.equal(source.includes("postInstallEvidenceIntakeFieldCoverage: postInstallEvidenceIntakeReady ? 1 : 0"), false);
  assert.equal(source.includes("launchProofEvidenceFields: launchProofEvidenceReceiptReady ? 6 : 0"), false);
  assert.equal(source.includes("launchProofEvidenceFieldCoverage: launchProofEvidenceReceiptReady ? 1 : 0"), false);
  assert.equal(source.includes("outputQualityExternalComparisonSources: 4"), false);
  assert.equal(source.includes("reviewPackageDecisionBriefFields: persistedChecks.reviewPackageDecisionBriefVisible ? 6 : 0"), false);
  assert.equal(source.includes("reviewIssueDecisionSummaryFields: persistedChecks.reviewIssueDecisionSummaryVisible ? 6 : 0"), false);
  assert.equal(source.includes("reviewPackageTrackerFormPayloadCount: trackerFormPayloadsReady ? 11 : 0"), false);
}

function testOutputQualityReleaseGateBrowserEvidenceAccessSurfacesPreserveExplicitZero() {
  const source = readFileSync(join(root, "scripts/capture-output-quality-audit.mjs"), "utf8");
  const releaseGateBrowserEvidence = vm.runInNewContext([
    scriptFunctionSource("scripts/capture-output-quality-audit.mjs", "finiteNumberOr"),
    scriptFunctionSource("scripts/capture-output-quality-audit.mjs", "countIssues"),
    "function reviewCommentNoteDecisionSummarySourceReady() { return false; }",
    "function reviewResultRepairActionPlanSourceReady() { return false; }",
    "function reviewPackageSubmissionCloseoutSummarySourceReady() { return false; }",
    "function postInstallEvidenceIntakeSourceReady() { return false; }",
    "function launchProofEvidenceReceiptSourceReady() { return false; }",
    "function outputQualityExternalClaimGuardSourceReady() { return false; }",
    "function homeFirstRunGuidedStartSourceReady() { return false; }",
    "function globalHelpAccessSourceReady() { return false; }",
    "function topbarDataSafetySourceReady() { return false; }",
    "function routeDeepLinkSourceReady() { return false; }",
    "function postInstallProofParserSourceReady() { return false; }",
    "function launchPacketReadyForExternalClaim() { return false; }",
    scriptFunctionSource("scripts/capture-output-quality-audit.mjs", "releaseGateBrowserEvidence"),
    "releaseGateBrowserEvidence;",
  ].join("\n"));
  const explicitZero = releaseGateBrowserEvidence({
    evidence: {
      result: {
        interactions: {
          persistedChecks: {
            globalHelpAccess: true,
            globalHelpAccessActions: 0,
            globalHelpAccessCoverage: 0,
            topbarDataSafety: true,
            topbarDataSafetyActions: 0,
            topbarDataSafetyCoverage: 0,
            routeDeepLink: true,
            routeDeepLinkCoverage: 0,
            homeFirstRunGuidedStart: true,
            homeFirstRunGuidedStartItems: 0,
            homeFirstRunGuidedStartCoverage: 0,
          },
        },
      },
    },
  });
  assert.equal(explicitZero.globalHelpAccess, true);
  assert.equal(explicitZero.globalHelpAccessActions, 0);
  assert.equal(explicitZero.globalHelpAccessCoverage, 0);
  assert.equal(explicitZero.topbarDataSafety, true);
  assert.equal(explicitZero.topbarDataSafetyActions, 0);
  assert.equal(explicitZero.topbarDataSafetyCoverage, 0);
  assert.equal(explicitZero.routeDeepLink, true);
  assert.equal(explicitZero.routeDeepLinkCoverage, 0);
  assert.equal(explicitZero.homeFirstRunGuidedStart, true);
  assert.equal(explicitZero.homeFirstRunGuidedStartItems, 0);
  assert.equal(explicitZero.homeFirstRunGuidedStartCoverage, 0);
  const derived = releaseGateBrowserEvidence({
    evidence: {
      result: {
        interactions: {
          persistedChecks: {
            globalHelpAccess: true,
            topbarDataSafety: true,
            routeDeepLink: true,
            homeFirstRunGuidedStart: true,
          },
        },
      },
    },
  });
  assert.equal(derived.globalHelpAccessActions, 4);
  assert.equal(derived.globalHelpAccessCoverage, 1);
  assert.equal(derived.topbarDataSafetyActions, 4);
  assert.equal(derived.topbarDataSafetyCoverage, 1);
  assert.equal(derived.routeDeepLinkCoverage, 1);
  assert.equal(derived.homeFirstRunGuidedStartItems, 3);
  assert.equal(derived.homeFirstRunGuidedStartCoverage, 1);
  assert.match(source, /const globalHelpAccessActions = finiteNumberOr\(\s+persistedChecks\.globalHelpAccessActions,\s+globalHelpAccessReady \? 4 : 0,/);
  assert.match(source, /const globalHelpAccessCoverage = finiteNumberOr\(\s+persistedChecks\.globalHelpAccessCoverage,\s+globalHelpAccessReady \? 1 : 0,/);
  assert.match(source, /const topbarDataSafetyActions = finiteNumberOr\(\s+persistedChecks\.topbarDataSafetyActions,\s+topbarDataSafetyReady \? 4 : 0,/);
  assert.match(source, /const topbarDataSafetyCoverage = finiteNumberOr\(\s+persistedChecks\.topbarDataSafetyCoverage,\s+topbarDataSafetyReady \? 1 : 0,/);
  assert.match(source, /const routeDeepLinkCoverage = finiteNumberOr\(\s+persistedChecks\.routeDeepLinkCoverage,\s+routeDeepLinkReady \? 1 : 0,/);
  assert.match(source, /const homeFirstRunGuidedStartItems = finiteNumberOr\(\s+persistedChecks\.homeFirstRunGuidedStartItems,\s+homeFirstRunGuidedStartReady \? 3 : 0,/);
  assert.match(source, /const homeFirstRunGuidedStartCoverage = finiteNumberOr\(\s+persistedChecks\.homeFirstRunGuidedStartCoverage,\s+homeFirstRunGuidedStartReady \? 1 : 0,/);
  assert.equal(source.includes("globalHelpAccessActions: globalHelpAccessReady ? 4 : 0"), false);
  assert.equal(source.includes("globalHelpAccessCoverage: globalHelpAccessReady ? 1 : 0"), false);
  assert.equal(source.includes("topbarDataSafetyActions: topbarDataSafetyReady ? 4 : 0"), false);
  assert.equal(source.includes("topbarDataSafetyCoverage: topbarDataSafetyReady ? 1 : 0"), false);
  assert.equal(source.includes("routeDeepLinkCoverage: routeDeepLinkReady ? 1 : 0"), false);
  assert.equal(source.includes("homeFirstRunGuidedStartItems: homeFirstRunGuidedStartReady ? 3 : 0"), false);
  assert.equal(source.includes("homeFirstRunGuidedStartCoverage: homeFirstRunGuidedStartReady ? 1 : 0"), false);
}

function testOutputQualityReleaseGateBrowserEvidenceReviewPackageCountsPreserveExplicitZero() {
  const source = readFileSync(join(root, "scripts/capture-output-quality-audit.mjs"), "utf8");
  const releaseGateBrowserEvidence = vm.runInNewContext([
    scriptFunctionSource("scripts/capture-output-quality-audit.mjs", "finiteNumberOr"),
    scriptFunctionSource("scripts/capture-output-quality-audit.mjs", "countIssues"),
    "function reviewCommentNoteDecisionSummarySourceReady() { return false; }",
    "function reviewResultRepairActionPlanSourceReady() { return false; }",
    "function reviewPackageSubmissionCloseoutSummarySourceReady() { return false; }",
    "function postInstallEvidenceIntakeSourceReady() { return false; }",
    "function launchProofEvidenceReceiptSourceReady() { return false; }",
    "function outputQualityExternalClaimGuardSourceReady() { return false; }",
    "function homeFirstRunGuidedStartSourceReady() { return false; }",
    "function globalHelpAccessSourceReady() { return false; }",
    "function topbarDataSafetySourceReady() { return false; }",
    "function routeDeepLinkSourceReady() { return false; }",
    "function postInstallProofParserSourceReady() { return false; }",
    "function launchPacketReadyForExternalClaim() { return false; }",
    scriptFunctionSource("scripts/capture-output-quality-audit.mjs", "releaseGateBrowserEvidence"),
    "releaseGateBrowserEvidence;",
  ].join("\n"));
  const explicitZero = releaseGateBrowserEvidence({
    evidence: {
      result: {
        interactions: {
          persistedChecks: {
            reviewPackageArtifactQualityRubricVisible: true,
            reviewPackageArtifactQualityItems: 0,
            reviewPackageDecisionBriefVisible: true,
            reviewPackageDecisionBriefFields: 0,
            reviewPackageDecisionBriefCoverage: 0,
            reviewIssueDecisionSummaryVisible: true,
            reviewIssueDecisionSummaryFields: 0,
            reviewIssueDecisionSummaryCoverage: 0,
            reviewCommentNoteDecisionSummaryVisible: true,
            reviewCommentNoteDecisionSummaryFields: 0,
            reviewCommentNoteDecisionSummaryCoverage: 0,
            reviewResultRepairActionPlanVisible: true,
            reviewResultRepairActionPlanFields: 0,
            reviewResultRepairActionPlanCoverage: 0,
            reviewPackageSubmissionCloseoutSummaryVisible: true,
            reviewPackageSubmissionCloseoutSummaryFields: 0,
            reviewPackageSubmissionCloseoutSummaryCoverage: 0,
            reviewPackageOperatorQuickStartVisible: true,
            reviewPackageOperatorQuickStartSteps: 0,
            reviewPackageOperatorQuickStartCoverage: 0,
            reviewPackageTrackerFormCopy: true,
            reviewPackageExternalReceiptIntegrity: true,
            reviewPackageFinalQualityGateVisible: true,
            reviewPackageTrackerFormPayloadCount: 0,
            reviewPackageTrackerFormPayloadCoverage: 0,
          },
        },
      },
    },
  });
  assert.equal(explicitZero.reviewPackageArtifactQualityItems, 0);
  assert.equal(explicitZero.reviewPackageDecisionBriefFields, 0);
  assert.equal(explicitZero.reviewPackageDecisionBriefCoverage, 0);
  assert.equal(explicitZero.reviewIssueDecisionSummaryFields, 0);
  assert.equal(explicitZero.reviewIssueDecisionSummaryCoverage, 0);
  assert.equal(explicitZero.reviewCommentNoteDecisionSummaryFields, 0);
  assert.equal(explicitZero.reviewCommentNoteDecisionSummaryCoverage, 0);
  assert.equal(explicitZero.reviewResultRepairActionPlanFields, 0);
  assert.equal(explicitZero.reviewResultRepairActionPlanCoverage, 0);
  assert.equal(explicitZero.reviewPackageSubmissionCloseoutSummaryFields, 0);
  assert.equal(explicitZero.reviewPackageSubmissionCloseoutSummaryCoverage, 0);
  assert.equal(explicitZero.reviewPackageOperatorQuickStartSteps, 0);
  assert.equal(explicitZero.reviewPackageOperatorQuickStartCoverage, 0);
  assert.equal(explicitZero.reviewPackageTrackerFormPayloadCount, 0);
  assert.equal(explicitZero.reviewPackageTrackerFormPayloadCoverage, 0);
  const derived = releaseGateBrowserEvidence({
    evidence: {
      result: {
        interactions: {
          persistedChecks: {
            reviewPackageArtifactQualityRubricVisible: true,
            reviewPackageDecisionBriefVisible: true,
            reviewIssueDecisionSummaryVisible: true,
            reviewCommentNoteDecisionSummaryVisible: true,
            reviewResultRepairActionPlanVisible: true,
            reviewPackageSubmissionCloseoutSummaryVisible: true,
            reviewPackageOperatorQuickStartVisible: true,
            reviewPackageTrackerFormCopy: true,
            reviewPackageExternalReceiptIntegrity: true,
            reviewPackageFinalQualityGateVisible: true,
          },
        },
      },
    },
  });
  assert.equal(derived.reviewPackageArtifactQualityItems, 5);
  assert.equal(derived.reviewPackageDecisionBriefFields, 6);
  assert.equal(derived.reviewPackageDecisionBriefCoverage, 1);
  assert.equal(derived.reviewIssueDecisionSummaryFields, 6);
  assert.equal(derived.reviewIssueDecisionSummaryCoverage, 1);
  assert.equal(derived.reviewCommentNoteDecisionSummaryFields, 6);
  assert.equal(derived.reviewCommentNoteDecisionSummaryCoverage, 1);
  assert.equal(derived.reviewResultRepairActionPlanFields, 6);
  assert.equal(derived.reviewResultRepairActionPlanCoverage, 1);
  assert.equal(derived.reviewPackageSubmissionCloseoutSummaryFields, 6);
  assert.equal(derived.reviewPackageSubmissionCloseoutSummaryCoverage, 1);
  assert.equal(derived.reviewPackageOperatorQuickStartSteps, 5);
  assert.equal(derived.reviewPackageOperatorQuickStartCoverage, 1);
  assert.equal(derived.reviewPackageTrackerFormPayloadCount, 11);
  assert.equal(derived.reviewPackageTrackerFormPayloadCoverage, 1);
  assert.match(source, /const reviewPackageArtifactQualityItems = finiteNumberOr\(\s+persistedChecks\.reviewPackageArtifactQualityItems,/);
  assert.match(source, /const reviewPackageDecisionBriefFields = finiteNumberOr\(\s+persistedChecks\.reviewPackageDecisionBriefFields,/);
  assert.match(source, /const reviewIssueDecisionSummaryFields = finiteNumberOr\(\s+persistedChecks\.reviewIssueDecisionSummaryFields,/);
  assert.match(source, /const reviewCommentNoteDecisionSummaryFields = finiteNumberOr\(\s+persistedChecks\.reviewCommentNoteDecisionSummaryFields,/);
  assert.match(source, /const reviewResultRepairActionPlanFields = finiteNumberOr\(\s+persistedChecks\.reviewResultRepairActionPlanFields,/);
  assert.match(source, /const reviewPackageSubmissionCloseoutSummaryFields = finiteNumberOr\(\s+persistedChecks\.reviewPackageSubmissionCloseoutSummaryFields,/);
  assert.match(source, /const reviewPackageOperatorQuickStartSteps = finiteNumberOr\(\s+persistedChecks\.reviewPackageOperatorQuickStartSteps,/);
  assert.match(source, /const reviewPackageTrackerFormPayloadCount = finiteNumberOr\(\s+persistedChecks\.reviewPackageTrackerFormPayloadCount,/);
  assert.equal(source.includes("reviewPackageArtifactQualityItems: persistedChecks.reviewPackageArtifactQualityRubricVisible ? 5 : 0"), false);
  assert.equal(source.includes("reviewPackageDecisionBriefFields: persistedChecks.reviewPackageDecisionBriefVisible ? 6 : 0"), false);
  assert.equal(source.includes("reviewIssueDecisionSummaryFields: persistedChecks.reviewIssueDecisionSummaryVisible ? 6 : 0"), false);
  assert.equal(source.includes("reviewCommentNoteDecisionSummaryFields: reviewCommentNoteDecisionSummaryVisible ? 6 : 0"), false);
  assert.equal(source.includes("reviewResultRepairActionPlanFields: reviewResultRepairActionPlanVisible ? 6 : 0"), false);
  assert.equal(source.includes("reviewPackageSubmissionCloseoutSummaryFields: reviewPackageSubmissionCloseoutSummaryVisible ? 6 : 0"), false);
  assert.equal(source.includes("reviewPackageOperatorQuickStartSteps: persistedChecks.reviewPackageOperatorQuickStartVisible ? 5 : 0"), false);
  assert.equal(source.includes("reviewPackageTrackerFormPayloadCount: trackerFormPayloadsReady ? 11 : 0"), false);
}

function testOutputQualityPostInstallIntakeCountsPreserveExplicitZero() {
  const source = readFileSync(join(root, "scripts/capture-output-quality-audit.mjs"), "utf8");
  const postInstallEvidenceIntakeSnapshot = vm.runInNewContext([
    scriptFunctionSource("scripts/capture-output-quality-audit.mjs", "finiteNumberOr"),
    scriptFunctionSource("scripts/capture-output-quality-audit.mjs", "postInstallEvidenceIntakeSnapshot"),
    "postInstallEvidenceIntakeSnapshot;",
  ].join("\n"));
  const fields = [
    { key: "pages_workflow_commit", label: "Pages workflow commit" },
    { key: "drift_workflow_commit", label: "Drift Watch workflow commit" },
    { key: "remote_parity_proof", label: "Remote parity proof", currentValue: "remoteWorkflowFilesReady=false" },
    { key: "actions_visibility_proof", label: "Actions visibility proof" },
    { key: "dispatch_readiness_proof", label: "Dispatch readiness proof" },
    { key: "handoff_verifier_proof", label: "Handoff verifier proof", expectedValue: "safeToDispatch=true" },
  ];
  const quickProofSteps = Array.from({ length: 4 }, (_, index) => ({
    key: `step_${index}`,
    command: "node proof",
    expected: "expected",
    evidenceFieldKey: "remote_parity_proof",
  }));
  const quickProofFieldMappings = Array.from({ length: 4 }, (_, index) => ({
    stepKey: `step_${index}`,
    fieldKey: "remote_parity_proof",
    fieldLabel: "Remote parity proof",
    proofCommand: "node proof",
    expectedValue: "expected",
    fieldCompleted: true,
  }));
  const explicitZero = postInstallEvidenceIntakeSnapshot({
    latestGate: {
      browserEvidence: {
        postInstallEvidenceIntakeFields: 6,
        postInstallEvidenceIntakeFieldCoverage: 1,
      },
    },
    launchExecutionPacket: {
      postInstallEvidenceIntake: {
        source: "generated_from_launch_execution_packet",
        status: "collect_post_install_proof",
        fieldCount: 0,
        fieldCoverage: 0,
        completedFieldCount: 0,
        pendingFieldCount: 0,
        commandCount: 0,
        signalCount: 0,
        checklistCount: 0,
        quickProofStepCount: 0,
        quickProofCoverage: 0,
        quickProofMappedFieldCount: 0,
        quickProofCompletedMappedFieldCount: 0,
        quickProofPendingMappedFieldCount: 0,
        quickProofFieldMappingCoverage: 0,
        fields,
        commands: ["a", "b", "c", "d"],
        expectedSignals: Array.from({ length: 8 }, (_, index) => `signal_${index}`),
        quickProofSteps,
        quickProofFieldMappings,
        quickProofReceipt: "JooPark Post-Install Quick Proof Receipt",
        dispatchGuard: "safeToDispatch=true before gh workflow run",
      },
    },
  });
  assert.equal(explicitZero.ready, false);
  assert.equal(explicitZero.fields, 0);
  assert.equal(explicitZero.coverage, 0);
  assert.equal(explicitZero.commandCount, 0);
  assert.equal(explicitZero.signalCount, 0);
  assert.equal(explicitZero.quickProofReady, false);
  assert.equal(explicitZero.quickProofStepCount, 0);
  assert.equal(explicitZero.quickProofMappedFieldCount, 0);
  assert.equal(explicitZero.quickProofCompletedMappedFieldCount, 0);
  assert.equal(explicitZero.quickProofPendingMappedFieldCount, 0);
  const readyIntake = postInstallEvidenceIntakeSnapshot({
    latestGate: { browserEvidence: {} },
    launchExecutionPacket: {
      postInstallEvidenceIntake: {
        source: "generated_from_launch_execution_packet",
        status: "collect_post_install_proof",
        fieldCount: 6,
        fieldCoverage: 1,
        completedFieldCount: 2,
        pendingFieldCount: 4,
        commandCount: 4,
        signalCount: 8,
        quickProofStepCount: 4,
        quickProofCoverage: 1,
        quickProofMappedFieldCount: 4,
        quickProofCompletedMappedFieldCount: 2,
        quickProofPendingMappedFieldCount: 2,
        quickProofFieldMappingCoverage: 1,
        fields,
        commands: ["a", "b", "c", "d"],
        expectedSignals: Array.from({ length: 8 }, (_, index) => `signal_${index}`),
        quickProofSteps,
        quickProofFieldMappings,
        quickProofReceipt: "JooPark Post-Install Quick Proof Receipt",
        dispatchGuard: "safeToDispatch=true before gh workflow run",
      },
    },
  });
  assert.equal(readyIntake.ready, true);
  assert.equal(readyIntake.fields, 6);
  assert.equal(readyIntake.coverage, 1);
  assert.equal(readyIntake.commandCount, 4);
  assert.equal(readyIntake.signalCount, 8);
  assert.equal(readyIntake.quickProofStepCount, 4);
  assert.equal(readyIntake.quickProofMappedFieldCount, 4);
  assert.equal(readyIntake.quickProofCompletedMappedFieldCount, 2);
  assert.equal(readyIntake.quickProofPendingMappedFieldCount, 2);
  assert.match(source, /const intakeFieldCount = finiteNumberOr\(intake\.fieldCount, fieldItems\.length\)/);
  assert.match(source, /const quickProofStepCount = finiteNumberOr\(intake\.quickProofStepCount, quickProofSteps\.length\)/);
  assert.equal(source.includes("Number(intake.fieldCount || fieldItems.length || 0)"), false);
  assert.equal(source.includes("Number(intake.commandCount || commands.length || 0)"), false);
  assert.equal(source.includes("Number(intake.quickProofStepCount || quickProofSteps.length || 0)"), false);
}

function testOutputQualityOperatorOnePageHandoffCountsPreserveExplicitZero() {
  const source = readFileSync(join(root, "scripts/capture-output-quality-audit.mjs"), "utf8");
  const operatorOnePageHandoffSnapshot = vm.runInNewContext([
    scriptFunctionSource("scripts/capture-output-quality-audit.mjs", "finiteNumberOr"),
    scriptFunctionSource("scripts/capture-output-quality-audit.mjs", "operatorOnePageHandoffSnapshot"),
    "operatorOnePageHandoffSnapshot;",
  ].join("\n"));
  const successSignals = [
    "workflowScopeAvailable=true or GitHub UI installAction rows applied on the default branch",
    "remoteWorkflowFilesReady=true",
    "remoteWorkflowVisibilityReady=true",
    "dispatchReady=true",
    "driftDispatchReady=true",
    "allDispatchReady=true",
    "all six post-install evidence fields are filled",
    "safeToDispatch=true before gh workflow run",
  ];
  const text = [
    "JooPark Launch Operator One-Page Handoff",
    "Do first:",
    "If CLI workflow scope is still blocked, use GitHub UI fallback:",
    "Prove after install:",
    "Success signals:",
    ...successSignals,
    "Do not run or claim yet:",
  ].join("\n");
  const handoff = {
    ready: true,
    text,
    sectionCount: 0,
    commandCount: 0,
    immediateCommandCount: 0,
    fallbackCommandCount: 0,
    proofCommandCount: 0,
    successSignalCount: 0,
    evidenceFieldCount: 0,
    forbiddenCommandCount: 0,
    immediateCommands: ["node immediate"],
    fallbackCommands: ["node fallback", "node fallback 2", "node fallback 3"],
    proofCommands: ["node proof 1", "node proof 2", "node proof 3", "node scripts/verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write"],
    successSignals,
    forbiddenCommands: ["gh workflow run pages", "gh workflow run drift", "Do not claim readyForExternalClaim=true"],
  };
  const explicitZero = operatorOnePageHandoffSnapshot({
    operatorOnePageHandoff: handoff,
  });
  assert.equal(explicitZero.ready, false);
  assert.equal(explicitZero.sectionCount, 0);
  assert.equal(explicitZero.commandCount, 0);
  assert.equal(explicitZero.immediateCommandCount, 0);
  assert.equal(explicitZero.fallbackCommandCount, 0);
  assert.equal(explicitZero.proofCommandCount, 0);
  assert.equal(explicitZero.successSignalCount, 0);
  assert.equal(explicitZero.evidenceFieldCount, 0);
  assert.equal(explicitZero.forbiddenCommandCount, 0);
  const derivedCounts = operatorOnePageHandoffSnapshot({
    operatorOnePageHandoff: {
      ...handoff,
      sectionCount: 8,
      commandCount: 8,
      immediateCommandCount: undefined,
      fallbackCommandCount: undefined,
      proofCommandCount: undefined,
      successSignalCount: undefined,
      forbiddenCommandCount: undefined,
    },
  });
  assert.equal(derivedCounts.ready, true);
  assert.equal(derivedCounts.immediateCommandCount, 1);
  assert.equal(derivedCounts.fallbackCommandCount, 3);
  assert.equal(derivedCounts.proofCommandCount, 4);
  assert.equal(derivedCounts.successSignalCount, 8);
  assert.equal(derivedCounts.forbiddenCommandCount, 3);
  assert.match(source, /const immediateCommandCount = finiteNumberOr\(handoff\.immediateCommandCount, immediateCommands\.length\)/);
  assert.match(source, /const proofCommandCount = finiteNumberOr\(handoff\.proofCommandCount, proofCommands\.length\)/);
  assert.match(source, /const forbiddenCommandCount = finiteNumberOr\(handoff\.forbiddenCommandCount, forbiddenCommands\.length\)/);
  assert.equal(source.includes("Number(handoff.immediateCommandCount || immediateCommands.length || 0)"), false);
  assert.equal(source.includes("Number(handoff.proofCommandCount || proofCommands.length || 0)"), false);
  assert.equal(source.includes("Number(handoff.forbiddenCommandCount || forbiddenCommands.length || 0)"), false);
}

function testOutputQualityBlockerResolutionCountsPreserveExplicitZero() {
  const source = readFileSync(join(root, "scripts/capture-output-quality-audit.mjs"), "utf8");
  const blockerResolutionChecklistSnapshot = vm.runInNewContext([
    scriptFunctionSource("scripts/capture-output-quality-audit.mjs", "finiteNumberOr"),
    scriptFunctionSource("scripts/capture-output-quality-audit.mjs", "blockerResolutionChecklistSnapshot"),
    "blockerResolutionChecklistSnapshot;",
  ].join("\n"));
  const items = [
    { key: "operator_auth_path", status: "action_required", proofCommand: "node proof 1" },
    { key: "remote_workflow_file_parity", status: "action_required", proofCommand: "node proof 2" },
    { key: "workflow_visibility", status: "action_required", proofCommand: "node proof 3" },
    { key: "dispatch_guard", status: "pass", proofCommand: "node proof 4", stopCondition: "If safeToDispatch=false, keep dispatch withheld." },
    { key: "launch_proof_capture", status: "deferred_until_dispatch", proofCommand: "node proof 5" },
    { key: "external_completion_claim", status: "blocked", proofCommand: "node proof 6" },
  ];
  const checklist = {
    source: "generated_from_launch_execution_packet",
    status: "action_required",
    activeItemKey: "operator_auth_path",
    itemCount: 0,
    passCount: 0,
    actionRequiredCount: 0,
    deferredCount: 0,
    proofCommandCount: 0,
    guard: "Do not run gh workflow run until every action_required item has passed and verify-launch-handoff reports safeToDispatch=true.",
    items,
  };
  const explicitZero = blockerResolutionChecklistSnapshot({
    blockerResolutionChecklist: checklist,
  });
  assert.equal(explicitZero.ready, false);
  assert.equal(explicitZero.itemCount, 0);
  assert.equal(explicitZero.passCount, 0);
  assert.equal(explicitZero.actionRequiredCount, 0);
  assert.equal(explicitZero.deferredCount, 0);
  assert.equal(explicitZero.proofCommandCount, 0);
  const derivedCounts = blockerResolutionChecklistSnapshot({
    blockerResolutionChecklist: {
      ...checklist,
      itemCount: undefined,
      passCount: undefined,
      actionRequiredCount: undefined,
      deferredCount: undefined,
      proofCommandCount: undefined,
    },
  });
  assert.equal(derivedCounts.ready, true);
  assert.equal(derivedCounts.itemCount, 6);
  assert.equal(derivedCounts.passCount, 1);
  assert.equal(derivedCounts.actionRequiredCount, 3);
  assert.equal(derivedCounts.deferredCount, 1);
  assert.equal(derivedCounts.proofCommandCount, 6);
  assert.match(source, /const itemCount = finiteNumberOr\(checklist\.itemCount, items\.length\)/);
  assert.match(source, /const actionRequiredCount = finiteNumberOr\(checklist\.actionRequiredCount, items\.filter/);
  assert.match(source, /const proofCommandCount = finiteNumberOr\(checklist\.proofCommandCount, items\.filter/);
  assert.equal(source.includes("Number(checklist.itemCount || items.length || 0)"), false);
  assert.equal(source.includes("Number(checklist.actionRequiredCount || items.filter"), false);
  assert.equal(source.includes("Number(checklist.proofCommandCount || items.filter"), false);
}

function testOutputQualityLaunchProofEvidenceReceiptCountsPreserveExplicitZero() {
  const source = readFileSync(join(root, "scripts/capture-output-quality-audit.mjs"), "utf8");
  const launchProofEvidenceReceiptSnapshot = vm.runInNewContext([
    scriptFunctionSource("scripts/capture-output-quality-audit.mjs", "finiteNumberOr"),
    scriptFunctionSource("scripts/capture-output-quality-audit.mjs", "launchProofEvidenceReceiptSnapshot"),
    "launchProofEvidenceReceiptSnapshot;",
  ].join("\n"));
  const labels = ["Pages site proof", "Pages workflow run proof", "Drift Watch workflow run proof", "Evidence freshness proof", "Release receipt proof", "Public claim guard proof"];
  const fields = labels.map((label, index) => ({
    key: `proof_${index}`,
    label,
    nextAction: `capture ${label}`,
  }));
  const receipt = [
    "JooPark Launch Proof Evidence Receipt",
    "Evidence fields to fill:",
    ...labels,
    "Next proof actions:",
    "Stop condition: do not post public launch copy",
  ].join("\n");
  const explicitZero = launchProofEvidenceReceiptSnapshot({
    latestGate: {
      browserEvidence: {
        launchProofEvidenceFields: 6,
        launchProofEvidenceFieldCoverage: 1,
      },
    },
    publishEvidence: {
      launchProofEvidenceFieldCount: 0,
      launchProofEvidenceFieldCoverage: 0,
      launchProofEvidenceFields: fields,
      launchProofEvidenceReceipt: receipt,
    },
  });
  assert.equal(explicitZero.ready, false);
  assert.equal(explicitZero.fields, 0);
  assert.equal(explicitZero.coverage, 0);
  assert.equal(explicitZero.nextActionCount, 6);
  assert.equal(explicitZero.nextActionCoverage, 1);
  const derivedCounts = launchProofEvidenceReceiptSnapshot({
    latestGate: {
      browserEvidence: {
        launchProofEvidenceFields: 6,
        launchProofEvidenceFieldCoverage: 1,
      },
    },
    publishEvidence: {
      launchProofEvidenceFields: fields,
      launchProofEvidenceReceipt: receipt,
    },
  });
  assert.equal(derivedCounts.ready, true);
  assert.equal(derivedCounts.fields, 6);
  assert.equal(derivedCounts.coverage, 1);
  assert.match(source, /const fieldCount = finiteNumberOr\(\s+publishEvidence\?\.launchProofEvidenceFieldCount,/);
  assert.match(source, /finiteNumberOr\(evidence\.launchProofEvidenceFields, fields\.length\)/);
  assert.match(source, /const coverage = finiteNumberOr\(publishEvidence\?\.launchProofEvidenceFieldCoverage, evidence\.launchProofEvidenceFieldCoverage\)/);
  assert.equal(source.includes("Number(publishEvidence?.launchProofEvidenceFieldCount || evidence.launchProofEvidenceFields || fields.length || 0)"), false);
  assert.equal(source.includes("Number(publishEvidence?.launchProofEvidenceFieldCoverage || evidence.launchProofEvidenceFieldCoverage || 0)"), false);
}

function testOutputQualityPagesAttestationProofCountsPreserveExplicitZero() {
  const source = readFileSync(join(root, "scripts/capture-output-quality-audit.mjs"), "utf8");
  const pagesAttestationProofCaptureSnapshot = vm.runInNewContext([
    scriptFunctionSource("scripts/capture-output-quality-audit.mjs", "finiteNumberOr"),
    scriptFunctionSource("scripts/capture-output-quality-audit.mjs", "pagesAttestationProofCaptureSnapshot"),
    "pagesAttestationProofCaptureSnapshot;",
  ].join("\n"));
  const explicitZero = pagesAttestationProofCaptureSnapshot({
    proofCaptureReady: true,
    falsePositiveGuard: true,
    proofFieldCoverage: 0,
    requiredFieldCount: 0,
    completedFieldCount: 0,
    commandCount: 0,
    fields: Array.from({ length: 6 }, (_, index) => ({ key: `field_${index}` })),
  });
  assert.equal(explicitZero.ready, true);
  assert.equal(explicitZero.fieldCoverage, 0);
  assert.equal(explicitZero.requiredFieldCount, 0);
  assert.equal(explicitZero.completedFieldCount, 0);
  assert.equal(explicitZero.commandCount, 0);
  const derivedCounts = pagesAttestationProofCaptureSnapshot({
    proofCaptureReady: true,
    falsePositiveGuard: true,
    fields: Array.from({ length: 6 }, (_, index) => ({ key: `field_${index}` })),
  });
  assert.equal(derivedCounts.ready, true);
  assert.equal(derivedCounts.fieldCoverage, 1);
  assert.equal(derivedCounts.requiredFieldCount, 6);
  assert.equal(derivedCounts.completedFieldCount, 0);
  assert.equal(derivedCounts.commandCount, 4);
  assert.match(source, /const fieldCoverage = finiteNumberOr\(pagesAttestationProof\?\.proofFieldCoverage, ready \? 1 : 0\)/);
  assert.match(source, /const requiredFieldCount = finiteNumberOr\(pagesAttestationProof\?\.requiredFieldCount, ready \? 6 : 0\)/);
  assert.match(source, /const commandCount = finiteNumberOr\(pagesAttestationProof\?\.commandCount, ready \? 4 : 0\)/);
  assert.equal(source.includes("Number(pagesAttestationProof?.proofFieldCoverage || (ready ? 1 : 0))"), false);
  assert.equal(source.includes("Number(pagesAttestationProof?.requiredFieldCount || (ready ? 6 : 0))"), false);
  assert.equal(source.includes("Number(pagesAttestationProof?.commandCount || (ready ? 4 : 0))"), false);
}

function testOutputQualityHandoffVerifierArtifactCountsPreserveExplicitZero() {
  const source = readFileSync(join(root, "scripts/capture-output-quality-audit.mjs"), "utf8");
  const handoffVerifierArtifactSnapshot = vm.runInNewContext([
    "const launchHandoffVerificationRel = \"data/launch-handoff-verification.json\";",
    scriptFunctionSource("scripts/capture-output-quality-audit.mjs", "finiteNumberOr"),
    scriptFunctionSource("scripts/capture-output-quality-audit.mjs", "handoffVerifierArtifactSnapshot"),
    "handoffVerifierArtifactSnapshot;",
  ].join("\n"));
  const explicitZero = handoffVerifierArtifactSnapshot({
    status: "pass",
    safeToDispatch: false,
    verificationArtifact: {
      write: true,
      artifactCoverage: 0,
      jsonPath: "data/launch-handoff-verification.json",
      markdownPath: "data/launch-handoff-verification.md",
      dispatchGuard: "verification-only guard",
    },
    postInstallEvidenceIntake: {
      status: "ready",
      fieldCount: 0,
      completedFieldCount: 0,
      fields: Array.from({ length: 6 }, (_, index) => ({ key: `field_${index}` })),
      proofComplete: false,
    },
  });
  assert.equal(explicitZero.ready, false);
  assert.equal(explicitZero.artifactCoverage, 0);
  assert.equal(explicitZero.postInstallFields, 0);
  assert.equal(explicitZero.postInstallCompleted, 0);
  const derivedCounts = handoffVerifierArtifactSnapshot({
    status: "pass",
    safeToDispatch: false,
    verificationArtifact: {
      write: true,
      artifactCoverage: 2,
      jsonPath: "data/launch-handoff-verification.json",
      markdownPath: "data/launch-handoff-verification.md",
      dispatchGuard: "verification-only guard",
    },
    postInstallEvidenceIntake: {
      status: "ready",
      fields: Array.from({ length: 6 }, (_, index) => ({ key: `field_${index}` })),
      proofComplete: false,
    },
  });
  assert.equal(derivedCounts.ready, true);
  assert.equal(derivedCounts.artifactCoverage, 2);
  assert.equal(derivedCounts.postInstallFields, 6);
  assert.equal(derivedCounts.postInstallCompleted, 0);
  assert.match(source, /const artifactCoverage = finiteNumberOr\(artifact\.artifactCoverage, 0\)/);
  assert.match(source, /postInstallFields: finiteNumberOr\(postInstall\.fieldCount, Array\.isArray\(postInstall\.fields\) \? postInstall\.fields\.length : 0\)/);
  assert.match(source, /postInstallCompleted: finiteNumberOr\(postInstall\.completedFieldCount, 0\)/);
  assert.equal(source.includes("Number(artifact.artifactCoverage || 0)"), false);
  assert.equal(source.includes("Number(postInstall.fieldCount || (Array.isArray(postInstall.fields) ? postInstall.fields.length : 0))"), false);
  assert.equal(source.includes("Number(postInstall.completedFieldCount || 0)"), false);
}

function outputReadinessSnapshotUnitFunction() {
  return vm.runInNewContext([
    scriptFunctionSource("scripts/capture-output-quality-audit.mjs", "finiteNumberOr"),
    "function postInstallEvidenceIntakeSnapshot() { return { ready: false }; }",
    "function postInstallProofParserSourceReady() { return false; }",
    "function operatorOnePageHandoffSnapshot() { return { ready: false }; }",
    "function workflowUiInstallReceiptSnapshot() { return { ready: false }; }",
    "function launchProofEvidenceReceiptSnapshot() { return { ready: false }; }",
    "function pagesAttestationProofCaptureSnapshot() { return { ready: false }; }",
    "function handoffVerifierArtifactSnapshot() { return { ready: false }; }",
    "function mainBridgePlanSnapshot() { return { ready: false }; }",
    "function outputQualityExternalClaimGuardSourceReady() { return false; }",
    "function finalReadyForExternalClaim() { return false; }",
    "function gateReady() { return false; }",
    "function homeFirstRunGuidedStartSourceReady() { return false; }",
    "function globalHelpAccessSourceReady() { return false; }",
    "function topbarDataSafetySourceReady() { return false; }",
    "function routeDeepLinkSourceReady() { return false; }",
    "function publishEvidenceActionCommand(action) { return action?.command || \"\"; }",
    "function publishEvidenceActionStatus(action) { return action?.status || \"\"; }",
    "function blockerResolutionChecklistSnapshot() { return { ready: false }; }",
    "function launchInstallPathSnapshot() { return { ready: false }; }",
    "function remoteWorkflowFileAcceptanceLedgerSnapshot() { return { ready: false }; }",
    "function launchProofAcceptanceLedgerSnapshot() { return { ready: false }; }",
    "function workflowAuthPreflightSnapshot() { return { ready: false }; }",
    "function launchPostAuthCheckpointSnapshot() { return { ready: false }; }",
    scriptFunctionSource("scripts/capture-output-quality-audit.mjs", "outputReadinessSnapshot"),
    "outputReadinessSnapshot;",
  ].join("\n"));
}

function testOutputQualityPostInstallProofParserCountsPreserveExplicitZero() {
  const source = readFileSync(join(root, "scripts/capture-output-quality-audit.mjs"), "utf8");
  const outputReadinessSnapshot = outputReadinessSnapshotUnitFunction();
  const explicitZero = outputReadinessSnapshot({
    latestGate: {
      browserEvidence: {
        postInstallProofParser: true,
        postInstallProofParserFalsePositiveGuard: true,
        postInstallProofParserFields: 0,
        postInstallProofParserCoverage: 0,
        postInstallProofParserDetectedFields: 0,
      },
    },
  }).postInstallProofParser;
  assert.equal(explicitZero.ready, true);
  assert.equal(explicitZero.fields, 0);
  assert.equal(explicitZero.coverage, 0);
  assert.equal(explicitZero.detectedFields, 0);
  assert.equal(explicitZero.status, "waiting_for_pasted_proof");
  const derivedCounts = outputReadinessSnapshot({
    latestGate: {
      browserEvidence: {
        postInstallProofParser: true,
        postInstallProofParserFalsePositiveGuard: true,
      },
    },
  }).postInstallProofParser;
  assert.equal(derivedCounts.ready, true);
  assert.equal(derivedCounts.fields, 6);
  assert.equal(derivedCounts.coverage, 1);
  assert.equal(derivedCounts.detectedFields, 0);
  assert.match(source, /const postInstallProofParserDetectedFields = finiteNumberOr\(evidence\.postInstallProofParserDetectedFields, 0\)/);
  assert.match(source, /fields: finiteNumberOr\(evidence\.postInstallProofParserFields, postInstallProofParserReady \? 6 : 0\)/);
  assert.match(source, /coverage: finiteNumberOr\(evidence\.postInstallProofParserCoverage, postInstallProofParserReady \? 1 : 0\)/);
  assert.equal(source.includes("Number(evidence.postInstallProofParserFields || (postInstallProofParserReady ? 6 : 0))"), false);
  assert.equal(source.includes("Number(evidence.postInstallProofParserCoverage || (postInstallProofParserReady ? 1 : 0))"), false);
  assert.equal(source.includes("Number(evidence.postInstallProofParserDetectedFields || 0)"), false);
}

function testOutputQualityLaunchExecutionPacketCountsPreserveExplicitZero() {
  const source = readFileSync(join(root, "scripts/capture-output-quality-audit.mjs"), "utf8");
  const outputReadinessSnapshot = outputReadinessSnapshotUnitFunction();
  const explicitZero = outputReadinessSnapshot({
    latestGate: { browserEvidence: { launchExecutionPacketStages: 5, launchExecutionPacketCommands: 16 } },
    launchExecutionPacket: { packet: true, stageCount: 0, commandCount: 0 },
  });
  assert.equal(explicitZero.copyReadyArtifacts.launchExecutionPacket, true);
  assert.equal(explicitZero.launchExecutionPacketStages, 0);
  assert.equal(explicitZero.launchExecutionPacketCommands, 0);
  const derivedCounts = outputReadinessSnapshot({
    latestGate: { browserEvidence: { launchExecutionPacketStages: 5, launchExecutionPacketCommands: 16 } },
    launchExecutionPacket: { packet: true },
  });
  assert.equal(derivedCounts.copyReadyArtifacts.launchExecutionPacket, true);
  assert.equal(derivedCounts.launchExecutionPacketStages, 5);
  assert.equal(derivedCounts.launchExecutionPacketCommands, 16);
  assert.match(source, /const launchExecutionPacketStageCount = finiteNumberOr\(launchExecutionPacket\?\.stageCount, evidence\.launchExecutionPacketStages\)/);
  assert.match(source, /const launchExecutionPacketCommandCount = finiteNumberOr\(launchExecutionPacket\?\.commandCount, evidence\.launchExecutionPacketCommands\)/);
  assert.equal(source.includes("Number(launchExecutionPacket?.stageCount || evidence.launchExecutionPacketStages || 0)"), false);
  assert.equal(source.includes("Number(launchExecutionPacket?.commandCount || evidence.launchExecutionPacketCommands || 0)"), false);
}

function testOutputQualityAccessSurfaceCountsPreserveExplicitZero() {
  const source = readFileSync(join(root, "scripts/capture-output-quality-audit.mjs"), "utf8");
  const outputReadinessSnapshot = outputReadinessSnapshotUnitFunction();
  const explicitZero = outputReadinessSnapshot({
    latestGate: {
      browserEvidence: {
        homeFirstRunGuidedStart: true,
        homeFirstRunGuidedStartItems: 0,
        homeFirstRunGuidedStartCoverage: 0,
        globalHelpAccess: true,
        globalHelpAccessActions: 0,
        globalHelpAccessCoverage: 0,
        topbarDataSafety: true,
        topbarDataSafetyActions: 0,
        topbarDataSafetyCoverage: 0,
        routeDeepLink: true,
        routeDeepLinkCoverage: 0,
      },
    },
  });
  assert.equal(explicitZero.firstRunGuidedStart.ready, true);
  assert.equal(explicitZero.firstRunGuidedStart.items, 0);
  assert.equal(explicitZero.firstRunGuidedStart.coverage, 0);
  assert.equal(explicitZero.globalHelpAccess.ready, true);
  assert.equal(explicitZero.globalHelpAccess.actions, 0);
  assert.equal(explicitZero.globalHelpAccess.coverage, 0);
  assert.equal(explicitZero.topbarDataSafety.ready, true);
  assert.equal(explicitZero.topbarDataSafety.actions, 0);
  assert.equal(explicitZero.topbarDataSafety.coverage, 0);
  assert.equal(explicitZero.routeDeepLink.ready, true);
  assert.equal(explicitZero.routeDeepLink.coverage, 0);
  const derivedCounts = outputReadinessSnapshot({
    latestGate: {
      browserEvidence: {
        homeFirstRunGuidedStart: true,
        globalHelpAccess: true,
        topbarDataSafety: true,
        routeDeepLink: true,
      },
    },
  });
  assert.equal(derivedCounts.firstRunGuidedStart.items, 3);
  assert.equal(derivedCounts.firstRunGuidedStart.coverage, 1);
  assert.equal(derivedCounts.globalHelpAccess.actions, 4);
  assert.equal(derivedCounts.globalHelpAccess.coverage, 1);
  assert.equal(derivedCounts.topbarDataSafety.actions, 4);
  assert.equal(derivedCounts.topbarDataSafety.coverage, 1);
  assert.equal(derivedCounts.routeDeepLink.coverage, 1);
  assert.match(source, /items: finiteNumberOr\(evidence\.homeFirstRunGuidedStartItems, firstRunGuidedStartReady \? 3 : 0\)/);
  assert.match(source, /actions: finiteNumberOr\(evidence\.globalHelpAccessActions, globalHelpAccessReady \? 4 : 0\)/);
  assert.match(source, /actions: finiteNumberOr\(evidence\.topbarDataSafetyActions, topbarDataSafetyReady \? 4 : 0\)/);
  assert.match(source, /coverage: finiteNumberOr\(evidence\.routeDeepLinkCoverage, routeDeepLinkReady \? 1 : 0\)/);
  assert.equal(source.includes("Number(evidence.homeFirstRunGuidedStartItems || (firstRunGuidedStartReady ? 3 : 0))"), false);
  assert.equal(source.includes("Number(evidence.globalHelpAccessActions || (globalHelpAccessReady ? 4 : 0))"), false);
  assert.equal(source.includes("Number(evidence.topbarDataSafetyActions || (topbarDataSafetyReady ? 4 : 0))"), false);
  assert.equal(source.includes("Number(evidence.routeDeepLinkCoverage || (routeDeepLinkReady ? 1 : 0))"), false);
}

function testOutputQualityPublishEvidenceCommandGuardCoveragePreserveExplicitZero() {
  const source = readFileSync(join(root, "scripts/capture-output-quality-audit.mjs"), "utf8");
  const outputReadinessSnapshot = outputReadinessSnapshotUnitFunction();
  const explicitZero = outputReadinessSnapshot({
    latestGate: {
      browserEvidence: {
        publishEvidenceSafeSuggestedCommands: true,
        publishEvidenceSuggestedVerificationCommands: 7,
        publishEvidenceSuggestedDispatchCommands: 0,
        publishEvidenceWithheldDispatchCommands: 2,
        publishEvidenceWithheldDispatchCoverage: 0,
      },
    },
  }).publishEvidenceCommandGuard;
  assert.equal(explicitZero.ready, true);
  assert.equal(explicitZero.coverage, 0);
  assert.equal(explicitZero.suggestedDispatchCommands, 0);
  assert.equal(explicitZero.withheldDispatchCommands, 2);
  const derivedCoverage = outputReadinessSnapshot({
    latestGate: {
      browserEvidence: {
        publishEvidenceSafeSuggestedCommands: true,
        publishEvidenceSuggestedVerificationCommands: 7,
        publishEvidenceSuggestedDispatchCommands: 0,
        publishEvidenceWithheldDispatchCommands: 2,
      },
    },
  }).publishEvidenceCommandGuard;
  assert.equal(derivedCoverage.ready, true);
  assert.equal(derivedCoverage.coverage, 1);
  assert.match(source, /coverage: finiteNumberOr\(evidence\.publishEvidenceWithheldDispatchCoverage, \(preDispatchCommandGuardReady \|\| postProofCommandGuardReady\) \? 1 : 0\)/);
  assert.equal(source.includes("Number(evidence.publishEvidenceWithheldDispatchCoverage || ((preDispatchCommandGuardReady || postProofCommandGuardReady) ? 1 : 0))"), false);
}

function testOutputQualityWorkflowAuthPreflightFieldsPreserveExplicitZero() {
  const source = readFileSync(join(root, "scripts/capture-output-quality-audit.mjs"), "utf8");
  const workflowAuthPreflightSnapshot = vm.runInNewContext([
    scriptFunctionSource("scripts/capture-output-quality-audit.mjs", "finiteNumberOr"),
    scriptFunctionSource("scripts/capture-output-quality-audit.mjs", "workflowAuthPreflightSnapshot"),
    "workflowAuthPreflightSnapshot;",
  ].join("\n"));
  const publishDispatchPlan = {
    workflowScope: { scopes: ["repo", "workflow"], source: "gh_auth_status" },
    workflowScopeChecked: true,
    workflowScopeAvailable: true,
    workflowScopeInstallBlocked: false,
    workflowScopeRefreshCommand: "gh auth refresh -h github.com -s workflow",
    nextVerificationCommand: "node scripts/check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write",
  };
  const explicitZero = workflowAuthPreflightSnapshot({
    latestGate: {
      browserEvidence: {
        publishDispatchAuthPreflight: true,
        systemStatusWorkflowAuthPreflightFields: 0,
      },
    },
    publishDispatchPlan,
  });
  assert.equal(explicitZero.uiVerified, true);
  assert.equal(explicitZero.fieldCoverage, 0);
  assert.equal(explicitZero.ready, false);
  const derivedCoverage = workflowAuthPreflightSnapshot({
    latestGate: {
      browserEvidence: {
        publishDispatchAuthPreflight: true,
      },
    },
    publishDispatchPlan,
  });
  assert.equal(derivedCoverage.fieldCoverage, 1);
  assert.equal(derivedCoverage.ready, true);
  assert.match(source, /const fieldCoverage = finiteNumberOr\(evidence\.systemStatusWorkflowAuthPreflightFields, uiVerified \? 1 : 0\)/);
  assert.equal(source.includes("Number(evidence.systemStatusWorkflowAuthPreflightFields || (uiVerified ? 1 : 0))"), false);
}

function testOutputQualityPreviousEvidenceAccessSurfaceCountsPreserveExplicitZero() {
  const source = readFileSync(join(root, "scripts/capture-output-quality-audit.mjs"), "utf8");
  const previousOutputQualityBrowserEvidence = vm.runInNewContext([
    scriptFunctionSource("scripts/capture-output-quality-audit.mjs", "isoAgeHours"),
    scriptFunctionSource("scripts/capture-output-quality-audit.mjs", "finiteNumberOr"),
    scriptFunctionSource("scripts/capture-output-quality-audit.mjs", "gateReady"),
    "function completeBrowserEvidence() { return true; }",
    "function outputQualityExternalClaimGuardSourceReady() { return true; }",
    "function gateReady() { return true; }",
    "function globalHelpAccessSourceReady() { return true; }",
    "function topbarDataSafetySourceReady() { return true; }",
    "function routeDeepLinkSourceReady() { return true; }",
    "function homeFirstRunGuidedStartSourceReady() { return true; }",
    scriptFunctionSource("scripts/capture-output-quality-audit.mjs", "previousOutputQualityBrowserEvidence"),
    "previousOutputQualityBrowserEvidence;",
  ].join("\n"));
  const base = {
    generatedAt: "2026-06-10T00:00:00.000Z",
    status: "pass",
    artifactQualityRubric: { status: "pass", items: Array.from({ length: 5 }, (_, index) => ({ key: `rubric_${index}` })) },
    externalComparison: Array.from({ length: 4 }, (_, index) => ({ key: `comparison_${index}` })),
    outputReadinessSnapshot: { status: "pass", copyReadyArtifacts: {} },
  };
  const explicitZero = previousOutputQualityBrowserEvidence({
    ...base,
    latestGate: {
      browserEvidence: {
        globalHelpAccess: true,
        outputQualityExternalComparison: true,
        outputQualityExternalComparisonSources: 0,
        reviewPackageArtifactQualityRubric: true,
        reviewPackageArtifactQualityItems: 0,
        globalHelpAccessActions: 0,
        globalHelpAccessCoverage: 0,
        topbarDataSafety: true,
        topbarDataSafetyActions: 0,
        topbarDataSafetyCoverage: 0,
        routeDeepLink: true,
        routeDeepLinkCoverage: 0,
        homeFirstRunGuidedStart: true,
        homeFirstRunGuidedStartItems: 0,
        homeFirstRunGuidedStartCoverage: 0,
      },
    },
  }, Date.parse("2026-06-10T01:00:00.000Z")).browserEvidence;
  assert.equal(explicitZero.outputQualityExternalComparisonSources, 0);
  assert.equal(explicitZero.reviewPackageArtifactQualityItems, 0);
  assert.equal(explicitZero.globalHelpAccessActions, 0);
  assert.equal(explicitZero.globalHelpAccessCoverage, 0);
  assert.equal(explicitZero.topbarDataSafetyActions, 0);
  assert.equal(explicitZero.topbarDataSafetyCoverage, 0);
  assert.equal(explicitZero.routeDeepLinkCoverage, 0);
  assert.equal(explicitZero.homeFirstRunGuidedStartItems, 0);
  assert.equal(explicitZero.homeFirstRunGuidedStartCoverage, 0);
  const derivedCounts = previousOutputQualityBrowserEvidence({
    ...base,
    latestGate: {
      browserEvidence: {
        globalHelpAccess: true,
        outputQualityExternalComparison: true,
        reviewPackageArtifactQualityRubric: true,
        topbarDataSafety: true,
        routeDeepLink: true,
        homeFirstRunGuidedStart: true,
      },
    },
  }, Date.parse("2026-06-10T01:00:00.000Z")).browserEvidence;
  assert.equal(derivedCounts.outputQualityExternalComparisonSources, 4);
  assert.equal(derivedCounts.reviewPackageArtifactQualityItems, 5);
  assert.equal(derivedCounts.globalHelpAccessActions, 4);
  assert.equal(derivedCounts.globalHelpAccessCoverage, 1);
  assert.equal(derivedCounts.topbarDataSafetyActions, 4);
  assert.equal(derivedCounts.topbarDataSafetyCoverage, 1);
  assert.equal(derivedCounts.routeDeepLinkCoverage, 1);
  assert.equal(derivedCounts.homeFirstRunGuidedStartItems, 3);
  assert.equal(derivedCounts.homeFirstRunGuidedStartCoverage, 1);
  assert.match(source, /globalHelpAccessActions: finiteNumberOr\(sourceBackedEvidence\.globalHelpAccessActions, finiteNumberOr\(snapshot\.globalHelpAccess\?\.actions,/);
  assert.match(source, /outputQualityExternalComparisonSources: finiteNumberOr\(sourceBackedEvidence\.outputQualityExternalComparisonSources, comparisons\.length\)/);
  assert.match(source, /reviewPackageArtifactQualityItems: finiteNumberOr\(sourceBackedEvidence\.reviewPackageArtifactQualityItems, Array\.isArray\(artifactRubric\.items\) \? artifactRubric\.items\.length : 0\)/);
  assert.match(source, /topbarDataSafetyActions: finiteNumberOr\(sourceBackedEvidence\.topbarDataSafetyActions, finiteNumberOr\(snapshot\.topbarDataSafety\?\.actions,/);
  assert.match(source, /routeDeepLinkCoverage: finiteNumberOr\(sourceBackedEvidence\.routeDeepLinkCoverage, finiteNumberOr\(snapshot\.routeDeepLink\?\.coverage,/);
  assert.match(source, /homeFirstRunGuidedStartItems: finiteNumberOr\(sourceBackedEvidence\.homeFirstRunGuidedStartItems, finiteNumberOr\(snapshot\.firstRunGuidedStart\?\.items,/);
  assert.equal(source.includes("Math.max(\n      Number(sourceBackedEvidence.globalHelpAccessActions || 0)"), false);
  assert.equal(source.includes("Math.max(\n      Number(sourceBackedEvidence.topbarDataSafetyActions || 0)"), false);
  assert.equal(source.includes("Math.max(\n      Number(sourceBackedEvidence.routeDeepLinkCoverage || 0)"), false);
  assert.equal(source.includes("Math.max(\n      Number(sourceBackedEvidence.homeFirstRunGuidedStartItems || 0)"), false);
  assert.equal(source.includes("Math.max(\n      Number(sourceBackedEvidence.outputQualityExternalComparisonSources || 0)"), false);
  assert.equal(source.includes("Math.max(\n      Number(sourceBackedEvidence.reviewPackageArtifactQualityItems || 0)"), false);
}

function testHomeLaunchActionCountsPreserveExplicitZero() {
  const source = readFileSync(join(root, "home-view.js"), "utf8");
  assert.match(source, /function firstClampedCount\(values, fallback = 0\)/);
  assert.match(source, /const currentLaunchActionCommandCount = firstClampedCount\(\[/);
  assert.match(source, /currentLaunchAction\?\.commandCount,\s+outputImmediateAction\?\.commandCount,\s+currentLaunchActionCommand \? 1 : 0,/);
  assert.match(source, /const currentLaunchWithheldCount = firstClampedCount\(\[/);
  assert.match(source, /currentLaunchAction\?\.withheldCommandCount,\s+outputImmediateAction\?\.withheldCommandCount,\s+outputAudit\?\.outputReadinessSnapshot\?\.publishEvidenceCommandGuard\?\.withheldDispatchCommands,/);
  assert.equal(source.includes("currentLaunchAction?.commandCount || outputImmediateAction?.commandCount || (currentLaunchActionCommand ? 1 : 0)"), false);
  assert.equal(source.includes("currentLaunchAction?.withheldCommandCount || outputImmediateAction?.withheldCommandCount || outputAudit?.outputReadinessSnapshot?.publishEvidenceCommandGuard?.withheldDispatchCommands || 0"), false);
}

function testHomeLaunchInstallMatrixCountsPreserveExplicitZero() {
  const source = readFileSync(join(root, "home-view.js"), "utf8");
  assert.match(source, /const launchInstallMatrixPathCount = firstClampedCount\(\[launchInstallMatrix\.installPathCount, launchInstallMatrixRows\.length\]\)/);
  assert.match(source, /const launchInstallMatrixSignalCount = firstClampedCount\(\[launchInstallMatrix\.requiredSignalCount, launchInstallMatrixSignals\.length\]\)/);
  assert.match(source, /data-home-launch-install-matrix-path-count="\$\{launchInstallMatrixPathCount\}"/);
  assert.match(source, /data-home-launch-install-matrix-signal-count="\$\{launchInstallMatrixSignalCount\}"/);
  assert.match(source, /\$\{launchInstallMatrixPathCount\} paths ->/);
  assert.match(source, /\$\{launchInstallMatrixSignalCount\} signals · remoteWorkflowFilesReady=true/);
  assert.equal(source.includes("launchInstallMatrix.installPathCount || launchInstallMatrixRows.length"), false);
  assert.equal(source.includes("launchInstallMatrix.requiredSignalCount || launchInstallMatrixSignals.length"), false);
}

function testLaunchClaimReadinessRequiresBothArtifacts() {
  const homeSource = readFileSync(join(root, "home-view.js"), "utf8");
  const appSource = readFileSync(join(root, "app.js"), "utf8");
  assert.match(homeSource, /const safeToDispatch = launchExecution\?\.readyToDispatch === true && outputAudit\?\.dispatchState\?\.allDispatchReady === true/);
  assert.match(homeSource, /const externalClaimReady = launchExecution\?\.readyForExternalClaim === true && outputAudit\?\.readyForExternalClaim === true/);
  assert.match(homeSource, /const currentLaunchAction = externalClaimReady/);
  assert.equal(homeSource.includes("launchExecution?.readyForExternalClaim || outputAudit?.readyForExternalClaim"), false);
  assert.equal(homeSource.includes("launchExecution?.readyToDispatch || outputAudit?.dispatchState?.allDispatchReady"), false);
  assert.match(appSource, /const readyForExternalClaim = launchRefresh\.readyForExternalClaim === true && launchExecution\.readyForExternalClaim === true/);
  assert.match(appSource, /const safeToDispatch = launchRefresh\.safeToDispatch === true && \(launchExecution\.safeToDispatch === true \|\| launchExecution\.readyToDispatch === true\)/);
  assert.equal(appSource.includes("launchRefresh.readyForExternalClaim || launchExecution.readyForExternalClaim"), false);
  assert.equal(appSource.includes("launchRefresh.safeToDispatch || launchExecution.safeToDispatch"), false);
}

function testHomeRemoteWorkflowLedgerCountsPreserveExplicitZero() {
  const source = readFileSync(join(root, "home-view.js"), "utf8");
  assert.match(source, /const remoteWorkflowFileLedgerFileCount = firstClampedCount\(\[remoteWorkflowFileLedger\.fileCount, remoteWorkflowFileLedgerItems\.length\]\)/);
  assert.match(source, /const remoteWorkflowFileLedgerReadyCount = firstClampedCount\(\[remoteWorkflowFileLedger\.readyCount\]\)/);
  assert.match(source, /remoteWorkflowFileLedgerReadyCount === remoteWorkflowFileLedgerFileCount/);
  assert.match(source, /data-home-remote-workflow-file-ledger-file-count="\$\{remoteWorkflowFileLedgerFileCount\}"/);
  assert.match(source, /`\$\{remoteWorkflowFileLedgerReadyCount\}\/\$\{remoteWorkflowFileLedgerFileCount\} files ready; missing=\$\{remoteWorkflowFileLedgerMissingCount\}; mismatch=\$\{remoteWorkflowFileLedgerMismatchCount\}`/);
  assert.equal(source.includes("remoteWorkflowFileLedger.fileCount || remoteWorkflowFileLedgerItems.length"), false);
  assert.equal(source.includes("remoteWorkflowFileLedger.readyCount || 0"), false);
  assert.equal(source.includes("remoteWorkflowFileLedger.missingCount || 0"), false);
  assert.equal(source.includes("remoteWorkflowFileLedger.mismatchCount || 0"), false);
}

function testHomeLaunchProofLedgerCountsPreserveExplicitZero() {
  const source = readFileSync(join(root, "home-view.js"), "utf8");
  assert.match(source, /const launchProofLedgerRequiredCount = firstClampedCount\(\[launchProofLedger\.requiredProofCount, launchProofLedgerItems\.length\]\)/);
  assert.match(source, /const launchProofLedgerReadyCount = firstClampedCount\(\[launchProofLedger\.readyProofCount\]\)/);
  assert.match(source, /const launchProofLedgerPendingCount = firstClampedCount\(/);
  assert.match(source, /launchProofLedgerPendingCount === 0/);
  assert.match(source, /pending=\$\{launchProofLedgerPendingCount\}/);
  assert.match(source, /data-home-launch-proof-ledger-required-count="\$\{launchProofLedgerRequiredTotal\}"/);
  assert.equal(source.includes("launchProofLedger.requiredProofCount || launchProofLedgerItems.length"), false);
  assert.equal(source.includes("launchProofLedger.readyProofCount || 0"), false);
  assert.equal(source.includes("launchProofLedger.pendingProofCount || 0"), false);
}

function testHomeLaunchBlockerResolverCountsPreserveExplicitZero() {
  const source = readFileSync(join(root, "home-view.js"), "utf8");
  assert.match(source, /const launchBlockerItemCount = firstClampedCount\(\[launchBlockerResolution\.itemCount, launchBlockerItems\.length\]\)/);
  assert.match(source, /const launchBlockerPassCount = firstClampedCount\(\[launchBlockerResolution\.passCount\]\)/);
  assert.match(source, /const launchBlockerActionRequiredCount = firstClampedCount\(\[launchBlockerResolution\.actionRequiredCount\]\)/);
  assert.match(source, /const launchBlockerDeferredCount = firstClampedCount\(\[launchBlockerResolution\.deferredCount\]\)/);
  assert.match(source, /const launchBlockerProofCommandCount = firstClampedCount\(\[launchBlockerResolution\.proofCommandCount, launchBlockerProofCommands\.length\]\)/);
  assert.match(source, /data-home-launch-blocker-resolver-item-count="\$\{launchBlockerItemCount\}"/);
  assert.match(source, /data-home-launch-blocker-resolver-proof-command-count="\$\{launchBlockerProofCommandCount\}"/);
  assert.match(source, /items=\$\{launchBlockerItemCount\}; pass=\$\{launchBlockerPassCount\}; actionRequired=\$\{launchBlockerActionRequiredCount\}; deferred=\$\{launchBlockerDeferredCount\}; proofCommands=\$\{launchBlockerProofCommandCount\}/);
  assert.equal(source.includes("launchBlockerResolution.itemCount || launchBlockerItems.length"), false);
  assert.equal(source.includes("launchBlockerResolution.passCount || 0"), false);
  assert.equal(source.includes("launchBlockerResolution.actionRequiredCount || 0"), false);
  assert.equal(source.includes("launchBlockerResolution.deferredCount || 0"), false);
  assert.equal(source.includes("launchBlockerResolution.proofCommandCount || launchBlockerProofCommands.length"), false);
}

function testHomePostInstallQuickProofCountsPreserveExplicitZero() {
  const source = readFileSync(join(root, "home-view.js"), "utf8");
  assert.match(source, /const postInstallQuickProofStepCount = firstClampedCount\(\[postInstallEvidenceIntake\.quickProofStepCount, postInstallQuickProofSteps\.length\]\)/);
  assert.match(source, /const postInstallQuickProofCoverage = firstClampedCount\(\[/);
  assert.match(source, /postInstallEvidenceIntake\.quickProofCoverage,/);
  assert.match(source, /postInstallQuickProofStepCount === 4/);
  assert.match(source, /const postInstallQuickProofMappedFieldCount = firstClampedCount\(\[postInstallEvidenceIntake\.quickProofMappedFieldCount, postInstallQuickProofFieldMappings\.length\]\)/);
  assert.match(source, /const postInstallQuickProofCompletedMappedFieldCount = firstClampedCount\(\[/);
  assert.match(source, /postInstallEvidenceIntake\.quickProofCompletedMappedFieldCount,/);
  assert.match(source, /const postInstallQuickProofFieldMappingCoverage = firstClampedCount\(\[/);
  assert.match(source, /postInstallEvidenceIntake\.quickProofFieldMappingCoverage,/);
  assert.match(source, /data-post-install-quick-proof-step-count="\$\{postInstallQuickProofStepCount\}"/);
  assert.match(source, /data-post-install-quick-proof-mapped-field-count="\$\{postInstallQuickProofMappedFieldCount\}"/);
  assert.match(source, /Quick proof: ready=\$\{postInstallQuickProofReady\}; steps=\$\{postInstallQuickProofStepCount\}; coverage=\$\{postInstallQuickProofCoverage\}/);
  assert.match(source, /Quick proof field mapping: ready=\$\{postInstallQuickProofFieldMappingReady\}; mapped=\$\{postInstallQuickProofMappedFieldCount\}; completed=\$\{postInstallQuickProofCompletedMappedFieldCount\}\/\$\{postInstallQuickProofMappedFieldCount\}; coverage=\$\{postInstallQuickProofFieldMappingCoverage\}/);
  assert.equal(source.includes("Number(postInstallEvidenceIntake.quickProofStepCount || postInstallQuickProofSteps.length || 0)"), false);
  assert.equal(source.includes("Number(postInstallEvidenceIntake.quickProofCoverage || (postInstallQuickProofStepCount === 4"), false);
  assert.equal(source.includes("Number(postInstallEvidenceIntake.quickProofMappedFieldCount || postInstallQuickProofFieldMappings.length || 0)"), false);
  assert.equal(source.includes("Number(postInstallEvidenceIntake.quickProofCompletedMappedFieldCount || postInstallQuickProofFieldMappings.filter"), false);
  assert.equal(source.includes("Number(postInstallEvidenceIntake.quickProofFieldMappingCoverage || (postInstallQuickProofMappedFieldCount === 4"), false);
}

function testHomeExternalClaimGuardCountsPreserveExplicitZero() {
  const source = readFileSync(join(root, "home-view.js"), "utf8");
  assert.match(source, /const externalClaimGuardRequirementCount = firstClampedCount\(\[externalClaimGuard\.requirementCount, externalClaimGuardRequirements\.length\]\)/);
  assert.match(source, /const externalClaimGuardBlockedCount = firstClampedCount\(\[externalClaimGuard\.blockedCount\]\)/);
  assert.match(source, /data-home-external-claim-guard-blocked-count="\$\{externalClaimGuardBlockedCount\}"/);
  assert.match(source, /data-home-external-claim-guard-requirement-count="\$\{externalClaimGuardRequirementCount\}"/);
  assert.match(source, /blocked \$\{externalClaimGuardBlockedCount\}\/\$\{externalClaimGuardRequirementCount\}/);
  assert.equal(source.includes("Number(externalClaimGuard.requirementCount || externalClaimGuardRequirements.length || 0)"), false);
  assert.equal(source.includes("Number(externalClaimGuard.blockedCount || 0)"), false);
  assert.equal(source.includes("externalClaimGuard.requirementCount || externalClaimGuardRequirements.length"), false);
  assert.equal(source.includes("externalClaimGuard.blockedCount || 0"), false);
}

function testReleaseStatusWorkflowUiInstallCoveragePreservesExplicitZero() {
  const source = readFileSync(join(root, "release-status.js"), "utf8");
  assert.match(source, /function finiteNumberOr\(value, fallback\)/);
  assert.match(source, /const pastePacketCoverage = finiteNumberOr\(data\?\.workflowUiInstallPastePacketCoverage, pastePacketReady \? 1 : 0\)/);
  assert.match(source, /const formFieldCoverage = finiteNumberOr\(data\?\.workflowUiInstallFormFieldCoverage, finiteNumberOr\(installReceipt\.formFieldCoverage, 0\)\)/);
  assert.equal(source.includes("Number(data?.workflowUiInstallPastePacketCoverage || (pastePacketReady ? 1 : 0))"), false);
  assert.equal(source.includes("Number(data?.workflowUiInstallFormFieldCoverage || installReceipt.formFieldCoverage || 0)"), false);
}

function testReleaseStatusExternalClaimGuardCountsPreserveExplicitZero() {
  const source = readFileSync(join(root, "release-status.js"), "utf8");
  assert.match(source, /const externalClaimGuardBlockedCount = finiteNumberOr\(externalClaimGuard\.blockedCount, 0\)/);
  assert.match(source, /const externalClaimGuardRequirementCount = finiteNumberOr\(externalClaimGuard\.requirementCount, externalClaimGuardRequirements\.length\)/);
  assert.match(source, /data-output-quality-audit-external-claim-guard-blocked-count="\$\{externalClaimGuardBlockedCount\}"/);
  assert.match(source, /data-output-quality-audit-external-claim-guard-requirement-count="\$\{externalClaimGuardRequirementCount\}"/);
  assert.match(source, /blocked \$\{externalClaimGuardBlockedCount\}\/\$\{externalClaimGuardRequirementCount\}/);
  assert.equal(source.includes("externalClaimGuard.blockedCount || 0"), false);
  assert.equal(source.includes("externalClaimGuard.requirementCount || externalClaimGuardRequirements.length"), false);
}

function testReleaseStatusLaunchReadinessFreshnessCountsPreserveExplicitZero() {
  const source = readFileSync(join(root, "release-status.js"), "utf8");
  const runtime = loadRuntime("release-status.js");
  const releaseStatus = runtime.JooParkReleaseStatus.create({
    html,
    raw,
    dateNow: () => Date.parse("2026-06-10T01:00:00.000Z"),
    formatLocalDateTime: (value) => String(value),
  });
  const attr = (markup, name) => {
    const match = markup.match(new RegExp(`${name}="([^"]*)"`));
    assert.ok(match, `${name} attribute missing`);
    return match[1];
  };
  const markup = releaseStatus.launchReadinessRefreshHTML({
    loaded: true,
    data: {
      status: "pass",
      generatedAt: "2026-06-10T00:00:00.000Z",
      evidenceFreshness: {
        generatedAt: "2026-06-10T00:00:00.000Z",
        sourceArtifactCount: 0,
        sourceArtifacts: ["data/launch-execution-packet.json", "data/output-quality-audit.json"],
      },
    },
  });
  assert.equal(attr(markup, "data-launch-readiness-refresh-source-artifact-count"), "0");
  assert.match(markup, /sourceArtifactCount: 0/);
  assert.doesNotMatch(markup, /sourceArtifactCount: 2/);
  assert.match(source, /sourceArtifactCount: finiteNumberOr\(freshness\.sourceArtifactCount, sourceArtifacts\.length\)/);
  assert.equal(source.includes("sourceArtifactCount: Number(freshness.sourceArtifactCount || sourceArtifacts.length || 0)"), false);
}

function testReleaseStatusPostAuthCheckpointCountsPreserveExplicitZero() {
  const source = readFileSync(join(root, "release-status.js"), "utf8");
  const runtime = loadRuntime("release-status.js");
  const releaseStatus = runtime.JooParkReleaseStatus.create({
    html,
    raw,
    dateNow: () => Date.parse("2026-06-10T00:00:00.000Z"),
    formatLocalDateTime: (value) => String(value),
  });
  const attr = (markup, name) => {
    const match = markup.match(new RegExp(`${name}="([^"]*)"`));
    assert.ok(match, `${name} attribute missing`);
    return match[1];
  };
  const recheckSequence = [
    { key: "confirm_scope", label: "Confirm scope", command: "gh auth status -h github.com" },
    { key: "install_workflows", label: "Install workflows", command: "node scripts/install-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write --verify" },
    { key: "verify_remote_parity", label: "Verify remote parity", command: "node scripts/check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write" },
    { key: "verify_actions_visibility", label: "Verify actions visibility", command: "node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects" },
    { key: "verify_handoff_guard", label: "Verify handoff guard", command: "node scripts/verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown" },
  ];
  const sourceArtifacts = [
    "gh auth status -h github.com",
    "data/remote-workflow-file-check.json",
    "data/publish-dispatch-plan.json",
    "data/launch-handoff-verification.json",
  ];
  const expectedSignals = [
    "Token scopes include workflow",
    "workflowScopeAvailable=true",
    "workflowScopeInstallBlocked=false",
    "remoteWorkflowFilesReady=true after installer or GitHub UI commit",
    "remoteWorkflowVisibilityReady=true before dispatch",
    "safeToDispatch=true before gh workflow run",
  ];
  const blockedSignals = [
    "workflowScopeInstallBlocked=true",
    "remoteWorkflowFilesReady=false",
    "remoteWorkflowVisibilityReady=false",
    "allDispatchReady=false",
  ];
  const basePacket = {
    loaded: true,
    data: {
      generatedAt: "2026-06-10T00:00:00.000Z",
      repo: "biojuho/BIOJUHO-Projects",
      postAuthCheckpoint: {
        key: "post_auth_checkpoint",
        status: "pass",
        commandCount: 5,
        recheckSequence,
        sourceArtifacts,
        expectedSignals,
        blockedSignals,
        verificationOnly: true,
        dispatchApproval: false,
      },
    },
  };
  const explicitZeroMarkup = releaseStatus.launchExecutionPacketHTML({
    loaded: true,
    data: {
      ...basePacket.data,
      postAuthCheckpoint: {
        ...basePacket.data.postAuthCheckpoint,
        commandCount: 0,
        recheckSequenceCount: 0,
        sourceArtifactCount: 0,
        expectedSignalCount: 0,
        blockedSignalCount: 0,
      },
    },
  });
  assert.equal(attr(explicitZeroMarkup, "data-launch-execution-post-auth-checkpoint-command-count"), "0");
  assert.equal(attr(explicitZeroMarkup, "data-launch-execution-post-auth-checkpoint-expected-count"), "0");
  assert.equal(attr(explicitZeroMarkup, "data-launch-execution-post-auth-checkpoint-blocked-count"), "0");
  assert.equal(attr(explicitZeroMarkup, "data-launch-execution-post-auth-checkpoint-recheck-count"), "0");
  assert.equal(attr(explicitZeroMarkup, "data-launch-execution-post-auth-checkpoint-source-artifact-count"), "0");
  assert.equal(attr(explicitZeroMarkup, "data-launch-post-auth-expected-count"), "0");
  assert.equal(attr(explicitZeroMarkup, "data-launch-post-auth-blocked-count"), "0");
  assert.doesNotMatch(explicitZeroMarkup, /data-launch-post-auth-recheck-step/);
  assert.doesNotMatch(explicitZeroMarkup, /data-launch-post-auth-source-artifact="/);
  assert.doesNotMatch(explicitZeroMarkup, /Token scopes include workflow/);
  const derivedMarkup = releaseStatus.launchExecutionPacketHTML(basePacket);
  assert.equal(attr(derivedMarkup, "data-launch-execution-post-auth-checkpoint-command-count"), "5");
  assert.equal(attr(derivedMarkup, "data-launch-execution-post-auth-checkpoint-expected-count"), "6");
  assert.equal(attr(derivedMarkup, "data-launch-execution-post-auth-checkpoint-blocked-count"), "4");
  assert.equal(attr(derivedMarkup, "data-launch-execution-post-auth-checkpoint-recheck-count"), "5");
  assert.equal(attr(derivedMarkup, "data-launch-execution-post-auth-checkpoint-source-artifact-count"), "4");
  assert.match(derivedMarkup, /data-launch-post-auth-recheck-step/);
  assert.match(derivedMarkup, /data-launch-post-auth-source-artifact="data\/remote-workflow-file-check\.json"/);
  assert.match(source, /const postAuthCommandCount = finiteNumberOr\(postAuthCheckpoint\.commandCount, 0\)/);
  assert.match(source, /const postAuthRecheckSequenceCount = finiteNumberOr\(postAuthCheckpoint\.recheckSequenceCount, postAuthRecheckSequence\.length\)/);
  assert.match(source, /const postAuthSourceArtifactCount = finiteNumberOr\(postAuthCheckpoint\.sourceArtifactCount, postAuthSourceArtifacts\.length\)/);
  assert.match(source, /const postAuthExpectedSignalCount = finiteNumberOr\(postAuthCheckpoint\.expectedSignalCount, postAuthExpectedSignals\.length\)/);
  assert.match(source, /const postAuthBlockedSignalCount = finiteNumberOr\(postAuthCheckpoint\.blockedSignalCount, postAuthBlockedSignals\.length\)/);
  assert.match(source, /data-launch-execution-post-auth-checkpoint-command-count="\$\{postAuthCommandCount\}"/);
  assert.match(source, /data-launch-execution-post-auth-checkpoint-expected-count="\$\{postAuthExpectedSignalCount\}"/);
  assert.match(source, /data-launch-execution-post-auth-checkpoint-blocked-count="\$\{postAuthBlockedSignalCount\}"/);
  assert.match(source, /data-launch-post-auth-recheck-count="\$\{postAuthRecheckSequenceCount\}"/);
  assert.match(source, /data-launch-post-auth-source-artifact-count="\$\{postAuthSourceArtifactCount\}"/);
  assert.equal(source.includes('data-launch-execution-post-auth-checkpoint-recheck-count="${postAuthRecheckSequence.length}"'), false);
  assert.equal(source.includes('data-launch-execution-post-auth-checkpoint-source-artifact-count="${postAuthSourceArtifacts.length}"'), false);
  assert.equal(source.includes("<dd>${postAuthRecheckSequence.length}</dd>"), false);
  assert.equal(source.includes("<dd>${postAuthSourceArtifacts.length}</dd>"), false);
}

function testReleaseStatusLaunchBlockerResolverCountsPreserveExplicitZero() {
  const source = readFileSync(join(root, "release-status.js"), "utf8");
  const runtime = loadRuntime("release-status.js");
  const releaseStatus = runtime.JooParkReleaseStatus.create({
    html,
    raw,
    dateNow: () => Date.parse("2026-06-10T00:00:00.000Z"),
    formatLocalDateTime: (value) => String(value),
  });
  const attr = (markup, name) => {
    const match = markup.match(new RegExp(`${name}="([^"]*)"`));
    assert.ok(match, `${name} attribute missing`);
    return match[1];
  };
  const markup = releaseStatus.launchExecutionPacketHTML({
    loaded: true,
    data: {
      blockerResolutionChecklist: {
        source: "fixture",
        status: "action_required",
        activeItemKey: "operator_auth",
        itemCount: 0,
        passCount: 0,
        actionRequiredCount: 0,
        deferredCount: 0,
        proofCommandCount: 0,
        items: [
          {
            key: "operator_auth",
            label: "Operator auth",
            status: "action_required",
            action: "Refresh workflow scope",
            proofCommand: "gh auth refresh -h github.com -s workflow",
            expectedValue: "workflowScopeAvailable=true",
            stopCondition: "Stop if safeToDispatch=false",
          },
          {
            key: "remote_files",
            label: "Remote files",
            status: "action_required",
            action: "Install workflow files",
            proofCommand: "node scripts/check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write",
            expectedValue: "remoteWorkflowFilesReady=true",
            stopCondition: "Stop if remoteWorkflowFilesReady=false",
          },
        ],
      },
    },
  });
  assert.equal(attr(markup, "data-launch-execution-blocker-resolution-item-count"), "0");
  assert.equal(attr(markup, "data-launch-execution-blocker-resolution-action-required-count"), "0");
  assert.equal(attr(markup, "data-launch-execution-blocker-resolution-deferred-count"), "0");
  assert.equal(attr(markup, "data-launch-blocker-resolution-item-count"), "0");
  assert.equal(attr(markup, "data-launch-blocker-resolution-pass-count"), "0");
  assert.equal(attr(markup, "data-launch-blocker-resolution-action-required-count"), "0");
  assert.equal(attr(markup, "data-launch-blocker-resolution-deferred-count"), "0");
  assert.equal(attr(markup, "data-launch-blocker-resolution-proof-command-count"), "0");
  assert.match(markup, /<div><dt>pass<\/dt><dd>0\/0<\/dd><\/div>/);
  assert.doesNotMatch(markup, /0\/2/);
  assert.match(source, /const blockerResolutionItemCount = finiteNumberOr\(blockerResolution\.itemCount, blockerResolutionItems\.length\)/);
  assert.match(source, /const blockerResolutionPassCount = finiteNumberOr\(blockerResolution\.passCount, 0\)/);
  assert.match(source, /const blockerResolutionActionRequiredCount = finiteNumberOr\(blockerResolution\.actionRequiredCount, 0\)/);
  assert.match(source, /const blockerResolutionDeferredCount = finiteNumberOr\(blockerResolution\.deferredCount, 0\)/);
  assert.match(source, /const blockerResolutionProofCommandCount = finiteNumberOr\(blockerResolution\.proofCommandCount, 0\)/);
  assert.match(source, /data-launch-execution-blocker-resolution-item-count="\$\{blockerResolutionItemCount\}"/);
  assert.match(source, /data-launch-execution-blocker-resolution-action-required-count="\$\{blockerResolutionActionRequiredCount\}"/);
  assert.match(source, /data-launch-execution-blocker-resolution-deferred-count="\$\{blockerResolutionDeferredCount\}"/);
  assert.match(source, /data-launch-blocker-resolution-proof-command-count="\$\{blockerResolutionProofCommandCount\}"/);
  assert.equal(source.includes('data-launch-execution-blocker-resolution-item-count="${blockerResolution.itemCount || blockerResolutionItems.length}"'), false);
  assert.equal(source.includes('data-launch-blocker-resolution-pass-count="${blockerResolution.passCount || 0}"'), false);
  assert.equal(source.includes("<dd>${blockerResolution.passCount || 0}/${blockerResolution.itemCount || blockerResolutionItems.length}</dd>"), false);
}

function testReleaseStatusInstallPathCountsDeriveFromSourcePaths() {
  const source = readFileSync(join(root, "release-status.js"), "utf8");
  const runtime = loadRuntime("release-status.js");
  const releaseStatus = runtime.JooParkReleaseStatus.create({
    html,
    raw,
    dateNow: () => Date.parse("2026-06-10T00:00:00.000Z"),
    formatLocalDateTime: (value) => String(value),
  });
  const attr = (markup, name) => {
    const match = markup.match(new RegExp(`${name}="([^"]*)"`));
    assert.ok(match, `${name} attribute missing`);
    return match[1];
  };
  const sourceBackedPaths = {
    ready: true,
    labels: ["CLI path after workflow scope", "GitHub UI path"],
    installerCommand: "node scripts/install-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write --verify",
    paths: [
      { key: "cli", label: "CLI path after workflow scope", commands: Array.from({ length: 7 }, (_, index) => `cli_${index}`) },
      { key: "ui", label: "GitHub UI path", commandCount: 3 },
    ],
  };
  const explicitZeroItemPaths = {
    ready: true,
    paths: [
      { key: "zero", label: "Explicit zero path", commandCount: 0, commands: ["copy", "open"] },
    ],
  };
  const publishMarkup = releaseStatus.publishEvidenceHTML({
    loaded: true,
    data: {
      generatedAt: "2026-06-10T00:00:00.000Z",
      evidenceExpiresAt: "2026-06-11T00:00:00.000Z",
      immediateNextAction: {
        key: "install_workflows",
        launchInstallPaths: sourceBackedPaths,
      },
    },
  });
  assert.equal(attr(publishMarkup, "data-publish-evidence-install-path-count"), "2");
  assert.equal(attr(publishMarkup, "data-publish-evidence-install-path-command-count"), "10");
  const publishZeroMarkup = releaseStatus.publishEvidenceHTML({
    loaded: true,
    data: {
      generatedAt: "2026-06-10T00:00:00.000Z",
      evidenceExpiresAt: "2026-06-11T00:00:00.000Z",
      launchInstallPaths: {
        ...sourceBackedPaths,
        count: 0,
        commandCount: 0,
      },
    },
  });
  assert.equal(attr(publishZeroMarkup, "data-publish-evidence-install-path-count"), "0");
  assert.equal(attr(publishZeroMarkup, "data-publish-evidence-install-path-command-count"), "0");
  const publishItemZeroMarkup = releaseStatus.publishEvidenceHTML({
    loaded: true,
    data: {
      generatedAt: "2026-06-10T00:00:00.000Z",
      evidenceExpiresAt: "2026-06-11T00:00:00.000Z",
      launchInstallPaths: explicitZeroItemPaths,
      immediateNextAction: {
        key: "install_workflows",
      },
    },
  });
  assert.match(publishItemZeroMarkup, /Explicit zero path<\/strong> · 0 commands/);
  assert.doesNotMatch(publishItemZeroMarkup, /Explicit zero path<\/strong> · 2 commands/);
  const outputMarkup = releaseStatus.outputQualityAuditHTML({
    loaded: true,
    data: {
      outputReadinessSnapshot: {
        launchInstallPaths: sourceBackedPaths,
      },
    },
  });
  assert.equal(attr(outputMarkup, "data-output-quality-audit-install-path-count"), "2");
  assert.equal(attr(outputMarkup, "data-output-quality-audit-install-path-command-count"), "10");
  assert.match(outputMarkup, /2 paths · 10 commands/);
  const outputZeroMarkup = releaseStatus.outputQualityAuditHTML({
    loaded: true,
    data: {
      outputReadinessSnapshot: {
        launchInstallPaths: {
          ...sourceBackedPaths,
          count: 0,
          commandCount: 0,
        },
      },
    },
  });
  assert.equal(attr(outputZeroMarkup, "data-output-quality-audit-install-path-count"), "0");
  assert.equal(attr(outputZeroMarkup, "data-output-quality-audit-install-path-command-count"), "0");
  assert.match(outputZeroMarkup, /0 paths · 0 commands/);
  const outputItemZeroMarkup = releaseStatus.outputQualityAuditHTML({
    loaded: true,
    data: {
      outputReadinessSnapshot: {
        launchInstallPaths: explicitZeroItemPaths,
      },
    },
  });
  assert.match(outputItemZeroMarkup, /Explicit zero path<\/strong><span>0 commands<\/span>/);
  assert.doesNotMatch(outputItemZeroMarkup, /Explicit zero path<\/strong><span>2 commands<\/span>/);
  assert.match(source, /function installPathItemCommandCount\(item\)/);
  assert.match(source, /return finiteNumberOr\(item\?\.commandCount, Array\.isArray\(item\?\.commands\) \? item\.commands\.length : 0\)/);
  assert.match(source, /const launchInstallPathItemCommandCount = launchInstallPathItems\.reduce/);
  assert.match(source, /\(total, item\) => total \+ installPathItemCommandCount\(item\)/);
  assert.match(source, /const launchInstallPathCount = finiteNumberOr\(launchInstallPaths\.count, launchInstallPathItems\.length\)/);
  assert.match(source, /const launchInstallPathCommandCount = finiteNumberOr\(launchInstallPaths\.commandCount, launchInstallPathItemCommandCount\)/);
  assert.match(source, /<strong>\$\{item\.label \|\| "Install path"\}<\/strong> · \$\{installPathItemCommandCount\(item\)\} commands/);
  assert.match(source, /<span>\$\{installPathItemCommandCount\(item\)\} commands<\/span>/);
  assert.match(source, /data-publish-evidence-install-path-count="\$\{launchInstallPathCount\}"/);
  assert.match(source, /data-publish-evidence-install-path-command-count="\$\{launchInstallPathCommandCount\}"/);
  assert.match(source, /data-output-quality-audit-install-path-count="\$\{launchInstallPathCount\}"/);
  assert.match(source, /data-output-quality-audit-install-path-command-count="\$\{launchInstallPathCommandCount\}"/);
  assert.equal(source.includes("${item.commandCount || (Array.isArray(item.commands) ? item.commands.length : 0)} commands"), false);
  assert.equal(source.includes('data-output-quality-audit-install-path-count="${launchInstallPaths.count || launchInstallPathItems.length || 0}"'), false);
  assert.equal(source.includes('data-output-quality-audit-install-path-command-count="${launchInstallPaths.commandCount || 0}"'), false);
}

function testReleaseStatusExternalClaimCloseoutCountsPreserveExplicitZero() {
  const source = readFileSync(join(root, "release-status.js"), "utf8");
  const runtime = loadRuntime("release-status.js");
  const releaseStatus = runtime.JooParkReleaseStatus.create({
    html,
    raw,
    formatLocalDateTime: (value) => String(value),
  });
  const attr = (markup, name) => {
    const match = markup.match(new RegExp(`${name}="([^"]*)"`));
    assert.ok(match, `${name} attribute missing`);
    return match[1];
  };
  const markup = releaseStatus.outputQualityAuditHTML({
    loaded: true,
    data: {
      externalClaimGuard: {
        text: "guard",
        closeoutPacket: {
          text: "packet",
          stepCount: 0,
          proofFieldCount: 0,
          allowedClaimCount: 0,
          forbiddenClaimCount: 0,
          steps: [{ key: "dispatch", label: "Dispatch", command: "gh workflow run" }],
          proofFields: [{ key: "pages", label: "Pages URL", current: "pending", expected: "url" }],
          allowedClaims: ["Release-note archive claim"],
          forbiddenClaims: ["Public complete before proof"],
        },
      },
    },
  });
  assert.equal(attr(markup, "data-output-quality-audit-external-claim-closeout-step-count"), "0");
  assert.equal(attr(markup, "data-output-quality-audit-external-claim-closeout-field-count"), "0");
  assert.equal(attr(markup, "data-output-quality-audit-external-claim-closeout-allowed-count"), "0");
  assert.equal(attr(markup, "data-output-quality-audit-external-claim-closeout-forbidden-count"), "0");
  assert.match(source, /const externalClaimCloseoutStepCount = finiteNumberOr\(externalClaimCloseout\.stepCount, externalClaimCloseoutSteps\.length\)/);
  assert.match(source, /const externalClaimCloseoutFieldCount = finiteNumberOr\(externalClaimCloseout\.proofFieldCount, externalClaimCloseoutFields\.length\)/);
  assert.match(source, /const externalClaimCloseoutAllowedCount = finiteNumberOr\(externalClaimCloseout\.allowedClaimCount, externalClaimAllowedClaims\.length\)/);
  assert.match(source, /const externalClaimCloseoutForbiddenCount = finiteNumberOr\(externalClaimCloseout\.forbiddenClaimCount, externalClaimForbiddenClaims\.length\)/);
  assert.match(source, /data-output-quality-audit-external-claim-closeout-step-count="\$\{externalClaimCloseoutStepCount\}"/);
  assert.equal(source.includes("externalClaimCloseout.stepCount || externalClaimCloseoutSteps.length"), false);
  assert.equal(source.includes("externalClaimCloseout.proofFieldCount || externalClaimCloseoutFields.length"), false);
  assert.equal(source.includes("externalClaimCloseout.allowedClaimCount || externalClaimAllowedClaims.length"), false);
  assert.equal(source.includes("externalClaimCloseout.forbiddenClaimCount || externalClaimForbiddenClaims.length"), false);
}

function testReleaseStatusOutputQualitySourceEvidenceStaleCountPreservesExplicitZero() {
  const source = readFileSync(join(root, "release-status.js"), "utf8");
  const runtime = loadRuntime("release-status.js");
  const releaseStatus = runtime.JooParkReleaseStatus.create({
    html,
    raw,
    formatLocalDateTime: (value) => String(value),
  });
  const attr = (markup, name) => {
    const match = markup.match(new RegExp(`${name}="([^"]*)"`));
    assert.ok(match, `${name} attribute missing`);
    return match[1];
  };
  const markup = releaseStatus.outputQualityAuditHTML({
    loaded: true,
    source: "test",
    data: {
      generatedAt: "2026-06-11T00:00:00.000Z",
      sourceEvidenceFresh: true,
      sourceEvidenceStaleCount: 0,
      sourceEvidenceFreshness: {
        staleCount: 2,
        sources: [
          { key: "fresh", label: "Fresh source", path: "fresh.json", status: "fresh", ageHours: 1, maxAgeHours: 24 },
          { key: "stale", label: "Stale source", path: "stale.json", status: "stale", ageHours: 30, maxAgeHours: 24 },
        ],
      },
      latestGate: {
        command: "npm run verify",
        checks: { pass: 1, fail: 0, notRun: 0, blocked: 0 },
      },
      outputReadinessSnapshot: {},
    },
  });
  assert.equal(attr(markup, "data-output-quality-audit-source-evidence-stale-count"), "0");
  assert.match(markup, /<dt>sourceEvidenceStale<\/dt><dd>0<\/dd>/);
  assert.match(source, /const sourceEvidenceStaleCount = finiteNumberOr\(data\?\.sourceEvidenceStaleCount, sourceFreshness\.staleCount \|\| 0\)/);
  assert.equal(source.includes("data?.sourceEvidenceStaleCount || sourceFreshness.staleCount || 0"), false);
}

function testReleaseStatusVerifyWorkspaceNextCandidateCountPreservesExplicitZero() {
  const source = readFileSync(join(root, "release-status.js"), "utf8");
  const runtime = loadRuntime("release-status.js");
  const releaseStatus = runtime.JooParkReleaseStatus.create({
    html,
    raw,
    formatLocalDateTime: (value) => String(value),
  });
  const attr = (markup, name) => {
    const match = markup.match(new RegExp(`${name}="([^"]*)"`));
    assert.ok(match, `${name} attribute missing`);
    return match[1];
  };
  const markup = releaseStatus.verifyWorkspaceSummaryHTML({
    loaded: true,
    data: {
      status: "blocked",
      generatedAt: "2026-06-11T00:00:00.000Z",
      syncArtifacts: true,
      evidenceSyncPass: true,
      stepResults: [],
      artifacts: {
        releaseReadiness: { status: "blocked", summary: "283 pass, 0 fail, 1 blocked" },
        launchReadiness: { status: "pass", safeToDispatch: false, readyForExternalClaim: false },
        outputQuality: { status: "pass" },
        productLoop: {
          status: "pass",
          nextCandidateCount: 0,
          nextCandidates: ["candidate a", "candidate b"],
        },
        evidenceSync: { status: "pass" },
      },
    },
  });
  assert.equal(attr(markup, "data-verify-workspace-summary-next-candidate-count"), "0");
  assert.match(markup, /<dt>next candidates<\/dt><dd>0<\/dd>/);
  assert.match(markup, /nextCandidateCount: 0/);
  assert.match(source, /const nextCandidateCount = finiteNumberOr\(productLoop\.nextCandidateCount, nextCandidates\.length\)/);
  assert.equal(source.includes("productLoop.nextCandidateCount || nextCandidates.length || 0"), false);
}

function testReleaseStatusLaunchInstallMatrixCountsPreserveExplicitZero() {
  const source = readFileSync(join(root, "release-status.js"), "utf8");
  const runtime = loadRuntime("release-status.js");
  const releaseStatus = runtime.JooParkReleaseStatus.create({
    html,
    raw,
    formatLocalDateTime: (value) => String(value),
  });
  const attr = (markup, name) => {
    const match = markup.match(new RegExp(`${name}="([^"]*)"`));
    assert.ok(match, `${name} attribute missing`);
    return match[1];
  };
  const markup = releaseStatus.launchExecutionPacketHTML({
    loaded: true,
    data: {
      workflowInstallVerificationMatrix: {
        source: "fixture",
        installPathCount: 0,
        requiredSignalCount: 0,
        verificationCommandCount: 0,
        matrixRows: [
          { key: "cli", label: "CLI path", verificationCommands: ["check remote", "check dispatch"] },
          { key: "ui", label: "GitHub UI path" },
        ],
        signalChecks: [
          { key: "remote", label: "Remote files" },
          { key: "dispatch", label: "Dispatch ready" },
        ],
      },
    },
  });
  assert.equal(attr(markup, "data-launch-execution-install-matrix-path-count"), "0");
  assert.equal(attr(markup, "data-launch-execution-install-matrix-signal-count"), "0");
  assert.equal(attr(markup, "data-launch-execution-install-matrix-verification-command-count"), "0");
  assert.equal(attr(markup, "data-launch-install-verification-path-count"), "0");
  assert.equal(attr(markup, "data-launch-install-verification-signal-count"), "0");
  assert.equal(attr(markup, "data-launch-install-verification-command-count"), "0");
  assert.match(source, /const installMatrixPathCount = finiteNumberOr\(installMatrix\.installPathCount, installMatrixRows\.length\)/);
  assert.match(source, /const installMatrixSignalCount = finiteNumberOr\(installMatrix\.requiredSignalCount, installMatrixSignals\.length\)/);
  assert.match(source, /const installMatrixVerificationCommandCount = finiteNumberOr\(installMatrix\.verificationCommandCount, installMatrixCommands\.length\)/);
  assert.match(source, /data-launch-execution-install-matrix-path-count="\$\{installMatrixPathCount\}"/);
  assert.match(source, /data-launch-install-verification-command-count="\$\{installMatrixVerificationCommandCount\}"/);
  assert.equal(source.includes("installMatrix.installPathCount || installMatrixRows.length"), false);
  assert.equal(source.includes("installMatrix.requiredSignalCount || installMatrixSignals.length"), false);
  assert.equal(source.includes("installMatrix.verificationCommandCount || installMatrixCommands.length"), false);
}

function testReleaseStatusRemoteWorkflowLedgerCountsPreserveExplicitZero() {
  const source = readFileSync(join(root, "release-status.js"), "utf8");
  const runtime = loadRuntime("release-status.js");
  const releaseStatus = runtime.JooParkReleaseStatus.create({
    html,
    raw,
    formatLocalDateTime: (value) => String(value),
  });
  const attr = (markup, name) => {
    const match = markup.match(new RegExp(`${name}="([^"]*)"`));
    assert.ok(match, `${name} attribute missing`);
    return match[1];
  };
  const markup = releaseStatus.launchExecutionPacketHTML({
    loaded: true,
    data: {
      remoteWorkflowFileAcceptanceLedger: {
        source: "fixture",
        fileCount: 0,
        readyCount: 0,
        missingCount: 0,
        mismatchCount: 0,
        files: [
          { key: "pages", path: ".github/workflows/joopark-pages.yml" },
          { key: "drift", path: ".github/workflows/joopark-drift-watch.yml" },
        ],
      },
    },
  });
  assert.equal(attr(markup, "data-remote-workflow-file-ledger-file-count"), "0");
  assert.equal(attr(markup, "data-remote-workflow-file-ledger-ready-count"), "0");
  assert.equal(attr(markup, "data-remote-workflow-file-ledger-missing-count"), "0");
  assert.equal(attr(markup, "data-remote-workflow-file-ledger-mismatch-count"), "0");
  assert.match(markup, /0\/0 files ready/);
  assert.doesNotMatch(markup, /0\/2 files ready/);
  assert.match(source, /const remoteFileLedgerFileCount = finiteNumberOr\(remoteFileLedger\.fileCount, remoteFileLedgerItems\.length\)/);
  assert.match(source, /const remoteFileLedgerReadyCount = finiteNumberOr\(remoteFileLedger\.readyCount, 0\)/);
  assert.match(source, /const remoteFileLedgerMissingCount = finiteNumberOr\(remoteFileLedger\.missingCount, 0\)/);
  assert.match(source, /const remoteFileLedgerMismatchCount = finiteNumberOr\(remoteFileLedger\.mismatchCount, 0\)/);
  assert.match(source, /data-remote-workflow-file-ledger-file-count="\$\{remoteFileLedgerFileCount\}"/);
  assert.match(source, /<strong>\$\{remoteFileLedgerReadyCount\}\/\$\{remoteFileLedgerFileCount\} files ready<\/strong>/);
  assert.equal(source.includes("remoteFileLedger.fileCount || remoteFileLedgerItems.length"), false);
  assert.equal(source.includes("remoteFileLedger.readyCount || 0"), false);
  assert.equal(source.includes("remoteFileLedger.missingCount || 0"), false);
  assert.equal(source.includes("remoteFileLedger.mismatchCount || 0"), false);
}

function testReleaseStatusPostInstallIntakeCountsPreserveExplicitZero() {
  const source = readFileSync(join(root, "release-status.js"), "utf8");
  const runtime = loadRuntime("release-status.js");
  const releaseStatus = runtime.JooParkReleaseStatus.create({
    html,
    raw,
    formatLocalDateTime: (value) => String(value),
  });
  const attr = (markup, name) => {
    const match = markup.match(new RegExp(`${name}="([^"]*)"`));
    assert.ok(match, `${name} attribute missing`);
    return match[1];
  };
  const markup = releaseStatus.launchExecutionPacketHTML({
    loaded: true,
    data: {
      postInstallEvidenceIntake: {
        source: "fixture",
        fieldCount: 0,
        completedFieldCount: 0,
        pendingFieldCount: 0,
        commandCount: 0,
        signalCount: 0,
        fieldCoverage: 0,
        verificationSequenceCount: 0,
        quickProofStepCount: 0,
        quickProofCoverage: 0,
        quickProofFieldMappingCoverage: 0,
        quickProofMappedFieldCount: 0,
        quickProofCompletedMappedFieldCount: 0,
        fields: [{ key: "pages" }, { key: "remote" }],
        commands: ["node scripts/check-remote-workflow-files.mjs"],
        expectedSignals: ["remoteWorkflowFilesReady=true"],
        verificationSequence: [{ key: "verify", command: "node scripts/verify-launch-handoff.mjs", expected: "safeToDispatch=true" }],
        quickProofSteps: [{ key: "remote", command: "node scripts/check-remote-workflow-files.mjs", expected: "remoteWorkflowFilesReady=true" }],
        quickProofFieldMappings: [{ stepKey: "remote", fieldKey: "remote_parity_proof" }],
      },
    },
  });
  assert.equal(attr(markup, "data-launch-post-install-evidence-intake-field-count"), "0");
  assert.equal(attr(markup, "data-launch-post-install-evidence-intake-completed-count"), "0");
  assert.equal(attr(markup, "data-launch-post-install-evidence-intake-command-count"), "0");
  assert.equal(attr(markup, "data-launch-post-install-evidence-intake-signal-count"), "0");
  assert.equal(attr(markup, "data-launch-post-install-evidence-intake-field-coverage"), "0");
  assert.equal(attr(markup, "data-launch-post-install-evidence-intake-sequence-count"), "0");
  assert.equal(attr(markup, "data-launch-post-install-quick-proof-step-count"), "0");
  assert.equal(attr(markup, "data-launch-post-install-quick-proof-coverage"), "0");
  assert.equal(attr(markup, "data-launch-post-install-quick-proof-field-mapping-coverage"), "0");
  assert.equal(attr(markup, "data-launch-post-install-quick-proof-mapped-field-count"), "0");
  assert.equal(attr(markup, "data-launch-post-install-quick-proof-completed-mapped-field-count"), "0");
  assert.match(markup, /0\/0 proof fields complete/);
  assert.doesNotMatch(markup, /2 proof fields complete/);
  assert.match(source, /const postInstallIntakeFieldCount = finiteNumberOr\(postInstallIntake\.fieldCount, postInstallIntakeFields\.length\)/);
  assert.match(source, /const postInstallIntakeCommandCount = finiteNumberOr\(postInstallIntake\.commandCount, postInstallIntakeCommands\.length\)/);
  assert.match(source, /const postInstallIntakeSignalCount = finiteNumberOr\(postInstallIntake\.signalCount, postInstallIntakeSignals\.length\)/);
  assert.match(source, /const postInstallIntakeSequenceCount = finiteNumberOr\(postInstallIntake\.verificationSequenceCount, postInstallIntakeSequence\.length\)/);
  assert.match(source, /const postInstallQuickProofStepCount = finiteNumberOr\(postInstallIntake\.quickProofStepCount, postInstallQuickProofSteps\.length\)/);
  assert.match(source, /const postInstallQuickProofMappedFieldCount = finiteNumberOr\(postInstallIntake\.quickProofMappedFieldCount, postInstallQuickProofFieldMappings\.length\)/);
  assert.match(source, /data-launch-post-install-evidence-intake-field-count="\$\{postInstallIntakeFieldCount\}"/);
  assert.match(source, /data-launch-post-install-quick-proof-mapped-field-count="\$\{postInstallQuickProofMappedFieldCount\}"/);
  assert.equal(source.includes("postInstallIntake.fieldCount || postInstallIntakeFields.length"), false);
  assert.equal(source.includes("postInstallIntake.commandCount || postInstallIntakeCommands.length"), false);
  assert.equal(source.includes("postInstallIntake.signalCount || postInstallIntakeSignals.length"), false);
  assert.equal(source.includes("postInstallIntake.verificationSequenceCount || postInstallIntakeSequence.length"), false);
  assert.equal(source.includes("postInstallIntake.quickProofStepCount || postInstallQuickProofSteps.length"), false);
  assert.equal(source.includes("postInstallIntake.quickProofMappedFieldCount || postInstallQuickProofFieldMappings.length"), false);
}

function testProductLoopSummaryOptionValueGuard() {
  const source = readFileSync(join(root, "scripts/sync-product-loop-summary.mjs"), "utf8");
  const optionValue = scriptFunction("scripts/sync-product-loop-summary.mjs", "optionValue");
  const experimentSummary = scriptFunction("scripts/sync-product-loop-summary.mjs", "experimentSummary");
  assert.equal(optionValue(["--product-loop=autoresearch-results/joopark-product-loop.json"], "--product-loop"), "autoresearch-results/joopark-product-loop.json");
  assert.equal(optionValue(["--product-loop", "tmp/product-loop.json", "--write"], "--product-loop"), "tmp/product-loop.json");
  assert.equal(optionValue(["--product-loop", "--markdown"], "--product-loop"), "");
  assert.equal(optionValue(["--output-quality", "--write"], "--output-quality"), "");
  assert.equal(optionValue(["--direction-log", "--markdown"], "--direction-log"), "");
  assert.equal(optionValue(["--github-discovery", "--write"], "--github-discovery"), "");
  const summary = experimentSummary({
    id: "github-project-discovery-artifact",
    primaryMetric: "githubDiscoveryActionableProjectCoverage",
    baseline: 0,
    candidate: 9,
    decision: "keep",
    generatedAt: "2026-06-10T00:00:00.000Z",
    topProjects: [
      { nameWithOwner: "biojuho/BIOJUHO-Projects", relation: "current-release-target", localCheckout: true, nextAction: "Keep launch proof green." },
      { nameWithOwner: "biojuho/autoresearch-skill-system", relation: "autoresearch-toolchain", localCheckout: false, nextAction: "Use as reference tooling only." },
    ],
    topProjectCount: 2,
    releaseTargetIncluded: true,
  });
  assert.equal(summary.topProjectCount, 2);
  assert.equal(summary.releaseTargetIncluded, true);
  assert.deepEqual(summary.topProjects.map((project) => project.nameWithOwner), [
    "biojuho/BIOJUHO-Projects",
    "biojuho/autoresearch-skill-system",
  ]);
  assert.match(source, /function optionValue\(argsList, name\)/);
  assert.match(source, /summary\.topProjects/);
  assert.match(source, /return value\.startsWith\("--"\) \? "" : value/);
}

function testGithubProjectDiscoveryOptionValueGuard() {
  const source = readFileSync(join(root, "scripts/capture-github-project-discovery.mjs"), "utf8");
  const optionValue = scriptFunction("scripts/capture-github-project-discovery.mjs", "optionValue");
  assert.equal(optionValue(["--owner=biojuho"], "--owner"), "biojuho");
  assert.equal(optionValue(["--owner", "biojuho", "--write"], "--owner"), "biojuho");
  assert.equal(optionValue(["--owner", "--write"], "--owner"), "");
  assert.equal(optionValue(["--local-root", "--markdown"], "--local-root"), "");
  assert.equal(optionValue(["--max-depth", "--out"], "--max-depth"), "");
  assert.equal(optionValue(["--out", "--markdown"], "--out"), "");
  assert.equal(optionValue(["--markdown-out", "--write"], "--markdown-out"), "");
  assert.match(source, /function optionValue\(argsList, name\)/);
  assert.match(source, /return value\.startsWith\("--"\) \? "" : value/);
}

function testOutputQualityPublishInstallPathRepairAwareCoverage() {
  const source = readFileSync(join(root, "scripts/capture-output-quality-audit.mjs"), "utf8");
  const releaseGateBrowserEvidence = vm.runInNewContext([
    scriptFunctionSource("scripts/capture-output-quality-audit.mjs", "finiteNumberOr"),
    scriptFunctionSource("scripts/capture-output-quality-audit.mjs", "countIssues"),
    "function reviewCommentNoteDecisionSummarySourceReady() { return false; }",
    "function reviewResultRepairActionPlanSourceReady() { return false; }",
    "function reviewPackageSubmissionCloseoutSummarySourceReady() { return false; }",
    "function postInstallEvidenceIntakeSourceReady() { return false; }",
    "function launchProofEvidenceReceiptSourceReady() { return false; }",
    "function outputQualityExternalClaimGuardSourceReady() { return false; }",
    "function homeFirstRunGuidedStartSourceReady() { return false; }",
    "function globalHelpAccessSourceReady() { return false; }",
    "function topbarDataSafetySourceReady() { return false; }",
    "function routeDeepLinkSourceReady() { return false; }",
    "function postInstallProofParserSourceReady() { return false; }",
    "function launchPacketReadyForExternalClaim() { return false; }",
    scriptFunctionSource("scripts/capture-output-quality-audit.mjs", "releaseGateBrowserEvidence"),
    "releaseGateBrowserEvidence;",
  ].join("\n"));
  const installPathCopy = [
    "Choose one install path",
    "CLI path after workflow scope",
    "GitHub UI path",
    "node scripts/install-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write --verify",
    "pbcopy < 'docs/github-pages-workflow.yml'",
    "open 'https://github.com/biojuho/BIOJUHO-Projects/edit/main/.github/workflows/joopark-pages.yml'",
  ].join("\n");
  const sourceBacked = releaseGateBrowserEvidence(
    { evidence: { result: { interactions: { persistedChecks: {} }, verify: {}, smoke: {}, mobile: {} } } },
    {
      launchInstallPaths: {
        ready: true,
        paths: [
          { label: "CLI path after workflow scope", commands: Array.from({ length: 7 }, (_, index) => `cli_${index}`) },
          { label: "GitHub UI path", commandCount: 3 },
        ],
      },
      shareUpdate: installPathCopy,
      launchAnnouncement: installPathCopy,
      postLaunchVerificationReceipt: installPathCopy,
    },
  );
  assert.equal(sourceBacked.publishEvidenceInstallPathCopyCoverage, 1);
  assert.equal(sourceBacked.publishEvidenceInstallPathPaths, 2);
  assert.equal(sourceBacked.publishEvidenceInstallPathCommands, 10);
  const explicitZero = releaseGateBrowserEvidence(
    { evidence: { result: { interactions: { persistedChecks: {} }, verify: {}, smoke: {}, mobile: {} } } },
    {
      launchInstallPaths: {
        ready: true,
        count: 0,
        commandCount: 0,
        paths: [
          { label: "CLI path after workflow scope", commands: Array.from({ length: 7 }, (_, index) => `cli_${index}`) },
          { label: "GitHub UI path", commandCount: 3 },
        ],
      },
      shareUpdate: installPathCopy,
      launchAnnouncement: installPathCopy,
      postLaunchVerificationReceipt: installPathCopy,
    },
  );
  assert.equal(explicitZero.publishEvidenceInstallPathCopyCoverage, 0);
  assert.equal(explicitZero.publishEvidenceInstallPathPaths, 0);
  assert.equal(explicitZero.publishEvidenceInstallPathCommands, 0);
  assert.match(source, /publishInstallPathTerms/);
  assert.match(source, /edit\/main\/\.github\/workflows\/joopark-pages\.yml/);
  assert.match(source, /const publishInstallPathItems = Array\.isArray\(publishInstallPaths\.paths\)/);
  assert.match(source, /const publishInstallPathCommandCount = finiteNumberOr\(publishInstallPaths\.commandCount, publishInstallPathItemCommandCount\)/);
  assert.equal(source.includes("Number(publishInstallPaths.commandCount || 0) >= 10"), false);
}

function testPublishDispatchOptionValueGuard() {
  const source = readFileSync(join(root, "scripts/plan-publish-dispatch.mjs"), "utf8");
  const optionValue = scriptFunction("scripts/plan-publish-dispatch.mjs", "optionValue");
  const workflowScopeFallbackText = scriptFunction("scripts/plan-publish-dispatch.mjs", "workflowScopeFallbackText");
  assert.equal(optionValue(["--repo=biojuho/BIOJUHO-Projects"], "--repo"), "biojuho/BIOJUHO-Projects");
  assert.equal(optionValue(["--repo", "biojuho/BIOJUHO-Projects", "--write"], "--repo"), "biojuho/BIOJUHO-Projects");
  assert.equal(optionValue(["--repo", "--write"], "--repo"), "");
  assert.equal(optionValue(["--workflow-list-fixture", "--live"], "--workflow-list-fixture"), "");
  assert.match(workflowScopeFallbackText([{ installAction: "replace_existing_remote_file" }, { installAction: "verified_remote_matches_template" }]), /edit-file pages/);
  assert.match(workflowScopeFallbackText([{ installAction: "replace_existing_remote_file" }, { installAction: "verified_remote_matches_template" }]), /new-file pages only for missing files/);
  assert.match(workflowScopeFallbackText([{ installAction: "create_missing_remote_file" }]), /new-file pages only/);
  assert.match(workflowScopeFallbackText([{ installAction: "verified_remote_matches_template" }, { installAction: "verified_remote_matches_template" }]), /No GitHub UI file change is required/);
  assert.match(source, /function optionValue\(argsList, name\)/);
  assert.match(source, /function workflowScopeFallbackText/);
  assert.match(source, /const installAction = remoteFileCheck\?\.installAction/);
  assert.match(source, /return value\.startsWith\("--"\) \? "" : value/);
}

function testRemoteWorkflowCheckOptionValueGuard() {
  const source = readFileSync(join(root, "scripts/check-remote-workflow-files.mjs"), "utf8");
  const optionValue = scriptFunction("scripts/check-remote-workflow-files.mjs", "optionValue");
  const workflowUiFallbackText = scriptFunction("scripts/check-remote-workflow-files.mjs", "workflowUiFallbackText");
  assert.equal(optionValue(["--repo=biojuho/BIOJUHO-Projects"], "--repo"), "biojuho/BIOJUHO-Projects");
  assert.equal(optionValue(["--repo", "biojuho/BIOJUHO-Projects", "--write"], "--repo"), "biojuho/BIOJUHO-Projects");
  assert.equal(optionValue(["--repo", "--write"], "--repo"), "");
  assert.equal(optionValue(["--branch", "main", "--markdown"], "--branch"), "main");
  assert.equal(optionValue(["--branch", "--markdown"], "--branch"), "");
  assert.match(workflowUiFallbackText([{ installAction: "replace_existing_remote_file" }]), /edit-file pages/);
  assert.match(workflowUiFallbackText([{ installAction: "replace_existing_remote_file" }]), /do not use new-file links/);
  assert.match(workflowUiFallbackText([{ installAction: "create_missing_remote_file" }]), /new-file links only/);
  assert.match(workflowUiFallbackText([{ installAction: "verified_remote_matches_template" }]), /No GitHub UI file change is required/);
  assert.match(source, /function optionValue\(argsList, name\)/);
  assert.match(source, /function workflowUiFallbackText/);
  assert.match(source, /return value\.startsWith\("--"\) \? "" : value/);
}

function testRemoteWorkflowInstallerOptionValueGuard() {
  const source = readFileSync(join(root, "scripts/install-remote-workflow-files.mjs"), "utf8");
  const optionValue = scriptFunction("scripts/install-remote-workflow-files.mjs", "optionValue");
  const workflowUiFallbackText = scriptFunction("scripts/install-remote-workflow-files.mjs", "workflowUiFallbackText");
  assert.equal(optionValue(["--repo=biojuho/BIOJUHO-Projects"], "--repo"), "biojuho/BIOJUHO-Projects");
  assert.equal(optionValue(["--repo", "biojuho/BIOJUHO-Projects", "--write"], "--repo"), "biojuho/BIOJUHO-Projects");
  assert.equal(optionValue(["--repo", "--write"], "--repo"), "");
  assert.equal(optionValue(["--branch", "main", "--verify"], "--branch"), "main");
  assert.equal(optionValue(["--branch", "--verify"], "--branch"), "");
  assert.equal(optionValue(["--message", "Install workflows", "--markdown"], "--message"), "Install workflows");
  assert.equal(optionValue(["--message", "--markdown"], "--message"), "");
  assert.match(workflowUiFallbackText([{ operation: "update" }, { operation: "noop" }]), /edit-file pages/);
  assert.match(workflowUiFallbackText([{ operation: "update" }, { operation: "noop" }]), /do not use new-file links for update rows/);
  assert.match(workflowUiFallbackText([{ operation: "create" }, { operation: "noop" }]), /new-file pages only for create rows/);
  assert.match(workflowUiFallbackText([{ operation: "noop" }, { operation: "noop" }]), /No GitHub UI file change is required/);
  assert.match(source, /function optionValue\(argsList, name\)/);
  assert.match(source, /function workflowUiFallbackText/);
  assert.match(source, /return value\.startsWith\("--"\) \? "" : value/);
}

function testWorkflowUiInstallRepairAwareActions() {
  const source = readFileSync(join(root, "scripts/plan-workflow-ui-install.mjs"), "utf8");
  const workflowUiInstallAction = scriptFunction("scripts/plan-workflow-ui-install.mjs", "workflowUiInstallAction");
  const workflowUiInstallInstruction = scriptFunction("scripts/plan-workflow-ui-install.mjs", "workflowUiInstallInstruction");
  assert.equal(workflowUiInstallAction({ installAction: "replace_existing_remote_file" }), "replace_existing_remote_file");
  assert.equal(workflowUiInstallAction({ installAction: "verified_remote_matches_template" }), "verified_remote_matches_template");
  assert.equal(workflowUiInstallAction({ remoteExists: true, remoteMatchesTemplate: false }), "replace_existing_remote_file");
  assert.equal(workflowUiInstallAction({ remoteExists: true, remoteMatchesTemplate: true }), "verified_remote_matches_template");
  assert.equal(workflowUiInstallAction({ remoteExists: false, remoteMatchesTemplate: false }), "create_missing_remote_file");
  assert.match(workflowUiInstallInstruction({
    installAction: "replace_existing_remote_file",
    targetRepositoryPath: ".github/workflows/joopark-pages.yml",
    defaultBranch: "main",
  }), /edit-file page/);
  assert.match(workflowUiInstallInstruction({
    installAction: "verified_remote_matches_template",
    targetRepositoryPath: ".github/workflows/joopark-drift-watch.yml",
    defaultBranch: "main",
  }), /No GitHub UI edit is required/);
  assert.match(source, /remoteWorkflowFileCheckPath = "data\/remote-workflow-file-check\.json"/);
  assert.match(source, /githubEditFileOpenCommand/);
  assert.match(source, /uiInstallOpenCommand/);
  assert.match(source, /installActionCoverage/);
  assert.match(source, /verified_remote_matches_template rows require no edit/);
}

function testMainBridgeOptionValueGuard() {
  const source = readFileSync(join(root, "scripts/plan-main-bridge.mjs"), "utf8");
  const optionValue = scriptFunction("scripts/plan-main-bridge.mjs", "optionValue");
  assert.equal(optionValue(["--out=data/main-bridge-plan.json"], "--out"), "data/main-bridge-plan.json");
  assert.equal(optionValue(["--out", "tmp/main-bridge.json", "--write"], "--out"), "tmp/main-bridge.json");
  assert.equal(optionValue(["--out", "--write"], "--out"), "");
  assert.match(source, /function optionValue\(argsList, name\)/);
  assert.match(source, /return value\.startsWith\("--"\) \? "" : value/);
}

function testPublishEvidenceRepairFirstCommand() {
  const source = readFileSync(join(root, "scripts/capture-publish-evidence.mjs"), "utf8");
  assert.match(source, /const launchReadinessRefresh = readJson\("data\/launch-readiness-refresh\.json"\)/);
  assert.match(source, /function publishEvidenceRepairFirstCommand/);
  assert.match(source, /repairFirstCommand \|\| commands\[0\]/);
  assert.match(source, /remoteWorkflowRepairAction/);
  assert.match(source, /launchReadinessMatchesRepo/);
}

function testPublishEvidenceOptionValueGuard() {
  const source = readFileSync(join(root, "scripts/capture-publish-evidence.mjs"), "utf8");
  const optionValue = scriptFunction("scripts/capture-publish-evidence.mjs", "optionValue");
  assert.equal(optionValue(["--repo=biojuho/BIOJUHO-Projects"], "--repo"), "biojuho/BIOJUHO-Projects");
  assert.equal(optionValue(["--repo", "biojuho/BIOJUHO-Projects", "--write"], "--repo"), "biojuho/BIOJUHO-Projects");
  assert.equal(optionValue(["--repo", "--write"], "--repo"), "");
  assert.equal(optionValue(["--out", "--markdown"], "--out"), "");
  assert.match(source, /function optionValue\(argsList, name\)/);
  assert.match(source, /return value\.startsWith\("--"\) \? "" : value/);
}

function testLaunchHandoffOptionValueGuard() {
  const source = readFileSync(join(root, "scripts/verify-launch-handoff.mjs"), "utf8");
  const optionValue = scriptFunction("scripts/verify-launch-handoff.mjs", "optionValue");
  const blockerResolutionSummary = vm.runInNewContext([
    scriptFunctionSource("scripts/verify-launch-handoff.mjs", "numberOr"),
    scriptFunctionSource("scripts/verify-launch-handoff.mjs", "blockerResolutionSummary"),
    "blockerResolutionSummary;",
  ].join("\n"));
  assert.equal(optionValue(["--repo=biojuho/BIOJUHO-Projects"], "--repo"), "biojuho/BIOJUHO-Projects");
  assert.equal(optionValue(["--repo", "biojuho/BIOJUHO-Projects", "--write"], "--repo"), "biojuho/BIOJUHO-Projects");
  assert.equal(optionValue(["--repo", "--write"], "--repo"), "");
  assert.equal(optionValue(["--out-json", "--write"], "--out-json"), "");
  assert.equal(optionValue(["--out-markdown", "--markdown"], "--out-markdown"), "");
  const explicitZeroSummary = blockerResolutionSummary({
    itemCount: 0,
    passCount: 0,
    actionRequiredCount: 0,
    deferredCount: 0,
    proofCommandCount: 0,
    items: [
      { status: "pass", proofCommand: "node pass" },
      { status: "action_required", proofCommand: "node fix" },
    ],
  });
  assert.equal(explicitZeroSummary.itemCount, 0);
  assert.equal(explicitZeroSummary.passCount, 0);
  assert.equal(explicitZeroSummary.actionRequiredCount, 0);
  assert.equal(explicitZeroSummary.proofCommandCount, 0);
  const derivedSummary = blockerResolutionSummary({
    items: [
      { status: "pass", proofCommand: "node pass" },
      { status: "action_required", proofCommand: "node fix" },
      { status: "deferred_until_dispatch" },
    ],
  });
  assert.equal(derivedSummary.itemCount, 3);
  assert.equal(derivedSummary.passCount, 1);
  assert.equal(derivedSummary.actionRequiredCount, 1);
  assert.equal(derivedSummary.deferredCount, 1);
  assert.equal(derivedSummary.proofCommandCount, 2);
  assert.match(source, /function optionValue\(argsList, name\)/);
  assert.match(source, /return value\.startsWith\("--"\) \? "" : value/);
  assert.match(source, /itemCount: numberOr\(source\.itemCount, items\.length\)/);
  assert.equal(source.includes("itemCount: Number(source.itemCount || items.length)"), false);
  assert.equal(source.includes("proofCommandCount: Number(source.proofCommandCount || items.filter"), false);
}

function testLaunchExecutionPacketOptionValueGuard() {
  const source = readFileSync(join(root, "scripts/capture-launch-execution-packet.mjs"), "utf8");
  const optionValue = scriptFunction("scripts/capture-launch-execution-packet.mjs", "optionValue");
  assert.equal(optionValue(["--out=data/launch-execution-packet.json"], "--out"), "data/launch-execution-packet.json");
  assert.equal(optionValue(["--out", "tmp/launch.json", "--write"], "--out"), "tmp/launch.json");
  assert.equal(optionValue(["--out", "--write"], "--out"), "");
  assert.equal(optionValue(["--out", "--markdown"], "--out"), "");
  assert.match(source, /function optionValue\(argsList, name\)/);
  assert.match(source, /return value\.startsWith\("--"\) \? "" : value/);
}

function testLaunchExecutionPacketTextCountsPreserveExplicitZero() {
  const source = readFileSync(join(root, "scripts/capture-launch-execution-packet.mjs"), "utf8");
  const helpers = vm.runInNewContext([
    scriptFunctionSource("scripts/capture-launch-execution-packet.mjs", "valueOrPending"),
    scriptFunctionSource("scripts/capture-launch-execution-packet.mjs", "numberOr"),
    scriptFunctionSource("scripts/capture-launch-execution-packet.mjs", "yesNo"),
    scriptFunctionSource("scripts/capture-launch-execution-packet.mjs", "postAuthCheckpointLines"),
    scriptFunctionSource("scripts/capture-launch-execution-packet.mjs", "postInstallEvidenceIntakeLines"),
    "({ postAuthCheckpointLines, postInstallEvidenceIntakeLines });",
  ].join("\n"));
  const postAuthLines = helpers.postAuthCheckpointLines({
    status: "pass",
    recheckSequenceCount: 0,
    recheckSequence: [
      { key: "confirm_scope", command: "gh auth status -h github.com" },
      { key: "verify_handoff_guard", command: "node scripts/verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown" },
    ],
  });
  assert.ok(postAuthLines.includes("- recheck sequence: 0"));
  assert.ok(!postAuthLines.includes("- recheck sequence: 2"));
  const postInstallLines = helpers.postInstallEvidenceIntakeLines({
    source: "fixture",
    status: "collect_post_install_proof",
    verificationSequenceCount: 0,
    quickProofStepCount: 0,
    quickProofMappedFieldCount: 0,
    quickProofCompletedMappedFieldCount: 0,
    verificationSequence: [{ key: "remote_parity" }, { key: "handoff" }],
    quickProofSteps: [{ key: "step_1" }, { key: "step_2" }, { key: "step_3" }],
    quickProofFieldMappings: [{ stepKey: "step_1" }, { stepKey: "step_2" }, { stepKey: "step_3" }, { stepKey: "step_4" }],
  });
  assert.ok(postInstallLines.includes("- commands: not available; signals=not available; checklist=not available; sequence=0"));
  assert.ok(postInstallLines.includes("- quick proof: ready=false; steps=0; coverage=not available"));
  assert.ok(postInstallLines.includes("- quick proof field mapping: ready=false; mapped=0; completed=0/0; coverage=not available"));
  assert.ok(!postInstallLines.includes("sequence=2"));
  assert.ok(!postInstallLines.includes("steps=3"));
  assert.ok(!postInstallLines.includes("mapped=4"));
  assert.match(source, /function numberOr\(value, fallback\)/);
  assert.match(source, /const recheckSequenceCount = numberOr\(checkpoint\?\.recheckSequenceCount, recheckSequence\.length\)/);
  assert.match(source, /const verificationSequenceCount = numberOr\(intake\?\.verificationSequenceCount, sequence\.length\)/);
  assert.match(source, /const quickProofStepCount = numberOr\(intake\?\.quickProofStepCount, quickProofSteps\.length\)/);
  assert.match(source, /const quickProofMappedFieldCount = numberOr\(intake\?\.quickProofMappedFieldCount, quickProofFieldMappings\.length\)/);
  assert.equal(source.includes("checkpoint?.recheckSequenceCount || recheckSequence.length"), false);
  assert.equal(source.includes("intake?.verificationSequenceCount || sequence.length"), false);
  assert.equal(source.includes("intake?.quickProofStepCount || quickProofSteps.length"), false);
  assert.equal(source.includes("intake?.quickProofMappedFieldCount || quickProofFieldMappings.length"), false);
}

function testLaunchExecutionRepairAwareGithubUiPath() {
  const source = readFileSync(join(root, "scripts/capture-launch-execution-packet.mjs"), "utf8");
  const openCommand = scriptFunction("scripts/capture-launch-execution-packet.mjs", "remoteWorkflowFileOpenCommand");
  assert.equal(openCommand({ installAction: "replace_existing_remote_file", githubNewFileOpenCommand: "open new", githubEditFileOpenCommand: "open edit" }), "open edit");
  assert.equal(openCommand({ installAction: "create_missing_remote_file", githubNewFileOpenCommand: "open new", githubEditFileOpenCommand: "open edit" }), "open new");
  assert.equal(openCommand({ installAction: "verified_remote_matches_template", githubNewFileOpenCommand: "open new", githubEditFileOpenCommand: "open edit" }), "");
  assert.match(source, /function workflowUiInstallCommands/);
  assert.match(source, /function remoteWorkflowFileOpenCommand/);
  assert.match(source, /remoteWorkflowCheckForPlan/);
  assert.match(source, /installAction === "replace_existing_remote_file"/);
  assert.match(source, /githubEditFileOpenCommand/);
  assert.match(source, /openCommand/);
  assert.match(source, /\`\$\{copyCommand\} && \$\{editCommand\}\`/);
  assert.match(source, /Use each file's create or edit URL according to installAction/);
}

function testMobileSmokeNumericFallbacks() {
  const source = readFileSync(join(root, "scripts/smoke-mobile.mjs"), "utf8");
  const positiveIntegerOption = scriptFunction("scripts/smoke-mobile.mjs", "positiveIntegerOption");
  const positiveMsOption = scriptFunction("scripts/smoke-mobile.mjs", "positiveMsOption");
  assert.equal(positiveIntegerOption("500", 1), 500);
  assert.equal(positiveIntegerOption("bad", 500), 500);
  assert.equal(positiveIntegerOption("Infinity", 500), 500);
  assert.equal(positiveIntegerOption("0", 500), 500);
  assert.equal(positiveIntegerOption("500.5", 500), 500);
  assert.equal(positiveMsOption("3000", 60000), 3000);
  assert.equal(positiveMsOption("bad", 60000), 60000);
  assert.equal(positiveMsOption("Infinity", 60000), 60000);
  assert.equal(positiveMsOption("-1", 60000), 60000);
  assert.match(source, /const viewportWidth = positiveIntegerOption\(process\.env\.MOBILE_SMOKE_WIDTH, 500\)/);
  assert.match(source, /const viewportHeight = positiveIntegerOption\(process\.env\.MOBILE_SMOKE_HEIGHT, 757\)/);
  assert.match(source, /const defaultEvaluateTimeoutMs = positiveMsOption\(process\.env\.SMOKE_RUNTIME_TIMEOUT_MS, 60000\)/);
  assert.match(source, /const routeReadyTimeoutMs = positiveMsOption\(process\.env\.MOBILE_SMOKE_ROUTE_READY_TIMEOUT_MS \|\| process\.env\.SMOKE_ROUTE_READY_TIMEOUT_MS, 9000\)/);
}

function testBrowserSmokeTimeoutFallbacks() {
  const contracts = [
    {
      relPath: "scripts/smoke-chrome.mjs",
      patterns: [
        /const defaultEvaluateTimeoutMs = positiveMsOption\(process\.env\.SMOKE_RUNTIME_TIMEOUT_MS, 90000\)/,
        /const routeReadyTimeoutMs = positiveMsOption\(process\.env\.SMOKE_ROUTE_READY_TIMEOUT_MS, 12000\)/,
      ],
    },
    {
      relPath: "scripts/smoke-a11y.mjs",
      patterns: [
        /const defaultEvaluateTimeoutMs = positiveMsOption\(process\.env\.SMOKE_RUNTIME_TIMEOUT_MS, 60000\)/,
      ],
    },
    {
      relPath: "scripts/smoke-interactions.mjs",
      patterns: [
        /const defaultEvaluateTimeoutMs = positiveMsOption\(process\.env\.SMOKE_RUNTIME_TIMEOUT_MS, 60000\)/,
        /const longScenarioEvaluateTimeoutMs = positiveMsOption\(process\.env\.SMOKE_LONG_SCENARIO_TIMEOUT_MS \|\| process\.env\.SMOKE_RUNTIME_TIMEOUT_MS, 300000\)/,
      ],
    },
  ];

  for (const contract of contracts) {
    const source = readFileSync(join(root, contract.relPath), "utf8");
    const positiveMsOption = scriptFunction(contract.relPath, "positiveMsOption");
    assert.equal(positiveMsOption("9000", 60000), 9000);
    assert.equal(positiveMsOption("bad", 60000), 60000);
    assert.equal(positiveMsOption("Infinity", 60000), 60000);
    assert.equal(positiveMsOption("0", 60000), 60000);
    assert.equal(positiveMsOption("-5", 60000), 60000);
    for (const pattern of contract.patterns) assert.match(source, pattern);
  }
}

function testCapturePreviewInlineOptions() {
  const source = readFileSync(join(root, "scripts/capture-preview.mjs"), "utf8");
  const optionValue = scriptFunction("scripts/capture-preview.mjs", "optionValue");
  const previewRequestPath = scriptFunction("scripts/capture-preview.mjs", "previewRequestPath");
  const positiveIntegerOption = scriptFunction("scripts/capture-preview.mjs", "positiveIntegerOption");

  assert.equal(optionValue(["--width=800", "--height", "450"], "--width"), "800");
  assert.equal(optionValue(["--width=800", "--height", "450"], "--height"), "450");
  assert.equal(optionValue(["--out=tmp/social.png", "--base-url=http://127.0.0.1:5178"], "--out"), "tmp/social.png");
  assert.equal(optionValue(["--out=tmp/social.png", "--base-url=http://127.0.0.1:5178"], "--base-url"), "http://127.0.0.1:5178");
  assert.equal(optionValue(["--width", "--height"], "--width"), "");
  assert.equal(optionValue(["--height", "--out"], "--height"), "");
  assert.equal(optionValue(["--out", "--base-url"], "--out"), "");
  assert.equal(optionValue(["--base-url", "--width"], "--base-url"), "");
  assert.equal(positiveIntegerOption("bad", 1200), 1200);
  assert.equal(positiveIntegerOption("Infinity", 630), 630);
  assert.equal(previewRequestPath("/"), "index.html");
  assert.equal(previewRequestPath("/styles.css"), "styles.css");
  assert.equal(previewRequestPath("/%E0%A4%A"), null);
  assert.match(source, /const width = positiveIntegerOption\(argValue\("--width"\) \|\| process\.env\.PREVIEW_WIDTH, 1200\)/);
  assert.match(source, /function optionValue\(argsList, name\)/);
  assert.match(source, /function previewStaticTarget\(pathname\)/);
  assert.match(source, /const allowedPrefix = `\$\{root\}\$\{sep\}`/);
  assert.match(source, /response\.writeHead\(403/);
  assert.equal(source.includes("arg.startsWith(`${name}=`)"), true);
  assert.equal(source.includes("value.startsWith(\"--\") ? \"\" : value"), true);
}

function testProductSmokeCloseUnrefsForcedServer() {
  for (const relPath of ["scripts/verify-product-smoke.mjs", "scripts/smoke-release.mjs"]) {
    const source = readFileSync(join(root, relPath), "utf8");
    assert.match(source, /let settled = false/);
    assert.match(source, /const forceStop = \(\) => \{/);
    assert.match(source, /server\.closeAllConnections/);
    assert.match(source, /server\.unref/);
    assert.match(source, /settle\(\)/);
  }
}

function testProductSmokeCliExitsAfterFlushedSuccess() {
  for (const relPath of ["scripts/verify-product-smoke.mjs", "scripts/smoke-release.mjs"]) {
    const source = readFileSync(join(root, relPath), "utf8");
    assert.match(source, /function writeJson\(payload\)/);
    assert.match(source, /process\.stdout\.write\(`\$\{JSON\.stringify\(payload, null, 2\)\}\\n`, resolveWrite\)/);
    assert.match(source, /async function runCli\(\)/);
    assert.match(source, /await withProductSmokeLock\(\{ root, label: "[^"]+", progress \}, main\)/);
    assert.match(source, /process\.exit\(0\)/);
  }
}

function testFullVerifyRefreshesPackagedBrowserGates() {
  const source = readFileSync(join(root, "scripts/verify-workspace.mjs"), "utf8");
  const auditSource = readFileSync(join(root, "scripts/audit-release-readiness.mjs"), "utf8");
  assert.match(source, /const syncArtifacts = process\.argv\.includes\("--sync-artifacts"\)/);
  assert.match(source, /node scripts\/audit-release-readiness\.mjs --run-gates --format=summary/);
  assert.match(source, /\["scripts\/audit-release-readiness\.mjs", "--run-gates", "--format=summary"\]/);
  assert.match(source, /node scripts\/audit-release-readiness\.mjs --format=summary/);
  assert.match(source, /if \(result\.status !== "pass" && !syncArtifacts\) break;/);
  assert.equal(source.includes('if (result.status !== "pass") break;'), false);
  assert.match(source, /releaseReadiness\.status === "blocked"/);
  assert.match(source, /hasBlockedStep \? "blocked" : "pass"/);
  assert.match(auditSource, /const verifyWorkspaceSummaryStatusReady = verifyWorkspaceSummaryArtifact\?\.status === "pass" \|\|/);
  assert.match(auditSource, /verifyWorkspaceSummaryArtifact\?\.status === "blocked"/);
  assert.match(auditSource, /verifyWorkspaceSummaryArtifactSyncReady = verifyWorkspaceSummaryStatusReady &&/);
}

function testPagesAttestationBlankTemplateGuard() {
  const output = execFileSync(process.execPath, [
    join(root, "scripts/capture-pages-attestation-proof.mjs"),
    "--repo",
    "biojuho/BIOJUHO-Projects",
  ], {
    cwd: root,
    encoding: "utf8",
  });
  const payload = JSON.parse(output);
  assert.equal(payload.proofComplete, false);
  assert.equal(payload.signedProofReady, false);
  assert.equal(payload.detectedFieldCount, 0);
  assert.equal(payload.completedFieldCount, 0);
  assert.equal(payload.falsePositiveGuard, true);
  assert.equal(payload.fields.every((field) => field.present === false && field.status === "missing"), true);
}

function testPagesAttestationOptionValueGuard() {
  const source = readFileSync(join(root, "scripts/capture-pages-attestation-proof.mjs"), "utf8");
  const optionValue = scriptFunction("scripts/capture-pages-attestation-proof.mjs", "optionValue");
  assert.equal(optionValue(["--repo=biojuho/BIOJUHO-Projects"], "--repo"), "biojuho/BIOJUHO-Projects");
  assert.equal(optionValue(["--repo", "biojuho/BIOJUHO-Projects", "--write"], "--repo"), "biojuho/BIOJUHO-Projects");
  assert.equal(optionValue(["--repo", "--write"], "--repo"), "");
  assert.equal(optionValue(["--input", "--markdown"], "--input"), "");
  assert.equal(optionValue(["--out", "--write"], "--out"), "");
  assert.equal(optionValue(["--out-markdown", "--markdown"], "--out-markdown"), "");
  assert.match(source, /function optionValue\(argsList, name\)/);
  assert.match(source, /return value\.startsWith\("--"\) \? "" : value/);
}

function testRefreshCandidateSnapshotLiveDriftBuffer() {
  const source = readFileSync(join(root, "scripts/refresh-candidate-snapshot.mjs"), "utf8");
  assert.match(source, /mkdtempSync\(join\(tmpdir\(\), "joopark-live-drift-"\)\)/);
  assert.match(source, /stdio:\s*\["ignore", stdoutFd, stderrFd\]/);
  assert.match(source, /stdoutLength/);
  assert.match(source, /stdoutTail/);
}

function testCandidateFreshnessDriftRepoOptionValueGuard() {
  const source = readFileSync(join(root, "scripts/check-candidate-freshness-drift.mjs"), "utf8");
  const collectOptionValues = scriptFunction("scripts/check-candidate-freshness-drift.mjs", "collectOptionValues");
  assert.deepEqual([...collectOptionValues("--repo", ["--repo=biojuho/BIOJUHO-Projects"])], ["biojuho/BIOJUHO-Projects"]);
  assert.deepEqual([...collectOptionValues("--repo", ["--repo", "biojuho/BIOJUHO-Projects", "--live"])], ["biojuho/BIOJUHO-Projects"]);
  assert.deepEqual([...collectOptionValues("--repo", ["--repo", "--live"])], []);
  assert.deepEqual([...collectOptionValues("--repo", ["--repo", "--fail-on-drift"])], []);
  assert.match(source, /function collectOptionValues\(flag, argsList = rawArgs\)/);
  assert.match(source, /!argsList\[index \+ 1\]\.startsWith\("--"\)/);
}

function testRefreshCandidateSnapshotRepoOptionValueGuard() {
  const source = readFileSync(join(root, "scripts/refresh-candidate-snapshot.mjs"), "utf8");
  const collectOptionValues = scriptFunction("scripts/refresh-candidate-snapshot.mjs", "collectOptionValues");
  const finiteNumberOr = scriptFunction("scripts/refresh-candidate-snapshot.mjs", "finiteNumberOr");
  const actionableDriftCountFromPayload = vm.runInNewContext([
    scriptFunctionSource("scripts/refresh-candidate-snapshot.mjs", "finiteNumberOr"),
    scriptFunctionSource("scripts/refresh-candidate-snapshot.mjs", "actionableDriftCountFromPayload"),
    "actionableDriftCountFromPayload;",
  ].join("\n"));
  assert.deepEqual([...collectOptionValues("--repo", ["--repo=Veritas-7/autoresearch-skill-system"])], ["Veritas-7/autoresearch-skill-system"]);
  assert.deepEqual([...collectOptionValues("--repo", ["--repo", "Veritas-7/autoresearch-skill-system", "--write"])], ["Veritas-7/autoresearch-skill-system"]);
  assert.deepEqual([...collectOptionValues("--repo", ["--repo", "--write"])], []);
  assert.deepEqual([...collectOptionValues("--repo", ["--repo", "--from-live-drift"])], []);
  assert.equal(finiteNumberOr(0, 7), 0);
  assert.equal(actionableDriftCountFromPayload({ actionableDriftCount: 0, blockingDriftCount: 5 }), 0);
  assert.equal(actionableDriftCountFromPayload({ blockingDriftCount: 5 }), 5);
  assert.match(source, /function collectOptionValues\(flag, argsList = rawArgs\)/);
  assert.match(source, /!argsList\[index \+ 1\]\.startsWith\("--"\)/);
  assert.match(source, /function actionableDriftCountFromPayload\(payload\)/);
  assert.equal(source.includes("actionableDriftCount || driftSnapshot.payload?.blockingDriftCount || 0"), false);
}

function testMeasurePerfInvalidThresholdFallback() {
  const output = execFileSync(process.execPath, ["scripts/measure-large-data-performance.mjs"], {
    cwd: root,
    encoding: "utf8",
    env: {
      ...process.env,
      JOOPARK_PERF_ISSUES: "100",
      JOOPARK_PERF_STORAGE_ITEMS: "50",
      JOOPARK_PERF_SAMPLES: "1",
      JOOPARK_PERF_WARMUPS: "0",
      JOOPARK_PERF_MAX_KANBAN_MODEL_MS: "bad",
    },
  });
  const summary = JSON.parse(output);
  assert.equal(summary.status, "pass");
  assert.equal(summary.thresholds.maxKanbanModelMs, 150);
  assert.equal(summary.thresholds.maxKanbanModelMs === null, false);
}

testWorkspaceStorage();
await testWorkspaceStorageArtifactMirrorAndHydration();
testDashboardStorageConfidenceBounds();
testStorageStatusRecoveryView();
testKanbanHelpers();
testImportGuards();
testRuntimeErrorBoundary();
await testPwaRuntimeUpdateReadyToast();
await testPwaRuntimeControllerChangeAppliedToast();
await testPwaRuntimeFirstInstallStaysQuiet();
testCalendarViewModelAndEscapes();
testTodoViewModelAndEscapes();
testNotesViewModelAndEscapes();
testHabitsViewModelAndEscapes();
testStatsViewModelAndEscapes();
testDashboardConfidenceBounds();
testDashboardAutoresearchConfidenceBounds();
testCommandPaletteBuildRenderAndEscapes();
testCommandPaletteUnusedAppWrappersRemoved();
testImportGuardUnusedAppWrappersRemoved();
testGlobalSearchUnusedAppWrappersRemoved();
testReviewStateUnusedAppWrappersRemoved();
testReviewIssuePayloadUnusedAppWrappersRemoved();
testHomeExecutionUnusedAppWrappersRemoved();
testCalendarUnusedAppWrapperRemoved();
testTodoUnusedAppWrappersRemoved();
testDialogShellUnusedAppWrapperRemoved();
testProjectPickerThinAppWrappersRemoved();
testInteractionSetupSingleUseAppWrapperRemoved();
testFooterClockSingleUseAppWrapperRemoved();
testEventReminderSingleUseAppWrapperRemoved();
testGlobalSearchStateAndEscapes();
testReviewExecutionChecklistHelpers();
testReviewIssuePayloadHelpers();
testReviewCreationActionsFiniteEstimate();
testReviewResultStateHelpers();
testPackagedBrowserGateContextParity();
testLlmWikiSmokeReadinessGuards();
testDesktopSmokeNavigationLoadGuard();
testProductSmokeUsesLock();
testProductSmokeLockHeartbeatStaleness();
testProductSmokePortOptionFallbacks();
testAuditReleaseSmokeLockWaitDoesNotConsumeAttemptBudget();
testAuditIncompletePackagedGateDoesNotCascadeBrowserSubchecks();
testReleaseReadinessSummaryPrefersFreshGateEvidenceCache();
testReleaseLockTimeoutFallbacks();
testReleaseReadinessFormatOption();
testRemoteWorkflowFileCheckFallbackAuditGuard();
testLaunchReadinessOptionValueGuard();
testOutputQualityOptionValueGuard();
testOutputQualityAcceptanceLedgerCountsPreserveExplicitZero();
testOutputQualityWorkflowUiReceiptCountsPreserveExplicitZero();
testOutputQualityPostAuthCheckpointCountsPreserveExplicitZero();
testOutputQualityReleaseGateBrowserEvidenceCountsPreserveExplicitZero();
testOutputQualityReleaseGateBrowserEvidenceAccessSurfacesPreserveExplicitZero();
testOutputQualityReleaseGateBrowserEvidenceReviewPackageCountsPreserveExplicitZero();
testOutputQualityPostInstallIntakeCountsPreserveExplicitZero();
testOutputQualityOperatorOnePageHandoffCountsPreserveExplicitZero();
testOutputQualityBlockerResolutionCountsPreserveExplicitZero();
testOutputQualityLaunchProofEvidenceReceiptCountsPreserveExplicitZero();
testOutputQualityPagesAttestationProofCountsPreserveExplicitZero();
testOutputQualityHandoffVerifierArtifactCountsPreserveExplicitZero();
testOutputQualityPostInstallProofParserCountsPreserveExplicitZero();
testOutputQualityLaunchExecutionPacketCountsPreserveExplicitZero();
testOutputQualityAccessSurfaceCountsPreserveExplicitZero();
testOutputQualityPublishEvidenceCommandGuardCoveragePreserveExplicitZero();
testOutputQualityWorkflowAuthPreflightFieldsPreserveExplicitZero();
testOutputQualityPreviousEvidenceAccessSurfaceCountsPreserveExplicitZero();
testHomeLaunchActionCountsPreserveExplicitZero();
testHomeLaunchInstallMatrixCountsPreserveExplicitZero();
testLaunchClaimReadinessRequiresBothArtifacts();
testHomeRemoteWorkflowLedgerCountsPreserveExplicitZero();
testHomeLaunchProofLedgerCountsPreserveExplicitZero();
testHomeLaunchBlockerResolverCountsPreserveExplicitZero();
testHomePostInstallQuickProofCountsPreserveExplicitZero();
testHomeExternalClaimGuardCountsPreserveExplicitZero();
testReleaseStatusWorkflowUiInstallCoveragePreservesExplicitZero();
testReleaseStatusExternalClaimGuardCountsPreserveExplicitZero();
testReleaseStatusLaunchReadinessFreshnessCountsPreserveExplicitZero();
testReleaseStatusPostAuthCheckpointCountsPreserveExplicitZero();
testReleaseStatusLaunchBlockerResolverCountsPreserveExplicitZero();
testReleaseStatusInstallPathCountsDeriveFromSourcePaths();
testReleaseStatusExternalClaimCloseoutCountsPreserveExplicitZero();
testReleaseStatusOutputQualitySourceEvidenceStaleCountPreservesExplicitZero();
testReleaseStatusVerifyWorkspaceNextCandidateCountPreservesExplicitZero();
testReleaseStatusLaunchInstallMatrixCountsPreserveExplicitZero();
testReleaseStatusRemoteWorkflowLedgerCountsPreserveExplicitZero();
testReleaseStatusPostInstallIntakeCountsPreserveExplicitZero();
testProductLoopSummaryOptionValueGuard();
testGithubProjectDiscoveryOptionValueGuard();
testOutputQualityPublishInstallPathRepairAwareCoverage();
testPublishDispatchOptionValueGuard();
testRemoteWorkflowCheckOptionValueGuard();
testRemoteWorkflowInstallerOptionValueGuard();
testWorkflowUiInstallRepairAwareActions();
testMainBridgeOptionValueGuard();
testPublishEvidenceRepairFirstCommand();
testPublishEvidenceOptionValueGuard();
testLaunchHandoffOptionValueGuard();
testLaunchExecutionPacketOptionValueGuard();
testLaunchExecutionPacketTextCountsPreserveExplicitZero();
testLaunchExecutionRepairAwareGithubUiPath();
testMobileSmokeNumericFallbacks();
testBrowserSmokeTimeoutFallbacks();
testCapturePreviewInlineOptions();
testProductSmokeCloseUnrefsForcedServer();
testProductSmokeCliExitsAfterFlushedSuccess();
testFullVerifyRefreshesPackagedBrowserGates();
testPagesAttestationBlankTemplateGuard();
testPagesAttestationOptionValueGuard();
testRefreshCandidateSnapshotLiveDriftBuffer();
testCandidateFreshnessDriftRepoOptionValueGuard();
testRefreshCandidateSnapshotRepoOptionValueGuard();
testMeasurePerfInvalidThresholdFallback();

console.log("PASS pure helper unit tests");
