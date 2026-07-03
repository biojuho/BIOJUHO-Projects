/* ================================================================
 * JooPark Workspace — operational dashboard insights engine.
 * Static non-module runtime loaded before app.js.
 * ================================================================ */

(function initJooParkDashboardInsightsEngine(global) {
  "use strict";

  const VERSION = "joopark-dashboard-insights-engine/v1";
  const EXTERNAL_RESEARCH_SOURCES = Object.freeze([
    {
      id: "webdev-pwa-offline-data",
      title: "web.dev PWA offline data",
      url: "https://web.dev/learn/pwa/offline-data",
      checkedAt: "2026-06-09",
      confidence: 0.86,
      note: "WebStorage is synchronous; Cache Storage fits app-shell resources; IndexedDB is better for structured data beyond this localStorage-only boundary.",
    },
    {
      id: "mdn-pwa-caching",
      title: "MDN PWA caching",
      url: "https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Caching",
      checkedAt: "2026-06-09",
      confidence: 0.84,
      note: "PWA caching improves offline operation and responsiveness, with freshness tradeoffs.",
    },
    {
      id: "owasp-xss-prevention",
      title: "OWASP XSS Prevention Cheat Sheet",
      url: "https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html",
      checkedAt: "2026-06-09",
      confidence: 0.9,
      note: "Untrusted strings need context-aware output encoding; reviewed HTML needs sanitization.",
    },
    {
      id: "w3c-wcag-22",
      title: "W3C WCAG 2.2",
      url: "https://www.w3.org/TR/WCAG22/",
      checkedAt: "2026-06-09",
      confidence: 0.88,
      note: "Focus visibility, 24px target minimum, predictable navigation, and consistent help are relevant to dense dashboard controls.",
    },
  ]);

  function listOf(value) {
    return Array.isArray(value) ? value : [];
  }

  function isObject(value) {
    return Boolean(value && typeof value === "object" && !Array.isArray(value));
  }

  function parseDate(value) {
    const date = new Date(`${value}T00:00:00`);
    return Number.isNaN(date.getTime()) ? null : date;
  }

  function daysUntil(date, today) {
    const target = parseDate(date);
    const base = parseDate(today);
    if (!target || !base) return null;
    return Math.round((target.getTime() - base.getTime()) / 86400000);
  }

  function riskLabel(level) {
    if (level >= 4) return "high";
    if (level >= 3) return "medium";
    return "low";
  }

  function card(key, title, status, evidence, lastUpdated, riskLevel, nextAction, sourceRefs) {
    return {
      key,
      title,
      status,
      evidence,
      lastUpdated: lastUpdated || new Date().toISOString(),
      riskLevel,
      riskLabel: riskLabel(riskLevel),
      nextAction,
      sourceRefs: listOf(sourceRefs),
    };
  }

  function latestGeneratedAt(source) {
    const data = source && source.data ? source.data : source;
    return data && (data.generatedAt || data.finishedAt || data.createdAt) || "";
  }

  function habitStreak(habit, today) {
    const log = isObject(habit && habit.log) ? habit.log : {};
    let streak = 0;
    const cursor = parseDate(today);
    if (!cursor) return 0;
    while (streak < 365) {
      const y = cursor.getFullYear();
      const m = String(cursor.getMonth() + 1).padStart(2, "0");
      const d = String(cursor.getDate()).padStart(2, "0");
      if (!log[`${y}-${m}-${d}`]) break;
      streak += 1;
      cursor.setDate(cursor.getDate() - 1);
    }
    return streak;
  }

  function buildCards(input = {}) {
    const dashboard = input.dashboard || {};
    const state = input.state || {};
    const today = input.today || new Date().toISOString().slice(0, 10);
    const publishItems = listOf(input.publishItems);
    const events = listOf(dashboard.events);
    const todos = listOf(dashboard.todos);
    const projects = listOf(dashboard.projects);
    const issues = listOf(dashboard.issues);
    const tasks = listOf(dashboard.gantt && dashboard.gantt.tasks);
    const habits = listOf(dashboard.habits).filter((habit) => !habit.archived);
    const todayEvents = events.filter((event) => event.date === today);
    const overdueTodos = todos.filter((todo) => !todo.done && todo.due && todo.due < today);
    const progressingProjects = projects.filter((project) => project.status !== "on-track" || Number(project.progress || 0) < 80);
    const blockedKanban = issues.filter((issue) => issue.status !== "done" && (issue.priority === "crit" || (issue.due && issue.due < today)));
    const delayedTasks = tasks.filter((task) => !task.milestone && task.end && task.end < today);
    const streaks = habits.map((habit) => habitStreak(habit, today));
    const bestStreak = streaks.length ? Math.max(...streaks) : 0;
    const storage = state.storageHealth || {};
    const storageRisk = storage.lastError ? 5 : Number(storage.localBytes || 0) > 1500000 ? 4 : 2;
    const releaseBlockers = publishItems.filter((item) => item.state === "blocked");
    const productLoop = input.productLoop || {};
    const productLoopGeneratedAt = latestGeneratedAt(productLoop);

    return [
      card("today_schedule", "오늘 일정", todayEvents.length ? `${todayEvents.length}건` : "비어 있음", todayEvents.slice(0, 3).map((event) => event.title).join(" · ") || "오늘 일정 없음", today, todayEvents.length >= 4 ? 3 : 1, { label: todayEvents.length ? "오늘 아젠다 확인" : "중요 일정 추가", view: "cal", status: "ready" }, ["events"]),
      card("overdue_todos", "지연 할 일", overdueTodos.length ? `${overdueTodos.length}건 지연` : "정상", overdueTodos.slice(0, 4).map((todo) => todo.title).join(" · ") || "지연된 할 일 없음", today, overdueTodos.length ? 5 : 1, { label: overdueTodos.length ? "가장 오래된 할 일 처리" : "오늘 할 일 유지", view: "todo", status: overdueTodos.length ? "action_required" : "ready" }, ["todos"]),
      card("active_projects", "진행 프로젝트", `${progressingProjects.length}/${projects.length} 주의`, progressingProjects.slice(0, 3).map((project) => `${project.name} ${project.progress}%`).join(" · ") || "모든 프로젝트 정상", today, progressingProjects.some((project) => project.health === "red") ? 5 : progressingProjects.length ? 3 : 1, { label: "위험 프로젝트 재정렬", view: "pm-portfolio", status: progressingProjects.length ? "review" : "ready" }, ["projects"]),
      card("blocked_kanban", "막힌 Kanban", blockedKanban.length ? `${blockedKanban.length}개 카드` : "없음", blockedKanban.slice(0, 4).map((issue) => `${issue.id} ${issue.title}`).join(" · ") || "crit/overdue 카드 없음", today, blockedKanban.length ? 5 : 1, { label: blockedKanban.length ? "crit/overdue 카드 먼저 이동" : "보드 상태 유지", view: "pm-kanban", status: blockedKanban.length ? "action_required" : "ready" }, ["issues"]),
      card("delayed_gantt", "Gantt 지연 작업", delayedTasks.length ? `${delayedTasks.length}개 지연` : "정상", delayedTasks.slice(0, 4).map((task) => `${task.name} ${daysUntil(task.end, today)}일`).join(" · ") || "종료일 지난 작업 없음", today, delayedTasks.length ? 4 : 1, { label: delayedTasks.length ? "지연 작업 owner 확인" : "다음 milestone 확인", view: "pm-gantt", status: delayedTasks.length ? "review" : "ready" }, ["gantt.tasks"]),
      card("habit_streaks", "습관 streak", habits.length ? `최고 ${bestStreak}일` : "습관 없음", habits.slice(0, 4).map((habit, index) => `${habit.name || habit.title}: ${streaks[index] || 0}일`).join(" · ") || "습관 데이터를 추가하세요", today, habits.length && bestStreak === 0 ? 3 : 1, { label: habits.length ? "오늘 습관 체크" : "첫 습관 추가", view: "habits", status: habits.length ? "ready" : "proposed" }, ["habits"]),
      card("storage_state", "저장소 상태", storage.lastError ? "저장 실패" : "정상", `${Number(storage.localBytes || 0)} bytes · persisted=${storage.persisted === true ? "true" : "false"}`, storage.checkedAt || today, storageRisk, { label: storage.lastError ? "긴급 백업 생성" : "저장소 health 갱신", view: "settings", status: storage.lastError ? "action_required" : "ready" }, ["storageHealth", "workspace-storage.js"]),
      card("release_readiness", "Release readiness", releaseBlockers.length ? `${releaseBlockers.length} blockers` : "ready", publishItems.slice(0, 4).map((item) => `${item.key || item.label}: ${item.state}`).join(" · ") || "release evidence 로드 대기", latestGeneratedAt(state.releaseReadinessSummary) || latestGeneratedAt(state.verifyWorkspaceSummary) || today, releaseBlockers.length ? 5 : 2, { label: releaseBlockers.length ? "System Status blocker 확인" : "release receipt 공유 준비", view: "system", status: releaseBlockers.length ? "action_required" : "ready" }, ["publishReadinessItems", "autoresearch-results/release-readiness-summary.json"]),
      card("product_loop", "Product loop", productLoop.status || "checking", productLoop.latestExperiment || productLoop.latestDirectionLoop || "loop evidence 로드 대기", productLoopGeneratedAt || today, productLoop.status === "ready-for-external-claim" ? 2 : 3, { label: "다음 product loop 후보 확인", view: "system", status: "review" }, ["autoresearch-results/joopark-product-loop.json"]),
    ];
  }

  function improvementCandidates(input = {}) {
    const cards = listOf(input.cards);
    const base = cards
      .filter((item) => item.riskLevel >= 3 || item.status !== "ready")
      .map((item) => ({
        id: `candidate-${item.key}`,
        createdAt: input.createdAt || new Date().toISOString(),
        sourceRefs: item.sourceRefs,
        summary: `${item.title}: ${item.evidence}`,
        scoreBreakdown: {
          userValue: item.key === "overdue_todos" || item.key === "blocked_kanban" ? 5 : 4,
          urgency: item.riskLevel,
          difficulty: item.key === "release_readiness" ? 3 : 2,
          regressionRisk: item.key === "release_readiness" ? 4 : 2,
          performance: item.key === "storage_state" ? 5 : 3,
          accessibility: item.key === "blocked_kanban" ? 4 : 3,
          security: item.key === "storage_state" || item.key === "release_readiness" ? 4 : 3,
          maintainability: 4,
          releaseReadiness: item.key === "release_readiness" ? 5 : 3,
          localStorageStability: item.key === "storage_state" ? 5 : 3,
          mobileUX: 3,
          evidenceTraceability: 5,
        },
        confidence: item.riskLevel >= 4 ? 0.82 : 0.7,
        verificationStatus: "candidate_scored",
        riskFlags: item.riskLevel >= 4 ? ["high_risk", item.key] : [item.key],
        nextAction: item.nextAction,
      }));
    if (base.length) return base;
    return [{
      id: "candidate-dashboard-retention-review",
      createdAt: input.createdAt || new Date().toISOString(),
      sourceRefs: ["dashboardStorage", "localStorage"],
      summary: "대시보드 evidence retention과 export/import guard를 주기적으로 검증",
      scoreBreakdown: { userValue: 4, urgency: 3, difficulty: 2, regressionRisk: 2, performance: 4, accessibility: 3, security: 4, maintainability: 4, releaseReadiness: 4, localStorageStability: 5, mobileUX: 3, evidenceTraceability: 5 },
      confidence: 0.72,
      verificationStatus: "candidate_scored",
      riskFlags: ["retention_policy"],
      nextAction: { label: "dashboard intelligence verifier 실행", command: "npm run verify:dashboard", view: "system", status: "ready" },
    }];
  }

  function dashboardInsightsModel(input = {}) {
    const cards = buildCards(input);
    const candidates = improvementCandidates({
      cards,
      createdAt: input.createdAt || new Date().toISOString(),
    });
    return {
      version: VERSION,
      generatedAt: input.createdAt || new Date().toISOString(),
      cards,
      candidates,
      externalResearchSources: EXTERNAL_RESEARCH_SOURCES.slice(),
      sourceSummary: {
        internal: ["events", "todos", "notes", "habits", "projects", "issues", "gantt", "team", "db catalog", "llm wiki", "settings/system", "release/product evidence"],
        externalCheckedAt: "2026-06-09",
        needs_external_validation: false,
      },
    };
  }

  function createDashboardInsightsEngine() {
    return Object.freeze({
      version: VERSION,
      externalResearchSources: EXTERNAL_RESEARCH_SOURCES.slice(),
      buildCards,
      improvementCandidates,
      dashboardInsightsModel,
    });
  }

  global.JooParkDashboardInsightsEngine = Object.freeze({
    version: VERSION,
    create: createDashboardInsightsEngine,
  });
})(typeof window !== "undefined" ? window : globalThis);
