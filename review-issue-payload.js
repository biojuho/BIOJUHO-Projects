(function (root) {
  "use strict";

  const VERSION = "joopark-review-issue-payload/v1";

  function createReviewIssuePayload(deps) {
    const options = deps || {};
    const shortCommit = options.shortCommit;
    const metricValue = options.metricValue;
    const parseSavedReviewResult = options.parseSavedReviewResult;
    const projectByIdOrName = options.projectByIdOrName;
    const reviewExecutionChecklistItemsFromSavedResult = options.reviewExecutionChecklistItemsFromSavedResult;
    const reviewOwnerAssignment = options.reviewOwnerAssignment;
    const reviewOwnerFollowUpItems = options.reviewOwnerFollowUpItems;
    const reviewOwnerPromptExamples = options.reviewOwnerPromptExamples;
    const todayISO = options.todayISO;
    const addDays = options.addDays;

    [
      ["shortCommit", shortCommit],
      ["metricValue", metricValue],
      ["parseSavedReviewResult", parseSavedReviewResult],
      ["projectByIdOrName", projectByIdOrName],
      ["reviewExecutionChecklistItemsFromSavedResult", reviewExecutionChecklistItemsFromSavedResult],
      ["reviewOwnerAssignment", reviewOwnerAssignment],
      ["reviewOwnerFollowUpItems", reviewOwnerFollowUpItems],
      ["reviewOwnerPromptExamples", reviewOwnerPromptExamples],
      ["todayISO", todayISO],
      ["addDays", addDays],
    ].forEach(([name, fn]) => {
      if (typeof fn !== "function") throw new Error(`review issue payload helper requires ${name}`);
    });

    function nonEmptyListOrDefault(items, fallback) {
      return Array.isArray(items) && items.length > 0 ? items : fallback;
    }

    function positiveFiniteNumberOrDefault(value, fallback) {
      const number = Number(value);
      return Number.isFinite(number) && number > 0 ? number : fallback;
    }

    function reviewOperationalReadinessLines({ owner, firstAction, timeboxHours, decisionGate, fallbackIfBlocked }) {
      const safeTimeboxHours = positiveFiniteNumberOrDefault(timeboxHours, 4);
      return [
        "## Operational Readiness",
        `- Owner: ${owner || "PM reviewer"}`,
        `- First action: ${firstAction || "Verify source metadata and comparison evidence before changing tracker status."}`,
        `- Timebox hours: ${safeTimeboxHours}`,
        `- Decision gate: ${decisionGate || "Proceed only when acceptance criteria and validation checks are satisfied or missingEvidence is listed."}`,
        `- Fallback if blocked: ${fallbackIfBlocked || "Keep the item in review/compare, record requiredFollowUp, and do not claim external completion."}`,
      ];
    }

    function reviewIssueDecisionSummaryLines({ project, decision, secondary, scope, timeboxHours, firstAction, fallbackIfBlocked }) {
      const safeTimeboxHours = positiveFiniteNumberOrDefault(timeboxHours, 4);
      const comparison = secondary
        ? `${secondary.project.name} ${secondary.decision.status} (${secondary.decision.label} ${secondary.decision.score})`
        : "No comparison candidate recorded.";
      const evidenceAnchor = [
        `source ${project.url || "missing"}`,
        `commit ${shortCommit(project.lastCommit) || project.lastCommit || "missing"}`,
        `pushedAt ${project.pushedAt || "missing"}`,
        `persist key ${decision.persistKey || "missing"}`,
      ].join("; ");
      return [
        "## Decision Summary",
        `- Recommendation: ${project.name} -> ${decision.status} (${decision.label} ${decision.score})`,
        `- Why this candidate: ${decision.reason}`,
        `- Comparison context: ${comparison}`,
        `- Evidence anchor: ${evidenceAnchor}`,
        `- First action: ${firstAction || `Verify ${project.name} source metadata and comparison candidate before changing tracker status.`}`,
        `- Stop condition: ${fallbackIfBlocked || `Keep the item in review/compare if acceptance criteria, validation checks, or missingEvidence are not explicit within ${safeTimeboxHours} hours.`}`,
      ];
    }

    function reviewIssueBodyLines({ project, decision, secondary, scope, timeboxHours, acceptanceCriteria, validationPlan }) {
      const safeTimeboxHours = positiveFiniteNumberOrDefault(timeboxHours, 4);
      const criteria = nonEmptyListOrDefault(acceptanceCriteria, [
        "Decision, source metadata, comparison, and next action are explicit enough to execute without rewriting.",
      ]);
      const validation = nonEmptyListOrDefault(validationPlan, [
        "Reopen the portfolio handoff and confirm the same persist key, score, labels, and comparison candidate are visible.",
      ]);
      const firstAction = `Verify ${project.name} source metadata and comparison candidate before changing tracker status.`;
      const fallbackIfBlocked = "Keep the item in review/compare, add requiredFollowUp, and do not claim install, publish, purchase, credential, or upload completion.";
      return [
        ...reviewIssueDecisionSummaryLines({
          project,
          decision,
          secondary,
          scope,
          timeboxHours: safeTimeboxHours,
          firstAction,
          fallbackIfBlocked,
        }),
        "",
        "## Decision",
        `- Scope: ${scope}`,
        `- Decision: ${project.name} ${decision.status} (${decision.label} ${decision.score})`,
        `- Persist key: ${decision.persistKey}`,
        decision.surface ? `- Surface: ${decision.surface}` : "",
        `- Reason: ${decision.reason}`,
        secondary ? `- Compare with: ${secondary.project.name} ${secondary.decision.status} (${secondary.decision.label} ${secondary.decision.score})` : "",
        "",
        "## Evidence Snapshot",
        `- Source URL: ${project.url || "missing"}`,
        `- Last commit: ${shortCommit(project.lastCommit) || project.lastCommit || "missing"}`,
        `- Pushed at: ${project.pushedAt || "missing"}`,
        `- Signals: ${metricValue(project.stars)} stars, ${metricValue(project.forks)} forks, ${metricValue(project.openIssues)} open issues, ${metricValue(project.risks)} risks`,
        `- Language: ${project.language || "unknown"}`,
        "",
        ...reviewOperationalReadinessLines({
          owner: "PM reviewer",
          firstAction,
          timeboxHours: safeTimeboxHours,
          decisionGate: "Move forward only when every acceptance criterion and validation check is satisfied or missingEvidence is explicit.",
          fallbackIfBlocked,
        }),
        "",
        "## Acceptance Criteria",
        ...criteria.map((item) => `- ${item}`),
        "",
        "## Validation Plan",
        ...validation.map((item) => `- ${item}`),
        "",
        "## Missing Evidence To Close",
        "- Record any stale source metadata, ambiguous score tie, unsafe external action, or missing user evidence before moving out of review.",
        "",
        `## Timebox: ${safeTimeboxHours} hours`,
      ].filter((line) => line !== "").join("\n");
    }

    function reviewMarkdownHeadingIndex(lines, target) {
      return lines.findIndex((line) => line.trim().toLowerCase() === `## ${target}`);
    }

    function reviewMarkdownSection(text, heading) {
      const target = String(heading || "").trim().toLowerCase();
      if (!target) return "";
      const lines = String(text || "").split(/\r?\n/);
      const start = reviewMarkdownHeadingIndex(lines, target);
      if (start < 0) return "";
      const body = [];
      for (let index = start + 1; index < lines.length; index += 1) {
        const line = lines[index];
        if (/^##\s+/.test(line.trim())) break;
        body.push(line);
      }
      return body.join("\n").trim();
    }

    function reviewPinnedNoteSummary(draft) {
      const summary = reviewMarkdownSection(draft && draft.body, "Decision Summary");
      if (!summary) return "";
      return [
        "## Pinned Note Summary",
        "- Source: Issue Draft Decision Summary",
        summary,
        "",
      ].join("\n");
    }

    function reviewPackageNoteBody(handoffMarkdown, draft) {
      const noteSummary = reviewPinnedNoteSummary(draft);
      return [
        noteSummary,
        String(handoffMarkdown || "").trim(),
        draft && draft.body ? "\n## Issue Draft" : "",
        draft && draft.body ? draft.body.trim() : "",
      ].filter(Boolean).join("\n");
    }

    function reviewExecutionPlanForSavedResult(saved) {
      const result = parseSavedReviewResult(saved);
      const plans = result && Array.isArray(result.executionPlan) ? result.executionPlan : [];
      return plans[0] || {};
    }

    function reviewExecutionDueDate(timeboxHours) {
      const hours = Number(timeboxHours);
      if (!Number.isFinite(hours) || hours <= 0) return "";
      const dayOffset = Math.max(0, Math.ceil(hours / 8) - 1);
      return addDays(todayISO(), dayOffset);
    }

    function reviewSavedResultTrackerFields(saved, draft) {
      const safeDraft = draft || {};
      const plan = reviewExecutionPlanForSavedResult(saved);
      const project = projectByIdOrName(safeDraft.projectId, safeDraft.projectName);
      const owner = plan.owner || "";
      const timeboxHours = Number(plan.timeboxHours);
      const executionChecklist = reviewExecutionChecklistItemsFromSavedResult(saved);
      const assignment = reviewOwnerAssignment(owner, project);
      const assigneeRequiredFollowUp = reviewOwnerFollowUpItems(assignment, owner, project);
      const assigneePromptExamples = reviewOwnerPromptExamples(assignment, owner, project);
      return {
        assignee: assignment.assignee,
        assigneeConfidence: assignment.confidence,
        assigneeSource: assignment.source,
        assigneeReason: assignment.reason,
        assigneeReviewRequired: assignment.reviewRequired,
        assigneeRequiredFollowUp,
        assigneePromptExamples,
        assigneeFollowUpReady: assigneeRequiredFollowUp.length > 0 || assigneePromptExamples.length > 0,
        due: reviewExecutionDueDate(timeboxHours),
        estimate: Number.isFinite(timeboxHours) && timeboxHours > 0 ? timeboxHours : safeDraft.estimate,
        executionOwner: owner,
        executionFirstAction: plan.firstAction || plan.action || "",
        executionDecisionGate: plan.decisionGate || "",
        executionFallbackIfBlocked: plan.fallbackIfBlocked || "",
        executionChecklist,
        executionChecklistReady: executionChecklist.length > 0,
        trackerReady: !!(owner && Number.isFinite(timeboxHours) && timeboxHours > 0),
      };
    }

    return {
      version: VERSION,
      reviewOperationalReadinessLines,
      reviewIssueDecisionSummaryLines,
      reviewIssueBodyLines,
      reviewPackageNoteBody,
      reviewMarkdownSection,
      reviewPinnedNoteSummary,
      reviewExecutionPlanForSavedResult,
      reviewExecutionDueDate,
      reviewSavedResultTrackerFields,
    };
  }

  root.JooParkReviewIssuePayload = {
    version: VERSION,
    create: createReviewIssuePayload,
  };
})(window);
