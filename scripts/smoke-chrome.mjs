#!/usr/bin/env node

import { spawn } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const chromePath = process.env.CHROME_PATH || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const baseUrl = (process.env.BASE_URL || "http://127.0.0.1:5178").replace(/\/+$/, "");
const tmpProfile = mkdtempSync(join(tmpdir(), "joopark-chrome-smoke-"));
const progressEnabled = process.env.SMOKE_PROGRESS === "1";
const defaultCdpTimeoutMs = 10000;
const defaultEvaluateTimeoutMs = Number(process.env.SMOKE_RUNTIME_TIMEOUT_MS || 90000);
const routeReadyTimeoutMs = Number(process.env.SMOKE_ROUTE_READY_TIMEOUT_MS || 12000);

const routes = [
  ["home", ["오늘 일정", "공개 준비 요약", "데이터 소유권", "팀 · 시스템 관리"]],
  ["cal", ["이번 달 일정", "일정 추가"]],
  ["todo", ["미완료", "새 할 일"]],
  ["notes", ["개의 메모", "+ 메모"]],
  ["habits", ["활성 습관", "습관"]],
  ["stats", ["이번 주 완료", "전체 완료율"]],
  ["llm-wiki", ["LLM 위키", "기초 개념", "개 문서"]],
  ["pm-portfolio", ["프로젝트", "평균 진행률"]],
  ["pm-kanban", ["Kanban", "To Do"]],
  ["pm-gantt", ["간트 차트", "작업"]],
  ["pm-team", ["팀 멤버", "프로젝트 매트릭스"]],
  ["dbm-instances", ["인스턴스", "평균 CPU", "로컬 DB 카탈로그"]],
  ["dbm-schema", ["스키마", "인덱스 / 관계", "로컬 DB 카탈로그"]],
  ["dbm-queries", ["저장 쿼리", "실행 시간 분포", "로컬 DB 카탈로그"]],
  ["dbm-backups", ["백업 캘린더", "마이그레이션 이력", "로컬 DB 카탈로그"]],
  ["settings", ["프로필", "데이터 백업"]],
  ["system", ["시스템 상태", "저장소", "운영 표면"]],
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
    const payload = JSON.stringify({ id, method, params });
    this.ws.send(payload);
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
  console.error(JSON.stringify({
    event,
    ...extra,
  }));
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
    throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text || "Runtime evaluation failed");
  }
  return result.result ? result.result.value : undefined;
}

function routeReadyTimeoutFor(route) {
  if (route === "system") return Math.max(routeReadyTimeoutMs, 20000);
  if (route === "settings") return Math.max(routeReadyTimeoutMs, 16000);
  return routeReadyTimeoutMs;
}

async function waitForAppRoute(client, route) {
  const timeoutMs = routeReadyTimeoutFor(route);
  const expression = `
    new Promise((resolve, reject) => {
      const route = ${JSON.stringify(route)};
      const started = Date.now();
      const routeReadyDiagnostics = () => {
        const view = document.getElementById("view-" + route);
        return {
          route,
          readyState: document.readyState,
          hash: location.hash,
          bodyView: document.body?.dataset?.view || "",
          viewExists: Boolean(view),
          viewHidden: view ? view.hidden : null,
          viewTextLength: view ? view.innerText.trim().length : 0,
          visibleViews: Array.from(document.querySelectorAll(".view"))
            .filter((node) => node.hidden === false)
            .map((node) => node.id),
          elapsedMs: Date.now() - started
        };
      };
      const check = () => {
        const state = routeReadyDiagnostics();
        const isReady = document.readyState === "complete" &&
          document.body &&
          document.body.dataset.view === route &&
          state.viewExists &&
          state.viewHidden === false &&
          state.viewTextLength > 0;
        if (isReady) resolve(state);
        else if (Date.now() - started > ${timeoutMs}) reject(new Error("route not ready: " + JSON.stringify(state)));
        else setTimeout(check, 100);
      };
      check();
    })
  `;
  const routeState = await evaluate(client, expression);
  progress("route-ready", {
    route,
    elapsedMs: routeState?.elapsedMs,
    timeoutMs,
  });
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
    `--remote-debugging-port=0`,
    `--user-data-dir=${tmpProfile}`,
    "about:blank",
  ], { stdio: ["ignore", "ignore", "pipe"] });

  const failures = [];
  const routeReports = [];
  const layoutIssues = [];
  const consoleIssues = [];
  const networkIssues = [];
  let serviceWorkerReport = null;
  let currentRoute = "boot";
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
    progress("cdp-domains-enabled");

    for (const [routeIndex, [route, expectedTexts]] of routes.entries()) {
      currentRoute = route;
      const url = `${baseUrl}/index.html?smoke-route=${routeIndex}#${route}`;
      progress("route-start", { route, url });
      await pageClient.send("Page.navigate", { url });
      await waitForAppRoute(pageClient, route);

      const report = await evaluate(pageClient, `(() => {
        const route = "${route}";
        const view = document.getElementById("view-" + route);
        const shell = document.querySelector(".shell");
        const main = document.querySelector(".main");
        const text = document.body.innerText || "";
        const formText = Array.from(document.querySelectorAll("input, textarea, select"))
          .map((node) => [node.placeholder, node.getAttribute("aria-label"), node.value].filter(Boolean).join(" "))
          .join("\\n");
        const searchableText = text + "\\n" + formText;
        const rect = (node) => {
          if (!node) return null;
          const r = node.getBoundingClientRect();
          return { left: r.left, right: r.right, width: r.width, height: r.height };
        };
        const docScrollWidth = Math.max(document.documentElement.scrollWidth, document.body.scrollWidth);
        const visibleViews = Array.from(document.querySelectorAll(".view"))
          .filter((node) => node.hidden === false)
          .map((node) => node.id);
        const readiness = document.querySelector("[data-home-readiness]");
        const readinessCards = Array.from(document.querySelectorAll("[data-home-readiness-card]")).map((node) => ({
          key: node.dataset.homeReadinessCard || "",
          tone: node.dataset.readinessTone || "",
          text: node.innerText || "",
        }));
        const pwaRuntime = document.querySelector("[data-system-pwa-runtime]");
        return {
          route,
          title: document.title,
          bodyView: document.body.dataset.view || "",
          innerWidth,
          innerHeight,
          docScrollWidth,
          overflowX: docScrollWidth > innerWidth + 1,
          shell: rect(shell),
          main: rect(main),
          visibleViews,
          textLength: text.trim().length,
          projectCount: Number(document.getElementById("navCountProjects")?.textContent || 0),
          issueCount: Number(document.getElementById("navCountIssues")?.textContent || 0),
          tableCount: Number(document.getElementById("navCountTables")?.textContent || 0),
          homeReadiness: route === "home" ? {
            present: Boolean(readiness),
            cardCount: readinessCards.length,
            keys: readinessCards.map((card) => card.key),
            tones: readinessCards.map((card) => card.tone),
            publishBlockers: readiness ? readiness.dataset.homePublishBlockers || "" : "",
            launchProofReady: readiness ? readiness.dataset.homeLaunchProofReady || "" : "",
            benchmarkCount: readiness ? readiness.dataset.homeBenchmarkCount || "" : "",
            sourceBackedCount: readiness ? readiness.dataset.homeSourceBackedCount || "" : "",
          } : null,
          pwaRuntime: route === "system" ? {
            present: Boolean(pwaRuntime),
            status: pwaRuntime ? pwaRuntime.dataset.pwaRuntimeStatus || "" : "",
            serviceWorkerActive: pwaRuntime ? pwaRuntime.dataset.pwaRuntimeServiceWorkerActive || "" : "",
            cacheReady: pwaRuntime ? pwaRuntime.dataset.pwaRuntimeCacheReady || "" : "",
            manifestLinked: pwaRuntime ? pwaRuntime.dataset.pwaRuntimeManifestLinked || "" : "",
            cachedAssetCount: pwaRuntime ? pwaRuntime.dataset.pwaRuntimeCachedAssetCount || "" : "",
          } : null,
          expected: ${JSON.stringify(expectedTexts)},
          missingText: ${JSON.stringify(expectedTexts)}.filter((needle) => !searchableText.includes(needle)),
        };
      })()`);

      if (report.bodyView !== route) failures.push(`${route}: body view is ${report.bodyView || "(empty)"}`);
      if (!report.visibleViews.includes(`view-${route}`)) failures.push(`${route}: visible view missing view-${route}`);
      if (report.textLength < 80) failures.push(`${route}: rendered text too short (${report.textLength})`);
      if (report.missingText.length > 0) failures.push(`${route}: missing text ${report.missingText.join(", ")}`);
      if (route === "home") {
        const readiness = report.homeReadiness || {};
        const readinessKeys = Array.isArray(readiness.keys) ? readiness.keys : [];
        const requiredKeys = ["data-ownership", "release-gate", "publish-proof", "benchmark-queue"];
        if (!readiness.present) failures.push("home readiness summary did not render");
        if (readiness.cardCount !== requiredKeys.length) failures.push(`home readiness card count was ${readiness.cardCount}`);
        for (const key of requiredKeys) {
          if (!readinessKeys.includes(key)) failures.push(`home readiness card missing ${key}`);
        }
        if (!/^\d+$/.test(readiness.publishBlockers || "")) failures.push("home readiness publish blocker count missing");
        if (!/^\d+$/.test(readiness.benchmarkCount || "")) failures.push("home readiness benchmark count missing");
        if (!/^\d+$/.test(readiness.sourceBackedCount || "")) failures.push("home readiness source-backed count missing");
        serviceWorkerReport = await evaluate(pageClient, `(() => {
          if (!("serviceWorker" in navigator)) return Promise.resolve({ supported: false, active: false, scriptURL: "", scope: "" });
          const timeout = new Promise((resolve) => setTimeout(() => resolve({ supported: true, active: false, scriptURL: "", scope: "", timedOut: true }), 6000));
          const ready = navigator.serviceWorker.ready.then((registration) => ({
            supported: true,
            active: Boolean(registration.active),
            scriptURL: registration.active ? registration.active.scriptURL : "",
            scope: registration.scope || "",
            timedOut: false,
          }));
          return Promise.race([ready, timeout]);
        })()`, 10000);
        if (!serviceWorkerReport.supported) failures.push("service worker API was not available");
        if (!serviceWorkerReport.active) failures.push("service worker did not become active");
        if (!String(serviceWorkerReport.scriptURL || "").endsWith("/sw.js")) failures.push(`service worker script was ${serviceWorkerReport.scriptURL || "(empty)"}`);
      }
      if (route === "system") {
        const pwaRuntime = report.pwaRuntime || {};
        if (!pwaRuntime.present) failures.push("system PWA runtime panel did not render");
        if (pwaRuntime.serviceWorkerActive !== "true") failures.push("system PWA runtime did not report active service worker");
        if (pwaRuntime.cacheReady !== "true") failures.push("system PWA runtime did not report app shell cache");
        if (pwaRuntime.manifestLinked !== "true") failures.push("system PWA runtime did not report manifest link");
        if (!/^\d+$/.test(pwaRuntime.cachedAssetCount || "") || Number(pwaRuntime.cachedAssetCount) < 1) failures.push("system PWA runtime cached asset count missing");
      }
      if (report.overflowX) layoutIssues.push(`${route}: horizontal overflow ${report.docScrollWidth}px > ${report.innerWidth}px`);
      if (report.shell?.width > report.innerWidth + 1) layoutIssues.push(`${route}: shell width ${Math.round(report.shell.width)}px > viewport ${report.innerWidth}px`);
      if (report.main?.right > report.innerWidth + 1) layoutIssues.push(`${route}: main right edge ${Math.round(report.main.right)}px > viewport ${report.innerWidth}px`);
      routeReports.push(report);
      progress("route-end", {
        route,
        textLength: report.textLength,
        missingText: report.missingText,
        docScrollWidth: report.docScrollWidth,
        overflowX: report.overflowX,
      });
    }
  } finally {
    progress("cleanup-start", { currentRoute });
    if (pageClient) pageClient.close();
    await terminateProcess(chrome);
    rmSync(tmpProfile, { recursive: true, force: true });
    progress("cleanup-end", { currentRoute });
  }

  const appConsoleIssues = consoleIssues.filter((issue) => issue.text && !issue.text.includes("Autofill.enable"));
  const appNetworkIssues = networkIssues.filter((issue) => {
    if (String(issue.text || "").includes("net::ERR_ABORTED")) return false;
    try {
      const url = new URL(issue.url || "");
      if (url.pathname.endsWith("/release-provenance.json")) return false;
    } catch (_) {}
    return true;
  });
  if (appConsoleIssues.length > 0) failures.push(`console issues: ${appConsoleIssues.length}`);
  if (appNetworkIssues.length > 0) failures.push(`network issues: ${appNetworkIssues.length}`);
  if (layoutIssues.length > 0) failures.push(`desktop layout issues: ${layoutIssues.length}`);

  const summary = {
    baseUrl,
    viewport: routeReports[0] ? {
      width: routeReports[0].innerWidth,
      height: routeReports[0].innerHeight,
    } : null,
    routeCount: routeReports.length,
    routes: routeReports.map((r) => ({
      route: r.route,
      bodyView: r.bodyView,
      visibleViews: r.visibleViews,
      textLength: r.textLength,
      innerWidth: r.innerWidth,
      docScrollWidth: r.docScrollWidth,
      overflowX: r.overflowX,
      projectCount: r.projectCount,
      issueCount: r.issueCount,
      tableCount: r.tableCount,
      homeReadiness: r.homeReadiness,
      missingText: r.missingText,
    })),
    layoutIssues,
    serviceWorker: serviceWorkerReport,
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
