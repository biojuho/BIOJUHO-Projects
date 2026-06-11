(function (global) {
  "use strict";

  const VERSION = "joopark-db-catalog/v1";
  const DB_HEALTH_MAP = { green: "녹색", amber: "주황", red: "적색" };
  const DB_HEALTH_ORDER = ["green", "amber", "red"];
  const MIG_STATUS_MAP = { pending: "대기", review: "검토", applied: "적용", "rolled-back": "롤백" };
  const MIG_STATUS_ORDER = ["pending", "review", "applied", "rolled-back"];
  const SAMPLE_AS_OF = "2026-05-29";
  const SOURCE_LABELS = { sample: "sample", manual: "manual", imported: "imported" };
  const STALE_REVIEW_SOURCE_KEY = "db-catalog:stale-sample-review";
  const DEFAULT_CATALOG_CARD_RENDER_LIMIT = 80;
  const DEFAULT_CATALOG_ROW_RENDER_LIMIT = 160;
  const DB_CATALOG_FILTERS = [
    { key: "all", label: "all", empty: "카탈로그 기록" },
    { key: "stale-sample", label: "stale sample", empty: "stale sample 기록" },
    { key: "manual", label: "manual", empty: "manual 기록" },
    { key: "imported", label: "imported", empty: "imported 기록" },
  ];

  function createDbCatalog(deps = {}) {
    const document = deps.document || global.document;
    const dashboard = deps.dashboard || {};
    const state = deps.state || {};
    const refs = deps.refs || {};
    const indexes = deps.indexes || {};
    const html = deps.html;
    const raw = deps.raw || ((value) => value);
    const setHTML = deps.setHTML || (() => {});
    const matches = deps.matches || (() => false);
    const escapeHtml = deps.escapeHtml || ((value) => String(value || ""));
    const clampInteger = typeof deps.clampInteger === "function"
      ? deps.clampInteger
      : function (value, min, max = Number.POSITIVE_INFINITY, fallback = 0) {
        const parsed = Number(value);
        const safeParsed = Number.isFinite(parsed) ? parsed : fallback;
        return Math.min(max, Math.max(min, Math.trunc(safeParsed)));
      };
    const clampNumber = typeof deps.clampNumber === "function"
      ? deps.clampNumber
      : function (value, min, max = Number.POSITIVE_INFINITY, fallback = 0) {
        const parsed = Number(value);
        const safeParsed = Number.isFinite(parsed) ? parsed : fallback;
        return Math.min(max, Math.max(min, safeParsed));
      };
    const HEALTH_COLOR = deps.HEALTH_COLOR || {};
    const panelHead = deps.panelHead || (() => "");
    const kpiCard = deps.kpiCard || (() => "");
    const spark = deps.spark || (() => "");
    const searchEmptyState = deps.searchEmptyState || (() => "");
    const currentInstance = deps.currentInstance || (() => null);
    const todayISO = deps.todayISO || (() => "");
    const parseDate = deps.parseDate || ((value) => new Date(value));
    const uid = deps.uid || ((prefix) => `${prefix}-${Date.now()}`);
    const nowISO = deps.nowISO || (() => new Date().toISOString());
    const formatLocalDateTime = deps.formatLocalDateTime || ((value) => value);
    const rebuildIndexes = deps.rebuildIndexes || (() => {});
    const commit = deps.commit || (() => {});
    const showToast = deps.showToast || (() => {});
    const showUndoToast = deps.showUndoToast || ((message) => showToast(message, "info"));
    const cloneRecord = deps.cloneRecord || ((value) => JSON.parse(JSON.stringify(value)));
    const captureDeletedItem = deps.captureDeletedItem || (() => "");
    const dropDeletedItem = deps.dropDeletedItem || (() => false);
    const canUndoDeletedItem = deps.canUndoDeletedItem || (() => true);
    const restoreDeletedArrayItem = deps.restoreDeletedArrayItem || ((list, index, item) => {
      if (!Array.isArray(list) || !item) return false;
      if (item.id && list.some((entry) => entry && entry.id === item.id)) return false;
      list.splice(Math.min(Math.max(index, 0), list.length), 0, cloneRecord(item));
      return true;
    });
    const openModal = deps.openModal || (() => {});
    const closeModal = deps.closeModal || (() => {});
    const closeSheet = deps.closeSheet || (() => {});
    const openTableSheet = deps.openTableSheet || (() => {});
    const catalogCardRenderLimit = clampInteger(deps.catalogCardRenderLimit, 20, Number.POSITIVE_INFINITY, DEFAULT_CATALOG_CARD_RENDER_LIMIT);
    const catalogRowRenderLimit = clampInteger(deps.catalogRowRenderLimit, 40, Number.POSITIVE_INFINITY, DEFAULT_CATALOG_ROW_RENDER_LIMIT);

    function virtualListNote(kind, total, rendered) {
      const hidden = total - rendered;
      if (hidden <= 0) return "";
      return html`
        <div class="virtual-list-note db-virtual-note" role="status" data-db-virtualized="true" data-db-virtual-kind="${kind}" data-db-virtual-rendered="${rendered}" data-db-virtual-total="${total}">
          <strong>${hidden}개 더 있음</strong>
          <span>검색어나 카탈로그 필터를 좁히면 숨겨진 기록을 바로 찾을 수 있습니다.</span>
        </div>
      `;
    }

    function catalogForm(selector) {
      return document ? document.querySelector(selector) : null;
    }

    function catalogFormData(selector) {
      const form = catalogForm(selector);
      return form ? new FormData(form) : null;
    }

    function catalogSource(record) {
      const source = record && record.catalogSource;
      return SOURCE_LABELS[source] ? source : "sample";
    }

    function parseCatalogDate(value) {
      const text = String(value || "").trim();
      if (!text) return null;
      const normalized = text.includes(" ") && !text.includes("T") ? text.replace(" ", "T") : text;
      const date = new Date(normalized);
      return Number.isNaN(date.getTime()) ? null : date;
    }

    function catalogUpdatedAt(record, fallback = SAMPLE_AS_OF) {
      return String(record?.catalogUpdatedAt || record?.updatedAt || record?.lastRun || record?.appliedAt || record?.scheduledAt || record?.date || fallback || SAMPLE_AS_OF).trim();
    }

    function catalogFreshness(record, fallback = SAMPLE_AS_OF) {
      const source = catalogSource(record);
      const updatedAt = catalogUpdatedAt(record, fallback);
      const updatedDate = parseCatalogDate(updatedAt);
      const todayDate = parseCatalogDate(todayISO());
      const ageDays = updatedDate && todayDate
        ? Math.max(0, Math.floor((todayDate.getTime() - updatedDate.getTime()) / 86400000))
        : null;
      const stale = source === "sample" || (Number.isFinite(ageDays) && ageDays > 7);
      return {
        source,
        updatedAt,
        ageDays,
        status: stale ? "stale" : "fresh",
        label: Number.isFinite(ageDays) ? `${source} · ${ageDays}d` : source,
      };
    }

    function activeCatalogFilter() {
      const current = String(state.dbCatalogFilter || "all").trim();
      return DB_CATALOG_FILTERS.some((option) => option.key === current) ? current : "all";
    }

    function catalogFilterLabel(filter = activeCatalogFilter()) {
      const option = DB_CATALOG_FILTERS.find((item) => item.key === filter);
      return option ? option.label : "all";
    }

    function recordMatchesCatalogFilter(record, filter = activeCatalogFilter(), fallback = SAMPLE_AS_OF) {
      if (filter === "all") return true;
      const meta = catalogFreshness(record, fallback);
      if (filter === "stale-sample") return meta.source === "sample" && meta.status === "stale";
      if (filter === "manual") return meta.source === "manual";
      if (filter === "imported") return meta.source === "imported";
      return true;
    }

    function allCatalogRecords() {
      const tables = (Array.isArray(dashboard.schemas) ? dashboard.schemas : [])
        .flatMap((schema) => (schema.databases || []).flatMap((db) => (db.tables || [])));
      return [
        ...(Array.isArray(dashboard.dbInstances) ? dashboard.dbInstances : []),
        ...tables,
        ...(Array.isArray(dashboard.queries) ? dashboard.queries : []),
        ...(Array.isArray(dashboard.backups) ? dashboard.backups : []),
        ...(Array.isArray(dashboard.migrations) ? dashboard.migrations : []),
      ];
    }

    function catalogBoundaryModel() {
      const records = allCatalogRecords();
      const filter = activeCatalogFilter();
      const counts = records.reduce((acc, record) => {
        const meta = catalogFreshness(record);
        acc.total += 1;
        acc[meta.source] = (acc[meta.source] || 0) + 1;
        if (meta.status === "stale") acc.stale += 1;
        if (meta.source === "sample" && meta.status === "stale") acc.staleSample += 1;
        if (recordMatchesCatalogFilter(record, filter)) acc.filtered += 1;
        return acc;
      }, { total: 0, sample: 0, manual: 0, imported: 0, stale: 0, staleSample: 0, filtered: 0 });
      return counts;
    }

    function catalogBadgeHTML(record, fallback = SAMPLE_AS_OF) {
      const meta = catalogFreshness(record, fallback);
      return html`<span class="db-source-badge db-source-${raw(meta.source)} db-freshness-${raw(meta.status)}" data-db-catalog-source="${meta.source}" data-db-catalog-freshness-status="${meta.status}" data-db-catalog-updated-at="${meta.updatedAt}" data-db-catalog-age-days="${meta.ageDays == null ? "" : meta.ageDays}">${meta.label}</span>`;
    }

    function catalogFilterCount(summary, key) {
      if (key === "all") return summary.total;
      if (key === "stale-sample") return summary.staleSample;
      return summary[key] || 0;
    }

    function catalogFilterBarHTML(summary) {
      const selected = activeCatalogFilter();
      return html`
        <div class="db-catalog-filterbar" role="group" aria-label="DB catalog provenance filter" data-db-catalog-filterbar data-db-catalog-filter-current="${selected}">
          ${raw(DB_CATALOG_FILTERS.map((option) => html`
            <button type="button" class="db-catalog-filter-btn ${raw(selected === option.key ? "is-active" : "")}" data-action="db-catalog-filter" data-db-catalog-filter-option="${option.key}" aria-pressed="${selected === option.key}">
              <span>${option.label}</span>
              <b>${catalogFilterCount(summary, option.key)}</b>
            </button>
          `).join(""))}
        </div>
      `;
    }

    function staleReviewIssue() {
      const issues = Array.isArray(dashboard.issues) ? dashboard.issues : [];
      return issues.find((issue) => issue && issue.sourceKey === STALE_REVIEW_SOURCE_KEY) || null;
    }

    function staleCatalogActionHTML(summary) {
      if (!summary.staleSample) return "";
      const existing = staleReviewIssue();
      const buttonLabel = existing ? "검증 이슈 열기" : "검증 이슈 만들기";
      const status = existing ? `created · ${existing.id}` : "ready";
      return html`
        <div class="db-catalog-stale-action" data-db-catalog-stale-action data-db-catalog-stale-action-count="${summary.staleSample}" data-db-catalog-stale-action-existing="${raw(existing ? "true" : "false")}" data-db-catalog-stale-action-issue-id="${existing ? existing.id : ""}">
          <span>
            <strong>stale sample review</strong>
            <small>${summary.staleSample} records · ${status}</small>
          </span>
          <button type="button" class="secondary-btn" data-action="db-catalog-create-stale-issue">${buttonLabel}</button>
        </div>
      `;
    }

    function issueSourceBacklinkHTML() {
      const link = state.issueSourceBacklink || null;
      if (!link || link.surface !== "db-catalog") return "";
      const issueById = indexes.issueById;
      const issue = issueById && typeof issueById.get === "function" ? issueById.get(link.issueId) : null;
      if (!issue || (link.sourceKey && issue.sourceKey !== link.sourceKey)) return "";
      return html`
        <section class="source-backlink db-source-backlink" data-source-backlink data-source-backlink-surface="db-catalog" data-source-backlink-issue-id="${issue.id}" data-source-backlink-source="${link.sourceLabel || "DB Catalog"}">
          <span>
            <strong>${link.sourceLabel || "DB Catalog"}에서 열린 이슈</strong>
            <small>${issue.id} · ${issue.title || issue.id}</small>
          </span>
          <button type="button" class="secondary-btn" data-action="open-source-backlink-issue" data-issue-id="${issue.id}">Kanban 이슈로 돌아가기</button>
        </section>
      `;
    }

    function catalogFilterEmptyHTML(surfaceLabel) {
      const label = catalogFilterLabel();
      return html`
        <article class="empty empty-action db-catalog-filter-empty" role="status" aria-live="polite" data-db-catalog-filter-empty="${surfaceLabel}" data-db-catalog-filter-empty-label="${label}">
          <strong>${label} 결과가 없습니다</strong>
          <span>${surfaceLabel}에서 현재 provenance 필터와 일치하는 로컬 카탈로그 기록이 없습니다.</span>
          <button type="button" class="primary-btn" data-action="db-catalog-filter" data-db-catalog-filter-option="all">필터 해제</button>
        </article>
      `;
    }

    function dbCatalogProvenanceHTML() {
      const summary = catalogBoundaryModel();
      const selected = activeCatalogFilter();
      return html`
        <section class="data-provenance db-catalog-provenance" data-db-catalog-provenance data-db-catalog-live="false" data-db-catalog-total-count="${summary.total}" data-db-catalog-sample-count="${summary.sample}" data-db-catalog-manual-count="${summary.manual}" data-db-catalog-imported-count="${summary.imported}" data-db-catalog-stale-count="${summary.stale}" data-db-catalog-stale-sample-count="${summary.staleSample}" data-db-catalog-filter-current="${selected}" data-db-catalog-filtered-count="${summary.filtered}" data-db-catalog-sample-as-of="${SAMPLE_AS_OF}">
          <strong>local catalog · no live connection</strong>
          <span>브라우저 localStorage에 저장되는 로컬 DB 카탈로그입니다. 실제 데이터베이스에 연결하거나 실시간 지표를 수집하지 않습니다.</span>
          <span class="db-catalog-facts">
            <b>sample ${summary.sample}</b>
            <b>manual ${summary.manual}</b>
            <b>imported ${summary.imported}</b>
            <b>stale ${summary.stale}</b>
          </span>
          ${raw(catalogFilterBarHTML(summary))}
          ${raw(staleCatalogActionHTML(summary))}
          ${raw(issueSourceBacklinkHTML())}
          <span>입력한 수동 기록과 샘플 지표만 표시하므로 토큰·비밀번호·접속 문자열은 저장하지 마세요.</span>
        </section>
      `;
    }

    function renderActiveDbCatalogView() {
      if (dashboard.currentView === "dbm-schema") {
        state.schemaSelectedTable = null;
        renderDbSchema();
      } else if (dashboard.currentView === "dbm-queries") renderDbQueries();
      else if (dashboard.currentView === "dbm-backups") renderDbBackups();
      else renderDbInstances();
    }

    function setDbCatalogFilter(filter) {
      const next = DB_CATALOG_FILTERS.some((option) => option.key === filter) ? filter : "all";
      state.dbCatalogFilter = next;
      renderActiveDbCatalogView();
    }

    function renderDbInstances() {
      const view = refs.views["dbm-instances"];
      if (!view) return;
      const q = state.query;
      const hasFilter = activeCatalogFilter() !== "all";
      const searchedList = dashboard.dbInstances.filter((d) => matches(`${d.name} ${d.engine} ${d.region}`, q));
      const list = searchedList.filter((d) => recordMatchesCatalogFilter(d));
      const inst = currentInstance();
      const cur = inst ? (list.find((d) => d.id === inst.id) || list[0] || (hasFilter ? null : inst)) : (list[0] || null);

      const totalConn = dashboard.dbInstances.reduce((a, d) => a + d.conn, 0);
      const avgCpu = dashboard.dbInstances.length
        ? Math.round(dashboard.dbInstances.reduce((a, d) => a + d.cpu, 0) / dashboard.dbInstances.length)
        : 0;
      const unhealthy = dashboard.dbInstances.filter((d) => d.health !== "green").length;

      const kpis = [
        { title: "인스턴스", value: String(dashboard.dbInstances.length), unit: "대", color: "#2387ff", badge: "✺", delta: "" },
        { title: "평균 CPU", value: String(avgCpu), unit: "%", color: "#22d3ee", badge: "▣", delta: "" },
        { title: "연결 합계", value: String(totalConn), unit: "건", color: "#a970ff", badge: "◉", delta: "" },
        { title: "비정상", value: String(unhealthy), unit: "건", color: unhealthy ? "#ff4d5e" : "#17d983", badge: "△", delta: unhealthy ? "주의" : "정상", trendDown: unhealthy > 0 },
      ];

      const card = (d) => html`
        <div class="db-card-wrap" data-search-result="dbm-instances">
          <button type="button" class="db-card ${raw(cur && d.id === cur.id ? "is-current" : "")}" data-action="pick-instance" data-instance-id="${d.id}">
            <div class="db-card-head">
              <strong>${d.name}</strong>
              <span class="db-health" style="background:${raw(HEALTH_COLOR[d.health])}"></span>
            </div>
            <small>${d.engine}</small>
            ${raw(catalogBadgeHTML(d))}
            <div class="db-card-stats">
              <span><b>${d.cpu}%</b><small>CPU</small></span>
              <span><b>${d.conn}</b><small>conn</small></span>
              <span><b>${d.latencyMs}ms</b><small>지연</small></span>
            </div>
          </button>
          <div class="db-card-actions">
            <button type="button" class="pm-icon-btn" data-action="instance-edit" data-instance-id="${d.id}" title="${d.name} 인스턴스 편집" aria-label="${d.name} 인스턴스 편집">✎</button>
            <button type="button" class="pm-icon-btn pm-icon-btn-del" data-action="instance-delete" data-instance-id="${d.id}" title="${d.name} 인스턴스 삭제" aria-label="${d.name} 인스턴스 삭제">✕</button>
          </div>
        </div>
      `;

      const dbInstanceSearchEmpty = q && searchedList.length === 0;
      const dbInstanceFilterEmpty = hasFilter && !dbInstanceSearchEmpty && list.length === 0;
      const visibleInstances = list.length > catalogCardRenderLimit ? list.slice(0, catalogCardRenderLimit) : list;

      const detail = cur ? html`
        ${raw(panelHead(cur.name, null, html`<small>${cur.engine} · ${cur.region}</small>`))}
        <div class="db-detail">
          <div class="db-gauges">
            <div class="gauge db-gauge" style="--g:${raw(cur.cpu)}"><span>CPU</span><b>${cur.cpu}%</b></div>
            <div class="gauge db-gauge" style="--g:${raw(cur.mem)}"><span>메모리</span><b>${cur.mem}%</b></div>
            <div class="gauge db-gauge" style="--g:${raw(Math.round((cur.conn / cur.connMax) * 100))}"><span>연결</span><b>${cur.conn}/${cur.connMax}</b></div>
          </div>
          <div class="db-spark-row">
            <div class="db-spark">
              <strong>연결 추이 (24h)</strong>
              ${raw(spark(cur.series, "#22d3ee"))}
            </div>
            <div class="db-meta">
              <span><b>지연</b> ${cur.latencyMs}ms</span>
              <span><b>리전</b> ${cur.region}</span>
              <span><b>상태</b> <em style="color:${raw(HEALTH_COLOR[cur.health])}">● ${cur.health}</em></span>
              <span><b>출처</b> ${raw(catalogBadgeHTML(cur))}</span>
            </div>
          </div>
        </div>
      ` : html`
        ${raw(panelHead("인스턴스 없음", null, ""))}
        <article class="empty">등록된 DB 카탈로그 인스턴스가 없습니다. 새 인스턴스를 추가하세요.</article>
      `;

      setHTML(view, html`
        ${raw(dbCatalogProvenanceHTML())}
        <section class="kpis kpis-4">${raw(kpis.map((k) => kpiCard(k)).join(""))}</section>
        <section class="db-layout">
          <article class="panel db-list-panel">
            ${raw(panelHead("인스턴스", null, html`<button type="button" class="primary-btn" data-action="instance-add">+ 인스턴스 추가</button>`))}
	            <div class="db-list" data-db-virtual-list="instances" data-db-rendered-count="${visibleInstances.length}" data-db-total-count="${list.length}">
	              ${list.length === 0
	                ? raw(dbInstanceSearchEmpty
	                  ? searchEmptyState("dbm-instances", "검색 결과가 없습니다", "인스턴스 이름, 엔진, 리전과 일치하는 DB 인스턴스가 없습니다.")
	                  : dbInstanceFilterEmpty
	                    ? catalogFilterEmptyHTML("인스턴스")
	                    : html`<article class="empty">일치하는 인스턴스가 없습니다.</article>`)
	                : raw(html`${raw(visibleInstances.map(card).join(""))}${raw(virtualListNote("instances", list.length, visibleInstances.length))}`)}
	            </div>
          </article>
          <article class="panel db-detail-panel">
            ${raw(detail)}
          </article>
        </section>
      `);
    }

    function renderDbSchema() {
      const view = refs.views["dbm-schema"];
      if (!view) return;
      const q = state.query;
      const hasFilter = activeCatalogFilter() !== "all";

      let selected = state.schemaSelectedTable;
      if (!selected && dashboard.schemas.length) {
        const cur = dashboard.schemas.find((s) => s.id === dashboard.currentInstanceId) || dashboard.schemas[0];
        const firstDb = cur && cur.databases ? cur.databases[0] : null;
        const firstTable = firstDb && firstDb.tables[0];
        if (firstTable) selected = firstTable.id;
      }

      const allTables = dashboard.schemas.flatMap((s) =>
        (s.databases || []).flatMap((db) => (db.tables || []).map((t) => ({ ...t, instance: s.id, db: db.name }))));
      const tableMatchesSearch = (t) => matches(`${t.name} ${t.db} ${t.instance} ${(t.columns || []).map((c) => c.name).join(" ")}`, q);
      const searchedTables = allTables.filter(tableMatchesSearch);
      const tableMatches = (t) => tableMatchesSearch(t) && recordMatchesCatalogFilter(t);
      const filteredTables = allTables.filter(tableMatches);
      const selectedTablePool = q || hasFilter ? filteredTables : allTables;
      const selectedTable = selectedTablePool.find((t) => t.id === selected) || selectedTablePool[0] || null;
      const schemaSearchEmpty = q && searchedTables.length === 0;
      const schemaFilterEmpty = hasFilter && !schemaSearchEmpty && filteredTables.length === 0;

      const totalDbs = dashboard.schemas.reduce((a, s) => a + (s.databases || []).length, 0);
      const totalTables = allTables.length;
      const totalIdx = allTables.reduce((a, t) => a + (t.indexes ? t.indexes.length : 0), 0);
      const totalFk = allTables.reduce((a, t) => a + (t.fks ? t.fks.length : 0), 0);

      const kpis = [
        { title: "DB", value: String(totalDbs), unit: "개", color: "#2387ff", badge: "◎", delta: "" },
        { title: "테이블", value: String(totalTables), unit: "개", color: "#22d3ee", badge: "▦", delta: "" },
        { title: "인덱스", value: String(totalIdx), unit: "개", color: "#a970ff", badge: "▣", delta: "" },
        { title: "FK 관계", value: String(totalFk), unit: "개", color: "#17d983", badge: "↔", delta: "" },
      ];

      const tree = dashboard.schemas.length === 0
        ? html`<article class="empty">등록된 스키마가 없습니다. 테이블을 추가하세요.</article>`
        : schemaSearchEmpty
          ? searchEmptyState("dbm-schema", "검색 결과가 없습니다", "테이블, 컬럼, 데이터베이스, 인스턴스와 일치하는 스키마 항목이 없습니다.")
          : schemaFilterEmpty
            ? catalogFilterEmptyHTML("스키마")
          : dashboard.schemas.map((s) => {
              const inst = dashboard.dbInstances.find((d) => d.id === s.id);
              const expanded = state.schemaExpanded.has(s.id);
              const dbs = (s.databases || []).map((db) => {
                const matchingTables = (db.tables || []).filter(tableMatches);
                if (matchingTables.length === 0) return "";
                const visibleTables = matchingTables.length > catalogRowRenderLimit ? matchingTables.slice(0, catalogRowRenderLimit) : matchingTables;
                return html`
                <details class="schema-db" open>
                  <summary>${db.name}</summary>
                  <ul data-db-virtual-list="schema-tables" data-db-rendered-count="${visibleTables.length}" data-db-total-count="${matchingTables.length}">${visibleTables.map((t) => raw(html`
                    <li class="schema-table-li" data-search-result="dbm-schema">
                      <button type="button" class="schema-table-btn ${raw(selectedTable && t.id === selectedTable.id ? "is-current" : "")}" data-action="open-table" data-table-id="${t.id}">
                        <span>${t.name}</span>
                        <em>${(t.rows || 0).toLocaleString()}</em>
                        ${raw(catalogBadgeHTML(t))}
                      </button>
                      <div class="schema-table-actions">
                        <button type="button" class="pm-icon-btn" data-action="table-edit" data-table-id="${t.id}" title="${t.name} 테이블 편집" aria-label="${t.name} 테이블 편집">✎</button>
                        <button type="button" class="pm-icon-btn pm-icon-btn-del" data-action="table-delete" data-table-id="${t.id}" title="${t.name} 테이블 삭제" aria-label="${t.name} 테이블 삭제">✕</button>
                      </div>
                    </li>
                  `))}${raw(virtualListNote("schema-tables", matchingTables.length, visibleTables.length))}</ul>
                </details>
              `;
              }).join("");
              if (!dbs) return "";
              return html`
                <details class="schema-inst" ${raw(expanded ? "open" : "")} data-instance-id="${s.id}">
                  <summary><strong>${inst ? inst.name : s.id}</strong><small>${inst ? inst.engine : ""}</small></summary>
                  ${raw(dbs)}
                </details>
              `;
            }).join("");

      const selectedColumns = selectedTable && Array.isArray(selectedTable.columns) ? selectedTable.columns : [];
      const columnsBody = selectedTable ? html`
        <table class="schema-columns-table">
          <thead><tr><th>컬럼</th><th>타입</th><th>제약</th><th>인덱스</th></tr></thead>
          <tbody>${selectedColumns.map((c) => raw(html`
            <tr>
              <td><strong>${c.name}</strong></td>
              <td><code>${c.type}</code></td>
              <td>
                ${c.pk ? raw(html`<span class="col-flag flag-pk">PK</span>`) : ""}
                ${c.fk ? raw(html`<span class="col-flag flag-fk">FK→${c.fk}</span>`) : ""}
                ${c.nullable === false ? raw(html`<span class="col-flag flag-nn">NOT NULL</span>`) : ""}
              </td>
              <td>${(c.idx || []).map((i) => raw(html`<small class="col-idx">${i}</small>`))}</td>
            </tr>
          `))}</tbody>
        </table>
      ` : html`<article class="empty">테이블을 선택하세요.</article>`;

      const selectedIndexes = selectedTable && Array.isArray(selectedTable.indexes) ? selectedTable.indexes : [];
      const selectedFks = selectedTable && Array.isArray(selectedTable.fks) ? selectedTable.fks : [];
      const relBody = selectedTable ? html`
        <div class="schema-rel-block">
          <h4>인덱스</h4>
          ${selectedIndexes.length === 0 ? raw(html`<small class="empty-line">없음</small>`) : raw(selectedIndexes.map((i) => html`
            <div class="schema-rel-row">
              <strong>${i.name}</strong>
              <code>(${i.cols.join(", ")})</code>
              ${i.unique ? raw(html`<span class="col-flag flag-pk">UNIQUE</span>`) : ""}
            </div>
          `).join(""))}
        </div>
        <div class="schema-rel-block">
          <h4>외래키</h4>
          ${selectedFks.length === 0 ? raw(html`<small class="empty-line">없음</small>`) : raw(selectedFks.map((f) => html`
            <div class="schema-rel-row">
              <code>${f.col}</code>
              <span>→</span>
              <code>${f.refs}</code>
            </div>
          `).join(""))}
        </div>
        <div class="schema-rel-block">
          <h4>메타</h4>
          <small><b>행 수</b> ${(selectedTable.rows || 0).toLocaleString()}</small>
          <small><b>크기</b> ${selectedTable.sizeMb || 0} MB</small>
          <small><b>위치</b> ${selectedTable.instance || ""} · ${selectedTable.db || ""}</small>
          <small><b>출처</b> ${raw(catalogBadgeHTML(selectedTable))}</small>
        </div>
      ` : "";

      setHTML(view, html`
        ${raw(dbCatalogProvenanceHTML())}
        <section class="kpis kpis-4">${raw(kpis.map((k) => kpiCard(k)).join(""))}</section>
        <section class="schema-pane">
          <article class="panel schema-tree-panel">
            ${raw(panelHead("스키마", null, html`<button type="button" class="primary-btn" data-action="table-add">+ 테이블 추가</button>`))}
            <div class="schema-tree">${raw(tree)}</div>
          </article>
          <article class="panel schema-columns-panel">
            ${raw(panelHead(selectedTable ? `${selectedTable.db}.${selectedTable.name}` : "테이블", null, ""))}
            ${raw(columnsBody)}
          </article>
          <article class="panel schema-rel-panel">
            ${raw(panelHead("인덱스 / 관계", null, ""))}
            ${raw(relBody)}
          </article>
        </section>
      `);
    }

    function renderDbQueries() {
      const view = refs.views["dbm-queries"];
      if (!view) return;
      const q = state.query;
      const hasFilter = activeCatalogFilter() !== "all";
      const searchedList = dashboard.queries.filter((x) => matches(`${x.id} ${x.text} ${x.db} ${x.instance}`, q));
      const list = searchedList.filter((x) => recordMatchesCatalogFilter(x, activeCatalogFilter(), x.lastRun));

      const total = dashboard.queries.length;
      const avg = total ? Math.round(dashboard.queries.reduce((a, x) => a + x.avgMs, 0) / total) : 0;
      const p95 = total ? Math.round(dashboard.queries.reduce((a, x) => a + x.p95Ms, 0) / total) : 0;
      const tps = total ? Math.round(dashboard.queries.reduce((a, x) => a + x.count, 0) / 24) : 0;

      const kpis = [
        { title: "slow query", value: String(total), unit: "건", color: "#ff4d5e", badge: "◉", delta: "" },
        { title: "평균 ms", value: String(avg), unit: "ms", color: "#22d3ee", badge: "▣", delta: "" },
        { title: "평균 p95", value: String(p95), unit: "ms", color: "#a970ff", badge: "✺", delta: "" },
        { title: "시간당 처리", value: String(tps), unit: "건/h", color: "#17d983", badge: "✓", delta: "" },
      ];

      const buckets = dashboard.queryHistogram;
      const maxC = Math.max(1, ...buckets.map((b) => b.count));
      const barW = 28;
      const gap = 8;
      const histW = (barW + gap) * buckets.length + gap;
      const histH = 160;
      const baseY = histH - 30;
      const histSvg = `<svg class="histogram" viewBox="0 0 ${histW} ${histH}">
        ${buckets.map((b, i) => {
          const h = Math.round(((b.count) / maxC) * (baseY - 10));
          const x = gap + i * (barW + gap);
          const y = baseY - h;
          return `<g class="hist-group"><rect class="hist-bar" x="${x}" y="${y}" width="${barW}" height="${h}" rx="3"><title>${escapeHtml(b.bucket)}: ${b.count}건</title></rect>
            <text class="hist-bar-count" x="${x + barW / 2}" y="${y - 4}" text-anchor="middle">${b.count}</text>
            <text class="hist-bar-label" x="${x + barW / 2}" y="${baseY + 14}" text-anchor="middle">${escapeHtml(b.bucket)}</text>
          </g>`;
        }).join("")}
        <line x1="0" x2="${histW}" y1="${baseY}" y2="${baseY}" class="hist-axis"/>
      </svg>`;

      const trendPoints = [12, 18, 22, 24, 28, 34, 30, 36, 42, 38, 32, 28, 26];

      const visibleQueries = list.length > catalogRowRenderLimit ? list.slice(0, catalogRowRenderLimit) : list;
      const rows = visibleQueries.map((qi) => html`
        <tr data-search-result="dbm-queries">
          <td><button type="button" class="query-id-btn" data-action="open-query" data-query-id="${qi.id}">${qi.id}</button></td>
          <td><code class="query-text">${qi.text}</code></td>
          <td>${qi.instance}/${qi.db}</td>
          <td class="query-num">${qi.avgMs}</td>
          <td class="query-num">${qi.p95Ms}</td>
          <td class="query-num">${qi.count}</td>
          <td>${qi.lastRun}<br>${raw(catalogBadgeHTML(qi, qi.lastRun))}</td>
          <td class="query-actions-cell">
            <button type="button" class="pm-icon-btn" data-action="query-edit" data-query-id="${qi.id}" title="${qi.id} 쿼리 편집" aria-label="${qi.id} 쿼리 편집">✎</button>
            <button type="button" class="pm-icon-btn pm-icon-btn-del" data-action="query-delete" data-query-id="${qi.id}" title="${qi.id} 쿼리 삭제" aria-label="${qi.id} 쿼리 삭제">✕</button>
          </td>
        </tr>
      `).join("");
      const queryVirtualRow = virtualListNote("queries", list.length, visibleQueries.length);
      const querySearchEmpty = q && searchedList.length === 0;
      const queryFilterEmpty = hasFilter && !querySearchEmpty && list.length === 0;

      setHTML(view, html`
        ${raw(dbCatalogProvenanceHTML())}
        <section class="kpis kpis-4">${raw(kpis.map((k) => kpiCard(k)).join(""))}</section>
        <section class="queries-row">
          <article class="panel queries-trend-panel">
            ${raw(panelHead("실행 시간 추세 (24h)", null, html`<small>p95 평균 ${p95}ms</small>`))}
            <div class="queries-trend">${raw(spark(trendPoints, "#22d3ee"))}</div>
          </article>
          <article class="panel queries-hist-panel">
            ${raw(panelHead("실행 시간 분포 (ms)", null, ""))}
            <div class="histogram-wrap">${raw(histSvg)}</div>
          </article>
        </section>
        <section class="panel queries-table-panel">
          ${raw(panelHead("저장 쿼리", null, html`<button type="button" class="primary-btn" data-action="query-add">+ 쿼리 추가</button>`))}
          <div class="query-table-wrap">
            <table class="query-table">
              <thead><tr><th>ID</th><th>SQL</th><th>인스턴스/DB</th><th>평균(ms)</th><th>p95(ms)</th><th>호출</th><th>최근 실행</th><th>관리</th></tr></thead>
	              <tbody data-db-virtual-list="queries" data-db-rendered-count="${visibleQueries.length}" data-db-total-count="${list.length}">${raw(querySearchEmpty
	                ? html`<tr><td colspan="8">${raw(searchEmptyState("dbm-queries", "검색 결과가 없습니다", "쿼리 ID, SQL, 인스턴스, 데이터베이스와 일치하는 저장 쿼리가 없습니다."))}</td></tr>`
	                : queryFilterEmpty
	                  ? html`<tr><td colspan="8">${raw(catalogFilterEmptyHTML("저장 쿼리"))}</td></tr>`
	                : rows
                    ? html`${raw(rows)}${raw(queryVirtualRow ? html`<tr><td colspan="8">${raw(queryVirtualRow)}</td></tr>` : "")}`
                    : html`<tr><td colspan="8"><div class="empty">저장된 쿼리가 없습니다.</div></td></tr>`)}</tbody>
            </table>
          </div>
        </section>
      `);
    }

    function renderDbBackups() {
      const view = refs.views["dbm-backups"];
      if (!view) return;
      const q = state.query.trim();
      const backups = Array.isArray(dashboard.backups) ? dashboard.backups : [];
      const migrations = Array.isArray(dashboard.migrations) ? dashboard.migrations : [];
      const hasFilter = activeCatalogFilter() !== "all";

      const today = todayISO();
      const nextScheduled = migrations.find((m) => m.scheduledAt);
      const total = backups.length;
      const ok = backups.filter((b) => b.status === "ok").length;
      const successRate = total ? Math.round((ok / total) * 1000) / 10 : 0;
      const completedBackups = backups.filter((b) => b.status !== "fail");
      const avgSec = completedBackups.length
        ? Math.round(completedBackups.reduce((a, b) => a + b.durationS, 0) / completedBackups.length)
        : 0;
      const pendingMig = migrations.filter((m) => m.status === "pending").length;
      const searchedBackups = backups.filter((b) => matches(`${b.date} ${b.instance} ${b.status} ${b.note || ""}`, q));
      const filteredBackups = searchedBackups.filter((b) => recordMatchesCatalogFilter(b, activeCatalogFilter(), b.date));
      const searchedMigrations = migrations.filter((m) => {
        return matches(`${m.id} ${m.title} ${m.instance} ${m.status} ${m.appliedAt || ""} ${m.scheduledAt || ""}`, q);
      });
      const filteredMigrations = searchedMigrations.filter((m) => recordMatchesCatalogFilter(m, activeCatalogFilter(), m.appliedAt || m.scheduledAt));
      const hasSearch = !!q;
      const backupSearchEmpty = hasSearch && searchedBackups.length === 0;
      const migrationSearchEmpty = hasSearch && searchedMigrations.length === 0;
      const backupFilterEmpty = hasFilter && !backupSearchEmpty && filteredBackups.length === 0;
      const migrationFilterEmpty = hasFilter && !migrationSearchEmpty && filteredMigrations.length === 0;
      const allSearchEmpty = hasSearch && backupSearchEmpty && migrationSearchEmpty;

      const kpis = [
        { title: "다음 백업", value: nextScheduled ? nextScheduled.scheduledAt.slice(5, 10) : "오늘", unit: "", color: "#2387ff", badge: "⏱", delta: nextScheduled ? `${nextScheduled.scheduledAt.slice(11)}` : "예정" },
        { title: "성공률", value: String(successRate), unit: "%", color: "#17d983", badge: "✓", delta: "" },
        { title: "평균 소요", value: String(avgSec), unit: "초", color: "#22d3ee", badge: "✺", delta: "" },
        { title: "대기 마이그", value: String(pendingMig), unit: "건", color: "#a970ff", badge: "↻", delta: "예정 작업" },
      ];

      const rangeStart = total ? backups[0].date : today;
      const rangeEnd = total ? backups[backups.length - 1].date : today;
      const start = parseDate(rangeStart);
      const weekStart = new Date(start);
      weekStart.setUTCDate(weekStart.getUTCDate() - ((weekStart.getUTCDay() + 6) % 7));
      const calCells = [];
      for (let i = 0; i < 35; i++) {
        const d = new Date(weekStart);
        d.setUTCDate(d.getUTCDate() + i);
        const iso = `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}-${String(d.getUTCDate()).padStart(2, "0")}`;
        const dayBackups = backups.filter((b) => b.date === iso && matches(`${b.date} ${b.instance} ${b.status} ${b.note || ""}`, q));
        const hasFail = dayBackups.some((b) => b.status === "fail");
        const hasWarn = dayBackups.some((b) => b.status === "warn");
        const inRange = total ? iso >= rangeStart && iso <= rangeEnd : iso === today;
        const isToday = iso === today;
        const cls = ["cal-cell", inRange ? "" : "is-out", isToday ? "is-today" : "", hasFail ? "has-fail" : (hasWarn ? "has-warn" : (dayBackups.length ? "has-ok" : ""))].join(" ");
        calCells.push(html`
          <button type="button" class="${raw(cls)}" data-action="open-backup" data-date="${iso}" ${raw(dayBackups.length ? 'data-search-result="dbm-backup"' : "")} ${dayBackups.length === 0 ? raw("disabled") : ""}>
            <small class="cal-date">${d.getUTCDate()}</small>
            <div class="cal-dots">
              ${dayBackups.map((b) => raw(html`<span class="cal-dot cal-dot-${b.status}" title="${b.instance} (${b.status})"></span>`))}
            </div>
          </button>
        `);
      }

      const weekHeads = ["월", "화", "수", "목", "금", "토", "일"].map((w) => html`<div class="cal-weekhead">${w}</div>`).join("");
      const backupEmptyHTML = backupSearchEmpty
        ? html`
          <article class="empty empty-action bkup-empty" ${raw(allSearchEmpty ? 'role="status" aria-live="polite" data-search-empty="dbm-backups"' : 'data-backup-search-empty="true"')}>
            <strong>${allSearchEmpty ? "백업 검색 결과가 없습니다" : "백업 기록에는 결과가 없습니다"}</strong>
            <span>${allSearchEmpty ? `“${q}”와 일치하는 백업이나 마이그레이션을 찾지 못했습니다.` : `“${q}”와 일치하는 백업 기록은 없습니다. 오른쪽 마이그레이션 결과를 확인하거나 검색어를 조정하세요.`}</span>
            <button type="button" class="primary-btn" data-action="clear-search">검색 초기화</button>
          </article>
        `
        : backupFilterEmpty
          ? catalogFilterEmptyHTML("백업")
        : "";

      const migrationList = [...filteredMigrations].reverse();
      const visibleMigrations = migrationList.length > catalogRowRenderLimit ? migrationList.slice(0, catalogRowRenderLimit) : migrationList;
      const migRows = visibleMigrations.map((m) => html`
        <div class="mig-row-wrap">
          <button type="button" class="mig-row mig-${raw(m.status)}" data-action="open-migration" data-mig-id="${m.id}" data-search-result="migration">
            <span class="mig-dot"></span>
            <div class="mig-body">
              <strong>${m.title}</strong>
              <small>${m.id} · ${m.instance}</small>
              ${raw(catalogBadgeHTML(m, m.appliedAt || m.scheduledAt))}
              <em>${m.appliedAt || m.scheduledAt || ""}</em>
            </div>
            <span class="mig-status">${m.status}${m.rolledBack ? raw(" · 롤백") : ""}</span>
          </button>
          <div class="mig-row-actions">
            <button type="button" class="pm-icon-btn" data-action="migration-edit" data-mig-id="${m.id}" title="${m.id} 마이그레이션 편집" aria-label="${m.id} 마이그레이션 편집">✎</button>
            <button type="button" class="pm-icon-btn pm-icon-btn-del" data-action="migration-delete" data-mig-id="${m.id}" title="${m.id} 마이그레이션 삭제" aria-label="${m.id} 마이그레이션 삭제">✕</button>
          </div>
        </div>
      `).join("");
      const migVirtualNote = virtualListNote("migrations", migrationList.length, visibleMigrations.length);
      const migEmptyHTML = !migRows
        ? html`
          ${raw(migrationFilterEmpty
            ? catalogFilterEmptyHTML("마이그레이션")
            : html`
              <article class="empty empty-action mig-empty">
                <strong>${hasSearch ? "마이그레이션 결과가 없습니다" : "마이그레이션 이력이 없습니다"}</strong>
                <span>${hasSearch ? `“${q}”와 일치하는 변경 이력을 찾지 못했습니다.` : "DB 변경 이력을 예약하거나 기록하면 이곳에서 추적할 수 있습니다."}</span>
                <button type="button" class="primary-btn" data-action="${hasSearch ? "clear-search" : "migration-add"}">${hasSearch ? "검색 초기화" : "+ 마이그레이션 추가"}</button>
              </article>
            `)}
        `
        : "";

      setHTML(view, html`
        ${raw(dbCatalogProvenanceHTML())}
        <section class="kpis kpis-4">${raw(kpis.map((k) => kpiCard(k)).join(""))}</section>
        <section class="backups-layout">
          <article class="panel bkup-cal-panel">
            ${raw(panelHead("백업 캘린더", null, html`<small>${total ? `${rangeStart} ~ ${rangeEnd}` : "백업 기록 없음"}</small>`))}
            <p class="bkup-sample-note">※ 백업 이력은 시각화 샘플입니다. 실제 백업 관리는 별도 운영 도구를 이용하세요.</p>
            <div class="bkup-cal">
              ${raw(weekHeads)}
              ${raw(calCells.join(""))}
            </div>
            ${raw(backupEmptyHTML)}
            <div class="bkup-legend">
              <span><i class="cal-dot cal-dot-ok"></i>성공</span>
              <span><i class="cal-dot cal-dot-warn"></i>경고</span>
              <span><i class="cal-dot cal-dot-fail"></i>실패</span>
            </div>
          </article>
          <article class="panel mig-panel">
            ${raw(panelHead("마이그레이션 이력", null, html`<button type="button" class="primary-btn" data-action="migration-add">+ 마이그레이션 추가</button>`))}
            <div class="mig-list" data-db-virtual-list="migrations" data-db-rendered-count="${visibleMigrations.length}" data-db-total-count="${migrationList.length}">${raw(migRows || migEmptyHTML)}${raw(migRows ? migVirtualNote : "")}</div>
          </article>
        </section>
      `);
    }

    function findTableById(tableId) {
      for (const s of dashboard.schemas) {
        for (const db of s.databases) {
          const t = db.tables.find((x) => x.id === tableId);
          if (t) return { table: t, instanceId: s.id, dbName: db.name, schema: s, db };
        }
      }
      return null;
    }

    function instanceSelectOptions(current) {
      return dashboard.dbInstances.map((d) => html`<option value="${d.id}" ${raw(d.id === current ? "selected" : "")}>${d.name}</option>`).join("");
    }

    function openInstanceModal(arg) {
      const editing = arg && typeof arg === "object";
      const d = editing ? arg : null;
      const form = html`
        <form id="instanceForm" class="modal-form">
          <label>이름
            <input type="text" name="name" required maxlength="80" value="${d ? d.name : ""}" placeholder="예: prod-postgres-01" />
          </label>
          <div class="form-row">
            <label>엔진
              <input type="text" name="engine" maxlength="60" value="${d ? d.engine : ""}" placeholder="예: PostgreSQL 15.3" />
            </label>
            <label>리전
              <input type="text" name="region" maxlength="40" value="${d ? d.region : ""}" placeholder="예: ap-northeast-2" />
            </label>
          </div>
          <div class="form-row">
            <label>CPU (%)
              <input type="number" name="cpu" min="0" max="100" value="${d ? d.cpu : 0}" />
            </label>
            <label>메모리 (%)
              <input type="number" name="mem" min="0" max="100" value="${d ? d.mem : 0}" />
            </label>
          </div>
          <div class="form-row">
            <label>연결 수
              <input type="number" name="conn" min="0" value="${d ? d.conn : 0}" />
            </label>
            <label>최대 연결
              <input type="number" name="connMax" min="1" value="${d ? d.connMax : 100}" />
            </label>
            <label>지연 (ms)
              <input type="number" name="latencyMs" min="0" value="${d ? d.latencyMs : 0}" />
            </label>
          </div>
          <label>헬스
            <select name="health">
              ${raw(DB_HEALTH_ORDER.map((k) => html`<option value="${k}" ${raw(d && d.health === k ? "selected" : (!d && k === "green" ? "selected" : ""))}>${DB_HEALTH_MAP[k]}</option>`).join(""))}
            </select>
          </label>
          ${editing ? raw(html`<button type="button" class="modal-delete" data-action="instance-delete" data-instance-id="${d.id}">이 인스턴스 삭제</button>`) : ""}
        </form>
      `;
      openModal(editing ? `인스턴스 편집: ${d.name}` : "새 인스턴스 추가", form, () => saveInstanceFromForm(editing ? d.id : null));
    }

    function saveInstanceFromForm(id) {
      const data = catalogFormData("#instanceForm");
      if (!data) return false;
      const name = (data.get("name") || "").toString().trim();
      if (!name) { showToast("이름을 입력하세요", "warn"); return false; }
      const engine = (data.get("engine") || "").toString().trim();
      const region = (data.get("region") || "").toString().trim();
      const cpu = clampInteger(data.get("cpu"), 0, 100);
      const mem = clampInteger(data.get("mem"), 0, 100);
      const conn = clampInteger(data.get("conn"), 0);
      const connMax = clampInteger(data.get("connMax"), 1, Number.POSITIVE_INFINITY, 100);
      const latencyMs = clampInteger(data.get("latencyMs"), 0);
      const health = (data.get("health") || "green").toString();
      const catalogUpdatedAt = nowISO();
      if (id) {
        const inst = indexes.instanceById.get(id);
        if (inst) Object.assign(inst, { name, engine, region, cpu, mem, conn, connMax, latencyMs, health, catalogSource: "manual", catalogUpdatedAt });
        showToast(`인스턴스 '${name}' 수정`, "info");
      } else {
        const newId = uid("db");
        dashboard.dbInstances.push({ id: newId, name, engine, region, cpu, mem, conn, connMax, health, latencyMs, series: [], catalogSource: "manual", catalogUpdatedAt });
        dashboard.currentInstanceId = newId;
        showToast(`인스턴스 '${name}' 추가`, "info");
      }
      rebuildIndexes();
      commit();
      return true;
    }

    function deleteInstance(id) {
      const inst = indexes.instanceById.get(id);
      if (!inst) return;
      const relSchemas = dashboard.schemas.filter((s) => s.id === id);
      const relTables = relSchemas.reduce((a, s) => a + s.databases.reduce((b, db) => b + db.tables.length, 0), 0);
      const relQueries = dashboard.queries.filter((q) => q.instance === id).length;
      const relMigs = dashboard.migrations.filter((m) => m.instance === id).length;
      openModal("인스턴스 삭제", html`
        <div class="modal-confirm-body">
          <p>인스턴스 <strong>${inst.name}</strong>을(를) 삭제합니다.</p>
          <p class="muted-note">연결된 스키마(테이블 ${relTables}개) · 쿼리 ${relQueries}건 · 마이그레이션 ${relMigs}건도 함께 삭제됩니다. 되돌릴 수 없습니다.</p>
        </div>
      `, () => {
        dashboard.schemas = dashboard.schemas.filter((s) => s.id !== id);
        dashboard.queries = dashboard.queries.filter((q) => q.instance !== id);
        dashboard.migrations = dashboard.migrations.filter((m) => m.instance !== id);
        const idx = dashboard.dbInstances.findIndex((d) => d.id === id);
        if (idx >= 0) dashboard.dbInstances.splice(idx, 1);
        if (dashboard.currentInstanceId === id) {
          dashboard.currentInstanceId = dashboard.dbInstances.length ? dashboard.dbInstances[0].id : "";
        }
        rebuildIndexes();
        closeModal();
        showToast(`인스턴스 '${inst.name}' 삭제`, "info");
        commit();
        return true;
      });
    }

    function openTableModal(arg) {
      const editing = arg && typeof arg === "object";
      const t = editing ? arg : null;
      let editInstanceId = "";
      let editDbName = "";
      if (t) {
        const ctx = findTableById(t.id);
        if (ctx) { editInstanceId = ctx.instanceId; editDbName = ctx.dbName; }
      }
      const form = html`
        <form id="tableForm" class="modal-form">
          <label>인스턴스
            <select name="instanceId">${raw(instanceSelectOptions(editInstanceId || dashboard.currentInstanceId))}</select>
          </label>
          <div class="form-row">
            <label>데이터베이스명
              <input type="text" name="dbName" required maxlength="60" value="${editDbName}" placeholder="예: radar" />
            </label>
            <label>테이블명
              <input type="text" name="tableName" required maxlength="80" value="${t ? t.name : ""}" placeholder="예: users" />
            </label>
          </div>
          <div class="form-row">
            <label>행 수
              <input type="number" name="rows" min="0" value="${t ? t.rows || 0 : 0}" />
            </label>
            <label>크기 (MB)
              <input type="number" name="sizeMb" min="0" value="${t ? t.sizeMb || 0 : 0}" />
            </label>
          </div>
          ${editing ? raw(html`<button type="button" class="modal-delete" data-action="table-delete" data-table-id="${t.id}">이 테이블 삭제</button>`) : ""}
        </form>
      `;
      openModal(editing ? `테이블 편집: ${t.name}` : "새 테이블 추가", form, () => saveTableFromForm(editing ? t.id : null));
    }

    function saveTableFromForm(id) {
      const data = catalogFormData("#tableForm");
      if (!data) return false;
      const instanceId = (data.get("instanceId") || "").toString();
      if (!instanceId) { showToast("인스턴스를 선택하세요", "warn"); return false; }
      const dbName = (data.get("dbName") || "").toString().trim();
      if (!dbName) { showToast("데이터베이스명을 입력하세요", "warn"); return false; }
      const tableName = (data.get("tableName") || "").toString().trim();
      if (!tableName) { showToast("테이블명을 입력하세요", "warn"); return false; }
      const rows = clampInteger(data.get("rows"), 0);
      const sizeMb = clampNumber(data.get("sizeMb"), 0);
      const catalogUpdatedAt = nowISO();

      if (id) {
        const ctx = findTableById(id);
        if (!ctx) { showToast("테이블을 찾을 수 없습니다", "error"); return false; }
        if (ctx.instanceId !== instanceId || ctx.dbName !== dbName) {
          ctx.db.tables = ctx.db.tables.filter((x) => x.id !== id);
          if (ctx.db.tables.length === 0) ctx.schema.databases = ctx.schema.databases.filter((d) => d.name !== ctx.dbName);
          let targetSchema = dashboard.schemas.find((s) => s.id === instanceId);
          if (!targetSchema) { targetSchema = { id: instanceId, databases: [] }; dashboard.schemas.push(targetSchema); }
          let targetDb = targetSchema.databases.find((d) => d.name === dbName);
          if (!targetDb) { targetDb = { name: dbName, tables: [] }; targetSchema.databases.push(targetDb); }
          Object.assign(ctx.table, { name: tableName, rows, sizeMb, catalogSource: "manual", catalogUpdatedAt });
          targetDb.tables.push(ctx.table);
        } else {
          Object.assign(ctx.table, { name: tableName, rows, sizeMb, catalogSource: "manual", catalogUpdatedAt });
        }
        showToast(`테이블 '${tableName}' 수정`, "info");
      } else {
        let targetSchema = dashboard.schemas.find((s) => s.id === instanceId);
        if (!targetSchema) { targetSchema = { id: instanceId, databases: [] }; dashboard.schemas.push(targetSchema); }
        let targetDb = targetSchema.databases.find((d) => d.name === dbName);
        if (!targetDb) { targetDb = { name: dbName, tables: [] }; targetSchema.databases.push(targetDb); }
        const newId = uid("t");
        targetDb.tables.push({ id: newId, name: tableName, rows, sizeMb, columns: [], indexes: [], fks: [], catalogSource: "manual", catalogUpdatedAt });
        showToast(`테이블 '${tableName}' 추가`, "info");
      }
      commit();
      return true;
    }

    function deleteTable(tableId) {
      const ctx = findTableById(tableId);
      if (!ctx) return;
      openModal("테이블 삭제", html`
        <div class="modal-confirm-body">
          <p>테이블 <strong>${ctx.dbName}.${ctx.table.name}</strong>을(를) 삭제합니다.</p>
          <p class="muted-note">컬럼 · 인덱스 · 외래키 정보도 모두 삭제됩니다. 되돌릴 수 없습니다.</p>
        </div>
      `, () => {
        ctx.db.tables = ctx.db.tables.filter((t) => t.id !== tableId);
        if (ctx.db.tables.length === 0) {
          ctx.schema.databases = ctx.schema.databases.filter((d) => d.name !== ctx.dbName);
        }
        if (state.schemaSelectedTable === tableId) state.schemaSelectedTable = null;
        closeModal();
        closeSheet();
        showToast(`테이블 '${ctx.table.name}' 삭제`, "info");
        commit();
        return true;
      });
    }

    function openColumnModal(tableId, colIndex) {
      const ctx = findTableById(tableId);
      if (!ctx) return;
      const editing = colIndex !== null && colIndex !== undefined;
      const c = editing ? ctx.table.columns[colIndex] : null;
      const form = html`
        <form id="columnForm" class="modal-form">
          <div class="form-row">
            <label>이름
              <input type="text" name="colName" required maxlength="80" value="${c ? c.name : ""}" placeholder="예: user_id" />
            </label>
            <label>타입
              <input type="text" name="colType" maxlength="60" value="${c ? c.type : ""}" placeholder="예: bigint" />
            </label>
          </div>
          <div class="form-row">
            <label class="check-inline">
              <input type="checkbox" name="pk" ${raw(c && c.pk ? "checked" : "")} /> PK
            </label>
            <label class="check-inline">
              <input type="checkbox" name="nullable" ${raw(!c || c.nullable !== false ? "checked" : "")} /> NULL 허용
            </label>
          </div>
          <label>FK 참조 (선택)
            <input type="text" name="fk" maxlength="120" value="${c && c.fk ? c.fk : ""}" placeholder="예: users.id" />
          </label>
        </form>
      `;
      openModal(editing ? `컬럼 편집: ${c.name}` : `컬럼 추가 — ${ctx.dbName}.${ctx.table.name}`, form, () => saveColumnFromForm(tableId, editing ? colIndex : null));
    }

    function saveColumnFromForm(tableId, colIndex) {
      const data = catalogFormData("#columnForm");
      if (!data) return false;
      const ctx = findTableById(tableId);
      if (!ctx) { showToast("테이블을 찾을 수 없습니다", "error"); return false; }
      const colName = (data.get("colName") || "").toString().trim();
      if (!colName) { showToast("컬럼 이름을 입력하세요", "warn"); return false; }
      const colType = (data.get("colType") || "").toString().trim() || "text";
      const pk = data.get("pk") === "on";
      const nullable = data.get("nullable") === "on";
      const fk = (data.get("fk") || "").toString().trim() || undefined;
      const col = { name: colName, type: colType };
      if (pk) col.pk = true;
      if (!nullable) col.nullable = false;
      if (fk) col.fk = fk;

      if (colIndex !== null && colIndex !== undefined) {
        ctx.table.columns[colIndex] = col;
        showToast(`컬럼 '${colName}' 수정`, "info");
      } else {
        ctx.table.columns.push(col);
        showToast(`컬럼 '${colName}' 추가`, "info");
      }
      ctx.table.catalogSource = "manual";
      ctx.table.catalogUpdatedAt = nowISO();
      commit();
      openTableSheet(tableId);
      return true;
    }

    function deleteColumn(tableId, colIndex) {
      const ctx = findTableById(tableId);
      if (!ctx) return;
      const col = ctx.table.columns[colIndex];
      if (!col) return;
      openModal("컬럼 삭제", html`
        <div class="modal-confirm-body">
          <p>컬럼 <strong>${col.name}</strong>을(를) 삭제합니다. 되돌릴 수 없습니다.</p>
        </div>
      `, () => {
        ctx.table.columns.splice(colIndex, 1);
        closeModal();
        showToast(`컬럼 '${col.name}' 삭제`, "info");
        commit();
        openTableSheet(tableId);
        return true;
      });
    }

    function openQueryModal(arg) {
      const editing = arg && typeof arg === "object";
      const qi = editing ? arg : null;
      const form = html`
        <form id="queryForm" class="modal-form">
          <div class="form-row">
            <label>인스턴스
              <select name="instance">${raw(instanceSelectOptions(qi ? qi.instance : dashboard.currentInstanceId))}</select>
            </label>
            <label>DB
              <input type="text" name="db" maxlength="60" value="${qi ? qi.db : ""}" placeholder="예: radar" />
            </label>
          </div>
          <label>쿼리문 (SQL)
            <textarea name="text" rows="5" maxlength="2000" placeholder="SELECT ...">${qi ? qi.text : ""}</textarea>
          </label>
          <div class="form-row">
            <label>평균 ms
              <input type="number" name="avgMs" min="0" value="${qi ? qi.avgMs : 0}" />
            </label>
            <label>p95 ms
              <input type="number" name="p95Ms" min="0" value="${qi ? qi.p95Ms : 0}" />
            </label>
            <label>실행 횟수
              <input type="number" name="count" min="0" value="${qi ? qi.count : 0}" />
            </label>
          </div>
          <label>비고 (Plan Hint)
            <input type="text" name="planHint" maxlength="200" value="${qi ? qi.planHint || "" : ""}" placeholder="예: seq scan on users" />
          </label>
          ${editing ? raw(html`<button type="button" class="modal-delete" data-action="query-delete" data-query-id="${qi.id}">이 쿼리 삭제</button>`) : ""}
        </form>
      `;
      openModal(editing ? `쿼리 편집: ${qi.id}` : "쿼리 추가", form, () => saveQueryFromForm(editing ? qi.id : null));
    }

    function saveQueryFromForm(id) {
      const data = catalogFormData("#queryForm");
      if (!data) return false;
      const instance = (data.get("instance") || "").toString();
      if (!instance) { showToast("인스턴스를 선택하세요", "warn"); return false; }
      const db = (data.get("db") || "").toString().trim();
      const text = (data.get("text") || "").toString().trim();
      if (!text) { showToast("쿼리문을 입력하세요", "warn"); return false; }
      const avgMs = clampInteger(data.get("avgMs"), 0);
      const p95Ms = clampInteger(data.get("p95Ms"), 0);
      const count = clampInteger(data.get("count"), 0);
      const planHint = (data.get("planHint") || "").toString().trim();
      const catalogUpdatedAt = nowISO();
      if (id) {
        const qi = dashboard.queries.find((x) => x.id === id);
        if (qi) Object.assign(qi, { instance, db, text, avgMs, p95Ms, count, planHint, catalogSource: "manual", catalogUpdatedAt });
        showToast("쿼리를 수정했습니다", "info");
      } else {
        const newId = uid("Q");
        dashboard.queries.push({ id: newId, instance, db, text, avgMs, p95Ms, count, planHint, lastRun: formatLocalDateTime(catalogUpdatedAt), catalogSource: "manual", catalogUpdatedAt });
        showToast("쿼리를 추가했습니다", "info");
      }
      commit();
      return true;
    }

    function deleteQuery(id) {
      const qi = dashboard.queries.find((x) => x.id === id);
      if (!qi) return;
      const idx = dashboard.queries.findIndex((x) => x.id === id);
      const removed = idx >= 0 ? cloneRecord(dashboard.queries[idx]) : cloneRecord(qi);
      const deletedEntryId = captureDeletedItem("query", removed, { index: idx });
      if (idx >= 0) dashboard.queries.splice(idx, 1);
      closeModal();
      closeSheet();
      commit();
      showUndoToast("쿼리를 삭제했습니다", () => {
        if (!canUndoDeletedItem(deletedEntryId)) return;
        if (!restoreDeletedArrayItem(dashboard.queries, idx, removed)) return;
        dropDeletedItem(deletedEntryId);
        commit();
        showToast("쿼리 삭제를 되돌렸습니다", "info");
      });
    }

    function openMigrationModal(arg) {
      const editing = arg && typeof arg === "object";
      const m = editing ? arg : null;
      const migrationDeleteLabel = m ? `✕ ${m.id} 마이그레이션 삭제` : "";
      const dateVal = m ? (m.appliedAt || m.scheduledAt || "").slice(0, 10) : "";
      const form = html`
        <form id="migrationForm" class="modal-form">
          <label>인스턴스
            <select name="instance">${raw(instanceSelectOptions(m ? m.instance : dashboard.currentInstanceId))}</select>
          </label>
          <label>제목
            <input type="text" name="title" required maxlength="120" value="${m ? m.title : ""}" placeholder="예: add index on users.email" />
          </label>
          <div class="form-row">
            <label>상태
              <select name="status">
                ${raw(MIG_STATUS_ORDER.map((k) => html`<option value="${k}" ${raw(m && m.status === k ? "selected" : (!m && k === "pending" ? "selected" : ""))}>${MIG_STATUS_MAP[k]}</option>`).join(""))}
              </select>
            </label>
            <label>일시 (적용 또는 예정)
              <input type="date" name="migDate" value="${dateVal}" />
            </label>
          </div>
          ${editing ? raw(html`<button type="button" class="modal-delete" data-action="migration-delete" data-mig-id="${m.id}" title="${migrationDeleteLabel}" aria-label="${migrationDeleteLabel}">이 마이그레이션 삭제</button>`) : ""}
        </form>
      `;
      openModal(editing ? `마이그레이션 편집: ${m.id}` : "마이그레이션 추가", form, () => saveMigrationFromForm(editing ? m.id : null));
    }

    function saveMigrationFromForm(id) {
      const data = catalogFormData("#migrationForm");
      if (!data) return false;
      const instance = (data.get("instance") || "").toString();
      if (!instance) { showToast("인스턴스를 선택하세요", "warn"); return false; }
      const title = (data.get("title") || "").toString().trim();
      if (!title) { showToast("제목을 입력하세요", "warn"); return false; }
      const status = (data.get("status") || "pending").toString();
      const migDate = (data.get("migDate") || "").toString();
      const dateTimeVal = migDate ? migDate + " 02:00" : undefined;
      const catalogUpdatedAt = nowISO();

      if (id) {
        const m = dashboard.migrations.find((x) => x.id === id);
        if (m) {
          m.instance = instance;
          m.title = title;
          m.status = status;
          delete m.appliedAt;
          delete m.scheduledAt;
          if (status === "applied" || status === "rolled-back") { if (dateTimeVal) m.appliedAt = dateTimeVal; }
          else { if (dateTimeVal) m.scheduledAt = dateTimeVal; }
          m.catalogSource = "manual";
          m.catalogUpdatedAt = catalogUpdatedAt;
        }
        showToast("마이그레이션을 수정했습니다", "info");
      } else {
        const newId = uid("M");
        const entry = { id: newId, instance, title, status, catalogSource: "manual", catalogUpdatedAt };
        if (status === "applied" || status === "rolled-back") { if (dateTimeVal) entry.appliedAt = dateTimeVal; }
        else { if (dateTimeVal) entry.scheduledAt = dateTimeVal; }
        dashboard.migrations.push(entry);
        showToast("마이그레이션을 추가했습니다", "info");
      }
      commit();
      return true;
    }

    function deleteMigration(id) {
      const m = dashboard.migrations.find((x) => x.id === id);
      if (!m) return;
      const idx = dashboard.migrations.findIndex((x) => x.id === id);
      const removed = idx >= 0 ? cloneRecord(dashboard.migrations[idx]) : cloneRecord(m);
      const deletedEntryId = captureDeletedItem("migration", removed, { index: idx });
      if (idx >= 0) dashboard.migrations.splice(idx, 1);
      closeModal();
      closeSheet();
      commit();
      showUndoToast("마이그레이션을 삭제했습니다", () => {
        if (!canUndoDeletedItem(deletedEntryId)) return;
        if (!restoreDeletedArrayItem(dashboard.migrations, idx, removed)) return;
        dropDeletedItem(deletedEntryId);
        commit();
        showToast("마이그레이션 삭제를 되돌렸습니다", "info");
      });
    }

    return Object.freeze({
      version: VERSION,
      dbCatalogProvenanceHTML,
      setDbCatalogFilter,
      renderDbInstances,
      renderDbSchema,
      renderDbQueries,
      renderDbBackups,
      findTableById,
      instanceSelectOptions,
      openInstanceModal,
      saveInstanceFromForm,
      deleteInstance,
      openTableModal,
      saveTableFromForm,
      deleteTable,
      openColumnModal,
      saveColumnFromForm,
      deleteColumn,
      openQueryModal,
      saveQueryFromForm,
      deleteQuery,
      openMigrationModal,
      saveMigrationFromForm,
      deleteMigration,
    });
  }

  global.JooParkDbCatalog = Object.freeze({
    version: VERSION,
    create: createDbCatalog,
    constants: Object.freeze({
      dbHealthMap: DB_HEALTH_MAP,
      dbHealthOrder: DB_HEALTH_ORDER,
      migrationStatusMap: MIG_STATUS_MAP,
      migrationStatusOrder: MIG_STATUS_ORDER,
    }),
  });
})(typeof window !== "undefined" ? window : globalThis);
