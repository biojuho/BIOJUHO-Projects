/* ================================================================
 * JooPark Workspace — Project & Database Management Dashboard
 * Single-page SPA, vanilla JS, static demo data.
 * ================================================================ */

/* ---------- Utilities ---------- */

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
  for (let i = 0; i < strings.length; i += 1) {
    out += strings[i];
    if (i >= values.length) continue;
    const v = values[i];
    if (v === null || v === undefined || v === false) continue;
    if (v && v.__raw) {
      out += v.value;
    } else if (Array.isArray(v)) {
      out += v.map((item) => {
        if (item && item.__raw) return item.value;
        return escapeHtml(item);
      }).join("");
    } else {
      out += escapeHtml(v);
    }
  }
  return out;
}

/* renderMarkdown(src) → 소독된 HTML 문자열.
 * marked(vendor/marked.umd.js)로 Markdown→HTML 변환 후 DOMPurify(vendor/purify.min.js)로
 * XSS 소독한다. 결과는 raw()로만 주입할 것. 반환값:
 *   ""   → 빈 본문
 *   null → 라이브러리 미로드(또는 파싱 실패) → 호출부에서 평문 폴백
 * 절대 소독을 거치지 않은 marked 출력을 그대로 렌더하지 말 것. */
let _mdHookReady = false;
function renderMarkdown(src) {
  const text = src == null ? "" : String(src).trim();
  if (!text) return "";
  if (typeof marked === "undefined" || typeof marked.parse !== "function" ||
      typeof DOMPurify === "undefined" || typeof DOMPurify.sanitize !== "function") {
    return null;
  }
  if (!_mdHookReady) {
    // 외부 링크는 새 탭 + noopener 로 안전하게 연다.
    DOMPurify.addHook("afterSanitizeAttributes", (node) => {
      if (node.tagName === "A" && node.getAttribute("href")) {
        node.setAttribute("target", "_blank");
        node.setAttribute("rel", "noopener noreferrer");
      }
    });
    _mdHookReady = true;
  }
  let rawHtml;
  try {
    rawHtml = marked.parse(text, { gfm: true, breaks: true });
  } catch (err) {
    return null;
  }
  return DOMPurify.sanitize(rawHtml, { USE_PROFILES: { html: true } });
}

function debounce(fn, ms) {
  let timer = null;
  return function debounced(...args) {
    if (timer !== null) clearTimeout(timer);
    timer = setTimeout(() => {
      timer = null;
      fn.apply(this, args);
    }, ms);
  };
}

const TOAST_TIMEOUT = 3200;
function showToast(message, tone, options = {}) {
  const region = nodeQuery(document, "#toastRegion");
  if (!region) return;
  const el = document.createElement("div");
  el.className = `toast toast-${tone || "info"}`;
  const text = document.createElement("span");
  text.className = "toast-message";
  text.textContent = message;
  el.appendChild(text);

  let dismissed = false;
  const timers = [];
  const dismiss = () => {
    if (dismissed) return;
    dismissed = true;
    timers.forEach((timer) => clearTimeout(timer));
    el.classList.add("toast-leave");
    setTimeout(() => el.remove(), 240);
  };

  if (options && typeof options.onAction === "function" && options.actionLabel) {
    const action = document.createElement("button");
    action.type = "button";
    action.className = "toast-action";
    action.dataset.toastAction = "true";
    action.textContent = options.actionLabel;
    action.addEventListener("click", (event) => {
      event.stopPropagation();
      dismiss();
      try {
        options.onAction();
      } catch (error) {
        console.error(error);
        showToast("작업을 되돌리지 못했습니다", "error");
      }
    });
    el.appendChild(action);
  }

  region.appendChild(el);
  const timeoutMs = Math.max(1000, Number(options.timeoutMs || TOAST_TIMEOUT));
  timers.push(setTimeout(() => el.classList.add("toast-leave"), timeoutMs - 320));
  timers.push(setTimeout(() => {
    dismissed = true;
    el.remove();
  }, timeoutMs));
}

function cloneRecord(value) {
  if (typeof structuredClone === "function") return structuredClone(value);
  return JSON.parse(JSON.stringify(value));
}

function restoreDeletedArrayItem(list, index, item) {
  if (!Array.isArray(list) || !item) return false;
  if (item.id && list.some((entry) => entry && entry.id === item.id)) return false;
  const nextIndex = Math.min(Math.max(index, 0), list.length);
  list.splice(nextIndex, 0, cloneRecord(item));
  return true;
}

function showUndoToast(message, onUndo) {
  showToast(message, "info", { actionLabel: "되돌리기", onAction: onUndo, timeoutMs: 8000 });
}

const DELETED_ITEM_LIMIT = 40;
const DELETED_ITEM_RETENTION_DAYS = 30;
const DELETED_ITEM_RETENTION_MS = DELETED_ITEM_RETENTION_DAYS * 24 * 60 * 60 * 1000;
const DELETED_ITEM_KIND_LABELS = Object.freeze({
  event: "일정",
  todo: "할 일",
  note: "메모",
  habit: "습관",
  issue: "이슈",
  task: "작업",
  query: "쿼리",
  migration: "마이그레이션",
});

function deletedItemKindLabel(kind) {
  return DELETED_ITEM_KIND_LABELS[kind] || "항목";
}

function deletedItemLabel(kind, record) {
  const candidates = [
    record && record.title,
    record && record.name,
    record && record.text,
    record && record.id,
  ];
  const found = candidates.map((value) => String(value || "").trim()).find(Boolean) || "";
  return found || `${deletedItemKindLabel(kind)} 항목`;
}

function normalizeDeletedMeta(meta) {
  const source = meta && typeof meta === "object" ? meta : {};
  return Object.entries(source).reduce((acc, [key, value]) => {
    if (key === "index" || key === "label") return acc;
    if (value === undefined) return acc;
    acc[key] = cloneRecord(value);
    return acc;
  }, {});
}

function deletedItemWithinRetention(item, nowMs = Date.now()) {
  const deletedAtMs = parseDateTime(item && item.deletedAt ? item.deletedAt : "");
  if (!Number.isFinite(deletedAtMs)) return true;
  return deletedAtMs >= nowMs - DELETED_ITEM_RETENTION_MS;
}

function compareDeletedItemsByDeletedAtDesc(a, b) {
  return String(b.deletedAt).localeCompare(String(a.deletedAt));
}

function nonNegativeIntegerIndex(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? Math.max(0, Math.trunc(parsed)) : 0;
}

function captureDeletedItem(kind, record, meta = {}) {
  if (!record || typeof record !== "object") return "";
  if (!DELETED_ITEM_KIND_LABELS[kind]) return "";
  if (!Array.isArray(dashboard.deletedItems)) dashboard.deletedItems = [];
  const recordId = clampText(record.id || "", 120);
  const index = nonNegativeIntegerIndex(meta.index);
  const entry = {
    id: uid("del"),
    kind,
    recordId,
    label: clampText(meta.label || deletedItemLabel(kind, record), 160),
    deletedAt: nowISO(),
    index,
    record: cloneRecord(record),
    meta: normalizeDeletedMeta(meta),
  };
  dashboard.deletedItems = dashboard.deletedItems
    .filter((item) => !(item && recordId && item.kind === kind && item.recordId === recordId));
  dashboard.deletedItems.unshift(entry);
  dashboard.deletedItems = dashboard.deletedItems.slice(0, DELETED_ITEM_LIMIT);
  return entry.id;
}

function isFirstDeletedItemForRecord(item, index, list) {
  if (!item.recordId) return true;
  return list.findIndex((other) => other.kind === item.kind && other.recordId === item.recordId) === index;
}

function deletedItemById(entryId) {
  if (!Array.isArray(dashboard.deletedItems)) dashboard.deletedItems = [];
  return dashboard.deletedItems.find((item) => item && item.id === entryId) || null;
}

function dropDeletedItem(entryId) {
  if (!entryId || !Array.isArray(dashboard.deletedItems)) return false;
  const before = dashboard.deletedItems.length;
  dashboard.deletedItems = dashboard.deletedItems.filter((item) => item && item.id !== entryId);
  return dashboard.deletedItems.length !== before;
}

function canUndoDeletedItem(entryId) {
  if (!entryId) return true;
  if (deletedItemById(entryId)) return true;
  showToast("복구 항목이 폐기되었습니다", "warn");
  return false;
}

function restoreDeletedRecord(entry) {
  const record = entry && entry.record ? cloneRecord(entry.record) : null;
  const index = nonNegativeIntegerIndex(entry && entry.index);
  if (!record) return false;
  switch (entry.kind) {
    case "event":
      return restoreDeletedArrayItem(dashboard.events, index, record);
    case "todo":
      return restoreDeletedArrayItem(dashboard.todos, index, record);
    case "note":
      return restoreDeletedArrayItem(dashboard.notes, index, record);
    case "habit":
      return restoreDeletedArrayItem(ensureDashboardHabits(), index, record);
    case "issue": {
      const restored = restoreDeletedArrayItem(dashboard.issues, index, record);
      if (restored) rebuildIndexes();
      return restored;
    }
    case "task": {
      if (!dashboard.gantt || typeof dashboard.gantt !== "object") {
        dashboard.gantt = { rangeStart: todayISO(), rangeEnd: addDaysISO(todayISO(), 60), tasks: [] };
      }
      if (!Array.isArray(dashboard.gantt.tasks)) dashboard.gantt.tasks = [];
      const restored = restoreDeletedArrayItem(dashboard.gantt.tasks, index, record);
      if (!restored) return false;
      const previousDeps = Array.isArray(entry.meta && entry.meta.previousDeps) ? entry.meta.previousDeps : [];
      previousDeps.forEach((snapshot) => {
        const task = taskById(snapshot.id);
        if (task && Array.isArray(snapshot.deps)) task.deps = [...snapshot.deps];
      });
      return true;
    }
    case "query":
      return restoreDeletedArrayItem(dashboard.queries, index, record);
    case "migration":
      return restoreDeletedArrayItem(dashboard.migrations, index, record);
    default:
      return false;
  }
}

function restoreDeletedItem(entryId) {
  const entry = deletedItemById(entryId);
  if (!entry) {
    showToast("복구할 항목을 찾지 못했습니다", "warn");
    return false;
  }
  if (!restoreDeletedRecord(entry)) {
    showToast("이미 존재하거나 복구할 수 없는 항목입니다", "warn");
    return false;
  }
  dropDeletedItem(entryId);
  commit();
  showToast(`${deletedItemKindLabel(entry.kind)}을(를) 복구했습니다`, "info");
  return true;
}

function restoreAllDeletedItems() {
  const entries = Array.isArray(dashboard.deletedItems) ? dashboard.deletedItems.map((entry) => cloneRecord(entry)) : [];
  if (entries.length === 0) {
    showToast("복구할 항목이 없습니다", "info");
    return false;
  }
  let restoredCount = 0;
  const failedIds = new Set();
  entries.forEach((entry) => {
    if (!entry || !entry.id) return;
    if (restoreDeletedRecord(entry)) {
      restoredCount += 1;
      dropDeletedItem(entry.id);
    } else {
      failedIds.add(entry.id);
    }
  });
  dashboard.deletedItems = (dashboard.deletedItems || []).filter((entry) => entry && failedIds.has(entry.id));
  if (restoredCount > 0) {
    commit();
    showToast(failedIds.size ? `${restoredCount}개 복구, ${failedIds.size}개 보류` : `${restoredCount}개 항목을 모두 복구했습니다`, "info");
    return true;
  }
  showToast("이미 존재하거나 복구할 수 없는 항목입니다", "warn");
  return false;
}

function discardDeletedItem(entryId) {
  if (!dropDeletedItem(entryId)) {
    showToast("폐기할 복구 항목을 찾지 못했습니다", "warn");
    return false;
  }
  commit();
  showToast("복구 항목을 폐기했습니다", "info");
  return true;
}

function confirmClearDeletedItems() {
  const count = Array.isArray(dashboard.deletedItems) ? dashboard.deletedItems.length : 0;
  if (count === 0) {
    showToast("비울 복구 항목이 없습니다", "info");
    return;
  }
  openModal("최근 삭제 비우기", html`
    <div class="modal-confirm-body">
      <p><strong>${count}개</strong> 복구 항목을 영구 폐기합니다.</p>
      <p class="muted-note">폐기한 항목은 로컬 복구함에서 다시 복구할 수 없습니다.</p>
    </div>
  `, () => {
    dashboard.deletedItems = [];
    commit();
    showToast("최근 삭제 복구함을 비웠습니다", "info");
    return true;
  });
}

function setDeletedRecoveryQuery(value) {
  state.deletedRecoveryQuery = clampText(String(value || ""), 80);
  renderSettings();
  requestAnimationFrame(() => {
    const input = nodeQuery(document, "[data-deleted-recovery-search]");
    if (!input) return;
    input.focus({ preventScroll: true });
    const pos = input.value.length;
    try { input.setSelectionRange(pos, pos); } catch (_) {}
  });
}

function setDeletedRecoveryKind(value) {
  const kind = DELETED_ITEM_KIND_LABELS[value] ? value : "all";
  state.deletedRecoveryKind = kind;
  renderSettings();
}

function clearDeletedRecoveryFilter() {
  state.deletedRecoveryQuery = "";
  state.deletedRecoveryKind = "all";
  renderSettings();
}

function openDeletedRecoveryPanel() {
  if (dashboard.currentView !== "settings") setView("settings");
  else renderSettings();
  let focused = false;
  const focusPanel = () => {
    const panel = nodeQuery(document, "[data-settings-deleted-recovery]");
    if (!panel) return;
    focused = true;
    panel.dataset.deletedRecoveryCommandFocused = "true";
    panel.setAttribute("tabindex", "-1");
    panel.scrollIntoView({ behavior: "smooth", block: "start" });
    try {
      panel.focus({ preventScroll: true });
    } catch (_) {
      panel.focus();
    }
  };
  const retryFocus = (attempt = 0) => {
    focusPanel();
    if (focused || attempt >= 20) return;
    setTimeout(() => retryFocus(attempt + 1), 120);
  };
  requestAnimationFrame(() => retryFocus());
  setTimeout(() => {
    if (!focused && dashboard.currentView === "settings") renderSettings();
    retryFocus();
  }, 450);
  setTimeout(() => retryFocus(), 1200);
  setTimeout(() => retryFocus(), 2400);
}

function setHTML(node, htmlString) {
  if (!node) return;
  node.innerHTML = htmlString;
}

function normalize(value) { return `${value}`.toLowerCase(); }
function matches(value, query) {
  if (!query) return true;
  return normalize(value).includes(normalize(query));
}
function callModuleHelper(helpers, label, name, args, missingMessage = `${label} helper missing`) {
  if (!helpers || typeof helpers[name] !== "function") throw new Error(`${missingMessage}: ${name}`);
  return helpers[name](...args);
}

function lazyRuntimeLoader() {
  return window.JooParkOpsRuntime && window.JooParkOpsRuntime.version === "joopark-ops-runtime-loader/v1"
    ? window.JooParkOpsRuntime
    : null;
}

function createLazyRuntimeHelpers(current, globalName, deps) {
  const mod = window[globalName];
  return current || (mod && typeof mod.create === "function" ? mod.create(deps) : null);
}

let verifyWorkspaceSummaryHelpers = null;
function getVerifyWorkspaceSummaryHelpers() { return verifyWorkspaceSummaryHelpers = createLazyRuntimeHelpers(verifyWorkspaceSummaryHelpers, "JooParkVerifyWorkspaceSummary", { fetch: window.fetch.bind(window) }); }

function verifyWorkspaceSummaryCall(name, ...args) {
  return callModuleHelper(getVerifyWorkspaceSummaryHelpers(), "verify workspace summary", name, args, "verify workspace summary helper unavailable");
}

function initialVerifyWorkspaceSummaryState() {
  return getVerifyWorkspaceSummaryHelpers()
    ? verifyWorkspaceSummaryCall("initialState")
    : { checked: false, loaded: false, source: "autoresearch-results/verify-workspace-summary.json", data: null, error: "verify workspace summary helper unavailable" };
}

const searchEmptyStateHelpers = window.JooParkSearchEmptyState && typeof window.JooParkSearchEmptyState.create === "function"
  ? window.JooParkSearchEmptyState.create({ html })
  : null;

function searchEmptyStateCall(name, ...args) {
  return callModuleHelper(searchEmptyStateHelpers, "search empty state", name, args, "search empty state helper unavailable");
}

function searchEmptyState(kind, title, description) { return searchEmptyStateCall("searchEmptyState", kind, title, description); }

function projectSearchText(p) {
  const topics = Array.isArray(p && p.topics) ? p.topics : [];
  const focus = p && typeof p.benchmarkFocus === "object" ? p.benchmarkFocus : null;
  const signals = focus && Array.isArray(focus.signals) ? focus.signals : [];
  return [
    p && p.name,
    p && p.owner,
    p && p.status,
    p && p.health,
    p && p.description,
    p && p.category,
    p && p.language,
    p && p.lastCommit,
    p && p.pushedAt,
    focus && focus.surface,
    focus && focus.flow,
    ...signals,
    ...topics,
  ].filter(Boolean).join(" ");
}

const ADOPTION_STAGE_LABEL = {
  adopt: "도입",
  review: "검토",
  watch: "관찰",
};

function safeGithubUrl(url) {
  const value = String(url || "").trim().replace(/\/+$/, "");
  return /^https:\/\/github\.com\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(value) ? value : "";
}

function githubNewIssueUrl(project, title, body) {
  const base = safeGithubUrl(project && project.url);
  if (!base) return "";
  const params = new URLSearchParams();
  if (title) params.set("title", title);
  if (body) params.set("body", body);
  const query = params.toString();
  return query ? `${base}/issues/new?${query}` : `${base}/issues/new`;
}

function metricValue(value) {
  return typeof value === "number" && Number.isFinite(value) ? value.toLocaleString("en-US") : "-";
}

function numericMetric(value) {
  return typeof value === "number" && Number.isFinite(value) ? Math.max(0, value) : 0;
}

function shortCommit(value) {
  const commit = String(value || "").trim();
  return /^[0-9a-f]{7,40}$/i.test(commit) ? commit.slice(0, 8) : "";
}

function parseDateTime(value) {
  return Date.parse(value || "");
}

function isParseableDateTime(value) {
  return !!value && !Number.isNaN(parseDateTime(value));
}

function sortedStrings(values) {
  return [...(values || [])].sort();
}

function projectCandidatePriority(p) {
  if (!p || p.sourceKind !== "adoption-candidate") return null;
  const stageScore = { adopt: 24, review: 14, watch: 6 }[p.adoptionStage] || 8;
  const pushedAt = parseDateTime(p.pushedAt);
  const recentDays = Number.isNaN(pushedAt) ? 365 : Math.max(0, Math.round((Date.now() - pushedAt) / (24 * 60 * 60 * 1000)));
  const activityScore = Math.max(0, 24 - Math.min(recentDays, 180) / 180 * 24);
  const popularityScore = Math.min(28, Math.log10(numericMetric(p.stars) + 1) * 7);
  const forkScore = Math.min(10, Math.log10(numericMetric(p.forks) + 1) * 4);
  const healthScore = p.health === "green" ? 8 : p.health === "amber" ? 4 : 0;
  const riskPenalty = Math.min(14, numericMetric(p.risks) * 3 + Math.log10(numericMetric(p.openIssues) + 1));
  const score = Math.round(Math.max(0, Math.min(100, stageScore + activityScore + popularityScore + forkScore + healthScore - riskPenalty)));
  const label = score >= 70 ? "높음" : score >= 45 ? "중간" : "관찰";
  return { score, label };
}

function projectCandidateAction(p) {
  if (!p || p.sourceKind !== "adoption-candidate") return null;
  const topics = new Set((Array.isArray(p.topics) ? p.topics : []).map((topic) => String(topic).toLowerCase()));
  const category = String(p.category || "");
  const priority = projectCandidatePriority(p);
  if (!safeGithubUrl(p.url)) return { key: "source", label: "소스 보강", reason: "GitHub 링크 확인", tone: "amber" };
  if (numericMetric(p.risks) >= 3 || numericMetric(p.openIssues) >= 200) return { key: "risk", label: "리스크 리뷰", reason: "이슈/복잡도 확인", tone: "amber" };
  if (p.adoptionStage === "adopt" || (priority && priority.score >= 72)) return { key: "spike", label: "스파이크", reason: "48h 실험", tone: "green" };
  if (["local-first", "offline-first", "p2p", "privacy", "sqlite", "yjs", "knowledge-base"].some((topic) => topics.has(topic))) {
    return { key: "architecture", label: "아키텍처 벤치", reason: "로컬 퍼스트 구조", tone: "cyan" };
  }
  if (category.includes("프로젝트관리") || ["project-management", "task-management", "kanban", "gantt", "roadmap", "workflows"].some((topic) => topics.has(topic))) {
    return { key: "pm", label: "PM 벤치", reason: "워크플로 비교", tone: "blue" };
  }
  if (category.includes("캘린더") || ["calendar", "scheduling"].some((topic) => topics.has(topic))) {
    return { key: "calendar", label: "일정 UX 벤치", reason: "캘린더 패턴", tone: "violet" };
  }
  if (p.adoptionStage === "watch") return { key: "watch", label: "월간 관찰", reason: "변화 추적", tone: "muted" };
  return { key: "feature", label: "기능 검토", reason: "적합성 확인", tone: "blue" };
}

function projectBenchmarkData(p, key) {
  return p && typeof p[key] === "object" ? p[key] : null;
}

function normalizedBenchmarkFocus(focus) {
  if (!focus) return null;
  const surface = String(focus.surface || "").trim();
  const flow = String(focus.flow || "").trim();
  const signals = Array.isArray(focus.signals)
    ? focus.signals.map((signal) => String(signal || "").trim()).filter(Boolean).slice(0, 4)
    : [];
  if (!surface || !flow || signals.length === 0) return null;
  return { surface, flow, signals };
}

function clampNumber(value, min, max = Number.POSITIVE_INFINITY, fallback = 0) {
  const parsed = Number(value);
  const safeParsed = Number.isNaN(parsed) ? fallback : parsed;
  return Math.min(max, Math.max(min, safeParsed));
}

function finiteNumberOr(value, fallback) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function positiveFiniteNumberOrNull(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

function normalizedBenchmarkRubric(focus) {
  const rubric = focus && Array.isArray(focus.rubric) ? focus.rubric : [];
  return rubric
    .map((row) => ({
      axis: String(row && row.axis || "").trim(),
      value: String(row && row.value || "").trim(),
      weight: clampNumber(row && row.weight, 0, 1),
      score: clampNumber(row && row.score, 0, 100),
    }))
    .filter((row) => row.axis && row.value)
    .slice(0, 6);
}

function projectBenchmarkFocus(p) {
  return normalizedBenchmarkFocus(projectBenchmarkData(p, "benchmarkFocus"));
}

function projectBenchmarkRubric(p) {
  return normalizedBenchmarkRubric(projectBenchmarkData(p, "benchmarkFocus"));
}

function projectKnowledgeBaseBenchmark(p) {
  return normalizedBenchmarkFocus(projectBenchmarkData(p, "knowledgeBaseBenchmark"));
}

function projectKnowledgeBaseRubric(p) {
  return normalizedBenchmarkRubric(projectBenchmarkData(p, "knowledgeBaseBenchmark"));
}

function projectWorkspaceBenchmark(p) {
  return normalizedBenchmarkFocus(projectBenchmarkData(p, "workspaceBenchmark"));
}

function projectWorkspaceRubric(p) {
  return normalizedBenchmarkRubric(projectBenchmarkData(p, "workspaceBenchmark"));
}

function weightedRubricScore(rubric) {
  const scored = (Array.isArray(rubric) ? rubric : []).filter((row) => row.weight > 0 && row.score > 0);
  const totalWeight = scored.reduce((sum, row) => sum + row.weight, 0);
  if (!totalWeight) return null;
  const score = Math.round(scored.reduce((sum, row) => sum + row.score * row.weight, 0) / totalWeight);
  const label = score >= 86 ? "강한 추천" : score >= 80 ? "추천" : score >= 72 ? "조건부" : "보류";
  return { score, label };
}

function topWeightedRubricAxis(rubric) {
  return (Array.isArray(rubric) ? rubric : [])
    .filter((row) => row.weight > 0 && row.score > 0)
    .reduce((top, row) => {
      if (!top) return row;
      return row.score * row.weight > top.score * top.weight ? row : top;
    }, null);
}

function projectBenchmarkRubricScore(p) {
  return weightedRubricScore(projectBenchmarkRubric(p));
}

function projectKnowledgeBaseRubricScore(p) {
  return weightedRubricScore(projectKnowledgeBaseRubric(p));
}

function projectWorkspaceRubricScore(p) {
  return weightedRubricScore(projectWorkspaceRubric(p));
}

function projectBenchmarkContext(p) {
  const pm = !!projectBenchmarkFocus(p);
  const workspace = projectWorkspaceRubric(p).length > 0;
  const knowledgeBase = projectKnowledgeBaseRubric(p).length > 0;
  return { pm, workspace, knowledgeBase, any: pm || workspace || knowledgeBase };
}

function projectPromptHandoffTarget(project) {
  const context = projectBenchmarkContext(project);
  if (!context.any) return null;
  if (context.pm) return { kind: "benchmark", label: "PM benchmark", selector: "[data-benchmark-review-handoff]" };
  if (context.workspace) return { kind: "workspace", label: "Workspace review", selector: "[data-workspace-review-handoff]" };
  if (context.knowledgeBase) return { kind: "knowledge-base", label: "KB/IA review", selector: "[data-knowledge-base-review-handoff]" };
  return null;
}

function projectPromptHandoffButton(project, variant = "card") {
  const target = projectPromptHandoffTarget(project);
  if (!target) return "";
  const cls = variant === "sheet" ? "sheet-action sheet-action-prompt" : "portfolio-prompt-handoff";
  return html`<button type="button" class="${cls}" data-action="show-project-prompt-handoff" data-project-id="${project.id}" data-prompt-handoff-target="${target.kind}" data-prompt-handoff-surface="${target.label}">↪ prompt handoff 보기</button>`;
}

function rankProjectsByRubric(projects, scoreProject) {
  return (Array.isArray(projects) ? projects : [])
    .map((project) => ({ project, rubricScore: scoreProject(project) }))
    .filter((item) => item.rubricScore)
    .sort((a, b) => b.rubricScore.score - a.rubricScore.score || String(a.project.name || "").localeCompare(String(b.project.name || "")));
}

function adoptionCandidateRubricProjects(projects, rubricProject) {
  return (Array.isArray(projects) ? projects : [])
    .filter((project) => project.sourceKind === "adoption-candidate" && rubricProject(project).length > 0);
}

function rankedAdoptionCandidateRubricProjects(projects, rubricProject, rankProjects, limit) {
  return rankProjects(adoptionCandidateRubricProjects(projects, rubricProject))
    .map((item) => item.project)
    .slice(0, limit);
}

function knowledgeBaseBenchmarkRubricRanking(projects) {
  return rankProjectsByRubric(projects, projectKnowledgeBaseRubricScore);
}

function workspaceBenchmarkRubricRanking(projects) {
  return rankProjectsByRubric(projects, projectWorkspaceRubricScore);
}

let reviewRecommendationExportHelpers = null;
function getReviewRecommendationExportHelpers() { return reviewRecommendationExportHelpers = createLazyRuntimeHelpers(reviewRecommendationExportHelpers, "JooParkReviewRecommendationExport", { html, raw, projectBenchmarkRubric, projectKnowledgeBaseRubric, projectWorkspaceRubric }); }

function reviewRecommendationExportCall(name, ...args) {
  return callModuleHelper(getReviewRecommendationExportHelpers(), "review recommendation export", name, args, "Review recommendation export helper missing");
}

function candidateBenchmarkRecommendationMarkdown(scored) {
  return reviewRecommendationExportCall("candidateBenchmarkRecommendationMarkdown", scored);
}

function projectCandidateSeedScope(p) {
  if (!p || p.sourceKind !== "adoption-candidate") return "";
  return String(p.seedScope || p.sourceScope || "demo-local-snapshot").trim() || "demo-local-snapshot";
}

function projectAdoptionMeta(p) {
  if (!p || p.sourceKind !== "adoption-candidate") return "";
  const stage = ADOPTION_STAGE_LABEL[p.adoptionStage] || p.adoptionStage || "검토";
  const repoUrl = safeGithubUrl(p.url);
  const priority = projectCandidatePriority(p);
  const action = projectCandidateAction(p);
  const benchmark = projectBenchmarkFocus(p);
  const knowledgeBenchmark = projectKnowledgeBaseBenchmark(p);
  const commit = shortCommit(p.lastCommit);
  const commitTitle = p.pushedAt ? `갱신 ${formatLocalDateTime(p.pushedAt)}` : "최신 커밋";
  const seedScope = projectCandidateSeedScope(p);
  return html`
    <div class="portfolio-candidate-meta" data-candidate-meta>
      <span data-candidate-seed-scope="${seedScope}" title="로컬 데모 스냅샷이며 라이브 DB 동기화가 아닙니다"><b>Seed</b> demo snapshot</span>
      ${action ? raw(html`<span class="portfolio-action portfolio-action-${action.tone}" data-candidate-action="${action.label}" data-candidate-action-key="${action.key}" title="${action.reason}"><b>액션</b> ${action.label}<small>${action.reason}</small></span>`) : ""}
      ${benchmark ? raw(html`<span class="portfolio-benchmark" data-candidate-benchmark="${benchmark.surface}" data-benchmark-flow="${benchmark.flow}" title="${benchmark.signals.join(" · ")}"><b>벤치</b> ${benchmark.surface}<small>${benchmark.flow}</small></span>`) : ""}
      ${knowledgeBenchmark ? raw(html`<span class="portfolio-benchmark" data-knowledge-base-benchmark="${knowledgeBenchmark.surface}" data-knowledge-base-flow="${knowledgeBenchmark.flow}" title="${knowledgeBenchmark.signals.join(" · ")}"><b>KB</b> ${knowledgeBenchmark.surface}<small>${knowledgeBenchmark.flow}</small></span>`) : ""}
      ${priority ? raw(html`<span class="portfolio-priority" data-candidate-priority="${priority.score}"><b>우선</b> ${priority.label} ${priority.score}</span>`) : ""}
      <span data-candidate-stage="${p.adoptionStage || ""}"><b>단계</b> ${stage}</span>
      <span><b>★</b> ${metricValue(p.stars)}</span>
      <span><b>Fork</b> ${metricValue(p.forks)}</span>
      ${p.language ? raw(html`<span><b>언어</b> ${p.language}</span>`) : ""}
      ${commit ? raw(html`<span class="portfolio-commit" data-candidate-commit="${commit}" data-candidate-pushed-at="${p.pushedAt || ""}" title="${commitTitle}"><b>Commit</b> ${commit}</span>`) : ""}
      ${repoUrl ? raw(html`<a class="portfolio-candidate-link" href="${repoUrl}" target="_blank" rel="noopener noreferrer">GitHub ↗</a>`) : ""}
    </div>
  `;
}

function spark(points, color) {
  if (!Array.isArray(points) || points.length === 0) return "";
  const max = Math.max(...points);
  const min = Math.min(...points);
  const coords = points.map((point, index) => {
    const x = (index / (points.length - 1 || 1)) * 94 + 1;
    const y = 34 - ((point - min) / (max - min || 1)) * 28;
    return `${x},${y}`;
  });
  return `<svg viewBox="0 0 100 40" aria-hidden="true"><polyline points="${coords.join(" ")}" fill="none" stroke="${escapeHtml(color)}" stroke-width="2"/><polygon points="1,38 ${coords.join(" ")} 98,38" fill="${escapeHtml(color)}" opacity=".12"/></svg>`;
}

/* ---------- Date helpers (Gantt, Calendar) ---------- */

function parseDate(s) {
  const [y, m, d] = s.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d));
}
function daysBetween(a, b) {
  return Math.round((parseDate(b) - parseDate(a)) / (24 * 3600 * 1000));
}
function addDays(s, n) {
  const d = parseDate(s);
  d.setUTCDate(d.getUTCDate() + n);
  const yyyy = d.getUTCFullYear();
  const mm = String(d.getUTCMonth() + 1).padStart(2, "0");
  const dd = String(d.getUTCDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}
function formatMonthDay(s) {
  const d = parseDate(s);
  return `${d.getUTCMonth() + 1}/${d.getUTCDate()}`;
}
function todayISO() {
  const d = new Date();
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

/* ---------- State ---------- */

const state = {
  query: "",
  previousFocus: null,
  modalOnConfirm: null,
  reviewArtifactRepairUndo: null,
  dashboardAutoresearchActive: false,
  kanbanFilter: null, // priority filter or null
  kanbanSourceFilter: "all",
  homeExecutionBucketFilter: "all",
  todoSourceFilter: "all",
  noteSourceFilter: "all",
  dbCatalogFilter: "all",
  calMode: "month",
  llmWikiCategory: null, // 선택된 LLM 위키 카테고리 id (null = 첫 카테고리)
  llmWikiArticle: null,  // 선택된 문서 id (null = 목록)
  llmWikiActionFilter: "all",
  issueSourceBacklink: null,
  llmWikiRecordBacklink: null,
  deletedRecoveryQuery: "",
  deletedRecoveryKind: "all",
  portfolioFilter: "all",
  portfolioActionFilter: "all",
  portfolioBenchmarkFilter: "all",
  schemaExpanded: new Set(["db-prod-1"]), // expanded instances in schema tree
  schemaSelectedTable: null,
  storageHealth: {
    status: "checking",
    localBytes: 0,
    usageBytes: null,
    quotaBytes: null,
    persisted: null,
    estimateSupported: false,
    persistedSupported: false,
    checkedAt: "",
    lastError: "",
  },
  pwaRuntime: {
    checked: false,
    status: "checking",
    secureContext: false,
    localHostContext: false,
    serviceWorkerSupported: false,
    serviceWorkerActive: false,
    controller: false,
    scriptURL: "",
    scope: "",
    cachesSupported: false,
    cacheReady: false,
    appShellCache: "",
    cachedAssetCount: 0,
    manifestLinked: false,
    standalone: false,
    online: true,
    checkedAt: "",
    lastError: "",
  },
  publishEvidence: {
    checked: false,
    loaded: false,
    source: "data/publish-evidence.json",
    data: null,
    error: "",
  },
  workflowUiInstallPlan: {
    checked: false,
    loaded: false,
    source: "data/workflow-ui-install-plan.json",
    data: null,
    error: "",
  },
  publishDispatchPlan: {
    checked: false,
    loaded: false,
    source: "data/publish-dispatch-plan.json",
    data: null,
    error: "",
  },
  remoteWorkflowFileCheck: {
    checked: false,
    loaded: false,
    source: "data/remote-workflow-file-check.json",
    data: null,
    error: "",
  },
  launchExecutionPacket: {
    checked: false,
    loaded: false,
    source: "data/launch-execution-packet.json",
    data: null,
    error: "",
  },
  launchReadinessRefresh: {
    checked: false,
    loaded: false,
    source: "data/launch-readiness-refresh.json",
    data: null,
    error: "",
  },
  verifyWorkspaceSummary: initialVerifyWorkspaceSummaryState(),
  releaseProvenance: {
    checked: false,
    loaded: false,
    source: "release-provenance.json",
    data: null,
    error: "",
  },
  outputQualityAudit: {
    checked: false,
    loaded: false,
    source: "data/output-quality-audit.json",
    data: null,
    error: "",
  },
  githubProjectDiscovery: {
    checked: false,
    loaded: false,
    source: "data/github-project-discovery.json",
    data: null,
    error: "",
  },
  projectSnapshotHealth: {
    checked: false,
    loaded: false,
    sourceCount: 0,
    loadedCount: 0,
    errorCount: 0,
    projectCount: 0,
    applied: false,
    appliedReason: "not checked",
    sources: [],
  },
};

/* ---------- Static demo data ---------- */

const dashboardSeedHelpers = window.JooParkWorkspaceSeedData && window.JooParkWorkspaceSeedData.version === "joopark-workspace-seed-data/v1" && typeof window.JooParkWorkspaceSeedData.create === "function"
  ? window.JooParkWorkspaceSeedData
  : null;

if (!dashboardSeedHelpers) {
  throw new Error("workspace seed data helper unavailable");
}

const dashboard = dashboardSeedHelpers.create({ addDays });

/* ---------- Refs ---------- */

const VIEWS = ["home", "cal", "todo", "notes", "habits", "stats", "llm-wiki", "pm-portfolio", "pm-kanban", "pm-gantt", "pm-team", "dbm-instances", "dbm-schema", "dbm-queries", "dbm-backups", "settings", "system"];

function rootDialogRefs(id) {
  return { root: nodeQuery(document, `#${id}`), title: nodeQuery(document, `#${id}Title`), body: nodeQuery(document, `#${id}Body`) };
}

const refs = {
  views: Object.fromEntries(VIEWS.map((id) => [id, nodeQuery(document, `#view-${id}`)])),
  query: nodeQuery(document, "#globalSearch"),
  searchClear: nodeQuery(document, "#globalSearchClear"),
  searchCount: nodeQuery(document, "#searchCount"),
  navItems: document.querySelectorAll("[data-action='nav-to']"),
  sheets: { ...rootDialogRefs("sheet"), meta: nodeQuery(document, "#sheetMeta") },
  modal: rootDialogRefs("modal"),
  projectSelect: nodeQuery(document, "#projectSelect"),
  projectSelectLabel: nodeQuery(document, "#projectSelectLabel"),
  projectPicker: nodeQuery(document, "#projectPicker"),
  footerNow: nodeQuery(document, "#footerNow"),
};

const projectPickerState = { query: "" };

const dialogShellHelpers = window.JooParkDialogShell && typeof window.JooParkDialogShell.create === "function"
  ? window.JooParkDialogShell.create({
      document,
      body: document.body,
      refs,
      state,
      html,
      raw,
      setHTML,
    })
  : null;

function dialogShellCall(name, ...args) {
  return callModuleHelper(dialogShellHelpers, "Dialog shell", name, args);
}

function assertRefs() {
  const missing = [];
  Object.entries(refs.views).forEach(([k, v]) => { if (!v) missing.push(`view-${k}`); });
  if (!refs.query) missing.push("query");
  if (missing.length) console.warn("[workspace] missing refs:", missing);
}

/* ---------- Helpers ---------- */

const PRIORITY_LABEL = { crit: "Critical", high: "High", med: "Medium", low: "Low" };
const STATUS_LABEL   = { todo: "To Do", "in-progress": "In Progress", review: "Review", done: "Done" };
const HEALTH_COLOR   = { green: "var(--green)", amber: "var(--amber)", red: "var(--red)" };

const projectPickerHelpers = window.JooParkProjectPicker && typeof window.JooParkProjectPicker.create === "function"
  ? window.JooParkProjectPicker.create({
      document,
      body: document.body,
      refs,
      state: projectPickerState,
      dashboard,
      html,
      raw,
      setHTML,
      matches,
      projectSearchText,
      spark,
      healthColor: HEALTH_COLOR,
    })
  : null;

const globalSearchHelpers = window.JooParkGlobalSearch && typeof window.JooParkGlobalSearch.create === "function"
  ? window.JooParkGlobalSearch.create({
      document,
      window,
      refs,
      state,
      getCurrentView: () => dashboard.currentView,
      renderCurrentView: () => renderCurrentView(),
      openPalette: () => commandPaletteCall("open"),
      debounce,
    })
  : null;

function projectPickerCall(name, ...args) {
  return callModuleHelper(projectPickerHelpers, "Project picker", name, args);
}

function globalSearchCall(name, ...args) {
  return callModuleHelper(globalSearchHelpers, "Global search", name, args);
}

const indexes = {
  teamById: new Map(),
  projectById: new Map(),
  issueById: new Map(),
  instanceById: new Map(),
};
function rebuildIndexes() {
  indexes.teamById.clear();
  dashboard.team.forEach((m) => indexes.teamById.set(m.id, m));
  indexes.projectById.clear();
  dashboard.projects.forEach((p) => indexes.projectById.set(p.id, p));
  indexes.issueById.clear();
  dashboard.issues.forEach((i) => indexes.issueById.set(i.id, i));
  indexes.instanceById.clear();
  dashboard.dbInstances.forEach((d) => indexes.instanceById.set(d.id, d));
}
rebuildIndexes();

function memberName(id) {
  const m = indexes.teamById.get(id);
  return m ? m.name : id;
}
function projectName(id) {
  const p = indexes.projectById.get(id);
  return p ? p.name : id;
}
function projectByIdOrName(id, name) {
  return (dashboard.projects || []).find((project) => project && (project.id === id || project.name === name)) || null;
}
function projectByName(name) {
  return projectByIdOrName(undefined, name);
}
function recordById(records, id) {
  return (records || []).find((record) => record && record.id === id) || null;
}
function recordIndexById(records, id) {
  return (records || []).findIndex((record) => record && record.id === id);
}
function recordByKey(records, key) {
  return (records || []).find((record) => record && record.key === key) || null;
}
function recordIndexByKey(records, key) {
  return (records || []).findIndex((record) => record && record.key === key);
}
function recordBySourceKey(records, sourceKey) {
  return (records || []).find((record) => record && record.sourceKey === sourceKey) || null;
}
function issueBySourceKey(sourceKey) {
  return recordBySourceKey(dashboard.issues, sourceKey);
}
function noteBySourceKey(sourceKey) {
  return recordBySourceKey(dashboard.notes, sourceKey);
}
function todoBySourceKey(sourceKey) {
  return recordBySourceKey(dashboard.todos, sourceKey);
}
function currentProject() {
  return indexes.projectById.get(dashboard.currentProjectId) || dashboard.projects[0] || null;
}
function currentInstance() {
  return indexes.instanceById.get(dashboard.currentInstanceId) || dashboard.dbInstances[0] || null;
}

/* ---------- Panel head helper ---------- */

function viewHref(viewName) {
  return viewName ? `#${viewName}` : "#";
}

function panelHead(title, link, controls) {
  return html`
    <div class="panel-head">
      <div><h2>${title}</h2>${link ? raw(html`<a href="${viewHref(link.view)}" data-action="${link.action}" data-view="${link.view || ""}">${link.label}</a>`) : ""}</div>
      ${controls ? raw(controls) : ""}
    </div>
  `;
}

function kpiCard(item) {
  return html`
    <article class="card kpi">
      <h3>${item.title}</h3>
      <span class="badge" style="color:${raw(escapeHtml(item.color))}">${item.badge}</span>
      <strong>${item.value}<small>${item.unit || ""}</small></strong>
      <span class="delta ${raw(item.trendDown ? "down" : "")}">${item.delta || ""}</span>
      ${item.points ? raw(spark(item.points, item.color)) : ""}
    </article>
  `;
}

function homeHeroHTML({ today, greet, name, todaysEvents, openTodos, overdueTodos }) {
  return html`
    <section class="panel home-hero">
      <div class="home-hero-text">
        <small>${formatKoreanFull(today)}</small>
        <h1>${greet}, ${name}님</h1>
        <p class="home-purpose">개인 일정, 프로젝트 진행, DB 카탈로그를 브라우저 로컬 저장으로 정리하는 워크스페이스입니다.</p>
        <p>오늘 일정 <b>${todaysEvents.length}</b>건 · 할 일 <b>${openTodos.length}</b>건${overdueTodos.length ? raw(html` · <span class="hero-warn">지난 마감 ${overdueTodos.length}건</span>`) : ""}</p>
      </div>
      <div class="home-activation">
        <div class="home-hero-actions">
          <button type="button" class="primary-btn" data-action="todo-add">+ 할 일</button>
          <button type="button" data-action="cal-add" data-date="${today}">+ 일정</button>
          <button type="button" data-action="note-add">+ 메모</button>
          <button type="button" class="secondary-btn" data-action="nav-to" data-view="pm-portfolio">포트폴리오</button>
          <button type="button" class="secondary-btn" data-action="nav-to" data-view="dbm-instances">DB 카탈로그</button>
        </div>
        <form class="home-quickadd" data-action="home-todo-quick-add" data-home-first-action="todo">
          <input type="text" name="title" maxlength="160" placeholder="오늘 바로 처리할 일 입력..." aria-label="홈에서 할 일 빠른 추가" autocomplete="off" />
          <select name="priority" aria-label="홈 할 일 우선순위">
            <option value="med">보통</option>
            <option value="high">높음</option>
            <option value="low">낮음</option>
          </select>
          <input type="date" name="due" value="${today}" aria-label="홈 할 일 마감일" />
          <button type="submit" class="primary-btn">바로 추가</button>
        </form>
      </div>
    </section>
  `;
}

function homeTileHTML(title, subtitle, viewName, body) {
  return html`
    <article class="panel home-tile">
      <div class="panel-head">
        <div><h2>${title}</h2><a href="${viewHref(viewName)}" data-action="nav-to" data-view="${viewName}">전체 보기 ›</a></div>
        <small class="home-tile-sub">${subtitle}</small>
      </div>
      ${raw(body)}
    </article>
  `;
}

function homeEmptyHTML(key, title, description, action, label) {
  return html`
    <div class="home-empty" data-home-empty="${key}">
      <strong>${title}</strong>
      <span>${description}</span>
      <button type="button" class="small-action" data-action="${action}">${label}</button>
    </div>
  `;
}

function homeListPreviewHTML(items, itemHTML) {
  return html`<ul class="home-list">${items.map((item) => raw(itemHTML(item)))}</ul>`;
}

const HOME_EXECUTION_PRIORITY_WEIGHT = { crit: 4, high: 3, med: 2, low: 1 };
const HOME_EXECUTION_STATUS_WEIGHT = { "in-progress": 3, review: 2, todo: 1 };
const HOME_EXECUTION_ISSUE_NEXT_STATUS = { todo: "in-progress", "in-progress": "review", review: "done" };
const HOME_EXECUTION_DUE_REASON_LABEL = { overdue: "overdue", today: "today", upcoming: "this week", unscheduled: "unscheduled" };
const HOME_EXECUTION_BUCKET_ORDER = ["overdue", "today", "upcoming"];
const HOME_EXECUTION_BUCKET_LABEL = { all: "전체", overdue: "긴급", today: "오늘", upcoming: "이번 주" };
const homeExecutionViewHelpers = window.JooParkHomeExecutionView && typeof window.JooParkHomeExecutionView.create === "function"
  ? window.JooParkHomeExecutionView.create({ html, raw, escapeHtml, dueLabel, homeEmptyHTML })
  : null;

function homeExecutionViewCall(name, ...args) {
  return callModuleHelper(homeExecutionViewHelpers, "home execution view", name, args, "home execution view helper unavailable");
}

function homeExecutionDueState(due, today) {
  if (!due) return "unscheduled";
  if (due < today) return "overdue";
  if (due === today) return "today";
  return "upcoming";
}

function homeExecutionDueWeight(stateKey) {
  if (stateKey === "overdue") return 3000;
  if (stateKey === "today") return 2000;
  if (stateKey === "upcoming") return 1000;
  return 0;
}

function homeExecutionIssueNextStatus(status) {
  return HOME_EXECUTION_ISSUE_NEXT_STATUS[status] || "in-progress";
}

function homeExecutionDueReasonLabel(stateKey) {
  return HOME_EXECUTION_DUE_REASON_LABEL[stateKey] || stateKey || "unscheduled";
}

function homeExecutionReasonKey(chips) {
  return (chips || []).map((chip) => chip.key).filter(Boolean).join("|");
}

function homeExecutionTypeCounts(items) {
  const list = items || [];
  return {
    todoCount: list.filter((item) => item.type === "todo").length,
    issueCount: list.filter((item) => item.type === "issue").length,
  };
}

function homeExecutionDueStateCounts(items) {
  const list = items || [];
  return {
    overdueCount: list.filter((item) => item.dueState === "overdue").length,
    todayCount: list.filter((item) => item.dueState === "today").length,
    upcomingCount: list.filter((item) => item.dueState === "upcoming").length,
  };
}

function homeExecutionWindowDriverModel({ dueCount, priorityCount, activeCount }) {
  const rows = [
    { key: "due", label: "마감", count: dueCount },
    { key: "priority", label: "고우선", count: priorityCount },
    { key: "active", label: "진행", count: activeCount },
  ];
  const leadDriverCount = Math.max(0, ...rows.map((driver) => driver.count));
  const leadDrivers = rows.filter((driver) => driver.count === leadDriverCount && driver.count > 0);
  return {
    leadDriverKey: leadDrivers.length ? leadDrivers.map((driver) => driver.key).join("+") : "baseline",
    leadDriverLabel: leadDrivers.length > 1 ? `공동 ${leadDrivers.map((driver) => driver.label).join("+")}` : leadDrivers[0]?.label || "기본",
    leadDriverCount,
    leadDriverTieCount: leadDrivers.length,
  };
}

function homeExecutionWindowDriverCounts(items) {
  const list = items || [];
  return {
    windowDuePressureCount: list.filter((item) => item.dueState === "overdue" || item.dueState === "today").length,
    windowHighPriorityCount: list.filter((item) => item.priority === "crit" || item.priority === "high").length,
    windowActiveIssueCount: list.filter((item) => item.reasonKey.includes("status:in-progress") || item.reasonKey.includes("status:review")).length,
  };
}

function homeExecutionBucketSummary(items) {
  return HOME_EXECUTION_BUCKET_ORDER.map((key) => {
    const bucketItems = (items || []).filter((item) => item.dueState === key);
    const typeCounts = homeExecutionTypeCounts(bucketItems);
    return {
      key,
      label: HOME_EXECUTION_BUCKET_LABEL[key] || key,
      count: bucketItems.length,
      todoCount: typeCounts.todoCount,
      issueCount: typeCounts.issueCount,
      topScore: bucketItems.reduce((max, item) => Math.max(max, item.score || 0), 0),
    };
  }).filter((bucket) => bucket.count > 0);
}

function homeExecutionBucketKey(buckets) {
  return (buckets || []).map((bucket) => `${bucket.key}:${bucket.count}:${bucket.todoCount}:${bucket.issueCount}`).join("|");
}

function normalizeHomeExecutionBucketFilter(value, buckets = []) {
  if (value === "all") return "all";
  const allowed = new Set((buckets || []).map((bucket) => bucket.key));
  return allowed.has(value) ? value : "all";
}

function homeExecutionCandidatesForBucket(candidates, bucketFilter) {
  return bucketFilter === "all"
    ? candidates
    : (candidates || []).filter((item) => item.dueState === bucketFilter);
}

function compareHomeExecutionQueueItems(a, b) {
  return b.score - a.score || String(a.due || "").localeCompare(String(b.due || "")) || a.title.localeCompare(b.title);
}

function homeExecutionQueueModel({ today, weekEnd, openTodos, bucketFilter = "all" }) {
  const todoItems = openTodos
    .filter((todo) => todo.due && todo.due <= today)
    .map((todo) => {
      const dueState = homeExecutionDueState(todo.due, today);
      const priorityWeight = HOME_EXECUTION_PRIORITY_WEIGHT[todo.priority] || HOME_EXECUTION_PRIORITY_WEIGHT.med;
      const dueScore = homeExecutionDueWeight(dueState);
      const priorityScore = priorityWeight * 100;
      const daysDelta = Math.abs(daysBetweenLocal(today, todo.due));
      const score = dueScore + priorityScore - daysDelta;
      const priority = todo.priority || "med";
      const priorityLabel = TODO_PRIORITY[todo.priority]?.label || "보통";
      const reasonChips = [
        { key: `due:${dueState}`, label: homeExecutionDueReasonLabel(dueState) },
        { key: `priority:${priority}`, label: priorityLabel },
      ];
      return {
        type: "todo",
        id: todo.id,
        title: todo.title,
        context: todo.category ? `할 일 · ${todo.category}` : "할 일",
        due: todo.due,
        dueState,
        priority,
        priorityLabel,
        score,
        scoreBreakdown: `due=${dueScore};priority=${priorityScore};age=-${daysDelta}`,
        reasonKey: homeExecutionReasonKey(reasonChips),
        reasonChips,
        action: "open-todo",
        quickAction: "home-execution-todo-complete",
        quickActionLabel: "완료",
        quickActionState: "done",
        idAttr: "todo-id",
      };
    });

  const issueItems = dashboard.issues
    .filter((issue) => issue.status !== "done" && issue.due && issue.due <= weekEnd)
    .map((issue) => {
      const dueState = homeExecutionDueState(issue.due, today);
      const priorityWeight = HOME_EXECUTION_PRIORITY_WEIGHT[issue.priority] || HOME_EXECUTION_PRIORITY_WEIGHT.med;
      const statusWeight = HOME_EXECUTION_STATUS_WEIGHT[issue.status] || 0;
      const dueScore = homeExecutionDueWeight(dueState);
      const priorityScore = priorityWeight * 100;
      const statusScore = statusWeight * 10;
      const daysDelta = Math.abs(daysBetweenLocal(today, issue.due));
      const score = dueScore + priorityScore + statusScore - daysDelta;
      const nextStatus = homeExecutionIssueNextStatus(issue.status);
      const priority = issue.priority || "med";
      const priorityLabel = PRIORITY_LABEL[issue.priority] || issue.priority || "Medium";
      const reasonChips = [
        { key: `due:${dueState}`, label: homeExecutionDueReasonLabel(dueState) },
        { key: `priority:${priority}`, label: priorityLabel },
        { key: `status:${issue.status || "todo"}`, label: STATUS_LABEL[issue.status] || issue.status || "To Do" },
      ];
      return {
        type: "issue",
        id: issue.id,
        title: issue.title,
        context: `${projectName(issue.project)} · ${STATUS_LABEL[issue.status] || issue.status} · ${memberName(issue.assignee)}`,
        due: issue.due,
        dueState,
        priority,
        priorityLabel,
        score,
        scoreBreakdown: `due=${dueScore};priority=${priorityScore};status=${statusScore};age=-${daysDelta}`,
        reasonKey: homeExecutionReasonKey(reasonChips),
        reasonChips,
        action: "open-issue",
        quickAction: "home-execution-issue-next",
        quickActionLabel: ISSUE_STATUS_LABELS[nextStatus] || "진행",
        quickActionState: nextStatus,
        idAttr: "issue-id",
      };
    });

  const allCandidates = [...todoItems, ...issueItems];
  const focusBuckets = homeExecutionBucketSummary(allCandidates);
  const normalizedBucketFilter = normalizeHomeExecutionBucketFilter(bucketFilter, focusBuckets);
  const visibleCandidates = homeExecutionCandidatesForBucket(allCandidates, normalizedBucketFilter);
  const visibleSortedCandidates = visibleCandidates.sort(compareHomeExecutionQueueItems);
  const items = visibleSortedCandidates.slice(0, 6);
  [
    { type: "todo", candidates: todoItems },
    { type: "issue", candidates: issueItems },
  ].forEach(({ type, candidates }) => {
    const bucketCandidates = homeExecutionCandidatesForBucket(candidates, normalizedBucketFilter);
    if (!bucketCandidates.length || items.some((item) => item.type === type)) return;
    const candidate = [...bucketCandidates].sort(compareHomeExecutionQueueItems)[0];
    if (!candidate) return;
    if (items.length >= 6) items[items.length - 1] = candidate;
    else items.push(candidate);
  });
  items.sort(compareHomeExecutionQueueItems);
  const filteredTypeCounts = homeExecutionTypeCounts(visibleCandidates);
  const filteredTodoCount = filteredTypeCounts.todoCount;
  const filteredIssueCount = filteredTypeCounts.issueCount;
  const hiddenCandidateCount = Math.max(visibleCandidates.length - items.length, 0);
  const {
    windowDuePressureCount,
    windowHighPriorityCount,
    windowActiveIssueCount,
  } = homeExecutionWindowDriverCounts(items);
  const windowDriver = homeExecutionWindowDriverModel({
    dueCount: windowDuePressureCount,
    priorityCount: windowHighPriorityCount,
    activeCount: windowActiveIssueCount,
  });
  const dueStateCounts = homeExecutionDueStateCounts(allCandidates);

  return {
    source: "linear_todoist_priority_due_benchmark",
    itemCount: items.length,
    filteredCandidateCount: visibleCandidates.length,
    filteredTodoCount,
    filteredIssueCount,
    hiddenCandidateCount,
    windowDuePressureCount,
    windowHighPriorityCount,
    windowActiveIssueCount,
    windowLeadDriverKey: windowDriver.leadDriverKey,
    windowLeadDriverLabel: windowDriver.leadDriverLabel,
    windowLeadDriverCount: windowDriver.leadDriverCount,
    windowLeadDriverTieCount: windowDriver.leadDriverTieCount,
    totalCandidateCount: todoItems.length + issueItems.length,
    todoCount: todoItems.length,
    issueCount: issueItems.length,
    overdueCount: dueStateCounts.overdueCount,
    todayCount: dueStateCounts.todayCount,
    upcomingCount: dueStateCounts.upcomingCount,
    activeBucket: focusBuckets[0]?.key || "",
    bucketFilter: normalizedBucketFilter,
    bucketFilterLabel: HOME_EXECUTION_BUCKET_LABEL[normalizedBucketFilter] || HOME_EXECUTION_BUCKET_LABEL.all,
    bucketKey: homeExecutionBucketKey(focusBuckets),
    focusBuckets,
    topScore: items[0]?.score || 0,
    windowFloorScore: items[items.length - 1]?.score || 0,
    items,
  };
}

function homeExecutionQueueHTML(model) {
  return homeExecutionViewCall("homeExecutionQueueHTML", model);
}

function setHomeExecutionBucketFilter(bucketKey) {
  state.homeExecutionBucketFilter = normalizeHomeExecutionBucketFilter(bucketKey, HOME_EXECUTION_BUCKET_ORDER.map((key) => ({ key })));
  if (dashboard.currentView === "home") renderHome();
}

function completeHomeExecutionTodo(id) {
  const todo = todoById(id);
  if (!todo || todo.done) return;
  const previousCompletedAt = todo.completedAt || null;
  todo.done = true;
  todo.completedAt = nowISO();
  commit();
  showUndoToast("오늘 실행 큐 할 일을 완료했습니다", () => {
    const current = todoById(id);
    if (!current) return;
    current.done = false;
    if (previousCompletedAt) current.completedAt = previousCompletedAt;
    else delete current.completedAt;
    commit();
    showToast("할 일 완료를 되돌렸습니다", "info");
  });
}

function advanceHomeExecutionIssue(id, nextStatus) {
  const issue = indexes.issueById.get(id);
  if (!issue || !ISSUE_STATUS_LABELS[nextStatus] || issue.status === nextStatus) return;
  const previousStatus = issue.status;
  const moved = insertIssueIntoKanbanLane(issue, nextStatus);
  if (!moved) return;
  commit();
  showUndoToast(`이슈를 '${ISSUE_STATUS_LABELS[nextStatus]}'으로 이동했습니다`, () => {
    const current = indexes.issueById.get(id);
    if (!current || !ISSUE_STATUS_LABELS[previousStatus]) return;
    insertIssueIntoKanbanLane(current, previousStatus);
    commit();
    showToast("이슈 상태 이동을 되돌렸습니다", "info");
  });
}









function firstStatusItem(items, status) {
  return (items || []).find((item) => item && item.status === status) || null;
}

function firstNonPassingStatusItem(items) {
  return (items || []).find((item) => item && item.status && item.status !== "pass") || null;
}

function firstStringIncluding(items, ...needles) {
  const list = Array.isArray(items) ? items : [];
  return list.find((item) => needles.every((needle) => String(item).includes(needle))) || "";
}

function nextStatusItem(items, fallback = {}, statuses = ["action_required"]) {
  for (const status of statuses) {
    const item = firstStatusItem(items, status);
    if (item) return item;
  }
  return items[0] || fallback;
}

function readyStatusCounts(items) {
  const readyCount = items.filter((item) => item.status === "ready").length;
  return {
    readyCount,
    actionRequiredCount: items.length - readyCount,
  };
}

function homeFirstRunGuidanceModel({
  todaysEvents,
  openTodos,
  noteCount,
  totalProjects,
  publishBlockers,
  externalClaimReady,
  launchProofReady,
}) {
  const firstRunSteps = [
    {
      key: "capture_today",
      label: "오늘 업무 캡처",
      status: todaysEvents.length || openTodos.length || noteCount ? "ready" : "action_required",
      metric: `${todaysEvents.length + openTodos.length + noteCount} items`,
      detail: "할 일, 일정, 메모 중 하나를 먼저 넣으면 홈 KPI와 오늘 패널이 바로 의미를 갖습니다.",
      action: "todo-add",
      actionLabel: "할 일 추가",
      viewName: "",
    },
    {
      key: "shape_project",
      label: "프로젝트 구조화",
      status: totalProjects ? "ready" : "action_required",
      metric: `${totalProjects} projects`,
      detail: "프로젝트를 하나 만들면 Kanban, Gantt, 팀 부하가 같은 운영 맥락으로 연결됩니다.",
      action: "project-add",
      actionLabel: "프로젝트 만들기",
      viewName: "",
    },
    {
      key: "review_system",
      label: "운영 증거 확인",
      status: publishBlockers.length ? "blocked" : "ready",
      metric: `${publishBlockers.length} blockers`,
      detail: "System Status에서 release gate, public launch blocker, 증거 수집 명령을 확인합니다.",
      action: "nav-to",
      actionLabel: "System 보기",
      viewName: "system",
    },
    {
      key: "protect_data",
      label: "백업/복구 준비",
      status: "ready",
      metric: "local JSON",
      detail: "Settings에서 저장소 상태, JSON export, 가져오기 제한을 확인해 데이터를 안전하게 다룹니다.",
      action: "nav-to",
      actionLabel: "Settings 보기",
      viewName: "settings",
    },
  ];
  const firstRunCounts = readyStatusCounts(firstRunSteps);
  const firstRunReadyCount = firstRunCounts.readyCount;
  const firstRunActionRequiredCount = firstRunCounts.actionRequiredCount;
  const firstRunNextStep = nextStatusItem(firstRunSteps, {}, ["action_required", "blocked"]);
  const firstRunGuidedStartItems = [
    {
      key: "workspace_purpose",
      label: "무엇을 관리하나",
      status: "ready",
      metric: "local workspace",
      detail: "일정, 할 일, 프로젝트, DB 카탈로그를 한 브라우저 로컬 workspace에서 관리합니다.",
      action: "orientation",
    },
    {
      key: "next_action",
      label: "다음 행동",
      status: firstRunNextStep.status,
      metric: firstRunNextStep.actionLabel,
      detail: `${firstRunNextStep.label}부터 시작하면 Home KPI와 운영 패널이 실제 데이터로 바뀝니다.`,
      action: firstRunNextStep.action,
    },
    {
      key: "public_proof_guard",
      label: "공개 증거",
      status: externalClaimReady ? "ready" : "blocked",
      metric: `readyForExternalClaim=${externalClaimReady ? "true" : "false"}`,
      detail: launchProofReady ? "공개 증거가 준비되어 launch receipt 확인으로 넘어갈 수 있습니다." : "workflow 설치와 launch proof가 pass할 때까지 외부 공개 완료 주장을 막습니다.",
      action: "proof-guard",
    },
  ];
  const firstRunGuidedStartCoverage = firstRunGuidedStartItems.length === 3 &&
    firstRunSteps.length === 4 &&
    !!firstRunNextStep.key &&
    firstRunGuidedStartItems.every((item) => item.key && item.label && item.status && item.metric && item.detail && item.action)
      ? 1
      : 0;

  return {
    firstRunSteps,
    firstRunReadyCount,
    firstRunActionRequiredCount,
    firstRunNextStep,
    firstRunGuidedStartItems,
    firstRunGuidedStartCoverage,
  };
}

function homeProjectFollowThroughModel({ totalProjects, totalIssues, milestoneCount, teamCount }) {
  const projectFollowThroughSteps = totalProjects ? [
    {
      key: "first_issue",
      label: "첫 이슈 연결",
      status: totalIssues ? "ready" : "action_required",
      metric: `${totalIssues} issues`,
      detail: "프로젝트를 만든 뒤 실제 실행 항목을 Kanban에 올려 진행 상태를 추적합니다.",
      action: "issue-add",
      actionLabel: "이슈 만들기",
      viewName: "pm-kanban",
    },
    {
      key: "first_milestone",
      label: "마일스톤 잡기",
      status: milestoneCount ? "ready" : "action_required",
      metric: `${milestoneCount} milestones`,
      detail: "Gantt 작업을 마일스톤으로 표시해 프로젝트의 다음 단계와 목표일을 고정합니다.",
      action: "task-add",
      actionLabel: "마일스톤 만들기",
      viewName: "pm-gantt",
      defaultMilestone: true,
    },
    {
      key: "first_owner",
      label: "담당자 추가",
      status: teamCount ? "ready" : "action_required",
      metric: `${teamCount} members`,
      detail: "팀 멤버를 등록해 이슈와 작업을 책임자 중심으로 배정할 수 있게 만듭니다.",
      action: "member-add",
      actionLabel: "담당자 추가",
      viewName: "pm-team",
    },
  ] : [];
  const projectFollowThroughCounts = readyStatusCounts(projectFollowThroughSteps);
  const projectFollowThroughReadyCount = projectFollowThroughCounts.readyCount;
  const projectFollowThroughActionRequiredCount = projectFollowThroughCounts.actionRequiredCount;
  const projectFollowThroughNextStep = nextStatusItem(projectFollowThroughSteps);
  return {
    projectFollowThroughSteps,
    projectFollowThroughReadyCount,
    projectFollowThroughActionRequiredCount,
    projectFollowThroughNextStep,
  };
}

/* ============================================================
 * View: Home
 * ============================================================ */

function homeTodayCommandContentHTML({ todaysEvents, overdueTodos, todayTodos, upcoming }) {
  const todayEventsHTML = todaysEvents.length
    ? todaysEvents.map((e) => eventRow(e, { compact: true })).join("")
    : html`<p class="agenda-empty">오늘 등록된 일정이 없습니다.</p>`;
  const todayTodoList = [...overdueTodos, ...todayTodos];
  const todayTodosHTML = todayTodoList.length
      ? html`<div class="home-today-todos">${todayTodoList.slice(0, 6).map((t) => raw(html`
        <div class="agenda-todo-row">
          <button type="button" class="todo-check-mini" data-action="todo-toggle" data-todo-id="${t.id}" aria-label="${t.title} ${t.done ? "완료 취소" : "완료 처리"}"></button>
          <button type="button" class="agenda-todo-open" data-action="open-todo" data-todo-id="${t.id}">
            <span class="agenda-todo-title">${t.title}</span>
            <span class="todo-due ${raw(dueLabel(t.due).cls)}">${dueLabel(t.due).text}</span>
          </button>
        </div>`))}</div>`
    : html`<p class="agenda-empty">오늘 마감인 할 일이 없습니다. 👍</p>`;
  const upcomingHTML = upcoming.length
    ? html`<ul class="home-upcoming">${upcoming.map((e) => {
        const c = EVENT_CATS[e.category] || EVENT_CATS.etc;
        const openId = e._masterId || e.id;
        return raw(html`<li>
          <button type="button" class="home-upcoming-open" data-action="open-event" data-event-id="${openId}">
            <span class="up-date" style="color:${raw(c.color)}">${formatKoreanShort(e.date)}</span>
            <span class="up-title">${e.title}</span>
            <span class="up-time">${eventTimeLabel(e)}</span>
          </button>
        </li>`);
      })}</ul>`
    : html`<p class="agenda-empty">앞으로 7일간 예정된 일정이 없습니다.</p>`;
  return { todayEventsHTML, todayTodosHTML, upcomingHTML };
}

const dashboardStorageHelpers = window.JooParkDashboardStorage && window.JooParkDashboardStorage.version === "joopark-dashboard-storage/v1" && typeof window.JooParkDashboardStorage.create === "function"
  ? window.JooParkDashboardStorage.create()
  : null;
const dashboardPrioritizationHelpers = window.JooParkDashboardPrioritization && window.JooParkDashboardPrioritization.version === "joopark-dashboard-prioritization/v1" && typeof window.JooParkDashboardPrioritization.create === "function"
  ? window.JooParkDashboardPrioritization.create()
  : null;
const dashboardEvidenceReceiptHelpers = window.JooParkDashboardEvidenceReceipts && window.JooParkDashboardEvidenceReceipts.version === "joopark-dashboard-evidence-receipts/v1" && typeof window.JooParkDashboardEvidenceReceipts.create === "function"
  ? window.JooParkDashboardEvidenceReceipts.create({ storage: dashboardStorageHelpers })
  : null;
const dashboardInsightsEngineHelpers = window.JooParkDashboardInsightsEngine && window.JooParkDashboardInsightsEngine.version === "joopark-dashboard-insights-engine/v1" && typeof window.JooParkDashboardInsightsEngine.create === "function"
  ? window.JooParkDashboardInsightsEngine.create()
  : null;
const dashboardAutoresearchLoopHelpers = window.JooParkDashboardAutoresearchLoop && window.JooParkDashboardAutoresearchLoop.version === "joopark-dashboard-autoresearch-loop/v1" && typeof window.JooParkDashboardAutoresearchLoop.create === "function"
  ? window.JooParkDashboardAutoresearchLoop.create()
  : null;
const dashboardViewHelpers = window.JooParkDashboardView && window.JooParkDashboardView.version === "joopark-dashboard-view/v1" && typeof window.JooParkDashboardView.create === "function"
  ? window.JooParkDashboardView.create({ html, raw })
  : null;
const DASHBOARD_COLLECTION_KEYS = Object.freeze([
  "dashboardInsights",
  "dashboardResearchLoops",
  "dashboardImprovementCandidates",
  "dashboardDecisionReceipts",
  "dashboardEvidenceSnapshots",
  "dashboardHealthChecks",
]);

function dashboardStorageCall(name, ...args) {
  return callModuleHelper(dashboardStorageHelpers, "dashboard storage", name, args, "dashboard storage helper unavailable");
}

function ensureDashboardCollections() {
  if (dashboardStorageHelpers) return dashboardStorageCall("ensureCollections", dashboard);
  DASHBOARD_COLLECTION_KEYS.forEach((key) => {
    if (!Array.isArray(dashboard[key])) dashboard[key] = [];
  });
  return dashboard;
}

function dashboardCollectionSummary() {
  if (dashboardStorageHelpers) return dashboardStorageCall("collectionSummary", dashboard);
  return DASHBOARD_COLLECTION_KEYS.map((key) => ({
    key,
    count: Array.isArray(dashboard[key]) ? dashboard[key].length : 0,
    retention: 0,
    latestHash: Array.isArray(dashboard[key]) && dashboard[key][0] ? dashboard[key][0].receiptHash || "" : "",
  }));
}

function dashboardProductLoopState() {
  const summary = state.verifyWorkspaceSummary && state.verifyWorkspaceSummary.data ? state.verifyWorkspaceSummary.data : {};
  const productLoop = summary.artifacts && summary.artifacts.productLoop ? summary.artifacts.productLoop : {};
  const direct = state.productLoopSummary && state.productLoopSummary.data ? state.productLoopSummary.data : {};
  return { ...direct, ...productLoop };
}

function dashboardInsightsModel() {
  ensureDashboardCollections();
  const autoresearchActive = state.dashboardAutoresearchActive === true || !!(dashboard.ui && dashboard.ui.dashboardAutoresearchActive);
  const base = callModuleHelper(dashboardInsightsEngineHelpers, "dashboard insights engine", "dashboardInsightsModel", [{
    dashboard,
    state,
    today: todayISO(),
    createdAt: nowISO(),
    publishItems: publishReadinessItems(),
    productLoop: dashboardProductLoopState(),
  }], "dashboard insights engine helper unavailable");
  const rankedCandidates = callModuleHelper(dashboardPrioritizationHelpers, "dashboard prioritization", "rankCandidates", [base.candidates || []], "dashboard prioritization helper unavailable");
  return {
    ...base,
    candidates: rankedCandidates,
    loops: dashboard.dashboardResearchLoops || [],
    receipts: dashboard.dashboardDecisionReceipts || [],
    latestReceipt: (dashboard.dashboardDecisionReceipts || [])[0] || null,
    autoresearchActive,
    collections: dashboardCollectionSummary(),
  };
}

function dashboardIntelligenceHTML() {
  return callModuleHelper(dashboardViewHelpers, "dashboard view", "renderDashboardIntelligenceHTML", [dashboardInsightsModel()], "dashboard view helper unavailable");
}

function systemDashboardReceiptHTML() {
  return callModuleHelper(dashboardViewHelpers, "dashboard view", "systemDashboardReceiptHTML", [dashboardInsightsModel()], "dashboard view helper unavailable");
}

function runDashboardAutoresearchLoop(options = {}) {
  if (options.active === true) state.dashboardAutoresearchActive = true;
  ensureDashboardUi().dashboardAutoresearchActive = state.dashboardAutoresearchActive === true;
  const result = callModuleHelper(dashboardAutoresearchLoopHelpers, "dashboard autoresearch loop", "runLoop", [{
    dashboard,
    state,
    today: todayISO(),
    createdAt: nowISO(),
    publishItems: publishReadinessItems(),
    productLoop: dashboardProductLoopState(),
    storage: dashboardStorageHelpers,
    prioritization: dashboardPrioritizationHelpers,
    receipts: dashboardEvidenceReceiptHelpers,
    insightsEngine: dashboardInsightsEngineHelpers,
    active: state.dashboardAutoresearchActive === true,
  }], "dashboard autoresearch loop helper unavailable");
  persist();
  updateNavCounts();
  if (dashboard.currentView === "home" || dashboard.currentView === "system") renderCurrentView();
  showToast("AutoResearch loop receipt를 저장했습니다", "info");
  return result;
}

function startDashboardAutoresearchLoop() {
  state.dashboardAutoresearchActive = true;
  ensureDashboardUi().dashboardAutoresearchActive = true;
  return runDashboardAutoresearchLoop({ active: true });
}

function stopDashboardAutoresearchLoop() {
  state.dashboardAutoresearchActive = false;
  ensureDashboardUi().dashboardAutoresearchActive = false;
  persist();
  if (dashboard.currentView === "home" || dashboard.currentView === "system") renderCurrentView();
  showToast("AutoResearch loop를 멈췄습니다", "info");
}

function copyDashboardDecisionReceipt(target) {
  const panel = target.closest("[data-dashboard-decision-receipt]");
  const text = nodeText(panel, "[data-dashboard-decision-receipt-text]");
  const status = nodeQuery(panel, "[data-dashboard-decision-receipt-copy-status]");
  copyTextWithStatus({
    text,
    datasetKey: "dashboardDecisionReceiptCopied",
    targets: [panel, target],
    status,
    copiedStatusText: "복사됨",
    failedStatusText: "복사 실패",
    copiedToast: "dashboard decision receipt를 복사했습니다",
    failedToast: "dashboard decision receipt 복사에 실패했습니다",
  });
}




const homeViewHelpers = window.JooParkHomeView && window.JooParkHomeView.version === "joopark-home-view/v1" && typeof window.JooParkHomeView.create === "function"
  ? window.JooParkHomeView.create({
      refs,
      dashboard,
      state,
      html,
      raw,
      setHTML,
      todayISO,
      addDaysISO,
      eventsOn,
      sortEvents,
      expandOccurrences,
      homeExecutionQueueModel,
      publishReadinessItems,
      safeGithubUrl,
      shortCommit,
      projectBenchmarkContext,
      recordByKey,
      firstStatusItem,
      firstStringIncluding,
      firstNonPassingStatusItem,
      publishEvidenceFresh,
      formatKoreanShort,
      clampInteger,
      homeFirstRunGuidanceModel,
      homeProjectFollowThroughModel,
      kpiCard,
      homeTileHTML,
      homeEmptyHTML,
      HEALTH_COLOR,
      homeListPreviewHTML,
      homeTodayCommandContentHTML,
      homeHeroHTML,
      homeExecutionQueueHTML,
      dashboardIntelligenceHTML,
    })
  : null;

function homeViewCall(name, ...args) {
  return callModuleHelper(homeViewHelpers, "Home view", name, args, "Home view helper unavailable");
}

function renderHome() {
  return homeViewCall("renderHome");
}

/* ============================================================
 * View: Portfolio
 * ============================================================ */

const PORTFOLIO_FILTERS = [
  { key: "all", label: "전체" },
  { key: "owned", label: "운영 프로젝트" },
  { key: "candidates", label: "도입 후보" },
];

const CANDIDATE_ACTION_FILTERS = [
  { key: "all", label: "모든 액션" },
  { key: "spike", label: "스파이크" },
  { key: "architecture", label: "아키텍처 벤치" },
  { key: "pm", label: "PM 벤치" },
  { key: "risk", label: "리스크 리뷰" },
  { key: "calendar", label: "일정 UX 벤치" },
  { key: "watch", label: "월간 관찰" },
  { key: "feature", label: "기능 검토" },
  { key: "source", label: "소스 보강" },
];

const CANDIDATE_BENCHMARK_FILTERS = [
  { key: "all", label: "모든 후보" },
  { key: "focused", label: "벤치 포커스" },
];

function portfolioMatchesFilter(project, filter) {
  if (filter === "owned") return project.sourceKind !== "adoption-candidate";
  if (filter === "candidates") return project.sourceKind === "adoption-candidate";
  return true;
}

function portfolioMatchesActionFilter(project, filter) {
  if (!filter || filter === "all") return true;
  const action = projectCandidateAction(project);
  return project.sourceKind === "adoption-candidate" && action && action.key === filter;
}

function portfolioMatchesBenchmarkFilter(project, filter) {
  if (!filter || filter === "all") return true;
  return project.sourceKind === "adoption-candidate" && !!projectBenchmarkFocus(project);
}

function benchmarkFocusQueueScore(project) {
  const focus = projectBenchmarkFocus(project);
  if (!focus) return 0;
  const text = `${focus.surface} ${focus.flow} ${focus.signals.join(" ")}`.toLowerCase();
  let score = 100;
  if (text.includes("calendar")) score += 20;
  if (text.includes("kanban")) score += 15;
  if (text.includes("pr")) score += 8;
  if (text.includes("task")) score += 5;
  return score;
}

function sortBenchmarkFocusProjects(projects) {
  return [...projects].sort((a, b) => {
    const benchmarkDiff = benchmarkFocusQueueScore(b) - benchmarkFocusQueueScore(a);
    if (benchmarkDiff !== 0) return benchmarkDiff;
    return compareCandidatePriorityThenName(a, b);
  });
}

function compareCandidatePriorityThenName(a, b) {
  const aPriority = projectCandidatePriority(a);
  const bPriority = projectCandidatePriority(b);
  const scoreDiff = (bPriority?.score || 0) - (aPriority?.score || 0);
  return scoreDiff || String(a.name || "").localeCompare(String(b.name || ""));
}

function candidateActionQueueSummary(projects, filter) {
  const selected = recordByKey(CANDIDATE_ACTION_FILTERS, filter) || CANDIDATE_ACTION_FILTERS[0];
  const queue = projects.filter((p) => p.sourceKind === "adoption-candidate" && portfolioMatchesActionFilter(p, selected.key));
  const ranked = [...queue].sort(compareCandidatePriorityThenName);
  const top = ranked[0] || null;
  const topPriority = top ? projectCandidatePriority(top) : null;
  const topAction = top ? projectCandidateAction(top) : null;
  const riskCount = queue.filter((p) => numericMetric(p.risks) >= 3 || numericMetric(p.openIssues) >= 200).length;
  const activeActions = new Set(queue.map((p) => projectCandidateAction(p)?.key).filter(Boolean)).size;
  return html`
    <section class="portfolio-action-summary" data-candidate-action-summary data-action-filter-summary="${selected.key}">
      <div>
        <span>액션 대기열</span>
        <strong>${selected.label}</strong>
      </div>
      <div>
        <span>후보</span>
        <strong>${queue.length}개</strong>
      </div>
      <div>
        <span>최우선</span>
        <strong data-candidate-action-summary-top>${top ? top.name : "없음"}</strong>
        ${topPriority ? raw(html`<small>${topPriority.label} ${topPriority.score}</small>`) : ""}
      </div>
      <div>
        <span>검토 기준</span>
        <strong>${topAction ? topAction.reason : selected.key === "all" ? `${activeActions}개 액션` : "대기 없음"}</strong>
      </div>
      <div>
        <span>리스크</span>
        <strong>${riskCount}개</strong>
      </div>
    </section>
  `;
}

function candidateBenchmarkQueueSummary(projects, filter) {
  const selected = recordByKey(CANDIDATE_BENCHMARK_FILTERS, filter) || CANDIDATE_BENCHMARK_FILTERS[0];
  const focused = sortBenchmarkFocusProjects(projects.filter((p) => p.sourceKind === "adoption-candidate" && projectBenchmarkFocus(p)));
  const top = focused[0] || null;
  const topFocus = top ? projectBenchmarkFocus(top) : null;
  const surfaces = new Set(focused.map((p) => projectBenchmarkFocus(p)?.surface).filter(Boolean)).size;
  return html`
    <section class="portfolio-benchmark-summary" data-candidate-benchmark-summary data-benchmark-filter-summary="${selected.key}">
      <div>
        <span>벤치 대기열</span>
        <strong>${selected.label}</strong>
      </div>
      <div>
        <span>포커스</span>
        <strong>${focused.length}개</strong>
      </div>
      <div>
        <span>최우선</span>
        <strong data-candidate-benchmark-summary-top>${top ? top.name : "없음"}</strong>
      </div>
      <div>
        <span>표면</span>
        <strong>${topFocus ? topFocus.surface : `${surfaces}개 표면`}</strong>
      </div>
      <div>
        <span>흐름</span>
        <strong>${topFocus ? topFocus.flow : "대기 없음"}</strong>
      </div>
    </section>
  `;
}

function rubricRowByAxis(rows, axis) {
  return (rows || []).find((row) => row && row.axis === axis) || null;
}

function rubricWeightLabel(row) {
  return row && row.weight ? `${Math.round(row.weight * 100)}%` : "가중 없음";
}

function rubricScoreLabel(row) {
  return row && row.score ? `${row.score}점` : "점수 없음";
}

function benchmarkRubricAxes(projects, rubricProject) {
  return Array.from(new Set((projects || []).flatMap((project) => rubricProject(project).map((row) => row.axis))));
}

function rubricProjectTitle(projects) {
  return (projects || []).map((project) => project.name.split("/").pop()).join(" / ");
}

function candidateBenchmarkRubric(projects, filter) {
  if (filter !== "focused") return "";
  const focused = sortBenchmarkFocusProjects(adoptionCandidateRubricProjects(projects, projectBenchmarkRubric)).slice(0, 2);
  if (focused.length < 2) return "";
  const axes = ["입력 소스", "AI 보조", "PM 표면", "운영 방식"];
  const rowFor = (project, axis) => rubricRowByAxis(projectBenchmarkRubric(project), axis);
  const scored = rankProjectsByRubric(focused, projectBenchmarkRubricScore);
  const topRecommendation = scored[0] || null;
  const header = html`
    <div class="portfolio-rubric-axis">비교 축</div>
    ${raw(focused.map((project) => {
      const score = projectBenchmarkRubricScore(project);
      return html`<div class="portfolio-rubric-project" data-rubric-project="${project.name}">${project.name}${score ? raw(html`<small data-rubric-total-score="${score.score}">${score.label} ${score.score}</small>`) : ""}</div>`;
    }).join(""))}
  `;
  const rows = axes.map((axis) => html`
    <div class="portfolio-rubric-axis" data-benchmark-rubric-axis="${axis}">${axis}</div>
    ${raw(focused.map((project) => {
      const row = rowFor(project, axis);
      const weight = rubricWeightLabel(row);
      const score = rubricScoreLabel(row);
      return html`<div class="portfolio-rubric-value" data-rubric-project="${project.name}" data-rubric-axis="${axis}" data-rubric-weight="${row ? row.weight : 0}" data-rubric-score="${row ? row.score : 0}"><span>${row ? row.value : "비교 대기"}</span><small>${weight} · ${score}</small></div>`;
    }).join(""))}
  `).join("");
  return html`
    <section class="portfolio-benchmark-rubric" data-candidate-benchmark-rubric>
      <div class="portfolio-rubric-head">
        <span>벤치 비교표</span>
        <strong>${rubricProjectTitle(focused)}</strong>
      </div>
      ${topRecommendation ? raw(html`<div class="portfolio-rubric-score" data-benchmark-rubric-recommendation="${topRecommendation.project.name}" data-rubric-score="${topRecommendation.rubricScore.score}"><span>추천 후보</span><strong>${topRecommendation.project.name}</strong><small>${topRecommendation.rubricScore.label} ${topRecommendation.rubricScore.score}</small></div>`) : ""}
      <div class="portfolio-rubric-grid">
        ${raw(header)}
        ${raw(rows)}
      </div>
      ${raw(candidateBenchmarkRecommendationExport(scored))}
    </section>
  `;
}

function candidateKnowledgeBaseRubric(projects, filter) {
  if (filter !== "focused") return "";
  const focused = rankedAdoptionCandidateRubricProjects(projects, projectKnowledgeBaseRubric, knowledgeBaseBenchmarkRubricRanking, 3);
  if (focused.length < 3) return "";
  const axes = benchmarkRubricAxes(focused, projectKnowledgeBaseRubric);
  const rowFor = (project, axis) => rubricRowByAxis(projectKnowledgeBaseRubric(project), axis);
  const scored = knowledgeBaseBenchmarkRubricRanking(focused);
  const topRecommendation = scored[0] || null;
  const header = html`
    <div class="portfolio-rubric-axis">비교 축</div>
    ${raw(focused.map((project) => {
      const score = projectKnowledgeBaseRubricScore(project);
      return html`<div class="portfolio-rubric-project" data-kb-rubric-project="${project.name}">${project.name}${score ? raw(html`<small data-kb-rubric-total-score="${score.score}">${score.label} ${score.score}</small>`) : ""}</div>`;
    }).join(""))}
  `;
  const rows = axes.map((axis) => html`
    <div class="portfolio-rubric-axis" data-kb-rubric-axis="${axis}">${axis}</div>
    ${raw(focused.map((project) => {
      const row = rowFor(project, axis);
      const weight = rubricWeightLabel(row);
      const score = rubricScoreLabel(row);
      return html`<div class="portfolio-rubric-value" data-kb-rubric-project="${project.name}" data-kb-rubric-axis="${axis}" data-kb-rubric-weight="${row ? row.weight : 0}" data-kb-rubric-score="${row ? row.score : 0}"><span>${row ? row.value : "비교 대기"}</span><small>${weight} · ${score}</small></div>`;
    }).join(""))}
  `).join("");
  return html`
    <section class="portfolio-benchmark-rubric" data-knowledge-base-benchmark-rubric>
      <div class="portfolio-rubric-head">
        <span>KB/IA 비교표</span>
        <strong>${rubricProjectTitle(focused)}</strong>
      </div>
      ${topRecommendation ? raw(html`<div class="portfolio-rubric-score" data-knowledge-base-rubric-recommendation="${topRecommendation.project.name}" data-kb-rubric-score="${topRecommendation.rubricScore.score}"><span>추천 후보</span><strong>${topRecommendation.project.name}</strong><small>${topRecommendation.rubricScore.label} ${topRecommendation.rubricScore.score}</small></div>`) : ""}
      <div class="portfolio-rubric-grid" style="--rubric-project-count:${focused.length}">
        ${raw(header)}
        ${raw(rows)}
      </div>
      ${raw(candidateKnowledgeBaseRecommendationExport(scored))}
      ${raw(candidateKnowledgeBaseReviewHandoff(scored))}
    </section>
  `;
}

function candidateWorkspaceRubric(projects, filter) {
  if (filter !== "focused") return "";
  const focused = rankedAdoptionCandidateRubricProjects(projects, projectWorkspaceRubric, workspaceBenchmarkRubricRanking, 2);
  if (focused.length < 2) return "";
  const axes = benchmarkRubricAxes(focused, projectWorkspaceRubric);
  const rowFor = (project, axis) => rubricRowByAxis(projectWorkspaceRubric(project), axis);
  const scored = workspaceBenchmarkRubricRanking(focused);
  const topRecommendation = scored[0] || null;
  const topFocus = topRecommendation ? projectWorkspaceBenchmark(topRecommendation.project) : null;
  const header = html`
    <div class="portfolio-rubric-axis">비교 축</div>
    ${raw(focused.map((project) => {
      const score = projectWorkspaceRubricScore(project);
      return html`<div class="portfolio-rubric-project" data-workspace-rubric-project="${project.name}">${project.name}${score ? raw(html`<small data-workspace-rubric-total-score="${score.score}">${score.label} ${score.score}</small>`) : ""}</div>`;
    }).join(""))}
  `;
  const rows = axes.map((axis) => html`
    <div class="portfolio-rubric-axis" data-workspace-rubric-axis="${axis}">${axis}</div>
    ${raw(focused.map((project) => {
      const row = rowFor(project, axis);
      const weight = rubricWeightLabel(row);
      const score = rubricScoreLabel(row);
      return html`<div class="portfolio-rubric-value" data-workspace-rubric-project="${project.name}" data-workspace-rubric-axis="${axis}" data-workspace-rubric-weight="${row ? row.weight : 0}" data-workspace-rubric-score="${row ? row.score : 0}"><span>${row ? row.value : "비교 대기"}</span><small>${weight} · ${score}</small></div>`;
    }).join(""))}
  `).join("");
  return html`
    <section class="portfolio-benchmark-rubric" data-workspace-benchmark-rubric data-workspace-benchmark-surface="${topFocus ? topFocus.surface : "JooPark Workspace"}" data-workspace-benchmark-flow="${topFocus ? topFocus.flow : "PM/task + notes/wiki collaboration transfer"}">
      <div class="portfolio-rubric-head">
        <span>Workspace 비교표</span>
        <strong>${rubricProjectTitle(focused)}</strong>
      </div>
      ${topRecommendation ? raw(html`<div class="portfolio-rubric-score" data-workspace-rubric-recommendation="${topRecommendation.project.name}" data-workspace-rubric-score="${topRecommendation.rubricScore.score}"><span>추천 후보</span><strong>${topRecommendation.project.name}</strong><small>${topRecommendation.rubricScore.label} ${topRecommendation.rubricScore.score}</small></div>`) : ""}
      <div class="portfolio-rubric-grid" style="--rubric-project-count:${focused.length}">
        ${raw(header)}
        ${raw(rows)}
      </div>
      ${raw(candidateWorkspaceRecommendationExport(scored))}
      ${raw(candidateWorkspaceReviewHandoff(scored))}
    </section>
  `;
}

function workspaceBenchmarkRecommendationMarkdown(scored) {
  return reviewRecommendationExportCall("workspaceBenchmarkRecommendationMarkdown", scored);
}

function candidateWorkspaceRecommendationExport(scored) {
  return reviewRecommendationExportCall("candidateWorkspaceRecommendationExport", scored);
}

function reviewStatusFromRubricScore(score, highStatus) {
  if (score >= 86) return highStatus;
  if (score >= 80) return "비교 유지";
  return "관찰";
}

function reviewReasonFromAxisOrFocus(rubric, focus, fallback) {
  const topAxis = topWeightedRubricAxis(rubric);
  if (topAxis) return `${topAxis.axis}: ${topAxis.value}`;
  return focus ? focus.flow : fallback;
}

function reviewDecisionRecord(rank, rubricScore, status, fields) {
  return {
    rank: rank + 1,
    status,
    score: rubricScore.score,
    label: rubricScore.label,
    ...fields,
  };
}

function projectWorkspaceReviewDecision(project, rank = 0) {
  const rubricScore = projectWorkspaceRubricScore(project);
  if (!project || !rubricScore) return null;
  const focus = projectWorkspaceBenchmark(project);
  const status = reviewStatusFromRubricScore(rubricScore.score, "Workspace 도입 검토");
  return reviewDecisionRecord(rank, rubricScore, status, {
    surface: focus ? focus.surface : "JooPark Workspace",
    reason: reviewReasonFromAxisOrFocus(projectWorkspaceRubric(project), focus, "Workspace 검토"),
    persistKey: `workspace-review:${project.id}:${rubricScore.score}`,
  });
}

function reviewDecisionsFromScored(scored, createDecision, limit) {
  return limitAndRerankDecisions(
    (Array.isArray(scored) ? scored : [])
      .map(({ project }, index) => ({ project, decision: createDecision(project, index) }))
      .filter((item) => item.decision),
    limit
  );
}

function limitAndRerankDecisions(items, limit) {
  return (Array.isArray(items) ? items : [])
    .slice(0, limit)
    .map((item, index) => ({ ...item, decision: { ...item.decision, rank: index + 1 } }));
}

function reviewPackageBundleArtifacts({ title, kind, primary, decisions, markdown, issueDraft, githubComment, noteBody }) {
  const bundleManifest = reviewPackageManifest({
    kind,
    primaryKey: primary.decision.persistKey,
    decisions,
    handoffMarkdown: markdown,
    issueDraft,
    githubCommentMarkdown: githubComment,
    noteBody,
  });
  const bundleMarkdown = reviewPackageBundleMarkdown({
    title,
    kind,
    primaryKey: primary.decision.persistKey,
    decisions,
    handoffMarkdown: markdown,
    issueDraft,
    githubCommentMarkdown: githubComment,
    noteBody,
    manifest: bundleManifest,
  });
  return { bundleManifest, bundleMarkdown };
}

function reviewPackageValidatedNoteBody(primary, markdown, issueDraft) {
  const key = primary && primary.decision ? primary.decision.persistKey : "";
  if (!key) return "";
  const savedResult = savedReviewResultByKey(key);
  return savedResult ? reviewSavedResultNoteBody(markdown, savedResult, issueDraft ? issueDraft.body : "") : "";
}

function reviewPackageNoteArtifact(kind, primary, noteBody, validatedNoteBody, existingNote) {
  const key = primary && primary.decision ? primary.decision.persistKey : "";
  return {
    kind,
    key,
    staticBody: noteBody,
    validatedBody: validatedNoteBody,
    createdBody: existingNote ? existingNote.body : "",
    sourceKind: existingNote ? existingNote.sourceKind : "",
    createdId: existingNote ? existingNote.id : "",
    artifactType: "note",
    repairReceiptMarkdown: reviewResultRepairReceiptForKey(key),
  };
}

function reviewPackageNoteContext(primary, markdown, issueDraft, artifactKind) {
  const key = primary && primary.decision ? primary.decision.persistKey : "";
  const existingNote = noteBySourceKey(key);
  const noteBody = reviewPackageNoteBody(markdown, issueDraft);
  const validatedNoteBody = reviewPackageValidatedNoteBody(primary, markdown, issueDraft);
  return {
    existingNote,
    noteBody,
    artifact: reviewPackageNoteArtifact(artifactKind, primary, noteBody, validatedNoteBody, existingNote),
  };
}

function reviewPackageHandoffViewHTML({
  kind,
  validatorTitle,
  decisions,
  primary,
  markdown,
  noteContext,
  issueDraft,
  githubComment,
  bundleManifest,
  bundleMarkdown,
  bundleFilename,
  issueDraftHTML = "",
  githubCommentHTML = "",
}) {
  return reviewPackageViewCall("reviewPackageHandoffHTML", {
    kind,
    schemaVersion: REVIEW_HANDOFF_SCHEMA_VERSION,
    validatorTitle,
    decisions,
    primary,
    markdown,
    existingNote: noteContext.existingNote,
    issueDraft,
    githubCommentMarkdown: githubComment,
    noteBody: noteContext.noteBody,
    bundleManifest,
    bundleMarkdown,
    bundleFilename,
    issueDraftHTML,
    githubCommentHTML,
    artifact: noteContext.artifact,
  });
}

function reviewPackageHandoffContext({ title, kind, artifactKind, primary, decisions, markdown, issueDraft, githubComment }) {
  const noteContext = reviewPackageNoteContext(primary, markdown, issueDraft, artifactKind);
  const { bundleManifest, bundleMarkdown } = reviewPackageBundleArtifacts({
    title,
    kind,
    primary,
    decisions,
    markdown,
    issueDraft,
    githubComment,
    noteBody: noteContext.noteBody,
  });
  return { noteContext, bundleManifest, bundleMarkdown };
}

const REVIEW_PACKAGE_HANDOFF_CONFIGS = Object.freeze({
  workspace: Object.freeze({
    title: "JooPark Workspace Review Package Bundle",
    kind: "workspace",
    artifactKind: "workspace-note",
    validatorTitle: "Workspace adoption review",
    bundleFilename: "joopark-workspace-review-package.md",
  }),
  "knowledge-base": Object.freeze({
    title: "JooPark Knowledge/IA Review Package Bundle",
    kind: "knowledge-base",
    artifactKind: "kb-note",
    validatorTitle: "Knowledge/IA benchmark review",
    bundleFilename: "joopark-kb-ia-review-package.md",
  }),
  benchmark: Object.freeze({
    title: "JooPark PM Benchmark Review Package Bundle",
    kind: "benchmark",
    artifactKind: "benchmark-note",
    validatorTitle: "PM benchmark review",
    bundleFilename: "joopark-benchmark-review-package.md",
  }),
});

function reviewPackageConfiguredHandoffHTML(config, { primary, decisions, markdown, issueDraft, githubComment, issueDraftHTML = "", githubCommentHTML = "" }) {
  const { noteContext, bundleManifest, bundleMarkdown } = reviewPackageHandoffContext({
    title: config.title,
    kind: config.kind,
    artifactKind: config.artifactKind,
    primary,
    decisions,
    markdown,
    issueDraft,
    githubComment,
  });
  return reviewPackageHandoffViewHTML({
    kind: config.kind,
    validatorTitle: config.validatorTitle,
    decisions,
    primary,
    markdown,
    noteContext,
    issueDraft,
    githubComment,
    bundleManifest,
    bundleMarkdown,
    bundleFilename: config.bundleFilename,
    issueDraftHTML,
    githubCommentHTML,
  });
}

function reviewPackageHandoffFromDecisions(decisions, {
  config,
  markdownForDecisions,
  issueDraftForDecisions,
  githubCommentForDecisions,
  issueDraftHTMLForDecisions,
  githubCommentHTMLForDecisions,
}) {
  if (!Array.isArray(decisions) || decisions.length === 0) return "";
  if (!config || typeof markdownForDecisions !== "function" || typeof issueDraftForDecisions !== "function" || typeof githubCommentForDecisions !== "function") return "";
  const markdown = markdownForDecisions(decisions);
  if (!markdown) return "";
  const primary = decisions[0];
  const issueDraft = issueDraftForDecisions(decisions);
  const githubComment = githubCommentForDecisions(decisions, issueDraft);
  return reviewPackageConfiguredHandoffHTML(config, {
    primary,
    decisions,
    markdown,
    issueDraft,
    githubComment,
    issueDraftHTML: typeof issueDraftHTMLForDecisions === "function" ? issueDraftHTMLForDecisions(decisions) : "",
    githubCommentHTML: typeof githubCommentHTMLForDecisions === "function" ? githubCommentHTMLForDecisions(decisions) : "",
  });
}

function workspaceReviewDecisions(scored) {
  return reviewDecisionsFromScored(scored, projectWorkspaceReviewDecision, 2);
}

function candidateWorkspaceReviewHandoff(scored) {
  return reviewPackageHandoffFromDecisions(workspaceReviewDecisions(scored), {
    config: REVIEW_PACKAGE_HANDOFF_CONFIGS.workspace,
    markdownForDecisions: workspaceReviewHandoffMarkdown,
    issueDraftForDecisions: workspaceReviewIssueDraft,
    githubCommentForDecisions: workspaceReviewGithubCommentMarkdown,
    issueDraftHTMLForDecisions: candidateWorkspaceReviewIssueDraft,
    githubCommentHTMLForDecisions: candidateWorkspaceReviewGithubComment,
  });
}

const REVIEW_HANDOFF_SCHEMA_VERSION = "joopark-review-handoff/v2";

function promptTableCell(value) {
  const text = value == null ? "" : String(value).replace(/\s+/g, " ").trim();
  return (text || "-").replace(/\|/g, "\\|");
}

function reviewPromptDecisionRows(decisions) {
  return decisions.map(({ project, decision }) => (
    `${decision.rank}. ${project.name} - ${decision.status} - ${decision.label} ${decision.score} - ${decision.persistKey} - ${decision.reason}`
  ));
}

function reviewPromptDecisionInputs(decisions) {
  return decisions.map(({ project, decision }) => [
    `<decision rank="${decision.rank}">`,
    `project: ${project.name}`,
    `status: ${decision.status}`,
    `score: ${decision.score}`,
    `label: ${decision.label}`,
    `persist_key: ${decision.persistKey}`,
    `reason: ${decision.reason}`,
    `source_url: ${project.url || ""}`,
    `language: ${project.language || ""}`,
    `stars: ${metricValue(project.stars)}`,
    `forks: ${metricValue(project.forks)}`,
    `last_commit: ${project.lastCommit || ""}`,
    `pushed_at: ${project.pushedAt || ""}`,
    `open_issues: ${metricValue(project.openIssues)}`,
    `risks: ${metricValue(project.risks)}`,
    `description: ${project.description || ""}`,
    "</decision>",
  ].join("\n")).join("\n\n");
}

const REVIEW_OUTPUT_QUALITY_CRITERIA = [
  ["accuracy", "Use supplied scores, source URLs, commits, and pushedAt values; move unverifiable claims to missingEvidence."],
  ["specificity", "Name the target surface, comparison candidate, persistKey, score, and concrete next action."],
  ["usability", "Return an issue-ready execution plan with acceptance criteria, validation plan, owner, first action, timebox, decision gate, and fallback."],
  ["operational_readiness", "A reviewer should know who acts first, what to do first, when to stop, and what to do if evidence blocks progress."],
  ["owner_accountability", "Use an exact active team member when possible; if the owner is a role, external group, or unmapped string, include requiredFollowUp and assignee confirmation guidance."],
  ["reusability", "Keep stable schemaVersion, persistKey, labels, and Markdown sections for copy, note, and issue workflows."],
  ["satisfaction", "The output should be usable without rewriting by a reviewer, PM, or downstream agent."],
];

function reviewPromptEvidenceRows(decisions) {
  return decisions.map(({ project, decision }) => (
    `| ${decision.rank} | ${promptTableCell(project.name)} | ${promptTableCell(decision.status)} | ${decision.score} | ${promptTableCell(decision.persistKey)} | ${promptTableCell(shortCommit(project.lastCommit) || project.lastCommit || "-")} | ${promptTableCell(project.pushedAt || "-")} | ${metricValue(project.stars)} / ${metricValue(project.forks)} / ${metricValue(project.openIssues)} | ${promptTableCell(decision.reason)} |`
  ));
}

function reviewExecutionPlanLines(config, decisions) {
  const primary = decisions[0];
  const secondary = reviewSecondaryDecision(decisions);
  if (!primary) return [];
  return [
    `1. Verify source metadata for ${primary.project.name}: ${shortCommit(primary.project.lastCommit) || "missing commit"} / ${primary.project.pushedAt || "missing pushedAt"}.`,
    `2. Run a focused review against ${config.primarySurface || config.reviewType} and keep ${secondary ? secondary.project.name : "no comparison candidate"} as the contrast baseline.`,
    `3. Convert the result into an issue or pinned note using persist key ${primary.decision.persistKey}, labels, score, and decision status exactly as supplied.`,
    "4. Mark the output defer/compare if acceptance criteria cannot be proven from the supplied evidence.",
    "5. Name the owner, first action, decision gate, and fallback if blocked so the generated issue can be executed without rewriting.",
  ];
}

function reviewOperationalReadinessLines({ owner, firstAction, timeboxHours, decisionGate, fallbackIfBlocked }) { return reviewIssuePayloadCall("reviewOperationalReadinessLines", { owner, firstAction, timeboxHours, decisionGate, fallbackIfBlocked }); }
function reviewIssueDecisionSummaryLines({ project, decision, secondary, scope, timeboxHours, firstAction, fallbackIfBlocked }) { return reviewIssuePayloadCall("reviewIssueDecisionSummaryLines", { project, decision, secondary, scope, timeboxHours, firstAction, fallbackIfBlocked }); }
function reviewIssueBodyLines({ project, decision, secondary, scope, timeboxHours, acceptanceCriteria, validationPlan }) { return reviewIssuePayloadCall("reviewIssueBodyLines", { project, decision, secondary, scope, timeboxHours, acceptanceCriteria, validationPlan }); }
function reviewPackageNoteBody(handoffMarkdown, draft) { return reviewIssuePayloadCall("reviewPackageNoteBody", handoffMarkdown, draft); }
function reviewMarkdownSection(text, heading) { return reviewIssuePayloadCall("reviewMarkdownSection", text, heading); }
function reviewPinnedNoteSummary(draft) { return reviewIssuePayloadCall("reviewPinnedNoteSummary", draft); }

const REVIEW_PACKAGE_MANIFEST_SCHEMA_VERSION = "joopark-review-package-manifest/v1";
const REVIEW_PACKAGE_REQUIRED_SECTIONS = ["Markdown Handoff", "Issue Draft", "GitHub Comment Draft", "Pinned Note Body"];
const REVIEW_PACKAGE_PASTE_TARGETS = [
  ["tracker_issue", "Tracker issue", "Issue tracker", "Issue Draft"],
  ["github_comment", "GitHub comment", "GitHub issue or comment", "GitHub Comment Draft"],
  ["pinned_note", "Pinned note", "Workspace note", "Pinned Note Body"],
];
const REVIEW_PACKAGE_FINAL_QUALITY_CRITERIA = [
  ["accuracy_evidence", "Accuracy evidence", "source URLs, commits, pushedAt values, persist keys, and checksum are present"],
  ["specific_context", "Specific context", "primary decision, comparison evidence, score, labels, and target surface are explicit"],
  ["execution_ready", "Execution ready", "owner, first action, timebox, decision gate, fallback, acceptance criteria, and validation plan are present"],
  ["reuse_ready", "Reuse ready", "handoff, issue draft, GitHub comment, pinned note, checksum, and copy targets are bundled"],
  ["safety_ready", "Safety ready", "missing evidence and unsafe external completion claims are blocked before status changes"],
  ["submit_ready", "Submit ready", "the package can be pasted into a tracker, comment, or note without rewriting"],
];
const REVIEW_PACKAGE_FINAL_QUALITY_REPAIRS = {
  accuracy_evidence: "Add a Source Snapshot row for every compared project with source URL, commit, pushedAt, score, persist key, and checksum.",
  specific_context: "Restore the primary decision key, persist key, source URL, decision gate, fallback, score, and comparison rationale before sharing.",
  execution_ready: "Fill owner, first action, timebox, decision gate, fallback, Acceptance Criteria, Validation Plan, and Missing Evidence To Close.",
  reuse_ready: "Regenerate the full bundle so Markdown Handoff, Issue Draft, GitHub Comment Draft, Pinned Note Body, checksum, and download/copy targets are present.",
  safety_ready: "Add missing-evidence handling and an explicit guard against unsafe external completion claims before any status update.",
  submit_ready: "Complete the failing quality repairs, then copy the regenerated tracker/comment/note bundle instead of rewriting it manually.",
};

function reviewPackagePayloadChecksum(value) { return reviewHandoffCall("reviewPackagePayloadChecksum", value); }
function reviewPackagePasteTargetReadiness(options) { return reviewHandoffCall("reviewPackagePasteTargetReadiness", options); }
function reviewPackageFinalQualityGate(options) { return reviewHandoffCall("reviewPackageFinalQualityGate", options); }
function reviewPackageManifest(options) { return reviewHandoffCall("reviewPackageManifest", options); }
function reviewPackageManifestMarkdown(manifest) { return reviewHandoffCall("reviewPackageManifestMarkdown", manifest); }
function reviewPackageManifestSummary(options) { return reviewHandoffCall("reviewPackageManifestSummary", options); }
function reviewPackagePastePreview(options) { return reviewHandoffCall("reviewPackagePastePreview", options); }

const REVIEW_PACKAGE_PASTE_PREVIEW_DATA_ATTRIBUTES = [
  "data-workspace-review-package-paste-preview",
  "data-knowledge-base-review-package-paste-preview",
  "data-benchmark-review-package-paste-preview",
];

function reviewPackageBundleMarkdown(options) { return reviewHandoffCall("reviewPackageBundleMarkdown", options); }
function reviewPackageBundleControls(options) { return reviewHandoffCall("reviewPackageBundleControls", options); }
function reviewGithubCommentMarkdown(options) { return reviewResultViewCall("reviewGithubCommentMarkdown", options); }
function genericReviewGithubCommentMarkdown(title, decisions, draft) { return reviewGithubCommentMarkdown({ title, decisions, draft }); }
function reviewGithubCommentMarkdownFromDraft(title, decisions, buildDraft) {
  const draft = buildDraft(decisions);
  return genericReviewGithubCommentMarkdown(title, decisions, draft);
}

function reviewResultIssuePrefix(reviewType) {
  const type = String(reviewType || "").toLowerCase();
  if (type.includes("workspace")) return "[Workspace]";
  if (type.includes("knowledge") || type.includes("ia")) return "[KB/IA]";
  if (type.includes("benchmark")) return "[Benchmark]";
  return "[Review]";
}

function reviewResultDefaultLabels(reviewType) {
  const prefix = reviewResultIssuePrefix(reviewType);
  if (prefix === "[Workspace]") return ["workspace", "benchmark", "handoff", "adoption"];
  if (prefix === "[KB/IA]") return ["knowledge-base", "ia", "handoff", "adoption"];
  if (prefix === "[Benchmark]") return ["benchmark", "handoff", "adoption"];
  return ["handoff", "review"];
}

let reviewExecutionChecklistHelpers = null;
function getReviewExecutionChecklistHelpers() { return reviewExecutionChecklistHelpers = createLazyRuntimeHelpers(reviewExecutionChecklistHelpers, "JooParkReviewExecutionChecklist", { parseSavedReviewResult, reviewPrimaryDecision }); }

function fallbackIssueExecutionChecklistItems(issue) {
  return (Array.isArray(issue && issue.executionChecklist) ? issue.executionChecklist : [])
    .map((item, index) => {
      if (typeof item === "string") return { id: `exec-${index + 1}`, text: item, done: false };
      return {
        id: item && item.id ? String(item.id) : `exec-${index + 1}`,
        text: item && item.text ? String(item.text) : "",
        done: !!(item && item.done),
      };
    })
    .filter((item) => item.text.trim());
}

function fallbackReviewExecutionChecklistItemsFromSavedResult(saved) {
  const result = parseSavedReviewResult(saved);
  if (!result) return [];
  const decisions = Array.isArray(result.decisions) ? result.decisions : [];
  const primary = reviewPrimaryDecision(decisions, saved && saved.key);
  const plans = Array.isArray(result.executionPlan) ? result.executionPlan : [];
  const primaryPlan = plans[0] || {};
  const executionCriteria = plans.flatMap((plan) => Array.isArray(plan && plan.acceptanceCriteria) ? plan.acceptanceCriteria : []);
  const executionValidation = plans.flatMap((plan) => Array.isArray(plan && plan.validationPlan) ? plan.validationPlan : []);
  const items = uniqueTextItems([
    primaryPlan.firstAction || primaryPlan.action ? `First action: ${primaryPlan.firstAction || primaryPlan.action}` : "",
    ...(Array.isArray(primary.acceptanceCriteria) ? primary.acceptanceCriteria.map((item) => `Acceptance: ${item}`) : []),
    ...executionCriteria.map((item) => `Acceptance: ${item}`),
    ...(Array.isArray(primary.validationPlan) ? primary.validationPlan.map((item) => `Validation: ${item}`) : []),
    ...executionValidation.map((item) => `Validation: ${item}`),
  ]).slice(0, 8);
  return items.map((text, index) => ({ id: `exec-${index + 1}`, text, done: false }));
}

function fallbackIssueExecutionChecklistProgress(issue) {
  const items = fallbackIssueExecutionChecklistItems(issue);
  const done = items.filter((item) => item.done).length;
  const total = items.length;
  const percent = total ? Math.round((done / total) * 100) : 0;
  return {
    total,
    done,
    remaining: Math.max(0, total - done),
    percent,
    label: total ? `${done}/${total} 완료` : "체크리스트 없음",
  };
}

function fallbackReviewExecutionChecklistLines(items) {
  const checklist = fallbackIssueExecutionChecklistItems({ executionChecklist: items });
  return (checklist.length ? checklist : [{ text: "No execution checklist supplied.", done: false }])
    .map((item) => `- [${item.done ? "x" : " "}] ${item.text}`);
}

function fallbackSyncIssueBodyExecutionChecklist(issue) {
  const body = String(issue && issue.body || "");
  if (!body.includes("## Execution Checklist")) return body;
  const section = ["## Execution Checklist", ...fallbackReviewExecutionChecklistLines(fallbackIssueExecutionChecklistItems(issue))].join("\n");
  return body.replace(/## Execution Checklist\n[\s\S]*?(?=\n## |$)/, section);
}

function fallbackReviewExecutionChecklistCountLabel(items) {
  const count = fallbackIssueExecutionChecklistItems({ executionChecklist: items }).length;
  return count ? `${count}개` : "없음";
}

function fallbackFirstPositiveTimeboxHours(plans) {
  return (Array.isArray(plans) ? plans : [])
    .map((plan) => Number(plan && plan.timeboxHours))
    .find((value) => Number.isFinite(value) && value > 0);
}

function reviewExecutionChecklistFallback(name, ...args) {
  if (name === "reviewExecutionChecklistItemsFromSavedResult") return fallbackReviewExecutionChecklistItemsFromSavedResult(args[0]);
  if (name === "issueExecutionChecklistItems") return fallbackIssueExecutionChecklistItems(args[0]);
  if (name === "issueExecutionChecklistProgress") return fallbackIssueExecutionChecklistProgress(args[0]);
  if (name === "reviewExecutionChecklistLines") return fallbackReviewExecutionChecklistLines(args[0]);
  if (name === "syncIssueBodyExecutionChecklist") return fallbackSyncIssueBodyExecutionChecklist(args[0]);
  if (name === "reviewExecutionChecklistCountLabel") return fallbackReviewExecutionChecklistCountLabel(args[0]);
  if (name === "firstPositiveTimeboxHours") return fallbackFirstPositiveTimeboxHours(args[0]);
  throw new Error(`Review execution checklist fallback missing: ${name}`);
}

function reviewExecutionChecklistCall(name, ...args) {
  const helpers = getReviewExecutionChecklistHelpers();
  if (!helpers) return reviewExecutionChecklistFallback(name, ...args);
  return callModuleHelper(helpers, "review execution checklist", name, args, "Review execution checklist runtime helper missing");
}

let reviewIssuePayloadHelpers = null;
function getReviewIssuePayloadHelpers() { return reviewIssuePayloadHelpers = createLazyRuntimeHelpers(reviewIssuePayloadHelpers, "JooParkReviewIssuePayload", { shortCommit, metricValue, parseSavedReviewResult, projectByIdOrName, reviewExecutionChecklistItemsFromSavedResult, reviewOwnerAssignment, reviewOwnerFollowUpItems, reviewOwnerPromptExamples, todayISO, addDays }); }

function reviewIssuePayloadCall(name, ...args) { return callModuleHelper(getReviewIssuePayloadHelpers(), "review issue payload", name, args, "Review issue payload runtime helper missing"); }

let reviewResultViewHelpers = null;
function getReviewResultViewHelpers() { return reviewResultViewHelpers = createLazyRuntimeHelpers(reviewResultViewHelpers, "JooParkReviewResultView", { html, raw, schemaVersion: REVIEW_HANDOFF_SCHEMA_VERSION, clampText, clampTextArray, clampInteger, formatLocalDateTime, nowISO, shortCommit, metricValue, memberName, reviewOperationalReadinessLines, reviewMarkdownList, reviewExecutionChecklistLines }); }

function reviewResultViewCall(name, ...args) { return callModuleHelper(getReviewResultViewHelpers(), "review result view", name, args, "Review result view runtime helper missing"); }

let reviewHandoffHelpers = null;
function getReviewHandoffHelpers() { return reviewHandoffHelpers = createLazyRuntimeHelpers(reviewHandoffHelpers, "JooParkReviewHandoff", { html, raw, dashboard, safeGithubUrl, shortCommit, metricValue, numericMetric, promptTableCell, reviewPromptDecisionRows, reviewPromptDecisionInputs, reviewPromptEvidenceRows, reviewExecutionPlanLines, reviewOwnerAssignment, reviewOwnerRequiredFollowUpText, reviewResultIssuePrefix, reviewResultDefaultLabels, savedReviewResultByKey, reviewResultSavedCard, memberName }); }

function reviewHandoffCall(name, ...args) { return callModuleHelper(getReviewHandoffHelpers(), "review handoff", name, args, "Review handoff runtime helper missing"); }

let reviewArtifactViewHelpers = null;
function getReviewArtifactViewHelpers() { return reviewArtifactViewHelpers = createLazyRuntimeHelpers(reviewArtifactViewHelpers, "JooParkReviewArtifactView", { html, raw, clampText, promptTableCell, formatLocalDateTime, escapeHtml, reviewArtifactRepairUndoFor, contractTerms: ["post-apply fresh receipt", "data-review-artifact-repair-preview"] }); }

function reviewArtifactViewCall(name, ...args) { return callModuleHelper(getReviewArtifactViewHelpers(), "review artifact view", name, args, "Review artifact view runtime helper missing"); }

let reviewPackageViewHelpers = null;
function getReviewPackageViewHelpers() { return reviewPackageViewHelpers = createLazyRuntimeHelpers(reviewPackageViewHelpers, "JooParkReviewPackageView", { html, raw, reviewResultValidator, reviewPackageManifestSummary, reviewPackagePastePreview, reviewPackageBundleControls, reviewArtifactDiffPanel }); }

function reviewPackageViewCall(name, payload) { return callModuleHelper(getReviewPackageViewHelpers(), "review package view", name, [payload], "Review package view runtime helper missing"); }


function reviewPromptSchema(primary, config) { return reviewHandoffCall("reviewPromptSchema", primary, config); }
function reviewResultExample(primary, reviewType) { return reviewHandoffCall("reviewResultExample", primary, reviewType); }

function savedReviewResultByKey(key) {
  return recordByKey(dashboard.reviewResults, key);
}

function reviewResultRepairReceiptForKey(key) {
  const saved = savedReviewResultByKey(key);
  return saved && saved.repairReceiptReady ? saved.postRepairReceipt || saved.repairReceiptMarkdown || "" : "";
}

function reviewIssueDraftOverrideByKey(key) {
  if (!key) return null;
  return recordByKey(dashboard.reviewIssueDraftOverrides, key);
}

function reviewDraftWithPersistedAssigneeOverride(draft) {
  if (!draft || !draft.persistKey || draft.assigneeOverride) return draft;
  const override = reviewIssueDraftOverrideByKey(draft.persistKey);
  if (!override) return draft;
  return {
    ...draft,
    assignee: override.assignee || "",
    assigneeOverride: true,
    assigneeOverrideSavedAt: override.savedAt || "",
  };
}

function saveReviewIssueDraftAssigneeOverride(key, assignee) {
  const normalizedKey = clampText(key || "", 180);
  if (!normalizedKey) return null;
  const savedAt = nowISO();
  dashboard.reviewIssueDraftOverrides = (Array.isArray(dashboard.reviewIssueDraftOverrides) ? dashboard.reviewIssueDraftOverrides : [])
    .filter((item) => item && item.key !== normalizedKey);
  const override = {
    key: normalizedKey,
    assignee: clampText(assignee || "", 80),
    savedAt,
  };
  dashboard.reviewIssueDraftOverrides.push(override);
  normalizeAllData();
  persist();
  return override;
}

function reviewResultSavedCard(saved) { return reviewResultViewCall("reviewResultSavedCard", saved); }

function renderSavedReviewResult(validator, saved) {
  const panel = nodeQuery(validator, "[data-review-result-saved-panel]");
  if (!panel) return;
  panel.dataset.reviewResultSaved = saved ? "true" : "false";
  setHTML(panel, reviewResultSavedCard(saved));
}

function reviewResultManifestEvidence(validator) {
  const handoff = reviewHandoffNode(validator);
  const manifest = nodeQuery(handoff, "[data-review-package-manifest]");
  if (!manifest) {
    return {
      packageChecksum: "",
      packageManifestStatus: "missing",
      packageSourceFreshness: "missing",
      packageSourceCount: 0,
    };
  }
  return {
    packageChecksum: manifest.dataset.reviewPackagePayloadChecksum || "",
    packageManifestStatus: manifest.dataset.reviewPackageManifestStatus || "",
    packageSourceFreshness: manifest.dataset.reviewPackageSourceFreshness || "",
    packageSourceCount: clampInteger(manifest.dataset.reviewPackageSourceCount, 0, 20),
  };
}

function compactReviewResult(result, expectedKey, reviewType, warnings, manifestEvidence) {
  return reviewResultViewCall("compactReviewResult", {
    result,
    expectedKey,
    reviewType,
    warnings,
    manifestEvidence,
  });
}

function saveValidatedReviewResult(validator, result, warnings) {
  if (!validator || !result || typeof result !== "object") return null;
  const key = validator.dataset.reviewResultPrimaryKey || "";
  if (!key) return null;
  const saved = compactReviewResult(result, key, validator.dataset.reviewResultType || "", warnings || [], reviewResultManifestEvidence(validator));
  const existingIndex = recordIndexByKey(dashboard.reviewResults, key);
  if (existingIndex >= 0) dashboard.reviewResults[existingIndex] = saved;
  else dashboard.reviewResults.push(saved);
  normalizeAllData();
  persist();
  validator.dataset.reviewResultSaved = "true";
  renderSavedReviewResult(validator, saved);
  refreshReviewIssueDraftFromSavedResult(validator, saved);
  showToast("검증 결과를 저장했습니다", "info");
  return saved;
}

function parseSavedReviewResult(saved) {
  if (!saved || !saved.resultJson) return null;
  try {
    const parsed = JSON.parse(saved.resultJson);
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : null;
  } catch (_) {
    return null;
  }
}

const REVIEW_HANDOFF_SELECTOR = "[data-benchmark-review-handoff], [data-knowledge-base-review-handoff], [data-workspace-review-handoff]";

function reviewHandoffNode(node) {
  return node ? node.closest(REVIEW_HANDOFF_SELECTOR) : null;
}

function reviewPrimaryDecision(decisions, key) {
  const list = Array.isArray(decisions) ? decisions : [];
  return list.find((decision) => decision && decision.persistKey === key) || list[0] || {};
}

function reviewSecondaryDecision(decisions) {
  const list = Array.isArray(decisions) ? decisions : [];
  return list.find((item) => item && item.decision && item.decision.rank > 1) || null;
}

function uniqueTextItems(items) {
  const seen = new Set();
  return (Array.isArray(items) ? items : [])
    .map((item) => String(item || "").trim())
    .filter((item) => {
      if (!item || seen.has(item)) return false;
      seen.add(item);
      return true;
    });
}

function reviewMarkdownList(items, fallback) {
  const list = uniqueTextItems(items);
  return (list.length ? list : [fallback || "No validated item supplied."]).map((item) => `- ${item}`);
}

function reviewExecutionChecklistItemsFromSavedResult(saved) { return reviewExecutionChecklistCall("reviewExecutionChecklistItemsFromSavedResult", saved); }
function issueExecutionChecklistItems(issue) { return reviewExecutionChecklistCall("issueExecutionChecklistItems", issue); }
function issueExecutionChecklistProgress(issue) { return reviewExecutionChecklistCall("issueExecutionChecklistProgress", issue); }

function renderIssueExecutionChecklistControls(issue) {
  const items = issueExecutionChecklistItems(issue);
  const progress = issueExecutionChecklistProgress(issue);
  return reviewResultViewCall("issueExecutionChecklistControls", {
    issueId: issue && issue.id || "",
    items,
    progress,
  });
}

function reviewExecutionChecklistLines(items) { return reviewExecutionChecklistCall("reviewExecutionChecklistLines", items); }
function syncIssueBodyExecutionChecklist(issue) { return reviewExecutionChecklistCall("syncIssueBodyExecutionChecklist", issue); }

function reviewIssueArtifactKind(issue) {
  const key = String(issue && issue.sourceKey || "");
  if (key.startsWith("benchmark-review:")) return "benchmark-issue";
  if (key.startsWith("workspace-review:")) return "workspace-issue";
  if (key.startsWith("kb-ia-review:")) return "kb-issue";
  return "issue";
}

function reviewIssueFreshReceipt(issue) {
  const createdBody = String(issue && issue.body || "");
  const checks = reviewArtifactDiffChecks({ createdBody, sourceKind: issue && issue.sourceKind || "" });
  const status = checks.every((check) => check.status === "pass") ? "pass" : "pending";
  const kind = reviewIssueArtifactKind(issue);
  const key = issue && issue.sourceKey ? issue.sourceKey : issue && issue.id || "";
  const markdown = reviewArtifactReceiptMarkdown({
    kind,
    key,
    status,
    sourceKind: issue && issue.sourceKind || "",
    createdId: issue && issue.id || "",
    artifactType: "issue",
    createdBody,
    checks,
  });
  return { kind, key, status, checks, markdown };
}

function renderIssueFreshReceiptControls(issue) {
  const progress = issueExecutionChecklistProgress(issue);
  const receipt = reviewIssueFreshReceipt(issue);
  return reviewArtifactViewCall("issueFreshReceiptControls", {
    issueId: issue && issue.id || "",
    receipt,
    progress,
  });
}

function reviewExecutionChecklistCountLabel(items) {
  return reviewExecutionChecklistCall("reviewExecutionChecklistCountLabel", items);
}

function reviewSavedResultSourceSnapshot(sourceSnapshot, primary) {
  const list = Array.isArray(sourceSnapshot) ? sourceSnapshot : [];
  const primaryProject = primary && primary.project;
  return list.find((item) => item && (item.project === primaryProject || item.sourceUrl)) || {};
}

function reviewSavedResultBody(saved, fallbackBody, options = {}) {
  const result = parseSavedReviewResult(saved);
  if (!result) return fallbackBody || "";
  const safeSaved = saved || {};
  const decisions = Array.isArray(result.decisions) ? result.decisions : [];
  const primary = reviewPrimaryDecision(decisions, safeSaved.key);
  const source = reviewSavedResultSourceSnapshot(result.sourceSnapshot, primary);
  const executionPlan = Array.isArray(result.executionPlan) ? result.executionPlan : [];
  const executionCriteria = executionPlan.flatMap((plan) => Array.isArray(plan && plan.acceptanceCriteria) ? plan.acceptanceCriteria : []);
  const executionValidation = executionPlan.flatMap((plan) => Array.isArray(plan && plan.validationPlan) ? plan.validationPlan : []);
  const missingEvidence = Array.isArray(primary.missingEvidence) ? primary.missingEvidence : [];
  const exceptions = Array.isArray(result.exceptions) ? result.exceptions : [];
  const qualityGate = result.qualityGate && typeof result.qualityGate === "object" ? result.qualityGate : {};
  const primaryExecutionPlan = executionPlan[0] || {};
  const savedProject = projectByIdOrName(safeSaved.project, primary.project || safeSaved.project);
  const ownerAssignment = reviewOwnerAssignment(primaryExecutionPlan.owner || "", savedProject);
  const assigneeRequiredFollowUp = options.skipAssigneeFollowUp ? [] : reviewOwnerFollowUpItems(ownerAssignment, primaryExecutionPlan.owner || "", savedProject);
  const assigneePromptExamples = options.skipAssigneeFollowUp ? [] : reviewOwnerPromptExamples(ownerAssignment, primaryExecutionPlan.owner || "", savedProject);
  const executionChecklist = reviewExecutionChecklistItemsFromSavedResult(saved);
  return reviewResultViewCall("reviewSavedResultBody", {
    result,
    saved: safeSaved,
    primary,
    source,
    executionPlan,
    executionCriteria,
    executionValidation,
    missingEvidence,
    exceptions,
    qualityGate,
    primaryExecutionPlan,
    ownerAssignment,
    assigneeRequiredFollowUp,
    assigneePromptExamples,
    executionChecklist,
  });
}

function reviewExecutionPlanForSavedResult(saved) {
  return reviewIssuePayloadCall("reviewExecutionPlanForSavedResult", saved);
}

function teamMemberByRole(members, role) {
  const list = Array.isArray(members) ? members : [];
  return list.find((member) => member && member.role === role) || null;
}

function reviewOwnerExactMember(candidates, query) {
  const list = Array.isArray(candidates) ? candidates : [];
  return list.find((member) => {
    const haystack = [member.id, member.name].map((value) => normalize(value || ""));
    return haystack.some((value) => value && (query === value || query.includes(value) || value.includes(query)));
  }) || null;
}

function reviewOwnerRoleHint(roleHints, query) {
  const list = Array.isArray(roleHints) ? roleHints : [];
  return list.find(([pattern]) => pattern.test(query)) || null;
}

function reviewOwnerAssignment(owner, project) {
  const query = normalize(owner || "").trim();
  if (!query) {
    return {
      assignee: "",
      confidence: "none",
      source: "missing-owner",
      reason: "executionPlan.owner was empty.",
      reviewRequired: true,
    };
  }
  const activeMembers = dashboard.team.filter((member) => !member.onLeave);
  const activeMemberById = new Map();
  activeMembers.forEach((member) => {
    if (!activeMemberById.has(member.id)) activeMemberById.set(member.id, member);
  });
  const projectMemberIds = new Set(Array.isArray(project && project.members) ? project.members : []);
  const projectMembers = activeMembers.filter((member) => projectMemberIds.has(member.id));
  const candidates = uniqueTextItems([...projectMembers, ...activeMembers].map((member) => member.id))
    .map((id) => activeMemberById.get(id))
    .filter(Boolean);
  const exact = reviewOwnerExactMember(candidates, query);
  if (exact) {
    return {
      assignee: exact.id,
      confidence: "high",
      source: "exact-member-match",
      reason: `owner "${owner}" matched ${exact.name}.`,
      reviewRequired: false,
    };
  }
  const roleHints = [
    [/pm|product|reviewer|owner|lead/, "PM"],
    [/qa|quality|test/, "QA"],
    [/design|ia|ux/, "Design"],
    [/frontend|ui|workspace/, "Frontend"],
    [/backend|api|server/, "Backend"],
    [/data|schema|analytics/, "Data"],
    [/devops|ops|release/, "DevOps"],
  ];
  const hintedRole = reviewOwnerRoleHint(roleHints, query);
  if (hintedRole) {
    const member = teamMemberByRole(activeMembers, hintedRole[1]);
    if (member) {
      return {
        assignee: member.id,
        confidence: "medium",
        source: "role-hint",
        reason: `owner "${owner}" matched role ${hintedRole[1]}.`,
        reviewRequired: true,
      };
    }
  }
  const fallback = projectMembers[0] || teamMemberByRole(activeMembers, "PM") || activeMembers[0];
  return {
    assignee: fallback ? fallback.id : "",
    confidence: fallback ? "low" : "none",
    source: fallback && projectMembers.includes(fallback) ? "project-member-fallback" : "team-fallback",
    reason: fallback ? `owner "${owner}" did not match a member; ${fallback.name} was suggested as a fallback.` : `owner "${owner}" did not match any available member.`,
    reviewRequired: true,
  };
}

function reviewOwnerFollowUpItems(assignment, owner, project) {
  if (!assignment || !assignment.reviewRequired) return [];
  const ownerText = owner || "missing owner";
  const assigneeName = assignment.assignee ? memberName(assignment.assignee) : "미지정";
  const projectNameText = project && project.name ? project.name : "선택된 프로젝트";
  if (assignment.confidence === "medium" && assignment.source === "role-hint") {
    return [
      `역할 owner "${ownerText}"가 ${assigneeName}에게 자동 매핑되었습니다. 생성 전 실제 책임자가 맞는지 확인하세요.`,
      `다음 결과에서는 role 대신 정확한 팀원 이름 또는 id를 executionPlan.owner에 넣도록 요청하세요.`,
    ];
  }
  if (assignment.confidence === "low") {
    return [
      `owner "${ownerText}"가 ${projectNameText}의 활성 팀원/역할과 직접 매칭되지 않아 ${assigneeName} fallback으로 제안되었습니다.`,
      "이슈를 진행 상태로 옮기기 전 정확한 담당자를 확인하고, LLM 결과에는 exceptions.requiredFollowUp으로 owner 확인 작업을 남기세요.",
    ];
  }
  return [
    "executionPlan.owner가 비어 있거나 담당자를 매핑할 수 없습니다.",
    "이슈 생성 전 담당자를 직접 선택하고, 다음 결과에는 정확한 owner와 requiredFollowUp을 포함하세요.",
  ];
}

function reviewOwnerPromptExamples(assignment, owner, project) {
  if (!assignment || !assignment.reviewRequired) return [];
  const assigneeName = assignment.assignee ? memberName(assignment.assignee) : "박주호";
  const ownerText = owner || "unassigned";
  const projectNameText = project && project.name ? project.name : "this review";
  if (assignment.confidence === "medium" && assignment.source === "role-hint") {
    return [
      `executionPlan[0].owner: "${assigneeName}"`,
      `exceptions[0].requiredFollowUp: "Confirm whether role owner '${ownerText}' should map to ${assigneeName} or another active team member before issue creation."`,
    ];
  }
  return [
    `executionPlan[0].owner: "${assigneeName}"`,
    `exceptions[0].requiredFollowUp: "Owner '${ownerText}' is not an exact active member for ${projectNameText}. Confirm the accountable assignee before moving this issue out of review."`,
  ];
}

function reviewOwnerRequiredFollowUpText(result) {
  const decisions = Array.isArray(result && result.decisions) ? result.decisions : [];
  const exceptions = Array.isArray(result && result.exceptions) ? result.exceptions : [];
  return [
    ...decisions.flatMap((decision) => Array.isArray(decision && decision.missingEvidence) ? decision.missingEvidence : []),
    ...exceptions.flatMap((item) => [item && item.message, item && item.requiredFollowUp]),
  ].filter(Boolean).join(" ");
}

function reviewAssigneeFollowUpPanel(draft) {
  const items = Array.isArray(draft && draft.assigneeRequiredFollowUp) ? draft.assigneeRequiredFollowUp : [];
  const examples = Array.isArray(draft && draft.assigneePromptExamples) ? draft.assigneePromptExamples : [];
  return reviewResultViewCall("reviewAssigneeFollowUpPanel", { items, examples });
}

function refreshReviewIssueDraftAssigneeFollowUpPanel(draftNode, draft) {
  if (!draftNode) return;
  const existing = reviewIssueDraftOwnerFollowUpPanel(draftNode);
  if (existing) existing.remove();
  const panelHTML = reviewAssigneeFollowUpPanel(draft);
  if (!panelHTML) return;
  const anchor = reviewIssueDraftAssigneePanel(draftNode);
  if (!anchor) return;
  const tmp = document.createElement("div");
  setHTML(tmp, panelHTML);
  const panel = tmp.firstElementChild;
  if (panel) anchor.insertAdjacentElement("afterend", panel);
}

function reviewAssigneeOptions(selected) {
  return [
    html`<option value="">미지정</option>`,
    ...dashboard.team
      .filter((member) => !member.onLeave)
      .map((member) => html`<option value="${member.id}" ${raw(member.id === selected ? "selected" : "")}>${member.name} (${member.role})</option>`),
  ].join("");
}

function reviewAssigneeConfidenceLabel(confidence) {
  if (confidence === "high") return "확정";
  if (confidence === "medium") return "역할 기반";
  if (confidence === "low") return "낮음";
  if (confidence === "manual") return "수동 확인";
  return "확인 필요";
}

function reviewAssigneeStatusText(draft) {
  if (draft.assigneeOverride) return draft.assignee ? `수동 확인됨: ${memberName(draft.assignee)}` : "수동 미지정: 담당자 확인 필요";
  if (draft.assigneeReviewRequired) return `자동 매핑 확인 필요: ${draft.assignee ? memberName(draft.assignee) : "미지정"}`;
  return `자동 매핑 확정: ${draft.assignee ? memberName(draft.assignee) : "미지정"}`;
}

function reviewIssueDraftAssigneeOverridePanel(draft) {
  return reviewResultViewCall("reviewIssueDraftAssigneeOverridePanel", {
    draft,
    optionsHTML: reviewAssigneeOptions(draft.assignee || ""),
    statusText: reviewAssigneeStatusText(draft),
    confidenceLabel: reviewAssigneeConfidenceLabel(draft.assigneeConfidence),
  });
}

function reviewIssueDraftPanel(options) {
  const data = options || {};
  const draft = data.draft;
  const existing = data.existing || null;
  if (!draft) return "";
  return reviewResultViewCall("reviewIssueDraftPanel", {
    title: data.title || "PM issue draft",
    scopeAttribute: data.scopeAttribute || "",
    createAttribute: data.createAttribute || "",
    draft,
    existing,
    priorityLabel: ISSUE_PRIORITY_MAP[draft.priority] || draft.priority || "-",
    assigneeLabel: draft.assignee ? memberName(draft.assignee) : "미지정",
    checklistLabel: reviewExecutionChecklistCountLabel(draft.executionChecklist),
    executionChecklistCount: issueExecutionChecklistItems({ executionChecklist: draft.executionChecklist }).length,
    assigneeOverridePanel: reviewIssueDraftAssigneeOverridePanel(draft),
    assigneeFollowUpPanel: reviewAssigneeFollowUpPanel(draft),
    artifactDiffPanel: reviewArtifactDiffPanel({
      kind: data.artifactKind || "review-issue",
      key: draft.persistKey,
      staticBody: data.staticBody || "",
      validatedBody: draft.body,
      createdBody: existing ? existing.body : "",
      sourceKind: existing ? existing.sourceKind : "",
      createdId: existing ? existing.id : "",
      artifactType: "issue",
      repairReceiptMarkdown: reviewResultRepairReceiptForKey(draft.persistKey),
    }),
  });
}

function reviewGithubCommentDraftPanel(options) {
  const data = options || {};
  return reviewResultViewCall("reviewGithubCommentDraftPanel", {
    title: "GitHub comment draft",
    scopeAttribute: data.scopeAttribute || "",
    openAttribute: data.openAttribute || "",
    copyAttribute: data.copyAttribute || "",
    statusAttribute: data.statusAttribute || "",
    textAttribute: data.textAttribute || "",
    key: data.key || "",
    target: data.target || "",
    issueUrl: data.issueUrl || "",
    comment: data.comment || "",
  });
}

function reviewIssueDraftCells(draftNode) {
  return reviewResultDraftStateCall("issueDraftCells", draftNode);
}

function reviewIssueDraftBodyNode(draftNode) {
  return reviewResultDraftStateCall("issueDraftBodyNode", draftNode);
}

function reviewIssueDraftNode(handoff) {
  return reviewResultDraftStateCall("issueDraftNode", handoff);
}

function reviewIssueDraftOwnerFollowUpPanel(draftNode) {
  return reviewResultDraftStateCall("issueDraftOwnerFollowUpPanel", draftNode);
}

function reviewIssueDraftAssigneePanel(draftNode) {
  return reviewResultDraftStateCall("issueDraftAssigneePanel", draftNode);
}

function reviewIssueDraftAssigneeSelect(panel) {
  return reviewResultDraftStateCall("issueDraftAssigneeSelect", panel);
}

function reviewIssueDraftAssigneeCopy(panel) {
  return reviewResultDraftStateCall("issueDraftAssigneeCopy", panel);
}

function reviewIssueDraftHead(draftNode) {
  return reviewResultDraftStateCall("issueDraftHead", draftNode);
}

function reviewIssueDraftCreateButton(head) {
  return reviewResultDraftStateCall("issueDraftCreateButton", head);
}

function reviewExecutionDueDate(timeboxHours) {
  return reviewIssuePayloadCall("reviewExecutionDueDate", timeboxHours);
}

function reviewSavedResultTrackerFields(saved, draft) {
  return reviewIssuePayloadCall("reviewSavedResultTrackerFields", saved, draft);
}

function firstPositiveTimeboxHours(plans) {
  return reviewExecutionChecklistCall("firstPositiveTimeboxHours", plans);
}

function reviewDraftWithSavedResult(draft) {
  if (!draft || !draft.persistKey) return draft;
  draft = reviewDraftWithPersistedAssigneeOverride(draft);
  const saved = savedReviewResultByKey(draft.persistKey);
  if (!saved) return { ...draft, resultSource: "static" };
  const result = parseSavedReviewResult(saved);
  const plans = result && Array.isArray(result.executionPlan) ? result.executionPlan : [];
  const timebox = firstPositiveTimeboxHours(plans);
  const tracker = reviewSavedResultTrackerFields(saved, draft);
  const assigneeOverride = !!draft.assigneeOverride;
  const assignee = assigneeOverride ? draft.assignee || "" : tracker.assignee || draft.assignee || "";
  const assigneeConfirmed = assigneeOverride && !!assignee;
  const assignmentLabel = assigneeConfirmed || (!assigneeOverride && !tracker.assigneeReviewRequired) ? "assignee-confirmed" : "assignee-review";
  const assigneeRequiredFollowUp = assigneeConfirmed ? [] : tracker.assigneeRequiredFollowUp;
  const assigneePromptExamples = assigneeConfirmed ? [] : tracker.assigneePromptExamples;
  const labels = uniqueTextItems([
    ...(draft.labels || []).filter((label) => label !== "assignee-review" && label !== "assignee-confirmed" && label !== "owner-followup"),
    ...(saved.labels || []),
    "validated-result",
    tracker.trackerReady ? "tracker-ready" : "tracker-review",
    tracker.executionChecklistReady ? "checklist-ready" : "checklist-review",
    assignmentLabel,
    ...(assigneeRequiredFollowUp.length ? ["owner-followup"] : []),
  ]);
  return {
    ...draft,
    title: saved.issueTitle || draft.title,
    priority: saved.recommendedAction === "defer" ? "med" : saved.confidence === "high" ? "high" : draft.priority,
    estimate: tracker.estimate || timebox || draft.estimate,
    assignee,
    assigneeOverride,
    assigneeConfidence: assigneeOverride ? "manual" : tracker.assigneeConfidence,
    assigneeSource: assigneeOverride ? "manual-override" : tracker.assigneeSource,
    assigneeReason: assigneeOverride ? "User selected the issue assignee before creation." : tracker.assigneeReason,
    assigneeReviewRequired: assigneeConfirmed ? false : assigneeOverride ? true : !!tracker.assigneeReviewRequired,
    assigneeOverrideSavedAt: draft.assigneeOverrideSavedAt || "",
    assigneeRequiredFollowUp,
    assigneePromptExamples,
    assigneeFollowUpReady: assigneeRequiredFollowUp.length > 0 || assigneePromptExamples.length > 0,
    due: tracker.due || draft.due || "",
    executionOwner: tracker.executionOwner,
    executionFirstAction: tracker.executionFirstAction,
    executionDecisionGate: tracker.executionDecisionGate,
    executionFallbackIfBlocked: tracker.executionFallbackIfBlocked,
    executionChecklist: tracker.executionChecklist,
    executionChecklistReady: tracker.executionChecklistReady,
    trackerReady: tracker.trackerReady,
    labels,
    body: reviewSavedResultBody(saved, draft.body, { skipAssigneeFollowUp: assigneeConfirmed }),
    resultSource: "validated",
    savedResultAt: saved.savedAt,
    packageChecksum: saved.packageChecksum || "",
  };
}

function refreshReviewIssueDraftFromSavedResult(validator, saved) {
  const handoff = reviewHandoffNode(validator);
  const draftNode = reviewIssueDraftNode(handoff);
  if (!draftNode || !saved) return;
  const bodyNode = reviewIssueDraftBodyNode(draftNode);
  const baseDraft = {
    title: draftNode.dataset.issueDraftTitle || "",
    projectName: draftNode.dataset.issueDraftProject || "",
    priority: draftNode.dataset.issueDraftPriority || "med",
    labels: draftNode.dataset.issueDraftLabels ? draftNode.dataset.issueDraftLabels.split(",").map((label) => label.trim()).filter(Boolean) : [],
    estimate: clampInteger(draftNode.dataset.issueDraftEstimate, 0, 999, 4),
    assignee: draftNode.dataset.issueDraftAssignee || "",
    assigneeOverride: draftNode.dataset.issueDraftAssigneeOverride === "true",
    assigneeOverrideSavedAt: draftNode.dataset.issueDraftAssigneeOverrideSavedAt || "",
    due: draftNode.dataset.issueDraftDue || "",
    persistKey: draftNode.dataset.issueDraftKey || saved.key,
    body: bodyNode ? bodyNode.textContent || "" : "",
  };
  const draft = reviewDraftWithSavedResult(baseDraft);
  draftNode.dataset.issueDraftTitle = draft.title;
  draftNode.dataset.issueDraftPriority = draft.priority;
  draftNode.dataset.issueDraftLabels = draft.labels.join(",");
  draftNode.dataset.issueDraftEstimate = String(draft.estimate);
  draftNode.dataset.issueDraftAssignee = draft.assignee || "";
  draftNode.dataset.issueDraftAssigneeOverride = draft.assigneeOverride ? "true" : "false";
  draftNode.dataset.issueDraftAssigneeOverrideSavedAt = draft.assigneeOverrideSavedAt || "";
  draftNode.dataset.issueDraftAssigneeConfidence = draft.assigneeConfidence || "none";
  draftNode.dataset.issueDraftAssigneeSource = draft.assigneeSource || "";
  draftNode.dataset.issueDraftAssigneeReview = draft.assigneeReviewRequired ? "true" : "false";
  draftNode.dataset.issueDraftAssigneeRequiredFollowUpCount = String((draft.assigneeRequiredFollowUp || []).length);
  draftNode.dataset.issueDraftAssigneePromptExampleCount = String((draft.assigneePromptExamples || []).length);
  draftNode.dataset.issueDraftOwnerFollowUpReady = draft.assigneeFollowUpReady ? "true" : "false";
  draftNode.dataset.issueDraftDue = draft.due || "";
  draftNode.dataset.issueDraftTrackerReady = draft.trackerReady ? "true" : "false";
  draftNode.dataset.issueDraftExecutionOwner = draft.executionOwner || "";
  draftNode.dataset.issueDraftExecutionChecklistCount = String(issueExecutionChecklistItems({ executionChecklist: draft.executionChecklist }).length);
  draftNode.dataset.issueDraftExecutionChecklistReady = draft.executionChecklistReady ? "true" : "false";
  draftNode.dataset.issueDraftResultSource = draft.resultSource || "static";
  draftNode.dataset.issueDraftSavedResultAt = draft.savedResultAt || "";
  draftNode.dataset.issueDraftPackageChecksum = saved.packageChecksum || "";
  const cells = reviewIssueDraftCells(draftNode);
  if (cells[0]) cells[0].textContent = draft.title;
  if (cells[2]) cells[2].textContent = ISSUE_PRIORITY_MAP[draft.priority] || draft.priority;
  if (cells[3]) cells[3].textContent = draft.assignee ? memberName(draft.assignee) : "미지정";
  if (cells[4]) cells[4].textContent = draft.due || "—";
  if (cells[5]) cells[5].textContent = `${draft.estimate}h`;
  if (cells[6]) cells[6].textContent = reviewExecutionChecklistCountLabel(draft.executionChecklist);
  if (bodyNode) bodyNode.textContent = draft.body;
  const assigneePanel = reviewIssueDraftAssigneePanel(draftNode);
  if (assigneePanel) {
    assigneePanel.dataset.assigneeReviewRequired = draft.assigneeReviewRequired ? "true" : "false";
    assigneePanel.dataset.assigneeConfidence = draft.assigneeConfidence || "none";
    assigneePanel.dataset.assigneeSource = draft.assigneeSource || "";
    const select = reviewIssueDraftAssigneeSelect(assigneePanel);
    const copy = reviewIssueDraftAssigneeCopy(assigneePanel);
    if (select) select.value = draft.assignee || "";
    if (copy) copy.textContent = `${reviewAssigneeStatusText(draft)} · ${reviewAssigneeConfidenceLabel(draft.assigneeConfidence)} · ${draft.assigneeReason || "매핑 근거 없음"}`;
  }
  refreshReviewIssueDraftAssigneeFollowUpPanel(draftNode, draft);
  const head = reviewIssueDraftHead(draftNode);
  if (head && !nodeQuery(head, "[data-issue-draft-validated-source]")) {
    const badge = document.createElement("small");
    badge.className = "portfolio-issue-draft-source";
    badge.setAttribute("data-issue-draft-validated-source", "");
    badge.textContent = "검증 JSON 적용";
    const createButton = reviewIssueDraftCreateButton(head);
    head.insertBefore(badge, createButton || null);
  }
}

function reviewSavedResultNoteBody(handoffText, saved, fallbackIssueBody) {
  const body = reviewSavedResultBody(saved, fallbackIssueBody);
  return reviewResultViewCall("reviewSavedResultNoteBody", { handoffText, saved, body });
}

function reviewArtifactDiffSnippet(text) {
  return reviewArtifactViewCall("reviewArtifactDiffSnippet", text);
}

function reviewArtifactDiffChecks(options) {
  return reviewArtifactViewCall("reviewArtifactDiffChecks", options);
}

function reviewArtifactReceiptMarkdown(options) {
  return reviewArtifactViewCall("reviewArtifactReceiptMarkdown", options);
}

function parseReviewArtifactReceipt(text) {
  return reviewArtifactViewCall("parseReviewArtifactReceipt", text);
}

function reviewArtifactReceiptRepairSuggestion(checkId) {
  return reviewArtifactViewCall("reviewArtifactReceiptRepairSuggestion", checkId);
}

function reviewArtifactReceiptComparison(receipt, current) {
  return reviewArtifactViewCall("reviewArtifactReceiptComparison", receipt, current);
}

function reviewArtifactReceiptCompareOutput(checks) {
  return reviewArtifactViewCall("reviewArtifactReceiptCompareOutput", checks);
}

function reviewArtifactPostApplyReceiptPanel(options) {
  return reviewArtifactViewCall("reviewArtifactPostApplyReceiptPanel", options);
}

function reviewArtifactDiffPanel(options) {
  return reviewArtifactViewCall("reviewArtifactDiffPanel", options);
}

let reviewArtifactStateHelpers = null;
function getReviewArtifactStateHelpers() { return reviewArtifactStateHelpers = createLazyRuntimeHelpers(reviewArtifactStateHelpers, "JooParkReviewArtifactState", { html, nodeText, nodeQuery, setHTML, showToast, openModal, reviewArtifactDiffSnippet, reviewArtifactDiffChecks, parseReviewArtifactReceipt, reviewArtifactReceiptComparison, reviewArtifactReceiptCompareOutput, issueById: (id) => indexes.issueById.get(id), noteById, getRepairUndo: () => state.reviewArtifactRepairUndo, setRepairUndo: (undo) => { state.reviewArtifactRepairUndo = undo; }, nowISO, rebuildIndexes, commit }); }

function reviewArtifactStateCall(name, ...args) {
  return callModuleHelper(getReviewArtifactStateHelpers(), "review artifact state", name, args, "Review artifact state helper missing");
}
function reviewResultValidator(decisions, reviewType) {
  return reviewHandoffCall("reviewResultValidator", decisions, reviewType);
}

function reviewPromptHandoffMarkdown(config) {
  return reviewHandoffCall("reviewPromptHandoffMarkdown", config);
}

function reviewPromptHandoffMarkdownFromDecisions(decisions, config) {
  if (!Array.isArray(decisions) || decisions.length === 0) return "";
  const options = config || {};
  const primary = decisions[0];
  const primarySurface = typeof options.primarySurface === "function"
    ? options.primarySurface(primary, decisions)
    : options.primarySurface || primary.decision.surface;
  return reviewPromptHandoffMarkdown({
    ...options,
    primarySurface,
    decisions,
  });
}

function reviewIssueDraftPanelConfig(title, artifactKind, scopeAttribute = "", createAttribute = "") {
  return { title, scopeAttribute, createAttribute, artifactKind };
}

function candidateReviewIssueDraftPanel(decisions, buildDraft, options) {
  const staticDraft = buildDraft(decisions);
  const draft = reviewDraftWithSavedResult(staticDraft);
  if (!draft) return "";
  const existing = issueBySourceKey(draft.persistKey);
  return reviewIssueDraftPanel({
    ...options,
    staticBody: staticDraft ? staticDraft.body : "",
    draft,
    existing,
  });
}

function candidateReviewGithubCommentPanel(decisions, buildDraft, buildComment, options) {
  if (!Array.isArray(decisions) || decisions.length === 0) return "";
  const primary = decisions[0];
  const draft = buildDraft(decisions);
  const comment = buildComment(decisions);
  if (!primary || !draft || !comment) return "";
  const issueUrl = githubNewIssueUrl(primary.project, draft.title, comment);
  return reviewGithubCommentDraftPanel({
    ...options,
    key: draft.persistKey,
    target: primary.project.name,
    issueUrl,
    comment,
  });
}

function reviewGithubCommentPanelAttributes(scopeAttribute) {
  return {
    scopeAttribute,
    openAttribute: `${scopeAttribute}-open`,
    copyAttribute: `${scopeAttribute}-copy`,
    statusAttribute: `${scopeAttribute}-copy-status`,
    textAttribute: `${scopeAttribute}-text`,
  };
}

function reviewIssueDraftContext(decisions) {
  if (!Array.isArray(decisions) || decisions.length === 0) return null;
  const primary = decisions[0];
  if (!primary || !primary.project || !primary.decision) return null;
  return { primary, secondary: reviewSecondaryDecision(decisions) };
}

function reviewIssueDraftPriority(score) {
  return score >= 86 ? "high" : "med";
}

function reviewIssueDraftBase(primary, labels, estimate) {
  return {
    projectId: primary.project.id,
    projectName: primary.project.name,
    priority: reviewIssueDraftPriority(primary.decision.score),
    status: "todo",
    estimate,
    labels,
    persistKey: primary.decision.persistKey,
  };
}

function reviewIssueDraftFromDecisions(decisions, config) {
  const context = reviewIssueDraftContext(decisions);
  if (!context) return null;
  const { primary, secondary } = context;
  return {
    title: `[${config.titlePrefix}] ${primary.project.name} ${primary.decision.status}`,
    ...reviewIssueDraftBase(primary, config.labels, config.estimate),
    body: reviewIssueBodyLines({
      project: primary.project,
      decision: primary.decision,
      secondary,
      scope: config.scope,
      timeboxHours: config.timeboxHours,
      acceptanceCriteria: config.acceptanceCriteria,
      validationPlan: config.validationPlan,
    }),
  };
}

function workspaceReviewHandoffMarkdown(decisions) {
  return reviewPromptHandoffMarkdownFromDecisions(decisions, {
    title: "JooPark Workspace Review Handoff",
    reviewType: "Workspace adoption review",
    task: "choose the next workspace benchmark or defer when evidence is weak",
    outputFocus: "PM/task transfer, local-first collaboration, and adoption risk",
    successCriteria: [
      "The primary recommendation uses the highest scored candidate without losing the comparison candidate.",
      "Every action item can be converted into a JooPark issue draft with stable labels and persistKey.",
      "Any missing source evidence is explicit instead of hidden in narrative prose.",
    ],
  });
}

function workspaceReviewIssueDraft(decisions) {
  return reviewIssueDraftFromDecisions(decisions, {
    titlePrefix: "Workspace",
    labels: ["workspace", "benchmark", "handoff", "adoption"],
    estimate: 4,
    scope: "Workspace benchmark review",
    timeboxHours: 4,
    acceptanceCriteria: [
      "PM/task transfer, notes/wiki flow, and collaboration/data-control fit are each reviewed against the comparison candidate.",
      "The reviewer records one adoption blocker or explicitly marks missingEvidence as empty.",
      "The final decision can be copied into a JooPark note or issue without rewriting the persist key, labels, score, or source URL.",
    ],
    validationPlan: [
      "Open the source repository and verify the commit/pushedAt from the Evidence Snapshot.",
      "Reopen Portfolio > 벤치 포커스 and confirm the same recommendation and comparison candidate are visible.",
      "Create or update a follow-up issue only after acceptance criteria and missingEvidence are explicit.",
    ],
  });
}

function candidateWorkspaceReviewIssueDraft(decisions) {
  return candidateReviewIssueDraftPanel(decisions, workspaceReviewIssueDraft, reviewIssueDraftPanelConfig("Workspace issue draft", "workspace-issue", "data-workspace-review-issue-draft", "data-workspace-review-issue-create"));
}

function workspaceReviewGithubCommentMarkdown(decisions) {
  return reviewGithubCommentMarkdownFromDraft("JooPark Workspace Review", decisions, workspaceReviewIssueDraft);
}

function candidateWorkspaceReviewGithubComment(decisions) {
  return candidateReviewGithubCommentPanel(decisions, workspaceReviewIssueDraft, workspaceReviewGithubCommentMarkdown, reviewGithubCommentPanelAttributes("data-workspace-review-github-comment"));
}

function knowledgeBaseBenchmarkRecommendationMarkdown(scored) {
  return reviewRecommendationExportCall("knowledgeBaseBenchmarkRecommendationMarkdown", scored);
}

function candidateKnowledgeBaseRecommendationExport(scored) {
  return reviewRecommendationExportCall("candidateKnowledgeBaseRecommendationExport", scored);
}

function projectKnowledgeBaseReviewDecision(project, rank = 0) {
  const rubricScore = projectKnowledgeBaseRubricScore(project);
  if (!project || !rubricScore) return null;
  const focus = projectKnowledgeBaseBenchmark(project);
  const status = reviewStatusFromRubricScore(rubricScore.score, "IA 도입 검토");
  return reviewDecisionRecord(rank, rubricScore, status, {
    surface: focus ? focus.surface : "Knowledge/IA",
    reason: reviewReasonFromAxisOrFocus(projectKnowledgeBaseRubric(project), focus, "KB/IA 검토"),
    persistKey: `kb-ia-review:${project.id}:${rubricScore.score}`,
  });
}

function knowledgeBaseReviewDecisions(scored) {
  return reviewDecisionsFromScored(scored, projectKnowledgeBaseReviewDecision, 3);
}

function candidateKnowledgeBaseReviewHandoff(scored) {
  return reviewPackageHandoffFromDecisions(knowledgeBaseReviewDecisions(scored), {
    config: REVIEW_PACKAGE_HANDOFF_CONFIGS["knowledge-base"],
    markdownForDecisions: knowledgeBaseReviewHandoffMarkdown,
    issueDraftForDecisions: knowledgeBaseReviewIssueDraft,
    githubCommentForDecisions: knowledgeBaseReviewGithubCommentMarkdown,
    issueDraftHTMLForDecisions: candidateKnowledgeBaseReviewIssueDraft,
    githubCommentHTMLForDecisions: candidateKnowledgeBaseReviewGithubComment,
  });
}

function knowledgeBaseReviewHandoffMarkdown(decisions) {
  return reviewPromptHandoffMarkdownFromDecisions(decisions, {
    title: "JooPark Knowledge/IA Review Handoff",
    reviewType: "Knowledge-base information architecture review",
    task: "choose the next knowledge-base benchmark or identify the missing IA evidence",
    outputFocus: "navigation structure, Markdown portability, permissions, and publishing workflow fit",
    successCriteria: [
      "The recommendation explains why the top IA pattern fits JooPark better than the alternatives.",
      "The issue draft can preserve labels, score, source URL, and persistKey without parsing prose.",
      "Any weak source metadata is captured as missingEvidence with a concrete follow-up.",
    ],
  });
}

function knowledgeBaseReviewIssueDraft(decisions) {
  return reviewIssueDraftFromDecisions(decisions, {
    titlePrefix: "KB/IA",
    labels: ["knowledge-base", "ia", "handoff", "adoption"],
    estimate: 3,
    scope: "Knowledge/IA benchmark review",
    timeboxHours: 3,
    acceptanceCriteria: [
      "Navigation structure, Markdown portability, permission model, and publishing workflow fit are each checked.",
      "The reviewer names the IA pattern JooPark should copy and the pattern it should avoid.",
      "The source URL, score, persist key, and comparison candidate survive note, issue, and GitHub comment copy flows.",
    ],
    validationPlan: [
      "Open the source repository and verify the Evidence Snapshot commit/pushedAt.",
      "Compare the top candidate against the portability counterweight before changing the status out of review.",
      "Publish a pinned review note only when missingEvidence is explicit.",
    ],
  });
}

function candidateKnowledgeBaseReviewIssueDraft(decisions) {
  return candidateReviewIssueDraftPanel(decisions, knowledgeBaseReviewIssueDraft, reviewIssueDraftPanelConfig("KB/IA issue draft", "kb-issue", "data-kb-review-issue-draft", "data-kb-review-issue-create"));
}

function knowledgeBaseReviewGithubCommentMarkdown(decisions) {
  return reviewGithubCommentMarkdownFromDraft("JooPark Knowledge/IA Review", decisions, knowledgeBaseReviewIssueDraft);
}

function candidateKnowledgeBaseReviewGithubComment(decisions) {
  return candidateReviewGithubCommentPanel(decisions, knowledgeBaseReviewIssueDraft, knowledgeBaseReviewGithubCommentMarkdown, reviewGithubCommentPanelAttributes("data-kb-review-github-comment"));
}

function candidateBenchmarkRecommendationExport(scored) {
  return reviewRecommendationExportCall("candidateBenchmarkRecommendationExport", scored);
}

function projectBenchmarkReviewDecision(project, rank = 0) {
  const rubricScore = projectBenchmarkRubricScore(project);
  if (!project || !rubricScore) return null;
  const action = projectCandidateAction(project);
  const focus = projectBenchmarkFocus(project);
  const status = reviewStatusFromRubricScore(rubricScore.score, "도입 검토");
  return reviewDecisionRecord(rank, rubricScore, status, {
    actionLabel: action ? action.label : "검토",
    reason: action ? action.reason : focus ? focus.flow : "벤치 대기",
    persistKey: `benchmark-review:${project.id}:${rubricScore.score}`,
  });
}

function compareReviewDecisionItemsByScoreThenRank(a, b) {
  return b.decision.score - a.decision.score || a.decision.rank - b.decision.rank;
}

function candidateBenchmarkReviewQueue(projects, filter) {
  if (filter !== "focused") return "";
  const decisions = limitAndRerankDecisions(
    sortBenchmarkFocusProjects(adoptionCandidateRubricProjects(projects, projectBenchmarkRubric))
      .map((project, index) => ({ project, decision: projectBenchmarkReviewDecision(project, index) }))
      .filter((item) => item.decision)
      .sort(compareReviewDecisionItemsByScoreThenRank),
    3
  );
  if (decisions.length === 0) return "";
  return html`
    <section class="portfolio-benchmark-review" data-benchmark-review-queue>
      <div class="portfolio-review-head">
        <span>리뷰 대기열</span>
        <strong>${decisions.length}개 결정</strong>
      </div>
      <div class="portfolio-review-list">
        ${raw(decisions.map(({ project, decision }) => html`
          <article class="portfolio-review-item" data-benchmark-review-decision="${decision.status}" data-review-project="${project.name}" data-review-score="${decision.score}" data-review-rank="${decision.rank}" data-review-persist-key="${decision.persistKey}">
            <span>${decision.rank}</span>
            <div>
              <strong>${project.name}</strong>
              <small>${decision.status} · ${decision.actionLabel} · ${decision.reason}</small>
            </div>
            <b>${decision.label} ${decision.score}</b>
          </article>
        `).join(""))}
      </div>
      ${raw(candidateBenchmarkReviewQueueHandoff(decisions))}
    </section>
  `;
}

function candidateBenchmarkReviewQueueHandoff(decisions) {
  return reviewPackageHandoffFromDecisions(decisions, {
    config: REVIEW_PACKAGE_HANDOFF_CONFIGS.benchmark,
    markdownForDecisions: candidateBenchmarkReviewQueueMarkdown,
    issueDraftForDecisions: benchmarkReviewIssueDraft,
    githubCommentForDecisions: (items, issueDraft) => genericReviewGithubCommentMarkdown("JooPark PM Benchmark Review", items, issueDraft),
    issueDraftHTMLForDecisions: candidateBenchmarkReviewIssueDraft,
  });
}

function candidateBenchmarkReviewQueueMarkdown(decisions) {
  return reviewPromptHandoffMarkdownFromDecisions(decisions, {
    title: "JooPark Benchmark Review Queue",
    reviewType: "PM benchmark review",
    task: "choose the next PM benchmark experiment and keep the runner-up as a comparison baseline",
    outputFocus: "AI task execution, PM surface fit, source quality, and operational repeatability",
    primarySurface: "JooPark PM benchmark",
    successCriteria: [
      "The top candidate remains traceable through rank, persistKey, score, and labels.",
      "The output separates recommendation JSON from Markdown summary for downstream parsing.",
      "Retries or follow-up research are triggered only through explicit exceptions.",
    ],
  });
}

function benchmarkReviewIssueDraft(decisions) {
  return reviewIssueDraftFromDecisions(decisions, {
    titlePrefix: "Benchmark",
    labels: ["benchmark", "handoff", "adoption"],
    estimate: 4,
    scope: "PM benchmark review",
    timeboxHours: 4,
    acceptanceCriteria: [
      "AI task execution, PM surface fit, source quality, and operational repeatability are each scored or marked missingEvidence.",
      "The runner-up remains in the issue body as the comparison baseline.",
      "A reviewer can accept, compare, watch, or defer the recommendation without reprocessing the portfolio cards.",
    ],
    validationPlan: [
      "Verify the source URL and commit from the Evidence Snapshot before accepting the candidate.",
      "Re-run the portfolio benchmark filter and confirm the same rank, score, and persist key.",
      "Move the issue only after the acceptance criteria are checked or exceptions are listed.",
    ],
  });
}

function candidateBenchmarkReviewIssueDraft(decisions) {
  return candidateReviewIssueDraftPanel(decisions, benchmarkReviewIssueDraft, {
    title: "PM issue draft",
    artifactKind: "benchmark-issue",
  });
}

async function writeClipboardText(text) {
  if (!text) return false;
  if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (err) {
      // Fall through to the legacy textarea path.
    }
  }
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.select();
  let copied = false;
  try {
    copied = document.execCommand("copy");
  } catch (err) {
    copied = false;
  }
  textarea.remove();
  return copied;
}

function setCopyDataset(targets, key, value) {
  targets.forEach((node) => {
    if (node) node.dataset[key] = value;
  });
}

function copyTextWithStatus({ text, datasetKey, targets, status, copiedStatusText, failedStatusText, copiedToast, failedToast }) {
  writeClipboardText(text).then((copied) => {
    const value = copied ? "true" : "false";
    setCopyDataset(targets, datasetKey, value);
    if (status) status.textContent = copied ? copiedStatusText : failedStatusText;
    showToast(copied ? copiedToast : failedToast, copied ? "info" : "error");
  });
}

function copyTextWithLabeledStatus({ statusLabel, copiedToast, ...options }) {
  copyTextWithStatus({
    ...options,
    copiedStatusText: `${statusLabel} 복사됨`,
    failedStatusText: `${statusLabel} 복사 실패`,
    copiedToast,
    failedToast: `${statusLabel} 복사 실패`,
  });
}

function copyPanelReceiptWithStatus({ panel, target, textSelector, statusSelector, datasetKey, extraTargets = [], statusLabel, copiedToast }) {
  if (!panel) return;
  copyTextWithLabeledStatus({
    text: nodeText(panel, textSelector),
    datasetKey,
    targets: [panel, ...extraTargets, target],
    status: nodeQuery(panel, statusSelector),
    statusLabel,
    copiedToast,
  });
}

function nodeQuery(root, selector) {
  return root ? root.querySelector(selector) : null;
}

function nodeText(root, selector) {
  return nodeQuery(root, selector)?.textContent || "";
}

function scrollMainToTop() {
  nodeQuery(document, ".main")?.scrollTo({ top: 0, behavior: "instant" });
}

let reviewResultDraftStateHelpers = null;
function getReviewResultDraftStateHelpers() { return reviewResultDraftStateHelpers = createLazyRuntimeHelpers(reviewResultDraftStateHelpers, "JooParkReviewResultDraftState", { nodeQuery, nodeText, copyTextWithStatus, memberName, reviewAssigneeConfidenceLabel, uniqueTextItems, saveReviewIssueDraftAssigneeOverride, showToast }); }

function reviewResultDraftStateCall(name, ...args) {
  return callModuleHelper(getReviewResultDraftStateHelpers(), "review result draft state", name, args, "Review result draft state helper missing");
}

let reviewCreationActionsHelpers = null;
function getReviewCreationActionsHelpers() { return reviewCreationActionsHelpers = createLazyRuntimeHelpers(reviewCreationActionsHelpers, "JooParkReviewCreationActions", { dashboard, reviewHandoffNode, issueBySourceKey, noteBySourceKey, openIssueInKanban, openNoteInNotesView, reviewIssueDraftNode, projectByName, nodeText, reviewDraftWithSavedResult, issueExecutionChecklistItems, savedReviewResultByKey, reviewSavedResultNoteBody, uid, nowISO, rebuildIndexes, commit, showToast }); }

function reviewCreationActionsCall(name, ...args) {
  return callModuleHelper(getReviewCreationActionsHelpers(), "review creation actions", name, args, "Review creation actions helper missing");
}

let reviewCopyActionsHelpers = null;
function getReviewCopyActionsHelpers() { return reviewCopyActionsHelpers = createLazyRuntimeHelpers(reviewCopyActionsHelpers, "JooParkReviewCopyActions", { writeClipboardText, showToast }); }

function reviewCopyActionsCall(name, ...args) {
  return callModuleHelper(getReviewCopyActionsHelpers(), "review copy actions", name, args, "Review copy actions helper missing");
}

let reviewSubmissionCopyHelpers = null;
function getReviewSubmissionCopyHelpers() { return reviewSubmissionCopyHelpers = createLazyRuntimeHelpers(reviewSubmissionCopyHelpers, "JooParkReviewSubmissionCopy", { writeClipboardText, showToast }); }

function reviewSubmissionCopyCall(name, ...args) {
  return callModuleHelper(getReviewSubmissionCopyHelpers(), "review submission copy", name, args, "Review submission copy helper missing");
}

let operationsCopyActionsHelpers = null;
function getOperationsCopyActionsHelpers() { return operationsCopyActionsHelpers = createLazyRuntimeHelpers(operationsCopyActionsHelpers, "JooParkOperationsCopyActions", { writeClipboardText, showToast }); }

function operationsCopyActionsCall(name, ...args) {
  const helpers = getOperationsCopyActionsHelpers();
  if (helpers) return callModuleHelper(helpers, "operations copy actions", name, args, "Operations copy actions helper missing");
  return ensureOpsRuntime("operations").then(() => (
    callModuleHelper(getOperationsCopyActionsHelpers(), "operations copy actions", name, args, "Operations copy actions helper missing")
  ));
}

const operationsCopySurfaceContracts = Object.freeze({
  workflowUiInstallReceipt: [
    "data-workflow-ui-install-receipt-text",
    "workflowUiInstallReceiptCopied",
    "workflowUiInstallPastePacketCopied",
    "workflowUiInstallPastePacketCoverage",
    "JooPark GitHub UI Workflow Paste Packet",
  ],
  publishEvidenceShareUpdate: [
    "data-publish-evidence-share-update-text",
    "publishEvidenceShareUpdateCopied",
    "publish evidence share update를 복사했습니다",
  ],
  publishLaunchAnnouncement: [
    "data-publish-evidence-launch-announcement-text",
    "publishLaunchAnnouncementCopied",
    "publish launch announcement을 복사했습니다",
  ],
  publishPostLaunchReceipt: [
    "data-publish-evidence-post-launch-receipt-text",
    "publishPostLaunchReceiptCopied",
    "publish post-launch receipt를 복사했습니다",
  ],
  publishLaunchProofReceipt: [
    "data-publish-evidence-launch-proof-receipt-text",
    "publishLaunchProofReceiptCopied",
    "launch proof evidence receipt를 복사했습니다",
  ],
  publishWorkflowScopePacket: [
    "publishDispatchWorkflowScopePacketCopied",
  ],
  postInstallEvidenceIntake: [
    "data-post-install-evidence-intake-text",
    "postInstallEvidenceIntakeCopied",
  ],
  launchReadinessRefreshReceipt: [
    "data-launch-readiness-refresh-receipt-text",
    "launchReadinessRefreshReceiptCopied",
    "launch readiness refresh receipt를 복사했습니다",
  ],
  verifyWorkspaceSummaryReceipt: [
    "data-verify-workspace-summary-receipt-text",
    "verifyWorkspaceSummaryReceiptCopied",
    "verify workspace summary receipt를 복사했습니다",
  ],
  settingsPrivacyHandoff: [
    "data-settings-privacy-handoff",
    "localStorage 키 `joopark.workspace.v3`",
    "토큰, 비밀번호, 세션 ID, API key",
    "private browsing",
    "file://",
  ],
});

function copyBenchmarkReviewHandoff(target) {
  copyReviewPackagePanelText(target, {
    panelSelector: "[data-benchmark-review-handoff], [data-knowledge-base-review-handoff], [data-workspace-review-handoff]",
    textSelector: "[data-review-handoff-text]",
    statusSelector: "[data-review-handoff-copy-status]",
    targetDatasetKey: "reviewHandoffCopied",
    panelDatasetKey: "reviewHandoffCopied",
    successStatus: "복사됨",
    failureStatus: "복사 실패",
    successToast: "handoff를 복사했습니다",
    failureToast: "복사 실패",
  });
}

function copyReviewPackageBundle(target) {
  copyReviewPackagePanelText(target, {
    panelSelector: "[data-benchmark-review-handoff], [data-knowledge-base-review-handoff], [data-workspace-review-handoff]",
    textSelector: "[data-review-package-bundle-text]",
    statusSelector: "[data-review-bundle-copy-status]",
    targetDatasetKey: "reviewBundleCopied",
    panelDatasetKey: "reviewBundleCopied",
    successStatus: "bundle 복사됨",
    failureStatus: "bundle 복사 실패",
    successToast: "review package bundle을 복사했습니다",
    failureToast: "bundle 복사 실패",
  });
}

function copyReviewPackagePasteBody(target) {
  reviewCopyActionsCall("copyReviewPackagePasteBody", target);
}

function copyReviewPackagePanelText(target, options) {
  reviewCopyActionsCall("copyReviewPackagePanelText", target, options);
}

function reviewPackagePanelCopyOptions({ panelSelector, textSelector, statusSelector, datasetKey, successStatus, failureStatus, successToast, failureToast }) {
  return {
    panelSelector,
    textSelector,
    statusSelector,
    targetDatasetKey: datasetKey,
    panelDatasetKey: datasetKey,
    successStatus,
    failureStatus,
    successToast,
    failureToast,
  };
}

function copyReviewPackageTrackerFields(target) {
  copyReviewPackagePanelText(target, reviewPackagePanelCopyOptions({
    panelSelector: "[data-review-package-tracker-fields]",
    textSelector: "[data-review-package-tracker-field-packet-body]",
    statusSelector: "[data-review-package-tracker-field-copy-status]",
    datasetKey: "reviewPackageTrackerFieldCopied",
    successStatus: "필드 복사됨",
    failureStatus: "필드 복사 실패",
    successToast: "tracker field packet을 복사했습니다",
    failureToast: "tracker field packet 복사 실패",
  }));
}

function copyReviewPackageTrackerForm(target) {
  copyReviewPackagePanelText(target, reviewPackagePanelCopyOptions({
    panelSelector: "[data-review-package-tracker-form]",
    textSelector: "[data-review-package-tracker-form-body]",
    statusSelector: "[data-review-package-tracker-form-copy-status]",
    datasetKey: "reviewPackageTrackerFormCopied",
    successStatus: "form packet 복사됨",
    failureStatus: "form packet 복사 실패",
    successToast: "external tracker form packet을 복사했습니다",
    failureToast: "external tracker form packet 복사 실패",
  }));
}

function copyReviewPackageSubmitSequence(target) {
  copyReviewPackagePanelText(target, reviewPackagePanelCopyOptions({
    panelSelector: "[data-review-package-submit-sequence]",
    textSelector: "[data-review-package-submit-sequence-body]",
    statusSelector: "[data-review-package-submit-sequence-copy-status]",
    datasetKey: "reviewPackageSubmitSequenceCopied",
    successStatus: "순서 복사됨",
    failureStatus: "순서 복사 실패",
    successToast: "submit sequence를 복사했습니다",
    failureToast: "submit sequence 복사 실패",
  }));
}

function copyReviewPackageExternalReceiptTemplate(target) {
  copyReviewPackagePanelText(target, reviewPackagePanelCopyOptions({
    panelSelector: "[data-review-package-external-receipt-template]",
    textSelector: "[data-review-package-external-receipt-template-body]",
    statusSelector: "[data-review-package-external-receipt-template-copy-status]",
    datasetKey: "reviewPackageExternalReceiptTemplateCopied",
    successStatus: "receipt 복사됨",
    failureStatus: "receipt 복사 실패",
    successToast: "external issue receipt template을 복사했습니다",
    failureToast: "external receipt template 복사 실패",
  }));
}

function externalReceiptSubmittedAt(value) {
  return reviewSubmissionCopyCall("externalReceiptSubmittedAt", value);
}

function externalReceiptValues(panel) {
  return reviewSubmissionCopyCall("externalReceiptValues", panel);
}

function fillExternalIssueText(template, values) {
  return reviewSubmissionCopyCall("fillExternalIssueText", template, values);
}

function copyReviewPackageFilledText(target, options) {
  reviewSubmissionCopyCall("copyReviewPackageFilledText", target, options);
}

function copyReviewPackageExternalReceiptFilled(target) {
  reviewSubmissionCopyCall("copyReviewPackageExternalReceiptFilled", target);
}

function copyReviewPackageSubmissionUpdateFilled(target) {
  reviewSubmissionCopyCall("copyReviewPackageSubmissionUpdateFilled", target);
}

function copyReviewArtifactReceipt(target) {
  reviewCopyActionsCall("copyReviewArtifactReceipt", target);
}

function copyReviewArtifactRepairPayload(target, kind) {
  reviewCopyActionsCall("copyReviewArtifactRepairPayload", target, kind);
}

function copyIssueFreshReceipt(target) {
  reviewCopyActionsCall("copyIssueFreshReceipt", target);
}

function copyReviewArtifactPostApplyReceipt(target) {
  reviewCopyActionsCall("copyReviewArtifactPostApplyReceipt", target);
}

function copyReviewPostRepairArtifactLink(target) {
  reviewCopyActionsCall("copyReviewPostRepairArtifactLink", target);
}

function reviewArtifactRepairUndoFor(artifactType, createdId) {
  return reviewArtifactStateCall("repairUndoFor", artifactType, createdId);
}

function reviewArtifactRepairPreview(target) {
  return reviewArtifactStateCall("repairPreview", target);
}

function undoReviewArtifactRepair(target) {
  return reviewArtifactStateCall("undoRepair", target);
}

function compareReviewArtifactReceipt(target) {
  return reviewArtifactStateCall("compareReceipt", target);
}

function insertReviewArtifactReceipt(target) {
  return reviewArtifactStateCall("insertReceipt", target);
}

function clearReviewArtifactReceipt(target) {
  return reviewArtifactStateCall("clearReceipt", target);
}

function reviewResultJsonCandidates(text) {
  return reviewHandoffCall("reviewResultJsonCandidates", text);
}

function parseReviewResult(text) {
  return reviewHandoffCall("parseReviewResult", text);
}

function validateReviewResultShape(result, expectedKey) {
  return reviewHandoffCall("validateReviewResultShape", result, expectedKey);
}

let reviewResultStateHelpers = null;
function getReviewResultStateHelpers() { return reviewResultStateHelpers = createLazyRuntimeHelpers(reviewResultStateHelpers, "JooParkReviewResultState", { nodeQuery, nodeText, setHTML, copyTextWithStatus, nowISO, clampText, clampTextArray, normalizeAllData, persist, renderSavedReviewResult, refreshReviewIssueDraftFromSavedResult, repairReceiptMarkdown: (model) => reviewResultViewCall("reviewResultRepairReceiptMarkdown", model), validationOutputHTML: (model) => reviewResultViewCall("reviewResultValidationOutput", model) }); }

function reviewResultStateCall(name, ...args) {
  return callModuleHelper(getReviewResultStateHelpers(), "review result state", name, args, "Review result state helper missing");
}

function attachReviewResultRepairReceipt(validator, saved, result, warnings) {
  return reviewResultStateCall("attachRepairReceipt", validator, saved, result, warnings);
}

function reviewResultValidatorNode(target) {
  return reviewResultStateCall("validatorNode", target);
}

function reviewResultValidatorInput(validator) {
  return reviewResultStateCall("validatorInput", validator);
}

function setReviewResultValidation(target, state, message, details = {}) {
  return reviewResultStateCall("setValidation", target, state, message, details);
}

function validateReviewResult(target) {
  const validator = reviewResultValidatorNode(target);
  const input = reviewResultValidatorInput(validator);
  if (!validator || !input) return;
  const parsed = parseReviewResult(input.value);
  if (parsed.state === "empty") {
    setReviewResultValidation(target, "empty", parsed.error);
    return;
  }
  if (parsed.state === "fail") {
    setReviewResultValidation(target, "fail", "JSON 파싱 실패", { failures: [parsed.error] });
    return;
  }
  const expectedKey = validator.dataset.reviewResultPrimaryKey || "";
  const validation = validateReviewResultShape(parsed.result, expectedKey);
  const pass = validation.failures.length === 0;
  if (pass) {
    const saved = saveValidatedReviewResult(validator, parsed.result, validation.warnings);
    const repairReceipt = attachReviewResultRepairReceipt(validator, saved, parsed.result, validation.warnings);
    setReviewResultValidation(target, "pass", "결과 JSON 검증 통과", {
      result: parsed.result,
      failures: validation.failures,
      warnings: validation.warnings,
      repairReceipt,
    });
    return;
  }
  setReviewResultValidation(target, pass ? "pass" : "fail", pass ? "결과 JSON 검증 통과" : "결과 JSON 검증 실패", {
    result: parsed.result,
    failures: validation.failures,
    warnings: validation.warnings,
  });
}

function insertReviewResultExample(target) {
  const validator = reviewResultValidatorNode(target);
  const input = reviewResultValidatorInput(validator);
  if (!validator || !input) return;
  input.value = target.dataset.reviewResultExample || "";
  input.dispatchEvent(new Event("input", { bubbles: true }));
  validateReviewResult(target);
}

function clearReviewResult(target) {
  const validator = reviewResultValidatorNode(target);
  const input = reviewResultValidatorInput(validator);
  if (!validator || !input) return;
  input.value = "";
  setReviewResultValidation(target, "empty", "결과 JSON 대기");
  input.focus();
}

function copyReviewResultRepair(target) {
  return reviewResultStateCall("copyRepair", target);
}

function copyReviewResultRepairReceipt(target) {
  return reviewResultStateCall("copyRepairReceipt", target);
}

function copyReviewGithubComment(target) {
  return reviewResultDraftStateCall("copyGithubComment", target);
}

function updateReviewIssueDraftAssignee(target) {
  return reviewResultDraftStateCall("updateIssueDraftAssignee", target);
}

function createBenchmarkReviewIssue(target) {
  return reviewCreationActionsCall("createBenchmarkReviewIssue", target);
}

function publishReviewHandoffNote(target) {
  return reviewCreationActionsCall("publishReviewHandoffNote", target);
}

function sortPortfolioProjects(projects) {
  if (state.portfolioFilter !== "candidates") return projects;
  if (state.portfolioBenchmarkFilter === "focused") return sortBenchmarkFocusProjects(projects);
  return [...projects].sort(compareCandidatePriorityThenName);
}

const portfolioViewHelpers = window.JooParkPortfolioView && typeof window.JooParkPortfolioView.create === "function"
  ? window.JooParkPortfolioView.create({
    html,
    raw,
    matches,
    kpiCard,
    searchEmptyState,
    spark,
    healthColor: HEALTH_COLOR,
    statusLabel: STATUS_LABEL,
    portfolioFilters: PORTFOLIO_FILTERS,
    actionFilters: CANDIDATE_ACTION_FILTERS,
    benchmarkFilters: CANDIDATE_BENCHMARK_FILTERS,
    projectSearchText,
    projectCandidateAction,
    projectBenchmarkFocus,
    projectCandidatePriority,
    projectAdoptionMeta,
    projectPromptHandoffButton,
    sortPortfolioProjects,
    sortBenchmarkFocusProjects,
    portfolioMatchesFilter,
    portfolioMatchesActionFilter,
    portfolioMatchesBenchmarkFilter,
    candidateActionQueueSummary,
    candidateBenchmarkQueueSummary,
    candidateBenchmarkRubric,
    candidateWorkspaceRubric,
    candidateKnowledgeBaseRubric,
    candidateBenchmarkReviewQueue,
  })
  : null;

function portfolioViewCall(name, payload) {
  return callModuleHelper(portfolioViewHelpers, "Portfolio view", name, [payload]);
}

function renderPortfolio() {
  const view = refs.views["pm-portfolio"];
  if (!view) return;
  if (!state.portfolioFilter) state.portfolioFilter = "all";
  if (!state.portfolioActionFilter) state.portfolioActionFilter = "all";
  if (!state.portfolioBenchmarkFilter) state.portfolioBenchmarkFilter = "all";
  setHTML(view, portfolioViewCall("renderPortfolioHTML", {
    projects: dashboard.projects,
    query: state.query,
    portfolioFilter: state.portfolioFilter,
    portfolioActionFilter: state.portfolioActionFilter,
    portfolioBenchmarkFilter: state.portfolioBenchmarkFilter,
    showReferenceProjects: referenceProjectsVisible(),
  }));
}

function referenceProjectsVisible() {
  return !!(dashboard.settings && dashboard.settings.showReferenceProjects === true);
}

function setReferenceProjectsVisible(visible) {
  if (!dashboard.settings || typeof dashboard.settings !== "object") dashboard.settings = {};
  dashboard.settings.showReferenceProjects = visible === true;
  if (!dashboard.settings.showReferenceProjects && state.portfolioFilter === "candidates") {
    state.portfolioFilter = "all";
    state.portfolioActionFilter = "all";
    state.portfolioBenchmarkFilter = "all";
  }
  persist();
  if (dashboard.currentView === "pm-portfolio") renderPortfolio();
  if (dashboard.currentView === "settings") renderSettings();
  showToast(dashboard.settings.showReferenceProjects ? "참고 자료를 표시합니다" : "참고 자료를 숨겼습니다", "info");
}

function toggleReferenceProjects() {
  setReferenceProjectsVisible(!referenceProjectsVisible());
}

/* ============================================================
 * View: Kanban
 * ============================================================ */

const kanbanViewHelpers = window.JooParkKanbanView && typeof window.JooParkKanbanView.create === "function"
  ? window.JooParkKanbanView.create({
    html,
    raw,
    matches,
    kpiCard,
    panelHead,
    searchEmptyState,
    memberName,
    projectName,
    formatMonthDay,
    issueExecutionChecklistItems,
    issueExecutionChecklistProgress,
    statusLabels: STATUS_LABEL,
    priorityLabels: PRIORITY_LABEL,
    statusOrder: ["todo", "in-progress", "review", "done"],
    priorityOrder: ["crit", "high", "med", "low"],
  })
  : null;

function kanbanViewCall(name, ...args) {
  return callModuleHelper(kanbanViewHelpers, "Kanban view", name, args);
}

function renderKanban() {
  const view = refs.views["pm-kanban"];
  if (!view) return;
  if (!Array.isArray(dashboard.issues)) dashboard.issues = [];
  const density = dashboard.ui && dashboard.ui.kanbanDensity === "compact" ? "compact" : "comfortable";
  setHTML(view, kanbanViewCall("renderKanbanHTML", {
    issues: dashboard.issues,
    currentProjectId: dashboard.currentProjectId,
    query: state.query,
    filter: state.kanbanFilter,
    sourceFilter: state.kanbanSourceFilter,
    density,
  }));
  setupKanbanDrag();
}

/* ============================================================
 * View: Gantt
 * ============================================================ */

const ganttViewHelpers = window.JooParkGanttView && typeof window.JooParkGanttView.create === "function"
  ? window.JooParkGanttView.create({
    html,
    raw,
    matches,
    kpiCard,
    panelHead,
    searchEmptyState,
    projectName,
    memberName,
    todayISO,
    daysBetween,
    parseDate,
  })
  : null;

function ganttViewCall(name, ...args) {
  return callModuleHelper(ganttViewHelpers, "Gantt view", name, args);
}

function renderGantt() {
  const view = refs.views["pm-gantt"];
  if (!view) return;
  setHTML(view, ganttViewCall("renderGanttHTML", {
    gantt: dashboard.gantt,
    query: state.query,
  }));
}

/* ============================================================
 * View: Team / Resources
 * ============================================================ */

const teamViewHelpers = window.JooParkTeamView && typeof window.JooParkTeamView.create === "function"
  ? window.JooParkTeamView.create({
    html,
    raw,
    matches,
    kpiCard,
    panelHead,
    searchEmptyState,
    projectName,
  })
  : null;

function teamViewCall(name, ...args) {
  return callModuleHelper(teamViewHelpers, "Team view", name, args);
}

function renderTeam() {
  const view = refs.views["pm-team"];
  if (!view) return;
  setHTML(view, teamViewCall("renderTeamHTML", {
    team: dashboard.team,
    projects: dashboard.projects,
    issues: dashboard.issues,
    query: state.query,
  }));
}

/* ============================================================
 * View: DB Instances
 * ============================================================ */

const DB_HEALTH_MAP = { green: "녹색", amber: "주황", red: "적색" };
const DB_HEALTH_ORDER = ["green", "amber", "red"];
const MIG_STATUS_MAP = { pending: "대기", review: "검토", applied: "적용", "rolled-back": "롤백" };
const MIG_STATUS_ORDER = ["pending", "review", "applied", "rolled-back"];

const dbCatalogHelpers = window.JooParkDbCatalog && typeof window.JooParkDbCatalog.create === "function"
  ? window.JooParkDbCatalog.create({
      document,
      dashboard,
      state,
      refs,
      indexes,
      html,
      raw,
      setHTML,
      matches,
      escapeHtml,
      clampInteger,
      clampNumber,
      HEALTH_COLOR,
      panelHead,
      kpiCard,
      spark,
      searchEmptyState,
      currentInstance,
      todayISO,
      parseDate,
      uid,
      nowISO,
      formatLocalDateTime,
      rebuildIndexes,
      commit,
      showToast,
      showUndoToast,
      cloneRecord,
      restoreDeletedArrayItem,
      captureDeletedItem,
      dropDeletedItem,
      canUndoDeletedItem,
      openModal,
      closeModal,
      closeSheet,
      openTableSheet,
    })
  : null;

function dbCatalogCall(name, ...args) {
  return callModuleHelper(dbCatalogHelpers, "db catalog", name, args, "db catalog helper unavailable");
}

const DB_CATALOG_STALE_REVIEW_SOURCE_KEY = "db-catalog:stale-sample-review";
const DB_CATALOG_PROJECT_PATTERN = /데이터|data|db|catalog|카탈로그/i;

function dbCatalogProjectSearchText(project) {
  return `${project.name || ""} ${project.description || ""}`;
}

function isDbCatalogProject(project) {
  return DB_CATALOG_PROJECT_PATTERN.test(dbCatalogProjectSearchText(project));
}

function defaultDbCatalogProject() {
  const projects = Array.isArray(dashboard.projects) ? dashboard.projects : [];
  return projects.find(isDbCatalogProject) || projects[0];
}

function dbCatalogStaleSampleRecords() {
  const records = [];
  const isSample = (record) => {
    const source = record && record.catalogSource;
    return source !== "manual" && source !== "imported";
  };
  const push = (kind, label, record) => {
    if (!record || !isSample(record)) return;
    records.push({ kind, label, id: record.id || "", updatedAt: record.catalogUpdatedAt || record.updatedAt || record.lastRun || record.appliedAt || record.scheduledAt || record.date || "" });
  };
  (Array.isArray(dashboard.dbInstances) ? dashboard.dbInstances : []).forEach((record) => {
    push("instance", record.name || record.id, record);
  });
  (Array.isArray(dashboard.schemas) ? dashboard.schemas : []).forEach((schema) => {
    (schema.databases || []).forEach((db) => {
      (db.tables || []).forEach((table) => {
        push("table", `${schema.instance || schema.name || "db"}/${db.name || "database"}.${table.name || table.id}`, table);
      });
    });
  });
  (Array.isArray(dashboard.queries) ? dashboard.queries : []).forEach((record) => {
    push("query", record.id || record.text || "query", record);
  });
  (Array.isArray(dashboard.backups) ? dashboard.backups : []).forEach((record) => {
    push("backup", `${record.instance || "db"} ${record.date || record.id || ""}`.trim(), record);
  });
  (Array.isArray(dashboard.migrations) ? dashboard.migrations : []).forEach((record) => {
    push("migration", record.id || record.title || "migration", record);
  });
  return records;
}

function dbCatalogStaleReviewBody(records) {
  const counts = records.reduce((acc, record) => {
    acc[record.kind] = (acc[record.kind] || 0) + 1;
    return acc;
  }, {});
  const countLines = sortedStrings(Object.keys(counts)).map((kind) => `- ${kind}: ${counts[kind]}`);
  const sampleLines = records.slice(0, 12).map((record) => `- ${record.kind}: ${record.label}${record.updatedAt ? ` (${record.updatedAt})` : ""}`);
  return [
    "DB Catalog stale sample review",
    "",
    `Source key: ${DB_CATALOG_STALE_REVIEW_SOURCE_KEY}`,
    `Generated: ${formatLocalDateTime(nowISO())}`,
    "Boundary: local catalog only; no live database connection or telemetry collection.",
    "",
    "Counts",
    ...(countLines.length ? countLines : ["- none: 0"]),
    "",
    "Sample records",
    ...(sampleLines.length ? sampleLines : ["- No stale sample records currently detected."]),
    "",
    "Action prompt",
    "- Confirm which shipped sample facts are still useful.",
    "- Replace stale sample metrics with manual local records where needed.",
    "- Keep credentials, tokens, connection strings, and secrets out of the local catalog.",
  ].join("\n");
}

function createDbCatalogStaleReviewIssue() {
  const records = dbCatalogStaleSampleRecords();
  if (!records.length) {
    showToast("stale sample 기록이 없습니다", "info");
    return null;
  }
  const existing = issueBySourceKey(DB_CATALOG_STALE_REVIEW_SOURCE_KEY);
  if (existing) {
    return openIssueInKanban(existing, { toast: `이미 생성된 DB 카탈로그 이슈입니다: ${existing.id}` });
  }
  const project = defaultDbCatalogProject();
  if (!project) {
    showToast("이슈를 만들 프로젝트가 없습니다", "warn");
    return null;
  }
  const issue = {
    id: uid("issue"),
    project: project.id,
    title: `[DB Catalog] stale sample ${records.length}개 검증`,
    status: "todo",
    priority: "high",
    assignee: "",
    labels: ["db-catalog", "freshness", "stale-sample"],
    due: null,
    estimate: 2,
    order: nextKanbanLaneOrder(project.id, "todo"),
    sourceKey: DB_CATALOG_STALE_REVIEW_SOURCE_KEY,
    sourceKind: "db-catalog-stale-review",
    body: dbCatalogStaleReviewBody(records),
    executionOwner: dashboard.settings && dashboard.settings.displayName ? dashboard.settings.displayName : "",
    executionFirstAction: "Open the stale sample filter and choose the first record that should become a manual catalog entry.",
    executionDecisionGate: "Do not treat sample CPU, query, migration, or backup values as live telemetry.",
    executionFallbackIfBlocked: "Leave sample records marked stale and add a pinned note with the manual verification owner.",
    executionChecklist: [
      { id: "db-stale-filter", text: "Review the stale sample filter", done: false },
      { id: "db-manual-entry", text: "Convert at least one stale sample fact into a manual local record", done: false },
      { id: "db-secret-boundary", text: "Confirm no secrets or connection strings were stored", done: false },
    ],
    executionChecklistReady: true,
  };
  dashboard.issues.push(issue);
  dashboard.currentProjectId = project.id;
  rebuildIndexes();
  commit();
  setView("pm-kanban");
  showToast(`DB 카탈로그 검증 이슈를 만들었습니다: ${issue.id}`, "info");
  return issue;
}

/* ============================================================
 * View: Settings
 * ============================================================ */

function renderSettings() {
  const view = refs.views.settings;
  if (!view) return;
  setHTML(view, settingsViewCall("renderSettingsHTML", {
    dashboard,
    storageHealth: state.storageHealth || {},
    handoffs: {
      backup: settingsBackupHandoffText(),
      deploy: settingsDeployHandoffText(),
      privacy: settingsPrivacyHandoffText(),
    },
    workflowUiInstallPlan: state.workflowUiInstallPlan || {},
    launchExecutionPacket: state.launchExecutionPacket || {},
    deletedItemRetentionDays: DELETED_ITEM_RETENTION_DAYS,
    deletedRecoveryFilter: {
      query: state.deletedRecoveryQuery || "",
      kind: state.deletedRecoveryKind || "all",
    },
  }));
  const fileInput = nodeQuery(view, "#importFile");
  if (fileInput) fileInput.addEventListener("change", handleImportFile);
}

let releaseStatusHelpers = null;
function getReleaseStatusHelpers() { return releaseStatusHelpers = createLazyRuntimeHelpers(releaseStatusHelpers, "JooParkReleaseStatus", { html, raw, formatLocalDateTime }); }

function releaseStatusFallback(name) {
  if (name === "publishReadinessItems") return [];
  if (name === "publishReadinessStateLabel") return "대기";
  if (name === "publishReadinessMarkdownLines") return [];
  if (name === "publishRepoPlaceholderGuardLines") return [];
  if (name === "publishDispatchGateGuardLines") return [];
  if (name === "publishUnblockHandoffText") return "";
  if (name === "publishEvidenceFresh") return false;
  if (name.endsWith("HTML")) return "";
  return "";
}

function releaseStatusCall(name, ...args) {
  const helpers = getReleaseStatusHelpers();
  if (!helpers) return releaseStatusFallback(name);
  return callModuleHelper(helpers, "release status", name, args, "release status helper unavailable");
}

function publishReadinessItems() {
  return releaseStatusCall("publishReadinessItems");
}

function publishReadinessStateLabel(state) {
  return releaseStatusCall("publishReadinessStateLabel", state);
}

function publishReadinessMarkdownLines() {
  return releaseStatusCall("publishReadinessMarkdownLines");
}

function publishRepoPlaceholderGuardLines() {
  return releaseStatusCall("publishRepoPlaceholderGuardLines");
}

function publishDispatchGateGuardLines() {
  return releaseStatusCall("publishDispatchGateGuardLines");
}

function publishUnblockHandoffText() {
  return releaseStatusCall("publishUnblockHandoffText");
}

function publishReadinessListHTML(items) {
  return releaseStatusCall("publishReadinessListHTML", items);
}

function workflowUiInstallPlanHTML(source) {
  return releaseStatusCall("workflowUiInstallPlanHTML", source);
}

function publishDispatchPlanHTML(source) {
  return releaseStatusCall("publishDispatchPlanHTML", source);
}

function remoteWorkflowFileCheckHTML(source) {
  return releaseStatusCall("remoteWorkflowFileCheckHTML", source);
}

function launchExecutionPacketHTML(source) {
  return releaseStatusCall("launchExecutionPacketHTML", source);
}

function launchReadinessRefreshHTML(source) {
  return releaseStatusCall("launchReadinessRefreshHTML", source);
}

function verifyWorkspaceSummaryHTML(source) {
  return releaseStatusCall("verifyWorkspaceSummaryHTML", source);
}

function releaseGateCacheHTML(source) {
  return releaseStatusCall("releaseGateCacheHTML", source);
}

function releaseProvenanceHTML(source) {
  return releaseStatusCall("releaseProvenanceHTML", source);
}

function pagesAttestationProofIntakeHTML(input) {
  return releaseStatusCall("pagesAttestationProofIntakeHTML", input);
}

function publishEvidenceFresh(data) {
  return releaseStatusCall("publishEvidenceFresh", data);
}

function publishEvidenceHTML(source) {
  return releaseStatusCall("publishEvidenceHTML", source);
}

function outputQualityAuditHTML(source) {
  return releaseStatusCall("outputQualityAuditHTML", source);
}

const systemStatusViewHelpers = window.JooParkSystemStatusView && typeof window.JooParkSystemStatusView.create === "function"
  ? window.JooParkSystemStatusView.create({
      html,
      raw,
      kpiCard,
      formatBytes,
      storageStatusModel,
      systemStorageHealthHTML,
      safeGithubUrl,
      shortCommit,
      projectBenchmarkContext,
      publishReadinessItems,
      publishUnblockHandoffText,
      publishReadinessListHTML,
      workflowUiInstallPlanHTML,
      publishDispatchPlanHTML,
      remoteWorkflowFileCheckHTML,
      launchExecutionPacketHTML,
      launchReadinessRefreshHTML,
      verifyWorkspaceSummaryHTML,
      releaseGateCacheHTML,
      releaseProvenanceHTML,
      pagesAttestationProofIntakeHTML,
      publishEvidenceHTML,
      outputQualityAuditHTML,
      systemDashboardReceiptHTML,
    })
  : null;

function systemStatusViewCall(name, payload) {
  return callModuleHelper(systemStatusViewHelpers, "system status view", name, [payload], "system status view helper unavailable");
}

function projectSnapshotHealthHTML(health) {
  return systemStatusViewCall("projectSnapshotHealthHTML", health);
}

function renderSystemStatus() {
  const view = refs.views.system;
  if (!view) return;
  setHTML(view, systemStatusViewCall("renderSystemStatusHTML", {
    dashboard,
    state,
    health: state.storageHealth || {},
    pwaRuntime: state.pwaRuntime || {},
    opsRuntime: lazyRuntimeLoader()?.stats() || {},
    routeCount: VIEWS.length,
    alerts: computeAlerts(),
    alertCount: urgentAlertCount(),
    publishItems: publishReadinessItems(),
    publishUnblockHandoff: publishUnblockHandoffText(),
    releaseReadinessSummary: state.releaseReadinessSummary || {},
  }));
}

function isEditingViewField(viewName) {
  const active = document.activeElement;
  const view = refs.views[viewName];
  return !!(active && view && view.contains(active) && ["INPUT", "TEXTAREA", "SELECT"].includes(active.tagName));
}

function refreshReleaseEvidenceViews() {
  if (dashboard.currentView === "system") {
    renderCurrentView();
    return;
  }
  if (dashboard.currentView === "home") {
    if (!isEditingViewField("home")) renderCurrentView();
    return;
  }
  if (dashboard.currentView === "settings") {
    if (!isEditingViewField("settings")) renderSettings();
  }
}

/* ============================================================
 * Sheet / Modal
 * ============================================================ */

function setActionTriggerExpanded(action, expanded) {
  document.querySelectorAll("[data-action][aria-expanded]").forEach((trigger) => {
    if (trigger.dataset.action !== action) return;
    trigger.setAttribute("aria-expanded", expanded ? "true" : "false");
  });
}

function setGlobalHelpTriggerExpanded(expanded) { setActionTriggerExpanded("open-global-help", expanded); }

function setDataSafetyTriggerExpanded(expanded) { setActionTriggerExpanded("open-data-safety-status", expanded); }

function openSheet(title, body, meta, options = {}) {
  const opened = dialogShellCall("openSheet", title, body, meta, options);
  setGlobalHelpTriggerExpanded(opened && options.globalHelpExpanded === true);
  setDataSafetyTriggerExpanded(opened && options.dataSafetyExpanded === true);
  return opened;
}

function closeSheet(options = {}) {
  const closed = dialogShellCall("closeSheet", options);
  setGlobalHelpTriggerExpanded(false);
  setDataSafetyTriggerExpanded(false);
  return closed;
}

function openModal(title, bodyHTML, onConfirm) { return dialogShellCall("openModal", title, bodyHTML, onConfirm); }

function closeModal() { return dialogShellCall("closeModal"); }

function editableModalRecord(arg) { return arg && typeof arg === "object" ? arg : null; }

function formText(data, name) { return (data.get(name) || "").toString().trim(); }

function isSheetOpen() { return dialogShellCall("isSheetOpen"); }

function isModalOpen() { return dialogShellCall("isModalOpen"); }

function getOpenDialogRoot() { return dialogShellCall("getOpenDialogRoot"); }

function trapTab(event, root) { return dialogShellCall("trapTab", event, root); }

/* ============================================================
 * Project picker (enhanced)
 * ============================================================ */

function updateProjectSelectLabel(project = currentProject()) { if (refs.projectSelectLabel) refs.projectSelectLabel.textContent = project ? project.name : ""; }
function pickProject(projectId) {
  const project = indexes.projectById.get(projectId);
  if (!project) return;
  const wasSame = dashboard.currentProjectId === projectId;
  dashboard.currentProjectId = projectId;
  updateProjectSelectLabel(project);
  projectPickerCall("setOpen", false);
  if (refs.projectSelect) refs.projectSelect.focus();
  if (!wasSame) {
    showToast(`프로젝트 '${project.name}'로 전환`, "info");
    renderCurrentView();
  }
}

/* ============================================================
 * Notifications / sheets for open actions
 * ============================================================ */

/* ============================================================
 * Alerts / reminders — computed from real data
 * ============================================================ */

/*
 * computeAlerts() — returns an array of alert objects derived from live data.
 * Urgency order: overdue → today → soon (tomorrow/day-after-tomorrow).
 * Each alert: { kind, icon, title, sub, action, eventId, todoId }
 *
 * alertCount (for bell badge) = overdue + today items only,
 * matching the "need action NOW" philosophy.
 */
function computeAlerts() {
  const today = todayISO();
  const dayAfterTomorrow = addDaysISO(today, 2);
  const alerts = [];

  const openTodos = (Array.isArray(dashboard.todos) ? dashboard.todos : []).filter((t) => !t.done);

  // 1. 기한 지난 할 일 (overdue)
  openTodos.filter((t) => t.due && t.due < today).forEach((t) => {
    alerts.push({
      kind: "overdue",
      icon: "⚑",
      title: `기한 지남: ${t.title}`,
      sub: `마감 ${formatKoreanShort(t.due)}`,
      action: "open-todo",
      todoId: t.id,
    });
  });

  // 2. 오늘 마감 할 일
  openTodos.filter((t) => t.due === today).forEach((t) => {
    alerts.push({
      kind: "today-todo",
      icon: "☑",
      title: `오늘 마감: ${t.title}`,
      sub: "오늘 처리 필요",
      action: "open-todo",
      todoId: t.id,
    });
  });

  // 3. 오늘 일정 (occurrences)
  eventsOn(today).forEach((e) => {
    alerts.push({
      kind: "today-event",
      icon: "◷",
      title: `오늘 일정: ${e.title}`,
      sub: eventTimeLabel(e),
      action: "open-event",
      eventId: e._masterId || e.id,
    });
  });

  // 4. 임박 마감 할 일 (내일~모레)
  const tomorrow = addDaysISO(today, 1);
  openTodos.filter((t) => t.due && t.due >= tomorrow && t.due <= dayAfterTomorrow).forEach((t) => {
    alerts.push({
      kind: "soon-todo",
      icon: "◉",
      title: `임박 마감: ${t.title}`,
      sub: `마감 ${formatKoreanShort(t.due)}`,
      action: "open-todo",
      todoId: t.id,
    });
  });

  // 5. 오늘 미완료 습관
  const habits = Array.isArray(dashboard.habits) ? dashboard.habits : [];
  habits.filter((h) => !h.archived).forEach((h) => {
    const done = h.log && h.log[today];
    if (!done) {
      alerts.push({
        kind: "habit",
        icon: "↺",
        title: `미완료 습관: ${h.name || h.title || "습관"}`,
        sub: "오늘 아직 기록 없음",
        action: null,
        habitId: h.id,
      });
    }
  });

  return alerts;
}

/* Count of "now-urgent" alerts (overdue + today). Used for bell badge. */
function urgentAlertCount() {
  return computeAlerts().filter((a) => a.kind === "overdue" || a.kind === "today-todo" || a.kind === "today-event").length;
}

function openNotificationsSheet() {
  const alerts = computeAlerts();
  let bodyHTML;
  if (alerts.length === 0) {
    bodyHTML = `<p class="agenda-empty notification-empty" role="status" aria-live="polite" data-notification-empty="true">확인할 알림이 없습니다.</p>`;
  } else {
    const rows = alerts.map((a) => {
      const kindCls = {
        overdue: "alert-overdue",
        "today-todo": "alert-today",
        "today-event": "alert-today",
        "soon-todo": "alert-soon",
        habit: "alert-habit",
      }[a.kind] || "";
      const dataAttrs = a.action
        ? (a.todoId
            ? `data-action="${escapeHtml(a.action)}" data-todo-id="${escapeHtml(a.todoId)}"`
            : a.eventId
              ? `data-action="${escapeHtml(a.action)}" data-event-id="${escapeHtml(a.eventId)}"`
              : `data-action="${escapeHtml(a.action)}"`)
        : "";
      const tag = a.action ? "button" : "div";
      const typeAttr = a.action ? `type="button"` : "";
      const labelAttr = a.action ? `aria-label="${escapeHtml(`${a.title} ${a.sub}`)}"` : "";
      return `<${tag} ${typeAttr} class="alert-row ${kindCls}" data-alert-row="true" data-alert-kind="${escapeHtml(a.kind)}" ${labelAttr} ${dataAttrs}>
        <span class="alert-icon">${escapeHtml(a.icon)}</span>
        <span class="alert-body">
          <strong>${escapeHtml(a.title)}</strong>
          <small>${escapeHtml(a.sub)}</small>
        </span>
      </${tag}>`;
    }).join("");

    // Lazy browser-notification permission button (best-effort, never auto-prompts)
    const notifBtn = ("Notification" in window && Notification.permission === "default")
      ? `<button type="button" class="notif-permission-btn" data-action="request-notif-permission">🔔 브라우저 알림 권한 허용</button>`
      : "";

    bodyHTML = `<div class="alert-list" data-alert-list="true">${rows}</div>${notifBtn}`;
  }

  openSheet(`알림 (${alerts.length}건)`, "", null, {
    bodyHTML,
    metaHTML: "",
    notificationExpanded: true,
  });
}

function dataSafetyStatusModel() {
  const health = state.storageHealth || {};
  const localBytes = finiteNumberOr(health.localBytes, storedPayloadBytes());
  const usageBytes = finiteNumberOr(health.usageBytes, localBytes);
  const quotaBytes = positiveFiniteNumberOrNull(health.quotaBytes);
  const usagePct = storagePercent(usageBytes, quotaBytes);
  const modelHealth = { ...health, localBytes, usageBytes, quotaBytes };
  const tone = storageTone(modelHealth);
  const statusLabel = storageStatusLabel(modelHealth);
  const persistedLabel = storagePersistentLabel(modelHealth);
  const lastSavedLabel = dashboard.lastSavedAt ? formatLocalDateTime(dashboard.lastSavedAt) : "아직 저장 전";
  const online = navigator.onLine !== false;
  const ready = tone !== "error" && !modelHealth.lastError;
  return {
    health: modelHealth,
    ready,
    tone,
    statusLabel,
    persistedLabel,
    localBytes,
    usageBytes,
    quotaBytes,
    usagePct,
    lastSavedLabel,
    online,
  };
}

function dataSafetyAccessItems(model = dataSafetyStatusModel()) {
  const usageDetail = model.usagePct === null
    ? "quota 확인 중"
    : `${model.usagePct.toFixed(1)}% of ${formatBytes(model.quotaBytes)}`;
  const deletedCount = Array.isArray(dashboard.deletedItems) ? dashboard.deletedItems.length : 0;
  return [
    {
      key: "saved_state",
      label: "저장 상태",
      value: model.statusLabel,
      detail: `마지막 저장 ${model.lastSavedLabel}`,
      action: "data-safety-refresh",
      status: model.ready ? "ready" : "error",
    },
    {
      key: "storage_health",
      label: "저장소 사용량",
      value: formatBytes(model.localBytes),
      detail: usageDetail,
      action: "data-safety-nav",
      viewName: "system",
      status: model.tone,
    },
    {
      key: "persistent_storage",
      label: "영속 저장",
      value: model.persistedLabel,
      detail: model.health.persisted === true ? "eviction 보호 활성" : "사용자 동작으로 요청 가능",
      action: "request-storage-persistence",
      status: model.health.persisted === true ? "ready" : "guarded",
    },
    {
      key: "backup_recovery",
      label: "백업·복구",
      value: deletedCount > 0 ? `최근 삭제 ${deletedCount}` : "JSON export",
      detail: deletedCount > 0 ? `Settings에서 최근 삭제 ${deletedCount}개 복구 가능` : "Settings에서 내보내기/가져오기",
      action: "data-safety-nav",
      viewName: "settings",
      status: deletedCount > 0 ? "guarded" : "ready",
    },
  ];
}

function updateDataSafetyTopbar() {
  const model = dataSafetyStatusModel();
  const items = dataSafetyAccessItems(model);
  const coverage = items.length === 4 && items.every((item) => item.key && item.label && item.value && item.detail && item.action && item.status) ? 1 : 0;
  const labelText = model.ready ? "저장됨" : model.statusLabel;
  const metaText = model.tone === "error" ? "확인 필요" : formatBytes(model.localBytes);
  document.querySelectorAll("[data-data-safety-trigger]").forEach((trigger) => {
    trigger.dataset.dataSafetyReady = coverage === 1 && model.ready ? "true" : "false";
    trigger.dataset.dataSafetyTone = model.tone;
    trigger.dataset.dataSafetyCoverage = String(coverage);
    trigger.dataset.dataSafetyActionCount = String(items.length);
    trigger.dataset.dataSafetyStatus = model.statusLabel;
    trigger.dataset.dataSafetyLocalBytes = String(model.localBytes);
    trigger.dataset.dataSafetyPersisted = model.health.persisted === true ? "true" : model.health.persisted === false ? "false" : "unknown";
    trigger.dataset.dataSafetyOnline = model.online ? "true" : "false";
    trigger.dataset.dataSafetyLastSaved = dashboard.lastSavedAt || "";
    trigger.setAttribute("aria-label", `로컬 데이터 상태 열기: ${model.statusLabel}, 마지막 저장 ${model.lastSavedLabel}, ${formatBytes(model.localBytes)}`);
    trigger.setAttribute("title", `로컬 데이터 상태 · ${model.statusLabel} · ${formatBytes(model.localBytes)}`);
    const label = nodeQuery(trigger, ".data-status-label");
    const meta = nodeQuery(trigger, "[data-data-safety-topbar-meta]");
    if (label) label.textContent = labelText;
    if (meta) meta.textContent = metaText;
  });
}

function isDataSafetyStatusSheetOpen() { return isSheetOpen() && !!nodeQuery(document, "#sheet [data-topbar-data-safety]"); }

function openDataSafetyStatusSheet() {
  const model = dataSafetyStatusModel();
  const items = dataSafetyAccessItems(model);
  const coverage = items.length === 4 && items.every((item) => item.key && item.label && item.value && item.detail && item.action && item.status) ? 1 : 0;
  const usagePct = model.usagePct === null ? "pending" : model.usagePct.toFixed(1);
  const bodyHTML = html`
    <section class="data-safety" data-topbar-data-safety data-topbar-data-safety-ready="${coverage === 1 && model.ready ? "true" : "false"}" data-topbar-data-safety-coverage="${coverage}" data-topbar-data-safety-action-count="${items.length}" data-topbar-data-safety-status="${model.statusLabel}" data-topbar-data-safety-tone="${model.tone}" data-topbar-data-safety-local-bytes="${model.localBytes}" data-topbar-data-safety-usage-percent="${usagePct}" data-topbar-data-safety-persisted="${model.health.persisted === true ? "true" : model.health.persisted === false ? "false" : "unknown"}" data-topbar-data-safety-online="${model.online ? "true" : "false"}" data-topbar-data-safety-last-saved="${dashboard.lastSavedAt || ""}" data-topbar-data-safety-storage-api="StorageManager.estimate persisted">
      <p class="data-safety-status" role="status" aria-live="polite" aria-atomic="true" data-topbar-data-safety-status-message>
        저장=${model.statusLabel} · 마지막 저장=${model.lastSavedLabel} · local=${formatBytes(model.localBytes)} · persistence=${model.persistedLabel} · online=${model.online ? "true" : "false"}
      </p>
      <div class="data-safety-actions">
        ${items.map((item) => raw(html`
          <button type="button" class="data-safety-action" data-action="${item.action}" data-view="${item.viewName || ""}" data-topbar-data-safety-action data-topbar-data-safety-action-key="${item.key}" data-topbar-data-safety-action-status="${item.status}" data-topbar-data-safety-action-value="${item.value}">
            <span aria-hidden="true">${item.key === "saved_state" ? "✓" : item.key === "storage_health" ? "▦" : item.key === "persistent_storage" ? "⛨" : "⇩"}</span>
            <span>
              <strong>${item.label}</strong>
              <small>${item.value} · ${item.detail}</small>
            </span>
          </button>
        `))}
      </div>
    </section>
  `;
  openSheet("로컬 데이터 상태", "", null, {
    bodyHTML,
    metaHTML: "",
    dataSafetyExpanded: true,
  });
}

function viewLabel(viewName) {
  return VIEW_LABELS[viewName] || "대시보드 홈";
}

function globalHelpAccessItems() {
  const currentView = dashboard.currentView;
  const searchReady = !isSearchInertView(currentView);
  const launchRefresh = state.launchReadinessRefresh && state.launchReadinessRefresh.data ? state.launchReadinessRefresh.data : {};
  const launchExecution = state.launchExecutionPacket && state.launchExecutionPacket.data ? state.launchExecutionPacket.data : {};
  const readyForExternalClaim = launchRefresh.readyForExternalClaim === true && launchExecution.readyForExternalClaim === true;
  const safeToDispatch = launchRefresh.safeToDispatch === true && (launchExecution.safeToDispatch === true || launchExecution.readyToDispatch === true);
  return [
    {
      key: "command_palette",
      label: "검색·이동",
      value: "ready",
      detail: "명령 팔레트",
      action: "global-help-open-palette",
      status: "ready",
    },
    {
      key: "view_recovery",
      label: `${viewLabel(currentView)} 복구`,
      value: searchReady ? "view search" : "command search",
      detail: searchReady ? "현재 뷰 검색" : "요약 화면",
      action: "global-help-search-recovery",
      status: "ready",
    },
    {
      key: "system_status",
      label: "시스템 상태",
      value: safeToDispatch ? "dispatch ready" : "dispatch guarded",
      detail: `safeToDispatch=${safeToDispatch ? "true" : "false"}`,
      action: "global-help-nav",
      viewName: "system",
      status: safeToDispatch ? "ready" : "guarded",
    },
    {
      key: "settings_backup",
      label: "설정·백업",
      value: readyForExternalClaim ? "claim ready" : "claim guarded",
      detail: `readyForExternalClaim=${readyForExternalClaim ? "true" : "false"}`,
      action: "global-help-nav",
      viewName: "settings",
      status: "ready",
    },
  ];
}

function openGlobalHelpSheet() {
  const currentView = dashboard.currentView;
  const items = globalHelpAccessItems();
  const coverage = items.length === 4 && items.every((item) => item.key && item.label && item.value && item.detail && item.action && item.status) ? 1 : 0;
  const launchRefresh = state.launchReadinessRefresh && state.launchReadinessRefresh.data ? state.launchReadinessRefresh.data : {};
  const launchExecution = state.launchExecutionPacket && state.launchExecutionPacket.data ? state.launchExecutionPacket.data : {};
  const safeToDispatch = launchRefresh.safeToDispatch === true && (launchExecution.safeToDispatch === true || launchExecution.readyToDispatch === true);
  const readyForExternalClaim = launchRefresh.readyForExternalClaim === true && launchExecution.readyForExternalClaim === true;
  const searchMode = isSearchInertView(currentView) ? "command" : "view";
  const bodyHTML = html`
    <section class="global-help" data-global-help-access data-global-help-access-ready="${coverage === 1 ? "true" : "false"}" data-global-help-access-coverage="${coverage}" data-global-help-access-action-count="${items.length}" data-global-help-current-view="${currentView}" data-global-help-search-mode="${searchMode}" data-global-help-safe-to-dispatch="${safeToDispatch ? "true" : "false"}" data-global-help-ready-for-external-claim="${readyForExternalClaim ? "true" : "false"}" data-global-help-consistent-help="wcag-3.2.6" data-global-help-status-role="status">
      <p class="global-help-status" role="status" aria-live="polite" aria-atomic="true" data-global-help-status-message>
        ${viewLabel(currentView)} · search=${searchMode} · safeToDispatch=${safeToDispatch ? "true" : "false"} · readyForExternalClaim=${readyForExternalClaim ? "true" : "false"}
      </p>
      <div class="global-help-actions">
        ${items.map((item) => raw(html`
          <button type="button" class="global-help-action" data-action="${item.action}" data-view="${item.viewName || ""}" data-global-help-action data-global-help-action-key="${item.key}" data-global-help-action-status="${item.status}" data-global-help-action-value="${item.value}">
            <span aria-hidden="true">${item.key === "command_palette" ? "⌘" : item.key === "view_recovery" ? "⌕" : item.key === "system_status" ? "◌" : "⚙"}</span>
            <span>
              <strong>${item.label}</strong>
              <small>${item.detail}</small>
            </span>
          </button>
        `))}
      </div>
    </section>
  `;
  openSheet("도움·상태", "", null, {
    bodyHTML,
    metaHTML: "",
    globalHelpExpanded: true,
  });
}

function openProjectSheet(id) {
  const p = indexes.projectById.get(id);
  if (!p) return;
  const myIssues = dashboard.issues.filter((i) => i.project === id);
  openSheet(`프로젝트: ${p.name}`,
    `${p.category ? `${p.category} · ` : ""}${p.owner} · 진행률 ${p.progress}% · 마감 ${p.deadline}`,
    { type: "list", items: [
      { label: "요약", value: p.description || "—" },
      { label: "카테고리", value: p.category || "—" },
      { label: "상태", value: STATUS_LABEL[p.status] || p.status },
      { label: "위험", value: `${p.risks}건` },
      { label: "열린 이슈", value: `${p.openIssues}건` },
      { label: "팀", value: p.members.map(memberName).join(", ") },
      { label: "언어/스택", value: p.language || "—" },
      { label: "최근 이슈", value: myIssues.slice(0, 3).map((i) => `${i.id} ${i.title}`).join(" · ") || "—" },
	    ], actions: [
	      ...(projectPromptHandoffTarget(p) ? [{ label: "↪ prompt handoff 보기", action: "show-project-prompt-handoff", target: id }] : []),
	      { label: `✎ ${p.name} 편집`, action: "project-edit", target: id },
	      { label: `✕ ${p.name} 삭제`, action: "project-delete", target: id },
	    ] });
}

function openIssueSheet(id) {
  const i = indexes.issueById.get(id);
  if (!i) return;
  const body = String(i.body || "").trim();
  const executionChecklist = issueExecutionChecklistItems(i);
  const executionChecklistText = reviewExecutionChecklistLines(executionChecklist).join("\n");
  const executionProgress = issueExecutionChecklistProgress(i);
  const sourceReturnAction = issueSourceReturnAction(i);
  openSheet(`이슈: ${i.id} ${i.title}`,
    `${projectName(i.project)} · ${memberName(i.assignee)} · 마감 ${i.due || "—"}`,
    { type: "list", items: [
      { label: "상태", value: STATUS_LABEL[i.status] || i.status },
      { label: "우선순위", value: PRIORITY_LABEL[i.priority] || i.priority },
      { label: "담당", value: i.assignee ? memberName(i.assignee) : "미지정" },
      ...(i.assigneeConfidence ? [{ label: "assignee confidence", value: i.assigneeConfidence }] : []),
      ...(i.assigneeSource ? [{ label: "assignee source", value: i.assigneeSource }] : []),
      ...(i.assigneeOverride ? [{ label: "assignee override", value: "manual" }] : []),
      ...(Array.isArray(i.assigneeRequiredFollowUp) && i.assigneeRequiredFollowUp.length ? [{ label: "assignee required follow-up", value: i.assigneeRequiredFollowUp.join("\n"), pre: true }] : []),
      ...(Array.isArray(i.assigneePromptExamples) && i.assigneePromptExamples.length ? [{ label: "assignee prompt examples", value: i.assigneePromptExamples.join("\n"), pre: true }] : []),
      { label: "마감", value: i.due || "—" },
      { label: "예상", value: `${i.estimate}시간` },
      { label: "라벨", value: i.labels.join(", ") || "—" },
      { label: "source kind", value: i.sourceKind || "—" },
      { label: "source key", value: i.sourceKey || "—" },
      ...(i.executionOwner ? [{ label: "execution owner", value: i.executionOwner }] : []),
      ...(i.executionFirstAction ? [{ label: "first action", value: i.executionFirstAction }] : []),
      ...(executionChecklist.length ? [
        { label: "execution checklist progress", value: `${executionProgress.label} · ${executionProgress.percent}%` },
        { label: "execution checklist", html: renderIssueExecutionChecklistControls(i) },
        { label: "execution checklist markdown", value: executionChecklistText, pre: true },
        { label: "post-checklist receipt", html: renderIssueFreshReceiptControls(i) },
      ] : []),
      ...(i.executionDecisionGate ? [{ label: "decision gate", value: i.executionDecisionGate, pre: true }] : []),
      ...(i.executionFallbackIfBlocked ? [{ label: "fallback", value: i.executionFallbackIfBlocked, pre: true }] : []),
      ...(body ? [{ label: "본문", value: body, pre: true }] : []),
    ], actions: [
      ...(sourceReturnAction ? [sourceReturnAction] : []),
      { label: `✎ ${i.id} 이슈 편집`, action: "issue-edit", target: id },
      { label: `✕ ${i.id} 이슈 삭제`, action: "issue-delete", target: id },
    ] });
}

function issueSourceReturnAction(issue) {
  const sourceKey = String(issue && issue.sourceKey || "");
  const sourceKind = String(issue && issue.sourceKind || "");
  if (sourceKind === "llm-wiki-action" && sourceKey.startsWith("llm-wiki:issue:")) {
    return { label: "↩ LLM Wiki 원문 열기", action: "open-issue-source", target: issue.id };
  }
  if (sourceKind === "db-catalog-stale-review" || sourceKey === DB_CATALOG_STALE_REVIEW_SOURCE_KEY) {
    return { label: "↩ DB Catalog stale sample 보기", action: "open-issue-source", target: issue.id };
  }
  const reviewSource = reviewIssueSourceLocation(sourceKey);
  if (reviewSource) {
    return { label: `↩ ${reviewSource.label} 보기`, action: "open-issue-source", target: issue.id };
  }
  return null;
}

function issueSourceFilterValue(issue) {
  const sourceKind = String(issue && issue.sourceKind || "");
  const sourceKey = String(issue && issue.sourceKey || "");
  if (sourceKind === "llm-wiki-action") return "wiki";
  if (sourceKind === "db-catalog-stale-review" || sourceKey === DB_CATALOG_STALE_REVIEW_SOURCE_KEY) return "db";
  if (sourceKey.startsWith("workspace-review:")) return "workspace-review";
  if (sourceKey.startsWith("kb-ia-review:")) return "kb-ia-review";
  if (sourceKey.startsWith("benchmark-review:")) return "benchmark-review";
  if (sourceKind === "validated-review-result") return "review";
  return sourceKind || sourceKey ? "source" : "all";
}

function rememberIssueSourceBacklink(issue, surface, sourceLabel, targetKey) {
  if (!issue || !issue.id) return null;
  const link = {
    issueId: issue.id,
    projectId: issue.project || "",
    surface: String(surface || ""),
    sourceLabel: clampText(sourceLabel || "Source", 80, "Source"),
    targetKey: String(targetKey || ""),
    sourceKey: String(issue.sourceKey || ""),
  };
  state.issueSourceBacklink = link;
  return link;
}

function activeIssueSourceBacklink(surface, targetKey = "") {
  const link = state.issueSourceBacklink;
  if (!link || link.surface !== surface) return null;
  if (targetKey && link.targetKey !== targetKey) return null;
  const issue = indexes.issueById.get(link.issueId);
  if (!issue) return null;
  if (link.sourceKey && issue.sourceKey !== link.sourceKey) return null;
  return {
    ...link,
    issueId: issue.id,
    issueTitle: issue.title || issue.id,
    projectId: issue.project || link.projectId || "",
    sourceFilter: issueSourceFilterValue(issue),
  };
}

function openIssueInKanban(issue, options = {}) {
  if (!issue) return null;
  if (issue.project) dashboard.currentProjectId = issue.project;
  setView("pm-kanban");
  if (options.sourceFilter !== false) {
    state.kanbanSourceFilter = issueSourceFilterValue(issue);
    renderKanban();
  }
  if (options.openSheet !== false) openIssueSheet(issue.id);
  if (options.toast) showToast(options.toast, options.tone || "info");
  return issue;
}

function openIssueFromPalette(issue) {
  if (!issue) return null;
  if (issueSourceFilterValue(issue) !== "all") return openIssueInKanban(issue);
  setView("pm-kanban");
  openIssueModal(issue);
  return issue;
}

function openTodoInTodoView(todo, options = {}) {
  if (!todo) return null;
  setView("todo");
  state.todoFilter = "all";
  state.todoSourceFilter = llmWikiRecordSourceMeta(todo, "todo") ? "wiki" : "all";
  renderTodos();
  openTodoModal(todo);
  if (options.toast) showToast(options.toast, options.tone || "info");
  return todo;
}

function openNoteInNotesView(note, options = {}) {
  if (!note) return null;
  setView("notes");
  state.noteSourceFilter = noteSourceFilterValue(note);
  renderNotes();
  openNoteModal(note);
  if (options.toast) showToast(options.toast, options.tone || "info");
  return note;
}

function reviewFamilySourceFilterValue(sourceKey) {
  const key = String(sourceKey || "");
  if (key.startsWith("workspace-review:")) return "workspace-review";
  if (key.startsWith("kb-ia-review:")) return "kb-ia-review";
  if (key.startsWith("benchmark-review:")) return "benchmark-review";
  return "";
}

function noteSourceFilterValue(note) {
  if (llmWikiRecordSourceMeta(note, "note")) return "wiki";
  const meta = reviewRecordSourceMeta(note, "note");
  if (meta) return reviewFamilySourceFilterValue(meta.sourceKey) || "review";
  return "all";
}

function llmWikiRecordLabel(kind) {
  return kind === "note" ? "메모" : "할 일";
}

function recordByLlmWikiBacklinkKind(kind, id) {
  return kind === "note" ? noteById(id) : todoById(id);
}

function rememberLlmWikiRecordBacklink(record, kind, articleId) {
  if (!record || !record.id || !articleId) return null;
  const recordKind = kind === "note" ? "note" : "todo";
  const link = {
    recordKind,
    recordId: record.id,
    recordTitle: clampText(record.title || record.id, 160, record.id),
    recordLabel: llmWikiRecordLabel(recordKind),
    surface: "llm-wiki",
    sourceLabel: "LLM Wiki",
    targetKey: String(articleId || ""),
    sourceKey: String(record.sourceKey || ""),
  };
  state.llmWikiRecordBacklink = link;
  return link;
}

function activeLlmWikiRecordBacklink(articleId = "") {
  const link = state.llmWikiRecordBacklink;
  if (!link || link.surface !== "llm-wiki") return null;
  if (articleId && link.targetKey !== articleId) return null;
  const record = recordByLlmWikiBacklinkKind(link.recordKind, link.recordId);
  if (!record) return null;
  if (link.sourceKey && record.sourceKey !== link.sourceKey) return null;
  return {
    ...link,
    recordId: record.id,
    recordTitle: record.title || link.recordTitle || record.id,
    sourceKey: record.sourceKey || link.sourceKey || "",
  };
}

function openLlmWikiRecordBacklink(kind, recordId) {
  const recordKind = kind === "note" ? "note" : "todo";
  const record = recordByLlmWikiBacklinkKind(recordKind, recordId);
  if (!record) {
    state.llmWikiRecordBacklink = null;
    showToast(`돌아갈 ${llmWikiRecordLabel(recordKind)}을(를) 찾을 수 없습니다`, "warn");
    renderCurrentView();
    return;
  }
  state.llmWikiRecordBacklink = null;
  if (recordKind === "note") {
    openNoteInNotesView(record, { toast: "연결된 메모로 돌아왔습니다" });
  } else {
    openTodoInTodoView(record, { toast: "연결된 할 일로 돌아왔습니다" });
  }
}

function openIssueSourceBacklink(issueId) {
  const issue = indexes.issueById.get(issueId);
  if (!issue) {
    state.issueSourceBacklink = null;
    showToast("돌아갈 Kanban 이슈를 찾을 수 없습니다", "warn");
    renderCurrentView();
    return;
  }
  state.issueSourceBacklink = null;
  openIssueInKanban(issue, { toast: `${issue.id} 이슈로 돌아왔습니다` });
}

function reviewIssueSourceBacklinkSurface(section) {
  return nodeQuery(section, '[data-source-backlink-surface="review"]');
}

function injectReviewIssueSourceBacklink(section, link) {
  if (!section || !link) return;
  const previous = reviewIssueSourceBacklinkSurface(section);
  if (previous) previous.remove();
  const wrapper = document.createElement("section");
  wrapper.className = "source-backlink review-source-backlink";
  wrapper.dataset.sourceBacklink = "true";
  wrapper.dataset.sourceBacklinkSurface = "review";
  wrapper.dataset.sourceBacklinkIssueId = link.issueId;
  wrapper.dataset.sourceBacklinkSource = link.sourceLabel;

  const copy = document.createElement("span");
  const title = document.createElement("strong");
  title.textContent = `${link.sourceLabel}에서 열린 이슈`;
  const detail = document.createElement("small");
  detail.textContent = `${link.issueId} · ${link.issueTitle}`;
  copy.append(title, detail);

  const button = document.createElement("button");
  button.type = "button";
  button.className = "secondary-btn";
  button.dataset.action = "open-source-backlink-issue";
  button.dataset.issueId = link.issueId;
  button.textContent = "Kanban 이슈로 돌아가기";

  wrapper.append(copy, button);
  section.insertBefore(wrapper, section.firstChild);
}

function reviewSourceByPrefix(sources, key) {
  const list = Array.isArray(sources) ? sources : [];
  return list.find((item) => item && key.startsWith(item.prefix)) || null;
}

function reviewIssueSourceLocation(sourceKey) {
  const key = String(sourceKey || "");
  const sources = [
    { prefix: "workspace-review:", label: "Workspace review 패키지", selector: "[data-workspace-review-handoff]" },
    { prefix: "kb-ia-review:", label: "KB/IA review 패키지", selector: "[data-knowledge-base-review-handoff]" },
    { prefix: "benchmark-review:", label: "PM benchmark review 패키지", selector: "[data-benchmark-review-handoff]" },
  ];
  const source = reviewSourceByPrefix(sources, key);
  if (!source) return null;
  const suffix = key.slice(source.prefix.length);
  const splitAt = suffix.lastIndexOf(":");
  const projectId = splitAt > 0 ? suffix.slice(0, splitAt) : suffix;
  return { ...source, key, projectId };
}

function reviewHandoffSectionByKey(selector, key) {
  return Array.from(document.querySelectorAll(selector))
    .find((node) => node.dataset.reviewHandoffPrimaryKey === key) || null;
}

function resetSearchQueryState() { state.query = ""; if (refs.query) refs.query.value = ""; if (refs.searchCount) refs.searchCount.textContent = ""; }

function focusPortfolioCandidateHandoffs() { state.portfolioFilter = "candidates"; state.portfolioActionFilter = "all"; state.portfolioBenchmarkFilter = "focused"; }

function openReviewIssueSource(location) {
  const project = indexes.projectById.get(location.projectId);
  if (!project) {
    showToast("연결된 review 후보를 찾을 수 없습니다", "warn");
    return;
  }
  if (dashboard.currentView !== "pm-portfolio") setView("pm-portfolio");
  resetSearchQueryState();
  focusPortfolioCandidateHandoffs();
  renderPortfolio();
  syncSearchClearControl();
  const section = reviewHandoffSectionByKey(location.selector, location.key);
  if (!section) {
    showToast("연결된 review 패키지를 찾을 수 없습니다", "warn");
    return;
  }
  section.setAttribute("data-review-source-return-revealed", "true");
  injectReviewIssueSourceBacklink(section, activeIssueSourceBacklink("review", location.key));
  section.setAttribute("tabindex", "-1");
  section.scrollIntoView({ behavior: "smooth", block: "start" });
  try {
    section.focus({ preventScroll: true });
  } catch (_) {
    // Ignore focus failures on older WebKit.
  }
  showToast(`${location.label}를 열었습니다`, "info");
}

function openLlmWikiSourceFromRecord(kind, recordId, fallbackSourceKey = "") {
  const recordKind = kind === "note" ? "note" : "todo";
  const record = recordKind === "note" ? noteById(recordId) : todoById(recordId);
  const sourceKey = String(record && record.sourceKey || fallbackSourceKey || "");
  const prefix = `llm-wiki:${recordKind}:`;
  if (!sourceKey.startsWith(prefix)) {
    showToast("연결된 LLM Wiki 원문이 없습니다", "warn");
    return;
  }
  const articleId = sourceKey.slice(prefix.length);
  const location = llmWikiArticleLocation(articleId);
  if (!location) {
    showToast("연결된 LLM Wiki 원문을 찾을 수 없습니다", "warn");
    return;
  }
  if (record) rememberLlmWikiRecordBacklink(record, recordKind, articleId);
  if (isModalOpen()) closeModal();
  setView("llm-wiki");
  selectLlmWiki(location.category.id, location.article.id);
  showToast("LLM Wiki 원문을 열었습니다", "info");
}

function openIssueSource(issueId) {
  const issue = indexes.issueById.get(issueId);
  if (!issue) return;
  const sourceKey = String(issue.sourceKey || "");
  const sourceKind = String(issue.sourceKind || "");
  closeSheet({ restoreFocus: false });
  state.llmWikiRecordBacklink = null;
  if (sourceKind === "llm-wiki-action" && sourceKey.startsWith("llm-wiki:issue:")) {
    const articleId = sourceKey.slice("llm-wiki:issue:".length);
    const location = llmWikiArticleLocation(articleId);
    if (!location) {
      showToast("연결된 LLM Wiki 원문을 찾을 수 없습니다", "warn");
      return;
    }
    rememberIssueSourceBacklink(issue, "llm-wiki", "LLM Wiki", articleId);
    setView("llm-wiki");
    selectLlmWiki(location.category.id, location.article.id);
    showToast("LLM Wiki 원문을 열었습니다", "info");
    return;
  }
  if (sourceKind === "db-catalog-stale-review" || sourceKey === DB_CATALOG_STALE_REVIEW_SOURCE_KEY) {
    rememberIssueSourceBacklink(issue, "db-catalog", "DB Catalog", "stale-sample");
    setView("dbm-instances");
    dbCatalogCall("setDbCatalogFilter", "stale-sample");
    showToast("DB Catalog stale sample queue를 열었습니다", "info");
    return;
  }
  const reviewSource = reviewIssueSourceLocation(sourceKey);
  if (reviewSource) {
    rememberIssueSourceBacklink(issue, "review", reviewSource.label, reviewSource.key);
    openReviewIssueSource(reviewSource);
    return;
  }
  showToast("연결된 원문 이동 경로가 없습니다", "warn");
}

function toggleIssueChecklistItem(issueId, checklistId, options = {}) {
  const issue = indexes.issueById.get(issueId);
  if (!issue) return;
  const items = issueExecutionChecklistItems(issue);
  const index = recordIndexById(items, checklistId);
  if (index < 0) return;
  items[index] = { ...items[index], done: !items[index].done };
  issue.executionChecklist = items;
  issue.executionChecklistReady = items.length > 0;
  issue.body = syncIssueBodyExecutionChecklist(issue);
  const progress = issueExecutionChecklistProgress(issue);
  persist();
  updateNavCounts();
  renderCurrentView();
  if (options.reopenSheet) openIssueSheet(issue.id);
  showToast(`실행 체크리스트 ${progress.label}`, progress.done === progress.total ? "info" : "info");
}

function openTaskSheet(id) {
  const t = taskById(id);
  if (!t) return;
  openSheet(`${t.milestone ? "마일스톤" : "작업"}: ${t.name}`,
    `${projectName(t.project)} · ${t.start} → ${t.end} · 담당 ${memberName(t.owner)}`,
    { type: "list", items: [
      { label: "기간", value: `${daysBetween(t.start, t.end) || 1}일` },
      { label: "의존", value: t.deps.join(", ") || "없음" },
      { label: "유형", value: t.milestone ? "마일스톤" : "작업" },
    ], actions: [
      { label: `✎ ${t.name} 작업 편집`, action: "task-edit", target: id },
      { label: `✕ ${t.name} 작업 삭제`, action: "task-delete", target: id },
    ] });
}

function openMemberSheet(id) {
  const m = indexes.teamById.get(id);
  if (!m) return;
  const myIssues = dashboard.issues.filter((i) => i.assignee === id && i.status !== "done");
  openSheet(`${m.name} · ${m.role}`,
    `부하 ${m.load}% · 프로젝트 ${m.projects.length}개${m.onLeave ? " · 휴가 중" : ""}`,
    { type: "list", items: [
      { label: "참여 프로젝트", value: m.projects.map(projectName).join(", ") || "—" },
      ...myIssues.slice(0, 6).map((i) => ({ label: i.id, value: `${i.title} (${STATUS_LABEL[i.status]})` })),
    ], actions: [
      { label: `✎ ${m.name} 멤버 편집`, action: "member-edit", target: id },
      { label: `✕ ${m.name} 멤버 삭제`, action: "member-delete", target: id },
    ] });
}

function openTableSheet(id) {
  let table = null;
  let instance = null;
  let dbName = null;
  for (const s of dashboard.schemas) {
    for (const db of s.databases) {
      for (const t of db.tables) {
        if (t.id === id) { table = t; instance = s.id; dbName = db.name; }
      }
    }
  }
  if (!table) return;
  state.schemaSelectedTable = id;
  dbCatalogCall("renderDbSchema");
  const inst = indexes.instanceById.get(instance);

  // Build column rows with edit/delete controls
  const colRowsHTML = (table.columns || []).map((c, ci) => html`
    <div class="sheet-col-row">
      <span class="sheet-col-name"><strong>${c.name}</strong> <code>${c.type}</code></span>
      <span class="sheet-col-flags">
        ${c.pk ? raw(html`<span class="col-flag flag-pk">PK</span>`) : ""}
        ${c.nullable === false ? raw(html`<span class="col-flag flag-nn">NN</span>`) : ""}
        ${c.fk ? raw(html`<span class="col-flag flag-fk">FK</span>`) : ""}
      </span>
      <div class="sheet-col-actions">
        <button type="button" class="pm-icon-btn" data-action="column-edit" data-table-id="${id}" data-col-index="${ci}" title="${c.name} 컬럼 편집" aria-label="${c.name} 컬럼 편집">✎</button>
        <button type="button" class="pm-icon-btn pm-icon-btn-del" data-action="column-delete" data-table-id="${id}" data-col-index="${ci}" title="${c.name} 컬럼 삭제" aria-label="${c.name} 컬럼 삭제">✕</button>
      </div>
    </div>
  `).join("");

  const sheetBodyHTML = html`
    <div class="sheet-cols-section">
      <div class="sheet-cols-head">
        <strong>컬럼 (${(table.columns || []).length})</strong>
        <button type="button" class="primary-btn sheet-col-add-btn" data-action="column-add" data-table-id="${id}">+ 컬럼 추가</button>
      </div>
      ${raw(colRowsHTML || html`<small class="empty-line">컬럼 없음</small>`)}
    </div>
    <div class="sheet-meta-section">
      <small><b>인덱스:</b> ${table.indexes.map((i) => i.name).join(", ") || "—"}</small>
      <small><b>외래키:</b> ${table.fks.map((f) => `${f.col}→${f.refs}`).join(", ") || "—"}</small>
    </div>
  `;

  openSheet(`테이블: ${dbName}.${table.name}`, `${inst ? inst.name : instance} · ${(table.rows || 0).toLocaleString()}행 · ${table.sizeMb || 0}MB`, null, {
    metaHTML: html`
    ${raw(sheetBodyHTML)}
    <div class="sheet-actions">
      <button type="button" class="sheet-action" data-action="table-edit" data-table-id="${id}">✎ ${table.name} 테이블 편집</button>
      <button type="button" class="sheet-action sheet-action-del" data-action="table-delete" data-table-id="${id}">✕ ${table.name} 테이블 삭제</button>
    </div>
    `,
  });
}

function openQuerySheet(id) {
  const qi = queryById(id);
  if (!qi) return;
  openSheet(`쿼리: ${qi.id}`,
    `${qi.instance}/${qi.db} · 평균 ${qi.avgMs}ms · p95 ${qi.p95Ms}ms`,
    { type: "paragraphs", items: [
      { label: "SQL", value: qi.text },
      { label: "Plan", value: qi.planHint },
      { label: "최근 실행", value: qi.lastRun },
      { label: "호출 수", value: String(qi.count) },
    ], actions: [
      { label: `✎ ${qi.id} 쿼리 편집`, action: "query-edit", target: id },
      { label: `✕ ${qi.id} 쿼리 삭제`, action: "query-delete", target: id },
    ] });
}

function openBackupSheet(date) {
  const items = dashboard.backups.filter((b) => b.date === date);
  if (items.length === 0) return;
  openSheet(`백업: ${date} (${items.length}건)`,
    items.map((b) => `${b.instance} ${b.status}`).join(" · "),
    { type: "list", items: items.map((b) => ({ label: b.instance, value: `${b.status} · ${b.sizeMb}MB · ${b.durationS}s${b.note ? " · " + b.note : ""}` })) });
}

function openMigrationSheet(id) {
  const m = migrationById(id);
  if (!m) return;
  openSheet(`마이그: ${m.title}`,
    `${m.id} · ${m.instance} · ${m.status}`,
    { type: "list", items: [
      { label: "상태", value: m.status + (m.rolledBack ? " (롤백됨)" : "") },
      { label: "적용", value: m.appliedAt || m.scheduledAt || "—" },
      { label: "작성", value: m.author || "—" },
      { label: "비고", value: m.rollbackReason || "—" },
    ], actions: [
      { label: `✎ ${m.id} 마이그레이션 편집`, action: "migration-edit", target: id },
      { label: `✕ ${m.id} 마이그레이션 삭제`, action: "migration-delete", target: id },
    ] });
}

function pickInstance(id) {
  const inst = indexes.instanceById.get(id);
  if (!inst) return;
  dashboard.currentInstanceId = id;
  if (dashboard.currentView === "dbm-instances") dbCatalogCall("renderDbInstances");
  if (dashboard.currentView === "dbm-schema") {
    state.schemaExpanded.add(id);
    state.schemaSelectedTable = null;
    dbCatalogCall("renderDbSchema");
  }
  showToast(`인스턴스 '${inst.name}' 선택`, "info");
}

function setKanbanFilter(priority) {
  state.kanbanFilter = priority || null;
  renderKanban();
}
function normalizeKanbanSourceFilterValue(filter) {
  return ["all", "wiki", "db", "review", "workspace-review", "kb-ia-review", "benchmark-review", "source"].includes(filter) ? filter : "all";
}
function issueMatchesKanbanSourceFilter(issue, filter) {
  const normalized = normalizeKanbanSourceFilterValue(filter);
  if (normalized === "all") return true;
  const value = issueSourceFilterValue(issue);
  if (normalized === "review") return value === "review" || value === "workspace-review" || value === "kb-ia-review" || value === "benchmark-review";
  return value === normalized;
}
function issueForCurrentProject(issues) {
  const list = Array.isArray(issues) ? issues : [];
  return list.find((issue) => issue && issue.project === dashboard.currentProjectId) || null;
}
function issueForKanbanSourceFilter(filter) {
  const normalized = normalizeKanbanSourceFilterValue(filter);
  if (normalized === "all" || !Array.isArray(dashboard.issues)) return null;
  const matches = dashboard.issues.filter((issue) => issueMatchesKanbanSourceFilter(issue, normalized));
  return issueForCurrentProject(matches)
    || matches[matches.length - 1]
    || null;
}
function setKanbanSourceFilter(filter) {
  state.kanbanSourceFilter = normalizeKanbanSourceFilterValue(filter);
  renderKanban();
}
function openKanbanSourceFilter(filter) {
  const normalized = normalizeKanbanSourceFilterValue(filter);
  const issue = issueForKanbanSourceFilter(normalized);
  if (issue && issue.project) dashboard.currentProjectId = issue.project;
  setView("pm-kanban");
  state.kanbanSourceFilter = normalized;
  renderKanban();
}
function setKanbanDensity(density) {
  ensureDashboardUi({ theme: "dark" }).kanbanDensity = density === "compact" ? "compact" : "comfortable";
  persist();
  renderKanban();
}

function setPortfolioFilter(filter) {
  state.portfolioFilter = PORTFOLIO_FILTERS.some((item) => item.key === filter) ? filter : "all";
  if (state.portfolioFilter !== "candidates") {
    state.portfolioActionFilter = "all";
    state.portfolioBenchmarkFilter = "all";
  }
  renderPortfolio();
}

function setPortfolioActionFilter(filter) {
  state.portfolioActionFilter = CANDIDATE_ACTION_FILTERS.some((item) => item.key === filter) ? filter : "all";
  if (state.portfolioActionFilter !== "all") {
    state.portfolioFilter = "candidates";
    state.portfolioBenchmarkFilter = "all";
  }
  renderPortfolio();
}

function setPortfolioBenchmarkFilter(filter) {
  state.portfolioBenchmarkFilter = CANDIDATE_BENCHMARK_FILTERS.some((item) => item.key === filter) ? filter : "all";
  if (state.portfolioBenchmarkFilter !== "all") {
    state.portfolioFilter = "candidates";
    state.portfolioActionFilter = "all";
  }
  renderPortfolio();
}

function showProjectPromptHandoff(projectId) {
  const project = indexes.projectById.get(projectId);
  const target = projectPromptHandoffTarget(project);
  if (!project || !target) {
    showToast("이 후보에는 prompt handoff가 없습니다", "warn");
    return;
  }
  closeSheet({ restoreFocus: false });
  if (dashboard.currentView !== "pm-portfolio") setView("pm-portfolio");
  resetSearchQueryState();
  focusPortfolioCandidateHandoffs();
  renderPortfolio();
  syncSearchClearControl();
  const section = nodeQuery(document, target.selector);
  if (!section) {
    showToast(`${target.label} handoff를 찾을 수 없습니다`, "warn");
    return;
  }
  section.setAttribute("data-prompt-handoff-revealed", "true");
  section.setAttribute("tabindex", "-1");
  section.scrollIntoView({ behavior: "smooth", block: "start" });
  try {
    section.focus({ preventScroll: true });
  } catch (_) {
    section.focus();
  }
  showToast(`${project.name} ${target.label} handoff로 이동했습니다`, "info");
}

function openNewProjectModal() {
  // 사이드바 "새 프로젝트 등록" 버튼이 이 함수를 호출하므로 새 CRUD 모달로 위임
  openProjectModal(null);
}

/* ============================================================
 * Personal workspace — 일정(Calendar) · 할 일(To-Do) · 메모(Notes)
 * Real CRUD persisted to localStorage. This is the part the user
 * actually manages day to day; the PM/DB views remain as context.
 * ============================================================ */

const STORE_KEY    = "joopark.workspace.v2"; // legacy — kept for migration read
const STORE_KEY_V3 = "joopark.workspace.v3";
const IMPORT_GUARDS = window.JooParkImportGuards;
if (!IMPORT_GUARDS || IMPORT_GUARDS.version !== "joopark-import-guards/v1") {
  throw new Error("JooParkImportGuards runtime is missing or incompatible");
}
const MAX_IMPORT_BYTES = IMPORT_GUARDS.maxImportBytes;
const ADOPTION_IMPORT_ID = "2026-06-04-repo-adoption-candidates";

const backupImportUiHelpers = window.JooParkBackupImportUi && typeof window.JooParkBackupImportUi.create === "function"
  ? window.JooParkBackupImportUi.create({
      html,
      raw,
      dashboard,
      importGuards: IMPORT_GUARDS,
      showToast,
      openModal,
      formatBytes,
      normalizeAllData,
      rebuildIndexes,
      commit,
    })
  : null;

function backupImportUiCall(name, ...args) {
  return callModuleHelper(backupImportUiHelpers, "backup import UI", name, args, "backup import UI helper unavailable");
}

// true once a v3 payload (with PM/DB slices) has been loaded from localStorage;
// prevents the GitHub snapshot from clobbering user-edited project data.
let pmWasPersisted = false;

const workspaceStorageHelpers = window.JooParkWorkspaceStorage && typeof window.JooParkWorkspaceStorage.create === "function"
  ? window.JooParkWorkspaceStorage.create({
      dashboard,
      state,
      storeKey: STORE_KEY,
      storeKeyV3: STORE_KEY_V3,
      nowISO,
      normalizeAllData,
      rebuildIndexes,
      seedPersonalData,
      finiteNumberOr,
      positiveFiniteNumberOrNull,
      showToast,
      getCurrentView: () => dashboard.currentView,
      renderSettings,
      setPmWasPersisted: (value) => { pmWasPersisted = !!value; },
      consoleRef: console,
    })
  : null;

function workspaceStorageCall(name, ...args) {
  return callModuleHelper(workspaceStorageHelpers, "workspace storage", name, args, "workspace storage helper unavailable");
}

const storageStatusViewHelpers = window.JooParkStorageStatusView && typeof window.JooParkStorageStatusView.create === "function"
  ? window.JooParkStorageStatusView.create({
      html,
      raw,
      formatBytes,
      formatLocalDateTime,
      storedPayloadBytes,
      storagePercent,
      storageTone,
      storageStatusLabel,
      storagePersistentLabel,
      panelHead,
      nowISO,
      storeKeyV3: STORE_KEY_V3,
    })
  : null;

function storageStatusViewCall(name, ...args) {
  return callModuleHelper(storageStatusViewHelpers, "storage status view", name, args, "storage status view helper unavailable");
}

function storageStatusModel(health) { return storageStatusViewCall("storageStatusModel", health); }
function settingsStorageHealthHTML(health) { return storageStatusViewCall("settingsStorageHealthHTML", health); }
function systemStorageHealthHTML(health) { return storageStatusViewCall("systemStorageHealthHTML", health); }

const settingsViewHelpers = window.JooParkSettingsView && typeof window.JooParkSettingsView.create === "function"
  ? window.JooParkSettingsView.create({
      html,
      raw,
      kpiCard,
      formatBytes,
      formatLocalDateTime,
      storageStatusModel,
      settingsStorageHealthHTML,
      maxImportBytes: MAX_IMPORT_BYTES,
    })
  : null;

function settingsViewCall(name, payload) {
  return callModuleHelper(settingsViewHelpers, "settings view", name, [payload], "settings view helper unavailable");
}

const EVENT_CATS = {
  work:     { label: "업무", color: "#2387ff" },
  meeting:  { label: "회의", color: "#a970ff" },
  personal: { label: "개인", color: "#17d983" },
  deadline: { label: "마감", color: "#ff4d5e" },
  etc:      { label: "기타", color: "#22d3ee" },
};
const EVENT_CAT_ORDER = ["work", "meeting", "personal", "deadline", "etc"];

const TODO_PRIORITY = {
  high: { label: "높음", color: "var(--red)" },
  med:  { label: "보통", color: "var(--cyan)" },
  low:  { label: "낮음", color: "var(--muted)" },
};
const TODO_PRIO_ORDER = ["high", "med", "low"];
const TODO_PRIO_RANK = { high: 0, med: 1, low: 2 };

const NOTE_COLORS = ["#22d3ee", "#17d983", "#f7a928", "#a970ff", "#ff4d5e", "#2387ff"];
const WEEKDAYS_KO = ["일", "월", "화", "수", "목", "금", "토"];

/* Personal collections live on `dashboard`; default to empty so renderers
 * never see undefined even if persisted data is partial / from an old build. */
if (!Array.isArray(dashboard.events))  dashboard.events  = [];
if (!Array.isArray(dashboard.todos))   dashboard.todos   = [];
if (!Array.isArray(dashboard.notes))   dashboard.notes   = [];
if (!Array.isArray(dashboard.reviewResults)) dashboard.reviewResults = [];
if (!Array.isArray(dashboard.reviewIssueDraftOverrides)) dashboard.reviewIssueDraftOverrides = [];
if (!dashboard.settings)               dashboard.settings = { displayName: "박주호" };
if (!Array.isArray(dashboard.habits))  dashboard.habits  = [];
ensureDashboardUi({ theme: "dark" });
dashboard.lastSavedAt = null;

function ensureDashboardUi(defaults = {}) { if (!dashboard.ui || typeof dashboard.ui !== "object") dashboard.ui = { ...defaults }; return dashboard.ui; }

/* ---------- Local-date helpers (calendar uses the viewer's local day) ---------- */

function uid(prefix) {
  return `${prefix}-${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
}
function nowISO() { return new Date().toISOString(); }
function ymd(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}
function dateFromISO(iso) {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d);
}
function ymToDate(ym) {
  const [y, m] = ym.split("-").map(Number);
  return new Date(y, m - 1, 1);
}
function monthKey(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
}
function addMonthsKey(ym, delta) {
  const d = ymToDate(ym);
  d.setMonth(d.getMonth() + delta);
  return monthKey(d);
}
function addDaysISO(iso, n) {
  const d = dateFromISO(iso);
  d.setDate(d.getDate() + n);
  return ymd(d);
}
function daysBetweenLocal(a, b) {
  return Math.round((dateFromISO(b) - dateFromISO(a)) / 86400000);
}
function isTodayISO(iso) { return iso === todayISO(); }
function formatKoreanFull(iso) {
  const d = dateFromISO(iso);
  return `${d.getFullYear()}년 ${d.getMonth() + 1}월 ${d.getDate()}일 (${WEEKDAYS_KO[d.getDay()]})`;
}
function formatKoreanShort(iso) {
  const d = dateFromISO(iso);
  return `${d.getMonth() + 1}/${d.getDate()} (${WEEKDAYS_KO[d.getDay()]})`;
}
function eventTimeLabel(e) {
  if (e.allDay) return "종일";
  if (!e.start) return "시간 미정";
  return e.end ? `${e.start}–${e.end}` : e.start;
}
function dueLabel(iso) {
  if (!iso) return { text: "기한 없음", cls: "is-none" };
  const today = todayISO();
  if (iso < today) return { text: `지남 ${Math.abs(daysBetweenLocal(today, iso))}일`, cls: "is-overdue" };
  if (iso === today) return { text: "오늘", cls: "is-today" };
  const dd = daysBetweenLocal(today, iso);
  if (dd === 1) return { text: "내일", cls: "is-soon" };
  return { text: `${formatKoreanShort(iso)} · D-${dd}`, cls: dd <= 3 ? "is-soon" : "" };
}
function selectOptions(map, orderKeys, current) {
  return orderKeys.map((k) => html`<option value="${k}" ${raw(k === current ? "selected" : "")}>${map[k].label}</option>`).join("");
}

function modalDeleteButtonHTML({ action, dataAttr, dataValue, label, title = "", ariaLabel = "" }) {
  const attrs = [
    `data-action="${escapeHtml(action)}"`,
    `${dataAttr}="${escapeHtml(dataValue)}"`,
  ];
  if (title) attrs.push(`title="${escapeHtml(title)}"`);
  if (ariaLabel) attrs.push(`aria-label="${escapeHtml(ariaLabel)}"`);
  return `<button type="button" class="modal-delete" ${attrs.join(" ")}>${escapeHtml(label)}</button>`;
}

function noteColorSwatchesHTML(activeColor) {
  const swatches = NOTE_COLORS.map((c) => html`
    <label class="swatch" style="--sw:${raw(c)}">
      <input type="radio" name="color" value="${c}" ${raw(activeColor === c ? "checked" : "")} />
      <span></span>
    </label>
  `).join("");
  return html`<div class="note-swatches" role="radiogroup" aria-label="색상">${raw(swatches)}</div>`;
}

/* ---------- Finders ---------- */

function eventById(id) { return recordById(dashboard.events, id); }
function todoById(id) { return recordById(dashboard.todos, id); }
function noteById(id) { return recordById(dashboard.notes, id); }
function taskById(id) { return recordById(dashboard.gantt.tasks, id); }
function habitById(id) { return recordById(dashboard.habits, id); }
function queryById(id) { return recordById(dashboard.queries, id); }
function migrationById(id) { return recordById(dashboard.migrations, id); }
function ensureDashboardHabits() {
  if (!Array.isArray(dashboard.habits)) dashboard.habits = [];
  return dashboard.habits;
}
function eventIndexById(id) { return recordIndexById(dashboard.events, id); }
function todoIndexById(id) { return recordIndexById(dashboard.todos, id); }
function noteIndexById(id) { return recordIndexById(dashboard.notes, id); }
function habitIndexById(id) { return recordIndexById(dashboard.habits, id); }
function issueIndexById(id) { return recordIndexById(dashboard.issues, id); }
function projectIndexById(id) { return recordIndexById(dashboard.projects, id); }
function memberIndexById(id) { return recordIndexById(dashboard.team, id); }
function taskIndexById(id) { return recordIndexById(dashboard.gantt.tasks, id); }
function compareEventsByDateAllDayStart(a, b) {
  if (a.date !== b.date) return a.date < b.date ? -1 : 1;
  if (a.allDay !== b.allDay) return a.allDay ? -1 : 1;
  return (a.start || "99:99") < (b.start || "99:99") ? -1 : 1;
}
function sortEvents(list) {
  return [...list].sort(compareEventsByDateAllDayStart);
}

/* ---------- Recurrence expansion ---------- */

/*
 * expandOccurrences(rangeStartISO, rangeEndISO)
 * Returns view-model occurrence objects for all master events that overlap
 * [rangeStart, rangeEnd] (inclusive, ISO date strings).
 *
 * Non-repeating events: included if their date is within the range.
 * Repeating events: dates are generated starting from the master's .date,
 *   stepping by day/week/month up to min(rangeEnd, repeatUntil||rangeEnd),
 *   and then filtered to [rangeStart, rangeEnd].
 *   Only dates NOT in master.exceptions[] are yielded.
 *
 * Month-stepping: we build each candidate date from the master's year/month/day
 * incremented by N months, then clamp the day to the last valid day of that
 * month.  e.g. Jan 31 + 1 month → Feb 28 (not skip).  This is consistent and
 * predictable for the typical monthly-recurrence use-case.
 *
 * Safety cap: max 750 iterations per master event to prevent runaway loops.
 *
 * Occurrence objects carry {…masterFields, date: occISO, _masterId, _occ:true}.
 * They are pure view-models — never persisted to dashboard.events.
 */
function expandOccurrences(rangeStartISO, rangeEndISO) {
  const results = [];
  const MAX_STEPS = 750;

  for (const master of dashboard.events) {
    const repeat = master.repeat || "none";
    const exceptions = Array.isArray(master.exceptions) ? master.exceptions : [];

    if (repeat === "none") {
      if (master.date >= rangeStartISO && master.date <= rangeEndISO) {
        results.push({ ...master, _masterId: master.id, _occ: true });
      }
      continue;
    }

    // Determine the upper bound of the series.
    const seriesEnd = master.repeatUntil
      ? (master.repeatUntil < rangeEndISO ? master.repeatUntil : rangeEndISO)
      : rangeEndISO;

    // Walk dates from master.date forward, stepping by the repeat unit.
    let step = 0;
    while (step < MAX_STEPS) {
      let occISO;

      if (repeat === "daily") {
        occISO = addDaysISO(master.date, step);
      } else if (repeat === "weekly") {
        occISO = addDaysISO(master.date, step * 7);
      } else if (repeat === "monthly") {
        // Month-step: extract year/month/day from master.date, add `step` months,
        // then clamp the day to the last valid day of the resulting month.
        const [my, mm, md] = master.date.split("-").map(Number);
        const totalMonths = (my - 1) * 12 + (mm - 1) + step;
        const ny = Math.floor(totalMonths / 12) + 1;
        const nm = (totalMonths % 12) + 1;
        const maxDay = new Date(ny, nm, 0).getDate(); // last day of that month
        const nd = md <= maxDay ? md : maxDay;
        occISO = `${String(ny).padStart(4, "0")}-${String(nm).padStart(2, "0")}-${String(nd).padStart(2, "0")}`;
      } else {
        break; // unknown repeat type — skip
      }

      if (occISO > seriesEnd) break; // past the series/range end

      step++;

      if (occISO < rangeStartISO) continue; // before the range start — keep stepping
      if (exceptions.includes(occISO)) continue; // skipped occurrence

      results.push({ ...master, date: occISO, _masterId: master.id, _occ: true });
    }
  }

  return results;
}

function occurrencesOn(iso) {
  return sortEvents(expandOccurrences(iso, iso));
}

function eventsOn(iso) {
  return occurrencesOn(iso);
}

/* Push a date into master.exceptions and persist. */
function skipOccurrence(masterId, iso) {
  const master = eventById(masterId);
  if (!master) return;
  if (!Array.isArray(master.exceptions)) master.exceptions = [];
  if (!master.exceptions.includes(iso)) {
    master.exceptions.push(iso);
    showToast(`${formatKoreanShort(iso)} 일정을 건너뜁니다`, "info");
    commit();
  }
}

function formatLocalDateTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "—";
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}
function localYmd(iso) {
  const d = new Date(iso);
  return isNaN(d.getTime()) ? todayISO() : ymd(d);
}
function safeNoteColor(c) {
  return NOTE_COLORS.includes(c) ? c : NOTE_COLORS[0];
}
function clampText(value, max, fallback = "") {
  const text = String(value == null ? fallback : value);
  return text.length > max ? text.slice(0, max) : text;
}
function normalizeCatalogSource(value) {
  return ["sample", "manual", "imported"].includes(value) ? value : "sample";
}
function normalizeCatalogUpdatedAt(value, fallback = "") {
  const text = clampText(value || fallback || "", 40);
  return text || "2026-05-29";
}
function clampTextArray(value, maxItems, maxChars) {
  return (Array.isArray(value) ? value : [])
    .map((item) => clampText(item, maxChars).trim())
    .filter(Boolean)
    .slice(0, maxItems);
}
function clampNumberArray(value, maxItems) {
  return (Array.isArray(value) ? value : [])
    .map((item) => Number(item))
    .filter((item) => Number.isFinite(item))
    .slice(0, maxItems);
}

function clampInteger(value, min, max = Number.POSITIVE_INFINITY, fallback = 0) {
  const source = value == null || value === "" ? fallback : value;
  const parsed = parseInt(source, 10);
  const safeParsed = Number.isFinite(parsed) ? parsed : fallback;
  return Math.min(max, Math.max(min, safeParsed));
}

/* Clamp/validate user- or import-supplied data so a hand-edited or malicious
 * backup can neither crash a renderer (missing date) nor break out of an
 * attribute (the only raw()-injected value reachable from import is note color). */
function normalizeAllData() {
  // ---- 개인 데이터 (personal) ----
  dashboard.events = (Array.isArray(dashboard.events) ? dashboard.events : [])
    .filter((e) => e && typeof e === "object" && typeof e.date === "string" && /^\d{4}-\d{2}-\d{2}$/.test(e.date));
  dashboard.events.forEach((e) => {
    if (!EVENT_CATS[e.category]) e.category = "etc";
    e.allDay = !!e.allDay;
    e.title = clampText(e.title, 120);
    e.location = clampText(e.location, 120);
    e.memo = clampText(e.memo, 600);
    // Normalize recurrence fields; default to "none" / null / [] if missing.
    if (!["none", "daily", "weekly", "monthly"].includes(e.repeat)) e.repeat = "none";
    if (e.repeatUntil != null && !/^\d{4}-\d{2}-\d{2}$/.test(e.repeatUntil)) e.repeatUntil = null;
    if (!Array.isArray(e.exceptions)) e.exceptions = [];
  });
  dashboard.todos = (Array.isArray(dashboard.todos) ? dashboard.todos : [])
    .filter((t) => t && typeof t === "object" && t.title != null);
  dashboard.todos.forEach((t) => {
    t.title = clampText(t.title, 160);
    t.category = clampText(t.category, 40);
    t.memo = clampText(t.memo, 600);
    if (!TODO_PRIORITY[t.priority]) t.priority = "med";
    t.done = !!t.done;
    if (t.due != null && !/^\d{4}-\d{2}-\d{2}$/.test(t.due)) t.due = null;
  });
  dashboard.notes = (Array.isArray(dashboard.notes) ? dashboard.notes : [])
    .filter((n) => n && typeof n === "object");
  dashboard.notes.forEach((n) => {
    n.title = clampText(n.title, 120);
    n.body = clampText(n.body, 4000);
    n.color = safeNoteColor(n.color);
    n.pinned = !!n.pinned;
  });
  dashboard.deletedItems = (Array.isArray(dashboard.deletedItems) ? dashboard.deletedItems : [])
    .filter((item) => item && typeof item === "object" && item.id && DELETED_ITEM_KIND_LABELS[item.kind] && item.record && typeof item.record === "object")
    .filter((item) => deletedItemWithinRetention(item))
    .map((item) => ({
      id: clampText(item.id, 80),
      kind: item.kind,
      recordId: clampText(item.recordId || (item.record && item.record.id) || "", 120),
      label: clampText(item.label || deletedItemLabel(item.kind, item.record), 160),
      deletedAt: clampText(item.deletedAt || nowISO(), 40),
      index: nonNegativeIntegerIndex(item.index),
      record: cloneRecord(item.record),
      meta: item.meta && typeof item.meta === "object" && !Array.isArray(item.meta) ? cloneRecord(item.meta) : {},
    }))
    .sort(compareDeletedItemsByDeletedAtDesc)
    .filter(isFirstDeletedItemForRecord)
    .slice(0, DELETED_ITEM_LIMIT);
  dashboard.reviewResults = (Array.isArray(dashboard.reviewResults) ? dashboard.reviewResults : [])
    .filter((item) => item && typeof item === "object" && item.key);
  dashboard.reviewResults.forEach((item) => {
    item.key = clampText(item.key, 180);
    item.schemaVersion = item.schemaVersion === REVIEW_HANDOFF_SCHEMA_VERSION ? REVIEW_HANDOFF_SCHEMA_VERSION : clampText(item.schemaVersion, 80);
    item.reviewType = clampText(item.reviewType, 120);
    item.project = clampText(item.project, 120);
    item.status = clampText(item.status, 80);
    item.score = clampInteger(item.score, 0, 100);
    if (!["adopt", "compare", "watch", "defer"].includes(item.recommendedAction)) item.recommendedAction = "defer";
    if (!["high", "medium", "low"].includes(item.confidence)) item.confidence = "low";
    item.summary = clampText(item.summary, 1200);
    item.issueTitle = clampText(item.issueTitle, 180);
    item.labels = clampTextArray(item.labels, 12, 40);
    item.warnings = clampTextArray(item.warnings, 8, 240);
    item.packageChecksum = clampText(item.packageChecksum, 80);
    item.packageManifestStatus = clampText(item.packageManifestStatus, 40);
    item.packageSourceFreshness = clampText(item.packageSourceFreshness, 40);
    item.packageSourceCount = clampInteger(item.packageSourceCount, 0, 20);
    item.savedAt = isParseableDateTime(item.savedAt) ? item.savedAt : nowISO();
    item.resultJson = clampText(item.resultJson, 20000);
    item.repairReceiptMarkdown = clampText(item.repairReceiptMarkdown || item.postRepairReceipt || "", 16000);
    item.postRepairReceipt = clampText(item.postRepairReceipt || item.repairReceiptMarkdown || "", 16000);
    item.repairReceiptAt = isParseableDateTime(item.repairReceiptAt) ? item.repairReceiptAt : "";
    item.repairReceiptPreviousFailureCount = clampInteger(item.repairReceiptPreviousFailureCount, 0, 20);
    item.repairReceiptPreviousWarningCount = clampInteger(item.repairReceiptPreviousWarningCount, 0, 20);
    item.repairReceiptReady = !!(item.repairReceiptMarkdown && item.repairReceiptAt);
    const repairEvidence = item.repairEvidence && typeof item.repairEvidence === "object" ? item.repairEvidence : {};
    item.repairEvidence = item.repairReceiptReady ? {
      status: clampText(repairEvidence.status || "repaired-validation-pass", 40),
      reviewType: clampText(repairEvidence.reviewType || item.reviewType || "", 120),
      primaryKey: clampText(repairEvidence.primaryKey || item.key || "", 180),
      previousState: clampText(repairEvidence.previousState || "fail", 20),
      previousFailureCount: clampInteger(repairEvidence.previousFailureCount || item.repairReceiptPreviousFailureCount, 0, 20),
      previousWarningCount: clampInteger(repairEvidence.previousWarningCount || item.repairReceiptPreviousWarningCount, 0, 20),
      previousFailures: clampTextArray(repairEvidence.previousFailures, 8, 240),
      previousWarnings: clampTextArray(repairEvidence.previousWarnings, 8, 240),
      repairedAt: isParseableDateTime(repairEvidence.repairedAt) ? repairEvidence.repairedAt : item.repairReceiptAt,
      checksum: clampText(repairEvidence.checksum || item.packageChecksum || "", 80),
    } : {};
  });
  dashboard.reviewIssueDraftOverrides = (Array.isArray(dashboard.reviewIssueDraftOverrides) ? dashboard.reviewIssueDraftOverrides : [])
    .filter((item) => item && typeof item === "object" && item.key)
    .map((item) => ({
      key: clampText(item.key, 180),
      assignee: clampText(item.assignee || "", 80),
      savedAt: isParseableDateTime(item.savedAt) ? item.savedAt : nowISO(),
    }))
    .filter((item, index, list) => recordIndexByKey(list, item.key) === index);

  // ---- 습관 (habits) ----
  dashboard.habits = (Array.isArray(dashboard.habits) ? dashboard.habits : [])
    .filter((h) => h && typeof h === "object" && h.id);
  dashboard.habits.forEach((h) => {
    h.name = clampText(h.name, 60);
    h.emoji = clampText(h.emoji || "OK", 4);
    if (!h.log || typeof h.log !== "object" || Array.isArray(h.log)) h.log = {};
  });

  // ---- PM 슬라이스 ----
  if (!Array.isArray(dashboard.projects))    dashboard.projects    = [];
  if (!Array.isArray(dashboard.issues))      dashboard.issues      = [];
  if (!Array.isArray(dashboard.team))        dashboard.team        = [];
  if (!Array.isArray(dashboard.dbInstances)) dashboard.dbInstances = [];
  if (!Array.isArray(dashboard.schemas))     dashboard.schemas     = [];
  if (!Array.isArray(dashboard.queries))     dashboard.queries     = [];
  if (!Array.isArray(dashboard.backups))     dashboard.backups     = [];
  if (!Array.isArray(dashboard.migrations))  dashboard.migrations  = [];
  if (!dashboard.imports || typeof dashboard.imports !== "object" || Array.isArray(dashboard.imports)) {
    dashboard.imports = {};
  }
  if (!dashboard.imports.projectImports || typeof dashboard.imports.projectImports !== "object" ||
      Array.isArray(dashboard.imports.projectImports)) {
    dashboard.imports.projectImports = {};
  }
  ensureDashboardCollections();

  dashboard.projects = dashboard.projects.filter((p) => p && typeof p === "object" && p.id && p.name);
  dashboard.projects.forEach((p) => {
    if (!Array.isArray(p.members)) p.members = [];
    p.members = clampTextArray(p.members, 20, 80);
    p.burn = clampNumberArray(p.burn, 60);
    if (p.burn.length === 0) p.burn = [0, 0, 0, 0, 0, 0, 0];
    if (!["on-track", "at-risk", "delayed"].includes(p.status)) p.status = "on-track";
    if (!["green", "amber", "red"].includes(p.health)) p.health = "green";
    p.progress = clampInteger(p.progress, 0, 100);
    p.openIssues = clampInteger(p.openIssues, 0);
    p.risks = clampInteger(p.risks, 0);
    p.name = clampText(p.name, 80);
    p.owner = clampText(p.owner || "—", 40);
    p.deadline = /^\d{4}-\d{2}-\d{2}$/.test(p.deadline || "") ? p.deadline : "2099-12-31";
    p.description = clampText(p.description, 500);
    p.category = clampText(p.category, 40);
  });

  dashboard.issues = dashboard.issues.filter((i) => i && typeof i === "object" && i.id && i.title);
  dashboard.issues.forEach((i) => {
    i.id = clampText(i.id, 80);
    i.project = clampText(i.project, 80);
    i.title = clampText(i.title, 120);
    i.assignee = clampText(i.assignee, 80);
    i.labels = clampTextArray(i.labels, 12, 40);
    i.assigneeOverride = !!i.assigneeOverride;
    i.assigneeConfidence = clampText(i.assigneeConfidence || "", 20);
    i.assigneeSource = clampText(i.assigneeSource || "", 60);
    i.assigneeReviewRequired = !!i.assigneeReviewRequired;
    i.assigneeRequiredFollowUp = clampTextArray(i.assigneeRequiredFollowUp, 6, 280);
    i.assigneePromptExamples = clampTextArray(i.assigneePromptExamples, 6, 260);
    i.assigneeFollowUpReady = i.assigneeRequiredFollowUp.length > 0 || i.assigneePromptExamples.length > 0;
    i.executionOwner = clampText(i.executionOwner || "", 80);
    i.executionFirstAction = clampText(i.executionFirstAction || "", 240);
    i.executionDecisionGate = clampText(i.executionDecisionGate || "", 300);
    i.executionFallbackIfBlocked = clampText(i.executionFallbackIfBlocked || "", 300);
    i.executionChecklist = issueExecutionChecklistItems(i)
      .slice(0, 12)
      .map((item, index) => ({
        id: clampText(item.id || `exec-${index + 1}`, 40),
        text: clampText(item.text, 240),
        done: !!item.done,
      }));
    i.executionChecklistReady = i.executionChecklist.length > 0;
    if (!ISSUE_STATUS_LABELS[i.status]) i.status = "todo";
    if (!ISSUE_PRIORITY_MAP[i.priority]) i.priority = "med";
    if (i.due != null && !/^\d{4}-\d{2}-\d{2}$/.test(i.due)) i.due = null;
    i.estimate = clampInteger(i.estimate, 0, 999);
    i.order = finiteNumberOr(i.order, 0);
  });
  normalizeKanbanIssueOrders();

  dashboard.team = dashboard.team.filter((m) => m && typeof m === "object" && m.id && m.name);
  dashboard.team.forEach((m) => {
    m.id = clampText(m.id, 80);
    m.name = clampText(m.name, 40);
    m.role = clampText(m.role, 40);
    m.avatar = clampText(m.avatar || m.name.slice(0, 1), 4);
    m.projects = clampTextArray(m.projects, 20, 80);
    m.load = clampInteger(m.load, 0, 100);
    m.onLeave = !!m.onLeave;
  });

  dashboard.dbInstances = dashboard.dbInstances.filter((d) => d && typeof d === "object" && d.id && d.name);
  dashboard.dbInstances.forEach((d) => {
    d.id = clampText(d.id, 80);
    d.name = clampText(d.name, 80);
    d.engine = clampText(d.engine, 60);
    d.region = clampText(d.region, 40);
    if (!["green", "amber", "red"].includes(d.health)) d.health = "green";
    d.cpu = clampInteger(d.cpu, 0, 100);
    d.mem = clampInteger(d.mem, 0, 100);
    d.conn = clampInteger(d.conn, 0);
    d.connMax = clampInteger(d.connMax, 1);
    d.latencyMs = clampInteger(d.latencyMs, 0);
    d.series = clampNumberArray(d.series, 60);
    d.catalogSource = normalizeCatalogSource(d.catalogSource);
    d.catalogUpdatedAt = normalizeCatalogUpdatedAt(d.catalogUpdatedAt || d.updatedAt, "2026-05-29");
  });

  dashboard.schemas = dashboard.schemas
    .filter((s) => s && typeof s === "object" && s.id)
    .map((s) => ({
      ...s,
      id: clampText(s.id, 80),
      databases: (Array.isArray(s.databases) ? s.databases : []).slice(0, 40).map((db) => ({
        ...db,
        name: clampText(db && db.name, 60),
        tables: (Array.isArray(db && db.tables) ? db.tables : []).slice(0, 200).map((table) => ({
          ...table,
          id: clampText(table && table.id, 80),
          name: clampText(table && table.name, 80),
          rows: clampInteger(table && table.rows, 0),
          sizeMb: clampInteger(table && table.sizeMb, 0),
          catalogSource: normalizeCatalogSource(table && table.catalogSource),
          catalogUpdatedAt: normalizeCatalogUpdatedAt(table && (table.catalogUpdatedAt || table.updatedAt), "2026-05-29"),
          columns: (Array.isArray(table && table.columns) ? table.columns : []).slice(0, 80).map((column) => ({
            ...column,
            name: clampText(column && column.name, 80),
            type: clampText(column && column.type, 60),
            idx: clampTextArray(column && column.idx, 20, 80),
            fk: clampText(column && column.fk, 120),
            pk: !!(column && column.pk),
            nullable: column && column.nullable !== false,
          })),
          indexes: (Array.isArray(table && table.indexes) ? table.indexes : []).slice(0, 40).map((index) => ({
            ...index,
            name: clampText(index && index.name, 80),
            cols: clampTextArray(index && index.cols, 20, 80),
            unique: !!(index && index.unique),
          })),
          fks: clampTextArray(table && table.fks, 40, 120),
        })),
      })),
    }));

  dashboard.queries = dashboard.queries.filter((q) => q && typeof q === "object" && q.id && q.text);
  dashboard.queries.forEach((q) => {
    q.id = clampText(q.id, 80);
    q.instance = clampText(q.instance, 80);
    q.db = clampText(q.db, 60);
    q.text = clampText(q.text, 2000);
    q.planHint = clampText(q.planHint, 200);
    q.avgMs = clampInteger(q.avgMs, 0);
    q.p95Ms = clampInteger(q.p95Ms, 0);
    q.count = clampInteger(q.count, 0);
    q.lastRun = clampText(q.lastRun, 40);
    q.catalogSource = normalizeCatalogSource(q.catalogSource);
    q.catalogUpdatedAt = normalizeCatalogUpdatedAt(q.catalogUpdatedAt || q.lastRun, q.lastRun || "2026-05-29");
  });

  dashboard.backups = dashboard.backups.filter((b) => b && typeof b === "object" && /^\d{4}-\d{2}-\d{2}$/.test(b.date || ""));
  dashboard.backups.forEach((b) => {
    b.instance = clampText(b.instance, 80);
    if (!["ok", "warn", "fail"].includes(b.status)) b.status = "ok";
    b.sizeMb = clampInteger(b.sizeMb, 0);
    b.durationS = clampInteger(b.durationS, 0);
    b.note = clampText(b.note, 200);
    b.catalogSource = normalizeCatalogSource(b.catalogSource);
    b.catalogUpdatedAt = normalizeCatalogUpdatedAt(b.catalogUpdatedAt, b.date || "2026-05-29");
  });

  dashboard.migrations = dashboard.migrations.filter((m) => m && typeof m === "object" && m.id && m.title);
  dashboard.migrations.forEach((m) => {
    m.id = clampText(m.id, 80);
    m.instance = clampText(m.instance, 80);
    m.title = clampText(m.title, 120);
    if (!MIG_STATUS_MAP[m.status]) m.status = "pending";
    m.scheduledAt = clampText(m.scheduledAt, 40);
    m.appliedAt = clampText(m.appliedAt, 40);
    m.catalogSource = normalizeCatalogSource(m.catalogSource);
    m.catalogUpdatedAt = normalizeCatalogUpdatedAt(m.catalogUpdatedAt || m.appliedAt || m.scheduledAt, m.appliedAt || m.scheduledAt || "2026-05-29");
  });

  // gantt: 객체 + tasks 배열 보장
  if (!dashboard.gantt || typeof dashboard.gantt !== "object" || Array.isArray(dashboard.gantt)) {
    dashboard.gantt = { tasks: [] };
  }
  if (!Array.isArray(dashboard.gantt.tasks)) dashboard.gantt.tasks = [];
  if (!/^\d{4}-\d{2}-\d{2}$/.test(dashboard.gantt.rangeStart || "")) dashboard.gantt.rangeStart = todayISO();
  if (!/^\d{4}-\d{2}-\d{2}$/.test(dashboard.gantt.rangeEnd || "") || dashboard.gantt.rangeEnd < dashboard.gantt.rangeStart) {
    dashboard.gantt.rangeEnd = addDaysISO(dashboard.gantt.rangeStart, 60);
  }
  dashboard.gantt.tasks = dashboard.gantt.tasks.filter((t) => t && typeof t === "object" && t.id && t.name);
  dashboard.gantt.tasks.forEach((t) => {
    t.name = clampText(t.name, 80);
    t.owner = clampText(t.owner, 80);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(t.start || "")) t.start = dashboard.gantt.rangeStart;
    if (!/^\d{4}-\d{2}-\d{2}$/.test(t.end || "") || t.end < t.start) t.end = t.start;
    t.deps = clampTextArray(t.deps, 20, 80);
    t.milestone = !!t.milestone;
    if (!["blue", "cyan", "green", "amber", "red", "violet"].includes(t.color)) t.color = "blue";
  });
  dashboard.currentProjectId = dashboard.projects.some((p) => p.id === dashboard.currentProjectId)
    ? dashboard.currentProjectId
    : (dashboard.projects[0] ? dashboard.projects[0].id : "");
  dashboard.currentInstanceId = dashboard.dbInstances.some((d) => d.id === dashboard.currentInstanceId)
    ? dashboard.currentInstanceId
    : (dashboard.dbInstances[0] ? dashboard.dbInstances[0].id : "");

  // ---- UI 슬라이스 ----
  const ui = ensureDashboardUi({ theme: "dark" });
  if (typeof ui.theme !== "string") ui.theme = "dark";
  if (!["comfortable", "compact"].includes(ui.kanbanDensity)) ui.kanbanDensity = "comfortable";
}
// 하위 호환 별칭 (기존 호출부에서 normalizePersonalData()를 참조하는 곳이 있을 경우 대비)
function normalizePersonalData() { normalizeAllData(); }

/* ---------- Persistence ---------- */

function storedPayloadBytes() { return workspaceStorageCall("storedPayloadBytes"); }
function formatBytes(bytes) { return workspaceStorageCall("formatBytes", bytes); }
function storagePercent(usageBytes, quotaBytes) { return workspaceStorageCall("storagePercent", usageBytes, quotaBytes); }
function storageTone(health) { return workspaceStorageCall("storageTone", health); }
function storageStatusLabel(health) { return workspaceStorageCall("storageStatusLabel", health); }
function storagePersistentLabel(health) { return workspaceStorageCall("storagePersistentLabel", health); }
function refreshStorageHealth(options = {}) {
  const result = workspaceStorageCall("refreshStorageHealth", options);
  if (result && typeof result.then === "function") {
    return result.then((health) => {
      updateDataSafetyTopbar();
      return health;
    });
  }
  updateDataSafetyTopbar();
  return result;
}
function requestStoragePersistence() {
  const result = workspaceStorageCall("requestStoragePersistence");
  if (result && typeof result.then === "function") {
    return result.then((value) => {
      updateDataSafetyTopbar();
      return value;
    });
  }
  updateDataSafetyTopbar();
  return result;
}
function persist() {
  const result = workspaceStorageCall("persist");
  updateDataSafetyTopbar();
  return result;
}
function loadPersisted() {
  const result = workspaceStorageCall("loadPersisted");
  updateDataSafetyTopbar();
  return result;
}
function hydrateArtifactStorage(options = {}) {
  const result = workspaceStorageCall("hydrateArtifactStorage", options);
  if (result && typeof result.then === "function") {
    return result.then((hydrated) => {
      updateDataSafetyTopbar();
      return hydrated;
    });
  }
  updateDataSafetyTopbar();
  return Promise.resolve(!!result);
}

function seedPersonalData() {
  const t = todayISO();
  dashboard.events = [
    { id: uid("ev"), title: "JooPark Workspace 둘러보기", date: t, allDay: true, start: null, end: null, category: "personal", location: "", memo: "왼쪽 메뉴에서 일정 · 할 일 · 메모를 관리하세요. 모든 데이터는 이 브라우저에 자동 저장됩니다. 이 일정은 삭제해도 됩니다.", createdAt: nowISO() },
    { id: uid("ev"), title: "주간 팀 회의", date: addDaysISO(t, 1), allDay: false, start: "10:00", end: "11:00", category: "meeting", location: "회의실 A · Zoom", memo: "", createdAt: nowISO() },
    { id: uid("ev"), title: "점심 약속", date: addDaysISO(t, 2), allDay: false, start: "12:30", end: "13:30", category: "personal", location: "", memo: "", createdAt: nowISO() },
    { id: uid("ev"), title: "월간 리포트 마감", date: addDaysISO(t, 3), allDay: true, start: null, end: null, category: "deadline", location: "", memo: "정산 + 진행률 요약 포함", createdAt: nowISO() },
  ];
  dashboard.todos = [
    { id: uid("td"), title: "이번 주 우선순위 정리", due: t, priority: "high", done: false, category: "업무", memo: "", createdAt: nowISO() },
    { id: uid("td"), title: "거래처 이메일 회신", due: addDaysISO(t, 1), priority: "med", done: false, category: "업무", memo: "", createdAt: nowISO() },
    { id: uid("td"), title: "운동 30분", due: null, priority: "low", done: false, category: "개인", memo: "", createdAt: nowISO() },
    { id: uid("td"), title: "환영합니다 — 왼쪽 체크박스를 눌러 완료 처리해 보세요", due: t, priority: "low", done: true, category: "개인", memo: "", createdAt: nowISO() },
  ];
  dashboard.notes = [
    { id: uid("nt"), title: "환영합니다 👋", body: "이 워크스페이스는 일정 · 할 일 · 메모를 한곳에서 관리합니다.\n\n• 모든 변경은 이 브라우저에 자동 저장됩니다.\n• 설정 → 데이터 백업에서 JSON으로 내보내기 / 가져오기 / 초기화를 할 수 있어요.\n• 상단 검색(⌘K)으로 현재 화면을 빠르게 필터링합니다.", color: "#22d3ee", pinned: true, updatedAt: nowISO() },
  ];
}

/* ---------- Nav badge counts ---------- */

function setText(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = String(value);
}
function updateNavCounts() {
  setText("navCountEvents", dashboard.events.length);
  setText("navCountTodos", dashboard.todos.filter((t) => !t.done).length);
  setText("navCountNotes", dashboard.notes.length);
  setText("navCountHabits", (dashboard.habits || []).filter((h) => !h.archived).length);
  setText("navCountWiki", llmWikiArticleCount());
  setText("navCountProjects", dashboard.projects.length);
  setText("navCountIssues", dashboard.issues.length);
  setText("navCountTasks", dashboard.gantt.tasks.length);
  setText("navCountTeam", dashboard.team.length);
  // DB nav badges
  const totalTables = dashboard.schemas.reduce((a, s) => a + s.databases.reduce((b, db) => b + db.tables.length, 0), 0);
  setText("navCountTables", totalTables);
  setText("navCountSlow", dashboard.queries.length);
  setText("navCountMig", dashboard.migrations.filter((m) => m.status === "pending").length);
  // Dynamic alerts badge (overdue + today items only)
  const alertCount = urgentAlertCount();
  setText("navCountAlerts", alertCount);
  const bellBadge = document.getElementById("bellBadge");
  if (bellBadge) {
    bellBadge.textContent = String(alertCount);
    bellBadge.style.display = alertCount > 0 ? "" : "none";
  }
}

/* commit = persist + refresh badges + re-render current view */
function commit() {
  persist();
  updateNavCounts();
  renderCurrentView();
}

/* ============================================================
 * View: 일정 (Calendar)
 * ============================================================ */

const calendarViewHelpers = window.JooParkCalendarView && typeof window.JooParkCalendarView.create === "function"
  ? window.JooParkCalendarView.create({
    html,
    raw,
    eventCats: EVENT_CATS,
    eventCatOrder: EVENT_CAT_ORDER,
    weekdaysKo: WEEKDAYS_KO,
    todayISO,
    ymToDate,
    ymd,
    matches,
    expandOccurrences,
    eventsOn,
    addDaysISO,
    isTodayISO,
    formatKoreanShort,
    formatKoreanFull,
    eventTimeLabel,
    kpiCard,
    searchEmptyState,
  })
  : null;

function calendarViewCall(name, ...args) {
  return callModuleHelper(calendarViewHelpers, "Calendar view", name, args);
}

function eventRow(e, opts) {
  return calendarViewCall("eventRow", e, opts);
}

function renderCalendar() {
  const view = refs.views.cal;
  if (!view) return;
  if (!state.calMonth) state.calMonth = monthKey(new Date());
  if (!state.calSelected) state.calSelected = todayISO();
  setHTML(view, calendarViewCall("renderCalendarHTML", {
    events: dashboard.events,
    todos: dashboard.todos,
    query: state.query,
    month: state.calMonth,
    selected: state.calSelected,
    mode: state.calMode,
  }));
}

const REPEAT_OPTIONS = [
  { value: "none",    label: "안 함" },
  { value: "daily",   label: "매일" },
  { value: "weekly",  label: "매주" },
  { value: "monthly", label: "매월" },
];

function openEventModal(arg) {
  // If arg is an occurrence view-model, resolve to its master for editing.
  if (arg && typeof arg === "object" && arg._masterId) {
    arg = eventById(arg._masterId) || arg;
  }
  const ev = editableModalRecord(arg);
  const editing = !!ev;
  const date = ev ? ev.date : (arg || state.calSelected || todayISO());
  const cat = ev ? ev.category : "work";
  const curRepeat = (ev && ev.repeat) || "none";
  const curRepeatUntil = (ev && ev.repeatUntil) || "";
  const isRepeating = editing && curRepeat !== "none";
  const deleteLabel = (ev && ev.repeat && ev.repeat !== "none") ? "이 일정 전체 삭제" : "이 일정 삭제";
  const repeatSelectHTML = REPEAT_OPTIONS.map((o) =>
    html`<option value="${o.value}" ${raw(o.value === curRepeat ? "selected" : "")}>${o.label}</option>`
  ).join("");
  const form = html`
    <form id="eventForm" class="modal-form">
      <label>제목
        <input type="text" name="title" required maxlength="120" value="${ev ? ev.title : ""}" placeholder="예: 팀 회의" />
      </label>
      <div class="form-row">
        <label>날짜
          <input type="date" name="date" required value="${date}" />
        </label>
        <label>분류
          <select name="category">${raw(selectOptions(EVENT_CATS, EVENT_CAT_ORDER, cat))}</select>
        </label>
      </div>
      <label class="check-inline">
        <input type="checkbox" name="allDay" ${raw(ev && ev.allDay ? "checked" : "")} /> 종일 일정
      </label>
      <div class="form-row" id="timeRow">
        <label>시작
          <input type="time" name="start" value="${ev && ev.start ? ev.start : ""}" />
        </label>
        <label>종료
          <input type="time" name="end" value="${ev && ev.end ? ev.end : ""}" />
        </label>
      </div>
      <div class="form-row">
        <label>반복
          <select name="repeat" id="repeatSelect">${raw(repeatSelectHTML)}</select>
        </label>
        <label id="repeatUntilLabel" ${raw(!isRepeating ? 'style="display:none"' : "")}>반복 종료일
          <input type="date" name="repeatUntil" id="repeatUntilInput" value="${curRepeatUntil}" />
        </label>
      </div>
      <label>장소
        <input type="text" name="location" maxlength="120" value="${ev ? ev.location || "" : ""}" placeholder="선택 사항" />
      </label>
      <label>메모
        <textarea name="memo" rows="3" maxlength="600" placeholder="선택 사항">${ev ? ev.memo || "" : ""}</textarea>
      </label>
      ${editing ? raw(modalDeleteButtonHTML({ action: "delete-event", dataAttr: "data-event-id", dataValue: ev.id, label: deleteLabel })) : ""}
    </form>
  `;
  openModal(editing ? "일정 편집" : "새 일정", form, () => saveEventFromForm(editing ? ev.id : null));
  const f = nodeQuery(document, "#eventForm");
  if (f) {
    const allDay = nodeQuery(f, "[name=allDay]");
    const timeRow = nodeQuery(f, "#timeRow");
    const syncTime = () => { if (timeRow) timeRow.style.display = allDay.checked ? "none" : ""; };
    if (allDay) allDay.addEventListener("change", syncTime);
    syncTime();

    const repeatSel = nodeQuery(f, "#repeatSelect");
    const repeatUntilLabel = nodeQuery(f, "#repeatUntilLabel");
    const syncRepeat = () => {
      if (repeatUntilLabel) {
        repeatUntilLabel.style.display = (repeatSel && repeatSel.value !== "none") ? "" : "none";
      }
    };
    if (repeatSel) repeatSel.addEventListener("change", syncRepeat);
    syncRepeat();
  }
}

function saveEventFromForm(id) {
  const form = nodeQuery(document, "#eventForm");
  if (!form) return false;
  const data = new FormData(form);
  const title = formText(data, "title");
  if (!title) { showToast("제목을 입력하세요", "warn"); return false; }
  const date = (data.get("date") || "").toString();
  if (!date) { showToast("날짜를 선택하세요", "warn"); return false; }
  const allDay = data.get("allDay") === "on";
  let start = allDay ? null : ((data.get("start") || "").toString() || null);
  let end = allDay ? null : ((data.get("end") || "").toString() || null);
  if (start && end && end < start) { const tmp = start; start = end; end = tmp; }
  const category = (data.get("category") || "work").toString();
  const location = formText(data, "location");
  const memo = formText(data, "memo");
  const repeat = (data.get("repeat") || "none").toString();
  const repeatUntilRaw = formText(data, "repeatUntil");
  const repeatUntil = (repeat !== "none" && repeatUntilRaw) ? repeatUntilRaw : null;
  if (id) {
    const ev = eventById(id);
    if (ev) {
      // Preserve existing exceptions when editing; don't reset skip list on edit.
      const exceptions = Array.isArray(ev.exceptions) ? ev.exceptions : [];
      Object.assign(ev, { title, date, allDay, start, end, category, location, memo, repeat, repeatUntil, exceptions });
    }
    showToast("일정을 수정했습니다", "info");
  } else {
    dashboard.events.push({ id: uid("ev"), title, date, allDay, start, end, category, location, memo, repeat, repeatUntil, exceptions: [], createdAt: nowISO() });
    showToast("일정을 추가했습니다", "info");
  }
  state.calSelected = date;
  state.calMonth = date.slice(0, 7);
  commit();
  return true;
}

function deleteEvent(id) {
  const idx = eventIndexById(id);
  if (idx < 0) {
    closeModal();
    return;
  }
  const removed = cloneRecord(dashboard.events[idx]);
  const deletedEntryId = captureDeletedItem("event", removed, { index: idx });
  dashboard.events.splice(idx, 1);
  closeModal();
  commit();
  showUndoToast("일정을 삭제했습니다", () => {
    if (!canUndoDeletedItem(deletedEntryId)) return;
    if (!restoreDeletedArrayItem(dashboard.events, idx, removed)) return;
    dropDeletedItem(deletedEntryId);
    commit();
    showToast("일정 삭제를 되돌렸습니다", "info");
  });
}

function calNav(delta) {
  if (!state.calMonth) state.calMonth = monthKey(new Date());
  if (!state.calSelected) state.calSelected = todayISO();
  if (state.calMode === "week") {
    state.calSelected = addDaysISO(state.calSelected, delta * 7);
    state.calMonth = state.calSelected.slice(0, 7);
  } else if (state.calMode === "day") {
    state.calSelected = addDaysISO(state.calSelected, delta);
    state.calMonth = state.calSelected.slice(0, 7);
  } else {
    state.calMonth = addMonthsKey(state.calMonth, delta);
  }
  renderCalendar();
}
function calToday() {
  state.calMonth = monthKey(new Date());
  state.calSelected = todayISO();
  renderCalendar();
}
function setCalendarMode(mode) {
  if (!["month", "week", "day"].includes(mode)) return;
  state.calMode = mode;
  if (!state.calSelected) state.calSelected = todayISO();
  state.calMonth = state.calSelected.slice(0, 7);
  renderCalendar();
}
function calendarDayButton(iso) {
  return [...document.querySelectorAll("#view-cal [data-action='cal-open-day']")]
    .find((el) => el.dataset.date === iso) || null;
}
function focusCalendarDay(iso) {
  const focus = () => {
    const cell = calendarDayButton(iso);
    if (!cell) return false;
    cell.tabIndex = 0;
    cell.focus({ preventScroll: true });
    return true;
  };
  if (!focus()) {
    requestAnimationFrame(focus);
    return;
  }
  requestAnimationFrame(focus);
}
function calSelectDay(iso, options = {}) {
  state.calSelected = iso;
  if (iso.slice(0, 7) !== state.calMonth) state.calMonth = iso.slice(0, 7);
  renderCalendar();
  if (options.focus) focusCalendarDay(iso);
}

/* ============================================================
 * View: 할 일 (To-Do)
 * ============================================================ */

const TODO_FILTERS = [
  { key: "active", label: "미완료" },
  { key: "today", label: "오늘" },
  { key: "upcoming", label: "예정" },
  { key: "done", label: "완료" },
  { key: "all", label: "전체" },
];

const LOCAL_SOURCE_FILTERS = [
  { key: "all", label: "전체 출처" },
  { key: "wiki", label: "LLM Wiki" },
];

const NOTE_SOURCE_FILTERS = [
  ...LOCAL_SOURCE_FILTERS,
  { key: "review", label: "Review" },
  { key: "workspace-review", label: "Workspace" },
  { key: "kb-ia-review", label: "KB/IA" },
  { key: "benchmark-review", label: "PM Bench" },
];

const todoViewHelpers = window.JooParkTodoView && typeof window.JooParkTodoView.create === "function"
  ? window.JooParkTodoView.create({
    html,
    raw,
    todayISO,
    matches,
    dueLabel,
    formatKoreanShort,
    kpiCard,
    searchEmptyState,
    todoPriority: TODO_PRIORITY,
    todoPrioRank: TODO_PRIO_RANK,
    todoFilters: TODO_FILTERS,
    todoSourceFilters: LOCAL_SOURCE_FILTERS,
  })
  : null;

function todoViewCall(name, ...args) {
  return callModuleHelper(todoViewHelpers, "Todo view", name, args);
}

function renderTodos() {
  const view = refs.views.todo;
  if (!view) return;
  if (!state.todoFilter) state.todoFilter = "active";
  setHTML(view, todoViewCall("renderTodosHTML", {
    todos: dashboard.todos,
    query: state.query,
    filter: state.todoFilter,
    sourceFilter: state.todoSourceFilter,
  }));
}

function quickAddTodo(form, options = {}) {
  if (!form) return;
  const input = nodeQuery(form, "input[name=title]");
  const title = (input && input.value || "").trim();
  if (!title) { if (input) input.focus(); return; }
  const priority = (nodeQuery(form, "[name=priority]") || {}).value || "med";
  const due = ((nodeQuery(form, "[name=due]") || {}).value || "") || null;
  dashboard.todos.push({ id: uid("td"), title, due, priority, done: false, category: "", memo: "", createdAt: nowISO() });
  showToast("할 일을 추가했습니다", "info");
  commit();
  // Re-focus the (freshly rendered) quick-add input for fast entry.
  const refocusSelector = options.refocusSelector || ".todo-quickadd input[name=title]";
  const next = nodeQuery(document, refocusSelector);
  if (next) next.focus();
}

function llmWikiRecordSourceMeta(record, kind) {
  const recordKind = kind === "note" ? "note" : "todo";
  const sourceKey = String(record && record.sourceKey || "");
  const prefix = `llm-wiki:${recordKind}:`;
  if (!sourceKey.startsWith(prefix)) return null;
  const articleId = sourceKey.slice(prefix.length);
  if (!articleId) return null;
  return { recordKind, sourceKey, articleId };
}

function llmWikiRecordSourceLinkHTML(record, kind) {
  const meta = llmWikiRecordSourceMeta(record, kind);
  if (!record || !meta) return "";
  return html`
    <section class="source-backlink modal-source-backlink" data-modal-source-link data-source-kind="llm-wiki" data-source-record-kind="${meta.recordKind}" data-source-record-id="${record.id}" data-source-article-id="${meta.articleId}">
      <span>
        <strong>LLM Wiki 원문</strong>
        <small>Source key · ${meta.sourceKey}</small>
      </span>
      <button type="button" class="secondary-btn" data-action="open-llm-wiki-source" data-source-record-kind="${meta.recordKind}" data-source-record-id="${record.id}" data-source-key="${meta.sourceKey}">원문 열기</button>
    </section>
  `;
}

function reviewRecordSourceMeta(record, kind) {
  const recordKind = kind === "todo" ? "todo" : "note";
  const sourceKey = String(record && record.sourceKey || "");
  const location = reviewIssueSourceLocation(sourceKey);
  if (!record || !location) return null;
  return { recordKind, sourceKey, location };
}

function reviewRecordSourceLinkHTML(record, kind) {
  const meta = reviewRecordSourceMeta(record, kind);
  if (!record || !meta) return "";
  return html`
    <section class="source-backlink modal-source-backlink" data-modal-source-link data-source-kind="review" data-source-record-kind="${meta.recordKind}" data-source-record-id="${record.id}" data-source-key="${meta.sourceKey}">
      <span>
        <strong>${meta.location.label}</strong>
        <small>Source key · ${meta.sourceKey}</small>
      </span>
      <button type="button" class="secondary-btn" data-action="open-review-record-source" data-source-record-kind="${meta.recordKind}" data-source-record-id="${record.id}" data-source-key="${meta.sourceKey}">패키지 열기</button>
    </section>
  `;
}

function openReviewSourceFromRecord(kind, recordId, fallbackSourceKey = "") {
  const recordKind = kind === "todo" ? "todo" : "note";
  const record = recordKind === "todo" ? todoById(recordId) : noteById(recordId);
  const sourceKey = String(record && record.sourceKey || fallbackSourceKey || "");
  const location = reviewIssueSourceLocation(sourceKey);
  if (!location) {
    showToast("연결된 review 패키지가 없습니다", "warn");
    return;
  }
  if (isModalOpen()) closeModal();
  state.llmWikiRecordBacklink = null;
  openReviewIssueSource(location);
}

function openTodoModal(arg) {
  const t = editableModalRecord(arg);
  const form = html`
    <form id="todoForm" class="modal-form">
      ${raw(llmWikiRecordSourceLinkHTML(t, "todo"))}
      <label>할 일
        <input type="text" name="title" required maxlength="160" value="${t ? t.title : ""}" placeholder="예: 보고서 초안 작성" />
      </label>
      <div class="form-row">
        <label>마감일
          <input type="date" name="due" value="${t && t.due ? t.due : ""}" />
        </label>
        <label>우선순위
          <select name="priority">${raw(selectOptions(TODO_PRIORITY, TODO_PRIO_ORDER, t ? t.priority : "med"))}</select>
        </label>
      </div>
      <label>분류
        <input type="text" name="category" maxlength="40" value="${t ? t.category || "" : ""}" placeholder="예: 업무 / 개인" />
      </label>
      <label>메모
        <textarea name="memo" rows="3" maxlength="600" placeholder="선택 사항">${t ? t.memo || "" : ""}</textarea>
      </label>
      ${t ? raw(modalDeleteButtonHTML({ action: "delete-todo", dataAttr: "data-todo-id", dataValue: t.id, label: "이 할 일 삭제" })) : ""}
    </form>
  `;
  openModal(t ? "할 일 편집" : "새 할 일", form, () => saveTodoFromForm(t ? t.id : null));
}

function saveTodoFromForm(id) {
  const form = nodeQuery(document, "#todoForm");
  if (!form) return false;
  const data = new FormData(form);
  const title = formText(data, "title");
  if (!title) { showToast("내용을 입력하세요", "warn"); return false; }
  const due = ((data.get("due") || "").toString() || null);
  const priority = (data.get("priority") || "med").toString();
  const category = formText(data, "category");
  const memo = formText(data, "memo");
  if (id) {
    const t = todoById(id);
    if (t) Object.assign(t, { title, due, priority, category, memo });
    showToast("할 일을 수정했습니다", "info");
  } else {
    dashboard.todos.push({ id: uid("td"), title, due, priority, done: false, category, memo, createdAt: nowISO() });
    showToast("할 일을 추가했습니다", "info");
  }
  commit();
  return true;
}

function toggleTodo(id) {
  const t = todoById(id);
  if (!t) return;
  t.done = !t.done;
  if (t.done) t.completedAt = nowISO();
  commit();
}

function deleteTodo(id) {
  const idx = todoIndexById(id);
  if (idx < 0) {
    closeModal();
    return;
  }
  const removed = cloneRecord(dashboard.todos[idx]);
  const deletedEntryId = captureDeletedItem("todo", removed, { index: idx });
  dashboard.todos.splice(idx, 1);
  closeModal();
  commit();
  showUndoToast("할 일을 삭제했습니다", () => {
    if (!canUndoDeletedItem(deletedEntryId)) return;
    if (!restoreDeletedArrayItem(dashboard.todos, idx, removed)) return;
    dropDeletedItem(deletedEntryId);
    commit();
    showToast("할 일 삭제를 되돌렸습니다", "info");
  });
}

function setTodoFilter(key) {
  state.todoFilter = key || "active";
  renderTodos();
}

function setTodoSourceFilter(key) {
  state.todoSourceFilter = key === "wiki" ? "wiki" : "all";
  renderTodos();
}

/* ============================================================
 * View: 메모 (Notes)
 * ============================================================ */

const notesViewHelpers = window.JooParkNotesView && typeof window.JooParkNotesView.create === "function"
  ? window.JooParkNotesView.create({
    html,
    raw,
    matches,
    safeNoteColor,
    renderMarkdown,
    formatKoreanShort,
    localYmd,
    searchEmptyState,
    noteSourceFilters: NOTE_SOURCE_FILTERS,
  })
  : null;

function notesViewCall(name, ...args) {
  return callModuleHelper(notesViewHelpers, "Notes view", name, args);
}

function renderNotes() {
  const view = refs.views.notes;
  if (!view) return;
  setHTML(view, notesViewCall("renderNotesHTML", {
    notes: dashboard.notes,
    query: state.query,
    sourceFilter: state.noteSourceFilter,
  }));
}

function setNoteSourceFilter(key) {
  state.noteSourceFilter = NOTE_SOURCE_FILTERS.some((filter) => filter.key === key) ? key : "all";
  renderNotes();
}

/* ---------- LLM 위키 ---------- */

const llmWikiViewHelpers = window.JooParkLlmWikiView && typeof window.JooParkLlmWikiView.create === "function"
  ? window.JooParkLlmWikiView.create({
    html,
    raw,
    matches,
    renderMarkdown,
    searchEmptyState,
  })
  : null;

function llmWikiArticleCount() {
  const data = window.JooParkLlmWikiView && window.JooParkLlmWikiView.data;
  if (!data || !Array.isArray(data.categories)) return 0;
  return data.categories.reduce((sum, cat) => sum + ((cat.articles || []).length), 0);
}

function llmWikiActionState() {
  const stateByArticle = {};
  const mark = (record, kind) => {
    const sourceKey = record && typeof record.sourceKey === "string" ? record.sourceKey : "";
    const prefix = `llm-wiki:${kind}:`;
    if (!sourceKey.startsWith(prefix)) return;
    const articleId = sourceKey.slice(prefix.length);
    if (!articleId) return;
    if (!stateByArticle[articleId]) stateByArticle[articleId] = {};
    stateByArticle[articleId][kind] = true;
  };
  (Array.isArray(dashboard.todos) ? dashboard.todos : []).forEach((record) => mark(record, "todo"));
  (Array.isArray(dashboard.notes) ? dashboard.notes : []).forEach((record) => mark(record, "note"));
  (Array.isArray(dashboard.issues) ? dashboard.issues : []).forEach((record) => mark(record, "issue"));
  return stateByArticle;
}

function renderLlmWiki() {
  const view = refs.views["llm-wiki"];
  if (!view) return;
  if (!llmWikiViewHelpers) {
    setHTML(view, html`<section class="empty">LLM 위키 모듈을 불러오지 못했습니다.</section>`);
    return;
  }
  setHTML(view, llmWikiViewHelpers.renderLlmWikiHTML({
    category: state.llmWikiCategory,
    article: state.llmWikiArticle,
    query: state.query,
    actionFilter: state.llmWikiActionFilter,
    actionState: llmWikiActionState(),
    sourceBacklink: activeLlmWikiRecordBacklink(state.llmWikiArticle || "") || activeIssueSourceBacklink("llm-wiki", state.llmWikiArticle || ""),
  }));
}

function selectLlmWiki(categoryId, articleId) {
  state.llmWikiCategory = categoryId;
  state.llmWikiArticle = articleId;
  // 카테고리/문서를 직접 고르면 검색 모드를 빠져나간다
  if (state.query) {
    resetSearchQueryState();
    syncSearchAffordance({ announce: false });
  }
  renderLlmWiki();
  scrollMainToTop();
}

function setLlmWikiActionFilter(filter) {
  const next = ["all", "open", "done"].includes(filter) ? filter : "all";
  state.llmWikiActionFilter = next;
  state.llmWikiArticle = null;
  renderLlmWiki();
  scrollMainToTop();
}

function llmWikiCategoryById(categories, categoryId) {
  return (categories || []).find((cat) => cat && cat.id === categoryId) || null;
}

function llmWikiArticles(category) {
  return category && Array.isArray(category.articles) ? category.articles : [];
}

function llmWikiArticleById(category, articleId) {
  return llmWikiArticles(category).find((item) => item && item.id === articleId) || null;
}

function llmWikiCategories() {
  const data = window.JooParkLlmWikiView && window.JooParkLlmWikiView.data;
  return data && Array.isArray(data.categories) ? data.categories : [];
}

function llmWikiArticleContext(categoryId = state.llmWikiCategory, articleId = state.llmWikiArticle) {
  const categories = llmWikiCategories();
  const category = llmWikiCategoryById(categories, categoryId);
  const article = category ? llmWikiArticleById(category, articleId) : null;
  if (!category || !article) return null;
  return { category, article };
}

function llmWikiArticleLocation(articleId) {
  const categories = llmWikiCategories();
  for (const category of categories) {
    const article = llmWikiArticleById(category, articleId);
    if (article) return { category, article };
  }
  return null;
}

function currentLlmWikiActionContext() {
  if (dashboard.currentView !== "llm-wiki") return null;
  return llmWikiArticleContext();
}

function llmWikiSourceRefs(article) {
  const sources = window.JooParkLlmWikiView && window.JooParkLlmWikiView.data && window.JooParkLlmWikiView.data.sources;
  return (article && Array.isArray(article.sources) ? article.sources : [])
    .map((id) => sources && sources[id])
    .filter(Boolean);
}

function llmWikiDraftKey(kind, article) {
  return `llm-wiki:${kind}:${article.id}`;
}

function llmWikiDraftBody(category, article) {
  const refs = llmWikiSourceRefs(article);
  const sourceLines = refs.slice(0, 8).map((source) => `- ${source.title} (${source.kind}, checked ${source.checked}): ${source.url}`);
  return [
    `# ${article.title}`,
    "",
    `Category: ${category.title}`,
    `Summary: ${article.summary}`,
    article.tags && article.tags.length ? `Tags: ${article.tags.join(", ")}` : "",
    "",
    "## Action prompt",
    `Turn this wiki reference into one concrete local workspace action. Keep provider/pricing/model claims source-checked before using them.`,
    "",
    sourceLines.length ? "## Sources" : "",
    ...sourceLines,
    "",
    `Source key: llm-wiki:${article.id}`,
  ].filter(Boolean).join("\n");
}

function createLlmWikiTodoDraft(categoryId, articleId) {
  const context = llmWikiArticleContext(categoryId, articleId);
  if (!context) {
    showToast("위키 문서를 찾을 수 없습니다", "warn");
    return null;
  }
  const { category, article } = context;
  const sourceKey = llmWikiDraftKey("todo", article);
  const existing = todoBySourceKey(sourceKey);
  if (existing) {
    return openTodoInTodoView(existing, { toast: `이미 생성된 위키 할 일입니다: ${existing.title}` });
  }
  const todo = {
    id: uid("td"),
    title: `[LLM Wiki] ${article.title}`,
    due: todayISO(),
    priority: "med",
    done: false,
    category: "LLM Wiki",
    memo: llmWikiDraftBody(category, article),
    createdAt: nowISO(),
    sourceKey,
    sourceKind: "llm-wiki-action",
  };
  dashboard.todos.push(todo);
  commit();
  state.todoFilter = "all";
  state.todoSourceFilter = "wiki";
  setView("todo");
  showToast("위키 글에서 할 일을 만들었습니다", "info");
  return todo;
}

function createLlmWikiNoteDraft(categoryId, articleId) {
  const context = llmWikiArticleContext(categoryId, articleId);
  if (!context) {
    showToast("위키 문서를 찾을 수 없습니다", "warn");
    return null;
  }
  const { category, article } = context;
  const sourceKey = llmWikiDraftKey("note", article);
  const existing = noteBySourceKey(sourceKey);
  if (existing) {
    return openNoteInNotesView(existing, { toast: `이미 생성된 위키 메모입니다: ${existing.title}` });
  }
  const note = {
    id: uid("nt"),
    title: `[LLM Wiki] ${article.title}`,
    body: llmWikiDraftBody(category, article),
    color: NOTE_COLORS[0],
    pinned: true,
    updatedAt: nowISO(),
    sourceKey,
    sourceKind: "llm-wiki-action",
  };
  dashboard.notes.push(note);
  commit();
  state.noteSourceFilter = "wiki";
  setView("notes");
  showToast("위키 글에서 메모를 만들었습니다", "info");
  return note;
}

function createLlmWikiIssueDraft(categoryId, articleId) {
  const context = llmWikiArticleContext(categoryId, articleId);
  if (!context) {
    showToast("위키 문서를 찾을 수 없습니다", "warn");
    return null;
  }
  const { category, article } = context;
  const project = currentProject();
  if (!project) {
    showToast("이슈를 만들 프로젝트가 없습니다", "warn");
    return null;
  }
  const sourceKey = llmWikiDraftKey("issue", article);
  const existing = issueBySourceKey(sourceKey);
  if (existing) {
    return openIssueInKanban(existing, { toast: `이미 생성된 위키 이슈입니다: ${existing.id}` });
  }
  const issue = {
    id: uid("issue"),
    project: project.id,
    title: `[LLM Wiki] ${article.title}`,
    status: "todo",
    priority: "med",
    assignee: "",
    labels: ["llm-wiki", "research"],
    due: null,
    estimate: 1,
    order: nextKanbanLaneOrder(project.id, "todo"),
    sourceKey,
    sourceKind: "llm-wiki-action",
    body: llmWikiDraftBody(category, article),
    executionOwner: dashboard.settings && dashboard.settings.displayName ? dashboard.settings.displayName : "",
    executionFirstAction: `Review ${article.title} and pick one local implementation task.`,
    executionDecisionGate: "Do not use volatile model, pricing, or provider claims until the cited sources are rechecked.",
    executionFallbackIfBlocked: "Convert the article into a pinned note and defer implementation.",
    executionChecklist: [
      { id: "wiki-source-check", text: "Recheck cited sources before acting on volatile claims", done: false },
      { id: "wiki-local-action", text: "Write one local workspace change or decision", done: false },
    ],
    executionChecklistReady: true,
  };
  dashboard.issues.push(issue);
  dashboard.currentProjectId = project.id;
  rebuildIndexes();
  commit();
  setView("pm-kanban");
  showToast(`위키 글에서 이슈를 만들었습니다: ${issue.id}`, "info");
  return issue;
}

function openNoteModal(arg) {
  const n = editableModalRecord(arg);
  const form = html`
    <form id="noteForm" class="modal-form">
      ${raw(llmWikiRecordSourceLinkHTML(n, "note"))}
      ${raw(reviewRecordSourceLinkHTML(n, "note"))}
      <label>제목
        <input type="text" name="title" maxlength="120" value="${n ? n.title : ""}" placeholder="제목" />
      </label>
      <label>내용 <small class="field-hint">Markdown 지원</small>
        <textarea name="body" rows="6" maxlength="4000" placeholder="메모를 입력하세요  ·  **굵게**, - 목록, [링크](url), \`코드\`">${n ? n.body || "" : ""}</textarea>
      </label>
      <div class="form-row note-form-row">
        ${raw(noteColorSwatchesHTML(n ? n.color : NOTE_COLORS[0]))}
        <label class="check-inline">
          <input type="checkbox" name="pinned" ${raw(n && n.pinned ? "checked" : "")} /> 상단 고정
        </label>
      </div>
      ${n ? raw(modalDeleteButtonHTML({ action: "delete-note", dataAttr: "data-note-id", dataValue: n.id, label: "이 메모 삭제" })) : ""}
    </form>
  `;
  openModal(n ? "메모 편집" : "새 메모", form, () => saveNoteFromForm(n ? n.id : null));
}

function saveNoteFromForm(id) {
  const form = nodeQuery(document, "#noteForm");
  if (!form) return false;
  const data = new FormData(form);
  const title = formText(data, "title");
  const body = (data.get("body") || "").toString();
  if (!title && !body.trim()) { showToast("제목이나 내용을 입력하세요", "warn"); return false; }
  const color = (data.get("color") || NOTE_COLORS[0]).toString();
  const pinned = data.get("pinned") === "on";
  if (id) {
    const n = noteById(id);
    if (n) Object.assign(n, { title, body, color, pinned, updatedAt: nowISO() });
    showToast("메모를 수정했습니다", "info");
  } else {
    dashboard.notes.push({ id: uid("nt"), title, body, color, pinned, updatedAt: nowISO() });
    showToast("메모를 추가했습니다", "info");
  }
  commit();
  return true;
}

function togglePin(id) {
  const n = noteById(id);
  if (!n) return;
  n.pinned = !n.pinned;
  n.updatedAt = nowISO();
  commit();
}

function deleteNote(id) {
  const idx = noteIndexById(id);
  if (idx < 0) {
    closeModal();
    return;
  }
  const removed = cloneRecord(dashboard.notes[idx]);
  const deletedEntryId = captureDeletedItem("note", removed, { index: idx });
  dashboard.notes.splice(idx, 1);
  closeModal();
  commit();
  showUndoToast("메모를 삭제했습니다", () => {
    if (!canUndoDeletedItem(deletedEntryId)) return;
    if (!restoreDeletedArrayItem(dashboard.notes, idx, removed)) return;
    dropDeletedItem(deletedEntryId);
    commit();
    showToast("메모 삭제를 되돌렸습니다", "info");
  });
}

/* ============================================================
 * View: 습관 트래커 (Habits)
 * ============================================================ */

/* weekDatesFor(iso) → 7 ISO strings for the week containing iso (Sun-first) */
function weekDatesFor(iso) {
  const d = dateFromISO(iso);
  const dow = d.getDay(); // 0=Sun
  const dates = [];
  for (let i = 0; i < 7; i++) {
    const dd = new Date(d);
    dd.setDate(d.getDate() - dow + i);
    dates.push(ymd(dd));
  }
  return dates;
}

/* habitStreak(habit) → { current, longest } */
function habitStreak(habit) {
  const log = habit.log || {};
  const today = todayISO();

  // Current streak: count back from today while log[date] is true
  let current = 0;
  let cursor = today;
  while (log[cursor]) {
    current += 1;
    cursor = addDaysISO(cursor, -1);
  }

  // Longest streak: collect all logged dates, sort, find max run
  const logged = sortedStrings(Object.keys(log).filter((d) => log[d]));
  let longest = 0;
  let run = 0;
  let prev = null;
  for (const d of logged) {
    if (prev && daysBetweenISO(prev, d) === 1) {
      run += 1;
    } else {
      run = 1;
    }
    if (run > longest) longest = run;
    prev = d;
  }
  // Ensure current is reflected in longest
  if (current > longest) longest = current;

  return { current, longest };
}

function daysBetweenISO(a, b) {
  return Math.round((dateFromISO(b) - dateFromISO(a)) / 86400000);
}

const habitsViewHelpers = window.JooParkHabitsView && typeof window.JooParkHabitsView.create === "function"
  ? window.JooParkHabitsView.create({
    html,
    raw,
    matches,
    todayISO,
    weekDatesFor,
    habitStreak,
    formatKoreanShort,
    kpiCard,
    panelHead,
    searchEmptyState,
    weekdaysKo: WEEKDAYS_KO,
    noteColors: NOTE_COLORS,
  })
  : null;

function habitsViewCall(name, ...args) {
  return callModuleHelper(habitsViewHelpers, "Habits view", name, args);
}

function renderHabits() {
  const view = refs.views.habits;
  if (!view) return;
  setHTML(view, habitsViewCall("renderHabitsHTML", {
    habits: ensureDashboardHabits(),
    query: state.query,
  }));
}

function openHabitModal(arg) {
  const h = editableModalRecord(arg);
  const form = html`
    <form id="habitForm" class="modal-form">
      <label>습관 이름
        <input type="text" name="name" required maxlength="60" value="${h ? h.name : ""}" placeholder="예: 물 2L 마시기" />
      </label>
      <div class="form-row">
        <label>이모지
          <input type="text" name="emoji" maxlength="4" value="${h ? h.emoji || "✅" : "✅"}" placeholder="✅" style="font-size:20px;text-align:center;width:72px" />
        </label>
        <label>주간 목표 (1-7일)
          <input type="number" name="target" min="1" max="7" value="${h ? (h.target || 7) : 7}" />
        </label>
      </div>
      <div class="form-row note-form-row">
        ${raw(noteColorSwatchesHTML(h ? h.color : NOTE_COLORS[0]))}
      </div>
      ${h ? raw(modalDeleteButtonHTML({ action: "habit-delete", dataAttr: "data-habit-id", dataValue: h.id, label: "이 습관 삭제" })) : ""}
    </form>
  `;
  openModal(h ? "습관 편집" : "새 습관", form, () => saveHabitFromForm(h ? h.id : null));
}

function saveHabitFromForm(id) {
  const form = nodeQuery(document, "#habitForm");
  if (!form) return false;
  const data = new FormData(form);
  const name = formText(data, "name");
  if (!name) { showToast("이름을 입력하세요", "warn"); return false; }
  const emoji = formText(data, "emoji") || "✅";
  const color = (data.get("color") || NOTE_COLORS[0]).toString();
  const target = clampInteger(data.get("target"), 1, 7, 7);
  const habits = ensureDashboardHabits();
  if (id) {
    const h = habitById(id);
    if (h) Object.assign(h, { name, emoji, color, target });
    showToast("습관을 수정했습니다", "info");
  } else {
    habits.push({ id: uid("hb"), name, emoji, color, target, createdAt: nowISO(), archived: false, log: {} });
    showToast("습관을 추가했습니다", "info");
  }
  commit();
  return true;
}

function toggleHabit(habitId, dateISO) {
  if (!habitId || !dateISO) return;
  ensureDashboardHabits();
  const h = habitById(habitId);
  if (!h) return;
  if (!h.log) h.log = {};
  if (h.log[dateISO]) {
    delete h.log[dateISO];
  } else {
    h.log[dateISO] = true;
  }
  commit();
}

function deleteHabit(id) {
  if (!Array.isArray(dashboard.habits)) return;
  const idx = habitIndexById(id);
  if (idx < 0) {
    closeModal();
    return;
  }
  const removed = cloneRecord(dashboard.habits[idx]);
  const deletedEntryId = captureDeletedItem("habit", removed, { index: idx });
  dashboard.habits.splice(idx, 1);
  closeModal();
  commit();
  showUndoToast("습관을 삭제했습니다", () => {
    if (!canUndoDeletedItem(deletedEntryId)) return;
    if (!restoreDeletedArrayItem(dashboard.habits, idx, removed)) return;
    dropDeletedItem(deletedEntryId);
    commit();
    showToast("습관 삭제를 되돌렸습니다", "info");
  });
}

/* ============================================================
 * View: 통계 / 인사이트 (Stats)
 * ============================================================ */

const statsViewHelpers = window.JooParkStatsView && typeof window.JooParkStatsView.create === "function"
  ? window.JooParkStatsView.create({
    html,
    raw,
    todayISO,
    localYmd,
    addDaysISO,
    dateFromISO,
    weekDatesFor,
    habitStreak,
    spark,
    kpiCard,
    panelHead,
    eventCats: EVENT_CATS,
    eventCatOrder: EVENT_CAT_ORDER,
    weekdaysKo: WEEKDAYS_KO,
  })
  : null;

function statsViewCall(name, ...args) {
  return callModuleHelper(statsViewHelpers, "Stats view", name, args);
}

function renderStats() {
  const view = refs.views.stats;
  if (!view) return;
  if (!Array.isArray(dashboard.todos)) dashboard.todos = [];
  if (!Array.isArray(dashboard.events)) dashboard.events = [];
  setHTML(view, statsViewCall("renderStatsHTML", {
    todos: dashboard.todos,
    habits: ensureDashboardHabits(),
    events: dashboard.events,
  }));
}

/* ============================================================
 * Data backup (export / import / reset) — used by Settings
 * ============================================================ */

function exportData() {
  try {
    const payload = JSON.stringify({
      app: "JooPark Workspace", v: 3,
      events:      dashboard.events,
      todos:       dashboard.todos,
      notes:       dashboard.notes,
      deletedItems: dashboard.deletedItems,
      reviewResults: dashboard.reviewResults,
      reviewIssueDraftOverrides: dashboard.reviewIssueDraftOverrides,
      dashboardInsights: dashboard.dashboardInsights,
      dashboardResearchLoops: dashboard.dashboardResearchLoops,
      dashboardImprovementCandidates: dashboard.dashboardImprovementCandidates,
      dashboardDecisionReceipts: dashboard.dashboardDecisionReceipts,
      dashboardEvidenceSnapshots: dashboard.dashboardEvidenceSnapshots,
      dashboardHealthChecks: dashboard.dashboardHealthChecks,
      settings:    dashboard.settings,
      habits:      dashboard.habits,
      projects:    dashboard.projects,
      issues:      dashboard.issues,
      gantt:       dashboard.gantt,
      team:        dashboard.team,
      dbInstances: dashboard.dbInstances,
      schemas:     dashboard.schemas,
      queries:     dashboard.queries,
      backups:     dashboard.backups,
      migrations:  dashboard.migrations,
      ui:          dashboard.ui,
      imports:     dashboard.imports,
      exportedAt:  nowISO(),
    }, null, 2);
    const blob = new Blob([payload], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `joopark-workspace-${todayISO()}.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    showToast("데이터를 내보냈습니다", "info");
  } catch (err) {
    showToast("내보내기 실패", "error");
  }
}

function rejectImportFile(input, message) {
  return backupImportUiCall("rejectImportFile", input, message);
}

function importBackupSummaryHTML(obj) {
  return backupImportUiCall("importBackupSummaryHTML", obj);
}

function applyImported(obj) {
  return backupImportUiCall("applyImported", obj);
}

function handleImportFile(event) {
  return backupImportUiCall("handleImportFile", event);
}

function confirmResetData() {
  openModal("전체 초기화", html`
    <div class="modal-confirm-body">
      <p>모든 <strong>일정 · 할 일 · 메모 · 습관 · 프로젝트 · DB 관리 데이터</strong>가 삭제됩니다. 이 작업은 되돌릴 수 없습니다.</p>
      <p class="muted-note">먼저 “데이터 내보내기”로 백업하는 것을 권장합니다.</p>
    </div>
  `, () => {
    dashboard.events = [];
    dashboard.todos = [];
    dashboard.notes = [];
    dashboard.deletedItems = [];
    dashboard.reviewResults = [];
    dashboard.reviewIssueDraftOverrides = [];
    dashboard.dashboardInsights = [];
    dashboard.dashboardResearchLoops = [];
    dashboard.dashboardImprovementCandidates = [];
    dashboard.dashboardDecisionReceipts = [];
    dashboard.dashboardEvidenceSnapshots = [];
    dashboard.dashboardHealthChecks = [];
    dashboard.habits = [];
    dashboard.projects = [];
    dashboard.issues = [];
    dashboard.gantt = { rangeStart: todayISO(), rangeEnd: addDaysISO(todayISO(), 60), tasks: [] };
    dashboard.team = [];
    dashboard.dbInstances = [];
    dashboard.schemas = [];
    dashboard.queries = [];
    dashboard.backups = [];
    dashboard.migrations = [];
    dashboard.imports = { projectImports: {}, autoProjectSeedDisabled: true, resetAt: nowISO() };
    dashboard.currentProjectId = "";
    dashboard.currentInstanceId = "";
    state.schemaExpanded = new Set();
    state.schemaSelectedTable = null;
    normalizeAllData();
    rebuildIndexes();
    commit();
    showToast("초기화했습니다", "info");
    return true;
  });
}

function settingsDataSummaryLines() {
  return [
    `- events: ${dashboard.events.length}`,
    `- todos: ${dashboard.todos.length}`,
    `- notes: ${dashboard.notes.length}`,
    `- recently deleted: ${Array.isArray(dashboard.deletedItems) ? dashboard.deletedItems.length : 0}`,
    `- review results: ${dashboard.reviewResults.length}`,
    `- review draft assignee overrides: ${dashboard.reviewIssueDraftOverrides.length}`,
    `- dashboard insights: ${(dashboard.dashboardInsights || []).length}`,
    `- dashboard research loops: ${(dashboard.dashboardResearchLoops || []).length}`,
    `- dashboard improvement candidates: ${(dashboard.dashboardImprovementCandidates || []).length}`,
    `- dashboard decision receipts: ${(dashboard.dashboardDecisionReceipts || []).length}`,
    `- dashboard evidence snapshots: ${(dashboard.dashboardEvidenceSnapshots || []).length}`,
    `- dashboard health checks: ${(dashboard.dashboardHealthChecks || []).length}`,
    `- habits: ${(dashboard.habits || []).filter((habit) => !habit.archived).length}`,
    `- projects: ${dashboard.projects.length}`,
    `- issues: ${dashboard.issues.length}`,
    `- gantt tasks: ${dashboard.gantt && Array.isArray(dashboard.gantt.tasks) ? dashboard.gantt.tasks.length : 0}`,
    `- team members: ${dashboard.team.length}`,
    `- db instances: ${dashboard.dbInstances.length}`,
    `- schema groups: ${dashboard.schemas.length}`,
    `- saved queries: ${dashboard.queries.length}`,
    `- migrations: ${dashboard.migrations.length}`,
    `- localStorage bytes: ${storedPayloadBytes()}`,
    `- last saved: ${formatLocalDateTime(dashboard.lastSavedAt)}`,
  ];
}

function settingsBackupHandoffText() {
  return [
    "# JooPark Workspace Backup Handoff / 백업 운영 체크리스트",
    "",
    "## 현재 데이터",
    ...settingsDataSummaryLines(),
    "",
    "## 안전한 순서",
    "1. 설정 -> 데이터 내보내기로 `joopark-workspace-YYYY-MM-DD.json` 파일을 먼저 보관합니다.",
    "2. 가져오기 전 파일의 `app` 값이 `JooPark Workspace`이고 `v` 값이 `3`인지 확인합니다.",
    `3. 가져오기 파일 크기는 ${formatBytes(MAX_IMPORT_BYTES)} 이하이고 컬렉션별 항목 수 상한을 넘지 않는지 확인합니다.`,
    "4. 가져오기는 현재 브라우저 데이터를 대체합니다. 복구가 필요하면 반드시 먼저 내보냅니다.",
    "5. 전체 초기화는 개인, 프로젝트, DB, import registry 데이터를 비웁니다.",
    "6. 초기화 후에는 Home 빈 상태 CTA로 첫 프로젝트, DB, 쿼리, 마이그레이션을 다시 생성합니다.",
    "7. 외부 공유나 패키징 전 `npm run verify`를 실행합니다.",
  ].join("\n");
}

function settingsPrivacyHandoffText() {
  return [
    "# JooPark Workspace Privacy & Storage Handoff / 개인정보·저장소 안전 체크리스트",
    "",
    "## 저장 범위",
    "- 이 앱은 정적 SPA 기준이며 서버 계정, 서버 DB, 원격 동기화를 사용하지 않습니다.",
    "- 모든 워크스페이스 데이터는 현재 브라우저 origin의 localStorage 키 `joopark.workspace.v3`에 저장됩니다.",
    "- Claude Artifact 환경처럼 `window.storage`가 제공되면 같은 v3 payload를 personal scope(shared=false) 키 `joopark-workspace:v3`에 비동기 미러링합니다.",
    "- 같은 파일을 `file://`로 직접 열면 localStorage 동작이 브라우저마다 달라질 수 있으므로 `http://127.0.0.1` 같은 로컬 정적 서버로 확인합니다.",
    "- private browsing 또는 incognito 세션, 브라우저 저장소 정리, 프로필 삭제 시 데이터가 사라질 수 있습니다.",
    "",
    "## 저장 금지",
    "- 토큰, 비밀번호, 세션 ID, API key, 주민번호, 결제 정보 같은 민감 정보는 입력하거나 저장하지 않습니다.",
    "- localStorage는 JavaScript에서 읽을 수 있으므로 인증이나 권한 검증이 필요한 비밀 저장소로 취급하지 않습니다.",
    "",
    "## 백업 파일 취급",
    "- 설정 -> 데이터 내보내기로 만든 JSON은 일정, 할 일, 메모, PM, DB 카탈로그, 테마를 포함한 전체 워크스페이스 데이터입니다.",
    "- 내보낸 JSON은 private 파일로 다루고, 공유 전에 개인 식별 정보와 민감 정보가 없는지 확인합니다.",
    "- 가져오기는 현재 브라우저 데이터를 대체합니다. 복구가 필요하면 먼저 현재 데이터를 내보냅니다.",
    "",
    "## 공개 전 확인",
    "1. Settings -> 데이터 백업에서 최신 JSON을 보관합니다.",
    "2. JSON 내부에 토큰, 비밀번호, API key, 주민번호가 없는지 확인합니다.",
    "3. `npm run verify`로 릴리스 패키지와 브라우저 smoke를 통과시킵니다.",
  ].join("\n");
}

function settingsDeployHandoffText() {
  const releaseGate = publishReadinessItems().find((item) => item.key === "release-gates") || {};
  const releaseGateEvidence = Array.isArray(releaseGate.evidence) ? releaseGate.evidence : [];
  return [
    "# JooPark Workspace Deploy Handoff / 배포 운영 체크리스트",
    "",
    "## 로컬 필수 게이트",
    "1. `npm run lint`",
    "2. `npm run test`",
    "3. `npm run verify`",
    "",
    "## Release gate evidence",
    ...releaseGateEvidence.map((item) => `- ${item}`),
    "",
    "## 패키지",
    "1. `node scripts/package-release.mjs`",
    "2. `node scripts/verify-release.mjs`",
    "3. `dist/release/`를 정적 서버에서 열거나 hosting artifact로 업로드합니다.",
    "",
    ...publishRepoPlaceholderGuardLines(),
    "",
    ...publishDispatchGateGuardLines(),
    "",
    "## Device-code approval handoff",
    "1. `gh auth refresh -h github.com -s workflow`가 one-time device code를 표시하면 `approvalUrl=https://github.com/login/device`에서 승인합니다.",
    "2. one-time device code는 프로젝트 파일, 로그, README, release receipt에 저장하지 않습니다.",
    "3. 승인 뒤 `gh auth status -h github.com`와 `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects`를 다시 실행해 `workflowScopeAvailable: true`와 `workflowScopeInstallBlocked: false`를 확인합니다.",
    "4. 승인 또는 GitHub UI 설치 확인 전에는 `install-remote-workflow-files.mjs`, `gh workflow run`, public launch copy, archive proof를 실행하지 않습니다.",
    "",
    "## GitHub Pages workflow",
    "1. `node scripts/prepare-github-pages-workflow.mjs --dry-run --check-scope`",
    "2. `workflowScopeAvailable`이 false이면 `gh auth refresh -h github.com -s workflow`로 CLI 권한을 갱신한 뒤 `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects`로 재확인합니다. 브라우저 인증을 진행하지 않으면 GitHub UI 경로를 사용합니다.",
    "3. `node scripts/plan-workflow-ui-install.mjs --dry-run --markdown`으로 GitHub UI target, `githubNewFileUrl`, `githubWorkflowUrl`, `templateCopyCommand`, `githubNewFileOpenCommand`, `githubWorkflowOpenCommand`, defaultBranch, template sha256, required terms, `suggestedRepo`, `nextVerificationCommand`를 확인합니다.",
    "4. `Remote workflow install packet` 또는 `workflow UI install plan`의 각 row에서 `installAction`을 확인합니다. `replace_existing_remote_file`은 edit-file page로 기존 파일을 전체 교체하고, `create_missing_remote_file`은 new-file page로 만들며, `verified_remote_matches_template`는 그대로 둡니다.",
    "5. workflow 파일은 repository default branch에 있어야 `workflow_dispatch`와 `schedule` 운영이 가능합니다.",
    "6. `githubWorkflowOpenCommand` 또는 `githubWorkflowUrl`에서 Actions workflow가 보이는지 확인합니다.",
    "7. `node scripts/check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write`로 default branch의 remote workflow file이 로컬 template과 같은지 확인하고 `remoteWorkflowFilesReady: true`, `remoteMatchesTemplate`를 확인합니다. System Status의 `Remote workflow install packet` 또는 `install packet 복사`로 GitHub edit/new-file page, `pbcopy` template, 재검증 명령을 한 번에 복사합니다.",
    "8. Pages 배포 job은 `pages: write`, `id-token: write`, `actions/upload-pages-artifact`, `actions/deploy-pages`, build/deploy `needs` 연결을 유지합니다.",
    "9. `node scripts/plan-publish-dispatch.mjs --dry-run`의 `workflowUiInstallPlans`에서 `templateCopyCommand`, `githubNewFileOpenCommand`, `githubWorkflowOpenCommand`, `templateSha256`를 다시 확인합니다.",
    "10. `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects`를 우선 실행하고, repo가 다르면 `node scripts/plan-publish-dispatch.mjs --live --repo OWNER/REPO` 템플릿에서 `OWNER/REPO`를 실제 repo로 바꿔 `repoEvidenceReady: true`, `remoteWorkflowFilesReady: true`, `dispatchReady: true`, `driftDispatchReady: true`, `allDispatchReady: true`를 확인한 뒤에만 `Publish JooPark Pages` workflow를 `workflow_dispatch`로 실행합니다.",
    "",
    "## Drift Watch workflow",
    "1. `node scripts/prepare-github-drift-watch-workflow.mjs --dry-run --check-scope`",
    "2. `.github/workflows/joopark-drift-watch.yml`도 workflow scope가 있는 세션에서 설치합니다.",
    "3. `driftDispatchReady: true`와 `allDispatchReady: true`가 확인된 뒤 advisory mode를 실행하고, 이후 repo-scoped `fail-on-drift` run으로 좁혀 확인합니다.",
    "",
    "## Post-dispatch evidence",
    "1. `node scripts/capture-publish-evidence.mjs --live --repo OWNER/REPO --markdown`으로 공유용 evidence report를 생성합니다.",
    "2. `node scripts/capture-publish-evidence.mjs --live --repo OWNER/REPO --write`로 JSON evidence를 저장합니다.",
    "3. Pages site의 `html_url`과 `status`가 기록되는지 확인합니다.",
    "4. `joopark-pages.yml`과 `joopark-drift-watch.yml`의 최신 run `status`와 `conclusion`이 success인지 확인합니다.",
    "",
    "## Publish readiness",
    ...publishReadinessMarkdownLines(),
  ].join("\n");
}

function copySettingsHandoff(target) {
  operationsCopyActionsCall("copySettingsHandoff", target);
}

function copySystemPublishHandoff(target) {
  operationsCopyActionsCall("copySystemPublishHandoff", target);
}

function copyPublishEvidenceShareUpdate(target) {
  operationsCopyActionsCall("copyPublishEvidenceShareUpdate", target);
}

function copyPublishLaunchAnnouncement(target) {
  operationsCopyActionsCall("copyPublishLaunchAnnouncement", target);
}

function copyPublishPostLaunchReceipt(target) {
  operationsCopyActionsCall("copyPublishPostLaunchReceipt", target);
}

function copyPublishLaunchProofReceipt(target) {
  operationsCopyActionsCall("copyPublishLaunchProofReceipt", target);
}

function copyRemoteWorkflowInstallPacket(target) {
  operationsCopyActionsCall("copyRemoteWorkflowInstallPacket", target);
}

function copyWorkflowUiInstallReceipt(target) {
  operationsCopyActionsCall("copyWorkflowUiInstallReceipt", target);
}

function copyHomeLaunchBlockerResolver(target) {
  operationsCopyActionsCall("copyHomeLaunchBlockerResolver", target);
}

function copyHomeLaunchActionChecklist(target) {
  operationsCopyActionsCall("copyHomeLaunchActionChecklist", target);
}

function copyPostInstallEvidenceIntake(target) {
  operationsCopyActionsCall("copyPostInstallEvidenceIntake", target);
}

function normalizePostInstallProofParserText(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[“”]/g, "\"")
    .replace(/[‘’]/g, "'")
    .replace(/\s*=\s*/g, "=");
}

function postInstallProofParserContext(value) {
  const rawText = String(value || "");
  const lines = rawText
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .filter((line) => !/\[(?:paste|replace|fill|todo|pending)[^\]]*\]/i.test(line))
    .filter((line) => !/^(?:[-*]\s*)?(expected success signals|post-install evidence fields to fill|required parser fields|detected parser fields|parser guard):?/i.test(line));
  return {
    rawText,
    text: normalizePostInstallProofParserText(lines.join("\n")),
    lines: lines.map((line) => ({
      raw: line,
      text: normalizePostInstallProofParserText(line),
    })),
  };
}

function postInstallProofParserHasFlag(text, key) {
  const normalized = normalizePostInstallProofParserText(text).replace(/\s*:\s*/g, ":");
  const compactKey = normalizePostInstallProofParserText(key);
  return normalized.includes(`${compactKey}=true`) || normalized.includes(`"${compactKey}":true`) || normalized.includes(`${compactKey}:true`);
}

function postInstallProofParserActualLine(context, markers, predicate) {
  return context.lines.some((line) => {
    if (!markers.some((marker) => line.text.includes(normalizePostInstallProofParserText(marker)))) return false;
    if (/\b(paste|replace|placeholder|todo|pending|missing)\b/i.test(line.raw)) return false;
    return predicate(line.raw, line.text);
  });
}

function postInstallProofParserTextHasAll(text, terms) {
  const normalized = normalizePostInstallProofParserText(text);
  return terms.every((term) => normalized.includes(normalizePostInstallProofParserText(term)));
}

function postInstallProofParserJsonFlagFallback(context, marker, flagKeys) {
  return postInstallProofParserTextHasAll(context.text, [marker])
    && flagKeys.every((key) => postInstallProofParserHasFlag(context.text, key));
}

function postInstallProofParserWorkflowCommitPredicate(workflowPath) {
  const normalizedPath = normalizePostInstallProofParserText(workflowPath);
  return (_raw, text) => text.includes(normalizedPath) && (text.includes("/commit/") || /\b[0-9a-f]{7,40}\b/.test(text));
}

function postInstallProofParserRules() {
  return [
    {
      key: "pages_workflow_commit",
      label: "Pages workflow commit",
      required: ".github/workflows/joopark-pages.yml commit URL or SHA",
      nextAction: "Paste the default-branch commit URL or SHA for .github/workflows/joopark-pages.yml from GitHub UI.",
      test: (context) => postInstallProofParserActualLine(context, ["pages_workflow_commit", "pages workflow commit", ".github/workflows/joopark-pages.yml"], postInstallProofParserWorkflowCommitPredicate(".github/workflows/joopark-pages.yml")),
    },
    {
      key: "drift_workflow_commit",
      label: "Drift Watch workflow commit",
      required: ".github/workflows/joopark-drift-watch.yml commit URL or SHA",
      nextAction: "Paste the default-branch commit URL or SHA for .github/workflows/joopark-drift-watch.yml from GitHub UI.",
      test: (context) => postInstallProofParserActualLine(context, ["drift_workflow_commit", "drift watch workflow commit", ".github/workflows/joopark-drift-watch.yml"], postInstallProofParserWorkflowCommitPredicate(".github/workflows/joopark-drift-watch.yml")),
    },
    {
      key: "remote_parity_proof",
      label: "Remote parity proof",
      required: "remoteWorkflowFilesReady=true",
      nextAction: "Run node scripts/check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write and paste remoteWorkflowFilesReady=true.",
      test: (context) => postInstallProofParserActualLine(context, ["remote_parity_proof", "remote parity proof"], (_raw, text) => postInstallProofParserHasFlag(text, "remoteWorkflowFilesReady")) || postInstallProofParserJsonFlagFallback(context, "\"generatedat\"", ["remoteWorkflowFilesReady", "remoteMatchesTemplate"]),
    },
    {
      key: "actions_visibility_proof",
      label: "Actions visibility proof",
      required: "remoteWorkflowVisibilityReady=true or gh workflow list shows both workflow paths",
      nextAction: "Run node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects --write and paste remoteWorkflowVisibilityReady=true.",
      test: (context) => postInstallProofParserActualLine(context, ["actions_visibility_proof", "actions visibility proof"], (_raw, text) => postInstallProofParserHasFlag(text, "remoteWorkflowVisibilityReady") || (text.includes("gh workflow list") && text.includes(".github/workflows/joopark-pages.yml") && text.includes(".github/workflows/joopark-drift-watch.yml"))) || postInstallProofParserTextHasAll(context.text, ["\"workflowlistsource\"", ".github/workflows/joopark-pages.yml", ".github/workflows/joopark-drift-watch.yml"]),
    },
    {
      key: "dispatch_readiness_proof",
      label: "Dispatch readiness proof",
      required: "dispatchReady=true, driftDispatchReady=true, allDispatchReady=true",
      nextAction: "Rerun node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects --write and paste dispatchReady=true, driftDispatchReady=true, and allDispatchReady=true.",
      test: (context) => postInstallProofParserActualLine(context, ["dispatch_readiness_proof", "dispatch readiness proof"], (_raw, text) => postInstallProofParserHasFlag(text, "dispatchReady") && postInstallProofParserHasFlag(text, "driftDispatchReady") && postInstallProofParserHasFlag(text, "allDispatchReady")) || postInstallProofParserJsonFlagFallback(context, "\"generatedat\"", ["dispatchReady", "driftDispatchReady", "allDispatchReady"]),
    },
    {
      key: "handoff_verifier_proof",
      label: "Handoff verifier proof",
      required: "verify-launch-handoff reports safeToDispatch=true before gh workflow run",
      nextAction: "Run node scripts/verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown and paste safeToDispatch=true.",
      test: (context) => postInstallProofParserActualLine(context, ["handoff_verifier_proof", "handoff verifier proof"], (_raw, text) => postInstallProofParserHasFlag(text, "safeToDispatch") && (text.includes("verify-launch-handoff") || text.includes("handoff verifier") || text.includes("before gh workflow run"))) || postInstallProofParserJsonFlagFallback(context, "\"verificationartifact\"", ["safeToDispatch"]),
    },
  ];
}

function parsePostInstallProofText(value) {
  const context = postInstallProofParserContext(value);
  const fields = postInstallProofParserRules().map((rule) => ({
    key: rule.key,
    label: rule.label,
    required: rule.required,
    nextAction: rule.nextAction,
    detected: rule.test(context),
  }));
  const detectedCount = fields.filter((field) => field.detected).length;
  const fieldCount = fields.length;
  const missingFields = fields.filter((field) => !field.detected);
  const coverage = fieldCount === 6 ? 1 : 0;
  const status = detectedCount === fieldCount ? "all_fields_detected" : detectedCount > 0 ? "partial_fields_detected" : "waiting_for_pasted_proof";
  const summary = [
    "JooPark Post-Install Proof Parser Receipt",
    `Status: ${status}`,
    `postInstallProofParserCoverage=${coverage}`,
    `Fields detected: ${detectedCount}/${fieldCount}`,
    "not dispatch approval",
    "Detected parser fields:",
    ...fields.map((field) => `- ${field.key}: ${field.detected ? "detected" : "missing"}; required=${field.required}; nextAction=${field.nextAction}`),
    "",
    "Missing field repair hints:",
    ...(missingFields.length
      ? missingFields.map((field) => `- ${field.key}: ${field.nextAction}`)
      : ["- none"]),
    "",
    "Stop condition: do not run gh workflow run until every post-install evidence field has been filled and verify-launch-handoff reports safeToDispatch=true.",
  ].join("\n");
  return { fields, detectedCount, fieldCount, coverage, status, summary };
}

function postInstallProofParserNode(target) {
  return target.closest("[data-post-install-proof-parser]");
}

function postInstallProofParserPanels(root = document) {
  return root?.matches && root.matches("[data-post-install-proof-parser]")
    ? [root]
    : Array.from((root || document).querySelectorAll("[data-post-install-proof-parser]"));
}

function postInstallProofParserInput(panel) {
  return nodeQuery(panel, "[data-post-install-proof-parser-input]");
}

function postInstallProofParserStatusText(panel) {
  return nodeQuery(panel, "[data-post-install-proof-parser-status-text]");
}

function postInstallProofParserSummary(panel) {
  return nodeQuery(panel, "[data-post-install-proof-parser-summary]");
}

function postInstallProofParserCopyStatus(panel) {
  return nodeQuery(panel, "[data-post-install-proof-parser-copy-status]");
}

function postInstallProofParserFieldRow(panel, key) {
  return nodeQuery(panel, `[data-post-install-proof-parser-field-key="${key}"]`);
}

function postInstallProofParserFieldState(row) {
  return nodeQuery(row, "span");
}

function postInstallProofParserFieldNextAction(row) {
  return nodeQuery(row, "[data-post-install-proof-parser-field-next-action]");
}

function updatePostInstallProofParser(root = document) {
  const panels = postInstallProofParserPanels(root);
  panels.forEach((panel) => {
    const input = postInstallProofParserInput(panel);
    const result = parsePostInstallProofText(input ? input.value : "");
    panel.dataset.postInstallProofParserReady = result.coverage === 1 ? "true" : "false";
    panel.dataset.postInstallProofParserCoverage = String(result.coverage);
    panel.dataset.postInstallProofParserFieldCount = String(result.fieldCount);
    panel.dataset.postInstallProofParserDetectedCount = String(result.detectedCount);
    panel.dataset.postInstallProofParserStatus = result.status;
    panel.dataset.postInstallProofParserDispatchApproval = "false";
    const status = postInstallProofParserStatusText(panel);
    if (status) {
      status.textContent = `${result.detectedCount}/${result.fieldCount} proof signals detected - not dispatch approval`;
    }
    const summary = postInstallProofParserSummary(panel);
    if (summary) summary.textContent = result.summary;
    result.fields.forEach((field) => {
      const row = postInstallProofParserFieldRow(panel, field.key);
      if (!row) return;
      row.dataset.postInstallProofParserFieldDetected = field.detected ? "true" : "false";
      row.dataset.postInstallProofParserFieldRequired = field.required;
      row.dataset.postInstallProofParserFieldNextAction = field.nextAction;
      const state = postInstallProofParserFieldState(row);
      if (state) state.textContent = field.detected ? "detected" : "missing";
      const nextAction = postInstallProofParserFieldNextAction(row);
      if (nextAction) nextAction.textContent = `Next: ${field.nextAction}`;
    });
  });
}

function copyPostInstallProofParserSummary(target) {
  const panel = postInstallProofParserNode(target);
  if (!panel) return;
  updatePostInstallProofParser(panel);
  const status = postInstallProofParserCopyStatus(panel);
  const text = nodeText(panel, "[data-post-install-proof-parser-summary]");
  copyTextWithLabeledStatus({
    text,
    datasetKey: "postInstallProofParserSummaryCopied",
    targets: [panel, target],
    status,
    statusLabel: "parser summary",
    copiedToast: "post-install proof parser summary를 복사했습니다",
  });
}

function copyPublishWorkflowScopePacket(target) {
  operationsCopyActionsCall("copyPublishWorkflowScopePacket", target);
}

function copyLaunchExecutionPacket(target) {
  operationsCopyActionsCall("copyLaunchExecutionPacket", target);
}

function copyLaunchCurrentActionPacket(target) {
  operationsCopyActionsCall("copyLaunchCurrentActionPacket", target);
}

function copyLaunchOperatorOnePage(target) {
  operationsCopyActionsCall("copyLaunchOperatorOnePage", target);
}

function copyLaunchReadinessRefreshReceipt(target) {
  operationsCopyActionsCall("copyLaunchReadinessRefreshReceipt", target);
}

function copyVerifyWorkspaceSummaryReceipt(target) {
  operationsCopyActionsCall("copyVerifyWorkspaceSummaryReceipt", target);
}

function releaseGateCachePanel(target) {
  return target.closest("[data-system-release-gate-cache]");
}

function releaseGateCacheRepairReceipt(target) {
  return target.closest("[data-release-gate-cache-repair-receipt]");
}

function copyReleaseGateCacheRepair(target) {
  copyPanelReceiptWithStatus({
    panel: releaseGateCachePanel(target),
    target,
    textSelector: "[data-release-gate-cache-repair-text]",
    statusSelector: "[data-release-gate-cache-repair-copy-status]",
    datasetKey: "releaseGateCacheRepairCopied",
    extraTargets: [releaseGateCacheRepairReceipt(target)],
    statusLabel: "cache repair",
    copiedToast: "release gate cache repair receipt를 복사했습니다",
  });
}

function releaseProvenancePanel(target) {
  return target.closest("[data-system-release-provenance]");
}

function copyReleaseProvenanceReceipt(target) {
  copyPanelReceiptWithStatus({
    panel: releaseProvenancePanel(target),
    target,
    textSelector: "[data-release-provenance-receipt-text]",
    statusSelector: "[data-release-provenance-receipt-copy-status]",
    datasetKey: "releaseProvenanceReceiptCopied",
    statusLabel: "provenance receipt",
    copiedToast: "release provenance receipt를 복사했습니다",
  });
}

function pagesAttestationProofIntakePanel(target) {
  return target.closest("[data-system-pages-attestation-proof-intake]");
}

function copyPagesAttestationProofIntake(target) {
  copyPanelReceiptWithStatus({
    panel: pagesAttestationProofIntakePanel(target),
    target,
    textSelector: "[data-pages-attestation-proof-intake-receipt-text]",
    statusSelector: "[data-pages-attestation-proof-intake-copy-status]",
    datasetKey: "pagesAttestationProofIntakeCopied",
    statusLabel: "attestation proof intake",
    copiedToast: "attestation proof intake를 복사했습니다",
  });
}

function copyOutputQualityAuditReceipt(target) {
  operationsCopyActionsCall("copyOutputQualityAuditReceipt", target);
}

function copyOutputQualityExternalClaimGuard(target) {
  operationsCopyActionsCall("copyOutputQualityExternalClaimGuard", target);
}

function updateUserDisplayName(name = dashboard.settings && dashboard.settings.displayName) { const el = nodeQuery(document, ".user strong"); if (el && name) el.textContent = name; }

function saveSettingsFromForm(form) {
  if (!form) return;
  const data = new FormData(form);
  const displayName = formText(data, "displayName") || "사용자";
  dashboard.settings.displayName = displayName;
  persist();
  updateUserDisplayName(displayName);
  showToast("설정을 저장했습니다", "info");
  renderSettings();
}

/* ============================================================
 * Router
 * ============================================================ */

const VIEW_LABELS = {
  home: "대시보드 홈",
  cal: "일정",
  todo: "할 일",
  notes: "메모",
  habits: "습관",
  stats: "통계",
  "llm-wiki": "LLM 위키",
  "pm-portfolio": "포트폴리오",
  "pm-kanban": "Kanban 보드",
  "pm-gantt": "간트 차트",
  "pm-team": "팀 / 리소스",
  "dbm-instances": "인스턴스 상태",
  "dbm-schema": "스키마 탐색",
  "dbm-queries": "질의 성능",
  "dbm-backups": "백업 / 마이그",
  settings: "설정",
  system: "시스템 상태",
};

const VIEW_RENDERERS = {
  home: renderHome, cal: renderCalendar, todo: renderTodos, notes: renderNotes, habits: renderHabits, stats: renderStats,
  "llm-wiki": renderLlmWiki, "pm-portfolio": renderPortfolio, "pm-kanban": renderKanban, "pm-gantt": renderGantt, "pm-team": renderTeam,
  "dbm-instances": () => dbCatalogCall("renderDbInstances"), "dbm-schema": () => dbCatalogCall("renderDbSchema"), "dbm-queries": () => dbCatalogCall("renderDbQueries"), "dbm-backups": () => dbCatalogCall("renderDbBackups"), settings: renderSettings, system: renderSystemStatus,
};

const navItemsByView = new Map();
let activeNavEls = [];
function buildNavIndex() {
  if (navItemsByView.size) return;
  refs.navItems.forEach((el) => {
    const view = el.dataset.view;
    if (!view) return;
    if (!navItemsByView.has(view)) navItemsByView.set(view, []);
    navItemsByView.get(view).push(el);
  });
}
function setActiveNav(viewName) {
  buildNavIndex();
  activeNavEls.forEach((el) => {
    el.classList.remove("active");
    el.classList.remove("is-active");
    el.removeAttribute("aria-current");
  });
  const next = navItemsByView.get(viewName) || [];
  next.forEach((el) => {
    el.classList.add("active");
    el.classList.add("is-active");
    el.setAttribute("aria-current", "page");
  });
  activeNavEls = next;
}

const OPS_RUNTIME_VIEW_GROUPS = Object.freeze({ settings: "release", system: "release", "pm-portfolio": "review" });
const OPS_RUNTIME_GETTERS = Object.freeze({
  release: [getReleaseStatusHelpers, getVerifyWorkspaceSummaryHelpers, getOperationsCopyActionsHelpers],
  operations: [getOperationsCopyActionsHelpers],
  review: [getReviewRecommendationExportHelpers, getReviewExecutionChecklistHelpers, getReviewIssuePayloadHelpers, getReviewResultViewHelpers, getReviewHandoffHelpers, getReviewArtifactViewHelpers, getReviewPackageViewHelpers, getReviewArtifactStateHelpers, getReviewResultDraftStateHelpers, getReviewCreationActionsHelpers, getReviewCopyActionsHelpers, getReviewSubmissionCopyHelpers, getReviewResultStateHelpers],
});
const opsRuntimeLoadPromises = new Map();
function opsRuntimeGroupForView(viewName) { return OPS_RUNTIME_VIEW_GROUPS[viewName] || ""; }
function refreshOpsRuntimeHelpers(group) { (OPS_RUNTIME_GETTERS[group] || []).forEach((getter) => getter()); }
function opsRuntimeGroupReady(group) { refreshOpsRuntimeHelpers(group); return (OPS_RUNTIME_GETTERS[group] || []).every((getter) => !!getter()); }
function ensureOpsRuntime(group) {
  if (opsRuntimeGroupReady(group)) return Promise.resolve(true);
  const loader = lazyRuntimeLoader();
  if (!loader || typeof loader.load !== "function") return Promise.reject(new Error(`operations runtime loader unavailable: ${group}`));
  if (!opsRuntimeLoadPromises.has(group)) opsRuntimeLoadPromises.set(group, loader.load(group).then(() => (refreshOpsRuntimeHelpers(group), opsRuntimeGroupReady(group))).finally(() => opsRuntimeLoadPromises.delete(group)));
  return opsRuntimeLoadPromises.get(group);
}
function renderOpsRuntimeLoading(viewName, group) {
  const view = refs.views[viewName];
  if (view) setHTML(view, html`<section class="panel ops-runtime-loading" data-ops-runtime-loading data-ops-runtime-group="${group}"><div class="panel-head"><div><h2>${VIEW_LABELS[viewName] || "운영 화면"} 준비 중</h2><small>운영/리뷰 런타임을 지연 로드하고 있습니다.</small></div><span class="pill warn">lazy runtime</span></div></section>`);
}
function queueOpsRuntimeRender(viewName, group) {
  ensureOpsRuntime(group).then(() => {
    if (dashboard.currentView === viewName) renderCurrentView();
    if (group === "release") refreshVerifyWorkspaceSummaryEvidence().catch(() => {});
  }).catch((error) => handleRuntimeError(error, { source: "ops-runtime", view: viewName, group }));
}

function renderCurrentView() {
  try {
    const lazyGroup = opsRuntimeGroupForView(dashboard.currentView);
    if (lazyGroup && !opsRuntimeGroupReady(lazyGroup)) {
      renderOpsRuntimeLoading(dashboard.currentView, lazyGroup);
      queueOpsRuntimeRender(dashboard.currentView, lazyGroup);
      return null;
    }
    return (VIEW_RENDERERS[dashboard.currentView] || renderHome)();
  } catch (error) {
    handleRuntimeError(error, { source: "render", view: dashboard.currentView });
    return null;
  }
}

let activeViewEl = null;

function normalizeRouteView(name) {
  return VIEWS.includes(name) ? name : "home";
}

function routeViewFromLocation() {
  const rawHash = (location.hash || "").slice(1);
  let name = rawHash || "home";
  try {
    name = decodeURIComponent(name);
  } catch (_) {
    name = "home";
  }
  return normalizeRouteView(name);
}

function syncRouteHistory(viewName, mode) {
  if (mode === "none") return;
  const hash = `#${viewName}`;
  if (location.hash === hash) return;
  const state = { view: viewName, routeDeepLinkCoverage: 1 };
  try {
    if (mode === "push") history.pushState(state, "", hash);
    else history.replaceState(state, "", hash);
  } catch (_) {
    history.replaceState(null, "", hash);
  }
}

function syncViewDataset(name) {
  document.body.dataset.view = name; // 상단바 맥락화(프로젝트 선택기 노출)·뷰별 CSS 훅
  document.body.dataset.routeView = name;
  document.body.dataset.routeHash = `#${name}`;
  document.body.dataset.routeDeepLinkCoverage = "1";
}

function syncActiveViewElement(name, previous) {
  if (previous !== name && activeViewEl) {
    activeViewEl.hidden = true;
  } else if (!activeViewEl) {
    // initial pass: hide everything except target
    Object.entries(refs.views).forEach(([k, el]) => {
      if (!el) return;
      el.hidden = (k !== name);
    });
  }
  const nextEl = refs.views[name];
  if (nextEl) {
    nextEl.hidden = false;
    activeViewEl = nextEl;
  }
}

function routeHistoryModeForView(previous, name) {
  return previous && previous !== name ? "push" : "replace";
}

function resetViewTransientState(previous, name) {
  resetSearchQueryState();
  state.kanbanFilter = null;
  state.kanbanSourceFilter = "all";
  if (previous !== name) { state.llmWikiCategory = null; state.llmWikiArticle = null; }
  syncSearchAffordance({ announce: document.activeElement === refs.query });
}

function refreshViewPostRender(name) {
  if (name === "settings" || name === "system") refreshStorageHealth({ render: true });
  scrollMainToTop();
}

function setView(name, options = {}) {
  name = normalizeRouteView(name);
  const previous = dashboard.currentView;
  if (previous !== name) closeSheet({ restoreFocus: false });
  dashboard.currentView = name;
  syncViewDataset(name);
  syncActiveViewElement(name, previous);
  setActiveNav(name);
  const defaultHistoryMode = routeHistoryModeForView(previous, name);
  syncRouteHistory(name, options.history || defaultHistoryMode);
  resetViewTransientState(previous, name);
  renderCurrentView();
  refreshViewPostRender(name);
}

/* ============================================================
 * Kanban drag-and-drop
 * ============================================================ */

let kanbanDragId = null;
let kanbanPointerDrag = null;

function clearKanbanDragClasses(board) {
  const root = board || document.getElementById("kanbanBoard");
  if (!root) return;
  root.querySelectorAll(".kanban-col").forEach((col) => {
    col.classList.remove("drag-over");
    col.classList.remove("touch-drag-over");
  });
  root.querySelectorAll(".kanban-card-wrap").forEach((card) => {
    card.classList.remove("is-touch-dragging");
  });
}

function kanbanPlacementOptions(targetWrap, draggedId, clientY) {
  const options = {};
  if (targetWrap && targetWrap.dataset.issueId && targetWrap.dataset.issueId !== draggedId) {
    const rect = targetWrap.getBoundingClientRect();
    if (clientY < rect.top + rect.height / 2) options.beforeId = targetWrap.dataset.issueId;
    else options.afterId = targetWrap.dataset.issueId;
  }
  return options;
}

function kanbanDropTargetFromPoint(clientX, clientY) {
  const target = document.elementFromPoint(clientX, clientY);
  return kanbanDropTargetFromElement(target);
}

function kanbanDropTargetFromElement(target) {
  if (!target) return null;
  const col = target.closest("[data-kanban-col]");
  if (!col) return null;
  return {
    col,
    status: col.dataset.kanbanCol,
    wrap: target.closest(".kanban-card-wrap[data-issue-id]"),
  };
}

function kanbanDropTargetFromEvent(event) {
  return kanbanDropTargetFromPoint(event.clientX, event.clientY) || kanbanDropTargetFromElement(event.target);
}

function finishKanbanPointerDrag(event, { cancel = false } = {}) {
  const drag = kanbanPointerDrag;
  if (!drag) return;
  kanbanPointerDrag = null;
  if (drag.card && typeof drag.card.releasePointerCapture === "function") {
    try { drag.card.releasePointerCapture(drag.pointerId); } catch (_) {}
  }
  clearKanbanDragClasses(drag.board);
  const clientX = Number.isFinite(event.clientX) ? event.clientX : drag.lastX;
  const clientY = Number.isFinite(event.clientY) ? event.clientY : drag.lastY;
  if (!drag.active) {
    const dx = Math.abs(Number(clientX || 0) - Number(drag.startX || 0));
    const dy = Math.abs(Number(clientY || 0) - Number(drag.startY || 0));
    drag.active = Math.max(dx, dy) >= 8;
  }
  if (cancel || !drag.active) return;
  const drop = kanbanDropTargetFromEvent(event) || kanbanDropTargetFromPoint(clientX, clientY) || drag.lastDrop;
  if (!drop || !drop.status) return;
  moveIssue(drag.id, drop.status, kanbanPlacementOptions(drop.wrap, drag.id, clientY));
}

function setupKanbanDrag() {
  const board = document.getElementById("kanbanBoard");
  if (!board) return;

  board.addEventListener("dragstart", (event) => {
    const wrap = event.target.closest("[data-issue-id]");
    if (!wrap) return;
    kanbanDragId = wrap.dataset.issueId;
    wrap.classList.add("is-dragging");
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", kanbanDragId);
  });

  board.addEventListener("dragend", (event) => {
    const wrap = event.target.closest("[data-issue-id]");
    if (wrap) wrap.classList.remove("is-dragging");
    clearKanbanDragClasses(board);
    kanbanDragId = null;
  });

  board.addEventListener("dragover", (event) => {
    const col = event.target.closest("[data-kanban-col]");
    if (!col) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
    board.querySelectorAll(".kanban-col").forEach((c) => c.classList.remove("drag-over"));
    col.classList.add("drag-over");
  });

  board.addEventListener("dragleave", (event) => {
    const col = event.target.closest("[data-kanban-col]");
    if (col && !col.contains(event.relatedTarget)) col.classList.remove("drag-over");
  });

  board.addEventListener("drop", (event) => {
    const col = event.target.closest("[data-kanban-col]");
    if (!col) return;
    event.preventDefault();
    const id = kanbanDragId || event.dataTransfer.getData("text/plain");
    const newStatus = col.dataset.kanbanCol;
    const targetWrap = event.target.closest(".kanban-card-wrap[data-issue-id]");
    const options = kanbanPlacementOptions(targetWrap, id, event.clientY);
    if (id && newStatus) moveIssue(id, newStatus, options);
    clearKanbanDragClasses(board);
    kanbanDragId = null;
  });

  board.addEventListener("pointerdown", (event) => {
    if (!["touch", "pen"].includes(event.pointerType)) return;
    if (event.button !== 0) return;
    if (event.target.closest("button, a, input, select, textarea, [contenteditable='true']")) return;
    const card = event.target.closest(".kanban-card-wrap[data-issue-id]");
    if (!card) return;
    kanbanPointerDrag = {
      id: card.dataset.issueId,
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      active: false,
      card,
      board,
    };
    if (typeof card.setPointerCapture === "function") {
      try { card.setPointerCapture(event.pointerId); } catch (_) {}
    }
  });

  board.addEventListener("pointermove", (event) => {
    const drag = kanbanPointerDrag;
    if (!drag || drag.pointerId !== event.pointerId) return;
    const dx = Math.abs(event.clientX - drag.startX);
    const dy = Math.abs(event.clientY - drag.startY);
    if (!drag.active && Math.max(dx, dy) < 8) return;
    drag.active = true;
    event.preventDefault();
    drag.card.classList.add("is-touch-dragging");
    const drop = kanbanDropTargetFromEvent(event);
    drag.lastX = event.clientX;
    drag.lastY = event.clientY;
    drag.lastDrop = drop;
    board.querySelectorAll(".kanban-col").forEach((col) => col.classList.remove("touch-drag-over"));
    if (drop && drop.col) drop.col.classList.add("touch-drag-over");
  });

  board.addEventListener("pointerup", (event) => {
    if (kanbanPointerDrag && kanbanPointerDrag.pointerId === event.pointerId) {
      finishKanbanPointerDrag(event);
    }
  });

  board.addEventListener("pointercancel", (event) => {
    if (kanbanPointerDrag && kanbanPointerDrag.pointerId === event.pointerId) {
      finishKanbanPointerDrag(event, { cancel: true });
    }
  });
}

/* ============================================================
 * PM CRUD — Projects, Issues (Kanban), Gantt Tasks, Team Members
 * ============================================================ */

function optionHTML(value, label, selected = false) {
  return html`<option value="${value}" ${raw(selected ? "selected" : "")}>${label}</option>`;
}

function optionListHTML(items, valueFn, labelFn, selectedFn = () => false) {
  return (items || []).map((item) => optionHTML(valueFn(item), labelFn(item), selectedFn(item))).join("");
}

function selectedOptionKey(selectedValue = "", fallbackValue = "") {
  const selected = selectedValue == null ? "" : String(selectedValue);
  const fallback = fallbackValue == null ? "" : String(fallbackValue);
  return selected || fallback;
}

function projectOptionsHTML(selectedProjectId = "", fallbackSelectedProjectId = "") {
  const current = selectedOptionKey(selectedProjectId, fallbackSelectedProjectId);
  return optionListHTML(dashboard.projects, (project) => project.id, (project) => project.name, (project) => !!current && project.id === current);
}

function keyedOptionsHTML(keys, labelMap, selectedKey = "", fallbackSelectedKey = "") {
  const current = selectedOptionKey(selectedKey, fallbackSelectedKey);
  return optionListHTML(keys, (key) => key, (key) => labelMap[key], (key) => !!current && key === current);
}

function teamMemberLabel(member) {
  return `${member.name} (${member.role})`;
}

function teamMemberOptionsHTML(selectedMemberId = "") {
  const current = selectedOptionKey(selectedMemberId);
  return [
    optionHTML("", "—"),
    optionListHTML(dashboard.team, (member) => member.id, teamMemberLabel, (member) => !!current && member.id === current),
  ].join("");
}

/* ---- 체크박스 목록 빌더 ---- */
function checkboxList(arr, valueKey, labelFn, checkedSet, name) {
  return arr.map((item) => html`
    <label class="check-inline">
      <input type="checkbox" name="${name}" value="${item[valueKey]}" ${raw(checkedSet.has(item[valueKey]) ? "checked" : "")} />
      ${labelFn(item)}
    </label>
  `).join("");
}

/* ============================================================
 * Projects CRUD
 * ============================================================ */

const PM_STATUS_MAP = { "on-track": "정상", "at-risk": "주의", delayed: "지연" };
const PM_STATUS_ORDER = ["on-track", "at-risk", "delayed"];
const PM_HEALTH_MAP = { green: "녹색", amber: "주황", red: "적색" };
const PM_HEALTH_ORDER = ["green", "amber", "red"];
const TASK_COLOR_MAP = { blue: "파랑", cyan: "청록", green: "초록", amber: "주황", red: "빨강", violet: "보라" };
const TASK_COLOR_ORDER = ["blue", "cyan", "green", "amber", "red", "violet"];

function openProjectModal(arg) {
  const p = editableModalRecord(arg);
  const memberChecked = new Set(p ? p.members : []);
  const statusOptions = keyedOptionsHTML(PM_STATUS_ORDER, PM_STATUS_MAP, p ? p.status : "");
  const healthOptions = keyedOptionsHTML(PM_HEALTH_ORDER, PM_HEALTH_MAP, p ? p.health : "");
  const form = html`
    <form id="projectForm" class="modal-form">
      <label>이름
        <input type="text" name="name" required maxlength="80" value="${p ? p.name : ""}" placeholder="예: 신규 데이터 파이프라인" />
      </label>
      <div class="form-row">
        <label>담당
          <input type="text" name="owner" maxlength="40" value="${p ? p.owner : ""}" placeholder="예: 데이터팀" />
        </label>
        <label>마감일
          <input type="date" name="deadline" value="${p ? p.deadline : ""}" />
        </label>
      </div>
      <div class="form-row">
        <label>진행률 (0-100)
          <input type="number" name="progress" min="0" max="100" value="${p ? p.progress : 0}" />
        </label>
        <label>상태
          <select name="status">
            ${raw(statusOptions)}
          </select>
        </label>
        <label>헬스
          <select name="health">
            ${raw(healthOptions)}
          </select>
        </label>
      </div>
      <label>멤버
        <div class="pm-checkbox-group">
          ${raw(checkboxList(dashboard.team, "id", teamMemberLabel, memberChecked, "members"))}
        </div>
      </label>
      ${p ? raw(modalDeleteButtonHTML({ action: "project-delete", dataAttr: "data-project-id", dataValue: p.id, label: "이 프로젝트 삭제" })) : ""}
    </form>
  `;
  openModal(p ? "프로젝트 편집" : "새 프로젝트 등록", form, () => saveProjectFromForm(p ? p.id : null));
}

function saveProjectFromForm(id) {
  const form = nodeQuery(document, "#projectForm");
  if (!form) return false;
  const data = new FormData(form);
  const name = formText(data, "name");
  if (!name) { showToast("이름을 입력하세요", "warn"); return false; }
  const owner = formText(data, "owner") || "—";
  const deadline = (data.get("deadline") || "").toString() || "2099-12-31";
  const progress = clampInteger(data.get("progress"), 0, 100);
  const status = (data.get("status") || "on-track").toString();
  const health = (data.get("health") || "green").toString();
  const members = data.getAll("members");
  if (id) {
    const p = indexes.projectById.get(id);
    if (p) {
      Object.assign(p, { name, owner, deadline, progress, status, health, members });
    }
    showToast(`프로젝트 '${name}' 수정`, "info");
  } else {
    const newId = uid("proj");
    const proj = { id: newId, name, owner, progress, status, health, deadline, burn: [0, 0, 0, 0, 0, 0, 0], risks: 0, openIssues: 0, members };
    dashboard.projects.push(proj);
    dashboard.currentProjectId = newId;
  }
  rebuildIndexes();
  // 멤버의 projects 목록도 동기화
  if (id) {
    const p = indexes.projectById.get(id);
    if (p) {
      dashboard.team.forEach((m) => {
        const hasProj = p.members.includes(m.id);
        if (hasProj && !m.projects.includes(id)) m.projects.push(id);
        if (!hasProj) m.projects = m.projects.filter((pid) => pid !== id);
      });
    }
  } else {
    const newProj = dashboard.projects[dashboard.projects.length - 1];
    members.forEach((mid) => {
      const m = indexes.teamById.get(mid);
      if (m && !m.projects.includes(newProj.id)) m.projects.push(newProj.id);
    });
    showToast(`프로젝트 '${name}' 등록`, "info");
  }
  updateProjectSelectLabel();
  commit();
  return true;
}

function deleteProject(id) {
  const p = indexes.projectById.get(id);
  if (!p) return;
  openModal("프로젝트 삭제", html`
    <div class="modal-confirm-body">
      <p>프로젝트 <strong>${p.name}</strong>을(를) 삭제합니다.</p>
      <p class="muted-note">연결된 이슈와 간트 작업도 모두 삭제됩니다. 되돌릴 수 없습니다.</p>
    </div>
  `, () => {
    // 이슈 삭제
    dashboard.issues = dashboard.issues.filter((i) => i.project !== id);
    // 간트 작업 삭제
    dashboard.gantt.tasks = dashboard.gantt.tasks.filter((t) => t.project !== id);
    // 팀원 projects 목록에서 제거
    dashboard.team.forEach((m) => { m.projects = m.projects.filter((pid) => pid !== id); });
    // 프로젝트 삭제
    const idx = projectIndexById(id);
    if (idx >= 0) dashboard.projects.splice(idx, 1);
    // currentProjectId 보정
    if (dashboard.currentProjectId === id) {
      dashboard.currentProjectId = dashboard.projects.length ? dashboard.projects[0].id : "";
      updateProjectSelectLabel();
    }
    rebuildIndexes();
    closeModal();
    showToast(`프로젝트 '${p.name}' 삭제`, "info");
    commit();
    return true;
  });
}

/* ============================================================
 * Issues (Kanban) CRUD + move
 * ============================================================ */

const ISSUE_STATUS_LABELS = { todo: "To Do", "in-progress": "In Progress", review: "Review", done: "Done" };
const ISSUE_STATUS_ORDER = ["todo", "in-progress", "review", "done"];
const ISSUE_PRIORITY_MAP = { crit: "Critical", high: "High", med: "Medium", low: "Low" };
const ISSUE_PRIORITY_ORDER = ["crit", "high", "med", "low"];
const KANBAN_ORDER_STEP = 1000;

function issueKanbanOrder(issue, fallbackIndex = 0) {
  const order = Number(issue && issue.order);
  return Number.isFinite(order) && order > 0 ? order : (Number(fallbackIndex) + 1) * KANBAN_ORDER_STEP;
}

function compareKanbanIssueEntriesByOrder(a, b) {
  const orderDiff = issueKanbanOrder(a.issue, a.index) - issueKanbanOrder(b.issue, b.index);
  if (orderDiff !== 0) return orderDiff;
  return a.index - b.index;
}

function sortedKanbanLaneIssues(project, status, options = {}) {
  const excludeId = options.excludeId || "";
  return dashboard.issues
    .map((issue, index) => ({ issue, index }))
    .filter((entry) => entry.issue.project === project && entry.issue.status === status && entry.issue.id !== excludeId)
    .sort(compareKanbanIssueEntriesByOrder)
    .map((entry) => entry.issue);
}

function resequenceKanbanLane(project, status, orderedIssues) {
  const lane = Array.isArray(orderedIssues) ? orderedIssues : sortedKanbanLaneIssues(project, status);
  lane.forEach((issue, index) => {
    issue.order = (index + 1) * KANBAN_ORDER_STEP;
  });
  return lane.length;
}

function normalizeKanbanIssueOrders() {
  const lanes = new Map();
  dashboard.issues.forEach((issue, index) => {
    const key = `${issue.project || ""}\u0000${issue.status || "todo"}`;
    if (!lanes.has(key)) lanes.set(key, { project: issue.project, status: issue.status, entries: [] });
    lanes.get(key).entries.push({ issue, index });
  });
  lanes.forEach((lane) => {
    lane.entries.sort(compareKanbanIssueEntriesByOrder);
    lane.entries.forEach((entry, index) => {
      entry.issue.order = (index + 1) * KANBAN_ORDER_STEP;
    });
  });
}

function nextKanbanLaneOrder(project, status, options = {}) {
  const lane = sortedKanbanLaneIssues(project, status, options);
  if (!lane.length) return KANBAN_ORDER_STEP;
  return Math.max(...lane.map((issue, index) => issueKanbanOrder(issue, index))) + KANBAN_ORDER_STEP;
}

function insertIssueIntoKanbanLane(issue, newStatus, options = {}) {
  if (!issue || !ISSUE_STATUS_LABELS[newStatus]) return false;
  const oldProject = issue.project;
  const oldStatus = issue.status;
  const hasPlacement = !!(options.position || options.beforeId || options.afterId);
  if (oldStatus === newStatus && !hasPlacement) return false;

  const targetLane = sortedKanbanLaneIssues(issue.project, newStatus, { excludeId: issue.id });
  let insertIndex = targetLane.length;
  if (options.position === "top") {
    insertIndex = 0;
  } else if (options.position === "bottom") {
    insertIndex = targetLane.length;
  } else if (options.beforeId) {
    const index = recordIndexById(targetLane, options.beforeId);
    if (index >= 0) insertIndex = index;
  } else if (options.afterId) {
    const index = recordIndexById(targetLane, options.afterId);
    if (index >= 0) insertIndex = index + 1;
  }

  issue.status = newStatus;
  const orderedTargetLane = [...targetLane];
  orderedTargetLane.splice(Math.max(0, Math.min(insertIndex, orderedTargetLane.length)), 0, issue);
  resequenceKanbanLane(issue.project, newStatus, orderedTargetLane);
  if (oldProject !== issue.project || oldStatus !== newStatus) {
    resequenceKanbanLane(oldProject, oldStatus);
  }
  return true;
}

function openIssueModal(arg) {
  const i = editableModalRecord(arg);
  const projOptions = projectOptionsHTML(i ? i.project : "", i ? "" : dashboard.currentProjectId);
  const teamOptions = teamMemberOptionsHTML(i ? i.assignee : "");
  const statusOptions = keyedOptionsHTML(ISSUE_STATUS_ORDER, ISSUE_STATUS_LABELS, i ? i.status : "", i ? "" : "todo");
  const prioOptions = keyedOptionsHTML(ISSUE_PRIORITY_ORDER, ISSUE_PRIORITY_MAP, i ? i.priority : "", i ? "" : "med");
  const form = html`
    <form id="issueForm" class="modal-form">
      <label>제목
        <input type="text" name="title" required maxlength="120" value="${i ? i.title : ""}" placeholder="예: API 응답 속도 개선" />
      </label>
      <div class="form-row">
        <label>프로젝트
          <select name="project">${raw(projOptions)}</select>
        </label>
        <label>상태
          <select name="status">${raw(statusOptions)}</select>
        </label>
      </div>
      <div class="form-row">
        <label>우선순위
          <select name="priority">${raw(prioOptions)}</select>
        </label>
        <label>담당
          <select name="assignee">${raw(teamOptions)}</select>
        </label>
      </div>
      <div class="form-row">
        <label>마감일
          <input type="date" name="due" value="${i && i.due ? i.due : ""}" />
        </label>
        <label>추정 (시간)
          <input type="number" name="estimate" min="0" value="${i ? i.estimate : 1}" />
        </label>
      </div>
      <label>라벨 (쉼표 구분)
        <input type="text" name="labels" maxlength="200" value="${i ? i.labels.join(", ") : ""}" placeholder="예: backend, perf" />
      </label>
      ${i ? raw(modalDeleteButtonHTML({ action: "issue-delete", dataAttr: "data-issue-id", dataValue: i.id, label: "이 이슈 삭제", title: `${i.id} 이슈 삭제`, ariaLabel: `${i.id} 이슈 삭제` })) : ""}
    </form>
  `;
  openModal(i ? `이슈 편집: ${i.id}` : "새 이슈", form, () => saveIssueFromForm(i ? i.id : null));
}

function saveIssueFromForm(id) {
  const form = nodeQuery(document, "#issueForm");
  if (!form) return false;
  const data = new FormData(form);
  const title = formText(data, "title");
  if (!title) { showToast("제목을 입력하세요", "warn"); return false; }
  const project = (data.get("project") || "").toString();
  if (!project) { showToast("프로젝트를 선택하세요", "warn"); return false; }
  const status = (data.get("status") || "todo").toString();
  const priority = (data.get("priority") || "med").toString();
  const assignee = (data.get("assignee") || "").toString();
  const due = (data.get("due") || "").toString() || null;
  const estimate = clampNumber(data.get("estimate"), 0, 999, 1);
  const labelsRaw = (data.get("labels") || "").toString();
  const labels = labelsRaw ? labelsRaw.split(",").map((l) => l.trim()).filter(Boolean) : [];
  if (id) {
    const issue = indexes.issueById.get(id);
    if (issue) {
      const oldProject = issue.project;
      const oldStatus = issue.status;
      Object.assign(issue, { title, project, status, priority, assignee, due, estimate, labels });
      if (oldProject !== project || oldStatus !== status) {
        issue.order = nextKanbanLaneOrder(project, status, { excludeId: issue.id });
        resequenceKanbanLane(oldProject, oldStatus);
        resequenceKanbanLane(project, status);
      }
    }
    showToast("이슈를 수정했습니다", "info");
  } else {
    const newId = uid("issue");
    dashboard.issues.push({ id: newId, project, title, status, priority, assignee, labels, due, estimate, order: nextKanbanLaneOrder(project, status) });
    showToast("이슈를 추가했습니다", "info");
  }
  rebuildIndexes();
  commit();
  return true;
}

function deleteIssue(id) {
  const issue = indexes.issueById.get(id);
  if (!issue) return;
  const idx = issueIndexById(id);
  const removed = idx >= 0 ? cloneRecord(dashboard.issues[idx]) : cloneRecord(issue);
  const deletedEntryId = captureDeletedItem("issue", removed, { index: idx });
  if (idx >= 0) dashboard.issues.splice(idx, 1);
  rebuildIndexes();
  closeModal();
  commit();
  showUndoToast("이슈를 삭제했습니다", () => {
    if (!canUndoDeletedItem(deletedEntryId)) return;
    if (!restoreDeletedArrayItem(dashboard.issues, idx, removed)) return;
    dropDeletedItem(deletedEntryId);
    rebuildIndexes();
    commit();
    showToast("이슈 삭제를 되돌렸습니다", "info");
  });
}

function moveIssue(id, newStatus, options = {}) {
  const issue = indexes.issueById.get(id);
  if (!issue) return;
  if (!ISSUE_STATUS_LABELS[newStatus]) return;
  const oldStatus = issue.status;
  const moved = insertIssueIntoKanbanLane(issue, newStatus, options);
  if (!moved) return;
  const orderLabel = options.position === "top" ? "맨 위" : options.position === "bottom" ? "맨 아래" : "지정한 위치";
  showToast(oldStatus === newStatus ? `이슈 순서를 ${orderLabel}로 변경` : `이슈를 '${ISSUE_STATUS_LABELS[newStatus]}'으로 이동`, "info");
  commit();
}

function moveIssueOrder(id, position) {
  const issue = indexes.issueById.get(id);
  if (!issue) return;
  moveIssue(id, issue.status, { position: position === "top" ? "top" : "bottom" });
}

/* ============================================================
 * Gantt Tasks CRUD
 * ============================================================ */

function openTaskModal(arg, options = {}) {
  const t = editableModalRecord(arg);
  const defaultMilestone = !t && options.defaultMilestone === true;
  const projOptions = projectOptionsHTML(t ? t.project : "");
  const teamOptions = teamMemberOptionsHTML(t ? t.owner : "");
  const colorOptions = keyedOptionsHTML(TASK_COLOR_ORDER, TASK_COLOR_MAP, t ? t.color : "", t ? "" : "blue");
  // deps: multi-select existing tasks (exclude self)
  const depSet = new Set(t ? t.deps : []);
  const otherTasks = dashboard.gantt.tasks.filter((x) => !t || x.id !== t.id);
  const depsHTML = otherTasks.length ? html`
    <label>의존 작업 (복수 선택 가능)
      <select name="deps" multiple size="${Math.min(6, otherTasks.length)}" class="pm-multi-select">
        ${raw(optionListHTML(otherTasks, (x) => x.id, (x) => `${x.name} (${x.id})`, (x) => depSet.has(x.id)))}
      </select>
    </label>
  ` : "";
  const form = html`
    <form id="taskForm" class="modal-form">
      <label>이름
        <input type="text" name="name" required maxlength="80" value="${t ? t.name : ""}" placeholder="예: API 구현" />
      </label>
      <div class="form-row">
        <label>프로젝트
          <select name="project">${raw(projOptions)}</select>
        </label>
        <label>담당
          <select name="owner">${raw(teamOptions)}</select>
        </label>
      </div>
      <div class="form-row">
        <label>시작일
          <input type="date" name="start" required value="${t ? t.start : ""}" />
        </label>
        <label>종료일
          <input type="date" name="end" required value="${t ? t.end : ""}" />
        </label>
      </div>
      <div class="form-row">
        <label>색상
          <select name="color">${raw(colorOptions)}</select>
        </label>
        <label class="check-inline" style="align-self:flex-end">
          <input type="checkbox" name="milestone" ${raw((t && t.milestone) || defaultMilestone ? "checked" : "")} /> 마일스톤
        </label>
      </div>
      ${raw(depsHTML)}
      ${t ? raw(modalDeleteButtonHTML({ action: "task-delete", dataAttr: "data-task-id", dataValue: t.id, label: "이 작업 삭제" })) : ""}
    </form>
  `;
  openModal(t ? `작업 편집: ${t.name}` : "새 작업 추가", form, () => saveTaskFromForm(t ? t.id : null));
}

function saveTaskFromForm(id) {
  const form = nodeQuery(document, "#taskForm");
  if (!form) return false;
  const data = new FormData(form);
  const name = formText(data, "name");
  if (!name) { showToast("이름을 입력하세요", "warn"); return false; }
  const project = (data.get("project") || "").toString();
  const owner = (data.get("owner") || "").toString();
  let start = (data.get("start") || "").toString();
  let end = (data.get("end") || "").toString();
  if (!start) { showToast("시작일을 입력하세요", "warn"); return false; }
  if (!end) { showToast("종료일을 입력하세요", "warn"); return false; }
  if (end < start) { const tmp = start; start = end; end = tmp; }
  const color = (data.get("color") || "blue").toString();
  const milestone = data.get("milestone") === "on";
  const deps = data.getAll("deps");
  if (id) {
    const task = taskById(id);
    if (task) Object.assign(task, { name, project, owner, start, end, color, milestone, deps });
    showToast("작업을 수정했습니다", "info");
  } else {
    const newId = uid("T");
    dashboard.gantt.tasks.push({ id: newId, project, name, start, end, owner, deps, milestone, color });
    showToast("작업을 추가했습니다", "info");
  }
  commit();
  return true;
}

function deleteTask(id) {
  const task = taskById(id);
  if (!task) return;
  const idx = taskIndexById(id);
  const removed = cloneRecord(task);
  const previousDeps = dashboard.gantt.tasks.map((x) => ({
    id: x.id,
    deps: Array.isArray(x.deps) ? [...x.deps] : [],
  }));
  const deletedEntryId = captureDeletedItem("task", removed, { index: idx, previousDeps });
  dashboard.gantt.tasks = dashboard.gantt.tasks.filter((x) => x.id !== id);
  // 다른 작업의 deps 에서도 제거
  dashboard.gantt.tasks.forEach((x) => { x.deps = (x.deps || []).filter((d) => d !== id); });
  closeModal();
  commit();
  showUndoToast("작업을 삭제했습니다", () => {
    if (!canUndoDeletedItem(deletedEntryId)) return;
    if (!restoreDeletedArrayItem(dashboard.gantt.tasks, idx, removed)) return;
    dropDeletedItem(deletedEntryId);
    previousDeps.forEach((entry) => {
      const next = taskById(entry.id);
      if (next) next.deps = [...entry.deps];
    });
    commit();
    showToast("작업 삭제를 되돌렸습니다", "info");
  });
}

/* ============================================================
 * Team Members CRUD
 * ============================================================ */

function openMemberModal(arg) {
  const m = editableModalRecord(arg);
  const projChecked = new Set(m ? m.projects : []);
  const form = html`
    <form id="memberForm" class="modal-form">
      <div class="form-row">
        <label>이름
          <input type="text" name="name" required maxlength="40" value="${m ? m.name : ""}" placeholder="예: 홍길동" />
        </label>
        <label>역할
          <input type="text" name="role" maxlength="40" value="${m ? m.role : ""}" placeholder="예: Backend" />
        </label>
      </div>
      <div class="form-row">
        <label>부하 (0-100)
          <input type="number" name="load" min="0" max="100" value="${m ? m.load : 0}" />
        </label>
        <label class="check-inline" style="align-self:flex-end">
          <input type="checkbox" name="onLeave" ${raw(m && m.onLeave ? "checked" : "")} /> 휴가 중
        </label>
      </div>
      <label>담당 프로젝트
        <div class="pm-checkbox-group">
          ${raw(checkboxList(dashboard.projects, "id", (p) => p.name, projChecked, "projects"))}
        </div>
      </label>
      ${m ? raw(modalDeleteButtonHTML({ action: "member-delete", dataAttr: "data-member-id", dataValue: m.id, label: "이 멤버 삭제" })) : ""}
    </form>
  `;
  openModal(m ? `멤버 편집: ${m.name}` : "새 멤버 추가", form, () => saveMemberFromForm(m ? m.id : null));
}

function saveMemberFromForm(id) {
  const form = nodeQuery(document, "#memberForm");
  if (!form) return false;
  const data = new FormData(form);
  const name = formText(data, "name");
  if (!name) { showToast("이름을 입력하세요", "warn"); return false; }
  const role = formText(data, "role");
  const load = clampInteger(data.get("load"), 0, 100);
  const onLeave = data.get("onLeave") === "on";
  const projects = data.getAll("projects");
  if (id) {
    const m = indexes.teamById.get(id);
    if (m) {
      const oldProjects = [...m.projects];
      Object.assign(m, { name, role, load, onLeave, projects });
      // 프로젝트 members 목록도 동기화
      oldProjects.forEach((pid) => {
        const p = indexes.projectById.get(pid);
        if (p) p.members = p.members.filter((mid) => mid !== id);
      });
      projects.forEach((pid) => {
        const p = indexes.projectById.get(pid);
        if (p && !p.members.includes(id)) p.members.push(id);
      });
    }
    showToast(`멤버 '${name}' 수정`, "info");
  } else {
    const newId = uid("m");
    const member = { id: newId, name, role, load, projects, onLeave };
    dashboard.team.push(member);
    // 프로젝트 members 목록에 추가
    projects.forEach((pid) => {
      const p = indexes.projectById.get(pid);
      if (p && !p.members.includes(newId)) p.members.push(newId);
    });
    showToast(`멤버 '${name}' 추가`, "info");
  }
  rebuildIndexes();
  commit();
  return true;
}

function deleteMember(id) {
  const m = indexes.teamById.get(id);
  if (!m) return;
  openModal("멤버 삭제", html`
    <div class="modal-confirm-body">
      <p>멤버 <strong>${m.name}</strong>을(를) 삭제합니다.</p>
      <p class="muted-note">이 멤버가 담당인 이슈 및 간트 작업의 담당자가 초기화됩니다.</p>
    </div>
  `, () => {
    // 이슈 담당자 초기화
    dashboard.issues.forEach((i) => { if (i.assignee === id) i.assignee = ""; });
    // 간트 작업 owner 초기화
    dashboard.gantt.tasks.forEach((t) => { if (t.owner === id) t.owner = ""; });
    // 프로젝트 members에서 제거
    dashboard.projects.forEach((p) => { p.members = p.members.filter((mid) => mid !== id); });
    // 팀원 삭제
    const idx = memberIndexById(id);
    if (idx >= 0) dashboard.team.splice(idx, 1);
    rebuildIndexes();
    closeModal();
    showToast(`멤버 '${m.name}' 삭제`, "info");
    commit();
    return true;
  });
}

/* ============================================================
 * DB CRUD — delegated to db-catalog.js
 * ============================================================ */

/* ============================================================
 * Actions
 * ============================================================ */

const MODAL_ACTION_HANDLERS = new Map([
  ["modal-confirm", () => {
    const cb = state.modalOnConfirm;
    if (typeof cb === "function") {
      if (cb() !== false) closeModal();
      return;
    }
    closeModal();
  }],
]);

const APP_SHELL_ACTION_HANDLERS = new Map([
  ["close-palette", () => commandPaletteCall("close")],
  ["close-sheet", closeSheet],
  ["close-modal", closeModal],
  ["open-new-project", openNewProjectModal],
  ["open-notifications", openNotificationsSheet],
  ["open-global-help", openGlobalHelpSheet],
  ["open-data-safety-status", openDataSafetyStatusSheet],
  ["data-safety-nav", (target) => {
    closeSheet({ restoreFocus: false });
    setView(target.dataset.view);
  }],
  ["data-safety-refresh", () => {
    refreshStorageHealth({ render: true }).then(() => {
      if (isDataSafetyStatusSheetOpen()) openDataSafetyStatusSheet();
    }).catch(() => {});
  }],
  ["global-help-open-palette", () => {
    closeSheet({ restoreFocus: false });
    commandPaletteCall("open");
  }],
  ["global-help-nav", (target) => {
    closeSheet({ restoreFocus: false });
    setView(target.dataset.view);
  }],
  ["global-help-search-recovery", () => {
    closeSheet({ restoreFocus: false });
    if (isSearchInertView()) commandPaletteCall("open");
    else if (refs.query) {
      refs.query.focus();
      showToast("현재 뷰 검색이 준비되었습니다", "info");
    }
  }],
  ["dashboard-autoresearch-run", () => runDashboardAutoresearchLoop()],
  ["dashboard-autoresearch-start", startDashboardAutoresearchLoop],
  ["dashboard-autoresearch-stop", stopDashboardAutoresearchLoop],
  ["request-notif-permission", () => {
    try {
      if ("Notification" in window && Notification.permission === "default") {
        Notification.requestPermission().then((perm) => {
          if (perm === "granted") {
            showToast("브라우저 알림 권한이 허용되었습니다", "info");
            eventReminderCall("start");
          } else {
            showToast("알림 권한이 거부되었습니다", "warn");
          }
        }).catch(() => {});
      }
    } catch (_) {}
  }],
  ["nav-to", (target) => setView(target.dataset.view)],
  ["open-palette", () => commandPaletteCall("open")],
  ["clear-search", () => globalSearchCall("clear")],
  ["toggle-theme", toggleTheme],
  ["set-theme", (target) => setTheme(target.dataset.theme)],
  ["toggle-reference-projects", toggleReferenceProjects],
  ["toggle-project-picker", () => projectPickerCall("toggle")],
  ["pick-project", (target) => pickProject(target.dataset.projectId)],
]);

const LLM_WIKI_ACTION_HANDLERS = new Map([
  ["llm-wiki-cat", (target) => selectLlmWiki(target.dataset.cat || null, null)],
  ["llm-wiki-open", (target) => selectLlmWiki(target.dataset.cat || null, target.dataset.article || null)],
  ["llm-wiki-action-filter", (target) => setLlmWikiActionFilter(target.dataset.wikiActionFilter || "all")],
  ["llm-wiki-create-todo", (target) => createLlmWikiTodoDraft(target.dataset.cat || null, target.dataset.article || null)],
  ["llm-wiki-create-note", (target) => createLlmWikiNoteDraft(target.dataset.cat || null, target.dataset.article || null)],
  ["llm-wiki-create-issue", (target) => createLlmWikiIssueDraft(target.dataset.cat || null, target.dataset.article || null)],
  ["open-llm-wiki-source", (target) => openLlmWikiSourceFromRecord(target.dataset.sourceRecordKind, target.dataset.sourceRecordId, target.dataset.sourceKey)],
  ["open-review-record-source", (target) => openReviewSourceFromRecord(target.dataset.sourceRecordKind, target.dataset.sourceRecordId, target.dataset.sourceKey)],
]);

const CALENDAR_ACTION_HANDLERS = new Map([
  ["cal-prev", () => calNav(-1)],
  ["cal-next", () => calNav(1)],
  ["cal-today", calToday],
  ["cal-mode", (target) => setCalendarMode(target.dataset.mode)],
  ["cal-open-day", (target) => calSelectDay(target.dataset.date, { focus: true })],
  ["cal-add", (target) => openEventModal(target.dataset.date || null)],
  ["open-event", (target) => openEventModal(eventById(target.dataset.eventId))],
  ["delete-event", (target) => deleteEvent(target.dataset.eventId)],
  ["skip-occurrence", (target) => skipOccurrence(target.dataset.eventId, target.dataset.date)],
]);

const TODO_ACTION_HANDLERS = new Map([
  ["todo-add", () => openTodoModal(null)],
  ["open-todo", (target) => openTodoModal(todoById(target.dataset.todoId))],
  ["todo-quick-add", quickAddTodo],
  ["home-todo-quick-add", (target) => quickAddTodo(target, { refocusSelector: "#view-home .home-quickadd input[name=title]" })],
  ["home-execution-bucket-filter", (target) => setHomeExecutionBucketFilter(target.dataset.homeExecutionBucketKey)],
  ["todo-filter", (target) => setTodoFilter(target.dataset.filter)],
  ["todo-source-filter", (target) => setTodoSourceFilter(target.dataset.todoSourceFilter)],
  ["todo-toggle", (target) => toggleTodo(target.dataset.todoId)],
  ["todo-delete", (target) => deleteTodo(target.dataset.todoId)],
  ["delete-todo", (target) => deleteTodo(target.dataset.todoId)],
]);

const HOME_EXECUTION_QUICK_ACTION_HANDLERS = new Map([
  ["home-execution-todo-complete", (target) => completeHomeExecutionTodo(target.dataset.todoId)],
  ["home-execution-issue-next", (target) => advanceHomeExecutionIssue(target.dataset.issueId, target.dataset.status)],
]);

const NOTE_ACTION_HANDLERS = new Map([
  ["note-add", () => openNoteModal(null)],
  ["open-note", (target) => openNoteModal(noteById(target.dataset.noteId))],
  ["note-source-filter", (target) => setNoteSourceFilter(target.dataset.noteSourceFilter)],
  ["note-pin", (target) => togglePin(target.dataset.noteId)],
  ["note-delete", (target) => deleteNote(target.dataset.noteId)],
  ["delete-note", (target) => deleteNote(target.dataset.noteId)],
]);

const HABIT_ACTION_HANDLERS = new Map([
  ["habit-add", () => openHabitModal(null)],
  ["open-habit", (target) => openHabitModal(habitById(target.dataset.habitId))],
  ["habit-toggle", (target) => toggleHabit(target.dataset.habitId, target.dataset.date)],
  ["habit-delete", (target) => deleteHabit(target.dataset.habitId)],
]);

const SETTINGS_STORAGE_ACTION_HANDLERS = new Map([
  ["export-data", exportData],
  ["reset-data", confirmResetData],
  ["restore-deleted-item", (target) => restoreDeletedItem(target.dataset.deletedId)],
  ["restore-all-deleted-items", restoreAllDeletedItems],
  ["discard-deleted-item", (target) => discardDeletedItem(target.dataset.deletedId)],
  ["clear-deleted-items", confirmClearDeletedItems],
  ["clear-deleted-recovery-filter", clearDeletedRecoveryFilter],
  ["save-settings", saveSettingsFromForm],
  ["refresh-storage-health", () => refreshStorageHealth({ render: true })],
  ["request-storage-persistence", requestStoragePersistence],
]);

const PORTFOLIO_ACTION_HANDLERS = new Map([
  ["portfolio-filter", (target) => setPortfolioFilter(target.dataset.filter)],
  ["portfolio-action-filter", (target) => setPortfolioActionFilter(target.dataset.actionFilter)],
  ["portfolio-benchmark-filter", (target) => setPortfolioBenchmarkFilter(target.dataset.benchmarkFilter)],
  ["show-project-prompt-handoff", (target) => showProjectPromptHandoff(targetDatasetId(target, "projectId"))],
]);

const KANBAN_ACTION_HANDLERS = new Map([
  ["filter-kanban", (target) => setKanbanFilter(target.dataset.priority)],
  ["filter-kanban-source", (target) => setKanbanSourceFilter(target.dataset.kanbanSourceFilter)],
  ["kanban-density", (target) => setKanbanDensity(target.dataset.kanbanDensity)],
]);

const DB_CATALOG_ACTION_HANDLERS = new Map([
  ["db-catalog-filter", (target) => dbCatalogCall("setDbCatalogFilter", target.dataset.dbCatalogFilterOption)],
  ["db-catalog-create-stale-issue", createDbCatalogStaleReviewIssue],
]);

const CREATE_MODAL_ACTION_HANDLERS = new Map([
  ["project-add", () => openProjectModal(null)],
  ["issue-add", () => openIssueModal(null)],
  ["task-add", (target) => openTaskModal(null, { defaultMilestone: target.dataset.defaultMilestone === "true" })],
  ["member-add", () => openMemberModal(null)],
  ["instance-add", () => dbCatalogCall("openInstanceModal", null)],
  ["table-add", () => dbCatalogCall("openTableModal", null)],
  ["column-add", (target) => dbCatalogCall("openColumnModal", target.dataset.tableId, null)],
  ["query-add", () => dbCatalogCall("openQueryModal", null)],
  ["migration-add", () => dbCatalogCall("openMigrationModal", null)],
]);

function targetDatasetId(target, key) {
  return target.dataset[key] || target.dataset.target;
}

function withTargetColumnIndex(target, callback) {
  const tid = target.dataset.tableId;
  const ci = Number(target.dataset.colIndex);
  if (!Number.isInteger(ci) || ci < 0) { showToast("컬럼 정보를 찾을 수 없습니다", "warn"); return; }
  callback(tid, ci);
}

const PM_CRUD_ACTION_HANDLERS = new Map([
  ["project-edit", (target) => {
    const pid = targetDatasetId(target, "projectId");
    closeSheet();
    openProjectModal(indexes.projectById.get(pid));
  }],
  ["project-delete", (target) => {
    const pid = targetDatasetId(target, "projectId");
    closeModal(); closeSheet(); deleteProject(pid);
  }],
  ["issue-edit", (target) => {
    const iid = targetDatasetId(target, "issueId");
    closeSheet();
    openIssueModal(indexes.issueById.get(iid));
  }],
  ["issue-delete", (target) => {
    const iid = targetDatasetId(target, "issueId");
    closeSheet(); deleteIssue(iid);
  }],
  ["issue-move", (target) => moveIssue(target.dataset.issueId, target.dataset.status)],
  ["issue-order", (target) => moveIssueOrder(target.dataset.issueId, target.dataset.position)],
  ["task-edit", (target) => {
    const tid = targetDatasetId(target, "taskId");
    closeSheet();
    openTaskModal(taskById(tid));
  }],
  ["task-delete", (target) => {
    const tid = targetDatasetId(target, "taskId");
    closeSheet(); deleteTask(tid);
  }],
  ["member-edit", (target) => {
    const mid = targetDatasetId(target, "memberId");
    closeSheet();
    openMemberModal(indexes.teamById.get(mid));
  }],
  ["member-delete", (target) => {
    const mid = targetDatasetId(target, "memberId");
    closeSheet(); deleteMember(mid);
  }],
]);

const DB_CRUD_ACTION_HANDLERS = new Map([
  ["instance-edit", (target) => {
    const iid = targetDatasetId(target, "instanceId");
    closeSheet();
    dbCatalogCall("openInstanceModal", indexes.instanceById.get(iid));
  }],
  ["instance-delete", (target) => {
    const iid = targetDatasetId(target, "instanceId");
    closeModal(); closeSheet(); dbCatalogCall("deleteInstance", iid);
  }],
  ["table-edit", (target) => {
    const tid = targetDatasetId(target, "tableId");
    closeSheet();
    const ctx = dbCatalogCall("findTableById", tid);
    dbCatalogCall("openTableModal", ctx ? ctx.table : null);
  }],
  ["table-delete", (target) => {
    const tid = targetDatasetId(target, "tableId");
    closeModal(); dbCatalogCall("deleteTable", tid);
  }],
  ["column-edit", (target) => withTargetColumnIndex(target, (tid, ci) => {
    closeModal();
    dbCatalogCall("openColumnModal", tid, ci);
  })],
  ["column-delete", (target) => withTargetColumnIndex(target, (tid, ci) => {
    dbCatalogCall("deleteColumn", tid, ci);
  })],
  ["query-edit", (target) => {
    const qid = targetDatasetId(target, "queryId");
    closeSheet();
    dbCatalogCall("openQueryModal", queryById(qid));
  }],
  ["query-delete", (target) => {
    const qid = targetDatasetId(target, "queryId");
    closeModal(); dbCatalogCall("deleteQuery", qid);
  }],
  ["migration-edit", (target) => {
    const mid = targetDatasetId(target, "migId");
    closeSheet();
    dbCatalogCall("openMigrationModal", migrationById(mid));
  }],
  ["migration-delete", (target) => {
    const mid = targetDatasetId(target, "migId");
    closeModal(); dbCatalogCall("deleteMigration", mid);
  }],
]);

const OPERATIONS_COPY_ACTION_HANDLERS = new Map([
  ["copy-settings-handoff", copySettingsHandoff],
  ["copy-system-publish-handoff", copySystemPublishHandoff],
  ["copy-publish-evidence-share-update", copyPublishEvidenceShareUpdate],
  ["copy-publish-launch-announcement", copyPublishLaunchAnnouncement],
  ["copy-publish-post-launch-receipt", copyPublishPostLaunchReceipt],
  ["copy-publish-launch-proof-receipt", copyPublishLaunchProofReceipt],
  ["copy-remote-workflow-install-packet", copyRemoteWorkflowInstallPacket],
  ["copy-workflow-ui-install-receipt", copyWorkflowUiInstallReceipt],
  ["copy-home-launch-blocker-resolver", copyHomeLaunchBlockerResolver],
  ["copy-home-launch-action-checklist", copyHomeLaunchActionChecklist],
  ["copy-post-install-evidence-intake", copyPostInstallEvidenceIntake],
  ["copy-post-install-proof-parser-summary", copyPostInstallProofParserSummary],
  ["copy-publish-workflow-scope-packet", copyPublishWorkflowScopePacket],
  ["copy-launch-execution-packet", copyLaunchExecutionPacket],
  ["copy-launch-current-action-packet", copyLaunchCurrentActionPacket],
  ["copy-launch-operator-one-page", copyLaunchOperatorOnePage],
  ["copy-launch-readiness-refresh-receipt", copyLaunchReadinessRefreshReceipt],
  ["copy-verify-workspace-summary-receipt", copyVerifyWorkspaceSummaryReceipt],
  ["copy-release-gate-cache-repair", copyReleaseGateCacheRepair],
  ["copy-release-provenance-receipt", copyReleaseProvenanceReceipt],
  ["copy-pages-attestation-proof-intake", copyPagesAttestationProofIntake],
  ["copy-output-quality-audit-receipt", copyOutputQualityAuditReceipt],
  ["copy-output-quality-external-claim-guard", copyOutputQualityExternalClaimGuard],
  ["copy-dashboard-decision-receipt", copyDashboardDecisionReceipt],
]);

const OPERATIONS_PARSER_ACTION_HANDLERS = new Map([
  ["parse-post-install-proof", (target) => updatePostInstallProofParser(postInstallProofParserNode(target) || document)],
]);

const REVIEW_COPY_ACTION_HANDLERS = new Map([
  ["copy-review-handoff", copyBenchmarkReviewHandoff],
  ["copy-review-bundle", copyReviewPackageBundle],
  ["copy-review-paste-body", copyReviewPackagePasteBody],
  ["copy-review-tracker-fields", copyReviewPackageTrackerFields],
  ["copy-review-tracker-form", copyReviewPackageTrackerForm],
  ["copy-review-submit-sequence", copyReviewPackageSubmitSequence],
  ["copy-review-external-receipt-template", copyReviewPackageExternalReceiptTemplate],
  ["copy-review-external-receipt-filled", copyReviewPackageExternalReceiptFilled],
  ["copy-review-submission-update-filled", copyReviewPackageSubmissionUpdateFilled],
  ["copy-review-artifact-receipt", copyReviewArtifactReceipt],
  ["copy-review-artifact-repair-body", (target) => copyReviewArtifactRepairPayload(target, "body")],
  ["copy-review-artifact-repair-receipt", (target) => copyReviewArtifactRepairPayload(target, "receipt")],
  ["copy-review-artifact-post-apply-receipt", copyReviewArtifactPostApplyReceipt],
  ["copy-review-post-repair-artifact-link", copyReviewPostRepairArtifactLink],
  ["copy-issue-fresh-receipt", copyIssueFreshReceipt],
  ["copy-review-result-repair", copyReviewResultRepair],
  ["copy-review-result-repair-receipt", copyReviewResultRepairReceipt],
  ["copy-review-github-comment", copyReviewGithubComment],
]);

const REVIEW_VALIDATION_ACTION_HANDLERS = new Map([
  ["preview-review-artifact-repair-apply", reviewArtifactRepairPreview],
  ["undo-review-artifact-repair", undoReviewArtifactRepair],
  ["insert-review-artifact-receipt", insertReviewArtifactReceipt],
  ["compare-review-artifact-receipt", compareReviewArtifactReceipt],
  ["clear-review-artifact-receipt", clearReviewArtifactReceipt],
  ["insert-review-result-example", insertReviewResultExample],
  ["validate-review-result", validateReviewResult],
  ["clear-review-result", clearReviewResult],
]);

const REVIEW_EXECUTION_ACTION_HANDLERS = new Map([
  ["create-review-issue", createBenchmarkReviewIssue],
  ["publish-review-note", publishReviewHandoffNote],
  ["toggle-issue-checklist", (target) => toggleIssueChecklistItem(target.dataset.issueId, target.dataset.checklistId, { reopenSheet: !!target.closest("#sheet") })],
]);

const RECORD_OPEN_ACTION_HANDLERS = new Map([
  ["open-project", (target) => openProjectSheet(target.dataset.projectId)],
  ["open-source-backlink-issue", (target) => openIssueSourceBacklink(target.dataset.issueId)],
  ["open-source-backlink-record", (target) => openLlmWikiRecordBacklink(target.dataset.sourceRecordKind, target.dataset.sourceRecordId)],
  ["open-issue-source", (target) => openIssueSource(target.dataset.target || target.dataset.issueId)],
  ["open-issue", (target) => openIssueSheet(target.dataset.issueId)],
  ["open-task", (target) => openTaskSheet(target.dataset.taskId)],
  ["open-member", (target) => openMemberSheet(target.dataset.memberId)],
  ["pick-instance", (target) => pickInstance(target.dataset.instanceId)],
  ["open-table", (target) => openTableSheet(target.dataset.tableId)],
  ["open-query", (target) => openQuerySheet(target.dataset.queryId)],
  ["open-backup", (target) => openBackupSheet(target.dataset.date)],
  ["open-migration", (target) => openMigrationSheet(target.dataset.migId)],
]);

const ACTION_HANDLER_GROUPS = Object.freeze([
  MODAL_ACTION_HANDLERS,
  APP_SHELL_ACTION_HANDLERS,
  LLM_WIKI_ACTION_HANDLERS,
  CALENDAR_ACTION_HANDLERS,
  TODO_ACTION_HANDLERS,
  HOME_EXECUTION_QUICK_ACTION_HANDLERS,
  NOTE_ACTION_HANDLERS,
  HABIT_ACTION_HANDLERS,
  SETTINGS_STORAGE_ACTION_HANDLERS,
  OPERATIONS_COPY_ACTION_HANDLERS,
  OPERATIONS_PARSER_ACTION_HANDLERS,
  RECORD_OPEN_ACTION_HANDLERS,
  PORTFOLIO_ACTION_HANDLERS,
  REVIEW_COPY_ACTION_HANDLERS,
  REVIEW_VALIDATION_ACTION_HANDLERS,
  REVIEW_EXECUTION_ACTION_HANDLERS,
  DB_CATALOG_ACTION_HANDLERS,
  KANBAN_ACTION_HANDLERS,
  CREATE_MODAL_ACTION_HANDLERS,
  PM_CRUD_ACTION_HANDLERS,
  DB_CRUD_ACTION_HANDLERS,
]);

function runActionHandler(action, target, handlers) {
  const handler = handlers.get(action);
  if (!handler) return false;
  try {
    const result = handler(target);
    if (result && typeof result.then === "function") {
      result.catch((error) => handleRuntimeError(error, { source: "action", action }));
    }
  } catch (error) {
    handleRuntimeError(error, { source: "action", action });
  }
  return true;
}

function handleActions(event) {
  const target = event.target.closest("[data-action]");
  if (!target) return;
  const action = target.getAttribute("data-action");
  ACTION_HANDLER_GROUPS.some((handlers) => runActionHandler(action, target, handlers));
}

/* ============================================================
 * Command Palette (Cmd/Ctrl+K) — unified search + commands
 * ============================================================ */

let _palOpen = false;

const commandPaletteHelpers = window.JooParkCommandPalette && typeof window.JooParkCommandPalette.create === "function"
  ? window.JooParkCommandPalette.create({
      document,
      matches,
      escapeHtml,
      clampInteger,
      formatKoreanShort,
      getDashboard: () => dashboard,
      getFuse: () => (typeof Fuse === "function" ? Fuse : null),
      getPreviousFocus: () => state.previousFocus,
      setPreviousFocus: (value) => { state.previousFocus = value; },
      onOpenChange: (open) => { _palOpen = open; },
      setView,
      openEventModal,
      openTodoModal,
      openNoteModal,
      openTodoRecord: openTodoInTodoView,
      openNoteRecord: openNoteInNotesView,
      openHabitModal,
      openProjectModal,
      openIssueModal,
      openIssueRecord: openIssueFromPalette,
      exportData,
      toggleTheme,
      openShortcutHelp: () => keyboardShortcutCall("openHelp"),
      openDeletedRecoveryPanel,
      getLlmWikiContext: currentLlmWikiActionContext,
      createLlmWikiTodoDraft,
      createLlmWikiNoteDraft,
      createLlmWikiIssueDraft,
      openKanbanSourceFilter,
      setKanbanSourceFilter,
      setTodoSourceFilter,
      setNoteSourceFilter,
    })
  : null;

function commandPaletteCall(name, ...args) {
  return callModuleHelper(commandPaletteHelpers, "command palette", name, args, "command palette helper unavailable");
}

const keyboardShortcutHelpers = window.JooParkKeyboardShortcuts && typeof window.JooParkKeyboardShortcuts.create === "function"
  ? window.JooParkKeyboardShortcuts.create({
      document,
      getCurrentView: () => dashboard.currentView,
      getSearchInput: () => refs.query,
      isPaletteOpen: () => _palOpen,
      isSearchInertView,
      escapeHtml,
      openModal,
      openPalette: () => commandPaletteCall("open"),
      closePalette: () => commandPaletteCall("close"),
      projectPickerIsOpen: () => projectPickerCall("isOpen"),
      setProjectPickerOpen: (open) => projectPickerCall("setOpen", open),
      restoreProjectPickerFocus: () => projectPickerCall("restoreFocus"),
      isModalOpen,
      closeModal,
      isSheetOpen,
      closeSheet,
      getOpenDialogRoot,
      trapTab,
      calSelectDay,
      addDaysISO,
      dateFromISO,
      openTaskSheet,
      moveIssueOrder,
      setCalendarMode,
      openEventModal,
      openTodoModal,
      openNoteModal,
      openHabitModal,
      openIssueModal,
      openProjectModal,
      openTaskModal,
      openMemberModal,
      setView,
    })
  : null;

function keyboardShortcutCall(name, ...args) {
  return callModuleHelper(keyboardShortcutHelpers, "keyboard shortcuts", name, args, "keyboard shortcut helper unavailable");
}

const interactionSetupHelpers = window.JooParkInteractionSetup && typeof window.JooParkInteractionSetup.create === "function"
  ? window.JooParkInteractionSetup.create({
      document,
      state,
      handleActions,
      projectPickerIsOpen: () => projectPickerCall("isOpen"),
      closeProjectPickerIfOutside: (target) => projectPickerCall("closeIfOutside", target),
      updateReviewIssueDraftAssignee,
      setDeletedRecoveryKind,
      updatePostInstallProofParser,
      postInstallProofParserNode,
      setDeletedRecoveryQuery,
      isModalOpen,
      closeModal,
    })
  : null;

function interactionSetupCall(name, ...args) {
  return callModuleHelper(interactionSetupHelpers, "interaction setup", name, args, "interaction setup helper unavailable");
}

/* ============================================================
 * Setup
 * ============================================================ */

function isSearchInertView(view = dashboard.currentView) { return globalSearchCall("isInertView", view); }

function syncSearchClearControl() { return globalSearchCall("clearControl"); }

function syncSearchAffordance({ announce = false } = {}) { return globalSearchCall("syncAffordance", { announce }); }

function syncViewFromLocation() {
  const name = routeViewFromLocation(), validHash = (location.hash || "") === `#${name}`;
  if (name !== dashboard.currentView || !validHash) setView(name, { history: validHash ? "none" : "replace" });
}

function setupInteractions() {
  keyboardShortcutCall("setup");
  interactionSetupCall("setup");
  window.addEventListener("hashchange", syncViewFromLocation);
  window.addEventListener("popstate", syncViewFromLocation);
}

const footerClockHelpers = window.JooParkFooterClock && typeof window.JooParkFooterClock.create === "function"
  ? window.JooParkFooterClock.create({ document, getFooterNow: () => refs.footerNow })
  : null;

function footerClockCall(name, ...args) {
  if (!footerClockHelpers || typeof footerClockHelpers[name] !== "function") return null;
  try {
    return footerClockHelpers[name](...args);
  } catch (_) {
    return null;
  }
}

/* ============================================================
 * GitHub snapshot sync (data/repos.json → dashboard.projects)
 * ============================================================ */

async function loadGithubProjects() {
  resetProjectSnapshotHealth();
  const repoSnapshot = await fetchProjectSnapshot("./data/repos.json");
  const adoptionSnapshot = await fetchProjectSnapshot("./data/adoption-candidates.json");
  const snapshot = mergeProjectSnapshots(repoSnapshot, adoptionSnapshot);
  if (!snapshot) {
    finalizeProjectSnapshotHealth({ snapshot, applied: false, appliedReason: "using bundled mock data" });
    console.info("[workspace] project snapshots not loaded (using mock data)");
    return false;
  }
  if (dashboard.imports && dashboard.imports.autoProjectSeedDisabled === true) {
    finalizeProjectSnapshotHealth({ snapshot, applied: false, appliedReason: "auto seed disabled after reset" });
    console.info("[workspace] github snapshot skipped — project auto seed disabled after reset");
    return false;
  }

  if (pmWasPersisted) {
    const changed = mergeImportedProjects(adoptionSnapshot);
    finalizeProjectSnapshotHealth({ snapshot, applied: changed, appliedReason: changed ? "refreshed persisted adoption candidates" : "persisted workspace data kept" });
    if (!changed) console.info("[workspace] github snapshot skipped — user has persisted project data");
    return changed;
  }

  applyGithubSnapshot(snapshot);
  finalizeProjectSnapshotHealth({ snapshot, applied: true, appliedReason: "applied merged project snapshots" });
  return true;
}

async function fetchProjectSnapshot(path) {
  try {
    const res = await fetch(path, { cache: "no-store" });
    if (!res.ok) {
      return projectSnapshotFailure(path, "http-error", `HTTP ${res.status}`);
    }
    const snapshot = await res.json();
    if (!Array.isArray(snapshot.projects) || snapshot.projects.length === 0) {
      return projectSnapshotFailure(path, "invalid-shape", "projects array missing or empty");
    }
    recordProjectSnapshotHealth(path, {
      loaded: true,
      status: "pass",
      projectCount: snapshot.projects.length,
      generatedAt: snapshot.generatedAt || "",
      source: snapshot.source || "",
      importId: snapshot.importId || "",
    });
    return snapshot;
  } catch (err) {
    const failed = projectSnapshotFailure(path, "error", err.message);
    console.info(`[workspace] project snapshot not loaded: ${path}`, err.message);
    return failed;
  }
}

function projectSnapshotFailure(path, status, error) {
  recordProjectSnapshotHealth(path, { loaded: false, status, error });
  return null;
}

function resetProjectSnapshotHealth() {
  state.projectSnapshotHealth = {
    checked: false,
    loaded: false,
    sourceCount: 0,
    loadedCount: 0,
    errorCount: 0,
    projectCount: 0,
    applied: false,
    appliedReason: "checking",
    sources: [],
  };
}

function projectSnapshotSources() {
  return Array.isArray(state.projectSnapshotHealth.sources) ? state.projectSnapshotHealth.sources : [];
}

function recordProjectSnapshotHealth(path, result) {
  const relPath = String(path || "").replace(/^\.\//, "");
  const next = {
    path: relPath,
    loaded: !!result.loaded,
    status: result.status || (result.loaded ? "pass" : "error"),
    projectCount: finiteNumberOr(result.projectCount, 0),
    generatedAt: result.generatedAt || "",
    source: result.source || "",
    importId: result.importId || "",
    error: result.error || "",
  };
  state.projectSnapshotHealth.sources = [...projectSnapshotSources().filter((item) => item.path !== relPath), next];
}

function finalizeProjectSnapshotHealth({ snapshot, applied, appliedReason }) {
  const sources = projectSnapshotSources();
  const loadedCount = sources.filter((item) => item.loaded).length;
  const errorCount = sources.filter((item) => !item.loaded).length;
  state.projectSnapshotHealth = {
    ...state.projectSnapshotHealth,
    checked: true,
    loaded: loadedCount > 0,
    sourceCount: sources.length,
    loadedCount,
    errorCount,
    projectCount: snapshot && Array.isArray(snapshot.projects) ? snapshot.projects.length : 0,
    applied: !!applied,
    appliedReason: appliedReason || "",
    sources,
  };
}

function setEvidenceState(stateKey, { source, loaded, data = null, error = "" }) {
  state[stateKey] = {
    checked: true,
    loaded,
    source,
    data: loaded ? data : null,
    error: loaded ? "" : error,
  };
  return loaded;
}

async function loadJsonEvidenceState({ url, source, stateKey, invalidMessage, validate }) {
  try {
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) {
      return setEvidenceState(stateKey, { source, loaded: false, error: `HTTP ${res.status}` });
    }
    const payload = await res.json();
    const valid = !!validate(payload);
    return setEvidenceState(stateKey, { source, loaded: valid, data: payload, error: invalidMessage });
  } catch (err) {
    return setEvidenceState(stateKey, { source, loaded: false, error: err.message });
  }
}

async function loadPublishEvidence() {
  return loadJsonEvidenceState({
    url: "./data/publish-evidence.json",
    source: "data/publish-evidence.json",
    stateKey: "publishEvidence",
    invalidMessage: "invalid publish evidence shape",
    validate: (evidence) => evidence &&
      evidence.status === "pass" &&
      Array.isArray(evidence.workflowEvidencePlans) &&
      typeof evidence.postPublishEvidenceReady === "boolean",
  });
}

async function loadWorkflowUiInstallPlan() {
  return loadJsonEvidenceState({
    url: "./data/workflow-ui-install-plan.json",
    source: "data/workflow-ui-install-plan.json",
    stateKey: "workflowUiInstallPlan",
    invalidMessage: "invalid workflow install plan shape",
    validate: (plan) => {
      const plans = Array.isArray(plan?.plans) ? plan.plans : [];
      const installRows = Array.isArray(plan?.installReceipt?.installRows) ? plan.installReceipt.installRows : [];
      const noopInstallReceiptReady = installRows.length > 0 &&
        installRows.every((row) => row.installAction === "verified_remote_matches_template" && row.required === false);
      const pastePacketText = plan?.workflowUiInstallPastePacket || plan?.uiPastePacket || plan?.packet || plan?.installReceipt?.text || "";
      const pastePacketReady = plan?.workflowUiInstallPastePacketReady === true || plan?.uiPastePacketReady === true || plan?.packetReady === true || plan?.installReceipt?.ready === true;
      return plan &&
        plan.status === "pass" &&
        plan.workflowUiInstallReady === true &&
        typeof plan.nextVerificationCommand === "string" &&
        plan.installReceipt &&
        plan.installReceipt.ready === true &&
        typeof plan.installReceipt.text === "string" &&
        plan.installReceipt.text.includes("JooPark GitHub UI Workflow Install Receipt") &&
        pastePacketReady &&
        pastePacketText.includes("JooPark GitHub UI Workflow Paste Packet") &&
        pastePacketText.includes("workflowUiInstallReady") &&
        pastePacketText.includes("GitHub new-file form values:") &&
        pastePacketText.includes("githubFileNameFieldValue=.github/workflows/joopark-pages.yml") &&
        pastePacketText.includes("remoteWorkflowVisibilityReady=true") &&
        Number(plan.workflowUiInstallPastePacketCoverage || 0) >= 1 &&
        Number(plan.workflowUiInstallFormFieldCoverage || 0) >= 1 &&
        Number(plan.installReceipt.commandCount || 0) >= (noopInstallReceiptReady ? 4 : 6) &&
        plans.length >= 2 &&
        plans.every((item) => item.githubNewFileUrl && item.githubWorkflowUrl && item.templateCopyCommand && item.githubNewFileOpenCommand && item.githubWorkflowOpenCommand && item.githubFileNameFieldValue && item.suggestedCommitMessage);
    },
  });
}

async function loadPublishDispatchPlan() {
  return loadJsonEvidenceState({
    url: "./data/publish-dispatch-plan.json",
    source: "data/publish-dispatch-plan.json",
    stateKey: "publishDispatchPlan",
    invalidMessage: "invalid publish dispatch plan shape",
    validate: (plan) => {
      const workflowPlans = Array.isArray(plan?.workflowPlans) ? plan.workflowPlans : [];
      return plan &&
        plan.status === "pass" &&
        typeof plan.repoEvidenceReady === "boolean" &&
        typeof plan.dispatchReady === "boolean" &&
        typeof plan.driftDispatchReady === "boolean" &&
        typeof plan.allDispatchReady === "boolean" &&
        typeof plan.nextVerificationCommand === "string" &&
        typeof plan.workflowListCommand === "string" &&
        workflowPlans.length >= 2 &&
        workflowPlans.every((item) => item.workflowFile && item.workflowPath && typeof item.dispatchReady === "boolean" && typeof item.dispatchCommand === "string");
    },
  });
}

async function loadRemoteWorkflowFileCheck() {
  return loadJsonEvidenceState({
    url: "./data/remote-workflow-file-check.json",
    source: "data/remote-workflow-file-check.json",
    stateKey: "remoteWorkflowFileCheck",
    invalidMessage: "invalid remote workflow file check shape",
    validate: (check) => {
      const checks = Array.isArray(check?.checks) ? check.checks : [];
      return check &&
        check.status === "pass" &&
        typeof check.repoEvidenceReady === "boolean" &&
        typeof check.remoteWorkflowFilesChecked === "boolean" &&
        typeof check.remoteWorkflowFilesReady === "boolean" &&
        typeof check.nextVerificationCommand === "string" &&
        typeof check.installPacket === "string" &&
        checks.length >= 2 &&
        checks.every((item) =>
          item.path &&
          typeof item.remoteExists === "boolean" &&
          typeof item.remoteMatchesTemplate === "boolean" &&
          typeof item.templateCopyCommand === "string" &&
          typeof item.githubNewFileOpenCommand === "string"
        );
    },
  });
}

async function loadLaunchExecutionPacket() {
  return loadJsonEvidenceState({
    url: "./data/launch-execution-packet.json",
    source: "data/launch-execution-packet.json",
    stateKey: "launchExecutionPacket",
    invalidMessage: "invalid launch execution packet shape",
    validate: (packet) => {
      const stages = Array.isArray(packet?.stages) ? packet.stages : [];
      const postInstallIntake = packet?.postInstallEvidenceIntake && typeof packet.postInstallEvidenceIntake === "object" ? packet.postInstallEvidenceIntake : {};
      return packet &&
        packet.status === "pass" &&
        typeof packet.packet === "string" &&
        typeof packet.readyToDispatch === "boolean" &&
        typeof packet.launchProofReady === "boolean" &&
        typeof packet.readyForExternalClaim === "boolean" &&
        postInstallIntake.quickProofReady === true &&
        Number(postInstallIntake.quickProofStepCount || 0) === 4 &&
        Number(postInstallIntake.quickProofCoverage || 0) === 1 &&
        postInstallIntake.quickProofFieldMappingReady === true &&
        Number(postInstallIntake.quickProofMappedFieldCount || 0) === 4 &&
        Number(postInstallIntake.quickProofFieldMappingCoverage || 0) === 1 &&
        Array.isArray(postInstallIntake.quickProofFieldMappings) &&
        String(postInstallIntake.quickProofReceipt || "").includes("JooPark Post-Install Quick Proof Receipt") &&
        Array.isArray(packet.externalComparison) &&
        stages.length >= 5 &&
        stages.every((item) => item.key && item.label && item.status && Array.isArray(item.commands));
    },
  });
}

async function loadLaunchReadinessRefresh() {
  return loadJsonEvidenceState({
    url: "./data/launch-readiness-refresh.json",
    source: "data/launch-readiness-refresh.json",
    stateKey: "launchReadinessRefresh",
    invalidMessage: "invalid launch readiness refresh shape",
    validate: (refresh) => refresh &&
      refresh.status === "pass" &&
      Number(refresh.commandCoverage || 0) >= 6 &&
      Array.isArray(refresh.commandRuns) &&
      Array.isArray(refresh.refreshChecklist) &&
      refresh.abComparison &&
      refresh.abComparison.decision === "keep_b" &&
      refresh.evidenceFreshness &&
      typeof refresh.evidenceFreshness.status === "string" &&
      Array.isArray(refresh.evidenceFreshness.sourceArtifacts) &&
      typeof refresh.safeToDispatch === "boolean" &&
      typeof refresh.readyForExternalClaim === "boolean" &&
      refresh.nextAction &&
      typeof refresh.nextAction.command === "string",
  });
}

async function loadVerifyWorkspaceSummary() {
  if (!getVerifyWorkspaceSummaryHelpers()) {
    state.verifyWorkspaceSummary = initialVerifyWorkspaceSummaryState();
    return false;
  }
  const result = await verifyWorkspaceSummaryCall("load");
  state.verifyWorkspaceSummary = result.state;
  return result.valid;
}

async function loadReleaseReadinessSummary() {
  return loadJsonEvidenceState({
    url: "./autoresearch-results/release-readiness-summary.json",
    source: "autoresearch-results/release-readiness-summary.json",
    stateKey: "releaseReadinessSummary",
    invalidMessage: "invalid release readiness summary shape",
    validate: (summary) => {
      const gate = summary?.packagedBrowserGate || summary?.packagedBrowserGates || {};
      const completionAudit = summary?.completionAudit || {};
      return summary &&
        summary.schemaVersion === "joopark-release-readiness-summary/v1" &&
        summary.checks &&
        typeof summary.checks === "object" &&
        completionAudit &&
        typeof completionAudit.status === "string" &&
        typeof completionAudit.launchCompletionAchieved === "boolean" &&
        Array.isArray(completionAudit.blockedSignals) &&
        gate &&
        typeof gate.status === "string" &&
        gate.cache &&
        typeof gate.cache === "object";
    },
  });
}

function provenanceSubjectByName(provenance, name) {
  const subjects = Array.isArray(provenance?.subject) ? provenance.subject : [];
  return subjects.find((item) => item && item.name === name) || null;
}

async function loadReleaseProvenance() {
  const candidates = [
    { url: "./release-provenance.json", source: "release-provenance.json" },
    { url: "./dist/release/release-provenance.json", source: "dist/release/release-provenance.json" },
  ];
  let lastError = "";
  for (const candidate of candidates) {
    try {
      const res = await fetch(candidate.url, { cache: "no-store" });
      if (!res.ok) {
        lastError = `HTTP ${res.status}`;
        continue;
      }
      const provenance = await res.json();
      const predicate = provenance?.predicate || {};
      const buildDefinition = predicate.buildDefinition || {};
      const runDetails = predicate.runDetails || {};
      const jooparkRelease = predicate.joopark_release || {};
      const manifestSubject = provenanceSubjectByName(provenance, "release-manifest.json");
      const dependencies = Array.isArray(buildDefinition.resolvedDependencies)
        ? buildDefinition.resolvedDependencies
        : [];
      const dependencyNames = new Set(dependencies.map((item) => item?.name).filter(Boolean));
      const valid = provenance &&
        provenance._type === "https://in-toto.io/Statement/v1" &&
        provenance.predicateType === "https://slsa.dev/provenance/v1" &&
        manifestSubject?.digest?.sha256 &&
        buildDefinition.buildType === "https://biojuho.local/joopark/static-release/v1" &&
        runDetails.builder?.id === "https://biojuho.local/joopark/local-release-packager" &&
        jooparkRelease.signatureStatus === "unsigned-local-provenance" &&
        jooparkRelease.signed === false &&
        ["source-tree", "index.html", "app.js", "sw.js", "data", "vendor"].every((name) => dependencyNames.has(name));
      return setEvidenceState("releaseProvenance", { source: candidate.source, loaded: valid, data: provenance, error: "invalid release provenance shape" });
    } catch (err) {
      lastError = err.message;
    }
  }
  return setEvidenceState("releaseProvenance", { source: "release-provenance.json", loaded: false, error: lastError || "release provenance not found" });
}

async function loadOutputQualityAudit() {
  return loadJsonEvidenceState({
    url: "./data/output-quality-audit.json",
    source: "data/output-quality-audit.json",
    stateKey: "outputQualityAudit",
    invalidMessage: "invalid output quality audit shape",
    validate: (audit) => audit &&
      audit.status === "pass" &&
      typeof audit.receipt === "string" &&
      Array.isArray(audit.criteria) &&
      Array.isArray(audit.externalComparison) &&
      typeof audit.releaseQualityReady === "boolean" &&
      typeof audit.readyForExternalClaim === "boolean",
  });
}

async function loadGithubProjectDiscovery() {
  return loadJsonEvidenceState({
    url: "./data/github-project-discovery.json",
    source: "data/github-project-discovery.json",
    stateKey: "githubProjectDiscovery",
    invalidMessage: "invalid GitHub project discovery shape",
    validate: (discovery) => discovery &&
      discovery.schemaVersion === "joopark-github-project-discovery/v1" &&
      discovery.status === "pass" &&
      discovery.privacy &&
      discovery.privacy.publicArtifactSafe === true &&
      discovery.privacy.absoluteLocalPathExposure === false &&
      discovery.counts &&
      Number(discovery.counts.rankedProjects || 0) > 0 &&
      Array.isArray(discovery.rankedProjects) &&
      discovery.rankedProjects.length > 0 &&
      discovery.abComparison &&
      discovery.abComparison.decision === "keep_b",
  });
}

function mergeProjectSnapshots(...snapshots) {
  const active = snapshots.filter((snapshot) => snapshot && Array.isArray(snapshot.projects));
  if (active.length === 0) return null;
  const seen = new Set();
  const seenRepos = new Set();
  const projects = [];
  active.forEach((snapshot) => {
    snapshot.projects.forEach((project) => {
      if (!project || !project.id) return;
      const repoKey = projectRepoKey(project);
      if (seen.has(project.id) || (repoKey && seenRepos.has(repoKey))) return;
      seen.add(project.id);
      if (repoKey) seenRepos.add(repoKey);
      projects.push(project);
    });
  });
  return {
    generatedAt: active.map((snapshot) => snapshot.generatedAt).filter(Boolean).join(" + "),
    source: active.map((snapshot) => snapshot.source).filter(Boolean).join(" + "),
    importId: active.map((snapshot) => snapshot.importId).filter(Boolean).pop() || ADOPTION_IMPORT_ID,
    projects,
  };
}

function projectRepoKey(project) {
  if (!project || typeof project !== "object") return "";
  const repoUrl = safeGithubUrl(project.url);
  if (repoUrl) return repoUrl.toLowerCase();
  const repoName = String(project.name || "").trim().toLowerCase();
  return /^[a-z0-9_.-]+\/[a-z0-9_.-]+$/.test(repoName) ? `name:${repoName}` : "";
}

function ensureImportRegistry() {
  if (!dashboard.imports || typeof dashboard.imports !== "object" || Array.isArray(dashboard.imports)) {
    dashboard.imports = {};
  }
  if (!dashboard.imports.projectImports || typeof dashboard.imports.projectImports !== "object" ||
      Array.isArray(dashboard.imports.projectImports)) {
    dashboard.imports.projectImports = {};
  }
  return dashboard.imports.projectImports;
}

function markAppliedProjectImports(projects, importId) {
  const candidates = (Array.isArray(projects) ? projects : [])
    .filter((p) => p && p.id && p.sourceKind === "adoption-candidate")
    .map((p) => p.id);
  if (candidates.length === 0) return false;
  const registry = ensureImportRegistry();
  const key = importId || ADOPTION_IMPORT_ID;
  const applied = new Set(Array.isArray(registry[key]) ? registry[key] : []);
  const before = applied.size;
  candidates.forEach((id) => applied.add(id));
  registry[key] = sortedStrings(applied);
  return applied.size !== before;
}

function mergeImportedProjects(snapshot) {
  if (!snapshot || !Array.isArray(snapshot.projects)) return false;
  const importId = snapshot.importId || ADOPTION_IMPORT_ID;
  const registry = ensureImportRegistry();
  const applied = new Set(Array.isArray(registry[importId]) ? registry[importId] : []);
  const existing = new Set(dashboard.projects.map((p) => p.id));
  let added = 0;
  let updated = 0;
  let registryChanged = false;

  snapshot.projects
    .filter((p) => p && p.id && p.sourceKind === "adoption-candidate")
    .forEach((project) => {
      const repoKey = projectRepoKey(project);
      const matches = dashboard.projects.filter((candidate) =>
        candidate && (candidate.id === project.id || (repoKey && projectRepoKey(candidate) === repoKey))
      );
      if (matches.length > 0) {
        matches.forEach((match) => {
          if (refreshImportedProjectMetadata(match, project)) updated += 1;
        });
        if (!applied.has(project.id)) {
          applied.add(project.id);
          registryChanged = true;
        }
        return;
      }
      if (applied.has(project.id)) return;
      dashboard.projects.push({ ...project, members: Array.isArray(project.members) ? project.members : [] });
      existing.add(project.id);
      applied.add(project.id);
      registryChanged = true;
      added += 1;
    });

  if (!registryChanged && updated === 0) return false;
  registry[importId] = sortedStrings(applied);
  normalizeAllData();
  rebuildIndexes();
  persist();
  if (added > 0) console.info(`[workspace] imported ${added} adoption candidate projects`);
  if (updated > 0) console.info(`[workspace] refreshed ${updated} adoption candidate projects`);
  return added > 0 || updated > 0;
}

function refreshImportedProjectMetadata(target, source) {
  const refreshFields = [
    "sourceKind",
    "adoptionStage",
    "topics",
    "language",
    "color",
    "url",
    "stars",
    "forks",
    "diskKb",
    "pushedAt",
    "createdAt",
    "lastCommit",
    "openIssues",
    "openPRs",
    "mergedPRs",
    "closedIssues",
  ];
  let changed = false;
  refreshFields.forEach((field) => {
    if (typeof source[field] === "undefined") return;
    const next = Array.isArray(source[field]) ? [...source[field]] : source[field];
    const current = target[field];
    const same = Array.isArray(next)
      ? Array.isArray(current) && next.length === current.length && next.every((value, index) => value === current[index])
      : current === next;
    if (same) return;
    target[field] = next;
    changed = true;
  });
  return changed;
}

function applyGithubSnapshot(snapshot) {
  // The remap below mutates issue/task/team project refs in place; running it
  // twice would rewrite already-remapped repo-* ids. Apply at most once.
  if (dashboard.githubMeta) return;
  const repoProjects = snapshot.projects.map((p) => ({ ...p, members: [] }));

  // Map each legacy proj-* id to a real repo id, in order. Anything past the
  // repo count wraps so no mock issue/task is orphaned.
  const oldIds = dashboard.projects.map((p) => p.id);
  const idMap = new Map();
  oldIds.forEach((oid, i) => idMap.set(oid, repoProjects[i % repoProjects.length].id));
  const remap = (id) => idMap.get(id) || id;

  dashboard.issues.forEach((i) => { i.project = remap(i.project); });
  dashboard.gantt.tasks.forEach((t) => { t.project = remap(t.project); });
  dashboard.team.forEach((m) => {
    const seen = new Set();
    m.projects = m.projects.map(remap).filter((v) => (seen.has(v) ? false : (seen.add(v), true)));
  });

  repoProjects.forEach((p) => {
    p.members = dashboard.team.filter((m) => m.projects.includes(p.id)).map((m) => m.id);
    const mockOpen = dashboard.issues.filter((i) => i.project === p.id && i.status !== "done").length;
    if (mockOpen > p.openIssues) p.openIssues = mockOpen;
  });

  dashboard.projects = repoProjects;
  dashboard.currentProjectId = repoProjects[0].id;
  dashboard.githubMeta = { generatedAt: snapshot.generatedAt, source: snapshot.source };
  markAppliedProjectImports(repoProjects, snapshot.importId);
  normalizeKanbanIssueOrders();

  rebuildIndexes();
}

function refreshAfterSnapshot() {
  updateProjectSelectLabel();
  setText("navCountProjects", dashboard.projects.length);
  setText("navCountIssues", dashboard.issues.length);
  if (projectPickerCall("isOpen")) projectPickerCall("renderOptions");
  renderCurrentView();
}

/* ---------- Browser notification helper (best-effort, opt-in only) ---------- */

const eventReminderHelpers = window.JooParkEventReminders && typeof window.JooParkEventReminders.create === "function"
  ? window.JooParkEventReminders.create({ window, eventsOn, todayISO })
  : null;

function eventReminderCall(name, ...args) {
  if (!eventReminderHelpers || typeof eventReminderHelpers[name] !== "function") return null;
  try {
    return eventReminderHelpers[name](...args);
  } catch (_) {
    return null;
  }
}

const pwaRuntimeHelpers = window.JooParkPwaRuntime && typeof window.JooParkPwaRuntime.create === "function"
  ? window.JooParkPwaRuntime.create({
      window,
      document,
      navigator,
      location,
      caches: window.caches,
    })
  : null;

function renderRuntimeErrorFallback(payload = {}) {
  const viewName = normalizeRouteView(dashboard.currentView || "home");
  const target = refs.views && refs.views[viewName] ? refs.views[viewName] : activeViewEl;
  if (!target) return;
  Object.entries(refs.views || {}).forEach(([name, el]) => {
    if (el) el.hidden = name !== viewName;
  });
  activeViewEl = target;
  target.hidden = false;
  target.replaceChildren();

  const section = document.createElement("section");
  section.className = "panel";
  section.dataset.runtimeErrorFallback = "true";
  section.setAttribute("role", "alert");

  const head = document.createElement("div");
  head.className = "panel-head";
  const titleWrap = document.createElement("div");
  const eyebrow = document.createElement("p");
  eyebrow.className = "eyebrow";
  eyebrow.textContent = "Runtime safety";
  const title = document.createElement("h2");
  title.textContent = "화면을 안전하게 유지했습니다";
  titleWrap.append(eyebrow, title);
  const badge = document.createElement("span");
  badge.className = "pill warn";
  badge.textContent = "오류 감지";
  head.append(titleWrap, badge);

  const guidance = document.createElement("p");
  guidance.className = "muted";
  guidance.textContent = "예상치 못한 오류가 발생했습니다. 다른 메뉴로 이동하거나 새로고침하면 계속 사용할 수 있습니다.";
  const detail = document.createElement("p");
  detail.className = "muted";
  detail.textContent = payload.message || "runtime error";

  section.append(head, guidance, detail);
  target.appendChild(section);
}

const runtimeErrorBoundaryHelpers = window.JooParkRuntimeErrorBoundary && typeof window.JooParkRuntimeErrorBoundary.create === "function"
  ? window.JooParkRuntimeErrorBoundary.create({
      window,
      consoleRef: console,
      locationRef: location,
      showToast,
      fallback: renderRuntimeErrorFallback,
      nowISO,
    })
  : null;

function handleRuntimeError(error, context = {}) {
  if (runtimeErrorBoundaryHelpers) {
    return runtimeErrorBoundaryHelpers.handle(error, context);
  }
  console.error("[joopark-runtime-error]", error);
  try {
    showToast("예상치 못한 오류가 발생했습니다. 화면을 안전하게 유지했습니다.", "error", { timeoutMs: 5200 });
  } catch (_) { /* fallback toast unavailable */ }
  return null;
}

function setupRuntimeErrorBoundary() {
  if (!runtimeErrorBoundaryHelpers) return false;
  return runtimeErrorBoundaryHelpers.install();
}

function pwaRuntimeCall(name, ...args) {
  return callModuleHelper(pwaRuntimeHelpers, "PWA runtime", name, args, "PWA runtime helper unavailable");
}

function renderPwaRuntimeIfVisible() {
  if (dashboard.currentView === "system") renderSystemStatus();
}

async function refreshPwaRuntimeStatus({ render = false } = {}) {
  if (!pwaRuntimeHelpers) return state.pwaRuntime;
  const next = await pwaRuntimeCall("inspect", state.pwaRuntime);
  state.pwaRuntime = next;
  if (render) renderPwaRuntimeIfVisible();
  return next;
}

function setupPwaRuntimeObservers() {
  if (!pwaRuntimeHelpers) return;
  pwaRuntimeCall("setupObservers", () => refreshPwaRuntimeStatus({ render: true }));
}

function registerServiceWorker() {
  const refresh = () => refreshPwaRuntimeStatus({ render: true });
  if (pwaRuntimeHelpers) {
    pwaRuntimeCall("register", refresh);
    return;
  }
  if (!("serviceWorker" in navigator)) return;
  if (!window.isSecureContext && location.hostname !== "localhost" && location.hostname !== "127.0.0.1") return;
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("./sw.js", { scope: "./" })
      .then(refresh)
      .catch(() => {
        state.pwaRuntime = {
          ...state.pwaRuntime,
          checked: true,
          status: "waiting",
          serviceWorkerSupported: true,
          lastError: "service worker registration failed",
          checkedAt: nowISO(),
        };
        renderPwaRuntimeIfVisible();
      });
  }, { once: true });
}

/* ============================================================
 * Theme (라이트/다크)
 * ============================================================ */

/* Apply the persisted theme to <html data-theme="...">. CSS variables under
 * [data-theme="light"] repaint every surface — no re-render needed. */
function applyTheme() {
  const theme = (dashboard.ui && dashboard.ui.theme === "light") ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", theme);
}

function setTheme(theme) {
  ensureDashboardUi({ theme: "dark" }).theme = theme === "light" ? "light" : "dark";
  applyTheme();
  persist();
  if (dashboard.currentView === "settings") renderSettings();
}

function toggleTheme() {
  const next = (dashboard.ui && dashboard.ui.theme === "light") ? "dark" : "light";
  setTheme(next);
  showToast(next === "light" ? "라이트 테마로 전환했습니다" : "다크 테마로 전환했습니다", "info");
}

function refreshReleaseEvidenceAfter(load) { return load().then(() => { refreshReleaseEvidenceViews(); }); }
function refreshVerifyWorkspaceSummaryEvidence() { return refreshReleaseEvidenceAfter(loadVerifyWorkspaceSummary); }

function setup() {
  assertRefs();
  setupRuntimeErrorBoundary();
  // Load the user's saved 일정 / 할 일 / 메모 before the first render (seeds on
  // first run). Everything the user manages day to day lives in localStorage.
  loadPersisted();
  hydrateArtifactStorage().then((hydrated) => {
    if (!hydrated) return;
    applyTheme();
    updateUserDisplayName();
    updateNavCounts();
    updateProjectSelectLabel();
    renderCurrentView();
  }).catch((error) => handleRuntimeError(error, { source: "artifact-storage-hydration" }));
  state.dashboardAutoresearchActive = !!(dashboard.ui && dashboard.ui.dashboardAutoresearchActive);
  applyTheme();
  updateUserDisplayName();
  updateNavCounts();
  // Boot to URL hash if present
  setView(routeViewFromLocation(), { history: "replace" });
  globalSearchCall("setup");
  commandPaletteCall("setup");
  setupInteractions();
  footerClockCall("update");
  updateDataSafetyTopbar();
  // Set project label to the current one
  updateProjectSelectLabel();
  footerClockCall("schedule");
  footerClockCall("setupVisibility");
  refreshStorageHealth();
  window.addEventListener("online", updateDataSafetyTopbar);
  window.addEventListener("offline", updateDataSafetyTopbar);
  loadGithubProjects().then((loaded) => {
    if (loaded) refreshAfterSnapshot();
    else if (dashboard.currentView === "system") renderSystemStatus();
  });
  [
    loadPublishEvidence,
    loadWorkflowUiInstallPlan,
    loadPublishDispatchPlan,
    loadRemoteWorkflowFileCheck,
    loadLaunchExecutionPacket,
    loadLaunchReadinessRefresh,
    loadReleaseReadinessSummary,
    loadReleaseProvenance,
    loadOutputQualityAudit,
    loadGithubProjectDiscovery,
  ].forEach(refreshReleaseEvidenceAfter);
  ensureOpsRuntime("release").then(refreshVerifyWorkspaceSummaryEvidence).catch((error) => handleRuntimeError(error, { source: "ops-runtime", group: "release" }));

  // Boot toast: warn about overdue todos once on load.
  const overdueCount = (Array.isArray(dashboard.todos) ? dashboard.todos : [])
    .filter((t) => !t.done && t.due && t.due < todayISO()).length;
  if (overdueCount > 0) {
    showToast(`기한 지난 할 일 ${overdueCount}건이 있습니다`, "warn");
  }

  // Start browser-notification reminder poll (guarded, does nothing unless
  // permission was previously granted — never auto-prompts).
  eventReminderCall("start");
  setupPwaRuntimeObservers();
  registerServiceWorker();
}

try {
  setup();
} catch (error) {
  handleRuntimeError(error, { source: "setup" });
}
