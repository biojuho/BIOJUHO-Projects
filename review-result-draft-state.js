(function (root) {
  "use strict";

  const VERSION = "joopark-review-result-draft-state/v1";
  const COMMENT_SELECTOR = "[data-review-github-comment-key]";
  const COMMENT_TEXT_SELECTOR = "[data-review-github-comment-text]";
  const COMMENT_STATUS_SELECTOR = "[data-review-github-comment-copy-status]";
  const DRAFT_SELECTOR = "[data-review-issue-draft]";
  const DRAFT_GRID_CELL_SELECTOR = ".portfolio-issue-draft-grid strong";
  const DRAFT_BODY_SELECTOR = "[data-issue-draft-body]";
  const OWNER_FOLLOW_UP_SELECTOR = "[data-issue-draft-owner-follow-up]";
  const ASSIGNEE_PANEL_SELECTOR = "[data-issue-draft-assignee-review-panel]";
  const ASSIGNEE_SELECT_SELECTOR = "[data-issue-draft-assignee-select]";
  const ASSIGNEE_COPY_SELECTOR = "[data-issue-draft-assignee-review-copy]";
  const DRAFT_HEAD_SELECTOR = ".portfolio-issue-draft-head";
  const DRAFT_CREATE_SELECTOR = "[data-review-issue-create]";

  function createReviewResultDraftState(deps) {
    const options = deps || {};
    const nodeQuery = options.nodeQuery;
    const nodeText = options.nodeText;
    const copyTextWithStatus = options.copyTextWithStatus;
    const memberName = options.memberName;
    const reviewAssigneeConfidenceLabel = options.reviewAssigneeConfidenceLabel;
    const uniqueTextItems = options.uniqueTextItems;
    const saveReviewIssueDraftAssigneeOverride = options.saveReviewIssueDraftAssigneeOverride;
    const showToast = options.showToast;

    if (
      typeof nodeQuery !== "function" ||
      typeof nodeText !== "function" ||
      typeof copyTextWithStatus !== "function" ||
      typeof memberName !== "function" ||
      typeof reviewAssigneeConfidenceLabel !== "function" ||
      typeof uniqueTextItems !== "function" ||
      typeof saveReviewIssueDraftAssigneeOverride !== "function" ||
      typeof showToast !== "function"
    ) {
      throw new Error("review result draft state helper requires DOM, copy, team, and persistence dependencies");
    }

    function issueDraftCells(draftNode) {
      return draftNode ? draftNode.querySelectorAll(DRAFT_GRID_CELL_SELECTOR) : [];
    }

    function issueDraftBodyNode(draftNode) {
      return nodeQuery(draftNode, DRAFT_BODY_SELECTOR);
    }

    function issueDraftNode(handoff) {
      return nodeQuery(handoff, DRAFT_SELECTOR);
    }

    function issueDraftOwnerFollowUpPanel(draftNode) {
      return nodeQuery(draftNode, OWNER_FOLLOW_UP_SELECTOR);
    }

    function issueDraftAssigneePanel(draftNode) {
      return nodeQuery(draftNode, ASSIGNEE_PANEL_SELECTOR);
    }

    function issueDraftAssigneeSelect(panel) {
      return nodeQuery(panel, ASSIGNEE_SELECT_SELECTOR);
    }

    function issueDraftAssigneeCopy(panel) {
      return nodeQuery(panel, ASSIGNEE_COPY_SELECTOR);
    }

    function issueDraftHead(draftNode) {
      return nodeQuery(draftNode, DRAFT_HEAD_SELECTOR);
    }

    function issueDraftCreateButton(head) {
      return nodeQuery(head, DRAFT_CREATE_SELECTOR);
    }

    function copyGithubComment(target) {
      const comment = target.closest(COMMENT_SELECTOR);
      const text = nodeText(comment, COMMENT_TEXT_SELECTOR);
      const status = nodeQuery(comment, COMMENT_STATUS_SELECTOR);
      copyTextWithStatus({
        text,
        datasetKey: "reviewGithubCommentCopied",
        targets: [target, comment],
        status,
        copiedStatusText: "댓글 복사됨",
        failedStatusText: "댓글 복사 실패",
        copiedToast: "GitHub comment draft를 복사했습니다",
        failedToast: "댓글 복사 실패",
      });
    }

    function updateIssueDraftAssignee(target) {
      const draftNode = target.closest(DRAFT_SELECTOR);
      if (!draftNode) return;
      const assignee = target.value || "";
      const savedOverride = saveReviewIssueDraftAssigneeOverride(draftNode.dataset.issueDraftKey || "", assignee);
      draftNode.dataset.issueDraftAssignee = assignee;
      draftNode.dataset.issueDraftAssigneeOverride = "true";
      draftNode.dataset.issueDraftAssigneeOverrideSavedAt = savedOverride ? savedOverride.savedAt : draftNode.dataset.issueDraftAssigneeOverrideSavedAt || "";
      draftNode.dataset.issueDraftAssigneeConfidence = "manual";
      draftNode.dataset.issueDraftAssigneeSource = "manual-override";
      draftNode.dataset.issueDraftAssigneeReview = assignee ? "false" : "true";
      draftNode.dataset.issueDraftAssigneeRequiredFollowUpCount = assignee ? "0" : draftNode.dataset.issueDraftAssigneeRequiredFollowUpCount || "0";
      draftNode.dataset.issueDraftAssigneePromptExampleCount = assignee ? "0" : draftNode.dataset.issueDraftAssigneePromptExampleCount || "0";
      draftNode.dataset.issueDraftOwnerFollowUpReady = assignee ? "false" : draftNode.dataset.issueDraftOwnerFollowUpReady || "false";
      const labels = (draftNode.dataset.issueDraftLabels || "")
        .split(",")
        .map((label) => label.trim())
        .filter((label) => label && label !== "assignee-review" && label !== "assignee-confirmed" && label !== "owner-followup");
      labels.push(assignee ? "assignee-confirmed" : "assignee-review");
      draftNode.dataset.issueDraftLabels = uniqueTextItems(labels).join(",");
      const cells = issueDraftCells(draftNode);
      if (cells[3]) cells[3].textContent = assignee ? memberName(assignee) : "미지정";
      const panel = issueDraftAssigneePanel(draftNode);
      if (panel) {
        panel.dataset.assigneeReviewRequired = assignee ? "false" : "true";
        panel.dataset.assigneeConfidence = "manual";
        panel.dataset.assigneeSource = "manual-override";
        const copy = issueDraftAssigneeCopy(panel);
        if (copy) copy.textContent = `${assignee ? `수동 확인됨: ${memberName(assignee)}` : "수동 확인 필요: 미지정"} · ${reviewAssigneeConfidenceLabel("manual")} · User selected the issue assignee before creation.`;
      }
      if (assignee) {
        const followUpPanel = issueDraftOwnerFollowUpPanel(draftNode);
        if (followUpPanel) followUpPanel.remove();
      }
      showToast(assignee ? `담당자를 ${memberName(assignee)}로 확인했습니다` : "담당자를 미지정으로 변경했습니다", assignee ? "info" : "warn");
    }

    return {
      version: VERSION,
      issueDraftCells,
      issueDraftBodyNode,
      issueDraftNode,
      issueDraftOwnerFollowUpPanel,
      issueDraftAssigneePanel,
      issueDraftAssigneeSelect,
      issueDraftAssigneeCopy,
      issueDraftHead,
      issueDraftCreateButton,
      copyGithubComment,
      updateIssueDraftAssignee,
    };
  }

  root.JooParkReviewResultDraftState = {
    version: VERSION,
    create: createReviewResultDraftState,
  };
})(window);
