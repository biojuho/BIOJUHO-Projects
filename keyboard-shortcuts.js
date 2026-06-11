(function (root) {
  "use strict";

  const VERSION = "joopark-keyboard-shortcuts/v1";

  function noop() {}

  function createKeyboardShortcuts(deps) {
    const options = deps || {};
    const documentRef = options.document || root.document;
    const getCurrentView = typeof options.getCurrentView === "function" ? options.getCurrentView : function defaultView() { return "home"; };
    const getSearchInput = typeof options.getSearchInput === "function" ? options.getSearchInput : function noSearchInput() { return null; };
    const isPaletteOpen = typeof options.isPaletteOpen === "function" ? options.isPaletteOpen : function paletteClosed() { return false; };
    const isSearchInertView = typeof options.isSearchInertView === "function" ? options.isSearchInertView : function searchActive() { return false; };
    const escapeHtml = typeof options.escapeHtml === "function" ? options.escapeHtml : function fallbackEscape(value) {
      return String(value || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
    };
    const callbacks = {
      openModal: options.openModal || noop,
      openPalette: options.openPalette || noop,
      closePalette: options.closePalette || noop,
      projectPickerIsOpen: options.projectPickerIsOpen || function () { return false; },
      setProjectPickerOpen: options.setProjectPickerOpen || noop,
      restoreProjectPickerFocus: options.restoreProjectPickerFocus || noop,
      isModalOpen: options.isModalOpen || function () { return false; },
      closeModal: options.closeModal || noop,
      isSheetOpen: options.isSheetOpen || function () { return false; },
      closeSheet: options.closeSheet || noop,
      getOpenDialogRoot: options.getOpenDialogRoot || function () { return null; },
      trapTab: options.trapTab || noop,
      calSelectDay: options.calSelectDay || noop,
      addDaysISO: options.addDaysISO || function (date) { return date; },
      dateFromISO: options.dateFromISO || function () { return new Date(); },
      openTaskSheet: options.openTaskSheet || noop,
      moveIssueOrder: options.moveIssueOrder || noop,
      setCalendarMode: options.setCalendarMode || noop,
      openEventModal: options.openEventModal || noop,
      openTodoModal: options.openTodoModal || noop,
      openNoteModal: options.openNoteModal || noop,
      openHabitModal: options.openHabitModal || noop,
      openIssueModal: options.openIssueModal || noop,
      openProjectModal: options.openProjectModal || noop,
      openTaskModal: options.openTaskModal || noop,
      openMemberModal: options.openMemberModal || noop,
      setView: options.setView || noop,
    };
    let lastGTime = 0;

    function closestTarget(event, selector) {
      return event.target && event.target.closest ? event.target.closest(selector) : null;
    }

    function isTypingTarget(element) {
      if (!element) return false;
      return element.tagName === "INPUT" ||
        element.tagName === "TEXTAREA" ||
        element.tagName === "SELECT" ||
        element.isContentEditable;
    }

    function activateNewItemShortcut(currentView) {
      if (currentView === "cal") callbacks.openEventModal(null);
      else if (currentView === "todo") callbacks.openTodoModal(null);
      else if (currentView === "notes") callbacks.openNoteModal(null);
      else if (currentView === "habits") callbacks.openHabitModal(null);
      else if (currentView === "pm-kanban") callbacks.openIssueModal(null);
      else if (currentView === "pm-portfolio") callbacks.openProjectModal(null);
      else if (currentView === "pm-gantt") callbacks.openTaskModal(null);
      else if (currentView === "pm-team") callbacks.openMemberModal(null);
      else callbacks.openEventModal(null);
    }

    function openShortcutHelp() {
      const nav = root.navigator || {};
      const isMac = /Mac|iPhone|iPad/.test(nav.platform || nav.userAgent || "");
      const mod = isMac ? "⌘" : "Ctrl";
      const rows = [
        [`<kbd class="kbd">${mod}+K</kbd>`, "명령 팔레트 / 통합 검색 열기"],
        [`<kbd class="kbd">/</kbd>`, "검색 가능 뷰는 현재 뷰 검색, 요약 뷰는 명령 팔레트"],
        [`<kbd class="kbd">n</kbd>`, "현재 뷰에 새 항목 추가"],
        [`<kbd class="kbd">?</kbd>`, "이 도움말 열기"],
        [`<kbd class="kbd">Esc</kbd>`, "팔레트 · 모달 · 시트 닫기"],
        [`<kbd class="kbd">g</kbd> → <kbd class="kbd">h</kbd>`, "홈 대시보드로 이동"],
        [`<kbd class="kbd">g</kbd> → <kbd class="kbd">c</kbd>`, "일정으로 이동"],
        [`<kbd class="kbd">g</kbd> → <kbd class="kbd">t</kbd>`, "할 일로 이동"],
        [`<kbd class="kbd">g</kbd> → <kbd class="kbd">m</kbd>`, "메모로 이동"],
        [`<kbd class="kbd">g</kbd> → <kbd class="kbd">i</kbd>`, "습관으로 이동"],
        [`<kbd class="kbd">g</kbd> → <kbd class="kbd">s</kbd>`, "통계로 이동"],
        [`<kbd class="kbd">g</kbd> → <kbd class="kbd">p</kbd>`, "포트폴리오로 이동"],
        [`<kbd class="kbd">g</kbd> → <kbd class="kbd">k</kbd>`, "Kanban 보드로 이동"],
        ["할 일 입력 후 <kbd class=\"kbd\">Enter</kbd>", "할 일 빠른 추가"],
      ];
      const tableHTML = `<table class="shortcut-table">
    <thead><tr><th>단축키</th><th>기능</th></tr></thead>
    <tbody>${rows.map(([key, desc]) => `<tr><td>${key}</td><td>${escapeHtml(desc)}</td></tr>`).join("")}</tbody>
  </table>`;
      callbacks.openModal("키보드 단축키", tableHTML, null);
    }

    function handleKeydown(event) {
      const key = event.key || "";
      const currentView = getCurrentView();

      if ((event.metaKey || event.ctrlKey) && key.toLowerCase() === "k") {
        event.preventDefault();
        if (isPaletteOpen()) callbacks.closePalette();
        else callbacks.openPalette();
        return;
      }

      if (key === "Escape") {
        if (isPaletteOpen()) {
          event.preventDefault();
          callbacks.closePalette();
          return;
        }
        if (callbacks.projectPickerIsOpen()) {
          event.preventDefault();
          callbacks.setProjectPickerOpen(false);
          callbacks.restoreProjectPickerFocus();
          return;
        }
        if (callbacks.isModalOpen()) callbacks.closeModal();
        else if (callbacks.isSheetOpen()) callbacks.closeSheet();
        return;
      }

      if (key === "Tab") {
        if (isPaletteOpen()) {
          const palPanel = documentRef.querySelector(".palette-panel");
          if (palPanel) {
            callbacks.trapTab(event, palPanel);
            return;
          }
        }
        const dialog = callbacks.getOpenDialogRoot();
        if (dialog) callbacks.trapTab(event, dialog);
      }

      const calendarCell = closestTarget(event, "[data-action='cal-open-day']");
      if (calendarCell && calendarCell.tagName.toLowerCase() !== "button") {
        const date = calendarCell.dataset.date;
        const deltas = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7 };
        if (Object.prototype.hasOwnProperty.call(deltas, key)) {
          event.preventDefault();
          callbacks.calSelectDay(callbacks.addDaysISO(date, deltas[key]), { focus: true });
          return;
        }
        if (key === "Home" || key === "End") {
          event.preventDefault();
          const dow = callbacks.dateFromISO(date).getDay();
          callbacks.calSelectDay(callbacks.addDaysISO(date, key === "Home" ? -dow : 6 - dow), { focus: true });
          return;
        }
        if (key === "Enter" || key === " ") {
          event.preventDefault();
          callbacks.calSelectDay(date, { focus: true });
          return;
        }
      }

      if (key === "Enter" || key === " ") {
        const el = closestTarget(event, "[data-action='open-task']");
        if (el && el.tagName.toLowerCase() !== "button") {
          event.preventDefault();
          callbacks.openTaskSheet(el.dataset.taskId);
        }
      }

      const active = documentRef.activeElement;
      const dialogOpen = isPaletteOpen() || callbacks.isModalOpen() || callbacks.isSheetOpen();
      if (isTypingTarget(active) || dialogOpen) return;

      if (
        currentView === "pm-kanban" &&
        event.altKey &&
        event.shiftKey &&
        !event.metaKey &&
        !event.ctrlKey &&
        (key === "ArrowUp" || key === "ArrowDown")
      ) {
        const focusedCard = active && active.closest ? active.closest("#view-pm-kanban .kanban-card-wrap[data-issue-id]") : null;
        if (focusedCard) {
          event.preventDefault();
          callbacks.moveIssueOrder(focusedCard.dataset.issueId, key === "ArrowUp" ? "top" : "bottom");
          return;
        }
      }

      if (key === "/" && !event.metaKey && !event.ctrlKey && !event.altKey) {
        event.preventDefault();
        if (isSearchInertView()) {
          callbacks.openPalette();
        } else {
          const query = getSearchInput();
          if (query) {
            query.focus();
            query.select();
          }
        }
        return;
      }

      if (key === "?") {
        event.preventDefault();
        openShortcutHelp();
        return;
      }

      if (currentView === "cal" && ["m", "w", "d"].includes(key) && !event.metaKey && !event.ctrlKey && !event.altKey) {
        event.preventDefault();
        callbacks.setCalendarMode({ m: "month", w: "week", d: "day" }[key]);
        return;
      }

      if (key === "n" && !event.metaKey && !event.ctrlKey && !event.altKey) {
        event.preventDefault();
        activateNewItemShortcut(currentView);
        return;
      }

      if (key === "g" && !event.metaKey && !event.ctrlKey && !event.altKey) {
        event.preventDefault();
        lastGTime = Date.now();
        return;
      }
      if (lastGTime && (Date.now() - lastGTime) < 1200 && !event.metaKey && !event.ctrlKey && !event.altKey) {
        const dest = {
          h: "home",
          c: "cal",
          t: "todo",
          m: "notes",
          i: "habits",
          s: "stats",
          p: "pm-portfolio",
          k: "pm-kanban",
        }[key];
        if (dest) {
          event.preventDefault();
          lastGTime = 0;
          callbacks.setView(dest);
          return;
        }
        lastGTime = 0;
      }
    }

    function setup() {
      if (!documentRef || documentRef.documentElement.dataset.keyboardShortcutsBound === "true") return;
      documentRef.documentElement.dataset.keyboardShortcutsBound = "true";
      documentRef.addEventListener("keydown", handleKeydown);
    }

    return {
      version: VERSION,
      setup,
      handleKeydown,
      openHelp: openShortcutHelp,
    };
  }

  root.JooParkKeyboardShortcuts = {
    version: VERSION,
    create: createKeyboardShortcuts,
  };
})(window);
