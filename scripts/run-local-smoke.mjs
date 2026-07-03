#!/usr/bin/env node

import { spawn } from "node:child_process";
import { createReadStream, existsSync, statSync } from "node:fs";
import { createServer } from "node:http";
import { extname, join, normalize, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(fileURLToPath(new URL("..", import.meta.url)));
const script = process.argv[2];
const args = process.argv.slice(3);

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

if (!script) {
  console.error("Usage: node scripts/run-local-smoke.mjs <script> [args...]");
  process.exit(1);
}

function requestPath(url) {
  try {
    const parsed = new URL(url || "/", "http://127.0.0.1");
    const pathname = decodeURIComponent(parsed.pathname);
    return pathname === "/" ? "/index.html" : pathname;
  } catch {
    return "/index.html";
  }
}

function safeFilePath(pathname) {
  const normalized = normalize(pathname).replace(/^(\.\.(?:\/|\\|$))+/, "");
  const target = join(root, normalized);
  return target.startsWith(root + sep) || target === root ? target : join(root, "index.html");
}

const server = createServer((req, res) => {
  let target = safeFilePath(requestPath(req.url));
  if (existsSync(target) && statSync(target).isDirectory()) target = join(target, "index.html");
  if (!existsSync(target) || !statSync(target).isFile()) {
    res.writeHead(404, { "content-type": "text/plain; charset=utf-8" });
    res.end("Not found");
    return;
  }
  res.writeHead(200, {
    "content-type": contentTypes[extname(target)] || "application/octet-stream",
    "cache-control": "no-store",
  });
  createReadStream(target).pipe(res);
});

function listen() {
  return new Promise((resolveListen, rejectListen) => {
    server.once("error", rejectListen);
    server.listen(0, "127.0.0.1", () => {
      server.off("error", rejectListen);
      resolveListen(server.address());
    });
  });
}

function closeServer() {
  return new Promise((resolveClose) => server.close(() => resolveClose()));
}

const address = await listen();
const baseUrl = `http://${address.address}:${address.port}`;
const child = spawn(process.execPath, [script, ...args], {
  cwd: root,
  env: { ...process.env, BASE_URL: process.env.BASE_URL || baseUrl },
  stdio: "inherit",
});

const code = await new Promise((resolveExit) => {
  child.once("exit", (exitCode, signal) => {
    if (signal) resolveExit(1);
    else resolveExit(exitCode || 0);
  });
});

await closeServer();
process.exit(code);
