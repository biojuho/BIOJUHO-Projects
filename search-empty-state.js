(function (root) {
  "use strict";

  const VERSION = "joopark-search-empty-state/v1";

  function createSearchEmptyState(deps) {
    const options = deps || {};
    const html = options.html;

    if (typeof html !== "function") {
      throw new Error("search empty state requires html helper");
    }

    function searchEmptyState(kind, title, description) {
      return html`
        <article class="empty empty-action" role="status" aria-live="polite" data-search-empty="${kind}">
          <strong>${title}</strong>
          <span>${description}</span>
          <button type="button" class="primary-btn" data-action="clear-search">검색 초기화</button>
        </article>
      `;
    }

    return {
      version: VERSION,
      searchEmptyState,
    };
  }

  root.JooParkSearchEmptyState = {
    version: VERSION,
    create: createSearchEmptyState,
  };
})(window);
