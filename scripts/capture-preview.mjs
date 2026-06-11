#!/usr/bin/env node

import { spawn } from "node:child_process";
import { createReadStream, existsSync, mkdirSync, rmSync, statSync, writeFileSync } from "node:fs";
import { createServer } from "node:http";
import { tmpdir } from "node:os";
import { dirname, extname, join, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const args = process.argv.slice(2);
const chromePath = process.env.CHROME_PATH || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const width = positiveIntegerOption(argValue("--width") || process.env.PREVIEW_WIDTH, 1200);
const height = positiveIntegerOption(argValue("--height") || process.env.PREVIEW_HEIGHT, 630);
const outPath = resolve(root, argValue("--out") || process.env.PREVIEW_OUT || "social-preview.png");
const requestedBaseUrl = (argValue("--base-url") || process.env.BASE_URL || "").replace(/\/+$/, "");
const tmpProfile = join(tmpdir(), `joopark-preview-${Date.now()}-${Math.random().toString(36).slice(2)}`);

function optionValue(argsList, name) {
  const inline = argsList.find((arg) => arg.startsWith(`${name}=`));
  if (inline) return inline.slice(name.length + 1);
  const index = argsList.indexOf(name);
  if (index < 0) return "";
  const value = argsList[index + 1] || "";
  return value.startsWith("--") ? "" : value;
}

function argValue(name) {
  return optionValue(args, name);
}

function positiveIntegerOption(value, fallback) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? Math.trunc(parsed) : fallback;
}

class CdpClient {
  constructor(wsUrl) {
    this.wsUrl = wsUrl;
    this.nextId = 1;
    this.pending = new Map();
  }

  async open() {
    this.ws = new WebSocket(this.wsUrl);
    await new Promise((resolveOpen, rejectOpen) => {
      const timer = setTimeout(() => rejectOpen(new Error("Timed out opening CDP websocket")), 8000);
      this.ws.addEventListener("message", (event) => this.handleMessage(event.data));
      this.ws.addEventListener("open", () => {
        clearTimeout(timer);
        resolveOpen();
      }, { once: true });
      this.ws.addEventListener("error", () => {
        clearTimeout(timer);
        rejectOpen(new Error(`Failed to open CDP websocket: ${this.wsUrl}`));
      }, { once: true });
    });
  }

  handleMessage(data) {
    const message = JSON.parse(String(data));
    if (!message.id || !this.pending.has(message.id)) return;
    const entry = this.pending.get(message.id);
    this.pending.delete(message.id);
    clearTimeout(entry.timer);
    if (message.error) entry.reject(new Error(`${message.error.message || "CDP error"} (${message.error.code || "no-code"})`));
    else entry.resolve(message.result || {});
  }

  send(method, params = {}, timeoutMs = 10000) {
    const id = this.nextId++;
    this.ws.send(JSON.stringify({ id, method, params }));
    return new Promise((resolveSend, rejectSend) => {
      const timer = setTimeout(() => {
        if (!this.pending.has(id)) return;
        this.pending.delete(id);
        rejectSend(new Error(`Timed out waiting for ${method}`));
      }, timeoutMs);
      this.pending.set(id, { resolve: resolveSend, reject: rejectSend, timer });
    });
  }

  close() {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) this.ws.close();
  }
}

function contentType(pathname) {
  return {
    ".css": "text/css; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".png": "image/png",
    ".svg": "image/svg+xml; charset=utf-8",
    ".webmanifest": "application/manifest+json; charset=utf-8",
  }[extname(pathname)] || "application/octet-stream";
}

function previewRequestPath(pathname) {
  let decoded;
  try {
    decoded = decodeURIComponent(pathname);
  } catch {
    return null;
  }
  return decoded === "/" ? "index.html" : decoded.replace(/^\/+/, "");
}

function previewStaticTarget(pathname) {
  const requestPath = previewRequestPath(pathname);
  if (!requestPath) return null;
  const target = resolve(root, requestPath);
  const allowedPrefix = `${root}${sep}`;
  return target === root || target.startsWith(allowedPrefix) ? target : null;
}

function startStaticServer() {
  const server = createServer((request, response) => {
    const rawPath = new URL(request.url || "/", "http://127.0.0.1").pathname;
    const filePath = previewStaticTarget(rawPath);
    if (!filePath) {
      response.writeHead(403, { "Content-Type": "text/plain; charset=utf-8" });
      response.end("Forbidden");
      return;
    }
    if (!existsSync(filePath) || !statSync(filePath).isFile()) {
      response.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
      response.end("Not found");
      return;
    }
    response.writeHead(200, {
      "Content-Type": contentType(filePath),
      "Cache-Control": "no-store",
    });
    createReadStream(filePath).pipe(response);
  });
  return new Promise((resolveServer, rejectServer) => {
    server.once("error", rejectServer);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      resolveServer({
        server,
        baseUrl: `http://127.0.0.1:${address.port}`,
      });
    });
  });
}

function waitForDevTools(chrome) {
  let stderr = "";
  return new Promise((resolveWs, rejectWs) => {
    const timer = setTimeout(() => rejectWs(new Error(`Timed out waiting for DevTools endpoint.\n${stderr}`)), 12000);
    chrome.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
      const match = stderr.match(/DevTools listening on (ws:\/\/[^\s]+)/);
      if (match) {
        clearTimeout(timer);
        resolveWs(match[1]);
      }
    });
    chrome.on("exit", (code) => {
      clearTimeout(timer);
      rejectWs(new Error(`Chrome exited before DevTools endpoint was ready: ${code}\n${stderr}`));
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
  throw new Error(`No page target exposed by Chrome${lastError ? `: ${lastError.message}` : ""}`);
}

function delay(ms) {
  return new Promise((resolveDelay) => setTimeout(resolveDelay, ms));
}

async function evaluate(client, expression, timeoutMs = 30000) {
  const result = await client.send("Runtime.evaluate", {
    expression,
    awaitPromise: true,
    returnByValue: true,
  }, timeoutMs);
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.text || "Runtime evaluation failed");
  return result.result ? result.result.value : undefined;
}

function pngInfo(buffer) {
  const signature = buffer.subarray(0, 8).toString("hex");
  if (signature !== "89504e470d0a1a0a") throw new Error("Preview output is not a PNG");
  return {
    width: buffer.readUInt32BE(16),
    height: buffer.readUInt32BE(20),
  };
}

async function terminateProcess(child) {
  if (!child || child.exitCode !== null || child.signalCode !== null) return;
  child.kill("SIGTERM");
  await delay(800);
  if (child.exitCode === null && child.signalCode === null) child.kill("SIGKILL");
}

async function main() {
  let serverHandle = null;
  let chrome = null;
  let pageClient = null;
  try {
    if (!Number.isFinite(width) || !Number.isFinite(height) || width < 320 || height < 240) {
      throw new Error("Preview width/height must be finite and at least 320x240");
    }
    serverHandle = requestedBaseUrl ? null : await startStaticServer();
    const baseUrl = requestedBaseUrl || serverHandle.baseUrl;
    const targetUrl = `${baseUrl}/#home`;
    chrome = spawn(chromePath, [
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
      `--window-size=${width},${height}`,
      "about:blank",
    ], { stdio: ["ignore", "ignore", "pipe"] });

    const browserWsUrl = await waitForDevTools(chrome);
    pageClient = new CdpClient(await pageWebSocketUrl(browserWsUrl));
    await pageClient.open();
    await pageClient.send("Page.enable");
    await pageClient.send("Runtime.enable");
    await pageClient.send("Emulation.setDeviceMetricsOverride", {
      width,
      height,
      deviceScaleFactor: 1,
      mobile: false,
    });
    await pageClient.send("Page.navigate", { url: targetUrl });
    await evaluate(pageClient, `
      new Promise((resolve, reject) => {
        const started = Date.now();
        const check = () => {
          const ready = document.readyState === "complete" &&
            document.body &&
            document.body.dataset.view === "home" &&
            document.querySelector(".home-hero") &&
            document.querySelector(".home-tiles");
          if (ready) resolve(true);
          else if (Date.now() - started > 15000) reject(new Error("home route not ready"));
          else setTimeout(check, 100);
        };
        check();
      })
    `);
    await delay(900);
    const screenshot = await pageClient.send("Page.captureScreenshot", {
      format: "png",
      fromSurface: true,
      captureBeyondViewport: false,
    }, 30000);
    const buffer = Buffer.from(screenshot.data, "base64");
    const info = pngInfo(buffer);
    if (info.width !== width || info.height !== height) {
      throw new Error(`Unexpected preview dimensions ${info.width}x${info.height}; expected ${width}x${height}`);
    }
    mkdirSync(dirname(outPath), { recursive: true });
    writeFileSync(outPath, buffer);
    console.log(JSON.stringify({
      status: "pass",
      outPath: outPath.replace(`${root}/`, ""),
      baseUrl,
      width: info.width,
      height: info.height,
      bytes: buffer.length,
    }, null, 2));
  } finally {
    if (pageClient) pageClient.close();
    await terminateProcess(chrome);
    if (serverHandle) await new Promise((resolveClose) => serverHandle.server.close(resolveClose));
    rmSync(tmpProfile, { recursive: true, force: true });
  }
}

main().catch((error) => {
  console.error(JSON.stringify({
    status: "fail",
    error: error.stack || error.message,
  }, null, 2));
  process.exit(1);
});
