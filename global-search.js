(function (root) {
  "use strict";

  const VERSION = "joopark-global-search/v1";
  const SEARCH_INERT_VIEWS = new Set(["home", "stats", "settings", "system"]);
  const SEARCH_VIEW_PLACEHOLDER = "현재 뷰 안에서 검색... (/)";
  const SEARCH_INERT_PLACEHOLDER = "요약 화면 · ⌘K로 이동/검색";
  const SEARCH_VIEW_LABEL = "현재 뷰 검색";
  const SEARCH_INERT_LABEL = "이 화면은 현재 뷰 검색을 지원하지 않음. 명령 팔레트로 이동 또는 통합 검색";
  const SEARCH_INERT_HINT = "이 화면은 요약 전용입니다. ⌘K로 이동·통합 검색을 여세요.";

  function noop() {}

  function createGlobalSearch(deps) {
    const options = deps || {};
    const documentRef = options.document || root.document;
    const windowRef = options.window || root;
    const refs = options.refs || {};
    const state = options.state || {};
    const getCurrentView = typeof options.getCurrentView === "function" ? options.getCurrentView : function defaultCurrentView() { return "home"; };
    const renderCurrentView = typeof options.renderCurrentView === "function" ? options.renderCurrentView : noop;
    const openPalette = typeof options.openPalette === "function" ? options.openPalette : noop;
    const debounce = typeof options.debounce === "function"
      ? options.debounce
      : function fallbackDebounce(fn) {
          return function debouncedFallback(...args) {
            return fn.apply(this, args);
          };
        };

    function isInertView(view = getCurrentView()) {
      return SEARCH_INERT_VIEWS.has(view);
    }

    function currentViewNode() {
      return refs.views && refs.views[getCurrentView()];
    }

    function searchEmptyNode(view = currentViewNode()) {
      return view ? view.querySelector("[data-search-empty]") : null;
    }

    function clearControl() {
      if (!refs.searchClear) return;
      refs.searchClear.hidden = isInertView() || !state.query;
    }

    function status() {
      if (!state.query || isInertView()) return "";
      const view = currentViewNode();
      if (!view) return "";
      const empty = searchEmptyNode(view);
      if (empty) return "검색 결과 없음";
      const resultCount = view.querySelectorAll("[data-search-result]").length;
      if (resultCount > 0) return `${resultCount}개 결과`;
      return "현재 뷰에서 필터링";
    }

    function syncAffordance({ announce = false } = {}) {
      const inert = isInertView();
      const shell = refs.query ? refs.query.closest(".search") : null;
      if (shell) {
        shell.classList.toggle("is-inert", inert);
        shell.dataset.searchScope = inert ? "command" : "view";
        shell.title = inert ? SEARCH_INERT_HINT : "현재 화면의 항목을 필터링합니다.";
      }
      if (refs.query) {
        refs.query.placeholder = inert ? SEARCH_INERT_PLACEHOLDER : SEARCH_VIEW_PLACEHOLDER;
        refs.query.setAttribute("aria-label", inert ? SEARCH_INERT_LABEL : SEARCH_VIEW_LABEL);
        refs.query.setAttribute("aria-readonly", inert ? "true" : "false");
        refs.query.readOnly = inert;
        if (inert && refs.query.value) refs.query.value = "";
      }
      if (inert && state.query) state.query = "";
      if (refs.searchCount) {
        refs.searchCount.textContent = inert && announce ? SEARCH_INERT_HINT : status();
      }
      clearControl();
    }

    function announceInert() {
      if (isInertView()) syncAffordance({ announce: true });
    }

    function revealEmptyIfNeeded() {
      if (!state.query || isInertView()) return;
      const empty = searchEmptyNode();
      if (!empty) return;
      const reveal = () => {
        const targetOffset = Math.min(128, Math.max(72, Math.round(windowRef.innerHeight * 0.22)));
        const main = documentRef.querySelector(".main");
        const mainStyle = main ? windowRef.getComputedStyle(main) : null;
        const mainScrollable = main && main.scrollHeight > main.clientHeight + 1 && mainStyle && mainStyle.overflowY !== "visible";
        if (mainScrollable) {
          const mainRect = main.getBoundingClientRect();
          const emptyRect = empty.getBoundingClientRect();
          const targetTop = Math.max(0, main.scrollTop + emptyRect.top - mainRect.top - targetOffset);
          main.scrollTo({ top: targetTop, behavior: "auto" });
          return;
        }
        const emptyRect = empty.getBoundingClientRect();
        const targetTop = Math.max(0, windowRef.scrollY + emptyRect.top - targetOffset);
        windowRef.scrollTo({ top: targetTop, behavior: "auto" });
        empty.scrollIntoView({ block: "center", inline: "nearest", behavior: "auto" });
      };
      reveal();
      windowRef.requestAnimationFrame(reveal);
    }

    const onSearchInput = debounce(() => {
      if (isInertView()) {
        state.query = "";
        if (refs.query) refs.query.value = "";
        syncAffordance({ announce: true });
        return;
      }
      clearControl();
      renderCurrentView();
      if (refs.searchCount) refs.searchCount.textContent = status();
      revealEmptyIfNeeded();
    }, 140);

    function clear() {
      state.query = "";
      if (refs.query) refs.query.value = "";
      const inert = isInertView();
      if (!inert) renderCurrentView();
      if (refs.searchCount) refs.searchCount.textContent = "";
      clearControl();
      if (refs.query) refs.query.focus();
      if (inert) announceInert();
    }

    function setup() {
      if (!refs.query || refs.query.dataset.globalSearchBound === "true") return;
      refs.query.dataset.globalSearchBound = "true";
      refs.query.addEventListener("focus", announceInert);
      refs.query.addEventListener("keydown", (event) => {
        if (!isInertView()) return;
        const printable = event.key && event.key.length === 1;
        if (!printable || event.metaKey || event.ctrlKey || event.altKey) return;
        event.preventDefault();
        openPalette();
      });
      refs.query.addEventListener("keydown", (event) => {
        if (isInertView() || event.key !== "Escape" || !state.query) return;
        event.preventDefault();
        event.stopPropagation();
        clear();
      });
      refs.query.addEventListener("input", (event) => {
        if (isInertView()) {
          event.target.value = "";
          state.query = "";
          syncAffordance({ announce: true });
          return;
        }
        state.query = event.target.value;
        clearControl();
        onSearchInput();
      });
    }

    return {
      version: VERSION,
      isInertView,
      clearControl,
      syncAffordance,
      announceInert,
      status,
      revealEmptyIfNeeded,
      clear,
      setup,
    };
  }

  root.JooParkGlobalSearch = {
    version: VERSION,
    create: createGlobalSearch,
  };
})(window);
