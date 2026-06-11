#!/usr/bin/env node

import { spawn } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const chromePath = process.env.CHROME_PATH || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const baseUrl = (process.env.BASE_URL || "http://127.0.0.1:5178").replace(/\/+$/, "");
const viewportWidth = positiveIntegerOption(process.env.MOBILE_SMOKE_WIDTH, 500);
const viewportHeight = positiveIntegerOption(process.env.MOBILE_SMOKE_HEIGHT, 757);
const tmpProfile = mkdtempSync(join(tmpdir(), "joopark-mobile-smoke-"));
const progressEnabled = process.env.SMOKE_PROGRESS === "1";
const defaultCdpTimeoutMs = 10000;
const defaultEvaluateTimeoutMs = positiveMsOption(process.env.SMOKE_RUNTIME_TIMEOUT_MS, 60000);
const routeReadyTimeoutMs = positiveMsOption(process.env.MOBILE_SMOKE_ROUTE_READY_TIMEOUT_MS || process.env.SMOKE_ROUTE_READY_TIMEOUT_MS, 9000);

function positiveIntegerOption(value, fallback) {
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed <= 0) return fallback;
  return parsed;
}

function positiveMsOption(value, fallback) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) return fallback;
  return parsed;
}

const routes = [
  ["home", ["오늘 일정", "팀 · 시스템 관리"]],
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
const searchInertRouteList = ["home", "stats", "settings", "system"];
const searchInertRoutes = new Set(searchInertRouteList);
const searchEmptyRoutes = routes
  .map(([route]) => route)
  .filter((route) => !searchInertRoutes.has(route));

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
    return () => {
      const current = this.listeners.get(method) || [];
      this.listeners.set(method, current.filter((item) => item !== callback));
    };
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
    throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text || "Runtime evaluation failed");
  }
  return result.result ? result.result.value : undefined;
}

async function waitForDocumentComplete(client, url, timeoutMs = 30000) {
  const started = Date.now();
  let lastState = null;
  while (Date.now() - started <= timeoutMs) {
    try {
      lastState = await evaluate(client, `(() => ({
        href: location.href,
        readyState: document.readyState
      }))()`, 3000);
      if (lastState?.href === url && lastState.readyState !== "loading") return lastState;
    } catch (error) {
      lastState = { error: error.message };
    }
    await delay(100);
  }
  throw new Error(`Timed out waiting for document complete after navigating to ${url}: ${JSON.stringify(lastState)}`);
}

async function navigateAndWaitForLoad(client, url) {
  const result = await client.send("Page.navigate", { url });
  if (result.errorText) throw new Error(`Navigation failed for ${url}: ${result.errorText}`);
  await waitForDocumentComplete(client, url);
  progress("mobile-page-loaded", { url });
}

function routeReadyTimeoutFor(route) {
  if (route === "system") return Math.max(routeReadyTimeoutMs, 20000);
  if (route === "settings") return Math.max(routeReadyTimeoutMs, 16000);
  return routeReadyTimeoutMs;
}

async function waitForAppRoute(client, route) {
  const timeoutMs = routeReadyTimeoutFor(route);
  const routeState = await evaluate(client, `
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
        const ready = document.readyState !== "loading" &&
          document.body?.dataset.view === route &&
          state.viewExists &&
          state.viewHidden === false &&
          state.viewTextLength > 0;
        if (ready) resolve(state);
        else if (Date.now() - started > ${timeoutMs}) reject(new Error("route not ready: " + JSON.stringify(state)));
        else setTimeout(check, 100);
      };
      check();
    })
  `);
  progress("mobile-route-ready", {
    route,
    elapsedMs: routeState?.elapsedMs,
    timeoutMs,
  });
  await delay(350);
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
    `--window-size=${viewportWidth},${viewportHeight}`,
    "--force-device-scale-factor=1",
    "--remote-debugging-port=0",
    `--user-data-dir=${tmpProfile}`,
    "about:blank",
  ], { stdio: ["ignore", "ignore", "pipe"] });

  const failures = [];
  const layoutIssues = [];
  const routeReports = [];
  let sheetActionReport = null;
  let modalTouchReport = null;
  let paletteMobileReport = null;
  let projectPickerMobileReport = null;
  let notificationSheetMobileReport = null;
  let searchEmptyMobileReport = null;
  const consoleIssues = [];
  const networkIssues = [];
  let currentRoute = "boot";
  let pageClient;

  try {
    const browserWs = await waitForDevTools(chrome);
    const pageWs = await pageWebSocketUrl(browserWs);
    pageClient = new CdpClient(pageWs);
    await pageClient.open();
    await pageClient.send("Runtime.enable");
    await pageClient.send("Page.enable");
    await pageClient.send("Network.enable");
    await pageClient.send("Emulation.setDeviceMetricsOverride", {
      width: viewportWidth,
      height: viewportHeight,
      deviceScaleFactor: 1,
      mobile: true,
    });

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

    for (const [routeIndex, [route, expectedTexts]] of routes.entries()) {
      currentRoute = route;
      const url = `${baseUrl}/index.html?smoke-route=${routeIndex}#${route}`;
      progress("mobile-route-start", { route, url });
      await navigateAndWaitForLoad(pageClient, url);
      await waitForAppRoute(pageClient, route);
      if (route === "habits") {
        await evaluate(pageClient, `
          new Promise((resolve, reject) => {
            const started = Date.now();
            const waitFor = (check, label) => {
              const tick = () => {
                try {
                  if (check()) return resolve(true);
                } catch (error) {
                  return reject(error);
                }
                if (Date.now() - started > 6000) return reject(new Error(label));
                setTimeout(tick, 100);
              };
              tick();
            };
            if (document.querySelector(".habit-card .icon-btn")) {
              resolve(true);
              return;
            }
            document.querySelector('[data-action="habit-add"]')?.click();
            const fillWhenReady = () => {
              const form = document.querySelector("#modal.open #habitForm");
              if (!form) {
                if (Date.now() - started > 6000) return reject(new Error("habit touch target setup modal did not open"));
                setTimeout(fillWhenReady, 100);
                return;
              }
              const nameInput = form.querySelector('input[name="name"]');
              if (nameInput) {
                nameInput.value = "모바일 터치 점검 습관";
                nameInput.dispatchEvent(new Event("input", { bubbles: true }));
              }
              document.querySelector('[data-action="modal-confirm"]')?.click();
              waitFor(() => Boolean(document.querySelector(".habit-card .icon-btn")), "habit touch target setup card did not render");
            };
            fillWhenReady();
          })
        `);
        await waitForAppRoute(pageClient, route);
      }

      const report = await evaluate(pageClient, `(() => {
        const route = "${route}";
        const view = document.getElementById("view-" + route);
        const shell = document.querySelector(".shell");
        const main = document.querySelector(".main");
        const sidebar = document.querySelector(".sidebar");
        const topbar = document.querySelector(".topbar");
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
        const textControlSelectors = [
          ".view .primary-btn",
          ".view .danger-btn",
          ".view .secondary-btn",
          ".view .seg-chip",
          ".view .file-btn",
          ".view .portfolio-export-download",
          ".view .sched-today-btn",
          ".view .sched-agenda-add",
          ".view .kanban-chip-clear",
          ".view .kanban-global-add",
          ".view .notif-permission-btn",
        ].join(",");
        const isVisible = (node) => {
          const style = getComputedStyle(node);
          const bounds = node.getBoundingClientRect();
          return style.display !== "none" && style.visibility !== "hidden" && bounds.width > 0 && bounds.height > 0;
        };
        const textControls = Array.from(document.querySelectorAll(textControlSelectors))
          .filter((node) => isVisible(node) && (node.textContent || "").trim().length > 0)
          .map((node) => {
            const bounds = node.getBoundingClientRect();
            const text = (node.textContent || "").replace(/\\s+/g, " ").trim();
            return {
              text,
              selector: node.className || node.tagName.toLowerCase(),
              left: Math.round(bounds.left),
              right: Math.round(bounds.right),
              width: Math.round(bounds.width),
              height: Math.round(bounds.height),
              clientWidth: node.clientWidth,
              scrollWidth: node.scrollWidth,
              clientHeight: node.clientHeight,
              scrollHeight: node.scrollHeight,
              overflowX: node.scrollWidth > node.clientWidth + 1,
              overflowY: node.scrollHeight > node.clientHeight + 1,
              tooShort: bounds.height < 30,
              outsideViewport: bounds.left < -1 || bounds.right > innerWidth + 1,
            };
          });
        const textControlIssues = textControls.flatMap((control) => {
          const issues = [];
          if (control.overflowX) issues.push("text_control_button_overflow " + control.text);
          if (control.overflowY) issues.push("text_control_button_vertical_overflow " + control.text);
          if (control.tooShort) issues.push("text_control_button_too_short " + control.text);
          if (control.outsideViewport) issues.push("text_control_button_outside_viewport " + control.text);
          return issues;
        });
        const touchActionSelectors = [
          ".pm-card-actions",
          ".kanban-move-btns",
          ".gantt-row-actions",
          ".team-row-actions",
          ".db-card-actions",
          ".schema-table-actions",
          ".mig-row-actions",
        ].join(",");
        const touchActionGroups = Array.from(document.querySelectorAll(touchActionSelectors))
          .filter((node) => isVisible(node) && node.querySelector("button"))
          .map((node) => {
            const bounds = node.getBoundingClientRect();
            const opacity = Number.parseFloat(getComputedStyle(node).opacity || "1");
            return {
              selector: node.className || node.tagName.toLowerCase(),
              left: Math.round(bounds.left),
              right: Math.round(bounds.right),
              width: Math.round(bounds.width),
              height: Math.round(bounds.height),
              opacity,
              hidden: opacity < 0.99,
            };
          });
        const touchActionIssues = touchActionGroups
          .filter((group) => group.hidden)
          .map((group) => "touch_action_group_hidden " + group.selector);
        const iconTouchSelectors = [
          ".pm-icon-btn",
          ".kanban-add-btn",
          ".kanban-move-btn",
          ".view .todo-check-mini",
          ".view .todo-check",
          ".view .todo-del",
          ".view .note-pin",
          ".view .note-del",
          ".view .icon-btn",
          ".view .habit-day:not(:disabled)",
        ].join(",");
        const iconTouchTargets = Array.from(document.querySelectorAll(iconTouchSelectors))
          .filter((node) => isVisible(node))
          .map((node) => {
            const bounds = node.getBoundingClientRect();
            return {
              selector: node.className || node.tagName.toLowerCase(),
              label: node.getAttribute("aria-label") || node.getAttribute("title") || (node.textContent || "").trim(),
              width: Math.round(bounds.width),
              height: Math.round(bounds.height),
              tooSmall: bounds.width < 31 || bounds.height < 31,
            };
          });
        const iconTouchIssues = iconTouchTargets
          .filter((target) => target.tooSmall)
          .map((target) => "icon_touch_target_too_small " + target.selector + " " + target.width + "x" + target.height + " " + target.label);
        if (route === "habits" && !iconTouchTargets.some((target) => String(target.selector).includes("icon-btn"))) {
          iconTouchIssues.push("habit_icon_touch_targets_missing");
        }
        if (route === "habits" && !iconTouchTargets.some((target) => String(target.selector).includes("habit-day"))) {
          iconTouchIssues.push("habit_day_touch_targets_missing");
        }
        const searchClearIssues = [];
        const searchInertRoutes = new Set(${JSON.stringify(searchInertRouteList)});
        const searchShell = document.querySelector(".search");
        const searchInput = document.getElementById("globalSearch");
        const searchClear = document.getElementById("globalSearchClear");
        if (!searchInertRoutes.has(route)) {
          if (!searchShell || !searchInput || !searchClear) {
            searchClearIssues.push("topbar_search_clear_missing");
          } else {
            searchInput.focus();
            searchInput.value = "mobile-search-check";
            searchInput.dispatchEvent(new Event("input", { bubbles: true }));
            const shellBounds = searchShell.getBoundingClientRect();
            const clearBounds = searchClear.getBoundingClientRect();
            const inputBounds = searchInput.getBoundingClientRect();
            if (searchClear.hidden) searchClearIssues.push("topbar_search_clear_hidden_after_query");
            if (clearBounds.width < 31 || clearBounds.height < 31) searchClearIssues.push("topbar_search_clear_too_small " + Math.round(clearBounds.width) + "x" + Math.round(clearBounds.height));
            if (clearBounds.left < -1 || clearBounds.right > innerWidth + 1) searchClearIssues.push("topbar_search_clear_outside_viewport");
            if (shellBounds.left < -1 || shellBounds.right > innerWidth + 1) searchClearIssues.push("topbar_search_shell_outside_viewport");
            if (inputBounds.width < 44) searchClearIssues.push("topbar_search_input_collapsed " + Math.round(inputBounds.width));
            searchClear.click();
            if (searchInput.value !== "") searchClearIssues.push("topbar_search_clear_click_did_not_clear");
            if (!searchClear.hidden) searchClearIssues.push("topbar_search_clear_still_visible_after_clear");
          }
        }
        const actionRowDefinitions = [
          { selector: ".portfolio-head", text: ".portfolio-name-btn", action: ".pm-card-actions" },
          { selector: ".gantt-label-row-wrap", text: ".gantt-label-row", action: ".gantt-row-actions" },
          { selector: ".team-row-wrap", text: ".team-row", action: ".team-row-actions" },
          { selector: ".schema-table-li", text: ".schema-table-btn", action: ".schema-table-actions" },
          { selector: ".mig-row-wrap", text: ".mig-row", action: ".mig-row-actions" },
        ];
        const overlaps = (a, b) => a.left < b.right - 1 && b.left < a.right - 1 && a.top < b.bottom - 1 && b.top < a.bottom - 1;
        const actionRowLayouts = actionRowDefinitions.flatMap((definition) => Array.from(document.querySelectorAll(definition.selector)).map((row) => {
          const textNode = row.querySelector(definition.text);
          const actionNode = row.querySelector(definition.action);
          if (!textNode || !actionNode || !isVisible(row) || !isVisible(textNode) || !isVisible(actionNode)) return null;
          const textRect = textNode.getBoundingClientRect();
          const actionRect = actionNode.getBoundingClientRect();
          return {
            selector: definition.selector,
            text: (textNode.textContent || "").replace(/\\s+/g, " ").trim().slice(0, 80),
            textRight: Math.round(textRect.right),
            actionLeft: Math.round(actionRect.left),
            textWidth: Math.round(textRect.width),
            actionWidth: Math.round(actionRect.width),
            overlap: overlaps(textRect, actionRect),
            collapsedText: textRect.width < 24,
          };
        }).filter(Boolean));
        const actionRowIssues = actionRowLayouts.flatMap((row) => {
          const issues = [];
          if (row.overlap) issues.push("action_row_overlap " + row.selector + " " + row.text);
          if (row.collapsedText) issues.push("action_row_text_collapsed " + row.selector + " " + row.text);
          return issues;
        });
        const docScrollWidth = Math.max(document.documentElement.scrollWidth, document.body.scrollWidth);
        return {
          route,
          bodyView: document.body.dataset.view || "",
          textLength: text.trim().length,
          innerWidth,
          innerHeight,
          docScrollWidth,
          overflowX: docScrollWidth > innerWidth + 1,
          shell: rect(shell),
          main: rect(main),
          sidebar: rect(sidebar),
          topbar: rect(topbar),
          visibleViews: Array.from(document.querySelectorAll(".view"))
            .filter((node) => node.hidden === false)
            .map((node) => node.id),
          textControlCount: textControls.length,
          textControlIssues,
          touchActionGroupCount: touchActionGroups.length,
          touchActionIssues,
          iconTouchTargetCount: iconTouchTargets.length,
          iconTouchIssues,
          searchClearIssues,
          actionRowLayoutCount: actionRowLayouts.length,
          actionRowIssues,
          expected: ${JSON.stringify(expectedTexts)},
          missingText: ${JSON.stringify(expectedTexts)}.filter((needle) => !searchableText.includes(needle)),
        };
      })()`);

      if (report.bodyView !== route) failures.push(`${route}: body view is ${report.bodyView || "(empty)"}`);
      if (!report.visibleViews.includes(`view-${route}`)) failures.push(`${route}: visible view missing view-${route}`);
      if (report.textLength < 80) failures.push(`${route}: rendered text too short (${report.textLength})`);
      if (report.missingText.length > 0) failures.push(`${route}: missing text ${report.missingText.join(", ")}`);
      if (report.overflowX) layoutIssues.push(`${route}: horizontal overflow ${report.docScrollWidth}px > ${report.innerWidth}px`);
      if (report.main?.width > report.innerWidth + 1) layoutIssues.push(`${route}: main width ${Math.round(report.main.width)}px > viewport ${report.innerWidth}px`);
      if (report.textControlIssues.length > 0) layoutIssues.push(`${route}: ${report.textControlIssues.join("; ")}`);
      if (report.touchActionIssues.length > 0) layoutIssues.push(`${route}: ${report.touchActionIssues.join("; ")}`);
      if (report.iconTouchIssues.length > 0) layoutIssues.push(`${route}: ${report.iconTouchIssues.join("; ")}`);
      if (report.searchClearIssues.length > 0) layoutIssues.push(`${route}: ${report.searchClearIssues.join("; ")}`);
      if (report.actionRowIssues.length > 0) layoutIssues.push(`${route}: ${report.actionRowIssues.join("; ")}`);
      routeReports.push(report);
      progress("mobile-route-end", {
        route,
        docScrollWidth: report.docScrollWidth,
        innerWidth: report.innerWidth,
        overflowX: report.overflowX,
        textControlCount: report.textControlCount,
        textControlIssues: report.textControlIssues,
        touchActionGroupCount: report.touchActionGroupCount,
        touchActionIssues: report.touchActionIssues,
        iconTouchTargetCount: report.iconTouchTargetCount,
        iconTouchIssues: report.iconTouchIssues,
        searchClearIssues: report.searchClearIssues,
        actionRowLayoutCount: report.actionRowLayoutCount,
        actionRowIssues: report.actionRowIssues,
      });
    }

    currentRoute = "search-empty-mobile";
    const missingSearchEmptyRoutes = routeReports
      .map((report) => report.route)
      .filter((route) => !searchInertRoutes.has(route) && !searchEmptyRoutes.includes(route));
    if (missingSearchEmptyRoutes.length > 0) {
      failures.push(`search empty route coverage missing ${missingSearchEmptyRoutes.join(", ")}`);
    }
    const searchEmptyReports = [];
    for (const route of searchEmptyRoutes) {
      const url = `${baseUrl}/index.html?smoke-search-empty-mobile=${encodeURIComponent(route)}#${route}`;
      await navigateAndWaitForLoad(pageClient, url);
      await waitForAppRoute(pageClient, route);
      const report = await evaluate(pageClient, `(() => {
        const waitFor = (predicate, message, timeout = 5000) => new Promise((resolve, reject) => {
          const started = Date.now();
          const tick = () => {
            try {
              if (predicate()) { resolve(true); return; }
            } catch (error) {
              reject(error);
              return;
            }
            if (Date.now() - started > timeout) reject(new Error(message));
            else setTimeout(tick, 50);
          };
          tick();
        });
        const nextFrame = () => new Promise((resolve) => requestAnimationFrame(() => resolve(true)));
        const rect = (node) => {
          if (!node) return null;
          const bounds = node.getBoundingClientRect();
          return {
            left: Math.round(bounds.left),
            top: Math.round(bounds.top),
            right: Math.round(bounds.right),
            bottom: Math.round(bounds.bottom),
            width: Math.round(bounds.width),
            height: Math.round(bounds.height),
          };
        };
        const withinHorizontalViewport = (bounds) => bounds && bounds.left >= -1 && bounds.right <= innerWidth + 1;
        const route = ${JSON.stringify(route)};
        return (async () => {
          const issues = [];
          const view = document.getElementById("view-" + route);
          const input = document.getElementById("globalSearch");
          const status = document.getElementById("searchCount");
          if (!view || !input || !status) {
            return { route, status: "fail", issues: ["search_empty_mobile_missing_nodes"] };
          }
          const query = "NO_MATCH_MOBILE_" + route;
          await waitFor(() => (
            typeof state !== "undefined" &&
            document.body?.dataset.view === route &&
            input.getAttribute("aria-readonly") === "false" &&
            !input.readOnly
          ), route + " search input did not become ready on mobile", 8000);
          await waitFor(() => {
            input.focus();
            input.value = query;
            const inputEvent = typeof InputEvent === "function"
              ? new InputEvent("input", { bubbles: true, inputType: "insertText", data: query })
              : new Event("input", { bubbles: true });
            input.dispatchEvent(inputEvent);
            return typeof state !== "undefined" && state.query === query && !input.readOnly;
          }, route + " search query did not reach app state on mobile", 8000);
          await new Promise((resolve) => setTimeout(resolve, 220));
          await nextFrame();
          if (!view.querySelector("[data-search-empty]") && typeof renderCurrentView === "function") {
            renderCurrentView();
            await nextFrame();
          }
          await waitFor(() => view.querySelector("[data-search-empty]") && /검색 결과 없음/.test(status.textContent || ""), route + " search empty state did not render on mobile", 8000);
          await nextFrame();
          const matchedAppQuery = typeof state !== "undefined" ? state.query : "";
          const empty = view.querySelector("[data-search-empty]");
          const button = empty ? empty.querySelector('[data-action="clear-search"]') : null;
          const emptyRect = rect(empty);
          const buttonRect = rect(button);
          const statusText = (status.textContent || "").trim();
          if (!empty) issues.push("search_empty_state_missing");
          if (empty && empty.getAttribute("role") !== "status") issues.push("search_empty_state_not_status");
          if (empty && empty.getAttribute("aria-live") !== "polite") issues.push("search_empty_state_not_live");
          if (emptyRect && !withinHorizontalViewport(emptyRect)) issues.push("search_empty_state_horizontal_overflow " + JSON.stringify(emptyRect));
          if (emptyRect && emptyRect.top > innerHeight - 44) issues.push("search_empty_state_below_fold " + JSON.stringify(emptyRect));
          if (empty && empty.scrollWidth > empty.clientWidth + 1) issues.push("search_empty_state_text_overflow");
          if (!button) issues.push("search_empty_clear_missing");
          if (buttonRect && (buttonRect.width < 90 || buttonRect.height < 32)) issues.push("search_empty_clear_too_small " + JSON.stringify(buttonRect));
          if (buttonRect && !withinHorizontalViewport(buttonRect)) issues.push("search_empty_clear_horizontal_overflow " + JSON.stringify(buttonRect));
          if (button && button.scrollWidth > button.clientWidth + 1) issues.push("search_empty_clear_text_overflow");
          if (!/검색 결과 없음/.test(statusText)) issues.push("search_empty_status_missing " + statusText);
          button?.click();
          await waitFor(() => !view.querySelector("[data-search-empty]"), route + " search clear did not restore mobile results");
          await nextFrame();
          if (input.value !== "") issues.push("search_empty_clear_did_not_clear_input");
          if (document.activeElement !== input) issues.push("search_empty_clear_did_not_restore_focus");
          return {
            route,
            status: issues.length === 0 ? "pass" : "fail",
            viewport: { width: innerWidth, height: innerHeight },
            query,
            matchedAppQuery,
            appQueryAfterClear: typeof state !== "undefined" ? state.query : "",
            viewText: (view.innerText || "").slice(0, 500),
            empty: emptyRect,
            clear: buttonRect,
            statusText,
            issues,
          };
        })();
      })()`);
      searchEmptyReports.push(report);
    }
    searchEmptyMobileReport = {
      status: searchEmptyReports.every((report) => report.status === "pass") ? "pass" : "fail",
      expectedRoutes: searchEmptyRoutes,
      searchInertRoutes: searchInertRouteList,
      expectedRouteCount: searchEmptyRoutes.length,
      routes: searchEmptyReports,
      issues: searchEmptyReports.flatMap((report) => (report.issues || []).map((issue) => `${report.route}: ${issue}`)),
    };
    if (searchEmptyMobileReport.status !== "pass") {
      layoutIssues.push(`search empty mobile issues: ${searchEmptyMobileReport.issues.join("; ")}`);
    }
    progress("mobile-search-empty-end", {
      status: searchEmptyMobileReport.status,
      expectedRouteCount: searchEmptyMobileReport.expectedRouteCount,
      search_empty_mobile_issue_count: searchEmptyMobileReport.issues.length,
    });

    currentRoute = "palette-mobile";
    await navigateAndWaitForLoad(pageClient, `${baseUrl}/index.html?smoke-palette-mobile#home`);
    await waitForAppRoute(pageClient, "home");
    paletteMobileReport = await evaluate(pageClient, `(() => {
      const waitFor = (predicate, message, timeout = 5000) => new Promise((resolve, reject) => {
        const started = Date.now();
        const tick = () => {
          try {
            if (predicate()) { resolve(true); return; }
          } catch (error) {
            reject(error);
            return;
          }
          if (Date.now() - started > timeout) reject(new Error(message));
          else setTimeout(tick, 50);
        };
        tick();
      });
      const nextFrame = () => new Promise((resolve) => requestAnimationFrame(() => resolve(true)));
      const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
      const rect = (node) => {
        if (!node) return null;
        const bounds = node.getBoundingClientRect();
        return {
          left: Math.round(bounds.left),
          top: Math.round(bounds.top),
          right: Math.round(bounds.right),
          bottom: Math.round(bounds.bottom),
          width: Math.round(bounds.width),
          height: Math.round(bounds.height),
        };
      };
      const visible = (node) => {
        if (!node) return false;
        const style = getComputedStyle(node);
        const bounds = node.getBoundingClientRect();
        return style.display !== "none" && style.visibility !== "hidden" && bounds.width > 0 && bounds.height > 0;
      };
      const withinViewport = (bounds) => bounds && bounds.left >= -1 && bounds.top >= -1 && bounds.right <= innerWidth + 1 && bounds.bottom <= innerHeight + 1;
      const overlaps = (a, b) => a && b && a.left < b.right - 1 && b.left < a.right - 1 && a.top < b.bottom - 1 && b.top < a.bottom - 1;

      return (async () => {
        const issues = [];
        const cmd = document.querySelector('[data-action="open-palette"]');
        const palette = document.getElementById("palette");
        const panel = document.querySelector(".palette-panel");
        const input = document.getElementById("paletteInput");
        const results = document.getElementById("paletteResults");
        const status = document.getElementById("paletteStatus");
        const hint = document.getElementById("paletteHint");
        if (!cmd || !palette || !panel || !input || !results || !status || !hint) {
          return {
            status: "fail",
            issues: ["palette_mobile_missing_nodes"],
            viewport: { width: innerWidth, height: innerHeight },
          };
        }

        cmd.click();
        await waitFor(() => palette.classList.contains("open") && document.activeElement === input, "palette did not open on mobile");
        await nextFrame();
        const panelRect = rect(panel);
        const inputRect = rect(input);
        const resultsRect = rect(results);
        const hintRect = rect(hint);
        const active = results.querySelector('[role="option"][aria-selected="true"]');
        const activeRect = rect(active);
        const resultStyle = getComputedStyle(results);
        const bodyOverflow = getComputedStyle(document.body).overflow;
        const main = document.querySelector(".main");
        const mainOverflowY = main ? getComputedStyle(main).overflowY : "";
        const itemRects = Array.from(results.querySelectorAll(".pal-item")).slice(0, 6).map(rect);
        const minItemHeight = itemRects.length ? Math.min(...itemRects.map((item) => item.height)) : 0;
        const docScrollWidth = Math.max(document.documentElement.scrollWidth, document.body.scrollWidth);

        if (!withinViewport(panelRect)) issues.push("palette_panel_outside_viewport " + JSON.stringify(panelRect));
        if (!document.body.classList.contains("palette-open")) issues.push("palette_body_not_locked");
        if (bodyOverflow !== "hidden") issues.push("palette_body_overflow_not_hidden " + bodyOverflow);
        if (mainOverflowY && mainOverflowY !== "hidden") issues.push("palette_main_scroll_not_locked " + mainOverflowY);
        if (docScrollWidth > innerWidth + 1) issues.push("palette_open_horizontal_overflow " + docScrollWidth + ">" + innerWidth);
        if (inputRect.height < 44) issues.push("palette_input_touch_target_too_short " + inputRect.height);
        if (resultsRect.height < 120) issues.push("palette_results_too_short " + resultsRect.height);
        if (resultStyle.overflowY !== "auto") issues.push("palette_results_not_scrollable");
        if (!active || !withinViewport(activeRect)) issues.push("palette_active_option_not_visible");
        if (minItemHeight && minItemHeight < 40) issues.push("palette_item_touch_target_too_short " + minItemHeight);
        if (hintRect.width < 120 || !withinViewport(hintRect)) issues.push("palette_hint_outside_viewport");

        input.value = "zzzz-no-match-mobile";
        input.dispatchEvent(new Event("input", { bubbles: true }));
        await waitFor(() => status.classList.contains("is-visible") && /검색 결과가 없습니다/.test(status.textContent), "palette mobile no-results status did not appear");
        await nextFrame();
        const statusRect = rect(status);
        const emptyResultsRect = rect(results);
        const emptyHintRect = rect(hint);
        if (!withinViewport(statusRect)) issues.push("palette_no_results_status_outside_viewport");
        if (status.scrollWidth > status.clientWidth + 1) issues.push("palette_no_results_status_text_overflow");
        if (overlaps(statusRect, emptyHintRect)) issues.push("palette_no_results_status_hint_overlap");
        if (!withinViewport(emptyHintRect)) issues.push("palette_no_results_hint_outside_viewport");
        if (emptyResultsRect && emptyResultsRect.bottom > innerHeight + 1) issues.push("palette_empty_results_outside_viewport");
        const noResultsText = (status.textContent || "").replace(/\\s+/g, " ").trim();

        input.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true, cancelable: true }));
        await waitFor(() => !palette.classList.contains("open"), "palette did not close on mobile");
        if (document.body.classList.contains("palette-open")) issues.push("palette_body_lock_not_cleared");

        return {
          status: issues.length === 0 ? "pass" : "fail",
          viewport: { width: innerWidth, height: innerHeight },
          panel: panelRect,
          input: inputRect,
          results: resultsRect,
          hint: hintRect,
          active: activeRect,
          itemCount: itemRects.length,
          minItemHeight,
          noResultsStatus: statusRect,
          noResultsText,
          noResultsResults: emptyResultsRect,
          noResultsHint: emptyHintRect,
          issues,
        };
      })();
    })()`);
    if (!paletteMobileReport || paletteMobileReport.status !== "pass") {
      const details = paletteMobileReport?.issues?.join("; ") || "no palette mobile report";
      layoutIssues.push(`palette mobile layout issues: ${details}`);
    }
    progress("mobile-palette-end", {
      status: paletteMobileReport?.status || "missing",
      palette_mobile_issue_count: paletteMobileReport?.issues?.length || 0,
    });

    currentRoute = "project-picker-mobile";
    await navigateAndWaitForLoad(pageClient, `${baseUrl}/index.html?smoke-project-picker-mobile#pm-portfolio`);
    await waitForAppRoute(pageClient, "pm-portfolio");
    projectPickerMobileReport = await evaluate(pageClient, `(() => {
      const waitFor = (predicate, message, timeout = 5000) => new Promise((resolve, reject) => {
        const started = Date.now();
        const tick = () => {
          try {
            if (predicate()) { resolve(true); return; }
          } catch (error) {
            reject(error);
            return;
          }
          if (Date.now() - started > timeout) reject(new Error(message));
          else setTimeout(tick, 50);
        };
        tick();
      });
      const nextFrame = () => new Promise((resolve) => requestAnimationFrame(() => resolve(true)));
      const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
      const rect = (node) => {
        if (!node) return null;
        const bounds = node.getBoundingClientRect();
        return {
          left: Math.round(bounds.left),
          top: Math.round(bounds.top),
          right: Math.round(bounds.right),
          bottom: Math.round(bounds.bottom),
          width: Math.round(bounds.width),
          height: Math.round(bounds.height),
        };
      };
      const withinViewport = (bounds) => bounds && bounds.left >= -1 && bounds.top >= -1 && bounds.right <= innerWidth + 1 && bounds.bottom <= innerHeight + 1;

      return (async () => {
        const issues = [];
        const opener = document.getElementById("projectSelect");
        const picker = document.getElementById("projectPicker");
        if (!opener || !picker) {
          return {
            status: "fail",
            issues: ["project_picker_mobile_missing_nodes"],
            viewport: { width: innerWidth, height: innerHeight },
          };
        }
        opener.click();
        await waitFor(() => !picker.hasAttribute("hidden"), "project picker did not open on mobile");
        await nextFrame();
        const input = document.getElementById("projectPickerSearch");
        const list = document.getElementById("projectPickerList");
        const status = document.getElementById("projectPickerStatus");
        const pickerRect = rect(picker);
        const listRect = rect(list);
        const optionRects = Array.from(list ? list.querySelectorAll('[role="option"]') : []).slice(0, 6).map(rect);
        const minOptionHeight = optionRects.length ? Math.min(...optionRects.map((item) => item.height)) : 0;
        const listStyle = list ? getComputedStyle(list) : null;
        const bodyOverflow = getComputedStyle(document.body).overflow;
        const main = document.querySelector(".main");
        const mainOverflowY = main ? getComputedStyle(main).overflowY : "";
        const docScrollWidth = Math.max(document.documentElement.scrollWidth, document.body.scrollWidth);
        if (!input || !list || !status) issues.push("project_picker_mobile_scaffold_missing");
        if (!withinViewport(pickerRect)) issues.push("project_picker_outside_viewport " + JSON.stringify(pickerRect));
        if (!document.body.classList.contains("project-picker-open")) issues.push("project_picker_body_not_locked");
        if (bodyOverflow !== "hidden") issues.push("project_picker_body_overflow_not_hidden " + bodyOverflow);
        if (mainOverflowY && mainOverflowY !== "hidden") issues.push("project_picker_main_scroll_not_locked " + mainOverflowY);
        if (docScrollWidth > innerWidth + 1) issues.push("project_picker_open_horizontal_overflow " + docScrollWidth + ">" + innerWidth);
        if (listStyle && listStyle.overflowY !== "auto") issues.push("project_picker_list_not_scrollable");
        if (listRect && listRect.height < 120) issues.push("project_picker_list_too_short " + listRect.height);
        if (minOptionHeight && minOptionHeight < 40) issues.push("project_picker_option_too_short " + minOptionHeight);
        if (input && input.getAttribute("aria-describedby") !== "projectPickerStatus") issues.push("project_picker_search_missing_status_description");

        if (input && list && status) {
          input.value = "zzzz-no-project-mobile";
          input.dispatchEvent(new Event("input", { bubbles: true }));
          await waitFor(() => status.classList.contains("is-visible") && /일치하는 프로젝트가 없습니다/.test(status.textContent), "project picker mobile no-results status did not appear");
          await nextFrame();
          const statusRect = rect(status);
          const emptyListRect = rect(list);
          if (list.querySelectorAll('[role="option"]').length !== 0) issues.push("project_picker_no_results_options_remained");
          if (!withinViewport(statusRect)) issues.push("project_picker_no_results_status_outside_viewport");
          if (status.scrollWidth > status.clientWidth + 1) issues.push("project_picker_no_results_status_text_overflow");
          if (emptyListRect && emptyListRect.bottom > innerHeight + 1) issues.push("project_picker_empty_list_outside_viewport");
        }

        input?.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true, cancelable: true }));
        await waitFor(() => picker.hasAttribute("hidden"), "project picker did not close on mobile");
        if (document.body.classList.contains("project-picker-open")) issues.push("project_picker_body_lock_not_cleared");

        return {
          status: issues.length === 0 ? "pass" : "fail",
          viewport: { width: innerWidth, height: innerHeight },
          picker: pickerRect,
          list: listRect,
          itemCount: optionRects.length,
          minOptionHeight,
          issues,
        };
      })();
    })()`);
    if (!projectPickerMobileReport || projectPickerMobileReport.status !== "pass") {
      const details = projectPickerMobileReport?.issues?.join("; ") || "no project picker mobile report";
      layoutIssues.push(`project picker mobile layout issues: ${details}`);
    }
    progress("mobile-project-picker-end", {
      status: projectPickerMobileReport?.status || "missing",
      project_picker_mobile_issue_count: projectPickerMobileReport?.issues?.length || 0,
    });

    currentRoute = "notification-sheet-mobile";
    await navigateAndWaitForLoad(pageClient, `${baseUrl}/index.html?smoke-notification-sheet-mobile#home`);
    await waitForAppRoute(pageClient, "home");
    notificationSheetMobileReport = await evaluate(pageClient, `(() => {
      const waitFor = (predicate, message, timeout = 5000) => new Promise((resolve, reject) => {
        const started = Date.now();
        const tick = () => {
          try {
            if (predicate()) { resolve(true); return; }
          } catch (error) {
            reject(error);
            return;
          }
          if (Date.now() - started > timeout) reject(new Error(message));
          else setTimeout(tick, 50);
        };
        tick();
      });
      const nextFrame = () => new Promise((resolve) => requestAnimationFrame(() => resolve(true)));
      const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
      const rect = (node) => {
        if (!node) return null;
        const bounds = node.getBoundingClientRect();
        return {
          left: Math.round(bounds.left),
          top: Math.round(bounds.top),
          right: Math.round(bounds.right),
          bottom: Math.round(bounds.bottom),
          width: Math.round(bounds.width),
          height: Math.round(bounds.height),
        };
      };
      const withinViewport = (bounds) => bounds && bounds.left >= -1 && bounds.top >= -1 && bounds.right <= innerWidth + 1 && bounds.bottom <= innerHeight + 1;

      return (async () => {
        const issues = [];
        const sheet = document.getElementById("sheet");
        const panel = sheet?.querySelector(".sheet-panel");
        const bell = document.querySelector('.bell[data-action="open-notifications"]');
        const original = {
          todos: Array.isArray(dashboard.todos) ? [...dashboard.todos] : [],
          events: Array.isArray(dashboard.events) ? [...dashboard.events] : [],
          habits: Array.isArray(dashboard.habits) ? [...dashboard.habits] : [],
        };
        const closeSheetIfOpen = async () => {
          if (!sheet?.classList.contains("open")) return;
          sheet.querySelector('[data-action="close-sheet"]')?.click();
          await waitFor(() => !sheet.classList.contains("open"), "notification sheet did not close");
          await nextFrame();
        };
        try {
          dashboard.events = [];
          dashboard.habits = [];
          dashboard.todos = Array.from({ length: 34 }, (_, index) => ({
            id: "mobile-alert-" + index,
            title: "모바일 알림 긴 제목 점검 " + index + " viewport overflow regression sentinel",
            due: "2000-01-01",
            priority: "high",
            done: false,
            category: "smoke",
            memo: "",
            createdAt: new Date().toISOString(),
          }));
          bell?.click();
          await waitFor(() => sheet?.classList.contains("open"), "notification sheet did not open with long alerts");
          await waitFor(() => withinViewport(rect(panel)) && document.body.classList.contains("sheet-open") && getComputedStyle(document.body).overflow === "hidden" && sheet.querySelectorAll("[data-alert-row]").length >= 30, "notification sheet did not settle with long alerts", 8000);
          await nextFrame();
          const panelRect = rect(panel);
          const list = sheet.querySelector("[data-alert-list]");
          const listRect = rect(list);
          const rows = Array.from(sheet.querySelectorAll("[data-alert-row]"));
          const rowRects = rows.slice(0, 8).map(rect);
          const minRowHeight = rowRects.length ? Math.min(...rowRects.map((item) => item.height)) : 0;
          const listStyle = list ? getComputedStyle(list) : null;
          const bodyStyle = getComputedStyle(document.body);
          const main = document.querySelector(".main");
          const mainStyle = main ? getComputedStyle(main) : null;
          const firstRow = rows[0];
          if (!withinViewport(panelRect)) issues.push("notification_sheet_panel_outside_viewport " + JSON.stringify(panelRect));
          if (!document.body.classList.contains("sheet-open")) issues.push("notification_sheet_body_not_locked");
          if (bodyStyle.overflow !== "hidden") issues.push("notification_sheet_body_overflow_not_hidden " + bodyStyle.overflow);
          if (mainStyle && mainStyle.overflowY !== "hidden") issues.push("notification_sheet_main_scroll_not_locked " + mainStyle.overflowY);
          if (!list || rows.length < 30) issues.push("notification_alert_list_missing_rows " + rows.length);
          if (listStyle && listStyle.overflowY !== "auto") issues.push("notification_alert_list_not_scrollable");
          if (list && list.scrollHeight <= list.clientHeight + 1) issues.push("notification_alert_list_not_scroll_needed");
          if (listRect && !withinViewport(listRect)) issues.push("notification_alert_list_outside_viewport " + JSON.stringify(listRect));
          if (minRowHeight && minRowHeight < 40) issues.push("notification_alert_row_too_short " + minRowHeight);
          if (firstRow && firstRow.scrollWidth > firstRow.clientWidth + 1) issues.push("notification_alert_row_text_overflow");
          await closeSheetIfOpen();

          dashboard.todos = [];
          dashboard.events = [];
          dashboard.habits = [];
          bell?.click();
          await waitFor(() => sheet?.classList.contains("open"), "notification sheet did not open empty state");
          await waitFor(() => withinViewport(rect(panel)) && document.body.classList.contains("sheet-open") && getComputedStyle(document.body).overflow === "hidden" && sheet.querySelector("[data-notification-empty]"), "notification sheet did not settle empty state", 8000);
          await nextFrame();
          const empty = sheet.querySelector("[data-notification-empty]");
          const emptyRect = rect(empty);
          if (!empty) issues.push("notification_empty_state_missing");
          if (empty && empty.getAttribute("role") !== "status") issues.push("notification_empty_state_not_status");
          if (empty && !/확인할 알림이 없습니다/.test(empty.textContent || "")) issues.push("notification_empty_state_text_missing");
          if (emptyRect && !withinViewport(emptyRect)) issues.push("notification_empty_state_outside_viewport");
          await closeSheetIfOpen();
          if (document.body.classList.contains("sheet-open")) issues.push("notification_sheet_body_lock_not_cleared");
        } finally {
          dashboard.todos = original.todos;
          dashboard.events = original.events;
          dashboard.habits = original.habits;
        }

        return {
          status: issues.length === 0 ? "pass" : "fail",
          viewport: { width: innerWidth, height: innerHeight },
          issues,
        };
      })();
    })()`);
    if (!notificationSheetMobileReport || notificationSheetMobileReport.status !== "pass") {
      const details = notificationSheetMobileReport?.issues?.join("; ") || "no notification sheet mobile report";
      layoutIssues.push(`notification sheet mobile layout issues: ${details}`);
    }
    progress("mobile-notification-sheet-end", {
      status: notificationSheetMobileReport?.status || "missing",
      notification_sheet_mobile_issue_count: notificationSheetMobileReport?.issues?.length || 0,
    });

    currentRoute = "sheet-actions";
    await navigateAndWaitForLoad(pageClient, `${baseUrl}/index.html?smoke-sheet-actions#pm-portfolio`);
    await waitForAppRoute(pageClient, "pm-portfolio");
    sheetActionReport = await evaluate(pageClient, `(() => {
      const waitFor = (predicate, message, timeout = 5000) => new Promise((resolve, reject) => {
        const started = Date.now();
        const tick = () => {
          try {
            if (predicate()) { resolve(true); return; }
          } catch (error) {
            reject(error);
            return;
          }
          if (Date.now() - started > timeout) reject(new Error(message));
          else setTimeout(tick, 50);
        };
        tick();
      });
      const nextFrame = () => new Promise((resolve) => requestAnimationFrame(() => resolve(true)));
      const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
      const sheet = document.getElementById("sheet");
      const inspectButtons = (context) => Array.from(document.querySelectorAll("#sheet .sheet-action")).map((node) => {
        const rect = node.getBoundingClientRect();
        return {
          context,
          text: node.textContent.trim(),
          left: Math.round(rect.left),
          right: Math.round(rect.right),
          width: Math.round(rect.width),
          height: Math.round(rect.height),
          clientWidth: node.clientWidth,
          scrollWidth: node.scrollWidth,
          overflowX: node.scrollWidth > node.clientWidth + 1,
          tooShort: rect.height < 35,
          outsideViewport: rect.left < -1 || rect.right > innerWidth + 1,
        };
      });
      const inspectActionGroups = (context) => Array.from(document.querySelectorAll("#sheet .sheet-col-actions")).map((node) => {
        const rect = node.getBoundingClientRect();
        const opacity = Number.parseFloat(getComputedStyle(node).opacity || "1");
        return {
          context,
          selector: node.className || node.tagName.toLowerCase(),
          left: Math.round(rect.left),
          right: Math.round(rect.right),
          width: Math.round(rect.width),
          height: Math.round(rect.height),
          opacity,
          hidden: opacity < 0.99,
        };
      });
      const inspectIconTargets = (context) => Array.from(document.querySelectorAll("#sheet .pm-icon-btn")).map((node) => {
        const rect = node.getBoundingClientRect();
        return {
          context,
          selector: node.className || node.tagName.toLowerCase(),
          label: node.getAttribute("aria-label") || node.getAttribute("title") || (node.textContent || "").trim(),
          width: Math.round(rect.width),
          height: Math.round(rect.height),
          tooSmall: rect.width < 31 || rect.height < 31,
        };
      });
      const rectsOverlap = (a, b) => a.left < b.right - 1 && b.left < a.right - 1 && a.top < b.bottom - 1 && b.top < a.bottom - 1;
      const inspectActionRows = (context) => Array.from(document.querySelectorAll("#sheet .sheet-col-row")).map((row) => {
        const textNode = row.querySelector(".sheet-col-name");
        const actionNode = row.querySelector(".sheet-col-actions");
        if (!textNode || !actionNode) return null;
        const textRect = textNode.getBoundingClientRect();
        const actionRect = actionNode.getBoundingClientRect();
        return {
          context,
          selector: "sheet-col-row",
          text: (textNode.textContent || "").replace(/\\s+/g, " ").trim(),
          textRight: Math.round(textRect.right),
          actionLeft: Math.round(actionRect.left),
          textWidth: Math.round(textRect.width),
          actionWidth: Math.round(actionRect.width),
          overlap: rectsOverlap(textRect, actionRect),
          collapsedText: textRect.width < 24,
        };
      }).filter(Boolean);
      const openAndInspect = async (route, openerSelector, context) => {
        if (document.body.dataset.view !== route) {
          location.hash = route;
          await waitFor(() => document.body.dataset.view === route, route + " route did not open");
          await nextFrame();
        }
        const opener = document.querySelector(openerSelector);
        if (!opener) return { context, missingOpener: true, buttons: [] };
        opener.click();
        await waitFor(() => sheet.classList.contains("open"), context + " sheet did not open");
        await waitFor(() => inspectButtons(context).every((button) => !button.outsideViewport), context + " sheet action buttons did not enter viewport", 8000);
        await nextFrame();
        const buttons = inspectButtons(context);
        const actionGroups = inspectActionGroups(context);
        const iconTargets = inspectIconTargets(context);
        const actionRows = inspectActionRows(context);
        document.querySelector('#sheet [data-action="close-sheet"]')?.click();
        await waitFor(() => !sheet.classList.contains("open"), context + " sheet did not close");
        return { context, missingOpener: false, buttons, actionGroups, iconTargets, actionRows };
      };

      return (async () => {
        const project = await openAndInspect("pm-portfolio", ".portfolio-card [data-action='open-project']", "sheet_actions_project");
        const table = await openAndInspect("dbm-schema", "[data-action='open-table']", "sheet_actions_table");
        const buttons = [...project.buttons, ...table.buttons];
        const actionGroups = [...(project.actionGroups || []), ...(table.actionGroups || [])];
        const iconTargets = [...(project.iconTargets || []), ...(table.iconTargets || [])];
        const actionRows = [...(project.actionRows || []), ...(table.actionRows || [])];
        const issues = [];
        for (const group of [project, table]) {
          if (group.missingOpener) issues.push(group.context + ": missing opener");
        }
        buttons.forEach((button) => {
          if (button.overflowX) issues.push(button.context + ": sheet_action_button_overflow " + button.text);
          if (button.tooShort) issues.push(button.context + ": sheet_action_button_too_short " + button.text);
          if (button.outsideViewport) issues.push(button.context + ": sheet_action_button_outside_viewport " + button.text);
        });
        actionGroups.forEach((group) => {
          if (group.hidden) issues.push(group.context + ": touch_action_group_hidden sheet_col_actions");
        });
        iconTargets.forEach((target) => {
          if (target.tooSmall) issues.push(target.context + ": icon_touch_target_too_small sheet_icon_targets " + target.width + "x" + target.height + " " + target.label);
        });
        actionRows.forEach((row) => {
          if (row.overlap) issues.push(row.context + ": action_row_overlap sheet_col_row " + row.text);
          if (row.collapsedText) issues.push(row.context + ": action_row_text_collapsed sheet_col_row " + row.text);
        });
        return {
          status: issues.length === 0 ? "pass" : "fail",
          buttonCount: buttons.length,
          actionGroupCount: actionGroups.length,
          iconTargetCount: iconTargets.length,
          actionRowCount: actionRows.length,
          issues,
          buttons,
          actionGroups,
          iconTargets,
          actionRows,
        };
      })();
    })()`);
    if (!sheetActionReport || sheetActionReport.status !== "pass") {
      const details = sheetActionReport?.issues?.join("; ") || "no sheet action report";
      layoutIssues.push(`sheet action layout issues: ${details}`);
    }

    currentRoute = "modal-touch";
    await navigateAndWaitForLoad(pageClient, `${baseUrl}/index.html?smoke-modal-touch#notes`);
    await waitForAppRoute(pageClient, "notes");
    modalTouchReport = await evaluate(pageClient, `(() => {
      const waitFor = (predicate, message, timeout = 5000) => new Promise((resolve, reject) => {
        const started = Date.now();
        const tick = () => {
          try {
            if (predicate()) { resolve(true); return; }
          } catch (error) {
            reject(error);
            return;
          }
          if (Date.now() - started > timeout) reject(new Error(message));
          else setTimeout(tick, 50);
        };
        tick();
      });
      const nextFrame = () => new Promise((resolve) => requestAnimationFrame(() => resolve(true)));
      const modal = document.getElementById("modal");
      const rect = (node) => {
        if (!node) return null;
        const bounds = node.getBoundingClientRect();
        return {
          left: Math.round(bounds.left),
          top: Math.round(bounds.top),
          right: Math.round(bounds.right),
          bottom: Math.round(bounds.bottom),
          width: Math.round(bounds.width),
          height: Math.round(bounds.height),
        };
      };
      const withinViewport = (bounds) => bounds && bounds.left >= -1 && bounds.top >= -1 && bounds.right <= innerWidth + 1 && bounds.bottom <= innerHeight + 1;
      const inspectSwatches = (context) => Array.from(document.querySelectorAll("#modal .swatch")).map((node) => {
        const rect = node.getBoundingClientRect();
        const input = node.querySelector('input[type="radio"]');
        const inputRect = input ? input.getBoundingClientRect() : rect;
        return {
          context,
          width: Math.round(rect.width),
          height: Math.round(rect.height),
          inputWidth: Math.round(inputRect.width),
          inputHeight: Math.round(inputRect.height),
          tooSmall: rect.width < 31 || rect.height < 31 || inputRect.width < 31 || inputRect.height < 31,
          outsideViewport: rect.left < -1 || rect.top < -1 || rect.right > innerWidth + 1 || rect.bottom > innerHeight + 1,
        };
      });
      const openAndInspect = async (route, openerSelector, context) => {
        if (document.body.dataset.view !== route) {
          location.hash = route;
          await waitFor(() => document.body.dataset.view === route, route + " route did not open");
          await nextFrame();
        }
        const opener = document.querySelector(openerSelector);
        if (!opener) return { context, missingOpener: true, swatches: [] };
        opener.focus();
        await nextFrame();
        opener.click();
        await waitFor(() => {
          const panelBounds = rect(modal.querySelector(".modal-panel"));
          const bodyOverflow = getComputedStyle(document.body).overflow;
          return modal.classList.contains("open") &&
            withinViewport(panelBounds) &&
            (document.body.classList.contains("modal-open") || bodyOverflow === "hidden") &&
            document.querySelectorAll("#modal .swatch").length >= 6;
        }, context + " modal touch state did not settle", 8000);
        await nextFrame();
        const panelRect = rect(modal.querySelector(".modal-panel"));
        const main = document.querySelector(".main");
        const bodyOverflow = getComputedStyle(document.body).overflow;
        const mainOverflowY = main ? getComputedStyle(main).overflowY : "";
        const bodyLocked = document.body.classList.contains("modal-open") || bodyOverflow === "hidden";
        const swatches = inspectSwatches(context);
        document.querySelector('#modal [data-action="close-modal"]')?.click();
        await waitFor(() => !modal.classList.contains("open"), context + " modal did not close");
        await waitFor(() => document.activeElement === opener, context + " modal focus was not restored", 8000);
        await nextFrame();
        return {
          context,
          missingOpener: false,
          swatches,
          panelRect,
          bodyLocked,
          bodyOverflow,
          mainOverflowY,
          lockCleared: !document.body.classList.contains("modal-open"),
          focusRestored: document.activeElement === opener,
        };
      };

      return (async () => {
        const note = await openAndInspect("notes", '[data-action="note-add"]', "note_modal_swatches");
        const habit = await openAndInspect("habits", '[data-action="habit-add"]', "habit_modal_swatches");
        const swatches = [...note.swatches, ...habit.swatches];
        const issues = [];
        for (const group of [note, habit]) {
          if (group.missingOpener) issues.push(group.context + ": missing opener");
          if (group.panelRect && !withinViewport(group.panelRect)) issues.push(group.context + ": modal_panel_outside_viewport " + JSON.stringify(group.panelRect));
          if (!group.bodyLocked) issues.push(group.context + ": modal_body_not_locked " + group.bodyOverflow);
          if (group.mainOverflowY && group.mainOverflowY !== "hidden") issues.push(group.context + ": modal_main_scroll_not_locked " + group.mainOverflowY);
          if (!group.lockCleared) issues.push(group.context + ": modal_body_lock_not_cleared");
          if (!group.focusRestored) issues.push(group.context + ": modal_focus_not_restored");
        }
        swatches.forEach((swatch) => {
          if (swatch.tooSmall) issues.push(swatch.context + ": modal_swatch_touch_target_too_small " + swatch.width + "x" + swatch.height + " input " + swatch.inputWidth + "x" + swatch.inputHeight);
          if (swatch.outsideViewport) issues.push(swatch.context + ": modal_swatch_outside_viewport");
        });
        return {
          status: issues.length === 0 ? "pass" : "fail",
          swatchCount: swatches.length,
          issues,
          swatches,
        };
      })();
    })()`);
    if (!modalTouchReport || modalTouchReport.status !== "pass") {
      const details = modalTouchReport?.issues?.join("; ") || "no modal touch report";
      layoutIssues.push(`modal touch layout issues: ${details}`);
    }
  } finally {
    if (pageClient) pageClient.close();
    await terminateProcess(chrome);
    cleanupTmpProfile();
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
  if (layoutIssues.length > 0) failures.push(`mobile layout issues: ${layoutIssues.length}`);

  const summary = {
    baseUrl,
    viewport: {
      width: viewportWidth,
      height: viewportHeight,
    },
    routeCount: routeReports.length,
    searchEmptyMobileReport,
    search_empty_mobile_issue_count: searchEmptyMobileReport?.issues?.length || 0,
    paletteMobileReport,
    palette_mobile_issue_count: paletteMobileReport?.issues?.length || 0,
    projectPickerMobileReport,
    project_picker_mobile_issue_count: projectPickerMobileReport?.issues?.length || 0,
    notificationSheetMobileReport,
    notification_sheet_mobile_issue_count: notificationSheetMobileReport?.issues?.length || 0,
    sheetActionReport,
    modalTouchReport,
    routes: routeReports.map((r) => ({
      route: r.route,
      bodyView: r.bodyView,
      textLength: r.textLength,
      innerWidth: r.innerWidth,
      docScrollWidth: r.docScrollWidth,
      overflowX: r.overflowX,
      missingText: r.missingText,
      textControlCount: r.textControlCount,
      textControlIssueCount: r.textControlIssues.length,
      touchActionGroupCount: r.touchActionGroupCount,
      touchActionIssueCount: r.touchActionIssues.length,
      iconTouchTargetCount: r.iconTouchTargetCount,
      iconTouchIssueCount: r.iconTouchIssues.length,
      searchClearIssueCount: r.searchClearIssues.length,
      actionRowLayoutCount: r.actionRowLayoutCount,
      actionRowIssueCount: r.actionRowIssues.length,
    })),
    layoutIssues,
    consoleIssues: appConsoleIssues,
    networkIssues: appNetworkIssues,
    status: failures.length === 0 ? "pass" : "fail",
    failures,
  };

  console.log(JSON.stringify(summary, null, 2));
  if (failures.length > 0) process.exit(1);
  process.exit(0);
}

main().catch((error) => {
  cleanupTmpProfile();
  console.error(error.stack || error.message);
  process.exit(1);
});
