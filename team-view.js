(function (root) {
  "use strict";

  const VERSION = "joopark-team-view/v1";

  function createTeamView(deps) {
    const options = deps || {};
    const html = options.html;
    const raw = options.raw;
    const matches = typeof options.matches === "function" ? options.matches : function () { return true; };
    const kpiCard = typeof options.kpiCard === "function" ? options.kpiCard : function () { return ""; };
    const panelHead = typeof options.panelHead === "function" ? options.panelHead : function (title) { return html`<div class="panel-head"><h2>${title}</h2></div>`; };
    const searchEmptyState = typeof options.searchEmptyState === "function" ? options.searchEmptyState : function () { return ""; };
    const projectName = typeof options.projectName === "function" ? options.projectName : function (id) { return id || "프로젝트"; };

    if (typeof html !== "function" || typeof raw !== "function") {
      throw new Error("team view requires html and raw helpers");
    }

    function safeProjects(member) {
      return Array.isArray(member.projects) ? member.projects : [];
    }

    function safeLoad(member) {
      const load = Number(member.load);
      if (!Number.isFinite(load)) return 0;
      return Math.max(0, Math.min(100, Math.round(load)));
    }

    function loadColor(load) {
      return load > 85 ? "var(--red)" : load > 65 ? "var(--amber)" : "var(--green)";
    }

    function memberSearchText(member) {
      const projects = safeProjects(member).map((id) => projectName(id)).join(" ");
      return `${member.name || ""} ${member.role || ""} ${projects}`;
    }

    function teamViewModel(input) {
      const data = input || {};
      const team = Array.isArray(data.team) ? data.team : [];
      const projects = Array.isArray(data.projects) ? data.projects : [];
      const issues = Array.isArray(data.issues) ? data.issues : [];
      const query = (data.query || "").trim();
      const list = team.filter((member) => matches(memberSearchText(member), query));
      const activeMembers = team.filter((member) => !member.onLeave);
      const total = team.length;
      const avgLoad = Math.round(activeMembers.reduce((sum, member) => sum + safeLoad(member), 0) / Math.max(1, activeMembers.length));
      const over = team.filter((member) => safeLoad(member) > 85).length;
      const leave = team.filter((member) => member.onLeave).length;
      const kpis = [
        { title: "팀원", value: String(total), unit: "명", color: "#2387ff", badge: "◈", delta: "" },
        { title: "평균 부하", value: String(avgLoad), unit: "%", color: "#22d3ee", badge: "✺", delta: "" },
        { title: "오버할당", value: String(over), unit: "명", color: "#ff4d5e", badge: "△", delta: over ? "조치 필요" : "없음", trendDown: over > 0 },
        { title: "휴가 중", value: String(leave), unit: "명", color: "#a970ff", badge: "◎", delta: "" },
      ];

      return {
        team,
        projects,
        issues,
        query,
        list,
        total,
        avgLoad,
        over,
        leave,
        kpis,
        teamSearchEmpty: !!query && list.length === 0,
      };
    }

    function memberOpenLabel(member) {
      const load = safeLoad(member);
      const projectCount = safeProjects(member).length;
      const leave = member.onLeave ? ", 휴가 중" : "";
      return `${member.name} 멤버 열기, ${member.role}, 부하 ${load}%, 담당 프로젝트 ${projectCount}개${leave}`;
    }

    function memberRow(member) {
      const load = safeLoad(member);
      const projects = safeProjects(member);
      const projectPills = projects.length === 0
        ? html`<small>—</small>`
        : projects.map((pid) => html`<span class="team-project-pill">${projectName(pid)}</span>`).join("");
      return html`
        <div class="team-row-wrap" data-search-result="pm-team">
          <button type="button" class="team-row" data-action="open-member" data-member-id="${member.id}" aria-label="${memberOpenLabel(member)}">
            <div class="team-row-name">
              <span class="team-avatar" aria-hidden="true">${(member.name || "?").slice(0, 1)}</span>
              <div>
                <strong>${member.name}</strong>
                <small>${member.role}${member.onLeave ? raw(" · <em class=\"team-leave\">휴가</em>") : ""}</small>
              </div>
            </div>
            <div class="team-projects">${raw(projectPills)}</div>
            <div class="team-load" aria-hidden="true">
              <div class="load-bar"><i style="--w:${raw(load)}%; background:${raw(loadColor(load))}"></i></div>
              <b>${load}%</b>
            </div>
          </button>
          <div class="team-row-actions">
            <button type="button" class="pm-icon-btn" data-action="member-edit" data-member-id="${member.id}" title="${member.name} 멤버 편집" aria-label="${member.name} 멤버 편집">✎</button>
            <button type="button" class="pm-icon-btn pm-icon-btn-del" data-action="member-delete" data-member-id="${member.id}" title="${member.name} 멤버 삭제" aria-label="${member.name} 멤버 삭제">✕</button>
          </div>
        </div>
      `;
    }

    function assignmentIssueCount(member, project, issues) {
      return issues.filter((issue) => issue.assignee === member.id && issue.project === project.id && issue.status !== "done").length;
    }

    function matrixHeadHTML(model) {
      return html`
        <div class="team-matrix-row team-matrix-head" role="row">
          <div role="columnheader" class="team-matrix-col-head team-matrix-member-head"><small>멤버</small></div>
          ${raw(model.projects.map((project) => html`<div role="columnheader" class="team-matrix-col-head"><small>${project.name}</small></div>`).join(""))}
        </div>
      `;
    }

    function matrixRowsHTML(model) {
      return model.list.map((member) => html`
        <div class="team-matrix-row" role="row">
          <div class="team-matrix-row-head" role="rowheader">
            <strong>${member.name}</strong>
            <small>${member.role}</small>
          </div>
          ${raw(model.projects.map((project) => {
            const assigned = safeProjects(member).includes(project.id);
            const issueCount = assignmentIssueCount(member, project, model.issues);
            const label = `${member.name}, ${project.name}, ${assigned ? `배정됨, 열린 이슈 ${issueCount}건` : "배정 없음"}`;
            return html`
              <div class="team-matrix-cell ${raw(assigned ? "is-assigned" : "")}" role="cell" aria-label="${label}">
                ${assigned ? raw(html`<b>${issueCount}</b><small>이슈</small>`) : raw(html`<span class="team-matrix-dash">·</span>`)}
              </div>
            `;
          }).join(""))}
        </div>
      `).join("");
    }

    function teamEmptyHTML(model) {
      return model.teamSearchEmpty
        ? html`<div class="team-search-empty">${raw(searchEmptyState("pm-team", "팀 검색 결과가 없습니다", `“${model.query}”와 일치하는 멤버나 역할이 없습니다. 검색어를 지우고 전체 리소스를 다시 확인하세요.`))}</div>`
        : html`<article class="empty">일치하는 멤버가 없습니다.</article>`;
    }

    function matrixEmptyHTML(model) {
      return html`
        <article class="empty team-matrix-empty" ${raw(model.teamSearchEmpty ? 'data-team-matrix-empty="search"' : "")}>
          ${model.teamSearchEmpty ? "검색된 멤버가 없어 매트릭스를 표시할 수 없습니다." : "매트릭스에 표시할 멤버가 없습니다."}
        </article>
      `;
    }

    function teamMatrixHTML(model) {
      const rows = matrixRowsHTML(model);
      return html`
        <div class="team-matrix" role="table" aria-label="프로젝트별 팀 배정 및 열린 이슈 수" aria-rowcount="${model.list.length + 1}" aria-colcount="${model.projects.length + 1}">
          ${raw(matrixHeadHTML(model))}
          ${rows ? raw(rows) : raw(matrixEmptyHTML(model))}
        </div>
      `;
    }

    function renderTeamHTML(input) {
      const model = teamViewModel(input);
      return html`
        <section class="kpis kpis-4">${raw(model.kpis.map((kpi) => kpiCard(kpi)).join(""))}</section>
        <section class="team-layout">
          <article class="panel team-list-panel">
            ${raw(panelHead("팀 멤버", null, html`<button type="button" class="primary-btn" data-action="member-add">+ 멤버 추가</button>`))}
            <div class="team-list">
              ${model.list.length === 0 ? raw(teamEmptyHTML(model)) : raw(model.list.map(memberRow).join(""))}
            </div>
          </article>
          <article class="panel team-matrix-panel">
            ${raw(panelHead("프로젝트 매트릭스", null, ""))}
            ${raw(teamMatrixHTML(model))}
          </article>
        </section>
      `;
    }

    return {
      version: VERSION,
      loadColor,
      teamViewModel,
      memberRow,
      matrixHeadHTML,
      matrixRowsHTML,
      teamMatrixHTML,
      renderTeamHTML,
    };
  }

  root.JooParkTeamView = {
    version: VERSION,
    create: createTeamView,
  };
})(window);
