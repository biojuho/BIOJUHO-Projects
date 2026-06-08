(function (root) {
  "use strict";

  const VERSION = "joopark-review-execution-checklist/v1";

  function createReviewExecutionChecklist(deps) {
    const options = deps || {};
    const parseSavedReviewResult = options.parseSavedReviewResult;
    const reviewPrimaryDecision = options.reviewPrimaryDecision;

    if (typeof parseSavedReviewResult !== "function" || typeof reviewPrimaryDecision !== "function") {
      throw new Error("review execution checklist helper requires saved result parser and primary decision resolver");
    }

    function uniqueTextItems(items) {
      const seen = new Set();
      return (Array.isArray(items) ? items : [])
        .map((item) => String(item || "").trim())
        .filter((item) => {
          if (!item || seen.has(item)) return false;
          seen.add(item);
          return true;
        });
    }

    function reviewExecutionChecklistItemsFromSavedResult(saved) {
      const result = parseSavedReviewResult(saved);
      if (!result) return [];
      const decisions = Array.isArray(result.decisions) ? result.decisions : [];
      const primary = reviewPrimaryDecision(decisions, saved && saved.key);
      const plans = Array.isArray(result.executionPlan) ? result.executionPlan : [];
      const primaryPlan = plans[0] || {};
      const executionCriteria = plans.flatMap((plan) => Array.isArray(plan && plan.acceptanceCriteria) ? plan.acceptanceCriteria : []);
      const executionValidation = plans.flatMap((plan) => Array.isArray(plan && plan.validationPlan) ? plan.validationPlan : []);
      const items = uniqueTextItems([
        primaryPlan.firstAction || primaryPlan.action ? `First action: ${primaryPlan.firstAction || primaryPlan.action}` : "",
        ...(Array.isArray(primary.acceptanceCriteria) ? primary.acceptanceCriteria.map((item) => `Acceptance: ${item}`) : []),
        ...executionCriteria.map((item) => `Acceptance: ${item}`),
        ...(Array.isArray(primary.validationPlan) ? primary.validationPlan.map((item) => `Validation: ${item}`) : []),
        ...executionValidation.map((item) => `Validation: ${item}`),
      ]).slice(0, 8);
      return items.map((text, index) => ({
        id: `exec-${index + 1}`,
        text,
        done: false,
      }));
    }

    function issueExecutionChecklistItems(issue) {
      return (Array.isArray(issue && issue.executionChecklist) ? issue.executionChecklist : [])
        .map((item, index) => {
          if (typeof item === "string") return { id: `exec-${index + 1}`, text: item, done: false };
          return {
            id: item && item.id ? String(item.id) : `exec-${index + 1}`,
            text: item && item.text ? String(item.text) : "",
            done: !!(item && item.done),
          };
        })
        .filter((item) => item.text.trim());
    }

    function issueExecutionChecklistProgress(issue) {
      const items = issueExecutionChecklistItems(issue);
      const done = items.filter((item) => item.done).length;
      const total = items.length;
      const percent = total ? Math.round((done / total) * 100) : 0;
      return {
        total,
        done,
        remaining: Math.max(0, total - done),
        percent,
        label: total ? `${done}/${total} 완료` : "체크리스트 없음",
      };
    }

    function reviewExecutionChecklistLines(items) {
      const checklist = issueExecutionChecklistItems({ executionChecklist: items });
      return (checklist.length ? checklist : [{ text: "No execution checklist supplied.", done: false }])
        .map((item) => `- [${item.done ? "x" : " "}] ${item.text}`);
    }

    function syncIssueBodyExecutionChecklist(issue) {
      const body = String(issue && issue.body || "");
      if (!body.includes("## Execution Checklist")) return body;
      const section = ["## Execution Checklist", ...reviewExecutionChecklistLines(issueExecutionChecklistItems(issue))].join("\n");
      return body.replace(/## Execution Checklist\n[\s\S]*?(?=\n## |$)/, section);
    }

    function reviewExecutionChecklistCountLabel(items) {
      const count = issueExecutionChecklistItems({ executionChecklist: items }).length;
      return count ? `${count}개` : "없음";
    }

    function firstPositiveTimeboxHours(plans) {
      const list = Array.isArray(plans) ? plans : [];
      return list
        .map((plan) => Number(plan && plan.timeboxHours))
        .find((value) => Number.isFinite(value) && value > 0);
    }

    return {
      version: VERSION,
      reviewExecutionChecklistItemsFromSavedResult,
      issueExecutionChecklistItems,
      issueExecutionChecklistProgress,
      reviewExecutionChecklistLines,
      syncIssueBodyExecutionChecklist,
      reviewExecutionChecklistCountLabel,
      firstPositiveTimeboxHours,
    };
  }

  root.JooParkReviewExecutionChecklist = {
    version: VERSION,
    create: createReviewExecutionChecklist,
  };
})(window);
