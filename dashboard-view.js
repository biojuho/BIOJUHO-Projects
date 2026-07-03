/* ================================================================
 * JooPark Workspace — dashboard intelligence view.
 * Static non-module runtime loaded before app.js.
 * ================================================================ */

(function initJooParkDashboardView(global) {
  "use strict";

  const VERSION = "joopark-dashboard-view/v1";

  function createDashboardView(deps = {}) {
    const html = deps.html;
    const raw = deps.raw;
    if (typeof html !== "function" || typeof raw !== "function") {
      throw new Error("dashboard view requires html and raw helpers");
    }

    function listOf(value) {
      return Array.isArray(value) ? value : [];
    }

    function confidenceText(value) {
      const number = Number(value);
      const bounded = Number.isFinite(number) ? Math.max(0, Math.min(1, number)) : 0;
      return bounded.toFixed(2);
    }

    function actionLabel(action) {
      return action && action.label ? action.label : "다음 액션 확인";
    }

    function actionView(action) {
      return action && action.view ? action.view : "home";
    }

    function cardHTML(card) {
      const action = card.nextAction || {};
      return html`
        <article class="dashboard-intel-card" data-dashboard-intel-card data-dashboard-card-key="${card.key}" data-dashboard-risk="${card.riskLabel}" data-dashboard-status="${card.status}">
          <div class="dashboard-intel-card-head">
            <div>
              <span>${card.title}</span>
              <strong>${card.status}</strong>
            </div>
            <em>${card.riskLabel}</em>
          </div>
          <p>${card.evidence}</p>
          <dl>
            <div><dt>갱신</dt><dd>${card.lastUpdated}</dd></div>
            <div><dt>근거</dt><dd>${listOf(card.sourceRefs).slice(0, 3).join(", ")}</dd></div>
          </dl>
          <button type="button" class="secondary-btn" data-action="nav-to" data-view="${actionView(action)}">${actionLabel(action)}</button>
        </article>
      `;
    }

    function candidateHTML(candidate, index) {
      const score = candidate.scoreBreakdown || {};
      const action = candidate.nextAction || {};
      return html`
        <li data-dashboard-candidate data-dashboard-candidate-rank="${index + 1}" data-dashboard-candidate-hash="${candidate.receiptHash || ""}">
          <div>
            <strong>${index + 1}. ${candidate.summary}</strong>
            <small>score ${score.weighted || score.total || "n/a"} · confidence ${confidenceText(candidate.confidence)} · ${candidate.verificationStatus}</small>
          </div>
          <span>${actionLabel(action)}</span>
        </li>
      `;
    }

    function receiptHTML(receipt) {
      if (!receipt) return "";
      return html`
        <div class="dashboard-receipt" data-dashboard-decision-receipt data-dashboard-decision-receipt-hash="${receipt.receiptHash || ""}" data-dashboard-decision-receipt-status="${receipt.verificationStatus || ""}">
          <div>
            <span>latest receipt</span>
            <strong>${receipt.summary}</strong>
            <small>${receipt.createdAt} · ${receipt.receiptHash}</small>
          </div>
          <button type="button" class="secondary-btn" data-action="copy-dashboard-decision-receipt" data-dashboard-decision-receipt-copy>receipt 복사</button>
          <span data-dashboard-decision-receipt-copy-status aria-live="polite"></span>
          <pre hidden data-dashboard-decision-receipt-text>${receipt.markdown || receipt.summary || ""}</pre>
        </div>
      `;
    }

    function researchSourceHTML(source) {
      const confidence = confidenceText(source.confidence);
      return html`
        <li data-dashboard-external-source data-dashboard-external-source-id="${source.id}" data-dashboard-external-source-confidence="${confidence}">
          <strong>${source.title}</strong>
          <span>${source.checkedAt} · confidence ${confidence}</span>
        </li>
      `;
    }

    function renderDashboardIntelligenceHTML(model = {}) {
      const cards = listOf(model.cards);
      const candidates = listOf(model.candidates);
      const loops = listOf(model.loops);
      const latestReceipt = model.latestReceipt || null;
      const active = model.autoresearchActive === true;
      const sources = listOf(model.externalResearchSources);
      return html`
        <section class="panel dashboard-intelligence" data-dashboard-intelligence data-dashboard-card-count="${cards.length}" data-dashboard-candidate-count="${candidates.length}" data-dashboard-loop-count="${loops.length}" data-dashboard-autoresearch-active="${active ? "true" : "false"}">
          <div class="panel-head">
            <div>
              <h2>운영 관제판</h2>
              <small>일정, 할 일, 프로젝트, Kanban, Gantt, 습관, 저장소, release, product loop 통합 상태</small>
            </div>
            <span class="publish-state">${active ? "loop active" : "manual loop"}</span>
          </div>
          <div class="dashboard-intel-grid">
            ${cards.slice(0, 9).map((item) => raw(cardHTML(item)))}
          </div>
          <div class="dashboard-loop-panel" data-dashboard-autoresearch-loop>
            <div>
              <span>AutoResearch loop</span>
              <strong>${loops.length ? `${loops.length} receipts` : "ready"}</strong>
              <p>현황 재확인, localStorage 요약, evidence 확인, research 확장, 후보 점수화, receipt 저장까지 브라우저 로컬 데이터로 반복합니다.</p>
            </div>
            <div class="dashboard-loop-actions">
              <button type="button" class="primary-btn" data-action="dashboard-autoresearch-run">1회 실행</button>
              <button type="button" class="secondary-btn" data-action="${active ? "dashboard-autoresearch-stop" : "dashboard-autoresearch-start"}">${active ? "멈춰" : "반복 시작"}</button>
            </div>
          </div>
          ${raw(receiptHTML(latestReceipt))}
          <div class="dashboard-candidate-strip" data-dashboard-candidate-strip>
            <div class="panel-head compact-head"><div><h3>다음 루프 후보 TOP 5</h3></div></div>
            <ol>
              ${candidates.slice(0, 5).map((item, index) => raw(candidateHTML(item, index)))}
            </ol>
          </div>
          <details class="dashboard-research-sources">
            <summary>외부 research source ${sources.length}개</summary>
            <ul>
              ${sources.map((source) => raw(researchSourceHTML(source)))}
            </ul>
          </details>
        </section>
      `;
    }

    function systemDashboardReceiptHTML(model = {}) {
      const receipts = listOf(model.receipts);
      const latest = receipts[0] || null;
      return html`
        <section class="panel dashboard-system-receipts" data-system-dashboard-receipts data-system-dashboard-receipt-count="${receipts.length}" data-system-dashboard-latest-hash="${latest ? latest.receiptHash : ""}">
          <div class="panel-head">
            <div>
              <h2>Dashboard intelligence receipts</h2>
              <p>AutoResearch loop, 후보 점수, 저장소 health, evidence snapshot 영수증</p>
            </div>
            <span class="publish-state">${receipts.length ? "ready" : "empty"}</span>
          </div>
          ${latest ? raw(receiptHTML(latest)) : raw(html`<p class="settings-note">Home에서 AutoResearch loop를 실행하면 System Status에 receipt가 표시됩니다.</p>`)}
          <dl class="storage-grid">
            ${listOf(model.collections).map((item) => raw(html`
              <div><dt>${item.key}</dt><dd>${item.count}/${item.retention}</dd></div>
            `))}
          </dl>
        </section>
      `;
    }

    return Object.freeze({
      version: VERSION,
      confidenceText,
      renderDashboardIntelligenceHTML,
      systemDashboardReceiptHTML,
    });
  }

  global.JooParkDashboardView = Object.freeze({
    version: VERSION,
    create: createDashboardView,
  });
})(typeof window !== "undefined" ? window : globalThis);
