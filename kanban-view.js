(function (root) {
  "use strict";

  const VERSION = "joopark-kanban-view/v1";
  const DEFAULT_STATUS_ORDER = ["todo", "in-progress", "review", "done"];
  const DEFAULT_PRIORITY_ORDER = ["crit", "high", "med", "low"];
  const DEFAULT_STATUS_LABELS = { todo: "To Do", "in-progress": "In Progress", review: "Review", done: "Done" };
  const DEFAULT_PRIORITY_LABELS = { crit: "Critical", high: "High", med: "Medium", low: "Low" };
  const SOURCE_FILTER_OPTIONS = [
    { key: "all", label: "전체" },
    { key: "wiki", label: "LLM Wiki" },
    { key: "db", label: "DB Catalog" },
    { key: "review", label: "Review" },
    { key: "workspace-review", label: "Workspace" },
    { key: "kb-ia-review", label: "KB/IA" },
    { key: "benchmark-review", label: "PM Bench" },
    { key: "source", label: "Source" },
  ];
  const STATUS_COLORS = {
    todo: "#7f91ad",
    "in-progress": "#22d3ee",
    review: "#a970ff",
    done: "#17d983",
  };
  const STATUS_BADGES = {
    todo: "○",
    "in-progress": "◑",
    review: "◐",
    done: "✓",
  };
  const DEFAULT_COLUMN_RENDER_LIMIT = 80;

  function renderLimitOption(value, fallback = DEFAULT_COLUMN_RENDER_LIMIT, minimum = 20) {
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) return fallback;
    return Math.max(minimum, Math.trunc(parsed));
  }

  function createKanbanView(deps) {
    const options = deps || {};
    const html = options.html;
    const raw = options.raw;
    const matches = typeof options.matches === "function" ? options.matches : function () { return true; };
    const kpiCard = typeof options.kpiCard === "function" ? options.kpiCard : function () { return ""; };
    const panelHead = typeof options.panelHead === "function" ? options.panelHead : function (title) { return html`<div class="panel-head"><h2>${title}</h2></div>`; };
    const searchEmptyState = typeof options.searchEmptyState === "function" ? options.searchEmptyState : function () { return ""; };
    const memberName = typeof options.memberName === "function" ? options.memberName : function (id) { return id || "미지정"; };
    const projectName = typeof options.projectName === "function" ? options.projectName : function (id) { return id || "프로젝트"; };
    const formatMonthDay = typeof options.formatMonthDay === "function" ? options.formatMonthDay : function (value) { return value || ""; };
    const issueExecutionChecklistItems = typeof options.issueExecutionChecklistItems === "function" ? options.issueExecutionChecklistItems : function () { return []; };
    const issueExecutionChecklistProgress = typeof options.issueExecutionChecklistProgress === "function" ? options.issueExecutionChecklistProgress : function () { return { done: 0, total: 0, percent: 0 }; };
    const statusLabels = options.statusLabels || DEFAULT_STATUS_LABELS;
    const priorityLabels = options.priorityLabels || DEFAULT_PRIORITY_LABELS;
    const statusOrder = Array.isArray(options.statusOrder) ? options.statusOrder : DEFAULT_STATUS_ORDER;
    const priorityOrder = Array.isArray(options.priorityOrder) ? options.priorityOrder : DEFAULT_PRIORITY_ORDER;
    const columnRenderLimit = renderLimitOption(options.columnRenderLimit);

    if (typeof html !== "function" || typeof raw !== "function") {
      throw new Error("kanban view requires html and raw helpers");
    }

    const labelObjectKeys = ["label", "name", "title", "value", "key", "id"];

    function scalarLabelText(value) {
      if (value === null || value === undefined) return "";
      if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
        return String(value).replace(/\s+/g, " ").trim();
      }
      return "";
    }

    function labelText(value) {
      const direct = scalarLabelText(value);
      if (direct) return direct;
      if (!value || typeof value !== "object") return "";
      for (const key of labelObjectKeys) {
        const nested = scalarLabelText(value[key]);
        if (nested) return nested;
      }
      return "";
    }

    function safeLabels(issue) {
      const source = issue && Array.isArray(issue.labels) ? issue.labels : [];
      const seen = new Set();
      const labels = [];
      source.forEach((item) => {
        const label = labelText(item).slice(0, 40).trim();
        const key = label.toLowerCase();
        if (!label || seen.has(key)) return;
        seen.add(key);
        labels.push(label);
      });
      return labels.slice(0, 12);
    }

    function nextStatusMap() {
      return statusOrder.reduce((acc, status, index) => {
        acc[status] = statusOrder[(index + 1) % statusOrder.length];
        return acc;
      }, {});
    }

    function prevStatusMap() {
      return statusOrder.reduce((acc, status, index) => {
        acc[status] = statusOrder[(index - 1 + statusOrder.length) % statusOrder.length];
        return acc;
      }, {});
    }

    function issueOrderValue(issue, fallbackIndex) {
      const order = Number(issue && issue.order);
      return Number.isFinite(order) ? order : (Number(fallbackIndex) + 1) * 1000;
    }

    function compareIssueEntries(a, b) {
      const orderDiff = issueOrderValue(a.issue, a.index) - issueOrderValue(b.issue, b.index);
      if (orderDiff !== 0) return orderDiff;
      return a.index - b.index;
    }

    function issueSourceDescriptor(issue) {
      const sourceKind = String(issue && issue.sourceKind || "").trim();
      const sourceKey = String(issue && issue.sourceKey || "").trim();
      const sourceMap = {
        "llm-wiki-action": { label: "LLM Wiki", fullLabel: "LLM Wiki", tone: "wiki" },
        "db-catalog-stale-review": { label: "DB Catalog", fullLabel: "DB Catalog", tone: "db" },
        "validated-review-result": { label: "Review", fullLabel: "Review", tone: "review" },
      };
      if (sourceKey.startsWith("workspace-review:")) return { label: "Workspace", fullLabel: "Workspace Review", tone: "review" };
      if (sourceKey.startsWith("kb-ia-review:")) return { label: "KB/IA", fullLabel: "KB/IA Review", tone: "review" };
      if (sourceKey.startsWith("benchmark-review:")) return { label: "PM Bench", fullLabel: "PM Bench Review", tone: "review" };
      if (sourceMap[sourceKind]) return sourceMap[sourceKind];
      if (sourceKind || sourceKey) return { label: "Source", fullLabel: "Source", tone: "source" };
      return { label: "", fullLabel: "", tone: "none" };
    }

    function issueMatches(issue, query) {
      if (!query) return true;
      const source = issueSourceDescriptor(issue);
      return matches(`${issue.id} ${issue.title} ${issue.assignee} ${safeLabels(issue).join(" ")} ${source.label} ${source.fullLabel}`, query);
    }

    function normalizeSourceFilter(value) {
      return SOURCE_FILTER_OPTIONS.some((option) => option.key === value) ? value : "all";
    }

    function sourceFilterLabel(value) {
      const option = SOURCE_FILTER_OPTIONS.find((item) => item.key === value);
      return option ? option.label : "Source";
    }

    function issueMatchesSourceFilter(issue, sourceFilter) {
      if (sourceFilter === "all") return true;
      const sourceKey = String(issue && issue.sourceKey || "").trim();
      if (sourceFilter === "workspace-review") return sourceKey.startsWith("workspace-review:");
      if (sourceFilter === "kb-ia-review") return sourceKey.startsWith("kb-ia-review:");
      if (sourceFilter === "benchmark-review") return sourceKey.startsWith("benchmark-review:");
      return issueSourceDescriptor(issue).tone === sourceFilter;
    }

    function issueMatchesPreparedSourceFilter(entry, sourceFilter) {
      if (sourceFilter === "all") return true;
      if (sourceFilter === "workspace-review") return entry.sourceKey.startsWith("workspace-review:");
      if (sourceFilter === "kb-ia-review") return entry.sourceKey.startsWith("kb-ia-review:");
      if (sourceFilter === "benchmark-review") return entry.sourceKey.startsWith("benchmark-review:");
      return entry.source.tone === sourceFilter;
    }

    const nextStatusByStatus = nextStatusMap();
    const prevStatusByStatus = prevStatusMap();

    function kanbanViewModel(input) {
      const data = input || {};
      const issues = Array.isArray(data.issues) ? data.issues : [];
      const currentProjectId = data.currentProjectId || "";
      const query = data.query || "";
      const filter = data.filter || "";
      const sourceFilter = normalizeSourceFilter(data.sourceFilter);
      const density = data.density === "compact" ? "compact" : "comfortable";
      const sourceCounts = SOURCE_FILTER_OPTIONS.reduce((acc, option) => {
        acc[option.key] = 0;
        return acc;
      }, {});
      const selectedEntries = issues.slice(0, 0);
      for (let index = 0; index < issues.length; index += 1) {
        const issue = issues[index];
        if (!issue || issue.project !== currentProjectId) continue;
        if (filter && issue.priority !== filter) continue;
        if (!issueMatches(issue, query)) continue;
        const entry = {
          issue,
          index,
          source: issueSourceDescriptor(issue),
          sourceKey: String(issue.sourceKey || "").trim(),
        };
        sourceCounts.all += 1;
        for (const option of SOURCE_FILTER_OPTIONS) {
          if (option.key !== "all" && issueMatchesPreparedSourceFilter(entry, option.key)) {
            sourceCounts[option.key] += 1;
          }
        }
        if (issueMatchesPreparedSourceFilter(entry, sourceFilter)) selectedEntries.push(entry);
      }
      const all = selectedEntries.sort(compareIssueEntries).map((entry) => entry.issue);
      const counts = statusOrder.reduce((acc, status) => {
        acc[status] = 0;
        return acc;
      }, {});
      all.forEach((issue) => {
        counts[issue.status] = (counts[issue.status] || 0) + 1;
      });
      const kpis = statusOrder.map((status) => ({
        title: statusLabels[status],
        value: String(counts[status] || 0),
        unit: "건",
        color: STATUS_COLORS[status] || "var(--cyan)",
        badge: STATUS_BADGES[status] || "○",
        delta: "",
      }));
      return {
        issues,
        currentProjectId,
        query,
        filter,
        sourceFilter,
        sourceCounts,
        density,
        all,
        counts,
        kpis,
        nextStatus: { ...nextStatusByStatus },
        prevStatus: { ...prevStatusByStatus },
      };
    }

    function filterChipsHTML(model) {
      return priorityOrder.map((priority) => html`
        <button type="button" class="kanban-chip priority-${raw(priority)} ${raw(model.filter === priority ? "is-active" : "")}" data-action="filter-kanban" data-priority="${priority}" aria-pressed="${raw(model.filter === priority ? "true" : "false")}" aria-label="${priorityLabels[priority]} 우선순위 필터">${priorityLabels[priority]}</button>
      `).join("");
    }

    function sourceFilterHTML(model) {
      return html`
        <div class="kanban-source-filterbar" role="group" aria-label="Kanban source filter" data-kanban-source-filterbar data-kanban-source-filter-current="${model.sourceFilter}">
          ${raw(SOURCE_FILTER_OPTIONS.map((option) => html`
            <button type="button" class="kanban-source-chip ${raw(model.sourceFilter === option.key ? "is-active" : "")}" data-action="filter-kanban-source" data-kanban-source-filter="${option.key}" aria-pressed="${model.sourceFilter === option.key}">
              <span>${option.label}</span>
              <b>${model.sourceCounts[option.key] || 0}</b>
            </button>
          `).join(""))}
        </div>
      `;
    }

    function densityToggleHTML(model) {
      const options = [
        { key: "comfortable", label: "표준" },
        { key: "compact", label: "압축" },
      ];
      return html`
        <div class="kanban-density-toggle" role="group" aria-label="Kanban card density" data-kanban-density-toggle data-kanban-density-current="${model.density}">
          ${raw(options.map((option) => html`
            <button type="button" class="kanban-density-btn ${raw(model.density === option.key ? "is-active" : "")}" data-action="kanban-density" data-kanban-density="${option.key}" aria-pressed="${model.density === option.key}">
              ${option.label}
            </button>
          `).join(""))}
        </div>
      `;
    }

    function issueExecutionHTML(issue) {
      const executionChecklist = issueExecutionChecklistItems(issue);
      if (!executionChecklist.length) return "";
      const executionProgress = issueExecutionChecklistProgress(issue);
      const firstExecutionItem = executionChecklist.find((item) => !item.done) || executionChecklist[0];
      return html`
        <div class="kanban-execution-checklist" data-kanban-execution-checklist data-execution-checklist-count="${executionProgress.total}" data-execution-checklist-completed="${executionProgress.done}" data-execution-checklist-done-count="${executionProgress.done}" data-execution-checklist-progress="${executionProgress.percent}" data-execution-checklist-progress-percent="${executionProgress.percent}">
          <span class="kanban-execution-count">실행 ${executionProgress.done}/${executionProgress.total}</span>
          <span class="kanban-execution-meter" aria-hidden="true"><i style="width:${executionProgress.percent}%"></i></span>
          <span class="kanban-execution-first">${executionProgress.done === executionProgress.total ? "모든 실행 항목 완료" : firstExecutionItem.text}</span>
          <label class="kanban-execution-toggle ${raw(firstExecutionItem.done ? "is-done" : "")}" data-kanban-execution-toggle-row data-checklist-id="${firstExecutionItem.id}">
            <input type="checkbox" data-action="toggle-issue-checklist" data-issue-id="${issue.id}" data-checklist-id="${firstExecutionItem.id}" data-kanban-execution-toggle data-execution-checklist-toggle ${raw(firstExecutionItem.done ? "checked" : "")} />
            <span>${firstExecutionItem.done ? "완료됨" : "다음 항목 완료"}</span>
          </label>
        </div>
      `;
    }

    function issueSourceBadgeHTML(issue) {
      const sourceKind = String(issue.sourceKind || "").trim();
      const sourceKey = String(issue.sourceKey || "").trim();
      if (!sourceKind && !sourceKey) return "";
      const source = issueSourceDescriptor(issue);
      const canReturnToSource = sourceKind === "llm-wiki-action"
        || sourceKind === "db-catalog-stale-review"
        || sourceKey === "db-catalog:stale-sample-review"
        || sourceKey.startsWith("workspace-review:")
        || sourceKey.startsWith("kb-ia-review:")
        || sourceKey.startsWith("benchmark-review:");
      const fullLabel = source.fullLabel || source.label;
      if (!canReturnToSource) {
        return html`<span class="kanban-source-badge kanban-source-${raw(source.tone)}" data-kanban-source-kind="${sourceKind}" data-kanban-source-key="${sourceKey}" data-kanban-source-label="${source.label}" data-kanban-source-full-label="${fullLabel}">${source.label}</span>`;
      }
      return html`<button type="button" class="kanban-source-badge kanban-source-${raw(source.tone)}" data-action="open-issue-source" data-issue-id="${issue.id}" data-kanban-source-kind="${sourceKind}" data-kanban-source-key="${sourceKey}" data-kanban-source-label="${source.label}" data-kanban-source-full-label="${fullLabel}" data-kanban-source-direct-return="true" title="${fullLabel} 원문 보기" aria-label="${issue.id} ${fullLabel} 원문 보기">${source.label}</button>`;
    }

    function issueCard(issue, model) {
      const prevStatus = model.prevStatus[issue.status];
      const nextStatus = model.nextStatus[issue.status];
      const order = issueOrderValue(issue, 0);
      const labels = safeLabels(issue)
        .map((label) => html`<span class="kanban-label" data-kanban-label="${label}" title="Kanban label: ${label}" aria-label="Kanban label ${label}">#${label}</span>`)
        .join("");
      return html`
        <div class="kanban-card-wrap" draggable="true" tabindex="0" data-issue-id="${issue.id}" data-issue-status="${issue.status}" data-issue-order="${order}" data-issue-source-kind="${issue.sourceKind || ""}" data-issue-source-key="${issue.sourceKey || ""}" data-kanban-card-density="${model.density}" data-search-result="pm-kanban" role="listitem" aria-label="${issue.id} ${issue.title} Kanban 카드">
          <div class="kanban-card priority-${raw(issue.priority)}">
            <div class="kanban-card-head">
              <span class="kanban-id">${issue.id}</span>
              <div class="kanban-card-head-right">
                ${raw(issueSourceBadgeHTML(issue))}
                <span class="kanban-priority priority-${raw(issue.priority)}">${priorityLabels[issue.priority] || issue.priority}</span>
                <div class="pm-card-actions">
                  <button type="button" class="pm-icon-btn" data-action="issue-edit" data-issue-id="${issue.id}" title="${issue.id} 이슈 편집" aria-label="${issue.id} 이슈 편집">✎</button>
                  <button type="button" class="pm-icon-btn pm-icon-btn-del" data-action="issue-delete" data-issue-id="${issue.id}" title="${issue.id} 이슈 삭제" aria-label="${issue.id} 이슈 삭제">✕</button>
                </div>
              </div>
            </div>
            <button type="button" class="kanban-title-btn" data-action="open-issue" data-issue-id="${issue.id}" aria-label="${issue.id} ${issue.title} 이슈 열기">
              <strong class="kanban-title">${issue.title}</strong>
            </button>
            <div class="kanban-card-foot">
              <span class="kanban-assignee">${memberName(issue.assignee)}</span>
              <span class="kanban-due">${issue.due ? formatMonthDay(issue.due) : "—"}</span>
            </div>
            ${raw(issueExecutionHTML(issue))}
            <div class="kanban-labels">${raw(labels)}</div>
            <div class="kanban-move-btns">
              <button type="button" class="kanban-move-btn" data-action="issue-order" data-issue-id="${issue.id}" data-position="top" title="맨 위로" aria-label="${issue.id} 이슈를 현재 컬럼 맨 위로 이동">⇧</button>
              <button type="button" class="kanban-move-btn" data-action="issue-move" data-issue-id="${issue.id}" data-status="${prevStatus}" title="◀ ${statusLabels[prevStatus]}" aria-label="${issue.id} 이슈를 ${statusLabels[prevStatus]}로 이동">◀</button>
              <button type="button" class="kanban-move-btn" data-action="issue-move" data-issue-id="${issue.id}" data-status="${nextStatus}" title="▶ ${statusLabels[nextStatus]}" aria-label="${issue.id} 이슈를 ${statusLabels[nextStatus]}로 이동">▶</button>
              <button type="button" class="kanban-move-btn" data-action="issue-order" data-issue-id="${issue.id}" data-position="bottom" title="맨 아래로" aria-label="${issue.id} 이슈를 현재 컬럼 맨 아래로 이동">⇩</button>
            </div>
          </div>
        </div>
      `;
    }

    function kanbanColumn(status, model) {
      const items = model.all.filter((issue) => issue.status === status);
      const visibleItems = items.length > columnRenderLimit ? items.slice(0, columnRenderLimit) : items;
      const hiddenCount = items.length - visibleItems.length;
      const body = items.length === 0
        ? html`<div class="kanban-empty" data-kanban-drop="${status}">없음</div>`
        : html`
          ${raw(visibleItems.map((issue) => issueCard(issue, model)).join(""))}
          ${hiddenCount > 0 ? raw(html`
            <div class="virtual-list-note kanban-virtual-note" role="status" data-kanban-virtualized="true" data-kanban-virtual-status="${status}" data-kanban-virtual-rendered="${visibleItems.length}" data-kanban-virtual-total="${items.length}">
              <strong>${hiddenCount}개 더 있음</strong>
              <span>검색·출처·우선순위 필터를 좁히면 숨겨진 이슈를 바로 찾을 수 있습니다.</span>
            </div>
          `) : ""}
        `;
      return html`
        <div class="kanban-col" data-kanban-col="${status}" data-kanban-rendered-count="${visibleItems.length}" data-kanban-total-count="${items.length}" role="region" aria-label="${statusLabels[status]} 컬럼, ${items.length}개 이슈">
          <div class="kanban-col-head">
            <strong>${statusLabels[status]}</strong>
            <div class="kanban-col-head-right">
              <span class="kanban-count">${items.length}</span>
              <button type="button" class="kanban-add-btn" data-action="issue-add" title="${statusLabels[status]}에 이슈 추가" aria-label="${statusLabels[status]}에 이슈 추가">+</button>
            </div>
          </div>
          <div class="kanban-list" data-kanban-drop="${status}" role="list" aria-label="${statusLabels[status]} 이슈 목록">
            ${raw(body)}
          </div>
        </div>
      `;
    }

    function sourceFilterEmptyHTML(model) {
      const label = sourceFilterLabel(model.sourceFilter);
      return html`
        <div class="kanban-source-empty" role="status" data-kanban-source-empty data-kanban-source-empty-filter="${model.sourceFilter}" data-kanban-source-empty-label="${label}">
          <strong>${label} 이슈가 없습니다</strong>
          <p>현재 프로젝트와 검색/우선순위 조건에서 이 출처의 Kanban 카드가 없습니다.</p>
          <button type="button" class="kanban-source-empty-clear" data-action="filter-kanban-source" data-kanban-source-filter="all">전체 출처 보기</button>
        </div>
      `;
    }

    function sourceFilterSummaryHTML(model) {
      if (model.sourceFilter === "all") return "";
      const label = sourceFilterLabel(model.sourceFilter);
      return html`
        <div class="kanban-source-summary" role="status" data-kanban-source-summary data-kanban-source-summary-filter="${model.sourceFilter}" data-kanban-source-summary-label="${label}" data-kanban-source-summary-count="${model.all.length}">
          <span><strong>${label}</strong> 출처만 표시 중</span>
          <b>${model.all.length}건</b>
          <button type="button" class="kanban-source-summary-clear" data-action="filter-kanban-source" data-kanban-source-filter="all">전체 출처 보기</button>
        </div>
      `;
    }

    function kanbanBoardHTML(model) {
      const isSearchEmpty = model.query && model.sourceCounts.all === 0;
      const isSourceEmpty = model.sourceFilter !== "all" && model.all.length === 0 && !isSearchEmpty;
      const content = isSearchEmpty
        ? searchEmptyState("pm-kanban", "검색 결과가 없습니다", "이슈 ID, 제목, 담당자, 라벨과 일치하는 Kanban 카드가 없습니다.")
        : isSourceEmpty
          ? sourceFilterEmptyHTML(model)
        : statusOrder.map((status) => kanbanColumn(status, model)).join("");
      return html`<div class="kanban kanban-density-${raw(model.density)} ${raw(isSearchEmpty ? "kanban-search-empty" : "")} ${raw(isSourceEmpty ? "kanban-source-filter-empty" : "")}" id="kanbanBoard" data-kanban-density="${model.density}">${raw(content)}</div>`;
    }

    function renderKanbanHTML(input) {
      const model = kanbanViewModel(input);
      return html`
        <section class="kpis kpis-4">${raw(model.kpis.map((kpi) => kpiCard(kpi)).join(""))}</section>
        <section class="panel kanban-panel">
          ${raw(panelHead(`Kanban — ${projectName(model.currentProjectId)}`, null, html`
            <div class="kanban-filters">
              <span class="kanban-filters-label">우선순위</span>
              ${raw(filterChipsHTML(model))}
              ${model.filter ? raw(html`<button type="button" class="kanban-chip-clear" data-action="filter-kanban" data-priority="">해제</button>`) : ""}
              ${raw(sourceFilterHTML(model))}
              ${raw(densityToggleHTML(model))}
              <button type="button" class="primary-btn kanban-global-add" data-action="issue-add">+ 이슈</button>
            </div>
          `))}
          ${raw(sourceFilterSummaryHTML(model))}
          ${raw(kanbanBoardHTML(model))}
        </section>
      `;
    }

    return {
      version: VERSION,
      kanbanViewModel,
      filterChipsHTML,
      sourceFilterHTML,
      densityToggleHTML,
      issueExecutionHTML,
      sourceFilterEmptyHTML,
      sourceFilterSummaryHTML,
      issueCard,
      kanbanColumn,
      kanbanBoardHTML,
      renderKanbanHTML,
      renderLimitOption,
    };
  }

  root.JooParkKanbanView = {
    version: VERSION,
    create: createKanbanView,
  };
})(window);
