/* ================================================================
 * JooPark Workspace — Home view orchestration.
 * Static non-module runtime loaded before app.js.
 * ================================================================ */

(function initJooParkHomeView(global) {
  "use strict";

  const VERSION = "joopark-home-view/v1";

  function createHomeView(deps = {}) {
    const {
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
      publishEvidenceFresh,
      formatKoreanShort,
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
    } = deps;
    const renderDashboardIntelligenceHTML = typeof dashboardIntelligenceHTML === "function" ? dashboardIntelligenceHTML : function () { return ""; };

    function homeCommandTilesHTML({
      todayEventsHTML,
      todayTodosHTML,
      upcomingHTML,
      totalProjects,
      portfolioBody,
      totalIssues,
      kanbanBody,
      dashboard,
      ganttBody,
      teamBody,
      unhealthy,
      instancesBody,
      schemaTotalTables,
      schemaBody,
      slow,
      queriesBody,
      pendingMig,
      backupsBody,
    }) {
      return html`
        <section class="home-command">
          <article class="panel home-today">
            <div class="panel-head"><div><h2>오늘</h2><a href="#cal" data-action="nav-to" data-view="cal" title="캘린더 뷰로 이동하여 오늘 일정을 확인합니다">일정 전체 ›</a></div></div>
            <div class="agenda-list">${raw(todayEventsHTML)}</div>
            <p class="home-today-label" title="오늘 마감이거나 이미 마감이 지난 할 일 목록">오늘 마감 할 일</p>
            ${raw(todayTodosHTML)}
          </article>
          <article class="panel home-upcoming-panel">
            <div class="panel-head"><div><h2>다가오는 7일</h2><a href="#cal" data-action="nav-to" data-view="cal" title="캘린더 뷰로 이동하여 전체 일정을 확인합니다">달력 ›</a></div></div>
            ${raw(upcomingHTML)}
          </article>
        </section>
        <p class="home-section-title" title="팀과 시스템 관련 요약 정보를 표시합니다">팀 · 시스템 관리</p>
        <section class="home-tiles">
          ${raw(homeTileHTML("프로젝트 포트폴리오", `${totalProjects}개`,        "pm-portfolio",   portfolioBody))}
          ${raw(homeTileHTML("Kanban 보드",         `${totalIssues}개 이슈`,    "pm-kanban",      kanbanBody))}
          ${raw(homeTileHTML("간트 마일스톤",        `${dashboard.gantt.tasks.filter((t) => t.milestone).length}개`, "pm-gantt", ganttBody))}
          ${raw(homeTileHTML("팀 부하",              `${dashboard.team.length}명`, "pm-team",      teamBody))}
          ${raw(homeTileHTML("DB 인스턴스",          `${unhealthy}건 주의`,       "dbm-instances",instancesBody))}
          ${raw(homeTileHTML("스키마",               `${schemaTotalTables} 테이블`,"dbm-schema",   schemaBody))}
          ${raw(homeTileHTML("질의 성능",            `slow ${slow}건`,            "dbm-queries",  queriesBody))}
          ${raw(homeTileHTML("백업 / 마이그",         `대기 ${pendingMig}건`,       "dbm-backups",  backupsBody))}
        </section>
      `;
    }
    
    function homeFirstRunGuidanceHTML({
      firstRunSteps,
      firstRunReadyCount,
      firstRunActionRequiredCount,
      firstRunNextStep,
      firstRunGuidedStartItems,
      firstRunGuidedStartCoverage,
    }) {
      const firstRunGuidedStartReady = firstRunGuidedStartCoverage === 1 && firstRunGuidedStartItems.length === 3;
      return html`
        <section class="panel home-first-run" data-home-first-run-guidance data-home-first-run-variant="task_strip" data-home-first-run-source="linear_jira_onboarding_benchmark" data-home-first-run-step-count="${firstRunSteps.length}" data-home-first-run-ready-count="${firstRunReadyCount}" data-home-first-run-action-required-count="${firstRunActionRequiredCount}" data-home-first-run-next-key="${firstRunNextStep.key}" data-home-first-run-next-action="${firstRunNextStep.action}" data-home-first-run-next-view="${firstRunNextStep.viewName || ""}" data-home-first-run-guided-start-ready="${firstRunGuidedStartReady ? "true" : "false"}" data-home-first-run-guided-start-coverage="${firstRunGuidedStartCoverage}" data-home-first-run-guided-start-item-count="${firstRunGuidedStartItems.length}">
          <div class="panel-head">
            <div>
              <h2>처음 5분 quick start</h2>
              <small>오늘 할 일, 실행 프로젝트, 로컬 백업을 한 화면에서 시작</small>
            </div>
            <span class="home-first-run-score">${firstRunReadyCount}/${firstRunSteps.length} ready</span>
          </div>
          <div class="home-first-run-guided-start" data-home-first-run-guided-start data-home-first-run-guided-start-coverage="${firstRunGuidedStartCoverage}" data-home-first-run-guided-start-item-count="${firstRunGuidedStartItems.length}">
            ${firstRunGuidedStartItems.map((item) => raw(html`
              <article class="home-first-run-guided-start-item" data-home-first-run-guided-start-item data-home-first-run-guided-start-key="${item.key}" data-home-first-run-guided-start-status="${item.status}" data-home-first-run-guided-start-action="${item.action}" data-home-first-run-guided-start-metric="${item.metric}">
                <small>${item.metric}</small>
                <strong>${item.label}</strong>
                <p>${item.detail}</p>
              </article>
            `))}
          </div>
          <ol class="home-first-run-steps">
            ${firstRunSteps.map((step, index) => raw(html`
              <li data-home-first-run-step data-home-first-run-step-key="${step.key}" data-home-first-run-step-status="${step.status}" data-home-first-run-step-action="${step.action}" data-home-first-run-step-view="${step.viewName || ""}">
                <span>${index + 1}</span>
                <div>
                  <strong>${step.label}</strong>
                  <small>${step.metric}</small>
                  <p>${step.detail}</p>
                </div>
                <button type="button" class="small-action" data-action="${step.action}" data-view="${step.viewName || ""}">${step.actionLabel}</button>
              </li>
            `))}
          </ol>
        </section>
      `;
    }
    
    function homeProjectFollowThroughHTML({
      projectFollowThroughSteps,
      projectFollowThroughReadyCount,
      projectFollowThroughActionRequiredCount,
      projectFollowThroughNextStep,
    }) {
      if (!projectFollowThroughSteps.length) return "";
      return html`
        <section class="panel home-project-followthrough" data-home-project-followthrough data-home-project-followthrough-variant="activation_ladder" data-home-project-followthrough-source="linear_project_jira_work_item_benchmark" data-home-project-followthrough-step-count="${projectFollowThroughSteps.length}" data-home-project-followthrough-ready-count="${projectFollowThroughReadyCount}" data-home-project-followthrough-action-required-count="${projectFollowThroughActionRequiredCount}" data-home-project-followthrough-next-key="${projectFollowThroughNextStep.key || ""}" data-home-project-followthrough-next-action="${projectFollowThroughNextStep.action || ""}" data-home-project-followthrough-next-view="${projectFollowThroughNextStep.viewName || ""}">
          <div class="panel-head">
            <div>
              <h2>Project follow-through</h2>
              <small>프로젝트 생성 후 실행 가능한 상태까지 이어지는 다음 행동</small>
            </div>
            <span class="home-project-followthrough-score">${projectFollowThroughReadyCount}/${projectFollowThroughSteps.length} ready</span>
          </div>
          <ol class="home-project-followthrough-steps">
            ${projectFollowThroughSteps.map((step) => raw(html`
              <li data-home-project-followthrough-step data-home-project-followthrough-step-key="${step.key}" data-home-project-followthrough-step-status="${step.status}" data-home-project-followthrough-step-action="${step.action}" data-home-project-followthrough-step-view="${step.viewName}">
                <span>${step.status === "ready" ? "Ready" : "Next"}</span>
                <div>
                  <strong>${step.label}</strong>
                  <small>${step.metric}</small>
                  <p>${step.detail}</p>
                </div>
                <button type="button" class="small-action" data-action="${step.action}" data-view="${step.viewName}"${step.defaultMilestone ? raw(' data-default-milestone="true"') : ""}>${step.actionLabel}</button>
              </li>
            `))}
          </ol>
        </section>
      `;
    }

    function homeReadinessSummaryHTML(model) {
      const { publishBlockers, launchProofReady, benchmarkFocused, sourceBacked, readinessCards } = model;
      return html`
        <section class="panel home-readiness" data-home-readiness data-home-publish-blockers="${publishBlockers.length}" data-home-launch-proof-ready="${launchProofReady ? "true" : "false"}" data-home-benchmark-count="${benchmarkFocused.length}" data-home-source-backed-count="${sourceBacked.length}">
          <div class="panel-head">
            <div><h2>워크스페이스 준비도</h2><a href="#system" data-action="nav-to" data-view="system">시스템 상태 ›</a></div>
            <small>로컬 데이터, 릴리스 게이트, 공개 증거, 벤치마크 큐 요약</small>
          </div>
          <div class="home-readiness-grid">
            ${readinessCards.map((card) => raw(html`
              <button type="button" class="home-readiness-card" data-action="nav-to" data-view="${card.viewName}" data-home-readiness-card="${card.key}" data-readiness-tone="${card.tone}" data-home-readiness-card-evidence-count="${card.evidenceCount || 0}">
                <span>${card.label}</span>
                <strong>${card.value}</strong>
                <small>${card.detail}</small>
              </button>
            `))}
          </div>
        </section>
      `;
    }

    function homeReleaseBadgeHTML({ publishBlockers, launchProofReady }) {
      const tone = launchProofReady ? "ready" : (publishBlockers.length ? "action" : "watch");
      const label = launchProofReady
        ? "공개 증거 준비 완료"
        : (publishBlockers.length ? `공개 준비 남은 작업 ${publishBlockers.length}건` : "공개 준비 점검 진행 중");
      return html`
        <button type="button" class="home-release-badge" data-action="nav-to" data-view="system" data-home-release-badge data-home-release-badge-tone="${tone}" data-home-release-blockers="${publishBlockers.length}" data-home-release-proof-ready="${launchProofReady ? "true" : "false"}" title="System Status에서 릴리스·공개 준비 상세를 확인합니다">
          <span>release</span>
          <strong>${label}</strong>
          <em>시스템 상태 ›</em>
        </button>
      `;
    }

    function homeCommandTilePreviewContentHTML({ totalIssues }) {
      const topProjects = [...dashboard.projects].sort((a, b) => b.progress - a.progress).slice(0, 3);
      const portfolioBody = topProjects.length
        ? homeListPreviewHTML(topProjects, (p, i) => html`
            <li title="${p.name}: 진행률 ${p.progress}%, 상태 ${p.health || 'unknown'}">
              <span class="home-dot" style="background:${raw(HEALTH_COLOR[p.health])}"></span>
              <strong>${p.name}</strong>
              <em>${p.progress}%</em>
            </li>`)
        : homeEmptyHTML("projects", "프로젝트가 없습니다", "첫 운영 프로젝트를 만들면 진행률과 상태가 홈에 나타납니다.", "project-add", "프로젝트 만들기");
    
      const counts = { todo: 0, "in-progress": 0, review: 0, done: 0 };
      dashboard.issues.forEach((i) => { counts[i.status] = (counts[i.status] || 0) + 1; });
      const kanbanBody = totalIssues
        ? html`
          <div class="home-stats">
            <div title="대기 중인 이슈: ${counts.todo}건"><b>${counts.todo}</b><small>To Do</small></div>
            <div title="진행 중인 이슈: ${counts["in-progress"]}건"><b>${counts["in-progress"]}</b><small>In Progress</small></div>
            <div title="검토 중인 이슈: ${counts.review}건"><b>${counts.review}</b><small>Review</small></div>
            <div title="완료된 이슈: ${counts.done}건"><b>${counts.done}</b><small>Done</small></div>
          </div>
        `
        : homeEmptyHTML("kanban", "이슈가 없습니다", "첫 이슈를 만들면 Kanban 단계별 작업량을 바로 볼 수 있습니다.", "issue-add", "이슈 만들기");
    
      const upcomingMs = dashboard.gantt.tasks.filter((t) => t.milestone).slice(0, 3);
      const ganttBody = upcomingMs.length
        ? homeListPreviewHTML(upcomingMs, (m) => html`
            <li title="마일스톤: ${m.name} - 시작일 ${m.start}">
              <span class="home-dot" style="background:var(--violet)"></span>
              <strong>${m.name}</strong>
              <em>${m.start}</em>
            </li>`)
        : homeEmptyHTML("gantt", "마일스톤이 없습니다", "일정이 있는 작업을 추가하면 홈에서 다음 마일스톤을 추적합니다.", "task-add", "작업 만들기");
    
      const overloaded = dashboard.team.filter((m) => m.load > 85);
      const teamBody = dashboard.team.length
        ? html`
          ${raw(homeListPreviewHTML(dashboard.team.slice(0, 4), (m) => html`
            <li title="${m.name}: 부하 ${m.load}%${m.load > 85 ? ' (오버할당)' : m.load > 65 ? ' (주의)' : ' (정상)'}">
              <span class="home-dot" style="background:${raw(m.load > 85 ? "var(--red)" : m.load > 65 ? "var(--amber)" : "var(--green)")}"></span>
              <strong>${m.name}</strong>
              <em>${m.load}%</em>
            </li>`))}
          <small class="home-sub">오버할당 ${overloaded.length}명</small>
        `
        : homeEmptyHTML("team", "팀 멤버가 없습니다", "담당자를 추가하면 부하와 배정 가능성을 홈에서 확인할 수 있습니다.", "member-add", "멤버 추가");
    
      const instancesBody = dashboard.dbInstances.length
        ? homeListPreviewHTML(dashboard.dbInstances, (d) => html`
            <li title="${d.name}: CPU ${d.cpu}%, 상태 ${d.health || 'unknown'}">
              <span class="home-dot" style="background:${raw(HEALTH_COLOR[d.health])}"></span>
              <strong>${d.name}</strong>
              <em>CPU ${d.cpu}%</em>
            </li>`)
        : homeEmptyHTML("db-instances", "DB 인스턴스가 없습니다", "DB 카탈로그 항목을 등록하면 상태와 CPU 메모를 홈에서 볼 수 있습니다.", "instance-add", "인스턴스 추가");
    
      const schemaTotalTables = dashboard.schemas.reduce((a, s) => a + s.databases.reduce((b, db) => b + db.tables.length, 0), 0);
      const schemaDbCount = dashboard.schemas.reduce((a, s) => a + s.databases.length, 0);
      const schemaBody = schemaTotalTables
        ? html`
          <div class="home-stats">
            <div title="등록된 DB 인스턴스 수: ${dashboard.dbInstances.length}개"><b>${dashboard.dbInstances.length}</b><small>인스턴스</small></div>
            <div title="등록된 데이터베이스 수: ${schemaDbCount}개"><b>${schemaDbCount}</b><small>DB</small></div>
            <div title="등록된 테이블 수: ${schemaTotalTables}개"><b>${schemaTotalTables}</b><small>테이블</small></div>
          </div>
        `
        : homeEmptyHTML("schema", "스키마가 없습니다", "DB 인스턴스를 기준으로 테이블 구조를 문서화하세요.", dashboard.dbInstances.length ? "table-add" : "instance-add", dashboard.dbInstances.length ? "테이블 추가" : "DB부터 추가");
    
      const topQueries = [...dashboard.queries].sort((a, b) => b.p95Ms - a.p95Ms).slice(0, 3);
      const queriesBody = topQueries.length
        ? homeListPreviewHTML(topQueries, (q) => html`
            <li title="쿼리 ${q.id}: P95 ${q.p95Ms}ms, 평균 ${q.avgMs}ms, 실행 ${q.count}회">
              <span class="home-dot" style="background:var(--red)"></span>
              <strong>${q.id}</strong>
              <em>p95 ${q.p95Ms}ms</em>
            </li>`)
        : homeEmptyHTML("queries", "저장 쿼리가 없습니다", "자주 보는 SQL을 저장하면 느린 쿼리 신호가 홈에 나타납니다.", dashboard.dbInstances.length ? "query-add" : "instance-add", dashboard.dbInstances.length ? "쿼리 추가" : "DB부터 추가");
    
      const recentBackups = dashboard.dbInstances.length ? dashboard.backups.slice(-4).reverse() : [];
      const backupsBody = recentBackups.length
        ? homeListPreviewHTML(recentBackups, (b) => html`
            <li title="백업 ${b.date}: ${b.instance} - 상태 ${b.status}">
              <span class="home-dot" style="background:${raw(b.status === "ok" ? "var(--green)" : b.status === "warn" ? "var(--amber)" : "var(--red)")}"></span>
              <strong>${b.date}</strong>
              <em>${b.instance}</em>
            </li>`)
        : homeEmptyHTML("backups", "백업 기록이 없습니다", "변경 이력을 기록하면 백업과 마이그레이션 상태를 홈에서 함께 확인할 수 있습니다.", "migration-add", "마이그레이션 추가");
    
      return {
        portfolioBody,
        kanbanBody,
        ganttBody,
        teamBody,
        instancesBody,
        schemaTotalTables,
        schemaBody,
        queriesBody,
        backupsBody,
      };
    }
    

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
      const executionQueue = homeExecutionQueueModel({ today, weekEnd, openTodos, bucketFilter: state.homeExecutionBucketFilter });
      // Occurrence-based like `upcoming` above so recurring deadlines count.
      const weekDeadlines =
        expandOccurrences(today, weekEnd).filter((e) => e.category === "deadline").length +
        openTodos.filter((t) => t.due && t.due >= today && t.due <= weekEnd).length;
    
      const totalProjects = dashboard.projects.length;
      const activeHabits = dashboard.habits.filter((h) => !h.archived);
      const habitsCheckedToday = activeHabits.filter((h) => h.log && h.log[today]).length;
      const totalIssues = dashboard.issues.length;
      const unhealthy = dashboard.dbInstances.filter((d) => d.health !== "green").length;
      const slow = dashboard.queries.length;
      const pendingMig = dashboard.migrations.filter((m) => m.status === "pending").length;
      const adoptionCandidates = dashboard.projects.filter((project) => project.sourceKind === "adoption-candidate");
      const sourceBacked = adoptionCandidates.filter((project) => safeGithubUrl(project.url) && shortCommit(project.lastCommit));
      const benchmarkFocused = adoptionCandidates.filter((project) => projectBenchmarkContext(project).any);
      const publishItems = publishReadinessItems();
      const publishBlockers = publishItems.filter((item) => item.state === "blocked");
      const publishData = state.publishEvidence && state.publishEvidence.data ? state.publishEvidence.data : null;
      const launchProofReady = !!(publishData && publishData.postPublishEvidenceReady && publishEvidenceFresh(publishData));
      const publishStatus = launchProofReady ? "proof ready" : `${publishBlockers.length} actions`;
      const releaseGate = publishReadinessItems().find((item) => item.key === "release-gates") || {};
      const releaseGateEvidence = Array.isArray(releaseGate.evidence) ? releaseGate.evidence : [];
      const readinessCards = [
        {
          key: "data-ownership",
          tone: "green",
          viewName: "settings",
          label: "데이터 소유권",
          value: "local",
          detail: "브라우저 저장 + JSON 백업/복구",
        },
        {
          key: "release-gate",
          tone: "blue",
          viewName: "system",
          label: "릴리스 게이트",
          value: `${releaseGateEvidence.length} proofs`,
          detail: "route 17/17, mobile search/UI, delete undo, a11y",
          evidenceCount: releaseGateEvidence.length,
        },
        {
          key: "publish-proof",
          tone: launchProofReady ? "green" : "amber",
          viewName: "system",
          label: "공개 증거",
          value: publishStatus,
          detail: launchProofReady ? "Pages/workflow evidence freshness 통과" : "workflow 설치와 dispatch evidence가 남음",
        },
        {
          key: "benchmark-queue",
          tone: "violet",
          viewName: "pm-portfolio",
          label: "벤치마크 큐",
          value: `${benchmarkFocused.length}/${adoptionCandidates.length}`,
          detail: `${sourceBacked.length}개 source-backed 후보 기반`,
        },
      ];
      const firstRunModel = homeFirstRunGuidanceModel({
        todaysEvents,
        openTodos,
        noteCount: dashboard.notes.length,
        totalProjects,
      });
      const {
        firstRunSteps,
        firstRunReadyCount,
        firstRunActionRequiredCount,
        firstRunNextStep,
        firstRunGuidedStartItems,
        firstRunGuidedStartCoverage,
      } = firstRunModel;
      const milestoneCount = dashboard.gantt.tasks.filter((task) => task.milestone).length;
      const projectFollowThroughModel = homeProjectFollowThroughModel({
        totalProjects,
        totalIssues,
        milestoneCount,
        teamCount: dashboard.team.length,
      });
      const projectFollowThroughHTML = homeProjectFollowThroughHTML(projectFollowThroughModel);
    
      /* Personal-first KPIs */
      const kpis = [
        { title: "오늘 일정",   value: String(todaysEvents.length), unit: "건", color: "var(--blue)", badge: "◷", delta: formatKoreanShort(today), tip: "오늘 등록된 일정 수" },
        { title: "할 일 남음",  value: String(openTodos.length),    unit: "건", color: overdueTodos.length ? "var(--red)" : "var(--cyan)", badge: "☑", delta: overdueTodos.length ? `지남 ${overdueTodos.length}건` : "양호", trendDown: overdueTodos.length > 0, tip: "미완료 할 일 수" },
        { title: "이번 주 마감", value: String(weekDeadlines),       unit: "건", color: "var(--amber)", badge: "⚑", delta: "앞으로 7일", tip: "이번 주 마감인 할 일 수" },
        { title: "습관 체크",   value: activeHabits.length ? `${habitsCheckedToday}/${activeHabits.length}` : "0", unit: activeHabits.length ? "" : "개", color: "var(--green)", badge: "↺", delta: activeHabits.length ? (habitsCheckedToday >= activeHabits.length ? "오늘 완료" : "오늘 남음 " + (activeHabits.length - habitsCheckedToday) + "개") : "습관을 추가해 보세요", tip: "오늘 체크한 습관 / 활성 습관 수" },
      ];
    
      const { todayEventsHTML, todayTodosHTML, upcomingHTML } = homeTodayCommandContentHTML({ todaysEvents, overdueTodos, todayTodos, upcoming });
      const {
        portfolioBody,
        kanbanBody,
        ganttBody,
        teamBody,
        instancesBody,
        schemaTotalTables,
        schemaBody,
        queriesBody,
        backupsBody,
      } = homeCommandTilePreviewContentHTML({ totalIssues });
    
      setHTML(view, html`
        ${raw(homeHeroHTML({ today, greet, name, todaysEvents, openTodos, overdueTodos }))}
        ${raw(homeReleaseBadgeHTML({ publishBlockers, launchProofReady }))}
        <section class="kpis kpis-4">${raw(kpis.map((k) => kpiCard(k)).join(""))}</section>
        ${raw(renderDashboardIntelligenceHTML())}
        ${raw(homeExecutionQueueHTML(executionQueue))}
        ${raw(homeCommandTilesHTML({ todayEventsHTML, todayTodosHTML, upcomingHTML, totalProjects, portfolioBody, totalIssues, kanbanBody, dashboard, ganttBody, teamBody, unhealthy, instancesBody, schemaTotalTables, schemaBody, slow, queriesBody, pendingMig, backupsBody }))}
        ${raw(homeFirstRunGuidanceHTML({ firstRunSteps, firstRunReadyCount, firstRunActionRequiredCount, firstRunNextStep, firstRunGuidedStartItems, firstRunGuidedStartCoverage }))}
        ${raw(projectFollowThroughHTML)}
        ${raw(homeReadinessSummaryHTML({ publishBlockers, launchProofReady, benchmarkFocused, sourceBacked, readinessCards }))}
      `);
    }

    return Object.freeze({
      version: VERSION,
      renderHome,
    });
  }

  global.JooParkHomeView = Object.freeze({
    version: VERSION,
    create: createHomeView,
  });
})(typeof window !== "undefined" ? window : globalThis);
