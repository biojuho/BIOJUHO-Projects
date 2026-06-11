#!/usr/bin/env node

import { spawn } from "node:child_process";
import { createServer } from "node:http";
import { existsSync, statSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { dirname, extname, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { withProductSmokeLock } from "./product-smoke-lock.mjs";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const host = "127.0.0.1";
const requestedPort = portOption(process.env.VERIFY_PRODUCT_PORT || process.env.PORT, 0);

function portOption(value, fallback = 0) {
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < 0 || parsed >= 65536) return fallback;
  return parsed;
}

const contentTypes = {
  ".css": "text/css; charset=utf-8",
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".md": "text/markdown; charset=utf-8",
  ".png": "image/png",
  ".svg": "image/svg+xml; charset=utf-8",
  ".webmanifest": "application/manifest+json; charset=utf-8",
};

const smokeScripts = [
  {
    key: "desktop",
    script: "scripts/smoke-chrome.mjs",
    timeoutMs: 180000,
    env: {
      SMOKE_RUNTIME_TIMEOUT_MS: "90000",
    },
  },
  {
    key: "mobile",
    script: "scripts/smoke-mobile.mjs",
    timeoutMs: 120000,
    env: {},
  },
  {
    key: "interactions",
    script: "scripts/smoke-interactions.mjs",
    timeoutMs: 180000,
    env: {
      SMOKE_RUNTIME_TIMEOUT_MS: "150000",
    },
  },
  {
    key: "accessibility",
    script: "scripts/smoke-a11y.mjs",
    timeoutMs: 120000,
    env: {},
  },
];

function progress(message) {
  console.error(`[verify-product-smoke] ${message}`);
}

function parseJsonOutput(stdout, fallbackStatus = "unknown") {
  try {
    return JSON.parse(stdout);
  } catch {
    return {
      status: fallbackStatus,
      output: stdout.trim(),
    };
  }
}

function writeJson(payload) {
  return new Promise((resolveWrite) => {
    process.stdout.write(`${JSON.stringify(payload, null, 2)}\n`, resolveWrite);
  });
}

function safeTarget(pathname) {
  let decoded;
  try {
    decoded = decodeURIComponent(pathname);
  } catch {
    return null;
  }

  const requestPath = decoded === "/" ? "index.html" : decoded.replace(/^\/+/, "");
  const target = resolve(root, requestPath);
  const allowedPrefix = `${root}${sep}`;
  if (target !== root && !target.startsWith(allowedPrefix)) return null;
  if (existsSync(target) && statSync(target).isDirectory()) return join(target, "index.html");
  return target;
}

function createProductServer() {
  const sockets = new Set();
  const server = createServer(async (request, response) => {
    const url = new URL(request.url || "/", `http://${request.headers.host || host}`);
    const target = safeTarget(url.pathname);

    if (!target) {
      response.writeHead(403, { "content-type": "text/plain; charset=utf-8" });
      response.end("Forbidden");
      return;
    }

    try {
      const body = await readFile(target);
      response.writeHead(200, {
        "cache-control": "no-store",
        "content-type": contentTypes[extname(target)] || "application/octet-stream",
      });
      response.end(body);
    } catch {
      response.writeHead(404, { "content-type": "text/plain; charset=utf-8" });
      response.end("Not found");
    }
  });

  server.keepAliveTimeout = 1000;
  server.on("connection", (socket) => {
    sockets.add(socket);
    socket.setTimeout(10000);
    socket.on("close", () => sockets.delete(socket));
  });
  server.destroyOpenSockets = () => {
    for (const socket of sockets) socket.destroy();
    sockets.clear();
  };
  return server;
}

function listen(server) {
  return new Promise((resolveListen, rejectListen) => {
    server.once("error", rejectListen);
    server.listen(requestedPort, host, () => {
      server.off("error", rejectListen);
      resolveListen(server.address().port);
    });
  });
}

function close(server) {
  return new Promise((resolveClose, rejectClose) => {
    let settled = false;
    const settle = (error) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      if (error) rejectClose(error);
      else resolveClose();
    };
    const forceStop = () => {
      if (typeof server.destroyOpenSockets === "function") server.destroyOpenSockets();
      if (typeof server.closeAllConnections === "function") server.closeAllConnections();
      if (typeof server.unref === "function") server.unref();
      settle();
    };
    const timer = setTimeout(() => {
      forceStop();
    }, 1000);
    try {
      server.close((error) => {
        settle(error);
      });
      if (typeof server.closeIdleConnections === "function") server.closeIdleConnections();
      if (typeof server.closeAllConnections === "function") server.closeAllConnections();
      if (typeof server.destroyOpenSockets === "function") server.destroyOpenSockets();
    } catch (error) {
      settle(error);
    }
  });
}

function runNodeScriptAsync(scriptPath, env = {}, timeoutMs = 120000) {
  return new Promise((resolveRun, rejectRun) => {
    const child = spawn(process.execPath, [join(root, scriptPath)], {
      cwd: root,
      env: { ...process.env, ...env },
      stdio: ["ignore", "pipe", "pipe"],
    });
    let stdout = "";
    let stderr = "";
    let didTimeout = false;

    const timer = setTimeout(() => {
      didTimeout = true;
      child.kill("SIGKILL");
    }, timeoutMs);
    const heartbeat = setInterval(() => {
      progress(`waiting for ${scriptPath}`);
    }, 5000);

    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    child.on("error", (error) => {
      clearTimeout(timer);
      clearInterval(heartbeat);
      error.step = scriptPath;
      error.stdout = stdout;
      error.stderr = stderr;
      rejectRun(error);
    });
    child.on("close", (code, signal) => {
      clearTimeout(timer);
      clearInterval(heartbeat);
      if (didTimeout) {
        const error = new Error(`${scriptPath} timed out after ${timeoutMs}ms`);
        error.step = scriptPath;
        error.stdout = stdout;
        error.stderr = stderr;
        rejectRun(error);
        return;
      }
      if (code !== 0) {
        const reported = parseJsonOutput(stdout, "fail");
        if (reported.status === "pass" && (!Array.isArray(reported.failures) || reported.failures.length === 0)) {
          resolveRun({ stdout, stderr, signal });
          return;
        }
        const error = new Error(`${scriptPath} failed with exit code ${code}${signal ? ` (${signal})` : ""}`);
        error.step = scriptPath;
        error.stdout = stdout;
        error.stderr = stderr;
        rejectRun(error);
        return;
      }
      resolveRun({ stdout, stderr });
    });
  });
}

function isRetryableRuntimeTimeout(error) {
  const details = [
    error && error.message,
    error && error.stdout,
    error && error.stderr,
  ].filter(Boolean).join("\n");
  return details.includes("Timed out waiting for Runtime.evaluate") ||
    details.includes("route not ready");
}

async function runRetryableBrowserScript(smoke, baseUrl, retries = 1) {
  const attempts = [];
  const env = {
    BASE_URL: baseUrl,
    SMOKE_PROGRESS: process.env.SMOKE_PROGRESS || "1",
    ...smoke.env,
  };
  for (let attempt = 0; attempt <= retries; attempt += 1) {
    try {
      const result = await runNodeScriptAsync(smoke.script, env, smoke.timeoutMs);
      return { ...result, attempts };
    } catch (error) {
      const retryable = isRetryableRuntimeTimeout(error);
      attempts.push({
        attempt: attempt + 1,
        retryable,
        message: error.message,
      });
      if (!retryable || attempt === retries) {
        error.attempts = attempts;
        throw error;
      }
    }
  }
  throw new Error(`${smoke.script} retry loop exited unexpectedly`);
}

function summarizeSmokeResult(key, result, attempts) {
  if (key === "desktop") {
    return {
      status: result.status,
      routeCount: result.routeCount,
      viewport: result.viewport,
      layoutIssues: result.layoutIssues,
      consoleIssues: result.consoleIssues,
      networkIssues: result.networkIssues,
      failures: result.failures,
      retryAttempts: attempts,
    };
  }
  if (key === "mobile") {
    return {
      status: result.status,
      routeCount: result.routeCount,
      viewport: result.viewport,
      layoutIssues: result.layoutIssues,
      consoleIssues: result.consoleIssues,
      networkIssues: result.networkIssues,
      failures: result.failures,
      retryAttempts: attempts,
    };
  }
  if (key === "interactions") {
    return {
      status: result.status,
      stepCount: result.steps ? result.steps.length : 0,
      persistedChecks: result.persistedChecks,
      consoleIssues: result.consoleIssues,
      networkIssues: result.networkIssues,
      failures: result.failures,
      retryAttempts: attempts,
    };
  }
  return {
    status: result.status,
    checks: result.checks,
    consoleIssues: result.consoleIssues,
    networkIssues: result.networkIssues,
    failures: result.failures,
    retryAttempts: attempts,
  };
}

async function main() {
  const server = createProductServer();
  progress("starting source smoke server");
  const port = await listen(server);
  const baseUrl = `http://${host}:${port}`;
  const results = {};

  try {
    for (const smoke of smokeScripts) {
      progress(`running ${smoke.script}`);
      const run = await runRetryableBrowserScript(smoke, baseUrl);
      const parsed = parseJsonOutput(run.stdout, "fail");
      if (run.attempts.length > 0) parsed.retryAttempts = run.attempts;
      if (parsed.status !== "pass") {
        throw Object.assign(new Error(`${smoke.script} reported ${parsed.status}`), {
          step: smoke.script,
          stdout: JSON.stringify(parsed, null, 2),
          stderr: run.stderr,
        });
      }
      results[smoke.key] = summarizeSmokeResult(smoke.key, parsed, run.attempts);
    }
  } finally {
    progress("stopping source smoke server");
    await close(server);
  }

  await writeJson({
    status: "pass",
    baseUrl,
    root: relative(process.cwd(), root) || ".",
    scripts: Object.fromEntries(smokeScripts.map((smoke) => [smoke.key, smoke.script])),
    results,
  });
}

async function runCli() {
  try {
    await withProductSmokeLock({ root, label: "verify:product", progress }, main);
    process.exit(0);
  } catch (error) {
    const payload = {
      status: "fail",
      step: error.step || "scripts/verify-product-smoke.mjs",
      message: error.message,
      attempts: error.attempts || [],
      stdout: error.stdout || "",
      stderr: error.stderr || "",
    };
    process.stdout.write(`${JSON.stringify(payload, null, 2)}\n`, () => process.exit(1));
  }
}

runCli();
