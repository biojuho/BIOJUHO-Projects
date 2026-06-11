(function (root) {
  "use strict";

  const VERSION = "joopark-review-creation-actions/v1";
  const ISSUE_BODY_SELECTOR = "[data-issue-draft-body]";
  const HANDOFF_TEXT_SELECTOR = "[data-review-handoff-text]";

  function createReviewCreationActions(deps) {
    const options = deps || {};
    const dashboard = options.dashboard;
    const reviewHandoffNode = options.reviewHandoffNode;
    const issueBySourceKey = options.issueBySourceKey;
    const noteBySourceKey = options.noteBySourceKey;
    const openIssueInKanban = options.openIssueInKanban;
    const openNoteInNotesView = options.openNoteInNotesView;
    const reviewIssueDraftNode = options.reviewIssueDraftNode;
    const projectByName = options.projectByName;
    const nodeText = options.nodeText;
    const reviewDraftWithSavedResult = options.reviewDraftWithSavedResult;
    const issueExecutionChecklistItems = options.issueExecutionChecklistItems;
    const savedReviewResultByKey = options.savedReviewResultByKey;
    const reviewSavedResultNoteBody = options.reviewSavedResultNoteBody;
    const uid = options.uid;
    const nowISO = options.nowISO;
    const rebuildIndexes = options.rebuildIndexes;
    const commit = options.commit;
    const showToast = options.showToast;

    if (
      !dashboard ||
      typeof reviewHandoffNode !== "function" ||
      typeof issueBySourceKey !== "function" ||
      typeof noteBySourceKey !== "function" ||
      typeof openIssueInKanban !== "function" ||
      typeof openNoteInNotesView !== "function" ||
      typeof reviewIssueDraftNode !== "function" ||
      typeof projectByName !== "function" ||
      typeof nodeText !== "function" ||
      typeof reviewDraftWithSavedResult !== "function" ||
      typeof issueExecutionChecklistItems !== "function" ||
      typeof savedReviewResultByKey !== "function" ||
      typeof reviewSavedResultNoteBody !== "function" ||
      typeof uid !== "function" ||
      typeof nowISO !== "function" ||
      typeof rebuildIndexes !== "function" ||
      typeof commit !== "function" ||
      typeof showToast !== "function"
    ) {
      throw new Error("review creation actions helper requires dashboard, lookup, draft, mutation, and toast dependencies");
    }

    function ensureDashboardArray(key) {
      if (!Array.isArray(dashboard[key])) dashboard[key] = [];
      return dashboard[key];
    }

    function draftLabels(draftNode) {
      return draftNode && draftNode.dataset.issueDraftLabels
        ? draftNode.dataset.issueDraftLabels.split(",").map((label) => label.trim()).filter(Boolean)
        : ["benchmark", "handoff", "adoption"];
    }

    function draftEstimate(draftNode) {
      const parsed = Number(draftNode && draftNode.dataset ? draftNode.dataset.issueDraftEstimate : "");
      return Number.isFinite(parsed) && parsed > 0 ? Math.min(999, parsed) : 4;
    }

    function reviewNoteDefaults(handoff) {
      const isKnowledgeBase = !!(handoff && handoff.closest("[data-knowledge-base-review-handoff]"));
      const isBenchmark = !!(handoff && handoff.closest("[data-benchmark-review-handoff]"));
      return {
        titlePrefix: isBenchmark ? "[PM Bench Review]" : isKnowledgeBase ? "[KB/IA Review]" : "[Workspace Review]",
        sourceKind: isBenchmark ? "benchmark-review-note" : isKnowledgeBase ? "knowledge-base-review-note" : "workspace-review-note",
        color: isBenchmark ? "#a970ff" : isKnowledgeBase ? "#84cc16" : "#22d3ee",
      };
    }

    function createBenchmarkReviewIssue(target) {
      const handoff = reviewHandoffNode(target);
      const key = target.dataset.reviewIssueKey || "";
      if (!handoff || !key) {
        showToast("이슈 초안을 찾을 수 없습니다", "warn");
        return;
      }
      const existing = issueBySourceKey(key);
      if (existing) {
        return openIssueInKanban(existing, { toast: `이미 생성된 이슈입니다: ${existing.id}` });
      }
      const draftNode = reviewIssueDraftNode(handoff);
      const title = draftNode ? draftNode.dataset.issueDraftTitle : "";
      const projectName = draftNode ? draftNode.dataset.issueDraftProject : "";
      const project = projectByName(projectName);
      if (!title || !project) {
        showToast("이슈 초안 프로젝트를 찾을 수 없습니다", "warn");
        return;
      }
      const draft = reviewDraftWithSavedResult({
        title,
        projectName,
        priority: draftNode ? draftNode.dataset.issueDraftPriority || "med" : "med",
        labels: draftLabels(draftNode),
        estimate: draftEstimate(draftNode),
        assignee: draftNode ? draftNode.dataset.issueDraftAssignee || "" : "",
        assigneeOverride: draftNode ? draftNode.dataset.issueDraftAssigneeOverride === "true" : false,
        due: draftNode ? draftNode.dataset.issueDraftDue || "" : "",
        persistKey: key,
        body: nodeText(draftNode, ISSUE_BODY_SELECTOR),
      });
      const newIssue = {
        id: uid("issue"),
        project: project.id,
        title: draft.title,
        status: "todo",
        priority: draft.priority,
        assignee: draft.assignee || "",
        labels: draft.labels,
        due: draft.due || null,
        estimate: draft.estimate,
        sourceKey: key,
        body: draft.body,
        sourceKind: draft.resultSource === "validated" ? "validated-review-result" : undefined,
        assigneeOverride: !!draft.assigneeOverride,
        assigneeConfidence: draft.assigneeConfidence || "",
        assigneeSource: draft.assigneeSource || "",
        assigneeReviewRequired: !!draft.assigneeReviewRequired,
        assigneeRequiredFollowUp: Array.isArray(draft.assigneeRequiredFollowUp) ? draft.assigneeRequiredFollowUp : [],
        assigneePromptExamples: Array.isArray(draft.assigneePromptExamples) ? draft.assigneePromptExamples : [],
        assigneeFollowUpReady: !!draft.assigneeFollowUpReady,
        executionOwner: draft.executionOwner || "",
        executionFirstAction: draft.executionFirstAction || "",
        executionDecisionGate: draft.executionDecisionGate || "",
        executionFallbackIfBlocked: draft.executionFallbackIfBlocked || "",
        executionChecklist: issueExecutionChecklistItems({ executionChecklist: draft.executionChecklist }),
        executionChecklistReady: !!draft.executionChecklistReady,
      };
      ensureDashboardArray("issues").push(newIssue);
      rebuildIndexes();
      commit();
      showToast(draft.resultSource === "validated" ? `검증 결과로 이슈를 생성했습니다: ${newIssue.id}` : `이슈 초안을 생성했습니다: ${newIssue.id}`, "info");
    }

    function publishReviewHandoffNote(target) {
      const handoff = reviewHandoffNode(target);
      const key = target.dataset.reviewNoteKey || "";
      if (!handoff || !key) {
        showToast("발행할 review note를 찾을 수 없습니다", "warn");
        return;
      }
      const existing = noteBySourceKey(key);
      if (existing) {
        return openNoteInNotesView(existing, { toast: `이미 발행된 review note를 열었습니다: ${existing.title}` });
      }
      const defaults = reviewNoteDefaults(handoff);
      const titlePrefix = target.dataset.reviewNoteTitlePrefix || defaults.titlePrefix;
      const sourceKind = target.dataset.reviewNoteKind || defaults.sourceKind;
      const color = target.dataset.reviewNoteColor || defaults.color;
      const handoffText = nodeText(handoff, HANDOFF_TEXT_SELECTOR);
      const draftNode = reviewIssueDraftNode(handoff);
      const projectName = draftNode ? draftNode.dataset.issueDraftProject || "" : "";
      const issueBody = nodeText(draftNode, ISSUE_BODY_SELECTOR);
      const saved = savedReviewResultByKey(key);
      if (!handoffText.trim() || !projectName) {
        showToast("review note 본문을 찾을 수 없습니다", "warn");
        return;
      }
      const body = saved ? reviewSavedResultNoteBody(handoffText, saved, issueBody) : [
        handoffText.trim(),
        issueBody.trim() ? "\n## Issue Draft" : "",
        issueBody.trim(),
      ].filter(Boolean).join("\n");
      const note = {
        id: uid("nt"),
        title: `${titlePrefix} ${projectName}`,
        body,
        color,
        pinned: true,
        updatedAt: nowISO(),
        sourceKey: key,
        sourceKind: saved ? `${sourceKind}:validated-review-result` : sourceKind,
      };
      ensureDashboardArray("notes").push(note);
      commit();
      showToast(saved ? `검증 결과로 review note를 발행했습니다: ${note.title}` : `review note를 발행했습니다: ${note.title}`, "info");
    }

    return {
      version: VERSION,
      createBenchmarkReviewIssue,
      publishReviewHandoffNote,
    };
  }

  root.JooParkReviewCreationActions = {
    version: VERSION,
    create: createReviewCreationActions,
  };
})(window);
