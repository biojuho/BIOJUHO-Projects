(function (root) {
  "use strict";

  const VERSION = "joopark-portfolio-view/v1";

  function createPortfolioView(deps) {
    const options = deps || {};
    const html = options.html;
    const raw = options.raw;
    const matches = typeof options.matches === "function" ? options.matches : function () { return true; };
    const kpiCard = typeof options.kpiCard === "function" ? options.kpiCard : function () { return ""; };
    const searchEmptyState = typeof options.searchEmptyState === "function" ? options.searchEmptyState : function () { return ""; };
    const projectSearchText = typeof options.projectSearchText === "function" ? options.projectSearchText : function (project) { return project && project.name ? project.name : ""; };
    const sortPortfolioProjects = typeof options.sortPortfolioProjects === "function" ? options.sortPortfolioProjects : function (projects) { return Array.isArray(projects) ? projects : []; };
    const portfolioMatchesFilter = typeof options.portfolioMatchesFilter === "function" ? options.portfolioMatchesFilter : function () { return true; };
    const portfolioMatchesActionFilter = typeof options.portfolioMatchesActionFilter === "function" ? options.portfolioMatchesActionFilter : function () { return true; };
    const portfolioMatchesBenchmarkFilter = typeof options.portfolioMatchesBenchmarkFilter === "function" ? options.portfolioMatchesBenchmarkFilter : function () { return true; };
    const projectBenchmarkFocus = typeof options.projectBenchmarkFocus === "function" ? options.projectBenchmarkFocus : function () { return null; };
    const projectCandidateAction = typeof options.projectCandidateAction === "function" ? options.projectCandidateAction : function () { return null; };
    const candidateActionQueueSummary = typeof options.candidateActionQueueSummary === "function" ? options.candidateActionQueueSummary : function () { return ""; };
    const candidateBenchmarkQueueSummary = typeof options.candidateBenchmarkQueueSummary === "function" ? options.candidateBenchmarkQueueSummary : function () { return ""; };
    const candidateBenchmarkRubric = typeof options.candidateBenchmarkRubric === "function" ? options.candidateBenchmarkRubric : function () { return ""; };
    const candidateWorkspaceRubric = typeof options.candidateWorkspaceRubric === "function" ? options.candidateWorkspaceRubric : function () { return ""; };
    const candidateKnowledgeBaseRubric = typeof options.candidateKnowledgeBaseRubric === "function" ? options.candidateKnowledgeBaseRubric : function () { return ""; };
    const candidateBenchmarkReviewQueue = typeof options.candidateBenchmarkReviewQueue === "function" ? options.candidateBenchmarkReviewQueue : function () { return ""; };
    const projectAdoptionMeta = typeof options.projectAdoptionMeta === "function" ? options.projectAdoptionMeta : function () { return ""; };
    const projectPromptHandoffButton = typeof options.projectPromptHandoffButton === "function" ? options.projectPromptHandoffButton : function () { return ""; };
    const spark = typeof options.spark === "function" ? options.spark : function () { return ""; };
    const portfolioFilters = Array.isArray(options.portfolioFilters) ? options.portfolioFilters : [];
    const actionFilters = Array.isArray(options.actionFilters) ? options.actionFilters : [];
    const benchmarkFilters = Array.isArray(options.benchmarkFilters) ? options.benchmarkFilters : [];
    const healthColor = options.healthColor || {};
    const statusLabel = options.statusLabel || {};

    if (typeof html !== "function" || typeof raw !== "function") {
      throw new Error("portfolio view requires html and raw helpers");
    }

    function projectMembers(project) {
      return Array.isArray(project.members) ? project.members : [];
    }

    function progressValue(project) {
      const progress = Number(project.progress);
      if (!Number.isFinite(progress)) return 0;
      return Math.max(0, Math.min(100, Math.round(progress)));
    }

    function numericValue(value) {
      const number = Number(value);
      return Number.isFinite(number) ? number : 0;
    }

    function projectListItemLabel(project) {
      const name = project.name || "프로젝트";
      const owner = project.owner || "담당자 없음";
      const progress = progressValue(project);
      const status = statusLabel[project.status] || project.status || "상태 없음";
      return `${name} 포트폴리오 항목, 담당 ${owner}, 진행률 ${progress}%, ${status}`;
    }

    function portfolioStats(projects) {
      const list = Array.isArray(projects) ? projects : [];
      return {
        total: list.length,
        avg: list.length ? Math.round(list.reduce((sum, project) => sum + progressValue(project), 0) / list.length) : 0,
        delayed: list.filter((project) => project.status === "delayed").length,
        risky: list.filter((project) => project.health !== "green").length,
      };
    }

    function portfolioViewModel(input) {
      const data = input || {};
      const projects = Array.isArray(data.projects) ? data.projects : [];
      const query = (data.query || "").trim();
      const portfolioFilter = data.portfolioFilter || "all";
      const portfolioActionFilter = data.portfolioActionFilter || "all";
      const portfolioBenchmarkFilter = data.portfolioBenchmarkFilter || "all";
      const candidateCount = projects.filter((project) => project.sourceKind === "adoption-candidate").length;
      const ownedCount = projects.length - candidateCount;
      const benchmarkFocusCount = projects.filter((project) => project.sourceKind === "adoption-candidate" && projectBenchmarkFocus(project)).length;
      const actionCounts = projects
        .filter((project) => project.sourceKind === "adoption-candidate")
        .reduce((acc, project) => {
          const key = projectCandidateAction(project)?.key || "feature";
          acc[key] = (acc[key] || 0) + 1;
          return acc;
        }, {});
      const list = sortPortfolioProjects(projects
        .filter((project) => portfolioMatchesFilter(project, portfolioFilter))
        .filter((project) => portfolioMatchesActionFilter(project, portfolioActionFilter))
        .filter((project) => portfolioMatchesBenchmarkFilter(project, portfolioBenchmarkFilter))
        .filter((project) => matches(projectSearchText(project), query)));
      const stats = portfolioStats(projects);
      const kpis = [
        { title: "프로젝트", value: String(stats.total), unit: "개", color: "#2387ff", badge: "▦", delta: "" },
        { title: "평균 진행률", value: String(stats.avg), unit: "%", color: "#17d983", badge: "✺", delta: "▲ 4%p" },
        { title: "지연", value: String(stats.delayed), unit: "건", color: "#ff4d5e", badge: "△", delta: stats.delayed ? "조치 필요" : "없음", trendDown: stats.delayed > 0 },
        { title: "위험 프로젝트", value: String(stats.risky), unit: "건", color: "#f7a928", badge: "⬡", delta: "Amber 이상" },
      ];

      return {
        projects,
        query,
        list,
        portfolioFilter,
        portfolioActionFilter,
        portfolioBenchmarkFilter,
        candidateCount,
        ownedCount,
        benchmarkFocusCount,
        actionCounts,
        kpis,
      };
    }

    function filterChips(model) {
      return portfolioFilters.map((filter) => {
        const count = filter.key === "owned" ? model.ownedCount : filter.key === "candidates" ? model.candidateCount : model.projects.length;
        return html`<button type="button" class="seg-chip ${raw(model.portfolioFilter === filter.key ? "is-active" : "")}" data-action="portfolio-filter" data-filter="${filter.key}" aria-pressed="${raw(model.portfolioFilter === filter.key ? "true" : "false")}">${filter.label} ${count}</button>`;
      }).join("");
    }

    function actionFilterChips(model) {
      return actionFilters
        .filter((filter) => filter.key === "all" || model.actionCounts[filter.key] || model.portfolioActionFilter === filter.key)
        .map((filter) => {
          const count = filter.key === "all" ? model.candidateCount : model.actionCounts[filter.key] || 0;
          return html`<button type="button" class="seg-chip ${raw(model.portfolioActionFilter === filter.key ? "is-active" : "")}" data-action="portfolio-action-filter" data-action-filter="${filter.key}" aria-pressed="${raw(model.portfolioActionFilter === filter.key ? "true" : "false")}">${filter.label} ${count}</button>`;
        }).join("");
    }

    function benchmarkFilterChips(model) {
      return benchmarkFilters.map((filter) => {
        const count = filter.key === "focused" ? model.benchmarkFocusCount : model.candidateCount;
        return html`<button type="button" class="seg-chip ${raw(model.portfolioBenchmarkFilter === filter.key ? "is-active" : "")}" data-action="portfolio-benchmark-filter" data-benchmark-filter="${filter.key}" aria-pressed="${raw(model.portfolioBenchmarkFilter === filter.key ? "true" : "false")}">${filter.label} ${count}</button>`;
      }).join("");
    }

    function projectCard(project, index, total) {
      const progress = progressValue(project);
      const burnColor = project.health === "red" ? "var(--red)" : project.health === "amber" ? "var(--amber)" : "var(--green)";
      const category = project.category || "";
      const description = project.description || "";
      return html`
        <article class="portfolio-card panel" role="listitem" aria-posinset="${index + 1}" aria-setsize="${total}" aria-label="${projectListItemLabel(project)}" data-project-id="${project.id}" data-source-kind="${project.sourceKind || "owned"}" data-search-result="pm-portfolio">
          <div class="portfolio-head">
            <button type="button" class="portfolio-name-btn" data-action="open-project" data-project-id="${project.id}">
              <strong class="portfolio-name">${project.name}</strong>
              <small>${project.owner || "담당자 없음"} · 마감 ${project.deadline || "미정"}</small>
            </button>
            <div class="portfolio-head-right">
              <span class="portfolio-health" style="background:${raw(healthColor[project.health] || "var(--muted)")}" aria-label="프로젝트 상태">${statusLabel[project.status] || project.status || "상태 없음"}</span>
              <div class="pm-card-actions">
                <button type="button" class="pm-icon-btn" data-action="project-edit" data-project-id="${project.id}" title="${project.name} 편집" aria-label="${project.name} 편집">✎</button>
                <button type="button" class="pm-icon-btn pm-icon-btn-del" data-action="project-delete" data-project-id="${project.id}" title="${project.name} 삭제" aria-label="${project.name} 삭제">✕</button>
              </div>
            </div>
          </div>
          ${category || description ? raw(html`
            <div class="portfolio-summary">
              ${category ? raw(html`<span class="portfolio-category">${category}</span>`) : ""}
              ${description ? raw(html`<p>${description}</p>`) : ""}
            </div>
          `) : ""}
          ${raw(projectAdoptionMeta(project))}
          ${raw(projectPromptHandoffButton(project))}
          <div class="portfolio-body">
            <div class="donut portfolio-donut" style="--value:${raw(progress)}">
              <span>진행률</span>
              <strong>${progress}%</strong>
            </div>
            <div class="portfolio-meta">
              <div class="portfolio-spark">${raw(spark(project.burn, burnColor))}</div>
              <div class="portfolio-meta-rows">
                <span><b>이슈</b> ${numericValue(project.openIssues)}</span>
                <span><b>위험</b> ${numericValue(project.risks)}</span>
                <span><b>팀</b> ${projectMembers(project).length}명</span>
              </div>
            </div>
          </div>
        </article>
      `;
    }

    function portfolioGridHTML(model) {
      if (model.list.length === 0) {
        return html`
          <section class="portfolio-grid">
            ${raw(model.query
              ? searchEmptyState("pm-portfolio", "검색 결과가 없습니다", "프로젝트 이름, 담당자, 후보 저장소, 커밋, 카테고리와 일치하는 항목이 없습니다.")
              : html`<article class="empty">일치하는 프로젝트가 없습니다.</article>`)}
          </section>
        `;
      }
      return html`
        <section class="portfolio-grid" role="list" aria-label="포트폴리오 프로젝트 목록" aria-setsize="${model.list.length}">
          ${raw(model.list.map((project, index) => projectCard(project, index, model.list.length)).join(""))}
        </section>
      `;
    }

    function renderPortfolioHTML(input) {
      const model = portfolioViewModel(input);
      return html`
        <section class="kpis">${raw(model.kpis.map((kpi) => kpiCard(kpi)).join(""))}</section>
        <div class="portfolio-toolbar">
          <div class="seg-control" aria-label="포트폴리오 필터">${raw(filterChips(model))}</div>
          <button type="button" class="primary-btn" data-action="project-add">+ 새 프로젝트</button>
        </div>
        <div class="portfolio-action-filter" data-candidate-action-filter-panel>
          <div class="seg-control" aria-label="후보 액션 필터">${raw(actionFilterChips(model))}</div>
        </div>
        <div class="portfolio-benchmark-filter" data-candidate-benchmark-filter-panel>
          <div class="seg-control" aria-label="후보 벤치 필터">${raw(benchmarkFilterChips(model))}</div>
        </div>
        ${raw(candidateActionQueueSummary(model.projects, model.portfolioActionFilter))}
        ${raw(candidateBenchmarkQueueSummary(model.projects, model.portfolioBenchmarkFilter))}
        ${raw(candidateBenchmarkRubric(model.projects, model.portfolioBenchmarkFilter))}
        ${raw(candidateWorkspaceRubric(model.projects, model.portfolioBenchmarkFilter))}
        ${raw(candidateKnowledgeBaseRubric(model.projects, model.portfolioBenchmarkFilter))}
        ${raw(candidateBenchmarkReviewQueue(model.projects, model.portfolioBenchmarkFilter))}
        ${raw(portfolioGridHTML(model))}
      `;
    }

    return {
      version: VERSION,
      portfolioViewModel,
      filterChips,
      actionFilterChips,
      benchmarkFilterChips,
      projectCard,
      portfolioGridHTML,
      renderPortfolioHTML,
    };
  }

  root.JooParkPortfolioView = {
    version: VERSION,
    create: createPortfolioView,
  };
})(window);
