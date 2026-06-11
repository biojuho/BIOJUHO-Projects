(function (root) {
  "use strict";

  const VERSION = "joopark-settings-view/v1";
  const DELETED_ITEM_KIND_LABELS = Object.freeze({
    event: "일정",
    todo: "할 일",
    note: "메모",
    habit: "습관",
    issue: "이슈",
    task: "작업",
    query: "쿼리",
    migration: "마이그레이션",
  });

  function createSettingsView(deps) {
    const options = deps || {};
    const html = options.html;
    const raw = options.raw;
    const kpiCard = typeof options.kpiCard === "function" ? options.kpiCard : function () { return ""; };
    const formatBytes = typeof options.formatBytes === "function" ? options.formatBytes : function (bytes) { return String(bytes); };
    const formatLocalDateTime = typeof options.formatLocalDateTime === "function" ? options.formatLocalDateTime : function (value) { return value || ""; };
    const storageStatusModel = typeof options.storageStatusModel === "function" ? options.storageStatusModel : function () {
      return { localBytes: 0, tone: "ok", statusLabel: "정상" };
    };
    const settingsStorageHealthHTML = typeof options.settingsStorageHealthHTML === "function" ? options.settingsStorageHealthHTML : function () { return ""; };
    const maxImportBytes = Number.isFinite(options.maxImportBytes) ? options.maxImportBytes : 0;

    if (typeof html !== "function" || typeof raw !== "function") {
      throw new Error("settings view requires html and raw helpers");
    }

    function countOf(value) {
      return Array.isArray(value) ? value.length : 0;
    }

    function normalize(value) {
      return String(value || "").trim().toLowerCase();
    }

    function sourceData(source) {
      if (!source || typeof source !== "object") return {};
      if (source.data && typeof source.data === "object") return source.data;
      return source;
    }

    function asArray(value) {
      return Array.isArray(value) ? value : [];
    }

    function deletedRecoveryExpiry(item, retentionDays) {
      const deletedAtMs = Date.parse(item && item.deletedAt ? item.deletedAt : "");
      if (!Number.isFinite(deletedAtMs)) {
        return {
          expiresAt: "",
          daysRemaining: "",
          label: `${retentionDays}일 보관`,
          state: "unknown",
        };
      }
      const expiresAtMs = deletedAtMs + retentionDays * 24 * 60 * 60 * 1000;
      const daysRemaining = Math.max(0, Math.ceil((expiresAtMs - Date.now()) / (24 * 60 * 60 * 1000)));
      return {
        expiresAt: new Date(expiresAtMs).toISOString(),
        daysRemaining,
        label: daysRemaining === 0 ? "오늘 만료" : `${daysRemaining}일 남음`,
        state: daysRemaining <= 3 ? "soon" : "normal",
      };
    }

    function launchRunbookModel(input) {
      const workflowSource = input && input.workflowUiInstallPlan && typeof input.workflowUiInstallPlan === "object" ? input.workflowUiInstallPlan : {};
      const packetSource = input && input.launchExecutionPacket && typeof input.launchExecutionPacket === "object" ? input.launchExecutionPacket : {};
      const workflow = sourceData(workflowSource);
      const packet = sourceData(packetSource);
      const receipt = workflow.installReceipt && typeof workflow.installReceipt === "object" ? workflow.installReceipt : {};
      const plans = asArray(workflow.plans);
      const pagesPlan = plans.find((plan) => plan && plan.key === "pages") || plans[0] || {};
      const driftPlan = plans.find((plan) => plan && plan.key === "drift-watch") || plans[1] || {};
      const currentAction = packet.currentAction && typeof packet.currentAction === "object" ? packet.currentAction : {};
      const postAuth = currentAction.postAuthCheckpoint && typeof currentAction.postAuthCheckpoint === "object" ? currentAction.postAuthCheckpoint : {};
      const stages = asArray(packet.stages);
      const stageTransition = packet.stageTransitionPreview && typeof packet.stageTransitionPreview === "object" ? packet.stageTransitionPreview : {};
      const installMatrix = packet.workflowInstallVerificationMatrix && typeof packet.workflowInstallVerificationMatrix === "object" ? packet.workflowInstallVerificationMatrix : {};
      const installMatrixRows = asArray(installMatrix.matrixRows);
      const installMatrixSignals = asArray(installMatrix.signalChecks);
      const remoteFileLedger = packet.remoteWorkflowFileAcceptanceLedger && typeof packet.remoteWorkflowFileAcceptanceLedger === "object" ? packet.remoteWorkflowFileAcceptanceLedger : {};
      const remoteFileLedgerItems = asArray(remoteFileLedger.files);
      const proofLedger = packet.launchProofAcceptanceLedger && typeof packet.launchProofAcceptanceLedger === "object" ? packet.launchProofAcceptanceLedger : {};
      const proofLedgerItems = asArray(proofLedger.requiredProofs);
      const packetPostInstallIntake = packet.postInstallEvidenceIntake && typeof packet.postInstallEvidenceIntake === "object" ? packet.postInstallEvidenceIntake : {};
      const packetPostInstallFields = asArray(packetPostInstallIntake.fields);
      const packetPostInstallCommands = asArray(packetPostInstallIntake.commands);
      const packetPostInstallSignals = asArray(packetPostInstallIntake.expectedSignals);
      const packetPostInstallChecklist = asArray(packetPostInstallIntake.checklist);
      const packetPostInstallSequence = asArray(packetPostInstallIntake.verificationSequence);
      const expectedSignals = asArray(receipt.expectedSignals).length ? asArray(receipt.expectedSignals) : [
        "remoteWorkflowFilesReady=true",
        "pages remoteExists=true and remoteMatchesTemplate=true",
        "drift-watch remoteExists=true and remoteMatchesTemplate=true",
        "remoteWorkflowVisibilityReady=true",
        "dispatchReady=true",
        "driftDispatchReady=true",
        "allDispatchReady=true",
        "safeToDispatch=true before gh workflow run",
      ];
      const remoteFileCommand = receipt.remoteFileCommand || postAuth.remoteFileCommand || `node scripts/check-remote-workflow-files.mjs --repo ${workflow.suggestedRepo || packet.repo || "OWNER/REPO"} --write`;
      const workflowListCommand = receipt.workflowListCommand || packet.workflowListCommand || `gh workflow list --repo ${workflow.suggestedRepo || packet.repo || "OWNER/REPO"} --all --json name,path,state,id`;
      const dispatchPlanCommand = receipt.dispatchPlanCommand || postAuth.dispatchPlanCommand || workflow.nextVerificationCommand || `node scripts/plan-publish-dispatch.mjs --live --repo ${workflow.suggestedRepo || packet.repo || "OWNER/REPO"} --write`;
      const handoffVerifyCommand = receipt.handoffVerifyCommand || postAuth.verifyCommand || `node scripts/verify-launch-handoff.mjs --repo ${workflow.suggestedRepo || packet.repo || "OWNER/REPO"} --write --markdown`;
      const ready = workflowSource.loaded === true && workflow.workflowUiInstallReady === true && plans.length >= 2 && receipt.ready === true;
      const withheldCommands = asArray(currentAction.withheldCommands);
      const acceptance = asArray(currentAction.acceptanceChecklist);
      const acceptancePassCount = Number.isFinite(currentAction.acceptancePassCount) ? currentAction.acceptancePassCount : acceptance.filter((item) => item.status === "pass").length;
      const acceptancePendingCount = Number.isFinite(currentAction.acceptancePendingCount) ? currentAction.acceptancePendingCount : acceptance.filter((item) => item.status !== "pass").length;
      const safeToDispatch = packet.readyToDispatch === true || packet.safeToDispatch === true;
      const steps = [
        {
          key: "copy-pages-template",
          label: "Copy Pages template",
          target: pagesPlan.targetRepositoryPath || ".github/workflows/joopark-pages.yml",
          command: pagesPlan.templateCopyCommand || "pbcopy < 'docs/github-pages-workflow.yml'",
          proof: "clipboard-template",
          detail: "Copy the verified Pages workflow template before opening GitHub.",
        },
        {
          key: "create-pages-workflow",
          label: "Create Pages workflow",
          target: pagesPlan.targetRepositoryPath || ".github/workflows/joopark-pages.yml",
          command: pagesPlan.githubNewFileOpenCommand || "",
          proof: "default-branch-commit",
          detail: "Commit the pasted YAML to the repository default branch.",
          url: pagesPlan.githubNewFileUrl || "",
        },
        {
          key: "copy-drift-template",
          label: "Copy Drift Watch template",
          target: driftPlan.targetRepositoryPath || ".github/workflows/joopark-drift-watch.yml",
          command: driftPlan.templateCopyCommand || "pbcopy < 'docs/github-drift-watch-workflow.yml'",
          proof: "clipboard-template",
          detail: "Copy the drift watcher template separately so file contents do not mix.",
        },
        {
          key: "create-drift-workflow",
          label: "Create Drift Watch workflow",
          target: driftPlan.targetRepositoryPath || ".github/workflows/joopark-drift-watch.yml",
          command: driftPlan.githubNewFileOpenCommand || "",
          proof: "default-branch-commit",
          detail: "Commit the drift watcher YAML to the same default branch.",
          url: driftPlan.githubNewFileUrl || "",
        },
        {
          key: "verify-remote-parity",
          label: "Verify remote file parity",
          target: workflow.defaultBranch || packet.defaultBranch || "main",
          command: remoteFileCommand,
          proof: "remoteWorkflowFilesReady=true",
          detail: "Confirm both remote workflow files match the local template SHA-256 values.",
        },
        {
          key: "verify-workflow-visibility",
          label: "Verify workflow visibility",
          target: workflow.actionsUrl || "",
          command: workflowListCommand,
          proof: "remoteWorkflowVisibilityReady=true",
          detail: "Confirm GitHub Actions can see both workflow files before dispatch.",
        },
        {
          key: "verify-dispatch-guard",
          label: "Recheck dispatch guard",
          target: workflow.suggestedRepo || packet.repo || "OWNER/REPO",
          command: dispatchPlanCommand,
          secondaryCommand: handoffVerifyCommand,
          proof: "safeToDispatch=true",
          detail: "Run the repo-scoped plan and handoff verifier. Dispatch remains withheld until every gate passes.",
        },
      ];
      const defaultPostInstallEvidenceIntakeCommands = [
        remoteFileCommand,
        workflowListCommand,
        dispatchPlanCommand,
        handoffVerifyCommand,
      ].filter(Boolean);
      const postInstallEvidenceIntakeCommands = packetPostInstallCommands.length ? packetPostInstallCommands : defaultPostInstallEvidenceIntakeCommands;
      const defaultPostInstallEvidenceIntakeSequence = [
        {
          key: "remote_file_parity",
          label: "Remote workflow file check",
          command: remoteFileCommand,
          expected: "remoteWorkflowFilesReady=true",
        },
        {
          key: "actions_visibility",
          label: "Actions visibility check",
          command: workflowListCommand,
          expected: "remoteWorkflowVisibilityReady=true",
        },
        {
          key: "dispatch_readiness",
          label: "Dispatch readiness plan",
          command: dispatchPlanCommand,
          expected: "allDispatchReady=true",
        },
        {
          key: "handoff_verifier",
          label: "Launch handoff verifier",
          command: handoffVerifyCommand,
          expected: "safeToDispatch=true before gh workflow run",
        },
      ].filter((step) => step.command);
      const postInstallEvidenceIntakeSequence = packetPostInstallSequence.length ? packetPostInstallSequence : defaultPostInstallEvidenceIntakeSequence;
      const postInstallEvidenceIntakeSequenceReady = packetPostInstallIntake.verificationSequenceReady === true ||
        (postInstallEvidenceIntakeSequence.length === 4 && postInstallEvidenceIntakeSequence.every((step) => step.command && step.expected));
      const postInstallEvidenceIntakeFinalCommand = packetPostInstallIntake.finalVerificationCommand ||
        postInstallEvidenceIntakeSequence[postInstallEvidenceIntakeSequence.length - 1]?.command ||
        "";
      const packetPostInstallQuickProofSteps = asArray(packetPostInstallIntake.quickProofSteps);
      const quickProofEvidenceFieldByKey = {
        remote_file_parity: "remote_parity_proof",
        actions_visibility: "actions_visibility_proof",
        dispatch_readiness: "dispatch_readiness_proof",
        handoff_verifier: "handoff_verifier_proof",
      };
      const postInstallQuickProofSteps = packetPostInstallQuickProofSteps.length
        ? packetPostInstallQuickProofSteps
        : postInstallEvidenceIntakeSequence.map((step) => ({
            key: step.key,
            label: step.label,
            command: step.command,
            expected: step.expected,
            evidenceFieldKey: quickProofEvidenceFieldByKey[step.key] || "",
            status: "evidence_required",
          }));
      const postInstallQuickProofStepCount = Number.isFinite(Number(packetPostInstallIntake.quickProofStepCount))
        ? Number(packetPostInstallIntake.quickProofStepCount)
        : postInstallQuickProofSteps.length;
      const postInstallQuickProofCoverage = Number.isFinite(Number(packetPostInstallIntake.quickProofCoverage))
        ? Number(packetPostInstallIntake.quickProofCoverage)
        : postInstallQuickProofStepCount === 4 && postInstallQuickProofSteps.every((step) => step.command && step.expected && step.evidenceFieldKey) ? 1 : 0;
      const postInstallQuickProofReady = packetPostInstallIntake.quickProofReady === true || postInstallQuickProofCoverage === 1;
      const defaultPostInstallEvidenceIntakeSignals = expectedSignals.length ? expectedSignals : [
        "remoteWorkflowFilesReady=true",
        "pages remoteExists=true and remoteMatchesTemplate=true",
        "drift-watch remoteExists=true and remoteMatchesTemplate=true",
        "remoteWorkflowVisibilityReady=true",
        "dispatchReady=true",
        "driftDispatchReady=true",
        "allDispatchReady=true",
        "safeToDispatch=true before gh workflow run",
      ];
      const postInstallEvidenceIntakeSignals = packetPostInstallSignals.length ? packetPostInstallSignals : defaultPostInstallEvidenceIntakeSignals;
      const defaultPostInstallEvidenceIntakeChecklist = [
        "Paste both default-branch workflow commit URLs or SHA values.",
        "Paste remoteWorkflowFilesReady=true from the remote file check.",
        "Paste the Actions workflow list showing both workflow files visible.",
        "Paste allDispatchReady=true from the publish dispatch plan.",
        "Paste safeToDispatch=true from verify-launch-handoff before any gh workflow run.",
      ];
      const postInstallEvidenceIntakeChecklist = packetPostInstallChecklist.length ? packetPostInstallChecklist : defaultPostInstallEvidenceIntakeChecklist;
      const defaultPostInstallEvidenceIntakeFields = [
        ["Pages workflow commit", "[paste commit URL or SHA for .github/workflows/joopark-pages.yml on the default branch]"],
        ["Drift Watch workflow commit", "[paste commit URL or SHA for .github/workflows/joopark-drift-watch.yml on the default branch]"],
        ["Remote parity proof", "[paste generatedAt plus remoteWorkflowFilesReady=true from data/remote-workflow-file-check.json]"],
        ["Actions visibility proof", "[paste gh workflow list output showing both workflow paths visible]"],
        ["Dispatch readiness proof", "[paste generatedAt plus dispatchReady=true, driftDispatchReady=true, and allDispatchReady=true]"],
        ["Handoff verifier proof", "[paste verify-launch-handoff status plus safeToDispatch=true before gh workflow run]"],
      ];
      const postInstallEvidenceIntakeFields = packetPostInstallFields.length
        ? packetPostInstallFields.map((field) => [field.label || field.key || "Proof field", field.placeholder || field.expectedValue || field.currentValue || "not available"])
        : defaultPostInstallEvidenceIntakeFields;
      const postInstallStopCondition = packetPostInstallIntake.stopCondition || "Stop condition: do not run gh workflow run, archive proof, or claim launch until all six post-install evidence fields are filled and verify-launch-handoff reports safeToDispatch=true.";
      const postInstallDispatchGuard = packetPostInstallIntake.dispatchGuard || receipt.dispatchGuard || "Do not run gh workflow run until every post-install evidence field has been filled, remoteWorkflowFilesReady=true, remoteWorkflowVisibilityReady=true, dispatchReady=true, driftDispatchReady=true, allDispatchReady=true, and verify-launch-handoff reports safeToDispatch=true.";
      const packetPostInstallQuickProofFieldMappings = asArray(packetPostInstallIntake.quickProofFieldMappings);
      const postInstallFieldKeyByLabel = {
        "Remote parity proof": "remote_parity_proof",
        "Actions visibility proof": "actions_visibility_proof",
        "Dispatch readiness proof": "dispatch_readiness_proof",
        "Handoff verifier proof": "handoff_verifier_proof",
      };
      const postInstallFieldByKey = new Map(postInstallEvidenceIntakeFields.map(([label, placeholder]) => [postInstallFieldKeyByLabel[label] || label, { label, placeholder }]));
      const postInstallQuickProofFieldMappings = packetPostInstallQuickProofFieldMappings.length
        ? packetPostInstallQuickProofFieldMappings
        : postInstallQuickProofSteps.map((step) => {
            const mappedField = postInstallFieldByKey.get(step.evidenceFieldKey) || {};
            return {
              stepKey: step.key || "",
              stepLabel: step.label || "",
              fieldKey: step.evidenceFieldKey || "",
              fieldLabel: mappedField.label || "",
              fieldStatus: "evidence_required",
              fieldCompleted: false,
              currentValue: mappedField.placeholder || "not available",
              expectedValue: step.expected || "not available",
              proofCommand: step.command || "not available",
              stopCondition: postInstallStopCondition,
            };
          });
      const postInstallQuickProofMappedFieldCount = Number.isFinite(Number(packetPostInstallIntake.quickProofMappedFieldCount))
        ? Number(packetPostInstallIntake.quickProofMappedFieldCount)
        : postInstallQuickProofFieldMappings.length;
      const postInstallQuickProofCompletedMappedFieldCount = Number.isFinite(Number(packetPostInstallIntake.quickProofCompletedMappedFieldCount))
        ? Number(packetPostInstallIntake.quickProofCompletedMappedFieldCount)
        : postInstallQuickProofFieldMappings.filter((item) => item.fieldCompleted).length;
      const postInstallQuickProofFieldMappingCoverage = Number.isFinite(Number(packetPostInstallIntake.quickProofFieldMappingCoverage))
        ? Number(packetPostInstallIntake.quickProofFieldMappingCoverage)
        : postInstallQuickProofMappedFieldCount === 4 && postInstallQuickProofFieldMappings.every((item) => item.stepKey && item.fieldKey && item.fieldLabel && item.proofCommand && item.expectedValue) ? 1 : 0;
      const postInstallQuickProofFieldMappingReady = packetPostInstallIntake.quickProofFieldMappingReady === true || postInstallQuickProofFieldMappingCoverage === 1;
      const postInstallEvidenceIntakeFieldCoverage = Number.isFinite(Number(packetPostInstallIntake.fieldCoverage))
        ? Number(packetPostInstallIntake.fieldCoverage)
        : postInstallEvidenceIntakeFields.length >= 6 ? 1 : 0;
      const postInstallEvidenceIntakeCompletedFieldCount = Number.isFinite(Number(packetPostInstallIntake.completedFieldCount)) ? Number(packetPostInstallIntake.completedFieldCount) : 0;
      const postInstallEvidenceIntakeProofComplete = packetPostInstallIntake.proofComplete === true;
      const postInstallEvidenceIntakeStatus = packetPostInstallIntake.status || "collect_post_install_proof";
      const dispatchGuard = postInstallDispatchGuard || postAuth.guard;
      const currentStageKey = stageTransition.currentStageKey || currentAction.stageKey || stages.find((stage) => stage.status === "action_required")?.key || "";
      const transitionNextStage = stageTransition.nextStageKey || (safeToDispatch ? "capture_launch_proof" : (currentStageKey === "install_workflows" ? "verify_visibility" : "dispatch_gate"));
      const transitionNextLabel = stageTransition.nextStageLabel || stages.find((stage) => stage.key === transitionNextStage)?.label || (safeToDispatch ? "Capture launch proof" : "Verify workflow visibility");
      const transitionPendingCount = Number.isFinite(stageTransition.pendingAcceptanceCount) ? stageTransition.pendingAcceptanceCount : acceptancePendingCount;
      const transitionGateCommand = stageTransition.gateCommand || handoffVerifyCommand;
      const postInstallEvidenceIntakeReady = packetPostInstallIntake.ready === true || (
        ready &&
        postInstallEvidenceIntakeCommands.length >= 4 &&
        postInstallEvidenceIntakeSignals.length >= 8 &&
        postInstallEvidenceIntakeFieldCoverage === 1
      );
      const postInstallQuickProofReceipt = packetPostInstallIntake.quickProofReceipt || [
        "JooPark Post-Install Quick Proof Receipt",
        `Status: ${postInstallEvidenceIntakeStatus}`,
        `Repo: ${workflow.suggestedRepo || packet.repo || "OWNER/REPO"}`,
        `Default branch: ${workflow.defaultBranch || packet.defaultBranch || "main"}`,
        `Proof complete: ${postInstallEvidenceIntakeProofComplete}`,
        `Fields complete: ${postInstallEvidenceIntakeCompletedFieldCount}/${postInstallEvidenceIntakeFields.length}`,
        `Quick proof steps: ${postInstallQuickProofStepCount}`,
        "",
        "4-step proof checklist:",
        ...postInstallQuickProofSteps.map((step, index) => `${index + 1}. ${step.key}: run ${step.command}; expect ${step.expected}; paste into ${step.evidenceFieldKey || "matching evidence field"}`),
        "",
        "Mapped proof fields:",
        ...postInstallQuickProofFieldMappings.map((item, index) => `${index + 1}. ${item.stepKey} -> ${item.fieldKey}: ${item.fieldStatus}; completed=${item.fieldCompleted}; current=${item.currentValue}; expected=${item.expectedValue}`),
        "",
        postInstallStopCondition,
      ].join("\n");
      const postInstallEvidenceIntakeText = [
        "# JooPark Workflow Post-Install Evidence Intake",
        "",
        "Status: collect post-install proof only; not dispatch approval",
        `Repo: ${workflow.suggestedRepo || packet.repo || "OWNER/REPO"}`,
        `Default branch: ${workflow.defaultBranch || packet.defaultBranch || "main"}`,
        `Quick proof: ready=${postInstallQuickProofReady}; steps=${postInstallQuickProofStepCount}; coverage=${postInstallQuickProofCoverage}`,
        `Quick proof field mapping: ready=${postInstallQuickProofFieldMappingReady}; mapped=${postInstallQuickProofMappedFieldCount}; completed=${postInstallQuickProofCompletedMappedFieldCount}/${postInstallQuickProofMappedFieldCount}; coverage=${postInstallQuickProofFieldMappingCoverage}`,
        "",
        postInstallQuickProofReceipt,
        "",
        "Required proof fields:",
        "- Pages workflow committed to `.github/workflows/joopark-pages.yml` on the default branch",
        "- Drift Watch workflow committed to `.github/workflows/joopark-drift-watch.yml` on the default branch",
        "- remoteWorkflowFilesReady=true",
        "- remoteWorkflowVisibilityReady=true",
        "- dispatchReady=true, driftDispatchReady=true, allDispatchReady=true",
        "- safeToDispatch=true before gh workflow run",
        "",
        "Evidence fields to fill:",
        ...postInstallEvidenceIntakeFields.map(([label, placeholder]) => `- ${label}: ${placeholder}`),
        "",
        "Verification commands to run after GitHub UI install:",
        ...postInstallEvidenceIntakeCommands.map((command, index) => `${index + 1}. ${command}`),
        "",
        "Verification sequence:",
        ...postInstallEvidenceIntakeSequence.map((step, index) => `${index + 1}. ${step.key}: ${step.label}; command=${step.command}; expected=${step.expected}`),
        "",
        "Expected success signals:",
        ...postInstallEvidenceIntakeSignals.map((signal) => `- ${signal}`),
        "",
        "Evidence checklist:",
        ...postInstallEvidenceIntakeChecklist.map((item) => `- [ ] ${item}`),
        "",
        "Dispatch guard:",
        dispatchGuard,
        postInstallStopCondition,
        "Do not run gh workflow run until every post-install evidence field has been filled and verify-launch-handoff reports safeToDispatch=true.",
      ].join("\n");

      return {
        ready,
        repo: workflow.suggestedRepo || packet.repo || "OWNER/REPO",
        defaultBranch: workflow.defaultBranch || packet.defaultBranch || "main",
        currentStage: currentAction.stageKey || "",
        currentLabel: currentAction.label || "Install workflows on the default branch",
        currentStatus: currentAction.status || packet.currentStatus || (safeToDispatch ? "ready" : "action_required"),
        successCondition: currentAction.successCondition || "remoteWorkflowFilesReady=true and workflow visibility confirmed.",
        remoteWorkflowFilesReady: packet.remoteWorkflowFilesReady === true,
        readyToDispatch: safeToDispatch,
        readyForExternalClaim: packet.readyForExternalClaim === true,
        withheldCount: withheldCommands.length,
        acceptancePassCount,
        acceptancePendingCount,
        stepCount: steps.length,
        signalCount: expectedSignals.length,
        steps,
        expectedSignals,
        dispatchGuard,
        transitionCurrentStage: currentStageKey,
        transitionNextStage,
        transitionNextLabel,
        transitionPendingCount,
        transitionGateCommand,
        transitionSource: stageTransition.source || "ui-fallback",
        installMatrixSource: installMatrix.source || "missing",
        installMatrixStatus: installMatrix.status || "unknown",
        installMatrixPathCount: Number.isFinite(installMatrix.installPathCount) ? installMatrix.installPathCount : installMatrixRows.length,
        installMatrixSignalCount: Number.isFinite(installMatrix.requiredSignalCount) ? installMatrix.requiredSignalCount : installMatrixSignals.length,
        installMatrixCommandCount: Number.isFinite(installMatrix.verificationCommandCount) ? installMatrix.verificationCommandCount : asArray(installMatrixRows[0]?.verificationCommands).length,
        installMatrixNextStage: installMatrix.nextStageKey || "verify_visibility",
        installMatrixRows,
        installMatrixSignals,
        installMatrixHandoffCommand: installMatrix.handoffCommand || transitionGateCommand,
        remoteFileLedgerSource: remoteFileLedger.source || "missing",
        remoteFileLedgerStatus: remoteFileLedger.status || "missing",
        remoteFileLedgerFileCount: Number.isFinite(remoteFileLedger.fileCount) ? remoteFileLedger.fileCount : remoteFileLedgerItems.length,
        remoteFileLedgerReadyCount: Number.isFinite(remoteFileLedger.readyCount) ? remoteFileLedger.readyCount : 0,
        remoteFileLedgerMissingCount: Number.isFinite(remoteFileLedger.missingCount) ? remoteFileLedger.missingCount : 0,
        remoteFileLedgerMismatchCount: Number.isFinite(remoteFileLedger.mismatchCount) ? remoteFileLedger.mismatchCount : 0,
        remoteFileLedgerVerifyCommand: remoteFileLedger.verifyCommand || remoteFileCommand,
        remoteFileLedgerItems,
        proofLedgerSource: proofLedger.source || "missing",
        proofLedgerStatus: proofLedger.status || "missing",
        proofLedgerRequiredCount: Number.isFinite(proofLedger.requiredProofCount) ? proofLedger.requiredProofCount : proofLedgerItems.length,
        proofLedgerReadyCount: Number.isFinite(proofLedger.readyProofCount) ? proofLedger.readyProofCount : 0,
        proofLedgerPendingCount: Number.isFinite(proofLedger.pendingProofCount) ? proofLedger.pendingProofCount : proofLedgerItems.length,
        proofLedgerCurrentGate: proofLedger.currentGate || "capture_launch_proof",
        proofLedgerDeferredUntil: proofLedger.deferredUntil || "safeToDispatch=true",
        proofLedgerCaptureCommand: proofLedger.captureWriteCommand || `node scripts/capture-publish-evidence.mjs --live --repo ${workflow.suggestedRepo || packet.repo || "OWNER/REPO"} --write`,
        proofLedgerItems,
        postInstallEvidenceIntakeReady,
        postInstallEvidenceIntakeCommands,
        postInstallEvidenceIntakeSignals,
        postInstallEvidenceIntakeChecklist,
        postInstallEvidenceIntakeSequence,
        postInstallEvidenceIntakeSequenceReady,
        postInstallEvidenceIntakeFinalCommand,
        postInstallEvidenceIntakeFields,
        postInstallEvidenceIntakeFieldCoverage,
        postInstallEvidenceIntakeCompletedFieldCount,
        postInstallEvidenceIntakeProofComplete,
        postInstallEvidenceIntakeStatus,
        postInstallEvidenceIntakeText,
        postInstallQuickProofReady,
        postInstallQuickProofSteps,
        postInstallQuickProofStepCount,
        postInstallQuickProofCoverage,
        postInstallQuickProofFieldMappingReady,
        postInstallQuickProofFieldMappings,
        postInstallQuickProofMappedFieldCount,
        postInstallQuickProofCompletedMappedFieldCount,
        postInstallQuickProofFieldMappingCoverage,
        postInstallQuickProofReceipt,
        source: workflowSource.source || "data/workflow-ui-install-plan.json",
        packetSource: packetSource.source || "data/launch-execution-packet.json",
      };
    }

    function settingsViewModel(input) {
      const data = input || {};
      const dashboard = data.dashboard && typeof data.dashboard === "object" ? data.dashboard : {};
      const settings = dashboard.settings && typeof dashboard.settings === "object" ? dashboard.settings : {};
      const ui = dashboard.ui && typeof dashboard.ui === "object" ? dashboard.ui : {};
      const health = data.storageHealth && typeof data.storageHealth === "object" ? data.storageHealth : {};
      const storageView = storageStatusModel(health);
      const theme = ui.theme === "light" ? "light" : "dark";
      const saved = formatLocalDateTime(dashboard.lastSavedAt);
      const handoffs = data.handoffs && typeof data.handoffs === "object" ? data.handoffs : {};
      const deletedItemRetentionDays = Number.isFinite(Number(data.deletedItemRetentionDays)) ? Math.max(1, Math.trunc(Number(data.deletedItemRetentionDays))) : 30;
      const deletedRecoveryFilter = data.deletedRecoveryFilter && typeof data.deletedRecoveryFilter === "object" ? data.deletedRecoveryFilter : {};
      const deletedRecoveryQuery = String(deletedRecoveryFilter.query || "").trim().slice(0, 80);
      const deletedRecoveryKind = DELETED_ITEM_KIND_LABELS[deletedRecoveryFilter.kind] ? deletedRecoveryFilter.kind : "all";
      const allDeletedItems = asArray(dashboard.deletedItems)
        .filter((item) => item && typeof item === "object" && item.id && DELETED_ITEM_KIND_LABELS[item.kind])
        .map((item) => {
          const expiry = deletedRecoveryExpiry(item, deletedItemRetentionDays);
          return {
            ...item,
            recoveryExpiresAt: expiry.expiresAt,
            recoveryDaysRemaining: expiry.daysRemaining,
            recoveryExpiryLabel: expiry.label,
            recoveryExpiryState: expiry.state,
          };
        })
        .slice(0, 40);
      const deletedQuery = normalize(deletedRecoveryQuery);
      const deletedItems = allDeletedItems.filter((item) => {
        if (deletedRecoveryKind !== "all" && item.kind !== deletedRecoveryKind) return false;
        if (!deletedQuery) return true;
        return normalize(`${item.label || ""} ${item.recordId || ""} ${deletedItemKindLabel(item.kind)}`).includes(deletedQuery);
      });
      const deletedKinds = Array.from(new Set(allDeletedItems.map((item) => item.kind))).filter((kind) => DELETED_ITEM_KIND_LABELS[kind]);

      return {
        dashboard,
        health,
        storageView,
        name: settings.displayName || "박주호",
        theme,
        saved,
        allDeletedItems,
        deletedItems,
        deletedItemRetentionDays,
        deletedRecoveryFilter: {
          query: deletedRecoveryQuery,
          kind: deletedRecoveryKind,
        },
        showReferenceProjects: settings.showReferenceProjects === true,
        deletedKinds,
        counts: {
          events: countOf(dashboard.events),
          todos: countOf(dashboard.todos),
          notes: countOf(dashboard.notes),
          deletedItems: allDeletedItems.length,
        },
        handoffs: {
          backup: handoffs.backup || "",
          deploy: handoffs.deploy || "",
          privacy: handoffs.privacy || "",
        },
        launchRunbook: launchRunbookModel(data),
      };
    }

    function storageKpi(model) {
      const tone = model.storageView.tone;
      const color = tone === "error" ? "#ff4d5e" : tone === "warn" ? "#f7a928" : "#17d983";
      const badge = tone === "error" || tone === "warn" ? "!" : "✓";
      return {
        title: "저장 상태",
        value: model.storageView.statusLabel,
        unit: "",
        color,
        badge,
        delta: `${formatBytes(model.storageView.localBytes)} · 마지막 저장 ${model.saved}`,
      };
    }

    function settingsKpisHTML(model) {
      const kpis = [
        { title: "저장된 일정", value: String(model.counts.events), unit: "건", color: "#2387ff", badge: "◷", delta: "" },
        { title: "저장된 할 일", value: String(model.counts.todos), unit: "건", color: "#22d3ee", badge: "☑", delta: "" },
        { title: "저장된 메모", value: String(model.counts.notes), unit: "개", color: "#a970ff", badge: "✎", delta: "" },
        storageKpi(model),
      ];
      return html`<section class="kpis kpis-4" data-settings-view-module="${VERSION}">${raw(kpis.map((item) => kpiCard(item)).join(""))}</section>`;
    }

    function profilePanelHTML(model) {
      return html`
        <section class="panel">
          <div class="panel-head"><div><h2>프로필</h2></div></div>
          <form class="settings-form" data-action="save-settings">
            <label>표시 이름
              <input type="text" name="displayName" maxlength="40" value="${model.name}" placeholder="이름" />
            </label>
            <button type="submit" class="primary-btn">저장</button>
          </form>
        </section>
      `;
    }

    function themePanelHTML(model) {
      return html`
        <section class="panel">
          <div class="panel-head"><div><h2>화면 테마</h2></div></div>
          <p class="settings-note">밝은 환경에서는 라이트, 어두운 환경에서는 다크 테마를 선택하세요. 설정은 이 브라우저에 저장됩니다.</p>
          <div class="theme-toggle" role="group" aria-label="테마 선택">
            <button type="button" class="theme-opt ${raw(model.theme === "dark" ? "is-active" : "")}" data-action="set-theme" data-theme="dark" aria-pressed="${model.theme === "dark" ? "true" : "false"}">🌙 다크</button>
            <button type="button" class="theme-opt ${raw(model.theme === "light" ? "is-active" : "")}" data-action="set-theme" data-theme="light" aria-pressed="${model.theme === "light" ? "true" : "false"}">☀️ 라이트</button>
          </div>
        </section>
      `;
    }

    function referenceProjectsPanelHTML(model) {
      return html`
        <section class="panel settings-reference-projects" data-settings-reference-projects data-reference-projects-visible="${model.showReferenceProjects ? "true" : "false"}">
          <div class="panel-head"><div><h2>참고 자료</h2></div></div>
          <button type="button" class="primary-btn" data-action="toggle-reference-projects" aria-pressed="${model.showReferenceProjects ? "true" : "false"}">${model.showReferenceProjects ? "숨기기" : "보기"}</button>
        </section>
      `;
    }

    function backupPanelHTML() {
      return html`
        <section class="panel">
          <div class="panel-head"><div><h2>데이터 백업</h2></div></div>
          <p class="settings-note">모든 일정 · 할 일 · 메모는 이 브라우저(localStorage)에 자동 저장됩니다. 기기를 옮기거나 백업하려면 JSON으로 내보내고, 다른 기기에서 가져오세요. 가져오기 파일은 ${formatBytes(maxImportBytes)} 이하만 처리하며, 컬렉션별 항목 수 상한을 넘으면 가져오지 않습니다.</p>
          <div class="settings-actions">
            <button type="button" class="primary-btn" data-action="export-data">⬇ 데이터 내보내기 (JSON)</button>
            <label class="file-btn">⬆ 가져오기
              <input id="importFile" type="file" accept="application/json,.json" />
            </label>
            <button type="button" class="danger-btn" data-action="reset-data">전체 초기화</button>
          </div>
        </section>
      `;
    }

    function deletedItemKindLabel(kind) {
      return DELETED_ITEM_KIND_LABELS[kind] || "항목";
    }

    function recentlyDeletedPanelHTML(model) {
      const items = asArray(model.deletedItems);
      const allItems = asArray(model.allDeletedItems);
      const filter = model.deletedRecoveryFilter || { query: "", kind: "all" };
      const activeFilter = !!filter.query || filter.kind !== "all";
      const kindOptions = ["all", ...asArray(model.deletedKinds)].map((kind) => html`
        <option value="${kind}" ${raw(filter.kind === kind ? "selected" : "")}>${kind === "all" ? "전체 종류" : deletedItemKindLabel(kind)}</option>
      `).join("");
      const rows = items.map((item) => html`
        <article class="deleted-recovery-row" role="listitem" data-deleted-recovery-item data-deleted-id="${item.id}" data-deleted-kind="${item.kind}" data-deleted-recovery-expires-at="${item.recoveryExpiresAt}" data-deleted-recovery-days-remaining="${item.recoveryDaysRemaining}" data-deleted-recovery-expiry-state="${item.recoveryExpiryState}">
          <div class="deleted-recovery-main">
            <strong>${item.label || deletedItemKindLabel(item.kind)}</strong>
            <small>
              ${deletedItemKindLabel(item.kind)} · ${formatLocalDateTime(item.deletedAt)}${item.recordId ? ` · ${item.recordId}` : ""}
              <span class="deleted-recovery-expiry" data-deleted-recovery-expiry data-expiry-state="${item.recoveryExpiryState}" title="${item.recoveryExpiresAt ? `만료: ${formatLocalDateTime(item.recoveryExpiresAt)}` : "보관 만료일 미확인"}">${item.recoveryExpiryLabel}</span>
            </small>
          </div>
          <div class="deleted-recovery-actions">
            <button type="button" class="deleted-recovery-restore" data-action="restore-deleted-item" data-deleted-id="${item.id}" aria-label="${item.label || deletedItemKindLabel(item.kind)} 복구">↩ 복구</button>
            <button type="button" class="deleted-recovery-discard" data-action="discard-deleted-item" data-deleted-id="${item.id}" aria-label="${item.label || deletedItemKindLabel(item.kind)} 폐기">✕ 폐기</button>
          </div>
        </article>
      `).join("");
      return html`
        <section class="panel deleted-recovery-panel" data-settings-deleted-recovery data-deleted-recovery-count="${allItems.length}" data-deleted-recovery-visible-count="${items.length}" data-deleted-recovery-kind="${filter.kind}" data-deleted-recovery-query="${filter.query}" data-deleted-recovery-retention-days="${model.deletedItemRetentionDays}">
          <div class="panel-head">
            <div>
              <h2>최근 삭제</h2>
              <p>${allItems.length}개 보관 · ${items.length}개 표시 · ${model.deletedItemRetentionDays}일</p>
            </div>
            ${allItems.length ? raw(html`
              <div class="deleted-recovery-head-actions">
                <button type="button" class="deleted-recovery-restore-all" data-action="restore-all-deleted-items">모두 복구</button>
                <button type="button" class="deleted-recovery-clear" data-action="clear-deleted-items">비우기</button>
              </div>
            `) : ""}
          </div>
          ${allItems.length ? raw(html`
            <div class="deleted-recovery-tools" data-deleted-recovery-tools>
              <label>검색
                <input type="search" value="${filter.query}" maxlength="80" placeholder="제목, ID, 종류" data-deleted-recovery-search aria-label="최근 삭제 검색" autocomplete="off" />
              </label>
              <label>종류
                <select data-deleted-recovery-kind-filter aria-label="최근 삭제 종류 필터">${raw(kindOptions)}</select>
              </label>
              ${activeFilter ? raw(html`<button type="button" class="deleted-recovery-reset" data-action="clear-deleted-recovery-filter">필터 초기화</button>`) : ""}
            </div>
          `) : ""}
          ${items.length
            ? raw(html`<div class="deleted-recovery-list" role="list" aria-label="최근 삭제 항목">${raw(rows)}</div>`)
            : raw(html`<p class="settings-note" data-deleted-recovery-empty>${allItems.length ? "조건에 맞는 삭제 항목이 없습니다." : "보관된 삭제 항목이 없습니다."}</p>`)}
        </section>
      `;
    }

    function handoffCardHTML({ kind, title, copyLabel, text, items }) {
      return html`
        <article class="settings-handoff-card" role="listitem" data-settings-${kind}-handoff>
          <strong>${title}</strong>
          <ul>
            ${raw(items.map((item) => html`<li>${item}</li>`).join(""))}
          </ul>
          <button type="button" class="portfolio-export-download portfolio-export-copy" data-action="copy-settings-handoff" data-settings-handoff-copy="${kind}" data-settings-handoff-text="${text}">${copyLabel}</button>
          <small class="portfolio-export-status" data-settings-handoff-copy-status aria-live="polite"></small>
        </article>
      `;
    }

    function handoffPanelHTML(model) {
      return html`
        <section class="panel settings-handoff" data-settings-handoff>
          <div class="panel-head"><div><h2>운영 handoff</h2></div></div>
          <p class="settings-note">외부 공유 전에는 데이터 보호와 배포 절차를 같은 순서로 확인하세요. 아래 내용은 현재 워크스페이스 상태를 포함한 복사용 체크리스트입니다.</p>
          <div class="settings-handoff-grid" role="list" aria-label="운영 handoff 체크리스트">
            ${raw(handoffCardHTML({
              kind: "backup",
              title: "백업 · 가져오기 · 초기화",
              copyLabel: "체크리스트 복사",
              text: model.handoffs.backup,
              items: [
                "내보내기 후 JSON 파일명과 생성 시각을 확인합니다.",
                "가져오기는 기존 데이터를 대체하므로 먼저 백업합니다.",
                "초기화 후 홈의 빈 상태 CTA로 첫 데이터를 다시 만듭니다.",
              ],
            }))}
            ${raw(handoffCardHTML({
              kind: "deploy",
              title: "배포 · GitHub Pages",
              copyLabel: "배포 handoff 복사",
              text: model.handoffs.deploy,
              items: [
                raw(html`<code>npm run verify</code>로 패키지와 브라우저 게이트를 통과시킵니다.`),
                "Pages workflow는 repository root의 default branch에 설치합니다.",
                raw(html`workflow 파일 push는 <code>workflow</code> scope 토큰이나 GitHub UI 세션에서만 수행합니다.`),
                raw(html`device-code 승인 code는 저장하지 않고 <code>workflowScopeAvailable: true</code> 재검증 전 dispatch를 막습니다.`),
              ],
            }))}
            ${raw(handoffCardHTML({
              kind: "privacy",
              title: "개인정보 · 저장소 안전",
              copyLabel: "privacy handoff 복사",
              text: model.handoffs.privacy,
              items: [
                "데이터는 이 브라우저 localStorage에 저장되며 서버로 동기화하지 않습니다.",
                "토큰, 비밀번호, 주민번호, API key 같은 민감 정보는 저장하지 않습니다.",
                "내보낸 JSON은 전체 워크스페이스 데이터이므로 공유 전 private 파일로 취급합니다.",
              ],
            }))}
          </div>
        </section>
      `;
    }

    function launchRunbookHTML(model) {
      const runbook = model.launchRunbook;
      return html`
        <section class="panel settings-launch-runbook" data-settings-launch-runbook data-settings-launch-runbook-ready="${runbook.ready ? "true" : "false"}" data-settings-launch-runbook-step-count="${runbook.stepCount}" data-settings-launch-runbook-signal-count="${runbook.signalCount}" data-settings-launch-runbook-safe-to-dispatch="${runbook.readyToDispatch ? "true" : "false"}" data-settings-launch-runbook-ready-for-external-claim="${runbook.readyForExternalClaim ? "true" : "false"}" data-settings-launch-runbook-withheld-count="${runbook.withheldCount}" data-settings-launch-runbook-current-stage="${runbook.currentStage}" data-settings-launch-runbook-source="${runbook.source}" data-settings-launch-runbook-packet-source="${runbook.packetSource}">
          <div class="panel-head">
            <div>
              <h2>배포 설치 runbook</h2>
              <p>GitHub UI install first, dispatch later</p>
            </div>
            <span class="publish-state">${runbook.readyToDispatch ? "ready" : runbook.currentStatus}</span>
          </div>
          <p class="settings-note">Settings에서도 default branch workflow 설치 순서를 바로 확인할 수 있게 고정했습니다. 두 workflow 파일을 먼저 설치하고 원격 파일 parity와 Actions visibility를 확인한 뒤에만 dispatch gate를 다시 봅니다.</p>
          <dl class="settings-launch-runbook-summary">
            <div><dt>repo</dt><dd>${runbook.repo}</dd></div>
            <div><dt>current action</dt><dd>${runbook.currentLabel}</dd></div>
            <div><dt>remote files</dt><dd>${runbook.remoteWorkflowFilesReady ? "ready" : "action_required"}</dd></div>
            <div><dt>dispatch</dt><dd>${runbook.readyToDispatch ? "safeToDispatch=true" : "withheld"}</dd></div>
            <div><dt>acceptance</dt><dd>${runbook.acceptancePassCount}/5 pass; pending=${runbook.acceptancePendingCount}</dd></div>
            <div><dt>withheld</dt><dd>${runbook.withheldCount} dispatch command${runbook.withheldCount === 1 ? "" : "s"}</dd></div>
          </dl>
          <div class="launch-transition-preview settings-launch-transition" data-settings-launch-transition-preview data-launch-transition-source="${runbook.transitionSource}" data-launch-transition-current-stage="${runbook.transitionCurrentStage}" data-launch-transition-next-stage="${runbook.transitionNextStage}" data-launch-transition-ready="${runbook.readyToDispatch ? "true" : "false"}" data-launch-transition-pending-count="${runbook.transitionPendingCount}" data-launch-transition-withheld-count="${runbook.withheldCount}">
            <div>
              <span>Stage transition preview</span>
              <strong>${runbook.transitionCurrentStage || "current"} -> ${runbook.transitionNextStage}</strong>
              <small>${runbook.readyToDispatch ? "ready after guard" : "conditional next stage"}</small>
            </div>
            <p>${runbook.readyToDispatch ? "safeToDispatch=true가 확인되면 launch proof capture로 넘어갑니다." : "post-install proof가 remoteWorkflowFilesReady=true와 remoteWorkflowVisibilityReady=true를 만들면 dispatch guard recheck로 넘어갑니다."}</p>
            <code data-launch-transition-gate-command>${runbook.transitionGateCommand}</code>
          </div>
          <div class="launch-transition-preview settings-install-verification-matrix" data-settings-install-verification-matrix data-launch-install-verification-source="${runbook.installMatrixSource}" data-launch-install-verification-status="${runbook.installMatrixStatus}" data-launch-install-verification-path-count="${runbook.installMatrixPathCount}" data-launch-install-verification-signal-count="${runbook.installMatrixSignalCount}" data-launch-install-verification-command-count="${runbook.installMatrixCommandCount}" data-launch-install-verification-next-stage="${runbook.installMatrixNextStage}">
            <div>
              <span>Workflow install verification matrix</span>
              <strong>${runbook.installMatrixPathCount} paths -> ${runbook.installMatrixNextStage}</strong>
              <small>${runbook.installMatrixStatus}</small>
            </div>
            <p>Settings runbook는 packet matrix와 같은 기준으로 remoteWorkflowFilesReady=true, remoteWorkflowVisibilityReady=true, dispatchReady=true, driftDispatchReady=true, allDispatchReady=true, verify-launch-handoff reports safeToDispatch=true를 확인합니다.</p>
            <ol>
              ${raw(runbook.installMatrixRows.map((row) => html`
                <li data-settings-install-verification-row data-settings-install-verification-row-key="${row.key || ""}" data-settings-install-verification-row-status="${row.status || ""}">
                  <strong>${row.label || "Install path"}</strong>
                  <span>${row.status || "pending"}</span>
                  <p>${row.guard || runbook.dispatchGuard}</p>
                </li>
              `).join(""))}
            </ol>
            <div class="settings-launch-runbook-signals" data-settings-install-verification-signals>
              ${raw(runbook.installMatrixSignals.map((signal) => html`<span data-settings-install-verification-signal data-settings-install-verification-signal-key="${signal.key || ""}" data-settings-install-verification-signal-status="${signal.status || ""}">${signal.key || signal.label}: ${signal.status || "pending"}</span>`).join(""))}
            </div>
            <code data-settings-install-verification-handoff-command>${runbook.installMatrixHandoffCommand}</code>
          </div>
          <div class="launch-transition-preview settings-remote-workflow-file-ledger" data-settings-remote-workflow-file-ledger data-remote-workflow-file-ledger-source="${runbook.remoteFileLedgerSource}" data-remote-workflow-file-ledger-status="${runbook.remoteFileLedgerStatus}" data-remote-workflow-file-ledger-file-count="${runbook.remoteFileLedgerFileCount}" data-remote-workflow-file-ledger-ready-count="${runbook.remoteFileLedgerReadyCount}" data-remote-workflow-file-ledger-missing-count="${runbook.remoteFileLedgerMissingCount}" data-remote-workflow-file-ledger-mismatch-count="${runbook.remoteFileLedgerMismatchCount}">
            <div>
              <span>Remote workflow file acceptance ledger</span>
              <strong>${runbook.remoteFileLedgerReadyCount}/${runbook.remoteFileLedgerFileCount} files ready</strong>
              <small>${runbook.remoteFileLedgerStatus}</small>
            </div>
            <p>각 workflow 파일을 default branch path, template SHA, remoteExists, remoteMatchesTemplate 기준으로 확인합니다.</p>
            <ol>
              ${raw(runbook.remoteFileLedgerItems.map((item) => html`
                <li data-settings-remote-workflow-file-ledger-item data-remote-workflow-file-key="${item.key || ""}" data-remote-workflow-file-status="${item.status || ""}" data-remote-workflow-file-remote-exists="${item.remoteExists ? "true" : "false"}" data-remote-workflow-file-remote-matches="${item.remoteMatchesTemplate ? "true" : "false"}">
                  <strong>${item.name || item.key}</strong>
                  <span>${item.status || "pending"}</span>
                  <p>${item.path || ""} · templateSha256=${item.templateSha256 || "not available"}</p>
                </li>
              `).join(""))}
            </ol>
            <code data-settings-remote-workflow-file-ledger-verify-command>${runbook.remoteFileLedgerVerifyCommand}</code>
          </div>
          <div class="launch-transition-preview settings-launch-proof-ledger" data-settings-launch-proof-ledger data-launch-proof-ledger-source="${runbook.proofLedgerSource}" data-launch-proof-ledger-status="${runbook.proofLedgerStatus}" data-launch-proof-ledger-required-count="${runbook.proofLedgerRequiredCount}" data-launch-proof-ledger-ready-count="${runbook.proofLedgerReadyCount}" data-launch-proof-ledger-pending-count="${runbook.proofLedgerPendingCount}" data-launch-proof-ledger-current-gate="${runbook.proofLedgerCurrentGate}" data-launch-proof-ledger-deferred-until="${runbook.proofLedgerDeferredUntil}">
            <div>
              <span>Launch proof acceptance ledger</span>
              <strong>${runbook.proofLedgerReadyCount}/${runbook.proofLedgerRequiredCount} proofs ready</strong>
              <small>${runbook.proofLedgerStatus}</small>
            </div>
            <p>dispatch 후 Pages URL/status, Pages/Drift workflow run status/conclusion/url/headSha, evidence freshness, receipt, public claim guard를 모두 확인해야 외부 공개 claim으로 넘어갑니다.</p>
            <ol>
              ${raw(runbook.proofLedgerItems.map((item) => html`
                <li data-settings-launch-proof-ledger-item data-launch-proof-acceptance-key="${item.key || ""}" data-launch-proof-acceptance-status="${item.status || ""}">
                  <strong>${item.label || item.key}</strong>
                  <span>${item.status || "pending"}</span>
                  <p>${item.required || ""}</p>
                </li>
              `).join(""))}
            </ol>
            <code data-settings-launch-proof-ledger-capture-command>${runbook.proofLedgerCaptureCommand}</code>
          </div>
          <ol class="settings-launch-runbook-steps" aria-label="default branch workflow install runbook">
            ${raw(runbook.steps.map((step) => html`
              <li data-settings-launch-runbook-step data-settings-launch-runbook-step-key="${step.key}" data-settings-launch-runbook-step-command="${step.command}" data-settings-launch-runbook-step-target="${step.target}" data-settings-launch-runbook-step-proof="${step.proof}">
                <div>
                  <span>${step.proof}</span>
                  <strong>${step.label}</strong>
                </div>
                <p>${step.detail}</p>
                <code>${step.command || "open GitHub target"}</code>
                ${step.secondaryCommand ? raw(html`<code>${step.secondaryCommand}</code>`) : ""}
                <small>${step.target}</small>
                ${step.url ? raw(html`<a href="${step.url}" target="_blank" rel="noopener" data-settings-launch-runbook-link>open target</a>`) : ""}
              </li>
            `).join(""))}
          </ol>
          <div class="settings-launch-runbook-signals" data-settings-launch-runbook-signals>
            ${raw(runbook.expectedSignals.map((signal) => html`<span data-settings-launch-runbook-signal>${signal}</span>`).join(""))}
          </div>
          <p class="settings-launch-runbook-guard" data-settings-launch-runbook-guard>${runbook.dispatchGuard}</p>
          <div class="post-install-evidence-intake settings-post-install-evidence-intake" data-post-install-evidence-intake data-settings-post-install-evidence-intake data-post-install-evidence-intake-ready="${runbook.postInstallEvidenceIntakeReady ? "true" : "false"}" data-post-install-evidence-intake-status="${runbook.postInstallEvidenceIntakeStatus}" data-post-install-evidence-intake-proof-complete="${runbook.postInstallEvidenceIntakeProofComplete ? "true" : "false"}" data-post-install-evidence-intake-completed-count="${runbook.postInstallEvidenceIntakeCompletedFieldCount}" data-post-install-evidence-intake-command-count="${runbook.postInstallEvidenceIntakeCommands.length}" data-post-install-evidence-intake-signal-count="${runbook.postInstallEvidenceIntakeSignals.length}" data-post-install-evidence-intake-field-count="${runbook.postInstallEvidenceIntakeFields.length}" data-post-install-evidence-intake-field-coverage="${runbook.postInstallEvidenceIntakeFieldCoverage}" data-post-install-evidence-intake-sequence-count="${runbook.postInstallEvidenceIntakeSequence.length}" data-post-install-evidence-intake-sequence-ready="${runbook.postInstallEvidenceIntakeSequenceReady ? "true" : "false"}" data-post-install-evidence-intake-final-command="${runbook.postInstallEvidenceIntakeFinalCommand}" data-post-install-evidence-intake-dispatch-guard="${runbook.dispatchGuard}" data-post-install-quick-proof-ready="${runbook.postInstallQuickProofReady ? "true" : "false"}" data-post-install-quick-proof-step-count="${runbook.postInstallQuickProofStepCount}" data-post-install-quick-proof-coverage="${runbook.postInstallQuickProofCoverage}" data-post-install-quick-proof-final-command="${runbook.postInstallEvidenceIntakeFinalCommand}" data-post-install-quick-proof-field-mapping-ready="${runbook.postInstallQuickProofFieldMappingReady ? "true" : "false"}" data-post-install-quick-proof-field-mapping-coverage="${runbook.postInstallQuickProofFieldMappingCoverage}" data-post-install-quick-proof-mapped-field-count="${runbook.postInstallQuickProofMappedFieldCount}" data-post-install-quick-proof-completed-mapped-field-count="${runbook.postInstallQuickProofCompletedMappedFieldCount}">
            <div class="post-install-evidence-intake-head">
              <span>post-install evidence intake</span>
              <strong>Collect proof before dispatch</strong>
              <p>GitHub UI 설치 직후 이 template에 remote parity, Actions visibility, dispatch guard 결과를 모읍니다. ${runbook.postInstallEvidenceIntakeCompletedFieldCount}/${runbook.postInstallEvidenceIntakeFields.length} fields complete · proofComplete=${runbook.postInstallEvidenceIntakeProofComplete ? "true" : "false"} · safeToDispatch=true 전에는 dispatch하지 않습니다.</p>
            </div>
            <div class="post-install-quick-proof" data-post-install-quick-proof data-post-install-quick-proof-ready="${runbook.postInstallQuickProofReady ? "true" : "false"}" data-post-install-quick-proof-step-count="${runbook.postInstallQuickProofStepCount}" data-post-install-quick-proof-coverage="${runbook.postInstallQuickProofCoverage}">
              <span>Quick proof</span>
              <ol>
                ${raw(runbook.postInstallQuickProofSteps.map((step, index) => html`
                  <li data-post-install-quick-proof-step data-post-install-quick-proof-step-key="${step.key || ""}" data-post-install-quick-proof-step-command="${step.command || ""}" data-post-install-quick-proof-step-expected="${step.expected || ""}" data-post-install-quick-proof-step-field="${step.evidenceFieldKey || ""}">
                    <strong>${index + 1}. ${step.label || step.key}</strong>
                    <code>${step.command || ""}</code>
                    <small>${step.expected || ""}</small>
                  </li>
                `).join(""))}
              </ol>
            </div>
            <div class="post-install-quick-proof-map" data-post-install-quick-proof-field-map data-post-install-quick-proof-field-mapping-ready="${runbook.postInstallQuickProofFieldMappingReady ? "true" : "false"}" data-post-install-quick-proof-field-mapping-coverage="${runbook.postInstallQuickProofFieldMappingCoverage}" data-post-install-quick-proof-mapped-field-count="${runbook.postInstallQuickProofMappedFieldCount}" data-post-install-quick-proof-completed-mapped-field-count="${runbook.postInstallQuickProofCompletedMappedFieldCount}">
              <span>Mapped fields</span>
              <ol>
                ${raw(runbook.postInstallQuickProofFieldMappings.map((item, index) => html`
                  <li data-post-install-quick-proof-field-map-item data-post-install-quick-proof-field-map-step="${item.stepKey || ""}" data-post-install-quick-proof-field-map-field="${item.fieldKey || ""}" data-post-install-quick-proof-field-map-status="${item.fieldStatus || ""}" data-post-install-quick-proof-field-map-completed="${item.fieldCompleted ? "true" : "false"}">
                    <strong>${index + 1}. ${item.stepKey || "step"} -> ${item.fieldLabel || item.fieldKey}</strong>
                    <small>${item.fieldStatus || "missing"} · completed=${item.fieldCompleted ? "true" : "false"}</small>
                    <p>${item.currentValue || ""}</p>
                  </li>
                `).join(""))}
              </ol>
            </div>
            <ol class="post-install-evidence-intake-checklist">
              ${raw(runbook.postInstallEvidenceIntakeChecklist.map((item) => html`<li data-post-install-evidence-intake-check>${item}</li>`).join(""))}
            </ol>
            <dl class="post-install-evidence-intake-fields">
              ${raw(runbook.postInstallEvidenceIntakeFields.map(([label, placeholder]) => html`<div data-post-install-evidence-intake-field data-post-install-evidence-intake-field-label="${label}"><dt>${label}</dt><dd>${placeholder}</dd></div>`).join(""))}
            </dl>
            <div class="post-install-evidence-intake-sequence" data-post-install-evidence-intake-sequence data-post-install-evidence-intake-sequence-count="${runbook.postInstallEvidenceIntakeSequence.length}" data-post-install-evidence-intake-sequence-ready="${runbook.postInstallEvidenceIntakeSequenceReady ? "true" : "false"}">
              <span>Verification sequence</span>
              <ol>
                ${raw(runbook.postInstallEvidenceIntakeSequence.map((step, index) => html`
                  <li data-post-install-evidence-intake-sequence-step data-post-install-evidence-intake-sequence-key="${step.key || ""}" data-post-install-evidence-intake-sequence-command="${step.command || ""}" data-post-install-evidence-intake-sequence-expected="${step.expected || ""}">
                    <strong>${index + 1}. ${step.label || step.key}</strong>
                    <code>${step.command || ""}</code>
                    <small>${step.expected || ""}</small>
                  </li>
                `).join(""))}
              </ol>
            </div>
            <div class="post-install-evidence-intake-commands">
              ${raw(runbook.postInstallEvidenceIntakeCommands.map((command) => html`<code data-post-install-evidence-intake-command>${command}</code>`).join(""))}
            </div>
            <div class="post-install-evidence-intake-signals">
              ${raw(runbook.postInstallEvidenceIntakeSignals.map((signal) => html`<span data-post-install-evidence-intake-signal>${signal}</span>`).join(""))}
            </div>
            <pre data-post-install-evidence-intake-text>${runbook.postInstallEvidenceIntakeText}</pre>
            <button type="button" class="portfolio-export-download portfolio-export-copy" data-action="copy-post-install-evidence-intake" data-post-install-evidence-intake-copy>intake template 복사</button>
            <small class="portfolio-export-status" data-post-install-evidence-intake-copy-status aria-live="polite"></small>
          </div>
        </section>
      `;
    }

    function infoPanelHTML() {
      return html`
        <section class="panel">
          <div class="panel-head"><div><h2>정보</h2></div></div>
          <ul class="settings-info">
            <li><strong>JooPark Workspace</strong> · v3.0 — 개인 관리(일정/할 일/메모/습관/통계) + 프로젝트 · DB 카탈로그</li>
            <li>단축키: <b>⌘K</b> 명령 팔레트 · <b>/</b> 검색 · <b>n</b> 새 항목 · <b>?</b> 도움말 · <b>g+키</b> 화면 이동 · <b>Esc</b> 닫기</li>
            <li>저장 위치: 브라우저 localStorage · 빌드 정적(외부 의존성 없음)</li>
          </ul>
        </section>
      `;
    }

    function renderSettingsHTML(input) {
      const model = settingsViewModel(input);
      return html`
        ${raw(settingsKpisHTML(model))}
        ${raw(profilePanelHTML(model))}
        ${raw(themePanelHTML(model))}
        ${raw(referenceProjectsPanelHTML(model))}
        ${raw(backupPanelHTML(model))}
        ${raw(recentlyDeletedPanelHTML(model))}
        ${raw(handoffPanelHTML(model))}
        ${raw(launchRunbookHTML(model))}
        ${raw(settingsStorageHealthHTML(model.health))}
        ${raw(infoPanelHTML())}
      `;
    }

    return {
      version: VERSION,
      settingsViewModel,
      settingsKpisHTML,
      handoffCardHTML,
      handoffPanelHTML,
      launchRunbookModel,
      launchRunbookHTML,
      renderSettingsHTML,
    };
  }

  root.JooParkSettingsView = {
    version: VERSION,
    create: createSettingsView,
  };
})(window);
