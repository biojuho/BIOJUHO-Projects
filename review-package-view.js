(function (root) {
  "use strict";

  const VERSION = "joopark-review-package-view/v1";

  const KIND_CONFIG = {
    workspace: {
      rootAttr: "data-workspace-review-handoff",
      countAttr: "data-workspace-review-handoff-count",
      primaryKeyAttr: "data-workspace-review-handoff-primary-key",
      label: "Workspace prompt handoff",
      downloadAttr: "data-workspace-review-handoff-download",
      filename: "joopark-workspace-review-handoff.md",
      copyAttr: "data-workspace-review-handoff-copy",
      copyKeyAttr: "data-workspace-review-handoff-copy-key",
      copyStatusAttr: "data-workspace-review-handoff-copy-status",
      bundleStatusAttr: "data-workspace-review-bundle-copy-status",
      bundleTextAttr: "data-workspace-review-package-bundle-text",
      handoffTextAttr: "data-workspace-review-handoff-text",
      note: {
        publishAttr: "data-workspace-review-note-publish",
        keyAttr: "data-workspace-review-note-key",
        statusAttr: "data-workspace-review-note-publish-status",
        createdAttr: "data-workspace-review-note-created",
        idAttr: "data-workspace-review-note-id",
      },
    },
    "knowledge-base": {
      rootAttr: "data-knowledge-base-review-handoff",
      countAttr: "data-kb-review-handoff-count",
      primaryKeyAttr: "data-kb-review-handoff-primary-key",
      label: "KB/IA prompt handoff",
      downloadAttr: "data-kb-review-handoff-download",
      filename: "joopark-kb-ia-review-handoff.md",
      copyAttr: "data-kb-review-handoff-copy",
      copyKeyAttr: "data-kb-review-handoff-copy-key",
      copyStatusAttr: "data-kb-review-handoff-copy-status",
      bundleStatusAttr: "data-kb-review-bundle-copy-status",
      bundleTextAttr: "data-kb-review-package-bundle-text",
      handoffTextAttr: "data-kb-review-handoff-text",
      note: {
        publishAttr: "data-kb-review-note-publish",
        keyAttr: "data-kb-review-note-key",
        statusAttr: "data-kb-review-note-publish-status",
        createdAttr: "data-kb-review-note-created",
        idAttr: "data-kb-review-note-id",
        kind: "knowledge-base-review-note",
        titlePrefix: "[KB/IA Review]",
        color: "#84cc16",
      },
    },
    benchmark: {
      rootAttr: "data-benchmark-review-handoff",
      label: "prompt handoff export",
      downloadAttr: "data-review-handoff-download",
      filename: "joopark-benchmark-review-queue.md",
      bundleStatusAttr: "data-benchmark-review-bundle-copy-status",
      bundleTextAttr: "data-benchmark-review-package-bundle-text",
      note: {
        publishAttr: "data-benchmark-review-note-publish",
        keyAttr: "data-benchmark-review-note-key",
        statusAttr: "data-benchmark-review-note-publish-status",
        createdAttr: "data-benchmark-review-note-created",
        idAttr: "data-benchmark-review-note-id",
        kind: "benchmark-review-note",
        titlePrefix: "[PM Bench Review]",
        color: "#a970ff",
      },
    },
  };

  function createReviewPackageView(deps) {
    const options = deps || {};
    const html = options.html;
    const raw = options.raw;
    const reviewResultValidator = typeof options.reviewResultValidator === "function" ? options.reviewResultValidator : function () { return ""; };
    const reviewPackageManifestSummary = typeof options.reviewPackageManifestSummary === "function" ? options.reviewPackageManifestSummary : function () { return ""; };
    const reviewPackagePastePreview = typeof options.reviewPackagePastePreview === "function" ? options.reviewPackagePastePreview : function () { return ""; };
    const reviewPackageBundleControls = typeof options.reviewPackageBundleControls === "function" ? options.reviewPackageBundleControls : function () { return ""; };
    const reviewArtifactDiffPanel = typeof options.reviewArtifactDiffPanel === "function" ? options.reviewArtifactDiffPanel : function () { return ""; };

    if (typeof html !== "function" || typeof raw !== "function") {
      throw new Error("review package view requires html and raw helpers");
    }

    function escapeAttr(value) {
      return String(value == null ? "" : value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
    }

    function attrs(pairs) {
      return pairs
        .filter((pair) => pair && pair[0] && pair[1] !== false && pair[1] !== null && pair[1] !== undefined)
        .map(([name, value]) => value === true ? name : `${name}="${escapeAttr(value)}"`)
        .join(" ");
    }

    function hrefFor(markdown) {
      return `data:text/markdown;charset=utf-8,${encodeURIComponent(markdown || "")}`;
    }

    function reviewPackageHandoffModel(input) {
      const data = input || {};
      const kind = data.kind || "benchmark";
      const config = KIND_CONFIG[kind] || KIND_CONFIG.benchmark;
      const decisions = Array.isArray(data.decisions) ? data.decisions : [];
      const primary = data.primary || decisions[0] || {};
      const decision = primary.decision || {};
      const project = primary.project || {};
      const primaryKey = data.primaryKey || decision.persistKey || "";
      const existingNote = data.existingNote || null;
      const noteCreated = !!(existingNote && existingNote.id);
      const markdown = data.markdown || "";
      const issueDraft = data.issueDraft || null;
      const githubCommentMarkdown = data.githubCommentMarkdown || "";
      const noteBody = data.noteBody || "";
      const bundleMarkdown = data.bundleMarkdown || "";
      const bundleFilename = data.bundleFilename || config.filename.replace("handoff", "package");

      return {
        kind,
        config,
        decisions,
        primary,
        decision,
        project,
        primaryKey,
        existingNote,
        noteCreated,
        markdown,
        issueDraft,
        githubCommentMarkdown,
        noteBody,
        bundleMarkdown,
        bundleFilename,
        schemaVersion: data.schemaVersion || "",
        validatorTitle: data.validatorTitle || "Review package",
        bundleManifest: data.bundleManifest || null,
        issueDraftHTML: data.issueDraftHTML || "",
        githubCommentHTML: data.githubCommentHTML || "",
        artifact: data.artifact || null,
      };
    }

    function rootAttrs(model) {
      const pairs = [
        [model.config.rootAttr, true],
        ["data-review-handoff-format", "markdown"],
        ["data-review-prompt-contract", model.schemaVersion],
        ["data-review-output-format", "json+markdown"],
        ["data-review-handoff-count", model.decisions.length],
        ["data-review-handoff-primary-key", model.primaryKey],
      ];
      if (model.config.countAttr) pairs.push([model.config.countAttr, model.decisions.length]);
      if (model.config.primaryKeyAttr) pairs.push([model.config.primaryKeyAttr, model.primaryKey]);
      if (model.config.note) {
        pairs.push([model.config.note.createdAttr, model.noteCreated ? "true" : "false"]);
        pairs.push([model.config.note.idAttr, model.noteCreated ? model.existingNote.id : ""]);
      }
      return attrs(pairs);
    }

    function copyButtonAttrs(model) {
      return attrs([
        ["type", "button"],
        ["class", "portfolio-export-download portfolio-export-copy"],
        ["data-action", "copy-review-handoff"],
        ["data-review-handoff-copy", true],
        [model.config.copyAttr, !!model.config.copyAttr],
        ["data-review-handoff-copy-key", model.primaryKey],
        [model.config.copyKeyAttr, model.config.copyKeyAttr ? model.primaryKey : false],
      ]);
    }

    function noteButtonHTML(model) {
      const note = model.config.note;
      if (!note) return "";
      return html`
        <button ${raw(attrs([
          ["type", "button"],
          ["class", "portfolio-export-download portfolio-export-copy"],
          ["data-action", "publish-review-note"],
          ["data-review-note-publish", true],
          [note.publishAttr, true],
          ["data-review-note-key", model.primaryKey],
          [note.keyAttr, model.primaryKey],
          ["data-review-note-kind", note.kind || false],
          ["data-review-note-title-prefix", note.titlePrefix || false],
          ["data-review-note-color", note.color || false],
          ["data-review-note-created", model.noteCreated ? "true" : "false"],
          ["data-review-note-id", model.noteCreated ? model.existingNote.id : ""],
          ["data-review-note-existing", model.noteCreated ? "true" : "false"],
        ]))}>${model.noteCreated ? "노트 열기" : "노트 발행"}</button>
      `;
    }

    function statusHTML(model) {
      return html`
        <small class="portfolio-export-status" ${raw(attrs([
          ["data-review-handoff-copy-status", true],
          [model.config.copyStatusAttr, !!model.config.copyStatusAttr],
          ["aria-live", "polite"],
        ]))}></small>
        <small class="portfolio-export-status" ${raw(attrs([
          ["data-review-bundle-copy-status", true],
          [model.config.bundleStatusAttr, !!model.config.bundleStatusAttr],
          ["aria-live", "polite"],
        ]))}></small>
        ${model.config.note ? raw(html`<small class="portfolio-export-status" ${raw(attrs([[model.config.note.statusAttr, true], ["aria-live", "polite"]]))}>${model.noteCreated ? "노트 발행됨" : ""}</small>`) : ""}
      `;
    }

    function reviewPackageHandoffHTML(input) {
      const model = reviewPackageHandoffModel(input);
      if (!model.decisions.length || !model.markdown || !model.primaryKey) return "";
      const manifestSummary = reviewPackageManifestSummary({ kind: model.kind, manifest: model.bundleManifest });
      const pastePreview = reviewPackagePastePreview({
        kind: model.kind,
        issueDraft: model.issueDraft,
        githubCommentMarkdown: model.githubCommentMarkdown,
        noteBody: model.noteBody,
      });
      const artifactPanel = model.artifact ? reviewArtifactDiffPanel(model.artifact) : "";
      return html`
        <section class="portfolio-review-handoff" ${raw(rootAttrs(model))}>
          <div class="portfolio-export-head">
            <span>${model.config.label}</span>
            <div class="portfolio-export-actions">
              <a class="portfolio-export-download" ${raw(attrs([[model.config.downloadAttr, true], ["href", hrefFor(model.markdown)], ["download", model.config.filename]]))}>MD 저장</a>
              <button ${raw(copyButtonAttrs(model))}>복사</button>
              ${raw(noteButtonHTML(model))}
              ${raw(reviewPackageBundleControls({ kind: model.kind, primaryKey: model.primaryKey, markdown: model.bundleMarkdown, filename: model.bundleFilename }))}
            </div>
          </div>
          ${raw(statusHTML(model))}
          <div class="portfolio-export-grid">
            <div>
              <span>우선 결정</span>
              <strong>${model.project.name} ${model.decision.status}</strong>
            </div>
            <div>
              <span>persist key</span>
              <strong>${model.primaryKey}</strong>
            </div>
            <div>
              <span>handoff 수</span>
              <strong>${model.decisions.length}개</strong>
            </div>
            <div>
              <span>출력 계약</span>
              <strong>${model.schemaVersion} · JSON+Markdown</strong>
            </div>
          </div>
          ${raw(reviewResultValidator(model.decisions, model.validatorTitle))}
          ${raw(manifestSummary)}
          ${raw(pastePreview)}
          ${raw(artifactPanel)}
          ${raw(model.issueDraftHTML)}
          ${raw(model.githubCommentHTML)}
          <pre data-review-package-bundle-text ${raw(attrs([[model.config.bundleTextAttr, !!model.config.bundleTextAttr], ["hidden", true]]))}>${model.bundleMarkdown}</pre>
          <pre class="portfolio-export-body" data-review-handoff-text ${raw(attrs([[model.config.handoffTextAttr, !!model.config.handoffTextAttr]]))}>${model.markdown}</pre>
        </section>
      `;
    }

    return {
      version: VERSION,
      reviewPackageHandoffModel,
      reviewPackageHandoffHTML,
      renderReviewPackageHandoffHTML: reviewPackageHandoffHTML,
    };
  }

  root.JooParkReviewPackageView = {
    version: VERSION,
    create: createReviewPackageView,
  };
})(window);
