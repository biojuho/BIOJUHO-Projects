(function attachReviewRecommendationExport(root) {
  "use strict";

  const VERSION = "joopark-review-recommendation-export/v1";

  function createReviewRecommendationExport(deps = {}) {
    const html = deps.html;
    const raw = deps.raw;
    const projectBenchmarkRubric = deps.projectBenchmarkRubric;
    const projectKnowledgeBaseRubric = deps.projectKnowledgeBaseRubric;
    const projectWorkspaceRubric = deps.projectWorkspaceRubric;

    if (typeof html !== "function" || typeof raw !== "function") {
      throw new Error("review recommendation export requires html and raw helpers");
    }

    function topWeightedAxis(rows) {
      return (Array.isArray(rows) ? rows : [])
        .filter((row) => row.weight > 0 && row.score > 0)
        .sort((a, b) => (b.score * b.weight) - (a.score * a.weight))[0] || null;
    }

    function escapeAttr(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("\"", "&quot;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;");
    }

    function recommendationMarkdown(scored, options) {
      if (!Array.isArray(scored) || scored.length < 2) return "";
      const [top, runnerUp] = scored;
      const rubric = options.rubric;
      const gap = top.rubricScore.score - runnerUp.rubricScore.score;
      const topAxis = topWeightedAxis(rubric(top.project));
      const lines = [
        options.title,
        "",
        options.recommendation(top, runnerUp),
        `Score gap: ${gap} point${gap === 1 ? "" : "s"}.`,
        topAxis ? `Primary reason: ${topAxis.axis} scored ${topAxis.score} at ${Math.round(topAxis.weight * 100)}% weight because ${topAxis.value}.` : "",
        "",
        "## Weighted Scores",
      ].filter(Boolean);
      scored.forEach(({ project, rubricScore }) => {
        lines.push("", `### ${project.name}: ${rubricScore.label} ${rubricScore.score}`);
        rubric(project).forEach((row) => {
          lines.push(`- ${row.axis}: weight ${Math.round(row.weight * 100)}%, score ${row.score} - ${row.value}`);
        });
      });
      return lines.join("\n");
    }

    function recommendationExport(scored, options) {
      if (!Array.isArray(scored) || scored.length < 2) return "";
      const [top, runnerUp] = scored;
      const markdown = options.markdown(scored);
      if (!markdown) return "";
      const gap = top.rubricScore.score - runnerUp.rubricScore.score;
      const topAxis = topWeightedAxis(options.rubric(top.project));
      const href = `data:text/markdown;charset=utf-8,${encodeURIComponent(markdown)}`;
      return html`
        <section class="portfolio-benchmark-export" ${raw(options.rootAttrs(top, gap))}>
          <div class="portfolio-export-head">
            <span>${options.label}</span>
            <a class="portfolio-export-download" ${raw(options.downloadAttr)} href="${href}" download="${options.filename}">MD 저장</a>
          </div>
          <div class="portfolio-export-grid">
            ${raw(options.summaryHTML({ top, runnerUp, gap, topAxis }))}
          </div>
          <pre class="portfolio-export-body" ${raw(options.textAttr)}>${markdown}</pre>
        </section>
      `;
    }

    function candidateBenchmarkRecommendationMarkdown(scored) {
      return recommendationMarkdown(scored, {
        title: "# JooPark Benchmark Recommendation",
        rubric: projectBenchmarkRubric,
        recommendation: (top, runnerUp) => `Recommendation: adopt ${top.project.name} first (${top.rubricScore.label} ${top.rubricScore.score}), and keep ${runnerUp.project.name} as the secondary benchmark (${runnerUp.rubricScore.label} ${runnerUp.rubricScore.score}).`,
      });
    }

    function workspaceBenchmarkRecommendationMarkdown(scored) {
      return recommendationMarkdown(scored, {
        title: "# JooPark Workspace Benchmark Recommendation",
        rubric: projectWorkspaceRubric,
        recommendation: (top, runnerUp) => `Recommendation: use ${top.project.name} as the primary Workspace benchmark (${top.rubricScore.label} ${top.rubricScore.score}), and keep ${runnerUp.project.name} as the PM/task contrast (${runnerUp.rubricScore.label} ${runnerUp.rubricScore.score}).`,
      });
    }

    function knowledgeBaseBenchmarkRecommendationMarkdown(scored) {
      return recommendationMarkdown(scored, {
        title: "# JooPark Knowledge/IA Benchmark Recommendation",
        rubric: projectKnowledgeBaseRubric,
        recommendation: (top, runnerUp) => `Recommendation: use ${top.project.name} as the primary Knowledge/IA benchmark (${top.rubricScore.label} ${top.rubricScore.score}), and keep ${runnerUp.project.name} as the portability counterweight (${runnerUp.rubricScore.label} ${runnerUp.rubricScore.score}).`,
      });
    }

    function candidateBenchmarkRecommendationExport(scored) {
      return recommendationExport(scored, {
        label: "추천 export",
        filename: "joopark-benchmark-recommendation.md",
        markdown: candidateBenchmarkRecommendationMarkdown,
        rubric: projectBenchmarkRubric,
        rootAttrs: (top, gap) => `data-candidate-benchmark-export data-benchmark-export-winner="${escapeAttr(top.project.name)}" data-benchmark-export-gap="${gap}" data-benchmark-export-format="markdown"`,
        downloadAttr: "data-benchmark-export-download",
        textAttr: "data-benchmark-export-text",
        summaryHTML: ({ top, runnerUp, gap, topAxis }) => html`
          <div>
            <span>우선 채택</span>
            <strong>${top.project.name} ${top.rubricScore.label} ${top.rubricScore.score}</strong>
          </div>
          <div>
            <span>보조 벤치</span>
            <strong>${runnerUp.project.name} ${runnerUp.rubricScore.label} ${runnerUp.rubricScore.score}</strong>
          </div>
          <div>
            <span>격차</span>
            <strong>${gap}점</strong>
          </div>
          <div>
            <span>근거</span>
            <strong>${topAxis ? `${topAxis.axis} ${topAxis.score}` : "점수 대기"}</strong>
          </div>
        `,
      });
    }

    function compactRecommendationSummaryHTML({ top, runnerUp, gap, topAxis }) {
      return html`
        <div><span>추천</span><strong>${top.project.name}</strong><small>${top.rubricScore.label} ${top.rubricScore.score}</small></div>
        <div><span>비교</span><strong>${runnerUp.project.name}</strong><small>${gap}점 차이</small></div>
        <div><span>근거</span><strong>${topAxis ? topAxis.axis : "가중 점수"}</strong><small>${topAxis ? `${topAxis.score}점 · ${Math.round(topAxis.weight * 100)}%` : "루브릭 합산"}</small></div>
      `;
    }

    function candidateWorkspaceRecommendationExport(scored) {
      return recommendationExport(scored, {
        label: "Workspace export",
        filename: "joopark-workspace-benchmark-recommendation.md",
        markdown: workspaceBenchmarkRecommendationMarkdown,
        rubric: projectWorkspaceRubric,
        rootAttrs: (top, gap) => `data-workspace-benchmark-export data-workspace-benchmark-export-winner="${escapeAttr(top.project.name)}" data-workspace-benchmark-export-gap="${gap}" data-workspace-benchmark-export-format="markdown"`,
        downloadAttr: "data-workspace-benchmark-export-download",
        textAttr: "data-workspace-benchmark-export-text",
        summaryHTML: compactRecommendationSummaryHTML,
      });
    }

    function candidateKnowledgeBaseRecommendationExport(scored) {
      return recommendationExport(scored, {
        label: "KB/IA export",
        filename: "joopark-kb-ia-recommendation.md",
        markdown: knowledgeBaseBenchmarkRecommendationMarkdown,
        rubric: projectKnowledgeBaseRubric,
        rootAttrs: (top, gap) => `data-knowledge-base-benchmark-export data-kb-benchmark-export-winner="${escapeAttr(top.project.name)}" data-kb-benchmark-export-gap="${gap}" data-kb-benchmark-export-format="markdown"`,
        downloadAttr: "data-kb-benchmark-export-download",
        textAttr: "data-kb-benchmark-export-text",
        summaryHTML: compactRecommendationSummaryHTML,
      });
    }

    return {
      version: VERSION,
      candidateBenchmarkRecommendationMarkdown,
      candidateBenchmarkRecommendationExport,
      workspaceBenchmarkRecommendationMarkdown,
      candidateWorkspaceRecommendationExport,
      knowledgeBaseBenchmarkRecommendationMarkdown,
      candidateKnowledgeBaseRecommendationExport,
    };
  }

  root.JooParkReviewRecommendationExport = {
    version: VERSION,
    create: createReviewRecommendationExport,
  };
})(window);
