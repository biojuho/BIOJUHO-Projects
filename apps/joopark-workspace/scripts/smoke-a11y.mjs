#!/usr/bin/env node

import { spawn } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const runtimeEnv = process["env"];
const chromePath = runtimeEnv.CHROME_PATH || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const baseUrl = (runtimeEnv.BASE_URL || "http://127.0.0.1:5178").replace(/\/+$/, "");
const tmpProfile = mkdtempSync(join(tmpdir(), "joopark-a11y-smoke-"));
const progressEnabled = runtimeEnv.SMOKE_PROGRESS === "1";

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
        else if (Date.now() - started > 6000) reject(new Error("home route not ready"));
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

      return (async () => {
        const palette = document.getElementById("palette");
        const paletteInput = document.getElementById("paletteInput");
        const paletteResults = document.getElementById("paletteResults");
        const cmdButton = document.querySelector('[data-action="open-palette"]');
        check("palette_initial_hidden", palette && palette.getAttribute("aria-hidden") === "true", "palette should start hidden");
        check("palette_input_combobox", paletteInput && paletteInput.getAttribute("role") === "combobox", "palette input should be a combobox");
        check("palette_input_controls_results", paletteInput && paletteInput.getAttribute("aria-controls") === "paletteResults", "palette input should control the results list");
        check("palette_results_listbox", paletteResults && paletteResults.getAttribute("role") === "listbox", "palette results should be a listbox");
        check("command_button_exists", Boolean(cmdButton), "command palette button is missing");

        cmdButton.focus();
        cmdButton.click();
        await waitFor(() => palette.classList.contains("open"), "palette did not open");
        check("palette_open_expanded", paletteInput.getAttribute("aria-expanded") === "true", "palette combobox should be expanded when open");
        check("palette_focuses_input", document.activeElement === paletteInput, "palette did not focus the input");
        let selected = paletteResults.querySelector('[role="option"][aria-selected="true"]');
        check("palette_selected_option_exists", Boolean(selected && selected.id), "palette selected option should have an id");
        check("palette_active_descendant_matches", paletteInput.getAttribute("aria-activedescendant") === selected.id, "palette active descendant does not match selected option");

        sendKey(paletteInput, "ArrowDown");
        await nextFrame();
        selected = paletteResults.querySelector('[role="option"][aria-selected="true"]');
        check("palette_arrow_updates_active_descendant", selected && paletteInput.getAttribute("aria-activedescendant") === selected.id, "palette arrow navigation did not update active descendant");

        sendKey(paletteInput, "Escape");
        await waitFor(() => !palette.classList.contains("open"), "palette did not close");
        check("palette_close_collapsed", paletteInput.getAttribute("aria-expanded") === "false", "palette combobox should be collapsed after close");
        check("palette_close_clears_active_descendant", !paletteInput.hasAttribute("aria-activedescendant"), "palette active descendant should clear after close");
        check("palette_restores_focus", document.activeElement === cmdButton, "palette did not restore focus to opener");

        document.dispatchEvent(new KeyboardEvent("keydown", { key: "?", bubbles: true, cancelable: true }));
        const modal = document.getElementById("modal");
        await waitFor(() => modal.classList.contains("open"), "shortcut help modal did not open");
        const modalClose = modal.querySelector('.modal-close[data-action="close-modal"]');
        check("modal_visible_to_a11y", modal.getAttribute("aria-hidden") === "false", "open modal should not be aria-hidden");
        check("informational_modal_focuses_close", document.activeElement === modalClose, "informational modal should focus the close button");
        modalClose.click();
        await waitFor(() => !modal.classList.contains("open"), "shortcut help modal did not close");
        location.hash = "pm-portfolio";
        await waitFor(() => document.body.dataset.view === "pm-portfolio", "pm portfolio route did not open");

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
        const projectOptions = Array.from(projectList ? projectList.querySelectorAll('[role="option"]') : []);
        check("project_picker_expanded", projectSelect.getAttribute("aria-expanded") === "true", "project picker button should expand");
        check("project_picker_focuses_search", document.activeElement === pickerSearch, "project picker did not focus search");
        check("project_picker_search_controls_list", pickerSearch && pickerSearch.getAttribute("aria-controls") === "projectPickerList", "project picker search should control list");
        check("project_picker_listbox", projectList && projectList.getAttribute("role") === "listbox", "project picker options should be inside a listbox");
        check("project_picker_options_present", projectOptions.length > 0, "project picker should render options");
        check("project_picker_option_ids_unique", new Set(projectOptions.map((node) => node.id).filter(Boolean)).size === projectOptions.length, "project options should have unique ids");
        check("project_picker_options_selected_state", projectOptions.every((node) => ["true", "false"].includes(node.getAttribute("aria-selected"))), "project options should expose selected state");
        sendKey(pickerSearch, "Escape");
        await waitFor(() => projectPicker.hasAttribute("hidden"), "project picker did not close on escape");
        await waitFor(() => document.activeElement === projectSelect, "project picker did not restore focus to opener");
        check("project_picker_collapsed", projectSelect.getAttribute("aria-expanded") === "false", "project picker button should collapse");
        check("project_picker_restores_focus", document.activeElement === projectSelect, "project picker should restore focus to opener");

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
  const appNetworkIssues = networkIssues.filter((issue) => !String(issue.text || "").includes("net::ERR_ABORTED"));
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
