#!/usr/bin/env node

import { spawn } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const chromePath = process.env.CHROME_PATH || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const baseUrl = (process.env.BASE_URL || "http://127.0.0.1:5178").replace(/\/+$/, "");
const tmpProfile = mkdtempSync(join(tmpdir(), "joopark-cockpit-smoke-"));
const progressEnabled = process.env.SMOKE_PROGRESS === "1";

class CdpClient {
  constructor(wsUrl) {
    this.wsUrl = wsUrl;
    this.nextId = 1;
    this.pending = new Map();
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

  handleMessage(data) {
    const message = JSON.parse(String(data));
    if (!message.id || !this.pending.has(message.id)) return;
    const { resolve, reject, timer } = this.pending.get(message.id);
    this.pending.delete(message.id);
    clearTimeout(timer);
    if (message.error) reject(new Error(message.error.message || "CDP error"));
    else resolve(message.result || {});
  }

  send(method, params = {}, timeoutMs = 10000) {
    const id = this.nextId++;
    this.ws.send(JSON.stringify({ id, method, params }));
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`Timed out waiting for ${method}`));
      }, timeoutMs);
      this.pending.set(id, { resolve, reject, timer });
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

async function waitForProcessExit(child, timeoutMs) {
  if (!child || child.exitCode !== null || child.signalCode !== null) return true;
  return await new Promise((resolve) => {
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
  for (let attempt = 0; attempt < 40; attempt += 1) {
    try {
      const response = await fetch(`http://127.0.0.1:${port}/json/list`);
      const targets = await response.json();
      const page = targets.find((target) => target.type === "page" && target.webSocketDebuggerUrl);
      if (page) return page.webSocketDebuggerUrl;
    } catch {
      // Retry until Chrome exposes the page target.
    }
    await delay(250);
  }
  throw new Error("No page target exposed by Chrome");
}

async function evaluate(client, expression, timeoutMs = 30000) {
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

const cockpitExpression = `
(async () => {
  const marker = "COCKPIT-SMOKE-" + Date.now();
  const steps = [];
  const failures = [];
  let articleContext = null;
  let issue = null;
  let siblingIssue = null;
  let event = null;

  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const assert = (condition, message) => { if (!condition) throw new Error(message); };
  const payload = () => JSON.parse(localStorage.getItem("joopark.workspace.v3") || "{}");
  const q = (selector, root = document) => root.querySelector(selector);
  const qa = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  const snapshot = () => ({
    view: typeof dashboard === "undefined" ? document.body?.dataset?.view || "" : dashboard.currentView,
    todos: typeof dashboard === "undefined" ? 0 : dashboard.todos.length,
    issues: typeof dashboard === "undefined" ? 0 : dashboard.issues.length,
    events: typeof dashboard === "undefined" ? 0 : dashboard.events.length,
    deletedItems: typeof dashboard === "undefined" || !Array.isArray(dashboard.deletedItems) ? 0 : dashboard.deletedItems.length,
    storageBytes: (localStorage.getItem("joopark.workspace.v3") || "").length,
  });
  const waitFor = async (predicate, message, timeout = 5000) => {
    const started = Date.now();
    while (Date.now() - started < timeout) {
      if (predicate()) return true;
      await sleep(50);
    }
    throw new Error(message);
  };
  const step = async (name, fn) => {
    const before = snapshot();
    try {
      const detail = await fn();
      steps.push({ name, status: "pass", detail: detail || {}, before, after: snapshot() });
    } catch (error) {
      failures.push(name + ": " + error.message);
      steps.push({ name, status: "fail", error: error.message, before, after: snapshot() });
    }
  };
  const sourceKey = (kind) => articleContext ? "llm-wiki:" + kind + ":" + articleContext.article.id : "";
  const laneIssues = (status) => dashboard.issues
    .filter((item) => item.project === issue.project && item.status === status)
    .sort((a, b) => Number(a.order || 0) - Number(b.order || 0));
  const clickLatestUndo = async (expectedText) => {
    await waitFor(() => qa("#toastRegion .toast").some((toast) => toast.textContent.includes(expectedText) && toast.textContent.includes("되돌리기")), "undo toast missing for " + expectedText);
    const actions = qa("#toastRegion [data-toast-action]");
    assert(actions.length > 0, "undo action button missing for " + expectedText);
    actions[actions.length - 1].click();
    await sleep(200);
  };

  await step("wiki document open", async () => {
    setView("llm-wiki", { history: "replace" });
    const category = llmWikiCategories().find((item) => Array.isArray(item.articles) && item.articles.length);
    assert(category, "no wiki category with articles");
    const article = category.articles[0];
    selectLlmWiki(category.id, article.id);
    await waitFor(() => dashboard.currentView === "llm-wiki" && state.llmWikiArticle === article.id && q("#view-llm-wiki").textContent.includes(article.title), "wiki article did not render");
    articleContext = { category, article };
    return { categoryId: category.id, articleId: article.id, title: article.title };
  });

  await step("todo or issue creation from wiki", async () => {
    assert(articleContext, "wiki article context missing");
    issue = createLlmWikiIssueDraft(articleContext.category.id, articleContext.article.id);
    await waitFor(() => issue && dashboard.currentView === "pm-kanban" && indexes.issueById.get(issue.id), "wiki issue was not created");
    assert(issue.sourceKey === sourceKey("issue"), "created issue source key did not point to wiki article");
    assert(q('#view-pm-kanban [data-issue-id="' + issue.id + '"]'), "created issue card did not render");
    return { issueId: issue.id, sourceKey: issue.sourceKey };
  });

  await step("kanban order change", async () => {
    assert(issue, "issue missing before kanban order step");
    siblingIssue = {
      id: marker + "-sibling",
      project: issue.project,
      title: marker + " sibling",
      status: issue.status,
      priority: "low",
      assignee: "",
      labels: ["smoke"],
      due: null,
      estimate: 1,
      order: nextKanbanLaneOrder(issue.project, issue.status),
    };
    dashboard.issues.push(siblingIssue);
    rebuildIndexes();
    commit();
    moveIssueOrder(issue.id, "bottom");
    await waitFor(() => laneIssues("todo").at(-1)?.id === issue.id, "issue was not moved to bottom of kanban lane");
    assert(q('#view-pm-kanban [data-issue-id="' + issue.id + '"][data-issue-order="' + issue.order + '"]'), "moved issue order did not render on card");
    return { issueId: issue.id, siblingId: siblingIssue.id, issueOrder: issue.order };
  });

  await step("calendar schedule", async () => {
    assert(issue, "issue missing before calendar step");
    const date = todayISO();
    event = {
      id: marker + "-event",
      title: marker + " follow-up for " + issue.id,
      date,
      allDay: true,
      start: null,
      end: null,
      category: "work",
      location: "",
      memo: "Cockpit smoke schedule for " + issue.id,
      repeat: "none",
      repeatUntil: null,
      exceptions: [],
      createdAt: nowISO(),
    };
    issue.due = date;
    dashboard.events.push(event);
    commit();
    setView("cal");
    await waitFor(() => dashboard.currentView === "cal" && q("#view-cal").textContent.includes(event.title), "scheduled event did not render in calendar");
    assert(payload().events.some((item) => item.id === event.id), "scheduled event did not persist");
    return { eventId: event.id, date };
  });

  await step("completion", async () => {
    assert(issue, "issue missing before completion step");
    moveIssue(issue.id, "done");
    await waitFor(() => indexes.issueById.get(issue.id)?.status === "done", "issue status did not become done");
    setView("pm-kanban");
    await waitFor(() => q('#view-pm-kanban [data-issue-id="' + issue.id + '"][data-issue-status="done"]'), "done issue card did not render");
    assert(payload().issues.some((item) => item.id === issue.id && item.status === "done"), "done issue status did not persist");
    return { issueId: issue.id, status: issue.status };
  });

  await step("delete and undo restore", async () => {
    assert(issue, "issue missing before delete step");
    const deletedId = issue.id;
    deleteIssue(deletedId);
    assert(!indexes.issueById.get(deletedId), "issue still indexed after delete");
    assert(!dashboard.issues.some((item) => item.id === deletedId), "issue still in dashboard after delete");
    await clickLatestUndo("이슈를 삭제했습니다");
    await waitFor(() => indexes.issueById.get(deletedId) && dashboard.issues.some((item) => item.id === deletedId), "issue was not restored by undo");
    const restored = indexes.issueById.get(deletedId);
    assert(restored.status === "done" && restored.sourceKey === sourceKey("issue"), "restored issue lost done status or wiki source");
    assert(payload().issues.some((item) => item.id === deletedId && item.status === "done"), "restored issue did not persist");
    return { issueId: deletedId, restored: true };
  });

  return {
    status: failures.length ? "fail" : "pass",
    marker,
    baseView: dashboard.currentView,
    stepCount: steps.length,
    requiredSteps: ["wiki document open", "todo or issue creation from wiki", "kanban order change", "calendar schedule", "completion", "delete and undo restore"],
    steps,
    failures,
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

  let pageClient;
  try {
    const browserWs = await waitForDevTools(chrome);
    const pageWs = await pageWebSocketUrl(browserWs);
    pageClient = new CdpClient(pageWs);
    await pageClient.open();
    await pageClient.send("Runtime.enable");
    await pageClient.send("Page.enable");
    await pageClient.send("Page.navigate", { url: `${baseUrl}/index.html#llm-wiki` });
    await evaluate(pageClient, `
      new Promise((resolve, reject) => {
        const started = Date.now();
        const check = () => {
          const ready = document.readyState === "complete" &&
            document.body &&
            document.body.dataset.view === "llm-wiki" &&
            typeof dashboard !== "undefined" &&
            typeof createLlmWikiIssueDraft === "function";
          if (ready) resolve(true);
          else if (Date.now() - started > 12000) reject(new Error("llm-wiki route not ready"));
          else setTimeout(check, 100);
        };
        check();
      })
    `);
    progress("app-ready");

    const result = await evaluate(pageClient, cockpitExpression, 70000);
    result.baseUrl = baseUrl;
    console.log(JSON.stringify(result, null, 2));
    if (result.status !== "pass") process.exitCode = 1;
  } finally {
    if (pageClient) pageClient.close();
    await terminateProcess(chrome);
    rmSync(tmpProfile, { recursive: true, force: true });
  }
}

main().catch((error) => {
  rmSync(tmpProfile, { recursive: true, force: true });
  console.error(error.stack || error.message);
  process.exit(1);
});
