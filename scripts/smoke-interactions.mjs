#!/usr/bin/env node

import { spawn } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const chromePath = process.env.CHROME_PATH || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const baseUrl = (process.env.BASE_URL || "http://127.0.0.1:5178").replace(/\/+$/, "");
const tmpProfile = mkdtempSync(join(tmpdir(), "joopark-interaction-smoke-"));
const progressEnabled = process.env.SMOKE_PROGRESS === "1";
const defaultCdpTimeoutMs = 10000;
const defaultEvaluateTimeoutMs = Number(process.env.SMOKE_RUNTIME_TIMEOUT_MS || 60000);
const longScenarioEvaluateTimeoutMs = Number(process.env.SMOKE_LONG_SCENARIO_TIMEOUT_MS || process.env.SMOKE_RUNTIME_TIMEOUT_MS || 120000);
const resetScenarioEvaluateTimeoutMs = 60000;

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

async function verifyResetPersistsAfterReload(client) {
  await client.send("Page.reload", { ignoreCache: true });
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
      const clearedArrays = ["events", "todos", "notes", "habits", "projects", "issues", "team", "dbInstances", "schemas", "queries", "migrations"];
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
  const storeKey = "joopark.workspace.v3";
  const steps = [];
  const failures = [];
  let backupExportOk = false;
  let backupImportOk = false;
  let backupResetOk = false;
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
  let candidateBenchmarkFocusVisibleOk = false;
  let candidateBenchmarkQueueVisibleOk = false;
  let candidateBenchmarkRubricVisibleOk = false;
  let candidateBenchmarkRubricScoreVisibleOk = false;
  let candidateBenchmarkRecommendationExportVisibleOk = false;
  let candidateBenchmarkReviewQueueVisibleOk = false;
  let candidateBenchmarkReviewHandoffVisibleOk = false;
  let candidateBenchmarkReviewHandoffCopyVisibleOk = false;
  let candidateBenchmarkReviewIssueDraftVisibleOk = false;
  let portfolioCandidateFilterOk = false;
  let portfolioCandidateRankedOk = false;
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
  async function runStep(name, fn) {
    const before = snapshot();
    try {
      await fn();
      steps.push({ name, status: "pass", before, after: snapshot() });
    } catch (error) {
      failures.push(name + ": " + error.message);
      steps.push({ name, status: "fail", error: error.message, before, after: snapshot() });
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

  await runStep("workspace candidate portfolio search", async () => {
    await nav("pm-portfolio");
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
    const riskCandidate = dashboard.projects.find((project) => project.name === "opf/openproject");
    assert(riskCandidate && projectCandidateAction(riskCandidate)?.label === "리스크 리뷰", "OpenProject candidate risk action was not computed");
    const adoptionResponse = await fetch("./data/adoption-candidates.json", { cache: "no-store" });
    assert(adoptionResponse.ok, "adoption candidate snapshot did not load for metadata refresh");
    const adoptionSnapshot = await adoptionResponse.json();
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
    candidateBenchmarkRubricVisibleOk = true;
    candidateBenchmarkRubricScoreVisibleOk = true;
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
    const reviewHandoff = qs("[data-benchmark-review-handoff]", reviewQueue);
    const reviewHandoffDownload = qs("[data-review-handoff-download]", reviewHandoff);
    const reviewHandoffCopy = qs("[data-review-handoff-copy]", reviewHandoff);
    const reviewHandoffText = qs("[data-review-handoff-text]", reviewHandoff).innerText;
    assert(reviewHandoff.dataset.reviewHandoffPrimaryKey === "benchmark-review:repo-taskosaur-taskosaur:86", "benchmark review handoff primary key did not render");
    assert(reviewHandoff.dataset.reviewHandoffCount === "2", "benchmark review handoff count did not render");
    assert(reviewHandoffDownload.getAttribute("download") === "joopark-benchmark-review-queue.md", "benchmark review handoff filename did not render");
    assert(reviewHandoffDownload.getAttribute("href").startsWith("data:text/markdown;charset=utf-8,"), "benchmark review handoff markdown link did not render");
    assert(reviewHandoffText.includes("Primary decision key: benchmark-review:repo-taskosaur-taskosaur:86") && reviewHandoffText.includes("Taskosaur/Taskosaur - 도입 검토") && reviewHandoffText.includes("happybhati/workstream - 비교 유지"), "benchmark review handoff markdown copy did not render");
    assert(reviewHandoffCopy.dataset.reviewHandoffCopyKey === "benchmark-review:repo-taskosaur-taskosaur:86", "benchmark review handoff copy key did not render");
    window.__smokeClipboardText = "";
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: async (text) => { window.__smokeClipboardText = text; } },
    });
    click("[data-review-handoff-copy]");
    await waitFor(() => window.__smokeClipboardText.includes("Primary decision key: benchmark-review:repo-taskosaur-taskosaur:86"), "benchmark review handoff copy text did not reach clipboard");
    await waitFor(() => reviewHandoff.dataset.reviewHandoffCopied === "true", "benchmark review handoff copy state did not update");
    assert(qs("[data-review-handoff-copy-status]", reviewHandoff).textContent.includes("복사됨"), "benchmark review handoff copy status did not render");
    const reviewIssueDraft = qs("[data-review-issue-draft]", reviewHandoff);
    const reviewIssueCreate = qs("[data-review-issue-create]", reviewIssueDraft);
    const reviewIssueBody = qs("[data-issue-draft-body]", reviewIssueDraft).innerText;
    assert(reviewIssueDraft.dataset.issueDraftTitle === "[Benchmark] Taskosaur/Taskosaur 도입 검토", "benchmark review issue draft title did not render");
    assert(reviewIssueDraft.dataset.issueDraftProject === "Taskosaur/Taskosaur", "benchmark review issue draft project did not render");
    assert(reviewIssueDraft.dataset.issueDraftPriority === "high", "benchmark review issue draft priority did not render");
    assert(reviewIssueDraft.dataset.issueDraftKey === "benchmark-review:repo-taskosaur-taskosaur:86", "benchmark review issue draft key did not render");
    assert(reviewIssueBody.includes("Persist key: benchmark-review:repo-taskosaur-taskosaur:86") && reviewIssueBody.includes("Compare with: happybhati/workstream"), "benchmark review issue draft body did not render");
    const beforeIssueCount = dashboard.issues.length;
    click("[data-review-issue-create]", reviewIssueDraft);
    await waitFor(() => dashboard.issues.length === beforeIssueCount + 1, "benchmark review issue draft did not create an issue");
    const createdIssue = dashboard.issues.find((issue) => issue.sourceKey === "benchmark-review:repo-taskosaur-taskosaur:86");
    assert(createdIssue, "benchmark review issue draft did not persist source key");
    assert(createdIssue.title === "[Benchmark] Taskosaur/Taskosaur 도입 검토", "benchmark review issue draft title was not saved");
    assert(createdIssue.project === "repo-taskosaur-taskosaur", "benchmark review issue draft project was not saved");
    assert(createdIssue.priority === "high", "benchmark review issue draft priority was not saved");
    assert(createdIssue.labels.includes("benchmark") && createdIssue.labels.includes("handoff"), "benchmark review issue draft labels were not saved");
    await waitFor(() => {
      const nextDraft = document.querySelector("[data-review-issue-draft]");
      return nextDraft && nextDraft.dataset.issueDraftCreated === "true" && nextDraft.dataset.issueDraftId === createdIssue.id;
    }, "benchmark review issue draft created state did not render");
    candidateBenchmarkRubricVisibleOk = true;
    candidateBenchmarkRubricScoreVisibleOk = true;
    candidateBenchmarkReviewQueueVisibleOk = true;
    candidateBenchmarkReviewHandoffVisibleOk = true;
    candidateBenchmarkReviewHandoffCopyVisibleOk = true;
    candidateBenchmarkReviewIssueDraftVisibleOk = true;
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
    candidateBenchmarkRecommendationExportVisibleOk = true;
    candidateBenchmarkReviewQueueVisibleOk = true;
    candidateBenchmarkReviewHandoffVisibleOk = true;
    candidateBenchmarkReviewHandoffCopyVisibleOk = true;
    candidateBenchmarkReviewIssueDraftVisibleOk = true;
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
    click('[data-action="issue-move"][data-issue-id="' + issue.id + '"][data-status="in-progress"]');
    await waitFor(() => indexes.issueById.get(issue.id).status === "in-progress", "issue did not move to in-progress");
  });

  await runStep("gantt task modal save", async () => {
    const name = marker + " task";
    await nav("pm-gantt");
    click('[data-action="task-add"]');
    fill('#taskForm [name="name"]', name);
    if (projectId) select('#taskForm [name="project"]', projectId);
    fill('#taskForm [name="start"]', "2026-06-16");
    fill('#taskForm [name="end"]', "2026-06-18");
    await confirmModal();
    assert(dashboard.gantt.tasks.some((task) => task.name === name), "task was not saved");
  });

  await runStep("team member modal save", async () => {
    const name = marker + " member";
    await nav("pm-team");
    click('[data-action="member-add"]');
    fill('#memberForm [name="name"]', name);
    fill('#memberForm [name="role"]', "QA");
    fill('#memberForm [name="load"]', "33");
    await confirmModal();
    assert(dashboard.team.some((member) => member.name === name && member.load === 33), "team member was not saved");
  });

  let instanceId = "";
  await runStep("db instance modal save", async () => {
    const name = marker + " db";
    await nav("dbm-instances");
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
    instanceId = instance.id;
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
    assert(dashboard.schemas.some((schema) => schema.id === instanceId && schema.databases.some((db) => db.name === "release" && db.tables.some((table) => table.name === tableName))), "table was not saved");
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
    assert(dashboard.queries.some((query) => query.text === text && query.avgMs === 17), "query was not saved");
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
    assert(dashboard.migrations.some((migration) => migration.title === title && migration.status === "pending"), "migration was not saved");
  });

  await runStep("settings save and theme", async () => {
    const name = marker + " user";
    await nav("settings");
    await waitFor(() => document.querySelector("[data-storage-health]"), "storage health panel did not render");
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
    assert(exported.issues.some((issue) => issue.title === marker + " issue" && issue.status === "in-progress"), "exported issue is missing");
    assert(exported.dbInstances.some((instance) => instance.name === marker + " db"), "exported DB instance is missing");
    assert(exported.queries.some((query) => query.text === "SELECT '" + marker + "' AS smoke"), "exported saved query is missing");
    backupExportOk = true;
  });

  await runStep("command palette opens created issue", async () => {
    assert(issueId, "no created issue id available");
    click('[data-action="open-palette"]');
    fill("#paletteInput", marker + " issue");
    await waitFor(() => document.querySelectorAll("#paletteResults .pal-item").length > 0, "palette produced no results");
    click("#paletteResults .pal-item");
    await waitFor(() => document.querySelector("#modal.open #issueForm"), "palette did not open issue modal");
    assert(document.querySelector('#issueForm [name="title"]').value.includes(marker), "palette opened the wrong issue");
    click('#modal [data-action="close-modal"]');
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
    candidateBenchmarkFocusVisible: candidateBenchmarkFocusVisibleOk,
    candidateBenchmarkQueueVisible: candidateBenchmarkQueueVisibleOk,
    candidateBenchmarkRubricVisible: candidateBenchmarkRubricVisibleOk,
    candidateBenchmarkRubricScoreVisible: candidateBenchmarkRubricScoreVisibleOk,
    candidateBenchmarkRecommendationExportVisible: candidateBenchmarkRecommendationExportVisibleOk,
    candidateBenchmarkReviewQueueVisible: candidateBenchmarkReviewQueueVisibleOk,
    candidateBenchmarkReviewHandoffVisible: candidateBenchmarkReviewHandoffVisibleOk,
    candidateBenchmarkReviewHandoffCopyVisible: candidateBenchmarkReviewHandoffCopyVisibleOk,
    candidateBenchmarkReviewIssueDraftVisible: candidateBenchmarkReviewIssueDraftVisibleOk,
    portfolioCandidateFilter: portfolioCandidateFilterOk,
    portfolioCandidateRanked: portfolioCandidateRankedOk,
  };
  Object.entries(persistedChecks).forEach(([key, ok]) => {
    if (!ok) failures.push("persisted check failed: " + key);
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
    assert(document.querySelector("#modal").innerText.includes("일정 1"), "import modal did not summarize imported events");
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
    const clearedArrays = ["events", "todos", "notes", "habits", "projects", "issues", "team", "dbInstances", "schemas", "queries", "migrations"];
    const uncleared = clearedArrays.filter((key) => !Array.isArray(payload[key]) || payload[key].length !== 0);
    assert(uncleared.length === 0, "reset left data in: " + uncleared.join(", "));
    assert(payload.gantt && Array.isArray(payload.gantt.tasks) && payload.gantt.tasks.length === 0, "reset left gantt tasks");
    assert(payload.imports && payload.imports.projectImports && Object.keys(payload.imports.projectImports).length === 0, "reset left imports registry");
    assert(payload.imports.autoProjectSeedDisabled === true, "reset did not disable automatic project seed imports");
    assert(payload.settings.displayName === importedMarker + " user", "reset should preserve display name");
    assert(payload.ui.theme === "dark", "reset should preserve theme");

    const emptyViews = [
      ["home", "프로젝트 포트폴리오"],
      ["pm-portfolio", "일치하는 프로젝트가 없습니다."],
      ["pm-kanban", "Kanban"],
      ["pm-gantt", "간트 차트"],
      ["pm-team", "일치하는 멤버가 없습니다."],
      ["dbm-instances", "등록된 DB 인스턴스가 없습니다."],
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
    backupImport: backupImportOk,
    backupReset: backupResetOk,
  };
  Object.entries({ backupImport: backupImportOk, backupReset: backupResetOk }).forEach(([key, ok]) => {
    if (!ok) failures.push("persisted check failed: " + key);
  });

  return {
    marker,
    status: failures.length === 0 ? "pass" : "fail",
    steps,
    failures,
    persistedChecks: finalChecks,
    final: snapshot(),
  };
})()
`;

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
    const appConsoleIssues = consoleIssues.filter((issue) => issue.text && !issue.text.includes("Autofill.enable"));
    const appNetworkIssues = networkIssues.filter((issue) => !String(issue.text || "").includes("net::ERR_ABORTED"));
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
    rmSync(tmpProfile, { recursive: true, force: true });
    progress("cleanup-end");
  }
}

main().catch((error) => {
  rmSync(tmpProfile, { recursive: true, force: true });
  console.error(error.stack || error.message);
  process.exit(1);
});
