#!/usr/bin/env node

import { spawn, spawnSync } from "node:child_process";
import { createServer } from "node:http";
import {
  existsSync,
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

function createReleaseServer() {
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
  try {
    smokeResult = parseJsonOutput(
      (await runNodeScriptAsync("scripts/smoke-chrome.mjs", {
        BASE_URL: baseUrl,
        SMOKE_PROGRESS: "1",
      }, 120000)).stdout,
      "fail",
    );
    mobileResult = parseJsonOutput(
      (await runNodeScriptAsync("scripts/smoke-mobile.mjs", {
        BASE_URL: baseUrl,
        SMOKE_PROGRESS: "1",
      }, 120000)).stdout,
      "fail",
    );
    interactionResult = parseJsonOutput(
      (await runNodeScriptAsync("scripts/smoke-interactions.mjs", {
        BASE_URL: baseUrl,
        SMOKE_PROGRESS: "1",
      }, 120000)).stdout,
      "fail",
    );
    accessibilityResult = parseJsonOutput(
      (await runNodeScriptAsync("scripts/smoke-a11y.mjs", {
        BASE_URL: baseUrl,
        SMOKE_PROGRESS: "1",
      }, 120000)).stdout,
      "fail",
    );
  } finally {
    await close(server);
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
    smoke: {
      status: smokeResult.status,
      routeCount: smokeResult.routeCount,
      consoleIssues: smokeResult.consoleIssues,
      networkIssues: smokeResult.networkIssues,
      failures: smokeResult.failures,
    },
    mobile: {
      status: mobileResult.status,
      routeCount: mobileResult.routeCount,
      viewport: mobileResult.viewport,
      layoutIssues: mobileResult.layoutIssues,
      consoleIssues: mobileResult.consoleIssues,
      networkIssues: mobileResult.networkIssues,
      failures: mobileResult.failures,
    },
    interactions: {
      status: interactionResult.status,
      stepCount: interactionResult.steps ? interactionResult.steps.length : 0,
      persistedChecks: interactionResult.persistedChecks,
      consoleIssues: interactionResult.consoleIssues,
      networkIssues: interactionResult.networkIssues,
      failures: interactionResult.failures,
    },
    accessibility: {
      status: accessibilityResult.status,
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
  }, null, 2));
  process.exit(1);
});
