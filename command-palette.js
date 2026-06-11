/* ================================================================
 * JooPark Workspace — command palette helpers
 * Static non-module runtime loaded before app.js.
 * ================================================================ */

(function initJooParkCommandPalette(global) {
  "use strict";

  const VERSION = "joopark-command-palette/v1";
  const DEFAULT_MAX_HITS = 40;
  const PAL_NAV_COMMANDS = Object.freeze([
    Object.freeze({ view: "home",          icon: "⌘", cls: "pal-icon-misc",  label: "홈 대시보드" }),
    Object.freeze({ view: "cal",           icon: "◷", cls: "pal-icon-event", label: "일정", terms: "calendar cal 일정 캘린더", priorityQueries: ["calendar", "cal", "일정", "캘린더"] }),
    Object.freeze({ view: "todo",          icon: "☑", cls: "pal-icon-todo",  label: "할 일", terms: "todo task tasks 할 일 할일", priorityQueries: ["todo", "task", "tasks", "할 일", "할일"] }),
    Object.freeze({ view: "notes",         icon: "✎", cls: "pal-icon-note",  label: "메모", terms: "note notes memo 메모 노트", priorityQueries: ["note", "notes", "memo", "메모", "노트"] }),
    Object.freeze({ view: "habits",        icon: "◉", cls: "pal-icon-habit", label: "습관", terms: "habit habits 습관 루틴", priorityQueries: ["habit", "habits", "습관", "루틴"] }),
    Object.freeze({ view: "stats",         icon: "▤", cls: "pal-icon-misc",  label: "통계", terms: "stats statistics 통계", priorityQueries: ["stats", "statistics", "통계"] }),
    Object.freeze({ view: "llm-wiki",      icon: "◇", cls: "pal-icon-note",  label: "LLM 위키", terms: "llm wiki knowledge 위키 지식", priorityQueries: ["llm wiki", "wiki", "LLM 위키", "위키"] }),
    Object.freeze({ view: "pm-portfolio",  icon: "▦", cls: "pal-icon-proj",  label: "포트폴리오", terms: "portfolio project projects 프로젝트", priorityQueries: ["portfolio", "project", "projects", "포트폴리오", "프로젝트"] }),
    Object.freeze({ view: "pm-kanban",     icon: "▣", cls: "pal-icon-issue", label: "Kanban 보드", terms: "kanban 칸반 board 보드", priorityQueries: ["kanban", "칸반"] }),
    Object.freeze({ view: "pm-gantt",      icon: "↔", cls: "pal-icon-misc",  label: "간트 차트", terms: "gantt timeline 간트 타임라인 차트", priorityQueries: ["gantt", "timeline", "간트", "간트 차트", "타임라인"] }),
    Object.freeze({ view: "pm-team",       icon: "◈", cls: "pal-icon-misc",  label: "팀 · 리소스", terms: "team resource resources 팀 리소스", priorityQueries: ["team", "resource", "resources", "팀", "리소스", "팀 리소스"] }),
    Object.freeze({ view: "dbm-instances", icon: "✺", cls: "pal-icon-misc",  label: "인스턴스 상태", terms: "db database 데이터베이스 데이터 카탈로그 instance instances 인스턴스 상태", priorityQueries: ["db instance", "db instances", "database instance", "database instances", "데이터베이스 인스턴스", "데이터 카탈로그 인스턴스"] }),
    Object.freeze({ view: "dbm-schema",    icon: "◎", cls: "pal-icon-misc",  label: "스키마 탐색", terms: "db database 데이터베이스 데이터 카탈로그 schema 스키마 탐색", priorityQueries: ["db schema", "database schema", "데이터베이스 스키마", "데이터 카탈로그 스키마"] }),
    Object.freeze({ view: "dbm-queries",   icon: "◉", cls: "pal-icon-misc",  label: "질의 성능", terms: "db database 데이터베이스 데이터 카탈로그 query queries 질의 쿼리 성능", priorityQueries: ["db query", "db queries", "database query", "database queries", "데이터베이스 질의", "데이터베이스 쿼리", "데이터 카탈로그 질의", "데이터 카탈로그 쿼리"] }),
    Object.freeze({ view: "dbm-backups",   icon: "⌘", cls: "pal-icon-misc",  label: "백업 · 마이그", terms: "db database 데이터베이스 데이터 카탈로그 backup 백업 migration 마이그", priorityQueries: ["db backup", "database backup", "데이터베이스 백업", "데이터 카탈로그 백업"] }),
    Object.freeze({ view: "settings",      icon: "⚙", cls: "pal-icon-misc",  label: "설정" }),
    Object.freeze({ view: "system",        icon: "◌", cls: "pal-icon-misc",  label: "시스템 상태", terms: "system status release readiness 시스템 상태 릴리스 준비", priorityQueries: ["system", "system status", "시스템", "시스템 상태", "릴리스 준비"] }),
  ]);

  function escapeHtml(value) {
    if (value === null || value === undefined) return "";
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function fallbackMatches(value, query) {
    if (!query) return true;
    return String(value || "").toLowerCase().includes(String(query || "").toLowerCase());
  }

  function safeArray(value) {
    return Array.isArray(value) ? value : [];
  }

  function uniqueByIdentity(list) {
    return safeArray(list).filter((item, itemIndex, allItems) => allItems.indexOf(item) === itemIndex);
  }

  function noop() {}

  function createCommandPalette(deps = {}) {
    const doc = deps.document || global.document;
    const matches = typeof deps.matches === "function" ? deps.matches : fallbackMatches;
    const escape = typeof deps.escapeHtml === "function" ? deps.escapeHtml : escapeHtml;
    const clampInteger = typeof deps.clampInteger === "function"
      ? deps.clampInteger
      : function (value, min, max = Number.POSITIVE_INFINITY, fallback = 0) {
        const parsed = Number(value);
        const safeParsed = Number.isFinite(parsed) ? parsed : fallback;
        return Math.min(max, Math.max(min, Math.trunc(safeParsed)));
      };
    const maxHits = clampInteger(deps.maxHits, 1, Number.POSITIVE_INFINITY, DEFAULT_MAX_HITS);
    const getDashboard = typeof deps.getDashboard === "function" ? deps.getDashboard : () => ({});
    const getFuse = typeof deps.getFuse === "function" ? deps.getFuse : () => global.Fuse;
    const getPreviousFocus = typeof deps.getPreviousFocus === "function" ? deps.getPreviousFocus : () => null;
    const setPreviousFocus = typeof deps.setPreviousFocus === "function" ? deps.setPreviousFocus : noop;
    const onOpenChange = typeof deps.onOpenChange === "function" ? deps.onOpenChange : noop;
    const formatKoreanShort = typeof deps.formatKoreanShort === "function" ? deps.formatKoreanShort : (value) => value || "";
    const setView = typeof deps.setView === "function" ? deps.setView : noop;
    const openEventModal = typeof deps.openEventModal === "function" ? deps.openEventModal : noop;
    const openTodoModal = typeof deps.openTodoModal === "function" ? deps.openTodoModal : noop;
    const openNoteModal = typeof deps.openNoteModal === "function" ? deps.openNoteModal : noop;
    const openTodoRecord = typeof deps.openTodoRecord === "function" ? deps.openTodoRecord : openTodoModal;
    const openNoteRecord = typeof deps.openNoteRecord === "function" ? deps.openNoteRecord : openNoteModal;
    const openHabitModal = typeof deps.openHabitModal === "function" ? deps.openHabitModal : noop;
    const openProjectModal = typeof deps.openProjectModal === "function" ? deps.openProjectModal : noop;
    const openIssueModal = typeof deps.openIssueModal === "function" ? deps.openIssueModal : noop;
    const exportData = typeof deps.exportData === "function" ? deps.exportData : noop;
    const toggleTheme = typeof deps.toggleTheme === "function" ? deps.toggleTheme : noop;
    const openShortcutHelp = typeof deps.openShortcutHelp === "function" ? deps.openShortcutHelp : noop;
    const openDeletedRecoveryPanel = typeof deps.openDeletedRecoveryPanel === "function" ? deps.openDeletedRecoveryPanel : noop;
    const openIssueRecord = typeof deps.openIssueRecord === "function" ? deps.openIssueRecord : (issue) => {
      setView("pm-kanban");
      openIssueModal(issue);
    };
    const getLlmWikiContext = typeof deps.getLlmWikiContext === "function" ? deps.getLlmWikiContext : () => null;
    const createLlmWikiTodoDraft = typeof deps.createLlmWikiTodoDraft === "function" ? deps.createLlmWikiTodoDraft : noop;
    const createLlmWikiNoteDraft = typeof deps.createLlmWikiNoteDraft === "function" ? deps.createLlmWikiNoteDraft : noop;
    const createLlmWikiIssueDraft = typeof deps.createLlmWikiIssueDraft === "function" ? deps.createLlmWikiIssueDraft : noop;
    const setKanbanSourceFilter = typeof deps.setKanbanSourceFilter === "function" ? deps.setKanbanSourceFilter : noop;
    const openKanbanSourceFilter = typeof deps.openKanbanSourceFilter === "function"
      ? deps.openKanbanSourceFilter
      : (filter) => {
        setView("pm-kanban");
        setKanbanSourceFilter(filter);
      };
    const setTodoSourceFilter = typeof deps.setTodoSourceFilter === "function" ? deps.setTodoSourceFilter : noop;
    const setNoteSourceFilter = typeof deps.setNoteSourceFilter === "function" ? deps.setNoteSourceFilter : noop;

    let open = false;
    let index = 0;
    let items = [];

    function paletteEl() { return doc && doc.getElementById("palette"); }
    function inputEl() { return doc && doc.getElementById("paletteInput"); }
    function resultsEl() { return doc && doc.getElementById("paletteResults"); }
    function statusEl() { return doc && doc.getElementById("paletteStatus"); }

    function paletteOptionButton(event) {
      const target = event && event.target;
      return target && typeof target.closest === "function" ? target.closest("[data-pal-index]") : null;
    }

    function paletteOptionIndex(button) {
      return optionalPaletteIndex(button && button.dataset ? button.dataset.palIndex : null);
    }

    function paletteOptionId(optionIndex) {
      return `pal-option-${optionIndex}`;
    }

    function isOpen() {
      return open;
    }

    function setOpen(next) {
      open = Boolean(next);
      onOpenChange(open);
    }

    function reviewSourceName(sourceKey, fallbackKind = "") {
      const key = String(sourceKey || "");
      if (key.startsWith("workspace-review:")) return "Workspace Review";
      if (key.startsWith("kb-ia-review:")) return "KB/IA Review";
      if (key.startsWith("benchmark-review:")) return "PM Bench Review";
      return String(fallbackKind || "").includes("review") ? "Review" : "";
    }

    function sourceFields(record) {
      return {
        sourceKey: String(record && record.sourceKey || ""),
        sourceKind: String(record && record.sourceKind || ""),
      };
    }

    function issueSourceName(issue) {
      const { sourceKey, sourceKind } = sourceFields(issue);
      if (sourceKind === "llm-wiki-action" || sourceKey.startsWith("llm-wiki:issue:")) return "LLM Wiki";
      if (sourceKind === "db-catalog-stale-review" || sourceKey === "db-catalog:stale-sample-review") return "DB Catalog";
      const reviewName = reviewSourceName(sourceKey, sourceKind);
      if (reviewName) return reviewName;
      return sourceKey || sourceKind ? "Source" : "";
    }

    function issueSourceLabel(issue) {
      const name = issueSourceName(issue);
      return name ? ` · ${name}` : "";
    }

    function sourceAliasText(name) {
      const aliases = {
        "LLM Wiki": "llm wiki 위키 wiki 출처 source",
        "DB Catalog": "db catalog database 데이터 카탈로그 디비 stale sample stale-sample 샘플 검증 출처 source",
        Review: "review 리뷰 검토 패키지 package benchmark workspace knowledge base 벤치마크 워크스페이스 지식 베이스 출처 source",
        "Workspace Review": "review workspace 워크스페이스 workspace review 리뷰 검토 패키지 package 출처 source",
        "KB/IA Review": "review kb ia knowledge base 지식 베이스 정보 구조 리뷰 검토 패키지 package 출처 source",
        "PM Bench Review": "review pm benchmark bench 벤치마크 리뷰 검토 패키지 package 출처 source",
        Source: "source 기타 출처",
      };
      return aliases[name] || "";
    }

    function issueSourceSearchText(issue) {
      const name = issueSourceName(issue);
      if (!name) return "";
      const { sourceKey, sourceKind } = sourceFields(issue);
      return `${name} ${sourceAliasText(name)} ${sourceKey} ${sourceKind}`;
    }

    function recordSourceName(record, kind) {
      const { sourceKey, sourceKind } = sourceFields(record);
      if (sourceKey.startsWith(`llm-wiki:${kind}:`)) return "LLM Wiki";
      const reviewName = reviewSourceName(sourceKey, sourceKind);
      if (reviewName) return reviewName;
      return sourceKey || sourceKind ? "Source" : "";
    }

    function recordSourceLabel(record, kind) {
      const name = recordSourceName(record, kind);
      return name ? ` · ${name}` : "";
    }

    function recordSourceSearchText(record, kind) {
      const { sourceKey, sourceKind } = sourceFields(record);
      const name = recordSourceName(record, kind);
      if (!name) return "";
      return `${name} ${sourceAliasText(name)} ${sourceKey} ${sourceKind}`;
    }

    function setStatus(message, options = {}) {
      const status = statusEl();
      if (!status) return;
      const text = message || "";
      status.textContent = text;
      status.classList.toggle("is-visible", Boolean(options.visible && text));
    }

    function setPaletteShellOpen(palette, nextOpen) {
      if (!palette) return;
      palette.classList.toggle("open", nextOpen);
      palette.setAttribute("aria-hidden", nextOpen ? "false" : "true");
      if (doc && doc.body) doc.body.classList.toggle("palette-open", nextOpen);
    }

    function setPaletteInputExpanded(input, expanded) {
      if (input) input.setAttribute("aria-expanded", expanded ? "true" : "false");
    }

    function setPaletteActiveDescendant(input, optionId) {
      if (!input) return;
      if (optionId) input.setAttribute("aria-activedescendant", optionId);
      else input.removeAttribute("aria-activedescendant");
    }

    function clampPaletteIndex(nextIndex) {
      if (!items.length) return 0;
      return clampInteger(nextIndex, 0, items.length - 1, index);
    }

    function optionalPaletteIndex(value) {
      if (!items.length) return null;
      const parsed = Number(value);
      if (!Number.isInteger(parsed) || parsed < 0 || parsed >= items.length) return null;
      return parsed;
    }

    function normalizePaletteText(value) {
      return String(value || "").toLowerCase().replace(/\s+/g, " ");
    }

    function paletteQueryTokens(query) {
      return String(query || "").split(/\s+/).map((token) => token.trim()).filter(Boolean);
    }

    function close() {
      if (!open) return;
      setOpen(false);
      const palette = paletteEl();
      if (!palette) return;
      setPaletteShellOpen(palette, false);
      const input = inputEl();
      if (input) {
        setPaletteInputExpanded(input, false);
        setPaletteActiveDescendant(input, "");
      }
      setStatus("");
      const previousFocus = getPreviousFocus();
      if (previousFocus && typeof previousFocus.focus === "function") {
        previousFocus.focus();
        setPreviousFocus(null);
      }
    }

    function openPalette() {
      if (open) return;
      setOpen(true);
      const palette = paletteEl();
      if (!palette) return;
      setPreviousFocus(doc.activeElement);
      setPaletteShellOpen(palette, true);
      const input = inputEl();
      if (input) {
        input.value = "";
        setPaletteInputExpanded(input, true);
        input.focus();
      }
      render("");
    }

    function buildItems(query) {
      const q = (query || "").trim();
      const dashboard = getDashboard() || {};
      const nextItems = [];
      const closeAnd = (fn) => () => {
        close();
        fn();
      };
      const queryTokens = paletteQueryTokens(q);
      const dashboardList = (key) => safeArray(dashboard[key]);
      const commandMatches = (command) => {
        if (!q) return true;
        const haystack = [command.label, command.sub, command.terms, command.key ? `source:${command.key}` : ""].join(" ");
        if (matches(haystack, q)) return true;
        return queryTokens.length > 0 && queryTokens.every((token) => matches(haystack, token));
      };
      const normalizedQuery = normalizePaletteText(q);
      const commandPriorityMatches = (command) => {
        if (normalizePaletteText(command.label) === normalizedQuery) return true;
        return safeArray(command.priorityQueries)
          .some((query) => normalizePaletteText(query) === normalizedQuery);
      };
      const simpleCommandMatches = (command) => !q || matches(command.label, q) || matches(command.sub, q);
      const paletteGroupItem = (command, group) => ({ ...command, iconCls: command.cls, group });
      const paletteRunnableItem = (command, group, run) => ({
        ...paletteGroupItem(command, group),
        run: closeAnd(run),
      });
      const mapNavCommand = (command) => ({
        icon: command.icon,
        iconCls: command.cls,
        label: `이동: ${command.label}`,
        sub: "화면 이동",
        group: "이동",
        run: closeAnd(() => setView(command.view)),
      });

      const matchedNavCommands = PAL_NAV_COMMANDS.filter(commandMatches);
      const priorityNavItems = q
        ? matchedNavCommands.filter(commandPriorityMatches).map(mapNavCommand)
        : [];
      const navItems = matchedNavCommands
        .filter((command) => !commandPriorityMatches(command))
        .map(mapNavCommand);

      const createDefs = [
        { icon: "◷", cls: "pal-icon-event", label: "새 일정", sub: "일정 추가", run: closeAnd(() => openEventModal(null)) },
        { icon: "☑", cls: "pal-icon-todo", label: "새 할 일", sub: "할 일 추가", run: closeAnd(() => openTodoModal(null)) },
        { icon: "✎", cls: "pal-icon-note", label: "새 메모", sub: "메모 추가", run: closeAnd(() => openNoteModal(null)) },
        { icon: "◉", cls: "pal-icon-habit", label: "새 습관", sub: "습관 추가", run: closeAnd(() => openHabitModal(null)) },
        { icon: "▦", cls: "pal-icon-proj", label: "새 프로젝트", sub: "프로젝트 추가", run: closeAnd(() => openProjectModal(null)) },
        { icon: "▣", cls: "pal-icon-issue", label: "새 이슈", sub: "이슈 추가", run: closeAnd(() => openIssueModal(null)) },
      ];
      const createItems = createDefs
        .filter(simpleCommandMatches)
        .map((command) => paletteGroupItem(command, "새로 만들기"));

      const deletedCount = dashboardList("deletedItems").length;
      const miscDefs = [
        { icon: "⬇", cls: "pal-icon-misc", label: "데이터 내보내기", sub: "JSON 파일로 저장", run: closeAnd(exportData) },
        { icon: "↩", cls: "pal-icon-misc", label: "최근 삭제 복구", sub: deletedCount > 0 ? `${deletedCount}개 복구/폐기` : "Settings 복구함 열기", run: closeAnd(openDeletedRecoveryPanel) },
        { icon: "◑", cls: "pal-icon-misc", label: "테마 전환", sub: "다크/라이트 모드", run: closeAnd(toggleTheme) },
        { icon: "?", cls: "pal-icon-misc", label: "단축키 도움말", sub: "키보드 단축키 목록 보기", run: closeAnd(openShortcutHelp) },
      ];
      const miscItems = miscDefs
        .filter(simpleCommandMatches)
        .map((command) => paletteGroupItem(command, "기타"));

      const kanbanSourceDefs = [
        { key: "all", icon: "▣", cls: "pal-icon-issue", label: "Kanban: 전체 출처 보기", sub: "source filter · all", terms: "kanban 칸반 source all 전체 출처" },
        { key: "wiki", icon: "◎", cls: "pal-icon-issue", label: "Kanban: LLM Wiki 출처 보기", sub: "source filter · LLM Wiki", terms: "kanban 칸반 source wiki llm wiki 위키 출처" },
        { key: "db", icon: "✺", cls: "pal-icon-issue", label: "Kanban: DB Catalog 출처 보기", sub: "source filter · DB Catalog", terms: "kanban 칸반 source db database catalog db catalog 데이터 카탈로그 출처" },
        { key: "review", icon: "◐", cls: "pal-icon-issue", label: "Kanban: Review 출처 보기", sub: "source filter · Review", terms: "kanban 칸반 source review 리뷰 검토 출처" },
        { key: "workspace-review", icon: "◐", cls: "pal-icon-issue", label: "Kanban: Workspace Review 출처 보기", sub: "source filter · Workspace Review", terms: "kanban 칸반 source review workspace workspace review 워크스페이스 리뷰 검토 출처" },
        { key: "kb-ia-review", icon: "◐", cls: "pal-icon-issue", label: "Kanban: KB/IA Review 출처 보기", sub: "source filter · KB/IA Review", terms: "kanban 칸반 source review kb ia knowledge base knowledge-base review 지식베이스 지식 베이스 IA 리뷰 검토 출처" },
        { key: "benchmark-review", icon: "◐", cls: "pal-icon-issue", label: "Kanban: PM Bench Review 출처 보기", sub: "source filter · PM Bench Review", terms: "kanban 칸반 source review pm bench benchmark pm benchmark review 벤치마크 리뷰 검토 출처" },
        { key: "source", icon: "↪", cls: "pal-icon-issue", label: "Kanban: 기타 Source 보기", sub: "source filter · Source", terms: "kanban 칸반 source other 기타 출처" },
      ];
      const kanbanSourceItems = kanbanSourceDefs
        .filter(commandMatches)
        .map((command) => paletteRunnableItem(command, "Kanban 필터", () => openKanbanSourceFilter(command.key)));

      const personalSourceDefs = [
        { key: "all", view: "todo", setFilter: setTodoSourceFilter, icon: "☑", cls: "pal-icon-todo", label: "할 일: 전체 출처 보기", sub: "source filter · all", terms: "todo task source all 전체 출처 할 일" },
        { key: "wiki", view: "todo", setFilter: setTodoSourceFilter, icon: "☑", cls: "pal-icon-todo", label: "할 일: LLM Wiki 출처 보기", sub: "source filter · LLM Wiki", terms: "todo task source wiki llm wiki 위키 출처 할 일" },
        { key: "all", view: "notes", setFilter: setNoteSourceFilter, icon: "✎", cls: "pal-icon-note", label: "메모: 전체 출처 보기", sub: "source filter · all", terms: "note memo source all 전체 출처 메모" },
        { key: "wiki", view: "notes", setFilter: setNoteSourceFilter, icon: "✎", cls: "pal-icon-note", label: "메모: LLM Wiki 출처 보기", sub: "source filter · LLM Wiki", terms: "note memo source wiki llm wiki 위키 출처 메모" },
        { key: "review", view: "notes", setFilter: setNoteSourceFilter, icon: "◐", cls: "pal-icon-note", label: "메모: Review 출처 보기", sub: "source filter · Review", terms: "note memo source review 리뷰 검토 패키지 출처 메모" },
        { key: "workspace-review", view: "notes", setFilter: setNoteSourceFilter, icon: "◐", cls: "pal-icon-note", label: "메모: Workspace Review 출처 보기", sub: "source filter · Workspace Review", terms: "note memo source review workspace workspace review 워크스페이스 리뷰 검토 패키지 출처 메모" },
        { key: "kb-ia-review", view: "notes", setFilter: setNoteSourceFilter, icon: "◐", cls: "pal-icon-note", label: "메모: KB/IA Review 출처 보기", sub: "source filter · KB/IA Review", terms: "note memo source review kb ia knowledge base knowledge-base review 지식베이스 지식 베이스 IA 리뷰 검토 패키지 출처 메모" },
        { key: "benchmark-review", view: "notes", setFilter: setNoteSourceFilter, icon: "◐", cls: "pal-icon-note", label: "메모: PM Bench Review 출처 보기", sub: "source filter · PM Bench Review", terms: "note memo source review pm bench benchmark pm benchmark review 벤치마크 리뷰 검토 패키지 출처 메모" },
      ];
      const personalSourceItems = personalSourceDefs
        .filter(commandMatches)
        .map((command) => paletteRunnableItem(command, "개인 출처 필터", () => {
          setView(command.view);
          command.setFilter(command.key);
        }));

      const wikiContext = getLlmWikiContext() || null;
      const wikiActionItems = wikiContext && wikiContext.article && wikiContext.category ? [
        {
          icon: "◎",
          cls: "pal-icon-misc",
          label: "위키 글에서 할 일 만들기",
          sub: wikiContext.article.title,
          run: closeAnd(() => createLlmWikiTodoDraft(wikiContext.category.id, wikiContext.article.id)),
        },
        {
          icon: "✎",
          cls: "pal-icon-note",
          label: "위키 글에서 메모 만들기",
          sub: wikiContext.article.title,
          run: closeAnd(() => createLlmWikiNoteDraft(wikiContext.category.id, wikiContext.article.id)),
        },
        {
          icon: "▣",
          cls: "pal-icon-issue",
          label: "위키 글에서 이슈 만들기",
          sub: wikiContext.article.title,
          run: closeAnd(() => createLlmWikiIssueDraft(wikiContext.category.id, wikiContext.article.id)),
        },
      ]
        .filter((command) => simpleCommandMatches(command) || matches(wikiContext.category.title, q))
        .map((command) => paletteGroupItem(command, "위키 실행"))
        : [];

      let hitItems = [];
      if (q) {
        const records = [];
        dashboardList("events").forEach((event) => records.push({
          label: event.title || "",
          aux: event.location || "",
          icon: "◷",
          iconCls: "pal-icon-event",
          sub: `일정 · ${formatKoreanShort(event.date)}`,
          group: "검색 결과",
          run: closeAnd(() => openEventModal(event)),
        }));
        dashboardList("todos").forEach((todo) => records.push({
          label: todo.text || todo.title || "(할 일)",
          aux: `${todo.category || ""} ${todo.memo || ""} ${recordSourceSearchText(todo, "todo")}`,
          icon: "☑",
          iconCls: "pal-icon-todo",
          sub: `할 일${todo.done ? " · 완료" : ""}${recordSourceLabel(todo, "todo")}`,
          group: "검색 결과",
          run: closeAnd(() => openTodoRecord(todo)),
        }));
        dashboardList("notes").forEach((note) => records.push({
          label: note.title || "(제목 없음)",
          aux: `${note.body || ""} ${recordSourceSearchText(note, "note")}`,
          icon: "✎",
          iconCls: "pal-icon-note",
          sub: `메모${recordSourceLabel(note, "note")}`,
          group: "검색 결과",
          run: closeAnd(() => openNoteRecord(note)),
        }));
        dashboardList("habits").forEach((habit) => records.push({
          label: habit.name || "",
          aux: "",
          icon: "◉",
          iconCls: "pal-icon-habit",
          sub: "습관",
          group: "검색 결과",
          run: closeAnd(() => {
            setView("habits");
            openHabitModal(habit);
          }),
        }));
        dashboardList("projects").forEach((project) => records.push({
          label: project.name || "",
          aux: project.owner || "",
          icon: "▦",
          iconCls: "pal-icon-proj",
          sub: `프로젝트 · ${project.owner || ""}`,
          group: "검색 결과",
          run: closeAnd(() => {
            setView("pm-portfolio");
            openProjectModal(project);
          }),
        }));
        dashboardList("issues").forEach((issue) => records.push({
          label: issue.title || "",
          aux: `${issue.id || ""} ${safeArray(issue.labels).join(" ")} ${issueSourceSearchText(issue)} ${issue.body || ""}`,
          icon: "▣",
          iconCls: "pal-icon-issue",
          sub: `이슈 · ${issue.id}${issueSourceLabel(issue)}`,
          group: "검색 결과",
          run: closeAnd(() => openIssueRecord(issue)),
        }));
        const recordMatchesQuery = (record) => {
          const haystack = [record.label, record.aux, record.sub].join(" ");
          if (matches(record.label, q) || matches(record.aux, q) || matches(record.sub, q)) return true;
          return queryTokens.length > 0 && queryTokens.every((token) => matches(haystack, token));
        };
        const exactTokenHits = records.filter(recordMatchesQuery);

        const FuseCtor = getFuse();
        if (typeof FuseCtor === "function") {
          const fuse = new FuseCtor(records, {
            keys: [{ name: "label", weight: 0.7 }, { name: "aux", weight: 0.3 }],
            threshold: 0.4,
            ignoreLocation: true,
            minMatchCharLength: 1,
            includeScore: true,
          });
          const fuseHits = fuse.search(q, { limit: maxHits }).map((result) => result.item);
          hitItems = uniqueByIdentity([...exactTokenHits, ...fuseHits]).slice(0, maxHits);
        } else {
          hitItems = records
            .filter(recordMatchesQuery)
            .slice(0, maxHits);
        }
      }

      if (q && hitItems.length > 0) {
        nextItems.push(...priorityNavItems, ...hitItems, ...navItems, ...createItems, ...personalSourceItems, ...kanbanSourceItems, ...wikiActionItems, ...miscItems);
      } else {
        nextItems.push(...priorityNavItems, ...navItems, ...createItems, ...personalSourceItems, ...kanbanSourceItems, ...wikiActionItems, ...miscItems);
      }
      return nextItems;
    }

    function render(query) {
      const results = resultsEl();
      if (!results) return;
      const input = inputEl();
      items = buildItems(query);
      index = 0;

      if (items.length === 0) {
        results.innerHTML = "";
        setStatus("검색 결과가 없습니다. 다른 검색어를 입력하세요.", { visible: true });
        setPaletteActiveDescendant(input, "");
        return;
      }

      setStatus(`${items.length}개 결과. 위아래 화살표로 이동하고 Enter로 실행하세요.`);
      let output = "";
      let currentGroup = null;
      items.forEach((item, itemIndex) => {
        if (item.group !== currentGroup) {
          currentGroup = item.group;
          output += paletteGroupHTML(currentGroup);
        }
        output += paletteItemHTML(item, itemIndex);
      });
      results.innerHTML = output;
      setPaletteActiveDescendant(input, paletteOptionId(0));
    }

    function setIndex(nextIndex) {
      if (!items.length) return;
      index = clampPaletteIndex(nextIndex);

      const results = resultsEl();
      const input = inputEl();
      if (!results) return;
      results.querySelectorAll(".pal-item").forEach((button) => {
        const buttonIndex = paletteOptionIndex(button);
        const active = buttonIndex === index;
        button.classList.toggle("is-active", active);
        button.setAttribute("aria-selected", String(active));
        if (active) {
          if (button.id) setPaletteActiveDescendant(input, button.id);
          button.scrollIntoView({ block: "nearest" });
        }
      });
    }

    function runIndex(runAt) {
      const nextIndex = optionalPaletteIndex(runAt);
      if (nextIndex === null) return;
      const item = items[nextIndex];
      if (item && typeof item.run === "function") item.run();
    }

    function paletteGroupHTML(group) {
      return `<div class="pal-group">${escape(group)}</div>`;
    }

    function paletteItemHTML(item, itemIndex) {
      const active = itemIndex === 0 ? " is-active" : "";
      let output = `<button type="button" id="${paletteOptionId(itemIndex)}" class="pal-item${active}" data-pal-index="${itemIndex}" role="option" aria-selected="${itemIndex === 0}">`;
      output += `<span class="pal-icon ${escape(item.iconCls || "pal-icon-misc")}">${escape(item.icon)}</span>`;
      output += `<span class="pal-text">`;
      output += `<span class="pal-label">${escape(item.label)}</span>`;
      if (item.sub) output += `<span class="pal-sub">${escape(item.sub)}</span>`;
      output += `</span></button>`;
      return output;
    }

    function handleInputChange(event) {
      render(event && event.target ? event.target.value : "");
    }

    function handleInputKeydown(event) {
      if (event.key === "ArrowDown") {
        event.preventDefault();
        setIndex(index + 1);
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        setIndex(index - 1);
      } else if (event.key === "Enter") {
        event.preventDefault();
        runIndex(index);
      } else if (event.key === "Escape") {
        event.preventDefault();
        close();
      }
    }

    function handleResultClick(event) {
      const button = paletteOptionButton(event);
      if (!button) return;
      const nextIndex = paletteOptionIndex(button);
      if (nextIndex === null) return;
      runIndex(nextIndex);
    }

    function handleResultMousemove(event) {
      const button = paletteOptionButton(event);
      if (!button) return;
      const nextIndex = paletteOptionIndex(button);
      if (nextIndex === null) return;
      if (nextIndex !== index) setIndex(nextIndex);
    }

    function setup() {
      const input = inputEl();
      if (input) {
        input.addEventListener("input", handleInputChange);
        input.addEventListener("keydown", handleInputKeydown);
      }

      const results = resultsEl();
      if (results) {
        results.addEventListener("click", handleResultClick);
        results.addEventListener("mousemove", handleResultMousemove);
      }
    }

    return Object.freeze({
      version: VERSION,
      el: paletteEl,
      input: inputEl,
      results: resultsEl,
      status: statusEl,
      isOpen,
      setStatus,
      open: openPalette,
      close,
      buildItems,
      render,
      setIndex,
      runIndex,
      setup,
    });
  }

  global.JooParkCommandPalette = Object.freeze({
    version: VERSION,
    create: createCommandPalette,
    navCommands: Object.freeze(PAL_NAV_COMMANDS.map((item) => ({ ...item }))),
  });
})(typeof window !== "undefined" ? window : globalThis);
