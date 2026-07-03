/* ================================================================
 * JooPark Workspace — release status helpers
 * Static non-module runtime loaded before app.js.
 * ================================================================ */

(function initJooParkReleaseStatus(global) {
  "use strict";

  const VERSION = "joopark-release-status/v1";
  const READINESS_ITEMS = Object.freeze([
    Object.freeze({
      key: "release-gates",
      state: "pass",
      label: "릴리스 게이트",
      detail: "패키지, manifest, 보안 헤더, fallback, 데스크톱/모바일/상호작용/접근성 스모크와 캐시 증거 깊이는 `npm run verify`에서 통합 검증합니다.",
      command: "npm run verify",
      evidence: Object.freeze([
        "package + manifest/source parity pass",
        "desktop/mobile route parity 17/17",
        "mobile search-empty 13 routes including llm-wiki",
        "mobile UI surfaces 5/5 pass",
        "delete/undo recovery 8 types persisted",
        "keyboard/ARIA accessibility pass",
      ]),
    }),
    Object.freeze({
      key: "pages-template",
      state: "pass",
      label: "Pages 템플릿",
      detail: "`docs/github-pages-workflow.yml`은 release package를 만들고 `pages: write`, `id-token: write`, `actions/upload-pages-artifact`, `actions/deploy-pages`, build/deploy `needs` 흐름으로 배포하도록 준비되어 있습니다.",
      command: "node scripts/prepare-github-pages-workflow.mjs --dry-run --check-scope",
    }),
    Object.freeze({
      key: "workflow-scope-preflight",
      state: "blocked",
      label: "workflow scope preflight",
      detail: "`workflowScopeAvailable`이 false이면 `gh auth refresh -h github.com -s workflow`로 CLI 권한을 갱신한 뒤 재확인하거나, workflow-scope token 또는 GitHub UI session에서 설치합니다.",
      command: "node scripts/prepare-github-pages-workflow.mjs --dry-run --check-scope && node scripts/prepare-github-drift-watch-workflow.mjs --dry-run --check-scope",
    }),
    Object.freeze({
      key: "pages-install",
      state: "blocked",
      label: "Pages workflow 설치",
      detail: "repository root의 `.github/workflows/joopark-pages.yml` 설치는 workflow-scope token 또는 GitHub UI session이 필요합니다.",
      command: "node scripts/prepare-github-pages-workflow.mjs --write",
    }),
    Object.freeze({
      key: "workflow-ui-install-plan",
      state: "blocked",
      label: "GitHub UI install plan",
      detail: "`plan-workflow-ui-install.mjs --dry-run --markdown`으로 UI에 붙여 넣을 workflow target, `githubNewFileUrl`, `githubWorkflowUrl`, `templateCopyCommand`, `githubNewFileOpenCommand`, `githubWorkflowOpenCommand`, defaultBranch, template sha256, required terms, `suggestedRepo`, `nextVerificationCommand`를 검증합니다.",
      command: "node scripts/plan-workflow-ui-install.mjs --dry-run --markdown",
    }),
    Object.freeze({
      key: "drift-watch-install",
      state: "blocked",
      label: "Drift Watch 설치",
      detail: "`docs/github-drift-watch-workflow.yml`도 default branch workflow로 설치되어야 schedule과 workflow_dispatch가 동작합니다.",
      command: "node scripts/prepare-github-drift-watch-workflow.mjs --write",
    }),
    Object.freeze({
      key: "publish-dispatch-plan",
      state: "blocked",
      label: "Publish dispatch dry-run",
      detail: "`node scripts/plan-publish-dispatch.mjs --dry-run`의 `workflowUiInstallPlans`에서 `templateCopyCommand`, `githubNewFileOpenCommand`, `githubWorkflowOpenCommand`를 확인한 뒤 `node scripts/plan-publish-dispatch.mjs --live --repo OWNER/REPO`에서 `OWNER/REPO`를 실제 repo로 바꿉니다. 현재 `suggestedRepo` 기준 검증 명령은 `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects`이며, 이 명령이 `repoEvidenceReady: true`, Pages `dispatchReady: true`, 전체 `allDispatchReady: true`를 보고할 때만 Pages publish와 Drift Watch dispatch를 실행합니다. 출력에 `repoEvidenceReady: false` 또는 `repo placeholder OWNER/REPO` blocker가 있으면 중단합니다.",
      command: "node scripts/plan-publish-dispatch.mjs --live --repo OWNER/REPO",
    }),
    Object.freeze({
      key: "remote-workflow-file-check",
      state: "blocked",
      label: "Remote workflow file check",
      detail: "`node scripts/check-remote-workflow-files.mjs --repo OWNER/REPO --write`로 default branch의 workflow YAML이 로컬 검증 템플릿과 같은지 확인합니다. `remoteWorkflowFilesReady: true`가 되기 전에는 dispatch를 실행하지 않습니다.",
      command: "node scripts/check-remote-workflow-files.mjs --repo OWNER/REPO --write",
    }),
    Object.freeze({
      key: "publish-dispatch",
      state: "blocked",
      label: "Publish 실행",
      detail: "dispatch dry-run 통과 후 `Publish JooPark Pages`와 `joopark-drift-watch.yml` advisory run을 workflow_dispatch로 실행합니다.",
      command: "gh workflow run --repo OWNER/REPO joopark-pages.yml",
    }),
    Object.freeze({
      key: "publish-evidence-capture",
      state: "blocked",
      label: "Publish evidence capture",
      detail: "dispatch 후 `capture-publish-evidence.mjs --live --repo OWNER/REPO --markdown`으로 Pages `html_url/status`와 Pages/Drift workflow run `status/conclusion`을 공유하고, `--write`로 JSON 증거를 저장해 `postPublishEvidenceReady: true`가 되어야 공개 증거가 완성됩니다.",
      command: "node scripts/capture-publish-evidence.mjs --live --repo OWNER/REPO --markdown",
    }),
  ]);

  function escapeHtml(value) {
    if (value === null || value === undefined) return "";
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function fallbackRaw(value) {
    return { __raw: true, value: value == null ? "" : String(value) };
  }

  function fallbackHtml(strings, ...values) {
    let out = "";
    for (let i = 0; i < strings.length; i += 1) {
      out += strings[i];
      if (i >= values.length) continue;
      const v = values[i];
      if (v === null || v === undefined || v === false) continue;
      if (v && v.__raw) out += v.value;
      else if (Array.isArray(v)) out += v.map((item) => item && item.__raw ? item.value : escapeHtml(item)).join("");
      else out += escapeHtml(v);
    }
    return out;
  }

  function cloneItem(item) {
    return { ...item };
  }

  function defaultFormatLocalDateTime(value) {
    if (!value) return "";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleString();
  }

  function createReleaseStatus(deps = {}) {
    const html = typeof deps.html === "function" ? deps.html : fallbackHtml;
    const raw = typeof deps.raw === "function" ? deps.raw : fallbackRaw;
    const formatLocalDateTime = typeof deps.formatLocalDateTime === "function"
      ? deps.formatLocalDateTime
      : defaultFormatLocalDateTime;
    const dateNow = typeof deps.dateNow === "function" ? deps.dateNow : () => Date.now();

    function finiteNumberOr(value, fallback) {
      if (value === null || value === undefined || value === "") return fallback;
      const number = Number(value);
      return Number.isFinite(number) ? number : fallback;
    }

    function installPathItemCommandCount(item) {
      return finiteNumberOr(item?.commandCount, Array.isArray(item?.commands) ? item.commands.length : 0);
    }

    function publishReadinessItems() {
      return READINESS_ITEMS.map(cloneItem);
    }

    function publishReadinessStateLabel(state) {
      if (state === "pass") return "준비";
      if (state === "blocked") return "action required";
      return "확인 필요";
    }

    function publishReadinessMarkdownLines() {
      return publishReadinessItems().map((item) => {
        const evidence = Array.isArray(item.evidence) && item.evidence.length
          ? ` Evidence: ${item.evidence.join("; ")}.`
          : "";
        return `- ${item.label}: ${publishReadinessStateLabel(item.state)}. ${item.detail}${evidence} Next: \`${item.command}\``;
      });
    }

    function publishRepoPlaceholderGuardLines() {
      return [
        "## Repo placeholder guard",
        "1. Replace every `OWNER/REPO` with the exact GitHub repo before sharing or running any live command.",
        "2. If `repoEvidenceReady: false` or `repo placeholder OWNER/REPO` appears in live plan output, do not run `gh workflow run --repo`.",
        "3. Do not save `node scripts/capture-publish-evidence.mjs --live --repo OWNER/REPO --write` as launch proof until the placeholder is replaced and `postPublishEvidenceReady: true` is confirmed.",
        "4. If `suggestedRepo` is present, replace `OWNER/REPO` with that value; this workspace's current remote suggestion is `biojuho/BIOJUHO-Projects`.",
      ];
    }

    function publishDispatchGateGuardLines() {
      return [
        "## Dispatch safety gate",
        "1. Do not run `Publish JooPark Pages`, `Watch JooPark Candidate Drift`, or any `gh workflow run --repo` command until `remoteWorkflowFilesReady: true`, `dispatchReady: true`, `driftDispatchReady: true`, and `allDispatchReady: true` are all confirmed.",
        "2. If `dispatchSuggestionStatus: withheld-until-all-dispatch-ready` or `suggestedDispatchCommands: []` appears, keep using verification commands only. Do not run until allDispatchReady: true.",
        "3. Inspect `workflowScope.scopes`, `workflowScopeAvailable`, and `workflowScopeInstallBlocked` in `data/publish-dispatch-plan.json`; if the scopes omit `workflow` or install is blocked, run `gh auth refresh -h github.com -s workflow`, then rerun `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects`, or use GitHub UI for workflow file installation.",
        "4. Treat `gh auth refresh -h github.com -s workflow` as an auth preflight only; do not treat it as workflow installation, dispatch, or launch proof.",
        "5. When ready, run only the repo-scoped commands returned under `suggestedDispatchCommands`, then capture live evidence with `node scripts/capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --markdown` and `--write`.",
      ];
    }

    function publishUnblockHandoffText() {
      const blocked = publishReadinessItems().filter((item) => item.state === "blocked");
      return [
        "# JooPark Workspace Publish Unblock Handoff / 공개 차단 해제 체크리스트",
        "",
        "## 현재 action-required 항목",
        ...blocked.map((item) => `- ${item.label}: ${item.detail} Next: \`${item.command}\``),
        "",
        "## CLI preflight",
        "1. `node scripts/prepare-github-pages-workflow.mjs --dry-run --check-scope`",
        "2. `node scripts/prepare-github-drift-watch-workflow.mjs --dry-run --check-scope`",
        "3. `node scripts/plan-workflow-ui-install.mjs --dry-run --markdown`으로 UI target, `githubNewFileUrl`, `githubWorkflowUrl`, `templateCopyCommand`, `githubNewFileOpenCommand`, `githubWorkflowOpenCommand`, defaultBranch, template sha256, required terms, `suggestedRepo`, `nextVerificationCommand`를 확인합니다.",
        "4. `workflowScopeAvailable`이 false이면 `gh auth refresh -h github.com -s workflow`로 CLI 권한을 갱신한 뒤 `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects`로 재확인합니다.",
        "5. 권한 갱신이 불가능하거나 브라우저 인증을 진행하지 않을 경우 CLI write를 중단하고 workflow-scope token 또는 GitHub UI session으로 설치합니다.",
        "",
        "## Device-code approval handoff",
        "1. `gh auth refresh -h github.com -s workflow`가 one-time device code를 표시하면 `https://github.com/login/device`에서 승인합니다.",
        "2. one-time device code는 프로젝트 파일, 로그, README, release receipt에 저장하지 않습니다.",
        "3. 승인 뒤 `gh auth status -h github.com`와 `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects`를 다시 실행해 `workflowScopeAvailable: true`와 `workflowScopeInstallBlocked: false`를 확인합니다.",
        "4. 승인 또는 GitHub UI 설치 확인 전에는 `install-remote-workflow-files.mjs`, `gh workflow run`, public launch copy, archive proof를 실행하지 않습니다.",
        "",
        ...publishRepoPlaceholderGuardLines(),
        "",
        ...publishDispatchGateGuardLines(),
        "",
        "## GitHub UI 설치 경로",
        "Targets: `.github/workflows/joopark-pages.yml`, `.github/workflows/joopark-drift-watch.yml`.",
        "1. `Remote workflow install packet` 또는 `install packet 복사`의 각 workflow row에서 `installAction`을 확인합니다: `replace_existing_remote_file`은 edit-file page, `create_missing_remote_file`은 new-file page, `verified_remote_matches_template`는 no-op입니다.",
        "2. 변경이 필요한 row만 `templateCopyCommand`로 YAML을 복사하고, 해당 row의 GitHub edit/new-file open command로 default branch 파일을 갱신합니다.",
        "3. `node scripts/check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write`로 default branch remote workflow file의 `remoteWorkflowFilesReady`와 `remoteMatchesTemplate`를 확인합니다.",
        "4. plan의 `githubWorkflowOpenCommand` 또는 `githubWorkflowUrl`에서 두 workflow가 Actions에 보이는지 확인합니다.",
        "5. plan의 `nextVerificationCommand`가 `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects`이면 그 repo-specific 명령을 먼저 실행하고, `node scripts/plan-publish-dispatch.mjs --live --repo OWNER/REPO`는 suggested repo가 틀릴 때만 템플릿으로 사용합니다.",
        "6. `remoteWorkflowFilesReady: true`, `dispatchReady: true`, `driftDispatchReady: true`, `allDispatchReady: true`가 모두 확인된 뒤에만 Actions 또는 `suggestedDispatchCommands`로 `Publish JooPark Pages`와 `Watch JooPark Candidate Drift`를 실행합니다.",
        "7. `node scripts/capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --markdown`으로 Pages `html_url/status`와 두 workflow run의 `status/conclusion`을 공유하고, `node scripts/capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --write`로 JSON 증거를 저장해 `postPublishEvidenceReady: true`를 확인합니다.",
        "",
        "## 완료 후 검증",
        "1. `npm run verify`",
        "2. System Status의 공개 준비 상태를 다시 확인합니다.",
      ].join("\n");
    }

    function publishReadinessListHTML(items) {
      return items.map((item) => html`
        <article class="publish-readiness-item" data-publish-readiness-item data-publish-key="${item.key}" data-publish-state="${item.state}" data-publish-evidence-count="${Array.isArray(item.evidence) ? item.evidence.length : 0}">
          <div>
            <strong>${item.label}</strong>
            <p>${item.detail}</p>
            ${Array.isArray(item.evidence) && item.evidence.length ? raw(html`
              <ul class="publish-readiness-evidence" data-publish-readiness-evidence>
                ${item.evidence.map((evidence) => raw(html`<li data-publish-readiness-evidence-item>${evidence}</li>`))}
              </ul>
            `) : ""}
            <code>${item.command}</code>
          </div>
          <span class="publish-state" data-publish-state-label>${publishReadinessStateLabel(item.state)}</span>
        </article>
      `).join("");
    }

    function workflowUiInstallPlanHTML(source) {
      const data = source?.data || null;
      const loaded = !!(source?.loaded && data);
      const plans = loaded && Array.isArray(data.plans) ? data.plans : [];
      const ready = loaded && data.workflowUiInstallReady === true && plans.length >= 2;
      const generatedAt = data?.generatedAt ? formatLocalDateTime(data.generatedAt) : "대기 중";
      const suggestedRepo = data?.suggestedRepo || "";
      const nextVerificationCommand = data?.nextVerificationCommand || "";
      const localTargetParityReady = loaded && data.localTargetParityReady === true;
      const installReceipt = data?.installReceipt || {};
      const installReceiptText = data?.workflowUiInstallPastePacket || data?.uiPastePacket || installReceipt.text || data?.packet || "";
      const pastePacketReady = data?.workflowUiInstallPastePacketReady === true || data?.uiPastePacketReady === true || data?.packetReady === true || installReceipt.ready === true;
      const pastePacketCoverage = finiteNumberOr(data?.workflowUiInstallPastePacketCoverage, pastePacketReady ? 1 : 0);
      const formFieldCoverage = finiteNumberOr(data?.workflowUiInstallFormFieldCoverage, finiteNumberOr(installReceipt.formFieldCoverage, 0));
      const parserReadyProofFieldCoverage = Number(installReceipt.parserReadyProofFieldCoverage || 0);
      const parserReadyProofBlockReady = installReceipt.parserReadyProofBlockReady === true;
      const pagesPlan = plans.find((plan) => plan.key === "pages" || String(plan.targetRepositoryPath || "").includes("joopark-pages.yml")) || {};
      const driftPlan = plans.find((plan) => plan.key === "drift-watch" || String(plan.targetRepositoryPath || "").includes("joopark-drift-watch.yml")) || {};
      const installCommands = Array.isArray(installReceipt.installCommands) ? installReceipt.installCommands : [];
      const expectedSignals = Array.isArray(installReceipt.expectedSignals) ? installReceipt.expectedSignals : [];
      const remoteFileCommand = installReceipt.remoteFileCommand || `node scripts/check-remote-workflow-files.mjs --repo ${suggestedRepo || "OWNER/REPO"} --write`;
      const workflowListCommand = installReceipt.workflowListCommand || `gh workflow list --repo ${suggestedRepo || "OWNER/REPO"} --all --json name,path,state,id`;
      const dispatchPlanCommand = installReceipt.dispatchPlanCommand || nextVerificationCommand || `node scripts/plan-publish-dispatch.mjs --live --repo ${suggestedRepo || "OWNER/REPO"} --write`;
      const handoffVerifyCommand = installReceipt.handoffVerifyCommand || `node scripts/verify-launch-handoff.mjs --repo ${suggestedRepo || "OWNER/REPO"} --write --markdown`;
      const postInstallDispatchGuard = installReceipt.dispatchGuard || "Do not run gh workflow run until every post-install evidence field has been filled, remoteWorkflowFilesReady=true, remoteWorkflowVisibilityReady=true, dispatchReady=true, driftDispatchReady=true, allDispatchReady=true, and verify-launch-handoff reports safeToDispatch=true.";
      const postInstallStopCondition = installReceipt.postInstallStopCondition || "Stop condition: do not run gh workflow run, archive proof, or claim launch until all six post-install evidence fields are filled and verify-launch-handoff reports safeToDispatch=true.";
      const dispatchGuard = postInstallDispatchGuard;
      const planInstallAction = (plan) => plan.installAction || (plan.remoteExists && plan.remoteMatchesTemplate ? "verified_remote_matches_template" : plan.remoteExists ? "replace_existing_remote_file" : "create_missing_remote_file");
      const planInstallRequired = (plan) => plan.uiInstallRequired !== false && planInstallAction(plan) !== "verified_remote_matches_template";
      const planOpenCommand = (plan, fallbackIndex) => plan.uiInstallOpenCommand || (planInstallAction(plan) === "replace_existing_remote_file" ? plan.githubEditFileOpenCommand : plan.githubNewFileOpenCommand) || installCommands[fallbackIndex] || "";
      const planOpenUrl = (plan) => {
        const action = planInstallAction(plan);
        if (action === "replace_existing_remote_file") return plan.githubEditFileUrl || plan.githubNewFileUrl || "";
        if (action === "verified_remote_matches_template") return plan.githubBlobUrl || plan.githubWorkflowUrl || plan.githubEditFileUrl || "";
        return plan.githubNewFileUrl || plan.githubEditFileUrl || "";
      };
      const planInstallDetail = (plan, fallbackTarget, fallbackCommit) => {
        const action = planInstallAction(plan);
        const target = plan.targetRepositoryPath || fallbackTarget;
        if (action === "replace_existing_remote_file") {
          return `installAction=replace_existing_remote_file: open the GitHub edit-file page for ${target}, replace the entire file with the copied YAML, and commit.`;
        }
        if (action === "verified_remote_matches_template") {
          return `installAction=verified_remote_matches_template: no GitHub UI edit is required for ${target}; keep the verified remote file unchanged.`;
        }
        return `installAction=create_missing_remote_file: paste the copied YAML, confirm file name ${plan.githubFileNameFieldValue || target}, and commit with "${plan.suggestedCommitMessage || fallbackCommit}".`;
      };
      const runbookSteps = [
        {
          key: "copy-pages-template",
          label: "Copy Pages template",
          target: pagesPlan.targetRepositoryPath || ".github/workflows/joopark-pages.yml",
          command: pagesPlan.templateCopyCommand || installCommands[0] || "",
          detail: planInstallRequired(pagesPlan) ? `Copy ${pagesPlan.template || "docs/github-pages-workflow.yml"} before opening the GitHub create/edit page.` : "No copy is required while the remote Pages workflow already matches the template.",
          proof: `templateSha256=${pagesPlan.templateSha256 || pagesPlan.sha256 || "missing"}`,
        },
        {
          key: "apply-pages-workflow",
          label: pagesPlan.uiInstallActionLabel || (planInstallAction(pagesPlan) === "replace_existing_remote_file" ? "Replace Pages workflow" : "Create Pages workflow"),
          target: pagesPlan.targetRepositoryPath || ".github/workflows/joopark-pages.yml",
          command: planOpenCommand(pagesPlan, 1) || "no-op: remote workflow file already matches template",
          url: planOpenUrl(pagesPlan),
          detail: planInstallDetail(pagesPlan, ".github/workflows/joopark-pages.yml", "Add JooPark Pages publish workflow"),
          proof: "pages remoteExists=true and remoteMatchesTemplate=true",
        },
        {
          key: "copy-drift-template",
          label: "Copy Drift Watch template",
          target: driftPlan.targetRepositoryPath || ".github/workflows/joopark-drift-watch.yml",
          command: driftPlan.templateCopyCommand || installCommands[2] || "",
          detail: planInstallRequired(driftPlan) ? `Copy ${driftPlan.template || "docs/github-drift-watch-workflow.yml"} before opening the GitHub create/edit page.` : "No copy is required while the remote Drift Watch workflow already matches the template.",
          proof: `templateSha256=${driftPlan.templateSha256 || driftPlan.sha256 || "missing"}`,
        },
        {
          key: "apply-drift-workflow",
          label: driftPlan.uiInstallActionLabel || (planInstallAction(driftPlan) === "verified_remote_matches_template" ? "Verify Drift Watch workflow" : "Create Drift Watch workflow"),
          target: driftPlan.targetRepositoryPath || ".github/workflows/joopark-drift-watch.yml",
          command: planOpenCommand(driftPlan, 3) || "no-op: remote workflow file already matches template",
          url: planOpenUrl(driftPlan),
          detail: planInstallDetail(driftPlan, ".github/workflows/joopark-drift-watch.yml", "Add JooPark candidate drift watch workflow"),
          proof: "drift-watch remoteExists=true and remoteMatchesTemplate=true",
        },
        {
          key: "verify-remote-parity",
          label: "Verify remote file parity",
          target: suggestedRepo || "OWNER/REPO",
          command: remoteFileCommand,
          detail: "Confirm both default-branch workflow files match the local template SHA-256 values.",
          proof: "remoteWorkflowFilesReady=true",
        },
        {
          key: "verify-workflow-visibility",
          label: "Verify workflow visibility",
          target: data?.actionsUrl || `${data?.repositoryUrl || "https://github.com/OWNER/REPO"}/actions`,
          command: workflowListCommand,
          url: data?.actionsUrl || "",
          detail: "Confirm GitHub Actions lists both workflow files before any dispatch attempt.",
          proof: "remoteWorkflowVisibilityReady=true",
        },
        {
          key: "verify-dispatch-guard",
          label: "Recheck dispatch guard",
          target: suggestedRepo || "OWNER/REPO",
          command: dispatchPlanCommand,
          detail: "Run the repo-scoped live plan and then the handoff verifier before dispatch.",
          proof: "dispatchReady=true; driftDispatchReady=true; allDispatchReady=true; safeToDispatch=true",
          secondaryCommand: handoffVerifyCommand,
        },
      ];
      const runbookReady = ready && runbookSteps.every((step) => step.command);
      const postInstallEvidenceIntakeCommands = [
        remoteFileCommand,
        workflowListCommand,
        dispatchPlanCommand,
        handoffVerifyCommand,
      ].filter(Boolean);
      const postInstallEvidenceIntakeSequence = [
        {
          key: "remote_file_parity",
          label: "Remote workflow file check",
          command: remoteFileCommand,
          expected: "remoteWorkflowFilesReady=true",
        },
        {
          key: "actions_visibility",
          label: "Actions visibility check",
          command: workflowListCommand,
          expected: "remoteWorkflowVisibilityReady=true",
        },
        {
          key: "dispatch_readiness",
          label: "Dispatch readiness plan",
          command: dispatchPlanCommand,
          expected: "allDispatchReady=true",
        },
        {
          key: "handoff_verifier",
          label: "Launch handoff verifier",
          command: handoffVerifyCommand,
          expected: "safeToDispatch=true before gh workflow run",
        },
      ].filter((step) => step.command);
      const postInstallEvidenceIntakeSequenceReady = postInstallEvidenceIntakeSequence.length === 4 &&
        postInstallEvidenceIntakeSequence.every((step) => step.expected);
      const postInstallEvidenceIntakeFinalCommand = postInstallEvidenceIntakeSequence[postInstallEvidenceIntakeSequence.length - 1]?.command || "";
      const quickProofEvidenceFieldByKey = {
        remote_file_parity: "remote_parity_proof",
        actions_visibility: "actions_visibility_proof",
        dispatch_readiness: "dispatch_readiness_proof",
        handoff_verifier: "handoff_verifier_proof",
      };
      const postInstallQuickProofSteps = postInstallEvidenceIntakeSequence.map((step) => ({
        key: step.key,
        label: step.label,
        command: step.command,
        expected: step.expected,
        evidenceFieldKey: quickProofEvidenceFieldByKey[step.key] || "",
        status: "evidence_required",
      }));
      const postInstallQuickProofStepCount = postInstallQuickProofSteps.length;
      const postInstallQuickProofCoverage = postInstallQuickProofStepCount === 4 &&
        postInstallQuickProofSteps.every((step) => step.command && step.expected && step.evidenceFieldKey) ? 1 : 0;
      const postInstallQuickProofReady = postInstallEvidenceIntakeSequenceReady && postInstallQuickProofCoverage === 1;
      const postInstallEvidenceIntakeSignals = expectedSignals.length ? expectedSignals : [
        "remoteWorkflowFilesReady=true",
        "pages remoteExists=true and remoteMatchesTemplate=true",
        "drift-watch remoteExists=true and remoteMatchesTemplate=true",
        "remoteWorkflowVisibilityReady=true",
        "dispatchReady=true",
        "driftDispatchReady=true",
        "allDispatchReady=true",
        "safeToDispatch=true before gh workflow run",
      ];
      const postInstallEvidenceIntakeChecklist = [
        "Paste the two default-branch workflow commit URLs or SHA values.",
        "Paste the remote workflow file check output with remoteWorkflowFilesReady=true.",
        "Paste the gh workflow list output showing both workflow paths visible in Actions.",
        "Paste the publish dispatch plan output showing allDispatchReady=true.",
        "Paste the launch handoff verifier output showing safeToDispatch=true before any gh workflow run.",
      ];
      const postInstallEvidenceIntakeFields = [
        ["Pages workflow commit", "[paste commit URL or SHA for .github/workflows/joopark-pages.yml on the default branch]"],
        ["Drift Watch workflow commit", "[paste commit URL or SHA for .github/workflows/joopark-drift-watch.yml on the default branch]"],
        ["Remote parity proof", "[paste generatedAt plus remoteWorkflowFilesReady=true from data/remote-workflow-file-check.json]"],
        ["Actions visibility proof", "[paste gh workflow list output showing both workflow paths visible]"],
        ["Dispatch readiness proof", "[paste generatedAt plus dispatchReady=true, driftDispatchReady=true, and allDispatchReady=true]"],
        ["Handoff verifier proof", "[paste verify-launch-handoff status plus safeToDispatch=true before gh workflow run]"],
      ];
      const postInstallProofParserFields = [
        ["pages_workflow_commit", "Pages workflow commit", ".github/workflows/joopark-pages.yml commit URL or SHA", "Paste the default-branch commit URL or SHA for .github/workflows/joopark-pages.yml from GitHub UI."],
        ["drift_workflow_commit", "Drift Watch workflow commit", ".github/workflows/joopark-drift-watch.yml commit URL or SHA", "Paste the default-branch commit URL or SHA for .github/workflows/joopark-drift-watch.yml from GitHub UI."],
        ["remote_parity_proof", "Remote parity proof", "remoteWorkflowFilesReady=true", "Run node scripts/check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write and paste remoteWorkflowFilesReady=true."],
        ["actions_visibility_proof", "Actions visibility proof", "remoteWorkflowVisibilityReady=true or gh workflow list shows both workflow paths", "Run node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects --write and paste remoteWorkflowVisibilityReady=true."],
        ["dispatch_readiness_proof", "Dispatch readiness proof", "dispatchReady=true, driftDispatchReady=true, allDispatchReady=true", "Rerun node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects --write and paste dispatchReady=true, driftDispatchReady=true, and allDispatchReady=true."],
        ["handoff_verifier_proof", "Handoff verifier proof", "verify-launch-handoff reports safeToDispatch=true before gh workflow run", "Run node scripts/verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown and paste safeToDispatch=true."],
      ];
      const postInstallProofParserCoverage = postInstallProofParserFields.length === postInstallEvidenceIntakeFields.length ? 1 : 0;
      const postInstallProofParserReady = postInstallProofParserCoverage === 1;
      const postInstallProofParserSample = [
        "pages_workflow_commit: https://github.com/biojuho/BIOJUHO-Projects/commit/abc1234 for .github/workflows/joopark-pages.yml",
        "drift_workflow_commit: https://github.com/biojuho/BIOJUHO-Projects/commit/def5678 for .github/workflows/joopark-drift-watch.yml",
        "remote_parity_proof: generatedAt=2026-06-08T00:00:00Z remoteWorkflowFilesReady=true remoteExists=true remoteMatchesTemplate=true",
        "actions_visibility_proof: gh workflow list shows .github/workflows/joopark-pages.yml and .github/workflows/joopark-drift-watch.yml; remoteWorkflowVisibilityReady=true",
        "dispatch_readiness_proof: dispatchReady=true driftDispatchReady=true allDispatchReady=true",
        "handoff_verifier_proof: verify-launch-handoff reports safeToDispatch=true before gh workflow run",
      ].join("\n");
      const postInstallProofParserReceipt = [
        "JooPark Post-Install Proof Parser Receipt",
        "Status: waiting_for_pasted_proof",
        `Repo: ${suggestedRepo || "OWNER/REPO"}`,
        `postInstallProofParserCoverage=${postInstallProofParserCoverage}`,
        `Fields detected: 0/${postInstallProofParserFields.length}`,
        "not dispatch approval",
        "Required parser fields:",
        ...postInstallProofParserFields.map(([key, label, required, nextAction]) => `- ${key}: ${label}; required=${required}; detected=false; nextAction=${nextAction}`),
        "",
        "Missing field repair hints:",
        ...postInstallProofParserFields.map(([key, _label, _required, nextAction]) => `- ${key}: ${nextAction}`),
        "",
        postInstallStopCondition,
      ].join("\n");
      const postInstallFieldByKey = {
        remote_parity_proof: postInstallEvidenceIntakeFields[2],
        actions_visibility_proof: postInstallEvidenceIntakeFields[3],
        dispatch_readiness_proof: postInstallEvidenceIntakeFields[4],
        handoff_verifier_proof: postInstallEvidenceIntakeFields[5],
      };
      const postInstallQuickProofFieldMappings = postInstallQuickProofSteps.map((step) => {
        const field = postInstallFieldByKey[step.evidenceFieldKey] || [];
        return {
          stepKey: step.key,
          stepLabel: step.label,
          fieldKey: step.evidenceFieldKey,
          fieldLabel: field[0] || "",
          fieldStatus: "evidence_required",
          fieldCompleted: false,
          currentValue: field[1] || "not available",
          expectedValue: step.expected,
          proofCommand: step.command,
          stopCondition: dispatchGuard,
        };
      });
      const postInstallQuickProofMappedFieldCount = postInstallQuickProofFieldMappings.length;
      const postInstallQuickProofCompletedMappedFieldCount = 0;
      const postInstallQuickProofFieldMappingCoverage = postInstallQuickProofMappedFieldCount === 4 &&
        postInstallQuickProofFieldMappings.every((item) => item.stepKey && item.fieldKey && item.fieldLabel && item.proofCommand && item.expectedValue) ? 1 : 0;
      const postInstallQuickProofFieldMappingReady = postInstallQuickProofFieldMappingCoverage === 1;
      const postInstallEvidenceIntakeFieldCoverage = postInstallEvidenceIntakeFields.length >= 6 ? 1 : 0;
      const postInstallEvidenceIntakeReady = runbookReady &&
        postInstallEvidenceIntakeCommands.length >= 4 &&
        postInstallEvidenceIntakeSignals.length >= 8 &&
        postInstallEvidenceIntakeFieldCoverage === 1;
      const postInstallQuickProofReceipt = [
        "JooPark Post-Install Quick Proof Receipt",
        "Status: collect_post_install_proof",
        `Repo: ${suggestedRepo || "OWNER/REPO"}`,
        `Default branch: ${data?.defaultBranch || "main"}`,
        "Proof complete: false",
        `Fields complete: 0/${postInstallEvidenceIntakeFields.length}`,
        `Quick proof steps: ${postInstallQuickProofStepCount}`,
        "",
        "4-step proof checklist:",
        ...postInstallQuickProofSteps.map((step, index) => `${index + 1}. ${step.key}: run ${step.command}; expect ${step.expected}; paste into ${step.evidenceFieldKey}`),
        "",
        "Mapped proof fields:",
        ...postInstallQuickProofFieldMappings.map((item, index) => `${index + 1}. ${item.stepKey} -> ${item.fieldKey}: ${item.fieldStatus}; completed=${item.fieldCompleted}; current=${item.currentValue}; expected=${item.expectedValue}`),
        "",
        "Six evidence fields remain required:",
        ...postInstallEvidenceIntakeFields.map(([label, placeholder]) => `- ${label}: ${placeholder}`),
        "",
        postInstallStopCondition,
      ].join("\n");
      const postInstallEvidenceIntakeText = [
        "# JooPark Workflow Post-Install Evidence Intake",
        "",
        "Status: collect post-install proof only; not dispatch approval",
        `Repo: ${suggestedRepo || "OWNER/REPO"}`,
        `Default branch: ${data?.defaultBranch || "main"}`,
        `Quick proof: ready=${postInstallQuickProofReady}; steps=${postInstallQuickProofStepCount}; coverage=${postInstallQuickProofCoverage}`,
        `Quick proof field mapping: ready=${postInstallQuickProofFieldMappingReady}; mapped=${postInstallQuickProofMappedFieldCount}; completed=${postInstallQuickProofCompletedMappedFieldCount}/${postInstallQuickProofMappedFieldCount}; coverage=${postInstallQuickProofFieldMappingCoverage}`,
        "",
        postInstallQuickProofReceipt,
        "",
        "Required proof fields:",
        "- Pages workflow committed to `.github/workflows/joopark-pages.yml` on the default branch",
        "- Drift Watch workflow committed to `.github/workflows/joopark-drift-watch.yml` on the default branch",
        "- remoteWorkflowFilesReady=true",
        "- remoteWorkflowVisibilityReady=true",
        "- dispatchReady=true, driftDispatchReady=true, allDispatchReady=true",
        "- safeToDispatch=true before gh workflow run",
        "",
        "Evidence fields to fill:",
        ...postInstallEvidenceIntakeFields.map(([label, placeholder]) => `- ${label}: ${placeholder}`),
        "",
        "Verification commands to run after GitHub UI install:",
        ...postInstallEvidenceIntakeCommands.map((command, index) => `${index + 1}. ${command}`),
        "",
        "Verification sequence:",
        ...postInstallEvidenceIntakeSequence.map((step, index) => `${index + 1}. ${step.key}: ${step.label}; command=${step.command}; expected=${step.expected}`),
        "",
        "Expected success signals:",
        ...postInstallEvidenceIntakeSignals.map((signal) => `- ${signal}`),
        "",
        "Evidence checklist:",
        ...postInstallEvidenceIntakeChecklist.map((item) => `- [ ] ${item}`),
        "",
        "Dispatch guard:",
        dispatchGuard,
        postInstallStopCondition,
        "Do not run gh workflow run until every post-install evidence field has been filled and verify-launch-handoff reports safeToDispatch=true.",
      ].join("\n");
      return html`
        <div class="workflow-ui-install-plan" data-system-workflow-ui-install-plan data-workflow-ui-install-source="${source?.source || "data/workflow-ui-install-plan.json"}" data-workflow-ui-install-loaded="${loaded ? "true" : "false"}" data-workflow-ui-install-ready="${ready ? "true" : "false"}" data-workflow-ui-install-target-parity-ready="${localTargetParityReady ? "true" : "false"}" data-workflow-ui-install-plan-count="${plans.length}" data-workflow-ui-install-suggested-repo="${suggestedRepo}" data-workflow-ui-install-next-command="${nextVerificationCommand}" data-workflow-ui-install-receipt-ready="${installReceipt.ready ? "true" : "false"}" data-workflow-ui-install-receipt-command-count="${installReceipt.commandCount || 0}" data-workflow-ui-install-receipt-checklist-count="${installReceipt.checklistCount || 0}" data-workflow-ui-install-receipt-expected-count="${installReceipt.expectedSignalCount || 0}" data-workflow-ui-install-receipt-verify-command="${installReceipt.handoffVerifyCommand || ""}" data-workflow-ui-install-paste-packet-ready="${pastePacketReady ? "true" : "false"}" data-workflow-ui-install-paste-packet-coverage="${pastePacketCoverage}" data-workflow-ui-install-parser-ready-proof-block-ready="${parserReadyProofBlockReady ? "true" : "false"}" data-workflow-ui-install-parser-ready-proof-field-coverage="${parserReadyProofFieldCoverage}" data-workflow-ui-install-form-field-coverage="${formFieldCoverage}" data-workflow-ui-install-runbook-ready="${runbookReady ? "true" : "false"}" data-workflow-ui-install-runbook-step-count="${runbookSteps.length}" data-workflow-ui-install-runbook-expected-signal-count="${expectedSignals.length}" data-workflow-ui-install-runbook-remote-file-command="${remoteFileCommand}" data-workflow-ui-install-runbook-dispatch-command="${dispatchPlanCommand}" data-workflow-ui-install-runbook-handoff-command="${handoffVerifyCommand}" data-workflow-ui-install-intake-ready="${postInstallEvidenceIntakeReady ? "true" : "false"}" data-workflow-ui-install-intake-command-count="${postInstallEvidenceIntakeCommands.length}" data-workflow-ui-install-intake-signal-count="${postInstallEvidenceIntakeSignals.length}" data-workflow-ui-install-intake-field-count="${postInstallEvidenceIntakeFields.length}" data-workflow-ui-install-intake-field-coverage="${postInstallEvidenceIntakeFieldCoverage}" data-workflow-ui-install-intake-sequence-count="${postInstallEvidenceIntakeSequence.length}" data-workflow-ui-install-intake-final-command="${postInstallEvidenceIntakeFinalCommand}" data-post-install-quick-proof-ready="${postInstallQuickProofReady ? "true" : "false"}" data-post-install-quick-proof-step-count="${postInstallQuickProofStepCount}" data-post-install-quick-proof-coverage="${postInstallQuickProofCoverage}" data-post-install-quick-proof-final-command="${postInstallEvidenceIntakeFinalCommand}" data-post-install-quick-proof-field-mapping-ready="${postInstallQuickProofFieldMappingReady ? "true" : "false"}" data-post-install-quick-proof-field-mapping-coverage="${postInstallQuickProofFieldMappingCoverage}" data-post-install-quick-proof-mapped-field-count="${postInstallQuickProofMappedFieldCount}" data-post-install-quick-proof-completed-mapped-field-count="${postInstallQuickProofCompletedMappedFieldCount}">
          <div class="publish-evidence-head">
            <strong>GitHub UI workflow install plan</strong>
            <span class="publish-state">${ready ? "ready" : "check required"}</span>
          </div>
          <p class="settings-note">GitHub 공식 workflow는 repository root의 <code>.github/workflows</code>에 YAML 파일로 저장되어야 하고, 수동 실행은 default branch의 <code>workflow_dispatch</code> workflow에서만 가능합니다. 아래 plan은 각 workflow의 <code>installAction</code>에 따라 GitHub UI create/edit/no-op 경로, 복사 명령, 확인 URL을 고정합니다.</p>
          <div class="workflow-ui-install-runbook" data-workflow-ui-install-runbook data-workflow-ui-install-runbook-ready="${runbookReady ? "true" : "false"}" data-workflow-ui-install-runbook-step-count="${runbookSteps.length}" data-workflow-ui-install-runbook-expected-signal-count="${expectedSignals.length}" data-workflow-ui-install-runbook-dispatch-guard="${dispatchGuard}">
            <div class="workflow-ui-install-runbook-head">
              <span>default branch runbook</span>
              <strong>GitHub UI install first, dispatch later</strong>
              <p>Use this sequence when CLI workflow scope is missing. Complete both file commits, prove remote parity and Actions visibility, then keep dispatch withheld until the handoff verifier reports safeToDispatch=true.</p>
            </div>
            <ol>
              ${runbookSteps.map((step, index) => raw(html`
                <li data-workflow-ui-install-runbook-step data-workflow-ui-install-runbook-step-key="${step.key}" data-workflow-ui-install-runbook-step-command="${step.command}" data-workflow-ui-install-runbook-step-target="${step.target}" data-workflow-ui-install-runbook-step-proof="${step.proof}">
                  <span>${String(index + 1).padStart(2, "0")}</span>
                  <div>
                    <strong>${step.label}</strong>
                    <p>${step.detail}</p>
                    <code>${step.command || "command unavailable"}</code>
                    ${step.secondaryCommand ? raw(html`<code>${step.secondaryCommand}</code>`) : ""}
                    ${step.url ? raw(html`<a href="${step.url}" target="_blank" rel="noopener" data-workflow-ui-install-runbook-link>open target</a>`) : ""}
                    <small>${step.proof}</small>
                  </div>
                </li>
              `))}
            </ol>
            <div class="workflow-ui-install-runbook-signals" data-workflow-ui-install-runbook-signals>
              ${expectedSignals.map((signal) => raw(html`<span data-workflow-ui-install-runbook-signal>${signal}</span>`))}
            </div>
            <p class="workflow-ui-install-runbook-guard" data-workflow-ui-install-runbook-guard>${dispatchGuard}</p>
          </div>
          <div class="post-install-evidence-intake workflow-ui-install-intake" data-post-install-evidence-intake data-workflow-ui-install-intake data-post-install-evidence-intake-ready="${postInstallEvidenceIntakeReady ? "true" : "false"}" data-post-install-evidence-intake-command-count="${postInstallEvidenceIntakeCommands.length}" data-post-install-evidence-intake-signal-count="${postInstallEvidenceIntakeSignals.length}" data-post-install-evidence-intake-field-count="${postInstallEvidenceIntakeFields.length}" data-post-install-evidence-intake-field-coverage="${postInstallEvidenceIntakeFieldCoverage}" data-post-install-evidence-intake-sequence-count="${postInstallEvidenceIntakeSequence.length}" data-post-install-evidence-intake-sequence-ready="${postInstallEvidenceIntakeSequenceReady ? "true" : "false"}" data-post-install-evidence-intake-final-command="${postInstallEvidenceIntakeFinalCommand}" data-post-install-evidence-intake-dispatch-guard="${dispatchGuard}" data-post-install-quick-proof-ready="${postInstallQuickProofReady ? "true" : "false"}" data-post-install-quick-proof-step-count="${postInstallQuickProofStepCount}" data-post-install-quick-proof-coverage="${postInstallQuickProofCoverage}" data-post-install-quick-proof-final-command="${postInstallEvidenceIntakeFinalCommand}" data-post-install-quick-proof-field-mapping-ready="${postInstallQuickProofFieldMappingReady ? "true" : "false"}" data-post-install-quick-proof-field-mapping-coverage="${postInstallQuickProofFieldMappingCoverage}" data-post-install-quick-proof-mapped-field-count="${postInstallQuickProofMappedFieldCount}" data-post-install-quick-proof-completed-mapped-field-count="${postInstallQuickProofCompletedMappedFieldCount}">
            <div class="post-install-evidence-intake-head">
              <span>post-install evidence intake</span>
              <strong>Collect proof before dispatch</strong>
              <p>After both GitHub UI commits, run these checks and paste the results into this template. This is not launch proof and does not allow gh workflow run until every post-install evidence field, remote workflow parity, Actions visibility, dispatch readiness, and the handoff verifier have passed.</p>
            </div>
            <div class="post-install-quick-proof" data-post-install-quick-proof data-post-install-quick-proof-ready="${postInstallQuickProofReady ? "true" : "false"}" data-post-install-quick-proof-step-count="${postInstallQuickProofStepCount}" data-post-install-quick-proof-coverage="${postInstallQuickProofCoverage}">
              <span>Quick proof</span>
              <ol>
                ${postInstallQuickProofSteps.map((step, index) => raw(html`
                  <li data-post-install-quick-proof-step data-post-install-quick-proof-step-key="${step.key || ""}" data-post-install-quick-proof-step-command="${step.command || ""}" data-post-install-quick-proof-step-expected="${step.expected || ""}" data-post-install-quick-proof-step-field="${step.evidenceFieldKey || ""}">
                    <strong>${index + 1}. ${step.label || step.key}</strong>
                    <code>${step.command || ""}</code>
                    <small>${step.expected || ""}</small>
                  </li>
                `))}
              </ol>
            </div>
            <div class="post-install-quick-proof-map" data-post-install-quick-proof-field-map data-post-install-quick-proof-field-mapping-ready="${postInstallQuickProofFieldMappingReady ? "true" : "false"}" data-post-install-quick-proof-field-mapping-coverage="${postInstallQuickProofFieldMappingCoverage}" data-post-install-quick-proof-mapped-field-count="${postInstallQuickProofMappedFieldCount}" data-post-install-quick-proof-completed-mapped-field-count="${postInstallQuickProofCompletedMappedFieldCount}">
              <span>Mapped fields</span>
              <ol>
                ${postInstallQuickProofFieldMappings.map((item, index) => raw(html`
                  <li data-post-install-quick-proof-field-map-item data-post-install-quick-proof-field-map-step="${item.stepKey || ""}" data-post-install-quick-proof-field-map-field="${item.fieldKey || ""}" data-post-install-quick-proof-field-map-status="${item.fieldStatus || ""}" data-post-install-quick-proof-field-map-completed="${item.fieldCompleted ? "true" : "false"}">
                    <strong>${index + 1}. ${item.stepKey || "step"} -> ${item.fieldLabel || item.fieldKey}</strong>
                    <small>${item.fieldStatus || "missing"} · completed=${item.fieldCompleted ? "true" : "false"}</small>
                    <p>${item.currentValue || ""}</p>
                  </li>
                `))}
              </ol>
            </div>
            <ol class="post-install-evidence-intake-checklist">
              ${postInstallEvidenceIntakeChecklist.map((item) => raw(html`<li data-post-install-evidence-intake-check>${item}</li>`))}
            </ol>
            <dl class="post-install-evidence-intake-fields">
              ${postInstallEvidenceIntakeFields.map(([label, placeholder]) => raw(html`<div data-post-install-evidence-intake-field data-post-install-evidence-intake-field-label="${label}"><dt>${label}</dt><dd>${placeholder}</dd></div>`))}
            </dl>
            <div class="post-install-evidence-intake-sequence" data-post-install-evidence-intake-sequence data-post-install-evidence-intake-sequence-count="${postInstallEvidenceIntakeSequence.length}" data-post-install-evidence-intake-sequence-ready="${postInstallEvidenceIntakeSequenceReady ? "true" : "false"}">
              <span>Verification sequence</span>
              <ol>
                ${postInstallEvidenceIntakeSequence.map((step, index) => raw(html`
                  <li data-post-install-evidence-intake-sequence-step data-post-install-evidence-intake-sequence-key="${step.key}" data-post-install-evidence-intake-sequence-command="${step.command}" data-post-install-evidence-intake-sequence-expected="${step.expected}">
                    <strong>${index + 1}. ${step.label}</strong>
                    <code>${step.command}</code>
                    <small>${step.expected}</small>
                  </li>
                `))}
              </ol>
            </div>
            <div class="post-install-evidence-intake-commands">
              ${postInstallEvidenceIntakeCommands.map((command) => raw(html`<code data-post-install-evidence-intake-command>${command}</code>`))}
            </div>
            <div class="post-install-evidence-intake-signals">
              ${postInstallEvidenceIntakeSignals.map((signal) => raw(html`<span data-post-install-evidence-intake-signal>${signal}</span>`))}
            </div>
            <div class="post-install-proof-parser" data-post-install-proof-parser data-post-install-proof-parser-ready="${postInstallProofParserReady ? "true" : "false"}" data-post-install-proof-parser-coverage="${postInstallProofParserCoverage}" data-post-install-proof-parser-field-count="${postInstallProofParserFields.length}" data-post-install-proof-parser-detected-count="0" data-post-install-proof-parser-status="waiting_for_pasted_proof" data-post-install-proof-parser-dispatch-approval="false">
              <div class="post-install-proof-parser-head">
                <span>proof parser</span>
                <strong>Paste combined proof and check gaps</strong>
                <p>Local parser only. It detects whether the six post-install proof fields are present and keeps dispatch blocked until the verifier separately reports safeToDispatch=true.</p>
              </div>
              <label class="post-install-proof-parser-input">
                <span>Combined proof</span>
                <textarea rows="7" spellcheck="false" data-post-install-proof-parser-input placeholder="${postInstallProofParserSample}"></textarea>
              </label>
              <div class="post-install-proof-parser-status" role="status" aria-live="polite" data-post-install-proof-parser-status-text>0/${postInstallProofParserFields.length} proof signals detected - not dispatch approval</div>
              <ol class="post-install-proof-parser-fields" data-post-install-proof-parser-fields>
                ${postInstallProofParserFields.map(([key, label, required, nextAction]) => raw(html`
                  <li data-post-install-proof-parser-field data-post-install-proof-parser-field-key="${key}" data-post-install-proof-parser-field-label="${label}" data-post-install-proof-parser-field-required="${required}" data-post-install-proof-parser-field-next-action="${nextAction}" data-post-install-proof-parser-field-detected="false">
                    <strong>${label}</strong>
                    <span>missing</span>
                    <small>${required}</small>
                    <small data-post-install-proof-parser-field-next-action>Next: ${nextAction}</small>
                  </li>
                `))}
              </ol>
              <pre data-post-install-proof-parser-summary>${postInstallProofParserReceipt}</pre>
              <div class="post-install-proof-parser-actions">
                <button type="button" class="portfolio-export-download portfolio-export-copy" data-action="parse-post-install-proof" data-post-install-proof-parser-parse>parser 점검</button>
                <button type="button" class="portfolio-export-download portfolio-export-copy" data-action="copy-post-install-proof-parser-summary" data-post-install-proof-parser-copy>parser summary 복사</button>
                <small class="portfolio-export-status" data-post-install-proof-parser-copy-status aria-live="polite"></small>
              </div>
            </div>
            <pre data-post-install-evidence-intake-text>${postInstallEvidenceIntakeText}</pre>
            <button type="button" class="portfolio-export-download portfolio-export-copy" data-action="copy-post-install-evidence-intake" data-post-install-evidence-intake-copy>intake template 복사</button>
            <small class="portfolio-export-status" data-post-install-evidence-intake-copy-status aria-live="polite"></small>
          </div>
          <dl class="storage-grid">
            <div><dt>source</dt><dd>${source?.source || "data/workflow-ui-install-plan.json"}</dd></div>
            <div><dt>generated</dt><dd>${generatedAt}</dd></div>
            <div><dt>suggestedRepo</dt><dd>${suggestedRepo || "not available"}</dd></div>
            <div><dt>defaultBranch</dt><dd>${data?.defaultBranch || "unknown"}</dd></div>
            <div><dt>plans</dt><dd>${plans.length}</dd></div>
            <div><dt>workflowUiInstallReady</dt><dd>${ready ? "true" : "false"}</dd></div>
            <div><dt>localTargetParityReady</dt><dd>${localTargetParityReady ? "true" : "false"}</dd></div>
            <div><dt>installReceiptReady</dt><dd>${installReceipt.ready ? "true" : "false"}</dd></div>
            <div><dt>workflowUiInstallPastePacketCoverage</dt><dd>${pastePacketCoverage}</dd></div>
            <div><dt>parserReadyProofFieldCoverage</dt><dd>${parserReadyProofFieldCoverage}</dd></div>
            <div><dt>parserReadyProofBlockReady</dt><dd>${parserReadyProofBlockReady ? "true" : "false"}</dd></div>
            <div><dt>workflowUiInstallFormFieldCoverage</dt><dd>${formFieldCoverage}</dd></div>
          </dl>
          ${source?.error ? raw(html`<p class="settings-note storage-error">workflow install plan load error: ${source.error}</p>`) : ""}
          <div class="workflow-ui-install-cards">
            ${plans.map((plan) => raw(html`
              <article class="workflow-ui-install-card" data-workflow-ui-install-card data-workflow-ui-install-key="${plan.key}" data-workflow-ui-install-target="${plan.targetRepositoryPath || ""}" data-workflow-ui-install-file-name-field="${plan.githubFileNameFieldValue || ""}" data-workflow-ui-install-commit-message="${plan.suggestedCommitMessage || ""}" data-workflow-ui-install-ready="${plan.uiInstallReady ? "true" : "false"}" data-workflow-ui-install-target-matches-template="${plan.targetMatchesTemplate ? "true" : "false"}" data-workflow-ui-install-action="${planInstallAction(plan)}" data-workflow-ui-install-required="${planInstallRequired(plan) ? "true" : "false"}" data-workflow-ui-install-open-command="${plan.uiInstallOpenCommand || ""}" data-workflow-ui-install-edit-url="${plan.githubEditFileUrl || ""}">
                <div>
                  <span>${plan.key}</span>
                  <strong>${plan.name || plan.workflowName || plan.targetRepositoryPath}</strong>
                  <p>${plan.targetRepositoryPath}</p>
                </div>
                <dl>
                  <div><dt>installAction</dt><dd>${planInstallAction(plan)}</dd></div>
                  <div><dt>template</dt><dd><code>${plan.template || ""}</code></dd></div>
                  <div><dt>sha256</dt><dd><code>${plan.sha256 || plan.templateSha256 || "missing"}</code></dd></div>
                  <div><dt>targetSha256</dt><dd><code>${plan.targetSha256 || "missing"}</code></dd></div>
                  <div><dt>targetMatchesTemplate</dt><dd>${plan.targetMatchesTemplate ? "true" : "false"}</dd></div>
                  <div><dt>remoteMatchesTemplate</dt><dd>${plan.remoteMatchesTemplate ? "true" : "false"}</dd></div>
                  <div><dt>templateCopyCommand</dt><dd><code>${plan.templateCopyCommand || ""}</code></dd></div>
                  <div><dt>create</dt><dd>${plan.githubNewFileUrl ? raw(html`<a href="${plan.githubNewFileUrl}" target="_blank" rel="noopener" data-workflow-ui-install-new-file>githubNewFileUrl</a>`) : "new file URL 대기"}</dd></div>
                  <div><dt>edit</dt><dd>${plan.githubEditFileUrl ? raw(html`<a href="${plan.githubEditFileUrl}" target="_blank" rel="noopener" data-workflow-ui-install-edit-file>githubEditFileUrl</a>`) : "edit file URL 대기"}</dd></div>
                  <div><dt>githubNewFileOpenCommand</dt><dd><code>${plan.githubNewFileOpenCommand || ""}</code></dd></div>
                  <div><dt>githubEditFileOpenCommand</dt><dd><code>${plan.githubEditFileOpenCommand || ""}</code></dd></div>
                  <div><dt>uiInstallOpenCommand</dt><dd><code>${plan.uiInstallOpenCommand || "no GitHub UI command required"}</code></dd></div>
                  <div><dt>githubFileNameFieldValue</dt><dd><code>${plan.githubFileNameFieldValue || plan.targetRepositoryPath || ""}</code></dd></div>
                  <div><dt>suggestedCommitMessage</dt><dd><code>${plan.suggestedCommitMessage || ""}</code></dd></div>
                  <div><dt>confirm</dt><dd>${plan.githubWorkflowUrl ? raw(html`<a href="${plan.githubWorkflowUrl}" target="_blank" rel="noopener" data-workflow-ui-install-workflow-url>githubWorkflowUrl</a>`) : "workflow URL 대기"}</dd></div>
                  <div><dt>githubWorkflowOpenCommand</dt><dd><code>${plan.githubWorkflowOpenCommand || ""}</code></dd></div>
                </dl>
              </article>
            `))}
          </div>
          <div class="workflow-ui-install-next" data-workflow-ui-install-next>
            <span>nextVerificationCommand</span>
            <code>${nextVerificationCommand || "node scripts/plan-publish-dispatch.mjs --live --repo OWNER/REPO"}</code>
          </div>
          ${installReceiptText ? raw(html`
            <div class="launch-execution-copy workflow-ui-install-receipt" data-workflow-ui-install-receipt data-workflow-ui-install-paste-packet data-workflow-ui-install-receipt-ready="${installReceipt.ready ? "true" : "false"}" data-workflow-ui-install-paste-packet-ready="${pastePacketReady ? "true" : "false"}">
              <div>
                <span>copy-ready UI paste packet</span>
                <strong>${installReceipt.label || "GitHub UI workflow install receipt"}</strong>
              </div>
              <pre data-workflow-ui-install-receipt-text data-workflow-ui-install-paste-packet-text>${installReceiptText}</pre>
              <button type="button" class="portfolio-export-download portfolio-export-copy" data-action="copy-workflow-ui-install-receipt" data-workflow-ui-install-receipt-copy data-workflow-ui-install-paste-packet-copy>UI paste packet 복사</button>
              <small class="portfolio-export-status" data-workflow-ui-install-receipt-copy-status aria-live="polite"></small>
            </div>
          `) : ""}
        </div>
      `;
    }

    function publishDispatchPlanHTML(source) {
      const data = source?.data || null;
      const loaded = !!(source?.loaded && data);
      const plans = loaded && Array.isArray(data.workflowPlans) ? data.workflowPlans : [];
      const blockers = loaded && Array.isArray(data.blockers) ? data.blockers : [];
      const nextActions = loaded && Array.isArray(data.nextActions) ? data.nextActions : [];
      const suggestedCommands = loaded && Array.isArray(data.suggestedCommands) ? data.suggestedCommands : [];
      const suggestedDispatchCommands = loaded && Array.isArray(data.suggestedDispatchCommands) ? data.suggestedDispatchCommands : [];
      const withheldDispatchCommands = loaded && Array.isArray(data.withheldDispatchCommands) ? data.withheldDispatchCommands : [];
      const suggestedDispatchCommandCount = loaded && Number.isFinite(Number(data.suggestedDispatchCommandCount))
        ? Number(data.suggestedDispatchCommandCount)
        : suggestedDispatchCommands.length;
      const withheldDispatchCommandCount = loaded && Number.isFinite(Number(data.withheldDispatchCommandCount))
        ? Number(data.withheldDispatchCommandCount)
        : withheldDispatchCommands.length;
      const dispatchSuggestionStatus = data?.dispatchSuggestionStatus || "withheld-until-all-dispatch-ready";
      const allReady = loaded && data.allDispatchReady === true;
      const dispatchReady = loaded && data.dispatchReady === true;
      const driftReady = loaded && data.driftDispatchReady === true;
      const repoReady = loaded && data.repoEvidenceReady === true;
      const localTargetsReady = loaded && data.localWorkflowTargetsReady === true;
      const localTargetParityReady = loaded && data.localTargetParityReady === true;
      const remoteVisible = loaded && data.remoteWorkflowVisibilityReady === true;
      const workflowScopeChecked = loaded && data.workflowScopeChecked === true;
      const workflowScopeAvailable = loaded && data.workflowScopeAvailable === true;
      const workflowScopeInstallBlocked = loaded && data.workflowScopeInstallBlocked === true;
      const workflowScope = loaded && data.workflowScope && typeof data.workflowScope === "object" ? data.workflowScope : {};
      const workflowScopes = Array.isArray(workflowScope.scopes)
        ? workflowScope.scopes.map((scope) => String(scope)).filter(Boolean)
        : [];
      const workflowScopeList = workflowScopes.length ? workflowScopes.join(", ") : workflowScopeChecked ? "none reported" : "not checked";
      const workflowScopeMissing = workflowScopeChecked && !workflowScopes.includes("workflow") ? "workflow" : "";
      const workflowScopeSource = workflowScope.source || (workflowScopeChecked ? "unknown" : "not checked");
      const workflowScopeStatus = workflowScopeChecked
        ? workflowScopeAvailable ? "workflow scope available" : "workflow scope missing"
        : "scope not checked";
      const workflowScopeAvailabilityLabel = workflowScopeChecked ? workflowScopeAvailable ? "true" : "false" : "not checked";
      const generatedAt = data?.generatedAt ? formatLocalDateTime(data.generatedAt) : "대기 중";
      const mode = data?.mode || "not loaded";
      const repo = data?.repo || "OWNER/REPO";
      const nextCommand = data?.nextVerificationCommand || "node scripts/plan-publish-dispatch.mjs --live --repo OWNER/REPO";
      const workflowScopeRefreshCommand = data?.workflowScopeRefreshCommand || "gh auth refresh -h github.com -s workflow";
      const workflowScopeRefreshClipboardCommand = data?.workflowScopeRefreshClipboardCommand || data?.workflowScopeRefreshHandoff?.clipboardCommand || `${workflowScopeRefreshCommand} --clipboard`;
      const workflowScopeRecheckCommand = data?.workflowScopeRecheckCommand || nextCommand;
      const workflowScopeApprovalHandoff = loaded && data.workflowScopeApprovalHandoff && typeof data.workflowScopeApprovalHandoff === "object"
        ? data.workflowScopeApprovalHandoff
        : loaded && data.workflowScopeRefreshHandoff?.approval && typeof data.workflowScopeRefreshHandoff.approval === "object"
          ? data.workflowScopeRefreshHandoff.approval
          : {};
      const workflowScopeApprovalStatus = workflowScopeApprovalHandoff.status || (workflowScopeInstallBlocked ? "approval_required" : "not_required");
      const workflowScopeApprovalUrl = workflowScopeApprovalHandoff.approvalUrl || "https://github.com/login/device";
      const workflowScopeApprovalPrompt = workflowScopeApprovalHandoff.expectedPrompt || "First copy your one-time code, then open https://github.com/login/device to approve the workflow scope.";
      const workflowScopeInteractiveApprovalRequired = workflowScopeApprovalHandoff.interactiveApprovalRequired ?? workflowScopeInstallBlocked;
      const workflowScopeTerminalWaitRequired = workflowScopeApprovalHandoff.terminalWaitRequired ?? workflowScopeInstallBlocked;
      const workflowScopeIncompleteApprovalSignal = workflowScopeApprovalHandoff.incompleteApprovalSignal || "Token scopes still omit workflow after the refresh attempt, or the gh auth refresh session was cancelled or timed out.";
      const workflowScopeDeviceCodePolicy = workflowScopeApprovalHandoff.sensitiveValuePolicy || "Do not store, log, or paste the one-time device code into project files.";
      const workflowScopeApprovalFallback = workflowScopeApprovalHandoff.fallback || "Use each workflow row's installAction to choose the GitHub edit-file or new-file page, and skip rows already verified on the default branch.";
      const workflowScopeApprovalStopCondition = workflowScopeApprovalHandoff.stopCondition || "Do not run install, dispatch, publish copy, or archive proof until workflow scope or GitHub UI installation is verified.";
      const workflowScopePacketText = [
        "# JooPark Workflow Scope Refresh Packet",
        "",
        `Status: ${workflowScopeMissing ? "action required - workflow scope missing" : "workflow scope present"}`,
        `Repo: ${repo}`,
        `workflowScope.scopes: ${workflowScopeList}`,
        `workflowScopeAvailable: ${workflowScopeChecked ? workflowScopeAvailable ? "true" : "false" : "not checked"}`,
        `workflowScopeInstallBlocked: ${workflowScopeInstallBlocked ? "true" : "false"}`,
        `Missing scope: ${workflowScopeMissing || "none"}`,
        `Scope source: ${workflowScopeSource}`,
        "",
        "Safe next commands:",
        `1. ${workflowScopeRefreshCommand}`,
        `2. ${workflowScopeRefreshClipboardCommand}`,
        `3. ${workflowScopeRecheckCommand}`,
        "",
        "Device-code approval handoff:",
        `Status: ${workflowScopeApprovalStatus}`,
        `Approval URL: ${workflowScopeApprovalUrl}`,
        `Expected prompt: ${workflowScopeApprovalPrompt}`,
        `Interactive approval required: ${workflowScopeInteractiveApprovalRequired ? "true" : "false"}`,
        `Terminal wait required: ${workflowScopeTerminalWaitRequired ? "true" : "false"}`,
        `Incomplete approval signal: ${workflowScopeIncompleteApprovalSignal}`,
        `Sensitive value policy: ${workflowScopeDeviceCodePolicy}`,
        `Stop condition: ${workflowScopeApprovalStopCondition}`,
        "",
        "GitHub UI fallback:",
        `1. ${workflowScopeApprovalFallback}`,
        "2. Commit only changed workflow files to the repository default branch.",
        "3. Rerun the recheck command until remoteWorkflowVisibilityReady and allDispatchReady are true.",
        "",
        "Dispatch guard:",
        "Do not run gh workflow run until remoteWorkflowFilesReady: true, dispatchReady: true, driftDispatchReady: true, and allDispatchReady: true.",
      ].join("\n");
      const defaultBranchHandoff = loaded && data.workflowDefaultBranchHandoff && typeof data.workflowDefaultBranchHandoff === "object"
        ? data.workflowDefaultBranchHandoff
        : null;
      const stateLabel = allReady ? "dispatch ready" : loaded && repoReady ? "blocked" : "repo check required";
      return html`
        <div class="publish-dispatch-plan" data-system-publish-dispatch-plan data-publish-dispatch-source="${source?.source || "data/publish-dispatch-plan.json"}" data-publish-dispatch-loaded="${loaded ? "true" : "false"}" data-publish-dispatch-ready="${dispatchReady ? "true" : "false"}" data-publish-dispatch-drift-ready="${driftReady ? "true" : "false"}" data-publish-dispatch-all-ready="${allReady ? "true" : "false"}" data-publish-dispatch-repo-ready="${repoReady ? "true" : "false"}" data-publish-dispatch-local-targets-ready="${localTargetsReady ? "true" : "false"}" data-publish-dispatch-local-target-parity-ready="${localTargetParityReady ? "true" : "false"}" data-publish-dispatch-remote-visible="${remoteVisible ? "true" : "false"}" data-publish-dispatch-workflow-scope-checked="${workflowScopeChecked ? "true" : "false"}" data-publish-dispatch-workflow-scope-available="${workflowScopeAvailable ? "true" : "false"}" data-publish-dispatch-workflow-scope-install-blocked="${workflowScopeInstallBlocked ? "true" : "false"}" data-publish-dispatch-workflow-scope-scopes="${workflowScopeList}" data-publish-dispatch-workflow-scope-missing="${workflowScopeMissing}" data-publish-dispatch-workflow-scope-source="${workflowScopeSource}" data-publish-dispatch-workflow-scope-refresh-command="${workflowScopeRefreshCommand}" data-publish-dispatch-workflow-scope-refresh-clipboard-command="${workflowScopeRefreshClipboardCommand}" data-publish-dispatch-workflow-scope-recheck-command="${workflowScopeRecheckCommand}" data-publish-dispatch-workflow-scope-approval-status="${workflowScopeApprovalStatus}" data-publish-dispatch-workflow-scope-approval-url="${workflowScopeApprovalUrl}" data-publish-dispatch-workflow-scope-interactive-approval-required="${workflowScopeInteractiveApprovalRequired ? "true" : "false"}" data-publish-dispatch-workflow-scope-terminal-wait-required="${workflowScopeTerminalWaitRequired ? "true" : "false"}" data-publish-dispatch-default-branch-handoff="${defaultBranchHandoff ? "true" : "false"}" data-publish-dispatch-plan-count="${plans.length}" data-publish-dispatch-repo="${repo}" data-publish-dispatch-next-command="${nextCommand}" data-publish-dispatch-suggested-dispatch-count="${suggestedDispatchCommandCount}" data-publish-dispatch-withheld-dispatch-count="${withheldDispatchCommandCount}" data-publish-dispatch-dispatch-suggestion-status="${dispatchSuggestionStatus}" data-publish-dispatch-suggested-commands-safe="${suggestedCommands.some((command) => command.includes("gh workflow run --repo")) && !allReady ? "false" : "true"}">
          <div class="publish-evidence-head">
            <strong>Publish dispatch plan</strong>
            <span class="publish-state" data-publish-dispatch-state-label>${stateLabel}</span>
          </div>
          <p class="settings-note">저장된 live plan은 GitHub Actions 목록에서 workflow가 보이는지 확인한 결과와 repository-root workflow 파일 존재 여부를 함께 보여줍니다. <code>allDispatchReady: true</code>가 되기 전에는 아래 <code>gh workflow run</code> 명령을 실행하지 않습니다.</p>
          <dl class="storage-grid">
            <div><dt>source</dt><dd>${source?.source || "data/publish-dispatch-plan.json"}</dd></div>
            <div><dt>mode</dt><dd>${mode}</dd></div>
            <div><dt>generated</dt><dd>${generatedAt}</dd></div>
            <div><dt>repo</dt><dd>${repo}</dd></div>
            <div><dt>suggestedRepo</dt><dd>${data?.suggestedRepo || "not available"}</dd></div>
            <div><dt>repoEvidenceReady</dt><dd>${repoReady ? "true" : "false"}</dd></div>
            <div><dt>localWorkflowTargetsReady</dt><dd>${localTargetsReady ? "true" : "false"}</dd></div>
            <div><dt>localTargetParityReady</dt><dd>${localTargetParityReady ? "true" : "false"}</dd></div>
            <div><dt>remoteWorkflowVisibilityReady</dt><dd>${remoteVisible ? "true" : "false"}</dd></div>
            <div><dt>workflowScopeAvailable</dt><dd>${workflowScopeChecked ? workflowScopeAvailable ? "true" : "false" : "not checked"}</dd></div>
            <div><dt>workflowScopeInstallBlocked</dt><dd>${workflowScopeInstallBlocked ? "true" : "false"}</dd></div>
            <div><dt>workflowScope.scopes</dt><dd>${workflowScopeList}</dd></div>
            <div><dt>workflowScope.missing</dt><dd>${workflowScopeMissing || "none"}</dd></div>
            <div><dt>workflowScope.source</dt><dd>${workflowScopeSource}</dd></div>
            <div><dt>workflowScopeRefreshCommand</dt><dd><code>${workflowScopeRefreshCommand}</code></dd></div>
            <div><dt>workflowScopeRefreshClipboardCommand</dt><dd><code>${workflowScopeRefreshClipboardCommand}</code></dd></div>
            <div><dt>workflowScopeRecheckCommand</dt><dd><code>${workflowScopeRecheckCommand}</code></dd></div>
            <div><dt>workflowScopeApproval</dt><dd>${workflowScopeApprovalStatus}</dd></div>
            <div><dt>approvalUrl</dt><dd><code>${workflowScopeApprovalUrl}</code></dd></div>
            <div><dt>interactiveApprovalRequired</dt><dd>${workflowScopeInteractiveApprovalRequired ? "true" : "false"}</dd></div>
            <div><dt>terminalWaitRequired</dt><dd>${workflowScopeTerminalWaitRequired ? "true" : "false"}</dd></div>
            <div><dt>workflowDefaultBranchHandoff</dt><dd>${defaultBranchHandoff ? "true" : "false"}</dd></div>
            <div><dt>workflowListCommand</dt><dd><code>${data?.workflowListCommand || "gh workflow list --repo OWNER/REPO --all --json name,path,state,id"}</code></dd></div>
            <div><dt>dispatchReady</dt><dd>${dispatchReady ? "true" : "false"}</dd></div>
            <div><dt>driftDispatchReady</dt><dd>${driftReady ? "true" : "false"}</dd></div>
            <div><dt>allDispatchReady</dt><dd>${allReady ? "true" : "false"}</dd></div>
            <div><dt>suggestedDispatchCommandCount</dt><dd>${suggestedDispatchCommandCount}</dd></div>
            <div><dt>withheldDispatchCommandCount</dt><dd>${withheldDispatchCommandCount}</dd></div>
            <div><dt>workflowPlans</dt><dd>${plans.length}</dd></div>
            <div><dt>blockers</dt><dd>${blockers.length}</dd></div>
          </dl>
          ${source?.error ? raw(html`<p class="settings-note storage-error">publish dispatch plan load error: ${source.error}</p>`) : ""}
          ${workflowScopeChecked ? raw(html`
            <div class="launch-execution-copy" data-publish-dispatch-auth-preflight data-publish-dispatch-auth-preflight-available="${workflowScopeAvailable ? "true" : "false"}" data-publish-dispatch-auth-preflight-install-blocked="${workflowScopeInstallBlocked ? "true" : "false"}" data-publish-dispatch-auth-preflight-scope-count="${workflowScopes.length}" data-publish-dispatch-auth-preflight-source="${workflowScopeSource}">
              <div>
                <span>Auth preflight</span>
                <strong>${workflowScopeStatus}</strong>
              </div>
              <p>auth preflight only; this does not install workflow files, run dispatch, or capture launch proof.</p>
              <code>workflowScopeAvailable=${workflowScopeAvailabilityLabel}</code>
              <code>workflowScopeInstallBlocked=${workflowScopeInstallBlocked ? "true" : "false"}</code>
              <code>workflowScope.scopes=${workflowScopeList}</code>
              <code>Missing scope=${workflowScopeMissing || "none"}</code>
              <code>workflowScopeRefreshCommand=${workflowScopeRefreshCommand}</code>
              <code>workflowScopeRefreshClipboardCommand=${workflowScopeRefreshClipboardCommand}</code>
              <code>workflowScopeRecheckCommand=${workflowScopeRecheckCommand}</code>
              <code>workflowScopeApproval=${workflowScopeApprovalStatus}</code>
              <code>approvalUrl=${workflowScopeApprovalUrl}</code>
              <code>interactiveApprovalRequired=${workflowScopeInteractiveApprovalRequired ? "true" : "false"}</code>
              <code>terminalWaitRequired=${workflowScopeTerminalWaitRequired ? "true" : "false"}</code>
              <code>${workflowScopeIncompleteApprovalSignal}</code>
              <code>${workflowScopeDeviceCodePolicy}</code>
              <small>Use GitHub UI workflow install plan if workflow scope cannot be granted; keep dispatch withheld until allDispatchReady: true.</small>
            </div>
          `) : ""}
          ${workflowScopeChecked ? raw(html`
            <div class="launch-execution-copy" data-publish-dispatch-workflow-scope-evidence data-publish-dispatch-workflow-scope-packet data-publish-dispatch-workflow-scope-packet-ready="${workflowScopeChecked ? "true" : "false"}">
              <div>
                <span>copy-ready scope fix</span>
                <strong>Workflow scope refresh packet</strong>
              </div>
              <span>workflow scope evidence</span>
              <code>workflowScope.scopes: ${workflowScopeList}</code>
              <code>workflowScopeInstallBlocked: ${workflowScopeInstallBlocked ? "true" : "false"}</code>
              ${workflowScopeMissing ? raw(html`
                <code>workflowScopeRefreshCommand: ${workflowScopeRefreshCommand}</code>
                <code>workflowScopeRefreshClipboardCommand: ${workflowScopeRefreshClipboardCommand}</code>
                <code>workflowScopeRecheckCommand: ${workflowScopeRecheckCommand}</code>
                <code>Approval URL: ${workflowScopeApprovalUrl}</code>
                <code>Interactive approval required: ${workflowScopeInteractiveApprovalRequired ? "true" : "false"}</code>
                <code>Terminal wait required: ${workflowScopeTerminalWaitRequired ? "true" : "false"}</code>
                <code>Incomplete approval signal: ${workflowScopeIncompleteApprovalSignal}</code>
                <code>${workflowScopeDeviceCodePolicy}</code>
              `) : ""}
              <p>${workflowScopeMissing ? "`workflow` scope is missing; run the refresh command, then rerun the recheck command, or install workflow files through GitHub UI." : "`workflow` scope is present; still wait for remote workflow visibility and allDispatchReady before dispatch."}</p>
              <pre data-publish-dispatch-workflow-scope-packet-text>${workflowScopePacketText}</pre>
              <button type="button" class="portfolio-export-download portfolio-export-copy" data-action="copy-publish-workflow-scope-packet" data-publish-dispatch-workflow-scope-packet-copy>scope packet 복사</button>
              <small class="portfolio-export-status" data-publish-dispatch-workflow-scope-packet-copy-status aria-live="polite"></small>
            </div>
          `) : ""}
          <div class="publish-dispatch-cards">
            ${plans.map((plan) => raw(html`
              <article class="publish-dispatch-card" data-publish-dispatch-workflow-card data-publish-dispatch-workflow-key="${plan.key}" data-publish-dispatch-workflow-path="${plan.workflowPath || ""}" data-publish-dispatch-workflow-ready="${plan.dispatchReady ? "true" : "false"}" data-publish-dispatch-workflow-target-exists="${plan.targetExists ? "true" : "false"}" data-publish-dispatch-workflow-target-matches-template="${plan.targetMatchesTemplate ? "true" : "false"}">
                <div>
                  <span>${plan.key}</span>
                  <strong>${plan.workflowName || plan.workflowFile || plan.key}</strong>
                  <p>${plan.workflowPath || plan.workflowFile || ""}</p>
                </div>
                <dl>
                  <div><dt>workflowFile</dt><dd><code>${plan.workflowFile || ""}</code></dd></div>
                  <div><dt>targetExists</dt><dd>${plan.targetExists ? "true" : "false"}</dd></div>
                  <div><dt>targetMatchesTemplate</dt><dd>${plan.targetMatchesTemplate ? "true" : "false"}</dd></div>
                  <div><dt>workflowVisible</dt><dd>${plan.checks?.workflowVisible === true ? "true" : plan.checks?.workflowVisible === false ? "false" : "not checked"}</dd></div>
                  <div><dt>dispatchReady</dt><dd>${plan.dispatchReady ? "true" : "false"}</dd></div>
                  <div><dt>dispatchCommand</dt><dd><code>${plan.dispatchCommand || ""}</code></dd></div>
                  <div><dt>scopeCheckCommand</dt><dd><code>${plan.scopeCheckCommand || ""}</code></dd></div>
                </dl>
                ${Array.isArray(plan.blockers) && plan.blockers.length ? raw(html`
                  <ul class="publish-dispatch-blockers">
                    ${plan.blockers.map((blocker) => raw(html`<li>${blocker}</li>`))}
                  </ul>
                `) : ""}
              </article>
            `))}
          </div>
          <div class="publish-dispatch-next" data-publish-dispatch-next>
            <span>nextVerificationCommand</span>
            <code>${nextCommand}</code>
          </div>
          ${defaultBranchHandoff ? raw(html`
            <div class="publish-dispatch-next" data-publish-dispatch-default-branch-handoff>
              <span>workflowDefaultBranchHandoff</span>
              <code>${defaultBranchHandoff.gitAddCommand || ""}</code>
              <code>${defaultBranchHandoff.gitCommitCommand || ""}</code>
              <code>${defaultBranchHandoff.workflowScopeRefreshCommand || workflowScopeRefreshCommand}</code>
              <code>${defaultBranchHandoff.workflowScopeRecheckCommand || workflowScopeRecheckCommand}</code>
              <code>${defaultBranchHandoff.remoteVisibilityVerificationCommand || nextCommand}</code>
              <p>${defaultBranchHandoff.requirement || "Land the staged workflow files on the repository default branch before dispatch."}</p>
            </div>
          `) : ""}
          ${nextActions.length ? raw(html`
            <ul class="publish-dispatch-blockers" data-publish-dispatch-next-actions>
              ${nextActions.map((action) => raw(html`<li>${action}</li>`))}
            </ul>
          `) : ""}
          ${suggestedCommands.length ? raw(html`
            <div class="publish-dispatch-next" data-publish-dispatch-suggested-commands>
              <span>suggestedCommands</span>
              ${suggestedCommands.map((command) => raw(html`<code>${command}</code>`))}
            </div>
          `) : ""}
          <div class="publish-dispatch-next" data-publish-dispatch-dispatch-command-guard>
            <span>suggestedDispatchCommands</span>
            ${suggestedDispatchCommands.length
              ? raw(html`<p>ready dispatch commands; run only repo-scoped suggestedDispatchCommands after allDispatchReady=true.</p>${suggestedDispatchCommands.map((command) => html`<code>${command}</code>`).join("")}`)
              : raw(html`<code>withheld until allDispatchReady: true</code>`)}
          </div>
          <div class="publish-dispatch-next" data-publish-dispatch-withheld-dispatch-commands data-publish-dispatch-withheld-dispatch-count="${withheldDispatchCommandCount}">
            <span>withheldDispatchCommands</span>
            ${withheldDispatchCommands.length
              ? raw(withheldDispatchCommands.map((command) => html`<code>${command}</code>`).join(""))
              : raw(html`<code>none</code>`)}
          </div>
        </div>
      `;
    }

    function remoteWorkflowFileCheckHTML(source) {
      const data = source?.data || null;
      const loaded = !!(source?.loaded && data);
      const checks = loaded && Array.isArray(data.checks) ? data.checks : [];
      const blockers = loaded && Array.isArray(data.blockers) ? data.blockers : [];
      const ready = loaded && data.remoteWorkflowFilesReady === true;
      const checked = loaded && data.remoteWorkflowFilesChecked === true;
      const repoReady = loaded && data.repoEvidenceReady === true;
      const installPacket = data?.installPacket || "";
      const workflowScope = data?.workflowScope && typeof data.workflowScope === "object" ? data.workflowScope : {};
      const workflowScopeAvailable = data?.workflowScopeAvailable === true || workflowScope.available === true;
      const workflowScopeInstallBlocked = data?.workflowScopeInstallBlocked === true;
      const workflowScopeList = Array.isArray(workflowScope.scopes) && workflowScope.scopes.length ? workflowScope.scopes.join(", ") : "none";
      const workflowScopeRefreshCommand = data?.workflowScopeRefreshCommand || "gh auth refresh -h github.com -s workflow";
      const workflowScopeRefreshClipboardCommand = data?.workflowScopeRefreshClipboardCommand || data?.workflowScopeApprovalHandoff?.clipboardCommand || `${workflowScopeRefreshCommand} --clipboard`;
      const workflowScopeRecheckCommand = data?.workflowScopeRecheckCommand || data?.nextVerificationCommand || "node scripts/check-remote-workflow-files.mjs --repo OWNER/REPO --write";
      const workflowScopeApprovalHandoff = data?.workflowScopeApprovalHandoff && typeof data.workflowScopeApprovalHandoff === "object" ? data.workflowScopeApprovalHandoff : {};
      const workflowScopeApprovalStatus = workflowScopeApprovalHandoff.status || (workflowScopeInstallBlocked ? "approval_required" : "not_required");
      const workflowScopeApprovalUrl = workflowScopeApprovalHandoff.approvalUrl || "https://github.com/login/device";
      const workflowScopeInteractiveApprovalRequired = workflowScopeApprovalHandoff.interactiveApprovalRequired ?? workflowScopeInstallBlocked;
      const workflowScopeTerminalWaitRequired = workflowScopeApprovalHandoff.terminalWaitRequired ?? workflowScopeInstallBlocked;
      const workflowScopeIncompleteApprovalSignal = workflowScopeApprovalHandoff.incompleteApprovalSignal || "Token scopes still omit workflow after the refresh attempt, or the gh auth refresh session was cancelled or timed out.";
      const workflowScopeApprovalPolicy = workflowScopeApprovalHandoff.sensitiveValuePolicy || "Do not store, log, or paste the one-time device code into project files.";
      const workflowScopeApprovalFallback = workflowScopeApprovalHandoff.fallback || "If browser approval cannot be completed, use each workflow row's installAction to choose the GitHub edit-file or new-file page, and skip rows already verified on the default branch.";
      const workflowScopeApprovalStopCondition = workflowScopeApprovalHandoff.stopCondition || "Do not run install, dispatch, publish copy, or archive proof until workflow scope or GitHub UI installation is verified.";
      const remediationSummary = data?.remediationSummary && typeof data.remediationSummary === "object" ? data.remediationSummary : {};
      const remediationAction = remediationSummary.currentAction || (ready ? "verified_remote_matches_template" : "create_or_update_remote_workflow_file");
      const generatedAt = data?.generatedAt ? formatLocalDateTime(data.generatedAt) : "대기 중";
      const stateLabel = ready ? "remote files ready" : checked ? "action required" : "repo check required";
      return html`
        <div class="publish-dispatch-plan" data-system-remote-workflow-file-check data-remote-workflow-file-source="${source?.source || "data/remote-workflow-file-check.json"}" data-remote-workflow-file-loaded="${loaded ? "true" : "false"}" data-remote-workflow-file-checked="${checked ? "true" : "false"}" data-remote-workflow-file-ready="${ready ? "true" : "false"}" data-remote-workflow-file-repo-ready="${repoReady ? "true" : "false"}" data-remote-workflow-file-check-count="${checks.length}" data-remote-workflow-file-blocker-count="${blockers.length}" data-remote-workflow-file-remediation-action="${remediationAction}" data-remote-workflow-file-remediation-edit-count="${remediationSummary.editCount || 0}" data-remote-workflow-file-remediation-create-count="${remediationSummary.createCount || 0}" data-remote-workflow-file-next-command="${data?.nextVerificationCommand || "node scripts/check-remote-workflow-files.mjs --repo OWNER/REPO --write"}" data-remote-workflow-file-workflow-scope-available="${workflowScopeAvailable ? "true" : "false"}" data-remote-workflow-file-workflow-scope-install-blocked="${workflowScopeInstallBlocked ? "true" : "false"}" data-remote-workflow-file-workflow-scope-approval-status="${workflowScopeApprovalStatus}" data-remote-workflow-file-workflow-scope-approval-url="${workflowScopeApprovalUrl}">
          <div class="publish-evidence-head">
            <strong>Remote workflow file check</strong>
            <span class="publish-state" data-remote-workflow-file-state-label>${stateLabel}</span>
          </div>
          <p class="settings-note">GitHub Contents API로 default branch의 workflow YAML을 읽고, 로컬 검증 템플릿의 SHA-256과 비교합니다. 이 단계는 파일 설치 여부를 확인하고, 그 다음 <code>Publish dispatch plan</code>이 Actions visibility를 확인합니다.</p>
          <dl class="storage-grid">
            <div><dt>source</dt><dd>${source?.source || "data/remote-workflow-file-check.json"}</dd></div>
            <div><dt>generated</dt><dd>${generatedAt}</dd></div>
            <div><dt>repo</dt><dd>${data?.repo || "OWNER/REPO"}</dd></div>
            <div><dt>defaultBranch</dt><dd>${data?.defaultBranch || "main"}</dd></div>
            <div><dt>repoEvidenceReady</dt><dd>${repoReady ? "true" : "false"}</dd></div>
            <div><dt>remoteWorkflowFilesChecked</dt><dd>${checked ? "true" : "false"}</dd></div>
            <div><dt>remoteWorkflowFilesReady</dt><dd>${ready ? "true" : "false"}</dd></div>
            <div><dt>remediationAction</dt><dd>${remediationAction}</dd></div>
            <div><dt>workflowScopeAvailable</dt><dd>${workflowScopeAvailable ? "true" : "false"}</dd></div>
            <div><dt>workflowScopeInstallBlocked</dt><dd>${workflowScopeInstallBlocked ? "true" : "false"}</dd></div>
            <div><dt>blockers</dt><dd>${blockers.length}</dd></div>
          </dl>
          <div class="publish-dispatch-next" data-remote-workflow-file-auth-preflight>
            <span>workflow scope preflight</span>
            <code>workflowScopeAvailable=${workflowScopeAvailable ? "true" : "false"}</code>
            <code>workflowScopeInstallBlocked=${workflowScopeInstallBlocked ? "true" : "false"}</code>
            <code>workflowScope.scopes=${workflowScopeList}</code>
            <code>${workflowScopeRefreshCommand}</code>
            <code>${workflowScopeRefreshClipboardCommand}</code>
            <code>${workflowScopeRecheckCommand}</code>
            <code>approvalUrl=${workflowScopeApprovalUrl}</code>
            <code>interactiveApprovalRequired=${workflowScopeInteractiveApprovalRequired ? "true" : "false"}</code>
            <code>terminalWaitRequired=${workflowScopeTerminalWaitRequired ? "true" : "false"}</code>
            <code>${workflowScopeIncompleteApprovalSignal}</code>
            <small>Device-code approval handoff · ${workflowScopeApprovalStatus} · one-time device code. ${workflowScopeApprovalPolicy}</small>
            <small>${workflowScopeApprovalFallback}</small>
            <small>${workflowScopeApprovalStopCondition}</small>
          </div>
          ${source?.error ? raw(html`<p class="settings-note storage-error">remote workflow file check load error: ${source.error}</p>`) : ""}
          <div class="publish-dispatch-cards">
            ${checks.map((check) => raw(html`
              <article class="publish-dispatch-card" data-remote-workflow-file-card data-remote-workflow-file-key="${check.key}" data-remote-workflow-file-path="${check.path || ""}" data-remote-workflow-file-exists="${check.remoteExists ? "true" : "false"}" data-remote-workflow-file-matches-template="${check.remoteMatchesTemplate ? "true" : "false"}" data-remote-workflow-file-install-action="${check.installAction || check.remediation?.installAction || ""}" data-remote-workflow-file-edit-url="${check.githubEditFileUrl || check.remediation?.githubEditFileUrl || ""}">
                <div>
                  <span>${check.key}</span>
                  <strong>${check.name || check.path}</strong>
                  <p>${check.path || ""}</p>
                </div>
                <dl>
                  <div><dt>templateSha256</dt><dd><code>${check.templateSha256 || "missing"}</code></dd></div>
                  <div><dt>remoteSha256</dt><dd><code>${check.remoteSha256 || "missing"}</code></dd></div>
                  <div><dt>remoteBlobSha</dt><dd><code>${check.remoteBlobSha || check.githubBlobSha || "missing"}</code></dd></div>
                  <div><dt>remoteExists</dt><dd>${check.remoteExists ? "true" : "false"}</dd></div>
                  <div><dt>remoteMatchesTemplate</dt><dd>${check.remoteMatchesTemplate ? "true" : "false"}</dd></div>
                  <div><dt>installAction</dt><dd>${check.installAction || check.remediation?.installAction || "pending"}</dd></div>
                  <div><dt>error</dt><dd>${check.error || "none"}</dd></div>
                  <div><dt>copy</dt><dd><code>${check.templateCopyCommand || ""}</code></dd></div>
                  <div><dt>create</dt><dd>${check.githubNewFileUrl ? raw(html`<a href="${check.githubNewFileUrl}" target="_blank" rel="noopener" data-remote-workflow-file-new-file>githubNewFileUrl</a>`) : "new-file URL 대기"}</dd></div>
                  <div><dt>edit</dt><dd>${check.githubEditFileUrl ? raw(html`<a href="${check.githubEditFileUrl}" target="_blank" rel="noopener" data-remote-workflow-file-edit-file>githubEditFileUrl</a>`) : "edit URL 대기"}</dd></div>
                  <div><dt>command</dt><dd><code>${check.command || ""}</code></dd></div>
                  <div><dt>workflow</dt><dd>${check.workflowUrl ? raw(html`<a href="${check.workflowUrl}" target="_blank" rel="noopener">Actions workflow</a>`) : "workflow URL 대기"}</dd></div>
                </dl>
                ${check.remediation?.nextStep ? raw(html`<p class="settings-note">${check.remediation.nextStep}</p>`) : ""}
                ${Array.isArray(check.blockers) && check.blockers.length ? raw(html`
                  <ul class="publish-dispatch-blockers">
                    ${check.blockers.map((blocker) => raw(html`<li>${blocker}</li>`))}
                  </ul>
                `) : ""}
              </article>
            `))}
          </div>
          ${blockers.length ? raw(html`
            <ul class="publish-dispatch-blockers" data-remote-workflow-file-blockers>
              ${blockers.map((blocker) => raw(html`<li>${blocker}</li>`))}
            </ul>
          `) : ""}
          <div class="publish-dispatch-next" data-remote-workflow-file-next>
            <span>nextVerificationCommand</span>
            <code>${data?.nextVerificationCommand || "node scripts/check-remote-workflow-files.mjs --repo OWNER/REPO --write"}</code>
            <code>${data?.dispatchPlanCommand || "node scripts/plan-publish-dispatch.mjs --live --repo OWNER/REPO --write"}</code>
          </div>
          <div class="launch-execution-copy" data-remote-workflow-install-packet data-remote-workflow-install-packet-ready="${installPacket ? "true" : "false"}">
            <div>
              <span>copy-ready installer</span>
              <strong>Remote workflow install packet</strong>
            </div>
            <pre data-remote-workflow-install-packet-text>${installPacket || "remote workflow install packet 대기 중"}</pre>
            <button type="button" class="portfolio-export-download portfolio-export-copy" data-action="copy-remote-workflow-install-packet" data-remote-workflow-install-packet-copy>install packet 복사</button>
            <small class="portfolio-export-status" data-remote-workflow-install-packet-copy-status aria-live="polite"></small>
          </div>
        </div>
      `;
    }

    function publishWorkflowRunLink(evidence, key, label) {
      const run = Array.isArray(evidence?.workflowRuns)
        ? evidence.workflowRuns.find((item) => item.key === key)
        : null;
      const latestRun = run?.latestRun || null;
      if (latestRun?.url) {
        return html`<a data-publish-evidence-run="${key}" href="${latestRun.url}" target="_blank" rel="noopener">${label} · ${latestRun.status || "unknown"} / ${latestRun.conclusion || "unknown"}</a>`;
      }
      const status = latestRun ? `${latestRun.status || "unknown"} / ${latestRun.conclusion || "unknown"}` : "run 대기";
      return html`<span data-publish-evidence-run="${key}">${label} · ${status}</span>`;
    }

    function launchExecutionPacketHTML(source) {
      const data = source?.data || null;
      const loaded = !!(source?.loaded && data);
      const stages = loaded && Array.isArray(data.stages) ? data.stages : [];
      const blockers = loaded && Array.isArray(data.blockers) ? data.blockers : [];
      const comparisons = loaded && Array.isArray(data.externalComparison) ? data.externalComparison : [];
      const packet = data?.packet || "";
      const currentAction = data?.currentAction || null;
      const operatorOnePage = data?.operatorOnePageHandoff && typeof data.operatorOnePageHandoff === "object" ? data.operatorOnePageHandoff : {};
      const operatorOnePageText = operatorOnePage.text || "";
      const stageTransition = data?.stageTransitionPreview && typeof data.stageTransitionPreview === "object" ? data.stageTransitionPreview : {};
      const blockerResolution = data?.blockerResolutionChecklist && typeof data.blockerResolutionChecklist === "object" ? data.blockerResolutionChecklist : {};
      const blockerResolutionItems = Array.isArray(blockerResolution.items) ? blockerResolution.items : [];
      const blockerResolutionItemCount = finiteNumberOr(blockerResolution.itemCount, blockerResolutionItems.length);
      const blockerResolutionPassCount = finiteNumberOr(blockerResolution.passCount, 0);
      const blockerResolutionActionRequiredCount = finiteNumberOr(blockerResolution.actionRequiredCount, 0);
      const blockerResolutionDeferredCount = finiteNumberOr(blockerResolution.deferredCount, 0);
      const blockerResolutionProofCommandCount = finiteNumberOr(blockerResolution.proofCommandCount, 0);
      const installMatrix = data?.workflowInstallVerificationMatrix && typeof data.workflowInstallVerificationMatrix === "object" ? data.workflowInstallVerificationMatrix : {};
      const installMatrixRows = Array.isArray(installMatrix.matrixRows) ? installMatrix.matrixRows : [];
      const installMatrixSignals = Array.isArray(installMatrix.signalChecks) ? installMatrix.signalChecks : [];
      const installMatrixCommands = Array.isArray(installMatrixRows[0]?.verificationCommands) ? installMatrixRows[0].verificationCommands : [];
      const installMatrixPathCount = finiteNumberOr(installMatrix.installPathCount, installMatrixRows.length);
      const installMatrixSignalCount = finiteNumberOr(installMatrix.requiredSignalCount, installMatrixSignals.length);
      const installMatrixVerificationCommandCount = finiteNumberOr(installMatrix.verificationCommandCount, installMatrixCommands.length);
      const remoteFileLedger = data?.remoteWorkflowFileAcceptanceLedger && typeof data.remoteWorkflowFileAcceptanceLedger === "object" ? data.remoteWorkflowFileAcceptanceLedger : {};
      const remoteFileLedgerItems = Array.isArray(remoteFileLedger.files) ? remoteFileLedger.files : [];
      const remoteFileLedgerFileCount = finiteNumberOr(remoteFileLedger.fileCount, remoteFileLedgerItems.length);
      const remoteFileLedgerReadyCount = finiteNumberOr(remoteFileLedger.readyCount, 0);
      const remoteFileLedgerMissingCount = finiteNumberOr(remoteFileLedger.missingCount, 0);
      const remoteFileLedgerMismatchCount = finiteNumberOr(remoteFileLedger.mismatchCount, 0);
      const proofLedger = data?.launchProofAcceptanceLedger && typeof data.launchProofAcceptanceLedger === "object" ? data.launchProofAcceptanceLedger : {};
      const proofLedgerItems = Array.isArray(proofLedger.requiredProofs) ? proofLedger.requiredProofs : [];
      const postInstallIntake = data?.postInstallEvidenceIntake && typeof data.postInstallEvidenceIntake === "object" ? data.postInstallEvidenceIntake : {};
      const postInstallIntakeFields = Array.isArray(postInstallIntake.fields) ? postInstallIntake.fields : [];
      const postInstallIntakeCommands = Array.isArray(postInstallIntake.commands) ? postInstallIntake.commands : [];
      const postInstallIntakeSignals = Array.isArray(postInstallIntake.expectedSignals) ? postInstallIntake.expectedSignals : [];
      const postInstallIntakeSequence = Array.isArray(postInstallIntake.verificationSequence) ? postInstallIntake.verificationSequence : [];
      const postInstallQuickProofSteps = Array.isArray(postInstallIntake.quickProofSteps) ? postInstallIntake.quickProofSteps : [];
      const postInstallQuickProofFieldMappings = Array.isArray(postInstallIntake.quickProofFieldMappings) ? postInstallIntake.quickProofFieldMappings : [];
      const postInstallIntakeFieldCount = finiteNumberOr(postInstallIntake.fieldCount, postInstallIntakeFields.length);
      const postInstallIntakeCompletedCount = finiteNumberOr(postInstallIntake.completedFieldCount, 0);
      const postInstallIntakeCommandCount = finiteNumberOr(postInstallIntake.commandCount, postInstallIntakeCommands.length);
      const postInstallIntakeSignalCount = finiteNumberOr(postInstallIntake.signalCount, postInstallIntakeSignals.length);
      const postInstallIntakeFieldCoverage = finiteNumberOr(postInstallIntake.fieldCoverage, 0);
      const postInstallIntakeSequenceCount = finiteNumberOr(postInstallIntake.verificationSequenceCount, postInstallIntakeSequence.length);
      const postInstallQuickProofStepCount = finiteNumberOr(postInstallIntake.quickProofStepCount, postInstallQuickProofSteps.length);
      const postInstallQuickProofCoverage = finiteNumberOr(postInstallIntake.quickProofCoverage, 0);
      const postInstallQuickProofFieldMappingCoverage = finiteNumberOr(postInstallIntake.quickProofFieldMappingCoverage, 0);
      const postInstallQuickProofMappedFieldCount = finiteNumberOr(postInstallIntake.quickProofMappedFieldCount, postInstallQuickProofFieldMappings.length);
      const postInstallQuickProofCompletedMappedFieldCount = finiteNumberOr(postInstallIntake.quickProofCompletedMappedFieldCount, 0);
      const postInstallIntakePendingFieldCount = finiteNumberOr(
        postInstallIntake.pendingFieldCount,
        Math.max(postInstallIntakeFieldCount - postInstallIntakeCompletedCount, 0),
      );
      const postInstallDispatchGuard = postInstallIntake.dispatchGuard || installMatrix.dispatchGuard || "Do not run gh workflow run until every post-install evidence field has been filled, remoteWorkflowFilesReady=true, remoteWorkflowVisibilityReady=true, dispatchReady=true, driftDispatchReady=true, allDispatchReady=true, and verify-launch-handoff reports safeToDispatch=true.";
      const postInstallStopCondition = postInstallIntake.stopCondition || "Stop condition: do not run gh workflow run, archive proof, or claim launch until all six post-install evidence fields are filled and verify-launch-handoff reports safeToDispatch=true.";
      const authPreflight = data?.authPreflight || currentAction?.authPreflight || {};
      const postAuthCheckpoint = data?.postAuthCheckpoint || currentAction?.postAuthCheckpoint || {};
      const currentAcceptance = Array.isArray(currentAction?.acceptanceChecklist) ? currentAction.acceptanceChecklist : [];
      const currentVerifyCommands = Array.isArray(currentAction?.verifyCommands) ? currentAction.verifyCommands : [];
      const currentInstallPaths = Array.isArray(currentAction?.installPaths) ? currentAction.installPaths : [];
      const defaultBranchProof = currentAction?.defaultBranchRequirementProof && typeof currentAction.defaultBranchRequirementProof === "object" ? currentAction.defaultBranchRequirementProof : {};
      const defaultBranchProofRequirements = Array.isArray(defaultBranchProof.requirements) ? defaultBranchProof.requirements : [];
      const defaultBranchProofFiles = Array.isArray(defaultBranchProof.workflowFiles) ? defaultBranchProof.workflowFiles : [];
      const defaultPostAuthExpectedSignals = ["Token scopes include workflow", "workflowScopeAvailable=true", "workflowScopeInstallBlocked=false", "safeToDispatch=true before gh workflow run"];
      const defaultPostAuthBlockedSignals = ["workflowScopeInstallBlocked=true", "remoteWorkflowFilesReady=false", "remoteWorkflowVisibilityReady=false", "allDispatchReady=false"];
      const postAuthExpectedSignals = Array.isArray(postAuthCheckpoint.expectedSignals) && postAuthCheckpoint.expectedSignals.length ? postAuthCheckpoint.expectedSignals : defaultPostAuthExpectedSignals;
      const postAuthBlockedSignals = Array.isArray(postAuthCheckpoint.blockedSignals) && postAuthCheckpoint.blockedSignals.length ? postAuthCheckpoint.blockedSignals : defaultPostAuthBlockedSignals;
      const postAuthRecheckSequence = Array.isArray(postAuthCheckpoint.recheckSequence) ? postAuthCheckpoint.recheckSequence : [];
      const postAuthSourceArtifacts = Array.isArray(postAuthCheckpoint.sourceArtifacts) ? postAuthCheckpoint.sourceArtifacts : [];
      const postAuthCommandCount = finiteNumberOr(postAuthCheckpoint.commandCount, 0);
      const postAuthRecheckSequenceCount = finiteNumberOr(postAuthCheckpoint.recheckSequenceCount, postAuthRecheckSequence.length);
      const postAuthSourceArtifactCount = finiteNumberOr(postAuthCheckpoint.sourceArtifactCount, postAuthSourceArtifacts.length);
      const postAuthExpectedSignalCount = finiteNumberOr(postAuthCheckpoint.expectedSignalCount, postAuthExpectedSignals.length);
      const postAuthBlockedSignalCount = finiteNumberOr(postAuthCheckpoint.blockedSignalCount, postAuthBlockedSignals.length);
      const postAuthExpectedSignalDisplay = postAuthExpectedSignalCount > 0 ? postAuthExpectedSignals.slice(0, postAuthExpectedSignalCount) : [];
      const postAuthBlockedSignalDisplay = postAuthBlockedSignalCount > 0 ? postAuthBlockedSignals.slice(0, postAuthBlockedSignalCount) : [];
      const postAuthRecheckSequenceDisplay = postAuthRecheckSequenceCount > 0 ? postAuthRecheckSequence.slice(0, postAuthRecheckSequenceCount) : [];
      const postAuthSourceArtifactDisplay = postAuthSourceArtifactCount > 0 ? postAuthSourceArtifacts.slice(0, postAuthSourceArtifactCount) : [];
      const readyToDispatch = !!data?.readyToDispatch;
      const launchProofReady = !!data?.launchProofReady;
      const externalReady = !!data?.readyForExternalClaim;
      const generatedAt = data?.generatedAt ? formatLocalDateTime(data.generatedAt) : "대기 중";
      const stateLabel = externalReady ? "launch ready" : readyToDispatch ? "dispatch ready" : "execution blocked";
      const authScopes = Array.isArray(authPreflight.scopes) ? authPreflight.scopes : [];
      const authMissingScopes = Array.isArray(authPreflight.missingScopes) ? authPreflight.missingScopes : [];
      const authScopeList = authPreflight.scopeList || (authScopes.length ? authScopes.join(", ") : authPreflight.checked ? "none reported" : "not checked");
      const authMissingList = authPreflight.missingScopeList || (authMissingScopes.length ? authMissingScopes.join(", ") : "none");
      const authApprovalStatus = authPreflight.approvalStatus || (authPreflight.workflowScopeInstallBlocked ? "approval_required" : "not_required");
      const authApprovalUrl = authPreflight.approvalUrl || "https://github.com/login/device";
      const authApprovalPrompt = authPreflight.approvalExpectedPrompt || "First copy your one-time code, then open https://github.com/login/device to approve the workflow scope.";
      const authRefreshClipboardCommand = authPreflight.refreshClipboardCommand || `${authPreflight.refreshCommand || "gh auth refresh -h github.com -s workflow"} --clipboard`;
      const authInteractiveApprovalRequired = authPreflight.approvalInteractiveRequired ?? authPreflight.workflowScopeInstallBlocked;
      const authTerminalWaitRequired = authPreflight.approvalTerminalWaitRequired ?? authPreflight.workflowScopeInstallBlocked;
      const authIncompleteApprovalSignal = authPreflight.approvalIncompleteSignal || "Token scopes still omit workflow after the refresh attempt, or the gh auth refresh session was cancelled or timed out.";
      const authDeviceCodePolicy = authPreflight.approvalSensitiveValuePolicy || "Do not store, log, or paste the one-time device code into project files.";
      const authApprovalStopCondition = authPreflight.approvalStopCondition || "Do not run install, dispatch, publish copy, or archive proof until workflow scope or GitHub UI installation is verified.";
      const currentStageKey = stageTransition.currentStageKey || currentAction?.stageKey || stages.find((stage) => stage.status === "action_required")?.key || "";
      const pendingAcceptance = currentAcceptance.filter((item) => item.status !== "pass");
      const passedAcceptance = currentAcceptance.filter((item) => item.status === "pass");
      const visibilityStage = stages.find((stage) => stage.key === "verify_visibility") || {};
      const dispatchGateStage = stages.find((stage) => stage.key === "dispatch_gate") || {};
      const captureStage = stages.find((stage) => stage.key === "capture_launch_proof") || {};
      const transitionReady = stageTransition.readyToAdvance === true || readyToDispatch;
      const transitionNextStageKey = stageTransition.nextStageKey || (transitionReady ? (captureStage.key || "capture_launch_proof") : (visibilityStage.key || "verify_visibility"));
      const transitionNextStageLabel = stageTransition.nextStageLabel || (transitionReady ? (captureStage.label || "Capture launch proof") : (visibilityStage.label || "Verify workflow visibility"));
      const transitionGateCommand = stageTransition.gateCommand || postAuthCheckpoint.verifyCommand || currentVerifyCommands.find((command) => command.includes("verify-launch-handoff")) || "node scripts/verify-launch-handoff.mjs --repo OWNER/REPO --write --markdown";
      const transitionPendingCount = Number.isFinite(stageTransition.pendingAcceptanceCount) ? stageTransition.pendingAcceptanceCount : pendingAcceptance.length;
      const transitionPassCount = Number.isFinite(stageTransition.passAcceptanceCount) ? stageTransition.passAcceptanceCount : passedAcceptance.length;
      const transitionWithheldCount = Number.isFinite(stageTransition.withheldDispatchCommandCount) ? stageTransition.withheldDispatchCommandCount : currentAction?.withheldCommandCount || 0;
      const transitionPreviewSteps = Array.isArray(stageTransition.steps) && stageTransition.steps.length ? stageTransition.steps : [
        {
          key: "complete-current-stage",
          label: currentAction?.label || "Complete current stage",
          status: currentAction?.status || "action_required",
          condition: currentAction?.successCondition || "Complete the current launch stage and rerun verification.",
        },
        {
          key: "unlock-next-stage",
          label: transitionNextStageLabel,
          status: readyToDispatch ? "ready_after_dispatch_gate" : "conditional",
          condition: readyToDispatch ? "safeToDispatch=true; capture live publish evidence next." : "remoteWorkflowFilesReady=true and remoteWorkflowVisibilityReady=true before dispatch.",
        },
        {
          key: "keep-dispatch-withheld",
          label: dispatchGateStage.label || "Dispatch only after allDispatchReady",
          status: readyToDispatch ? "ready" : "withheld",
          condition: readyToDispatch ? "Run only suggestedDispatchCommands, then capture launch proof." : "Keep gh workflow run withheld until allDispatchReady=true and safeToDispatch=true.",
        },
      ];
      const proofLedgerRequiredCount = Number.isFinite(Number(proofLedger.requiredProofCount))
        ? Number(proofLedger.requiredProofCount)
        : (proofLedgerItems.length || 0);
      const proofLedgerReadyCount = Number.isFinite(Number(proofLedger.readyProofCount))
        ? Number(proofLedger.readyProofCount)
        : 0;
      const proofLedgerPendingCount = Number.isFinite(Number(proofLedger.pendingProofCount))
        ? Number(proofLedger.pendingProofCount)
        : Math.max(0, proofLedgerRequiredCount - proofLedgerReadyCount);
      return html`
        <div class="launch-execution-packet" data-system-launch-execution-packet data-launch-execution-source="${source?.source || "data/launch-execution-packet.json"}" data-launch-execution-loaded="${loaded ? "true" : "false"}" data-launch-execution-ready-to-dispatch="${readyToDispatch ? "true" : "false"}" data-launch-execution-proof-ready="${launchProofReady ? "true" : "false"}" data-launch-execution-external-ready="${externalReady ? "true" : "false"}" data-launch-execution-stage-count="${stages.length}" data-launch-execution-command-count="${data?.commandCount || 0}" data-launch-execution-comparison-count="${comparisons.length}" data-launch-execution-blocker-count="${blockers.length}" data-launch-execution-auth-preflight-status="${authPreflight.status || ""}" data-launch-execution-auth-preflight-checked="${authPreflight.checked ? "true" : "false"}" data-launch-execution-auth-workflow-scope-available="${authPreflight.workflowScopeAvailable ? "true" : "false"}" data-launch-execution-auth-workflow-scope-install-blocked="${authPreflight.workflowScopeInstallBlocked ? "true" : "false"}" data-launch-execution-auth-scope-count="${authScopes.length}" data-launch-execution-auth-scope-list="${authScopeList}" data-launch-execution-auth-missing-scopes="${authMissingList}" data-launch-execution-auth-refresh-command="${authPreflight.refreshCommand || ""}" data-launch-execution-auth-recheck-command="${authPreflight.recheckCommand || ""}" data-launch-execution-auth-approval-status="${authApprovalStatus}" data-launch-execution-auth-approval-url="${authApprovalUrl}" data-launch-execution-post-auth-checkpoint-status="${postAuthCheckpoint.status || ""}" data-launch-execution-post-auth-checkpoint-command-count="${postAuthCommandCount}" data-launch-execution-post-auth-checkpoint-expected-count="${postAuthExpectedSignalCount}" data-launch-execution-post-auth-checkpoint-blocked-count="${postAuthBlockedSignalCount}" data-launch-execution-post-auth-checkpoint-recheck-count="${postAuthRecheckSequenceCount}" data-launch-execution-post-auth-checkpoint-source-artifact-count="${postAuthSourceArtifactCount}" data-launch-execution-post-auth-checkpoint-dispatch-approval="${postAuthCheckpoint.dispatchApproval ? "true" : "false"}" data-launch-execution-post-auth-checkpoint-verification-only="${postAuthCheckpoint.verificationOnly ? "true" : "false"}" data-launch-execution-post-auth-checkpoint-trigger-command="${postAuthCheckpoint.triggerCommand || ""}" data-launch-execution-post-auth-checkpoint-verify-command="${postAuthCheckpoint.verifyCommand || ""}" data-launch-execution-post-auth-checkpoint-install-command="${postAuthCheckpoint.installCommand || ""}" data-launch-execution-current-action-stage="${currentAction?.stageKey || ""}" data-launch-execution-current-action-status="${currentAction?.status || ""}" data-launch-execution-current-action-command-count="${currentAction?.commandCount || 0}" data-launch-execution-current-action-withheld-count="${currentAction?.withheldCommandCount || 0}" data-launch-execution-current-action-acceptance-count="${currentAcceptance.length}" data-launch-execution-current-action-acceptance-pass-count="${currentAction?.acceptancePassCount || 0}" data-launch-execution-current-action-acceptance-pending-count="${currentAction?.acceptancePendingCount || 0}" data-launch-execution-current-action-verify-count="${currentVerifyCommands.length}" data-launch-execution-transition-source="${stageTransition.source || "ui-fallback"}" data-launch-execution-transition-current-stage="${currentStageKey}" data-launch-execution-transition-next-stage="${transitionNextStageKey}" data-launch-execution-transition-ready="${transitionReady ? "true" : "false"}" data-launch-execution-transition-pending-count="${transitionPendingCount}" data-launch-execution-transition-pass-count="${transitionPassCount}" data-launch-execution-transition-withheld-count="${transitionWithheldCount}" data-launch-execution-transition-gate-command="${transitionGateCommand}" data-launch-execution-blocker-resolution-source="${blockerResolution.source || "missing"}" data-launch-execution-blocker-resolution-status="${blockerResolution.status || "missing"}" data-launch-execution-blocker-resolution-active="${blockerResolution.activeItemKey || ""}" data-launch-execution-blocker-resolution-item-count="${blockerResolutionItemCount}" data-launch-execution-blocker-resolution-action-required-count="${blockerResolutionActionRequiredCount}" data-launch-execution-blocker-resolution-deferred-count="${blockerResolutionDeferredCount}" data-launch-execution-install-matrix-source="${installMatrix.source || "missing"}" data-launch-execution-install-matrix-path-count="${installMatrixPathCount}" data-launch-execution-install-matrix-signal-count="${installMatrixSignalCount}" data-launch-execution-install-matrix-verification-command-count="${installMatrixVerificationCommandCount}" data-launch-execution-install-matrix-ready-to-dispatch="${installMatrix.readyToDispatch ? "true" : "false"}" data-launch-post-install-evidence-intake-source="${postInstallIntake.source || "missing"}" data-launch-post-install-evidence-intake-status="${postInstallIntake.status || "missing"}" data-launch-post-install-evidence-intake-ready="${postInstallIntake.ready ? "true" : "false"}" data-launch-post-install-evidence-intake-proof-complete="${postInstallIntake.proofComplete ? "true" : "false"}" data-launch-post-install-evidence-intake-field-count="${postInstallIntakeFieldCount}" data-launch-post-install-evidence-intake-completed-count="${postInstallIntakeCompletedCount}" data-launch-post-install-evidence-intake-command-count="${postInstallIntakeCommandCount}" data-launch-post-install-evidence-intake-signal-count="${postInstallIntakeSignalCount}" data-launch-post-install-evidence-intake-field-coverage="${postInstallIntakeFieldCoverage}" data-launch-post-install-evidence-intake-sequence-count="${postInstallIntakeSequenceCount}" data-launch-post-install-evidence-intake-sequence-ready="${postInstallIntake.verificationSequenceReady ? "true" : "false"}" data-launch-post-install-evidence-intake-final-command="${postInstallIntake.finalVerificationCommand || postInstallIntakeSequence[postInstallIntakeSequence.length - 1]?.command || ""}" data-launch-post-install-quick-proof-ready="${postInstallIntake.quickProofReady ? "true" : "false"}" data-launch-post-install-quick-proof-step-count="${postInstallQuickProofStepCount}" data-launch-post-install-quick-proof-coverage="${postInstallQuickProofCoverage}" data-launch-post-install-quick-proof-final-command="${postInstallIntake.quickProofFinalCommand || postInstallIntake.finalVerificationCommand || ""}" data-launch-post-install-quick-proof-field-mapping-ready="${postInstallIntake.quickProofFieldMappingReady ? "true" : "false"}" data-launch-post-install-quick-proof-field-mapping-coverage="${postInstallQuickProofFieldMappingCoverage}" data-launch-post-install-quick-proof-mapped-field-count="${postInstallQuickProofMappedFieldCount}" data-launch-post-install-quick-proof-completed-mapped-field-count="${postInstallQuickProofCompletedMappedFieldCount}" data-remote-workflow-file-ledger-source="${remoteFileLedger.source || "missing"}" data-remote-workflow-file-ledger-status="${remoteFileLedger.status || "missing"}" data-remote-workflow-file-ledger-file-count="${remoteFileLedgerFileCount}" data-remote-workflow-file-ledger-ready-count="${remoteFileLedgerReadyCount}" data-remote-workflow-file-ledger-missing-count="${remoteFileLedgerMissingCount}" data-remote-workflow-file-ledger-mismatch-count="${remoteFileLedgerMismatchCount}" data-launch-proof-ledger-source="${proofLedger.source || "missing"}" data-launch-proof-ledger-status="${proofLedger.status || "missing"}" data-launch-proof-ledger-required-count="${proofLedgerRequiredCount}" data-launch-proof-ledger-ready-count="${proofLedgerReadyCount}" data-launch-proof-ledger-pending-count="${proofLedgerPendingCount}" data-launch-proof-ledger-current-gate="${proofLedger.currentGate || "capture_launch_proof"}" data-launch-proof-ledger-capture-command="${proofLedger.captureWriteCommand || ""}">
          <div class="publish-evidence-head">
            <strong>Launch execution packet</strong>
            <span class="publish-state" data-launch-execution-state-label>${stateLabel}</span>
          </div>
          <p class="settings-note">workflow 설치, visibility 확인, dispatch 보류 조건, live evidence 캡처, public claim guard를 한 번에 복사하는 실행 패킷입니다. <code>allDispatchReady: true</code> 전에는 dispatch 명령을 실행하지 않습니다.</p>
          <dl class="storage-grid">
            <div><dt>source</dt><dd>${source?.source || "data/launch-execution-packet.json"}</dd></div>
            <div><dt>generated</dt><dd>${generatedAt}</dd></div>
            <div><dt>repo</dt><dd>${data?.repo || "OWNER/REPO"}</dd></div>
            <div><dt>defaultBranch</dt><dd>${data?.defaultBranch || "main"}</dd></div>
            <div><dt>readyToDispatch</dt><dd>${readyToDispatch ? "true" : "false"}</dd></div>
            <div><dt>launchProofReady</dt><dd>${launchProofReady ? "true" : "false"}</dd></div>
            <div><dt>readyForExternalClaim</dt><dd>${externalReady ? "true" : "false"}</dd></div>
            <div><dt>stages</dt><dd>${stages.length}</dd></div>
            <div><dt>commands</dt><dd>${data?.commandCount || 0}</dd></div>
          </dl>
          ${source?.error ? raw(html`<p class="settings-note storage-error">launch execution packet load error: ${source.error}</p>`) : ""}
          ${operatorOnePageText ? raw(html`
            <article class="launch-operator-one-page" data-launch-operator-one-page data-launch-operator-one-page-source="${operatorOnePage.source || "generated_from_launch_execution_packet"}" data-launch-operator-one-page-ready="${operatorOnePage.ready ? "true" : "false"}" data-launch-operator-one-page-status="${operatorOnePage.status || "action_required"}" data-launch-operator-one-page-stage="${operatorOnePage.stageKey || currentAction?.stageKey || ""}" data-launch-operator-one-page-active="${operatorOnePage.activeItemKey || ""}" data-launch-operator-one-page-section-count="${operatorOnePage.sectionCount || 0}" data-launch-operator-one-page-command-count="${operatorOnePage.commandCount || 0}" data-launch-operator-one-page-immediate-command-count="${operatorOnePage.immediateCommandCount || 0}" data-launch-operator-one-page-fallback-command-count="${operatorOnePage.fallbackCommandCount || 0}" data-launch-operator-one-page-proof-command-count="${operatorOnePage.proofCommandCount || 0}" data-launch-operator-one-page-success-signal-count="${operatorOnePage.successSignalCount || 0}" data-launch-operator-one-page-forbidden-command-count="${operatorOnePage.forbiddenCommandCount || 0}">
              <div>
                <span>Operator one-page handoff</span>
                <strong>${operatorOnePage.activeItemKey || currentAction?.stageKey || "current blocker"}</strong>
                <small>${operatorOnePage.status || "action_required"} · ${operatorOnePage.sectionCount || 0} sections</small>
              </div>
              <p>긴 launch packet 전에 바로 실행할 명령, GitHub UI fallback, 증명 명령, 성공 신호, 금지 행동만 압축한 운영자용 one-page입니다.</p>
              <dl class="storage-grid">
                <div><dt>stage</dt><dd>${operatorOnePage.stageKey || currentAction?.stageKey || "not available"}</dd></div>
                <div><dt>immediate</dt><dd>${operatorOnePage.immediateCommandCount || 0}</dd></div>
                <div><dt>fallback</dt><dd>${operatorOnePage.fallbackCommandCount || 0}</dd></div>
                <div><dt>proof</dt><dd>${operatorOnePage.proofCommandCount || 0}</dd></div>
                <div><dt>signals</dt><dd>${operatorOnePage.successSignalCount || 0}</dd></div>
              </dl>
              <pre data-launch-operator-one-page-text hidden>${operatorOnePageText}</pre>
              <div class="launch-execution-current-action-copy" data-launch-operator-one-page-copy-card>
                <button type="button" class="portfolio-export-download portfolio-export-copy" data-action="copy-launch-operator-one-page" data-launch-operator-one-page-copy>one-page 복사</button>
                <small class="portfolio-export-status" data-launch-operator-one-page-copy-status aria-live="polite"></small>
              </div>
            </article>
          `) : ""}
          ${authPreflight.status ? raw(html`
            <article class="launch-execution-auth-preflight" data-launch-execution-auth-preflight>
              <div>
                <span>Auth preflight</span>
                <strong>${authPreflight.status}</strong>
                <small>${authPreflight.source || "publish-dispatch-plan"}</small>
              </div>
              <dl class="storage-grid">
                <div><dt>workflowScopeAvailable</dt><dd>${authPreflight.workflowScopeAvailable ? "true" : "false"}</dd></div>
                <div><dt>workflowScopeInstallBlocked</dt><dd>${authPreflight.workflowScopeInstallBlocked ? "true" : "false"}</dd></div>
                <div><dt>scopes</dt><dd>${authScopeList}</dd></div>
                <div><dt>missingScopes</dt><dd>${authMissingList}</dd></div>
                <div><dt>approval</dt><dd>${authApprovalStatus}</dd></div>
                <div><dt>approvalUrl</dt><dd><code>${authApprovalUrl}</code></dd></div>
                <div><dt>interactiveApprovalRequired</dt><dd>${authInteractiveApprovalRequired ? "true" : "false"}</dd></div>
                <div><dt>terminalWaitRequired</dt><dd>${authTerminalWaitRequired ? "true" : "false"}</dd></div>
              </dl>
              <div class="launch-execution-commands">
                <code>${authPreflight.refreshCommand || "gh auth refresh -h github.com -s workflow"}</code>
                <code>${authRefreshClipboardCommand}</code>
                <code>${authPreflight.recheckCommand || "node scripts/plan-publish-dispatch.mjs --live --repo OWNER/REPO"}</code>
                <code>${authApprovalPrompt}</code>
                <code>interactiveApprovalRequired=${authInteractiveApprovalRequired ? "true" : "false"}</code>
                <code>terminalWaitRequired=${authTerminalWaitRequired ? "true" : "false"}</code>
                <code>${authIncompleteApprovalSignal}</code>
                <code>${authDeviceCodePolicy}</code>
                <code>${authApprovalStopCondition}</code>
              </div>
            </article>
          `) : ""}
          ${postAuthCheckpoint.status ? raw(html`
            <article class="launch-execution-post-auth-checkpoint" data-launch-execution-post-auth-checkpoint>
              <div>
                <span>Post-auth checkpoint</span>
                <strong>${postAuthCheckpoint.status}</strong>
                <small>${postAuthCheckpoint.key || "post_auth_checkpoint"}</small>
              </div>
              <dl class="storage-grid">
                <div><dt>trigger</dt><dd>${postAuthCheckpoint.triggerCommand || "gh auth refresh -h github.com -s workflow"}</dd></div>
                <div><dt>confirm scope</dt><dd>${postAuthCheckpoint.authStatusCommand || "gh auth status -h github.com"}</dd></div>
                <div><dt>verify handoff</dt><dd>${postAuthCheckpoint.verifyCommand || "node scripts/verify-launch-handoff.mjs --repo OWNER/REPO --write --markdown"}</dd></div>
                <div><dt>install after pass</dt><dd>${postAuthCheckpoint.installCommand || "node scripts/install-remote-workflow-files.mjs --repo OWNER/REPO --write --verify"}</dd></div>
                <div><dt>commands</dt><dd>${postAuthCommandCount}</dd></div>
                <div><dt>expected signals</dt><dd>${postAuthExpectedSignalCount}</dd></div>
                <div><dt>blocked signals</dt><dd>${postAuthBlockedSignalCount}</dd></div>
                <div><dt>recheck sequence</dt><dd>${postAuthRecheckSequenceCount}</dd></div>
                <div><dt>source artifacts</dt><dd>${postAuthSourceArtifactCount}</dd></div>
                <div><dt>verification only</dt><dd>${postAuthCheckpoint.verificationOnly ? "true" : "false"}</dd></div>
                <div><dt>dispatch approval</dt><dd>${postAuthCheckpoint.dispatchApproval ? "true" : "false"}</dd></div>
              </dl>
              <div class="launch-execution-commands" data-launch-post-auth-expected-signals data-launch-post-auth-expected-count="${postAuthExpectedSignalCount}">
                <span>Expected signals</span>
                ${postAuthExpectedSignalDisplay.map((signal) => raw(html`<code>${signal}</code>`))}
              </div>
              <div class="launch-execution-commands" data-launch-post-auth-blocked-signals data-launch-post-auth-blocked-count="${postAuthBlockedSignalCount}">
                <span>Still blocked if</span>
                ${postAuthBlockedSignalDisplay.map((signal) => raw(html`<code>${signal}</code>`))}
              </div>
              ${postAuthRecheckSequenceDisplay.length ? raw(html`
                <div class="launch-execution-commands" data-launch-post-auth-recheck-sequence data-launch-post-auth-recheck-count="${postAuthRecheckSequenceCount}">
                  <span>Ordered recheck sequence</span>
                  <ol>
                    ${postAuthRecheckSequenceDisplay.map((step, index) => raw(html`
                      <li data-launch-post-auth-recheck-step data-launch-post-auth-recheck-index="${index + 1}" data-launch-post-auth-recheck-key="${step.key || ""}" data-launch-post-auth-recheck-command="${step.command || ""}" data-launch-post-auth-recheck-source="${step.sourceArtifact || ""}" data-launch-post-auth-recheck-expected="${step.expected || ""}" data-launch-post-auth-recheck-stop="${step.stopCondition || ""}">
                        <strong>${index + 1}. ${step.label || step.key || "recheck"}</strong>
                        <code>${step.command || "not available"}</code>
                        <small>Expected: ${step.expected || "not available"} · Source: ${step.sourceArtifact || "not available"} · Stop: ${step.stopCondition || "not available"}</small>
                      </li>
                    `))}
                  </ol>
                </div>
              `) : ""}
              ${postAuthSourceArtifactDisplay.length ? raw(html`
                <div class="launch-execution-commands" data-launch-post-auth-source-artifacts data-launch-post-auth-source-artifact-count="${postAuthSourceArtifactCount}">
                  <span>Source artifacts</span>
                  ${postAuthSourceArtifactDisplay.map((artifact) => raw(html`<code data-launch-post-auth-source-artifact="${artifact}">${artifact}</code>`))}
                </div>
              `) : ""}
              <p>${postAuthCheckpoint.guard || "Do not run gh workflow run until every action_required post-auth checkpoint item has passed and verify-launch-handoff reports safeToDispatch=true."}</p>
            </article>
          `) : ""}
          ${currentAction ? raw(html`
            <article class="launch-execution-current-action" data-launch-execution-current-action>
              <div>
                <span>Current action</span>
                <strong>${currentAction.label || "Next launch step"}</strong>
                <small>${currentAction.status || "pending"}</small>
              </div>
              <p>${currentAction.successCondition || "Complete the current stage and rerun verification."}</p>
              ${defaultBranchProof.ready ? raw(html`
                <div class="launch-current-default-branch-proof" data-launch-current-default-branch-proof data-launch-current-default-branch-proof-ready="true" data-launch-current-default-branch-proof-file-count="${defaultBranchProofFiles.length}" data-launch-current-default-branch-proof-requirement-count="${defaultBranchProofRequirements.length}">
                  <span>Default-branch requirement proof</span>
                  <strong>${defaultBranchProof.defaultBranch || data?.defaultBranch || "main"}</strong>
                  <p>${defaultBranchProof.source || "GitHub manual workflow dispatch docs + GitHub REST repository contents API"}</p>
                  <div class="launch-execution-commands">
                    <code>${defaultBranchProof.manualDispatchDocsUrl || "https://docs.github.com/en/actions/managing-workflow-runs/manually-running-a-workflow?tool=webui"}</code>
                    <code>${defaultBranchProof.repositoryContentsDocsUrl || "https://docs.github.com/en/rest/repos/contents#get-repository-content"}</code>
                    <code>${defaultBranchProof.workflowListCommand || "gh workflow list --repo OWNER/REPO --all --json name,path,state,id"}</code>
                  </div>
                  ${defaultBranchProofRequirements.length ? raw(html`
                    <ul>
                      ${defaultBranchProofRequirements.map((requirement) => raw(html`<li>${requirement}</li>`))}
                    </ul>
                  `) : ""}
                </div>
              `) : ""}
              ${currentInstallPaths.length ? raw(html`
                <div class="launch-execution-install-paths" data-launch-execution-install-paths>
                  ${currentInstallPaths.map((path) => raw(html`
                    <section data-launch-execution-install-path data-launch-execution-install-path-key="${path.key || ""}">
                      <div><strong>${path.label || "Install path"}</strong><span>${path.key || "path"}</span></div>
                      <p>${path.when || "Use the path that matches the operator's access."}</p>
                      ${Array.isArray(path.commands) && path.commands.length ? raw(html`
                        <div class="launch-execution-commands">
                          ${path.commands.map((command) => raw(html`<code>${command}</code>`))}
                        </div>
                      `) : ""}
                      <small>${path.success || ""} ${path.guard || ""}</small>
                    </section>
                  `))}
                </div>
              `) : ""}
              ${Array.isArray(currentAction.commands) && currentAction.commands.length ? raw(html`
                <div class="launch-execution-commands" data-launch-execution-current-action-commands>
                  ${currentAction.commands.map((command) => raw(html`<code>${command}</code>`))}
                </div>
              `) : ""}
              ${currentAcceptance.length ? raw(html`
                <ul class="launch-execution-acceptance" data-launch-execution-current-acceptance>
                  ${currentAcceptance.map((item) => raw(html`
                    <li data-launch-execution-acceptance-item data-launch-execution-acceptance-key="${item.key}" data-launch-execution-acceptance-status="${item.status}">
                      <div><strong>${item.label}</strong><span>${item.status}</span></div>
                      <p>${item.required}</p>
                      <small>${item.evidence}</small>
                    </li>
                  `))}
                </ul>
              `) : ""}
              ${currentVerifyCommands.length ? raw(html`
                <div class="launch-execution-commands" data-launch-execution-current-action-verify-commands>
                  <span>Verify after running</span>
                  ${currentVerifyCommands.map((command) => raw(html`<code>${command}</code>`))}
                </div>
              `) : ""}
              <pre data-launch-execution-current-action-text hidden>${currentAction.packet || ""}</pre>
              <div class="launch-execution-current-action-copy" data-launch-execution-current-action-copy-card>
                <button type="button" class="portfolio-export-download portfolio-export-copy" data-action="copy-launch-current-action-packet" data-launch-execution-current-action-copy>current action 복사</button>
                <small class="portfolio-export-status" data-launch-execution-current-action-copy-status aria-live="polite"></small>
              </div>
            </article>
          `) : ""}
          ${blockerResolutionItems.length ? raw(html`
            <article class="launch-blocker-resolution-checklist" data-launch-blocker-resolution-checklist data-launch-blocker-resolution-source="${blockerResolution.source || "missing"}" data-launch-blocker-resolution-status="${blockerResolution.status || "missing"}" data-launch-blocker-resolution-active="${blockerResolution.activeItemKey || ""}" data-launch-blocker-resolution-item-count="${blockerResolutionItemCount}" data-launch-blocker-resolution-pass-count="${blockerResolutionPassCount}" data-launch-blocker-resolution-action-required-count="${blockerResolutionActionRequiredCount}" data-launch-blocker-resolution-deferred-count="${blockerResolutionDeferredCount}" data-launch-blocker-resolution-proof-command-count="${blockerResolutionProofCommandCount}" data-launch-blocker-resolution-guard="${blockerResolution.guard || blockerResolution.dispatchGuard || ""}">
              <div>
                <span>Blocker resolution checklist</span>
                <strong>${blockerResolution.activeItemKey || "no active blocker"}</strong>
                <small>${blockerResolution.status || "pending"}</small>
              </div>
              <p>현재 막힌 launch 신호를 조치, 증명 명령, 기대값, 중단 조건으로 나눕니다. <code>safeToDispatch=true</code> 전에는 dispatch와 public claim을 계속 보류합니다.</p>
              <dl class="storage-grid">
                <div><dt>pass</dt><dd>${blockerResolutionPassCount}/${blockerResolutionItemCount}</dd></div>
                <div><dt>action required</dt><dd>${blockerResolutionActionRequiredCount}</dd></div>
                <div><dt>deferred</dt><dd>${blockerResolutionDeferredCount}</dd></div>
                <div><dt>proof commands</dt><dd>${blockerResolutionProofCommandCount}</dd></div>
              </dl>
              <ul class="launch-execution-acceptance" data-launch-blocker-resolution-list>
                ${blockerResolutionItems.map((item) => raw(html`
                  <li data-launch-blocker-resolution-item data-launch-blocker-resolution-key="${item.key || ""}" data-launch-blocker-resolution-status="${item.status || ""}">
                    <div><strong>${item.label || item.key}</strong><span>${item.status || "pending"}</span></div>
                    <p>${item.action || ""}</p>
                    <small>${item.blockedSignal || ""}</small>
                    ${item.proofCommand ? raw(html`<code>${item.proofCommand}</code>`) : ""}
                    <small>Expected: ${item.expectedValue || ""}</small>
                    <small>Stop: ${item.stopCondition || ""}</small>
                  </li>
                `))}
              </ul>
              <p>${blockerResolution.guard || blockerResolution.dispatchGuard || "Do not run gh workflow run until every action_required item has passed and verify-launch-handoff reports safeToDispatch=true."}</p>
            </article>
          `) : ""}
          ${installMatrixRows.length ? raw(html`
            <article class="launch-install-verification-matrix" data-launch-install-verification-matrix data-launch-install-verification-source="${installMatrix.source || "missing"}" data-launch-install-verification-status="${installMatrix.status || "unknown"}" data-launch-install-verification-path-count="${installMatrixPathCount}" data-launch-install-verification-signal-count="${installMatrixSignalCount}" data-launch-install-verification-command-count="${installMatrixVerificationCommandCount}" data-launch-install-verification-next-stage="${installMatrix.nextStageKey || "verify_visibility"}" data-launch-install-verification-ready-to-dispatch="${installMatrix.readyToDispatch ? "true" : "false"}">
              <div>
                <span>Workflow install verification matrix</span>
                <strong>${installMatrix.currentStageKey || "install_workflows"} -> ${installMatrix.nextStageKey || "verify_visibility"}</strong>
                <small>${installMatrix.status || "install_verification_required"}</small>
              </div>
              <p>두 설치 경로 모두 post-install proof를 같은 신호로 판정합니다. <code>remoteWorkflowFilesReady=true</code>, <code>remoteWorkflowVisibilityReady=true</code>, <code>dispatchReady=true</code>, <code>driftDispatchReady=true</code>, <code>allDispatchReady=true</code>, <code>verify-launch-handoff reports safeToDispatch=true</code> 전에는 dispatch를 보류합니다.</p>
              <div class="launch-execution-install-paths">
                ${installMatrixRows.map((row) => raw(html`
                  <section data-launch-install-verification-row data-launch-install-verification-row-key="${row.key || ""}" data-launch-install-verification-row-status="${row.status || ""}" data-launch-install-verification-row-command-count="${row.commandCount || 0}">
                    <div><strong>${row.label || "Install path"}</strong><span>${row.status || "pending"}</span></div>
                    <p>${row.guard || installMatrix.dispatchGuard || postInstallDispatchGuard}</p>
                    <code>${row.firstCommand || "choose install command"}</code>
                  </section>
                `))}
              </div>
              <div class="launch-execution-commands" data-launch-install-verification-commands>
                <span>Post-install verification</span>
                ${(installMatrixCommands.length ? installMatrixCommands : [installMatrix.remoteFileCommand, installMatrix.workflowListCommand, installMatrix.dispatchPlanCommand, installMatrix.handoffCommand].filter(Boolean)).map((command) => raw(html`<code>${command}</code>`))}
              </div>
              <ul class="launch-execution-acceptance" data-launch-install-verification-signals>
                ${installMatrixSignals.map((signal) => raw(html`
                  <li data-launch-install-verification-signal data-launch-install-verification-signal-key="${signal.key || ""}" data-launch-install-verification-signal-status="${signal.status || ""}">
                    <div><strong>${signal.label || signal.key}</strong><span>${signal.status || "pending"}</span></div>
                    <p>${signal.required || ""}</p>
                    <small>${signal.evidence || ""}</small>
                  </li>
                `))}
              </ul>
            </article>
          `) : ""}
          ${postInstallIntakeFields.length ? raw(html`
            <article class="launch-post-install-evidence-intake" data-launch-post-install-evidence-intake data-launch-post-install-evidence-intake-source="${postInstallIntake.source || "missing"}" data-launch-post-install-evidence-intake-status="${postInstallIntake.status || "missing"}" data-launch-post-install-evidence-intake-ready="${postInstallIntake.ready ? "true" : "false"}" data-launch-post-install-evidence-intake-proof-complete="${postInstallIntake.proofComplete ? "true" : "false"}" data-launch-post-install-evidence-intake-field-count="${postInstallIntakeFieldCount}" data-launch-post-install-evidence-intake-completed-count="${postInstallIntakeCompletedCount}" data-launch-post-install-evidence-intake-command-count="${postInstallIntakeCommandCount}" data-launch-post-install-evidence-intake-signal-count="${postInstallIntakeSignalCount}" data-launch-post-install-evidence-intake-field-coverage="${postInstallIntakeFieldCoverage}" data-launch-post-install-evidence-intake-sequence-count="${postInstallIntakeSequenceCount}" data-launch-post-install-evidence-intake-sequence-ready="${postInstallIntake.verificationSequenceReady ? "true" : "false"}" data-launch-post-install-evidence-intake-final-command="${postInstallIntake.finalVerificationCommand || postInstallIntakeSequence[postInstallIntakeSequence.length - 1]?.command || ""}" data-launch-post-install-quick-proof-ready="${postInstallIntake.quickProofReady ? "true" : "false"}" data-launch-post-install-quick-proof-step-count="${postInstallQuickProofStepCount}" data-launch-post-install-quick-proof-coverage="${postInstallQuickProofCoverage}" data-launch-post-install-quick-proof-final-command="${postInstallIntake.quickProofFinalCommand || postInstallIntake.finalVerificationCommand || ""}" data-launch-post-install-quick-proof-field-mapping-ready="${postInstallIntake.quickProofFieldMappingReady ? "true" : "false"}" data-launch-post-install-quick-proof-field-mapping-coverage="${postInstallQuickProofFieldMappingCoverage}" data-launch-post-install-quick-proof-mapped-field-count="${postInstallQuickProofMappedFieldCount}" data-launch-post-install-quick-proof-completed-mapped-field-count="${postInstallQuickProofCompletedMappedFieldCount}">
              <div>
                <span>Post-install evidence intake</span>
                <strong>${postInstallIntakeCompletedCount}/${postInstallIntakeFieldCount} proof fields complete</strong>
                <small>${postInstallIntake.status || "collect_post_install_proof"} · proofComplete=${postInstallIntake.proofComplete ? "true" : "false"}</small>
              </div>
              <p>GitHub UI 또는 workflow-scope CLI 설치 직후 commit, remote parity, Actions visibility, dispatch readiness, handoff verifier 증거를 한 객체로 모읍니다. 이 ledger가 copy-ready여도 <code>proofComplete=false</code>이면 dispatch는 계속 보류합니다.</p>
              <dl class="storage-grid">
                <div><dt>coverage</dt><dd>${postInstallIntakeFieldCoverage}</dd></div>
                <div><dt>commands</dt><dd>${postInstallIntakeCommandCount}</dd></div>
                <div><dt>signals</dt><dd>${postInstallIntakeSignalCount}</dd></div>
                <div><dt>pending</dt><dd>${postInstallIntakePendingFieldCount}</dd></div>
                <div><dt>quickProofCoverage</dt><dd>${postInstallQuickProofCoverage}</dd></div>
                <div><dt>quickProofSteps</dt><dd>${postInstallQuickProofStepCount}</dd></div>
                <div><dt>quickProofFieldMappingCoverage</dt><dd>${postInstallQuickProofFieldMappingCoverage}</dd></div>
                <div><dt>mappedFields</dt><dd>${postInstallQuickProofCompletedMappedFieldCount}/${postInstallQuickProofMappedFieldCount}</dd></div>
              </dl>
              ${postInstallQuickProofSteps.length ? raw(html`
                <div class="post-install-quick-proof" data-launch-post-install-quick-proof data-launch-post-install-quick-proof-ready="${postInstallIntake.quickProofReady ? "true" : "false"}" data-launch-post-install-quick-proof-step-count="${postInstallQuickProofStepCount}" data-launch-post-install-quick-proof-coverage="${postInstallQuickProofCoverage}">
                  <span>Quick proof</span>
                  <ol>
                    ${postInstallQuickProofSteps.map((step, index) => raw(html`
                      <li data-launch-post-install-quick-proof-step data-launch-post-install-quick-proof-step-key="${step.key || ""}" data-launch-post-install-quick-proof-step-command="${step.command || ""}" data-launch-post-install-quick-proof-step-expected="${step.expected || ""}" data-launch-post-install-quick-proof-step-field="${step.evidenceFieldKey || ""}">
                        <strong>${index + 1}. ${step.label || step.key}</strong>
                        <code>${step.command || ""}</code>
                        <small>${step.expected || ""}</small>
                      </li>
                    `))}
                  </ol>
                </div>
              `) : ""}
              ${postInstallQuickProofFieldMappings.length ? raw(html`
                <div class="post-install-quick-proof-map" data-launch-post-install-quick-proof-field-map data-launch-post-install-quick-proof-field-mapping-ready="${postInstallIntake.quickProofFieldMappingReady ? "true" : "false"}" data-launch-post-install-quick-proof-field-mapping-coverage="${postInstallQuickProofFieldMappingCoverage}" data-launch-post-install-quick-proof-mapped-field-count="${postInstallQuickProofMappedFieldCount}" data-launch-post-install-quick-proof-completed-mapped-field-count="${postInstallQuickProofCompletedMappedFieldCount}">
                  <span>Mapped fields</span>
                  <ol>
                    ${postInstallQuickProofFieldMappings.map((item, index) => raw(html`
                      <li data-launch-post-install-quick-proof-field-map-item data-launch-post-install-quick-proof-field-map-step="${item.stepKey || ""}" data-launch-post-install-quick-proof-field-map-field="${item.fieldKey || ""}" data-launch-post-install-quick-proof-field-map-status="${item.fieldStatus || ""}" data-launch-post-install-quick-proof-field-map-completed="${item.fieldCompleted ? "true" : "false"}">
                        <strong>${index + 1}. ${item.stepKey || "step"} -> ${item.fieldLabel || item.fieldKey}</strong>
                        <small>${item.fieldStatus || "missing"} · completed=${item.fieldCompleted ? "true" : "false"}</small>
                        <p>${item.currentValue || ""}</p>
                      </li>
                    `))}
                  </ol>
                </div>
              `) : ""}
              <div class="launch-execution-commands" data-launch-post-install-evidence-intake-commands>
	                <span>Verification commands</span>
	                ${postInstallIntakeCommands.map((command) => raw(html`<code data-launch-post-install-evidence-intake-command>${command}</code>`))}
	              </div>
              ${postInstallIntakeSequence.length ? raw(html`
                <div class="post-install-evidence-intake-sequence" data-launch-post-install-evidence-intake-sequence data-launch-post-install-evidence-intake-sequence-count="${postInstallIntakeSequenceCount}" data-launch-post-install-evidence-intake-sequence-ready="${postInstallIntake.verificationSequenceReady ? "true" : "false"}">
                  <span>Verification sequence</span>
                  <ol>
                    ${postInstallIntakeSequence.map((step, index) => raw(html`
                      <li data-launch-post-install-evidence-intake-sequence-step data-launch-post-install-evidence-intake-sequence-key="${step.key || ""}" data-launch-post-install-evidence-intake-sequence-command="${step.command || ""}" data-launch-post-install-evidence-intake-sequence-expected="${step.expected || ""}">
                        <strong>${index + 1}. ${step.label || step.key}</strong>
                        <code>${step.command || ""}</code>
                        <small>${step.expected || ""}</small>
                      </li>
                    `))}
                  </ol>
                </div>
              `) : ""}
	              <div class="post-install-evidence-intake-signals" data-launch-post-install-evidence-intake-signals>
                ${postInstallIntakeSignals.map((signal) => raw(html`<span data-launch-post-install-evidence-intake-signal>${signal}</span>`))}
              </div>
              <ul class="launch-execution-acceptance" data-launch-post-install-evidence-intake-fields>
                ${postInstallIntakeFields.map((field) => raw(html`
                  <li data-launch-post-install-evidence-intake-field data-launch-post-install-evidence-intake-field-key="${field.key || ""}" data-launch-post-install-evidence-intake-field-status="${field.status || ""}" data-launch-post-install-evidence-intake-field-completed="${field.completed ? "true" : "false"}">
                    <div><strong>${field.label || field.key}</strong><span>${field.status || "pending"}</span></div>
                    <p>${field.currentValue || ""}</p>
                    <small>Expected: ${field.expectedValue || ""}</small>
                    ${field.proofCommand ? raw(html`<code>${field.proofCommand}</code>`) : ""}
                    <small>Stop: ${field.stopCondition || ""}</small>
                  </li>
                `))}
              </ul>
              <p>${postInstallIntake.stopCondition || postInstallStopCondition}</p>
            </article>
          `) : ""}
          ${remoteFileLedgerItems.length ? raw(html`
            <article class="remote-workflow-file-acceptance-ledger" data-remote-workflow-file-acceptance-ledger data-remote-workflow-file-ledger-source="${remoteFileLedger.source || "missing"}" data-remote-workflow-file-ledger-status="${remoteFileLedger.status || "missing"}" data-remote-workflow-file-ledger-file-count="${remoteFileLedgerFileCount}" data-remote-workflow-file-ledger-ready-count="${remoteFileLedgerReadyCount}" data-remote-workflow-file-ledger-missing-count="${remoteFileLedgerMissingCount}" data-remote-workflow-file-ledger-mismatch-count="${remoteFileLedgerMismatchCount}" data-remote-workflow-file-ledger-verify-command="${remoteFileLedger.verifyCommand || ""}">
              <div>
                <span>Remote workflow file acceptance ledger</span>
                <strong>${remoteFileLedgerReadyCount}/${remoteFileLedgerFileCount} files ready</strong>
                <small>${remoteFileLedger.status || "remote_file_install_required"}</small>
              </div>
              <p>default branch에 설치되어야 하는 workflow 파일을 파일 단위로 검증합니다. 각 row는 template SHA, remote SHA, installAction, GitHub create/edit command, remoteExists, remoteMatchesTemplate를 함께 보여줍니다.</p>
              <div class="launch-execution-commands" data-remote-workflow-file-ledger-commands>
                <span>Verify after install</span>
                <code>${remoteFileLedger.verifyCommand || "node scripts/check-remote-workflow-files.mjs --repo OWNER/REPO --write"}</code>
                <code>${remoteFileLedger.dispatchPlanCommand || "node scripts/plan-publish-dispatch.mjs --live --repo OWNER/REPO --write"}</code>
              </div>
              <ul class="launch-execution-acceptance" data-remote-workflow-file-ledger-list>
                ${remoteFileLedgerItems.map((file) => raw(html`
                  <li data-remote-workflow-file-ledger-item data-remote-workflow-file-key="${file.key || ""}" data-remote-workflow-file-status="${file.status || ""}" data-remote-workflow-file-remote-exists="${file.remoteExists ? "true" : "false"}" data-remote-workflow-file-remote-matches="${file.remoteMatchesTemplate ? "true" : "false"}">
                    <div><strong>${file.name || file.key}</strong><span>${file.status || "pending"}</span></div>
                    <p>${file.path || ""}</p>
                    <small>installAction=${file.installAction || "pending"} · templateSha256=${file.templateSha256 || "not available"} · remoteSha256=${file.remoteSha256 || "not available"} · ${file.evidence || ""}</small>
                    <code>${file.templateCopyCommand || "copy template"}</code>
                    <code>${file.openCommand || (file.installAction === "verified_remote_matches_template" ? "No GitHub file edit required" : file.githubNewFileOpenCommand || file.githubNewFileUrl || "open GitHub file page")}</code>
                  </li>
                `))}
              </ul>
            </article>
          `) : ""}
          ${proofLedgerItems.length ? raw(html`
            <article class="launch-proof-acceptance-ledger" data-launch-proof-acceptance-ledger data-launch-proof-ledger-source="${proofLedger.source || "missing"}" data-launch-proof-ledger-status="${proofLedger.status || "missing"}" data-launch-proof-ledger-required-count="${proofLedgerRequiredCount}" data-launch-proof-ledger-ready-count="${proofLedgerReadyCount}" data-launch-proof-ledger-pending-count="${proofLedgerPendingCount}" data-launch-proof-ledger-current-gate="${proofLedger.currentGate || "capture_launch_proof"}" data-launch-proof-ledger-current-gate-status="${proofLedger.currentGateStatus || ""}" data-launch-proof-ledger-deferred-until="${proofLedger.deferredUntil || "safeToDispatch=true"}" data-launch-proof-ledger-capture-command="${proofLedger.captureWriteCommand || ""}">
              <div>
                <span>Launch proof acceptance ledger</span>
                <strong>${proofLedgerReadyCount}/${proofLedgerRequiredCount} proofs ready</strong>
                <small>${proofLedger.status || "proof_blocked_until_dispatch"}</small>
              </div>
              <p>dispatch 후 public launch proof로 인정할 필드를 한 곳에 고정합니다. <code>Pages html_url/status</code>, 두 workflow run의 <code>status/conclusion/url/headSha</code>, freshness, receipt, public claim guard가 모두 준비되기 전에는 외부 완료 claim을 막습니다.</p>
              <dl class="storage-grid">
                <div><dt>current gate</dt><dd>${proofLedger.currentGate || "capture_launch_proof"}</dd></div>
                <div><dt>deferred until</dt><dd>${proofLedger.deferredUntil || "safeToDispatch=true"}</dd></div>
                <div><dt>pending</dt><dd>${proofLedgerPendingCount}</dd></div>
                <div><dt>readyForExternalClaim</dt><dd>${proofLedger.readyForExternalClaim ? "true" : "false"}</dd></div>
              </dl>
              <div class="launch-execution-commands" data-launch-proof-acceptance-capture-commands>
                <span>Capture commands</span>
                <code>${proofLedger.captureMarkdownCommand || "node scripts/capture-publish-evidence.mjs --live --repo OWNER/REPO --markdown"}</code>
                <code>${proofLedger.captureWriteCommand || "node scripts/capture-publish-evidence.mjs --live --repo OWNER/REPO --write"}</code>
              </div>
              <ul class="launch-execution-acceptance" data-launch-proof-acceptance-list>
                ${proofLedgerItems.map((proof) => raw(html`
                  <li data-launch-proof-acceptance-item data-launch-proof-acceptance-key="${proof.key || ""}" data-launch-proof-acceptance-status="${proof.status || ""}">
                    <div><strong>${proof.label || proof.key}</strong><span>${proof.status || "pending"}</span></div>
                    <p>${proof.required || ""}</p>
                    <small>${proof.evidence || ""}</small>
                    ${proof.command ? raw(html`<code>${proof.command}</code>`) : ""}
                  </li>
                `))}
              </ul>
            </article>
          `) : ""}
          <article class="launch-transition-preview" data-launch-execution-transition-preview data-launch-transition-source="${stageTransition.source || "ui-fallback"}" data-launch-transition-current-stage="${currentStageKey}" data-launch-transition-next-stage="${transitionNextStageKey}" data-launch-transition-ready="${transitionReady ? "true" : "false"}" data-launch-transition-pending-count="${transitionPendingCount}" data-launch-transition-withheld-count="${transitionWithheldCount}">
            <div>
              <span>Stage transition preview</span>
              <strong>${currentAction?.label || "Current stage"} -> ${transitionNextStageLabel}</strong>
              <small>${transitionReady ? "ready after guard" : "conditional next stage"}</small>
            </div>
            <p>${transitionReady ? "safeToDispatch=true가 확인됐으므로 repo-scoped dispatch 후 launch proof capture로 전환합니다." : "post-install proof가 remoteWorkflowFilesReady=true와 remoteWorkflowVisibilityReady=true를 만들면 dispatch guard recheck로 전환합니다. 현재 dispatch command는 withheld 상태입니다."}</p>
            <dl class="storage-grid">
              <div><dt>current</dt><dd>${currentStageKey || "unknown"}</dd></div>
              <div><dt>next</dt><dd>${transitionNextStageKey}</dd></div>
              <div><dt>pending</dt><dd>${transitionPendingCount}</dd></div>
              <div><dt>withheld</dt><dd>${transitionWithheldCount}</dd></div>
            </dl>
            <ol>
              ${transitionPreviewSteps.map((step) => raw(html`
                <li data-launch-transition-step data-launch-transition-step-key="${step.key}" data-launch-transition-step-status="${step.status}">
                  <strong>${step.label}</strong>
                  <span>${step.status}</span>
                  <p>${step.condition}</p>
                </li>
              `))}
            </ol>
            <code data-launch-transition-gate-command>${transitionGateCommand}</code>
          </article>
          ${stages.length ? raw(html`
            <ol class="launch-execution-stages" data-launch-execution-stages>
              ${stages.map((stage) => raw(html`
                <li data-launch-execution-stage data-launch-execution-stage-key="${stage.key}" data-launch-execution-stage-status="${stage.status}">
                  <div><strong>${stage.label}</strong><span>${stage.status}</span></div>
                  <p>${stage.detail}</p>
                  ${Array.isArray(stage.commands) && stage.commands.length ? raw(html`
                    <div class="launch-execution-commands">
                      ${stage.commands.map((command) => raw(html`<code>${command}</code>`))}
                    </div>
                  `) : ""}
                </li>
              `))}
            </ol>
          `) : ""}
          ${comparisons.length ? raw(html`
            <ul class="launch-execution-comparison" data-launch-execution-comparison>
              ${comparisons.map((item) => raw(html`<li data-launch-execution-comparison-item data-launch-execution-comparison-key="${item.key}"><a href="${item.url}" target="_blank" rel="noopener">${item.label}</a><p>${item.detail}</p></li>`))}
            </ul>
          `) : ""}
          ${blockers.length ? raw(html`
            <ul class="publish-evidence-blockers" data-launch-execution-blockers>
              ${blockers.map((blocker) => raw(html`<li>${blocker}</li>`))}
            </ul>
          `) : ""}
          ${packet ? raw(html`
            <div class="launch-execution-copy" data-launch-execution-packet-copy-card>
              <div>
                <span>Copy-ready launch sequence</span>
                <strong>${externalReady ? "외부 공개 가능" : "실행 전 guard 포함"}</strong>
              </div>
              <pre data-launch-execution-packet-text hidden>${packet}</pre>
              <button type="button" class="portfolio-export-download portfolio-export-copy" data-action="copy-launch-execution-packet" data-launch-execution-packet-copy>launch packet 복사</button>
              <small class="portfolio-export-status" data-launch-execution-packet-copy-status aria-live="polite"></small>
            </div>
          `) : ""}
        </div>
      `;
    }

    function launchReadinessFreshness(data) {
      const freshness = data?.evidenceFreshness || {};
      const generatedMs = Date.parse(freshness.generatedAt || data?.generatedAt || "");
      const configuredMaxAgeHours = Number.isFinite(Number(freshness.maxAgeHours))
        ? Number(freshness.maxAgeHours)
        : Number.isFinite(Number(data?.evidenceMaxAgeHours)) ? Number(data.evidenceMaxAgeHours) : 24;
      const expiresMs = Number.isFinite(Date.parse(freshness.expiresAt || data?.evidenceExpiresAt || ""))
        ? Date.parse(freshness.expiresAt || data?.evidenceExpiresAt || "")
        : generatedMs + configuredMaxAgeHours * 60 * 60 * 1000;
      const hasGeneratedAt = Number.isFinite(generatedMs);
      const nowMs = dateNow();
      const ageHours = hasGeneratedAt ? Math.max(0, (nowMs - generatedMs) / (60 * 60 * 1000)) : null;
      const status = !hasGeneratedAt ? "missing" : nowMs > expiresMs ? "stale" : "fresh";
      const sourceArtifacts = Array.isArray(freshness.sourceArtifacts) ? freshness.sourceArtifacts : [];
      return {
        status,
        fresh: status === "fresh",
        refreshRequired: status !== "fresh",
        maxAgeHours: configuredMaxAgeHours,
        ageHours,
        ageLabel: ageHours === null ? "not available" : `${Math.round(ageHours * 10) / 10}h`,
        expiresAt: Number.isFinite(expiresMs) ? new Date(expiresMs).toISOString() : "",
        expiresAtLabel: Number.isFinite(expiresMs) ? formatLocalDateTime(new Date(expiresMs).toISOString()) : "not available",
        sourceArtifacts,
        sourceArtifactCount: finiteNumberOr(freshness.sourceArtifactCount, sourceArtifacts.length),
        policy: freshness.policy || "Rerun npm run refresh:launch-readiness before dispatch or external claim when this evidence is stale.",
      };
    }

    function launchReadinessDispatchCommandState(data, ready, safeToDispatch) {
      const suggestedCommands = Array.isArray(data?.suggestedDispatchCommands) ? data.suggestedDispatchCommands : [];
      const activeCommands = Array.isArray(data?.activeDispatchCommands) ? data.activeDispatchCommands : [];
      const suggestedCount = Number.isFinite(Number(data?.suggestedDispatchCommandCount))
        ? Number(data.suggestedDispatchCommandCount)
        : suggestedCommands.length;
      const referenceCount = Number.isFinite(Number(data?.dispatchCommandReferenceCount))
        ? Number(data.dispatchCommandReferenceCount)
        : suggestedCount;
      const activeCount = Number.isFinite(Number(data?.activeDispatchCommandCount))
        ? Number(data.activeDispatchCommandCount)
        : ready ? 0 : safeToDispatch ? suggestedCount || activeCommands.length : 0;
      const disposition = data?.dispatchCommandDisposition || (ready
        ? "not_applicable_after_launch_proof"
        : safeToDispatch ? "active" : "withheld");
      const label = disposition === "not_applicable_after_launch_proof"
        ? "not applicable after proof"
        : disposition === "active" ? "active" : "withheld";
      return {
        disposition,
        label,
        activeCount,
        referenceCount,
        suggestedCount,
        detail: `${label} · active ${activeCount} / reference ${referenceCount}`,
      };
    }

    function launchReadinessRefreshReceiptText(data, freshness) {
      const ready = data?.readyForExternalClaim === true;
      const safeToDispatch = data?.safeToDispatch === true;
      const dispatchState = launchReadinessDispatchCommandState(data, ready, safeToDispatch);
      const ab = data?.abComparison || {};
      const nextAction = data?.nextAction || {};
      const latestGate = data?.latestGate || {};
      const latestGateChecks = latestGate.checks || {};
      const latestGateLine = `${latestGate.command || "not available"} -> ${Number(latestGateChecks.pass || 0)} pass, ${Number(latestGateChecks.fail || 0)} fail, ${Number(latestGateChecks.notRun || 0)} not_run, ${Number(latestGateChecks.blocked || 0)} blocked`;
      const repairAction = data?.remoteWorkflowRepairAction || {};
      const sourceSync = data?.sourceArtifactSync || {};
      const checklist = Array.isArray(data?.refreshChecklist) ? data.refreshChecklist : [];
      const commands = Array.isArray(data?.commandRuns) ? data.commandRuns : [];
      const blockers = Array.isArray(data?.blockers) ? data.blockers : [];
      const artifacts = Array.isArray(freshness?.sourceArtifacts) ? freshness.sourceArtifacts : [];
      return [
        "# JooPark Launch Readiness Refresh Receipt",
        "",
        `status: ${data?.status || "missing"}`,
        `generatedAt: ${data?.generatedAt || "not available"}`,
        `evidenceFreshness: ${freshness?.status || "missing"}`,
        `refreshRequired: ${freshness?.refreshRequired ? "true" : "false"}`,
        `evidenceMaxAgeHours: ${freshness?.maxAgeHours || 24}`,
        `sourceArtifactCount: ${freshness?.sourceArtifactCount || 0}`,
        `sourceArtifactSync: ${sourceSync.status || "missing"}`,
        `sourceArtifactSyncOutputQualityGeneratedAt: ${sourceSync.outputQualityGeneratedAt || "not available"}`,
        `commandCoverage: ${data?.commandCoverage || 0}`,
        `A/B decision: ${ab.decision || "not checked"}`,
        `outputQualityGeneratedAt: ${data?.outputQualityGeneratedAt || "not available"}`,
        `outputQualitySourceInputCount: ${data?.outputQualitySourceInputCount || 0}`,
        `latestGate: ${latestGateLine}`,
        `outputQualityGateTraceability: ${data?.outputQualityGateTraceability?.status || "missing"}`,
        "",
        "## Readiness",
        `workflowScopeAvailable: ${data?.workflowScopeAvailable === true}`,
        `workflowScopeInstallBlocked: ${data?.workflowScopeInstallBlocked === true}`,
        `remoteWorkflowFilesReady: ${data?.remoteWorkflowFilesReady === true}`,
        `remoteWorkflowVisibilityReady: ${data?.remoteWorkflowVisibilityReady === true}`,
        `allDispatchReady: ${data?.allDispatchReady === true}`,
        `safeToDispatch: ${safeToDispatch}`,
        `readyForExternalClaim: ${ready}`,
        `suggestedDispatchCommandCount: ${data?.suggestedDispatchCommandCount || 0}`,
        `withheldDispatchCommandCount: ${data?.withheldDispatchCommandCount || 0}`,
        `dispatchCommandDisposition: ${dispatchState.disposition}`,
        `activeDispatchCommandCount: ${dispatchState.activeCount}`,
        `dispatchCommandReferenceCount: ${dispatchState.referenceCount}`,
        "",
        "## Next Action",
        `key: ${nextAction.key || "not available"}`,
        `status: ${nextAction.status || "not available"}`,
        `command: ${nextAction.command || "npm run refresh:launch-readiness"}`,
        `detail: ${nextAction.detail || "Do not run gh workflow run until every action_required refresh checklist item has passed and verify-launch-handoff reports safeToDispatch=true."}`,
        "",
        "## Remote Workflow Repair Action",
        `installAction: ${repairAction.installAction || "not required"}`,
        `target: ${repairAction.targetPath || "not available"}`,
        `command: ${repairAction.command || "not available"}`,
        `remoteBlobSha: ${repairAction.remoteBlobSha || "not available"}`,
        `githubEditFileUrl: ${repairAction.githubEditFileUrl || "not available"}`,
        "",
        "## Guard",
        data?.guard || "Do not run gh workflow run until every action_required refresh checklist item has passed and verify-launch-handoff reports safeToDispatch=true.",
        "",
        "## Refresh Checklist",
        ...(checklist.length ? checklist.map((item) => `- ${item.key || item.label}: ${item.status} - ${item.evidence}`) : ["- not available"]),
        "",
        "## Source Artifacts",
        ...(artifacts.length ? artifacts.map((artifact) => `- ${artifact.key}: ${artifact.status} - ${artifact.path}`) : ["- not available"]),
        "",
        "## Commands Run",
        ...(commands.length ? commands.map((run) => `- ${run.status}: ${run.command}`) : ["- not available"]),
        "",
        "## Blockers",
        ...(blockers.length ? blockers.map((blocker) => `- ${blocker}`) : ["- none"]),
      ].join("\n");
    }

    function launchReadinessRefreshHTML(source) {
      const data = source?.data || null;
      const loaded = !!(source?.loaded && data);
      const checklist = loaded && Array.isArray(data.refreshChecklist) ? data.refreshChecklist : [];
      const blockers = loaded && Array.isArray(data.blockers) ? data.blockers : [];
      const commands = loaded && Array.isArray(data.commandRuns) ? data.commandRuns : [];
      const ab = data?.abComparison || {};
      const nextAction = data?.nextAction || {};
      const latestGate = data?.latestGate || {};
      const latestGateChecks = latestGate.checks || {};
      const latestGateLine = `${latestGate.command || "not available"} -> ${Number(latestGateChecks.pass || 0)} pass, ${Number(latestGateChecks.fail || 0)} fail, ${Number(latestGateChecks.notRun || 0)} not_run, ${Number(latestGateChecks.blocked || 0)} blocked`;
      const ready = loaded && data.readyForExternalClaim === true;
      const safeToDispatch = loaded && data.safeToDispatch === true;
      const generatedAt = data?.generatedAt ? formatLocalDateTime(data.generatedAt) : "대기 중";
      const freshness = launchReadinessFreshness(data);
      const statusLabel = ready ? "external ready" : safeToDispatch ? "dispatch ready" : loaded ? "refresh complete" : "not loaded";
      const dispatchState = launchReadinessDispatchCommandState(data, ready, safeToDispatch);
      const repairAction = data?.remoteWorkflowRepairAction || {};
      const sourceSync = data?.sourceArtifactSync || {};
      const receiptText = launchReadinessRefreshReceiptText(data, freshness);
      return html`
        <div class="launch-readiness-refresh" data-system-launch-readiness-refresh data-launch-readiness-refresh-source="${source?.source || "data/launch-readiness-refresh.json"}" data-launch-readiness-refresh-loaded="${loaded ? "true" : "false"}" data-launch-readiness-refresh-status="${data?.status || "missing"}" data-launch-readiness-refresh-command-coverage="${data?.commandCoverage || 0}" data-launch-readiness-refresh-safe-to-dispatch="${safeToDispatch ? "true" : "false"}" data-launch-readiness-refresh-external-ready="${ready ? "true" : "false"}" data-launch-readiness-refresh-workflow-scope-available="${data?.workflowScopeAvailable ? "true" : "false"}" data-launch-readiness-refresh-workflow-scope-install-blocked="${data?.workflowScopeInstallBlocked ? "true" : "false"}" data-launch-readiness-refresh-remote-files-ready="${data?.remoteWorkflowFilesReady ? "true" : "false"}" data-launch-readiness-refresh-remote-visible="${data?.remoteWorkflowVisibilityReady ? "true" : "false"}" data-launch-readiness-refresh-all-dispatch-ready="${data?.allDispatchReady ? "true" : "false"}" data-launch-readiness-refresh-ready-for-external-claim="${ready ? "true" : "false"}" data-launch-readiness-refresh-withheld-count="${data?.withheldDispatchCommandCount || 0}" data-launch-readiness-refresh-suggested-dispatch-count="${data?.suggestedDispatchCommandCount || 0}" data-launch-readiness-refresh-active-dispatch-count="${dispatchState.activeCount}" data-launch-readiness-refresh-reference-dispatch-count="${dispatchState.referenceCount}" data-launch-readiness-refresh-dispatch-command-disposition="${dispatchState.disposition}" data-launch-readiness-refresh-next-action="${nextAction.key || ""}" data-launch-readiness-refresh-next-command="${nextAction.command || ""}" data-launch-readiness-refresh-repair-action="${repairAction.installAction || ""}" data-launch-readiness-refresh-repair-command="${repairAction.command || ""}" data-launch-readiness-refresh-repair-edit-url="${repairAction.githubEditFileUrl || ""}" data-launch-readiness-refresh-ab-decision="${ab.decision || ""}" data-launch-readiness-refresh-freshness-status="${freshness.status}" data-launch-readiness-refresh-fresh="${freshness.fresh ? "true" : "false"}" data-launch-readiness-refresh-refresh-required="${freshness.refreshRequired ? "true" : "false"}" data-launch-readiness-refresh-max-age-hours="${freshness.maxAgeHours}" data-launch-readiness-refresh-evidence-expires-at="${freshness.expiresAt}" data-launch-readiness-refresh-source-artifact-count="${freshness.sourceArtifactCount}" data-launch-readiness-refresh-source-artifact-sync="${sourceSync.status || "missing"}" data-launch-readiness-refresh-source-artifact-sync-output-quality-generated-at="${sourceSync.outputQualityGeneratedAt || ""}" data-launch-readiness-refresh-output-quality-gate-traceability="${data?.outputQualityGateTraceability?.status || "missing"}" data-launch-readiness-refresh-latest-gate-status="${latestGate.status || "missing"}" data-launch-readiness-refresh-latest-gate-pass="${Number(latestGateChecks.pass || 0)}" data-launch-readiness-refresh-latest-gate-total="${Number(latestGateChecks.total || 0)}" data-launch-readiness-refresh-output-quality-source-input-count="${data?.outputQualitySourceInputCount || 0}">
          <div class="publish-evidence-head">
            <strong>Launch readiness refresh</strong>
            <span class="publish-state" data-launch-readiness-refresh-state-label>${statusLabel} · ${freshness.status}</span>
          </div>
          <p class="settings-note">workflow UI plan, remote file check, dispatch plan, launch packet, handoff verifier, output quality audit을 한 번에 갱신한 결과입니다. 이 패널은 dispatch를 실행하지 않고 active dispatch command와 reference command를 분리합니다.</p>
          <dl class="storage-grid">
            <div><dt>source</dt><dd>${source?.source || "data/launch-readiness-refresh.json"}</dd></div>
            <div><dt>generated</dt><dd>${generatedAt}</dd></div>
            <div><dt>freshness</dt><dd>${freshness.status} · age ${freshness.ageLabel}</dd></div>
            <div><dt>expires</dt><dd>${freshness.expiresAtLabel}</dd></div>
            <div><dt>coverage</dt><dd>${data?.commandCoverage || 0} commands</dd></div>
            <div><dt>A/B</dt><dd>${ab.decision || "not checked"}</dd></div>
            <div><dt>latest gate</dt><dd>${latestGateLine}</dd></div>
            <div><dt>quality inputs</dt><dd>${data?.outputQualitySourceInputCount || 0} sources</dd></div>
            <div><dt>source sync</dt><dd>${sourceSync.status || "missing"} · ${sourceSync.outputQualityGeneratedAt || "not available"}</dd></div>
            <div><dt>workflow scope</dt><dd>${data?.workflowScopeAvailable ? "available" : data?.workflowScopeInstallBlocked ? "blocked" : "not checked"}</dd></div>
            <div><dt>remote files</dt><dd>${data?.remoteWorkflowFilesReady ? "ready" : "blocked"}</dd></div>
            <div><dt>dispatch</dt><dd>${dispatchState.detail}</dd></div>
            <div><dt>external claim</dt><dd>${ready ? "ready" : "blocked"}</dd></div>
          </dl>
          <div class="publish-dispatch-commands" data-launch-readiness-refresh-next-action>
            <strong>Next action</strong>
            <code>${nextAction.command || "npm run refresh:launch-readiness"}</code>
            <code>npm run refresh:launch-readiness</code>
            <small>${nextAction.detail || "Refresh launch readiness evidence before dispatch."}</small>
            <small data-launch-readiness-refresh-freshness-policy>${freshness.policy}</small>
          </div>
          <div class="publish-dispatch-commands" data-launch-readiness-refresh-repair-action>
            <strong>Remote workflow repair</strong>
            <code>${repairAction.installAction || "not required"}</code>
            <code>${repairAction.command || "not available"}</code>
            <small>${repairAction.githubEditFileUrl || repairAction.targetPath || "remote repair action 대기"}</small>
          </div>
          <div class="launch-execution-copy" data-launch-readiness-refresh-receipt data-launch-readiness-refresh-receipt-copy-ready="${loaded ? "true" : "false"}">
            <pre data-launch-readiness-refresh-receipt-text>${receiptText}</pre>
            <button type="button" class="portfolio-export-download portfolio-export-copy" data-action="copy-launch-readiness-refresh-receipt" data-launch-readiness-refresh-receipt-copy>readiness receipt 복사</button>
            <small class="portfolio-export-status" data-launch-readiness-refresh-receipt-copy-status aria-live="polite"></small>
          </div>
          ${freshness.sourceArtifacts.length ? raw(html`
            <ul class="settings-info" data-launch-readiness-refresh-source-artifacts>
              ${freshness.sourceArtifacts.map((artifact) => raw(html`
                <li data-launch-readiness-refresh-source-artifact data-launch-readiness-refresh-source-artifact-key="${artifact.key || ""}" data-launch-readiness-refresh-source-artifact-status="${artifact.status || ""}">
                  <strong>${artifact.key || "artifact"}</strong> · ${artifact.status || "unknown"} · ${artifact.path || ""}
                </li>
              `))}
            </ul>
          `) : ""}
          ${checklist.length ? raw(html`
            <ul class="settings-info" data-launch-readiness-refresh-checklist>
              ${checklist.map((item) => raw(html`
                <li data-launch-readiness-refresh-check data-launch-readiness-refresh-check-key="${item.key}" data-launch-readiness-refresh-check-status="${item.status}">
                  <strong>${item.label}</strong> · ${item.status} · ${item.evidence}
                </li>
              `))}
            </ul>
          `) : ""}
          ${commands.length ? raw(html`
            <div class="launch-execution-commands" data-launch-readiness-refresh-commands>
              ${commands.map((run) => raw(html`<code data-launch-readiness-refresh-command data-launch-readiness-refresh-command-status="${run.status}">${run.command}</code>`))}
            </div>
          `) : ""}
          ${blockers.length ? raw(html`
            <ul class="publish-evidence-blockers" data-launch-readiness-refresh-blockers>
              ${blockers.map((blocker) => raw(html`<li>${blocker}</li>`))}
            </ul>
          `) : ""}
        </div>
      `;
    }

    function durationSeconds(value) {
      const ms = Number(value || 0);
      if (!Number.isFinite(ms) || ms <= 0) return 0;
      return Math.round(ms / 1000);
    }

    const VERIFY_WORKSPACE_SUMMARY_REQUIRED_STEPS = ["release_readiness_gates", "launch_readiness_refresh", "product_loop_summary_sync"];

    function verifyWorkspaceSummaryReceiptText(data) {
      const artifacts = data?.artifacts || {};
      const releaseReadiness = artifacts.releaseReadiness || {};
      const launchReadiness = artifacts.launchReadiness || {};
      const outputQuality = artifacts.outputQuality || {};
      const productLoop = artifacts.productLoop || {};
      const evidenceSync = artifacts.evidenceSync || {};
      const steps = Array.isArray(data?.stepResults) ? data.stepResults : [];
      const nextCandidates = Array.isArray(productLoop.nextCandidates) ? productLoop.nextCandidates : [];
      const nextCandidateCount = finiteNumberOr(productLoop.nextCandidateCount, nextCandidates.length);
      const dispatchState = launchReadinessDispatchCommandState(launchReadiness, launchReadiness.readyForExternalClaim === true, launchReadiness.safeToDispatch === true);
      return [
        "# JooPark Verify Workspace Summary Receipt",
        "",
        `source: autoresearch-results/verify-workspace-summary.json`,
        `status: ${data?.status || "missing"}`,
        `generatedAt: ${data?.generatedAt || "not available"}`,
        `command: ${data?.command || "npm run verify:full"}`,
        `runner: ${data?.runner || "scripts/verify-workspace.mjs"}`,
        `syncArtifacts: ${data?.syncArtifacts === true}`,
        `evidenceSyncPass: ${data?.evidenceSyncPass === true}`,
        `durationSeconds: ${durationSeconds(data?.durationMs)}`,
        `requiredStepIds: ${VERIFY_WORKSPACE_SUMMARY_REQUIRED_STEPS.join(", ")}`,
        "",
        "## Artifacts",
        `releaseReadiness: ${releaseReadiness.status || "missing"} - ${releaseReadiness.summary || "not available"}`,
        `launchReadiness: ${launchReadiness.status || "missing"} - ${launchReadiness.latestGateSummary || "not available"}`,
        `outputQuality: ${outputQuality.status || "missing"} - ${outputQuality.latestGateSummary || "not available"}`,
        `productLoop: ${productLoop.status || "missing"} - ${productLoop.latestGateSummary || "not available"}; latestExperiment=${productLoop.latestExperiment || "not available"}; latestDirectionLoop=${productLoop.latestDirectionLoop || "not available"}; latestDirectionExperiment=${productLoop.latestDirectionExperiment || "not available"}; latestDiscoveryExperiment=${productLoop.latestDiscoveryExperiment || "not available"}`,
        `evidenceSync: ${evidenceSync.status || "missing"} - gateParity=${evidenceSync.productLoopGateParityReady === true}; publishParity=${evidenceSync.productLoopPublishParityReady === true}; summarySync=${evidenceSync.summarySyncReady === true}; nextCandidates=${evidenceSync.nextCandidatesReady === true}; nextCandidateList=${evidenceSync.nextCandidateListReady === true}; directionLoop=${evidenceSync.directionLoopSyncReady === true}; directionExperiment=${evidenceSync.latestDirectionExperimentReady === true}; discoveryExperiment=${evidenceSync.latestDiscoveryExperimentReady === true}`,
        `nextCandidateCount: ${nextCandidateCount}`,
        "",
        "## Next Candidates",
        ...(nextCandidates.length ? nextCandidates.map((candidate, index) => `${index + 1}. ${candidate}`) : ["not available"]),
        "",
        "## Steps",
        ...(steps.length ? steps.map((step) => `- ${step.id}: ${step.status}; ${durationSeconds(step.durationMs)}s; ${step.command}`) : ["- not available"]),
        "",
        "## Dispatch Guard",
        `safeToDispatch: ${launchReadiness.safeToDispatch === true}`,
        `readyForExternalClaim: ${launchReadiness.readyForExternalClaim === true}`,
        `dispatchCommandDisposition: ${dispatchState.disposition}`,
        `activeDispatchCommandCount: ${dispatchState.activeCount}`,
        `dispatchCommandReferenceCount: ${dispatchState.referenceCount}`,
        data?.externalClaimGuard || "Do not claim readyForExternalClaim until release quality, public launch proof, and external completion claim proof all pass.",
      ].join("\n");
    }

    function verifyWorkspaceSummaryHTML(source) {
      const data = source?.data || null;
      const loaded = !!(source?.loaded && data);
      const artifacts = data?.artifacts || {};
      const releaseReadiness = artifacts.releaseReadiness || {};
      const launchReadiness = artifacts.launchReadiness || {};
      const outputQuality = artifacts.outputQuality || {};
      const productLoop = artifacts.productLoop || {};
      const evidenceSync = artifacts.evidenceSync || {};
      const steps = loaded && Array.isArray(data.stepResults) ? data.stepResults : [];
      const nextCandidates = Array.isArray(productLoop.nextCandidates) ? productLoop.nextCandidates : [];
      const nextCandidateCount = finiteNumberOr(productLoop.nextCandidateCount, nextCandidates.length);
      const stepIds = new Set(steps.map((step) => step.id));
      const missingStepCount = VERIFY_WORKSPACE_SUMMARY_REQUIRED_STEPS.filter((id) => !stepIds.has(id)).length;
      const generatedAt = data?.generatedAt ? formatLocalDateTime(data.generatedAt) : "대기 중";
      const duration = durationSeconds(data?.durationMs);
      const evidenceSyncPass = loaded && data.evidenceSyncPass === true && evidenceSync.status === "pass";
      const statusLabel = loaded && data.status === "pass" && evidenceSyncPass ? "full verify pass" : loaded ? "review required" : "not loaded";
      const dispatchState = launchReadinessDispatchCommandState(launchReadiness, launchReadiness.readyForExternalClaim === true, launchReadiness.safeToDispatch === true);
      const receiptText = verifyWorkspaceSummaryReceiptText(data);
      return html`
        <div class="verify-workspace-summary" data-system-verify-workspace-summary data-verify-workspace-summary-source="${source?.source || "autoresearch-results/verify-workspace-summary.json"}" data-verify-workspace-summary-loaded="${loaded ? "true" : "false"}" data-verify-workspace-summary-status="${data?.status || "missing"}" data-verify-workspace-summary-command="${data?.command || "npm run verify:full"}" data-verify-workspace-summary-sync-artifacts="${data?.syncArtifacts ? "true" : "false"}" data-verify-workspace-summary-evidence-sync-pass="${evidenceSyncPass ? "true" : "false"}" data-verify-workspace-summary-step-count="${steps.length}" data-verify-workspace-summary-required-step-missing-count="${missingStepCount}" data-verify-workspace-summary-duration-seconds="${duration}" data-verify-workspace-summary-release-readiness="${releaseReadiness.status || "missing"}" data-verify-workspace-summary-launch-readiness="${launchReadiness.status || "missing"}" data-verify-workspace-summary-output-quality="${outputQuality.status || "missing"}" data-verify-workspace-summary-product-loop="${productLoop.status || "missing"}" data-verify-workspace-summary-latest-experiment="${productLoop.latestExperiment || ""}" data-verify-workspace-summary-latest-direction-loop="${productLoop.latestDirectionLoop || ""}" data-verify-workspace-summary-latest-direction-experiment="${productLoop.latestDirectionExperiment || ""}" data-verify-workspace-summary-latest-discovery-experiment="${productLoop.latestDiscoveryExperiment || ""}" data-verify-workspace-summary-direction-loop-sync="${evidenceSync.directionLoopSyncReady ? "true" : "false"}" data-verify-workspace-summary-direction-experiment-sync="${evidenceSync.latestDirectionExperimentReady ? "true" : "false"}" data-verify-workspace-summary-discovery-experiment-sync="${evidenceSync.latestDiscoveryExperimentReady ? "true" : "false"}" data-verify-workspace-summary-next-candidate-list="${evidenceSync.nextCandidateListReady ? "true" : "false"}" data-verify-workspace-summary-next-candidate-count="${nextCandidateCount}" data-verify-workspace-summary-evidence-sync="${evidenceSync.status || "missing"}" data-verify-workspace-summary-safe-to-dispatch="${launchReadiness.safeToDispatch ? "true" : "false"}" data-verify-workspace-summary-ready-for-external-claim="${launchReadiness.readyForExternalClaim ? "true" : "false"}" data-verify-workspace-summary-dispatch-command-disposition="${dispatchState.disposition}" data-verify-workspace-summary-active-dispatch-count="${dispatchState.activeCount}" data-verify-workspace-summary-reference-dispatch-count="${dispatchState.referenceCount}">
          <div class="publish-evidence-head">
            <strong>Verify workspace summary</strong>
            <span class="publish-state" data-verify-workspace-summary-state-label>${statusLabel}</span>
          </div>
          <p class="settings-note"><code>npm run verify:full</code>이 release gate, launch readiness refresh, product loop summary sync, evidenceSync parity를 모두 통과했는지 보여주는 full evidence sync 요약입니다.</p>
          <dl class="storage-grid">
            <div><dt>status</dt><dd>${data?.status || "missing"}</dd></div>
            <div><dt>generated</dt><dd>${generatedAt}</dd></div>
            <div><dt>duration</dt><dd>${duration}s</dd></div>
            <div><dt>syncArtifacts</dt><dd>${data?.syncArtifacts ? "true" : "false"}</dd></div>
            <div><dt>releaseReadiness</dt><dd>${releaseReadiness.status || "missing"} · ${releaseReadiness.summary || ""}</dd></div>
            <div><dt>launchReadiness</dt><dd>${launchReadiness.status || "missing"} · ${launchReadiness.latestGateSummary || ""}</dd></div>
            <div><dt>outputQuality</dt><dd>${outputQuality.status || "missing"} · ${outputQuality.latestGateSummary || ""}</dd></div>
            <div><dt>productLoop</dt><dd>${productLoop.status || "missing"} · experiment ${productLoop.latestExperiment || "no experiment"} · ${productLoop.latestDirectionLoop || "no direction loop"} · direction experiment ${productLoop.latestDirectionExperiment || "no direction experiment"} · discovery experiment ${productLoop.latestDiscoveryExperiment || "no discovery experiment"}</dd></div>
            <div><dt>evidenceSync</dt><dd>${evidenceSync.status || "missing"} · gate ${evidenceSync.productLoopGateParityReady === true ? "pass" : "missing"} · publish ${evidenceSync.productLoopPublishParityReady === true ? "pass" : "missing"} · summary ${evidenceSync.summarySyncReady === true ? "pass" : "missing"} · next ${evidenceSync.nextCandidatesReady === true ? "pass" : "missing"} · candidate list ${evidenceSync.nextCandidateListReady === true ? "pass" : "missing"} · direction ${evidenceSync.directionLoopSyncReady === true ? "pass" : "missing"} · direction experiment ${evidenceSync.latestDirectionExperimentReady === true ? "pass" : "missing"} · discovery experiment ${evidenceSync.latestDiscoveryExperimentReady === true ? "pass" : "missing"}</dd></div>
            <div><dt>next candidates</dt><dd>${nextCandidateCount}</dd></div>
            <div><dt>dispatch</dt><dd>${dispatchState.detail}</dd></div>
            <div><dt>external claim</dt><dd>${launchReadiness.readyForExternalClaim ? "ready" : "blocked"}</dd></div>
            <div><dt>steps</dt><dd>${steps.length}</dd></div>
          </dl>
          ${steps.length ? raw(html`
            <ul class="settings-info" data-verify-workspace-summary-steps>
              ${steps.map((step) => raw(html`
                <li data-verify-workspace-summary-step data-verify-workspace-summary-step-id="${step.id || ""}" data-verify-workspace-summary-step-status="${step.status || ""}">
                  <strong>${step.id || "step"}</strong> · ${step.status || "missing"} · ${durationSeconds(step.durationMs)}s · <code>${step.command || ""}</code>
                </li>
              `))}
            </ul>
          `) : ""}
          ${nextCandidates.length ? raw(html`
            <ol class="settings-info" data-verify-workspace-summary-next-candidates>
              ${nextCandidates.map((candidate, index) => raw(html`
                <li data-verify-workspace-summary-next-candidate data-verify-workspace-summary-next-candidate-index="${index + 1}">
                  ${candidate}
                </li>
              `))}
            </ol>
          `) : ""}
          <div class="launch-execution-copy" data-verify-workspace-summary-receipt data-verify-workspace-summary-receipt-copy-ready="${loaded ? "true" : "false"}">
            <pre data-verify-workspace-summary-receipt-text>${receiptText}</pre>
            <button type="button" class="portfolio-export-download portfolio-export-copy" data-action="copy-verify-workspace-summary-receipt" data-verify-workspace-summary-receipt-copy>verify receipt 복사</button>
            <small class="portfolio-export-status" data-verify-workspace-summary-receipt-copy-status aria-live="polite"></small>
          </div>
        </div>
      `;
    }

    function releaseGateCacheRepairText(data, source) {
      const gate = data?.packagedBrowserGate || data?.packagedBrowserGates || {};
      const cache = gate.cache || {};
      const checks = data?.checks || {};
      const completionAudit = data?.completionAudit || {};
      const blockedSignals = Array.isArray(completionAudit.blockedSignals) ? completionAudit.blockedSignals : [];
      const issues = Array.isArray(cache.issues) ? cache.issues : [];
      const mismatches = Array.isArray(cache.contextMismatches) ? cache.contextMismatches : [];
      const contextMatched = cache.contextMatched !== false;
      const cachedEvidenceStatus = cache.cachedEvidenceStatus || "missing";
      const cachedResultStatus = cache.cachedResultStatus || "missing";
      const repairCommand = "npm test";
      const recheckCommand = "node scripts/audit-release-readiness.mjs --format=summary";
      return [
        "# JooPark Release Gate Cache Repair",
        "",
        `source: ${source?.source || "autoresearch-results/release-readiness-summary.json"}`,
        `status: ${data?.status || "missing"}`,
        `generatedAt: ${data?.generatedAt || "not available"}`,
        `summary: ${Number(checks.pass || 0)} pass, ${Number(checks.fail || 0)} fail, ${Number(checks.notRun || 0)} not_run, ${Number(checks.blocked || 0)} blocked`,
        `completionAudit: ${completionAudit.status || "missing"}`,
        `launchCompletionAchieved: ${completionAudit.launchCompletionAchieved === true}`,
        `readyForExternalClaim: ${completionAudit.readyForExternalClaim === true}`,
        `blockedSignals: ${blockedSignals.length ? blockedSignals.join("; ") : "none"}`,
        `packagedBrowserGate.status: ${gate.status || "missing"}`,
        `packagedBrowserGate.cached: ${gate.cached === true}`,
        `cache.status: ${cache.status || (contextMatched ? "valid" : "invalid")}`,
        `cachedEvidenceStatus: ${cachedEvidenceStatus}`,
        `cachedResultStatus: ${cachedResultStatus}`,
        `contextMatched: ${contextMatched}`,
        `cache.generatedAt: ${cache.generatedAt || "not available"}`,
        `cache.ageMinutes: ${Number(cache.ageMinutes || 0)}`,
        `cache.inputFiles: ${Number(cache.inputFiles || 0)}`,
        "",
        "## Issues",
        ...(issues.length ? issues.map((issue) => `- ${issue}`) : ["- none"]),
        "",
        "## Context mismatches",
        ...(mismatches.length
          ? mismatches.map((item) => `- ${item.path || "unknown"}: ${item.reason || "changed"}; cached=${item.cached?.sha256 || "missing"}; current=${item.current?.sha256 || "missing"}`)
          : ["- none"]),
        "",
        "## Repair commands",
        `1. ${repairCommand}`,
        `2. ${recheckCommand}`,
        "",
        "Stop condition: do not rely on cached packaged browser gates when contextMatched=false, cachedEvidenceStatus/cachedResultStatus is not pass, issues includes context_mismatch, or the audit summary reports not_run.",
      ].join("\n");
    }

    function releaseGateCacheHTML(source) {
      const data = source?.data || null;
      const loaded = !!(source?.loaded && data);
      const gate = data?.packagedBrowserGate || data?.packagedBrowserGates || {};
      const cache = gate.cache || {};
      const checks = data?.checks || {};
      const completionAudit = data?.completionAudit || {};
      const blockedSignals = Array.isArray(completionAudit.blockedSignals) ? completionAudit.blockedSignals : [];
      const issues = Array.isArray(cache.issues) ? cache.issues : [];
      const mismatches = Array.isArray(cache.contextMismatches) ? cache.contextMismatches : [];
      const contextMatched = loaded && cache.contextMatched !== false;
      const gatePass = loaded && gate.status === "pass";
      const generatedAt = data?.generatedAt ? formatLocalDateTime(data.generatedAt) : "대기 중";
      const cacheGeneratedAt = cache.generatedAt ? formatLocalDateTime(cache.generatedAt) : "not available";
      const cacheStatus = cache.status || (contextMatched ? "valid" : "invalid");
      const cachedEvidenceStatus = cache.cachedEvidenceStatus || "missing";
      const cachedResultStatus = cache.cachedResultStatus || "missing";
      const cacheAvailable = gate.cached === true ||
        (cacheStatus === "valid" && cachedEvidenceStatus === "pass" && cachedResultStatus === "pass");
      const cacheReady = gatePass &&
        cacheAvailable &&
        contextMatched &&
        cacheStatus === "valid" &&
        cachedEvidenceStatus === "pass" &&
        cachedResultStatus === "pass" &&
        issues.length === 0 &&
        mismatches.length === 0 &&
        Number(checks.notRun || 0) === 0;
      const stateLabel = cacheReady ? "cached pass" : loaded ? "repair required" : "not loaded";
      const repairCommand = "npm test";
      const recheckCommand = "node scripts/audit-release-readiness.mjs --format=summary";
      const repairText = releaseGateCacheRepairText(data, source);
      return html`
        <div class="release-gate-cache" data-system-release-gate-cache data-release-gate-cache-source="${source?.source || "autoresearch-results/release-readiness-summary.json"}" data-release-gate-cache-loaded="${loaded ? "true" : "false"}" data-release-gate-cache-status="${gate.status || "missing"}" data-release-gate-cache-summary-status="${data?.status || "missing"}" data-release-gate-cache-cached="${cacheAvailable ? "true" : "false"}" data-release-gate-cache-context-matched="${contextMatched ? "true" : "false"}" data-release-gate-cache-ready="${cacheReady ? "true" : "false"}" data-release-gate-cache-cache-status="${cacheStatus}" data-release-gate-cache-cached-evidence-status="${cachedEvidenceStatus}" data-release-gate-cache-cached-result-status="${cachedResultStatus}" data-release-gate-cache-age-minutes="${Number(cache.ageMinutes || 0)}" data-release-gate-cache-input-files="${Number(cache.inputFiles || 0)}" data-release-gate-cache-issue-count="${issues.length}" data-release-gate-cache-mismatch-count="${mismatches.length}" data-release-gate-cache-pass="${Number(checks.pass || 0)}" data-release-gate-cache-fail="${Number(checks.fail || 0)}" data-release-gate-cache-not-run="${Number(checks.notRun || 0)}" data-release-gate-cache-blocked="${Number(checks.blocked || 0)}" data-release-gate-cache-completion-audit="${completionAudit.status || "missing"}" data-release-gate-cache-launch-completion-achieved="${completionAudit.launchCompletionAchieved === true ? "true" : "false"}" data-release-gate-cache-ready-for-external-claim="${completionAudit.readyForExternalClaim === true ? "true" : "false"}" data-release-gate-cache-completion-blocked-signals="${blockedSignals.join("; ")}" data-release-gate-cache-repair-command="${repairCommand}" data-release-gate-cache-recheck-command="${recheckCommand}">
          <div class="publish-evidence-head">
            <strong>Release gate cache</strong>
            <span class="publish-state" data-release-gate-cache-state-label>${stateLabel}</span>
          </div>
          <p class="settings-note">빠른 audit summary가 재사용하는 packaged browser gate cache의 fingerprint 상태입니다. <code>contextMatched=false</code>, <code>cachedEvidenceStatus</code>/<code>cachedResultStatus</code>가 pass가 아니거나 <code>context_mismatch</code>, <code>not_run</code>이 보이면 <code>${repairCommand}</code>로 fresh packaged browser gate를 만든 뒤 summary를 다시 확인합니다.</p>
          <dl class="storage-grid">
            <div><dt>summary</dt><dd>${Number(checks.pass || 0)} pass / ${Number(checks.fail || 0)} fail / ${Number(checks.notRun || 0)} not_run</dd></div>
            <div><dt>completion audit</dt><dd>${completionAudit.status || "missing"} · launchCompletionAchieved=${completionAudit.launchCompletionAchieved === true ? "true" : "false"}</dd></div>
            <div><dt>blocked signals</dt><dd>${blockedSignals.length ? blockedSignals.join("; ") : "none"}</dd></div>
            <div><dt>packaged gate</dt><dd>${gate.status || "missing"}${gate.cached ? " · cached" : ""}</dd></div>
            <div><dt>context</dt><dd>${contextMatched ? "matched" : "mismatch"}</dd></div>
            <div><dt>cache</dt><dd>${cacheStatus} · age ${Number(cache.ageMinutes || 0)}m</dd></div>
            <div><dt>cachedEvidenceStatus</dt><dd>${cachedEvidenceStatus}</dd></div>
            <div><dt>cachedResultStatus</dt><dd>${cachedResultStatus}</dd></div>
            <div><dt>generated</dt><dd>${generatedAt}</dd></div>
            <div><dt>cache generated</dt><dd>${cacheGeneratedAt}</dd></div>
            <div><dt>input files</dt><dd>${Number(cache.inputFiles || 0)}</dd></div>
            <div><dt>issues</dt><dd>${issues.length} issues · ${mismatches.length} mismatches</dd></div>
          </dl>
          <div class="publish-dispatch-commands" data-release-gate-cache-repair>
            <strong>Repair path</strong>
            <code>${repairCommand}</code>
            <code>${recheckCommand}</code>
            <small>Rebuild the packaged browser gate cache, then confirm the audit summary reports <code>0 not_run</code>.</small>
          </div>
          ${issues.length || mismatches.length ? raw(html`
            <ul class="settings-info" data-release-gate-cache-issues>
              ${issues.map((issue) => raw(html`<li data-release-gate-cache-issue>${issue}</li>`))}
              ${mismatches.map((item) => raw(html`
                <li data-release-gate-cache-mismatch data-release-gate-cache-mismatch-path="${item.path || ""}" data-release-gate-cache-mismatch-reason="${item.reason || ""}">
                  <strong>${item.path || "unknown"}</strong> · ${item.reason || "changed"}
                </li>
              `))}
            </ul>
          `) : ""}
          <div class="launch-execution-copy" data-release-gate-cache-repair-receipt data-release-gate-cache-repair-copy-ready="${loaded ? "true" : "false"}">
            <pre data-release-gate-cache-repair-text>${repairText}</pre>
            <button type="button" class="portfolio-export-download portfolio-export-copy" data-action="copy-release-gate-cache-repair" data-release-gate-cache-repair-copy>cache repair 복사</button>
            <small class="portfolio-export-status" data-release-gate-cache-repair-copy-status aria-live="polite"></small>
          </div>
        </div>
      `;
    }

    function releaseProvenanceReceiptText(data, source) {
      const predicate = data?.predicate || {};
      const buildDefinition = predicate.buildDefinition || {};
      const runDetails = predicate.runDetails || {};
      const jooparkRelease = predicate.joopark_release || {};
      const subject = Array.isArray(data?.subject) ? data.subject.find((item) => item?.name === "release-manifest.json") : null;
      const dependencies = Array.isArray(buildDefinition.resolvedDependencies) ? buildDefinition.resolvedDependencies : [];
      const externalParameters = buildDefinition.externalParameters || {};
      const internalParameters = buildDefinition.internalParameters || {};
      return [
        "# JooPark Release Provenance Receipt",
        "",
        `source: ${source?.source || "release-provenance.json"}`,
        `loaded: ${source?.loaded === true}`,
        `statementType: ${data?._type || "missing"}`,
        `predicateType: ${data?.predicateType || "missing"}`,
        `subject: ${subject?.name || "missing"}`,
        `subjectSha256: ${subject?.digest?.sha256 || "missing"}`,
        `buildType: ${buildDefinition.buildType || "missing"}`,
        `builderId: ${runDetails.builder?.id || "missing"}`,
        `sourceCommit: ${externalParameters.sourceCommit || "missing"}`,
        `sourceBranch: ${externalParameters.sourceBranch || "missing"}`,
        `sourceDirty: ${externalParameters.sourceDirty === true}`,
        `runtimeFileCount: ${internalParameters.runtimeFileCount || jooparkRelease.runtimeFileCount || 0}`,
        `totalBytes: ${internalParameters.totalBytes || jooparkRelease.totalBytes || 0}`,
        `resolvedDependencies: ${dependencies.length}`,
        `signed: ${jooparkRelease.signed === true}`,
        `signatureStatus: ${jooparkRelease.signatureStatus || "missing"}`,
        "",
        "## Guard",
        "This is unsigned local provenance. Do not present it as a GitHub artifact attestation, signed SLSA attestation, public launch proof, or external completion claim.",
        "Verify command: node scripts/verify-release.mjs",
        "Full gate: npm run verify:full",
        "",
        "## External Attestation Path",
        jooparkRelease.strongerExternalReference || "GitHub artifact attestations can sign release artifacts after workflow installation.",
      ].join("\n");
    }

    function releaseProvenanceHTML(source) {
      const data = source?.data || null;
      const loaded = !!(source?.loaded && data);
      const predicate = data?.predicate || {};
      const buildDefinition = predicate.buildDefinition || {};
      const runDetails = predicate.runDetails || {};
      const jooparkRelease = predicate.joopark_release || {};
      const subject = Array.isArray(data?.subject) ? data.subject.find((item) => item?.name === "release-manifest.json") : null;
      const dependencies = Array.isArray(buildDefinition.resolvedDependencies) ? buildDefinition.resolvedDependencies : [];
      const externalParameters = buildDefinition.externalParameters || {};
      const internalParameters = buildDefinition.internalParameters || {};
      const subjectDigest = subject?.digest?.sha256 || "";
      const signed = jooparkRelease.signed === true;
      const signatureStatus = jooparkRelease.signatureStatus || "missing";
      const statusLabel = loaded ? (signed ? "signed" : signatureStatus) : "not loaded";
      const receiptText = releaseProvenanceReceiptText(data, source);
      const coreDependencies = ["source-tree", "index.html", "app.js", "sw.js", "data", "vendor"];
      return html`
        <div class="release-provenance" data-system-release-provenance data-release-provenance-source="${source?.source || "release-provenance.json"}" data-release-provenance-loaded="${loaded ? "true" : "false"}" data-release-provenance-statement-type="${data?._type || ""}" data-release-provenance-predicate-type="${data?.predicateType || ""}" data-release-provenance-subject="${subject?.name || ""}" data-release-provenance-subject-sha="${subjectDigest}" data-release-provenance-build-type="${buildDefinition.buildType || ""}" data-release-provenance-builder-id="${runDetails.builder?.id || ""}" data-release-provenance-source-commit="${externalParameters.sourceCommit || ""}" data-release-provenance-source-branch="${externalParameters.sourceBranch || ""}" data-release-provenance-source-dirty="${externalParameters.sourceDirty === true ? "true" : "false"}" data-release-provenance-runtime-file-count="${internalParameters.runtimeFileCount || jooparkRelease.runtimeFileCount || 0}" data-release-provenance-total-bytes="${internalParameters.totalBytes || jooparkRelease.totalBytes || 0}" data-release-provenance-dependency-count="${dependencies.length}" data-release-provenance-signed="${signed ? "true" : "false"}" data-release-provenance-signature-status="${signatureStatus}" data-release-provenance-verify-command="node scripts/verify-release.mjs">
          <div class="publish-evidence-head">
            <strong>Release provenance</strong>
            <span class="publish-state" data-release-provenance-state-label>${statusLabel}</span>
          </div>
          <p class="settings-note">패키지 manifest를 subject digest로 묶은 로컬 provenance입니다. 이 증거는 unsigned 상태이며 GitHub artifact attestation이나 공개 완료 증거로 주장하지 않습니다.</p>
          <dl class="storage-grid">
            <div><dt>subject</dt><dd>${subject?.name || "missing"}</dd></div>
            <div><dt>subject sha256</dt><dd><code data-release-provenance-subject-sha-text>${subjectDigest ? subjectDigest.slice(0, 16) : "missing"}</code></dd></div>
            <div><dt>predicate</dt><dd>${data?.predicateType || "missing"}</dd></div>
            <div><dt>buildType</dt><dd>${buildDefinition.buildType || "missing"}</dd></div>
            <div><dt>builder</dt><dd>${runDetails.builder?.id || "missing"}</dd></div>
            <div><dt>source</dt><dd>${externalParameters.sourceCommit || "missing"} · ${externalParameters.sourceBranch || "unknown"}</dd></div>
            <div><dt>dependencies</dt><dd>${dependencies.length}</dd></div>
            <div><dt>runtime files</dt><dd>${internalParameters.runtimeFileCount || jooparkRelease.runtimeFileCount || 0}</dd></div>
            <div><dt>signed</dt><dd>${signed ? "true" : "false"}</dd></div>
            <div><dt>status</dt><dd>${signatureStatus}</dd></div>
          </dl>
          <div class="publish-dispatch-commands" data-release-provenance-commands>
            <strong>Verification</strong>
            <code>node scripts/verify-release.mjs</code>
            <code>npm run verify:full</code>
            <small>${jooparkRelease.strongerExternalReference || "GitHub artifact attestations can sign release artifacts after workflow installation."}</small>
          </div>
          ${dependencies.length ? raw(html`
            <ul class="settings-info" data-release-provenance-dependencies>
              ${coreDependencies.map((name) => {
                const dependency = dependencies.find((item) => item?.name === name) || {};
                const digest = dependency.digest?.sha256 || dependency.digest?.gitCommit || "";
                return raw(html`
                  <li data-release-provenance-dependency data-release-provenance-dependency-name="${name}" data-release-provenance-dependency-present="${dependency.name ? "true" : "false"}">
                    <strong>${name}</strong> · ${dependency.name ? "present" : "missing"}${digest ? ` · ${digest.slice(0, 12)}` : ""}
                  </li>
                `);
              })}
            </ul>
          `) : ""}
          <div class="launch-execution-copy" data-release-provenance-receipt data-release-provenance-receipt-copy-ready="${loaded ? "true" : "false"}">
            <pre data-release-provenance-receipt-text>${receiptText}</pre>
            <button type="button" class="portfolio-export-download portfolio-export-copy" data-action="copy-release-provenance-receipt" data-release-provenance-receipt-copy>provenance receipt 복사</button>
            <small class="portfolio-export-status" data-release-provenance-receipt-copy-status aria-live="polite"></small>
          </div>
        </div>
      `;
    }

    function pagesAttestationProofIntakeReceiptText(input = {}) {
      const dispatchData = input.publishDispatchPlan?.data || {};
      const launchData = input.launchExecutionPacket?.data || {};
      const repo = dispatchData.repoEvidenceReady && dispatchData.repo && dispatchData.repo !== "OWNER/REPO"
        ? dispatchData.repo
        : dispatchData.suggestedRepo || launchData.repo || "biojuho/BIOJUHO-Projects";
      const workflowRunCommand = `gh run list --repo ${repo} --workflow joopark-pages.yml --limit 1 --json databaseId,status,conclusion,url,headSha,createdAt,updatedAt,event,displayTitle`;
      const manifestVerifyCommand = `gh attestation verify dist/release/release-manifest.json -R ${repo}`;
      const indexVerifyCommand = `gh attestation verify dist/release/index.html -R ${repo}`;
      const actionOutputUrl = `https://github.com/${repo}/attestations/[attestation-id]`;
      return [
        "# JooPark Pages Attestation Proof Intake",
        "",
        "Status: proof intake ready; not signed proof yet",
        `Repo: ${repo}`,
        "Workflow: joopark-pages.yml",
        "Attestation action: actions/attest@v4",
        "Subject path: dist/release/**",
        "Required permission: attestations: write",
        "",
        "Proof fields to fill after the Pages workflow run:",
        `- pages_workflow_run: paste the successful run URL/headSha from ${workflowRunCommand}`,
        `- attestation_url: paste actions/attest attestation-url output, expected shape ${actionOutputUrl}`,
        "- attestation_id: paste actions/attest attestation-id output",
        `- manifest_verify: paste pass output from ${manifestVerifyCommand}`,
        `- index_verify: paste pass output from ${indexVerifyCommand}`,
        "- predicate_type: confirm SLSA build provenance predicate is present",
        "",
        "Verification commands:",
        workflowRunCommand,
        manifestVerifyCommand,
        indexVerifyCommand,
        "",
        "Guard:",
        "Do not claim signed GitHub artifact attestation proof, readyForExternalClaim=true, public launch complete, or archive proof until the remote Pages workflow has run, actions/attest produced attestation-url, both gh attestation verify commands pass, and capture-publish-evidence plus verify-launch-handoff report the final public proof gates as ready.",
        "",
        "External comparison:",
        "GitHub artifact attestations require workflow permissions plus actions/attest, and actions/attest exposes attestation-url/attestation-id outputs for the signed proof handoff.",
      ].join("\n");
    }

    function pagesAttestationProofIntakeHTML(input = {}) {
      const launchData = input.launchExecutionPacket?.data || {};
      const dispatchData = input.publishDispatchPlan?.data || {};
      const repo = dispatchData.repoEvidenceReady && dispatchData.repo && dispatchData.repo !== "OWNER/REPO"
        ? dispatchData.repo
        : dispatchData.suggestedRepo || launchData.repo || "biojuho/BIOJUHO-Projects";
      const remoteWorkflowReady = dispatchData.remoteWorkflowVisibilityReady === true || launchData.remoteWorkflowVisibilityReady === true;
      const allDispatchReady = dispatchData.allDispatchReady === true || launchData.allDispatchReady === true;
      const ready = false;
      const workflowRunCommand = `gh run list --repo ${repo} --workflow joopark-pages.yml --limit 1 --json databaseId,status,conclusion,url,headSha,createdAt,updatedAt,event,displayTitle`;
      const manifestVerifyCommand = `gh attestation verify dist/release/release-manifest.json -R ${repo}`;
      const indexVerifyCommand = `gh attestation verify dist/release/index.html -R ${repo}`;
      const proofFields = [
        { key: "pages_workflow_run", label: "Pages workflow run", value: remoteWorkflowReady ? "capture after dispatch" : "blocked_until_workflow_visible" },
        { key: "attestation_url", label: "Attestation URL", value: "pending actions/attest attestation-url" },
        { key: "attestation_id", label: "Attestation ID", value: "pending actions/attest attestation-id" },
        { key: "manifest_verify", label: "Manifest verify", value: manifestVerifyCommand },
        { key: "index_verify", label: "Index verify", value: indexVerifyCommand },
        { key: "predicate_type", label: "Predicate type", value: "https://slsa.dev/provenance/v1" },
      ];
      const receipt = pagesAttestationProofIntakeReceiptText(input);
      return html`
        <div class="pages-attestation-proof-intake" data-system-pages-attestation-proof-intake data-pages-attestation-proof-intake-ready="${ready ? "true" : "false"}" data-pages-attestation-proof-intake-copy-ready="true" data-pages-attestation-proof-intake-verification-only="true" data-pages-attestation-proof-intake-repo="${repo}" data-pages-attestation-proof-intake-workflow="joopark-pages.yml" data-pages-attestation-proof-intake-action="actions/attest@v4" data-pages-attestation-proof-intake-subject-path="dist/release/**" data-pages-attestation-proof-intake-required-permission="attestations: write" data-pages-attestation-proof-intake-field-count="${proofFields.length}" data-pages-attestation-proof-intake-command-count="3" data-pages-attestation-proof-intake-remote-workflow-visible="${remoteWorkflowReady ? "true" : "false"}" data-pages-attestation-proof-intake-all-dispatch-ready="${allDispatchReady ? "true" : "false"}" data-pages-attestation-proof-intake-manifest-verify-command="${manifestVerifyCommand}" data-pages-attestation-proof-intake-index-verify-command="${indexVerifyCommand}">
          <div class="publish-evidence-head">
            <strong>Pages attestation proof intake</strong>
            <span class="publish-state">proof pending</span>
          </div>
          <p class="settings-note">actions/attest@v4 실행 후 attestation-url, attestation-id, gh attestation verify 결과를 모으는 증거 수집 패킷입니다. remote workflow 실행 전에는 signed proof로 주장하지 않습니다.</p>
          <dl class="storage-grid">
            <div><dt>repo</dt><dd>${repo}</dd></div>
            <div><dt>workflow</dt><dd>joopark-pages.yml</dd></div>
            <div><dt>action</dt><dd>actions/attest@v4</dd></div>
            <div><dt>subject</dt><dd>dist/release/**</dd></div>
            <div><dt>permission</dt><dd>attestations: write</dd></div>
            <div><dt>ready</dt><dd>false</dd></div>
          </dl>
          <ul class="settings-info" data-pages-attestation-proof-fields>
            ${proofFields.map((field) => raw(html`
              <li data-pages-attestation-proof-field data-pages-attestation-proof-field-key="${field.key}">
                <strong>${field.label}</strong> · ${field.value}
              </li>
            `))}
          </ul>
          <div class="publish-dispatch-commands" data-pages-attestation-proof-commands>
            <strong>Verification commands</strong>
            <code>${workflowRunCommand}</code>
            <code>${manifestVerifyCommand}</code>
            <code>${indexVerifyCommand}</code>
          </div>
          <div class="launch-execution-copy" data-pages-attestation-proof-intake-receipt data-pages-attestation-proof-intake-receipt-copy-ready="true">
            <pre data-pages-attestation-proof-intake-receipt-text>${receipt}</pre>
            <button type="button" class="portfolio-export-download portfolio-export-copy" data-action="copy-pages-attestation-proof-intake" data-pages-attestation-proof-intake-copy>attestation proof intake 복사</button>
            <small class="portfolio-export-status" data-pages-attestation-proof-intake-copy-status aria-live="polite"></small>
          </div>
        </div>
      `;
    }

    function publishEvidenceFresh(data) {
      if (!data?.generatedAt) return false;
      const maxAgeHours = Number.isFinite(Number(data.evidenceMaxAgeHours)) ? Number(data.evidenceMaxAgeHours) : 24;
      const expiresAt = data.evidenceExpiresAt
        ? Date.parse(data.evidenceExpiresAt)
        : Date.parse(data.generatedAt) + maxAgeHours * 60 * 60 * 1000;
      return Number.isFinite(expiresAt) && dateNow() <= expiresAt;
    }

    function publishEvidenceNextActionLabel(nextAction) {
      if (nextAction?.label) return nextAction.label;
      if (nextAction?.key === "capture-live-evidence") return "Capture live publish evidence";
      if (nextAction?.key === "replace-repo-placeholder") return "Replace OWNER/REPO";
      return nextAction?.key || "Action required";
    }

    function publishEvidenceNextActionDetail(nextAction) {
      if (nextAction?.detail) return nextAction.detail;
      if (nextAction?.key === "capture-live-evidence") return "Dry-run evidence is not launch proof; run live capture after workflow installation and dispatch.";
      if (nextAction?.key === "replace-repo-placeholder") return "Use the suggested repo before running live dispatch or saving evidence.";
      return "Resolve the current publish evidence blocker before sharing launch proof.";
    }

    function publishEvidenceActionCommand(action) {
      if (!action) return "";
      if (action.command) return action.command;
      if (Array.isArray(action.commands) && action.commands.length) return action.commands[0];
      if (Array.isArray(action.verifyCommands) && action.verifyCommands.length) return action.verifyCommands[0];
      return "";
    }

    function publishEvidenceHTML(source) {
      const data = source?.data || null;
      const loaded = !!(source?.loaded && data);
      const capturedReady = !!data?.postPublishEvidenceReady;
      const evidenceFresh = loaded ? publishEvidenceFresh(data) : false;
      const readyForExternalClaim = data?.readyForExternalClaim === true;
      const launchProofCaptured = capturedReady && evidenceFresh;
      const launchProofReady = launchProofCaptured && readyForExternalClaim;
      const mode = data?.mode || "not loaded";
      const repoReady = !!data?.repoEvidenceReady;
      const pagesReady = !!data?.pagesEvidenceReady;
      const workflowReady = !!data?.workflowEvidenceReady;
      const pagesUrl = data?.pagesSite?.site?.html_url || "";
      const displayRepo = data?.displayRepo || data?.suggestedRepo || data?.repo || "";
      const evidenceRepo = data?.evidenceRepo || data?.repo || "";
      const suggestedRepo = data?.suggestedRepo || "";
      const repoResolution = data?.repoResolution || "";
      const repoPlaceholderResolved = !!data?.repoPlaceholderResolved;
      const repoReplacementHint = data?.repoReplacementHint || "";
      const generatedAt = data?.generatedAt ? formatLocalDateTime(data.generatedAt) : "대기 중";
      const evidenceExpiresAt = data?.evidenceExpiresAt ? formatLocalDateTime(data.evidenceExpiresAt) : "대기 중";
      const evidenceMaxAgeHours = Number.isFinite(Number(data?.evidenceMaxAgeHours)) ? Number(data.evidenceMaxAgeHours) : 24;
      const blockers = Array.isArray(data?.blockers) ? data.blockers : [];
      const nextAction = data?.nextAction && typeof data.nextAction === "object" ? data.nextAction : null;
      const immediateNextAction = data?.immediateNextAction && typeof data.immediateNextAction === "object" ? data.immediateNextAction : nextAction;
      const deferredNextAction = data?.deferredNextAction && typeof data.deferredNextAction === "object" ? data.deferredNextAction : null;
      const launchInstallPaths = data?.launchInstallPaths || immediateNextAction?.launchInstallPaths || {};
      const launchInstallPathItems = Array.isArray(launchInstallPaths.paths) ? launchInstallPaths.paths : [];
      const launchInstallPathItemCommandCount = launchInstallPathItems.reduce(
        (total, item) => total + installPathItemCommandCount(item),
        0,
      );
      const launchInstallPathCount = finiteNumberOr(launchInstallPaths.count, launchInstallPathItems.length);
      const launchInstallPathCommandCount = finiteNumberOr(launchInstallPaths.commandCount, launchInstallPathItemCommandCount);
      const suggestedCommands = Array.isArray(data?.suggestedCommands) ? data.suggestedCommands : [];
      const suggestedDispatchCommands = Array.isArray(data?.suggestedDispatchCommands) ? data.suggestedDispatchCommands : [];
      const withheldDispatchCommands = Array.isArray(data?.withheldDispatchCommands) ? data.withheldDispatchCommands : [];
      const publishDispatchReady = !!data?.publishDispatchReady;
      const publishDispatchDisposition = data?.dispatchCommandDisposition || (launchProofReady ? "not_applicable_after_launch_proof" : publishDispatchReady ? "active_until_launch_proof" : "withheld_until_all_dispatch_ready");
      const publishActiveDispatchCount = finiteNumberOr(data?.activeDispatchCommandCount, 0);
      const publishReferenceDispatchCount = finiteNumberOr(
        data?.dispatchCommandReferenceCount,
        launchProofReady ? suggestedDispatchCommands.length : withheldDispatchCommands.length,
      );
      const dispatchSuggestionStatus = data?.dispatchSuggestionStatus || "";
      const suggestedCommandsSafe = !suggestedCommands.some((command) => command.includes("gh workflow run --repo"));
      const shareUpdate = data?.shareUpdate || "";
      const launchAnnouncement = data?.launchAnnouncement || "";
      const postLaunchVerificationReceipt = data?.postLaunchVerificationReceipt || "";
      const launchProofEvidenceReceipt = data?.launchProofEvidenceReceipt || "";
      const launchProofEvidenceFields = Array.isArray(data?.launchProofEvidenceFields) ? data.launchProofEvidenceFields : [];
      const launchProofEvidenceFieldLabels = ["Pages site proof", "Pages workflow run proof", "Drift Watch workflow run proof", "Evidence freshness proof", "Release receipt proof", "Public claim guard proof"];
      const launchProofEvidenceDisplayFields = launchProofEvidenceFields.length ? launchProofEvidenceFields : launchProofEvidenceFieldLabels.map((label) => ({ label, value: "not available" }));
      const launchProofEvidenceFieldCoverage = Number(data?.launchProofEvidenceFieldCoverage || (launchProofEvidenceDisplayFields.length >= 6 ? 1 : 0));
      const stateLabel = launchProofReady ? "launch proof ready" : launchProofCaptured ? "external claim guarded" : capturedReady && !evidenceFresh ? "stale evidence" : loaded && mode === "dry-run" ? "dry-run evidence" : "action required";
      return html`
        <div class="publish-evidence" data-system-publish-evidence data-publish-evidence-source="${source?.source || "data/publish-evidence.json"}" data-publish-evidence-loaded="${loaded ? "true" : "false"}" data-publish-evidence-ready="${launchProofReady ? "true" : "false"}" data-publish-evidence-launch-proof-ready="${launchProofReady ? "true" : "false"}" data-publish-evidence-mode="${mode}" data-publish-evidence-fresh="${evidenceFresh ? "true" : "false"}" data-publish-evidence-repo-ready="${repoReady ? "true" : "false"}" data-publish-evidence-pages-ready="${pagesReady ? "true" : "false"}" data-publish-evidence-workflows-ready="${workflowReady ? "true" : "false"}" data-publish-evidence-display-repo="${displayRepo}" data-publish-evidence-evidence-repo="${evidenceRepo}" data-publish-evidence-repo-resolution="${repoResolution}" data-publish-evidence-repo-placeholder-resolved="${repoPlaceholderResolved ? "true" : "false"}" data-publish-evidence-suggested-repo="${suggestedRepo}" data-publish-evidence-next-action="${nextAction?.key || ""}" data-publish-evidence-next-command="${nextAction?.command || ""}" data-publish-evidence-immediate-action="${immediateNextAction?.key || ""}" data-publish-evidence-immediate-action-status="${immediateNextAction?.status || ""}" data-publish-evidence-immediate-action-source="${immediateNextAction?.source || ""}" data-publish-evidence-immediate-command="${publishEvidenceActionCommand(immediateNextAction)}" data-publish-evidence-immediate-command-count="${Number(immediateNextAction?.commandCount || 0)}" data-publish-evidence-immediate-withheld-command-count="${Number(immediateNextAction?.withheldCommandCount || 0)}" data-publish-evidence-install-paths-ready="${launchInstallPaths.ready ? "true" : "false"}" data-publish-evidence-install-path-count="${launchInstallPathCount}" data-publish-evidence-install-path-command-count="${launchInstallPathCommandCount}" data-publish-evidence-deferred-action="${deferredNextAction?.key || ""}" data-publish-evidence-deferred-command="${deferredNextAction?.command || ""}" data-publish-evidence-dispatch-ready="${publishDispatchReady ? "true" : "false"}" data-publish-evidence-dispatch-suggestion-status="${dispatchSuggestionStatus}" data-publish-evidence-dispatch-command-disposition="${publishDispatchDisposition}" data-publish-evidence-active-dispatch-count="${publishActiveDispatchCount}" data-publish-evidence-reference-dispatch-count="${publishReferenceDispatchCount}" data-publish-evidence-suggested-commands-safe="${suggestedCommandsSafe ? "true" : "false"}" data-publish-evidence-suggested-dispatch-count="${suggestedDispatchCommands.length}" data-publish-evidence-withheld-dispatch-count="${withheldDispatchCommands.length}" data-publish-evidence-share-update-ready="${shareUpdate ? "true" : "false"}" data-publish-evidence-launch-announcement-ready="${launchAnnouncement ? "true" : "false"}" data-publish-evidence-post-launch-receipt-ready="${postLaunchVerificationReceipt ? "true" : "false"}" data-publish-evidence-launch-proof-receipt-ready="${launchProofEvidenceReceipt ? "true" : "false"}" data-publish-evidence-launch-proof-field-count="${launchProofEvidenceDisplayFields.length}" data-publish-evidence-launch-proof-field-coverage="${launchProofEvidenceFieldCoverage}">
          <div class="publish-evidence-head">
            <strong>Post-dispatch evidence</strong>
            <span class="publish-state" data-publish-evidence-state-label>${stateLabel}</span>
          </div>
          ${immediateNextAction ? raw(html`
            <div class="publish-evidence-next-action" data-publish-evidence-next-action-card>
              <span>Next action · Immediate action</span>
              <strong>${publishEvidenceNextActionLabel(immediateNextAction)}</strong>
              <p>${immediateNextAction.successCondition ? `Success condition: ${immediateNextAction.successCondition}` : publishEvidenceNextActionDetail(immediateNextAction)}</p>
              <code>${publishEvidenceActionCommand(immediateNextAction) || "node scripts/capture-publish-evidence.mjs --live --repo OWNER/REPO --markdown"}</code>
              ${launchInstallPathItems.length ? raw(html`
                <div class="publish-evidence-command-list" data-publish-evidence-install-paths>
                  <span>Choose one install path</span>
                  ${launchInstallPathItems.map((item) => raw(html`<p data-publish-evidence-install-path-item data-publish-evidence-install-path-key="${item.key || ""}"><strong>${item.label || "Install path"}</strong> · ${installPathItemCommandCount(item)} commands · ${item.when || ""} ${Array.isArray(item.commands) ? item.commands.join(" | ") : ""}</p>`))}
                </div>
              `) : ""}
              ${deferredNextAction ? raw(html`
                <div class="publish-evidence-deferred-action" data-publish-evidence-deferred-action-card>
                  <span>Deferred evidence capture</span>
                  <strong>${publishEvidenceNextActionLabel(deferredNextAction)}</strong>
                  <p>${publishEvidenceNextActionDetail(deferredNextAction)}</p>
                  <code>${deferredNextAction.command || ""}</code>
                </div>
              `) : ""}
            </div>
          `) : ""}
          ${(suggestedCommands.length || withheldDispatchCommands.length || suggestedDispatchCommands.length) ? raw(html`
            <div class="publish-evidence-command-guard" data-publish-evidence-command-guard>
              <div>
                <span>Dispatch command guard</span>
                <strong>${launchProofReady ? "dispatch commands archived" : publishDispatchReady ? "dispatch commands ready" : "dispatch commands withheld"}</strong>
                <p>dispatchCommandDisposition: ${publishDispatchDisposition}; activeDispatchCommandCount: ${publishActiveDispatchCount}; dispatchCommandReferenceCount: ${publishReferenceDispatchCount}; dispatchSuggestionStatus: ${dispatchSuggestionStatus || "not available"}</p>
              </div>
              ${suggestedCommands.length ? raw(html`
                <div class="publish-evidence-command-list" data-publish-evidence-suggested-commands>
                  <span>Suggested repo commands</span>
                  ${suggestedCommands.map((command) => raw(html`<code>${command}</code>`))}
                </div>
              `) : ""}
              ${suggestedDispatchCommands.length ? raw(html`
                <div class="publish-evidence-command-list" data-publish-evidence-suggested-dispatch-commands>
                  <span>Suggested dispatch commands</span>
                  ${suggestedDispatchCommands.map((command) => raw(html`<code>${command}</code>`))}
                </div>
              `) : ""}
              ${withheldDispatchCommands.length ? raw(html`
                <div class="publish-evidence-command-list" data-publish-evidence-withheld-dispatch-commands>
                  <span>Withheld dispatch commands</span>
                  ${withheldDispatchCommands.map((command) => raw(html`<code>${command}</code>`))}
                </div>
              `) : ""}
            </div>
          `) : ""}
          ${shareUpdate ? raw(html`
            <div class="publish-evidence-share-update" data-publish-evidence-share-update>
              <div>
                <span>Launch proof share update</span>
                <strong>${launchProofReady ? "공유 가능" : "action-required update"}</strong>
              </div>
              <pre data-publish-evidence-share-update-text hidden>${shareUpdate}</pre>
              <button type="button" class="portfolio-export-download portfolio-export-copy" data-action="copy-publish-evidence-share-update" data-publish-evidence-share-update-copy>share update 복사</button>
              <small class="portfolio-export-status" data-publish-evidence-share-update-copy-status aria-live="polite"></small>
            </div>
          `) : ""}
          ${launchAnnouncement ? raw(html`
            <div class="publish-evidence-launch-announcement" data-publish-evidence-launch-announcement>
              <div>
                <span>Public launch announcement</span>
                <strong>${launchProofReady ? "게시 가능" : "proof 전 게시 차단"}</strong>
              </div>
              <pre data-publish-evidence-launch-announcement-text hidden>${launchAnnouncement}</pre>
              <button type="button" class="portfolio-export-download portfolio-export-copy" data-action="copy-publish-launch-announcement" data-publish-evidence-launch-announcement-copy>launch announcement 복사</button>
              <small class="portfolio-export-status" data-publish-evidence-launch-announcement-copy-status aria-live="polite"></small>
            </div>
          `) : ""}
          ${postLaunchVerificationReceipt ? raw(html`
            <div class="publish-evidence-post-launch-receipt" data-publish-evidence-post-launch-receipt>
              <div>
                <span>Post-launch verification receipt</span>
                <strong>${launchProofReady ? "보관 가능" : "verification 보관 차단"}</strong>
              </div>
              <pre data-publish-evidence-post-launch-receipt-text hidden>${postLaunchVerificationReceipt}</pre>
              <button type="button" class="portfolio-export-download portfolio-export-copy" data-action="copy-publish-post-launch-receipt" data-publish-evidence-post-launch-receipt-copy>post-launch receipt 복사</button>
              <small class="portfolio-export-status" data-publish-evidence-post-launch-receipt-copy-status aria-live="polite"></small>
            </div>
          `) : ""}
          ${launchProofEvidenceReceipt ? raw(html`
            <div class="publish-evidence-launch-proof-receipt" data-publish-evidence-launch-proof-receipt data-publish-evidence-launch-proof-field-count="${launchProofEvidenceDisplayFields.length}" data-publish-evidence-launch-proof-field-coverage="${launchProofEvidenceFieldCoverage}">
              <div>
                <span>Launch proof evidence receipt</span>
                <strong>${launchProofReady ? "proof review 가능" : "live proof 전 차단"}</strong>
              </div>
              <dl class="post-install-evidence-intake-fields">
                ${launchProofEvidenceDisplayFields.map((field) => raw(html`<div data-publish-evidence-launch-proof-field data-publish-evidence-launch-proof-field-label="${field.label || ""}" data-publish-evidence-launch-proof-field-next-action="${field.nextAction || ""}"><dt>${field.label || "Proof field"}</dt><dd>${field.value || "not available"}</dd><small>Next: ${field.nextAction || "not available"}</small></div>`))}
              </dl>
              <pre data-publish-evidence-launch-proof-receipt-text hidden>${launchProofEvidenceReceipt}</pre>
              <button type="button" class="portfolio-export-download portfolio-export-copy" data-action="copy-publish-launch-proof-receipt" data-publish-evidence-launch-proof-receipt-copy>launch proof receipt 복사</button>
              <small class="portfolio-export-status" data-publish-evidence-launch-proof-receipt-copy-status aria-live="polite"></small>
            </div>
          `) : ""}
          <dl class="storage-grid">
            <div><dt>source</dt><dd>${source?.source || "data/publish-evidence.json"}</dd></div>
            <div><dt>mode</dt><dd>${mode}</dd></div>
            <div><dt>displayRepo</dt><dd>${displayRepo || "not available"}</dd></div>
            <div><dt>evidenceRepo</dt><dd>${evidenceRepo || "not available"}</dd></div>
            <div><dt>repoResolution</dt><dd>${repoResolution || "not available"}</dd></div>
            <div><dt>repo</dt><dd>${data?.repo || "OWNER/REPO"}</dd></div>
            <div><dt>suggestedRepo</dt><dd>${suggestedRepo || "not available"}</dd></div>
            <div><dt>repoReplacementHint</dt><dd>${repoReplacementHint || "Replace OWNER/REPO with the exact GitHub owner/name repo"}</dd></div>
            <div><dt>generated</dt><dd>${generatedAt}</dd></div>
            <div><dt>expires</dt><dd>${evidenceExpiresAt}</dd></div>
            <div><dt>evidenceMaxAgeHours</dt><dd>${evidenceMaxAgeHours}</dd></div>
            <div><dt>evidenceFresh</dt><dd>${evidenceFresh ? "true" : "false"}</dd></div>
            <div><dt>launchProofReady</dt><dd>${launchProofReady ? "true" : "false"}</dd></div>
            <div><dt>postPublishEvidenceReady</dt><dd>${capturedReady ? "true" : "false"}</dd></div>
            <div><dt>repoEvidenceReady</dt><dd>${repoReady ? "true" : "false"}</dd></div>
            <div><dt>pagesEvidenceReady</dt><dd>${pagesReady ? "true" : "false"}</dd></div>
            <div><dt>workflowEvidenceReady</dt><dd>${workflowReady ? "true" : "false"}</dd></div>
            <div><dt>nextAction</dt><dd>${nextAction?.key || "not available"}</dd></div>
            <div><dt>immediateNextAction</dt><dd>${immediateNextAction?.key || "not available"}</dd></div>
            <div><dt>immediateCommandCount</dt><dd>${Number(immediateNextAction?.commandCount || 0)}</dd></div>
            <div><dt>deferredNextAction</dt><dd>${deferredNextAction?.key || "not available"}</dd></div>
            <div><dt>Pages URL</dt><dd>${pagesUrl ? raw(html`<a data-publish-evidence-pages-url href="${pagesUrl}" target="_blank" rel="noopener">${pagesUrl}</a>`) : "html_url 대기"}</dd></div>
            <div><dt>Pages run</dt><dd>${raw(publishWorkflowRunLink(data, "pages", "joopark-pages.yml"))}</dd></div>
            <div><dt>Drift run</dt><dd>${raw(publishWorkflowRunLink(data, "drift-watch", "joopark-drift-watch.yml"))}</dd></div>
          </dl>
          ${source?.error ? raw(html`<p class="settings-note storage-error">publish evidence load error: ${source.error}</p>`) : ""}
          ${blockers.length ? raw(html`
            <ul class="publish-evidence-blockers">
              ${blockers.map((blocker) => raw(html`<li>${blocker}</li>`))}
            </ul>
          `) : ""}
          <p class="settings-note">dispatch 후 <code>node scripts/capture-publish-evidence.mjs --live --repo OWNER/REPO --markdown</code>에서 <code>OWNER/REPO</code>를 실제 repo로 바꿔 공유용 보고서를 만들고 <code>--write</code>로 저장하면 이 패널이 <code>data/publish-evidence.json</code>에서 Pages URL과 repo-scoped workflow run 결과를 표시합니다. 저장된 evidence는 ${evidenceMaxAgeHours}시간 freshness window 안에서만 current proof로 표시됩니다. launch proof는 <code>repoEvidenceReady: true</code>, <code>evidenceFresh: true</code>, <code>postPublishEvidenceReady: true</code>가 모두 충족될 때만 준비됩니다.</p>
        </div>
      `;
    }

    function outputQualityAuditHTML(source) {
      const data = source?.data || null;
      const loaded = !!(source?.loaded && data);
      const criteria = loaded && Array.isArray(data.criteria) ? data.criteria : [];
      const promptChecklist = loaded && Array.isArray(data.promptToArtifactChecklist) ? data.promptToArtifactChecklist : [];
      const goalCompletionAudit = data?.goalCompletionAudit || {};
      const completionAudit = loaded && Array.isArray(data.completionAuditChecklist) ? data.completionAuditChecklist : [];
      const comparisons = loaded && Array.isArray(data.externalComparison) ? data.externalComparison : [];
      const blockers = loaded && Array.isArray(data.blockers) ? data.blockers : [];
      const receipt = data?.receipt || "";
      const gate = data?.latestGate || {};
      const checks = gate.checks || {};
      const snapshot = data?.outputReadinessSnapshot || {};
      const artifactRubric = data?.artifactQualityRubric || {};
      const artifactRubricItems = Array.isArray(artifactRubric.items) ? artifactRubric.items : [];
      const variantComparison = data?.outputVariantComparison || snapshot.outputVariantComparison || {};
      const variantComparisonItems = Array.isArray(variantComparison.variants) ? variantComparison.variants : [];
      const variantComparisonCriteria = Array.isArray(variantComparison.criteria) ? variantComparison.criteria : [];
      const trackerFormPayloads = snapshot.trackerFormPayloads || {};
      const issueDecisionSummary = snapshot.reviewIssueDecisionSummary || {};
      const commentNoteDecisionSummary = snapshot.reviewCommentNoteDecisionSummary || {};
      const repairActionPlan = snapshot.reviewResultRepairActionPlan || {};
      const submissionCloseoutSummary = snapshot.reviewPackageSubmissionCloseoutSummary || {};
      const runtimeIssues = snapshot.runtimeIssues || {};
      const copyReadyArtifacts = snapshot.copyReadyArtifacts || {};
      const publishCommandGuard = snapshot.publishEvidenceCommandGuard || {};
      const publishImmediateAction = snapshot.publishEvidenceImmediateNextAction || {};
      const workflowAuthPreflight = snapshot.workflowAuthPreflight || {};
      const launchPostAuthCheckpoint = snapshot.launchPostAuthCheckpoint || {};
      const workflowUiInstallReceipt = snapshot.workflowUiInstallReceipt || {};
      const handoffVerifierArtifact = snapshot.handoffVerifierArtifact || {};
      const mainBridgePlan = snapshot.mainBridgePlan || {};
      const postInstallEvidenceIntake = snapshot.postInstallEvidenceIntake || {};
      const launchProofEvidenceReceipt = snapshot.launchProofEvidenceReceipt || {};
      const launchAcceptance = snapshot.launchAcceptanceChecklist || {};
      const blockerResolution = snapshot.blockerResolutionChecklist || {};
      const launchInstallPaths = snapshot.launchInstallPaths || data?.launchInstallPathSnapshot || {};
      const launchInstallPathItems = Array.isArray(launchInstallPaths.paths) ? launchInstallPaths.paths : [];
      const launchInstallPathItemCommandCount = launchInstallPathItems.reduce(
        (total, item) => total + installPathItemCommandCount(item),
        0,
      );
      const launchInstallPathCount = finiteNumberOr(launchInstallPaths.count, launchInstallPathItems.length);
      const launchInstallPathCommandCount = finiteNumberOr(launchInstallPaths.commandCount, launchInstallPathItemCommandCount);
      const launchInstallInstallerCommand = launchInstallPaths.installerCommand || "node scripts/install-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write --verify";
      const executionState = data?.executionState || {};
      const sourceFreshness = data?.sourceEvidenceFreshness || {};
      const sourceFreshnessSources = Array.isArray(sourceFreshness.sources) ? sourceFreshness.sources : [];
      const generatedAt = data?.generatedAt ? formatLocalDateTime(data.generatedAt) : "대기 중";
      const releaseReady = !!data?.releaseQualityReady;
      const externalReady = !!data?.readyForExternalClaim;
      const launchPacketExternalReady = !!executionState.readyForExternalClaim;
      const sourceEvidenceFresh = !!data?.sourceEvidenceFresh;
      const sourceEvidenceStaleCount = finiteNumberOr(data?.sourceEvidenceStaleCount, sourceFreshness.staleCount || 0);
      const goalCompletionReady = !!goalCompletionAudit.ready;
      const goalCompletionBlockedCount = Number(goalCompletionAudit.blockedCount || 0);
      const completionAuditReady = !!data?.completionAuditReady;
      const completionAuditBlockedCount = Number(data?.completionAuditBlockedCount || 0);
      const externalClaimGuard = data?.externalClaimGuard || {};
      const externalClaimGuardRequirements = Array.isArray(externalClaimGuard.requirements) ? externalClaimGuard.requirements : [];
      const externalClaimGuardSignals = Array.isArray(externalClaimGuard.requiredSignals) ? externalClaimGuard.requiredSignals : [];
      const externalClaimGuardCommands = Array.isArray(externalClaimGuard.proofCommands) ? externalClaimGuard.proofCommands : [];
      const externalClaimGuardText = externalClaimGuard.text || "";
      const externalClaimGuardReady = !!externalClaimGuard.ready;
      const externalClaimGuardBlockedCount = finiteNumberOr(externalClaimGuard.blockedCount, 0);
      const externalClaimGuardRequirementCount = finiteNumberOr(externalClaimGuard.requirementCount, externalClaimGuardRequirements.length);
      const externalClaimCloseout = externalClaimGuard.closeoutPacket || {};
      const externalClaimCloseoutSteps = Array.isArray(externalClaimCloseout.steps) ? externalClaimCloseout.steps : [];
      const externalClaimCloseoutFields = Array.isArray(externalClaimCloseout.proofFields) ? externalClaimCloseout.proofFields : [];
      const externalClaimAllowedClaims = Array.isArray(externalClaimCloseout.allowedClaims) ? externalClaimCloseout.allowedClaims : [];
      const externalClaimForbiddenClaims = Array.isArray(externalClaimCloseout.forbiddenClaims) ? externalClaimCloseout.forbiddenClaims : [];
      const externalClaimCloseoutStepCount = finiteNumberOr(externalClaimCloseout.stepCount, externalClaimCloseoutSteps.length);
      const externalClaimCloseoutFieldCount = finiteNumberOr(externalClaimCloseout.proofFieldCount, externalClaimCloseoutFields.length);
      const externalClaimCloseoutAllowedCount = finiteNumberOr(externalClaimCloseout.allowedClaimCount, externalClaimAllowedClaims.length);
      const externalClaimCloseoutForbiddenCount = finiteNumberOr(externalClaimCloseout.forbiddenClaimCount, externalClaimForbiddenClaims.length);
      const publishState = data?.publishState || {};
      const resolvedRepo = publishState.repo || publishState.suggestedRepo || "";
      const evidenceRepo = publishState.evidenceRepo || "";
      const repoResolution = publishState.repoResolution || "";
      const repoPlaceholderResolved = !!publishState.repoPlaceholderResolved;
      const outputNextAction = data?.nextAction && typeof data.nextAction === "object" ? data.nextAction : {};
      const outputNextActionReady = !!outputNextAction.ready;
      const outputNextActionCommand = outputNextAction.command || "";
      const outputNextActionDeferredCommand = outputNextAction.deferredCommand || "";
      const stateLabel = externalReady ? "external claim ready" : releaseReady ? "quality ready; launch blocked" : "quality action required";
      return html`
        <div class="output-quality-audit" data-system-output-quality-audit data-output-quality-audit-source="${source?.source || "data/output-quality-audit.json"}" data-output-quality-audit-loaded="${loaded ? "true" : "false"}" data-output-quality-audit-release-ready="${releaseReady ? "true" : "false"}" data-output-quality-audit-external-ready="${externalReady ? "true" : "false"}" data-output-quality-audit-launch-packet-external-ready="${launchPacketExternalReady ? "true" : "false"}" data-output-quality-audit-source-evidence-fresh="${sourceEvidenceFresh ? "true" : "false"}" data-output-quality-audit-source-evidence-count="${sourceFreshnessSources.length}" data-output-quality-audit-source-evidence-stale-count="${sourceEvidenceStaleCount}" data-output-quality-audit-artifact-rubric-status="${artifactRubric.status || "unknown"}" data-output-quality-audit-artifact-rubric-score="${artifactRubric.totalScore || 0}" data-output-quality-audit-artifact-rubric-max-score="${artifactRubric.maxScore || 0}" data-output-quality-audit-artifact-rubric-passing-score="${artifactRubric.passingScore || 0}" data-output-quality-audit-artifact-rubric-item-count="${artifactRubricItems.length}" data-output-quality-audit-variant-status="${variantComparison.status || "unknown"}" data-output-quality-audit-variant-decision="${variantComparison.decision || ""}" data-output-quality-audit-variant-selected="${variantComparison.selectedVariant || ""}" data-output-quality-audit-variant-score="${variantComparison.winnerScore || 0}" data-output-quality-audit-variant-baseline-score="${variantComparison.baselineScore || 0}" data-output-quality-audit-variant-max-score="${variantComparison.maxScore || 0}" data-output-quality-audit-variant-count="${variantComparisonItems.length}" data-output-quality-audit-variant-criteria-count="${variantComparisonCriteria.length}" data-output-quality-audit-criteria-count="${criteria.length}" data-output-quality-audit-goal-count="${promptChecklist.length}" data-output-quality-audit-goal-ready="${goalCompletionReady ? "true" : "false"}" data-output-quality-audit-goal-blocked-count="${goalCompletionBlockedCount}" data-output-quality-audit-completion-count="${completionAudit.length}" data-output-quality-audit-completion-ready="${completionAuditReady ? "true" : "false"}" data-output-quality-audit-completion-blocked-count="${completionAuditBlockedCount}" data-output-quality-audit-external-claim-guard-ready="${externalClaimGuardReady ? "true" : "false"}" data-output-quality-audit-external-claim-guard-status="${externalClaimGuard.status || "not_available"}" data-output-quality-audit-external-claim-guard-blocked-count="${externalClaimGuardBlockedCount}" data-output-quality-audit-external-claim-guard-requirement-count="${externalClaimGuardRequirementCount}" data-output-quality-audit-external-claim-guard-command-count="${externalClaimGuardCommands.length}" data-output-quality-audit-comparison-count="${comparisons.length}" data-output-quality-audit-blocker-count="${blockers.length}" data-output-quality-audit-repo="${resolvedRepo}" data-output-quality-audit-evidence-repo="${evidenceRepo}" data-output-quality-audit-repo-resolution="${repoResolution}" data-output-quality-audit-repo-placeholder-resolved="${repoPlaceholderResolved ? "true" : "false"}" data-output-quality-audit-next-action-ready="${outputNextActionReady ? "true" : "false"}" data-output-quality-audit-next-action-key="${outputNextAction.key || ""}" data-output-quality-audit-next-action-status="${outputNextAction.status || ""}" data-output-quality-audit-next-action-source="${outputNextAction.source || ""}" data-output-quality-audit-next-action-command="${outputNextActionCommand}" data-output-quality-audit-next-action-deferred-key="${outputNextAction.deferredKey || ""}" data-output-quality-audit-next-action-deferred-command="${outputNextActionDeferredCommand}" data-output-quality-audit-snapshot-status="${snapshot.status || "unknown"}" data-output-quality-audit-review-ready="${snapshot.reviewPackageReadyToSubmit ? "true" : "false"}" data-output-quality-audit-issue-decision-summary="${issueDecisionSummary.ready ? "true" : "false"}" data-output-quality-audit-issue-decision-summary-fields="${issueDecisionSummary.fields || 0}" data-output-quality-audit-comment-note-decision-summary="${commentNoteDecisionSummary.ready ? "true" : "false"}" data-output-quality-audit-comment-note-decision-summary-fields="${commentNoteDecisionSummary.fields || 0}" data-output-quality-audit-repair-action-plan="${repairActionPlan.ready ? "true" : "false"}" data-output-quality-audit-repair-action-plan-fields="${repairActionPlan.fields || 0}" data-output-quality-audit-submission-closeout-summary="${submissionCloseoutSummary.ready ? "true" : "false"}" data-output-quality-audit-submission-closeout-summary-fields="${submissionCloseoutSummary.fields || 0}" data-output-quality-audit-tracker-form-payload-count="${trackerFormPayloads.count || 0}" data-output-quality-audit-tracker-form-payload-checksums="${trackerFormPayloads.checksumsReady ? "true" : "false"}" data-output-quality-audit-workflow-auth-preflight="${workflowAuthPreflight.ready ? "true" : "false"}" data-output-quality-audit-workflow-auth-preflight-ui-verified="${workflowAuthPreflight.uiVerified ? "true" : "false"}" data-output-quality-audit-workflow-auth-preflight-fields="${workflowAuthPreflight.fieldCoverage || 0}" data-output-quality-audit-workflow-auth-preflight-available="${workflowAuthPreflight.workflowScopeAvailable ? "true" : "false"}" data-output-quality-audit-workflow-auth-preflight-install-blocked="${workflowAuthPreflight.workflowScopeInstallBlocked ? "true" : "false"}" data-output-quality-audit-workflow-auth-preflight-scope-count="${workflowAuthPreflight.scopeCount || 0}" data-output-quality-audit-launch-post-auth-checkpoint="${launchPostAuthCheckpoint.ready ? "true" : "false"}" data-output-quality-audit-launch-post-auth-checkpoint-command-count="${launchPostAuthCheckpoint.commandCount || 0}" data-output-quality-audit-launch-post-auth-checkpoint-expected-count="${launchPostAuthCheckpoint.expectedSignalCount || 0}" data-output-quality-audit-launch-post-auth-checkpoint-blocked-count="${launchPostAuthCheckpoint.blockedSignalCount || 0}" data-output-quality-audit-launch-post-auth-checkpoint-recheck-count="${launchPostAuthCheckpoint.recheckSequenceCount || 0}" data-output-quality-audit-launch-post-auth-checkpoint-source-artifact-count="${launchPostAuthCheckpoint.sourceArtifactCount || 0}" data-output-quality-audit-launch-post-auth-checkpoint-dispatch-approval="${launchPostAuthCheckpoint.dispatchApproval ? "true" : "false"}" data-output-quality-audit-launch-post-auth-checkpoint-verification-only="${launchPostAuthCheckpoint.verificationOnly ? "true" : "false"}" data-output-quality-audit-launch-post-auth-checkpoint-verify-command="${launchPostAuthCheckpoint.verifyCommand || ""}" data-output-quality-audit-workflow-ui-install-receipt="${workflowUiInstallReceipt.ready ? "true" : "false"}" data-output-quality-audit-workflow-ui-install-receipt-command-count="${workflowUiInstallReceipt.commandCount || 0}" data-output-quality-audit-workflow-ui-install-receipt-checklist-count="${workflowUiInstallReceipt.checklistCount || 0}" data-output-quality-audit-workflow-ui-install-receipt-verify-command="${workflowUiInstallReceipt.verifyCommand || ""}" data-output-quality-audit-workflow-ui-install-paste-packet="${copyReadyArtifacts.workflowUiInstallPastePacket ? "true" : "false"}" data-output-quality-audit-workflow-ui-install-paste-packet-coverage="${workflowUiInstallReceipt.pastePacketCoverage || 0}" data-output-quality-audit-handoff-verifier-artifact="${handoffVerifierArtifact.ready ? "true" : "false"}" data-output-quality-audit-handoff-verifier-artifact-coverage="${handoffVerifierArtifact.artifactCoverage || 0}" data-output-quality-audit-handoff-verifier-safe-to-dispatch="${handoffVerifierArtifact.safeToDispatch ? "true" : "false"}" data-output-quality-audit-handoff-verifier-json-path="${handoffVerifierArtifact.jsonPath || ""}" data-output-quality-audit-handoff-verifier-markdown-path="${handoffVerifierArtifact.markdownPath || ""}" data-output-quality-audit-post-install-evidence-intake="${postInstallEvidenceIntake.ready ? "true" : "false"}" data-output-quality-audit-post-install-evidence-intake-source="${postInstallEvidenceIntake.source || ""}" data-output-quality-audit-post-install-evidence-intake-status="${postInstallEvidenceIntake.status || ""}" data-output-quality-audit-post-install-evidence-intake-fields="${postInstallEvidenceIntake.fields || 0}" data-output-quality-audit-post-install-evidence-intake-coverage="${postInstallEvidenceIntake.coverage || 0}" data-output-quality-audit-post-install-evidence-intake-completed-count="${postInstallEvidenceIntake.completedFieldCount || 0}" data-output-quality-audit-post-install-evidence-intake-proof-complete="${postInstallEvidenceIntake.proofComplete ? "true" : "false"}" data-output-quality-audit-post-install-evidence-intake-command-count="${postInstallEvidenceIntake.commandCount || 0}" data-output-quality-audit-post-install-evidence-intake-signal-count="${postInstallEvidenceIntake.signalCount || 0}" data-output-quality-audit-launch-proof-evidence-receipt="${launchProofEvidenceReceipt.ready ? "true" : "false"}" data-output-quality-audit-launch-proof-evidence-fields="${launchProofEvidenceReceipt.fields || 0}" data-output-quality-audit-launch-proof-evidence-coverage="${launchProofEvidenceReceipt.coverage || 0}" data-output-quality-audit-publish-evidence-command-guard="${publishCommandGuard.ready ? "true" : "false"}" data-output-quality-audit-publish-evidence-immediate-action="${publishImmediateAction.ready ? "true" : "false"}" data-output-quality-audit-publish-evidence-immediate-action-key="${publishImmediateAction.key || ""}" data-output-quality-audit-publish-evidence-suggested-dispatch-count="${publishCommandGuard.suggestedDispatchCommands || 0}" data-output-quality-audit-publish-evidence-withheld-dispatch-count="${publishCommandGuard.withheldDispatchCommands || 0}" data-output-quality-audit-launch-acceptance-total="${launchAcceptance.total || 0}" data-output-quality-audit-launch-acceptance-pass="${launchAcceptance.pass || 0}" data-output-quality-audit-launch-acceptance-pending="${launchAcceptance.pending || 0}" data-output-quality-audit-launch-acceptance-stage="${launchAcceptance.stageKey || ""}" data-output-quality-audit-blocker-resolution="${blockerResolution.ready ? "true" : "false"}" data-output-quality-audit-blocker-resolution-active="${blockerResolution.activeItemKey || ""}" data-output-quality-audit-blocker-resolution-item-count="${blockerResolution.itemCount || 0}" data-output-quality-audit-blocker-resolution-action-required-count="${blockerResolution.actionRequiredCount || 0}" data-output-quality-audit-blocker-resolution-deferred-count="${blockerResolution.deferredCount || 0}" data-output-quality-audit-blocker-resolution-proof-command-count="${blockerResolution.proofCommandCount || 0}" data-output-quality-audit-install-paths-ready="${launchInstallPaths.ready ? "true" : "false"}" data-output-quality-audit-install-path-count="${launchInstallPathCount}" data-output-quality-audit-install-path-command-count="${launchInstallPathCommandCount}">
          <div class="publish-evidence-head">
            <strong>Final output quality audit</strong>
            <span class="publish-state" data-output-quality-audit-state-label>${stateLabel}</span>
          </div>
          <p class="settings-note">최종 산출물이 단순 생성물이 아니라 바로 복사·제출·공유 가능한지 기준별로 압축한 receipt입니다. Public launch proof가 막혀 있으면 외부 출시 완료 문구로 쓰지 않습니다.</p>
          ${outputNextAction.key ? raw(html`
            <section class="publish-evidence-next-action output-quality-next-action" data-output-quality-audit-next-action data-output-quality-audit-next-action-ready="${outputNextActionReady ? "true" : "false"}" data-output-quality-audit-next-action-key="${outputNextAction.key || ""}" data-output-quality-audit-next-action-status="${outputNextAction.status || ""}" data-output-quality-audit-next-action-source="${outputNextAction.source || ""}" data-output-quality-audit-next-action-command="${outputNextActionCommand}" data-output-quality-audit-next-action-deferred-key="${outputNextAction.deferredKey || ""}" data-output-quality-audit-next-action-deferred-command="${outputNextActionDeferredCommand}">
              <span>Structured next action</span>
              <strong>${outputNextAction.label || outputNextAction.key}</strong>
              <p>${outputNextAction.successCondition ? `Success condition: ${outputNextAction.successCondition}` : outputNextAction.detail || outputNextAction.guard || "Keep public launch claims blocked until proof is complete."}</p>
              <code>${outputNextActionCommand || "not available"}</code>
              ${outputNextActionDeferredCommand ? raw(html`<small>Deferred: ${outputNextAction.deferredLabel || outputNextAction.deferredKey} · ${outputNextActionDeferredCommand}</small>`) : ""}
            </section>
          `) : ""}
          <dl class="storage-grid">
            <div><dt>source</dt><dd>${source?.source || "data/output-quality-audit.json"}</dd></div>
            <div><dt>generated</dt><dd>${generatedAt}</dd></div>
            <div><dt>repo</dt><dd>${resolvedRepo || "not available"}</dd></div>
            <div><dt>evidence repo</dt><dd>${evidenceRepo || "not available"}</dd></div>
            <div><dt>repo resolution</dt><dd>${repoResolution || "not available"}</dd></div>
            <div><dt>latest gate</dt><dd>${gate.command || "npm run verify"}</dd></div>
            <div><dt>checks</dt><dd>${checks.pass || 0} pass · ${checks.fail || 0} fail · ${checks.notRun || 0} not_run · ${checks.blocked || 0} blocked</dd></div>
            <div><dt>releaseQualityReady</dt><dd>${releaseReady ? "true" : "false"}</dd></div>
            <div><dt>launchPacketReadyForExternalClaim</dt><dd>${launchPacketExternalReady ? "true" : "false"}</dd></div>
            <div><dt>readyForExternalClaim</dt><dd>${externalReady ? "true" : "false"}</dd></div>
            <div><dt>sourceEvidenceFresh</dt><dd>${sourceEvidenceFresh ? "true" : "false"}</dd></div>
            <div><dt>sourceEvidenceStale</dt><dd>${sourceEvidenceStaleCount}</dd></div>
            <div><dt>artifactQualityRubric</dt><dd>${artifactRubric.status || "unknown"} · ${artifactRubric.totalScore || 0}/${artifactRubric.maxScore || 0}</dd></div>
            <div><dt>outputVariantComparison</dt><dd>${variantComparison.decision || "unknown"} · ${variantComparison.selectedVariant || "not selected"}</dd></div>
            <div><dt>goalCompletionAudit</dt><dd>${goalCompletionAudit.status || "unknown"} · ${goalCompletionAudit.passCount || 0}/${goalCompletionAudit.total || 0}</dd></div>
            <div><dt>completionAuditReady</dt><dd>${completionAuditReady ? "true" : "false"}</dd></div>
            <div><dt>completionAuditBlocked</dt><dd>${completionAuditBlockedCount}</dd></div>
            <div><dt>externalComparison</dt><dd>${comparisons.length}</dd></div>
          </dl>
          ${source?.error ? raw(html`<p class="settings-note storage-error">output quality audit load error: ${source.error}</p>`) : ""}
          ${sourceFreshnessSources.length ? raw(html`
            <ul class="output-quality-source-freshness" data-output-quality-audit-source-freshness>
              ${sourceFreshnessSources.map((item) => raw(html`<li data-output-quality-audit-source-freshness-item data-output-quality-audit-source-freshness-key="${item.key}" data-output-quality-audit-source-freshness-status="${item.status}"><strong>${item.label}</strong><span>${item.status}</span><p>${item.path} · age ${item.ageHours ?? "unknown"}h / ${item.maxAgeHours}h</p></li>`))}
            </ul>
          `) : ""}
          ${loaded ? raw(html`
            <ul class="output-quality-snapshot" data-output-quality-audit-snapshot>
              <li data-output-quality-audit-snapshot-item data-output-quality-audit-snapshot-key="review-package"><strong>Review package</strong><span>${snapshot.reviewPackageReadyToSubmit ? "ready" : "check"}</span><p>Final quality ${snapshot.reviewPackageFinalQualityScore || "pending"}</p></li>
              <li data-output-quality-audit-snapshot-item data-output-quality-audit-snapshot-key="review-decision-summaries"><strong>Review decision summaries</strong><span>${issueDecisionSummary.ready && commentNoteDecisionSummary.ready ? "pass" : "check"}</span><p>issue ${issueDecisionSummary.fields || 0} fields · comment/note ${commentNoteDecisionSummary.fields || 0} fields · coverage ${commentNoteDecisionSummary.coverage || 0}</p></li>
              <li data-output-quality-audit-snapshot-item data-output-quality-audit-snapshot-key="review-repair-action-plan"><strong>Review repair action plan</strong><span>${repairActionPlan.ready ? "pass" : "check"}</span><p>${repairActionPlan.fields || 0} fields · coverage ${repairActionPlan.coverage || 0}</p></li>
              <li data-output-quality-audit-snapshot-item data-output-quality-audit-snapshot-key="submission-closeout-summary"><strong>Submission closeout summary</strong><span>${submissionCloseoutSummary.ready ? "pass" : "check"}</span><p>${submissionCloseoutSummary.fields || 0} fields · coverage ${submissionCloseoutSummary.coverage || 0}</p></li>
              <li data-output-quality-audit-snapshot-item data-output-quality-audit-snapshot-key="tracker-form-payloads"><strong>Tracker form payloads</strong><span>${trackerFormPayloads.ready ? "pass" : "check"}</span><p>${trackerFormPayloads.count || 0} fields · checksums ${trackerFormPayloads.checksumsReady ? "ready" : "pending"}</p></li>
              <li data-output-quality-audit-snapshot-item data-output-quality-audit-snapshot-key="runtime-issues"><strong>Runtime issues</strong><span>${(runtimeIssues.console || 0) + (runtimeIssues.network || 0) + (runtimeIssues.layout || 0) === 0 ? "clear" : "check"}</span><p>console ${runtimeIssues.console || 0} · network ${runtimeIssues.network || 0} · layout ${runtimeIssues.layout || 0}</p></li>
              <li data-output-quality-audit-snapshot-item data-output-quality-audit-snapshot-key="workflow-auth-preflight"><strong>Workflow auth preflight</strong><span>${workflowAuthPreflight.ready ? "pass" : "check"}</span><p>ui ${workflowAuthPreflight.uiVerified ? "verified" : "pending"} · workflowScopeAvailable=${workflowAuthPreflight.workflowScopeAvailable ? "true" : "false"} · workflowScopeInstallBlocked=${workflowAuthPreflight.workflowScopeInstallBlocked ? "true" : "false"} · missing ${workflowAuthPreflight.missingScopeList || "none"} · scopes ${workflowAuthPreflight.scopeList || "not checked"}</p></li>
              <li data-output-quality-audit-snapshot-item data-output-quality-audit-snapshot-key="launch-post-auth-checkpoint"><strong>Launch post-auth checkpoint</strong><span>${launchPostAuthCheckpoint.ready ? "pass" : "check"}</span><p>${launchPostAuthCheckpoint.commandCount || 0} commands · expected ${launchPostAuthCheckpoint.expectedSignalCount || 0} · blocked ${launchPostAuthCheckpoint.blockedSignalCount || 0} · recheck ${launchPostAuthCheckpoint.recheckSequenceCount || 0} · sources ${launchPostAuthCheckpoint.sourceArtifactCount || 0} · dispatchApproval=${launchPostAuthCheckpoint.dispatchApproval ? "true" : "false"} · verificationOnly=${launchPostAuthCheckpoint.verificationOnly ? "true" : "false"} · verify ${launchPostAuthCheckpoint.verifyCommand || "not available"} · guard ${launchPostAuthCheckpoint.guard || "not available"}</p></li>
              <li data-output-quality-audit-snapshot-item data-output-quality-audit-snapshot-key="workflow-ui-install-receipt"><strong>Workflow UI paste packet</strong><span>${workflowUiInstallReceipt.ready ? "pass" : "check"}</span><p>workflowUiInstallPastePacketCoverage=${workflowUiInstallReceipt.pastePacketCoverage || 0} · ${workflowUiInstallReceipt.commandCount || 0} commands · checklist ${workflowUiInstallReceipt.checklistCount || 0} · verify ${workflowUiInstallReceipt.verifyCommand || "not available"}</p></li>
              <li data-output-quality-audit-snapshot-item data-output-quality-audit-snapshot-key="handoff-verifier-artifact"><strong>Launch handoff verifier artifact</strong><span>${handoffVerifierArtifact.ready ? "pass" : "check"}</span><p>artifactCoverage=${handoffVerifierArtifact.artifactCoverage || 0} · safeToDispatch=${handoffVerifierArtifact.safeToDispatch ? "true" : "false"} · json ${handoffVerifierArtifact.jsonPath || "not available"} · markdown ${handoffVerifierArtifact.markdownPath || "not available"}</p></li>
              <li data-output-quality-audit-snapshot-item data-output-quality-audit-snapshot-key="main-bridge-plan"><strong>Main PR bridge plan</strong><span>${mainBridgePlan.ready ? "pass" : "check"}</span><p>strategy=${mainBridgePlan.strategy || "not available"} · noCommonHistory=${mainBridgePlan.noCommonHistory ? "true" : "false"} · branch ${mainBridgePlan.bridgeBranch || "not available"} · commands ${mainBridgePlan.commandCount || 0}</p></li>
              <li data-output-quality-audit-snapshot-item data-output-quality-audit-snapshot-key="post-install-evidence-intake"><strong>Post-install evidence intake</strong><span>${postInstallEvidenceIntake.ready ? "pass" : "check"}</span><p>${postInstallEvidenceIntake.fields || 0} fields · coverage ${postInstallEvidenceIntake.coverage || 0} · completed ${postInstallEvidenceIntake.completedFieldCount || 0}/${postInstallEvidenceIntake.fields || 0} · proofComplete ${postInstallEvidenceIntake.proofComplete ? "true" : "false"} · commands ${postInstallEvidenceIntake.commandCount || 0}</p></li>
              <li data-output-quality-audit-snapshot-item data-output-quality-audit-snapshot-key="launch-proof-evidence-receipt"><strong>Launch proof evidence receipt</strong><span>${launchProofEvidenceReceipt.ready ? "pass" : "check"}</span><p>${launchProofEvidenceReceipt.fields || 0} fields · coverage ${launchProofEvidenceReceipt.coverage || 0}</p></li>
              <li data-output-quality-audit-snapshot-item data-output-quality-audit-snapshot-key="launch-acceptance-checklist"><strong>Launch acceptance checklist</strong><span>${launchAcceptance.pending === 0 && launchAcceptance.total ? "pass" : "pending"}</span><p>${launchAcceptance.pass || 0}/${launchAcceptance.total || 0} pass · ${launchAcceptance.pending || 0} pending · stage ${launchAcceptance.stageKey || "not available"}</p></li>
              <li data-output-quality-audit-snapshot-item data-output-quality-audit-snapshot-key="blocker-resolution-checklist" data-output-quality-audit-blocker-resolution-guard="${blockerResolution.guard || ""}"><strong>Blocker resolution checklist</strong><span>${blockerResolution.ready ? "pass" : "check"}</span><p>active ${blockerResolution.activeItemKey || "not available"} · ${blockerResolution.passCount || 0}/${blockerResolution.itemCount || 0} pass · actionRequired ${blockerResolution.actionRequiredCount || 0} · deferred ${blockerResolution.deferredCount || 0} · proofCommands ${blockerResolution.proofCommandCount || 0} · guard ${blockerResolution.guard || "not available"}</p></li>
              <li data-output-quality-audit-snapshot-item data-output-quality-audit-snapshot-key="launch-install-path-options"><strong>Launch install path options</strong><span>${launchInstallPaths.ready ? "pass" : "check"}</span><p>${launchInstallPathCount} paths · ${launchInstallPathCommandCount} commands · ${(launchInstallPaths.labels || []).join(" | ") || "labels pending"} · installer ${launchInstallInstallerCommand}</p></li>
              <li data-output-quality-audit-snapshot-item data-output-quality-audit-snapshot-key="publish-evidence-command-guard"><strong>Publish evidence command guard</strong><span>${publishCommandGuard.ready ? "pass" : "check"}</span><p>${publishCommandGuard.suggestedVerificationCommands || 0} safe suggestions · ${publishCommandGuard.suggestedDispatchCommands || 0} suggested dispatch · ${publishCommandGuard.withheldDispatchCommands || 0} withheld dispatch</p></li>
              <li data-output-quality-audit-snapshot-item data-output-quality-audit-snapshot-key="publish-evidence-immediate-action"><strong>Publish evidence immediate action</strong><span>${publishImmediateAction.ready ? "pass" : "check"}</span><p>${publishImmediateAction.key || "pending"} from ${publishImmediateAction.source || "not available"} · deferred ${publishImmediateAction.deferredKey || "not available"}</p></li>
              <li data-output-quality-audit-snapshot-item data-output-quality-audit-snapshot-key="copy-ready-artifacts"><strong>Copy-ready artifacts</strong><span>${copyReadyArtifacts.launchExecutionPacket && copyReadyArtifacts.workflowUiInstallPastePacket && copyReadyArtifacts.handoffVerifierArtifact && copyReadyArtifacts.mainBridgePlan && copyReadyArtifacts.operatorOnePageHandoff ? "ready" : "check"}</span><p>share/update/launch/receipt packet evidence retained · workflow UI paste packet ${copyReadyArtifacts.workflowUiInstallPastePacket ? "ready" : "pending"} · handoff verifier artifact ${copyReadyArtifacts.handoffVerifierArtifact ? "ready" : "pending"} · main bridge plan ${copyReadyArtifacts.mainBridgePlan ? "ready" : "pending"} · operator one-page ${copyReadyArtifacts.operatorOnePageHandoff ? "ready" : "pending"}</p></li>
            </ul>
          `) : ""}
          ${launchInstallPathItems.length ? raw(html`
            <ul class="output-quality-snapshot" data-output-quality-audit-install-paths>
              ${launchInstallPathItems.map((item) => raw(html`<li data-output-quality-audit-install-path-item data-output-quality-audit-install-path-key="${item.key || ""}"><strong>${item.label || "Install path"}</strong><span>${installPathItemCommandCount(item)} commands</span><p>${item.when || ""} ${Array.isArray(item.commands) ? item.commands.join(" | ") : ""}</p></li>`))}
            </ul>
          `) : ""}
          ${criteria.length ? raw(html`
            <ul class="output-quality-criteria" data-output-quality-audit-criteria>
              ${criteria.map((item) => raw(html`<li data-output-quality-criterion data-output-quality-criterion-key="${item.key}" data-output-quality-criterion-status="${item.status}"><strong>${item.label}</strong><span>${item.status}</span><p>${item.detail}</p></li>`))}
            </ul>
          `) : ""}
          ${artifactRubricItems.length ? raw(html`
            <section class="output-quality-completion" data-output-quality-audit-artifact-rubric>
              <strong>Artifact quality rubric</strong>
              <p class="settings-note">Score ${artifactRubric.totalScore || 0}/${artifactRubric.maxScore || 0} · pass threshold ${artifactRubric.passingScore || 0} · ${artifactRubric.externalBaseline || "external baseline pending"}</p>
              <ul class="output-quality-criteria">
                ${artifactRubricItems.map((item) => raw(html`<li data-output-quality-audit-artifact-rubric-item data-output-quality-audit-artifact-rubric-key="${item.key}" data-output-quality-audit-artifact-rubric-status="${item.status}" data-output-quality-audit-artifact-rubric-score="${item.score || 0}" data-output-quality-audit-artifact-rubric-weight="${item.weight || 0}"><strong>${item.label}</strong><span>${item.status} · ${item.score || 0}/${item.weight || 0}</span><p>${item.detail}</p></li>`))}
              </ul>
            </section>
          `) : ""}
          ${variantComparisonItems.length ? raw(html`
            <section class="output-quality-completion" data-output-quality-audit-variant-comparison data-output-quality-audit-variant-status="${variantComparison.status || "unknown"}" data-output-quality-audit-variant-decision="${variantComparison.decision || ""}" data-output-quality-audit-variant-selected="${variantComparison.selectedVariant || ""}">
              <strong>Output variant comparison</strong>
              <p class="settings-note">${variantComparison.conclusion || "Candidate comparison pending."}</p>
              <ul class="output-quality-criteria" data-output-quality-audit-variant-list>
                ${variantComparisonItems.map((item) => raw(html`<li data-output-quality-audit-variant-item data-output-quality-audit-variant-key="${item.key || ""}" data-output-quality-audit-variant-item-status="${item.status || ""}"><strong>${item.label || item.key}</strong><span>${item.status || "unknown"} · ${item.score || 0}/${item.maxScore || 0}</span><p>${item.detail || ""}</p></li>`))}
              </ul>
              <ul class="output-quality-criteria" data-output-quality-audit-variant-criteria>
                ${variantComparisonCriteria.map((item) => raw(html`<li data-output-quality-audit-variant-criterion data-output-quality-audit-variant-criterion-key="${item.key || ""}" data-output-quality-audit-variant-criterion-winner="${item.winner || ""}"><strong>${item.label || item.key}</strong><span>winner ${item.winner || "unknown"}</span><p>${item.evidence || ""}</p></li>`))}
              </ul>
            </section>
          `) : ""}
          ${externalClaimGuardText ? raw(html`
            <section class="output-quality-external-claim-guard" data-output-quality-audit-external-claim-guard data-output-quality-audit-external-claim-guard-ready="${externalClaimGuardReady ? "true" : "false"}" data-output-quality-audit-external-claim-guard-status="${externalClaimGuard.status || "not_available"}" data-output-quality-audit-external-claim-guard-blocked-count="${externalClaimGuardBlockedCount}" data-output-quality-audit-external-claim-guard-requirement-count="${externalClaimGuardRequirementCount}" data-output-quality-audit-external-claim-guard-command-count="${externalClaimGuardCommands.length}">
              <div>
                <span>External completion claim guard</span>
                <strong>${externalClaimGuardReady ? "외부 완료 주장 가능" : "외부 완료 주장 차단"}</strong>
                <p>${externalClaimGuard.status || "not_available"} · blocked ${externalClaimGuardBlockedCount}/${externalClaimGuardRequirementCount}</p>
              </div>
              <ul class="output-quality-criteria" data-output-quality-audit-external-claim-guard-requirements>
                ${externalClaimGuardRequirements.map((item) => raw(html`<li data-output-quality-audit-external-claim-guard-item data-output-quality-audit-external-claim-guard-key="${item.key}" data-output-quality-audit-external-claim-guard-item-status="${item.status}"><strong>${item.label}</strong><span>${item.status}</span><p>${item.detail}${Array.isArray(item.missing) && item.missing.length ? ` Missing: ${item.missing.join("; ")}` : ""}</p></li>`))}
              </ul>
              <div class="output-quality-external-claim-guard-signals" data-output-quality-audit-external-claim-guard-signals>
                ${externalClaimGuardSignals.map((signal) => raw(html`<span data-output-quality-audit-external-claim-guard-signal>${signal}</span>`))}
              </div>
              <div class="output-quality-external-claim-guard-commands" data-output-quality-audit-external-claim-guard-commands>
                ${externalClaimGuardCommands.map((command) => raw(html`<code data-output-quality-audit-external-claim-guard-command>${command}</code>`))}
              </div>
              ${externalClaimCloseout.text ? raw(html`
                <section class="output-quality-completion" data-output-quality-audit-external-claim-closeout data-output-quality-audit-external-claim-closeout-ready="${externalClaimCloseout.ready ? "true" : "false"}" data-output-quality-audit-external-claim-closeout-status="${externalClaimCloseout.status || "unknown"}" data-output-quality-audit-external-claim-closeout-step-count="${externalClaimCloseoutStepCount}" data-output-quality-audit-external-claim-closeout-field-count="${externalClaimCloseoutFieldCount}" data-output-quality-audit-external-claim-closeout-allowed-count="${externalClaimCloseoutAllowedCount}" data-output-quality-audit-external-claim-closeout-forbidden-count="${externalClaimCloseoutForbiddenCount}">
                  <strong>External claim closeout packet</strong>
                  <p class="settings-note">default branch workflow_dispatch, workflow run summary, and Release-note archive claim proof fields required before external completion claims.</p>
                  <ol class="output-quality-criteria" data-output-quality-audit-external-claim-closeout-steps>
                    ${externalClaimCloseoutSteps.map((step) => raw(html`<li data-output-quality-audit-external-claim-closeout-step data-output-quality-audit-external-claim-closeout-step-key="${step.key || ""}"><strong>${step.label || step.key}</strong><span>${step.command || ""}</span><p>${step.detail || ""}</p></li>`))}
                  </ol>
                  <ul class="output-quality-criteria" data-output-quality-audit-external-claim-closeout-fields>
                    ${externalClaimCloseoutFields.map((field) => raw(html`<li data-output-quality-audit-external-claim-closeout-field data-output-quality-audit-external-claim-closeout-field-key="${field.key || ""}"><strong>${field.label || field.key}</strong><span>${field.current || ""}</span><p>Expected: ${field.expected || ""}</p></li>`))}
                  </ul>
                  <div class="output-quality-external-claim-guard-signals" data-output-quality-audit-external-claim-closeout-claims>
                    ${externalClaimAllowedClaims.map((claim) => raw(html`<span data-output-quality-audit-external-claim-closeout-allowed>${claim}</span>`))}
                    ${externalClaimForbiddenClaims.map((claim) => raw(html`<span data-output-quality-audit-external-claim-closeout-forbidden>${claim}</span>`))}
                  </div>
                </section>
              `) : ""}
              <p class="settings-note" data-output-quality-audit-external-claim-guard-stop>${externalClaimGuard.stopCondition || ""}</p>
              <pre data-output-quality-audit-external-claim-guard-text hidden>${externalClaimGuardText}</pre>
              <button type="button" class="portfolio-export-download portfolio-export-copy" data-action="copy-output-quality-external-claim-guard" data-output-quality-audit-external-claim-guard-copy>external claim guard 복사</button>
              <small class="portfolio-export-status" data-output-quality-audit-external-claim-guard-copy-status aria-live="polite"></small>
            </section>
          `) : ""}
          ${promptChecklist.length ? raw(html`
            <section class="output-quality-completion" data-output-quality-audit-goal-completion data-output-quality-audit-goal-status="${goalCompletionAudit.status || "unknown"}" data-output-quality-audit-goal-ready="${goalCompletionReady ? "true" : "false"}" data-output-quality-audit-goal-blocked-count="${goalCompletionBlockedCount}">
              <strong>Prompt-to-artifact checklist</strong>
              <p class="settings-note">사용자 목표 1-7번을 실제 copy-ready 산출물, audit evidence, 외부 기준, 반복 개선 로그에 매핑합니다.</p>
              <ul class="output-quality-criteria" data-output-quality-audit-goal-checklist>
                ${promptChecklist.map((item) => raw(html`<li data-output-quality-audit-goal-item data-output-quality-audit-goal-key="${item.key}" data-output-quality-audit-goal-status="${item.status}"><strong>${item.label}</strong><span>${item.status}</span><p>${item.artifact} · ${item.improvement}${Array.isArray(item.missing) && item.missing.length ? ` Missing: ${item.missing.join("; ")}` : ""}</p></li>`))}
              </ul>
            </section>
          `) : ""}
          ${completionAudit.length ? raw(html`
            <section class="output-quality-completion" data-output-quality-audit-completion>
              <strong>Completion audit</strong>
              <ul class="output-quality-criteria" data-output-quality-audit-completion-checklist>
                ${completionAudit.map((item) => raw(html`<li data-output-quality-audit-completion-item data-output-quality-audit-completion-key="${item.key}" data-output-quality-audit-completion-status="${item.status}"><strong>${item.label}</strong><span>${item.status}</span><p>${item.detail}${Array.isArray(item.missing) && item.missing.length ? ` Missing: ${item.missing.join("; ")}` : ""}</p></li>`))}
              </ul>
            </section>
          `) : ""}
          ${comparisons.length ? raw(html`
            <ul class="output-quality-comparison" data-output-quality-audit-comparison>
              ${comparisons.map((item) => raw(html`<li data-output-quality-comparison-item data-output-quality-comparison-key="${item.key}"><a href="${item.url}" target="_blank" rel="noopener">${item.label}</a><p>${item.detail}</p></li>`))}
            </ul>
          `) : ""}
          ${blockers.length ? raw(html`
            <ul class="publish-evidence-blockers" data-output-quality-audit-blockers>
              ${blockers.map((blocker) => raw(html`<li>${blocker}</li>`))}
            </ul>
          `) : ""}
          ${receipt ? raw(html`
            <div class="output-quality-receipt" data-output-quality-audit-receipt>
              <div>
                <span>Copy-ready receipt</span>
                <strong>${externalReady ? "외부 공유 가능" : "내부 품질 증거용"}</strong>
              </div>
              <pre data-output-quality-audit-receipt-text hidden>${receipt}</pre>
              <button type="button" class="portfolio-export-download portfolio-export-copy" data-action="copy-output-quality-audit-receipt" data-output-quality-audit-receipt-copy>quality receipt 복사</button>
              <small class="portfolio-export-status" data-output-quality-audit-receipt-copy-status aria-live="polite"></small>
            </div>
          `) : ""}
        </div>
      `;
    }

    return Object.freeze({
      version: VERSION,
      publishReadinessItems,
      publishReadinessStateLabel,
      publishReadinessMarkdownLines,
      publishRepoPlaceholderGuardLines,
      publishDispatchGateGuardLines,
      publishUnblockHandoffText,
      publishReadinessListHTML,
      workflowUiInstallPlanHTML,
      publishDispatchPlanHTML,
      remoteWorkflowFileCheckHTML,
      launchExecutionPacketHTML,
      launchReadinessRefreshHTML,
      verifyWorkspaceSummaryHTML,
      releaseGateCacheHTML,
      releaseProvenanceHTML,
      pagesAttestationProofIntakeHTML,
      publishEvidenceFresh,
      publishEvidenceHTML,
      outputQualityAuditHTML,
    });
  }

  global.JooParkReleaseStatus = Object.freeze({
    version: VERSION,
    create: createReleaseStatus,
    readinessItems: Object.freeze(READINESS_ITEMS.map(cloneItem)),
  });
})(typeof window !== "undefined" ? window : globalThis);
