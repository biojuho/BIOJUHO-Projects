(function (root) {
  "use strict";

  const VERSION = "joopark-review-submission-copy/v1";

  function createReviewSubmissionCopy(deps) {
    const options = deps || {};
    const writeClipboardText = typeof options.writeClipboardText === "function"
      ? options.writeClipboardText
      : async () => false;
    const showToast = typeof options.showToast === "function" ? options.showToast : function () {};

    function setDataset(element, key, value) {
      if (element && key) element.dataset[key] = value;
    }

    function submissionPanel(target) {
      return target.closest("[data-review-package-external-receipt-template]");
    }

    function panelQuery(panel, selector) {
      return panel && selector ? panel.querySelector(selector) : null;
    }

    function panelText(panel, selector) {
      return panelQuery(panel, selector)?.textContent || "";
    }

    function externalReceiptInputValue(panel, selector) {
      const input = panelQuery(panel, selector);
      return input ? String(input.value || "").trim() : "";
    }

    function externalReceiptSubmittedAt(value) {
      if (value) return value;
      try {
        return new Date().toISOString();
      } catch (_) {
        return "missing submitted timestamp";
      }
    }

    function externalReceiptValues(panel) {
      const externalUrl = externalReceiptInputValue(panel, "[data-review-package-external-receipt-url]");
      const externalId = externalReceiptInputValue(panel, "[data-review-package-external-receipt-id]");
      const submittedAt = externalReceiptSubmittedAt(externalReceiptInputValue(panel, "[data-review-package-external-receipt-submitted-at]"));
      return { externalUrl, externalId, submittedAt };
    }

    function fillExternalIssueText(template, values) {
      const data = values || {};
      const externalUrl = data.externalUrl || "[paste issue URL]";
      const externalId = data.externalId || "[paste issue ID]";
      const submittedAt = data.submittedAt || "[paste timestamp after creation]";
      return String(template || "")
        .replace("Status: ready after external issue URL/ID", "Status: submitted")
        .replace("External issue URL: [paste after creation]", `External issue URL: ${externalUrl}`)
        .replace("External issue ID: [paste after creation]", `External issue ID: ${externalId}`)
        .replace("External issue: [paste issue ID] — [paste issue URL]", `External issue: ${externalId} — ${externalUrl}`)
        .replaceAll("Submitted artifact: [paste issue ID] — [paste issue URL]", `Submitted artifact: ${externalId} — ${externalUrl}`)
        .replace("Submitted at: [paste timestamp after creation]", `Submitted at: ${submittedAt}`)
        .replace("Next action: After external issue URL/ID are filled, post the GitHub comment body, pin the workspace note, and retain the package bundle proof.", "Next action: Post the GitHub comment body, pin the workspace note, and retain the package bundle proof.");
    }

    function copyReviewPackageFilledText(target, options) {
      const data = options || {};
      const panel = submissionPanel(target);
      const stateHost = data.stateHostSelector ? panelQuery(panel, data.stateHostSelector) : panel;
      const templateHost = data.templateHostSelector ? panelQuery(panel, data.templateHostSelector) : panel;
      const status = panelQuery(panel, data.statusSelector || "");
      const template = panelText(templateHost, data.textSelector || "");
      const values = externalReceiptValues(panel);
      if (!(values.externalUrl && values.externalId)) {
        setDataset(target, data.targetDatasetKey, "false");
        setDataset(stateHost, data.stateDatasetKey, "false");
        if (status) status.textContent = data.requiredStatus || "URL/ID 필요";
        showToast(data.requiredToast || "external issue URL과 ID를 먼저 입력하세요", "warn");
        return;
      }
      const text = fillExternalIssueText(template, values);
      writeClipboardText(text).then((copied) => {
        const state = copied ? "true" : "false";
        setDataset(target, data.targetDatasetKey, state);
        setDataset(stateHost, data.stateDatasetKey, state);
        if (status) status.textContent = copied ? data.successStatus : data.failureStatus;
        showToast(copied ? data.successToast : data.failureToast, copied ? "info" : "error");
      });
    }

    function copyReviewPackageExternalReceiptFilled(target) {
      copyReviewPackageFilledText(target, {
        textSelector: "[data-review-package-external-receipt-template-body]",
        statusSelector: "[data-review-package-external-receipt-filled-copy-status]",
        targetDatasetKey: "reviewPackageExternalReceiptFilledCopied",
        stateDatasetKey: "reviewPackageExternalReceiptFilledCopied",
        successStatus: "완성 receipt 복사됨",
        failureStatus: "완성 receipt 복사 실패",
        successToast: "완성 external receipt를 복사했습니다",
        failureToast: "완성 external receipt 복사 실패",
      });
    }

    function copyReviewPackageSubmissionUpdateFilled(target) {
      copyReviewPackageFilledText(target, {
        stateHostSelector: "[data-review-package-submission-update]",
        templateHostSelector: "[data-review-package-submission-update]",
        textSelector: "[data-review-package-submission-update-body]",
        statusSelector: "[data-review-package-submission-update-filled-copy-status]",
        targetDatasetKey: "reviewPackageSubmissionUpdateFilledCopied",
        stateDatasetKey: "reviewPackageSubmissionUpdateFilledCopied",
        successStatus: "최종 update 복사됨",
        failureStatus: "최종 update 복사 실패",
        successToast: "review submission update를 복사했습니다",
        failureToast: "review submission update 복사 실패",
      });
    }

    return {
      version: VERSION,
      externalReceiptInputValue,
      externalReceiptSubmittedAt,
      externalReceiptValues,
      fillExternalIssueText,
      copyReviewPackageFilledText,
      copyReviewPackageExternalReceiptFilled,
      copyReviewPackageSubmissionUpdateFilled,
    };
  }

  root.JooParkReviewSubmissionCopy = {
    version: VERSION,
    create: createReviewSubmissionCopy,
  };
})(window);
