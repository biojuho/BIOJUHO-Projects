#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import { spawn } from "node:child_process";
import { chromium } from "playwright";

const DEFAULT_SELECTORS_PATH = path.join(process.cwd(), "skills", "x-article-publisher", "config", "selectors.json");
const DEFAULT_CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const DEFAULT_EDGE = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";

function parseArgs(argv) {
  const args = {
    profileDir: "Default",
    userDataDir: path.join(process.env.LOCALAPPDATA || "", "Google", "Chrome", "User Data"),
    selectorsPath: DEFAULT_SELECTORS_PATH,
    output: path.join(process.cwd(), "artifacts", "live-smoke-test.json"),
    screenshot: path.join(process.cwd(), "artifacts", "live-smoke-test.png"),
    log: path.join(process.cwd(), "artifacts", "live-smoke-test.log"),
    browserPath: DEFAULT_CHROME,
    browserLabel: "chrome",
    remoteDebugPort: 9222,
  };

  for (let i = 2; i < argv.length; i += 1) {
    const arg = argv[i];
    const next = argv[i + 1];
    if (arg === "--profile-dir" && next) {
      args.profileDir = next;
      i += 1;
    } else if (arg === "--user-data-dir" && next) {
      args.userDataDir = next;
      i += 1;
    } else if (arg === "--selectors" && next) {
      args.selectorsPath = next;
      i += 1;
    } else if (arg === "--output" && next) {
      args.output = next;
      i += 1;
    } else if (arg === "--screenshot" && next) {
      args.screenshot = next;
      i += 1;
    } else if (arg === "--log" && next) {
      args.log = next;
      i += 1;
    } else if (arg === "--browser" && next) {
      args.browserLabel = next;
      args.browserPath = next === "edge" ? DEFAULT_EDGE : DEFAULT_CHROME;
      args.userDataDir =
        next === "edge"
          ? path.join(process.env.LOCALAPPDATA || "", "Microsoft", "Edge", "User Data")
          : path.join(process.env.LOCALAPPDATA || "", "Google", "Chrome", "User Data");
      i += 1;
    } else if (arg === "--browser-path" && next) {
      args.browserPath = next;
      i += 1;
    } else if (arg === "--port" && next) {
      args.remoteDebugPort = Number(next);
      i += 1;
    }
  }
  return args;
}

function ensureDir(filePath) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
}

function appendLog(filePath, message) {
  ensureDir(filePath);
  fs.appendFileSync(filePath, `[${new Date().toISOString()}] ${message}\n`, "utf-8");
}

function writeReport(filePath, report) {
  ensureDir(filePath);
  fs.writeFileSync(filePath, JSON.stringify(report, null, 2), "utf-8");
}

function loadSelectors(selectorsPath) {
  return JSON.parse(fs.readFileSync(selectorsPath, "utf-8"));
}

async function visibleCount(page, selectorSpec) {
  try {
    if (selectorSpec.type === "placeholder") {
      return await page.getByPlaceholder(selectorSpec.value, { exact: false }).count();
    }
    if (selectorSpec.type === "text") {
      return await page.getByText(selectorSpec.value, { exact: false }).count();
    }
    if (selectorSpec.type === "menuitem") {
      return await page.getByRole("menuitem", { name: selectorSpec.value, exact: false }).count();
    }
    if (selectorSpec.type === "role") {
      return await page.getByRole(selectorSpec.value, { name: selectorSpec.name || undefined }).count();
    }
    if (selectorSpec.type === "css") {
      return await page.locator(selectorSpec.value).count();
    }
  } catch {
    return 0;
  }
  return 0;
}

async function collectVisibleButtons(page) {
  return await page.locator("button:visible").evaluateAll((buttons) =>
    buttons
      .map((button) => ({
        text: button.innerText?.trim() || "",
        ariaLabel: button.getAttribute("aria-label") || "",
        title: button.getAttribute("title") || "",
      }))
      .filter((item) => item.text || item.ariaLabel || item.title)
      .slice(0, 60),
  );
}

async function collectTextboxMeta(page) {
  return await page.locator("[contenteditable='true'], textarea, input").evaluateAll((nodes) =>
    nodes
      .map((node) => ({
        tag: node.tagName.toLowerCase(),
        ariaLabel: node.getAttribute("aria-label") || "",
        placeholder: node.getAttribute("placeholder") || "",
        role: node.getAttribute("role") || "",
        text: node.textContent?.trim()?.slice(0, 80) || "",
      }))
      .slice(0, 60),
  );
}

async function collectPageTextSample(page) {
  const bodyText = await page.locator("body").innerText().catch(() => "");
  return bodyText
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .slice(0, 40);
}

async function waitForDebugger(port, logPath) {
  const endpoint = `http://127.0.0.1:${port}/json/version`;
  for (let attempt = 0; attempt < 40; attempt += 1) {
    try {
      const response = await fetch(endpoint);
      if (response.ok) {
        appendLog(logPath, `remote debugger ready on attempt ${attempt + 1}`);
        return true;
      }
    } catch {
      // ignore and retry
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  appendLog(logPath, "remote debugger did not start in time");
  return false;
}

async function killProcessTree(pid, logPath) {
  appendLog(logPath, `killing browser pid=${pid}`);
  await new Promise((resolve) => {
    const killer = spawn("taskkill", ["/pid", String(pid), "/t", "/f"], { stdio: "ignore" });
    killer.on("exit", () => resolve());
    killer.on("error", () => resolve());
  });
}

async function main() {
  const args = parseArgs(process.argv);
  ensureDir(args.log);
  fs.writeFileSync(args.log, "", "utf-8");
  const selectors = loadSelectors(args.selectorsPath);
  const report = {
    timestamp: new Date().toISOString(),
    target: "https://x.com/compose/articles",
    browserLabel: args.browserLabel,
    browserPath: args.browserPath,
    profileDir: args.profileDir,
    userDataDir: args.userDataDir,
    results: {},
  };

  appendLog(args.log, `starting browser ${args.browserPath}`);
  const browserProcess = spawn(
    args.browserPath,
    [
      `--remote-debugging-port=${args.remoteDebugPort}`,
      `--user-data-dir=${args.userDataDir}`,
      `--profile-directory=${args.profileDir}`,
      "--no-first-run",
      "--no-default-browser-check",
      "about:blank",
    ],
    {
      detached: false,
      stdio: "ignore",
    },
  );
  report.results.browserPid = browserProcess.pid;
  writeReport(args.output, report);

  let browser;
  try {
    const ready = await waitForDebugger(args.remoteDebugPort, args.log);
    if (!ready) {
      throw new Error("Chrome remote debugging endpoint was not reachable.");
    }

    appendLog(args.log, "connecting over CDP");
    browser = await chromium.connectOverCDP(`http://127.0.0.1:${args.remoteDebugPort}`);
    const context = browser.contexts()[0] || (await browser.newContext());
    const page = context.pages()[0] || (await context.newPage());

    appendLog(args.log, "navigating to compose/articles");
    await page.goto("https://x.com/compose/articles", { waitUntil: "domcontentloaded", timeout: 45000 });
    await page.waitForTimeout(5000);

    report.results.url = page.url();
    report.results.title = await page.title();
    report.results.loggedIn = !/login|signin|flow\/login/i.test(page.url());
    report.results.pageTextSample = await collectPageTextSample(page);
    report.results.visibleButtons = await collectVisibleButtons(page);
    report.results.textboxes = await collectTextboxMeta(page);
    report.results.selectorChecks = {};
    writeReport(args.output, report);

    for (const [groupName, entries] of Object.entries(selectors)) {
      if (!entries || typeof entries !== "object" || Array.isArray(entries)) {
        continue;
      }
      report.results.selectorChecks[groupName] = {};
      for (const [selectorName, selectorSpecs] of Object.entries(entries)) {
        if (!Array.isArray(selectorSpecs)) {
          continue;
        }
        const counts = [];
        for (const spec of selectorSpecs) {
          counts.push({ spec, count: await visibleCount(page, spec) });
        }
        report.results.selectorChecks[groupName][selectorName] = counts;
      }
    }
    writeReport(args.output, report);

    const createCandidates = selectors.actions?.create_article || [];
    for (const candidate of createCandidates) {
      let locator = null;
      if (candidate.type === "text") {
        locator = page.getByText(candidate.value, { exact: false });
      } else if (candidate.type === "css") {
        locator = page.locator(candidate.value);
      }
      if (locator && (await locator.count()) > 0) {
        appendLog(args.log, `clicking create candidate=${candidate.value}`);
        await locator.first().click({ timeout: 10000 });
        await page.waitForTimeout(4000);
        report.results.afterCreateUrl = page.url();
        report.results.afterCreateButtons = await collectVisibleButtons(page);
        report.results.afterCreateTextboxes = await collectTextboxMeta(page);
        writeReport(args.output, report);
        break;
      }
    }

    await page.screenshot({ path: args.screenshot, fullPage: true });
    writeReport(args.output, report);
    console.log(JSON.stringify(report, null, 2));
  } catch (error) {
    report.results.error = String(error);
    writeReport(args.output, report);
    appendLog(args.log, `error=${String(error)}`);
    throw error;
  } finally {
    if (browser) {
      try {
        await browser.close();
      } catch {
        // ignore
      }
    }
    await killProcessTree(browserProcess.pid, args.log);
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
