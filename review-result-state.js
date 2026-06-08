(function (root) {
  "use strict";

  const VERSION = "joopark-review-result-state/v1";
  const VALIDATOR_SELECTOR = "[data-review-result-validator]";
  const INPUT_SELECTOR = "[data-review-result-input]";
  const STATUS_SELECTOR = "[data-review-result-status]";
  const OUTPUT_SELECTOR = "[data-review-result-output]";

  function createReviewResultState(deps) {
    const options = deps || {};
    const nodeQuery = options.nodeQuery;
    const nodeText = options.nodeText;
    const setHTML = options.setHTML;
    const copyTextWithStatus = options.copyTextWithStatus;
    const nowISO = options.nowISO;
    const clampText = options.clampText;
    const clampTextArray = options.clampTextArray;
    const normalizeAllData = options.normalizeAllData;
    const persist = options.persist;
    const renderSavedReviewResult = options.renderSavedReviewResult;
    const refreshReviewIssueDraftFromSavedResult = options.refreshReviewIssueDraftFromSavedResult;
    const repairReceiptMarkdown = options.repairReceiptMarkdown;
    const validationOutputHTML = options.validationOutputHTML;
    const repairSnapshots = new WeakMap();

    if (
      typeof nodeQuery !== "function" ||
      typeof nodeText !== "function" ||
      typeof setHTML !== "function" ||
      typeof copyTextWithStatus !== "function" ||
      typeof nowISO !== "function" ||
      typeof clampText !== "function" ||
      typeof clampTextArray !== "function" ||
      typeof normalizeAllData !== "function" ||
      typeof persist !== "function" ||
      typeof renderSavedReviewResult !== "function" ||
      typeof refreshReviewIssueDraftFromSavedResult !== "function" ||
      typeof repairReceiptMarkdown !== "function" ||
      typeof validationOutputHTML !== "function"
    ) {
      throw new Error("review result state helper requires DOM, persistence, and view dependencies");
    }

    function validatorNode(target) {
      return target ? target.closest(VALIDATOR_SELECTOR) : null;
    }

    function validatorInput(validator) {
      return nodeQuery(validator, INPUT_SELECTOR);
    }

    function validatorStatus(validator) {
      return nodeQuery(validator, STATUS_SELECTOR);
    }

    function validatorOutput(validator) {
      return nodeQuery(validator, OUTPUT_SELECTOR);
    }

    function recordRepairSnapshot(validator, state, message, details) {
      if (!validator) return;
      if (state === "empty") {
        repairSnapshots.delete(validator);
        return;
      }
      if (state !== "fail") return;
      repairSnapshots.set(validator, {
        state,
        message,
        expectedKey: validator.dataset.reviewResultPrimaryKey || "",
        reviewType: validator.dataset.reviewResultType || "",
        capturedAt: nowISO(),
        failures: Array.isArray(details && details.failures) ? details.failures : [],
        warnings: Array.isArray(details && details.warnings) ? details.warnings : [],
      });
    }

    function postRepairReceiptModel(validator, result, warnings, saved) {
      const previous = validator ? repairSnapshots.get(validator) : null;
      if (!previous) return null;
      return {
        previous,
        result: result || {},
        warnings: Array.isArray(warnings) ? warnings : [],
        saved: saved || {},
        expectedKey: validator.dataset.reviewResultPrimaryKey || previous.expectedKey || "",
        reviewType: validator.dataset.reviewResultType || previous.reviewType || "",
        repairedAt: nowISO(),
      };
    }

    function attachRepairReceipt(validator, saved, result, warnings) {
      if (!saved) return null;
      const model = postRepairReceiptModel(validator, result, warnings, saved);
      if (!model) return null;
      const previousFailures = Array.isArray(model.previous.failures) ? model.previous.failures : [];
      const previousWarnings = Array.isArray(model.previous.warnings) ? model.previous.warnings : [];
      const markdown = repairReceiptMarkdown(model);
      saved.repairReceiptReady = true;
      saved.repairReceiptAt = model.repairedAt;
      saved.repairReceiptPreviousFailureCount = previousFailures.length;
      saved.repairReceiptPreviousWarningCount = previousWarnings.length;
      saved.repairReceiptMarkdown = clampText(markdown, 16000);
      saved.postRepairReceipt = saved.repairReceiptMarkdown;
      saved.repairEvidence = {
        status: "repaired-validation-pass",
        reviewType: model.reviewType || saved.reviewType || "",
        primaryKey: model.expectedKey || saved.key || "",
        previousState: model.previous.state || "",
        previousFailureCount: previousFailures.length,
        previousWarningCount: previousWarnings.length,
        previousFailures: clampTextArray(previousFailures, 8, 240),
        previousWarnings: clampTextArray(previousWarnings, 8, 240),
        repairedAt: model.repairedAt,
        checksum: saved.packageChecksum || "",
      };
      normalizeAllData();
      persist();
      renderSavedReviewResult(validator, saved);
      refreshReviewIssueDraftFromSavedResult(validator, saved);
      return { ...model, markdown };
    }

    function setValidation(target, state, message, details = {}) {
      const validator = validatorNode(target);
      if (!validator) return;
      const status = validatorStatus(validator);
      const output = validatorOutput(validator);
      validator.dataset.reviewResultState = state;
      validator.dataset.reviewResultFailureCount = String(details.failures ? details.failures.length : 0);
      recordRepairSnapshot(validator, state, message, details);
      if (status) status.textContent = message;
      if (!output) return;
      if (state === "empty") {
        setHTML(output, "");
        return;
      }
      setHTML(output, validationOutputHTML({
        state,
        result: details.result || {},
        failures: details.failures || [],
        warnings: details.warnings || [],
        expectedKey: validator.dataset.reviewResultPrimaryKey || "",
        reviewType: validator.dataset.reviewResultType || "",
        repairReceipt: details.repairReceipt || null,
      }));
    }

    function copyRepair(target) {
      const repair = target.closest("[data-review-result-repair]");
      const status = nodeQuery(repair, "[data-review-result-repair-copy-status]");
      const text = nodeText(repair, "[data-review-result-repair-text]");
      copyTextWithStatus({
        text,
        datasetKey: "reviewResultRepairCopied",
        targets: [target, repair],
        status,
        copiedStatusText: "repair packet 복사됨",
        failedStatusText: "repair packet 복사 실패",
        copiedToast: "repair packet을 복사했습니다",
        failedToast: "repair packet 복사 실패",
      });
    }

    function copyRepairReceipt(target) {
      const receipt = target.closest("[data-review-result-repair-receipt]");
      const status = nodeQuery(receipt, "[data-review-result-repair-receipt-copy-status]");
      const text = nodeText(receipt, "[data-review-result-repair-receipt-text]");
      copyTextWithStatus({
        text,
        datasetKey: "reviewResultRepairReceiptCopied",
        targets: [target, receipt],
        status,
        copiedStatusText: "post-repair receipt 복사됨",
        failedStatusText: "post-repair receipt 복사 실패",
        copiedToast: "post-repair receipt를 복사했습니다",
        failedToast: "post-repair receipt 복사 실패",
      });
    }

    return {
      version: VERSION,
      validatorNode,
      validatorInput,
      validatorStatus,
      validatorOutput,
      recordRepairSnapshot,
      postRepairReceiptModel,
      attachRepairReceipt,
      setValidation,
      copyRepair,
      copyRepairReceipt,
    };
  }

  root.JooParkReviewResultState = {
    version: VERSION,
    create: createReviewResultState,
  };
})(window);
