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
function showToast(message, tone) {
  const region = document.querySelector("#toastRegion");
  if (!region) return;
  const el = document.createElement("div");
  el.className = `toast toast-${tone || "info"}`;
  el.textContent = message;
  region.appendChild(el);
  setTimeout(() => el.classList.add("toast-leave"), TOAST_TIMEOUT - 320);
  setTimeout(() => el.remove(), TOAST_TIMEOUT);
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

function daysSinceIso(iso) {
  const time = Date.parse(iso || "");
  if (Number.isNaN(time)) return 365;
  return Math.max(0, Math.round((Date.now() - time) / (24 * 60 * 60 * 1000)));
}

function candidatePriorityLabel(score) {
  if (score >= 70) return "높음";
  if (score >= 45) return "중간";
  return "관찰";
}

function projectCandidatePriority(p) {
  if (!p || p.sourceKind !== "adoption-candidate") return null;
  const stageScore = { adopt: 24, review: 14, watch: 6 }[p.adoptionStage] || 8;
  const recentDays = daysSinceIso(p.pushedAt);
  const activityScore = Math.max(0, 24 - Math.min(recentDays, 180) / 180 * 24);
  const popularityScore = Math.min(28, Math.log10(numericMetric(p.stars) + 1) * 7);
  const forkScore = Math.min(10, Math.log10(numericMetric(p.forks) + 1) * 4);
  const healthScore = p.health === "green" ? 8 : p.health === "amber" ? 4 : 0;
  const riskPenalty = Math.min(14, numericMetric(p.risks) * 3 + Math.log10(numericMetric(p.openIssues) + 1));
  const score = Math.round(Math.max(0, Math.min(100, stageScore + activityScore + popularityScore + forkScore + healthScore - riskPenalty)));
  return { score, label: candidatePriorityLabel(score) };
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

function projectBenchmarkFocus(p) {
  const focus = p && typeof p.benchmarkFocus === "object" ? p.benchmarkFocus : null;
  if (!focus) return null;
  const surface = String(focus.surface || "").trim();
  const flow = String(focus.flow || "").trim();
  const signals = Array.isArray(focus.signals)
    ? focus.signals.map((signal) => String(signal || "").trim()).filter(Boolean).slice(0, 4)
    : [];
  if (!surface || !flow || signals.length === 0) return null;
  return { surface, flow, signals };
}

function projectBenchmarkRubric(p) {
  const focus = p && typeof p.benchmarkFocus === "object" ? p.benchmarkFocus : null;
  const rubric = focus && Array.isArray(focus.rubric) ? focus.rubric : [];
  return rubric
    .map((row) => ({
      axis: String(row && row.axis || "").trim(),
      value: String(row && row.value || "").trim(),
      weight: Math.max(0, Math.min(1, Number(row && row.weight) || 0)),
      score: Math.max(0, Math.min(100, Number(row && row.score) || 0)),
    }))
    .filter((row) => row.axis && row.value)
    .slice(0, 6);
}

function projectKnowledgeBaseBenchmark(p) {
  const focus = p && typeof p.knowledgeBaseBenchmark === "object" ? p.knowledgeBaseBenchmark : null;
  if (!focus) return null;
  const surface = String(focus.surface || "").trim();
  const flow = String(focus.flow || "").trim();
  const signals = Array.isArray(focus.signals)
    ? focus.signals.map((signal) => String(signal || "").trim()).filter(Boolean).slice(0, 4)
    : [];
  if (!surface || !flow || signals.length === 0) return null;
  return { surface, flow, signals };
}

function projectKnowledgeBaseRubric(p) {
  const focus = p && typeof p.knowledgeBaseBenchmark === "object" ? p.knowledgeBaseBenchmark : null;
  const rubric = focus && Array.isArray(focus.rubric) ? focus.rubric : [];
  return rubric
    .map((row) => ({
      axis: String(row && row.axis || "").trim(),
      value: String(row && row.value || "").trim(),
      weight: Math.max(0, Math.min(1, Number(row && row.weight) || 0)),
      score: Math.max(0, Math.min(100, Number(row && row.score) || 0)),
    }))
    .filter((row) => row.axis && row.value)
    .slice(0, 6);
}

function projectWorkspaceBenchmark(p) {
  const focus = p && typeof p.workspaceBenchmark === "object" ? p.workspaceBenchmark : null;
  if (!focus) return null;
  const surface = String(focus.surface || "").trim();
  const flow = String(focus.flow || "").trim();
  const signals = Array.isArray(focus.signals)
    ? focus.signals.map((signal) => String(signal || "").trim()).filter(Boolean).slice(0, 4)
    : [];
  if (!surface || !flow || signals.length === 0) return null;
  return { surface, flow, signals };
}

function projectWorkspaceRubric(p) {
  const focus = p && typeof p.workspaceBenchmark === "object" ? p.workspaceBenchmark : null;
  const rubric = focus && Array.isArray(focus.rubric) ? focus.rubric : [];
  return rubric
    .map((row) => ({
      axis: String(row && row.axis || "").trim(),
      value: String(row && row.value || "").trim(),
      weight: Math.max(0, Math.min(1, Number(row && row.weight) || 0)),
      score: Math.max(0, Math.min(100, Number(row && row.score) || 0)),
    }))
    .filter((row) => row.axis && row.value)
    .slice(0, 6);
}

function weightedRubricScore(rubric) {
  const scored = (Array.isArray(rubric) ? rubric : []).filter((row) => row.weight > 0 && row.score > 0);
  const totalWeight = scored.reduce((sum, row) => sum + row.weight, 0);
  if (!totalWeight) return null;
  const score = Math.round(scored.reduce((sum, row) => sum + row.score * row.weight, 0) / totalWeight);
  const label = score >= 86 ? "강한 추천" : score >= 80 ? "추천" : score >= 72 ? "조건부" : "보류";
  return { score, label };
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

function candidateBenchmarkRubricRanking(projects) {
  return (Array.isArray(projects) ? projects : [])
    .map((project) => ({ project, rubricScore: projectBenchmarkRubricScore(project) }))
    .filter((item) => item.rubricScore)
    .sort((a, b) => b.rubricScore.score - a.rubricScore.score || String(a.project.name || "").localeCompare(String(b.project.name || "")));
}

function knowledgeBaseBenchmarkRubricRanking(projects) {
  return (Array.isArray(projects) ? projects : [])
    .map((project) => ({ project, rubricScore: projectKnowledgeBaseRubricScore(project) }))
    .filter((item) => item.rubricScore)
    .sort((a, b) => b.rubricScore.score - a.rubricScore.score || String(a.project.name || "").localeCompare(String(b.project.name || "")));
}

function workspaceBenchmarkRubricRanking(projects) {
  return (Array.isArray(projects) ? projects : [])
    .map((project) => ({ project, rubricScore: projectWorkspaceRubricScore(project) }))
    .filter((item) => item.rubricScore)
    .sort((a, b) => b.rubricScore.score - a.rubricScore.score || String(a.project.name || "").localeCompare(String(b.project.name || "")));
}

function candidateBenchmarkRecommendationMarkdown(scored) {
  if (!Array.isArray(scored) || scored.length < 2) return "";
  const [top, runnerUp] = scored;
  const gap = top.rubricScore.score - runnerUp.rubricScore.score;
  const topAxis = projectBenchmarkRubric(top.project)
    .filter((row) => row.weight > 0 && row.score > 0)
    .sort((a, b) => (b.score * b.weight) - (a.score * a.weight))[0] || null;
  const lines = [
    "# JooPark Benchmark Recommendation",
    "",
    `Recommendation: adopt ${top.project.name} first (${top.rubricScore.label} ${top.rubricScore.score}), and keep ${runnerUp.project.name} as the secondary benchmark (${runnerUp.rubricScore.label} ${runnerUp.rubricScore.score}).`,
    `Score gap: ${gap} point${gap === 1 ? "" : "s"}.`,
    topAxis ? `Primary reason: ${topAxis.axis} scored ${topAxis.score} at ${Math.round(topAxis.weight * 100)}% weight because ${topAxis.value}.` : "",
    "",
    "## Weighted Scores",
  ].filter(Boolean);
  scored.forEach(({ project, rubricScore }) => {
    lines.push("", `### ${project.name}: ${rubricScore.label} ${rubricScore.score}`);
    projectBenchmarkRubric(project).forEach((row) => {
      lines.push(`- ${row.axis}: weight ${Math.round(row.weight * 100)}%, score ${row.score} - ${row.value}`);
    });
  });
  return lines.join("\n");
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
  return html`
    <div class="portfolio-candidate-meta" data-candidate-meta>
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
  kanbanFilter: null, // priority filter or null
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
};

/* ---------- Static demo data ---------- */

const dashboard = {
  currentView: "home",
  currentProjectId: "proj-radar",
  currentInstanceId: "db-prod-1",

  projects: [
    { id: "proj-radar", name: "OSS Radar v2", owner: "운영팀", progress: 72, status: "on-track", health: "green",
      deadline: "2026-07-10", burn: [10, 20, 30, 42, 55, 65, 72], risks: 1, openIssues: 14, members: ["jp", "sk", "mh"] },
    { id: "proj-data", name: "데이터 허브", owner: "데이터팀", progress: 48, status: "at-risk", health: "amber",
      deadline: "2026-06-20", burn: [5, 12, 22, 30, 38, 44, 48], risks: 3, openIssues: 22, members: ["sk", "yj"] },
    { id: "proj-docs", name: "Docs 파이프라인", owner: "문서팀", progress: 91, status: "on-track", health: "green",
      deadline: "2026-06-05", burn: [22, 40, 58, 70, 80, 87, 91], risks: 0, openIssues: 4, members: ["mh", "yj"] },
    { id: "proj-policy", name: "정책 허브", owner: "법무팀", progress: 34, status: "delayed", health: "red",
      deadline: "2026-06-12", burn: [4, 9, 15, 22, 27, 31, 34], risks: 4, openIssues: 9, members: ["jp", "yj"] },
    { id: "proj-mobile", name: "모바일 알림", owner: "프론트팀", progress: 58, status: "on-track", health: "green",
      deadline: "2026-07-25", burn: [8, 18, 28, 38, 46, 52, 58], risks: 1, openIssues: 11, members: ["sk", "mh", "hr"] },
    { id: "proj-billing", name: "결제 정산", owner: "결제팀", progress: 25, status: "at-risk", health: "amber",
      deadline: "2026-08-01", burn: [3, 6, 11, 15, 18, 22, 25], risks: 2, openIssues: 17, members: ["hr", "yj"] },
  ],

  issues: [
    { id: "PM-101", project: "proj-radar", title: "라이선스 보고서 자동화", status: "todo", priority: "high", assignee: "jp", labels: ["backend", "docs"], due: "2026-06-05", estimate: 5 },
    { id: "PM-102", project: "proj-radar", title: "PR 리뷰 자동 라우팅", status: "in-progress", priority: "med", assignee: "sk", labels: ["bot"], due: "2026-06-08", estimate: 8 },
    { id: "PM-103", project: "proj-radar", title: "라이선스 충돌 알림 채널", status: "review", priority: "high", assignee: "mh", labels: ["ops"], due: "2026-06-02", estimate: 3 },
    { id: "PM-104", project: "proj-radar", title: "주간 리포트 PDF 출력", status: "done", priority: "low", assignee: "jp", labels: ["docs"], due: "2026-05-25", estimate: 2 },
    { id: "PM-105", project: "proj-radar", title: "OSS 카탈로그 검색 캐시", status: "todo", priority: "med", assignee: "sk", labels: ["backend", "perf"], due: "2026-06-18", estimate: 5 },
    { id: "PM-106", project: "proj-radar", title: "운영자 권한 분리", status: "in-progress", priority: "crit", assignee: "jp", labels: ["security"], due: "2026-06-01", estimate: 4 },

    { id: "PM-201", project: "proj-data", title: "민감값 마스킹 룰", status: "review", priority: "crit", assignee: "yj", labels: ["security"], due: "2026-06-03", estimate: 3 },
    { id: "PM-202", project: "proj-data", title: "데이터 카탈로그 정합성", status: "in-progress", priority: "high", assignee: "yj", labels: ["data"], due: "2026-06-10", estimate: 6 },
    { id: "PM-203", project: "proj-data", title: "스키마 변경 감지", status: "todo", priority: "med", assignee: "sk", labels: ["backend"], due: "2026-06-15", estimate: 5 },
    { id: "PM-204", project: "proj-data", title: "샘플 데이터 자동 생성", status: "todo", priority: "low", assignee: "sk", labels: ["dev"], due: "2026-06-22", estimate: 2 },
    { id: "PM-205", project: "proj-data", title: "Airflow DAG 점검", status: "done", priority: "med", assignee: "yj", labels: ["data"], due: "2026-05-20", estimate: 4 },

    { id: "PM-301", project: "proj-docs", title: "한/영 번역 동기화", status: "in-progress", priority: "med", assignee: "mh", labels: ["docs", "i18n"], due: "2026-06-04", estimate: 5 },
    { id: "PM-302", project: "proj-docs", title: "API 레퍼런스 자동화", status: "done", priority: "high", assignee: "yj", labels: ["docs"], due: "2026-05-22", estimate: 4 },
    { id: "PM-303", project: "proj-docs", title: "튜토리얼 영상 캡션", status: "review", priority: "low", assignee: "mh", labels: ["docs", "media"], due: "2026-06-01", estimate: 2 },

    { id: "PM-401", project: "proj-policy", title: "GDPR 갭 분석 v2", status: "todo", priority: "crit", assignee: "jp", labels: ["compliance"], due: "2026-06-09", estimate: 7 },
    { id: "PM-402", project: "proj-policy", title: "동의서 템플릿 표준화", status: "in-progress", priority: "high", assignee: "yj", labels: ["legal"], due: "2026-06-12", estimate: 5 },
    { id: "PM-403", project: "proj-policy", title: "정책 변경 로그", status: "todo", priority: "med", assignee: "jp", labels: ["compliance"], due: "2026-06-20", estimate: 3 },

    { id: "PM-501", project: "proj-mobile", title: "푸시 채널 분리", status: "in-progress", priority: "high", assignee: "sk", labels: ["mobile"], due: "2026-06-15", estimate: 5 },
    { id: "PM-502", project: "proj-mobile", title: "다크 모드 토큰", status: "review", priority: "low", assignee: "mh", labels: ["ui"], due: "2026-06-08", estimate: 2 },
    { id: "PM-503", project: "proj-mobile", title: "에러 추적 SDK 통합", status: "todo", priority: "med", assignee: "hr", labels: ["mobile", "ops"], due: "2026-06-25", estimate: 4 },
    { id: "PM-504", project: "proj-mobile", title: "알림 클릭 트래킹", status: "todo", priority: "med", assignee: "sk", labels: ["mobile"], due: "2026-07-01", estimate: 3 },
    { id: "PM-505", project: "proj-mobile", title: "iOS 16 호환성", status: "done", priority: "high", assignee: "hr", labels: ["mobile"], due: "2026-05-28", estimate: 4 },

    { id: "PM-601", project: "proj-billing", title: "환불 트랜잭션 격리", status: "review", priority: "crit", assignee: "hr", labels: ["billing"], due: "2026-06-06", estimate: 5 },
    { id: "PM-602", project: "proj-billing", title: "월간 정산 리포트", status: "in-progress", priority: "high", assignee: "yj", labels: ["data"], due: "2026-06-30", estimate: 8 },
    { id: "PM-603", project: "proj-billing", title: "세금 코드 매핑", status: "todo", priority: "high", assignee: "hr", labels: ["billing", "compliance"], due: "2026-07-05", estimate: 6 },
    { id: "PM-604", project: "proj-billing", title: "결제 실패 재시도", status: "todo", priority: "med", assignee: "hr", labels: ["billing"], due: "2026-07-10", estimate: 3 },
    { id: "PM-605", project: "proj-billing", title: "PG 사 라우팅 룰", status: "todo", priority: "low", assignee: "yj", labels: ["billing"], due: "2026-07-15", estimate: 2 },
  ],

  gantt: {
    rangeStart: "2026-05-01",
    rangeEnd: "2026-08-01",
    tasks: [
      { id: "T1",  project: "proj-radar",   name: "요구 정리",         start: "2026-05-01", end: "2026-05-14", owner: "jp", deps: [],          milestone: false, color: "blue" },
      { id: "T2",  project: "proj-radar",   name: "스키마 설계",       start: "2026-05-10", end: "2026-05-28", owner: "sk", deps: ["T1"],      milestone: false, color: "blue" },
      { id: "T3",  project: "proj-radar",   name: "API 구현",          start: "2026-05-28", end: "2026-06-20", owner: "sk", deps: ["T2"],      milestone: false, color: "blue" },
      { id: "M1",  project: "proj-radar",   name: "베타 마일스톤",     start: "2026-06-20", end: "2026-06-20", owner: "jp", deps: ["T3"],      milestone: true,  color: "blue" },
      { id: "T4",  project: "proj-radar",   name: "QA & 문서",         start: "2026-06-20", end: "2026-07-10", owner: "mh", deps: ["M1"],      milestone: false, color: "blue" },

      { id: "T5",  project: "proj-data",    name: "파이프라인 설계",   start: "2026-05-05", end: "2026-05-22", owner: "yj", deps: [],          milestone: false, color: "cyan" },
      { id: "T6",  project: "proj-data",    name: "마스킹 룰 구현",    start: "2026-05-22", end: "2026-06-10", owner: "yj", deps: ["T5"],      milestone: false, color: "cyan" },
      { id: "M2",  project: "proj-data",    name: "데이터 GA",         start: "2026-06-20", end: "2026-06-20", owner: "yj", deps: ["T6"],      milestone: true,  color: "cyan" },

      { id: "T7",  project: "proj-docs",    name: "번역 동기화",       start: "2026-05-12", end: "2026-06-04", owner: "mh", deps: [],          milestone: false, color: "violet" },
      { id: "T8",  project: "proj-docs",    name: "API 레퍼런스",      start: "2026-05-01", end: "2026-05-22", owner: "yj", deps: [],          milestone: false, color: "violet" },

      { id: "T9",  project: "proj-policy",  name: "GDPR 갭 분석",      start: "2026-05-20", end: "2026-06-09", owner: "jp", deps: [],          milestone: false, color: "amber" },
      { id: "T10", project: "proj-policy",  name: "동의서 표준화",     start: "2026-05-25", end: "2026-06-12", owner: "yj", deps: [],          milestone: false, color: "amber" },
      { id: "M3",  project: "proj-policy",  name: "정책 v3 공개",      start: "2026-06-25", end: "2026-06-25", owner: "jp", deps: ["T10"],     milestone: true,  color: "amber" },

      { id: "T11", project: "proj-mobile",  name: "푸시 채널 분리",    start: "2026-05-15", end: "2026-06-15", owner: "sk", deps: [],          milestone: false, color: "green" },
      { id: "T12", project: "proj-mobile",  name: "다크 모드 토큰",    start: "2026-05-28", end: "2026-06-08", owner: "mh", deps: [],          milestone: false, color: "green" },
      { id: "T13", project: "proj-mobile",  name: "SDK 통합",          start: "2026-06-15", end: "2026-07-01", owner: "hr", deps: ["T11"],     milestone: false, color: "green" },

      { id: "T14", project: "proj-billing", name: "환불 격리",         start: "2026-05-18", end: "2026-06-06", owner: "hr", deps: [],          milestone: false, color: "red" },
      { id: "T15", project: "proj-billing", name: "정산 리포트",       start: "2026-06-06", end: "2026-06-30", owner: "yj", deps: ["T14"],     milestone: false, color: "red" },
      { id: "T16", project: "proj-billing", name: "세금 매핑",         start: "2026-06-15", end: "2026-07-05", owner: "hr", deps: [],          milestone: false, color: "red" },
      { id: "T17", project: "proj-billing", name: "재시도 로직",       start: "2026-07-05", end: "2026-07-20", owner: "hr", deps: ["T16"],     milestone: false, color: "red" },
    ],
  },

  team: [
    { id: "jp", name: "박주호", role: "PM",       load: 78, projects: ["proj-radar", "proj-policy"], onLeave: false },
    { id: "sk", name: "서기태", role: "Backend",  load: 92, projects: ["proj-radar", "proj-data", "proj-mobile"], onLeave: false },
    { id: "mh", name: "문하늘", role: "Design",   load: 35, projects: ["proj-radar", "proj-docs", "proj-mobile"], onLeave: false },
    { id: "yj", name: "윤재민", role: "Data",     load: 84, projects: ["proj-data", "proj-docs", "proj-policy", "proj-billing"], onLeave: false },
    { id: "hr", name: "한혜린", role: "Mobile",   load: 71, projects: ["proj-mobile", "proj-billing"], onLeave: false },
    { id: "do", name: "도민재", role: "Frontend", load: 0,  projects: [],                              onLeave: true  },
    { id: "ks", name: "강서윤", role: "QA",       load: 48, projects: ["proj-radar", "proj-mobile"], onLeave: false },
    { id: "nm", name: "남명진", role: "DevOps",   load: 62, projects: ["proj-radar", "proj-data", "proj-billing"], onLeave: false },
  ],

  dbInstances: [
    { id: "db-prod-1",  name: "prod-postgres-01",  engine: "PostgreSQL 15.3", region: "ap-northeast-2", cpu: 42, mem: 68, conn: 184, connMax: 300,  health: "green", latencyMs: 12, series: [20, 22, 28, 34, 30, 38, 42] },
    { id: "db-prod-2",  name: "prod-redis-01",     engine: "Redis 7.2.4",     region: "ap-northeast-2", cpu: 18, mem: 35, conn: 512, connMax: 2000, health: "green", latencyMs: 1,  series: [12, 14, 15, 15, 17, 18, 18] },
    { id: "db-stage-1", name: "stage-postgres-01", engine: "PostgreSQL 15.3", region: "ap-northeast-2", cpu: 88, mem: 74, conn: 240, connMax: 300,  health: "amber", latencyMs: 38, series: [60, 72, 80, 84, 85, 86, 88] },
    { id: "db-dev-1",   name: "dev-postgres-01",   engine: "PostgreSQL 14.9", region: "ap-northeast-2", cpu: 9,  mem: 21, conn: 8,   connMax: 100,  health: "green", latencyMs: 4,  series: [6, 7, 7, 8, 8, 9, 9] },
  ],

  schemas: [
    { id: "db-prod-1", databases: [
      { name: "radar", tables: [
        { id: "t-radar-users",    name: "users",          rows: 18342, sizeMb: 62,
          columns: [
            { name: "id",         type: "bigint",       pk: true,  nullable: false },
            { name: "email",      type: "text",         nullable: false, idx: ["uniq_email"] },
            { name: "name",       type: "text",         nullable: true },
            { name: "role",       type: "text",         nullable: false },
            { name: "created_at", type: "timestamptz",  nullable: false },
          ],
          indexes: [{ name: "uniq_email", cols: ["email"], unique: true }],
          fks: [] },
        { id: "t-radar-repos",    name: "repositories",   rows: 4012, sizeMb: 18,
          columns: [
            { name: "id",         type: "bigint", pk: true },
            { name: "owner_id",   type: "bigint", fk: "users.id", nullable: false },
            { name: "name",       type: "text",   nullable: false },
            { name: "license",    type: "text",   nullable: true },
            { name: "created_at", type: "timestamptz", nullable: false },
          ],
          indexes: [{ name: "idx_owner", cols: ["owner_id"] }],
          fks: [{ col: "owner_id", refs: "users.id" }] },
        { id: "t-radar-issues",   name: "issues",         rows: 22018, sizeMb: 41,
          columns: [
            { name: "id",       type: "bigint", pk: true },
            { name: "repo_id",  type: "bigint", fk: "repositories.id", nullable: false },
            { name: "title",    type: "text",   nullable: false },
            { name: "status",   type: "text",   nullable: false },
            { name: "priority", type: "text",   nullable: false },
            { name: "due_at",   type: "timestamptz", nullable: true },
          ],
          indexes: [{ name: "idx_repo_status", cols: ["repo_id", "status"] }],
          fks: [{ col: "repo_id", refs: "repositories.id" }] },
        { id: "t-radar-licenses", name: "licenses",       rows: 312, sizeMb: 1,
          columns: [
            { name: "spdx_id", type: "text", pk: true },
            { name: "name",   type: "text", nullable: false },
            { name: "kind",   type: "text", nullable: false },
          ],
          indexes: [],
          fks: [] },
        { id: "t-radar-audit", name: "audit_log",         rows: 184012, sizeMb: 412,
          columns: [
            { name: "id",        type: "bigserial", pk: true },
            { name: "actor_id",  type: "bigint",    fk: "users.id" },
            { name: "action",    type: "text" },
            { name: "object",    type: "text" },
            { name: "at",        type: "timestamptz", nullable: false },
          ],
          indexes: [{ name: "idx_audit_at", cols: ["at"] }],
          fks: [{ col: "actor_id", refs: "users.id" }] },
      ] },
      { name: "billing", tables: [
        { id: "t-bill-orders",   name: "orders",          rows: 92341, sizeMb: 184,
          columns: [
            { name: "id",        type: "bigint", pk: true },
            { name: "user_id",   type: "bigint", fk: "radar.users.id" },
            { name: "amount",    type: "numeric(12,2)" },
            { name: "currency",  type: "char(3)" },
            { name: "status",    type: "text" },
            { name: "created_at",type: "timestamptz" },
          ],
          indexes: [{ name: "idx_user", cols: ["user_id"] }, { name: "idx_status", cols: ["status"] }],
          fks: [{ col: "user_id", refs: "radar.users.id" }] },
        { id: "t-bill-refunds",  name: "refunds",         rows: 1240, sizeMb: 8,
          columns: [
            { name: "id",        type: "bigint", pk: true },
            { name: "order_id",  type: "bigint", fk: "orders.id" },
            { name: "reason",    type: "text" },
            { name: "amount",    type: "numeric(12,2)" },
            { name: "created_at",type: "timestamptz" },
          ],
          indexes: [{ name: "idx_order", cols: ["order_id"] }],
          fks: [{ col: "order_id", refs: "orders.id" }] },
        { id: "t-bill-tax",      name: "tax_rates",       rows: 412, sizeMb: 1,
          columns: [
            { name: "code", type: "text", pk: true },
            { name: "rate", type: "numeric(6,4)" },
            { name: "region", type: "text" },
          ],
          indexes: [],
          fks: [] },
      ] },
    ] },
    { id: "db-prod-2", databases: [
      { name: "cache", tables: [
        { id: "t-cache-sess",   name: "sessions:*",        rows: 12842, sizeMb: 22, columns: [{ name: "key", type: "string" }, { name: "ttl", type: "seconds" }, { name: "value", type: "json" }], indexes: [], fks: [] },
        { id: "t-cache-queue",  name: "queue:notifications", rows: 1240, sizeMb: 3, columns: [{ name: "id", type: "stream" }, { name: "payload", type: "json" }], indexes: [], fks: [] },
        { id: "t-cache-rate",   name: "rate:user:*",       rows: 4920, sizeMb: 5, columns: [{ name: "key", type: "string" }, { name: "count", type: "int" }], indexes: [], fks: [] },
      ] },
    ] },
    { id: "db-stage-1", databases: [
      { name: "radar_stage", tables: [
        { id: "t-stage-users",  name: "users",         rows: 184, sizeMb: 1,  columns: [{ name: "id", type: "bigint", pk: true }, { name: "email", type: "text" }, { name: "name", type: "text" }], indexes: [], fks: [] },
        { id: "t-stage-repos",  name: "repositories",  rows: 42, sizeMb: 1,   columns: [{ name: "id", type: "bigint", pk: true }, { name: "owner_id", type: "bigint" }, { name: "name", type: "text" }], indexes: [], fks: [] },
        { id: "t-stage-issues", name: "issues",        rows: 220, sizeMb: 1,  columns: [{ name: "id", type: "bigint", pk: true }, { name: "repo_id", type: "bigint" }, { name: "status", type: "text" }], indexes: [], fks: [] },
        { id: "t-stage-flags",  name: "feature_flags", rows: 28, sizeMb: 1,   columns: [{ name: "key", type: "text", pk: true }, { name: "enabled", type: "bool" }], indexes: [], fks: [] },
      ] },
    ] },
    { id: "db-dev-1", databases: [
      { name: "scratch", tables: [
        { id: "t-dev-test", name: "test_runs", rows: 18, sizeMb: 1, columns: [{ name: "id", type: "bigint", pk: true }, { name: "ran_at", type: "timestamptz" }], indexes: [], fks: [] },
      ] },
    ] },
  ],

  queries: [
    { id: "Q1",  instance: "db-prod-1",  db: "radar",   text: "SELECT r.*, u.email FROM repositories r JOIN users u ON u.id = r.owner_id WHERE r.license IS NULL", avgMs: 1280, p95Ms: 2100, count: 42,  lastRun: "2026-05-29 09:14", planHint: "seq scan on repositories" },
    { id: "Q2",  instance: "db-stage-1", db: "radar",   text: "UPDATE issues SET status = $1 WHERE repo_id = $2 AND due_at < NOW()",                              avgMs: 980,  p95Ms: 1450, count: 118, lastRun: "2026-05-29 09:11", planHint: "missing idx on (repo_id, due_at)" },
    { id: "Q3",  instance: "db-prod-1",  db: "billing", text: "SELECT o.id, SUM(o.amount) FROM orders o WHERE o.created_at > now() - interval '30 days' GROUP BY o.id", avgMs: 740, p95Ms: 1200, count: 32, lastRun: "2026-05-29 09:09", planHint: "consider materialized view" },
    { id: "Q4",  instance: "db-prod-1",  db: "radar",   text: "SELECT * FROM audit_log WHERE at > NOW() - interval '1 hour' ORDER BY at DESC LIMIT 200",            avgMs: 612,  p95Ms: 980,  count: 84,  lastRun: "2026-05-29 09:08", planHint: "OK (idx_audit_at)" },
    { id: "Q5",  instance: "db-prod-1",  db: "radar",   text: "SELECT count(*) FROM issues WHERE status = 'todo' AND priority IN ('high','crit')",                  avgMs: 540,  p95Ms: 820,  count: 240, lastRun: "2026-05-29 09:07", planHint: "consider partial idx" },
    { id: "Q6",  instance: "db-stage-1", db: "radar",   text: "INSERT INTO issues(...) SELECT ... FROM staging_issues",                                              avgMs: 488,  p95Ms: 720,  count: 6,   lastRun: "2026-05-29 02:00", planHint: "batch insert" },
    { id: "Q7",  instance: "db-prod-1",  db: "billing", text: "SELECT * FROM orders WHERE status = 'failed' AND created_at > now() - interval '24h'",               avgMs: 420,  p95Ms: 640,  count: 64,  lastRun: "2026-05-29 09:05", planHint: "OK (idx_status)" },
    { id: "Q8",  instance: "db-prod-1",  db: "radar",   text: "DELETE FROM audit_log WHERE at < now() - interval '90 days'",                                        avgMs: 380,  p95Ms: 580,  count: 1,   lastRun: "2026-05-29 03:00", planHint: "scheduled cleanup" },
    { id: "Q9",  instance: "db-dev-1",   db: "scratch", text: "SELECT * FROM test_runs ORDER BY ran_at DESC LIMIT 100",                                             avgMs: 320,  p95Ms: 480,  count: 22,  lastRun: "2026-05-29 08:42", planHint: "OK" },
    { id: "Q10", instance: "db-prod-1",  db: "billing", text: "SELECT r.id FROM refunds r WHERE r.created_at > $1 ORDER BY r.amount DESC",                          avgMs: 270,  p95Ms: 400,  count: 18,  lastRun: "2026-05-29 09:01", planHint: "OK (idx_order)" },
    { id: "Q11", instance: "db-stage-1", db: "radar",   text: "VACUUM ANALYZE issues",                                                                              avgMs: 240,  p95Ms: 320,  count: 1,   lastRun: "2026-05-29 04:00", planHint: "scheduled maintenance" },
    { id: "Q12", instance: "db-prod-1",  db: "radar",   text: "SELECT spdx_id FROM licenses WHERE kind = $1",                                                       avgMs: 210,  p95Ms: 300,  count: 920, lastRun: "2026-05-29 09:14", planHint: "lookup" },
  ],

  queryHistogram: [
    { bucket: "<10",     count: 1820 },
    { bucket: "10-50",   count: 940 },
    { bucket: "50-100",  count: 612 },
    { bucket: "100-200", count: 412 },
    { bucket: "200-400", count: 280 },
    { bucket: "400-600", count: 184 },
    { bucket: "600-800", count: 120 },
    { bucket: "0.8-1s",  count: 82  },
    { bucket: "1-2s",    count: 42  },
    { bucket: "2-5s",    count: 14  },
    { bucket: "5-10s",   count: 4   },
    { bucket: ">10s",    count: 1   },
  ],

  backups: (function () {
    const out = [];
    const instances = ["db-prod-1", "db-prod-2", "db-stage-1", "db-dev-1"];
    const start = "2026-05-01";
    for (let d = 0; d < 30; d++) {
      const date = addDays(start, d);
      instances.forEach((inst) => {
        // Deterministic pattern: most ok, some warn, rare fail
        const key = (d * 7 + inst.length) % 23;
        let status = "ok";
        let note = "";
        if (key === 0) { status = "fail"; note = "디스크 부족"; }
        else if (key === 3 || key === 14) { status = "warn"; note = "느린 I/O"; }
        const sizeMb = status === "fail" ? 0 : (inst === "db-prod-1" ? 1800 + (d * 6) : inst === "db-prod-2" ? 420 + d : inst === "db-stage-1" ? 380 + d * 2 : 80 + d);
        const durationS = status === "fail" ? 0 : (inst === "db-prod-1" ? 42 + (key % 5) * 8 : 8 + (key % 4) * 3);
        out.push({ date, instance: inst, status, sizeMb, durationS, note });
      });
    }
    return out;
  })(),

  migrations: [
    { id: "M-2026-05-12-01", instance: "db-prod-1",  title: "add issues.priority", status: "applied",  appliedAt: "2026-05-12 02:05", rolledBack: false },
    { id: "M-2026-05-15-01", instance: "db-prod-1",  title: "create index idx_audit_at", status: "applied", appliedAt: "2026-05-15 02:02", rolledBack: false },
    { id: "M-2026-05-20-01", instance: "db-prod-1",  title: "add billing.refunds.reason", status: "applied", appliedAt: "2026-05-20 02:04", rolledBack: false },
    { id: "M-2026-05-25-03", instance: "db-stage-1", title: "drop users.legacy_token",  status: "pending",  scheduledAt: "2026-05-30 02:00" },
    { id: "M-2026-05-28-01", instance: "db-prod-1",  title: "alter audit_log.actor_id nullable",  status: "review",   author: "jp" },
    { id: "M-2026-05-28-02", instance: "db-stage-1", title: "feature flag table bootstrap", status: "applied", appliedAt: "2026-05-28 02:10", rolledBack: false },
    { id: "M-2026-05-29-01", instance: "db-prod-1",  title: "create materialized view monthly_orders", status: "pending", scheduledAt: "2026-05-31 02:00" },
    { id: "M-2026-05-29-02", instance: "db-prod-1",  title: "drop audit_log.legacy",   status: "rolled-back", appliedAt: "2026-05-26 02:00", rolledBack: true, rollbackReason: "타이밍 충돌로 롤백" },
  ],

  projects_list_for_picker: null, // computed below in setup if needed
};

/* ---------- Refs ---------- */

const refs = {
  views: {
    home:           document.querySelector("#view-home"),
    cal:            document.querySelector("#view-cal"),
    todo:           document.querySelector("#view-todo"),
    notes:          document.querySelector("#view-notes"),
    habits:         document.querySelector("#view-habits"),
    stats:          document.querySelector("#view-stats"),
    "pm-portfolio": document.querySelector("#view-pm-portfolio"),
    "pm-kanban":    document.querySelector("#view-pm-kanban"),
    "pm-gantt":     document.querySelector("#view-pm-gantt"),
    "pm-team":      document.querySelector("#view-pm-team"),
    "dbm-instances":document.querySelector("#view-dbm-instances"),
    "dbm-schema":   document.querySelector("#view-dbm-schema"),
    "dbm-queries":  document.querySelector("#view-dbm-queries"),
    "dbm-backups":  document.querySelector("#view-dbm-backups"),
    settings:       document.querySelector("#view-settings"),
  },
  query: document.querySelector("#globalSearch"),
  searchCount: document.querySelector("#searchCount"),
  navItems: document.querySelectorAll("[data-action='nav-to']"),
  sheets: {
    root: document.querySelector("#sheet"),
    title: document.querySelector("#sheetTitle"),
    body: document.querySelector("#sheetBody"),
    meta: document.querySelector("#sheetMeta"),
  },
  modal: {
    root: document.querySelector("#modal"),
    title: document.querySelector("#modalTitle"),
    body: document.querySelector("#modalBody"),
  },
  projectSelect: document.querySelector("#projectSelect"),
  projectSelectLabel: document.querySelector("#projectSelectLabel"),
  projectPicker: document.querySelector("#projectPicker"),
  footerNow: document.querySelector("#footerNow"),
};

const projectPickerState = { query: "" };

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
function currentProject() {
  return indexes.projectById.get(dashboard.currentProjectId) || dashboard.projects[0] || null;
}
function currentInstance() {
  return indexes.instanceById.get(dashboard.currentInstanceId) || dashboard.dbInstances[0] || null;
}

/* ---------- Panel head helper ---------- */

function panelHead(title, link, controls) {
  return html`
    <div class="panel-head">
      <div><h2>${title}</h2>${link ? raw(html`<a href="#" data-action="${link.action}" data-view="${link.view || ""}">${link.label}</a>`) : ""}</div>
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

/* ============================================================
 * View: Home
 * ============================================================ */

function renderHome() {
  const view = refs.views.home;
  if (!view) return;

  const today = todayISO();
  const now = new Date();
  const hour = now.getHours();
  const greet = hour < 6 ? "편안한 새벽 되세요" : hour < 12 ? "좋은 아침입니다" : hour < 18 ? "좋은 오후입니다" : "좋은 저녁입니다";
  const name = (dashboard.settings && dashboard.settings.displayName) || "박주호";

  const todaysEvents = eventsOn(today);
  const openTodos = dashboard.todos.filter((t) => !t.done);
  const overdueTodos = openTodos.filter((t) => t.due && t.due < today);
  const todayTodos = openTodos.filter((t) => t.due === today);
  const weekEnd = addDaysISO(today, 7);
  // Use expandOccurrences so recurring events appear in the upcoming list.
  const upcoming = sortEvents(expandOccurrences(addDaysISO(today, 1), weekEnd)).slice(0, 6);
  const weekDeadlines =
    dashboard.events.filter((e) => e.category === "deadline" && e.date >= today && e.date <= weekEnd).length +
    openTodos.filter((t) => t.due && t.due >= today && t.due <= weekEnd).length;

  const totalProjects = dashboard.projects.length;
  const onTrack = dashboard.projects.filter((p) => p.status === "on-track").length;
  const totalIssues = dashboard.issues.length;
  const unhealthy = dashboard.dbInstances.filter((d) => d.health !== "green").length;
  const slow = dashboard.queries.length;
  const pendingMig = dashboard.migrations.filter((m) => m.status === "pending").length;

  /* Personal-first KPIs */
  const kpis = [
    { title: "오늘 일정",   value: String(todaysEvents.length), unit: "건", color: "#2387ff", badge: "◷", delta: formatKoreanShort(today) },
    { title: "할 일 남음",  value: String(openTodos.length),    unit: "건", color: overdueTodos.length ? "#ff4d5e" : "#22d3ee", badge: "☑", delta: overdueTodos.length ? `지남 ${overdueTodos.length}건` : "양호", trendDown: overdueTodos.length > 0 },
    { title: "이번 주 마감", value: String(weekDeadlines),       unit: "건", color: "#f7a928", badge: "⚑", delta: "앞으로 7일" },
    { title: "진행 프로젝트", value: String(totalProjects),       unit: "개", color: "#17d983", badge: "▦", delta: `${onTrack}개 정상` },
  ];

  /* 오늘의 일정 + 할 일 (today's command panel) */
  const todayEventsHTML = todaysEvents.length
    ? todaysEvents.map((e) => eventRow(e, { compact: true })).join("")
    : html`<p class="agenda-empty">오늘 등록된 일정이 없습니다.</p>`;
  const todayTodoList = [...overdueTodos, ...todayTodos];
  const todayTodosHTML = todayTodoList.length
    ? html`<div class="home-today-todos">${todayTodoList.slice(0, 6).map((t) => raw(html`
        <div class="agenda-todo-row">
          <button type="button" class="todo-check-mini" data-action="todo-toggle" data-todo-id="${t.id}" aria-label="완료 토글"></button>
          <button type="button" class="agenda-todo-open" data-action="open-todo" data-todo-id="${t.id}">
            <span class="agenda-todo-title">${t.title}</span>
            <span class="todo-due ${raw(dueLabel(t.due).cls)}">${dueLabel(t.due).text}</span>
          </button>
        </div>`))}</div>`
    : html`<p class="agenda-empty">오늘 마감인 할 일이 없습니다. 👍</p>`;

  const upcomingHTML = upcoming.length
    ? html`<ul class="home-upcoming">${upcoming.map((e) => {
        const c = EVENT_CATS[e.category] || EVENT_CATS.etc;
        // For occurrences, open their master event.
        const openId = e._masterId || e.id;
        return raw(html`<li data-action="open-event" data-event-id="${openId}">
          <span class="up-date" style="color:${raw(c.color)}">${formatKoreanShort(e.date)}</span>
          <span class="up-title">${e.title}</span>
          <span class="up-time">${eventTimeLabel(e)}</span>
        </li>`);
      })}</ul>`
    : html`<p class="agenda-empty">앞으로 7일간 예정된 일정이 없습니다.</p>`;

  const tile = (title, subtitle, viewName, body) => html`
    <article class="panel home-tile">
      <div class="panel-head">
        <div><h2>${title}</h2><a href="#" data-action="nav-to" data-view="${viewName}">전체 보기 ›</a></div>
        <small class="home-tile-sub">${subtitle}</small>
      </div>
      ${raw(body)}
    </article>
  `;

  const topProjects = [...dashboard.projects].sort((a, b) => b.progress - a.progress).slice(0, 3);
  const portfolioBody = html`
    <ul class="home-list">${topProjects.map((p) => raw(html`
      <li>
        <span class="home-dot" style="background:${raw(HEALTH_COLOR[p.health])}"></span>
        <strong>${p.name}</strong>
        <em>${p.progress}%</em>
      </li>
    `))}</ul>
  `;

  const counts = { todo: 0, "in-progress": 0, review: 0, done: 0 };
  dashboard.issues.forEach((i) => { counts[i.status] = (counts[i.status] || 0) + 1; });
  const kanbanBody = html`
    <div class="home-stats">
      <div><b>${counts.todo}</b><small>To Do</small></div>
      <div><b>${counts["in-progress"]}</b><small>In Progress</small></div>
      <div><b>${counts.review}</b><small>Review</small></div>
      <div><b>${counts.done}</b><small>Done</small></div>
    </div>
  `;

  const upcomingMs = dashboard.gantt.tasks.filter((t) => t.milestone).slice(0, 3);
  const ganttBody = html`
    <ul class="home-list">${upcomingMs.map((m) => raw(html`
      <li>
        <span class="home-dot" style="background:var(--violet)"></span>
        <strong>${m.name}</strong>
        <em>${m.start}</em>
      </li>
    `))}</ul>
  `;

  const overloaded = dashboard.team.filter((m) => m.load > 85);
  const teamBody = html`
    <ul class="home-list">${dashboard.team.slice(0, 4).map((m) => raw(html`
      <li>
        <span class="home-dot" style="background:${raw(m.load > 85 ? "var(--red)" : m.load > 65 ? "var(--amber)" : "var(--green)")}"></span>
        <strong>${m.name}</strong>
        <em>${m.load}%</em>
      </li>
    `))}</ul>
    <small class="home-sub">오버할당 ${overloaded.length}명</small>
  `;

  const instancesBody = html`
    <ul class="home-list">${dashboard.dbInstances.map((d) => raw(html`
      <li>
        <span class="home-dot" style="background:${raw(HEALTH_COLOR[d.health])}"></span>
        <strong>${d.name}</strong>
        <em>CPU ${d.cpu}%</em>
      </li>
    `))}</ul>
  `;

  const schemaTotalTables = dashboard.schemas.reduce((a, s) => a + s.databases.reduce((b, db) => b + db.tables.length, 0), 0);
  const schemaBody = html`
    <div class="home-stats">
      <div><b>${dashboard.dbInstances.length}</b><small>인스턴스</small></div>
      <div><b>${dashboard.schemas.reduce((a, s) => a + s.databases.length, 0)}</b><small>DB</small></div>
      <div><b>${schemaTotalTables}</b><small>테이블</small></div>
    </div>
  `;

  const topQueries = [...dashboard.queries].sort((a, b) => b.p95Ms - a.p95Ms).slice(0, 3);
  const queriesBody = html`
    <ul class="home-list">${topQueries.map((q) => raw(html`
      <li>
        <span class="home-dot" style="background:var(--red)"></span>
        <strong>${q.id}</strong>
        <em>p95 ${q.p95Ms}ms</em>
      </li>
    `))}</ul>
  `;

  const recentBackups = dashboard.backups.slice(-4).reverse();
  const backupsBody = html`
    <ul class="home-list">${recentBackups.map((b) => raw(html`
      <li>
        <span class="home-dot" style="background:${raw(b.status === "ok" ? "var(--green)" : b.status === "warn" ? "var(--amber)" : "var(--red)")}"></span>
        <strong>${b.date}</strong>
        <em>${b.instance}</em>
      </li>
    `))}</ul>
  `;

  setHTML(view, html`
    <section class="panel home-hero">
      <div class="home-hero-text">
        <small>${formatKoreanFull(today)}</small>
        <h1>${greet}, ${name}님</h1>
        <p>오늘 일정 <b>${todaysEvents.length}</b>건 · 할 일 <b>${openTodos.length}</b>건${overdueTodos.length ? raw(html` · <span class="hero-warn">지난 마감 ${overdueTodos.length}건</span>`) : ""}</p>
      </div>
      <div class="home-hero-actions">
        <button type="button" class="primary-btn" data-action="cal-add" data-date="${today}">+ 일정</button>
        <button type="button" data-action="todo-add">+ 할 일</button>
        <button type="button" data-action="note-add">+ 메모</button>
      </div>
    </section>
    <section class="kpis kpis-4">${raw(kpis.map((k) => kpiCard(k)).join(""))}</section>
    <section class="home-command">
      <article class="panel home-today">
        <div class="panel-head"><div><h2>오늘</h2><a href="#cal" data-action="nav-to" data-view="cal">일정 전체 ›</a></div></div>
        <div class="agenda-list">${raw(todayEventsHTML)}</div>
        <p class="home-today-label">오늘 마감 할 일</p>
        ${raw(todayTodosHTML)}
      </article>
      <article class="panel home-upcoming-panel">
        <div class="panel-head"><div><h2>다가오는 7일</h2><a href="#cal" data-action="nav-to" data-view="cal">달력 ›</a></div></div>
        ${raw(upcomingHTML)}
      </article>
    </section>
    <p class="home-section-title">팀 · 시스템 관리</p>
    <section class="home-tiles">
      ${raw(tile("프로젝트 포트폴리오", `${totalProjects}개`,        "pm-portfolio",   portfolioBody))}
      ${raw(tile("Kanban 보드",         `${totalIssues}개 이슈`,    "pm-kanban",      kanbanBody))}
      ${raw(tile("간트 마일스톤",        `${dashboard.gantt.tasks.filter((t) => t.milestone).length}개`, "pm-gantt", ganttBody))}
      ${raw(tile("팀 부하",              `${dashboard.team.length}명`, "pm-team",      teamBody))}
      ${raw(tile("DB 인스턴스",          `${unhealthy}건 주의`,       "dbm-instances",instancesBody))}
      ${raw(tile("스키마",               `${schemaTotalTables} 테이블`,"dbm-schema",   schemaBody))}
      ${raw(tile("질의 성능",            `slow ${slow}건`,            "dbm-queries",  queriesBody))}
      ${raw(tile("백업 / 마이그",         `대기 ${pendingMig}건`,       "dbm-backups",  backupsBody))}
    </section>
  `);
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
    const aPriority = projectCandidatePriority(a);
    const bPriority = projectCandidatePriority(b);
    const scoreDiff = (bPriority?.score || 0) - (aPriority?.score || 0);
    if (scoreDiff !== 0) return scoreDiff;
    return String(a.name || "").localeCompare(String(b.name || ""));
  });
}

function candidateActionQueueSummary(projects, filter) {
  const selected = CANDIDATE_ACTION_FILTERS.find((item) => item.key === filter) || CANDIDATE_ACTION_FILTERS[0];
  const queue = projects.filter((p) => p.sourceKind === "adoption-candidate" && portfolioMatchesActionFilter(p, selected.key));
  const ranked = [...queue].sort((a, b) => {
    const aPriority = projectCandidatePriority(a);
    const bPriority = projectCandidatePriority(b);
    const scoreDiff = (bPriority?.score || 0) - (aPriority?.score || 0);
    if (scoreDiff !== 0) return scoreDiff;
    return String(a.name || "").localeCompare(String(b.name || ""));
  });
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
  const selected = CANDIDATE_BENCHMARK_FILTERS.find((item) => item.key === filter) || CANDIDATE_BENCHMARK_FILTERS[0];
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

function candidateBenchmarkRubric(projects, filter) {
  if (filter !== "focused") return "";
  const focused = sortBenchmarkFocusProjects(projects.filter((p) => p.sourceKind === "adoption-candidate" && projectBenchmarkRubric(p).length > 0)).slice(0, 2);
  if (focused.length < 2) return "";
  const axes = ["입력 소스", "AI 보조", "PM 표면", "운영 방식"];
  const rowFor = (project, axis) => projectBenchmarkRubric(project).find((row) => row.axis === axis) || null;
  const scored = candidateBenchmarkRubricRanking(focused);
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
      const weight = row && row.weight ? `${Math.round(row.weight * 100)}%` : "가중 없음";
      const score = row && row.score ? `${row.score}점` : "점수 없음";
      return html`<div class="portfolio-rubric-value" data-rubric-project="${project.name}" data-rubric-axis="${axis}" data-rubric-weight="${row ? row.weight : 0}" data-rubric-score="${row ? row.score : 0}"><span>${row ? row.value : "비교 대기"}</span><small>${weight} · ${score}</small></div>`;
    }).join(""))}
  `).join("");
  return html`
    <section class="portfolio-benchmark-rubric" data-candidate-benchmark-rubric>
      <div class="portfolio-rubric-head">
        <span>벤치 비교표</span>
        <strong>${focused.map((project) => project.name.split("/").pop()).join(" / ")}</strong>
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
  const focused = knowledgeBaseBenchmarkRubricRanking((Array.isArray(projects) ? projects : [])
    .filter((p) => p.sourceKind === "adoption-candidate" && projectKnowledgeBaseRubric(p).length > 0))
    .map((item) => item.project)
    .slice(0, 3);
  if (focused.length < 3) return "";
  const axes = Array.from(new Set(focused.flatMap((project) => projectKnowledgeBaseRubric(project).map((row) => row.axis))));
  const rowFor = (project, axis) => projectKnowledgeBaseRubric(project).find((row) => row.axis === axis) || null;
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
      const weight = row && row.weight ? `${Math.round(row.weight * 100)}%` : "가중 없음";
      const score = row && row.score ? `${row.score}점` : "점수 없음";
      return html`<div class="portfolio-rubric-value" data-kb-rubric-project="${project.name}" data-kb-rubric-axis="${axis}" data-kb-rubric-weight="${row ? row.weight : 0}" data-kb-rubric-score="${row ? row.score : 0}"><span>${row ? row.value : "비교 대기"}</span><small>${weight} · ${score}</small></div>`;
    }).join(""))}
  `).join("");
  return html`
    <section class="portfolio-benchmark-rubric" data-knowledge-base-benchmark-rubric>
      <div class="portfolio-rubric-head">
        <span>KB/IA 비교표</span>
        <strong>${focused.map((project) => project.name.split("/").pop()).join(" / ")}</strong>
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
  const focused = workspaceBenchmarkRubricRanking((Array.isArray(projects) ? projects : [])
    .filter((p) => p.sourceKind === "adoption-candidate" && projectWorkspaceRubric(p).length > 0))
    .map((item) => item.project)
    .slice(0, 2);
  if (focused.length < 2) return "";
  const axes = Array.from(new Set(focused.flatMap((project) => projectWorkspaceRubric(project).map((row) => row.axis))));
  const rowFor = (project, axis) => projectWorkspaceRubric(project).find((row) => row.axis === axis) || null;
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
      const weight = row && row.weight ? `${Math.round(row.weight * 100)}%` : "가중 없음";
      const score = row && row.score ? `${row.score}점` : "점수 없음";
      return html`<div class="portfolio-rubric-value" data-workspace-rubric-project="${project.name}" data-workspace-rubric-axis="${axis}" data-workspace-rubric-weight="${row ? row.weight : 0}" data-workspace-rubric-score="${row ? row.score : 0}"><span>${row ? row.value : "비교 대기"}</span><small>${weight} · ${score}</small></div>`;
    }).join(""))}
  `).join("");
  return html`
    <section class="portfolio-benchmark-rubric" data-workspace-benchmark-rubric data-workspace-benchmark-surface="${topFocus ? topFocus.surface : "JooPark Workspace"}" data-workspace-benchmark-flow="${topFocus ? topFocus.flow : "PM/task + notes/wiki collaboration transfer"}">
      <div class="portfolio-rubric-head">
        <span>Workspace 비교표</span>
        <strong>${focused.map((project) => project.name.split("/").pop()).join(" / ")}</strong>
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
  if (!Array.isArray(scored) || scored.length < 2) return "";
  const [top, runnerUp] = scored;
  const gap = top.rubricScore.score - runnerUp.rubricScore.score;
  const topAxis = projectWorkspaceRubric(top.project)
    .filter((row) => row.weight > 0 && row.score > 0)
    .sort((a, b) => (b.score * b.weight) - (a.score * a.weight))[0] || null;
  const lines = [
    "# JooPark Workspace Benchmark Recommendation",
    "",
    `Recommendation: use ${top.project.name} as the primary Workspace benchmark (${top.rubricScore.label} ${top.rubricScore.score}), and keep ${runnerUp.project.name} as the PM/task contrast (${runnerUp.rubricScore.label} ${runnerUp.rubricScore.score}).`,
    `Score gap: ${gap} point${gap === 1 ? "" : "s"}.`,
    topAxis ? `Primary reason: ${topAxis.axis} scored ${topAxis.score} at ${Math.round(topAxis.weight * 100)}% weight because ${topAxis.value}.` : "",
    "",
    "## Weighted Scores",
  ].filter(Boolean);
  scored.forEach(({ project, rubricScore }) => {
    lines.push("", `### ${project.name}: ${rubricScore.label} ${rubricScore.score}`);
    projectWorkspaceRubric(project).forEach((row) => {
      lines.push(`- ${row.axis}: weight ${Math.round(row.weight * 100)}%, score ${row.score} - ${row.value}`);
    });
  });
  return lines.join("\n");
}

function candidateWorkspaceRecommendationExport(scored) {
  if (!Array.isArray(scored) || scored.length < 2) return "";
  const [top, runnerUp] = scored;
  const markdown = workspaceBenchmarkRecommendationMarkdown(scored);
  if (!markdown) return "";
  const gap = top.rubricScore.score - runnerUp.rubricScore.score;
  const topAxis = projectWorkspaceRubric(top.project)
    .filter((row) => row.weight > 0 && row.score > 0)
    .sort((a, b) => (b.score * b.weight) - (a.score * a.weight))[0] || null;
  const href = `data:text/markdown;charset=utf-8,${encodeURIComponent(markdown)}`;
  return html`
    <section class="portfolio-benchmark-export" data-workspace-benchmark-export data-workspace-benchmark-export-winner="${top.project.name}" data-workspace-benchmark-export-gap="${gap}" data-workspace-benchmark-export-format="markdown">
      <div class="portfolio-export-head">
        <span>Workspace export</span>
        <a class="portfolio-export-download" data-workspace-benchmark-export-download href="${href}" download="joopark-workspace-benchmark-recommendation.md">MD 저장</a>
      </div>
      <div class="portfolio-export-grid">
        <div><span>추천</span><strong>${top.project.name}</strong><small>${top.rubricScore.label} ${top.rubricScore.score}</small></div>
        <div><span>비교</span><strong>${runnerUp.project.name}</strong><small>${gap}점 차이</small></div>
        <div><span>근거</span><strong>${topAxis ? topAxis.axis : "가중 점수"}</strong><small>${topAxis ? `${topAxis.score}점 · ${Math.round(topAxis.weight * 100)}%` : "루브릭 합산"}</small></div>
      </div>
      <pre class="portfolio-export-body" data-workspace-benchmark-export-text>${markdown}</pre>
    </section>
  `;
}

function projectWorkspaceReviewDecision(project, rank = 0) {
  const rubricScore = projectWorkspaceRubricScore(project);
  if (!project || !rubricScore) return null;
  const focus = projectWorkspaceBenchmark(project);
  const topAxis = projectWorkspaceRubric(project)
    .filter((row) => row.weight > 0 && row.score > 0)
    .sort((a, b) => (b.score * b.weight) - (a.score * a.weight))[0] || null;
  const status = rubricScore.score >= 86 ? "Workspace 도입 검토" : rubricScore.score >= 80 ? "비교 유지" : "관찰";
  return {
    rank: rank + 1,
    status,
    score: rubricScore.score,
    label: rubricScore.label,
    surface: focus ? focus.surface : "JooPark Workspace",
    reason: topAxis ? `${topAxis.axis}: ${topAxis.value}` : focus ? focus.flow : "Workspace 검토",
    persistKey: `workspace-review:${project.id}:${rubricScore.score}`,
  };
}

function workspaceReviewDecisions(scored) {
  return (Array.isArray(scored) ? scored : [])
    .map(({ project }, index) => ({ project, decision: projectWorkspaceReviewDecision(project, index) }))
    .filter((item) => item.decision)
    .slice(0, 2)
    .map((item, index) => ({ ...item, decision: { ...item.decision, rank: index + 1 } }));
}

function candidateWorkspaceReviewHandoff(scored) {
  const decisions = workspaceReviewDecisions(scored);
  if (decisions.length === 0) return "";
  const markdown = workspaceReviewHandoffMarkdown(decisions);
  if (!markdown) return "";
  const primary = decisions[0];
  const existingNote = dashboard.notes.find((note) => note.sourceKey === primary.decision.persistKey);
  const href = `data:text/markdown;charset=utf-8,${encodeURIComponent(markdown)}`;
  return html`
    <section class="portfolio-review-handoff" data-workspace-review-handoff data-review-handoff-format="markdown" data-review-handoff-count="${decisions.length}" data-workspace-review-handoff-count="${decisions.length}" data-review-handoff-primary-key="${primary.decision.persistKey}" data-workspace-review-handoff-primary-key="${primary.decision.persistKey}" data-workspace-review-note-created="${existingNote ? "true" : "false"}" data-workspace-review-note-id="${existingNote ? existingNote.id : ""}">
      <div class="portfolio-export-head">
        <span>Workspace handoff</span>
        <div class="portfolio-export-actions">
          <a class="portfolio-export-download" data-workspace-review-handoff-download href="${href}" download="joopark-workspace-review-handoff.md">MD 저장</a>
          <button type="button" class="portfolio-export-download portfolio-export-copy" data-action="copy-review-handoff" data-review-handoff-copy data-workspace-review-handoff-copy data-review-handoff-copy-key="${primary.decision.persistKey}" data-workspace-review-handoff-copy-key="${primary.decision.persistKey}">복사</button>
          <button type="button" class="portfolio-export-download portfolio-export-copy" data-action="publish-review-note" data-review-note-publish data-workspace-review-note-publish data-review-note-key="${primary.decision.persistKey}" data-workspace-review-note-key="${primary.decision.persistKey}" data-review-note-created="${existingNote ? "true" : "false"}" data-review-note-id="${existingNote ? existingNote.id : ""}" ${raw(existingNote ? "disabled" : "")}>${existingNote ? "노트 발행됨" : "노트 발행"}</button>
        </div>
      </div>
      <small class="portfolio-export-status" data-review-handoff-copy-status data-workspace-review-handoff-copy-status aria-live="polite"></small>
      <small class="portfolio-export-status" data-workspace-review-note-publish-status aria-live="polite">${existingNote ? "노트 발행됨" : ""}</small>
      <div class="portfolio-export-grid">
        <div>
          <span>우선 결정</span>
          <strong>${primary.project.name} ${primary.decision.status}</strong>
        </div>
        <div>
          <span>persist key</span>
          <strong>${primary.decision.persistKey}</strong>
        </div>
        <div>
          <span>handoff 수</span>
          <strong>${decisions.length}개</strong>
        </div>
      </div>
      ${raw(candidateWorkspaceReviewIssueDraft(decisions))}
      ${raw(candidateWorkspaceReviewGithubComment(decisions))}
      <pre class="portfolio-export-body" data-review-handoff-text data-workspace-review-handoff-text>${markdown}</pre>
    </section>
  `;
}

function workspaceReviewHandoffMarkdown(decisions) {
  if (!Array.isArray(decisions) || decisions.length === 0) return "";
  const primary = decisions[0];
  const rows = decisions.map(({ project, decision }) => (
    `${decision.rank}. ${project.name} - ${decision.status} - ${decision.label} ${decision.score} - ${decision.persistKey} - ${decision.reason}`
  ));
  return [
    "# JooPark Workspace Review Handoff",
    "",
    `Primary decision key: ${primary.decision.persistKey}`,
    `Primary decision: ${primary.project.name} ${primary.decision.status} ${primary.decision.score}`,
    `Primary surface: ${primary.decision.surface}`,
    "",
    "## Decisions",
    ...rows,
  ].join("\n");
}

function workspaceReviewIssueDraft(decisions) {
  if (!Array.isArray(decisions) || decisions.length === 0) return null;
  const primary = decisions[0];
  if (!primary || !primary.project || !primary.decision) return null;
  const secondary = decisions.find((item) => item.decision.rank > 1);
  const labels = ["workspace", "benchmark", "handoff", "adoption"];
  return {
    title: `[Workspace] ${primary.project.name} ${primary.decision.status}`,
    projectId: primary.project.id,
    projectName: primary.project.name,
    priority: primary.decision.score >= 86 ? "high" : "med",
    status: "todo",
    estimate: 4,
    labels,
    persistKey: primary.decision.persistKey,
    body: [
      `Decision: ${primary.project.name} ${primary.decision.status} (${primary.decision.label} ${primary.decision.score})`,
      `Persist key: ${primary.decision.persistKey}`,
      `Surface: ${primary.decision.surface}`,
      `Reason: ${primary.decision.reason}`,
      secondary ? `Compare with: ${secondary.project.name} ${secondary.decision.status} (${secondary.decision.label} ${secondary.decision.score})` : "",
    ].filter(Boolean).join("\n"),
  };
}

function candidateWorkspaceReviewIssueDraft(decisions) {
  const draft = workspaceReviewIssueDraft(decisions);
  if (!draft) return "";
  const existing = dashboard.issues.find((issue) => issue.sourceKey === draft.persistKey);
  return html`
    <section class="portfolio-review-issue-draft" data-review-issue-draft data-workspace-review-issue-draft data-issue-draft-title="${draft.title}" data-issue-draft-project="${draft.projectName}" data-issue-draft-priority="${draft.priority}" data-issue-draft-key="${draft.persistKey}" data-issue-draft-labels="${draft.labels.join(",")}" data-issue-draft-estimate="${draft.estimate}" data-issue-draft-created="${existing ? "true" : "false"}" data-issue-draft-id="${existing ? existing.id : ""}">
      <div class="portfolio-issue-draft-head">
        <span>Workspace issue draft</span>
        <button type="button" class="portfolio-export-download portfolio-issue-draft-create" data-action="create-review-issue" data-review-issue-create data-workspace-review-issue-create data-review-issue-key="${draft.persistKey}" ${raw(existing ? "disabled" : "")}>${existing ? "생성됨" : "이슈 생성"}</button>
      </div>
      <div class="portfolio-issue-draft-grid">
        <div>
          <span>제목</span>
          <strong>${draft.title}</strong>
        </div>
        <div>
          <span>프로젝트</span>
          <strong>${draft.projectName}</strong>
        </div>
        <div>
          <span>우선순위</span>
          <strong>${ISSUE_PRIORITY_MAP[draft.priority]}</strong>
        </div>
      </div>
      <pre class="portfolio-issue-draft-body" data-issue-draft-body>${draft.body}</pre>
    </section>
  `;
}

function workspaceReviewGithubCommentMarkdown(decisions) {
  if (!Array.isArray(decisions) || decisions.length === 0) return "";
  const primary = decisions[0];
  const draft = workspaceReviewIssueDraft(decisions);
  if (!primary || !primary.project || !primary.decision || !draft) return "";
  const secondary = decisions.find((item) => item.decision.rank > 1);
  return [
    "## JooPark Workspace Review",
    "",
    `Primary decision key: ${primary.decision.persistKey}`,
    `Recommendation: ${primary.project.name} ${primary.decision.status} (${primary.decision.label} ${primary.decision.score})`,
    `Surface: ${primary.decision.surface}`,
    `Reason: ${primary.decision.reason}`,
    secondary ? `Compare with: ${secondary.project.name} ${secondary.decision.status} (${secondary.decision.label} ${secondary.decision.score})` : "",
    "",
    "## Issue Draft",
    `Title: ${draft.title}`,
    `Priority: ${draft.priority}`,
    `Labels: ${draft.labels.join(", ")}`,
    `Estimate: ${draft.estimate}`,
    "",
    draft.body,
  ].filter(Boolean).join("\n");
}

function candidateWorkspaceReviewGithubComment(decisions) {
  if (!Array.isArray(decisions) || decisions.length === 0) return "";
  const primary = decisions[0];
  const draft = workspaceReviewIssueDraft(decisions);
  const comment = workspaceReviewGithubCommentMarkdown(decisions);
  if (!primary || !draft || !comment) return "";
  const issueUrl = githubNewIssueUrl(primary.project, draft.title, comment);
  return html`
    <section class="portfolio-review-issue-draft portfolio-review-github-comment" data-workspace-review-github-comment data-review-github-comment-key="${draft.persistKey}" data-review-github-comment-target="${primary.project.name}" data-review-github-comment-format="markdown">
      <div class="portfolio-issue-draft-head">
        <span>GitHub comment draft</span>
        <div class="portfolio-export-actions">
          ${issueUrl ? raw(html`<a class="portfolio-export-download" data-workspace-review-github-comment-open href="${issueUrl}" target="_blank" rel="noopener">이슈 열기</a>`) : ""}
          <button type="button" class="portfolio-export-download portfolio-export-copy" data-action="copy-review-github-comment" data-review-github-comment-copy data-workspace-review-github-comment-copy data-review-github-comment-copy-key="${draft.persistKey}">댓글 복사</button>
        </div>
      </div>
      <small class="portfolio-export-status" data-review-github-comment-copy-status data-workspace-review-github-comment-copy-status aria-live="polite"></small>
      <pre class="portfolio-issue-draft-body" data-review-github-comment-text data-workspace-review-github-comment-text>${comment}</pre>
    </section>
  `;
}

function knowledgeBaseBenchmarkRecommendationMarkdown(scored) {
  if (!Array.isArray(scored) || scored.length < 2) return "";
  const [top, runnerUp] = scored;
  const gap = top.rubricScore.score - runnerUp.rubricScore.score;
  const topAxis = projectKnowledgeBaseRubric(top.project)
    .filter((row) => row.weight > 0 && row.score > 0)
    .sort((a, b) => (b.score * b.weight) - (a.score * a.weight))[0] || null;
  const lines = [
    "# JooPark Knowledge/IA Benchmark Recommendation",
    "",
    `Recommendation: use ${top.project.name} as the primary Knowledge/IA benchmark (${top.rubricScore.label} ${top.rubricScore.score}), and keep ${runnerUp.project.name} as the portability counterweight (${runnerUp.rubricScore.label} ${runnerUp.rubricScore.score}).`,
    `Score gap: ${gap} point${gap === 1 ? "" : "s"}.`,
    topAxis ? `Primary reason: ${topAxis.axis} scored ${topAxis.score} at ${Math.round(topAxis.weight * 100)}% weight because ${topAxis.value}.` : "",
    "",
    "## Weighted Scores",
  ].filter(Boolean);
  scored.forEach(({ project, rubricScore }) => {
    lines.push("", `### ${project.name}: ${rubricScore.label} ${rubricScore.score}`);
    projectKnowledgeBaseRubric(project).forEach((row) => {
      lines.push(`- ${row.axis}: weight ${Math.round(row.weight * 100)}%, score ${row.score} - ${row.value}`);
    });
  });
  return lines.join("\n");
}

function candidateKnowledgeBaseRecommendationExport(scored) {
  if (!Array.isArray(scored) || scored.length < 2) return "";
  const [top, runnerUp] = scored;
  const markdown = knowledgeBaseBenchmarkRecommendationMarkdown(scored);
  if (!markdown) return "";
  const gap = top.rubricScore.score - runnerUp.rubricScore.score;
  const topAxis = projectKnowledgeBaseRubric(top.project)
    .filter((row) => row.weight > 0 && row.score > 0)
    .sort((a, b) => (b.score * b.weight) - (a.score * a.weight))[0] || null;
  const href = `data:text/markdown;charset=utf-8,${encodeURIComponent(markdown)}`;
  return html`
    <section class="portfolio-benchmark-export" data-knowledge-base-benchmark-export data-kb-benchmark-export-winner="${top.project.name}" data-kb-benchmark-export-gap="${gap}" data-kb-benchmark-export-format="markdown">
      <div class="portfolio-export-head">
        <span>KB/IA export</span>
        <a class="portfolio-export-download" data-kb-benchmark-export-download href="${href}" download="joopark-kb-ia-recommendation.md">MD 저장</a>
      </div>
      <div class="portfolio-export-grid">
        <div><span>추천</span><strong>${top.project.name}</strong><small>${top.rubricScore.label} ${top.rubricScore.score}</small></div>
        <div><span>비교</span><strong>${runnerUp.project.name}</strong><small>${gap}점 차이</small></div>
        <div><span>근거</span><strong>${topAxis ? topAxis.axis : "가중 점수"}</strong><small>${topAxis ? `${topAxis.score}점 · ${Math.round(topAxis.weight * 100)}%` : "루브릭 합산"}</small></div>
      </div>
      <pre class="portfolio-export-body" data-kb-benchmark-export-text>${markdown}</pre>
    </section>
  `;
}

function projectKnowledgeBaseReviewDecision(project, rank = 0) {
  const rubricScore = projectKnowledgeBaseRubricScore(project);
  if (!project || !rubricScore) return null;
  const focus = projectKnowledgeBaseBenchmark(project);
  const topAxis = projectKnowledgeBaseRubric(project)
    .filter((row) => row.weight > 0 && row.score > 0)
    .sort((a, b) => (b.score * b.weight) - (a.score * a.weight))[0] || null;
  const status = rubricScore.score >= 86 ? "IA 도입 검토" : rubricScore.score >= 80 ? "비교 유지" : "관찰";
  return {
    rank: rank + 1,
    status,
    score: rubricScore.score,
    label: rubricScore.label,
    surface: focus ? focus.surface : "Knowledge/IA",
    reason: topAxis ? `${topAxis.axis}: ${topAxis.value}` : focus ? focus.flow : "KB/IA 검토",
    persistKey: `kb-ia-review:${project.id}:${rubricScore.score}`,
  };
}

function knowledgeBaseReviewDecisions(scored) {
  return (Array.isArray(scored) ? scored : [])
    .map(({ project }, index) => ({ project, decision: projectKnowledgeBaseReviewDecision(project, index) }))
    .filter((item) => item.decision)
    .slice(0, 3)
    .map((item, index) => ({ ...item, decision: { ...item.decision, rank: index + 1 } }));
}

function candidateKnowledgeBaseReviewHandoff(scored) {
  const decisions = knowledgeBaseReviewDecisions(scored);
  if (decisions.length === 0) return "";
  const markdown = knowledgeBaseReviewHandoffMarkdown(decisions);
  if (!markdown) return "";
  const primary = decisions[0];
  const existingNote = dashboard.notes.find((note) => note.sourceKey === primary.decision.persistKey);
  const href = `data:text/markdown;charset=utf-8,${encodeURIComponent(markdown)}`;
  return html`
    <section class="portfolio-review-handoff" data-knowledge-base-review-handoff data-review-handoff-format="markdown" data-review-handoff-count="${decisions.length}" data-kb-review-handoff-count="${decisions.length}" data-review-handoff-primary-key="${primary.decision.persistKey}" data-kb-review-handoff-primary-key="${primary.decision.persistKey}" data-kb-review-note-created="${existingNote ? "true" : "false"}" data-kb-review-note-id="${existingNote ? existingNote.id : ""}">
      <div class="portfolio-export-head">
        <span>KB/IA handoff</span>
        <div class="portfolio-export-actions">
          <a class="portfolio-export-download" data-kb-review-handoff-download href="${href}" download="joopark-kb-ia-review-handoff.md">MD 저장</a>
          <button type="button" class="portfolio-export-download portfolio-export-copy" data-action="copy-review-handoff" data-review-handoff-copy data-kb-review-handoff-copy data-review-handoff-copy-key="${primary.decision.persistKey}" data-kb-review-handoff-copy-key="${primary.decision.persistKey}">복사</button>
          <button type="button" class="portfolio-export-download portfolio-export-copy" data-action="publish-review-note" data-review-note-publish data-kb-review-note-publish data-review-note-key="${primary.decision.persistKey}" data-kb-review-note-key="${primary.decision.persistKey}" data-review-note-kind="knowledge-base-review-note" data-review-note-title-prefix="[KB/IA Review]" data-review-note-color="#84cc16" data-review-note-created="${existingNote ? "true" : "false"}" data-review-note-id="${existingNote ? existingNote.id : ""}" ${raw(existingNote ? "disabled" : "")}>${existingNote ? "노트 발행됨" : "노트 발행"}</button>
        </div>
      </div>
      <small class="portfolio-export-status" data-review-handoff-copy-status data-kb-review-handoff-copy-status aria-live="polite"></small>
      <small class="portfolio-export-status" data-kb-review-note-publish-status aria-live="polite">${existingNote ? "노트 발행됨" : ""}</small>
      <div class="portfolio-export-grid">
        <div>
          <span>우선 결정</span>
          <strong>${primary.project.name} ${primary.decision.status}</strong>
        </div>
        <div>
          <span>persist key</span>
          <strong>${primary.decision.persistKey}</strong>
        </div>
        <div>
          <span>handoff 수</span>
          <strong>${decisions.length}개</strong>
        </div>
      </div>
      ${raw(candidateKnowledgeBaseReviewIssueDraft(decisions))}
      ${raw(candidateKnowledgeBaseReviewGithubComment(decisions))}
      <pre class="portfolio-export-body" data-review-handoff-text data-kb-review-handoff-text>${markdown}</pre>
    </section>
  `;
}

function knowledgeBaseReviewHandoffMarkdown(decisions) {
  if (!Array.isArray(decisions) || decisions.length === 0) return "";
  const primary = decisions[0];
  const rows = decisions.map(({ project, decision }) => (
    `${decision.rank}. ${project.name} - ${decision.status} - ${decision.label} ${decision.score} - ${decision.persistKey} - ${decision.reason}`
  ));
  return [
    "# JooPark Knowledge/IA Review Handoff",
    "",
    `Primary decision key: ${primary.decision.persistKey}`,
    `Primary decision: ${primary.project.name} ${primary.decision.status} ${primary.decision.score}`,
    `Primary surface: ${primary.decision.surface}`,
    "",
    "## Decisions",
    ...rows,
  ].join("\n");
}

function knowledgeBaseReviewIssueDraft(decisions) {
  if (!Array.isArray(decisions) || decisions.length === 0) return null;
  const primary = decisions[0];
  if (!primary || !primary.project || !primary.decision) return null;
  const secondary = decisions.find((item) => item.decision.rank > 1);
  const labels = ["knowledge-base", "ia", "handoff", "adoption"];
  return {
    title: `[KB/IA] ${primary.project.name} ${primary.decision.status}`,
    projectId: primary.project.id,
    projectName: primary.project.name,
    priority: primary.decision.score >= 86 ? "high" : "med",
    status: "todo",
    estimate: 3,
    labels,
    persistKey: primary.decision.persistKey,
    body: [
      `Decision: ${primary.project.name} ${primary.decision.status} (${primary.decision.label} ${primary.decision.score})`,
      `Persist key: ${primary.decision.persistKey}`,
      `Surface: ${primary.decision.surface}`,
      `Reason: ${primary.decision.reason}`,
      secondary ? `Compare with: ${secondary.project.name} ${secondary.decision.status} (${secondary.decision.label} ${secondary.decision.score})` : "",
    ].filter(Boolean).join("\n"),
  };
}

function candidateKnowledgeBaseReviewIssueDraft(decisions) {
  const draft = knowledgeBaseReviewIssueDraft(decisions);
  if (!draft) return "";
  const existing = dashboard.issues.find((issue) => issue.sourceKey === draft.persistKey);
  return html`
    <section class="portfolio-review-issue-draft" data-review-issue-draft data-kb-review-issue-draft data-issue-draft-title="${draft.title}" data-issue-draft-project="${draft.projectName}" data-issue-draft-priority="${draft.priority}" data-issue-draft-key="${draft.persistKey}" data-issue-draft-labels="${draft.labels.join(",")}" data-issue-draft-estimate="${draft.estimate}" data-issue-draft-created="${existing ? "true" : "false"}" data-issue-draft-id="${existing ? existing.id : ""}">
      <div class="portfolio-issue-draft-head">
        <span>KB/IA issue draft</span>
        <button type="button" class="portfolio-export-download portfolio-issue-draft-create" data-action="create-review-issue" data-review-issue-create data-kb-review-issue-create data-review-issue-key="${draft.persistKey}" ${raw(existing ? "disabled" : "")}>${existing ? "생성됨" : "이슈 생성"}</button>
      </div>
      <div class="portfolio-issue-draft-grid">
        <div>
          <span>제목</span>
          <strong>${draft.title}</strong>
        </div>
        <div>
          <span>프로젝트</span>
          <strong>${draft.projectName}</strong>
        </div>
        <div>
          <span>우선순위</span>
          <strong>${ISSUE_PRIORITY_MAP[draft.priority]}</strong>
        </div>
      </div>
      <pre class="portfolio-issue-draft-body" data-issue-draft-body>${draft.body}</pre>
    </section>
  `;
}

function knowledgeBaseReviewGithubCommentMarkdown(decisions) {
  if (!Array.isArray(decisions) || decisions.length === 0) return "";
  const primary = decisions[0];
  const draft = knowledgeBaseReviewIssueDraft(decisions);
  if (!primary || !primary.project || !primary.decision || !draft) return "";
  const secondary = decisions.find((item) => item.decision.rank > 1);
  return [
    "## JooPark Knowledge/IA Review",
    "",
    `Primary decision key: ${primary.decision.persistKey}`,
    `Recommendation: ${primary.project.name} ${primary.decision.status} (${primary.decision.label} ${primary.decision.score})`,
    `Surface: ${primary.decision.surface}`,
    `Reason: ${primary.decision.reason}`,
    secondary ? `Compare with: ${secondary.project.name} ${secondary.decision.status} (${secondary.decision.label} ${secondary.decision.score})` : "",
    "",
    "## Issue Draft",
    `Title: ${draft.title}`,
    `Priority: ${draft.priority}`,
    `Labels: ${draft.labels.join(", ")}`,
    `Estimate: ${draft.estimate}`,
    "",
    draft.body,
  ].filter(Boolean).join("\n");
}

function candidateKnowledgeBaseReviewGithubComment(decisions) {
  if (!Array.isArray(decisions) || decisions.length === 0) return "";
  const primary = decisions[0];
  const draft = knowledgeBaseReviewIssueDraft(decisions);
  const comment = knowledgeBaseReviewGithubCommentMarkdown(decisions);
  if (!primary || !draft || !comment) return "";
  const issueUrl = githubNewIssueUrl(primary.project, draft.title, comment);
  return html`
    <section class="portfolio-review-issue-draft portfolio-review-github-comment" data-kb-review-github-comment data-review-github-comment-key="${draft.persistKey}" data-review-github-comment-target="${primary.project.name}" data-review-github-comment-format="markdown">
      <div class="portfolio-issue-draft-head">
        <span>GitHub comment draft</span>
        <div class="portfolio-export-actions">
          ${issueUrl ? raw(html`<a class="portfolio-export-download" data-kb-review-github-comment-open href="${issueUrl}" target="_blank" rel="noopener">이슈 열기</a>`) : ""}
          <button type="button" class="portfolio-export-download portfolio-export-copy" data-action="copy-review-github-comment" data-review-github-comment-copy data-kb-review-github-comment-copy data-review-github-comment-copy-key="${draft.persistKey}">댓글 복사</button>
        </div>
      </div>
      <small class="portfolio-export-status" data-review-github-comment-copy-status data-kb-review-github-comment-copy-status aria-live="polite"></small>
      <pre class="portfolio-issue-draft-body" data-review-github-comment-text data-kb-review-github-comment-text>${comment}</pre>
    </section>
  `;
}

function candidateBenchmarkRecommendationExport(scored) {
  if (!Array.isArray(scored) || scored.length < 2) return "";
  const [top, runnerUp] = scored;
  const markdown = candidateBenchmarkRecommendationMarkdown(scored);
  if (!markdown) return "";
  const gap = top.rubricScore.score - runnerUp.rubricScore.score;
  const topAxis = projectBenchmarkRubric(top.project)
    .filter((row) => row.weight > 0 && row.score > 0)
    .sort((a, b) => (b.score * b.weight) - (a.score * a.weight))[0] || null;
  const href = `data:text/markdown;charset=utf-8,${encodeURIComponent(markdown)}`;
  return html`
    <section class="portfolio-benchmark-export" data-candidate-benchmark-export data-benchmark-export-winner="${top.project.name}" data-benchmark-export-gap="${gap}" data-benchmark-export-format="markdown">
      <div class="portfolio-export-head">
        <span>추천 export</span>
        <a class="portfolio-export-download" data-benchmark-export-download href="${href}" download="joopark-benchmark-recommendation.md">MD 저장</a>
      </div>
      <div class="portfolio-export-grid">
        <div>
          <span>우선 채택</span>
          <strong>${top.project.name} ${top.rubricScore.label} ${top.rubricScore.score}</strong>
        </div>
        <div>
          <span>보조 벤치</span>
          <strong>${runnerUp.project.name} ${runnerUp.rubricScore.label} ${runnerUp.rubricScore.score}</strong>
        </div>
        <div>
          <span>격차</span>
          <strong>${gap}점</strong>
        </div>
        <div>
          <span>근거</span>
          <strong>${topAxis ? `${topAxis.axis} ${topAxis.score}` : "점수 대기"}</strong>
        </div>
      </div>
      <pre class="portfolio-export-body" data-benchmark-export-text>${markdown}</pre>
    </section>
  `;
}

function projectBenchmarkReviewDecision(project, rank = 0) {
  const rubricScore = projectBenchmarkRubricScore(project);
  if (!project || !rubricScore) return null;
  const action = projectCandidateAction(project);
  const focus = projectBenchmarkFocus(project);
  const status = rubricScore.score >= 86 ? "도입 검토" : rubricScore.score >= 80 ? "비교 유지" : "관찰";
  return {
    rank: rank + 1,
    status,
    score: rubricScore.score,
    label: rubricScore.label,
    actionLabel: action ? action.label : "검토",
    reason: action ? action.reason : focus ? focus.flow : "벤치 대기",
    persistKey: `benchmark-review:${project.id}:${rubricScore.score}`,
  };
}

function candidateBenchmarkReviewQueue(projects, filter) {
  if (filter !== "focused") return "";
  const decisions = sortBenchmarkFocusProjects(projects.filter((p) => p.sourceKind === "adoption-candidate" && projectBenchmarkRubric(p).length > 0))
    .map((project, index) => ({ project, decision: projectBenchmarkReviewDecision(project, index) }))
    .filter((item) => item.decision)
    .sort((a, b) => b.decision.score - a.decision.score || a.decision.rank - b.decision.rank)
    .slice(0, 3)
    .map((item, index) => ({ ...item, decision: { ...item.decision, rank: index + 1 } }));
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
  if (!Array.isArray(decisions) || decisions.length === 0) return "";
  const markdown = candidateBenchmarkReviewQueueMarkdown(decisions);
  if (!markdown) return "";
  const primary = decisions[0];
  const href = `data:text/markdown;charset=utf-8,${encodeURIComponent(markdown)}`;
  return html`
    <section class="portfolio-review-handoff" data-benchmark-review-handoff data-review-handoff-format="markdown" data-review-handoff-count="${decisions.length}" data-review-handoff-primary-key="${primary.decision.persistKey}">
      <div class="portfolio-export-head">
        <span>handoff export</span>
        <div class="portfolio-export-actions">
          <a class="portfolio-export-download" data-review-handoff-download href="${href}" download="joopark-benchmark-review-queue.md">MD 저장</a>
          <button type="button" class="portfolio-export-download portfolio-export-copy" data-action="copy-review-handoff" data-review-handoff-copy data-review-handoff-copy-key="${primary.decision.persistKey}">복사</button>
        </div>
      </div>
      <small class="portfolio-export-status" data-review-handoff-copy-status aria-live="polite"></small>
      <div class="portfolio-export-grid">
        <div>
          <span>우선 결정</span>
          <strong>${primary.project.name} ${primary.decision.status}</strong>
        </div>
        <div>
          <span>persist key</span>
          <strong>${primary.decision.persistKey}</strong>
        </div>
        <div>
          <span>handoff 수</span>
          <strong>${decisions.length}개</strong>
        </div>
      </div>
      ${raw(candidateBenchmarkReviewIssueDraft(decisions))}
      <pre class="portfolio-export-body" data-review-handoff-text>${markdown}</pre>
    </section>
  `;
}

function candidateBenchmarkReviewQueueMarkdown(decisions) {
  if (!Array.isArray(decisions) || decisions.length === 0) return "";
  const primary = decisions[0];
  const rows = decisions.map(({ project, decision }) => (
    `${decision.rank}. ${project.name} - ${decision.status} - ${decision.label} ${decision.score} - ${decision.persistKey} - ${decision.reason}`
  ));
  return [
    "# JooPark Benchmark Review Queue",
    "",
    `Primary decision key: ${primary.decision.persistKey}`,
    `Primary decision: ${primary.project.name} ${primary.decision.status} ${primary.decision.score}`,
    "",
    "## Decisions",
    ...rows,
  ].join("\n");
}

function benchmarkReviewIssueDraft(decisions) {
  if (!Array.isArray(decisions) || decisions.length === 0) return null;
  const primary = decisions[0];
  if (!primary || !primary.project || !primary.decision) return null;
  const secondary = decisions.find((item) => item.decision.rank > 1);
  const labels = ["benchmark", "handoff", "adoption"];
  return {
    title: `[Benchmark] ${primary.project.name} ${primary.decision.status}`,
    projectId: primary.project.id,
    projectName: primary.project.name,
    priority: primary.decision.score >= 86 ? "high" : "med",
    status: "todo",
    estimate: 4,
    labels,
    persistKey: primary.decision.persistKey,
    body: [
      `Decision: ${primary.project.name} ${primary.decision.status} (${primary.decision.label} ${primary.decision.score})`,
      `Persist key: ${primary.decision.persistKey}`,
      `Reason: ${primary.decision.reason}`,
      secondary ? `Compare with: ${secondary.project.name} ${secondary.decision.status} (${secondary.decision.label} ${secondary.decision.score})` : "",
    ].filter(Boolean).join("\n"),
  };
}

function candidateBenchmarkReviewIssueDraft(decisions) {
  const draft = benchmarkReviewIssueDraft(decisions);
  if (!draft) return "";
  const existing = dashboard.issues.find((issue) => issue.sourceKey === draft.persistKey);
  return html`
    <section class="portfolio-review-issue-draft" data-review-issue-draft data-issue-draft-title="${draft.title}" data-issue-draft-project="${draft.projectName}" data-issue-draft-priority="${draft.priority}" data-issue-draft-key="${draft.persistKey}" data-issue-draft-labels="${draft.labels.join(",")}" data-issue-draft-estimate="${draft.estimate}" data-issue-draft-created="${existing ? "true" : "false"}" data-issue-draft-id="${existing ? existing.id : ""}">
      <div class="portfolio-issue-draft-head">
        <span>PM issue draft</span>
        <button type="button" class="portfolio-export-download portfolio-issue-draft-create" data-action="create-review-issue" data-review-issue-create data-review-issue-key="${draft.persistKey}" ${raw(existing ? "disabled" : "")}>${existing ? "생성됨" : "이슈 생성"}</button>
      </div>
      <div class="portfolio-issue-draft-grid">
        <div>
          <span>제목</span>
          <strong>${draft.title}</strong>
        </div>
        <div>
          <span>프로젝트</span>
          <strong>${draft.projectName}</strong>
        </div>
        <div>
          <span>우선순위</span>
          <strong>${ISSUE_PRIORITY_MAP[draft.priority]}</strong>
        </div>
      </div>
      <pre class="portfolio-issue-draft-body" data-issue-draft-body>${draft.body}</pre>
    </section>
  `;
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

function copyBenchmarkReviewHandoff(target) {
  const handoff = target.closest("[data-benchmark-review-handoff], [data-knowledge-base-review-handoff], [data-workspace-review-handoff]");
  const text = handoff ? handoff.querySelector("[data-review-handoff-text]")?.textContent || "" : "";
  const status = handoff ? handoff.querySelector("[data-review-handoff-copy-status]") : null;
  writeClipboardText(text).then((copied) => {
    target.dataset.reviewHandoffCopied = copied ? "true" : "false";
    if (handoff) handoff.dataset.reviewHandoffCopied = copied ? "true" : "false";
    if (status) status.textContent = copied ? "복사됨" : "복사 실패";
    showToast(copied ? "handoff를 복사했습니다" : "복사 실패", copied ? "info" : "error");
  });
}

function copyReviewGithubComment(target) {
  const comment = target.closest("[data-workspace-review-github-comment], [data-kb-review-github-comment]");
  const text = comment ? comment.querySelector("[data-review-github-comment-text]")?.textContent || "" : "";
  const status = comment ? comment.querySelector("[data-review-github-comment-copy-status]") : null;
  writeClipboardText(text).then((copied) => {
    target.dataset.reviewGithubCommentCopied = copied ? "true" : "false";
    if (comment) comment.dataset.reviewGithubCommentCopied = copied ? "true" : "false";
    if (status) status.textContent = copied ? "댓글 복사됨" : "댓글 복사 실패";
    showToast(copied ? "GitHub comment draft를 복사했습니다" : "댓글 복사 실패", copied ? "info" : "error");
  });
}

function createBenchmarkReviewIssue(target) {
  const handoff = target.closest("[data-benchmark-review-handoff], [data-knowledge-base-review-handoff], [data-workspace-review-handoff]");
  const key = target.dataset.reviewIssueKey || "";
  if (!handoff || !key) {
    showToast("이슈 초안을 찾을 수 없습니다", "warn");
    return;
  }
  const draftNode = handoff.querySelector("[data-review-issue-draft]");
  const title = draftNode ? draftNode.dataset.issueDraftTitle : "";
  const projectName = draftNode ? draftNode.dataset.issueDraftProject : "";
  const project = dashboard.projects.find((item) => item.name === projectName);
  if (!title || !project) {
    showToast("이슈 초안 프로젝트를 찾을 수 없습니다", "warn");
    return;
  }
  const existing = dashboard.issues.find((issue) => issue.sourceKey === key);
  if (existing) {
    showToast(`이미 생성된 이슈입니다: ${existing.id}`, "info");
    renderCurrentView();
    return;
  }
  const body = draftNode ? draftNode.querySelector("[data-issue-draft-body]")?.textContent || "" : "";
  const priority = draftNode ? draftNode.dataset.issueDraftPriority || "med" : "med";
  const labels = draftNode && draftNode.dataset.issueDraftLabels
    ? draftNode.dataset.issueDraftLabels.split(",").map((label) => label.trim()).filter(Boolean)
    : ["benchmark", "handoff", "adoption"];
  const estimate = draftNode && Number(draftNode.dataset.issueDraftEstimate) > 0 ? Number(draftNode.dataset.issueDraftEstimate) : 4;
  const newIssue = {
    id: uid("issue"),
    project: project.id,
    title,
    status: "todo",
    priority,
    assignee: "",
    labels,
    due: null,
    estimate,
    sourceKey: key,
    body,
  };
  dashboard.issues.push(newIssue);
  rebuildIndexes();
  commit();
  showToast(`이슈 초안을 생성했습니다: ${newIssue.id}`, "info");
}

function publishReviewHandoffNote(target) {
  const handoff = target.closest("[data-workspace-review-handoff], [data-knowledge-base-review-handoff]");
  const key = target.dataset.reviewNoteKey || "";
  if (!handoff || !key) {
    showToast("발행할 review note를 찾을 수 없습니다", "warn");
    return;
  }
  const existing = dashboard.notes.find((note) => note.sourceKey === key);
  if (existing) {
    showToast(`이미 발행된 노트입니다: ${existing.title}`, "info");
    renderCurrentView();
    return;
  }
  const isKnowledgeBase = !!handoff.closest("[data-knowledge-base-review-handoff]");
  const titlePrefix = target.dataset.reviewNoteTitlePrefix || (isKnowledgeBase ? "[KB/IA Review]" : "[Workspace Review]");
  const sourceKind = target.dataset.reviewNoteKind || (isKnowledgeBase ? "knowledge-base-review-note" : "workspace-review-note");
  const color = target.dataset.reviewNoteColor || (isKnowledgeBase ? "#84cc16" : "#22d3ee");
  const handoffText = handoff.querySelector("[data-review-handoff-text]")?.textContent || "";
  const draftNode = handoff.querySelector("[data-review-issue-draft]");
  const projectName = draftNode ? draftNode.dataset.issueDraftProject || "" : "";
  const issueBody = draftNode ? draftNode.querySelector("[data-issue-draft-body]")?.textContent || "" : "";
  if (!handoffText.trim() || !projectName) {
    showToast("review note 본문을 찾을 수 없습니다", "warn");
    return;
  }
  const note = {
    id: uid("nt"),
    title: `${titlePrefix} ${projectName}`,
    body: [
      handoffText.trim(),
      issueBody.trim() ? "\n## Issue Draft" : "",
      issueBody.trim(),
    ].filter(Boolean).join("\n"),
    color,
    pinned: true,
    updatedAt: nowISO(),
    sourceKey: key,
    sourceKind,
  };
  dashboard.notes.push(note);
  commit();
  showToast(`review note를 발행했습니다: ${note.title}`, "info");
}

function sortPortfolioProjects(projects) {
  if (state.portfolioFilter !== "candidates") return projects;
  if (state.portfolioBenchmarkFilter === "focused") return sortBenchmarkFocusProjects(projects);
  return [...projects].sort((a, b) => {
    const aPriority = projectCandidatePriority(a);
    const bPriority = projectCandidatePriority(b);
    const scoreDiff = (bPriority?.score || 0) - (aPriority?.score || 0);
    if (scoreDiff !== 0) return scoreDiff;
    return String(a.name || "").localeCompare(String(b.name || ""));
  });
}

function renderPortfolio() {
  const view = refs.views["pm-portfolio"];
  if (!view) return;
  if (!state.portfolioFilter) state.portfolioFilter = "all";
  if (!state.portfolioActionFilter) state.portfolioActionFilter = "all";
  if (!state.portfolioBenchmarkFilter) state.portfolioBenchmarkFilter = "all";
  const q = state.query;
  const list = sortPortfolioProjects(dashboard.projects
    .filter((p) => portfolioMatchesFilter(p, state.portfolioFilter))
    .filter((p) => portfolioMatchesActionFilter(p, state.portfolioActionFilter))
    .filter((p) => portfolioMatchesBenchmarkFilter(p, state.portfolioBenchmarkFilter))
    .filter((p) => matches(projectSearchText(p), q)));
  const candidateCount = dashboard.projects.filter((p) => p.sourceKind === "adoption-candidate").length;
  const ownedCount = dashboard.projects.length - candidateCount;
  const benchmarkFocusCount = dashboard.projects.filter((p) => p.sourceKind === "adoption-candidate" && projectBenchmarkFocus(p)).length;
  const filterChips = PORTFOLIO_FILTERS.map((filter) => {
    const count = filter.key === "owned" ? ownedCount : filter.key === "candidates" ? candidateCount : dashboard.projects.length;
    return html`<button type="button" class="seg-chip ${raw(state.portfolioFilter === filter.key ? "is-active" : "")}" data-action="portfolio-filter" data-filter="${filter.key}" aria-pressed="${raw(state.portfolioFilter === filter.key ? "true" : "false")}">${filter.label} ${count}</button>`;
  }).join("");
  const actionCounts = dashboard.projects
    .filter((p) => p.sourceKind === "adoption-candidate")
    .reduce((acc, p) => {
      const key = projectCandidateAction(p)?.key || "feature";
      acc[key] = (acc[key] || 0) + 1;
      return acc;
    }, {});
  const actionFilterChips = CANDIDATE_ACTION_FILTERS
    .filter((filter) => filter.key === "all" || actionCounts[filter.key] || state.portfolioActionFilter === filter.key)
    .map((filter) => {
      const count = filter.key === "all" ? candidateCount : actionCounts[filter.key] || 0;
      return html`<button type="button" class="seg-chip ${raw(state.portfolioActionFilter === filter.key ? "is-active" : "")}" data-action="portfolio-action-filter" data-action-filter="${filter.key}" aria-pressed="${raw(state.portfolioActionFilter === filter.key ? "true" : "false")}">${filter.label} ${count}</button>`;
    }).join("");
  const benchmarkFilterChips = CANDIDATE_BENCHMARK_FILTERS.map((filter) => {
    const count = filter.key === "focused" ? benchmarkFocusCount : candidateCount;
    return html`<button type="button" class="seg-chip ${raw(state.portfolioBenchmarkFilter === filter.key ? "is-active" : "")}" data-action="portfolio-benchmark-filter" data-benchmark-filter="${filter.key}" aria-pressed="${raw(state.portfolioBenchmarkFilter === filter.key ? "true" : "false")}">${filter.label} ${count}</button>`;
  }).join("");
  const actionSummary = candidateActionQueueSummary(dashboard.projects, state.portfolioActionFilter);
  const benchmarkSummary = candidateBenchmarkQueueSummary(dashboard.projects, state.portfolioBenchmarkFilter);
  const benchmarkRubric = candidateBenchmarkRubric(dashboard.projects, state.portfolioBenchmarkFilter);
  const workspaceRubric = candidateWorkspaceRubric(dashboard.projects, state.portfolioBenchmarkFilter);
  const knowledgeBaseRubric = candidateKnowledgeBaseRubric(dashboard.projects, state.portfolioBenchmarkFilter);
  const benchmarkReviewQueue = candidateBenchmarkReviewQueue(dashboard.projects, state.portfolioBenchmarkFilter);

  const stats = {
    total: dashboard.projects.length,
    avg: dashboard.projects.length ? Math.round(dashboard.projects.reduce((a, p) => a + p.progress, 0) / dashboard.projects.length) : 0,
    delayed: dashboard.projects.filter((p) => p.status === "delayed").length,
    risky: dashboard.projects.filter((p) => p.health !== "green").length,
  };

  const kpis = [
    { title: "프로젝트", value: String(stats.total), unit: "개", color: "#2387ff", badge: "▦", delta: "" },
    { title: "평균 진행률", value: String(stats.avg), unit: "%", color: "#17d983", badge: "✺", delta: "▲ 4%p" },
    { title: "지연", value: String(stats.delayed), unit: "건", color: "#ff4d5e", badge: "△", delta: stats.delayed ? "조치 필요" : "없음", trendDown: stats.delayed > 0 },
    { title: "위험 프로젝트", value: String(stats.risky), unit: "건", color: "#f7a928", badge: "⬡", delta: "Amber 이상" },
  ];

  const card = (p) => {
    const burnColor = p.health === "red" ? "var(--red)" : p.health === "amber" ? "var(--amber)" : "var(--green)";
    const category = p.category || "";
    const description = p.description || "";
    return html`
      <article class="portfolio-card panel" data-project-id="${p.id}" data-source-kind="${p.sourceKind || "owned"}">
        <div class="portfolio-head">
          <button type="button" class="portfolio-name-btn" data-action="open-project" data-project-id="${p.id}">
            <strong class="portfolio-name">${p.name}</strong>
            <small>${p.owner} · 마감 ${p.deadline}</small>
          </button>
          <div class="portfolio-head-right">
            <span class="portfolio-health" style="background:${raw(HEALTH_COLOR[p.health])}">${STATUS_LABEL[p.status] || p.status}</span>
            <div class="pm-card-actions">
              <button type="button" class="pm-icon-btn" data-action="project-edit" data-project-id="${p.id}" title="편집">✎</button>
              <button type="button" class="pm-icon-btn pm-icon-btn-del" data-action="project-delete" data-project-id="${p.id}" title="삭제">✕</button>
            </div>
          </div>
        </div>
        ${category || description ? raw(html`
          <div class="portfolio-summary">
            ${category ? raw(html`<span class="portfolio-category">${category}</span>`) : ""}
            ${description ? raw(html`<p>${description}</p>`) : ""}
          </div>
        `) : ""}
        ${raw(projectAdoptionMeta(p))}
        <div class="portfolio-body">
          <div class="donut portfolio-donut" style="--value:${raw(p.progress)}">
            <span>진행률</span>
            <strong>${p.progress}%</strong>
          </div>
          <div class="portfolio-meta">
            <div class="portfolio-spark">${raw(spark(p.burn, burnColor))}</div>
            <div class="portfolio-meta-rows">
              <span><b>이슈</b> ${p.openIssues}</span>
              <span><b>위험</b> ${p.risks}</span>
              <span><b>팀</b> ${p.members.length}명</span>
            </div>
          </div>
        </div>
      </article>
    `;
  };

  setHTML(view, html`
    <section class="kpis">${raw(kpis.map((k) => kpiCard(k)).join(""))}</section>
    <div class="portfolio-toolbar">
      <div class="seg-control" aria-label="포트폴리오 필터">${raw(filterChips)}</div>
      <button type="button" class="primary-btn" data-action="project-add">+ 새 프로젝트</button>
    </div>
    <div class="portfolio-action-filter" data-candidate-action-filter-panel>
      <div class="seg-control" aria-label="후보 액션 필터">${raw(actionFilterChips)}</div>
    </div>
    <div class="portfolio-benchmark-filter" data-candidate-benchmark-filter-panel>
      <div class="seg-control" aria-label="후보 벤치 필터">${raw(benchmarkFilterChips)}</div>
    </div>
    ${raw(actionSummary)}
    ${raw(benchmarkSummary)}
    ${raw(benchmarkRubric)}
    ${raw(workspaceRubric)}
    ${raw(knowledgeBaseRubric)}
    ${raw(benchmarkReviewQueue)}
    <section class="portfolio-grid">
      ${list.length === 0 ? raw(html`<article class="empty">일치하는 프로젝트가 없습니다.</article>`) : raw(list.map(card).join(""))}
    </section>
  `);
}

/* ============================================================
 * View: Kanban
 * ============================================================ */

function renderKanban() {
  const view = refs.views["pm-kanban"];
  if (!view) return;
  const q = state.query;
  const pf = state.kanbanFilter;
  const all = dashboard.issues
    .filter((i) => i.project === dashboard.currentProjectId)
    .filter((i) => !pf || i.priority === pf)
    .filter((i) => matches(`${i.id} ${i.title} ${i.assignee} ${i.labels.join(" ")}`, q));

  const columns = ["todo", "in-progress", "review", "done"];
  const counts = columns.reduce((acc, c) => { acc[c] = all.filter((i) => i.status === c).length; return acc; }, {});
  const kpis = columns.map((c) => ({
    title: STATUS_LABEL[c], value: String(counts[c]), unit: "건",
    color: c === "todo" ? "#7f91ad" : c === "in-progress" ? "#22d3ee" : c === "review" ? "#a970ff" : "#17d983",
    badge: c === "done" ? "✓" : c === "review" ? "◐" : c === "in-progress" ? "◑" : "○",
    delta: "",
  }));

  const filterChips = ["crit", "high", "med", "low"].map((p) => html`
    <button type="button" class="kanban-chip priority-${raw(p)} ${raw(pf === p ? "is-active" : "")}" data-action="filter-kanban" data-priority="${p}" aria-pressed="${raw(pf === p ? "true" : "false")}">${PRIORITY_LABEL[p]}</button>
  `).join("");

  const NEXT_STATUS = { todo: "in-progress", "in-progress": "review", review: "done", done: "todo" };
  const PREV_STATUS = { todo: "done", "in-progress": "todo", review: "in-progress", done: "review" };

  const col = (status) => {
    const items = all.filter((i) => i.status === status);
    return html`
      <div class="kanban-col" data-kanban-col="${status}">
        <div class="kanban-col-head">
          <strong>${STATUS_LABEL[status]}</strong>
          <div class="kanban-col-head-right">
            <span class="kanban-count">${items.length}</span>
            <button type="button" class="kanban-add-btn" data-action="issue-add" title="이슈 추가">+</button>
          </div>
        </div>
        <div class="kanban-list" data-kanban-drop="${status}">
          ${items.length === 0 ? raw(html`<div class="kanban-empty" data-kanban-drop="${status}">없음</div>`) : raw(items.map((i) => {
            const prevSt = PREV_STATUS[i.status];
            const nextSt = NEXT_STATUS[i.status];
            return html`
            <div class="kanban-card-wrap" draggable="true" data-issue-id="${i.id}">
              <div class="kanban-card priority-${raw(i.priority)}">
                <div class="kanban-card-head">
                  <span class="kanban-id">${i.id}</span>
                  <div class="kanban-card-head-right">
                    <span class="kanban-priority priority-${raw(i.priority)}">${PRIORITY_LABEL[i.priority]}</span>
                    <div class="pm-card-actions">
                      <button type="button" class="pm-icon-btn" data-action="issue-edit" data-issue-id="${i.id}" title="편집">✎</button>
                      <button type="button" class="pm-icon-btn pm-icon-btn-del" data-action="issue-delete" data-issue-id="${i.id}" title="삭제">✕</button>
                    </div>
                  </div>
                </div>
                <button type="button" class="kanban-title-btn" data-action="open-issue" data-issue-id="${i.id}">
                  <strong class="kanban-title">${i.title}</strong>
                </button>
                <div class="kanban-card-foot">
                  <span class="kanban-assignee">${memberName(i.assignee)}</span>
                  <span class="kanban-due">${i.due ? formatMonthDay(i.due) : "—"}</span>
                </div>
                <div class="kanban-labels">${i.labels.map((l) => raw(html`<span class="kanban-label">#${l}</span>`))}</div>
                <div class="kanban-move-btns">
                  <button type="button" class="kanban-move-btn" data-action="issue-move" data-issue-id="${i.id}" data-status="${prevSt}" title="◀ ${STATUS_LABEL[prevSt]}">◀</button>
                  <button type="button" class="kanban-move-btn" data-action="issue-move" data-issue-id="${i.id}" data-status="${nextSt}" title="▶ ${STATUS_LABEL[nextSt]}">▶</button>
                </div>
              </div>
            </div>`;
          }).join(""))}
        </div>
      </div>
    `;
  };

  setHTML(view, html`
    <section class="kpis kpis-4">${raw(kpis.map((k) => kpiCard(k)).join(""))}</section>
    <section class="panel kanban-panel">
      ${raw(panelHead(`Kanban — ${projectName(dashboard.currentProjectId)}`, null, html`
        <div class="kanban-filters">
          <span class="kanban-filters-label">우선순위</span>
          ${raw(filterChips)}
          ${pf ? raw(html`<button type="button" class="kanban-chip-clear" data-action="filter-kanban" data-priority="">해제</button>`) : ""}
          <button type="button" class="primary-btn kanban-global-add" data-action="issue-add">+ 이슈</button>
        </div>
      `))}
      <div class="kanban" id="kanbanBoard">
        ${raw(columns.map(col).join(""))}
      </div>
    </section>
  `);
  // Drag-and-drop: wire after render
  setupKanbanDrag();
}

/* ============================================================
 * View: Gantt
 * ============================================================ */

function renderGantt() {
  const view = refs.views["pm-gantt"];
  if (!view) return;
  const q = state.query;
  const tasks = dashboard.gantt.tasks.filter((t) => matches(`${t.name} ${t.owner} ${t.project}`, q));

  const rangeStart = dashboard.gantt.rangeStart;
  const rangeEnd = dashboard.gantt.rangeEnd;
  const totalDays = daysBetween(rangeStart, rangeEnd);
  const DAY_PX = 12;
  const ROW_H = 30;
  const TOP_PAD = 30;
  const svgW = totalDays * DAY_PX;
  const svgH = TOP_PAD + tasks.length * ROW_H + 20;
  const dayToX = (d) => daysBetween(rangeStart, d) * DAY_PX;

  const milestones = tasks.filter((t) => t.milestone).length;
  const today = todayISO();
  const dueSoon = tasks.filter((t) => !t.milestone && daysBetween(today, t.end) >= 0 && daysBetween(today, t.end) <= 7).length;
  const overdue = tasks.filter((t) => !t.milestone && daysBetween(t.end, today) > 0).length;
  const depViolations = tasks.filter((t) => t.deps.some((d) => {
    const dep = dashboard.gantt.tasks.find((x) => x.id === d);
    return dep && daysBetween(dep.end, t.start) < 0;
  })).length;

  const kpis = [
    { title: "마일스톤",       value: String(milestones), unit: "개", color: "#a970ff", badge: "◆", delta: "" },
    { title: "임박 데드라인",   value: String(dueSoon),    unit: "건", color: "#f7a928", badge: "△", delta: "7일 이내" },
    { title: "지연",            value: String(overdue),    unit: "건", color: "#ff4d5e", badge: "✕", delta: overdue ? "조치 필요" : "없음", trendDown: overdue > 0 },
    { title: "의존 충돌",        value: String(depViolations), unit: "건", color: "#f7a928", badge: "↔", delta: depViolations ? "주의" : "정상" },
  ];

  // Month grid lines + labels
  const months = [];
  let cursor = parseDate(rangeStart);
  cursor.setUTCDate(1);
  while (cursor < parseDate(rangeEnd)) {
    const s = `${cursor.getUTCFullYear()}-${String(cursor.getUTCMonth() + 1).padStart(2, "0")}-01`;
    months.push(s);
    cursor.setUTCMonth(cursor.getUTCMonth() + 1);
  }
  const monthLines = months.map((m) => {
    const x = dayToX(m);
    return `<line class="gantt-month-line" x1="${x}" y1="0" x2="${x}" y2="${svgH}"/>
            <text class="gantt-month-label" x="${x + 4}" y="16">${escapeHtml(m.slice(0, 7))}</text>`;
  }).join("");

  // Today line
  const todayX = dayToX(today);
  const todayLine = `<line class="gantt-today-line" x1="${todayX}" y1="0" x2="${todayX}" y2="${svgH}"/>
                     <text class="gantt-today-label" x="${todayX + 4}" y="${svgH - 4}">오늘</text>`;

  // Task rows (background row stripes)
  const rowStripes = tasks.map((_, idx) => `<rect class="gantt-row-bg" x="0" y="${TOP_PAD + idx * ROW_H}" width="${svgW}" height="${ROW_H}"/>`).join("");

  // Bars and milestones
  const bars = tasks.map((t, idx) => {
    const y = TOP_PAD + idx * ROW_H + 6;
    const cls = `gantt-bar gantt-bar-${t.color}`;
    if (t.milestone) {
      const cx = dayToX(t.start) + 6;
      const cy = TOP_PAD + idx * ROW_H + ROW_H / 2;
      const r = 8;
      return `<polygon class="gantt-milestone gantt-bar-${t.color}" data-action="open-task" data-task-id="${escapeHtml(t.id)}" points="${cx},${cy - r} ${cx + r},${cy} ${cx},${cy + r} ${cx - r},${cy}" tabindex="0"><title>${escapeHtml(t.name)} · ${escapeHtml(t.start)}</title></polygon>`;
    }
    const x = dayToX(t.start);
    const w = Math.max(6, (daysBetween(t.start, t.end)) * DAY_PX);
    return `<g class="${cls}" data-action="open-task" data-task-id="${escapeHtml(t.id)}" tabindex="0">
      <rect class="gantt-bar-rect" x="${x}" y="${y}" width="${w}" height="${ROW_H - 12}" rx="4"/>
      <text class="gantt-bar-label" x="${x + 6}" y="${y + (ROW_H - 12) / 2 + 4}">${escapeHtml(t.name)}</text>
      <title>${escapeHtml(t.name)} · ${escapeHtml(t.start)} → ${escapeHtml(t.end)}</title>
    </g>`;
  }).join("");

  // Dependencies (right-angle polyline)
  const depLines = tasks.flatMap((t, idx) => t.deps.map((depId) => {
    const fromIdx = tasks.findIndex((x) => x.id === depId);
    if (fromIdx < 0) return "";
    const from = tasks[fromIdx];
    const x1 = dayToX(from.end);
    const y1 = TOP_PAD + fromIdx * ROW_H + ROW_H / 2;
    const x2 = dayToX(t.start);
    const y2 = TOP_PAD + idx * ROW_H + ROW_H / 2;
    const midX = (x1 + x2) / 2;
    return `<polyline class="gantt-dep" points="${x1},${y1} ${midX},${y1} ${midX},${y2} ${x2},${y2}"/>
            <polygon class="gantt-dep-arrow" points="${x2 - 6},${y2 - 3} ${x2},${y2} ${x2 - 6},${y2 + 3}"/>`;
  })).join("");

  const labels = tasks.map((t) => html`
    <div class="gantt-label-row-wrap">
      <button type="button" class="gantt-label-row" data-action="open-task" data-task-id="${t.id}">
        <span class="gantt-label-name">${t.milestone ? raw("◆ ") : ""}${t.name}</span>
        <small class="gantt-label-meta">${projectName(t.project)} · ${memberName(t.owner)}</small>
      </button>
      <div class="gantt-row-actions">
        <button type="button" class="pm-icon-btn" data-action="task-edit" data-task-id="${t.id}" title="편집">✎</button>
        <button type="button" class="pm-icon-btn pm-icon-btn-del" data-action="task-delete" data-task-id="${t.id}" title="삭제">✕</button>
      </div>
    </div>
  `).join("");

  setHTML(view, html`
    <section class="kpis kpis-4">${raw(kpis.map((k) => kpiCard(k)).join(""))}</section>
    <section class="panel gantt-panel">
      ${raw(panelHead("간트 차트", null, html`<button type="button" class="primary-btn" data-action="task-add">+ 작업 추가</button>`))}
      <div class="gantt">
        <div class="gantt-labels">
          <div class="gantt-labels-head">작업</div>
          ${raw(labels)}
        </div>
        <div class="gantt-svg-wrap">
          <svg class="gantt-svg" viewBox="0 0 ${svgW} ${svgH}" preserveAspectRatio="none" style="height:${svgH}px; min-width:${svgW}px">
            ${raw(rowStripes)}
            ${raw(monthLines)}
            ${raw(todayLine)}
            ${raw(depLines)}
            ${raw(bars)}
          </svg>
        </div>
      </div>
    </section>
  `);
}

/* ============================================================
 * View: Team / Resources
 * ============================================================ */

function renderTeam() {
  const view = refs.views["pm-team"];
  if (!view) return;
  const q = state.query;
  const list = dashboard.team.filter((m) => matches(`${m.name} ${m.role}`, q));

  const total = dashboard.team.length;
  const avgLoad = Math.round(dashboard.team.filter((m) => !m.onLeave).reduce((a, m) => a + m.load, 0) / Math.max(1, dashboard.team.filter((m) => !m.onLeave).length));
  const over = dashboard.team.filter((m) => m.load > 85).length;
  const leave = dashboard.team.filter((m) => m.onLeave).length;

  const kpis = [
    { title: "팀원",          value: String(total),   unit: "명", color: "#2387ff", badge: "◈", delta: "" },
    { title: "평균 부하",      value: String(avgLoad), unit: "%", color: "#22d3ee", badge: "✺", delta: "" },
    { title: "오버할당",       value: String(over),    unit: "명", color: "#ff4d5e", badge: "△", delta: over ? "조치 필요" : "없음", trendDown: over > 0 },
    { title: "휴가 중",        value: String(leave),   unit: "명", color: "#a970ff", badge: "◎", delta: "" },
  ];

  const loadColor = (n) => n > 85 ? "var(--red)" : n > 65 ? "var(--amber)" : "var(--green)";
  const memberRow = (m) => html`
    <div class="team-row-wrap">
      <button type="button" class="team-row" data-action="open-member" data-member-id="${m.id}">
        <div class="team-row-name">
          <span class="team-avatar" aria-hidden="true">${m.name.slice(0, 1)}</span>
          <div>
            <strong>${m.name}</strong>
            <small>${m.role}${m.onLeave ? raw(" · <em class=\"team-leave\">휴가</em>") : ""}</small>
          </div>
        </div>
        <div class="team-projects">${m.projects.length === 0 ? raw(html`<small>—</small>`) : m.projects.map((pid) => raw(html`<span class="team-project-pill">${projectName(pid)}</span>`))}</div>
        <div class="team-load">
          <div class="load-bar"><i style="--w:${raw(m.load)}%; background:${raw(loadColor(m.load))}"></i></div>
          <b>${m.load}%</b>
        </div>
      </button>
      <div class="team-row-actions">
        <button type="button" class="pm-icon-btn" data-action="member-edit" data-member-id="${m.id}" title="편집">✎</button>
        <button type="button" class="pm-icon-btn pm-icon-btn-del" data-action="member-delete" data-member-id="${m.id}" title="삭제">✕</button>
      </div>
    </div>
  `;

  // Matrix: members × projects
  const projs = dashboard.projects;
  const matrixHead = html`
    <div class="team-matrix-row team-matrix-head">
      <div></div>
      ${projs.map((p) => raw(html`<div class="team-matrix-col-head"><small>${p.name}</small></div>`))}
    </div>
  `;
  const matrixRows = list.map((m) => html`
    <div class="team-matrix-row">
      <div class="team-matrix-row-head">
        <strong>${m.name}</strong>
        <small>${m.role}</small>
      </div>
      ${projs.map((p) => {
        const assigned = m.projects.includes(p.id);
        const issueCount = dashboard.issues.filter((i) => i.assignee === m.id && i.project === p.id && i.status !== "done").length;
        return raw(html`
          <div class="team-matrix-cell ${raw(assigned ? "is-assigned" : "")}">
            ${assigned ? raw(html`<b>${issueCount}</b><small>이슈</small>`) : raw(html`<span class="team-matrix-dash">·</span>`)}
          </div>
        `);
      })}
    </div>
  `).join("");

  setHTML(view, html`
    <section class="kpis kpis-4">${raw(kpis.map((k) => kpiCard(k)).join(""))}</section>
    <section class="team-layout">
      <article class="panel team-list-panel">
        ${raw(panelHead("팀 멤버", null, html`<button type="button" class="primary-btn" data-action="member-add">+ 멤버 추가</button>`))}
        <div class="team-list">
          ${list.length === 0 ? raw(html`<article class="empty">일치하는 멤버가 없습니다.</article>`) : raw(list.map(memberRow).join(""))}
        </div>
      </article>
      <article class="panel team-matrix-panel">
        ${raw(panelHead("프로젝트 매트릭스", null, ""))}
        <div class="team-matrix">
          ${raw(matrixHead)}
          ${raw(matrixRows)}
        </div>
      </article>
    </section>
  `);
}

/* ============================================================
 * View: DB Instances
 * ============================================================ */

function renderDbInstances() {
  const view = refs.views["dbm-instances"];
  if (!view) return;
  const q = state.query;
  const list = dashboard.dbInstances.filter((d) => matches(`${d.name} ${d.engine} ${d.region}`, q));
  const inst = currentInstance();
  const cur = inst ? (list.find((d) => d.id === inst.id) || list[0] || inst) : (list[0] || null);

  const totalConn = dashboard.dbInstances.reduce((a, d) => a + d.conn, 0);
  const avgCpu = dashboard.dbInstances.length
    ? Math.round(dashboard.dbInstances.reduce((a, d) => a + d.cpu, 0) / dashboard.dbInstances.length)
    : 0;
  const unhealthy = dashboard.dbInstances.filter((d) => d.health !== "green").length;

  const kpis = [
    { title: "인스턴스",   value: String(dashboard.dbInstances.length), unit: "대", color: "#2387ff", badge: "✺", delta: "" },
    { title: "평균 CPU",   value: String(avgCpu),                       unit: "%", color: "#22d3ee", badge: "▣", delta: "" },
    { title: "연결 합계",   value: String(totalConn),                   unit: "건", color: "#a970ff", badge: "◉", delta: "" },
    { title: "비정상",     value: String(unhealthy),                   unit: "건", color: unhealthy ? "#ff4d5e" : "#17d983", badge: "△", delta: unhealthy ? "주의" : "정상", trendDown: unhealthy > 0 },
  ];

  const card = (d) => html`
    <div class="db-card-wrap">
      <button type="button" class="db-card ${raw(cur && d.id === cur.id ? "is-current" : "")}" data-action="pick-instance" data-instance-id="${d.id}">
        <div class="db-card-head">
          <strong>${d.name}</strong>
          <span class="db-health" style="background:${raw(HEALTH_COLOR[d.health])}"></span>
        </div>
        <small>${d.engine}</small>
        <div class="db-card-stats">
          <span><b>${d.cpu}%</b><small>CPU</small></span>
          <span><b>${d.conn}</b><small>conn</small></span>
          <span><b>${d.latencyMs}ms</b><small>지연</small></span>
        </div>
      </button>
      <div class="db-card-actions">
        <button type="button" class="pm-icon-btn" data-action="instance-edit" data-instance-id="${d.id}" title="편집">✎</button>
        <button type="button" class="pm-icon-btn pm-icon-btn-del" data-action="instance-delete" data-instance-id="${d.id}" title="삭제">✕</button>
      </div>
    </div>
  `;

  const detail = cur ? html`
    ${raw(panelHead(cur.name, null, html`<small>${cur.engine} · ${cur.region}</small>`))}
    <div class="db-detail">
      <div class="db-gauges">
        <div class="gauge db-gauge" style="--g:${raw(cur.cpu)}"><span>CPU</span><b>${cur.cpu}%</b></div>
        <div class="gauge db-gauge" style="--g:${raw(cur.mem)}"><span>메모리</span><b>${cur.mem}%</b></div>
        <div class="gauge db-gauge" style="--g:${raw(Math.round((cur.conn / cur.connMax) * 100))}"><span>연결</span><b>${cur.conn}/${cur.connMax}</b></div>
      </div>
      <div class="db-spark-row">
        <div class="db-spark">
          <strong>연결 추이 (24h)</strong>
          ${raw(spark(cur.series, "#22d3ee"))}
        </div>
        <div class="db-meta">
          <span><b>지연</b> ${cur.latencyMs}ms</span>
          <span><b>리전</b> ${cur.region}</span>
          <span><b>상태</b> <em style="color:${raw(HEALTH_COLOR[cur.health])}">● ${cur.health}</em></span>
        </div>
      </div>
    </div>
  ` : html`
    ${raw(panelHead("인스턴스 없음", null, ""))}
    <article class="empty">등록된 DB 인스턴스가 없습니다. 새 인스턴스를 추가하세요.</article>
  `;

  setHTML(view, html`
    <section class="kpis kpis-4">${raw(kpis.map((k) => kpiCard(k)).join(""))}</section>
    <section class="db-layout">
      <article class="panel db-list-panel">
        ${raw(panelHead("인스턴스", null, html`<button type="button" class="primary-btn" data-action="instance-add">+ 인스턴스 추가</button>`))}
        <div class="db-list">
          ${list.length === 0 ? raw(html`<article class="empty">일치하는 인스턴스가 없습니다.</article>`) : raw(list.map(card).join(""))}
        </div>
      </article>
      <article class="panel db-detail-panel">
        ${raw(detail)}
      </article>
    </section>
  `);
}

/* ============================================================
 * View: DB Schema
 * ============================================================ */

function renderDbSchema() {
  const view = refs.views["dbm-schema"];
  if (!view) return;
  const q = state.query;

  // Compute selected table (default: first table of current instance's first db)
  let selected = state.schemaSelectedTable;
  if (!selected && dashboard.schemas.length) {
    const cur = dashboard.schemas.find((s) => s.id === dashboard.currentInstanceId) || dashboard.schemas[0];
    const firstDb = cur && cur.databases ? cur.databases[0] : null;
    const firstTable = firstDb && firstDb.tables[0];
    if (firstTable) selected = firstTable.id;
  }

  const allTables = dashboard.schemas.flatMap((s) =>
    (s.databases || []).flatMap((db) => (db.tables || []).map((t) => ({ ...t, instance: s.id, db: db.name }))));
  const selectedTable = allTables.find((t) => t.id === selected) || allTables[0] || null;

  const totalDbs = dashboard.schemas.reduce((a, s) => a + (s.databases || []).length, 0);
  const totalTables = allTables.length;
  const totalIdx = allTables.reduce((a, t) => a + (t.indexes ? t.indexes.length : 0), 0);
  const totalFk = allTables.reduce((a, t) => a + (t.fks ? t.fks.length : 0), 0);

  const kpis = [
    { title: "DB",      value: String(totalDbs),    unit: "개", color: "#2387ff", badge: "◎", delta: "" },
    { title: "테이블",   value: String(totalTables),  unit: "개", color: "#22d3ee", badge: "▦", delta: "" },
    { title: "인덱스",   value: String(totalIdx),     unit: "개", color: "#a970ff", badge: "▣", delta: "" },
    { title: "FK 관계",  value: String(totalFk),     unit: "개", color: "#17d983", badge: "↔", delta: "" },
  ];

  // Tree
  const tree = dashboard.schemas.length === 0 ? html`<article class="empty">등록된 스키마가 없습니다. 테이블을 추가하세요.</article>` : dashboard.schemas.map((s) => {
    const inst = dashboard.dbInstances.find((d) => d.id === s.id);
    const expanded = state.schemaExpanded.has(s.id);
    const dbs = (s.databases || []).map((db) => html`
      <details class="schema-db" open>
        <summary>${db.name}</summary>
        <ul>${(db.tables || []).filter((t) => matches(`${t.name} ${(t.columns || []).map((c) => c.name).join(" ")}`, q)).map((t) => raw(html`
          <li class="schema-table-li">
            <button type="button" class="schema-table-btn ${raw(selectedTable && t.id === selectedTable.id ? "is-current" : "")}" data-action="open-table" data-table-id="${t.id}">
              <span>${t.name}</span>
              <em>${(t.rows || 0).toLocaleString()}</em>
            </button>
            <div class="schema-table-actions">
              <button type="button" class="pm-icon-btn" data-action="table-edit" data-table-id="${t.id}" title="편집">✎</button>
              <button type="button" class="pm-icon-btn pm-icon-btn-del" data-action="table-delete" data-table-id="${t.id}" title="삭제">✕</button>
            </div>
          </li>
        `))}</ul>
      </details>
    `).join("");
    return html`
      <details class="schema-inst" ${raw(expanded ? "open" : "")} data-instance-id="${s.id}">
        <summary><strong>${inst ? inst.name : s.id}</strong><small>${inst ? inst.engine : ""}</small></summary>
        ${raw(dbs)}
      </details>
    `;
  }).join("");

  // Columns table
  const selectedColumns = selectedTable && Array.isArray(selectedTable.columns) ? selectedTable.columns : [];
  const columnsBody = selectedTable ? html`
    <table class="schema-columns-table">
      <thead><tr><th>컬럼</th><th>타입</th><th>제약</th><th>인덱스</th></tr></thead>
      <tbody>${selectedColumns.map((c) => raw(html`
        <tr>
          <td><strong>${c.name}</strong></td>
          <td><code>${c.type}</code></td>
          <td>
            ${c.pk ? raw(html`<span class="col-flag flag-pk">PK</span>`) : ""}
            ${c.fk ? raw(html`<span class="col-flag flag-fk">FK→${c.fk}</span>`) : ""}
            ${c.nullable === false ? raw(html`<span class="col-flag flag-nn">NOT NULL</span>`) : ""}
          </td>
          <td>${(c.idx || []).map((i) => raw(html`<small class="col-idx">${i}</small>`))}</td>
        </tr>
      `))}</tbody>
    </table>
  ` : html`<article class="empty">테이블을 선택하세요.</article>`;

  // Indexes / FK panel
  const selectedIndexes = selectedTable && Array.isArray(selectedTable.indexes) ? selectedTable.indexes : [];
  const selectedFks = selectedTable && Array.isArray(selectedTable.fks) ? selectedTable.fks : [];
  const relBody = selectedTable ? html`
    <div class="schema-rel-block">
      <h4>인덱스</h4>
      ${selectedIndexes.length === 0 ? raw(html`<small class="empty-line">없음</small>`) : raw(selectedIndexes.map((i) => html`
        <div class="schema-rel-row">
          <strong>${i.name}</strong>
          <code>(${i.cols.join(", ")})</code>
          ${i.unique ? raw(html`<span class="col-flag flag-pk">UNIQUE</span>`) : ""}
        </div>
      `).join(""))}
    </div>
    <div class="schema-rel-block">
      <h4>외래키</h4>
      ${selectedFks.length === 0 ? raw(html`<small class="empty-line">없음</small>`) : raw(selectedFks.map((f) => html`
        <div class="schema-rel-row">
          <code>${f.col}</code>
          <span>→</span>
          <code>${f.refs}</code>
        </div>
      `).join(""))}
    </div>
    <div class="schema-rel-block">
      <h4>메타</h4>
      <small><b>행 수</b> ${(selectedTable.rows || 0).toLocaleString()}</small>
      <small><b>크기</b> ${selectedTable.sizeMb || 0} MB</small>
      <small><b>위치</b> ${selectedTable.instance || ""} · ${selectedTable.db || ""}</small>
    </div>
  ` : "";

  setHTML(view, html`
    <section class="kpis kpis-4">${raw(kpis.map((k) => kpiCard(k)).join(""))}</section>
    <section class="schema-pane">
      <article class="panel schema-tree-panel">
        ${raw(panelHead("스키마", null, html`<button type="button" class="primary-btn" data-action="table-add">+ 테이블 추가</button>`))}
        <div class="schema-tree">${raw(tree)}</div>
      </article>
      <article class="panel schema-columns-panel">
        ${raw(panelHead(selectedTable ? `${selectedTable.db}.${selectedTable.name}` : "테이블", null, ""))}
        ${raw(columnsBody)}
      </article>
      <article class="panel schema-rel-panel">
        ${raw(panelHead("인덱스 / 관계", null, ""))}
        ${raw(relBody)}
      </article>
    </section>
  `);
}

/* ============================================================
 * View: DB Queries
 * ============================================================ */

function renderDbQueries() {
  const view = refs.views["dbm-queries"];
  if (!view) return;
  const q = state.query;
  const list = dashboard.queries.filter((x) => matches(`${x.id} ${x.text} ${x.db} ${x.instance}`, q));

  const total = dashboard.queries.length;
  const avg = total ? Math.round(dashboard.queries.reduce((a, x) => a + x.avgMs, 0) / total) : 0;
  const p95 = total ? Math.round(dashboard.queries.reduce((a, x) => a + x.p95Ms, 0) / total) : 0;
  const tps = total ? Math.round(dashboard.queries.reduce((a, x) => a + x.count, 0) / 24) : 0;

  const kpis = [
    { title: "slow query",  value: String(total), unit: "건", color: "#ff4d5e", badge: "◉", delta: "" },
    { title: "평균 ms",      value: String(avg),  unit: "ms", color: "#22d3ee", badge: "▣", delta: "" },
    { title: "평균 p95",      value: String(p95),  unit: "ms", color: "#a970ff", badge: "✺", delta: "" },
    { title: "시간당 처리",   value: String(tps), unit: "건/h", color: "#17d983", badge: "✓", delta: "" },
  ];

  // Histogram
  const buckets = dashboard.queryHistogram;
  const maxC = Math.max(1, ...buckets.map((b) => b.count));
  const barW = 28;
  const gap = 8;
  const histW = (barW + gap) * buckets.length + gap;
  const histH = 160;
  const baseY = histH - 30;
  const histSvg = `<svg class="histogram" viewBox="0 0 ${histW} ${histH}">
    ${buckets.map((b, i) => {
      const h = Math.round(((b.count) / maxC) * (baseY - 10));
      const x = gap + i * (barW + gap);
      const y = baseY - h;
      return `<g class="hist-group"><rect class="hist-bar" x="${x}" y="${y}" width="${barW}" height="${h}" rx="3"><title>${escapeHtml(b.bucket)}: ${b.count}건</title></rect>
        <text class="hist-bar-count" x="${x + barW / 2}" y="${y - 4}" text-anchor="middle">${b.count}</text>
        <text class="hist-bar-label" x="${x + barW / 2}" y="${baseY + 14}" text-anchor="middle">${escapeHtml(b.bucket)}</text>
      </g>`;
    }).join("")}
    <line x1="0" x2="${histW}" y1="${baseY}" y2="${baseY}" class="hist-axis"/>
  </svg>`;

  // Trend sparkline (synthetic from histogram)
  const trendPoints = [12, 18, 22, 24, 28, 34, 30, 36, 42, 38, 32, 28, 26];

  // Top-N table
  const rows = list.map((qi) => html`
    <tr>
      <td><button type="button" class="query-id-btn" data-action="open-query" data-query-id="${qi.id}">${qi.id}</button></td>
      <td><code class="query-text">${qi.text}</code></td>
      <td>${qi.instance}/${qi.db}</td>
      <td class="query-num">${qi.avgMs}</td>
      <td class="query-num">${qi.p95Ms}</td>
      <td class="query-num">${qi.count}</td>
      <td>${qi.lastRun}</td>
      <td class="query-actions-cell">
        <button type="button" class="pm-icon-btn" data-action="query-edit" data-query-id="${qi.id}" title="편집">✎</button>
        <button type="button" class="pm-icon-btn pm-icon-btn-del" data-action="query-delete" data-query-id="${qi.id}" title="삭제">✕</button>
      </td>
    </tr>
  `).join("");

  setHTML(view, html`
    <section class="kpis kpis-4">${raw(kpis.map((k) => kpiCard(k)).join(""))}</section>
    <section class="queries-row">
      <article class="panel queries-trend-panel">
        ${raw(panelHead("실행 시간 추세 (24h)", null, html`<small>p95 평균 ${p95}ms</small>`))}
        <div class="queries-trend">${raw(spark(trendPoints, "#22d3ee"))}</div>
      </article>
      <article class="panel queries-hist-panel">
        ${raw(panelHead("실행 시간 분포 (ms)", null, ""))}
        <div class="histogram-wrap">${raw(histSvg)}</div>
      </article>
    </section>
    <section class="panel queries-table-panel">
      ${raw(panelHead("저장 쿼리", null, html`<button type="button" class="primary-btn" data-action="query-add">+ 쿼리 추가</button>`))}
      <div class="query-table-wrap">
        <table class="query-table">
          <thead><tr><th>ID</th><th>SQL</th><th>인스턴스/DB</th><th>평균(ms)</th><th>p95(ms)</th><th>호출</th><th>최근 실행</th><th>관리</th></tr></thead>
          <tbody>${raw(rows || html`<tr><td colspan="8"><div class="empty">저장된 쿼리가 없습니다.</div></td></tr>`)}</tbody>
        </table>
      </div>
    </section>
  `);
}

/* ============================================================
 * View: DB Backups / Migrations
 * ============================================================ */

function renderDbBackups() {
  const view = refs.views["dbm-backups"];
  if (!view) return;
  const q = state.query;

  const today = todayISO();
  const todayIdx = dashboard.backups.findIndex((b) => b.date >= today);
  const nextScheduled = dashboard.migrations.find((m) => m.scheduledAt);
  const total = dashboard.backups.length;
  const ok = dashboard.backups.filter((b) => b.status === "ok").length;
  const successRate = Math.round((ok / total) * 1000) / 10;
  const avgSec = Math.round(dashboard.backups.filter((b) => b.status !== "fail").reduce((a, b) => a + b.durationS, 0) / Math.max(1, dashboard.backups.filter((b) => b.status !== "fail").length));
  const pendingMig = dashboard.migrations.filter((m) => m.status === "pending").length;

  const kpis = [
    { title: "다음 백업",     value: nextScheduled ? nextScheduled.scheduledAt.slice(5, 10) : "오늘", unit: "", color: "#2387ff", badge: "⏱", delta: nextScheduled ? `${nextScheduled.scheduledAt.slice(11)}` : "예정" },
    { title: "성공률",        value: String(successRate), unit: "%", color: "#17d983", badge: "✓", delta: "" },
    { title: "평균 소요",     value: String(avgSec),      unit: "초", color: "#22d3ee", badge: "✺", delta: "" },
    { title: "대기 마이그",    value: String(pendingMig),  unit: "건", color: "#a970ff", badge: "↻", delta: "예정 작업" },
  ];

  // Calendar: 7×5 grid spanning the backups date range
  const start = parseDate(dashboard.backups[0].date);
  // Find first Monday on or before start
  const weekStart = new Date(start);
  weekStart.setUTCDate(weekStart.getUTCDate() - ((weekStart.getUTCDay() + 6) % 7));
  const calCells = [];
  for (let i = 0; i < 35; i++) {
    const d = new Date(weekStart);
    d.setUTCDate(d.getUTCDate() + i);
    const iso = `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}-${String(d.getUTCDate()).padStart(2, "0")}`;
    const dayBackups = dashboard.backups.filter((b) => b.date === iso && matches(`${b.instance} ${b.note}`, q));
    const hasFail = dayBackups.some((b) => b.status === "fail");
    const hasWarn = dayBackups.some((b) => b.status === "warn");
    const inRange = iso >= dashboard.backups[0].date && iso <= dashboard.backups[dashboard.backups.length - 1].date;
    const isToday = iso === today;
    const cls = ["cal-cell", inRange ? "" : "is-out", isToday ? "is-today" : "", hasFail ? "has-fail" : (hasWarn ? "has-warn" : (dayBackups.length ? "has-ok" : ""))].join(" ");
    calCells.push(html`
      <button type="button" class="${raw(cls)}" data-action="open-backup" data-date="${iso}" ${dayBackups.length === 0 ? raw("disabled") : ""}>
        <small class="cal-date">${d.getUTCDate()}</small>
        <div class="cal-dots">
          ${dayBackups.map((b) => raw(html`<span class="cal-dot cal-dot-${b.status}" title="${b.instance} (${b.status})"></span>`))}
        </div>
      </button>
    `);
  }

  const weekHeads = ["월", "화", "수", "목", "금", "토", "일"].map((w) => html`<div class="cal-weekhead">${w}</div>`).join("");

  // Migrations timeline (reverse chronological)
  const migRows = [...dashboard.migrations].reverse().map((m) => html`
    <div class="mig-row-wrap">
      <button type="button" class="mig-row mig-${raw(m.status)}" data-action="open-migration" data-mig-id="${m.id}">
        <span class="mig-dot"></span>
        <div class="mig-body">
          <strong>${m.title}</strong>
          <small>${m.id} · ${m.instance}</small>
          <em>${m.appliedAt || m.scheduledAt || ""}</em>
        </div>
        <span class="mig-status">${m.status}${m.rolledBack ? raw(" · 롤백") : ""}</span>
      </button>
      <div class="mig-row-actions">
        <button type="button" class="pm-icon-btn" data-action="migration-edit" data-mig-id="${m.id}" title="편집">✎</button>
        <button type="button" class="pm-icon-btn pm-icon-btn-del" data-action="migration-delete" data-mig-id="${m.id}" title="삭제">✕</button>
      </div>
    </div>
  `).join("");

  setHTML(view, html`
    <section class="kpis kpis-4">${raw(kpis.map((k) => kpiCard(k)).join(""))}</section>
    <section class="backups-layout">
      <article class="panel bkup-cal-panel">
        ${raw(panelHead("백업 캘린더", null, html`<small>${dashboard.backups[0].date} ~ ${dashboard.backups[dashboard.backups.length - 1].date}</small>`))}
        <p class="bkup-sample-note">※ 백업 이력은 시각화 샘플입니다. 실제 백업 관리는 별도 운영 도구를 이용하세요.</p>
        <div class="bkup-cal">
          ${raw(weekHeads)}
          ${raw(calCells.join(""))}
        </div>
        <div class="bkup-legend">
          <span><i class="cal-dot cal-dot-ok"></i>성공</span>
          <span><i class="cal-dot cal-dot-warn"></i>경고</span>
          <span><i class="cal-dot cal-dot-fail"></i>실패</span>
        </div>
      </article>
      <article class="panel mig-panel">
        ${raw(panelHead("마이그레이션 이력", null, html`<button type="button" class="primary-btn" data-action="migration-add">+ 마이그레이션 추가</button>`))}
        <div class="mig-list">${raw(migRows)}</div>
      </article>
    </section>
  `);
}

/* ============================================================
 * View: Settings (placeholder)
 * ============================================================ */

function renderSettings() {
  const view = refs.views.settings;
  if (!view) return;
  const name = (dashboard.settings && dashboard.settings.displayName) || "박주호";
  const health = state.storageHealth || {};
  const localBytes = Number.isFinite(health.localBytes) ? health.localBytes : storedPayloadBytes();
  const usageBytes = Number.isFinite(health.usageBytes) ? health.usageBytes : localBytes;
  const quotaBytes = Number.isFinite(health.quotaBytes) ? health.quotaBytes : null;
  const usagePct = storagePercent(usageBytes, quotaBytes);
  const usagePctLabel = usagePct === null ? "추정치 없음" : `${usagePct.toFixed(1)}%`;
  const meterWidth = usagePct === null ? 3 : Math.max(3, Math.min(100, usagePct));
  const tone = storageTone(health);
  const statusLabel = storageStatusLabel(health);
  const quotaLabel = quotaBytes ? formatBytes(quotaBytes) : "추정치 없음";
  const lastChecked = health.checkedAt ? formatLocalDateTime(health.checkedAt) : "대기 중";
  const persistedLabel = storagePersistentLabel(health);
  const saved = formatLocalDateTime(dashboard.lastSavedAt);
  const theme = (dashboard.ui && dashboard.ui.theme === "light") ? "light" : "dark";

  setHTML(view, html`
    <section class="kpis kpis-4">
      ${raw(kpiCard({ title: "저장된 일정", value: String(dashboard.events.length), unit: "건", color: "#2387ff", badge: "◷", delta: "" }))}
      ${raw(kpiCard({ title: "저장된 할 일", value: String(dashboard.todos.length), unit: "건", color: "#22d3ee", badge: "☑", delta: "" }))}
      ${raw(kpiCard({ title: "저장된 메모", value: String(dashboard.notes.length), unit: "개", color: "#a970ff", badge: "✎", delta: "" }))}
      ${raw(kpiCard({ title: "저장 상태", value: statusLabel, unit: "", color: tone === "error" ? "#ff4d5e" : tone === "warn" ? "#f7a928" : "#17d983", badge: tone === "error" ? "!" : tone === "warn" ? "!" : "✓", delta: `${formatBytes(localBytes)} · 마지막 저장 ${saved}` }))}
    </section>

    <section class="panel">
      <div class="panel-head"><div><h2>프로필</h2></div></div>
      <form class="settings-form" data-action="save-settings">
        <label>표시 이름
          <input type="text" name="displayName" maxlength="40" value="${name}" placeholder="이름" />
        </label>
        <button type="submit" class="primary-btn">저장</button>
      </form>
    </section>

    <section class="panel">
      <div class="panel-head"><div><h2>화면 테마</h2></div></div>
      <p class="settings-note">밝은 환경에서는 라이트, 어두운 환경에서는 다크 테마를 선택하세요. 설정은 이 브라우저에 저장됩니다.</p>
      <div class="theme-toggle" role="group" aria-label="테마 선택">
        <button type="button" class="theme-opt ${raw(theme === "dark" ? "is-active" : "")}" data-action="set-theme" data-theme="dark" aria-pressed="${theme === "dark"}">🌙 다크</button>
        <button type="button" class="theme-opt ${raw(theme === "light" ? "is-active" : "")}" data-action="set-theme" data-theme="light" aria-pressed="${theme === "light"}">☀️ 라이트</button>
      </div>
    </section>

    <section class="panel">
      <div class="panel-head"><div><h2>데이터 백업</h2></div></div>
      <p class="settings-note">모든 일정 · 할 일 · 메모는 이 브라우저(localStorage)에 자동 저장됩니다. 기기를 옮기거나 백업하려면 JSON으로 내보내고, 다른 기기에서 가져오세요.</p>
      <div class="settings-actions">
        <button type="button" class="primary-btn" data-action="export-data">⬇ 데이터 내보내기 (JSON)</button>
        <label class="file-btn">⬆ 가져오기
          <input id="importFile" type="file" accept="application/json,.json" />
        </label>
        <button type="button" class="danger-btn" data-action="reset-data">전체 초기화</button>
      </div>
    </section>

    <section class="panel storage-health" data-storage-health data-storage-tone="${tone}">
      <div class="panel-head">
        <div><h2>저장소 상태</h2></div>
        <div class="settings-actions">
          <button type="button" data-action="refresh-storage-health">새로고침</button>
          <button type="button" class="primary-btn" data-action="request-storage-persistence">영속 저장 요청</button>
        </div>
      </div>
      <div class="storage-meter" aria-label="브라우저 저장소 사용률">
        <span style="width:${raw(meterWidth.toFixed(1))}%"></span>
      </div>
      <dl class="storage-grid">
        <div><dt>상태</dt><dd id="storageHealthStatus">${statusLabel}</dd></div>
        <div><dt>저장 데이터</dt><dd data-storage-local>${formatBytes(localBytes)}</dd></div>
        <div><dt>브라우저 사용량</dt><dd>${formatBytes(usageBytes)}</dd></div>
        <div><dt>추정 한도</dt><dd>${quotaLabel}</dd></div>
        <div><dt>사용률</dt><dd>${usagePctLabel}</dd></div>
        <div><dt>영속 저장</dt><dd>${persistedLabel}</dd></div>
        <div><dt>StorageManager</dt><dd>${health.estimateSupported ? "지원" : "미지원"}</dd></div>
        <div><dt>확인 시각</dt><dd id="storageHealthUpdated">${lastChecked}</dd></div>
      </dl>
      ${health.lastError ? raw(html`<p class="settings-note storage-error">최근 오류: ${health.lastError}</p>`) : ""}
    </section>

    <section class="panel">
      <div class="panel-head"><div><h2>정보</h2></div></div>
      <ul class="settings-info">
        <li><strong>JooPark Workspace</strong> · v3.0 — 개인 관리(일정/할 일/메모/습관/통계) + 프로젝트 · DB 카탈로그</li>
        <li>단축키: <b>⌘K</b> 명령 팔레트 · <b>/</b> 검색 · <b>n</b> 새 항목 · <b>?</b> 도움말 · <b>g+키</b> 화면 이동 · <b>Esc</b> 닫기</li>
        <li>지역 ap-northeast-2 · 빌드 정적(외부 의존성 없음)</li>
      </ul>
    </section>
  `);
  const fileInput = view.querySelector("#importFile");
  if (fileInput) fileInput.addEventListener("change", handleImportFile);
}

/* ============================================================
 * Sheet / Modal
 * ============================================================ */

function renderSheetMeta(meta) {
  if (!meta) return "";
  function actionsHTML(actions) {
    if (!actions || !actions.length) return "";
    return html`<div class="sheet-actions">${actions.map((entry) => raw(html`<button type="button" class="sheet-action" data-action="${entry.action}" data-project-id="${entry.target || ""}" data-issue-id="${entry.target || ""}" data-task-id="${entry.target || ""}" data-member-id="${entry.target || ""}" data-query-id="${entry.target || ""}" data-mig-id="${entry.target || ""}" data-target="${entry.target || ""}">${entry.label}</button>`))}</div>`;
  }
  if (meta.type === "list") {
    const listHTML = html`<ul>${meta.items.map((entry) => raw(html`<li>${entry.label ? raw(html`<strong>${entry.label}:</strong> `) : ""}${entry.value}</li>`))}</ul>`;
    return listHTML + actionsHTML(meta.actions);
  }
  if (meta.type === "paragraphs") {
    const parasHTML = html`${meta.items.map((entry) => raw(html`<p>${entry.label ? raw(html`<strong>${entry.label}:</strong> `) : ""}${entry.value}</p>`))}`;
    return parasHTML + actionsHTML(meta.actions);
  }
  if (meta.type === "actions") {
    return html`<div class="sheet-actions">${meta.items.map((entry) => raw(html`<button type="button" class="sheet-action" data-action="${entry.action}" data-target="${entry.target || ""}">${entry.label}</button>`))}</div>`;
  }
  return "";
}

function openSheet(title, body, meta) {
  state.previousFocus = document.activeElement;
  refs.sheets.title.textContent = title;
  refs.sheets.body.textContent = body || "";
  setHTML(refs.sheets.meta, renderSheetMeta(meta));
  refs.sheets.root.classList.add("open");
  refs.sheets.root.setAttribute("aria-hidden", "false");
  const closeBtn = refs.sheets.root.querySelector('.sheet-head [data-action="close-sheet"]');
  if (closeBtn) closeBtn.focus();
}

function closeSheet() {
  if (!refs.sheets.root.classList.contains("open")) return;
  refs.sheets.root.classList.remove("open");
  refs.sheets.root.setAttribute("aria-hidden", "true");
  if (state.previousFocus && typeof state.previousFocus.focus === "function") {
    state.previousFocus.focus();
    state.previousFocus = null;
  }
}

function openModal(title, bodyHTML, onConfirm) {
  if (!refs.modal.root) return;
  state.previousFocus = document.activeElement;
  refs.modal.title.textContent = title;
  setHTML(refs.modal.body, bodyHTML);
  state.modalOnConfirm = onConfirm || null;
  refs.modal.root.classList.add("open");
  refs.modal.root.setAttribute("aria-hidden", "false");
  const firstInput = refs.modal.body.querySelector("input, select, textarea");
  if (firstInput) firstInput.focus();
  else {
    const closeBtn = refs.modal.root.querySelector(".modal-close");
    if (closeBtn) closeBtn.focus();
  }
}

function closeModal() {
  if (!refs.modal.root || !refs.modal.root.classList.contains("open")) return;
  refs.modal.root.classList.remove("open");
  refs.modal.root.setAttribute("aria-hidden", "true");
  state.modalOnConfirm = null;
  if (state.previousFocus && typeof state.previousFocus.focus === "function") {
    state.previousFocus.focus();
    state.previousFocus = null;
  }
}

function getOpenDialogRoot() {
  if (refs.modal.root && refs.modal.root.classList.contains("open")) {
    return refs.modal.root.querySelector(".modal-panel") || refs.modal.root;
  }
  if (refs.sheets.root && refs.sheets.root.classList.contains("open")) {
    return refs.sheets.root.querySelector(".sheet-panel") || refs.sheets.root;
  }
  return null;
}

const FOCUSABLE_SELECTOR = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
function getFocusable(root) {
  if (!root) return [];
  return Array.from(root.querySelectorAll(FOCUSABLE_SELECTOR)).filter((el) => {
    if (el.hasAttribute("hidden")) return false;
    const rect = el.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  });
}
function trapTab(event, root) {
  if (event.key !== "Tab") return;
  const focusable = getFocusable(root);
  if (focusable.length === 0) { event.preventDefault(); return; }
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  const active = document.activeElement;
  if (event.shiftKey) {
    if (active === first || !root.contains(active)) { event.preventDefault(); last.focus(); }
  } else if (active === last || !root.contains(active)) { event.preventDefault(); first.focus(); }
}

/* ============================================================
 * Project picker (enhanced)
 * ============================================================ */

function renderProjectOptions() {
  const list = refs.projectPicker && refs.projectPicker.querySelector("#projectPickerList");
  if (!list) return;
  const q = projectPickerState.query;
  const filtered = dashboard.projects.filter((p) => matches(projectSearchText(p), q));
  if (filtered.length === 0) {
    setHTML(list, html`<div class="project-empty">일치하는 프로젝트가 없습니다.</div>`);
    return;
  }
  const body = filtered.map((p, idx) => {
    const isCurrent = p.id === dashboard.currentProjectId;
    return html`
      <button type="button" id="project-option-${idx}" role="option" class="project-option ${raw(isCurrent ? "is-current" : "")}" data-action="pick-project" data-project-id="${p.id}" aria-selected="${raw(isCurrent ? "true" : "false")}">
        <div class="project-option-row">
          <strong>${p.name}</strong>
          <span class="project-env-pill">${p.category || p.owner}</span>
        </div>
        <div class="project-meta">
          <span><b>진행률</b> ${p.progress}%</span>
          <span><b>이슈</b> ${p.openIssues}</span>
          ${p.description ? raw(html`<span class="project-meta-summary">${p.description}</span>`) : ""}
          <span class="project-meta-spark">${raw(spark(p.burn, HEALTH_COLOR[p.health] || "#22d3ee"))}</span>
        </div>
      </button>
    `;
  }).join("");
  setHTML(list, body);
}

let projectPickerInitialized = false;
function restoreProjectPickerFocus() {
  if (!refs.projectSelect) return;
  refs.projectSelect.focus();
  setTimeout(() => {
    if (refs.projectPicker && refs.projectPicker.hasAttribute("hidden")) refs.projectSelect.focus();
  }, 0);
  setTimeout(() => {
    if (refs.projectPicker && refs.projectPicker.hasAttribute("hidden")) refs.projectSelect.focus();
  }, 80);
}

function ensureProjectPickerScaffold() {
  if (projectPickerInitialized || !refs.projectPicker) return;
  setHTML(refs.projectPicker, html`
    <div class="project-search">
      <span aria-hidden="true">⌕</span>
      <input id="projectPickerSearch" type="search" placeholder="프로젝트 검색" autocomplete="off" aria-label="프로젝트 검색" aria-controls="projectPickerList" />
    </div>
    <div id="projectPickerList" class="project-list" role="listbox" aria-label="프로젝트 목록"></div>
  `);
  const searchInput = refs.projectPicker.querySelector("#projectPickerSearch");
  if (searchInput) {
    searchInput.addEventListener("input", (event) => {
      projectPickerState.query = event.target.value;
      renderProjectOptions();
    });
  }
  // Close when focus leaves the picker (e.g. Tab past the last option) so it
  // never lingers open behind the rest of the page.
  refs.projectPicker.addEventListener("focusout", (event) => {
    const next = event.relatedTarget;
    if (!next) return;
    if (refs.projectPicker.contains(next)) return;
    if (refs.projectSelect && refs.projectSelect.contains(next)) return;
    setProjectPickerOpen(false);
  });
  projectPickerInitialized = true;
}

function setProjectPickerOpen(open) {
  if (!refs.projectPicker || !refs.projectSelect) return;
  if (open) {
    ensureProjectPickerScaffold();
    projectPickerState.query = "";
    const searchInput = refs.projectPicker.querySelector("#projectPickerSearch");
    if (searchInput) searchInput.value = "";
    renderProjectOptions();
    refs.projectPicker.removeAttribute("hidden");
    refs.projectSelect.setAttribute("aria-expanded", "true");
    if (searchInput) searchInput.focus();
  } else {
    const restoreFocus = refs.projectPicker.contains(document.activeElement);
    if (restoreFocus) refs.projectSelect.focus();
    refs.projectPicker.setAttribute("hidden", "");
    refs.projectSelect.setAttribute("aria-expanded", "false");
    if (restoreFocus) restoreProjectPickerFocus();
  }
}
function toggleProjectPicker() {
  if (!refs.projectPicker) return;
  setProjectPickerOpen(refs.projectPicker.hasAttribute("hidden"));
}
function pickProject(projectId) {
  const project = indexes.projectById.get(projectId);
  if (!project) return;
  const wasSame = dashboard.currentProjectId === projectId;
  dashboard.currentProjectId = projectId;
  if (refs.projectSelectLabel) refs.projectSelectLabel.textContent = project.name;
  setProjectPickerOpen(false);
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
    bodyHTML = `<p class="agenda-empty">확인할 알림이 없습니다. 👍</p>`;
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
      return `<${tag} ${typeAttr} class="alert-row ${kindCls}" ${dataAttrs}>
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

    bodyHTML = `<div class="alert-list">${rows}</div>${notifBtn}`;
  }

  // openSheet with raw HTML body (use sheetBody as innerHTML)
  state.previousFocus = document.activeElement;
  refs.sheets.title.textContent = `알림 (${alerts.length}건)`;
  refs.sheets.body.textContent = ""; // clear text
  setHTML(refs.sheets.body, bodyHTML);
  setHTML(refs.sheets.meta, "");
  refs.sheets.root.classList.add("open");
  refs.sheets.root.setAttribute("aria-hidden", "false");
  const closeBtn = refs.sheets.root.querySelector('.sheet-head [data-action="close-sheet"]');
  if (closeBtn) closeBtn.focus();
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
      { label: "✎ 편집", action: "project-edit", target: id },
      { label: "✕ 삭제", action: "project-delete", target: id },
    ] });
}

function openIssueSheet(id) {
  const i = indexes.issueById.get(id);
  if (!i) return;
  openSheet(`이슈: ${i.id} ${i.title}`,
    `${projectName(i.project)} · ${memberName(i.assignee)} · 마감 ${i.due || "—"}`,
    { type: "list", items: [
      { label: "상태", value: STATUS_LABEL[i.status] || i.status },
      { label: "우선순위", value: PRIORITY_LABEL[i.priority] || i.priority },
      { label: "예상", value: `${i.estimate}시간` },
      { label: "라벨", value: i.labels.join(", ") || "—" },
    ], actions: [
      { label: "✎ 편집", action: "issue-edit", target: id },
      { label: "✕ 삭제", action: "issue-delete", target: id },
    ] });
}

function openTaskSheet(id) {
  const t = dashboard.gantt.tasks.find((x) => x.id === id);
  if (!t) return;
  openSheet(`${t.milestone ? "마일스톤" : "작업"}: ${t.name}`,
    `${projectName(t.project)} · ${t.start} → ${t.end} · 담당 ${memberName(t.owner)}`,
    { type: "list", items: [
      { label: "기간", value: `${daysBetween(t.start, t.end) || 1}일` },
      { label: "의존", value: t.deps.join(", ") || "없음" },
      { label: "유형", value: t.milestone ? "마일스톤" : "작업" },
    ], actions: [
      { label: "✎ 편집", action: "task-edit", target: id },
      { label: "✕ 삭제", action: "task-delete", target: id },
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
      { label: "✎ 편집", action: "member-edit", target: id },
      { label: "✕ 삭제", action: "member-delete", target: id },
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
  renderDbSchema();
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
        <button type="button" class="pm-icon-btn" data-action="column-edit" data-table-id="${id}" data-col-index="${ci}" title="편집">✎</button>
        <button type="button" class="pm-icon-btn pm-icon-btn-del" data-action="column-delete" data-table-id="${id}" data-col-index="${ci}" title="삭제">✕</button>
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

  state.previousFocus = document.activeElement;
  refs.sheets.title.textContent = `테이블: ${dbName}.${table.name}`;
  refs.sheets.body.textContent = `${inst ? inst.name : instance} · ${(table.rows || 0).toLocaleString()}행 · ${table.sizeMb || 0}MB`;
  setHTML(refs.sheets.meta, html`
    ${raw(sheetBodyHTML)}
    <div class="sheet-actions">
      <button type="button" class="sheet-action" data-action="table-edit" data-table-id="${id}">✎ 편집</button>
      <button type="button" class="sheet-action sheet-action-del" data-action="table-delete" data-table-id="${id}">✕ 삭제</button>
    </div>
  `);
  refs.sheets.root.classList.add("open");
  refs.sheets.root.setAttribute("aria-hidden", "false");
  const closeBtn = refs.sheets.root.querySelector('.sheet-head [data-action="close-sheet"]');
  if (closeBtn) closeBtn.focus();
}

function openQuerySheet(id) {
  const qi = dashboard.queries.find((x) => x.id === id);
  if (!qi) return;
  openSheet(`쿼리: ${qi.id}`,
    `${qi.instance}/${qi.db} · 평균 ${qi.avgMs}ms · p95 ${qi.p95Ms}ms`,
    { type: "paragraphs", items: [
      { label: "SQL", value: qi.text },
      { label: "Plan", value: qi.planHint },
      { label: "최근 실행", value: qi.lastRun },
      { label: "호출 수", value: String(qi.count) },
    ], actions: [
      { label: "✎ 편집", action: "query-edit", target: id },
      { label: "✕ 삭제", action: "query-delete", target: id },
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
  const m = dashboard.migrations.find((x) => x.id === id);
  if (!m) return;
  openSheet(`마이그: ${m.title}`,
    `${m.id} · ${m.instance} · ${m.status}`,
    { type: "list", items: [
      { label: "상태", value: m.status + (m.rolledBack ? " (롤백됨)" : "") },
      { label: "적용", value: m.appliedAt || m.scheduledAt || "—" },
      { label: "작성", value: m.author || "—" },
      { label: "비고", value: m.rollbackReason || "—" },
    ], actions: [
      { label: "✎ 편집", action: "migration-edit", target: id },
      { label: "✕ 삭제", action: "migration-delete", target: id },
    ] });
}

function pickInstance(id) {
  const inst = indexes.instanceById.get(id);
  if (!inst) return;
  dashboard.currentInstanceId = id;
  if (dashboard.currentView === "dbm-instances") renderDbInstances();
  if (dashboard.currentView === "dbm-schema") {
    state.schemaExpanded.add(id);
    state.schemaSelectedTable = null;
    renderDbSchema();
  }
  showToast(`인스턴스 '${inst.name}' 선택`, "info");
}

function setKanbanFilter(priority) {
  state.kanbanFilter = priority || null;
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
const ADOPTION_IMPORT_ID = "2026-06-04-repo-adoption-candidates";

// true once a v3 payload (with PM/DB slices) has been loaded from localStorage;
// prevents the GitHub snapshot from clobbering user-edited project data.
let pmWasPersisted = false;

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
if (!dashboard.settings)               dashboard.settings = { displayName: "박주호" };
if (!Array.isArray(dashboard.habits))  dashboard.habits  = [];
if (!dashboard.ui || typeof dashboard.ui !== "object") dashboard.ui = { theme: "dark" };
dashboard.lastSavedAt = null;

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

/* ---------- Finders ---------- */

function eventById(id) { return dashboard.events.find((e) => e.id === id); }
function todoById(id) { return dashboard.todos.find((t) => t.id === id); }
function noteById(id) { return dashboard.notes.find((n) => n.id === id); }
function sortEvents(list) {
  return [...list].sort((a, b) => {
    if (a.date !== b.date) return a.date < b.date ? -1 : 1;
    if (a.allDay !== b.allDay) return a.allDay ? -1 : 1;
    return (a.start || "99:99") < (b.start || "99:99") ? -1 : 1;
  });
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
    if (typeof e.title !== "string") e.title = String(e.title == null ? "" : e.title);
    // Normalize recurrence fields; default to "none" / null / [] if missing.
    if (!["none", "daily", "weekly", "monthly"].includes(e.repeat)) e.repeat = "none";
    if (e.repeatUntil != null && !/^\d{4}-\d{2}-\d{2}$/.test(e.repeatUntil)) e.repeatUntil = null;
    if (!Array.isArray(e.exceptions)) e.exceptions = [];
  });
  dashboard.todos = (Array.isArray(dashboard.todos) ? dashboard.todos : [])
    .filter((t) => t && typeof t === "object" && t.title != null);
  dashboard.todos.forEach((t) => {
    if (!TODO_PRIORITY[t.priority]) t.priority = "med";
    t.done = !!t.done;
    if (t.due != null && !/^\d{4}-\d{2}-\d{2}$/.test(t.due)) t.due = null;
  });
  dashboard.notes = (Array.isArray(dashboard.notes) ? dashboard.notes : [])
    .filter((n) => n && typeof n === "object");
  dashboard.notes.forEach((n) => { n.color = safeNoteColor(n.color); n.pinned = !!n.pinned; });

  // ---- 습관 (habits) ----
  dashboard.habits = (Array.isArray(dashboard.habits) ? dashboard.habits : [])
    .filter((h) => h && typeof h === "object" && h.id);
  dashboard.habits.forEach((h) => {
    if (!h.log || typeof h.log !== "object" || Array.isArray(h.log)) h.log = {};
  });

  // ---- PM 슬라이스 ----
  if (!Array.isArray(dashboard.projects))    dashboard.projects    = [];
  if (!Array.isArray(dashboard.issues))      dashboard.issues      = [];
  if (!Array.isArray(dashboard.team))        dashboard.team        = [];
  if (!Array.isArray(dashboard.dbInstances)) dashboard.dbInstances = [];
  if (!Array.isArray(dashboard.schemas))     dashboard.schemas     = [];
  if (!Array.isArray(dashboard.queries))     dashboard.queries     = [];
  if (!Array.isArray(dashboard.migrations))  dashboard.migrations  = [];
  if (!dashboard.imports || typeof dashboard.imports !== "object" || Array.isArray(dashboard.imports)) {
    dashboard.imports = {};
  }
  if (!dashboard.imports.projectImports || typeof dashboard.imports.projectImports !== "object" ||
      Array.isArray(dashboard.imports.projectImports)) {
    dashboard.imports.projectImports = {};
  }

  dashboard.projects = dashboard.projects.filter((p) => p && typeof p === "object" && p.id && p.name);
  dashboard.projects.forEach((p) => {
    if (!Array.isArray(p.members)) p.members = [];
    if (!Array.isArray(p.burn) || p.burn.length === 0) p.burn = [0, 0, 0, 0, 0, 0, 0];
    if (!["on-track", "at-risk", "delayed"].includes(p.status)) p.status = "on-track";
    if (!["green", "amber", "red"].includes(p.health)) p.health = "green";
    p.progress = Math.min(100, Math.max(0, parseInt(p.progress || "0", 10) || 0));
    p.openIssues = Math.max(0, parseInt(p.openIssues || "0", 10) || 0);
    p.risks = Math.max(0, parseInt(p.risks || "0", 10) || 0);
    p.owner = (p.owner || "—").toString();
    p.deadline = /^\d{4}-\d{2}-\d{2}$/.test(p.deadline || "") ? p.deadline : "2099-12-31";
    p.description = (p.description || "").toString();
    p.category = (p.category || "").toString();
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
    if (!/^\d{4}-\d{2}-\d{2}$/.test(t.start || "")) t.start = dashboard.gantt.rangeStart;
    if (!/^\d{4}-\d{2}-\d{2}$/.test(t.end || "") || t.end < t.start) t.end = t.start;
    if (!Array.isArray(t.deps)) t.deps = [];
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
  if (!dashboard.ui || typeof dashboard.ui !== "object") dashboard.ui = { theme: "dark" };
  if (typeof dashboard.ui.theme !== "string") dashboard.ui.theme = "dark";
}
// 하위 호환 별칭 (기존 호출부에서 normalizePersonalData()를 참조하는 곳이 있을 경우 대비)
function normalizePersonalData() { normalizeAllData(); }

/* ---------- Persistence ---------- */

function storageByteLength(value) {
  const text = value == null ? "" : String(value);
  try { return new Blob([text]).size; } catch (_) { return text.length; }
}

function storedPayloadBytes() {
  try { return storageByteLength(localStorage.getItem(STORE_KEY_V3) || ""); }
  catch (_) { return 0; }
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
    const manager = typeof navigator !== "undefined" && navigator.storage ? navigator.storage : null;
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
  if (options.render && dashboard.currentView === "settings") renderSettings();
  return next;
}

async function requestStoragePersistence() {
  try {
    const manager = typeof navigator !== "undefined" && navigator.storage ? navigator.storage : null;
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
    if (dashboard.currentView === "settings") renderSettings();
    showToast("영속 저장 요청에 실패했습니다", "error");
  }
}

function persist() {
  try {
    const savedAt = nowISO();
    const payload = {
      v: 3,
      events:      dashboard.events,
      todos:       dashboard.todos,
      notes:       dashboard.notes,
      settings:    dashboard.settings,
      habits:      dashboard.habits,
      projects:    dashboard.projects,
      issues:      dashboard.issues,
      gantt:       dashboard.gantt,
      team:        dashboard.team,
      dbInstances: dashboard.dbInstances,
      schemas:     dashboard.schemas,
      queries:     dashboard.queries,
      migrations:  dashboard.migrations,
      ui:          dashboard.ui,
      imports:     dashboard.imports,
      savedAt,
    };
    const serialized = JSON.stringify(payload);
    localStorage.setItem(STORE_KEY_V3, serialized);
    dashboard.lastSavedAt = savedAt;
    state.storageHealth = {
      ...state.storageHealth,
      localBytes: storageByteLength(serialized),
      lastError: "",
      checkedAt: savedAt,
    };
    return true;
  } catch (err) {
    console.warn("[workspace] persist failed:", err && err.message);
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

function loadPersisted() {
  // ---- 1순위: v3 저장소 ----
  let rawV3 = null;
  try { rawV3 = JSON.parse(localStorage.getItem(STORE_KEY_V3) || "null"); } catch (_) { rawV3 = null; }

  if (rawV3 && typeof rawV3 === "object" && rawV3.v === 3) {
    const hasPersonalSlices =
      Array.isArray(rawV3.events) || Array.isArray(rawV3.todos) || Array.isArray(rawV3.notes);
    // v3 슬라이스가 존재하면 덮어쓰고, 없으면 현재 하드코딩 기본값을 유지
    if (Array.isArray(rawV3.events))      dashboard.events      = rawV3.events;
    if (Array.isArray(rawV3.todos))       dashboard.todos       = rawV3.todos;
    if (Array.isArray(rawV3.notes))       dashboard.notes       = rawV3.notes;
    if (rawV3.settings && typeof rawV3.settings === "object")
      dashboard.settings = { ...dashboard.settings, ...rawV3.settings };
    if (Array.isArray(rawV3.habits))      dashboard.habits      = rawV3.habits;
    if (Array.isArray(rawV3.projects))    dashboard.projects    = rawV3.projects;
    if (Array.isArray(rawV3.issues))      dashboard.issues      = rawV3.issues;
    if (rawV3.gantt && typeof rawV3.gantt === "object" && !Array.isArray(rawV3.gantt))
      dashboard.gantt = rawV3.gantt;
    if (Array.isArray(rawV3.team))        dashboard.team        = rawV3.team;
    if (Array.isArray(rawV3.dbInstances)) dashboard.dbInstances = rawV3.dbInstances;
    if (Array.isArray(rawV3.schemas))     dashboard.schemas     = rawV3.schemas;
    if (Array.isArray(rawV3.queries))     dashboard.queries     = rawV3.queries;
	    if (Array.isArray(rawV3.migrations))  dashboard.migrations  = rawV3.migrations;
	    if (rawV3.ui && typeof rawV3.ui === "object") dashboard.ui  = rawV3.ui;
	    if (rawV3.imports && typeof rawV3.imports === "object") dashboard.imports = rawV3.imports;
	    dashboard.lastSavedAt = rawV3.savedAt || null;
    pmWasPersisted = true;
    normalizeAllData();
    rebuildIndexes();
    // 개인 슬라이스 자체가 없는 구형 v3 파일만 시드한다.
    // reset/import처럼 빈 배열을 명시한 저장소는 사용자의 빈 상태로 보존한다.
    if (!hasPersonalSlices && !dashboard.events.length && !dashboard.todos.length && !dashboard.notes.length) {
      seedPersonalData();
      persist();
    }
    return true;
  }

  // ---- 2순위: v2 레거시 마이그레이션 ----
  let rawV2 = null;
  try { rawV2 = JSON.parse(localStorage.getItem(STORE_KEY) || "null"); } catch (_) { rawV2 = null; }

  if (rawV2 && typeof rawV2 === "object" && (rawV2.events || rawV2.todos || rawV2.notes)) {
    // 개인 데이터만 가져오고 PM/DB 슬라이스는 하드코딩 기본값 유지
    if (Array.isArray(rawV2.events)) dashboard.events = rawV2.events;
    if (Array.isArray(rawV2.todos))  dashboard.todos  = rawV2.todos;
    if (Array.isArray(rawV2.notes))  dashboard.notes  = rawV2.notes;
    if (rawV2.settings && typeof rawV2.settings === "object")
      dashboard.settings = { ...dashboard.settings, ...rawV2.settings };
    dashboard.lastSavedAt = rawV2.savedAt || null;
    pmWasPersisted = false;
    normalizeAllData();
    rebuildIndexes();
    persist(); // v2 → v3으로 즉시 마이그레이션
    return true;
  }

  // ---- 3순위: 신규 설치 ----
  seedPersonalData();
  pmWasPersisted = false;
  normalizeAllData();
  rebuildIndexes();
  persist();
  return false;
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

function calLegend() {
  return html`<div class="sched-legend">${EVENT_CAT_ORDER.map((k) => raw(html`
    <span><i style="background:${raw(EVENT_CATS[k].color)}"></i>${EVENT_CATS[k].label}</span>
  `))}</div>`;
}

function eventRow(e, opts) {
  const compact = opts && opts.compact;
  const c = EVENT_CATS[e.category] || EVENT_CATS.etc;
  // For occurrence view-models, open their master event.
  const openId = e._masterId || e.id;
  const isRecurring = e._occ && (e.repeat && e.repeat !== "none");
  const skipBtn = (opts && opts.showSkip && isRecurring)
    ? html`<button type="button" class="agenda-skip" data-action="skip-occurrence" data-event-id="${e._masterId}" data-date="${e.date}" title="이 날짜 건너뛰기" aria-label="이 날짜 건너뛰기">건너뛰기</button>`
    : "";
  return html`
    <div class="agenda-item-wrap">
      <button type="button" class="agenda-item" data-action="open-event" data-event-id="${openId}">
        <span class="agenda-bar" style="background:${raw(c.color)}"></span>
        <span class="agenda-time">${eventTimeLabel(e)}</span>
        <span class="agenda-body">
          <strong>${e.title}</strong>
          ${isRecurring ? raw(html`<span class="agenda-recur-icon" title="반복 일정">↺</span>`) : ""}
          ${e.location || (!compact && e.memo) ? raw(html`<small>${[e.location, compact ? "" : e.memo].filter(Boolean).join(" · ")}</small>`) : ""}
        </span>
        <span class="agenda-cat" style="color:${raw(c.color)}">${c.label}</span>
      </button>${raw(skipBtn)}
    </div>
  `;
}

function renderCalendar() {
  const view = refs.views.cal;
  if (!view) return;
  if (!state.calMonth) state.calMonth = monthKey(new Date());
  if (!state.calSelected) state.calSelected = todayISO();
  const q = state.query;
  const ym = state.calMonth;
  const first = ymToDate(ym);
  const year = first.getFullYear();
  const month = first.getMonth();
  const firstWeekday = first.getDay();
  const gridStart = new Date(year, month, 1 - firstWeekday);

  // matchedIds targets master events (occurrences inherit the master's id via _masterId).
  const matchedIds = new Set(
    dashboard.events
      .filter((e) => matches(`${e.title} ${e.memo} ${e.location} ${(EVENT_CATS[e.category] || {}).label || ""}`, q))
      .map((e) => e.id)
  );

  const today = todayISO();
  // Count occurrences in this month (not just master dates).
  const monthStart = `${ym}-01`;
  const monthEnd = (() => {
    const [my, mm] = ym.split("-").map(Number);
    const lastDay = new Date(my, mm, 0).getDate();
    return `${ym}-${String(lastDay).padStart(2, "0")}`;
  })();
  const monthOccs = expandOccurrences(monthStart, monthEnd);
  const todayCount = eventsOn(today).length;
  const upcomingDeadlines = expandOccurrences(today, addDaysISO(today, 365))
    .filter((e) => e.category === "deadline").length;
  const kpis = [
    { title: "이번 달 일정", value: String(monthOccs.length), unit: "건", color: "#2387ff", badge: "▦", delta: `${WEEKDAYS_KO[new Date().getDay()]}요일` },
    { title: "오늘 일정", value: String(todayCount), unit: "건", color: "#17d983", badge: "◷", delta: formatKoreanShort(today) },
    { title: "다가오는 마감", value: String(upcomingDeadlines), unit: "건", color: upcomingDeadlines ? "#ff4d5e" : "#17d983", badge: "⚑", delta: upcomingDeadlines ? "확인 필요" : "여유", trendDown: upcomingDeadlines > 0 },
    { title: "전체 일정", value: String(dashboard.events.length), unit: "건", color: "#a970ff", badge: "◈", delta: "자동 저장됨" },
  ];

  const weekdayHead = WEEKDAYS_KO.map((w, i) => html`<div class="sched-wd ${raw(i === 0 ? "is-sun" : i === 6 ? "is-sat" : "")}">${w}</div>`).join("");

  const cells = [];
  for (let i = 0; i < 42; i++) {
    const d = new Date(gridStart);
    d.setDate(gridStart.getDate() + i);
    const iso = ymd(d);
    const out = d.getMonth() !== month;
    const dow = d.getDay();
    let dayEvents = eventsOn(iso);
    // For search filtering, match against the master event's id (_masterId).
    if (q) dayEvents = dayEvents.filter((e) => matchedIds.has(e._masterId || e.id));
    const shown = dayEvents.slice(0, 3);
    const chips = shown.map((e) => {
      const c = EVENT_CATS[e.category] || EVENT_CATS.etc;
      const openId = e._masterId || e.id;
      return html`<button type="button" class="sched-chip" data-action="open-event" data-event-id="${openId}" title="${e.title}">
        <i style="background:${raw(c.color)}"></i>${e.allDay ? "" : raw(html`<em>${e.start || ""}</em> `)}${e.title}
      </button>`;
    }).join("");
    const more = dayEvents.length > 3 ? html`<span class="sched-more">+${dayEvents.length - 3}건 더</span>` : "";
    cells.push(html`
      <div class="sched-cell ${raw(out ? "is-out" : "")} ${raw(isTodayISO(iso) ? "is-today" : "")} ${raw(state.calSelected === iso ? "is-sel" : "")}"
           data-action="cal-open-day" data-date="${iso}" tabindex="0" aria-label="${formatKoreanFull(iso)}">
        <span class="sched-date ${raw(dow === 0 ? "is-sun" : dow === 6 ? "is-sat" : "")}">${d.getDate()}</span>
        <div class="sched-cell-events">${raw(chips)}${raw(more)}</div>
      </div>
    `);
  }

  // Agenda for the selected day (events + todos due that day)
  const sel = state.calSelected;
  const selEvents = eventsOn(sel);
  const selTodos = dashboard.todos.filter((t) => t.due === sel);
  const agendaEvents = selEvents.length
    ? selEvents.map((e) => eventRow(e, { showSkip: true })).join("")
    : html`<p class="sched-agenda-empty">일정이 없습니다.</p>`;
  const agendaTodos = selTodos.length
    ? html`<div class="sched-agenda-todos">${selTodos.map((t) => raw(html`
        <button type="button" class="agenda-todo ${raw(t.done ? "is-done" : "")}" data-action="open-todo" data-todo-id="${t.id}">
          <span class="todo-check-mini ${raw(t.done ? "is-on" : "")}">${raw(t.done ? "✓" : "")}</span>${t.title}
        </button>`))}</div>`
    : "";

  setHTML(view, html`
    <section class="kpis kpis-4">${raw(kpis.map((k) => kpiCard(k)).join(""))}</section>
    <section class="sched-layout">
      <div class="panel sched-cal">
        <div class="sched-toolbar">
          <div class="sched-nav">
            <button type="button" data-action="cal-prev" aria-label="이전 달">‹</button>
            <strong>${year}년 ${month + 1}월</strong>
            <button type="button" data-action="cal-next" aria-label="다음 달">›</button>
            <button type="button" class="sched-today-btn" data-action="cal-today">오늘</button>
          </div>
          ${raw(calLegend())}
          <button type="button" class="sched-add primary-btn" data-action="cal-add">+ 일정 추가</button>
        </div>
        <div class="sched-weekdays">${raw(weekdayHead)}</div>
        <div class="sched-grid">${raw(cells.join(""))}</div>
      </div>
      <aside class="panel sched-agenda">
        <div class="panel-head">
          <div><h2>${formatKoreanFull(sel)}</h2></div>
          ${raw(isTodayISO(sel) ? html`<small class="home-tile-sub">오늘</small>` : "")}
        </div>
        <button type="button" class="sched-agenda-add" data-action="cal-add" data-date="${sel}">+ 이 날짜에 일정 추가</button>
        <div class="sched-agenda-list">${raw(agendaEvents)}</div>
        ${selTodos.length ? raw(html`<p class="sched-agenda-label">이 날짜 마감 할 일</p>${raw(agendaTodos)}`) : ""}
      </aside>
    </section>
  `);
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
  const editing = arg && typeof arg === "object";
  const ev = editing ? arg : null;
  const date = editing ? ev.date : (arg || state.calSelected || todayISO());
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
      ${editing ? raw(html`<button type="button" class="modal-delete" data-action="delete-event" data-event-id="${ev.id}">${deleteLabel}</button>`) : ""}
    </form>
  `;
  openModal(editing ? "일정 편집" : "새 일정", form, () => saveEventFromForm(editing ? ev.id : null));
  const f = document.querySelector("#eventForm");
  if (f) {
    const allDay = f.querySelector("[name=allDay]");
    const timeRow = f.querySelector("#timeRow");
    const syncTime = () => { if (timeRow) timeRow.style.display = allDay.checked ? "none" : ""; };
    if (allDay) allDay.addEventListener("change", syncTime);
    syncTime();

    const repeatSel = f.querySelector("#repeatSelect");
    const repeatUntilLabel = f.querySelector("#repeatUntilLabel");
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
  const form = document.querySelector("#eventForm");
  if (!form) return false;
  const data = new FormData(form);
  const title = (data.get("title") || "").toString().trim();
  if (!title) { showToast("제목을 입력하세요", "warn"); return false; }
  const date = (data.get("date") || "").toString();
  if (!date) { showToast("날짜를 선택하세요", "warn"); return false; }
  const allDay = data.get("allDay") === "on";
  let start = allDay ? null : ((data.get("start") || "").toString() || null);
  let end = allDay ? null : ((data.get("end") || "").toString() || null);
  if (start && end && end < start) { const tmp = start; start = end; end = tmp; }
  const category = (data.get("category") || "work").toString();
  const location = (data.get("location") || "").toString().trim();
  const memo = (data.get("memo") || "").toString().trim();
  const repeat = (data.get("repeat") || "none").toString();
  const repeatUntilRaw = (data.get("repeatUntil") || "").toString().trim();
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
  const idx = dashboard.events.findIndex((e) => e.id === id);
  if (idx >= 0) { dashboard.events.splice(idx, 1); showToast("일정을 삭제했습니다", "info"); }
  closeModal();
  commit();
}

function calNav(delta) {
  if (!state.calMonth) state.calMonth = monthKey(new Date());
  state.calMonth = addMonthsKey(state.calMonth, delta);
  renderCalendar();
}
function calToday() {
  state.calMonth = monthKey(new Date());
  state.calSelected = todayISO();
  renderCalendar();
}
function calSelectDay(iso) {
  state.calSelected = iso;
  if (iso.slice(0, 7) !== state.calMonth) state.calMonth = iso.slice(0, 7);
  renderCalendar();
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

function todoMatchesFilter(t, filter) {
  const today = todayISO();
  switch (filter) {
    case "active": return !t.done;
    case "today": return !t.done && t.due === today;
    case "upcoming": return !t.done && t.due && t.due > today;
    case "done": return t.done;
    default: return true;
  }
}

function todoRow(t) {
  const dl = dueLabel(t.due);
  const prio = TODO_PRIORITY[t.priority] || TODO_PRIORITY.med;
  return html`
    <div class="todo-row ${raw(t.done ? "is-done" : "")} prio-${raw(t.priority)}">
      <button type="button" class="todo-check ${raw(t.done ? "is-on" : "")}" data-action="todo-toggle" data-todo-id="${t.id}" aria-label="${t.done ? "완료 취소" : "완료 처리"}">${raw(t.done ? "✓" : "")}</button>
      <button type="button" class="todo-main" data-action="open-todo" data-todo-id="${t.id}">
        <span class="todo-title">${t.title}</span>
        <span class="todo-meta">
          <span class="todo-due ${raw(t.done ? "" : dl.cls)}">${dl.text}</span>
          ${t.category ? raw(html`<span class="todo-tag">${t.category}</span>`) : ""}
          <span class="todo-prio" style="color:${raw(prio.color)}">${prio.label}</span>
        </span>
      </button>
      <button type="button" class="todo-del" data-action="todo-delete" data-todo-id="${t.id}" aria-label="삭제">✕</button>
    </div>
  `;
}

function renderTodos() {
  const view = refs.views.todo;
  if (!view) return;
  if (!state.todoFilter) state.todoFilter = "active";
  const q = state.query;
  const today = todayISO();

  const base = dashboard.todos.filter((t) => matches(`${t.title} ${t.category} ${t.memo}`, q));
  const open = base.filter((t) => !t.done);
  const overdue = open.filter((t) => t.due && t.due < today);
  const dueToday = open.filter((t) => t.due === today);
  const doneCount = base.filter((t) => t.done).length;
  const total = base.length;
  const rate = total ? Math.round((doneCount / total) * 100) : 0;

  const kpis = [
    { title: "미완료", value: String(open.length), unit: "건", color: "#22d3ee", badge: "☑", delta: total ? `전체 ${total}건` : "" },
    { title: "오늘 마감", value: String(dueToday.length), unit: "건", color: "#2387ff", badge: "◷", delta: formatKoreanShort(today) },
    { title: "기한 지남", value: String(overdue.length), unit: "건", color: overdue.length ? "#ff4d5e" : "#17d983", badge: "⚑", delta: overdue.length ? "지금 처리" : "없음", trendDown: overdue.length > 0 },
    { title: "완료율", value: String(rate), unit: "%", color: "#17d983", badge: "✓", delta: `완료 ${doneCount}건` },
  ];

  const filtered = base.filter((t) => todoMatchesFilter(t, state.todoFilter));
  filtered.sort((a, b) => {
    if (a.done !== b.done) return a.done ? 1 : -1;
    const ad = a.due || "9999-99-99";
    const bd = b.due || "9999-99-99";
    if (ad !== bd) return ad < bd ? -1 : 1;
    return (TODO_PRIO_RANK[a.priority] ?? 1) - (TODO_PRIO_RANK[b.priority] ?? 1);
  });

  // Group only for the default "active" view; other filters show a flat list.
  let listHTML;
  if (filtered.length === 0) {
    listHTML = html`<article class="empty">${q ? "일치하는 할 일이 없습니다." : "할 일이 없습니다. 위에서 추가해 보세요."}</article>`;
  } else if (state.todoFilter === "active") {
    const buckets = [
      { label: "기한 지남", items: filtered.filter((t) => t.due && t.due < today) },
      { label: "오늘", items: filtered.filter((t) => t.due === today) },
      { label: "예정", items: filtered.filter((t) => t.due && t.due > today) },
      { label: "기한 없음", items: filtered.filter((t) => !t.due) },
    ].filter((b) => b.items.length);
    listHTML = buckets.map((b) => html`
      <div class="todo-group">
        <p class="todo-group-head">${b.label} <span>${b.items.length}</span></p>
        ${raw(b.items.map((t) => todoRow(t)).join(""))}
      </div>
    `).join("");
  } else {
    listHTML = html`<div class="todo-group">${raw(filtered.map((t) => todoRow(t)).join(""))}</div>`;
  }

  const filterChips = TODO_FILTERS.map((f) => html`
    <button type="button" class="seg-chip ${raw(state.todoFilter === f.key ? "is-active" : "")}" data-action="todo-filter" data-filter="${f.key}" aria-pressed="${raw(state.todoFilter === f.key ? "true" : "false")}">${f.label}</button>
  `).join("");

  setHTML(view, html`
    <section class="kpis kpis-4">${raw(kpis.map((k) => kpiCard(k)).join(""))}</section>
    <section class="panel todo-panel">
      <form class="todo-quickadd" data-action="todo-quick-add">
        <input type="text" name="title" maxlength="160" placeholder="새 할 일을 입력하고 Enter… (예: 보고서 초안 작성)" aria-label="새 할 일" autocomplete="off" />
        <select name="priority" aria-label="우선순위">
          <option value="med">보통</option>
          <option value="high">높음</option>
          <option value="low">낮음</option>
        </select>
        <input type="date" name="due" aria-label="마감일" />
        <button type="submit" class="primary-btn">추가</button>
      </form>
      <div class="seg-control">${raw(filterChips)}</div>
      <div class="todo-list">${raw(listHTML)}</div>
    </section>
  `);
}

function quickAddTodo(form) {
  if (!form) return;
  const input = form.querySelector("input[name=title]");
  const title = (input && input.value || "").trim();
  if (!title) { if (input) input.focus(); return; }
  const priority = (form.querySelector("[name=priority]") || {}).value || "med";
  const due = ((form.querySelector("[name=due]") || {}).value || "") || null;
  dashboard.todos.push({ id: uid("td"), title, due, priority, done: false, category: "", memo: "", createdAt: nowISO() });
  showToast("할 일을 추가했습니다", "info");
  commit();
  // Re-focus the (freshly rendered) quick-add input for fast entry.
  const next = refs.views.todo && refs.views.todo.querySelector(".todo-quickadd input[name=title]");
  if (next) next.focus();
}

function openTodoModal(arg) {
  const editing = arg && typeof arg === "object";
  const t = editing ? arg : null;
  const form = html`
    <form id="todoForm" class="modal-form">
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
      ${editing ? raw(html`<button type="button" class="modal-delete" data-action="delete-todo" data-todo-id="${t.id}">이 할 일 삭제</button>`) : ""}
    </form>
  `;
  openModal(editing ? "할 일 편집" : "새 할 일", form, () => saveTodoFromForm(editing ? t.id : null));
}

function saveTodoFromForm(id) {
  const form = document.querySelector("#todoForm");
  if (!form) return false;
  const data = new FormData(form);
  const title = (data.get("title") || "").toString().trim();
  if (!title) { showToast("내용을 입력하세요", "warn"); return false; }
  const due = ((data.get("due") || "").toString() || null);
  const priority = (data.get("priority") || "med").toString();
  const category = (data.get("category") || "").toString().trim();
  const memo = (data.get("memo") || "").toString().trim();
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
  const idx = dashboard.todos.findIndex((t) => t.id === id);
  if (idx >= 0) { dashboard.todos.splice(idx, 1); showToast("할 일을 삭제했습니다", "info"); }
  closeModal();
  commit();
}

function setTodoFilter(key) {
  state.todoFilter = key || "active";
  renderTodos();
}

/* ============================================================
 * View: 메모 (Notes)
 * ============================================================ */

function renderNotes() {
  const view = refs.views.notes;
  if (!view) return;
  const q = state.query;
  const list = dashboard.notes
    .filter((n) => matches(`${n.title} ${n.body}`, q))
    .sort((a, b) => {
      if (!!a.pinned !== !!b.pinned) return a.pinned ? -1 : 1;
      return (b.updatedAt || "") < (a.updatedAt || "") ? -1 : 1;
    });

  const cards = list.length === 0
    ? html`<article class="empty">${q ? "일치하는 메모가 없습니다." : "메모가 없습니다. + 메모로 추가해 보세요."}</article>`
    : list.map((n) => {
        const body = (n.body || "").trim();
        const color = safeNoteColor(n.color);
        // Markdown 렌더(소독됨). null이면 라이브러리 미로드 → 평문 미리보기로 폴백.
        const rendered = body ? renderMarkdown(body) : null;
        const isMd = body && rendered != null;
        const bodyContent = body
          ? (isMd ? raw(rendered) : (body.length > 220 ? body.slice(0, 220) + "…" : body))
          : "내용 없음";
        // 본문은 버튼 밖 div로 분리 — 마크다운의 블록 요소·링크가 버튼 안에서
        // 비유효해지거나 클릭이 가로채이는 것을 막는다. 편집은 제목 클릭으로 연다.
        return html`
          <article class="note-card ${raw(n.pinned ? "is-pinned" : "")}" style="--note:${raw(color)}">
            <button type="button" class="note-open" data-action="open-note" data-note-id="${n.id}">
              <strong class="note-title">${n.title || "(제목 없음)"}</strong>
            </button>
            <div class="note-body ${raw(isMd ? "markdown-body" : "")}">${bodyContent}</div>
            <div class="note-foot">
              <small>${n.updatedAt ? formatKoreanShort(localYmd(n.updatedAt)) : ""}</small>
              <span class="note-actions">
                <button type="button" class="note-pin ${raw(n.pinned ? "is-on" : "")}" data-action="note-pin" data-note-id="${n.id}" aria-label="고정">${raw(n.pinned ? "★" : "☆")}</button>
                <button type="button" class="note-del" data-action="note-delete" data-note-id="${n.id}" aria-label="삭제">✕</button>
              </span>
            </div>
          </article>
        `;
      }).join("");

  setHTML(view, html`
    <section class="notes-toolbar">
      <div><strong>${dashboard.notes.length}</strong>개의 메모${dashboard.notes.filter((n) => n.pinned).length ? raw(html` · 고정 ${dashboard.notes.filter((n) => n.pinned).length}개`) : ""}</div>
      <button type="button" class="primary-btn" data-action="note-add">+ 메모</button>
    </section>
    <section class="notes-grid">${raw(cards)}</section>
  `);
}

function openNoteModal(arg) {
  const editing = arg && typeof arg === "object";
  const n = editing ? arg : null;
  const current = n ? n.color || NOTE_COLORS[0] : NOTE_COLORS[0];
  const swatches = NOTE_COLORS.map((c, i) => html`
    <label class="swatch" style="--sw:${raw(c)}">
      <input type="radio" name="color" value="${c}" ${raw((n ? n.color === c : i === 0) ? "checked" : "")} />
      <span></span>
    </label>
  `).join("");
  const form = html`
    <form id="noteForm" class="modal-form">
      <label>제목
        <input type="text" name="title" maxlength="120" value="${n ? n.title : ""}" placeholder="제목" />
      </label>
      <label>내용 <small class="field-hint">Markdown 지원</small>
        <textarea name="body" rows="6" maxlength="4000" placeholder="메모를 입력하세요  ·  **굵게**, - 목록, [링크](url), \`코드\`">${n ? n.body || "" : ""}</textarea>
      </label>
      <div class="form-row note-form-row">
        <div class="note-swatches" role="radiogroup" aria-label="색상">${raw(swatches)}</div>
        <label class="check-inline">
          <input type="checkbox" name="pinned" ${raw(n && n.pinned ? "checked" : "")} /> 상단 고정
        </label>
      </div>
      ${editing ? raw(html`<button type="button" class="modal-delete" data-action="delete-note" data-note-id="${n.id}">이 메모 삭제</button>`) : ""}
    </form>
  `;
  openModal(editing ? "메모 편집" : "새 메모", form, () => saveNoteFromForm(editing ? n.id : null));
}

function saveNoteFromForm(id) {
  const form = document.querySelector("#noteForm");
  if (!form) return false;
  const data = new FormData(form);
  const title = (data.get("title") || "").toString().trim();
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
  const idx = dashboard.notes.findIndex((n) => n.id === id);
  if (idx >= 0) { dashboard.notes.splice(idx, 1); showToast("메모를 삭제했습니다", "info"); }
  closeModal();
  commit();
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
  const logged = Object.keys(log).filter((d) => log[d]).sort();
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

function renderHabits() {
  const view = refs.views.habits;
  if (!view) return;
  if (!Array.isArray(dashboard.habits)) dashboard.habits = [];

  const today = todayISO();
  const weekDates = weekDatesFor(today);
  const active = dashboard.habits.filter((h) => !h.archived);

  // KPI calculations
  const todayDone = active.filter((h) => (h.log || {})[today]).length;
  const weekRates = active.map((h) => {
    const log = h.log || {};
    const target = h.target || 7;
    const doneDays = weekDates.filter((d) => log[d]).length;
    return Math.min(100, Math.round((doneDays / target) * 100));
  });
  const avgRate = weekRates.length ? Math.round(weekRates.reduce((s, r) => s + r, 0) / weekRates.length) : 0;
  const bestStreak = active.reduce((best, h) => {
    const { longest } = habitStreak(h);
    return longest > best ? longest : best;
  }, 0);

  const kpis = [
    { title: "활성 습관", value: String(active.length), unit: "개", color: "var(--cyan)", badge: "◉", delta: dashboard.habits.filter((h) => h.archived).length ? `보관 ${dashboard.habits.filter((h) => h.archived).length}개` : "관리 중" },
    { title: "오늘 완료", value: String(todayDone), unit: `/${active.length}`, color: "var(--green)", badge: "✓", delta: formatKoreanShort(today) },
    { title: "평균 달성률", value: String(avgRate), unit: "%", color: "var(--blue)", badge: "▦", delta: "이번 주" },
    { title: "최장 연속", value: String(bestStreak), unit: "일", color: "var(--violet)", badge: "🔥", delta: "전체 습관 중 최고" },
  ];

  // Per-habit cards
  const cardsHTML = active.length === 0
    ? html`<article class="empty">습관이 없습니다. <button type="button" class="link-btn" data-action="habit-add">+ 습관 추가</button>로 시작해 보세요.</article>`
    : active.map((h) => {
        const log = h.log || {};
        const { current, longest } = habitStreak(h);
        const target = h.target || 7;
        const weekDone = weekDates.filter((d) => log[d]).length;
        const rate = Math.min(100, Math.round((weekDone / target) * 100));
        const color = h.color || NOTE_COLORS[0];

        const dayButtons = weekDates.map((d, i) => {
          const checked = !!log[d];
          const isToday = d === today;
          const isFuture = d > today;
          return html`<button
            type="button"
            class="habit-day ${raw(checked ? "is-checked" : "")} ${raw(isToday ? "is-today" : "")} ${raw(isFuture ? "is-future" : "")}"
            data-action="${raw(isFuture ? "" : "habit-toggle")}"
            data-habit-id="${h.id}"
            data-date="${d}"
            ${raw(isFuture ? "disabled" : "")}
            aria-label="${WEEKDAYS_KO[i]}${raw(isToday ? " (오늘)" : "")}${raw(checked ? " 완료" : "")}"
            title="${d}"
          >${WEEKDAYS_KO[i]}</button>`;
        }).join("");

        return html`
          <article class="habit-card" style="--habit-color:${raw(color)}">
            <div class="habit-card-head">
              <span class="habit-emoji">${h.emoji || "✅"}</span>
              <strong class="habit-name">${h.name}</strong>
              <div class="habit-card-actions">
                <button type="button" class="icon-btn" data-action="open-habit" data-habit-id="${h.id}" aria-label="편집">✎</button>
                <button type="button" class="icon-btn icon-btn-del" data-action="habit-delete" data-habit-id="${h.id}" aria-label="삭제">✕</button>
              </div>
            </div>
            <div class="habit-week-grid">${raw(dayButtons)}</div>
            <div class="habit-stats-row">
              <span class="streak-badge">🔥 ${current}일 연속</span>
              <span class="streak-best">최장 ${longest}일</span>
              <span class="habit-week-prog">${weekDone}/${target} <small>(${rate}%)</small></span>
            </div>
            <div class="habit-bar-wrap">
              <div class="habit-bar" style="width:${rate}%;background:${raw(color)}"></div>
            </div>
          </article>
        `;
      }).join("");

  setHTML(view, html`
    <section class="kpis kpis-4">${raw(kpis.map((k) => kpiCard(k)).join(""))}</section>
    <section class="panel habits-panel">
      ${raw(panelHead("습관 트래커", null, html`<button type="button" class="primary-btn" data-action="habit-add">+ 습관 추가</button>`))}
      <div class="habits-grid">${raw(cardsHTML)}</div>
    </section>
  `);
}

function openHabitModal(arg) {
  const editing = arg && typeof arg === "object";
  const h = editing ? arg : null;
  const curColor = h ? (h.color || NOTE_COLORS[0]) : NOTE_COLORS[0];
  const swatches = NOTE_COLORS.map((c, i) => html`
    <label class="swatch" style="--sw:${raw(c)}">
      <input type="radio" name="color" value="${c}" ${raw((h ? h.color === c : i === 0) ? "checked" : "")} />
      <span></span>
    </label>
  `).join("");
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
        <div class="note-swatches" role="radiogroup" aria-label="색상">${raw(swatches)}</div>
      </div>
      ${editing ? raw(html`<button type="button" class="modal-delete" data-action="habit-delete" data-habit-id="${h.id}">이 습관 삭제</button>`) : ""}
    </form>
  `;
  openModal(editing ? "습관 편집" : "새 습관", form, () => saveHabitFromForm(editing ? h.id : null));
}

function saveHabitFromForm(id) {
  const form = document.querySelector("#habitForm");
  if (!form) return false;
  const data = new FormData(form);
  const name = (data.get("name") || "").toString().trim();
  if (!name) { showToast("이름을 입력하세요", "warn"); return false; }
  const emoji = (data.get("emoji") || "✅").toString().trim() || "✅";
  const color = (data.get("color") || NOTE_COLORS[0]).toString();
  const target = Math.min(7, Math.max(1, parseInt(data.get("target") || "7", 10) || 7));
  if (!Array.isArray(dashboard.habits)) dashboard.habits = [];
  if (id) {
    const h = dashboard.habits.find((x) => x.id === id);
    if (h) Object.assign(h, { name, emoji, color, target });
    showToast("습관을 수정했습니다", "info");
  } else {
    dashboard.habits.push({ id: uid("hb"), name, emoji, color, target, createdAt: nowISO(), archived: false, log: {} });
    showToast("습관을 추가했습니다", "info");
  }
  commit();
  return true;
}

function toggleHabit(habitId, dateISO) {
  if (!habitId || !dateISO) return;
  if (!Array.isArray(dashboard.habits)) dashboard.habits = [];
  const h = dashboard.habits.find((x) => x.id === habitId);
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
  const idx = dashboard.habits.findIndex((h) => h.id === id);
  if (idx >= 0) { dashboard.habits.splice(idx, 1); showToast("습관을 삭제했습니다", "info"); }
  closeModal();
  commit();
}

/* ============================================================
 * View: 통계 / 인사이트 (Stats)
 * ============================================================ */

/* barChart(items, opts) → SVG or HTML bar chart */
function barChart(items, opts) {
  // items: [{label, value, color}]
  // opts: {maxWidth: 200, height: 16, showValues: true, horizontal: true}
  if (!items || items.length === 0) return html`<p class="muted-note">데이터 없음</p>`;
  const maxVal = Math.max(...items.map((i) => i.value), 1);
  const maxWidth = (opts && opts.maxWidth) || 180;
  const barH = (opts && opts.height) || 14;
  const showValues = opts && opts.showValues !== false;
  return items.map((item) => {
    const pct = Math.round((item.value / maxVal) * 100);
    const w = Math.max(pct === 0 ? 0 : 4, Math.round((item.value / maxVal) * maxWidth));
    return html`
      <div class="bar-row">
        <span class="bar-label">${item.label}</span>
        <div class="bar-track" style="height:${barH}px">
          <div class="bar-fill" style="width:${w}px;height:${barH}px;background:${raw(item.color || "var(--blue)")}"></div>
        </div>
        ${showValues ? raw(html`<span class="bar-val">${item.value}</span>`) : ""}
      </div>
    `;
  }).join("");
}

function renderStats() {
  const view = refs.views.stats;
  if (!view) return;

  const today = todayISO();
  const todos = Array.isArray(dashboard.todos) ? dashboard.todos : [];
  const habits = Array.isArray(dashboard.habits) ? dashboard.habits : [];
  const events = Array.isArray(dashboard.events) ? dashboard.events : [];

  // KPI calculations
  const weekStart = weekDatesFor(today)[0];
  const weekTodoDone = todos.filter((t) => t.done && t.completedAt && localYmd(t.completedAt) >= weekStart && localYmd(t.completedAt) <= today).length;
  const totalDone = todos.filter((t) => t.done).length;
  const totalRate = todos.length ? Math.round((totalDone / todos.length) * 100) : 0;
  const activeHabits = habits.filter((h) => !h.archived).length;
  const upcomingDeadline7 = todos.filter((t) => !t.done && t.due && t.due >= today && t.due <= addDaysISO(today, 7)).length
    + events.filter((e) => e.category === "deadline" && e.date >= today && e.date <= addDaysISO(today, 7)).length;

  const kpis = [
    { title: "이번 주 완료", value: String(weekTodoDone), unit: "건", color: "var(--green)", badge: "✓", delta: "할 일" },
    { title: "전체 완료율", value: String(totalRate), unit: "%", color: "var(--blue)", badge: "▦", delta: `${totalDone}/${todos.length}건` },
    { title: "활성 습관", value: String(activeHabits), unit: "개", color: "var(--violet)", badge: "◉", delta: "습관 트래커" },
    { title: "다가오는 마감", value: String(upcomingDeadline7), unit: "건", color: upcomingDeadline7 ? "var(--red)" : "var(--green)", badge: "⚑", delta: "7일 이내", trendDown: upcomingDeadline7 > 0 },
  ];

  // 최근 14일 할 일 추이
  const last14 = [];
  for (let i = 13; i >= 0; i--) last14.push(addDaysISO(today, -i));

  const createdByDay = last14.map((d) =>
    todos.filter((t) => t.createdAt && localYmd(t.createdAt) === d).length
  );
  const completedByDay = last14.map((d) =>
    todos.filter((t) => t.completedAt && localYmd(t.completedAt) === d).length
  );

  const trendSection = (createdByDay.some((v) => v > 0) || completedByDay.some((v) => v > 0))
    ? html`
      <div class="stats-chart-block">
        <p class="stats-chart-title">생성 추이 <small style="color:var(--cyan)">(최근 14일)</small></p>
        <div class="spark-wrap">${raw(spark(createdByDay, "var(--cyan)"))}</div>
        <p class="stats-chart-title" style="margin-top:10px">완료 추이 <small style="color:var(--green)">(최근 14일)</small></p>
        <div class="spark-wrap">${raw(spark(completedByDay, "var(--green)"))}</div>
        <div class="spark-legend">
          <span><i style="background:var(--cyan)"></i>생성</span>
          <span><i style="background:var(--green)"></i>완료</span>
        </div>
      </div>`
    : html`<p class="muted-note">아직 할 일 기록이 없습니다.</p>`;

  // 요일별 완료 분포
  const doneByWeekday = [0, 0, 0, 0, 0, 0, 0];
  todos.forEach((t) => {
    if (t.done && t.completedAt) {
      const d = dateFromISO(localYmd(t.completedAt));
      doneByWeekday[d.getDay()] += 1;
    }
  });
  const weekdayItems = WEEKDAYS_KO.map((w, i) => ({
    label: w + "요일",
    value: doneByWeekday[i],
    color: i === 0 ? "var(--red)" : i === 6 ? "var(--blue)" : "var(--cyan)",
  }));
  const weekdaySection = doneByWeekday.some((v) => v > 0)
    ? html`<div class="bar-chart">${raw(barChart(weekdayItems, { maxWidth: 200, height: 14 }))}</div>`
    : html`<p class="muted-note">완료된 할 일 없음 (completedAt 필요)</p>`;

  // 일정 분류 분포
  const catCounts = {};
  EVENT_CAT_ORDER.forEach((k) => { catCounts[k] = 0; });
  events.forEach((e) => { if (catCounts[e.category] !== undefined) catCounts[e.category]++; else catCounts["etc"] = (catCounts["etc"] || 0) + 1; });
  const catItems = EVENT_CAT_ORDER.filter((k) => catCounts[k] > 0).map((k) => ({
    label: EVENT_CATS[k].label,
    value: catCounts[k],
    color: EVENT_CATS[k].color,
  }));
  const catSection = catItems.length
    ? html`<div class="bar-chart">${raw(barChart(catItems, { maxWidth: 200, height: 14 }))}</div>`
    : html`<p class="muted-note">일정이 없습니다.</p>`;

  // 습관 요약
  const habitSummaryRows = habits.filter((h) => !h.archived).map((h) => {
    const weekDates = weekDatesFor(today);
    const log = h.log || {};
    const weekDone = weekDates.filter((d) => log[d]).length;
    const target = h.target || 7;
    const pct = Math.min(100, Math.round((weekDone / target) * 100));
    const { current } = habitStreak(h);
    return html`
      <div class="habit-summary-row">
        <span class="habit-summary-emoji">${h.emoji || "✅"}</span>
        <div class="habit-summary-info">
          <strong>${h.name}</strong>
          <div class="habit-summary-bar-wrap">
            <div class="habit-summary-bar" style="width:${pct}%;background:${raw(h.color || "var(--cyan)")}"></div>
          </div>
          <small>${weekDone}/${target}일 · 🔥 ${current}일 연속</small>
        </div>
        <span class="habit-summary-pct">${pct}%</span>
      </div>
    `;
  }).join("");

  const habitSummarySection = habits.filter((h) => !h.archived).length
    ? html`<div class="habit-summary-list">${raw(habitSummaryRows)}</div>`
    : html`<p class="muted-note">활성 습관이 없습니다. <a href="#habits" data-action="nav-to" data-view="habits">습관 트래커</a>에서 추가해 보세요.</p>`;

  setHTML(view, html`
    <section class="kpis kpis-4">${raw(kpis.map((k) => kpiCard(k)).join(""))}</section>
    <div class="stats-grid">
      <section class="panel stats-panel">
        ${raw(panelHead("최근 14일 할 일 추이", null, ""))}
        <div class="stats-panel-body">${raw(trendSection)}</div>
      </section>
      <section class="panel stats-panel">
        ${raw(panelHead("요일별 완료 분포", null, ""))}
        <div class="stats-panel-body">${raw(weekdaySection)}</div>
      </section>
      <section class="panel stats-panel">
        ${raw(panelHead("일정 분류 분포", null, ""))}
        <div class="stats-panel-body">${raw(catSection)}</div>
      </section>
      <section class="panel stats-panel">
        ${raw(panelHead("습관 요약", null, ""))}
        <div class="stats-panel-body">${raw(habitSummarySection)}</div>
      </section>
    </div>
  `);
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
      settings:    dashboard.settings,
      habits:      dashboard.habits,
      projects:    dashboard.projects,
      issues:      dashboard.issues,
      gantt:       dashboard.gantt,
      team:        dashboard.team,
      dbInstances: dashboard.dbInstances,
      schemas:     dashboard.schemas,
      queries:     dashboard.queries,
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

function applyImported(obj) {
  if (!obj || typeof obj !== "object") { showToast("올바르지 않은 파일입니다", "error"); return; }
  // 개인 슬라이스가 하나라도 있어야 유효한 백업으로 인정
  if (!Array.isArray(obj.events) && !Array.isArray(obj.todos) && !Array.isArray(obj.notes)) {
    showToast("백업 형식이 아닙니다", "error");
    return;
  }
  // 개인 슬라이스
  if (Array.isArray(obj.events))  dashboard.events  = obj.events;
  if (Array.isArray(obj.todos))   dashboard.todos   = obj.todos;
  if (Array.isArray(obj.notes))   dashboard.notes   = obj.notes;
  if (obj.settings && typeof obj.settings === "object")
    dashboard.settings = { ...dashboard.settings, ...obj.settings };
  // 확장 슬라이스 (v3 백업에만 존재; 없으면 현재 값 유지)
  if (Array.isArray(obj.habits))      dashboard.habits      = obj.habits;
  if (Array.isArray(obj.projects))    dashboard.projects    = obj.projects;
  if (Array.isArray(obj.issues))      dashboard.issues      = obj.issues;
  if (obj.gantt && typeof obj.gantt === "object" && !Array.isArray(obj.gantt))
    dashboard.gantt = obj.gantt;
  if (Array.isArray(obj.team))        dashboard.team        = obj.team;
  if (Array.isArray(obj.dbInstances))  dashboard.dbInstances = obj.dbInstances;
  if (Array.isArray(obj.schemas))      dashboard.schemas     = obj.schemas;
  if (Array.isArray(obj.queries))      dashboard.queries     = obj.queries;
  if (Array.isArray(obj.migrations))   dashboard.migrations  = obj.migrations;
  if (obj.ui && typeof obj.ui === "object") dashboard.ui    = obj.ui;
  if (obj.imports && typeof obj.imports === "object") dashboard.imports = obj.imports;
  normalizeAllData();
  rebuildIndexes();
  commit();
  showToast("백업을 가져왔습니다 (기존 데이터 대체)", "info");
}

function handleImportFile(event) {
  const input = event.target;
  const file = input.files && input.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    let obj = null;
    try { obj = JSON.parse(reader.result); } catch (_) { showToast("JSON 파싱 실패", "error"); input.value = ""; return; }
    if (!obj || (!Array.isArray(obj.events) && !Array.isArray(obj.todos) && !Array.isArray(obj.notes))) {
      showToast("백업 형식이 아닙니다", "error"); input.value = ""; return;
    }
    const ne = Array.isArray(obj.events) ? obj.events.length : "—";
    const nt = Array.isArray(obj.todos) ? obj.todos.length : "—";
    const nn = Array.isArray(obj.notes) ? obj.notes.length : "—";
    // Replacing localStorage data is destructive and has no undo — confirm first
    // (mirrors confirmResetData), unlike the previous silent overwrite.
    openModal("백업 가져오기", html`
      <div class="modal-confirm-body">
        <p>가져올 데이터 — 일정 <strong>${ne}</strong> · 할 일 <strong>${nt}</strong> · 메모 <strong>${nn}</strong></p>
        <p class="muted-note">현재 저장된 일정 · 할 일 · 메모가 모두 <strong>대체</strong>됩니다. 되돌릴 수 없으니, 필요하면 먼저 내보내기로 백업하세요.</p>
      </div>
    `, () => { applyImported(obj); return true; });
    input.value = ""; // allow re-selecting the same file later
  };
  reader.onerror = () => { showToast("파일 읽기 실패", "error"); input.value = ""; };
  reader.readAsText(file);
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
    dashboard.habits = [];
    dashboard.projects = [];
    dashboard.issues = [];
    dashboard.gantt = { rangeStart: todayISO(), rangeEnd: addDaysISO(todayISO(), 60), tasks: [] };
    dashboard.team = [];
    dashboard.dbInstances = [];
    dashboard.schemas = [];
    dashboard.queries = [];
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

function saveSettingsFromForm(form) {
  if (!form) return;
  const data = new FormData(form);
  const displayName = (data.get("displayName") || "").toString().trim() || "사용자";
  dashboard.settings.displayName = displayName;
  persist();
  const avatar = document.querySelector(".user strong");
  if (avatar) avatar.textContent = displayName;
  showToast("설정을 저장했습니다", "info");
  renderSettings();
}

/* ============================================================
 * Router
 * ============================================================ */

const VIEWS = ["home", "cal", "todo", "notes", "habits", "stats", "pm-portfolio", "pm-kanban", "pm-gantt", "pm-team",
               "dbm-instances", "dbm-schema", "dbm-queries", "dbm-backups", "settings"];

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

function renderCurrentView() {
  switch (dashboard.currentView) {
    case "home":           return renderHome();
    case "cal":            return renderCalendar();
    case "todo":           return renderTodos();
    case "notes":          return renderNotes();
    case "habits":         return renderHabits();
    case "stats":          return renderStats();
    case "pm-portfolio":   return renderPortfolio();
    case "pm-kanban":      return renderKanban();
    case "pm-gantt":       return renderGantt();
    case "pm-team":        return renderTeam();
    case "dbm-instances":  return renderDbInstances();
    case "dbm-schema":     return renderDbSchema();
    case "dbm-queries":    return renderDbQueries();
    case "dbm-backups":    return renderDbBackups();
    case "settings":       return renderSettings();
    default:               return renderHome();
  }
}

let activeViewEl = null;
function setView(name) {
  if (!VIEWS.includes(name)) name = "home";
  const previous = dashboard.currentView;
  dashboard.currentView = name;
  document.body.dataset.view = name; // 상단바 맥락화(프로젝트 선택기 노출)·뷰별 CSS 훅

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
  setActiveNav(name);
  if (location.hash !== `#${name}`) history.replaceState(null, "", `#${name}`);
  state.query = "";
  state.kanbanFilter = null;
  if (refs.query) refs.query.value = "";
  if (refs.searchCount) refs.searchCount.textContent = "";
  renderCurrentView();
  if (name === "settings") refreshStorageHealth({ render: true });
  document.querySelector(".main").scrollTo({ top: 0, behavior: "instant" });
}

/* ============================================================
 * Kanban drag-and-drop
 * ============================================================ */

let kanbanDragId = null;

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
    board.querySelectorAll(".kanban-col").forEach((col) => col.classList.remove("drag-over"));
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
    if (id && newStatus) moveIssue(id, newStatus);
    board.querySelectorAll(".kanban-col").forEach((c) => c.classList.remove("drag-over"));
    kanbanDragId = null;
  });
}

/* ============================================================
 * PM CRUD — Projects, Issues (Kanban), Gantt Tasks, Team Members
 * ============================================================ */

/* ---- 공통 select 옵션 빌더 (배열 버전) ---- */
function simpleOptions(arr, valueKey, labelFn, current) {
  return arr.map((item) => html`<option value="${item[valueKey]}" ${raw(item[valueKey] === current ? "selected" : "")}>${labelFn(item)}</option>`).join("");
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
  const editing = arg && typeof arg === "object";
  const p = editing ? arg : null;
  const memberChecked = new Set(p ? p.members : []);
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
            ${raw(PM_STATUS_ORDER.map((k) => html`<option value="${k}" ${raw(p && p.status === k ? "selected" : "")}>${PM_STATUS_MAP[k]}</option>`).join(""))}
          </select>
        </label>
        <label>헬스
          <select name="health">
            ${raw(PM_HEALTH_ORDER.map((k) => html`<option value="${k}" ${raw(p && p.health === k ? "selected" : "")}>${PM_HEALTH_MAP[k]}</option>`).join(""))}
          </select>
        </label>
      </div>
      <label>멤버
        <div class="pm-checkbox-group">
          ${raw(checkboxList(dashboard.team, "id", (m) => `${m.name} (${m.role})`, memberChecked, "members"))}
        </div>
      </label>
      ${editing ? raw(html`<button type="button" class="modal-delete" data-action="project-delete" data-project-id="${p.id}">이 프로젝트 삭제</button>`) : ""}
    </form>
  `;
  openModal(editing ? "프로젝트 편집" : "새 프로젝트 등록", form, () => saveProjectFromForm(editing ? p.id : null));
}

function saveProjectFromForm(id) {
  const form = document.querySelector("#projectForm");
  if (!form) return false;
  const data = new FormData(form);
  const name = (data.get("name") || "").toString().trim();
  if (!name) { showToast("이름을 입력하세요", "warn"); return false; }
  const owner = (data.get("owner") || "").toString().trim() || "—";
  const deadline = (data.get("deadline") || "").toString() || "2099-12-31";
  const progress = Math.min(100, Math.max(0, parseInt(data.get("progress") || "0", 10) || 0));
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
  if (refs.projectSelectLabel) {
    const cur = currentProject();
    if (cur) refs.projectSelectLabel.textContent = cur.name;
  }
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
    const idx = dashboard.projects.findIndex((p2) => p2.id === id);
    if (idx >= 0) dashboard.projects.splice(idx, 1);
    // currentProjectId 보정
    if (dashboard.currentProjectId === id) {
      dashboard.currentProjectId = dashboard.projects.length ? dashboard.projects[0].id : "";
      if (refs.projectSelectLabel) {
        const cur = dashboard.projects[0];
        refs.projectSelectLabel.textContent = cur ? cur.name : "";
      }
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

function openIssueModal(arg) {
  const editing = arg && typeof arg === "object";
  const i = editing ? arg : null;
  const projOptions = dashboard.projects.map((p) => html`<option value="${p.id}" ${raw(i && i.project === p.id ? "selected" : (!i && p.id === dashboard.currentProjectId ? "selected" : ""))}>${p.name}</option>`).join("");
  const teamOptions = [html`<option value="">—</option>`, ...dashboard.team.map((m) => html`<option value="${m.id}" ${raw(i && i.assignee === m.id ? "selected" : "")}>${m.name} (${m.role})</option>`)].join("");
  const statusOptions = ISSUE_STATUS_ORDER.map((k) => html`<option value="${k}" ${raw(i && i.status === k ? "selected" : (!i && k === "todo" ? "selected" : ""))}>${ISSUE_STATUS_LABELS[k]}</option>`).join("");
  const prioOptions = ISSUE_PRIORITY_ORDER.map((k) => html`<option value="${k}" ${raw(i && i.priority === k ? "selected" : (!i && k === "med" ? "selected" : ""))}>${ISSUE_PRIORITY_MAP[k]}</option>`).join("");
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
      ${editing ? raw(html`<button type="button" class="modal-delete" data-action="issue-delete" data-issue-id="${i.id}">이 이슈 삭제</button>`) : ""}
    </form>
  `;
  openModal(editing ? `이슈 편집: ${i.id}` : "새 이슈", form, () => saveIssueFromForm(editing ? i.id : null));
}

function saveIssueFromForm(id) {
  const form = document.querySelector("#issueForm");
  if (!form) return false;
  const data = new FormData(form);
  const title = (data.get("title") || "").toString().trim();
  if (!title) { showToast("제목을 입력하세요", "warn"); return false; }
  const project = (data.get("project") || "").toString();
  if (!project) { showToast("프로젝트를 선택하세요", "warn"); return false; }
  const status = (data.get("status") || "todo").toString();
  const priority = (data.get("priority") || "med").toString();
  const assignee = (data.get("assignee") || "").toString();
  const due = (data.get("due") || "").toString() || null;
  const estimate = Math.max(0, parseFloat(data.get("estimate") || "1") || 0);
  const labelsRaw = (data.get("labels") || "").toString();
  const labels = labelsRaw ? labelsRaw.split(",").map((l) => l.trim()).filter(Boolean) : [];
  if (id) {
    const issue = indexes.issueById.get(id);
    if (issue) Object.assign(issue, { title, project, status, priority, assignee, due, estimate, labels });
    showToast("이슈를 수정했습니다", "info");
  } else {
    const newId = uid("issue");
    dashboard.issues.push({ id: newId, project, title, status, priority, assignee, labels, due, estimate });
    showToast("이슈를 추가했습니다", "info");
  }
  rebuildIndexes();
  commit();
  return true;
}

function deleteIssue(id) {
  const issue = indexes.issueById.get(id);
  if (!issue) return;
  const idx = dashboard.issues.findIndex((i) => i.id === id);
  if (idx >= 0) dashboard.issues.splice(idx, 1);
  rebuildIndexes();
  closeModal();
  showToast("이슈를 삭제했습니다", "info");
  commit();
}

function moveIssue(id, newStatus) {
  const issue = indexes.issueById.get(id);
  if (!issue) return;
  issue.status = newStatus;
  showToast(`이슈를 '${ISSUE_STATUS_LABELS[newStatus]}'으로 이동`, "info");
  commit();
}

/* ============================================================
 * Gantt Tasks CRUD
 * ============================================================ */

function openTaskModal(arg) {
  const editing = arg && typeof arg === "object";
  const t = editing ? arg : null;
  const projOptions = dashboard.projects.map((p) => html`<option value="${p.id}" ${raw(t && t.project === p.id ? "selected" : "")}>${p.name}</option>`).join("");
  const teamOptions = [html`<option value="">—</option>`, ...dashboard.team.map((m) => html`<option value="${m.id}" ${raw(t && t.owner === m.id ? "selected" : "")}>${m.name} (${m.role})</option>`)].join("");
  const colorOptions = TASK_COLOR_ORDER.map((k) => html`<option value="${k}" ${raw(t && t.color === k ? "selected" : (!t && k === "blue" ? "selected" : ""))}>${TASK_COLOR_MAP[k]}</option>`).join("");
  // deps: multi-select existing tasks (exclude self)
  const depSet = new Set(t ? t.deps : []);
  const otherTasks = dashboard.gantt.tasks.filter((x) => !t || x.id !== t.id);
  const depsHTML = otherTasks.length ? html`
    <label>의존 작업 (복수 선택 가능)
      <select name="deps" multiple size="${Math.min(6, otherTasks.length)}" class="pm-multi-select">
        ${raw(otherTasks.map((x) => html`<option value="${x.id}" ${raw(depSet.has(x.id) ? "selected" : "")}>${x.name} (${x.id})</option>`).join(""))}
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
          <input type="checkbox" name="milestone" ${raw(t && t.milestone ? "checked" : "")} /> 마일스톤
        </label>
      </div>
      ${raw(depsHTML)}
      ${editing ? raw(html`<button type="button" class="modal-delete" data-action="task-delete" data-task-id="${t.id}">이 작업 삭제</button>`) : ""}
    </form>
  `;
  openModal(editing ? `작업 편집: ${t.name}` : "새 작업 추가", form, () => saveTaskFromForm(editing ? t.id : null));
}

function saveTaskFromForm(id) {
  const form = document.querySelector("#taskForm");
  if (!form) return false;
  const data = new FormData(form);
  const name = (data.get("name") || "").toString().trim();
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
    const task = dashboard.gantt.tasks.find((x) => x.id === id);
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
  const task = dashboard.gantt.tasks.find((x) => x.id === id);
  if (!task) return;
  dashboard.gantt.tasks = dashboard.gantt.tasks.filter((x) => x.id !== id);
  // 다른 작업의 deps 에서도 제거
  dashboard.gantt.tasks.forEach((x) => { x.deps = x.deps.filter((d) => d !== id); });
  closeModal();
  showToast("작업을 삭제했습니다", "info");
  commit();
}

/* ============================================================
 * Team Members CRUD
 * ============================================================ */

function openMemberModal(arg) {
  const editing = arg && typeof arg === "object";
  const m = editing ? arg : null;
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
      ${editing ? raw(html`<button type="button" class="modal-delete" data-action="member-delete" data-member-id="${m.id}">이 멤버 삭제</button>`) : ""}
    </form>
  `;
  openModal(editing ? `멤버 편집: ${m.name}` : "새 멤버 추가", form, () => saveMemberFromForm(editing ? m.id : null));
}

function saveMemberFromForm(id) {
  const form = document.querySelector("#memberForm");
  if (!form) return false;
  const data = new FormData(form);
  const name = (data.get("name") || "").toString().trim();
  if (!name) { showToast("이름을 입력하세요", "warn"); return false; }
  const role = (data.get("role") || "").toString().trim();
  const load = Math.min(100, Math.max(0, parseInt(data.get("load") || "0", 10) || 0));
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
    const idx = dashboard.team.findIndex((m2) => m2.id === id);
    if (idx >= 0) dashboard.team.splice(idx, 1);
    rebuildIndexes();
    closeModal();
    showToast(`멤버 '${m.name}' 삭제`, "info");
    commit();
    return true;
  });
}

/* ============================================================
 * DB CRUD — Instances, Tables, Columns, Queries, Migrations
 * ============================================================ */

const DB_HEALTH_MAP   = { green: "녹색", amber: "주황", red: "적색" };
const DB_HEALTH_ORDER = ["green", "amber", "red"];
const MIG_STATUS_MAP   = { pending: "대기", review: "검토", applied: "적용", "rolled-back": "롤백" };
const MIG_STATUS_ORDER = ["pending", "review", "applied", "rolled-back"];

/* helper: find a table object (and its instance/db context) by table id */
function findTableById(tableId) {
  for (const s of dashboard.schemas) {
    for (const db of s.databases) {
      const t = db.tables.find((x) => x.id === tableId);
      if (t) return { table: t, instanceId: s.id, dbName: db.name, schema: s, db };
    }
  }
  return null;
}

/* helper: select options for instances */
function instanceSelectOptions(current) {
  return dashboard.dbInstances.map((d) => html`<option value="${d.id}" ${raw(d.id === current ? "selected" : "")}>${d.name}</option>`).join("");
}

/* ---- Instances CRUD ---- */

function openInstanceModal(arg) {
  const editing = arg && typeof arg === "object";
  const d = editing ? arg : null;
  const form = html`
    <form id="instanceForm" class="modal-form">
      <label>이름
        <input type="text" name="name" required maxlength="80" value="${d ? d.name : ""}" placeholder="예: prod-postgres-01" />
      </label>
      <div class="form-row">
        <label>엔진
          <input type="text" name="engine" maxlength="60" value="${d ? d.engine : ""}" placeholder="예: PostgreSQL 15.3" />
        </label>
        <label>리전
          <input type="text" name="region" maxlength="40" value="${d ? d.region : ""}" placeholder="예: ap-northeast-2" />
        </label>
      </div>
      <div class="form-row">
        <label>CPU (%)
          <input type="number" name="cpu" min="0" max="100" value="${d ? d.cpu : 0}" />
        </label>
        <label>메모리 (%)
          <input type="number" name="mem" min="0" max="100" value="${d ? d.mem : 0}" />
        </label>
      </div>
      <div class="form-row">
        <label>연결 수
          <input type="number" name="conn" min="0" value="${d ? d.conn : 0}" />
        </label>
        <label>최대 연결
          <input type="number" name="connMax" min="1" value="${d ? d.connMax : 100}" />
        </label>
        <label>지연 (ms)
          <input type="number" name="latencyMs" min="0" value="${d ? d.latencyMs : 0}" />
        </label>
      </div>
      <label>헬스
        <select name="health">
          ${raw(DB_HEALTH_ORDER.map((k) => html`<option value="${k}" ${raw(d && d.health === k ? "selected" : (!d && k === "green" ? "selected" : ""))}>${DB_HEALTH_MAP[k]}</option>`).join(""))}
        </select>
      </label>
      ${editing ? raw(html`<button type="button" class="modal-delete" data-action="instance-delete" data-instance-id="${d.id}">이 인스턴스 삭제</button>`) : ""}
    </form>
  `;
  openModal(editing ? `인스턴스 편집: ${d.name}` : "새 인스턴스 추가", form, () => saveInstanceFromForm(editing ? d.id : null));
}

function saveInstanceFromForm(id) {
  const form = document.querySelector("#instanceForm");
  if (!form) return false;
  const data = new FormData(form);
  const name = (data.get("name") || "").toString().trim();
  if (!name) { showToast("이름을 입력하세요", "warn"); return false; }
  const engine    = (data.get("engine") || "").toString().trim();
  const region    = (data.get("region") || "").toString().trim();
  const cpu       = Math.min(100, Math.max(0, parseInt(data.get("cpu") || "0", 10) || 0));
  const mem       = Math.min(100, Math.max(0, parseInt(data.get("mem") || "0", 10) || 0));
  const conn      = Math.max(0, parseInt(data.get("conn") || "0", 10) || 0);
  const connMax   = Math.max(1, parseInt(data.get("connMax") || "100", 10) || 1);
  const latencyMs = Math.max(0, parseInt(data.get("latencyMs") || "0", 10) || 0);
  const health    = (data.get("health") || "green").toString();
  if (id) {
    const inst = indexes.instanceById.get(id);
    if (inst) Object.assign(inst, { name, engine, region, cpu, mem, conn, connMax, latencyMs, health });
    showToast(`인스턴스 '${name}' 수정`, "info");
  } else {
    const newId = uid("db");
    dashboard.dbInstances.push({ id: newId, name, engine, region, cpu, mem, conn, connMax, health, latencyMs, series: [] });
    dashboard.currentInstanceId = newId;
    showToast(`인스턴스 '${name}' 추가`, "info");
  }
  rebuildIndexes();
  commit();
  return true;
}

function deleteInstance(id) {
  const inst = indexes.instanceById.get(id);
  if (!inst) return;
  const relSchemas = dashboard.schemas.filter((s) => s.id === id);
  const relTables = relSchemas.reduce((a, s) => a + s.databases.reduce((b, db) => b + db.tables.length, 0), 0);
  const relQueries = dashboard.queries.filter((q) => q.instance === id).length;
  const relMigs = dashboard.migrations.filter((m) => m.instance === id).length;
  openModal("인스턴스 삭제", html`
    <div class="modal-confirm-body">
      <p>인스턴스 <strong>${inst.name}</strong>을(를) 삭제합니다.</p>
      <p class="muted-note">연결된 스키마(테이블 ${relTables}개) · 쿼리 ${relQueries}건 · 마이그레이션 ${relMigs}건도 함께 삭제됩니다. 되돌릴 수 없습니다.</p>
    </div>
  `, () => {
    dashboard.schemas = dashboard.schemas.filter((s) => s.id !== id);
    dashboard.queries = dashboard.queries.filter((q) => q.instance !== id);
    dashboard.migrations = dashboard.migrations.filter((m) => m.instance !== id);
    const idx = dashboard.dbInstances.findIndex((d) => d.id === id);
    if (idx >= 0) dashboard.dbInstances.splice(idx, 1);
    if (dashboard.currentInstanceId === id) {
      dashboard.currentInstanceId = dashboard.dbInstances.length ? dashboard.dbInstances[0].id : "";
    }
    rebuildIndexes();
    closeModal();
    showToast(`인스턴스 '${inst.name}' 삭제`, "info");
    commit();
    return true;
  });
}

/* ---- Tables CRUD ---- */

function openTableModal(arg) {
  const editing = arg && typeof arg === "object";
  const t = editing ? arg : null;
  let editInstanceId = "";
  let editDbName = "";
  if (t) {
    const ctx = findTableById(t.id);
    if (ctx) { editInstanceId = ctx.instanceId; editDbName = ctx.dbName; }
  }
  const form = html`
    <form id="tableForm" class="modal-form">
      <label>인스턴스
        <select name="instanceId">${raw(instanceSelectOptions(editInstanceId || dashboard.currentInstanceId))}</select>
      </label>
      <div class="form-row">
        <label>데이터베이스명
          <input type="text" name="dbName" required maxlength="60" value="${editDbName}" placeholder="예: radar" />
        </label>
        <label>테이블명
          <input type="text" name="tableName" required maxlength="80" value="${t ? t.name : ""}" placeholder="예: users" />
        </label>
      </div>
      <div class="form-row">
        <label>행 수
          <input type="number" name="rows" min="0" value="${t ? t.rows || 0 : 0}" />
        </label>
        <label>크기 (MB)
          <input type="number" name="sizeMb" min="0" value="${t ? t.sizeMb || 0 : 0}" />
        </label>
      </div>
      ${editing ? raw(html`<button type="button" class="modal-delete" data-action="table-delete" data-table-id="${t.id}">이 테이블 삭제</button>`) : ""}
    </form>
  `;
  openModal(editing ? `테이블 편집: ${t.name}` : "새 테이블 추가", form, () => saveTableFromForm(editing ? t.id : null));
}

function saveTableFromForm(id) {
  const form = document.querySelector("#tableForm");
  if (!form) return false;
  const data = new FormData(form);
  const instanceId = (data.get("instanceId") || "").toString();
  if (!instanceId) { showToast("인스턴스를 선택하세요", "warn"); return false; }
  const dbName    = (data.get("dbName") || "").toString().trim();
  if (!dbName) { showToast("데이터베이스명을 입력하세요", "warn"); return false; }
  const tableName = (data.get("tableName") || "").toString().trim();
  if (!tableName) { showToast("테이블명을 입력하세요", "warn"); return false; }
  const rows   = Math.max(0, parseInt(data.get("rows") || "0", 10) || 0);
  const sizeMb = Math.max(0, parseFloat(data.get("sizeMb") || "0") || 0);

  if (id) {
    const ctx = findTableById(id);
    if (!ctx) { showToast("테이블을 찾을 수 없습니다", "error"); return false; }
    // Move to a different instance/db if changed
    if (ctx.instanceId !== instanceId || ctx.dbName !== dbName) {
      // Remove from old location
      ctx.db.tables = ctx.db.tables.filter((x) => x.id !== id);
      if (ctx.db.tables.length === 0) ctx.schema.databases = ctx.schema.databases.filter((d) => d.name !== ctx.dbName);
      // Insert into new location
      let targetSchema = dashboard.schemas.find((s) => s.id === instanceId);
      if (!targetSchema) { targetSchema = { id: instanceId, databases: [] }; dashboard.schemas.push(targetSchema); }
      let targetDb = targetSchema.databases.find((d) => d.name === dbName);
      if (!targetDb) { targetDb = { name: dbName, tables: [] }; targetSchema.databases.push(targetDb); }
      Object.assign(ctx.table, { name: tableName, rows, sizeMb });
      targetDb.tables.push(ctx.table);
    } else {
      Object.assign(ctx.table, { name: tableName, rows, sizeMb });
    }
    showToast(`테이블 '${tableName}' 수정`, "info");
  } else {
    let targetSchema = dashboard.schemas.find((s) => s.id === instanceId);
    if (!targetSchema) { targetSchema = { id: instanceId, databases: [] }; dashboard.schemas.push(targetSchema); }
    let targetDb = targetSchema.databases.find((d) => d.name === dbName);
    if (!targetDb) { targetDb = { name: dbName, tables: [] }; targetSchema.databases.push(targetDb); }
    const newId = uid("t");
    targetDb.tables.push({ id: newId, name: tableName, rows, sizeMb, columns: [], indexes: [], fks: [] });
    showToast(`테이블 '${tableName}' 추가`, "info");
  }
  commit();
  return true;
}

function deleteTable(tableId) {
  const ctx = findTableById(tableId);
  if (!ctx) return;
  openModal("테이블 삭제", html`
    <div class="modal-confirm-body">
      <p>테이블 <strong>${ctx.dbName}.${ctx.table.name}</strong>을(를) 삭제합니다.</p>
      <p class="muted-note">컬럼 · 인덱스 · 외래키 정보도 모두 삭제됩니다. 되돌릴 수 없습니다.</p>
    </div>
  `, () => {
    ctx.db.tables = ctx.db.tables.filter((t) => t.id !== tableId);
    if (ctx.db.tables.length === 0) {
      ctx.schema.databases = ctx.schema.databases.filter((d) => d.name !== ctx.dbName);
    }
    if (state.schemaSelectedTable === tableId) state.schemaSelectedTable = null;
    closeModal();
    closeSheet();
    showToast(`테이블 '${ctx.table.name}' 삭제`, "info");
    commit();
    return true;
  });
}

/* ---- Columns CRUD ---- */

function openColumnModal(tableId, colIndex) {
  const ctx = findTableById(tableId);
  if (!ctx) return;
  const editing = colIndex !== null && colIndex !== undefined;
  const c = editing ? ctx.table.columns[colIndex] : null;
  const form = html`
    <form id="columnForm" class="modal-form">
      <div class="form-row">
        <label>이름
          <input type="text" name="colName" required maxlength="80" value="${c ? c.name : ""}" placeholder="예: user_id" />
        </label>
        <label>타입
          <input type="text" name="colType" maxlength="60" value="${c ? c.type : ""}" placeholder="예: bigint" />
        </label>
      </div>
      <div class="form-row">
        <label class="check-inline">
          <input type="checkbox" name="pk" ${raw(c && c.pk ? "checked" : "")} /> PK
        </label>
        <label class="check-inline">
          <input type="checkbox" name="nullable" ${raw(!c || c.nullable !== false ? "checked" : "")} /> NULL 허용
        </label>
      </div>
      <label>FK 참조 (선택)
        <input type="text" name="fk" maxlength="120" value="${c && c.fk ? c.fk : ""}" placeholder="예: users.id" />
      </label>
    </form>
  `;
  openModal(editing ? `컬럼 편집: ${c.name}` : `컬럼 추가 — ${ctx.dbName}.${ctx.table.name}`, form, () => saveColumnFromForm(tableId, editing ? colIndex : null));
}

function saveColumnFromForm(tableId, colIndex) {
  const form = document.querySelector("#columnForm");
  if (!form) return false;
  const ctx = findTableById(tableId);
  if (!ctx) { showToast("테이블을 찾을 수 없습니다", "error"); return false; }
  const data = new FormData(form);
  const colName = (data.get("colName") || "").toString().trim();
  if (!colName) { showToast("컬럼 이름을 입력하세요", "warn"); return false; }
  const colType  = (data.get("colType") || "").toString().trim() || "text";
  const pk       = data.get("pk") === "on";
  const nullable = data.get("nullable") === "on";
  const fk       = (data.get("fk") || "").toString().trim() || undefined;
  const col = { name: colName, type: colType };
  if (pk) col.pk = true;
  if (!nullable) col.nullable = false;
  if (fk) col.fk = fk;

  if (colIndex !== null && colIndex !== undefined) {
    ctx.table.columns[colIndex] = col;
    showToast(`컬럼 '${colName}' 수정`, "info");
  } else {
    ctx.table.columns.push(col);
    showToast(`컬럼 '${colName}' 추가`, "info");
  }
  commit();
  // Re-open table sheet to refresh column list
  openTableSheet(tableId);
  return true;
}

function deleteColumn(tableId, colIndex) {
  const ctx = findTableById(tableId);
  if (!ctx) return;
  const col = ctx.table.columns[colIndex];
  if (!col) return;
  openModal("컬럼 삭제", html`
    <div class="modal-confirm-body">
      <p>컬럼 <strong>${col.name}</strong>을(를) 삭제합니다. 되돌릴 수 없습니다.</p>
    </div>
  `, () => {
    ctx.table.columns.splice(colIndex, 1);
    closeModal();
    showToast(`컬럼 '${col.name}' 삭제`, "info");
    commit();
    openTableSheet(tableId);
    return true;
  });
}

/* ---- Saved Queries CRUD ---- */

function openQueryModal(arg) {
  const editing = arg && typeof arg === "object";
  const qi = editing ? arg : null;
  const form = html`
    <form id="queryForm" class="modal-form">
      <div class="form-row">
        <label>인스턴스
          <select name="instance">${raw(instanceSelectOptions(qi ? qi.instance : dashboard.currentInstanceId))}</select>
        </label>
        <label>DB
          <input type="text" name="db" maxlength="60" value="${qi ? qi.db : ""}" placeholder="예: radar" />
        </label>
      </div>
      <label>쿼리문 (SQL)
        <textarea name="text" rows="5" maxlength="2000" placeholder="SELECT ...">${qi ? qi.text : ""}</textarea>
      </label>
      <div class="form-row">
        <label>평균 ms
          <input type="number" name="avgMs" min="0" value="${qi ? qi.avgMs : 0}" />
        </label>
        <label>p95 ms
          <input type="number" name="p95Ms" min="0" value="${qi ? qi.p95Ms : 0}" />
        </label>
        <label>실행 횟수
          <input type="number" name="count" min="0" value="${qi ? qi.count : 0}" />
        </label>
      </div>
      <label>비고 (Plan Hint)
        <input type="text" name="planHint" maxlength="200" value="${qi ? qi.planHint || "" : ""}" placeholder="예: seq scan on users" />
      </label>
      ${editing ? raw(html`<button type="button" class="modal-delete" data-action="query-delete" data-query-id="${qi.id}">이 쿼리 삭제</button>`) : ""}
    </form>
  `;
  openModal(editing ? `쿼리 편집: ${qi.id}` : "쿼리 추가", form, () => saveQueryFromForm(editing ? qi.id : null));
}

function saveQueryFromForm(id) {
  const form = document.querySelector("#queryForm");
  if (!form) return false;
  const data = new FormData(form);
  const instance  = (data.get("instance") || "").toString();
  if (!instance) { showToast("인스턴스를 선택하세요", "warn"); return false; }
  const db        = (data.get("db") || "").toString().trim();
  const text      = (data.get("text") || "").toString().trim();
  if (!text) { showToast("쿼리문을 입력하세요", "warn"); return false; }
  const avgMs     = Math.max(0, parseInt(data.get("avgMs") || "0", 10) || 0);
  const p95Ms     = Math.max(0, parseInt(data.get("p95Ms") || "0", 10) || 0);
  const count     = Math.max(0, parseInt(data.get("count") || "0", 10) || 0);
  const planHint  = (data.get("planHint") || "").toString().trim();
  if (id) {
    const qi = dashboard.queries.find((x) => x.id === id);
    if (qi) Object.assign(qi, { instance, db, text, avgMs, p95Ms, count, planHint });
    showToast("쿼리를 수정했습니다", "info");
  } else {
    const newId = uid("Q");
    dashboard.queries.push({ id: newId, instance, db, text, avgMs, p95Ms, count, planHint, lastRun: formatLocalDateTime(nowISO()) });
    showToast("쿼리를 추가했습니다", "info");
  }
  commit();
  return true;
}

function deleteQuery(id) {
  const qi = dashboard.queries.find((x) => x.id === id);
  if (!qi) return;
  const idx = dashboard.queries.findIndex((x) => x.id === id);
  if (idx >= 0) dashboard.queries.splice(idx, 1);
  closeModal();
  closeSheet();
  showToast("쿼리를 삭제했습니다", "info");
  commit();
}

/* ---- Migrations CRUD ---- */

function openMigrationModal(arg) {
  const editing = arg && typeof arg === "object";
  const m = editing ? arg : null;
  const dateVal = m ? (m.appliedAt || m.scheduledAt || "").slice(0, 10) : "";
  const form = html`
    <form id="migrationForm" class="modal-form">
      <label>인스턴스
        <select name="instance">${raw(instanceSelectOptions(m ? m.instance : dashboard.currentInstanceId))}</select>
      </label>
      <label>제목
        <input type="text" name="title" required maxlength="120" value="${m ? m.title : ""}" placeholder="예: add index on users.email" />
      </label>
      <div class="form-row">
        <label>상태
          <select name="status">
            ${raw(MIG_STATUS_ORDER.map((k) => html`<option value="${k}" ${raw(m && m.status === k ? "selected" : (!m && k === "pending" ? "selected" : ""))}>${MIG_STATUS_MAP[k]}</option>`).join(""))}
          </select>
        </label>
        <label>일시 (적용 또는 예정)
          <input type="date" name="migDate" value="${dateVal}" />
        </label>
      </div>
      ${editing ? raw(html`<button type="button" class="modal-delete" data-action="migration-delete" data-mig-id="${m.id}">이 마이그레이션 삭제</button>`) : ""}
    </form>
  `;
  openModal(editing ? `마이그레이션 편집: ${m.id}` : "마이그레이션 추가", form, () => saveMigrationFromForm(editing ? m.id : null));
}

function saveMigrationFromForm(id) {
  const form = document.querySelector("#migrationForm");
  if (!form) return false;
  const data = new FormData(form);
  const instance = (data.get("instance") || "").toString();
  if (!instance) { showToast("인스턴스를 선택하세요", "warn"); return false; }
  const title  = (data.get("title") || "").toString().trim();
  if (!title) { showToast("제목을 입력하세요", "warn"); return false; }
  const status   = (data.get("status") || "pending").toString();
  const migDate  = (data.get("migDate") || "").toString();
  const dateTimeVal = migDate ? migDate + " 02:00" : undefined;

  if (id) {
    const m = dashboard.migrations.find((x) => x.id === id);
    if (m) {
      m.instance = instance;
      m.title    = title;
      m.status   = status;
      delete m.appliedAt;
      delete m.scheduledAt;
      if (status === "applied" || status === "rolled-back") { if (dateTimeVal) m.appliedAt = dateTimeVal; }
      else { if (dateTimeVal) m.scheduledAt = dateTimeVal; }
    }
    showToast("마이그레이션을 수정했습니다", "info");
  } else {
    const newId = uid("M");
    const entry = { id: newId, instance, title, status };
    if (status === "applied" || status === "rolled-back") { if (dateTimeVal) entry.appliedAt = dateTimeVal; }
    else { if (dateTimeVal) entry.scheduledAt = dateTimeVal; }
    dashboard.migrations.push(entry);
    showToast("마이그레이션을 추가했습니다", "info");
  }
  commit();
  return true;
}

function deleteMigration(id) {
  const m = dashboard.migrations.find((x) => x.id === id);
  if (!m) return;
  const idx = dashboard.migrations.findIndex((x) => x.id === id);
  if (idx >= 0) dashboard.migrations.splice(idx, 1);
  closeModal();
  closeSheet();
  showToast("마이그레이션을 삭제했습니다", "info");
  commit();
}

/* ============================================================
 * Actions
 * ============================================================ */

function handleActions(event) {
  const target = event.target.closest("[data-action]");
  if (!target) return;
  const action = target.getAttribute("data-action");
  if (action === "close-palette") { closePalette(); return; }
  if (action === "close-sheet") { closeSheet(); return; }
  if (action === "close-modal") { closeModal(); return; }
  if (action === "modal-confirm") {
    const cb = state.modalOnConfirm;
    if (typeof cb === "function") { if (cb() !== false) closeModal(); }
    else closeModal();
    return;
  }
  if (action === "open-new-project") { openNewProjectModal(); return; }
  if (action === "open-notifications") { openNotificationsSheet(); return; }
  if (action === "request-notif-permission") {
    try {
      if ("Notification" in window && Notification.permission === "default") {
        Notification.requestPermission().then((perm) => {
          if (perm === "granted") {
            showToast("브라우저 알림 권한이 허용되었습니다", "info");
            startEventReminders();
          } else {
            showToast("알림 권한이 거부되었습니다", "warn");
          }
        }).catch(() => {});
      }
    } catch (_) {}
    return;
  }
  if (action === "nav-to") { setView(target.dataset.view); return; }
  if (action === "open-palette") { openPalette(); return; }

  /* --- 일정 (Calendar) --- */
  if (action === "cal-prev") { calNav(-1); return; }
  if (action === "cal-next") { calNav(1); return; }
  if (action === "cal-today") { calToday(); return; }
  if (action === "cal-open-day") { calSelectDay(target.dataset.date); return; }
  if (action === "cal-add") { openEventModal(target.dataset.date || null); return; }
  if (action === "open-event") { openEventModal(eventById(target.dataset.eventId)); return; }
  if (action === "delete-event") { deleteEvent(target.dataset.eventId); return; }
  if (action === "skip-occurrence") { skipOccurrence(target.dataset.eventId, target.dataset.date); return; }

  /* --- 할 일 (To-Do) --- */
  if (action === "todo-quick-add") { quickAddTodo(target); return; }
  if (action === "todo-add") { openTodoModal(null); return; }
  if (action === "open-todo") { openTodoModal(todoById(target.dataset.todoId)); return; }
  if (action === "todo-toggle") { toggleTodo(target.dataset.todoId); return; }
  if (action === "todo-delete") { deleteTodo(target.dataset.todoId); return; }
  if (action === "delete-todo") { deleteTodo(target.dataset.todoId); return; }
  if (action === "todo-filter") { setTodoFilter(target.dataset.filter); return; }

  /* --- 메모 (Notes) --- */
  if (action === "note-add") { openNoteModal(null); return; }
  if (action === "open-note") { openNoteModal(noteById(target.dataset.noteId)); return; }
  if (action === "note-pin") { togglePin(target.dataset.noteId); return; }
  if (action === "note-delete") { deleteNote(target.dataset.noteId); return; }
  if (action === "delete-note") { deleteNote(target.dataset.noteId); return; }

  /* --- 습관 (Habits) --- */
  if (action === "habit-add") { openHabitModal(null); return; }
  if (action === "open-habit") {
    const hid = target.dataset.habitId;
    openHabitModal((dashboard.habits || []).find((h) => h.id === hid)); return;
  }
  if (action === "habit-toggle") { toggleHabit(target.dataset.habitId, target.dataset.date); return; }
  if (action === "habit-delete") { deleteHabit(target.dataset.habitId); return; }

  /* --- 설정 / 백업 --- */
  if (action === "export-data") { exportData(); return; }
  if (action === "reset-data") { confirmResetData(); return; }
  if (action === "save-settings") { saveSettingsFromForm(target); return; }
  if (action === "refresh-storage-health") { refreshStorageHealth({ render: true }); return; }
  if (action === "request-storage-persistence") { requestStoragePersistence(); return; }
  if (action === "toggle-theme") { toggleTheme(); return; }
  if (action === "set-theme") { setTheme(target.dataset.theme); return; }

  if (action === "toggle-project-picker") { toggleProjectPicker(); return; }
  if (action === "pick-project") { pickProject(target.dataset.projectId); return; }
  if (action === "open-project") { openProjectSheet(target.dataset.projectId); return; }
  if (action === "portfolio-filter") { setPortfolioFilter(target.dataset.filter); return; }
  if (action === "portfolio-action-filter") { setPortfolioActionFilter(target.dataset.actionFilter); return; }
  if (action === "portfolio-benchmark-filter") { setPortfolioBenchmarkFilter(target.dataset.benchmarkFilter); return; }
  if (action === "copy-review-handoff") { copyBenchmarkReviewHandoff(target); return; }
  if (action === "copy-review-github-comment") { copyReviewGithubComment(target); return; }
  if (action === "create-review-issue") { createBenchmarkReviewIssue(target); return; }
  if (action === "publish-review-note") { publishReviewHandoffNote(target); return; }
  if (action === "open-issue")   { openIssueSheet(target.dataset.issueId); return; }
  if (action === "open-task")    { openTaskSheet(target.dataset.taskId); return; }
  if (action === "open-member")  { openMemberSheet(target.dataset.memberId); return; }
  if (action === "pick-instance"){ pickInstance(target.dataset.instanceId); return; }
  if (action === "open-table")   { openTableSheet(target.dataset.tableId); return; }
  if (action === "open-query")   { openQuerySheet(target.dataset.queryId); return; }
  if (action === "open-backup")  { openBackupSheet(target.dataset.date); return; }
  if (action === "open-migration"){ openMigrationSheet(target.dataset.migId); return; }
  if (action === "filter-kanban"){ setKanbanFilter(target.dataset.priority); return; }

  /* --- PM CRUD actions --- */
  // 각 data-* 속성은 카드 버튼에서 오거나, 시트의 data-target에서 옴 (공통 id 변수)
  if (action === "project-add")    { openProjectModal(null); return; }
  if (action === "project-edit")   {
    const pid = target.dataset.projectId || target.dataset.target;
    closeSheet();
    openProjectModal(indexes.projectById.get(pid)); return;
  }
  if (action === "project-delete") {
    const pid = target.dataset.projectId || target.dataset.target;
    closeModal(); closeSheet(); deleteProject(pid); return;
  }
  if (action === "issue-add")      { openIssueModal(null); return; }
  if (action === "issue-edit")     {
    const iid = target.dataset.issueId || target.dataset.target;
    closeSheet();
    openIssueModal(indexes.issueById.get(iid)); return;
  }
  if (action === "issue-delete")   {
    const iid = target.dataset.issueId || target.dataset.target;
    closeSheet(); deleteIssue(iid); return;
  }
  if (action === "issue-move")     { moveIssue(target.dataset.issueId, target.dataset.status); return; }
  if (action === "task-add")       { openTaskModal(null); return; }
  if (action === "task-edit")      {
    const tid = target.dataset.taskId || target.dataset.target;
    closeSheet();
    openTaskModal(dashboard.gantt.tasks.find((x) => x.id === tid)); return;
  }
  if (action === "task-delete")    {
    const tid = target.dataset.taskId || target.dataset.target;
    closeSheet(); deleteTask(tid); return;
  }
  if (action === "member-add")     { openMemberModal(null); return; }
  if (action === "member-edit")    {
    const mid = target.dataset.memberId || target.dataset.target;
    closeSheet();
    openMemberModal(indexes.teamById.get(mid)); return;
  }
  if (action === "member-delete")  {
    const mid = target.dataset.memberId || target.dataset.target;
    closeSheet(); deleteMember(mid); return;
  }

  /* --- DB CRUD actions --- */
  if (action === "instance-add")    { openInstanceModal(null); return; }
  if (action === "instance-edit")   {
    const iid = target.dataset.instanceId || target.dataset.target;
    closeSheet();
    openInstanceModal(indexes.instanceById.get(iid)); return;
  }
  if (action === "instance-delete") {
    const iid = target.dataset.instanceId || target.dataset.target;
    closeModal(); closeSheet(); deleteInstance(iid); return;
  }

  if (action === "table-add")    { openTableModal(null); return; }
  if (action === "table-edit")   {
    const tid = target.dataset.tableId || target.dataset.target;
    closeSheet();
    const ctx = findTableById(tid);
    openTableModal(ctx ? ctx.table : null); return;
  }
  if (action === "table-delete") {
    const tid = target.dataset.tableId || target.dataset.target;
    closeModal(); deleteTable(tid); return;
  }

  if (action === "column-add")    {
    const tid = target.dataset.tableId;
    openColumnModal(tid, null); return;
  }
  if (action === "column-edit")   {
    const tid = target.dataset.tableId;
    const ci  = parseInt(target.dataset.colIndex, 10);
    closeModal();
    openColumnModal(tid, ci); return;
  }
  if (action === "column-delete") {
    const tid = target.dataset.tableId;
    const ci  = parseInt(target.dataset.colIndex, 10);
    deleteColumn(tid, ci); return;
  }

  if (action === "query-add")    { openQueryModal(null); return; }
  if (action === "query-edit")   {
    const qid = target.dataset.queryId || target.dataset.target;
    closeSheet();
    openQueryModal(dashboard.queries.find((x) => x.id === qid)); return;
  }
  if (action === "query-delete") {
    const qid = target.dataset.queryId || target.dataset.target;
    closeModal(); deleteQuery(qid); return;
  }

  if (action === "migration-add")    { openMigrationModal(null); return; }
  if (action === "migration-edit")   {
    const mid = target.dataset.migId || target.dataset.target;
    closeSheet();
    openMigrationModal(dashboard.migrations.find((x) => x.id === mid)); return;
  }
  if (action === "migration-delete") {
    const mid = target.dataset.migId || target.dataset.target;
    closeModal(); deleteMigration(mid); return;
  }
}

/* ============================================================
 * Command Palette (Cmd/Ctrl+K) — unified search + commands
 * ============================================================ */

// Palette state (merged into module-level vars to avoid touching `state` object)
let _palOpen = false;
let _palIndex = 0;
let _palItems = [];
let _lastGTime = 0; // timestamp for g-chord detection

const PAL_MAX_HITS = 40;

/* View navigation commands */
const PAL_NAV_COMMANDS = [
  { view: "home",          icon: "⌘", cls: "pal-icon-misc",  label: "홈 대시보드" },
  { view: "cal",           icon: "◷", cls: "pal-icon-event", label: "일정" },
  { view: "todo",          icon: "☑", cls: "pal-icon-todo",  label: "할 일" },
  { view: "notes",         icon: "✎", cls: "pal-icon-note",  label: "메모" },
  { view: "habits",        icon: "◉", cls: "pal-icon-habit", label: "습관" },
  { view: "stats",         icon: "▤", cls: "pal-icon-misc",  label: "통계" },
  { view: "pm-portfolio",  icon: "▦", cls: "pal-icon-proj",  label: "포트폴리오" },
  { view: "pm-kanban",     icon: "▣", cls: "pal-icon-issue", label: "Kanban 보드" },
  { view: "pm-gantt",      icon: "↔", cls: "pal-icon-misc",  label: "간트 차트" },
  { view: "pm-team",       icon: "◈", cls: "pal-icon-misc",  label: "팀 · 리소스" },
  { view: "dbm-instances", icon: "✺", cls: "pal-icon-misc",  label: "인스턴스 상태" },
  { view: "dbm-schema",    icon: "◎", cls: "pal-icon-misc",  label: "스키마 탐색" },
  { view: "dbm-queries",   icon: "◉", cls: "pal-icon-misc",  label: "질의 성능" },
  { view: "dbm-backups",   icon: "⌘", cls: "pal-icon-misc",  label: "백업 · 마이그" },
  { view: "settings",      icon: "⚙", cls: "pal-icon-misc",  label: "설정" },
];

function _palEl() { return document.getElementById("palette"); }
function _palInput() { return document.getElementById("paletteInput"); }
function _palResultsEl() { return document.getElementById("paletteResults"); }

function openPalette() {
  if (_palOpen) return;
  _palOpen = true;
  const el = _palEl();
  if (!el) return;
  // Save focus before opening
  state.previousFocus = document.activeElement;
  el.classList.add("open");
  el.setAttribute("aria-hidden", "false");
  const input = _palInput();
  if (input) {
    input.value = "";
    input.setAttribute("aria-expanded", "true");
    input.focus();
  }
  renderPaletteResults("");
}

function closePalette() {
  if (!_palOpen) return;
  _palOpen = false;
  const el = _palEl();
  if (!el) return;
  el.classList.remove("open");
  el.setAttribute("aria-hidden", "true");
  const input = _palInput();
  if (input) {
    input.setAttribute("aria-expanded", "false");
    input.removeAttribute("aria-activedescendant");
  }
  // Restore focus
  if (state.previousFocus && typeof state.previousFocus.focus === "function") {
    state.previousFocus.focus();
    state.previousFocus = null;
  }
}

function _buildPaletteItems(query) {
  const q = (query || "").trim();
  const items = [];

  // ── 1. Navigation commands (always shown, filtered by query)
  const navItems = PAL_NAV_COMMANDS
    .filter((c) => !q || matches(c.label, q))
    .map((c) => ({
      icon: c.icon, iconCls: c.cls,
      label: `이동: ${c.label}`, sub: "화면 이동",
      group: "이동",
      run() { closePalette(); setView(c.view); },
    }));

  // ── 2. Create commands (shown when no query, or query matches)
  const createDefs = [
    { icon: "◷", cls: "pal-icon-event",  label: "새 일정",     sub: "일정 추가",      run() { closePalette(); openEventModal(null); } },
    { icon: "☑", cls: "pal-icon-todo",   label: "새 할 일",    sub: "할 일 추가",     run() { closePalette(); openTodoModal(null); } },
    { icon: "✎", cls: "pal-icon-note",   label: "새 메모",     sub: "메모 추가",      run() { closePalette(); openNoteModal(null); } },
    { icon: "◉", cls: "pal-icon-habit",  label: "새 습관",     sub: "습관 추가",      run() { closePalette(); openHabitModal(null); } },
    { icon: "▦", cls: "pal-icon-proj",   label: "새 프로젝트", sub: "프로젝트 추가",  run() { closePalette(); openProjectModal(null); } },
    { icon: "▣", cls: "pal-icon-issue",  label: "새 이슈",     sub: "이슈 추가",      run() { closePalette(); openIssueModal(null); } },
  ];
  const createItems = createDefs
    .filter((c) => !q || matches(c.label, q) || matches(c.sub, q))
    .map((c) => ({ ...c, iconCls: c.cls, group: "새로 만들기" }));

  // ── 3. Other commands
  const miscDefs = [
    { icon: "⬇", cls: "pal-icon-misc", label: "데이터 내보내기", sub: "JSON 파일로 저장", run() { closePalette(); exportData(); } },
    { icon: "◑", cls: "pal-icon-misc", label: "테마 전환",       sub: "다크/라이트 모드", run() { closePalette(); if (typeof toggleTheme === "function") toggleTheme(); } },
    { icon: "?", cls: "pal-icon-misc", label: "단축키 도움말",   sub: "키보드 단축키 목록 보기", run() { closePalette(); openShortcutHelp(); } },
  ];
  const miscItems = miscDefs
    .filter((c) => !q || matches(c.label, q) || matches(c.sub, q))
    .map((c) => ({ ...c, iconCls: c.cls, group: "기타" }));

  // ── 4. Search hits (only when query non-empty)
  // Fuse.js(vendor/fuse.min.js)가 있으면 오타 허용·관련도 랭킹 퍼지 검색을 쓰고,
  // 미로드 시 기존 부분일치(matches)로 폴백한다. 두 경로 모두 PAL_MAX_HITS로 제한.
  let hitItems = [];
  if (q) {
    // 모든 검색 가능 항목을 평탄 레코드로 모은다. 각 레코드는 그대로 팔레트
    // 아이템(icon/iconCls/label/sub/group/run)이며, label(주)·aux(보조) 텍스트로 검색된다.
    const records = [];
    (dashboard.events || []).forEach((ev) => records.push({
      label: ev.title || "", aux: ev.location || "",
      icon: "◷", iconCls: "pal-icon-event",
      sub: `일정 · ${formatKoreanShort(ev.date)}`, group: "검색 결과",
      run() { closePalette(); openEventModal(ev); },
    }));
    (dashboard.todos || []).forEach((t) => records.push({
      label: t.text || t.title || "(할 일)", aux: "",
      icon: "☑", iconCls: "pal-icon-todo",
      sub: `할 일${t.done ? " · 완료" : ""}`, group: "검색 결과",
      run() { closePalette(); openTodoModal(t); },
    }));
    (dashboard.notes || []).forEach((n) => records.push({
      label: n.title || "(제목 없음)", aux: n.body || "",
      icon: "✎", iconCls: "pal-icon-note",
      sub: "메모", group: "검색 결과",
      run() { closePalette(); openNoteModal(n); },
    }));
    (dashboard.habits || []).forEach((h) => records.push({
      label: h.name || "", aux: "",
      icon: "◉", iconCls: "pal-icon-habit",
      sub: "습관", group: "검색 결과",
      run() { closePalette(); setView("habits"); openHabitModal(h); },
    }));
    (dashboard.projects || []).forEach((p) => records.push({
      label: p.name || "", aux: p.owner || "",
      icon: "▦", iconCls: "pal-icon-proj",
      sub: `프로젝트 · ${p.owner || ""}`, group: "검색 결과",
      run() { closePalette(); setView("pm-portfolio"); openProjectModal(p); },
    }));
    (dashboard.issues || []).forEach((iss) => records.push({
      label: iss.title || "", aux: iss.id || "",
      icon: "▣", iconCls: "pal-icon-issue",
      sub: `이슈 · ${iss.id}`, group: "검색 결과",
      run() { closePalette(); setView("pm-kanban"); openIssueModal(iss); },
    }));

    if (typeof Fuse === "function") {
      const fuse = new Fuse(records, {
        keys: [{ name: "label", weight: 0.7 }, { name: "aux", weight: 0.3 }],
        threshold: 0.4,       // 오타 허용도 (0=정확, 1=아무거나)
        ignoreLocation: true, // 문자열 어디서든 매칭
        minMatchCharLength: 1,
        includeScore: true,   // 관련도순 정렬(기본 shouldSort)
      });
      hitItems = fuse.search(q, { limit: PAL_MAX_HITS }).map((r) => r.item);
    } else {
      // 폴백: 부분일치(원래 동작) — 카테고리 순서 유지 후 상한 적용
      hitItems = records
        .filter((r) => matches(r.label, q) || matches(r.aux, q))
        .slice(0, PAL_MAX_HITS);
    }
  }

  // Merge: if query, put search hits first, then commands; else nav, create, misc
  if (q && hitItems.length > 0) {
    items.push(...hitItems, ...navItems, ...createItems, ...miscItems);
  } else {
    items.push(...navItems, ...createItems, ...miscItems);
  }

  return items;
}

function renderPaletteResults(query) {
  const resultsEl = _palResultsEl();
  if (!resultsEl) return;
  const input = _palInput();
  _palItems = _buildPaletteItems(query);
  _palIndex = 0;

  if (_palItems.length === 0) {
    resultsEl.innerHTML = "";
    if (input) input.removeAttribute("aria-activedescendant");
    return;
  }

  let html_out = "";
  let currentGroup = null;
  _palItems.forEach((item, idx) => {
    if (item.group !== currentGroup) {
      currentGroup = item.group;
      html_out += `<div class="pal-group">${escapeHtml(currentGroup)}</div>`;
    }
    const active = idx === 0 ? " is-active" : "";
    html_out += `<button type="button" id="pal-option-${idx}" class="pal-item${active}" data-pal-index="${idx}" role="option" aria-selected="${idx === 0}">`;
    html_out += `<span class="pal-icon ${escapeHtml(item.iconCls || "pal-icon-misc")}">${escapeHtml(item.icon)}</span>`;
    html_out += `<span class="pal-text">`;
    html_out += `<span class="pal-label">${escapeHtml(item.label)}</span>`;
    if (item.sub) html_out += `<span class="pal-sub">${escapeHtml(item.sub)}</span>`;
    html_out += `</span></button>`;
  });
  resultsEl.innerHTML = html_out;
  if (input) input.setAttribute("aria-activedescendant", "pal-option-0");
}

function _palSetIndex(idx) {
  const items = _palItems;
  if (!items.length) return;
  // Clamp
  if (idx < 0) idx = 0;
  if (idx >= items.length) idx = items.length - 1;
  _palIndex = idx;

  const resultsEl = _palResultsEl();
  const input = _palInput();
  if (!resultsEl) return;
  resultsEl.querySelectorAll(".pal-item").forEach((btn) => {
    const i = parseInt(btn.dataset.palIndex, 10);
    const active = i === _palIndex;
    btn.classList.toggle("is-active", active);
    btn.setAttribute("aria-selected", String(active));
    if (active) {
      if (input && btn.id) input.setAttribute("aria-activedescendant", btn.id);
      btn.scrollIntoView({ block: "nearest" });
    }
  });
}

function _palRunIndex(idx) {
  const item = _palItems[idx];
  if (item && typeof item.run === "function") item.run();
}

function setupPalette() {
  const input = _palInput();
  if (input) {
    input.addEventListener("input", () => {
      renderPaletteResults(input.value);
    });
    input.addEventListener("keydown", (event) => {
      if (event.key === "ArrowDown") {
        event.preventDefault();
        _palSetIndex(_palIndex + 1);
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        _palSetIndex(_palIndex - 1);
      } else if (event.key === "Enter") {
        event.preventDefault();
        _palRunIndex(_palIndex);
      } else if (event.key === "Escape") {
        event.preventDefault();
        closePalette();
      }
    });
  }

  // Result click delegation
  const resultsEl = _palResultsEl();
  if (resultsEl) {
    resultsEl.addEventListener("click", (event) => {
      const btn = event.target.closest("[data-pal-index]");
      if (!btn) return;
      const idx = parseInt(btn.dataset.palIndex, 10);
      _palRunIndex(idx);
    });
    // Hover → update active index
    resultsEl.addEventListener("mousemove", (event) => {
      const btn = event.target.closest("[data-pal-index]");
      if (!btn) return;
      const idx = parseInt(btn.dataset.palIndex, 10);
      if (idx !== _palIndex) _palSetIndex(idx);
    });
  }
}

/* ============================================================
 * Shortcut help modal
 * ============================================================ */

function openShortcutHelp() {
  const isMac = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);
  const mod = isMac ? "⌘" : "Ctrl";
  const rows = [
    [`<kbd class="kbd">${mod}+K</kbd>`, "명령 팔레트 / 통합 검색 열기"],
    [`<kbd class="kbd">/</kbd>`, "현재 뷰 내 검색창 포커스"],
    [`<kbd class="kbd">n</kbd>`, "현재 뷰에 새 항목 추가"],
    [`<kbd class="kbd">?</kbd>`, "이 도움말 열기"],
    [`<kbd class="kbd">Esc</kbd>`, "팔레트 · 모달 · 시트 닫기"],
    [`<kbd class="kbd">g</kbd> → <kbd class="kbd">h</kbd>`, "홈 대시보드로 이동"],
    [`<kbd class="kbd">g</kbd> → <kbd class="kbd">c</kbd>`, "일정으로 이동"],
    [`<kbd class="kbd">g</kbd> → <kbd class="kbd">t</kbd>`, "할 일로 이동"],
    [`<kbd class="kbd">g</kbd> → <kbd class="kbd">m</kbd>`, "메모로 이동"],
    [`<kbd class="kbd">g</kbd> → <kbd class="kbd">i</kbd>`, "습관으로 이동"],
    [`<kbd class="kbd">g</kbd> → <kbd class="kbd">s</kbd>`, "통계로 이동"],
    [`<kbd class="kbd">g</kbd> → <kbd class="kbd">p</kbd>`, "포트폴리오로 이동"],
    [`<kbd class="kbd">g</kbd> → <kbd class="kbd">k</kbd>`, "Kanban 보드로 이동"],
    ["할 일 입력 후 <kbd class=\"kbd\">Enter</kbd>", "할 일 빠른 추가"],
  ];
  const tableHTML = `<table class="shortcut-table">
    <thead><tr><th>단축키</th><th>기능</th></tr></thead>
    <tbody>${rows.map(([key, desc]) => `<tr><td>${key}</td><td>${escapeHtml(desc)}</td></tr>`).join("")}</tbody>
  </table>`;
  openModal("키보드 단축키", tableHTML, null);
}

/* ============================================================
 * Setup
 * ============================================================ */

const SEARCH_INERT_VIEWS = new Set(["home", "settings"]);
const onSearchInput = debounce(() => {
  const inert = SEARCH_INERT_VIEWS.has(dashboard.currentView);
  if (!inert) renderCurrentView();
  if (refs.searchCount) {
    // Only claim "filtering" on views that actually filter on the query.
    refs.searchCount.textContent = (!inert && state.query) ? "현재 뷰에서 필터링" : "";
  }
}, 140);

function setupGlobalSearch() {
  if (!refs.query) return;
  refs.query.addEventListener("input", (event) => {
    state.query = event.target.value;
    onSearchInput();
  });
}

function setupInteractions() {
  document.body.addEventListener("click", (event) => {
    const action = event.target.closest("[data-action]");
    // Forms with data-action are handled on `submit` (Enter / submit button),
    // not on click, so the click and the native submit don't fire twice.
    if (action && action.tagName !== "FORM") {
      event.preventDefault();
      handleActions({ target: action });
      return;
    }
    if (refs.projectPicker && !refs.projectPicker.hasAttribute("hidden")) {
      if (!refs.projectPicker.contains(event.target) && !(refs.projectSelect && refs.projectSelect.contains(event.target))) {
        setProjectPickerOpen(false);
      }
    }
  });
  document.addEventListener("keydown", (event) => {
    // ── Cmd/Ctrl+K → open command palette (replaces old focus-search)
    if ((event.metaKey || event.ctrlKey) && event.key && event.key.toLowerCase() === "k") {
      event.preventDefault();
      if (_palOpen) closePalette();
      else openPalette();
      return;
    }

    // ── Escape: palette → modal → sheet → project picker (in priority order)
    if (event.key === "Escape") {
      if (_palOpen) { closePalette(); return; }
      if (refs.projectPicker && !refs.projectPicker.hasAttribute("hidden")) {
        event.preventDefault();
        setProjectPickerOpen(false);
        restoreProjectPickerFocus();
        return;
      }
      if (refs.modal.root && refs.modal.root.classList.contains("open")) { closeModal(); }
      else if (refs.sheets.root.classList.contains("open")) { closeSheet(); }
      return;
    }

    if (event.key === "Tab") {
      // Also trap tab inside palette panel
      if (_palOpen) {
        const palPanel = document.querySelector(".palette-panel");
        if (palPanel) { trapTab(event, palPanel); return; }
      }
      const dialog = getOpenDialogRoot();
      if (dialog) trapTab(event, dialog);
    }

    if (event.key === "Enter" || event.key === " ") {
      // Focusable-but-not-native-button elements (Gantt SVG bars/milestones, and
      // calendar day cells) need Enter/Space activated here. Real <button>s skip —
      // the click handler already fires for those on Enter/Space.
      const el = event.target.closest && event.target.closest("[data-action='open-task'], [data-action='cal-open-day']");
      if (el && el.tagName.toLowerCase() !== "button") {
        event.preventDefault();
        const act = el.getAttribute("data-action");
        if (act === "open-task") openTaskSheet(el.dataset.taskId);
        else if (act === "cal-open-day") calSelectDay(el.dataset.date);
      }
    }

    // ── Single-key shortcuts: only fire when not typing in a form field or
    //    palette/modal/sheet open. The palette has its own keydown listener.
    const ae = document.activeElement;
    const inField = ae && (ae.tagName === "INPUT" || ae.tagName === "TEXTAREA" || ae.tagName === "SELECT" || ae.isContentEditable);
    const dialogOpen = _palOpen || (refs.modal.root && refs.modal.root.classList.contains("open")) || (refs.sheets.root && refs.sheets.root.classList.contains("open"));
    if (inField || dialogOpen) return;

    // / → focus in-view search
    if (event.key === "/" && !event.metaKey && !event.ctrlKey && !event.altKey) {
      event.preventDefault();
      if (refs.query) { refs.query.focus(); refs.query.select(); }
      return;
    }

    // ? (Shift+/) → shortcut help
    if (event.key === "?") {
      event.preventDefault();
      openShortcutHelp();
      return;
    }

    // n → new item (context-aware)
    if (event.key === "n" && !event.metaKey && !event.ctrlKey && !event.altKey) {
      event.preventDefault();
      const cv = dashboard.currentView;
      if (cv === "cal")          { openEventModal(null); }
      else if (cv === "todo")    { openTodoModal(null); }
      else if (cv === "notes")   { openNoteModal(null); }
      else if (cv === "habits")  { openHabitModal(null); }
      else if (cv === "pm-kanban")   { openIssueModal(null); }
      else if (cv === "pm-portfolio") { openProjectModal(null); }
      else if (cv === "pm-gantt")    { openTaskModal(null); }
      else if (cv === "pm-team")     { openMemberModal(null); }
      else { openEventModal(null); }
      return;
    }

    // g-chord: g then a letter within 1.2 s → navigate
    if (event.key === "g" && !event.metaKey && !event.ctrlKey && !event.altKey) {
      event.preventDefault();
      _lastGTime = Date.now();
      return;
    }
    if (_lastGTime && (Date.now() - _lastGTime) < 1200 && !event.metaKey && !event.ctrlKey && !event.altKey) {
      const G_MAP = {
        h: "home", c: "cal", t: "todo", m: "notes",
        i: "habits", s: "stats", p: "pm-portfolio", k: "pm-kanban",
      };
      const dest = G_MAP[event.key];
      if (dest) {
        event.preventDefault();
        _lastGTime = 0;
        setView(dest);
        return;
      }
      _lastGTime = 0;
    }
  });
  // Form submission: quick-add / settings forms dispatch via data-action;
  // modal forms (no data-action) trigger the modal's confirm on Enter.
  // preventDefault on every submit so a form never navigates the page.
  document.body.addEventListener("submit", (event) => {
    event.preventDefault();
    const actionForm = event.target.closest("form[data-action]");
    if (actionForm) { handleActions({ target: actionForm }); return; }
    if (refs.modal.root && refs.modal.root.classList.contains("open") && typeof state.modalOnConfirm === "function") {
      if (state.modalOnConfirm() !== false) closeModal();
    }
  });
  window.addEventListener("hashchange", () => {
    const name = location.hash.slice(1) || "home";
    if (name !== dashboard.currentView) setView(name);
  });
}

function updateFooter() {
  if (!refs.footerNow) return;
  const d = new Date();
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  const hh = String(d.getHours()).padStart(2, "0");
  const mi = String(d.getMinutes()).padStart(2, "0");
  refs.footerNow.textContent = `현재 시각: ${yyyy}-${mm}-${dd} ${hh}:${mi}`;
}

let footerTimerId = null;
function scheduleFooterTick() {
  if (footerTimerId !== null) return;
  const now = new Date();
  const msToNextMinute = (60 - now.getSeconds()) * 1000 - now.getMilliseconds();
  footerTimerId = setTimeout(function tick() {
    updateFooter();
    footerTimerId = setTimeout(tick, 60 * 1000);
  }, msToNextMinute);
}
function pauseFooterTick() {
  if (footerTimerId !== null) { clearTimeout(footerTimerId); footerTimerId = null; }
}

/* ============================================================
 * GitHub snapshot sync (data/repos.json → dashboard.projects)
 * ============================================================ */

async function loadGithubProjects() {
  const repoSnapshot = await fetchProjectSnapshot("./data/repos.json");
  const adoptionSnapshot = await fetchProjectSnapshot("./data/adoption-candidates.json");
  const snapshot = mergeProjectSnapshots(repoSnapshot, adoptionSnapshot);
  if (!snapshot) {
    console.info("[workspace] project snapshots not loaded (using mock data)");
    return false;
  }
  if (dashboard.imports && dashboard.imports.autoProjectSeedDisabled === true) {
    console.info("[workspace] github snapshot skipped — project auto seed disabled after reset");
    return false;
  }

  if (pmWasPersisted) {
    const changed = mergeImportedProjects(adoptionSnapshot);
    if (!changed) console.info("[workspace] github snapshot skipped — user has persisted project data");
    return changed;
  }

  applyGithubSnapshot(snapshot);
  return true;
}

async function fetchProjectSnapshot(path) {
  try {
    const res = await fetch(path, { cache: "no-store" });
    if (!res.ok) return null;
    const snapshot = await res.json();
    if (!Array.isArray(snapshot.projects) || snapshot.projects.length === 0) return null;
    return snapshot;
  } catch (err) {
    console.info(`[workspace] project snapshot not loaded: ${path}`, err.message);
    return null;
  }
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
  registry[key] = [...applied].sort();
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
  registry[importId] = [...applied].sort();
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

  rebuildIndexes();
}

function refreshAfterSnapshot() {
  const cur = currentProject();
  if (refs.projectSelectLabel && cur) refs.projectSelectLabel.textContent = cur.name;
  const navProjects = document.getElementById("navCountProjects");
  if (navProjects) navProjects.textContent = String(dashboard.projects.length);
  const navIssues = document.getElementById("navCountIssues");
  if (navIssues) navIssues.textContent = String(dashboard.issues.length);
  if (refs.projectPicker && !refs.projectPicker.hasAttribute("hidden")) renderProjectOptions();
  renderCurrentView();
}

/* ---------- Browser notification helper (best-effort, opt-in only) ---------- */

function tryBrowserNotification(title, body) {
  try {
    if (!("Notification" in window)) return;
    if (Notification.permission !== "granted") return;
    new Notification(title, { body, icon: "" });
  } catch (_) { /* intentionally silent */ }
}

/* Poll every ~60 s for events starting within 10 minutes (while page is open). */
let _browserNotifLastFired = new Set();
function startEventReminders() {
  try {
    setInterval(() => {
      try {
        if (!("Notification" in window) || Notification.permission !== "granted") return;
        const now = new Date();
        const todayStr = todayISO();
        eventsOn(todayStr).forEach((e) => {
          if (e.allDay || !e.start) return;
          const [hh, mm] = e.start.split(":").map(Number);
          const evTime = new Date(now.getFullYear(), now.getMonth(), now.getDate(), hh, mm, 0);
          const diffMin = (evTime - now) / 60000;
          if (diffMin >= 0 && diffMin <= 10) {
            const key = `${e._masterId || e.id}-${todayStr}`;
            if (!_browserNotifLastFired.has(key)) {
              _browserNotifLastFired.add(key);
              tryBrowserNotification(`일정 알림: ${e.title}`, `${e.start} 시작 (약 ${Math.round(diffMin)}분 후)`);
            }
          }
        });
      } catch (_) { /* silent */ }
    }, 60000);
  } catch (_) { /* silent */ }
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
  if (!dashboard.ui || typeof dashboard.ui !== "object") dashboard.ui = { theme: "dark" };
  dashboard.ui.theme = theme === "light" ? "light" : "dark";
  applyTheme();
  persist();
  if (dashboard.currentView === "settings") renderSettings();
}

function toggleTheme() {
  const next = (dashboard.ui && dashboard.ui.theme === "light") ? "dark" : "light";
  setTheme(next);
  showToast(next === "light" ? "라이트 테마로 전환했습니다" : "다크 테마로 전환했습니다", "info");
}

function setup() {
  assertRefs();
  // Load the user's saved 일정 / 할 일 / 메모 before the first render (seeds on
  // first run). Everything the user manages day to day lives in localStorage.
  loadPersisted();
  applyTheme();
  const nameEl = document.querySelector(".user strong");
  if (nameEl && dashboard.settings && dashboard.settings.displayName) {
    nameEl.textContent = dashboard.settings.displayName;
  }
  updateNavCounts();
  // Boot to URL hash if present
  const initial = (location.hash.slice(1) || "home");
  setView(VIEWS.includes(initial) ? initial : "home");
  setupGlobalSearch();
  setupPalette();
  setupInteractions();
  updateFooter();
  // Set project label to the current one
  const cur = currentProject();
  if (refs.projectSelectLabel && cur) refs.projectSelectLabel.textContent = cur.name;
  scheduleFooterTick();
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) pauseFooterTick();
    else { updateFooter(); scheduleFooterTick(); }
  });
  refreshStorageHealth();
  loadGithubProjects().then((loaded) => { if (loaded) refreshAfterSnapshot(); });

  // Boot toast: warn about overdue todos once on load.
  const overdueCount = (Array.isArray(dashboard.todos) ? dashboard.todos : [])
    .filter((t) => !t.done && t.due && t.due < todayISO()).length;
  if (overdueCount > 0) {
    showToast(`기한 지난 할 일 ${overdueCount}건이 있습니다`, "warn");
  }

  // Start browser-notification reminder poll (guarded, does nothing unless
  // permission was previously granted — never auto-prompts).
  startEventReminders();
}

setup();
