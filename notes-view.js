(function (root) {
  "use strict";

  const VERSION = "joopark-notes-view/v1";

  function createNotesView(deps) {
    const options = deps || {};
    const html = options.html;
    const raw = options.raw;
    const matches = typeof options.matches === "function" ? options.matches : function () { return true; };
    const safeNoteColor = typeof options.safeNoteColor === "function" ? options.safeNoteColor : function (value) { return value || "var(--cyan)"; };
    const renderMarkdown = typeof options.renderMarkdown === "function" ? options.renderMarkdown : function () { return null; };
    const formatKoreanShort = typeof options.formatKoreanShort === "function" ? options.formatKoreanShort : function (value) { return value || ""; };
    const localYmd = typeof options.localYmd === "function" ? options.localYmd : function (value) { return value || ""; };
    const searchEmptyState = typeof options.searchEmptyState === "function" ? options.searchEmptyState : function () { return ""; };
    const noteSourceFilters = Array.isArray(options.noteSourceFilters) ? options.noteSourceFilters : [];

    if (typeof html !== "function" || typeof raw !== "function") {
      throw new Error("notes view requires html and raw helpers");
    }

    function isReviewNoteSource(note) {
      const sourceKey = String(note && note.sourceKey || "");
      return sourceKey.startsWith("workspace-review:")
        || sourceKey.startsWith("kb-ia-review:")
        || sourceKey.startsWith("benchmark-review:");
    }

    function noteMatchesSourceFilter(note, sourceFilter) {
      const sourceKey = String(note && note.sourceKey || "");
      switch (sourceFilter) {
        case "wiki": return sourceKey.startsWith("llm-wiki:note:");
        case "review": return isReviewNoteSource(note);
        case "workspace-review": return sourceKey.startsWith("workspace-review:");
        case "kb-ia-review": return sourceKey.startsWith("kb-ia-review:");
        case "benchmark-review": return sourceKey.startsWith("benchmark-review:");
        default: return true;
      }
    }

    function notesViewModel(input) {
      const data = input || {};
      const notes = Array.isArray(data.notes) ? data.notes : [];
      const q = data.query || "";
      const sourceFilter = data.sourceFilter || "all";
      const base = notes.filter((note) => matches(`${note.title} ${note.body}`, q));
      const sourceCounts = noteSourceFilters.reduce((acc, filter) => {
        acc[filter.key] = filter.key === "all"
          ? base.length
          : base.filter((note) => noteMatchesSourceFilter(note, filter.key)).length;
        return acc;
      }, { all: base.length });
      const activeSourceLabel = (noteSourceFilters.find((item) => item.key === sourceFilter) || {}).label || "전체 출처";
      const list = base
        .filter((note) => noteMatchesSourceFilter(note, sourceFilter))
        .sort((a, b) => {
          if (!!a.pinned !== !!b.pinned) return a.pinned ? -1 : 1;
          return (b.updatedAt || "") < (a.updatedAt || "") ? -1 : 1;
        });
      return {
        notes,
        q,
        list,
        pinnedCount: notes.filter((note) => note.pinned).length,
        sourceFilter,
        sourceCounts,
        activeSourceLabel,
      };
    }

    function noteBodyPreview(note) {
      const body = (note.body || "").trim();
      const rendered = body ? renderMarkdown(body) : null;
      const isMarkdown = body && rendered != null;
      const bodyContent = body
        ? (isMarkdown ? raw(rendered) : (body.length > 220 ? body.slice(0, 220) + "…" : body))
        : "내용 없음";
      return { bodyContent, isMarkdown };
    }

    function reviewNoteSourceMeta(note) {
      const sourceKey = String(note && note.sourceKey || "");
      const sources = [
        { prefix: "workspace-review:", label: "Workspace review 패키지", shortLabel: "Workspace" },
        { prefix: "kb-ia-review:", label: "KB/IA review 패키지", shortLabel: "KB/IA" },
        { prefix: "benchmark-review:", label: "PM benchmark review 패키지", shortLabel: "PM Bench" },
      ];
      const source = sources.find((item) => sourceKey.startsWith(item.prefix));
      return source ? { ...source, sourceKey } : null;
    }

    function noteSourceReturnButton(note) {
      const sourceKey = String(note && note.sourceKey || "");
      const prefix = "llm-wiki:note:";
      const title = note && note.title ? note.title : "메모";
      if (!sourceKey.startsWith(prefix) || !sourceKey.slice(prefix.length)) return "";
      return html`
        <button type="button" class="local-source-badge local-source-wiki" data-action="open-llm-wiki-source" data-source-record-kind="note" data-source-record-id="${note.id}" data-source-key="${sourceKey}" data-source-article-id="${sourceKey.slice(prefix.length)}" title="LLM Wiki 원문 보기" aria-label="${title} LLM Wiki 원문 보기">LLM Wiki</button>
      `;
    }

    function noteReviewSourceReturnButton(note) {
      const meta = reviewNoteSourceMeta(note);
      if (!meta) return "";
      const title = note && note.title ? note.title : "메모";
      return html`
        <button type="button" class="local-source-badge local-source-review" data-action="open-review-record-source" data-source-kind="review" data-source-record-kind="note" data-source-record-id="${note.id}" data-source-key="${meta.sourceKey}" data-review-source-label="${meta.label}" data-review-source-short-label="${meta.shortLabel}" title="${meta.label} 보기" aria-label="${title} ${meta.label} 보기">${meta.shortLabel}</button>
      `;
    }

    function noteCard(note) {
      const noteTitle = note.title || "(제목 없음)";
      const color = safeNoteColor(note.color);
      const preview = noteBodyPreview(note);
      return html`
        <article class="note-card ${raw(note.pinned ? "is-pinned" : "")}" style="--note:${raw(color)}" data-search-result="notes">
          <button type="button" class="note-open" data-action="open-note" data-note-id="${note.id}">
            <strong class="note-title">${noteTitle}</strong>
          </button>
          <div class="note-body ${raw(preview.isMarkdown ? "markdown-body" : "")}">${preview.bodyContent}</div>
          <div class="note-foot">
            <small>${note.updatedAt ? formatKoreanShort(localYmd(note.updatedAt)) : ""}</small>
            <span class="note-actions">
              ${raw(noteSourceReturnButton(note))}
              ${raw(noteReviewSourceReturnButton(note))}
              <button type="button" class="note-pin ${raw(note.pinned ? "is-on" : "")}" data-action="note-pin" data-note-id="${note.id}" aria-pressed="${raw(note.pinned ? "true" : "false")}" aria-label="${noteTitle} ${note.pinned ? "고정 해제" : "고정"}">${raw(note.pinned ? "★" : "☆")}</button>
              <button type="button" class="note-del" data-action="note-delete" data-note-id="${note.id}" aria-label="${noteTitle} 삭제">✕</button>
            </span>
          </div>
        </article>
      `;
    }

    function notesToolbarHTML(model) {
      return html`
        <section class="notes-toolbar">
          <div><strong>${model.notes.length}</strong>개의 메모${model.pinnedCount ? raw(html` · 고정 ${model.pinnedCount}개`) : ""}</div>
          <button type="button" class="primary-btn" data-action="note-add">+ 메모</button>
        </section>
      `;
    }

    function notesSourceFilterHTML(model) {
      if (!model || (model.sourceCounts.wiki === 0 && model.sourceCounts.review === 0 && model.sourceFilter === "all")) return "";
      return html`
        <section class="seg-control source-filter-control" data-note-source-filterbar data-note-source-filter-current="${model.sourceFilter}">
          ${raw(noteSourceFilters.map((filter) => {
            const count = model.sourceCounts[filter.key] || 0;
            return html`
              <button type="button" class="seg-chip ${raw(model.sourceFilter === filter.key ? "is-active" : "")}" data-action="note-source-filter" data-note-source-filter="${filter.key}" data-note-source-filter-count="${count}" aria-pressed="${raw(model.sourceFilter === filter.key ? "true" : "false")}">${filter.label} <span>${count}</span></button>
            `;
          }).join(""))}
        </section>
      `;
    }

    function notesGridHTML(model) {
      const cards = model.list.length === 0
        ? (model.q
          ? searchEmptyState("notes", "검색 결과가 없습니다", "메모 제목이나 본문과 일치하는 항목이 없습니다.")
          : model.sourceFilter !== "all"
            ? html`
              <article class="empty empty-action" data-note-source-empty="${model.sourceFilter}">
                <strong>${model.activeSourceLabel} 메모가 없습니다</strong>
                <span>출처 필터를 전체로 돌리면 모든 로컬 메모를 다시 볼 수 있습니다.</span>
                <button type="button" class="secondary-btn" data-action="note-source-filter" data-note-source-filter="all">전체 출처 보기</button>
              </article>
            `
          : html`<article class="empty">메모가 없습니다. + 메모로 추가해 보세요.</article>`)
        : model.list.map((note) => noteCard(note)).join("");
      return html`<section class="notes-grid">${raw(cards)}</section>`;
    }

    function renderNotesHTML(input) {
      const model = notesViewModel(input);
      return html`
        ${raw(notesToolbarHTML(model))}
        ${raw(notesSourceFilterHTML(model))}
        ${raw(notesGridHTML(model))}
      `;
    }

    return {
      version: VERSION,
      isReviewNoteSource,
      noteMatchesSourceFilter,
      notesViewModel,
      noteBodyPreview,
      reviewNoteSourceMeta,
      noteSourceReturnButton,
      noteReviewSourceReturnButton,
      noteCard,
      notesToolbarHTML,
      notesSourceFilterHTML,
      notesGridHTML,
      renderNotesHTML,
    };
  }

  root.JooParkNotesView = {
    version: VERSION,
    create: createNotesView,
  };
})(window);
