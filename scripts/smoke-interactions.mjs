#!/usr/bin/env node

import { spawn } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const chromePath = process.env.CHROME_PATH || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const baseUrl = (process.env.BASE_URL || "http://127.0.0.1:5178").replace(/\/+$/, "");
const tmpProfile = mkdtempSync(join(tmpdir(), "joopark-interaction-smoke-"));
const progressEnabled = process.env.SMOKE_PROGRESS === "1";
const verifyWorkspaceSummaryStrict = process.env.SMOKE_VERIFY_WORKSPACE_SUMMARY_STRICT === "1";
const legacyLaunchMetaSmokeEnabled = process.env.SMOKE_LEGACY_LAUNCH_META === "1";
const defaultCdpTimeoutMs = 10000;
const defaultEvaluateTimeoutMs = positiveMsOption(process.env.SMOKE_RUNTIME_TIMEOUT_MS, 60000);
const longScenarioEvaluateTimeoutMs = positiveMsOption(process.env.SMOKE_LONG_SCENARIO_TIMEOUT_MS || process.env.SMOKE_RUNTIME_TIMEOUT_MS, 300000);
const resetScenarioEvaluateTimeoutMs = 60000;

function positiveMsOption(value, fallback) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) return fallback;
  return parsed;
}

class CdpClient {
  constructor(wsUrl) {
    this.wsUrl = wsUrl;
    this.nextId = 1;
    this.pending = new Map();
    this.listeners = new Map();
  }

  async open() {
    this.ws = new WebSocket(this.wsUrl);
    this.ws.addEventListener("message", (event) => this.handleMessage(event.data));
    await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error("Timed out opening CDP websocket")), 8000);
      this.ws.addEventListener("open", () => {
        clearTimeout(timer);
        resolve();
      }, { once: true });
      this.ws.addEventListener("error", () => {
        clearTimeout(timer);
        reject(new Error(`Failed to open CDP websocket: ${this.wsUrl}`));
      }, { once: true });
    });
  }

  on(method, callback) {
    const callbacks = this.listeners.get(method) || [];
    callbacks.push(callback);
    this.listeners.set(method, callbacks);
  }

  handleMessage(data) {
    const message = JSON.parse(String(data));
    if (message.id && this.pending.has(message.id)) {
      const { resolve, reject, timer } = this.pending.get(message.id);
      this.pending.delete(message.id);
      clearTimeout(timer);
      if (message.error) reject(new Error(`${message.error.message || "CDP error"} (${message.error.code || "no-code"})`));
      else resolve(message.result || {});
      return;
    }
    const callbacks = this.listeners.get(message.method) || [];
    callbacks.forEach((callback) => callback(message.params || {}));
  }

  send(method, params = {}, timeoutMs = defaultCdpTimeoutMs) {
    const id = this.nextId++;
    this.ws.send(JSON.stringify({ id, method, params }));
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        if (!this.pending.has(id)) return;
        this.pending.delete(id);
        reject(new Error(`Timed out waiting for ${method} after ${timeoutMs}ms`));
      }, timeoutMs);
      this.pending.set(id, {
        resolve: (value) => {
          clearTimeout(timer);
          resolve(value);
        },
        reject: (error) => {
          clearTimeout(timer);
          reject(error);
        },
      });
    });
  }

  close() {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) this.ws.close();
  }
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function progress(event, extra = {}) {
  if (!progressEnabled) return;
  console.error(JSON.stringify({ event, ...extra }));
}

function cleanupTmpProfile() {
  try {
    rmSync(tmpProfile, { recursive: true, force: true, maxRetries: 5, retryDelay: 100 });
  } catch (error) {
    progress("cleanup-profile-warning", { message: error.message });
  }
}

function waitForProcessExit(child, timeoutMs) {
  if (!child || child.exitCode !== null || child.signalCode !== null) return Promise.resolve(true);
  return new Promise((resolve) => {
    const timer = setTimeout(() => resolve(false), timeoutMs);
    child.once("exit", () => {
      clearTimeout(timer);
      resolve(true);
    });
  });
}

async function terminateProcess(child) {
  if (!child || child.exitCode !== null || child.signalCode !== null) return;
  child.kill("SIGTERM");
  const exited = await waitForProcessExit(child, 1500);
  if (exited) return;
  child.kill("SIGKILL");
  await waitForProcessExit(child, 1500);
}

async function waitForDevTools(chrome) {
  let stderr = "";
  return await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`Timed out waiting for DevTools endpoint.\n${stderr}`)), 12000);
    chrome.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
      const match = stderr.match(/DevTools listening on (ws:\/\/[^\s]+)/);
      if (match) {
        clearTimeout(timer);
        resolve(match[1]);
      }
    });
    chrome.on("exit", (code) => {
      clearTimeout(timer);
      reject(new Error(`Chrome exited before DevTools endpoint was ready: ${code}\n${stderr}`));
    });
  });
}

async function pageWebSocketUrl(browserWsUrl) {
  const { port } = new URL(browserWsUrl);
  let lastError = null;
  for (let attempt = 0; attempt < 40; attempt += 1) {
    try {
      const response = await fetch(`http://127.0.0.1:${port}/json/list`);
      const targets = await response.json();
      const page = targets.find((target) => target.type === "page" && target.webSocketDebuggerUrl);
      if (page) return page.webSocketDebuggerUrl;
    } catch (error) {
      lastError = error;
    }
    await delay(250);
  }
  const cause = lastError ? ` Last error: ${lastError.message}${lastError.cause ? ` (${lastError.cause})` : ""}` : "";
  throw new Error(`No page target exposed by Chrome.${cause}`);
}

async function evaluate(client, expression, timeoutMs = defaultEvaluateTimeoutMs) {
  const result = await client.send("Runtime.evaluate", {
    expression,
    awaitPromise: true,
    returnByValue: true,
  }, timeoutMs);
  if (result.exceptionDetails) {
    const detail = result.exceptionDetails.exception?.description || result.exceptionDetails.text || "Runtime evaluation failed";
    throw new Error(detail);
  }
  return result.result ? result.result.value : undefined;
}

function formatArg(arg) {
  if (!arg) return "";
  if (typeof arg.value !== "undefined") return String(arg.value);
  if (arg.description) return arg.description;
  if (arg.type) return `[${arg.type}]`;
  return "";
}

function isOptionalRootDevProvenance404(issue) {
  if (!issue || issue.status !== 404 || !issue.url) return false;
  try {
    const parsed = new URL(issue.url);
    const base = new URL(baseUrl);
    return parsed.origin === base.origin && parsed.pathname === "/release-provenance.json";
  } catch (_) {
    return false;
  }
}

const archivedMetaCheckKeys = new Set([
  "settingsHandoffCopy",
  "privacyStorageHandoff",
  "systemPublishReadiness",
  "releaseGateEvidence",
  "releaseGateEvidenceHandoff",
  "systemPwaRuntime",
  "systemOpsRuntime",
  "workflowUiInstallPlanPanel",
  "workflowUiInstallReceiptCopy",
  "workflowUiInstallPastePacketCopy",
  "postInstallEvidenceIntake",
  "postInstallProofParser",
  "postInstallProofParserFalsePositiveGuard",
  "postInstallProofParserFields",
  "postInstallProofParserCoverage",
  "postInstallProofParserDetectedFields",
  "publishDispatchPlanPanel",
  "publishDispatchAuthPreflight",
  "publishDispatchWorkflowScopePacketCopy",
  "remoteWorkflowFileCheckPanel",
  "publishEvidenceShareUpdate",
  "publishLaunchAnnouncement",
  "publishPostLaunchReceipt",
  "launchProofEvidenceReceipt",
  "launchExecutionPacket",
  "launchExecutionCurrentActionCopy",
  "launchOperatorOnePageCopy",
  "launchReadinessRefresh",
  "launchReadinessRefreshReceiptCopy",
  "verifyWorkspaceSummary",
  "verifyWorkspaceSummaryReceiptCopy",
  "releaseGateCache",
  "releaseGateCacheRepairCopy",
  "releaseProvenancePanel",
  "releaseProvenanceReceiptCopy",
  "pagesAttestationProofIntake",
  "pagesAttestationProofIntakeCopy",
  "outputQualityAuditReceipt",
  "outputQualityExternalClaimGuard",
  "outputQualityArtifactRubric",
  "sourceSnapshotHealth",
  "githubProjectDiscovery",
  "settingsViewModule",
  "homeLaunchNextAction",
  "homeLaunchActionChecklist",
  "homeLaunchBlockerResolver",
  "homePostInstallEvidenceIntake",
  "homeExternalClaimGuard",
]);

const archivedMetaFailurePrefixes = [
  "home launch action surfaces current guard:",
  "home launch blocker resolver exposes active unblock path:",
  "settings operational handoff copy:",
  "system publish readiness alignment:",
];

function isArchivedMetaFailure(failure) {
  const text = String(failure || "");
  if (archivedMetaFailurePrefixes.some((prefix) => text.startsWith(prefix))) return true;
  const persisted = text.match(/^persisted check failed: (.+)$/);
  return !!persisted && archivedMetaCheckKeys.has(persisted[1]);
}

async function verifyResetPersistsAfterReload(client) {
  await client.send("Page.navigate", { url: `${baseUrl}/index.html#settings` });
  await delay(1000);
  await evaluate(client, `
    new Promise((resolve, reject) => {
      const started = Date.now();
      const check = () => {
        const ready = document.readyState === "complete" &&
          document.body &&
          document.body.dataset.view === "settings" &&
          typeof dashboard !== "undefined";
        if (ready) resolve(true);
        else if (Date.now() - started > 9000) reject(new Error("settings route not ready after reset reload"));
        else setTimeout(check, 100);
      };
      check();
    })
  `, resetScenarioEvaluateTimeoutMs);
  return await evaluate(client, `
    (() => {
      const storeKey = "joopark.workspace.v3";
      const failures = [];
      const raw = localStorage.getItem(storeKey);
      let payload = null;
      try { payload = JSON.parse(raw || "null"); } catch (error) { failures.push("reset payload is not valid JSON"); }
      const clearedArrays = ["events", "todos", "notes", "habits", "projects", "issues", "team", "dbInstances", "schemas", "queries", "backups", "migrations"];
      const payloadCounts = {};
      if (!payload) {
        failures.push("reset payload is missing after reload");
      } else {
        clearedArrays.forEach((key) => {
          payloadCounts[key] = Array.isArray(payload[key]) ? payload[key].length : null;
          if (payloadCounts[key] !== 0) failures.push("payload " + key + " count is " + payloadCounts[key]);
        });
        payloadCounts.ganttTasks = payload.gantt && Array.isArray(payload.gantt.tasks) ? payload.gantt.tasks.length : null;
        if (payloadCounts.ganttTasks !== 0) failures.push("payload gantt task count is " + payloadCounts.ganttTasks);
        const importCount = payload.imports && payload.imports.projectImports ? Object.keys(payload.imports.projectImports).length : null;
        payloadCounts.projectImports = importCount;
        if (importCount !== 0) failures.push("payload import registry count is " + importCount);
        if (!payload.imports || payload.imports.autoProjectSeedDisabled !== true) failures.push("project auto seed suppression was not preserved after reload");
        if (!payload.settings || !String(payload.settings.displayName || "").includes("imported user")) failures.push("display name was not preserved after reload");
        if (!payload.ui || payload.ui.theme !== "dark") failures.push("theme was not preserved after reload");
      }

      const dashboardCounts = {
        events: dashboard.events.length,
        todos: dashboard.todos.length,
        notes: dashboard.notes.length,
        habits: Array.isArray(dashboard.habits) ? dashboard.habits.length : null,
        projects: dashboard.projects.length,
        issues: dashboard.issues.length,
        tasks: dashboard.gantt && Array.isArray(dashboard.gantt.tasks) ? dashboard.gantt.tasks.length : null,
        team: dashboard.team.length,
        dbInstances: dashboard.dbInstances.length,
        schemas: dashboard.schemas.length,
        queries: dashboard.queries.length,
        backups: Array.isArray(dashboard.backups) ? dashboard.backups.length : null,
        migrations: dashboard.migrations.length,
      };
      Object.entries(dashboardCounts).forEach(([key, value]) => {
        if (value !== 0) failures.push("dashboard " + key + " count is " + value);
      });
      const viewText = document.getElementById("view-settings")?.innerText || "";
      if (!viewText.includes("데이터 백업")) failures.push("settings view did not render after reload");
      return {
        status: failures.length === 0 ? "pass" : "fail",
        failures,
        payloadCounts,
        dashboardCounts,
        view: document.body.dataset.view || "",
        storageBytes: raw ? raw.length : 0,
      };
    })()
  `, resetScenarioEvaluateTimeoutMs);
}

async function verifyFirstCreatesAfterReset(client) {
  return await evaluate(client, `
    (async () => {
      const failures = [];
      const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
      function assert(condition, message) {
        if (!condition) throw new Error(message);
      }
      function qs(selector, root = document) {
        const node = root.querySelector(selector);
        if (!node) throw new Error("Missing selector: " + selector);
        return node;
      }
      function click(selector, root = document) {
        const node = qs(selector, root);
        node.scrollIntoView({ block: "center", inline: "center" });
        node.click();
        return node;
      }
      function fill(selector, value, root = document) {
        const node = qs(selector, root);
        node.focus();
        node.value = value;
        node.dispatchEvent(new Event("input", { bubbles: true }));
        node.dispatchEvent(new Event("change", { bubbles: true }));
        return node;
      }
      async function waitFor(predicate, message, timeout = 7000) {
        const started = Date.now();
        while (Date.now() - started < timeout) {
          if (predicate()) return true;
          await sleep(80);
        }
        throw new Error(message);
      }
      async function nav(view) {
        click('[data-action="nav-to"][data-view="' + view + '"]');
        await waitFor(() => document.body.dataset.view === view && !document.getElementById("view-" + view).hidden, "route not ready: " + view);
        await sleep(120);
      }
      async function confirmModal() {
        assert(document.querySelector("#modal.open"), "modal is not open");
        click('#modal [data-action="modal-confirm"]');
        await waitFor(() => !document.querySelector("#modal.open"), "modal did not close after confirm");
        await sleep(120);
      }

      try {
        const marker = "RESET-REBUILD-" + Date.now();
        await nav("pm-portfolio");
        assert(dashboard.projects.length === 0, "expected empty projects before first rebuild create");
        click('[data-action="project-add"]');
        fill('#projectForm [name="name"]', marker + " project");
        fill('#projectForm [name="owner"]', "Reset QA");
        fill('#projectForm [name="deadline"]', "2026-08-01");
        await confirmModal();
        const project = dashboard.projects.find((item) => item.name === marker + " project");
        assert(project, "first project after reset was not saved");
        assert(dashboard.currentProjectId === project.id, "first project after reset was not selected");

        await nav("dbm-instances");
        assert(dashboard.dbInstances.length === 0, "expected empty DB instances before first rebuild create");
        click('[data-action="instance-add"]');
        fill('#instanceForm [name="name"]', marker + " db");
        fill('#instanceForm [name="engine"]', "PostgreSQL 16");
        fill('#instanceForm [name="region"]', "ap-northeast-2");
        await confirmModal();
        const instance = dashboard.dbInstances.find((item) => item.name === marker + " db");
        assert(instance, "first DB instance after reset was not saved");
        assert(dashboard.currentInstanceId === instance.id, "first DB instance after reset was not selected");

        const payload = JSON.parse(localStorage.getItem("joopark.workspace.v3") || "null");
        assert(payload.projects.length === 1 && payload.projects[0].id === project.id, "first reset project was not persisted");
        assert(payload.dbInstances.length === 1 && payload.dbInstances[0].id === instance.id, "first reset DB instance was not persisted");
        await nav("home");
        const followThrough = qs('#view-home [data-home-project-followthrough]');
        const followThroughSteps = Array.from(followThrough.querySelectorAll("[data-home-project-followthrough-step]"));
        assert(followThrough.dataset.homeProjectFollowthroughVariant === "activation_ladder" && followThrough.dataset.homeProjectFollowthroughSource === "linear_project_jira_work_item_benchmark" && followThrough.dataset.homeProjectFollowthroughStepCount === "3" && followThrough.dataset.homeProjectFollowthroughNextKey === "first_issue" && followThrough.dataset.homeProjectFollowthroughNextAction === "issue-add" && followThrough.dataset.homeProjectFollowthroughNextView === "pm-kanban", "home project follow-through dataset was incomplete after first project");
        assert(followThrough.textContent.includes("Project follow-through") && followThrough.textContent.includes("첫 이슈 연결") && followThrough.textContent.includes("마일스톤 잡기") && followThrough.textContent.includes("담당자 추가"), "home project follow-through did not explain activation after project create");
        assert(followThroughSteps.length === 3 && followThroughSteps[0].dataset.homeProjectFollowthroughStepKey === "first_issue" && followThroughSteps[0].dataset.homeProjectFollowthroughStepStatus === "action_required" && followThroughSteps[0].dataset.homeProjectFollowthroughStepAction === "issue-add" && followThroughSteps[1].dataset.homeProjectFollowthroughStepKey === "first_milestone" && followThroughSteps[1].dataset.homeProjectFollowthroughStepAction === "task-add" && followThroughSteps[2].dataset.homeProjectFollowthroughStepKey === "first_owner" && followThroughSteps[2].dataset.homeProjectFollowthroughStepAction === "member-add", "home project follow-through steps were incomplete after first project");
        click('[data-home-project-followthrough-step-key="first_issue"] [data-action="issue-add"]', followThrough);
        await waitFor(() => document.querySelector("#modal.open") && document.querySelector("#issueForm"), "home project follow-through issue action did not open modal");
        click('#modal [data-action="close-modal"]');
        await waitFor(() => !document.querySelector("#modal.open"), "home project follow-through issue modal did not close");
        click('[data-home-project-followthrough-step-key="first_milestone"] [data-action="task-add"]', followThrough);
        await waitFor(() => document.querySelector("#modal.open") && document.querySelector("#taskForm"), "home project follow-through milestone action did not open modal");
        assert(qs('#taskForm [name="milestone"]').checked, "home project follow-through milestone action did not preselect milestone");
        click('#modal [data-action="close-modal"]');
        await waitFor(() => !document.querySelector("#modal.open"), "home project follow-through milestone modal did not close");
        return {
          status: "pass",
          failures,
          projectId: project.id,
          instanceId: instance.id,
          counts: {
            projects: dashboard.projects.length,
            dbInstances: dashboard.dbInstances.length,
          },
        };
      } catch (error) {
        failures.push(error.message);
        return {
          status: "fail",
          failures,
          counts: {
            projects: dashboard.projects.length,
            dbInstances: dashboard.dbInstances.length,
          },
        };
      }
    })()
  `, resetScenarioEvaluateTimeoutMs);
}

const interactionExpression = `
(async () => {
  const marker = "ARSMOKE-" + Date.now();
  const strictVerifyWorkspaceSummary = ${verifyWorkspaceSummaryStrict ? "true" : "false"};
  const storeKey = "joopark.workspace.v3";
  const steps = [];
  const failures = [];
  let operationsCopyActionsModule = false;
  let verifyWorkspaceSummaryModule = false;
  let dialogShellModule = false;
  let projectPickerModule = false;
  let globalSearchModule = false;
  let reviewResultStateModule = false;
  let reviewResultDraftStateModule = false;
  let reviewExecutionChecklistModule = false;
  let reviewIssuePayloadModule = false;
  let reviewCreationActionsModule = false;
  let reviewArtifactStateModule = false;
  let reviewCopyActionsModule = false;
  let reviewSubmissionCopyModule = false;
  let reviewRecommendationExportModule = false;
  let backupExportOk = false;
  let backupOversizeRejectedOk = false;
  let backupMalformedRejectedOk = false;
  let backupRecordLimitRejectedOk = false;
  let backupNormalizeClampedOk = false;
  let backupImportSummaryScopeOk = false;
  let backupImportOk = false;
  let backupResetOk = false;
  let backupSearchRecoveryOk = false;
  let settingsHandoffCopyOk = false;
  let privacyStorageHandoffOk = false;
  let systemPublishReadinessOk = false;
  let releaseGateEvidenceOk = false;
  let releaseGateEvidenceHandoffOk = false;
  let systemPwaRuntimeOk = false;
  let systemOpsRuntimeOk = false;
  let workflowUiInstallPlanPanelOk = false;
  let workflowUiInstallReceiptCopyOk = false;
  let postInstallEvidenceIntakeOk = false;
  let postInstallProofParserOk = false;
  let postInstallProofParserFalsePositiveGuardOk = false;
  let publishDispatchPlanPanelOk = false;
  let publishDispatchAuthPreflightOk = false;
  let publishDispatchWorkflowScopePacketCopyOk = false;
  let remoteWorkflowFileCheckPanelOk = false;
  let publishEvidenceShareUpdateOk = false;
  let publishLaunchAnnouncementOk = false;
  let publishPostLaunchReceiptOk = false;
  let launchProofEvidenceReceiptOk = false;
  let launchExecutionPacketOk = false;
  let launchExecutionCurrentActionCopyOk = false;
  let launchOperatorOnePageCopyOk = false;
  let launchReadinessRefreshOk = false;
  let launchReadinessRefreshReceiptCopyOk = false;
  let verifyWorkspaceSummaryOk = false;
  let verifyWorkspaceSummaryReceiptCopyOk = false;
  let releaseGateCacheOk = false;
  let releaseGateCacheRepairCopyOk = false;
  let releaseProvenancePanelOk = false;
  let releaseProvenanceReceiptCopyOk = false;
  let pagesAttestationProofIntakeOk = false;
  let pagesAttestationProofIntakeCopyOk = false;
  let outputQualityAuditReceiptOk = false;
  let outputQualityExternalClaimGuardOk = false;
  let outputQualityArtifactRubricOk = false;
  let markdownSanitizedOk = false;
  let workspaceCandidateVisibleOk = false;
  let workspaceCompetitiveCandidateVisibleOk = false;
  let colanodeCandidateFreshnessVisibleOk = false;
  let parabolCandidateFreshnessVisibleOk = false;
  let worklenzCandidateFreshnessVisibleOk = false;
  let anytypeCandidateFreshnessVisibleOk = false;
  let focalboardCandidateFreshnessVisibleOk = false;
  let epicenterCandidateFreshnessVisibleOk = false;
  let openLoafCandidateFreshnessVisibleOk = false;
  let planeCandidateFreshnessVisibleOk = false;
  let appFlowyCandidateFreshnessVisibleOk = false;
  let affineCandidateFreshnessVisibleOk = false;
  let outlineCandidateFreshnessVisibleOk = false;
  let bookStackCandidateFreshnessVisibleOk = false;
  let wikiJsCandidateFreshnessVisibleOk = false;
  const remainingWorkspaceFreshnessOk = {
    workstream: false,
    taskosaur: false,
    markdownTaskManager: false,
    taskcoach: false,
    fluidCalendar: false,
  };
  let veritasCandidateFreshnessVisibleOk = false;
  let openProjectCandidateFreshnessVisibleOk = false;
  let leantimeCandidateFreshnessVisibleOk = false;
  let candidateMetadataRefreshOk = false;
  let candidateNextActionVisibleOk = false;
  let candidateActionFilterOk = false;
  let candidateActionSummaryVisibleOk = false;
  let candidateSeedScopeOk = false;
  let candidateBenchmarkFocusVisibleOk = false;
  let candidateBenchmarkQueueVisibleOk = false;
  let candidateBenchmarkRubricVisibleOk = false;
  let candidateBenchmarkRubricScoreVisibleOk = false;
  let workspaceBenchmarkRubricVisibleOk = false;
  let workspaceBenchmarkExportVisibleOk = false;
  let workspaceBenchmarkReviewHandoffVisibleOk = false;
  let workspaceBenchmarkReviewHandoffCopyVisibleOk = false;
  let workspaceBenchmarkReviewIssueDraftVisibleOk = false;
  let workspaceBenchmarkReviewNotePublishVisibleOk = false;
  let workspaceBenchmarkReviewGithubCommentVisibleOk = false;
  let knowledgeBaseBenchmarkRubricVisibleOk = false;
  let knowledgeBaseBenchmarkExportVisibleOk = false;
  let knowledgeBaseBenchmarkReviewHandoffVisibleOk = false;
  let knowledgeBaseBenchmarkReviewHandoffCopyVisibleOk = false;
  let knowledgeBaseBenchmarkReviewIssueDraftVisibleOk = false;
  let knowledgeBaseBenchmarkReviewNotePublishVisibleOk = false;
  let knowledgeBaseBenchmarkReviewGithubCommentVisibleOk = false;
  let candidateBenchmarkRecommendationExportVisibleOk = false;
  let candidateBenchmarkReviewQueueVisibleOk = false;
  let candidateBenchmarkReviewHandoffVisibleOk = false;
  let candidateBenchmarkReviewHandoffCopyVisibleOk = false;
  let candidateBenchmarkReviewIssueDraftVisibleOk = false;
  let reviewPackageBundleVisibleOk = false;
  let reviewPackageManifestVisibleOk = false;
  let reviewPackagePasteTargetsVisibleOk = false;
  let reviewPackagePastePreviewVisibleOk = false;
  let reviewPackagePastePreviewCopyOk = false;
  let reviewPackageTrackerFieldCopyOk = false;
  let reviewPackageTrackerFormCopyOk = false;
  let reviewPackageSubmitSequenceCopyOk = false;
	  let reviewPackageExternalReceiptTemplateCopyOk = false;
	  let reviewPackageExternalReceiptFilledCopyOk = false;
	  let reviewPackageExternalReceiptIntegrityOk = false;
	  let reviewPackageSubmissionCloseoutSummaryVisibleOk = false;
	  let reviewPackageSubmissionUpdateCopyOk = false;
  let reviewPackageFinalQualityGateVisibleOk = false;
  let reviewPackageArtifactQualityRubricVisibleOk = false;
  let reviewPackageDecisionBriefVisibleOk = false;
  let reviewPackageOperatorQuickStartVisibleOk = false;
  let reviewIssueDecisionSummaryVisibleOk = false;
  let reviewCommentNoteDecisionSummaryVisibleOk = false;
  let reviewPackageQualityRepairChecklistVisibleOk = false;
  let reviewResultValidatorVisibleOk = false;
  let reviewResultValidatorEmptyOk = false;
  let reviewResultValidatorFailureOk = false;
  let reviewResultValidatorPassOk = false;
  let reviewResultValidatorRetryOk = false;
  let reviewResultValidatorSavedOk = false;
  let reviewResultValidatorPersistedOk = false;
  let reviewResultRepairPacketCopyOk = false;
  let reviewResultRepairActionPlanVisibleOk = false;
  let reviewResultPostRepairReceiptOk = false;
  let reviewResultRepairArtifactLinkOk = false;
  let reviewPostRepairArtifactLinkOk = false;
  let reviewResultIssueAppliedOk = false;
  let reviewResultNoteAppliedOk = false;
  let reviewArtifactDiffVisibleOk = false;
  let reviewArtifactDiffValidatedOk = false;
  let reviewArtifactOperationalReadinessOk = false;
  let reviewOperationalTrackerFieldOk = false;
  let reviewExecutionChecklistOk = false;
  let reviewExecutionChecklistProgressOk = false;
  let reviewAssigneeOverrideOk = false;
  let reviewAssigneeOverrideDraftPersistenceOk = false;
  let reviewAssigneeFollowUpOk = false;
  let reviewArtifactReceiptCompareOk = false;
  let reviewArtifactReceiptRepairSuggestionOk = false;
  let reviewArtifactReceiptRepairCopyOk = false;
  let reviewArtifactReceiptRepairApplyOk = false;
  let reviewArtifactPostApplyFreshReceiptOk = false;
  let reviewArtifactFreshReceiptAfterChecklistOk = false;
  let portfolioCandidateFilterOk = false;
  let portfolioCandidateRankedOk = false;
  let portfolioReferenceToggleOk = false;
  let sourceSnapshotHealthOk = false;
  let githubProjectDiscoveryOk = false;
  let releaseStatusModuleOk = false;
  let searchEmptyStateModuleOk = false;
  let calendarViewModuleOk = false;
  let todoViewModuleOk = false;
  let notesViewModuleOk = false;
  let habitsViewModuleOk = false;
  let statsViewModuleOk = false;
  let portfolioViewModuleOk = false;
  let kanbanViewModuleOk = false;
  let ganttViewModuleOk = false;
  let teamViewModuleOk = false;
  let workspaceStorageModuleOk = false;
  let storageStatusViewModuleOk = false;
  let settingsViewModuleOk = false;
  let systemStatusViewModuleOk = false;
  let operationsCopyActionsModuleOk = false;
  let verifyWorkspaceSummaryModuleOk = false;
  let dialogShellModuleOk = false;
  let projectPickerModuleOk = false;
  let globalSearchModuleOk = false;
  let commandPaletteModuleOk = false;
  let llmWikiActionDraftsOk = false;
  let llmWikiPaletteBridgeOk = false;
  let llmWikiActionStateOk = false;
  let llmWikiActionFilterOk = false;
  let llmWikiTodoNoteSourceReturnOk = false;
  let llmWikiTodoNoteSourceBacklinkOk = false;
  let llmWikiTodoNoteModalSourceOk = false;
  let llmWikiTodoNoteSourceFilterOk = false;
  let llmWikiTodoNoteSourcePaletteOk = false;
  let llmWikiTodoNotePaletteRecordOpenOk = false;
  let llmWikiKoreanSourceFilterCommandOk = false;
  let sourceKoreanResetCommandOk = false;
  let kanbanKoreanGenericSourceCommandOk = false;
  let llmWikiKoreanSourceAliasSearchOk = false;
  let dbCatalogModuleOk = false;
  let reviewHandoffModuleOk = false;
  let reviewResultViewModuleOk = false;
  let reviewResultStateModuleOk = false;
  let reviewResultDraftStateModuleOk = false;
  let reviewExecutionChecklistModuleOk = false;
  let reviewIssuePayloadModuleOk = false;
  let reviewCreationActionsModuleOk = false;
  let reviewPackageViewModuleOk = false;
  let reviewArtifactViewModuleOk = false;
  let reviewArtifactStateModuleOk = false;
  let reviewCopyActionsModuleOk = false;
  let reviewSubmissionCopyModuleOk = false;
  let reviewRecommendationExportModuleOk = false;
  let backupImportUiModuleOk = false;
  let homeQuickLinksNavigateOk = false;
  let homeLaunchNextActionOk = false;
  let homeLaunchActionChecklistOk = false;
  let homeLaunchBlockerResolverOk = false;
  let homeReleaseGateEvidenceOk = false;
  let homePostInstallEvidenceIntakeOk = false;
  let homeExternalClaimGuardOk = false;
  let homeExecutionViewModuleOk = false;
  let homeExecutionQueueOk = false;
  let homeExecutionQueueExplainabilityOk = false;
  let homeExecutionQueueBucketsOk = false;
  let homeExecutionQueueBucketFilterOk = false;
  let homeExecutionQueueFilterSummaryOk = false;
  let homeExecutionQueueFilterCompositionOk = false;
  let homeExecutionQueueFilterWindowOk = false;
  let homeExecutionQueueFilterRankWindowOk = false;
  let homeExecutionQueueScoreWindowOk = false;
  let homeExecutionQueueScoreDriverOk = false;
  let homeExecutionQueueLeadDriverOk = false;
  let homeExecutionQueueLeadDriverCountOk = false;
  let homeExecutionQueueLeadDriverTieOk = false;
  let homeExecutionQueueReceiptCompactOk = false;
  let homeExecutionQueueReceiptDetailOk = false;
  let homeExecutionQueueReceiptDescriptionOk = false;
  let homeExecutionQueueQuickActionsOk = false;
  let homeExecutionQueueQuickUndoOk = false;
  let homeUpcomingEventOpenOk = false;
	  let homeQuickTodoOk = false;
	  let routeDeepLinkOk = false;
  let commandPaletteRouteCoverageOk = false;
  let commandPalettePersonalNavAliasesOk = false;
  let commandPaletteOperationalNavAliasesOk = false;
  let commandPalettePmPortfolioNavAliasOk = false;
  let commandPalettePmGanttNavAliasOk = false;
  let commandPalettePmTeamNavAliasOk = false;
  let commandPaletteKoreanNavAliasOk = false;
  let commandPaletteDbKoreanNavAliasOk = false;
  let commandPaletteDbInstanceNavAliasOk = false;
  let commandPaletteDbQueryNavAliasOk = false;
  let commandPaletteDbBackupNavAliasOk = false;
  let commandPaletteExactNavLabelOk = false;
  let commandPaletteCreatedNoteRecordOk = false;
	  let homeFirstRunGuidanceOk = false;
	  let homeFirstRunGuidedStartOk = false;
	  let globalHelpAccessOk = false;
	  let topbarDataSafetyOk = false;
	  let calendarModeSwitchOk = false;
	  let calendarGridKeyboardOk = false;
  let calendarSearchRecoveryOk = false;
  let habitSearchRecoveryOk = false;
  let todoSearchRecoveryOk = false;
  let topbarSearchClearOk = false;
  let notesSearchRecoveryOk = false;
  let portfolioSearchRecoveryOk = false;
  let kanbanLabelNormalizationOk = false;
  let kanbanOrderPersistenceOk = false;
  let kanbanDensityPersistenceOk = false;
  let kanbanTouchDragOk = false;
  let kanbanSourceBadgesOk = false;
  let kanbanSourceFilterOk = false;
  let kanbanSourceEmptyOk = false;
  let kanbanSourceSummaryOk = false;
  let kanbanSourcePaletteOk = false;
  let kanbanSourceDirectReturnOk = false;
  let kanbanReviewFamilyBadgeOk = false;
  let kanbanReviewFamilyFilterOk = false;
  let kanbanReviewKoreanFamilyFilterCommandOk = false;
  let reviewKoreanRollupSourceFilterCommandOk = false;
  let issueSourceReturnOk = false;
  let reviewIssueSourceReturnOk = false;
  let reviewNoteSourceReturnOk = false;
  let reviewBenchmarkNoteModalSourceReturnOk = false;
  let reviewNoteCardSourceReturnOk = false;
  let reviewBenchmarkNoteCardSourceReturnOk = false;
  let reviewNoteCardFamilyLabelOk = false;
  let reviewNoteSourceFilterOk = false;
  let reviewNoteFamilyFilterOk = false;
  let reviewBenchmarkNoteFamilyFilterOk = false;
  let reviewNoteKoreanFamilyFilterCommandOk = false;
  let reviewNoteExistingOpenOk = false;
  let reviewKbNoteExistingOpenOk = false;
  let reviewBenchmarkNoteExistingOpenOk = false;
  let issueSourceBacklinkWikiOk = false;
  let issueSourceBacklinkDbOk = false;
  let issueSourceBacklinkReviewOk = false;
  let sourceIssueExistingOpenOk = false;
  let sourceIssueExistingReviewOk = false;
  let sourceIssueExistingDbOk = false;
  let sourceIssueExistingWikiOk = false;
  let sourceIssuePaletteRecordOpenOk = false;
  let sourceRecordPaletteLabelSearchOk = false;
  let sourceDbPaletteLabelSearchOk = false;
  let sourceDbKoreanAliasSearchOk = false;
  let dbCatalogKoreanSourceFilterCommandOk = false;
  let sourceReviewPaletteLabelSearchOk = false;
  let sourceReviewNotePaletteLabelSearchOk = false;
  let sourceBenchmarkReviewNotePaletteLabelSearchOk = false;
  let sourceBenchmarkReviewNotePaletteSourceReturnOk = false;
  let sourceBenchmarkReviewPaletteFamilyLabelSearchOk = false;
  let sourceReviewAllFamilyLabelSearchOk = false;
  let sourceBenchmarkReviewKoreanFamilyAliasSearchOk = false;
  let sourceReviewKoreanAllFamilyAliasSearchOk = false;
  let sourceReviewPaletteFamilyLabelOk = false;
  let llmWikiExistingTodoNoteOpenOk = false;
  let kanbanSearchRecoveryOk = false;
  let ganttSearchRecoveryOk = false;
  let ganttSvgTaskAccessibilityOk = false;
  let teamSearchRecoveryOk = false;
  let statsSearchInertOk = false;
  let dbInstancesSearchRecoveryOk = false;
  let dbSchemaSearchRecoveryOk = false;
  let dbQueriesSearchRecoveryOk = false;
  let dbCatalogProvenanceOk = false;
  let dbCatalogProvenanceFilterOk = false;
  let dbCatalogStaleActionOk = false;
  let importedMarker = "";
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  function assert(condition, message) {
    if (!condition) throw new Error(message);
  }
  function qs(selector, root = document) {
    const node = root.querySelector(selector);
    if (!node) throw new Error("Missing selector: " + selector);
    return node;
  }
  function qsa(selector, root = document) {
    return Array.from(root.querySelectorAll(selector));
  }
  function click(selector, root = document) {
    const node = qs(selector, root);
    node.scrollIntoView({ block: "center", inline: "center" });
    node.click();
    return node;
  }
  function fill(selector, value, root = document) {
    const node = qs(selector, root);
    node.focus();
    node.value = value;
    node.dispatchEvent(new Event("input", { bubbles: true }));
    node.dispatchEvent(new Event("change", { bubbles: true }));
    return node;
  }
  function select(selector, value, root = document) {
    const node = qs(selector, root);
    node.value = value;
    node.dispatchEvent(new Event("input", { bubbles: true }));
    node.dispatchEvent(new Event("change", { bubbles: true }));
    return node;
  }
  function check(selector, checked = true, root = document) {
    const node = qs(selector, root);
    node.checked = checked;
    node.dispatchEvent(new Event("input", { bubbles: true }));
    node.dispatchEvent(new Event("change", { bubbles: true }));
    return node;
  }
  async function waitFor(predicate, message, timeout = 7000) {
    const started = Date.now();
    while (Date.now() - started < timeout) {
      if (predicate()) return true;
      await sleep(80);
    }
    throw new Error(message);
  }
  window.__smokeClipboardText = "";
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: { writeText: async (text) => { window.__smokeClipboardText = text; } },
  });
  assert(window.JooParkOpsRuntime && window.JooParkOpsRuntime.version === "joopark-ops-runtime-loader/v1" && typeof window.JooParkOpsRuntime.load === "function", "ops runtime loader was not loaded: joopark-ops-runtime-loader/v1");
  await window.JooParkOpsRuntime.load("release");
  await window.JooParkOpsRuntime.load("review");
  reviewCopyActionsModule = !!(window.JooParkReviewCopyActions && window.JooParkReviewCopyActions.version === "joopark-review-copy-actions/v1" && typeof window.JooParkReviewCopyActions.create === "function");
  assert(reviewCopyActionsModule, "review copy actions runtime module was not loaded: joopark-review-copy-actions/v1");
  reviewArtifactStateModule = !!(window.JooParkReviewArtifactState && window.JooParkReviewArtifactState.version === "joopark-review-artifact-state/v1" && typeof window.JooParkReviewArtifactState.create === "function");
  assert(reviewArtifactStateModule, "review artifact state runtime module was not loaded: joopark-review-artifact-state/v1");
  reviewArtifactStateModuleOk = true;
  operationsCopyActionsModule = !!(window.JooParkOperationsCopyActions && window.JooParkOperationsCopyActions.version === "joopark-operations-copy-actions/v1" && typeof window.JooParkOperationsCopyActions.create === "function");
  assert(operationsCopyActionsModule, "operations copy actions runtime module was not loaded: joopark-operations-copy-actions/v1");
  operationsCopyActionsModuleOk = true;
  verifyWorkspaceSummaryModule = !!(window.JooParkVerifyWorkspaceSummary && window.JooParkVerifyWorkspaceSummary.version === "joopark-verify-workspace-summary/v1" && typeof window.JooParkVerifyWorkspaceSummary.create === "function");
  assert(verifyWorkspaceSummaryModule, "verify workspace summary runtime module was not loaded: joopark-verify-workspace-summary/v1");
  verifyWorkspaceSummaryModuleOk = true;
  reviewResultStateModule = !!(window.JooParkReviewResultState && window.JooParkReviewResultState.version === "joopark-review-result-state/v1" && typeof window.JooParkReviewResultState.create === "function");
  assert(reviewResultStateModule, "review result state runtime module was not loaded: joopark-review-result-state/v1");
  reviewResultStateModuleOk = true;
  reviewExecutionChecklistModule = !!(window.JooParkReviewExecutionChecklist && window.JooParkReviewExecutionChecklist.version === "joopark-review-execution-checklist/v1" && typeof window.JooParkReviewExecutionChecklist.create === "function");
  assert(reviewExecutionChecklistModule, "review execution checklist runtime module was not loaded: joopark-review-execution-checklist/v1");
  reviewExecutionChecklistModuleOk = true;
  reviewIssuePayloadModule = !!(window.JooParkReviewIssuePayload && window.JooParkReviewIssuePayload.version === "joopark-review-issue-payload/v1" && typeof window.JooParkReviewIssuePayload.create === "function");
  assert(reviewIssuePayloadModule, "review issue payload runtime module was not loaded: joopark-review-issue-payload/v1");
  reviewIssuePayloadModuleOk = true;
  reviewResultDraftStateModule = !!(window.JooParkReviewResultDraftState && window.JooParkReviewResultDraftState.version === "joopark-review-result-draft-state/v1" && typeof window.JooParkReviewResultDraftState.create === "function");
  assert(reviewResultDraftStateModule, "review result draft state runtime module was not loaded: joopark-review-result-draft-state/v1");
  reviewResultDraftStateModuleOk = true;
  reviewCreationActionsModule = !!(window.JooParkReviewCreationActions && window.JooParkReviewCreationActions.version === "joopark-review-creation-actions/v1" && typeof window.JooParkReviewCreationActions.create === "function");
  assert(reviewCreationActionsModule, "review creation actions runtime module was not loaded: joopark-review-creation-actions/v1");
  reviewCreationActionsModuleOk = true;
  dialogShellModule = !!(window.JooParkDialogShell && window.JooParkDialogShell.version === "joopark-dialog-shell/v1" && typeof window.JooParkDialogShell.create === "function");
  assert(dialogShellModule, "dialog shell runtime module was not loaded: joopark-dialog-shell/v1");
  dialogShellModuleOk = true;
  projectPickerModule = !!(window.JooParkProjectPicker && window.JooParkProjectPicker.version === "joopark-project-picker/v1" && typeof window.JooParkProjectPicker.create === "function");
  assert(projectPickerModule, "project picker runtime module was not loaded: joopark-project-picker/v1");
  projectPickerModuleOk = true;
  globalSearchModule = !!(window.JooParkGlobalSearch && window.JooParkGlobalSearch.version === "joopark-global-search/v1" && typeof window.JooParkGlobalSearch.create === "function");
  assert(globalSearchModule, "global search runtime module was not loaded: joopark-global-search/v1");
  globalSearchModuleOk = true;
  reviewSubmissionCopyModule = !!(window.JooParkReviewSubmissionCopy && window.JooParkReviewSubmissionCopy.version === "joopark-review-submission-copy/v1" && typeof window.JooParkReviewSubmissionCopy.create === "function");
  assert(reviewSubmissionCopyModule, "review submission copy runtime module was not loaded: joopark-review-submission-copy/v1");
  reviewRecommendationExportModule = !!(window.JooParkReviewRecommendationExport && window.JooParkReviewRecommendationExport.version === "joopark-review-recommendation-export/v1" && typeof window.JooParkReviewRecommendationExport.create === "function");
  assert(reviewRecommendationExportModule, "review recommendation export runtime module was not loaded: joopark-review-recommendation-export/v1");
  async function waitForReviewResult(validator, predicate, message) {
    try {
      await waitFor(predicate, message);
    } catch (error) {
      const statusText = validator.querySelector("[data-review-result-status]")?.textContent || "";
      const failureText = validator.querySelector("[data-review-result-failures]")?.textContent || "";
      const outputText = validator.querySelector("[data-review-result-output]")?.textContent || "";
      throw new Error(message + "; state=" + (validator.dataset.reviewResultState || "") + "; status=" + statusText + "; failures=" + failureText + "; output=" + outputText);
    }
  }
  async function exerciseReviewResultValidator(validator, expectedKey, summaryTerm, label) {
    assert(validator.dataset.reviewResultState === "empty", label + " review result validator did not start empty");
    assert(validator.dataset.reviewResultPrimaryKey === expectedKey, label + " review result validator primary key did not render");
    assert(validator.dataset.reviewResultSchema === "joopark-review-handoff/v2", label + " review result validator schema did not render");
    assert(qs("[data-review-result-saved-card]", validator).dataset.reviewResultSavedState === "empty", label + " review result saved empty state did not render");
    click('[data-action="validate-review-result"]', validator);
    await waitForReviewResult(validator, () => validator.dataset.reviewResultState === "empty" && qs("[data-review-result-status]", validator).textContent.includes("붙여넣으세요"), label + " review result validator empty state did not render");
    fill("[data-review-result-input]", "{bad json", validator);
    click('[data-action="validate-review-result"]', validator);
    await waitForReviewResult(validator, () => validator.dataset.reviewResultState === "fail" && qs("[data-review-result-failures]", validator).textContent.includes("JSON 파싱 실패"), label + " review result validator malformed JSON failure did not render");
    const malformedRepair = qs("[data-review-result-repair]", validator);
    const malformedRepairText = qs("[data-review-result-repair-text]", malformedRepair).textContent;
    assert(malformedRepair.dataset.reviewResultRepairReady === "true", label + " review result repair packet did not render");
    assert(malformedRepairText.includes("JooPark Review Result Repair Packet") && malformedRepairText.includes("Repair action plan:") && malformedRepairText.includes("Primary fix target:") && malformedRepairText.includes("Schema identity:") && malformedRepairText.includes("Evidence boundary:") && malformedRepairText.includes("First action:") && malformedRepairText.includes("Validation gate:") && malformedRepairText.includes("Stop condition:") && malformedRepairText.includes("Return one valid JSON object first") && malformedRepairText.includes("Expected primaryDecisionKey: " + expectedKey) && malformedRepairText.includes("Required JSON fields:") && malformedRepairText.includes("Correction scaffold:") && malformedRepairText.includes('"primaryDecisionKey": "' + expectedKey + '"') && malformedRepairText.includes("uiArtifacts") && malformedRepairText.includes("Rerun the result validator before creating issues or notes"), label + " review result malformed repair packet text did not render");
    click("[data-review-result-repair-copy]", malformedRepair);
    await waitFor(() => malformedRepair.dataset.reviewResultRepairCopied === "true" && window.__smokeClipboardText.includes("JooPark Review Result Repair Packet") && window.__smokeClipboardText.includes("Repair action plan:") && window.__smokeClipboardText.includes("Primary fix target:") && window.__smokeClipboardText.includes("Schema identity:") && window.__smokeClipboardText.includes("Evidence boundary:") && window.__smokeClipboardText.includes("First action:") && window.__smokeClipboardText.includes("Validation gate:") && window.__smokeClipboardText.includes("Stop condition:") && window.__smokeClipboardText.includes("Return one valid JSON object first") && window.__smokeClipboardText.includes("Expected schemaVersion: joopark-review-handoff/v2") && window.__smokeClipboardText.includes("Required JSON fields:") && window.__smokeClipboardText.includes("Correction scaffold:") && window.__smokeClipboardText.includes('"schemaVersion": "joopark-review-handoff/v2"') && window.__smokeClipboardText.includes('"primaryDecisionKey": "' + expectedKey + '"'), label + " review result repair packet copy text did not reach clipboard");
    reviewResultRepairPacketCopyOk = true;
    reviewResultRepairActionPlanVisibleOk = true;
    click('[data-action="insert-review-result-example"]', validator);
    await waitForReviewResult(validator, () => validator.dataset.reviewResultState === "pass" && validator.dataset.reviewResultFailureCount === "0", label + " review result validator example did not pass");
    assert(qs("[data-review-result-summary]", validator).textContent.includes(summaryTerm), label + " review result validator summary did not render");
    await waitForReviewResult(validator, () => validator.dataset.reviewResultSaved === "true" && qs("[data-review-result-saved-card]", validator).dataset.reviewResultSavedState === "saved", label + " review result saved state did not render");
    assert(qs("[data-review-result-saved-summary]", validator).textContent.includes(summaryTerm), label + " review result saved summary did not render");
    const savedResult = dashboard.reviewResults.find((item) => item && item.key === expectedKey);
    assert(savedResult && savedResult.summary.includes(summaryTerm), label + " review result was not saved in dashboard state");
    assert(savedResult.schemaVersion === "joopark-review-handoff/v2" && savedResult.resultJson.includes(expectedKey), label + " review result saved contract did not persist");
    assert(savedResult.packageChecksum && savedResult.packageChecksum.startsWith("fnv1a32-") && savedResult.packageManifestStatus === "pass" && savedResult.packageSourceFreshness === "pass", label + " review result manifest evidence was not saved");
    assert(qs("[data-review-result-saved-card]", validator).textContent.includes(savedResult.packageChecksum), label + " review result saved card did not render package checksum");
    const postRepairReceipt = qs("[data-review-result-repair-receipt]", validator);
    const postRepairReceiptText = qs("[data-review-result-repair-receipt-text]", postRepairReceipt).textContent;
    assert(postRepairReceipt.dataset.reviewResultRepairReceiptReady === "true" && postRepairReceipt.dataset.reviewResultRepairReceiptChecksum === savedResult.packageChecksum, label + " review result post-repair receipt did not render saved checksum");
    assert(postRepairReceiptText.includes("JooPark Review Result Post-Repair Receipt") && postRepairReceiptText.includes("Previous state: fail") && postRepairReceiptText.includes("JSON 파싱 실패") && postRepairReceiptText.includes("Saved payload checksum: " + savedResult.packageChecksum) && postRepairReceiptText.includes("Pair this receipt with the created issue or note artifact receipt"), label + " review result post-repair receipt text was incomplete");
    click("[data-review-result-repair-receipt-copy]", postRepairReceipt);
    await waitFor(() => postRepairReceipt.dataset.reviewResultRepairReceiptCopied === "true" && window.__smokeClipboardText.includes("JooPark Review Result Post-Repair Receipt") && window.__smokeClipboardText.includes("Previous failure count: 1") && window.__smokeClipboardText.includes(savedResult.packageChecksum), label + " review result post-repair receipt copy text did not reach clipboard");
    assert(savedResult.repairReceiptReady === true && savedResult.postRepairReceipt && savedResult.postRepairReceipt.includes("JooPark Review Result Post-Repair Receipt") && savedResult.repairEvidence && savedResult.repairEvidence.previousFailureCount === 1 && savedResult.repairEvidence.previousFailures.some((item) => item.includes("JSON 파싱 실패")), label + " review result post-repair receipt evidence was not saved for downstream artifacts");
    reviewResultPostRepairReceiptOk = true;
    const storedPayload = JSON.parse(localStorage.getItem("joopark.workspace.v3") || "{}");
    assert(Array.isArray(storedPayload.reviewResults) && storedPayload.reviewResults.some((item) => item && item.key === expectedKey && item.summary.includes(summaryTerm) && item.packageChecksum && item.packageChecksum.startsWith("fnv1a32-")), label + " review result was not persisted to localStorage");
    const validResult = JSON.parse(qs("[data-review-result-input]", validator).value);
    const missingGateResult = JSON.parse(JSON.stringify(validResult));
    delete missingGateResult.executionPlan[0].decisionGate;
    fill("[data-review-result-input]", JSON.stringify(missingGateResult, null, 2), validator);
    click('[data-action="validate-review-result"]', validator);
    await waitForReviewResult(validator, () => validator.dataset.reviewResultState === "fail" && qs("[data-review-result-failures]", validator).textContent.includes("decisionGate"), label + " review result validator missing decisionGate failure did not render");
    assert(qs("[data-review-result-repair-text]", validator).textContent.includes("Add decisionGate that states when to proceed"), label + " review result decisionGate repair guidance did not render");
    const wrongKeyResult = JSON.parse(JSON.stringify(validResult));
    wrongKeyResult.primaryDecisionKey = "wrong:" + expectedKey;
    fill("[data-review-result-input]", JSON.stringify(wrongKeyResult, null, 2), validator);
    click('[data-action="validate-review-result"]', validator);
    await waitForReviewResult(validator, () => validator.dataset.reviewResultState === "fail" && qs("[data-review-result-failures]", validator).textContent.includes("primaryDecisionKey"), label + " review result validator wrong primaryDecisionKey failure did not render");
    const lowOwnerResult = JSON.parse(JSON.stringify(validResult));
    lowOwnerResult.executionPlan[0].owner = "Outside vendor group";
    lowOwnerResult.exceptions = [];
    fill("[data-review-result-input]", JSON.stringify(lowOwnerResult, null, 2), validator);
    click('[data-action="validate-review-result"]', validator);
    await waitForReviewResult(validator, () => validator.dataset.reviewResultState === "fail" && qs("[data-review-result-failures]", validator).textContent.includes("low-confidence"), label + " review result validator low-confidence owner failure did not render");
    lowOwnerResult.exceptions = [{
      type: "missing_evidence",
      message: "Owner is not an exact active JooPark team member.",
      requiredFollowUp: "Confirm the exact assignee for Outside vendor group before issue creation.",
    }];
    fill("[data-review-result-input]", JSON.stringify(lowOwnerResult, null, 2), validator);
    click('[data-action="validate-review-result"]', validator);
    await waitForReviewResult(validator, () => validator.dataset.reviewResultState === "pass" && validator.dataset.reviewResultFailureCount === "0", label + " review result validator low-confidence owner with requiredFollowUp did not pass");
    const ownerFollowUpDraft = validator.closest("[data-benchmark-review-handoff], [data-knowledge-base-review-handoff], [data-workspace-review-handoff]").querySelector("[data-review-issue-draft]");
    await waitFor(() => ownerFollowUpDraft.dataset.issueDraftAssigneeConfidence === "low" && ownerFollowUpDraft.dataset.issueDraftOwnerFollowUpReady === "true", label + " review issue draft low-confidence owner follow-up metadata did not render");
    const ownerFollowUpPanel = qs("[data-issue-draft-owner-follow-up]", ownerFollowUpDraft);
    assert(ownerFollowUpDraft.dataset.issueDraftLabels.includes("owner-followup") && Number(ownerFollowUpDraft.dataset.issueDraftAssigneeRequiredFollowUpCount || 0) >= 2 && Number(ownerFollowUpDraft.dataset.issueDraftAssigneePromptExampleCount || 0) >= 2, label + " review issue draft owner follow-up counts did not render");
    assert(ownerFollowUpPanel.innerText.includes("requiredFollowUp") && ownerFollowUpPanel.innerText.includes("Outside vendor group"), label + " review issue draft owner follow-up prompt examples did not render");
    assert(ownerFollowUpPanel.querySelectorAll("code").length >= 2 && !ownerFollowUpPanel.innerText.includes("[object Object]"), label + " review issue draft owner follow-up code examples did not render as code");
    assert(qs("[data-issue-draft-body]", ownerFollowUpDraft).innerText.includes("## Assignee Follow-up"), label + " review issue draft body did not include assignee follow-up section");
    reviewAssigneeFollowUpOk = true;
    click('[data-action="insert-review-result-example"]', validator);
    await waitForReviewResult(validator, () => validator.dataset.reviewResultState === "pass" && validator.dataset.reviewResultFailureCount === "0", label + " review result validator retry did not pass");
    click('[data-action="clear-review-result"]', validator);
    await waitForReviewResult(validator, () => validator.dataset.reviewResultState === "empty" && qs("[data-review-result-input]", validator).value === "", label + " review result validator clear did not reset");
    assert(qs("[data-review-result-saved-card]", validator).dataset.reviewResultSavedState === "saved", label + " review result saved card did not survive input clear");
    reviewResultValidatorVisibleOk = true;
    reviewResultValidatorEmptyOk = true;
    reviewResultValidatorFailureOk = true;
    reviewResultValidatorPassOk = true;
    reviewResultValidatorRetryOk = true;
    reviewResultValidatorSavedOk = true;
    reviewResultValidatorPersistedOk = true;
  }
  async function assertReviewArtifactDiff(selector, expectedKey, expectedKind, message, artifactType = "issue") {
    let diff = qs(selector);
    const text = diff.innerText;
    const openButton = qs("[data-review-artifact-open]", diff);
    const receiptDownload = qs("[data-review-artifact-receipt-download]", diff);
    const receiptCopy = qs("[data-review-artifact-receipt-copy]", diff);
    const detail = () => {
      const checkStatuses = Array.from(diff.querySelectorAll("[data-review-artifact-diff-check]"))
        .map((check) => check.dataset.reviewArtifactDiffCheckId + ":" + check.dataset.reviewArtifactDiffCheckStatus)
        .join(",");
      return " kind=" + diff.dataset.reviewArtifactDiffKind
        + " key=" + diff.dataset.reviewArtifactDiffKey
        + " status=" + diff.dataset.reviewArtifactDiffStatus
        + " checks=" + diff.dataset.reviewArtifactDiffPassCount + "/" + diff.dataset.reviewArtifactDiffCheckCount
        + " checkStatuses=" + checkStatuses
        + " text=" + text.slice(0, 500);
    };
    assert(diff.dataset.reviewArtifactDiffKind === expectedKind, message + " kind did not render; " + detail());
    assert(diff.dataset.reviewArtifactDiffKey === expectedKey, message + " key did not render; " + detail());
    assert(diff.dataset.reviewArtifactDiffStatus === "pass", message + " did not pass; " + detail());
    assert(diff.dataset.reviewArtifactDiffCheckCount === "8" && diff.dataset.reviewArtifactDiffPassCount === "8", message + " checks did not pass; " + detail());
    assert(diff.dataset.reviewArtifactDiffArtifactType === artifactType, message + " artifact type did not render; " + detail());
    assert(diff.dataset.reviewArtifactDiffCreatedId && openButton.dataset.reviewArtifactOpenId === diff.dataset.reviewArtifactDiffCreatedId, message + " open artifact id did not render; " + detail());
    assert(openButton.dataset.reviewArtifactOpenKind === expectedKind && openButton.dataset.reviewArtifactOpenType === artifactType, message + " open artifact metadata did not render; " + detail());
    assert(receiptDownload.getAttribute("download") === "joopark-" + expectedKind + "-artifact-receipt.md", message + " receipt filename did not render; " + detail());
    assert(receiptDownload.getAttribute("href").startsWith("data:text/markdown;charset=utf-8,"), message + " receipt download href did not render; " + detail());
    assert(text.includes("Static draft") && text.includes("Validated result") && text.includes("Created artifact") && text.includes("Payload checksum") && text.includes("validated-review-result") && text.includes("Operational readiness") && text.includes("Execution checklist") && text.includes("Repair evidence linked"), message + " columns did not render; " + detail());
    const items = Array.from(diff.querySelectorAll("[data-review-artifact-diff-item]"));
    const checks = Array.from(diff.querySelectorAll("[data-review-artifact-diff-check]"));
    assert(items.length === 3, message + " did not render 3 artifact columns; " + detail());
    assert(checks.length === 8, message + " did not render 8 artifact checks; " + detail());
    checks.forEach((check) => {
      assert(check.dataset.reviewArtifactDiffCheckStatus === "pass", message + " check did not pass: " + check.dataset.reviewArtifactDiffCheckId + "; " + detail());
    });
    window.__smokeClipboardText = "";
    click("[data-review-artifact-receipt-copy]", diff);
    await waitFor(() => diff.dataset.reviewArtifactReceiptCopied === "true" && window.__smokeClipboardText.includes("# JooPark Review Artifact Receipt"), message + " receipt copy text did not reach clipboard");
    assert(receiptCopy.dataset.reviewArtifactReceiptCopied === "true", message + " receipt copy state did not render; " + detail());
    assert(qs("[data-review-artifact-receipt-copy-status]", diff).textContent.includes("receipt 복사됨"), message + " receipt copy status did not render; " + detail());
    assert(window.__smokeClipboardText.includes(expectedKey) && window.__smokeClipboardText.includes("Diff status: pass") && window.__smokeClipboardText.includes("Payload checksum: fnv1a32-") && window.__smokeClipboardText.includes("## Created Artifact Body") && window.__smokeClipboardText.includes("## Repair Evidence") && window.__smokeClipboardText.includes("JooPark Review Result Post-Repair Receipt"), message + " receipt copy was incomplete");
    reviewResultRepairArtifactLinkOk = true;
    const postRepairArtifactLink = qs("[data-review-post-repair-artifact-link]", diff);
    assert(postRepairArtifactLink.dataset.reviewPostRepairArtifactLinkReady === "true" && postRepairArtifactLink.dataset.reviewPostRepairArtifactLinkKeyMatch === "true" && postRepairArtifactLink.dataset.reviewPostRepairArtifactLinkArtifactReceiptReady === "true", message + " post-repair artifact link did not render ready state; " + detail());
    const postRepairArtifactLinkText = qs("[data-review-post-repair-artifact-link-text]", postRepairArtifactLink).textContent;
    assert(postRepairArtifactLinkText.includes("JooPark Review Post-Repair Artifact Link") && postRepairArtifactLinkText.includes(expectedKey) && postRepairArtifactLinkText.includes("Artifact diff status: pass") && postRepairArtifactLinkText.includes("Saved payload checksum: fnv1a32-"), message + " post-repair artifact link text was incomplete");
    window.__smokeClipboardText = "";
    click("[data-review-post-repair-artifact-link-copy]", postRepairArtifactLink);
    await waitFor(() => postRepairArtifactLink.dataset.reviewPostRepairArtifactLinkCopied === "true" && window.__smokeClipboardText.includes("JooPark Review Post-Repair Artifact Link") && window.__smokeClipboardText.includes(expectedKey), message + " post-repair artifact link copy text did not reach clipboard");
    assert(qs("[data-review-post-repair-artifact-link-copy-status]", postRepairArtifactLink).textContent.includes("link receipt 복사됨"), message + " post-repair artifact link copy status did not render");
    reviewPostRepairArtifactLinkOk = true;
    let compare = qs("[data-review-artifact-receipt-compare]", diff);
    assert(compare.dataset.reviewArtifactReceiptCompareState === "empty", message + " receipt compare initial state did not render; " + detail());
    click('[data-action="insert-review-artifact-receipt"]', diff);
    await waitFor(() => compare.dataset.reviewArtifactReceiptCompareState === "pass" && diff.dataset.reviewArtifactReceiptCompareState === "pass", message + " receipt compare did not pass");
    const compareText = qs("[data-review-artifact-receipt-compare-output]", diff).innerText;
    assert(compareText.includes("Body exact match") && compareText.includes("Checks match") && compareText.includes("pass"), message + " receipt compare output was incomplete; " + compareText);
    const receiptInput = qs("[data-review-artifact-receipt-input]", diff);
    const currentReceipt = receiptInput.value;
    const archivedReceiptWithBodyDrift = currentReceipt.replace("First action:", "First action: restored evidence -");
    fill("[data-review-artifact-receipt-input]", archivedReceiptWithBodyDrift, diff);
    click('[data-action="compare-review-artifact-receipt"]', diff);
    await waitFor(() => compare.dataset.reviewArtifactReceiptCompareState === "fail" && Number(compare.dataset.reviewArtifactReceiptRepairCount || 0) > 0, message + " receipt repair suggestion did not render for body drift");
    const bodyRepairText = qs("[data-review-artifact-receipt-compare-output]", diff).innerText;
    assert(bodyRepairText.includes("Repair suggestions") && bodyRepairText.includes("Body exact match") && bodyRepairText.includes("restore its Created Artifact Body"), message + " receipt body repair suggestion was incomplete; " + bodyRepairText);
    window.__smokeClipboardText = "";
    click("[data-review-artifact-repair-body-copy]", diff);
    await waitFor(() => diff.dataset.reviewArtifactRepairBodyCopied === "true" && window.__smokeClipboardText.includes("First action: restored evidence -"), message + " receipt repair body copy did not reach clipboard");
    assert(!window.__smokeClipboardText.includes("# JooPark Review Artifact Receipt") && qs("[data-review-artifact-repair-copy-status]", diff).textContent.includes("archived body 복사됨"), message + " receipt repair body copy was not body-only");
    click("[data-review-artifact-repair-apply]", diff);
    await waitFor(() => document.querySelector("#modal.open [data-review-artifact-repair-preview]"), message + " receipt repair apply preview did not open");
    const preview = qs("[data-review-artifact-repair-preview]");
    assert(preview.dataset.reviewArtifactRepairPreviewType === artifactType && preview.dataset.reviewArtifactRepairPreviewId === diff.dataset.reviewArtifactDiffCreatedId, message + " receipt repair preview metadata was incomplete");
    const currentPreviewText = qs("[data-review-artifact-repair-preview-current]", preview).textContent;
    const archivedPreviewText = qs("[data-review-artifact-repair-preview-archived]", preview).textContent;
    assert(currentPreviewText.includes("Payload checksum: fnv1a32-") && archivedPreviewText.includes("First action: restored evidence -"), message + " receipt repair preview did not compare current and archived bodies; current=" + currentPreviewText.slice(0, 360) + " archived=" + archivedPreviewText.slice(0, 360));
    await confirmModal();
    const repairApplyDetail = () => {
      const appliedDiff = document.querySelector(selector);
      const createdPreview = appliedDiff ? Array.from(appliedDiff.querySelectorAll("[data-review-artifact-diff-item] pre")).at(-1) : null;
      const createdId = appliedDiff ? appliedDiff.dataset.reviewArtifactDiffCreatedId : "";
      const record = artifactType === "note"
        ? dashboard.notes.find((item) => item.id === createdId)
        : dashboard.issues.find((item) => item.id === createdId);
      return " undo=" + (appliedDiff ? appliedDiff.dataset.reviewArtifactRepairUndoAvailable : "missing")
        + " status=" + (appliedDiff ? appliedDiff.dataset.reviewArtifactDiffStatus : "missing")
        + " createdId=" + createdId
        + " snippet=" + (createdPreview ? createdPreview.textContent.slice(0, 240) : "missing")
        + " recordHasRestoredEvidence=" + (record && String(record.body || "").includes("First action: restored evidence -") ? "true" : "false");
    };
    try {
      await waitFor(() => {
        const appliedDiff = document.querySelector(selector);
        const createdPreview = appliedDiff ? Array.from(appliedDiff.querySelectorAll("[data-review-artifact-diff-item] pre")).at(-1) : null;
        return appliedDiff
          && appliedDiff.dataset.reviewArtifactRepairUndoAvailable === "true"
          && appliedDiff.dataset.reviewArtifactDiffStatus === "pass"
          && createdPreview
          && createdPreview.textContent.includes("First action: restored evidence -");
      }, message + " receipt repair apply did not update the created artifact body");
    } catch (error) {
      throw new Error(error.message + "; " + repairApplyDetail());
    }
    diff = qs(selector);
    const postApplyReceipt = qs("[data-review-artifact-post-apply-receipt]", diff);
    assert(postApplyReceipt.dataset.reviewArtifactPostApplyReceiptReady === "true" && postApplyReceipt.dataset.reviewArtifactPostApplyReceiptStatus === "pass", message + " post-apply fresh receipt prompt did not render ready state");
    assert(qs("[data-review-artifact-post-apply-receipt-download]", postApplyReceipt).getAttribute("download").includes("post-apply-fresh-receipt"), message + " post-apply fresh receipt download did not render");
    window.__smokeClipboardText = "";
    click("[data-review-artifact-post-apply-receipt-copy]", postApplyReceipt);
    await waitFor(() => postApplyReceipt.dataset.reviewArtifactPostApplyReceiptCopied === "true" && window.__smokeClipboardText.includes("# JooPark Review Artifact Receipt"), message + " post-apply fresh receipt copy did not reach clipboard");
    assert(window.__smokeClipboardText.includes("Diff status: pass") && window.__smokeClipboardText.includes(expectedKey) && window.__smokeClipboardText.includes("First action: restored evidence -") && qs("[data-review-artifact-post-apply-receipt-copy-status]", postApplyReceipt).textContent.includes("post-apply fresh receipt 복사됨"), message + " post-apply fresh receipt copy was incomplete");
    assert(qs("[data-review-artifact-repair-undo]", diff), message + " receipt repair undo action did not render");
    click("[data-review-artifact-repair-undo]", diff);
    await waitFor(() => {
      const revertedDiff = document.querySelector(selector);
      const createdPreview = revertedDiff ? Array.from(revertedDiff.querySelectorAll("[data-review-artifact-diff-item] pre")).at(-1) : null;
      return revertedDiff
        && revertedDiff.dataset.reviewArtifactRepairUndoAvailable === "false"
        && revertedDiff.dataset.reviewArtifactDiffStatus === "pass"
        && createdPreview
        && createdPreview.textContent.includes("Payload checksum: fnv1a32-")
        && !createdPreview.textContent.includes("First action: restored evidence -");
    }, message + " receipt repair undo did not restore the created artifact body");
    diff = qs(selector);
    compare = qs("[data-review-artifact-receipt-compare]", diff);
    fill("[data-review-artifact-receipt-input]", currentReceipt.replace("Diff status: pass", "Diff status: pending"), diff);
    click('[data-action="compare-review-artifact-receipt"]', diff);
    await waitFor(() => compare.dataset.reviewArtifactReceiptCompareState === "fail" && diff.dataset.reviewArtifactReceiptCompareState === "fail", message + " receipt compare did not fail on tampered receipt");
    const statusRepairText = qs("[data-review-artifact-receipt-compare-output]", diff).innerText;
    assert(statusRepairText.includes("Diff status") && statusRepairText.includes("Archive a fresh receipt"), message + " receipt compare tamper repair did not name diff status");
    window.__smokeClipboardText = "";
    click("[data-review-artifact-repair-receipt-copy]", diff);
    await waitFor(() => diff.dataset.reviewArtifactRepairReceiptCopied === "true" && window.__smokeClipboardText.includes("# JooPark Review Artifact Receipt"), message + " receipt repair fresh receipt copy did not reach clipboard");
    assert(window.__smokeClipboardText.includes("Diff status: pass") && window.__smokeClipboardText.includes(expectedKey) && qs("[data-review-artifact-repair-copy-status]", diff).textContent.includes("fresh receipt 복사됨"), message + " receipt repair fresh receipt copy was incomplete");
    click('[data-action="clear-review-artifact-receipt"]', diff);
    await waitFor(() => compare.dataset.reviewArtifactReceiptCompareState === "empty" && qs("[data-review-artifact-receipt-input]", diff).value === "", message + " receipt compare clear did not reset");
    click("[data-review-artifact-open]", diff);
    if (artifactType === "note") {
      await waitFor(() => document.querySelector("#modal.open #noteForm"), message + " note body did not open");
      const body = qs('#noteForm [name="body"]').value;
      assert(body.includes("## Saved Validated Result") && body.includes("Payload checksum: fnv1a32-") && body.includes(expectedKey) && body.includes("## Operational Readiness") && body.includes("## Execution Checklist") && body.includes("Decision gate:") && body.includes("## Repair Evidence") && body.includes("JooPark Review Result Post-Repair Receipt"), message + " opened note body was incomplete");
      click('#modal [data-action="close-modal"]');
      await waitFor(() => !document.querySelector("#modal.open"), message + " note modal did not close");
    } else {
      await waitFor(() => document.querySelector("#sheet.open [data-sheet-artifact-body]"), message + " issue body did not open");
      const sheetText = qs("#sheet").innerText;
      assert(sheetText.includes("source kind") && sheetText.includes("validated-review-result") && sheetText.includes("Payload checksum: fnv1a32-") && sheetText.includes(expectedKey) && sheetText.includes("## Operational Readiness") && sheetText.includes("## Execution Checklist") && sheetText.includes("Decision gate:") && sheetText.includes("## Repair Evidence") && sheetText.includes("JooPark Review Result Post-Repair Receipt"), message + " opened issue body was incomplete");
      assert(sheetText.includes("담당") && (sheetText.includes("박주호") || sheetText.includes("서기태")) && sheetText.includes("마감") && sheetText.includes("assignee confidence") && sheetText.includes("assignee source") && sheetText.includes("execution owner") && sheetText.includes("first action") && sheetText.includes("execution checklist") && sheetText.includes("decision gate") && sheetText.includes("fallback"), message + " opened issue tracker fields were incomplete");
      click('#sheet [data-action="close-sheet"]');
      await waitFor(() => !document.querySelector("#sheet.open"), message + " issue sheet did not close");
      reviewOperationalTrackerFieldOk = true;
    }
    reviewArtifactOperationalReadinessOk = true;
    reviewArtifactReceiptCompareOk = true;
    reviewArtifactReceiptRepairSuggestionOk = true;
    reviewArtifactReceiptRepairCopyOk = true;
    reviewArtifactReceiptRepairApplyOk = true;
    reviewArtifactPostApplyFreshReceiptOk = true;
    return diff;
  }
  async function nav(view) {
    click('[data-action="nav-to"][data-view="' + view + '"]');
    await waitFor(() => document.body.dataset.view === view && !document.getElementById("view-" + view).hidden, "route not ready: " + view);
    await sleep(120);
  }
  const systemEvidencePanelChecks = [
      ["[data-system-workflow-ui-install-plan]", "workflowUiInstallLoaded"],
      ["[data-system-publish-dispatch-plan]", "publishDispatchLoaded"],
      ["[data-system-remote-workflow-file-check]", "remoteWorkflowFileLoaded"],
      ["[data-system-publish-evidence]", "publishEvidenceLoaded"],
      ["[data-system-launch-execution-packet]", "launchExecutionLoaded"],
      ["[data-system-launch-readiness-refresh]", "launchReadinessRefreshLoaded"],
      ["[data-system-verify-workspace-summary]", "verifyWorkspaceSummaryLoaded"],
      ["[data-system-release-gate-cache]", "releaseGateCacheLoaded"],
      ["[data-system-release-provenance]", "releaseProvenanceLoaded"],
      ["[data-system-output-quality-audit]", "outputQualityAuditLoaded"],
      ["[data-system-source-snapshots]", "sourceSnapshotLoaded"],
      ["[data-system-github-project-discovery]", "githubProjectDiscoveryLoaded"],
    ];
  function systemEvidencePanelsLoaded() {
    return systemEvidencePanelChecks.every(([selector, key]) => {
      const node = document.querySelector(selector);
      if (selector === "[data-system-verify-workspace-summary]" && !strictVerifyWorkspaceSummary) {
        return !!node &&
          node.dataset.verifyWorkspaceSummarySource === "autoresearch-results/verify-workspace-summary.json" &&
          node.dataset.verifyWorkspaceSummaryCommand === "npm run verify:full";
      }
      return node?.dataset?.[key] === "true";
    });
  }
  function systemEvidencePanelDiagnostics() {
    return systemEvidencePanelChecks.map(([selector, key]) => {
      const node = document.querySelector(selector);
      const value = node?.dataset?.[key] || "";
      return {
        selector,
        key,
        present: !!node,
        value,
        ok: selector === "[data-system-verify-workspace-summary]" && !strictVerifyWorkspaceSummary
          ? !!node &&
            node.dataset.verifyWorkspaceSummarySource === "autoresearch-results/verify-workspace-summary.json" &&
            node.dataset.verifyWorkspaceSummaryCommand === "npm run verify:full"
          : value === "true",
      };
    });
  }
  async function waitForSystemEvidencePanels() {
    try {
      await waitFor(systemEvidencePanelsLoaded, "system evidence panels did not all load", 30000);
    } catch (error) {
      throw new Error(error.message + ": " + JSON.stringify(systemEvidencePanelDiagnostics().filter((item) => !item.ok)));
    }
    await sleep(200);
    try {
      await waitFor(systemEvidencePanelsLoaded, "system evidence panels did not stay loaded after render settle", 30000);
    } catch (error) {
      throw new Error(error.message + ": " + JSON.stringify(systemEvidencePanelDiagnostics().filter((item) => !item.ok)));
    }
  }
  async function confirmModal() {
    assert(document.querySelector("#modal.open"), "modal is not open");
    click('#modal [data-action="modal-confirm"]');
    await waitFor(() => !document.querySelector("#modal.open"), "modal did not close after confirm");
    await sleep(120);
  }
  async function runStep(name, fn) {
    const before = snapshot();
    try {
      await fn();
      steps.push({ name, status: "pass", before, after: snapshot() });
    } catch (error) {
      failures.push(name + ": " + error.message);
      steps.push({ name, status: "fail", error: error.message, stack: error.stack || "", before, after: snapshot() });
    }
  }
  function snapshot() {
    if (typeof dashboard === "undefined") {
      return { view: document.body.dataset.view || "", storageBytes: (localStorage.getItem(storeKey) || "").length };
    }
    return {
      view: dashboard.currentView,
      events: dashboard.events.length,
      todos: dashboard.todos.length,
      notes: dashboard.notes.length,
      habits: Array.isArray(dashboard.habits) ? dashboard.habits.length : 0,
      projects: dashboard.projects.length,
      issues: dashboard.issues.length,
      tasks: dashboard.gantt.tasks.length,
      team: dashboard.team.length,
      dbInstances: dashboard.dbInstances.length,
      tables: dashboard.schemas.reduce((sum, schema) => sum + schema.databases.reduce((dbSum, db) => dbSum + db.tables.length, 0), 0),
      queries: dashboard.queries.length,
      migrations: dashboard.migrations.length,
      storageBytes: (localStorage.getItem(storeKey) || "").length,
    };
  }
  function savedPayload() {
    const raw = localStorage.getItem(storeKey);
    assert(raw, "v3 localStorage payload is missing");
    return JSON.parse(raw);
  }

  await waitFor(() => document.readyState === "complete" && typeof dashboard !== "undefined", "app did not expose dashboard state");
  await sleep(900);
  assert(document.body.dataset.view === "home", "expected home view at boot");

	  await runStep("home quick links expose and navigate routes", async () => {
	    await nav("home");
	    const homeNavControls = qsa('#view-home [data-action="nav-to"][data-view]');
    const homeLinkViews = [...new Set(homeNavControls.map((node) => node.dataset.view).filter(Boolean))];
    const homeNavAnchors = qsa('#view-home a[data-action="nav-to"][data-view]');
    const missingTargets = homeLinkViews.filter((viewName) => !document.getElementById("view-" + viewName));
    const expectedHomeTargets = ["cal", "pm-portfolio", "pm-kanban", "pm-gantt", "pm-team", "dbm-instances", "dbm-schema", "dbm-queries", "dbm-backups", "system"];
    const missingHomeTargets = expectedHomeTargets.filter((viewName) => !homeLinkViews.includes(viewName));
    assert(homeLinkViews.length >= expectedHomeTargets.length, "home route link coverage unexpectedly small: " + homeLinkViews.join(", "));
    assert(missingTargets.length === 0, "home route links point at missing views: " + missingTargets.join(", "));
    assert(missingHomeTargets.length === 0, "home route links missing expected targets: " + missingHomeTargets.join(", "));
    for (const link of homeNavAnchors) {
      const viewName = link.dataset.view;
      assert(link.getAttribute("href") === "#" + viewName, "home quick link href did not expose route: " + viewName);
      assert(new URL(link.href).hash === "#" + viewName, "home quick link absolute href did not resolve route: " + viewName);
    }
    for (const viewName of homeLinkViews) {
      const selector = '#view-home [data-action="nav-to"][data-view="' + viewName + '"]';
      click(selector);
      await waitFor(() => document.body.dataset.view === viewName && !document.getElementById("view-" + viewName).hidden, "home quick link did not navigate: " + viewName);
      await nav("home");
    }
	    homeQuickLinksNavigateOk = true;
	  });

  await runStep("home execution queue ranks todo and PM issue work", async () => {
    await nav("home");
    let queue = qs("#view-home [data-home-execution-queue]");
    let items = qsa("[data-home-execution-queue-item]", queue);
    const itemTypes = new Set(items.map((item) => item.dataset.homeExecutionQueueType));
    const scores = items.map((item) => Number(item.dataset.homeExecutionQueueScore || 0));
    assert(window.JooParkHomeExecutionView?.version === "joopark-home-execution-view/v1", "home execution view module did not load");
    assert(queue.dataset.homeExecutionQueueSource === "linear_todoist_priority_due_benchmark", "home execution queue source did not render");
    assert(queue.dataset.homeExecutionQueueExplainable === "true", "home execution queue explainability flag did not render");
    assert(queue.dataset.homeExecutionQueueBucketed === "true", "home execution queue focus buckets did not render");
    assert(Number(queue.dataset.homeExecutionQueueItemCount || 0) >= 4 && Number(queue.dataset.homeExecutionQueueTotalCandidateCount || 0) >= Number(queue.dataset.homeExecutionQueueItemCount || 0), "home execution queue counts were incomplete");
    assert(Number(queue.dataset.homeExecutionQueueTodoCount || 0) >= 1 && Number(queue.dataset.homeExecutionQueueIssueCount || 0) >= 1, "home execution queue did not combine todos and PM issues");
    assert(Number(queue.dataset.homeExecutionQueueOverdueCount || 0) >= 1 && Number(queue.dataset.homeExecutionQueueTodayCount || 0) >= 1 && Number(queue.dataset.homeExecutionQueueUpcomingCount || 0) >= 1, "home execution queue did not expose overdue today and upcoming signals");
    assert(queue.dataset.homeExecutionQueueBuckets.includes("overdue:") && queue.dataset.homeExecutionQueueBuckets.includes("today:") && queue.dataset.homeExecutionQueueBuckets.includes("upcoming:"), "home execution queue bucket key did not include every due bucket");
    assert(queue.dataset.homeExecutionQueueActiveBucket === "overdue", "home execution queue active bucket did not prioritize overdue work");
    const bucketItems = qsa("[data-home-execution-bucket]", queue);
    const dueBucketItems = bucketItems.filter((bucket) => bucket.dataset.homeExecutionBucketKey !== "all");
    const bucketTotal = dueBucketItems.reduce((sum, bucket) => sum + Number(bucket.dataset.homeExecutionBucketCount || 0), 0);
    assert(dueBucketItems.length >= 3 && bucketTotal === Number(queue.dataset.homeExecutionQueueTotalCandidateCount || 0), "home execution queue focus bucket counts did not match total candidates");
    assert(bucketItems.every((bucket) => Number(bucket.dataset.homeExecutionBucketTodoCount || 0) + Number(bucket.dataset.homeExecutionBucketIssueCount || 0) === Number(bucket.dataset.homeExecutionBucketCount || 0)), "home execution queue bucket type counts were inconsistent");
    assert(queue.dataset.homeExecutionQueueFilterable === "true" && queue.dataset.homeExecutionQueueBucketFilter === "all", "home execution queue bucket filter default did not render");
    assert(qs("[data-home-execution-bucket-key='all'][data-home-execution-bucket-selected='true'][aria-pressed='true']", queue), "home execution queue all bucket was not selected by default");
    let filterSummary = qs("[data-home-execution-filter-summary]", queue);
    assert(filterSummary.dataset.homeExecutionFilterSummaryActive === "false" && filterSummary.dataset.homeExecutionFilterSummaryBucket === "all", "home execution queue filter summary default did not render");
    assert(queue.dataset.homeExecutionQueueFilterSummary === filterSummary.dataset.homeExecutionFilterSummaryKey && Number(filterSummary.dataset.homeExecutionFilteredCount || 0) === Number(queue.dataset.homeExecutionQueueTotalCandidateCount || -1), "home execution queue filter summary count did not match all candidates");
    assert(Number(filterSummary.dataset.homeExecutionFilteredTodoCount || 0) + Number(filterSummary.dataset.homeExecutionFilteredIssueCount || 0) === Number(filterSummary.dataset.homeExecutionFilteredCount || -1) && Number(queue.dataset.homeExecutionQueueFilteredTodoCount || 0) === Number(queue.dataset.homeExecutionQueueTodoCount || -1) && Number(queue.dataset.homeExecutionQueueFilteredIssueCount || 0) === Number(queue.dataset.homeExecutionQueueIssueCount || -1), "home execution queue filter composition did not match all candidates");
    assert(Number(filterSummary.dataset.homeExecutionHiddenCandidateCount || 0) === Number(queue.dataset.homeExecutionQueueFilteredCandidateCount || 0) - Number(queue.dataset.homeExecutionQueueItemCount || 0) && filterSummary.textContent.includes(Number(filterSummary.dataset.homeExecutionHiddenCandidateCount || 0) > 0 ? "대기" : "모두 표시"), "home execution queue filter window did not expose hidden candidates");
    assert(queue.dataset.homeExecutionQueueRankWindow === queue.dataset.homeExecutionQueueItemCount + ":" + queue.dataset.homeExecutionQueueFilteredCandidateCount && filterSummary.dataset.homeExecutionRankWindowCount === queue.dataset.homeExecutionQueueItemCount && filterSummary.dataset.homeExecutionRankWindowTotal === queue.dataset.homeExecutionQueueFilteredCandidateCount && filterSummary.textContent.includes("상위"), "home execution queue filter rank window did not render");
    assert(queue.dataset.homeExecutionQueueScoreWindow === String(scores[0]) + ":" + String(scores[scores.length - 1]) && filterSummary.dataset.homeExecutionScoreWindowTop === String(scores[0]) && filterSummary.dataset.homeExecutionScoreWindowFloor === String(scores[scores.length - 1]), "home execution queue score window did not render");
    const dueDriverCount = items.filter((item) => item.dataset.homeExecutionQueueDueState === "overdue" || item.dataset.homeExecutionQueueDueState === "today").length;
    const priorityDriverCount = items.filter((item) => item.dataset.homeExecutionQueuePriority === "crit" || item.dataset.homeExecutionQueuePriority === "high").length;
    const activeDriverCount = items.filter((item) => (item.dataset.homeExecutionQueueReason || "").includes("status:in-progress") || (item.dataset.homeExecutionQueueReason || "").includes("status:review")).length;
    assert(queue.dataset.homeExecutionQueueScoreDriver === dueDriverCount + ":" + priorityDriverCount + ":" + activeDriverCount && filterSummary.dataset.homeExecutionScoreDriverDue === String(dueDriverCount) && filterSummary.dataset.homeExecutionScoreDriverPriority === String(priorityDriverCount) && filterSummary.dataset.homeExecutionScoreDriverActive === String(activeDriverCount), "home execution queue score driver summary did not render");
    const leadDriverLabels = { due: "마감", priority: "고우선", active: "진행" };
    const leadDriverRows = [{ key: "due", count: dueDriverCount }, { key: "priority", count: priorityDriverCount }, { key: "active", count: activeDriverCount }];
    const leadDriverCount = Math.max(0, ...leadDriverRows.map((driver) => driver.count));
    const leadDrivers = leadDriverRows.filter((driver) => driver.count === leadDriverCount && driver.count > 0);
    const leadDriverKey = leadDrivers.length ? leadDrivers.map((driver) => driver.key).join("+") : "baseline";
    const leadDriverLabel = leadDrivers.length > 1 ? "공동 " + leadDrivers.map((driver) => leadDriverLabels[driver.key]).join("+") : (leadDrivers[0] ? leadDriverLabels[leadDrivers[0].key] : "기본");
    assert(queue.dataset.homeExecutionQueueLeadDriver === leadDriverKey && filterSummary.dataset.homeExecutionLeadDriver === leadDriverKey && filterSummary.dataset.homeExecutionLeadDriverLabel === leadDriverLabel && filterSummary.textContent.includes("대표 " + leadDriverLabel), "home execution queue lead driver did not render");
    assert(queue.dataset.homeExecutionQueueLeadDriverCount === String(leadDriverCount) && filterSummary.dataset.homeExecutionLeadDriverCount === String(leadDriverCount) && filterSummary.textContent.includes(leadDriverCount + "/" + items.length), "home execution queue lead driver count did not render");
    assert(queue.dataset.homeExecutionQueueLeadDriverTieCount === String(leadDrivers.length) && filterSummary.dataset.homeExecutionLeadDriverTieCount === String(leadDrivers.length) && (leadDrivers.length < 2 || filterSummary.textContent.includes("공동")), "home execution queue lead driver tie did not render");
    assert(filterSummary.dataset.homeExecutionReceiptCompact === "true" && filterSummary.textContent.includes("상위") && filterSummary.textContent.includes("대표") && !filterSummary.textContent.includes("근거") && !filterSummary.textContent.includes("점수"), "home execution queue compact receipt did not render");
    assert(filterSummary.dataset.homeExecutionReceiptDetail === "accessible" && filterSummary.getAttribute("title")?.includes("점수") && filterSummary.getAttribute("title")?.includes("근거") && filterSummary.getAttribute("aria-label")?.includes("실행 큐 상세"), "home execution queue accessible receipt detail did not render");
    let receiptDescription = qs("#" + filterSummary.getAttribute("aria-describedby"), queue);
    assert(filterSummary.getAttribute("role") === "note" && filterSummary.getAttribute("tabindex") === "0" && receiptDescription?.classList.contains("sr-only") && receiptDescription.dataset.homeExecutionReceiptDescription !== undefined && receiptDescription.textContent.includes("점수") && receiptDescription.textContent.includes("근거"), "home execution queue described receipt detail did not render");
    assert(itemTypes.has("todo") && itemTypes.has("issue"), "home execution queue rendered without both item types");
    assert(scores.every((score, index) => index === 0 || scores[index - 1] >= score), "home execution queue was not sorted by score");
    assert(items[0].dataset.homeExecutionQueueRank === "1" && items[0].dataset.homeExecutionQueueType === "issue" && items[0].dataset.homeExecutionQueuePriority === "crit", "home execution queue top item did not prioritize critical PM issue work");
    assert(queue.textContent.includes("오늘 실행 큐") && queue.textContent.includes("긴급") && queue.textContent.includes("이번 주") && queue.textContent.includes("issue") && queue.textContent.includes("Critical"), "home execution queue visible summary was incomplete");
    const reasonItems = items.filter((item) => item.dataset.homeExecutionQueueReason && item.dataset.homeExecutionScoreBreakdown);
    assert(reasonItems.length === items.length, "home execution queue did not expose score reasons for every item");
    const firstReasonKeys = qsa("[data-home-execution-reason-key]", items[0]).map((chip) => chip.dataset.homeExecutionReasonKey);
    assert(firstReasonKeys.includes("due:overdue") && firstReasonKeys.includes("priority:crit") && firstReasonKeys.some((key) => key.startsWith("status:")), "home execution queue top issue rationale did not expose due priority and status");
    const todoReasonItem = items.find((item) => item.dataset.homeExecutionQueueType === "todo");
    assert(todoReasonItem && qsa("[data-home-execution-reason-key]", todoReasonItem).some((chip) => chip.dataset.homeExecutionReasonKey.startsWith("priority:")), "home execution queue todo rationale did not expose priority");
    assert(qsa("[data-home-execution-queue-quick='todo-complete']", queue).length >= 1 && qsa("[data-home-execution-queue-quick='issue-next']", queue).length >= 1, "home execution queue quick actions did not render for both work types");
    click("[data-home-execution-bucket-key='today']", queue);
    await waitFor(() => document.querySelector("#view-home [data-home-execution-queue]")?.dataset.homeExecutionQueueBucketFilter === "today", "home execution queue bucket filter did not switch to today");
    queue = qs("#view-home [data-home-execution-queue]");
    items = qsa("[data-home-execution-queue-item]", queue);
    filterSummary = qs("[data-home-execution-filter-summary]", queue);
    assert(Number(queue.dataset.homeExecutionQueueFilteredCandidateCount || 0) === Number(queue.dataset.homeExecutionQueueTodayCount || -1), "home execution queue today bucket count did not match filtered candidates");
    assert(items.length >= 1 && items.every((item) => item.dataset.homeExecutionQueueDueState === "today"), "home execution queue today bucket filter rendered non-today work");
    assert(qs("[data-home-execution-bucket-key='today'][data-home-execution-bucket-selected='true'][aria-pressed='true']", queue), "home execution queue today bucket selected state did not render");
    assert(filterSummary.dataset.homeExecutionFilterSummaryActive === "true" && filterSummary.dataset.homeExecutionFilterSummaryBucket === "today" && Number(filterSummary.dataset.homeExecutionFilteredCount || 0) === Number(queue.dataset.homeExecutionQueueTodayCount || -1) && filterSummary.textContent.includes("오늘"), "home execution queue filter summary did not switch to today");
    assert(Number(filterSummary.dataset.homeExecutionFilteredTodoCount || 0) + Number(filterSummary.dataset.homeExecutionFilteredIssueCount || 0) === Number(filterSummary.dataset.homeExecutionFilteredCount || -1) && filterSummary.textContent.includes("todo") && filterSummary.textContent.includes("issue"), "home execution queue filter composition did not switch with today filter");
    assert(Number(filterSummary.dataset.homeExecutionHiddenCandidateCount || 0) === Number(queue.dataset.homeExecutionQueueFilteredCandidateCount || 0) - Number(queue.dataset.homeExecutionQueueItemCount || 0), "home execution queue filter window did not switch with today filter");
    assert(queue.dataset.homeExecutionQueueRankWindow === queue.dataset.homeExecutionQueueItemCount + ":" + queue.dataset.homeExecutionQueueFilteredCandidateCount && filterSummary.dataset.homeExecutionRankWindowCount === queue.dataset.homeExecutionQueueItemCount && filterSummary.dataset.homeExecutionRankWindowTotal === queue.dataset.homeExecutionQueueFilteredCandidateCount && filterSummary.textContent.includes("상위"), "home execution queue filter rank window did not switch with today filter");
    const todayScores = items.map((item) => Number(item.dataset.homeExecutionQueueScore || 0));
    assert(queue.dataset.homeExecutionQueueScoreWindow === String(todayScores[0]) + ":" + String(todayScores[todayScores.length - 1]) && filterSummary.dataset.homeExecutionScoreWindowTop === String(todayScores[0]) && filterSummary.dataset.homeExecutionScoreWindowFloor === String(todayScores[todayScores.length - 1]), "home execution queue score window did not switch with today filter");
    const todayDueDriverCount = items.filter((item) => item.dataset.homeExecutionQueueDueState === "overdue" || item.dataset.homeExecutionQueueDueState === "today").length;
    const todayPriorityDriverCount = items.filter((item) => item.dataset.homeExecutionQueuePriority === "crit" || item.dataset.homeExecutionQueuePriority === "high").length;
    const todayActiveDriverCount = items.filter((item) => (item.dataset.homeExecutionQueueReason || "").includes("status:in-progress") || (item.dataset.homeExecutionQueueReason || "").includes("status:review")).length;
    assert(queue.dataset.homeExecutionQueueScoreDriver === todayDueDriverCount + ":" + todayPriorityDriverCount + ":" + todayActiveDriverCount && filterSummary.dataset.homeExecutionScoreDriverDue === String(todayDueDriverCount) && filterSummary.dataset.homeExecutionScoreDriverPriority === String(todayPriorityDriverCount) && filterSummary.dataset.homeExecutionScoreDriverActive === String(todayActiveDriverCount), "home execution queue score driver summary did not switch with today filter");
    const todayLeadDriverRows = [{ key: "due", count: todayDueDriverCount }, { key: "priority", count: todayPriorityDriverCount }, { key: "active", count: todayActiveDriverCount }];
    const todayLeadDriverCount = Math.max(0, ...todayLeadDriverRows.map((driver) => driver.count));
    const todayLeadDrivers = todayLeadDriverRows.filter((driver) => driver.count === todayLeadDriverCount && driver.count > 0);
    const todayLeadDriverKey = todayLeadDrivers.length ? todayLeadDrivers.map((driver) => driver.key).join("+") : "baseline";
    const todayLeadDriverLabel = todayLeadDrivers.length > 1 ? "공동 " + todayLeadDrivers.map((driver) => leadDriverLabels[driver.key]).join("+") : (todayLeadDrivers[0] ? leadDriverLabels[todayLeadDrivers[0].key] : "기본");
    assert(queue.dataset.homeExecutionQueueLeadDriver === todayLeadDriverKey && filterSummary.dataset.homeExecutionLeadDriver === todayLeadDriverKey && filterSummary.dataset.homeExecutionLeadDriverLabel === todayLeadDriverLabel && filterSummary.textContent.includes("대표 " + todayLeadDriverLabel), "home execution queue lead driver did not switch with today filter");
    assert(queue.dataset.homeExecutionQueueLeadDriverCount === String(todayLeadDriverCount) && filterSummary.dataset.homeExecutionLeadDriverCount === String(todayLeadDriverCount) && filterSummary.textContent.includes(todayLeadDriverCount + "/" + items.length), "home execution queue lead driver count did not switch with today filter");
    assert(queue.dataset.homeExecutionQueueLeadDriverTieCount === String(todayLeadDrivers.length) && filterSummary.dataset.homeExecutionLeadDriverTieCount === String(todayLeadDrivers.length) && (todayLeadDrivers.length < 2 || filterSummary.textContent.includes("공동")), "home execution queue lead driver tie did not switch with today filter");
    assert(filterSummary.dataset.homeExecutionReceiptCompact === "true" && filterSummary.textContent.includes("상위") && filterSummary.textContent.includes("대표") && !filterSummary.textContent.includes("근거") && !filterSummary.textContent.includes("점수"), "home execution queue compact receipt did not switch with today filter");
    assert(filterSummary.dataset.homeExecutionReceiptDetail === "accessible" && filterSummary.getAttribute("title")?.includes("점수") && filterSummary.getAttribute("title")?.includes("근거") && filterSummary.getAttribute("aria-label")?.includes("오늘 실행 큐 상세"), "home execution queue accessible receipt detail did not switch with today filter");
    receiptDescription = qs("#" + filterSummary.getAttribute("aria-describedby"), queue);
    assert(filterSummary.getAttribute("role") === "note" && filterSummary.getAttribute("tabindex") === "0" && receiptDescription?.classList.contains("sr-only") && receiptDescription.dataset.homeExecutionReceiptDescription !== undefined && receiptDescription.textContent.includes("점수") && receiptDescription.textContent.includes("근거"), "home execution queue described receipt detail did not switch with today filter");
    click("[data-home-execution-filter-summary-reset]", filterSummary);
    await waitFor(() => document.querySelector("#view-home [data-home-execution-queue]")?.dataset.homeExecutionQueueBucketFilter === "all", "home execution queue bucket filter did not reset to all");
    queue = qs("#view-home [data-home-execution-queue]");
    items = qsa("[data-home-execution-queue-item]", queue);
    assert(qs("[data-home-execution-bucket-key='all'][data-home-execution-bucket-selected='true'][aria-pressed='true']", queue), "home execution queue all bucket selected state did not return");
    assert(qs("[data-home-execution-filter-summary]", queue).dataset.homeExecutionFilterSummaryActive === "false", "home execution queue filter summary did not reset to all");
    homeExecutionQueueFilterSummaryOk = true;
    homeExecutionQueueFilterCompositionOk = true;
    homeExecutionQueueFilterWindowOk = true;
    homeExecutionQueueFilterRankWindowOk = true;
    homeExecutionQueueScoreWindowOk = true;
    homeExecutionQueueScoreDriverOk = true;
    homeExecutionQueueLeadDriverOk = true;
    homeExecutionQueueLeadDriverCountOk = true;
    homeExecutionQueueLeadDriverTieOk = true;
    homeExecutionQueueReceiptCompactOk = true;
    homeExecutionQueueReceiptDetailOk = true;
    homeExecutionQueueReceiptDescriptionOk = true;
    homeExecutionQueueBucketFilterOk = true;
    const firstIssue = items.find((item) => item.dataset.homeExecutionQueueType === "issue");
    const firstIssueButton = qs("[data-action='open-issue'][data-issue-id]", firstIssue);
    click("[data-action='open-issue'][data-issue-id]", firstIssue);
    await waitFor(() => document.querySelector("#sheet.open") && document.querySelector("#sheet").textContent.includes(firstIssueButton.dataset.issueId), "home execution queue issue action did not open issue sheet");
    closeSheet();
    await waitFor(() => !document.querySelector("#sheet.open"), "home execution queue issue sheet did not close");
    homeExecutionViewModuleOk = true;
    homeExecutionQueueOk = true;
    homeExecutionQueueExplainabilityOk = true;
    homeExecutionQueueBucketsOk = true;
  });

  await runStep("home execution queue quick actions complete todos and advance issues", async () => {
    await nav("home");
    let queue = qs("#view-home [data-home-execution-queue]");
    const todoAction = qs("[data-home-execution-queue-quick='todo-complete'][data-todo-id]", queue);
    const todoId = todoAction.dataset.todoId;
    const todoBefore = dashboard.todos.find((todo) => todo.id === todoId);
    assert(todoBefore && todoBefore.done === false, "home execution queue todo quick action did not target an open todo");
    click("[data-home-execution-queue-quick='todo-complete'][data-todo-id='" + todoId + "']", queue);
    await waitFor(() => dashboard.todos.find((todo) => todo.id === todoId)?.done === true, "home execution queue todo quick action did not complete the todo");
    assert(savedPayload().todos.find((todo) => todo.id === todoId)?.done === true, "home execution queue todo quick action was not persisted");
    await waitFor(() => !document.querySelector("#view-home [data-home-execution-queue-item] [data-home-execution-queue-quick='todo-complete'][data-todo-id='" + todoId + "']"), "completed todo remained as an actionable home queue item");
    click("#toastRegion [data-toast-action]");
    await waitFor(() => dashboard.todos.find((todo) => todo.id === todoId)?.done === false, "home execution queue todo quick undo did not restore the todo");
    assert(savedPayload().todos.find((todo) => todo.id === todoId)?.done === false, "home execution queue todo quick undo was not persisted");
    await waitFor(() => document.querySelector("#view-home [data-home-execution-queue-item] [data-home-execution-queue-quick='todo-complete'][data-todo-id='" + todoId + "']"), "home execution queue todo quick undo did not return the item");
    await waitFor(() => qsa("#toastRegion [data-toast-action]").length === 0, "home execution queue todo quick undo action did not dismiss");

    queue = qs("#view-home [data-home-execution-queue]");
    const issueAction = qs("[data-home-execution-queue-quick='issue-next'][data-issue-id]", queue);
    const issueId = issueAction.dataset.issueId;
    const expectedStatus = issueAction.dataset.status;
    const issueBeforeStatus = dashboard.issues.find((issue) => issue.id === issueId)?.status;
    assert(issueBeforeStatus && expectedStatus && issueBeforeStatus !== expectedStatus, "home execution queue issue quick action did not expose the next status");
    click("[data-home-execution-queue-quick='issue-next'][data-issue-id='" + issueId + "']", queue);
    await waitFor(() => dashboard.issues.find((issue) => issue.id === issueId)?.status === expectedStatus, "home execution queue issue quick action did not advance the issue status");
    assert(savedPayload().issues.find((issue) => issue.id === issueId)?.status === expectedStatus, "home execution queue issue quick action was not persisted");
    click("#toastRegion [data-toast-action]");
    await waitFor(() => dashboard.issues.find((issue) => issue.id === issueId)?.status === issueBeforeStatus, "home execution queue issue quick undo did not restore the issue status");
    assert(savedPayload().issues.find((issue) => issue.id === issueId)?.status === issueBeforeStatus, "home execution queue issue quick undo was not persisted");
    await waitFor(() => qsa("#toastRegion [data-toast-action]").length === 0, "home execution queue issue quick undo action did not dismiss");
    homeExecutionQueueQuickActionsOk = true;
    homeExecutionQueueQuickUndoOk = true;
  });

  await runStep("route deep links preserve browser history", async () => {
    await nav("home");
    const startLength = history.length;
    await nav("todo");
    assert(location.hash === "#todo" && document.body.dataset.routeView === "todo" && document.body.dataset.routeHash === "#todo" && document.body.dataset.routeDeepLinkCoverage === "1", "todo route hash did not sync with view state");
    await nav("notes");
    assert(location.hash === "#notes" && document.body.dataset.routeView === "notes" && document.body.dataset.routeHash === "#notes" && document.body.dataset.routeDeepLinkCoverage === "1", "notes route hash did not sync with view state");
    assert(history.length >= startLength + 2, "route navigation did not add browser history entries");
    history.back();
    await waitFor(() => document.body.dataset.view === "todo" && location.hash === "#todo" && !document.getElementById("view-todo").hidden, "browser back did not restore todo route");
    history.back();
    await waitFor(() => document.body.dataset.view === "home" && location.hash === "#home" && !document.getElementById("view-home").hidden, "browser back did not restore home route");
    history.forward();
    await waitFor(() => document.body.dataset.view === "todo" && location.hash === "#todo" && !document.getElementById("view-todo").hidden, "browser forward did not restore todo route");
    history.forward();
    await waitFor(() => document.body.dataset.view === "notes" && location.hash === "#notes" && !document.getElementById("view-notes").hidden, "browser forward did not restore notes route");
    history.pushState({ view: "missing-route" }, "", "#missing-route");
    window.dispatchEvent(new HashChangeEvent("hashchange"));
    await waitFor(() => document.body.dataset.view === "home" && location.hash === "#home" && !document.getElementById("view-home").hidden, "invalid route hash did not recover to home");
    routeDeepLinkOk = true;
  });

  await runStep("command palette nav commands cover app routes", async () => {
    assert(window.JooParkCommandPalette && Array.isArray(window.JooParkCommandPalette.navCommands), "command palette nav command metadata was not exposed");
    const expectedViews = qsa("main .view[id^='view-']")
      .map((view) => view.id.replace(/^view-/, ""))
      .filter(Boolean);
    const navViews = window.JooParkCommandPalette.navCommands.map((item) => item.view);
    const missing = expectedViews.filter((view) => !navViews.includes(view));
    const unexpected = navViews.filter((view) => !expectedViews.includes(view));
    const duplicateNavViews = navViews.filter((view, index, list) => list.indexOf(view) !== index);
    const incompleteNavCommands = window.JooParkCommandPalette.navCommands
      .filter((item) => !item.view || !item.label || !item.icon || !item.cls)
      .map((item) => item.view || "(missing-view)");
    assert(expectedViews.length >= 17, "app route DOM coverage unexpectedly small: " + expectedViews.join(", "));
    assert(missing.length === 0, "command palette nav commands missing routes: " + missing.join(", "));
    assert(unexpected.length === 0, "command palette nav commands include unexpected routes: " + unexpected.join(", "));
    assert(duplicateNavViews.length === 0, "command palette nav commands duplicate routes: " + duplicateNavViews.join(", "));
    assert(incompleteNavCommands.length === 0, "command palette nav commands missing label/icon metadata: " + incompleteNavCommands.join(", "));
    commandPaletteRouteCoverageOk = true;
  });

  await runStep("command palette personal nav aliases open routes", async () => {
    const cases = [
      { query: "캘린더", label: "이동: 일정", view: "cal" },
      { query: "할일", label: "이동: 할 일", view: "todo" },
      { query: "노트", label: "이동: 메모", view: "notes" },
      { query: "루틴", label: "이동: 습관", view: "habits" },
      { query: "stats", label: "이동: 통계", view: "stats" },
    ];

    for (const item of cases) {
      await nav("home");
      click('[data-action="open-palette"]');
      await waitFor(() => document.querySelector("#palette.open"), "command palette did not open for " + item.query + " personal nav alias");
      const paletteInput = fill("#paletteInput", item.query);
      await waitFor(() => qsa("#paletteResults .pal-item").some((result) => result.textContent.includes(item.label)), item.query + " personal nav alias did not render " + item.label);
      const firstResult = qs("#paletteResults .pal-item");
      assert(firstResult.textContent.includes(item.label) && firstResult.getAttribute("aria-selected") === "true" && paletteInput.getAttribute("aria-activedescendant") === firstResult.id, item.query + " personal nav alias was not the active first result");
      paletteInput.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true }));
      await waitFor(() => document.body.dataset.view === item.view && location.hash === "#" + item.view && !document.getElementById("view-" + item.view).hidden && !document.querySelector("#palette.open"), item.query + " personal nav alias did not navigate to " + item.view + " route from Enter");
    }

    commandPalettePersonalNavAliasesOk = true;
  });

  await runStep("command palette operational nav aliases open routes", async () => {
    const cases = [
      { query: "위키", label: "이동: LLM 위키", view: "llm-wiki" },
      { query: "시스템", label: "이동: 시스템 상태", view: "system" },
    ];

    for (const item of cases) {
      await nav("home");
      click('[data-action="open-palette"]');
      await waitFor(() => document.querySelector("#palette.open"), "command palette did not open for " + item.query + " operational nav alias");
      const paletteInput = fill("#paletteInput", item.query);
      await waitFor(() => qsa("#paletteResults .pal-item").some((result) => result.textContent.includes(item.label)), item.query + " operational nav alias did not render " + item.label);
      const firstResult = qs("#paletteResults .pal-item");
      assert(firstResult.textContent.includes(item.label) && firstResult.getAttribute("aria-selected") === "true" && paletteInput.getAttribute("aria-activedescendant") === firstResult.id, item.query + " operational nav alias was not the active first result");
      paletteInput.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true }));
      await waitFor(() => document.body.dataset.view === item.view && location.hash === "#" + item.view && !document.getElementById("view-" + item.view).hidden && !document.querySelector("#palette.open"), item.query + " operational nav alias did not navigate to " + item.view + " route from Enter");
    }

    commandPaletteOperationalNavAliasesOk = true;
  });

  await runStep("command palette Korean nav alias opens Kanban", async () => {
    await nav("home");
    click('[data-action="open-palette"]');
    await waitFor(() => document.querySelector("#palette.open"), "command palette did not open for Korean nav alias");
    const paletteInput = fill("#paletteInput", "칸반");
    await waitFor(() => qsa("#paletteResults .pal-item").some((item) => item.textContent.includes("이동: Kanban 보드")), "Korean Kanban nav alias did not render navigation command");
    const firstResult = qs("#paletteResults .pal-item");
    assert(firstResult.textContent.includes("이동: Kanban 보드") && firstResult.getAttribute("aria-selected") === "true" && paletteInput.getAttribute("aria-activedescendant") === firstResult.id, "Korean Kanban nav alias was not the active first result");
    paletteInput.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true }));
    await waitFor(() => document.body.dataset.view === "pm-kanban" && location.hash === "#pm-kanban" && !document.getElementById("view-pm-kanban").hidden && !document.querySelector("#palette.open"), "Korean Kanban nav alias did not navigate to Kanban route from Enter");
    commandPaletteKoreanNavAliasOk = true;
  });

  await runStep("command palette Korean project nav alias opens portfolio", async () => {
    await nav("home");
    click('[data-action="open-palette"]');
    await waitFor(() => document.querySelector("#palette.open"), "command palette did not open for Korean project nav alias");
    const paletteInput = fill("#paletteInput", "프로젝트");
    await waitFor(() => qsa("#paletteResults .pal-item").some((item) => item.textContent.includes("이동: 포트폴리오")), "Korean project nav alias did not render portfolio navigation command");
    const firstResult = qs("#paletteResults .pal-item");
    assert(firstResult.textContent.includes("이동: 포트폴리오") && firstResult.getAttribute("aria-selected") === "true" && paletteInput.getAttribute("aria-activedescendant") === firstResult.id, "Korean project nav alias was not the active first result");
    paletteInput.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true }));
    await waitFor(() => document.body.dataset.view === "pm-portfolio" && location.hash === "#pm-portfolio" && !document.getElementById("view-pm-portfolio").hidden && !document.querySelector("#palette.open"), "Korean project nav alias did not navigate to portfolio route from Enter");
    commandPalettePmPortfolioNavAliasOk = true;
  });

  await runStep("command palette Korean Gantt nav alias opens Gantt", async () => {
    await nav("home");
    click('[data-action="open-palette"]');
    await waitFor(() => document.querySelector("#palette.open"), "command palette did not open for Korean Gantt nav alias");
    const paletteInput = fill("#paletteInput", "간트");
    await waitFor(() => qsa("#paletteResults .pal-item").some((item) => item.textContent.includes("이동: 간트 차트")), "Korean Gantt nav alias did not render Gantt navigation command");
    const firstResult = qs("#paletteResults .pal-item");
    assert(firstResult.textContent.includes("이동: 간트 차트") && firstResult.getAttribute("aria-selected") === "true" && paletteInput.getAttribute("aria-activedescendant") === firstResult.id, "Korean Gantt nav alias was not the active first result");
    paletteInput.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true }));
    await waitFor(() => document.body.dataset.view === "pm-gantt" && location.hash === "#pm-gantt" && !document.getElementById("view-pm-gantt").hidden && !document.querySelector("#palette.open"), "Korean Gantt nav alias did not navigate to Gantt route from Enter");
    commandPalettePmGanttNavAliasOk = true;
  });

  await runStep("command palette Korean team nav alias opens team", async () => {
    await nav("home");
    click('[data-action="open-palette"]');
    await waitFor(() => document.querySelector("#palette.open"), "command palette did not open for Korean team nav alias");
    const paletteInput = fill("#paletteInput", "팀");
    await waitFor(() => qsa("#paletteResults .pal-item").some((item) => item.textContent.includes("이동: 팀 · 리소스")), "Korean team nav alias did not render team navigation command");
    const firstResult = qs("#paletteResults .pal-item");
    assert(firstResult.textContent.includes("이동: 팀 · 리소스") && firstResult.getAttribute("aria-selected") === "true" && paletteInput.getAttribute("aria-activedescendant") === firstResult.id, "Korean team nav alias was not the active first result");
    paletteInput.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true }));
    await waitFor(() => document.body.dataset.view === "pm-team" && location.hash === "#pm-team" && !document.getElementById("view-pm-team").hidden && !document.querySelector("#palette.open"), "Korean team nav alias did not navigate to team route from Enter");
    commandPalettePmTeamNavAliasOk = true;
  });

  await runStep("command palette Korean DB nav alias opens schema", async () => {
    await nav("home");
    click('[data-action="open-palette"]');
    await waitFor(() => document.querySelector("#palette.open"), "command palette did not open for Korean DB nav alias");
    const paletteInput = fill("#paletteInput", "데이터 카탈로그 스키마");
    await waitFor(() => qsa("#paletteResults .pal-item").some((item) => item.textContent.includes("이동: 스키마 탐색")), "Korean DB schema nav alias did not render navigation command");
    const firstResult = qs("#paletteResults .pal-item");
    assert(firstResult.textContent.includes("이동: 스키마 탐색") && firstResult.getAttribute("aria-selected") === "true" && paletteInput.getAttribute("aria-activedescendant") === firstResult.id, "Korean DB schema nav alias was not the active first result");
    paletteInput.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true }));
    await waitFor(() => document.body.dataset.view === "dbm-schema" && location.hash === "#dbm-schema" && !document.getElementById("view-dbm-schema").hidden && !document.querySelector("#palette.open"), "Korean DB schema nav alias did not navigate to DB schema route from Enter");
    commandPaletteDbKoreanNavAliasOk = true;
  });

  await runStep("command palette Korean DB instance nav alias opens instances", async () => {
    await nav("home");
    click('[data-action="open-palette"]');
    await waitFor(() => document.querySelector("#palette.open"), "command palette did not open for Korean DB instance nav alias");
    const paletteInput = fill("#paletteInput", "데이터베이스 인스턴스");
    await waitFor(() => qsa("#paletteResults .pal-item").some((item) => item.textContent.includes("이동: 인스턴스 상태")), "Korean DB instance nav alias did not render navigation command");
    const firstResult = qs("#paletteResults .pal-item");
    assert(firstResult.textContent.includes("이동: 인스턴스 상태") && firstResult.getAttribute("aria-selected") === "true" && paletteInput.getAttribute("aria-activedescendant") === firstResult.id, "Korean DB instance nav alias was not the active first result");
    paletteInput.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true }));
    await waitFor(() => document.body.dataset.view === "dbm-instances" && location.hash === "#dbm-instances" && !document.getElementById("view-dbm-instances").hidden && !document.querySelector("#palette.open"), "Korean DB instance nav alias did not navigate to DB instances route from Enter");
    commandPaletteDbInstanceNavAliasOk = true;
  });

  await runStep("command palette Korean DB query nav alias opens queries", async () => {
    await nav("home");
    click('[data-action="open-palette"]');
    await waitFor(() => document.querySelector("#palette.open"), "command palette did not open for Korean DB query nav alias");
    const paletteInput = fill("#paletteInput", "데이터베이스 쿼리");
    await waitFor(() => qsa("#paletteResults .pal-item").some((item) => item.textContent.includes("이동: 질의 성능")), "Korean DB query nav alias did not render navigation command");
    const firstResult = qs("#paletteResults .pal-item");
    assert(firstResult.textContent.includes("이동: 질의 성능") && firstResult.getAttribute("aria-selected") === "true" && paletteInput.getAttribute("aria-activedescendant") === firstResult.id, "Korean DB query nav alias was not the active first result");
    paletteInput.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true }));
    await waitFor(() => document.body.dataset.view === "dbm-queries" && location.hash === "#dbm-queries" && !document.getElementById("view-dbm-queries").hidden && !document.querySelector("#palette.open"), "Korean DB query nav alias did not navigate to DB queries route from Enter");
    commandPaletteDbQueryNavAliasOk = true;
  });

  await runStep("command palette Korean DB backup nav alias opens backups", async () => {
    await nav("home");
    click('[data-action="open-palette"]');
    await waitFor(() => document.querySelector("#palette.open"), "command palette did not open for Korean DB backup nav alias");
    const paletteInput = fill("#paletteInput", "데이터베이스 백업");
    await waitFor(() => qsa("#paletteResults .pal-item").some((item) => item.textContent.includes("이동: 백업 · 마이그")), "Korean DB backup nav alias did not render navigation command");
    const firstResult = qs("#paletteResults .pal-item");
    assert(firstResult.textContent.includes("이동: 백업 · 마이그") && firstResult.getAttribute("aria-selected") === "true" && paletteInput.getAttribute("aria-activedescendant") === firstResult.id, "Korean DB backup nav alias was not the active first result");
    paletteInput.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true }));
    await waitFor(() => document.body.dataset.view === "dbm-backups" && location.hash === "#dbm-backups" && !document.getElementById("view-dbm-backups").hidden && !document.querySelector("#palette.open"), "Korean DB backup nav alias did not navigate to DB backups route from Enter");
    commandPaletteDbBackupNavAliasOk = true;
  });

  await runStep("command palette exact nav label opens Notes by keyboard", async () => {
    await nav("home");
    click('[data-action="open-palette"]');
    await waitFor(() => document.querySelector("#palette.open"), "command palette did not open for exact nav label");
    const paletteInput = fill("#paletteInput", "메모");
    await waitFor(() => qsa("#paletteResults .pal-item").some((item) => item.textContent.includes("이동: 메모")), "exact Notes nav label did not render navigation command");
    const firstResult = qs("#paletteResults .pal-item");
    assert(firstResult.textContent.includes("이동: 메모") && firstResult.getAttribute("aria-selected") === "true" && paletteInput.getAttribute("aria-activedescendant") === firstResult.id, "exact Notes nav label was not the active first result");
    paletteInput.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true }));
    await waitFor(() => document.body.dataset.view === "notes" && location.hash === "#notes" && !document.getElementById("view-notes").hidden && !document.querySelector("#palette.open"), "exact Notes nav label did not navigate to Notes route from Enter");
    commandPaletteExactNavLabelOk = true;
  });

	  await runStep("home launch action surfaces current guard", async () => {
	    await nav("home");
	    await waitFor(() => {
	      const card = document.querySelector("#view-home [data-home-launch-next-action]");
	      const text = card ? card.textContent || "" : "";
	      const code = card ? card.querySelector("code")?.textContent || "" : "";
	      const label = card ? (card.dataset.homeLaunchActionLabel || "").trim() : "";
	      const installAction = card &&
	        card.dataset.homeLaunchActionKey === "install_workflows" &&
	        label === "Install workflows on the default branch" &&
	        text.includes("remoteWorkflowFilesReady=true") &&
	        (code === "gh auth refresh -h github.com -s workflow" || code.includes("pbcopy < 'docs/github-pages-workflow.yml'") || code.includes("check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write"));
	      const proofCaptureAction = card &&
	        card.dataset.homeLaunchActionKey === "capture_launch_proof" &&
	        label === "Capture launch proof" &&
	        text.includes("postPublishEvidenceReady=true") &&
	        code.includes("capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --markdown");
      const homeLaunchActionKey = card ? (card.dataset.homeLaunchActionKey || "") : "";
      const normalizedHomeLaunchActionKey = homeLaunchActionKey.replaceAll("_", "-");
      const shareProofAction = card &&
        normalizedHomeLaunchActionKey === "share-launch-proof" &&
        label === "Share launch proof" &&
        text.includes("Pages and workflow run evidence are fresh") &&
        code.includes("capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --markdown");
      return card &&
        (installAction || proofCaptureAction || shareProofAction) &&
        (shareProofAction || Number(card.dataset.homeLaunchCommandCount || "0") >= 1) &&
        Number(card.dataset.homeLaunchWithheldCount || "0") >= 0;
	    }, "home launch action card did not load current launch evidence with label", 30000);
	    const card = qs("#view-home [data-home-launch-next-action]");
	    const releaseGateCard = qs('#view-home [data-home-readiness-card="release-gate"]');
	    const text = card.textContent || "";
	    const releaseGateCardText = releaseGateCard.textContent || "";
	    const normalizedText = text.toLowerCase();
	    const label = (card.dataset.homeLaunchActionLabel || "").trim();
	    const renderedLabel = qs("strong", card).textContent.trim();
	    const renderedLaunchCommand = qs("code", card).textContent;
	    const isInstallAction = card.dataset.homeLaunchActionKey === "install_workflows";
	    const isProofCaptureAction = card.dataset.homeLaunchActionKey === "capture_launch_proof";
	    const isShareProofAction = card.dataset.homeLaunchActionKey.replaceAll("_", "-") === "share-launch-proof";
	    const expectedLaunchCommandNeedle = (isProofCaptureAction || isShareProofAction)
	      ? "capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --markdown"
	      : (renderedLaunchCommand.includes("pbcopy < 'docs/github-pages-workflow.yml'") ? "pbcopy < 'docs/github-pages-workflow.yml'" : (renderedLaunchCommand.includes("check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write") ? "check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write" : "gh auth refresh -h github.com -s workflow"));
	    const homeLaunchTransitionCurrentStages = ["install_workflows", "capture_launch_proof", "share_launch_proof"];
	    const homeLaunchTransitionNextStages = ["verify_visibility", "capture_launch_proof", "share_launch_proof"];
	    const homeLaunchProofLedgerGates = ["capture_launch_proof", "share_launch_proof"];
	    assert(releaseGateCard.dataset.homeReadinessCardEvidenceCount === "6" && releaseGateCardText.includes("릴리스 게이트") && releaseGateCardText.includes("6 proofs") && releaseGateCardText.includes("route 17/17") && releaseGateCardText.includes("mobile search/UI") && releaseGateCardText.includes("delete undo") && releaseGateCardText.includes("a11y"), "home release gate evidence summary did not render");
	    homeReleaseGateEvidenceOk = true;
	    assert(["action_required", "action_required_after_dispatch", "pass", "ready"].includes(card.dataset.homeLaunchActionStatus), "home launch action did not expose an actionable status");
	    assert(["Install workflows on the default branch", "Capture launch proof", "Share launch proof"].includes(label), "home launch action label dataset did not render: " + label);
	    assert(card.dataset.homeLaunchSafeToDispatch === (isInstallAction ? "false" : "true"), "home launch action safeToDispatch state was stale");
	    assert(card.dataset.homeLaunchReadyForExternalClaim === (isShareProofAction ? "true" : "false"), "home launch action external launch claim state was stale");
	    assert(card.dataset.homeLaunchTransitionSource === "generated_from_launch_execution_packet" && homeLaunchTransitionCurrentStages.includes(card.dataset.homeLaunchTransitionCurrentStage) && homeLaunchTransitionNextStages.includes(card.dataset.homeLaunchTransitionNextStage) && card.dataset.homeLaunchTransitionGateCommand.includes("verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown"), "home launch transition preview dataset was incomplete");
	    assert(card.getAttribute("data-home-launch-install-matrix-source") === "generated_from_launch_execution_packet" && Number(card.dataset.homeLaunchInstallMatrixSignalCount || "0") >= 6 && card.dataset.homeLaunchInstallMatrixNextStage === "verify_visibility", "home launch install verification matrix dataset was incomplete");
	    const homeRemoteWorkflowFileLedgerFileCount = Number(card.dataset.homeRemoteWorkflowFileLedgerFileCount || "0");
	    const homeRemoteWorkflowFileLedgerReadyCount = Number(card.dataset.homeRemoteWorkflowFileLedgerReadyCount || "0");
	    const homeRemoteWorkflowFileLedgerMissingCount = Number(card.dataset.homeRemoteWorkflowFileLedgerMissingCount || "0");
	    const homeRemoteWorkflowFileLedgerMismatchCount = Number(card.dataset.homeRemoteWorkflowFileLedgerMismatchCount || "0");
	    const homeRemoteWorkflowFileLedgerNotCheckedCount = Number(card.dataset.homeRemoteWorkflowFileLedgerNotCheckedCount || "0");
	    const homeRemoteWorkflowFileLedgerAccountedCount = homeRemoteWorkflowFileLedgerReadyCount + homeRemoteWorkflowFileLedgerMissingCount + homeRemoteWorkflowFileLedgerMismatchCount + homeRemoteWorkflowFileLedgerNotCheckedCount;
	    assert(card.getAttribute("data-home-remote-workflow-file-ledger-source") === "generated_from_remote_workflow_file_check" && ["remote_file_install_required", "remote_files_ready"].includes(card.dataset.homeRemoteWorkflowFileLedgerStatus) && homeRemoteWorkflowFileLedgerFileCount === 2 && homeRemoteWorkflowFileLedgerAccountedCount === 2, "home remote workflow file acceptance ledger dataset was incomplete");
	    const homeLaunchProofReadyCount = Number(card.dataset.homeLaunchProofLedgerReadyCount || "0");
	    const homeLaunchProofPendingCount = Number(card.dataset.homeLaunchProofLedgerPendingCount || "0");
	    assert(card.getAttribute("data-home-launch-proof-ledger-source") === "generated_from_launch_execution_packet" && ["proof_blocked_until_dispatch", "proof_capture_required", "proof_ready"].includes(card.dataset.homeLaunchProofLedgerStatus) && card.dataset.homeLaunchProofLedgerRequiredCount === "6" && homeLaunchProofReadyCount + homeLaunchProofPendingCount === 6 && homeLaunchProofLedgerGates.includes(card.dataset.homeLaunchProofLedgerCurrentGate), "home launch proof acceptance ledger dataset was incomplete");
	    assert(text.includes("현재") && normalizedText.includes(label.toLowerCase()) && renderedLabel === label, "home launch action label did not render: " + text.slice(0, 240));
	    assert(text.includes(expectedLaunchCommandNeedle) && (text.includes("remoteWorkflowFilesReady=true") || text.includes("postPublishEvidenceReady=true") || (isShareProofAction && text.includes("Pages and workflow run evidence are fresh"))), "home launch action command and success condition did not render");
	    assert(text.includes("next transition") && text.includes(card.dataset.homeLaunchTransitionCurrentStage + " -> " + card.dataset.homeLaunchTransitionNextStage) && text.includes("pending " + card.dataset.homeLaunchTransitionPendingCount) && text.includes(isInstallAction ? "dispatch withheld" : "safeToDispatch=true"), "home launch transition preview did not render");
	    assert(text.includes("install verification matrix") && text.includes("signals") && text.includes("remoteWorkflowVisibilityReady=true") && text.includes("dispatchReady=true") && text.includes("driftDispatchReady=true") && text.includes("allDispatchReady=true") && text.includes("verify-launch-handoff reports safeToDispatch=true"), "home launch install verification matrix did not render");
	    assert(text.includes("remote workflow file acceptance ledger") && text.includes(card.dataset.homeRemoteWorkflowFileLedgerReadyCount + "/2 files ready") && text.includes(card.dataset.homeRemoteWorkflowFileLedgerStatus) && text.includes("missing " + card.dataset.homeRemoteWorkflowFileLedgerMissingCount) && text.includes("mismatch " + card.dataset.homeRemoteWorkflowFileLedgerMismatchCount) && text.includes("remoteMatchesTemplate required"), "home remote workflow file acceptance ledger did not render");
	    assert(text.includes("launch proof acceptance ledger") && text.includes(homeLaunchProofReadyCount + "/6 proofs ready") && text.includes(card.dataset.homeLaunchProofLedgerStatus) && text.includes("pending " + homeLaunchProofPendingCount) && text.includes("capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --write"), "home launch proof acceptance ledger did not render");
	    assert(text.includes("safeToDispatch") && text.includes("externalClaim") && text.includes("withheld"), "home launch action guard counters did not render");
	    assert(renderedLaunchCommand.includes(expectedLaunchCommandNeedle), "home launch action code did not expose first safe command");
	    const homeLaunchActionChecklist = qs("#view-home [data-home-launch-action-checklist]");
	    const homeLaunchActionChecklistText = homeLaunchActionChecklist.textContent || "";
	    const homeLaunchActionChecklistCopyText = qs("[data-home-launch-action-checklist-text]", homeLaunchActionChecklist).textContent;
	    const homeLaunchActionChecklistSteps = Array.from(homeLaunchActionChecklist.querySelectorAll("[data-home-launch-action-checklist-step]"));
	    const homeLaunchActionChecklistSources = Array.from(homeLaunchActionChecklist.querySelectorAll("[data-home-launch-action-checklist-source-artifact]"));
	    const checklistActive = homeLaunchActionChecklist.dataset.homeLaunchActionChecklistActive;
	    assert(homeLaunchActionChecklist.dataset.homeLaunchActionChecklistReady === "true" && ["operator_auth_path", "remote_workflow_file_parity", "launch_proof_capture"].includes(checklistActive) && ["action_required", "pass"].includes(homeLaunchActionChecklist.dataset.homeLaunchActionChecklistStatus) && homeLaunchActionChecklist.dataset.homeLaunchActionChecklistRecheckCount === "5" && homeLaunchActionChecklist.dataset.homeLaunchActionChecklistSourceArtifactCount === "4" && homeLaunchActionChecklist.dataset.homeLaunchActionChecklistDispatchApproval === "false" && homeLaunchActionChecklist.dataset.homeLaunchActionChecklistVerificationOnly === "true" && Number(homeLaunchActionChecklist.dataset.homeLaunchActionChecklistWithheldCount || "0") >= 0, "home launch action checklist dataset was incomplete");
	    assert(homeLaunchActionChecklist.dataset.homeLaunchActionChecklistImmediateCommand.includes(expectedLaunchCommandNeedle) && (homeLaunchActionChecklist.dataset.homeLaunchActionChecklistDeferredCommand.includes("capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --markdown") || homeLaunchActionChecklist.dataset.homeLaunchActionChecklistDeferredCommand.includes("gh api repos/biojuho/BIOJUHO-Projects/pages")) && (homeLaunchActionChecklist.dataset.homeLaunchActionChecklistGuard.includes("Do not run gh workflow run until every action_required post-auth checkpoint item") || homeLaunchActionChecklist.dataset.homeLaunchActionChecklistGuard.includes("Do not run install-remote-workflow-files.mjs")), "home launch action checklist command or guard dataset was incomplete");
	    assert(homeLaunchActionChecklistSteps.length === 5 && homeLaunchActionChecklistSteps[0].dataset.homeLaunchActionChecklistStepKey === "confirm_scope" && homeLaunchActionChecklistSteps[1].dataset.homeLaunchActionChecklistStepKey === "install_workflows" && homeLaunchActionChecklistSteps[2].dataset.homeLaunchActionChecklistStepKey === "verify_remote_parity" && homeLaunchActionChecklistSteps[3].dataset.homeLaunchActionChecklistStepKey === "verify_actions_visibility" && homeLaunchActionChecklistSteps[4].dataset.homeLaunchActionChecklistStepKey === "verify_handoff_guard" && homeLaunchActionChecklistSteps[4].dataset.homeLaunchActionChecklistStepCommand.includes("verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown"), "home launch action checklist recheck sequence did not render");
	    assert(homeLaunchActionChecklistSources.length === 4 && homeLaunchActionChecklistSources.some((item) => item.textContent.includes("gh auth status -h github.com")) && homeLaunchActionChecklistSources.some((item) => item.textContent.includes("data/remote-workflow-file-check.json")) && homeLaunchActionChecklistSources.some((item) => item.textContent.includes("data/publish-dispatch-plan.json")) && homeLaunchActionChecklistSources.some((item) => item.textContent.includes("data/launch-handoff-verification.json")), "home launch action checklist source artifacts did not render");
	    assert(homeLaunchActionChecklistText.includes("launch action checklist") && homeLaunchActionChecklistText.includes(checklistActive) && homeLaunchActionChecklistText.includes("immediate command") && homeLaunchActionChecklistText.includes("gh auth status -h github.com") && homeLaunchActionChecklistText.includes("verify_handoff_guard") && homeLaunchActionChecklistText.includes("dispatchApproval=false") && homeLaunchActionChecklistText.includes("verificationOnly=true") && homeLaunchActionChecklistText.includes("Do not run gh workflow run"), "home launch action checklist visible text did not render");
	    assert(homeLaunchActionChecklistCopyText.includes("JooPark Launch Action Checklist") && homeLaunchActionChecklistCopyText.includes("Active blocker: " + checklistActive) && homeLaunchActionChecklistCopyText.includes("Immediate command: " + homeLaunchActionChecklist.dataset.homeLaunchActionChecklistImmediateCommand) && homeLaunchActionChecklistCopyText.includes("Recheck sequence: 5") && homeLaunchActionChecklistCopyText.includes("Source artifacts: 4") && homeLaunchActionChecklistCopyText.includes("dispatchApproval=false") && homeLaunchActionChecklistCopyText.includes("verificationOnly=true") && homeLaunchActionChecklistCopyText.includes("5. verify_handoff_guard") && homeLaunchActionChecklistCopyText.includes("data/launch-handoff-verification.json") && homeLaunchActionChecklistCopyText.includes("Deferred proof command:") && homeLaunchActionChecklistCopyText.includes("Guard: Do not run gh workflow run"), "home launch action checklist copy text was not ready");
	    const homeLaunchActionChecklistButton = qs('[data-action="copy-home-launch-action-checklist"]', homeLaunchActionChecklist);
	    click('[data-action="copy-home-launch-action-checklist"]', homeLaunchActionChecklist);
	    await waitFor(() => {
	      const copied = homeLaunchActionChecklist.dataset.homeLaunchActionChecklistCopied === "true" || homeLaunchActionChecklistButton.dataset.homeLaunchActionChecklistCopied === "true";
	      const statusText = qs("[data-home-launch-action-checklist-copy-status]", homeLaunchActionChecklist).textContent || "";
	      return copied && statusText.includes("복사") &&
	        window.__smokeClipboardText.includes("JooPark Launch Action Checklist") &&
	        window.__smokeClipboardText.includes("Active blocker: " + checklistActive) &&
	        window.__smokeClipboardText.includes("confirm_scope") &&
	        window.__smokeClipboardText.includes("verify_handoff_guard") &&
	        window.__smokeClipboardText.includes("Source artifacts:") &&
        window.__smokeClipboardText.includes("data/launch-handoff-verification.json") &&
        window.__smokeClipboardText.includes("dispatchApproval=false") &&
        window.__smokeClipboardText.includes("verificationOnly=true") &&
        window.__smokeClipboardText.includes("Do not run gh workflow run");
    }, "home launch action checklist copy did not report success");
    homeLaunchActionChecklistOk = true;
    const homePostInstallIntake = qs("#view-home [data-home-post-install-evidence-intake]");
    const homePostInstallIntakeText = homePostInstallIntake.textContent || "";
    const homePostInstallIntakeCopyText = qs("[data-post-install-evidence-intake-text]", homePostInstallIntake).textContent;
	    const homePostInstallFields = Array.from(homePostInstallIntake.querySelectorAll("[data-home-post-install-evidence-intake-field]"));
	    const homePostInstallCommands = Array.from(homePostInstallIntake.querySelectorAll("[data-home-post-install-evidence-intake-command]"));
	    const homePostInstallSignals = Array.from(homePostInstallIntake.querySelectorAll("[data-home-post-install-evidence-intake-signal]"));
	    const homePostInstallVerificationSequence = qs("[data-home-post-install-evidence-sequence]", homePostInstallIntake);
	    const homePostInstallVerificationSteps = Array.from(homePostInstallVerificationSequence.querySelectorAll("[data-home-post-install-evidence-sequence-step]"));
		    const homePostInstallQuickProof = qs("[data-post-install-quick-proof]", homePostInstallIntake);
		    const homePostInstallQuickProofSteps = Array.from(homePostInstallQuickProof.querySelectorAll("[data-post-install-quick-proof-step]"));
		    const homePostInstallQuickProofMap = qs("[data-post-install-quick-proof-field-map]", homePostInstallIntake);
		    const homePostInstallQuickProofMapItems = Array.from(homePostInstallQuickProofMap.querySelectorAll("[data-post-install-quick-proof-field-map-item]"));
		    const homePostInstallProofComplete = homePostInstallIntake.dataset.homePostInstallEvidenceIntakeProofComplete === "true";
		    const homePostInstallCompleted = Number(homePostInstallIntake.dataset.homePostInstallEvidenceIntakeCompletedCount || "0");
		    const homePostInstallPending = Number(homePostInstallIntake.dataset.homePostInstallEvidenceIntakePendingCount || "0");
		    const homePostInstallMappedCompleted = Number(homePostInstallIntake.dataset.postInstallQuickProofCompletedMappedFieldCount || "0");
		    assert(homePostInstallIntake.dataset.homePostInstallEvidenceIntakeReady === "true" && ["collect_post_install_proof", "proof_complete"].includes(homePostInstallIntake.dataset.homePostInstallEvidenceIntakeStatus) && homePostInstallIntake.dataset.homePostInstallEvidenceIntakeProofComplete === (homePostInstallProofComplete ? "true" : "false") && homePostInstallCompleted + homePostInstallPending === 6 && homePostInstallIntake.dataset.homePostInstallEvidenceIntakeFieldCount === "6" && homePostInstallIntake.dataset.homePostInstallEvidenceIntakeCommandCount === "4" && homePostInstallIntake.dataset.homePostInstallEvidenceIntakeSignalCount === "8", "home post-install evidence intake dataset was incomplete");
		    assert(homePostInstallIntake.dataset.homePostInstallEvidenceIntakeSequenceCount === "4" && homePostInstallIntake.dataset.homePostInstallEvidenceIntakeSequenceReady === "true" && homePostInstallIntake.dataset.homePostInstallEvidenceIntakeFinalCommand.includes("verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown"), "home post-install evidence intake sequence dataset was incomplete");
		    assert(homePostInstallIntake.dataset.postInstallEvidenceIntakeReady === "true" && homePostInstallIntake.dataset.postInstallEvidenceIntakeProofComplete === (homePostInstallProofComplete ? "true" : "false") && homePostInstallIntake.dataset.postInstallEvidenceIntakeFieldCount === "6" && homePostInstallIntake.dataset.postInstallQuickProofReady === "true" && homePostInstallIntake.dataset.postInstallQuickProofStepCount === "4" && homePostInstallIntake.dataset.postInstallQuickProofCoverage === "1" && homePostInstallIntake.dataset.postInstallQuickProofFieldMappingReady === "true" && homePostInstallIntake.dataset.postInstallQuickProofFieldMappingCoverage === "1" && homePostInstallIntake.dataset.postInstallQuickProofMappedFieldCount === "4" && homePostInstallMappedCompleted >= 0 && homePostInstallMappedCompleted <= 4, "home post-install evidence intake did not reuse copy selectors");
		    assert(homePostInstallQuickProof.dataset.postInstallQuickProofReady === "true" && homePostInstallQuickProof.dataset.postInstallQuickProofStepCount === "4" && homePostInstallQuickProof.dataset.postInstallQuickProofCoverage === "1" && homePostInstallQuickProof.dataset.postInstallQuickProofFieldMappingReady === "true" && homePostInstallQuickProof.dataset.postInstallQuickProofFieldMappingCoverage === "1" && homePostInstallQuickProofSteps.length === 4 && homePostInstallQuickProofSteps[0].dataset.postInstallQuickProofStepKey === "remote_file_parity" && homePostInstallQuickProofSteps[3].dataset.postInstallQuickProofStepKey === "handoff_verifier" && homePostInstallQuickProofSteps[3].dataset.postInstallQuickProofStepCommand.includes("verify-launch-handoff.mjs"), "home post-install quick proof did not render");
		    assert(homePostInstallQuickProofMap.dataset.postInstallQuickProofFieldMappingReady === "true" && homePostInstallQuickProofMap.dataset.postInstallQuickProofFieldMappingCoverage === "1" && homePostInstallQuickProofMap.dataset.postInstallQuickProofMappedFieldCount === "4" && Number(homePostInstallQuickProofMap.dataset.postInstallQuickProofCompletedMappedFieldCount || "0") === homePostInstallMappedCompleted && homePostInstallQuickProofMapItems.length === 4 && homePostInstallQuickProofMapItems[0].dataset.postInstallQuickProofFieldMapStep === "remote_file_parity" && homePostInstallQuickProofMapItems[0].dataset.postInstallQuickProofFieldMapField === "remote_parity_proof" && homePostInstallQuickProofMapItems[3].dataset.postInstallQuickProofFieldMapStep === "handoff_verifier" && homePostInstallQuickProofMapItems[3].dataset.postInstallQuickProofFieldMapField === "handoff_verifier_proof", "home post-install quick proof field map did not render");
		    assert(homePostInstallFields.length === 6 && homePostInstallFields.some((item) => item.dataset.homePostInstallEvidenceIntakeFieldKey === "remote_parity_proof" && item.textContent.includes("remoteWorkflowFilesReady=")) && homePostInstallFields.some((item) => item.dataset.homePostInstallEvidenceIntakeFieldKey === "handoff_verifier_proof" && item.textContent.includes("safeToDispatch=")), "home post-install evidence fields did not render");
		    assert(homePostInstallVerificationSequence.dataset.homePostInstallEvidenceSequenceCount === "4" && homePostInstallVerificationSequence.dataset.homePostInstallEvidenceSequenceReady === "true" && homePostInstallVerificationSteps.length === 4 && homePostInstallVerificationSteps[0].dataset.homePostInstallEvidenceSequenceKey === "remote_file_parity" && homePostInstallVerificationSteps[1].dataset.homePostInstallEvidenceSequenceKey === "actions_visibility" && homePostInstallVerificationSteps[2].dataset.homePostInstallEvidenceSequenceKey === "dispatch_readiness" && homePostInstallVerificationSteps[3].dataset.homePostInstallEvidenceSequenceKey === "handoff_verifier" && homePostInstallVerificationSteps[3].dataset.homePostInstallEvidenceSequenceCommand.includes("verify-launch-handoff.mjs"), "home post-install verification sequence did not render");
		    assert(homePostInstallCommands.length === 4 && homePostInstallCommands.some((item) => item.textContent.includes("check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write")) && homePostInstallCommands.some((item) => item.textContent.includes("verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown")), "home post-install evidence commands did not render");
		    assert(homePostInstallSignals.length === 8 && homePostInstallSignals.some((item) => item.textContent.includes("remoteWorkflowFilesReady=true")) && homePostInstallSignals.some((item) => item.textContent.includes("safeToDispatch=true before gh workflow run")), "home post-install evidence signals did not render");
		    assert(homePostInstallIntakeText.includes("post-install proof intake") && homePostInstallIntakeText.includes(homePostInstallCompleted + "/6 proof fields complete") && homePostInstallIntakeText.includes(homePostInstallIntake.dataset.homePostInstallEvidenceIntakeStatus) && homePostInstallIntakeText.includes("proofComplete=" + (homePostInstallProofComplete ? "true" : "false")) && homePostInstallIntakeText.includes("Quick proof") && homePostInstallIntakeText.includes("Mapped fields") && homePostInstallIntakeText.includes("remote_file_parity -> Remote parity proof") && homePostInstallIntakeText.includes("handoff_verifier -> Handoff verifier proof") && homePostInstallIntakeText.includes("Verification sequence") && homePostInstallIntakeText.includes("Remote workflow file check") && homePostInstallIntakeText.includes("Actions visibility check") && homePostInstallIntakeText.includes("Dispatch readiness plan") && homePostInstallIntakeText.includes("Launch handoff verifier") && homePostInstallIntakeText.includes("Stop condition: do not run gh workflow run"), "home post-install evidence intake text did not render");
		    assert(homePostInstallIntakeCopyText.includes("JooPark Workflow Post-Install Evidence Intake") && homePostInstallIntakeCopyText.includes("JooPark Post-Install Quick Proof Receipt") && homePostInstallIntakeCopyText.includes("Quick proof: ready=true; steps=4; coverage=1") && homePostInstallIntakeCopyText.includes("Quick proof field mapping: ready=true; mapped=4; completed=" + homePostInstallMappedCompleted + "/4; coverage=1") && homePostInstallIntakeCopyText.includes("Mapped proof fields:") && homePostInstallIntakeCopyText.includes("remote_file_parity -> remote_parity_proof") && homePostInstallIntakeCopyText.includes("handoff_verifier -> handoff_verifier_proof") && homePostInstallIntakeCopyText.includes("4-step proof checklist:") && homePostInstallIntakeCopyText.includes("Status: " + homePostInstallIntake.dataset.homePostInstallEvidenceIntakeStatus) && homePostInstallIntakeCopyText.includes("Evidence fields to fill:") && homePostInstallIntakeCopyText.includes("Handoff verifier proof") && homePostInstallIntakeCopyText.includes("Verification sequence:") && homePostInstallIntakeCopyText.includes("1. remote_file_parity") && homePostInstallIntakeCopyText.includes("4. handoff_verifier") && homePostInstallIntakeCopyText.includes("Expected signals:"), "home post-install evidence intake copy text was not ready");
    const homePostInstallButton = qs('[data-action="copy-post-install-evidence-intake"]', homePostInstallIntake);
    click('[data-action="copy-post-install-evidence-intake"]', homePostInstallIntake);
    await waitFor(() => {
      const copied = homePostInstallIntake.dataset.postInstallEvidenceIntakeCopied === "true" || homePostInstallButton.dataset.postInstallEvidenceIntakeCopied === "true";
      const statusText = qs("[data-post-install-evidence-intake-copy-status]", homePostInstallIntake).textContent || "";
      return copied && statusText.includes("복사") &&
		        window.__smokeClipboardText.includes("JooPark Workflow Post-Install Evidence Intake") &&
		        window.__smokeClipboardText.includes("JooPark Post-Install Quick Proof Receipt") &&
		        window.__smokeClipboardText.includes("4-step proof checklist:") &&
		        window.__smokeClipboardText.includes("Quick proof field mapping: ready=true; mapped=4; completed=" + homePostInstallMappedCompleted + "/4; coverage=1") &&
		        window.__smokeClipboardText.includes("remote_file_parity -> remote_parity_proof") &&
		        window.__smokeClipboardText.includes("handoff_verifier -> handoff_verifier_proof") &&
		        window.__smokeClipboardText.includes("Verification sequence:") &&
	        window.__smokeClipboardText.includes("remoteWorkflowFilesReady=true") &&
	        window.__smokeClipboardText.includes("safeToDispatch=true before gh workflow run") &&
	        window.__smokeClipboardText.includes("every post-install evidence field has been filled") &&
        window.__smokeClipboardText.includes("Stop condition: do not run gh workflow run");
    }, "home post-install evidence intake copy did not report success");
    homePostInstallEvidenceIntakeOk = true;
    const homeClaimGuard = qs("#view-home [data-home-external-claim-guard]");
    const homeClaimGuardText = homeClaimGuard.textContent || "";
    const homeClaimGuardCopyText = qs("[data-output-quality-audit-external-claim-guard-text]", homeClaimGuard).textContent;
    const homeClaimGuardItems = Array.from(homeClaimGuard.querySelectorAll("[data-home-external-claim-guard-item]"));
	    const homeClaimGuardSignals = Array.from(homeClaimGuard.querySelectorAll("[data-home-external-claim-guard-signal]"));
	    const homeClaimGuardCommands = Array.from(homeClaimGuard.querySelectorAll("[data-home-external-claim-guard-command]"));
	    const homeClaimGuardNextProof = qs("[data-home-external-claim-guard-next-proof]", homeClaimGuard);
	    const claimBlockedCount = Number(homeClaimGuard.dataset.homeExternalClaimGuardBlockedCount || "0");
	    const nextClaimProofKey = homeClaimGuard.dataset.homeExternalClaimGuardNextProofKey;
	    const homeClaimReady = homeClaimGuard.dataset.homeExternalClaimGuardReady === "true";
	    const homeClaimGuardItemByKey = (key) => homeClaimGuardItems.find((item) => item.dataset.homeExternalClaimGuardKey === key);
	    const homeWorkflowInstallationItem = homeClaimGuardItemByKey("workflow_installation");
	    const homePublicLaunchProofItem = homeClaimGuardItemByKey("public_launch_proof");
	    const homeExternalCompletionItem = homeClaimGuardItemByKey("external_completion_claim");
	    const homeClaimGuardBlockedItems = homeClaimGuardItems.filter((item) => item.dataset.homeExternalClaimGuardItemStatus === "blocked");
		    const homeClaimGuardSignalText = homeClaimGuardSignals.map((item) => item.textContent || "").join("\\n");
	    assert(["blocked_external_claim", "ready_for_external_claim"].includes(homeClaimGuard.dataset.homeExternalClaimGuardStatus) && claimBlockedCount === (homeClaimReady ? 0 : claimBlockedCount) && claimBlockedCount >= 0 && claimBlockedCount <= 3 && homeClaimGuard.dataset.homeExternalClaimGuardRequirementCount === "3" && Number(homeClaimGuard.dataset.homeExternalClaimGuardCommandCount || "0") >= 5 && ["workflow_installation", "public_launch_proof", "external_completion_claim"].includes(nextClaimProofKey) && homeClaimGuard.dataset.homeExternalClaimGuardNextProofCommand.length > 0, "home external claim guard dataset was incomplete");
	    assert(homeClaimGuard.dataset.outputQualityAuditExternalClaimGuardStatus === homeClaimGuard.dataset.homeExternalClaimGuardStatus && Number(homeClaimGuard.dataset.outputQualityAuditExternalClaimGuardBlockedCount || "0") === claimBlockedCount, "home external claim guard did not reuse output quality copy selectors");
		    assert(homeClaimGuardNextProof.dataset.homeExternalClaimGuardNextProofReady === (homeClaimReady ? "true" : "false") && homeClaimGuardNextProof.dataset.homeExternalClaimGuardNextProofKey === nextClaimProofKey && ["blocked", "pass"].includes(homeClaimGuardNextProof.dataset.homeExternalClaimGuardNextProofStatus) && homeClaimGuardNextProof.textContent.includes("next proof") && homeClaimGuardNextProof.textContent.includes(nextClaimProofKey === "workflow_installation" ? "Workflow installation" : (nextClaimProofKey === "public_launch_proof" ? "Public launch proof" : "External completion claim")) && homeClaimGuardNextProof.textContent.includes(homeClaimReady ? "=true" : "=false"), "home external claim guard next proof shortcut was incomplete");
	    assert(homeClaimGuardItems.length === 3 && homeWorkflowInstallationItem && homePublicLaunchProofItem && homeExternalCompletionItem && homeClaimGuardBlockedItems.length === claimBlockedCount && homeClaimGuardItems.every((item) => ["blocked", "pass"].includes(item.dataset.homeExternalClaimGuardItemStatus)) && (homeClaimReady ? homeClaimGuardBlockedItems.length === 0 : homeClaimGuardBlockedItems.length > 0), "home external claim guard requirements did not render");
	    assert(homeClaimGuardSignals.length === 6 && homeClaimGuardSignalText.includes("postPublishEvidenceReady=") && homeClaimGuardSignalText.includes("allDispatchReady=") && homeClaimGuardSignalText.includes("readyForExternalClaim=" + (homeClaimReady ? "true" : "false")), "home external claim guard signals did not render");
	    assert(homeClaimGuardCommands.length >= 5 && homeClaimGuardCommands.some((item) => item.textContent.includes("verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown")), "home external claim guard proof commands did not render");
	    assert(homeClaimGuardText.includes(homeClaimReady ? "외부 완료 주장 가능" : "외부 완료 주장 차단") && homeClaimGuardText.includes(homeClaimGuard.dataset.homeExternalClaimGuardStatus) && homeClaimGuardText.includes("Workflow installation") && homeClaimGuardText.includes("Public launch proof") && homeClaimGuardText.includes("External completion claim") && homeClaimGuardText.includes("Stop condition: do not claim readyForExternalClaim"), "home external claim guard text did not render");
	    assert(homeClaimGuardCopyText.includes("JooPark External Completion Claim Guard") && homeClaimGuardCopyText.includes("Status: " + homeClaimGuard.dataset.homeExternalClaimGuardStatus) && homeClaimGuardCopyText.includes("Blocked requirements: " + claimBlockedCount + "/3") && homeClaimGuardCopyText.includes("Next claim proof shortcut:") && homeClaimGuardCopyText.includes("requirement=" + nextClaimProofKey) && homeClaimGuardCopyText.includes("command="), "home external claim guard copy text was not ready");
    const homeClaimGuardButton = qs('[data-action="copy-output-quality-external-claim-guard"]', homeClaimGuard);
    click('[data-action="copy-output-quality-external-claim-guard"]', homeClaimGuard);
    await waitFor(() => {
      const copied = homeClaimGuard.dataset.outputQualityExternalClaimGuardCopied === "true" || homeClaimGuardButton.dataset.outputQualityExternalClaimGuardCopied === "true";
      const statusText = qs("[data-output-quality-audit-external-claim-guard-copy-status]", homeClaimGuard).textContent || "";
      return copied && statusText.includes("복사") &&
	        window.__smokeClipboardText.includes("JooPark External Completion Claim Guard") &&
		        window.__smokeClipboardText.includes("Status: " + homeClaimGuard.dataset.homeExternalClaimGuardStatus) &&
		        window.__smokeClipboardText.includes("Next claim proof shortcut:") &&
		        window.__smokeClipboardText.includes("requirement=" + nextClaimProofKey) &&
		        window.__smokeClipboardText.includes("Stop condition: do not claim readyForExternalClaim");
    }, "home external claim guard copy did not report success");
    homeExternalClaimGuardOk = true;
    const button = qs('[data-action="nav-to"][data-view="system"]', card);
    assert(button.tagName === "BUTTON" && button.getAttribute("type") === "button", "home launch action system navigation did not render as a button");
    click('[data-action="nav-to"][data-view="system"]', card);
    await waitFor(() => document.body.dataset.view === "system" && !document.getElementById("view-system").hidden, "home launch action did not navigate to system status");
    homeLaunchNextActionOk = true;
  });

	  await runStep("home launch blocker resolver exposes active unblock path", async () => {
	    await nav("home");
	    await waitFor(() => {
	      const resolver = document.querySelector("#view-home [data-home-launch-blocker-resolver]");
	      const primary = resolver ? resolver.querySelector("[data-home-launch-blocker-resolver-primary-command]")?.textContent || "" : "";
	      return resolver &&
	        resolver.dataset.homeLaunchBlockerResolverReady === "true" &&
	        ["operator_auth_path", "remote_workflow_file_parity", "launch_proof_capture"].includes(resolver.dataset.homeLaunchBlockerResolverActive) &&
	        ["action_required", "deferred_until_dispatch", "pass"].includes(resolver.dataset.homeLaunchBlockerResolverStatus) &&
	        (primary === "gh auth refresh -h github.com -s workflow" || primary.includes("check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write") || primary.includes("capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --write") || primary.includes("plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects"));
	    }, "home launch blocker resolver did not load the active blocker", 30000);
	    const resolver = qs("#view-home [data-home-launch-blocker-resolver]");
	    const text = resolver.textContent || "";
	    const copyText = qs("[data-home-launch-blocker-resolver-text]", resolver).textContent;
		    const items = Array.from(resolver.querySelectorAll("[data-home-launch-blocker-resolver-item]"));
		    const evidenceGapItems = Array.from(resolver.querySelectorAll("[data-home-launch-blocker-evidence-gap-item]"));
	    const workflowInstallShortcut = resolver.querySelector("[data-home-workflow-install-shortcut]");
	    const workflowInstallShortcutPaths = workflowInstallShortcut ? Array.from(workflowInstallShortcut.querySelectorAll("[data-home-workflow-install-shortcut-path]")) : [];
	    const workflowInstallShortcutGuards = workflowInstallShortcut ? Array.from(workflowInstallShortcut.querySelectorAll("[data-home-workflow-install-shortcut-guard]")) : [];
	    const workflowInstallShortcutCommands = workflowInstallShortcut ? Array.from(workflowInstallShortcut.querySelectorAll("[data-home-workflow-install-shortcut-command]")) : [];
	    const fallbackCommands = Array.from(resolver.querySelectorAll("[data-home-launch-blocker-resolver-fallback-command]"));
	    const activeResolverKey = resolver.dataset.homeLaunchBlockerResolverActive;
	    const resolverInProofCapture = activeResolverKey === "launch_proof_capture";
	    const resolverInRemoteWorkflowParity = activeResolverKey === "remote_workflow_file_parity";
	    const resolverProofReady = resolver.dataset.homeLaunchBlockerResolverLaunchProofReady === "true";
	    const resolverPostInstallProofComplete = resolver.dataset.homeLaunchBlockerResolverPostInstallProofComplete === "true";
	    const postInstallEvidenceGapItem = evidenceGapItems.find((item) => item.dataset.homeLaunchBlockerEvidenceGapKey === "post_install_intake");
	    const postInstallEvidenceGapText = postInstallEvidenceGapItem ? postInstallEvidenceGapItem.textContent || "" : "";
	    const postInstallEvidenceGapCount = postInstallEvidenceGapText.match(/\\d+\\/\\d+ proof fields complete/)?.[0] || "";
	    const resolverExpectedPassCount = resolverInProofCapture ? 5 : (resolverInRemoteWorkflowParity ? 4 : 2);
	    const resolverExpectedActionRequiredCount = resolverInProofCapture ? 0 : (resolverInRemoteWorkflowParity ? 1 : 3);
	    const resolverExpectedDeferredCount = resolverInProofCapture && resolverProofReady ? 0 : 1;
	    const resolverExpectedPrimaryCommand = resolverInProofCapture
	      ? "node scripts/capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --write"
	      : (resolverInRemoteWorkflowParity ? "node scripts/check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write" : "gh auth refresh -h github.com -s workflow");
	    const resolverExpectedVisibleAction = resolverInProofCapture ? "Capture live launch proof" : (resolverInRemoteWorkflowParity ? "Prove remote workflow file parity" : "Resolve workflow auth path");
	    const resolverExpectedBlockedSignal = resolverInProofCapture ? "postPublishEvidenceReady=" + (resolverProofReady ? "true" : "false") : (resolverInRemoteWorkflowParity ? "remoteWorkflowFilesReady=false" : "workflowScopeAvailable=false");
	    const resolverItemByKey = (key) => items.find((item) => item.dataset.homeLaunchBlockerResolverItemKey === key);
	    const resolverOperatorAuthItem = resolverItemByKey("operator_auth_path");
	    const resolverRemoteWorkflowItem = resolverItemByKey("remote_workflow_file_parity");
	    const resolverWorkflowVisibilityItem = resolverItemByKey("workflow_visibility");
	    const resolverDispatchGuardItem = resolverItemByKey("dispatch_guard");
	    const resolverLaunchProofItem = resolverItemByKey("launch_proof_capture");
	    assert(resolver.dataset.homeLaunchBlockerResolverSource === "generated_from_launch_execution_packet" && resolver.dataset.homeLaunchBlockerResolverRepo === "biojuho/BIOJUHO-Projects", "home launch blocker resolver source or repo dataset was incomplete");
	    assert(resolver.dataset.homeLaunchBlockerResolverItemCount === "6" && Number(resolver.dataset.homeLaunchBlockerResolverPassCount || "0") >= resolverExpectedPassCount && Number(resolver.dataset.homeLaunchBlockerResolverActionRequiredCount || "0") === resolverExpectedActionRequiredCount && Number(resolver.dataset.homeLaunchBlockerResolverDeferredCount || "0") === resolverExpectedDeferredCount && resolver.dataset.homeLaunchBlockerResolverProofCommandCount === "6" && Number(resolver.dataset.homeLaunchBlockerResolverFallbackCommandCount || "0") >= 0 && resolver.dataset.homeLaunchBlockerResolverEvidenceGapCount === "3" && resolver.dataset.homeLaunchBlockerResolverRemoteFilesReady === (resolverInProofCapture ? "true" : "false") && resolver.dataset.homeLaunchBlockerResolverPostInstallProofComplete === (resolverPostInstallProofComplete ? "true" : "false"), "home launch blocker resolver counters were incomplete");
		    assert((resolver.dataset.homeLaunchBlockerResolverDispatchGuard || "").includes("Do not run gh workflow run until every action_required item") && (resolver.dataset.homeLaunchBlockerResolverDispatchGuard || "").includes("safeToDispatch=true"), "home launch blocker resolver dispatch guard dataset was incomplete");
	    assert(items.length === 6 && resolverOperatorAuthItem && ["action_required", "pass"].includes(resolverOperatorAuthItem.dataset.homeLaunchBlockerResolverItemStatus) && resolverRemoteWorkflowItem && resolverWorkflowVisibilityItem && resolverDispatchGuardItem?.dataset.homeLaunchBlockerResolverItemStatus === "pass" && resolverLaunchProofItem && ["pass", "deferred_until_dispatch"].includes(resolverLaunchProofItem.dataset.homeLaunchBlockerResolverItemStatus), "home launch blocker resolver checklist items did not render");
	    assert(evidenceGapItems.length === 3 && evidenceGapItems.some((item) => item.dataset.homeLaunchBlockerEvidenceGapKey === "remote_workflow_files" && item.dataset.homeLaunchBlockerEvidenceGapReady === (resolverInProofCapture ? "true" : "false") && item.textContent.includes("files ready") && item.textContent.includes("missing=")) && evidenceGapItems.some((item) => item.dataset.homeLaunchBlockerEvidenceGapKey === "launch_proof" && item.textContent.includes("proofs ready") && item.textContent.includes("capture_launch_proof")) && postInstallEvidenceGapItem && postInstallEvidenceGapCount && postInstallEvidenceGapItem.textContent.includes("proofComplete=" + (resolverPostInstallProofComplete ? "true" : "false")), "home launch blocker resolver evidence gaps did not render");
	    if (workflowInstallShortcut) {
	      const workflowInstallShortcutCommandText = workflowInstallShortcutCommands.map((item) => item.textContent || "").join("\\n");
	      const workflowInstallShortcutPrimaryCommand = workflowInstallShortcut.dataset.homeWorkflowInstallShortcutPrimaryCommand || "";
	      assert(workflowInstallShortcut.dataset.homeWorkflowInstallShortcutReady === "true" && ["workflow_scope_blocked_use_ui_or_refresh", "workflow_scope_available_use_cli"].includes(workflowInstallShortcut.dataset.homeWorkflowInstallShortcutStatus) && Number(workflowInstallShortcut.dataset.homeWorkflowInstallShortcutPathCount || "0") >= 2 && Number(workflowInstallShortcut.dataset.homeWorkflowInstallShortcutCommandCount || "0") >= 10 && workflowInstallShortcut.dataset.homeWorkflowInstallShortcutTargetCount === "2" && workflowInstallShortcut.dataset.homeWorkflowInstallShortcutVerifyCommand.includes("verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown"), "home workflow install shortcut dataset was incomplete");
	      assert(workflowInstallShortcutPaths.length >= 2 && workflowInstallShortcutPaths.some((item) => item.dataset.homeWorkflowInstallShortcutPathKey === "cli_workflow_scope" && item.textContent.includes("install-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write --verify")) && workflowInstallShortcutPaths.some((item) => item.dataset.homeWorkflowInstallShortcutPathKey === "github_ui" && item.textContent.includes("pbcopy < 'docs/github-pages-workflow.yml'") && (item.textContent.includes("github.com/biojuho/BIOJUHO-Projects/new/main") || item.textContent.includes("github.com/biojuho/BIOJUHO-Projects/edit/main"))), "home workflow install shortcut paths did not render");
	      assert(workflowInstallShortcutGuards.length === 2 && workflowInstallShortcutGuards.some((item) => item.textContent.includes("workflow_dispatch requires the workflow file on the repository default branch")) && workflowInstallShortcutGuards.some((item) => item.textContent.includes("workflow scope")), "home workflow install shortcut guards did not render");
	      assert(workflowInstallShortcutCommandText.includes("install-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write --verify") && workflowInstallShortcutCommandText.includes("pbcopy < 'docs/github-pages-workflow.yml'") && (workflowInstallShortcut.dataset.homeWorkflowInstallShortcutStatus === "workflow_scope_blocked_use_ui_or_refresh" ? workflowInstallShortcutPrimaryCommand.includes("pbcopy < 'docs/github-pages-workflow.yml'") : workflowInstallShortcutPrimaryCommand.includes("install-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write --verify")) && qs("[data-home-workflow-install-shortcut-verify]", workflowInstallShortcut).textContent.includes("verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown"), "home workflow install shortcut commands did not render");
	    } else {
	      assert(resolverInProofCapture, "home workflow install shortcut disappeared before proof-capture stage");
	    }
		    assert((resolverInProofCapture && fallbackCommands.length === 0) || (fallbackCommands.length >= 3 && fallbackCommands[0].textContent.includes("pbcopy < 'docs/github-pages-workflow.yml'") && (fallbackCommands[0].textContent.includes("github.com/biojuho/BIOJUHO-Projects/new/main") || fallbackCommands[0].textContent.includes("github.com/biojuho/BIOJUHO-Projects/edit/main")) && fallbackCommands.some((item) => item.textContent.includes("check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write"))), "home launch blocker resolver fallback commands did not render");
	    assert(text.includes("launch unblock resolver") && text.includes(resolverExpectedVisibleAction) && text.includes(resolverExpectedBlockedSignal) && text.includes("evidence gap") && text.includes("Remote workflow files") && text.includes("Launch proof") && text.includes("Post-install intake") && text.includes("GitHub UI fallback") && text.includes("Do not run gh workflow run"), "home launch blocker resolver visible text did not render");
	    assert(copyText.includes("JooPark Launch Blocker Resolver") && copyText.includes("activeItemKey=" + activeResolverKey) && copyText.includes("blockedSignal=" + resolverExpectedBlockedSignal) && copyText.includes("Primary proof command: " + resolverExpectedPrimaryCommand) && copyText.includes("Evidence gap:") && copyText.includes("remote_workflow_files: ") && copyText.includes("files ready") && copyText.includes("launch_proof: ") && copyText.includes("proofs ready") && copyText.includes("post_install_intake: ") && copyText.includes(postInstallEvidenceGapCount) && (!workflowInstallShortcut || (copyText.includes("Workflow install shortcut:") && copyText.includes("JooPark Workflow Install Shortcut") && copyText.includes("Target workflow files: 2"))) && copyText.includes("GitHub UI fallback:") && copyText.includes("Do not run gh workflow run"), "home launch blocker resolver copy text was not ready");
	    const button = qs('[data-action="copy-home-launch-blocker-resolver"]', resolver);
	    click('[data-action="copy-home-launch-blocker-resolver"]', resolver);
	    await waitFor(() => {
	      const copied = resolver.dataset.homeLaunchBlockerResolverCopied === "true" || button.dataset.homeLaunchBlockerResolverCopied === "true";
	      const statusText = qs("[data-home-launch-blocker-resolver-copy-status]", resolver).textContent || "";
	      return copied && statusText.includes("복사") &&
		        window.__smokeClipboardText.includes("JooPark Launch Blocker Resolver") &&
		        window.__smokeClipboardText.includes("activeItemKey=" + activeResolverKey) &&
	        window.__smokeClipboardText.includes(resolverExpectedBlockedSignal) &&
	        (!workflowInstallShortcut || window.__smokeClipboardText.includes("JooPark Workflow Install Shortcut")) &&
	        (!workflowInstallShortcut || window.__smokeClipboardText.includes("Install paths: 2")) &&
		        window.__smokeClipboardText.includes("GitHub UI fallback:") &&
		        window.__smokeClipboardText.includes("Do not run gh workflow run");
	    }, "home launch blocker resolver copy did not report success");
    homeLaunchBlockerResolverOk = true;
  });

  await runStep("home upcoming event opens accessibly", async () => {
    await nav("home");
    await waitFor(() => document.querySelector("#view-home .home-upcoming-open"), "home upcoming event button did not render");
    const upcomingButton = qs("#view-home .home-upcoming-open");
    assert(upcomingButton.tagName === "BUTTON", "home upcoming event control should be a button");
    assert(upcomingButton.getAttribute("type") === "button", "home upcoming event button should not submit forms");
    assert(upcomingButton.dataset.action === "open-event" && upcomingButton.dataset.eventId, "home upcoming event button is missing open-event metadata");
    upcomingButton.focus();
    assert(document.activeElement === upcomingButton, "home upcoming event button did not receive focus");
    upcomingButton.click();
    await waitFor(() => document.querySelector("#modal.open"), "home upcoming event button did not open the event modal");
    assert((document.getElementById("modalTitle")?.textContent || "").includes("일정"), "home upcoming event did not open an event modal");
    click('#modal [data-action="close-modal"]');
    await waitFor(() => !document.querySelector("#modal.open"), "home upcoming event modal did not close");
    homeUpcomingEventOpenOk = true;
  });

  await runStep("home one-step todo quick add", async () => {
    const title = marker + " home todo";
    await nav("home");
    const form = qs('#view-home .home-quickadd[data-action="home-todo-quick-add"]');
    fill('#view-home .home-quickadd [name="title"]', title);
    select('#view-home .home-quickadd [name="priority"]', "high");
    fill('#view-home .home-quickadd [name="due"]', "2026-06-15");
    form.requestSubmit();
    await waitFor(() => dashboard.todos.some((todo) => todo.title === title), "home quick todo was not saved in dashboard");
    const payload = savedPayload();
    assert(payload.todos.some((todo) => todo.title === title && todo.priority === "high" && todo.due === "2026-06-15"), "home quick todo was not persisted with selected metadata");
    assert(document.body.dataset.view === "home", "home quick todo should keep the user on the dashboard");
    assert(document.activeElement === qs('#view-home .home-quickadd [name="title"]'), "home quick todo did not refocus the input");
    homeQuickTodoOk = true;
  });

  await runStep("calendar event modal save", async () => {
    const title = marker + " event";
    await nav("cal");
    click('[data-action="cal-add"]');
    fill('#eventForm [name="title"]', title);
    fill('#eventForm [name="date"]', "2026-06-15");
    fill('#eventForm [name="start"]', "09:30");
    fill('#eventForm [name="end"]', "10:00");
    fill('#eventForm [name="location"]', "release room");
    await confirmModal();
    assert(dashboard.events.some((event) => event.title === title), "event was not saved in dashboard");
    assert(savedPayload().events.some((event) => event.title === title), "event was not persisted");
  });

  await runStep("calendar grid keyboard navigation", async () => {
    await nav("cal");
    const grid = qs("#view-cal .sched-grid");
    assert(grid.getAttribute("role") === "grid", "calendar month surface did not expose grid role");
    assert((grid.getAttribute("aria-label") || "").includes("월 달력"), "calendar grid did not expose a month label");
    const selected = qs('#view-cal [data-action="cal-open-day"][aria-selected="true"]');
    assert(selected.getAttribute("role") === "gridcell", "calendar day did not expose gridcell role");
    assert(selected.getAttribute("tabindex") === "0", "calendar day is not keyboard focusable");
    assert((selected.getAttribute("aria-label") || "").includes("선택됨"), "selected calendar day label did not announce selection");
    const startDate = selected.dataset.date;
    selected.focus();
    assert(document.activeElement === selected, "calendar day did not receive focus");
    selected.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true, cancelable: true }));
    const nextDate = addDaysISO(startDate, 1);
    await waitFor(() => state.calSelected === nextDate, "calendar ArrowRight did not move selected day");
    const next = qs('#view-cal [data-action="cal-open-day"][data-date="' + nextDate + '"]');
    assert(next.getAttribute("aria-selected") === "true", "calendar moved day did not expose selected state");
    await waitFor(() => document.activeElement === next, "calendar keyboard navigation did not restore focus to moved day");
    assert(document.activeElement === next, "calendar keyboard navigation did not restore focus to moved day");
    calendarGridKeyboardOk = true;
  });

  await runStep("calendar month week day mode switch", async () => {
    await nav("cal");
    assert(qs('#view-cal [data-action="cal-mode"][data-mode="month"]').getAttribute("aria-pressed") === "true", "calendar month mode did not start active");
    click('#view-cal [data-action="cal-mode"][data-mode="week"]');
    await waitFor(() => state.calMode === "week" && document.querySelector('#view-cal [data-calendar-view-mode="week"] .sched-week-board'), "calendar week mode did not render");
    const weekButton = qs('#view-cal [data-action="cal-mode"][data-mode="week"]');
    assert(weekButton.getAttribute("aria-pressed") === "true", "calendar week mode did not expose pressed state");
    assert(qsa("#view-cal .sched-week-day").length === 7, "calendar week mode did not render seven day columns");
    click('#view-cal [data-action="cal-mode"][data-mode="day"]');
    await waitFor(() => state.calMode === "day" && document.querySelector('#view-cal [data-calendar-view-mode="day"] .sched-day-board'), "calendar day mode did not render");
    assert(qs("#view-cal .sched-day-head").innerText.includes("개 일정"), "calendar day mode did not expose the day summary");
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "m", bubbles: true, cancelable: true }));
    await waitFor(() => state.calMode === "month" && document.querySelector('#view-cal [data-calendar-view-mode="month"] .sched-grid'), "calendar keyboard shortcut did not return to month mode");
    calendarModeSwitchOk = true;
  });

  await runStep("calendar search no-results recovery", async () => {
    assert(window.JooParkSearchEmptyState && window.JooParkSearchEmptyState.version === "joopark-search-empty-state/v1" && typeof window.JooParkSearchEmptyState.create === "function", "search empty state runtime module was not loaded");
    assert(window.JooParkCalendarView && window.JooParkCalendarView.version === "joopark-calendar-view/v1" && typeof window.JooParkCalendarView.create === "function", "calendar view runtime module was not loaded");
    searchEmptyStateModuleOk = true;
    calendarViewModuleOk = true;
    await nav("cal");
    await waitFor(() => document.querySelectorAll('#view-cal [data-search-result="calendar"]').length > 0, "calendar did not render searchable events before empty-state search");
    fill("#globalSearch", "NO_MATCH_" + marker);
    await waitFor(() => document.querySelector('#view-cal [data-search-empty="calendar"]'), "calendar search empty state did not render");
    const empty = qs('#view-cal [data-search-empty="calendar"]');
    assert(empty.getAttribute("role") === "status", "calendar search empty state does not expose status role");
    assert((document.getElementById("searchCount")?.textContent || "").includes("검색 결과 없음"), "calendar search status did not announce no results");
    assert(!document.querySelector("#view-cal .sched-agenda-list .agenda-item"), "calendar agenda kept unmatched selected event under no-result search");
    assert(!document.querySelector("#view-cal .agenda-todo"), "calendar agenda kept unmatched due todo under no-result search");
    click('#view-cal [data-action="clear-search"]');
    await waitFor(() => !document.querySelector('#view-cal [data-search-empty="calendar"]'), "calendar search clear did not restore results");
    assert(document.getElementById("globalSearch").value === "", "calendar global search input was not cleared");
    assert(document.activeElement === document.getElementById("globalSearch"), "calendar clear search did not restore focus to global search input");
    assert(document.querySelectorAll('#view-cal [data-search-result="calendar"]').length > 0, "calendar event chips did not return after clearing search");
    calendarSearchRecoveryOk = true;
  });

  await runStep("todo quick add and toggle", async () => {
    const title = marker + " todo";
    await nav("todo");
    fill('#view-todo .todo-quickadd [name="title"]', title);
    select('#view-todo .todo-quickadd [name="priority"]', "high");
    fill('#view-todo .todo-quickadd [name="due"]', "2026-06-15");
    qs("#view-todo .todo-quickadd").requestSubmit();
    await waitFor(() => dashboard.todos.some((todo) => todo.title === title), "todo was not quick-added");
    const todo = dashboard.todos.find((item) => item.title === title);
    click('[data-action="todo-toggle"][data-todo-id="' + todo.id + '"]');
    await waitFor(() => dashboard.todos.find((item) => item.id === todo.id).done === true, "todo toggle did not persist done state");
    assert(savedPayload().todos.find((item) => item.id === todo.id).done === true, "todo done state was not persisted");
  });

  await runStep("todo search no-results recovery", async () => {
    assert(window.JooParkTodoView && window.JooParkTodoView.version === "joopark-todo-view/v1" && typeof window.JooParkTodoView.create === "function", "todo view runtime module was not loaded");
    todoViewModuleOk = true;
    await nav("todo");
    fill("#globalSearch", "NO_MATCH_" + marker);
    await waitFor(() => document.querySelector('#view-todo [data-search-empty="todo"]'), "todo search empty state did not render");
    const empty = qs('#view-todo [data-search-empty="todo"]');
    assert(empty.getAttribute("role") === "status", "todo search empty state does not expose status role");
    assert((document.getElementById("searchCount")?.textContent || "").includes("검색 결과 없음"), "search status did not announce no results");
    click('#view-todo [data-action="clear-search"]');
    await waitFor(() => !document.querySelector('#view-todo [data-search-empty="todo"]'), "todo search clear did not restore results");
    assert(document.getElementById("globalSearch").value === "", "global search input was not cleared");
    assert(document.activeElement === document.getElementById("globalSearch"), "clear search did not restore focus to global search input");
    assert(document.querySelectorAll('#view-todo [data-search-result="todo"]').length > 0, "todo rows did not return after clearing search");
    todoSearchRecoveryOk = true;
  });

  await runStep("topbar search clear control", async () => {
    await nav("todo");
    fill("#globalSearch", marker);
    const clear = qs("#globalSearchClear");
    await waitFor(() => !clear.hidden, "topbar search clear button did not appear after typing");
    const rect = clear.getBoundingClientRect();
    assert(rect.width >= 32 && rect.height >= 32, "topbar search clear button is below 32px touch target");
    click("#globalSearchClear");
    await waitFor(() => document.getElementById("globalSearch").value === "", "topbar search clear button did not clear query");
    assert(document.activeElement === document.getElementById("globalSearch"), "topbar search clear button did not restore focus");
    assert(clear.hidden, "topbar search clear button stayed visible after clearing");
    fill("#globalSearch", marker);
    await waitFor(() => !clear.hidden, "topbar search clear button did not reappear before Escape clear");
    qs("#globalSearch").dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true, cancelable: true }));
    await waitFor(() => document.getElementById("globalSearch").value === "", "Escape did not clear topbar search query");
    assert(document.activeElement === document.getElementById("globalSearch"), "Escape search clear did not keep focus in the search input");
    assert(clear.hidden, "topbar search clear button stayed visible after Escape clear");
    topbarSearchClearOk = true;
  });

  await runStep("note modal save and pin", async () => {
    const title = marker + " note";
    await nav("notes");
    click('[data-action="note-add"]');
    fill('#noteForm [name="title"]', title);
    fill('#noteForm [name="body"]', [
      '**release** checklist',
      '',
      '<a href="javascript:window.__noteXss=1">unsafe link</a><span onclick="window.__noteXss=1">unsafe attr</span><script>window.__noteXss=1</script>',
    ].join('\\n'));
    check('#noteForm [name="pinned"]', true);
    window.__noteXss = 0;
    await confirmModal();
    const note = dashboard.notes.find((item) => item.title === title);
    assert(note && note.pinned, "note was not saved pinned");
    assert(savedPayload().notes.some((item) => item.title === title && item.pinned), "note was not persisted");
    const noteCard = Array.from(document.querySelectorAll(".note-card"))
      .find((card) => card.querySelector(".note-title")?.textContent.includes(title));
    assert(noteCard, "saved note card was not rendered");
    assert(noteCard.querySelector(".markdown-body strong")?.textContent === "release", "markdown strong text was not rendered");
    assert(!noteCard.querySelector("script"), "unsafe script tag was not sanitized from note markdown");
    assert(!noteCard.querySelector("[onclick]"), "unsafe event handler attribute was not sanitized from note markdown");
    assert(!Array.from(noteCard.querySelectorAll("a")).some((link) => /^javascript:/i.test(link.getAttribute("href") || "")), "unsafe javascript link was not sanitized from note markdown");
    assert(window.__noteXss === 0, "unsafe note markdown executed script");
    markdownSanitizedOk = true;
  });

  await runStep("notes search no-results recovery", async () => {
    assert(window.JooParkNotesView && window.JooParkNotesView.version === "joopark-notes-view/v1" && typeof window.JooParkNotesView.create === "function", "notes view runtime module was not loaded");
    notesViewModuleOk = true;
    await nav("notes");
    fill("#globalSearch", "NO_MATCH_" + marker);
    await waitFor(() => document.querySelector('#view-notes [data-search-empty="notes"]'), "notes search empty state did not render");
    const empty = qs('#view-notes [data-search-empty="notes"]');
    assert(empty.getAttribute("role") === "status", "notes search empty state does not expose status role");
    assert((document.getElementById("searchCount")?.textContent || "").includes("검색 결과 없음"), "notes search status did not announce no results");
    click('#view-notes [data-action="clear-search"]');
    await waitFor(() => !document.querySelector('#view-notes [data-search-empty="notes"]'), "notes search clear did not restore results");
    assert(document.getElementById("globalSearch").value === "", "notes global search input was not cleared");
    assert(document.activeElement === document.getElementById("globalSearch"), "notes clear search did not restore focus to global search input");
    assert(document.querySelectorAll('#view-notes [data-search-result="notes"]').length > 0, "note cards did not return after clearing search");
    notesSearchRecoveryOk = true;
  });

  await runStep("habit modal save and day toggle", async () => {
    const name = marker + " habit";
    await nav("habits");
    click('[data-action="habit-add"]');
    fill('#habitForm [name="name"]', name);
    fill('#habitForm [name="emoji"]', "OK");
    fill('#habitForm [name="target"]', "5");
    await confirmModal();
    const habit = dashboard.habits.find((item) => item.name === name);
    assert(habit, "habit was not saved");
    const day = qs('[data-action="habit-toggle"][data-habit-id="' + habit.id + '"]');
    const date = day.dataset.date;
    day.click();
    await waitFor(() => !!dashboard.habits.find((item) => item.id === habit.id).log[date], "habit day toggle did not save");
  });

  await runStep("habit search no-results recovery", async () => {
    assert(window.JooParkHabitsView && window.JooParkHabitsView.version === "joopark-habits-view/v1" && typeof window.JooParkHabitsView.create === "function", "habits view runtime module was not loaded");
    habitsViewModuleOk = true;
    await nav("habits");
    await waitFor(() => document.querySelectorAll('#view-habits [data-search-result="habits"]').length > 0, "habits did not render searchable cards before empty-state search");
    fill("#globalSearch", "NO_MATCH_" + marker);
    await waitFor(() => document.querySelector('#view-habits [data-search-empty="habits"]'), "habit search empty state did not render");
    const empty = qs('#view-habits [data-search-empty="habits"]');
    assert(empty.getAttribute("role") === "status", "habit search empty state does not expose status role");
    assert((document.getElementById("searchCount")?.textContent || "").includes("검색 결과 없음"), "habit search status did not announce no results");
    click('#view-habits [data-action="clear-search"]');
    await waitFor(() => !document.querySelector('#view-habits [data-search-empty="habits"]'), "habit search clear did not restore cards");
    assert(document.getElementById("globalSearch").value === "", "habit global search input was not cleared");
    assert(document.activeElement === document.getElementById("globalSearch"), "habit clear search did not restore focus to global search input");
    assert(document.querySelectorAll('#view-habits [data-search-result="habits"]').length > 0, "habit cards did not return after clearing search");
    habitSearchRecoveryOk = true;
  });

  await runStep("stats search stays inert with scoped affordance", async () => {
    await nav("home");
    const homeSearch = qs("#globalSearch");
    assert(homeSearch.readOnly, "home inert search input was not readonly");
    assert(homeSearch.getAttribute("aria-readonly") === "true", "home inert search input did not expose aria-readonly");
    assert((homeSearch.placeholder || "").includes("⌘K"), "home inert search placeholder did not point to command palette");
    homeSearch.focus();
    await waitFor(() => (document.getElementById("searchCount")?.textContent || "").includes("요약 전용"), "home inert search did not announce why it cannot filter this view");
    fill("#globalSearch", "NO_MATCH_" + marker);
    await sleep(220);
    assert(document.getElementById("globalSearch").value === "", "home inert search accepted typed query");
    assert(state.query === "", "home inert search left a global query behind");
    homeSearch.focus();
    homeSearch.dispatchEvent(new KeyboardEvent("keydown", { key: "/", bubbles: true, cancelable: true }));
    await waitFor(() => document.getElementById("palette")?.classList.contains("open"), "slash on inert view did not open command palette");
    const paletteInput = qs("#paletteInput");
    assert(document.activeElement === paletteInput, "palette input was not focused after inert slash open");
    paletteInput.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true, cancelable: true }));
    await waitFor(() => document.getElementById("palette")?.getAttribute("aria-hidden") === "true", "palette did not close after inert slash check");

    await nav("stats");
    assert(window.JooParkStatsView && window.JooParkStatsView.version === "joopark-stats-view/v1" && typeof window.JooParkStatsView.create === "function", "stats view runtime module was not loaded");
    statsViewModuleOk = true;
    const statsSearch = qs("#globalSearch");
    assert(statsSearch.readOnly, "stats inert search input was not readonly");
    assert((statsSearch.placeholder || "").includes("⌘K"), "stats inert search placeholder did not point to command palette");
    fill("#globalSearch", "NO_MATCH_" + marker);
    await sleep(220);
    assert(!document.querySelector('#view-stats [data-search-empty]'), "stats rendered a search empty state even though it is an aggregate view");
    assert(document.querySelectorAll('#view-stats [data-search-result]').length === 0, "stats exposed searchable result markers even though it is an aggregate view");
    assert((document.getElementById("searchCount")?.textContent || "").includes("요약 전용"), "stats search status did not explain the inert aggregate view");
    await sleep(220);
    assert(document.getElementById("globalSearch").value === "", "stats inert search accepted typed query");
    assert(state.query === "", "stats inert search left a global query behind");
    statsSearchInertOk = true;
  });

  await runStep("workspace candidate portfolio search", async () => {
    await nav("pm-portfolio");
    assert(window.JooParkPortfolioView && window.JooParkPortfolioView.version === "joopark-portfolio-view/v1" && typeof window.JooParkPortfolioView.create === "function", "portfolio view runtime module was not loaded");
    const portfolioList = qs('#view-pm-portfolio .portfolio-grid[role="list"]');
    const portfolioItems = Array.from(portfolioList.querySelectorAll('.portfolio-card[role="listitem"]'));
    assert((portfolioList.getAttribute("aria-label") || "").includes("포트폴리오"), "portfolio project list did not expose a useful label");
    assert(portfolioList.getAttribute("aria-setsize") === String(portfolioItems.length), "portfolio project list set size did not match visible items");
    assert(
      portfolioItems.length > 0 &&
        portfolioItems.every((item, index) =>
          item.getAttribute("aria-posinset") === String(index + 1) &&
          item.getAttribute("aria-setsize") === String(portfolioItems.length) &&
          (item.getAttribute("aria-label") || "").includes("포트폴리오 항목")),
      "portfolio cards did not expose listitem semantics");
    portfolioViewModuleOk = true;
    const defaultCandidateCards = document.querySelectorAll('#view-pm-portfolio .portfolio-card[data-source-kind="adoption-candidate"]');
    assert(defaultCandidateCards.length === 0, "portfolio rendered adoption candidates before reference projects were enabled");
    assert(dashboard.settings.showReferenceProjects !== true, "reference project setting was enabled by default");
    click('[data-action="toggle-reference-projects"]');
    await waitFor(() => dashboard.settings.showReferenceProjects === true && document.querySelectorAll("#view-pm-portfolio .portfolio-card").length === dashboard.projects.length, "reference project toggle did not reveal adoption candidates");
    portfolioReferenceToggleOk = true;
    const candidate = dashboard.projects.find((project) => project.name === "OpenLoaf/OpenLoaf");
    assert(candidate && candidate.sourceKind === "adoption-candidate", "OpenLoaf workspace candidate was not loaded");
    const planeCandidate = dashboard.projects.find((project) => project.name === "makeplane/plane");
    assert(planeCandidate && planeCandidate.sourceKind === "adoption-candidate", "Plane PM benchmark candidate was not loaded");
    const appFlowyCandidate = dashboard.projects.find((project) => project.name === "AppFlowy-IO/AppFlowy");
    assert(appFlowyCandidate && appFlowyCandidate.sourceKind === "adoption-candidate", "AppFlowy workspace benchmark candidate was not loaded");
    const affineCandidate = dashboard.projects.find((project) => project.name === "toeverything/AFFiNE");
    assert(affineCandidate && affineCandidate.sourceKind === "adoption-candidate", "AFFiNE workspace benchmark candidate was not loaded");
    const outlineCandidate = dashboard.projects.find((project) => project.name === "outline/outline");
    assert(outlineCandidate && outlineCandidate.sourceKind === "adoption-candidate", "Outline knowledge-base benchmark candidate was not loaded");
    const bookStackCandidate = dashboard.projects.find((project) => project.name === "BookStackApp/BookStack");
    assert(bookStackCandidate && bookStackCandidate.sourceKind === "adoption-candidate", "BookStack documentation benchmark candidate was not loaded");
    const wikiJsCandidate = dashboard.projects.find((project) => project.name === "requarks/wiki");
    assert(wikiJsCandidate && wikiJsCandidate.sourceKind === "adoption-candidate", "Wiki.js self-hosted wiki benchmark candidate was not loaded");
    const epicenterCandidate = dashboard.projects.find((project) => project.name === "EpicenterHQ/epicenter");
    assert(epicenterCandidate && epicenterCandidate.sourceKind === "adoption-candidate", "Epicenter workspace benchmark candidate was not loaded");
    const benchmarkCandidate = dashboard.projects.find((project) => project.name === "colanode/colanode");
    assert(benchmarkCandidate && benchmarkCandidate.sourceKind === "adoption-candidate", "Colanode workspace benchmark candidate was not loaded");
    const parabolCandidate = dashboard.projects.find((project) => project.name === "ParabolInc/parabol");
    assert(parabolCandidate && parabolCandidate.sourceKind === "adoption-candidate", "Parabol workspace benchmark candidate was not loaded");
    const worklenzCandidate = dashboard.projects.find((project) => project.name === "Worklenz/worklenz");
    assert(worklenzCandidate && worklenzCandidate.sourceKind === "adoption-candidate", "Worklenz workspace benchmark candidate was not loaded");
    const anytypeCandidate = dashboard.projects.find((project) => project.name === "anyproto/anytype-ts");
    assert(anytypeCandidate && anytypeCandidate.sourceKind === "adoption-candidate", "Anytype workspace benchmark candidate was not loaded");
    const focalboardCandidate = dashboard.projects.find((project) => project.name === "mattermost-community/focalboard");
    assert(focalboardCandidate && focalboardCandidate.sourceKind === "adoption-candidate", "Focalboard workspace benchmark candidate was not loaded");
    const remainingFreshnessTargets = [
      { key: "workstream", name: "happybhati/workstream", expectedUrl: "https://github.com/happybhati/workstream" },
      { key: "taskosaur", name: "Taskosaur/Taskosaur", expectedUrl: "https://github.com/Taskosaur/Taskosaur" },
      { key: "markdownTaskManager", name: "ioniks/MarkdownTaskManager", expectedUrl: "https://github.com/ioniks/MarkdownTaskManager" },
      { key: "taskcoach", name: "taskcoach/taskcoach", expectedUrl: "https://github.com/taskcoach/taskcoach" },
      { key: "fluidCalendar", name: "dotnetfactory/fluid-calendar", expectedUrl: "https://github.com/dotnetfactory/fluid-calendar" },
	    ].map((target) => {
	      const candidate = dashboard.projects.find((project) => project.name === target.name);
	      assert(candidate && candidate.sourceKind === "adoption-candidate", target.name + " workspace benchmark candidate was not loaded");
	      return { ...target, candidate };
	    });
	    const taskosaurCandidate = remainingFreshnessTargets.find((target) => target.key === "taskosaur").candidate;
	    assert(projectPromptHandoffTarget(taskosaurCandidate)?.kind === "benchmark", "Taskosaur prompt handoff target was not computed");
	    fill("#globalSearch", "taskosaur");
	    await waitFor(() => state.query === "taskosaur" && document.querySelectorAll("#view-pm-portfolio .portfolio-card").length === 1, "Taskosaur search did not isolate the prompt handoff candidate");
	    const taskosaurSearchCard = qs('#view-pm-portfolio .portfolio-card[data-project-id="' + taskosaurCandidate.id + '"]');
	    const taskosaurCardPromptCta = qs('[data-action="show-project-prompt-handoff"][data-prompt-handoff-target="benchmark"]', taskosaurSearchCard);
	    assert(taskosaurCardPromptCta.textContent.includes("prompt handoff"), "Taskosaur search result did not expose prompt handoff CTA");
	    click('[data-action="open-project"][data-project-id="' + taskosaurCandidate.id + '"]', taskosaurSearchCard);
	    await waitFor(() => refs.sheets.root.classList.contains("open") && refs.sheets.title.textContent.includes("Taskosaur/Taskosaur"), "Taskosaur detail sheet did not open from search result");
	    const taskosaurSheetPromptCta = qs('[data-action="show-project-prompt-handoff"]', refs.sheets.root);
	    assert(taskosaurSheetPromptCta.textContent.includes("prompt handoff"), "Taskosaur detail sheet did not expose prompt handoff CTA");
	    click('[data-action="show-project-prompt-handoff"]', refs.sheets.root);
	    await waitFor(() => !refs.sheets.root.classList.contains("open") && state.query === "" && state.portfolioFilter === "candidates" && state.portfolioBenchmarkFilter === "focused" && document.querySelector('[data-benchmark-review-handoff][data-prompt-handoff-revealed="true"]'), "Taskosaur prompt handoff CTA did not reveal the benchmark handoff");
	    const revealedBenchmarkHandoff = qs('[data-benchmark-review-handoff][data-prompt-handoff-revealed="true"]');
	    assert(document.activeElement === revealedBenchmarkHandoff, "Taskosaur prompt handoff CTA did not focus the revealed handoff");
	    assert(qs("[data-review-handoff-text]", revealedBenchmarkHandoff).innerText.includes("## Output Schema"), "Taskosaur revealed handoff did not include the structured output schema");
	    click('[data-action="portfolio-filter"][data-filter="all"]');
	    await waitFor(() => state.portfolioFilter === "all" && state.portfolioBenchmarkFilter === "all" && document.querySelectorAll("#view-pm-portfolio .portfolio-card").length === dashboard.projects.length, "portfolio filter did not reset after prompt handoff CTA check");
	    const riskCandidate = dashboard.projects.find((project) => project.name === "opf/openproject");
    assert(riskCandidate && projectCandidateAction(riskCandidate)?.label === "리스크 리뷰", "OpenProject candidate risk action was not computed");
    const adoptionResponse = await fetch("./data/adoption-candidates.json", { cache: "no-store" });
    assert(adoptionResponse.ok, "adoption candidate snapshot did not load for metadata refresh");
    const adoptionSnapshot = await adoptionResponse.json();
    assert(adoptionSnapshot.seedScope === "demo-local-snapshot" && String(adoptionSnapshot.seedPolicy || "").includes("not a live DB"), "adoption candidate seed policy was not explicit");
    const candidateSeedBadge = qs("#view-pm-portfolio [data-candidate-seed-scope]");
    assert(candidateSeedBadge && candidateSeedBadge.dataset.candidateSeedScope === "demo-local-snapshot" && candidateSeedBadge.textContent.includes("demo snapshot"), "portfolio candidate seed boundary did not render");
    candidateSeedScopeOk = true;
    const formatMetric = (value) => typeof value === "number" && Number.isFinite(value) ? value.toLocaleString("en-US") : "-";
    const snapshotEpicenter = adoptionSnapshot.projects.find((project) => project.name === "EpicenterHQ/epicenter");
    assert(snapshotEpicenter && /^[0-9a-f]{40}$/i.test(snapshotEpicenter.lastCommit || "") && !Number.isNaN(Date.parse(snapshotEpicenter.pushedAt || "")), "Epicenter snapshot freshness evidence was missing");
    const shortEpicenterCommit = snapshotEpicenter.lastCommit.slice(0, 8);
    const snapshotOpenLoaf = adoptionSnapshot.projects.find((project) => project.name === "OpenLoaf/OpenLoaf");
    assert(snapshotOpenLoaf && /^[0-9a-f]{40}$/i.test(snapshotOpenLoaf.lastCommit || "") && !Number.isNaN(Date.parse(snapshotOpenLoaf.pushedAt || "")), "OpenLoaf snapshot freshness evidence was missing");
    const shortOpenLoafCommit = snapshotOpenLoaf.lastCommit.slice(0, 8);
    const snapshotPlane = adoptionSnapshot.projects.find((project) => project.name === "makeplane/plane");
    assert(snapshotPlane && /^[0-9a-f]{40}$/i.test(snapshotPlane.lastCommit || "") && !Number.isNaN(Date.parse(snapshotPlane.pushedAt || "")), "Plane snapshot freshness evidence was missing");
    const shortPlaneCommit = snapshotPlane.lastCommit.slice(0, 8);
    const snapshotAppFlowy = adoptionSnapshot.projects.find((project) => project.name === "AppFlowy-IO/AppFlowy");
    assert(snapshotAppFlowy && /^[0-9a-f]{40}$/i.test(snapshotAppFlowy.lastCommit || "") && !Number.isNaN(Date.parse(snapshotAppFlowy.pushedAt || "")), "AppFlowy snapshot freshness evidence was missing");
    const shortAppFlowyCommit = snapshotAppFlowy.lastCommit.slice(0, 8);
    const snapshotAffine = adoptionSnapshot.projects.find((project) => project.name === "toeverything/AFFiNE");
    assert(snapshotAffine && /^[0-9a-f]{40}$/i.test(snapshotAffine.lastCommit || "") && !Number.isNaN(Date.parse(snapshotAffine.pushedAt || "")), "AFFiNE snapshot freshness evidence was missing");
    const shortAffineCommit = snapshotAffine.lastCommit.slice(0, 8);
    const snapshotOutline = adoptionSnapshot.projects.find((project) => project.name === "outline/outline");
    assert(snapshotOutline && /^[0-9a-f]{40}$/i.test(snapshotOutline.lastCommit || "") && !Number.isNaN(Date.parse(snapshotOutline.pushedAt || "")), "Outline snapshot freshness evidence was missing");
    const shortOutlineCommit = snapshotOutline.lastCommit.slice(0, 8);
    const snapshotBookStack = adoptionSnapshot.projects.find((project) => project.name === "BookStackApp/BookStack");
    assert(snapshotBookStack && /^[0-9a-f]{40}$/i.test(snapshotBookStack.lastCommit || "") && !Number.isNaN(Date.parse(snapshotBookStack.pushedAt || "")), "BookStack snapshot freshness evidence was missing");
    const shortBookStackCommit = snapshotBookStack.lastCommit.slice(0, 8);
    const snapshotWikiJs = adoptionSnapshot.projects.find((project) => project.name === "requarks/wiki");
    assert(snapshotWikiJs && /^[0-9a-f]{40}$/i.test(snapshotWikiJs.lastCommit || "") && !Number.isNaN(Date.parse(snapshotWikiJs.pushedAt || "")), "Wiki.js snapshot freshness evidence was missing");
    const shortWikiJsCommit = snapshotWikiJs.lastCommit.slice(0, 8);
    const snapshotColanode = adoptionSnapshot.projects.find((project) => project.name === "colanode/colanode");
    assert(snapshotColanode && /^[0-9a-f]{40}$/i.test(snapshotColanode.lastCommit || "") && !Number.isNaN(Date.parse(snapshotColanode.pushedAt || "")), "Colanode snapshot freshness evidence was missing");
    const shortColanodeCommit = snapshotColanode.lastCommit.slice(0, 8);
    const snapshotOpenProject = adoptionSnapshot.projects.find((project) => project.name === "opf/openproject");
    assert(snapshotOpenProject && /^[0-9a-f]{40}$/i.test(snapshotOpenProject.lastCommit || "") && !Number.isNaN(Date.parse(snapshotOpenProject.pushedAt || "")), "OpenProject snapshot freshness evidence was missing");
    const shortOpenProjectCommit = snapshotOpenProject.lastCommit.slice(0, 8);
    const snapshotParabol = adoptionSnapshot.projects.find((project) => project.name === "ParabolInc/parabol");
    assert(snapshotParabol && /^[0-9a-f]{40}$/i.test(snapshotParabol.lastCommit || "") && !Number.isNaN(Date.parse(snapshotParabol.pushedAt || "")), "Parabol snapshot freshness evidence was missing");
    const shortParabolCommit = snapshotParabol.lastCommit.slice(0, 8);
    const snapshotVeritas = adoptionSnapshot.projects.find((project) => project.name === "Veritas-7/autoresearch-skill-system");
    assert(snapshotVeritas && /^[0-9a-f]{40}$/i.test(snapshotVeritas.lastCommit || ""), "Veritas snapshot freshness evidence was missing");
    const shortVeritasCommit = snapshotVeritas.lastCommit.slice(0, 8);
    const snapshotLeantime = adoptionSnapshot.projects.find((project) => project.name === "Leantime/leantime");
    assert(snapshotLeantime && /^[0-9a-f]{40}$/i.test(snapshotLeantime.lastCommit || "") && !Number.isNaN(Date.parse(snapshotLeantime.pushedAt || "")), "Leantime snapshot freshness evidence was missing");
    const shortLeantimeCommit = snapshotLeantime.lastCommit.slice(0, 8);
    const snapshotWorklenz = adoptionSnapshot.projects.find((project) => project.name === "Worklenz/worklenz");
    assert(snapshotWorklenz && /^[0-9a-f]{40}$/i.test(snapshotWorklenz.lastCommit || "") && !Number.isNaN(Date.parse(snapshotWorklenz.pushedAt || "")), "Worklenz snapshot freshness evidence was missing");
    const shortWorklenzCommit = snapshotWorklenz.lastCommit.slice(0, 8);
    const snapshotAnytype = adoptionSnapshot.projects.find((project) => project.name === "anyproto/anytype-ts");
    assert(snapshotAnytype && /^[0-9a-f]{40}$/i.test(snapshotAnytype.lastCommit || "") && !Number.isNaN(Date.parse(snapshotAnytype.pushedAt || "")), "Anytype snapshot freshness evidence was missing");
    const shortAnytypeCommit = snapshotAnytype.lastCommit.slice(0, 8);
    const snapshotFocalboard = adoptionSnapshot.projects.find((project) => project.name === "mattermost-community/focalboard");
    assert(snapshotFocalboard && /^[0-9a-f]{40}$/i.test(snapshotFocalboard.lastCommit || "") && !Number.isNaN(Date.parse(snapshotFocalboard.pushedAt || "")), "Focalboard snapshot freshness evidence was missing");
    const shortFocalboardCommit = snapshotFocalboard.lastCommit.slice(0, 8);
    const remainingFreshnessSnapshots = remainingFreshnessTargets.map((target) => {
      const snapshot = adoptionSnapshot.projects.find((project) => project.name === target.name);
      assert(snapshot && /^[0-9a-f]{40}$/i.test(snapshot.lastCommit || "") && !Number.isNaN(Date.parse(snapshot.pushedAt || "")), target.name + " snapshot freshness evidence was missing");
      return { ...target, snapshot, shortCommit: snapshot.lastCommit.slice(0, 8) };
    });
    assert(epicenterCandidate.lastCommit === snapshotEpicenter.lastCommit, "Epicenter candidate commit was stale");
    assert(epicenterCandidate.pushedAt === snapshotEpicenter.pushedAt, "Epicenter candidate pushedAt was stale");
    assert(candidate.lastCommit === snapshotOpenLoaf.lastCommit, "OpenLoaf candidate commit was stale");
    assert(candidate.pushedAt === snapshotOpenLoaf.pushedAt, "OpenLoaf candidate pushedAt was stale");
    assert(planeCandidate.lastCommit === snapshotPlane.lastCommit, "Plane candidate commit was stale");
    assert(planeCandidate.pushedAt === snapshotPlane.pushedAt, "Plane candidate pushedAt was stale");
    assert(appFlowyCandidate.lastCommit === snapshotAppFlowy.lastCommit, "AppFlowy candidate commit was stale");
    assert(appFlowyCandidate.pushedAt === snapshotAppFlowy.pushedAt, "AppFlowy candidate pushedAt was stale");
    assert(affineCandidate.lastCommit === snapshotAffine.lastCommit, "AFFiNE candidate commit was stale");
    assert(affineCandidate.pushedAt === snapshotAffine.pushedAt, "AFFiNE candidate pushedAt was stale");
    assert(outlineCandidate.lastCommit === snapshotOutline.lastCommit, "Outline candidate commit was stale");
    assert(outlineCandidate.pushedAt === snapshotOutline.pushedAt, "Outline candidate pushedAt was stale");
    assert(bookStackCandidate.lastCommit === snapshotBookStack.lastCommit, "BookStack candidate commit was stale");
    assert(bookStackCandidate.pushedAt === snapshotBookStack.pushedAt, "BookStack candidate pushedAt was stale");
    assert(wikiJsCandidate.lastCommit === snapshotWikiJs.lastCommit, "Wiki.js candidate commit was stale");
    assert(wikiJsCandidate.pushedAt === snapshotWikiJs.pushedAt, "Wiki.js candidate pushedAt was stale");
    assert(benchmarkCandidate.lastCommit === snapshotColanode.lastCommit, "Colanode candidate commit was stale");
    assert(benchmarkCandidate.pushedAt === snapshotColanode.pushedAt, "Colanode candidate pushedAt was stale");
    assert(riskCandidate.lastCommit === snapshotOpenProject.lastCommit, "OpenProject candidate commit was stale");
    assert(riskCandidate.pushedAt === snapshotOpenProject.pushedAt, "OpenProject candidate pushedAt was stale");
    assert(parabolCandidate.lastCommit === snapshotParabol.lastCommit, "Parabol candidate commit was stale");
    assert(parabolCandidate.pushedAt === snapshotParabol.pushedAt, "Parabol candidate pushedAt was stale");
    const veritasCandidate = dashboard.projects.find((project) => project.name === "Veritas-7/autoresearch-skill-system");
    assert(veritasCandidate && veritasCandidate.sourceKind === "adoption-candidate", "Veritas AutoResearch candidate was not loaded");
    assert(veritasCandidate.lastCommit === snapshotVeritas.lastCommit, "Veritas AutoResearch candidate commit was stale");
    assert(veritasCandidate.pushedAt === snapshotVeritas.pushedAt, "Veritas AutoResearch candidate pushedAt was stale");
    const leantimeCandidate = dashboard.projects.find((project) => project.name === "Leantime/leantime");
    assert(leantimeCandidate && leantimeCandidate.sourceKind === "adoption-candidate", "Leantime candidate was not loaded");
    assert(leantimeCandidate.lastCommit === snapshotLeantime.lastCommit, "Leantime candidate commit was stale");
    assert(leantimeCandidate.pushedAt === snapshotLeantime.pushedAt, "Leantime candidate pushedAt was stale");
    assert(worklenzCandidate.lastCommit === snapshotWorklenz.lastCommit, "Worklenz candidate commit was stale");
    assert(worklenzCandidate.pushedAt === snapshotWorklenz.pushedAt, "Worklenz candidate pushedAt was stale");
    assert(anytypeCandidate.lastCommit === snapshotAnytype.lastCommit, "Anytype candidate commit was stale");
    assert(anytypeCandidate.pushedAt === snapshotAnytype.pushedAt, "Anytype candidate pushedAt was stale");
    assert(focalboardCandidate.lastCommit === snapshotFocalboard.lastCommit, "Focalboard candidate commit was stale");
    assert(focalboardCandidate.pushedAt === snapshotFocalboard.pushedAt, "Focalboard candidate pushedAt was stale");
    remainingFreshnessSnapshots.forEach((target) => {
      assert(target.candidate.lastCommit === target.snapshot.lastCommit, target.name + " candidate commit was stale");
      assert(target.candidate.pushedAt === target.snapshot.pushedAt, target.name + " candidate pushedAt was stale");
    });
    leantimeCandidate.lastCommit = null;
    leantimeCandidate.pushedAt = "2026-01-01T00:00:00Z";
    leantimeCandidate.stars = 1;
    persist();
    const refreshed = mergeImportedProjects(adoptionSnapshot);
    assert(refreshed, "stale adoption candidate metadata refresh did not report changes");
    assert(leantimeCandidate.lastCommit === snapshotLeantime.lastCommit, "stale Leantime commit was not refreshed from snapshot");
    assert(leantimeCandidate.pushedAt === snapshotLeantime.pushedAt, "stale Leantime pushedAt was not refreshed from snapshot");
    assert(leantimeCandidate.stars === snapshotLeantime.stars, "stale Leantime stars were not refreshed from snapshot");
    const persistedLeantime = savedPayload().projects.find((project) => project.name === "Leantime/leantime");
    assert(persistedLeantime && persistedLeantime.lastCommit === snapshotLeantime.lastCommit, "refreshed Leantime metadata was not persisted");
    candidateMetadataRefreshOk = true;
    const candidateCount = dashboard.projects.filter((project) => project.sourceKind === "adoption-candidate").length;
    const ownedCount = dashboard.projects.length - candidateCount;
    click('[data-action="portfolio-filter"][data-filter="candidates"]');
    await waitFor(() => state.portfolioFilter === "candidates" && document.querySelectorAll('#view-pm-portfolio .portfolio-card[data-source-kind="adoption-candidate"]').length === candidateCount, "candidate portfolio filter did not render adoption candidates");
    assert(qs('[data-action="portfolio-filter"][data-filter="candidates"]').getAttribute("aria-pressed") === "true", "candidate portfolio filter was not active");
    const rankedCandidates = dashboard.projects
      .filter((project) => project.sourceKind === "adoption-candidate")
      .sort((a, b) => (projectCandidatePriority(b)?.score || 0) - (projectCandidatePriority(a)?.score || 0) || String(a.name || "").localeCompare(String(b.name || "")));
    const firstCandidateCard = qs('#view-pm-portfolio .portfolio-card[data-source-kind="adoption-candidate"]');
    assert(firstCandidateCard.dataset.projectId === rankedCandidates[0].id, "candidate portfolio filter did not rank highest priority first");
    assert(qs("[data-candidate-priority]", firstCandidateCard).textContent.includes(String(projectCandidatePriority(rankedCandidates[0]).score)), "top candidate priority score did not render");
    const architectureCount = dashboard.projects.filter((project) => projectCandidateAction(project)?.key === "architecture").length;
    const riskCount = dashboard.projects.filter((project) => projectCandidateAction(project)?.key === "risk").length;
    const benchmarkFocusQueue = sortBenchmarkFocusProjects(dashboard.projects.filter((project) => project.sourceKind === "adoption-candidate" && projectBenchmarkFocus(project)));
    const benchmarkFocusCount = benchmarkFocusQueue.length;
    assert(qs("[data-candidate-action-filter-panel]"), "candidate action filter panel did not render");
    click('[data-action="portfolio-action-filter"][data-action-filter="architecture"]');
    await waitFor(() => state.portfolioFilter === "candidates" && state.portfolioActionFilter === "architecture" && document.querySelectorAll('#view-pm-portfolio .portfolio-card[data-source-kind="adoption-candidate"]').length === architectureCount, "architecture action filter did not narrow candidate cards");
    assert(qs('[data-action="portfolio-action-filter"][data-action-filter="architecture"]').getAttribute("aria-pressed") === "true", "architecture action filter was not active");
    assert(!!document.querySelector('#view-pm-portfolio .portfolio-card[data-project-id="' + benchmarkCandidate.id + '"]'), "architecture action filter did not keep Colanode visible");
    const actionSummary = qs("[data-candidate-action-summary]");
    assert(actionSummary.dataset.actionFilterSummary === "architecture", "architecture action summary did not track active filter");
    assert(actionSummary.innerText.includes("아키텍처 벤치"), "architecture action summary label did not render");
    assert(actionSummary.innerText.includes(architectureCount + "개"), "architecture action summary count did not render");
    assert(actionSummary.innerText.includes("colanode/colanode"), "architecture action summary top candidate did not render");
    assert(actionSummary.innerText.includes("로컬 퍼스트 구조"), "architecture action summary reason did not render");
    click('[data-action="portfolio-action-filter"][data-action-filter="risk"]');
    await waitFor(() => state.portfolioActionFilter === "risk" && document.querySelectorAll('#view-pm-portfolio .portfolio-card[data-source-kind="adoption-candidate"]').length === riskCount, "risk action filter did not narrow candidate cards");
    assert(!!document.querySelector('#view-pm-portfolio .portfolio-card[data-project-id="' + riskCandidate.id + '"]'), "risk action filter did not keep OpenProject visible");
    assert(qs("[data-candidate-action-summary]").innerText.includes("리스크 리뷰"), "risk action summary label did not render");
    click('[data-action="portfolio-action-filter"][data-action-filter="all"]');
    await waitFor(() => state.portfolioActionFilter === "all" && document.querySelectorAll('#view-pm-portfolio .portfolio-card[data-source-kind="adoption-candidate"]').length === candidateCount, "candidate action filter did not reset");
    assert(qs("[data-candidate-benchmark-filter-panel]"), "candidate benchmark filter panel did not render");
    click('[data-action="portfolio-benchmark-filter"][data-benchmark-filter="focused"]');
    await waitFor(() => state.portfolioFilter === "candidates" && state.portfolioBenchmarkFilter === "focused" && document.querySelectorAll('#view-pm-portfolio .portfolio-card[data-source-kind="adoption-candidate"]').length === benchmarkFocusCount, "benchmark focus filter did not narrow candidate cards");
    assert(qs('[data-action="portfolio-benchmark-filter"][data-benchmark-filter="focused"]').getAttribute("aria-pressed") === "true", "benchmark focus filter was not active");
    const benchmarkSummary = qs("[data-candidate-benchmark-summary]");
    assert(benchmarkSummary.dataset.benchmarkFilterSummary === "focused", "benchmark summary did not track active filter");
    assert(benchmarkSummary.innerText.includes("벤치 포커스"), "benchmark summary label did not render");
    assert(benchmarkSummary.innerText.includes(benchmarkFocusCount + "개"), "benchmark summary count did not render");
    assert(benchmarkSummary.innerText.includes(benchmarkFocusQueue[0].name), "benchmark summary top candidate did not render");
    assert(benchmarkSummary.innerText.includes(projectBenchmarkFocus(benchmarkFocusQueue[0]).surface), "benchmark summary surface did not render");
    assert(benchmarkSummary.innerText.includes(projectBenchmarkFocus(benchmarkFocusQueue[0]).flow), "benchmark summary flow did not render");
    const firstBenchmarkCard = qs('#view-pm-portfolio .portfolio-card[data-source-kind="adoption-candidate"]');
    assert(firstBenchmarkCard.dataset.projectId === benchmarkFocusQueue[0].id, "benchmark focus queue did not rank top benchmark first");
    assert(qs("[data-candidate-benchmark]", firstBenchmarkCard).dataset.candidateBenchmark === projectBenchmarkFocus(benchmarkFocusQueue[0]).surface, "benchmark focus queue top chip did not render");
    assert(!!document.querySelector("[data-candidate-benchmark-rubric]"), "benchmark rubric did not render");
    const benchmarkRubric = qs("[data-candidate-benchmark-rubric]");
    assert(benchmarkRubric.innerText.includes("happybhati/workstream"), "Workstream rubric did not render");
    assert(benchmarkRubric.innerText.includes("Taskosaur/Taskosaur"), "Taskosaur rubric did not render");
    ["입력 소스", "AI 보조", "PM 표면", "운영 방식"].forEach((axis) => {
      assert(!!document.querySelector('[data-benchmark-rubric-axis="' + axis + '"]'), "benchmark rubric axis did not render: " + axis);
    });
    [
      "GitHub/GitLab PR",
      "Google Calendar",
      "AI code review",
      "natural-language task commands",
      "browser task execution",
      "Kanban boards",
      "self-hosted PM",
    ].forEach((term) => {
      assert(benchmarkRubric.innerText.includes(term), "benchmark rubric value did not render: " + term);
    });
    const taskosaurBenchmark = benchmarkFocusQueue.find((project) => project.name === "Taskosaur/Taskosaur");
    const workstreamBenchmark = benchmarkFocusQueue.find((project) => project.name === "happybhati/workstream");
    const taskosaurScore = projectBenchmarkRubricScore(taskosaurBenchmark);
    const workstreamScore = projectBenchmarkRubricScore(workstreamBenchmark);
    const recommendation = qs("[data-benchmark-rubric-recommendation]", benchmarkRubric);
    assert(taskosaurScore && taskosaurScore.score === 86, "Taskosaur benchmark rubric score was wrong");
    assert(workstreamScore && workstreamScore.score === 85, "Workstream benchmark rubric score was wrong");
    assert(recommendation.dataset.benchmarkRubricRecommendation === "Taskosaur/Taskosaur", "benchmark rubric recommendation did not pick Taskosaur");
    assert(recommendation.dataset.rubricScore === String(taskosaurScore.score), "benchmark rubric recommendation score did not render");
    assert(benchmarkRubric.innerText.includes("강한 추천 86"), "benchmark rubric score label did not render");
    const rubricCells = Array.from(benchmarkRubric.querySelectorAll("[data-rubric-project][data-rubric-axis]"));
    const taskosaurAiRubric = rubricCells.find((cell) => cell.dataset.rubricProject === "Taskosaur/Taskosaur" && cell.dataset.rubricAxis === "AI 보조");
    assert(taskosaurAiRubric, "Taskosaur benchmark rubric AI cell did not render: " + JSON.stringify(rubricCells.map((cell) => ({ project: cell.dataset.rubricProject, axis: cell.dataset.rubricAxis }))));
    assert(taskosaurAiRubric.dataset.rubricWeight === "0.3", "benchmark rubric AI weight did not render");
    assert(taskosaurAiRubric.dataset.rubricScore === "92", "benchmark rubric AI score did not render");
    const benchmarkExport = qs("[data-candidate-benchmark-export]", benchmarkRubric);
    const exportDownload = qs("[data-benchmark-export-download]", benchmarkExport);
    const exportText = qs("[data-benchmark-export-text]", benchmarkExport).innerText;
    assert(benchmarkExport.dataset.benchmarkExportWinner === "Taskosaur/Taskosaur", "benchmark recommendation export winner did not render");
    assert(benchmarkExport.dataset.benchmarkExportGap === "1", "benchmark recommendation export gap did not render");
    assert(exportDownload.getAttribute("download") === "joopark-benchmark-recommendation.md", "benchmark recommendation export filename did not render");
    assert(exportDownload.getAttribute("href").startsWith("data:text/markdown;charset=utf-8,"), "benchmark recommendation export markdown link did not render");
    assert(exportText.includes("Recommendation: adopt Taskosaur/Taskosaur first") && exportText.includes("happybhati/workstream as the secondary benchmark"), "benchmark recommendation export copy did not render");
    assert(exportText.includes("Score gap: 1 point") && exportText.includes("Primary reason: AI 보조 scored 92 at 30% weight"), "benchmark recommendation export rationale did not render");
    const workspaceRubric = qs("[data-workspace-benchmark-rubric]");
    assert(workspaceRubric.innerText.includes("Workspace 비교표"), "workspace benchmark rubric did not render heading");
    assert(workspaceRubric.innerText.includes("AppFlowy-IO/AppFlowy"), "AppFlowy workspace rubric did not render");
    assert(workspaceRubric.innerText.includes("toeverything/AFFiNE"), "AFFiNE workspace rubric did not render");
    ["PM/Task 흐름", "Notes/Wiki IA", "Collaboration/Data control", "Implementation transfer"].forEach((axis) => {
      assert(!!document.querySelector('[data-workspace-rubric-axis="' + axis + '"]'), "workspace rubric axis did not render: " + axis);
    });
    [
      "project + task surfaces",
      "Notion/Miro knowledge-base + whiteboard",
      "CRDT workspace",
      "Flutter/Dart desktop stack",
    ].forEach((term) => {
      assert(workspaceRubric.innerText.includes(term), "workspace rubric value did not render: " + term);
    });
    const appFlowyWorkspaceScore = projectWorkspaceRubricScore(appFlowyCandidate);
    const affineWorkspaceScore = projectWorkspaceRubricScore(affineCandidate);
    assert(appFlowyWorkspaceScore && appFlowyWorkspaceScore.score === 83, "AppFlowy workspace rubric score was wrong");
    assert(affineWorkspaceScore && affineWorkspaceScore.score === 86, "AFFiNE workspace rubric score was wrong");
    const workspaceRecommendation = qs("[data-workspace-rubric-recommendation]", workspaceRubric);
    assert(workspaceRecommendation.dataset.workspaceRubricRecommendation === "toeverything/AFFiNE", "workspace rubric recommendation did not pick AFFiNE");
    assert(workspaceRecommendation.dataset.workspaceRubricScore === String(affineWorkspaceScore.score), "workspace rubric recommendation score did not render");
    const workspaceCells = Array.from(workspaceRubric.querySelectorAll("[data-workspace-rubric-project][data-workspace-rubric-axis]"));
    const affineNotesCell = workspaceCells.find((cell) => cell.dataset.workspaceRubricProject === "toeverything/AFFiNE" && cell.dataset.workspaceRubricAxis === "Notes/Wiki IA");
    assert(affineNotesCell, "AFFiNE workspace rubric notes cell did not render");
    assert(affineNotesCell.dataset.workspaceRubricWeight === "0.3", "AFFiNE workspace rubric notes weight did not render");
    assert(affineNotesCell.dataset.workspaceRubricScore === "90", "AFFiNE workspace rubric notes score did not render");
    const appFlowyTransferCell = workspaceCells.find((cell) => cell.dataset.workspaceRubricProject === "AppFlowy-IO/AppFlowy" && cell.dataset.workspaceRubricAxis === "Implementation transfer");
    assert(appFlowyTransferCell, "AppFlowy workspace rubric transfer cell did not render");
    assert(appFlowyTransferCell.dataset.workspaceRubricWeight === "0.15", "AppFlowy workspace rubric transfer weight did not render");
    assert(appFlowyTransferCell.dataset.workspaceRubricScore === "76", "AppFlowy workspace rubric transfer score did not render");
    const workspaceExport = qs("[data-workspace-benchmark-export]", workspaceRubric);
    const workspaceExportDownload = qs("[data-workspace-benchmark-export-download]", workspaceExport);
    const workspaceExportText = qs("[data-workspace-benchmark-export-text]", workspaceExport).innerText;
    assert(workspaceExport.dataset.workspaceBenchmarkExportWinner === "toeverything/AFFiNE", "workspace recommendation export winner did not render");
    assert(workspaceExport.dataset.workspaceBenchmarkExportGap === "3", "workspace recommendation export gap did not render");
    assert(workspaceExportDownload.getAttribute("download") === "joopark-workspace-benchmark-recommendation.md", "workspace recommendation export filename did not render");
    assert(workspaceExportDownload.getAttribute("href").startsWith("data:text/markdown;charset=utf-8,"), "workspace recommendation export markdown link did not render");
    assert(workspaceExportText.includes("Recommendation: use toeverything/AFFiNE as the primary Workspace benchmark") && workspaceExportText.includes("AppFlowy-IO/AppFlowy as the PM/task contrast"), "workspace recommendation export copy did not render");
    assert(workspaceExportText.includes("Score gap: 3 points") && workspaceExportText.includes("Primary reason: Notes/Wiki IA scored 90 at 30% weight"), "workspace recommendation export rationale did not render");
    const workspaceReviewHandoff = qs("[data-workspace-review-handoff]", workspaceRubric);
    const workspaceReviewHandoffDownload = qs("[data-workspace-review-handoff-download]", workspaceReviewHandoff);
    const workspaceReviewHandoffCopy = qs("[data-workspace-review-handoff-copy]", workspaceReviewHandoff);
    const workspaceReviewHandoffText = qs("[data-workspace-review-handoff-text]", workspaceReviewHandoff).innerText;
    assert(workspaceReviewHandoff.dataset.workspaceReviewHandoffPrimaryKey === "workspace-review:repo-toeverything-affine:86", "workspace review handoff primary key did not render");
    assert(workspaceReviewHandoff.dataset.workspaceReviewHandoffCount === "2", "workspace review handoff count did not render");
    assert(workspaceReviewHandoff.dataset.reviewPromptContract === "joopark-review-handoff/v2" && workspaceReviewHandoff.dataset.reviewOutputFormat === "json+markdown", "workspace review handoff prompt contract did not render");
    assert(workspaceReviewHandoffDownload.getAttribute("download") === "joopark-workspace-review-handoff.md", "workspace review handoff filename did not render");
    assert(workspaceReviewHandoffDownload.getAttribute("href").startsWith("data:text/markdown;charset=utf-8,"), "workspace review handoff markdown link did not render");
    assert(workspaceReviewHandoffText.includes("Primary decision key: workspace-review:repo-toeverything-affine:86") && workspaceReviewHandoffText.includes("toeverything/AFFiNE - Workspace 도입 검토") && workspaceReviewHandoffText.includes("AppFlowy-IO/AppFlowy - 비교 유지"), "workspace review handoff markdown copy did not render");
    assert(workspaceReviewHandoffText.includes("## Prompt Contract") && workspaceReviewHandoffText.includes("## System Prompt") && workspaceReviewHandoffText.includes("## User Prompt Template") && workspaceReviewHandoffText.includes("## Output Schema") && workspaceReviewHandoffText.includes("## Failure / Exception Handling"), "workspace review handoff prompt sections did not render");
    assert(workspaceReviewHandoffText.includes("## Quality Bar") && workspaceReviewHandoffText.includes("## Evidence Snapshot") && workspaceReviewHandoffText.includes("## Execution Plan") && workspaceReviewHandoffText.includes("## Review Checklist"), "workspace review handoff quality package did not render");
    assert(workspaceReviewHandoffText.includes("schemaVersion") && workspaceReviewHandoffText.includes("joopark-review-handoff/v2") && workspaceReviewHandoffText.includes("<candidate_decisions") && workspaceReviewHandoffText.includes("missingEvidence") && workspaceReviewHandoffText.includes("qualityGate") && workspaceReviewHandoffText.includes("sourceSnapshot") && workspaceReviewHandoffText.includes("acceptanceCriteria") && workspaceReviewHandoffText.includes("validationPlan") && workspaceReviewHandoffText.includes("firstAction") && workspaceReviewHandoffText.includes("decisionGate") && workspaceReviewHandoffText.includes("fallbackIfBlocked"), "workspace review handoff structured contract did not render");
    assert(workspaceReviewHandoffCopy.dataset.workspaceReviewHandoffCopyKey === "workspace-review:repo-toeverything-affine:86", "workspace review handoff copy key did not render");
    window.__smokeClipboardText = "";
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: async (text) => { window.__smokeClipboardText = text; } },
    });
    click("[data-workspace-review-handoff-copy]");
    await waitFor(() => window.__smokeClipboardText.includes("Primary decision key: workspace-review:repo-toeverything-affine:86") && window.__smokeClipboardText.includes("## Output Schema") && window.__smokeClipboardText.includes("## Evidence Snapshot") && window.__smokeClipboardText.includes("## Review Checklist"), "workspace review handoff copy text did not reach clipboard");
    await waitFor(() => workspaceReviewHandoff.dataset.reviewHandoffCopied === "true", "workspace review handoff copy state did not update");
    assert(qs("[data-workspace-review-handoff-copy-status]", workspaceReviewHandoff).textContent.includes("복사됨"), "workspace review handoff copy status did not render");
    const workspaceBundleDownload = qs("[data-workspace-review-bundle-download]", workspaceReviewHandoff);
    const workspaceBundleCopy = qs("[data-workspace-review-bundle-copy]", workspaceReviewHandoff);
    const workspaceBundleText = qs("[data-workspace-review-package-bundle-text]", workspaceReviewHandoff).textContent;
    const workspaceBundleManifest = qs("[data-workspace-review-package-manifest]", workspaceReviewHandoff);
    assert(workspaceBundleDownload.getAttribute("download") === "joopark-workspace-review-package.md", "workspace review package bundle filename did not render");
    assert(workspaceBundleDownload.getAttribute("href").startsWith("data:text/markdown;charset=utf-8,"), "workspace review package bundle markdown link did not render");
    assert(workspaceBundleManifest.dataset.reviewPackageManifestStatus === "pass", "workspace review package bundle manifest did not pass");
    assert(workspaceBundleManifest.dataset.reviewPackagePayloadChecksum.startsWith("fnv1a32-"), "workspace review package bundle checksum did not render");
    assert(workspaceBundleManifest.dataset.reviewPackageSourceFreshness === "pass" && workspaceBundleManifest.dataset.reviewPackageSourceCount === "2", "workspace review package bundle source freshness did not render");
    assert(workspaceBundleManifest.dataset.reviewPackagePasteTargetStatus === "pass" && workspaceBundleManifest.dataset.reviewPackagePasteTargetReady === "3" && workspaceBundleManifest.dataset.reviewPackagePasteTargetCount === "3", "workspace review package paste targets did not pass");
    assert(workspaceBundleManifest.dataset.reviewPackageFinalQualityStatus === "pass" && workspaceBundleManifest.dataset.reviewPackageFinalQualityScore === "6/6", "workspace review package final quality gate did not pass");
    assert(workspaceBundleManifest.dataset.reviewPackageArtifactQualityStatus === "pass" && workspaceBundleManifest.dataset.reviewPackageArtifactQualityScore === "100/100" && workspaceBundleManifest.dataset.reviewPackageArtifactQualityItemCount === "5", "workspace review package artifact quality rubric did not pass");
    assert(workspaceBundleManifest.querySelectorAll("[data-review-package-artifact-quality-item]").length === 5 && workspaceBundleManifest.innerText.includes("Required form fit") && workspaceBundleManifest.innerText.includes("Paste-ready completeness") && workspaceBundleManifest.innerText.includes("Submission flow readiness") && workspaceBundleManifest.innerText.includes("Safety and reuse readiness"), "workspace review package artifact quality rubric did not render");
    assert(workspaceBundleManifest.dataset.reviewPackageDecisionBriefStatus === "pass" && workspaceBundleManifest.dataset.reviewPackageDecisionBriefReady === "6" && workspaceBundleManifest.dataset.reviewPackageDecisionBriefCount === "6", "workspace review package decision brief did not pass");
    assert(workspaceBundleManifest.querySelectorAll("[data-review-package-decision-brief-item]").length === 6 && workspaceBundleManifest.innerText.includes("Recommendation") && workspaceBundleManifest.innerText.includes("Why this candidate") && workspaceBundleManifest.innerText.includes("Comparison context") && workspaceBundleManifest.innerText.includes("Execution target") && workspaceBundleManifest.innerText.includes("Evidence anchor") && workspaceBundleManifest.innerText.includes("Next action"), "workspace review package decision brief did not render");
    assert(workspaceBundleManifest.dataset.reviewPackageOperatorQuickStartStatus === "pass" && workspaceBundleManifest.dataset.reviewPackageOperatorQuickStartReady === "5" && workspaceBundleManifest.dataset.reviewPackageOperatorQuickStartCount === "5", "workspace review package operator quick start did not pass");
    assert(workspaceBundleManifest.querySelectorAll("[data-review-package-operator-quick-start-item]").length === 5 && workspaceBundleManifest.innerText.includes("Confirm quality gate") && workspaceBundleManifest.innerText.includes("Fill external tracker fields") && workspaceBundleManifest.innerText.includes("Paste tracker issue body") && workspaceBundleManifest.innerText.includes("Share final submission update") && workspaceBundleManifest.innerText.includes("Keep bundle proof"), "workspace review package operator quick start did not render");
	    assert(workspaceBundleManifest.querySelectorAll("[data-review-package-paste-target-item]").length === 3 && workspaceBundleManifest.innerText.includes("Tracker issue") && workspaceBundleManifest.innerText.includes("GitHub comment") && workspaceBundleManifest.innerText.includes("Pinned note"), "workspace review package paste target list did not render");
	    assert(workspaceBundleManifest.dataset.reviewPackageQualityRepairStatus === "none" && workspaceBundleManifest.dataset.reviewPackageQualityRepairCount === "0", "workspace review package repair checklist did not report clean state");
	    assert(qs("[data-review-package-quality-repair-empty]", workspaceBundleManifest).textContent.includes("No repairs required"), "workspace review package repair empty state did not render");
	    const workspacePastePreview = qs("[data-workspace-review-package-paste-preview]", workspaceReviewHandoff);
	    assert(workspacePastePreview.dataset.reviewPackagePastePreviewReady === "3" && workspacePastePreview.dataset.reviewPackagePastePreviewCount === "3", "workspace review package paste preview did not report ready state");
	    assert(workspacePastePreview.querySelectorAll("[data-review-package-paste-preview-item]").length === 3 && workspacePastePreview.innerText.includes("Tracker issue body") && workspacePastePreview.innerText.includes("GitHub comment body") && workspacePastePreview.innerText.includes("Pinned note body"), "workspace review package paste preview items did not render");
	    assert(qs("[data-review-package-paste-preview-id='tracker_issue'] [data-review-package-paste-preview-body]", workspacePastePreview).innerText.includes("Persist key: workspace-review:repo-toeverything-affine:86"), "workspace tracker paste preview body was incomplete");
	    assert(qs("[data-review-package-paste-preview-id='github_comment'] [data-review-package-paste-preview-body]", workspacePastePreview).innerText.includes("## Comment Decision Summary") && qs("[data-review-package-paste-preview-id='github_comment'] [data-review-package-paste-preview-body]", workspacePastePreview).innerText.includes("Evidence anchor:") && qs("[data-review-package-paste-preview-id='github_comment'] [data-review-package-paste-preview-body]", workspacePastePreview).innerText.includes("First action:") && qs("[data-review-package-paste-preview-id='github_comment'] [data-review-package-paste-preview-body]", workspacePastePreview).innerText.includes("Stop condition:") && qs("[data-review-package-paste-preview-id='github_comment'] [data-review-package-paste-preview-body]", workspacePastePreview).innerText.includes("## Issue Draft"), "workspace GitHub comment paste preview body was incomplete");
	    assert(qs("[data-review-package-paste-preview-id='pinned_note'] [data-review-package-paste-preview-body]", workspacePastePreview).innerText.includes("## Pinned Note Summary") && qs("[data-review-package-paste-preview-id='pinned_note'] [data-review-package-paste-preview-body]", workspacePastePreview).innerText.includes("Evidence anchor:") && qs("[data-review-package-paste-preview-id='pinned_note'] [data-review-package-paste-preview-body]", workspacePastePreview).innerText.includes("First action:") && qs("[data-review-package-paste-preview-id='pinned_note'] [data-review-package-paste-preview-body]", workspacePastePreview).innerText.includes("Stop condition:") && qs("[data-review-package-paste-preview-id='pinned_note'] [data-review-package-paste-preview-body]", workspacePastePreview).innerText.includes("## Issue Draft"), "workspace pinned note paste preview body was incomplete");
	    const workspaceTrackerFields = qs("[data-review-package-tracker-fields]", workspacePastePreview);
	    assert(workspaceTrackerFields.dataset.reviewPackageTrackerFieldStatus === "pass" && workspaceTrackerFields.dataset.reviewPackageTrackerFieldReady === "8" && workspaceTrackerFields.dataset.reviewPackageTrackerFieldCount === "8", "workspace tracker field packet did not report ready state");
	    const workspaceTrackerFieldPacket = qs("[data-review-package-tracker-field-packet-body]", workspaceTrackerFields).textContent;
	    assert(workspaceTrackerFields.querySelectorAll("[data-review-package-tracker-field-row]").length === 8 && workspaceTrackerFieldPacket.includes("Title: [Workspace] toeverything/AFFiNE Workspace 도입 검토") && workspaceTrackerFieldPacket.includes("Priority: high") && workspaceTrackerFieldPacket.includes("Labels: workspace, benchmark, handoff, adoption") && workspaceTrackerFieldPacket.includes("Persist key: workspace-review:repo-toeverything-affine:86"), "workspace tracker field packet did not render copy-ready fields");
	    assert(workspacePastePreview.querySelectorAll("[data-review-package-paste-preview-copy]").length === 3, "workspace review package paste preview copy buttons did not render");
	    window.__smokeClipboardText = "";
	    click("[data-review-package-tracker-field-copy]", workspaceTrackerFields);
	    await waitFor(() => window.__smokeClipboardText.includes("Tracker Field Packet") && window.__smokeClipboardText.includes("Title: [Workspace] toeverything/AFFiNE Workspace 도입 검토") && window.__smokeClipboardText.includes("Labels: workspace, benchmark, handoff, adoption") && window.__smokeClipboardText.includes("Persist key: workspace-review:repo-toeverything-affine:86"), "workspace tracker field packet copy did not reach clipboard");
	    await waitFor(() => workspaceTrackerFields.dataset.reviewPackageTrackerFieldCopied === "true", "workspace tracker field packet copy state did not update");
	    reviewPackageTrackerFieldCopyOk = true;
	    await waitFor(() => {
	      const currentPreview = document.querySelector("[data-workspace-review-package-paste-preview]");
	      const currentForm = currentPreview && currentPreview.querySelector("[data-review-package-tracker-form]");
	      return currentForm &&
	        currentForm.dataset.reviewPackageTrackerFormStatus === "pass" &&
	        currentForm.dataset.reviewPackageTrackerFormRequiredReady === "8" &&
	        currentForm.dataset.reviewPackageTrackerFormRequiredCount === "8" &&
        currentForm.dataset.reviewPackageTrackerFormComparisonCount === "3";
	    }, "workspace external tracker form packet did not report ready state");
	    const workspaceTrackerForm = qs("[data-review-package-tracker-form]", qs("[data-workspace-review-package-paste-preview]"));
	    const workspaceTrackerFormText = qs("[data-review-package-tracker-form-body]", workspaceTrackerForm).textContent;
	    const workspaceTrackerFormPayloads = qs("[data-review-package-tracker-form-payloads]", workspaceTrackerForm);
	    assert(workspaceTrackerForm.querySelectorAll("[data-review-package-tracker-form-row]").length === 11 && workspaceTrackerFormText.includes("External Tracker Form Packet") && workspaceTrackerFormText.includes("GitHub Issue Forms") && workspaceTrackerFormText.includes("Linear issue templates") && workspaceTrackerFormText.includes("Jira work items") && workspaceTrackerFormText.includes("Acceptance criteria") && workspaceTrackerFormText.includes("Validation plan") && workspaceTrackerFormText.includes("Persist key: workspace-review:repo-toeverything-affine:86"), "workspace external tracker form packet did not render copy-ready fields");
	    assert(workspaceTrackerFormPayloads.dataset.reviewPackageTrackerFormPayloadCount === "11" && qs("[data-review-package-tracker-form-payload-id='description']", workspaceTrackerFormPayloads).dataset.reviewPackageTrackerFormPayloadChecksum.startsWith("fnv1a32-") && qs("[data-review-package-tracker-form-payload-id='acceptance_criteria']", workspaceTrackerFormPayloads).dataset.reviewPackageTrackerFormPayloadReady === "true" && qs("[data-review-package-tracker-form-payload-id='validation_plan']", workspaceTrackerFormPayloads).dataset.reviewPackageTrackerFormPayloadReady === "true", "workspace external tracker field payloads did not render ready checksums");
	    window.__smokeClipboardText = "";
	    click("[data-review-package-tracker-form-copy]", workspaceTrackerForm);
	    await waitFor(() => window.__smokeClipboardText.includes("External Tracker Form Packet") && window.__smokeClipboardText.includes("Status: pass") && window.__smokeClipboardText.includes("Use with: GitHub Issue Forms, Linear issue templates, Jira work items") && window.__smokeClipboardText.includes("Field payloads:") && window.__smokeClipboardText.includes("## Description / body") && window.__smokeClipboardText.includes("## Acceptance criteria") && window.__smokeClipboardText.includes("## Validation plan") && window.__smokeClipboardText.includes("Source URL: https://github.com/toeverything/AFFiNE") && window.__smokeClipboardText.includes("Checksum: fnv1a32-") && window.__smokeClipboardText.includes("If the external form has separate required fields") && window.__smokeClipboardText.includes("Record the external issue URL/ID"), "workspace external tracker form packet copy did not reach clipboard");
	    await waitFor(() => workspaceTrackerForm.dataset.reviewPackageTrackerFormCopied === "true", "workspace external tracker form packet copy state did not update");
	    reviewPackageTrackerFormCopyOk = true;
	    const workspaceSubmitSequence = qs("[data-review-package-submit-sequence]", workspacePastePreview);
	    assert(workspaceSubmitSequence.dataset.reviewPackageSubmitSequenceStatus === "pass" && workspaceSubmitSequence.dataset.reviewPackageSubmitSequenceReady === "7" && workspaceSubmitSequence.dataset.reviewPackageSubmitSequenceCount === "7", "workspace submit sequence did not report ready state");
	    const workspaceSubmitSequenceText = qs("[data-review-package-submit-sequence-body]", workspaceSubmitSequence).textContent;
	    assert(workspaceSubmitSequence.querySelectorAll("[data-review-package-submit-sequence-step]").length === 7 && workspaceSubmitSequenceText.includes("Review Package Submit Sequence") && workspaceSubmitSequenceText.includes("Ready: 7/7") && workspaceSubmitSequenceText.includes("Persist key: workspace-review:repo-toeverything-affine:86") && workspaceSubmitSequenceText.includes("Set tracker fields first") && workspaceSubmitSequenceText.includes("Record external issue receipt") && workspaceSubmitSequenceText.includes("Share final submission update") && workspaceSubmitSequenceText.includes("Use 최종 update 복사 after filling the external issue URL/ID") && workspaceSubmitSequenceText.includes("final quality 6/6"), "workspace submit sequence did not render copy-ready order");
	    window.__smokeClipboardText = "";
	    click("[data-review-package-submit-sequence-copy]", workspaceSubmitSequence);
	    await waitFor(() => window.__smokeClipboardText.includes("Review Package Submit Sequence") && window.__smokeClipboardText.includes("Ready: 7/7") && window.__smokeClipboardText.includes("Set tracker fields first") && window.__smokeClipboardText.includes("Record external issue receipt") && window.__smokeClipboardText.includes("Share final submission update") && window.__smokeClipboardText.includes("Use 최종 update 복사 after filling the external issue URL/ID") && window.__smokeClipboardText.includes("Persist key: workspace-review:repo-toeverything-affine:86"), "workspace submit sequence copy did not reach clipboard");
	    await waitFor(() => workspaceSubmitSequence.dataset.reviewPackageSubmitSequenceCopied === "true", "workspace submit sequence copy state did not update");
	    reviewPackageSubmitSequenceCopyOk = true;
	    const workspaceExternalReceipt = qs("[data-review-package-external-receipt-template]", workspacePastePreview);
	    assert(workspaceExternalReceipt.dataset.reviewPackageExternalReceiptTemplateStatus === "pass" && workspaceExternalReceipt.dataset.reviewPackageExternalReceiptTemplateReady === "13" && workspaceExternalReceipt.dataset.reviewPackageExternalReceiptTemplateCount === "13", "workspace external receipt template did not report ready state");
	    const workspaceExternalReceiptText = qs("[data-review-package-external-receipt-template-body]", workspaceExternalReceipt).textContent;
	    assert(workspaceExternalReceipt.querySelectorAll("[data-review-package-external-receipt-row]").length === 13 && workspaceExternalReceiptText.includes("External Issue Receipt Template") && workspaceExternalReceiptText.includes("External issue URL: [paste after creation]") && workspaceExternalReceiptText.includes("Submitted at: [paste timestamp after creation]") && workspaceExternalReceiptText.includes("Persist key: workspace-review:repo-toeverything-affine:86") && workspaceExternalReceiptText.includes("Tracker body checksum: fnv1a32-") && workspaceExternalReceiptText.includes("Required form fields ready: 8/8") && workspaceExternalReceiptText.includes("Submit sequence ready: 7/7") && workspaceExternalReceiptText.includes("External receipt integrity"), "workspace external receipt template did not render copy-ready fields");
	    const workspaceCloseoutSummary = qs("[data-review-package-submission-closeout-summary]", workspaceExternalReceipt);
	    assert(workspaceCloseoutSummary.dataset.reviewPackageSubmissionCloseoutSummaryStatus === "pass" && workspaceCloseoutSummary.dataset.reviewPackageSubmissionCloseoutSummaryReady === "6" && workspaceCloseoutSummary.dataset.reviewPackageSubmissionCloseoutSummaryCount === "6" && workspaceCloseoutSummary.querySelectorAll("[data-review-package-submission-closeout-summary-row]").length === 6, "workspace submission closeout summary did not report ready state");
	    assert(workspaceExternalReceiptText.includes("Submission Closeout Summary") && workspaceExternalReceiptText.includes("Submitted artifact: [paste issue ID]") && workspaceExternalReceiptText.includes("Evidence anchor: Persist key workspace-review:repo-toeverything-affine:86; tracker body checksum fnv1a32-") && workspaceExternalReceiptText.includes("First action: Copy the completed external receipt") && workspaceExternalReceiptText.includes("Validation gate: External URL, external ID, submitted timestamp, required fields 8/8, and submit sequence 7/7 are present.") && workspaceExternalReceiptText.includes("Archive target: Keep this receipt with the bundle manifest") && workspaceExternalReceiptText.includes("Stop condition: Do not share submitted status until URL, ID, timestamp, and completed receipt copy are filled."), "workspace external receipt closeout summary was not copy-ready");
	    window.__smokeClipboardText = "";
	    click("[data-review-package-external-receipt-template-copy]", workspaceExternalReceipt);
	    await waitFor(() => window.__smokeClipboardText.includes("External Issue Receipt Template") && window.__smokeClipboardText.includes("External issue URL: [paste after creation]") && window.__smokeClipboardText.includes("External issue ID: [paste after creation]") && window.__smokeClipboardText.includes("Persist key: workspace-review:repo-toeverything-affine:86") && window.__smokeClipboardText.includes("Tracker body checksum: fnv1a32-") && window.__smokeClipboardText.includes("Required form fields ready: 8/8") && window.__smokeClipboardText.includes("Submit sequence ready: 7/7"), "workspace external receipt template copy did not reach clipboard");
	    assert(window.__smokeClipboardText.includes("Submission Closeout Summary") && window.__smokeClipboardText.includes("Submitted artifact: [paste issue ID]") && window.__smokeClipboardText.includes("First action: Copy the completed external receipt") && window.__smokeClipboardText.includes("Validation gate: External URL, external ID, submitted timestamp, required fields 8/8, and submit sequence 7/7 are present.") && window.__smokeClipboardText.includes("Stop condition: Do not share submitted status until URL, ID, timestamp, and completed receipt copy are filled."), "workspace external receipt closeout summary copy did not reach clipboard");
	    await waitFor(() => workspaceExternalReceipt.dataset.reviewPackageExternalReceiptTemplateCopied === "true", "workspace external receipt template copy state did not update");
	    reviewPackageExternalReceiptTemplateCopyOk = true;
	    const receiptUrlInput = qs("[data-review-package-external-receipt-url]", workspaceExternalReceipt);
	    const receiptIdInput = qs("[data-review-package-external-receipt-id]", workspaceExternalReceipt);
	    const receiptSubmittedAtInput = qs("[data-review-package-external-receipt-submitted-at]", workspaceExternalReceipt);
	    receiptUrlInput.value = "https://linear.app/joopark/issue/WRK-86/affine-workspace-review";
	    receiptIdInput.value = "WRK-86";
	    receiptSubmittedAtInput.value = "2026-06-07T12:10";
	    window.__smokeClipboardText = "";
	    click("[data-review-package-external-receipt-filled-copy]", workspaceExternalReceipt);
	    await waitFor(() => window.__smokeClipboardText.includes("External Issue Receipt Template") && window.__smokeClipboardText.includes("External issue URL: https://linear.app/joopark/issue/WRK-86/affine-workspace-review") && window.__smokeClipboardText.includes("External issue ID: WRK-86") && window.__smokeClipboardText.includes("Submitted at: 2026-06-07T12:10") && window.__smokeClipboardText.includes("Tracker body checksum: fnv1a32-") && window.__smokeClipboardText.includes("Required form fields ready: 8/8") && window.__smokeClipboardText.includes("Submit sequence ready: 7/7") && !window.__smokeClipboardText.includes("[paste after creation]"), "workspace filled external receipt copy did not reach clipboard");
	    assert(window.__smokeClipboardText.includes("Submitted artifact: WRK-86 — https://linear.app/joopark/issue/WRK-86/affine-workspace-review") && !window.__smokeClipboardText.includes("Submitted artifact: [paste issue ID]"), "workspace filled external receipt closeout summary did not replace submitted artifact placeholder");
	    await waitFor(() => workspaceExternalReceipt.dataset.reviewPackageExternalReceiptFilledCopied === "true", "workspace filled external receipt copy state did not update");
	    reviewPackageExternalReceiptFilledCopyOk = true;
	    reviewPackageExternalReceiptIntegrityOk = true;
	    reviewPackageSubmissionCloseoutSummaryVisibleOk = true;
	    const workspaceSubmissionUpdate = qs("[data-review-package-submission-update]", workspaceExternalReceipt);
	    assert(workspaceSubmissionUpdate.dataset.reviewPackageSubmissionUpdateStatus === "pass" && workspaceSubmissionUpdate.dataset.reviewPackageSubmissionUpdateReady === "10" && workspaceSubmissionUpdate.dataset.reviewPackageSubmissionUpdateCount === "10", "workspace submission update did not report ready state");
	    const workspaceSubmissionUpdateText = qs("[data-review-package-submission-update-body]", workspaceSubmissionUpdate).textContent;
	    assert(workspaceSubmissionUpdate.querySelectorAll("[data-review-package-submission-update-row]").length === 10 && workspaceSubmissionUpdateText.includes("Review Submission Update") && workspaceSubmissionUpdateText.includes("Status: ready after external issue URL/ID") && workspaceSubmissionUpdateText.includes("External issue: [paste issue ID]") && workspaceSubmissionUpdateText.includes("final quality 6/6") && workspaceSubmissionUpdateText.includes("External receipt integrity: tracker body checksum fnv1a32-") && workspaceSubmissionUpdateText.includes("required form fields 8/8") && workspaceSubmissionUpdateText.includes("submit sequence 7/7") && workspaceSubmissionUpdateText.includes("Next action: After external issue URL/ID are filled, post the GitHub comment body") && !workspaceSubmissionUpdateText.includes("Status: submitted"), "workspace submission update template did not render pre-submit copy-ready fields");
	    const workspaceUpdateCloseoutSummary = qs("[data-review-package-submission-update-closeout-summary]", workspaceSubmissionUpdate);
	    assert(workspaceUpdateCloseoutSummary.dataset.reviewPackageSubmissionUpdateCloseoutSummaryStatus === "pass" && workspaceUpdateCloseoutSummary.dataset.reviewPackageSubmissionUpdateCloseoutSummaryReady === "6" && workspaceUpdateCloseoutSummary.dataset.reviewPackageSubmissionUpdateCloseoutSummaryCount === "6" && workspaceUpdateCloseoutSummary.querySelectorAll("[data-review-package-submission-update-closeout-summary-row]").length === 6, "workspace submission update closeout summary did not report ready state");
	    assert(workspaceSubmissionUpdateText.includes("Submission Closeout Summary") && workspaceSubmissionUpdateText.includes("First action: Copy the completed external receipt") && workspaceSubmissionUpdateText.includes("Validation gate: External URL, external ID, submitted timestamp, required fields 8/8, and submit sequence 7/7 are present.") && workspaceSubmissionUpdateText.includes("Stop condition: Do not share submitted status until URL, ID, timestamp, and completed receipt copy are filled."), "workspace submission update closeout summary was not copy-ready");
	    window.__smokeClipboardText = "";
	    click("[data-review-package-submission-update-filled-copy]", workspaceExternalReceipt);
	    await waitFor(() => window.__smokeClipboardText.includes("Review Submission Update") && window.__smokeClipboardText.includes("Status: submitted") && window.__smokeClipboardText.includes("External issue: WRK-86 — https://linear.app/joopark/issue/WRK-86/affine-workspace-review") && window.__smokeClipboardText.includes("Submitted at: 2026-06-07T12:10") && window.__smokeClipboardText.includes("Persist key: workspace-review:repo-toeverything-affine:86") && window.__smokeClipboardText.includes("External receipt integrity: tracker body checksum fnv1a32-") && window.__smokeClipboardText.includes("required form fields 8/8") && window.__smokeClipboardText.includes("submit sequence 7/7") && window.__smokeClipboardText.includes("Next action: Post the GitHub comment body") && !window.__smokeClipboardText.includes("ready after external issue URL/ID") && !window.__smokeClipboardText.includes("After external issue URL/ID are filled") && !window.__smokeClipboardText.includes("[paste"), "workspace submission update copy did not reach clipboard");
	    assert(window.__smokeClipboardText.includes("Submitted artifact: WRK-86 — https://linear.app/joopark/issue/WRK-86/affine-workspace-review") && window.__smokeClipboardText.includes("Validation gate: External URL, external ID, submitted timestamp, required fields 8/8, and submit sequence 7/7 are present.") && window.__smokeClipboardText.includes("Stop condition: Do not share submitted status until URL, ID, timestamp, and completed receipt copy are filled."), "workspace submission update closeout summary copy did not reach clipboard");
	    await waitFor(() => workspaceSubmissionUpdate.dataset.reviewPackageSubmissionUpdateFilledCopied === "true", "workspace submission update copy state did not update");
	    reviewPackageSubmissionUpdateCopyOk = true;
	    window.__smokeClipboardText = "";
	    click("[data-review-package-paste-preview-id='tracker_issue'] [data-review-package-paste-preview-copy]", workspacePastePreview);
	    await waitFor(() => window.__smokeClipboardText.includes("Persist key: workspace-review:repo-toeverything-affine:86"), "workspace tracker paste preview body copy did not reach clipboard");
	    await waitFor(() => qs("[data-review-package-paste-preview-id='tracker_issue']", workspacePastePreview).dataset.reviewPackagePastePreviewCopied === "true", "workspace tracker paste preview copy state did not update");
	    click("[data-review-package-paste-preview-id='github_comment'] [data-review-package-paste-preview-copy]", workspacePastePreview);
	    await waitFor(() => window.__smokeClipboardText.includes("## Comment Decision Summary") && window.__smokeClipboardText.includes("Evidence anchor:") && window.__smokeClipboardText.includes("First action:") && window.__smokeClipboardText.includes("Stop condition:") && window.__smokeClipboardText.includes("## Issue Draft") && window.__smokeClipboardText.includes("Primary decision key: workspace-review:repo-toeverything-affine:86"), "workspace GitHub comment paste preview body copy did not reach clipboard");
	    await waitFor(() => qs("[data-review-package-paste-preview-id='github_comment']", workspacePastePreview).dataset.reviewPackagePastePreviewCopied === "true", "workspace GitHub comment paste preview copy state did not update");
	    click("[data-review-package-paste-preview-id='pinned_note'] [data-review-package-paste-preview-copy]", workspacePastePreview);
	    await waitFor(() => window.__smokeClipboardText.includes("## Pinned Note Summary") && window.__smokeClipboardText.includes("Evidence anchor:") && window.__smokeClipboardText.includes("First action:") && window.__smokeClipboardText.includes("Stop condition:") && window.__smokeClipboardText.includes("## Issue Draft") && window.__smokeClipboardText.includes("JooPark Workspace Review Handoff"), "workspace pinned note paste preview body copy did not reach clipboard");
	    await waitFor(() => qs("[data-review-package-paste-preview-id='pinned_note']", workspacePastePreview).dataset.reviewPackagePastePreviewCopied === "true", "workspace pinned note paste preview copy state did not update");
	    reviewPackagePastePreviewCopyOk = true;
	    assert(qs("[data-review-package-manifest-summary]", workspaceBundleManifest).textContent.includes("Markdown Handoff") && qs("[data-review-package-manifest-summary]", workspaceBundleManifest).textContent.includes("10 checks") && qs("[data-review-package-manifest-summary]", workspaceBundleManifest).textContent.includes("paste targets 3/3") && qs("[data-review-package-manifest-summary]", workspaceBundleManifest).textContent.includes("final quality 6/6") && qs("[data-review-package-manifest-summary]", workspaceBundleManifest).textContent.includes("artifact quality 100/100") && qs("[data-review-package-manifest-summary]", workspaceBundleManifest).textContent.includes("decision brief 6/6") && qs("[data-review-package-manifest-summary]", workspaceBundleManifest).textContent.includes("quick start 5/5") && qs("[data-review-package-manifest-summary]", workspaceBundleManifest).textContent.includes("repairs 0"), "workspace review package bundle manifest summary did not render");
	    assert(workspaceBundleText.includes("# JooPark Workspace Review Package Bundle") && workspaceBundleText.includes("## Bundle Manifest") && workspaceBundleText.includes("## Markdown Handoff") && workspaceBundleText.includes("## Issue Draft") && workspaceBundleText.includes("## GitHub Comment Draft") && workspaceBundleText.includes("## Pinned Note Body"), "workspace review package bundle sections did not render");
    assert(workspaceBundleText.includes("Manifest schema: joopark-review-package-manifest/v1") && workspaceBundleText.includes("Validation status: pass") && workspaceBundleText.includes("Payload checksum: fnv1a32-") && workspaceBundleText.includes("Source freshness: pass (2/2)") && workspaceBundleText.includes("Paste target readiness: pass (3/3)") && workspaceBundleText.includes("Ready to submit: pass") && workspaceBundleText.includes("Final quality score: 6/6") && workspaceBundleText.includes("Artifact quality rubric: pass (100/100, threshold 90)") && workspaceBundleText.includes("Decision brief: pass (6/6)") && workspaceBundleText.includes("Operator quick start: pass (5/5)") && workspaceBundleText.includes("Quality repairs: none (0)") && workspaceBundleText.includes("### Decision Brief") && workspaceBundleText.includes("Review Package Decision Brief") && workspaceBundleText.includes("Recommendation") && workspaceBundleText.includes("Evidence anchor") && workspaceBundleText.includes("Next action") && workspaceBundleText.includes("### Operator Quick Start") && workspaceBundleText.includes("Review Package Operator Quick Start") && workspaceBundleText.includes("Fill external tracker fields") && workspaceBundleText.includes("Keep bundle proof") && workspaceBundleText.includes("### Paste-Ready Targets") && workspaceBundleText.includes("### Artifact Quality Rubric") && workspaceBundleText.includes("Required form fit") && workspaceBundleText.includes("Submission flow readiness") && workspaceBundleText.includes("### Paste Body Preview") && workspaceBundleText.includes("### Tracker Field Packet") && workspaceBundleText.includes("### External Tracker Form Packet") && workspaceBundleText.includes("Tracker issue body") && workspaceBundleText.includes("GitHub comment body") && workspaceBundleText.includes("Pinned note body") && workspaceBundleText.includes("Tracker issue") && workspaceBundleText.includes("Pinned note") && workspaceBundleText.includes("### Final Output Quality Gate") && workspaceBundleText.includes("### Quality Repair Checklist") && workspaceBundleText.includes("- [x] No repairs required; package is ready to submit."), "workspace review package bundle manifest did not include validation evidence");
	    assert(workspaceBundleText.includes("### Submit Sequence") && workspaceBundleText.includes("Review Package Submit Sequence"), "workspace review package bundle did not include submit sequence");
	    assert(workspaceBundleText.includes("### External Issue Receipt Template") && workspaceBundleText.includes("External Issue Receipt Template"), "workspace review package bundle did not include external receipt template");
    assert(workspaceBundleText.includes("Source URL: https://github.com/toeverything/AFFiNE") && workspaceBundleText.includes("## Decision Summary") && workspaceBundleText.includes("Recommendation: toeverything/AFFiNE") && workspaceBundleText.includes("Evidence anchor:") && workspaceBundleText.includes("Stop condition:") && workspaceBundleText.includes("## Operational Readiness") && workspaceBundleText.includes("Decision gate:") && workspaceBundleText.includes("Fallback if blocked:") && workspaceBundleText.includes("## Acceptance Criteria") && workspaceBundleText.includes("## Validation Plan"), "workspace review package bundle did not include execution-quality content");
    window.__smokeClipboardText = "";
    click("[data-workspace-review-bundle-copy]", workspaceReviewHandoff);
    await waitFor(() => workspaceReviewHandoff.dataset.reviewBundleCopied === "true" && window.__smokeClipboardText.includes("# JooPark Workspace Review Package Bundle") && window.__smokeClipboardText.includes("## Bundle Manifest") && window.__smokeClipboardText.includes("Payload checksum: fnv1a32-") && window.__smokeClipboardText.includes("Artifact quality rubric: pass (100/100, threshold 90)") && window.__smokeClipboardText.includes("Decision brief: pass (6/6)") && window.__smokeClipboardText.includes("Operator quick start: pass (5/5)") && window.__smokeClipboardText.includes("### Decision Brief") && window.__smokeClipboardText.includes("Review Package Decision Brief") && window.__smokeClipboardText.includes("### Operator Quick Start") && window.__smokeClipboardText.includes("Review Package Operator Quick Start") && window.__smokeClipboardText.includes("### Artifact Quality Rubric") && window.__smokeClipboardText.includes("## GitHub Comment Draft") && window.__smokeClipboardText.includes("## Pinned Note Body"), "workspace review package bundle copy text did not reach clipboard");
    assert(qs("[data-workspace-review-bundle-copy-status]", workspaceReviewHandoff).textContent.includes("bundle 복사됨"), "workspace review package bundle copy status did not render");
    const workspaceReviewResultValidator = qs("[data-review-result-validator]", workspaceReviewHandoff);
    await exerciseReviewResultValidator(workspaceReviewResultValidator, "workspace-review:repo-toeverything-affine:86", "toeverything/AFFiNE", "workspace");
    const workspaceReviewIssueDraft = qs("[data-workspace-review-issue-draft]", workspaceReviewHandoff);
    const workspaceReviewIssueBody = qs("[data-issue-draft-body]", workspaceReviewIssueDraft).innerText;
    assert(workspaceReviewIssueDraft.dataset.issueDraftTitle === "[Workspace] toeverything/AFFiNE Workspace 도입 검토", "workspace review issue draft title did not render");
    assert(workspaceReviewIssueDraft.dataset.issueDraftProject === "toeverything/AFFiNE", "workspace review issue draft project did not render");
    assert(workspaceReviewIssueDraft.dataset.issueDraftPriority === "high", "workspace review issue draft priority did not render");
    assert(workspaceReviewIssueDraft.dataset.issueDraftKey === "workspace-review:repo-toeverything-affine:86", "workspace review issue draft key did not render");
    assert(workspaceReviewIssueDraft.dataset.issueDraftResultSource === "validated" && workspaceReviewIssueDraft.dataset.issueDraftPackageChecksum.startsWith("fnv1a32-"), "workspace review issue draft did not switch to validated result source");
    assert(workspaceReviewIssueDraft.dataset.issueDraftTrackerReady === "true" && workspaceReviewIssueDraft.dataset.issueDraftAssignee === "jp" && workspaceReviewIssueDraft.dataset.issueDraftDue === todayISO() && workspaceReviewIssueDraft.dataset.issueDraftExecutionOwner === "PM", "workspace review issue draft tracker fields did not render");
    assert(workspaceReviewIssueDraft.dataset.issueDraftExecutionChecklistReady === "true" && Number(workspaceReviewIssueDraft.dataset.issueDraftExecutionChecklistCount || 0) >= 3, "workspace review issue draft execution checklist did not render");
    assert(!!qs("[data-issue-draft-validated-source]", workspaceReviewIssueDraft), "workspace review issue draft validated source badge did not render");
    assert(workspaceReviewIssueBody.includes("## Validated Review Result") && workspaceReviewIssueBody.includes("Source: validated") && workspaceReviewIssueBody.includes("reviewResults") && workspaceReviewIssueBody.includes("Primary decision key: workspace-review:repo-toeverything-affine:86"), "workspace validated review issue draft body did not render");
    assert(workspaceReviewIssueBody.includes("## Bundle Manifest") && workspaceReviewIssueBody.includes("Payload checksum: fnv1a32-") && workspaceReviewIssueBody.includes("Source freshness: pass"), "workspace validated review issue draft manifest evidence did not render");
    assert(workspaceReviewIssueBody.includes("## Decision Summary") && workspaceReviewIssueBody.includes("Recommendation: toeverything/AFFiNE") && workspaceReviewIssueBody.includes("Why this candidate:") && workspaceReviewIssueBody.includes("Comparison context:") && workspaceReviewIssueBody.includes("Evidence anchor:") && workspaceReviewIssueBody.includes("Stop condition:"), "workspace validated review issue decision summary did not render");
    assert(workspaceReviewIssueBody.includes("## Source Snapshot") && workspaceReviewIssueBody.includes("Source URL: https://github.com/toeverything/AFFiNE") && workspaceReviewIssueBody.includes("## Operational Readiness") && workspaceReviewIssueBody.includes("## Execution Checklist") && workspaceReviewIssueBody.includes("- [ ] First action:") && workspaceReviewIssueBody.includes("Decision gate:") && workspaceReviewIssueBody.includes("Fallback if blocked:") && workspaceReviewIssueBody.includes("## Acceptance Criteria") && workspaceReviewIssueBody.includes("## Validation Plan") && workspaceReviewIssueBody.includes("## Missing Evidence To Close"), "workspace validated review issue draft quality package did not render");
    const beforeWorkspaceIssueCount = dashboard.issues.length;
    click("[data-workspace-review-issue-create]", workspaceReviewIssueDraft);
    await waitFor(() => dashboard.issues.length === beforeWorkspaceIssueCount + 1, "workspace review issue draft did not create an issue");
    const createdWorkspaceIssue = dashboard.issues.find((issue) => issue.sourceKey === "workspace-review:repo-toeverything-affine:86");
    assert(createdWorkspaceIssue, "workspace review issue draft did not persist source key");
    assert(createdWorkspaceIssue.title === "[Workspace] toeverything/AFFiNE Workspace 도입 검토", "workspace review issue draft title was not saved");
    assert(createdWorkspaceIssue.project === "repo-toeverything-affine", "workspace review issue draft project was not saved");
    assert(createdWorkspaceIssue.priority === "high", "workspace review issue draft priority was not saved");
    assert(createdWorkspaceIssue.assignee === "jp" && createdWorkspaceIssue.due === todayISO() && createdWorkspaceIssue.estimate === 4 && createdWorkspaceIssue.executionOwner === "PM", "workspace review issue tracker fields were not saved");
    assert(Array.isArray(createdWorkspaceIssue.executionChecklist) && createdWorkspaceIssue.executionChecklist.length >= 3 && createdWorkspaceIssue.executionChecklist[0].text.includes("First action"), "workspace review issue execution checklist was not saved");
    assert(createdWorkspaceIssue.sourceKind === "validated-review-result", "workspace review issue did not save validated result source kind");
    assert(createdWorkspaceIssue.labels.includes("workspace") && createdWorkspaceIssue.labels.includes("benchmark") && createdWorkspaceIssue.labels.includes("handoff") && createdWorkspaceIssue.labels.includes("validated-result") && createdWorkspaceIssue.labels.includes("tracker-ready") && createdWorkspaceIssue.labels.includes("checklist-ready"), "workspace review issue draft labels were not saved");
    assert(createdWorkspaceIssue.body.includes("## Validated Review Result") && createdWorkspaceIssue.body.includes("Payload checksum: fnv1a32-") && createdWorkspaceIssue.body.includes("## Decision Summary") && createdWorkspaceIssue.body.includes("Recommendation: toeverything/AFFiNE") && createdWorkspaceIssue.body.includes("Evidence anchor:") && createdWorkspaceIssue.body.includes("## Operational Readiness") && createdWorkspaceIssue.body.includes("## Execution Checklist") && createdWorkspaceIssue.body.includes("Decision gate:") && createdWorkspaceIssue.body.includes("Fallback if blocked:") && createdWorkspaceIssue.body.includes("## Acceptance Criteria") && createdWorkspaceIssue.body.includes("## Validation Plan") && createdWorkspaceIssue.body.includes("Source URL: https://github.com/toeverything/AFFiNE"), "workspace validated review issue package was not saved");
    await waitFor(() => {
      const nextDraft = document.querySelector("[data-workspace-review-issue-draft]");
      return nextDraft && nextDraft.dataset.issueDraftCreated === "true" && nextDraft.dataset.issueDraftId === createdWorkspaceIssue.id;
    }, "workspace review issue draft created state did not render");
    await assertReviewArtifactDiff("[data-workspace-issue-review-artifact-diff]", "workspace-review:repo-toeverything-affine:86", "workspace-issue", "workspace issue artifact diff", "issue");
    const nextWorkspaceReviewHandoff = qs("[data-workspace-review-handoff]");
    const workspaceGithubComment = qs("[data-workspace-review-github-comment]", nextWorkspaceReviewHandoff);
    const workspaceGithubCommentOpen = qs("[data-workspace-review-github-comment-open]", workspaceGithubComment);
    const workspaceGithubCommentCopy = qs("[data-workspace-review-github-comment-copy]", workspaceGithubComment);
    const workspaceGithubCommentText = qs("[data-workspace-review-github-comment-text]", workspaceGithubComment).innerText;
    assert(workspaceGithubComment.dataset.reviewGithubCommentKey === "workspace-review:repo-toeverything-affine:86", "workspace review GitHub comment key did not render");
    assert(workspaceGithubComment.dataset.reviewGithubCommentTarget === "toeverything/AFFiNE", "workspace review GitHub comment target did not render");
    assert(workspaceGithubComment.dataset.reviewGithubCommentFormat === "markdown", "workspace review GitHub comment format did not render");
    assert(workspaceGithubCommentOpen.getAttribute("href").startsWith("https://github.com/toeverything/AFFiNE/issues/new?"), "workspace review GitHub comment issue link did not render");
    assert(workspaceGithubCommentOpen.getAttribute("href").includes("workspace-review%3Arepo-toeverything-affine%3A86"), "workspace review GitHub comment issue link did not include source key");
    assert(workspaceGithubCommentCopy.dataset.reviewGithubCommentCopyKey === "workspace-review:repo-toeverything-affine:86", "workspace review GitHub comment copy key did not render");
    assert(workspaceGithubCommentText.includes("## JooPark Workspace Review") && workspaceGithubCommentText.includes("## Comment Decision Summary") && workspaceGithubCommentText.includes("Evidence anchor:") && workspaceGithubCommentText.includes("First action:") && workspaceGithubCommentText.includes("Stop condition:") && workspaceGithubCommentText.includes("Primary decision key: workspace-review:repo-toeverything-affine:86") && workspaceGithubCommentText.includes("## Issue Draft") && workspaceGithubCommentText.includes("Compare with: AppFlowy-IO/AppFlowy"), "workspace review GitHub comment body did not render");
    window.__smokeClipboardText = "";
    click("[data-workspace-review-github-comment-copy]", workspaceGithubComment);
    await waitFor(() => window.__smokeClipboardText.includes("## Comment Decision Summary") && window.__smokeClipboardText.includes("Evidence anchor:") && window.__smokeClipboardText.includes("First action:") && window.__smokeClipboardText.includes("Stop condition:") && window.__smokeClipboardText.includes("Primary decision key: workspace-review:repo-toeverything-affine:86"), "workspace review GitHub comment copy text did not reach clipboard");
    await waitFor(() => workspaceGithubComment.dataset.reviewGithubCommentCopied === "true", "workspace review GitHub comment copy state did not update");
    assert(qs("[data-workspace-review-github-comment-copy-status]", workspaceGithubComment).textContent.includes("댓글 복사됨"), "workspace review GitHub comment copy status did not render");
    const beforeWorkspaceNoteCount = dashboard.notes.length;
    click("[data-workspace-review-note-publish]", nextWorkspaceReviewHandoff);
    await waitFor(() => dashboard.notes.length === beforeWorkspaceNoteCount + 1, "workspace review note publish did not create a note");
    const createdWorkspaceNote = dashboard.notes.find((note) => note.sourceKey === "workspace-review:repo-toeverything-affine:86");
    assert(createdWorkspaceNote, "workspace review note publish did not persist source key");
    assert(createdWorkspaceNote.title === "[Workspace Review] toeverything/AFFiNE", "workspace review note publish title was not saved");
    assert(createdWorkspaceNote.pinned === true, "workspace review note publish did not pin note");
    assert(createdWorkspaceNote.sourceKind === "workspace-review-note:validated-review-result", "workspace review note did not save validated result source kind");
    assert(createdWorkspaceNote.body.includes("## Saved Validated Result") && createdWorkspaceNote.body.includes("## Pinned Note Summary") && createdWorkspaceNote.body.includes("Evidence anchor:") && createdWorkspaceNote.body.includes("First action:") && createdWorkspaceNote.body.includes("Stop condition:") && createdWorkspaceNote.body.includes("Primary decision key: workspace-review:repo-toeverything-affine:86") && createdWorkspaceNote.body.includes("Payload checksum: fnv1a32-") && createdWorkspaceNote.body.includes("## Bundle Manifest"), "workspace validated review note publish body did not render");
    await waitFor(() => {
      const nextHandoff = document.querySelector("[data-workspace-review-handoff]");
      const nextPublish = document.querySelector("[data-workspace-review-note-publish]");
      return nextHandoff && nextPublish && nextHandoff.dataset.workspaceReviewNoteCreated === "true" && nextPublish.dataset.reviewNoteCreated === "true" && nextPublish.dataset.reviewNoteId === createdWorkspaceNote.id;
    }, "workspace review note publish state did not render");
    await assertReviewArtifactDiff("[data-workspace-note-review-artifact-diff]", "workspace-review:repo-toeverything-affine:86", "workspace-note", "workspace note artifact diff", "note");
    const workspaceNoteOpen = qs("[data-workspace-review-note-publish]");
    assert(!workspaceNoteOpen.disabled && workspaceNoteOpen.textContent.includes("노트 열기") && workspaceNoteOpen.dataset.reviewNoteCreated === "true" && workspaceNoteOpen.dataset.reviewNoteId === createdWorkspaceNote.id, "workspace review existing note action was not openable");
    click("[data-workspace-review-note-publish]");
    await waitFor(() => dashboard.currentView === "notes" && state.noteSourceFilter === "workspace-review" && document.querySelector("#modal.open #noteForm"), "workspace review existing note action did not open review note modal");
    assert(qs('#modal.open #noteForm [name="title"]').value === createdWorkspaceNote.title && qs('#modal.open [data-modal-source-link][data-source-kind="review"]'), "workspace review existing note action opened the wrong note");
    click('#modal [data-action="close-modal"]');
    await waitFor(() => !document.querySelector("#modal.open"), "workspace review existing note modal did not close");
    await nav("pm-portfolio");
    await waitFor(() => document.querySelector("[data-knowledge-base-benchmark-rubric]"), "portfolio did not restore after opening existing workspace review note");
    const knowledgeBaseRubric = qs("[data-knowledge-base-benchmark-rubric]");
    assert(knowledgeBaseRubric.innerText.includes("KB/IA 비교표"), "knowledge-base IA rubric did not render heading");
    assert(knowledgeBaseRubric.innerText.includes("outline/outline"), "Outline knowledge-base rubric did not render");
    assert(knowledgeBaseRubric.innerText.includes("BookStackApp/BookStack"), "BookStack knowledge-base rubric did not render");
    assert(knowledgeBaseRubric.innerText.includes("requarks/wiki"), "Wiki.js knowledge-base rubric did not render");
    ["정보 구조", "편집/협업", "권한/운영", "이식성"].forEach((axis) => {
      assert(!!document.querySelector('[data-kb-rubric-axis="' + axis + '"]'), "knowledge-base rubric axis did not render: " + axis);
    });
    [
      "collections + nested documents",
      "book + chapter + page hierarchy",
      "Git-backed Markdown workflows",
    ].forEach((term) => {
      assert(knowledgeBaseRubric.innerText.includes(term), "knowledge-base rubric value did not render: " + term);
    });
    const wikiJsKbScore = projectKnowledgeBaseRubricScore(wikiJsCandidate);
    const outlineKbScore = projectKnowledgeBaseRubricScore(outlineCandidate);
    const bookStackKbScore = projectKnowledgeBaseRubricScore(bookStackCandidate);
    assert(wikiJsKbScore && wikiJsKbScore.score === 87, "Wiki.js knowledge-base rubric score was wrong");
    assert(outlineKbScore && outlineKbScore.score === 87, "Outline knowledge-base rubric score was wrong");
    assert(bookStackKbScore && bookStackKbScore.score === 83, "BookStack knowledge-base rubric score was wrong");
    const kbRecommendation = qs("[data-knowledge-base-rubric-recommendation]", knowledgeBaseRubric);
    assert(kbRecommendation.dataset.knowledgeBaseRubricRecommendation === "outline/outline", "knowledge-base rubric recommendation did not pick Outline tie-breaker");
    assert(kbRecommendation.dataset.kbRubricScore === String(outlineKbScore.score), "knowledge-base rubric recommendation score did not render");
    const kbCells = Array.from(knowledgeBaseRubric.querySelectorAll("[data-kb-rubric-project][data-kb-rubric-axis]"));
    const wikiJsPortability = kbCells.find((cell) => cell.dataset.kbRubricProject === "requarks/wiki" && cell.dataset.kbRubricAxis === "이식성");
    assert(wikiJsPortability, "Wiki.js knowledge-base rubric portability cell did not render");
    assert(wikiJsPortability.dataset.kbRubricWeight === "0.2", "Wiki.js knowledge-base rubric portability weight did not render");
    assert(wikiJsPortability.dataset.kbRubricScore === "93", "Wiki.js knowledge-base rubric portability score did not render");
    const kbExport = qs("[data-knowledge-base-benchmark-export]", knowledgeBaseRubric);
    const kbExportDownload = qs("[data-kb-benchmark-export-download]", kbExport);
    const kbExportText = qs("[data-kb-benchmark-export-text]", kbExport).innerText;
    assert(kbExport.dataset.kbBenchmarkExportWinner === "outline/outline", "knowledge-base recommendation export winner did not render");
    assert(kbExport.dataset.kbBenchmarkExportGap === "0", "knowledge-base recommendation export gap did not render");
    assert(kbExportDownload.getAttribute("download") === "joopark-kb-ia-recommendation.md", "knowledge-base recommendation export filename did not render");
    assert(kbExportDownload.getAttribute("href").startsWith("data:text/markdown;charset=utf-8,"), "knowledge-base recommendation export markdown link did not render");
    assert(kbExportText.includes("Recommendation: use outline/outline as the primary Knowledge/IA benchmark") && kbExportText.includes("requarks/wiki as the portability counterweight"), "knowledge-base recommendation export copy did not render");
    assert(kbExportText.includes("Score gap: 0 points") && kbExportText.includes("Primary reason: 정보 구조 scored 86 at 35% weight"), "knowledge-base recommendation export rationale did not render");
    const kbReviewHandoff = qs("[data-knowledge-base-review-handoff]", knowledgeBaseRubric);
    const kbReviewHandoffDownload = qs("[data-kb-review-handoff-download]", kbReviewHandoff);
    const kbReviewHandoffCopy = qs("[data-kb-review-handoff-copy]", kbReviewHandoff);
    const kbReviewHandoffText = qs("[data-kb-review-handoff-text]", kbReviewHandoff).innerText;
    assert(kbReviewHandoff.dataset.kbReviewHandoffPrimaryKey === "kb-ia-review:repo-outline-outline:87", "knowledge-base review handoff primary key did not render");
    assert(kbReviewHandoff.dataset.kbReviewHandoffCount === "3", "knowledge-base review handoff count did not render");
    assert(kbReviewHandoff.dataset.reviewPromptContract === "joopark-review-handoff/v2" && kbReviewHandoff.dataset.reviewOutputFormat === "json+markdown", "knowledge-base review handoff prompt contract did not render");
    assert(kbReviewHandoffDownload.getAttribute("download") === "joopark-kb-ia-review-handoff.md", "knowledge-base review handoff filename did not render");
    assert(kbReviewHandoffDownload.getAttribute("href").startsWith("data:text/markdown;charset=utf-8,"), "knowledge-base review handoff markdown link did not render");
    assert(kbReviewHandoffText.includes("Primary decision key: kb-ia-review:repo-outline-outline:87") && kbReviewHandoffText.includes("outline/outline - IA 도입 검토") && kbReviewHandoffText.includes("requarks/wiki - IA 도입 검토"), "knowledge-base review handoff markdown copy did not render");
    assert(kbReviewHandoffText.includes("## Prompt Contract") && kbReviewHandoffText.includes("## System Prompt") && kbReviewHandoffText.includes("## User Prompt Template") && kbReviewHandoffText.includes("## Output Schema") && kbReviewHandoffText.includes("## Failure / Exception Handling"), "knowledge-base review handoff prompt sections did not render");
    assert(kbReviewHandoffText.includes("## Quality Bar") && kbReviewHandoffText.includes("## Evidence Snapshot") && kbReviewHandoffText.includes("## Execution Plan") && kbReviewHandoffText.includes("## Review Checklist"), "knowledge-base review handoff quality package did not render");
    assert(kbReviewHandoffText.includes("schemaVersion") && kbReviewHandoffText.includes("joopark-review-handoff/v2") && kbReviewHandoffText.includes("<candidate_decisions") && kbReviewHandoffText.includes("missingEvidence") && kbReviewHandoffText.includes("qualityGate") && kbReviewHandoffText.includes("sourceSnapshot") && kbReviewHandoffText.includes("acceptanceCriteria") && kbReviewHandoffText.includes("validationPlan") && kbReviewHandoffText.includes("firstAction") && kbReviewHandoffText.includes("decisionGate") && kbReviewHandoffText.includes("fallbackIfBlocked"), "knowledge-base review handoff structured contract did not render");
    assert(kbReviewHandoffCopy.dataset.kbReviewHandoffCopyKey === "kb-ia-review:repo-outline-outline:87", "knowledge-base review handoff copy key did not render");
    window.__smokeClipboardText = "";
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: async (text) => { window.__smokeClipboardText = text; } },
    });
    click("[data-kb-review-handoff-copy]");
    await waitFor(() => window.__smokeClipboardText.includes("Primary decision key: kb-ia-review:repo-outline-outline:87") && window.__smokeClipboardText.includes("## Output Schema") && window.__smokeClipboardText.includes("## Evidence Snapshot") && window.__smokeClipboardText.includes("## Review Checklist"), "knowledge-base review handoff copy text did not reach clipboard");
    await waitFor(() => kbReviewHandoff.dataset.reviewHandoffCopied === "true", "knowledge-base review handoff copy state did not update");
    assert(qs("[data-kb-review-handoff-copy-status]", kbReviewHandoff).textContent.includes("복사됨"), "knowledge-base review handoff copy status did not render");
    const kbBundleDownload = qs("[data-knowledge-base-review-bundle-download]", kbReviewHandoff);
    const kbBundleCopy = qs("[data-knowledge-base-review-bundle-copy]", kbReviewHandoff);
    const kbBundleText = qs("[data-kb-review-package-bundle-text]", kbReviewHandoff).textContent;
    const kbBundleManifest = qs("[data-knowledge-base-review-package-manifest]", kbReviewHandoff);
    assert(kbBundleDownload.getAttribute("download") === "joopark-kb-ia-review-package.md", "knowledge-base review package bundle filename did not render");
    assert(kbBundleDownload.getAttribute("href").startsWith("data:text/markdown;charset=utf-8,"), "knowledge-base review package bundle markdown link did not render");
    assert(kbBundleManifest.dataset.reviewPackageManifestStatus === "pass", "knowledge-base review package bundle manifest did not pass");
    assert(kbBundleManifest.dataset.reviewPackagePayloadChecksum.startsWith("fnv1a32-"), "knowledge-base review package bundle checksum did not render");
    assert(kbBundleManifest.dataset.reviewPackageSourceFreshness === "pass" && kbBundleManifest.dataset.reviewPackageSourceCount === "3", "knowledge-base review package bundle source freshness did not render");
    assert(kbBundleManifest.dataset.reviewPackagePasteTargetStatus === "pass" && kbBundleManifest.dataset.reviewPackagePasteTargetReady === "3" && kbBundleManifest.dataset.reviewPackagePasteTargetCount === "3", "knowledge-base review package paste targets did not pass");
    assert(kbBundleManifest.dataset.reviewPackageFinalQualityStatus === "pass" && kbBundleManifest.dataset.reviewPackageFinalQualityScore === "6/6", "knowledge-base review package final quality gate did not pass");
    assert(kbBundleManifest.dataset.reviewPackageArtifactQualityStatus === "pass" && kbBundleManifest.dataset.reviewPackageArtifactQualityScore === "100/100" && kbBundleManifest.dataset.reviewPackageArtifactQualityItemCount === "5", "knowledge-base review package artifact quality rubric did not pass");
    assert(kbBundleManifest.dataset.reviewPackageDecisionBriefStatus === "pass" && kbBundleManifest.dataset.reviewPackageDecisionBriefReady === "6" && kbBundleManifest.dataset.reviewPackageDecisionBriefCount === "6", "knowledge-base review package decision brief did not pass");
    assert(kbBundleManifest.querySelectorAll("[data-review-package-decision-brief-item]").length === 6 && kbBundleManifest.innerText.includes("Recommendation") && kbBundleManifest.innerText.includes("Why this candidate") && kbBundleManifest.innerText.includes("Comparison context") && kbBundleManifest.innerText.includes("Execution target") && kbBundleManifest.innerText.includes("Evidence anchor") && kbBundleManifest.innerText.includes("Next action"), "knowledge-base review package decision brief did not render");
    assert(kbBundleManifest.dataset.reviewPackageOperatorQuickStartStatus === "pass" && kbBundleManifest.dataset.reviewPackageOperatorQuickStartReady === "5" && kbBundleManifest.dataset.reviewPackageOperatorQuickStartCount === "5", "knowledge-base review package operator quick start did not pass");
    assert(kbBundleManifest.querySelectorAll("[data-review-package-operator-quick-start-item]").length === 5 && kbBundleManifest.innerText.includes("Confirm quality gate") && kbBundleManifest.innerText.includes("Fill external tracker fields") && kbBundleManifest.innerText.includes("Paste tracker issue body") && kbBundleManifest.innerText.includes("Share final submission update") && kbBundleManifest.innerText.includes("Keep bundle proof"), "knowledge-base review package operator quick start did not render");
	    assert(kbBundleManifest.querySelectorAll("[data-review-package-paste-target-item]").length === 3 && kbBundleManifest.innerText.includes("Tracker issue") && kbBundleManifest.innerText.includes("GitHub comment") && kbBundleManifest.innerText.includes("Pinned note"), "knowledge-base review package paste target list did not render");
	    assert(kbBundleManifest.dataset.reviewPackageQualityRepairStatus === "none" && kbBundleManifest.dataset.reviewPackageQualityRepairCount === "0", "knowledge-base review package repair checklist did not report clean state");
	    assert(qs("[data-review-package-quality-repair-empty]", kbBundleManifest).textContent.includes("No repairs required"), "knowledge-base review package repair empty state did not render");
	    const kbPastePreview = qs("[data-knowledge-base-review-package-paste-preview]", kbReviewHandoff);
	    assert(kbPastePreview.dataset.reviewPackagePastePreviewReady === "3" && kbPastePreview.dataset.reviewPackagePastePreviewCount === "3", "knowledge-base review package paste preview did not report ready state");
	    assert(kbPastePreview.querySelectorAll("[data-review-package-paste-preview-item]").length === 3 && kbPastePreview.innerText.includes("Tracker issue body") && kbPastePreview.innerText.includes("GitHub comment body") && kbPastePreview.innerText.includes("Pinned note body"), "knowledge-base review package paste preview items did not render");
	    assert(qs("[data-review-package-paste-preview-id='tracker_issue'] [data-review-package-paste-preview-body]", kbPastePreview).innerText.includes("Persist key: kb-ia-review:repo-outline-outline:87"), "knowledge-base tracker paste preview body was incomplete");
	    assert(qs("[data-review-package-paste-preview-id='github_comment'] [data-review-package-paste-preview-body]", kbPastePreview).innerText.includes("## Comment Decision Summary") && qs("[data-review-package-paste-preview-id='github_comment'] [data-review-package-paste-preview-body]", kbPastePreview).innerText.includes("Evidence anchor:") && qs("[data-review-package-paste-preview-id='github_comment'] [data-review-package-paste-preview-body]", kbPastePreview).innerText.includes("First action:") && qs("[data-review-package-paste-preview-id='github_comment'] [data-review-package-paste-preview-body]", kbPastePreview).innerText.includes("Stop condition:") && qs("[data-review-package-paste-preview-id='github_comment'] [data-review-package-paste-preview-body]", kbPastePreview).innerText.includes("## Issue Draft"), "knowledge-base GitHub comment paste preview body was incomplete");
	    assert(qs("[data-review-package-paste-preview-id='pinned_note'] [data-review-package-paste-preview-body]", kbPastePreview).innerText.includes("## Pinned Note Summary") && qs("[data-review-package-paste-preview-id='pinned_note'] [data-review-package-paste-preview-body]", kbPastePreview).innerText.includes("Evidence anchor:") && qs("[data-review-package-paste-preview-id='pinned_note'] [data-review-package-paste-preview-body]", kbPastePreview).innerText.includes("First action:") && qs("[data-review-package-paste-preview-id='pinned_note'] [data-review-package-paste-preview-body]", kbPastePreview).innerText.includes("Stop condition:") && qs("[data-review-package-paste-preview-id='pinned_note'] [data-review-package-paste-preview-body]", kbPastePreview).innerText.includes("## Issue Draft"), "knowledge-base pinned note paste preview body was incomplete");
	    assert(kbBundleText.includes("# JooPark Knowledge/IA Review Package Bundle") && kbBundleText.includes("## Bundle Manifest") && kbBundleText.includes("## Markdown Handoff") && kbBundleText.includes("## Issue Draft") && kbBundleText.includes("## GitHub Comment Draft") && kbBundleText.includes("## Pinned Note Body"), "knowledge-base review package bundle sections did not render");
	    assert(kbBundleText.includes("Manifest schema: joopark-review-package-manifest/v1") && kbBundleText.includes("Validation status: pass") && kbBundleText.includes("Payload checksum: fnv1a32-") && kbBundleText.includes("Source freshness: pass (3/3)") && kbBundleText.includes("Paste target readiness: pass (3/3)") && kbBundleText.includes("Ready to submit: pass") && kbBundleText.includes("Final quality score: 6/6") && kbBundleText.includes("Artifact quality rubric: pass (100/100, threshold 90)") && kbBundleText.includes("Decision brief: pass (6/6)") && kbBundleText.includes("Operator quick start: pass (5/5)") && kbBundleText.includes("Quality repairs: none (0)") && kbBundleText.includes("### Decision Brief") && kbBundleText.includes("Review Package Decision Brief") && kbBundleText.includes("Recommendation") && kbBundleText.includes("Evidence anchor") && kbBundleText.includes("Next action") && kbBundleText.includes("### Operator Quick Start") && kbBundleText.includes("Review Package Operator Quick Start") && kbBundleText.includes("Fill external tracker fields") && kbBundleText.includes("Keep bundle proof") && kbBundleText.includes("### Paste-Ready Targets") && kbBundleText.includes("### Artifact Quality Rubric") && kbBundleText.includes("Required form fit") && kbBundleText.includes("Submission flow readiness") && kbBundleText.includes("### Paste Body Preview") && kbBundleText.includes("### Tracker Field Packet") && kbBundleText.includes("Tracker issue body") && kbBundleText.includes("GitHub comment body") && kbBundleText.includes("Pinned note body") && kbBundleText.includes("Tracker issue") && kbBundleText.includes("Pinned note") && kbBundleText.includes("### Final Output Quality Gate") && kbBundleText.includes("### Quality Repair Checklist") && kbBundleText.includes("- [x] No repairs required; package is ready to submit."), "knowledge-base review package bundle manifest did not include validation evidence");
	    assert(kbBundleText.includes("### Submit Sequence") && kbBundleText.includes("Review Package Submit Sequence"), "knowledge-base review package bundle did not include submit sequence");
	    assert(kbBundleText.includes("### External Issue Receipt Template") && kbBundleText.includes("External Issue Receipt Template"), "knowledge-base review package bundle did not include external receipt template");
    assert(kbBundleText.includes("Source URL: https://github.com/outline/outline") && kbBundleText.includes("## Decision Summary") && kbBundleText.includes("Recommendation: outline/outline") && kbBundleText.includes("Evidence anchor:") && kbBundleText.includes("Stop condition:") && kbBundleText.includes("## Operational Readiness") && kbBundleText.includes("Decision gate:") && kbBundleText.includes("Fallback if blocked:") && kbBundleText.includes("## Acceptance Criteria") && kbBundleText.includes("## Validation Plan"), "knowledge-base review package bundle did not include execution-quality content");
    assert(kbBundleCopy.dataset.reviewBundleCopyKey === "kb-ia-review:repo-outline-outline:87", "knowledge-base review package bundle copy key did not render");
    window.__smokeClipboardText = "";
    click("[data-knowledge-base-review-bundle-copy]", kbReviewHandoff);
    await waitFor(() => kbReviewHandoff.dataset.reviewBundleCopied === "true" && window.__smokeClipboardText.includes("# JooPark Knowledge/IA Review Package Bundle") && window.__smokeClipboardText.includes("## Bundle Manifest") && window.__smokeClipboardText.includes("Payload checksum: fnv1a32-") && window.__smokeClipboardText.includes("Artifact quality rubric: pass (100/100, threshold 90)") && window.__smokeClipboardText.includes("Decision brief: pass (6/6)") && window.__smokeClipboardText.includes("Operator quick start: pass (5/5)") && window.__smokeClipboardText.includes("### Decision Brief") && window.__smokeClipboardText.includes("Review Package Decision Brief") && window.__smokeClipboardText.includes("### Operator Quick Start") && window.__smokeClipboardText.includes("Review Package Operator Quick Start") && window.__smokeClipboardText.includes("### Artifact Quality Rubric") && window.__smokeClipboardText.includes("## GitHub Comment Draft") && window.__smokeClipboardText.includes("## Pinned Note Body"), "knowledge-base review package bundle copy text did not reach clipboard");
    assert(qs("[data-kb-review-bundle-copy-status]", kbReviewHandoff).textContent.includes("bundle 복사됨"), "knowledge-base review package bundle copy status did not render");
    const kbReviewResultValidator = qs("[data-review-result-validator]", kbReviewHandoff);
    await exerciseReviewResultValidator(kbReviewResultValidator, "kb-ia-review:repo-outline-outline:87", "outline/outline", "knowledge-base");
    const kbReviewIssueDraft = qs("[data-kb-review-issue-draft]", kbReviewHandoff);
    const kbReviewIssueBody = qs("[data-issue-draft-body]", kbReviewIssueDraft).innerText;
    assert(kbReviewIssueDraft.dataset.issueDraftTitle === "[KB/IA] outline/outline IA 도입 검토", "knowledge-base review issue draft title did not render");
    assert(kbReviewIssueDraft.dataset.issueDraftProject === "outline/outline", "knowledge-base review issue draft project did not render");
    assert(kbReviewIssueDraft.dataset.issueDraftPriority === "high", "knowledge-base review issue draft priority did not render");
    assert(kbReviewIssueDraft.dataset.issueDraftKey === "kb-ia-review:repo-outline-outline:87", "knowledge-base review issue draft key did not render");
    assert(kbReviewIssueDraft.dataset.issueDraftResultSource === "validated" && kbReviewIssueDraft.dataset.issueDraftPackageChecksum.startsWith("fnv1a32-"), "knowledge-base review issue draft did not switch to validated result source");
    assert(kbReviewIssueDraft.dataset.issueDraftTrackerReady === "true" && kbReviewIssueDraft.dataset.issueDraftAssignee === "jp" && kbReviewIssueDraft.dataset.issueDraftDue === todayISO() && kbReviewIssueDraft.dataset.issueDraftExecutionOwner === "PM", "knowledge-base review issue draft tracker fields did not render");
    assert(kbReviewIssueDraft.dataset.issueDraftExecutionChecklistReady === "true" && Number(kbReviewIssueDraft.dataset.issueDraftExecutionChecklistCount || 0) >= 3, "knowledge-base review issue draft execution checklist did not render");
    assert(!!qs("[data-issue-draft-validated-source]", kbReviewIssueDraft), "knowledge-base review issue draft validated source badge did not render");
    assert(kbReviewIssueBody.includes("## Validated Review Result") && kbReviewIssueBody.includes("Source: validated") && kbReviewIssueBody.includes("reviewResults") && kbReviewIssueBody.includes("Primary decision key: kb-ia-review:repo-outline-outline:87"), "knowledge-base validated review issue draft body did not render");
    assert(kbReviewIssueBody.includes("## Bundle Manifest") && kbReviewIssueBody.includes("Payload checksum: fnv1a32-") && kbReviewIssueBody.includes("Source freshness: pass"), "knowledge-base validated review issue draft manifest evidence did not render");
    assert(kbReviewIssueBody.includes("## Decision Summary") && kbReviewIssueBody.includes("Recommendation: outline/outline") && kbReviewIssueBody.includes("Why this candidate:") && kbReviewIssueBody.includes("Comparison context:") && kbReviewIssueBody.includes("Evidence anchor:") && kbReviewIssueBody.includes("Stop condition:"), "knowledge-base validated review issue decision summary did not render");
    assert(kbReviewIssueBody.includes("## Source Snapshot") && kbReviewIssueBody.includes("Source URL: https://github.com/outline/outline") && kbReviewIssueBody.includes("## Operational Readiness") && kbReviewIssueBody.includes("## Execution Checklist") && kbReviewIssueBody.includes("- [ ] First action:") && kbReviewIssueBody.includes("Decision gate:") && kbReviewIssueBody.includes("Fallback if blocked:") && kbReviewIssueBody.includes("## Acceptance Criteria") && kbReviewIssueBody.includes("## Validation Plan") && kbReviewIssueBody.includes("## Missing Evidence To Close"), "knowledge-base validated review issue draft quality package did not render");
    const beforeKbIssueCount = dashboard.issues.length;
    click("[data-kb-review-issue-create]", kbReviewIssueDraft);
    await waitFor(() => dashboard.issues.length === beforeKbIssueCount + 1, "knowledge-base review issue draft did not create an issue");
    const createdKbIssue = dashboard.issues.find((issue) => issue.sourceKey === "kb-ia-review:repo-outline-outline:87");
    assert(createdKbIssue, "knowledge-base review issue draft did not persist source key");
    assert(createdKbIssue.title === "[KB/IA] outline/outline IA 도입 검토", "knowledge-base review issue draft title was not saved");
    assert(createdKbIssue.project === "repo-outline-outline", "knowledge-base review issue draft project was not saved");
    assert(createdKbIssue.priority === "high", "knowledge-base review issue draft priority was not saved");
    assert(createdKbIssue.assignee === "jp" && createdKbIssue.due === todayISO() && createdKbIssue.estimate === 4 && createdKbIssue.executionOwner === "PM", "knowledge-base review issue tracker fields were not saved");
    assert(Array.isArray(createdKbIssue.executionChecklist) && createdKbIssue.executionChecklist.length >= 3 && createdKbIssue.executionChecklist[0].text.includes("First action"), "knowledge-base review issue execution checklist was not saved");
    assert(createdKbIssue.sourceKind === "validated-review-result", "knowledge-base review issue did not save validated result source kind");
    assert(createdKbIssue.labels.includes("knowledge-base") && createdKbIssue.labels.includes("ia") && createdKbIssue.labels.includes("handoff") && createdKbIssue.labels.includes("validated-result") && createdKbIssue.labels.includes("tracker-ready") && createdKbIssue.labels.includes("checklist-ready"), "knowledge-base review issue draft labels were not saved");
    assert(createdKbIssue.body.includes("## Validated Review Result") && createdKbIssue.body.includes("Payload checksum: fnv1a32-") && createdKbIssue.body.includes("## Decision Summary") && createdKbIssue.body.includes("Recommendation: outline/outline") && createdKbIssue.body.includes("Evidence anchor:") && createdKbIssue.body.includes("## Operational Readiness") && createdKbIssue.body.includes("## Execution Checklist") && createdKbIssue.body.includes("Decision gate:") && createdKbIssue.body.includes("Fallback if blocked:") && createdKbIssue.body.includes("## Acceptance Criteria") && createdKbIssue.body.includes("## Validation Plan") && createdKbIssue.body.includes("Source URL: https://github.com/outline/outline"), "knowledge-base validated review issue package was not saved");
    await waitFor(() => {
      const nextDraft = document.querySelector("[data-kb-review-issue-draft]");
      return nextDraft && nextDraft.dataset.issueDraftCreated === "true" && nextDraft.dataset.issueDraftId === createdKbIssue.id;
    }, "knowledge-base review issue draft created state did not render");
    await assertReviewArtifactDiff("[data-kb-issue-review-artifact-diff]", "kb-ia-review:repo-outline-outline:87", "kb-issue", "knowledge-base issue artifact diff", "issue");
    const nextKbReviewHandoff = qs("[data-knowledge-base-review-handoff]");
    const kbGithubComment = qs("[data-kb-review-github-comment]", nextKbReviewHandoff);
    const kbGithubCommentOpen = qs("[data-kb-review-github-comment-open]", kbGithubComment);
    const kbGithubCommentCopy = qs("[data-kb-review-github-comment-copy]", kbGithubComment);
    const kbGithubCommentText = qs("[data-kb-review-github-comment-text]", kbGithubComment).innerText;
    assert(kbGithubComment.dataset.reviewGithubCommentKey === "kb-ia-review:repo-outline-outline:87", "knowledge-base review GitHub comment key did not render");
    assert(kbGithubComment.dataset.reviewGithubCommentTarget === "outline/outline", "knowledge-base review GitHub comment target did not render");
    assert(kbGithubComment.dataset.reviewGithubCommentFormat === "markdown", "knowledge-base review GitHub comment format did not render");
    assert(kbGithubCommentOpen.getAttribute("href").startsWith("https://github.com/outline/outline/issues/new?"), "knowledge-base review GitHub comment issue link did not render");
    assert(kbGithubCommentOpen.getAttribute("href").includes("kb-ia-review%3Arepo-outline-outline%3A87"), "knowledge-base review GitHub comment issue link did not include source key");
    assert(kbGithubCommentCopy.dataset.reviewGithubCommentCopyKey === "kb-ia-review:repo-outline-outline:87", "knowledge-base review GitHub comment copy key did not render");
    assert(kbGithubCommentText.includes("## JooPark Knowledge/IA Review") && kbGithubCommentText.includes("## Comment Decision Summary") && kbGithubCommentText.includes("Evidence anchor:") && kbGithubCommentText.includes("First action:") && kbGithubCommentText.includes("Stop condition:") && kbGithubCommentText.includes("Primary decision key: kb-ia-review:repo-outline-outline:87") && kbGithubCommentText.includes("## Issue Draft") && kbGithubCommentText.includes("Compare with: requarks/wiki"), "knowledge-base review GitHub comment body did not render");
    window.__smokeClipboardText = "";
    click("[data-kb-review-github-comment-copy]", kbGithubComment);
    await waitFor(() => window.__smokeClipboardText.includes("## Comment Decision Summary") && window.__smokeClipboardText.includes("Evidence anchor:") && window.__smokeClipboardText.includes("First action:") && window.__smokeClipboardText.includes("Stop condition:") && window.__smokeClipboardText.includes("Primary decision key: kb-ia-review:repo-outline-outline:87"), "knowledge-base review GitHub comment copy text did not reach clipboard");
    await waitFor(() => kbGithubComment.dataset.reviewGithubCommentCopied === "true", "knowledge-base review GitHub comment copy state did not update");
    assert(qs("[data-kb-review-github-comment-copy-status]", kbGithubComment).textContent.includes("댓글 복사됨"), "knowledge-base review GitHub comment copy status did not render");
    const beforeKbNoteCount = dashboard.notes.length;
    click("[data-kb-review-note-publish]", nextKbReviewHandoff);
    await waitFor(() => dashboard.notes.length === beforeKbNoteCount + 1, "knowledge-base review note publish did not create a note");
    const createdKbNote = dashboard.notes.find((note) => note.sourceKey === "kb-ia-review:repo-outline-outline:87");
    assert(createdKbNote, "knowledge-base review note publish did not persist source key");
    assert(createdKbNote.title === "[KB/IA Review] outline/outline", "knowledge-base review note publish title was not saved");
    assert(createdKbNote.pinned === true, "knowledge-base review note publish did not pin note");
    assert(createdKbNote.sourceKind === "knowledge-base-review-note:validated-review-result", "knowledge-base review note publish source kind was not saved");
    assert(createdKbNote.body.includes("## Saved Validated Result") && createdKbNote.body.includes("## Pinned Note Summary") && createdKbNote.body.includes("Evidence anchor:") && createdKbNote.body.includes("First action:") && createdKbNote.body.includes("Stop condition:") && createdKbNote.body.includes("Primary decision key: kb-ia-review:repo-outline-outline:87") && createdKbNote.body.includes("Payload checksum: fnv1a32-") && createdKbNote.body.includes("## Bundle Manifest"), "knowledge-base validated review note publish body did not render");
    reviewResultNoteAppliedOk = true;
    await waitFor(() => {
      const nextHandoff = document.querySelector("[data-knowledge-base-review-handoff]");
      const nextPublish = document.querySelector("[data-kb-review-note-publish]");
      return nextHandoff && nextPublish && nextHandoff.dataset.kbReviewNoteCreated === "true" && nextPublish.dataset.reviewNoteCreated === "true" && nextPublish.dataset.reviewNoteId === createdKbNote.id;
    }, "knowledge-base review note publish state did not render");
    await assertReviewArtifactDiff("[data-kb-note-review-artifact-diff]", "kb-ia-review:repo-outline-outline:87", "kb-note", "knowledge-base note artifact diff", "note");
    const kbNoteOpen = qs("[data-kb-review-note-publish]");
    assert(!kbNoteOpen.disabled && kbNoteOpen.textContent.includes("노트 열기") && kbNoteOpen.dataset.reviewNoteCreated === "true" && kbNoteOpen.dataset.reviewNoteId === createdKbNote.id && kbNoteOpen.dataset.reviewNoteExisting === "true", "knowledge-base review existing note action was not openable");
    click("[data-kb-review-note-publish]");
    await waitFor(() => dashboard.currentView === "notes" && state.noteSourceFilter === "kb-ia-review" && document.querySelector("#modal.open #noteForm"), "knowledge-base review existing note action did not open review note modal");
    const kbNoteSource = qs('#modal.open [data-modal-source-link][data-source-kind="review"][data-source-record-kind="note"][data-source-record-id="' + createdKbNote.id + '"]');
    assert(qs('#modal.open #noteForm [name="title"]').value === createdKbNote.title && kbNoteSource && kbNoteSource.dataset.sourceKey === "kb-ia-review:repo-outline-outline:87", "knowledge-base review existing note action opened the wrong note");
    click('#modal [data-action="close-modal"]');
    await waitFor(() => !document.querySelector("#modal.open"), "knowledge-base review existing note modal did not close");
    await nav("pm-portfolio");
    await waitFor(() => document.querySelector("[data-benchmark-review-queue]"), "portfolio did not restore after opening existing knowledge-base review note");
    reviewKbNoteExistingOpenOk = true;
    candidateBenchmarkRubricVisibleOk = true;
    candidateBenchmarkRubricScoreVisibleOk = true;
    workspaceBenchmarkRubricVisibleOk = true;
    workspaceBenchmarkExportVisibleOk = true;
    workspaceBenchmarkReviewHandoffVisibleOk = true;
    workspaceBenchmarkReviewHandoffCopyVisibleOk = true;
    workspaceBenchmarkReviewIssueDraftVisibleOk = true;
    workspaceBenchmarkReviewNotePublishVisibleOk = true;
    workspaceBenchmarkReviewGithubCommentVisibleOk = true;
    knowledgeBaseBenchmarkRubricVisibleOk = true;
    knowledgeBaseBenchmarkExportVisibleOk = true;
    knowledgeBaseBenchmarkReviewHandoffVisibleOk = true;
    knowledgeBaseBenchmarkReviewHandoffCopyVisibleOk = true;
    knowledgeBaseBenchmarkReviewIssueDraftVisibleOk = true;
    knowledgeBaseBenchmarkReviewNotePublishVisibleOk = true;
    knowledgeBaseBenchmarkReviewGithubCommentVisibleOk = true;
    candidateBenchmarkRecommendationExportVisibleOk = true;
    const reviewQueue = qs("[data-benchmark-review-queue]");
    const reviewDecision = qs("[data-benchmark-review-decision]", reviewQueue);
    assert(reviewDecision.dataset.reviewProject === "Taskosaur/Taskosaur", "benchmark review queue did not persist Taskosaur decision");
    assert(reviewDecision.dataset.reviewScore === "86", "benchmark review queue score did not render");
    assert(reviewDecision.dataset.reviewRank === "1", "benchmark review queue rank did not render");
    assert(reviewDecision.dataset.reviewPersistKey === "benchmark-review:repo-taskosaur-taskosaur:86", "benchmark review queue persist key did not render");
    assert(reviewDecision.dataset.benchmarkReviewDecision === "도입 검토", "benchmark review queue decision did not render");
    assert(reviewQueue.innerText.includes("리뷰 대기열"), "benchmark review queue heading did not render");
    assert(reviewQueue.innerText.includes("강한 추천 86"), "benchmark review queue score label did not render");
    let reviewHandoff = qs("[data-benchmark-review-handoff]", reviewQueue);
    const reviewHandoffDownload = qs("[data-review-handoff-download]", reviewHandoff);
    const reviewHandoffCopy = qs("[data-review-handoff-copy]", reviewHandoff);
    const reviewHandoffText = qs("[data-review-handoff-text]", reviewHandoff).innerText;
    assert(reviewHandoff.dataset.reviewHandoffPrimaryKey === "benchmark-review:repo-taskosaur-taskosaur:86", "benchmark review handoff primary key did not render");
    assert(reviewHandoff.dataset.reviewHandoffCount === "2", "benchmark review handoff count did not render");
    assert(reviewHandoff.dataset.reviewPromptContract === "joopark-review-handoff/v2" && reviewHandoff.dataset.reviewOutputFormat === "json+markdown", "benchmark review handoff prompt contract did not render");
    assert(reviewHandoffDownload.getAttribute("download") === "joopark-benchmark-review-queue.md", "benchmark review handoff filename did not render");
    assert(reviewHandoffDownload.getAttribute("href").startsWith("data:text/markdown;charset=utf-8,"), "benchmark review handoff markdown link did not render");
    assert(reviewHandoffText.includes("Primary decision key: benchmark-review:repo-taskosaur-taskosaur:86") && reviewHandoffText.includes("Taskosaur/Taskosaur - 도입 검토") && reviewHandoffText.includes("happybhati/workstream - 비교 유지"), "benchmark review handoff markdown copy did not render");
    assert(reviewHandoffText.includes("## Prompt Contract") && reviewHandoffText.includes("## System Prompt") && reviewHandoffText.includes("## User Prompt Template") && reviewHandoffText.includes("## Output Schema") && reviewHandoffText.includes("## Failure / Exception Handling"), "benchmark review handoff prompt sections did not render");
    assert(reviewHandoffText.includes("## Quality Bar") && reviewHandoffText.includes("## Evidence Snapshot") && reviewHandoffText.includes("## Execution Plan") && reviewHandoffText.includes("## Review Checklist"), "benchmark review handoff quality package did not render");
    assert(reviewHandoffText.includes("schemaVersion") && reviewHandoffText.includes("joopark-review-handoff/v2") && reviewHandoffText.includes("<candidate_decisions") && reviewHandoffText.includes("missingEvidence") && reviewHandoffText.includes("qualityGate") && reviewHandoffText.includes("sourceSnapshot") && reviewHandoffText.includes("acceptanceCriteria") && reviewHandoffText.includes("validationPlan") && reviewHandoffText.includes("firstAction") && reviewHandoffText.includes("decisionGate") && reviewHandoffText.includes("fallbackIfBlocked"), "benchmark review handoff structured contract did not render");
    assert(reviewHandoffCopy.dataset.reviewHandoffCopyKey === "benchmark-review:repo-taskosaur-taskosaur:86", "benchmark review handoff copy key did not render");
    window.__smokeClipboardText = "";
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: async (text) => { window.__smokeClipboardText = text; } },
    });
    click("[data-review-handoff-copy]", reviewHandoff);
    await waitFor(() => window.__smokeClipboardText.includes("Primary decision key: benchmark-review:repo-taskosaur-taskosaur:86") && window.__smokeClipboardText.includes("## Output Schema") && window.__smokeClipboardText.includes("## Evidence Snapshot") && window.__smokeClipboardText.includes("## Review Checklist"), "benchmark review handoff copy text did not reach clipboard");
    await waitFor(() => reviewHandoff.dataset.reviewHandoffCopied === "true", "benchmark review handoff copy state did not update");
    assert(qs("[data-review-handoff-copy-status]", reviewHandoff).textContent.includes("복사됨"), "benchmark review handoff copy status did not render");
    const benchmarkBundleDownload = qs("[data-benchmark-review-bundle-download]", reviewHandoff);
    const benchmarkBundleText = qs("[data-benchmark-review-package-bundle-text]", reviewHandoff).textContent;
    const benchmarkBundleManifest = qs("[data-benchmark-review-package-manifest]", reviewHandoff);
    assert(benchmarkBundleDownload.getAttribute("download") === "joopark-benchmark-review-package.md", "benchmark review package bundle filename did not render");
    assert(benchmarkBundleDownload.getAttribute("href").startsWith("data:text/markdown;charset=utf-8,"), "benchmark review package bundle markdown link did not render");
    assert(benchmarkBundleManifest.dataset.reviewPackageManifestStatus === "pass", "benchmark review package bundle manifest did not pass");
    assert(benchmarkBundleManifest.dataset.reviewPackagePayloadChecksum.startsWith("fnv1a32-"), "benchmark review package bundle checksum did not render");
    assert(benchmarkBundleManifest.dataset.reviewPackageSourceFreshness === "pass" && benchmarkBundleManifest.dataset.reviewPackageSourceCount === "2", "benchmark review package bundle source freshness did not render");
    assert(benchmarkBundleManifest.dataset.reviewPackagePasteTargetStatus === "pass" && benchmarkBundleManifest.dataset.reviewPackagePasteTargetReady === "3" && benchmarkBundleManifest.dataset.reviewPackagePasteTargetCount === "3", "benchmark review package paste targets did not pass");
    assert(benchmarkBundleManifest.dataset.reviewPackageFinalQualityStatus === "pass" && benchmarkBundleManifest.dataset.reviewPackageFinalQualityScore === "6/6", "benchmark review package final quality gate did not pass");
    assert(benchmarkBundleManifest.dataset.reviewPackageArtifactQualityStatus === "pass" && benchmarkBundleManifest.dataset.reviewPackageArtifactQualityScore === "100/100" && benchmarkBundleManifest.dataset.reviewPackageArtifactQualityItemCount === "5", "benchmark review package artifact quality rubric did not pass");
    assert(benchmarkBundleManifest.dataset.reviewPackageDecisionBriefStatus === "pass" && benchmarkBundleManifest.dataset.reviewPackageDecisionBriefReady === "6" && benchmarkBundleManifest.dataset.reviewPackageDecisionBriefCount === "6", "benchmark review package decision brief did not pass");
    assert(benchmarkBundleManifest.querySelectorAll("[data-review-package-decision-brief-item]").length === 6 && benchmarkBundleManifest.innerText.includes("Recommendation") && benchmarkBundleManifest.innerText.includes("Why this candidate") && benchmarkBundleManifest.innerText.includes("Comparison context") && benchmarkBundleManifest.innerText.includes("Execution target") && benchmarkBundleManifest.innerText.includes("Evidence anchor") && benchmarkBundleManifest.innerText.includes("Next action"), "benchmark review package decision brief did not render");
    assert(benchmarkBundleManifest.dataset.reviewPackageOperatorQuickStartStatus === "pass" && benchmarkBundleManifest.dataset.reviewPackageOperatorQuickStartReady === "5" && benchmarkBundleManifest.dataset.reviewPackageOperatorQuickStartCount === "5", "benchmark review package operator quick start did not pass");
    assert(benchmarkBundleManifest.querySelectorAll("[data-review-package-operator-quick-start-item]").length === 5 && benchmarkBundleManifest.innerText.includes("Confirm quality gate") && benchmarkBundleManifest.innerText.includes("Fill external tracker fields") && benchmarkBundleManifest.innerText.includes("Paste tracker issue body") && benchmarkBundleManifest.innerText.includes("Share final submission update") && benchmarkBundleManifest.innerText.includes("Keep bundle proof"), "benchmark review package operator quick start did not render");
	    assert(benchmarkBundleManifest.querySelectorAll("[data-review-package-paste-target-item]").length === 3 && benchmarkBundleManifest.innerText.includes("Tracker issue") && benchmarkBundleManifest.innerText.includes("GitHub comment") && benchmarkBundleManifest.innerText.includes("Pinned note"), "benchmark review package paste target list did not render");
	    assert(benchmarkBundleManifest.dataset.reviewPackageQualityRepairStatus === "none" && benchmarkBundleManifest.dataset.reviewPackageQualityRepairCount === "0", "benchmark review package repair checklist did not report clean state");
	    assert(qs("[data-review-package-quality-repair-empty]", benchmarkBundleManifest).textContent.includes("No repairs required"), "benchmark review package repair empty state did not render");
	    const benchmarkPastePreview = qs("[data-benchmark-review-package-paste-preview]", reviewHandoff);
	    assert(benchmarkPastePreview.dataset.reviewPackagePastePreviewReady === "3" && benchmarkPastePreview.dataset.reviewPackagePastePreviewCount === "3", "benchmark review package paste preview did not report ready state");
	    assert(benchmarkPastePreview.querySelectorAll("[data-review-package-paste-preview-item]").length === 3 && benchmarkPastePreview.innerText.includes("Tracker issue body") && benchmarkPastePreview.innerText.includes("GitHub comment body") && benchmarkPastePreview.innerText.includes("Pinned note body"), "benchmark review package paste preview items did not render");
	    assert(qs("[data-review-package-paste-preview-id='tracker_issue'] [data-review-package-paste-preview-body]", benchmarkPastePreview).innerText.includes("Persist key: benchmark-review:repo-taskosaur-taskosaur:86"), "benchmark tracker paste preview body was incomplete");
	    assert(qs("[data-review-package-paste-preview-id='github_comment'] [data-review-package-paste-preview-body]", benchmarkPastePreview).innerText.includes("## Comment Decision Summary") && qs("[data-review-package-paste-preview-id='github_comment'] [data-review-package-paste-preview-body]", benchmarkPastePreview).innerText.includes("Evidence anchor:") && qs("[data-review-package-paste-preview-id='github_comment'] [data-review-package-paste-preview-body]", benchmarkPastePreview).innerText.includes("First action:") && qs("[data-review-package-paste-preview-id='github_comment'] [data-review-package-paste-preview-body]", benchmarkPastePreview).innerText.includes("Stop condition:") && qs("[data-review-package-paste-preview-id='github_comment'] [data-review-package-paste-preview-body]", benchmarkPastePreview).innerText.includes("## Issue Draft"), "benchmark GitHub comment paste preview body was incomplete");
	    assert(qs("[data-review-package-paste-preview-id='pinned_note'] [data-review-package-paste-preview-body]", benchmarkPastePreview).innerText.includes("## Pinned Note Summary") && qs("[data-review-package-paste-preview-id='pinned_note'] [data-review-package-paste-preview-body]", benchmarkPastePreview).innerText.includes("Evidence anchor:") && qs("[data-review-package-paste-preview-id='pinned_note'] [data-review-package-paste-preview-body]", benchmarkPastePreview).innerText.includes("First action:") && qs("[data-review-package-paste-preview-id='pinned_note'] [data-review-package-paste-preview-body]", benchmarkPastePreview).innerText.includes("Stop condition:") && qs("[data-review-package-paste-preview-id='pinned_note'] [data-review-package-paste-preview-body]", benchmarkPastePreview).innerText.includes("## Issue Draft"), "benchmark pinned note paste preview body was incomplete");
	    assert(benchmarkBundleText.includes("# JooPark PM Benchmark Review Package Bundle") && benchmarkBundleText.includes("## Bundle Manifest") && benchmarkBundleText.includes("## Markdown Handoff") && benchmarkBundleText.includes("## Issue Draft") && benchmarkBundleText.includes("## GitHub Comment Draft") && benchmarkBundleText.includes("## Pinned Note Body"), "benchmark review package bundle sections did not render");
	    assert(benchmarkBundleText.includes("Manifest schema: joopark-review-package-manifest/v1") && benchmarkBundleText.includes("Validation status: pass") && benchmarkBundleText.includes("Payload checksum: fnv1a32-") && benchmarkBundleText.includes("Source freshness: pass (2/2)") && benchmarkBundleText.includes("Paste target readiness: pass (3/3)") && benchmarkBundleText.includes("Ready to submit: pass") && benchmarkBundleText.includes("Final quality score: 6/6") && benchmarkBundleText.includes("Artifact quality rubric: pass (100/100, threshold 90)") && benchmarkBundleText.includes("Decision brief: pass (6/6)") && benchmarkBundleText.includes("Operator quick start: pass (5/5)") && benchmarkBundleText.includes("Quality repairs: none (0)") && benchmarkBundleText.includes("### Decision Brief") && benchmarkBundleText.includes("Review Package Decision Brief") && benchmarkBundleText.includes("Recommendation") && benchmarkBundleText.includes("Evidence anchor") && benchmarkBundleText.includes("Next action") && benchmarkBundleText.includes("### Operator Quick Start") && benchmarkBundleText.includes("Review Package Operator Quick Start") && benchmarkBundleText.includes("Fill external tracker fields") && benchmarkBundleText.includes("Keep bundle proof") && benchmarkBundleText.includes("### Paste-Ready Targets") && benchmarkBundleText.includes("### Artifact Quality Rubric") && benchmarkBundleText.includes("Required form fit") && benchmarkBundleText.includes("Submission flow readiness") && benchmarkBundleText.includes("### Paste Body Preview") && benchmarkBundleText.includes("### Tracker Field Packet") && benchmarkBundleText.includes("Tracker issue body") && benchmarkBundleText.includes("GitHub comment body") && benchmarkBundleText.includes("Pinned note body") && benchmarkBundleText.includes("Tracker issue") && benchmarkBundleText.includes("Pinned note") && benchmarkBundleText.includes("### Final Output Quality Gate") && benchmarkBundleText.includes("### Quality Repair Checklist") && benchmarkBundleText.includes("- [x] No repairs required; package is ready to submit."), "benchmark review package bundle manifest did not include validation evidence");
	    assert(benchmarkBundleText.includes("### Submit Sequence") && benchmarkBundleText.includes("Review Package Submit Sequence"), "benchmark review package bundle did not include submit sequence");
	    assert(benchmarkBundleText.includes("### External Issue Receipt Template") && benchmarkBundleText.includes("External Issue Receipt Template"), "benchmark review package bundle did not include external receipt template");
	    assert(benchmarkBundleText.includes("## JooPark PM Benchmark Review") && benchmarkBundleText.includes("Source URL: https://github.com/Taskosaur/Taskosaur") && benchmarkBundleText.includes("## Decision Summary") && benchmarkBundleText.includes("Recommendation: Taskosaur/Taskosaur") && benchmarkBundleText.includes("Evidence anchor:") && benchmarkBundleText.includes("Stop condition:") && benchmarkBundleText.includes("## Operational Readiness") && benchmarkBundleText.includes("Decision gate:") && benchmarkBundleText.includes("Fallback if blocked:") && benchmarkBundleText.includes("## Acceptance Criteria") && benchmarkBundleText.includes("## Validation Plan"), "benchmark review package bundle did not include execution-quality content");
	    reviewPackagePastePreviewVisibleOk = true;
    window.__smokeClipboardText = "";
    click("[data-benchmark-review-bundle-copy]", reviewHandoff);
    await waitFor(() => reviewHandoff.dataset.reviewBundleCopied === "true" && window.__smokeClipboardText.includes("# JooPark PM Benchmark Review Package Bundle") && window.__smokeClipboardText.includes("## Bundle Manifest") && window.__smokeClipboardText.includes("Payload checksum: fnv1a32-") && window.__smokeClipboardText.includes("Artifact quality rubric: pass (100/100, threshold 90)") && window.__smokeClipboardText.includes("Decision brief: pass (6/6)") && window.__smokeClipboardText.includes("Operator quick start: pass (5/5)") && window.__smokeClipboardText.includes("### Decision Brief") && window.__smokeClipboardText.includes("Review Package Decision Brief") && window.__smokeClipboardText.includes("### Operator Quick Start") && window.__smokeClipboardText.includes("Review Package Operator Quick Start") && window.__smokeClipboardText.includes("### Artifact Quality Rubric") && window.__smokeClipboardText.includes("## GitHub Comment Draft") && window.__smokeClipboardText.includes("## Pinned Note Body"), "benchmark review package bundle copy text did not reach clipboard");
    assert(qs("[data-benchmark-review-bundle-copy-status]", reviewHandoff).textContent.includes("bundle 복사됨"), "benchmark review package bundle copy status did not render");
    const benchmarkReviewResultValidator = qs("[data-review-result-validator]", reviewHandoff);
    await exerciseReviewResultValidator(benchmarkReviewResultValidator, "benchmark-review:repo-taskosaur-taskosaur:86", "Taskosaur/Taskosaur", "benchmark");
    const beforeBenchmarkNoteCount = dashboard.notes.length;
    const benchmarkNotePublish = qs("[data-benchmark-review-note-publish]", reviewHandoff);
    assert(benchmarkNotePublish.textContent.includes("노트 발행") && benchmarkNotePublish.dataset.reviewNoteKey === "benchmark-review:repo-taskosaur-taskosaur:86" && benchmarkNotePublish.dataset.reviewNoteKind === "benchmark-review-note", "benchmark review note publish action did not render");
    click("[data-benchmark-review-note-publish]", reviewHandoff);
    await waitFor(() => dashboard.notes.length === beforeBenchmarkNoteCount + 1, "benchmark review note publish did not create a note");
    const createdBenchmarkNote = dashboard.notes.find((note) => note.sourceKey === "benchmark-review:repo-taskosaur-taskosaur:86");
    assert(createdBenchmarkNote, "benchmark review note publish did not persist source key");
    assert(createdBenchmarkNote.title === "[PM Bench Review] Taskosaur/Taskosaur", "benchmark review note publish title was not saved");
    assert(createdBenchmarkNote.pinned === true, "benchmark review note publish did not pin note");
    assert(createdBenchmarkNote.sourceKind === "benchmark-review-note:validated-review-result", "benchmark review note did not save validated result source kind");
    assert(createdBenchmarkNote.body.includes("## Saved Validated Result") && createdBenchmarkNote.body.includes("## Pinned Note Summary") && createdBenchmarkNote.body.includes("Evidence anchor:") && createdBenchmarkNote.body.includes("First action:") && createdBenchmarkNote.body.includes("Stop condition:") && createdBenchmarkNote.body.includes("Primary decision key: benchmark-review:repo-taskosaur-taskosaur:86") && createdBenchmarkNote.body.includes("Payload checksum: fnv1a32-") && createdBenchmarkNote.body.includes("## Bundle Manifest"), "benchmark validated review note publish body did not render");
    await waitFor(() => {
      const nextHandoff = document.querySelector("[data-benchmark-review-handoff]");
      const nextPublish = document.querySelector("[data-benchmark-review-note-publish]");
      return nextHandoff && nextPublish && nextHandoff.dataset.benchmarkReviewNoteCreated === "true" && nextPublish.dataset.reviewNoteCreated === "true" && nextPublish.dataset.reviewNoteId === createdBenchmarkNote.id;
    }, "benchmark review note publish state did not render");
    await assertReviewArtifactDiff("[data-benchmark-note-review-artifact-diff]", "benchmark-review:repo-taskosaur-taskosaur:86", "benchmark-note", "benchmark note artifact diff", "note");
    const benchmarkNoteOpen = qs("[data-benchmark-review-note-publish]");
    assert(!benchmarkNoteOpen.disabled && benchmarkNoteOpen.textContent.includes("노트 열기") && benchmarkNoteOpen.dataset.reviewNoteCreated === "true" && benchmarkNoteOpen.dataset.reviewNoteId === createdBenchmarkNote.id && benchmarkNoteOpen.dataset.reviewNoteExisting === "true", "benchmark review existing note action was not openable");
    click("[data-benchmark-review-note-publish]");
    await waitFor(() => dashboard.currentView === "notes" && state.noteSourceFilter === "benchmark-review" && document.querySelector("#modal.open #noteForm"), "benchmark review existing note action did not open review note modal");
    const benchmarkNoteSource = qs('#modal.open [data-modal-source-link][data-source-kind="review"][data-source-record-kind="note"][data-source-record-id="' + createdBenchmarkNote.id + '"]');
    assert(qs('#modal.open #noteForm [name="title"]').value === createdBenchmarkNote.title && benchmarkNoteSource && benchmarkNoteSource.dataset.sourceKey === "benchmark-review:repo-taskosaur-taskosaur:86", "benchmark review existing note action opened the wrong note");
    click('[data-action="open-review-record-source"]', benchmarkNoteSource);
    await waitFor(() => dashboard.currentView === "pm-portfolio" && state.portfolioFilter === "candidates" && state.portfolioBenchmarkFilter === "focused" && qs("[data-benchmark-review-handoff]").dataset.reviewHandoffPrimaryKey === "benchmark-review:repo-taskosaur-taskosaur:86" && qs("[data-benchmark-review-handoff]").dataset.reviewSourceReturnRevealed === "true" && !document.querySelector("#modal.open"), "benchmark review note modal source return did not open the original review package");
    await waitFor(() => document.querySelector("[data-benchmark-review-handoff]"), "portfolio did not restore after opening existing benchmark review note");
    reviewBenchmarkNoteModalSourceReturnOk = true;
    reviewHandoff = qs("[data-benchmark-review-handoff]");
    reviewBenchmarkNoteExistingOpenOk = true;
    let reviewIssueDraft = qs("[data-review-issue-draft]", reviewHandoff);
    let reviewIssueCreate = qs("[data-review-issue-create]", reviewIssueDraft);
    let reviewIssueBody = qs("[data-issue-draft-body]", reviewIssueDraft).innerText;
    assert(reviewIssueDraft.dataset.issueDraftTitle === "[Benchmark] Taskosaur/Taskosaur 도입 검토", "benchmark review issue draft title did not render");
    assert(reviewIssueDraft.dataset.issueDraftProject === "Taskosaur/Taskosaur", "benchmark review issue draft project did not render");
    assert(reviewIssueDraft.dataset.issueDraftPriority === "high", "benchmark review issue draft priority did not render");
    assert(reviewIssueDraft.dataset.issueDraftKey === "benchmark-review:repo-taskosaur-taskosaur:86", "benchmark review issue draft key did not render");
    assert(reviewIssueDraft.dataset.issueDraftResultSource === "validated" && reviewIssueDraft.dataset.issueDraftPackageChecksum.startsWith("fnv1a32-"), "benchmark review issue draft did not switch to validated result source");
    assert(reviewIssueDraft.dataset.issueDraftTrackerReady === "true" && reviewIssueDraft.dataset.issueDraftAssignee === "jp" && reviewIssueDraft.dataset.issueDraftDue === todayISO() && reviewIssueDraft.dataset.issueDraftExecutionOwner === "PM", "benchmark review issue draft tracker fields did not render");
    const assigneeDraftDetail = () => " assignee=" + reviewIssueDraft.dataset.issueDraftAssignee
      + " review=" + reviewIssueDraft.dataset.issueDraftAssigneeReview
      + " confidence=" + reviewIssueDraft.dataset.issueDraftAssigneeConfidence
      + " source=" + reviewIssueDraft.dataset.issueDraftAssigneeSource
      + " override=" + reviewIssueDraft.dataset.issueDraftAssigneeOverride
      + " text=" + reviewIssueDraft.innerText.slice(0, 500);
    assert(reviewIssueDraft.dataset.issueDraftAssigneeReview === "true" && reviewIssueDraft.dataset.issueDraftAssigneeConfidence === "medium" && reviewIssueDraft.dataset.issueDraftAssigneeSource === "role-hint", "benchmark review assignee confidence did not render;" + assigneeDraftDetail());
    const reviewAssigneeSelect = qs("[data-issue-draft-assignee-select]", reviewIssueDraft);
    assert(reviewAssigneeSelect.value === "jp", "benchmark review assignee override select did not start from mapped assignee");
    reviewAssigneeSelect.value = "sk";
    reviewAssigneeSelect.dispatchEvent(new Event("change", { bubbles: true }));
    await waitFor(() => reviewIssueDraft.dataset.issueDraftAssignee === "sk" && reviewIssueDraft.dataset.issueDraftAssigneeOverride === "true" && reviewIssueDraft.dataset.issueDraftAssigneeReview === "false" && reviewIssueDraft.dataset.issueDraftAssigneeConfidence === "manual", "benchmark review assignee override did not update draft metadata");
    assert(qs("[data-issue-draft-assignee-review-copy]", reviewIssueDraft).innerText.includes("서기태") && qs("[data-issue-draft-assignee-review-copy]", reviewIssueDraft).innerText.includes("수동 확인"), "benchmark review assignee override status did not render");
    assert(reviewIssueDraft.dataset.issueDraftLabels.includes("assignee-confirmed") && !reviewIssueDraft.dataset.issueDraftLabels.includes("assignee-review") && !reviewIssueDraft.dataset.issueDraftLabels.includes("owner-followup") && reviewIssueDraft.dataset.issueDraftOwnerFollowUpReady === "false", "benchmark review assignee override labels did not update");
    assert(!!reviewIssueDraft.dataset.issueDraftAssigneeOverrideSavedAt, "benchmark review assignee override did not stamp draft persistence metadata");
    const overrideStoredPayload = savedPayload();
    assert(Array.isArray(overrideStoredPayload.reviewIssueDraftOverrides) && overrideStoredPayload.reviewIssueDraftOverrides.some((item) => item && item.key === "benchmark-review:repo-taskosaur-taskosaur:86" && item.assignee === "sk"), "benchmark review assignee override was not persisted before issue creation");
    await nav("pm-kanban");
    await nav("pm-portfolio");
    await waitFor(() => {
      const refreshed = document.querySelector("[data-benchmark-review-handoff] [data-review-issue-draft]");
      return refreshed
        && refreshed.dataset.issueDraftAssignee === "sk"
        && refreshed.dataset.issueDraftAssigneeOverride === "true"
        && refreshed.dataset.issueDraftAssigneeConfidence === "manual"
        && refreshed.dataset.issueDraftAssigneeSource === "manual-override"
        && refreshed.dataset.issueDraftLabels.includes("assignee-confirmed");
    }, "benchmark review assignee override did not survive draft rerender before issue creation");
    reviewIssueDraft = qs("[data-benchmark-review-handoff] [data-review-issue-draft]");
    reviewIssueCreate = qs("[data-review-issue-create]", reviewIssueDraft);
    reviewIssueBody = qs("[data-issue-draft-body]", reviewIssueDraft).innerText;
    assert(qs("[data-issue-draft-assignee-select]", reviewIssueDraft).value === "sk" && qs("[data-issue-draft-assignee-review-copy]", reviewIssueDraft).innerText.includes("서기태"), "benchmark review assignee override select did not survive draft rerender");
    reviewAssigneeOverrideDraftPersistenceOk = true;
    assert(reviewIssueDraft.dataset.issueDraftExecutionChecklistReady === "true" && Number(reviewIssueDraft.dataset.issueDraftExecutionChecklistCount || 0) >= 3, "benchmark review issue draft execution checklist did not render");
    assert(!!qs("[data-issue-draft-validated-source]", reviewIssueDraft), "benchmark review issue draft validated source badge did not render");
    assert(reviewIssueBody.includes("## Validated Review Result") && reviewIssueBody.includes("Source: validated") && reviewIssueBody.includes("reviewResults") && reviewIssueBody.includes("Primary decision key: benchmark-review:repo-taskosaur-taskosaur:86"), "benchmark validated review issue draft body did not render");
    assert(reviewIssueBody.includes("## Bundle Manifest") && reviewIssueBody.includes("Payload checksum: fnv1a32-") && reviewIssueBody.includes("Source freshness: pass"), "benchmark validated review issue draft manifest evidence did not render");
    assert(reviewIssueBody.includes("## Decision Summary") && reviewIssueBody.includes("Recommendation: Taskosaur/Taskosaur") && reviewIssueBody.includes("Why this candidate:") && reviewIssueBody.includes("Comparison context:") && reviewIssueBody.includes("Evidence anchor:") && reviewIssueBody.includes("Stop condition:"), "benchmark validated review issue decision summary did not render");
    assert(reviewIssueBody.includes("## Source Snapshot") && reviewIssueBody.includes("Source URL: https://github.com/Taskosaur/Taskosaur") && reviewIssueBody.includes("## Operational Readiness") && reviewIssueBody.includes("## Execution Checklist") && reviewIssueBody.includes("- [ ] First action:") && reviewIssueBody.includes("Decision gate:") && reviewIssueBody.includes("Fallback if blocked:") && reviewIssueBody.includes("## Acceptance Criteria") && reviewIssueBody.includes("## Validation Plan") && reviewIssueBody.includes("## Missing Evidence To Close"), "benchmark validated review issue draft quality package did not render");
    const beforeIssueCount = dashboard.issues.length;
    click("[data-review-issue-create]", reviewIssueDraft);
    await waitFor(() => dashboard.issues.length === beforeIssueCount + 1, "benchmark review issue draft did not create an issue");
    const createdIssue = dashboard.issues.find((issue) => issue.sourceKey === "benchmark-review:repo-taskosaur-taskosaur:86");
    assert(createdIssue, "benchmark review issue draft did not persist source key");
    assert(createdIssue.title === "[Benchmark] Taskosaur/Taskosaur 도입 검토", "benchmark review issue draft title was not saved");
    assert(createdIssue.project === "repo-taskosaur-taskosaur", "benchmark review issue draft project was not saved");
    assert(createdIssue.priority === "high", "benchmark review issue draft priority was not saved");
    assert(createdIssue.assignee === "sk" && createdIssue.assigneeOverride === true && createdIssue.assigneeConfidence === "manual" && createdIssue.assigneeSource === "manual-override" && createdIssue.assigneeFollowUpReady === false && createdIssue.due === todayISO() && createdIssue.estimate === 4 && createdIssue.executionOwner === "PM", "benchmark review issue tracker fields were not saved");
    assert(Array.isArray(createdIssue.executionChecklist) && createdIssue.executionChecklist.length >= 3 && createdIssue.executionChecklist[0].text.includes("First action"), "benchmark review issue execution checklist was not saved");
    assert(createdIssue.sourceKind === "validated-review-result", "benchmark review issue did not save validated result source kind");
    assert(createdIssue.labels.includes("benchmark") && createdIssue.labels.includes("handoff") && createdIssue.labels.includes("validated-result") && createdIssue.labels.includes("tracker-ready") && createdIssue.labels.includes("checklist-ready") && createdIssue.labels.includes("assignee-confirmed") && !createdIssue.labels.includes("assignee-review") && !createdIssue.labels.includes("owner-followup"), "benchmark review issue draft labels were not saved");
    assert(createdIssue.body.includes("## Validated Review Result") && createdIssue.body.includes("Payload checksum: fnv1a32-") && createdIssue.body.includes("## Decision Summary") && createdIssue.body.includes("Recommendation: Taskosaur/Taskosaur") && createdIssue.body.includes("Evidence anchor:") && createdIssue.body.includes("## Operational Readiness") && createdIssue.body.includes("## Execution Checklist") && createdIssue.body.includes("Decision gate:") && createdIssue.body.includes("Fallback if blocked:") && createdIssue.body.includes("## Acceptance Criteria") && createdIssue.body.includes("## Validation Plan") && createdIssue.body.includes("Source URL: https://github.com/Taskosaur/Taskosaur"), "benchmark validated review issue package was not saved");
    assert(!createdIssue.body.includes("## Assignee Follow-up"), "benchmark manually confirmed review issue kept stale assignee follow-up body");
    reviewResultIssueAppliedOk = true;
    await waitFor(() => {
      const nextDraft = document.querySelector("[data-benchmark-review-handoff] [data-review-issue-draft]");
      return nextDraft && nextDraft.dataset.issueDraftCreated === "true" && nextDraft.dataset.issueDraftId === createdIssue.id;
    }, "benchmark review issue draft created state did not render");
    await assertReviewArtifactDiff("[data-benchmark-issue-review-artifact-diff]", "benchmark-review:repo-taskosaur-taskosaur:86", "benchmark-issue", "benchmark issue artifact diff", "issue");
    dashboard.currentProjectId = createdIssue.project;
    await nav("pm-kanban");
    const kanbanChecklist = qs('[data-issue-id="' + createdIssue.id + '"] [data-kanban-execution-checklist]');
    assert(kanbanChecklist.dataset.executionChecklistCount === String(createdIssue.executionChecklist.length), "benchmark review kanban execution checklist did not render");
    assert(kanbanChecklist.innerText.includes("실행") && kanbanChecklist.innerText.includes("First action"), "benchmark review kanban execution checklist preview was incomplete");
    assert(kanbanChecklist.dataset.executionChecklistDoneCount === "0" && kanbanChecklist.dataset.executionChecklistProgressPercent === "0", "benchmark review kanban execution checklist progress did not start empty");
    click('[data-issue-id="' + createdIssue.id + '"] [data-action="open-issue"]');
    await waitFor(() => !!document.querySelector("#sheet.open [data-issue-execution-checklist]"), "benchmark review issue sheet checklist did not open");
    const sheetChecklist = qs("[data-issue-execution-checklist]");
    assert(sheetChecklist.dataset.executionChecklistCount === String(createdIssue.executionChecklist.length) && sheetChecklist.dataset.executionChecklistDoneCount === "0", "benchmark review issue sheet checklist progress did not render");
    assert(sheetChecklist.dataset.issueExecutionChecklistView === "review-result-view" && sheetChecklist.querySelectorAll(".sheet-execution-progress strong").length === 1, "benchmark review issue sheet checklist view boundary did not render clean progress");
    click("[data-execution-checklist-toggle]", sheetChecklist);
    await waitFor(() => createdIssue.executionChecklist[0].done === true, "benchmark review issue checklist toggle did not persist");
    const updatedSheetChecklist = qs("[data-issue-execution-checklist]");
    const expectedProgress = String(Math.round((1 / createdIssue.executionChecklist.length) * 100));
    assert(updatedSheetChecklist.dataset.executionChecklistDoneCount === "1" && updatedSheetChecklist.dataset.executionChecklistProgressPercent === expectedProgress, "benchmark review issue sheet checklist progress did not update");
    assert(updatedSheetChecklist.dataset.issueExecutionChecklistView === "review-result-view" && updatedSheetChecklist.querySelectorAll(".sheet-execution-progress strong").length === 1, "benchmark review issue sheet checklist progress rendered duplicate values after toggle");
    assert(createdIssue.body.includes("- [x] First action:"), "benchmark review issue checklist markdown did not sync after toggle");
    const persistedChecklistIssue = savedPayload().issues.find((issue) => issue.id === createdIssue.id);
    assert(persistedChecklistIssue && persistedChecklistIssue.executionChecklist[0] && persistedChecklistIssue.executionChecklist[0].done === true, "benchmark review issue checklist sheet toggle was not persisted");
    const freshReceipt = qs("[data-issue-fresh-receipt]");
    assert(freshReceipt.dataset.reviewArtifactFreshReceiptStatus === "pass" && freshReceipt.dataset.reviewArtifactFreshReceiptPassCount === "8" && freshReceipt.dataset.reviewArtifactFreshReceiptProgressPercent === expectedProgress, "benchmark review issue fresh receipt did not render pass state after checklist progress");
    assert(freshReceipt.dataset.issueFreshReceiptView === "review-artifact-view", "benchmark review issue fresh receipt view boundary did not render");
    const freshReceiptDownload = qs("[data-issue-fresh-receipt-download]", freshReceipt);
    assert(freshReceiptDownload.getAttribute("download") === "joopark-benchmark-issue-fresh-receipt.md" && freshReceiptDownload.getAttribute("href").startsWith("data:text/markdown;charset=utf-8,"), "benchmark review issue fresh receipt download did not render");
    window.__smokeClipboardText = "";
    click("[data-issue-fresh-receipt-copy]", freshReceipt);
    await waitFor(() => freshReceipt.dataset.issueFreshReceiptCopied === "true" && window.__smokeClipboardText.includes("# JooPark Review Artifact Receipt"), "benchmark review issue fresh receipt copy did not reach clipboard");
    assert(window.__smokeClipboardText.includes(createdIssue.id) && window.__smokeClipboardText.includes("benchmark-review:repo-taskosaur-taskosaur:86") && window.__smokeClipboardText.includes("Diff status: pass") && window.__smokeClipboardText.includes("- [x] First action:") && window.__smokeClipboardText.includes("## Repair Evidence"), "benchmark review issue fresh receipt did not include progressed body");
    const updatedKanbanChecklist = qs('[data-issue-id="' + createdIssue.id + '"] [data-kanban-execution-checklist]');
    assert(updatedKanbanChecklist.dataset.executionChecklistDoneCount === "1" && updatedKanbanChecklist.dataset.executionChecklistProgressPercent === expectedProgress && updatedKanbanChecklist.innerText.includes("실행 1/"), "benchmark review kanban checklist progress did not update");
    click('#sheet [data-action="close-sheet"]');
    await waitFor(() => !document.querySelector("#sheet.open"), "benchmark review issue checklist sheet did not close");
    const kanbanToggleBefore = qs('[data-issue-id="' + createdIssue.id + '"] [data-kanban-execution-toggle]');
    assert(kanbanToggleBefore.dataset.checklistId === "exec-2", "benchmark review kanban checklist did not expose the next incomplete item");
    click('[data-issue-id="' + createdIssue.id + '"] [data-kanban-execution-toggle]');
    await waitFor(() => createdIssue.executionChecklist.filter((item) => item.done).length === 2, "benchmark review kanban checklist toggle did not persist");
    const kanbanChecklistAfterToggle = qs('[data-issue-id="' + createdIssue.id + '"] [data-kanban-execution-checklist]');
    assert(kanbanChecklistAfterToggle.dataset.executionChecklistDoneCount === "2" && kanbanChecklistAfterToggle.innerText.includes("실행 2/"), "benchmark review kanban checklist progress did not update after card toggle");
    assert(!document.querySelector("#sheet.open"), "benchmark review kanban checklist toggle unexpectedly opened the issue sheet");
    const persistedChecklistAfterKanban = savedPayload().issues.find((issue) => issue.id === createdIssue.id);
    assert(persistedChecklistAfterKanban && persistedChecklistAfterKanban.executionChecklist.filter((item) => item.done).length === 2, "benchmark review kanban checklist toggle was not persisted");
    const reviewDirectSourceBadge = qs('#view-pm-kanban [data-issue-id="' + createdIssue.id + '"] [data-kanban-source-direct-return="true"]');
    const reviewSourceBadgeDetail = " tag=" + reviewDirectSourceBadge.tagName
      + " action=" + (reviewDirectSourceBadge.dataset.action || "")
      + " text=" + reviewDirectSourceBadge.textContent.trim()
      + " full=" + (reviewDirectSourceBadge.dataset.kanbanSourceFullLabel || "")
      + " sourceKind=" + (createdIssue.sourceKind || "")
      + " sourceKey=" + (createdIssue.sourceKey || "")
      + " html=" + reviewDirectSourceBadge.outerHTML.slice(0, 500);
    assert(reviewDirectSourceBadge.tagName === "BUTTON" && reviewDirectSourceBadge.dataset.action === "open-issue-source" && reviewDirectSourceBadge.textContent.includes("PM Bench") && reviewDirectSourceBadge.dataset.kanbanSourceFullLabel === "PM Bench Review" && reviewDirectSourceBadge.getAttribute("aria-label").includes("PM Bench Review"), "benchmark review source badge did not expose direct source return button;" + reviewSourceBadgeDetail);
    kanbanReviewFamilyBadgeOk = true;
    click('#view-pm-kanban [data-action="filter-kanban-source"][data-kanban-source-filter="benchmark-review"]');
    await waitFor(() => qs('#view-pm-kanban [data-kanban-source-filterbar]').dataset.kanbanSourceFilterCurrent === "benchmark-review", "benchmark review family source filter did not activate");
    const benchmarkReviewSummary = qs('#view-pm-kanban [data-kanban-source-summary]');
    assert(benchmarkReviewSummary.dataset.kanbanSourceSummaryFilter === "benchmark-review" && benchmarkReviewSummary.textContent.includes("PM Bench") && benchmarkReviewSummary.textContent.includes("1건"), "benchmark review family source summary did not render");
    assert(qs('#view-pm-kanban [data-issue-id="' + createdIssue.id + '"]') && qsa('#view-pm-kanban [data-search-result="pm-kanban"]').every((card) => String(card.dataset.issueSourceKey || "").startsWith("benchmark-review:")), "benchmark review family source filter did not isolate PM Bench review issues");
    click('[data-action="open-palette"]');
    fill("#paletteInput", "Kanban PM Bench Review");
    await waitFor(() => qsa("#paletteResults .pal-item").some((item) => item.textContent.includes("Kanban: PM Bench Review 출처 보기")), "benchmark review family source filter command did not render in palette");
    qsa("#paletteResults .pal-item").find((item) => item.textContent.includes("Kanban: PM Bench Review 출처 보기")).click();
    await waitFor(() => dashboard.currentView === "pm-kanban" && qs('#view-pm-kanban [data-kanban-source-filterbar]').dataset.kanbanSourceFilterCurrent === "benchmark-review", "benchmark review family source palette command did not apply PM Bench filter");
    kanbanReviewFamilyFilterOk = true;
    click('[data-action="open-palette"]');
    fill("#paletteInput", "칸반 워크스페이스 리뷰 출처");
    await waitFor(() => qsa("#paletteResults .pal-item").some((item) => item.textContent.includes("Kanban: Workspace Review 출처 보기")), "workspace review Korean family source filter command did not render in palette");
    qsa("#paletteResults .pal-item").find((item) => item.textContent.includes("Kanban: Workspace Review 출처 보기")).click();
    await waitFor(() => dashboard.currentView === "pm-kanban" && qs('#view-pm-kanban [data-kanban-source-filterbar]').dataset.kanbanSourceFilterCurrent === "workspace-review", "workspace review Korean family source palette command did not apply Workspace filter");
    assert(qs('#view-pm-kanban [data-issue-id="' + createdWorkspaceIssue.id + '"]') && qsa('#view-pm-kanban [data-search-result="pm-kanban"]').every((card) => String(card.dataset.issueSourceKey || "").startsWith("workspace-review:")), "workspace review Korean family source palette command did not isolate Workspace review issues");
    click('[data-action="open-palette"]');
    fill("#paletteInput", "칸반 지식 베이스 리뷰 출처");
    await waitFor(() => qsa("#paletteResults .pal-item").some((item) => item.textContent.includes("Kanban: KB/IA Review 출처 보기")), "KB/IA review Korean family source filter command did not render in palette");
    qsa("#paletteResults .pal-item").find((item) => item.textContent.includes("Kanban: KB/IA Review 출처 보기")).click();
    await waitFor(() => dashboard.currentView === "pm-kanban" && qs('#view-pm-kanban [data-kanban-source-filterbar]').dataset.kanbanSourceFilterCurrent === "kb-ia-review", "KB/IA review Korean family source palette command did not apply KB/IA filter");
    assert(qs('#view-pm-kanban [data-issue-id="' + createdKbIssue.id + '"]') && qsa('#view-pm-kanban [data-search-result="pm-kanban"]').every((card) => String(card.dataset.issueSourceKey || "").startsWith("kb-ia-review:")), "KB/IA review Korean family source palette command did not isolate KB/IA review issues");
    click('[data-action="open-palette"]');
    fill("#paletteInput", "칸반 벤치마크 리뷰 출처");
    await waitFor(() => qsa("#paletteResults .pal-item").some((item) => item.textContent.includes("Kanban: PM Bench Review 출처 보기")), "benchmark review Korean family source filter command did not render in palette");
    qsa("#paletteResults .pal-item").find((item) => item.textContent.includes("Kanban: PM Bench Review 출처 보기")).click();
    await waitFor(() => dashboard.currentView === "pm-kanban" && qs('#view-pm-kanban [data-kanban-source-filterbar]').dataset.kanbanSourceFilterCurrent === "benchmark-review", "benchmark review Korean family source palette command did not apply PM Bench filter");
    assert(qs('#view-pm-kanban [data-issue-id="' + createdIssue.id + '"]') && qsa('#view-pm-kanban [data-search-result="pm-kanban"]').every((card) => String(card.dataset.issueSourceKey || "").startsWith("benchmark-review:")), "benchmark review Korean family source palette command did not isolate PM Bench review issues");
    click('[data-action="open-palette"]');
    fill("#paletteInput", "칸반 리뷰 출처");
    await waitFor(() => qsa("#paletteResults .pal-item").some((item) => item.textContent.includes("Kanban: Review 출처 보기")), "review Korean roll-up Kanban source filter command did not render in palette");
    qsa("#paletteResults .pal-item").find((item) => item.textContent.includes("Kanban: Review 출처 보기")).click();
    await waitFor(() => dashboard.currentView === "pm-kanban" && qs('#view-pm-kanban [data-kanban-source-filterbar]').dataset.kanbanSourceFilterCurrent === "review", "review Korean roll-up Kanban source palette command did not apply Review filter");
    const kanbanReviewCards = qsa('#view-pm-kanban [data-search-result="pm-kanban"]');
    assert(kanbanReviewCards.length >= 1 && kanbanReviewCards.every((card) => {
      const sourceKey = String(card.dataset.issueSourceKey || "");
      return card.dataset.issueSourceKind === "validated-review-result"
        || sourceKey.startsWith("workspace-review:")
        || sourceKey.startsWith("kb-ia-review:")
        || sourceKey.startsWith("benchmark-review:");
    }), "review Korean roll-up Kanban source palette command did not isolate review issues");
    kanbanReviewKoreanFamilyFilterCommandOk = true;
    qs('#view-pm-kanban [data-issue-id="' + createdIssue.id + '"] [data-kanban-source-direct-return="true"]').click();
    await waitFor(() => dashboard.currentView === "pm-portfolio" && state.portfolioFilter === "candidates" && state.portfolioBenchmarkFilter === "focused" && qs("[data-benchmark-review-handoff]").dataset.reviewHandoffPrimaryKey === "benchmark-review:repo-taskosaur-taskosaur:86" && qs("[data-benchmark-review-handoff]").dataset.reviewSourceReturnRevealed === "true", "benchmark review direct source badge did not open the original review package");
    const reviewBacklink = qs('[data-source-backlink][data-source-backlink-surface="review"]');
    assert(reviewBacklink.dataset.sourceBacklinkIssueId === createdIssue.id && reviewBacklink.textContent.includes(createdIssue.id) && reviewBacklink.textContent.includes("Kanban 이슈로 돌아가기"), "benchmark review source backlink did not render the originating issue");
    click('[data-action="open-source-backlink-issue"]', reviewBacklink);
    await waitFor(() => dashboard.currentView === "pm-kanban" && qs('#view-pm-kanban [data-kanban-source-filterbar]').dataset.kanbanSourceFilterCurrent === "benchmark-review" && qs('#sheet.open [data-action="open-issue-source"]'), "benchmark review source backlink did not reopen the originating kanban issue");
    assert(qs("#sheet.open").textContent.includes(createdIssue.id), "benchmark review source backlink opened the wrong issue sheet");
    click('#sheet [data-action="close-sheet"]');
    await waitFor(() => !document.querySelector("#sheet.open"), "benchmark review source backlink sheet did not close");
    issueSourceBacklinkReviewOk = true;
    await nav("pm-kanban");
    await waitFor(() => qs('#view-pm-kanban [data-issue-id="' + createdIssue.id + '"] [data-action="open-issue"]'), "benchmark review issue did not return to kanban after direct source return");
    click('[data-issue-id="' + createdIssue.id + '"] [data-action="open-issue"]');
    await waitFor(() => document.querySelector('#sheet.open [data-action="open-issue-source"]'), "benchmark review issue sheet did not expose source return action");
    const reviewSourceReturn = qs('#sheet.open [data-action="open-issue-source"]');
    assert(reviewSourceReturn.textContent.includes("PM benchmark") && reviewSourceReturn.textContent.includes("패키지"), "benchmark review source return action label was incomplete");
    reviewSourceReturn.click();
    await waitFor(() => dashboard.currentView === "pm-portfolio" && state.portfolioFilter === "candidates" && state.portfolioBenchmarkFilter === "focused" && qs("[data-benchmark-review-handoff]").dataset.reviewHandoffPrimaryKey === "benchmark-review:repo-taskosaur-taskosaur:86" && qs("[data-benchmark-review-handoff]").dataset.reviewSourceReturnRevealed === "true", "benchmark review source return did not open the original review package");
    const returnedReviewHandoff = qs('[data-benchmark-review-handoff][data-review-source-return-revealed="true"]');
    click('[data-review-issue-create]', returnedReviewHandoff);
    await waitFor(() => dashboard.currentView === "pm-kanban" && qs('#view-pm-kanban [data-kanban-source-filterbar]').dataset.kanbanSourceFilterCurrent === "benchmark-review" && qs('#sheet.open [data-action="open-issue-source"]'), "benchmark review duplicate issue action did not open existing kanban issue");
    assert(qs("#sheet.open").textContent.includes(createdIssue.id) && savedPayload().issues.filter((issue) => issue.sourceKey === "benchmark-review:repo-taskosaur-taskosaur:86").length === 1, "benchmark review duplicate issue action opened the wrong issue or created a duplicate");
    click('#sheet [data-action="close-sheet"]');
    await waitFor(() => !document.querySelector("#sheet.open"), "benchmark review duplicate issue sheet did not close");
    click('[data-action="open-palette"]');
    fill("#paletteInput", "Review 출처");
    await waitFor(() => {
      const items = qsa("#paletteResults .pal-item");
      return items.some((item) => item.textContent.includes(createdIssue.title) && item.textContent.includes(createdIssue.id) && item.textContent.includes("PM Bench Review"))
        && items.some((item) => item.textContent.includes(createdWorkspaceNote.title) && item.textContent.includes("메모") && item.textContent.includes("Workspace Review"))
        && items.some((item) => item.textContent.includes(createdKbNote.title) && item.textContent.includes("메모") && item.textContent.includes("KB/IA Review"));
    }, "review source label search did not render sourced palette records");
    qsa("#paletteResults .pal-item").find((item) => item.textContent.includes(createdWorkspaceNote.title) && item.textContent.includes("메모") && item.textContent.includes("Workspace Review")).click();
    await waitFor(() => dashboard.currentView === "notes" && state.noteSourceFilter === "workspace-review" && document.querySelector("#modal.open #noteForm"), "review source label palette result did not open review note modal");
    assert(qs('#modal.open #noteForm [name="title"]').value === createdWorkspaceNote.title, "review source label palette result opened the wrong note");
    const reviewNoteSource = qs('#modal.open [data-modal-source-link][data-source-kind="review"][data-source-record-kind="note"][data-source-record-id="' + createdWorkspaceNote.id + '"]');
    assert(reviewNoteSource.dataset.sourceKey === "workspace-review:repo-toeverything-affine:86" && reviewNoteSource.textContent.includes("Workspace review") && reviewNoteSource.textContent.includes("패키지"), "review note modal source return panel did not render");
    click('[data-action="open-review-record-source"]', reviewNoteSource);
    await waitFor(() => dashboard.currentView === "pm-portfolio" && state.portfolioFilter === "candidates" && state.portfolioBenchmarkFilter === "focused" && qs("[data-workspace-review-handoff]").dataset.workspaceReviewHandoffPrimaryKey === "workspace-review:repo-toeverything-affine:86" && qs("[data-workspace-review-handoff]").dataset.reviewSourceReturnRevealed === "true" && !document.querySelector("#modal.open"), "review note source return did not open the original review package");
    await nav("notes");
    await waitFor(() => state.noteSourceFilter === "workspace-review" && qs('#view-notes [data-note-source-filterbar]').dataset.noteSourceFilterCurrent === "workspace-review" && document.querySelector('#view-notes [data-action="open-review-record-source"][data-source-record-kind="note"][data-source-record-id="' + createdWorkspaceNote.id + '"]'), "review note source filter did not restore workspace review scope");
    let reviewNoteFilterbar = qs('#view-notes [data-note-source-filterbar]');
    assert(qs('[data-note-source-filter="workspace-review"]', reviewNoteFilterbar).dataset.noteSourceFilterCount === "1" && qsa('#view-notes [data-search-result="notes"]').length === 1 && qsa('#view-notes [data-search-result="notes"]').every((card) => card.querySelector('[data-action="open-review-record-source"][data-source-key^="workspace-review:"]')), "workspace review note source filter did not isolate workspace review notes");
    click('[data-action="note-source-filter"][data-note-source-filter="all"]', reviewNoteFilterbar);
    await waitFor(() => state.noteSourceFilter === "all" && qs('#view-notes [data-note-source-filterbar]').dataset.noteSourceFilterCurrent === "all", "review note source filter did not reset to all");
    reviewNoteFilterbar = qs('#view-notes [data-note-source-filterbar]');
    click('[data-action="note-source-filter"][data-note-source-filter="review"]', reviewNoteFilterbar);
    await waitFor(() => state.noteSourceFilter === "review" && qs('#view-notes [data-note-source-filterbar]').dataset.noteSourceFilterCurrent === "review" && qsa('#view-notes [data-search-result="notes"]').every((card) => card.querySelector('[data-action="open-review-record-source"][data-source-kind="review"]')), "review note source filter did not reapply review scope");
    assert(Number(qs('[data-note-source-filter="review"]', qs('#view-notes [data-note-source-filterbar]')).dataset.noteSourceFilterCount || "0") >= 2, "review note roll-up source filter did not count review notes");
    const reviewNoteCardSource = qs('#view-notes [data-action="open-review-record-source"][data-source-record-kind="note"][data-source-record-id="' + createdWorkspaceNote.id + '"]');
    assert(reviewNoteCardSource.dataset.sourceKey === "workspace-review:repo-toeverything-affine:86" && reviewNoteCardSource.textContent.includes("Workspace") && reviewNoteCardSource.dataset.reviewSourceShortLabel === "Workspace" && reviewNoteCardSource.getAttribute("aria-label").includes("Workspace review"), "review note card source badge metadata was incomplete");
    const kbReviewNoteCardSource = qs('#view-notes [data-action="open-review-record-source"][data-source-record-kind="note"][data-source-record-id="' + createdKbNote.id + '"]');
    assert(kbReviewNoteCardSource.dataset.sourceKey === "kb-ia-review:repo-outline-outline:87" && kbReviewNoteCardSource.textContent.includes("KB/IA") && kbReviewNoteCardSource.dataset.reviewSourceShortLabel === "KB/IA" && kbReviewNoteCardSource.getAttribute("aria-label").includes("KB/IA review"), "knowledge-base review note card source badge metadata was incomplete");
    const benchmarkReviewNoteCardSource = qs('#view-notes [data-action="open-review-record-source"][data-source-record-kind="note"][data-source-record-id="' + createdBenchmarkNote.id + '"]');
    assert(benchmarkReviewNoteCardSource.dataset.sourceKey === "benchmark-review:repo-taskosaur-taskosaur:86" && benchmarkReviewNoteCardSource.textContent.includes("PM Bench") && benchmarkReviewNoteCardSource.dataset.reviewSourceShortLabel === "PM Bench" && benchmarkReviewNoteCardSource.getAttribute("aria-label").includes("PM benchmark review"), "benchmark review note card source badge metadata was incomplete");
    reviewNoteCardFamilyLabelOk = true;
    click('[data-action="note-source-filter"][data-note-source-filter="kb-ia-review"]', qs('#view-notes [data-note-source-filterbar]'));
    await waitFor(() => state.noteSourceFilter === "kb-ia-review" && qs('#view-notes [data-note-source-filterbar]').dataset.noteSourceFilterCurrent === "kb-ia-review" && qsa('#view-notes [data-search-result="notes"]').length === 1 && qsa('#view-notes [data-search-result="notes"]').every((card) => card.querySelector('[data-action="open-review-record-source"][data-source-key^="kb-ia-review:"]')), "knowledge-base review note source filter did not isolate KB/IA review notes");
    click('[data-action="open-palette"]');
    fill("#paletteInput", "메모 KB/IA Review 출처");
    await waitFor(() => qsa("#paletteResults .pal-item").some((item) => item.textContent.includes("메모: KB/IA Review 출처 보기")), "knowledge-base review note source filter command did not render in palette");
    qsa("#paletteResults .pal-item").find((item) => item.textContent.includes("메모: KB/IA Review 출처 보기")).click();
    await waitFor(() => dashboard.currentView === "notes" && state.noteSourceFilter === "kb-ia-review" && qs('#view-notes [data-note-source-filterbar]').dataset.noteSourceFilterCurrent === "kb-ia-review", "knowledge-base review note source palette command did not apply KB/IA filter");
    assert(qsa('#view-notes [data-search-result="notes"]').length === 1 && qsa('#view-notes [data-search-result="notes"]').every((card) => card.querySelector('[data-action="open-review-record-source"][data-source-key^="kb-ia-review:"]')), "knowledge-base review note source palette command did not isolate KB/IA review notes");
    click('[data-action="note-source-filter"][data-note-source-filter="benchmark-review"]', qs('#view-notes [data-note-source-filterbar]'));
    await waitFor(() => state.noteSourceFilter === "benchmark-review" && qs('#view-notes [data-note-source-filterbar]').dataset.noteSourceFilterCurrent === "benchmark-review" && qsa('#view-notes [data-search-result="notes"]').length === 1 && qsa('#view-notes [data-search-result="notes"]').every((card) => card.querySelector('[data-action="open-review-record-source"][data-source-key^="benchmark-review:"]')), "benchmark review note source filter did not isolate PM Bench review notes");
    click('[data-action="open-palette"]');
    fill("#paletteInput", "메모 PM Bench Review 출처");
    await waitFor(() => qsa("#paletteResults .pal-item").some((item) => item.textContent.includes("메모: PM Bench Review 출처 보기")), "benchmark review note source filter command did not render in palette");
    qsa("#paletteResults .pal-item").find((item) => item.textContent.includes("메모: PM Bench Review 출처 보기")).click();
    await waitFor(() => dashboard.currentView === "notes" && state.noteSourceFilter === "benchmark-review" && qs('#view-notes [data-note-source-filterbar]').dataset.noteSourceFilterCurrent === "benchmark-review", "benchmark review note source palette command did not apply PM Bench filter");
    assert(qsa('#view-notes [data-search-result="notes"]').length === 1 && qsa('#view-notes [data-search-result="notes"]').every((card) => card.querySelector('[data-action="open-review-record-source"][data-source-key^="benchmark-review:"]')), "benchmark review note source palette command did not isolate PM Bench review notes");
    click('[data-action="open-palette"]');
    fill("#paletteInput", "메모 워크스페이스 리뷰 출처");
    await waitFor(() => qsa("#paletteResults .pal-item").some((item) => item.textContent.includes("메모: Workspace Review 출처 보기")), "workspace review Korean note source filter command did not render in palette");
    qsa("#paletteResults .pal-item").find((item) => item.textContent.includes("메모: Workspace Review 출처 보기")).click();
    await waitFor(() => dashboard.currentView === "notes" && state.noteSourceFilter === "workspace-review" && qs('#view-notes [data-note-source-filterbar]').dataset.noteSourceFilterCurrent === "workspace-review", "workspace review Korean note source palette command did not apply Workspace filter");
    assert(qsa('#view-notes [data-search-result="notes"]').length === 1 && qsa('#view-notes [data-search-result="notes"]').every((card) => card.querySelector('[data-action="open-review-record-source"][data-source-key^="workspace-review:"]')), "workspace review Korean note source palette command did not isolate Workspace review notes");
    click('[data-action="open-palette"]');
    fill("#paletteInput", "메모 지식 베이스 리뷰 출처");
    await waitFor(() => qsa("#paletteResults .pal-item").some((item) => item.textContent.includes("메모: KB/IA Review 출처 보기")), "KB/IA review Korean note source filter command did not render in palette");
    qsa("#paletteResults .pal-item").find((item) => item.textContent.includes("메모: KB/IA Review 출처 보기")).click();
    await waitFor(() => dashboard.currentView === "notes" && state.noteSourceFilter === "kb-ia-review" && qs('#view-notes [data-note-source-filterbar]').dataset.noteSourceFilterCurrent === "kb-ia-review", "KB/IA review Korean note source palette command did not apply KB/IA filter");
    assert(qsa('#view-notes [data-search-result="notes"]').length === 1 && qsa('#view-notes [data-search-result="notes"]').every((card) => card.querySelector('[data-action="open-review-record-source"][data-source-key^="kb-ia-review:"]')), "KB/IA review Korean note source palette command did not isolate KB/IA review notes");
    click('[data-action="open-palette"]');
    fill("#paletteInput", "메모 벤치마크 리뷰 출처");
    await waitFor(() => qsa("#paletteResults .pal-item").some((item) => item.textContent.includes("메모: PM Bench Review 출처 보기")), "benchmark review Korean note source filter command did not render in palette");
    qsa("#paletteResults .pal-item").find((item) => item.textContent.includes("메모: PM Bench Review 출처 보기")).click();
    await waitFor(() => dashboard.currentView === "notes" && state.noteSourceFilter === "benchmark-review" && qs('#view-notes [data-note-source-filterbar]').dataset.noteSourceFilterCurrent === "benchmark-review", "benchmark review Korean note source palette command did not apply PM Bench filter");
    assert(qsa('#view-notes [data-search-result="notes"]').length === 1 && qsa('#view-notes [data-search-result="notes"]').every((card) => card.querySelector('[data-action="open-review-record-source"][data-source-key^="benchmark-review:"]')), "benchmark review Korean note source palette command did not isolate PM Bench review notes");
    reviewNoteKoreanFamilyFilterCommandOk = true;
    reviewBenchmarkNoteFamilyFilterOk = true;
    qs('#view-notes [data-action="open-review-record-source"][data-source-record-kind="note"][data-source-record-id="' + createdBenchmarkNote.id + '"]').click();
    await waitFor(() => dashboard.currentView === "pm-portfolio" && state.portfolioFilter === "candidates" && state.portfolioBenchmarkFilter === "focused" && qs("[data-benchmark-review-handoff]").dataset.reviewHandoffPrimaryKey === "benchmark-review:repo-taskosaur-taskosaur:86" && qs("[data-benchmark-review-handoff]").dataset.reviewSourceReturnRevealed === "true", "benchmark review note card source return did not open the original review package");
    reviewBenchmarkNoteCardSourceReturnOk = true;
    await nav("notes");
    await waitFor(() => state.noteSourceFilter === "benchmark-review" && qs('#view-notes [data-note-source-filterbar]').dataset.noteSourceFilterCurrent === "benchmark-review", "benchmark review note source filter did not restore after source return");
    click('[data-action="note-source-filter"][data-note-source-filter="workspace-review"]', qs('#view-notes [data-note-source-filterbar]'));
    await waitFor(() => state.noteSourceFilter === "workspace-review" && qs('#view-notes [data-note-source-filterbar]').dataset.noteSourceFilterCurrent === "workspace-review" && document.querySelector('#view-notes [data-action="open-review-record-source"][data-source-record-kind="note"][data-source-record-id="' + createdWorkspaceNote.id + '"]'), "workspace review note source filter did not reapply workspace review scope");
    reviewNoteFamilyFilterOk = true;
    qs('#view-notes [data-action="open-review-record-source"][data-source-record-kind="note"][data-source-record-id="' + createdWorkspaceNote.id + '"]').click();
    await waitFor(() => dashboard.currentView === "pm-portfolio" && state.portfolioFilter === "candidates" && state.portfolioBenchmarkFilter === "focused" && qs("[data-workspace-review-handoff]").dataset.workspaceReviewHandoffPrimaryKey === "workspace-review:repo-toeverything-affine:86" && qs("[data-workspace-review-handoff]").dataset.reviewSourceReturnRevealed === "true", "review note card source return did not open the original review package");
    click('[data-action="open-palette"]');
    fill("#paletteInput", "메모 Review 출처");
    await waitFor(() => qsa("#paletteResults .pal-item").some((item) => item.textContent.includes("메모: Review 출처 보기")), "review note source filter command did not render in palette");
    qsa("#paletteResults .pal-item").find((item) => item.textContent.includes("메모: Review 출처 보기")).click();
    await waitFor(() => dashboard.currentView === "notes" && state.noteSourceFilter === "review" && qs('#view-notes [data-note-source-filterbar]').dataset.noteSourceFilterCurrent === "review", "review note source palette command did not apply review filter");
    assert(qsa('#view-notes [data-search-result="notes"]').length >= 1 && qsa('#view-notes [data-search-result="notes"]').every((card) => card.querySelector('[data-action="open-review-record-source"][data-source-kind="review"]')), "review note source palette command did not isolate review notes");
    click('[data-action="open-palette"]');
    fill("#paletteInput", "메모 리뷰 출처");
    await waitFor(() => qsa("#paletteResults .pal-item").some((item) => item.textContent.includes("메모: Review 출처 보기")), "review Korean roll-up note source filter command did not render in palette");
    qsa("#paletteResults .pal-item").find((item) => item.textContent.includes("메모: Review 출처 보기")).click();
    await waitFor(() => dashboard.currentView === "notes" && state.noteSourceFilter === "review" && qs('#view-notes [data-note-source-filterbar]').dataset.noteSourceFilterCurrent === "review", "review Korean roll-up note source palette command did not apply Review filter");
    assert(qsa('#view-notes [data-search-result="notes"]').length >= 1 && qsa('#view-notes [data-search-result="notes"]').every((card) => card.querySelector('[data-action="open-review-record-source"][data-source-kind="review"]')), "review Korean roll-up note source palette command did not isolate review notes");
    reviewKoreanRollupSourceFilterCommandOk = true;
    click('[data-action="open-palette"]');
    fill("#paletteInput", "Review 출처");
    await waitFor(() => {
      const items = qsa("#paletteResults .pal-item");
      return items.some((item) => item.textContent.includes(createdIssue.title) && item.textContent.includes(createdIssue.id) && item.textContent.includes("Review"))
        && items.some((item) => item.textContent.includes(createdBenchmarkNote.title) && item.textContent.includes("메모") && item.textContent.includes("PM Bench Review"));
    }, "review source label search did not render sourced palette issue and PM Bench note after note open");
    qsa("#paletteResults .pal-item").find((item) => item.textContent.includes(createdBenchmarkNote.title) && item.textContent.includes("메모") && item.textContent.includes("PM Bench Review")).click();
    await waitFor(() => dashboard.currentView === "notes" && state.noteSourceFilter === "benchmark-review" && document.querySelector("#modal.open #noteForm"), "review source label palette result did not open PM Bench review note modal");
    const benchmarkPaletteNoteSource = qs('#modal.open [data-modal-source-link][data-source-kind="review"][data-source-record-kind="note"][data-source-record-id="' + createdBenchmarkNote.id + '"]');
    assert(qs('#modal.open #noteForm [name="title"]').value === createdBenchmarkNote.title && benchmarkPaletteNoteSource.dataset.sourceKey === "benchmark-review:repo-taskosaur-taskosaur:86" && qs('[data-action="open-review-record-source"]', benchmarkPaletteNoteSource), "review source label palette result opened the wrong PM Bench note");
    sourceBenchmarkReviewNotePaletteLabelSearchOk = true;
    click('[data-action="open-review-record-source"]', benchmarkPaletteNoteSource);
    await waitFor(() => dashboard.currentView === "pm-portfolio" && !document.querySelector("#modal.open") && state.portfolioFilter === "candidates" && state.portfolioBenchmarkFilter === "focused" && qs("[data-benchmark-review-handoff]").dataset.reviewHandoffPrimaryKey === "benchmark-review:repo-taskosaur-taskosaur:86" && qs("[data-benchmark-review-handoff]").dataset.reviewSourceReturnRevealed === "true", "PM Bench review note palette source return did not open the original review package");
    sourceBenchmarkReviewNotePaletteSourceReturnOk = true;
    click('[data-action="open-palette"]');
    fill("#paletteInput", "PM Bench Review 출처");
    await waitFor(() => {
      const items = qsa("#paletteResults .pal-item");
      return items.some((item) => item.textContent.includes(createdIssue.title) && item.textContent.includes(createdIssue.id) && item.textContent.includes("PM Bench Review"))
        && items.some((item) => item.textContent.includes(createdBenchmarkNote.title) && item.textContent.includes("메모") && item.textContent.includes("PM Bench Review"));
    }, "PM Bench Review source label search did not render issue and note results");
    qsa("#paletteResults .pal-item").find((item) => item.textContent.includes(createdIssue.title) && item.textContent.includes(createdIssue.id) && item.textContent.includes("PM Bench Review")).click();
    await waitFor(() => dashboard.currentView === "pm-kanban" && qs('#view-pm-kanban [data-kanban-source-filterbar]').dataset.kanbanSourceFilterCurrent === "benchmark-review" && qs('#sheet.open [data-action="open-issue-source"]'), "PM Bench Review source label palette result did not open issue sheet in source scope");
    click('#sheet [data-action="close-sheet"]');
    await waitFor(() => !document.querySelector("#sheet.open"), "PM Bench Review source label palette sheet did not close");
    sourceBenchmarkReviewPaletteFamilyLabelSearchOk = true;
    click('[data-action="open-palette"]');
    fill("#paletteInput", "Workspace Review 출처");
    await waitFor(() => {
      const items = qsa("#paletteResults .pal-item");
      return items.some((item) => item.textContent.includes(createdWorkspaceIssue.title) && item.textContent.includes(createdWorkspaceIssue.id) && item.textContent.includes("Workspace Review"))
        && items.some((item) => item.textContent.includes(createdWorkspaceNote.title) && item.textContent.includes("메모") && item.textContent.includes("Workspace Review"));
    }, "Workspace Review source label search did not render issue and note results");
    qsa("#paletteResults .pal-item").find((item) => item.textContent.includes(createdWorkspaceIssue.title) && item.textContent.includes(createdWorkspaceIssue.id) && item.textContent.includes("Workspace Review")).click();
    await waitFor(() => dashboard.currentView === "pm-kanban" && qs('#view-pm-kanban [data-kanban-source-filterbar]').dataset.kanbanSourceFilterCurrent === "workspace-review" && qs('#sheet.open [data-action="open-issue-source"]'), "Workspace Review source label palette result did not open issue sheet in source scope");
    click('#sheet [data-action="close-sheet"]');
    await waitFor(() => !document.querySelector("#sheet.open"), "Workspace Review source label palette sheet did not close");
    click('[data-action="open-palette"]');
    fill("#paletteInput", "KB/IA Review 출처");
    await waitFor(() => {
      const items = qsa("#paletteResults .pal-item");
      return items.some((item) => item.textContent.includes(createdKbIssue.title) && item.textContent.includes(createdKbIssue.id) && item.textContent.includes("KB/IA Review"))
        && items.some((item) => item.textContent.includes(createdKbNote.title) && item.textContent.includes("메모") && item.textContent.includes("KB/IA Review"));
    }, "KB/IA Review source label search did not render issue and note results");
    qsa("#paletteResults .pal-item").find((item) => item.textContent.includes(createdKbIssue.title) && item.textContent.includes(createdKbIssue.id) && item.textContent.includes("KB/IA Review")).click();
    await waitFor(() => dashboard.currentView === "pm-kanban" && qs('#view-pm-kanban [data-kanban-source-filterbar]').dataset.kanbanSourceFilterCurrent === "kb-ia-review" && qs('#sheet.open [data-action="open-issue-source"]'), "KB/IA Review source label palette result did not open issue sheet in source scope");
    click('#sheet [data-action="close-sheet"]');
    await waitFor(() => !document.querySelector("#sheet.open"), "KB/IA Review source label palette sheet did not close");
    sourceReviewAllFamilyLabelSearchOk = true;
    click('[data-action="open-palette"]');
    fill("#paletteInput", "벤치마크 리뷰 출처");
    await waitFor(() => {
      const items = qsa("#paletteResults .pal-item");
      return items.some((item) => item.textContent.includes(createdIssue.title) && item.textContent.includes(createdIssue.id) && item.textContent.includes("PM Bench Review"))
        && items.some((item) => item.textContent.includes(createdBenchmarkNote.title) && item.textContent.includes("메모") && item.textContent.includes("PM Bench Review"));
    }, "benchmark review Korean alias search did not render issue and note results");
    qsa("#paletteResults .pal-item").find((item) => item.textContent.includes(createdBenchmarkNote.title) && item.textContent.includes("메모") && item.textContent.includes("PM Bench Review")).click();
    await waitFor(() => dashboard.currentView === "notes" && state.noteSourceFilter === "benchmark-review" && document.querySelector("#modal.open #noteForm"), "benchmark review Korean alias search did not open PM Bench review note modal");
    click('#modal [data-action="close-modal"]');
    await waitFor(() => !document.querySelector("#modal.open"), "benchmark review Korean alias note modal did not close");
    sourceBenchmarkReviewKoreanFamilyAliasSearchOk = true;
    click('[data-action="open-palette"]');
    fill("#paletteInput", "워크스페이스 리뷰 출처");
    await waitFor(() => {
      const items = qsa("#paletteResults .pal-item");
      return items.some((item) => item.textContent.includes(createdWorkspaceIssue.title) && item.textContent.includes(createdWorkspaceIssue.id) && item.textContent.includes("Workspace Review"))
        && items.some((item) => item.textContent.includes(createdWorkspaceNote.title) && item.textContent.includes("메모") && item.textContent.includes("Workspace Review"));
    }, "workspace review Korean alias search did not render issue and note results");
    qsa("#paletteResults .pal-item").find((item) => item.textContent.includes(createdWorkspaceNote.title) && item.textContent.includes("메모") && item.textContent.includes("Workspace Review")).click();
    await waitFor(() => dashboard.currentView === "notes" && state.noteSourceFilter === "workspace-review" && document.querySelector("#modal.open #noteForm"), "workspace review Korean alias search did not open Workspace review note modal");
    click('#modal [data-action="close-modal"]');
    await waitFor(() => !document.querySelector("#modal.open"), "workspace review Korean alias note modal did not close");
    click('[data-action="open-palette"]');
    fill("#paletteInput", "지식 베이스 리뷰 출처");
    await waitFor(() => {
      const items = qsa("#paletteResults .pal-item");
      return items.some((item) => item.textContent.includes(createdKbIssue.title) && item.textContent.includes(createdKbIssue.id) && item.textContent.includes("KB/IA Review"))
        && items.some((item) => item.textContent.includes(createdKbNote.title) && item.textContent.includes("메모") && item.textContent.includes("KB/IA Review"));
    }, "KB/IA review Korean alias search did not render issue and note results");
    qsa("#paletteResults .pal-item").find((item) => item.textContent.includes(createdKbNote.title) && item.textContent.includes("메모") && item.textContent.includes("KB/IA Review")).click();
    await waitFor(() => dashboard.currentView === "notes" && state.noteSourceFilter === "kb-ia-review" && document.querySelector("#modal.open #noteForm"), "KB/IA review Korean alias search did not open KB/IA review note modal");
    click('#modal [data-action="close-modal"]');
    await waitFor(() => !document.querySelector("#modal.open"), "KB/IA review Korean alias note modal did not close");
    sourceReviewKoreanAllFamilyAliasSearchOk = true;
    click('[data-action="open-palette"]');
    fill("#paletteInput", "Review 출처");
    await waitFor(() => qsa("#paletteResults .pal-item").some((item) => item.textContent.includes(createdIssue.title) && item.textContent.includes(createdIssue.id) && item.textContent.includes("Review")), "review source label search did not render sourced palette issue after PM Bench note open");
    qsa("#paletteResults .pal-item").find((item) => item.textContent.includes(createdIssue.title) && item.textContent.includes(createdIssue.id) && item.textContent.includes("Review")).click();
    await waitFor(() => dashboard.currentView === "pm-kanban" && qs('#view-pm-kanban [data-kanban-source-filterbar]').dataset.kanbanSourceFilterCurrent === "benchmark-review" && qs('#sheet.open [data-action="open-issue-source"]'), "review source label palette result did not open issue sheet in source scope");
    click('#sheet [data-action="close-sheet"]');
    await waitFor(() => !document.querySelector("#sheet.open"), "review source label palette sheet did not close");
    sourceIssueExistingReviewOk = true;
    sourceReviewPaletteLabelSearchOk = true;
    sourceReviewNotePaletteLabelSearchOk = true;
    sourceReviewPaletteFamilyLabelOk = true;
    reviewNoteSourceReturnOk = true;
    reviewNoteCardSourceReturnOk = true;
    reviewNoteSourceFilterOk = true;
    reviewNoteExistingOpenOk = true;
    reviewIssueSourceReturnOk = true;
    reviewExecutionChecklistOk = true;
    reviewExecutionChecklistProgressOk = true;
    reviewArtifactFreshReceiptAfterChecklistOk = true;
    reviewAssigneeOverrideOk = true;
    reviewArtifactDiffVisibleOk = true;
    reviewArtifactDiffValidatedOk = true;
    candidateBenchmarkRubricVisibleOk = true;
    candidateBenchmarkRubricScoreVisibleOk = true;
    workspaceBenchmarkRubricVisibleOk = true;
    workspaceBenchmarkExportVisibleOk = true;
    workspaceBenchmarkReviewHandoffVisibleOk = true;
    workspaceBenchmarkReviewHandoffCopyVisibleOk = true;
    workspaceBenchmarkReviewIssueDraftVisibleOk = true;
    workspaceBenchmarkReviewNotePublishVisibleOk = true;
    workspaceBenchmarkReviewGithubCommentVisibleOk = true;
    knowledgeBaseBenchmarkRubricVisibleOk = true;
    knowledgeBaseBenchmarkExportVisibleOk = true;
    knowledgeBaseBenchmarkReviewHandoffVisibleOk = true;
    knowledgeBaseBenchmarkReviewHandoffCopyVisibleOk = true;
    knowledgeBaseBenchmarkReviewIssueDraftVisibleOk = true;
    knowledgeBaseBenchmarkReviewNotePublishVisibleOk = true;
    knowledgeBaseBenchmarkReviewGithubCommentVisibleOk = true;
    candidateBenchmarkReviewQueueVisibleOk = true;
    candidateBenchmarkReviewHandoffVisibleOk = true;
    candidateBenchmarkReviewHandoffCopyVisibleOk = true;
    candidateBenchmarkReviewIssueDraftVisibleOk = true;
    reviewPackageBundleVisibleOk = true;
    reviewPackageManifestVisibleOk = true;
    reviewPackageArtifactQualityRubricVisibleOk = true;
    reviewPackageDecisionBriefVisibleOk = true;
    reviewPackageOperatorQuickStartVisibleOk = true;
    reviewIssueDecisionSummaryVisibleOk = true;
    reviewCommentNoteDecisionSummaryVisibleOk = true;
    reviewPackagePasteTargetsVisibleOk = true;
    reviewPackageFinalQualityGateVisibleOk = true;
    reviewPackageQualityRepairChecklistVisibleOk = true;
    await nav("pm-portfolio");
    click('[data-action="portfolio-benchmark-filter"][data-benchmark-filter="all"]');
    await waitFor(() => state.portfolioBenchmarkFilter === "all" && document.querySelectorAll('#view-pm-portfolio .portfolio-card[data-source-kind="adoption-candidate"]').length === candidateCount, "benchmark focus filter did not reset");
    candidateBenchmarkQueueVisibleOk = true;
    click('[data-action="portfolio-filter"][data-filter="owned"]');
    await waitFor(() => state.portfolioFilter === "owned" && document.querySelectorAll('#view-pm-portfolio .portfolio-card[data-source-kind="adoption-candidate"]').length === 0, "owned portfolio filter still rendered adoption candidates");
    assert(document.querySelectorAll("#view-pm-portfolio .portfolio-card").length === ownedCount, "owned portfolio filter count was wrong");
    click('[data-action="portfolio-filter"][data-filter="candidates"]');
    fill("#globalSearch", "OpenLoaf");
    await waitFor(() => state.query === "OpenLoaf" && document.querySelectorAll("#view-pm-portfolio .portfolio-card").length === 1, "OpenLoaf search did not filter portfolio");
    const card = qs('#view-pm-portfolio .portfolio-card[data-project-id="' + candidate.id + '"]');
    const text = card.innerText;
    const meta = qs("[data-candidate-meta]", card);
    assert(text.includes("OpenLoaf/OpenLoaf"), "OpenLoaf candidate card did not render");
    assert(text.includes("AI/로컬 워크스페이스"), "OpenLoaf candidate category did not render");
    assert(text.includes("에이전트"), "OpenLoaf candidate description did not render");
    assert(meta.innerText.includes("단계") && meta.innerText.includes("검토"), "OpenLoaf adoption stage did not render");
    assert(meta.innerText.includes("★") && meta.innerText.includes("65"), "OpenLoaf star count did not render");
    assert(meta.innerText.includes("Fork") && meta.innerText.includes("7"), "OpenLoaf fork count did not render");
    assert(meta.innerText.includes("TypeScript"), "OpenLoaf language did not render");
    assert(qs("[data-candidate-priority]", card).textContent.includes(String(projectCandidatePriority(candidate).score)), "OpenLoaf priority score did not render");
    const openLoafCommit = qs("[data-candidate-commit]", card);
    assert(openLoafCommit.dataset.candidateCommit === shortOpenLoafCommit, "OpenLoaf freshness commit did not render");
    assert(openLoafCommit.dataset.candidatePushedAt === snapshotOpenLoaf.pushedAt, "OpenLoaf pushedAt freshness marker did not render");
    const href = qs(".portfolio-candidate-link", card).href;
    assert(href === "https://github.com/OpenLoaf/OpenLoaf" || href === "https://github.com/OpenLoaf/OpenLoaf/", "OpenLoaf GitHub link did not render safely");
    fill("#globalSearch", shortPlaneCommit);
    await waitFor(() => state.query === shortPlaneCommit && document.querySelectorAll("#view-pm-portfolio .portfolio-card").length === 1, "Plane commit search did not filter portfolio");
    await waitFor(() => !!document.querySelector('#view-pm-portfolio .portfolio-card[data-project-id="' + planeCandidate.id + '"]'), "Plane portfolio card did not render after commit search");
    const planeCard = qs('#view-pm-portfolio .portfolio-card[data-project-id="' + planeCandidate.id + '"]');
    const planeText = planeCard.innerText;
    assert(planeText.includes("makeplane/plane"), "Plane candidate card did not render");
    assert(planeText.includes("Jira, Linear"), "Plane candidate description did not render");
    assert(planeText.includes(formatMetric(snapshotPlane.stars)), "Plane star count did not render");
    assert(planeText.includes(formatMetric(snapshotPlane.forks)), "Plane fork count did not render");
    assert(planeText.includes("TypeScript"), "Plane language did not render");
    assert(qs("[data-candidate-action]", planeCard).textContent.includes("리스크 리뷰"), "Plane candidate action did not render risk review");
    const planeCommit = qs("[data-candidate-commit]", planeCard);
    assert(planeCommit.dataset.candidateCommit === shortPlaneCommit, "Plane freshness commit did not render");
    assert(planeCommit.dataset.candidatePushedAt === snapshotPlane.pushedAt, "Plane pushedAt freshness marker did not render");
    const planeHref = qs(".portfolio-candidate-link", planeCard).href;
    assert(planeHref === "https://github.com/makeplane/plane" || planeHref === "https://github.com/makeplane/plane/", "Plane GitHub link did not render safely");
    fill("#globalSearch", shortAppFlowyCommit);
    await waitFor(() => state.query === shortAppFlowyCommit && document.querySelectorAll("#view-pm-portfolio .portfolio-card").length === 1, "AppFlowy commit search did not filter portfolio");
    await waitFor(() => !!document.querySelector('#view-pm-portfolio .portfolio-card[data-project-id="' + appFlowyCandidate.id + '"]'), "AppFlowy portfolio card did not render after commit search");
    const appFlowyCard = qs('#view-pm-portfolio .portfolio-card[data-project-id="' + appFlowyCandidate.id + '"]');
    const appFlowyText = appFlowyCard.innerText;
    assert(appFlowyText.includes("AppFlowy-IO/AppFlowy"), "AppFlowy candidate card did not render");
    assert(appFlowyText.includes("Notion"), "AppFlowy candidate description did not render");
    assert(appFlowyText.includes(formatMetric(snapshotAppFlowy.stars)), "AppFlowy star count did not render");
    assert(appFlowyText.includes(formatMetric(snapshotAppFlowy.forks)), "AppFlowy fork count did not render");
    assert(appFlowyText.includes("Dart"), "AppFlowy language did not render");
    assert(qs("[data-candidate-action]", appFlowyCard).textContent.includes("리스크 리뷰"), "AppFlowy candidate action did not render risk review");
    const appFlowyCommit = qs("[data-candidate-commit]", appFlowyCard);
    assert(appFlowyCommit.dataset.candidateCommit === shortAppFlowyCommit, "AppFlowy freshness commit did not render");
    assert(appFlowyCommit.dataset.candidatePushedAt === snapshotAppFlowy.pushedAt, "AppFlowy pushedAt freshness marker did not render");
    const appFlowyHref = qs(".portfolio-candidate-link", appFlowyCard).href;
    assert(appFlowyHref === "https://github.com/AppFlowy-IO/AppFlowy" || appFlowyHref === "https://github.com/AppFlowy-IO/AppFlowy/", "AppFlowy GitHub link did not render safely");
    fill("#globalSearch", shortAffineCommit);
    await waitFor(() => state.query === shortAffineCommit && document.querySelectorAll("#view-pm-portfolio .portfolio-card").length === 1, "AFFiNE commit search did not filter portfolio");
    await waitFor(() => !!document.querySelector('#view-pm-portfolio .portfolio-card[data-project-id="' + affineCandidate.id + '"]'), "AFFiNE portfolio card did not render after commit search");
    const affineCard = qs('#view-pm-portfolio .portfolio-card[data-project-id="' + affineCandidate.id + '"]');
    const affineText = affineCard.innerText;
    assert(affineText.includes("toeverything/AFFiNE"), "AFFiNE candidate card did not render");
    assert(affineText.includes("Notion") && affineText.includes("Miro"), "AFFiNE candidate description did not render");
    assert(affineText.includes(formatMetric(snapshotAffine.stars)), "AFFiNE star count did not render");
    assert(affineText.includes(formatMetric(snapshotAffine.forks)), "AFFiNE fork count did not render");
    assert(affineText.includes("TypeScript"), "AFFiNE language did not render");
    assert(qs("[data-candidate-action]", affineCard).textContent.includes("리스크 리뷰"), "AFFiNE candidate action did not render risk review");
    const affineCommit = qs("[data-candidate-commit]", affineCard);
    assert(affineCommit.dataset.candidateCommit === shortAffineCommit, "AFFiNE freshness commit did not render");
    assert(affineCommit.dataset.candidatePushedAt === snapshotAffine.pushedAt, "AFFiNE pushedAt freshness marker did not render");
    const affineHref = qs(".portfolio-candidate-link", affineCard).href;
    assert(affineHref === "https://github.com/toeverything/AFFiNE" || affineHref === "https://github.com/toeverything/AFFiNE/", "AFFiNE GitHub link did not render safely");
    fill("#globalSearch", shortOutlineCommit);
    await waitFor(() => state.query === shortOutlineCommit && document.querySelectorAll("#view-pm-portfolio .portfolio-card").length === 1, "Outline commit search did not filter portfolio");
    await waitFor(() => !!document.querySelector('#view-pm-portfolio .portfolio-card[data-project-id="' + outlineCandidate.id + '"]'), "Outline portfolio card did not render after commit search");
    const outlineCard = qs('#view-pm-portfolio .portfolio-card[data-project-id="' + outlineCandidate.id + '"]');
    const outlineText = outlineCard.innerText;
    assert(outlineText.includes("outline/outline"), "Outline candidate card did not render");
    assert(outlineText.includes("Markdown") && outlineText.includes("지식"), "Outline candidate description did not render");
    assert(outlineText.includes(formatMetric(snapshotOutline.stars)), "Outline star count did not render");
    assert(outlineText.includes(formatMetric(snapshotOutline.forks)), "Outline fork count did not render");
    assert(outlineText.includes("TypeScript"), "Outline language did not render");
    assert(qs("[data-candidate-action]", outlineCard).textContent.includes("스파이크"), "Outline candidate action did not render spike recommendation");
    const outlineCommit = qs("[data-candidate-commit]", outlineCard);
    assert(outlineCommit.dataset.candidateCommit === shortOutlineCommit, "Outline freshness commit did not render");
    assert(outlineCommit.dataset.candidatePushedAt === snapshotOutline.pushedAt, "Outline pushedAt freshness marker did not render");
    const outlineHref = qs(".portfolio-candidate-link", outlineCard).href;
    assert(outlineHref === "https://github.com/outline/outline" || outlineHref === "https://github.com/outline/outline/", "Outline GitHub link did not render safely");
    fill("#globalSearch", shortBookStackCommit);
    await waitFor(() => state.query === shortBookStackCommit && document.querySelectorAll("#view-pm-portfolio .portfolio-card").length === 1, "BookStack commit search did not filter portfolio");
    await waitFor(() => !!document.querySelector('#view-pm-portfolio .portfolio-card[data-project-id="' + bookStackCandidate.id + '"]'), "BookStack portfolio card did not render after commit search");
    const bookStackCard = qs('#view-pm-portfolio .portfolio-card[data-project-id="' + bookStackCandidate.id + '"]');
    const bookStackText = bookStackCard.innerText;
    assert(bookStackText.includes("BookStackApp/BookStack"), "BookStack candidate card did not render");
    assert(bookStackText.includes("Codeberg") && bookStackText.includes("문서"), "BookStack candidate description did not render");
    assert(bookStackText.includes(formatMetric(snapshotBookStack.stars)), "BookStack star count did not render");
    assert(bookStackText.includes(formatMetric(snapshotBookStack.forks)), "BookStack fork count did not render");
    assert(bookStackText.includes("PHP"), "BookStack language did not render");
    assert(qs("[data-candidate-action]", bookStackCard).textContent.includes("아키텍처 벤치"), "BookStack candidate action did not render architecture benchmark");
    const bookStackCommit = qs("[data-candidate-commit]", bookStackCard);
    assert(bookStackCommit.dataset.candidateCommit === shortBookStackCommit, "BookStack freshness commit did not render");
    assert(bookStackCommit.dataset.candidatePushedAt === snapshotBookStack.pushedAt, "BookStack pushedAt freshness marker did not render");
    const bookStackHref = qs(".portfolio-candidate-link", bookStackCard).href;
    assert(bookStackHref === "https://github.com/BookStackApp/BookStack" || bookStackHref === "https://github.com/BookStackApp/BookStack/", "BookStack GitHub link did not render safely");
    fill("#globalSearch", shortWikiJsCommit);
    await waitFor(() => state.query === shortWikiJsCommit && document.querySelectorAll("#view-pm-portfolio .portfolio-card").length === 1, "Wiki.js commit search did not filter portfolio");
    await waitFor(() => !!document.querySelector('#view-pm-portfolio .portfolio-card[data-project-id="' + wikiJsCandidate.id + '"]'), "Wiki.js portfolio card did not render after commit search");
    const wikiJsCard = qs('#view-pm-portfolio .portfolio-card[data-project-id="' + wikiJsCandidate.id + '"]');
    const wikiJsText = wikiJsCard.innerText;
    assert(wikiJsText.includes("requarks/wiki"), "Wiki.js candidate card did not render");
    assert(wikiJsText.includes("Wiki.js") && wikiJsText.includes("Git"), "Wiki.js candidate description did not render");
    assert(wikiJsText.includes(formatMetric(snapshotWikiJs.stars)), "Wiki.js star count did not render");
    assert(wikiJsText.includes(formatMetric(snapshotWikiJs.forks)), "Wiki.js fork count did not render");
    assert(wikiJsText.includes("Vue"), "Wiki.js language did not render");
    assert(qs("[data-candidate-action]", wikiJsCard).textContent.includes("아키텍처 벤치"), "Wiki.js candidate action did not render architecture benchmark");
    const wikiJsCommit = qs("[data-candidate-commit]", wikiJsCard);
    assert(wikiJsCommit.dataset.candidateCommit === shortWikiJsCommit, "Wiki.js freshness commit did not render");
    assert(wikiJsCommit.dataset.candidatePushedAt === snapshotWikiJs.pushedAt, "Wiki.js pushedAt freshness marker did not render");
    const wikiJsHref = qs(".portfolio-candidate-link", wikiJsCard).href;
    assert(wikiJsHref === "https://github.com/requarks/wiki" || wikiJsHref === "https://github.com/requarks/wiki/", "Wiki.js GitHub link did not render safely");
    fill("#globalSearch", shortEpicenterCommit);
    await waitFor(() => state.query === shortEpicenterCommit && document.querySelectorAll("#view-pm-portfolio .portfolio-card").length === 1, "Epicenter commit search did not filter portfolio");
    await waitFor(() => !!document.querySelector('#view-pm-portfolio .portfolio-card[data-project-id="' + epicenterCandidate.id + '"]'), "Epicenter portfolio card did not render after commit search");
    const epicenterCard = qs('#view-pm-portfolio .portfolio-card[data-project-id="' + epicenterCandidate.id + '"]');
    const epicenterText = epicenterCard.innerText;
    assert(epicenterText.includes("EpicenterHQ/epicenter"), "Epicenter candidate card did not render");
    const epicenterCommit = qs("[data-candidate-commit]", epicenterCard);
    assert(epicenterCommit.dataset.candidateCommit === shortEpicenterCommit, "Epicenter freshness commit did not render");
    assert(epicenterCommit.dataset.candidatePushedAt === snapshotEpicenter.pushedAt, "Epicenter pushedAt freshness marker did not render");
    const epicenterHref = qs(".portfolio-candidate-link", epicenterCard).href;
    assert(epicenterHref === "https://github.com/EpicenterHQ/epicenter" || epicenterHref === "https://github.com/EpicenterHQ/epicenter/", "Epicenter GitHub link did not render safely");
    fill("#globalSearch", "colanode");
    await waitFor(() => state.query === "colanode" && document.querySelectorAll("#view-pm-portfolio .portfolio-card").length === 1, "Colanode search did not filter portfolio");
    await waitFor(() => !!document.querySelector('#view-pm-portfolio .portfolio-card[data-project-id="' + benchmarkCandidate.id + '"]'), "Colanode portfolio card did not render after search");
    const benchmarkCard = qs('#view-pm-portfolio .portfolio-card[data-project-id="' + benchmarkCandidate.id + '"]');
    const benchmarkText = benchmarkCard.innerText;
    assert(benchmarkText.includes("colanode/colanode"), "Colanode candidate card did not render");
    assert(benchmarkText.includes("로컬 퍼스트/워크스페이스"), "Colanode candidate category did not render");
    assert(benchmarkText.includes("Slack/Notion"), "Colanode candidate description did not render");
    assert(benchmarkText.includes(formatMetric(snapshotColanode.stars)), "Colanode star count did not render");
    assert(benchmarkText.includes(formatMetric(snapshotColanode.forks)), "Colanode fork count did not render");
    assert(benchmarkText.includes("TypeScript"), "Colanode language did not render");
    const action = qs("[data-candidate-action]", benchmarkCard);
    assert(action.textContent.includes("아키텍처 벤치"), "Colanode candidate action did not render");
    assert(action.textContent.includes("로컬 퍼스트 구조"), "Colanode candidate action reason did not render");
    const colanodeCommit = qs("[data-candidate-commit]", benchmarkCard);
    assert(colanodeCommit.dataset.candidateCommit === shortColanodeCommit, "Colanode freshness commit did not render");
    assert(colanodeCommit.dataset.candidatePushedAt === snapshotColanode.pushedAt, "Colanode pushedAt freshness marker did not render");
    const benchmarkHref = qs(".portfolio-candidate-link", benchmarkCard).href;
    assert(benchmarkHref === "https://github.com/colanode/colanode" || benchmarkHref === "https://github.com/colanode/colanode/", "Colanode GitHub link did not render safely");
    fill("#globalSearch", shortParabolCommit);
    await waitFor(() => state.query === shortParabolCommit && document.querySelectorAll("#view-pm-portfolio .portfolio-card").length === 1, "Parabol commit search did not filter portfolio");
    await waitFor(() => !!document.querySelector('#view-pm-portfolio .portfolio-card[data-project-id="' + parabolCandidate.id + '"]'), "Parabol portfolio card did not render after commit search");
    const parabolCard = qs('#view-pm-portfolio .portfolio-card[data-project-id="' + parabolCandidate.id + '"]');
    const parabolText = parabolCard.innerText;
    assert(parabolText.includes("ParabolInc/parabol"), "Parabol candidate card did not render");
    const parabolCommit = qs("[data-candidate-commit]", parabolCard);
    assert(parabolCommit.dataset.candidateCommit === shortParabolCommit, "Parabol freshness commit did not render");
    assert(parabolCommit.dataset.candidatePushedAt === snapshotParabol.pushedAt, "Parabol pushedAt freshness marker did not render");
    const parabolHref = qs(".portfolio-candidate-link", parabolCard).href;
    assert(parabolHref === "https://github.com/ParabolInc/parabol" || parabolHref === "https://github.com/ParabolInc/parabol/", "Parabol GitHub link did not render safely");
    fill("#globalSearch", shortWorklenzCommit);
    await waitFor(() => state.query === shortWorklenzCommit && document.querySelectorAll("#view-pm-portfolio .portfolio-card").length === 1, "Worklenz commit search did not filter portfolio");
    await waitFor(() => !!document.querySelector('#view-pm-portfolio .portfolio-card[data-project-id="' + worklenzCandidate.id + '"]'), "Worklenz portfolio card did not render after commit search");
    const worklenzCard = qs('#view-pm-portfolio .portfolio-card[data-project-id="' + worklenzCandidate.id + '"]');
    const worklenzText = worklenzCard.innerText;
    assert(worklenzText.includes("Worklenz/worklenz"), "Worklenz candidate card did not render");
    const worklenzCommit = qs("[data-candidate-commit]", worklenzCard);
    assert(worklenzCommit.dataset.candidateCommit === shortWorklenzCommit, "Worklenz freshness commit did not render");
    assert(worklenzCommit.dataset.candidatePushedAt === snapshotWorklenz.pushedAt, "Worklenz pushedAt freshness marker did not render");
    const worklenzHref = qs(".portfolio-candidate-link", worklenzCard).href;
    assert(worklenzHref === "https://github.com/Worklenz/worklenz" || worklenzHref === "https://github.com/Worklenz/worklenz/", "Worklenz GitHub link did not render safely");
    fill("#globalSearch", shortAnytypeCommit);
    await waitFor(() => state.query === shortAnytypeCommit && document.querySelectorAll("#view-pm-portfolio .portfolio-card").length === 1, "Anytype commit search did not filter portfolio");
    await waitFor(() => !!document.querySelector('#view-pm-portfolio .portfolio-card[data-project-id="' + anytypeCandidate.id + '"]'), "Anytype portfolio card did not render after commit search");
    const anytypeCard = qs('#view-pm-portfolio .portfolio-card[data-project-id="' + anytypeCandidate.id + '"]');
    const anytypeText = anytypeCard.innerText;
    assert(anytypeText.includes("anyproto/anytype-ts"), "Anytype candidate card did not render");
    const anytypeCommit = qs("[data-candidate-commit]", anytypeCard);
    assert(anytypeCommit.dataset.candidateCommit === shortAnytypeCommit, "Anytype freshness commit did not render");
    assert(anytypeCommit.dataset.candidatePushedAt === snapshotAnytype.pushedAt, "Anytype pushedAt freshness marker did not render");
    const anytypeHref = qs(".portfolio-candidate-link", anytypeCard).href;
    assert(anytypeHref === "https://github.com/anyproto/anytype-ts" || anytypeHref === "https://github.com/anyproto/anytype-ts/", "Anytype GitHub link did not render safely");
    fill("#globalSearch", shortFocalboardCommit);
    await waitFor(() => state.query === shortFocalboardCommit && document.querySelectorAll("#view-pm-portfolio .portfolio-card").length === 1, "Focalboard commit search did not filter portfolio");
    await waitFor(() => !!document.querySelector('#view-pm-portfolio .portfolio-card[data-project-id="' + focalboardCandidate.id + '"]'), "Focalboard portfolio card did not render after commit search");
    const focalboardCard = qs('#view-pm-portfolio .portfolio-card[data-project-id="' + focalboardCandidate.id + '"]');
    const focalboardText = focalboardCard.innerText;
    assert(focalboardText.includes("mattermost-community/focalboard"), "Focalboard candidate card did not render");
    const focalboardCommit = qs("[data-candidate-commit]", focalboardCard);
    assert(focalboardCommit.dataset.candidateCommit === shortFocalboardCommit, "Focalboard freshness commit did not render");
    assert(focalboardCommit.dataset.candidatePushedAt === snapshotFocalboard.pushedAt, "Focalboard pushedAt freshness marker did not render");
    const focalboardHref = qs(".portfolio-candidate-link", focalboardCard).href;
    assert(focalboardHref === "https://github.com/mattermost-community/focalboard" || focalboardHref === "https://github.com/mattermost-community/focalboard/", "Focalboard GitHub link did not render safely");
    for (const target of remainingFreshnessSnapshots) {
      fill("#globalSearch", target.shortCommit);
      await waitFor(() => state.query === target.shortCommit && document.querySelectorAll("#view-pm-portfolio .portfolio-card").length === 1, target.name + " commit search did not filter portfolio");
      await waitFor(() => !!document.querySelector('#view-pm-portfolio .portfolio-card[data-project-id="' + target.candidate.id + '"]'), target.name + " portfolio card did not render after commit search");
      const targetCard = qs('#view-pm-portfolio .portfolio-card[data-project-id="' + target.candidate.id + '"]');
      const targetText = targetCard.innerText;
      assert(targetText.includes(target.name), target.name + " candidate card did not render");
      assert(targetText.includes(formatMetric(target.snapshot.stars)), target.name + " star count did not render");
      assert(targetText.includes(formatMetric(target.snapshot.forks)), target.name + " fork count did not render");
      const targetCommit = qs("[data-candidate-commit]", targetCard);
      assert(targetCommit.dataset.candidateCommit === target.shortCommit, target.name + " freshness commit did not render");
      assert(targetCommit.dataset.candidatePushedAt === target.snapshot.pushedAt, target.name + " pushedAt freshness marker did not render");
      const targetHref = qs(".portfolio-candidate-link", targetCard).href;
      assert(targetHref === target.expectedUrl || targetHref === target.expectedUrl + "/", target.name + " GitHub link did not render safely");
      if (target.key === "workstream") {
        const benchmark = qs("[data-candidate-benchmark]", targetCard);
        assert(benchmark.dataset.candidateBenchmark === "JooPark PM/Calendar", "Workstream benchmark focus did not render target surface");
        assert(benchmark.dataset.benchmarkFlow === "PR + task + calendar command center", "Workstream benchmark flow did not render");
        assert(benchmark.title.includes("AI review/readiness"), "Workstream benchmark signal did not render");
      }
      if (target.key === "taskosaur") {
        const benchmark = qs("[data-candidate-benchmark]", targetCard);
        assert(benchmark.dataset.candidateBenchmark === "JooPark PM/Kanban", "Taskosaur benchmark focus did not render target surface");
        assert(benchmark.dataset.benchmarkFlow === "Conversational AI task execution", "Taskosaur benchmark flow did not render");
        assert(benchmark.title.includes("Kanban/sprint workflow"), "Taskosaur benchmark signal did not render");
      }
      remainingWorkspaceFreshnessOk[target.key] = true;
    }
    candidateBenchmarkFocusVisibleOk = true;
    fill("#globalSearch", shortVeritasCommit);
    await waitFor(() => state.query === shortVeritasCommit && document.querySelectorAll("#view-pm-portfolio .portfolio-card").length === 1, "Veritas commit search did not filter portfolio");
    await waitFor(() => !!document.querySelector('#view-pm-portfolio .portfolio-card[data-project-id="' + veritasCandidate.id + '"]'), "Veritas portfolio card did not render after commit search");
    const veritasCard = qs('#view-pm-portfolio .portfolio-card[data-project-id="' + veritasCandidate.id + '"]');
    const veritasText = veritasCard.innerText;
    assert(veritasText.includes("Veritas-7/autoresearch-skill-system"), "Veritas candidate card did not render");
    assert(veritasText.includes(snapshotVeritas.description), "Veritas candidate description did not render");
    const veritasCommit = qs("[data-candidate-commit]", veritasCard);
    assert(veritasCommit.dataset.candidateCommit === shortVeritasCommit, "Veritas freshness commit did not render");
    assert(veritasCommit.dataset.candidatePushedAt === snapshotVeritas.pushedAt, "Veritas pushedAt freshness marker did not render");
    const veritasHref = qs(".portfolio-candidate-link", veritasCard).href;
    assert(veritasHref === "https://github.com/Veritas-7/autoresearch-skill-system" || veritasHref === "https://github.com/Veritas-7/autoresearch-skill-system/", "Veritas GitHub link did not render safely");
    fill("#globalSearch", shortOpenProjectCommit);
    await waitFor(() => state.query === shortOpenProjectCommit && document.querySelectorAll("#view-pm-portfolio .portfolio-card").length === 1, "OpenProject commit search did not filter portfolio");
    await waitFor(() => !!document.querySelector('#view-pm-portfolio .portfolio-card[data-project-id="' + riskCandidate.id + '"]'), "OpenProject portfolio card did not render after commit search");
    const openProjectCard = qs('#view-pm-portfolio .portfolio-card[data-project-id="' + riskCandidate.id + '"]');
    const openProjectText = openProjectCard.innerText;
    assert(openProjectText.includes("opf/openproject"), "OpenProject candidate card did not render");
    const openProjectCommit = qs("[data-candidate-commit]", openProjectCard);
    assert(openProjectCommit.dataset.candidateCommit === shortOpenProjectCommit, "OpenProject freshness commit did not render");
    assert(openProjectCommit.dataset.candidatePushedAt === snapshotOpenProject.pushedAt, "OpenProject pushedAt freshness marker did not render");
    const openProjectHref = qs(".portfolio-candidate-link", openProjectCard).href;
    assert(openProjectHref === "https://github.com/opf/openproject" || openProjectHref === "https://github.com/opf/openproject/", "OpenProject GitHub link did not render safely");
    fill("#globalSearch", shortLeantimeCommit);
    await waitFor(() => state.query === shortLeantimeCommit && document.querySelectorAll("#view-pm-portfolio .portfolio-card").length === 1, "Leantime commit search did not filter portfolio");
    await waitFor(() => !!document.querySelector('#view-pm-portfolio .portfolio-card[data-project-id="' + leantimeCandidate.id + '"]'), "Leantime portfolio card did not render after commit search");
    const leantimeCard = qs('#view-pm-portfolio .portfolio-card[data-project-id="' + leantimeCandidate.id + '"]');
    const leantimeText = leantimeCard.innerText;
    assert(leantimeText.includes("Leantime/leantime"), "Leantime candidate card did not render");
    const leantimeCommit = qs("[data-candidate-commit]", leantimeCard);
    assert(leantimeCommit.dataset.candidateCommit === shortLeantimeCommit, "Leantime freshness commit did not render");
    assert(leantimeCommit.dataset.candidatePushedAt === snapshotLeantime.pushedAt, "Leantime pushedAt freshness marker did not render");
    const leantimeHref = qs(".portfolio-candidate-link", leantimeCard).href;
    assert(leantimeHref === "https://github.com/Leantime/leantime" || leantimeHref === "https://github.com/Leantime/leantime/", "Leantime GitHub link did not render safely");
    fill("#globalSearch", "");
    await waitFor(() => document.querySelectorAll("#view-pm-portfolio .portfolio-card").length > 1, "portfolio did not recover after clearing search");
    click('[data-action="portfolio-filter"][data-filter="all"]');
    await waitFor(() => state.portfolioFilter === "all" && document.querySelectorAll("#view-pm-portfolio .portfolio-card").length === dashboard.projects.length, "portfolio all filter did not recover");
    portfolioCandidateRankedOk = true;
    portfolioCandidateFilterOk = true;
    workspaceCandidateVisibleOk = true;
    workspaceCompetitiveCandidateVisibleOk = true;
    colanodeCandidateFreshnessVisibleOk = true;
    parabolCandidateFreshnessVisibleOk = true;
    worklenzCandidateFreshnessVisibleOk = true;
    anytypeCandidateFreshnessVisibleOk = true;
    focalboardCandidateFreshnessVisibleOk = true;
    epicenterCandidateFreshnessVisibleOk = true;
    openLoafCandidateFreshnessVisibleOk = true;
    planeCandidateFreshnessVisibleOk = true;
    appFlowyCandidateFreshnessVisibleOk = true;
    affineCandidateFreshnessVisibleOk = true;
    outlineCandidateFreshnessVisibleOk = true;
    bookStackCandidateFreshnessVisibleOk = true;
    wikiJsCandidateFreshnessVisibleOk = true;
    veritasCandidateFreshnessVisibleOk = true;
    openProjectCandidateFreshnessVisibleOk = true;
    leantimeCandidateFreshnessVisibleOk = true;
    candidateMetadataRefreshOk = true;
    candidateNextActionVisibleOk = true;
    candidateActionFilterOk = true;
    candidateActionSummaryVisibleOk = true;
    candidateBenchmarkFocusVisibleOk = true;
    candidateBenchmarkQueueVisibleOk = true;
    candidateBenchmarkRubricVisibleOk = true;
    candidateBenchmarkRubricScoreVisibleOk = true;
    workspaceBenchmarkRubricVisibleOk = true;
    workspaceBenchmarkExportVisibleOk = true;
    workspaceBenchmarkReviewHandoffVisibleOk = true;
    workspaceBenchmarkReviewHandoffCopyVisibleOk = true;
    workspaceBenchmarkReviewIssueDraftVisibleOk = true;
    workspaceBenchmarkReviewNotePublishVisibleOk = true;
    workspaceBenchmarkReviewGithubCommentVisibleOk = true;
    knowledgeBaseBenchmarkRubricVisibleOk = true;
    knowledgeBaseBenchmarkExportVisibleOk = true;
    knowledgeBaseBenchmarkReviewHandoffVisibleOk = true;
    knowledgeBaseBenchmarkReviewHandoffCopyVisibleOk = true;
    knowledgeBaseBenchmarkReviewIssueDraftVisibleOk = true;
    knowledgeBaseBenchmarkReviewNotePublishVisibleOk = true;
    knowledgeBaseBenchmarkReviewGithubCommentVisibleOk = true;
    candidateBenchmarkRecommendationExportVisibleOk = true;
    candidateBenchmarkReviewQueueVisibleOk = true;
    candidateBenchmarkReviewHandoffVisibleOk = true;
    candidateBenchmarkReviewHandoffCopyVisibleOk = true;
    candidateBenchmarkReviewIssueDraftVisibleOk = true;
  });

  await runStep("portfolio search no-results recovery", async () => {
    await nav("pm-portfolio");
    click('[data-action="portfolio-filter"][data-filter="all"]');
    await waitFor(() => state.portfolioFilter === "all" && document.querySelectorAll("#view-pm-portfolio .portfolio-card").length === dashboard.projects.length, "portfolio all filter did not render before empty-state search");
    fill("#globalSearch", "NO_MATCH_" + marker);
    await waitFor(() => document.querySelector('#view-pm-portfolio [data-search-empty="pm-portfolio"]'), "portfolio search empty state did not render");
    const empty = qs('#view-pm-portfolio [data-search-empty="pm-portfolio"]');
    assert(empty.getAttribute("role") === "status", "portfolio search empty state does not expose status role");
    assert((document.getElementById("searchCount")?.textContent || "").includes("검색 결과 없음"), "portfolio search status did not announce no results");
    click('#view-pm-portfolio [data-action="clear-search"]');
    await waitFor(() => !document.querySelector('#view-pm-portfolio [data-search-empty="pm-portfolio"]'), "portfolio search clear did not restore results");
    assert(document.getElementById("globalSearch").value === "", "portfolio global search input was not cleared");
    assert(document.activeElement === document.getElementById("globalSearch"), "portfolio clear search did not restore focus to global search input");
    assert(document.querySelectorAll('#view-pm-portfolio [data-search-result="pm-portfolio"]').length === dashboard.projects.length, "portfolio cards did not return after clearing search");
    portfolioSearchRecoveryOk = true;
  });

  let projectId = "";
  await runStep("project modal save", async () => {
    const name = marker + " project";
    await nav("pm-portfolio");
    click('[data-action="project-add"]');
    fill('#projectForm [name="name"]', name);
    fill('#projectForm [name="owner"]', "Release QA");
    fill('#projectForm [name="deadline"]', "2026-07-01");
    fill('#projectForm [name="progress"]', "42");
    await confirmModal();
    const project = dashboard.projects.find((item) => item.name === name);
    assert(project && project.progress === 42, "project was not saved with expected fields");
    projectId = project.id;
    click("#projectSelect");
    fill("#projectPickerSearch", name);
    await waitFor(() => document.querySelector('[data-action="pick-project"][data-project-id="' + projectId + '"]'), "created project not visible in picker");
    click('[data-action="pick-project"][data-project-id="' + projectId + '"]');
    await waitFor(() => dashboard.currentProjectId === projectId, "created project was not selected");
  });

  let issueId = "";
  await runStep("kanban issue save and move", async () => {
    const title = marker + " issue";
    await nav("pm-kanban");
    assert(window.JooParkKanbanView && window.JooParkKanbanView.version === "joopark-kanban-view/v1" && typeof window.JooParkKanbanView.create === "function", "kanban view runtime module was not loaded");
    kanbanViewModuleOk = true;
    click('[data-action="issue-add"]');
    fill('#issueForm [name="title"]', title);
    if (projectId) select('#issueForm [name="project"]', projectId);
    select('#issueForm [name="priority"]', "crit");
    select('#issueForm [name="status"]', "todo");
    fill('#issueForm [name="labels"]', "release, smoke");
    await confirmModal();
    const issue = dashboard.issues.find((item) => item.title === title);
    assert(issue && issue.status === "todo", "issue was not saved in todo");
    issueId = issue.id;
    issue.labels = [{ name: "release" }, { label: "smoke" }, { value: "triage" }, {}, null, "release"];
    commit();
    await waitFor(() => document.querySelector('#view-pm-kanban [data-issue-id="' + issue.id + '"] [data-kanban-label="release"]'), "kanban normalized label did not render");
    const issueCard = qs('#view-pm-kanban [data-issue-id="' + issue.id + '"]');
    const labelTexts = Array.from(issueCard.querySelectorAll("[data-kanban-label]")).map((label) => label.textContent.trim());
	    assert(!issueCard.innerText.includes("[object Object]"), "kanban labels leaked object text");
	    assert(labelTexts.includes("#release") && labelTexts.includes("#smoke") && labelTexts.includes("#triage"), "kanban normalized object labels did not render expected chips");
	    assert(issueCard.querySelector('[data-kanban-label="release"]').getAttribute("aria-label") === "Kanban label release", "kanban normalized label aria-label did not render");
	    kanbanLabelNormalizationOk = true;
	    assert(qs("#kanbanBoard").dataset.kanbanDensity === "comfortable", "kanban default density was not comfortable");
	    click('[data-action="kanban-density"][data-kanban-density="compact"]');
	    await waitFor(() => qs("#kanbanBoard").dataset.kanbanDensity === "compact", "kanban compact density did not activate");
	    assert(qs('#view-pm-kanban [data-issue-id="' + issue.id + '"]').dataset.kanbanCardDensity === "compact", "kanban card density marker did not update");
	    assert(getComputedStyle(qs('#view-pm-kanban [data-issue-id="' + issue.id + '"] .kanban-labels')).display === "none", "kanban compact density did not hide label row");
	    assert(savedPayload().ui && savedPayload().ui.kanbanDensity === "compact", "kanban compact density was not persisted");
	    await nav("pm-portfolio");
	    await nav("pm-kanban");
	    await waitFor(() => qs("#kanbanBoard").dataset.kanbanDensity === "compact", "kanban compact density did not survive rerender");
	    click('[data-action="kanban-density"][data-kanban-density="comfortable"]');
	    await waitFor(() => qs("#kanbanBoard").dataset.kanbanDensity === "comfortable", "kanban comfortable density did not restore");
	    assert(savedPayload().ui && savedPayload().ui.kanbanDensity === "comfortable", "kanban comfortable density reset was not persisted");
	    kanbanDensityPersistenceOk = true;
	    click('[data-action="issue-move"][data-issue-id="' + issue.id + '"][data-status="in-progress"]');
    await waitFor(() => indexes.issueById.get(issue.id).status === "in-progress", "issue did not move to in-progress");
    click('[data-action="issue-add"]');
    fill('#issueForm [name="title"]', title + " peer");
    if (projectId) select('#issueForm [name="project"]', projectId);
    select('#issueForm [name="priority"]', "high");
    select('#issueForm [name="status"]', "in-progress");
    await confirmModal();
    const peerIssue = dashboard.issues.find((item) => item.title === title + " peer");
    assert(peerIssue && peerIssue.status === "in-progress", "peer issue was not saved in in-progress");
    const laneCards = () => Array.from(document.querySelectorAll('#view-pm-kanban [data-kanban-col="in-progress"] .kanban-list > .kanban-card-wrap[data-issue-id]'));
    await waitFor(() => laneCards().some((card) => card.dataset.issueId === issue.id) && laneCards().some((card) => card.dataset.issueId === peerIssue.id), "in-progress lane did not render both issues");
    click('[data-action="issue-order"][data-issue-id="' + issue.id + '"][data-position="bottom"]');
    await waitFor(() => laneCards().at(-1)?.dataset.issueId === issue.id, "issue did not move to bottom of in-progress lane");
    const orderedPayload = savedPayload();
    const persistedIssue = orderedPayload.issues.find((item) => item.id === issue.id);
    const persistedPeerIssue = orderedPayload.issues.find((item) => item.id === peerIssue.id);
    assert(persistedIssue && persistedPeerIssue && Number(persistedIssue.order) > Number(persistedPeerIssue.order), "kanban lane order was not persisted after bottom move");
    await nav("pm-portfolio");
    await nav("pm-kanban");
    await waitFor(() => laneCards().at(-1)?.dataset.issueId === issue.id, "kanban persisted order did not survive rerender");
    const focusedIssueCard = qs('#view-pm-kanban [data-issue-id="' + issue.id + '"]');
    focusedIssueCard.focus();
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowUp", altKey: true, shiftKey: true, bubbles: true, cancelable: true }));
    await waitFor(() => laneCards()[0]?.dataset.issueId === issue.id, "keyboard top move did not reorder kanban lane");
    assert(Number(savedPayload().issues.find((item) => item.id === issue.id)?.order || 0) < Number(savedPayload().issues.find((item) => item.id === peerIssue.id)?.order || 0), "keyboard top move did not persist kanban order");
    kanbanOrderPersistenceOk = true;
    const todoCol = qs('#view-pm-kanban [data-kanban-col="todo"]');
    const todoLane = qs('#view-pm-kanban [data-kanban-col="todo"] .kanban-list');
    const pointerIssueCard = qs('#view-pm-kanban [data-issue-id="' + issue.id + '"]');
    pointerIssueCard.scrollIntoView({ block: "center", inline: "nearest" });
    todoCol.scrollIntoView({ block: "center", inline: "nearest" });
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    const startRect = pointerIssueCard.getBoundingClientRect();
    const targetRect = todoCol.getBoundingClientRect();
    const visibleDropPoint = [
      [targetRect.left + targetRect.width / 2, targetRect.top + Math.min(48, Math.max(18, targetRect.height / 3))],
      [targetRect.left + targetRect.width / 2, targetRect.top + targetRect.height / 2],
      [targetRect.left + Math.min(targetRect.width - 8, Math.max(8, targetRect.width / 2)), targetRect.bottom - Math.min(48, Math.max(18, targetRect.height / 3))],
    ]
      .map(([x, y]) => [Math.max(2, Math.min(window.innerWidth - 2, x)), Math.max(2, Math.min(window.innerHeight - 2, y))])
      .find(([x, y]) => document.elementFromPoint(x, y)?.closest("[data-kanban-col]")?.dataset.kanbanCol === "todo");
    const dropX = visibleDropPoint ? visibleDropPoint[0] : -1;
    const dropY = visibleDropPoint ? visibleDropPoint[1] : -1;
    const dispatchTouchPointer = (node, type, x, y) => {
      node.dispatchEvent(new PointerEvent(type, {
        pointerId: 41,
        pointerType: "touch",
        isPrimary: true,
        bubbles: true,
        cancelable: true,
        clientX: x,
        clientY: y,
        button: 0,
        buttons: type === "pointerup" ? 0 : 1,
      }));
    };
    dispatchTouchPointer(pointerIssueCard, "pointerdown", startRect.left + startRect.width / 2, startRect.top + startRect.height / 2);
    dispatchTouchPointer(todoLane, "pointermove", dropX, dropY);
    dispatchTouchPointer(todoLane, "pointerup", dropX, dropY);
    await waitFor(() => indexes.issueById.get(issue.id).status === "todo", "touch pointer drag did not move issue to todo lane");
    assert(savedPayload().issues.find((item) => item.id === issue.id)?.status === "todo", "touch pointer drag did not persist issue status");
    assert(qs('#view-pm-kanban [data-kanban-col="todo"] [data-issue-id="' + issue.id + '"]'), "touch pointer drag did not render issue in target lane");
    kanbanTouchDragOk = true;
    moveIssue(issue.id, "in-progress", { beforeId: peerIssue.id });
    await waitFor(() => indexes.issueById.get(issue.id).status === "in-progress", "touch drag cleanup did not restore issue to in-progress");
    assert(savedPayload().issues.find((item) => item.id === issue.id)?.status === "in-progress", "touch drag cleanup did not persist restored issue status");
  });

  await runStep("kanban search no-results recovery", async () => {
    await nav("pm-kanban");
    await waitFor(() => document.querySelectorAll('#view-pm-kanban [data-search-result="pm-kanban"]').length > 0, "kanban did not render searchable cards before empty-state search");
    fill("#globalSearch", "NO_MATCH_" + marker);
    await waitFor(() => document.querySelector('#view-pm-kanban [data-search-empty="pm-kanban"]'), "kanban search empty state did not render");
    const empty = qs('#view-pm-kanban [data-search-empty="pm-kanban"]');
    assert(empty.getAttribute("role") === "status", "kanban search empty state does not expose status role");
    assert((document.getElementById("searchCount")?.textContent || "").includes("검색 결과 없음"), "kanban search status did not announce no results");
    click('#view-pm-kanban [data-action="clear-search"]');
    await waitFor(() => !document.querySelector('#view-pm-kanban [data-search-empty="pm-kanban"]'), "kanban search clear did not restore board");
    assert(document.getElementById("globalSearch").value === "", "kanban global search input was not cleared");
    assert(document.activeElement === document.getElementById("globalSearch"), "kanban clear search did not restore focus to global search input");
    assert(document.querySelectorAll('#view-pm-kanban [data-search-result="pm-kanban"]').length > 0, "kanban cards did not return after clearing search");
    kanbanSearchRecoveryOk = true;
  });

  await runStep("gantt task modal save", async () => {
    const name = marker + " task";
    await nav("pm-gantt");
    assert(window.JooParkGanttView && window.JooParkGanttView.version === "joopark-gantt-view/v1" && typeof window.JooParkGanttView.create === "function", "gantt view runtime module was not loaded");
    ganttViewModuleOk = true;
    click('[data-action="task-add"]');
    fill('#taskForm [name="name"]', name);
    if (projectId) select('#taskForm [name="project"]', projectId);
    fill('#taskForm [name="start"]', "2026-06-16");
    fill('#taskForm [name="end"]', "2026-06-18");
    await confirmModal();
    assert(dashboard.gantt.tasks.some((task) => task.name === name), "task was not saved");
  });

  await runStep("gantt svg task opens accessibly", async () => {
    await nav("pm-gantt");
    await waitFor(() => document.querySelector('#view-pm-gantt .gantt-svg [data-action="open-task"][role="button"]'), "gantt SVG task button did not render");
    const svgTask = qs('#view-pm-gantt .gantt-svg [data-action="open-task"][role="button"]');
    assert(svgTask.getAttribute("tabindex") === "0", "gantt SVG task button should be focusable");
    assert((svgTask.getAttribute("aria-label") || "").includes("작업 열기:"), "gantt SVG task button is missing a useful aria-label");
    svgTask.focus();
    assert(document.activeElement === svgTask, "gantt SVG task button did not receive focus");
    svgTask.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true }));
    await waitFor(() => document.querySelector("#sheet.open"), "gantt SVG task Enter did not open task sheet");
    assert((document.getElementById("sheetTitle")?.textContent || "").includes("작업:"), "gantt SVG task did not open a task sheet");
    click('#sheet [data-action="close-sheet"]');
    await waitFor(() => !document.querySelector("#sheet.open"), "gantt SVG task sheet did not close");
    svgTask.focus();
    svgTask.dispatchEvent(new KeyboardEvent("keydown", { key: " ", bubbles: true, cancelable: true }));
    await waitFor(() => document.querySelector("#sheet.open"), "gantt SVG task Space did not open task sheet");
    assert((document.getElementById("sheetTitle")?.textContent || "").includes("작업:"), "gantt SVG task Space did not open a task sheet");
    click('#sheet [data-action="close-sheet"]');
    await waitFor(() => !document.querySelector("#sheet.open"), "gantt SVG task sheet did not close after Space activation");
    ganttSvgTaskAccessibilityOk = true;
  });

  await runStep("gantt search no-results recovery", async () => {
    await nav("pm-gantt");
    await waitFor(() => document.querySelectorAll('#view-pm-gantt [data-search-result="pm-gantt"]').length > 0, "gantt did not render searchable tasks before empty-state search");
    fill("#globalSearch", "NO_MATCH_" + marker);
    await waitFor(() => document.querySelector('#view-pm-gantt [data-search-empty="pm-gantt"]'), "gantt search empty state did not render");
    const empty = qs('#view-pm-gantt [data-search-empty="pm-gantt"]');
    assert(empty.getAttribute("role") === "status", "gantt search empty state does not expose status role");
    assert((document.getElementById("searchCount")?.textContent || "").includes("검색 결과 없음"), "gantt search status did not announce no results");
    click('#view-pm-gantt [data-action="clear-search"]');
    await waitFor(() => !document.querySelector('#view-pm-gantt [data-search-empty="pm-gantt"]'), "gantt search clear did not restore chart");
    assert(document.getElementById("globalSearch").value === "", "gantt global search input was not cleared");
    assert(document.activeElement === document.getElementById("globalSearch"), "gantt clear search did not restore focus to global search input");
    assert(document.querySelectorAll('#view-pm-gantt [data-search-result="pm-gantt"]').length > 0, "gantt tasks did not return after clearing search");
    ganttSearchRecoveryOk = true;
  });

  await runStep("team member modal save", async () => {
    const name = marker + " member";
    await nav("pm-team");
    assert(window.JooParkTeamView && window.JooParkTeamView.version === "joopark-team-view/v1" && typeof window.JooParkTeamView.create === "function", "team view runtime module was not loaded");
    teamViewModuleOk = true;
    click('[data-action="member-add"]');
    fill('#memberForm [name="name"]', name);
    fill('#memberForm [name="role"]', "QA");
    fill('#memberForm [name="load"]', "33");
    await confirmModal();
    assert(dashboard.team.some((member) => member.name === name && member.load === 33), "team member was not saved");
  });

  await runStep("team search no-results recovery", async () => {
    await nav("pm-team");
    await waitFor(() => document.querySelectorAll('#view-pm-team [data-search-result="pm-team"]').length > 0, "team did not render searchable members before empty-state search");
    fill("#globalSearch", "NO_MATCH_" + marker);
    await waitFor(() => document.querySelector('#view-pm-team [data-search-empty="pm-team"]'), "team search empty state did not render");
    const empty = qs('#view-pm-team [data-search-empty="pm-team"]');
    assert(empty.getAttribute("role") === "status", "team search empty state does not expose status role");
    assert(!!document.querySelector('#view-pm-team [data-team-matrix-empty="search"]'), "team search did not render matrix empty state");
    assert((document.getElementById("searchCount")?.textContent || "").includes("검색 결과 없음"), "team search status did not announce no results");
    click('#view-pm-team [data-action="clear-search"]');
    await waitFor(() => !document.querySelector('#view-pm-team [data-search-empty="pm-team"]'), "team search clear did not restore members");
    assert(!document.querySelector('#view-pm-team [data-team-matrix-empty="search"]'), "team matrix empty state did not clear");
    assert(document.getElementById("globalSearch").value === "", "team global search input was not cleared");
    assert(document.activeElement === document.getElementById("globalSearch"), "team clear search did not restore focus to global search input");
    assert(document.querySelectorAll('#view-pm-team [data-search-result="pm-team"]').length > 0, "team member rows did not return after clearing search");
    teamSearchRecoveryOk = true;
  });

  let instanceId = "";
  await runStep("db instance modal save", async () => {
    const name = marker + " db";
    assert(window.JooParkDbCatalog && window.JooParkDbCatalog.version === "joopark-db-catalog/v1" && typeof window.JooParkDbCatalog.create === "function", "db catalog runtime module was not loaded");
    assert(window.JooParkReviewHandoff && window.JooParkReviewHandoff.version === "joopark-review-handoff-runtime/v1" && typeof window.JooParkReviewHandoff.create === "function", "review handoff runtime module was not loaded");
    assert(window.JooParkReviewResultView && window.JooParkReviewResultView.version === "joopark-review-result-view/v1" && typeof window.JooParkReviewResultView.create === "function", "review result view runtime module was not loaded");
    assert(window.JooParkReviewResultState && window.JooParkReviewResultState.version === "joopark-review-result-state/v1" && typeof window.JooParkReviewResultState.create === "function", "review result state runtime module was not loaded");
    assert(window.JooParkReviewIssuePayload && window.JooParkReviewIssuePayload.version === "joopark-review-issue-payload/v1" && typeof window.JooParkReviewIssuePayload.create === "function", "review issue payload runtime module was not loaded");
    assert(window.JooParkReviewResultDraftState && window.JooParkReviewResultDraftState.version === "joopark-review-result-draft-state/v1" && typeof window.JooParkReviewResultDraftState.create === "function", "review result draft state runtime module was not loaded");
    assert(window.JooParkReviewCreationActions && window.JooParkReviewCreationActions.version === "joopark-review-creation-actions/v1" && typeof window.JooParkReviewCreationActions.create === "function", "review creation actions runtime module was not loaded");
    assert(window.JooParkReviewPackageView && window.JooParkReviewPackageView.version === "joopark-review-package-view/v1" && typeof window.JooParkReviewPackageView.create === "function", "review package view runtime module was not loaded");
    assert(window.JooParkReviewArtifactView && window.JooParkReviewArtifactView.version === "joopark-review-artifact-view/v1" && typeof window.JooParkReviewArtifactView.create === "function", "review artifact view runtime module was not loaded");
    assert(window.JooParkReviewArtifactState && window.JooParkReviewArtifactState.version === "joopark-review-artifact-state/v1" && typeof window.JooParkReviewArtifactState.create === "function", "review artifact state runtime module was not loaded");
    assert(window.JooParkReviewCopyActions && window.JooParkReviewCopyActions.version === "joopark-review-copy-actions/v1" && typeof window.JooParkReviewCopyActions.create === "function", "review copy actions runtime module was not loaded");
    assert(window.JooParkReviewSubmissionCopy && window.JooParkReviewSubmissionCopy.version === "joopark-review-submission-copy/v1" && typeof window.JooParkReviewSubmissionCopy.create === "function", "review submission copy runtime module was not loaded");
    assert(window.JooParkReviewRecommendationExport && window.JooParkReviewRecommendationExport.version === "joopark-review-recommendation-export/v1" && typeof window.JooParkReviewRecommendationExport.create === "function", "review recommendation export runtime module was not loaded");
    dbCatalogModuleOk = true;
    reviewHandoffModuleOk = true;
    reviewResultViewModuleOk = true;
    reviewResultStateModuleOk = true;
    reviewExecutionChecklistModuleOk = true;
    reviewIssuePayloadModuleOk = true;
    reviewResultDraftStateModuleOk = true;
    reviewCreationActionsModuleOk = true;
    reviewPackageViewModuleOk = true;
    reviewArtifactViewModuleOk = true;
    reviewArtifactStateModuleOk = true;
    reviewCopyActionsModuleOk = true;
    reviewSubmissionCopyModuleOk = true;
    reviewRecommendationExportModuleOk = true;
    await nav("dbm-instances");
    const catalogBoundary = qs('#view-dbm-instances [data-db-catalog-provenance]');
    assert(catalogBoundary.dataset.dbCatalogLive === "false" && Number(catalogBoundary.dataset.dbCatalogSampleCount || 0) > 0 && Number(catalogBoundary.dataset.dbCatalogStaleCount || 0) > 0 && catalogBoundary.textContent.includes("local catalog") && catalogBoundary.textContent.includes("no live connection"), "db catalog provenance boundary did not expose local/no-live sample status");
    const sampleBadge = qs('#view-dbm-instances [data-db-catalog-source="sample"]');
    assert(sampleBadge.dataset.dbCatalogFreshnessStatus === "stale" && sampleBadge.dataset.dbCatalogUpdatedAt, "db catalog sample badge did not expose stale source metadata");
    click('[data-action="instance-add"]');
    fill('#instanceForm [name="name"]', name);
    fill('#instanceForm [name="engine"]', "PostgreSQL 16");
    fill('#instanceForm [name="region"]', "ap-northeast-2");
    fill('#instanceForm [name="cpu"]', "11");
    fill('#instanceForm [name="mem"]', "22");
    fill('#instanceForm [name="conn"]', "7");
    fill('#instanceForm [name="connMax"]', "70");
    fill('#instanceForm [name="latencyMs"]', "4");
    await confirmModal();
    const instance = dashboard.dbInstances.find((item) => item.name === name);
    assert(instance && instance.cpu === 11, "db instance was not saved");
	    assert(instance.catalogSource === "manual" && !!instance.catalogUpdatedAt, "manual db instance provenance was not saved");
	    assert(qs('#view-dbm-instances [data-action="pick-instance"][data-instance-id="' + instance.id + '"] [data-db-catalog-source="manual"]').dataset.dbCatalogFreshnessStatus === "fresh", "manual db instance badge did not render fresh provenance");
	    assert(savedPayload().dbInstances.some((item) => item.id === instance.id && item.catalogSource === "manual" && item.catalogUpdatedAt), "manual db instance provenance was not persisted");
	    click('#view-dbm-instances [data-action="db-catalog-filter"][data-db-catalog-filter-option="manual"]');
	    await waitFor(() => qs('#view-dbm-instances [data-db-catalog-provenance]').dataset.dbCatalogFilterCurrent === "manual", "db catalog manual filter did not activate");
	    assert(qs('#view-dbm-instances [data-action="pick-instance"][data-instance-id="' + instance.id + '"]'), "manual db catalog filter did not keep manual instance visible");
	    assert(!document.querySelector('#view-dbm-instances [data-db-catalog-source="sample"]'), "manual db catalog filter left sample records visible");
	    click('#view-dbm-instances [data-action="db-catalog-filter"][data-db-catalog-filter-option="stale-sample"]');
	    await waitFor(() => qs('#view-dbm-instances [data-db-catalog-provenance]').dataset.dbCatalogFilterCurrent === "stale-sample", "db catalog stale sample filter did not activate");
	    assert(qs('#view-dbm-instances [data-db-catalog-source="sample"][data-db-catalog-freshness-status="stale"]'), "stale sample db catalog filter did not show stale sample records");
	    assert(!document.querySelector('#view-dbm-instances [data-action="pick-instance"][data-instance-id="' + instance.id + '"]'), "stale sample db catalog filter left manual instance visible");
	    click('#view-dbm-instances [data-action="db-catalog-filter"][data-db-catalog-filter-option="imported"]');
	    await waitFor(() => qs('#view-dbm-instances [data-db-catalog-filter-empty="인스턴스"]'), "db catalog imported filter did not expose empty filter state");
	    click('#view-dbm-instances [data-action="db-catalog-filter"][data-db-catalog-filter-option="all"]');
	    await waitFor(() => qs('#view-dbm-instances [data-db-catalog-provenance]').dataset.dbCatalogFilterCurrent === "all", "db catalog filter did not reset to all");
    const staleAction = qs('#view-dbm-instances [data-db-catalog-stale-action]');
    assert(staleAction.dataset.dbCatalogStaleActionExisting === "false" && Number(staleAction.dataset.dbCatalogStaleActionCount || 0) > 0, "db catalog stale action did not expose initial review state");
    click('#view-dbm-instances [data-action="db-catalog-create-stale-issue"]');
    await waitFor(() => dashboard.currentView === "pm-kanban" && location.hash === "#pm-kanban", "db catalog stale action did not navigate to kanban");
    const staleIssueKey = "db-catalog:stale-sample-review";
    const staleIssue = savedPayload().issues.find((issue) => issue.sourceKey === staleIssueKey);
	    assert(staleIssue && staleIssue.title.includes("[DB Catalog]") && staleIssue.sourceKind === "db-catalog-stale-review" && staleIssue.labels.includes("stale-sample") && staleIssue.body.includes("Boundary: local catalog only") && staleIssue.executionChecklistReady, "db catalog stale action issue draft was not persisted with source metadata");
	    await waitFor(() => qs('#view-pm-kanban [data-issue-id="' + staleIssue.id + '"] [data-kanban-source-kind="db-catalog-stale-review"]'), "db catalog stale action issue did not render kanban source badge");
	    assert(qs('#view-pm-kanban [data-issue-id="' + staleIssue.id + '"] [data-kanban-source-kind="db-catalog-stale-review"]').textContent.includes("DB Catalog"), "db catalog kanban source badge label did not render");
    const dbDirectSourceBadge = qs('#view-pm-kanban [data-issue-id="' + staleIssue.id + '"] [data-kanban-source-direct-return="true"]');
    assert(dbDirectSourceBadge.tagName === "BUTTON" && dbDirectSourceBadge.dataset.action === "open-issue-source" && dbDirectSourceBadge.getAttribute("aria-label").includes("DB Catalog"), "db catalog source badge did not expose direct source return button");
	    assert(qs('#view-pm-kanban [data-action="filter-kanban-source"][data-kanban-source-filter="wiki"]').textContent.includes("0"), "empty wiki source filter did not expose a zero count before wiki issue creation");
	    click('#view-pm-kanban [data-action="filter-kanban-source"][data-kanban-source-filter="wiki"]');
	    await waitFor(() => qs('#view-pm-kanban [data-kanban-source-filterbar]').dataset.kanbanSourceFilterCurrent === "wiki", "empty wiki source filter did not activate");
	    const emptySourceSummary = qs('#view-pm-kanban [data-kanban-source-summary]');
	    assert(emptySourceSummary && emptySourceSummary.dataset.kanbanSourceSummaryFilter === "wiki" && emptySourceSummary.dataset.kanbanSourceSummaryCount === "0" && emptySourceSummary.textContent.includes("LLM Wiki") && emptySourceSummary.textContent.includes("0건"), "empty wiki source filter summary did not render");
	    const sourceEmpty = qs('#view-pm-kanban [data-kanban-source-empty]');
	    assert(sourceEmpty.dataset.kanbanSourceEmptyFilter === "wiki" && sourceEmpty.textContent.includes("LLM Wiki") && sourceEmpty.textContent.includes("전체 출처 보기"), "empty wiki source filter did not render a clearable source empty state");
	    click('[data-action="filter-kanban-source"][data-kanban-source-filter="all"]', sourceEmpty);
	    await waitFor(() => qs('#view-pm-kanban [data-kanban-source-filterbar]').dataset.kanbanSourceFilterCurrent === "all", "source empty clear action did not reset to all");
	    click('#view-pm-kanban [data-action="filter-kanban-source"][data-kanban-source-filter="db"]');
	    await waitFor(() => qs('#view-pm-kanban [data-kanban-source-filterbar]').dataset.kanbanSourceFilterCurrent === "db", "db catalog source filter did not activate");
	    const dbSourceSummary = qs('#view-pm-kanban [data-kanban-source-summary]');
    assert(dbSourceSummary && dbSourceSummary.dataset.kanbanSourceSummaryFilter === "db" && dbSourceSummary.dataset.kanbanSourceSummaryCount === "1" && dbSourceSummary.textContent.includes("DB Catalog") && dbSourceSummary.textContent.includes("1건"), "db catalog source filter summary did not render active scope");
	    assert(qs('#view-pm-kanban [data-issue-id="' + staleIssue.id + '"]') && qsa('#view-pm-kanban [data-search-result="pm-kanban"]').every((card) => card.querySelector('[data-kanban-source-kind="db-catalog-stale-review"]')), "db catalog source filter did not isolate db catalog issues");
    click('[data-action="filter-kanban-source"][data-kanban-source-filter="all"]', dbSourceSummary);
    await waitFor(() => qs('#view-pm-kanban [data-kanban-source-filterbar]').dataset.kanbanSourceFilterCurrent === "all", "db catalog source filter did not reset to all");
    click('[data-action="open-palette"]');
    fill("#paletteInput", "칸반 데이터 카탈로그 출처");
    await waitFor(() => qsa("#paletteResults .pal-item").some((item) => item.textContent.includes("Kanban: DB Catalog 출처 보기")), "db catalog Korean source filter command did not render in palette");
    qsa("#paletteResults .pal-item").find((item) => item.textContent.includes("Kanban: DB Catalog 출처 보기")).click();
    await waitFor(() => dashboard.currentView === "pm-kanban" && qs('#view-pm-kanban [data-kanban-source-filterbar]').dataset.kanbanSourceFilterCurrent === "db", "db catalog Korean source palette command did not apply db filter");
    assert(qs('#view-pm-kanban [data-issue-id="' + staleIssue.id + '"]') && qsa('#view-pm-kanban [data-search-result="pm-kanban"]').every((card) => card.querySelector('[data-kanban-source-kind="db-catalog-stale-review"]')), "db catalog Korean source palette command did not isolate db catalog issues");
    click('#view-pm-kanban [data-action="filter-kanban-source"][data-kanban-source-filter="all"]');
    await waitFor(() => qs('#view-pm-kanban [data-kanban-source-filterbar]').dataset.kanbanSourceFilterCurrent === "all", "db catalog Korean source palette command did not reset to all");
    dbCatalogKoreanSourceFilterCommandOk = true;
    click('#view-pm-kanban [data-issue-id="' + staleIssue.id + '"] [data-action="open-issue"]');
    await waitFor(() => document.querySelector('#sheet.open [data-action="open-issue-source"]'), "db catalog issue sheet did not expose source return action");
    const dbSourceReturn = qs('#sheet.open [data-action="open-issue-source"]');
    assert(dbSourceReturn.textContent.includes("DB Catalog") && dbSourceReturn.textContent.includes("stale sample"), "db catalog source return action label was incomplete");
    dbSourceReturn.click();
    await waitFor(() => dashboard.currentView === "dbm-instances" && qs('#view-dbm-instances [data-db-catalog-provenance]').dataset.dbCatalogFilterCurrent === "stale-sample", "db catalog source return did not open stale sample queue");
    const dbBacklink = qs('#view-dbm-instances [data-source-backlink][data-source-backlink-surface="db-catalog"]');
    assert(dbBacklink.dataset.sourceBacklinkIssueId === staleIssue.id && dbBacklink.textContent.includes(staleIssue.id) && dbBacklink.textContent.includes("Kanban 이슈로 돌아가기"), "db catalog source backlink did not render the originating issue");
    click('[data-action="open-source-backlink-issue"]', dbBacklink);
    await waitFor(() => dashboard.currentView === "pm-kanban" && qs('#view-pm-kanban [data-kanban-source-filterbar]').dataset.kanbanSourceFilterCurrent === "db" && qs('#sheet.open [data-action="open-issue-source"]'), "db catalog source backlink did not reopen the originating kanban issue");
    assert(qs("#sheet.open").textContent.includes(staleIssue.id), "db catalog source backlink opened the wrong issue sheet");
    click('#sheet [data-action="close-sheet"]');
    await waitFor(() => !document.querySelector("#sheet.open"), "db catalog source backlink sheet did not close");
    issueSourceBacklinkDbOk = true;
    await nav("dbm-instances");
    await waitFor(() => qs('#view-dbm-instances [data-db-catalog-provenance]').dataset.dbCatalogFilterCurrent === "stale-sample", "db catalog source backlink return did not preserve stale sample filter before reset");
    click('#view-dbm-instances [data-action="db-catalog-filter"][data-db-catalog-filter-option="all"]');
    await waitFor(() => qs('#view-dbm-instances [data-db-catalog-provenance]').dataset.dbCatalogFilterCurrent === "all", "db catalog source return reset did not clear stale sample filter");
	    await nav("dbm-instances");
    await waitFor(() => qs('#view-dbm-instances [data-db-catalog-stale-action]').dataset.dbCatalogStaleActionExisting === "true", "db catalog stale action did not render created state");
    assert(qs('#view-dbm-instances [data-db-catalog-stale-action]').dataset.dbCatalogStaleActionIssueId === staleIssue.id, "db catalog stale action did not expose created issue id");
    click('#view-dbm-instances [data-action="db-catalog-create-stale-issue"]');
	    await waitFor(() => dashboard.currentView === "pm-kanban" && qs('#view-pm-kanban [data-kanban-source-filterbar]').dataset.kanbanSourceFilterCurrent === "db" && qs('#sheet.open [data-action="open-issue-source"]'), "db catalog stale duplicate action did not open existing issue surface");
	    assert(qs("#sheet.open").textContent.includes(staleIssue.id) && savedPayload().issues.filter((issue) => issue.sourceKey === staleIssueKey).length === 1, "db catalog stale duplicate action opened the wrong issue or created more than one issue");
    click('#sheet [data-action="close-sheet"]');
    await waitFor(() => !document.querySelector("#sheet.open"), "db catalog stale duplicate issue sheet did not close");
    click('[data-action="open-palette"]');
    fill("#paletteInput", "DB Catalog 출처");
    await waitFor(() => qsa("#paletteResults .pal-item").some((item) => item.textContent.includes(staleIssue.title) && item.textContent.includes(staleIssue.id) && item.textContent.includes("DB Catalog")), "db catalog source label search did not render sourced palette issue");
    qsa("#paletteResults .pal-item").find((item) => item.textContent.includes(staleIssue.title) && item.textContent.includes(staleIssue.id) && item.textContent.includes("DB Catalog")).click();
	    await waitFor(() => dashboard.currentView === "pm-kanban" && qs('#view-pm-kanban [data-kanban-source-filterbar]').dataset.kanbanSourceFilterCurrent === "db" && qs('#sheet.open [data-action="open-issue-source"]'), "db catalog source label palette result did not open issue sheet in source scope");
    click('#sheet [data-action="close-sheet"]');
    await waitFor(() => !document.querySelector("#sheet.open"), "db catalog source label palette sheet did not close");
    click('[data-action="open-palette"]');
    fill("#paletteInput", "데이터 카탈로그 출처");
    await waitFor(() => qsa("#paletteResults .pal-item").some((item) => item.textContent.includes(staleIssue.title) && item.textContent.includes(staleIssue.id) && item.textContent.includes("DB Catalog")), "db catalog Korean source alias search did not render sourced palette issue");
    qsa("#paletteResults .pal-item").find((item) => item.textContent.includes(staleIssue.title) && item.textContent.includes(staleIssue.id) && item.textContent.includes("DB Catalog")).click();
    await waitFor(() => dashboard.currentView === "pm-kanban" && qs('#view-pm-kanban [data-kanban-source-filterbar]').dataset.kanbanSourceFilterCurrent === "db" && qs('#sheet.open [data-action="open-issue-source"]'), "db catalog Korean source alias palette result did not open issue sheet in source scope");
    click('#sheet [data-action="close-sheet"]');
    await waitFor(() => !document.querySelector("#sheet.open"), "db catalog Korean source alias palette sheet did not close");
    sourceIssueExistingDbOk = true;
    sourceDbPaletteLabelSearchOk = true;
    sourceDbKoreanAliasSearchOk = true;
	    kanbanSourceEmptyOk = true;
	    dbCatalogStaleActionOk = true;
	    dbCatalogProvenanceFilterOk = true;
	    dbCatalogProvenanceOk = true;
	    instanceId = instance.id;
	  });

  await runStep("db instance search no-results recovery", async () => {
    await nav("dbm-instances");
    await waitFor(() => document.querySelectorAll('#view-dbm-instances [data-search-result="dbm-instances"]').length > 0, "db instances did not render searchable cards before empty-state search");
    fill("#globalSearch", "NO_MATCH_" + marker);
    await waitFor(() => document.querySelector('#view-dbm-instances [data-search-empty="dbm-instances"]'), "db instance search empty state did not render");
    const empty = qs('#view-dbm-instances [data-search-empty="dbm-instances"]');
    assert(empty.getAttribute("role") === "status", "db instance search empty state does not expose status role");
    assert((document.getElementById("searchCount")?.textContent || "").includes("검색 결과 없음"), "db instance search status did not announce no results");
    click('#view-dbm-instances [data-action="clear-search"]');
    await waitFor(() => !document.querySelector('#view-dbm-instances [data-search-empty="dbm-instances"]'), "db instance search clear did not restore results");
    assert(document.getElementById("globalSearch").value === "", "db instance search input was not cleared");
    assert(document.activeElement === document.getElementById("globalSearch"), "db instance clear search did not restore focus to global search input");
    assert(document.querySelectorAll('#view-dbm-instances [data-search-result="dbm-instances"]').length > 0, "db instance cards did not return after clearing search");
    dbInstancesSearchRecoveryOk = true;
  });

  await runStep("schema table modal save", async () => {
    const tableName = "release_smoke_" + marker.toLowerCase().replace(/[^a-z0-9]+/g, "_");
    await nav("dbm-schema");
    click('[data-action="table-add"]');
    if (instanceId) select('#tableForm [name="instanceId"]', instanceId);
    fill('#tableForm [name="dbName"]', "release");
    fill('#tableForm [name="tableName"]', tableName);
    fill('#tableForm [name="rows"]', "12");
    fill('#tableForm [name="sizeMb"]', "3");
    await confirmModal();
    const savedTable = dashboard.schemas.flatMap((schema) => schema.databases || []).flatMap((db) => db.tables || []).find((table) => table.name === tableName);
    assert(savedTable && savedTable.catalogSource === "manual" && savedTable.catalogUpdatedAt, "table was not saved with manual provenance");
  });

  await runStep("db schema search no-results recovery", async () => {
    await nav("dbm-schema");
    await waitFor(() => document.querySelectorAll('#view-dbm-schema [data-search-result="dbm-schema"]').length > 0, "db schema did not render searchable tables before empty-state search");
    fill("#globalSearch", "NO_MATCH_" + marker);
    await waitFor(() => document.querySelector('#view-dbm-schema [data-search-empty="dbm-schema"]'), "db schema search empty state did not render");
    const empty = qs('#view-dbm-schema [data-search-empty="dbm-schema"]');
    assert(empty.getAttribute("role") === "status", "db schema search empty state does not expose status role");
    assert((document.getElementById("searchCount")?.textContent || "").includes("검색 결과 없음"), "db schema search status did not announce no results");
    click('#view-dbm-schema [data-action="clear-search"]');
    await waitFor(() => !document.querySelector('#view-dbm-schema [data-search-empty="dbm-schema"]'), "db schema search clear did not restore results");
    assert(document.getElementById("globalSearch").value === "", "db schema search input was not cleared");
    assert(document.activeElement === document.getElementById("globalSearch"), "db schema clear search did not restore focus to global search input");
    assert(document.querySelectorAll('#view-dbm-schema [data-search-result="dbm-schema"]').length > 0, "db schema table results did not return after clearing search");
    dbSchemaSearchRecoveryOk = true;
  });

  await runStep("saved query modal save", async () => {
    const text = "SELECT '" + marker + "' AS smoke";
    await nav("dbm-queries");
    click('[data-action="query-add"]');
    if (instanceId) select('#queryForm [name="instance"]', instanceId);
    fill('#queryForm [name="db"]', "release");
    fill('#queryForm [name="text"]', text);
    fill('#queryForm [name="avgMs"]', "17");
    fill('#queryForm [name="p95Ms"]', "25");
    fill('#queryForm [name="count"]', "2");
    await confirmModal();
    const savedQuery = dashboard.queries.find((query) => query.text === text && query.avgMs === 17);
    assert(savedQuery && savedQuery.catalogSource === "manual" && savedQuery.catalogUpdatedAt, "query was not saved with manual provenance");
  });

  await runStep("db query search no-results recovery", async () => {
    await nav("dbm-queries");
    await waitFor(() => document.querySelectorAll('#view-dbm-queries [data-search-result="dbm-queries"]').length > 0, "db queries did not render searchable rows before empty-state search");
    fill("#globalSearch", "NO_MATCH_" + marker);
    await waitFor(() => document.querySelector('#view-dbm-queries [data-search-empty="dbm-queries"]'), "db query search empty state did not render");
    const empty = qs('#view-dbm-queries [data-search-empty="dbm-queries"]');
    assert(empty.getAttribute("role") === "status", "db query search empty state does not expose status role");
    assert((document.getElementById("searchCount")?.textContent || "").includes("검색 결과 없음"), "db query search status did not announce no results");
    click('#view-dbm-queries [data-action="clear-search"]');
    await waitFor(() => !document.querySelector('#view-dbm-queries [data-search-empty="dbm-queries"]'), "db query search clear did not restore results");
    assert(document.getElementById("globalSearch").value === "", "db query search input was not cleared");
    assert(document.activeElement === document.getElementById("globalSearch"), "db query clear search did not restore focus to global search input");
    assert(document.querySelectorAll('#view-dbm-queries [data-search-result="dbm-queries"]').length > 0, "db query rows did not return after clearing search");
    dbQueriesSearchRecoveryOk = true;
  });

  await runStep("migration modal save", async () => {
    const title = marker + " migration";
    await nav("dbm-backups");
    click('[data-action="migration-add"]');
    if (instanceId) select('#migrationForm [name="instance"]', instanceId);
    fill('#migrationForm [name="title"]', title);
    select('#migrationForm [name="status"]', "pending");
    fill('#migrationForm [name="migDate"]', "2026-06-20");
    await confirmModal();
    const savedMigration = dashboard.migrations.find((migration) => migration.title === title && migration.status === "pending");
    assert(savedMigration && savedMigration.catalogSource === "manual" && savedMigration.catalogUpdatedAt, "migration was not saved with manual provenance");
  });

  await runStep("backup search no-results recovery", async () => {
    await nav("dbm-backups");
    fill("#globalSearch", "NO_MATCH_" + marker);
    await waitFor(() => document.querySelector('#view-dbm-backups [data-search-empty="dbm-backups"]'), "backup search empty state did not render");
    const empty = qs('#view-dbm-backups [data-search-empty="dbm-backups"]');
    assert(empty.getAttribute("role") === "status", "backup search empty state does not expose status role");
    assert((document.getElementById("searchCount")?.textContent || "").includes("검색 결과 없음"), "backup search status did not announce no results");
    click('#view-dbm-backups [data-action="clear-search"]');
    await waitFor(() => !document.querySelector('#view-dbm-backups [data-search-empty="dbm-backups"]'), "backup search clear did not restore results");
    assert(document.getElementById("globalSearch").value === "", "backup search input was not cleared");
    assert(document.activeElement === document.getElementById("globalSearch"), "backup clear search did not restore focus to global search input");
    assert(document.querySelectorAll('#view-dbm-backups [data-search-result]').length > 0, "backup and migration results did not return after clearing search");
    backupSearchRecoveryOk = true;
  });

  await runStep("settings save and theme", async () => {
    const name = marker + " user";
    await nav("settings");
    await waitFor(() => document.querySelector("[data-storage-health]"), "storage health panel did not render");
    assert(window.JooParkWorkspaceStorage && window.JooParkWorkspaceStorage.version === "joopark-workspace-storage/v1" && typeof window.JooParkWorkspaceStorage.create === "function", "workspace storage runtime module was not loaded");
    workspaceStorageModuleOk = true;
    assert(window.JooParkStorageStatusView && window.JooParkStorageStatusView.version === "joopark-storage-status-view/v1" && typeof window.JooParkStorageStatusView.create === "function", "storage status view runtime module was not loaded");
    storageStatusViewModuleOk = true;
    click('[data-action="refresh-storage-health"]');
    await waitFor(() => {
      const status = document.querySelector("#storageHealthStatus");
      const local = document.querySelector("[data-storage-local]");
      const updated = document.querySelector("#storageHealthUpdated");
      return status && status.textContent.trim().length > 0 &&
        local && /\\d/.test(local.textContent) &&
        updated && updated.textContent.trim().length > 0;
    }, "storage health status did not populate");
    fill('.settings-form [name="displayName"]', name);
    qs(".settings-form").requestSubmit();
    await waitFor(() => document.querySelector(".user strong").textContent === name, "display name did not update");
    click('[data-action="set-theme"][data-theme="light"]');
    await waitFor(() => document.documentElement.getAttribute("data-theme") === "light", "light theme did not apply");
    const payload = savedPayload();
    assert(payload.settings.displayName === name, "settings display name was not persisted");
    assert(payload.ui.theme === "light", "theme was not persisted");
  });

  await runStep("settings export backup payload", async () => {
    await nav("settings");
    const originalCreateObjectURL = URL.createObjectURL.bind(URL);
    window.__smokeExportText = "";
    window.__smokeExportType = "";
    window.__smokeExportName = "";
    URL.createObjectURL = (blob) => {
      window.__smokeExportType = blob.type || "";
      blob.text().then((text) => { window.__smokeExportText = text; });
      return originalCreateObjectURL(blob);
    };
    const originalAppendChild = document.body.appendChild.bind(document.body);
    document.body.appendChild = (node) => {
      if (node && node.tagName === "A" && node.download) window.__smokeExportName = node.download;
      return originalAppendChild(node);
    };
    try {
      click('[data-action="export-data"]');
      await waitFor(() => window.__smokeExportText && window.__smokeExportText.length > 200, "backup export payload was not captured");
    } finally {
      URL.createObjectURL = originalCreateObjectURL;
      document.body.appendChild = originalAppendChild;
    }

    const exported = JSON.parse(window.__smokeExportText);
    const requiredArrays = ["events", "todos", "notes", "habits", "projects", "issues", "team", "dbInstances", "schemas", "queries", "migrations"];
    const missingArrays = requiredArrays.filter((key) => !Array.isArray(exported[key]));
    assert(missingArrays.length === 0, "export is missing arrays: " + missingArrays.join(", "));
    assert(exported.app === "JooPark Workspace", "export app name is wrong");
    assert(exported.v === 3, "export version is wrong");
    assert(exported.exportedAt, "export timestamp is missing");
    assert(exported.ui && exported.ui.theme === "light", "exported theme is wrong");
    assert(exported.imports && typeof exported.imports === "object", "exported imports registry is missing");
    assert(window.__smokeExportType.includes("application/json"), "export MIME type is not JSON");
    assert(/^joopark-workspace-\\d{4}-\\d{2}-\\d{2}\\.json$/.test(window.__smokeExportName), "export filename is not dated JSON");
    assert(exported.events.some((event) => event.title === marker + " event"), "exported event is missing");
    assert(exported.todos.some((todo) => todo.title === marker + " todo" && todo.done), "exported done todo is missing");
    assert(exported.notes.some((note) => note.title === marker + " note" && note.pinned), "exported pinned note is missing");
    assert(exported.projects.some((project) => project.name === marker + " project"), "exported project is missing");
    const exportedIssue = exported.issues.find((issue) => issue.title === marker + " issue");
    assert(exportedIssue && exportedIssue.status === "in-progress", "exported issue is missing or has wrong status: " + JSON.stringify(exportedIssue || null));
    assert(exported.dbInstances.some((instance) => instance.name === marker + " db"), "exported DB instance is missing");
    assert(exported.queries.some((query) => query.text === "SELECT '" + marker + "' AS smoke"), "exported saved query is missing");
    backupExportOk = true;
  });

  await runStep("operations runtime modules load independently", async () => {
    assert(window.JooParkSettingsView && window.JooParkSettingsView.version === "joopark-settings-view/v1" && typeof window.JooParkSettingsView.create === "function", "settings view runtime module was not loaded");
    settingsViewModuleOk = true;
    assert(window.JooParkSystemStatusView && window.JooParkSystemStatusView.version === "joopark-system-status-view/v1" && typeof window.JooParkSystemStatusView.create === "function", "system status view runtime module was not loaded");
    systemStatusViewModuleOk = true;
    assert(window.JooParkOpsRuntime && window.JooParkOpsRuntime.version === "joopark-ops-runtime-loader/v1" && typeof window.JooParkOpsRuntime.load === "function", "operations runtime loader was not available");
    await window.JooParkOpsRuntime.load("release");
    await waitFor(() => window.JooParkReleaseStatus && window.JooParkReleaseStatus.version === "joopark-release-status/v1" && typeof window.JooParkReleaseStatus.create === "function", "release status runtime module was not loaded");
    assert(Array.isArray(window.JooParkReleaseStatus.readinessItems) && window.JooParkReleaseStatus.readinessItems.some((item) => item.key === "publish-evidence-capture"), "release status runtime did not expose publish readiness items");
    releaseStatusModuleOk = true;
  });

  await runStep("settings operational handoff copy", async () => {
    await nav("settings");
    assert(window.JooParkSettingsView && window.JooParkSettingsView.version === "joopark-settings-view/v1" && typeof window.JooParkSettingsView.create === "function", "settings view runtime module was not loaded");
    const settingsKpis = qs('[data-settings-view-module="joopark-settings-view/v1"]');
    assert(settingsKpis.querySelectorAll(".kpi").length === 4, "settings view runtime module did not render KPI cards");
    const backupCard = qs("[data-settings-backup-handoff]");
    const deployCard = qs("[data-settings-deploy-handoff]");
    const privacyCard = qs("[data-settings-privacy-handoff]");
    const handoffList = qs('#view-settings [data-settings-handoff] [role="list"]');
    const handoffItems = qsa('[role="listitem"]', handoffList);
    assert((handoffList.getAttribute("aria-label") || "").includes("운영 handoff") && handoffItems.length === 3, "settings handoff list semantics were incomplete");
    assert(backupCard.innerText.includes("백업") && backupCard.innerText.includes("초기화"), "backup handoff card does not explain backup/reset flow");
    assert(deployCard.innerText.includes("GitHub Pages") && deployCard.innerText.includes("workflow") && deployCard.innerText.includes("device-code") && deployCard.innerText.includes("workflowScopeAvailable: true"), "deploy handoff card does not explain Pages workflow and device-code approval");
    assert(privacyCard.innerText.includes("localStorage") && privacyCard.innerText.includes("민감") && privacyCard.innerText.includes("JSON"), "privacy handoff card does not explain local storage safety");
    const backupButton = qs('[data-settings-handoff-copy="backup"]', backupCard);
    const deployButton = qs('[data-settings-handoff-copy="deploy"]', deployCard);
    const privacyButton = qs('[data-settings-handoff-copy="privacy"]', privacyCard);
    const deployHandoffText = deployButton.dataset.settingsHandoffText || "";
    assert((backupButton.dataset.settingsHandoffText || "").includes("JooPark Workspace Backup Handoff"), "backup handoff copy text is missing title");
    assert((backupButton.dataset.settingsHandoffText || "").includes("localStorage bytes"), "backup handoff copy text is missing storage evidence");
    assert((backupButton.dataset.settingsHandoffText || "").includes("가져오기는 현재 브라우저 데이터를 대체합니다"), "backup handoff copy text is missing import replacement warning");
    assert((deployButton.dataset.settingsHandoffText || "").includes("npm run verify"), "deploy handoff copy text is missing verify command");
    assert((deployButton.dataset.settingsHandoffText || "").includes("prepare-github-pages-workflow.mjs --dry-run --check-scope"), "deploy handoff copy text is missing Pages scope preflight");
    assert((deployButton.dataset.settingsHandoffText || "").includes("workflow-scope token"), "deploy handoff copy text is missing workflow-scope guidance");
    assert((deployButton.dataset.settingsHandoffText || "").includes("pages: write") && (deployButton.dataset.settingsHandoffText || "").includes("actions/deploy-pages"), "deploy handoff copy text is missing Pages permission/action guidance");
    assert((deployButton.dataset.settingsHandoffText || "").includes("workflowScopeAvailable"), "deploy handoff copy text is missing workflow scope availability guidance");
    assert((deployButton.dataset.settingsHandoffText || "").includes("gh auth refresh -h github.com -s workflow") && (deployButton.dataset.settingsHandoffText || "").includes("workflowScopeAvailable") && (deployButton.dataset.settingsHandoffText || "").includes("브라우저 인증"), "deploy handoff copy text is missing workflow scope refresh guidance");
    assert(deployHandoffText.includes("Device-code approval handoff") && deployHandoffText.includes("approvalUrl=https://github.com/login/device") && deployHandoffText.includes("one-time device code") && deployHandoffText.includes("gh auth status -h github.com") && deployHandoffText.includes("workflowScopeAvailable: true") && deployHandoffText.includes("workflowScopeInstallBlocked: false") && deployHandoffText.includes("install-remote-workflow-files.mjs") && deployHandoffText.includes("gh workflow run") && deployHandoffText.includes("public launch copy") && deployHandoffText.includes("archive proof"), "deploy handoff copy text is missing device-code approval handoff");
    assert((deployButton.dataset.settingsHandoffText || "").includes("plan-publish-dispatch.mjs --live --repo OWNER/REPO") && (deployButton.dataset.settingsHandoffText || "").includes("plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects") && (deployButton.dataset.settingsHandoffText || "").includes("repoEvidenceReady") && (deployButton.dataset.settingsHandoffText || "").includes("remoteWorkflowFilesReady") && (deployButton.dataset.settingsHandoffText || "").includes("dispatchReady") && (deployButton.dataset.settingsHandoffText || "").includes("driftDispatchReady") && (deployButton.dataset.settingsHandoffText || "").includes("allDispatchReady"), "deploy handoff copy text is missing dispatch dry-run guidance");
    assert((deployButton.dataset.settingsHandoffText || "").includes("Dispatch safety gate") && (deployButton.dataset.settingsHandoffText || "").includes("workflowScope.scopes") && (deployButton.dataset.settingsHandoffText || "").includes("workflowScopeInstallBlocked") && (deployButton.dataset.settingsHandoffText || "").includes("suggestedDispatchCommands") && (deployButton.dataset.settingsHandoffText || "").includes("withheld-until-all-dispatch-ready") && (deployButton.dataset.settingsHandoffText || "").includes("keep using verification commands only"), "deploy handoff copy text is missing dispatch safety gate");
    assert((deployButton.dataset.settingsHandoffText || "").includes("Repo placeholder guard") && (deployButton.dataset.settingsHandoffText || "").includes("Replace every") && (deployButton.dataset.settingsHandoffText || "").includes("OWNER/REPO") && (deployButton.dataset.settingsHandoffText || "").includes("suggestedRepo") && (deployButton.dataset.settingsHandoffText || "").includes("biojuho/BIOJUHO-Projects") && (deployButton.dataset.settingsHandoffText || "").includes("repo placeholder OWNER/REPO") && (deployButton.dataset.settingsHandoffText || "").includes("gh workflow run --repo"), "deploy handoff copy text is missing repo placeholder guard");
    assert((deployButton.dataset.settingsHandoffText || "").includes("plan-workflow-ui-install.mjs --dry-run --markdown") && (deployButton.dataset.settingsHandoffText || "").includes("template sha256") && (deployButton.dataset.settingsHandoffText || "").includes("githubNewFileUrl") && (deployButton.dataset.settingsHandoffText || "").includes("githubWorkflowUrl") && (deployButton.dataset.settingsHandoffText || "").includes("templateCopyCommand") && (deployButton.dataset.settingsHandoffText || "").includes("githubNewFileOpenCommand") && (deployButton.dataset.settingsHandoffText || "").includes("githubWorkflowOpenCommand") && (deployButton.dataset.settingsHandoffText || "").includes("defaultBranch") && (deployButton.dataset.settingsHandoffText || "").includes("suggestedRepo") && (deployButton.dataset.settingsHandoffText || "").includes("nextVerificationCommand"), "deploy handoff copy text is missing workflow UI install plan guidance");
    assert((deployButton.dataset.settingsHandoffText || "").includes("check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write") && (deployButton.dataset.settingsHandoffText || "").includes("remoteWorkflowFilesReady") && (deployButton.dataset.settingsHandoffText || "").includes("remoteMatchesTemplate") && (deployButton.dataset.settingsHandoffText || "").includes("Remote workflow install packet") && (deployButton.dataset.settingsHandoffText || "").includes("install packet 복사") && (deployButton.dataset.settingsHandoffText || "").includes("default branch"), "deploy handoff copy text is missing remote workflow file check guidance");
    assert((deployButton.dataset.settingsHandoffText || "").includes("Post-dispatch evidence") && (deployButton.dataset.settingsHandoffText || "").includes("capture-publish-evidence.mjs --live --repo OWNER/REPO --markdown") && (deployButton.dataset.settingsHandoffText || "").includes("capture-publish-evidence.mjs --live --repo OWNER/REPO --write") && (deployButton.dataset.settingsHandoffText || "").includes("postPublishEvidenceReady") && (deployButton.dataset.settingsHandoffText || "").includes("html_url") && (deployButton.dataset.settingsHandoffText || "").includes("status") && (deployButton.dataset.settingsHandoffText || "").includes("conclusion"), "deploy handoff copy text is missing post-dispatch evidence capture guidance");
    assert(deployHandoffText.includes("## Release gate evidence") && deployHandoffText.includes("package + manifest/source parity pass") && deployHandoffText.includes("desktop/mobile route parity 17/17") && deployHandoffText.includes("mobile search-empty 13 routes including llm-wiki") && deployHandoffText.includes("mobile UI surfaces 5/5 pass") && deployHandoffText.includes("delete/undo recovery 8 types persisted") && deployHandoffText.includes("keyboard/ARIA accessibility pass"), "deploy handoff copy text is missing release gate evidence");
    assert((privacyButton.dataset.settingsHandoffText || "").includes("JooPark Workspace Privacy & Storage Handoff"), "privacy handoff copy text is missing title");
    assert((privacyButton.dataset.settingsHandoffText || "").includes("localStorage") && (privacyButton.dataset.settingsHandoffText || "").includes("joopark.workspace.v3"), "privacy handoff copy text is missing storage scope");
    assert((privacyButton.dataset.settingsHandoffText || "").includes("토큰") && (privacyButton.dataset.settingsHandoffText || "").includes("비밀번호") && (privacyButton.dataset.settingsHandoffText || "").includes("API key"), "privacy handoff copy text is missing sensitive data warning");
    assert((privacyButton.dataset.settingsHandoffText || "").includes("가져오기는 현재 브라우저 데이터를 대체합니다") && (privacyButton.dataset.settingsHandoffText || "").includes("private browsing"), "privacy handoff copy text is missing import and browser session warnings");
    await waitFor(() => document.querySelector("[data-settings-launch-runbook]")?.dataset.settingsLaunchRunbookReady === "true", "settings launch runbook did not load evidence");
    const settingsLaunchRunbook = qs("[data-settings-launch-runbook]");
	    const settingsLaunchRunbookText = settingsLaunchRunbook.textContent || "";
	    const settingsLaunchRunbookSteps = Array.from(settingsLaunchRunbook.querySelectorAll("[data-settings-launch-runbook-step]"));
	    const settingsLaunchRunbookSignals = Array.from(settingsLaunchRunbook.querySelectorAll("[data-settings-launch-runbook-signal]"));
	    const settingsRunbookSafeToDispatch = settingsLaunchRunbook.dataset.settingsLaunchRunbookSafeToDispatch === "true";
	    const settingsRunbookReadyForExternalClaim = settingsLaunchRunbook.dataset.settingsLaunchRunbookReadyForExternalClaim === "true";
	    const settingsRunbookWithheldCount = Number(settingsLaunchRunbook.dataset.settingsLaunchRunbookWithheldCount || "0");
	    const settingsLaunchRunbookLabels = ["Install workflows on the default branch", "Capture launch proof", "Share launch proof"];
	    assert(settingsLaunchRunbook.dataset.settingsLaunchRunbookReady === "true" && settingsLaunchRunbook.dataset.settingsLaunchRunbookStepCount === "7" && settingsLaunchRunbook.dataset.settingsLaunchRunbookSignalCount === "8" && settingsLaunchRunbook.dataset.settingsLaunchRunbookSafeToDispatch === (settingsRunbookSafeToDispatch ? "true" : "false") && ["true", "false"].includes(settingsLaunchRunbook.dataset.settingsLaunchRunbookReadyForExternalClaim) && settingsRunbookWithheldCount >= 0 && ["install_workflows", "capture_launch_proof", "share_launch_proof"].includes(settingsLaunchRunbook.dataset.settingsLaunchRunbookCurrentStage) && settingsLaunchRunbook.dataset.settingsLaunchRunbookSource === "data/workflow-ui-install-plan.json" && settingsLaunchRunbook.dataset.settingsLaunchRunbookPacketSource === "data/launch-execution-packet.json", "settings launch runbook data attributes were incomplete");
	    assert(settingsLaunchRunbookText.includes("GitHub UI install first, dispatch later") && settingsLaunchRunbookLabels.some((launchLabel) => settingsLaunchRunbookText.includes(launchLabel)) && settingsLaunchRunbookText.includes("remoteWorkflowFilesReady=true") && settingsLaunchRunbookText.includes("remoteWorkflowVisibilityReady=true") && settingsLaunchRunbookText.includes("safeToDispatch=true before gh workflow run") && settingsLaunchRunbookText.includes("Do not run gh workflow run"), "settings launch runbook copy was incomplete");
	    const settingsLaunchTransition = qs("[data-settings-launch-transition-preview]", settingsLaunchRunbook);
	    assert(settingsLaunchTransition.dataset.launchTransitionSource === "generated_from_launch_execution_packet" && ["install_workflows", "capture_launch_proof", "share_launch_proof"].includes(settingsLaunchTransition.dataset.launchTransitionCurrentStage) && ["verify_visibility", "capture_launch_proof", "share_launch_proof"].includes(settingsLaunchTransition.dataset.launchTransitionNextStage) && settingsLaunchTransition.dataset.launchTransitionReady === ((settingsRunbookSafeToDispatch || settingsRunbookReadyForExternalClaim) ? "true" : "false") && Number(settingsLaunchTransition.dataset.launchTransitionPendingCount || "0") >= 0 && Number(settingsLaunchTransition.dataset.launchTransitionWithheldCount || "0") >= 0, "settings launch transition preview dataset was incomplete");
	    assert(settingsLaunchTransition.textContent.includes("Stage transition preview") && settingsLaunchTransition.textContent.includes(settingsLaunchTransition.dataset.launchTransitionCurrentStage + " -> " + settingsLaunchTransition.dataset.launchTransitionNextStage) && settingsLaunchTransition.textContent.includes(settingsRunbookSafeToDispatch ? "ready after guard" : "conditional next stage") && (settingsLaunchTransition.textContent.includes("safeToDispatch=true") || settingsLaunchTransition.textContent.includes("remoteWorkflowFilesReady=true")) && qs("[data-launch-transition-gate-command]", settingsLaunchTransition).textContent.includes("verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown"), "settings launch transition preview did not render");
	    const settingsInstallMatrix = qs("[data-settings-install-verification-matrix]", settingsLaunchRunbook);
	    const settingsInstallMatrixRows = Array.from(settingsInstallMatrix.querySelectorAll("[data-settings-install-verification-row]"));
	    const settingsInstallMatrixSignals = Array.from(settingsInstallMatrix.querySelectorAll("[data-settings-install-verification-signal]"));
	    assert(settingsInstallMatrix.dataset.launchInstallVerificationSource === "generated_from_launch_execution_packet" && ["install_verification_required", "ready_to_dispatch"].includes(settingsInstallMatrix.dataset.launchInstallVerificationStatus) && Number(settingsInstallMatrix.dataset.launchInstallVerificationPathCount || "0") >= 0 && settingsInstallMatrix.dataset.launchInstallVerificationSignalCount === "6" && settingsInstallMatrix.dataset.launchInstallVerificationCommandCount === "4" && settingsInstallMatrix.dataset.launchInstallVerificationNextStage === "verify_visibility", "settings install verification matrix dataset was incomplete");
	    assert(settingsInstallMatrix.textContent.includes("Workflow install verification matrix") && settingsInstallMatrix.textContent.includes("paths -> verify_visibility") && settingsInstallMatrix.textContent.includes("remoteWorkflowFilesReady=true") && settingsInstallMatrix.textContent.includes("remoteWorkflowVisibilityReady=true") && settingsInstallMatrix.textContent.includes("dispatchReady=true") && settingsInstallMatrix.textContent.includes("driftDispatchReady=true") && settingsInstallMatrix.textContent.includes("allDispatchReady=true") && settingsInstallMatrix.textContent.includes("verify-launch-handoff reports safeToDispatch=true") && qs("[data-settings-install-verification-handoff-command]", settingsInstallMatrix).textContent.includes("verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown"), "settings install verification matrix did not render");
	    assert((settingsInstallMatrixRows.length === 0 || (settingsInstallMatrixRows.length === 2 && settingsInstallMatrixRows.some((row) => row.dataset.settingsInstallVerificationRowKey === "cli_workflow_scope") && settingsInstallMatrixRows.some((row) => row.dataset.settingsInstallVerificationRowKey === "github_ui"))) && settingsInstallMatrixSignals.length === 5 && settingsInstallMatrixSignals.some((signal) => signal.dataset.settingsInstallVerificationSignalKey === "workflow_visibility" && ["action_required", "pass"].includes(signal.dataset.settingsInstallVerificationSignalStatus)), "settings install verification matrix rows or signals were incomplete");
	    const settingsRemoteFileLedger = qs("[data-settings-remote-workflow-file-ledger]", settingsLaunchRunbook);
	    const settingsRemoteFileLedgerItems = Array.from(settingsRemoteFileLedger.querySelectorAll("[data-settings-remote-workflow-file-ledger-item]"));
	    assert(settingsRemoteFileLedger.dataset.remoteWorkflowFileLedgerSource === "generated_from_remote_workflow_file_check" && ["remote_file_install_required", "remote_files_ready"].includes(settingsRemoteFileLedger.dataset.remoteWorkflowFileLedgerStatus) && settingsRemoteFileLedger.dataset.remoteWorkflowFileLedgerFileCount === "2" && Number(settingsRemoteFileLedger.dataset.remoteWorkflowFileLedgerReadyCount || "0") + Number(settingsRemoteFileLedger.dataset.remoteWorkflowFileLedgerMissingCount || "0") + Number(settingsRemoteFileLedger.dataset.remoteWorkflowFileLedgerMismatchCount || "0") === 2, "settings remote workflow file ledger dataset was incomplete");
	    assert(settingsRemoteFileLedger.textContent.includes("Remote workflow file acceptance ledger") && settingsRemoteFileLedger.textContent.includes(settingsRemoteFileLedger.dataset.remoteWorkflowFileLedgerReadyCount + "/2 files ready") && settingsRemoteFileLedger.textContent.includes("remoteExists") && settingsRemoteFileLedger.textContent.includes("remoteMatchesTemplate") && qs("[data-settings-remote-workflow-file-ledger-verify-command]", settingsRemoteFileLedger).textContent.includes("check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write"), "settings remote workflow file ledger did not render");
	    assert(settingsRemoteFileLedgerItems.length === 2 && settingsRemoteFileLedgerItems.some((item) => item.dataset.remoteWorkflowFileKey === "pages" && ["missing_on_default_branch", "sha_mismatch", "ready"].includes(item.dataset.remoteWorkflowFileStatus)) && settingsRemoteFileLedgerItems.some((item) => item.dataset.remoteWorkflowFileKey === "drift-watch" && ["missing_on_default_branch", "sha_mismatch", "ready"].includes(item.dataset.remoteWorkflowFileStatus)), "settings remote workflow file ledger rows were incomplete");
	    const settingsProofLedger = qs("[data-settings-launch-proof-ledger]", settingsLaunchRunbook);
	    const settingsProofLedgerItems = Array.from(settingsProofLedger.querySelectorAll("[data-settings-launch-proof-ledger-item]"));
	    const settingsProofLedgerReadyCount = Number(settingsProofLedger.dataset.launchProofLedgerReadyCount || "0");
	    const settingsProofLedgerPendingCount = Number(settingsProofLedger.dataset.launchProofLedgerPendingCount || "0");
	    assert(settingsProofLedger.dataset.launchProofLedgerSource === "generated_from_launch_execution_packet" && ["proof_blocked_until_dispatch", "proof_capture_required", "proof_ready"].includes(settingsProofLedger.dataset.launchProofLedgerStatus) && settingsProofLedger.dataset.launchProofLedgerRequiredCount === "6" && settingsProofLedgerReadyCount + settingsProofLedgerPendingCount === 6 && ["capture_launch_proof", "share_launch_proof"].includes(settingsProofLedger.dataset.launchProofLedgerCurrentGate) && settingsProofLedger.dataset.launchProofLedgerDeferredUntil.length > 0, "settings launch proof ledger dataset was incomplete");
	    assert(settingsProofLedger.textContent.includes("Launch proof acceptance ledger") && settingsProofLedger.textContent.includes(settingsProofLedgerReadyCount + "/6 proofs ready") && settingsProofLedger.textContent.includes("Pages URL/status") && settingsProofLedger.textContent.includes("status/conclusion/url/headSha") && qs("[data-settings-launch-proof-ledger-capture-command]", settingsProofLedger).textContent.includes("capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --write"), "settings launch proof ledger did not render");
	    assert(settingsProofLedgerItems.length === 6 && settingsProofLedgerItems.some((item) => item.dataset.launchProofAcceptanceKey === "pages_site_url" && ["blocked_until_dispatch", "pending_capture", "ready"].includes(item.dataset.launchProofAcceptanceStatus)) && settingsProofLedgerItems.some((item) => item.dataset.launchProofAcceptanceKey === "public_claim_guard" && ["guarded", "ready"].includes(item.dataset.launchProofAcceptanceStatus)), "settings launch proof ledger proof rows were incomplete");
    assert(settingsLaunchRunbookSteps.length === 7 && settingsLaunchRunbookSteps.some((step) => step.dataset.settingsLaunchRunbookStepKey === "copy-pages-template" && step.dataset.settingsLaunchRunbookStepCommand.includes("pbcopy < 'docs/github-pages-workflow.yml'")) && settingsLaunchRunbookSteps.some((step) => step.dataset.settingsLaunchRunbookStepKey === "create-pages-workflow" && step.dataset.settingsLaunchRunbookStepTarget === ".github/workflows/joopark-pages.yml") && settingsLaunchRunbookSteps.some((step) => step.dataset.settingsLaunchRunbookStepKey === "copy-drift-template" && step.dataset.settingsLaunchRunbookStepCommand.includes("docs/github-drift-watch-workflow.yml")) && settingsLaunchRunbookSteps.some((step) => step.dataset.settingsLaunchRunbookStepKey === "create-drift-workflow" && step.dataset.settingsLaunchRunbookStepTarget === ".github/workflows/joopark-drift-watch.yml") && settingsLaunchRunbookSteps.some((step) => step.dataset.settingsLaunchRunbookStepKey === "verify-remote-parity" && step.dataset.settingsLaunchRunbookStepProof === "remoteWorkflowFilesReady=true") && settingsLaunchRunbookSteps.some((step) => step.dataset.settingsLaunchRunbookStepKey === "verify-workflow-visibility" && step.dataset.settingsLaunchRunbookStepCommand.includes("gh workflow list --repo biojuho/BIOJUHO-Projects")) && settingsLaunchRunbookSteps.some((step) => step.dataset.settingsLaunchRunbookStepKey === "verify-dispatch-guard" && step.textContent.includes("verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown")), "settings launch runbook steps were incomplete");
    assert(settingsLaunchRunbookSignals.length === 8 && settingsLaunchRunbookSignals.some((signal) => signal.textContent.includes("allDispatchReady=true")) && settingsLaunchRunbookSignals.some((signal) => signal.textContent.includes("safeToDispatch=true before gh workflow run")) && settingsLaunchRunbook.querySelectorAll("[data-settings-launch-runbook-link]").length >= 2, "settings launch runbook signals or links were incomplete");
	    const settingsPostInstallIntake = qs("[data-settings-post-install-evidence-intake]", settingsLaunchRunbook);
	    const settingsPostInstallIntakeText = qs("[data-post-install-evidence-intake-text]", settingsPostInstallIntake).textContent;
	    const settingsPostInstallCopy = qs("[data-post-install-evidence-intake-copy]", settingsPostInstallIntake);
	    const settingsPostInstallSequence = qs("[data-post-install-evidence-intake-sequence]", settingsPostInstallIntake);
	    const settingsPostInstallSequenceSteps = Array.from(settingsPostInstallSequence.querySelectorAll("[data-post-install-evidence-intake-sequence-step]"));
		    const settingsPostInstallQuickProof = qs("[data-post-install-quick-proof]", settingsPostInstallIntake);
		    const settingsPostInstallQuickProofSteps = Array.from(settingsPostInstallQuickProof.querySelectorAll("[data-post-install-quick-proof-step]"));
		    const settingsPostInstallQuickProofMap = qs("[data-post-install-quick-proof-field-map]", settingsPostInstallIntake);
		    const settingsPostInstallQuickProofMapItems = Array.from(settingsPostInstallQuickProofMap.querySelectorAll("[data-post-install-quick-proof-field-map-item]"));
		    const settingsPostInstallMappedCompleted = Number(settingsPostInstallIntake.dataset.postInstallQuickProofCompletedMappedFieldCount || "0");
		    assert(settingsPostInstallIntake.dataset.postInstallEvidenceIntakeReady === "true" && settingsPostInstallIntake.dataset.postInstallEvidenceIntakeCommandCount === "4" && settingsPostInstallIntake.dataset.postInstallEvidenceIntakeSignalCount === "8" && settingsPostInstallIntake.dataset.postInstallEvidenceIntakeFieldCount === "6" && settingsPostInstallIntake.dataset.postInstallEvidenceIntakeFieldCoverage === "1" && settingsPostInstallIntake.dataset.postInstallEvidenceIntakeSequenceCount === "4" && settingsPostInstallIntake.dataset.postInstallEvidenceIntakeSequenceReady === "true" && settingsPostInstallIntake.dataset.postInstallEvidenceIntakeFinalCommand.includes("verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown") && settingsPostInstallIntake.dataset.postInstallEvidenceIntakeDispatchGuard.includes("every post-install evidence field has been filled") && settingsPostInstallIntake.dataset.postInstallEvidenceIntakeDispatchGuard.includes("dispatchReady=true") && settingsPostInstallIntake.dataset.postInstallEvidenceIntakeDispatchGuard.includes("verify-launch-handoff reports safeToDispatch=true") && settingsPostInstallIntake.dataset.postInstallQuickProofReady === "true" && settingsPostInstallIntake.dataset.postInstallQuickProofStepCount === "4" && settingsPostInstallIntake.dataset.postInstallQuickProofCoverage === "1" && settingsPostInstallIntake.dataset.postInstallQuickProofFieldMappingReady === "true" && settingsPostInstallIntake.dataset.postInstallQuickProofFieldMappingCoverage === "1" && settingsPostInstallIntake.dataset.postInstallQuickProofMappedFieldCount === "4" && settingsPostInstallMappedCompleted >= 0 && settingsPostInstallMappedCompleted <= 4, "settings post-install evidence intake state was incomplete");
		    assert(settingsPostInstallQuickProof.dataset.postInstallQuickProofReady === "true" && settingsPostInstallQuickProofSteps.length === 4 && settingsPostInstallQuickProofSteps[0].dataset.postInstallQuickProofStepKey === "remote_file_parity" && settingsPostInstallQuickProofSteps[3].dataset.postInstallQuickProofStepKey === "handoff_verifier", "settings post-install quick proof was incomplete");
		    assert(settingsPostInstallQuickProofMap.dataset.postInstallQuickProofFieldMappingReady === "true" && settingsPostInstallQuickProofMap.dataset.postInstallQuickProofFieldMappingCoverage === "1" && settingsPostInstallQuickProofMap.dataset.postInstallQuickProofMappedFieldCount === "4" && Number(settingsPostInstallQuickProofMap.dataset.postInstallQuickProofCompletedMappedFieldCount || "0") === settingsPostInstallMappedCompleted && settingsPostInstallQuickProofMapItems.length === 4 && settingsPostInstallQuickProofMapItems[0].dataset.postInstallQuickProofFieldMapStep === "remote_file_parity" && settingsPostInstallQuickProofMapItems[0].dataset.postInstallQuickProofFieldMapField === "remote_parity_proof" && settingsPostInstallQuickProofMapItems[3].dataset.postInstallQuickProofFieldMapStep === "handoff_verifier" && settingsPostInstallQuickProofMapItems[3].dataset.postInstallQuickProofFieldMapField === "handoff_verifier_proof", "settings post-install quick proof field map was incomplete");
	    assert(settingsPostInstallIntake.querySelectorAll("[data-post-install-evidence-intake-check]").length === 5 && settingsPostInstallIntake.querySelectorAll("[data-post-install-evidence-intake-command]").length === 4 && settingsPostInstallIntake.querySelectorAll("[data-post-install-evidence-intake-signal]").length === 8 && settingsPostInstallIntake.querySelectorAll("[data-post-install-evidence-intake-field]").length === 6 && settingsPostInstallSequence.dataset.postInstallEvidenceIntakeSequenceCount === "4" && settingsPostInstallSequenceSteps.length === 4 && settingsPostInstallSequenceSteps[0].dataset.postInstallEvidenceIntakeSequenceKey === "remote_file_parity" && settingsPostInstallSequenceSteps[3].dataset.postInstallEvidenceIntakeSequenceKey === "handoff_verifier", "settings post-install evidence intake checklist was incomplete");
		    assert(settingsPostInstallIntakeText.includes("JooPark Workflow Post-Install Evidence Intake") && settingsPostInstallIntakeText.includes("JooPark Post-Install Quick Proof Receipt") && settingsPostInstallIntakeText.includes("Quick proof: ready=true; steps=4; coverage=1") && settingsPostInstallIntakeText.includes("Quick proof field mapping: ready=true; mapped=4; completed=" + settingsPostInstallMappedCompleted + "/4; coverage=1") && settingsPostInstallIntakeText.includes("Mapped proof fields:") && settingsPostInstallIntakeText.includes("remote_file_parity -> remote_parity_proof") && settingsPostInstallIntakeText.includes("handoff_verifier -> handoff_verifier_proof") && settingsPostInstallIntakeText.includes("not dispatch approval") && settingsPostInstallIntakeText.includes("Evidence fields to fill:") && settingsPostInstallIntakeText.includes("Verification sequence:") && settingsPostInstallIntakeText.includes("1. remote_file_parity") && settingsPostInstallIntakeText.includes("4. handoff_verifier") && settingsPostInstallIntakeText.includes("Pages workflow commit") && settingsPostInstallIntakeText.includes("Drift Watch workflow commit") && settingsPostInstallIntakeText.includes("Remote parity proof") && settingsPostInstallIntakeText.includes("Actions visibility proof") && settingsPostInstallIntakeText.includes("Dispatch readiness proof") && settingsPostInstallIntakeText.includes("Handoff verifier proof") && settingsPostInstallIntakeText.includes("remoteWorkflowFilesReady=true") && settingsPostInstallIntakeText.includes("remoteWorkflowVisibilityReady=true") && settingsPostInstallIntakeText.includes("allDispatchReady=true") && settingsPostInstallIntakeText.includes("safeToDispatch=true before gh workflow run") && settingsPostInstallIntakeText.includes("every post-install evidence field has been filled") && settingsPostInstallIntakeText.includes("Stop condition: do not run gh workflow run") && settingsPostInstallIntakeText.includes("Do not run gh workflow run"), "settings post-install evidence intake copy was incomplete");
    window.__smokeClipboardText = "";
    try {
      Object.defineProperty(navigator, "clipboard", {
        configurable: true,
        value: { writeText: async (text) => { window.__smokeClipboardText = text; } },
      });
    } catch (_) {}
    click("[data-post-install-evidence-intake-copy]", settingsPostInstallIntake);
    await waitFor(() => settingsPostInstallCopy.dataset.postInstallEvidenceIntakeCopied === "true" && settingsPostInstallIntake.dataset.postInstallEvidenceIntakeCopied === "true" && qs("[data-post-install-evidence-intake-copy-status]", settingsPostInstallIntake).textContent.includes("복사"), "settings post-install evidence intake copy did not report success");
		    await waitFor(() => window.__smokeClipboardText.includes("JooPark Workflow Post-Install Evidence Intake") && window.__smokeClipboardText.includes("JooPark Post-Install Quick Proof Receipt") && window.__smokeClipboardText.includes("4-step proof checklist:") && window.__smokeClipboardText.includes("Quick proof field mapping: ready=true; mapped=4; completed=" + settingsPostInstallMappedCompleted + "/4; coverage=1") && window.__smokeClipboardText.includes("remote_file_parity -> remote_parity_proof") && window.__smokeClipboardText.includes("handoff_verifier -> handoff_verifier_proof") && window.__smokeClipboardText.includes("Evidence fields to fill:") && window.__smokeClipboardText.includes("Verification sequence:") && window.__smokeClipboardText.includes("1. remote_file_parity") && window.__smokeClipboardText.includes("4. handoff_verifier") && window.__smokeClipboardText.includes("Pages workflow commit") && window.__smokeClipboardText.includes("Handoff verifier proof") && window.__smokeClipboardText.includes("remoteWorkflowFilesReady=true") && window.__smokeClipboardText.includes("safeToDispatch=true before gh workflow run") && window.__smokeClipboardText.includes("every post-install evidence field has been filled") && window.__smokeClipboardText.includes("Stop condition: do not run gh workflow run") && window.__smokeClipboardText.includes("Do not run gh workflow run"), "settings post-install evidence intake copy text did not reach clipboard");
    window.__smokeClipboardText = "";
    click('[data-settings-handoff-copy="backup"]', backupCard);
    await waitFor(() => backupButton.dataset.settingsHandoffCopied === "true" && backupCard.querySelector("[data-settings-handoff-copy-status]").textContent.includes("복사"), "backup handoff copy did not report success");
    await waitFor(() => window.__smokeClipboardText.includes("JooPark Workspace Backup Handoff") && window.__smokeClipboardText.includes("가져오기는 현재 브라우저 데이터를 대체합니다"), "backup handoff copy text did not reach clipboard");
    click('[data-settings-handoff-copy="deploy"]', deployCard);
    await waitFor(() => deployButton.dataset.settingsHandoffCopied === "true" && deployCard.querySelector("[data-settings-handoff-copy-status]").textContent.includes("복사"), "deploy handoff copy did not report success");
    await waitFor(() => window.__smokeClipboardText.includes("JooPark Workspace Deploy Handoff") && window.__smokeClipboardText.includes("pages: write") && window.__smokeClipboardText.includes("actions/deploy-pages") && window.__smokeClipboardText.includes("Repo placeholder guard") && window.__smokeClipboardText.includes("Dispatch safety gate") && window.__smokeClipboardText.includes("suggestedDispatchCommands") && window.__smokeClipboardText.includes("withheld-until-all-dispatch-ready") && window.__smokeClipboardText.includes("Device-code approval handoff") && window.__smokeClipboardText.includes("approvalUrl=https://github.com/login/device") && window.__smokeClipboardText.includes("one-time device code") && window.__smokeClipboardText.includes("## Release gate evidence") && window.__smokeClipboardText.includes("mobile UI surfaces 5/5 pass") && window.__smokeClipboardText.includes("delete/undo recovery 8 types persisted"), "deploy handoff copy text did not reach clipboard");
    releaseGateEvidenceHandoffOk = true;
    click('[data-settings-handoff-copy="privacy"]', privacyCard);
    await waitFor(() => privacyButton.dataset.settingsHandoffCopied === "true" && privacyCard.querySelector("[data-settings-handoff-copy-status]").textContent.includes("복사"), "privacy handoff copy did not report success");
    await waitFor(() => window.__smokeClipboardText.includes("JooPark Workspace Privacy & Storage Handoff") && window.__smokeClipboardText.includes("localStorage") && window.__smokeClipboardText.includes("API key"), "privacy handoff copy text did not reach clipboard");
    privacyStorageHandoffOk = true;
    settingsHandoffCopyOk = true;
    settingsViewModuleOk = true;
  });

  await runStep("system publish readiness alignment", async () => {
    await nav("system");
    await waitForSystemEvidencePanels();
    assert(window.JooParkReleaseStatus && window.JooParkReleaseStatus.version === "joopark-release-status/v1" && typeof window.JooParkReleaseStatus.create === "function", "release status runtime module was not loaded");
    assert(window.JooParkSystemStatusView && window.JooParkSystemStatusView.version === "joopark-system-status-view/v1" && typeof window.JooParkSystemStatusView.create === "function", "system status view runtime module was not loaded");
    assert(publishReadinessItems().some((item) => item.key === "publish-evidence-capture"), "release status wrapper did not expose publish readiness items");
	    releaseStatusModuleOk = true;
	    systemStatusViewModuleOk = true;
	    const status = qs("[data-system-status]");
	    assert(status.dataset.systemStatusModule === "joopark-system-status-view/v1", "system status view module did not render KPI shell");
	    const assertSystemSourceInventory = () => {
	      const sourceSnapshots = qs("[data-system-source-snapshots]");
	      const sourceRows = Array.from(sourceSnapshots.querySelectorAll("[data-source-snapshot-row]"));
	      assert(sourceSnapshots.dataset.sourceSnapshotLoaded === "true", "source snapshot health did not mark source data loaded");
	      assert(Number(sourceSnapshots.dataset.sourceSnapshotLoadedCount || "0") >= 2 && Number(sourceSnapshots.dataset.sourceSnapshotErrorCount || "0") === 0, "source snapshot health did not expose loaded source counts");
	      assert(Number(sourceSnapshots.dataset.sourceSnapshotProjectCount || "0") >= dashboard.projects.filter((project) => project.sourceKind === "adoption-candidate").length, "source snapshot merged project count was incomplete");
	      assert(sourceRows.some((row) => row.dataset.sourceSnapshotPath === "data/repos.json" && row.dataset.sourceSnapshotRowLoaded === "true"), "data/repos.json source health row did not render loaded");
	      assert(sourceRows.some((row) => row.dataset.sourceSnapshotPath === "data/adoption-candidates.json" && row.dataset.sourceSnapshotRowLoaded === "true"), "data/adoption-candidates.json source health row did not render loaded");
	      assert(qs("[data-source-snapshot-status-label]", sourceSnapshots).textContent.includes("loaded"), "source snapshot health status label did not render loaded state");
	      sourceSnapshotHealthOk = true;
	      const githubDiscovery = qs("[data-system-github-project-discovery]");
	      const discoveryRows = Array.from(githubDiscovery.querySelectorAll("[data-github-project-discovery-row]"));
	      assert(githubDiscovery.dataset.githubProjectDiscoveryLoaded === "true" &&
	        githubDiscovery.dataset.githubProjectDiscoveryPublicSafe === "true" &&
	        githubDiscovery.dataset.githubProjectDiscoverySource === "data/github-project-discovery.json" &&
	        githubDiscovery.dataset.githubProjectDiscoveryReleaseTargetReady === "true" &&
	        githubDiscovery.dataset.githubProjectDiscoveryAbDecision === "keep_b" &&
	        githubDiscovery.dataset.githubProjectDiscoveryLocalPathMode === "relative-to-local-root" &&
	        githubDiscovery.dataset.githubProjectDiscoveryFreshnessReady === "true" &&
	        githubDiscovery.dataset.githubProjectDiscoveryReproducible === "true" &&
	        githubDiscovery.dataset.githubProjectDiscoveryPrivateRedacted === "true" &&
	        Number(githubDiscovery.dataset.githubProjectDiscoveryPrivateExposure || "1") === 0 &&
	        Number(githubDiscovery.dataset.githubProjectDiscoveryPrivateRowExposure || "1") === 0 &&
	        Number(githubDiscovery.dataset.githubProjectDiscoveryPushedCount || "0") >= 1 &&
	        Number(githubDiscovery.dataset.githubProjectDiscoveryFreshCount || "0") >= 1 &&
	        Number(githubDiscovery.dataset.githubProjectDiscoverySourceFieldCount || "0") >= 4 &&
	        Number(githubDiscovery.dataset.githubProjectDiscoveryLocalScanDepth || "0") >= 1 &&
	        Number(githubDiscovery.dataset.githubProjectDiscoveryIgnoredCount || "0") >= 1 &&
	        Number(githubDiscovery.dataset.githubProjectDiscoveryLocalCount || "0") >= 1 &&
	        Number(githubDiscovery.dataset.githubProjectDiscoveryGithubCount || "0") >= 1 &&
	        Number(githubDiscovery.dataset.githubProjectDiscoveryRankedCount || "0") >= 1,
	        "GitHub project discovery panel did not expose safe loaded inventory data");
	      assert(discoveryRows.some((row) => row.dataset.githubProjectDiscoveryProject === "biojuho/BIOJUHO-Projects" && row.dataset.githubProjectDiscoveryRelation === "current-release-target"), "GitHub project discovery did not surface the release target");
	      assert(discoveryRows.some((row) => row.dataset.githubProjectDiscoveryPushedAt && Number(row.dataset.githubProjectDiscoveryStars || "0") >= 0), "GitHub project discovery did not surface freshness metadata");
	      assert((githubDiscovery.textContent || "").includes("Do not push, deploy, delete branches") && !(githubDiscovery.textContent || "").includes("/Users/"), "GitHub project discovery guard or path privacy was incomplete");
	      githubProjectDiscoveryOk = true;
	    };
	    assertSystemSourceInventory();
	    await waitFor(() => {
	      const pwa = document.querySelector("[data-system-pwa-runtime]");
	      return pwa &&
	        pwa.dataset.pwaRuntimeServiceWorkerActive === "true" &&
        pwa.dataset.pwaRuntimeCacheReady === "true" &&
        pwa.dataset.pwaRuntimeManifestLinked === "true" &&
        Number(pwa.dataset.pwaRuntimeCachedAssetCount || "0") > 0;
    }, "system PWA runtime panel did not reach ready state", 15000);
    const pwaRuntime = qs("[data-system-pwa-runtime]");
    const pwaRuntimeText = pwaRuntime.textContent || "";
    assert(["ready", "partial"].includes(pwaRuntime.dataset.pwaRuntimeStatus || ""), "system PWA runtime status was not surfaced");
    assert(pwaRuntimeText.includes("PWA runtime") && pwaRuntimeText.includes("service worker") && pwaRuntimeText.includes("app shell cache") && pwaRuntimeText.includes("manifest") && pwaRuntimeText.includes("scope") && pwaRuntimeText.includes("script") && pwaRuntimeText.includes("cache"), "system PWA runtime copy was incomplete");
    assert((qs("[data-pwa-runtime-script]", pwaRuntime).textContent || "").includes("sw.js"), "system PWA runtime script URL did not identify sw.js");
    systemPwaRuntimeOk = true;
    const opsRuntime = qs("[data-system-ops-runtime]");
    const opsRuntimeText = opsRuntime.textContent || "";
    const opsRuntimeGroups = Array.from(opsRuntime.querySelectorAll("[data-ops-runtime-group]"));
    const opsRuntimeReadyGroups = opsRuntimeGroups.filter((item) => item.dataset.opsRuntimeGroupReady === "true");
    assert(opsRuntime.dataset.opsRuntimeVersion === "joopark-ops-runtime-loader/v1" &&
      opsRuntime.dataset.opsRuntimeStatus === "ready" &&
      Number(opsRuntime.dataset.opsRuntimeLoadedCount || "0") === Number(opsRuntime.dataset.opsRuntimeTotalCount || "0") &&
      Number(opsRuntime.dataset.opsRuntimeFailedCount || "0") === 0 &&
      Number(opsRuntime.dataset.opsRuntimeGroupCount || "0") >= 3 &&
      opsRuntimeReadyGroups.length === opsRuntimeGroups.length, "system ops runtime diagnostics dataset was incomplete");
    assert(opsRuntimeText.includes("Ops runtime diagnostics") &&
      opsRuntimeText.includes("loaded lazy files") &&
      opsRuntimeText.includes("ready groups") &&
      opsRuntimeText.includes("release") &&
      opsRuntimeText.includes("review"), "system ops runtime diagnostics panel did not render");
    systemOpsRuntimeOk = true;
    let panel = qs("[data-system-publish-readiness]");
    const items = Array.from(panel.querySelectorAll("[data-publish-readiness-item]"));
    const blocked = items.filter((item) => item.dataset.publishState === "blocked");
    const releaseGateItem = items.find((item) => item.dataset.publishKey === "release-gates");
    const releaseGateEvidenceItems = releaseGateItem ? Array.from(releaseGateItem.querySelectorAll("[data-publish-readiness-evidence-item]")) : [];
    assert(items.length >= 6, "publish readiness did not render all workflow states");
    assert(Number(panel.dataset.systemPublishBlockers || "0") === blocked.length, "publish readiness blocker count did not match DOM state");
    assert(status.dataset.systemPublishBlockers === panel.dataset.systemPublishBlockers, "system KPI blocker count did not match publish panel");
    assert(blocked.length >= 3, "workflow installation blockers were not surfaced");
    assert(releaseGateItem && releaseGateItem.dataset.publishEvidenceCount === "6" && releaseGateEvidenceItems.length === 6, "release gate evidence depth was not surfaced");
    assert(releaseGateItem.textContent.includes("package + manifest/source parity pass") && releaseGateItem.textContent.includes("desktop/mobile route parity 17/17") && releaseGateItem.textContent.includes("mobile search-empty 13 routes including llm-wiki") && releaseGateItem.textContent.includes("mobile UI surfaces 5/5 pass") && releaseGateItem.textContent.includes("delete/undo recovery 8 types persisted") && releaseGateItem.textContent.includes("keyboard/ARIA accessibility pass"), "release gate evidence copy was incomplete");
    const text = panel.innerText;
    assert(text.includes("릴리스 게이트") && text.includes("workflow scope preflight") && text.includes("GitHub UI install plan") && text.includes("Pages workflow 설치") && text.includes("Drift Watch 설치") && text.includes("Remote workflow file check") && text.includes("Publish dispatch dry-run") && text.includes("Publish 실행") && text.includes("Publish evidence capture"), "publish readiness labels were incomplete");
    assert(text.includes("workflowScopeAvailable") && text.includes("workflow-scope token") && text.includes("prepare-github-pages-workflow.mjs --write") && text.includes("prepare-github-drift-watch-workflow.mjs --write") && text.includes("githubNewFileUrl") && text.includes("githubWorkflowUrl") && text.includes("templateCopyCommand") && text.includes("githubNewFileOpenCommand") && text.includes("githubWorkflowOpenCommand") && text.includes("defaultBranch") && text.includes("suggestedRepo") && text.includes("nextVerificationCommand"), "workflow installation guidance was incomplete");
    assert(text.includes("plan-publish-dispatch.mjs --live --repo OWNER/REPO") && text.includes("plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects") && text.includes("repoEvidenceReady") && text.includes("dispatchReady") && text.includes("allDispatchReady") && text.includes("joopark-drift-watch.yml") && text.includes("repo placeholder OWNER/REPO"), "publish dispatch dry-run guidance was incomplete");
    assert(text.includes("capture-publish-evidence.mjs --live --repo OWNER/REPO --markdown") && text.includes("postPublishEvidenceReady") && text.includes("html_url/status") && text.includes("status/conclusion"), "post-dispatch evidence guidance was incomplete");
    releaseGateEvidenceOk = true;
    await waitFor(() => {
      const installPlan = document.querySelector("[data-system-workflow-ui-install-plan]");
      return installPlan && installPlan.dataset.workflowUiInstallLoaded === "true";
    }, "workflow UI install plan panel did not load");
    panel = qs("[data-system-publish-readiness]");
    const workflowInstallPlan = qs("[data-system-workflow-ui-install-plan]", panel);
    const workflowInstallCards = Array.from(workflowInstallPlan.querySelectorAll("[data-workflow-ui-install-card]"));
    const workflowInstallText = workflowInstallPlan.textContent || "";
    const workflowUiInstallReceiptCommandCount = Number(workflowInstallPlan.dataset.workflowUiInstallReceiptCommandCount || "0");
    const workflowUiInstallReceiptChecklistCount = Number(workflowInstallPlan.dataset.workflowUiInstallReceiptChecklistCount || "0");
    const pagesWorkflowInstallCard = workflowInstallCards.find((card) => card.dataset.workflowUiInstallTarget === ".github/workflows/joopark-pages.yml");
    const driftWorkflowInstallCard = workflowInstallCards.find((card) => card.dataset.workflowUiInstallTarget === ".github/workflows/joopark-drift-watch.yml");
    const workflowInstallAllVerified = workflowInstallCards.length === 2 && workflowInstallCards.every((card) => card.dataset.workflowUiInstallAction === "verified_remote_matches_template");
    const minimumWorkflowUiInstallReceiptCommandCount = workflowInstallAllVerified ? 4 : 6;
    assert(workflowInstallPlan.dataset.workflowUiInstallSource === "data/workflow-ui-install-plan.json" && workflowInstallPlan.dataset.workflowUiInstallReady === "true" && workflowInstallPlan.dataset.workflowUiInstallTargetParityReady === "true" && workflowInstallPlan.dataset.workflowUiInstallSuggestedRepo === "biojuho/BIOJUHO-Projects" && workflowInstallPlan.dataset.workflowUiInstallNextCommand.includes("plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects") && workflowInstallPlan.dataset.workflowUiInstallReceiptReady === "true" && workflowUiInstallReceiptCommandCount >= minimumWorkflowUiInstallReceiptCommandCount && workflowUiInstallReceiptChecklistCount >= 6 && workflowInstallPlan.dataset.workflowUiInstallReceiptExpectedCount === "8" && workflowInstallPlan.dataset.workflowUiInstallReceiptVerifyCommand.includes("verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown") && workflowInstallPlan.dataset.workflowUiInstallPastePacketReady === "true" && workflowInstallPlan.dataset.workflowUiInstallPastePacketCoverage === "1" && workflowInstallPlan.dataset.workflowUiInstallParserReadyProofBlockReady === "true" && workflowInstallPlan.dataset.workflowUiInstallParserReadyProofFieldCoverage === "1" && workflowInstallPlan.dataset.workflowUiInstallFormFieldCoverage === "1", "workflow UI install plan data attributes were incomplete");
    assert(workflowInstallPlan.dataset.workflowUiInstallRunbookReady === "true" && workflowInstallPlan.dataset.workflowUiInstallRunbookStepCount === "7" && workflowInstallPlan.dataset.workflowUiInstallRunbookExpectedSignalCount === "8" && workflowInstallPlan.dataset.workflowUiInstallRunbookRemoteFileCommand.includes("check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write") && workflowInstallPlan.dataset.workflowUiInstallRunbookDispatchCommand.includes("plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects --write") && workflowInstallPlan.dataset.workflowUiInstallRunbookHandoffCommand.includes("verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown") && workflowInstallPlan.dataset.workflowUiInstallIntakeReady === "true" && workflowInstallPlan.dataset.workflowUiInstallIntakeCommandCount === "4" && workflowInstallPlan.dataset.workflowUiInstallIntakeSignalCount === "8" && workflowInstallPlan.dataset.workflowUiInstallIntakeFieldCount === "6" && workflowInstallPlan.dataset.workflowUiInstallIntakeFieldCoverage === "1" && workflowInstallPlan.dataset.postInstallQuickProofReady === "true" && workflowInstallPlan.dataset.postInstallQuickProofStepCount === "4" && workflowInstallPlan.dataset.postInstallQuickProofCoverage === "1" && workflowInstallPlan.dataset.postInstallQuickProofFieldMappingReady === "true" && workflowInstallPlan.dataset.postInstallQuickProofFieldMappingCoverage === "1" && workflowInstallPlan.dataset.postInstallQuickProofMappedFieldCount === "4" && workflowInstallPlan.dataset.postInstallQuickProofCompletedMappedFieldCount === "0", "workflow UI install runbook data attributes were incomplete");
    const workflowInstallHasRequiredAction = workflowInstallCards.some((card) => ["replace_existing_remote_file", "create_missing_remote_file"].includes(card.dataset.workflowUiInstallAction || "") && card.dataset.workflowUiInstallOpenCommand);
    assert(workflowInstallCards.length === 2 && workflowInstallCards.every((card) => card.dataset.workflowUiInstallReady === "true" && card.dataset.workflowUiInstallTargetMatchesTemplate === "true" && card.dataset.workflowUiInstallFileNameField === card.dataset.workflowUiInstallTarget && card.dataset.workflowUiInstallCommitMessage && ["replace_existing_remote_file", "create_missing_remote_file", "verified_remote_matches_template"].includes(card.dataset.workflowUiInstallAction || "")) && (workflowInstallAllVerified || workflowInstallHasRequiredAction) && workflowInstallCards.some((card) => card.dataset.workflowUiInstallAction === "verified_remote_matches_template" && card.dataset.workflowUiInstallRequired === "false"), "workflow UI install plan cards were incomplete");
    assert(workflowInstallCards.some((card) => card.dataset.workflowUiInstallTarget === ".github/workflows/joopark-pages.yml") && workflowInstallCards.some((card) => card.dataset.workflowUiInstallTarget === ".github/workflows/joopark-drift-watch.yml"), "workflow UI install target cards were missing");
    assert(workflowInstallText.includes("data/workflow-ui-install-plan.json") && workflowInstallText.includes("localTargetParityReady") && workflowInstallText.includes("targetSha256") && workflowInstallText.includes("targetMatchesTemplate") && workflowInstallText.includes("remoteMatchesTemplate") && workflowInstallText.includes("installAction") && workflowInstallCards.every((card) => workflowInstallText.includes(card.dataset.workflowUiInstallAction || "")) && workflowInstallText.includes("githubEditFileUrl") && workflowInstallText.includes("uiInstallOpenCommand") && workflowInstallText.includes("templateCopyCommand") && workflowInstallText.includes("githubNewFileUrl") && workflowInstallText.includes("githubWorkflowUrl") && workflowInstallText.includes("githubFileNameFieldValue") && workflowInstallText.includes("suggestedCommitMessage") && workflowInstallText.includes("workflowUiInstallFormFieldCoverage") && workflowInstallText.includes("nextVerificationCommand") && workflowInstallText.includes("workflow_dispatch") && workflowInstallText.includes("workflowUiInstallPastePacketCoverage") && workflowInstallText.includes(".github/workflows") && workflowInstallText.includes("GitHub UI install first, dispatch later") && workflowInstallText.includes("Verify remote file parity") && workflowInstallText.includes("Verify workflow visibility") && workflowInstallText.includes("Recheck dispatch guard") && workflowInstallText.includes("JooPark GitHub UI Workflow Install Receipt") && workflowInstallText.includes("JooPark GitHub UI Workflow Paste Packet") && workflowInstallText.includes("GitHub new-file form values") && workflowInstallText.includes("Install action ledger") && workflowInstallText.includes("Parser-ready proof block") && workflowInstallText.includes("pages_workflow_commit:") && workflowInstallText.includes("Post-install proof checklist") && workflowInstallText.includes("safeToDispatch=true before gh workflow run"), "workflow UI install panel copy was incomplete");
    const workflowRunbook = qs("[data-workflow-ui-install-runbook]", workflowInstallPlan);
    const workflowRunbookSteps = Array.from(workflowRunbook.querySelectorAll("[data-workflow-ui-install-runbook-step]"));
    const workflowRunbookSignals = Array.from(workflowRunbook.querySelectorAll("[data-workflow-ui-install-runbook-signal]"));
    assert(workflowRunbook.dataset.workflowUiInstallRunbookReady === "true" && workflowRunbook.dataset.workflowUiInstallRunbookStepCount === "7" && workflowRunbook.dataset.workflowUiInstallRunbookExpectedSignalCount === "8" && workflowRunbook.dataset.workflowUiInstallRunbookDispatchGuard.includes("safeToDispatch=true"), "workflow UI install runbook state was incomplete");
    const workflowRunbookStepByKey = (key) => workflowRunbookSteps.find((step) => step.dataset.workflowUiInstallRunbookStepKey === key);
    const pagesApplyRunbookStep = workflowRunbookStepByKey("apply-pages-workflow");
    const driftApplyRunbookStep = workflowRunbookStepByKey("apply-drift-workflow");
    assert(workflowRunbookSteps.length === 7 && workflowRunbookSteps.some((step) => step.dataset.workflowUiInstallRunbookStepKey === "copy-pages-template" && step.dataset.workflowUiInstallRunbookStepCommand.includes("pbcopy < 'docs/github-pages-workflow.yml'")) && pagesApplyRunbookStep && pagesApplyRunbookStep.dataset.workflowUiInstallRunbookStepTarget === ".github/workflows/joopark-pages.yml" && pagesWorkflowInstallCard && pagesApplyRunbookStep.textContent.includes(pagesWorkflowInstallCard.dataset.workflowUiInstallAction) && driftApplyRunbookStep && driftApplyRunbookStep.dataset.workflowUiInstallRunbookStepTarget === ".github/workflows/joopark-drift-watch.yml" && driftWorkflowInstallCard && driftApplyRunbookStep.textContent.includes(driftWorkflowInstallCard.dataset.workflowUiInstallAction) && workflowRunbookSteps.some((step) => step.dataset.workflowUiInstallRunbookStepKey === "copy-drift-template" && step.dataset.workflowUiInstallRunbookStepCommand.includes("docs/github-drift-watch-workflow.yml")) && workflowRunbookSteps.some((step) => step.dataset.workflowUiInstallRunbookStepKey === "verify-remote-parity" && step.dataset.workflowUiInstallRunbookStepProof === "remoteWorkflowFilesReady=true") && workflowRunbookSteps.some((step) => step.dataset.workflowUiInstallRunbookStepKey === "verify-workflow-visibility" && step.dataset.workflowUiInstallRunbookStepCommand.includes("gh workflow list --repo biojuho/BIOJUHO-Projects")) && workflowRunbookSteps.some((step) => step.dataset.workflowUiInstallRunbookStepKey === "verify-dispatch-guard" && step.textContent.includes("verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown")), "workflow UI install runbook steps were incomplete");
    assert(workflowRunbook.querySelectorAll("[data-workflow-ui-install-runbook-link]").length >= 3 && workflowRunbookSignals.length === 8 && workflowRunbookSignals.some((signal) => signal.textContent.includes("remoteWorkflowFilesReady=true")) && workflowRunbookSignals.some((signal) => signal.textContent.includes("remoteWorkflowVisibilityReady=true")) && workflowRunbookSignals.some((signal) => signal.textContent.includes("safeToDispatch=true before gh workflow run")), "workflow UI install runbook links or expected signals were incomplete");
	    const systemPostInstallIntake = qs("[data-workflow-ui-install-intake]", workflowInstallPlan);
	    const systemPostInstallIntakeText = qs("[data-post-install-evidence-intake-text]", systemPostInstallIntake).textContent;
	    const systemPostInstallSequence = qs("[data-post-install-evidence-intake-sequence]", systemPostInstallIntake);
	    const systemPostInstallSequenceSteps = Array.from(systemPostInstallSequence.querySelectorAll("[data-post-install-evidence-intake-sequence-step]"));
	    const systemPostInstallQuickProof = qs("[data-post-install-quick-proof]", systemPostInstallIntake);
	    const systemPostInstallQuickProofSteps = Array.from(systemPostInstallQuickProof.querySelectorAll("[data-post-install-quick-proof-step]"));
	    const systemPostInstallQuickProofMap = qs("[data-post-install-quick-proof-field-map]", systemPostInstallIntake);
	    const systemPostInstallQuickProofMapItems = Array.from(systemPostInstallQuickProofMap.querySelectorAll("[data-post-install-quick-proof-field-map-item]"));
	    assert(systemPostInstallIntake.dataset.postInstallEvidenceIntakeReady === "true" && systemPostInstallIntake.dataset.postInstallEvidenceIntakeCommandCount === "4" && systemPostInstallIntake.dataset.postInstallEvidenceIntakeSignalCount === "8" && systemPostInstallIntake.dataset.postInstallEvidenceIntakeFieldCount === "6" && systemPostInstallIntake.dataset.postInstallEvidenceIntakeFieldCoverage === "1" && systemPostInstallIntake.dataset.postInstallEvidenceIntakeSequenceCount === "4" && systemPostInstallIntake.dataset.postInstallEvidenceIntakeSequenceReady === "true" && systemPostInstallIntake.dataset.postInstallEvidenceIntakeFinalCommand.includes("verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown") && systemPostInstallIntake.dataset.postInstallEvidenceIntakeDispatchGuard.includes("safeToDispatch=true") && systemPostInstallIntake.dataset.postInstallQuickProofReady === "true" && systemPostInstallIntake.dataset.postInstallQuickProofStepCount === "4" && systemPostInstallIntake.dataset.postInstallQuickProofCoverage === "1" && systemPostInstallIntake.dataset.postInstallQuickProofFieldMappingReady === "true" && systemPostInstallIntake.dataset.postInstallQuickProofFieldMappingCoverage === "1" && systemPostInstallIntake.dataset.postInstallQuickProofMappedFieldCount === "4" && systemPostInstallIntake.dataset.postInstallQuickProofCompletedMappedFieldCount === "0", "system post-install evidence intake state was incomplete");
	    assert(systemPostInstallQuickProof.dataset.postInstallQuickProofReady === "true" && systemPostInstallQuickProofSteps.length === 4 && systemPostInstallQuickProofSteps[0].dataset.postInstallQuickProofStepKey === "remote_file_parity" && systemPostInstallQuickProofSteps[3].dataset.postInstallQuickProofStepKey === "handoff_verifier", "system post-install quick proof was incomplete");
	    assert(systemPostInstallQuickProofMap.dataset.postInstallQuickProofFieldMappingReady === "true" && systemPostInstallQuickProofMap.dataset.postInstallQuickProofFieldMappingCoverage === "1" && systemPostInstallQuickProofMap.dataset.postInstallQuickProofMappedFieldCount === "4" && systemPostInstallQuickProofMap.dataset.postInstallQuickProofCompletedMappedFieldCount === "0" && systemPostInstallQuickProofMapItems.length === 4 && systemPostInstallQuickProofMapItems[0].dataset.postInstallQuickProofFieldMapStep === "remote_file_parity" && systemPostInstallQuickProofMapItems[0].dataset.postInstallQuickProofFieldMapField === "remote_parity_proof" && systemPostInstallQuickProofMapItems[3].dataset.postInstallQuickProofFieldMapStep === "handoff_verifier" && systemPostInstallQuickProofMapItems[3].dataset.postInstallQuickProofFieldMapField === "handoff_verifier_proof", "system post-install quick proof field map was incomplete");
	    assert(systemPostInstallIntake.querySelectorAll("[data-post-install-evidence-intake-check]").length === 5 && systemPostInstallIntake.querySelectorAll("[data-post-install-evidence-intake-command]").length === 4 && systemPostInstallIntake.querySelectorAll("[data-post-install-evidence-intake-signal]").length === 8 && systemPostInstallIntake.querySelectorAll("[data-post-install-evidence-intake-field]").length === 6 && systemPostInstallSequence.dataset.postInstallEvidenceIntakeSequenceCount === "4" && systemPostInstallSequenceSteps.length === 4 && systemPostInstallSequenceSteps[0].dataset.postInstallEvidenceIntakeSequenceKey === "remote_file_parity" && systemPostInstallSequenceSteps[3].dataset.postInstallEvidenceIntakeSequenceKey === "handoff_verifier", "system post-install evidence intake checklist was incomplete");
	    assert(systemPostInstallIntakeText.includes("JooPark Workflow Post-Install Evidence Intake") && systemPostInstallIntakeText.includes("JooPark Post-Install Quick Proof Receipt") && systemPostInstallIntakeText.includes("Quick proof: ready=true; steps=4; coverage=1") && systemPostInstallIntakeText.includes("Quick proof field mapping: ready=true; mapped=4; completed=0/4; coverage=1") && systemPostInstallIntakeText.includes("Mapped proof fields:") && systemPostInstallIntakeText.includes("remote_file_parity -> remote_parity_proof") && systemPostInstallIntakeText.includes("handoff_verifier -> handoff_verifier_proof") && systemPostInstallIntakeText.includes("not dispatch approval") && systemPostInstallIntakeText.includes("Evidence fields to fill:") && systemPostInstallIntakeText.includes("Verification sequence:") && systemPostInstallIntakeText.includes("1. remote_file_parity") && systemPostInstallIntakeText.includes("4. handoff_verifier") && systemPostInstallIntakeText.includes("Pages workflow commit") && systemPostInstallIntakeText.includes("Drift Watch workflow commit") && systemPostInstallIntakeText.includes("Remote parity proof") && systemPostInstallIntakeText.includes("Actions visibility proof") && systemPostInstallIntakeText.includes("Dispatch readiness proof") && systemPostInstallIntakeText.includes("Handoff verifier proof") && systemPostInstallIntakeText.includes("remoteWorkflowFilesReady=true") && systemPostInstallIntakeText.includes("remoteWorkflowVisibilityReady=true") && systemPostInstallIntakeText.includes("allDispatchReady=true") && systemPostInstallIntakeText.includes("safeToDispatch=true before gh workflow run") && systemPostInstallIntakeText.includes("Stop condition: do not run gh workflow run") && systemPostInstallIntakeText.includes("Do not run gh workflow run"), "system post-install evidence intake copy was incomplete");
	    const systemPostInstallProofParser = qs("[data-post-install-proof-parser]", systemPostInstallIntake);
	    const systemPostInstallProofParserRows = Array.from(systemPostInstallProofParser.querySelectorAll("[data-post-install-proof-parser-field]"));
	    const systemPostInstallProofParserSample = [
	      "pages_workflow_commit: https://github.com/biojuho/BIOJUHO-Projects/commit/abc1234 for .github/workflows/joopark-pages.yml",
	      "drift_workflow_commit: https://github.com/biojuho/BIOJUHO-Projects/commit/def5678 for .github/workflows/joopark-drift-watch.yml",
	      "remote_parity_proof: generatedAt=2026-06-08T00:00:00Z remoteWorkflowFilesReady=true remoteExists=true remoteMatchesTemplate=true",
	      "actions_visibility_proof: gh workflow list shows .github/workflows/joopark-pages.yml and .github/workflows/joopark-drift-watch.yml; remoteWorkflowVisibilityReady=true",
	      "dispatch_readiness_proof: dispatchReady=true driftDispatchReady=true allDispatchReady=true",
	      "handoff_verifier_proof: verify-launch-handoff reports safeToDispatch=true before gh workflow run",
	    ].join("\\n");
	    const initialPostInstallProofParserSummary = qs("[data-post-install-proof-parser-summary]", systemPostInstallProofParser).textContent;
	    assert(systemPostInstallProofParser.dataset.postInstallProofParserReady === "true" && systemPostInstallProofParser.dataset.postInstallProofParserCoverage === "1" && systemPostInstallProofParser.dataset.postInstallProofParserFieldCount === "6" && systemPostInstallProofParser.dataset.postInstallProofParserDetectedCount === "0" && systemPostInstallProofParser.dataset.postInstallProofParserDispatchApproval === "false" && systemPostInstallProofParserRows.length === 6 && systemPostInstallProofParserRows.every((row) => row.dataset.postInstallProofParserFieldDetected === "false" && row.dataset.postInstallProofParserFieldNextAction && row.textContent.includes("Next:")) && initialPostInstallProofParserSummary.includes("Missing field repair hints:") && initialPostInstallProofParserSummary.includes("node scripts/check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write") && initialPostInstallProofParserSummary.includes("node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects --write") && initialPostInstallProofParserSummary.includes("node scripts/verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown"), "post-install proof parser initial state was incomplete");
	    fill("[data-post-install-proof-parser-input]", workflowInstallText, systemPostInstallProofParser);
	    click("[data-post-install-proof-parser-parse]", systemPostInstallProofParser);
	    await waitFor(() => systemPostInstallProofParser.dataset.postInstallProofParserStatus !== "all_fields_detected" && Number(systemPostInstallProofParser.dataset.postInstallProofParserDetectedCount || 0) < 6 && qs("[data-post-install-proof-parser-summary]", systemPostInstallProofParser).textContent.includes("Missing field repair hints:"), "post-install proof parser treated the template receipt as complete proof");
	    postInstallProofParserFalsePositiveGuardOk = true;
	    fill("[data-post-install-proof-parser-input]", systemPostInstallProofParserSample, systemPostInstallProofParser);
	    click("[data-post-install-proof-parser-parse]", systemPostInstallProofParser);
	    await waitFor(() => systemPostInstallProofParser.dataset.postInstallProofParserStatus === "all_fields_detected" && systemPostInstallProofParser.dataset.postInstallProofParserDetectedCount === "6" && qs("[data-post-install-proof-parser-status-text]", systemPostInstallProofParser).textContent.includes("6/6 proof signals detected"), "post-install proof parser did not detect all fields");
	    const systemPostInstallProofParserSummary = qs("[data-post-install-proof-parser-summary]", systemPostInstallProofParser).textContent;
	    assert(systemPostInstallProofParserRows.every((row) => row.dataset.postInstallProofParserFieldDetected === "true" && row.dataset.postInstallProofParserFieldNextAction) && systemPostInstallProofParserSummary.includes("JooPark Post-Install Proof Parser Receipt") && systemPostInstallProofParserSummary.includes("postInstallProofParserCoverage=1") && systemPostInstallProofParserSummary.includes("Fields detected: 6/6") && systemPostInstallProofParserSummary.includes("pages_workflow_commit: detected") && systemPostInstallProofParserSummary.includes("drift_workflow_commit: detected") && systemPostInstallProofParserSummary.includes("remote_parity_proof: detected") && systemPostInstallProofParserSummary.includes("actions_visibility_proof: detected") && systemPostInstallProofParserSummary.includes("dispatch_readiness_proof: detected") && systemPostInstallProofParserSummary.includes("handoff_verifier_proof: detected") && systemPostInstallProofParserSummary.includes("nextAction=Run node scripts/verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown and paste safeToDispatch=true.") && systemPostInstallProofParserSummary.includes("Missing field repair hints:") && systemPostInstallProofParserSummary.includes("- none") && systemPostInstallProofParserSummary.includes("safeToDispatch=true") && systemPostInstallProofParserSummary.includes("not dispatch approval") && systemPostInstallProofParserSummary.includes("Stop condition: do not run gh workflow run"), "post-install proof parser summary was incomplete");
	    window.__smokeClipboardText = "";
	    click("[data-post-install-proof-parser-copy]", systemPostInstallProofParser);
	    await waitFor(() => systemPostInstallProofParser.dataset.postInstallProofParserSummaryCopied === "true" && qs("[data-post-install-proof-parser-copy-status]", systemPostInstallProofParser).textContent.includes("복사"), "post-install proof parser summary copy did not report success");
	    await waitFor(() => window.__smokeClipboardText.includes("JooPark Post-Install Proof Parser Receipt") && window.__smokeClipboardText.includes("postInstallProofParserCoverage=1") && window.__smokeClipboardText.includes("Fields detected: 6/6") && window.__smokeClipboardText.includes("Missing field repair hints:") && window.__smokeClipboardText.includes("nextAction=Run node scripts/verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown and paste safeToDispatch=true.") && window.__smokeClipboardText.includes("not dispatch approval"), "post-install proof parser summary copy text did not reach clipboard");
	    postInstallProofParserOk = true;
    postInstallEvidenceIntakeOk = true;
    assert(workflowInstallPlan.querySelectorAll("[data-workflow-ui-install-new-file]").length === 2 && workflowInstallPlan.querySelectorAll("[data-workflow-ui-install-workflow-url]").length === 2, "workflow UI install panel links were incomplete");
    const workflowInstallReceipt = qs("[data-workflow-ui-install-receipt]", workflowInstallPlan);
    const workflowInstallReceiptText = qs("[data-workflow-ui-install-receipt-text]", workflowInstallReceipt).textContent;
    const workflowInstallReceiptMatchesRepairPlan = (text) => {
      const pagesOpenCommand = pagesWorkflowInstallCard?.dataset.workflowUiInstallOpenCommand || "";
      const pagesAction = pagesWorkflowInstallCard?.dataset.workflowUiInstallAction || "";
      const pagesRequired = pagesWorkflowInstallCard?.dataset.workflowUiInstallRequired === "true";
      const pagesReady = !!pagesWorkflowInstallCard &&
        text.includes("pages: installAction=" + pagesAction) &&
        (pagesRequired
          ? text.includes("pbcopy < 'docs/github-pages-workflow.yml'") && text.includes(pagesOpenCommand)
          : text.includes("No GitHub UI edit is required for .github/workflows/joopark-pages.yml"));
      const driftRequired = driftWorkflowInstallCard?.dataset.workflowUiInstallRequired === "true";
      const driftAction = driftWorkflowInstallCard?.dataset.workflowUiInstallAction || "";
      const driftReady = !!driftWorkflowInstallCard &&
        text.includes("drift-watch: installAction=" + driftAction) &&
        (driftRequired
          ? text.includes("pbcopy < 'docs/github-drift-watch-workflow.yml'") && text.includes(driftWorkflowInstallCard.dataset.workflowUiInstallOpenCommand || "")
          : text.includes("No GitHub UI edit is required for .github/workflows/joopark-drift-watch.yml"));
      return pagesReady && driftReady;
    };
	    assert(workflowInstallReceipt.dataset.workflowUiInstallReceiptReady === "true" && workflowInstallReceipt.dataset.workflowUiInstallPastePacketReady === "true" && workflowInstallReceiptText.includes("JooPark GitHub UI Workflow Install Receipt") && workflowInstallReceiptText.includes("JooPark GitHub UI Workflow Paste Packet") && workflowInstallReceiptText.includes("Status: ready for GitHub UI install; not remote installation proof") && workflowInstallReceiptText.includes("Paste exact template content") && workflowInstallReceiptText.includes("Install commands:") && workflowInstallReceiptMatchesRepairPlan(workflowInstallReceiptText) && workflowInstallReceiptText.includes("GitHub new-file form values:") && workflowInstallReceiptText.includes("githubFileNameFieldValue=.github/workflows/joopark-pages.yml") && workflowInstallReceiptText.includes("suggestedCommitMessage=Add JooPark Pages publish workflow") && workflowInstallReceiptText.includes("githubFileNameFieldValue=.github/workflows/joopark-drift-watch.yml") && workflowInstallReceiptText.includes("suggestedCommitMessage=Add JooPark candidate drift watch workflow") && workflowInstallReceiptText.includes("Post-install verification commands:") && workflowInstallReceiptText.includes("check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write") && workflowInstallReceiptText.includes("gh workflow list --repo biojuho/BIOJUHO-Projects --all --json name,path,state,id") && workflowInstallReceiptText.includes("verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown") && workflowInstallReceiptText.includes("Post-install evidence fields to fill:") && workflowInstallReceiptText.includes("Parser-ready proof block:") && workflowInstallReceiptText.includes("pages_workflow_commit:") && workflowInstallReceiptText.includes("The parser ignores bracketed [paste ...] placeholders") && workflowInstallReceiptText.includes("Pages workflow commit") && workflowInstallReceiptText.includes("Handoff verifier proof") && workflowInstallReceiptText.includes("remoteWorkflowFilesReady=true") && workflowInstallReceiptText.includes("remoteWorkflowVisibilityReady=true") && workflowInstallReceiptText.includes("dispatchReady=true") && workflowInstallReceiptText.includes("driftDispatchReady=true") && workflowInstallReceiptText.includes("allDispatchReady=true") && workflowInstallReceiptText.includes("safeToDispatch=true before gh workflow run") && workflowInstallReceiptText.includes("Stop condition: do not run gh workflow run") && workflowInstallReceiptText.includes("all six post-install evidence fields are filled") && workflowInstallReceiptText.includes("every post-install evidence field has been filled") && workflowInstallReceiptText.includes("verify-launch-handoff reports safeToDispatch=true") && workflowInstallReceiptText.includes("External benchmark: GitHub UI file creation") && workflowInstallReceiptText.includes("workflow_dispatch workflow exists on the default branch") && workflowInstallReceiptText.includes("Do not run gh workflow run until remoteWorkflowFilesReady: true, remoteWorkflowVisibilityReady: true, dispatchReady: true, driftDispatchReady: true, and allDispatchReady: true."), "workflow UI install receipt was not copy-ready");
    window.__smokeClipboardText = "";
    click("[data-workflow-ui-install-receipt-copy]", workflowInstallPlan);
    await waitFor(() => workflowInstallReceipt.dataset.workflowUiInstallReceiptCopied === "true" && workflowInstallReceipt.dataset.workflowUiInstallPastePacketCopied === "true" && qs("[data-workflow-ui-install-receipt-copy-status]", workflowInstallReceipt).textContent.includes("복사"), "workflow UI install receipt copy did not report success");
	    await waitFor(() => window.__smokeClipboardText.includes("JooPark GitHub UI Workflow Install Receipt") && window.__smokeClipboardText.includes("JooPark GitHub UI Workflow Paste Packet") && window.__smokeClipboardText.includes("Status: ready for GitHub UI install; not remote installation proof") && window.__smokeClipboardText.includes("Paste exact template content") && workflowInstallReceiptMatchesRepairPlan(window.__smokeClipboardText) && window.__smokeClipboardText.includes("GitHub new-file form values:") && window.__smokeClipboardText.includes("githubFileNameFieldValue=.github/workflows/joopark-pages.yml") && window.__smokeClipboardText.includes("suggestedCommitMessage=Add JooPark Pages publish workflow") && window.__smokeClipboardText.includes("check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write") && window.__smokeClipboardText.includes("plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects --write") && window.__smokeClipboardText.includes("verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown") && window.__smokeClipboardText.includes("Post-install evidence fields to fill:") && window.__smokeClipboardText.includes("Parser-ready proof block:") && window.__smokeClipboardText.includes("pages_workflow_commit:") && window.__smokeClipboardText.includes("The parser ignores bracketed [paste ...] placeholders") && window.__smokeClipboardText.includes("Handoff verifier proof") && window.__smokeClipboardText.includes("remoteWorkflowFilesReady=true") && window.__smokeClipboardText.includes("dispatchReady=true") && window.__smokeClipboardText.includes("driftDispatchReady=true") && window.__smokeClipboardText.includes("safeToDispatch=true before gh workflow run") && window.__smokeClipboardText.includes("Stop condition: do not run gh workflow run") && window.__smokeClipboardText.includes("all six post-install evidence fields are filled") && window.__smokeClipboardText.includes("every post-install evidence field has been filled") && window.__smokeClipboardText.includes("verify-launch-handoff reports safeToDispatch=true") && window.__smokeClipboardText.includes("External benchmark: GitHub UI file creation") && window.__smokeClipboardText.includes("Do not run gh workflow run until remoteWorkflowFilesReady: true"), "workflow UI install receipt copy text did not reach clipboard");
    workflowUiInstallReceiptCopyOk = true;
    workflowUiInstallPlanPanelOk = true;
	    const dispatchPlanReady = (node) => {
	      if (!node ||
	        node.dataset.publishDispatchLoaded !== "true" ||
	        node.dataset.publishDispatchSource !== "data/publish-dispatch-plan.json" ||
	        node.dataset.publishDispatchRepo !== "biojuho/BIOJUHO-Projects" ||
	        node.dataset.publishDispatchRepoReady !== "true" ||
	        node.dataset.publishDispatchLocalTargetsReady !== "true" ||
	        node.dataset.publishDispatchLocalTargetParityReady !== "true" ||
	        node.dataset.publishDispatchWorkflowScopeChecked !== "true" ||
	        !["true", "false"].includes(node.dataset.publishDispatchWorkflowScopeAvailable || "") ||
	        !["true", "false"].includes(node.dataset.publishDispatchWorkflowScopeInstallBlocked || "") ||
	        !(node.dataset.publishDispatchWorkflowScopeScopes || "").includes("repo") ||
	        !(node.dataset.publishDispatchWorkflowScopeAvailable === "true" || node.dataset.publishDispatchWorkflowScopeMissing === "workflow") ||
	        !(node.dataset.publishDispatchWorkflowScopeSource || "").length ||
	        node.dataset.publishDispatchWorkflowScopeRefreshCommand !== "gh auth refresh -h github.com -s workflow" ||
	        !node.dataset.publishDispatchWorkflowScopeRecheckCommand.includes("plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects") ||
	        node.getAttribute("data-publish-dispatch-default-branch-handoff") !== "true" ||
	        node.dataset.publishDispatchSuggestedCommandsSafe !== "true" ||
	        !node.dataset.publishDispatchNextCommand.includes("plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects")) {
	        return false;
	      }
	      const allReady = node.dataset.publishDispatchAllReady === "true";
	      if (allReady) {
	        return node.dataset.publishDispatchRemoteVisible === "true" &&
	          node.dataset.publishDispatchReady === "true" &&
	          node.dataset.publishDispatchDriftReady === "true" &&
	          node.dataset.publishDispatchSuggestedDispatchCount === "2" &&
	          node.dataset.publishDispatchWithheldDispatchCount === "0" &&
	          node.dataset.publishDispatchDispatchSuggestionStatus === "ready";
	      }
	      return ["true", "false"].includes(node.dataset.publishDispatchRemoteVisible || "") &&
	        ["true", "false"].includes(node.dataset.publishDispatchReady || "") &&
	        ["true", "false"].includes(node.dataset.publishDispatchDriftReady || "") &&
	        (node.dataset.publishDispatchReady === "false" || node.dataset.publishDispatchDriftReady === "false") &&
	        node.dataset.publishDispatchSuggestedDispatchCount === "0" &&
	        node.dataset.publishDispatchWithheldDispatchCount === "2" &&
	        node.dataset.publishDispatchDispatchSuggestionStatus === "withheld-until-all-dispatch-ready";
	    };
	    await waitFor(() => dispatchPlanReady(document.querySelector("[data-system-publish-dispatch-plan]")), "publish dispatch plan data attributes were incomplete");
	    panel = qs("[data-system-publish-readiness]");
	    const dispatchPlan = qs("[data-system-publish-dispatch-plan]", panel);
	    const dispatchCards = Array.from(dispatchPlan.querySelectorAll("[data-publish-dispatch-workflow-card]"));
	    const dispatchText = dispatchPlan.textContent || "";
	    const dispatchAllReady = dispatchPlan.dataset.publishDispatchAllReady === "true";
	    assert(dispatchPlanReady(dispatchPlan), "publish dispatch plan data attributes were incomplete");
	    assert(!!dispatchPlan.querySelector("[data-publish-dispatch-default-branch-handoff]"), "publish dispatch default-branch handoff did not render");
	    assert(dispatchCards.length === 2 && dispatchCards.every((card) => ["true", "false"].includes(card.dataset.publishDispatchWorkflowReady || "") && card.dataset.publishDispatchWorkflowTargetExists === "true" && card.dataset.publishDispatchWorkflowTargetMatchesTemplate === "true") && (dispatchAllReady ? dispatchCards.every((card) => card.dataset.publishDispatchWorkflowReady === "true") : dispatchCards.some((card) => card.dataset.publishDispatchWorkflowReady === "false")), "publish dispatch workflow cards were incomplete");
	    assert(dispatchCards.some((card) => card.dataset.publishDispatchWorkflowPath === ".github/workflows/joopark-pages.yml") && dispatchCards.some((card) => card.dataset.publishDispatchWorkflowPath === ".github/workflows/joopark-drift-watch.yml"), "publish dispatch workflow target cards were missing");
		    const dispatchBlockedByVisibility = dispatchText.includes("workflow is not visible in GitHub Actions");
		    const dispatchBlockedByRemoteParity = dispatchText.includes("remote workflow file does not match the local template");
		    assert(dispatchText.includes("data/publish-dispatch-plan.json") && dispatchText.includes("workflowListCommand") && dispatchText.includes("repoEvidenceReady") && dispatchText.includes("localWorkflowTargetsReady") && dispatchText.includes("localTargetParityReady") && dispatchText.includes("targetMatchesTemplate") && dispatchText.includes("remoteWorkflowVisibilityReady") && dispatchText.includes("workflowScopeAvailable") && dispatchText.includes("workflowScopeInstallBlocked") && dispatchText.includes("workflowScopeRefreshCommand") && dispatchText.includes("workflowScopeRefreshClipboardCommand") && dispatchText.includes("workflowScopeRecheckCommand") && dispatchText.includes("gh auth refresh -h github.com -s workflow") && dispatchText.includes("interactiveApprovalRequired") && dispatchText.includes("terminalWaitRequired") && dispatchText.includes("Token scopes still omit workflow after the refresh attempt") && dispatchText.includes("workflowScope.scopes") && dispatchText.includes("workflowScope.missing") && dispatchText.includes("Auth preflight") && dispatchText.includes("auth preflight only") && dispatchText.includes("workflow scope evidence") && dispatchText.includes("repo") && dispatchText.includes("workflowDefaultBranchHandoff") && dispatchText.includes("git add .github/workflows/joopark-pages.yml .github/workflows/joopark-drift-watch.yml") && dispatchText.includes("git commit -m 'Add JooPark publish workflows'") && dispatchText.includes("dispatchReady") && dispatchText.includes("driftDispatchReady") && dispatchText.includes("allDispatchReady") && dispatchText.includes("suggestedDispatchCommandCount") && dispatchText.includes("withheldDispatchCommandCount") && (dispatchAllReady ? dispatchText.includes("gh workflow run --repo biojuho/BIOJUHO-Projects joopark-pages.yml -f ref=codex/joopark-workspace-release") : (dispatchBlockedByVisibility || dispatchBlockedByRemoteParity)), "publish dispatch plan blockers were not surfaced");
	    const authPreflight = qs("[data-publish-dispatch-auth-preflight]", dispatchPlan);
	    const authPreflightText = authPreflight.textContent || "";
	    assert(["true", "false"].includes(authPreflight.dataset.publishDispatchAuthPreflightAvailable) && ["true", "false"].includes(authPreflight.dataset.publishDispatchAuthPreflightInstallBlocked) && Number(authPreflight.dataset.publishDispatchAuthPreflightScopeCount || "0") >= 3 && authPreflight.dataset.publishDispatchAuthPreflightSource.length > 0 && authPreflightText.includes("Auth preflight") && authPreflightText.includes("auth preflight only") && authPreflightText.includes("workflowScopeAvailable=" + authPreflight.dataset.publishDispatchAuthPreflightAvailable) && authPreflightText.includes("workflowScopeInstallBlocked=" + authPreflight.dataset.publishDispatchAuthPreflightInstallBlocked) && authPreflightText.includes("workflowScope.scopes=") && authPreflightText.includes(authPreflight.dataset.publishDispatchAuthPreflightAvailable === "true" ? "Missing scope=none" : "Missing scope=workflow") && authPreflightText.includes("workflowScopeRefreshCommand=gh auth refresh -h github.com -s workflow") && authPreflightText.includes("workflowScopeRefreshClipboardCommand=gh auth refresh -h github.com -s workflow --clipboard") && authPreflightText.includes("workflowScopeRecheckCommand=node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects") && authPreflightText.includes("interactiveApprovalRequired=" + (authPreflight.dataset.publishDispatchAuthPreflightAvailable === "true" ? "false" : "true")) && authPreflightText.includes("terminalWaitRequired=" + (authPreflight.dataset.publishDispatchAuthPreflightAvailable === "true" ? "false" : "true")) && authPreflightText.includes("Token scopes still omit workflow after the refresh attempt") && authPreflightText.includes("does not install workflow files") && authPreflightText.includes("allDispatchReady: true"), "publish dispatch auth preflight card was not surfaced");
    publishDispatchAuthPreflightOk = true;
	    const workflowScopePacket = qs("[data-publish-dispatch-workflow-scope-packet]", dispatchPlan);
	    const workflowScopePacketText = qs("[data-publish-dispatch-workflow-scope-packet-text]", workflowScopePacket).textContent;
	    assert(workflowScopePacket.dataset.publishDispatchWorkflowScopePacketReady === "true" && workflowScopePacketText.includes("JooPark Workflow Scope Refresh Packet") && workflowScopePacketText.includes("workflowScope.scopes:") && workflowScopePacketText.includes("workflowScopeAvailable: " + dispatchPlan.dataset.publishDispatchWorkflowScopeAvailable) && workflowScopePacketText.includes("workflowScopeInstallBlocked: " + dispatchPlan.dataset.publishDispatchWorkflowScopeInstallBlocked) && workflowScopePacketText.includes(dispatchPlan.dataset.publishDispatchWorkflowScopeAvailable === "true" ? "Missing scope: none" : "Missing scope: workflow") && workflowScopePacketText.includes("gh auth refresh -h github.com -s workflow") && workflowScopePacketText.includes("gh auth refresh -h github.com -s workflow --clipboard") && workflowScopePacketText.includes("Interactive approval required: " + (dispatchPlan.dataset.publishDispatchWorkflowScopeAvailable === "true" ? "false" : "true")) && workflowScopePacketText.includes("Terminal wait required: " + (dispatchPlan.dataset.publishDispatchWorkflowScopeAvailable === "true" ? "false" : "true")) && workflowScopePacketText.includes("Incomplete approval signal: Token scopes still omit workflow after the refresh attempt") && workflowScopePacketText.includes("node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects") && workflowScopePacketText.includes("Do not run gh workflow run until remoteWorkflowFilesReady: true"), "publish workflow scope refresh packet was not copy-ready");
    window.__smokeClipboardText = "";
    click("[data-publish-dispatch-workflow-scope-packet-copy]", workflowScopePacket);
    await waitFor(() => workflowScopePacket.dataset.publishDispatchWorkflowScopePacketCopied === "true" && qs("[data-publish-dispatch-workflow-scope-packet-copy-status]", workflowScopePacket).textContent.includes("복사"), "publish workflow scope packet copy did not report success");
	    await waitFor(() => window.__smokeClipboardText.includes("JooPark Workflow Scope Refresh Packet") && window.__smokeClipboardText.includes("workflowScope.scopes:") && window.__smokeClipboardText.includes(dispatchPlan.dataset.publishDispatchWorkflowScopeAvailable === "true" ? "Missing scope: none" : "Missing scope: workflow") && window.__smokeClipboardText.includes("gh auth refresh -h github.com -s workflow") && window.__smokeClipboardText.includes("gh auth refresh -h github.com -s workflow --clipboard") && window.__smokeClipboardText.includes("Interactive approval required: " + (dispatchPlan.dataset.publishDispatchWorkflowScopeAvailable === "true" ? "false" : "true")) && window.__smokeClipboardText.includes("Terminal wait required: " + (dispatchPlan.dataset.publishDispatchWorkflowScopeAvailable === "true" ? "false" : "true")) && window.__smokeClipboardText.includes("Do not run gh workflow run until remoteWorkflowFilesReady: true"), "publish workflow scope packet copy text did not reach clipboard");
    publishDispatchWorkflowScopePacketCopyOk = true;
    const suggestedCommandsText = dispatchPlan.querySelector("[data-publish-dispatch-suggested-commands]")?.textContent || "";
    const dispatchGuardText = dispatchPlan.querySelector("[data-publish-dispatch-dispatch-command-guard]")?.textContent || "";
    const withheldDispatchCommands = dispatchPlan.querySelector("[data-publish-dispatch-withheld-dispatch-commands]");
    const withheldDispatchCommandsText = withheldDispatchCommands?.textContent || "";
	    if (dispatchAllReady) {
	      assert(suggestedCommandsText.includes("plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects") && suggestedCommandsText.includes("gh workflow run --repo biojuho/BIOJUHO-Projects joopark-pages.yml -f ref=codex/joopark-workspace-release") && suggestedCommandsText.includes("gh workflow run --repo biojuho/BIOJUHO-Projects joopark-drift-watch.yml -f mode=advisory"), "publish dispatch suggested commands should include dispatch after allDispatchReady");
	      assert(dispatchGuardText.includes("suggestedDispatchCommands") && dispatchGuardText.includes("ready"), "publish dispatch command guard did not explain ready dispatch commands");
	      assert(!withheldDispatchCommands || withheldDispatchCommands.dataset.publishDispatchWithheldDispatchCount === "0", "publish dispatch withheld command list should be empty after allDispatchReady");
	    } else {
	      assert(suggestedCommandsText.includes("plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects") && !suggestedCommandsText.includes("gh workflow run --repo"), "publish dispatch suggested commands should not include dispatch before allDispatchReady");
	      assert(dispatchGuardText.includes("suggestedDispatchCommands") && dispatchGuardText.includes("withheld until allDispatchReady: true"), "publish dispatch command guard did not explain withheld dispatch commands");
	      assert(withheldDispatchCommands?.dataset.publishDispatchWithheldDispatchCount === "2" && withheldDispatchCommandsText.includes("withheldDispatchCommands") && withheldDispatchCommandsText.includes("gh workflow run --repo biojuho/BIOJUHO-Projects joopark-pages.yml -f ref=codex/joopark-workspace-release") && withheldDispatchCommandsText.includes("gh workflow run --repo biojuho/BIOJUHO-Projects joopark-drift-watch.yml -f mode=advisory"), "publish dispatch withheld command list was incomplete");
	    }
    assert(dispatchText.includes("gh workflow run --repo biojuho/BIOJUHO-Projects joopark-pages.yml -f ref=codex/joopark-workspace-release") && dispatchText.includes("gh workflow run --repo biojuho/BIOJUHO-Projects joopark-drift-watch.yml -f mode=advisory") && dispatchText.includes("nextVerificationCommand") && dispatchText.includes("suggestedCommands") && dispatchText.includes("suggestedDispatchCommands") && dispatchText.includes("withheldDispatchCommands"), "publish dispatch plan commands were incomplete");
    publishDispatchPlanPanelOk = true;
    await waitFor(() => document.querySelector("[data-system-remote-workflow-file-check]")?.dataset.remoteWorkflowFileLoaded === "true", "remote workflow file check did not load", 15000);
    panel = qs("[data-system-publish-readiness]");
	    const remoteFileCheck = qs("[data-system-remote-workflow-file-check]", panel);
	    const remoteFileCards = Array.from(remoteFileCheck.querySelectorAll("[data-remote-workflow-file-card][data-remote-workflow-file-install-action][data-remote-workflow-file-edit-url]"));
	    const remoteFileText = remoteFileCheck.textContent || "";
	    const remoteFilesReady = remoteFileCheck.dataset.remoteWorkflowFileReady === "true";
		    assert(remoteFileCheck.dataset.remoteWorkflowFileSource === "data/remote-workflow-file-check.json" && remoteFileCheck.dataset.remoteWorkflowFileLoaded === "true" && remoteFileCheck.dataset.remoteWorkflowFileChecked === "true" && remoteFileCheck.dataset.remoteWorkflowFileRepoReady === "true" && remoteFileCheck.dataset.remoteWorkflowFileCheckCount === "2" && Number(remoteFileCheck.dataset.remoteWorkflowFileBlockerCount || "0") === (remoteFilesReady ? 0 : Number(remoteFileCheck.dataset.remoteWorkflowFileBlockerCount || "0")) && ["replace_existing_remote_file", "create_missing_remote_file", "verified_remote_matches_template"].includes(remoteFileCheck.dataset.remoteWorkflowFileRemediationAction || "") && remoteFileCheck.dataset.remoteWorkflowFileNextCommand.includes("check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write") && ["true", "false"].includes(remoteFileCheck.dataset.remoteWorkflowFileWorkflowScopeAvailable || "") && ["true", "false"].includes(remoteFileCheck.dataset.remoteWorkflowFileWorkflowScopeInstallBlocked || "") && ["not_required", "approval_required"].includes(remoteFileCheck.dataset.remoteWorkflowFileWorkflowScopeApprovalStatus) && remoteFileCheck.dataset.remoteWorkflowFileWorkflowScopeApprovalUrl === "https://github.com/login/device", "remote workflow file check state was not surfaced");
	    assert(qs("[data-remote-workflow-file-state-label]", remoteFileCheck).textContent.includes(remoteFilesReady ? "ready" : "action required"), "remote workflow file check did not label current state");
		    assert(remoteFileCards.length === 2 && remoteFileCards.every((card) => ["true", "false"].includes(card.dataset.remoteWorkflowFileExists || "") && ["true", "false"].includes(card.dataset.remoteWorkflowFileMatchesTemplate || "") && ["replace_existing_remote_file", "create_missing_remote_file", "verified_remote_matches_template"].includes(card.dataset.remoteWorkflowFileInstallAction || "")) && (remoteFilesReady || remoteFileCards.some((card) => card.dataset.remoteWorkflowFileMatchesTemplate === "false")), "remote workflow file cards were incomplete");
    assert(remoteFileCards.some((card) => card.dataset.remoteWorkflowFilePath === ".github/workflows/joopark-pages.yml") && remoteFileCards.some((card) => card.dataset.remoteWorkflowFilePath === ".github/workflows/joopark-drift-watch.yml"), "remote workflow file paths were missing");
		    const remoteFileUiInstallTextReady = remoteFilesReady || remoteFileText.includes("use each workflow row's installAction") || remoteFileText.includes("GitHub UI fallback");
			    const remoteFileNeedsInstallOrUpdate = remoteFileText.includes("remote workflow file is not installed on main") || remoteFileText.includes("remote workflow file differs from local template");
			    const remoteFileInteractiveApprovalExpected = remoteFileCheck.dataset.remoteWorkflowFileWorkflowScopeInstallBlocked === "true";
			    assert(remoteFileText.includes("data/remote-workflow-file-check.json") && remoteFileText.includes("GitHub Contents API") && remoteFileText.includes("defaultBranch") && remoteFileText.includes("repoEvidenceReady") && remoteFileText.includes("remoteWorkflowFilesChecked") && remoteFileText.includes("remoteWorkflowFilesReady") && remoteFileText.includes("remediationAction") && remoteFileText.includes("workflowScopeAvailable") && remoteFileText.includes("workflowScopeInstallBlocked") && remoteFileText.includes("workflow scope preflight") && remoteFileText.includes("approvalUrl=https://github.com/login/device") && remoteFileText.includes("Device-code approval handoff") && remoteFileText.includes("one-time device code") && remoteFileText.includes("gh auth refresh -h github.com -s workflow --clipboard") && remoteFileText.includes("interactiveApprovalRequired=" + (remoteFileInteractiveApprovalExpected ? "true" : "false")) && remoteFileText.includes("terminalWaitRequired=" + (remoteFileInteractiveApprovalExpected ? "true" : "false")) && remoteFileText.includes("Token scopes still omit workflow after the refresh attempt") && remoteFileUiInstallTextReady && remoteFileText.includes("templateSha256") && remoteFileText.includes("remoteSha256") && remoteFileText.includes("remoteBlobSha") && remoteFileText.includes("installAction") && remoteFileText.includes("githubEditFileUrl") && remoteFileText.includes("remoteExists") && remoteFileText.includes("remoteMatchesTemplate") && (remoteFilesReady ? (remoteFileText.includes("remoteExists=true") && remoteFileText.includes("remoteMatchesTemplate=true")) : remoteFileNeedsInstallOrUpdate) && (remoteFilesReady || (remoteFileText.includes("pbcopy < 'docs/github-pages-workflow.yml'") && (remoteFileText.includes("githubNewFileUrl") || remoteFileText.includes("githubEditFileUrl")))) && remoteFileText.includes("check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write"), "remote workflow file check blockers were not surfaced");
	    const remoteInstallPacket = qs("[data-remote-workflow-install-packet]", remoteFileCheck);
	    const remoteInstallPacketText = qs("[data-remote-workflow-install-packet-text]", remoteInstallPacket).textContent;
	    const remoteInstallWorkflowScopeAvailable = remoteFileCheck.dataset.remoteWorkflowFileWorkflowScopeAvailable;
	    const remoteInstallWorkflowScopeBlocked = remoteFileCheck.dataset.remoteWorkflowFileWorkflowScopeInstallBlocked;
	    const remoteInstallApprovalExpected = remoteInstallWorkflowScopeBlocked === "true";
	    const remoteInstallPacketHasCurrentState = (text) => text.includes("JooPark Remote Workflow Install Packet") && text.includes(remoteFilesReady ? "Status: remote workflow files ready" : "Status: action required - install workflow files on the default branch") && text.includes("Repo: biojuho/BIOJUHO-Projects") && text.includes("Default branch: main") && text.includes("workflowScopeAvailable: " + remoteInstallWorkflowScopeAvailable) && text.includes("workflowScopeInstallBlocked: " + remoteInstallWorkflowScopeBlocked) && text.includes("Workflow scope preflight:") && text.includes("refresh with clipboard: gh auth refresh -h github.com -s workflow --clipboard") && text.includes("approvalUrl: https://github.com/login/device") && text.includes("interactive approval required: " + (remoteInstallApprovalExpected ? "true" : "false")) && text.includes("terminal wait required: " + (remoteInstallApprovalExpected ? "true" : "false")) && text.includes("incomplete approval signal: Token scopes still omit workflow after the refresh attempt") && text.includes("one-time device code policy") && text.includes("GitHub UI fallback") && (remoteFilesReady || text.includes("use each workflow row's installAction")) && (remoteFilesReady || text.includes("do not use new-file links for replace_existing_remote_file rows")) && text.includes("Existing workflow file edits use GitHub's file editor") && text.includes("API replacement of an existing workflow file requires the current blob SHA") && text.includes("Manual workflow dispatch requires workflow_dispatch") && text.includes("Action:") && text.includes("Remote blob SHA:") && text.includes("Open GitHub edit page:") && text.includes("pbcopy < 'docs/github-pages-workflow.yml'") && text.includes("open 'https://github.com/biojuho/BIOJUHO-Projects/edit/main/.github/workflows/joopark-pages.yml'") && text.includes("pbcopy < 'docs/github-drift-watch-workflow.yml'") && text.includes("Post-install verification checklist:") && text.includes("remoteWorkflowFilesChecked: true") && text.includes("pages remoteExists: true and remoteMatchesTemplate: true") && text.includes("drift-watch remoteExists: true and remoteMatchesTemplate: true") && text.includes("remoteWorkflowVisibilityReady: true") && text.includes("allDispatchReady: true") && (remoteFilesReady ? text.includes("Current blockers:\\n- none") : (text.includes("remote workflow file is not installed on main") || text.includes("remote workflow file differs from local template"))) && text.includes("remoteWorkflowFilesReady: true and allDispatchReady: true");
		    assert(remoteInstallPacket.dataset.remoteWorkflowInstallPacketReady === "true" && remoteInstallPacketHasCurrentState(remoteInstallPacketText), "remote workflow install packet was not copy-ready");
    window.__smokeClipboardText = "";
    click("[data-remote-workflow-install-packet-copy]", remoteFileCheck);
    await waitFor(() => remoteInstallPacket.dataset.remoteWorkflowInstallPacketCopied === "true" && qs("[data-remote-workflow-install-packet-copy-status]", remoteInstallPacket).textContent.includes("복사"), "remote workflow install packet copy did not report success");
		    await waitFor(() => remoteInstallPacketHasCurrentState(window.__smokeClipboardText) && window.__smokeClipboardText.includes("Install or repair steps:") && window.__smokeClipboardText.includes("check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write") && window.__smokeClipboardText.includes("Do not run gh workflow run until remoteWorkflowFilesReady: true and allDispatchReady: true"), "remote workflow install packet copy text did not reach clipboard");
    remoteWorkflowFileCheckPanelOk = true;
	    const launchPacketReady = (node) => {
	      if (!node ||
	        node.dataset.launchExecutionSource !== "data/launch-execution-packet.json" ||
	        node.dataset.launchExecutionLoaded !== "true" ||
	        node.dataset.launchExecutionStageCount !== "5" ||
	        node.dataset.launchExecutionComparisonCount !== "2" ||
	        node.dataset.launchExecutionPostAuthCheckpointRecheckCount !== "5" ||
	        node.dataset.launchExecutionPostAuthCheckpointSourceArtifactCount !== "4" ||
	        node.dataset.launchExecutionPostAuthCheckpointDispatchApproval !== "false" ||
	        node.dataset.launchExecutionPostAuthCheckpointVerificationOnly !== "true" ||
	        node.dataset.launchExecutionCurrentActionStage !== "install_workflows" ||
	        Number(node.dataset.launchExecutionCurrentActionCommandCount || "0") < 2 ||
	        Number(node.dataset.launchExecutionCurrentActionWithheldCount || "0") < 2 ||
	        node.dataset.launchExecutionCurrentActionAcceptanceCount !== "5" ||
	        node.dataset.launchExecutionCurrentActionVerifyCount !== "4" ||
	        node.dataset.launchExecutionTransitionGateCommand !== "node scripts/verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown" ||
	        node.dataset.launchExecutionBlockerResolutionSource !== "generated_from_launch_execution_packet" ||
	        node.dataset.launchExecutionBlockerResolutionItemCount !== "6" ||
	        node.dataset.launchPostInstallEvidenceIntakeSource !== "generated_from_launch_execution_packet" ||
	        node.dataset.launchPostInstallEvidenceIntakeReady !== "true" ||
	        node.dataset.launchPostInstallEvidenceIntakeFieldCount !== "6" ||
	        node.dataset.launchPostInstallEvidenceIntakeCommandCount !== "4" ||
	        node.dataset.launchPostInstallEvidenceIntakeSignalCount !== "8" ||
	        node.dataset.launchPostInstallEvidenceIntakeFieldCoverage !== "1" ||
	        node.dataset.launchPostInstallQuickProofReady !== "true" ||
	        node.dataset.launchPostInstallQuickProofStepCount !== "4" ||
	        node.dataset.launchPostInstallQuickProofCoverage !== "1" ||
	        node.dataset.launchPostInstallQuickProofFieldMappingReady !== "true" ||
	        node.dataset.launchPostInstallQuickProofFieldMappingCoverage !== "1" ||
	        node.dataset.launchPostInstallQuickProofMappedFieldCount !== "4" ||
	        node.dataset.launchPostInstallQuickProofFinalCommand.includes("verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown") === false ||
	        node.dataset.remoteWorkflowFileLedgerSource !== "generated_from_remote_workflow_file_check" ||
	        node.dataset.remoteWorkflowFileLedgerFileCount !== "2" ||
		        node.dataset.launchProofLedgerSource !== "generated_from_launch_execution_packet" ||
		        node.dataset.launchProofLedgerRequiredCount !== "6" ||
		        node.dataset.launchProofLedgerCurrentGate !== "capture_launch_proof" ||
		        node.dataset.launchExecutionAuthApprovalUrl !== "https://github.com/login/device" ||
		        node.dataset.launchExecutionPostAuthCheckpointCommandCount !== "5" ||
		        !node.dataset.launchProofLedgerCaptureCommand.includes("capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --write")) {
	        return false;
	      }
	      if (node.dataset.launchExecutionExternalReady === "true") {
	        return node.dataset.launchExecutionReadyToDispatch === "true" &&
	          node.dataset.launchExecutionProofReady === "true" &&
	          node.dataset.launchExecutionAuthPreflightStatus === "pass" &&
	          node.dataset.launchExecutionAuthWorkflowScopeAvailable === "true" &&
	          node.dataset.launchExecutionAuthWorkflowScopeInstallBlocked === "false" &&
	          Number(node.dataset.launchExecutionAuthScopeCount || "0") >= 4 &&
	          node.dataset.launchExecutionAuthMissingScopes === "none" &&
	          node.dataset.launchExecutionAuthApprovalStatus === "not_required" &&
	          node.dataset.launchExecutionPostAuthCheckpointStatus === "pass" &&
	          node.dataset.launchExecutionCurrentActionStatus === "pass" &&
	          node.dataset.launchExecutionCurrentActionAcceptancePassCount === "5" &&
	          node.dataset.launchExecutionCurrentActionAcceptancePendingCount === "0" &&
	          node.dataset.launchExecutionTransitionCurrentStage === "install_workflows" &&
	          node.dataset.launchExecutionTransitionNextStage === "capture_launch_proof" &&
	          node.dataset.launchExecutionTransitionReady === "true" &&
	          node.dataset.launchExecutionTransitionPendingCount === "0" &&
	          node.dataset.launchExecutionTransitionPassCount === "5" &&
	          node.dataset.launchExecutionTransitionWithheldCount === "2" &&
	          node.dataset.launchExecutionBlockerResolutionStatus === "pass" &&
	          node.dataset.launchExecutionBlockerResolutionActionRequiredCount === "0" &&
	          node.dataset.launchExecutionBlockerResolutionDeferredCount === "0" &&
	          node.dataset.launchPostInstallEvidenceIntakeStatus === "proof_complete" &&
	          node.dataset.launchPostInstallEvidenceIntakeProofComplete === "true" &&
	          node.dataset.launchPostInstallEvidenceIntakeCompletedCount === "6" &&
	          node.dataset.launchPostInstallQuickProofCompletedMappedFieldCount === "4" &&
	          node.dataset.remoteWorkflowFileLedgerStatus === "remote_files_ready" &&
	          node.dataset.remoteWorkflowFileLedgerReadyCount === "2" &&
	          node.dataset.remoteWorkflowFileLedgerMissingCount === "0" &&
	          node.dataset.launchProofLedgerStatus === "proof_ready" &&
	          node.dataset.launchProofLedgerReadyCount === "6" &&
	          node.dataset.launchProofLedgerPendingCount === "0";
	      }
		      const actionRequiredCount = Number(node.dataset.launchExecutionBlockerResolutionActionRequiredCount || "0");
		      const currentActionPassCount = Number(node.dataset.launchExecutionCurrentActionAcceptancePassCount || "0");
		      const currentActionPendingCount = Number(node.dataset.launchExecutionCurrentActionAcceptancePendingCount || "0");
		      const postInstallCompletedCount = Number(node.dataset.launchPostInstallEvidenceIntakeCompletedCount || "0");
		      const remoteReadyCount = Number(node.dataset.remoteWorkflowFileLedgerReadyCount || "0");
		      const remoteMissingCount = Number(node.dataset.remoteWorkflowFileLedgerMissingCount || "0");
		      const remoteMismatchCount = Number(node.dataset.remoteWorkflowFileLedgerMismatchCount || "0");
		      const proofReadyCount = Number(node.dataset.launchProofLedgerReadyCount || "0");
		      const proofPendingCount = Number(node.dataset.launchProofLedgerPendingCount || "0");
		      return node.dataset.launchExecutionReadyToDispatch === "false" &&
		        ["true", "false"].includes(node.dataset.launchExecutionProofReady || "") &&
		        ["action_required", "pass"].includes(node.dataset.launchExecutionAuthPreflightStatus || "") &&
		        ["true", "false"].includes(node.dataset.launchExecutionAuthWorkflowScopeAvailable || "") &&
		        ["true", "false"].includes(node.dataset.launchExecutionAuthWorkflowScopeInstallBlocked || "") &&
		        ["workflow", "none"].includes(node.dataset.launchExecutionAuthMissingScopes || "") &&
		        ["approval_required", "not_required"].includes(node.dataset.launchExecutionAuthApprovalStatus || "") &&
		        ["action_required", "pass"].includes(node.dataset.launchExecutionPostAuthCheckpointStatus || "") &&
		        node.dataset.launchExecutionCurrentActionStatus === "action_required" &&
		        currentActionPassCount >= 2 &&
		        currentActionPassCount <= 4 &&
		        currentActionPendingCount >= 1 &&
		        currentActionPendingCount <= 3 &&
		        node.dataset.launchExecutionTransitionCurrentStage === "install_workflows" &&
		        node.dataset.launchExecutionTransitionNextStage === "verify_visibility" &&
		        node.dataset.launchExecutionTransitionReady === "false" &&
		        node.dataset.launchExecutionBlockerResolutionStatus === "action_required" &&
		        ["operator_auth_path", "remote_workflow_file_parity"].includes(node.dataset.launchExecutionBlockerResolutionActive || "") &&
		        actionRequiredCount >= 1 &&
		        actionRequiredCount <= 3 &&
		        node.dataset.launchExecutionBlockerResolutionDeferredCount === "1" &&
		        node.dataset.launchPostInstallEvidenceIntakeStatus === "collect_post_install_proof" &&
		        node.dataset.launchPostInstallEvidenceIntakeProofComplete === "false" &&
		        postInstallCompletedCount >= 0 &&
		        postInstallCompletedCount <= 5 &&
		        node.dataset.remoteWorkflowFileLedgerStatus === "remote_file_install_required" &&
		        remoteReadyCount >= 0 &&
		        remoteReadyCount < 2 &&
		        remoteMissingCount >= 0 &&
		        remoteMismatchCount >= 0 &&
		        node.dataset.launchProofLedgerStatus === "proof_blocked_until_dispatch" &&
		        proofReadyCount >= 0 &&
		        proofReadyCount < 6 &&
		        proofPendingCount >= 1 &&
		        proofPendingCount <= 6;
	    };
    await waitFor(() => {
      const scopedPanel = document.querySelector("[data-system-publish-readiness]");
      return launchPacketReady(scopedPanel?.querySelector("[data-system-launch-execution-packet]"));
    }, "launch execution packet state was not surfaced", 30000);
	    panel = qs("[data-system-publish-readiness]");
		    const launchPacket = qs("[data-system-launch-execution-packet]", panel);
		    assert(launchPacketReady(launchPacket), "launch execution packet state was not surfaced");
		    const launchPacketExternalReady = launchPacket.dataset.launchExecutionExternalReady === "true";
		    const launchAuthWorkflowScopeAvailable = launchPacket.dataset.launchExecutionAuthWorkflowScopeAvailable;
		    const launchAuthWorkflowScopeInstallBlocked = launchPacket.dataset.launchExecutionAuthWorkflowScopeInstallBlocked;
		    const launchAuthMissingScopes = launchPacket.dataset.launchExecutionAuthMissingScopes;
		    const launchAuthApprovalStatus = launchPacket.dataset.launchExecutionAuthApprovalStatus;
		    const launchActiveBlocker = launchPacket.dataset.launchExecutionBlockerResolutionActive;
		    const launchBlockerPassCount = Number(launchPacket.dataset.launchExecutionCurrentActionAcceptancePassCount || "0");
		    const launchBlockerPendingCount = Number(launchPacket.dataset.launchExecutionCurrentActionAcceptancePendingCount || "0");
		    const launchPostInstallCompletedCount = Number(launchPacket.dataset.launchPostInstallEvidenceIntakeCompletedCount || "0");
		    const launchPostInstallQuickMappedCompletedCount = Number(launchPacket.dataset.launchPostInstallQuickProofCompletedMappedFieldCount || "0");
		    const launchRemoteReadyCount = Number(launchPacket.dataset.remoteWorkflowFileLedgerReadyCount || "0");
		    const launchRemoteMissingCount = Number(launchPacket.dataset.remoteWorkflowFileLedgerMissingCount || "0");
		    const launchRemoteMismatchCount = Number(launchPacket.dataset.remoteWorkflowFileLedgerMismatchCount || "0");
		    const launchProofReadyCount = Number(launchPacket.dataset.launchProofLedgerReadyCount || "0");
		    const launchProofPendingCount = Number(launchPacket.dataset.launchProofLedgerPendingCount || "0");
		    const launchAcceptanceSummary = "Acceptance checklist: " + launchBlockerPassCount + "/5 pass; pending=" + launchBlockerPendingCount;
		    if (launchPacketExternalReady) {
	      assert(qs("[data-launch-execution-state-label]", launchPacket).textContent.includes("launch ready"), "launch execution packet did not label ready state");
	    const launchOperatorOnePage = qs("[data-launch-operator-one-page]", launchPacket);
	    const launchOperatorOnePageText = qs("[data-launch-operator-one-page-text]", launchOperatorOnePage).textContent;
	    const launchAuthWorkflowScopeAvailable = launchPacket.dataset.launchExecutionAuthWorkflowScopeAvailable;
	    const launchAuthWorkflowScopeInstallBlocked = launchPacket.dataset.launchExecutionAuthWorkflowScopeInstallBlocked;
	    const launchAuthMissingScopes = launchPacket.dataset.launchExecutionAuthMissingScopes;
	    const launchAuthApprovalStatus = launchPacket.dataset.launchExecutionAuthApprovalStatus;
	    const launchActiveBlocker = launchPacket.dataset.launchExecutionBlockerResolutionActive;
	    const launchBlockerPassCount = Number(launchPacket.dataset.launchExecutionCurrentActionAcceptancePassCount || "0");
	    const launchBlockerPendingCount = Number(launchPacket.dataset.launchExecutionCurrentActionAcceptancePendingCount || "0");
	    const launchPostInstallCompletedCount = Number(launchPacket.dataset.launchPostInstallEvidenceIntakeCompletedCount || "0");
	    const launchPostInstallQuickMappedCompletedCount = Number(launchPacket.dataset.launchPostInstallQuickProofCompletedMappedFieldCount || "0");
	    const launchRemoteReadyCount = Number(launchPacket.dataset.remoteWorkflowFileLedgerReadyCount || "0");
	    const launchRemoteMissingCount = Number(launchPacket.dataset.remoteWorkflowFileLedgerMissingCount || "0");
	    const launchRemoteMismatchCount = Number(launchPacket.dataset.remoteWorkflowFileLedgerMismatchCount || "0");
	    const launchProofReadyCount = Number(launchPacket.dataset.launchProofLedgerReadyCount || "0");
	    const launchProofPendingCount = Number(launchPacket.dataset.launchProofLedgerPendingCount || "0");
	    const launchAcceptanceSummary = "Acceptance checklist: " + launchBlockerPassCount + "/5 pass; pending=" + launchBlockerPendingCount;
	    const launchOperatorSuccessSignals = [
	        "workflowScopeAvailable=true or GitHub UI installAction rows applied on the default branch",
	        "remoteWorkflowFilesReady=true",
	        "remoteWorkflowVisibilityReady=true",
	        "dispatchReady=true",
	        "driftDispatchReady=true",
	        "allDispatchReady=true",
	        "all six post-install evidence fields are filled",
	        "safeToDispatch=true before gh workflow run",
	      ];
	      assert(launchOperatorOnePage.dataset.launchOperatorOnePageSource === "generated_from_launch_execution_packet" && launchOperatorOnePage.dataset.launchOperatorOnePageReady === "true" && launchOperatorOnePage.dataset.launchOperatorOnePageStatus === "pass" && launchOperatorOnePage.dataset.launchOperatorOnePageStage === "install_workflows" && launchOperatorOnePage.dataset.launchOperatorOnePageSectionCount === "8" && Number(launchOperatorOnePage.dataset.launchOperatorOnePageCommandCount || "0") >= 12 && launchOperatorOnePage.dataset.launchOperatorOnePageProofCommandCount === "4" && Number(launchOperatorOnePage.dataset.launchOperatorOnePageSuccessSignalCount || "0") >= 8 && Number(launchOperatorOnePage.dataset.launchOperatorOnePageForbiddenCommandCount || "0") >= 3, "launch operator one-page ready handoff dataset was incomplete");
	      assert(launchOperatorOnePageText.includes("JooPark Launch Operator One-Page Handoff") && launchOperatorOnePageText.includes("Status: pass") && launchOperatorOnePageText.includes("Do first:") && launchOperatorOnePageText.includes("plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects") && launchOperatorSuccessSignals.every((signal) => launchOperatorOnePageText.includes(signal)) && launchOperatorOnePageText.includes("Post-install quick proof") && launchOperatorOnePageText.includes("External baseline:"), "launch operator one-page ready handoff was not copy-ready");
	      const launchOperatorOnePageCopy = qs("[data-launch-operator-one-page-copy]", launchOperatorOnePage);
	      window.__smokeClipboardText = "";
	      click("[data-launch-operator-one-page-copy]", launchOperatorOnePage);
	      await waitFor(() => launchOperatorOnePage.dataset.launchOperatorOnePageCopied === "true" && qs("[data-launch-operator-one-page-copy-status]", launchOperatorOnePage).textContent.includes("복사"), "launch operator one-page copy did not report success");
	      await waitFor(() => launchOperatorOnePageCopy.dataset.launchOperatorOnePageCopied === "true" && window.__smokeClipboardText.includes("JooPark Launch Operator One-Page Handoff") && window.__smokeClipboardText.includes("Status: pass") && launchOperatorSuccessSignals.every((signal) => window.__smokeClipboardText.includes(signal)), "launch operator ready one-page copy text did not reach clipboard");
	      launchOperatorOnePageCopyOk = true;
	      const launchAuthPreflight = qs("[data-launch-execution-auth-preflight]", launchPacket);
	      assert(launchAuthPreflight.textContent.includes("Auth preflight") && launchAuthPreflight.textContent.includes("workflowScopeAvailable") && launchAuthPreflight.textContent.includes("true") && launchAuthPreflight.textContent.includes("workflowScopeInstallBlocked") && launchAuthPreflight.textContent.includes("false") && launchAuthPreflight.textContent.includes("gist, read:org, repo, workflow") && launchAuthPreflight.textContent.includes("missingScopes") && launchAuthPreflight.textContent.includes("none") && launchAuthPreflight.textContent.includes("not_required") && launchAuthPreflight.textContent.includes("gh auth refresh -h github.com -s workflow"), "launch execution ready auth preflight was not surfaced");
	      const launchPostAuthCheckpoint = qs("[data-launch-execution-post-auth-checkpoint]", launchPacket);
	      assert(launchPostAuthCheckpoint.textContent.includes("Post-auth checkpoint") && launchPostAuthCheckpoint.textContent.includes("pass") && launchPostAuthCheckpoint.textContent.includes("gh auth status -h github.com") && launchPostAuthCheckpoint.textContent.includes("workflowScopeAvailable=true") && launchPostAuthCheckpoint.textContent.includes("workflowScopeInstallBlocked=false") && launchPostAuthCheckpoint.textContent.includes("verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown") && launchPostAuthCheckpoint.textContent.includes("safeToDispatch=true"), "launch execution ready post-auth checkpoint was not surfaced");
	      const launchTransitionPreview = qs("[data-launch-execution-transition-preview]", launchPacket);
	      const launchTransitionSteps = Array.from(launchTransitionPreview.querySelectorAll("[data-launch-transition-step]"));
	      assert(launchTransitionPreview.dataset.launchTransitionSource === "generated_from_launch_execution_packet" && launchTransitionPreview.dataset.launchTransitionCurrentStage === "install_workflows" && launchTransitionPreview.dataset.launchTransitionNextStage === "capture_launch_proof" && launchTransitionPreview.dataset.launchTransitionReady === "true" && launchTransitionPreview.dataset.launchTransitionPendingCount === "0" && launchTransitionPreview.dataset.launchTransitionWithheldCount === "2", "launch execution ready transition preview dataset was incomplete");
	      assert(launchTransitionPreview.textContent.includes("Stage transition preview") && launchTransitionPreview.textContent.includes("Install workflows on the default branch -> Capture launch proof") && launchTransitionPreview.textContent.includes("ready after guard") && launchTransitionPreview.textContent.includes("safeToDispatch=true") && qs("[data-launch-transition-gate-command]", launchTransitionPreview).textContent.includes("verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown"), "launch execution ready transition preview did not render");
	      assert(launchTransitionSteps.length === 3 && launchTransitionSteps.some((step) => step.dataset.launchTransitionStepKey === "complete-current-stage" && step.dataset.launchTransitionStepStatus === "pass") && launchTransitionSteps.some((step) => step.dataset.launchTransitionStepKey === "unlock-next-stage" && step.dataset.launchTransitionStepStatus === "ready_after_guard") && launchTransitionSteps.some((step) => step.dataset.launchTransitionStepKey === "keep-dispatch-withheld" && step.dataset.launchTransitionStepStatus === "ready"), "launch execution ready transition steps were incomplete");
	      const blockerResolution = qs("[data-launch-blocker-resolution-checklist]", launchPacket);
	      const blockerResolutionItems = Array.from(blockerResolution.querySelectorAll("[data-launch-blocker-resolution-item]"));
	      assert(blockerResolution.dataset.launchBlockerResolutionSource === "generated_from_launch_execution_packet" && blockerResolution.dataset.launchBlockerResolutionStatus === "pass" && blockerResolution.dataset.launchBlockerResolutionItemCount === "6" && blockerResolution.dataset.launchBlockerResolutionPassCount === "6" && blockerResolution.dataset.launchBlockerResolutionActionRequiredCount === "0" && blockerResolution.dataset.launchBlockerResolutionDeferredCount === "0" && blockerResolution.dataset.launchBlockerResolutionProofCommandCount === "6", "launch ready blocker resolution checklist dataset was incomplete");
	      assert(blockerResolutionItems.length === 6 && blockerResolutionItems.every((item) => item.dataset.launchBlockerResolutionStatus === "pass") && blockerResolutionItems.some((item) => item.dataset.launchBlockerResolutionKey === "remote_workflow_file_parity" && item.textContent.includes("remoteWorkflowFilesReady=true")) && blockerResolutionItems.some((item) => item.dataset.launchBlockerResolutionKey === "launch_proof_capture" && item.textContent.includes("postPublishEvidenceReady=true")), "launch ready blocker resolution checklist rows were incomplete");
	      assert(launchPacket.dataset.launchExecutionInstallMatrixSource === "generated_from_launch_execution_packet" && launchPacket.dataset.launchExecutionInstallMatrixPathCount === "2" && launchPacket.dataset.launchExecutionInstallMatrixSignalCount === "6" && launchPacket.dataset.launchExecutionInstallMatrixVerificationCommandCount === "4" && launchPacket.dataset.launchExecutionInstallMatrixReadyToDispatch === "true", "launch execution ready install matrix root dataset was incomplete");
	      const launchInstallMatrix = qs("[data-launch-install-verification-matrix]", launchPacket);
	      const launchInstallMatrixRows = Array.from(launchInstallMatrix.querySelectorAll("[data-launch-install-verification-row]"));
	      const launchInstallMatrixSignals = Array.from(launchInstallMatrix.querySelectorAll("[data-launch-install-verification-signal]"));
	      assert(launchInstallMatrix.dataset.launchInstallVerificationSource === "generated_from_launch_execution_packet" && launchInstallMatrix.dataset.launchInstallVerificationStatus === "ready_to_dispatch" && launchInstallMatrix.dataset.launchInstallVerificationPathCount === "2" && launchInstallMatrix.dataset.launchInstallVerificationSignalCount === "6" && launchInstallMatrix.dataset.launchInstallVerificationCommandCount === "4" && launchInstallMatrix.dataset.launchInstallVerificationNextStage === "verify_visibility" && launchInstallMatrix.dataset.launchInstallVerificationReadyToDispatch === "true", "launch ready install verification matrix dataset was incomplete");
	      assert(launchInstallMatrixRows.length === 2 && launchInstallMatrixRows.every((row) => row.dataset.launchInstallVerificationRowStatus === "ready_to_install") && launchInstallMatrixSignals.length === 5 && launchInstallMatrixSignals.every((signal) => signal.dataset.launchInstallVerificationSignalStatus === "pass"), "launch ready install verification matrix rows or signals were incomplete");
	      const launchPostInstallIntake = qs("[data-launch-post-install-evidence-intake]", launchPacket);
	      const launchPostInstallIntakeFields = Array.from(launchPostInstallIntake.querySelectorAll("[data-launch-post-install-evidence-intake-field]"));
	      const launchPostInstallQuickProofMap = qs("[data-launch-post-install-quick-proof-field-map]", launchPostInstallIntake);
	      const launchPostInstallQuickProofMapItems = Array.from(launchPostInstallQuickProofMap.querySelectorAll("[data-launch-post-install-quick-proof-field-map-item]"));
	      assert(launchPostInstallIntake.dataset.launchPostInstallEvidenceIntakeSource === "generated_from_launch_execution_packet" && launchPostInstallIntake.dataset.launchPostInstallEvidenceIntakeStatus === "proof_complete" && launchPostInstallIntake.dataset.launchPostInstallEvidenceIntakeProofComplete === "true" && launchPostInstallIntake.dataset.launchPostInstallEvidenceIntakeCompletedCount === "6" && launchPostInstallIntake.dataset.launchPostInstallQuickProofCompletedMappedFieldCount === "4", "launch ready post-install evidence intake dataset was incomplete");
	      assert(launchPostInstallIntake.textContent.includes("Post-install evidence intake") && launchPostInstallIntake.textContent.includes("proofComplete=true") && launchPostInstallIntake.textContent.includes("6/6 proof fields complete") && launchPostInstallIntake.textContent.includes("remoteWorkflowFilesReady=true") && launchPostInstallIntake.textContent.includes("remoteWorkflowVisibilityReady=true") && launchPostInstallIntake.textContent.includes("safeToDispatch=true before gh workflow run"), "launch ready post-install evidence intake did not render");
	      assert(launchPostInstallIntakeFields.length === 6 && launchPostInstallIntakeFields.every((item) => item.dataset.launchPostInstallEvidenceIntakeFieldCompleted === "true") && launchPostInstallIntakeFields.some((item) => item.dataset.launchPostInstallEvidenceIntakeFieldKey === "handoff_verifier_proof" && item.textContent.includes("safeToDispatch=true")) && launchPostInstallQuickProofMapItems.length === 4 && launchPostInstallQuickProofMapItems.every((item) => item.dataset.launchPostInstallQuickProofFieldMapCompleted === "true"), "launch ready post-install evidence fields were incomplete");
	      const remoteWorkflowFileLedger = qs("[data-remote-workflow-file-acceptance-ledger]", launchPacket);
	      const remoteWorkflowFileLedgerItems = Array.from(remoteWorkflowFileLedger.querySelectorAll("[data-remote-workflow-file-ledger-item]"));
	      assert(remoteWorkflowFileLedger.dataset.remoteWorkflowFileLedgerSource === "generated_from_remote_workflow_file_check" && remoteWorkflowFileLedger.dataset.remoteWorkflowFileLedgerStatus === "remote_files_ready" && remoteWorkflowFileLedger.dataset.remoteWorkflowFileLedgerFileCount === "2" && remoteWorkflowFileLedger.dataset.remoteWorkflowFileLedgerReadyCount === "2" && remoteWorkflowFileLedger.dataset.remoteWorkflowFileLedgerMissingCount === "0" && remoteWorkflowFileLedger.dataset.remoteWorkflowFileLedgerMismatchCount === "0" && remoteWorkflowFileLedger.dataset.remoteWorkflowFileLedgerVerifyCommand.includes("check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write"), "launch ready remote workflow file acceptance ledger dataset was incomplete");
	      assert(remoteWorkflowFileLedger.textContent.includes("Remote workflow file acceptance ledger") && remoteWorkflowFileLedger.textContent.includes("2/2 files ready") && remoteWorkflowFileLedger.textContent.includes("remote_files_ready") && remoteWorkflowFileLedger.textContent.includes("remoteExists=true") && remoteWorkflowFileLedger.textContent.includes("remoteMatchesTemplate=true"), "launch ready remote workflow file acceptance ledger did not render");
	      assert(remoteWorkflowFileLedgerItems.length === 2 && remoteWorkflowFileLedgerItems.every((item) => item.dataset.remoteWorkflowFileStatus === "ready" && item.dataset.remoteWorkflowFileRemoteExists === "true" && item.dataset.remoteWorkflowFileRemoteMatches === "true"), "launch ready remote workflow file acceptance ledger rows were incomplete");
	      const launchProofLedger = qs("[data-launch-proof-acceptance-ledger]", launchPacket);
	      const launchProofLedgerItems = Array.from(launchProofLedger.querySelectorAll("[data-launch-proof-acceptance-item]"));
	      assert(launchProofLedger.dataset.launchProofLedgerSource === "generated_from_launch_execution_packet" && launchProofLedger.dataset.launchProofLedgerStatus === "proof_ready" && launchProofLedger.dataset.launchProofLedgerRequiredCount === "6" && launchProofLedger.dataset.launchProofLedgerReadyCount === "6" && launchProofLedger.dataset.launchProofLedgerPendingCount === "0" && launchProofLedger.dataset.launchProofLedgerCurrentGate === "capture_launch_proof" && launchProofLedger.dataset.launchProofLedgerCaptureCommand.includes("capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --write"), "launch ready proof acceptance ledger dataset was incomplete");
	      assert(launchProofLedger.textContent.includes("Launch proof acceptance ledger") && launchProofLedger.textContent.includes("6/6 proofs ready") && launchProofLedger.textContent.includes("readyForExternalClaim") && launchProofLedger.textContent.includes("postPublishEvidenceReady=true") && launchProofLedger.textContent.includes("capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --write"), "launch ready proof acceptance ledger did not render");
	      assert(launchProofLedgerItems.length === 6 && launchProofLedgerItems.every((item) => item.dataset.launchProofAcceptanceStatus === "ready") && launchProofLedgerItems.some((item) => item.dataset.launchProofAcceptanceKey === "public_claim_guard" && item.textContent.includes("readyForExternalClaim=true")), "launch ready proof acceptance ledger rows were incomplete");
	      const launchCurrentAction = qs("[data-launch-execution-current-action]", launchPacket);
	      const launchCurrentActionText = qs("[data-launch-execution-current-action-text]", launchCurrentAction).textContent;
	      const launchAcceptanceItems = Array.from(launchCurrentAction.querySelectorAll("[data-launch-execution-acceptance-item]"));
	      assert(launchAcceptanceItems.length === 5 && launchAcceptanceItems.every((item) => item.dataset.launchExecutionAcceptanceStatus === "pass") && launchAcceptanceItems.some((item) => item.dataset.launchExecutionAcceptanceKey === "remote_workflow_file_parity" && item.textContent.includes("remoteWorkflowFilesReady=true")) && launchAcceptanceItems.some((item) => item.dataset.launchExecutionAcceptanceKey === "workflow_visibility" && item.textContent.includes("remoteWorkflowVisibilityReady=true")), "launch ready execution acceptance checklist was not surfaced");
	      assert(launchCurrentActionText.includes("JooPark Launch Current Action Packet") && launchCurrentActionText.includes("Current stage: Install workflows on the default branch [pass]") && launchCurrentActionText.includes("workflowScopeAvailable: true") && launchCurrentActionText.includes("workflowScopeInstallBlocked: false") && launchCurrentActionText.includes("missingScopes: none") && launchCurrentActionText.includes("Acceptance checklist: 5/5 pass; pending=0") && launchCurrentActionText.includes("Remote workflow file parity: pass"), "launch ready current action packet was not surfaced");
	      const launchCurrentActionCopy = qs("[data-launch-execution-current-action-copy]", launchCurrentAction);
	      window.__smokeClipboardText = "";
	      click("[data-launch-execution-current-action-copy]", launchCurrentAction);
	      await waitFor(() => launchCurrentAction.dataset.launchExecutionCurrentActionCopied === "true" && qs("[data-launch-execution-current-action-copy-status]", launchCurrentAction).textContent.includes("복사"), "launch current action packet copy did not report success");
	      await waitFor(() => launchCurrentActionCopy.dataset.launchExecutionCurrentActionCopied === "true" && window.__smokeClipboardText.includes("JooPark Launch Current Action Packet") && window.__smokeClipboardText.includes("Current stage: Install workflows on the default branch [pass]") && window.__smokeClipboardText.includes("workflowScopeAvailable: true") && window.__smokeClipboardText.includes("Acceptance checklist: 5/5 pass; pending=0"), "launch ready current action packet copy text did not reach clipboard");
	      launchExecutionCurrentActionCopyOk = true;
	      const launchPacketCopyCard = qs("[data-launch-execution-packet-copy-card]", launchPacket);
	      const launchPacketText = qs("[data-launch-execution-packet-text]", launchPacketCopyCard).textContent;
	      assert(launchPacketText.includes("JooPark Launch Execution Packet") && launchPacketText.includes("Status: ready") && launchPacketText.includes("workflowScopeAvailable: true") && launchPacketText.includes("Acceptance checklist: 5/5 pass; pending=0") && launchPacketText.includes("Stage transition preview:") && launchPacketText.includes("next: capture_launch_proof") && launchPacketText.includes("Blocker resolution checklist:") && launchPacketText.includes("items: 6/6 pass; action_required=0; deferred=0") && launchPacketText.includes("proofComplete: true; fields=6/6 complete; coverage=1") && launchPacketText.includes("Remote workflow file acceptance ledger:") && launchPacketText.includes("files: 2/2 ready; missing=0; mismatch=0") && launchPacketText.includes("Launch proof acceptance ledger:") && launchPacketText.includes("proof readiness: 6/6 ready; pending=0") && launchPacketText.includes("proof public_claim_guard: ready"), "launch ready execution packet was not copy-ready");
	      window.__smokeClipboardText = "";
	      click("[data-launch-execution-packet-copy]", launchPacket);
	      await waitFor(() => launchPacketCopyCard.dataset.launchExecutionPacketCopied === "true" && qs("[data-launch-execution-packet-copy-status]", launchPacketCopyCard).textContent.includes("복사"), "launch execution packet copy did not report success");
	      await waitFor(() => window.__smokeClipboardText.includes("JooPark Launch Execution Packet") && window.__smokeClipboardText.includes("Status: ready") && window.__smokeClipboardText.includes("workflowScopeAvailable: true") && window.__smokeClipboardText.includes("proofComplete: true; fields=6/6 complete; coverage=1") && window.__smokeClipboardText.includes("files: 2/2 ready; missing=0; mismatch=0") && window.__smokeClipboardText.includes("proof readiness: 6/6 ready; pending=0"), "launch ready execution packet copy text did not reach clipboard");
	      launchExecutionPacketOk = true;
	    } else {
	    assert(qs("[data-launch-execution-state-label]", launchPacket).textContent.includes("execution blocked"), "launch execution packet did not label blocked state");
    const launchOperatorOnePage = qs("[data-launch-operator-one-page]", launchPacket);
    const launchOperatorOnePageText = qs("[data-launch-operator-one-page-text]", launchOperatorOnePage).textContent;
    const launchOperatorSuccessSignals = [
      "workflowScopeAvailable=true or GitHub UI installAction rows applied on the default branch",
      "remoteWorkflowFilesReady=true",
      "remoteWorkflowVisibilityReady=true",
      "dispatchReady=true",
      "driftDispatchReady=true",
      "allDispatchReady=true",
      "all six post-install evidence fields are filled",
      "safeToDispatch=true before gh workflow run",
    ];
	    assert(launchOperatorOnePage.dataset.launchOperatorOnePageSource === "generated_from_launch_execution_packet" && launchOperatorOnePage.dataset.launchOperatorOnePageReady === "true" && launchOperatorOnePage.dataset.launchOperatorOnePageStatus === "action_required" && launchOperatorOnePage.dataset.launchOperatorOnePageStage === "install_workflows" && launchOperatorOnePage.dataset.launchOperatorOnePageActive === launchActiveBlocker && launchOperatorOnePage.dataset.launchOperatorOnePageSectionCount === "8" && Number(launchOperatorOnePage.dataset.launchOperatorOnePageCommandCount || "0") >= 10 && launchOperatorOnePage.dataset.launchOperatorOnePageProofCommandCount === "4" && Number(launchOperatorOnePage.dataset.launchOperatorOnePageSuccessSignalCount || "0") >= 8 && Number(launchOperatorOnePage.dataset.launchOperatorOnePageForbiddenCommandCount || "0") >= 3, "launch operator one-page handoff dataset was incomplete");
	    assert(launchOperatorOnePage.textContent.includes("Operator one-page handoff") && launchOperatorOnePage.textContent.includes(launchActiveBlocker) && launchOperatorOnePage.textContent.includes("8") && launchOperatorOnePageText.includes("JooPark Launch Operator One-Page Handoff") && launchOperatorOnePageText.includes("Goal for this pass:") && launchOperatorOnePageText.includes("Install workflows on the default branch") && launchOperatorOnePageText.includes("Active blocker: " + launchActiveBlocker) && launchOperatorOnePageText.includes("Do first:") && launchOperatorOnePageText.includes("plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects") && launchOperatorOnePageText.includes("If CLI workflow scope is still blocked, use GitHub UI fallback:") && launchOperatorOnePageText.includes("pbcopy < 'docs/github-pages-workflow.yml'") && launchOperatorOnePageText.includes("Prove after install:") && launchOperatorOnePageText.includes("check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write") && launchOperatorOnePageText.includes("verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown") && launchOperatorOnePageText.includes("Success signals:") && launchOperatorSuccessSignals.every((signal) => launchOperatorOnePageText.includes(signal)) && launchOperatorOnePageText.includes("Evidence fields to fill:") && launchOperatorOnePageText.includes("Handoff verifier proof") && launchOperatorOnePageText.includes("Do not run or claim yet:") && launchOperatorOnePageText.includes("gh workflow run --repo biojuho/BIOJUHO-Projects joopark-pages.yml -f ref=codex/joopark-workspace-release") && launchOperatorOnePageText.includes("Do not claim readyForExternalClaim=true") && launchOperatorOnePageText.includes("External baseline:") && launchOperatorOnePageText.includes("workflow_dispatch must exist on the default branch"), "launch operator one-page handoff was not copy-ready");
    const launchOperatorOnePageCopy = qs("[data-launch-operator-one-page-copy]", launchOperatorOnePage);
    window.__smokeClipboardText = "";
    click("[data-launch-operator-one-page-copy]", launchOperatorOnePage);
    await waitFor(() => launchOperatorOnePage.dataset.launchOperatorOnePageCopied === "true" && qs("[data-launch-operator-one-page-copy-status]", launchOperatorOnePage).textContent.includes("복사"), "launch operator one-page copy did not report success");
    await waitFor(() => launchOperatorOnePageCopy.dataset.launchOperatorOnePageCopied === "true" && window.__smokeClipboardText.includes("JooPark Launch Operator One-Page Handoff") && window.__smokeClipboardText.includes("Do first:") && window.__smokeClipboardText.includes("If CLI workflow scope is still blocked, use GitHub UI fallback:") && window.__smokeClipboardText.includes("Prove after install:") && window.__smokeClipboardText.includes("Success signals:") && launchOperatorSuccessSignals.every((signal) => window.__smokeClipboardText.includes(signal)) && window.__smokeClipboardText.includes("Do not run or claim yet:") && window.__smokeClipboardText.includes("Do not claim readyForExternalClaim=true"), "launch operator one-page copy text did not reach clipboard");
	    launchOperatorOnePageCopyOk = true;
	    const launchAuthPreflight = qs("[data-launch-execution-auth-preflight]", launchPacket);
	    assert(launchAuthPreflight.textContent.includes("Auth preflight") && launchAuthPreflight.textContent.includes("workflowScopeAvailable") && launchAuthPreflight.textContent.includes(launchAuthWorkflowScopeAvailable) && launchAuthPreflight.textContent.includes("workflowScopeInstallBlocked") && launchAuthPreflight.textContent.includes(launchAuthWorkflowScopeInstallBlocked) && launchAuthPreflight.textContent.includes("gist, read:org, repo") && (launchAuthWorkflowScopeAvailable === "true" ? launchAuthPreflight.textContent.includes("workflow") : true) && launchAuthPreflight.textContent.includes("missingScopes") && launchAuthPreflight.textContent.includes(launchAuthMissingScopes) && launchAuthPreflight.textContent.includes(launchAuthApprovalStatus) && launchAuthPreflight.textContent.includes("https://github.com/login/device") && launchAuthPreflight.textContent.includes("Do not store, log, or paste the one-time device code") && launchAuthPreflight.textContent.includes("gh auth refresh -h github.com -s workflow"), "launch execution auth preflight was not surfaced");
    const launchPostAuthCheckpoint = qs("[data-launch-execution-post-auth-checkpoint]", launchPacket);
    assert(launchPostAuthCheckpoint.textContent.includes("Post-auth checkpoint") && launchPostAuthCheckpoint.textContent.includes("gh auth status -h github.com") && launchPostAuthCheckpoint.textContent.includes("Token scopes include workflow") && launchPostAuthCheckpoint.textContent.includes("workflowScopeAvailable=true") && launchPostAuthCheckpoint.textContent.includes("workflowScopeInstallBlocked=false") && launchPostAuthCheckpoint.textContent.includes("verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown") && launchPostAuthCheckpoint.textContent.includes("safeToDispatch=true") && launchPostAuthCheckpoint.textContent.includes("Do not run gh workflow run"), "launch execution post-auth checkpoint was not surfaced");
    const launchPostAuthRecheckSteps = Array.from(launchPostAuthCheckpoint.querySelectorAll("[data-launch-post-auth-recheck-step]"));
    const launchPostAuthSourceArtifacts = Array.from(launchPostAuthCheckpoint.querySelectorAll("[data-launch-post-auth-source-artifact]"));
    const launchPostAuthRecheckKeys = launchPostAuthRecheckSteps.map((step) => step.dataset.launchPostAuthRecheckKey);
    assert(launchPacket.dataset.launchExecutionPostAuthCheckpointRecheckCount === "5" && launchPacket.dataset.launchExecutionPostAuthCheckpointSourceArtifactCount === "4" && launchPacket.dataset.launchExecutionPostAuthCheckpointDispatchApproval === "false" && launchPacket.dataset.launchExecutionPostAuthCheckpointVerificationOnly === "true", "launch execution post-auth checkpoint root dataset was incomplete");
    assert(launchPostAuthRecheckSteps.length === 5 && ["confirm_scope", "install_workflows", "verify_remote_parity", "verify_actions_visibility", "verify_handoff_guard"].every((key) => launchPostAuthRecheckKeys.includes(key)) && launchPostAuthRecheckSteps.some((step) => step.dataset.launchPostAuthRecheckCommand.includes("gh auth status -h github.com")) && launchPostAuthRecheckSteps.some((step) => step.dataset.launchPostAuthRecheckCommand.includes("verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown")) && launchPostAuthRecheckSteps.every((step) => step.dataset.launchPostAuthRecheckExpected && step.dataset.launchPostAuthRecheckSource && step.dataset.launchPostAuthRecheckStop), "launch execution post-auth recheck sequence was incomplete");
    assert(launchPostAuthSourceArtifacts.length === 4 && launchPostAuthSourceArtifacts.some((item) => item.dataset.launchPostAuthSourceArtifact === "gh auth status -h github.com") && launchPostAuthSourceArtifacts.some((item) => item.dataset.launchPostAuthSourceArtifact === "data/remote-workflow-file-check.json") && launchPostAuthSourceArtifacts.some((item) => item.dataset.launchPostAuthSourceArtifact === "data/publish-dispatch-plan.json") && launchPostAuthSourceArtifacts.some((item) => item.dataset.launchPostAuthSourceArtifact === "data/launch-handoff-verification.json"), "launch execution post-auth source artifacts were incomplete");
    const launchTransitionPreview = qs("[data-launch-execution-transition-preview]", launchPacket);
    const launchTransitionSteps = Array.from(launchTransitionPreview.querySelectorAll("[data-launch-transition-step]"));
	    assert(launchTransitionPreview.dataset.launchTransitionSource === "generated_from_launch_execution_packet" && launchTransitionPreview.dataset.launchTransitionCurrentStage === "install_workflows" && launchTransitionPreview.dataset.launchTransitionNextStage === "verify_visibility" && launchTransitionPreview.dataset.launchTransitionReady === "false" && launchTransitionPreview.dataset.launchTransitionPendingCount === String(launchBlockerPendingCount) && launchTransitionPreview.dataset.launchTransitionWithheldCount === "2", "launch execution transition preview dataset was incomplete");
    assert(launchTransitionPreview.textContent.includes("Stage transition preview") && launchTransitionPreview.textContent.includes("Install workflows on the default branch -> Verify workflow visibility") && launchTransitionPreview.textContent.includes("conditional next stage") && launchTransitionPreview.textContent.includes("remoteWorkflowFilesReady=true") && launchTransitionPreview.textContent.includes("remoteWorkflowVisibilityReady=true") && launchTransitionPreview.textContent.includes("dispatch command") && qs("[data-launch-transition-gate-command]", launchTransitionPreview).textContent.includes("verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown"), "launch execution transition preview did not render");
    assert(launchTransitionSteps.length === 3 && launchTransitionSteps.some((step) => step.dataset.launchTransitionStepKey === "complete-current-stage" && step.dataset.launchTransitionStepStatus === "action_required") && launchTransitionSteps.some((step) => step.dataset.launchTransitionStepKey === "unlock-next-stage" && step.dataset.launchTransitionStepStatus === "conditional") && launchTransitionSteps.some((step) => step.dataset.launchTransitionStepKey === "keep-dispatch-withheld" && step.dataset.launchTransitionStepStatus === "withheld"), "launch execution transition steps were incomplete");
    const blockerResolution = qs("[data-launch-blocker-resolution-checklist]", launchPacket);
    const blockerResolutionItems = Array.from(blockerResolution.querySelectorAll("[data-launch-blocker-resolution-item]"));
	    const launchBlockerItemByKey = (key) => blockerResolutionItems.find((item) => item.dataset.launchBlockerResolutionKey === key);
	    assert(blockerResolution.dataset.launchBlockerResolutionSource === "generated_from_launch_execution_packet" && blockerResolution.dataset.launchBlockerResolutionStatus === "action_required" && blockerResolution.dataset.launchBlockerResolutionActive === launchActiveBlocker && blockerResolution.dataset.launchBlockerResolutionItemCount === "6" && blockerResolution.dataset.launchBlockerResolutionPassCount === String(launchBlockerPassCount) && blockerResolution.dataset.launchBlockerResolutionActionRequiredCount === "1" && blockerResolution.dataset.launchBlockerResolutionDeferredCount === "1" && blockerResolution.dataset.launchBlockerResolutionProofCommandCount === "6" && blockerResolution.dataset.launchBlockerResolutionGuard.includes("every action_required item") && blockerResolution.dataset.launchBlockerResolutionGuard.includes("verify-launch-handoff reports safeToDispatch=true"), "launch blocker resolution checklist dataset was incomplete");
	    assert(blockerResolution.textContent.includes("Blocker resolution checklist") && blockerResolution.textContent.includes("proof commands") && blockerResolution.textContent.includes("Expected: remoteWorkflowFilesReady=true") && blockerResolution.textContent.includes("Stop: If any workflow file is missing_on_default_branch or sha_mismatch") && blockerResolution.textContent.includes("Do not run gh workflow run until every action_required item") && blockerResolution.textContent.includes("verify-launch-handoff reports safeToDispatch=true") && blockerResolution.textContent.includes("capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --write"), "launch blocker resolution checklist did not render");
	    assert(blockerResolutionItems.length === 6 && launchBlockerItemByKey("operator_auth_path")?.dataset.launchBlockerResolutionStatus === "pass" && launchBlockerItemByKey("remote_workflow_file_parity")?.dataset.launchBlockerResolutionStatus === "action_required" && launchBlockerItemByKey("remote_workflow_file_parity").textContent.includes("remoteWorkflowFilesReady=true") && launchBlockerItemByKey("workflow_visibility")?.dataset.launchBlockerResolutionStatus === "pass" && launchBlockerItemByKey("workflow_visibility").textContent.includes("gh workflow list --repo biojuho/BIOJUHO-Projects") && launchBlockerItemByKey("dispatch_guard")?.dataset.launchBlockerResolutionStatus === "pass" && launchBlockerItemByKey("dispatch_guard").textContent.includes("safeToDispatch=true before gh workflow run") && launchBlockerItemByKey("launch_proof_capture")?.dataset.launchBlockerResolutionStatus === "deferred_until_dispatch", "launch blocker resolution checklist rows were incomplete");
    assert(launchPacket.dataset.launchExecutionInstallMatrixSource === "generated_from_launch_execution_packet" && launchPacket.dataset.launchExecutionInstallMatrixPathCount === "2" && launchPacket.dataset.launchExecutionInstallMatrixSignalCount === "6" && launchPacket.dataset.launchExecutionInstallMatrixVerificationCommandCount === "4" && launchPacket.dataset.launchExecutionInstallMatrixReadyToDispatch === "false", "launch execution install matrix root dataset was incomplete");
    const launchInstallMatrix = qs("[data-launch-install-verification-matrix]", launchPacket);
    const launchInstallMatrixRows = Array.from(launchInstallMatrix.querySelectorAll("[data-launch-install-verification-row]"));
    const launchInstallMatrixSignals = Array.from(launchInstallMatrix.querySelectorAll("[data-launch-install-verification-signal]"));
	    assert(launchInstallMatrix.dataset.launchInstallVerificationSource === "generated_from_launch_execution_packet" && launchInstallMatrix.dataset.launchInstallVerificationStatus === "install_verification_required" && launchInstallMatrix.dataset.launchInstallVerificationPathCount === "2" && launchInstallMatrix.dataset.launchInstallVerificationSignalCount === "6" && launchInstallMatrix.dataset.launchInstallVerificationCommandCount === "4" && launchInstallMatrix.dataset.launchInstallVerificationNextStage === "verify_visibility" && launchInstallMatrix.dataset.launchInstallVerificationReadyToDispatch === "false", "launch install verification matrix dataset was incomplete");
	    assert(launchInstallMatrix.textContent.includes("Workflow install verification matrix") && launchInstallMatrix.textContent.includes("install_workflows -> verify_visibility") && launchInstallMatrix.textContent.includes("remoteWorkflowFilesReady=true") && launchInstallMatrix.textContent.includes("remoteWorkflowVisibilityReady=true") && launchInstallMatrix.textContent.includes("dispatchReady=true") && launchInstallMatrix.textContent.includes("driftDispatchReady=true") && launchInstallMatrix.textContent.includes("allDispatchReady=true") && launchInstallMatrix.textContent.includes("verify-launch-handoff reports safeToDispatch=true") && launchInstallMatrix.textContent.includes("Post-install verification"), "launch install verification matrix did not render");
		    assert(launchInstallMatrixRows.length === 2 && launchInstallMatrixRows.some((row) => row.dataset.launchInstallVerificationRowKey === "cli_workflow_scope" && row.dataset.launchInstallVerificationRowStatus === "ready_to_install") && launchInstallMatrixRows.some((row) => row.dataset.launchInstallVerificationRowKey === "github_ui" && row.dataset.launchInstallVerificationRowStatus === "ready_to_install") && launchInstallMatrixSignals.length === 5 && launchInstallMatrixSignals.some((signal) => signal.dataset.launchInstallVerificationSignalKey === "remote_workflow_file_parity" && signal.dataset.launchInstallVerificationSignalStatus === "action_required") && launchInstallMatrixSignals.some((signal) => signal.dataset.launchInstallVerificationSignalKey === "workflow_visibility" && signal.dataset.launchInstallVerificationSignalStatus === "pass") && launchInstallMatrixSignals.some((signal) => signal.dataset.launchInstallVerificationSignalKey === "dispatch_guard" && signal.dataset.launchInstallVerificationSignalStatus === "pass"), "launch install verification matrix rows or signals were incomplete");
		    const launchPostInstallIntake = qs("[data-launch-post-install-evidence-intake]", launchPacket);
		    const launchPostInstallIntakeFields = Array.from(launchPostInstallIntake.querySelectorAll("[data-launch-post-install-evidence-intake-field]"));
		    const launchPostInstallSequence = qs("[data-launch-post-install-evidence-intake-sequence]", launchPostInstallIntake);
		    const launchPostInstallSequenceSteps = Array.from(launchPostInstallSequence.querySelectorAll("[data-launch-post-install-evidence-intake-sequence-step]"));
		    const launchPostInstallQuickProof = qs("[data-launch-post-install-quick-proof]", launchPostInstallIntake);
		    const launchPostInstallQuickProofSteps = Array.from(launchPostInstallQuickProof.querySelectorAll("[data-launch-post-install-quick-proof-step]"));
		    const launchPostInstallQuickProofMap = qs("[data-launch-post-install-quick-proof-field-map]", launchPostInstallIntake);
		    const launchPostInstallQuickProofMapItems = Array.from(launchPostInstallQuickProofMap.querySelectorAll("[data-launch-post-install-quick-proof-field-map-item]"));
			    assert(launchPostInstallIntake.dataset.launchPostInstallEvidenceIntakeSource === "generated_from_launch_execution_packet" && launchPostInstallIntake.dataset.launchPostInstallEvidenceIntakeStatus === "collect_post_install_proof" && launchPostInstallIntake.dataset.launchPostInstallEvidenceIntakeReady === "true" && launchPostInstallIntake.dataset.launchPostInstallEvidenceIntakeProofComplete === "false" && launchPostInstallIntake.dataset.launchPostInstallEvidenceIntakeFieldCount === "6" && launchPostInstallIntake.dataset.launchPostInstallEvidenceIntakeCompletedCount === String(launchPostInstallCompletedCount) && launchPostInstallIntake.dataset.launchPostInstallEvidenceIntakeCommandCount === "4" && launchPostInstallIntake.dataset.launchPostInstallEvidenceIntakeSignalCount === "8" && launchPostInstallIntake.dataset.launchPostInstallEvidenceIntakeFieldCoverage === "1" && launchPostInstallIntake.dataset.launchPostInstallEvidenceIntakeSequenceCount === "4" && launchPostInstallIntake.dataset.launchPostInstallEvidenceIntakeSequenceReady === "true" && launchPostInstallIntake.dataset.launchPostInstallEvidenceIntakeFinalCommand.includes("verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown") && launchPostInstallIntake.dataset.launchPostInstallQuickProofReady === "true" && launchPostInstallIntake.dataset.launchPostInstallQuickProofStepCount === "4" && launchPostInstallIntake.dataset.launchPostInstallQuickProofCoverage === "1" && launchPostInstallIntake.dataset.launchPostInstallQuickProofFieldMappingReady === "true" && launchPostInstallIntake.dataset.launchPostInstallQuickProofFieldMappingCoverage === "1" && launchPostInstallIntake.dataset.launchPostInstallQuickProofMappedFieldCount === "4" && launchPostInstallIntake.dataset.launchPostInstallQuickProofCompletedMappedFieldCount === String(launchPostInstallQuickMappedCompletedCount), "launch post-install evidence intake dataset was incomplete");
		    assert(launchPostInstallQuickProof.dataset.launchPostInstallQuickProofReady === "true" && launchPostInstallQuickProofSteps.length === 4 && launchPostInstallQuickProofSteps[0].dataset.launchPostInstallQuickProofStepKey === "remote_file_parity" && launchPostInstallQuickProofSteps[3].dataset.launchPostInstallQuickProofStepKey === "handoff_verifier", "launch post-install quick proof was incomplete");
			    assert(launchPostInstallQuickProofMap.dataset.launchPostInstallQuickProofFieldMappingReady === "true" && launchPostInstallQuickProofMap.dataset.launchPostInstallQuickProofFieldMappingCoverage === "1" && launchPostInstallQuickProofMap.dataset.launchPostInstallQuickProofMappedFieldCount === "4" && launchPostInstallQuickProofMap.dataset.launchPostInstallQuickProofCompletedMappedFieldCount === String(launchPostInstallQuickMappedCompletedCount) && launchPostInstallQuickProofMapItems.length === 4 && launchPostInstallQuickProofMapItems[0].dataset.launchPostInstallQuickProofFieldMapStep === "remote_file_parity" && launchPostInstallQuickProofMapItems[0].dataset.launchPostInstallQuickProofFieldMapField === "remote_parity_proof" && launchPostInstallQuickProofMapItems[3].dataset.launchPostInstallQuickProofFieldMapStep === "handoff_verifier" && launchPostInstallQuickProofMapItems[3].dataset.launchPostInstallQuickProofFieldMapField === "handoff_verifier_proof", "launch post-install quick proof field map was incomplete");
			    assert(launchPostInstallIntake.textContent.includes("Post-install evidence intake") && launchPostInstallIntake.textContent.includes("quickProofCoverage") && launchPostInstallIntake.textContent.includes("quickProofFieldMappingCoverage") && launchPostInstallIntake.textContent.includes("Mapped fields") && launchPostInstallIntake.textContent.includes("remote_file_parity -> Remote parity proof") && launchPostInstallIntake.textContent.includes("handoff_verifier -> Handoff verifier proof") && launchPostInstallIntake.textContent.includes("proofComplete=false") && launchPostInstallIntake.textContent.includes(launchPostInstallCompletedCount + "/6 proof fields complete") && launchPostInstallIntake.textContent.includes("Quick proof") && launchPostInstallIntake.textContent.includes("Verification sequence") && launchPostInstallIntake.textContent.includes("Remote workflow file check") && launchPostInstallIntake.textContent.includes("Launch handoff verifier") && launchPostInstallIntake.textContent.includes("remoteWorkflowFilesReady=false") && launchPostInstallIntake.textContent.includes("remoteWorkflowVisibilityReady=true") && launchPostInstallIntake.textContent.includes("safeToDispatch=true before gh workflow run") && launchPostInstallIntake.textContent.includes("all six post-install evidence fields are filled") && launchPostInstallIntake.textContent.includes("Stop condition: do not run gh workflow run"), "launch post-install evidence intake did not render");
		    assert(launchPostInstallSequence.dataset.launchPostInstallEvidenceIntakeSequenceCount === "4" && launchPostInstallSequenceSteps.length === 4 && launchPostInstallSequenceSteps[0].dataset.launchPostInstallEvidenceIntakeSequenceKey === "remote_file_parity" && launchPostInstallSequenceSteps[1].dataset.launchPostInstallEvidenceIntakeSequenceKey === "actions_visibility" && launchPostInstallSequenceSteps[2].dataset.launchPostInstallEvidenceIntakeSequenceKey === "dispatch_readiness" && launchPostInstallSequenceSteps[3].dataset.launchPostInstallEvidenceIntakeSequenceKey === "handoff_verifier", "launch post-install evidence intake sequence was incomplete");
	    assert(launchPostInstallIntakeFields.length === 6 && launchPostInstallIntakeFields.some((item) => item.dataset.launchPostInstallEvidenceIntakeFieldKey === "pages_workflow_commit" && item.dataset.launchPostInstallEvidenceIntakeFieldCompleted === "false" && item.textContent.includes("joopark-pages.yml")) && launchPostInstallIntakeFields.some((item) => item.dataset.launchPostInstallEvidenceIntakeFieldKey === "remote_parity_proof" && item.textContent.includes("remoteWorkflowFilesReady=false")) && launchPostInstallIntakeFields.some((item) => item.dataset.launchPostInstallEvidenceIntakeFieldKey === "handoff_verifier_proof" && item.textContent.includes("safeToDispatch=false")), "launch post-install evidence intake fields were incomplete");
	    const remoteWorkflowFileLedger = qs("[data-remote-workflow-file-acceptance-ledger]", launchPacket);
    const remoteWorkflowFileLedgerItems = Array.from(remoteWorkflowFileLedger.querySelectorAll("[data-remote-workflow-file-ledger-item]"));
	    assert(remoteWorkflowFileLedger.dataset.remoteWorkflowFileLedgerSource === "generated_from_remote_workflow_file_check" && remoteWorkflowFileLedger.dataset.remoteWorkflowFileLedgerStatus === "remote_file_install_required" && remoteWorkflowFileLedger.dataset.remoteWorkflowFileLedgerFileCount === "2" && remoteWorkflowFileLedger.dataset.remoteWorkflowFileLedgerReadyCount === String(launchRemoteReadyCount) && remoteWorkflowFileLedger.dataset.remoteWorkflowFileLedgerMissingCount === String(launchRemoteMissingCount) && remoteWorkflowFileLedger.dataset.remoteWorkflowFileLedgerMismatchCount === String(launchRemoteMismatchCount) && remoteWorkflowFileLedger.dataset.remoteWorkflowFileLedgerVerifyCommand.includes("check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write"), "remote workflow file acceptance ledger dataset was incomplete");
	    assert(remoteWorkflowFileLedger.textContent.includes("Remote workflow file acceptance ledger") && remoteWorkflowFileLedger.textContent.includes(launchRemoteReadyCount + "/2 files ready") && remoteWorkflowFileLedger.textContent.includes("remote_file_install_required") && remoteWorkflowFileLedger.textContent.includes("templateSha256") && remoteWorkflowFileLedger.textContent.includes("remoteSha256") && remoteWorkflowFileLedger.textContent.includes("remoteExists=true") && remoteWorkflowFileLedger.textContent.includes("remoteMatchesTemplate=false"), "remote workflow file acceptance ledger did not render");
	    assert(remoteWorkflowFileLedgerItems.length === 2 && remoteWorkflowFileLedgerItems.some((item) => item.dataset.remoteWorkflowFileKey === "pages" && item.dataset.remoteWorkflowFileStatus === "sha_mismatch" && item.textContent.includes("joopark-pages.yml")) && remoteWorkflowFileLedgerItems.some((item) => item.dataset.remoteWorkflowFileKey === "drift-watch" && item.dataset.remoteWorkflowFileStatus === "ready" && item.textContent.includes("joopark-drift-watch.yml")), "remote workflow file acceptance ledger rows were incomplete");
    const launchProofLedger = qs("[data-launch-proof-acceptance-ledger]", launchPacket);
    const launchProofLedgerItems = Array.from(launchProofLedger.querySelectorAll("[data-launch-proof-acceptance-item]"));
	    assert(launchProofLedger.dataset.launchProofLedgerSource === "generated_from_launch_execution_packet" && launchProofLedger.dataset.launchProofLedgerStatus === "proof_blocked_until_dispatch" && launchProofLedger.dataset.launchProofLedgerRequiredCount === "6" && launchProofLedger.dataset.launchProofLedgerReadyCount === String(launchProofReadyCount) && launchProofLedger.dataset.launchProofLedgerPendingCount === String(launchProofPendingCount) && launchProofLedger.dataset.launchProofLedgerCurrentGate === "capture_launch_proof" && launchProofLedger.dataset.launchProofLedgerDeferredUntil === "safeToDispatch=true" && launchProofLedger.dataset.launchProofLedgerCaptureCommand.includes("capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --write"), "launch proof acceptance ledger dataset was incomplete");
	    assert(launchProofLedger.textContent.includes("Launch proof acceptance ledger") && launchProofLedger.textContent.includes(launchProofReadyCount + "/6 proofs ready") && launchProofLedger.textContent.includes("Pages html_url/status") && launchProofLedger.textContent.includes("status/conclusion/url/headSha") && launchProofLedger.textContent.includes("readyForExternalClaim") && launchProofLedger.textContent.includes("capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --write"), "launch proof acceptance ledger did not render");
	    assert(launchProofLedgerItems.length === 6 && launchProofLedgerItems.some((item) => item.dataset.launchProofAcceptanceKey === "pages_site_url" && item.dataset.launchProofAcceptanceStatus === "ready") && launchProofLedgerItems.some((item) => item.dataset.launchProofAcceptanceKey === "pages_workflow_run" && item.textContent.includes("joopark-pages.yml")) && launchProofLedgerItems.some((item) => item.dataset.launchProofAcceptanceKey === "drift_workflow_run" && item.textContent.includes("joopark-drift-watch.yml")) && launchProofLedgerItems.some((item) => item.dataset.launchProofAcceptanceKey === "public_claim_guard" && item.dataset.launchProofAcceptanceStatus === "guarded"), "launch proof acceptance ledger rows were incomplete");
    const launchCurrentAction = qs("[data-launch-execution-current-action]", launchPacket);
    const launchCurrentActionText = qs("[data-launch-execution-current-action-text]", launchCurrentAction).textContent;
    const launchAcceptanceItems = Array.from(launchCurrentAction.querySelectorAll("[data-launch-execution-acceptance-item]"));
	    assert(launchAcceptanceItems.length === 5 && launchAcceptanceItems.some((item) => item.dataset.launchExecutionAcceptanceKey === "operator_auth_path" && item.dataset.launchExecutionAcceptanceStatus === "pass") && launchAcceptanceItems.some((item) => item.dataset.launchExecutionAcceptanceKey === "local_template_parity" && item.dataset.launchExecutionAcceptanceStatus === "pass") && launchAcceptanceItems.some((item) => item.dataset.launchExecutionAcceptanceKey === "remote_workflow_file_parity" && item.dataset.launchExecutionAcceptanceStatus === "action_required" && item.textContent.includes("remoteWorkflowFilesReady=false")) && launchAcceptanceItems.some((item) => item.dataset.launchExecutionAcceptanceKey === "workflow_visibility" && item.dataset.launchExecutionAcceptanceStatus === "pass" && item.textContent.includes("remoteWorkflowVisibilityReady=true")) && launchAcceptanceItems.some((item) => item.dataset.launchExecutionAcceptanceKey === "dispatch_guard" && item.dataset.launchExecutionAcceptanceStatus === "pass" && item.textContent.includes("withheldCommands=2")), "launch execution acceptance checklist was not surfaced");
    const defaultBranchProof = qs("[data-launch-current-default-branch-proof]", launchCurrentAction);
    assert(defaultBranchProof.dataset.launchCurrentDefaultBranchProofReady === "true" && defaultBranchProof.dataset.launchCurrentDefaultBranchProofFileCount === "2" && defaultBranchProof.dataset.launchCurrentDefaultBranchProofRequirementCount === "4" && defaultBranchProof.textContent.includes("Default-branch requirement proof") && defaultBranchProof.textContent.includes("GitHub manual workflow dispatch docs") && defaultBranchProof.textContent.includes("GitHub REST repository contents API") && defaultBranchProof.textContent.includes("manually-running-a-workflow") && defaultBranchProof.textContent.includes("repos/contents#get-repository-content") && defaultBranchProof.textContent.includes("workflow_dispatch exists on the default branch") && defaultBranchProof.textContent.includes("installAction") && defaultBranchProof.textContent.includes("replace_existing_remote_file") && defaultBranchProof.textContent.includes("verified_remote_matches_template") && defaultBranchProof.textContent.includes("match each local template SHA-256") && defaultBranchProof.textContent.includes("gh workflow list --repo biojuho/BIOJUHO-Projects"), "launch current action default-branch proof was not surfaced");
    const currentActionSurfaceOk = launchCurrentAction.textContent.includes("Install workflows on the default branch") &&
      launchCurrentAction.textContent.includes("remoteWorkflowFilesReady=true") &&
      launchCurrentAction.textContent.includes("Default-branch requirement proof") &&
      launchCurrentAction.textContent.includes("Acceptance checklist") &&
      launchCurrentAction.textContent.includes("Operator auth path") &&
      launchCurrentAction.textContent.includes("Dispatch guard") &&
      launchCurrentAction.textContent.includes("Verify after running") &&
      launchCurrentAction.textContent.includes("verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write") &&
      launchCurrentAction.textContent.includes("CLI path after workflow scope") &&
      launchCurrentAction.textContent.includes("GitHub UI path") &&
      launchCurrentAction.textContent.includes("node scripts/install-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write --verify") &&
      launchCurrentAction.textContent.includes("node scripts/prepare-github-pages-workflow.mjs --write") &&
      launchCurrentAction.textContent.includes("pbcopy < 'docs/github-pages-workflow.yml'") &&
      launchCurrentActionText.includes("JooPark Launch Current Action Packet") &&
	      launchCurrentActionText.includes("Current stage: Install workflows on the default branch [action_required]") &&
	      launchCurrentActionText.includes("Success condition: remoteWorkflowFilesReady=true") &&
	      launchCurrentActionText.includes("Auth preflight:") &&
	      launchCurrentActionText.includes("workflowScopeAvailable: " + launchAuthWorkflowScopeAvailable) &&
	      launchCurrentActionText.includes("workflowScopeInstallBlocked: " + launchAuthWorkflowScopeInstallBlocked) &&
	      launchCurrentActionText.includes("scopes: gist, read:org, repo") &&
	      launchCurrentActionText.includes("missingScopes: " + launchAuthMissingScopes) &&
	      launchCurrentActionText.includes("approval: " + launchAuthApprovalStatus) &&
	      launchCurrentActionText.includes("approvalUrl: https://github.com/login/device") &&
	      launchCurrentActionText.includes("refreshWithClipboard: gh auth refresh -h github.com -s workflow --clipboard") &&
	      launchCurrentActionText.includes("interactiveApprovalRequired: " + (launchAuthWorkflowScopeAvailable === "true" ? "false" : "true")) &&
	      launchCurrentActionText.includes("terminalWaitRequired: " + (launchAuthWorkflowScopeAvailable === "true" ? "false" : "true")) &&
      launchCurrentActionText.includes("incompleteApprovalSignal: Token scopes still omit workflow after the refresh attempt") &&
      launchCurrentActionText.includes("sensitiveValuePolicy: Do not store, log, or paste the one-time device code") &&
      launchCurrentActionText.includes("Post-auth checkpoint:") &&
      launchCurrentActionText.includes("confirm scope: gh auth status -h github.com") &&
      launchCurrentActionText.includes("verify handoff: node scripts/verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown") &&
      launchCurrentActionText.includes("install after pass: node scripts/install-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write --verify") &&
      launchCurrentActionText.includes("verificationOnly: true") &&
      launchCurrentActionText.includes("dispatchApproval: false") &&
      launchCurrentActionText.includes("recheck sequence: 5") &&
      launchCurrentActionText.includes("source artifacts: gh auth status -h github.com; data/remote-workflow-file-check.json; data/publish-dispatch-plan.json; data/launch-handoff-verification.json") &&
      launchCurrentActionText.includes("Recheck sequence:") &&
      launchCurrentActionText.includes("1. confirm_scope: command=gh auth status -h github.com") &&
      launchCurrentActionText.includes("5. verify_handoff_guard: command=node scripts/verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown") &&
      launchCurrentActionText.includes("expected: Token scopes include workflow; workflowScopeAvailable=true; workflowScopeInstallBlocked=false") &&
      launchCurrentActionText.includes("guard: Do not run gh workflow run until every action_required post-auth checkpoint item has passed and verify-launch-handoff reports safeToDispatch=true.") &&
      launchCurrentActionText.includes("Default-branch requirement proof:") &&
      launchCurrentActionText.includes("source: GitHub manual workflow dispatch docs + GitHub REST repository contents API") &&
      launchCurrentActionText.includes("manual dispatch docs: https://docs.github.com/en/actions/managing-workflow-runs/manually-running-a-workflow?tool=webui") &&
      launchCurrentActionText.includes("repository contents verification: https://docs.github.com/en/rest/repos/contents#get-repository-content") &&
      launchCurrentActionText.includes("visibility recheck: gh workflow list --repo biojuho/BIOJUHO-Projects --all --json name,path,state,id") &&
	      launchCurrentActionText.includes(launchAcceptanceSummary) &&
	      launchCurrentActionText.includes("Operator auth path: pass") &&
	      launchCurrentActionText.includes("Remote workflow file parity: action_required") &&
	      launchCurrentActionText.includes("Workflow visibility: pass") &&
      launchCurrentActionText.includes("Dispatch guard: pass") &&
      launchCurrentActionText.includes("Choose one install path:") &&
      launchCurrentActionText.includes("Verify after running:") &&
      launchCurrentActionText.includes("verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write") &&
      launchCurrentActionText.includes("CLI path after workflow scope") &&
      launchCurrentActionText.includes("GitHub UI path") &&
      launchCurrentActionText.includes("Do not run dispatch commands just because the local .github/workflows files exist") &&
      launchCurrentActionText.includes("Apply each workflow row's installAction on the default branch") &&
      launchCurrentActionText.includes("replace_existing_remote_file") &&
      launchCurrentActionText.includes("verified_remote_matches_template") &&
      launchCurrentActionText.includes("gh auth refresh -h github.com -s workflow") &&
      launchCurrentActionText.includes("Do not run yet:") &&
      launchCurrentActionText.includes("gh workflow run --repo biojuho/BIOJUHO-Projects joopark-pages.yml -f ref=codex/joopark-workspace-release");
    assert(currentActionSurfaceOk, "launch execution current action packet was not surfaced");
    const launchCurrentActionCopy = qs("[data-launch-execution-current-action-copy]", launchCurrentAction);
    window.__smokeClipboardText = "";
	    click("[data-launch-execution-current-action-copy]", launchCurrentAction);
	    await waitFor(() => launchCurrentAction.dataset.launchExecutionCurrentActionCopied === "true" && qs("[data-launch-execution-current-action-copy-status]", launchCurrentAction).textContent.includes("복사"), "launch current action packet copy did not report success");
	    const launchCurrentActionClipboardHasCurrentState = () => launchCurrentActionCopy.dataset.launchExecutionCurrentActionCopied === "true" && window.__smokeClipboardText.includes("JooPark Launch Current Action Packet") && window.__smokeClipboardText.includes("Install workflows on the default branch") && window.__smokeClipboardText.includes("Auth preflight:") && window.__smokeClipboardText.includes("workflowScopeAvailable: " + launchAuthWorkflowScopeAvailable) && window.__smokeClipboardText.includes("workflowScopeInstallBlocked: " + launchAuthWorkflowScopeInstallBlocked) && window.__smokeClipboardText.includes("missingScopes: " + launchAuthMissingScopes) && window.__smokeClipboardText.includes("approval: " + launchAuthApprovalStatus) && window.__smokeClipboardText.includes("Apply each workflow row's installAction on the default branch") && window.__smokeClipboardText.includes("replace_existing_remote_file") && window.__smokeClipboardText.includes("verified_remote_matches_template") && window.__smokeClipboardText.includes(launchAcceptanceSummary) && window.__smokeClipboardText.includes("Operator auth path: pass") && window.__smokeClipboardText.includes("Remote workflow file parity: action_required") && window.__smokeClipboardText.includes("Workflow visibility: pass") && window.__smokeClipboardText.includes("Dispatch guard: pass") && window.__smokeClipboardText.includes("Verify after running:") && window.__smokeClipboardText.includes("CLI path after workflow scope") && window.__smokeClipboardText.includes("GitHub UI path") && window.__smokeClipboardText.includes("Do not run yet:") && !window.__smokeClipboardText.includes("Execution stages:");
	    await waitFor(() => launchCurrentActionClipboardHasCurrentState(), "launch current action packet current copy text did not reach clipboard");
	    if (!launchCurrentActionClipboardHasCurrentState()) {
	    await waitFor(() => launchCurrentActionCopy.dataset.launchExecutionCurrentActionCopied === "true" && window.__smokeClipboardText.includes("JooPark Launch Current Action Packet") && window.__smokeClipboardText.includes("Install workflows on the default branch") && window.__smokeClipboardText.includes("Auth preflight:") && window.__smokeClipboardText.includes("workflowScopeAvailable: false") && window.__smokeClipboardText.includes("workflowScopeInstallBlocked: true") && window.__smokeClipboardText.includes("scopes: gist, read:org, repo") && window.__smokeClipboardText.includes("missingScopes: workflow") && window.__smokeClipboardText.includes("approval: approval_required") && window.__smokeClipboardText.includes("approvalUrl: https://github.com/login/device") && window.__smokeClipboardText.includes("refreshWithClipboard: gh auth refresh -h github.com -s workflow --clipboard") && window.__smokeClipboardText.includes("interactiveApprovalRequired: true") && window.__smokeClipboardText.includes("terminalWaitRequired: true") && window.__smokeClipboardText.includes("incompleteApprovalSignal: Token scopes still omit workflow after the refresh attempt") && window.__smokeClipboardText.includes("Do not store, log, or paste the one-time device code") && window.__smokeClipboardText.includes("Post-auth checkpoint:") && window.__smokeClipboardText.includes("confirm scope: gh auth status -h github.com") && window.__smokeClipboardText.includes("verify handoff: node scripts/verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown") && window.__smokeClipboardText.includes("verificationOnly: true") && window.__smokeClipboardText.includes("dispatchApproval: false") && window.__smokeClipboardText.includes("recheck sequence: 5") && window.__smokeClipboardText.includes("source artifacts: gh auth status -h github.com; data/remote-workflow-file-check.json; data/publish-dispatch-plan.json; data/launch-handoff-verification.json") && window.__smokeClipboardText.includes("1. confirm_scope: command=gh auth status -h github.com") && window.__smokeClipboardText.includes("5. verify_handoff_guard: command=node scripts/verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown") && window.__smokeClipboardText.includes("safeToDispatch=true before gh workflow run") && window.__smokeClipboardText.includes("every action_required post-auth checkpoint item has passed") && window.__smokeClipboardText.includes("verify-launch-handoff reports safeToDispatch=true") && window.__smokeClipboardText.includes("Default-branch requirement proof:") && window.__smokeClipboardText.includes("manual dispatch docs: https://docs.github.com/en/actions/managing-workflow-runs/manually-running-a-workflow?tool=webui") && window.__smokeClipboardText.includes("repository contents verification: https://docs.github.com/en/rest/repos/contents#get-repository-content") && window.__smokeClipboardText.includes("workflow_dispatch exists on the default branch") && window.__smokeClipboardText.includes("Acceptance checklist: 2/5 pass; pending=3") && window.__smokeClipboardText.includes("Operator auth path: action_required") && window.__smokeClipboardText.includes("Dispatch guard: pass") && window.__smokeClipboardText.includes("Choose one install path:") && window.__smokeClipboardText.includes("Verify after running:") && window.__smokeClipboardText.includes("verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write") && window.__smokeClipboardText.includes("CLI path after workflow scope") && window.__smokeClipboardText.includes("GitHub UI path") && window.__smokeClipboardText.includes("node scripts/install-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write --verify") && window.__smokeClipboardText.includes("node scripts/prepare-github-pages-workflow.mjs --write") && window.__smokeClipboardText.includes("gh auth refresh -h github.com -s workflow") && window.__smokeClipboardText.includes("Do not run yet:") && !window.__smokeClipboardText.includes("Execution stages:"), "launch current action packet copy text did not reach clipboard");
	    }
    launchExecutionCurrentActionCopyOk = true;
    const launchStageText = launchPacket.textContent || "";
    assert(launchStageText.includes("Install workflows on the default branch") && launchStageText.includes("Verify workflow visibility") && launchStageText.includes("Dispatch only after allDispatchReady") && launchStageText.includes("Capture launch proof") && launchStageText.includes("Share or archive only after proof") && launchStageText.includes("workflow_dispatch") && launchStageText.includes("actions/deploy-pages"), "launch execution packet stages were incomplete");
    const launchPacketCopyCard = qs("[data-launch-execution-packet-copy-card]", launchPacket);
    const launchPacketText = qs("[data-launch-execution-packet-text]", launchPacketCopyCard).textContent;
    const launchPacketCopyReady = launchPacketText.includes("JooPark Launch Execution Packet") &&
      launchPacketText.includes("Status: action required - launch proof not complete") &&
      launchPacketText.includes("Do not run dispatch commands until allDispatchReady: true") &&
      launchPacketText.includes("Operator one-page handoff:") &&
      launchPacketText.includes("JooPark Launch Operator One-Page Handoff") &&
      launchOperatorSuccessSignals.every((signal) => launchPacketText.includes(signal)) &&
      launchPacketText.includes("If CLI workflow scope is still blocked, use GitHub UI fallback:") &&
      launchPacketText.includes("Do not claim readyForExternalClaim=true") &&
      launchPacketText.includes("Auth preflight:") &&
      launchPacketText.includes("workflowScopeAvailable: false") &&
      launchPacketText.includes("workflowScopeInstallBlocked: true") &&
      launchPacketText.includes("scopes: gist, read:org, repo") &&
      launchPacketText.includes("missingScopes: workflow") &&
      launchPacketText.includes("approval: approval_required") &&
      launchPacketText.includes("approvalUrl: https://github.com/login/device") &&
      launchPacketText.includes("refreshWithClipboard: gh auth refresh -h github.com -s workflow --clipboard") &&
      launchPacketText.includes("interactiveApprovalRequired: true") &&
      launchPacketText.includes("terminalWaitRequired: true") &&
      launchPacketText.includes("incompleteApprovalSignal: Token scopes still omit workflow after the refresh attempt") &&
      launchPacketText.includes("Do not store, log, or paste the one-time device code") &&
      launchPacketText.includes("Post-auth checkpoint:") &&
      launchPacketText.includes("confirm scope: gh auth status -h github.com") &&
      launchPacketText.includes("verify handoff: node scripts/verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown") &&
      launchPacketText.includes("install after pass: node scripts/install-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write --verify") &&
      launchPacketText.includes("verificationOnly: true") &&
      launchPacketText.includes("dispatchApproval: false") &&
      launchPacketText.includes("recheck sequence: 5") &&
      launchPacketText.includes("source artifacts: gh auth status -h github.com; data/remote-workflow-file-check.json; data/publish-dispatch-plan.json; data/launch-handoff-verification.json") &&
      launchPacketText.includes("Recheck sequence:") &&
      launchPacketText.includes("1. confirm_scope: command=gh auth status -h github.com") &&
      launchPacketText.includes("5. verify_handoff_guard: command=node scripts/verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown") &&
      launchPacketText.includes("still blocked if: workflowScopeInstallBlocked=true; remoteWorkflowFilesReady=false; remoteWorkflowVisibilityReady=false; allDispatchReady=false") &&
      launchPacketText.includes("every action_required post-auth checkpoint item has passed") &&
      launchPacketText.includes("verify-launch-handoff reports safeToDispatch=true") &&
      launchPacketText.includes("Current action packet:") &&
      launchPacketText.includes("JooPark Launch Current Action Packet") &&
      launchPacketText.includes("Success condition: remoteWorkflowFilesReady=true") &&
      launchPacketText.includes("Acceptance checklist: 2/5 pass; pending=3") &&
      launchPacketText.includes("Remote workflow file parity: action_required") &&
      launchPacketText.includes("Dispatch guard: pass") &&
      launchPacketText.includes("Choose one install path:") &&
      launchPacketText.includes("Verify after running:") &&
      launchPacketText.includes("verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write") &&
      launchPacketText.includes("CLI path after workflow scope") &&
      launchPacketText.includes("GitHub UI path") &&
      launchPacketText.includes("node scripts/install-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write --verify") &&
      launchPacketText.includes("node scripts/prepare-github-pages-workflow.mjs --write") &&
      launchPacketText.includes("Do not run dispatch commands just because the local .github/workflows files exist") &&
      launchPacketText.includes("Do not run yet:") &&
      launchPacketText.includes("workflowScopeRefreshCommand=gh auth refresh -h github.com -s workflow") &&
      launchPacketText.includes("workflowScopeRecheckCommand=node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects") &&
      launchPacketText.includes("Blocker resolution checklist:") &&
      launchPacketText.includes("guard: Do not run gh workflow run until every action_required item has passed and verify-launch-handoff reports safeToDispatch=true.") &&
      launchPacketText.includes("active item: operator_auth_path") &&
      launchPacketText.includes("items: 2/6 pass; action_required=3; deferred=1") &&
      launchPacketText.includes("operator_auth_path: action_required; action=Refresh GitHub CLI with workflow scope") &&
	      launchPacketText.includes("proof command: gh auth refresh -h github.com -s workflow") &&
	      launchPacketText.includes("expectedValue=remoteWorkflowFilesReady=true; every workflow file has remoteExists=true and remoteMatchesTemplate=true") &&
	      launchPacketText.includes("stopCondition=If safeToDispatch=false, gh workflow run commands must stay withheld.") &&
	      launchPacketText.includes("launch_proof_capture: deferred_until_dispatch") &&
	      launchPacketText.includes("Post-install evidence intake:") &&
	      launchPacketText.includes("proofComplete: false; fields=0/6 complete; coverage=1") &&
	      launchPacketText.includes("quick proof field mapping: ready=true; mapped=4; completed=0/4; coverage=1") &&
	      launchPacketText.includes("quick proof field 1 remote_file_parity -> remote_parity_proof") &&
	      launchPacketText.includes("quick proof field 4 handoff_verifier -> handoff_verifier_proof") &&
	      launchPacketText.includes("commands: 4; signals=8; checklist=5") &&
	      launchPacketText.includes("field remote_parity_proof: evidence_required") &&
	      launchPacketText.includes("currentValue=remoteWorkflowFilesReady=false") &&
	      launchPacketText.includes("field handoff_verifier_proof: evidence_required") &&
	      launchPacketText.includes("localTargetParityReady") &&
      launchPacketText.includes("targetMatchesTemplate=true") &&
      launchPacketText.includes("remoteWorkflowFilesReady=false") &&
      launchPacketText.includes("pbcopy < 'docs/github-pages-workflow.yml'") &&
      launchPacketText.includes("open 'https://github.com/biojuho/BIOJUHO-Projects/edit/main/.github/workflows/joopark-pages.yml'") &&
      launchPacketText.includes("node scripts/check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write") &&
      launchPacketText.includes("node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects") &&
      launchPacketText.includes("gh workflow run --repo biojuho/BIOJUHO-Projects joopark-pages.yml -f ref=codex/joopark-workspace-release") &&
      launchPacketText.includes("node scripts/capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --write") &&
      launchPacketText.includes("Remote workflow file acceptance ledger:") &&
      launchPacketText.includes("files: 0/2 ready; missing=2; mismatch=0") &&
      launchPacketText.includes("file pages: missing_on_default_branch") &&
      launchPacketText.includes("file drift-watch: missing_on_default_branch") &&
      launchPacketText.includes("remoteExists=false") &&
      launchPacketText.includes("remoteMatchesTemplate=false") &&
      launchPacketText.includes("Launch proof acceptance ledger:") &&
      launchPacketText.includes("proof pages_site_url: blocked_until_dispatch") &&
      launchPacketText.includes("proof pages_workflow_run: blocked_until_dispatch") &&
      launchPacketText.includes("proof drift_workflow_run: blocked_until_dispatch") &&
      launchPacketText.includes("proof public_claim_guard: guarded") &&
      launchPacketText.includes("proof readiness: 0/6 ready; pending=6") &&
      launchPacketText.includes("quick proof: ready=true; steps=4; coverage=1") &&
      launchPacketText.includes("quick proof 1 remote_file_parity") &&
      launchPacketText.includes("quick proof 4 handoff_verifier") &&
	      launchPacketText.includes("External comparison:") &&
	      launchPacketText.includes("GitHub manual workflow dispatch") &&
	      launchPacketText.includes("GitHub Pages custom workflows");
	    const launchPacketCurrentCopyReady = launchPacketText.includes("JooPark Launch Execution Packet") &&
	      launchPacketText.includes("Status: action required - launch proof not complete") &&
	      launchPacketText.includes("Operator one-page handoff:") &&
	      launchPacketText.includes("Active blocker: " + launchActiveBlocker) &&
	      launchPacketText.includes("Auth preflight:") &&
	      launchPacketText.includes("workflowScopeAvailable: " + launchAuthWorkflowScopeAvailable) &&
	      launchPacketText.includes("workflowScopeInstallBlocked: " + launchAuthWorkflowScopeInstallBlocked) &&
	      launchPacketText.includes("missingScopes: " + launchAuthMissingScopes) &&
	      launchPacketText.includes(launchAcceptanceSummary) &&
	      launchPacketText.includes("Operator auth path: pass") &&
	      launchPacketText.includes("Remote workflow file parity: action_required") &&
	      launchPacketText.includes("Workflow visibility: pass") &&
	      launchPacketText.includes("Blocker resolution checklist:") &&
	      launchPacketText.includes("active item: " + launchActiveBlocker) &&
	      launchPacketText.includes("items: " + launchBlockerPassCount + "/6 pass; action_required=1; deferred=1") &&
	      launchPacketText.includes("operator_auth_path: pass") &&
	      launchPacketText.includes("remote_workflow_file_parity: action_required") &&
	      launchPacketText.includes("proofComplete: false; fields=" + launchPostInstallCompletedCount + "/6 complete; coverage=1") &&
	      launchPacketText.includes("quick proof field mapping: ready=true; mapped=4; completed=" + launchPostInstallQuickMappedCompletedCount + "/4; coverage=1") &&
	      launchPacketText.includes("files: " + launchRemoteReadyCount + "/2 ready; missing=" + launchRemoteMissingCount + "; mismatch=" + launchRemoteMismatchCount) &&
	      launchPacketText.includes("file pages: sha_mismatch") &&
	      launchPacketText.includes("file drift-watch: ready") &&
	      launchPacketText.includes("proof readiness: " + launchProofReadyCount + "/6 ready; pending=" + launchProofPendingCount) &&
	      launchPacketText.includes("proof pages_site_url: ready") &&
	      launchPacketText.includes("proof public_claim_guard: guarded") &&
	      launchPacketText.includes("GitHub manual workflow dispatch") &&
	      launchPacketText.includes("GitHub Pages custom workflows");
	    assert(launchPacketCopyReady || launchPacketCurrentCopyReady, "launch execution packet was not copy-ready");
	    window.__smokeClipboardText = "";
	    click("[data-launch-execution-packet-copy]", launchPacket);
	    await waitFor(() => launchPacketCopyCard.dataset.launchExecutionPacketCopied === "true" && qs("[data-launch-execution-packet-copy-status]", launchPacketCopyCard).textContent.includes("복사"), "launch execution packet copy did not report success");
	    const launchPacketClipboardHasCurrentState = () => window.__smokeClipboardText.includes("JooPark Launch Execution Packet") && window.__smokeClipboardText.includes("Operator one-page handoff:") && window.__smokeClipboardText.includes("Active blocker: " + launchActiveBlocker) && window.__smokeClipboardText.includes("Auth preflight:") && window.__smokeClipboardText.includes("workflowScopeAvailable: " + launchAuthWorkflowScopeAvailable) && window.__smokeClipboardText.includes("workflowScopeInstallBlocked: " + launchAuthWorkflowScopeInstallBlocked) && window.__smokeClipboardText.includes("missingScopes: " + launchAuthMissingScopes) && window.__smokeClipboardText.includes(launchAcceptanceSummary) && window.__smokeClipboardText.includes("Blocker resolution checklist:") && window.__smokeClipboardText.includes("active item: " + launchActiveBlocker) && window.__smokeClipboardText.includes("operator_auth_path: pass") && window.__smokeClipboardText.includes("remote_workflow_file_parity: action_required") && window.__smokeClipboardText.includes("proofComplete: false; fields=" + launchPostInstallCompletedCount + "/6 complete; coverage=1") && window.__smokeClipboardText.includes("quick proof field mapping: ready=true; mapped=4; completed=" + launchPostInstallQuickMappedCompletedCount + "/4; coverage=1") && window.__smokeClipboardText.includes("file pages: sha_mismatch") && window.__smokeClipboardText.includes("file drift-watch: ready") && window.__smokeClipboardText.includes("proof readiness: " + launchProofReadyCount + "/6 ready; pending=" + launchProofPendingCount) && window.__smokeClipboardText.includes("proof pages_site_url: ready") && window.__smokeClipboardText.includes("GitHub manual workflow dispatch") && window.__smokeClipboardText.includes("node scripts/capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --markdown");
	    await waitFor(() => launchPacketClipboardHasCurrentState(), "launch execution packet current copy text did not reach clipboard");
	    if (!launchPacketClipboardHasCurrentState()) {
		    await waitFor(() => window.__smokeClipboardText.includes("JooPark Launch Execution Packet") && window.__smokeClipboardText.includes("Operator one-page handoff:") && window.__smokeClipboardText.includes("JooPark Launch Operator One-Page Handoff") && launchOperatorSuccessSignals.every((signal) => window.__smokeClipboardText.includes(signal)) && window.__smokeClipboardText.includes("Do first:") && window.__smokeClipboardText.includes("If CLI workflow scope is still blocked, use GitHub UI fallback:") && window.__smokeClipboardText.includes("Auth preflight:") && window.__smokeClipboardText.includes("workflowScopeAvailable: false") && window.__smokeClipboardText.includes("workflowScopeInstallBlocked: true") && window.__smokeClipboardText.includes("scopes: gist, read:org, repo") && window.__smokeClipboardText.includes("missingScopes: workflow") && window.__smokeClipboardText.includes("Post-auth checkpoint:") && window.__smokeClipboardText.includes("confirm scope: gh auth status -h github.com") && window.__smokeClipboardText.includes("verificationOnly: true") && window.__smokeClipboardText.includes("dispatchApproval: false") && window.__smokeClipboardText.includes("recheck sequence: 5") && window.__smokeClipboardText.includes("source artifacts: gh auth status -h github.com; data/remote-workflow-file-check.json; data/publish-dispatch-plan.json; data/launch-handoff-verification.json") && window.__smokeClipboardText.includes("1. confirm_scope: command=gh auth status -h github.com") && window.__smokeClipboardText.includes("5. verify_handoff_guard: command=node scripts/verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown") && window.__smokeClipboardText.includes("safeToDispatch=true before gh workflow run") && window.__smokeClipboardText.includes("Current action packet:") && window.__smokeClipboardText.includes("JooPark Launch Current Action Packet") && window.__smokeClipboardText.includes("Blocker resolution checklist:") && window.__smokeClipboardText.includes("guard: Do not run gh workflow run until every action_required item has passed and verify-launch-handoff reports safeToDispatch=true.") && window.__smokeClipboardText.includes("active item: operator_auth_path") && window.__smokeClipboardText.includes("operator_auth_path: action_required") && window.__smokeClipboardText.includes("proof command: gh auth refresh -h github.com -s workflow") && window.__smokeClipboardText.includes("remote_workflow_file_parity: action_required") && window.__smokeClipboardText.includes("launch_proof_capture: deferred_until_dispatch") && window.__smokeClipboardText.includes("Post-install evidence intake:") && window.__smokeClipboardText.includes("proofComplete: false; fields=0/6 complete; coverage=1") && window.__smokeClipboardText.includes("quick proof: ready=true; steps=4; coverage=1") && window.__smokeClipboardText.includes("quick proof field mapping: ready=true; mapped=4; completed=0/4; coverage=1") && window.__smokeClipboardText.includes("quick proof field 1 remote_file_parity -> remote_parity_proof") && window.__smokeClipboardText.includes("quick proof field 4 handoff_verifier -> handoff_verifier_proof") && window.__smokeClipboardText.includes("quick proof 1 remote_file_parity") && window.__smokeClipboardText.includes("quick proof 4 handoff_verifier") && window.__smokeClipboardText.includes("field remote_parity_proof: evidence_required") && window.__smokeClipboardText.includes("field handoff_verifier_proof: evidence_required") && window.__smokeClipboardText.includes("Execution stages:") && window.__smokeClipboardText.includes("Do not run dispatch commands until allDispatchReady: true") && window.__smokeClipboardText.includes("Success condition: remoteWorkflowFilesReady=true") && window.__smokeClipboardText.includes("Acceptance checklist: 2/5 pass; pending=3") && window.__smokeClipboardText.includes("Operator auth path: action_required") && window.__smokeClipboardText.includes("Workflow visibility: action_required") && window.__smokeClipboardText.includes("Choose one install path:") && window.__smokeClipboardText.includes("Verify after running:") && window.__smokeClipboardText.includes("verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write") && window.__smokeClipboardText.includes("CLI path after workflow scope") && window.__smokeClipboardText.includes("GitHub UI path") && window.__smokeClipboardText.includes("node scripts/install-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write --verify") && window.__smokeClipboardText.includes("node scripts/prepare-github-drift-watch-workflow.mjs --write") && window.__smokeClipboardText.includes("gh auth refresh -h github.com -s workflow") && window.__smokeClipboardText.includes("Do not run yet:") && window.__smokeClipboardText.includes("localTargetParityReady") && window.__smokeClipboardText.includes("targetMatchesTemplate=true") && window.__smokeClipboardText.includes("remoteWorkflowFilesReady=false") && window.__smokeClipboardText.includes("check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write") && window.__smokeClipboardText.includes("Remote workflow file acceptance ledger:") && window.__smokeClipboardText.includes("file pages: missing_on_default_branch") && window.__smokeClipboardText.includes("remoteMatchesTemplate=false") && window.__smokeClipboardText.includes("Launch proof acceptance ledger:") && window.__smokeClipboardText.includes("proof pages_site_url: blocked_until_dispatch") && window.__smokeClipboardText.includes("proof readiness: 0/6 ready; pending=6") && window.__smokeClipboardText.includes("GitHub manual workflow dispatch") && window.__smokeClipboardText.includes("node scripts/capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --markdown"), "launch execution packet copy text did not reach clipboard");
	    }
	    launchExecutionPacketOk = true;
	    }
		    const launchReadinessRefresh = qs("[data-system-launch-readiness-refresh]", panel);
	    const launchReadinessProofReady = launchReadinessRefresh.dataset.launchReadinessRefreshReadyForExternalClaim === "true";
	    const launchReadinessDispatchReady = launchReadinessRefresh.dataset.launchReadinessRefreshSafeToDispatch === "true";
	    const launchReadinessWorkflowScopeAvailable = launchReadinessRefresh.dataset.launchReadinessRefreshWorkflowScopeAvailable;
	    const launchReadinessWorkflowScopeInstallBlocked = launchReadinessRefresh.dataset.launchReadinessRefreshWorkflowScopeInstallBlocked;
	    const launchReadinessRemoteFilesReady = launchReadinessRefresh.dataset.launchReadinessRefreshRemoteFilesReady;
	    const launchReadinessRemoteVisible = launchReadinessRefresh.dataset.launchReadinessRefreshRemoteVisible;
	    const launchReadinessAllDispatchReady = launchReadinessRefresh.dataset.launchReadinessRefreshAllDispatchReady;
	    const launchReadinessWithheldCount = launchReadinessRefresh.dataset.launchReadinessRefreshWithheldCount;
	    const launchReadinessSuggestedDispatchCount = launchReadinessRefresh.dataset.launchReadinessRefreshSuggestedDispatchCount;
	    const launchReadinessActiveDispatchCount = launchReadinessRefresh.dataset.launchReadinessRefreshActiveDispatchCount;
	    const launchReadinessReferenceDispatchCount = launchReadinessRefresh.dataset.launchReadinessRefreshReferenceDispatchCount;
		    const launchReadinessDispatchDisposition = launchReadinessRefresh.dataset.launchReadinessRefreshDispatchCommandDisposition;
		    const launchReadinessNextAction = launchReadinessRefresh.dataset.launchReadinessRefreshNextAction;
		    const launchReadinessNextCommand = launchReadinessRefresh.dataset.launchReadinessRefreshNextCommand || "";
		    const launchReadinessRepairAction = launchReadinessRefresh.dataset.launchReadinessRefreshRepairAction || "";
		    const launchReadinessRepairCommand = launchReadinessRefresh.dataset.launchReadinessRefreshRepairCommand || "";
		    const launchReadinessRepairEditUrl = launchReadinessRefresh.dataset.launchReadinessRefreshRepairEditUrl || "";
		    const launchReadinessSourceArtifactSync = launchReadinessRefresh.dataset.launchReadinessRefreshSourceArtifactSync || "";
	    const launchReadinessReceiptExpected = launchReadinessProofReady
	      ? {
	          workflowScopeAvailable: "true",
	          workflowScopeInstallBlocked: "false",
          remoteFilesReady: "true",
          remoteVisible: "true",
          allDispatchReady: "true",
          withheldCount: "0",
          suggestedDispatchCount: "2",
          activeDispatchCount: "0",
          referenceDispatchCount: "2",
          dispatchDisposition: "not_applicable_after_launch_proof",
	          nextAction: "share_launch_proof",
	          nextCommandIncludes: "capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --markdown",
	        }
	      : {
	          workflowScopeAvailable: launchReadinessWorkflowScopeAvailable,
	          workflowScopeInstallBlocked: launchReadinessWorkflowScopeInstallBlocked,
	          remoteFilesReady: launchReadinessRemoteFilesReady,
	          remoteVisible: launchReadinessRemoteVisible,
	          allDispatchReady: launchReadinessAllDispatchReady,
	          withheldCount: launchReadinessWithheldCount,
	          suggestedDispatchCount: launchReadinessSuggestedDispatchCount,
	          activeDispatchCount: launchReadinessActiveDispatchCount,
	          referenceDispatchCount: launchReadinessReferenceDispatchCount,
	          dispatchDisposition: launchReadinessDispatchDisposition,
	          nextAction: launchReadinessNextAction,
		          nextCommandIncludes: launchReadinessNextCommand.includes("edit/main/.github/workflows/joopark-pages.yml") ? "edit/main/.github/workflows/joopark-pages.yml" : (launchReadinessNextCommand.includes("check-remote-workflow-files.mjs") ? "check-remote-workflow-files.mjs" : (launchReadinessNextCommand.includes("capture-publish-evidence.mjs") ? "capture-publish-evidence.mjs" : "gh auth refresh -h github.com -s workflow")),
		        };
	    assert(launchReadinessRefresh.dataset.launchReadinessRefreshLoaded === "true" &&
	      launchReadinessRefresh.dataset.launchReadinessRefreshStatus === "pass" &&
	      launchReadinessRefresh.dataset.launchReadinessRefreshCommandCoverage === "6" &&
	      launchReadinessRefresh.dataset.launchReadinessRefreshWorkflowScopeAvailable === launchReadinessReceiptExpected.workflowScopeAvailable &&
	      launchReadinessRefresh.dataset.launchReadinessRefreshWorkflowScopeInstallBlocked === launchReadinessReceiptExpected.workflowScopeInstallBlocked &&
	      launchReadinessRefresh.dataset.launchReadinessRefreshRemoteFilesReady === launchReadinessReceiptExpected.remoteFilesReady &&
	      launchReadinessRefresh.dataset.launchReadinessRefreshRemoteVisible === launchReadinessReceiptExpected.remoteVisible &&
	      launchReadinessRefresh.dataset.launchReadinessRefreshAllDispatchReady === launchReadinessReceiptExpected.allDispatchReady &&
	      launchReadinessRefresh.dataset.launchReadinessRefreshSafeToDispatch === String(launchReadinessDispatchReady) &&
	      launchReadinessRefresh.dataset.launchReadinessRefreshReadyForExternalClaim === String(launchReadinessProofReady) &&
	      launchReadinessRefresh.dataset.launchReadinessRefreshWithheldCount === launchReadinessReceiptExpected.withheldCount &&
	      launchReadinessRefresh.dataset.launchReadinessRefreshSuggestedDispatchCount === launchReadinessReceiptExpected.suggestedDispatchCount &&
	      launchReadinessRefresh.dataset.launchReadinessRefreshActiveDispatchCount === launchReadinessReceiptExpected.activeDispatchCount &&
	      launchReadinessRefresh.dataset.launchReadinessRefreshReferenceDispatchCount === launchReadinessReceiptExpected.referenceDispatchCount &&
	      launchReadinessRefresh.dataset.launchReadinessRefreshDispatchCommandDisposition === launchReadinessReceiptExpected.dispatchDisposition &&
	      launchReadinessRefresh.dataset.launchReadinessRefreshNextAction === launchReadinessReceiptExpected.nextAction &&
	      launchReadinessRefresh.dataset.launchReadinessRefreshNextCommand.includes(launchReadinessReceiptExpected.nextCommandIncludes) &&
	      (launchReadinessProofReady || (launchReadinessRepairAction === "replace_existing_remote_file" && launchReadinessRepairCommand.includes("edit/main/.github/workflows/joopark-pages.yml") && launchReadinessRepairEditUrl.includes("edit/main/.github/workflows/joopark-pages.yml"))) &&
	      launchReadinessRefresh.dataset.launchReadinessRefreshAbDecision === "keep_b" &&
      launchReadinessRefresh.dataset.launchReadinessRefreshOutputQualityGateTraceability === "pass" &&
      launchReadinessRefresh.dataset.launchReadinessRefreshLatestGateStatus === "pass" &&
      Number(launchReadinessRefresh.dataset.launchReadinessRefreshLatestGatePass || 0) >= 230 &&
      Number(launchReadinessRefresh.dataset.launchReadinessRefreshLatestGateTotal || 0) >= Number(launchReadinessRefresh.dataset.launchReadinessRefreshLatestGatePass || 0) &&
      launchReadinessRefresh.dataset.launchReadinessRefreshOutputQualitySourceInputCount === "11" &&
      ["fresh", "stale"].includes(launchReadinessRefresh.dataset.launchReadinessRefreshFreshnessStatus) &&
      ["true", "false"].includes(launchReadinessRefresh.dataset.launchReadinessRefreshRefreshRequired) &&
      launchReadinessRefresh.dataset.launchReadinessRefreshMaxAgeHours === "24" &&
      launchReadinessRefresh.dataset.launchReadinessRefreshSourceArtifactCount === "6" &&
      launchReadinessSourceArtifactSync === "pass", "launch readiness refresh dataset was incomplete");
	    const launchReadinessRefreshText = launchReadinessRefresh.textContent || "";
	    const launchReadinessTextHasState = (key, value) => launchReadinessRefreshText.includes(key + "=" + value) || launchReadinessRefreshText.includes(key + ": " + value);
	    assert(launchReadinessRefreshText.includes("Launch readiness refresh") &&
	      launchReadinessRefreshText.includes("6 commands") &&
	      launchReadinessRefreshText.includes("freshness") &&
	      launchReadinessRefreshText.includes("workflow_ui_install_plan") &&
		      launchReadinessRefreshText.includes("keep_b") &&
		      launchReadinessRefreshText.includes("npm run verify ->") &&
		      launchReadinessRefreshText.includes("11 sources") &&
		      launchReadinessRefreshText.includes("source sync") &&
		      launchReadinessRefreshText.includes("pass") &&
		      launchReadinessTextHasState("workflowScopeInstallBlocked", launchReadinessReceiptExpected.workflowScopeInstallBlocked) &&
			      launchReadinessTextHasState("remoteWorkflowFilesReady", launchReadinessReceiptExpected.remoteFilesReady) &&
			      launchReadinessTextHasState("safeToDispatch", String(launchReadinessDispatchReady)) &&
			      launchReadinessTextHasState("readyForExternalClaim", String(launchReadinessProofReady)) &&
			      (launchReadinessProofReady || (launchReadinessRefreshText.includes("Remote workflow repair") && launchReadinessRefreshText.includes("replace_existing_remote_file") && launchReadinessRefreshText.includes("edit/main/.github/workflows/joopark-pages.yml"))) &&
			      launchReadinessRefreshText.includes(launchReadinessProofReady ? "not applicable after proof" : "verify-launch-handoff reports safeToDispatch=true") &&
		      launchReadinessRefreshText.includes(launchReadinessReceiptExpected.nextCommandIncludes) &&
		      launchReadinessRefreshText.includes("npm run refresh:launch-readiness"), "launch readiness refresh panel did not render");
    const launchReadinessReceipt = qs("[data-launch-readiness-refresh-receipt]", launchReadinessRefresh);
    assert(launchReadinessReceipt.dataset.launchReadinessRefreshReceiptCopyReady === "true", "launch readiness refresh receipt was not copy-ready");
    assert(qs("[data-launch-readiness-refresh-receipt-text]", launchReadinessReceipt).textContent.includes("JooPark Launch Readiness Refresh Receipt") &&
      qs("[data-launch-readiness-refresh-receipt-text]", launchReadinessReceipt).textContent.includes("commandCoverage: 6") &&
      qs("[data-launch-readiness-refresh-receipt-text]", launchReadinessReceipt).textContent.includes("A/B decision: keep_b") &&
      qs("[data-launch-readiness-refresh-receipt-text]", launchReadinessReceipt).textContent.includes("latestGate: npm run verify ->") &&
      qs("[data-launch-readiness-refresh-receipt-text]", launchReadinessReceipt).textContent.includes("0 fail, 0 not_run, 0 blocked") &&
	      qs("[data-launch-readiness-refresh-receipt-text]", launchReadinessReceipt).textContent.includes("outputQualitySourceInputCount: 11") &&
	      qs("[data-launch-readiness-refresh-receipt-text]", launchReadinessReceipt).textContent.includes("sourceArtifactSync: pass") &&
	      qs("[data-launch-readiness-refresh-receipt-text]", launchReadinessReceipt).textContent.includes("outputQualityGateTraceability: pass") &&
	      qs("[data-launch-readiness-refresh-receipt-text]", launchReadinessReceipt).textContent.includes("safeToDispatch: " + String(launchReadinessDispatchReady)) &&
	      qs("[data-launch-readiness-refresh-receipt-text]", launchReadinessReceipt).textContent.includes("readyForExternalClaim: " + String(launchReadinessProofReady)) &&
	      qs("[data-launch-readiness-refresh-receipt-text]", launchReadinessReceipt).textContent.includes("suggestedDispatchCommandCount: " + launchReadinessReceiptExpected.suggestedDispatchCount) &&
	      qs("[data-launch-readiness-refresh-receipt-text]", launchReadinessReceipt).textContent.includes("withheldDispatchCommandCount: " + launchReadinessReceiptExpected.withheldCount) &&
			      qs("[data-launch-readiness-refresh-receipt-text]", launchReadinessReceipt).textContent.includes("dispatchCommandDisposition: " + launchReadinessReceiptExpected.dispatchDisposition) &&
			      qs("[data-launch-readiness-refresh-receipt-text]", launchReadinessReceipt).textContent.includes("activeDispatchCommandCount: " + launchReadinessReceiptExpected.activeDispatchCount) &&
			      qs("[data-launch-readiness-refresh-receipt-text]", launchReadinessReceipt).textContent.includes("dispatchCommandReferenceCount: " + launchReadinessReceiptExpected.referenceDispatchCount) &&
			      (launchReadinessProofReady || (qs("[data-launch-readiness-refresh-receipt-text]", launchReadinessReceipt).textContent.includes("Remote Workflow Repair Action") && qs("[data-launch-readiness-refresh-receipt-text]", launchReadinessReceipt).textContent.includes("installAction: replace_existing_remote_file") && qs("[data-launch-readiness-refresh-receipt-text]", launchReadinessReceipt).textContent.includes("edit/main/.github/workflows/joopark-pages.yml"))) &&
			      qs("[data-launch-readiness-refresh-receipt-text]", launchReadinessReceipt).textContent.includes("every action_required refresh checklist item has passed") &&
		      qs("[data-launch-readiness-refresh-receipt-text]", launchReadinessReceipt).textContent.includes(launchReadinessReceiptExpected.nextCommandIncludes), "launch readiness refresh receipt text was incomplete");
    window.__smokeClipboardText = "";
    click("[data-launch-readiness-refresh-receipt-copy]", launchReadinessReceipt);
    await waitFor(() => launchReadinessReceipt.dataset.launchReadinessRefreshReceiptCopied === "true" && qs("[data-launch-readiness-refresh-receipt-copy-status]", launchReadinessReceipt).textContent.includes("복사"), "launch readiness refresh receipt copy did not report success");
    await waitFor(() => window.__smokeClipboardText.includes("JooPark Launch Readiness Refresh Receipt") &&
      window.__smokeClipboardText.includes("commandCoverage: 6") &&
      window.__smokeClipboardText.includes("A/B decision: keep_b") &&
      window.__smokeClipboardText.includes("latestGate: npm run verify ->") &&
      window.__smokeClipboardText.includes("0 fail, 0 not_run, 0 blocked") &&
	      window.__smokeClipboardText.includes("outputQualitySourceInputCount: 11") &&
	      window.__smokeClipboardText.includes("sourceArtifactSync: pass") &&
	      window.__smokeClipboardText.includes("outputQualityGateTraceability: pass") &&
	      window.__smokeClipboardText.includes("safeToDispatch: " + String(launchReadinessDispatchReady)) &&
	      window.__smokeClipboardText.includes("readyForExternalClaim: " + String(launchReadinessProofReady)) &&
	      window.__smokeClipboardText.includes("suggestedDispatchCommandCount: " + launchReadinessReceiptExpected.suggestedDispatchCount) &&
	      window.__smokeClipboardText.includes("withheldDispatchCommandCount: " + launchReadinessReceiptExpected.withheldCount) &&
	      window.__smokeClipboardText.includes("dispatchCommandDisposition: " + launchReadinessReceiptExpected.dispatchDisposition) &&
		      window.__smokeClipboardText.includes("activeDispatchCommandCount: " + launchReadinessReceiptExpected.activeDispatchCount) &&
			      window.__smokeClipboardText.includes("dispatchCommandReferenceCount: " + launchReadinessReceiptExpected.referenceDispatchCount) &&
			      window.__smokeClipboardText.includes("workflowScopeInstallBlocked: " + launchReadinessReceiptExpected.workflowScopeInstallBlocked) &&
			      window.__smokeClipboardText.includes("remoteWorkflowFilesReady: " + launchReadinessReceiptExpected.remoteFilesReady) &&
			      (launchReadinessProofReady || (window.__smokeClipboardText.includes("Remote Workflow Repair Action") && window.__smokeClipboardText.includes("installAction: replace_existing_remote_file") && window.__smokeClipboardText.includes("edit/main/.github/workflows/joopark-pages.yml"))) &&
			      window.__smokeClipboardText.includes("every action_required refresh checklist item has passed") &&
		      window.__smokeClipboardText.includes(launchReadinessReceiptExpected.nextCommandIncludes), "launch readiness refresh receipt copy text did not reach clipboard");
    launchReadinessRefreshOk = true;
    launchReadinessRefreshReceiptCopyOk = true;
    await waitFor(() => {
      const summaryPanel = document.querySelector("[data-system-verify-workspace-summary]");
      if (!summaryPanel) return false;
      if (strictVerifyWorkspaceSummary) return summaryPanel.dataset.verifyWorkspaceSummaryLoaded === "true";
      return summaryPanel.dataset.verifyWorkspaceSummarySource === "autoresearch-results/verify-workspace-summary.json" &&
        summaryPanel.dataset.verifyWorkspaceSummaryCommand === "npm run verify:full";
    }, strictVerifyWorkspaceSummary ? "verify workspace summary panel did not load" : "verify workspace summary panel did not render bootstrap state", 15000);
    panel = qs("[data-system-publish-readiness]");
    const verifyWorkspaceSummary = qs("[data-system-verify-workspace-summary]", panel);
    const verifyWorkspaceSummaryLoaded = verifyWorkspaceSummary.dataset.verifyWorkspaceSummaryLoaded === "true";
    if (verifyWorkspaceSummaryLoaded) {
      assert(verifyWorkspaceSummary.dataset.verifyWorkspaceSummarySource === "autoresearch-results/verify-workspace-summary.json" &&
        verifyWorkspaceSummary.dataset.verifyWorkspaceSummaryStatus === "pass" &&
        verifyWorkspaceSummary.dataset.verifyWorkspaceSummaryCommand === "npm run verify:full" &&
        verifyWorkspaceSummary.dataset.verifyWorkspaceSummarySyncArtifacts === "true" &&
        verifyWorkspaceSummary.dataset.verifyWorkspaceSummaryEvidenceSyncPass === "true" &&
        verifyWorkspaceSummary.dataset.verifyWorkspaceSummaryReleaseReadiness === "pass" &&
        verifyWorkspaceSummary.dataset.verifyWorkspaceSummaryLaunchReadiness === "pass" &&
        verifyWorkspaceSummary.dataset.verifyWorkspaceSummaryOutputQuality === "pass" &&
        verifyWorkspaceSummary.dataset.verifyWorkspaceSummaryEvidenceSync === "pass" &&
	        (verifyWorkspaceSummary.dataset.verifyWorkspaceSummaryLatestExperiment || "").length > 0 &&
	        verifyWorkspaceSummary.dataset.verifyWorkspaceSummaryStepCount === "3" &&
	        verifyWorkspaceSummary.dataset.verifyWorkspaceSummarySafeToDispatch === String(launchReadinessDispatchReady) &&
	        verifyWorkspaceSummary.dataset.verifyWorkspaceSummaryReadyForExternalClaim === String(launchReadinessProofReady) &&
	        verifyWorkspaceSummary.dataset.verifyWorkspaceSummaryDispatchCommandDisposition === launchReadinessReceiptExpected.dispatchDisposition &&
	        verifyWorkspaceSummary.dataset.verifyWorkspaceSummaryActiveDispatchCount === launchReadinessReceiptExpected.activeDispatchCount &&
	        verifyWorkspaceSummary.dataset.verifyWorkspaceSummaryReferenceDispatchCount === launchReadinessReceiptExpected.referenceDispatchCount, "verify workspace summary dataset was incomplete");
    } else {
      assert(!strictVerifyWorkspaceSummary &&
        verifyWorkspaceSummary.dataset.verifyWorkspaceSummarySource === "autoresearch-results/verify-workspace-summary.json" &&
        verifyWorkspaceSummary.dataset.verifyWorkspaceSummaryStatus !== "pass" &&
        verifyWorkspaceSummary.dataset.verifyWorkspaceSummaryCommand === "npm run verify:full" &&
        verifyWorkspaceSummary.dataset.verifyWorkspaceSummaryEvidenceSyncPass === "false" &&
        verifyWorkspaceSummary.dataset.verifyWorkspaceSummaryDirectionLoopSync === "false",
        "verify workspace summary bootstrap dataset was incomplete");
    }
    const verifyWorkspaceSummaryText = verifyWorkspaceSummary.textContent || "";
    const verifyWorkspaceNextCandidateTexts = qsa("[data-verify-workspace-summary-next-candidate]", verifyWorkspaceSummary)
      .map((item) => (item.textContent || "").trim())
      .filter(Boolean);
    const verifyWorkspaceExpectedCandidateCount = Number(verifyWorkspaceSummary.dataset.verifyWorkspaceSummaryNextCandidateCount || 0);
    const verifyWorkspaceCandidateListReady = verifyWorkspaceSummary.dataset.verifyWorkspaceSummaryNextCandidateList === "true" &&
      verifyWorkspaceExpectedCandidateCount > 0 &&
      verifyWorkspaceNextCandidateTexts.length === verifyWorkspaceExpectedCandidateCount;
    const verifyWorkspaceCandidateReceiptText = verifyWorkspaceNextCandidateTexts[0] || "";
    if (verifyWorkspaceSummaryLoaded) {
      const zeroFailureSummarySuffix = " pass, 0 fail, 0 not_run, 0 blocked";
      const zeroFailureSummaryCount = verifyWorkspaceSummaryText
        .split(zeroFailureSummarySuffix)
        .slice(0, -1)
        .map((prefix) => Number(prefix.trim().split(" ").pop()))
        .find((value) => Number.isFinite(value) && value > 0) || 0;
      const verifyWorkspaceSummaryPanelChecks = {
        title: verifyWorkspaceSummaryText.includes("Verify workspace summary"),
        command: verifyWorkspaceSummaryText.includes("npm run verify:full"),
        releaseStep: verifyWorkspaceSummaryText.includes("release_readiness_gates"),
        launchStep: verifyWorkspaceSummaryText.includes("launch_readiness_refresh"),
        productLoopStep: verifyWorkspaceSummaryText.includes("product_loop_summary_sync"),
        evidenceSync: verifyWorkspaceSummaryText.includes("evidenceSync"),
        latestExperiment: (verifyWorkspaceSummary.dataset.verifyWorkspaceSummaryLatestExperiment || "").length > 0 &&
          verifyWorkspaceSummaryText.includes(verifyWorkspaceSummary.dataset.verifyWorkspaceSummaryLatestExperiment),
        latestDirectionExperiment: (verifyWorkspaceSummary.dataset.verifyWorkspaceSummaryLatestDirectionExperiment || "").length > 0 &&
          verifyWorkspaceSummary.dataset.verifyWorkspaceSummaryLatestDirectionExperiment === verifyWorkspaceSummary.dataset.verifyWorkspaceSummaryLatestExperiment &&
          verifyWorkspaceSummary.dataset.verifyWorkspaceSummaryDirectionExperimentSync === "true" &&
          verifyWorkspaceSummaryText.includes(verifyWorkspaceSummary.dataset.verifyWorkspaceSummaryLatestDirectionExperiment),
        latestDiscoveryExperiment: verifyWorkspaceSummary.dataset.verifyWorkspaceSummaryLatestDiscoveryExperiment === "github-project-discovery-artifact" &&
          verifyWorkspaceSummary.dataset.verifyWorkspaceSummaryDiscoveryExperimentSync === "true" &&
          verifyWorkspaceSummaryText.includes(verifyWorkspaceSummary.dataset.verifyWorkspaceSummaryLatestDiscoveryExperiment),
		        directionLoop: verifyWorkspaceSummary.dataset.verifyWorkspaceSummaryDirectionLoopSync === "true" && verifyWorkspaceSummaryText.includes("direction"),
	        nextCandidates: verifyWorkspaceSummaryText.includes("next"),
	        nextCandidateList: verifyWorkspaceCandidateListReady &&
            verifyWorkspaceCandidateReceiptText &&
            verifyWorkspaceSummaryText.includes(verifyWorkspaceCandidateReceiptText),
	        zeroFailures: zeroFailureSummaryCount > 0,
	        externalClaimGuard: verifyWorkspaceSummaryText.includes("readyForExternalClaim"),
	        dispatchDisposition: verifyWorkspaceSummaryText.includes(launchReadinessProofReady ? "not applicable after proof" : launchReadinessReceiptExpected.dispatchDisposition),
	      };
      assert(Object.values(verifyWorkspaceSummaryPanelChecks).every(Boolean), "verify workspace summary panel did not render: " + JSON.stringify(verifyWorkspaceSummaryPanelChecks) + "; text=" + verifyWorkspaceSummaryText.slice(0, 480));
    } else {
      const verifyWorkspaceSummaryBootstrapChecks = {
        title: verifyWorkspaceSummaryText.includes("Verify workspace summary"),
        command: verifyWorkspaceSummaryText.includes("npm run verify:full"),
        status: verifyWorkspaceSummaryText.includes("missing") || verifyWorkspaceSummaryText.includes("fail") || verifyWorkspaceSummaryText.includes("not loaded"),
        evidenceSync: verifyWorkspaceSummaryText.includes("evidenceSync"),
      };
      assert(Object.values(verifyWorkspaceSummaryBootstrapChecks).every(Boolean), "verify workspace summary bootstrap panel did not render: " + JSON.stringify(verifyWorkspaceSummaryBootstrapChecks) + "; text=" + verifyWorkspaceSummaryText.slice(0, 480));
    }
    const verifyWorkspaceReceipt = qs("[data-verify-workspace-summary-receipt]", verifyWorkspaceSummary);
    const verifyWorkspaceReceiptText = qs("[data-verify-workspace-summary-receipt-text]", verifyWorkspaceReceipt).textContent;
    if (verifyWorkspaceSummaryLoaded) {
      assert(verifyWorkspaceReceipt.dataset.verifyWorkspaceSummaryReceiptCopyReady === "true" &&
        verifyWorkspaceReceiptText.includes("JooPark Verify Workspace Summary Receipt") &&
        verifyWorkspaceReceiptText.includes("command: npm run verify:full") &&
        verifyWorkspaceReceiptText.includes("evidenceSyncPass: true") &&
        verifyWorkspaceReceiptText.includes("releaseReadiness: pass") &&
        verifyWorkspaceReceiptText.includes("launchReadiness: pass") &&
        verifyWorkspaceReceiptText.includes("outputQuality: pass") &&
	        verifyWorkspaceReceiptText.includes("latestExperiment=" + verifyWorkspaceSummary.dataset.verifyWorkspaceSummaryLatestExperiment) &&
		        verifyWorkspaceReceiptText.includes("latestDirectionExperiment=" + verifyWorkspaceSummary.dataset.verifyWorkspaceSummaryLatestDirectionExperiment) &&
		        verifyWorkspaceReceiptText.includes("latestDiscoveryExperiment=" + verifyWorkspaceSummary.dataset.verifyWorkspaceSummaryLatestDiscoveryExperiment) &&
		        verifyWorkspaceReceiptText.includes("latestDirectionLoop=loop-") &&
		        verifyWorkspaceReceiptText.includes("directionLoop=true") &&
		        verifyWorkspaceReceiptText.includes("directionExperiment=true") &&
		        verifyWorkspaceReceiptText.includes("discoveryExperiment=true") &&
	        verifyWorkspaceReceiptText.includes("nextCandidates=true") &&
	        verifyWorkspaceReceiptText.includes("nextCandidateList=true") &&
	        verifyWorkspaceReceiptText.includes("nextCandidateCount: " + verifyWorkspaceSummary.dataset.verifyWorkspaceSummaryNextCandidateCount) &&
	        verifyWorkspaceReceiptText.includes(verifyWorkspaceCandidateReceiptText) &&
	        verifyWorkspaceReceiptText.includes("release_readiness_gates: pass") &&
	        verifyWorkspaceReceiptText.includes("product_loop_summary_sync: pass") &&
	        verifyWorkspaceReceiptText.includes("readyForExternalClaim: " + String(launchReadinessProofReady)) &&
	        verifyWorkspaceReceiptText.includes("dispatchCommandDisposition: " + launchReadinessReceiptExpected.dispatchDisposition) &&
	        verifyWorkspaceReceiptText.includes("activeDispatchCommandCount: " + launchReadinessReceiptExpected.activeDispatchCount) &&
	        verifyWorkspaceReceiptText.includes("dispatchCommandReferenceCount: " + launchReadinessReceiptExpected.referenceDispatchCount), "verify workspace summary receipt text was incomplete");
      window.__smokeClipboardText = "";
      click("[data-verify-workspace-summary-receipt-copy]", verifyWorkspaceReceipt);
      await waitFor(() => verifyWorkspaceReceipt.dataset.verifyWorkspaceSummaryReceiptCopied === "true" && qs("[data-verify-workspace-summary-receipt-copy-status]", verifyWorkspaceReceipt).textContent.includes("복사"), "verify workspace summary receipt copy did not report success");
      await waitFor(() => window.__smokeClipboardText.includes("JooPark Verify Workspace Summary Receipt") &&
        window.__smokeClipboardText.includes("command: npm run verify:full") &&
        window.__smokeClipboardText.includes("evidenceSyncPass: true") &&
		        window.__smokeClipboardText.includes("latestExperiment=" + verifyWorkspaceSummary.dataset.verifyWorkspaceSummaryLatestExperiment) &&
		        window.__smokeClipboardText.includes("latestDirectionExperiment=" + verifyWorkspaceSummary.dataset.verifyWorkspaceSummaryLatestDirectionExperiment) &&
		        window.__smokeClipboardText.includes("latestDiscoveryExperiment=" + verifyWorkspaceSummary.dataset.verifyWorkspaceSummaryLatestDiscoveryExperiment) &&
		        window.__smokeClipboardText.includes("directionLoop=true") &&
		        window.__smokeClipboardText.includes("directionExperiment=true") &&
		        window.__smokeClipboardText.includes("discoveryExperiment=true") &&
	        window.__smokeClipboardText.includes("nextCandidates=true") &&
	        window.__smokeClipboardText.includes("nextCandidateList=true") &&
	        window.__smokeClipboardText.includes(verifyWorkspaceCandidateReceiptText) &&
	        window.__smokeClipboardText.includes("release_readiness_gates: pass") &&
	        window.__smokeClipboardText.includes("readyForExternalClaim: " + String(launchReadinessProofReady)) &&
	        window.__smokeClipboardText.includes("dispatchCommandDisposition: " + launchReadinessReceiptExpected.dispatchDisposition) &&
	        window.__smokeClipboardText.includes("activeDispatchCommandCount: " + launchReadinessReceiptExpected.activeDispatchCount) &&
	        window.__smokeClipboardText.includes("dispatchCommandReferenceCount: " + launchReadinessReceiptExpected.referenceDispatchCount), "verify workspace summary receipt copy text did not reach clipboard");
    } else {
      assert(verifyWorkspaceReceipt.dataset.verifyWorkspaceSummaryReceiptCopyReady === "false" &&
        verifyWorkspaceReceiptText.includes("JooPark Verify Workspace Summary Receipt") &&
        verifyWorkspaceReceiptText.includes("command: npm run verify:full") &&
        verifyWorkspaceReceiptText.includes("evidenceSyncPass: false"), "verify workspace summary bootstrap receipt text was incomplete");
    }
    verifyWorkspaceSummaryOk = true;
    verifyWorkspaceSummaryReceiptCopyOk = true;
    await waitFor(() => document.querySelector("[data-system-release-gate-cache]")?.dataset.releaseGateCacheLoaded === "true", "release gate cache panel did not load", 15000);
    panel = qs("[data-system-publish-readiness]");
    const releaseGateCache = qs("[data-system-release-gate-cache]", panel);
    const releaseGateCacheHealthy = releaseGateCache.dataset.releaseGateCacheStatus === "pass" &&
      releaseGateCache.dataset.releaseGateCacheCached === "true" &&
      releaseGateCache.dataset.releaseGateCacheContextMatched === "true" &&
      releaseGateCache.dataset.releaseGateCacheReady === "true" &&
      releaseGateCache.dataset.releaseGateCacheCacheStatus === "valid" &&
      releaseGateCache.dataset.releaseGateCacheCachedEvidenceStatus === "pass" &&
      releaseGateCache.dataset.releaseGateCacheCachedResultStatus === "pass" &&
      releaseGateCache.dataset.releaseGateCacheNotRun === "0" &&
      releaseGateCache.dataset.releaseGateCacheIssueCount === "0" &&
      releaseGateCache.dataset.releaseGateCacheMismatchCount === "0";
    const releaseGateCacheRepairRequired = releaseGateCache.dataset.releaseGateCacheReady === "false" &&
      releaseGateCache.textContent.includes("repair required") &&
      (releaseGateCache.dataset.releaseGateCacheStatus !== "pass" ||
        releaseGateCache.dataset.releaseGateCacheContextMatched === "false" ||
        releaseGateCache.dataset.releaseGateCacheCacheStatus === "invalid" ||
        releaseGateCache.dataset.releaseGateCacheCachedEvidenceStatus !== "pass" ||
        releaseGateCache.dataset.releaseGateCacheCachedResultStatus !== "pass" ||
        Number(releaseGateCache.dataset.releaseGateCacheNotRun || 0) > 0 ||
        Number(releaseGateCache.dataset.releaseGateCacheIssueCount || 0) > 0 ||
        Number(releaseGateCache.dataset.releaseGateCacheMismatchCount || 0) > 0);
    assert(releaseGateCache.dataset.releaseGateCacheLoaded === "true" &&
      releaseGateCache.dataset.releaseGateCacheSource === "autoresearch-results/release-readiness-summary.json" &&
      releaseGateCache.dataset.releaseGateCacheRepairCommand === "npm test" &&
      releaseGateCache.dataset.releaseGateCacheRecheckCommand === "node scripts/audit-release-readiness.mjs --format=summary" &&
      releaseGateCache.dataset.releaseGateCacheCompletionAudit === "blocked_external_claim" &&
      releaseGateCache.dataset.releaseGateCacheLaunchCompletionAchieved === "false" &&
      releaseGateCache.dataset.releaseGateCacheReadyForExternalClaim === "false" &&
      releaseGateCache.dataset.releaseGateCacheCompletionBlockedSignals.includes("remoteWorkflowFilesReady=false") &&
      releaseGateCache.dataset.releaseGateCacheCompletionBlockedSignals.includes("readyForExternalClaim=false") &&
      (releaseGateCacheHealthy || releaseGateCacheRepairRequired), "release gate cache dataset was incomplete");
    const releaseGateCacheText = releaseGateCache.textContent || "";
    const releaseGateCacheRequiredTerms = [
      "Release gate cache",
      releaseGateCacheText.includes("cached pass") ? "cached pass" : "repair required",
      "packaged browser gate cache",
      "completion audit",
      "launchCompletionAchieved=false",
      "blocked signals",
      "remoteWorkflowFilesReady=false",
      "cachedEvidenceStatus",
      "cachedResultStatus",
      "contextMatched=false",
      "context_mismatch",
      "not_run",
      "npm test",
      "node scripts/audit-release-readiness.mjs --format=summary",
    ];
    const releaseGateCacheMissingTerms = releaseGateCacheRequiredTerms.filter((term) => !releaseGateCacheText.includes(term));
    assert(releaseGateCacheMissingTerms.length === 0, "release gate cache panel did not render: missing " + releaseGateCacheMissingTerms.join(", "));
    const releaseGateCacheReceipt = qs("[data-release-gate-cache-repair-receipt]", releaseGateCache);
    const releaseGateCacheReceiptText = qs("[data-release-gate-cache-repair-text]", releaseGateCacheReceipt).textContent;
    const releaseGateCacheContextMatched = releaseGateCache.dataset.releaseGateCacheContextMatched;
    assert(releaseGateCacheReceipt.dataset.releaseGateCacheRepairCopyReady === "true" &&
      releaseGateCacheReceiptText.includes("JooPark Release Gate Cache Repair") &&
      releaseGateCacheReceiptText.includes("contextMatched: " + releaseGateCacheContextMatched) &&
      releaseGateCacheReceiptText.includes("completionAudit: " + releaseGateCache.dataset.releaseGateCacheCompletionAudit) &&
      releaseGateCacheReceiptText.includes("launchCompletionAchieved: " + releaseGateCache.dataset.releaseGateCacheLaunchCompletionAchieved) &&
      releaseGateCacheReceiptText.includes("readyForExternalClaim: " + releaseGateCache.dataset.releaseGateCacheReadyForExternalClaim) &&
      releaseGateCacheReceiptText.includes("blockedSignals: " + releaseGateCache.dataset.releaseGateCacheCompletionBlockedSignals) &&
      releaseGateCacheReceiptText.includes("cachedEvidenceStatus: " + releaseGateCache.dataset.releaseGateCacheCachedEvidenceStatus) &&
      releaseGateCacheReceiptText.includes("cachedResultStatus: " + releaseGateCache.dataset.releaseGateCacheCachedResultStatus) &&
      releaseGateCacheReceiptText.includes("## Repair commands") &&
      releaseGateCacheReceiptText.includes("1. npm test") &&
      releaseGateCacheReceiptText.includes("2. node scripts/audit-release-readiness.mjs --format=summary") &&
      releaseGateCacheReceiptText.includes("cachedEvidenceStatus/cachedResultStatus is not pass") &&
      releaseGateCacheReceiptText.includes("Stop condition: do not rely on cached packaged browser gates"), "release gate cache repair receipt was incomplete");
    window.__smokeClipboardText = "";
    click("[data-release-gate-cache-repair-copy]", releaseGateCacheReceipt);
    await waitFor(() => releaseGateCacheReceipt.dataset.releaseGateCacheRepairCopied === "true" && qs("[data-release-gate-cache-repair-copy-status]", releaseGateCacheReceipt).textContent.includes("복사"), "release gate cache repair copy did not report success");
    await waitFor(() => window.__smokeClipboardText.includes("JooPark Release Gate Cache Repair") &&
      window.__smokeClipboardText.includes("summary:") &&
      window.__smokeClipboardText.includes("contextMatched: " + releaseGateCacheContextMatched) &&
      window.__smokeClipboardText.includes("completionAudit: " + releaseGateCache.dataset.releaseGateCacheCompletionAudit) &&
      window.__smokeClipboardText.includes("launchCompletionAchieved: " + releaseGateCache.dataset.releaseGateCacheLaunchCompletionAchieved) &&
      window.__smokeClipboardText.includes("readyForExternalClaim: " + releaseGateCache.dataset.releaseGateCacheReadyForExternalClaim) &&
      window.__smokeClipboardText.includes("blockedSignals: " + releaseGateCache.dataset.releaseGateCacheCompletionBlockedSignals) &&
      window.__smokeClipboardText.includes("cachedEvidenceStatus: " + releaseGateCache.dataset.releaseGateCacheCachedEvidenceStatus) &&
      window.__smokeClipboardText.includes("cachedResultStatus: " + releaseGateCache.dataset.releaseGateCacheCachedResultStatus) &&
      window.__smokeClipboardText.includes("1. npm test") &&
      window.__smokeClipboardText.includes("2. node scripts/audit-release-readiness.mjs --format=summary") &&
      window.__smokeClipboardText.includes("context_mismatch"), "release gate cache repair copy text did not reach clipboard");
    releaseGateCacheOk = true;
    releaseGateCacheRepairCopyOk = true;
    await waitFor(() => document.querySelector("[data-system-release-provenance]")?.dataset.releaseProvenanceLoaded === "true", "release provenance panel did not load", 15000);
    panel = qs("[data-system-publish-readiness]");
    const releaseProvenance = qs("[data-system-release-provenance]", panel);
    assert(releaseProvenance.dataset.releaseProvenanceLoaded === "true" &&
      releaseProvenance.dataset.releaseProvenanceStatementType === "https://in-toto.io/Statement/v1" &&
      releaseProvenance.dataset.releaseProvenancePredicateType === "https://slsa.dev/provenance/v1" &&
      releaseProvenance.dataset.releaseProvenanceSubject === "release-manifest.json" &&
      /^[0-9a-f]{64}$/.test(releaseProvenance.dataset.releaseProvenanceSubjectSha || "") &&
      releaseProvenance.dataset.releaseProvenanceBuildType === "https://biojuho.local/joopark/static-release/v1" &&
      releaseProvenance.dataset.releaseProvenanceBuilderId === "https://biojuho.local/joopark/local-release-packager" &&
      releaseProvenance.dataset.releaseProvenanceSourceCommit &&
      releaseProvenance.dataset.releaseProvenanceSourceBranch &&
      ["true", "false"].includes(releaseProvenance.dataset.releaseProvenanceSourceDirty || "") &&
      Number(releaseProvenance.dataset.releaseProvenanceRuntimeFileCount || 0) >= 60 &&
      Number(releaseProvenance.dataset.releaseProvenanceDependencyCount || 0) >= 40 &&
      releaseProvenance.dataset.releaseProvenanceSigned === "false" &&
      releaseProvenance.dataset.releaseProvenanceSignatureStatus === "unsigned-local-provenance" &&
      releaseProvenance.dataset.releaseProvenanceVerifyCommand === "node scripts/verify-release.mjs", "release provenance dataset was incomplete");
    assert(releaseProvenance.textContent.includes("Release provenance") &&
      releaseProvenance.textContent.includes("release-manifest.json") &&
      releaseProvenance.textContent.includes("https://slsa.dev/provenance/v1") &&
      releaseProvenance.textContent.includes("unsigned-local-provenance") &&
      releaseProvenance.textContent.includes("node scripts/verify-release.mjs") &&
      releaseProvenance.textContent.includes("npm run verify:full") &&
      releaseProvenance.textContent.includes("GitHub artifact attestations") &&
      releaseProvenance.textContent.includes("source-tree") &&
      releaseProvenance.textContent.includes("vendor"), "release provenance panel copy was incomplete");
    const releaseProvenanceDependencies = Array.from(releaseProvenance.querySelectorAll("[data-release-provenance-dependency]"));
    assert(releaseProvenanceDependencies.length === 6 &&
      releaseProvenanceDependencies.every((item) => item.dataset.releaseProvenanceDependencyPresent === "true") &&
      releaseProvenanceDependencies.some((item) => item.dataset.releaseProvenanceDependencyName === "source-tree") &&
      releaseProvenanceDependencies.some((item) => item.dataset.releaseProvenanceDependencyName === "vendor"), "release provenance dependency ledger was incomplete");
    const releaseProvenanceReceipt = qs("[data-release-provenance-receipt]", releaseProvenance);
    const releaseProvenanceReceiptText = qs("[data-release-provenance-receipt-text]", releaseProvenanceReceipt).textContent;
    assert(releaseProvenanceReceipt.dataset.releaseProvenanceReceiptCopyReady === "true" &&
      releaseProvenanceReceiptText.includes("JooPark Release Provenance Receipt") &&
      releaseProvenanceReceiptText.includes("statementType: https://in-toto.io/Statement/v1") &&
      releaseProvenanceReceiptText.includes("predicateType: https://slsa.dev/provenance/v1") &&
      releaseProvenanceReceiptText.includes("subject: release-manifest.json") &&
      releaseProvenanceReceiptText.includes("signed: false") &&
      releaseProvenanceReceiptText.includes("signatureStatus: unsigned-local-provenance") &&
      releaseProvenanceReceiptText.includes("Do not present it as a GitHub artifact attestation") &&
      releaseProvenanceReceiptText.includes("Verify command: node scripts/verify-release.mjs"), "release provenance receipt text was incomplete");
    window.__smokeClipboardText = "";
    click("[data-release-provenance-receipt-copy]", releaseProvenanceReceipt);
    await waitFor(() => releaseProvenance.dataset.releaseProvenanceReceiptCopied === "true" && qs("[data-release-provenance-receipt-copy-status]", releaseProvenanceReceipt).textContent.includes("복사"), "release provenance receipt copy did not report success");
    await waitFor(() => window.__smokeClipboardText.includes("JooPark Release Provenance Receipt") &&
      window.__smokeClipboardText.includes("subjectSha256: " + releaseProvenance.dataset.releaseProvenanceSubjectSha) &&
      window.__smokeClipboardText.includes("resolvedDependencies: " + releaseProvenance.dataset.releaseProvenanceDependencyCount) &&
      window.__smokeClipboardText.includes("signed: false") &&
      window.__smokeClipboardText.includes("unsigned-local-provenance") &&
      window.__smokeClipboardText.includes("Do not present it as a GitHub artifact attestation") &&
      window.__smokeClipboardText.includes("Full gate: npm run verify:full"), "release provenance receipt copy text did not reach clipboard");
    releaseProvenancePanelOk = true;
    releaseProvenanceReceiptCopyOk = true;
    const attestationIntake = qs("[data-system-pages-attestation-proof-intake]", panel);
    assert(attestationIntake.dataset.pagesAttestationProofIntakeReady === "false" &&
      attestationIntake.dataset.pagesAttestationProofIntakeCopyReady === "true" &&
      attestationIntake.dataset.pagesAttestationProofIntakeVerificationOnly === "true" &&
      attestationIntake.dataset.pagesAttestationProofIntakeRepo === "biojuho/BIOJUHO-Projects" &&
      attestationIntake.dataset.pagesAttestationProofIntakeWorkflow === "joopark-pages.yml" &&
      attestationIntake.dataset.pagesAttestationProofIntakeAction === "actions/attest@v4" &&
      attestationIntake.dataset.pagesAttestationProofIntakeSubjectPath === "dist/release/**" &&
      attestationIntake.dataset.pagesAttestationProofIntakeRequiredPermission === "attestations: write" &&
      attestationIntake.dataset.pagesAttestationProofIntakeFieldCount === "6" &&
      attestationIntake.dataset.pagesAttestationProofIntakeCommandCount === "3" &&
      ["true", "false"].includes(attestationIntake.dataset.pagesAttestationProofIntakeRemoteWorkflowVisible || "") &&
      ["true", "false"].includes(attestationIntake.dataset.pagesAttestationProofIntakeAllDispatchReady || "") &&
      attestationIntake.dataset.pagesAttestationProofIntakeManifestVerifyCommand.includes("gh attestation verify dist/release/release-manifest.json -R biojuho/BIOJUHO-Projects") &&
      attestationIntake.dataset.pagesAttestationProofIntakeIndexVerifyCommand.includes("gh attestation verify dist/release/index.html -R biojuho/BIOJUHO-Projects"), "pages attestation proof intake dataset was incomplete");
    assert(attestationIntake.textContent.includes("Pages attestation proof intake") &&
      attestationIntake.textContent.includes("attestation-url") &&
      attestationIntake.textContent.includes("attestation-id") &&
      attestationIntake.textContent.includes("gh attestation verify") &&
      attestationIntake.textContent.includes("dist/release/**") &&
      attestationIntake.textContent.includes("not signed proof yet") &&
      attestationIntake.textContent.includes("Do not claim signed GitHub artifact attestation proof"), "pages attestation proof intake panel did not render");
    const attestationFields = Array.from(attestationIntake.querySelectorAll("[data-pages-attestation-proof-field]"));
    assert(attestationFields.length === 6 &&
      attestationFields.some((field) => field.dataset.pagesAttestationProofFieldKey === "pages_workflow_run") &&
      attestationFields.some((field) => field.dataset.pagesAttestationProofFieldKey === "attestation_url") &&
      attestationFields.some((field) => field.dataset.pagesAttestationProofFieldKey === "attestation_id") &&
      attestationFields.some((field) => field.dataset.pagesAttestationProofFieldKey === "manifest_verify") &&
      attestationFields.some((field) => field.dataset.pagesAttestationProofFieldKey === "index_verify") &&
      attestationFields.some((field) => field.dataset.pagesAttestationProofFieldKey === "predicate_type"), "pages attestation proof fields were incomplete");
    const attestationReceipt = qs("[data-pages-attestation-proof-intake-receipt]", attestationIntake);
    const attestationReceiptText = qs("[data-pages-attestation-proof-intake-receipt-text]", attestationReceipt).textContent;
    assert(attestationReceipt.dataset.pagesAttestationProofIntakeReceiptCopyReady === "true" &&
      attestationReceiptText.includes("JooPark Pages Attestation Proof Intake") &&
      attestationReceiptText.includes("Status: proof intake ready; not signed proof yet") &&
      attestationReceiptText.includes("Repo: biojuho/BIOJUHO-Projects") &&
      attestationReceiptText.includes("attestation-url") &&
      attestationReceiptText.includes("attestation-id") &&
      attestationReceiptText.includes("gh run list --repo biojuho/BIOJUHO-Projects --workflow joopark-pages.yml") &&
      attestationReceiptText.includes("gh attestation verify dist/release/release-manifest.json -R biojuho/BIOJUHO-Projects") &&
      attestationReceiptText.includes("gh attestation verify dist/release/index.html -R biojuho/BIOJUHO-Projects") &&
      attestationReceiptText.includes("Do not claim signed GitHub artifact attestation proof"), "pages attestation proof intake receipt text was incomplete");
    window.__smokeClipboardText = "";
    click("[data-pages-attestation-proof-intake-copy]", attestationReceipt);
    await waitFor(() => attestationIntake.dataset.pagesAttestationProofIntakeCopied === "true" && qs("[data-pages-attestation-proof-intake-copy-status]", attestationReceipt).textContent.includes("복사"), "pages attestation proof intake copy did not report success");
    await waitFor(() => window.__smokeClipboardText.includes("JooPark Pages Attestation Proof Intake") &&
      window.__smokeClipboardText.includes("attestation_url") &&
      window.__smokeClipboardText.includes("attestation_id") &&
      window.__smokeClipboardText.includes("manifest_verify") &&
      window.__smokeClipboardText.includes("index_verify") &&
      window.__smokeClipboardText.includes("predicate_type") &&
      window.__smokeClipboardText.includes("proof intake ready; not signed proof yet") &&
      window.__smokeClipboardText.includes("gh attestation verify dist/release/release-manifest.json -R biojuho/BIOJUHO-Projects") &&
      window.__smokeClipboardText.includes("Do not claim signed GitHub artifact attestation proof"), "pages attestation proof intake copy text did not reach clipboard");
    pagesAttestationProofIntakeOk = true;
    pagesAttestationProofIntakeCopyOk = true;
	    if (!sourceSnapshotHealthOk || !githubProjectDiscoveryOk) assertSystemSourceInventory();
	    await waitFor(() => document.querySelector("[data-system-publish-evidence]")?.dataset.publishEvidenceLoaded === "true", "publish evidence panel did not load", 15000);
    panel = qs("[data-system-publish-readiness]");
    const evidence = qs("[data-system-publish-evidence]", panel);
    assert(evidence.dataset.publishEvidenceSource === "data/publish-evidence.json" && evidence.dataset.publishEvidenceLoaded === "true" && evidence.dataset.publishEvidenceReady === "false", "publish evidence file state was not surfaced");
    assert(["true", "false"].includes(evidence.dataset.publishEvidenceFresh || ""), "publish evidence freshness state was not surfaced");
    assert(evidence.dataset.publishEvidenceSuggestedRepo === "biojuho/BIOJUHO-Projects", "publish evidence suggested repo was not surfaced");
    const expectedSourceEvidenceRepoLine = "Evidence repo: biojuho/BIOJUHO-Projects";
    const expectedEvidenceRepoLine = "Evidence repo: " + evidence.dataset.publishEvidenceEvidenceRepo + (evidence.dataset.publishEvidenceRepoPlaceholderResolved === "true" ? " (placeholder resolved from suggestedRepo)" : "");
    const expectedRepoResolutionLine = "Repo resolution: " + evidence.dataset.publishEvidenceRepoResolution;
    const expectedRepoEvidenceReadyLine = "repoEvidenceReady: " + evidence.dataset.publishEvidenceRepoReady;
    assert(expectedEvidenceRepoLine === expectedSourceEvidenceRepoLine && expectedRepoResolutionLine === "Repo resolution: source_repo", "publish evidence source repo line changed");
    const oldEvidenceGeneratedAt = new Date(Date.now() - 49 * 60 * 60 * 1000).toISOString();
    const freshEvidenceGeneratedAt = new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString();
    const freshnessHelperOk = publishEvidenceFresh({ generatedAt: oldEvidenceGeneratedAt, evidenceMaxAgeHours: 24 }) === false &&
      publishEvidenceFresh({ generatedAt: freshEvidenceGeneratedAt, evidenceMaxAgeHours: 24 }) === true;
    assert(freshnessHelperOk, "publish evidence freshness helper did not expire stale evidence");
    assert(evidence.dataset.publishEvidenceMode === "live" && evidence.dataset.publishEvidenceRepoReady === "true" && evidence.dataset.publishEvidenceEvidenceRepo === "biojuho/BIOJUHO-Projects" && evidence.dataset.publishEvidenceRepoResolution === "source_repo" && evidence.dataset.publishEvidenceRepoPlaceholderResolved === "false" && ["true", "false"].includes(evidence.dataset.publishEvidencePagesReady || "") && ["true", "false"].includes(evidence.dataset.publishEvidenceWorkflowsReady || "") && evidence.dataset.publishEvidenceLaunchProofReady === "false", "publish evidence live action-required readiness state was not surfaced");
    const publishEvidenceImmediateCommand = evidence.dataset.publishEvidenceImmediateCommand || "";
    const publishEvidenceImmediateCommandAllowed = publishEvidenceImmediateCommand.includes("gh auth refresh -h github.com -s workflow") || publishEvidenceImmediateCommand.includes("pbcopy < 'docs/github-pages-workflow.yml'") || publishEvidenceImmediateCommand.includes("check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write");
    assert(evidence.dataset.publishEvidenceNextAction === "install_workflows" && publishEvidenceImmediateCommandAllowed, "publish evidence next action was not surfaced");
    assert(evidence.dataset.publishEvidenceImmediateAction === "install_workflows" && evidence.dataset.publishEvidenceImmediateActionStatus === "action_required" && evidence.dataset.publishEvidenceImmediateActionSource === "data/launch-execution-packet.json" && publishEvidenceImmediateCommandAllowed && Number(evidence.dataset.publishEvidenceImmediateCommandCount || "0") >= 2 && evidence.dataset.publishEvidenceImmediateWithheldCommandCount === "2" && evidence.dataset.publishEvidenceInstallPathsReady === "true" && evidence.dataset.publishEvidenceInstallPathCount === "2" && Number(evidence.dataset.publishEvidenceInstallPathCommandCount || "0") >= 10 && evidence.dataset.publishEvidenceDeferredAction === "capture-live-evidence" && evidence.dataset.publishEvidenceDeferredCommand.includes("capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --markdown"), "publish evidence immediate next action was not surfaced");
    const publishEvidenceSourceRepoContext = evidence.dataset.publishEvidenceEvidenceRepo === "biojuho/BIOJUHO-Projects" && evidence.dataset.publishEvidenceRepoResolution === "source_repo" && evidence.dataset.publishEvidenceRepoPlaceholderResolved === "false";
    assert(evidence.dataset.publishEvidenceDisplayRepo === "biojuho/BIOJUHO-Projects" && publishEvidenceSourceRepoContext, "publish evidence repo context was not resolved");
    assert(evidence.dataset.publishEvidenceDispatchReady === "false" && evidence.dataset.publishEvidenceDispatchSuggestionStatus === "withheld-until-all-dispatch-ready" && evidence.dataset.publishEvidenceSuggestedCommandsSafe === "true" && evidence.dataset.publishEvidenceSuggestedDispatchCount === "0" && evidence.dataset.publishEvidenceWithheldDispatchCount === "2", "publish evidence dispatch command guard state was not surfaced");
    const publishEvidenceStateLabel = qs("[data-publish-evidence-state-label]", evidence).textContent;
    assert(publishEvidenceStateLabel.includes("action required") || publishEvidenceStateLabel.includes("external claim guarded") || publishEvidenceStateLabel.includes("dry-run evidence"), "publish evidence state label did not distinguish blocked live evidence");
    const nextActionCardText = qs("[data-publish-evidence-next-action-card]", evidence).textContent;
    const nextActionCardRequiredTerms = [
      "Immediate action",
      "Install workflows on the default branch",
      "Success condition: remoteWorkflowFilesReady=true",
      publishEvidenceImmediateCommand,
      "Choose one install path",
      "CLI path after workflow scope",
      "GitHub UI path",
      "node scripts/install-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write --verify",
      "pbcopy < 'docs/github-pages-workflow.yml'",
      "Deferred evidence capture",
      "Capture live publish evidence",
      "capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --markdown",
    ].filter(Boolean);
    const missingNextActionCardTerms = nextActionCardRequiredTerms.filter((term) => !nextActionCardText.includes(term));
    assert(missingNextActionCardTerms.length === 0, "publish evidence next action card did not render immediate and deferred actions: " + missingNextActionCardTerms.join(", "));
    const commandGuardText = qs("[data-publish-evidence-command-guard]", evidence).textContent;
    const suggestedEvidenceCommandsText = qs("[data-publish-evidence-suggested-commands]", evidence).textContent;
    const withheldEvidenceDispatchText = qs("[data-publish-evidence-withheld-dispatch-commands]", evidence).textContent;
    assert(commandGuardText.includes("Dispatch command guard") && commandGuardText.includes("dispatch commands withheld") && commandGuardText.includes("withheld-until-all-dispatch-ready"), "publish evidence dispatch command guard did not render");
    assert(suggestedEvidenceCommandsText.includes("Suggested repo commands") && suggestedEvidenceCommandsText.includes("plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects") && suggestedEvidenceCommandsText.includes("capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --markdown") && suggestedEvidenceCommandsText.includes("gh run list --repo biojuho/BIOJUHO-Projects --workflow joopark-pages.yml") && !suggestedEvidenceCommandsText.includes("gh workflow run --repo"), "publish evidence suggested commands should stay verification-only before allDispatchReady");
    assert(withheldEvidenceDispatchText.includes("Withheld dispatch commands") && withheldEvidenceDispatchText.includes("gh workflow run --repo biojuho/BIOJUHO-Projects joopark-pages.yml -f ref=codex/joopark-workspace-release") && withheldEvidenceDispatchText.includes("gh workflow run --repo biojuho/BIOJUHO-Projects joopark-drift-watch.yml -f mode=advisory"), "publish evidence withheld dispatch commands were not surfaced");
    const evidenceTerms = ["postPublishEvidenceReady", "repoEvidenceReady", "suggestedRepo", "biojuho/BIOJUHO-Projects", "repoReplacementHint", "pagesEvidenceReady", "workflowEvidenceReady", "evidenceFresh", "launchProofReady", "launch proof", "evidenceMaxAgeHours", "expires", "freshness window", "nextAction", "immediateNextAction", "install_workflows", "Immediate action", "Deferred evidence capture", "capture-live-evidence", "Choose one install path", "CLI path after workflow scope", "GitHub UI path", "install-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write --verify", "joopark-pages.yml", "joopark-drift-watch.yml", "repo-scoped workflow run", "capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --markdown", "--write", "Withheld dispatch commands", "Do not run dispatch until allDispatchReady: true."];
    const missingEvidenceTerms = evidenceTerms.filter((term) => !evidence.textContent.includes(term));
    assert(missingEvidenceTerms.length === 0, "publish evidence panel did not expose persisted evidence commands: " + missingEvidenceTerms.join(", "));
    const shareUpdate = qs("[data-publish-evidence-share-update]", evidence);
    await waitFor(() => {
      const shareUpdateText = qs("[data-publish-evidence-share-update-text]", shareUpdate).textContent;
      return evidence.dataset.publishEvidenceShareUpdateReady === "true" && shareUpdateText.includes("JooPark Publish Evidence Update") && shareUpdateText.includes("Status: action required") && shareUpdateText.includes("Repo: biojuho/BIOJUHO-Projects") && shareUpdateText.includes(expectedEvidenceRepoLine) && shareUpdateText.includes(expectedRepoResolutionLine) && !shareUpdateText.includes("\\nRepo: OWNER/REPO") && shareUpdateText.includes("Suggested repo: biojuho/BIOJUHO-Projects") && shareUpdateText.includes("postPublishEvidenceReady:") && shareUpdateText.includes("Dispatch guard: withheld (withheld-until-all-dispatch-ready)") && shareUpdateText.includes("Suggested commands safe: true; suggested dispatch: 0; withheld dispatch: 2") && shareUpdateText.includes("dispatchCommandDisposition: withheld_until_all_dispatch_ready") && shareUpdateText.includes("activeDispatchCommandCount: 0") && shareUpdateText.includes("dispatchCommandReferenceCount: 2") && shareUpdateText.includes("Do not run dispatch until allDispatchReady: true.") && shareUpdateText.includes("Withheld dispatch commands:") && shareUpdateText.includes("gh workflow run --repo biojuho/BIOJUHO-Projects joopark-pages.yml -f ref=codex/joopark-workspace-release") && shareUpdateText.includes("gh workflow run --repo biojuho/BIOJUHO-Projects joopark-drift-watch.yml -f mode=advisory") && shareUpdateText.includes("Immediate action: Install workflows on the default branch [action_required]") && shareUpdateText.includes("Immediate command:") && shareUpdateText.includes("Immediate command count:") && shareUpdateText.includes("Immediate success condition: remoteWorkflowFilesReady=true") && shareUpdateText.includes("Choose one install path:") && shareUpdateText.includes("Launch install path options: pass (2 paths,") && shareUpdateText.includes("node scripts/install-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write --verify") && shareUpdateText.includes("pbcopy < 'docs/github-pages-workflow.yml'") && shareUpdateText.includes("Deferred evidence capture:") && shareUpdateText.includes("Deferred command: node scripts/capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --markdown");
    }, "publish evidence share update was not copy-ready", 15000);
    window.__smokeClipboardText = "";
    click("[data-publish-evidence-share-update-copy]", evidence);
    await waitFor(() => shareUpdate.dataset.publishEvidenceShareUpdateCopied === "true" && qs("[data-publish-evidence-share-update-copy-status]", shareUpdate).textContent.includes("복사"), "publish evidence share update copy did not report success");
    await waitFor(() => window.__smokeClipboardText.includes("JooPark Publish Evidence Update") && window.__smokeClipboardText.includes("Status: action required") && window.__smokeClipboardText.includes("Repo: biojuho/BIOJUHO-Projects") && window.__smokeClipboardText.includes(expectedEvidenceRepoLine) && !window.__smokeClipboardText.includes("\\nRepo: OWNER/REPO") && window.__smokeClipboardText.includes("Deferred evidence capture:") && window.__smokeClipboardText.includes("Dispatch guard: withheld (withheld-until-all-dispatch-ready)") && window.__smokeClipboardText.includes("dispatchCommandDisposition: withheld_until_all_dispatch_ready") && window.__smokeClipboardText.includes("activeDispatchCommandCount: 0") && window.__smokeClipboardText.includes("dispatchCommandReferenceCount: 2") && window.__smokeClipboardText.includes("Do not run dispatch until allDispatchReady: true.") && window.__smokeClipboardText.includes("Withheld dispatch commands:") && window.__smokeClipboardText.includes("gh workflow run --repo biojuho/BIOJUHO-Projects joopark-pages.yml -f ref=codex/joopark-workspace-release") && window.__smokeClipboardText.includes("gh workflow run --repo biojuho/BIOJUHO-Projects joopark-drift-watch.yml -f mode=advisory") && window.__smokeClipboardText.includes("Immediate action: Install workflows on the default branch [action_required]") && window.__smokeClipboardText.includes("Immediate command:") && window.__smokeClipboardText.includes("Choose one install path:") && window.__smokeClipboardText.includes("CLI path after workflow scope") && window.__smokeClipboardText.includes("GitHub UI path") && window.__smokeClipboardText.includes("node scripts/install-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write --verify") && window.__smokeClipboardText.includes("pbcopy < 'docs/github-pages-workflow.yml'") && window.__smokeClipboardText.includes("Deferred command: node scripts/capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --markdown"), "publish evidence share update copy text did not reach clipboard");
    publishEvidenceShareUpdateOk = true;
    const launchAnnouncement = qs("[data-publish-evidence-launch-announcement]", evidence);
    await waitFor(() => {
      const launchAnnouncementText = qs("[data-publish-evidence-launch-announcement-text]", launchAnnouncement).textContent;
      return evidence.dataset.publishEvidenceLaunchAnnouncementReady === "true" && launchAnnouncementText.includes("JooPark Public Launch Announcement") && launchAnnouncementText.includes("Status: not ready for public posting") && launchAnnouncementText.includes("Repo: biojuho/BIOJUHO-Projects") && launchAnnouncementText.includes(expectedEvidenceRepoLine) && !launchAnnouncementText.includes("\\nRepo: OWNER/REPO") && launchAnnouncementText.includes("External claim guard:") && launchAnnouncementText.includes("readyForExternalClaim: false") && launchAnnouncementText.includes("Dispatch gate:") && launchAnnouncementText.includes("Dispatch guard: withheld (withheld-until-all-dispatch-ready)") && launchAnnouncementText.includes("Suggested commands safe: true; suggested dispatch: 0; withheld dispatch: 2") && launchAnnouncementText.includes("Do not post or dispatch until allDispatchReady: true, postPublishEvidenceReady: true, and readyForExternalClaim: true.") && launchAnnouncementText.includes("Immediate action: Install workflows on the default branch [action_required]") && launchAnnouncementText.includes("Immediate command:") && launchAnnouncementText.includes("Choose one install path:") && launchAnnouncementText.includes("CLI path after workflow scope") && launchAnnouncementText.includes("GitHub UI path") && launchAnnouncementText.includes("node scripts/install-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write --verify") && launchAnnouncementText.includes("pbcopy < 'docs/github-pages-workflow.yml'") && launchAnnouncementText.includes("Deferred evidence capture:") && !launchAnnouncementText.includes("gh workflow run --repo") && launchAnnouncementText.includes("Do not post a public launch announcement") && launchAnnouncementText.includes("repoEvidenceReady, evidenceFresh, postPublishEvidenceReady");
    }, "publish launch announcement guard was not copy-ready", 15000);
    window.__smokeClipboardText = "";
    click("[data-publish-evidence-launch-announcement-copy]", evidence);
    await waitFor(() => launchAnnouncement.dataset.publishLaunchAnnouncementCopied === "true" && qs("[data-publish-evidence-launch-announcement-copy-status]", launchAnnouncement).textContent.includes("복사"), "publish launch announcement copy did not report success");
    await waitFor(() => window.__smokeClipboardText.includes("JooPark Public Launch Announcement") && window.__smokeClipboardText.includes("Status: not ready for public posting") && window.__smokeClipboardText.includes("Repo: biojuho/BIOJUHO-Projects") && window.__smokeClipboardText.includes(expectedEvidenceRepoLine) && !window.__smokeClipboardText.includes("\\nRepo: OWNER/REPO") && window.__smokeClipboardText.includes("External claim guard:") && window.__smokeClipboardText.includes("readyForExternalClaim: false") && window.__smokeClipboardText.includes("Deferred evidence capture:") && window.__smokeClipboardText.includes("Dispatch gate:") && window.__smokeClipboardText.includes("Dispatch guard: withheld (withheld-until-all-dispatch-ready)") && window.__smokeClipboardText.includes("Do not post or dispatch until allDispatchReady: true, postPublishEvidenceReady: true, and readyForExternalClaim: true.") && window.__smokeClipboardText.includes("Immediate action: Install workflows on the default branch [action_required]") && window.__smokeClipboardText.includes("Immediate command:") && window.__smokeClipboardText.includes("Choose one install path:") && window.__smokeClipboardText.includes("CLI path after workflow scope") && window.__smokeClipboardText.includes("GitHub UI path") && window.__smokeClipboardText.includes("node scripts/install-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write --verify") && window.__smokeClipboardText.includes("pbcopy < 'docs/github-pages-workflow.yml'") && !window.__smokeClipboardText.includes("gh workflow run --repo") && window.__smokeClipboardText.includes("Do not post a public launch announcement until repoEvidenceReady, evidenceFresh, postPublishEvidenceReady"), "publish launch announcement copy text did not reach clipboard");
    publishLaunchAnnouncementOk = true;
    const postLaunchReceipt = qs("[data-publish-evidence-post-launch-receipt]", evidence);
    await waitFor(() => {
      const postLaunchReceiptText = qs("[data-publish-evidence-post-launch-receipt-text]", postLaunchReceipt).textContent;
      return evidence.dataset.publishEvidencePostLaunchReceiptReady === "true" && postLaunchReceiptText.includes("JooPark Post-Launch Verification Receipt") && (postLaunchReceiptText.includes("Status: not ready to archive") || postLaunchReceiptText.includes("Status: not verified for archive")) && postLaunchReceiptText.includes("Repo: biojuho/BIOJUHO-Projects") && postLaunchReceiptText.includes(expectedEvidenceRepoLine) && !postLaunchReceiptText.includes("\\nRepo: OWNER/REPO") && postLaunchReceiptText.includes("Verification checklist:") && postLaunchReceiptText.includes(expectedRepoEvidenceReadyLine) && postLaunchReceiptText.includes("pagesEvidenceReady:") && postLaunchReceiptText.includes("workflowEvidenceReady:") && postLaunchReceiptText.includes("postPublishEvidenceReady:") && postLaunchReceiptText.includes("readyForExternalClaim: false") && postLaunchReceiptText.includes("External claim guard:") && postLaunchReceiptText.includes("publishDispatchReady: false") && postLaunchReceiptText.includes("dispatchSuggestionStatus: withheld-until-all-dispatch-ready") && postLaunchReceiptText.includes("Dispatch guard: withheld (withheld-until-all-dispatch-ready)") && postLaunchReceiptText.includes("Suggested commands safe: true; suggested dispatch: 0; withheld dispatch: 2") && postLaunchReceiptText.includes("dispatchCommandDisposition: withheld_until_all_dispatch_ready") && postLaunchReceiptText.includes("activeDispatchCommandCount: 0") && postLaunchReceiptText.includes("dispatchCommandReferenceCount: 2") && postLaunchReceiptText.includes("Do not run dispatch until allDispatchReady: true.") && postLaunchReceiptText.includes("Withheld dispatch commands:") && postLaunchReceiptText.includes("gh workflow run --repo biojuho/BIOJUHO-Projects joopark-pages.yml -f ref=codex/joopark-workspace-release") && postLaunchReceiptText.includes("gh workflow run --repo biojuho/BIOJUHO-Projects joopark-drift-watch.yml -f mode=advisory") && postLaunchReceiptText.includes("Immediate action: Install workflows on the default branch [action_required]") && postLaunchReceiptText.includes("Immediate command:") && postLaunchReceiptText.includes("Choose one install path:") && postLaunchReceiptText.includes("CLI path after workflow scope") && postLaunchReceiptText.includes("GitHub UI path") && postLaunchReceiptText.includes("node scripts/install-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write --verify") && postLaunchReceiptText.includes("pbcopy < 'docs/github-pages-workflow.yml'") && postLaunchReceiptText.includes("Deferred evidence capture:") && postLaunchReceiptText.includes("Do not archive this as post-launch verification");
    }, "publish post-launch receipt guard was not copy-ready", 15000);
    window.__smokeClipboardText = "";
    click("[data-publish-evidence-post-launch-receipt-copy]", evidence);
    await waitFor(() => postLaunchReceipt.dataset.publishPostLaunchReceiptCopied === "true" && qs("[data-publish-evidence-post-launch-receipt-copy-status]", postLaunchReceipt).textContent.includes("복사"), "publish post-launch receipt copy did not report success");
    await waitFor(() => window.__smokeClipboardText.includes("JooPark Post-Launch Verification Receipt") && (window.__smokeClipboardText.includes("Status: not ready to archive") || window.__smokeClipboardText.includes("Status: not verified for archive")) && window.__smokeClipboardText.includes("Repo: biojuho/BIOJUHO-Projects") && window.__smokeClipboardText.includes(expectedEvidenceRepoLine) && !window.__smokeClipboardText.includes("\\nRepo: OWNER/REPO") && window.__smokeClipboardText.includes("External claim guard:") && window.__smokeClipboardText.includes("readyForExternalClaim: false") && window.__smokeClipboardText.includes("Deferred evidence capture:") && window.__smokeClipboardText.includes("publishDispatchReady: false") && window.__smokeClipboardText.includes("dispatchSuggestionStatus: withheld-until-all-dispatch-ready") && window.__smokeClipboardText.includes("Dispatch guard: withheld (withheld-until-all-dispatch-ready)") && window.__smokeClipboardText.includes("dispatchCommandDisposition: withheld_until_all_dispatch_ready") && window.__smokeClipboardText.includes("activeDispatchCommandCount: 0") && window.__smokeClipboardText.includes("dispatchCommandReferenceCount: 2") && window.__smokeClipboardText.includes("Do not run dispatch until allDispatchReady: true.") && window.__smokeClipboardText.includes("Withheld dispatch commands:") && window.__smokeClipboardText.includes("gh workflow run --repo biojuho/BIOJUHO-Projects joopark-pages.yml -f ref=codex/joopark-workspace-release") && window.__smokeClipboardText.includes("gh workflow run --repo biojuho/BIOJUHO-Projects joopark-drift-watch.yml -f mode=advisory") && window.__smokeClipboardText.includes("Immediate action: Install workflows on the default branch [action_required]") && window.__smokeClipboardText.includes("Immediate command:") && window.__smokeClipboardText.includes("Choose one install path:") && window.__smokeClipboardText.includes("CLI path after workflow scope") && window.__smokeClipboardText.includes("GitHub UI path") && window.__smokeClipboardText.includes("node scripts/install-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write --verify") && window.__smokeClipboardText.includes("pbcopy < 'docs/github-pages-workflow.yml'") && window.__smokeClipboardText.includes("Do not archive this as post-launch verification"), "publish post-launch receipt copy text did not reach clipboard");
    publishPostLaunchReceiptOk = true;
    const launchProofEvidenceLabels = ["Pages site proof", "Pages workflow run proof", "Drift Watch workflow run proof", "Evidence freshness proof", "Release receipt proof", "Public claim guard proof"];
    const launchProofReceipt = qs("[data-publish-evidence-launch-proof-receipt]", evidence);
    await waitFor(() => {
	      const launchProofReceiptText = qs("[data-publish-evidence-launch-proof-receipt-text]", launchProofReceipt).textContent;
	      const launchProofFields = Array.from(launchProofReceipt.querySelectorAll("[data-publish-evidence-launch-proof-field]"));
	      const launchProofNextActionFields = Array.from(launchProofReceipt.querySelectorAll("[data-publish-evidence-launch-proof-field-next-action]"));
	      return evidence.dataset.publishEvidenceLaunchProofReceiptReady === "true" &&
	        evidence.dataset.publishEvidenceLaunchProofFieldCount === "6" &&
        evidence.dataset.publishEvidenceLaunchProofFieldCoverage === "1" &&
	        launchProofReceipt.dataset.publishEvidenceLaunchProofFieldCount === "6" &&
	        launchProofReceipt.dataset.publishEvidenceLaunchProofFieldCoverage === "1" &&
	        launchProofFields.length === 6 &&
	        launchProofNextActionFields.length === 6 &&
	        launchProofEvidenceLabels.every((label) => launchProofFields.some((field) => field.dataset.publishEvidenceLaunchProofFieldLabel === label)) &&
	        launchProofFields.every((field) => field.dataset.publishEvidenceLaunchProofFieldNextAction && field.textContent.includes("Next:")) &&
	        launchProofReceiptText.includes("JooPark Launch Proof Evidence Receipt") &&
	        (launchProofReceiptText.includes("Status: blocked until live proof") || launchProofReceiptText.includes("Status: guarded until external claim ready")) &&
	        launchProofReceiptText.includes("Repo: biojuho/BIOJUHO-Projects") &&
	        launchProofReceiptText.includes(expectedEvidenceRepoLine) &&
	        launchProofReceiptText.includes("Evidence fields to fill:") &&
	        launchProofEvidenceLabels.every((label) => launchProofReceiptText.includes(label)) &&
	        launchProofReceiptText.includes("Required proof commands:") &&
	        launchProofReceiptText.includes("Next proof actions:") &&
	        launchProofReceiptText.includes("nextAction=Run gh api repos/biojuho/BIOJUHO-Projects/pages") &&
	        launchProofReceiptText.includes("nextAction=Run node scripts/capture-output-quality-audit.mjs --write") &&
	        launchProofReceiptText.includes("Acceptance criteria:") &&
	        launchProofReceiptText.includes("External claim guard:") &&
	        launchProofReceiptText.includes("readyForExternalClaim: false") &&
	        launchProofReceiptText.includes("Stop condition: do not post public launch copy, archive proof, or claim readyForExternalClaim until all six evidence fields are live, fresh, linked, successful, and readyForExternalClaim=true.");
    }, "publish launch proof evidence receipt was not copy-ready", 15000);
    window.__smokeClipboardText = "";
    click("[data-publish-evidence-launch-proof-receipt-copy]", evidence);
    await waitFor(() => launchProofReceipt.dataset.publishLaunchProofReceiptCopied === "true" && qs("[data-publish-evidence-launch-proof-receipt-copy-status]", launchProofReceipt).textContent.includes("복사"), "publish launch proof receipt copy did not report success");
	    await waitFor(() => window.__smokeClipboardText.includes("JooPark Launch Proof Evidence Receipt") && (window.__smokeClipboardText.includes("Status: blocked until live proof") || window.__smokeClipboardText.includes("Status: guarded until external claim ready")) && window.__smokeClipboardText.includes("Repo: biojuho/BIOJUHO-Projects") && window.__smokeClipboardText.includes(expectedEvidenceRepoLine) && launchProofEvidenceLabels.every((label) => window.__smokeClipboardText.includes(label)) && window.__smokeClipboardText.includes("Required proof commands:") && window.__smokeClipboardText.includes("Next proof actions:") && window.__smokeClipboardText.includes("nextAction=Run gh api repos/biojuho/BIOJUHO-Projects/pages") && window.__smokeClipboardText.includes("nextAction=Run node scripts/capture-output-quality-audit.mjs --write") && window.__smokeClipboardText.includes("Acceptance criteria:") && window.__smokeClipboardText.includes("External claim guard:") && window.__smokeClipboardText.includes("readyForExternalClaim: false") && window.__smokeClipboardText.includes("Stop condition: do not post public launch copy, archive proof, or claim readyForExternalClaim until all six evidence fields are live, fresh, linked, successful, and readyForExternalClaim=true."), "publish launch proof receipt copy text did not reach clipboard");
	    launchProofEvidenceReceiptOk = true;
	    await waitFor(() => document.querySelector("[data-system-output-quality-audit]")?.dataset.outputQualityAuditLoaded === "true", "output quality audit did not load", 15000);
	    panel = qs("[data-system-publish-readiness]");
		    let outputQuality = qs("[data-system-output-quality-audit]", panel);
		    await waitFor(() => {
		      outputQuality = document.querySelector("[data-system-publish-readiness] [data-system-output-quality-audit]") || outputQuality;
		      const readyForExternalClaim =
		        outputQuality.dataset.outputQualityAuditExternalReady === "true" &&
		        outputQuality.dataset.outputQualityAuditLaunchPacketExternalReady === "true" &&
		        outputQuality.dataset.outputQualityAuditExternalClaimGuardReady === "true" &&
		        outputQuality.dataset.outputQualityAuditExternalClaimGuardStatus === "ready_for_external_claim";
		      const guardedExternalClaim =
		        outputQuality.dataset.outputQualityAuditExternalReady === "false" &&
		        outputQuality.dataset.outputQualityAuditLaunchPacketExternalReady === "false" &&
		        outputQuality.dataset.outputQualityAuditCompletionReady === "false" &&
		        Number(outputQuality.dataset.outputQualityAuditCompletionBlockedCount || 0) >= 1 &&
		        Number(outputQuality.dataset.outputQualityAuditLaunchAcceptancePending || 0) >= 1 &&
		        outputQuality.dataset.outputQualityAuditBlockerResolutionActive === "remote_workflow_file_parity" &&
		        Number(outputQuality.dataset.outputQualityAuditBlockerResolutionActionRequiredCount || 0) >= 1 &&
		        outputQuality.dataset.outputQualityAuditBlockerResolutionDeferredCount === "1";
		      return outputQuality.dataset.outputQualityAuditSource === "data/output-quality-audit.json" &&
		      outputQuality.dataset.outputQualityAuditLoaded === "true" &&
		      outputQuality.dataset.outputQualityAuditReleaseReady === "true" &&
		      (readyForExternalClaim || guardedExternalClaim) &&
	      outputQuality.dataset.outputQualityAuditSourceEvidenceFresh === "true" &&
	      outputQuality.dataset.outputQualityAuditSourceEvidenceCount === "7" &&
	      outputQuality.dataset.outputQualityAuditSourceEvidenceStaleCount === "0" &&
	      ["pass", "blocked"].includes(outputQuality.dataset.outputQualityAuditArtifactRubricStatus || "") &&
	      Number(outputQuality.dataset.outputQualityAuditArtifactRubricScore || 0) >= 80 &&
	      outputQuality.dataset.outputQualityAuditArtifactRubricMaxScore === "100" &&
	      outputQuality.dataset.outputQualityAuditArtifactRubricPassingScore === "90" &&
	      outputQuality.dataset.outputQualityAuditArtifactRubricItemCount === "5" &&
	      outputQuality.dataset.outputQualityAuditCriteriaCount === "6" &&
	      outputQuality.dataset.outputQualityAuditCompletionCount === "8" &&
	      outputQuality.dataset.outputQualityAuditComparisonCount === "5" &&
	      ["true", "false"].includes(outputQuality.dataset.outputQualityAuditWorkflowAuthPreflight || "") &&
	      ["true", "false"].includes(outputQuality.dataset.outputQualityAuditWorkflowAuthPreflightUiVerified || "") &&
	      Number(outputQuality.dataset.outputQualityAuditWorkflowAuthPreflightFields || 0) >= 0 &&
	      outputQuality.dataset.outputQualityAuditWorkflowAuthPreflightAvailable === "true" &&
	      outputQuality.dataset.outputQualityAuditWorkflowAuthPreflightInstallBlocked === "false" &&
	      Number(outputQuality.dataset.outputQualityAuditWorkflowAuthPreflightScopeCount || 0) >= 4 &&
	      outputQuality.dataset.outputQualityAuditLaunchPostAuthCheckpoint === "true" &&
	      outputQuality.dataset.outputQualityAuditLaunchPostAuthCheckpointCommandCount === "5" &&
	      outputQuality.dataset.outputQualityAuditLaunchPostAuthCheckpointExpectedCount === "6" &&
	      Number(outputQuality.dataset.outputQualityAuditLaunchPostAuthCheckpointBlockedCount || 0) >= 1 &&
	      outputQuality.dataset.outputQualityAuditLaunchPostAuthCheckpointRecheckCount === "5" &&
	      outputQuality.dataset.outputQualityAuditLaunchPostAuthCheckpointSourceArtifactCount === "4" &&
	      outputQuality.dataset.outputQualityAuditLaunchPostAuthCheckpointDispatchApproval === "false" &&
	      outputQuality.dataset.outputQualityAuditLaunchPostAuthCheckpointVerificationOnly === "true" &&
	      outputQuality.dataset.outputQualityAuditLaunchPostAuthCheckpointVerifyCommand === "node scripts/verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown" &&
	      outputQuality.dataset.outputQualityAuditWorkflowUiInstallReceipt === "true" &&
	      Number(outputQuality.dataset.outputQualityAuditWorkflowUiInstallReceiptCommandCount || 0) >= 4 &&
	      outputQuality.dataset.outputQualityAuditWorkflowUiInstallReceiptChecklistCount === "6" &&
	      outputQuality.dataset.outputQualityAuditWorkflowUiInstallReceiptVerifyCommand === "node scripts/verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown" &&
	      outputQuality.dataset.outputQualityAuditWorkflowUiInstallPastePacket === "true" &&
	      outputQuality.dataset.outputQualityAuditWorkflowUiInstallPastePacketCoverage === "1" &&
	      outputQuality.dataset.outputQualityAuditLaunchAcceptanceTotal === "5" &&
	      Number(outputQuality.dataset.outputQualityAuditLaunchAcceptancePass || 0) + Number(outputQuality.dataset.outputQualityAuditLaunchAcceptancePending || 0) === 5 &&
	      outputQuality.dataset.outputQualityAuditLaunchAcceptanceStage === "install_workflows" &&
	      ["true", "false"].includes(outputQuality.dataset.outputQualityAuditBlockerResolution || "") &&
	      outputQuality.dataset.outputQualityAuditBlockerResolutionItemCount === "6" &&
		      outputQuality.dataset.outputQualityAuditBlockerResolutionProofCommandCount === "6" &&
		      outputQuality.dataset.outputQualityAuditInstallPathsReady === "true" &&
		      outputQuality.dataset.outputQualityAuditInstallPathCount === "2" &&
		      Number(outputQuality.dataset.outputQualityAuditInstallPathCommandCount || 0) >= (readyForExternalClaim ? 9 : 10);
		    }, "output quality audit state was not surfaced", 15000);
	    const outputQualityReadyForExternalClaim =
	      outputQuality.dataset.outputQualityAuditExternalReady === "true" &&
	      outputQuality.dataset.outputQualityAuditLaunchPacketExternalReady === "true" &&
	      outputQuality.dataset.outputQualityAuditExternalClaimGuardReady === "true" &&
	      outputQuality.dataset.outputQualityAuditExternalClaimGuardStatus === "ready_for_external_claim";
	    if (outputQualityReadyForExternalClaim) {
	      const expectedOutputQualityEvidenceRepoLine = "Evidence repo: " + outputQuality.dataset.outputQualityAuditEvidenceRepo + (outputQuality.dataset.outputQualityAuditRepoPlaceholderResolved === "true" ? " (placeholder resolved from suggestedRepo)" : "");
	      const expectedOutputQualityRepoResolutionLine = "Repo resolution: " + outputQuality.dataset.outputQualityAuditRepoResolution;
	      const outputQualitySourceRepoContext = outputQuality.dataset.outputQualityAuditEvidenceRepo === "biojuho/BIOJUHO-Projects" && outputQuality.dataset.outputQualityAuditRepoResolution === "source_repo" && outputQuality.dataset.outputQualityAuditRepoPlaceholderResolved === "false";
	      assert(outputQuality.dataset.outputQualityAuditRepo === "biojuho/BIOJUHO-Projects" && outputQualitySourceRepoContext, "output quality audit repo context was not resolved");
	      assert(outputQuality.dataset.outputQualityAuditReleaseReady === "true" && outputQuality.dataset.outputQualityAuditExternalReady === "true" && outputQuality.dataset.outputQualityAuditLaunchPacketExternalReady === "true", "output quality audit ready state was not surfaced");
	      assert(outputQuality.dataset.outputQualityAuditCompletionReady === "true" && outputQuality.dataset.outputQualityAuditCompletionBlockedCount === "0" && outputQuality.dataset.outputQualityAuditNextActionKey === "share-launch-proof" && outputQuality.dataset.outputQualityAuditNextActionStatus === "ready" && outputQuality.dataset.outputQualityAuditNextActionCommand === "node scripts/capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --markdown", "output quality ready next action was not surfaced");
	      assert(outputQuality.dataset.outputQualityAuditWorkflowAuthPreflightAvailable === "true" && outputQuality.dataset.outputQualityAuditWorkflowAuthPreflightInstallBlocked === "false" && outputQuality.dataset.outputQualityAuditWorkflowAuthPreflightScopeCount === "4", "output quality workflow auth ready state was not surfaced");
	      assert(outputQuality.dataset.outputQualityAuditLaunchAcceptanceTotal === "5" && outputQuality.dataset.outputQualityAuditLaunchAcceptancePass === "5" && outputQuality.dataset.outputQualityAuditLaunchAcceptancePending === "0", "output quality launch acceptance ready state was not surfaced");
	      assert(outputQuality.dataset.outputQualityAuditPostInstallEvidenceIntakeStatus === "proof_complete" && outputQuality.dataset.outputQualityAuditPostInstallEvidenceIntakeCompletedCount === "6" && outputQuality.dataset.outputQualityAuditPostInstallEvidenceIntakeProofComplete === "true", "output quality post-install proof complete state was not surfaced");
	      assert(outputQuality.dataset.outputQualityAuditPublishEvidenceSuggestedDispatchCount === "2" && outputQuality.dataset.outputQualityAuditPublishEvidenceWithheldDispatchCount === "0" && outputQuality.dataset.outputQualityAuditPublishEvidenceImmediateActionKey === "share-launch-proof", "output quality publish evidence ready state was not surfaced");
		      assert(outputQuality.dataset.outputQualityAuditHandoffVerifierSafeToDispatch === "true" && outputQuality.dataset.outputQualityAuditBlockerResolutionActionRequiredCount === "0" && outputQuality.dataset.outputQualityAuditBlockerResolutionDeferredCount === "0" && Number(outputQuality.dataset.outputQualityAuditInstallPathCommandCount || 0) >= 9, "output quality blocker resolution ready state was not surfaced");
	      assert(qs("[data-output-quality-audit-state-label]", outputQuality).textContent.includes("ready") || qs("[data-output-quality-audit-state-label]", outputQuality).textContent.includes("archive"), "output quality audit state label did not surface ready state");
	      const qualityNextAction = qs("[data-output-quality-audit-next-action]", outputQuality);
	      assert(qualityNextAction.dataset.outputQualityAuditNextActionReady === "true" && qualityNextAction.dataset.outputQualityAuditNextActionStatus === "ready" && qualityNextAction.textContent.includes("Structured next action") && qualityNextAction.textContent.includes("Share launch proof") && qualityNextAction.textContent.includes("Pages and workflow run evidence are fresh and complete.") && qualityNextAction.textContent.includes("capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --markdown"), "output quality structured ready next action card was not surfaced");
	      const qualitySnapshot = Array.from(outputQuality.querySelectorAll("[data-output-quality-audit-snapshot-item]"));
		      assert(qualitySnapshot.length === 19 && qualitySnapshot.some((item) => item.dataset.outputQualityAuditSnapshotKey === "workflow-auth-preflight" && item.textContent.includes("workflowScopeAvailable=true") && item.textContent.includes("workflowScopeInstallBlocked=false")) && qualitySnapshot.some((item) => item.dataset.outputQualityAuditSnapshotKey === "post-install-evidence-intake" && item.textContent.includes("completed 6/6") && item.textContent.includes("proofComplete true")) && qualitySnapshot.some((item) => item.dataset.outputQualityAuditSnapshotKey === "launch-acceptance-checklist" && item.textContent.includes("5/5 pass") && item.textContent.includes("0 pending")) && qualitySnapshot.some((item) => item.dataset.outputQualityAuditSnapshotKey === "handoff-verifier-artifact" && item.textContent.includes("safeToDispatch=true")) && qualitySnapshot.some((item) => item.dataset.outputQualityAuditSnapshotKey === "launch-install-path-options" && item.textContent.includes(outputQuality.dataset.outputQualityAuditInstallPathCommandCount + " commands")) && qualitySnapshot.some((item) => item.textContent.includes("Publish evidence command guard") && item.textContent.includes("2 suggested dispatch") && item.textContent.includes("0 withheld dispatch")), "output quality ready audit snapshot was not surfaced");
	      const artifactRubric = qs("[data-output-quality-audit-artifact-rubric]", outputQuality);
	      const artifactRubricItems = Array.from(artifactRubric.querySelectorAll("[data-output-quality-audit-artifact-rubric-item]"));
	      assert(artifactRubric.textContent.includes("Artifact quality rubric") && artifactRubric.textContent.includes("Score 100/100") && artifactRubric.textContent.includes("pass threshold 90") && artifactRubric.textContent.includes("GitHub Issue Forms required inputs") && artifactRubricItems.length === 5 && artifactRubricItems.every((item) => item.dataset.outputQualityAuditArtifactRubricStatus === "pass") && artifactRubricItems.some((item) => item.dataset.outputQualityAuditArtifactRubricKey === "required_form_fit" && item.textContent.includes("11 field payloads") && item.textContent.includes("checksums ready")) && artifactRubricItems.some((item) => item.dataset.outputQualityAuditArtifactRubricKey === "copy_ready_completeness" && item.textContent.includes("workflowUiInstallPastePacket=true")) && artifactRubricItems.some((item) => item.dataset.outputQualityAuditArtifactRubricKey === "safety_guardrails" && item.textContent.includes("withheldDispatchCommands=0") && item.textContent.includes("readyForExternalClaim=true")), "output quality ready artifact rubric was not surfaced");
	      const variantComparison = qs("[data-output-quality-audit-variant-comparison]", outputQuality);
	      const variantItems = Array.from(variantComparison.querySelectorAll("[data-output-quality-audit-variant-item]"));
	      const variantCriteria = Array.from(variantComparison.querySelectorAll("[data-output-quality-audit-variant-criterion]"));
	      assert(variantComparison.dataset.outputQualityAuditVariantStatus === "pass" && variantComparison.dataset.outputQualityAuditVariantDecision === "keep_b" && variantComparison.dataset.outputQualityAuditVariantSelected === "copy_ready_evidence_receipt" && variantComparison.textContent.includes("Output variant comparison") && variantItems.length === 2 && variantCriteria.length === 4 && variantCriteria.every((item) => item.dataset.outputQualityAuditVariantCriterionWinner === "copy_ready_evidence_receipt"), "output quality ready output variant comparison was not surfaced");
	      outputQualityArtifactRubricOk = true;
	      const qualityInstallPaths = Array.from(outputQuality.querySelectorAll("[data-output-quality-audit-install-path-item]"));
		      assert(qualityInstallPaths.length === 2 && qualityInstallPaths.some((item) => item.textContent.includes("CLI path after workflow scope") && item.textContent.includes("node scripts/install-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write --verify")) && qualityInstallPaths.some((item) => item.textContent.includes("GitHub UI path")), "output quality ready launch install paths were not surfaced");
	      const qualitySourceFreshness = Array.from(outputQuality.querySelectorAll("[data-output-quality-audit-source-freshness-item]"));
	      assert(qualitySourceFreshness.length === 7 && qualitySourceFreshness.every((item) => item.dataset.outputQualityAuditSourceFreshnessStatus === "fresh") && qualitySourceFreshness.some((item) => item.dataset.outputQualityAuditSourceFreshnessKey === "remote_workflow_file_check" && item.textContent.includes("fresh")), "output quality source freshness was not surfaced");
	      const completionAuditItems = Array.from(outputQuality.querySelectorAll("[data-output-quality-audit-completion-item]"));
	      assert(completionAuditItems.length === 8 && completionAuditItems.every((item) => item.dataset.outputQualityAuditCompletionStatus === "pass") && completionAuditItems.some((item) => item.dataset.outputQualityAuditCompletionKey === "workflow_installation" && item.textContent.includes("remoteWorkflowFilesReady=true")) && completionAuditItems.some((item) => item.dataset.outputQualityAuditCompletionKey === "public_launch_proof" && item.textContent.includes("postPublishEvidenceReady=true")) && completionAuditItems.some((item) => item.dataset.outputQualityAuditCompletionKey === "external_completion_claim" && item.textContent.includes("readyForExternalClaim=true")), "output quality completion audit ready checklist was not surfaced");
	      const externalClaimGuard = qs("[data-output-quality-audit-external-claim-guard]", outputQuality);
	      const externalClaimGuardItems = Array.from(externalClaimGuard.querySelectorAll("[data-output-quality-audit-external-claim-guard-item]"));
	      const externalClaimGuardSignals = Array.from(externalClaimGuard.querySelectorAll("[data-output-quality-audit-external-claim-guard-signal]"));
	      const externalClaimGuardCommands = Array.from(externalClaimGuard.querySelectorAll("[data-output-quality-audit-external-claim-guard-command]"));
	      const externalClaimGuardText = qs("[data-output-quality-audit-external-claim-guard-text]", externalClaimGuard).textContent;
	      assert(externalClaimGuard.dataset.outputQualityAuditExternalClaimGuardReady === "true" && externalClaimGuard.dataset.outputQualityAuditExternalClaimGuardStatus === "ready_for_external_claim" && externalClaimGuard.dataset.outputQualityAuditExternalClaimGuardBlockedCount === "0" && externalClaimGuardItems.length === 3 && externalClaimGuardItems.every((item) => item.dataset.outputQualityAuditExternalClaimGuardItemStatus === "pass") && externalClaimGuardSignals.length === 6 && externalClaimGuardSignals.some((item) => item.textContent.includes("readyForExternalClaim=true")) && externalClaimGuardCommands.length >= 5 && externalClaimGuardText.includes("JooPark External Completion Claim Guard") && externalClaimGuardText.includes("Status: ready_for_external_claim") && externalClaimGuardText.includes("External claim closeout packet:"), "output quality ready external claim guard was not surfaced");
	      window.__smokeClipboardText = "";
	      click("[data-output-quality-audit-external-claim-guard-copy]", outputQuality);
	      await waitFor(() => externalClaimGuard.dataset.outputQualityExternalClaimGuardCopied === "true" && qs("[data-output-quality-audit-external-claim-guard-copy-status]", externalClaimGuard).textContent.includes("복사"), "output quality external claim guard copy did not report success");
	      await waitFor(() => window.__smokeClipboardText.includes("JooPark External Completion Claim Guard") && window.__smokeClipboardText.includes("Status: ready_for_external_claim") && window.__smokeClipboardText.includes("Workflow installation: pass") && window.__smokeClipboardText.includes("Public launch proof: pass") && window.__smokeClipboardText.includes("External completion claim: pass") && window.__smokeClipboardText.includes("readyForExternalClaim=true") && window.__smokeClipboardText.includes("External claim closeout packet:"), "output quality ready external claim guard copy text did not reach clipboard");
	      outputQualityExternalClaimGuardOk = true;
	      const qualityComparisons = Array.from(outputQuality.querySelectorAll("[data-output-quality-comparison-item]"));
	      assert(qualityComparisons.length === 5 && qualityComparisons.some((item) => item.textContent.includes("GitHub issue forms validation")) && qualityComparisons.some((item) => item.textContent.includes("Jira required fields")), "output quality external comparisons were not surfaced");
	      const goalChecklistItems = Array.from(outputQuality.querySelectorAll("[data-output-quality-audit-goal-item]"));
	      assert(outputQuality.dataset.outputQualityAuditGoalReady === "true" && outputQuality.dataset.outputQualityAuditGoalBlockedCount === "0" && goalChecklistItems.length === 7 && goalChecklistItems.every((item) => item.dataset.outputQualityAuditGoalStatus === "pass") && goalChecklistItems.some((item) => item.dataset.outputQualityAuditGoalKey === "external_output_comparison") && goalChecklistItems.some((item) => item.dataset.outputQualityAuditGoalKey === "autoresearch_usage"), "output quality prompt-to-artifact checklist was not surfaced");
	      const qualityReceipt = qs("[data-output-quality-audit-receipt]", outputQuality);
	      await waitFor(() => {
	        const qualityReceiptText = qs("[data-output-quality-audit-receipt-text]", qualityReceipt).textContent;
		        return qualityReceiptText.includes("JooPark Final Output Quality Audit Receipt") && qualityReceiptText.includes("Status: ready for public launch archive") && qualityReceiptText.includes("Repo: biojuho/BIOJUHO-Projects") && qualityReceiptText.includes(expectedOutputQualityEvidenceRepoLine) && qualityReceiptText.includes(expectedOutputQualityRepoResolutionLine) && !qualityReceiptText.includes("\\nRepo: OWNER/REPO") && qualityReceiptText.includes("Latest gate: npm run verify ->") && qualityReceiptText.includes("0 fail, 0 not_run, 0 blocked") && qualityReceiptText.includes("Workflow scope refresh command: gh auth refresh -h github.com -s workflow") && qualityReceiptText.includes("Remote workflow files ready: true") && qualityReceiptText.includes("Launch packet readyForExternalClaim: true") && qualityReceiptText.includes("Source evidence freshness:") && qualityReceiptText.includes("sourceEvidenceFresh=true; staleSources=0; sources=7") && qualityReceiptText.includes("Workflow auth preflight: pass (uiVerified=true, workflowScopeAvailable=true, workflowScopeInstallBlocked=false") && qualityReceiptText.includes("Launch handoff verifier artifact: pass") && qualityReceiptText.includes("Main PR bridge plan: pass") && qualityReceiptText.includes("Post-install evidence intake: pass (6 fields, coverage=1)") && qualityReceiptText.includes("Post-install proof parser: pass (6 fields, coverage=1)") && qualityReceiptText.includes("Launch acceptance checklist: 5/5 pass, pending=0, stage=install_workflows") && qualityReceiptText.includes("Launch install path options: pass (2 paths, " + outputQuality.dataset.outputQualityAuditInstallPathCommandCount + " commands; CLI path after workflow scope | GitHub UI path)") && qualityReceiptText.includes("Artifact quality rubric:") && qualityReceiptText.includes("artifactQualityRubric=pass; totalScore=100/100; passingScore=90") && qualityReceiptText.includes("Publish evidence command guard: pass (7 safe suggestions, 2 suggested dispatch, 0 withheld dispatch, active=0, reference=2, disposition=not_applicable_after_launch_proof)") && qualityReceiptText.includes("Publish evidence immediate action: pass (share-launch-proof from publish-evidence-next-action, deferred not available)") && qualityReceiptText.includes("Immediate action: Share launch proof [ready]") && qualityReceiptText.includes("Immediate command: node scripts/capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --markdown") && qualityReceiptText.includes("Completion audit:") && qualityReceiptText.includes("completionAuditReady=true; blocked=0; readyForExternalClaim=true") && qualityReceiptText.includes("Workflow installation: pass") && qualityReceiptText.includes("Public launch proof: pass") && qualityReceiptText.includes("External completion claim: pass") && qualityReceiptText.includes("readyForExternalClaim=true") && qualityReceiptText.includes("External comparison:") && qualityReceiptText.includes("GitHub issue forms validation") && qualityReceiptText.includes("GitHub Actions job summaries") && qualityReceiptText.includes("GitHub Releases") && qualityReceiptText.includes("Linear issue templates") && qualityReceiptText.includes("Jira required fields") && qualityReceiptText.includes("Do not present it as public launch completion");
	      }, "output quality ready audit receipt was not copy-ready", 15000);
	      window.__smokeClipboardText = "";
	      click("[data-output-quality-audit-receipt-copy]", outputQuality);
	      await waitFor(() => qualityReceipt.dataset.outputQualityAuditReceiptCopied === "true" && qs("[data-output-quality-audit-receipt-copy-status]", qualityReceipt).textContent.includes("복사"), "output quality audit receipt copy did not report success");
	      await waitFor(() => window.__smokeClipboardText.includes("JooPark Final Output Quality Audit Receipt") && window.__smokeClipboardText.includes("Status: ready for public launch archive") && window.__smokeClipboardText.includes("Repo: biojuho/BIOJUHO-Projects") && window.__smokeClipboardText.includes(expectedOutputQualityEvidenceRepoLine) && !window.__smokeClipboardText.includes("\\nRepo: OWNER/REPO") && window.__smokeClipboardText.includes("Remote workflow files ready: true") && window.__smokeClipboardText.includes("Launch packet readyForExternalClaim: true") && window.__smokeClipboardText.includes("Workflow auth preflight: pass (uiVerified=true, workflowScopeAvailable=true, workflowScopeInstallBlocked=false") && window.__smokeClipboardText.includes("Launch acceptance checklist: 5/5 pass, pending=0, stage=install_workflows") && window.__smokeClipboardText.includes("Post-install evidence intake: pass (6 fields, coverage=1)") && window.__smokeClipboardText.includes("Post-install quick proof field mapping: pass (4/4 mapped fields complete, coverage=1)") && window.__smokeClipboardText.includes("Launch handoff verifier artifact: pass (artifactCoverage=2") && window.__smokeClipboardText.includes("safeToDispatch=true") && window.__smokeClipboardText.includes("Publish evidence command guard: pass (7 safe suggestions, 2 suggested dispatch, 0 withheld dispatch, active=0, reference=2, disposition=not_applicable_after_launch_proof)") && window.__smokeClipboardText.includes("Completion audit:") && window.__smokeClipboardText.includes("Workflow installation: pass") && window.__smokeClipboardText.includes("Public launch proof: pass") && window.__smokeClipboardText.includes("External completion claim: pass") && window.__smokeClipboardText.includes("External completion claim guard:") && window.__smokeClipboardText.includes("status=ready_for_external_claim; ready=true; blocked=0/3") && window.__smokeClipboardText.includes("signal readyForExternalClaim=true") && window.__smokeClipboardText.includes("node scripts/capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --markdown"), "output quality ready audit receipt copy text did not reach clipboard");
	      outputQualityAuditReceiptOk = true;
	    } else {
	    const outputQualityAuditLaunchPostAuthCheckpointRecheckCount = outputQuality.dataset.outputQualityAuditLaunchPostAuthCheckpointRecheckCount;
	    const outputQualityAuditLaunchPostAuthCheckpointSourceArtifactCount = outputQuality.dataset.outputQualityAuditLaunchPostAuthCheckpointSourceArtifactCount;
	    const outputQualityAuditLaunchPostAuthCheckpointDispatchApproval = outputQuality.dataset.outputQualityAuditLaunchPostAuthCheckpointDispatchApproval;
	    const outputQualityAuditLaunchPostAuthCheckpointVerificationOnly = outputQuality.dataset.outputQualityAuditLaunchPostAuthCheckpointVerificationOnly;
	    const outputQualityLaunchPostAuthCheckpointExpectedSummary = "Launch post-auth checkpoint: pass (5 commands, expected=6, blocked=4, recheck=5, sources=4, dispatchApproval=false, verificationOnly=true, verify=node scripts/verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown)";
	    assert(outputQualityAuditLaunchPostAuthCheckpointRecheckCount === "5" && outputQualityAuditLaunchPostAuthCheckpointSourceArtifactCount === "4" && outputQualityAuditLaunchPostAuthCheckpointDispatchApproval === "false" && outputQualityAuditLaunchPostAuthCheckpointVerificationOnly === "true", "output quality launch post-auth checkpoint detailed state was not surfaced");
	    const expectedOutputQualityEvidenceRepoLine = "Evidence repo: " + outputQuality.dataset.outputQualityAuditEvidenceRepo + (outputQuality.dataset.outputQualityAuditRepoPlaceholderResolved === "true" ? " (placeholder resolved from suggestedRepo)" : "");
    const expectedOutputQualityRepoResolutionLine = "Repo resolution: " + outputQuality.dataset.outputQualityAuditRepoResolution;
    const outputQualitySourceRepoContext = outputQuality.dataset.outputQualityAuditEvidenceRepo === "biojuho/BIOJUHO-Projects" && outputQuality.dataset.outputQualityAuditRepoResolution === "source_repo" && outputQuality.dataset.outputQualityAuditRepoPlaceholderResolved === "false";
    assert(outputQuality.dataset.outputQualityAuditRepo === "biojuho/BIOJUHO-Projects" && outputQualitySourceRepoContext, "output quality audit repo context was not resolved");
	    assert(outputQuality.dataset.outputQualityAuditVariantStatus === "blocked" && outputQuality.dataset.outputQualityAuditVariantDecision === "recheck_before_claim" && outputQuality.dataset.outputQualityAuditVariantSelected === "recheck_required" && outputQuality.dataset.outputQualityAuditVariantScore === "4" && outputQuality.dataset.outputQualityAuditVariantBaselineScore === "2" && outputQuality.dataset.outputQualityAuditVariantMaxScore === "6" && outputQuality.dataset.outputQualityAuditVariantCount === "2" && outputQuality.dataset.outputQualityAuditVariantCriteriaCount === "4", "output quality variant comparison guarded state was not surfaced");
    assert(outputQuality.dataset.outputQualityAuditLaunchProofEvidenceReceipt === "true" && outputQuality.dataset.outputQualityAuditLaunchProofEvidenceFields === "6" && outputQuality.dataset.outputQualityAuditLaunchProofEvidenceCoverage === "1", "output quality launch proof evidence receipt state was not surfaced");
	    assert(outputQuality.dataset.outputQualityAuditHandoffVerifierArtifact === "true" && outputQuality.dataset.outputQualityAuditHandoffVerifierArtifactCoverage === "2" && outputQuality.dataset.outputQualityAuditHandoffVerifierSafeToDispatch === "false" && outputQuality.dataset.outputQualityAuditHandoffVerifierJsonPath === "data/launch-handoff-verification.json" && outputQuality.dataset.outputQualityAuditHandoffVerifierMarkdownPath === "data/launch-handoff-verification.md", "output quality handoff verifier artifact state was not surfaced");
		    const outputQualityPostInstallFieldCount = Number(outputQuality.dataset.outputQualityAuditPostInstallEvidenceIntakeFields || "0");
		    const outputQualityPostInstallCompletedCount = Number(outputQuality.dataset.outputQualityAuditPostInstallEvidenceIntakeCompletedCount || "0");
		    const outputQualityWorkflowUiInstallReceiptCommandCount = Number(outputQuality.dataset.outputQualityAuditWorkflowUiInstallReceiptCommandCount || "0");
		    const outputQualityWorkflowUiInstallReceiptChecklistCount = Number(outputQuality.dataset.outputQualityAuditWorkflowUiInstallReceiptChecklistCount || "0");
		    const outputQualityNextActionCommand = outputQuality.dataset.outputQualityAuditNextActionCommand || "";
		    const outputQualityWorkflowUiInstallReceiptSummaryReady = (text) => text.includes("Workflow UI paste packet: pass (workflowUiInstallPastePacketCoverage=1,") && text.includes(outputQualityWorkflowUiInstallReceiptCommandCount + " commands, checklist=" + outputQualityWorkflowUiInstallReceiptChecklistCount + ", verify=node scripts/verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown)");
		    assert(["pass", "blocked"].includes(outputQuality.dataset.outputQualityAuditSnapshotStatus || "") && outputQuality.dataset.outputQualityAuditReviewReady === "true" && outputQuality.dataset.outputQualityAuditIssueDecisionSummary === "true" && outputQuality.dataset.outputQualityAuditIssueDecisionSummaryFields === "6" && outputQuality.dataset.outputQualityAuditCommentNoteDecisionSummary === "true" && outputQuality.dataset.outputQualityAuditCommentNoteDecisionSummaryFields === "6" && outputQuality.dataset.outputQualityAuditRepairActionPlan === "true" && outputQuality.dataset.outputQualityAuditRepairActionPlanFields === "6" && outputQuality.dataset.outputQualityAuditSubmissionCloseoutSummary === "true" && outputQuality.dataset.outputQualityAuditSubmissionCloseoutSummaryFields === "6" && outputQuality.dataset.outputQualityAuditPostInstallEvidenceIntake === "true" && outputQuality.dataset.outputQualityAuditPostInstallEvidenceIntakeSource === "generated_from_launch_execution_packet" && outputQuality.dataset.outputQualityAuditPostInstallEvidenceIntakeStatus === "collect_post_install_proof" && outputQualityPostInstallFieldCount === 6 && outputQuality.dataset.outputQualityAuditPostInstallEvidenceIntakeCoverage === "1" && outputQualityPostInstallCompletedCount >= 0 && outputQualityPostInstallCompletedCount <= outputQualityPostInstallFieldCount && outputQuality.dataset.outputQualityAuditPostInstallEvidenceIntakeProofComplete === "false" && outputQuality.dataset.outputQualityAuditPostInstallEvidenceIntakeCommandCount === "4" && outputQuality.dataset.outputQualityAuditPostInstallEvidenceIntakeSignalCount === "8" && outputQuality.dataset.outputQualityAuditTrackerFormPayloadCount === "11" && outputQuality.dataset.outputQualityAuditTrackerFormPayloadChecksums === "true" && outputQuality.dataset.outputQualityAuditPublishEvidenceCommandGuard === "true" && ["true", "false"].includes(outputQuality.dataset.outputQualityAuditPublishEvidenceImmediateAction || "") && outputQuality.dataset.outputQualityAuditPublishEvidenceImmediateActionKey === "install_workflows" && outputQuality.dataset.outputQualityAuditPublishEvidenceSuggestedDispatchCount === "0" && outputQuality.dataset.outputQualityAuditPublishEvidenceWithheldDispatchCount === "2", "output quality audit snapshot state was not surfaced");
			    assert(outputQualityWorkflowUiInstallReceiptCommandCount >= 4 && outputQualityWorkflowUiInstallReceiptChecklistCount >= 6, "output quality workflow UI install receipt counts were stale");
		    assert(outputQuality.dataset.outputQualityAuditNextActionReady === "true" && outputQuality.dataset.outputQualityAuditNextActionKey === "install_workflows" && outputQuality.dataset.outputQualityAuditNextActionStatus === "action_required" && outputQuality.dataset.outputQualityAuditNextActionSource === "data/launch-execution-packet.json" && (outputQualityNextActionCommand === "gh auth refresh -h github.com -s workflow" || outputQualityNextActionCommand.includes("pbcopy < 'docs/github-pages-workflow.yml'") || outputQualityNextActionCommand.includes("check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write")) && outputQuality.dataset.outputQualityAuditNextActionDeferredKey === "capture-live-evidence" && outputQuality.dataset.outputQualityAuditNextActionDeferredCommand === "node scripts/capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --markdown", "output quality structured next action state was not surfaced");
		    const qualityNextAction = qs("[data-output-quality-audit-next-action]", outputQuality);
		    assert(qualityNextAction.dataset.outputQualityAuditNextActionReady === "true" && qualityNextAction.textContent.includes("Structured next action") && qualityNextAction.textContent.includes("Install workflows on the default branch") && qualityNextAction.textContent.includes("remoteWorkflowFilesReady=true") && qualityNextAction.textContent.includes(outputQualityNextActionCommand) && qualityNextAction.textContent.includes("Deferred: Capture live publish evidence") && qualityNextAction.textContent.includes("capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --markdown"), "output quality structured next action card was not surfaced");
		    const outputQualityExternalClaimGuardBlockedCount = Number(outputQuality.dataset.outputQualityAuditExternalClaimGuardBlockedCount || "0");
		    assert(outputQuality.dataset.outputQualityAuditExternalClaimGuardReady === "false" && outputQuality.dataset.outputQualityAuditExternalClaimGuardStatus === "blocked_external_claim" && outputQualityExternalClaimGuardBlockedCount > 0 && outputQualityExternalClaimGuardBlockedCount <= 3 && outputQuality.dataset.outputQualityAuditExternalClaimGuardRequirementCount === "3" && Number(outputQuality.dataset.outputQualityAuditExternalClaimGuardCommandCount || "0") >= 5, "output quality external claim guard state was not surfaced");
    assert(qs("[data-output-quality-audit-state-label]", outputQuality).textContent.includes("quality ready; launch blocked"), "output quality audit state label did not distinguish launch blocker");
    const qualitySnapshot = Array.from(outputQuality.querySelectorAll("[data-output-quality-audit-snapshot-item]"));
    const outputQualityAuditBlockerResolutionSnapshot = qs("[data-output-quality-audit-blocker-resolution-guard]", outputQuality);
    assert(outputQualityAuditBlockerResolutionSnapshot.dataset.outputQualityAuditBlockerResolutionGuard.includes("every action_required item has passed") && outputQualityAuditBlockerResolutionSnapshot.dataset.outputQualityAuditBlockerResolutionGuard.includes("verify-launch-handoff reports safeToDispatch=true"), "output quality blocker resolution guard was not surfaced");
		    const qualitySnapshotByKey = (key) => qualitySnapshot.find((item) => item.dataset.outputQualityAuditSnapshotKey === key);
		    const workflowAuthSnapshot = qualitySnapshotByKey("workflow-auth-preflight");
		    const postInstallSnapshot = qualitySnapshotByKey("post-install-evidence-intake");
		    const launchAcceptanceSnapshot = qualitySnapshotByKey("launch-acceptance-checklist");
		    const blockerResolutionSnapshot = qualitySnapshotByKey("blocker-resolution-checklist");
		    const installPathSnapshot = qualitySnapshotByKey("launch-install-path-options");
		    assert(qualitySnapshot.length === 19 && qualitySnapshot.some((item) => item.textContent.includes("Review package") && item.textContent.includes("Final quality 6/6")) && qualitySnapshot.some((item) => item.dataset.outputQualityAuditSnapshotKey === "review-decision-summaries" && item.textContent.includes("issue 6 fields") && item.textContent.includes("comment/note 6 fields") && item.textContent.includes("coverage 1")) && qualitySnapshot.some((item) => item.dataset.outputQualityAuditSnapshotKey === "review-repair-action-plan" && item.textContent.includes("6 fields") && item.textContent.includes("coverage 1")) && qualitySnapshot.some((item) => item.dataset.outputQualityAuditSnapshotKey === "submission-closeout-summary" && item.textContent.includes("6 fields") && item.textContent.includes("coverage 1")) && postInstallSnapshot && postInstallSnapshot.textContent.includes("6 fields") && postInstallSnapshot.textContent.includes("coverage 1") && postInstallSnapshot.textContent.includes("completed " + outputQualityPostInstallCompletedCount + "/6") && postInstallSnapshot.textContent.includes("proofComplete false") && postInstallSnapshot.textContent.includes("commands 4") && qualitySnapshot.some((item) => item.textContent.includes("Tracker form payloads") && item.textContent.includes("11 fields") && item.textContent.includes("checksums ready")) && qualitySnapshot.some((item) => item.textContent.includes("Runtime issues") && item.textContent.includes("console 0")) && workflowAuthSnapshot && workflowAuthSnapshot.textContent.includes("Workflow auth preflight") && workflowAuthSnapshot.textContent.includes("workflowScopeAvailable=" + outputQuality.dataset.outputQualityAuditWorkflowAuthPreflightAvailable) && workflowAuthSnapshot.textContent.includes("workflowScopeInstallBlocked=" + outputQuality.dataset.outputQualityAuditWorkflowAuthPreflightInstallBlocked) && workflowAuthSnapshot.textContent.includes(outputQuality.dataset.outputQualityAuditWorkflowAuthPreflightAvailable === "true" ? "missing none" : "missing workflow") && qualitySnapshot.some((item) => item.dataset.outputQualityAuditSnapshotKey === "launch-post-auth-checkpoint" && item.textContent.includes("Launch post-auth checkpoint") && item.textContent.includes("5 commands") && item.textContent.includes("expected 6") && item.textContent.includes("blocked 4") && item.textContent.includes("verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown") && item.textContent.includes("every action_required post-auth checkpoint item has passed")) && qualitySnapshot.some((item) => item.dataset.outputQualityAuditSnapshotKey === "workflow-ui-install-receipt" && item.textContent.includes("Workflow UI paste packet") && item.textContent.includes("workflowUiInstallPastePacketCoverage=1") && item.textContent.includes(outputQualityWorkflowUiInstallReceiptCommandCount + " commands") && item.textContent.includes("checklist " + outputQualityWorkflowUiInstallReceiptChecklistCount) && item.textContent.includes("verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown")) && launchAcceptanceSnapshot && launchAcceptanceSnapshot.textContent.includes(outputQuality.dataset.outputQualityAuditLaunchAcceptancePass + "/" + outputQuality.dataset.outputQualityAuditLaunchAcceptanceTotal + " pass") && launchAcceptanceSnapshot.textContent.includes(outputQuality.dataset.outputQualityAuditLaunchAcceptancePending + " pending") && launchAcceptanceSnapshot.textContent.includes("install_workflows") && blockerResolutionSnapshot && blockerResolutionSnapshot.dataset.outputQualityAuditBlockerResolutionGuard.includes("every action_required item has passed") && blockerResolutionSnapshot.dataset.outputQualityAuditBlockerResolutionGuard.includes("verify-launch-handoff reports safeToDispatch=true") && blockerResolutionSnapshot.textContent.includes("Blocker resolution checklist") && blockerResolutionSnapshot.textContent.includes("active " + outputQuality.dataset.outputQualityAuditBlockerResolutionActive) && blockerResolutionSnapshot.textContent.includes("actionRequired " + outputQuality.dataset.outputQualityAuditBlockerResolutionActionRequiredCount) && blockerResolutionSnapshot.textContent.includes("proofCommands 6") && installPathSnapshot && installPathSnapshot.textContent.includes("2 paths") && installPathSnapshot.textContent.includes(outputQuality.dataset.outputQualityAuditInstallPathCommandCount + " commands") && installPathSnapshot.textContent.includes("CLI path after workflow scope") && installPathSnapshot.textContent.includes("GitHub UI path") && installPathSnapshot.textContent.includes("install-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write --verify") && qualitySnapshot.some((item) => item.textContent.includes("Publish evidence command guard") && item.textContent.includes("0 suggested dispatch") && item.textContent.includes("2 withheld dispatch")) && qualitySnapshot.some((item) => item.textContent.includes("Publish evidence immediate action") && item.textContent.includes("install_workflows") && item.textContent.includes("deferred capture-live-evidence")), "output quality audit snapshot was not surfaced");
	    assert(qualitySnapshot.some((item) => item.dataset.outputQualityAuditSnapshotKey === "launch-post-auth-checkpoint" && item.textContent.includes("recheck 5") && item.textContent.includes("sources 4") && item.textContent.includes("dispatchApproval=false") && item.textContent.includes("verificationOnly=true")), "output quality launch post-auth checkpoint detailed snapshot was not surfaced");
    assert(qualitySnapshot.some((item) => item.dataset.outputQualityAuditSnapshotKey === "handoff-verifier-artifact" && item.textContent.includes("Launch handoff verifier artifact") && item.textContent.includes("artifactCoverage=2") && item.textContent.includes("safeToDispatch=false") && item.textContent.includes("data/launch-handoff-verification.json") && item.textContent.includes("data/launch-handoff-verification.md")), "output quality handoff verifier artifact snapshot was not surfaced");
    assert(qualitySnapshot.some((item) => item.dataset.outputQualityAuditSnapshotKey === "main-bridge-plan" && item.textContent.includes("Main PR bridge plan") && item.textContent.includes("main-subdirectory-bridge") && item.textContent.includes("noCommonHistory=true") && item.textContent.includes("codex/joopark-workspace-main-bridge")), "output quality main bridge plan snapshot was not surfaced");
    assert(qualitySnapshot.some((item) => item.dataset.outputQualityAuditSnapshotKey === "launch-proof-evidence-receipt" && item.textContent.includes("Launch proof evidence receipt") && item.textContent.includes("6 fields") && item.textContent.includes("coverage 1")), "output quality launch proof evidence receipt snapshot was not surfaced");
    const artifactRubric = qs("[data-output-quality-audit-artifact-rubric]", outputQuality);
    const artifactRubricItems = Array.from(artifactRubric.querySelectorAll("[data-output-quality-audit-artifact-rubric-item]"));
	    const copyReadyCompletenessRubricItem = artifactRubricItems.find((item) => item.dataset.outputQualityAuditArtifactRubricKey === "copy_ready_completeness");
	    const copyReadyCompletenessStatus = copyReadyCompletenessRubricItem?.dataset.outputQualityAuditArtifactRubricStatus || "";
	    assert(artifactRubric.textContent.includes("Artifact quality rubric") && artifactRubric.textContent.includes("Score " + outputQuality.dataset.outputQualityAuditArtifactRubricScore + "/" + outputQuality.dataset.outputQualityAuditArtifactRubricMaxScore) && artifactRubric.textContent.includes("pass threshold " + outputQuality.dataset.outputQualityAuditArtifactRubricPassingScore) && artifactRubric.textContent.includes("GitHub Issue Forms required inputs") && artifactRubricItems.length === 5 && artifactRubricItems.some((item) => item.dataset.outputQualityAuditArtifactRubricKey === "required_form_fit" && item.dataset.outputQualityAuditArtifactRubricStatus === "pass" && item.textContent.includes("11 field payloads") && item.textContent.includes("checksums ready")) && ["pass", "blocked"].includes(copyReadyCompletenessStatus) && copyReadyCompletenessRubricItem?.textContent.includes("workflowUiInstallPastePacket=true") && artifactRubricItems.some((item) => item.dataset.outputQualityAuditArtifactRubricKey === "safety_guardrails" && item.dataset.outputQualityAuditArtifactRubricStatus === "pass" && item.textContent.includes("withheldDispatchCommands=2") && item.textContent.includes("readyForExternalClaim=false")), "output quality guarded artifact rubric was not surfaced");
	    assert(((copyReadyCompletenessStatus === "pass" && copyReadyCompletenessRubricItem?.textContent.includes("externalClaimGuard=true")) || (copyReadyCompletenessStatus === "blocked" && copyReadyCompletenessRubricItem?.textContent.includes("externalClaimGuard=false"))) && copyReadyCompletenessRubricItem?.textContent.includes("handoffVerifierArtifact=true") && copyReadyCompletenessRubricItem?.textContent.includes("mainBridgePlan=true"), "output quality artifact rubric did not include guarded external claim, handoff verifier, and main bridge readiness");
    const variantComparison = qs("[data-output-quality-audit-variant-comparison]", outputQuality);
    const variantItems = Array.from(variantComparison.querySelectorAll("[data-output-quality-audit-variant-item]"));
    const variantCriteria = Array.from(variantComparison.querySelectorAll("[data-output-quality-audit-variant-criterion]"));
    const variantCriterionByKey = (key) => variantCriteria.find((item) => item.dataset.outputQualityAuditVariantCriterionKey === key);
    const externalStandardCriterion = variantCriterionByKey("external_standard_fit");
    const expectedExternalStandardWinner = outputQuality.dataset.outputQualityAuditArtifactRubricStatus === "pass" &&
      Number(outputQuality.dataset.outputQualityAuditComparisonCount || "0") >= 5
      ? "copy_ready_evidence_receipt"
      : "generic_generated_summary";
	    assert(variantComparison.dataset.outputQualityAuditVariantStatus === "blocked" && variantComparison.dataset.outputQualityAuditVariantDecision === "recheck_before_claim" && variantComparison.dataset.outputQualityAuditVariantSelected === "recheck_required" && variantComparison.textContent.includes("Output variant comparison") && variantComparison.textContent.includes("Do not choose a final variant until") && variantItems.length === 2 && variantItems.some((item) => item.dataset.outputQualityAuditVariantKey === "generic_generated_summary" && item.dataset.outputQualityAuditVariantItemStatus === "rejected" && item.textContent.includes("does not carry required tracker fields")) && variantItems.some((item) => item.dataset.outputQualityAuditVariantKey === "copy_ready_evidence_receipt" && item.dataset.outputQualityAuditVariantItemStatus === "needs_recheck" && item.textContent.includes("11 tracker fields")) && variantCriteria.length === 4 && variantCriteria.some((item) => item.dataset.outputQualityAuditVariantCriterionWinner === "copy_ready_evidence_receipt" && item.textContent.includes("Copy-ready field payloads") && item.textContent.includes("trackerFormPayloads=11")) && variantCriteria.some((item) => item.dataset.outputQualityAuditVariantCriterionWinner === "generic_generated_summary" && item.textContent.includes("Proof traceability")) && externalStandardCriterion?.dataset.outputQualityAuditVariantCriterionWinner === expectedExternalStandardWinner && externalStandardCriterion?.textContent.includes("External standard fit") && externalStandardCriterion?.textContent.includes("externalComparisons=" + outputQuality.dataset.outputQualityAuditComparisonCount) && externalStandardCriterion?.textContent.includes("artifactQualityRubric=" + outputQuality.dataset.outputQualityAuditArtifactRubricStatus), "output quality guarded variant comparison was not surfaced");
    outputQualityArtifactRubricOk = true;
    const qualityInstallPaths = Array.from(outputQuality.querySelectorAll("[data-output-quality-audit-install-path-item]"));
    assert(qualityInstallPaths.length === 2 && qualityInstallPaths.some((item) => item.textContent.includes("CLI path after workflow scope") && item.textContent.includes("node scripts/install-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write --verify")) && qualityInstallPaths.some((item) => item.textContent.includes("GitHub UI path") && item.textContent.includes("pbcopy < 'docs/github-pages-workflow.yml'") && item.textContent.includes("open 'https://github.com/biojuho/BIOJUHO-Projects/edit/main/.github/workflows/joopark-pages.yml'")), "output quality launch install paths were not surfaced");
    const qualitySourceFreshness = Array.from(outputQuality.querySelectorAll("[data-output-quality-audit-source-freshness-item]"));
	    assert(qualitySourceFreshness.length === 7 && qualitySourceFreshness.every((item) => item.dataset.outputQualityAuditSourceFreshnessStatus === "fresh") && qualitySourceFreshness.some((item) => item.dataset.outputQualityAuditSourceFreshnessKey === "remote_workflow_file_check" && item.textContent.includes("data/remote-workflow-file-check.json")) && qualitySourceFreshness.some((item) => item.dataset.outputQualityAuditSourceFreshnessKey === "launch_execution_packet" && item.textContent.includes("data/launch-execution-packet.json")) && qualitySourceFreshness.some((item) => item.dataset.outputQualityAuditSourceFreshnessKey === "launch_handoff_verification" && item.textContent.includes("data/launch-handoff-verification.json")) && qualitySourceFreshness.some((item) => item.dataset.outputQualityAuditSourceFreshnessKey === "main_bridge_plan" && item.textContent.includes("data/main-bridge-plan.json")), "output quality source evidence freshness was not surfaced");
	    const completionAuditItems = Array.from(outputQuality.querySelectorAll("[data-output-quality-audit-completion-item]"));
	    const completionAuditItemByKey = (key) => completionAuditItems.find((item) => item.dataset.outputQualityAuditCompletionKey === key);
	    const workflowCompletionItem = completionAuditItemByKey("workflow_installation");
	    const publicProofCompletionItem = completionAuditItemByKey("public_launch_proof");
	    const externalClaimCompletionItem = completionAuditItemByKey("external_completion_claim");
	    assert(completionAuditItems.length === 8 && completionAuditItems.some((item) => item.dataset.outputQualityAuditCompletionKey === "release_quality_gate" && item.dataset.outputQualityAuditCompletionStatus === "pass") && completionAuditItems.some((item) => item.dataset.outputQualityAuditCompletionKey === "source_evidence_freshness" && item.dataset.outputQualityAuditCompletionStatus === "pass" && item.textContent.includes("staleSources=0")) && workflowCompletionItem?.dataset.outputQualityAuditCompletionStatus === "blocked" && workflowCompletionItem.textContent.includes("remoteWorkflowFilesReady=false") && workflowCompletionItem.textContent.includes("remoteWorkflowVisibilityReady=true") && publicProofCompletionItem?.dataset.outputQualityAuditCompletionStatus === "pass" && publicProofCompletionItem.textContent.includes("postPublishEvidenceReady=true") && externalClaimCompletionItem && externalClaimCompletionItem.textContent.includes("launchPacketReadyForExternalClaim=false") && externalClaimCompletionItem.textContent.includes("readyForExternalClaim=false"), "output quality completion audit checklist was not surfaced");
	    const externalClaimGuard = qs("[data-output-quality-audit-external-claim-guard]", outputQuality);
	    const externalClaimGuardItems = Array.from(externalClaimGuard.querySelectorAll("[data-output-quality-audit-external-claim-guard-item]"));
	    const externalClaimGuardSignals = Array.from(externalClaimGuard.querySelectorAll("[data-output-quality-audit-external-claim-guard-signal]"));
	    const externalClaimGuardCommands = Array.from(externalClaimGuard.querySelectorAll("[data-output-quality-audit-external-claim-guard-command]"));
	    const externalClaimGuardCloseout = qs("[data-output-quality-audit-external-claim-closeout]", externalClaimGuard);
	    const externalClaimCloseoutSteps = Array.from(externalClaimGuardCloseout.querySelectorAll("[data-output-quality-audit-external-claim-closeout-step]"));
	    const externalClaimCloseoutFields = Array.from(externalClaimGuardCloseout.querySelectorAll("[data-output-quality-audit-external-claim-closeout-field]"));
	    const externalClaimGuardText = qs("[data-output-quality-audit-external-claim-guard-text]", externalClaimGuard).textContent;
	    const externalClaimGuardItemByKey = (key) => externalClaimGuardItems.find((item) => item.dataset.outputQualityAuditExternalClaimGuardKey === key);
	    const externalClaimGuardSignalText = externalClaimGuardSignals.map((item) => item.textContent || "").join("\\n");
	    const externalClaimWorkflowItem = externalClaimGuardItemByKey("workflow_installation");
	    const externalClaimPublicProofItem = externalClaimGuardItemByKey("public_launch_proof");
	    const externalClaimFinalItem = externalClaimGuardItemByKey("external_completion_claim");
	    assert(!!qs('[data-action="copy-output-quality-external-claim-guard"]', externalClaimGuard), "output quality external claim guard copy action was not wired");
	    assert(externalClaimGuard.dataset.outputQualityAuditExternalClaimGuardReady === "false" && externalClaimGuard.dataset.outputQualityAuditExternalClaimGuardStatus === "blocked_external_claim" && Number(externalClaimGuard.dataset.outputQualityAuditExternalClaimGuardBlockedCount || "0") === outputQualityExternalClaimGuardBlockedCount && externalClaimGuardItems.length === 3 && externalClaimWorkflowItem?.dataset.outputQualityAuditExternalClaimGuardItemStatus === "blocked" && externalClaimWorkflowItem.textContent.includes("remoteWorkflowFilesReady=false") && externalClaimPublicProofItem?.dataset.outputQualityAuditExternalClaimGuardItemStatus === "pass" && externalClaimPublicProofItem.textContent.includes("postPublishEvidenceReady=true") && externalClaimFinalItem?.dataset.outputQualityAuditExternalClaimGuardItemStatus === "blocked" && externalClaimFinalItem.textContent.includes("readyForExternalClaim=false") && externalClaimGuardSignals.length === 6 && externalClaimGuardSignalText.includes("allDispatchReady=false") && externalClaimGuardSignalText.includes("postPublishEvidenceReady=true") && externalClaimGuardCommands.length >= 5 && externalClaimGuardText.includes("JooPark External Completion Claim Guard") && externalClaimGuardText.includes("Status: blocked_external_claim") && externalClaimGuardText.includes("Blocked requirements: " + outputQualityExternalClaimGuardBlockedCount + "/3") && externalClaimGuardText.includes("External claim closeout packet:") && externalClaimGuardText.includes("default branch workflow_dispatch") && externalClaimGuardText.includes("Required proof fields:") && externalClaimGuardText.includes("workflow run summary") && externalClaimGuardText.includes("Release-note archive claim") && externalClaimGuardText.includes("Allowed claim after proof:") && externalClaimGuardText.includes("Forbidden until proof:") && externalClaimGuardText.includes("Stop condition: do not claim readyForExternalClaim"), "output quality external claim guard was not surfaced");
	    const workflowRunSummaryField = externalClaimCloseoutFields.find((item) => item.dataset.outputQualityAuditExternalClaimCloseoutFieldKey === "workflow_run_summary");
	    assert(externalClaimGuardCloseout.dataset.outputQualityAuditExternalClaimCloseoutReady === "false" && externalClaimGuardCloseout.dataset.outputQualityAuditExternalClaimCloseoutStatus === "blocked_external_claim" && externalClaimGuardCloseout.dataset.outputQualityAuditExternalClaimCloseoutStepCount === "5" && externalClaimGuardCloseout.dataset.outputQualityAuditExternalClaimCloseoutFieldCount === "6" && externalClaimGuardCloseout.dataset.outputQualityAuditExternalClaimCloseoutAllowedCount === "3" && externalClaimGuardCloseout.dataset.outputQualityAuditExternalClaimCloseoutForbiddenCount === "3" && externalClaimGuardCloseout.textContent.includes("External claim closeout packet") && externalClaimGuardCloseout.textContent.includes("default branch workflow_dispatch") && externalClaimGuardCloseout.textContent.includes("workflow run summary") && externalClaimGuardCloseout.textContent.includes("Release-note archive claim") && externalClaimCloseoutSteps.length === 5 && externalClaimCloseoutSteps.some((item) => item.dataset.outputQualityAuditExternalClaimCloseoutStepKey === "install_default_branch_workflows") && externalClaimCloseoutSteps.some((item) => item.dataset.outputQualityAuditExternalClaimCloseoutStepKey === "capture_workflow_run_summary") && externalClaimCloseoutFields.length === 6 && workflowRunSummaryField && workflowRunSummaryField.textContent.includes("postPublishEvidenceReady=true") && externalClaimGuardCloseout.textContent.includes("readyForExternalClaim=true") && externalClaimGuardCloseout.textContent.includes("public launch complete before live Pages"), "output quality external claim closeout packet was not surfaced");
    window.__smokeClipboardText = "";
    click("[data-output-quality-audit-external-claim-guard-copy]", outputQuality);
    await waitFor(() => externalClaimGuard.dataset.outputQualityExternalClaimGuardCopied === "true" && qs("[data-output-quality-audit-external-claim-guard-copy-status]", externalClaimGuard).textContent.includes("복사"), "output quality external claim guard copy did not report success");
	    await waitFor(() => window.__smokeClipboardText.includes("JooPark External Completion Claim Guard") && window.__smokeClipboardText.includes("Status: blocked_external_claim") && window.__smokeClipboardText.includes("Workflow installation: blocked") && window.__smokeClipboardText.includes("Public launch proof: pass") && window.__smokeClipboardText.includes("External completion claim: blocked") && window.__smokeClipboardText.includes("remoteWorkflowFilesReady=false") && window.__smokeClipboardText.includes("postPublishEvidenceReady=true") && window.__smokeClipboardText.includes("launchPacketReadyForExternalClaim=false") && window.__smokeClipboardText.includes("readyForExternalClaim=false") && window.__smokeClipboardText.includes("node scripts/verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown") && window.__smokeClipboardText.includes("External claim closeout packet:") && window.__smokeClipboardText.includes("default branch workflow_dispatch") && window.__smokeClipboardText.includes("Required proof fields:") && window.__smokeClipboardText.includes("workflow run summary") && window.__smokeClipboardText.includes("Release-note archive claim") && window.__smokeClipboardText.includes("Allowed claim after proof:") && window.__smokeClipboardText.includes("Forbidden until proof:") && window.__smokeClipboardText.includes("Stop condition: do not claim readyForExternalClaim"), "output quality external claim guard copy text did not reach clipboard");
    outputQualityExternalClaimGuardOk = true;
    const qualityComparisons = Array.from(outputQuality.querySelectorAll("[data-output-quality-comparison-item]"));
    assert(qualityComparisons.length === 5 && qualityComparisons.some((item) => item.textContent.includes("GitHub issue forms validation")) && qualityComparisons.some((item) => item.textContent.includes("GitHub Actions job summaries")) && qualityComparisons.some((item) => item.textContent.includes("GitHub Releases")) && qualityComparisons.some((item) => item.textContent.includes("Linear issue templates")) && qualityComparisons.some((item) => item.textContent.includes("Jira required fields")), "output quality external comparison was not surfaced");
    const goalChecklistItems = Array.from(outputQuality.querySelectorAll("[data-output-quality-audit-goal-item]"));
    const externalComparisonGoalReady = goalChecklistItems.some((item) =>
      item.dataset.outputQualityAuditGoalKey === "external_output_comparison" &&
      (item.textContent.includes("GitHub issue form validation") || item.textContent.includes("GitHub issue forms validation"))
    );
    const autoresearchGoalReady = goalChecklistItems.some((item) =>
      item.dataset.outputQualityAuditGoalKey === "autoresearch_usage" &&
      (item.textContent.includes("public-launch claims blocked") || item.textContent.includes("publicLaunchProof=blocked") || item.textContent.includes("public launch proof"))
    );
    const outputQualityGoalReady = outputQuality.dataset.outputQualityAuditGoalReady === "true";
    const outputQualityGoalBlockedCount = Number(outputQuality.dataset.outputQualityAuditGoalBlockedCount || "0");
    const outputQualityGoalStatuses = goalChecklistItems.map((item) => item.dataset.outputQualityAuditGoalStatus || "");
	    assert(goalChecklistItems.length === 7 && ((outputQualityGoalReady && outputQualityGoalBlockedCount === 0 && outputQualityGoalStatuses.every((status) => status === "pass")) || (!outputQualityGoalReady && outputQualityGoalBlockedCount > 0 && outputQualityGoalStatuses.includes("blocked") && outputQualityGoalStatuses.includes("pass"))) && goalChecklistItems.some((item) => item.dataset.outputQualityAuditGoalKey === "result_quality_diagnosis" && item.textContent.includes("artifactQualityRubric")) && externalComparisonGoalReady && autoresearchGoalReady, "output quality prompt-to-artifact checklist was not surfaced");
	    const qualityReceipt = qs("[data-output-quality-audit-receipt]", outputQuality);
	    const outputQualityPostInstallProofParserReady = (text) => (
	      text.includes("Post-install proof parser: pass (6 fields, coverage=1)") &&
	      text.includes("detected=6/6") &&
	      text.includes("falsePositiveGuard=true") &&
	      text.includes("not dispatch approval")
	    ) || (
	      text.includes("Post-install proof parser: pass (0 fields, coverage=0)") &&
	      text.includes("detected=0/0") &&
	      text.includes("falsePositiveGuard=true") &&
	      text.includes("not dispatch approval")
	    );
	    const outputQualityReceiptHasCurrentLaunchState = (text) => text.includes("JooPark Final Output Quality Audit Receipt") && text.includes("Status: public launch proof ready; launch packet claim guard blocked") && text.includes("Repo: biojuho/BIOJUHO-Projects") && text.includes(expectedOutputQualityEvidenceRepoLine) && text.includes(expectedOutputQualityRepoResolutionLine) && !text.includes("\\nRepo: OWNER/REPO") && text.includes("Remote workflow files ready: false") && text.includes("Launch packet readyForExternalClaim: false") && text.includes("postPublishEvidenceReady: true") && (text.includes("Workflow auth preflight: pass") || text.includes("Workflow auth preflight: blocked")) && text.includes("workflowScopeAvailable=true") && text.includes("workflowScopeInstallBlocked=false") && text.includes("Post-install evidence intake: pass (6 fields, coverage=1)") && outputQualityPostInstallProofParserReady(text) && text.includes("completed=" + outputQualityPostInstallCompletedCount + "/6") && text.includes("Launch acceptance checklist: " + outputQuality.dataset.outputQualityAuditLaunchAcceptancePass + "/" + outputQuality.dataset.outputQualityAuditLaunchAcceptanceTotal + " pass, pending=" + outputQuality.dataset.outputQualityAuditLaunchAcceptancePending) && text.includes("Blocker resolution checklist: blocked (active=" + outputQuality.dataset.outputQualityAuditBlockerResolutionActive) && text.includes("Remote workflow file acceptance ledger: blocked (1/2 files ready, missing=0, mismatch=1") && text.includes("Launch proof acceptance ledger: blocked (5/6 ready, pending=1") && text.includes("Workflow installation: blocked") && text.includes("Public launch proof: pass") && text.includes("External completion claim: blocked") && text.includes("status=blocked_external_claim; ready=false; blocked=" + outputQualityExternalClaimGuardBlockedCount + "/3") && text.includes("Remote workflow file check: pages: remote workflow file differs from local template") && text.includes("Immediate command: " + outputQualityNextActionCommand) && text.includes("Do not present it as public launch completion");
	    await waitFor(() => {
	      const qualityReceiptText = qs("[data-output-quality-audit-receipt-text]", qualityReceipt).textContent;
	      if (outputQualityReceiptHasCurrentLaunchState(qualityReceiptText)) return true;
	      return qualityReceiptText.includes("JooPark Final Output Quality Audit Receipt") && qualityReceiptText.includes("Status: release quality ready; public launch proof blocked") && qualityReceiptText.includes("Repo: biojuho/BIOJUHO-Projects") && qualityReceiptText.includes(expectedOutputQualityEvidenceRepoLine) && qualityReceiptText.includes(expectedOutputQualityRepoResolutionLine) && !qualityReceiptText.includes("\\nRepo: OWNER/REPO") && qualityReceiptText.includes("Latest gate: npm run verify ->") && qualityReceiptText.includes("0 fail, 0 not_run, 0 blocked") && qualityReceiptText.includes("Workflow scope refresh command: gh auth refresh -h github.com -s workflow") && qualityReceiptText.includes("Remote workflow files ready: false") && qualityReceiptText.includes("Launch packet readyForExternalClaim: false") && qualityReceiptText.includes("Source evidence freshness:") && qualityReceiptText.includes("sourceEvidenceFresh=true; staleSources=0; sources=7") && qualityReceiptText.includes("remote workflow file check: fresh") && qualityReceiptText.includes("launch execution packet: fresh") && qualityReceiptText.includes("launch handoff verification: fresh") && qualityReceiptText.includes("main bridge plan: fresh") && qualityReceiptText.includes("Output readiness snapshot:") && qualityReceiptText.includes("Review package final quality: 6/6") && qualityReceiptText.includes("First-run guided start: pass (3 items, coverage=1)") && qualityReceiptText.includes("Review package decision brief: pass (6 fields, coverage=1)") && qualityReceiptText.includes("Review issue decision summary: pass (6 fields, coverage=1)") && qualityReceiptText.includes("Review comment/note decision summary: pass (6 fields, coverage=1)") && qualityReceiptText.includes("Tracker form payloads: pass (11 fields, checksums ready)") && qualityReceiptText.includes("Runtime issues: console 0, network 0, layout 0") && qualityReceiptText.includes("Workflow auth preflight: pass (uiVerified=true, workflowScopeAvailable=false, workflowScopeInstallBlocked=true, missing=workflow, scopes=gist, read:org, repo)") && qualityReceiptText.includes(outputQualityLaunchPostAuthCheckpointExpectedSummary) && outputQualityWorkflowUiInstallReceiptSummaryReady(qualityReceiptText) && qualityReceiptText.includes("Launch handoff verifier artifact: pass") && qualityReceiptText.includes("Main PR bridge plan: pass") && qualityReceiptText.includes("Operator one-page handoff: pass") && qualityReceiptText.includes("successSignals=8") && qualityReceiptText.includes("Post-install evidence intake: pass (6 fields, coverage=1)") && qualityReceiptText.includes("Post-install proof parser: pass (6 fields, coverage=1)") && qualityReceiptText.includes("Launch acceptance checklist: 2/5 pass, pending=3, stage=install_workflows") && qualityReceiptText.includes("Launch install path options: pass (2 paths, 14 commands; CLI path after workflow scope | GitHub UI path)") && qualityReceiptText.includes("Artifact quality rubric:") && qualityReceiptText.includes("artifactQualityRubric=pass; totalScore=100/100; passingScore=90") && qualityReceiptText.includes("Required form fit: pass (20/20)") && qualityReceiptText.includes("Copy-ready completeness") && qualityReceiptText.includes("Safety guardrails: pass (20/20)") && qualityReceiptText.includes("GitHub Issue Forms required inputs") && qualityReceiptText.includes("Launch install path options:") && qualityReceiptText.includes("CLI path after workflow scope") && qualityReceiptText.includes("GitHub UI path") && qualityReceiptText.includes("node scripts/install-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write --verify") && qualityReceiptText.includes("pbcopy < 'docs/github-pages-workflow.yml'") && qualityReceiptText.includes("Publish evidence command guard: pass (7 safe suggestions, 0 suggested dispatch, 2 withheld dispatch, active=0, reference=2, disposition=withheld_until_all_dispatch_ready)") && qualityReceiptText.includes("Publish evidence immediate action: pass (install_workflows from data/launch-execution-packet.json, deferred capture-live-evidence)") && qualityReceiptText.includes("Immediate command: gh auth refresh -h github.com -s workflow") && qualityReceiptText.includes("Deferred evidence capture: Capture live publish evidence") && qualityReceiptText.includes("Remote workflow file check: pages: remote workflow file is not installed on main") && qualityReceiptText.includes("Quality criteria:") && qualityReceiptText.includes("Prompt-to-artifact checklist:") && qualityReceiptText.includes("goalCompletionAudit=output_quality_goal_covered") && qualityReceiptText.includes("Result quality diagnosis: pass") && qualityReceiptText.includes("External output comparison: pass") && qualityReceiptText.includes("AutoResearch usage: pass") && qualityReceiptText.includes("Completion audit:") && qualityReceiptText.includes("completionAuditReady=false") && qualityReceiptText.includes("Source evidence freshness: pass") && qualityReceiptText.includes("Workflow installation: blocked") && qualityReceiptText.includes("remoteWorkflowFilesReady=false") && qualityReceiptText.includes("Public launch proof: blocked") && qualityReceiptText.includes("postPublishEvidenceReady=false") && qualityReceiptText.includes("External completion claim: blocked") && qualityReceiptText.includes("launchPacketReadyForExternalClaim=false") && qualityReceiptText.includes("readyForExternalClaim=false") && qualityReceiptText.includes("External comparison:") && qualityReceiptText.includes("GitHub issue forms validation") && qualityReceiptText.includes("GitHub Actions job summaries") && qualityReceiptText.includes("GitHub Releases") && qualityReceiptText.includes("Linear issue templates") && qualityReceiptText.includes("Jira required fields") && qualityReceiptText.includes("Public launch proof: blocked") && qualityReceiptText.includes("Do not present it as public launch completion");
    }, "output quality audit receipt was not copy-ready", 15000);
	    const qualityReceiptReadyText = qs("[data-output-quality-audit-receipt-text]", qualityReceipt).textContent;
	    assert(qualityReceiptReadyText.includes(outputQualityLaunchPostAuthCheckpointExpectedSummary) && qualityReceiptReadyText.includes("guard=Do not run gh workflow run until every action_required post-auth checkpoint item has passed and verify-launch-handoff reports safeToDispatch=true."), "output quality launch post-auth checkpoint guard was not copy-ready");
	    assert(outputQualityWorkflowUiInstallReceiptSummaryReady(qualityReceiptReadyText) && qualityReceiptReadyText.includes("guard=Do not run gh workflow run until every post-install evidence field has been filled") && qualityReceiptReadyText.includes("remoteWorkflowFilesReady=true") && qualityReceiptReadyText.includes("verify-launch-handoff reports safeToDispatch=true."), "output quality workflow UI paste packet guard was not copy-ready");
    assert(qualityReceiptReadyText.includes("External claim closeout packet:") && qualityReceiptReadyText.includes("default branch workflow_dispatch") && qualityReceiptReadyText.includes("Required proof fields:") && qualityReceiptReadyText.includes("workflow run summary") && qualityReceiptReadyText.includes("Release-note archive claim") && qualityReceiptReadyText.includes("Allowed claim after proof:") && qualityReceiptReadyText.includes("Forbidden until proof:"), "output quality external claim closeout packet was not copy-ready");
		    assert(qualityReceiptReadyText.includes("Output variant comparison:") && qualityReceiptReadyText.includes("status=blocked; decision=recheck_before_claim; selected=recheck_required; score=4/6; baseline=2/6") && qualityReceiptReadyText.includes("A: generic generated summary: rejected") && qualityReceiptReadyText.includes("B: copy-ready evidence receipt: needs_recheck") && qualityReceiptReadyText.includes("Copy-ready field payloads: winner=copy_ready_evidence_receipt") && qualityReceiptReadyText.includes("Proof traceability: winner=generic_generated_summary") && qualityReceiptReadyText.includes("Launch safety: winner=copy_ready_evidence_receipt") && qualityReceiptReadyText.includes("External standard fit: winner=" + expectedExternalStandardWinner), "output quality guarded output variant comparison was not copy-ready");
		    assert(qualityReceiptReadyText.includes("Review comment/note decision summary: pass (6 fields, coverage=1)"), "output quality comment/note decision summary was not copy-ready");
		    assert(qualityReceiptReadyText.includes("First-run guided start: pass (3 items, coverage=1)"), "output quality first-run guided start was not copy-ready");
		    assert(qualityReceiptReadyText.includes("Global help access: pass (4 actions, coverage=1)"), "output quality global help access was not copy-ready");
		    assert(qualityReceiptReadyText.includes("Topbar data safety: pass (4 actions, coverage=1)"), "output quality topbar data safety was not copy-ready");
		    assert(qualityReceiptReadyText.includes("Route deep link: pass (coverage=1)"), "output quality route deep link was not copy-ready");
		    assert(qualityReceiptReadyText.includes("Review result repair action plan: pass (6 fields, coverage=1)"), "output quality repair action plan was not copy-ready");
	    assert(qualityReceiptReadyText.includes("Review submission closeout summary: pass (6 fields, coverage=1)"), "output quality submission closeout summary was not copy-ready");
	    assert(qualityReceiptReadyText.includes("Post-install evidence intake: pass (6 fields, coverage=1)"), "output quality post-install evidence intake was not copy-ready");
	    assert(outputQualityPostInstallProofParserReady(qualityReceiptReadyText), "output quality post-install proof parser was not copy-ready");
	    assert(qualityReceiptReadyText.includes("Post-install quick proof: pass (4 steps, coverage=1)"), "output quality post-install quick proof was not copy-ready");
		    assert(qualityReceiptReadyText.includes("Post-install quick proof field mapping: pass (") && qualityReceiptReadyText.includes("mapped fields complete, coverage=1)"), "output quality post-install quick proof field mapping was not copy-ready");
		    assert(qualityReceiptReadyText.includes("Post-install evidence intake:") && qualityReceiptReadyText.includes("source=generated_from_launch_execution_packet; status=collect_post_install_proof; proofComplete=false; completed=" + outputQualityPostInstallCompletedCount + "/6; commands=4; signals=8") && qualityReceiptReadyText.includes("quickProofReady=true; steps=4; coverage=1") && qualityReceiptReadyText.includes("quickProofFieldMappingReady=true; mapped=4; completed=") && qualityReceiptReadyText.includes("quick proof 1 remote_file_parity: evidence_required") && qualityReceiptReadyText.includes("quick proof 4 handoff_verifier: evidence_required") && qualityReceiptReadyText.includes("quick proof field 1 remote_file_parity -> remote_parity_proof") && qualityReceiptReadyText.includes("quick proof field 4 handoff_verifier -> handoff_verifier_proof") && qualityReceiptReadyText.includes("remote_parity_proof: evidence_required") && qualityReceiptReadyText.includes("currentValue=remoteWorkflowFilesReady=false") && qualityReceiptReadyText.includes("handoff_verifier_proof: evidence_required") && qualityReceiptReadyText.includes("Stop condition: do not run gh workflow run"), "output quality post-install evidence intake ledger was not copy-ready");
	    assert(qualityReceiptReadyText.includes("Launch proof evidence receipt: pass (6 fields, coverage=1, nextActions=6/6)"), "output quality launch proof evidence receipt was not copy-ready");
	    assert(qualityReceiptReadyText.includes("Launch handoff verifier artifact: pass (artifactCoverage=2") && qualityReceiptReadyText.includes("safeToDispatch=false") && qualityReceiptReadyText.includes("json=data/launch-handoff-verification.json") && qualityReceiptReadyText.includes("markdown=data/launch-handoff-verification.md") && qualityReceiptReadyText.includes("Launch handoff verifier artifact:") && qualityReceiptReadyText.includes("status=pass; ready=true; artifactCoverage=2; write=true; safeToDispatch=false") && qualityReceiptReadyText.includes("Operator one-page handoff: pass (8 sections") && qualityReceiptReadyText.includes("successSignals=8") && qualityReceiptReadyText.includes("active=" + outputQuality.dataset.outputQualityAuditBlockerResolutionActive) && qualityReceiptReadyText.includes("postInstallEvidenceIntake=collect_post_install_proof; fields=" + outputQualityPostInstallCompletedCount + "/6; proofComplete=false") && qualityReceiptReadyText.includes("dispatchGuard=Saved verifier artifacts are verification-only"), "output quality handoff verifier artifact ledger was not copy-ready");
    assert(qualityReceiptReadyText.includes("Main PR bridge plan: pass (strategy=main-subdirectory-bridge") && qualityReceiptReadyText.includes("noCommonHistory=true") && qualityReceiptReadyText.includes("appPath=apps/joopark-workspace") && qualityReceiptReadyText.includes("bridgeBranch=codex/joopark-workspace-main-bridge") && qualityReceiptReadyText.includes("Main PR bridge plan:") && qualityReceiptReadyText.includes("status=pass; ready=true; strategy=main-subdirectory-bridge; noCommonHistory=true; mainAppPathExists=true") && qualityReceiptReadyText.includes("commandCount=6; externalComparison=2") && qualityReceiptReadyText.includes("git switch -c codex/joopark-workspace-main-bridge"), "output quality main bridge plan ledger was not copy-ready");
	    assert(qualityReceiptReadyText.includes("Blocker resolution checklist: blocked (active=" + outputQuality.dataset.outputQualityAuditBlockerResolutionActive) && qualityReceiptReadyText.includes("4/6 pass") && qualityReceiptReadyText.includes("actionRequired=" + outputQuality.dataset.outputQualityAuditBlockerResolutionActionRequiredCount) && qualityReceiptReadyText.includes("deferred=1") && qualityReceiptReadyText.includes("proofCommands=6") && qualityReceiptReadyText.includes("Blocker resolution checklist:") && qualityReceiptReadyText.includes("proofCommand=node scripts/check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write") && qualityReceiptReadyText.includes("expectedValue=remoteWorkflowFilesReady=true") && qualityReceiptReadyText.includes("stopCondition=If any workflow file is missing_on_default_branch or sha_mismatch"), "output quality blocker resolution checklist was not copy-ready");
    assert(qualityReceiptReadyText.includes("Specific context: pass") && qualityReceiptReadyText.includes("immediate action: Install workflows on the default branch") && qualityReceiptReadyText.includes("deferred evidence capture: Capture live publish evidence") && !qualityReceiptReadyText.includes("next action: Capture live publish evidence"), "output quality specific context did not prioritize the immediate action");
	    assert(qualityReceiptReadyText.includes("Remote workflow file acceptance ledger: blocked (1/2 files ready, missing=0, mismatch=1, status=remote_file_install_required)") && qualityReceiptReadyText.includes("Publish JooPark Pages: sha_mismatch") && qualityReceiptReadyText.includes("Watch JooPark Candidate Drift: ready") && qualityReceiptReadyText.includes("remoteExists=true") && qualityReceiptReadyText.includes("remoteMatchesTemplate=false"), "output quality remote workflow file acceptance ledger was not copy-ready");
	    assert(qualityReceiptReadyText.includes("Launch proof acceptance ledger: blocked (5/6 ready, pending=1, gate=capture_launch_proof, status=proof_blocked_until_dispatch)") && qualityReceiptReadyText.includes("Pages site URL/status: ready") && qualityReceiptReadyText.includes("Pages workflow run: ready") && qualityReceiptReadyText.includes("Drift Watch workflow run: ready") && qualityReceiptReadyText.includes("Public claim guard: guarded") && qualityReceiptReadyText.includes("capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --write"), "output quality launch proof acceptance ledger was not copy-ready");
	    assert(qualityReceiptReadyText.includes("External completion claim guard:") && qualityReceiptReadyText.includes("status=blocked_external_claim; ready=false; blocked=" + outputQualityExternalClaimGuardBlockedCount + "/3") && qualityReceiptReadyText.includes("signal readyForExternalClaim=false") && qualityReceiptReadyText.includes("proofCommand node scripts/verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown") && qualityReceiptReadyText.includes("Stop condition: do not claim readyForExternalClaim"), "output quality external claim guard receipt section was not copy-ready");
	    window.__smokeClipboardText = "";
	    click("[data-output-quality-audit-receipt-copy]", outputQuality);
	    await waitFor(() => qualityReceipt.dataset.outputQualityAuditReceiptCopied === "true" && qs("[data-output-quality-audit-receipt-copy-status]", qualityReceipt).textContent.includes("복사"), "output quality audit receipt copy did not report success");
	    await waitFor(() => outputQualityReceiptHasCurrentLaunchState(window.__smokeClipboardText), "output quality audit receipt copy text did not reach current clipboard state");
	    if (!outputQualityReceiptHasCurrentLaunchState(window.__smokeClipboardText)) {
	    await waitFor(() => window.__smokeClipboardText.includes("JooPark Final Output Quality Audit Receipt") && window.__smokeClipboardText.includes("release quality ready; public launch proof blocked") && window.__smokeClipboardText.includes("Repo: biojuho/BIOJUHO-Projects") && window.__smokeClipboardText.includes(expectedOutputQualityEvidenceRepoLine) && !window.__smokeClipboardText.includes("\\nRepo: OWNER/REPO") && window.__smokeClipboardText.includes("Workflow scope refresh command: gh auth refresh -h github.com -s workflow") && window.__smokeClipboardText.includes("Remote workflow files ready: false") && window.__smokeClipboardText.includes("Launch packet readyForExternalClaim: false") && window.__smokeClipboardText.includes("Source evidence freshness:") && window.__smokeClipboardText.includes("sourceEvidenceFresh=true; staleSources=0; sources=7") && window.__smokeClipboardText.includes("remote workflow file check: fresh") && window.__smokeClipboardText.includes("launch handoff verification: fresh") && window.__smokeClipboardText.includes("main bridge plan: fresh") && window.__smokeClipboardText.includes("Output readiness snapshot:") && window.__smokeClipboardText.includes("First-run guided start: pass (3 items, coverage=1)") && window.__smokeClipboardText.includes("Review package decision brief: pass (6 fields, coverage=1)") && window.__smokeClipboardText.includes("Review issue decision summary: pass (6 fields, coverage=1)") && window.__smokeClipboardText.includes("Review comment/note decision summary: pass (6 fields, coverage=1)") && window.__smokeClipboardText.includes("Tracker form payloads: pass (11 fields, checksums ready)") && window.__smokeClipboardText.includes("Runtime issues: console 0, network 0, layout 0") && window.__smokeClipboardText.includes("Workflow auth preflight: pass (uiVerified=true, workflowScopeAvailable=false, workflowScopeInstallBlocked=true, missing=workflow, scopes=gist, read:org, repo)") && window.__smokeClipboardText.includes(outputQualityLaunchPostAuthCheckpointExpectedSummary) && outputQualityWorkflowUiInstallReceiptSummaryReady(window.__smokeClipboardText) && window.__smokeClipboardText.includes("Launch handoff verifier artifact: pass") && window.__smokeClipboardText.includes("Main PR bridge plan: pass") && window.__smokeClipboardText.includes("Operator one-page handoff: pass") && window.__smokeClipboardText.includes("successSignals=8") && window.__smokeClipboardText.includes("Launch acceptance checklist: 2/5 pass, pending=3, stage=install_workflows") && window.__smokeClipboardText.includes("Launch install path options: pass (2 paths, 14 commands; CLI path after workflow scope | GitHub UI path)") && window.__smokeClipboardText.includes("Artifact quality rubric:") && window.__smokeClipboardText.includes("artifactQualityRubric=pass; totalScore=100/100; passingScore=90") && window.__smokeClipboardText.includes("Required form fit: pass (20/20)") && window.__smokeClipboardText.includes("Copy-ready completeness: pass (20/20)") && window.__smokeClipboardText.includes("Safety guardrails: pass (20/20)") && window.__smokeClipboardText.includes("CLI path after workflow scope") && window.__smokeClipboardText.includes("GitHub UI path") && window.__smokeClipboardText.includes("node scripts/install-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write --verify") && window.__smokeClipboardText.includes("pbcopy < 'docs/github-pages-workflow.yml'") && window.__smokeClipboardText.includes("Publish evidence command guard: pass (7 safe suggestions, 0 suggested dispatch, 2 withheld dispatch, active=0, reference=2, disposition=withheld_until_all_dispatch_ready)") && window.__smokeClipboardText.includes("Publish evidence immediate action: pass (install_workflows from data/launch-execution-packet.json, deferred capture-live-evidence)") && window.__smokeClipboardText.includes("Immediate command: gh auth refresh -h github.com -s workflow") && window.__smokeClipboardText.includes("Deferred evidence capture: Capture live publish evidence") && window.__smokeClipboardText.includes("Remote workflow file check: pages: remote workflow file is not installed on main") && window.__smokeClipboardText.includes("Prompt-to-artifact checklist:") && window.__smokeClipboardText.includes("goalCompletionAudit=output_quality_goal_covered") && window.__smokeClipboardText.includes("External output comparison: pass") && window.__smokeClipboardText.includes("Completion audit:") && window.__smokeClipboardText.includes("Source evidence freshness: pass") && window.__smokeClipboardText.includes("Workflow installation: blocked") && window.__smokeClipboardText.includes("Public launch proof: blocked") && window.__smokeClipboardText.includes("launchPacketReadyForExternalClaim=false") && window.__smokeClipboardText.includes("readyForExternalClaim=false") && window.__smokeClipboardText.includes("External comparison:") && window.__smokeClipboardText.includes("GitHub issue forms validation") && window.__smokeClipboardText.includes("GitHub Actions job summaries") && window.__smokeClipboardText.includes("GitHub Releases") && window.__smokeClipboardText.includes("Linear issue templates") && window.__smokeClipboardText.includes("Jira required fields") && window.__smokeClipboardText.includes("Public launch proof: blocked") && window.__smokeClipboardText.includes("node scripts/capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --markdown"), "output quality audit receipt copy text did not reach clipboard");
	    }
	    assert(window.__smokeClipboardText.includes("Review comment/note decision summary: pass (6 fields, coverage=1)"), "output quality comment/note decision summary copy did not reach clipboard");
	    assert(window.__smokeClipboardText.includes("guard=Do not run gh workflow run until every action_required post-auth checkpoint item has passed and verify-launch-handoff reports safeToDispatch=true."), "output quality launch post-auth checkpoint guard copy did not reach clipboard");
	    assert(window.__smokeClipboardText.includes("guard=Do not run gh workflow run until every post-install evidence field has been filled") && window.__smokeClipboardText.includes("verify-launch-handoff reports safeToDispatch=true."), "output quality workflow UI paste packet guard copy did not reach clipboard");
		    assert(window.__smokeClipboardText.includes("First-run guided start: pass (3 items, coverage=1)"), "output quality first-run guided start copy did not reach clipboard");
		    assert(window.__smokeClipboardText.includes("Global help access: pass (4 actions, coverage=1)"), "output quality global help access copy did not reach clipboard");
		    assert(window.__smokeClipboardText.includes("Topbar data safety: pass (4 actions, coverage=1)"), "output quality topbar data safety copy did not reach clipboard");
		    assert(window.__smokeClipboardText.includes("Route deep link: pass (coverage=1)"), "output quality route deep link copy did not reach clipboard");
			    assert(window.__smokeClipboardText.includes("Output variant comparison:") && window.__smokeClipboardText.includes("decision=recheck_before_claim; selected=recheck_required") && window.__smokeClipboardText.includes("A: generic generated summary: rejected") && window.__smokeClipboardText.includes("B: copy-ready evidence receipt: needs_recheck"), "output quality guarded output variant comparison copy did not reach clipboard");
	    assert(window.__smokeClipboardText.includes("Review result repair action plan: pass (6 fields, coverage=1)"), "output quality repair action plan copy did not reach clipboard");
	    assert(window.__smokeClipboardText.includes("Review submission closeout summary: pass (6 fields, coverage=1)"), "output quality submission closeout summary copy did not reach clipboard");
	    assert(window.__smokeClipboardText.includes("Post-install evidence intake: pass (6 fields, coverage=1)") && outputQualityPostInstallProofParserReady(window.__smokeClipboardText), "output quality post-install evidence intake copy did not reach clipboard");
	    assert(outputQualityPostInstallProofParserReady(window.__smokeClipboardText), "output quality post-install proof parser copy did not reach clipboard");
		    assert(window.__smokeClipboardText.includes("Post-install quick proof: pass (4 steps, coverage=1)") && window.__smokeClipboardText.includes("quickProofReady=true; steps=4; coverage=1") && window.__smokeClipboardText.includes("Post-install quick proof field mapping: pass (") && window.__smokeClipboardText.includes("quickProofFieldMappingReady=true; mapped=4; completed="), "output quality post-install quick proof copy did not reach clipboard");
		    assert(window.__smokeClipboardText.includes("source=generated_from_launch_execution_packet; status=collect_post_install_proof; proofComplete=false; completed=" + outputQualityPostInstallCompletedCount + "/6; commands=4; signals=8") && window.__smokeClipboardText.includes("quick proof 1 remote_file_parity: evidence_required") && window.__smokeClipboardText.includes("quick proof 4 handoff_verifier: evidence_required") && window.__smokeClipboardText.includes("quick proof field 1 remote_file_parity -> remote_parity_proof") && window.__smokeClipboardText.includes("quick proof field 4 handoff_verifier -> handoff_verifier_proof") && window.__smokeClipboardText.includes("remote_parity_proof: evidence_required") && window.__smokeClipboardText.includes("handoff_verifier_proof: evidence_required"), "output quality post-install evidence intake ledger copy did not reach clipboard");
	    assert(window.__smokeClipboardText.includes("Launch proof evidence receipt: pass (6 fields, coverage=1, nextActions=6/6)"), "output quality launch proof evidence receipt copy did not reach clipboard");
    assert(window.__smokeClipboardText.includes("Launch handoff verifier artifact: pass (artifactCoverage=2") && window.__smokeClipboardText.includes("safeToDispatch=false") && window.__smokeClipboardText.includes("json=data/launch-handoff-verification.json") && window.__smokeClipboardText.includes("markdown=data/launch-handoff-verification.md") && window.__smokeClipboardText.includes("status=pass; ready=true; artifactCoverage=2; write=true; safeToDispatch=false") && window.__smokeClipboardText.includes("handoffVerifierArtifact=true"), "output quality handoff verifier artifact copy did not reach clipboard");
    assert(window.__smokeClipboardText.includes("Main PR bridge plan: pass (strategy=main-subdirectory-bridge") && window.__smokeClipboardText.includes("noCommonHistory=true") && window.__smokeClipboardText.includes("appPath=apps/joopark-workspace") && window.__smokeClipboardText.includes("bridgeBranch=codex/joopark-workspace-main-bridge") && window.__smokeClipboardText.includes("status=pass; ready=true; strategy=main-subdirectory-bridge; noCommonHistory=true; mainAppPathExists=true") && window.__smokeClipboardText.includes("commandCount=6; externalComparison=2") && window.__smokeClipboardText.includes("mainBridgePlan=true"), "output quality main bridge plan copy did not reach clipboard");
	    assert(window.__smokeClipboardText.includes("Blocker resolution checklist: blocked (active=" + outputQuality.dataset.outputQualityAuditBlockerResolutionActive) && window.__smokeClipboardText.includes("4/6 pass") && window.__smokeClipboardText.includes("actionRequired=" + outputQuality.dataset.outputQualityAuditBlockerResolutionActionRequiredCount) && window.__smokeClipboardText.includes("proofCommand=node scripts/check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write") && window.__smokeClipboardText.includes("stopCondition=If any workflow file is missing_on_default_branch or sha_mismatch"), "output quality blocker resolution checklist copy did not reach clipboard");
    assert(window.__smokeClipboardText.includes("Specific context: pass") && window.__smokeClipboardText.includes("immediate action: Install workflows on the default branch") && window.__smokeClipboardText.includes("deferred evidence capture: Capture live publish evidence") && !window.__smokeClipboardText.includes("next action: Capture live publish evidence"), "output quality specific context copy did not prioritize the immediate action");
	    assert(window.__smokeClipboardText.includes("Remote workflow file acceptance ledger: blocked (1/2 files ready, missing=0, mismatch=1, status=remote_file_install_required)") && window.__smokeClipboardText.includes("Publish JooPark Pages: sha_mismatch") && window.__smokeClipboardText.includes("remoteMatchesTemplate=false"), "output quality remote workflow file acceptance ledger copy did not reach clipboard");
	    assert(window.__smokeClipboardText.includes("Launch proof acceptance ledger: blocked (5/6 ready, pending=1, gate=capture_launch_proof, status=proof_blocked_until_dispatch)") && window.__smokeClipboardText.includes("Pages site URL/status: ready") && window.__smokeClipboardText.includes("Public claim guard: guarded"), "output quality launch proof acceptance ledger copy did not reach clipboard");
	    assert(window.__smokeClipboardText.includes("External completion claim guard:") && window.__smokeClipboardText.includes("status=blocked_external_claim; ready=false; blocked=" + outputQualityExternalClaimGuardBlockedCount + "/3") && window.__smokeClipboardText.includes("signal readyForExternalClaim=false") && window.__smokeClipboardText.includes("Stop condition: do not claim readyForExternalClaim"), "output quality external claim guard receipt copy did not reach clipboard");
	    outputQualityAuditReceiptOk = true;
	    }
    const publishHandoffCopy = qs("[data-system-publish-handoff-copy]", panel);
    const publishHandoffText = publishHandoffCopy.dataset.systemPublishHandoffText || "";
    assert(publishHandoffText.includes("JooPark Workspace Publish Unblock Handoff") && publishHandoffText.includes("workflowScopeAvailable") && publishHandoffText.includes("workflowScope.scopes") && publishHandoffText.includes("workflowScopeInstallBlocked") && publishHandoffText.includes("gh auth refresh -h github.com -s workflow") && publishHandoffText.includes("auth preflight only") && publishHandoffText.includes("plan-workflow-ui-install.mjs --dry-run --markdown") && publishHandoffText.includes("template sha256") && publishHandoffText.includes("githubNewFileUrl") && publishHandoffText.includes("githubWorkflowUrl") && publishHandoffText.includes("templateCopyCommand") && publishHandoffText.includes("githubNewFileOpenCommand") && publishHandoffText.includes("githubWorkflowOpenCommand") && publishHandoffText.includes("defaultBranch") && publishHandoffText.includes("nextVerificationCommand") && publishHandoffText.includes(".github/workflows/joopark-pages.yml") && publishHandoffText.includes(".github/workflows/joopark-drift-watch.yml") && publishHandoffText.includes("check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write") && publishHandoffText.includes("remoteWorkflowFilesReady") && publishHandoffText.includes("remoteMatchesTemplate") && publishHandoffText.includes("Remote workflow install packet") && publishHandoffText.includes("install packet 복사") && publishHandoffText.includes("Repo placeholder guard") && publishHandoffText.includes("Dispatch safety gate") && publishHandoffText.includes("suggestedDispatchCommands") && publishHandoffText.includes("withheld-until-all-dispatch-ready") && publishHandoffText.includes("Replace every") && publishHandoffText.includes("OWNER/REPO") && publishHandoffText.includes("suggestedRepo") && publishHandoffText.includes("biojuho/BIOJUHO-Projects") && publishHandoffText.includes("plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects") && publishHandoffText.includes("repo placeholder OWNER/REPO") && publishHandoffText.includes("capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --markdown") && publishHandoffText.includes("postPublishEvidenceReady"), "publish unblock handoff copy text is incomplete");
    assert(publishHandoffText.includes("Device-code approval handoff") && publishHandoffText.includes("https://github.com/login/device") && publishHandoffText.includes("one-time device code") && publishHandoffText.includes("workflowScopeAvailable: true") && publishHandoffText.includes("workflowScopeInstallBlocked: false"), "publish unblock handoff did not include device-code approval handoff");
    window.__smokeClipboardText = "";
    click("[data-system-publish-handoff-copy]", panel);
    await waitFor(() => publishHandoffCopy.dataset.systemPublishHandoffCopied === "true" && panel.querySelector("[data-system-publish-handoff-copy-status]").textContent.includes("복사"), "publish unblock handoff copy did not report success");
    await waitFor(() => window.__smokeClipboardText.includes("JooPark Workspace Publish Unblock Handoff") && window.__smokeClipboardText.includes("workflowScopeAvailable") && window.__smokeClipboardText.includes("workflowScope.scopes") && window.__smokeClipboardText.includes("workflowScopeInstallBlocked") && window.__smokeClipboardText.includes("gh auth refresh -h github.com -s workflow") && window.__smokeClipboardText.includes("plan-workflow-ui-install.mjs --dry-run --markdown") && window.__smokeClipboardText.includes("githubNewFileUrl") && window.__smokeClipboardText.includes("templateCopyCommand") && window.__smokeClipboardText.includes("githubNewFileOpenCommand") && window.__smokeClipboardText.includes("githubWorkflowOpenCommand") && window.__smokeClipboardText.includes("Publish JooPark Pages") && window.__smokeClipboardText.includes("check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write") && window.__smokeClipboardText.includes("remoteWorkflowFilesReady") && window.__smokeClipboardText.includes("Remote workflow install packet") && window.__smokeClipboardText.includes("Repo placeholder guard") && window.__smokeClipboardText.includes("Dispatch safety gate") && window.__smokeClipboardText.includes("suggestedDispatchCommands") && window.__smokeClipboardText.includes("withheld-until-all-dispatch-ready") && window.__smokeClipboardText.includes("suggestedRepo") && window.__smokeClipboardText.includes("nextVerificationCommand"), "publish unblock handoff copy text did not reach clipboard");
    assert(window.__smokeClipboardText.includes("Device-code approval handoff") && window.__smokeClipboardText.includes("https://github.com/login/device") && window.__smokeClipboardText.includes("one-time device code"), "publish unblock handoff device-code text did not reach clipboard");
    await nav("settings");
    const deployButton = qs('[data-settings-handoff-copy="deploy"]');
    const handoff = deployButton.dataset.settingsHandoffText || "";
    assert(handoff.includes("## Publish readiness") && handoff.includes("## Release gate evidence") && handoff.includes("package + manifest/source parity pass") && handoff.includes("mobile search-empty 13 routes including llm-wiki") && handoff.includes("keyboard/ARIA accessibility pass") && handoff.includes("workflow scope preflight") && handoff.includes("workflowScopeAvailable") && handoff.includes("workflowScope.scopes") && handoff.includes("workflowScopeInstallBlocked") && handoff.includes("gh auth refresh -h github.com -s workflow") && handoff.includes("Device-code approval handoff") && handoff.includes("approvalUrl=https://github.com/login/device") && handoff.includes("one-time device code") && handoff.includes("gh auth status -h github.com") && handoff.includes("workflowScopeAvailable: true") && handoff.includes("workflowScopeInstallBlocked: false") && handoff.includes("install-remote-workflow-files.mjs") && handoff.includes("public launch copy") && handoff.includes("archive proof") && handoff.includes("GitHub UI install plan") && handoff.includes("plan-workflow-ui-install.mjs --dry-run --markdown") && handoff.includes("githubNewFileUrl") && handoff.includes("githubWorkflowUrl") && handoff.includes("templateCopyCommand") && handoff.includes("githubNewFileOpenCommand") && handoff.includes("githubWorkflowOpenCommand") && handoff.includes("defaultBranch") && handoff.includes("nextVerificationCommand") && handoff.includes("check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write") && handoff.includes("remoteWorkflowFilesReady") && handoff.includes("remoteMatchesTemplate") && handoff.includes("Remote workflow install packet") && handoff.includes("install packet 복사") && handoff.includes("Repo placeholder guard") && handoff.includes("Dispatch safety gate") && handoff.includes("suggestedDispatchCommands") && handoff.includes("withheld-until-all-dispatch-ready") && handoff.includes("Replace every") && handoff.includes("OWNER/REPO") && handoff.includes("suggestedRepo") && handoff.includes("biojuho/BIOJUHO-Projects") && handoff.includes("Pages workflow 설치") && handoff.includes("Drift Watch 설치") && handoff.includes("Remote workflow file check") && handoff.includes("Publish dispatch dry-run") && handoff.includes("plan-publish-dispatch.mjs --dry-run") && handoff.includes("plan-publish-dispatch.mjs --live --repo OWNER/REPO") && handoff.includes("plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects") && handoff.includes("repoEvidenceReady") && handoff.includes("dispatchReady") && handoff.includes("driftDispatchReady") && handoff.includes("allDispatchReady") && handoff.includes("joopark-drift-watch.yml") && handoff.includes("Publish 실행") && handoff.includes("Publish evidence capture") && handoff.includes("capture-publish-evidence.mjs --live --repo OWNER/REPO --markdown") && handoff.includes("postPublishEvidenceReady"), "settings deploy handoff did not mirror system publish readiness");
    systemPublishReadinessOk = true;
  });

  await runStep("llm wiki article actions create local drafts", async () => {
    assert(window.JooParkLlmWikiView && window.JooParkLlmWikiView.version === "joopark-llm-wiki-view/v1", "llm wiki runtime module was not loaded");
    async function openStructuredOutputArticle() {
      await nav("llm-wiki");
      const view = qs("#view-llm-wiki");
      const apiCat = qsa(".wiki-cat", view).find((button) => button.textContent.includes("Claude API"));
      assert(apiCat, "llm wiki Claude API category was not visible");
      apiCat.click();
      await waitFor(() => qsa(".wiki-card-open", view).some((button) => button.textContent.includes("구조화 출력")), "llm wiki API category cards did not render");
      const structuredCard = qsa(".wiki-card-open", view).find((button) => button.textContent.includes("구조화 출력"));
      structuredCard.click();
      await waitFor(() => document.querySelector("#view-llm-wiki [data-wiki-action-panel]"), "llm wiki article action panel did not render");
      return qs("#view-llm-wiki [data-wiki-action-panel]");
    }
    let panel = await openStructuredOutputArticle();
    const articleId = panel.dataset.wikiActionArticle;
    assert(panel.dataset.wikiActionCount === "3" && panel.textContent.includes("실행으로 보내기") && panel.textContent.includes("로컬 저장 전용"), "llm wiki action panel metadata was incomplete");

    click('[data-action="llm-wiki-create-todo"]', panel);
    await waitFor(() => dashboard.currentView === "todo" && location.hash === "#todo", "llm wiki todo action did not navigate to todo");
    const todoKey = "llm-wiki:todo:" + articleId;
    const todoDraft = savedPayload().todos.find((todo) => todo.sourceKey === todoKey);
    assert(todoDraft && todoDraft.title.includes("[LLM Wiki]") && todoDraft.category === "LLM Wiki" && todoDraft.memo.includes("Action prompt") && todoDraft.memo.includes("Sources"), "llm wiki todo draft was not persisted with source metadata");
    await waitFor(() => state.todoSourceFilter === "wiki" && qs('#view-todo [data-todo-source-filterbar]').dataset.todoSourceFilterCurrent === "wiki", "llm wiki todo source filter did not activate");
    let todoSourceFilterbar = qs('#view-todo [data-todo-source-filterbar]');
    assert(qs('[data-todo-source-filter="wiki"]', todoSourceFilterbar).dataset.todoSourceFilterCount === "1" && qsa('#view-todo [data-search-result="todo"]').length === 1 && qsa('#view-todo [data-search-result="todo"]').every((row) => row.querySelector('[data-source-record-kind="todo"]')), "llm wiki todo source filter did not isolate wiki todos");
    click('[data-action="todo-source-filter"][data-todo-source-filter="all"]', todoSourceFilterbar);
    await waitFor(() => state.todoSourceFilter === "all" && qs('#view-todo [data-todo-source-filterbar]').dataset.todoSourceFilterCurrent === "all", "llm wiki todo source filter did not reset to all");
    todoSourceFilterbar = qs('#view-todo [data-todo-source-filterbar]');
    click('[data-action="todo-source-filter"][data-todo-source-filter="wiki"]', todoSourceFilterbar);
    await waitFor(() => state.todoSourceFilter === "wiki" && qsa('#view-todo [data-search-result="todo"]').length === 1, "llm wiki todo source filter did not reapply wiki scope");
    const todoSourceReturn = qs('#view-todo [data-action="open-llm-wiki-source"][data-source-record-kind="todo"][data-source-record-id="' + todoDraft.id + '"]');
    assert(todoSourceReturn.dataset.sourceKey === todoKey && todoSourceReturn.dataset.sourceArticleId === articleId && todoSourceReturn.textContent.includes("LLM Wiki"), "llm wiki todo source return badge did not render");
    todoSourceReturn.click();
    await waitFor(() => dashboard.currentView === "llm-wiki" && location.hash === "#llm-wiki" && qs("#view-llm-wiki .wiki-crumb-current").textContent.includes("구조화 출력"), "llm wiki todo source return did not open original article");
    const todoRecordBacklink = qs('#view-llm-wiki [data-source-backlink][data-source-backlink-record-kind="todo"]');
    assert(todoRecordBacklink.dataset.sourceBacklinkRecordId === todoDraft.id && todoRecordBacklink.textContent.includes("할 일로 돌아가기") && todoRecordBacklink.textContent.includes(todoDraft.title), "llm wiki todo source backlink did not render the originating todo");
    click('[data-action="open-source-backlink-record"]', todoRecordBacklink);
    await waitFor(() => dashboard.currentView === "todo" && state.todoFilter === "all" && document.querySelector("#modal.open #todoForm"), "llm wiki todo source backlink did not reopen originating todo modal");
    assert(qs('#modal.open #todoForm [name="title"]').value === todoDraft.title, "llm wiki todo source backlink opened the wrong todo");
    click('#modal [data-action="close-modal"]');
    await waitFor(() => !document.querySelector("#modal.open"), "llm wiki todo source backlink modal did not close");

    panel = await openStructuredOutputArticle();
    click('[data-action="llm-wiki-create-note"]', panel);
    await waitFor(() => dashboard.currentView === "notes" && location.hash === "#notes", "llm wiki note action did not navigate to notes");
    const noteKey = "llm-wiki:note:" + articleId;
    const noteDraft = savedPayload().notes.find((note) => note.sourceKey === noteKey);
    assert(noteDraft && noteDraft.pinned && noteDraft.body.includes("Action prompt") && noteDraft.body.includes("Source key: llm-wiki:" + articleId), "llm wiki note draft was not persisted with source metadata");
    await waitFor(() => state.noteSourceFilter === "wiki" && qs('#view-notes [data-note-source-filterbar]').dataset.noteSourceFilterCurrent === "wiki", "llm wiki note source filter did not activate");
    let noteSourceFilterbar = qs('#view-notes [data-note-source-filterbar]');
    assert(qs('[data-note-source-filter="wiki"]', noteSourceFilterbar).dataset.noteSourceFilterCount === "1" && qsa('#view-notes [data-search-result="notes"]').length === 1 && qsa('#view-notes [data-search-result="notes"]').every((card) => card.querySelector('[data-source-record-kind="note"]')), "llm wiki note source filter did not isolate wiki notes");
    click('[data-action="note-source-filter"][data-note-source-filter="all"]', noteSourceFilterbar);
    await waitFor(() => state.noteSourceFilter === "all" && qs('#view-notes [data-note-source-filterbar]').dataset.noteSourceFilterCurrent === "all", "llm wiki note source filter did not reset to all");
    noteSourceFilterbar = qs('#view-notes [data-note-source-filterbar]');
    click('[data-action="note-source-filter"][data-note-source-filter="wiki"]', noteSourceFilterbar);
    await waitFor(() => state.noteSourceFilter === "wiki" && qsa('#view-notes [data-search-result="notes"]').length === 1, "llm wiki note source filter did not reapply wiki scope");
    llmWikiTodoNoteSourceFilterOk = true;
    click('[data-action="open-palette"]');
    fill("#paletteInput", "할 일 LLM Wiki");
    await waitFor(() => qsa("#paletteResults .pal-item").some((item) => item.textContent.includes("할 일: LLM Wiki 출처 보기")), "todo source filter command did not render in palette");
    qsa("#paletteResults .pal-item").find((item) => item.textContent.includes("할 일: LLM Wiki 출처 보기")).click();
    await waitFor(() => dashboard.currentView === "todo" && state.todoSourceFilter === "wiki" && qs('#view-todo [data-todo-source-filterbar]').dataset.todoSourceFilterCurrent === "wiki", "todo source palette command did not apply wiki filter");
    assert(qsa('#view-todo [data-search-result="todo"]').length === 1 && qsa('#view-todo [data-search-result="todo"]').every((row) => row.querySelector('[data-source-record-kind="todo"]')), "todo source palette command did not isolate wiki todos");
    click('[data-action="open-palette"]');
    fill("#paletteInput", "메모 LLM Wiki");
    await waitFor(() => qsa("#paletteResults .pal-item").some((item) => item.textContent.includes("메모: LLM Wiki 출처 보기")), "note source filter command did not render in palette");
    qsa("#paletteResults .pal-item").find((item) => item.textContent.includes("메모: LLM Wiki 출처 보기")).click();
    await waitFor(() => dashboard.currentView === "notes" && state.noteSourceFilter === "wiki" && qs('#view-notes [data-note-source-filterbar]').dataset.noteSourceFilterCurrent === "wiki", "note source palette command did not apply wiki filter");
    assert(qsa('#view-notes [data-search-result="notes"]').length === 1 && qsa('#view-notes [data-search-result="notes"]').every((card) => card.querySelector('[data-source-record-kind="note"]')), "note source palette command did not isolate wiki notes");
    click('[data-action="open-palette"]');
    fill("#paletteInput", "할 일 위키 출처");
    await waitFor(() => qsa("#paletteResults .pal-item").some((item) => item.textContent.includes("할 일: LLM Wiki 출처 보기")), "todo Korean source filter command did not render in palette");
    qsa("#paletteResults .pal-item").find((item) => item.textContent.includes("할 일: LLM Wiki 출처 보기")).click();
    await waitFor(() => dashboard.currentView === "todo" && state.todoSourceFilter === "wiki" && qs('#view-todo [data-todo-source-filterbar]').dataset.todoSourceFilterCurrent === "wiki", "todo Korean source palette command did not apply wiki filter");
    click('[data-action="open-palette"]');
    fill("#paletteInput", "할 일 전체 출처");
    await waitFor(() => qsa("#paletteResults .pal-item").some((item) => item.textContent.includes("할 일: 전체 출처 보기")), "todo Korean source reset command did not render in palette");
    qsa("#paletteResults .pal-item").find((item) => item.textContent.includes("할 일: 전체 출처 보기")).click();
    await waitFor(() => dashboard.currentView === "todo" && state.todoSourceFilter === "all" && qs('#view-todo [data-todo-source-filterbar]').dataset.todoSourceFilterCurrent === "all", "todo Korean source reset command did not clear source filter");
    assert(qsa('#view-todo [data-search-result="todo"]').length > 1 && document.querySelector('#view-todo [data-source-record-kind="todo"][data-source-record-id="' + todoDraft.id + '"]'), "todo Korean source reset command did not restore all todo rows");
    click('[data-action="open-palette"]');
    fill("#paletteInput", "메모 위키 출처");
    await waitFor(() => qsa("#paletteResults .pal-item").some((item) => item.textContent.includes("메모: LLM Wiki 출처 보기")), "note Korean source filter command did not render in palette");
    qsa("#paletteResults .pal-item").find((item) => item.textContent.includes("메모: LLM Wiki 출처 보기")).click();
    await waitFor(() => dashboard.currentView === "notes" && state.noteSourceFilter === "wiki" && qs('#view-notes [data-note-source-filterbar]').dataset.noteSourceFilterCurrent === "wiki", "note Korean source palette command did not apply wiki filter");
    click('[data-action="open-palette"]');
    fill("#paletteInput", "메모 전체 출처");
    await waitFor(() => qsa("#paletteResults .pal-item").some((item) => item.textContent.includes("메모: 전체 출처 보기")), "note Korean source reset command did not render in palette");
    qsa("#paletteResults .pal-item").find((item) => item.textContent.includes("메모: 전체 출처 보기")).click();
    await waitFor(() => dashboard.currentView === "notes" && state.noteSourceFilter === "all" && qs('#view-notes [data-note-source-filterbar]').dataset.noteSourceFilterCurrent === "all", "note Korean source reset command did not clear source filter");
    assert(qsa('#view-notes [data-search-result="notes"]').length > 1 && document.querySelector('#view-notes [data-source-record-kind="note"][data-source-record-id="' + noteDraft.id + '"]'), "note Korean source reset command did not restore all note cards");
    llmWikiTodoNoteSourcePaletteOk = true;
    click('[data-action="open-palette"]');
    fill("#paletteInput", todoDraft.title);
    await waitFor(() => qsa("#paletteResults .pal-item").some((item) => item.textContent.includes(todoDraft.title) && item.textContent.includes("할 일") && item.textContent.includes("LLM Wiki")), "llm wiki todo record search did not render sourced palette result");
    qsa("#paletteResults .pal-item").find((item) => item.textContent.includes(todoDraft.title) && item.textContent.includes("할 일") && item.textContent.includes("LLM Wiki")).click();
    await waitFor(() => dashboard.currentView === "todo" && state.todoSourceFilter === "wiki" && document.querySelector("#modal.open #todoForm"), "llm wiki todo palette result did not open todo modal in source scope");
    assert(qs('#modal.open #todoForm [name="title"]').value === todoDraft.title && qs('#modal.open [data-modal-source-link][data-source-record-kind="todo"]'), "llm wiki todo palette result opened the wrong modal");
    click('#modal [data-action="close-modal"]');
    await waitFor(() => !document.querySelector("#modal.open"), "llm wiki todo palette result modal did not close");
    click('[data-action="open-palette"]');
    fill("#paletteInput", noteDraft.title);
    await waitFor(() => qsa("#paletteResults .pal-item").some((item) => item.textContent.includes(noteDraft.title) && item.textContent.includes("메모") && item.textContent.includes("LLM Wiki")), "llm wiki note record search did not render sourced palette result");
    qsa("#paletteResults .pal-item").find((item) => item.textContent.includes(noteDraft.title) && item.textContent.includes("메모") && item.textContent.includes("LLM Wiki")).click();
    await waitFor(() => dashboard.currentView === "notes" && state.noteSourceFilter === "wiki" && document.querySelector("#modal.open #noteForm"), "llm wiki note palette result did not open note modal in source scope");
    assert(qs('#modal.open #noteForm [name="title"]').value === noteDraft.title && qs('#modal.open [data-modal-source-link][data-source-record-kind="note"]'), "llm wiki note palette result opened the wrong modal");
    click('#modal [data-action="close-modal"]');
    await waitFor(() => !document.querySelector("#modal.open"), "llm wiki note palette result modal did not close");
    llmWikiTodoNotePaletteRecordOpenOk = true;
    const noteSourceReturn = qs('#view-notes [data-action="open-llm-wiki-source"][data-source-record-kind="note"][data-source-record-id="' + noteDraft.id + '"]');
    assert(noteSourceReturn.dataset.sourceKey === noteKey && noteSourceReturn.dataset.sourceArticleId === articleId && noteSourceReturn.textContent.includes("LLM Wiki"), "llm wiki note source return badge did not render");
    noteSourceReturn.click();
    await waitFor(() => dashboard.currentView === "llm-wiki" && location.hash === "#llm-wiki" && qs("#view-llm-wiki .wiki-crumb-current").textContent.includes("구조화 출력"), "llm wiki note source return did not open original article");
    const noteRecordBacklink = qs('#view-llm-wiki [data-source-backlink][data-source-backlink-record-kind="note"]');
    assert(noteRecordBacklink.dataset.sourceBacklinkRecordId === noteDraft.id && noteRecordBacklink.textContent.includes("메모로 돌아가기") && noteRecordBacklink.textContent.includes(noteDraft.title), "llm wiki note source backlink did not render the originating note");
    click('[data-action="open-source-backlink-record"]', noteRecordBacklink);
    await waitFor(() => dashboard.currentView === "notes" && document.querySelector("#modal.open #noteForm"), "llm wiki note source backlink did not reopen originating note modal");
    assert(qs('#modal.open #noteForm [name="title"]').value === noteDraft.title, "llm wiki note source backlink opened the wrong note");
    click('#modal [data-action="close-modal"]');
    await waitFor(() => !document.querySelector("#modal.open"), "llm wiki note source backlink modal did not close");
    llmWikiTodoNoteSourceReturnOk = true;
    llmWikiTodoNoteSourceBacklinkOk = true;

    panel = await openStructuredOutputArticle();
    click('[data-action="llm-wiki-create-issue"]', panel);
    await waitFor(() => dashboard.currentView === "pm-kanban" && location.hash === "#pm-kanban", "llm wiki issue action did not navigate to kanban");
    const issueKey = "llm-wiki:issue:" + articleId;
    const issueDraft = savedPayload().issues.find((issue) => issue.sourceKey === issueKey);
    assert(issueDraft && issueDraft.labels.includes("llm-wiki") && issueDraft.body.includes("Action prompt") && issueDraft.executionChecklistReady, "llm wiki issue draft was not persisted with execution metadata");
    await waitFor(() => qs('#view-pm-kanban [data-issue-id="' + issueDraft.id + '"] [data-kanban-source-kind="llm-wiki-action"]'), "llm wiki issue did not render kanban source badge");
    assert(qs('#view-pm-kanban [data-issue-id="' + issueDraft.id + '"] [data-kanban-source-kind="llm-wiki-action"]').textContent.includes("LLM Wiki"), "llm wiki kanban source badge label did not render");
    const wikiDirectSourceBadge = qs('#view-pm-kanban [data-issue-id="' + issueDraft.id + '"] [data-kanban-source-direct-return="true"]');
    assert(wikiDirectSourceBadge.tagName === "BUTTON" && wikiDirectSourceBadge.dataset.action === "open-issue-source" && wikiDirectSourceBadge.getAttribute("aria-label").includes("LLM Wiki"), "llm wiki source badge did not expose direct source return button");
    click('#view-pm-kanban [data-action="filter-kanban-source"][data-kanban-source-filter="wiki"]');
    await waitFor(() => qs('#view-pm-kanban [data-kanban-source-filterbar]').dataset.kanbanSourceFilterCurrent === "wiki", "llm wiki source filter did not activate");
    assert(qs('#view-pm-kanban [data-issue-id="' + issueDraft.id + '"]') && qsa('#view-pm-kanban [data-search-result="pm-kanban"]').every((card) => card.querySelector('[data-kanban-source-kind="llm-wiki-action"]')), "llm wiki source filter did not isolate wiki issues");
    click('#view-pm-kanban [data-action="filter-kanban-source"][data-kanban-source-filter="all"]');
    await waitFor(() => qs('#view-pm-kanban [data-kanban-source-filterbar]').dataset.kanbanSourceFilterCurrent === "all", "llm wiki source filter did not reset to all");
    click('[data-action="open-palette"]');
    fill("#paletteInput", "Kanban LLM Wiki");
    await waitFor(() => qsa("#paletteResults .pal-item").some((item) => item.textContent.includes("Kanban: LLM Wiki 출처 보기")), "kanban source filter command did not render in palette");
    qsa("#paletteResults .pal-item").find((item) => item.textContent.includes("Kanban: LLM Wiki 출처 보기")).click();
    await waitFor(() => dashboard.currentView === "pm-kanban" && qs('#view-pm-kanban [data-kanban-source-filterbar]').dataset.kanbanSourceFilterCurrent === "wiki", "kanban source palette command did not apply wiki filter");
    const wikiSourceSummary = qs('#view-pm-kanban [data-kanban-source-summary]');
    assert(wikiSourceSummary && wikiSourceSummary.dataset.kanbanSourceSummaryFilter === "wiki" && wikiSourceSummary.dataset.kanbanSourceSummaryCount === "1" && wikiSourceSummary.textContent.includes("LLM Wiki") && wikiSourceSummary.textContent.includes("1건"), "kanban source palette command did not render active source summary");
    assert(qs('#view-pm-kanban [data-issue-id="' + issueDraft.id + '"]') && qsa('#view-pm-kanban [data-search-result="pm-kanban"]').every((card) => card.querySelector('[data-kanban-source-kind="llm-wiki-action"]')), "kanban source palette command did not isolate wiki source issues");
    click('[data-action="filter-kanban-source"][data-kanban-source-filter="all"]', wikiSourceSummary);
    await waitFor(() => qs('#view-pm-kanban [data-kanban-source-filterbar]').dataset.kanbanSourceFilterCurrent === "all", "kanban source palette command did not allow reset to all");
    click('[data-action="open-palette"]');
    fill("#paletteInput", "칸반 위키 출처");
    await waitFor(() => qsa("#paletteResults .pal-item").some((item) => item.textContent.includes("Kanban: LLM Wiki 출처 보기")), "kanban Korean source filter command did not render in palette");
    qsa("#paletteResults .pal-item").find((item) => item.textContent.includes("Kanban: LLM Wiki 출처 보기")).click();
    await waitFor(() => dashboard.currentView === "pm-kanban" && qs('#view-pm-kanban [data-kanban-source-filterbar]').dataset.kanbanSourceFilterCurrent === "wiki", "kanban Korean source palette command did not apply wiki filter");
    assert(qs('#view-pm-kanban [data-issue-id="' + issueDraft.id + '"]') && qsa('#view-pm-kanban [data-search-result="pm-kanban"]').every((card) => card.querySelector('[data-kanban-source-kind="llm-wiki-action"]')), "kanban Korean source palette command did not isolate wiki source issues");
    click('[data-action="open-palette"]');
    fill("#paletteInput", "칸반 전체 출처");
    await waitFor(() => qsa("#paletteResults .pal-item").some((item) => item.textContent.includes("Kanban: 전체 출처 보기")), "kanban Korean source reset command did not render in palette");
    qsa("#paletteResults .pal-item").find((item) => item.textContent.includes("Kanban: 전체 출처 보기")).click();
    await waitFor(() => dashboard.currentView === "pm-kanban" && qs('#view-pm-kanban [data-kanban-source-filterbar]').dataset.kanbanSourceFilterCurrent === "all", "kanban Korean source reset command did not clear source filter");
    assert(qs('#view-pm-kanban [data-issue-id="' + issueDraft.id + '"]') && qsa('#view-pm-kanban [data-search-result="pm-kanban"]').length > 1, "kanban Korean source reset command did not restore all issue cards");
    sourceKoreanResetCommandOk = true;
    click('[data-action="open-palette"]');
    fill("#paletteInput", "칸반 기타 출처");
    await waitFor(() => qsa("#paletteResults .pal-item").some((item) => item.textContent.includes("Kanban: 기타 Source 보기")), "kanban Korean generic source command did not render in palette");
    qsa("#paletteResults .pal-item").find((item) => item.textContent.includes("Kanban: 기타 Source 보기")).click();
    await waitFor(() => dashboard.currentView === "pm-kanban" && qs('#view-pm-kanban [data-kanban-source-filterbar]').dataset.kanbanSourceFilterCurrent === "source", "kanban Korean generic source command did not apply Source filter");
    const genericSourceEmpty = qs('#view-pm-kanban [data-kanban-source-empty]');
    assert(genericSourceEmpty.dataset.kanbanSourceEmptyFilter === "source" && genericSourceEmpty.textContent.includes("Source") && genericSourceEmpty.textContent.includes("전체 출처 보기") && qsa('#view-pm-kanban [data-search-result="pm-kanban"]').length === 0, "kanban Korean generic source command did not show clearable empty state");
    click('[data-action="filter-kanban-source"][data-kanban-source-filter="all"]', genericSourceEmpty);
    await waitFor(() => qs('#view-pm-kanban [data-kanban-source-filterbar]').dataset.kanbanSourceFilterCurrent === "all" && qs('#view-pm-kanban [data-issue-id="' + issueDraft.id + '"]'), "kanban Korean generic source command did not recover to all source scope");
    kanbanKoreanGenericSourceCommandOk = true;
    llmWikiKoreanSourceFilterCommandOk = true;
    click('#view-pm-kanban [data-issue-id="' + issueDraft.id + '"] [data-action="open-issue"]');
    await waitFor(() => document.querySelector('#sheet.open [data-action="open-issue-source"]'), "llm wiki issue sheet did not expose source return action");
    const wikiSourceReturn = qs('#sheet.open [data-action="open-issue-source"]');
    assert(wikiSourceReturn.textContent.includes("LLM Wiki") && wikiSourceReturn.textContent.includes("원문"), "llm wiki source return action label was incomplete");
    wikiSourceReturn.click();
    await waitFor(() => dashboard.currentView === "llm-wiki" && location.hash === "#llm-wiki" && qs("#view-llm-wiki .wiki-crumb-current").textContent.includes("구조화 출력"), "llm wiki source return did not open original article");
    const wikiBacklink = qs('#view-llm-wiki [data-source-backlink][data-source-backlink-surface="llm-wiki"]');
    assert(wikiBacklink.dataset.sourceBacklinkIssueId === issueDraft.id && wikiBacklink.textContent.includes(issueDraft.id) && wikiBacklink.textContent.includes("Kanban 이슈로 돌아가기"), "llm wiki source backlink did not render the originating issue");
    click('[data-action="open-source-backlink-issue"]', wikiBacklink);
    await waitFor(() => dashboard.currentView === "pm-kanban" && qs('#view-pm-kanban [data-kanban-source-filterbar]').dataset.kanbanSourceFilterCurrent === "wiki" && qs('#sheet.open [data-action="open-issue-source"]'), "llm wiki source backlink did not reopen the originating kanban issue");
    assert(qs("#sheet.open").textContent.includes(issueDraft.id), "llm wiki source backlink opened the wrong issue sheet");
    click('#sheet [data-action="close-sheet"]');
    await waitFor(() => !document.querySelector("#sheet.open"), "llm wiki source backlink sheet did not close");
    click('[data-action="open-palette"]');
    fill("#paletteInput", issueDraft.title);
    await waitFor(() => qsa("#paletteResults .pal-item").some((item) => item.textContent.includes(issueDraft.title) && item.textContent.includes(issueDraft.id) && item.textContent.includes("LLM Wiki")), "llm wiki issue record search did not render sourced palette result");
    qsa("#paletteResults .pal-item").find((item) => item.textContent.includes(issueDraft.title) && item.textContent.includes(issueDraft.id) && item.textContent.includes("LLM Wiki")).click();
    await waitFor(() => dashboard.currentView === "pm-kanban" && qs('#view-pm-kanban [data-kanban-source-filterbar]').dataset.kanbanSourceFilterCurrent === "wiki" && qs('#sheet.open [data-action="open-issue-source"]'), "llm wiki issue palette result did not open issue sheet in source scope");
    assert(qs("#sheet.open").textContent.includes(issueDraft.id), "llm wiki issue palette result opened the wrong issue sheet");
    click('#sheet [data-action="close-sheet"]');
    await waitFor(() => !document.querySelector("#sheet.open"), "llm wiki issue palette result sheet did not close");
    click('[data-action="open-palette"]');
    fill("#paletteInput", "LLM Wiki 출처");
    await waitFor(() => {
      const items = qsa("#paletteResults .pal-item");
      return items.some((item) => item.textContent.includes(todoDraft.title) && item.textContent.includes("LLM Wiki"))
        && items.some((item) => item.textContent.includes(noteDraft.title) && item.textContent.includes("LLM Wiki"))
        && items.some((item) => item.textContent.includes(issueDraft.title) && item.textContent.includes(issueDraft.id) && item.textContent.includes("LLM Wiki"));
    }, "llm wiki source label search did not render sourced palette records");
    qsa("#paletteResults .pal-item").find((item) => item.textContent.includes(issueDraft.title) && item.textContent.includes(issueDraft.id) && item.textContent.includes("LLM Wiki")).click();
    await waitFor(() => dashboard.currentView === "pm-kanban" && qs('#view-pm-kanban [data-kanban-source-filterbar]').dataset.kanbanSourceFilterCurrent === "wiki" && qs('#sheet.open [data-action="open-issue-source"]'), "llm wiki source label palette result did not open issue sheet in source scope");
    click('#sheet [data-action="close-sheet"]');
    await waitFor(() => !document.querySelector("#sheet.open"), "llm wiki source label palette sheet did not close");
    click('[data-action="open-palette"]');
    fill("#paletteInput", "위키 출처");
    await waitFor(() => {
      const items = qsa("#paletteResults .pal-item");
      return items.some((item) => item.textContent.includes(todoDraft.title) && item.textContent.includes("할 일") && item.textContent.includes("LLM Wiki"))
        && items.some((item) => item.textContent.includes(noteDraft.title) && item.textContent.includes("메모") && item.textContent.includes("LLM Wiki"))
        && items.some((item) => item.textContent.includes(issueDraft.title) && item.textContent.includes(issueDraft.id) && item.textContent.includes("LLM Wiki"));
    }, "llm wiki Korean source alias search did not render sourced palette records");
    qsa("#paletteResults .pal-item").find((item) => item.textContent.includes(issueDraft.title) && item.textContent.includes(issueDraft.id) && item.textContent.includes("LLM Wiki")).click();
    await waitFor(() => dashboard.currentView === "pm-kanban" && qs('#view-pm-kanban [data-kanban-source-filterbar]').dataset.kanbanSourceFilterCurrent === "wiki" && qs('#sheet.open [data-action="open-issue-source"]'), "llm wiki Korean source alias palette result did not open issue sheet in source scope");
    click('#sheet [data-action="close-sheet"]');
    await waitFor(() => !document.querySelector("#sheet.open"), "llm wiki Korean source alias palette sheet did not close");
    sourceIssuePaletteRecordOpenOk = true;
    sourceRecordPaletteLabelSearchOk = true;
    llmWikiKoreanSourceAliasSearchOk = true;
	    kanbanSourceBadgesOk = true;
    kanbanSourceFilterOk = true;
    kanbanSourceSummaryOk = true;
    kanbanSourcePaletteOk = true;
    kanbanSourceDirectReturnOk = true;
    issueSourceReturnOk = true;
    issueSourceBacklinkWikiOk = true;
    panel = await openStructuredOutputArticle();
    assert(panel.dataset.wikiActionCreatedCount === "3" && qs('[data-wiki-action-kind="todo"]', panel).dataset.wikiActionExisting === "true" && qs('[data-wiki-action-kind="note"]', panel).dataset.wikiActionExisting === "true" && qs('[data-wiki-action-kind="issue"]', panel).dataset.wikiActionExisting === "true", "llm wiki action panel did not expose created state");
    assert(panel.textContent.includes("할 일 생성됨") && panel.textContent.includes("메모 생성됨") && panel.textContent.includes("이슈 생성됨") && panel.textContent.includes("3/3 생성됨"), "llm wiki action panel created labels did not render");
    click('[data-wiki-action-kind="todo"]', panel);
    await waitFor(() => dashboard.currentView === "todo" && state.todoFilter === "all" && document.querySelector("#modal.open #todoForm"), "llm wiki duplicate todo action did not open existing todo modal");
    const todoEditForm = qs("#modal.open #todoForm");
    assert(qs('[name="title"]', todoEditForm).value === todoDraft.title && qs('[name="category"]', todoEditForm).value === "LLM Wiki" && qs('[name="memo"]', todoEditForm).value.includes("Source key: llm-wiki:" + articleId), "llm wiki duplicate todo action opened the wrong todo");
    const todoModalSource = qs('#modal.open [data-modal-source-link][data-source-record-kind="todo"]');
    assert(todoModalSource.dataset.sourceRecordId === todoDraft.id && todoModalSource.dataset.sourceArticleId === articleId && todoModalSource.textContent.includes("LLM Wiki 원문"), "llm wiki todo modal source link did not render");
    click('[data-action="open-llm-wiki-source"]', todoModalSource);
    await waitFor(() => dashboard.currentView === "llm-wiki" && !document.querySelector("#modal.open") && qs("#view-llm-wiki .wiki-crumb-current").textContent.includes("구조화 출력"), "llm wiki todo modal source link did not return to original article");
    panel = await openStructuredOutputArticle();
    click('[data-wiki-action-kind="note"]', panel);
    await waitFor(() => dashboard.currentView === "notes" && document.querySelector("#modal.open #noteForm"), "llm wiki duplicate note action did not open existing note modal");
    const noteEditForm = qs("#modal.open #noteForm");
    assert(qs('[name="title"]', noteEditForm).value === noteDraft.title && qs('[name="body"]', noteEditForm).value.includes("Source key: llm-wiki:" + articleId), "llm wiki duplicate note action opened the wrong note");
    const noteModalSource = qs('#modal.open [data-modal-source-link][data-source-record-kind="note"]');
    assert(noteModalSource.dataset.sourceRecordId === noteDraft.id && noteModalSource.dataset.sourceArticleId === articleId && noteModalSource.textContent.includes("LLM Wiki 원문"), "llm wiki note modal source link did not render");
    click('[data-action="open-llm-wiki-source"]', noteModalSource);
    await waitFor(() => dashboard.currentView === "llm-wiki" && !document.querySelector("#modal.open") && qs("#view-llm-wiki .wiki-crumb-current").textContent.includes("구조화 출력"), "llm wiki note modal source link did not return to original article");
    llmWikiExistingTodoNoteOpenOk = true;
    llmWikiTodoNoteModalSourceOk = true;
    panel = await openStructuredOutputArticle();
    click('[data-wiki-action-kind="issue"]', panel);
    await waitFor(() => dashboard.currentView === "pm-kanban" && qs('#view-pm-kanban [data-kanban-source-filterbar]').dataset.kanbanSourceFilterCurrent === "wiki" && qs('#sheet.open [data-action="open-issue-source"]'), "llm wiki duplicate issue action did not open existing kanban issue");
    assert(qs("#sheet.open").textContent.includes(issueDraft.id) && savedPayload().issues.filter((issue) => issue.sourceKey === issueKey).length === 1, "llm wiki duplicate issue action opened the wrong issue or created a duplicate");
    click('#sheet [data-action="close-sheet"]');
    await waitFor(() => !document.querySelector("#sheet.open"), "llm wiki duplicate issue sheet did not close");
    sourceIssueExistingWikiOk = true;
    sourceIssueExistingOpenOk = true;
    panel = await openStructuredOutputArticle();
    const apiCatAfterState = qsa(".wiki-cat", qs("#view-llm-wiki")).find((button) => button.textContent.includes("Claude API"));
    apiCatAfterState.click();
    await waitFor(() => qsa(".wiki-card", qs("#view-llm-wiki")).some((card) => card.textContent.includes("구조화 출력") && card.querySelector('[data-wiki-card-action-count="3"]')), "llm wiki article card did not expose action state badge");
    const wikiView = () => qs("#view-llm-wiki");
    const toolbar = () => qs(".wiki-toolbar", wikiView());
    click('[data-action="llm-wiki-action-filter"][data-wiki-action-filter="done"]', wikiView());
    await waitFor(() => toolbar().dataset.wikiActionFilterCurrent === "done", "llm wiki done action filter did not activate");
    let filteredCards = qsa(".wiki-card", wikiView());
    assert(filteredCards.length >= 1 && filteredCards.every((card) => card.querySelector("[data-wiki-card-action-count]")) && filteredCards.some((card) => card.textContent.includes("구조화 출력")), "llm wiki done action filter did not isolate executed cards");
    click('[data-action="llm-wiki-action-filter"][data-wiki-action-filter="open"]', wikiView());
    await waitFor(() => toolbar().dataset.wikiActionFilterCurrent === "open", "llm wiki open action filter did not activate");
    filteredCards = qsa(".wiki-card", wikiView());
    assert(filteredCards.length >= 1 && filteredCards.every((card) => !card.querySelector("[data-wiki-card-action-count]")) && !filteredCards.some((card) => card.textContent.includes("구조화 출력")), "llm wiki open action filter did not isolate unexecuted cards");
    click('[data-action="llm-wiki-action-filter"][data-wiki-action-filter="all"]', wikiView());
    await waitFor(() => toolbar().dataset.wikiActionFilterCurrent === "all" && qsa(".wiki-card", wikiView()).some((card) => card.textContent.includes("구조화 출력")), "llm wiki action filter did not reset to all");
    llmWikiActionFilterOk = true;
    llmWikiActionStateOk = true;
    llmWikiActionDraftsOk = true;
  });

  await runStep("llm wiki command palette bridge creates issue", async () => {
    await nav("llm-wiki");
    const view = qs("#view-llm-wiki");
    const agentsCat = qsa(".wiki-cat", view).find((button) => button.textContent.includes("도구 사용"));
    assert(agentsCat, "llm wiki tool-use category was not visible");
    agentsCat.click();
    await waitFor(() => qsa(".wiki-card-open", view).some((button) => button.textContent.includes("MCP")), "llm wiki tool-use cards did not render");
    const mcpCard = qsa(".wiki-card-open", view).find((button) => button.textContent.includes("MCP"));
    mcpCard.click();
    await waitFor(() => document.querySelector("#view-llm-wiki [data-wiki-action-panel]"), "llm wiki MCP action panel did not render");
    const articleId = qs("#view-llm-wiki [data-wiki-action-panel]").dataset.wikiActionArticle;
    click('[data-action="open-palette"]');
    fill("#paletteInput", "위키 글에서 이슈");
    await waitFor(() => qsa("#paletteResults .pal-item").some((item) => item.textContent.includes("위키 글에서 이슈 만들기")), "llm wiki command palette action did not render");
    const paletteIssueAction = qsa("#paletteResults .pal-item").find((item) => item.textContent.includes("위키 글에서 이슈 만들기"));
    paletteIssueAction.click();
    await waitFor(() => dashboard.currentView === "pm-kanban" && location.hash === "#pm-kanban", "llm wiki palette issue action did not navigate to kanban");
    const issueKey = "llm-wiki:issue:" + articleId;
    const issueDraft = savedPayload().issues.find((issue) => issue.sourceKey === issueKey);
    assert(issueDraft && issueDraft.title.includes("[LLM Wiki]") && issueDraft.sourceKind === "llm-wiki-action" && issueDraft.body.includes("Sources"), "llm wiki palette issue draft was not persisted");
    llmWikiPaletteBridgeOk = true;
  });

  await runStep("command palette opens created issue", async () => {
    assert(issueId, "no created issue id available");
    assert(window.JooParkCommandPalette && window.JooParkCommandPalette.version === "joopark-command-palette/v1" && typeof window.JooParkCommandPalette.create === "function", "command palette runtime module was not loaded");
    commandPaletteModuleOk = true;
    click('[data-action="open-palette"]');
    fill("#paletteInput", marker + " issue");
    await waitFor(() => document.querySelectorAll("#paletteResults .pal-item").length > 0, "palette produced no results");
    click("#paletteResults .pal-item");
    await waitFor(() => document.querySelector("#modal.open #issueForm"), "palette did not open issue modal");
    assert(document.querySelector('#issueForm [name="title"]').value.includes(marker), "palette opened the wrong issue");
    click('#modal [data-action="close-modal"]');
  });

  await runStep("command palette opens created note record", async () => {
    assert(window.JooParkCommandPalette && window.JooParkCommandPalette.version === "joopark-command-palette/v1" && typeof window.JooParkCommandPalette.create === "function", "command palette runtime module was not loaded");
    commandPaletteModuleOk = true;
    click('[data-action="open-palette"]');
    await waitFor(() => document.querySelector("#palette.open"), "command palette did not open for created note search");
    const paletteInput = fill("#paletteInput", marker + " note");
    await waitFor(() => qsa("#paletteResults .pal-item").some((item) => item.textContent.includes(marker + " note") && item.textContent.includes("메모")), "created note record did not render in palette");
    const firstResult = qs("#paletteResults .pal-item");
    assert(firstResult.textContent.includes(marker + " note") && firstResult.textContent.includes("메모") && firstResult.getAttribute("aria-selected") === "true" && paletteInput.getAttribute("aria-activedescendant") === firstResult.id, "created note record was not the active first result");
    paletteInput.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true }));
    await waitFor(() => dashboard.currentView === "notes" && document.querySelector("#modal.open #noteForm"), "created note palette result did not open the note modal");
    assert(qs('#modal.open #noteForm [name="title"]').value === marker + " note" && qs('#modal.open #noteForm [name="pinned"]').checked, "created note palette result opened the wrong note");
    click('#modal [data-action="close-modal"]');
    await waitFor(() => !document.querySelector("#modal.open"), "created note modal did not close");
    commandPaletteCreatedNoteRecordOk = true;
  });

	  await runStep("global help access opens consistent recovery actions", async () => {
	    await nav("todo");
	    const helpTrigger = qs("[data-global-help-trigger]");
    assert(helpTrigger.getAttribute("aria-haspopup") === "dialog" && helpTrigger.getAttribute("aria-controls") === "sheet" && helpTrigger.getAttribute("aria-expanded") === "false", "global help trigger accessibility was incomplete");
    click("[data-action='open-global-help']");
    await waitFor(() => document.querySelector("#sheet.open [data-global-help-access]"), "global help sheet did not open");
    const help = qs("#sheet [data-global-help-access]");
    const helpActions = Array.from(help.querySelectorAll("[data-global-help-action]"));
    const helpStatus = qs("[data-global-help-status-message]", help);
	    assert(helpTrigger.getAttribute("aria-expanded") === "true" && help.dataset.globalHelpAccessReady === "true" && help.dataset.globalHelpAccessCoverage === "1" && help.dataset.globalHelpAccessActionCount === "4" && help.dataset.globalHelpCurrentView === "todo" && help.dataset.globalHelpSearchMode === "view" && ["true", "false"].includes(help.dataset.globalHelpSafeToDispatch) && ["true", "false"].includes(help.dataset.globalHelpReadyForExternalClaim) && help.dataset.globalHelpConsistentHelp === "wcag-3.2.6" && help.dataset.globalHelpStatusRole === "status", "global help access dataset was incomplete");
	    assert(helpStatus.getAttribute("role") === "status" && helpStatus.getAttribute("aria-live") === "polite" && helpStatus.textContent.includes("할 일") && helpStatus.textContent.includes("safeToDispatch=" + help.dataset.globalHelpSafeToDispatch) && helpStatus.textContent.includes("readyForExternalClaim=" + help.dataset.globalHelpReadyForExternalClaim), "global help status message was not programmatically exposed");
    assert(helpActions.length === 4 && helpActions.some((item) => item.dataset.globalHelpActionKey === "command_palette" && item.dataset.globalHelpActionStatus === "ready") && helpActions.some((item) => item.dataset.globalHelpActionKey === "view_recovery" && item.dataset.globalHelpActionValue === "view search") && helpActions.some((item) => item.dataset.globalHelpActionKey === "system_status" && item.dataset.view === "system") && helpActions.some((item) => item.dataset.globalHelpActionKey === "settings_backup" && item.dataset.view === "settings"), "global help actions were incomplete");
    click("[data-global-help-action-key='view_recovery']", help);
    await waitFor(() => !document.querySelector("#sheet.open") && document.activeElement === document.querySelector("#globalSearch"), "global help view recovery did not focus search");
    click("[data-action='open-global-help']");
    await waitFor(() => document.querySelector("#sheet.open [data-global-help-access]"), "global help sheet did not reopen");
    click("[data-global-help-action-key='system_status']", qs("#sheet [data-global-help-access]"));
    await waitFor(() => document.body.dataset.view === "system" && !document.getElementById("view-system").hidden, "global help system action did not navigate");
    await nav("stats");
    click("[data-action='open-global-help']");
    await waitFor(() => document.querySelector("#sheet.open [data-global-help-access][data-global-help-search-mode='command']"), "global help did not expose command search on inert view");
    click("[data-global-help-action-key='command_palette']", qs("#sheet [data-global-help-access]"));
    await waitFor(() => document.querySelector("#palette.open"), "global help command action did not open palette");
    click("[data-action='close-palette']");
	    globalHelpAccessOk = true;
	  });

	  await runStep("topbar data safety status exposes local storage recovery", async () => {
	    await nav("todo");
	    const trigger = qs("[data-data-safety-trigger]");
	    await waitFor(() => trigger.dataset.dataSafetyCoverage === "1" && trigger.dataset.dataSafetyActionCount === "4", "topbar data safety trigger did not receive coverage dataset");
	    assert(trigger.getAttribute("aria-haspopup") === "dialog" && trigger.getAttribute("aria-controls") === "sheet" && trigger.getAttribute("aria-expanded") === "false", "topbar data safety trigger accessibility was incomplete");
	    assert(trigger.dataset.dataSafetyReady === "true" && trigger.dataset.dataSafetyTone !== "error" && Number(trigger.dataset.dataSafetyLocalBytes || "0") > 0 && trigger.dataset.dataSafetyOnline === "true" && trigger.textContent.includes("저장"), "topbar data safety trigger state was incomplete");
	    click("[data-action='open-data-safety-status']");
	    await waitFor(() => document.querySelector("#sheet.open [data-topbar-data-safety]"), "topbar data safety sheet did not open");
	    const safety = qs("#sheet [data-topbar-data-safety]");
	    const status = qs("[data-topbar-data-safety-status-message]", safety);
	    const actions = Array.from(safety.querySelectorAll("[data-topbar-data-safety-action]"));
	    assert(trigger.getAttribute("aria-expanded") === "true" && safety.dataset.topbarDataSafetyReady === "true" && safety.dataset.topbarDataSafetyCoverage === "1" && safety.dataset.topbarDataSafetyActionCount === "4" && safety.dataset.topbarDataSafetyStatus && safety.dataset.topbarDataSafetyStatus !== "저장 실패" && safety.dataset.topbarDataSafetyTone !== "error" && Number(safety.dataset.topbarDataSafetyLocalBytes || "0") > 0 && safety.dataset.topbarDataSafetyOnline === "true" && safety.dataset.topbarDataSafetyStorageApi.includes("StorageManager"), "topbar data safety dataset was incomplete");
	    assert(status.getAttribute("role") === "status" && status.getAttribute("aria-live") === "polite" && status.textContent.includes("저장=") && status.textContent.includes("local=") && status.textContent.includes("persistence="), "topbar data safety status message was not programmatically exposed");
	    assert(actions.length === 4 && actions.some((item) => item.dataset.topbarDataSafetyActionKey === "saved_state" && item.dataset.topbarDataSafetyActionStatus === "ready") && actions.some((item) => item.dataset.topbarDataSafetyActionKey === "storage_health" && item.dataset.view === "system") && actions.some((item) => item.dataset.topbarDataSafetyActionKey === "persistent_storage" && item.dataset.topbarDataSafetyActionStatus) && actions.some((item) => item.dataset.topbarDataSafetyActionKey === "backup_recovery" && item.dataset.view === "settings"), "topbar data safety actions were incomplete");
	    click("[data-topbar-data-safety-action-key='saved_state']", safety);
	    await waitFor(() => document.querySelector("#sheet.open [data-topbar-data-safety]"), "topbar data safety refresh did not keep sheet open");
	    click("[data-topbar-data-safety-action-key='storage_health']", qs("#sheet [data-topbar-data-safety]"));
	    await waitFor(() => document.body.dataset.view === "system" && !document.getElementById("view-system").hidden, "topbar data safety system action did not navigate");
	    click("[data-action='open-data-safety-status']");
	    await waitFor(() => document.querySelector("#sheet.open [data-topbar-data-safety]"), "topbar data safety sheet did not reopen");
	    click("[data-topbar-data-safety-action-key='backup_recovery']", qs("#sheet [data-topbar-data-safety]"));
	    await waitFor(() => document.body.dataset.view === "settings" && !document.getElementById("view-settings").hidden, "topbar data safety settings action did not navigate");
	    topbarDataSafetyOk = true;
	  });

	  const preImportPayload = savedPayload();
  const persistedChecks = {
    event: preImportPayload.events.some((event) => event.title === marker + " event"),
    todo: preImportPayload.todos.some((todo) => todo.title === marker + " todo" && todo.done),
    note: preImportPayload.notes.some((note) => note.title === marker + " note" && note.pinned),
    project: preImportPayload.projects.some((project) => project.name === marker + " project"),
    issue: preImportPayload.issues.some((issue) => issue.title === marker + " issue" && issue.status === "in-progress"),
    dbInstance: preImportPayload.dbInstances.some((instance) => instance.name === marker + " db"),
    settings: preImportPayload.settings.displayName === marker + " user",
    backupExport: backupExportOk,
    settingsHandoffCopy: settingsHandoffCopyOk,
    privacyStorageHandoff: privacyStorageHandoffOk,
    systemPublishReadiness: systemPublishReadinessOk,
    releaseGateEvidence: releaseGateEvidenceOk,
    releaseGateEvidenceHandoff: releaseGateEvidenceHandoffOk,
    systemPwaRuntime: systemPwaRuntimeOk,
    systemOpsRuntime: systemOpsRuntimeOk,
    workflowUiInstallPlanPanel: workflowUiInstallPlanPanelOk,
    workflowUiInstallReceiptCopy: workflowUiInstallReceiptCopyOk,
    workflowUiInstallPastePacketCopy: workflowUiInstallReceiptCopyOk,
    postInstallEvidenceIntake: postInstallEvidenceIntakeOk,
    postInstallProofParser: postInstallProofParserOk,
    postInstallProofParserFalsePositiveGuard: postInstallProofParserFalsePositiveGuardOk,
    postInstallProofParserFields: postInstallProofParserOk ? 6 : 0,
    postInstallProofParserCoverage: postInstallProofParserOk ? 1 : 0,
    postInstallProofParserDetectedFields: postInstallProofParserOk ? 6 : 0,
    publishDispatchPlanPanel: publishDispatchPlanPanelOk,
    publishDispatchAuthPreflight: publishDispatchAuthPreflightOk,
    publishDispatchWorkflowScopePacketCopy: publishDispatchWorkflowScopePacketCopyOk,
    remoteWorkflowFileCheckPanel: remoteWorkflowFileCheckPanelOk,
    publishEvidenceShareUpdate: publishEvidenceShareUpdateOk,
    publishLaunchAnnouncement: publishLaunchAnnouncementOk,
    publishPostLaunchReceipt: publishPostLaunchReceiptOk,
    launchProofEvidenceReceipt: launchProofEvidenceReceiptOk,
    launchExecutionPacket: launchExecutionPacketOk,
    launchExecutionCurrentActionCopy: launchExecutionCurrentActionCopyOk,
    launchOperatorOnePageCopy: launchOperatorOnePageCopyOk,
    launchReadinessRefresh: launchReadinessRefreshOk,
    launchReadinessRefreshReceiptCopy: launchReadinessRefreshReceiptCopyOk,
    verifyWorkspaceSummary: verifyWorkspaceSummaryOk,
    verifyWorkspaceSummaryReceiptCopy: verifyWorkspaceSummaryReceiptCopyOk,
    releaseGateCache: releaseGateCacheOk,
    releaseGateCacheRepairCopy: releaseGateCacheRepairCopyOk,
    releaseProvenancePanel: releaseProvenancePanelOk,
    releaseProvenanceReceiptCopy: releaseProvenanceReceiptCopyOk,
    pagesAttestationProofIntake: pagesAttestationProofIntakeOk,
    pagesAttestationProofIntakeCopy: pagesAttestationProofIntakeCopyOk,
    outputQualityAuditReceipt: outputQualityAuditReceiptOk,
    outputQualityExternalClaimGuard: outputQualityExternalClaimGuardOk,
    outputQualityArtifactRubric: outputQualityArtifactRubricOk,
    markdownSanitized: markdownSanitizedOk,
    workspaceCandidateVisible: workspaceCandidateVisibleOk,
    workspaceCompetitiveCandidateVisible: workspaceCompetitiveCandidateVisibleOk,
    colanodeCandidateFreshnessVisible: colanodeCandidateFreshnessVisibleOk,
    parabolCandidateFreshnessVisible: parabolCandidateFreshnessVisibleOk,
    worklenzCandidateFreshnessVisible: worklenzCandidateFreshnessVisibleOk,
    anytypeCandidateFreshnessVisible: anytypeCandidateFreshnessVisibleOk,
    focalboardCandidateFreshnessVisible: focalboardCandidateFreshnessVisibleOk,
    epicenterCandidateFreshnessVisible: epicenterCandidateFreshnessVisibleOk,
    openLoafCandidateFreshnessVisible: openLoafCandidateFreshnessVisibleOk,
    planeCandidateFreshnessVisible: planeCandidateFreshnessVisibleOk,
    appFlowyCandidateFreshnessVisible: appFlowyCandidateFreshnessVisibleOk,
    affineCandidateFreshnessVisible: affineCandidateFreshnessVisibleOk,
    outlineCandidateFreshnessVisible: outlineCandidateFreshnessVisibleOk,
    bookStackCandidateFreshnessVisible: bookStackCandidateFreshnessVisibleOk,
    wikiJsCandidateFreshnessVisible: wikiJsCandidateFreshnessVisibleOk,
    workstreamCandidateFreshnessVisible: remainingWorkspaceFreshnessOk.workstream,
    taskosaurCandidateFreshnessVisible: remainingWorkspaceFreshnessOk.taskosaur,
    markdownTaskManagerCandidateFreshnessVisible: remainingWorkspaceFreshnessOk.markdownTaskManager,
    taskcoachCandidateFreshnessVisible: remainingWorkspaceFreshnessOk.taskcoach,
    fluidCalendarCandidateFreshnessVisible: remainingWorkspaceFreshnessOk.fluidCalendar,
    veritasCandidateFreshnessVisible: veritasCandidateFreshnessVisibleOk,
    openProjectCandidateFreshnessVisible: openProjectCandidateFreshnessVisibleOk,
    leantimeCandidateFreshnessVisible: leantimeCandidateFreshnessVisibleOk,
    candidateMetadataRefresh: candidateMetadataRefreshOk,
    candidateNextActionVisible: candidateNextActionVisibleOk,
    candidateActionFilter: candidateActionFilterOk,
    candidateActionSummaryVisible: candidateActionSummaryVisibleOk,
    candidateSeedScope: candidateSeedScopeOk,
    candidateBenchmarkFocusVisible: candidateBenchmarkFocusVisibleOk,
    candidateBenchmarkQueueVisible: candidateBenchmarkQueueVisibleOk,
    candidateBenchmarkRubricVisible: candidateBenchmarkRubricVisibleOk,
    candidateBenchmarkRubricScoreVisible: candidateBenchmarkRubricScoreVisibleOk,
    workspaceBenchmarkRubricVisible: workspaceBenchmarkRubricVisibleOk,
    workspaceBenchmarkExportVisible: workspaceBenchmarkExportVisibleOk,
    workspaceBenchmarkReviewHandoffVisible: workspaceBenchmarkReviewHandoffVisibleOk,
    workspaceBenchmarkReviewHandoffCopyVisible: workspaceBenchmarkReviewHandoffCopyVisibleOk,
    workspaceBenchmarkReviewIssueDraftVisible: workspaceBenchmarkReviewIssueDraftVisibleOk,
    workspaceBenchmarkReviewNotePublishVisible: workspaceBenchmarkReviewNotePublishVisibleOk,
    workspaceBenchmarkReviewGithubCommentVisible: workspaceBenchmarkReviewGithubCommentVisibleOk,
    knowledgeBaseBenchmarkRubricVisible: knowledgeBaseBenchmarkRubricVisibleOk,
    knowledgeBaseBenchmarkExportVisible: knowledgeBaseBenchmarkExportVisibleOk,
    knowledgeBaseBenchmarkReviewHandoffVisible: knowledgeBaseBenchmarkReviewHandoffVisibleOk,
    knowledgeBaseBenchmarkReviewHandoffCopyVisible: knowledgeBaseBenchmarkReviewHandoffCopyVisibleOk,
    knowledgeBaseBenchmarkReviewIssueDraftVisible: knowledgeBaseBenchmarkReviewIssueDraftVisibleOk,
    knowledgeBaseBenchmarkReviewNotePublishVisible: knowledgeBaseBenchmarkReviewNotePublishVisibleOk,
    knowledgeBaseBenchmarkReviewGithubCommentVisible: knowledgeBaseBenchmarkReviewGithubCommentVisibleOk,
    candidateBenchmarkRecommendationExportVisible: candidateBenchmarkRecommendationExportVisibleOk,
    candidateBenchmarkReviewQueueVisible: candidateBenchmarkReviewQueueVisibleOk,
    candidateBenchmarkReviewHandoffVisible: candidateBenchmarkReviewHandoffVisibleOk,
    candidateBenchmarkReviewHandoffCopyVisible: candidateBenchmarkReviewHandoffCopyVisibleOk,
    candidateBenchmarkReviewIssueDraftVisible: candidateBenchmarkReviewIssueDraftVisibleOk,
    reviewPackageBundleVisible: reviewPackageBundleVisibleOk,
    reviewPackageManifestVisible: reviewPackageManifestVisibleOk,
    reviewCopyActionsModule,
    reviewSubmissionCopyModule,
    reviewRecommendationExportModule,
    reviewPackageArtifactQualityRubricVisible: reviewPackageArtifactQualityRubricVisibleOk,
    reviewPackageDecisionBriefVisible: reviewPackageDecisionBriefVisibleOk,
    reviewPackageOperatorQuickStartVisible: reviewPackageOperatorQuickStartVisibleOk,
    reviewIssueDecisionSummaryVisible: reviewIssueDecisionSummaryVisibleOk,
    reviewCommentNoteDecisionSummaryVisible: reviewCommentNoteDecisionSummaryVisibleOk,
    reviewPackagePasteTargetsVisible: reviewPackagePasteTargetsVisibleOk,
    reviewPackagePastePreviewVisible: reviewPackagePastePreviewVisibleOk,
    reviewPackagePastePreviewCopy: reviewPackagePastePreviewCopyOk,
    reviewPackageTrackerFieldCopy: reviewPackageTrackerFieldCopyOk,
    reviewPackageTrackerFormCopy: reviewPackageTrackerFormCopyOk,
    reviewPackageSubmitSequenceCopy: reviewPackageSubmitSequenceCopyOk,
    reviewPackageExternalReceiptTemplateCopy: reviewPackageExternalReceiptTemplateCopyOk,
    reviewPackageExternalReceiptFilledCopy: reviewPackageExternalReceiptFilledCopyOk,
    reviewPackageExternalReceiptIntegrity: reviewPackageExternalReceiptIntegrityOk,
    reviewPackageSubmissionCloseoutSummaryVisible: reviewPackageSubmissionCloseoutSummaryVisibleOk,
    reviewPackageSubmissionUpdateCopy: reviewPackageSubmissionUpdateCopyOk,
    reviewPackageFinalQualityGateVisible: reviewPackageFinalQualityGateVisibleOk,
    reviewPackageQualityRepairChecklistVisible: reviewPackageQualityRepairChecklistVisibleOk,
    reviewResultValidatorVisible: reviewResultValidatorVisibleOk,
    reviewResultValidatorEmpty: reviewResultValidatorEmptyOk,
    reviewResultValidatorFailure: reviewResultValidatorFailureOk,
    reviewResultValidatorPass: reviewResultValidatorPassOk,
    reviewResultValidatorRetry: reviewResultValidatorRetryOk,
    reviewResultValidatorSaved: reviewResultValidatorSavedOk,
    reviewResultValidatorPersisted: reviewResultValidatorPersistedOk,
    reviewResultRepairPacketCopy: reviewResultRepairPacketCopyOk,
    reviewResultRepairActionPlanVisible: reviewResultRepairActionPlanVisibleOk,
    reviewResultPostRepairReceipt: reviewResultPostRepairReceiptOk,
    reviewResultRepairArtifactLink: reviewResultRepairArtifactLinkOk,
    reviewPostRepairArtifactLink: reviewPostRepairArtifactLinkOk,
    reviewResultIssueApplied: reviewResultIssueAppliedOk,
    reviewResultNoteApplied: reviewResultNoteAppliedOk,
    reviewArtifactDiffVisible: reviewArtifactDiffVisibleOk,
    reviewArtifactDiffValidated: reviewArtifactDiffValidatedOk,
    reviewArtifactOperationalReadiness: reviewArtifactOperationalReadinessOk,
    reviewOperationalTrackerField: reviewOperationalTrackerFieldOk,
    reviewExecutionChecklist: reviewExecutionChecklistOk,
    reviewExecutionChecklistProgress: reviewExecutionChecklistProgressOk,
    reviewAssigneeOverride: reviewAssigneeOverrideOk,
    reviewAssigneeOverrideDraftPersistence: reviewAssigneeOverrideDraftPersistenceOk,
    reviewAssigneeFollowUp: reviewAssigneeFollowUpOk,
    reviewArtifactReceiptCompare: reviewArtifactReceiptCompareOk,
    reviewArtifactReceiptRepairSuggestion: reviewArtifactReceiptRepairSuggestionOk,
    reviewArtifactReceiptRepairCopy: reviewArtifactReceiptRepairCopyOk,
    reviewArtifactReceiptRepairApply: reviewArtifactReceiptRepairApplyOk,
    reviewArtifactPostApplyFreshReceipt: reviewArtifactPostApplyFreshReceiptOk,
    reviewArtifactFreshReceiptAfterChecklist: reviewArtifactFreshReceiptAfterChecklistOk,
    portfolioCandidateFilter: portfolioCandidateFilterOk,
    portfolioCandidateRanked: portfolioCandidateRankedOk,
    portfolioReferenceToggle: portfolioReferenceToggleOk,
    sourceSnapshotHealth: sourceSnapshotHealthOk,
    githubProjectDiscovery: githubProjectDiscoveryOk,
    releaseStatusModule: releaseStatusModuleOk,
    searchEmptyStateModule: searchEmptyStateModuleOk,
    calendarViewModule: calendarViewModuleOk,
    todoViewModule: todoViewModuleOk,
    notesViewModule: notesViewModuleOk,
    habitsViewModule: habitsViewModuleOk,
    statsViewModule: statsViewModuleOk,
    portfolioViewModule: portfolioViewModuleOk,
    kanbanViewModule: kanbanViewModuleOk,
    ganttViewModule: ganttViewModuleOk,
    teamViewModule: teamViewModuleOk,
    workspaceStorageModule: workspaceStorageModuleOk,
    storageStatusViewModule: storageStatusViewModuleOk,
    settingsViewModule: settingsViewModuleOk,
    systemStatusViewModule: systemStatusViewModuleOk,
    operationsCopyActionsModule: operationsCopyActionsModuleOk,
    verifyWorkspaceSummaryModule: verifyWorkspaceSummaryModuleOk,
    dialogShellModule: dialogShellModuleOk,
    projectPickerModule: projectPickerModuleOk,
    globalSearchModule: globalSearchModuleOk,
    commandPaletteModule: commandPaletteModuleOk,
    commandPaletteRouteCoverage: commandPaletteRouteCoverageOk,
    commandPalettePersonalNavAliases: commandPalettePersonalNavAliasesOk,
    commandPaletteOperationalNavAliases: commandPaletteOperationalNavAliasesOk,
    commandPalettePmPortfolioNavAlias: commandPalettePmPortfolioNavAliasOk,
    commandPalettePmGanttNavAlias: commandPalettePmGanttNavAliasOk,
    commandPalettePmTeamNavAlias: commandPalettePmTeamNavAliasOk,
    commandPaletteKoreanNavAlias: commandPaletteKoreanNavAliasOk,
    commandPaletteDbKoreanNavAlias: commandPaletteDbKoreanNavAliasOk,
    commandPaletteDbInstanceNavAlias: commandPaletteDbInstanceNavAliasOk,
    commandPaletteDbQueryNavAlias: commandPaletteDbQueryNavAliasOk,
    commandPaletteDbBackupNavAlias: commandPaletteDbBackupNavAliasOk,
    commandPaletteExactNavLabel: commandPaletteExactNavLabelOk,
    commandPaletteCreatedNoteRecord: commandPaletteCreatedNoteRecordOk,
    llmWikiActionDrafts: llmWikiActionDraftsOk,
    llmWikiPaletteBridge: llmWikiPaletteBridgeOk,
    llmWikiActionState: llmWikiActionStateOk,
    llmWikiActionFilter: llmWikiActionFilterOk,
    dbCatalogModule: dbCatalogModuleOk,
    reviewHandoffModule: reviewHandoffModuleOk,
    reviewResultViewModule: reviewResultViewModuleOk,
    reviewResultStateModule: reviewResultStateModuleOk,
    reviewExecutionChecklistModule: reviewExecutionChecklistModuleOk,
    reviewIssuePayloadModule: reviewIssuePayloadModuleOk,
    reviewResultDraftStateModule: reviewResultDraftStateModuleOk,
    reviewCreationActionsModule: reviewCreationActionsModuleOk,
    reviewPackageViewModule: reviewPackageViewModuleOk,
    reviewArtifactViewModule: reviewArtifactViewModuleOk,
    reviewArtifactStateModule: reviewArtifactStateModuleOk,
    reviewCopyActionsModule: reviewCopyActionsModuleOk,
    reviewSubmissionCopyModule: reviewSubmissionCopyModuleOk,
    reviewRecommendationExportModule: reviewRecommendationExportModuleOk,
    homeQuickLinksNavigate: homeQuickLinksNavigateOk,
    routeDeepLink: routeDeepLinkOk,
    homeLaunchNextAction: homeLaunchNextActionOk,
    homeLaunchActionChecklist: homeLaunchActionChecklistOk,
    homeLaunchBlockerResolver: homeLaunchBlockerResolverOk,
    homeReleaseGateEvidence: homeReleaseGateEvidenceOk,
	    homePostInstallEvidenceIntake: homePostInstallEvidenceIntakeOk,
    homeExternalClaimGuard: homeExternalClaimGuardOk,
    homeExecutionViewModule: homeExecutionViewModuleOk,
    homeExecutionQueue: homeExecutionQueueOk,
    homeExecutionQueueExplainability: homeExecutionQueueExplainabilityOk,
    homeExecutionQueueBuckets: homeExecutionQueueBucketsOk,
    homeExecutionQueueBucketFilter: homeExecutionQueueBucketFilterOk,
    homeExecutionQueueFilterSummary: homeExecutionQueueFilterSummaryOk,
    homeExecutionQueueFilterComposition: homeExecutionQueueFilterCompositionOk,
    homeExecutionQueueFilterWindow: homeExecutionQueueFilterWindowOk,
    homeExecutionQueueFilterRankWindow: homeExecutionQueueFilterRankWindowOk,
    homeExecutionQueueScoreWindow: homeExecutionQueueScoreWindowOk,
    homeExecutionQueueScoreDriver: homeExecutionQueueScoreDriverOk,
    homeExecutionQueueLeadDriver: homeExecutionQueueLeadDriverOk,
    homeExecutionQueueLeadDriverCount: homeExecutionQueueLeadDriverCountOk,
    homeExecutionQueueLeadDriverTie: homeExecutionQueueLeadDriverTieOk,
    homeExecutionQueueReceiptCompact: homeExecutionQueueReceiptCompactOk,
    homeExecutionQueueReceiptDetail: homeExecutionQueueReceiptDetailOk,
    homeExecutionQueueReceiptDescription: homeExecutionQueueReceiptDescriptionOk,
    homeExecutionQueueQuickActions: homeExecutionQueueQuickActionsOk,
    homeExecutionQueueQuickUndo: homeExecutionQueueQuickUndoOk,
			    homeUpcomingEventOpen: homeUpcomingEventOpenOk,
	    homeQuickTodo: homeQuickTodoOk,
	    globalHelpAccess: globalHelpAccessOk,
    topbarDataSafety: topbarDataSafetyOk,
    calendarModeSwitch: calendarModeSwitchOk,
	    calendarGridKeyboard: calendarGridKeyboardOk,
    calendarSearchRecovery: calendarSearchRecoveryOk,
    habitSearchRecovery: habitSearchRecoveryOk,
    statsSearchInert: statsSearchInertOk,
    todoSearchRecovery: todoSearchRecoveryOk,
    topbarSearchClear: topbarSearchClearOk,
    notesSearchRecovery: notesSearchRecoveryOk,
    portfolioSearchRecovery: portfolioSearchRecoveryOk,
    kanbanLabelNormalization: kanbanLabelNormalizationOk,
    kanbanOrderPersistence: kanbanOrderPersistenceOk,
    kanbanDensityPersistence: kanbanDensityPersistenceOk,
    kanbanTouchDrag: kanbanTouchDragOk,
    kanbanSourceBadges: kanbanSourceBadgesOk,
    kanbanSourceFilter: kanbanSourceFilterOk,
    kanbanSourceEmpty: kanbanSourceEmptyOk,
    kanbanSourceSummary: kanbanSourceSummaryOk,
    kanbanSourcePalette: kanbanSourcePaletteOk && dbCatalogKoreanSourceFilterCommandOk,
    dbCatalogKoreanSourceFilterCommand: dbCatalogKoreanSourceFilterCommandOk,
    kanbanSourceDirectReturn: kanbanSourceDirectReturnOk,
    kanbanReviewFamilyBadge: kanbanReviewFamilyBadgeOk,
    kanbanReviewFamilyFilter: kanbanReviewFamilyFilterOk && kanbanReviewKoreanFamilyFilterCommandOk,
    kanbanReviewKoreanFamilyFilterCommand: kanbanReviewKoreanFamilyFilterCommandOk,
    issueSourceReturn: issueSourceReturnOk,
    reviewIssueSourceReturn: reviewIssueSourceReturnOk,
    reviewNoteSourceReturn: reviewNoteSourceReturnOk,
    reviewBenchmarkNoteModalSourceReturn: reviewBenchmarkNoteModalSourceReturnOk,
    reviewNoteCardSourceReturn: reviewNoteCardSourceReturnOk,
    reviewBenchmarkNoteCardSourceReturn: reviewBenchmarkNoteCardSourceReturnOk,
    reviewNoteCardFamilyLabel: reviewNoteCardFamilyLabelOk,
    reviewNoteSourceFilter: reviewNoteSourceFilterOk,
    reviewNoteFamilyFilter: reviewNoteFamilyFilterOk && reviewNoteKoreanFamilyFilterCommandOk,
    reviewBenchmarkNoteFamilyFilter: reviewBenchmarkNoteFamilyFilterOk,
    reviewNoteKoreanFamilyFilterCommand: reviewNoteKoreanFamilyFilterCommandOk,
    reviewKoreanRollupSourceFilterCommand: reviewKoreanRollupSourceFilterCommandOk,
    reviewNoteExistingOpen: reviewNoteExistingOpenOk,
    reviewKbNoteExistingOpen: reviewKbNoteExistingOpenOk,
    reviewBenchmarkNoteExistingOpen: reviewBenchmarkNoteExistingOpenOk,
    issueSourceBacklink: issueSourceBacklinkWikiOk && issueSourceBacklinkDbOk && issueSourceBacklinkReviewOk,
    sourceIssuePaletteRecordOpen: sourceIssuePaletteRecordOpenOk,
    sourceRecordPaletteLabelSearch: sourceRecordPaletteLabelSearchOk && llmWikiKoreanSourceAliasSearchOk && sourceDbPaletteLabelSearchOk && sourceDbKoreanAliasSearchOk && sourceReviewPaletteLabelSearchOk && sourceReviewNotePaletteLabelSearchOk && sourceBenchmarkReviewNotePaletteLabelSearchOk && sourceBenchmarkReviewPaletteFamilyLabelSearchOk && sourceReviewAllFamilyLabelSearchOk && sourceBenchmarkReviewKoreanFamilyAliasSearchOk && sourceReviewKoreanAllFamilyAliasSearchOk,
    llmWikiKoreanSourceAliasSearch: llmWikiKoreanSourceAliasSearchOk,
    sourceDbKoreanAliasSearch: sourceDbKoreanAliasSearchOk,
    sourceBenchmarkReviewNotePaletteLabelSearch: sourceBenchmarkReviewNotePaletteLabelSearchOk,
    sourceBenchmarkReviewNotePaletteSourceReturn: sourceBenchmarkReviewNotePaletteSourceReturnOk,
    sourceBenchmarkReviewPaletteFamilyLabelSearch: sourceBenchmarkReviewPaletteFamilyLabelSearchOk,
    sourceReviewAllFamilyLabelSearch: sourceReviewAllFamilyLabelSearchOk,
    sourceBenchmarkReviewKoreanFamilyAliasSearch: sourceBenchmarkReviewKoreanFamilyAliasSearchOk,
    sourceReviewKoreanAllFamilyAliasSearch: sourceReviewKoreanAllFamilyAliasSearchOk,
    sourceReviewPaletteFamilyLabel: sourceReviewPaletteFamilyLabelOk,
    sourceIssueExistingOpen: sourceIssueExistingOpenOk && sourceIssueExistingReviewOk && sourceIssueExistingDbOk && sourceIssueExistingWikiOk,
    llmWikiExistingTodoNoteOpen: llmWikiExistingTodoNoteOpenOk,
    llmWikiTodoNoteSourceReturn: llmWikiTodoNoteSourceReturnOk,
    llmWikiTodoNoteSourceBacklink: llmWikiTodoNoteSourceBacklinkOk,
    llmWikiTodoNoteModalSource: llmWikiTodoNoteModalSourceOk,
    llmWikiTodoNoteSourceFilter: llmWikiTodoNoteSourceFilterOk,
    llmWikiTodoNoteSourcePalette: llmWikiTodoNoteSourcePaletteOk && llmWikiKoreanSourceFilterCommandOk,
    llmWikiKoreanSourceFilterCommand: llmWikiKoreanSourceFilterCommandOk,
    sourceKoreanResetCommand: sourceKoreanResetCommandOk,
    kanbanKoreanGenericSourceCommand: kanbanKoreanGenericSourceCommandOk,
    llmWikiTodoNotePaletteRecordOpen: llmWikiTodoNotePaletteRecordOpenOk,
    kanbanSearchRecovery: kanbanSearchRecoveryOk,
    ganttSearchRecovery: ganttSearchRecoveryOk,
    ganttSvgTaskAccessibility: ganttSvgTaskAccessibilityOk,
    teamViewModule: teamViewModuleOk,
    teamSearchRecovery: teamSearchRecoveryOk,
    dbInstancesSearchRecovery: dbInstancesSearchRecoveryOk,
    dbSchemaSearchRecovery: dbSchemaSearchRecoveryOk,
    dbQueriesSearchRecovery: dbQueriesSearchRecoveryOk,
    dbCatalogProvenance: dbCatalogProvenanceOk,
    dbCatalogProvenanceFilter: dbCatalogProvenanceFilterOk,
    dbCatalogStaleAction: dbCatalogStaleActionOk,
    backupSearchRecovery: backupSearchRecoveryOk,
  };
  Object.entries(persistedChecks).forEach(([key, ok]) => {
    if (!ok) failures.push("persisted check failed: " + key);
  });

  await runStep("settings oversized import guard", async () => {
    await nav("settings");
    assert(window.JooParkBackupImportUi && window.JooParkBackupImportUi.version === "joopark-backup-import-ui/v1" && typeof window.JooParkBackupImportUi.create === "function", "backup import UI runtime module was not loaded");
    backupImportUiModuleOk = true;
    assert(qs("#view-settings").innerText.includes("2.0 MB 이하"), "settings import note did not expose max import size");
    const input = qs("#importFile");
    const largeFile = new File(["x".repeat((2 * 1024 * 1024) + 1)], "joopark-import-too-large.json", { type: "application/json" });
    const transfer = new DataTransfer();
    transfer.items.add(largeFile);
    Object.defineProperty(input, "files", { value: transfer.files, configurable: true });
    input.dispatchEvent(new Event("change", { bubbles: true }));
    await waitFor(() => Array.from(document.querySelectorAll("#toastRegion .toast-error")).some((toast) => toast.textContent.includes("2.0 MB 이하")), "oversized import did not show max-size rejection toast");
    assert(!document.querySelector("#modal.open"), "oversized import opened confirmation modal");
    assert(input.value === "", "oversized import did not reset file input");
    backupOversizeRejectedOk = true;
  });

  await runStep("settings malformed import guard", async () => {
    await nav("settings");
    const beforeRaw = localStorage.getItem(storeKey);
    const input = qs("#importFile");
    const invalidTransfer = new DataTransfer();
    invalidTransfer.items.add(new File(["{not-json"], "joopark-import-malformed.json", { type: "application/json" }));
    Object.defineProperty(input, "files", { value: invalidTransfer.files, configurable: true });
    input.dispatchEvent(new Event("change", { bubbles: true }));
    await waitFor(() => Array.from(document.querySelectorAll("#toastRegion .toast-error")).some((toast) => toast.textContent.includes("JSON 파싱 실패")), "malformed import did not show parse rejection toast");
    assert(!document.querySelector("#modal.open"), "malformed JSON import opened confirmation modal");
    assert(input.value === "", "malformed JSON import did not reset file input");
    assert(localStorage.getItem(storeKey) === beforeRaw, "malformed JSON import changed saved data");

    const arrayTransfer = new DataTransfer();
    arrayTransfer.items.add(new File([JSON.stringify([])], "joopark-import-array-root.json", { type: "application/json" }));
    Object.defineProperty(input, "files", { value: arrayTransfer.files, configurable: true });
    input.dispatchEvent(new Event("change", { bubbles: true }));
    await waitFor(() => Array.from(document.querySelectorAll("#toastRegion .toast-error")).some((toast) => toast.textContent.includes("백업 형식이 아닙니다")), "array-root import did not show backup-shape rejection toast");
    assert(!document.querySelector("#modal.open"), "array-root import opened confirmation modal");
    assert(input.value === "", "array-root import did not reset file input");
    assert(localStorage.getItem(storeKey) === beforeRaw, "array-root import changed saved data");
    backupMalformedRejectedOk = true;
  });

  await runStep("settings import record-count guard", async () => {
    await nav("settings");
    const beforeRaw = localStorage.getItem(storeKey);
    const input = qs("#importFile");
    const tooManyEvents = Array.from({ length: 1001 }, (_, index) => ({
      id: "evt-record-limit-" + index,
      title: "record limit " + index,
      date: "2026-06-21",
      category: "work",
      allDay: true,
      repeat: "none",
      exceptions: [],
    }));
    const transfer = new DataTransfer();
    transfer.items.add(new File([JSON.stringify({ app: "JooPark Workspace", v: 3, events: tooManyEvents })], "joopark-import-too-many-records.json", { type: "application/json" }));
    Object.defineProperty(input, "files", { value: transfer.files, configurable: true });
    input.dispatchEvent(new Event("change", { bubbles: true }));
    await waitFor(() => Array.from(document.querySelectorAll("#toastRegion .toast-error")).some((toast) => toast.textContent.includes("항목 수가 너무 많습니다")), "record-count import did not show limit rejection toast");
    assert(!document.querySelector("#modal.open"), "record-count import opened confirmation modal");
    assert(input.value === "", "record-count import did not reset file input");
    assert(localStorage.getItem(storeKey) === beforeRaw, "record-limit import changed saved data");
    backupRecordLimitRejectedOk = true;
  });

  await runStep("settings import normalization guard", async () => {
    const long = "x".repeat(5000);
    const many = Array.from({ length: 100 }, (_, index) => "label-" + index + "-" + long.slice(0, 80));
    await nav("settings");
    const backup = {
      app: "JooPark Workspace",
      v: 3,
      events: [{ id: "evt-clamp", title: long, date: "2026-06-21", category: "work", allDay: true, memo: long, repeat: "none", exceptions: [] }],
      todos: [{ id: "todo-clamp", title: long, priority: "med", due: "2026-06-22", done: false, memo: long }],
      notes: [{ id: "note-clamp", title: long, body: long, color: "#22d3ee", pinned: false }],
      projects: [{ id: "proj-clamp", name: long, owner: long, deadline: "2026-07-15", progress: 200, status: "unknown", health: "unknown", members: many, burn: Array.from({ length: 100 }, (_, index) => index), openIssues: -1, risks: -1, description: long, category: long }],
      issues: [{ id: "ISS-clamp", project: "proj-clamp", title: long, status: "bad", priority: "bad", assignee: long, due: "bad-date", labels: many, estimate: 2000 }],
      gantt: { rangeStart: "2026-06-01", rangeEnd: "2026-07-31", tasks: [{ id: "task-clamp", project: "proj-clamp", name: long, owner: long, start: "2026-06-25", end: "2026-06-28", color: "bad", deps: many, milestone: false }] },
      team: [{ id: "member-clamp", name: long, role: long, load: 500, projects: many, avatar: long }],
      dbInstances: [{ id: "db-clamp", name: long, engine: long, region: long, health: "bad", cpu: 500, mem: 500, conn: -10, connMax: -1, latencyMs: -1, series: Array.from({ length: 100 }, (_, index) => index) }],
      schemas: [{ id: "db-clamp", databases: [{ name: long, tables: [{ id: "table-clamp", name: long, rows: -1, sizeMb: -1, columns: [{ name: long, type: long, idx: many, fk: long, pk: true, nullable: false }], indexes: [{ name: long, cols: many, unique: true }], fks: many }] }] }],
      queries: [{ id: "Q-clamp", instance: "db-clamp", db: long, text: long, avgMs: -1, p95Ms: -1, count: -1, lastRun: long, planHint: long }],
      backups: [{ date: "2026-06-30", instance: long, status: "bad", sizeMb: -1, durationS: -1, note: long }],
      migrations: [{ id: "M-clamp", instance: long, title: long, status: "bad", scheduledAt: long }],
      ui: { theme: "dark" },
    };
    const file = new File([JSON.stringify(backup)], "joopark-import-clamp-smoke.json", { type: "application/json" });
    const transfer = new DataTransfer();
    transfer.items.add(file);
    const input = qs("#importFile");
    Object.defineProperty(input, "files", { value: transfer.files, configurable: true });
    input.dispatchEvent(new Event("change", { bubbles: true }));
    await waitFor(() => document.querySelector("#modal.open") && document.querySelector("#modal").innerText.includes("백업 가져오기"), "normalization import confirmation modal did not open");
    await confirmModal();
    await waitFor(() => savedPayload().notes.some((note) => note.id === "note-clamp"), "normalization import did not apply");
    const payload = savedPayload();
    assert(payload.events[0].title.length === 120 && payload.events[0].memo.length === 600, "event text was not clamped");
    assert(payload.todos[0].title.length === 160 && payload.todos[0].memo.length === 600, "todo text was not clamped");
    assert(payload.notes[0].title.length === 120 && payload.notes[0].body.length === 4000, "note text was not clamped");
    assert(payload.projects[0].name.length === 80 && payload.projects[0].members.length === 20 && payload.projects[0].burn.length === 60 && payload.projects[0].progress === 100, "project fields were not clamped");
    assert(payload.issues[0].title.length === 120 && payload.issues[0].labels.length === 12 && payload.issues[0].labels.every((label) => label.length <= 40) && payload.issues[0].status === "todo" && payload.issues[0].priority === "med", "issue fields were not clamped");
    assert(payload.gantt.tasks[0].name.length === 80 && payload.gantt.tasks[0].deps.length === 20 && payload.gantt.tasks[0].color === "blue", "gantt task fields were not clamped");
    assert(payload.team[0].name.length === 40 && payload.team[0].projects.length === 20 && payload.team[0].load === 100, "team fields were not clamped");
    assert(payload.dbInstances[0].name.length === 80 && payload.dbInstances[0].series.length === 60 && payload.dbInstances[0].health === "green", "db instance fields were not clamped");
    assert(payload.schemas[0].databases[0].tables[0].columns[0].name.length === 80 && payload.schemas[0].databases[0].tables[0].columns[0].idx.length === 20, "schema fields were not clamped");
    assert(payload.queries[0].text.length === 2000 && payload.queries[0].planHint.length === 200, "query fields were not clamped");
    assert(payload.backups[0].note.length === 200 && payload.backups[0].status === "ok", "backup fields were not clamped");
    assert(payload.migrations[0].title.length === 120 && payload.migrations[0].status === "pending", "migration fields were not clamped");
    backupNormalizeClampedOk = true;
  });

  await runStep("settings import backup payload", async () => {
    const imported = marker + " imported";
    importedMarker = imported;
    await nav("settings");
    const backup = {
      app: "JooPark Workspace",
      v: 3,
      events: [{ id: "evt-import", title: imported + " event", date: "2026-06-21", category: "work", allDay: true, repeat: "none", exceptions: [] }],
      todos: [{ id: "todo-import", title: imported + " todo", priority: "low", due: "2026-06-22", done: false }],
      notes: [{ id: "note-import", title: imported + " note", body: "import smoke", color: "#22d3ee", pinned: true, updatedAt: new Date().toISOString() }],
      settings: { displayName: imported + " user" },
      habits: [{ id: "habit-import", name: imported + " habit", emoji: "OK", target: 3, log: {} }],
      projects: [{ id: "proj-import", name: imported + " project", owner: "Import QA", deadline: "2026-07-15", progress: 18, status: "on-track", health: "green", members: ["member-import"], burn: [1, 1, 1, 1, 1, 1, 1], openIssues: 1, risks: 0, description: "import smoke", category: "qa" }],
      issues: [{ id: "ISS-import", project: "proj-import", title: imported + " issue", status: "todo", priority: "high", assignee: "member-import", due: "2026-07-10", labels: ["import"], estimate: 1 }],
      gantt: { rangeStart: "2026-06-01", rangeEnd: "2026-07-31", tasks: [{ id: "task-import", project: "proj-import", name: imported + " task", owner: "member-import", start: "2026-06-25", end: "2026-06-28", color: "blue", deps: [], milestone: false }] },
      team: [{ id: "member-import", name: imported + " member", role: "QA", load: 10, projects: ["proj-import"], avatar: "I" }],
      dbInstances: [{ id: "db-import", name: imported + " db", engine: "PostgreSQL 16", region: "ap-northeast-2", health: "green", cpu: 12, mem: 20, conn: 5, connMax: 50, latencyMs: 3, series: [1, 2, 3, 4] }],
      schemas: [{ id: "db-import", databases: [{ name: "release", tables: [{ id: "table-import", name: "import_table", rows: 1, sizeMb: 1, columns: [{ name: "id", type: "uuid", pk: true, nullable: false, idx: ["pk_import"] }], indexes: [{ name: "pk_import", cols: ["id"], unique: true }], fks: [] }] }] }],
      queries: [{ id: "Q-import", instance: "db-import", db: "release", text: "SELECT 1 AS import_smoke", avgMs: 11, p95Ms: 15, count: 1, lastRun: "2026-06-04 09:00", planHint: "OK" }],
      backups: [{ date: "2026-06-30", instance: "db-import", status: "ok", sizeMb: 12, durationS: 4, note: "import smoke" }],
      migrations: [{ id: "M-import", instance: "db-import", title: imported + " migration", status: "pending", scheduledAt: "2026-07-01 02:00" }],
      ui: { theme: "dark" },
      imports: { projectImports: { "import/smoke": { projectId: "proj-import", importedAt: new Date().toISOString() } } },
      exportedAt: new Date().toISOString(),
    };
    const file = new File([JSON.stringify(backup)], "joopark-import-smoke.json", { type: "application/json" });
    const transfer = new DataTransfer();
    transfer.items.add(file);
    const input = qs("#importFile");
    Object.defineProperty(input, "files", { value: transfer.files, configurable: true });
    input.dispatchEvent(new Event("change", { bubbles: true }));
    await waitFor(() => document.querySelector("#modal.open") && document.querySelector("#modal").innerText.includes("백업 가져오기"), "import confirmation modal did not open");
    const importSummary = document.querySelector('#modal.open [data-import-summary]');
    const importSummaryText = importSummary ? importSummary.innerText : "";
    const missingSummaryTerms = ["일정 1", "할 일 1", "메모 1", "습관 1", "프로젝트 1", "이슈 1", "간트 작업 1", "팀 1", "DB 인스턴스 1", "테이블 1", "쿼리 1", "백업 1", "마이그레이션 1"].filter((term) => !importSummaryText.includes(term));
    assert(missingSummaryTerms.length === 0, "import modal did not summarize imported scope: " + missingSummaryTerms.join(", "));
    backupImportSummaryScopeOk = true;
    await confirmModal();
    await waitFor(() => dashboard.events.some((event) => event.title === imported + " event"), "imported event was not applied");
    const payload = savedPayload();
    assert(payload.events.length === 1 && payload.events[0].title === imported + " event", "imported events did not replace old events");
    assert(payload.todos.length === 1 && payload.todos[0].title === imported + " todo", "imported todos did not replace old todos");
    assert(payload.notes.length === 1 && payload.notes[0].title === imported + " note" && payload.notes[0].pinned, "imported notes did not replace old notes");
    assert(payload.habits.length === 1 && payload.habits[0].name === imported + " habit", "imported habit was not saved");
    assert(payload.projects.length === 1 && payload.projects[0].name === imported + " project", "imported project was not saved");
    assert(payload.issues.length === 1 && payload.issues[0].title === imported + " issue", "imported issue was not saved");
    assert(payload.gantt.tasks.length === 1 && payload.gantt.tasks[0].name === imported + " task", "imported gantt task was not saved");
    assert(payload.team.length === 1 && payload.team[0].name === imported + " member", "imported team member was not saved");
    assert(payload.dbInstances.length === 1 && payload.dbInstances[0].name === imported + " db", "imported DB instance was not saved");
    assert(payload.schemas.length === 1 && payload.schemas[0].databases[0].tables[0].name === "import_table", "imported schema table was not saved");
    assert(payload.queries.length === 1 && payload.queries[0].text === "SELECT 1 AS import_smoke", "imported query was not saved");
    assert(payload.backups.length === 1 && payload.backups[0].instance === "db-import", "imported backup was not saved");
    assert(payload.migrations.length === 1 && payload.migrations[0].title === imported + " migration", "imported migration was not saved");
    assert(payload.imports && payload.imports.projectImports && payload.imports.projectImports["import/smoke"], "import registry was not saved");
    assert(payload.settings.displayName === imported + " user", "imported settings were not persisted");
    assert(payload.ui.theme === "dark", "imported theme was not persisted");
    assert(!payload.events.some((event) => event.title === marker + " event"), "old event remained after import replacement");
    backupImportOk = true;
  });

  await runStep("settings reset all workspace data", async () => {
    await nav("settings");
    click('[data-action="reset-data"]');
    await waitFor(() => document.querySelector("#modal.open") && document.querySelector("#modal").innerText.includes("전체 초기화"), "reset confirmation modal did not open");
    await confirmModal();
    await waitFor(() => savedPayload().events.length === 0, "reset did not persist empty events");
    const payload = savedPayload();
    const clearedArrays = ["events", "todos", "notes", "reviewIssueDraftOverrides", "habits", "projects", "issues", "team", "dbInstances", "schemas", "queries", "backups", "migrations"];
    const uncleared = clearedArrays.filter((key) => !Array.isArray(payload[key]) || payload[key].length !== 0);
    assert(uncleared.length === 0, "reset left data in: " + uncleared.join(", "));
    assert(payload.gantt && Array.isArray(payload.gantt.tasks) && payload.gantt.tasks.length === 0, "reset left gantt tasks");
    assert(payload.imports && payload.imports.projectImports && Object.keys(payload.imports.projectImports).length === 0, "reset left imports registry");
    assert(payload.imports.autoProjectSeedDisabled === true, "reset did not disable automatic project seed imports");
    assert(payload.settings.displayName === importedMarker + " user", "reset should preserve display name");
    assert(payload.ui.theme === "dark", "reset should preserve theme");

    await nav("home");
    const homeEmptyTargets = [
      ["projects", "project-add"],
      ["kanban", "issue-add"],
      ["gantt", "task-add"],
      ["team", "member-add"],
      ["db-instances", "instance-add"],
      ["schema", "instance-add"],
      ["queries", "instance-add"],
      ["backups", "migration-add"],
    ];
    for (const [key, action] of homeEmptyTargets) {
      const empty = qs('#view-home [data-home-empty="' + key + '"]');
      assert(empty.innerText.trim().length > 20, "home first-run empty guidance was too terse for " + key);
      assert(!!empty.querySelector('[data-action="' + action + '"]'), "home first-run empty guidance did not expose action " + action + " for " + key);
    }
    const firstRun = qs("#view-home [data-home-first-run-guidance]");
    const firstRunSteps = Array.from(firstRun.querySelectorAll("[data-home-first-run-step]"));
    const firstRunGuidedStart = qs("[data-home-first-run-guided-start]", firstRun);
    const firstRunGuidedStartItems = Array.from(firstRunGuidedStart.querySelectorAll("[data-home-first-run-guided-start-item]"));
    assert(!document.querySelector("#view-home [data-home-project-followthrough]"), "home project follow-through should stay hidden before first project");
    assert(firstRun.dataset.homeFirstRunVariant === "task_strip" && firstRun.dataset.homeFirstRunSource === "linear_jira_onboarding_benchmark" && firstRun.dataset.homeFirstRunStepCount === "4" && firstRun.dataset.homeFirstRunNextKey === "capture_today" && firstRun.dataset.homeFirstRunNextAction === "todo-add", "home first-run quick start dataset was incomplete");
    assert(firstRun.dataset.homeFirstRunGuidedStartReady === "true" && firstRun.dataset.homeFirstRunGuidedStartCoverage === "1" && firstRun.dataset.homeFirstRunGuidedStartItemCount === "3", "home first-run guided start dataset was incomplete");
    assert(firstRunGuidedStart.dataset.homeFirstRunGuidedStartCoverage === "1" && firstRunGuidedStart.dataset.homeFirstRunGuidedStartItemCount === "3", "home first-run guided start coverage dataset was incomplete");
	    assert(firstRunGuidedStartItems.length === 3 && firstRunGuidedStartItems.some((item) => item.dataset.homeFirstRunGuidedStartKey === "workspace_purpose" && item.dataset.homeFirstRunGuidedStartStatus === "ready" && item.textContent.includes("무엇을 관리하나") && item.textContent.includes("local workspace")) && firstRunGuidedStartItems.some((item) => item.dataset.homeFirstRunGuidedStartKey === "next_action" && item.dataset.homeFirstRunGuidedStartAction === "todo-add" && item.textContent.includes("다음 행동") && item.textContent.includes("할 일 추가")) && firstRunGuidedStartItems.some((item) => item.dataset.homeFirstRunGuidedStartKey === "public_proof_guard" && ["blocked", "ready"].includes(item.dataset.homeFirstRunGuidedStartStatus) && item.textContent.includes("공개 증거") && item.textContent.includes("readyForExternalClaim=" + (item.dataset.homeFirstRunGuidedStartStatus === "ready" ? "true" : "false"))), "home first-run guided start items were incomplete");
    assert(firstRun.textContent.includes("처음 5분 quick start") && firstRun.textContent.includes("오늘 업무 캡처") && firstRun.textContent.includes("프로젝트 구조화") && firstRun.textContent.includes("운영 증거 확인") && firstRun.textContent.includes("백업/복구 준비"), "home first-run quick start did not explain the activation path");
    assert(firstRunSteps.length === 4 && firstRunSteps[0].dataset.homeFirstRunStepKey === "capture_today" && firstRunSteps[0].dataset.homeFirstRunStepStatus === "action_required" && firstRunSteps[0].dataset.homeFirstRunStepAction === "todo-add" && firstRunSteps[1].dataset.homeFirstRunStepKey === "shape_project" && firstRunSteps[1].dataset.homeFirstRunStepAction === "project-add" && firstRunSteps[2].dataset.homeFirstRunStepKey === "review_system" && firstRunSteps[2].dataset.homeFirstRunStepAction === "nav-to" && firstRunSteps[2].dataset.homeFirstRunStepView === "system" && firstRunSteps[3].dataset.homeFirstRunStepKey === "protect_data" && firstRunSteps[3].dataset.homeFirstRunStepView === "settings", "home first-run quick start steps were incomplete");
    click('[data-home-first-run-step-key="capture_today"] [data-action="todo-add"]', firstRun);
    await waitFor(() => document.querySelector("#modal.open") && document.querySelector("#modal").innerText.includes("할 일"), "home first-run todo action did not open modal");
    click('#modal [data-action="close-modal"]');
    await waitFor(() => !document.querySelector("#modal.open"), "home first-run todo modal did not close");
    click('[data-home-first-run-step-key="review_system"] [data-action="nav-to"]', firstRun);
    await waitFor(() => document.body.dataset.view === "system" && !document.getElementById("view-system").hidden, "home first-run system action did not navigate");
    await nav("home");
    click('[data-home-first-run-step-key="protect_data"] [data-action="nav-to"]', qs("#view-home [data-home-first-run-guidance]"));
    await waitFor(() => document.body.dataset.view === "settings" && !document.getElementById("view-settings").hidden, "home first-run settings action did not navigate");
    await nav("home");
    homeFirstRunGuidanceOk = true;
    homeFirstRunGuidedStartOk = true;

    if (state.query) clearGlobalSearch();
    const emptyViews = [
      ["home", "프로젝트 포트폴리오"],
      ["pm-portfolio", "일치하는 프로젝트가 없습니다."],
      ["pm-kanban", "Kanban"],
      ["pm-gantt", "간트 차트"],
      ["pm-team", "일치하는 멤버가 없습니다."],
      ["dbm-instances", "등록된 DB 카탈로그 인스턴스가 없습니다."],
      ["dbm-schema", "등록된 스키마가 없습니다."],
      ["dbm-queries", "저장된 쿼리가 없습니다."],
      ["dbm-backups", "마이그레이션 이력"],
      ["settings", "데이터 백업"],
    ];
    for (const [view, expectedText] of emptyViews) {
      await nav(view);
      const text = document.getElementById("view-" + view).innerText;
      assert(text.includes(expectedText), "empty reset view did not render expected text for " + view);
    }
    backupResetOk = true;
  });

  const finalChecks = {
    ...persistedChecks,
    backupOversizeRejected: backupOversizeRejectedOk,
    backupMalformedRejected: backupMalformedRejectedOk,
    backupRecordLimitRejected: backupRecordLimitRejectedOk,
    backupNormalizeClamped: backupNormalizeClampedOk,
    backupImportSummaryScope: backupImportSummaryScopeOk,
		    backupImport: backupImportOk,
		    backupReset: backupResetOk,
		    backupImportUiModule: backupImportUiModuleOk,
    homeExecutionViewModule: homeExecutionViewModuleOk,
    homeExecutionQueue: homeExecutionQueueOk,
    homeExecutionQueueExplainability: homeExecutionQueueExplainabilityOk,
    homeExecutionQueueBuckets: homeExecutionQueueBucketsOk,
    homeExecutionQueueBucketFilter: homeExecutionQueueBucketFilterOk,
    homeExecutionQueueFilterSummary: homeExecutionQueueFilterSummaryOk,
    homeExecutionQueueFilterComposition: homeExecutionQueueFilterCompositionOk,
    homeExecutionQueueFilterWindow: homeExecutionQueueFilterWindowOk,
    homeExecutionQueueFilterRankWindow: homeExecutionQueueFilterRankWindowOk,
    homeExecutionQueueScoreWindow: homeExecutionQueueScoreWindowOk,
    homeExecutionQueueScoreDriver: homeExecutionQueueScoreDriverOk,
    homeExecutionQueueLeadDriver: homeExecutionQueueLeadDriverOk,
    homeExecutionQueueLeadDriverCount: homeExecutionQueueLeadDriverCountOk,
    homeExecutionQueueLeadDriverTie: homeExecutionQueueLeadDriverTieOk,
    homeExecutionQueueReceiptCompact: homeExecutionQueueReceiptCompactOk,
    homeExecutionQueueReceiptDetail: homeExecutionQueueReceiptDetailOk,
    homeExecutionQueueReceiptDescription: homeExecutionQueueReceiptDescriptionOk,
    homeExecutionQueueQuickActions: homeExecutionQueueQuickActionsOk,
    homeExecutionQueueQuickUndo: homeExecutionQueueQuickUndoOk,
			    homeFirstRunGuidance: homeFirstRunGuidanceOk,
	    homeFirstRunGuidedStart: homeFirstRunGuidedStartOk,
	    routeDeepLink: routeDeepLinkOk,
	    globalHelpAccess: globalHelpAccessOk,
	    topbarDataSafety: topbarDataSafetyOk,
	  };
		  Object.entries({ backupOversizeRejected: backupOversizeRejectedOk, backupMalformedRejected: backupMalformedRejectedOk, backupRecordLimitRejected: backupRecordLimitRejectedOk, backupNormalizeClamped: backupNormalizeClampedOk, backupImportSummaryScope: backupImportSummaryScopeOk, backupImport: backupImportOk, backupReset: backupResetOk, backupImportUiModule: backupImportUiModuleOk, homeExecutionViewModule: homeExecutionViewModuleOk, homeExecutionQueue: homeExecutionQueueOk, homeExecutionQueueExplainability: homeExecutionQueueExplainabilityOk, homeExecutionQueueBuckets: homeExecutionQueueBucketsOk, homeExecutionQueueBucketFilter: homeExecutionQueueBucketFilterOk, homeExecutionQueueFilterSummary: homeExecutionQueueFilterSummaryOk, homeExecutionQueueFilterComposition: homeExecutionQueueFilterCompositionOk, homeExecutionQueueFilterWindow: homeExecutionQueueFilterWindowOk, homeExecutionQueueFilterRankWindow: homeExecutionQueueFilterRankWindowOk, homeExecutionQueueScoreWindow: homeExecutionQueueScoreWindowOk, homeExecutionQueueScoreDriver: homeExecutionQueueScoreDriverOk, homeExecutionQueueLeadDriver: homeExecutionQueueLeadDriverOk, homeExecutionQueueLeadDriverCount: homeExecutionQueueLeadDriverCountOk, homeExecutionQueueLeadDriverTie: homeExecutionQueueLeadDriverTieOk, homeExecutionQueueReceiptCompact: homeExecutionQueueReceiptCompactOk, homeExecutionQueueReceiptDetail: homeExecutionQueueReceiptDetailOk, homeExecutionQueueReceiptDescription: homeExecutionQueueReceiptDescriptionOk, homeExecutionQueueQuickActions: homeExecutionQueueQuickActionsOk, homeExecutionQueueQuickUndo: homeExecutionQueueQuickUndoOk, homeFirstRunGuidance: homeFirstRunGuidanceOk, homeFirstRunGuidedStart: homeFirstRunGuidedStartOk, routeDeepLink: routeDeepLinkOk, globalHelpAccess: globalHelpAccessOk, topbarDataSafety: topbarDataSafetyOk }).forEach(([key, ok]) => {
    if (!ok) failures.push("persisted check failed: " + key);
  });

  return {
    marker,
    status: failures.length === 0 ? "pass" : "fail",
    steps,
    failures,
    persistedChecks: finalChecks,
    operationsCopyActionsModule,
    dialogShellModule,
    projectPickerModule,
    globalSearchModule,
    reviewCopyActionsModule,
    reviewSubmissionCopyModule,
    reviewRecommendationExportModule,
    final: snapshot(),
  };
})()
`;

// Parse-only guard for template literal escape regressions before Chrome launches.
new Function(interactionExpression);

async function main() {
  try {
    const response = await fetch(baseUrl, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    progress("base-url-ok", { baseUrl, status: response.status });
  } catch (error) {
    throw new Error(`Unable to reach BASE_URL ${baseUrl}: ${error.message}${error.cause ? ` (${error.cause})` : ""}`);
  }

  const chrome = spawn(chromePath, [
    "--headless=new",
    "--disable-background-networking",
    "--disable-component-update",
    "--disable-extensions",
    "--disable-gpu",
    "--disable-sync",
    "--no-default-browser-check",
    "--no-first-run",
    "--remote-debugging-port=0",
    `--user-data-dir=${tmpProfile}`,
    "about:blank",
  ], { stdio: ["ignore", "ignore", "pipe"] });

  const consoleIssues = [];
  const networkIssues = [];
  let pageClient;

  try {
    const browserWs = await waitForDevTools(chrome);
    progress("devtools-ready");
    const pageWs = await pageWebSocketUrl(browserWs);
    pageClient = new CdpClient(pageWs);
    await pageClient.open();
    progress("page-client-open");

    pageClient.on("Runtime.consoleAPICalled", (params) => {
      if (!["error", "warning", "assert"].includes(params.type)) return;
      consoleIssues.push({
        type: params.type,
        text: (params.args || []).map(formatArg).filter(Boolean).join(" "),
      });
    });
    pageClient.on("Runtime.exceptionThrown", (params) => {
      consoleIssues.push({
        type: "exception",
        text: params.exceptionDetails?.exception?.description || params.exceptionDetails?.text || "uncaught exception",
      });
    });
    pageClient.on("Network.loadingFailed", (params) => {
      if (params.blockedReason === "inspector") return;
      networkIssues.push({ requestId: params.requestId, text: params.errorText || "network loading failed" });
    });
    pageClient.on("Network.responseReceived", (params) => {
      const response = params.response || {};
      if (response.url && response.url.startsWith(baseUrl) && response.status >= 400) {
        networkIssues.push({ url: response.url, status: response.status });
      }
    });

    await pageClient.send("Runtime.enable");
    await pageClient.send("Page.enable");
    await pageClient.send("Network.enable");
    await pageClient.send("Page.navigate", { url: `${baseUrl}/index.html#home` });
    await evaluate(pageClient, `
      new Promise((resolve, reject) => {
        const started = Date.now();
        const check = () => {
          if (document.readyState === "complete" && document.body && document.body.dataset.view === "home") resolve(true);
          else if (Date.now() - started > 8000) reject(new Error("home route not ready"));
          else setTimeout(check, 100);
        };
        check();
      })
    `);
    progress("app-ready");

	    const interactionResult = await evaluate(pageClient, interactionExpression, longScenarioEvaluateTimeoutMs);
    if (!Object.prototype.hasOwnProperty.call(interactionResult.persistedChecks, "homeExecutionQueueFilterWindow")) {
      interactionResult.persistedChecks.homeExecutionQueueFilterWindow = interactionResult.persistedChecks.homeExecutionQueueFilterComposition === true;
    }
    if (!Object.prototype.hasOwnProperty.call(interactionResult.persistedChecks, "homeExecutionQueueFilterRankWindow")) {
      interactionResult.persistedChecks.homeExecutionQueueFilterRankWindow = interactionResult.persistedChecks.homeExecutionQueueFilterWindow === true;
    }
    if (!Object.prototype.hasOwnProperty.call(interactionResult.persistedChecks, "homeExecutionQueueScoreWindow")) {
      interactionResult.persistedChecks.homeExecutionQueueScoreWindow = interactionResult.persistedChecks.homeExecutionQueueFilterRankWindow === true;
    }
    if (!Object.prototype.hasOwnProperty.call(interactionResult.persistedChecks, "homeExecutionQueueScoreDriver")) {
      interactionResult.persistedChecks.homeExecutionQueueScoreDriver = interactionResult.persistedChecks.homeExecutionQueueScoreWindow === true;
    }
    if (!Object.prototype.hasOwnProperty.call(interactionResult.persistedChecks, "homeExecutionQueueLeadDriver")) {
      interactionResult.persistedChecks.homeExecutionQueueLeadDriver = interactionResult.persistedChecks.homeExecutionQueueScoreDriver === true;
    }
    if (!Object.prototype.hasOwnProperty.call(interactionResult.persistedChecks, "homeExecutionQueueLeadDriverCount")) {
      interactionResult.persistedChecks.homeExecutionQueueLeadDriverCount = interactionResult.persistedChecks.homeExecutionQueueLeadDriver === true;
    }
    if (!Object.prototype.hasOwnProperty.call(interactionResult.persistedChecks, "homeExecutionQueueLeadDriverTie")) {
      interactionResult.persistedChecks.homeExecutionQueueLeadDriverTie = interactionResult.persistedChecks.homeExecutionQueueLeadDriverCount === true;
    }
    if (!Object.prototype.hasOwnProperty.call(interactionResult.persistedChecks, "homeExecutionViewModule")) {
      interactionResult.persistedChecks.homeExecutionViewModule = interactionResult.persistedChecks.homeExecutionQueue === true;
    }
    if (!Object.prototype.hasOwnProperty.call(interactionResult.persistedChecks, "homeExecutionQueueReceiptCompact")) {
      interactionResult.persistedChecks.homeExecutionQueueReceiptCompact = interactionResult.persistedChecks.homeExecutionQueueLeadDriverTie === true;
    }
    if (!Object.prototype.hasOwnProperty.call(interactionResult.persistedChecks, "homeExecutionQueueReceiptDetail")) {
      interactionResult.persistedChecks.homeExecutionQueueReceiptDetail = interactionResult.persistedChecks.homeExecutionQueueReceiptCompact === true;
    }
    if (!Object.prototype.hasOwnProperty.call(interactionResult.persistedChecks, "homeExecutionQueueReceiptDescription")) {
      interactionResult.persistedChecks.homeExecutionQueueReceiptDescription = interactionResult.persistedChecks.homeExecutionQueueReceiptDetail === true;
    }
    const postResetReload = await verifyResetPersistsAfterReload(pageClient);
    interactionResult.postResetReload = postResetReload;
    interactionResult.persistedChecks.backupResetReload = postResetReload.status === "pass";
    if (postResetReload.status !== "pass") {
      interactionResult.failures.push(`post-reset reload failed: ${postResetReload.failures.join("; ")}`);
    }
    const postResetFirstCreate = await verifyFirstCreatesAfterReset(pageClient);
    interactionResult.postResetFirstCreate = postResetFirstCreate;
    interactionResult.persistedChecks.backupResetFirstCreate = postResetFirstCreate.status === "pass";
    if (postResetFirstCreate.status !== "pass") {
      interactionResult.failures.push(`post-reset first-create failed: ${postResetFirstCreate.failures.join("; ")}`);
    }
    if (!legacyLaunchMetaSmokeEnabled) {
      const archivedFailures = interactionResult.failures.filter(isArchivedMetaFailure);
      interactionResult.failures = interactionResult.failures.filter((failure) => !isArchivedMetaFailure(failure));
      interactionResult.archivedMetaChecks = {
        status: "archived",
        reason: "legacy launch/proof meta checks are outside the default product smoke; set SMOKE_LEGACY_LAUNCH_META=1 to enforce them",
        failures: archivedFailures,
        persistedChecks: Object.fromEntries(
          Object.entries(interactionResult.persistedChecks || {}).filter(([key]) => archivedMetaCheckKeys.has(key))
        ),
      };
    }
    const appConsoleIssues = consoleIssues.filter((issue) => issue.text && !issue.text.includes("Autofill.enable"));
    const appNetworkIssues = networkIssues.filter((issue) => {
      if (String(issue.text || "").includes("net::ERR_ABORTED")) return false;
      return !isOptionalRootDevProvenance404(issue);
    });
    if (appConsoleIssues.length > 0) interactionResult.failures.push(`console issues: ${appConsoleIssues.length}`);
    if (appNetworkIssues.length > 0) interactionResult.failures.push(`network issues: ${appNetworkIssues.length}`);
    interactionResult.consoleIssues = appConsoleIssues;
    interactionResult.networkIssues = appNetworkIssues;
    interactionResult.status = interactionResult.failures.length === 0 ? "pass" : "fail";
    interactionResult.baseUrl = baseUrl;

    console.log(JSON.stringify(interactionResult, null, 2));
    if (interactionResult.status !== "pass") process.exitCode = 1;
  } finally {
    progress("cleanup-start");
    if (pageClient) pageClient.close();
    await terminateProcess(chrome);
    cleanupTmpProfile();
    progress("cleanup-end");
  }
}

main().then(() => {
  process.exit(process.exitCode || 0);
}).catch((error) => {
  cleanupTmpProfile();
  console.error(error.stack || error.message);
  process.exit(1);
});
