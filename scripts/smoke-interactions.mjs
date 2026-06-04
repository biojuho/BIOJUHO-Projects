#!/usr/bin/env node

import { spawn } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const chromePath = process.env.CHROME_PATH || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const baseUrl = (process.env.BASE_URL || "http://127.0.0.1:5178").replace(/\/+$/, "");
const tmpProfile = mkdtempSync(join(tmpdir(), "joopark-interaction-smoke-"));
const progressEnabled = process.env.SMOKE_PROGRESS === "1";

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
      const { resolve, reject } = this.pending.get(message.id);
      this.pending.delete(message.id);
      if (message.error) reject(new Error(`${message.error.message || "CDP error"} (${message.error.code || "no-code"})`));
      else resolve(message.result || {});
      return;
    }
    const callbacks = this.listeners.get(message.method) || [];
    callbacks.forEach((callback) => callback(message.params || {}));
  }

  send(method, params = {}) {
    const id = this.nextId++;
    this.ws.send(JSON.stringify({ id, method, params }));
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      setTimeout(() => {
        if (!this.pending.has(id)) return;
        this.pending.delete(id);
        reject(new Error(`Timed out waiting for ${method}`));
      }, 10000);
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

async function evaluate(client, expression) {
  const result = await client.send("Runtime.evaluate", {
    expression,
    awaitPromise: true,
    returnByValue: true,
  });
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

const interactionExpression = `
(async () => {
  const marker = "ARSMOKE-" + Date.now();
  const storeKey = "joopark.workspace.v3";
  const steps = [];
  const failures = [];
  let backupExportOk = false;
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
    fill('#noteForm [name="body"]', "**release** checklist");
    check('#noteForm [name="pinned"]', true);
    await confirmModal();
    const note = dashboard.notes.find((item) => item.title === title);
    assert(note && note.pinned, "note was not saved pinned");
    assert(savedPayload().notes.some((item) => item.title === title && item.pinned), "note was not persisted");
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

  const finalPayload = savedPayload();
  const persistedChecks = {
    event: finalPayload.events.some((event) => event.title === marker + " event"),
    todo: finalPayload.todos.some((todo) => todo.title === marker + " todo" && todo.done),
    note: finalPayload.notes.some((note) => note.title === marker + " note" && note.pinned),
    project: finalPayload.projects.some((project) => project.name === marker + " project"),
    issue: finalPayload.issues.some((issue) => issue.title === marker + " issue" && issue.status === "in-progress"),
    dbInstance: finalPayload.dbInstances.some((instance) => instance.name === marker + " db"),
    settings: finalPayload.settings.displayName === marker + " user",
    backupExport: backupExportOk,
  };
  Object.entries(persistedChecks).forEach(([key, ok]) => {
    if (!ok) failures.push("persisted check failed: " + key);
  });

  return {
    marker,
    status: failures.length === 0 ? "pass" : "fail",
    steps,
    failures,
    persistedChecks,
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

    const interactionResult = await evaluate(pageClient, interactionExpression);
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
