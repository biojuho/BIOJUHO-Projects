#!/usr/bin/env node

import { spawn, spawnSync } from "node:child_process";
import { createServer } from "node:http";
import {
  existsSync,
  readFileSync,
  statSync,
} from "node:fs";
import { readFile } from "node:fs/promises";
import {
  dirname,
  extname,
  join,
  relative,
  resolve,
  sep,
} from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const releaseDir = process.env.RELEASE_OUT_DIR
  ? resolve(root, process.env.RELEASE_OUT_DIR)
  : join(root, "dist", "release");
const host = "127.0.0.1";
const requestedPort = Number(process.env.RELEASE_SMOKE_PORT || process.env.PORT || 0);
const shouldPackage = process.env.RELEASE_SMOKE_SKIP_PACKAGE !== "1";

const contentTypes = {
  ".css": "text/css; charset=utf-8",
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".md": "text/markdown; charset=utf-8",
  ".svg": "image/svg+xml; charset=utf-8",
};

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

function runNodeScript(scriptPath, scriptArgs = [], env = {}, timeoutMs = 90000) {
  const result = spawnSync(process.execPath, [join(root, scriptPath), ...scriptArgs], {
    cwd: root,
    env: { ...process.env, ...env },
    encoding: "utf-8",
    killSignal: "SIGKILL",
    timeout: timeoutMs,
  });

  if (result.error) {
    const error = new Error(`${scriptPath} failed: ${result.error.message}`);
    error.step = scriptPath;
    error.stdout = result.stdout || "";
    error.stderr = result.stderr || "";
    throw error;
  }

  if (result.status !== 0) {
    const error = new Error(`${scriptPath} failed with exit code ${result.status}`);
    error.step = scriptPath;
    error.stdout = result.stdout || "";
    error.stderr = result.stderr || "";
    throw error;
  }

  return {
    stdout: result.stdout || "",
    stderr: result.stderr || "",
  };
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

    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    child.on("error", (error) => {
      clearTimeout(timer);
      error.step = scriptPath;
      error.stdout = stdout;
      error.stderr = stderr;
      rejectRun(error);
    });
    child.on("close", (code, signal) => {
      clearTimeout(timer);
      if (didTimeout) {
        const error = new Error(`${scriptPath} timed out after ${timeoutMs}ms`);
        error.step = scriptPath;
        error.stdout = stdout;
        error.stderr = stderr;
        rejectRun(error);
        return;
      }
      if (code !== 0) {
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
  return details.includes("Timed out waiting for Runtime.evaluate");
}

async function runRetryableBrowserScript(scriptPath, env = {}, timeoutMs = 120000, retries = 1) {
  const attempts = [];
  for (let attempt = 0; attempt <= retries; attempt += 1) {
    try {
      const result = await runNodeScriptAsync(scriptPath, env, timeoutMs);
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
  throw new Error(`${scriptPath} retry loop exited unexpectedly`);
}

function safeTarget(pathname) {
  let decoded;
  try {
    decoded = decodeURIComponent(pathname);
  } catch {
    return null;
  }

  const requestPath = decoded === "/" ? "index.html" : decoded.replace(/^\/+/, "");
  const target = resolve(releaseDir, requestPath);
  const allowedPrefix = `${releaseDir}${sep}`;
  if (target !== releaseDir && !target.startsWith(allowedPrefix)) return null;
  if (existsSync(target) && statSync(target).isDirectory()) return join(target, "index.html");
  return target;
}

function readReleaseHeaderRules() {
  const path = join(releaseDir, "_headers");
  if (!existsSync(path)) return [];
  const rules = [];
  let current = null;
  for (const line of readFileSync(path, "utf-8").split(/\r?\n/)) {
    if (!line.trim() || line.trimStart().startsWith("#")) continue;
    if (/^\s/.test(line)) {
      if (!current) continue;
      const index = line.indexOf(":");
      if (index < 0) continue;
      current.headers.push({
        name: line.slice(0, index).trim(),
        value: line.slice(index + 1).trim(),
      });
      continue;
    }
    current = { pattern: line.trim(), headers: [] };
    rules.push(current);
  }
  return rules;
}

function readReleaseRedirectRules() {
  const path = join(releaseDir, "_redirects");
  if (!existsSync(path)) return [];
  const rules = [];
  for (const line of readFileSync(path, "utf-8").split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const [from, to, status = "301"] = trimmed.split(/\s+/);
    if (!from || !to) continue;
    rules.push({ from, to, status: Number(status) || 301 });
  }
  return rules;
}

function headerRuleMatches(pattern, pathname) {
  if (pattern === "/*") return true;
  if (pattern.endsWith("*")) return pathname.startsWith(pattern.slice(0, -1));
  return pathname === pattern;
}

function headersForPath(pathname, rules) {
  const headers = {};
  for (const rule of rules) {
    if (!headerRuleMatches(rule.pattern, pathname)) continue;
    for (const header of rule.headers) headers[header.name] = header.value;
  }
  return headers;
}

function redirectRuleMatches(pattern, pathname) {
  if (pattern === "/*") return true;
  if (pattern.endsWith("*")) return pathname.startsWith(pattern.slice(0, -1));
  return pathname === pattern;
}

function redirectForPath(pathname, rules) {
  return rules.find((rule) => redirectRuleMatches(rule.from, pathname)) || null;
}

function mergeHeaders(base, custom) {
  const headers = { ...base };
  for (const [key, value] of Object.entries(custom)) {
    for (const existing of Object.keys(headers)) {
      if (existing.toLowerCase() === key.toLowerCase()) delete headers[existing];
    }
    headers[key] = value;
  }
  return headers;
}

function createReleaseServer() {
  const sockets = new Set();
  const releaseHeaderRules = readReleaseHeaderRules();
  const releaseRedirectRules = readReleaseRedirectRules();
  const server = createServer(async (request, response) => {
    const url = new URL(request.url || "/", `http://${request.headers.host || host}`);
    let target = safeTarget(url.pathname);

    if (!target) {
      response.writeHead(403, { "content-type": "text/plain; charset=utf-8" });
      response.end("Forbidden");
      return;
    }

    try {
      const body = await readFile(target);
      response.writeHead(200, mergeHeaders({
        "cache-control": "no-store",
        "content-type": contentTypes[extname(target)] || "application/octet-stream",
      }, headersForPath(url.pathname, releaseHeaderRules)));
      response.end(body);
    } catch {
      const redirectRule = redirectForPath(url.pathname, releaseRedirectRules);
      const redirectTarget = redirectRule ? safeTarget(redirectRule.to) : null;
      if (redirectRule?.status === 200 && redirectTarget) {
        try {
          target = redirectTarget;
          const body = await readFile(target);
          response.writeHead(200, mergeHeaders({
            "cache-control": "no-store",
            "content-type": contentTypes[extname(target)] || "application/octet-stream",
          }, headersForPath(redirectRule.to, releaseHeaderRules)));
          response.end(body);
          return;
        } catch {
          // Fall through to the 404 response below.
        }
      }
      if (redirectRule && redirectRule.status >= 300 && redirectRule.status < 400) {
        response.writeHead(redirectRule.status, {
          "content-type": "text/plain; charset=utf-8",
          location: redirectRule.to,
        });
        response.end("Redirect");
        return;
      }
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

async function fetchHeaderMap(url) {
  const response = await fetch(url);
  const headers = {};
  for (const [key, value] of response.headers.entries()) headers[key.toLowerCase()] = value;
  return { status: response.status, headers };
}

async function smokeReleaseHeaders(baseUrl) {
  const root = await fetchHeaderMap(`${baseUrl}/`);
  const app = await fetchHeaderMap(`${baseUrl}/app.js`);
  const vendor = await fetchHeaderMap(`${baseUrl}/vendor/fuse.min.js`);
  const headerChecks = {
    root_x_content_type_options: root.headers["x-content-type-options"] === "nosniff",
    root_frame_options: root.headers["x-frame-options"] === "DENY",
    root_referrer_policy: root.headers["referrer-policy"] === "strict-origin-when-cross-origin",
    root_permissions_policy: root.headers["permissions-policy"] === "camera=(), microphone=(), geolocation=()",
    app_cache_no_cache: app.headers["cache-control"] === "no-cache",
    vendor_cache_immutable: vendor.headers["cache-control"] === "public, max-age=31536000, immutable",
  };
  return {
    status: Object.values(headerChecks).every(Boolean) ? "pass" : "fail",
    checks: headerChecks,
    responses: {
      root: root.status,
      app: app.status,
      vendor: vendor.status,
    },
  };
}

async function fetchTextResponse(url) {
  const response = await fetch(url, { redirect: "manual" });
  return {
    status: response.status,
    headers: Object.fromEntries([...response.headers.entries()].map(([key, value]) => [key.toLowerCase(), value])),
    body: await response.text(),
  };
}

async function smokeReleaseFallbacks(baseUrl) {
  const root = await fetchTextResponse(`${baseUrl}/`);
  const direct = await fetchTextResponse(`${baseUrl}/workspace/direct-link-check`);
  const notFound = await fetchTextResponse(`${baseUrl}/404.html`);
  const fallbackChecks = {
    direct_path_rewrites_to_index: direct.status === 200 && direct.body === root.body,
    direct_path_keeps_url_without_redirect: !direct.headers.location,
    custom_404_matches_index: notFound.status === 200 && notFound.body === root.body,
    fallback_html_content_type: String(direct.headers["content-type"] || "").startsWith("text/html"),
  };
  return {
    status: Object.values(fallbackChecks).every(Boolean) ? "pass" : "fail",
    checks: fallbackChecks,
    responses: {
      root: root.status,
      direct: direct.status,
      notFound: notFound.status,
    },
  };
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
    const timer = setTimeout(() => {
      if (typeof server.destroyOpenSockets === "function") server.destroyOpenSockets();
      resolveClose();
    }, 1000);
    server.close((error) => {
      clearTimeout(timer);
      if (error) rejectClose(error);
      else resolveClose();
    });
    if (typeof server.closeIdleConnections === "function") server.closeIdleConnections();
    if (typeof server.closeAllConnections === "function") server.closeAllConnections();
    if (typeof server.destroyOpenSockets === "function") server.destroyOpenSockets();
  });
}

async function main() {
  const packageResult = shouldPackage
    ? parseJsonOutput(runNodeScript("scripts/package-release.mjs", [], {
      RELEASE_OUT_DIR: releaseDir,
    }).stdout, "fail")
    : { status: "skipped" };
  if (packageResult.status !== "pass" && packageResult.status !== "skipped") {
    throw Object.assign(new Error("release package generation failed"), {
      step: "scripts/package-release.mjs",
      stdout: JSON.stringify(packageResult, null, 2),
      stderr: "",
    });
  }

  const verifyResult = parseJsonOutput(
    runNodeScript("scripts/verify-release.mjs", [releaseDir], {}, 90000).stdout,
    "fail",
  );
  if (verifyResult.status !== "pass") {
    throw Object.assign(new Error("release manifest verification failed"), {
      step: "scripts/verify-release.mjs",
      stdout: JSON.stringify(verifyResult, null, 2),
      stderr: "",
    });
  }

  const server = createReleaseServer();
  const port = await listen(server);
  const baseUrl = `http://${host}:${port}`;

  let smokeResult;
  let mobileResult;
  let interactionResult;
  let accessibilityResult;
  let headerResult;
  let fallbackResult;
  try {
    headerResult = await smokeReleaseHeaders(baseUrl);
    fallbackResult = await smokeReleaseFallbacks(baseUrl);
    const smokeRun = await runRetryableBrowserScript("scripts/smoke-chrome.mjs", {
      BASE_URL: baseUrl,
      SMOKE_PROGRESS: "1",
      SMOKE_RUNTIME_TIMEOUT_MS: "90000",
    }, 180000);
    smokeResult = parseJsonOutput(smokeRun.stdout, "fail");
    if (smokeRun.attempts.length > 0) smokeResult.retryAttempts = smokeRun.attempts;
    const mobileRun = await runRetryableBrowserScript("scripts/smoke-mobile.mjs", {
      BASE_URL: baseUrl,
      SMOKE_PROGRESS: "1",
    }, 120000);
    mobileResult = parseJsonOutput(mobileRun.stdout, "fail");
    if (mobileRun.attempts.length > 0) mobileResult.retryAttempts = mobileRun.attempts;
    const interactionRun = await runRetryableBrowserScript("scripts/smoke-interactions.mjs", {
      BASE_URL: baseUrl,
      SMOKE_PROGRESS: "1",
      SMOKE_RUNTIME_TIMEOUT_MS: "150000",
    }, 180000);
    interactionResult = parseJsonOutput(interactionRun.stdout, "fail");
    if (interactionRun.attempts.length > 0) interactionResult.retryAttempts = interactionRun.attempts;
    const accessibilityRun = await runRetryableBrowserScript("scripts/smoke-a11y.mjs", {
      BASE_URL: baseUrl,
      SMOKE_PROGRESS: "1",
    }, 120000);
    accessibilityResult = parseJsonOutput(accessibilityRun.stdout, "fail");
    if (accessibilityRun.attempts.length > 0) accessibilityResult.retryAttempts = accessibilityRun.attempts;
  } finally {
    await close(server);
  }

  if (headerResult.status !== "pass") {
    throw Object.assign(new Error("release header smoke failed"), {
      step: "scripts/smoke-release.mjs:headers",
      stdout: JSON.stringify(headerResult, null, 2),
      stderr: "",
    });
  }
  if (fallbackResult.status !== "pass") {
    throw Object.assign(new Error("release fallback smoke failed"), {
      step: "scripts/smoke-release.mjs:fallbacks",
      stdout: JSON.stringify(fallbackResult, null, 2),
      stderr: "",
    });
  }
  if (smokeResult.status !== "pass") {
    throw Object.assign(new Error("release browser smoke failed"), {
      step: "scripts/smoke-chrome.mjs",
      stdout: JSON.stringify(smokeResult, null, 2),
      stderr: "",
    });
  }
  if (mobileResult.status !== "pass") {
    throw Object.assign(new Error("release mobile smoke failed"), {
      step: "scripts/smoke-mobile.mjs",
      stdout: JSON.stringify(mobileResult, null, 2),
      stderr: "",
    });
  }
  if (interactionResult.status !== "pass") {
    throw Object.assign(new Error("release interaction smoke failed"), {
      step: "scripts/smoke-interactions.mjs",
      stdout: JSON.stringify(interactionResult, null, 2),
      stderr: "",
    });
  }
  if (accessibilityResult.status !== "pass") {
    throw Object.assign(new Error("release accessibility smoke failed"), {
      step: "scripts/smoke-a11y.mjs",
      stdout: JSON.stringify(accessibilityResult, null, 2),
      stderr: "",
    });
  }

  console.log(JSON.stringify({
    status: "pass",
    releaseDir: relative(root, releaseDir),
    baseUrl,
    package: packageResult,
    verify: verifyResult,
    headers: headerResult,
    fallbacks: fallbackResult,
    smoke: {
      status: smokeResult.status,
      routeCount: smokeResult.routeCount,
      retryAttempts: smokeResult.retryAttempts || [],
      consoleIssues: smokeResult.consoleIssues,
      networkIssues: smokeResult.networkIssues,
      failures: smokeResult.failures,
    },
    mobile: {
      status: mobileResult.status,
      routeCount: mobileResult.routeCount,
      retryAttempts: mobileResult.retryAttempts || [],
      viewport: mobileResult.viewport,
      layoutIssues: mobileResult.layoutIssues,
      consoleIssues: mobileResult.consoleIssues,
      networkIssues: mobileResult.networkIssues,
      failures: mobileResult.failures,
    },
    interactions: {
      status: interactionResult.status,
      stepCount: interactionResult.steps ? interactionResult.steps.length : 0,
      retryAttempts: interactionResult.retryAttempts || [],
      persistedChecks: interactionResult.persistedChecks,
      consoleIssues: interactionResult.consoleIssues,
      networkIssues: interactionResult.networkIssues,
      failures: interactionResult.failures,
    },
    accessibility: {
      status: accessibilityResult.status,
      retryAttempts: accessibilityResult.retryAttempts || [],
      checks: accessibilityResult.checks,
      consoleIssues: accessibilityResult.consoleIssues,
      networkIssues: accessibilityResult.networkIssues,
      failures: accessibilityResult.failures,
    },
  }, null, 2));
}

main().catch((error) => {
  console.error(JSON.stringify({
    status: "fail",
    step: error.step || "scripts/smoke-release.mjs",
    message: error.message,
    stdout: error.stdout || "",
    stderr: error.stderr || "",
    attempts: error.attempts || [],
  }, null, 2));
  process.exit(1);
});
