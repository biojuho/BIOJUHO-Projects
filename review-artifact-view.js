(function (root) {
  "use strict";

  const VERSION = "joopark-review-artifact-view/v1";

  function createReviewArtifactView(deps) {
    const options = deps || {};
    const html = options.html;
    const raw = options.raw;
    const clampText = typeof options.clampText === "function"
      ? options.clampText
      : function (value, max) {
        const text = String(value == null ? "" : value);
        return max > 0 && text.length > max ? text.slice(0, max) : text;
      };
    const promptTableCell = typeof options.promptTableCell === "function"
      ? options.promptTableCell
      : function (value) {
        return String(value == null ? "" : value).replace(/\s+/g, " ").trim().replace(/\|/g, "\\|") || "-";
      };
    const formatLocalDateTime = typeof options.formatLocalDateTime === "function"
      ? options.formatLocalDateTime
      : function (value) { return value || ""; };
    const escapeHtml = typeof options.escapeHtml === "function"
      ? options.escapeHtml
      : function (value) {
        return String(value == null ? "" : value)
          .replace(/&/g, "&amp;")
          .replace(/</g, "&lt;")
          .replace(/>/g, "&gt;")
          .replace(/"/g, "&quot;")
          .replace(/'/g, "&#39;");
      };
    const reviewArtifactRepairUndoFor = typeof options.reviewArtifactRepairUndoFor === "function"
      ? options.reviewArtifactRepairUndoFor
      : function () { return null; };

    if (typeof html !== "function" || typeof raw !== "function") {
      throw new Error("review artifact view requires html and raw helpers");
    }

    function reviewArtifactDiffSnippet(text) {
      const lines = String(text || "").split("\n")
        .map((line) => line.trim())
        .filter(Boolean);
      const terms = [
        "## Validated Review Result",
        "## Saved Validated Result",
        "## Decision",
        "## Source Snapshot",
        "## Bundle Manifest",
        "## Operational Readiness",
        "Payload checksum",
        "First action",
        "Decision gate",
        "Fallback if blocked",
        "## Acceptance Criteria",
        "## Validation Plan",
        "Source URL",
        "Primary decision key",
        "Source: validated",
      ];
      const picked = [];
      const seen = new Set();
      lines.forEach((line) => {
        if (picked.length >= 12) return;
        const lower = line.toLowerCase();
        if (!terms.some((term) => lower.includes(term.toLowerCase()))) return;
        if (seen.has(line)) return;
        picked.push(line);
        seen.add(line);
      });
      lines.forEach((line) => {
        if (picked.length >= 12 || seen.has(line)) return;
        picked.push(line);
        seen.add(line);
      });
      return clampText((picked.length ? picked : ["No artifact content."]).join("\n"), 1400);
    }

    function reviewArtifactDiffChecks({ createdBody, sourceKind }) {
      const body = String(createdBody || "");
      const source = String(sourceKind || "");
      const checks = [
        {
          id: "validated_source",
          label: "Validated source",
          status: source.includes("validated-review-result") && body.includes("## Validated Review Result") ? "pass" : "pending",
        },
        {
          id: "checksum",
          label: "Payload checksum",
          status: body.includes("Payload checksum: fnv1a32-") ? "pass" : "pending",
        },
        {
          id: "acceptance",
          label: "Acceptance criteria",
          status: body.includes("## Acceptance Criteria") ? "pass" : "pending",
        },
        {
          id: "validation",
          label: "Validation plan",
          status: body.includes("## Validation Plan") ? "pass" : "pending",
        },
        {
          id: "source_snapshot",
          label: "Source snapshot",
          status: body.includes("## Source Snapshot") || body.includes("Source URL:") ? "pass" : "pending",
        },
        {
          id: "operational_readiness",
          label: "Operational readiness",
          status: body.includes("## Operational Readiness")
            && body.includes("Owner:")
            && body.includes("First action:")
            && body.includes("Decision gate:")
            && body.includes("Fallback if blocked:")
            && !body.includes("No decision gate supplied.")
            && !body.includes("No fallback supplied.")
            ? "pass"
            : "pending",
        },
        {
          id: "execution_checklist",
          label: "Execution checklist",
          status: body.includes("## Execution Checklist") && /- \[[ x]\] /i.test(body) ? "pass" : "pending",
        },
      ];
      if (body.includes("## Repair Evidence") || body.includes("JooPark Review Result Post-Repair Receipt")) {
        checks.push({
          id: "repair_evidence",
          label: "Repair evidence linked",
          status: body.includes("## Repair Evidence")
            && body.includes("JooPark Review Result Post-Repair Receipt")
            && body.includes("Previous Failure Evidence")
            && body.includes("Post-repair receipt checksum: fnv1a32-")
            ? "pass"
            : "pending",
        });
      }
      return checks;
    }

    function reviewArtifactReceiptMarkdown({ kind, key, status, sourceKind, createdId, artifactType, createdBody, checks }) {
      const rows = Array.isArray(checks) ? checks : [];
      return [
        "# JooPark Review Artifact Receipt",
        "",
        "## Artifact",
        `- Artifact kind: ${kind || "missing"}`,
        `- Artifact type: ${artifactType || "missing"}`,
        `- Artifact id: ${createdId || "missing"}`,
        `- Primary key: ${key || "missing"}`,
        `- Source kind: ${sourceKind || "missing"}`,
        `- Diff status: ${status || "missing"}`,
        "",
        "## Checks",
        "| check | status |",
        "| --- | --- |",
        ...rows.map((check) => `| ${promptTableCell(check.label)} | ${promptTableCell(check.status)} |`),
        "",
        "## Created Artifact Body",
        String(createdBody || "").trim(),
      ].join("\n");
    }

    function parseReviewArtifactReceipt(text) {
      const rawText = String(text || "");
      const lines = rawText.split(/\r?\n/);
      const meta = {};
      const checks = [];
      let section = "";
      const bodyLines = [];
      lines.forEach((line) => {
        if (section === "created artifact body") {
          bodyLines.push(line);
          return;
        }
        const heading = line.match(/^##\s+(.+?)\s*$/);
        if (heading) {
          section = heading[1].trim().toLowerCase();
          return;
        }
        if (section === "artifact") {
          const match = line.match(/^-\s+([^:]+):\s*(.*)$/);
          if (match) meta[match[1].trim().toLowerCase()] = match[2].trim();
          return;
        }
        if (section === "checks") {
          if (!line.startsWith("|") || /---/.test(line) || /check\s*\|\s*status/i.test(line)) return;
          const cells = line.slice(1, line.endsWith("|") ? -1 : undefined).split("|").map((cell) => cell.trim().replace(/\\\|/g, "|"));
          if (cells.length >= 2 && cells[0]) checks.push({ label: cells[0], status: cells[1] || "" });
        }
      });
      const body = bodyLines.join("\n").trim();
      return {
        valid: rawText.includes("# JooPark Review Artifact Receipt") && !!body,
        raw: rawText,
        artifactKind: meta["artifact kind"] || "",
        artifactType: meta["artifact type"] || "",
        artifactId: meta["artifact id"] || "",
        primaryKey: meta["primary key"] || "",
        sourceKind: meta["source kind"] || "",
        diffStatus: meta["diff status"] || "",
        checks,
        body,
      };
    }

    function reviewArtifactReceiptRepairSuggestion(checkId) {
      const suggestions = {
        receipt_present: "Paste the unedited JooPark Review Artifact Receipt that includes Artifact metadata, Checks, and Created Artifact Body before comparing.",
        primary_key: "Open the artifact diff for the archived primary key, or replace this archived receipt with the current panel receipt before sharing.",
        artifact_id: "Compare the archived receipt with the same generated issue/note; if the current artifact is correct, archive a fresh receipt from this panel.",
        artifact_type: "Compare issue receipts with issue panels and note receipts with note panels, then save a fresh receipt from the matching artifact type.",
        source_kind: "Regenerate the artifact from the validated-review-result source, or replace the archived receipt with a receipt from the current validated source.",
        diff_status: "Archive a fresh receipt after the current diff status returns to pass; do not share a pending or failed receipt.",
        body_match: "If the archived receipt is authoritative, restore its Created Artifact Body in the current issue/note; otherwise replace the archived receipt with the current one.",
        checks_match: "Rerun validation and create a fresh receipt so every check row matches the current pass state.",
      };
      return suggestions[checkId] || "Review the archived receipt against the current artifact, then replace whichever side is no longer authoritative.";
    }

    function reviewArtifactReceiptCheckSignature(checks) {
      return (checks || []).map((check) => `${check.label}:${check.status}`).join("\n");
    }

    function reviewArtifactReceiptChecksPass(checks) {
      const rows = Array.isArray(checks) ? checks : [];
      return rows.length > 0 && rows.every((check) => check.status === "pass");
    }

    function reviewArtifactReceiptComparison(receipt, current) {
      const sameCheckRows = reviewArtifactReceiptCheckSignature(receipt.checks) === reviewArtifactReceiptCheckSignature(current.checks);
      const currentChecksPass = reviewArtifactReceiptChecksPass(current.checks);
      const rows = [
        {
          id: "receipt_present",
          label: "Receipt present",
          status: receipt.valid && !!receipt.primaryKey && !!receipt.body ? "pass" : "fail",
          reason: receipt.valid ? "archived receipt parsed" : "paste a JooPark artifact receipt",
        },
        {
          id: "primary_key",
          label: "Primary key",
          status: receipt.primaryKey && receipt.primaryKey === current.primaryKey ? "pass" : "fail",
          reason: `${receipt.primaryKey || "missing"} -> ${current.primaryKey || "missing"}`,
        },
        {
          id: "artifact_id",
          label: "Artifact id",
          status: receipt.artifactId && receipt.artifactId === current.artifactId ? "pass" : "fail",
          reason: `${receipt.artifactId || "missing"} -> ${current.artifactId || "missing"}`,
        },
        {
          id: "artifact_type",
          label: "Artifact type",
          status: receipt.artifactType && receipt.artifactType === current.artifactType ? "pass" : "fail",
          reason: `${receipt.artifactType || "missing"} -> ${current.artifactType || "missing"}`,
        },
        {
          id: "source_kind",
          label: "Source kind",
          status: receipt.sourceKind && receipt.sourceKind === current.sourceKind ? "pass" : "fail",
          reason: `${receipt.sourceKind || "missing"} -> ${current.sourceKind || "missing"}`,
        },
        {
          id: "diff_status",
          label: "Diff status",
          status: receipt.diffStatus === "pass" && current.diffStatus === "pass" ? "pass" : "fail",
          reason: `${receipt.diffStatus || "missing"} -> ${current.diffStatus || "missing"}`,
        },
        {
          id: "body_match",
          label: "Body exact match",
          status: receipt.body.trim() === current.body.trim() ? "pass" : "fail",
          reason: receipt.body.trim() === current.body.trim() ? "created body unchanged" : "created body drifted",
        },
        {
          id: "checks_match",
          label: "Checks match",
          status: sameCheckRows && currentChecksPass ? "pass" : "fail",
          reason: sameCheckRows ? "check rows unchanged" : "check rows drifted",
        },
      ];
      return rows.map((check) => ({
        ...check,
        repair: check.status === "pass" ? "" : reviewArtifactReceiptRepairSuggestion(check.id),
        receiptBody: receipt.body || "",
        currentReceipt: current.raw || "",
      }));
    }

    function reviewArtifactReceiptCompareOutput(checks) {
      const rows = Array.isArray(checks) ? checks : [];
      const pass = reviewArtifactReceiptChecksPass(rows);
      const repairs = rows.filter((check) => check.status !== "pass" && check.repair);
      const archivedBodyRepair = repairs.some((check) => check.id === "body_match")
        ? rows.find((check) => check.id === "body_match")?.receiptBody || ""
        : "";
      const freshReceiptRepair = repairs.length ? rows.find((check) => check.currentReceipt)?.currentReceipt || "" : "";
      return html`
        <div class="review-result-card review-result-${pass ? "pass" : "fail"}" data-review-artifact-receipt-compare-card>
          <strong>${pass ? "receipt 비교 통과" : "receipt 비교 실패"}</strong>
          <ul data-review-artifact-receipt-compare-list>
            ${raw(rows.map((check) => html`
              <li data-review-artifact-receipt-compare-check data-review-artifact-receipt-compare-check-id="${check.id}" data-review-artifact-receipt-compare-check-status="${check.status}">
                <span>${check.label}</span>
                <strong>${check.status}</strong>
                <small>${check.reason}</small>
              </li>
            `).join(""))}
          </ul>
          ${repairs.length ? raw(html`
            <div class="review-artifact-receipt-repair" data-review-artifact-receipt-repair>
              <strong>Repair suggestions</strong>
              <div class="review-artifact-receipt-repair-actions">
                ${archivedBodyRepair ? raw(html`<button type="button" class="portfolio-export-download portfolio-export-copy" data-action="copy-review-artifact-repair-body" data-review-artifact-repair-body-copy>archived body 복사</button>`) : ""}
                ${archivedBodyRepair ? raw(html`<button type="button" class="portfolio-export-download portfolio-export-copy" data-action="preview-review-artifact-repair-apply" data-review-artifact-repair-apply>archived body 적용</button>`) : ""}
                ${freshReceiptRepair ? raw(html`<button type="button" class="portfolio-export-download portfolio-export-copy" data-action="copy-review-artifact-repair-receipt" data-review-artifact-repair-receipt-copy>fresh receipt 복사</button>`) : ""}
              </div>
              <ol data-review-artifact-receipt-repair-list>
                ${raw(repairs.map((check) => html`
                  <li data-review-artifact-receipt-repair-item data-review-artifact-receipt-repair-check-id="${check.id}">
                    <span>${check.label}</span>
                    <p>${check.repair}</p>
                  </li>
                `).join(""))}
              </ol>
              ${archivedBodyRepair ? raw(html`<pre data-review-artifact-repair-body-text hidden>${archivedBodyRepair}</pre>`) : ""}
              ${freshReceiptRepair ? raw(html`<pre data-review-artifact-repair-receipt-text hidden>${freshReceiptRepair}</pre>`) : ""}
              <small class="portfolio-export-status" data-review-artifact-repair-copy-status aria-live="polite"></small>
            </div>
          `) : ""}
        </div>
      `;
    }

    function reviewPostRepairArtifactLinkMarkdown({ repairReceiptMarkdown, artifactReceiptMarkdown, key, artifactType, createdId, status }) {
      const repairReceipt = String(repairReceiptMarkdown || "").trim();
      const artifactReceipt = String(artifactReceiptMarkdown || "").trim();
      const savedChecksumMatch = repairReceipt.match(/Saved payload checksum:\s*([^\n]+)/i);
      const savedChecksum = savedChecksumMatch ? savedChecksumMatch[1].trim() : "missing";
      const keyMatch = !!key && repairReceipt.includes(`Primary key: ${key}`);
      const artifactReceiptReady = artifactReceipt.includes("# JooPark Review Artifact Receipt") && artifactReceipt.includes(`- Primary key: ${key || "missing"}`);
      const linkStatus = repairReceipt && artifactReceiptReady && keyMatch && status === "pass" ? "pass" : "pending";
      return [
        "# JooPark Review Post-Repair Artifact Link",
        "",
        "- Status: " + linkStatus,
        `- Primary key: ${key || "missing"}`,
        `- Artifact type: ${artifactType || "missing"}`,
        `- Artifact id: ${createdId || "missing"}`,
        `- Artifact diff status: ${status || "missing"}`,
        `- Repair receipt present: ${repairReceipt ? "yes" : "no"}`,
        `- Repair receipt key match: ${keyMatch ? "pass" : "fail"}`,
        `- Artifact receipt present: ${artifactReceiptReady ? "yes" : "no"}`,
        `- Saved payload checksum: ${savedChecksum}`,
        "",
        "## Guard",
        "- Archive this link only with both the post-repair receipt and the current artifact receipt.",
        "- If artifact diff status is not pass, create a fresh artifact receipt after repair before sharing completion.",
      ].join("\n");
    }

    function reviewPostRepairArtifactLinkPanel({ repairReceiptMarkdown, artifactReceiptMarkdown, key, artifactType, createdId, status }) {
      const repairReceipt = String(repairReceiptMarkdown || "").trim();
      if (!repairReceipt) return "";
      const artifactReceipt = String(artifactReceiptMarkdown || "").trim();
      const keyMatch = !!key && repairReceipt.includes(`Primary key: ${key}`);
      const artifactReceiptReady = artifactReceipt.includes("# JooPark Review Artifact Receipt") && artifactReceipt.includes(`- Primary key: ${key || "missing"}`);
      const ready = keyMatch && artifactReceiptReady && status === "pass";
      const markdown = reviewPostRepairArtifactLinkMarkdown({ repairReceiptMarkdown, artifactReceiptMarkdown, key, artifactType, createdId, status });
      return html`
        <section class="review-post-repair-artifact-link" data-review-post-repair-artifact-link data-review-post-repair-artifact-link-ready="${ready ? "true" : "false"}" data-review-post-repair-artifact-link-key-match="${keyMatch ? "true" : "false"}" data-review-post-repair-artifact-link-artifact-receipt-ready="${artifactReceiptReady ? "true" : "false"}" data-review-post-repair-artifact-link-status="${status || "missing"}">
          <div class="review-artifact-post-apply-receipt-head">
            <div>
              <span>post-repair artifact link</span>
              <strong>${ready ? "repair receipt와 artifact receipt 연결됨" : "repair/artifact receipt 연결 대기"}</strong>
            </div>
            <small>${keyMatch ? "key match" : "key mismatch"} · ${artifactReceiptReady ? "artifact receipt ready" : "artifact receipt missing"}</small>
          </div>
          <p>수정된 validator 결과와 생성된 issue/note artifact receipt를 같은 primary key로 묶어 보관합니다.</p>
          <div class="review-artifact-post-apply-receipt-actions">
            <button type="button" class="portfolio-export-download portfolio-export-copy" data-action="copy-review-post-repair-artifact-link" data-review-post-repair-artifact-link-copy ${raw(ready ? "" : "disabled")}>link receipt 복사</button>
          </div>
          <pre data-review-post-repair-artifact-link-text hidden>${markdown}</pre>
          <small class="portfolio-export-status" data-review-post-repair-artifact-link-copy-status aria-live="polite">${ready ? "link receipt 대기" : "pass artifact receipt 대기"}</small>
        </section>
      `;
    }

    function issueFreshReceiptControls(model) {
      const data = model || {};
      const issueId = data.issueId || "";
      const receipt = data.receipt && typeof data.receipt === "object" ? data.receipt : {};
      const checks = Array.isArray(receipt.checks) ? receipt.checks : [];
      const progress = data.progress && typeof data.progress === "object" ? data.progress : {};
      const passCount = checks.filter((check) => check && check.status === "pass").length;
      const markdown = String(receipt.markdown || "");
      const href = `data:text/markdown;charset=utf-8,${encodeURIComponent(markdown)}`;
      return html`
        <div class="sheet-fresh-receipt" data-issue-fresh-receipt data-issue-fresh-receipt-view="review-artifact-view" data-issue-id="${issueId}" data-review-artifact-fresh-receipt-status="${receipt.status || "missing"}" data-review-artifact-fresh-receipt-kind="${receipt.kind || ""}" data-review-artifact-fresh-receipt-key="${receipt.key || ""}" data-review-artifact-fresh-receipt-created-id="${issueId}" data-review-artifact-fresh-receipt-check-count="${checks.length}" data-review-artifact-fresh-receipt-pass-count="${passCount}" data-review-artifact-fresh-receipt-progress-percent="${progress.percent || 0}">
          <div class="sheet-fresh-receipt-head">
            <span>fresh receipt</span>
            <strong>${receipt.status || "missing"} · ${passCount}/${checks.length} · ${progress.percent || 0}%</strong>
          </div>
          <div class="sheet-fresh-receipt-actions">
            <a class="portfolio-export-download" data-issue-fresh-receipt-download href="${href}" download="joopark-${receipt.kind || "issue"}-fresh-receipt.md">receipt 저장</a>
            <button type="button" class="portfolio-export-download portfolio-export-copy" data-action="copy-issue-fresh-receipt" data-issue-id="${issueId}" data-issue-fresh-receipt-copy>receipt 복사</button>
          </div>
          <small class="portfolio-export-status" data-issue-fresh-receipt-copy-status aria-live="polite"></small>
          <pre data-issue-fresh-receipt-text hidden>${markdown}</pre>
        </div>
      `;
    }

    function reviewArtifactPostApplyReceiptPanel({ repairUndo, receiptMarkdown, receiptHref, status, checks, kind }) {
      if (!repairUndo) return "";
      const rows = Array.isArray(checks) ? checks : [];
      const passCount = rows.filter((check) => check.status === "pass").length;
      const ready = status === "pass" && passCount === rows.length && rows.length > 0;
      return html`
        <section class="review-artifact-post-apply-receipt" data-review-artifact-post-apply-receipt data-review-artifact-post-apply-receipt-ready="${ready ? "true" : "false"}" data-review-artifact-post-apply-receipt-status="${status}" data-review-artifact-post-apply-receipt-pass-count="${passCount}" data-review-artifact-post-apply-receipt-check-count="${rows.length}" data-review-artifact-post-apply-receipt-applied-at="${repairUndo.appliedAt || ""}">
          <div class="review-artifact-post-apply-receipt-head">
            <div>
              <span>post-apply fresh receipt</span>
              <strong>${ready ? "복구 적용 후 pass receipt 준비됨" : "복구 적용 후 pass 대기"}</strong>
            </div>
            <small>${passCount}/${rows.length} checks · ${formatLocalDateTime(repairUndo.appliedAt)}</small>
          </div>
          <p>${ready ? "현재 복구된 artifact body와 pass check 상태를 새 receipt로 보관하세요." : "현재 artifact checks가 pass가 된 뒤 fresh receipt를 보관하세요."}</p>
          <div class="review-artifact-post-apply-receipt-actions">
            ${ready ? raw(html`<a class="portfolio-export-download" data-review-artifact-post-apply-receipt-download href="${receiptHref}" download="joopark-${kind}-post-apply-fresh-receipt.md">fresh receipt 저장</a>`) : ""}
            <button type="button" class="portfolio-export-download portfolio-export-copy" data-action="copy-review-artifact-post-apply-receipt" data-review-artifact-post-apply-receipt-copy ${raw(ready ? "" : "disabled")}>fresh receipt 복사</button>
          </div>
          <pre data-review-artifact-post-apply-receipt-text hidden>${receiptMarkdown}</pre>
          <small class="portfolio-export-status" data-review-artifact-post-apply-receipt-copy-status aria-live="polite">${ready ? "fresh receipt 대기" : "pass receipt 대기"}</small>
        </section>
      `;
    }

    function reviewArtifactDiffPanel({ kind, key, staticBody, validatedBody, createdBody, sourceKind, createdId, artifactType, repairReceiptMarkdown }) {
      if (!String(createdBody || "").trim()) return "";
      const normalizedKind = String(kind || "review").toLowerCase().replace(/[^a-z0-9-]/g, "-");
      const normalizedArtifactType = artifactType === "note" ? "note" : "issue";
      const openAction = normalizedArtifactType === "note" ? "open-note" : "open-issue";
      const openDataAttr = normalizedArtifactType === "note" ? "data-note-id" : "data-issue-id";
      const checks = reviewArtifactDiffChecks({ createdBody, sourceKind });
      const status = checks.every((check) => check.status === "pass") ? "pass" : "pending";
      const statusLabel = status === "pass" ? "검증 통과" : "대기";
      const repairUndo = reviewArtifactRepairUndoFor(normalizedArtifactType, createdId);
      const receiptMarkdown = reviewArtifactReceiptMarkdown({
        kind: normalizedKind,
        key,
        status,
        sourceKind,
        createdId,
        artifactType: normalizedArtifactType,
        createdBody,
        checks,
      });
      const receiptHref = `data:text/markdown;charset=utf-8,${encodeURIComponent(receiptMarkdown)}`;
      const panels = [
        { title: "Static draft", source: "baseline", body: staticBody },
        { title: "Validated result", source: "validated-review-result", body: validatedBody || "No saved validated result was applied." },
        { title: "Created artifact", source: sourceKind || "created", body: createdBody },
      ];
      return html`
        <section class="review-artifact-diff portfolio-review-artifact-diff" data-review-artifact-diff data-${normalizedKind}-review-artifact-diff data-review-artifact-diff-kind="${normalizedKind}" data-review-artifact-diff-key="${key}" data-review-artifact-diff-status="${status}" data-review-artifact-diff-check-count="${checks.length}" data-review-artifact-diff-pass-count="${checks.filter((check) => check.status === "pass").length}" data-review-artifact-diff-created-id="${createdId || ""}" data-review-artifact-diff-artifact-type="${normalizedArtifactType}" data-review-artifact-repair-undo-available="${repairUndo ? "true" : "false"}" data-review-artifact-repair-undo-at="${repairUndo ? repairUndo.appliedAt || "" : ""}">
          <div class="review-artifact-diff-head portfolio-artifact-diff-head">
            <span>Artifact diff</span>
            <div class="review-artifact-diff-actions">
              <small data-review-artifact-diff-status-label>${statusLabel}</small>
              <a class="portfolio-export-download" data-review-artifact-receipt-download href="${receiptHref}" download="joopark-${normalizedKind}-artifact-receipt.md">receipt 저장</a>
              <button type="button" class="portfolio-export-download portfolio-export-copy" data-action="copy-review-artifact-receipt" data-review-artifact-receipt-copy>receipt 복사</button>
              ${createdId ? raw(`<button type="button" class="portfolio-export-download portfolio-export-copy review-artifact-diff-open" data-action="${openAction}" data-review-artifact-open data-review-artifact-open-kind="${normalizedKind}" data-review-artifact-open-type="${normalizedArtifactType}" data-review-artifact-open-id="${escapeHtml(createdId)}" ${openDataAttr}="${escapeHtml(createdId)}">본문 열기</button>`) : ""}
              ${repairUndo ? raw(html`<button type="button" class="portfolio-export-download portfolio-export-copy" data-action="undo-review-artifact-repair" data-review-artifact-repair-undo>적용 되돌리기</button>`) : ""}
            </div>
          </div>
          <small class="portfolio-export-status" data-review-artifact-receipt-copy-status aria-live="polite"></small>
          ${raw(reviewArtifactPostApplyReceiptPanel({ repairUndo, receiptMarkdown, receiptHref, status, checks, kind: normalizedKind }))}
          ${raw(reviewPostRepairArtifactLinkPanel({ repairReceiptMarkdown, artifactReceiptMarkdown: receiptMarkdown, key, artifactType: normalizedArtifactType, createdId, status }))}
          <div class="review-artifact-diff-grid portfolio-artifact-diff-grid">
            ${raw(panels.map((panel) => html`
              <article class="review-artifact-diff-item portfolio-artifact-diff-item" data-review-artifact-diff-item data-review-artifact-diff-source="${panel.source}">
                <div>
                  <strong>${panel.title}</strong>
                  <span>${panel.source}</span>
                </div>
                <pre>${reviewArtifactDiffSnippet(panel.body)}</pre>
              </article>
            `).join(""))}
          </div>
          <ul class="review-artifact-diff-checks" data-review-artifact-diff-checks>
            ${raw(checks.map((check) => html`
              <li data-review-artifact-diff-check data-review-artifact-diff-check-id="${check.id}" data-review-artifact-diff-check-status="${check.status}">
                <span>${check.label}</span>
                <strong>${check.status}</strong>
              </li>
            `).join(""))}
          </ul>
          <pre data-review-artifact-receipt-text hidden>${receiptMarkdown}</pre>
          <section class="review-artifact-receipt-compare" data-review-artifact-receipt-compare data-review-artifact-receipt-compare-state="empty">
            <div class="review-artifact-receipt-compare-head">
              <span>Receipt compare</span>
              <div class="review-artifact-diff-actions">
                <button type="button" class="portfolio-export-download portfolio-export-copy" data-action="insert-review-artifact-receipt">현재 receipt 넣기</button>
                <button type="button" class="portfolio-export-download portfolio-export-copy" data-action="compare-review-artifact-receipt">receipt 비교</button>
                <button type="button" class="portfolio-export-download portfolio-export-copy" data-action="clear-review-artifact-receipt">초기화</button>
              </div>
            </div>
            <textarea class="review-artifact-receipt-input" data-review-artifact-receipt-input rows="4" spellcheck="false" placeholder="보관한 artifact receipt Markdown을 붙여넣어 현재 생성 artifact와 비교하세요."></textarea>
            <small class="portfolio-export-status" data-review-artifact-receipt-compare-status aria-live="polite">receipt 대기</small>
            <div class="review-artifact-receipt-output" data-review-artifact-receipt-compare-output></div>
          </section>
        </section>
      `;
    }

    return {
      version: VERSION,
      reviewArtifactDiffSnippet,
      reviewArtifactDiffChecks,
      reviewArtifactReceiptMarkdown,
      parseReviewArtifactReceipt,
      reviewArtifactReceiptRepairSuggestion,
      reviewArtifactReceiptComparison,
      reviewArtifactReceiptCompareOutput,
      reviewPostRepairArtifactLinkMarkdown,
      reviewPostRepairArtifactLinkPanel,
      issueFreshReceiptControls,
      reviewArtifactPostApplyReceiptPanel,
      reviewArtifactDiffPanel,
    };
  }

  root.JooParkReviewArtifactView = {
    version: VERSION,
    create: createReviewArtifactView,
  };
})(window);
