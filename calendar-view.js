(function (root) {
  "use strict";

  const VERSION = "joopark-calendar-view/v1";

  function createCalendarView(deps) {
    const options = deps || {};
    const html = options.html;
    const raw = options.raw;
    const eventCats = options.eventCats || {};
    const eventCatOrder = Array.isArray(options.eventCatOrder) ? options.eventCatOrder : [];
    const weekdaysKo = Array.isArray(options.weekdaysKo) ? options.weekdaysKo : [];
    const todayISO = typeof options.todayISO === "function" ? options.todayISO : function () { return ""; };
    const ymToDate = typeof options.ymToDate === "function" ? options.ymToDate : function () { return new Date(); };
    const ymd = typeof options.ymd === "function" ? options.ymd : function () { return ""; };
    const matches = typeof options.matches === "function" ? options.matches : function () { return true; };
    const expandOccurrences = typeof options.expandOccurrences === "function" ? options.expandOccurrences : function () { return []; };
    const eventsOn = typeof options.eventsOn === "function" ? options.eventsOn : function () { return []; };
    const addDaysISO = typeof options.addDaysISO === "function" ? options.addDaysISO : function (value) { return value; };
    const isTodayISO = typeof options.isTodayISO === "function" ? options.isTodayISO : function () { return false; };
    const formatKoreanShort = typeof options.formatKoreanShort === "function" ? options.formatKoreanShort : function (value) { return value || ""; };
    const formatKoreanFull = typeof options.formatKoreanFull === "function" ? options.formatKoreanFull : function (value) { return value || ""; };
    const eventTimeLabel = typeof options.eventTimeLabel === "function" ? options.eventTimeLabel : function () { return ""; };
    const kpiCard = typeof options.kpiCard === "function" ? options.kpiCard : function () { return ""; };
    const searchEmptyState = typeof options.searchEmptyState === "function" ? options.searchEmptyState : function () { return ""; };

    if (typeof html !== "function" || typeof raw !== "function") {
      throw new Error("calendar view requires html and raw helpers");
    }

    function categoryMeta(category) {
      return eventCats[category] || eventCats.etc || { label: "기타", color: "var(--cyan)" };
    }

    function parseISODate(value) {
      const [year, month, day] = String(value || "").split("-").map(Number);
      if (!year || !month || !day) return new Date();
      return new Date(year, month - 1, day);
    }

    function weekStartISO(value) {
      const date = parseISODate(value);
      return addDaysISO(ymd(date), -date.getDay());
    }

    function validMode(value) {
      return ["month", "week", "day"].includes(value) ? value : "month";
    }

    function modeLabel(mode) {
      if (mode === "week") return "주";
      if (mode === "day") return "일";
      return "월";
    }

    function calLegend() {
      return html`<div class="sched-legend">${eventCatOrder.map((key) => raw(html`
        <span><i style="background:${raw(categoryMeta(key).color)}"></i>${categoryMeta(key).label}</span>
      `))}</div>`;
    }

    function eventRow(event, opts) {
      const compact = opts && opts.compact;
      const searchResult = opts && opts.searchResult;
      const category = categoryMeta(event.category);
      const openId = event._masterId || event.id;
      const isRecurring = event._occ && (event.repeat && event.repeat !== "none");
      const skipBtn = (opts && opts.showSkip && isRecurring)
        ? html`<button type="button" class="agenda-skip" data-action="skip-occurrence" data-event-id="${event._masterId}" data-date="${event.date}" title="이 날짜 건너뛰기" aria-label="이 날짜 건너뛰기">건너뛰기</button>`
        : "";
      return html`
        <div class="agenda-item-wrap">
          <button type="button" class="agenda-item" data-action="open-event" data-event-id="${openId}" ${raw(searchResult ? `data-search-result="${searchResult}"` : "")}>
            <span class="agenda-bar" style="background:${raw(category.color)}"></span>
            <span class="agenda-time">${eventTimeLabel(event)}</span>
            <span class="agenda-body">
              <strong>${event.title}</strong>
              ${isRecurring ? raw(html`<span class="agenda-recur-icon" title="반복 일정">↺</span>`) : ""}
              ${event.location || (!compact && event.memo) ? raw(html`<small>${[event.location, compact ? "" : event.memo].filter(Boolean).join(" · ")}</small>`) : ""}
            </span>
            <span class="agenda-cat" style="color:${raw(category.color)}">${category.label}</span>
          </button>${raw(skipBtn)}
        </div>
      `;
    }

    function calendarViewModel(input) {
      const data = input || {};
      const events = Array.isArray(data.events) ? data.events : [];
      const todos = Array.isArray(data.todos) ? data.todos : [];
      const q = (data.query || "").trim();
      const ym = data.month || "";
      const mode = validMode(data.mode);
      const selectedDate = data.selected || todayISO();
      const first = ymToDate(ym);
      const year = first.getFullYear();
      const month = first.getMonth();
      const firstWeekday = first.getDay();
      const gridStart = new Date(year, month, 1 - firstWeekday);
      const today = todayISO();
      const monthStart = `${ym}-01`;
      const monthEnd = (() => {
        const parts = ym.split("-").map(Number);
        const lastDay = new Date(parts[0], parts[1], 0).getDate();
        return `${ym}-${String(lastDay).padStart(2, "0")}`;
      })();
      const weekStart = weekStartISO(selectedDate);
      const weekEnd = addDaysISO(weekStart, 6);
      const rangeStart = mode === "week" ? weekStart : mode === "day" ? selectedDate : monthStart;
      const rangeEnd = mode === "week" ? weekEnd : mode === "day" ? selectedDate : monthEnd;
      const rangeTitle = mode === "week"
        ? `${formatKoreanShort(weekStart)} - ${formatKoreanShort(weekEnd)}`
        : mode === "day"
          ? formatKoreanFull(selectedDate)
          : `${year}년 ${month + 1}월`;
      const matchedIds = new Set(
        events
          .filter((event) => matches(`${event.title} ${event.memo} ${event.location} ${categoryMeta(event.category).label}`, q))
          .map((event) => event.id)
      );
      const monthOccurrences = expandOccurrences(monthStart, monthEnd);
      const visibleMonthOccurrences = q
        ? monthOccurrences.filter((event) => matchedIds.has(event._masterId || event.id))
        : monthOccurrences;
      const rangeOccurrences = expandOccurrences(rangeStart, rangeEnd);
      const visibleRangeOccurrences = q
        ? rangeOccurrences.filter((event) => matchedIds.has(event._masterId || event.id))
        : rangeOccurrences;
      const todayCount = eventsOn(today).length;
      const upcomingDeadlines = expandOccurrences(today, addDaysISO(today, 365))
        .filter((event) => event.category === "deadline").length;
      const kpis = [
        { title: "이번 달 일정", value: String(monthOccurrences.length), unit: "건", color: "#2387ff", badge: "▦", delta: `${weekdaysKo[new Date().getDay()] || ""}요일` },
        { title: "오늘 일정", value: String(todayCount), unit: "건", color: "#17d983", badge: "◷", delta: formatKoreanShort(today) },
        { title: "다가오는 마감", value: String(upcomingDeadlines), unit: "건", color: upcomingDeadlines ? "#ff4d5e" : "#17d983", badge: "⚑", delta: upcomingDeadlines ? "확인 필요" : "여유", trendDown: upcomingDeadlines > 0 },
        { title: "전체 일정", value: String(events.length), unit: "건", color: "#a970ff", badge: "◈", delta: "자동 저장됨" },
      ];
      return {
        events,
        todos,
        q,
        ym,
        year,
        month,
        gridStart,
        mode,
        selectedDate,
        weekStart,
        weekEnd,
        rangeStart,
        rangeEnd,
        rangeTitle,
        matchedIds,
        monthOccurrences,
        visibleMonthOccurrences,
        rangeOccurrences,
        visibleRangeOccurrences,
        calendarSearchEmpty: !!q && visibleRangeOccurrences.length === 0,
        kpis,
      };
    }

    function modeSwitchHTML(model) {
      const modes = [
        { key: "month", label: "월" },
        { key: "week", label: "주" },
        { key: "day", label: "일" },
      ];
      return html`
        <div class="sched-mode" role="group" aria-label="달력 보기 전환">
          ${raw(modes.map((mode) => html`
            <button type="button" data-action="cal-mode" data-mode="${mode.key}" aria-pressed="${raw(model.mode === mode.key ? "true" : "false")}" class="${raw(model.mode === mode.key ? "is-active" : "")}">${mode.label}</button>
          `).join(""))}
        </div>
      `;
    }

    function weekdayHeaderHTML() {
      return weekdaysKo.map((day, index) => html`<div class="sched-wd ${raw(index === 0 ? "is-sun" : index === 6 ? "is-sat" : "")}" role="columnheader">${day}</div>`).join("");
    }

    function calendarGridHTML(model) {
      const cells = [];
      for (let i = 0; i < 42; i += 1) {
        const date = new Date(model.gridStart);
        date.setDate(model.gridStart.getDate() + i);
        const iso = ymd(date);
        const out = date.getMonth() !== model.month;
        const dow = date.getDay();
        let dayEvents = eventsOn(iso);
        if (model.q) dayEvents = dayEvents.filter((event) => model.matchedIds.has(event._masterId || event.id));
        const shown = dayEvents.slice(0, 3);
        const selected = model.selectedDate === iso;
        const todayCell = isTodayISO(iso);
        const dayLabel = [
          formatKoreanFull(iso),
          dayEvents.length ? `일정 ${dayEvents.length}건` : "일정 없음",
          selected ? "선택됨" : "",
          todayCell ? "오늘" : "",
        ].filter(Boolean).join(" - ");
        const chips = shown.map((event) => {
          const category = categoryMeta(event.category);
          const openId = event._masterId || event.id;
          return html`<button type="button" class="sched-chip" data-action="open-event" data-event-id="${openId}" data-search-result="calendar" title="${event.title}">
            <i style="background:${raw(category.color)}"></i>${event.allDay ? "" : raw(html`<em>${event.start || ""}</em> `)}${event.title}
          </button>`;
        }).join("");
        const more = dayEvents.length > 3 ? html`<span class="sched-more">+${dayEvents.length - 3}건 더</span>` : "";
        cells.push(html`
          <div class="sched-cell ${raw(out ? "is-out" : "")} ${raw(todayCell ? "is-today" : "")} ${raw(selected ? "is-sel" : "")}"
               data-action="cal-open-day" data-date="${iso}" role="gridcell" aria-selected="${raw(selected ? "true" : "false")}" ${raw(todayCell ? 'aria-current="date"' : "")} tabindex="${raw(selected ? "0" : "-1")}" aria-label="${dayLabel}">
            <span class="sched-date ${raw(dow === 0 ? "is-sun" : dow === 6 ? "is-sat" : "")}">${date.getDate()}</span>
            <div class="sched-cell-events">${raw(chips)}${raw(more)}</div>
          </div>
        `);
      }
      const rows = [];
      for (let i = 0; i < cells.length; i += 7) {
        rows.push(html`<div class="sched-row" role="row">${raw(cells.slice(i, i + 7).join(""))}</div>`);
      }
      return rows.join("");
    }

    function calendarWeekHTML(model) {
      const days = [];
      for (let index = 0; index < 7; index += 1) {
        const iso = addDaysISO(model.weekStart, index);
        let dayEvents = eventsOn(iso);
        if (model.q) dayEvents = dayEvents.filter((event) => model.matchedIds.has(event._masterId || event.id));
        const selectedTodos = model.q ? [] : model.todos.filter((todo) => todo.due === iso);
        const selected = model.selectedDate === iso;
        const todayCell = isTodayISO(iso);
        const totalItems = dayEvents.length + selectedTodos.length;
        const body = totalItems
          ? html`
            <div class="sched-week-events">${raw(dayEvents.map((event) => eventRow(event, { compact: true, showSkip: true })).join(""))}</div>
            ${selectedTodos.length ? raw(html`
              <div class="sched-week-todos">
                ${raw(selectedTodos.map((todo) => html`
                  <button type="button" class="agenda-todo ${raw(todo.done ? "is-done" : "")}" data-action="open-todo" data-todo-id="${todo.id}">
                    <span class="todo-check-mini ${raw(todo.done ? "is-on" : "")}">${raw(todo.done ? "✓" : "")}</span>${todo.title}
                  </button>
                `).join(""))}
              </div>
            `) : ""}
          `
          : html`<p class="sched-week-empty">${model.q ? "검색 결과 없음" : "비어 있음"}</p>`;
        days.push(html`
          <section class="sched-week-day ${raw(selected ? "is-sel" : "")} ${raw(todayCell ? "is-today" : "")}"
                   data-action="cal-open-day" data-date="${iso}" role="listitem" tabindex="${raw(selected ? "0" : "-1")}"
                   aria-selected="${raw(selected ? "true" : "false")}" ${raw(todayCell ? 'aria-current="date"' : "")}
                   aria-label="${formatKoreanFull(iso)} - ${totalItems ? `항목 ${totalItems}건` : "항목 없음"}${selected ? " - 선택됨" : ""}">
            <div class="sched-week-head">
              <strong>${weekdaysKo[index] || ""}</strong>
              <span>${formatKoreanShort(iso)}</span>
            </div>
            ${raw(body)}
          </section>
        `);
      }
      return html`<div class="sched-week-board" role="list" aria-label="${model.rangeTitle} 주간 일정">${raw(days.join(""))}</div>`;
    }

    function calendarDayHTML(model) {
      let dayEvents = eventsOn(model.selectedDate);
      if (model.q) dayEvents = dayEvents.filter((event) => model.matchedIds.has(event._masterId || event.id));
      const dayTodos = model.q ? [] : model.todos.filter((todo) => todo.due === model.selectedDate);
      const allDayEvents = dayEvents.filter((event) => event.allDay);
      const timedEvents = dayEvents.filter((event) => !event.allDay);
      const dayEmpty = dayEvents.length === 0 && dayTodos.length === 0;
      return html`
        <div class="sched-day-board" aria-label="${formatKoreanFull(model.selectedDate)} 일간 일정">
          <div class="sched-day-head">
            <div>
              <strong>${formatKoreanFull(model.selectedDate)}</strong>
              <span>${dayEvents.length}개 일정 · ${dayTodos.length}개 마감 할 일</span>
            </div>
            <button type="button" class="sched-agenda-add" data-action="cal-add" data-date="${model.selectedDate}">+ 이 날짜에 일정 추가</button>
          </div>
          ${dayEmpty ? raw(html`<p class="sched-day-empty">${model.q ? "이 날짜에 검색 결과가 없습니다." : "이 날짜는 비어 있습니다."}</p>`) : ""}
          ${allDayEvents.length ? raw(html`
            <section class="sched-day-section">
              <h3>종일</h3>
              <div class="sched-day-list">${raw(allDayEvents.map((event) => eventRow(event, { showSkip: true })).join(""))}</div>
            </section>
          `) : ""}
          ${timedEvents.length ? raw(html`
            <section class="sched-day-section">
              <h3>시간대</h3>
              <div class="sched-day-list">${raw(timedEvents.map((event) => eventRow(event, { showSkip: true })).join(""))}</div>
            </section>
          `) : ""}
          ${dayTodos.length ? raw(html`
            <section class="sched-day-section">
              <h3>마감 할 일</h3>
              <div class="sched-agenda-todos">${raw(dayTodos.map((todo) => html`
                <button type="button" class="agenda-todo ${raw(todo.done ? "is-done" : "")}" data-action="open-todo" data-todo-id="${todo.id}">
                  <span class="todo-check-mini ${raw(todo.done ? "is-on" : "")}">${raw(todo.done ? "✓" : "")}</span>${todo.title}
                </button>
              `).join(""))}</div>
            </section>
          `) : ""}
        </div>
      `;
    }

    function calendarPrimaryHTML(model) {
      if (model.mode === "week") return calendarWeekHTML(model);
      if (model.mode === "day") return calendarDayHTML(model);
      return html`
        <div class="sched-weekdays" role="row">${raw(weekdayHeaderHTML())}</div>
        <div class="sched-grid" role="grid" aria-label="${model.year}년 ${model.month + 1}월 달력">${raw(calendarGridHTML(model))}</div>
      `;
    }

    function calendarAgendaHTML(model) {
      const selectedDate = model.selectedDate;
      let selectedEvents = eventsOn(selectedDate);
      if (model.q) selectedEvents = selectedEvents.filter((event) => model.matchedIds.has(event._masterId || event.id));
      const selectedTodos = model.q ? [] : model.todos.filter((todo) => todo.due === selectedDate);
      const agendaEvents = selectedEvents.length
        ? selectedEvents.map((event) => eventRow(event, { showSkip: true })).join("")
        : html`<p class="sched-agenda-empty">${model.q ? "선택한 날짜에 검색 결과가 없습니다." : "일정이 없습니다."}</p>`;
      const agendaTodos = selectedTodos.length
        ? html`<div class="sched-agenda-todos">${selectedTodos.map((todo) => raw(html`
            <button type="button" class="agenda-todo ${raw(todo.done ? "is-done" : "")}" data-action="open-todo" data-todo-id="${todo.id}">
              <span class="todo-check-mini ${raw(todo.done ? "is-on" : "")}">${raw(todo.done ? "✓" : "")}</span>${todo.title}
            </button>`))}</div>`
        : "";
      return html`
        <aside class="panel sched-agenda">
          <div class="panel-head">
            <div><h2>${formatKoreanFull(selectedDate)}</h2></div>
            ${raw(isTodayISO(selectedDate) ? html`<small class="home-tile-sub">오늘</small>` : "")}
          </div>
          <button type="button" class="sched-agenda-add" data-action="cal-add" data-date="${selectedDate}">+ 이 날짜에 일정 추가</button>
          <div class="sched-agenda-list">${raw(agendaEvents)}</div>
          ${selectedTodos.length ? raw(html`<p class="sched-agenda-label">이 날짜 마감 할 일</p>${raw(agendaTodos)}`) : ""}
        </aside>
      `;
    }

    function renderCalendarHTML(input) {
      const model = calendarViewModel(input);
      const calendarEmptyHTML = model.calendarSearchEmpty
        ? html`
          <div class="calendar-search-empty">
            ${raw(searchEmptyState("calendar", "일정 검색 결과가 없습니다", `“${model.q}”와 일치하는 일정이 이번 달에 없습니다. 검색어를 지우고 월간 일정을 다시 확인하세요.`))}
          </div>
        `
        : "";
      return html`
        <section class="kpis kpis-4">${raw(model.kpis.map((kpi) => kpiCard(kpi)).join(""))}</section>
        <section class="sched-layout">
          <div class="panel sched-cal" data-calendar-view-mode="${model.mode}">
            <div class="sched-toolbar">
              <div class="sched-nav">
                <button type="button" data-action="cal-prev" aria-label="이전 ${modeLabel(model.mode)}">‹</button>
                <strong>${model.rangeTitle}</strong>
                <button type="button" data-action="cal-next" aria-label="다음 ${modeLabel(model.mode)}">›</button>
                <button type="button" class="sched-today-btn" data-action="cal-today">오늘</button>
              </div>
              ${raw(modeSwitchHTML(model))}
              ${raw(calLegend())}
              <button type="button" class="sched-add primary-btn" data-action="cal-add">+ 일정 추가</button>
            </div>
            <p class="sched-range-summary">${modeLabel(model.mode)}간 보기 · ${model.visibleRangeOccurrences.length}개 일정${model.q ? " · 검색 적용" : ""}</p>
            ${raw(calendarEmptyHTML)}
            ${raw(calendarPrimaryHTML(model))}
          </div>
          ${raw(calendarAgendaHTML(model))}
        </section>
      `;
    }

    return {
      version: VERSION,
      calLegend,
      eventRow,
      calendarViewModel,
      modeSwitchHTML,
      weekdayHeaderHTML,
      calendarGridHTML,
      calendarWeekHTML,
      calendarDayHTML,
      calendarPrimaryHTML,
      calendarAgendaHTML,
      renderCalendarHTML,
    };
  }

  root.JooParkCalendarView = {
    version: VERSION,
    create: createCalendarView,
  };
})(window);
