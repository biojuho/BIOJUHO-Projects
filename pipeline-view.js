/* ================================================================
 * JooPark Workspace — 제약 파이프라인 보드 (pm-pipeline view).
 * 신약 자산(asset) × 워크스트림(workstream) 2차원 매트릭스를 하나의
 * 컴포넌트로 렌더링한다. 셀을 누르면 마일스톤·WBS 트리·위키 딥링크가
 * 시트로 열린다. 색은 var(--*) 토큰만 사용한다(테마/대비 안전).
 * 데이터는 dashboard.pipeline = { assets:[], cells:{ "ID:ws": {…} } }.
 * ================================================================ */

(function (root) {
  "use strict";

  const VERSION = "joopark-pipeline-view/v1";

  // 워크스트림은 정적 상수(persist 안 함). 셀 키 = `${assetId}:${ws.key}`.
  const WORKSTREAMS = [
    { key: "efficacy", label: "효능(비임상)" },
    { key: "CMC", label: "CMC/제제" },
    { key: "toxicology", label: "독성" },
    { key: "regulatory", label: "규제/인허가" },
    { key: "BD", label: "BD/사업개발" },
  ];

  // 임상 단계 토큰 → 색/라벨/뱃지. 색은 토큰 문자열(raw로 주입).
  const PHASE_COLOR = {
    discovery: "var(--muted)",
    planned: "var(--muted)",
    preclinical: "var(--cyan)",
    ind: "var(--blue)",
    phase1: "var(--blue)",
    phase2: "var(--violet)",
    phase3: "var(--amber)",
    nda: "var(--green)",
    onhold: "var(--red)",
  };
  const PHASE_LABEL = {
    discovery: "발굴", planned: "계획", preclinical: "비임상", ind: "IND",
    phase1: "임상 1상", phase2: "임상 2상", phase3: "임상 3상", nda: "허가신청", onhold: "보류",
  };
  const PHASE_BADGE = {
    discovery: "○", planned: "○", preclinical: "◔", ind: "◑",
    phase1: "◑", phase2: "◕", phase3: "◕", nda: "●", onhold: "▲",
  };

  const RISK_LABEL = {
    aggregation: "응집", thermolability: "열 불안정", adsorption: "용기 흡착",
    deamidation: "탈아미드화", hydrolysis: "가수분해", "efficacy-signal": "효능신호 약함",
    immunogenicity: "면역원성", supply: "공급/원료",
  };

  const WBS_STATUS_LABEL = { todo: "예정", doing: "진행", done: "완료", blocked: "지연" };
  const WBS_STATUS_SET = { todo: 1, doing: 1, done: 1, blocked: 1 };

  // 어떤 자산이든 인스턴스화할 수 있는 워크스트림별 표준 WBS 템플릿.
  // 데이터 없는 셀의 드릴다운에서 읽기 전용으로 보여준다.
  const WBS_TEMPLATES = {
    efficacy: [
      { id: "EFF-T1", name: "질환 모델 확립", status: "todo", owner: "", deps: [], children: [] },
      { id: "EFF-T2", name: "용량 설정 PoC", status: "todo", owner: "", deps: ["EFF-T1"], children: [] },
      { id: "EFF-T3", name: "GLP 효능 시험", status: "todo", owner: "", deps: ["EFF-T2"], children: [] },
      { id: "EFF-T4", name: "작용기전(MoA) 분석", status: "todo", owner: "", deps: ["EFF-T2"], children: [] },
      { id: "EFF-T5", name: "결과 보고서", status: "todo", owner: "", deps: ["EFF-T3"], children: [] },
    ],
    CMC: [
      { id: "CMC-T1", name: "QTPP / CQA 정의", status: "todo", owner: "", deps: [], children: [] },
      { id: "CMC-T2", name: "처방(Formulation) 스크리닝", status: "todo", owner: "", deps: ["CMC-T1"], children: [] },
      { id: "CMC-T3", name: "공정(Process) 개발", status: "todo", owner: "", deps: ["CMC-T2"], children: [] },
      { id: "CMC-T4", name: "분석법 개발·밸리데이션", status: "todo", owner: "", deps: ["CMC-T2"], children: [] },
      { id: "CMC-T5", name: "안정성 시험", status: "todo", owner: "", deps: ["CMC-T3"], children: [] },
      { id: "CMC-T6", name: "기술 이전(Tech transfer)", status: "todo", owner: "", deps: ["CMC-T5"], children: [] },
    ],
    toxicology: [
      { id: "TOX-T1", name: "단회투여 독성", status: "todo", owner: "", deps: [], children: [] },
      { id: "TOX-T2", name: "반복투여 GLP 독성", status: "todo", owner: "", deps: ["TOX-T1"], children: [] },
      { id: "TOX-T3", name: "안전성 약리", status: "todo", owner: "", deps: ["TOX-T1"], children: [] },
      { id: "TOX-T4", name: "유전 독성", status: "todo", owner: "", deps: [], children: [] },
      { id: "TOX-T5", name: "독성 패키지 종합", status: "todo", owner: "", deps: ["TOX-T2", "TOX-T3", "TOX-T4"], children: [] },
    ],
    regulatory: [
      { id: "REG-T1", name: "규제 전략 수립", status: "todo", owner: "", deps: [], children: [] },
      { id: "REG-T2", name: "Pre-IND 미팅", status: "todo", owner: "", deps: ["REG-T1"], children: [] },
      { id: "REG-T3", name: "IND 서류 준비", status: "todo", owner: "", deps: ["REG-T2"], children: [] },
      { id: "REG-T4", name: "제출(Submission)", status: "todo", owner: "", deps: ["REG-T3"], children: [] },
      { id: "REG-T5", name: "심사 대응", status: "todo", owner: "", deps: ["REG-T4"], children: [] },
    ],
    BD: [
      { id: "BD-T1", name: "시장/경쟁 조사", status: "todo", owner: "", deps: [], children: [] },
      { id: "BD-T2", name: "타겟 파트너 리스트", status: "todo", owner: "", deps: ["BD-T1"], children: [] },
      { id: "BD-T3", name: "비밀유지계약(CDA)", status: "todo", owner: "", deps: ["BD-T2"], children: [] },
      { id: "BD-T4", name: "텀시트 협상", status: "todo", owner: "", deps: ["BD-T3"], children: [] },
      { id: "BD-T5", name: "실사(Due diligence) 대응", status: "todo", owner: "", deps: ["BD-T4"], children: [] },
    ],
  };

  function cellKey(assetId, wsKey) {
    return `${assetId}:${wsKey}`;
  }

  function createPipelineView(deps) {
    const options = deps || {};
    const html = options.html;
    const raw = options.raw;
    const escapeHtml = typeof options.escapeHtml === "function" ? options.escapeHtml : function (v) { return v == null ? "" : String(v); };
    const matches = typeof options.matches === "function" ? options.matches : function () { return true; };
    const kpiCard = typeof options.kpiCard === "function" ? options.kpiCard : function () { return ""; };
    const panelHead = typeof options.panelHead === "function"
      ? options.panelHead
      : function (title) { return html`<div class="panel-head"><div><h2>${title}</h2></div></div>`; };
    const searchEmptyState = typeof options.searchEmptyState === "function" ? options.searchEmptyState : null;

    if (typeof html !== "function" || typeof raw !== "function") {
      throw new Error("pipeline view requires html and raw helpers");
    }

    function safeWbsStatus(status) {
      return WBS_STATUS_SET[status] ? status : "todo";
    }

    function assetSearchText(asset) {
      return [asset.id, asset.name, asset.modality, asset.indication].filter(Boolean).join(" ");
    }

    function pipelineViewModel(input) {
      const data = input || {};
      const assets = Array.isArray(data.assets) ? data.assets : [];
      const cells = data.cells && typeof data.cells === "object" ? data.cells : {};
      const query = (data.query || "").trim();
      const list = query ? assets.filter((asset) => matches(assetSearchText(asset), query)) : assets;

      const totalSlots = assets.length * WORKSTREAMS.length;
      let activeCount = 0;
      let riskTotal = 0;
      let latestDate = "";
      Object.keys(cells).forEach((key) => {
        const cell = cells[key];
        if (!cell || typeof cell !== "object") return;
        activeCount += 1;
        if (Array.isArray(cell.riskFlags)) riskTotal += cell.riskFlags.length;
        if (typeof cell.lastUpdated === "string" && cell.lastUpdated > latestDate) latestDate = cell.lastUpdated;
      });

      const kpis = [
        { title: "자산", value: String(assets.length), unit: "개", color: "var(--blue)", badge: "⬢" },
        { title: "활성 셀", value: String(activeCount), unit: `/${totalSlots}`, color: "var(--cyan)", badge: "▦" },
        { title: "위험 플래그", value: String(riskTotal), unit: "건", color: "var(--red)", badge: "△", delta: riskTotal ? "검토 필요" : "없음", trendDown: riskTotal > 0 },
        { title: "최근 업데이트", value: latestDate || "—", unit: "", color: "var(--green)", badge: "✺" },
      ];

      return { assets, cells, query, list, totalSlots, activeCount, riskTotal, latestDate, kpis };
    }

    function cellButton(asset, ws, cell) {
      if (!cell) {
        return html`
          <div class="pipe-cell" role="cell">
            <button type="button" class="pipe-cell-btn is-empty" data-action="open-pipeline-cell" data-asset="${asset.id}" data-ws="${ws.key}" aria-label="${asset.id} ${ws.label}, 데이터 없음 — 표준 WBS 템플릿 보기">
              <span class="pipe-empty-dot" aria-hidden="true">·</span>
              <small>데이터 없음</small>
            </button>
          </div>`;
      }
      const color = PHASE_COLOR[cell.status] || "var(--muted)";
      const phaseLabel = cell.phaseLabel || PHASE_LABEL[cell.status] || cell.status || "—";
      const badge = PHASE_BADGE[cell.status] || "○";
      const risks = Array.isArray(cell.riskFlags) ? cell.riskFlags : [];
      const riskTitle = risks.map((r) => RISK_LABEL[r] || r).join(", ");
      const ariaLabel = `${asset.id} ${ws.label}, ${phaseLabel}${risks.length ? `, 위험 ${risks.length}건` : ""}, 업데이트 ${cell.lastUpdated || "미상"}`;
      return html`
        <div class="pipe-cell" role="cell">
          <button type="button" class="pipe-cell-btn" data-action="open-pipeline-cell" data-asset="${asset.id}" data-ws="${ws.key}" style="border-inline-start-color:${raw(color)}" aria-label="${ariaLabel}">
            <span class="pipe-chip">
              <span class="pipe-dot" style="background:${raw(color)}" aria-hidden="true">${badge}</span>
              <span class="pipe-phase">${phaseLabel}</span>
            </span>
            <span class="pipe-cell-foot">
              ${risks.length
                ? raw(html`<span class="pipe-risk" title="${riskTitle}">⚠ ${risks.length}</span>`)
                : raw(html`<span class="pipe-clear">정상</span>`)}
              <small class="pipe-updated">${cell.lastUpdated || ""}</small>
            </span>
          </button>
        </div>`;
    }

    function matrixHTML(model) {
      if (!model.list.length) {
        if (model.query && searchEmptyState) {
          return searchEmptyState("pm-pipeline", "검색 결과 없음", "일치하는 자산이 없습니다. 검색어를 지우면 전체 매트릭스가 표시됩니다.");
        }
        return html`<div class="pipe-matrix-empty">일치하는 자산이 없습니다.</div>`;
      }
      const headRow = html`
        <div class="pipe-row pipe-row-head" role="row">
          <div class="pipe-corner" role="columnheader">자산 \\ 워크스트림</div>
          ${raw(WORKSTREAMS.map((ws) => html`<div class="pipe-colhead" role="columnheader">${ws.label}</div>`).join(""))}
        </div>`;
      const bodyRows = model.list.map((asset) => {
        const stageLabel = PHASE_LABEL[asset.stage] || asset.stage || "—";
        const stageColor = PHASE_COLOR[asset.stage] || "var(--muted)";
        const cells = WORKSTREAMS.map((ws) => cellButton(asset, ws, model.cells[cellKey(asset.id, ws.key)])).join("");
        return html`
          <div class="pipe-row" role="row" data-search-result="pm-pipeline">
            <div class="pipe-rowhead" role="rowheader">
              <strong class="pipe-asset-id">${asset.id}</strong>
              <span class="pipe-asset-stage"><span class="pipe-dot pipe-dot-sm" style="background:${raw(stageColor)}" aria-hidden="true"></span>${stageLabel}</span>
              <small class="pipe-asset-meta">${asset.indication || "적응증 미정"}</small>
            </div>
            ${raw(cells)}
          </div>`;
      }).join("");
      return html`
        <div class="pipe-matrix" role="table" aria-label="제약 파이프라인 자산 × 워크스트림 매트릭스" aria-rowcount="${model.list.length + 1}" aria-colcount="${WORKSTREAMS.length + 1}">
          ${raw(headRow)}
          ${raw(bodyRows)}
        </div>`;
    }

    function legendHTML() {
      const items = ["planned", "preclinical", "ind", "phase2", "phase3", "nda"];
      return html`<div class="pipe-legend" aria-hidden="true">${raw(items.map((status) =>
        html`<span class="pipe-legend-item"><span class="pipe-dot pipe-dot-sm" style="background:${raw(PHASE_COLOR[status])}"></span>${PHASE_LABEL[status]}</span>`
      ).join(""))}</div>`;
    }

    function renderPipelineHTML(input) {
      const model = pipelineViewModel(input);
      return html`
        <section class="kpis kpis-4">${raw(model.kpis.map((kpi) => kpiCard(kpi)).join(""))}</section>
        <section class="panel pipe-panel" aria-label="제약 파이프라인 보드">
          ${raw(panelHead("파이프라인 보드", null, legendHTML()))}
          <p class="pipe-hint">셀을 누르면 마일스톤·WBS·연결된 위키 문서가 열립니다. 색은 임상 단계를 뜻합니다.</p>
          ${raw(matrixHTML(model))}
        </section>`;
    }

    function wbsNode(task) {
      const status = safeWbsStatus(task.status);
      const statusLabel = WBS_STATUS_LABEL[status] || status;
      const owner = task.owner ? ` · ${task.owner}` : "";
      const deps = Array.isArray(task.deps) && task.deps.length ? ` · 의존 ${task.deps.join(", ")}` : "";
      const head = html`<span class="pipe-wbs-status pipe-wbs-${raw(status)}">${statusLabel}</span> <span class="pipe-wbs-name">${task.name}</span><small class="pipe-wbs-meta">${owner}${deps}</small>`;
      if (Array.isArray(task.children) && task.children.length) {
        return html`<details class="pipe-wbs" open><summary>${raw(head)}</summary><div class="pipe-wbs-kids">${raw(task.children.map(wbsNode).join(""))}</div></details>`;
      }
      return html`<div class="pipe-wbs-leaf">${raw(head)}</div>`;
    }

    function milestonesHTML(milestones) {
      const list = Array.isArray(milestones) ? milestones : [];
      if (!list.length) return "";
      return html`
        <ul class="pipe-milestones">
          ${raw(list.map((m) => html`
            <li class="pipe-ms ${raw(m.done ? "is-done" : "")}">
              <span class="pipe-ms-mark" aria-hidden="true">${m.done ? "●" : "○"}</span>
              <span class="pipe-ms-label">${m.label}</span>
              ${m.date ? raw(html`<small class="pipe-ms-date">${m.date}</small>`) : ""}
            </li>`).join(""))}
        </ul>`;
    }

    function cellSheetBody(input) {
      const data = input || {};
      const asset = data.asset || {};
      const ws = data.ws || {};
      const cell = data.cell || null;

      if (!cell) {
        const tmpl = WBS_TEMPLATES[ws.key] || [];
        return html`
          <div class="pipe-sheet">
            <p class="pipe-sheet-meta">${asset.id || ""} · ${asset.modality || "모달리티 미정"} · ${asset.indication || "적응증 미정"}</p>
            <p class="pipe-sheet-empty">이 워크스트림에는 아직 기록된 데이터가 없습니다. 아래는 <b>${ws.label || ""}</b> 표준 WBS 템플릿(예정)입니다.</p>
            <div class="pipe-wbs-tree">${raw(tmpl.map(wbsNode).join(""))}</div>
          </div>`;
      }

      const phaseLabel = cell.phaseLabel || PHASE_LABEL[cell.status] || cell.status || "—";
      const color = PHASE_COLOR[cell.status] || "var(--muted)";
      const risks = Array.isArray(cell.riskFlags) ? cell.riskFlags : [];
      const wbs = Array.isArray(cell.wbs) ? cell.wbs : [];
      return html`
        <div class="pipe-sheet">
          <div class="pipe-sheet-head">
            <span class="pipe-chip pipe-chip-lg"><span class="pipe-dot" style="background:${raw(color)}" aria-hidden="true">${PHASE_BADGE[cell.status] || "○"}</span>${phaseLabel}</span>
            ${cell.lastUpdated ? raw(html`<small class="pipe-sheet-date">업데이트 ${cell.lastUpdated}</small>`) : ""}
          </div>
          <dl class="pipe-fields">
            <div><dt>담당</dt><dd>${cell.owner || "미정"}</dd></div>
            <div><dt>다음 액션</dt><dd>${cell.nextAction || "—"}</dd></div>
            <div><dt>위험 플래그</dt><dd>${risks.length ? raw(escapeHtml(risks.map((r) => RISK_LABEL[r] || r).join(", "))) : "없음"}</dd></div>
          </dl>
          ${cell.milestones && cell.milestones.length ? raw(html`<h3 class="pipe-sheet-h">마일스톤</h3>${raw(milestonesHTML(cell.milestones))}`) : ""}
          ${wbs.length ? raw(html`<h3 class="pipe-sheet-h">WBS (작업 분해)</h3><div class="pipe-wbs-tree">${raw(wbs.map(wbsNode).join(""))}</div>`) : ""}
          ${cell.docLink && cell.docLink.article
            ? raw(html`<div class="pipe-sheet-actions"><button type="button" class="primary-btn" data-action="open-pipeline-wiki" data-cat="${cell.docLink.category || ""}" data-article="${cell.docLink.article}">◎ 연결된 위키 문서 열기</button></div>`)
            : ""}
        </div>`;
    }

    return {
      version: VERSION,
      WORKSTREAMS,
      PHASE_COLOR,
      pipelineViewModel,
      renderPipelineHTML,
      cellSheetBody,
    };
  }

  root.JooParkPipelineView = {
    version: VERSION,
    create: createPipelineView,
  };
})(typeof window !== "undefined" ? window : globalThis);
