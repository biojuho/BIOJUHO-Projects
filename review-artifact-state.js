(function (root) {
  "use strict";

  const VERSION = "joopark-review-artifact-state/v1";

  function createReviewArtifactState(deps) {
    const options = deps || {};
    const html = options.html;
    const nodeText = options.nodeText;
    const nodeQuery = options.nodeQuery;
    const setHTML = options.setHTML;
    const showToast = options.showToast;
    const openModal = options.openModal;
    const reviewArtifactDiffSnippet = options.reviewArtifactDiffSnippet;
    const reviewArtifactDiffChecks = options.reviewArtifactDiffChecks;
    const parseReviewArtifactReceipt = options.parseReviewArtifactReceipt;
    const reviewArtifactReceiptComparison = options.reviewArtifactReceiptComparison;
    const reviewArtifactReceiptCompareOutput = options.reviewArtifactReceiptCompareOutput;
    const issueById = options.issueById;
    const noteById = options.noteById;
    const getRepairUndo = options.getRepairUndo;
    const setRepairUndo = options.setRepairUndo;
    const nowISO = options.nowISO;
    const rebuildIndexes = options.rebuildIndexes;
    const commit = options.commit;

    if (
      typeof html !== "function" ||
      typeof nodeText !== "function" ||
      typeof nodeQuery !== "function" ||
      typeof setHTML !== "function" ||
      typeof showToast !== "function" ||
      typeof openModal !== "function" ||
      typeof reviewArtifactDiffSnippet !== "function" ||
      typeof reviewArtifactDiffChecks !== "function" ||
      typeof parseReviewArtifactReceipt !== "function" ||
      typeof reviewArtifactReceiptComparison !== "function" ||
      typeof reviewArtifactReceiptCompareOutput !== "function" ||
      typeof issueById !== "function" ||
      typeof noteById !== "function" ||
      typeof getRepairUndo !== "function" ||
      typeof setRepairUndo !== "function" ||
      typeof nowISO !== "function" ||
      typeof rebuildIndexes !== "function" ||
      typeof commit !== "function"
    ) {
      throw new Error("review artifact state helper requires DOM, state, and artifact model dependencies");
    }

    function repairUndoFor(artifactType, createdId) {
      const undo = getRepairUndo();
      if (!undo || !createdId) return null;
      return undo.artifactType === artifactType && undo.createdId === createdId ? undo : null;
    }

    function repairTarget(panel) {
      if (!panel) return null;
      const artifactType = panel.dataset.reviewArtifactDiffArtifactType === "note" ? "note" : "issue";
      const createdId = panel.dataset.reviewArtifactDiffCreatedId || "";
      const record = artifactType === "note" ? noteById(createdId) : issueById(createdId);
      if (!createdId || !record) return null;
      return { artifactType, createdId, record };
    }

    function recordBody(target) {
      return target && target.record ? String(target.record.body || "") : "";
    }

    function setRecordBody(target, body) {
      if (!target || !target.record) return false;
      target.record.body = String(body || "");
      if (target.artifactType === "note") target.record.updatedAt = nowISO();
      return true;
    }

    function diffNode(target) {
      return target ? target.closest("[data-review-artifact-diff]") : null;
    }

    function repairBodyText(panel) {
      return nodeText(panel, "[data-review-artifact-repair-body-text]");
    }

    function receiptInput(panel) {
      return nodeQuery(panel, "[data-review-artifact-receipt-input]");
    }

    function receiptText(panel) {
      return nodeText(panel, "[data-review-artifact-receipt-text]");
    }

    function receiptCompareCounts(checks) {
      return {
        count: checks.length,
        passCount: checks.filter((check) => check.status === "pass").length,
        repairCount: checks.filter((check) => check.status !== "pass" && check.repair).length,
      };
    }

    function repairPreview(target) {
      const panel = diffNode(target);
      const repair = repairTarget(panel);
      const archivedBody = repairBodyText(panel);
      if (!panel || !repair || !archivedBody.trim()) {
        showToast("적용할 archived body를 찾을 수 없습니다", "warn");
        return;
      }
      const currentBody = recordBody(repair);
      const archivedChecks = reviewArtifactDiffChecks({ createdBody: archivedBody, sourceKind: repair.record.sourceKind || "" });
      const passCount = archivedChecks.filter((check) => check.status === "pass").length;
      openModal("archived body 적용", html`
        <div class="modal-confirm-body review-artifact-repair-preview" data-review-artifact-repair-preview data-review-artifact-repair-preview-type="${repair.artifactType}" data-review-artifact-repair-preview-id="${repair.createdId}">
          <p><strong>${repair.createdId}</strong>의 현재 ${repair.artifactType === "note" ? "노트" : "이슈"} 본문을 pasted receipt의 Created Artifact Body로 교체합니다.</p>
          <p class="muted-note">적용 후 diff panel에서 한 번 되돌릴 수 있습니다. post-apply fresh receipt는 저장 body를 바꾸지 않고 보관용으로만 복사합니다.</p>
          <div class="review-artifact-repair-preview-grid">
            <article>
              <strong>현재 저장 body</strong>
              <pre data-review-artifact-repair-preview-current>${reviewArtifactDiffSnippet(currentBody)}</pre>
            </article>
            <article>
              <strong>적용할 archived body</strong>
              <pre data-review-artifact-repair-preview-archived>${reviewArtifactDiffSnippet(archivedBody)}</pre>
            </article>
          </div>
          <small data-review-artifact-repair-preview-checks>적용 후 예상 artifact checks: ${passCount}/${archivedChecks.length}</small>
        </div>
      `, () => applyRepairBody({
        artifactType: repair.artifactType,
        createdId: repair.createdId,
        previousBody: currentBody,
        nextBody: archivedBody,
      }));
    }

    function applyRepairBody(repair) {
      const artifactType = repair && repair.artifactType === "note" ? "note" : "issue";
      const createdId = repair ? repair.createdId || "" : "";
      const record = artifactType === "note" ? noteById(createdId) : issueById(createdId);
      if (!record || !String(repair && repair.nextBody || "").trim()) {
        showToast("repair 적용 대상이 없습니다", "error");
        return false;
      }
      setRepairUndo({
        artifactType,
        createdId,
        previousBody: String(repair.previousBody || ""),
        appliedBody: String(repair.nextBody || ""),
        appliedAt: nowISO(),
      });
      setRecordBody({ artifactType, createdId, record }, repair.nextBody);
      rebuildIndexes();
      commit();
      showToast("archived body를 적용했습니다", "info");
      return true;
    }

    function undoRepair(target) {
      const panel = diffNode(target);
      const repair = repairTarget(panel);
      const undo = repair ? repairUndoFor(repair.artifactType, repair.createdId) : null;
      if (!repair || !undo) {
        showToast("되돌릴 repair가 없습니다", "warn");
        return;
      }
      setRecordBody(repair, undo.previousBody);
      setRepairUndo(null);
      rebuildIndexes();
      commit();
      showToast("repair 적용을 되돌렸습니다", "info");
    }

    function setReceiptCompareState(panel, state, message, checks = []) {
      const compare = nodeQuery(panel, "[data-review-artifact-receipt-compare]");
      if (!panel || !compare) return;
      const status = nodeQuery(compare, "[data-review-artifact-receipt-compare-status]");
      const output = nodeQuery(compare, "[data-review-artifact-receipt-compare-output]");
      const counts = receiptCompareCounts(checks);
      panel.dataset.reviewArtifactReceiptCompareState = state;
      panel.dataset.reviewArtifactReceiptCompareCount = String(counts.count);
      panel.dataset.reviewArtifactReceiptComparePassCount = String(counts.passCount);
      panel.dataset.reviewArtifactReceiptRepairCount = String(counts.repairCount);
      compare.dataset.reviewArtifactReceiptCompareState = state;
      compare.dataset.reviewArtifactReceiptCompareCount = String(counts.count);
      compare.dataset.reviewArtifactReceiptComparePassCount = String(counts.passCount);
      compare.dataset.reviewArtifactReceiptRepairCount = String(counts.repairCount);
      if (status) status.textContent = message;
      if (!output) return;
      setHTML(output, state === "empty" ? "" : reviewArtifactReceiptCompareOutput(checks));
    }

    function compareReceipt(target) {
      const panel = diffNode(target);
      const input = receiptInput(panel);
      const currentText = receiptText(panel);
      if (!panel || !input) return;
      const pastedText = input.value || "";
      if (!pastedText.trim()) {
        setReceiptCompareState(panel, "empty", "receipt 대기");
        return;
      }
      const receipt = parseReviewArtifactReceipt(pastedText);
      const current = parseReviewArtifactReceipt(currentText);
      const checks = reviewArtifactReceiptComparison(receipt, current);
      const pass = checks.every((check) => check.status === "pass");
      setReceiptCompareState(panel, pass ? "pass" : "fail", pass ? "receipt 비교 통과" : "receipt 비교 실패", checks);
    }

    function insertReceipt(target) {
      const panel = diffNode(target);
      const input = receiptInput(panel);
      const text = receiptText(panel);
      if (!panel || !input) return;
      input.value = text;
      input.dispatchEvent(new Event("input", { bubbles: true }));
      compareReceipt(target);
    }

    function clearReceipt(target) {
      const panel = diffNode(target);
      const input = receiptInput(panel);
      if (!panel || !input) return;
      input.value = "";
      setReceiptCompareState(panel, "empty", "receipt 대기");
      input.focus();
    }

    return {
      version: VERSION,
      repairUndoFor,
      repairTarget,
      recordBody,
      setRecordBody,
      diffNode,
      repairBodyText,
      receiptInput,
      receiptText,
      repairPreview,
      applyRepairBody,
      undoRepair,
      setReceiptCompareState,
      compareReceipt,
      insertReceipt,
      clearReceipt,
    };
  }

  root.JooParkReviewArtifactState = {
    version: VERSION,
    create: createReviewArtifactState,
  };
})(window);
