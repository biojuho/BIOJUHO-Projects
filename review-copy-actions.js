(function (root) {
  "use strict";

  const VERSION = "joopark-review-copy-actions/v1";

  function createReviewCopyActions(deps) {
    const options = deps || {};
    const writeClipboardText = typeof options.writeClipboardText === "function"
      ? options.writeClipboardText
      : async () => false;
    const showToast = typeof options.showToast === "function" ? options.showToast : function () {};

    function setDataset(element, key, value) {
      if (element && key) element.dataset[key] = value;
    }

    function closestPanel(target, selector) {
      return target.closest(selector);
    }

    function panelText(panel, selector) {
      return panel ? panel.querySelector(selector)?.textContent || "" : "";
    }

    function panelStatus(panel, selector) {
      return panel ? panel.querySelector(selector) : null;
    }

    function copyReviewPackagePasteBody(target) {
      const item = closestPanel(target, "[data-review-package-paste-preview-item]");
      const panel = closestPanel(target, "[data-review-package-paste-preview]");
      const text = panelText(item, "[data-review-package-paste-preview-body]");
      const status = panelStatus(item, "[data-review-package-paste-preview-copy-status]");
      writeClipboardText(text).then((copied) => {
        const state = copied ? "true" : "false";
        setDataset(target, "reviewPackagePastePreviewCopied", state);
        setDataset(item, "reviewPackagePastePreviewCopied", state);
        setDataset(panel, "reviewPackagePastePreviewCopied", state);
        if (status) status.textContent = copied ? "본문 복사됨" : "본문 복사 실패";
        showToast(copied ? "paste body를 복사했습니다" : "paste body 복사 실패", copied ? "info" : "error");
      });
    }

    function copyReviewPackagePanelText(target, data) {
      const config = data || {};
      const panel = closestPanel(target, config.panelSelector || "");
      const text = panelText(panel, config.textSelector || "");
      const status = panelStatus(panel, config.statusSelector || "");
      writeClipboardText(text).then((copied) => {
        const state = copied ? "true" : "false";
        setDataset(target, config.targetDatasetKey, state);
        setDataset(panel, config.panelDatasetKey, state);
        if (status) status.textContent = copied ? config.successStatus : config.failureStatus;
        showToast(copied ? config.successToast : config.failureToast, copied ? "info" : "error");
      });
    }

    function copyReviewArtifactReceipt(target) {
      const panel = closestPanel(target, "[data-review-artifact-diff]");
      const text = panelText(panel, "[data-review-artifact-receipt-text]");
      const status = panelStatus(panel, "[data-review-artifact-receipt-copy-status]");
      writeClipboardText(text).then((copied) => {
        const state = copied ? "true" : "false";
        setDataset(target, "reviewArtifactReceiptCopied", state);
        setDataset(panel, "reviewArtifactReceiptCopied", state);
        if (status) status.textContent = copied ? "receipt 복사됨" : "receipt 복사 실패";
        showToast(copied ? "artifact receipt를 복사했습니다" : "receipt 복사 실패", copied ? "info" : "error");
      });
    }

    function copyReviewArtifactRepairPayload(target, kind) {
      const panel = closestPanel(target, "[data-review-artifact-diff]");
      const isBody = kind === "body";
      const selector = isBody ? "[data-review-artifact-repair-body-text]" : "[data-review-artifact-repair-receipt-text]";
      const text = panelText(panel, selector);
      const status = panelStatus(panel, "[data-review-artifact-repair-copy-status]");
      writeClipboardText(text).then((copied) => {
        const state = copied ? "true" : "false";
        const key = isBody ? "reviewArtifactRepairBodyCopied" : "reviewArtifactRepairReceiptCopied";
        setDataset(target, key, state);
        setDataset(panel, key, state);
        if (status) status.textContent = copied
          ? (isBody ? "archived body 복사됨" : "fresh receipt 복사됨")
          : "repair 복사 실패";
        showToast(copied ? "repair payload를 복사했습니다" : "repair 복사 실패", copied ? "info" : "error");
      });
    }

    function copyIssueFreshReceipt(target) {
      const panel = closestPanel(target, "[data-issue-fresh-receipt]");
      const text = panelText(panel, "[data-issue-fresh-receipt-text]");
      const status = panelStatus(panel, "[data-issue-fresh-receipt-copy-status]");
      writeClipboardText(text).then((copied) => {
        const state = copied ? "true" : "false";
        setDataset(target, "issueFreshReceiptCopied", state);
        setDataset(panel, "issueFreshReceiptCopied", state);
        if (status) status.textContent = copied ? "fresh receipt 복사됨" : "fresh receipt 복사 실패";
        showToast(copied ? "fresh receipt를 복사했습니다" : "fresh receipt 복사 실패", copied ? "info" : "error");
      });
    }

    function copyReviewArtifactPostApplyReceipt(target) {
      const panel = closestPanel(target, "[data-review-artifact-post-apply-receipt]");
      const ready = panel && panel.dataset.reviewArtifactPostApplyReceiptReady === "true";
      const text = panelText(panel, "[data-review-artifact-post-apply-receipt-text]");
      const status = panelStatus(panel, "[data-review-artifact-post-apply-receipt-copy-status]");
      if (!ready || !text.trim()) {
        setDataset(target, "reviewArtifactPostApplyReceiptCopied", "false");
        setDataset(panel, "reviewArtifactPostApplyReceiptCopied", "false");
        if (status) status.textContent = "pass receipt 대기";
        showToast("pass 상태의 fresh receipt가 아직 준비되지 않았습니다", "warn");
        return;
      }
      writeClipboardText(text).then((copied) => {
        const state = copied ? "true" : "false";
        setDataset(target, "reviewArtifactPostApplyReceiptCopied", state);
        setDataset(panel, "reviewArtifactPostApplyReceiptCopied", state);
        if (status) status.textContent = copied ? "post-apply fresh receipt 복사됨" : "fresh receipt 복사 실패";
        showToast(copied ? "post-apply fresh receipt를 복사했습니다" : "fresh receipt 복사 실패", copied ? "info" : "error");
      });
    }

    function copyReviewPostRepairArtifactLink(target) {
      const panel = closestPanel(target, "[data-review-post-repair-artifact-link]");
      const ready = panel && panel.dataset.reviewPostRepairArtifactLinkReady === "true";
      const text = panelText(panel, "[data-review-post-repair-artifact-link-text]");
      const status = panelStatus(panel, "[data-review-post-repair-artifact-link-copy-status]");
      if (!ready || !text.trim()) {
        setDataset(target, "reviewPostRepairArtifactLinkCopied", "false");
        setDataset(panel, "reviewPostRepairArtifactLinkCopied", "false");
        if (status) status.textContent = "pass artifact link 대기";
        showToast("post-repair artifact link가 아직 pass 상태가 아닙니다", "warn");
        return;
      }
      writeClipboardText(text).then((copied) => {
        const state = copied ? "true" : "false";
        setDataset(target, "reviewPostRepairArtifactLinkCopied", state);
        setDataset(panel, "reviewPostRepairArtifactLinkCopied", state);
        if (status) status.textContent = copied ? "link receipt 복사됨" : "link receipt 복사 실패";
        showToast(copied ? "post-repair artifact link를 복사했습니다" : "link receipt 복사 실패", copied ? "info" : "error");
      });
    }

    return {
      version: VERSION,
      copyReviewPackagePasteBody,
      copyReviewPackagePanelText,
      copyReviewArtifactReceipt,
      copyReviewArtifactRepairPayload,
      copyIssueFreshReceipt,
      copyReviewArtifactPostApplyReceipt,
      copyReviewPostRepairArtifactLink,
    };
  }

  root.JooParkReviewCopyActions = {
    version: VERSION,
    create: createReviewCopyActions,
  };
})(window);
