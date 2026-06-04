#!/usr/bin/env node

import { spawn } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const chromePath = process.env.CHROME_PATH || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const baseUrl = (process.env.BASE_URL || "http://127.0.0.1:5178").replace(/\/+$/, "");
const tmpProfile = mkdtempSync(join(tmpdir(), "joopark-chrome-smoke-"));

const routes = [
  ["home", ["좋은 오후입니다", "팀 · 시스템 관리"]],
  ["cal", ["이번 달 일정", "일정 추가"]],
  ["todo", ["미완료", "새 할 일"]],
  ["notes", ["개의 메모", "+ 메모"]],
  ["habits", ["활성 습관", "습관"]],
  ["stats", ["이번 주 완료", "전체 완료율"]],
  ["pm-portfolio", ["프로젝트", "평균 진행률"]],
  ["pm-kanban", ["Kanban", "To Do"]],
  ["pm-gantt", ["간트 차트", "작업"]],
  ["pm-team", ["팀 멤버", "프로젝트 매트릭스"]],
  ["dbm-instances", ["인스턴스", "평균 CPU"]],
  ["dbm-schema", ["스키마", "인덱스 / 관계"]],
  ["dbm-queries", ["저장 쿼리", "실행 시간 분포"]],
  ["dbm-backups", ["백업 캘린더", "마이그레이션 이력"]],
  ["settings", ["프로필", "데이터 백업"]],
];

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
    const payload = JSON.stringify({ id, method, params });
    this.ws.send(payload);
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
    throw new Error(result.exceptionDetails.text || "Runtime evaluation failed");
  }
  return result.result ? result.result.value : undefined;
}

async function waitForAppRoute(client, route) {
  const expression = `
    new Promise((resolve, reject) => {
      const started = Date.now();
      const check = () => {
        const view = document.getElementById("view-${route}");
        const isReady = document.readyState === "complete" &&
          document.body &&
          document.body.dataset.view === "${route}" &&
          view &&
          view.hidden === false &&
          view.innerText.trim().length > 0;
        if (isReady) resolve(true);
        else if (Date.now() - started > 6000) reject(new Error("route not ready"));
        else setTimeout(check, 100);
      };
      check();
    })
  `;
  await evaluate(client, expression);
  await delay(650);
}

function formatArg(arg) {
  if (!arg) return "";
  if (typeof arg.value !== "undefined") return String(arg.value);
  if (arg.description) return arg.description;
  if (arg.type) return `[${arg.type}]`;
  return "";
}

async function main() {
  try {
    const response = await fetch(baseUrl, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
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
    `--remote-debugging-port=0`,
    `--user-data-dir=${tmpProfile}`,
    "about:blank",
  ], { stdio: ["ignore", "ignore", "pipe"] });

  const failures = [];
  const routeReports = [];
  const consoleIssues = [];
  const networkIssues = [];
  let currentRoute = "boot";
  let pageClient;

  try {
    const browserWs = await waitForDevTools(chrome);
    const pageWs = await pageWebSocketUrl(browserWs);
    pageClient = new CdpClient(pageWs);
    await pageClient.open();

    pageClient.on("Runtime.consoleAPICalled", (params) => {
      if (!["error", "warning", "assert"].includes(params.type)) return;
      consoleIssues.push({
        route: currentRoute,
        type: params.type,
        text: (params.args || []).map(formatArg).filter(Boolean).join(" "),
      });
    });
    pageClient.on("Runtime.exceptionThrown", (params) => {
      consoleIssues.push({
        route: currentRoute,
        type: "exception",
        text: params.exceptionDetails?.exception?.description || params.exceptionDetails?.text || "uncaught exception",
      });
    });
    pageClient.on("Network.loadingFailed", (params) => {
      if (params.blockedReason === "inspector") return;
      networkIssues.push({
        route: currentRoute,
        requestId: params.requestId,
        text: params.errorText || "network loading failed",
      });
    });
    pageClient.on("Network.responseReceived", (params) => {
      const response = params.response || {};
      if (response.url && response.url.startsWith(baseUrl) && response.status >= 400) {
        networkIssues.push({
          route: currentRoute,
          url: response.url,
          status: response.status,
        });
      }
    });

    await pageClient.send("Runtime.enable");
    await pageClient.send("Page.enable");
    await pageClient.send("Network.enable");

    for (const [route, expectedTexts] of routes) {
      currentRoute = route;
      const url = `${baseUrl}/index.html#${route}`;
      await pageClient.send("Page.navigate", { url });
      await waitForAppRoute(pageClient, route);

      const report = await evaluate(pageClient, `(() => {
        const route = "${route}";
        const view = document.getElementById("view-" + route);
        const text = document.body.innerText || "";
        const formText = Array.from(document.querySelectorAll("input, textarea, select"))
          .map((node) => [node.placeholder, node.getAttribute("aria-label"), node.value].filter(Boolean).join(" "))
          .join("\\n");
        const searchableText = text + "\\n" + formText;
        const visibleViews = Array.from(document.querySelectorAll(".view"))
          .filter((node) => node.hidden === false)
          .map((node) => node.id);
        return {
          route,
          title: document.title,
          bodyView: document.body.dataset.view || "",
          visibleViews,
          textLength: text.trim().length,
          projectCount: Number(document.getElementById("navCountProjects")?.textContent || 0),
          issueCount: Number(document.getElementById("navCountIssues")?.textContent || 0),
          tableCount: Number(document.getElementById("navCountTables")?.textContent || 0),
          expected: ${JSON.stringify(expectedTexts)},
          missingText: ${JSON.stringify(expectedTexts)}.filter((needle) => !searchableText.includes(needle)),
        };
      })()`);

      if (report.bodyView !== route) failures.push(`${route}: body view is ${report.bodyView || "(empty)"}`);
      if (!report.visibleViews.includes(`view-${route}`)) failures.push(`${route}: visible view missing view-${route}`);
      if (report.textLength < 80) failures.push(`${route}: rendered text too short (${report.textLength})`);
      if (report.missingText.length > 0) failures.push(`${route}: missing text ${report.missingText.join(", ")}`);
      routeReports.push(report);
    }
  } finally {
    if (pageClient) pageClient.close();
    chrome.kill("SIGTERM");
    await delay(250);
    rmSync(tmpProfile, { recursive: true, force: true });
  }

  const appConsoleIssues = consoleIssues.filter((issue) => issue.text && !issue.text.includes("Autofill.enable"));
  const appNetworkIssues = networkIssues.filter((issue) => !String(issue.text || "").includes("net::ERR_ABORTED"));
  if (appConsoleIssues.length > 0) failures.push(`console issues: ${appConsoleIssues.length}`);
  if (appNetworkIssues.length > 0) failures.push(`network issues: ${appNetworkIssues.length}`);

  const summary = {
    baseUrl,
    routeCount: routeReports.length,
    routes: routeReports.map((r) => ({
      route: r.route,
      bodyView: r.bodyView,
      visibleViews: r.visibleViews,
      textLength: r.textLength,
      projectCount: r.projectCount,
      issueCount: r.issueCount,
      tableCount: r.tableCount,
      missingText: r.missingText,
    })),
    consoleIssues: appConsoleIssues,
    networkIssues: appNetworkIssues,
    status: failures.length === 0 ? "pass" : "fail",
    failures,
  };

  console.log(JSON.stringify(summary, null, 2));
  if (failures.length > 0) process.exit(1);
}

main().catch((error) => {
  rmSync(tmpProfile, { recursive: true, force: true });
  console.error(error.stack || error.message);
  process.exit(1);
});
