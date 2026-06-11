#!/usr/bin/env node

import { spawn } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const chromePath = process.env.CHROME_PATH || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const baseUrl = (process.env.BASE_URL || "http://127.0.0.1:5178").replace(/\/+$/, "");
const tmpProfile = mkdtempSync(join(tmpdir(), "joopark-a11y-smoke-"));
const progressEnabled = process.env.SMOKE_PROGRESS === "1";
const defaultCdpTimeoutMs = 10000;
const defaultEvaluateTimeoutMs = positiveMsOption(process.env.SMOKE_RUNTIME_TIMEOUT_MS, 60000);
const routeReadyTimeoutMs = positiveMsOption(process.env.SMOKE_ROUTE_READY_TIMEOUT_MS, 12000);

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

async function waitForHome(client) {
  await evaluate(client, `
    new Promise((resolve, reject) => {
      const started = Date.now();
      const check = () => {
        const view = document.getElementById("view-home");
        const ready = document.readyState === "complete" &&
          document.body &&
          document.body.dataset.view === "home" &&
          view &&
          view.hidden === false &&
          view.innerText.trim().length > 0;
        if (ready) resolve(true);
        else if (Date.now() - started > ${routeReadyTimeoutMs}) reject(new Error("home route not ready"));
        else setTimeout(check, 100);
      };
      check();
    })
  `);
  await delay(650);
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

  const failures = [];
  const consoleIssues = [];
  const networkIssues = [];
  let checks = {};
  let pageClient;

  try {
    const browserWs = await waitForDevTools(chrome);
    const pageWs = await pageWebSocketUrl(browserWs);
    pageClient = new CdpClient(pageWs);
    await pageClient.open();

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
      networkIssues.push({
        requestId: params.requestId,
        text: params.errorText || "network loading failed",
      });
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
    await waitForHome(pageClient);

    const domResult = await evaluate(pageClient, `(() => {
      const failures = [];
      const checks = {};
      const check = (id, condition, message) => {
        checks[id] = Boolean(condition);
        if (!condition) failures.push(message || id);
      };
      const waitFor = (predicate, message, timeout = 4000) => new Promise((resolve, reject) => {
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
      const sendKey = (target, key) => {
        target.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true }));
      };
      const nextFrame = () => new Promise((resolve) => requestAnimationFrame(() => resolve(true)));
      const navTo = async (view) => {
        location.hash = view;
        await waitFor(() => {
          const viewEl = document.getElementById("view-" + view);
          return document.body.dataset.view === view &&
            viewEl &&
            viewEl.hidden === false &&
            !viewEl.querySelector("[data-ops-runtime-loading]") &&
            viewEl.innerText.trim().length > 0;
        }, view + " route did not open");
        await nextFrame();
      };
      const hasActionLabel = (selector, term) => {
        const node = document.querySelector(selector);
        const label = node ? (node.getAttribute("aria-label") || "") : "";
        return Boolean(node && label.includes(term) && !["✎", "✕", "◀", "▶"].includes(label.trim()));
      };
      const hasActionTitle = (selector, term) => {
        const node = document.querySelector(selector);
        const title = node ? (node.getAttribute("title") || "").trim() : "";
        return Boolean(node && title.includes(term) && !["편집", "삭제"].includes(title));
      };
      const actionLabel = (root, selector) => {
        const node = root ? root.querySelector(selector) : null;
        return node ? (node.getAttribute("aria-label") || "").trim() : "";
      };

      return (async () => {
        const palette = document.getElementById("palette");
        const paletteInput = document.getElementById("paletteInput");
        const paletteResults = document.getElementById("paletteResults");
        const paletteStatus = document.getElementById("paletteStatus");
        const paletteHint = document.getElementById("paletteHint");
        const cmdButton = document.querySelector('[data-action="open-palette"]');
        const paletteDescribedBy = (paletteInput && paletteInput.getAttribute("aria-describedby") || "").split(/\\s+/).filter(Boolean);
        check("palette_initial_hidden", palette && palette.getAttribute("aria-hidden") === "true", "palette should start hidden");
        check("palette_input_combobox", paletteInput && paletteInput.getAttribute("role") === "combobox", "palette input should be a combobox");
        check("palette_input_controls_results", paletteInput && paletteInput.getAttribute("aria-controls") === "paletteResults", "palette input should control the results list");
        check("palette_input_describedby_hint_status", paletteDescribedBy.includes("paletteHint") && paletteDescribedBy.includes("paletteStatus"), "palette input should describe keyboard help and dynamic result status");
        check("palette_results_listbox", paletteResults && paletteResults.getAttribute("role") === "listbox", "palette results should be a listbox");
        check("palette_status_live_region", paletteStatus && paletteStatus.getAttribute("role") === "status" && paletteStatus.getAttribute("aria-live") === "polite", "palette status should be a polite live region");
        check("palette_hint_id_exists", Boolean(paletteHint), "palette keyboard hint should be addressable");
        check("command_button_exists", Boolean(cmdButton), "command palette button is missing");
        check("command_palette_module_loaded", window.JooParkCommandPalette && window.JooParkCommandPalette.version === "joopark-command-palette/v1" && typeof window.JooParkCommandPalette.create === "function", "command palette runtime module should be loaded");

        cmdButton.focus();
        cmdButton.click();
        await waitFor(() => palette.classList.contains("open"), "palette did not open");
        check("palette_open_expanded", paletteInput.getAttribute("aria-expanded") === "true", "palette combobox should be expanded when open");
        check("palette_body_lock", document.body.classList.contains("palette-open"), "palette should lock the background scroll container while open");
        check("palette_focuses_input", document.activeElement === paletteInput, "palette did not focus the input");
        let selected = paletteResults.querySelector('[role="option"][aria-selected="true"]');
        check("palette_selected_option_exists", Boolean(selected && selected.id), "palette selected option should have an id");
        check("palette_active_descendant_matches", paletteInput.getAttribute("aria-activedescendant") === selected.id, "palette active descendant does not match selected option");
        check("palette_status_announces_results", /개 결과/.test((paletteStatus && paletteStatus.textContent) || ""), "palette status should announce the current result count");

        sendKey(paletteInput, "ArrowDown");
        await nextFrame();
        selected = paletteResults.querySelector('[role="option"][aria-selected="true"]');
        check("palette_arrow_updates_active_descendant", selected && paletteInput.getAttribute("aria-activedescendant") === selected.id, "palette arrow navigation did not update active descendant");

        paletteInput.value = "zzzz-no-match";
        paletteInput.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: "z" }));
        await waitFor(() => paletteResults.querySelectorAll('[role="option"]').length === 0, "palette no-results state did not render");
        check("palette_no_results_clears_active_descendant", !paletteInput.hasAttribute("aria-activedescendant"), "palette no-results state should clear active descendant");
        check("palette_no_results_status_visible", paletteStatus && paletteStatus.classList.contains("is-visible") && /검색 결과가 없습니다/.test(paletteStatus.textContent), "palette no-results status should be visible and announced");

        sendKey(paletteInput, "Escape");
        await waitFor(() => !palette.classList.contains("open"), "palette did not close");
        check("palette_close_collapsed", paletteInput.getAttribute("aria-expanded") === "false", "palette combobox should be collapsed after close");
        check("palette_close_clears_active_descendant", !paletteInput.hasAttribute("aria-activedescendant"), "palette active descendant should clear after close");
        check("palette_close_clears_status", paletteStatus && !paletteStatus.textContent.trim() && !paletteStatus.classList.contains("is-visible"), "palette status should clear after close");
        check("palette_body_lock_cleared", !document.body.classList.contains("palette-open"), "palette should clear the background lock after close");
        check("palette_restores_focus", document.activeElement === cmdButton, "palette did not restore focus to opener");

        document.dispatchEvent(new KeyboardEvent("keydown", { key: "?", bubbles: true, cancelable: true }));
        const modal = document.getElementById("modal");
        await waitFor(() => modal.classList.contains("open"), "shortcut help modal did not open");
        const modalClose = modal.querySelector('.modal-close[data-action="close-modal"]');
        const modalPanel = modal.querySelector(".modal-panel");
        check("modal_visible_to_a11y", modal.getAttribute("aria-hidden") === "false", "open modal should not be aria-hidden");
        check("modal_panel_labelled_dialog", modalPanel && modalPanel.getAttribute("role") === "dialog" && modalPanel.getAttribute("aria-modal") === "true" && modalPanel.getAttribute("aria-labelledby") === "modalTitle", "modal panel should be a labelled modal dialog");
        check("modal_body_lock", document.body.classList.contains("modal-open"), "open modal should lock the background scroll container");
        check("informational_modal_focuses_close", document.activeElement === modalClose, "informational modal should focus the close button");
        modalClose.click();
        await waitFor(() => !modal.classList.contains("open"), "shortcut help modal did not close");
        check("modal_body_lock_cleared", !document.body.classList.contains("modal-open"), "modal should clear the background lock after closing");
        await navTo("pm-portfolio");

        const projectSelect = document.getElementById("projectSelect");
        const projectPicker = document.getElementById("projectPicker");
        await waitFor(() => getComputedStyle(projectSelect).display !== "none", "project picker opener is not visible on PM route");
        check("project_picker_button_dialog", projectSelect && projectSelect.getAttribute("aria-haspopup") === "dialog", "project picker button should announce dialog popup");
        check("project_picker_button_controls", projectSelect && projectSelect.getAttribute("aria-controls") === "projectPicker", "project picker button should control the picker");
        check("project_picker_dialog_role", projectPicker && projectPicker.getAttribute("role") === "dialog", "project picker popup should use dialog role");
        projectSelect.focus();
        projectSelect.click();
        await waitFor(() => !projectPicker.hasAttribute("hidden"), "project picker did not open");
        const pickerSearch = document.getElementById("projectPickerSearch");
        const projectList = document.getElementById("projectPickerList");
        const projectPickerStatus = document.getElementById("projectPickerStatus");
        const projectOptions = Array.from(projectList ? projectList.querySelectorAll('[role="option"]') : []);
        check("project_picker_expanded", projectSelect.getAttribute("aria-expanded") === "true", "project picker button should expand");
        check("project_picker_body_lock", document.body.classList.contains("project-picker-open"), "project picker should lock the background scroll container while open");
        check("project_picker_focuses_search", document.activeElement === pickerSearch, "project picker did not focus search");
        check("project_picker_search_controls_list", pickerSearch && pickerSearch.getAttribute("aria-controls") === "projectPickerList", "project picker search should control list");
        check("project_picker_search_describes_status", pickerSearch && pickerSearch.getAttribute("aria-describedby") === "projectPickerStatus", "project picker search should describe dynamic result status");
        check("project_picker_listbox", projectList && projectList.getAttribute("role") === "listbox", "project picker options should be inside a listbox");
        check("project_picker_status_live_region", projectPickerStatus && projectPickerStatus.getAttribute("role") === "status" && projectPickerStatus.getAttribute("aria-live") === "polite", "project picker status should be a polite live region");
        check("project_picker_options_present", projectOptions.length > 0, "project picker should render options");
        check("project_picker_option_ids_unique", new Set(projectOptions.map((node) => node.id).filter(Boolean)).size === projectOptions.length, "project options should have unique ids");
        check("project_picker_options_selected_state", projectOptions.every((node) => ["true", "false"].includes(node.getAttribute("aria-selected"))), "project options should expose selected state");
        pickerSearch.value = "zzzz-no-project";
        pickerSearch.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: "z" }));
        await waitFor(() => projectList.querySelectorAll('[role="option"]').length === 0, "project picker no-results state did not render");
        check("project_picker_no_results_status_visible", projectPickerStatus && projectPickerStatus.classList.contains("is-visible") && /일치하는 프로젝트가 없습니다/.test(projectPickerStatus.textContent), "project picker no-results status should be visible and announced");
        sendKey(pickerSearch, "Escape");
        await waitFor(() => projectPicker.hasAttribute("hidden"), "project picker did not close on escape");
        await waitFor(() => document.activeElement === projectSelect, "project picker did not restore focus to opener");
        check("project_picker_collapsed", projectSelect.getAttribute("aria-expanded") === "false", "project picker button should collapse");
        check("project_picker_close_clears_status", projectPickerStatus && !projectPickerStatus.textContent.trim() && !projectPickerStatus.classList.contains("is-visible"), "project picker status should clear after close");
        check("project_picker_body_lock_cleared", !document.body.classList.contains("project-picker-open"), "project picker should clear the background lock after close");
        pickerSearch.value = "late-hidden-input";
        pickerSearch.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: "l" }));
        await nextFrame();
        check("project_picker_hidden_input_ignored", projectPicker.hasAttribute("hidden") && projectList.querySelectorAll('[role="option"]').length === 0 && projectPickerStatus && !projectPickerStatus.textContent.trim() && !projectPickerStatus.classList.contains("is-visible"), "hidden project picker input events should not restore list or status");
        await waitFor(() => document.activeElement === projectSelect, "project picker focus changed after hidden input guard");
        check("project_picker_restores_focus", document.activeElement === projectSelect, "project picker should restore focus to opener");

        check("pm_project_icon_labels", hasActionLabel('[data-action="project-edit"]', "편집") && hasActionLabel('[data-action="project-delete"]', "삭제"), "project icon buttons should expose descriptive labels");
        check("pm_project_icon_titles", hasActionTitle('[data-action="project-edit"]', "편집") && hasActionTitle('[data-action="project-delete"]', "삭제"), "project icon tooltips should expose descriptive titles");
        check("portfolio_view_module_loaded", window.JooParkPortfolioView && window.JooParkPortfolioView.version === "joopark-portfolio-view/v1" && typeof window.JooParkPortfolioView.create === "function", "portfolio view runtime module should be loaded");
        const portfolioGrid = document.querySelector('#view-pm-portfolio .portfolio-grid[role="list"]');
        const portfolioCards = Array.from(document.querySelectorAll('#view-pm-portfolio .portfolio-card[role="listitem"]'));
        const portfolioOpenButtons = portfolioCards.map((card) => card.querySelector('[data-action="open-project"]')).filter(Boolean);
        check("portfolio_card_list_semantics",
          !!portfolioGrid &&
            (portfolioGrid.getAttribute("aria-label") || "").includes("포트폴리오") &&
            portfolioGrid.getAttribute("aria-setsize") === String(portfolioCards.length) &&
            portfolioCards.length > 0 &&
            portfolioOpenButtons.length === portfolioCards.length &&
            portfolioCards.every((card, index) => {
              const label = card.getAttribute("aria-label") || "";
              return card.getAttribute("aria-posinset") === String(index + 1) &&
                card.getAttribute("aria-setsize") === String(portfolioCards.length) &&
                label.includes("포트폴리오 항목") &&
                label.includes("진행률") &&
                label.includes("담당");
            }),
          "portfolio cards should expose list semantics and descriptive open labels");
        const projectCard = document.querySelector(".portfolio-card");
        const projectName = projectCard ? (projectCard.querySelector(".portfolio-name")?.textContent || "").trim() : "";
        projectCard?.querySelector('[data-action="open-project"]')?.click();
        await waitFor(() => document.getElementById("sheet").classList.contains("open"), "project sheet did not open for contextual action checks");
        const projectSheetActionText = Array.from(document.querySelectorAll("#sheet .sheet-action")).map((node) => node.textContent.trim()).join(" ");
        check("project_sheet_action_context_labels",
          Boolean(projectName &&
            projectSheetActionText.includes(projectName) &&
            projectSheetActionText.includes("편집") &&
            projectSheetActionText.includes("삭제") &&
            !projectSheetActionText.split(/\s{2,}/).includes("✎ 편집") &&
            !projectSheetActionText.split(/\s{2,}/).includes("✕ 삭제")),
          "project sheet actions should include the project name");
        document.querySelector('#sheet [data-action="close-sheet"]').click();
        await waitFor(() => !document.getElementById("sheet").classList.contains("open"), "project sheet did not close after contextual action checks");
        await navTo("pm-kanban");
        check("pm_issue_icon_labels", hasActionLabel('[data-action="issue-edit"]', "이슈 편집") && hasActionLabel('[data-action="issue-delete"]', "이슈 삭제"), "issue icon buttons should expose descriptive labels");
        check("pm_issue_icon_titles", hasActionTitle('[data-action="issue-edit"]', "이슈 편집") && hasActionTitle('[data-action="issue-delete"]', "이슈 삭제"), "issue icon tooltips should expose descriptive titles");
        check("pm_issue_move_labels", hasActionLabel('[data-action="issue-move"][data-status]', "이슈를"), "issue move icon buttons should expose destination labels");
        const kanbanLanes = Array.from(document.querySelectorAll('#view-pm-kanban .kanban-col[role="region"]'));
        const kanbanLists = Array.from(document.querySelectorAll('#view-pm-kanban .kanban-list[role="list"]'));
        const kanbanCards = Array.from(document.querySelectorAll('#view-pm-kanban .kanban-card-wrap[role="listitem"]'));
        check("kanban_view_module_loaded", window.JooParkKanbanView && window.JooParkKanbanView.version === "joopark-kanban-view/v1" && typeof window.JooParkKanbanView.create === "function", "kanban view runtime module should be loaded");
        check("kanban_lane_list_semantics",
          kanbanLanes.length >= 4 &&
            kanbanLists.length >= 4 &&
            kanbanCards.length > 0 &&
            kanbanLanes.every((lane) => (lane.getAttribute("aria-label") || "").includes("이슈")),
          "kanban lanes and cards should expose list semantics and lane labels");
        await navTo("pm-gantt");
        check("gantt_view_module_loaded", window.JooParkGanttView && window.JooParkGanttView.version === "joopark-gantt-view/v1" && typeof window.JooParkGanttView.create === "function", "gantt view runtime module should be loaded");
        const ganttSvg = document.querySelector('#view-pm-gantt .gantt-svg[role="group"]');
        const ganttSummary = document.getElementById("ganttChartSummary");
        const ganttSvgButtons = Array.from(document.querySelectorAll('#view-pm-gantt .gantt-svg [data-action="open-task"][role="button"]'));
        check("gantt_svg_group_labelled",
          !!ganttSvg &&
            !!ganttSummary &&
            ganttSvg.getAttribute("aria-labelledby") === "ganttChartSummary" &&
            (ganttSummary.textContent || "").includes("간트 차트"),
          "gantt SVG chart should expose a labelled group summary");
        check("gantt_svg_button_semantics",
          ganttSvgButtons.length > 0 &&
            ganttSvgButtons.every((button) => button.getAttribute("tabindex") === "0" && (button.getAttribute("aria-label") || "").includes("작업 열기:")),
          "gantt SVG bars and milestones should expose focusable button semantics and useful labels");
        check("pm_task_icon_labels", hasActionLabel('[data-action="task-edit"]', "작업 편집") && hasActionLabel('[data-action="task-delete"]', "작업 삭제"), "task icon buttons should expose descriptive labels");
        check("pm_task_icon_titles", hasActionTitle('[data-action="task-edit"]', "작업 편집") && hasActionTitle('[data-action="task-delete"]', "작업 삭제"), "task icon tooltips should expose descriptive titles");
        await navTo("pm-team");
        check("team_view_module_loaded", window.JooParkTeamView && window.JooParkTeamView.version === "joopark-team-view/v1" && typeof window.JooParkTeamView.create === "function", "team view runtime module should be loaded");
        const teamMatrix = document.querySelector('#view-pm-team .team-matrix[role="table"]');
        const teamRows = Array.from(document.querySelectorAll('#view-pm-team .team-matrix [role="row"]'));
        const teamColumnHeaders = Array.from(document.querySelectorAll('#view-pm-team .team-matrix [role="columnheader"]'));
        const teamRowHeaders = Array.from(document.querySelectorAll('#view-pm-team .team-matrix [role="rowheader"]'));
        const teamCells = Array.from(document.querySelectorAll('#view-pm-team .team-matrix [role="cell"]'));
        const teamAssignedCells = teamCells.filter((cell) => cell.classList.contains("is-assigned"));
        check("team_matrix_table_semantics",
          !!teamMatrix &&
            Number(teamMatrix.getAttribute("aria-rowcount")) >= 2 &&
            Number(teamMatrix.getAttribute("aria-colcount")) >= 2 &&
            teamRows.length >= 2 &&
            teamColumnHeaders.length > 1 &&
            teamRowHeaders.length > 0 &&
            teamCells.length > 0 &&
            teamAssignedCells.length > 0 &&
            teamCells.every((cell) => (cell.getAttribute("aria-label") || "").length > 0) &&
            teamAssignedCells.every((cell) => (cell.getAttribute("aria-label") || "").includes("열린 이슈")),
          "team resource matrix should expose table, row, header, and labelled assignment cell semantics");
        check("pm_member_icon_labels", hasActionLabel('[data-action="member-edit"]', "멤버 편집") && hasActionLabel('[data-action="member-delete"]', "멤버 삭제"), "member icon buttons should expose descriptive labels");
        check("pm_member_icon_titles", hasActionTitle('[data-action="member-edit"]', "멤버 편집") && hasActionTitle('[data-action="member-delete"]', "멤버 삭제"), "member icon tooltips should expose descriptive titles");
        check("db_catalog_module_loaded", window.JooParkDbCatalog && window.JooParkDbCatalog.version === "joopark-db-catalog/v1" && typeof window.JooParkDbCatalog.create === "function", "db catalog runtime module should be loaded");
        await navTo("dbm-instances");
        check("db_instance_icon_labels", hasActionLabel('[data-action="instance-edit"]', "인스턴스 편집") && hasActionLabel('[data-action="instance-delete"]', "인스턴스 삭제"), "instance icon buttons should expose descriptive labels");
        check("db_instance_icon_titles", hasActionTitle('[data-action="instance-edit"]', "인스턴스 편집") && hasActionTitle('[data-action="instance-delete"]', "인스턴스 삭제"), "instance icon tooltips should expose descriptive titles");
        await navTo("dbm-schema");
        check("db_table_icon_labels", hasActionLabel('[data-action="table-edit"]', "테이블 편집") && hasActionLabel('[data-action="table-delete"]', "테이블 삭제"), "table icon buttons should expose descriptive labels");
        check("db_table_icon_titles", hasActionTitle('[data-action="table-edit"]', "테이블 편집") && hasActionTitle('[data-action="table-delete"]', "테이블 삭제"), "table icon tooltips should expose descriptive titles");
        const firstTable = document.querySelector('[data-action="open-table"]');
        const tableName = firstTable ? (firstTable.querySelector("span")?.textContent || "").trim() : "";
        firstTable.click();
        await waitFor(() => document.getElementById("sheet").classList.contains("open"), "table sheet did not open for column label checks");
        check("db_column_icon_labels", hasActionLabel('[data-action="column-edit"]', "컬럼 편집") && hasActionLabel('[data-action="column-delete"]', "컬럼 삭제"), "column icon buttons should expose descriptive labels");
        check("db_column_icon_titles", hasActionTitle('[data-action="column-edit"]', "컬럼 편집") && hasActionTitle('[data-action="column-delete"]', "컬럼 삭제"), "column icon tooltips should expose descriptive titles");
        const tableSheetActionText = Array.from(document.querySelectorAll("#sheet .sheet-action")).map((node) => node.textContent.trim()).join(" ");
        check("table_sheet_action_context_labels",
          Boolean(tableName &&
            tableSheetActionText.includes(tableName) &&
            tableSheetActionText.includes("테이블 편집") &&
            tableSheetActionText.includes("테이블 삭제")),
          "table sheet actions should include the table name");
        document.querySelector('#sheet [data-action="close-sheet"]').click();
        await waitFor(() => !document.getElementById("sheet").classList.contains("open"), "table sheet did not close after column label checks");
        await navTo("dbm-queries");
        check("db_query_icon_labels", hasActionLabel('[data-action="query-edit"]', "쿼리 편집") && hasActionLabel('[data-action="query-delete"]', "쿼리 삭제"), "query icon buttons should expose descriptive labels");
        check("db_query_icon_titles", hasActionTitle('[data-action="query-edit"]', "쿼리 편집") && hasActionTitle('[data-action="query-delete"]', "쿼리 삭제"), "query icon tooltips should expose descriptive titles");
        await navTo("dbm-backups");
        check("db_migration_icon_labels", hasActionLabel('[data-action="migration-edit"]', "마이그레이션 편집") && hasActionLabel('[data-action="migration-delete"]', "마이그레이션 삭제"), "migration icon buttons should expose descriptive labels");
        check("db_migration_icon_titles", hasActionTitle('[data-action="migration-edit"]', "마이그레이션 편집") && hasActionTitle('[data-action="migration-delete"]', "마이그레이션 삭제"), "migration icon tooltips should expose descriptive titles");
        await navTo("todo");
        const todoRow = document.querySelector(".todo-row");
        const todoTitle = todoRow ? (todoRow.querySelector(".todo-title")?.textContent || "").trim() : "";
        const todoToggleLabel = actionLabel(todoRow, '[data-action="todo-toggle"]');
        const todoDeleteLabel = actionLabel(todoRow, '[data-action="todo-delete"]');
        check("personal_todo_action_labels",
          Boolean(todoTitle &&
            todoToggleLabel.includes(todoTitle) &&
            todoToggleLabel.includes("완료") &&
            todoDeleteLabel.includes(todoTitle) &&
            todoDeleteLabel.includes("삭제") &&
            !["완료 토글", "완료 처리", "완료 취소", "삭제"].includes(todoToggleLabel) &&
            todoDeleteLabel !== "삭제"),
          "todo action buttons should include the todo title in their accessible labels");
        await navTo("notes");
        const noteCard = document.querySelector(".note-card");
        const noteTitle = noteCard ? (noteCard.querySelector(".note-title")?.textContent || "").trim() : "";
        const notePin = noteCard ? noteCard.querySelector('[data-action="note-pin"]') : null;
        const notePinLabel = actionLabel(noteCard, '[data-action="note-pin"]');
        const noteDeleteLabel = actionLabel(noteCard, '[data-action="note-delete"]');
        check("personal_note_action_labels",
          Boolean(noteTitle &&
            notePin &&
            ["true", "false"].includes(notePin.getAttribute("aria-pressed")) &&
            notePinLabel.includes(noteTitle) &&
            notePinLabel.includes("고정") &&
            noteDeleteLabel.includes(noteTitle) &&
            noteDeleteLabel.includes("삭제") &&
            notePinLabel !== "고정" &&
            noteDeleteLabel !== "삭제"),
          "note action buttons should include the note title in their accessible labels");
        await navTo("habits");
        if (!document.querySelector(".habit-card")) {
          document.querySelector('[data-action="habit-add"]')?.click();
          await waitFor(() => document.getElementById("modal").classList.contains("open") && document.querySelector("#habitForm"), "habit add modal did not open");
          const habitNameInput = document.querySelector('#habitForm input[name="name"]');
          habitNameInput.value = "접근성 점검 습관";
          habitNameInput.dispatchEvent(new Event("input", { bubbles: true }));
          document.querySelector('#modal [data-action="modal-confirm"]').click();
          await waitFor(() => !document.getElementById("modal").classList.contains("open") && document.querySelector(".habit-card"), "habit card did not render after add");
        }
        const habitCard = document.querySelector(".habit-card");
        const habitName = habitCard ? (habitCard.querySelector(".habit-name")?.textContent || "").trim() : "";
        const habitEditLabel = actionLabel(habitCard, '[data-action="open-habit"]');
        const habitDeleteLabel = actionLabel(habitCard, '[data-action="habit-delete"]');
        const habitDay = habitCard ? habitCard.querySelector('[data-action="habit-toggle"]') : null;
        check("personal_habit_action_labels",
          Boolean(habitName &&
            habitEditLabel.includes(habitName) &&
            habitEditLabel.includes("습관 편집") &&
            habitDeleteLabel.includes(habitName) &&
            habitDeleteLabel.includes("습관 삭제") &&
            habitDay &&
            ["true", "false"].includes(habitDay.getAttribute("aria-pressed")) &&
            habitEditLabel !== "편집" &&
            habitDeleteLabel !== "삭제"),
          "habit action buttons should include the habit name in their accessible labels");
        await navTo("stats");
        const statsSparkCharts = Array.from(document.querySelectorAll('#view-stats [data-stats-chart="todo-trend"] [role="img"]'));
        check("stats_view_module_loaded",
          window.JooParkStatsView && window.JooParkStatsView.version === "joopark-stats-view/v1" && typeof window.JooParkStatsView.create === "function",
          "stats view runtime module should be loaded");
        check("stats_accessible_spark_charts",
          statsSparkCharts.length >= 2 &&
            statsSparkCharts.every((chart) => {
              const label = chart.getAttribute("aria-label") || "";
              return label.includes("최근 14일") && label.includes("총") && label.includes("최고");
            }),
          "stats trend spark charts should expose text alternatives with range and totals");
        await navTo("settings");
        check("settings_view_module_loaded",
          window.JooParkSettingsView && window.JooParkSettingsView.version === "joopark-settings-view/v1" && typeof window.JooParkSettingsView.create === "function",
          "settings view runtime module should be loaded");
        const settingsHandoffList = document.querySelector('#view-settings [data-settings-handoff] [role="list"]');
        const settingsHandoffItems = Array.from(document.querySelectorAll('#view-settings [data-settings-handoff] [role="listitem"]'));
        check("settings_handoff_list_semantics",
          !!settingsHandoffList &&
            (settingsHandoffList.getAttribute("aria-label") || "").includes("운영 handoff") &&
            settingsHandoffItems.length === 3 &&
            settingsHandoffItems.every((item) => item.querySelector('[data-action="copy-settings-handoff"]')),
          "settings handoff cards should expose list/listitem semantics and copy controls");
        const themeButtons = Array.from(document.querySelectorAll('#view-settings .theme-opt[aria-pressed]'));
        check("settings_theme_toggle_buttons",
          themeButtons.length === 2 &&
            themeButtons.some((button) => button.getAttribute("aria-pressed") === "true") &&
            themeButtons.some((button) => button.getAttribute("aria-pressed") === "false"),
          "settings theme toggle buttons should expose aria-pressed states");
        await navTo("system");
        check("system_status_view_module_loaded",
          window.JooParkSystemStatusView && window.JooParkSystemStatusView.version === "joopark-system-status-view/v1" && typeof window.JooParkSystemStatusView.create === "function",
          "system status view runtime module should be loaded");
        const systemStatus = document.querySelector('#view-system [data-system-status][data-system-status-module="joopark-system-status-view/v1"]');
        const systemSourceSnapshot = document.querySelector('#view-system [data-system-source-snapshots]');
        check("system_status_source_snapshot_region",
          !!systemStatus &&
            !!systemSourceSnapshot &&
            systemSourceSnapshot.getAttribute("role") === "status" &&
            systemSourceSnapshot.getAttribute("aria-live") === "polite" &&
            systemSourceSnapshot.querySelectorAll("[data-source-snapshot-row]").length >= 2,
          "system status should expose the source snapshot health region and rows");
        await navTo("pm-portfolio");
        const referenceToggle = document.querySelector('#view-pm-portfolio [data-action="toggle-reference-projects"]');
        if (referenceToggle && referenceToggle.dataset.referenceProjectsVisible !== "true") {
          referenceToggle.click();
          await waitFor(() => document.querySelector('#view-pm-portfolio [data-action="toggle-reference-projects"]')?.dataset.referenceProjectsVisible === "true", "reference project toggle did not enable candidates before prompt handoff check");
        }
        document.querySelector('#view-pm-portfolio [data-action="portfolio-filter"][data-filter="candidates"]')?.click();
        await waitFor(
          () => document.querySelector('#view-pm-portfolio .portfolio-card[data-source-kind="adoption-candidate"]'),
          "portfolio candidates did not render before prompt handoff check");
        await waitFor(
          () => document.querySelector('#view-pm-portfolio [data-action="show-project-prompt-handoff"]'),
          "portfolio prompt handoff CTA did not render after candidates became visible");
        const promptHandoffCta = document.querySelector('#view-pm-portfolio [data-action="show-project-prompt-handoff"]');
        check("portfolio_prompt_handoff_cta_available",
          !!promptHandoffCta,
          "portfolio prompt handoff CTA should be available after reference projects are visible");
        promptHandoffCta.click();
        await waitFor(
          () => document.querySelector('#view-pm-portfolio [data-review-result-status]'),
          "review result validator status did not render after prompt handoff CTA");
        const reviewResultStatus = document.querySelector('#view-pm-portfolio [data-review-result-status]');
        check("review_result_status_live_region",
          !!reviewResultStatus &&
            reviewResultStatus.getAttribute("role") === "status" &&
            reviewResultStatus.getAttribute("aria-live") === "polite" &&
            reviewResultStatus.getAttribute("aria-atomic") === "true",
          "review result validator status should be a polite live region");

        const sheet = document.getElementById("sheet");
        const sidebarAlert = document.querySelector('.sidebar [data-action="open-notifications"]');
        const bellAlert = document.querySelector('.bell[data-action="open-notifications"]');
        check("notification_sidebar_button", sidebarAlert && sidebarAlert.tagName === "BUTTON", "sidebar notification control should be a button, not a route link");
        check("notification_sidebar_controls_sheet", sidebarAlert && sidebarAlert.getAttribute("aria-controls") === "sheet", "sidebar notification button should control the sheet");
        check("notification_sidebar_dialog_popup", sidebarAlert && sidebarAlert.getAttribute("aria-haspopup") === "dialog", "sidebar notification button should announce a dialog popup");
        check("notification_bell_controls_sheet", bellAlert && bellAlert.getAttribute("aria-controls") === "sheet", "bell notification button should control the sheet");
        check("notification_initial_collapsed", sidebarAlert && bellAlert && sidebarAlert.getAttribute("aria-expanded") === "false" && bellAlert.getAttribute("aria-expanded") === "false", "notification triggers should start collapsed");
        sidebarAlert.focus();
        sidebarAlert.click();
        await waitFor(() => sheet.classList.contains("open"), "notification sheet did not open");
        const sheetClose = sheet.querySelector('.sheet-head [data-action="close-sheet"]');
        const sheetPanel = sheet.querySelector(".sheet-panel");
        check("notification_sheet_visible_to_a11y", sheet.getAttribute("aria-hidden") === "false", "notification sheet should not be aria-hidden when open");
        check("notification_sheet_modal_dialog", sheetPanel && sheetPanel.getAttribute("role") === "dialog" && sheetPanel.getAttribute("aria-modal") === "true" && sheetPanel.getAttribute("aria-labelledby") === "sheetTitle", "notification sheet panel should be a labelled modal dialog");
        check("notification_sheet_body_lock", document.body.classList.contains("sheet-open"), "notification sheet should lock the background scroll container while open");
        check("notification_triggers_expanded", sidebarAlert.getAttribute("aria-expanded") === "true" && bellAlert.getAttribute("aria-expanded") === "true", "notification triggers should expand while the sheet is open");
        check("notification_sheet_focuses_close", document.activeElement === sheetClose, "notification sheet should focus the close button");
        sheetClose.click();
        await waitFor(() => !sheet.classList.contains("open"), "notification sheet did not close");
        check("notification_triggers_collapsed", sidebarAlert.getAttribute("aria-expanded") === "false" && bellAlert.getAttribute("aria-expanded") === "false", "notification triggers should collapse after closing the sheet");
        check("notification_sheet_body_lock_cleared", !document.body.classList.contains("sheet-open"), "notification sheet should clear the background lock after closing");
        check("notification_sheet_restores_focus", document.activeElement === sidebarAlert, "notification sheet should restore focus to the opener");

        return { checks, failures };
      })();
    })()`);

    failures.push(...(domResult.failures || []));
    progress("dom-a11y-checked", { failures: domResult.failures.length });
    checks = domResult.checks || {};
  } finally {
    if (pageClient) pageClient.close();
    await terminateProcess(chrome);
    rmSync(tmpProfile, { recursive: true, force: true });
  }

  const appConsoleIssues = consoleIssues.filter((issue) => issue.text && !issue.text.includes("Autofill.enable"));
  const appNetworkIssues = networkIssues.filter((issue) => {
    if (String(issue.text || "").includes("net::ERR_ABORTED")) return false;
    return !isOptionalRootDevProvenance404(issue);
  });
  if (appConsoleIssues.length > 0) failures.push(`console issues: ${appConsoleIssues.length}`);
  if (appNetworkIssues.length > 0) failures.push(`network issues: ${appNetworkIssues.length}`);

  const summary = {
    baseUrl,
    status: failures.length === 0 ? "pass" : "fail",
    checks,
    consoleIssues: appConsoleIssues,
    networkIssues: appNetworkIssues,
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
