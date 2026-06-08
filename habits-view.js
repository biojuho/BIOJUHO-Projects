(function (root) {
  "use strict";

  const VERSION = "joopark-habits-view/v1";

  function createHabitsView(deps) {
    const options = deps || {};
    const html = options.html;
    const raw = options.raw;
    const matches = typeof options.matches === "function" ? options.matches : function () { return true; };
    const todayISO = typeof options.todayISO === "function" ? options.todayISO : function () { return ""; };
    const weekDatesFor = typeof options.weekDatesFor === "function" ? options.weekDatesFor : function () { return []; };
    const habitStreak = typeof options.habitStreak === "function" ? options.habitStreak : function () { return { current: 0, longest: 0 }; };
    const formatKoreanShort = typeof options.formatKoreanShort === "function" ? options.formatKoreanShort : function (value) { return value || ""; };
    const kpiCard = typeof options.kpiCard === "function" ? options.kpiCard : function () { return ""; };
    const panelHead = typeof options.panelHead === "function" ? options.panelHead : function (title) { return html`<div class="panel-head"><h2>${title}</h2></div>`; };
    const searchEmptyState = typeof options.searchEmptyState === "function" ? options.searchEmptyState : function () { return ""; };
    const weekdaysKo = Array.isArray(options.weekdaysKo) ? options.weekdaysKo : [];
    const noteColors = Array.isArray(options.noteColors) ? options.noteColors : [];

    if (typeof html !== "function" || typeof raw !== "function") {
      throw new Error("habits view requires html and raw helpers");
    }

    function habitColor(habit) {
      return habit.color || noteColors[0] || "var(--cyan)";
    }

    function habitsViewModel(input) {
      const data = input || {};
      const habits = Array.isArray(data.habits) ? data.habits : [];
      const q = (data.query || "").trim();
      const today = todayISO();
      const weekDates = weekDatesFor(today);
      const active = habits.filter((habit) => !habit.archived);
      const list = active.filter((habit) => matches(`${habit.name} ${habit.emoji || ""}`, q));
      const todayDone = active.filter((habit) => (habit.log || {})[today]).length;
      const weekRates = active.map((habit) => {
        const log = habit.log || {};
        const target = habit.target || 7;
        const doneDays = weekDates.filter((date) => log[date]).length;
        return Math.min(100, Math.round((doneDays / target) * 100));
      });
      const avgRate = weekRates.length ? Math.round(weekRates.reduce((sum, rate) => sum + rate, 0) / weekRates.length) : 0;
      const bestStreak = active.reduce((best, habit) => {
        const streak = habitStreak(habit);
        return streak.longest > best ? streak.longest : best;
      }, 0);
      const archivedCount = habits.filter((habit) => habit.archived).length;
      const kpis = [
        { title: "활성 습관", value: String(active.length), unit: "개", color: "var(--cyan)", badge: "◉", delta: archivedCount ? `보관 ${archivedCount}개` : "관리 중" },
        { title: "오늘 완료", value: String(todayDone), unit: `/${active.length}`, color: "var(--green)", badge: "✓", delta: formatKoreanShort(today) },
        { title: "평균 달성률", value: String(avgRate), unit: "%", color: "var(--blue)", badge: "▦", delta: "이번 주" },
        { title: "최장 연속", value: String(bestStreak), unit: "일", color: "var(--violet)", badge: "🔥", delta: "전체 습관 중 최고" },
      ];
      return {
        habits,
        q,
        today,
        weekDates,
        active,
        list,
        kpis,
      };
    }

    function habitDayButton(habit, date, index, model) {
      const log = habit.log || {};
      const checked = !!log[date];
      const isToday = date === model.today;
      const isFuture = date > model.today;
      const weekday = weekdaysKo[index] || "";
      return html`<button
        type="button"
        class="habit-day ${raw(checked ? "is-checked" : "")} ${raw(isToday ? "is-today" : "")} ${raw(isFuture ? "is-future" : "")}"
        data-action="${raw(isFuture ? "" : "habit-toggle")}"
        data-habit-id="${habit.id}"
        data-date="${date}"
        ${raw(isFuture ? "disabled" : "")}
        aria-pressed="${raw(checked ? "true" : "false")}"
        aria-label="${weekday}${raw(isToday ? " (오늘)" : "")}${raw(checked ? " 완료" : "")}"
        title="${date}"
      >${weekday}</button>`;
    }

    function habitCard(habit, model) {
      const log = habit.log || {};
      const streak = habitStreak(habit);
      const target = habit.target || 7;
      const weekDone = model.weekDates.filter((date) => log[date]).length;
      const rate = Math.min(100, Math.round((weekDone / target) * 100));
      const color = habitColor(habit);
      const dayButtons = model.weekDates.map((date, index) => habitDayButton(habit, date, index, model)).join("");
      return html`
        <article class="habit-card" style="--habit-color:${raw(color)}" data-search-result="habits">
          <div class="habit-card-head">
            <span class="habit-emoji">${habit.emoji || "✅"}</span>
            <strong class="habit-name">${habit.name}</strong>
            <div class="habit-card-actions">
              <button type="button" class="icon-btn" data-action="open-habit" data-habit-id="${habit.id}" aria-label="${habit.name} 습관 편집">✎</button>
              <button type="button" class="icon-btn icon-btn-del" data-action="habit-delete" data-habit-id="${habit.id}" aria-label="${habit.name} 습관 삭제">✕</button>
            </div>
          </div>
          <div class="habit-week-grid">${raw(dayButtons)}</div>
          <div class="habit-stats-row">
            <span class="streak-badge">🔥 ${streak.current}일 연속</span>
            <span class="streak-best">최장 ${streak.longest}일</span>
            <span class="habit-week-prog">${weekDone}/${target} <small>(${rate}%)</small></span>
          </div>
          <div class="habit-bar-wrap">
            <div class="habit-bar" style="width:${rate}%;background:${raw(color)}"></div>
          </div>
        </article>
      `;
    }

    function habitsGridHTML(model) {
      const cards = model.active.length === 0
        ? html`<article class="empty">습관이 없습니다. <button type="button" class="link-btn" data-action="habit-add">+ 습관 추가</button>로 시작해 보세요.</article>`
        : model.list.length === 0 && model.q
          ? searchEmptyState("habits", "습관 검색 결과가 없습니다", `“${model.q}”와 일치하는 습관이 없습니다. 검색어를 지우고 전체 습관을 다시 확인하세요.`)
          : model.list.map((habit) => habitCard(habit, model)).join("");
      return html`<div class="habits-grid">${raw(cards)}</div>`;
    }

    function renderHabitsHTML(input) {
      const model = habitsViewModel(input);
      return html`
        <section class="kpis kpis-4">${raw(model.kpis.map((kpi) => kpiCard(kpi)).join(""))}</section>
        <section class="panel habits-panel">
          ${raw(panelHead("습관 트래커", null, html`<button type="button" class="primary-btn" data-action="habit-add">+ 습관 추가</button>`))}
          ${raw(habitsGridHTML(model))}
        </section>
      `;
    }

    return {
      version: VERSION,
      habitsViewModel,
      habitDayButton,
      habitCard,
      habitsGridHTML,
      renderHabitsHTML,
    };
  }

  root.JooParkHabitsView = {
    version: VERSION,
    create: createHabitsView,
  };
})(window);
