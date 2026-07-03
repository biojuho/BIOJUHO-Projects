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

    function copyFeedback(copied, messages) {
      return {
        state: copied ? "true" : "false",
        statusText: copied ? messages.successStatus : messages.failureStatus,
        toastText: copied ? messages.successToast : messages.failureToast,
        toastTone: copied ? "info" : "error",
      };
    }

    function configuredCopyFeedback(copied, config) {
      return copyFeedback(copied, config);
    }

    function copyReviewPackagePasteBody(target) {
      const item = closestPanel(target, "[data-review-package-paste-preview-item]");
      const panel = closestPanel(target, "[data-review-package-paste-preview]");
      const text = panelText(item, "[data-review-package-paste-preview-body]");
      const status = panelStatus(item, "[data-review-package-paste-preview-copy-status]");
      writeClipboardText(text).then((copied) => {
        const feedback = copyFeedback(copied, {
          successStatus: "본문 복사됨",
          failureStatus: "본문 복사 실패",
          successToast: "paste body를 복사했습니다",
          failureToast: "paste body 복사 실패",
        });
        setDataset(target, "reviewPackagePastePreviewCopied", feedback.state);
        setDataset(item, "reviewPackagePastePreviewCopied", feedback.state);
        setDataset(panel, "reviewPackagePastePreviewCopied", feedback.state);
        if (status) status.textContent = feedback.statusText;
        showToast(feedback.toastText, feedback.toastTone);
      });
    }

    function copyReviewPackagePanelText(target, data) {
      const config = data || {};
      const panel = closestPanel(target, config.panelSelector || "");
      const text = panelText(panel, config.textSelector || "");
      const status = panelStatus(panel, config.statusSelector || "");
      writeClipboardText(text).then((copied) => {
        const feedback = configuredCopyFeedback(copied, config);
        setDataset(target, config.targetDatasetKey, feedback.state);
        setDataset(panel, config.panelDatasetKey, feedback.state);
        if (status) status.textContent = feedback.statusText;
        showToast(feedback.toastText, feedback.toastTone);
      });
    }

    function copyReviewArtifactReceipt(target) {
      const panel = closestPanel(target, "[data-review-artifact-diff]");
      const text = panelText(panel, "[data-review-artifact-receipt-text]");
      const status = panelStatus(panel, "[data-review-artifact-receipt-copy-status]");
      writeClipboardText(text).then((copied) => {
        const feedback = copyFeedback(copied, {
          successStatus: "receipt 복사됨",
          failureStatus: "receipt 복사 실패",
          successToast: "artifact receipt를 복사했습니다",
          failureToast: "receipt 복사 실패",
        });
        setDataset(target, "reviewArtifactReceiptCopied", feedback.state);
        setDataset(panel, "reviewArtifactReceiptCopied", feedback.state);
        if (status) status.textContent = feedback.statusText;
        showToast(feedback.toastText, feedback.toastTone);
      });
    }

    function copyReviewArtifactRepairPayload(target, kind) {
      const panel = closestPanel(target, "[data-review-artifact-diff]");
      const isBody = kind === "body";
      const selector = isBody ? "[data-review-artifact-repair-body-text]" : "[data-review-artifact-repair-receipt-text]";
      const text = panelText(panel, selector);
      const status = panelStatus(panel, "[data-review-artifact-repair-copy-status]");
      writeClipboardText(text).then((copied) => {
        const feedback = copyFeedback(copied, {
          successStatus: isBody ? "archived body 복사됨" : "fresh receipt 복사됨",
          failureStatus: "repair 복사 실패",
          successToast: "repair payload를 복사했습니다",
          failureToast: "repair 복사 실패",
        });
        const key = isBody ? "reviewArtifactRepairBodyCopied" : "reviewArtifactRepairReceiptCopied";
        setDataset(target, key, feedback.state);
        setDataset(panel, key, feedback.state);
        if (status) status.textContent = feedback.statusText;
        showToast(feedback.toastText, feedback.toastTone);
      });
    }

    function copyIssueFreshReceipt(target) {
      const panel = closestPanel(target, "[data-issue-fresh-receipt]");
      const text = panelText(panel, "[data-issue-fresh-receipt-text]");
      const status = panelStatus(panel, "[data-issue-fresh-receipt-copy-status]");
      writeClipboardText(text).then((copied) => {
        const feedback = copyFeedback(copied, {
          successStatus: "fresh receipt 복사됨",
          failureStatus: "fresh receipt 복사 실패",
          successToast: "fresh receipt를 복사했습니다",
          failureToast: "fresh receipt 복사 실패",
        });
        setDataset(target, "issueFreshReceiptCopied", feedback.state);
        setDataset(panel, "issueFreshReceiptCopied", feedback.state);
        if (status) status.textContent = feedback.statusText;
        showToast(feedback.toastText, feedback.toastTone);
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
        const feedback = copyFeedback(copied, {
          successStatus: "post-apply fresh receipt 복사됨",
          failureStatus: "fresh receipt 복사 실패",
          successToast: "post-apply fresh receipt를 복사했습니다",
          failureToast: "fresh receipt 복사 실패",
        });
        setDataset(target, "reviewArtifactPostApplyReceiptCopied", feedback.state);
        setDataset(panel, "reviewArtifactPostApplyReceiptCopied", feedback.state);
        if (status) status.textContent = feedback.statusText;
        showToast(feedback.toastText, feedback.toastTone);
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
        const feedback = copyFeedback(copied, {
          successStatus: "link receipt 복사됨",
          failureStatus: "link receipt 복사 실패",
          successToast: "post-repair artifact link를 복사했습니다",
          failureToast: "link receipt 복사 실패",
        });
        setDataset(target, "reviewPostRepairArtifactLinkCopied", feedback.state);
        setDataset(panel, "reviewPostRepairArtifactLinkCopied", feedback.state);
        if (status) status.textContent = feedback.statusText;
        showToast(feedback.toastText, feedback.toastTone);
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
