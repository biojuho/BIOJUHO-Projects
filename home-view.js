/* ================================================================
 * JooPark Workspace — Home view orchestration.
 * Static non-module runtime loaded before app.js.
 * ================================================================ */

(function initJooParkHomeView(global) {
  "use strict";

  const VERSION = "joopark-home-view/v1";

  function createHomeView(deps = {}) {
    const {
      refs,
      dashboard,
      state,
      html,
      raw,
      setHTML,
      todayISO,
      addDaysISO,
      eventsOn,
      sortEvents,
      expandOccurrences,
      homeExecutionQueueModel,
      publishReadinessItems,
      safeGithubUrl,
      shortCommit,
      projectBenchmarkContext,
      recordByKey,
      firstStatusItem,
      firstStringIncluding,
      firstNonPassingStatusItem,
      publishEvidenceFresh,
      formatKoreanShort,
      clampInteger: clampIntegerDep,
      homeFirstRunGuidanceModel,
      homeProjectFollowThroughModel,
      kpiCard,
      homeTileHTML,
      homeEmptyHTML,
      HEALTH_COLOR,
      homeListPreviewHTML,
      homeTodayCommandContentHTML,
      homeHeroHTML,
      homeExecutionQueueHTML,
      dashboardIntelligenceHTML,
    } = deps;
    const renderDashboardIntelligenceHTML = typeof dashboardIntelligenceHTML === "function" ? dashboardIntelligenceHTML : function () { return ""; };
    const clampInteger = typeof clampIntegerDep === "function"
      ? clampIntegerDep
      : function (value, min, max = Number.POSITIVE_INFINITY, fallback = 0) {
        const parsed = Number(value);
        const safeParsed = Number.isFinite(parsed) ? parsed : fallback;
        return Math.min(max, Math.max(min, Math.trunc(safeParsed)));
      };

    function firstClampedCount(values, fallback = 0) {
      const list = Array.isArray(values) ? values : [];
      const match = list.find((value) => Number.isFinite(Number(value)));
      return match === undefined ? fallback : clampInteger(match, 0, Number.POSITIVE_INFINITY, fallback);
    }

    function homeCommandTilesHTML({
      todayEventsHTML,
      todayTodosHTML,
      upcomingHTML,
      totalProjects,
      portfolioBody,
      totalIssues,
      kanbanBody,
      dashboard,
      ganttBody,
      teamBody,
      unhealthy,
      instancesBody,
      schemaTotalTables,
      schemaBody,
      slow,
      queriesBody,
      pendingMig,
      backupsBody,
    }) {
      return html`
        <section class="home-command">
          <article class="panel home-today">
            <div class="panel-head"><div><h2>오늘</h2><a href="#cal" data-action="nav-to" data-view="cal">일정 전체 ›</a></div></div>
            <div class="agenda-list">${raw(todayEventsHTML)}</div>
            <p class="home-today-label">오늘 마감 할 일</p>
            ${raw(todayTodosHTML)}
          </article>
          <article class="panel home-upcoming-panel">
            <div class="panel-head"><div><h2>다가오는 7일</h2><a href="#cal" data-action="nav-to" data-view="cal">달력 ›</a></div></div>
            ${raw(upcomingHTML)}
          </article>
        </section>
        <p class="home-section-title">팀 · 시스템 관리</p>
        <section class="home-tiles">
          ${raw(homeTileHTML("프로젝트 포트폴리오", `${totalProjects}개`,        "pm-portfolio",   portfolioBody))}
          ${raw(homeTileHTML("Kanban 보드",         `${totalIssues}개 이슈`,    "pm-kanban",      kanbanBody))}
          ${raw(homeTileHTML("간트 마일스톤",        `${dashboard.gantt.tasks.filter((t) => t.milestone).length}개`, "pm-gantt", ganttBody))}
          ${raw(homeTileHTML("팀 부하",              `${dashboard.team.length}명`, "pm-team",      teamBody))}
          ${raw(homeTileHTML("DB 인스턴스",          `${unhealthy}건 주의`,       "dbm-instances",instancesBody))}
          ${raw(homeTileHTML("스키마",               `${schemaTotalTables} 테이블`,"dbm-schema",   schemaBody))}
          ${raw(homeTileHTML("질의 성능",            `slow ${slow}건`,            "dbm-queries",  queriesBody))}
          ${raw(homeTileHTML("백업 / 마이그",         `대기 ${pendingMig}건`,       "dbm-backups",  backupsBody))}
        </section>
      `;
    }
    
    function homeFirstRunGuidanceHTML({
      firstRunSteps,
      firstRunReadyCount,
      firstRunActionRequiredCount,
      firstRunNextStep,
      firstRunGuidedStartItems,
      firstRunGuidedStartCoverage,
    }) {
      const firstRunGuidedStartReady = firstRunGuidedStartCoverage === 1 && firstRunGuidedStartItems.length === 3;
      return html`
        <section class="panel home-first-run" data-home-first-run-guidance data-home-first-run-variant="task_strip" data-home-first-run-source="linear_jira_onboarding_benchmark" data-home-first-run-step-count="${firstRunSteps.length}" data-home-first-run-ready-count="${firstRunReadyCount}" data-home-first-run-action-required-count="${firstRunActionRequiredCount}" data-home-first-run-next-key="${firstRunNextStep.key}" data-home-first-run-next-action="${firstRunNextStep.action}" data-home-first-run-next-view="${firstRunNextStep.viewName || ""}" data-home-first-run-guided-start-ready="${firstRunGuidedStartReady ? "true" : "false"}" data-home-first-run-guided-start-coverage="${firstRunGuidedStartCoverage}" data-home-first-run-guided-start-item-count="${firstRunGuidedStartItems.length}">
          <div class="panel-head">
            <div>
              <h2>처음 5분 quick start</h2>
              <small>오늘 할 일, 실행 프로젝트, 로컬 백업을 한 화면에서 시작</small>
            </div>
            <span class="home-first-run-score">${firstRunReadyCount}/${firstRunSteps.length} ready</span>
          </div>
          <div class="home-first-run-guided-start" data-home-first-run-guided-start data-home-first-run-guided-start-coverage="${firstRunGuidedStartCoverage}" data-home-first-run-guided-start-item-count="${firstRunGuidedStartItems.length}">
            ${firstRunGuidedStartItems.map((item) => raw(html`
              <article class="home-first-run-guided-start-item" data-home-first-run-guided-start-item data-home-first-run-guided-start-key="${item.key}" data-home-first-run-guided-start-status="${item.status}" data-home-first-run-guided-start-action="${item.action}" data-home-first-run-guided-start-metric="${item.metric}">
                <small>${item.metric}</small>
                <strong>${item.label}</strong>
                <p>${item.detail}</p>
              </article>
            `))}
          </div>
          <ol class="home-first-run-steps">
            ${firstRunSteps.map((step, index) => raw(html`
              <li data-home-first-run-step data-home-first-run-step-key="${step.key}" data-home-first-run-step-status="${step.status}" data-home-first-run-step-action="${step.action}" data-home-first-run-step-view="${step.viewName || ""}">
                <span>${index + 1}</span>
                <div>
                  <strong>${step.label}</strong>
                  <small>${step.metric}</small>
                  <p>${step.detail}</p>
                </div>
                <button type="button" class="small-action" data-action="${step.action}" data-view="${step.viewName || ""}">${step.actionLabel}</button>
              </li>
            `))}
          </ol>
        </section>
      `;
    }
    
    function homeProjectFollowThroughHTML({
      projectFollowThroughSteps,
      projectFollowThroughReadyCount,
      projectFollowThroughActionRequiredCount,
      projectFollowThroughNextStep,
    }) {
      if (!projectFollowThroughSteps.length) return "";
      return html`
        <section class="panel home-project-followthrough" data-home-project-followthrough data-home-project-followthrough-variant="activation_ladder" data-home-project-followthrough-source="linear_project_jira_work_item_benchmark" data-home-project-followthrough-step-count="${projectFollowThroughSteps.length}" data-home-project-followthrough-ready-count="${projectFollowThroughReadyCount}" data-home-project-followthrough-action-required-count="${projectFollowThroughActionRequiredCount}" data-home-project-followthrough-next-key="${projectFollowThroughNextStep.key || ""}" data-home-project-followthrough-next-action="${projectFollowThroughNextStep.action || ""}" data-home-project-followthrough-next-view="${projectFollowThroughNextStep.viewName || ""}">
          <div class="panel-head">
            <div>
              <h2>Project follow-through</h2>
              <small>프로젝트 생성 후 실행 가능한 상태까지 이어지는 다음 행동</small>
            </div>
            <span class="home-project-followthrough-score">${projectFollowThroughReadyCount}/${projectFollowThroughSteps.length} ready</span>
          </div>
          <ol class="home-project-followthrough-steps">
            ${projectFollowThroughSteps.map((step) => raw(html`
              <li data-home-project-followthrough-step data-home-project-followthrough-step-key="${step.key}" data-home-project-followthrough-step-status="${step.status}" data-home-project-followthrough-step-action="${step.action}" data-home-project-followthrough-step-view="${step.viewName}">
                <span>${step.status === "ready" ? "Ready" : "Next"}</span>
                <div>
                  <strong>${step.label}</strong>
                  <small>${step.metric}</small>
                  <p>${step.detail}</p>
                </div>
                <button type="button" class="small-action" data-action="${step.action}" data-view="${step.viewName}"${step.defaultMilestone ? raw(' data-default-milestone="true"') : ""}>${step.actionLabel}</button>
              </li>
            `))}
          </ol>
        </section>
      `;
    }

    function homeLaunchOperationsHTML(model) {
      const {
        publishBlockers, launchProofReady, benchmarkFocused, sourceBacked, readinessCards,
        currentLaunchActionKey, currentLaunchActionLabel, currentLaunchActionStatus,
        currentLaunchActionCommandCount, currentLaunchWithheldCount, safeToDispatch,
        externalClaimReady, launchTransition, currentLaunchStage, launchTransitionNextStage,
        launchTransitionPendingCount, launchTransitionGateCommand, launchInstallMatrix,
        launchInstallMatrixRows, launchInstallMatrixSignals, launchInstallMatrixPathCount,
        launchInstallMatrixSignalCount, remoteWorkflowFileLedger,
        remoteWorkflowFileLedgerItems, remoteWorkflowFileLedgerFileCount,
        remoteWorkflowFileLedgerReadyCount, remoteWorkflowFileLedgerMissingCount,
        remoteWorkflowFileLedgerMismatchCount, remoteWorkflowFileLedgerReady, launchProofLedger,
        launchProofLedgerItems, launchProofLedgerReady,
        currentLaunchActionDetail, currentLaunchActionCommand, launchTransitionNextLabel,
        launchActionChecklistText, launchActionChecklistReady, launchActionChecklistStatus,
        launchActionChecklistActiveKey, launchActionChecklistImmediateCommand,
        launchActionChecklistDeferredCommand, launchActionChecklistRecheckSteps,
        launchActionChecklistSourceArtifacts, launchActionChecklistDispatchApproval,
        launchActionChecklistVerificationOnly, launchActionChecklistGuard,
        launchBlockerResolverText, launchBlockerResolverReady, launchBlockerActiveKey,
        launchBlockerResolution, launchBlockerItems, launchBlockerProofCommands,
        launchBlockerItemCount, launchBlockerPassCount, launchBlockerActionRequiredCount,
        launchBlockerDeferredCount, launchBlockerProofCommandCount, launchBlockerFallbackCommands,
        launchEvidenceGapItems, launchPostInstallIntakeForGap, launchBlockerDispatchGuard,
        launchBlockerActiveItem, workflowInstallShortcutText,
        workflowInstallShortcutReady, workflowScopeInstallBlocked, workflowInstallShortcutPaths,
        workflowInstallShortcutCommandCount, workflowInstallShortcutTargetCount,
        workflowInstallShortcutPrimaryPath, workflowInstallShortcutPrimaryCommand,
        workflowInstallShortcutVerifyCommand, workflowInstallShortcutDefaultBranchGuard,
        workflowInstallShortcutScopeGuard, launchBlockerFallbackPath, postInstallEvidenceText,
        postInstallEvidenceReady, postInstallEvidenceStatus, postInstallEvidenceProofComplete,
        postInstallEvidenceCompletedCount, postInstallEvidencePendingCount,
        postInstallEvidenceFieldCount, postInstallEvidenceCommands, postInstallEvidenceSignals,
        postInstallEvidenceFields, postInstallEvidenceIntake, postInstallQuickProofReady,
        postInstallQuickProofStepCount, postInstallQuickProofCoverage, postInstallQuickProofSteps,
        postInstallQuickProofFieldMappingReady, postInstallQuickProofFieldMappingCoverage,
        postInstallQuickProofMappedFieldCount, postInstallQuickProofCompletedMappedFieldCount,
        postInstallQuickProofFieldMappings,
        postInstallVerificationSequence,
        postInstallVerificationSequenceReady, postInstallVerificationFinalCommand,
        postInstallEvidenceStopCondition, externalClaimGuardText, externalClaimGuardReady,
        externalClaimGuard, externalClaimGuardBlockedCount, externalClaimGuardRequirementCount,
        externalClaimGuardCommands, externalClaimGuardPrimaryRequirement,
        externalClaimGuardPrimarySignal, externalClaimGuardPrimaryCommand,
        externalClaimGuardRequirements, externalClaimGuardSignals, homeExternalClaimGuardText,
      } = model;
      const launchProofLedgerRequiredTotal = firstClampedCount([launchProofLedger.requiredProofCount, launchProofLedgerItems.length]);
      const launchProofLedgerReadyTotal = firstClampedCount([launchProofLedger.readyProofCount]);
      const launchProofLedgerPendingTotal = firstClampedCount(
        [launchProofLedger.pendingProofCount],
        Math.max(0, launchProofLedgerRequiredTotal - launchProofLedgerReadyTotal),
      );
    
      return html`
        <section class="panel home-readiness" data-home-readiness data-home-publish-blockers="${publishBlockers.length}" data-home-launch-proof-ready="${launchProofReady ? "true" : "false"}" data-home-benchmark-count="${benchmarkFocused.length}" data-home-source-backed-count="${sourceBacked.length}">
          <div class="panel-head">
            <div><h2>공개 준비 요약</h2><a href="#system" data-action="nav-to" data-view="system">시스템 상태 ›</a></div>
            <small>첫 방문자가 신뢰도를 판단하는 핵심 증거</small>
          </div>
          <div class="home-readiness-grid">
            ${readinessCards.map((card) => raw(html`
              <button type="button" class="home-readiness-card" data-action="nav-to" data-view="${card.viewName}" data-home-readiness-card="${card.key}" data-readiness-tone="${card.tone}" data-home-readiness-card-evidence-count="${card.evidenceCount || 0}">
                <span>${card.label}</span>
                <strong>${card.value}</strong>
                <small>${card.detail}</small>
              </button>
            `))}
          </div>
          <div class="home-launch-next" data-home-launch-next-action data-home-launch-action-key="${currentLaunchActionKey}" data-home-launch-action-label="${currentLaunchActionLabel}" data-home-launch-action-status="${currentLaunchActionStatus}" data-home-launch-command-count="${currentLaunchActionCommandCount}" data-home-launch-withheld-count="${currentLaunchWithheldCount}" data-home-launch-safe-to-dispatch="${safeToDispatch ? "true" : "false"}" data-home-launch-ready-for-external-claim="${externalClaimReady ? "true" : "false"}" data-home-launch-transition-source="${launchTransition.source || "ui-fallback"}" data-home-launch-transition-current-stage="${currentLaunchStage}" data-home-launch-transition-next-stage="${launchTransitionNextStage}" data-home-launch-transition-pending-count="${launchTransitionPendingCount}" data-home-launch-transition-gate-command="${launchTransitionGateCommand}" data-home-launch-install-matrix-source="${launchInstallMatrix.source || "missing"}" data-home-launch-install-matrix-path-count="${launchInstallMatrixPathCount}" data-home-launch-install-matrix-signal-count="${launchInstallMatrixSignalCount}" data-home-launch-install-matrix-next-stage="${launchInstallMatrix.nextStageKey || "verify_visibility"}" data-home-remote-workflow-file-ledger-source="${remoteWorkflowFileLedger.source || "missing"}" data-home-remote-workflow-file-ledger-status="${remoteWorkflowFileLedger.status || "missing"}" data-home-remote-workflow-file-ledger-file-count="${remoteWorkflowFileLedgerFileCount}" data-home-remote-workflow-file-ledger-ready-count="${remoteWorkflowFileLedgerReadyCount}" data-home-remote-workflow-file-ledger-missing-count="${remoteWorkflowFileLedgerMissingCount}" data-home-remote-workflow-file-ledger-mismatch-count="${remoteWorkflowFileLedgerMismatchCount}" data-home-remote-workflow-file-ledger-not-checked-count="${remoteWorkflowFileLedger.notCheckedCount || 0}" data-home-launch-proof-ledger-source="${launchProofLedger.source || "missing"}" data-home-launch-proof-ledger-status="${launchProofLedger.status || "missing"}" data-home-launch-proof-ledger-required-count="${launchProofLedgerRequiredTotal}" data-home-launch-proof-ledger-ready-count="${launchProofLedgerReadyTotal}" data-home-launch-proof-ledger-pending-count="${launchProofLedgerPendingTotal}" data-home-launch-proof-ledger-current-gate="${launchProofLedger.currentGate || "capture_launch_proof"}">
            <div>
              <span>현재 launch action</span>
              <strong>${currentLaunchActionLabel}</strong>
              <p>${currentLaunchActionDetail}</p>
            </div>
            <code>${currentLaunchActionCommand}</code>
            <div class="home-launch-transition" data-home-launch-transition-preview>
              <span>next transition</span>
              <strong>${currentLaunchStage} -> ${launchTransitionNextStage}</strong>
              <p>${launchTransitionNextLabel} · pending ${launchTransitionPendingCount} · ${safeToDispatch ? "safeToDispatch=true" : "dispatch withheld"}</p>
              <code>${launchTransitionGateCommand}</code>
            </div>
            <div class="home-launch-transition home-launch-install-matrix" data-home-launch-install-matrix>
              <span>install verification matrix</span>
              <strong>${launchInstallMatrixPathCount} paths -> ${launchInstallMatrix.nextStageKey || "verify_visibility"}</strong>
              <p>${launchInstallMatrixSignalCount} signals · remoteWorkflowFilesReady=true · remoteWorkflowVisibilityReady=true · dispatchReady=true · driftDispatchReady=true · allDispatchReady=true · verify-launch-handoff reports safeToDispatch=true</p>
              <code>${launchInstallMatrix.handoffCommand || launchTransitionGateCommand}</code>
            </div>
            <div class="home-launch-transition home-remote-workflow-file-ledger" data-home-remote-workflow-file-ledger>
              <span>remote workflow file acceptance ledger</span>
              <strong>${remoteWorkflowFileLedgerReadyCount}/${remoteWorkflowFileLedgerFileCount} files ready</strong>
              <p>${remoteWorkflowFileLedger.status || "remote_file_install_required"} · missing ${remoteWorkflowFileLedgerMissingCount} · mismatch ${remoteWorkflowFileLedgerMismatchCount} · remoteMatchesTemplate required</p>
              <code>${remoteWorkflowFileLedger.verifyCommand || "node scripts/check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write"}</code>
            </div>
            <div class="home-launch-transition home-launch-proof-ledger" data-home-launch-proof-ledger>
              <span>launch proof acceptance ledger</span>
              <strong>${launchProofLedgerReadyTotal}/${launchProofLedgerRequiredTotal} proofs ready</strong>
              <p>${launchProofLedger.status || "proof_blocked_until_dispatch"} · pending ${launchProofLedgerPendingTotal} · ${launchProofLedger.deferredUntil || "safeToDispatch=true"}</p>
              <code>${launchProofLedger.captureWriteCommand || "node scripts/capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --write"}</code>
            </div>
            <dl>
              <div><dt>safeToDispatch</dt><dd>${safeToDispatch ? "true" : "false"}</dd></div>
              <div><dt>withheld</dt><dd>${currentLaunchWithheldCount}</dd></div>
              <div><dt>externalClaim</dt><dd>${externalClaimReady ? "true" : "false"}</dd></div>
            </dl>
            <button type="button" class="secondary-btn" data-action="nav-to" data-view="system">실행 패킷 보기</button>
          </div>
          ${launchActionChecklistText ? raw(html`
            <div class="home-launch-action-checklist" data-home-launch-action-checklist data-home-launch-action-checklist-ready="${launchActionChecklistReady ? "true" : "false"}" data-home-launch-action-checklist-active="${launchActionChecklistActiveKey}" data-home-launch-action-checklist-status="${launchActionChecklistStatus}" data-home-launch-action-checklist-recheck-count="${launchActionChecklistRecheckSteps.length}" data-home-launch-action-checklist-source-artifact-count="${launchActionChecklistSourceArtifacts.length}" data-home-launch-action-checklist-dispatch-approval="${launchActionChecklistDispatchApproval ? "true" : "false"}" data-home-launch-action-checklist-verification-only="${launchActionChecklistVerificationOnly ? "true" : "false"}" data-home-launch-action-checklist-withheld-count="${currentLaunchWithheldCount}" data-home-launch-action-checklist-immediate-command="${launchActionChecklistImmediateCommand}" data-home-launch-action-checklist-deferred-command="${launchActionChecklistDeferredCommand}" data-home-launch-action-checklist-guard="${launchActionChecklistGuard}">
              <div class="home-launch-action-checklist-summary">
                <span>launch action checklist</span>
                <strong>${launchActionChecklistActiveKey}</strong>
                <p>${launchActionChecklistStatus} · recheck ${launchActionChecklistRecheckSteps.length} · source artifacts ${launchActionChecklistSourceArtifacts.length} · dispatchApproval=${launchActionChecklistDispatchApproval ? "true" : "false"} · verificationOnly=${launchActionChecklistVerificationOnly ? "true" : "false"}</p>
              </div>
              <div class="home-launch-action-checklist-command">
                <span>immediate command</span>
                <code>${launchActionChecklistImmediateCommand}</code>
                <p><b>Deferred proof</b> ${launchActionChecklistDeferredCommand}</p>
              </div>
              <ol class="home-launch-action-checklist-steps" data-home-launch-action-checklist-recheck-sequence>
                ${launchActionChecklistRecheckSteps.map((step, index) => raw(html`
                  <li data-home-launch-action-checklist-step data-home-launch-action-checklist-step-key="${step.key || ""}" data-home-launch-action-checklist-step-command="${step.command || ""}" data-home-launch-action-checklist-step-expected="${step.expected || ""}" data-home-launch-action-checklist-step-source="${step.sourceArtifact || ""}">
                    <div>
                      <strong>${index + 1}. ${step.label || step.key || "Recheck step"}</strong>
                      <small>${step.key || ""}</small>
                    </div>
                    <code>${step.command || ""}</code>
                    <p>${step.expected || ""}</p>
                    <small>${step.sourceArtifact || ""} · ${step.stopCondition || ""}</small>
                  </li>
                `))}
              </ol>
              <div class="home-launch-action-checklist-sources">
                ${launchActionChecklistSourceArtifacts.map((artifact) => raw(html`<code data-home-launch-action-checklist-source-artifact="${artifact}">${artifact}</code>`))}
              </div>
              <p class="home-launch-action-checklist-guard">${launchActionChecklistGuard}</p>
              <pre data-home-launch-action-checklist-text hidden>${launchActionChecklistText}</pre>
              <div class="home-launch-action-checklist-actions">
                <button type="button" class="secondary-btn" data-action="copy-home-launch-action-checklist" data-home-launch-action-checklist-copy>checklist 복사</button>
                <span data-home-launch-action-checklist-copy-status aria-live="polite"></span>
              </div>
            </div>
          `) : ""}
          ${launchBlockerResolverText ? raw(html`
            <div class="home-launch-blocker-resolver" data-home-launch-blocker-resolver data-home-launch-blocker-resolver-ready="${launchBlockerResolverReady ? "true" : "false"}" data-home-launch-blocker-resolver-active="${launchBlockerActiveKey}" data-home-launch-blocker-resolver-status="${launchBlockerResolution.status || "action_required"}" data-home-launch-blocker-resolver-source="${launchBlockerResolution.source || "missing"}" data-home-launch-blocker-resolver-repo="${launchBlockerResolution.repo || "biojuho/BIOJUHO-Projects"}" data-home-launch-blocker-resolver-item-count="${launchBlockerItemCount}" data-home-launch-blocker-resolver-pass-count="${launchBlockerPassCount}" data-home-launch-blocker-resolver-action-required-count="${launchBlockerActionRequiredCount}" data-home-launch-blocker-resolver-deferred-count="${launchBlockerDeferredCount}" data-home-launch-blocker-resolver-proof-command-count="${launchBlockerProofCommandCount}" data-home-launch-blocker-resolver-fallback-command-count="${launchBlockerFallbackCommands.length}" data-home-launch-blocker-resolver-evidence-gap-count="${launchEvidenceGapItems.length}" data-home-launch-blocker-resolver-remote-files-ready="${remoteWorkflowFileLedgerReady ? "true" : "false"}" data-home-launch-blocker-resolver-launch-proof-ready="${launchProofLedgerReady ? "true" : "false"}" data-home-launch-blocker-resolver-post-install-proof-complete="${launchPostInstallIntakeForGap.proofComplete ? "true" : "false"}" data-home-launch-blocker-resolver-dispatch-guard="${launchBlockerDispatchGuard}">
              <div class="home-launch-blocker-summary">
                <span>launch unblock resolver</span>
                <strong>${launchBlockerActiveItem.label || launchBlockerActiveKey}</strong>
                <p>${launchBlockerResolution.status || "action_required"} · ${launchBlockerActiveItem.blockedSignal || "blocked signal unavailable"}</p>
              </div>
              <div class="home-launch-blocker-active" data-home-launch-blocker-resolver-active-item data-home-launch-blocker-resolver-active-status="${launchBlockerActiveItem.status || "action_required"}">
                <span>primary proof command</span>
                <code data-home-launch-blocker-resolver-primary-command>${launchBlockerActiveItem.proofCommand || ""}</code>
                <p>${launchBlockerActiveItem.action || ""}</p>
                <p><b>Expected</b> ${launchBlockerActiveItem.expectedValue || ""}</p>
                <p><b>Stop</b> ${launchBlockerActiveItem.stopCondition || ""}</p>
              </div>
              <div class="home-launch-blocker-evidence-gap" data-home-launch-blocker-evidence-gap data-home-launch-blocker-evidence-gap-count="${launchEvidenceGapItems.length}">
                <span>evidence gap</span>
                <ul>
                  ${launchEvidenceGapItems.map((item) => raw(html`
                    <li data-home-launch-blocker-evidence-gap-item data-home-launch-blocker-evidence-gap-key="${item.key}" data-home-launch-blocker-evidence-gap-ready="${item.ready ? "true" : "false"}">
                      <strong>${item.label}</strong>
                      <small>${item.status}</small>
                      <p>${item.summary}</p>
                      <code>${item.command}</code>
                    </li>
                  `))}
                </ul>
              </div>
              ${workflowInstallShortcutText ? raw(html`
                <div class="home-workflow-install-shortcut" data-home-workflow-install-shortcut data-home-workflow-install-shortcut-ready="${workflowInstallShortcutReady ? "true" : "false"}" data-home-workflow-install-shortcut-status="${workflowScopeInstallBlocked ? "workflow_scope_blocked_use_ui_or_refresh" : "workflow_scope_available_use_cli"}" data-home-workflow-install-shortcut-path-count="${workflowInstallShortcutPaths.length}" data-home-workflow-install-shortcut-command-count="${workflowInstallShortcutCommandCount}" data-home-workflow-install-shortcut-target-count="${workflowInstallShortcutTargetCount}" data-home-workflow-install-shortcut-primary-path="${workflowInstallShortcutPrimaryPath.key || ""}" data-home-workflow-install-shortcut-primary-command="${workflowInstallShortcutPrimaryCommand}" data-home-workflow-install-shortcut-verify-command="${workflowInstallShortcutVerifyCommand}">
                  <div>
                    <span>workflow install shortcut</span>
                    <strong>${workflowScopeInstallBlocked ? "GitHub UI path 또는 scope refresh" : "CLI install path ready"}</strong>
                    <p>${workflowInstallShortcutTargetCount} workflow files · ${workflowInstallShortcutPaths.length} paths · ${workflowInstallShortcutCommandCount} commands</p>
                  </div>
                  <div class="home-workflow-install-shortcut-guards">
                    <span data-home-workflow-install-shortcut-guard>${workflowInstallShortcutDefaultBranchGuard}</span>
                    <span data-home-workflow-install-shortcut-guard>${workflowInstallShortcutScopeGuard}</span>
                  </div>
                  <ul>
                    ${workflowInstallShortcutPaths.map((path) => raw(html`
                      <li data-home-workflow-install-shortcut-path data-home-workflow-install-shortcut-path-key="${path.key || ""}" data-home-workflow-install-shortcut-path-command-count="${Array.isArray(path.commands) ? path.commands.length : 0}">
                        <div>
                          <strong>${path.label || path.key}</strong>
                          <small>${Array.isArray(path.commands) ? path.commands.length : 0} commands</small>
                        </div>
                        <p>${path.when || path.success || ""}</p>
                        ${(Array.isArray(path.commands) ? path.commands.slice(0, 3) : []).map((command) => raw(html`<code data-home-workflow-install-shortcut-command>${command}</code>`))}
                        <small>${path.guard || ""}</small>
                      </li>
                    `))}
                  </ul>
                  <p><b>Verify</b> <code data-home-workflow-install-shortcut-verify>${workflowInstallShortcutVerifyCommand}</code></p>
                </div>
              `) : ""}
              <ul class="home-launch-blocker-items">
                ${launchBlockerItems.map((item) => raw(html`
                  <li data-home-launch-blocker-resolver-item data-home-launch-blocker-resolver-item-key="${item.key || ""}" data-home-launch-blocker-resolver-item-status="${item.status || ""}">
                    <div>
                      <strong>${item.label || item.key}</strong>
                      <span>${item.status || "unknown"}</span>
                    </div>
                    <p>${item.blockedSignal || item.evidence || ""}</p>
                    <code>${item.proofCommand || ""}</code>
                  </li>
                `))}
              </ul>
              <div class="home-launch-blocker-fallback" data-home-launch-blocker-resolver-fallback>
                <span>GitHub UI fallback</span>
                <strong>${launchBlockerFallbackPath.label || "GitHub UI path"}</strong>
                <p>${launchBlockerFallbackPath.when || "Use when the CLI token still lacks workflow scope or browser-based file creation is preferred."}</p>
                <div>
                  ${launchBlockerFallbackCommands.map((command) => raw(html`<code data-home-launch-blocker-resolver-fallback-command>${command}</code>`))}
                </div>
              </div>
              <p class="home-launch-blocker-guard" data-home-launch-blocker-resolver-dispatch-guard-text>${launchBlockerDispatchGuard}</p>
              <pre data-home-launch-blocker-resolver-text hidden>${launchBlockerResolverText}</pre>
              <div class="home-launch-blocker-actions">
                <button type="button" class="secondary-btn" data-action="copy-home-launch-blocker-resolver" data-home-launch-blocker-resolver-copy>resolver 복사</button>
                <span data-home-launch-blocker-resolver-copy-status aria-live="polite"></span>
              </div>
            </div>
          `) : ""}
          ${postInstallEvidenceText ? raw(html`
            <div class="home-post-install-intake" data-home-post-install-evidence-intake data-post-install-evidence-intake data-home-post-install-evidence-intake-ready="${postInstallEvidenceReady ? "true" : "false"}" data-home-post-install-evidence-intake-status="${postInstallEvidenceStatus}" data-home-post-install-evidence-intake-proof-complete="${postInstallEvidenceProofComplete ? "true" : "false"}" data-home-post-install-evidence-intake-completed-count="${postInstallEvidenceCompletedCount}" data-home-post-install-evidence-intake-pending-count="${postInstallEvidencePendingCount}" data-home-post-install-evidence-intake-field-count="${postInstallEvidenceFieldCount}" data-home-post-install-evidence-intake-command-count="${postInstallEvidenceCommands.length}" data-home-post-install-evidence-intake-signal-count="${postInstallEvidenceSignals.length}" data-home-post-install-evidence-intake-sequence-count="${postInstallVerificationSequence.length}" data-home-post-install-evidence-intake-sequence-ready="${postInstallVerificationSequenceReady ? "true" : "false"}" data-home-post-install-evidence-intake-final-command="${postInstallVerificationFinalCommand}" data-post-install-evidence-intake-ready="${postInstallEvidenceReady ? "true" : "false"}" data-post-install-evidence-intake-proof-complete="${postInstallEvidenceProofComplete ? "true" : "false"}" data-post-install-evidence-intake-completed-count="${postInstallEvidenceCompletedCount}" data-post-install-evidence-intake-pending-count="${postInstallEvidencePendingCount}" data-post-install-evidence-intake-field-count="${postInstallEvidenceFieldCount}" data-post-install-evidence-intake-command-count="${postInstallEvidenceCommands.length}" data-post-install-evidence-intake-signal-count="${postInstallEvidenceSignals.length}" data-post-install-evidence-intake-sequence-count="${postInstallVerificationSequence.length}" data-post-install-evidence-intake-final-command="${postInstallVerificationFinalCommand}" data-post-install-evidence-intake-dispatch-guard="${postInstallEvidenceStopCondition}" data-post-install-quick-proof-ready="${postInstallQuickProofReady ? "true" : "false"}" data-post-install-quick-proof-step-count="${postInstallQuickProofStepCount}" data-post-install-quick-proof-coverage="${postInstallQuickProofCoverage}" data-post-install-quick-proof-final-command="${postInstallEvidenceIntake.quickProofFinalCommand || postInstallVerificationFinalCommand}" data-post-install-quick-proof-field-mapping-ready="${postInstallQuickProofFieldMappingReady ? "true" : "false"}" data-post-install-quick-proof-field-mapping-coverage="${postInstallQuickProofFieldMappingCoverage}" data-post-install-quick-proof-mapped-field-count="${postInstallQuickProofMappedFieldCount}" data-post-install-quick-proof-completed-mapped-field-count="${postInstallQuickProofCompletedMappedFieldCount}">
              <div class="home-post-install-intake-summary">
                <span>post-install proof intake</span>
                <strong>${postInstallEvidenceCompletedCount}/${postInstallEvidenceFieldCount} proof fields complete</strong>
                <p>${postInstallEvidenceStatus} · proofComplete=${postInstallEvidenceProofComplete ? "true" : "false"} · pending ${postInstallEvidencePendingCount}</p>
              </div>
              <div class="home-post-install-quick-proof" data-post-install-quick-proof data-post-install-quick-proof-ready="${postInstallQuickProofReady ? "true" : "false"}" data-post-install-quick-proof-step-count="${postInstallQuickProofStepCount}" data-post-install-quick-proof-coverage="${postInstallQuickProofCoverage}" data-post-install-quick-proof-field-mapping-ready="${postInstallQuickProofFieldMappingReady ? "true" : "false"}" data-post-install-quick-proof-field-mapping-coverage="${postInstallQuickProofFieldMappingCoverage}">
                <span>Quick proof</span>
                <ol>
                  ${postInstallQuickProofSteps.map((step, index) => raw(html`
                    <li data-post-install-quick-proof-step data-post-install-quick-proof-step-key="${step.key || ""}" data-post-install-quick-proof-step-command="${step.command || ""}" data-post-install-quick-proof-step-expected="${step.expected || ""}" data-post-install-quick-proof-step-field="${step.evidenceFieldKey || ""}">
                      <strong>${index + 1}. ${step.label || step.key}</strong>
                      <code>${step.command || ""}</code>
                      <small>${step.expected || ""}</small>
                    </li>
                  `))}
                </ol>
              </div>
              <div class="home-post-install-quick-proof-map" data-post-install-quick-proof-field-map data-post-install-quick-proof-field-mapping-ready="${postInstallQuickProofFieldMappingReady ? "true" : "false"}" data-post-install-quick-proof-field-mapping-coverage="${postInstallQuickProofFieldMappingCoverage}" data-post-install-quick-proof-mapped-field-count="${postInstallQuickProofMappedFieldCount}" data-post-install-quick-proof-completed-mapped-field-count="${postInstallQuickProofCompletedMappedFieldCount}">
                <span>Mapped fields</span>
                <ol>
                  ${postInstallQuickProofFieldMappings.map((item, index) => raw(html`
                    <li data-post-install-quick-proof-field-map-item data-post-install-quick-proof-field-map-step="${item.stepKey || ""}" data-post-install-quick-proof-field-map-field="${item.fieldKey || ""}" data-post-install-quick-proof-field-map-status="${item.fieldStatus || ""}" data-post-install-quick-proof-field-map-completed="${item.fieldCompleted ? "true" : "false"}">
                      <strong>${index + 1}. ${item.stepKey || "step"} -> ${item.fieldLabel || item.fieldKey}</strong>
                      <small>${item.fieldStatus || "missing"} · completed=${item.fieldCompleted ? "true" : "false"}</small>
                      <p>${item.currentValue || ""}</p>
                    </li>
                  `))}
                </ol>
              </div>
              <ul class="home-post-install-intake-fields">
                ${postInstallEvidenceFields.map((field) => raw(html`
                  <li data-home-post-install-evidence-intake-field data-post-install-evidence-intake-field data-home-post-install-evidence-intake-field-key="${field.key || ""}" data-home-post-install-evidence-intake-field-status="${field.status || ""}" data-post-install-evidence-intake-field-label="${field.label || field.key || ""}">
                    <strong>${field.label || field.key}</strong>
                    <span>${field.status || (field.completed ? "complete" : "evidence_required")}</span>
                    <p>${field.currentValue || field.placeholder || ""}</p>
                  </li>
                `))}
              </ul>
              <div class="home-post-install-intake-sequence" data-home-post-install-evidence-sequence data-post-install-evidence-intake-sequence data-home-post-install-evidence-sequence-count="${postInstallVerificationSequence.length}" data-home-post-install-evidence-sequence-ready="${postInstallVerificationSequenceReady ? "true" : "false"}">
                <span>Verification sequence</span>
                <ol>
                  ${postInstallVerificationSequence.map((step, index) => raw(html`
                    <li data-home-post-install-evidence-sequence-step data-post-install-evidence-intake-sequence-step data-home-post-install-evidence-sequence-key="${step.key}" data-home-post-install-evidence-sequence-command="${step.command}" data-home-post-install-evidence-sequence-expected="${step.expected}">
                      <div>
                        <strong>${index + 1}. ${step.label}</strong>
                        <small>${step.key}</small>
                      </div>
                      <code>${step.command}</code>
                      <p>${step.expected}</p>
                    </li>
                  `))}
                </ol>
              </div>
              <div class="home-post-install-intake-commands">
                ${postInstallEvidenceCommands.map((command) => raw(html`<code data-home-post-install-evidence-intake-command data-post-install-evidence-intake-command>${command}</code>`))}
              </div>
              <div class="home-post-install-intake-signals">
                ${postInstallEvidenceSignals.map((signal) => raw(html`<span data-home-post-install-evidence-intake-signal data-post-install-evidence-intake-signal>${signal}</span>`))}
              </div>
              <p class="home-post-install-intake-stop" data-home-post-install-evidence-intake-stop>${postInstallEvidenceStopCondition}</p>
              <pre data-post-install-evidence-intake-text hidden>${postInstallEvidenceText}</pre>
              <div class="home-post-install-intake-actions">
                <button type="button" class="secondary-btn" data-action="copy-post-install-evidence-intake" data-post-install-evidence-intake-copy>intake template 복사</button>
                <span data-post-install-evidence-intake-copy-status aria-live="polite"></span>
              </div>
            </div>
          `) : ""}
          ${externalClaimGuardText ? raw(html`
            <div class="home-external-claim-guard" data-home-external-claim-guard data-output-quality-audit-external-claim-guard data-home-external-claim-guard-ready="${externalClaimGuardReady ? "true" : "false"}" data-home-external-claim-guard-status="${externalClaimGuard.status || "not_available"}" data-home-external-claim-guard-blocked-count="${externalClaimGuardBlockedCount}" data-home-external-claim-guard-requirement-count="${externalClaimGuardRequirementCount}" data-home-external-claim-guard-command-count="${externalClaimGuardCommands.length}" data-home-external-claim-guard-next-proof-key="${externalClaimGuardPrimaryRequirement.key || "workflow_installation"}" data-home-external-claim-guard-next-proof-command="${externalClaimGuardPrimaryCommand}" data-output-quality-audit-external-claim-guard-ready="${externalClaimGuardReady ? "true" : "false"}" data-output-quality-audit-external-claim-guard-status="${externalClaimGuard.status || "not_available"}" data-output-quality-audit-external-claim-guard-blocked-count="${externalClaimGuardBlockedCount}" data-output-quality-audit-external-claim-guard-requirement-count="${externalClaimGuardRequirementCount}" data-output-quality-audit-external-claim-guard-command-count="${externalClaimGuardCommands.length}">
              <div class="home-external-claim-guard-summary">
                <span>external claim guard</span>
                <strong>${externalClaimGuardReady ? "외부 완료 주장 가능" : "외부 완료 주장 차단"}</strong>
                <p>${externalClaimGuard.status || "not_available"} · blocked ${externalClaimGuardBlockedCount}/${externalClaimGuardRequirementCount}</p>
              </div>
              <div class="home-external-claim-guard-next-proof" data-home-external-claim-guard-next-proof data-home-external-claim-guard-next-proof-ready="${externalClaimGuardReady ? "true" : "false"}" data-home-external-claim-guard-next-proof-key="${externalClaimGuardPrimaryRequirement.key || "workflow_installation"}" data-home-external-claim-guard-next-proof-status="${externalClaimGuardPrimaryRequirement.status || "blocked"}">
                <span>next proof</span>
                <strong>${externalClaimGuardPrimaryRequirement.label || "Workflow installation"}</strong>
                <p>${externalClaimGuardPrimaryRequirement.status || "blocked"} · ${externalClaimGuardPrimarySignal}</p>
                <code>${externalClaimGuardPrimaryCommand}</code>
              </div>
              <ul class="home-external-claim-guard-requirements">
                ${externalClaimGuardRequirements.map((item) => raw(html`
                  <li data-home-external-claim-guard-item data-home-external-claim-guard-key="${item.key}" data-home-external-claim-guard-item-status="${item.status}" data-output-quality-audit-external-claim-guard-item data-output-quality-audit-external-claim-guard-key="${item.key}" data-output-quality-audit-external-claim-guard-item-status="${item.status}">
                    <strong>${item.label}</strong>
                    <span>${item.status}</span>
                  </li>
                `))}
              </ul>
              <div class="home-external-claim-guard-signals">
                ${externalClaimGuardSignals.slice(0, 6).map((signal) => raw(html`<span data-home-external-claim-guard-signal data-output-quality-audit-external-claim-guard-signal>${signal}</span>`))}
              </div>
              <div class="home-external-claim-guard-commands">
                ${externalClaimGuardCommands.map((command) => raw(html`<code data-home-external-claim-guard-command data-output-quality-audit-external-claim-guard-command>${command}</code>`))}
              </div>
              <p class="home-external-claim-guard-stop" data-home-external-claim-guard-stop data-output-quality-audit-external-claim-guard-stop>${externalClaimGuard.stopCondition || ""}</p>
              <pre data-output-quality-audit-external-claim-guard-text hidden>${homeExternalClaimGuardText}</pre>
              <div class="home-external-claim-guard-actions">
                <button type="button" class="secondary-btn" data-action="copy-output-quality-external-claim-guard" data-output-quality-audit-external-claim-guard-copy>external claim guard 복사</button>
                <span data-output-quality-audit-external-claim-guard-copy-status aria-live="polite"></span>
              </div>
            </div>
          `) : ""}
        </section>
      `;
    }

    function homeCommandTilePreviewContentHTML({ totalIssues }) {
      const topProjects = [...dashboard.projects].sort((a, b) => b.progress - a.progress).slice(0, 3);
      const portfolioBody = topProjects.length
        ? homeListPreviewHTML(topProjects, (p) => html`
            <li>
              <span class="home-dot" style="background:${raw(HEALTH_COLOR[p.health])}"></span>
              <strong>${p.name}</strong>
              <em>${p.progress}%</em>
            </li>`)
        : homeEmptyHTML("projects", "프로젝트가 없습니다", "첫 운영 프로젝트를 만들면 진행률과 상태가 홈에 나타납니다.", "project-add", "프로젝트 만들기");
    
      const counts = { todo: 0, "in-progress": 0, review: 0, done: 0 };
      dashboard.issues.forEach((i) => { counts[i.status] = (counts[i.status] || 0) + 1; });
      const kanbanBody = totalIssues
        ? html`
          <div class="home-stats">
            <div><b>${counts.todo}</b><small>To Do</small></div>
            <div><b>${counts["in-progress"]}</b><small>In Progress</small></div>
            <div><b>${counts.review}</b><small>Review</small></div>
            <div><b>${counts.done}</b><small>Done</small></div>
          </div>
        `
        : homeEmptyHTML("kanban", "이슈가 없습니다", "첫 이슈를 만들면 Kanban 단계별 작업량을 바로 볼 수 있습니다.", "issue-add", "이슈 만들기");
    
      const upcomingMs = dashboard.gantt.tasks.filter((t) => t.milestone).slice(0, 3);
      const ganttBody = upcomingMs.length
        ? homeListPreviewHTML(upcomingMs, (m) => html`
            <li>
              <span class="home-dot" style="background:var(--violet)"></span>
              <strong>${m.name}</strong>
              <em>${m.start}</em>
            </li>`)
        : homeEmptyHTML("gantt", "마일스톤이 없습니다", "일정이 있는 작업을 추가하면 홈에서 다음 마일스톤을 추적합니다.", "task-add", "작업 만들기");
    
      const overloaded = dashboard.team.filter((m) => m.load > 85);
      const teamBody = dashboard.team.length
        ? html`
          ${raw(homeListPreviewHTML(dashboard.team.slice(0, 4), (m) => html`
            <li>
              <span class="home-dot" style="background:${raw(m.load > 85 ? "var(--red)" : m.load > 65 ? "var(--amber)" : "var(--green)")}"></span>
              <strong>${m.name}</strong>
              <em>${m.load}%</em>
            </li>`))}
          <small class="home-sub">오버할당 ${overloaded.length}명</small>
        `
        : homeEmptyHTML("team", "팀 멤버가 없습니다", "담당자를 추가하면 부하와 배정 가능성을 홈에서 확인할 수 있습니다.", "member-add", "멤버 추가");
    
      const instancesBody = dashboard.dbInstances.length
        ? homeListPreviewHTML(dashboard.dbInstances, (d) => html`
            <li>
              <span class="home-dot" style="background:${raw(HEALTH_COLOR[d.health])}"></span>
              <strong>${d.name}</strong>
              <em>CPU ${d.cpu}%</em>
            </li>`)
        : homeEmptyHTML("db-instances", "DB 인스턴스가 없습니다", "DB 카탈로그 항목을 등록하면 상태와 CPU 메모를 홈에서 볼 수 있습니다.", "instance-add", "인스턴스 추가");
    
      const schemaTotalTables = dashboard.schemas.reduce((a, s) => a + s.databases.reduce((b, db) => b + db.tables.length, 0), 0);
      const schemaDbCount = dashboard.schemas.reduce((a, s) => a + s.databases.length, 0);
      const schemaBody = schemaTotalTables
        ? html`
          <div class="home-stats">
            <div><b>${dashboard.dbInstances.length}</b><small>인스턴스</small></div>
            <div><b>${schemaDbCount}</b><small>DB</small></div>
            <div><b>${schemaTotalTables}</b><small>테이블</small></div>
          </div>
        `
        : homeEmptyHTML("schema", "스키마가 없습니다", "DB 인스턴스를 기준으로 테이블 구조를 문서화하세요.", dashboard.dbInstances.length ? "table-add" : "instance-add", dashboard.dbInstances.length ? "테이블 추가" : "DB부터 추가");
    
      const topQueries = [...dashboard.queries].sort((a, b) => b.p95Ms - a.p95Ms).slice(0, 3);
      const queriesBody = topQueries.length
        ? homeListPreviewHTML(topQueries, (q) => html`
            <li>
              <span class="home-dot" style="background:var(--red)"></span>
              <strong>${q.id}</strong>
              <em>p95 ${q.p95Ms}ms</em>
            </li>`)
        : homeEmptyHTML("queries", "저장 쿼리가 없습니다", "자주 보는 SQL을 저장하면 느린 쿼리 신호가 홈에 나타납니다.", dashboard.dbInstances.length ? "query-add" : "instance-add", dashboard.dbInstances.length ? "쿼리 추가" : "DB부터 추가");
    
      const recentBackups = dashboard.dbInstances.length ? dashboard.backups.slice(-4).reverse() : [];
      const backupsBody = recentBackups.length
        ? homeListPreviewHTML(recentBackups, (b) => html`
            <li>
              <span class="home-dot" style="background:${raw(b.status === "ok" ? "var(--green)" : b.status === "warn" ? "var(--amber)" : "var(--red)")}"></span>
              <strong>${b.date}</strong>
              <em>${b.instance}</em>
            </li>`)
        : homeEmptyHTML("backups", "백업 기록이 없습니다", "변경 이력을 기록하면 백업과 마이그레이션 상태를 홈에서 함께 확인할 수 있습니다.", "migration-add", "마이그레이션 추가");
    
      return {
        portfolioBody,
        kanbanBody,
        ganttBody,
        teamBody,
        instancesBody,
        schemaTotalTables,
        schemaBody,
        queriesBody,
        backupsBody,
      };
    }
    

    function renderHome() {
      const view = refs.views.home;
      if (!view) return;
    
      const today = todayISO();
      const now = new Date();
      const hour = now.getHours();
      const greet = hour < 6 ? "편안한 새벽 되세요" : hour < 12 ? "좋은 아침입니다" : hour < 18 ? "좋은 오후입니다" : "좋은 저녁입니다";
      const name = (dashboard.settings && dashboard.settings.displayName) || "박주호";
    
      const todaysEvents = eventsOn(today);
      const openTodos = dashboard.todos.filter((t) => !t.done);
      const overdueTodos = openTodos.filter((t) => t.due && t.due < today);
      const todayTodos = openTodos.filter((t) => t.due === today);
      const weekEnd = addDaysISO(today, 7);
      // Use expandOccurrences so recurring events appear in the upcoming list.
      const upcoming = sortEvents(expandOccurrences(addDaysISO(today, 1), weekEnd)).slice(0, 6);
      const executionQueue = homeExecutionQueueModel({ today, weekEnd, openTodos, bucketFilter: state.homeExecutionBucketFilter });
      const weekDeadlines =
        dashboard.events.filter((e) => e.category === "deadline" && e.date >= today && e.date <= weekEnd).length +
        openTodos.filter((t) => t.due && t.due >= today && t.due <= weekEnd).length;
    
      const totalProjects = dashboard.projects.length;
      const onTrack = dashboard.projects.filter((p) => p.status === "on-track").length;
      const totalIssues = dashboard.issues.length;
      const unhealthy = dashboard.dbInstances.filter((d) => d.health !== "green").length;
      const slow = dashboard.queries.length;
      const pendingMig = dashboard.migrations.filter((m) => m.status === "pending").length;
      const adoptionCandidates = dashboard.projects.filter((project) => project.sourceKind === "adoption-candidate");
      const sourceBacked = adoptionCandidates.filter((project) => safeGithubUrl(project.url) && shortCommit(project.lastCommit));
      const benchmarkFocused = adoptionCandidates.filter((project) => projectBenchmarkContext(project).any);
      const publishItems = publishReadinessItems();
      const publishBlockers = publishItems.filter((item) => item.state === "blocked");
      const publishData = state.publishEvidence && state.publishEvidence.data ? state.publishEvidence.data : null;
      const launchExecution = state.launchExecutionPacket && state.launchExecutionPacket.data ? state.launchExecutionPacket.data : null;
      const outputAudit = state.outputQualityAudit && state.outputQualityAudit.data ? state.outputQualityAudit.data : null;
      const outputImmediateAction = outputAudit?.nextAction ||
        outputAudit?.publishState?.immediateNextAction ||
        publishData?.immediateNextAction ||
        publishData?.nextAction ||
        null;
      const launchExecutionCurrentAction = launchExecution?.currentAction || null;
      const safeToDispatch = launchExecution?.readyToDispatch === true && outputAudit?.dispatchState?.allDispatchReady === true;
      const externalClaimReady = launchExecution?.readyForExternalClaim === true && outputAudit?.readyForExternalClaim === true;
      const currentLaunchAction = externalClaimReady
        ? (outputImmediateAction || launchExecutionCurrentAction)
        : (launchExecutionCurrentAction || outputImmediateAction);
      const currentLaunchActionKey = currentLaunchAction?.stageKey || currentLaunchAction?.key || outputImmediateAction?.key || "system-review";
      const currentLaunchActionLabel = currentLaunchAction?.label || outputImmediateAction?.label || publishBlockers[0]?.label || "System Status 확인";
      const currentLaunchActionStatus = currentLaunchAction?.status || outputImmediateAction?.status || (publishBlockers.length ? "action_required" : "ready");
      const currentLaunchActionCommand = Array.isArray(currentLaunchAction?.commands) && currentLaunchAction.commands.length
        ? currentLaunchAction.commands[0]
        : currentLaunchAction?.command || outputImmediateAction?.command || publishBlockers[0]?.command || "node scripts/verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --markdown";
      const currentLaunchActionDetail = currentLaunchAction?.successCondition ||
        currentLaunchAction?.detail ||
        currentLaunchAction?.deferredDetail ||
        outputImmediateAction?.successCondition ||
        outputImmediateAction?.detail ||
        outputImmediateAction?.deferredDetail ||
        "System Status에서 현재 blocker와 다음 검증 명령을 확인합니다.";
      const declaredLaunchActionCommandCount = firstClampedCount([
        currentLaunchAction?.commandCount,
        outputImmediateAction?.commandCount,
        currentLaunchActionCommand ? 1 : 0,
      ]);
      const currentLaunchActionCommandCount = currentLaunchActionCommand
        ? Math.max(1, declaredLaunchActionCommandCount)
        : declaredLaunchActionCommandCount;
      const currentLaunchWithheldCount = firstClampedCount([
        currentLaunchAction?.withheldCommandCount,
        outputImmediateAction?.withheldCommandCount,
        outputAudit?.outputReadinessSnapshot?.publishEvidenceCommandGuard?.withheldDispatchCommands,
      ]);
      const launchStages = Array.isArray(launchExecution?.stages) ? launchExecution.stages : [];
      const launchTransition = launchExecution?.stageTransitionPreview && typeof launchExecution.stageTransitionPreview === "object" ? launchExecution.stageTransitionPreview : {};
      const launchInstallMatrix = launchExecution?.workflowInstallVerificationMatrix && typeof launchExecution.workflowInstallVerificationMatrix === "object" ? launchExecution.workflowInstallVerificationMatrix : {};
      const launchInstallMatrixRows = Array.isArray(launchInstallMatrix.matrixRows) ? launchInstallMatrix.matrixRows : [];
      const launchInstallMatrixSignals = Array.isArray(launchInstallMatrix.signalChecks) ? launchInstallMatrix.signalChecks : [];
      const launchInstallMatrixPathCount = firstClampedCount([launchInstallMatrix.installPathCount, launchInstallMatrixRows.length]);
      const launchInstallMatrixSignalCount = firstClampedCount([launchInstallMatrix.requiredSignalCount, launchInstallMatrixSignals.length]);
      const remoteWorkflowFileLedger = launchExecution?.remoteWorkflowFileAcceptanceLedger && typeof launchExecution.remoteWorkflowFileAcceptanceLedger === "object" ? launchExecution.remoteWorkflowFileAcceptanceLedger : {};
      const remoteWorkflowFileLedgerItems = Array.isArray(remoteWorkflowFileLedger.files) ? remoteWorkflowFileLedger.files : [];
      const remoteWorkflowFileLedgerFileCount = firstClampedCount([remoteWorkflowFileLedger.fileCount, remoteWorkflowFileLedgerItems.length]);
      const remoteWorkflowFileLedgerReadyCount = firstClampedCount([remoteWorkflowFileLedger.readyCount]);
      const remoteWorkflowFileLedgerMissingCount = firstClampedCount([remoteWorkflowFileLedger.missingCount]);
      const remoteWorkflowFileLedgerMismatchCount = firstClampedCount([remoteWorkflowFileLedger.mismatchCount]);
      const launchProofLedger = launchExecution?.launchProofAcceptanceLedger && typeof launchExecution.launchProofAcceptanceLedger === "object" ? launchExecution.launchProofAcceptanceLedger : {};
      const launchProofLedgerItems = Array.isArray(launchProofLedger.requiredProofs) ? launchProofLedger.requiredProofs : [];
      const remoteWorkflowFileLedgerReady = !!(
        remoteWorkflowFileLedger.ready ||
        remoteWorkflowFileLedger.remoteWorkflowFilesReady ||
        remoteWorkflowFileLedger.status === "remote_files_ready" ||
        (
          remoteWorkflowFileLedgerFileCount > 0 &&
          remoteWorkflowFileLedgerReadyCount === remoteWorkflowFileLedgerFileCount &&
          remoteWorkflowFileLedgerMissingCount === 0 &&
          remoteWorkflowFileLedgerMismatchCount === 0
        )
      );
      const launchProofLedgerRequiredCount = firstClampedCount([launchProofLedger.requiredProofCount, launchProofLedgerItems.length]);
      const launchProofLedgerReadyCount = firstClampedCount([launchProofLedger.readyProofCount]);
      const launchProofLedgerPendingCount = firstClampedCount(
        [launchProofLedger.pendingProofCount],
        Math.max(0, launchProofLedgerRequiredCount - launchProofLedgerReadyCount),
      );
      const launchProofLedgerReady = !!(
        launchProofLedger.ready ||
        launchProofLedger.launchProofReady ||
        launchProofLedger.publicLaunchProofReady ||
        (
          launchProofLedgerRequiredCount > 0 &&
          launchProofLedgerReadyCount === launchProofLedgerRequiredCount &&
          launchProofLedgerPendingCount === 0
        )
      );
      const launchBlockerResolution = launchExecution?.blockerResolutionChecklist && typeof launchExecution.blockerResolutionChecklist === "object"
        ? launchExecution.blockerResolutionChecklist
        : (outputAudit?.outputReadinessSnapshot?.blockerResolutionChecklist && typeof outputAudit.outputReadinessSnapshot.blockerResolutionChecklist === "object" ? outputAudit.outputReadinessSnapshot.blockerResolutionChecklist : {});
      const launchBlockerItems = Array.isArray(launchBlockerResolution.items) ? launchBlockerResolution.items : [];
      const launchBlockerActionRequiredItem = firstStatusItem(launchBlockerItems, "action_required");
      const launchBlockerActiveKey = launchBlockerResolution.activeItemKey ||
        launchBlockerActionRequiredItem?.key ||
        (launchProofLedgerReady ? "launch_proof_capture" : "");
      const launchBlockerActiveItem = recordByKey(launchBlockerItems, launchBlockerActiveKey) || launchBlockerActionRequiredItem || null;
      const launchBlockerProofCommands = launchBlockerItems.map((item) => item.proofCommand).filter(Boolean);
      const launchBlockerItemCount = firstClampedCount([launchBlockerResolution.itemCount, launchBlockerItems.length]);
      const launchBlockerPassCount = firstClampedCount([launchBlockerResolution.passCount]);
      const launchBlockerActionRequiredCount = firstClampedCount([launchBlockerResolution.actionRequiredCount]);
      const launchBlockerDeferredCount = firstClampedCount([launchBlockerResolution.deferredCount]);
      const launchBlockerProofCommandCount = firstClampedCount([launchBlockerResolution.proofCommandCount, launchBlockerProofCommands.length]);
      const launchInstallPathOptions = Array.isArray(currentLaunchAction?.installPaths)
        ? currentLaunchAction.installPaths
        : (Array.isArray(launchExecution?.installPaths) ? launchExecution.installPaths : []);
      const launchBlockerFallbackPath = recordByKey(launchInstallPathOptions, "github_ui") || {};
      const launchBlockerFallbackCommands = Array.isArray(launchBlockerFallbackPath.commands) ? launchBlockerFallbackPath.commands : [];
      const workflowAuthPreflight = launchExecution?.authPreflight && typeof launchExecution.authPreflight === "object"
        ? launchExecution.authPreflight
        : (outputAudit?.outputReadinessSnapshot?.workflowAuthPreflight && typeof outputAudit.outputReadinessSnapshot.workflowAuthPreflight === "object" ? outputAudit.outputReadinessSnapshot.workflowAuthPreflight : {});
      const workflowScopeInstallBlocked = !!workflowAuthPreflight.workflowScopeInstallBlocked;
      const workflowInstallShortcutPaths = launchInstallPathOptions.filter((path) => Array.isArray(path.commands) && path.commands.length);
      const workflowInstallShortcutCommandCount = workflowInstallShortcutPaths.reduce((total, path) => total + path.commands.length, 0);
      const workflowInstallShortcutTargetCount = firstClampedCount([
        remoteWorkflowFileLedger.fileCount,
        remoteWorkflowFileLedgerItems.length > 0 ? remoteWorkflowFileLedgerItems.length : undefined,
      ], 2);
      const workflowInstallShortcutCliPath = recordByKey(workflowInstallShortcutPaths, "cli_workflow_scope") || workflowInstallShortcutPaths[0] || {};
      const workflowInstallShortcutUiPath = recordByKey(workflowInstallShortcutPaths, "github_ui") || {};
      const workflowInstallShortcutPrimaryPath = workflowScopeInstallBlocked && workflowInstallShortcutUiPath.key ? workflowInstallShortcutUiPath : workflowInstallShortcutCliPath;
      const workflowInstallShortcutPrimaryCommands = Array.isArray(workflowInstallShortcutPrimaryPath.commands) ? workflowInstallShortcutPrimaryPath.commands : [];
      const workflowInstallShortcutPrimaryCommand = workflowInstallShortcutPrimaryCommands[0] || currentLaunchActionCommand;
      const workflowInstallShortcutVerifyCommand = launchExecution?.postAuthCheckpoint?.verifyCommand ||
        "node scripts/verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown";
      const workflowInstallShortcutDefaultBranchGuard = "workflow_dispatch requires the workflow file on the repository default branch before manual dispatch.";
      const workflowInstallShortcutScopeGuard = "Writing .github/workflows through the repository contents API requires workflow scope; use GitHub UI when workflowScopeInstallBlocked=true.";
      const workflowInstallShortcutReady = workflowInstallShortcutPaths.length >= 2 && workflowInstallShortcutCommandCount >= 10;
      const launchBlockerDispatchGuard = launchBlockerResolution.guard || launchBlockerResolution.dispatchGuard || "Do not run gh workflow run until every action_required item has passed and verify-launch-handoff reports safeToDispatch=true.";
      const launchPostInstallIntakeForGap = launchExecution?.postInstallEvidenceIntake && typeof launchExecution.postInstallEvidenceIntake === "object"
        ? launchExecution.postInstallEvidenceIntake
        : (outputAudit?.outputReadinessSnapshot?.postInstallEvidenceIntake && typeof outputAudit.outputReadinessSnapshot.postInstallEvidenceIntake === "object" ? outputAudit.outputReadinessSnapshot.postInstallEvidenceIntake : {});
      const launchPostInstallFieldCountForGap = firstClampedCount([launchPostInstallIntakeForGap.fieldCount, launchPostInstallIntakeForGap.fieldsCount, Array.isArray(launchPostInstallIntakeForGap.fields) ? launchPostInstallIntakeForGap.fields.length : 0]);
      const launchPostInstallCompletedForGap = firstClampedCount([launchPostInstallIntakeForGap.completedFieldCount]);
      const launchPostInstallPendingForGap = firstClampedCount([launchPostInstallIntakeForGap.pendingFieldCount], Math.max(0, launchPostInstallFieldCountForGap - launchPostInstallCompletedForGap));
      const launchEvidenceGapItems = [
        {
          key: "remote_workflow_files",
          label: "Remote workflow files",
          status: remoteWorkflowFileLedger.status || "remote_file_install_required",
          ready: remoteWorkflowFileLedgerReady,
          summary: `${remoteWorkflowFileLedgerReadyCount}/${remoteWorkflowFileLedgerFileCount} files ready; missing=${remoteWorkflowFileLedgerMissingCount}; mismatch=${remoteWorkflowFileLedgerMismatchCount}`,
          command: remoteWorkflowFileLedger.verifyCommand || "node scripts/check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write",
        },
        {
          key: "launch_proof",
          label: "Launch proof",
          status: launchProofLedger.status || "proof_blocked_until_dispatch",
          ready: launchProofLedgerReady,
          summary: `${launchProofLedgerReadyCount}/${launchProofLedgerRequiredCount} proofs ready; pending=${launchProofLedgerPendingCount}; gate=${launchProofLedger.currentGate || "capture_launch_proof"}`,
          command: launchProofLedger.captureWriteCommand || "node scripts/capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --write",
        },
        {
          key: "post_install_intake",
          label: "Post-install intake",
          status: launchPostInstallIntakeForGap.status || "collect_post_install_proof",
          ready: !!launchPostInstallIntakeForGap.proofComplete,
          summary: `${launchPostInstallCompletedForGap}/${launchPostInstallFieldCountForGap} proof fields complete; pending=${launchPostInstallPendingForGap}; proofComplete=${launchPostInstallIntakeForGap.proofComplete ? "true" : "false"}`,
          command: Array.isArray(launchPostInstallIntakeForGap.commands) && launchPostInstallIntakeForGap.commands.length
            ? launchPostInstallIntakeForGap.commands[0]
            : "node scripts/check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write",
        },
      ];
      const launchBlockerResolverReady = !!(launchBlockerActiveItem && launchBlockerItems.length && launchBlockerProofCommands.length);
      const workflowInstallShortcutText = workflowInstallShortcutReady ? [
        "JooPark Workflow Install Shortcut",
        `Status: ${workflowScopeInstallBlocked ? "workflow_scope_blocked_use_ui_or_refresh" : "workflow_scope_available_use_cli"}`,
        `Repo: ${launchBlockerResolution.repo || "biojuho/BIOJUHO-Projects"}`,
        `Target workflow files: ${workflowInstallShortcutTargetCount}`,
        `Install paths: ${workflowInstallShortcutPaths.length}`,
        `Install command count: ${workflowInstallShortcutCommandCount}`,
        `Primary path: ${workflowInstallShortcutPrimaryPath.label || workflowInstallShortcutPrimaryPath.key || "not_available"}`,
        `Primary command: ${workflowInstallShortcutPrimaryCommand}`,
        `Verify command: ${workflowInstallShortcutVerifyCommand}`,
        "",
        "Official guard:",
        `- ${workflowInstallShortcutDefaultBranchGuard}`,
        `- ${workflowInstallShortcutScopeGuard}`,
        "",
        "Install paths:",
        ...workflowInstallShortcutPaths.flatMap((path) => [
          `- ${path.key}: ${path.label}; commands=${Array.isArray(path.commands) ? path.commands.length : 0}; success=${path.success || "not_available"}; guard=${path.guard || "not_available"}`,
          ...(Array.isArray(path.commands) ? path.commands.map((command, index) => `  ${index + 1}. ${command}`) : []),
        ]),
        "",
        `Dispatch guard: ${launchBlockerDispatchGuard}`,
      ].join("\n") : "";
      const launchBlockerResolverText = launchBlockerResolverReady ? [
        "JooPark Launch Blocker Resolver",
        `Source: ${launchBlockerResolution.source || "missing"}`,
        `Repo: ${launchBlockerResolution.repo || "biojuho/BIOJUHO-Projects"}`,
        `Status: ${launchBlockerResolution.status || "action_required"}`,
        `currentStageKey=${launchBlockerResolution.currentStageKey || currentLaunchActionKey}`,
        `activeItemKey=${launchBlockerActiveKey}`,
        `activeStatus=${launchBlockerActiveItem.status || "action_required"}`,
        `blockedSignal=${launchBlockerActiveItem.blockedSignal || "not_available"}`,
        "",
        "Active unblock action:",
        `- ${launchBlockerActiveItem.action || "not_available"}`,
        `Primary proof command: ${launchBlockerActiveItem.proofCommand || "not_available"}`,
        `Expected value: ${launchBlockerActiveItem.expectedValue || "not_available"}`,
        `Stop condition: ${launchBlockerActiveItem.stopCondition || "not_available"}`,
        "",
        "Checklist state:",
        `- items=${launchBlockerItemCount}; pass=${launchBlockerPassCount}; actionRequired=${launchBlockerActionRequiredCount}; deferred=${launchBlockerDeferredCount}; proofCommands=${launchBlockerProofCommandCount}`,
        ...launchBlockerItems.map((item) => `- ${item.key}: ${item.status}; blockedSignal=${item.blockedSignal || "not_available"}; proofCommand=${item.proofCommand || "not_available"}; expected=${item.expectedValue || "not_available"}; stopCondition=${item.stopCondition || "not_available"}`),
        "",
    	    "Evidence gap:",
    	    ...launchEvidenceGapItems.map((item) => `- ${item.key}: ${item.status}; ready=${item.ready ? "true" : "false"}; ${item.summary}; command=${item.command}`),
    	    "",
        ...(workflowInstallShortcutText ? [
          "Workflow install shortcut:",
          ...workflowInstallShortcutText.split("\n"),
          "",
        ] : []),
    	    "Required proof commands:",
        ...launchBlockerProofCommands.map((command, index) => `${index + 1}. ${command}`),
        "",
        "GitHub UI fallback:",
        `- Use when: ${launchBlockerFallbackPath.when || "Use when workflowScopeInstallBlocked=true remains after recheck or the operator chooses browser-based default-branch file creation."}`,
        ...launchBlockerFallbackCommands.map((command, index) => `${index + 1}. ${command}`),
        `- Success: ${launchBlockerFallbackPath.success || "remoteWorkflowFilesReady=true and remoteWorkflowVisibilityReady=true are confirmed."}`,
        `- Guard: ${launchBlockerFallbackPath.guard || "Keep dispatch withheld until every post-install evidence field, remote workflow parity, Actions visibility, dispatch readiness, and verify-launch-handoff safeToDispatch=true proof are complete."}`,
        "",
        `Dispatch guard: ${launchBlockerDispatchGuard}`,
      ].join("\n") : "";
      const launchPostAuthCheckpoint = launchExecution?.postAuthCheckpoint && typeof launchExecution.postAuthCheckpoint === "object"
        ? launchExecution.postAuthCheckpoint
        : (outputAudit?.outputReadinessSnapshot?.launchPostAuthCheckpoint && typeof outputAudit.outputReadinessSnapshot.launchPostAuthCheckpoint === "object" ? outputAudit.outputReadinessSnapshot.launchPostAuthCheckpoint : {});
      const launchActionChecklistRecheckSteps = Array.isArray(launchPostAuthCheckpoint.recheckSequence) ? launchPostAuthCheckpoint.recheckSequence : [];
      const launchActionChecklistSourceArtifacts = Array.isArray(launchPostAuthCheckpoint.sourceArtifacts) ? launchPostAuthCheckpoint.sourceArtifacts : [];
      const launchActionChecklistDeferredCommand = outputAudit?.nextAction?.deferredCommand ||
        outputAudit?.publishState?.deferredNextAction?.command ||
        publishData?.deferredNextAction?.command ||
        "node scripts/capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --markdown";
      const launchActionChecklistStatus = launchPostAuthCheckpoint.status || currentLaunchActionStatus || "action_required";
      const launchActionChecklistActiveKey = launchBlockerActiveKey || currentLaunchActionKey || "install_workflows";
      const launchActionChecklistImmediateCommand = currentLaunchActionCommand || launchPostAuthCheckpoint.triggerCommand || "gh auth refresh -h github.com -s workflow";
      const launchActionChecklistDispatchApproval = launchPostAuthCheckpoint.dispatchApproval === true;
      const launchActionChecklistVerificationOnly = launchPostAuthCheckpoint.verificationOnly === true;
      const launchActionChecklistGuard = launchPostAuthCheckpoint.guard || outputAudit?.nextAction?.guard || launchBlockerDispatchGuard;
      const launchActionChecklistReady = launchActionChecklistRecheckSteps.length >= 5 &&
        launchActionChecklistSourceArtifacts.length >= 4 &&
        launchActionChecklistVerificationOnly &&
        !launchActionChecklistDispatchApproval &&
        !!launchActionChecklistGuard;
      const launchActionChecklistText = launchActionChecklistReady ? [
        "JooPark Launch Action Checklist",
        `Status: ${launchActionChecklistStatus}`,
        `Active blocker: ${launchActionChecklistActiveKey}`,
        `Immediate command: ${launchActionChecklistImmediateCommand}`,
        `Recheck sequence: ${launchActionChecklistRecheckSteps.length}`,
        `Source artifacts: ${launchActionChecklistSourceArtifacts.length}`,
        `Withheld dispatch commands: ${currentLaunchWithheldCount}`,
        `dispatchApproval=${launchActionChecklistDispatchApproval ? "true" : "false"}`,
        `verificationOnly=${launchActionChecklistVerificationOnly ? "true" : "false"}`,
        "",
        "Recheck sequence:",
        ...launchActionChecklistRecheckSteps.map((step, index) => `${index + 1}. ${step.key || "step"}: ${step.label || "Recheck step"}; command=${step.command || "not_available"}; expected=${step.expected || "not_available"}; source=${step.sourceArtifact || "not_available"}; stop=${step.stopCondition || "not_available"}`),
        "",
        "Source artifacts:",
        ...launchActionChecklistSourceArtifacts.map((artifact) => `- ${artifact}`),
        "",
        "Deferred proof command:",
        `- ${launchActionChecklistDeferredCommand}`,
        "",
        `Guard: ${launchActionChecklistGuard}`,
      ].join("\n") : "";
      const postInstallEvidenceIntake = launchExecution?.postInstallEvidenceIntake && typeof launchExecution.postInstallEvidenceIntake === "object"
        ? launchExecution.postInstallEvidenceIntake
        : (outputAudit?.outputReadinessSnapshot?.postInstallEvidenceIntake && typeof outputAudit.outputReadinessSnapshot.postInstallEvidenceIntake === "object" ? outputAudit.outputReadinessSnapshot.postInstallEvidenceIntake : {});
      const postInstallEvidenceFields = Array.isArray(postInstallEvidenceIntake.fields)
        ? postInstallEvidenceIntake.fields
        : (Array.isArray(postInstallEvidenceIntake.fieldItems) ? postInstallEvidenceIntake.fieldItems : []);
      const postInstallEvidenceCommands = Array.isArray(postInstallEvidenceIntake.commands) ? postInstallEvidenceIntake.commands : [];
      const postInstallEvidenceSignals = Array.isArray(postInstallEvidenceIntake.expectedSignals) ? postInstallEvidenceIntake.expectedSignals : [];
      const postInstallEvidenceFieldCount = firstClampedCount([postInstallEvidenceIntake.fieldCount, postInstallEvidenceIntake.fieldsCount, typeof postInstallEvidenceIntake.fields === "number" ? postInstallEvidenceIntake.fields : postInstallEvidenceFields.length]);
      const postInstallEvidenceCompletedCount = firstClampedCount([postInstallEvidenceIntake.completedFieldCount]);
      const postInstallEvidencePendingCount = firstClampedCount([postInstallEvidenceIntake.pendingFieldCount], Math.max(0, postInstallEvidenceFieldCount - postInstallEvidenceCompletedCount));
      const postInstallEvidenceProofComplete = !!postInstallEvidenceIntake.proofComplete;
      const postInstallEvidenceReady = !!postInstallEvidenceIntake.ready || (postInstallEvidenceFields.length >= 6 && postInstallEvidenceCommands.length >= 4 && postInstallEvidenceSignals.length >= 8);
      const postInstallEvidenceStatus = postInstallEvidenceIntake.status || (postInstallEvidenceProofComplete ? "proof_complete" : "collect_post_install_proof");
      const postInstallEvidenceStopCondition = postInstallEvidenceIntake.stopCondition || "Stop condition: do not run gh workflow run, archive proof, or claim launch until all six post-install evidence fields are filled and verify-launch-handoff reports safeToDispatch=true.";
      const findPostInstallEvidenceCommand = (...needles) => firstStringIncluding(postInstallEvidenceCommands, ...needles);
      const findPostInstallEvidenceSignal = (...needles) => firstStringIncluding(postInstallEvidenceSignals, ...needles);
      const packetPostInstallVerificationSequence = Array.isArray(postInstallEvidenceIntake.verificationSequence)
        ? postInstallEvidenceIntake.verificationSequence
        : [];
      const fallbackPostInstallVerificationSequence = [
        {
          key: "remote_file_parity",
          label: "Remote workflow file check",
          command: findPostInstallEvidenceCommand("check-remote-workflow-files") || "node scripts/check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write",
          expected: findPostInstallEvidenceSignal("remoteWorkflowFilesReady=true") || "remoteWorkflowFilesReady=true",
          guard: "Confirm both default-branch workflow files exist and match local templates before checking Actions visibility.",
        },
        {
          key: "actions_visibility",
          label: "Actions visibility check",
          command: findPostInstallEvidenceCommand("gh workflow list") || "gh workflow list --repo biojuho/BIOJUHO-Projects --all --json name,path,state,id",
          expected: findPostInstallEvidenceSignal("remoteWorkflowVisibilityReady=true") || "remoteWorkflowVisibilityReady=true",
          guard: "Confirm GitHub Actions lists both workflow files before planning dispatch.",
        },
        {
          key: "dispatch_readiness",
          label: "Dispatch readiness plan",
          command: findPostInstallEvidenceCommand("plan-publish-dispatch") || "node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects",
          expected: findPostInstallEvidenceSignal("allDispatchReady=true") || "allDispatchReady=true",
          guard: "Confirm pages and drift dispatch readiness are both true before final handoff verification.",
        },
        {
          key: "handoff_verifier",
          label: "Launch handoff verifier",
          command: findPostInstallEvidenceCommand("verify-launch-handoff") || "node scripts/verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown",
          expected: findPostInstallEvidenceSignal("safeToDispatch=true before gh workflow run") || "safeToDispatch=true before gh workflow run",
          guard: postInstallEvidenceStopCondition,
        },
      ];
      const postInstallVerificationSequence = packetPostInstallVerificationSequence.length
        ? packetPostInstallVerificationSequence
        : fallbackPostInstallVerificationSequence;
      const postInstallVerificationSequenceReady = postInstallEvidenceReady &&
        (postInstallEvidenceIntake.verificationSequenceReady === true || postInstallVerificationSequence.length === 4) &&
        postInstallVerificationSequence.every((step) => step.command && step.expected);
      const postInstallVerificationFinalStep = postInstallVerificationSequence[postInstallVerificationSequence.length - 1] || {};
      const postInstallVerificationFinalCommand = postInstallEvidenceIntake.finalVerificationCommand || postInstallVerificationFinalStep.command || "";
      const packetPostInstallQuickProofSteps = Array.isArray(postInstallEvidenceIntake.quickProofSteps)
        ? postInstallEvidenceIntake.quickProofSteps
        : [];
      const postInstallQuickProofSteps = packetPostInstallQuickProofSteps.length
        ? packetPostInstallQuickProofSteps
        : postInstallVerificationSequence.map((step) => ({
            key: step.key,
            label: step.label,
            command: step.command,
            expected: step.expected,
            evidenceFieldKey: step.evidenceFieldKey || "",
            status: postInstallEvidenceProofComplete ? "proof_ready" : "evidence_required",
          }));
      const postInstallQuickProofStepCount = firstClampedCount([postInstallEvidenceIntake.quickProofStepCount, postInstallQuickProofSteps.length]);
      const postInstallQuickProofCoverage = firstClampedCount([
        postInstallEvidenceIntake.quickProofCoverage,
      ], postInstallQuickProofStepCount === 4 && postInstallQuickProofSteps.every((step) => step.command && step.expected) ? 1 : 0);
      const packetPostInstallQuickProofFieldMappings = Array.isArray(postInstallEvidenceIntake.quickProofFieldMappings)
        ? postInstallEvidenceIntake.quickProofFieldMappings
        : [];
      const postInstallFieldByKey = new Map(postInstallEvidenceFields.map((field) => [field.key, field]));
      const postInstallQuickProofFieldMappings = packetPostInstallQuickProofFieldMappings.length
        ? packetPostInstallQuickProofFieldMappings
        : postInstallQuickProofSteps.map((step) => {
            const mappedField = postInstallFieldByKey.get(step.evidenceFieldKey) || {};
            return {
              stepKey: step.key || "",
              stepLabel: step.label || "",
              fieldKey: step.evidenceFieldKey || "",
              fieldLabel: mappedField.label || "",
              fieldStatus: mappedField.status || "missing",
              fieldCompleted: !!mappedField.completed,
              currentValue: mappedField.currentValue || "not available",
              expectedValue: mappedField.expectedValue || step.expected || "not available",
              proofCommand: mappedField.proofCommand || step.command || "not available",
              stopCondition: mappedField.stopCondition || postInstallEvidenceStopCondition,
            };
          });
      const postInstallQuickProofMappedFieldCount = firstClampedCount([postInstallEvidenceIntake.quickProofMappedFieldCount, postInstallQuickProofFieldMappings.length]);
      const postInstallQuickProofCompletedMappedFieldCount = firstClampedCount([
        postInstallEvidenceIntake.quickProofCompletedMappedFieldCount,
        postInstallQuickProofFieldMappings.filter((item) => item.fieldCompleted).length,
      ]);
      const postInstallQuickProofFieldMappingCoverage = firstClampedCount([
        postInstallEvidenceIntake.quickProofFieldMappingCoverage,
      ], postInstallQuickProofMappedFieldCount === 4 && postInstallQuickProofFieldMappings.every((item) => item.stepKey && item.fieldKey && item.fieldLabel && item.proofCommand && item.expectedValue) ? 1 : 0);
      const postInstallQuickProofFieldMappingReady = postInstallEvidenceIntake.quickProofFieldMappingReady === true || postInstallQuickProofFieldMappingCoverage === 1;
      const postInstallQuickProofReady = postInstallEvidenceIntake.quickProofReady === true || postInstallQuickProofCoverage === 1;
      const postInstallQuickProofReceipt = postInstallEvidenceIntake.quickProofReceipt || [
        "JooPark Post-Install Quick Proof Receipt",
        `Status: ${postInstallEvidenceStatus}`,
        `Proof complete: ${postInstallEvidenceProofComplete}`,
        `Fields complete: ${postInstallEvidenceCompletedCount}/${postInstallEvidenceFieldCount}`,
        `Quick proof steps: ${postInstallQuickProofStepCount}`,
        "",
        "4-step proof checklist:",
        ...postInstallQuickProofSteps.map((step, index) => `${index + 1}. ${step.key}: run ${step.command}; expect ${step.expected}; paste into ${step.evidenceFieldKey || "matching evidence field"}`),
        "",
        "Mapped proof fields:",
        ...postInstallQuickProofFieldMappings.map((item, index) => `${index + 1}. ${item.stepKey} -> ${item.fieldKey}: ${item.fieldStatus}; completed=${item.fieldCompleted}; current=${item.currentValue}; expected=${item.expectedValue}`),
        "",
        postInstallEvidenceStopCondition,
      ].join("\n");
      const postInstallEvidenceText = postInstallEvidenceReady ? [
        "JooPark Workflow Post-Install Evidence Intake",
        `Status: ${postInstallEvidenceStatus}`,
        "Scope: Home launch handoff after GitHub UI or CLI workflow installation",
        `Proof complete: ${postInstallEvidenceProofComplete}`,
        `Fields complete: ${postInstallEvidenceCompletedCount}/${postInstallEvidenceFieldCount}`,
        `Pending fields: ${postInstallEvidencePendingCount}`,
        `Quick proof: ready=${postInstallQuickProofReady}; steps=${postInstallQuickProofStepCount}; coverage=${postInstallQuickProofCoverage}`,
        `Quick proof field mapping: ready=${postInstallQuickProofFieldMappingReady}; mapped=${postInstallQuickProofMappedFieldCount}; completed=${postInstallQuickProofCompletedMappedFieldCount}/${postInstallQuickProofMappedFieldCount}; coverage=${postInstallQuickProofFieldMappingCoverage}`,
        "",
        postInstallQuickProofReceipt,
        "",
        "Evidence fields to fill:",
        ...postInstallEvidenceFields.map((field) => `- ${field.label || field.key}: ${field.placeholder || field.currentValue || "evidence required"}; expected=${field.expectedValue || "not available"}; proofCommand=${field.proofCommand || "not available"}; stopCondition=${field.stopCondition || postInstallEvidenceStopCondition}`),
        "",
        "Verification commands:",
        ...postInstallEvidenceCommands.map((command, index) => `${index + 1}. ${command}`),
        "",
        "Verification sequence:",
        ...postInstallVerificationSequence.map((step, index) => `${index + 1}. ${step.key}: ${step.label}; command=${step.command}; expected=${step.expected}; guard=${step.guard}`),
        "",
        "Expected signals:",
        ...postInstallEvidenceSignals.map((signal) => `- ${signal}`),
        "",
        postInstallEvidenceStopCondition,
      ].join("\n") : "";
      const externalClaimGuard = outputAudit?.externalClaimGuard && typeof outputAudit.externalClaimGuard === "object" ? outputAudit.externalClaimGuard : {};
      const externalClaimGuardRequirements = Array.isArray(externalClaimGuard.requirements) ? externalClaimGuard.requirements : [];
      const externalClaimGuardSignals = Array.isArray(externalClaimGuard.requiredSignals) ? externalClaimGuard.requiredSignals : [];
      const externalClaimGuardCommands = Array.isArray(externalClaimGuard.proofCommands) ? externalClaimGuard.proofCommands : [];
      const externalClaimGuardText = externalClaimGuard.text || "";
      const externalClaimGuardReady = !!externalClaimGuard.ready;
      const externalClaimGuardRequirementCount = firstClampedCount([externalClaimGuard.requirementCount, externalClaimGuardRequirements.length]);
      const externalClaimGuardBlockedCount = firstClampedCount([externalClaimGuard.blockedCount]);
      const externalClaimGuardPrimaryRequirement = firstNonPassingStatusItem(externalClaimGuardRequirements) || externalClaimGuardRequirements[0] || {};
      const externalClaimGuardPrimarySignal = firstStringIncluding(externalClaimGuardSignals, "remoteWorkflowFilesReady=false") ||
        firstStringIncluding(externalClaimGuardSignals, "readyForExternalClaim=false") ||
        externalClaimGuardSignals[0] ||
        "readyForExternalClaim=false";
      const externalClaimGuardPrimaryCommand = firstStringIncluding(externalClaimGuardCommands, "verify-launch-handoff.mjs") ||
        externalClaimGuardCommands[0] ||
        "node scripts/verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown";
      const externalClaimGuardNextProofText = externalClaimGuardText ? [
        "Next claim proof shortcut:",
        `- requirement=${externalClaimGuardPrimaryRequirement.key || "workflow_installation"}`,
        `- label=${externalClaimGuardPrimaryRequirement.label || "Workflow installation"}`,
        `- status=${externalClaimGuardPrimaryRequirement.status || "blocked"}`,
        `- signal=${externalClaimGuardPrimarySignal}`,
        `- command=${externalClaimGuardPrimaryCommand}`,
        `- stopCondition=${externalClaimGuard.stopCondition || "Stop condition: do not claim readyForExternalClaim until Workflow installation, Public launch proof, and External completion claim are all pass."}`,
      ].join("\n") : "";
      const homeExternalClaimGuardText = externalClaimGuardText ? `${externalClaimGuardText}\n\n${externalClaimGuardNextProofText}` : "";
      const currentLaunchStage = launchTransition.currentStageKey || currentLaunchAction?.stageKey || currentLaunchActionKey;
      const launchTransitionNextStage = launchTransition.nextStageKey || (safeToDispatch
        ? "capture_launch_proof"
        : (currentLaunchStage === "install_workflows" ? "verify_visibility" : "dispatch_gate"));
      const launchTransitionNextLabel = launchTransition.nextStageLabel || recordByKey(launchStages, launchTransitionNextStage)?.label ||
        (safeToDispatch ? "Capture launch proof" : "Verify workflow visibility");
      const launchTransitionPendingCount = Number.isFinite(launchTransition.pendingAcceptanceCount) ? launchTransition.pendingAcceptanceCount : Number(currentLaunchAction?.acceptancePendingCount || 0);
      const launchTransitionGateCommand = launchTransition.gateCommand || launchExecution?.postAuthCheckpoint?.verifyCommand ||
        firstStringIncluding(currentLaunchAction?.verifyCommands, "verify-launch-handoff") ||
        "node scripts/verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown";
      const launchProofReady = !!(publishData && publishData.postPublishEvidenceReady && publishEvidenceFresh(publishData));
      const publishStatus = launchProofReady ? "proof ready" : `${publishBlockers.length} actions`;
      const releaseGate = publishReadinessItems().find((item) => item.key === "release-gates") || {};
      const releaseGateEvidence = Array.isArray(releaseGate.evidence) ? releaseGate.evidence : [];
      const readinessCards = [
        {
          key: "data-ownership",
          tone: "green",
          viewName: "settings",
          label: "데이터 소유권",
          value: "local",
          detail: "브라우저 저장 + JSON 백업/복구",
        },
        {
          key: "release-gate",
          tone: "blue",
          viewName: "system",
          label: "릴리스 게이트",
          value: `${releaseGateEvidence.length} proofs`,
          detail: "route 17/17, mobile search/UI, delete undo, a11y",
          evidenceCount: releaseGateEvidence.length,
        },
        {
          key: "publish-proof",
          tone: launchProofReady ? "green" : "amber",
          viewName: "system",
          label: "공개 증거",
          value: publishStatus,
          detail: launchProofReady ? "Pages/workflow evidence freshness 통과" : "workflow 설치와 dispatch evidence가 남음",
        },
        {
          key: "benchmark-queue",
          tone: "violet",
          viewName: "pm-portfolio",
          label: "벤치마크 큐",
          value: `${benchmarkFocused.length}/${adoptionCandidates.length}`,
          detail: `${sourceBacked.length}개 source-backed 후보 기반`,
        },
      ];
      const firstRunModel = homeFirstRunGuidanceModel({
        todaysEvents,
        openTodos,
        noteCount: dashboard.notes.length,
        totalProjects,
        publishBlockers,
        externalClaimReady,
        launchProofReady,
      });
      const {
        firstRunSteps,
        firstRunReadyCount,
        firstRunActionRequiredCount,
        firstRunNextStep,
        firstRunGuidedStartItems,
        firstRunGuidedStartCoverage,
      } = firstRunModel;
      const milestoneCount = dashboard.gantt.tasks.filter((task) => task.milestone).length;
      const projectFollowThroughModel = homeProjectFollowThroughModel({
        totalProjects,
        totalIssues,
        milestoneCount,
        teamCount: dashboard.team.length,
      });
      const projectFollowThroughHTML = homeProjectFollowThroughHTML(projectFollowThroughModel);
    
      /* Personal-first KPIs */
      const kpis = [
        { title: "오늘 일정",   value: String(todaysEvents.length), unit: "건", color: "#2387ff", badge: "◷", delta: formatKoreanShort(today) },
        { title: "할 일 남음",  value: String(openTodos.length),    unit: "건", color: overdueTodos.length ? "#ff4d5e" : "#22d3ee", badge: "☑", delta: overdueTodos.length ? `지남 ${overdueTodos.length}건` : "양호", trendDown: overdueTodos.length > 0 },
        { title: "이번 주 마감", value: String(weekDeadlines),       unit: "건", color: "#f7a928", badge: "⚑", delta: "앞으로 7일" },
        { title: "진행 프로젝트", value: String(totalProjects),       unit: "개", color: "#17d983", badge: "▦", delta: `${onTrack}개 정상` },
      ];
    
      const { todayEventsHTML, todayTodosHTML, upcomingHTML } = homeTodayCommandContentHTML({ todaysEvents, overdueTodos, todayTodos, upcoming });
      const {
        portfolioBody,
        kanbanBody,
        ganttBody,
        teamBody,
        instancesBody,
        schemaTotalTables,
        schemaBody,
        queriesBody,
        backupsBody,
      } = homeCommandTilePreviewContentHTML({ totalIssues });
    
      setHTML(view, html`
        ${raw(homeHeroHTML({ today, greet, name, todaysEvents, openTodos, overdueTodos }))}
        <section class="kpis kpis-4">${raw(kpis.map((k) => kpiCard(k)).join(""))}</section>
        ${raw(renderDashboardIntelligenceHTML())}
        ${raw(homeExecutionQueueHTML(executionQueue))}
        ${raw(homeCommandTilesHTML({ todayEventsHTML, todayTodosHTML, upcomingHTML, totalProjects, portfolioBody, totalIssues, kanbanBody, dashboard, ganttBody, teamBody, unhealthy, instancesBody, schemaTotalTables, schemaBody, slow, queriesBody, pendingMig, backupsBody }))}
        ${raw(homeFirstRunGuidanceHTML({ firstRunSteps, firstRunReadyCount, firstRunActionRequiredCount, firstRunNextStep, firstRunGuidedStartItems, firstRunGuidedStartCoverage }))}
        ${raw(projectFollowThroughHTML)}
        ${raw(homeLaunchOperationsHTML({
          publishBlockers, launchProofReady, benchmarkFocused, sourceBacked, readinessCards, currentLaunchActionKey, currentLaunchActionLabel, currentLaunchActionStatus, currentLaunchActionCommandCount, currentLaunchWithheldCount, safeToDispatch, externalClaimReady, launchTransition, currentLaunchStage, launchTransitionNextStage, launchTransitionPendingCount, launchTransitionGateCommand, launchInstallMatrix, launchInstallMatrixRows, launchInstallMatrixSignals, launchInstallMatrixPathCount, launchInstallMatrixSignalCount, remoteWorkflowFileLedger, remoteWorkflowFileLedgerItems, remoteWorkflowFileLedgerFileCount, remoteWorkflowFileLedgerReadyCount, remoteWorkflowFileLedgerMissingCount, remoteWorkflowFileLedgerMismatchCount, remoteWorkflowFileLedgerReady, launchProofLedger, launchProofLedgerItems, launchProofLedgerReady, currentLaunchActionDetail, currentLaunchActionCommand, launchTransitionNextLabel,
          launchActionChecklistText, launchActionChecklistReady, launchActionChecklistStatus, launchActionChecklistActiveKey, launchActionChecklistImmediateCommand, launchActionChecklistDeferredCommand, launchActionChecklistRecheckSteps, launchActionChecklistSourceArtifacts, launchActionChecklistDispatchApproval, launchActionChecklistVerificationOnly, launchActionChecklistGuard,
          launchBlockerResolverText, launchBlockerResolverReady, launchBlockerActiveKey, launchBlockerResolution, launchBlockerItems, launchBlockerProofCommands, launchBlockerItemCount, launchBlockerPassCount, launchBlockerActionRequiredCount, launchBlockerDeferredCount, launchBlockerProofCommandCount, launchBlockerFallbackCommands, launchEvidenceGapItems, launchPostInstallIntakeForGap, launchBlockerDispatchGuard, launchBlockerActiveItem, workflowInstallShortcutText, workflowInstallShortcutReady, workflowScopeInstallBlocked, workflowInstallShortcutPaths, workflowInstallShortcutCommandCount, workflowInstallShortcutTargetCount, workflowInstallShortcutPrimaryPath, workflowInstallShortcutPrimaryCommand, workflowInstallShortcutVerifyCommand, workflowInstallShortcutDefaultBranchGuard, workflowInstallShortcutScopeGuard, launchBlockerFallbackPath,
          postInstallEvidenceText, postInstallEvidenceReady, postInstallEvidenceStatus, postInstallEvidenceProofComplete, postInstallEvidenceCompletedCount, postInstallEvidencePendingCount, postInstallEvidenceFieldCount, postInstallEvidenceCommands, postInstallEvidenceSignals, postInstallEvidenceFields, postInstallEvidenceIntake, postInstallQuickProofReady, postInstallQuickProofStepCount, postInstallQuickProofCoverage, postInstallQuickProofSteps, postInstallQuickProofFieldMappingReady, postInstallQuickProofFieldMappingCoverage, postInstallQuickProofMappedFieldCount, postInstallQuickProofCompletedMappedFieldCount, postInstallQuickProofFieldMappings, postInstallVerificationSequence, postInstallVerificationSequenceReady, postInstallVerificationFinalCommand, postInstallEvidenceStopCondition, externalClaimGuardText, externalClaimGuardReady, externalClaimGuard, externalClaimGuardBlockedCount, externalClaimGuardRequirementCount, externalClaimGuardCommands, externalClaimGuardPrimaryRequirement, externalClaimGuardPrimarySignal, externalClaimGuardPrimaryCommand, externalClaimGuardRequirements, externalClaimGuardSignals, homeExternalClaimGuardText,
        }))}
      `);
    }

    return Object.freeze({
      version: VERSION,
      renderHome,
    });
  }

  global.JooParkHomeView = Object.freeze({
    version: VERSION,
    create: createHomeView,
  });
})(typeof window !== "undefined" ? window : globalThis);
