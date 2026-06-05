#!/usr/bin/env node

import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import {
  copyFileSync,
  existsSync,
  mkdirSync,
  readdirSync,
  readFileSync,
  rmSync,
  statSync,
  writeFileSync,
} from "node:fs";
import { basename, dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const outDir = process.env.RELEASE_OUT_DIR
  ? resolve(root, process.env.RELEASE_OUT_DIR)
  : join(root, "dist", "release");
const sourceEntries = [
  "index.html",
  "app.js",
  "styles.css",
  "favicon.svg",
  "README.md",
  "data",
  "vendor",
];

function sha256(path) {
  return createHash("sha256").update(readFileSync(path)).digest("hex");
}

function walkFiles(baseDir) {
  const files = [];
  function visit(path) {
    const stat = statSync(path);
    if (stat.isDirectory()) {
      for (const name of readdirSync(path).sort()) visit(join(path, name));
      return;
    }
    if (stat.isFile()) files.push(path);
  }
  visit(baseDir);
  return files;
}

function copyEntry(entry) {
  const source = join(root, entry);
  const target = join(outDir, entry);
  if (!existsSync(source)) throw new Error(`Missing release source: ${entry}`);
  const stat = statSync(source);
  if (stat.isDirectory()) {
    for (const file of walkFiles(source)) {
      const rel = relative(source, file);
      const dest = join(target, rel);
      mkdirSync(dirname(dest), { recursive: true });
      copyFileSync(file, dest);
    }
    return;
  }
  mkdirSync(dirname(target), { recursive: true });
  copyFileSync(source, target);
}

function buildManifest() {
  const source = sourceMetadata();
  const files = walkFiles(outDir)
    .filter((file) => !["RELEASE.md", "release-manifest.json"].includes(basename(file)))
    .map((file) => {
      const rel = relative(outDir, file).replaceAll("\\", "/");
      return {
        path: rel,
        bytes: statSync(file).size,
        sha256: sha256(file),
      };
    });
  return {
    name: "JooPark Workspace",
    version: "3.0.0",
    generatedAt: new Date().toISOString(),
    sourceCommit: source.commit,
    source,
    files,
  };
}

function gitOutput(args) {
  return gitOutputRaw(args).trim();
}

function gitOutputRaw(args) {
  try {
    return execFileSync("git", args, {
      cwd: root,
      encoding: "utf-8",
      stdio: ["ignore", "pipe", "ignore"],
    }).replace(/\r?\n$/, "");
  } catch {
    return "";
  }
}

function currentCommit() {
  return gitOutput(["rev-parse", "--short", "HEAD"]);
}

function sourceMetadata() {
  const statusText = gitOutputRaw(["status", "--short", "--untracked-files=all"]);
  const dirtyFiles = statusText ? statusText.split("\n").filter(Boolean) : [];
  return {
    commit: process.env.SOURCE_COMMIT || currentCommit(),
    branch: gitOutput(["branch", "--show-current"]) || gitOutput(["rev-parse", "--abbrev-ref", "HEAD"]),
    dirty: dirtyFiles.length > 0,
    dirtyFiles,
  };
}

function writeReleaseNotes(manifest) {
  const totalBytes = manifest.files.reduce((sum, file) => sum + file.bytes, 0);
  const dirtyLabel = manifest.source?.dirty ? `dirty (${manifest.source.dirtyFiles.length} paths)` : "clean";
  const lines = [
    "# JooPark Workspace Release",
    "",
    `- Version: ${manifest.version}`,
    `- Generated: ${manifest.generatedAt}`,
    `- Source commit: ${manifest.sourceCommit}`,
    `- Source branch: ${manifest.source?.branch || "unknown"}`,
    `- Source tree: ${dirtyLabel}`,
    `- Runtime files: ${manifest.files.length}`,
    `- Total bytes: ${totalBytes}`,
    "",
    "## Run",
    "",
    "```bash",
    "python3 -m http.server 5178",
    "```",
    "",
    "Open `http://127.0.0.1:5178/` from this directory. If the port is busy, use another port and set `BASE_URL` to match.",
    "",
    "## Verify",
    "",
    "From the project root, run:",
    "",
    "```bash",
    "node scripts/verify-release.mjs",
    "node scripts/audit-release-readiness.mjs --run-gates",
    "BASE_URL=http://127.0.0.1:5178 node scripts/smoke-chrome.mjs",
    "BASE_URL=http://127.0.0.1:5178 node scripts/smoke-mobile.mjs",
    "BASE_URL=http://127.0.0.1:5178 node scripts/smoke-interactions.mjs",
    "BASE_URL=http://127.0.0.1:5178 node scripts/smoke-a11y.mjs",
    "node scripts/smoke-release.mjs",
    "```",
    "",
    "Expected result: verification and smoke commands report `status` as `pass`; the smoke output should also have empty `consoleIssues` and `networkIssues`. `smoke-mobile.mjs` must also report empty `layoutIssues`. `smoke-a11y.mjs` must report every keyboard and ARIA check as `true`. `audit-release-readiness.mjs --run-gates` maps release requirements to concrete evidence and reports external publish blockers such as a missing Git remote. `smoke-release.mjs` is the full packaged-release gate: it rebuilds `dist/release`, verifies the manifest, serves the package on a temporary local port, route-smokes the served package, checks the mobile layout, runs the click/input interaction smoke, and runs the keyboard/ARIA accessibility smoke.",
    "",
  ];
  writeFileSync(join(outDir, "RELEASE.md"), lines.join("\n"), "utf-8");
}

function writeDeploySupportFiles() {
  copyFileSync(join(outDir, "index.html"), join(outDir, "404.html"));
  writeFileSync(join(outDir, "_redirects"), [
    "# Netlify fallback for static SPA deployments.",
    "# Existing files are served normally; unmatched direct paths rewrite to the app shell.",
    "/* /index.html 200",
    "",
  ].join("\n"), "utf-8");
  writeFileSync(join(outDir, "_headers"), [
    "/*",
    "  X-Content-Type-Options: nosniff",
    "  X-Frame-Options: DENY",
    "  Referrer-Policy: strict-origin-when-cross-origin",
    "  Permissions-Policy: camera=(), microphone=(), geolocation=()",
    "/vendor/*",
    "  Cache-Control: public, max-age=31536000, immutable",
    "/app.js",
    "  Cache-Control: no-cache",
    "/styles.css",
    "  Cache-Control: no-cache",
    "/index.html",
    "  Cache-Control: no-cache",
    "/404.html",
    "  Cache-Control: no-cache",
    "",
  ].join("\n"), "utf-8");
  writeFileSync(join(outDir, "vercel.json"), `${JSON.stringify({
    $schema: "https://openapi.vercel.sh/vercel.json",
    cleanUrls: false,
    trailingSlash: false,
    headers: [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
      {
        source: "/vendor/(.*)",
        headers: [
          { key: "Cache-Control", value: "public, max-age=31536000, immutable" },
        ],
      },
      {
        source: "/(app.js|styles.css|index.html|404.html)",
        headers: [
          { key: "Cache-Control", value: "no-cache" },
        ],
      },
    ],
  }, null, 2)}\n`, "utf-8");
}

rmSync(outDir, { recursive: true, force: true });
mkdirSync(outDir, { recursive: true });
for (const entry of sourceEntries) copyEntry(entry);
writeDeploySupportFiles();
const manifest = buildManifest();
writeReleaseNotes(manifest);
manifest.files = buildManifest().files;
writeFileSync(join(outDir, "release-manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`, "utf-8");

console.log(JSON.stringify({
  status: "pass",
  output: relative(root, outDir),
  files: manifest.files.length,
  bytes: manifest.files.reduce((sum, file) => sum + file.bytes, 0),
}, null, 2));
