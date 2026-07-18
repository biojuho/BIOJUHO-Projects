#!/usr/bin/env node

import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
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

const PWA_TEST_ORIGIN = "http://127.0.0.1:5178";
const PWA_TEST_SW_URL = `${PWA_TEST_ORIGIN}/sw.js`;

function pwaRuntimeFixture(options = {}) {
  const runtime = loadRuntime("pwa-runtime.js");
  const toasts = [];
  const reloads = [];
  const refreshes = [];
  const loadCallbacks = [];
  const hasActiveWorker = Object.prototype.hasOwnProperty.call(options, "activeWorker");
  const activeWorker = hasActiveWorker
    ? options.activeWorker
    : { scriptURL: `${PWA_TEST_SW_URL}?v=1` };
  const worker = options.worker || eventTargetMock({
    state: options.workerState || "installing",
    scriptURL: options.workerScriptURL || PWA_TEST_SW_URL,
  });
  const registration = options.registration || eventTargetMock({
    active: activeWorker,
    installing: worker,
    waiting: null,
    scope: `${PWA_TEST_ORIGIN}/`,
  });
  const hasController = Object.prototype.hasOwnProperty.call(options, "controller");
  const serviceWorker = options.serviceWorker || eventTargetMock({
    controller: hasController ? options.controller : activeWorker,
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
    showToast(message, tone, toastOptions) {
      toasts.push({ message, tone, options: toastOptions });
    },
  });
  return {
    api,
    activeWorker,
    loadCallbacks,
    refreshes,
    registration,
    reloads,
    serviceWorker,
    toasts,
    worker,
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

  // Extra-key array-of-objects (e.g. externalResearchSources) must keep object
  // structure, not be flattened to "[object Object]" by cleanStringArray.
  const withSources = storage.normalizeDashboardRecord({
    id: "src",
    summary: "S",
    externalResearchSources: [
      { id: "s1", title: "Doc", url: "https://example.com", confidence: 0.8 },
      { id: "s2", title: "Paper", url: "https://example.org", confidence: 0.6 },
    ],
  }, { confidence: 0.65 });
  assert.equal(Array.isArray(withSources.externalResearchSources), true);
  assert.equal(withSources.externalResearchSources[0].title, "Doc");
  assert.equal(withSources.externalResearchSources[1].url, "https://example.org");
  assert.equal(JSON.stringify(withSources).includes("[object Object]"), false);
  // Plain string arrays still normalize as strings.
  const withTags = storage.normalizeDashboardRecord({ id: "t", summary: "S", tags: ["a", "b"] }, { confidence: 0.65 });
  assert.deepEqual(withTags.tags, ["a", "b"]);
}

function testEventReminderStartIsIdempotent() {
  const runtime = loadRuntime("event-reminders.js");
  let intervals = 0, cleared = 0, nextId = 1;
  const reminders = runtime.JooParkEventReminders.create({
    window: {},
    setInterval: () => { intervals += 1; return nextId++; },
    clearInterval: () => { cleared += 1; },
    Notification: function () {},
    eventsOn: () => [],
    todayISO: () => "2026-06-15",
  });
  const id1 = reminders.start();
  const id2 = reminders.start();
  assert.equal(intervals, 1, "start() must not create a second interval (init + permission-grant both call it)");
  assert.equal(id1, id2);
  reminders.stop();
  assert.equal(cleared, 1);
  const id3 = reminders.start();
  assert.equal(intervals, 2, "start() after stop() creates a fresh interval");
  assert.notEqual(id3, id1);
}

function testWikiLocalDocLinksResolve() {
  // The LLM wiki registry links to bundled local docs (url: "./docs/..."); a
  // broken path renders a dead reference. Verify every local url resolves so a
  // future doc rename/removal fails the gate instead of shipping a dead link.
  const source = readFileSync(join(root, "llm-wiki-view.js"), "utf8");
  const localUrls = [...source.matchAll(/url:\s*"(\.\/[^"]+)"/g)].map((m) => m[1]);
  assert.ok(localUrls.length >= 5, "expected the wiki registry to reference local docs");
  for (const rel of localUrls) {
    assert.ok(existsSync(join(root, rel)), `wiki links to a missing local doc: ${rel}`);
  }
}

function testPipelineMatrixRenders() {
  // 제약 파이프라인 보드: 하나의 컴포넌트가 자산 × 워크스트림 매트릭스를
  // 7×5로 찍어내고, 셀 드릴다운이 마일스톤·WBS·위키 딥링크를 만들며,
  // 토큰/시드/저장 배선이 무너지지 않았는지 한 번에 검증한다.
  const runtime = loadRuntime("pipeline-view.js");
  assert.ok(runtime.JooParkPipelineView && typeof runtime.JooParkPipelineView.create === "function", "pipeline view exports create");
  const view = runtime.JooParkPipelineView.create({ html, raw, escapeHtml, kpiCard: () => "", panelHead: (t) => `<h2>${t}</h2>`, matches: () => true });

  const assets = [
    { id: "PX301", name: "PX301", modality: "샘플 바이오", indication: "샘플 적응증", stage: "preclinical" },
    { id: "RX101", name: "RX101", modality: "미정", indication: "미정", stage: "planned" },
  ];
  const cells = {
    "PX301:efficacy": {
      status: "preclinical", phaseLabel: "비임상 효능 샘플", owner: "효능팀", nextAction: "후속",
      riskFlags: ["efficacy-signal"], lastUpdated: "2026-06-15",
      docLink: { category: "sample-pipeline", article: "sample-efficacy-study" },
      milestones: [{ id: "m1", label: "유도", date: null, done: true }],
      wbs: [{ id: "EFF-1", name: "모델", status: "done", owner: "효능팀", deps: [], children: [
        { id: "EFF-1a", name: "정성 리뷰", status: "done", owner: "효능팀", deps: [], children: [] },
      ] }],
    },
  };

  const out = view.renderPipelineHTML({ assets, cells, query: "" });
  assert.equal(typeof out, "string");
  const cellButtons = (out.match(/data-action="open-pipeline-cell"/g) || []).length;
  assert.equal(cellButtons, assets.length * view.WORKSTREAMS.length, "matrix renders one button per asset × workstream");
  assert.ok(/data-asset="PX301"/.test(out) && /data-ws="efficacy"/.test(out), "matrix wires asset × workstream into data attrs");
  assert.ok(out.includes("데이터 없음"), "dataless cells render an empty-state button");

  const body = view.cellSheetBody({ asset: assets[0], ws: view.WORKSTREAMS[0], cell: cells["PX301:efficacy"] });
  assert.ok(/data-action="open-pipeline-wiki"/.test(body) && /data-article="sample-efficacy-study"/.test(body), "drill-down links to the wiki article");
  assert.ok(/<details/.test(body), "WBS tree renders nested <details>");

  const emptyBody = view.cellSheetBody({ asset: assets[1], ws: view.WORKSTREAMS[1], cell: null });
  assert.ok(emptyBody.includes("표준 WBS 템플릿"), "empty cell shows the workstream WBS template");

  // 게이트 패리티: 연결된 위키 article/category id가 실제로 존재해야 한다.
  const wikiSource = readFileSync(join(root, "llm-wiki-view.js"), "utf8");
  assert.ok(wikiSource.includes('id: "sample-efficacy-study"') && wikiSource.includes('id: "sample-formulation-plan"'), "pipeline links to real wiki article ids");
  assert.ok(wikiSource.includes('id: "sample-pipeline"'), "wiki has the sample pipeline category");

  // 토큰 규율: 모듈에 raw hex 색이 없어야 한다(var(--*)만).
  const moduleSource = readFileSync(join(root, "pipeline-view.js"), "utf8");
  assert.ok(!/#[0-9a-fA-F]{3,8}\b/.test(moduleSource), "pipeline-view must use var(--*) tokens, not raw hex");

  // 시드/저장 패리티: 7자산 + persist/apply 양쪽 배선.
  const seedSource = readFileSync(join(root, "workspace-seed-data.js"), "utf8");
  assert.ok(/pipeline:\s*\{/.test(seedSource), "seed defines a pipeline slice");
  ["RX101", "RX201", "RX202", "PX301", "RX302", "RX401", "RX601"].forEach((id) => {
    assert.ok(seedSource.includes(`"${id}"`), `seed includes asset ${id}`);
  });
  const storageSource = readFileSync(join(root, "workspace-storage.js"), "utf8");
  assert.ok(/pipeline:\s*dashboard\.pipeline/.test(storageSource), "persistPayload writes pipeline");
  assert.ok(/rawV3\.pipeline/.test(storageSource), "applyV3Payload reads pipeline");

  // 검색 계약: 행마다 data-search-result 훅, 무결과+검색어면 공용 search empty state.
  assert.equal((out.match(/data-search-result="pm-pipeline"/g) || []).length, assets.length, "each asset row carries the search-result hook");
  assert.ok(/aria-rowcount="3"/.test(out) && /aria-colcount="6"/.test(out), "matrix exposes aria row/col counts");
  const viewWithEmpty = runtime.JooParkPipelineView.create({ html, raw, escapeHtml, kpiCard: () => "", panelHead: (t) => `<h2>${t}</h2>`, matches: () => false, searchEmptyState: (kind, title) => `<div data-search-empty="${kind}">${title}</div>` });
  const emptyOut = viewWithEmpty.renderPipelineHTML({ assets, cells, query: "zzz" });
  assert.ok(/data-search-empty="pm-pipeline"/.test(emptyOut), "query with no match renders the shared search empty state");

  // 백업 왕복/초기화 계약: export·import·reset이 pipeline 슬라이스를 다룬다.
  const appSource = readFileSync(join(root, "app.js"), "utf8");
  assert.ok(/pipeline:\s+dashboard\.pipeline,/.test(appSource), "exportData includes the pipeline slice");
  assert.ok(appSource.includes("dashboard.pipeline = { assets: [], cells: {} };"), "reset clears the pipeline slice");
  const importUiSource = readFileSync(join(root, "backup-import-ui.js"), "utf8");
  assert.ok(importUiSource.includes("isPlainObject(source.pipeline)"), "applyImported restores the pipeline slice");
  const importGuardsSource = readFileSync(join(root, "backup-import-guards.js"), "utf8");
  assert.ok(importGuardsSource.includes("pipelineAssets") && importGuardsSource.includes("pipelineCells"), "import guards bound pipeline sizes");

  // 위키 딥링크 포커스 계약: 시트 닫기 후 stale 포커스 복원 없이 문서 헤딩으로 이동.
  assert.ok(/open-pipeline-wiki[\s\S]{0,200}closeSheet\(\{ restoreFocus: false \}\)/.test(appSource), "wiki deep link closes the sheet without restoring stale focus");
}

function testKeyboardShortcutInteractionGuards() {
  const runtime = loadRuntime("keyboard-shortcuts.js");
  const calls = [];
  const make = (over = {}) => runtime.JooParkKeyboardShortcuts.create({
    document: { activeElement: { tagName: "BUTTON", closest: () => null } },
    getCurrentView: () => over.view || "home",
    isPaletteOpen: () => false,
    projectPickerIsOpen: () => over.pickerOpen === true,
    setView: (v) => calls.push(`setView:${v}`),
    setCalendarMode: (m) => calls.push(`calMode:${m}`),
    openEventModal: () => calls.push("event"),
  });
  const ev = (key) => ({ key, metaKey: false, ctrlKey: false, altKey: false, shiftKey: false, target: { closest: () => null }, preventDefault() {} });

  // #1: single-key shortcuts must be suppressed while the project picker is open.
  calls.length = 0;
  make({ pickerOpen: true }).handleKeydown(ev("n"));
  assert.equal(calls.length, 0, "single-key shortcut must not fire over an open project picker");
  // Sanity: with the picker closed, 'n' on home opens the new-item modal.
  calls.length = 0;
  make({ pickerOpen: false }).handleKeydown(ev("n"));
  assert.deepEqual(calls, ["event"]);

  // #3: on the calendar, a pending g-chord beats the m/w/d mode switch.
  calls.length = 0;
  const ksCal = make({ view: "cal" });
  ksCal.handleKeydown(ev("g"));
  ksCal.handleKeydown(ev("m"));
  assert.deepEqual(calls, ["setView:notes"], "g m on calendar navigates to notes, not month mode");
  // Sanity: a plain 'm' (no preceding g) still switches calendar mode.
  calls.length = 0;
  make({ view: "cal" }).handleKeydown(ev("m"));
  assert.deepEqual(calls, ["calMode:month"]);

  // #2: the command palette stops Escape from bubbling to the document handler
  // (so one Esc doesn't also close an underlying modal).
  const paletteSource = readFileSync(join(root, "command-palette.js"), "utf8");
  assert.match(paletteSource, /event\.key === "Escape"\) \{\s*event\.preventDefault\(\);\s*\/\/[\s\S]*?event\.stopPropagation\(\);\s*close\(\);/);
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
  const usage = view.storageUsageSummary(11, 1000);
  assert.equal(usage.usagePct, 1.2);
  assert.equal(usage.usagePctLabel, "1.2%");
  assert.equal(usage.meterWidth, 3);
  assert.equal(usage.quotaLabel, "1000 B");
  const statusModel = view.storageStatusModel({ usageBytes: 11, quotaBytes: 1000 });
  assert.equal(statusModel.usagePctLabel, usage.usagePctLabel);
  assert.equal(statusModel.meterWidth, usage.meterWidth);
  const unknownUsageView = runtime.JooParkStorageStatusView.create({
    html,
    raw,
    formatBytes: (bytes) => `${bytes} B`,
    storagePercent: () => null,
  });
  const unknownUsage = unknownUsageView.storageUsageSummary(11, null);
  assert.equal(unknownUsage.usagePct, null);
  assert.equal(unknownUsage.usagePctLabel, "추정치 없음");
  assert.equal(unknownUsage.meterWidth, 3);
  assert.equal(unknownUsage.quotaLabel, "추정치 없음");
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

  // Round-trip: the app exports issues[].body (review/wiki/db-catalog issues) and
  // projects[].benchmark* (adoption candidates). Importing the app's own backup
  // must NOT be fatally rejected, and these fields must survive validation.
  const roundTripPayload = {
    projects: [{
      id: "proj-bench",
      name: "Bench Project",
      benchmarkFocus: { surface: "PM", flow: "f", signals: ["a", "b"], rubric: [{ axis: "입력", value: "x", weight: 0.25, score: 90 }] },
      workspaceBenchmark: { surface: "WS", flow: "w", signals: [], rubric: [] },
      knowledgeBaseBenchmark: { surface: "KB", flow: "k", signals: ["s"], rubric: [{ axis: "ax", value: "v", weight: 0.5, score: 80 }] },
    }],
    issues: [{
      id: "ISS-body",
      project: "proj-bench",
      title: "Has body",
      status: "todo",
      body: "# Review\nThis review issue body must survive import.",
    }],
  };
  const roundTrip = runtime.JooParkImportGuards.validateImportPayload(roundTripPayload);
  assert.equal(roundTrip.ok, true);
  assert.equal(roundTrip.violations.some((entry) => entry.fatal), false);
  assert.equal(roundTrip.normalized.issues[0].body, roundTripPayload.issues[0].body);
  assert.equal(roundTrip.normalized.projects[0].benchmarkFocus.rubric[0].score, 90);
  assert.equal(roundTrip.normalized.projects[0].benchmarkFocus.signals.length, 2);
  assert.equal(roundTrip.normalized.projects[0].knowledgeBaseBenchmark.surface, "KB");

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
  const { api, loadCallbacks, registration, reloads, toasts, worker } = pwaRuntimeFixture({
    activeWorker: { scriptURL: PWA_TEST_SW_URL },
    controller: { scriptURL: PWA_TEST_SW_URL },
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
  const { api, refreshes, registration, serviceWorker, toasts, worker } = pwaRuntimeFixture({
    workerScriptURL: `${PWA_TEST_SW_URL}?v=2`,
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
  const { api, refreshes, registration, serviceWorker, toasts, worker } = pwaRuntimeFixture({
    activeWorker: null,
    controller: null,
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
  assert.deepEqual(calendar.calendarEventsForDate(model, "2026-06-09").map((event) => event.id), ["evt-alpha"]);
  assert.deepEqual(calendar.calendarEventsForDate(model, "2026-06-12").map((event) => event.id), []);

  const unfilteredModel = calendar.calendarViewModel({
    events,
    todos: [],
    query: "",
    month: "2026-06",
    selected: "2026-06-09",
    mode: "week",
  });
  assert.deepEqual(calendar.calendarEventsForDate(unfilteredModel, "2026-06-12").map((event) => event.id), ["evt-beta"]);

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

function testTeamViewModelAndSummary() {
  const runtime = loadRuntime("team-view.js");
  const teamView = runtime.JooParkTeamView.create({
    html,
    raw,
    matches,
    kpiCard,
    panelHead: (title, _link, controls) => html`<header><h2>${title}</h2>${raw(controls || "")}</header>`,
    searchEmptyState,
    projectName: (id) => id === "p1" ? "Alpha Project" : id || "프로젝트",
  });
  const team = [
    { id: "m1", name: "Alpha <script>", role: "PM", load: 50, projects: ["p1"] },
    { id: "m2", name: "Beta", role: "Backend", load: 98 },
    { id: "m3", name: "Gamma", role: "Design", load: 100, onLeave: true },
    { id: "m4", name: "Delta", role: "QA", load: "bad" },
  ];
  const summary = teamView.teamLoadSummary(team);
  assert.equal(summary.total, 4);
  assert.equal(summary.avgLoad, 49);
  // Over-allocation counts only active members — Gamma is at 100 but on leave,
  // so it must not be flagged "조치 필요" (consistent with avgLoad excluding leave).
  assert.equal(summary.over, 1);
  assert.equal(summary.leave, 1);

  const model = teamView.teamViewModel({ team, projects: [], issues: [], query: "Alpha" });
  assert.equal(model.total, summary.total);
  assert.equal(model.avgLoad, summary.avgLoad);
  assert.equal(model.over, summary.over);
  assert.equal(model.leave, summary.leave);
  assert.deepEqual(model.list.map((member) => member.id), ["m1"]);

  const row = teamView.memberRow(team[0]);
  assert.match(row, /Alpha &lt;script&gt;/);
  assert.doesNotMatch(row, /<script>/);
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
  assert.equal(todo.todoSourceSummaryHTML(model), "");
  const wikiSourceSummary = todo.todoSourceSummaryHTML(wikiModel);
  assert.match(wikiSourceSummary, /data-todo-source-summary/);
  assert.match(wikiSourceSummary, /data-todo-source-summary-filter="wiki"/);
  assert.match(wikiSourceSummary, /data-todo-source-summary-count="1"/);
  assert.match(wikiSourceSummary, /LLM Wiki/);
  assert.match(wikiSourceSummary, /전체 출처 보기/);

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

function testTodoOverdueReschedule() {
  const runtime = loadRuntime("todo-view.js");
  const todo = runtime.JooParkTodoView.create({
    html,
    raw,
    todoPriority: { med: { label: "보통", color: "var(--cyan)" } },
    todoPrioRank: { med: 1 },
    todoFilters: [{ key: "active", label: "미완료" }],
    todoSourceFilters: [{ key: "all", label: "전체" }],
    dueLabel: (value) => ({ cls: "", text: value || "마감 없음" }),
    todayISO: () => "2026-06-09",
    addDaysISO,
    matches,
    formatKoreanShort: (value) => value,
    kpiCard,
    searchEmptyState,
  });

  // Pure reschedule rule: "today" snaps to today; "plus1" pushes one day past
  // the later of due/today so overdue items land on tomorrow.
  assert.equal(todo.rescheduleDue("2026-06-01", "today", "2026-06-09"), "2026-06-09");
  assert.equal(todo.rescheduleDue("2026-06-01", "plus1", "2026-06-09"), "2026-06-10");
  assert.equal(todo.rescheduleDue("2026-06-11", "plus1", "2026-06-09"), "2026-06-12");
  assert.equal(todo.rescheduleDue(null, "today", "2026-06-09"), "2026-06-09");
  assert.equal(todo.rescheduleDue(null, "plus1", "2026-06-09"), "2026-06-10");

  const overdueRow = todo.todoRow({ id: "late", title: "늦은 일", priority: "med", due: "2026-06-01", done: false });
  assert.match(overdueRow, /data-action="todo-reschedule" data-todo-id="late" data-due-mode="today"/);
  assert.match(overdueRow, /data-action="todo-reschedule" data-todo-id="late" data-due-mode="plus1"/);
  const futureRow = todo.todoRow({ id: "future", title: "미래 일", priority: "med", due: "2026-06-11", done: false });
  assert.doesNotMatch(futureRow, /todo-reschedule/);
  const doneRow = todo.todoRow({ id: "done", title: "끝난 일", priority: "med", due: "2026-06-01", done: true });
  assert.doesNotMatch(doneRow, /todo-reschedule/);

  const bucketList = todo.todoListHTML(todo.todoViewModel([
    { id: "late", title: "늦은 일", priority: "med", due: "2026-06-01", done: false },
    { id: "today", title: "오늘 일", priority: "med", due: "2026-06-09", done: false },
  ], "", "active", "all"));
  assert.match(bucketList, /data-action="todo-reschedule-overdue"/);
  assert.equal((bucketList.match(/data-action="todo-reschedule-overdue"/g) || []).length, 1);
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
  assert.equal(notesView.notesSourceSummaryHTML(model), "");
  const wikiSourceSummary = notesView.notesSourceSummaryHTML(wikiModel);
  assert.match(wikiSourceSummary, /data-note-source-summary/);
  assert.match(wikiSourceSummary, /data-note-source-summary-filter="wiki"/);
  assert.match(wikiSourceSummary, /data-note-source-summary-count="1"/);
  assert.match(wikiSourceSummary, /LLM Wiki/);
  assert.match(wikiSourceSummary, /전체 출처 보기/);

  const card = notesView.noteCard(notes[1]);
  assert.match(card, /Alpha &lt;script&gt;/);
  assert.match(card, /Body &lt;b&gt;/);
  assert.doesNotMatch(card, /<script>/);

  const empty = notesView.notesGridHTML(notesView.notesViewModel({ notes, query: "Missing <script>", sourceFilter: "all" }));
  assert.match(empty, /data-search-empty="notes"/);
  assert.doesNotMatch(empty, /<script>/);
}

function testNoteModalPreviewHelpers() {
  const runtime = loadRuntime("notes-view.js");
  const createNotesView = (renderMarkdown) => runtime.JooParkNotesView.create({
    html,
    raw,
    matches,
    safeNoteColor: (value) => value || "var(--cyan)",
    renderMarkdown,
    formatKoreanShort: (value) => value,
    localYmd: (value) => String(value || "").slice(0, 10),
    searchEmptyState,
    noteSourceFilters: [{ key: "all", label: "전체" }],
  });

  const markdownView = createNotesView((src) => `<p><strong>${src}</strong></p>`);
  const toggle = markdownView.noteModalModeToggleHTML();
  assert.match(toggle, /data-note-modal-mode-bar/);
  assert.match(toggle, /data-note-modal-mode="edit"/);
  assert.match(toggle, /data-note-modal-mode="preview"/);
  assert.match(toggle, /type="button"/);
  assert.equal(markdownView.noteModalPreviewHTML("**bold**"), "<p><strong>**bold**</strong></p>");
  assert.match(markdownView.noteModalPreviewHTML(""), /아직 내용이 없습니다/);

  // Renderer unavailable (null) → escaped plain-text fallback, never blank.
  const plainView = createNotesView(() => null);
  const fallback = plainView.noteModalPreviewHTML("plain <script>");
  assert.match(fallback, /note-modal-plain/);
  assert.match(fallback, /plain &lt;script&gt;/);
  assert.doesNotMatch(fallback, /<script>/);
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
  assert.deepEqual(JSON.parse(JSON.stringify(habitsView.habitWeekProgress(habits[0], model.weekDates))), {
    weekDone: 2,
    target: 3,
    rate: 67,
  });
  assert.equal(model.kpis[0].value, "1");
  assert.equal(model.kpis[1].value, "1");
  assert.equal(model.kpis[3].value, "4");

  const card = habitsView.habitCard(habits[0], model);
  assert.match(card, /Alpha &lt;script&gt;/);
  assert.match(card, /2\/3 <small>\(67%\)<\/small>/);
  assert.match(card, /width:67%;background:#2387ff/);
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
  assert.deepEqual(JSON.parse(JSON.stringify(statsView.todoCompletionStats(model.todos, weekDatesFor(model.today)[0], model.today))), {
    weekTodoDone: 1,
    totalDone: 1,
    totalRate: 50,
  });
  assert.deepEqual(JSON.parse(JSON.stringify(statsView.statsHabitProgress(model.activeHabits[0], model.today))), {
    weekDone: 1,
    target: 7,
    pct: 14,
  });

  const chart = statsView.barChart([{ label: "Alpha <script>", value: 2, color: "var(--cyan)" }]);
  assert.match(chart, /Alpha &lt;script&gt;/);
  assert.doesNotMatch(chart, /<script>/);

  const habitSummary = statsView.habitSummarySection(model);
  assert.match(habitSummary, /Alpha &lt;script&gt;/);
  assert.match(habitSummary, /1\/7일 · 🔥 1일 연속/);
  assert.match(habitSummary, /width:14%;background:var\(--cyan\)/);
}

function createStatsViewForTests(extraDeps = {}) {
  const runtime = loadRuntime("stats-view.js");
  return runtime.JooParkStatsView.create({
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
    eventCats: { deadline: { label: "마감", color: "var(--red)" }, etc: { label: "기타", color: "var(--cyan)" } },
    eventCatOrder: ["deadline", "etc"],
    weekdaysKo: ["일", "월", "화", "수", "목", "금", "토"],
    ...extraDeps,
  });
}

function testStatsViewIgnoresStaleCompletedAt() {
  const statsView = createStatsViewForTests();
  // A todo unchecked after completion may carry a stale completedAt in legacy
  // localStorage data — no completion surface may count it.
  const model = statsView.statsViewModel({
    todos: [
      { id: "stale", createdAt: "2026-06-01T08:00:00", done: false, completedAt: "2026-06-09T09:00:00" },
      { id: "done", createdAt: "2026-06-01T08:00:00", done: true, completedAt: "2026-06-09T09:00:00" },
    ],
    habits: [],
    events: [],
  });
  assert.equal(model.kpis[0].value, "1");
  assert.equal(model.completedByDay.at(-1), 1);
  assert.deepEqual(JSON.parse(JSON.stringify(model.doneByWeekday)), [0, 0, 1, 0, 0, 0, 0]);
}

function testStatsViewExpandsRecurringDeadlines() {
  const occurrences = [
    { id: "weekly-deadline", category: "deadline", date: "2026-06-10", _masterId: "weekly-deadline", _occ: true },
  ];
  const statsView = createStatsViewForTests({
    expandOccurrences: (start, end) => occurrences.filter((event) => event.date >= start && event.date <= end),
  });
  // Master date is long past, but the injected expander surfaces this week's
  // occurrence — the 7-day deadline KPI must count occurrences, not masters.
  const model = statsView.statsViewModel({
    todos: [],
    habits: [],
    events: [{ id: "weekly-deadline", category: "deadline", date: "2024-01-07", repeat: "weekly" }],
  });
  assert.equal(model.kpis[3].value, "1");
}

function testNotesSortStableForEqualUpdatedAt() {
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
    noteSourceFilters: [{ key: "all", label: "전체" }],
  });
  // Imported/legacy notes can share or lack updatedAt; the comparator must
  // return 0 for ties so input order is preserved (sort contract + stability).
  const sameStamp = notesView.notesViewModel({
    notes: [
      { id: "first", title: "A", body: "", updatedAt: "2026-06-09T10:00:00" },
      { id: "second", title: "B", body: "", updatedAt: "2026-06-09T10:00:00" },
    ],
    query: "",
    sourceFilter: "all",
  });
  assert.deepEqual(sameStamp.list.map((note) => note.id), ["first", "second"]);
  const missingStamp = notesView.notesViewModel({
    notes: [
      { id: "older", title: "A", body: "" },
      { id: "newer", title: "B", body: "" },
    ],
    query: "",
    sourceFilter: "all",
  });
  assert.deepEqual(missingStamp.list.map((note) => note.id), ["older", "newer"]);
}

function extractAppFunction(appSource, name, nextMarker) {
  const start = appSource.indexOf(`function ${name}(`);
  const end = appSource.indexOf(nextMarker, start);
  assert.ok(start >= 0 && end > start, `could not extract ${name} from app.js`);
  return appSource.slice(start, end);
}

function testExpandOccurrencesFastForwardsOldSeries() {
  const appSource = readFileSync(join(root, "app.js"), "utf8");
  const source = extractAppFunction(appSource, "expandOccurrences", "\nfunction occurrencesOn");
  const sandbox = {
    dashboard: { events: [] },
    addDaysISO,
    daysBetweenLocal: (a, b) => Math.round((dateFromISO(b) - dateFromISO(a)) / 86400000),
  };
  vm.createContext(sandbox);
  vm.runInContext(`${source}; this.expandOccurrences = expandOccurrences;`, sandbox, { filename: "app.js#expandOccurrences" });

  // A daily series started >750 days before the queried range must still
  // surface — the step cap bounds in-range occurrences, not series age.
  sandbox.dashboard.events = [{ id: "old-daily", title: "스탠드업", date: "2024-01-01", repeat: "daily" }];
  const june = sandbox.expandOccurrences("2026-06-01", "2026-06-30");
  assert.equal(june.length, 30);
  assert.equal(june[0].date, "2026-06-01");
  assert.equal(june.at(-1).date, "2026-06-30");

  sandbox.dashboard.events = [{ id: "old-weekly", title: "주간 회의", date: "2024-01-01", repeat: "weekly", exceptions: ["2026-06-08"] }];
  const weekly = sandbox.expandOccurrences("2026-06-01", "2026-06-30");
  assert.deepEqual(JSON.parse(JSON.stringify(weekly.map((event) => event.date))), ["2026-06-01", "2026-06-15", "2026-06-22", "2026-06-29"]);

  sandbox.dashboard.events = [{ id: "old-monthly", title: "월말 정산", date: "2024-01-31", repeat: "monthly" }];
  const monthly = sandbox.expandOccurrences("2026-06-01", "2026-06-30");
  assert.deepEqual(JSON.parse(JSON.stringify(monthly.map((event) => event.date))), ["2026-06-30"]);

  // repeatUntil before the range still ends the series.
  sandbox.dashboard.events = [{ id: "ended", title: "끝난 일정", date: "2024-01-01", repeat: "daily", repeatUntil: "2025-12-31" }];
  assert.equal(sandbox.expandOccurrences("2026-06-01", "2026-06-30").length, 0);
}

function testHabitStreakGivesTodayGrace() {
  const appSource = readFileSync(join(root, "app.js"), "utf8");
  const source = extractAppFunction(appSource, "habitStreak", "\nfunction daysBetweenISO");
  const sandbox = {
    todayISO: () => "2026-06-15",
    addDaysISO,
    sortedStrings: (values) => [...values].sort(),
    daysBetweenISO: (a, b) => Math.round((dateFromISO(b) - dateFromISO(a)) / 86400000),
  };
  vm.createContext(sandbox);
  vm.runInContext(`${source}; this.habitStreak = habitStreak;`, sandbox, { filename: "app.js#habitStreak" });

  // A 7-day run ending yesterday is still "current" before today is checked in.
  const log = {};
  for (let i = 1; i <= 7; i += 1) log[addDaysISO("2026-06-15", -i)] = true;
  assert.equal(sandbox.habitStreak({ log }).current, 7);

  // Checking today extends the same run to 8 — grace never double-counts.
  assert.equal(sandbox.habitStreak({ log: { ...log, "2026-06-15": true } }).current, 8);

  // A gap before yesterday means no live streak (grace covers only today).
  assert.equal(sandbox.habitStreak({ log: { "2026-06-13": true } }).current, 0);
  assert.equal(sandbox.habitStreak({ log: {} }).current, 0);
}

function testCompareEventsIsTotalOrder() {
  const appSource = readFileSync(join(root, "app.js"), "utf8");
  const source = extractAppFunction(appSource, "compareEventsByDateAllDayStart", "\nfunction sortEvents");
  const sandbox = {};
  vm.createContext(sandbox);
  vm.runInContext(`${source}; this.cmp = compareEventsByDateAllDayStart;`, sandbox, { filename: "app.js#compareEvents" });
  const cmp = sandbox.cmp;
  // Equal date+allDay+start must compare to 0 (antisymmetry), not 1 both ways.
  const a = { date: "2026-06-15", allDay: false, start: "09:00" };
  const b = { date: "2026-06-15", allDay: false, start: "09:00" };
  assert.equal(cmp(a, b), 0);
  assert.equal(cmp(b, a), 0);
  // Ordering still holds for genuinely different keys.
  assert.equal(cmp({ date: "2026-06-15", start: "08:00" }, { date: "2026-06-15", start: "09:00" }), -1);
  assert.equal(cmp({ date: "2026-06-15", start: "10:00" }, { date: "2026-06-15", start: "09:00" }), 1);
  assert.equal(cmp({ date: "2026-06-14" }, { date: "2026-06-15" }), -1);
  assert.equal(cmp({ date: "2026-06-15", allDay: true, start: "09:00" }, { date: "2026-06-15", allDay: false, start: "08:00" }), -1);
}

function testLightThemeAccentContrastMeetsWcagAA() {
  // WCAG 2.2 SC 1.4.3: normal text needs >=4.5:1. Light-theme accent tokens are
  // used as small status/KPI text on the page bg, so they must clear AA. Parse the
  // [data-theme="light"] block and assert each accent against #eef2f8.
  const css = readFileSync(join(root, "styles.css"), "utf8");
  const block = css.slice(css.indexOf('[data-theme="light"] {'));
  const tokenValue = (name) => {
    const m = block.match(new RegExp(`--${name}:\\s*(#[0-9a-fA-F]{6})`));
    assert.ok(m, `light --${name} token not found`);
    return m[1];
  };
  const hex = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
  const lin = (c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
  const lum = (rgb) => { const [r, g, b] = rgb.map(lin); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
  const ratio = (a, b) => { const la = lum(hex(a)), lb = lum(hex(b)); return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05); };
  const bg = tokenValue("bg"); // #eef2f8
  for (const accent of ["blue", "cyan", "green", "amber", "red"]) {
    const r = ratio(tokenValue(accent), bg);
    assert.ok(r >= 4.5, `light --${accent} contrast ${r.toFixed(2)} < 4.5 on bg ${bg}`);
  }
  // Body text and muted must also clear AA on the page bg.
  assert.ok(ratio(tokenValue("text"), bg) >= 4.5, "light --text below AA");
  assert.ok(ratio(tokenValue("muted"), bg) >= 4.5, "light --muted below AA");
}

function testRouteChangeAccessibilityWired() {
  // Guard the SPA route-change a11y contract against churn: a polite live-region
  // announcer in the DOM, and setView focusing/announcing only on real changes
  // after first paint (WCAG 2.4.3 + dynamic-content announcement).
  const indexSource = readFileSync(join(root, "index.html"), "utf8");
  assert.match(indexSource, /id="routeAnnouncer"[^>]*aria-live="polite"/);
  const appSource = readFileSync(join(root, "app.js"), "utf8");
  assert.match(appSource, /if \(options\.viewChanged\) announceRouteChange\(name\)/);
  assert.match(appSource, /function announceRouteChange\(name\)/);
  assert.match(appSource, /if \(!routeNavReady\) return;/);
  assert.match(appSource, /routeNavReady = true;/);
  // Must compute a typing guard and prefer heading focus over the live region
  // (no double-announce: live region only fires when not focusing a heading).
  assert.match(appSource, /const typing = /);
  assert.match(appSource, /if \(!typing && heading\)/);
}

function testHomeExecutionQueueIncludesUpcomingTodos() {
  // Personal todos must use the same week horizon as PM issues so the "이번 주"
  // (upcoming) bucket can hold todos, not only issues.
  const source = readFileSync(join(root, "app.js"), "utf8");
  assert.match(source, /const todoItems = openTodos\s*\n\s*\.filter\(\(todo\) => todo\.due && todo\.due <= weekEnd\)/);
  assert.equal(source.includes(".filter((todo) => todo.due && todo.due <= today)"), false);
}

function testToggleTodoClearsCompletedAtOnUncheck() {
  const appSource = readFileSync(join(root, "app.js"), "utf8");
  assert.match(appSource, /t\.done = !t\.done;\n  if \(t\.done\) t\.completedAt = nowISO\(\);\n  else delete t\.completedAt;/);
}

function testCrudDataIntegrityGuards() {
  const appSource = readFileSync(join(root, "app.js"), "utf8");
  // Bug 1: editing a recurring event resets exceptions when the recurrence
  // identity (rule type or anchor date) changes, so old skips can't become
  // phantom gaps on the new series.
  assert.match(appSource, /const recurrenceChanged = \(ev\.repeat \|\| "none"\) !== repeat \|\| \(ev\.date \|\| ""\) !== date;/);
  assert.match(appSource, /const exceptions = \(!recurrenceChanged && Array\.isArray\(ev\.exceptions\)\) \? ev\.exceptions : \[\];/);
  // Bug 2: restoring an issue/task refuses to resurrect an orphan whose project
  // was deleted, and scrubs dangling assignee/owner/deps references.
  assert.match(appSource, /이 이슈의 프로젝트가 삭제되어 복구할 수 없습니다/);
  assert.match(appSource, /이 작업의 프로젝트가 삭제되어 복구할 수 없습니다/);
  assert.match(appSource, /if \(record\.assignee && !recordById\(dashboard\.team, record\.assignee\)\) record\.assignee = "";/);
  assert.match(appSource, /record\.deps = record\.deps\.filter\(\(depId\) => taskById\(depId\)\);/);
  // Bug 3: deleting a project scrubs the removed tasks from surviving tasks' deps.
  assert.match(appSource, /const removedTaskIds = new Set\(dashboard\.gantt\.tasks\.filter\(\(t\) => t\.project === id\)\.map\(\(t\) => t\.id\)\);/);
  assert.match(appSource, /t\.deps = t\.deps\.filter\(\(depId\) => !removedTaskIds\.has\(depId\)\);/);
  // Bug 4a: home-execution advance undo restores the original kanban slot, not bottom.
  assert.match(appSource, /const restoreBeforeId = previousIndex >= 0 && previousIndex \+ 1 < previousLane\.length/);
  assert.match(appSource, /insertIssueIntoKanbanLane\(current, previousStatus, restoreBeforeId \? \{ beforeId: restoreBeforeId \} : \{ position: "bottom" \}\);/);
}

function testHomeWeekDeadlinesUseOccurrences() {
  const source = readFileSync(join(root, "home-view.js"), "utf8");
  assert.match(source, /expandOccurrences\(today, weekEnd\)\.filter\(\(e\) => e\.category === "deadline"\)\.length \+/);
  assert.equal(source.includes('dashboard.events.filter((e) => e.category === "deadline" && e.date >= today && e.date <= weekEnd)'), false);
}

function testSeedDataAnchorsToToday() {
  const runtime = loadRuntime("workspace-seed-data.js");
  const seed = runtime.JooParkWorkspaceSeedData.create({ addDays: addDaysISO, today: "2026-06-12" });

  // Backups end today, queries ran today — the first run never looks stale.
  const backupDates = seed.backups.map((backup) => backup.date).sort();
  assert.equal(backupDates.at(-1), "2026-06-12");
  assert.equal(backupDates[0], "2026-05-14");
  seed.queries.forEach((query) => assert.match(query.lastRun, /^2026-06-12 \d{2}:\d{2}$/));

  // Open project deadlines sit in the future; gantt range brackets today.
  seed.projects.forEach((project) => assert.ok(project.deadline >= "2026-06-12", `${project.id} deadline ${project.deadline}`));
  assert.ok(seed.gantt.rangeStart < "2026-06-12" && seed.gantt.rangeEnd > "2026-06-12");

  // Only intended demo records stay overdue among non-done issues (PM-106).
  const overdueOpen = seed.issues.filter((issue) => issue.status !== "done" && issue.due < "2026-06-12").map((issue) => issue.id);
  assert.deepEqual(JSON.parse(JSON.stringify(overdueOpen)), ["PM-106"]);

  // Pending migrations stay scheduled in the future, applied ones in the past.
  seed.migrations.forEach((migration) => {
    if (migration.status === "pending") assert.ok(migration.scheduledAt > "2026-06-12", migration.id);
    if (migration.status === "applied") assert.ok(migration.appliedAt < "2026-06-12", migration.id);
  });

  // A different anchor shifts every relative date with it.
  const shifted = runtime.JooParkWorkspaceSeedData.create({ addDays: addDaysISO, today: "2027-01-01" });
  assert.equal(shifted.backups.map((backup) => backup.date).sort().at(-1), "2027-01-01");
}

function testGlobalSearchCountIncludesVirtualizedOverflow() {
  const source = readFileSync(join(root, "global-search.js"), "utf8");
  assert.match(source, /function virtualizedOverflowCount\(view\)/);
  assert.match(source, /\[data-todo-virtual-total\],\[data-kanban-virtual-total\]/);
  assert.match(source, /view\.querySelectorAll\("\[data-search-result\]"\)\.length \+ virtualizedOverflowCount\(view\)/);
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
	      currentProjectId: "p1",
	      issues: [
	        { id: "issue-wiki", title: "Wiki issue", project: "p1", sourceKind: "llm-wiki-action", sourceKey: "llm-wiki:issue:alpha" },
	        { id: "issue-db", title: "DB issue", project: "p1", sourceKind: "db-catalog-stale-review", sourceKey: "db-catalog:stale-sample-review" },
	        { id: "issue-review", title: "Review issue", project: "p1", sourceKind: "validated-review-result", sourceKey: "review:alpha" },
	        { id: "issue-workspace", title: "Workspace issue", project: "p1", sourceKey: "workspace-review:alpha" },
	        { id: "issue-kb", title: "KB issue", project: "p1", sourceKey: "kb-ia-review:alpha" },
	        { id: "issue-bench", title: "Bench issue", project: "p1", sourceKey: "benchmark-review:alpha" },
	        { id: "issue-source", title: "Source issue", project: "p1", sourceKind: "external-import" },
	        { id: "issue-local", title: "Local issue", project: "p1" },
	        { id: "issue-other-project", title: "Other project wiki", project: "p2", sourceKind: "llm-wiki-action", sourceKey: "llm-wiki:issue:other" },
	      ],
	      todos: [
	        { id: "todo-alpha", title: "Alpha <script>", category: "Ops", memo: "Beta", sourceKey: "llm-wiki:todo:alpha" },
	        { id: "todo-local", title: "Local task", category: "Ops", memo: "" },
      ],
      notes: [
        { id: "note-wiki", title: "Wiki note", body: "", sourceKey: "llm-wiki:note:alpha" },
        { id: "note-workspace", title: "Workspace note", body: "", sourceKey: "workspace-review:alpha" },
        { id: "note-kb", title: "KB note", body: "", sourceKey: "kb-ia-review:alpha" },
        { id: "note-benchmark", title: "PM note", body: "", sourceKey: "benchmark-review:alpha" },
        { id: "note-local", title: "Local note", body: "" },
      ],
      deletedItems: [{ id: "deleted" }],
    }),
    openTodoRecord: (todo) => { openedTodoId = todo.id; },
    formatKoreanShort: (value) => value,
  });

	  const items = palette.buildItems("Alpha <script>");
	  assert.equal(items.some((item) => item.label === "Alpha <script>"), true);
	  const kanbanSourceItems = palette.buildItems("source")
	    .filter((item) => item.group === "Kanban 필터");
	  assert.equal(kanbanSourceItems.length, 8);
	  const kanbanSourceSub = Object.fromEntries(kanbanSourceItems.map((item) => [item.label, item.sub]));
	  assert.equal(kanbanSourceSub["Kanban: 전체 출처 보기"], "source filter · all · 8건");
	  assert.equal(kanbanSourceSub["Kanban: LLM Wiki 출처 보기"], "source filter · LLM Wiki · 1건");
	  assert.equal(kanbanSourceSub["Kanban: DB Catalog 출처 보기"], "source filter · DB Catalog · 1건");
	  assert.equal(kanbanSourceSub["Kanban: Review 출처 보기"], "source filter · Review · 4건");
	  assert.equal(kanbanSourceSub["Kanban: Workspace Review 출처 보기"], "source filter · Workspace Review · 1건");
	  assert.equal(kanbanSourceSub["Kanban: KB/IA Review 출처 보기"], "source filter · KB/IA Review · 1건");
	  assert.equal(kanbanSourceSub["Kanban: PM Bench Review 출처 보기"], "source filter · PM Bench Review · 1건");
	  assert.equal(kanbanSourceSub["Kanban: 기타 Source 보기"], "source filter · Source · 1건");
	  const personalSourceItems = palette.buildItems("source")
	    .filter((item) => item.group === "개인 출처 필터");
  assert.equal(personalSourceItems.length, 8);
  const personalSourceSub = Object.fromEntries(personalSourceItems.map((item) => [item.label, item.sub]));
  assert.equal(personalSourceSub["할 일: 전체 출처 보기"], "source filter · all · 2건");
  assert.equal(personalSourceSub["할 일: LLM Wiki 출처 보기"], "source filter · LLM Wiki · 1건");
  assert.equal(personalSourceSub["메모: 전체 출처 보기"], "source filter · all · 5건");
  assert.equal(personalSourceSub["메모: LLM Wiki 출처 보기"], "source filter · LLM Wiki · 1건");
  assert.equal(personalSourceSub["메모: Review 출처 보기"], "source filter · Review · 3건");
  assert.equal(personalSourceSub["메모: Workspace Review 출처 보기"], "source filter · Workspace Review · 1건");
  assert.equal(personalSourceSub["메모: KB/IA Review 출처 보기"], "source filter · KB/IA Review · 1건");
  assert.equal(personalSourceSub["메모: PM Bench Review 출처 보기"], "source filter · PM Bench Review · 1건");

  palette.render("Alpha <script>");
  assert.match(elements.paletteResults.innerHTML, /Alpha &lt;script&gt;/);
  assert.doesNotMatch(elements.paletteResults.innerHTML, /<script>/);
  assert.equal(elements.paletteInput.attributes["aria-activedescendant"], "pal-option-0");

  // No-match queries fall back to quick capture instead of a dead end.
  palette.render("no-such-command");
  assert.match(elements.paletteResults.innerHTML, /바로 만들기/);
  assert.match(elements.paletteResults.innerHTML, /&quot;no-such-command&quot; 새 할 일로 추가/);
  assert.match(elements.paletteResults.innerHTML, /&quot;no-such-command&quot; 새 메모로 추가/);
  const quickCaptureItems = palette.buildItems("no-such-command");
  assert.equal(quickCaptureItems.length, 2);
  assert.deepEqual(JSON.parse(JSON.stringify(quickCaptureItems.map((item) => item.group))), ["바로 만들기", "바로 만들기"]);
  const longQuery = "긴 제목 ".repeat(20).trim();
  const longCapture = palette.buildItems(longQuery).filter((item) => item.group === "바로 만들기");
  assert.equal(longCapture.length, 2);
  assert.match(longCapture[0].label, /…" 새 할 일로 추가$/);

  palette.render("Alpha");
  palette.runIndex("not-a-number");
  assert.equal(openedTodoId, "");
  palette.runIndex(0);
  assert.equal(openedTodoId, "todo-alpha");
}

function testCommandPaletteUnusedAppWrappersRemoved() {
  const appSource = readFileSync(join(root, "app.js"), "utf8");
  const structureSource = readFileSync(join(root, "scripts/check-app-structure.mjs"), "utf8");
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
  assert.equal(structureSource.includes("commandPaletteCall(\\\"open\\\"") || structureSource.includes("commandPaletteCall(\"open\""), true);
  assert.equal(structureSource.includes("commandPaletteCall(\\\"close\\\"") || structureSource.includes("commandPaletteCall(\"close\""), true);
  assert.equal(structureSource.includes("commandPaletteCall(\"setup\"") || structureSource.includes("commandPaletteCall(\\\"setup\\\""), true);
}

function testImportGuardUnusedAppWrappersRemoved() {
  const appSource = readFileSync(join(root, "app.js"), "utf8");
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
  assert.match(appSource, /const IMPORT_GUARDS = window\.JooParkImportGuards/);
  assert.match(appSource, /importGuards: IMPORT_GUARDS/);
  assert.match(appSource, /function importBackupSummaryHTML\(obj\) \{\s*return backupImportUiCall\("importBackupSummaryHTML", obj\);\s*\}/);
  assert.match(smokeSource, /const importGuards = window\.JooParkImportGuards/);
  assert.match(smokeSource, /importGuards\.isBackupShape\(deletedImportShape\)/);
  assert.match(smokeSource, /importGuards\.backupSummaryItems\(deletedImportShape\)/);
  assert.match(smokeSource, /importGuards\.recordLimitViolations\(/);
}

function testGlobalSearchUnusedAppWrappersRemoved() {
  const appSource = readFileSync(join(root, "app.js"), "utf8");
  const globalSearchSource = readFileSync(join(root, "global-search.js"), "utf8");
  const structureSource = readFileSync(join(root, "scripts/check-app-structure.mjs"), "utf8");
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
}

function testReviewStateUnusedAppWrappersRemoved() {
  const appSource = readFileSync(join(root, "app.js"), "utf8");
  const reviewResultStateSource = readFileSync(join(root, "review-result-state.js"), "utf8");
  const reviewArtifactStateSource = readFileSync(join(root, "review-artifact-state.js"), "utf8");
  const structureSource = readFileSync(join(root, "scripts/check-app-structure.mjs"), "utf8");
  const removedWrappers = [
    "function applyReviewArtifactRepairBody",
    "function reviewResultRecordRepairSnapshot",
    "function reviewResultPostRepairReceiptModel",
  ];
  const hasTerm = (source, term) => source.includes(term) || source.includes(term.replaceAll("\"", "\\\""));
  for (const wrapper of removedWrappers) {
    assert.equal(appSource.includes(wrapper), false);
    assert.equal(structureSource.includes(wrapper), false);
  }
  assert.match(appSource, /function reviewArtifactRepairPreview\(target\) \{\s*return reviewArtifactStateCall\("repairPreview", target\);\s*\}/);
  assert.match(appSource, /function undoReviewArtifactRepair\(target\) \{\s*return reviewArtifactStateCall\("undoRepair", target\);\s*\}/);
  assert.match(appSource, /function attachReviewResultRepairReceipt\(validator, saved, result, warnings\) \{\s*return reviewResultStateCall\("attachRepairReceipt", validator, saved, result, warnings\);\s*\}/);
  assert.match(reviewArtifactStateSource, /function applyRepairBody\(repair\)/);
  assert.match(reviewResultStateSource, /function recordRepairSnapshot\(validator, state, message, details\)/);
  assert.match(reviewResultStateSource, /function postRepairReceiptModel\(validator, result, warnings, saved\)/);
  assert.equal(hasTerm(structureSource, "reviewArtifactStateCall(\"undoRepair\""), true);
}

function testReviewIssuePayloadUnusedAppWrappersRemoved() {
  const appSource = readFileSync(join(root, "app.js"), "utf8");
  const payloadSource = readFileSync(join(root, "review-issue-payload.js"), "utf8");
  const hasTerm = (source, term) => source.includes(term) || source.includes(term.replaceAll("\"", "\\\""));
  assert.equal(appSource.includes("function reviewOwnerToAssignee"), false);
  assert.match(appSource, /function reviewOwnerAssignment\(owner, project\)/);
  assert.match(appSource, /function reviewSavedResultTrackerFields\(saved, draft\) \{\s*return reviewIssuePayloadCall\("reviewSavedResultTrackerFields", saved, draft\);\s*\}/);
  assert.match(payloadSource, /const reviewOwnerAssignment = options\.reviewOwnerAssignment/);
  assert.match(payloadSource, /const assignment = reviewOwnerAssignment\(owner, project\)/);
}

function testHomeExecutionUnusedAppWrappersRemoved() {
  const appSource = readFileSync(join(root, "app.js"), "utf8");
  const homeExecutionSource = readFileSync(join(root, "home-execution-view.js"), "utf8");
  const removedWrappers = [
    "function homeExecutionReasonChipsHTML",
    "function homeExecutionBucketSummaryHTML",
  ];
  for (const wrapper of removedWrappers) {
    assert.equal(appSource.includes(wrapper), false);
  }
  assert.match(appSource, /function homeExecutionReasonKey\(chips\)/);
  assert.match(appSource, /function homeExecutionBucketSummary\(items\)/);
  assert.match(appSource, /function homeExecutionBucketKey\(buckets\)/);
  assert.match(homeExecutionSource, /function homeExecutionReasonChipsHTML\(item\)/);
  assert.match(homeExecutionSource, /function homeExecutionBucketSummaryHTML\(model\)/);
}

function testCalendarUnusedAppWrapperRemoved() {
  const appSource = readFileSync(join(root, "app.js"), "utf8");
  const calendarSource = readFileSync(join(root, "calendar-view.js"), "utf8");
  const structureSource = readFileSync(join(root, "scripts/check-app-structure.mjs"), "utf8");
  assert.equal(appSource.includes("function calLegend"), false);
  assert.match(appSource, /function calendarViewCall\(name, \.\.\.args\)/);
  assert.match(appSource, /calendarViewCall\("renderCalendarHTML"/);
  assert.match(calendarSource, /function calLegend\(\)/);
  assert.match(structureSource, /function calLegend/);
}

function testTodoUnusedAppWrappersRemoved() {
  const appSource = readFileSync(join(root, "app.js"), "utf8");
  const todoSource = readFileSync(join(root, "todo-view.js"), "utf8");
  const structureSource = readFileSync(join(root, "scripts/check-app-structure.mjs"), "utf8");
  assert.equal(appSource.includes("function todoMatchesFilter"), false);
  assert.equal(appSource.includes("function todoRow"), false);
  assert.match(appSource, /function todoViewCall\(name, \.\.\.args\)/);
  assert.match(appSource, /todoViewCall\("renderTodosHTML"/);
  assert.match(todoSource, /function todoMatchesFilter\(todo, filter\)/);
  assert.match(todoSource, /function todoRow\(todo\)/);
  assert.match(structureSource, /function todoMatchesFilter/);
  assert.match(structureSource, /function todoRow/);
}

function testDialogShellUnusedAppWrapperRemoved() {
  const appSource = readFileSync(join(root, "app.js"), "utf8");
  const dialogShellSource = readFileSync(join(root, "dialog-shell.js"), "utf8");
  const structureSource = readFileSync(join(root, "scripts/check-app-structure.mjs"), "utf8");
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
}

function testProjectPickerThinAppWrappersRemoved() {
  const appSource = readFileSync(join(root, "app.js"), "utf8");
  const projectPickerSource = readFileSync(join(root, "project-picker.js"), "utf8");
  const structureSource = readFileSync(join(root, "scripts/check-app-structure.mjs"), "utf8");
  const hasTerm = (source, term) => source.includes(term) || source.includes(term.replaceAll("\"", "\\\""));
  assert.equal(appSource.includes("function setProjectPickerOpen"), false);
  assert.equal(appSource.includes("function projectPickerIsOpen"), false);
  assert.equal(structureSource.includes("function setProjectPickerOpen"), false);
  assert.equal(structureSource.includes("function projectPickerIsOpen"), false);
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

function testHomeLaunchActionCountsPreserveExplicitZero() {
  const source = readFileSync(join(root, "home-view.js"), "utf8");
  assert.match(source, /function firstClampedCount\(values, fallback = 0\)/);
  assert.match(source, /const declaredLaunchActionCommandCount = firstClampedCount\(\[/);
  assert.match(source, /currentLaunchAction\?\.commandCount,\s+outputImmediateAction\?\.commandCount,\s+currentLaunchActionCommand \? 1 : 0,/);
  assert.match(source, /const currentLaunchActionCommandCount = currentLaunchActionCommand\s+\? Math\.max\(1, declaredLaunchActionCommandCount\)\s+: declaredLaunchActionCommandCount;/);
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

function testAppWorkflowUiInstallLoaderAcceptsNoopReceiptCommands() {
  const source = readFileSync(join(root, "app.js"), "utf8");
  assert.match(source, /function loadWorkflowUiInstallPlan\(\)/);
  assert.match(source, /const noopInstallReceiptReady = installRows\.length > 0 &&/);
  assert.match(source, /Number\(plan\.installReceipt\.commandCount \|\| 0\) >= \(noopInstallReceiptReady \? 4 : 6\)/);
  assert.equal(source.includes("Number(plan.installReceipt.commandCount || 0) >= 8"), false);
}

function testReleaseStatusPublishUnblockHandoffNamesWorkflowTargets() {
  const source = readFileSync(join(root, "release-status.js"), "utf8");
  assert.match(source, /function publishUnblockHandoffText\(\)/);
  assert(source.includes("Targets: `.github/workflows/joopark-pages.yml`, `.github/workflows/joopark-drift-watch.yml`."));
  assert(source.includes("replace_existing_remote_file"));
  assert(source.includes("verified_remote_matches_template"));
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

function testTrackedFilesExposeNoLocalAccountPaths() {
  const textExtensions = new Set([
    ".js", ".mjs", ".md", ".html", ".css", ".json", ".yml", ".yaml", ".svg", ".txt", ".webmanifest", ".sh",
  ]);
  const syntheticFixtureAllowlist = new Set(["scripts/test-pure-helpers.mjs"]);
  const tracked = execFileSync("git", ["ls-files", "-z"], { cwd: root, encoding: "utf8" })
    .split("\0")
    .filter(Boolean);
  const accountPathPattern = /\/Users\/(?=[A-Za-z0-9._%+-]*[A-Za-z0-9])[A-Za-z0-9._%+-]+/;
  for (const relPath of tracked) {
    if (syntheticFixtureAllowlist.has(relPath)) continue;
    const dotIndex = relPath.lastIndexOf(".");
    const extension = dotIndex === -1 ? "" : relPath.slice(dotIndex).toLowerCase();
    if (!textExtensions.has(extension)) continue;
    const text = readFileSync(join(root, relPath), "utf8");
    assert.doesNotMatch(text, accountPathPattern, `${relPath} exposes a local account path`);
  }
}

function testMobileSmokeNumericFallbacks() {
  const source = readFileSync(join(root, "scripts/smoke-mobile.mjs"), "utf8");
  const positiveIntegerOption = scriptFunction("scripts/smoke-mobile.mjs", "positiveIntegerOption");
  const positiveMsOption = scriptFunction("scripts/smoke-mobile.mjs", "positiveMsOption");
  const routeReadyExpression = scriptFunction("scripts/smoke-mobile.mjs", "routeReadyExpression");
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
  assert.match(source, /function routeReadyExpression\(route, timeoutMs\)/);
  assert.match(source, /const routeState = await evaluate\(client, routeReadyExpression\(route, timeoutMs\)\)/);
  const routeReadySource = routeReadyExpression("pm-portfolio", 9000);
  assert.match(routeReadySource, /const route = "pm-portfolio"/);
  assert.match(routeReadySource, /\[data-ops-runtime-loading\]/);
  assert.match(routeReadySource, /runtimeLoading/);
  assert.match(routeReadySource, /!state\.runtimeLoading/);
  assert.match(routeReadySource, /Date\.now\(\) - started > 9000/);
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
    if (contract.relPath === "scripts/smoke-chrome.mjs") {
      const routeReadyExpression = scriptFunction(contract.relPath, "routeReadyExpression");
      const routeReadySource = routeReadyExpression("system", 20000);
      assert.match(source, /function routeReadyExpression\(route, timeoutMs\)/);
      assert.match(source, /const routeState = await evaluate\(client, routeReadyExpression\(route, timeoutMs\)\)/);
      assert.match(routeReadySource, /const route = "system"/);
      assert.match(routeReadySource, /document\.body\.dataset\.view === route/);
      assert.match(routeReadySource, /state\.viewTextLength > 0/);
      assert.match(routeReadySource, /Date\.now\(\) - started > 20000/);
    }
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
testEventReminderStartIsIdempotent();
testKeyboardShortcutInteractionGuards();
testWikiLocalDocLinksResolve();
testStorageStatusRecoveryView();
testKanbanHelpers();
testImportGuards();
testRuntimeErrorBoundary();
await testPwaRuntimeUpdateReadyToast();
await testPwaRuntimeControllerChangeAppliedToast();
await testPwaRuntimeFirstInstallStaysQuiet();
testCalendarViewModelAndEscapes();
testTeamViewModelAndSummary();
testTodoViewModelAndEscapes();
testTodoOverdueReschedule();
testNotesViewModelAndEscapes();
testNoteModalPreviewHelpers();
testHabitsViewModelAndEscapes();
testStatsViewModelAndEscapes();
testStatsViewIgnoresStaleCompletedAt();
testStatsViewExpandsRecurringDeadlines();
testNotesSortStableForEqualUpdatedAt();
testExpandOccurrencesFastForwardsOldSeries();
testHabitStreakGivesTodayGrace();
testCompareEventsIsTotalOrder();
testHomeExecutionQueueIncludesUpcomingTodos();
testRouteChangeAccessibilityWired();
testLightThemeAccentContrastMeetsWcagAA();
testToggleTodoClearsCompletedAtOnUncheck();
testCrudDataIntegrityGuards();
testHomeWeekDeadlinesUseOccurrences();
testSeedDataAnchorsToToday();
testGlobalSearchCountIncludesVirtualizedOverflow();
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
testLlmWikiSmokeReadinessGuards();
testDesktopSmokeNavigationLoadGuard();
testProductSmokeUsesLock();
testProductSmokeLockHeartbeatStaleness();
testProductSmokePortOptionFallbacks();
testHomeLaunchActionCountsPreserveExplicitZero();
testHomeLaunchInstallMatrixCountsPreserveExplicitZero();
testLaunchClaimReadinessRequiresBothArtifacts();
testHomeRemoteWorkflowLedgerCountsPreserveExplicitZero();
testHomeLaunchProofLedgerCountsPreserveExplicitZero();
testHomeLaunchBlockerResolverCountsPreserveExplicitZero();
testHomePostInstallQuickProofCountsPreserveExplicitZero();
testHomeExternalClaimGuardCountsPreserveExplicitZero();
testReleaseStatusWorkflowUiInstallCoveragePreservesExplicitZero();
testAppWorkflowUiInstallLoaderAcceptsNoopReceiptCommands();
testReleaseStatusPublishUnblockHandoffNamesWorkflowTargets();
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
testTrackedFilesExposeNoLocalAccountPaths();
testMobileSmokeNumericFallbacks();
testBrowserSmokeTimeoutFallbacks();
testCapturePreviewInlineOptions();
testProductSmokeCloseUnrefsForcedServer();
testProductSmokeCliExitsAfterFlushedSuccess();
testMeasurePerfInvalidThresholdFallback();
testPipelineMatrixRenders();

console.log("PASS pure helper unit tests");
