(function (root) {
  "use strict";

  const VERSION = "joopark-operations-copy-actions/v1";

  function createOperationsCopyActions(deps) {
    const options = deps || {};
    const writeClipboardText = typeof options.writeClipboardText === "function"
      ? options.writeClipboardText
      : async () => false;
    const showToast = typeof options.showToast === "function" ? options.showToast : function () {};

    function asArray(value) {
      if (!value) return [];
      return Array.isArray(value) ? value : [value];
    }

    function setDataset(element, keys, value) {
      if (!element) return;
      asArray(keys).forEach((key) => {
        if (key) element.dataset[key] = value;
      });
    }

    function closestPanel(target, selector) {
      return target.closest(selector);
    }

    function panelStatus(panel, selector) {
      return panel ? panel.querySelector(selector) : null;
    }

    function panelText(target, panel, config) {
      if (config.targetTextDatasetKey) return target.dataset[config.targetTextDatasetKey] || "";
      if (!panel) return "";
      return panel.querySelector(config.textSelector || "")?.textContent || "";
    }

    function copyFeedback(copied, config) {
      return {
        state: copied ? "true" : "false",
        statusText: copied ? config.successStatus : config.failureStatus,
        toastText: copied ? config.successToast : config.failureToast,
        toastTone: copied ? "info" : "error",
      };
    }

    function copyConfiguredText(target, data) {
      const config = data || {};
      const panel = closestPanel(target, config.panelSelector || "");
      const status = panelStatus(panel, config.statusSelector || "");
      const text = panelText(target, panel, config);
      writeClipboardText(text).then((copied) => {
        const feedback = copyFeedback(copied, config);
        setDataset(target, config.targetDatasetKeys, feedback.state);
        setDataset(panel, config.panelDatasetKeys, feedback.state);
        if (status) status.textContent = feedback.statusText;
        showToast(feedback.toastText, feedback.toastTone);
      });
    }

    function copySettingsHandoff(target) {
      copyConfiguredText(target, {
        panelSelector: "[data-settings-backup-handoff], [data-settings-deploy-handoff], [data-settings-privacy-handoff]",
        targetTextDatasetKey: "settingsHandoffText",
        statusSelector: "[data-settings-handoff-copy-status]",
        targetDatasetKeys: "settingsHandoffCopied",
        panelDatasetKeys: "settingsHandoffCopied",
        successStatus: "복사됨",
        failureStatus: "복사 실패",
        successToast: "운영 handoff를 복사했습니다",
        failureToast: "복사 실패",
      });
    }

    function copySystemPublishHandoff(target) {
      copyConfiguredText(target, {
        panelSelector: "[data-system-publish-handoff]",
        targetTextDatasetKey: "systemPublishHandoffText",
        statusSelector: "[data-system-publish-handoff-copy-status]",
        targetDatasetKeys: "systemPublishHandoffCopied",
        panelDatasetKeys: "systemPublishHandoffCopied",
        successStatus: "복사됨",
        failureStatus: "복사 실패",
        successToast: "publish unblock handoff를 복사했습니다",
        failureToast: "복사 실패",
      });
    }

    function copyPublishEvidenceShareUpdate(target) {
      copyConfiguredText(target, {
        panelSelector: "[data-publish-evidence-share-update]",
        textSelector: "[data-publish-evidence-share-update-text]",
        statusSelector: "[data-publish-evidence-share-update-copy-status]",
        targetDatasetKeys: "publishEvidenceShareUpdateCopied",
        panelDatasetKeys: "publishEvidenceShareUpdateCopied",
        successStatus: "share update 복사됨",
        failureStatus: "share update 복사 실패",
        successToast: "publish evidence share update를 복사했습니다",
        failureToast: "publish evidence share update 복사 실패",
      });
    }

    function copyPublishLaunchAnnouncement(target) {
      copyConfiguredText(target, {
        panelSelector: "[data-publish-evidence-launch-announcement]",
        textSelector: "[data-publish-evidence-launch-announcement-text]",
        statusSelector: "[data-publish-evidence-launch-announcement-copy-status]",
        targetDatasetKeys: "publishLaunchAnnouncementCopied",
        panelDatasetKeys: "publishLaunchAnnouncementCopied",
        successStatus: "launch announcement 복사됨",
        failureStatus: "launch announcement 복사 실패",
        successToast: "publish launch announcement을 복사했습니다",
        failureToast: "publish launch announcement 복사 실패",
      });
    }

    function copyPublishPostLaunchReceipt(target) {
      copyConfiguredText(target, {
        panelSelector: "[data-publish-evidence-post-launch-receipt]",
        textSelector: "[data-publish-evidence-post-launch-receipt-text]",
        statusSelector: "[data-publish-evidence-post-launch-receipt-copy-status]",
        targetDatasetKeys: "publishPostLaunchReceiptCopied",
        panelDatasetKeys: "publishPostLaunchReceiptCopied",
        successStatus: "post-launch receipt 복사됨",
        failureStatus: "post-launch receipt 복사 실패",
        successToast: "publish post-launch receipt를 복사했습니다",
        failureToast: "publish post-launch receipt 복사 실패",
      });
    }

    function copyPublishLaunchProofReceipt(target) {
      copyConfiguredText(target, {
        panelSelector: "[data-publish-evidence-launch-proof-receipt]",
        textSelector: "[data-publish-evidence-launch-proof-receipt-text]",
        statusSelector: "[data-publish-evidence-launch-proof-receipt-copy-status]",
        targetDatasetKeys: "publishLaunchProofReceiptCopied",
        panelDatasetKeys: "publishLaunchProofReceiptCopied",
        successStatus: "launch proof receipt 복사됨",
        failureStatus: "launch proof receipt 복사 실패",
        successToast: "launch proof evidence receipt를 복사했습니다",
        failureToast: "launch proof evidence receipt 복사 실패",
      });
    }

    function copyRemoteWorkflowInstallPacket(target) {
      copyConfiguredText(target, {
        panelSelector: "[data-remote-workflow-install-packet]",
        textSelector: "[data-remote-workflow-install-packet-text]",
        statusSelector: "[data-remote-workflow-install-packet-copy-status]",
        targetDatasetKeys: "remoteWorkflowInstallPacketCopied",
        panelDatasetKeys: "remoteWorkflowInstallPacketCopied",
        successStatus: "install packet 복사됨",
        failureStatus: "install packet 복사 실패",
        successToast: "remote workflow install packet을 복사했습니다",
        failureToast: "remote workflow install packet 복사 실패",
      });
    }

    function copyWorkflowUiInstallReceipt(target) {
      copyConfiguredText(target, {
        panelSelector: "[data-workflow-ui-install-receipt]",
        textSelector: "[data-workflow-ui-install-receipt-text]",
        statusSelector: "[data-workflow-ui-install-receipt-copy-status]",
        targetDatasetKeys: ["workflowUiInstallReceiptCopied", "workflowUiInstallPastePacketCopied"],
        panelDatasetKeys: ["workflowUiInstallReceiptCopied", "workflowUiInstallPastePacketCopied"],
        successStatus: "UI paste packet 복사됨",
        failureStatus: "UI paste packet 복사 실패",
        successToast: "workflow UI paste packet을 복사했습니다",
        failureToast: "workflow UI paste packet 복사 실패",
      });
    }

    function copyHomeLaunchBlockerResolver(target) {
      copyConfiguredText(target, {
        panelSelector: "[data-home-launch-blocker-resolver]",
        textSelector: "[data-home-launch-blocker-resolver-text]",
        statusSelector: "[data-home-launch-blocker-resolver-copy-status]",
        targetDatasetKeys: "homeLaunchBlockerResolverCopied",
        panelDatasetKeys: "homeLaunchBlockerResolverCopied",
        successStatus: "resolver 복사됨",
        failureStatus: "resolver 복사 실패",
        successToast: "launch blocker resolver를 복사했습니다",
        failureToast: "launch blocker resolver 복사 실패",
      });
    }

    function copyHomeLaunchActionChecklist(target) {
      copyConfiguredText(target, {
        panelSelector: "[data-home-launch-action-checklist]",
        textSelector: "[data-home-launch-action-checklist-text]",
        statusSelector: "[data-home-launch-action-checklist-copy-status]",
        targetDatasetKeys: "homeLaunchActionChecklistCopied",
        panelDatasetKeys: "homeLaunchActionChecklistCopied",
        successStatus: "checklist 복사됨",
        failureStatus: "checklist 복사 실패",
        successToast: "launch action checklist를 복사했습니다",
        failureToast: "launch action checklist 복사 실패",
      });
    }

    function copyPostInstallEvidenceIntake(target) {
      copyConfiguredText(target, {
        panelSelector: "[data-post-install-evidence-intake]",
        textSelector: "[data-post-install-evidence-intake-text]",
        statusSelector: "[data-post-install-evidence-intake-copy-status]",
        targetDatasetKeys: "postInstallEvidenceIntakeCopied",
        panelDatasetKeys: "postInstallEvidenceIntakeCopied",
        successStatus: "post-install intake 복사됨",
        failureStatus: "post-install intake 복사 실패",
        successToast: "post-install evidence intake를 복사했습니다",
        failureToast: "post-install evidence intake 복사 실패",
      });
    }

    function copyPublishWorkflowScopePacket(target) {
      copyConfiguredText(target, {
        panelSelector: "[data-publish-dispatch-workflow-scope-packet]",
        textSelector: "[data-publish-dispatch-workflow-scope-packet-text]",
        statusSelector: "[data-publish-dispatch-workflow-scope-packet-copy-status]",
        targetDatasetKeys: "publishDispatchWorkflowScopePacketCopied",
        panelDatasetKeys: "publishDispatchWorkflowScopePacketCopied",
        successStatus: "scope packet 복사됨",
        failureStatus: "scope packet 복사 실패",
        successToast: "workflow scope refresh packet을 복사했습니다",
        failureToast: "workflow scope refresh packet 복사 실패",
      });
    }

    function copyLaunchExecutionPacket(target) {
      copyConfiguredText(target, {
        panelSelector: "[data-launch-execution-packet-copy-card]",
        textSelector: "[data-launch-execution-packet-text]",
        statusSelector: "[data-launch-execution-packet-copy-status]",
        targetDatasetKeys: "launchExecutionPacketCopied",
        panelDatasetKeys: "launchExecutionPacketCopied",
        successStatus: "launch packet 복사됨",
        failureStatus: "launch packet 복사 실패",
        successToast: "launch execution packet을 복사했습니다",
        failureToast: "launch execution packet 복사 실패",
      });
    }

    function copyLaunchCurrentActionPacket(target) {
      copyConfiguredText(target, {
        panelSelector: "[data-launch-execution-current-action]",
        textSelector: "[data-launch-execution-current-action-text]",
        statusSelector: "[data-launch-execution-current-action-copy-status]",
        targetDatasetKeys: "launchExecutionCurrentActionCopied",
        panelDatasetKeys: "launchExecutionCurrentActionCopied",
        successStatus: "current action 복사됨",
        failureStatus: "current action 복사 실패",
        successToast: "launch current action packet을 복사했습니다",
        failureToast: "launch current action packet 복사 실패",
      });
    }

    function copyLaunchOperatorOnePage(target) {
      copyConfiguredText(target, {
        panelSelector: "[data-launch-operator-one-page]",
        textSelector: "[data-launch-operator-one-page-text]",
        statusSelector: "[data-launch-operator-one-page-copy-status]",
        targetDatasetKeys: "launchOperatorOnePageCopied",
        panelDatasetKeys: "launchOperatorOnePageCopied",
        successStatus: "one-page 복사됨",
        failureStatus: "one-page 복사 실패",
        successToast: "launch operator one-page handoff를 복사했습니다",
        failureToast: "launch operator one-page handoff 복사 실패",
      });
    }

    function copyLaunchReadinessRefreshReceipt(target) {
      copyConfiguredText(target, {
        panelSelector: "[data-launch-readiness-refresh-receipt]",
        textSelector: "[data-launch-readiness-refresh-receipt-text]",
        statusSelector: "[data-launch-readiness-refresh-receipt-copy-status]",
        targetDatasetKeys: "launchReadinessRefreshReceiptCopied",
        panelDatasetKeys: "launchReadinessRefreshReceiptCopied",
        successStatus: "readiness receipt 복사됨",
        failureStatus: "readiness receipt 복사 실패",
        successToast: "launch readiness refresh receipt를 복사했습니다",
        failureToast: "launch readiness refresh receipt 복사 실패",
      });
    }

    function copyVerifyWorkspaceSummaryReceipt(target) {
      copyConfiguredText(target, {
        panelSelector: "[data-verify-workspace-summary-receipt]",
        textSelector: "[data-verify-workspace-summary-receipt-text]",
        statusSelector: "[data-verify-workspace-summary-receipt-copy-status]",
        targetDatasetKeys: "verifyWorkspaceSummaryReceiptCopied",
        panelDatasetKeys: "verifyWorkspaceSummaryReceiptCopied",
        successStatus: "verify receipt 복사됨",
        failureStatus: "verify receipt 복사 실패",
        successToast: "verify workspace summary receipt를 복사했습니다",
        failureToast: "verify receipt 복사 실패",
      });
    }

    function copyOutputQualityAuditReceipt(target) {
      copyConfiguredText(target, {
        panelSelector: "[data-output-quality-audit-receipt]",
        textSelector: "[data-output-quality-audit-receipt-text]",
        statusSelector: "[data-output-quality-audit-receipt-copy-status]",
        targetDatasetKeys: "outputQualityAuditReceiptCopied",
        panelDatasetKeys: "outputQualityAuditReceiptCopied",
        successStatus: "quality receipt 복사됨",
        failureStatus: "quality receipt 복사 실패",
        successToast: "output quality audit receipt를 복사했습니다",
        failureToast: "output quality audit receipt 복사 실패",
      });
    }

    function copyOutputQualityExternalClaimGuard(target) {
      copyConfiguredText(target, {
        panelSelector: "[data-output-quality-audit-external-claim-guard]",
        textSelector: "[data-output-quality-audit-external-claim-guard-text]",
        statusSelector: "[data-output-quality-audit-external-claim-guard-copy-status]",
        targetDatasetKeys: "outputQualityExternalClaimGuardCopied",
        panelDatasetKeys: "outputQualityExternalClaimGuardCopied",
        successStatus: "external claim guard 복사됨",
        failureStatus: "external claim guard 복사 실패",
        successToast: "external completion claim guard를 복사했습니다",
        failureToast: "external completion claim guard 복사 실패",
      });
    }

    return {
      version: VERSION,
      copyConfiguredText,
      copySettingsHandoff,
      copySystemPublishHandoff,
      copyPublishEvidenceShareUpdate,
      copyPublishLaunchAnnouncement,
      copyPublishPostLaunchReceipt,
      copyPublishLaunchProofReceipt,
      copyRemoteWorkflowInstallPacket,
      copyWorkflowUiInstallReceipt,
      copyHomeLaunchBlockerResolver,
      copyHomeLaunchActionChecklist,
      copyPostInstallEvidenceIntake,
      copyPublishWorkflowScopePacket,
      copyLaunchExecutionPacket,
      copyLaunchCurrentActionPacket,
      copyLaunchOperatorOnePage,
      copyLaunchReadinessRefreshReceipt,
      copyVerifyWorkspaceSummaryReceipt,
      copyOutputQualityAuditReceipt,
      copyOutputQualityExternalClaimGuard,
    };
  }

  root.JooParkOperationsCopyActions = {
    version: VERSION,
    create: createOperationsCopyActions,
  };
})(window);
