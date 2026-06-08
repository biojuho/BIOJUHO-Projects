(function (root) {
  "use strict";

  const VERSION = "joopark-gantt-view/v1";
  const DAY_PX = 12;
  const ROW_H = 30;
  const TOP_PAD = 30;

  function createGanttView(deps) {
    const options = deps || {};
    const html = options.html;
    const raw = options.raw;
    const matches = typeof options.matches === "function" ? options.matches : function () { return true; };
    const kpiCard = typeof options.kpiCard === "function" ? options.kpiCard : function () { return ""; };
    const panelHead = typeof options.panelHead === "function" ? options.panelHead : function (title) { return html`<div class="panel-head"><h2>${title}</h2></div>`; };
    const searchEmptyState = typeof options.searchEmptyState === "function" ? options.searchEmptyState : function () { return ""; };
    const projectName = typeof options.projectName === "function" ? options.projectName : function (id) { return id || "프로젝트"; };
    const memberName = typeof options.memberName === "function" ? options.memberName : function (id) { return id || "미지정"; };
    const todayISO = typeof options.todayISO === "function" ? options.todayISO : function () { return ""; };
    const daysBetween = typeof options.daysBetween === "function" ? options.daysBetween : function () { return 0; };
    const parseDate = typeof options.parseDate === "function" ? options.parseDate : function (value) { return new Date(value); };

    if (typeof html !== "function" || typeof raw !== "function") {
      throw new Error("gantt view requires html and raw helpers");
    }

    function safeDeps(task) {
      return Array.isArray(task.deps) ? task.deps : [];
    }

    function safeColor(color) {
      return /^[a-z0-9-]+$/i.test(color || "") ? color : "blue";
    }

    function taskMatches(task, query) {
      return matches(`${task.name} ${task.owner} ${task.project}`, query);
    }

    function ganttViewModel(input) {
      const data = input || {};
      const gantt = data.gantt && typeof data.gantt === "object" ? data.gantt : {};
      const allTasks = Array.isArray(gantt.tasks) ? gantt.tasks : [];
      const query = data.query || "";
      const tasks = allTasks.filter((task) => taskMatches(task, query));
      const rangeStart = gantt.rangeStart || todayISO();
      const rangeEnd = gantt.rangeEnd || rangeStart;
      const totalDays = daysBetween(rangeStart, rangeEnd);
      const svgW = Math.max(1, totalDays * DAY_PX);
      const svgH = TOP_PAD + tasks.length * ROW_H + 20;
      const today = todayISO();

      const milestones = tasks.filter((task) => task.milestone).length;
      const dueSoon = tasks.filter((task) => !task.milestone && daysBetween(today, task.end) >= 0 && daysBetween(today, task.end) <= 7).length;
      const overdue = tasks.filter((task) => !task.milestone && daysBetween(task.end, today) > 0).length;
      const depViolations = tasks.filter((task) => safeDeps(task).some((depId) => {
        const dep = allTasks.find((candidate) => candidate.id === depId);
        return dep && daysBetween(dep.end, task.start) < 0;
      })).length;

      const kpis = [
        { title: "마일스톤", value: String(milestones), unit: "개", color: "#a970ff", badge: "◆", delta: "" },
        { title: "임박 데드라인", value: String(dueSoon), unit: "건", color: "#f7a928", badge: "△", delta: "7일 이내" },
        { title: "지연", value: String(overdue), unit: "건", color: "#ff4d5e", badge: "✕", delta: overdue ? "조치 필요" : "없음", trendDown: overdue > 0 },
        { title: "의존 충돌", value: String(depViolations), unit: "건", color: "#f7a928", badge: "↔", delta: depViolations ? "주의" : "정상" },
      ];

      return {
        allTasks,
        tasks,
        query,
        rangeStart,
        rangeEnd,
        totalDays,
        svgW,
        svgH,
        today,
        milestones,
        dueSoon,
        overdue,
        depViolations,
        kpis,
      };
    }

    function dayToX(model, value) {
      return daysBetween(model.rangeStart, value) * DAY_PX;
    }

    function chartSummary(model) {
      return `간트 차트: 표시 작업 ${model.tasks.length}개, 마일스톤 ${model.milestones}개, 지연 ${model.overdue}건, 의존 충돌 ${model.depViolations}건`;
    }

    function monthLinesHTML(model) {
      const months = [];
      const cursor = parseDate(model.rangeStart);
      cursor.setUTCDate(1);
      while (cursor < parseDate(model.rangeEnd)) {
        const month = `${cursor.getUTCFullYear()}-${String(cursor.getUTCMonth() + 1).padStart(2, "0")}-01`;
        months.push(month);
        cursor.setUTCMonth(cursor.getUTCMonth() + 1);
      }
      return months.map((month) => {
        const x = dayToX(model, month);
        return html`<line class="gantt-month-line" x1="${x}" y1="0" x2="${x}" y2="${model.svgH}"/>
          <text class="gantt-month-label" x="${x + 4}" y="16">${month.slice(0, 7)}</text>`;
      }).join("");
    }

    function todayLineHTML(model) {
      const todayX = dayToX(model, model.today);
      return html`<line class="gantt-today-line" x1="${todayX}" y1="0" x2="${todayX}" y2="${model.svgH}"/>
        <text class="gantt-today-label" x="${todayX + 4}" y="${model.svgH - 4}">오늘</text>`;
    }

    function rowStripesHTML(model) {
      return model.tasks.map((_task, index) => html`<rect class="gantt-row-bg" x="0" y="${TOP_PAD + index * ROW_H}" width="${model.svgW}" height="${ROW_H}"/>`).join("");
    }

    function taskShapeHTML(task, index, model) {
      const color = safeColor(task.color);
      const y = TOP_PAD + index * ROW_H + 6;
      const cls = `gantt-bar gantt-bar-${color}`;
      if (task.milestone) {
        const cx = dayToX(model, task.start) + 6;
        const cy = TOP_PAD + index * ROW_H + ROW_H / 2;
        const r = 8;
        const label = `작업 열기: ${task.name} · 마일스톤 ${task.start}`;
        return html`<polygon class="gantt-milestone gantt-bar-${raw(color)}" data-action="open-task" data-task-id="${task.id}" role="button" aria-label="${label}" points="${cx},${cy - r} ${cx + r},${cy} ${cx},${cy + r} ${cx - r},${cy}" tabindex="0"><title>${task.name} · ${task.start}</title></polygon>`;
      }
      const x = dayToX(model, task.start);
      const w = Math.max(6, daysBetween(task.start, task.end) * DAY_PX);
      const label = `작업 열기: ${task.name} · ${task.start}부터 ${task.end}까지`;
      return html`<g class="${raw(cls)}" data-action="open-task" data-task-id="${task.id}" role="button" aria-label="${label}" tabindex="0">
        <rect class="gantt-bar-rect" x="${x}" y="${y}" width="${w}" height="${ROW_H - 12}" rx="4"/>
        <text class="gantt-bar-label" x="${x + 6}" y="${y + (ROW_H - 12) / 2 + 4}">${task.name}</text>
        <title>${task.name} · ${task.start} → ${task.end}</title>
      </g>`;
    }

    function depLinesHTML(model) {
      return model.tasks.flatMap((task, index) => safeDeps(task).map((depId) => {
        const fromIndex = model.tasks.findIndex((candidate) => candidate.id === depId);
        if (fromIndex < 0) return "";
        const from = model.tasks[fromIndex];
        const x1 = dayToX(model, from.end);
        const y1 = TOP_PAD + fromIndex * ROW_H + ROW_H / 2;
        const x2 = dayToX(model, task.start);
        const y2 = TOP_PAD + index * ROW_H + ROW_H / 2;
        const midX = (x1 + x2) / 2;
        return html`<polyline class="gantt-dep" points="${x1},${y1} ${midX},${y1} ${midX},${y2} ${x2},${y2}"/>
          <polygon class="gantt-dep-arrow" points="${x2 - 6},${y2 - 3} ${x2},${y2} ${x2 - 6},${y2 + 3}"/>`;
      })).join("");
    }

    function labelsHTML(model) {
      return model.tasks.map((task) => html`
        <div class="gantt-label-row-wrap" data-search-result="pm-gantt">
          <button type="button" class="gantt-label-row" data-action="open-task" data-task-id="${task.id}">
            <span class="gantt-label-name">${task.milestone ? raw("◆ ") : ""}${task.name}</span>
            <small class="gantt-label-meta">${projectName(task.project)} · ${memberName(task.owner)}</small>
          </button>
          <div class="gantt-row-actions">
            <button type="button" class="pm-icon-btn" data-action="task-edit" data-task-id="${task.id}" title="${task.name} 작업 편집" aria-label="${task.name} 작업 편집">✎</button>
            <button type="button" class="pm-icon-btn pm-icon-btn-del" data-action="task-delete" data-task-id="${task.id}" title="${task.name} 작업 삭제" aria-label="${task.name} 작업 삭제">✕</button>
          </div>
        </div>
      `).join("");
    }

    function ganttChartHTML(model) {
      const summary = chartSummary(model);
      return html`
        <div class="gantt-labels">
          <div class="gantt-labels-head">작업</div>
          ${raw(labelsHTML(model))}
        </div>
        <div class="gantt-svg-wrap">
          <p id="ganttChartSummary" class="sr-only">${summary}. 왼쪽 목록과 SVG 작업 막대 모두 같은 작업 열기 동작을 제공합니다.</p>
          <svg class="gantt-svg" role="group" aria-labelledby="ganttChartSummary" viewBox="0 0 ${model.svgW} ${model.svgH}" preserveAspectRatio="none" style="height:${model.svgH}px; min-width:${model.svgW}px">
            ${raw(rowStripesHTML(model))}
            ${raw(monthLinesHTML(model))}
            ${raw(todayLineHTML(model))}
            ${raw(depLinesHTML(model))}
            ${raw(model.tasks.map((task, index) => taskShapeHTML(task, index, model)).join(""))}
          </svg>
        </div>
      `;
    }

    function renderGanttHTML(input) {
      const model = ganttViewModel(input);
      const isSearchEmpty = model.query && model.tasks.length === 0;
      const ganttContent = isSearchEmpty
        ? searchEmptyState("pm-gantt", "검색 결과가 없습니다", "작업명, 담당자, 프로젝트와 일치하는 간트 작업이 없습니다.")
        : ganttChartHTML(model);

      return html`
        <section class="kpis kpis-4">${raw(model.kpis.map((kpi) => kpiCard(kpi)).join(""))}</section>
        <section class="panel gantt-panel">
          ${raw(panelHead("간트 차트", null, html`<button type="button" class="primary-btn" data-action="task-add">+ 작업 추가</button>`))}
          <div class="gantt ${raw(isSearchEmpty ? "gantt-search-empty" : "")}">
            ${raw(ganttContent)}
          </div>
        </section>
      `;
    }

    return {
      version: VERSION,
      ganttViewModel,
      chartSummary,
      monthLinesHTML,
      todayLineHTML,
      taskShapeHTML,
      depLinesHTML,
      labelsHTML,
      ganttChartHTML,
      renderGanttHTML,
    };
  }

  root.JooParkGanttView = {
    version: VERSION,
    create: createGanttView,
  };
})(window);
