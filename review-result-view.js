(function (root) {
  "use strict";

  const VERSION = "joopark-review-result-view/v1";

  function createReviewResultView(deps) {
    const options = deps || {};
    const html = options.html;
    const raw = typeof options.raw === "function"
      ? options.raw
      : function (value) { return { __raw: true, value: value == null ? "" : String(value) }; };
    const schemaVersion = options.schemaVersion || "joopark-review-handoff/v2";
    const clampText = typeof options.clampText === "function"
      ? options.clampText
      : function (value, max) {
        const text = String(value == null ? "" : value);
        return max > 0 && text.length > max ? text.slice(0, max) : text;
      };
    const clampTextArray = typeof options.clampTextArray === "function"
      ? options.clampTextArray
      : function (value, maxItems, maxChars) {
        return (Array.isArray(value) ? value : [])
          .slice(0, maxItems)
          .map((item) => clampText(item, maxChars))
          .filter(Boolean);
      };
    const formatLocalDateTime = typeof options.formatLocalDateTime === "function"
      ? options.formatLocalDateTime
      : function (value) { return value || ""; };
    const nowISO = typeof options.nowISO === "function"
      ? options.nowISO
      : function () { return new Date().toISOString(); };
    const shortCommit = typeof options.shortCommit === "function" ? options.shortCommit : function (value) { return value || ""; };
    const metricValue = typeof options.metricValue === "function" ? options.metricValue : function (value) { return value == null || value === "" ? "-" : value; };
    const memberName = typeof options.memberName === "function" ? options.memberName : function (value) { return value || "unassigned"; };
    const reviewOperationalReadinessLines = typeof options.reviewOperationalReadinessLines === "function"
      ? options.reviewOperationalReadinessLines
      : function () { return ["## Operational Readiness", "- Owner: unassigned"]; };
    const reviewMarkdownList = typeof options.reviewMarkdownList === "function"
      ? options.reviewMarkdownList
      : function (items, fallback) {
        const list = Array.isArray(items) && items.length ? items : [fallback || "No items supplied."];
        return list.map((item) => `- ${item}`);
      };
    const reviewExecutionChecklistLines = typeof options.reviewExecutionChecklistLines === "function"
      ? options.reviewExecutionChecklistLines
      : function () { return ["- [ ] No execution checklist supplied."]; };

    if (typeof html !== "function") {
      throw new Error("review result view requires html helper");
    }

    function reviewActionLabel(action) {
      return {
        adopt: "도입",
        compare: "비교",
        watch: "관찰",
        defer: "보류",
      }[action] || "미정";
    }

    function reviewConfidenceLabel(confidence) {
      return {
        high: "높음",
        medium: "중간",
        low: "낮음",
      }[confidence] || "미정";
    }

    function reviewResultSavedCard(saved) {
      if (!saved) {
        return html`
          <div class="review-result-saved is-empty" data-review-result-saved-card data-review-result-saved-state="empty">
            <strong>저장된 결과 없음</strong>
            <span>검증 통과 시 이 handoff 결과가 localStorage에 저장됩니다.</span>
          </div>
        `;
      }
      return html`
        <div class="review-result-saved" data-review-result-saved-card data-review-result-saved-state="saved" data-review-result-saved-key="${saved.key}" data-review-result-saved-action="${saved.recommendedAction}" data-review-result-saved-confidence="${saved.confidence}">
          <div>
            <strong>저장된 결과</strong>
            <span>${formatLocalDateTime(saved.savedAt)} · ${reviewActionLabel(saved.recommendedAction)} · 신뢰도 ${reviewConfidenceLabel(saved.confidence)}</span>
          </div>
          <p data-review-result-saved-summary>${saved.summary}</p>
          <dl>
            <div><dt>issue</dt><dd>${saved.issueTitle || "-"}</dd></div>
            <div><dt>key</dt><dd>${saved.key}</dd></div>
            <div><dt>bundle</dt><dd>${saved.packageChecksum || "-"}</dd></div>
            <div><dt>manifest</dt><dd>${saved.packageManifestStatus || "-"} · ${saved.packageSourceFreshness || "-"}</dd></div>
          </dl>
        </div>
      `;
    }

    function compactReviewResult({ result, expectedKey, reviewType, warnings, manifestEvidence }) {
      const decisions = Array.isArray(result && result.decisions) ? result.decisions : [];
      const primaryDecision = decisions.find((decision) => decision && decision.persistKey === expectedKey) || decisions[0] || {};
      const uiArtifacts = result && result.uiArtifacts && typeof result.uiArtifacts === "object" ? result.uiArtifacts : {};
      const manifest = manifestEvidence || {};
      return {
        key: expectedKey,
        schemaVersion: result && result.schemaVersion || schemaVersion,
        reviewType,
        project: clampText(primaryDecision.project || "", 120),
        status: clampText(primaryDecision.status || "", 80),
        score: Math.max(0, Math.min(100, parseInt(primaryDecision.score || "0", 10) || 0)),
        recommendedAction: result && result.recommendedAction || "defer",
        confidence: result && result.confidence || "low",
        summary: clampText(uiArtifacts.markdownSummary || "", 1200),
        issueTitle: clampText(uiArtifacts.issueTitle || "", 180),
        labels: clampTextArray(uiArtifacts.labels, 12, 40),
        warnings: clampTextArray(warnings, 8, 240),
        packageChecksum: clampText(manifest.packageChecksum || "", 80),
        packageManifestStatus: clampText(manifest.packageManifestStatus || "", 40),
        packageSourceFreshness: clampText(manifest.packageSourceFreshness || "", 40),
        packageSourceCount: Number(manifest.packageSourceCount || 0) || 0,
        savedAt: nowISO(),
        resultJson: clampText(JSON.stringify(result || {}, null, 2), 20000),
      };
    }

    function reviewSavedResultExecutionLines(executionPlan) {
      const plans = Array.isArray(executionPlan) ? executionPlan : [];
      if (plans.length === 0) return ["- No execution plan supplied."];
      return plans.map((plan, index) => {
        const action = plan && plan.action ? plan.action : "No action supplied.";
        const firstAction = plan && plan.firstAction ? plan.firstAction : action;
        const owner = plan && plan.owner ? plan.owner : "unassigned";
        const hours = plan && Number(plan.timeboxHours) > 0 ? `${Number(plan.timeboxHours)}h` : "no timebox";
        const gate = plan && plan.decisionGate ? plan.decisionGate : "No decision gate supplied.";
        const fallback = plan && plan.fallbackIfBlocked ? plan.fallbackIfBlocked : "No fallback supplied.";
        return `- ${index + 1}. ${action} First action: ${firstAction}. Owner: ${owner}. Timebox: ${hours}. Decision gate: ${gate}. Fallback if blocked: ${fallback}`;
      });
    }

    function reviewSavedResultRepairEvidenceLines(saved) {
      const data = saved && typeof saved === "object" ? saved : {};
      const evidence = data.repairEvidence && typeof data.repairEvidence === "object" ? data.repairEvidence : {};
      const receipt = data.postRepairReceipt ? String(data.postRepairReceipt) : "";
      if (!receipt && Object.keys(evidence).length === 0) return [];
      const failures = Array.isArray(evidence.previousFailures) ? evidence.previousFailures : [];
      const warnings = Array.isArray(evidence.previousWarnings) ? evidence.previousWarnings : [];
      return [
        "",
        "## Repair Evidence",
        "- Source: JooPark Review Result Post-Repair Receipt",
        `- Previous state: ${evidence.previousState || "unknown"}`,
        `- Previous failure count: ${Number(evidence.previousFailureCount || failures.length) || 0}`,
        `- Previous warning count: ${Number(evidence.previousWarningCount || warnings.length) || 0}`,
        `- Repaired at: ${formatLocalDateTime(evidence.repairedAt || data.savedAt)}`,
        `- Post-repair receipt checksum: ${evidence.checksum || data.packageChecksum || "missing"}`,
        `- Post-repair primary key: ${evidence.primaryKey || data.key || "missing"}`,
        "- Receipt guard: Pair this created issue/note artifact receipt with the post-repair receipt before archiving.",
        "",
        "### Previous Failure Evidence",
        ...(failures.length ? failures.map((failure, index) => `${index + 1}. ${failure}`) : ["- none"]),
        "",
        "### Previous Warning Evidence",
        ...(warnings.length ? warnings.map((warning, index) => `${index + 1}. ${warning}`) : ["- none"]),
      ];
    }

    function reviewIssueDecisionSummaryLines({ result, saved, primary, source, primaryExecutionPlan }) {
      const decisions = Array.isArray(result && result.decisions) ? result.decisions : [];
      const comparison = decisions.find((decision) => decision && decision.persistKey !== (primary.persistKey || saved.key)) || null;
      const projectName = primary.project || saved.project || "missing project";
      const status = primary.status || saved.status || result.recommendedAction || "missing status";
      const score = primary.score || saved.score || "missing score";
      const rationale = primary.rationale || saved.summary || "No rationale supplied.";
      const firstAction = primaryExecutionPlan.firstAction || primaryExecutionPlan.action || `Verify ${projectName} source metadata and comparison evidence before changing tracker status.`;
      const fallback = primaryExecutionPlan.fallbackIfBlocked || "Keep the item in review/compare when acceptance criteria, validation checks, or missingEvidence are incomplete.";
      const evidenceAnchor = [
        `source ${source.sourceUrl || "missing"}`,
        `commit ${shortCommit(source.lastCommit) || source.lastCommit || "missing"}`,
        `pushedAt ${source.pushedAt || "missing"}`,
        `persist key ${primary.persistKey || saved.key || "missing"}`,
      ].join("; ");
      return [
        "## Decision Summary",
        `- Recommendation: ${projectName} -> ${status} (score ${score})`,
        `- Why this candidate: ${rationale}`,
        `- Comparison context: ${comparison ? `${comparison.project || "comparison project"} ${comparison.status || "status missing"} (score ${comparison.score || "missing"})` : "No comparison candidate recorded."}`,
        `- Evidence anchor: ${evidenceAnchor}`,
        `- First action: ${firstAction}`,
        `- Stop condition: ${fallback}`,
      ];
    }

    function reviewMarkdownSection(text, heading) {
      const target = String(heading || "").trim().toLowerCase();
      if (!target) return "";
      const lines = String(text || "").split(/\r?\n/);
      const start = lines.findIndex((line) => line.trim().toLowerCase() === `## ${target}`);
      if (start < 0) return "";
      const body = [];
      for (let index = start + 1; index < lines.length; index += 1) {
        const line = lines[index];
        if (/^##\s+/.test(line.trim())) break;
        body.push(line);
      }
      return body.join("\n").trim();
    }

    function reviewMarkdownBulletValue(text, label, fallback) {
      const prefix = `- ${label}:`;
      const line = String(text || "").split(/\r?\n/).find((item) => item.trim().startsWith(prefix));
      if (!line) return fallback || "missing";
      return line.trim().slice(prefix.length).trim() || fallback || "missing";
    }

    function reviewCommentDecisionSummaryLines({ primaryDecision, primaryProject, secondaryDecision, secondaryProject, draft }) {
      const summary = reviewMarkdownSection(draft && draft.body, "Decision Summary");
      const primaryScore = primaryDecision.score == null ? "missing" : primaryDecision.score;
      const secondaryScore = secondaryDecision && secondaryDecision.score == null ? "missing" : secondaryDecision ? secondaryDecision.score : "missing";
      return [
        "## Comment Decision Summary",
        `- Recommendation: ${reviewMarkdownBulletValue(summary, "Recommendation", `${primaryProject.name || "missing"} -> ${primaryDecision.status || "missing"} (${primaryDecision.label || "score"} ${primaryScore})`)}`,
        `- Why this candidate: ${reviewMarkdownBulletValue(summary, "Why this candidate", primaryDecision.reason || "No rationale supplied.")}`,
        `- Comparison context: ${reviewMarkdownBulletValue(summary, "Comparison context", secondaryDecision && secondaryProject ? `${secondaryProject.name} ${secondaryDecision.status || "missing"} (${secondaryDecision.label || "score"} ${secondaryScore})` : "No comparison candidate recorded.")}`,
        `- Evidence anchor: ${reviewMarkdownBulletValue(summary, "Evidence anchor", `persist key ${primaryDecision.persistKey || draft.persistKey || "missing"}`)}`,
        `- First action: ${reviewMarkdownBulletValue(summary, "First action", "Verify source metadata and comparison candidate before changing tracker status.")}`,
        `- Stop condition: ${reviewMarkdownBulletValue(summary, "Stop condition", "Keep the item in review/compare if acceptance criteria, validation checks, or missingEvidence are incomplete.")}`,
      ];
    }

    function reviewPinnedNoteSummaryLines(body) {
      const summary = reviewMarkdownSection(body, "Decision Summary");
      if (!summary) return [];
      return [
        "## Pinned Note Summary",
        "- Source: Issue Draft Decision Summary",
        summary,
        "",
      ];
    }

    function reviewSavedResultBody(model) {
      const data = model || {};
      const result = data.result && typeof data.result === "object" ? data.result : {};
      const saved = data.saved && typeof data.saved === "object" ? data.saved : {};
      const primary = data.primary && typeof data.primary === "object" ? data.primary : {};
      const source = data.source && typeof data.source === "object" ? data.source : {};
      const executionPlan = Array.isArray(data.executionPlan) ? data.executionPlan : [];
      const executionCriteria = Array.isArray(data.executionCriteria) ? data.executionCriteria : [];
      const executionValidation = Array.isArray(data.executionValidation) ? data.executionValidation : [];
      const missingEvidence = Array.isArray(data.missingEvidence) ? data.missingEvidence : [];
      const exceptions = Array.isArray(data.exceptions) ? data.exceptions : [];
      const qualityGate = data.qualityGate && typeof data.qualityGate === "object" ? data.qualityGate : {};
      const primaryExecutionPlan = data.primaryExecutionPlan && typeof data.primaryExecutionPlan === "object" ? data.primaryExecutionPlan : {};
      const ownerAssignment = data.ownerAssignment && typeof data.ownerAssignment === "object" ? data.ownerAssignment : {};
      const assigneeRequiredFollowUp = Array.isArray(data.assigneeRequiredFollowUp) ? data.assigneeRequiredFollowUp : [];
      const assigneePromptExamples = Array.isArray(data.assigneePromptExamples) ? data.assigneePromptExamples : [];
      const executionChecklist = Array.isArray(data.executionChecklist) ? data.executionChecklist : [];
      return [
        "## Validated Review Result",
        "- Source: validated `reviewResults` JSON, not scraped prose.",
        `- Schema version: ${result.schemaVersion || saved.schemaVersion || "missing"}`,
        `- Primary decision key: ${result.primaryDecisionKey || saved.key}`,
        `- Recommended action: ${result.recommendedAction || saved.recommendedAction || "missing"} (${reviewActionLabel(result.recommendedAction || saved.recommendedAction)})`,
        `- Confidence: ${result.confidence || saved.confidence || "missing"} (${reviewConfidenceLabel(result.confidence || saved.confidence)})`,
        saved.summary ? `- UI summary: ${saved.summary}` : "",
        "",
        ...reviewIssueDecisionSummaryLines({
          result,
          saved,
          primary,
          source,
          primaryExecutionPlan,
        }),
        "",
        "## Decision",
        `- Project: ${primary.project || saved.project || "missing"}`,
        `- Status: ${primary.status || saved.status || "missing"}`,
        `- Score: ${primary.score || saved.score || "missing"}`,
        `- Persist key: ${primary.persistKey || saved.key}`,
        primary.rationale ? `- Rationale: ${primary.rationale}` : "",
        "",
        "## Source Snapshot",
        `- Source URL: ${source.sourceUrl || "missing"}`,
        `- Last commit: ${shortCommit(source.lastCommit) || source.lastCommit || "missing"}`,
        `- Pushed at: ${source.pushedAt || "missing"}`,
        `- Signals: ${metricValue(source.stars)} stars, ${metricValue(source.forks)} forks, ${metricValue(source.openIssues)} open issues`,
        "",
        "## Bundle Manifest",
        `- Payload checksum: ${saved.packageChecksum || "missing"}`,
        `- Manifest status: ${saved.packageManifestStatus || "missing"}`,
        `- Source freshness: ${saved.packageSourceFreshness || "missing"} (${saved.packageSourceCount || 0} sources)`,
        ...reviewSavedResultRepairEvidenceLines(saved),
        "",
        ...reviewOperationalReadinessLines({
          owner: primaryExecutionPlan.owner || "unassigned",
          firstAction: primaryExecutionPlan.firstAction || primaryExecutionPlan.action || "No first action supplied.",
          timeboxHours: primaryExecutionPlan.timeboxHours,
          decisionGate: primaryExecutionPlan.decisionGate || "No decision gate supplied.",
          fallbackIfBlocked: primaryExecutionPlan.fallbackIfBlocked || "No fallback supplied.",
        }),
        ...(assigneeRequiredFollowUp.length || assigneePromptExamples.length ? [
          "",
          "## Assignee Follow-up",
          `- Mapping confidence: ${ownerAssignment.confidence || "none"} (${ownerAssignment.source || "unknown"})`,
          `- Suggested assignee: ${ownerAssignment.assignee ? memberName(ownerAssignment.assignee) : "unassigned"}`,
          ...assigneeRequiredFollowUp.map((item) => `- Required: ${item}`),
          ...assigneePromptExamples.map((item) => `- Prompt example: ${item}`),
        ] : []),
        "",
        "## Execution Checklist",
        ...reviewExecutionChecklistLines(executionChecklist),
        "",
        "## Acceptance Criteria",
        ...reviewMarkdownList([...(Array.isArray(primary.acceptanceCriteria) ? primary.acceptanceCriteria : []), ...executionCriteria], "Decision JSON is validated before issue creation."),
        "",
        "## Validation Plan",
        ...reviewMarkdownList([...(Array.isArray(primary.validationPlan) ? primary.validationPlan : []), ...executionValidation], "Reopen the handoff and confirm the saved result card still matches the issue."),
        "",
        "## Execution Plan",
        ...reviewSavedResultExecutionLines(executionPlan),
        "",
        "## Quality Gate",
        ...(Object.keys(qualityGate).length ? Object.entries(qualityGate).map(([key, value]) => `- ${key}: ${value}`) : ["- No quality gate supplied."]),
        "",
        "## Missing Evidence To Close",
        ...reviewMarkdownList(missingEvidence, "No missing evidence listed by the validated result."),
        "",
        "## Exceptions",
        ...(exceptions.length ? exceptions.map((item) => `- ${item.type || "exception"}: ${item.message || ""}${item.requiredFollowUp ? ` Follow-up: ${item.requiredFollowUp}` : ""}`) : ["- None."]),
      ].filter((line) => line !== "").join("\n");
    }

    function reviewSavedResultNoteBody(model) {
      const data = model || {};
      const saved = data.saved && typeof data.saved === "object" ? data.saved : {};
      const body = data.body == null ? "" : String(data.body);
      return [
        "## Saved Validated Result",
        `- Saved at: ${formatLocalDateTime(saved && saved.savedAt)}`,
        `- Primary key: ${saved && saved.key ? saved.key : "missing"}`,
        `- Payload checksum: ${saved && saved.packageChecksum ? saved.packageChecksum : "missing"}`,
        "",
        ...reviewPinnedNoteSummaryLines(body),
        body,
        "",
        "## Markdown Handoff",
        String(data.handoffText || "").trim(),
      ].filter(Boolean).join("\n");
    }

    function reviewAssigneeFollowUpPanel(model) {
      const data = model || {};
      const items = Array.isArray(data.items) ? data.items : [];
      const examples = Array.isArray(data.examples) ? data.examples : [];
      if (!items.length && !examples.length) return "";
      return html`
        <div class="portfolio-assignee-followup" data-issue-draft-owner-follow-up data-owner-follow-up-ready="true" data-assignee-required-follow-up-count="${items.length}" data-assignee-prompt-example-count="${examples.length}">
          <strong>담당 follow-up</strong>
          ${items.length ? raw(html`<ul>${raw(items.map((item) => html`<li>${item}</li>`).join(""))}</ul>`) : ""}
          ${examples.length ? raw(html`
            <div class="portfolio-assignee-prompt-examples">
              <span>다음 프롬프트 예시</span>
              ${raw(examples.map((item) => html`<code>${item}</code>`).join(""))}
            </div>
          `) : ""}
        </div>
      `;
    }

    function reviewIssueDraftAssigneeOverridePanel(model) {
      const data = model || {};
      const draft = data.draft && typeof data.draft === "object" ? data.draft : {};
      return html`
        <div class="portfolio-assignee-override" data-issue-draft-assignee-review-panel data-assignee-review-required="${draft.assigneeReviewRequired ? "true" : "false"}" data-assignee-confidence="${draft.assigneeConfidence || "none"}" data-assignee-source="${draft.assigneeSource || ""}">
          <label>
            <span>담당 확인</span>
            <select data-issue-draft-assignee-select aria-label="review issue draft assignee override">
              ${raw(data.optionsHTML || "")}
            </select>
          </label>
          <small data-issue-draft-assignee-review-copy>${data.statusText || "담당 확인 필요"} · ${data.confidenceLabel || "확인 필요"} · ${draft.assigneeReason || "매핑 근거 없음"}</small>
        </div>
      `;
    }

    function issueExecutionChecklistControls(model) {
      const data = model || {};
      const items = Array.isArray(data.items) ? data.items : [];
      const progress = data.progress && typeof data.progress === "object" ? data.progress : {};
      const issueId = data.issueId || "";
      if (!items.length) return "";
      return html`
        <div class="sheet-execution-checklist" data-issue-execution-checklist data-issue-execution-checklist-view="review-result-view" data-issue-id="${issueId}" data-execution-checklist-count="${progress.total || items.length}" data-execution-checklist-completed="${progress.done || 0}" data-execution-checklist-done-count="${progress.done || 0}" data-execution-checklist-progress="${progress.percent || 0}" data-execution-checklist-progress-percent="${progress.percent || 0}">
          <div class="sheet-execution-progress">
            <span>${progress.label || "체크리스트 없음"}</span>
            <strong>${progress.percent || 0}%</strong>
          </div>
          <div class="sheet-execution-progress-bar" aria-hidden="true"><span style="width:${progress.percent || 0}%"></span></div>
          <div class="sheet-execution-items">
            ${raw(items.map((item, index) => html`
              <label class="sheet-execution-item ${raw(item.done ? "is-done" : "")}" data-execution-checklist-item-row data-checklist-id="${item.id}">
                <input type="checkbox" data-action="toggle-issue-checklist" data-issue-id="${issueId}" data-checklist-id="${item.id}" data-execution-checklist-toggle ${raw(item.done ? "checked" : "")} />
                <span>${index + 1}. ${item.text}</span>
              </label>
            `).join(""))}
          </div>
        </div>
      `;
    }

    function reviewIssueDraftPanel(model) {
      const data = model || {};
      const draft = data.draft && typeof data.draft === "object" ? data.draft : {};
      const existing = data.existing && typeof data.existing === "object" ? data.existing : null;
      const labels = Array.isArray(draft.labels) ? draft.labels : [];
      const created = !!existing || data.created === true;
      const executionChecklistCount = Number.isFinite(Number(data.executionChecklistCount))
        ? Number(data.executionChecklistCount)
        : (Array.isArray(draft.executionChecklist) ? draft.executionChecklist.length : 0);
      return html`
        <section class="portfolio-review-issue-draft" data-review-issue-draft ${raw(data.scopeAttribute || "")} data-issue-draft-title="${draft.title || ""}" data-issue-draft-project="${draft.projectName || ""}" data-issue-draft-priority="${draft.priority || ""}" data-issue-draft-key="${draft.persistKey || ""}" data-issue-draft-labels="${labels.join(",")}" data-issue-draft-estimate="${draft.estimate || ""}" data-issue-draft-assignee="${draft.assignee || ""}" data-issue-draft-assignee-override="${draft.assigneeOverride ? "true" : "false"}" data-issue-draft-assignee-override-saved-at="${draft.assigneeOverrideSavedAt || ""}" data-issue-draft-assignee-confidence="${draft.assigneeConfidence || "none"}" data-issue-draft-assignee-source="${draft.assigneeSource || ""}" data-issue-draft-assignee-review="${draft.assigneeReviewRequired ? "true" : "false"}" data-issue-draft-assignee-required-follow-up-count="${(draft.assigneeRequiredFollowUp || []).length}" data-issue-draft-assignee-prompt-example-count="${(draft.assigneePromptExamples || []).length}" data-issue-draft-owner-follow-up-ready="${draft.assigneeFollowUpReady ? "true" : "false"}" data-issue-draft-due="${draft.due || ""}" data-issue-draft-tracker-ready="${draft.trackerReady ? "true" : "false"}" data-issue-draft-execution-owner="${draft.executionOwner || ""}" data-issue-draft-execution-checklist-count="${executionChecklistCount}" data-issue-draft-execution-checklist-ready="${draft.executionChecklistReady ? "true" : "false"}" data-issue-draft-result-source="${draft.resultSource || "static"}" data-issue-draft-saved-result-at="${draft.savedResultAt || ""}" data-issue-draft-package-checksum="${draft.packageChecksum || ""}" data-issue-draft-created="${created ? "true" : "false"}" data-issue-draft-id="${existing ? existing.id || "" : ""}">
          <div class="portfolio-issue-draft-head">
            <span>${data.title || "PM issue draft"}</span>
            ${draft.resultSource === "validated" ? raw(html`<small class="portfolio-issue-draft-source" data-issue-draft-validated-source>검증 JSON 적용</small>`) : ""}
            <button type="button" class="portfolio-export-download portfolio-issue-draft-create" data-action="create-review-issue" data-review-issue-create ${raw(data.createAttribute || "")} data-review-issue-key="${draft.persistKey || ""}" data-review-issue-existing="${raw(created ? "true" : "false")}">${created ? "기존 이슈 열기" : "이슈 생성"}</button>
          </div>
          <div class="portfolio-issue-draft-grid">
            <div>
              <span>제목</span>
              <strong>${draft.title || ""}</strong>
            </div>
            <div>
              <span>프로젝트</span>
              <strong>${draft.projectName || ""}</strong>
            </div>
            <div>
              <span>우선순위</span>
              <strong>${data.priorityLabel || draft.priority || "-"}</strong>
            </div>
            <div>
              <span>담당</span>
              <strong>${data.assigneeLabel || (draft.assignee ? memberName(draft.assignee) : "미지정")}</strong>
            </div>
            <div>
              <span>마감</span>
              <strong>${draft.due || "—"}</strong>
            </div>
            <div>
              <span>예상</span>
              <strong>${draft.estimate || 0}h</strong>
            </div>
            <div>
              <span>체크리스트</span>
              <strong>${data.checklistLabel || `${executionChecklistCount}개`}</strong>
            </div>
          </div>
          ${raw(data.assigneeOverridePanel || "")}
          ${raw(data.assigneeFollowUpPanel || "")}
          <pre class="portfolio-issue-draft-body" data-issue-draft-body>${draft.body || ""}</pre>
          ${raw(data.artifactDiffPanel || "")}
        </section>
      `;
    }

    function reviewGithubCommentMarkdown(model) {
      const data = model || {};
      const decisions = Array.isArray(data.decisions) ? data.decisions : [];
      const draft = data.draft && typeof data.draft === "object" ? data.draft : null;
      if (!decisions.length || !draft) return "";
      const primary = decisions[0] || {};
      const primaryDecision = primary.decision || {};
      const primaryProject = primary.project || {};
      const secondary = decisions.find((item) => Number(item && item.decision && item.decision.rank) > 1);
      const secondaryDecision = secondary && secondary.decision ? secondary.decision : null;
      const secondaryProject = secondary && secondary.project ? secondary.project : null;
      const labels = Array.isArray(draft.labels) ? draft.labels : [];
      const primaryScore = primaryDecision.score == null ? "missing" : primaryDecision.score;
      const secondaryScore = secondaryDecision && secondaryDecision.score == null ? "missing" : secondaryDecision ? secondaryDecision.score : "missing";
      return [
        `## ${data.title || "JooPark Review"}`,
        "",
        ...reviewCommentDecisionSummaryLines({
          primaryDecision,
          primaryProject,
          secondaryDecision,
          secondaryProject,
          draft,
        }),
        "",
        `Primary decision key: ${primaryDecision.persistKey || draft.persistKey || "missing"}`,
        `Recommendation: ${primaryProject.name || "missing"} ${primaryDecision.status || "missing"} (${primaryDecision.label || "score"} ${primaryScore})`,
        primaryDecision.surface ? `Surface: ${primaryDecision.surface}` : "",
        primaryDecision.reason ? `Reason: ${primaryDecision.reason}` : "",
        secondaryDecision && secondaryProject ? `Compare with: ${secondaryProject.name} ${secondaryDecision.status || "missing"} (${secondaryDecision.label || "score"} ${secondaryScore})` : "",
        "",
        "## Issue Draft",
        `Title: ${draft.title || "missing"}`,
        `Priority: ${draft.priority || "missing"}`,
        `Labels: ${labels.join(", ") || "none"}`,
        `Estimate: ${draft.estimate || "missing"}`,
        "",
        draft.body || "",
      ].filter(Boolean).join("\n");
    }

    function reviewGithubCommentDraftPanel(model) {
      const data = model || {};
      const key = data.key || "";
      return html`
        <section class="portfolio-review-issue-draft portfolio-review-github-comment" ${raw(data.scopeAttribute || "")} data-review-github-comment-key="${key}" data-review-github-comment-target="${data.target || ""}" data-review-github-comment-format="markdown">
          <div class="portfolio-issue-draft-head">
            <span>${data.title || "GitHub comment draft"}</span>
            <div class="portfolio-export-actions">
              ${data.issueUrl ? raw(html`<a class="portfolio-export-download" ${raw(data.openAttribute || "")} href="${data.issueUrl}" target="_blank" rel="noopener">이슈 열기</a>`) : ""}
              <button type="button" class="portfolio-export-download portfolio-export-copy" data-action="copy-review-github-comment" data-review-github-comment-copy ${raw(data.copyAttribute || "")} data-review-github-comment-copy-key="${key}">댓글 복사</button>
            </div>
          </div>
          <small class="portfolio-export-status" data-review-github-comment-copy-status ${raw(data.statusAttribute || "")} aria-live="polite"></small>
          <pre class="portfolio-issue-draft-body" data-review-github-comment-text ${raw(data.textAttribute || "")}>${data.comment || ""}</pre>
        </section>
      `;
    }

    function reviewResultRepairSuggestion(failure, expectedKey) {
      const text = String(failure || "");
      if (/JSON 파싱 실패|JSON/i.test(text)) {
        return "Return one valid JSON object first. Remove comments, trailing Markdown before the JSON, dangling commas, and unquoted property names.";
      }
      if (text.includes("schemaVersion")) return `Set schemaVersion exactly to ${schemaVersion}.`;
      if (text.includes("primaryDecisionKey")) return `Set primaryDecisionKey exactly to ${expectedKey || "the handoff primary decision key"}.`;
      if (text.includes("recommendedAction")) return "Set recommendedAction to adopt, compare, watch, or defer.";
      if (text.includes("confidence")) return "Set confidence to high, medium, or low.";
      if (text.includes("decisions")) return "Keep decisions as an array and include the primary persistKey with source-backed rationale.";
      if (text.includes("acceptanceCriteria")) return "Add checklist-ready acceptanceCriteria with concrete pass/fail outcomes.";
      if (text.includes("validationPlan")) return "Add checklist-ready validationPlan steps that can be run before issue or note creation.";
      if (text.includes("missingEvidence")) return "Set missingEvidence to an array, even when there are no gaps.";
      if (text.includes("sourceSnapshot")) return "Include sourceSnapshot evidence from the handoff instead of inventing repository facts.";
      if (text.includes("decisionGate")) return "Add decisionGate that states when to proceed, compare, or stop.";
      if (text.includes("fallbackIfBlocked")) return "Add fallbackIfBlocked that prevents unsafe external completion claims.";
      if (text.includes("owner")) return "Use an exact active team member when possible, or add exceptions.requiredFollowUp for exact assignee confirmation.";
      if (text.includes("qualityGate")) return "Add qualityGate with explicit pass/fail evidence for the review output.";
      if (text.includes("executionPlan")) return "Add executionPlan with action, firstAction, owner, timeboxHours, decisionGate, fallbackIfBlocked, acceptanceCriteria, and validationPlan.";
      if (text.includes("exceptions")) return "Set exceptions to an array and include requiredFollowUp when evidence or ownership is ambiguous.";
      if (text.includes("uiArtifacts.markdownSummary")) return "Add uiArtifacts.markdownSummary as a concise tracker-ready summary.";
      return "Repair this field using only the handoff evidence, then rerun the result validator before creating an issue or note.";
    }

    function reviewResultRepairRequiredFields(expectedKey) {
      return [
        `schemaVersion must equal ${schemaVersion}`,
        `primaryDecisionKey must equal ${expectedKey || "the handoff primary decision key"}`,
        "recommendedAction must be one of adopt, compare, watch, defer",
        "confidence must be one of high, medium, low",
        "decisions[] must include the primary persistKey plus checklist-ready acceptanceCriteria, validationPlan, and missingEvidence[]",
        "sourceSnapshot[] must preserve source URL, commit/pushedAt evidence, project, and persist key from the handoff",
        "qualityGate must state pass/fail evidence for the generated review output",
        "executionPlan[] must include action, firstAction, owner, timeboxHours, decisionGate, fallbackIfBlocked, acceptanceCriteria, and validationPlan",
        "exceptions must be an array and include requiredFollowUp when evidence or ownership is ambiguous",
        "uiArtifacts.markdownSummary must be a concise tracker-ready summary",
      ];
    }

    function reviewResultRepairActionPlan({ state, expectedKey, failures, warnings }) {
      const safeFailures = Array.isArray(failures) ? failures : [];
      const safeWarnings = Array.isArray(warnings) ? warnings : [];
      const primaryTarget = safeFailures.length
        ? `${safeFailures.length} validation failure(s); fix these before warnings.`
        : `${safeWarnings.length} warning(s); review before downstream use.`;
      return [
        "Repair action plan:",
        `- Primary fix target: ${primaryTarget}`,
        `- Schema identity: keep schemaVersion ${schemaVersion} and primaryDecisionKey ${expectedKey || "the handoff primary decision key"}.`,
        "- Evidence boundary: copy facts only from the handoff sourceSnapshot and decision evidence; do not invent repository facts or launch proof.",
        "- First action: return one corrected JSON object that satisfies Required JSON fields before adding commentary.",
        "- Validation gate: rerun the result validator and save only after state=pass with zero validation failures.",
        "- Stop condition: do not create an issue, note, or archived repair until the post-repair receipt and artifact receipt are paired.",
      ];
    }

    function reviewResultRepairScaffold(expectedKey, reviewType) {
      return JSON.stringify({
        schemaVersion,
        primaryDecisionKey: expectedKey || "paste primary decision key",
        recommendedAction: "compare",
        confidence: "medium",
        decisions: [
          {
            persistKey: expectedKey || "paste primary decision key",
            project: "copy primary project from the handoff",
            status: "candidate_ready_or_needs_review",
            score: 0,
            rationale: "source-backed rationale from the handoff evidence",
            acceptanceCriteria: ["Checklist-ready acceptance criterion with a concrete pass/fail outcome."],
            validationPlan: ["Concrete validation step to run before issue or note creation."],
            missingEvidence: [],
          },
        ],
        sourceSnapshot: [
          {
            project: "copy project from Evidence Snapshot",
            sourceUrl: "copy source URL from Evidence Snapshot",
            commit: "copy commit from Evidence Snapshot or write unknown",
            pushedAt: "copy pushedAt from Evidence Snapshot or write unknown",
            persistKey: expectedKey || "paste primary decision key",
          },
        ],
        qualityGate: {
          status: "pass_or_needs_review",
          evidence: "name the concrete handoff evidence used",
        },
        executionPlan: [
          {
            action: reviewType ? `${reviewType} follow-up` : "review follow-up",
            firstAction: "First concrete action an assignee can take without reinterpreting the review.",
            owner: "exact assignee or role from the handoff",
            timeboxHours: 4,
            decisionGate: "Observable condition that decides adopt, compare, watch, defer, or stop.",
            fallbackIfBlocked: "Safe fallback that avoids claiming external completion without evidence.",
            acceptanceCriteria: ["Checklist-ready execution acceptance criterion."],
            validationPlan: ["Concrete validation step for the execution plan."],
          },
        ],
        exceptions: [],
        missingEvidence: [],
        uiArtifacts: {
          markdownSummary: "Copy-ready summary for the tracker or note.",
        },
      }, null, 2);
    }

    function reviewResultRepairPacket({ state, reviewType, expectedKey, failures, warnings }) {
      const safeFailures = Array.isArray(failures) ? failures : [];
      const safeWarnings = Array.isArray(warnings) ? warnings : [];
      if (state !== "fail" && safeWarnings.length === 0) return "";
      const repairItems = safeFailures.length ? safeFailures : safeWarnings;
      const instructions = Array.from(new Set(repairItems.map((failure) => reviewResultRepairSuggestion(failure, expectedKey))));
      const requiredFields = reviewResultRepairRequiredFields(expectedKey);
      return [
        "JooPark Review Result Repair Packet",
        `Status: ${state === "fail" ? "action required - validation failed" : "warning - review before downstream use"}`,
        `Review type: ${reviewType || "unknown"}`,
        `Expected schemaVersion: ${schemaVersion}`,
        `Expected primaryDecisionKey: ${expectedKey || "unknown"}`,
        "",
        ...reviewResultRepairActionPlan({ state, expectedKey, failures: safeFailures, warnings: safeWarnings }),
        "",
        "Validation failures:",
        ...(safeFailures.length ? safeFailures.map((failure, index) => `${index + 1}. ${failure}`) : ["- none"]),
        "",
        "Warnings:",
        ...(safeWarnings.length ? safeWarnings.map((warning, index) => `${index + 1}. ${warning}`) : ["- none"]),
        "",
        "Repair instructions:",
        ...instructions.map((instruction, index) => `${index + 1}. ${instruction}`),
        "",
        "Required JSON fields:",
        ...requiredFields.map((field, index) => `${index + 1}. ${field}`),
        "",
        "Correction scaffold:",
        "```json",
        reviewResultRepairScaffold(expectedKey, reviewType),
        "```",
        "",
        "Guard:",
        "- Use only the candidate evidence supplied in the handoff.",
        "- Do not claim install, publish, purchase, credential use, or external completion unless evidence proves it.",
        "- Return corrected JSON first, with uiArtifacts.markdownSummary populated.",
        "- Rerun the result validator before creating issues or notes.",
      ].join("\n");
    }

    function reviewResultRepairReceiptMarkdown(model) {
      const data = model || {};
      const previous = data.previous && typeof data.previous === "object" ? data.previous : {};
      const result = data.result && typeof data.result === "object" ? data.result : {};
      const saved = data.saved && typeof data.saved === "object" ? data.saved : {};
      const previousFailures = Array.isArray(previous.failures) ? previous.failures : [];
      const previousWarnings = Array.isArray(previous.warnings) ? previous.warnings : [];
      const warnings = Array.isArray(data.warnings) ? data.warnings : [];
      const summary = result && result.uiArtifacts && result.uiArtifacts.markdownSummary
        ? result.uiArtifacts.markdownSummary
        : saved.summary || "No summary supplied.";
      return [
        "# JooPark Review Result Post-Repair Receipt",
        "",
        "- Status: repaired validation pass",
        `- Review type: ${data.reviewType || previous.reviewType || result.reviewType || "unknown"}`,
        `- Primary key: ${data.expectedKey || previous.expectedKey || result.primaryDecisionKey || saved.key || "missing"}`,
        `- Repaired at: ${data.repairedAt || nowISO()}`,
        `- Previous state: ${previous.state || "unknown"}`,
        `- Previous failure count: ${previousFailures.length}`,
        `- Previous warning count: ${previousWarnings.length}`,
        `- Saved payload checksum: ${saved.packageChecksum || "missing"}`,
        "",
        "## Previous Failure Evidence",
        ...(previousFailures.length ? previousFailures.map((failure, index) => `${index + 1}. ${failure}`) : ["- none"]),
        "",
        "## Previous Warning Evidence",
        ...(previousWarnings.length ? previousWarnings.map((warning, index) => `${index + 1}. ${warning}`) : ["- none"]),
        "",
        "## Corrected Result",
        `- schemaVersion: ${result.schemaVersion || saved.schemaVersion || "missing"}`,
        `- primaryDecisionKey: ${result.primaryDecisionKey || saved.key || "missing"}`,
        `- recommendedAction: ${result.recommendedAction || saved.recommendedAction || "missing"} (${reviewActionLabel(result.recommendedAction || saved.recommendedAction)})`,
        `- confidence: ${result.confidence || saved.confidence || "missing"} (${reviewConfidenceLabel(result.confidence || saved.confidence)})`,
        `- summary: ${summary}`,
        "",
        "## Current Warnings",
        ...(warnings.length ? warnings.map((warning, index) => `${index + 1}. ${warning}`) : ["- none"]),
        "",
        "## Downstream Guard",
        "- Pair this receipt with the created issue or note artifact receipt before archiving the repair as complete.",
        "- Do not claim external publish, install, or launch completion until artifact diff and publish evidence gates pass.",
      ].join("\n");
    }

    function reviewResultPostRepairReceiptPanel(model) {
      const data = model || {};
      const previous = data.previous && typeof data.previous === "object" ? data.previous : {};
      const previousFailures = Array.isArray(previous.failures) ? previous.failures : [];
      const previousWarnings = Array.isArray(previous.warnings) ? previous.warnings : [];
      if (!previous.state || (previousFailures.length === 0 && previousWarnings.length === 0)) return "";
      const saved = data.saved && typeof data.saved === "object" ? data.saved : {};
      const receipt = reviewResultRepairReceiptMarkdown(data);
      return html`
        <div class="review-result-repair-receipt" data-review-result-repair-receipt data-review-result-repair-receipt-ready="true" data-review-result-repair-receipt-failure-count="${previousFailures.length}" data-review-result-repair-receipt-warning-count="${previousWarnings.length}" data-review-result-repair-receipt-checksum="${saved.packageChecksum || ""}">
          <strong>post-repair receipt</strong>
          <p>이전 실패와 수정된 pass 결과를 함께 보관해 issue/note 생성 전 수리 증거로 사용할 수 있습니다.</p>
          <dl>
            <div><dt>previous</dt><dd>${previous.state || "unknown"} · ${previousFailures.length} failures</dd></div>
            <div><dt>checksum</dt><dd>${saved.packageChecksum || "missing"}</dd></div>
          </dl>
          <pre data-review-result-repair-receipt-text>${receipt}</pre>
          <div class="review-result-repair-actions">
            <button type="button" class="portfolio-export-download portfolio-export-copy" data-action="copy-review-result-repair-receipt" data-review-result-repair-receipt-copy>post-repair receipt 복사</button>
            <small class="portfolio-export-status" data-review-result-repair-receipt-copy-status role="status" aria-live="polite" aria-atomic="true"></small>
          </div>
        </div>
      `;
    }

    function reviewResultValidationOutput(options) {
      const { state, result, failures, warnings, expectedKey, reviewType } = options || {};
      if (state === "empty") return "";
      const safeFailures = Array.isArray(failures) ? failures : [];
      const safeWarnings = Array.isArray(warnings) ? warnings : [];
      const summary = result && result.uiArtifacts && result.uiArtifacts.markdownSummary
        ? result.uiArtifacts.markdownSummary
        : "";
      const repairPacket = reviewResultRepairPacket({ state, reviewType, expectedKey, failures: safeFailures, warnings: safeWarnings });
      const postRepairReceipt = state === "pass" ? reviewResultPostRepairReceiptPanel(options && options.repairReceipt) : "";
      return html`
        <div class="review-result-card review-result-${state}" data-review-result-card>
          <strong>${state === "pass" ? "검증 통과" : "검증 실패"}</strong>
          ${summary ? raw(html`<p data-review-result-summary>${summary}</p>`) : ""}
          ${safeFailures.length ? raw(html`<ul data-review-result-failures>${raw(safeFailures.map((item) => html`<li>${item}</li>`).join(""))}</ul>`) : ""}
          ${safeWarnings.length ? raw(html`<ul data-review-result-warnings>${raw(safeWarnings.map((item) => html`<li>${item}</li>`).join(""))}</ul>`) : ""}
          ${repairPacket ? raw(html`
            <div class="review-result-repair" data-review-result-repair data-review-result-repair-ready="true">
              <strong>repair packet</strong>
              <p>실패 원인과 수정 지침을 그대로 복사해 JSON 재생성 요청에 붙여넣을 수 있습니다.</p>
              <pre data-review-result-repair-text>${repairPacket}</pre>
              <div class="review-result-repair-actions">
                <button type="button" class="portfolio-export-download portfolio-export-copy" data-action="copy-review-result-repair" data-review-result-repair-copy>repair packet 복사</button>
                <small class="portfolio-export-status" data-review-result-repair-copy-status role="status" aria-live="polite" aria-atomic="true"></small>
              </div>
            </div>
          `) : ""}
          ${postRepairReceipt ? raw(postRepairReceipt) : ""}
        </div>
      `;
    }

    return {
      version: VERSION,
      reviewActionLabel,
      reviewConfidenceLabel,
      reviewResultSavedCard,
      compactReviewResult,
      reviewSavedResultBody,
      reviewSavedResultNoteBody,
      reviewAssigneeFollowUpPanel,
      reviewIssueDraftAssigneeOverridePanel,
      issueExecutionChecklistControls,
      reviewIssueDraftPanel,
      reviewGithubCommentMarkdown,
      reviewGithubCommentDraftPanel,
      reviewResultRepairPacket,
      reviewResultRepairReceiptMarkdown,
      reviewResultPostRepairReceiptPanel,
      reviewResultValidationOutput,
    };
  }

  root.JooParkReviewResultView = {
    version: VERSION,
    create: createReviewResultView,
  };
})(window);
