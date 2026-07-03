(function (root) {
  "use strict";

  const VERSION = "joopark-stats-view/v1";

  function createStatsView(deps) {
    const options = deps || {};
    const html = options.html;
    const raw = options.raw;
    const todayISO = typeof options.todayISO === "function" ? options.todayISO : function () { return ""; };
    const localYmd = typeof options.localYmd === "function" ? options.localYmd : function (value) { return value || ""; };
    const addDaysISO = typeof options.addDaysISO === "function" ? options.addDaysISO : function (value) { return value; };
    const expandOccurrences = typeof options.expandOccurrences === "function" ? options.expandOccurrences : null;
    const dateFromISO = typeof options.dateFromISO === "function" ? options.dateFromISO : function (value) { return new Date(value); };
    const weekDatesFor = typeof options.weekDatesFor === "function" ? options.weekDatesFor : function () { return []; };
    const habitStreak = typeof options.habitStreak === "function" ? options.habitStreak : function () { return { current: 0, longest: 0 }; };
    const spark = typeof options.spark === "function" ? options.spark : function () { return ""; };
    const kpiCard = typeof options.kpiCard === "function" ? options.kpiCard : function () { return ""; };
    const panelHead = typeof options.panelHead === "function" ? options.panelHead : function (title) { return html`<div class="panel-head"><h2>${title}</h2></div>`; };
    const eventCats = options.eventCats || {};
    const eventCatOrder = Array.isArray(options.eventCatOrder) ? options.eventCatOrder : [];
    const weekdaysKo = Array.isArray(options.weekdaysKo) ? options.weekdaysKo : [];

    if (typeof html !== "function" || typeof raw !== "function") {
      throw new Error("stats view requires html and raw helpers");
    }

    function eventCategory(category) {
      return eventCats[category] || eventCats.etc || { label: "기타", color: "var(--cyan)" };
    }

    function sum(values) {
      return values.reduce((total, value) => total + value, 0);
    }

    function sparkSummary(label, dates, points) {
      const total = sum(points);
      const max = Math.max(...points, 0);
      const last = points[points.length - 1] || 0;
      const activeDays = points.filter((value) => value > 0).length;
      const range = dates.length ? `${dates[0]}부터 ${dates[dates.length - 1]}까지` : "최근 기간";
      return `${label}: ${range}, 총 ${total}건, 최고 ${max}건, 마지막 날 ${last}건, 기록 있는 날 ${activeDays}일`;
    }

    function sparkDetail(dates, points) {
      return dates.map((date, index) => `${date} ${points[index] || 0}건`).join(", ");
    }

    function accessibleSpark(points, dates, color, label) {
      const summary = sparkSummary(label, dates, points);
      return html`
        <div class="spark-chart" role="img" aria-label="${summary}">
          <div class="spark-wrap" aria-hidden="true">${raw(spark(points, color))}</div>
          <p class="sr-only">${summary}. 일별 값: ${sparkDetail(dates, points)}</p>
        </div>
      `;
    }

    function barChart(items, opts) {
      if (!items || items.length === 0) return html`<p class="muted-note">데이터 없음</p>`;
      const maxVal = Math.max(...items.map((item) => item.value), 1);
      const maxWidth = (opts && opts.maxWidth) || 180;
      const barH = (opts && opts.height) || 14;
      const showValues = opts && opts.showValues !== false;
      return items.map((item) => {
        const pct = Math.round((item.value / maxVal) * 100);
        const width = Math.max(pct === 0 ? 0 : 4, Math.round((item.value / maxVal) * maxWidth));
        return html`
          <div class="bar-row" aria-label="${item.label} ${item.value}건">
            <span class="bar-label">${item.label}</span>
            <div class="bar-track" style="height:${barH}px" aria-hidden="true">
              <div class="bar-fill" style="width:${width}px;height:${barH}px;background:${raw(item.color || "var(--blue)")}"></div>
            </div>
            ${showValues ? raw(html`<span class="bar-val">${item.value}</span>`) : ""}
          </div>
        `;
      }).join("");
    }

    function statsViewModel(input) {
      const data = input || {};
      const today = todayISO();
      const todos = Array.isArray(data.todos) ? data.todos : [];
      const habits = Array.isArray(data.habits) ? data.habits : [];
      const events = Array.isArray(data.events) ? data.events : [];
      const weekStart = weekDatesFor(today)[0] || today;
      const completion = todoCompletionStats(todos, weekStart, today);
      const activeHabits = habits.filter((habit) => !habit.archived);
      // Occurrence-based when the runtime injects expandOccurrences so recurring
      // deadlines and skipped exceptions count correctly; master-date fallback
      // keeps standalone view-model tests independent of the runtime expander.
      const deadlineEvents7 = expandOccurrences
        ? expandOccurrences(today, addDaysISO(today, 7)).filter((event) => event.category === "deadline").length
        : events.filter((event) => event.category === "deadline" && event.date >= today && event.date <= addDaysISO(today, 7)).length;
      const upcomingDeadline7 = todos.filter((todo) => !todo.done && todo.due && todo.due >= today && todo.due <= addDaysISO(today, 7)).length
        + deadlineEvents7;
      const kpis = [
        { title: "이번 주 완료", value: String(completion.weekTodoDone), unit: "건", color: "var(--green)", badge: "✓", delta: "할 일" },
        { title: "전체 완료율", value: String(completion.totalRate), unit: "%", color: "var(--blue)", badge: "▦", delta: `${completion.totalDone}/${todos.length}건` },
        { title: "활성 습관", value: String(activeHabits.length), unit: "개", color: "var(--violet)", badge: "◉", delta: "습관 트래커" },
        { title: "다가오는 마감", value: String(upcomingDeadline7), unit: "건", color: upcomingDeadline7 ? "var(--red)" : "var(--green)", badge: "⚑", delta: "7일 이내", trendDown: upcomingDeadline7 > 0 },
      ];

      const last14 = [];
      for (let index = 13; index >= 0; index -= 1) last14.push(addDaysISO(today, -index));
      const createdByDay = new Array(14).fill(0);
      const completedByDay = new Array(14).fill(0);
      const last14Set = new Set(last14);
      const dateToIndex = {};
      last14.forEach((date, i) => { dateToIndex[date] = i; });
      const doneByWeekday = [0, 0, 0, 0, 0, 0, 0];
      let weekTodoDone = 0;
      let totalDone = 0;
      todos.forEach((todo) => {
        if (todo.createdAt) {
          const createdDate = localYmd(todo.createdAt);
          if (dateToIndex[createdDate] !== undefined) createdByDay[dateToIndex[createdDate]] += 1;
        }
        if (todo.done) {
          totalDone += 1;
          if (todo.completedAt) {
            const completedDate = localYmd(todo.completedAt);
            if (dateToIndex[completedDate] !== undefined) completedByDay[dateToIndex[completedDate]] += 1;
            const date = dateFromISO(completedDate);
            doneByWeekday[date.getDay()] += 1;
            if (completedDate >= weekStart && completedDate <= today) weekTodoDone += 1;
          }
        }
      });
      const weekdayItems = weekdaysKo.map((weekday, index) => ({
        label: `${weekday}요일`,
        value: doneByWeekday[index],
        color: index === 0 ? "var(--red)" : index === 6 ? "var(--blue)" : "var(--cyan)",
      }));

      const categoryCounts = {};
      eventCatOrder.forEach((key) => { categoryCounts[key] = 0; });
      events.forEach((event) => {
        if (categoryCounts[event.category] !== undefined) categoryCounts[event.category] += 1;
        else categoryCounts.etc = (categoryCounts.etc || 0) + 1;
      });
      const categoryItems = eventCatOrder.filter((key) => categoryCounts[key] > 0).map((key) => ({
        label: eventCategory(key).label,
        value: categoryCounts[key],
        color: eventCategory(key).color,
      }));

      return {
        today,
        todos,
        habits,
        events,
        activeHabits,
        kpis,
        last14,
        createdByDay,
        completedByDay,
        doneByWeekday,
        weekdayItems,
        categoryItems,
      };
    }

    function todoCompletionStats(todos, weekStart, today) {
      let weekTodoDone = 0;
      let totalDone = 0;
      todos.forEach((todo) => {
        if (todo.done) {
          totalDone += 1;
          if (todo.completedAt) {
            const completedDate = localYmd(todo.completedAt);
            if (completedDate >= weekStart && completedDate <= today) weekTodoDone += 1;
          }
        }
      });
      const totalRate = todos.length ? Math.round((totalDone / todos.length) * 100) : 0;
      return { weekTodoDone, totalDone, totalRate };
    }

    function trendSection(model) {
      const hasTrend = model.createdByDay.some((value) => value > 0) || model.completedByDay.some((value) => value > 0);
      if (!hasTrend) return html`<p class="muted-note">아직 할 일 기록이 없습니다.</p>`;
      return html`
        <div class="stats-chart-block" data-stats-chart="todo-trend">
          <p class="stats-chart-title">생성 추이 <small style="color:var(--cyan)">(최근 14일)</small></p>
          ${raw(accessibleSpark(model.createdByDay, model.last14, "var(--cyan)", "최근 14일 할 일 생성 추이"))}
          <p class="stats-chart-title" style="margin-top:10px">완료 추이 <small style="color:var(--green)">(최근 14일)</small></p>
          ${raw(accessibleSpark(model.completedByDay, model.last14, "var(--green)", "최근 14일 할 일 완료 추이"))}
          <div class="spark-legend">
            <span><i style="background:var(--cyan)"></i>생성</span>
            <span><i style="background:var(--green)"></i>완료</span>
          </div>
        </div>
      `;
    }

    function weekdaySection(model) {
      return model.doneByWeekday.some((value) => value > 0)
        ? html`<div class="bar-chart" data-stats-chart="weekday-completion">${raw(barChart(model.weekdayItems, { maxWidth: 200, height: 14 }))}</div>`
        : html`<p class="muted-note">아직 완료한 할 일이 없습니다. 할 일을 완료하면 요일별 분포가 채워집니다.</p>`;
    }

    function categorySection(model) {
      return model.categoryItems.length
        ? html`<div class="bar-chart" data-stats-chart="event-category">${raw(barChart(model.categoryItems, { maxWidth: 200, height: 14 }))}</div>`
        : html`<p class="muted-note">일정이 없습니다.</p>`;
    }

    function statsHabitProgress(habit, today) {
      const weekDates = weekDatesFor(today);
      const log = habit.log || {};
      const weekDone = weekDates.filter((date) => log[date]).length;
      const target = habit.target || 7;
      const pct = Math.min(100, Math.round((weekDone / target) * 100));
      return { weekDone, target, pct };
    }

    function habitSummaryRow(habit, today) {
      const progress = statsHabitProgress(habit, today);
      const streak = habitStreak(habit);
      return html`
        <div class="habit-summary-row">
          <span class="habit-summary-emoji">${habit.emoji || "✅"}</span>
          <div class="habit-summary-info">
            <strong>${habit.name}</strong>
            <div class="habit-summary-bar-wrap" aria-hidden="true">
              <div class="habit-summary-bar" style="width:${progress.pct}%;background:${raw(habit.color || "var(--cyan)")}"></div>
            </div>
            <small>${progress.weekDone}/${progress.target}일 · 🔥 ${streak.current}일 연속</small>
          </div>
          <span class="habit-summary-pct" aria-label="${habit.name} 이번 주 달성률 ${progress.pct}%">${progress.pct}%</span>
        </div>
      `;
    }

    function habitSummarySection(model) {
      if (!model.activeHabits.length) {
        return html`<p class="muted-note">활성 습관이 없습니다. <a href="#habits" data-action="nav-to" data-view="habits">습관 트래커</a>에서 추가해 보세요.</p>`;
      }
      return html`<div class="habit-summary-list">${raw(model.activeHabits.map((habit) => habitSummaryRow(habit, model.today)).join(""))}</div>`;
    }

    function renderStatsHTML(input) {
      const model = statsViewModel(input);
      return html`
        <section class="kpis kpis-4">${raw(model.kpis.map((kpi) => kpiCard(kpi)).join(""))}</section>
        <div class="stats-grid">
          <section class="panel stats-panel">
            ${raw(panelHead("최근 14일 할 일 추이", null, ""))}
            <div class="stats-panel-body">${raw(trendSection(model))}</div>
          </section>
          <section class="panel stats-panel">
            ${raw(panelHead("요일별 완료 분포", null, ""))}
            <div class="stats-panel-body">${raw(weekdaySection(model))}</div>
          </section>
          <section class="panel stats-panel">
            ${raw(panelHead("일정 분류 분포", null, ""))}
            <div class="stats-panel-body">${raw(categorySection(model))}</div>
          </section>
          <section class="panel stats-panel">
            ${raw(panelHead("습관 요약", null, ""))}
            <div class="stats-panel-body">${raw(habitSummarySection(model))}</div>
          </section>
        </div>
      `;
    }

    return {
      version: VERSION,
      statsViewModel,
      todoCompletionStats,
      accessibleSpark,
      barChart,
      trendSection,
      weekdaySection,
      categorySection,
      statsHabitProgress,
      habitSummarySection,
      renderStatsHTML,
    };
  }

  root.JooParkStatsView = {
    version: VERSION,
    create: createStatsView,
  };
})(window);
