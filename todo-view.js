(function (root) {
  "use strict";

  const VERSION = "joopark-todo-view/v1";
  const DEFAULT_TODO_RENDER_LIMIT = 160;
  const DEFAULT_TODO_BUCKET_RENDER_LIMIT = 80;

  function renderLimitOption(value, fallback, minimum) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? Math.max(minimum, Math.trunc(parsed)) : fallback;
  }

  function createTodoView(deps) {
    const options = deps || {};
    const html = options.html;
    const raw = options.raw;
    const todoPriority = options.todoPriority || {};
    const todoPrioRank = options.todoPrioRank || {};
    const todoFilters = Array.isArray(options.todoFilters) ? options.todoFilters : [];
    const todoSourceFilters = Array.isArray(options.todoSourceFilters) ? options.todoSourceFilters : [];
    const dueLabel = typeof options.dueLabel === "function" ? options.dueLabel : function () { return { cls: "", text: "마감 없음" }; };
    const todayISO = typeof options.todayISO === "function" ? options.todayISO : function () { return ""; };
    const matches = typeof options.matches === "function" ? options.matches : function () { return true; };
    const formatKoreanShort = typeof options.formatKoreanShort === "function" ? options.formatKoreanShort : function (value) { return value || ""; };
    const kpiCard = typeof options.kpiCard === "function" ? options.kpiCard : function () { return ""; };
    const searchEmptyState = typeof options.searchEmptyState === "function" ? options.searchEmptyState : function () { return ""; };
    const todoRenderLimit = renderLimitOption(options.todoRenderLimit, DEFAULT_TODO_RENDER_LIMIT, 40);
    const todoBucketRenderLimit = renderLimitOption(options.todoBucketRenderLimit, DEFAULT_TODO_BUCKET_RENDER_LIMIT, 20);

    if (typeof html !== "function" || typeof raw !== "function") {
      throw new Error("todo view requires html and raw helpers");
    }

    function todoMatchesFilter(todo, filter) {
      const today = todayISO();
      switch (filter) {
        case "active": return !todo.done;
        case "today": return !todo.done && todo.due === today;
        case "upcoming": return !todo.done && todo.due && todo.due > today;
        case "done": return todo.done;
        default: return true;
      }
    }

    function todoMatchesSourceFilter(todo, sourceFilter) {
      const sourceKey = String(todo && todo.sourceKey || "");
      switch (sourceFilter) {
        case "wiki": return sourceKey.startsWith("llm-wiki:todo:");
        default: return true;
      }
    }

    function todoSourceReturnButton(todo) {
      const sourceKey = String(todo && todo.sourceKey || "");
      const prefix = "llm-wiki:todo:";
      if (!sourceKey.startsWith(prefix) || !sourceKey.slice(prefix.length)) return "";
      const title = todo && todo.title ? todo.title : "할 일";
      return html`
        <button type="button" class="local-source-badge local-source-wiki" data-action="open-llm-wiki-source" data-source-record-kind="todo" data-source-record-id="${todo.id}" data-source-key="${sourceKey}" data-source-article-id="${sourceKey.slice(prefix.length)}" title="LLM Wiki 원문 보기" aria-label="${title} LLM Wiki 원문 보기">LLM Wiki</button>
      `;
    }

    function todoRow(todo) {
      const dl = dueLabel(todo.due);
      const prio = todoPriority[todo.priority] || todoPriority.med || { label: "보통", color: "var(--cyan)" };
      return html`
        <div class="todo-row ${raw(todo.done ? "is-done" : "")} prio-${raw(todo.priority)}" data-search-result="todo">
          <button type="button" class="todo-check ${raw(todo.done ? "is-on" : "")}" data-action="todo-toggle" data-todo-id="${todo.id}" aria-label="${todo.title} ${todo.done ? "완료 취소" : "완료 처리"}">${raw(todo.done ? "✓" : "")}</button>
          <button type="button" class="todo-main" data-action="open-todo" data-todo-id="${todo.id}">
            <span class="todo-title">${todo.title}</span>
            <span class="todo-meta">
              <span class="todo-due ${raw(todo.done ? "" : dl.cls)}">${dl.text}</span>
              ${todo.category ? raw(html`<span class="todo-tag">${todo.category}</span>`) : ""}
              <span class="todo-prio" style="color:${raw(prio.color)}">${prio.label}</span>
            </span>
          </button>
          <span class="todo-row-actions">
            ${raw(todoSourceReturnButton(todo))}
            <button type="button" class="todo-del" data-action="todo-delete" data-todo-id="${todo.id}" aria-label="${todo.title} 삭제">✕</button>
          </span>
        </div>
      `;
    }

    function todoViewModel(todos, query, filter, sourceFilter) {
      const safeTodos = Array.isArray(todos) ? todos : [];
      const q = query || "";
      const today = todayISO();
      const base = safeTodos.filter((todo) => matches(`${todo.title} ${todo.category} ${todo.memo}`, q));
      const activeSourceFilter = sourceFilter || "all";
      const sourceCounts = {
        all: base.length,
        wiki: base.filter((todo) => todoMatchesSourceFilter(todo, "wiki")).length,
      };
      const sourceBase = base.filter((todo) => todoMatchesSourceFilter(todo, activeSourceFilter));
      const activeSourceLabel = (todoSourceFilters.find((item) => item.key === activeSourceFilter) || {}).label || "전체 출처";
      const open = sourceBase.filter((todo) => !todo.done);
      const overdue = open.filter((todo) => todo.due && todo.due < today);
      const dueToday = open.filter((todo) => todo.due === today);
      const doneCount = sourceBase.filter((todo) => todo.done).length;
      const total = sourceBase.length;
      const rate = total ? Math.round((doneCount / total) * 100) : 0;
      const kpis = [
        { title: "미완료", value: String(open.length), unit: "건", color: "#22d3ee", badge: "☑", delta: total ? `전체 ${total}건` : "" },
        { title: "오늘 마감", value: String(dueToday.length), unit: "건", color: "#2387ff", badge: "◷", delta: formatKoreanShort(today) },
        { title: "기한 지남", value: String(overdue.length), unit: "건", color: overdue.length ? "#ff4d5e" : "#17d983", badge: "⚑", delta: overdue.length ? "지금 처리" : "없음", trendDown: overdue.length > 0 },
        { title: "완료율", value: String(rate), unit: "%", color: "#17d983", badge: "✓", delta: `완료 ${doneCount}건` },
      ];

      const filtered = sourceBase.filter((todo) => todoMatchesFilter(todo, filter));
      filtered.sort((a, b) => {
        if (a.done !== b.done) return a.done ? 1 : -1;
        const ad = a.due || "9999-99-99";
        const bd = b.due || "9999-99-99";
        if (ad !== bd) return ad < bd ? -1 : 1;
        return (todoPrioRank[a.priority] ?? 1) - (todoPrioRank[b.priority] ?? 1);
      });

      return {
        q,
        today,
        kpis,
        filtered,
        filter,
        sourceFilter: activeSourceFilter,
        sourceCounts,
        activeSourceLabel,
      };
    }

    function todoListHTML(model) {
      const q = model.q;
      const filtered = model.filtered;
      if (filtered.length === 0) {
        return q
          ? searchEmptyState("todo", "검색 결과가 없습니다", `“${q}”와 일치하는 할 일을 찾지 못했습니다. 검색어를 지우거나 새 할 일을 바로 추가하세요.`)
          : model.sourceFilter !== "all"
            ? html`
              <article class="empty empty-action" data-todo-source-empty="${model.sourceFilter}">
                <strong>${model.activeSourceLabel} 할 일이 없습니다</strong>
                <span>출처 필터를 전체로 돌리면 모든 로컬 할 일을 다시 볼 수 있습니다.</span>
                <button type="button" class="secondary-btn" data-action="todo-source-filter" data-todo-source-filter="all">전체 출처 보기</button>
              </article>
            `
          : html`
            <article class="empty empty-action">
              <strong>아직 할 일이 없습니다</strong>
              <span>위 입력창에서 첫 할 일을 추가하면 미완료, 오늘, 예정 상태로 자동 정리됩니다.</span>
            </article>
          `;
      }

      function todoVirtualNote(total, rendered, scope) {
        const hidden = total - rendered;
        if (hidden <= 0) return "";
        return html`
          <div class="virtual-list-note todo-virtual-note" role="status" data-todo-virtualized="true" data-todo-virtual-scope="${scope}" data-todo-virtual-rendered="${rendered}" data-todo-virtual-total="${total}">
            <strong>${hidden}개 더 있음</strong>
            <span>검색어·상태·출처 필터를 좁히면 숨겨진 할 일을 바로 찾을 수 있습니다.</span>
          </div>
        `;
      }

      if (model.filter === "active") {
        const today = model.today;
        const buckets = [
          { label: "기한 지남", items: filtered.filter((todo) => todo.due && todo.due < today) },
          { label: "오늘", items: filtered.filter((todo) => todo.due === today) },
          { label: "예정", items: filtered.filter((todo) => todo.due && todo.due > today) },
          { label: "기한 없음", items: filtered.filter((todo) => !todo.due) },
        ].filter((bucket) => bucket.items.length);
        return buckets.map((bucket) => html`
          <div class="todo-group">
            <p class="todo-group-head">${bucket.label} <span>${bucket.items.length}</span></p>
            ${raw(bucket.items.slice(0, todoBucketRenderLimit).map((todo) => todoRow(todo)).join(""))}
            ${raw(todoVirtualNote(bucket.items.length, Math.min(bucket.items.length, todoBucketRenderLimit), bucket.label))}
          </div>
        `).join("");
      }

      const visible = filtered.length > todoRenderLimit ? filtered.slice(0, todoRenderLimit) : filtered;
      return html`
        <div class="todo-group">
          ${raw(visible.map((todo) => todoRow(todo)).join(""))}
          ${raw(todoVirtualNote(filtered.length, visible.length, "all"))}
        </div>
      `;
    }

    function todoFilterChipsHTML(activeFilter) {
      return todoFilters.map((filter) => html`
        <button type="button" class="seg-chip ${raw(activeFilter === filter.key ? "is-active" : "")}" data-action="todo-filter" data-filter="${filter.key}" aria-pressed="${raw(activeFilter === filter.key ? "true" : "false")}">${filter.label}</button>
      `).join("");
    }

    function todoSourceFilterChipsHTML(model) {
      if (!model || (model.sourceCounts.wiki === 0 && model.sourceFilter === "all")) return "";
      return html`
        <div class="seg-control source-filter-control" data-todo-source-filterbar data-todo-source-filter-current="${model.sourceFilter}">
          ${raw(todoSourceFilters.map((filter) => {
            const count = model.sourceCounts[filter.key] || 0;
            return html`
              <button type="button" class="seg-chip ${raw(model.sourceFilter === filter.key ? "is-active" : "")}" data-action="todo-source-filter" data-todo-source-filter="${filter.key}" data-todo-source-filter-count="${count}" aria-pressed="${raw(model.sourceFilter === filter.key ? "true" : "false")}">${filter.label} <span>${count}</span></button>
            `;
          }).join(""))}
        </div>
      `;
    }

    function renderTodosHTML(input) {
      const model = todoViewModel(input && input.todos, input && input.query, input && input.filter, input && input.sourceFilter);
      return html`
        <section class="kpis kpis-4">${raw(model.kpis.map((kpi) => kpiCard(kpi)).join(""))}</section>
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
          <div class="seg-control">${raw(todoFilterChipsHTML(input && input.filter))}</div>
          ${raw(todoSourceFilterChipsHTML(model))}
          <div class="todo-list">${raw(todoListHTML(model))}</div>
        </section>
      `;
    }

    return {
      version: VERSION,
      todoMatchesFilter,
      todoMatchesSourceFilter,
      todoSourceReturnButton,
      renderLimitOption,
      todoRow,
      todoViewModel,
      todoListHTML,
      todoFilterChipsHTML,
      todoSourceFilterChipsHTML,
      renderTodosHTML,
    };
  }

  root.JooParkTodoView = {
    version: VERSION,
    create: createTodoView,
  };
})(window);
