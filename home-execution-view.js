(function (root) {
  "use strict";

  const VERSION = "joopark-home-execution-view/v1";

  function createHomeExecutionView(deps) {
    const options = deps || {};
    const html = options.html;
    const raw = options.raw;
    const escapeHtml = options.escapeHtml;
    const dueLabel = options.dueLabel;
    const homeEmptyHTML = options.homeEmptyHTML;

    if (typeof html !== "function" || typeof raw !== "function" || typeof escapeHtml !== "function" || typeof dueLabel !== "function" || typeof homeEmptyHTML !== "function") {
      throw new Error("home execution view requires html/raw/escapeHtml/dueLabel/homeEmptyHTML helpers");
    }

    function homeExecutionReasonChipsHTML(item) {
      const chips = Array.isArray(item.reasonChips) ? item.reasonChips : [];
      if (!chips.length) return "";
      return html`
        <span class="home-execution-reasons" aria-label="${item.title} 우선순위 근거">
          ${chips.map((chip) => raw(html`<span class="home-execution-reason" data-home-execution-reason-key="${chip.key}">${chip.label}</span>`))}
        </span>
      `;
    }

    function homeExecutionBucketSummaryHTML(model) {
      const buckets = Array.isArray(model.focusBuckets) ? model.focusBuckets : [];
      if (!buckets.length) return "";
      const allBucket = {
        key: "all",
        label: "전체",
        count: model.totalCandidateCount,
        todoCount: model.todoCount,
        issueCount: model.issueCount,
        topScore: model.topScore,
      };
      return html`
        <div class="home-execution-queue-summary" data-home-execution-buckets role="list" aria-label="오늘 실행 큐 마감 버킷 필터">
          ${[allBucket, ...buckets].map((bucket) => raw(html`
            <button type="button" class="home-execution-bucket" role="listitem" data-action="home-execution-bucket-filter" data-home-execution-bucket data-home-execution-bucket-key="${bucket.key}" data-home-execution-bucket-selected="${bucket.key === model.bucketFilter ? "true" : "false"}" data-home-execution-bucket-count="${bucket.count}" data-home-execution-bucket-todo-count="${bucket.todoCount}" data-home-execution-bucket-issue-count="${bucket.issueCount}" data-home-execution-bucket-top-score="${bucket.topScore}" aria-pressed="${bucket.key === model.bucketFilter ? "true" : "false"}" aria-label="오늘 실행 큐 ${bucket.label} 필터">
              <strong>${bucket.label}</strong>
              <span>${bucket.count}</span>
              <small>${bucket.todoCount} todo · ${bucket.issueCount} issue</small>
            </button>
          `))}
        </div>
      `;
    }

    function homeExecutionQueueHTML(model) {
      const items = model.items || [];
      const receiptDetail = `점수 ${model.topScore}-${model.windowFloorScore}; 근거 마감 ${model.windowDuePressureCount}, 고우선 ${model.windowHighPriorityCount}, 진행 ${model.windowActiveIssueCount}; 대표 ${model.windowLeadDriverLabel} ${model.windowLeadDriverCount}/${model.itemCount}`;
      return html`
        <section class="panel home-execution-queue" data-home-execution-queue data-home-execution-queue-source="${model.source}" data-home-execution-queue-explainable="true" data-home-execution-queue-bucketed="true" data-home-execution-queue-filterable="true" data-home-execution-queue-buckets="${model.bucketKey}" data-home-execution-queue-active-bucket="${model.activeBucket}" data-home-execution-queue-bucket-filter="${model.bucketFilter}" data-home-execution-queue-bucket-filter-label="${model.bucketFilterLabel}" data-home-execution-queue-filter-summary="${model.bucketFilter}:${model.itemCount}:${model.filteredCandidateCount}:${model.filteredTodoCount}:${model.filteredIssueCount}:${model.hiddenCandidateCount}:${model.totalCandidateCount}" data-home-execution-queue-rank-window="${model.itemCount}:${model.filteredCandidateCount}" data-home-execution-queue-score-window="${model.topScore}:${model.windowFloorScore}" data-home-execution-queue-score-driver="${model.windowDuePressureCount}:${model.windowHighPriorityCount}:${model.windowActiveIssueCount}" data-home-execution-queue-lead-driver="${model.windowLeadDriverKey}" data-home-execution-queue-lead-driver-count="${model.windowLeadDriverCount}" data-home-execution-queue-lead-driver-tie-count="${model.windowLeadDriverTieCount}" data-home-execution-queue-item-count="${model.itemCount}" data-home-execution-queue-hidden-candidate-count="${model.hiddenCandidateCount}" data-home-execution-queue-filtered-candidate-count="${model.filteredCandidateCount}" data-home-execution-queue-filtered-todo-count="${model.filteredTodoCount}" data-home-execution-queue-filtered-issue-count="${model.filteredIssueCount}" data-home-execution-queue-total-candidate-count="${model.totalCandidateCount}" data-home-execution-queue-todo-count="${model.todoCount}" data-home-execution-queue-issue-count="${model.issueCount}" data-home-execution-queue-overdue-count="${model.overdueCount}" data-home-execution-queue-today-count="${model.todayCount}" data-home-execution-queue-upcoming-count="${model.upcomingCount}" data-home-execution-queue-top-score="${model.topScore}">
          <div class="panel-head">
            <div>
              <h2>오늘 실행 큐</h2>
              <small>마감과 우선순위로 개인 할 일과 PM 이슈를 함께 정렬</small>
            </div>
            <span class="home-execution-queue-count">${model.itemCount}/${model.filteredCandidateCount} focus</span>
          </div>
          ${raw(homeExecutionBucketSummaryHTML(model))}
          <div class="home-execution-filter-summary" data-home-execution-filter-summary data-home-execution-filter-summary-active="${model.bucketFilter === "all" ? "false" : "true"}" data-home-execution-filter-summary-bucket="${model.bucketFilter}" data-home-execution-filter-summary-key="${model.bucketFilter}:${model.itemCount}:${model.filteredCandidateCount}:${model.filteredTodoCount}:${model.filteredIssueCount}:${model.hiddenCandidateCount}:${model.totalCandidateCount}" data-home-execution-receipt-compact="true" data-home-execution-receipt-detail="accessible" data-home-execution-filtered-count="${model.filteredCandidateCount}" data-home-execution-filtered-todo-count="${model.filteredTodoCount}" data-home-execution-filtered-issue-count="${model.filteredIssueCount}" data-home-execution-hidden-candidate-count="${model.hiddenCandidateCount}" data-home-execution-rank-window-count="${model.itemCount}" data-home-execution-rank-window-total="${model.filteredCandidateCount}" data-home-execution-score-window-top="${model.topScore}" data-home-execution-score-window-floor="${model.windowFloorScore}" data-home-execution-score-driver-due="${model.windowDuePressureCount}" data-home-execution-score-driver-priority="${model.windowHighPriorityCount}" data-home-execution-score-driver-active="${model.windowActiveIssueCount}" data-home-execution-lead-driver="${model.windowLeadDriverKey}" data-home-execution-lead-driver-label="${model.windowLeadDriverLabel}" data-home-execution-lead-driver-count="${model.windowLeadDriverCount}" data-home-execution-lead-driver-tie-count="${model.windowLeadDriverTieCount}" data-home-execution-filter-total-count="${model.totalCandidateCount}" role="note" tabindex="0" title="${receiptDetail}" aria-label="${model.bucketFilterLabel} 실행 큐 상세" aria-describedby="homeExecutionReceiptDetail">
            <span><strong>${model.bucketFilterLabel}</strong><small>${model.filteredCandidateCount}/${model.totalCandidateCount} 후보 · ${model.filteredTodoCount} todo/${model.filteredIssueCount} issue · 상위 ${model.itemCount}/${model.filteredCandidateCount} · 대표 ${model.windowLeadDriverLabel} ${model.windowLeadDriverCount}/${model.itemCount} · ${model.hiddenCandidateCount ? `${model.hiddenCandidateCount} 대기` : "모두 표시"}</small></span>
            ${model.bucketFilter === "all" ? "" : raw(html`<button type="button" data-action="home-execution-bucket-filter" data-home-execution-bucket-key="all" data-home-execution-filter-summary-reset aria-label="오늘 실행 큐 전체 필터">전체</button>`)}
          </div>
          <span id="homeExecutionReceiptDetail" class="sr-only" data-home-execution-receipt-description>${receiptDetail}</span>
          ${items.length ? raw(html`
            <ol class="home-execution-queue-list">
              ${items.map((item, index) => raw(html`
                <li data-home-execution-queue-item data-home-execution-queue-rank="${index + 1}" data-home-execution-queue-type="${item.type}" data-home-execution-queue-priority="${item.priority}" data-home-execution-queue-due-state="${item.dueState}" data-home-execution-queue-score="${item.score}" data-home-execution-queue-reason="${item.reasonKey}" data-home-execution-score-breakdown="${item.scoreBreakdown}">
                  <div class="home-execution-queue-row">
                    <button type="button" class="home-execution-queue-open" data-action="${item.action}" ${raw(item.type === "todo" ? `data-todo-id="${escapeHtml(item.id)}"` : `data-issue-id="${escapeHtml(item.id)}"`)} aria-label="${item.title} 열기">
                      <span class="home-execution-rank">${index + 1}</span>
                      <span class="home-execution-main">
                        <strong>${item.title}</strong>
                        <small>${item.context}</small>
                        ${raw(homeExecutionReasonChipsHTML(item))}
                      </span>
                      <span class="todo-due ${raw(dueLabel(item.due).cls)}">${dueLabel(item.due).text}</span>
                      <span class="home-execution-priority">${item.priorityLabel}</span>
                    </button>
                    <div class="home-execution-actions">
                      <button type="button" class="home-execution-quick-action" data-action="${item.quickAction}" data-home-execution-queue-quick="${item.type === "todo" ? "todo-complete" : "issue-next"}" data-home-execution-queue-next="${item.quickActionState}" ${raw(item.type === "todo" ? `data-todo-id="${escapeHtml(item.id)}"` : `data-issue-id="${escapeHtml(item.id)}" data-status="${escapeHtml(item.quickActionState)}"`)} aria-label="${item.title} ${item.type === "todo" ? "완료 처리" : `${item.quickActionLabel} 상태로 이동`}">${item.type === "todo" ? "완료" : `→ ${item.quickActionLabel}`}</button>
                    </div>
                  </div>
                </li>
              `))}
            </ol>
          `) : raw(homeEmptyHTML("execution-queue", "오늘 실행 큐가 비었습니다", "오늘 마감이나 이번 주 PM 이슈가 생기면 여기서 바로 열 수 있습니다.", "todo-add", "할 일 추가"))}
        </section>
      `;
    }

    return {
      version: VERSION,
      homeExecutionBucketSummaryHTML,
      homeExecutionQueueHTML,
      homeExecutionReasonChipsHTML,
    };
  }

  root.JooParkHomeExecutionView = {
    version: VERSION,
    create: createHomeExecutionView,
  };
})(window);
